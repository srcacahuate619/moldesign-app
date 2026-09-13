"""Wrapper de subprocess para compute_mmgbsa con timeout REAL.

Problema v1.7: `compute_mmgbsa` (OpenMM/MM-GBSA) se lanzaba vía
`loop.run_in_executor(None, ...)` + `asyncio.wait_for(timeout=60)`. wait_for
expira el *wrapper*, pero el thread del executor SIGUE corriendo OpenMM en
background → uvicorn queda con threads quemando CPU (48 threads ~1288%) y no
hay forma de matarlos.

Solución: este script se ejecuta como SUBPROCESS desde queue_handler. Si el
caller aplica timeout (asyncio.wait_for + proc.kill), el proceso hijo se mata
de verdad y no queda nada corriendo. Escribe el resultado como JSON en stdout.

Uso:
    python mmgbsa_subprocess.py <protein_pdb> <smiles> [max_iter] [poses_sdf]

FIX v2.1 (2026-08-04, MM-GBSA -27983 kcal/mol): antes el cálculo usaba
`compute_mmgbsa(smiles)` que genera la conformación del ligando con RDKit
EmbedMolecule y la coloca ARBITRARIAMENTE en el complejo → overlap estérico
→ términos Lennard-Jones explotan → valores absurdos (-27983 kcal/mol) y
físicamente sin sentido (no es la pose de docking). Ahora, si el caller pasa
`poses_sdf` (el archivo .sdf con las poses reales de Vina), extraemos las
coordenadas de la pose #1 y usamos `compute_mmgbsa_from_pose` — el ligando
queda en el bolsillo real y el ΔG es el de la pose dockeada.
"""
from __future__ import annotations

import json
import pathlib
import sys


def _extract_first_pose_coords(poses_sdf: str) -> list[tuple[float, float, float]] | None:
    """Extrae las coordenadas (x, y, z) de la primera pose de un SDF de Vina.

    Devuelve None si el archivo no se puede leer o no contiene una pose con
    coordenadas 3D (degradación: el caller caerá al fallback SMILES-only).

    Nota (2026-08-04): NO usamos `conf.Is3D()` como gate porque RDKit puede
    reportar False si el flag de dimensión del header V2000 está mal aunque
    las coordenadas Z sean reales (algunos SDF de Vina salen así). La
    heurística robusta es: hay conformer Y al menos un átomo con Z != 0.
    """
    try:
        from rdkit import Chem
        with open(poses_sdf, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        mol = Chem.MolFromMolBlock(content, sanitize=False, removeHs=False)
        if mol is None:
            return None
        conf = mol.GetConformer()
        if conf is None:
            return None
        n_atoms = mol.GetNumAtoms()
        if n_atoms == 0:
            return None
        positions = []
        has_3d = False
        for i in range(n_atoms):
            pos = conf.GetAtomPosition(i)
            positions.append((float(pos.x), float(pos.y), float(pos.z)))
            if abs(pos.z) > 1e-6:
                has_3d = True
        if not has_3d:
            return None
        return positions
    except Exception:
        return None


def main() -> int:
    # ── ARGUMENTOS: POSICIONALES NO, PORQUE YA FALLARON ──────────────────
    #
    # Auditoria del 2026-09-04. El contrato era
    #
    #     <proteina> <smiles> [max_iter] [poses_sdf]
    #
    # y los DOS llamadores de produccion —`services/pipeline/runner.py` y
    # `services/docking/queue_handler.py`— construian `[proteina, smiles]` y
    # anadian el SDF, que caia en la posicion de `max_iter`:
    #
    #     ValueError: invalid literal for int() with base 10: 'fake_pose.sdf'
    #
    # El proceso moria en la primera linea util. MM-GBSA llevaba sin funcionar
    # en ningun camino de produccion desde el commit que decia arreglarlo
    # («FIX v2.1 (2026-08-04): pasar el SDF de poses de Vina al subprocess»).
    # El fallo era invisible porque el llamador captura la excepcion y trata la
    # ausencia de resultado como «MM-GBSA no disponible».
    #
    # Se acepta el SDF POR NOMBRE (`--poses`), que es lo que hace imposible
    # confundirlo con un entero, y se conserva la forma posicional antigua para
    # no romper a nadie que la use. Si el tercer posicional no es un numero se
    # dice, en vez de morir con un ValueError sin contexto.
    argumentos = sys.argv[1:]
    poses_sdf: str | None = None
    posicionales: list[str] = []
    i = 0
    while i < len(argumentos):
        actual = argumentos[i]
        if actual == "--poses" and i + 1 < len(argumentos):
            poses_sdf = argumentos[i + 1]
            i += 2
            continue
        if actual.startswith("--poses="):
            poses_sdf = actual.split("=", 1)[1]
            i += 1
            continue
        posicionales.append(actual)
        i += 1

    if len(posicionales) < 2:
        print(json.dumps({"error": "faltan argumentos"}))
        return 2
    protein_pdb = posicionales[0]
    smiles = posicionales[1]

    max_iter = 500
    if len(posicionales) > 2:
        tercero = posicionales[2]
        if tercero.isdigit():
            max_iter = int(tercero)
        elif tercero.lower().endswith((".sdf", ".pdbqt")):
            # La forma antigua, y el error exacto que se documenta arriba: se
            # acepta en vez de morir, porque un SDF en esa posicion sigue
            # siendo una intencion legible.
            poses_sdf = poses_sdf or tercero
        else:
            print(json.dumps({
                "error": (
                    f"tercer argumento no interpretable: {tercero!r}. "
                    "Se esperaba max_iter (entero) o un .sdf de poses; "
                    "pasa el SDF con --poses <ruta>."
                )
            }))
            return 2
    if poses_sdf is None and len(posicionales) > 3:
        poses_sdf = posicionales[3]

    try:
        # La raiz del backend se deduce de la posicion de ESTE archivo, que
        # vive en `backend/services/docking/`. Aqui habia una ruta absoluta a
        # la maquina de construccion: en cualquier instalacion real ese
        # directorio no existe, el import de `services.chemistry.molchamb_v2`
        # fallaba, y el `except` de abajo lo devolvia como
        # `{"error": "No module named 'services'"}`.
        #
        # Es decir: MM-GBSA no podia funcionar en NINGUNA maquina que no
        # fuera la de construccion, y fallaba con un mensaje que no apunta
        # a la causa.
        sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

        pose_coords = _extract_first_pose_coords(poses_sdf) if poses_sdf else None
        if pose_coords:
            from services.chemistry.molchamb_v2 import compute_mmgbsa_from_pose
            result = compute_mmgbsa_from_pose(
                protein_pdb, smiles, pose_coords, max_iter=max_iter,
                ligand_sdf_path=poses_sdf,  # FIX NaN: usar SDF como topología con H coords
            )
            # Marcar que el cálculo usó la pose real (para depuración).
            result["used_pose"] = True
        else:
            from services.chemistry.molchamb_v2 import compute_mmgbsa
            result = compute_mmgbsa(protein_pdb, smiles, max_iter=max_iter)
            result["used_pose"] = False

        print(json.dumps(result))
        return 0
    except Exception as exc:
        print(json.dumps({"error": str(exc)[:500]}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
