#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""run_enspilot01_diversidad.py — ENS-PILOT-01: ¿la piscina del ensemble contiene diversidad?

Qué se demostró y qué falta
---------------------------
El 2026-09-17 se corrigió ENS-05: `_prepare_ligand_pdbqt` sustituía el confórmero
del hash derivado (`<hash>__c07`) por el del hash canónico —la conformación 0,
que existe siempre—, así que **las K corridas de Vina partían de la misma
geometría** y `conformer_index` era falso.

Lo que se demostró entonces fue que **Meeko recibe el SDF correcto** de cada
conformación, sobre un ensemble instrumentado de tres benceno. Lo que NO se
demostró es que la piscina *contenga* diversidad al final del camino real, con
Vina de verdad, sobre el pipeline del producto.

Este piloto lo mide. Es **verificación del arreglo, no evidencia de ventaja**:
nada de aquí dice que el ensemble mejore nada. Esa pregunta es ENS-PROD-01, con
su prerregistro, su cohorte y sus 248 complejos.

Las cuatro comprobaciones (bloque 1 de `VALIDACION_EN_SERVIDOR.md`)
------------------------------------------------------------------
1. **El `conformer_sha256` difiere por conformación en la corrida real**, no
   sólo en las pruebas. Es el dato que hizo invisible ENS-05 durante toda su
   vida: un índice es una etiqueta, un hash es comprobable.
2. **RMSD pareado entre poses etiquetadas con `conformer_index` distinto**, y
   entre las conformaciones de ENTRADA. Si las entradas fueran iguales, el
   arreglo no habría llegado; si las entradas difieren y las poses convergen,
   eso es una lectura legítima (misma solución desde puntos distintos) y no un
   fallo.
3. **Cuántas conformaciones distintas sobreviven al top-N entregado.**
4. **Las seis puertas de `pose_recovery` sobre artefactos REALES** de Vina y
   Meeko, no sobre los SDF escritos a mano de las pruebas. Con ligandos
   macrocíclicos incluidos, para ejercitar el descarte de pseudo-átomos de
   pegado.

El protocolo
------------
Se ejecuta el camino del producto —`generate_conformer_ensemble` →
`run_ensemble_docking` → `run_vina_docking`— con el intérprete que se
distribuye, no con el de desarrollo: lo que se verifica tiene que ser lo que se
entrega.

  * `exhaustiveness=32`, que es lo que ejecuta el producto (`runner.py:696`),
    y NO el 8 de la evidencia sellada. Un piloto del pipeline actual se corre
    con el presupuesto del pipeline actual.
  * `K=30`, `num_modes=9`, semilla 42.
  * Receptor: el 5TUN ya preparado de `REC-07`, con su caja `G_ADAPT`. Se pasa
    como `prepared_receptor_bytes`, así que no se consulta el catálogo ni la red.

Lo que este piloto NO es
------------------------
**No es un redocking.** Los ligandos no son los nativos de 5TUN: se acoplan
contra una cavidad que no es la suya. Ninguna afinidad de aquí significa nada, y
el artefacto no las presenta como resultado. Lo que se mide es geometría de la
piscina: qué entró, qué salió y si se puede demostrar de dónde vino.

**Los diez ligandos quedan quemados.** Están declarados abajo precisamente para
que ENS-PROD-01 los excluya de su cohorte.

Uso
---
    python-embed/python.exe scripts/run_enspilot01_diversidad.py
    python-embed/python.exe scripts/run_enspilot01_diversidad.py --reanudar
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import itertools
import json
import math
import os
import platform
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND = PROJECT_ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

# El preparador usa `sys.executable` en modo DESKTOP; en CLOUD iría a buscar un
# intérprete de Linux que aquí no existe.
os.environ.setdefault("APP_MODE", "DESKTOP")
# Sin esto el arnés no replica el entorno de Tauri y `/health` mentiría: la
# lección de `qa_vm_audit.py`, que aquí vale igual.
os.environ.setdefault("VINA_EXECUTABLE_PATH",
                      str(PROJECT_ROOT / "tools" / "vina" / "vina.exe"))

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                              # noqa: BLE001
        pass

# ── Congelado antes de correr ────────────────────────────────────────────────
K = 30
NUM_POSES = 9
SEMILLA = 42
EXHAUSTIVIDAD = 32
CENTRO = (11.104, 135.221, 21.288)
TAMANO = (19.0, 25.3, 25.9)
RECEPTOR = PROJECT_ROOT / "scripts/artifacts_science/REC-07/_work/5TUN_receptor.pdbqt"

#: Los diez ligandos, declarados para que ENS-PROD-01 los excluya. Dos son
#: macrociclos: sin ellos no se ejercita el descarte de pseudo-átomos de pegado
#: que Meeko inserta al abrir el anillo, que es justo la rama del lector de poses
#: que nunca había visto un artefacto real.
LIGANDOS: list[dict] = [
    {"nombre": "aspirina", "smiles": "CC(=O)Oc1ccccc1C(=O)O", "macrociclo": False},
    {"nombre": "ibuprofeno", "smiles": "CC(C)Cc1ccc(cc1)C(C)C(=O)O", "macrociclo": False},
    {"nombre": "naproxeno", "smiles": "COc1ccc2cc(ccc2c1)C(C)C(=O)O", "macrociclo": False},
    {"nombre": "cafeina", "smiles": "Cn1cnc2c1c(=O)n(C)c(=O)n2C", "macrociclo": False},
    {"nombre": "paracetamol", "smiles": "CC(=O)Nc1ccc(O)cc1", "macrociclo": False},
    {"nombre": "warfarina", "smiles": "CC(=O)CC(c1ccccc1)c1c(O)c2ccccc2oc1=O", "macrociclo": False},
    {"nombre": "celecoxib",
     "smiles": "Cc1ccc(cc1)-c1cc(nn1-c1ccc(cc1)S(N)(=O)=O)C(F)(F)F", "macrociclo": False},
    {"nombre": "indometacina",
     "smiles": "COc1ccc2c(c1)c(CC(=O)O)c(C)n2C(=O)c1ccc(Cl)cc1", "macrociclo": False},
    {"nombre": "muscona", "smiles": "CC1CCCCCCCCCCCCC1=O", "macrociclo": True},
    {"nombre": "exaltolida", "smiles": "O=C1CCCCCCCCCCCCCCO1", "macrociclo": True},
]


# ─────────────────────────────────────────────────────────────────────────────
# Lectura de geometrías
# ─────────────────────────────────────────────────────────────────────────────

def _tipos_y_coordenadas(bloque: str) -> tuple[list[str], list[tuple[float, float, float]]]:
    """Tipos AutoDock y coordenadas de un bloque PDBQT, con el MISMO filtro
    de pseudo-átomos que usa el lector del producto.

    Se importa la tabla en vez de copiarla: dos listas de tipos de pegado que
    se separan sería la clase de divergencia que este piloto existe para no
    tener.
    """
    from services.chemistry.pose_physical_validity import TIPOS_PEGADO_MACROCICLO

    tipos: list[str] = []
    coordenadas: list[tuple[float, float, float]] = []
    for linea in bloque.splitlines():
        if not linea.startswith(("ATOM", "HETATM")):
            continue
        try:
            punto = (float(linea[30:38]), float(linea[38:46]), float(linea[46:54]))
        except (ValueError, IndexError):
            continue
        tipo = linea[76:78].strip()
        if tipo in TIPOS_PEGADO_MACROCICLO:
            continue
        tipos.append(tipo)
        coordenadas.append(punto)
    return tipos, coordenadas


def _coordenadas_de_sdf(texto: str) -> list[tuple[str, float, float, float]]:
    """Átomos de un molblock V2000, sin sanear: se compara lo escrito."""
    lineas = texto.splitlines()
    if len(lineas) < 4 or "V2000" not in lineas[3]:
        return []
    try:
        cuantos = int(lineas[3][0:3])
    except ValueError:
        return []
    atomos = []
    for linea in lineas[4:4 + cuantos]:
        try:
            atomos.append((linea[31:34].strip(), float(linea[0:10]),
                           float(linea[10:20]), float(linea[20:30])))
        except (ValueError, IndexError):
            return []
    return atomos


def _rmsd(a: list[tuple[float, float, float]],
          b: list[tuple[float, float, float]]) -> float | None:
    """RMSD en sitio, sin realinear. None si no hay correspondencia 1:1.

    No se superponen las geometrías a propósito: dos poses dentro del mismo
    receptor ocupan el espacio que ocupan, y alinearlas borraría justamente la
    diferencia que interesa. Para las conformaciones de ENTRADA la lectura es
    otra —son geometrías libres— y se dice al informarlas.
    """
    if not a or len(a) != len(b):
        return None
    total = sum((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 + (p[2] - q[2]) ** 2
                for p, q in zip(a, b))
    return math.sqrt(total / len(a))


def _resumen(valores: list[float]) -> dict:
    if not valores:
        return {"n": 0}
    ordenados = sorted(valores)
    n = len(ordenados)
    return {
        "n": n,
        "min": round(ordenados[0], 3),
        "mediana": round(ordenados[n // 2], 3),
        "max": round(ordenados[-1], 3),
        "media": round(sum(ordenados) / n, 3),
    }


# ─────────────────────────────────────────────────────────────────────────────

async def _un_ligando(ligando: dict, receptor_bytes: bytes, k: int) -> dict:
    from chem.conformer_ensemble import generate_conformer_ensemble
    from services.docking.ensemble import run_ensemble_docking
    from services.docking.pose_recovery import (
        PoseNoRecuperable,
        recuperar_pose_agrupada,
    )
    from services.docking.vina_service import run_vina_docking
    from utils.local_storage import read_text
    from utils.file_handlers import StoragePath

    fila: dict = {"nombre": ligando["nombre"], "smiles": ligando["smiles"],
                  "macrociclo": ligando["macrociclo"], "k_pedido": k}
    t0 = time.time()

    # ── 1. La piscina de entrada ────────────────────────────────────
    ensemble = await generate_conformer_ensemble(ligando["smiles"], k)
    conformeros = ensemble.get("conformers") or []
    fila["k_generado"] = len(conformeros)
    fila["conformer_warnings"] = ensemble.get("conformer_warnings") or []

    hashes = [c.get("conformer_sha256") for c in conformeros]
    fila["sha256_por_conformacion"] = {
        "declarados": sum(1 for h in hashes if h),
        "distintos": len({h for h in hashes if h}),
        "todos_distintos": (len({h for h in hashes if h}) == len(conformeros)
                            and all(hashes)),
    }

    # RMSD entre las conformaciones de entrada: ¿hay diversidad ANTES de Vina?
    geometrias: dict[int, list[tuple[float, float, float]]] = {}
    for conformero in conformeros:
        try:
            texto = await read_text(
                StoragePath.ligand_conformer(conformero["smiles_hash"]))
        except Exception:                                          # noqa: BLE001
            continue
        atomos = _coordenadas_de_sdf(texto)
        pesados = [(x, y, z) for elemento, x, y, z in atomos if elemento != "H"]
        if pesados:
            geometrias[int(conformero.get("indice", 0))] = pesados

    entradas = [
        v for v in (
            _rmsd(geometrias[i], geometrias[j])
            for i, j in itertools.combinations(sorted(geometrias), 2)
        ) if v is not None
    ]
    fila["rmsd_entre_conformaciones_de_entrada"] = _resumen(entradas)
    fila["nota_rmsd_entrada"] = (
        "Geometrías libres sin superponer: incluye traslación y rotación, así "
        "que es una cota superior de la diferencia conformacional, no la "
        "diferencia conformacional."
    )

    # ── 2. La corrida real ──────────────────────────────────────────
    async def _dock_una(smiles_hash: str, smiles: str | None = None):
        return await run_vina_docking(
            smiles_hash=smiles_hash,
            target_pdb_id="5TUN",
            target_chain="A",
            target_center=CENTRO,
            target_size=TAMANO,
            exhaustiveness=EXHAUSTIVIDAD,
            num_poses=NUM_POSES,
            seed=SEMILLA,
            smiles=smiles,
            prepared_receptor_bytes=receptor_bytes,
        )

    resultado = await run_ensemble_docking(
        smiles=ligando["smiles"],
        conformeros=conformeros,
        num_poses=NUM_POSES,
        dock_una=_dock_una,
    )
    poses = resultado.poses or []
    fila["poses_entregadas"] = len(poses)
    fila["segundos"] = round(time.time() - t0, 1)

    # ── 3. Procedencia: el hash, no la etiqueta ─────────────────────
    indices = [p.conformer_index for p in poses]
    procedencias = [
        ((p.source_provenance or {}).get("ligand_input") or {}).get("conformer_sha256")
        for p in poses
    ]
    esperado = {int(c.get("indice", 0)): c.get("conformer_sha256") for c in conformeros}
    coinciden = sum(
        1 for indice, sha in zip(indices, procedencias)
        if indice is not None and sha and esperado.get(indice) == sha
    )
    fila["procedencia_de_las_poses"] = {
        "con_conformer_index": sum(1 for i in indices if i is not None),
        "con_conformer_sha256": sum(1 for s in procedencias if s),
        "sha_coincide_con_el_generador": coinciden,
        "conformaciones_representadas": len({i for i in indices if i is not None}),
        "sha_distintos_entregados": len({s for s in procedencias if s}),
    }

    # ── 4. RMSD dentro de la piscina entregada ──────────────────────
    lecturas: dict[int, tuple[list[str], list[tuple[float, float, float]]]] = {}
    for posicion, pose in enumerate(poses):
        if not pose.pdbqt_block:
            continue
        lecturas[posicion] = _tipos_y_coordenadas(pose.pdbqt_block)

    mismos_atomos = len({tuple(t) for t, _ in lecturas.values()}) <= 1
    fila["orden_atomico_estable_entre_conformaciones"] = mismos_atomos
    entre_conformaciones: list[float] = []
    if mismos_atomos:
        for a, b in itertools.combinations(sorted(lecturas), 2):
            if indices[a] == indices[b]:
                continue
            valor = _rmsd(lecturas[a][1], lecturas[b][1])
            if valor is not None:
                entre_conformaciones.append(valor)
    fila["rmsd_entre_poses_de_conformaciones_distintas"] = _resumen(entre_conformaciones)
    if not mismos_atomos:
        fila["rmsd_omitido_porque"] = (
            "El orden atómico del PDBQT no es el mismo entre conformaciones, "
            "así que un RMSD por índice compararía átomos distintos. Se informa "
            "el hecho en vez de un número sin correspondencia."
        )

    # ── 5. Las seis puertas sobre artefactos reales ─────────────────
    recuperadas, fallos = 0, []
    for pose in poses:
        try:
            await recuperar_pose_agrupada(pose)
            recuperadas += 1
        except PoseNoRecuperable as exc:
            fallos.append(str(exc)[:220])
        except Exception as exc:                                   # noqa: BLE001
            fallos.append(f"{type(exc).__name__}: {str(exc)[:200]}")
    fila["pose_recovery"] = {
        "poses": len(poses),
        "recuperadas": recuperadas,
        "fallos": fallos[:5],
    }

    fila["afinidades"] = [round(float(p.affinity), 3) for p in poses]
    fila["nota_afinidad"] = (
        "No significan nada: estos ligandos no son los nativos de 5TUN. Se "
        "registran porque el orden de la piscina se decide con ellas."
    )
    return fila


async def _main(args) -> int:
    destino = Path(args.salida)
    destino.mkdir(parents=True, exist_ok=True)
    jsonl = destino / "per_complex.jsonl"

    if jsonl.exists() and jsonl.stat().st_size > 0 and not args.reanudar:
        print(f"Ya hay resultados en {jsonl}. Usa --reanudar o escribe en otro "
              f"directorio: reusar el de salida ya destruyó 102 resultados de "
              f"RS-03-PARAM-B.", file=sys.stderr)
        return 2

    if not RECEPTOR.exists():
        print(f"Falta el receptor preparado: {RECEPTOR}", file=sys.stderr)
        return 2
    receptor_bytes = RECEPTOR.read_bytes()

    hechos: set[str] = set()
    if args.reanudar and jsonl.exists():
        for linea in jsonl.read_text(encoding="utf-8").splitlines():
            if linea.strip():
                hechos.add(json.loads(linea)["nombre"])
        print(f"Reanudando: {len(hechos)} ligandos ya registrados.")

    from services.docking.vina_service import _resolve_executable          # noqa: PLC2701
    from core.config import get_settings

    settings = get_settings()

    entorno = {
        "experimento": "ENS-PILOT-01",
        "interprete": f"{Path(sys.executable).name} {platform.python_version()}",
        "es_el_runtime_distribuido": "python-embed" in str(sys.executable).replace("\\", "/"),
        "vina": _resolve_executable(settings.vina_executable_path),
        "vina_sha256": hashlib.sha256(
            Path(_resolve_executable(settings.vina_executable_path)).read_bytes()
        ).hexdigest() if _resolve_executable(settings.vina_executable_path) else None,
        "vina_cpu": int(settings.vina_cpu),
        "receptor_sha256": hashlib.sha256(receptor_bytes).hexdigest(),
        "receptor_origen": str(RECEPTOR.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "k": args.k, "num_poses": NUM_POSES, "semilla": SEMILLA,
        "exhaustividad": EXHAUSTIVIDAD,
        "centro": list(CENTRO), "tamano": list(TAMANO),
        "plataforma": platform.platform(),
        "inicio_utc": datetime.now(UTC).isoformat(),
        "ligandos_quemados": [l["nombre"] for l in LIGANDOS],
        "advertencia": ("No es un redocking: los ligandos no son los nativos de "
                        "5TUN. Ninguna afinidad de aquí es interpretable."),
    }
    (destino / "entorno.json").write_text(
        json.dumps(entorno, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(entorno, ensure_ascii=False, indent=2), flush=True)

    seleccion = [l for l in LIGANDOS if not args.solo or l["nombre"] in args.solo]
    with jsonl.open("a", encoding="utf-8") as registro:
        for numero, ligando in enumerate(seleccion, start=1):
            if ligando["nombre"] in hechos:
                continue
            print(f"\n[{numero}/{len(seleccion)}] {ligando['nombre']} "
                  f"(K={args.k}, exh={EXHAUSTIVIDAD})", flush=True)
            try:
                fila = await _un_ligando(ligando, receptor_bytes, args.k)
            except Exception as exc:                               # noqa: BLE001
                fila = {"nombre": ligando["nombre"], "error": f"{type(exc).__name__}: {exc}"}
                print(f"    FALLÓ: {fila['error']}", flush=True)
            registro.write(json.dumps(fila, ensure_ascii=False, sort_keys=True) + "\n")
            registro.flush()
            if "error" not in fila:
                p = fila["procedencia_de_las_poses"]
                print(f"    {fila['k_generado']} conformaciones, "
                      f"{fila['sha256_por_conformacion']['distintos']} hashes distintos; "
                      f"{fila['poses_entregadas']} poses de "
                      f"{p['conformaciones_representadas']} conformaciones; "
                      f"RMSD intra-piscina mediana "
                      f"{fila['rmsd_entre_poses_de_conformaciones_distintas'].get('mediana')} Å; "
                      f"recuperadas {fila['pose_recovery']['recuperadas']}/"
                      f"{fila['pose_recovery']['poses']}; {fila['segundos']}s",
                      flush=True)

    filas = [json.loads(l) for l in jsonl.read_text(encoding="utf-8").splitlines()
             if l.strip()]
    buenas = [f for f in filas if "error" not in f]
    metricas = {
        **entorno,
        "fin_utc": datetime.now(UTC).isoformat(),
        "ligandos": len(filas),
        "ligandos_sin_error": len(buenas),
        "todos_los_sha_de_entrada_distintos": all(
            f["sha256_por_conformacion"]["todos_distintos"] for f in buenas),
        "poses_con_sha_que_coincide": sum(
            f["procedencia_de_las_poses"]["sha_coincide_con_el_generador"] for f in buenas),
        "poses_entregadas": sum(f["poses_entregadas"] for f in buenas),
        "poses_recuperadas": sum(f["pose_recovery"]["recuperadas"] for f in buenas),
        "conformaciones_representadas_mediana": (
            sorted(f["procedencia_de_las_poses"]["conformaciones_representadas"]
                   for f in buenas)[len(buenas) // 2] if buenas else None),
        "rmsd_intra_piscina_mediana_por_ligando": {
            f["nombre"]: f["rmsd_entre_poses_de_conformaciones_distintas"].get("mediana")
            for f in buenas},
        "lectura": {
            "demuestra": ("Que cada conformación entra a Vina con SU geometría y "
                          "que la pose entregada puede demostrar de cuál vino."),
            "no_demuestra": ("Ninguna ventaja del ensemble. Eso es ENS-PROD-01, "
                             "con prerregistro, cohorte y 248 complejos."),
        },
    }
    (destino / "metrics.json").write_text(
        json.dumps(metricas, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("\n== Resumen ==")
    print(f"ligandos sin error           {metricas['ligandos_sin_error']}/{metricas['ligandos']}")
    print(f"sha de entrada todos distintos  {metricas['todos_los_sha_de_entrada_distintos']}")
    print(f"poses con sha que coincide   {metricas['poses_con_sha_que_coincide']}/{metricas['poses_entregadas']}")
    print(f"poses recuperadas (6 puertas) {metricas['poses_recuperadas']}/{metricas['poses_entregadas']}")
    print(f"conformaciones en el top-{NUM_POSES} (mediana) {metricas['conformaciones_representadas_mediana']}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--salida",
                    default=str(PROJECT_ROOT / "scripts/artifacts_science/ENS-PILOT-01"))
    ap.add_argument("--k", type=int, default=K)
    ap.add_argument("--solo", nargs="*", default=None,
                    help="nombres de ligando a correr (por defecto, los diez)")
    ap.add_argument("--reanudar", action="store_true")
    args = ap.parse_args()

    # Un directorio de datos propio, antes de que nada importe `settings`.
    # Dos razones: la corrida no ensucia los datos reales del usuario, y el
    # artefacto queda autocontenido —conformaciones, PDBQT y archivos de poses
    # viven junto a sus métricas—. Un artefacto por corrida, nunca reusando el
    # directorio de salida.
    os.environ.setdefault("LOCAL_DATA_DIR", str(Path(args.salida) / "_work" / "data"))
    return asyncio.run(_main(args))


if __name__ == "__main__":
    raise SystemExit(main())
