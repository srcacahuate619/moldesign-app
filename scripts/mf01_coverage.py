"""MF-01 — Tabla de cobertura por fuente y flexibilidad sobre train/val.

Entregable 3 de la primera tanda de docs/49 (sección 15): caracterizar las
poses EXISTENTES de Ruta C (data/pose_selector_dataset, sellado) en
train+val = 156 complejos / 3469 poses. Por cada complejo se calcula:

  - número de poses por fuente (molflex / flexible_redock / ruta_a),
  - oráculo por fuente: mínimo RMSD pocket-frame de las poses de esa fuente,
  - oráculo de la unión: mínimo RMSD global del complejo,
  - rot_bonds del ligando cristalográfico (data/pdbbind/{pid}/{pid}_ligand.sdf),
  - flag oracle_covered = (min RMSD <= 2.0 Å), definición canónica de
    docs/49 §5 ("cobertura/oráculo min RMSD <=2 Å", RMSD pocket-frame sin
    alineamiento rígido).

El sidecar sellado de FND-06 (poses_provenance.jsonl, clave
pid|source|file_stem) se usa para completar metadatos por corrida (seed,
exhaustiveness, num_modes, box) y se resume en metrics.json.

ANÁLISIS READ-ONLY: no re-docking, no scoring v0.6, no unión deduplicada
(eso es MF-11 / RS-01, fases posteriores). El dataset sellado no se toca.

Salidas (scripts/artifacts_science/MF-01/):
  - metrics.json      tablas de cobertura por fuente y por estrato,
                      desglose train/val y distribución de poses.
  - per_complex.jsonl un registro por complejo (156, ordenados por pid).
  - failures.jsonl    anomalías detectadas (poses sin provenance, SDF sin
                      parsear, ...); vacío si todo cuadra.

Determinista: sin marcas de tiempo, claves ordenadas, agregación canónica.
Dos corridas sobre los mismos insumos producen bytes idénticos.

Uso:
    python scripts/mf01_coverage.py [--out-dir scripts/artifacts_science/MF-01]
"""

import argparse
import json
import os
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

from rdkit import Chem, RDLogger
from rdkit.Chem import Descriptors

RDLogger.logger().setLevel(RDLogger.ERROR)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATASET_DIR = PROJECT_ROOT / "data" / "pose_selector_dataset"
PDBBIND_DIR = PROJECT_ROOT / "data" / "pdbbind"
PROVENANCE_PATH = (
    PROJECT_ROOT
    / "scripts"
    / "artifacts_science"
    / "FND-06"
    / "poses_provenance.jsonl"
)
OUT_DIR_DEFAULT = PROJECT_ROOT / "scripts" / "artifacts_science" / "MF-01"

FUENTES_CANONICAS = ["flexible_redock", "molflex", "ruta_a"]
SPLITS = ["train", "val"]
UMBRAL_ORACULO = 2.0  # Å, definición canónica docs/49 §5
ESTRATOS_CANONICOS = ["0-4", "5-9", "10-14", ">=15", "unknown"]

CLAVES_COMPLEJO = [
    "pid",
    "split",
    "rot_bonds",
    "n_poses",
    "min_rmsd",
    "min_rmsd_union",
    "oracle_covered",
]


def _atomic_write(path: Path, texto: str) -> None:
    """Escritura atómica (temp + os.replace), igual que la convención FND-06."""
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(texto)
    os.replace(tmp, path)


def _leer_poses(split: str) -> tuple[dict[str, list[dict]], list[dict]]:
    """Lee poses_{split}.jsonl y agrupa por pid.

    Devuelve (por_pid, fallas): poses sin `rmsd` válido o con pid ausente se
    reportan como falla y NO se agregan (nunca se inventa un RMSD).
    """
    path = DATASET_DIR / f"poses_{split}.jsonl"
    por_pid: dict[str, list[dict]] = defaultdict(list)
    fallas: list[dict] = []
    with open(path, encoding="utf-8") as fh:
        for linea in fh:
            linea = linea.strip()
            if not linea:
                continue
            try:
                p = json.loads(linea)
            except json.JSONDecodeError as exc:
                fallas.append({"pid": "?", "tipo": "json_invalido", "detalle": str(exc)})
                continue
            pid = p.get("pid")
            if not pid:
                fallas.append({"pid": "?", "tipo": "sin_pid", "detalle": linea[:120]})
                continue
            rmsd = p.get("rmsd")
            if rmsd is None or not isinstance(rmsd, (int, float)):
                fallas.append({"pid": pid, "tipo": "sin_rmsd", "detalle": str(p.get("file_stem"))})
                continue
            por_pid[pid].append(p)
    return por_pid, fallas


def _cargar_provenance() -> dict[tuple[str, str, str], dict]:
    """Sidecar FND-06 indexado por (pid, source, file_stem)."""
    sidecar: dict[tuple[str, str, str], dict] = {}
    with open(PROVENANCE_PATH, encoding="utf-8") as fh:
        for linea in fh:
            linea = linea.strip()
            if not linea:
                continue
            r = json.loads(linea)
            sidecar[(r["pid"], r["source"], r["file_stem"])] = r
    return sidecar


def _rot_bonds(pid: str) -> int | str:
    """Enlaces rotables del ligando cristalográfico.

    Convención de Ruta C (ruta_a_exh_validation.py): leer
    data/pdbbind/{pid}/{pid}_ligand.sdf, sanitizado y con fallback sin
    sanitizar (mf.leer_ligando), luego
    Descriptors.NumRotatableBonds(AddHs(mol)). Si el SDF no parsea o falta,
    devuelve "unknown" (honesto, nunca inventado).
    """
    sdf = PDBBIND_DIR / pid / f"{pid}_ligand.sdf"
    if not sdf.is_file():
        return "unknown"
    mol = None
    try:
        mol = Chem.MolFromMolFile(str(sdf))
    except Exception:
        mol = None
    if mol is None:
        try:
            mol = Chem.MolFromMolFile(str(sdf), sanitize=False, removeHs=False)
        except Exception:
            mol = None
    if mol is None:
        return "unknown"
    try:
        return int(Descriptors.NumRotatableBonds(Chem.AddHs(mol)))
    except Exception:
        return "unknown"


def _estrato(rot_bonds: int | str) -> str:
    """Estrato de flexibilidad canónico (docs/49: rotatable_bonds)."""
    if rot_bonds == "unknown":
        return "unknown"
    if rot_bonds <= 4:
        return "0-4"
    if rot_bonds <= 9:
        return "5-9"
    if rot_bonds <= 14:
        return "10-14"
    return ">=15"


def _median(values: list[float]) -> float | None:
    """Mediana (stdlib statistics) o None si no hay valores."""
    if not values:
        return None
    return float(statistics.median(values))


def _celda_fuente(
    registros: list[dict], fuente: str, denominador: int
) -> dict:
    """Celda de cobertura de una fuente sobre un subconjunto de complejos."""
    con_poses = [r for r in registros if r["n_poses"].get(fuente, 0) > 0]
    cubiertos = [r for r in con_poses if r["min_rmsd"].get(fuente) is not None
                 and r["min_rmsd"][fuente] <= UMBRAL_ORACULO]
    min_rmsds = [r["min_rmsd"][fuente] for r in con_poses]
    return {
        "n_poses": sum(r["n_poses"].get(fuente, 0) for r in registros),
        "n_complejos_con_poses": len(con_poses),
        "n_complejos_cubiertos": len(cubiertos),
        "pct_sobre_total": round(100.0 * len(cubiertos) / denominador, 1),
        "pct_sobre_con_poses": (
            round(100.0 * len(cubiertos) / len(con_poses), 1)
            if con_poses
            else None
        ),
        "mediana_min_rmsd": (
            round(_median(min_rmsds), 3) if min_rmsds else None
        ),
    }


def _celda_union(registros: list[dict], denominador: int) -> dict:
    """Celda de cobertura de la unión (todas las fuentes) sobre un subconjunto."""
    con_poses = [r for r in registros if r["min_rmsd_union"] is not None]
    cubiertos = [r for r in con_poses if r["min_rmsd_union"] <= UMBRAL_ORACULO]
    min_rmsds = [r["min_rmsd_union"] for r in con_poses]
    return {
        "n_poses": sum(sum(r["n_poses"].values()) for r in registros),
        "n_complejos_con_poses": len(con_poses),
        "n_complejos_cubiertos": len(cubiertos),
        "pct_sobre_total": round(100.0 * len(cubiertos) / denominador, 1),
        "pct_sobre_con_poses": (
            round(100.0 * len(cubiertos) / len(con_poses), 1)
            if con_poses
            else None
        ),
        "mediana_min_rmsd": (
            round(_median(min_rmsds), 3) if min_rmsds else None
        ),
    }


def _construir_complejos(
    poses_por_split: dict[str, dict[str, list[dict]]],
) -> tuple[list[dict], list[dict]]:
    """Agrega poses por complejo (pid x split) con oráculos por fuente/unión."""
    pids = set(poses_por_split["train"]) & set(poses_por_split["val"])
    fallas: list[dict] = [
        {"pid": pid, "tipo": "pid_en_ambos_splits", "detalle": "leakage de split"}
        for pid in sorted(pids)
    ]
    registros: list[dict] = []
    for split in SPLITS:
        for pid in sorted(poses_por_split[split]):
            if pid in pids:
                continue
            rot_bonds = _rot_bonds(pid)
            rec = {
                "pid": pid,
                "split": split,
                "rot_bonds": rot_bonds,
                "n_poses": {f: 0 for f in FUENTES_CANONICAS},
                "min_rmsd": {f: None for f in FUENTES_CANONICAS},
                "min_rmsd_union": None,
                "oracle_covered": False,
            }
            for p in poses_por_split[split][pid]:
                fuente = p["source"]
                if fuente not in rec["n_poses"]:
                    rec["n_poses"][fuente] = 0
                    rec["min_rmsd"][fuente] = None
                rec["n_poses"][fuente] += 1
                rmsd = float(p["rmsd"])
                actual = rec["min_rmsd"][fuente]
                if actual is None or rmsd < actual:
                    rec["min_rmsd"][fuente] = rmsd
                if rec["min_rmsd_union"] is None or rmsd < rec["min_rmsd_union"]:
                    rec["min_rmsd_union"] = rmsd
            rec["oracle_covered"] = rec["min_rmsd_union"] <= UMBRAL_ORACULO
            registros.append(rec)
    registros.sort(key=lambda r: r["pid"])
    return registros, fallas


def _fuentes_presentes(registros: list[dict]) -> list[str]:
    """Fuentes canónicas presentes + cualquier fuente extra (orden estable)."""
    presentes = set()
    for r in registros:
        presentes.update(f for f, n in r["n_poses"].items() if n > 0)
    return sorted(set(FUENTES_CANONICAS) | presentes)


def _metadata_provenance(
    registros: list[dict],
    poses_por_split: dict[str, dict[str, list[dict]]],
    sidecar: dict[tuple[str, str, str], dict],
) -> tuple[dict, list[dict]]:
    """Resumen de metadatos por corrida (sidecar FND-06) y fallas de join."""
    meta = {
        f: {
            "n_runs": 0,
            "n_poses_con_provenance": 0,
            "n_poses_sin_provenance": 0,
            "seed": {},
            "exhaustiveness": {},
            "num_modes": {},
            "box_method": {},
        }
        for f in FUENTES_CANONICAS
    }
    fallas: list[dict] = []
    runs_vistos: set[tuple[str, str, str]] = set()
    for split in SPLITS:
        for pid, poses in poses_por_split[split].items():
            if pid in (set(poses_por_split["train"]) & set(poses_por_split["val"])):
                continue
            for p in poses:
                fuente = p["source"]
                if fuente not in meta:
                    meta[fuente] = {
                        "n_runs": 0,
                        "n_poses_con_provenance": 0,
                        "n_poses_sin_provenance": 0,
                        "seed": {},
                        "exhaustiveness": {},
                        "num_modes": {},
                        "box_method": {},
                    }
                clave = (pid, fuente, p["file_stem"])
                rec = sidecar.get(clave)
                if rec is None:
                    meta[fuente]["n_poses_sin_provenance"] += 1
                    fallas.append(
                        {
                            "pid": pid,
                            "tipo": "sin_provenance",
                            "detalle": f"{fuente}|{p['file_stem']}",
                        }
                    )
                    continue
                meta[fuente]["n_poses_con_provenance"] += 1
                if clave not in runs_vistos:
                    runs_vistos.add(clave)
                    meta[fuente]["n_runs"] += 1
                    for campo in ("seed", "exhaustiveness", "num_modes"):
                        valor = rec.get(campo)
                        clave_ser = str(valor)
                        meta[fuente][campo][clave_ser] = (
                            meta[fuente][campo].get(clave_ser, 0) + 1
                        )
                    box = rec.get("box") or {}
                    metodo = box.get("method", "unknown")
                    meta[fuente]["box_method"][metodo] = (
                        meta[fuente]["box_method"].get(metodo, 0) + 1
                    )
    for fuente in meta:
        for campo in ("seed", "exhaustiveness", "num_modes", "box_method"):
            meta[fuente][campo] = dict(
                sorted(meta[fuente][campo].items(), key=lambda kv: str(kv[0]))
            )
    return meta, fallas


def _tabular_estratos(
    registros: list[dict], fuentes: list[str]
) -> tuple[dict, dict]:
    """Cobertura por estrato de flexibilidad + distribución de poses."""
    por_estrato: dict[str, list[dict]] = defaultdict(list)
    for r in registros:
        por_estrato[_estrato(r["rot_bonds"])].append(r)

    cobertura: dict[str, dict] = {}
    distribucion: dict[str, dict] = {}
    for estrato in ESTRATOS_CANONICOS:
        sub = por_estrato.get(estrato, [])
        if not sub:
            continue
        n_estrato = len(sub)
        por_fuente = {
            f: _celda_estrato(sub, f, n_estrato) for f in fuentes
        }
        cobertura[estrato] = {
            "n_complejos": n_estrato,
            "por_fuente": por_fuente,
            "union": _celda_union_estrato(sub, n_estrato),
        }
        distribucion[estrato] = {
            f: sum(r["n_poses"].get(f, 0) for r in sub) for f in fuentes
        }
    return cobertura, distribucion


def _celda_estrato(registros: list[dict], fuente: str, n_estrato: int) -> dict:
    """Celda de cobertura de una fuente DENTRO de un estrato."""
    con_poses = [r for r in registros if r["n_poses"].get(fuente, 0) > 0]
    cubiertos = [r for r in con_poses if r["min_rmsd"].get(fuente) is not None
                 and r["min_rmsd"][fuente] <= UMBRAL_ORACULO]
    min_rmsds = [r["min_rmsd"][fuente] for r in con_poses]
    return {
        "n_poses": sum(r["n_poses"].get(fuente, 0) for r in registros),
        "n_complejos_con_poses": len(con_poses),
        "n_complejos_cubiertos": len(cubiertos),
        "pct_sobre_estrato": (
            round(100.0 * len(cubiertos) / n_estrato, 1) if n_estrato else None
        ),
        "mediana_min_rmsd": (
            round(_median(min_rmsds), 3) if min_rmsds else None
        ),
    }


def _celda_union_estrato(registros: list[dict], n_estrato: int) -> dict:
    """Celda de cobertura de la unión DENTRO de un estrato."""
    con_poses = [r for r in registros if r["min_rmsd_union"] is not None]
    cubiertos = [r for r in con_poses if r["min_rmsd_union"] <= UMBRAL_ORACULO]
    min_rmsds = [r["min_rmsd_union"] for r in con_poses]
    return {
        "n_poses": sum(sum(r["n_poses"].values()) for r in registros),
        "n_complejos_con_poses": len(con_poses),
        "n_complejos_cubiertos": len(cubiertos),
        "pct_sobre_estrato": (
            round(100.0 * len(cubiertos) / n_estrato, 1) if n_estrato else None
        ),
        "mediana_min_rmsd": (
            round(_median(min_rmsds), 3) if min_rmsds else None
        ),
    }


def _registro_complejo_a_linea(rec: dict) -> dict:
    """Proyección canónica del registro por complejo (orden de claves fijo)."""
    return {k: rec[k] for k in CLAVES_COMPLEJO}


def main(argv: list[str] | None = None) -> int:
    """Orquesta el análisis completo y escribe los tres artefactos."""
    parser = argparse.ArgumentParser(
        description="MF-01: tabla de cobertura por fuente y flexibilidad "
        "(análisis read-only sobre poses existentes)."
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=OUT_DIR_DEFAULT,
        help="directorio de salida (default: scripts/artifacts_science/MF-01)",
    )
    args = parser.parse_args(argv)

    poses_por_split: dict[str, dict[str, list[dict]]] = {}
    fallas: list[dict] = []
    for split in SPLITS:
        por_pid, fallas_split = _leer_poses(split)
        poses_por_split[split] = por_pid
        fallas.extend(fallas_split)

    sidecar = _cargar_provenance()
    registros, fallas_complejos = _construir_complejos(poses_por_split)
    fallas.extend(fallas_complejos)
    metadata, fallas_prov = _metadata_provenance(
        registros, poses_por_split, sidecar
    )
    fallas.extend(fallas_prov)

    fuentes = _fuentes_presentes(registros)

    n_por_split = {s: len(set(poses_por_split[s])) for s in SPLITS}
    registros_split = {s: [r for r in registros if r["split"] == s] for s in SPLITS}

    cobertura_por_fuente: dict[str, dict] = {}
    for clave, sub, denominador in [
        ("train_val", registros, len(registros)),
        ("train", registros_split["train"], n_por_split["train"]),
        ("val", registros_split["val"], n_por_split["val"]),
    ]:
        cobertura_por_fuente[clave] = {
            f: _celda_fuente(sub, f, denominador) for f in fuentes
        }
        cobertura_por_fuente[clave]["union"] = _celda_union(sub, denominador)

    cobertura_estrato, distribucion_estrato = _tabular_estratos(
        registros, fuentes
    )

    n_poses = {s: sum(len(v) for v in poses_por_split[s].values()) for s in SPLITS}
    n_poses_total = sum(n_poses.values())
    n_con_provenance = sum(
        m["n_poses_con_provenance"] for m in metadata.values()
    )
    n_sin_provenance = n_poses_total - n_con_provenance

    metrics = {
        "experiment_id": "MF-01",
        "alcance": {
            "splits": "train+val (poses EXISTENTES; test histórico fuera de alcance)",
            "n_complejos": len(registros),
            "n_poses": n_poses_total,
            "por_split": {
                s: {"n_complejos": n_por_split[s], "n_poses": n_poses[s]}
                for s in SPLITS
            },
        },
        "definiciones": {
            "oraculo": (
                f"min RMSD pocket-frame <= {UMBRAL_ORACULO} A por complejo "
                "(docs/49 §5: cobertura/oráculo; sin alineamiento rígido)"
            ),
            "min_rmsd_por_fuente": (
                "mínimo del campo rmsd (pocket-frame) entre las poses de esa "
                "fuente dentro del complejo"
            ),
            "min_rmsd_union": (
                "mínimo del campo rmsd entre TODAS las poses del complejo "
                "(oráculo de la unión pre-deduplicación)"
            ),
            "oracle_covered": "min_rmsd_union <= 2.0 A",
            "mediana_min_rmsd": (
                "mediana de los min-RMSD sobre los complejos CON poses de la "
                "fuente (denominador condicional)"
            ),
            "pct_sobre_total": (
                "n complejos cubiertos / total del subconjunto (156, 116 o 40)"
            ),
            "pct_sobre_estrato": "n complejos cubiertos / n del estrato",
            "rot_bonds": (
                "Descriptors.NumRotatableBonds(AddHs(mol)) del SDF "
                "cristalográfico (convención ruta_a_exh_validation.py); "
                "'unknown' si el SDF no parsea"
            ),
            "estratos": "0-4 / 5-9 / 10-14 / >=15 rot_bonds",
        },
        "cobertura_por_fuente": cobertura_por_fuente,
        "cobertura_por_estrato": cobertura_estrato,
        "distribucion_poses_por_fuente_estrato": distribucion_estrato,
        "provenance_por_fuente": {
            "sidecar": "scripts/artifacts_science/FND-06/poses_provenance.jsonl",
            "n_poses_con_provenance": n_con_provenance,
            "n_poses_sin_provenance": n_sin_provenance,
            "por_fuente": metadata,
        },
        "notas": [
            "Determinista: dos corridas sobre los mismos insumos producen "
            "bytes idénticos (sin marcas de tiempo).",
            "Análisis read-only: no re-docking, no scoring v0.6, no unión "
            "deduplicada (MF-11/RS-01 posteriores).",
            "La cobertura de la unión aquí es PRE-deduplicación: cada pose "
            "cuenta una vez aunque dos fuentes generen la misma pose.",
        ],
    }

    args.out_dir.mkdir(parents=True, exist_ok=True)
    _atomic_write(
        args.out_dir / "metrics.json",
        json.dumps(metrics, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    lineas = "\n".join(
        json.dumps(_registro_complejo_a_linea(r), ensure_ascii=False)
        for r in registros
    ) + "\n"
    _atomic_write(args.out_dir / "per_complex.jsonl", lineas)

    fallas_unicas: dict[tuple, dict] = {}
    for f in fallas:
        clave = (f["pid"], f["tipo"], f["detalle"])
        fallas_unicas[clave] = f
    lineas_fallas = "\n".join(
        json.dumps(f, ensure_ascii=False, sort_keys=True)
        for f in sorted(
            fallas_unicas.values(),
            key=lambda f: (f["pid"], f["tipo"], f["detalle"]),
        )
    ) + "\n"
    _atomic_write(args.out_dir / "failures.jsonl", lineas_fallas)

    print(f"MF-01: {len(registros)} complejos, {n_poses_total} poses "
          f"({n_por_split['train']} train / {n_por_split['val']} val)")
    union = cobertura_por_fuente["train_val"]["union"]
    print(f"oráculo unión train+val: {union['n_complejos_cubiertos']}/"
          f"{len(registros)} ({union['pct_sobre_total']}%), "
          f"mediana min-RMSD {union['mediana_min_rmsd']} A")
    for f in fuentes:
        celda = cobertura_por_fuente["train_val"][f]
        print(f"  {f}: {celda['n_complejos_cubiertos']}/{len(registros)} "
              f"({celda['pct_sobre_total']}%), poses={celda['n_poses']}, "
              f"mediana min-RMSD {celda['mediana_min_rmsd']} A")
    print(f"provenance: {n_con_provenance}/{n_poses_total} poses con sidecar "
          f"({n_sin_provenance} sin)")
    print(f"artefactos: {args.out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
