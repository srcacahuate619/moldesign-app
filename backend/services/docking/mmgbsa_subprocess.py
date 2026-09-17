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

La pose acoplada es obligatoria. Si falta o no se puede leer, se devuelve
status=not_evaluated y mmgbsa=null, sin generar un conformador desde SMILES.
Las fórmulas y parámetros del cálculo sobre una pose válida no cambian.
"""
from __future__ import annotations

# ruff: noqa: T201 -- stdout es el protocolo JSON del proceso hijo

import json
import math
from contextlib import redirect_stdout
import pathlib
import sys


def _extract_first_pose_coords(poses_sdf: str) -> list[tuple[float, float, float]] | None:
    """Extrae las coordenadas (x, y, z) de la primera pose de un SDF de Vina.

    Devuelve None si el archivo no se puede leer o no contiene una pose con
    coordenadas 3D. El caller se abstiene; nunca reconstruye desde SMILES.

    Nota (2026-08-04): NO usamos `conf.Is3D()` como gate porque RDKit puede
    reportar False si el flag de dimensión del header V2000 está mal aunque
    las coordenadas Z sean reales (algunos SDF de Vina salen así). La
    Se acepta un conformador marcado 3D (también si es plano), o con Z no
    nula aunque el header esté mal. Todas las coordenadas deben ser finitas.
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
        has_3d = conf.Is3D()
        for i in range(n_atoms):
            pos = conf.GetAtomPosition(i)
            coords = (float(pos.x), float(pos.y), float(pos.z))
            if not all(math.isfinite(value) for value in coords):
                return None
            positions.append(coords)
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
        if not pose_coords:
            print(json.dumps({
                "mmgbsa": None, "used_pose": False, "status": "not_evaluated",
                "error": "No se dispone de una pose acoplada válida; MM-GBSA no evaluado.",
            }))
            return 0
        with redirect_stdout(sys.stderr):
            from services.chemistry.molchamb_v2 import compute_mmgbsa_from_pose
            result = compute_mmgbsa_from_pose(
                protein_pdb, smiles, pose_coords, max_iter=max_iter,
                ligand_sdf_path=poses_sdf,
            )
        result.setdefault("used_pose", True)
        score = result.get("mmgbsa")
        if score is None or not math.isfinite(score):
            result["mmgbsa"] = None
            result["status"] = "not_evaluated"
            result.setdefault("error", "MM-GBSA no produjo una energía finita.")
        else:
            result["status"] = "evaluated"

        print(json.dumps(result))
        return 0
    except Exception as exc:
        print(json.dumps({"mmgbsa": None, "status": "not_evaluated", "error": str(exc)[:500]}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
