# -*- coding: utf-8 -*-
"""
backfill_pose_provenance.py — Sidecar de provenance de las 4300 poses
históricas del dataset pose-selector (FND-06).

Genera `poses_provenance.jsonl` (un registro por corrida, clave
"pid|source|file_stem") usando SOLO fuentes verificables:

  1. Dataset (solo lectura): data/pose_selector_dataset/poses_{train,val,test}.jsonl
  2. Artefactos JSON de corridas: scripts/artifacts_molflex_v3.json (n_conf por
     pid, probe de Vina 1.2.7, box/exh/num_modes), scripts/artifacts_ruta_a.json
     (cohorte, seed de selección, timeout).
  3. Convenciones de nombres documentadas en el código: file_stem `conf{cid}.out`
     → conformer_id; `exh1|exh2|exh4` → exhaustiveness; `{pid}` (flexible_redock).
  4. Parámetros hardcodeados en los scripts generadores (molflex.py,
     redock_pdbbind.py, ruta_a_exh_validation.py): seed ETKDG=42, box 25 Å,
     exh=8, num_modes=9, cadenas de preparación, timeouts.
  5. Centro de caja: derivado determinista del SDF cristalográfico con la
     misma definición de rp.find_binding_center (centroide de átomos pesados,
     parser stdlib V2000), marcado center_derived=true.

Lo irrecuperable se marca "unknown" explícito, nunca se inventa:

  - seed de flexible_redock/ruta_a: Vina se invocó SIN --seed (semilla no
    controlada; el SEED=42 de ruta_a fue solo selección de cohorte).
  - created_at de todo el histórico: no existe registro temporal determinista
    de las corridas originales.

Salida determinista: sin marcas de tiempo, orden canónico de claves, floats
Python estables. Dos corridas producen bytes idénticos.

Verificación opcional (no bloqueante): si RDKit + redock_pdbbind están
importables, se compara el centroide stdlib contra rp.find_binding_center para
todos los pids; el resultado se registra en backfill_report.json.

Uso:
  python scripts/backfill_pose_provenance.py [--out FILE] [--report-out FILE]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
import pose_provenance as pp  # noqa: E402

DATASET_DIR = PROJECT_ROOT / "data" / "pose_selector_dataset"
PDBBIND = PROJECT_ROOT / "data" / "pdbbind"
ARTIFACTS_DIR = PROJECT_ROOT / "scripts"
ARTIFACTO_MOLFLEX_V3 = ARTIFACTS_DIR / "artifacts_molflex_v3.json"
ARTIFACTO_RUTA_A = ARTIFACTS_DIR / "artifacts_ruta_a.json"
SPLITS = ("poses_train.jsonl", "poses_val.jsonl", "poses_test.jsonl")

# ───────────────────────── valores recuperados del código ──────────────────
# Cada constante documenta de qué fuente verificable sale.

BOX_SIZE = 25.0          # molflex.py:BOX_SIZE y redock_pdbbind.py size "25"
EXH_RIGIDO = 8           # molflex.py:EXHAUSTIVENESS y redock_pdbbind.py "8"
NUM_MODES = 9            # molflex.py:NUM_MODES, redock_pdbbind.py "9",
                         # ruta_a_exh_validation.py:NUM_MODES
SEED_ETKDG = 42          # molflex.py:construir_ensemble randomSeed=42
VINA_VERSION = "1.2.7"   # artifacts_molflex_v3.json:probe + vina.exe --version
MEEKO_VERSION = "0.7.1"  # redock_pdbbind.py (comentario fallback) y entorno

# Atribución de corrida por pid (artifacts_molflex_v3.json).
# e2: n_conf objetivo 30; v4: n_conf objetivo 20. 10gs aparece en ambas porque
# el workdir se reusó: conf0-18 los sobreescribió v4, conf19-28 quedaron
# "stale" de e2 (verificable por timestamps: artifacts v3 01:21 < dataset
# 14:57 del 2026-08-14, y por stems del dataset: 29 archivos en 10gs).
PIDS_E2 = {"1a4w", "1aaq", "1ajx", "184l"}
PIDS_V4 = {"186l", "187l", "188l", "1a1e", "1a28", "1a30", "1a4r", "1a99",
           "1add", "1ado", "1afk", "1afl", "1ai4"}
PID_MIXTO = "10gs"

# ───────────────────────── parser SDF V2000 (stdlib) ───────────────────────

ELEMENTOS = {
    "H": 1, "He": 2, "Li": 3, "Be": 4, "B": 5, "C": 6, "N": 7, "O": 8,
    "F": 9, "Na": 11, "Mg": 12, "Al": 13, "Si": 14, "P": 15, "S": 16,
    "Cl": 17, "K": 19, "Ca": 20, "Sc": 21, "Ti": 22, "V": 23, "Cr": 24,
    "Mn": 25, "Fe": 26, "Co": 27, "Ni": 28, "Cu": 29, "Zn": 30, "Ga": 31,
    "Ge": 32, "As": 33, "Se": 34, "Br": 35, "Rb": 37, "Sr": 38, "Y": 39,
    "Zr": 40, "Nb": 41, "Mo": 42, "Tc": 43, "Ru": 44, "Rh": 45, "Pd": 46,
    "Ag": 47, "Cd": 48, "In": 49, "Sn": 50, "Sb": 51, "Te": 52, "I": 53,
    "Cs": 55, "Ba": 56, "La": 57, "Ce": 58, "Pr": 59, "Nd": 60, "Sm": 62,
    "Eu": 63, "Gd": 64, "Tb": 65, "Dy": 66, "Ho": 67, "Er": 68, "Tm": 69,
    "Yb": 70, "Lu": 71, "Hf": 72, "Ta": 73, "W": 74, "Re": 75, "Os": 76,
    "Ir": 77, "Pt": 78, "Au": 79, "Hg": 80, "Tl": 81, "Pb": 82, "Bi": 83,
    "U": 92,
}


def centro_pesados_sdf(texto):
    """Centroide de átomos pesados (Z > 1) del primer bloque mol V2000.

    Réplica determinista de la definición de rp.find_binding_center (RDKit
    sanitize=False + numpy mean). Devuelve [x, y, z] redondeado a 3 decimales
    o None si el bloque es ilegible.

    Formato verificado empíricamente sobre los 236 SDF del dataset: la línea
    de conteos termina con "V2000" en la MISMA línea; n_átomos va en las
    columnas fijas [0:3] (algunos SDF, p. ej. 1k6p/1k6v, no separan n_átomos
    de n_enlaces con espacio).
    """
    bloque = texto.split("$$$$")[0]
    lineas = bloque.splitlines()
    idx_v = None
    for i, l in enumerate(lineas):
        if l.strip().endswith("V2000"):
            idx_v = i
            break
    if idx_v is None or idx_v < 3:
        return None
    try:
        n_atom = int(lineas[idx_v][0:3])
    except ValueError:
        return None
    coords = []
    for l in lineas[idx_v + 1: idx_v + 1 + n_atom]:
        if len(l) < 34:
            return None
        z = ELEMENTOS.get(l[31:34].strip(), 0)
        if z <= 1:
            continue
        try:
            x, y, zz = float(l[0:10]), float(l[10:20]), float(l[20:30])
        except ValueError:
            return None
        coords.append([x, y, zz])
    if not coords:
        return None
    n = len(coords)
    return [round(sum(c[i] for c in coords) / n, 3) for i in range(3)]


# ───────────────────────── fuentes de metadatos ────────────────────────────

_cache_centros: dict = {}
_cache_artifacts: dict = {}


def centro_de_pid(pid):
    """Centro de caja de un pid (derivado determinista del SDF). Cacheado."""
    if pid in _cache_centros:
        return _cache_centros[pid]
    sdf = PDBBIND / pid / f"{pid}_ligand.sdf"
    try:
        centro = centro_pesados_sdf(sdf.read_text(encoding="utf-8"))
    except Exception:
        centro = None
    _cache_centros[pid] = centro
    return centro


def cargar_artefacto(nombre):
    """Carga un artifacts JSON (cacheado)."""
    if nombre not in _cache_artifacts:
        ruta = ARTIFACTS_DIR / nombre
        if ruta.is_file():
            _cache_artifacts[nombre] = json.loads(
                ruta.read_text(encoding="utf-8"))
        else:
            _cache_artifacts[nombre] = {}
    return _cache_artifacts[nombre]


def n_conf_molflex(pid):
    """n_conf de la corrida molflex que produjo el pid (o None)."""
    v3 = cargar_artefacto("artifacts_molflex_v3.json")
    if pid == PID_MIXTO:
        e2 = v3.get("e2", {}).get("agregados", {}).get(pid, {})
        return e2.get("n_conf")
    if pid in PIDS_E2:
        e2 = v3.get("e2", {}).get("agregados", {}).get(pid, {})
        return e2.get("n_conf")
    v4 = v3.get("v4", {}).get("complejos", {}).get(pid, {})
    return v4.get("n_conf")


def run_molflex(pid):
    """Identificador de corrida molflex del pid."""
    if pid == PID_MIXTO:
        return "e2_v4_mixto"
    return "e2" if pid in PIDS_E2 else "v4"


# ───────────────────────── registros por fuente ────────────────────────────

def caja(pid):
    """Box del contrato para un pid (centro derivado del SDF)."""
    centro = centro_de_pid(pid)
    return {
        "center": centro if centro is not None else pp.DESCONOCIDO,
        "size": [BOX_SIZE, BOX_SIZE, BOX_SIZE],
        "method": "center_from_crystal_ligand",
        "center_derived": True,
    }


def prep_molflex():
    """Preparación química de la cadena MolFlex (documentada en molflex.py)."""
    return {
        "ligand": {"method": "meeko_molecule_preparation_etkdg",
                   "tool": "meeko", "version": MEEKO_VERSION},
        "receptor": {"protonation": "pdb_original",
                     "tool": "openbabel_pdb2pdbqt_rigido"},
    }


def prep_flexible():
    """Preparación de flexible_redock (redock_pdbbind.py)."""
    return {
        "ligand": {"method": "meeko_molecule_preparation_conformacion_cristal",
                   "tool": "meeko", "version": MEEKO_VERSION,
                   "fallback": "openbabel_sdf2pdbqt"},
        "receptor": {"protonation": "pdb_original",
                     "tool": "openbabel_pdb2pdbqt_rigido",
                     "fallback": "meeko_cli_mk_prepare_receptor"},
    }


def prep_ruta_a():
    """Preparación de ruta_a (ruta_a_exh_validation.py, misma cadena)."""
    return {
        "ligand": {"method": "meeko_molecule_preparation_conformacion_cristal",
                   "tool": "meeko", "version": MEEKO_VERSION},
        "receptor": {"protonation": "pdb_original",
                     "tool": "openbabel_pdb2pdbqt_rigido"},
    }


def registro_molflex(pid, stem, cid):
    """Registro de provenance de una corrida molflex (conformero cid)."""
    run = run_molflex(pid)
    if run == "e2_v4_mixto":
        exp_id = "historico_molflex_exp_v3_e2_v4_mixto"
    else:
        exp_id = f"historico_molflex_exp_v3_{run}"
    registro = pp.construir_registro(
        pid=pid, source="molflex", file_stem=stem,
        seed=SEED_ETKDG, conformer_id=cid,
        exhaustiveness=EXH_RIGIDO, num_modes=NUM_MODES,
        box=caja(pid), preparation=prep_molflex(),
        engine={"name": "vina", "version": VINA_VERSION},
        experiment_id=exp_id, created_at=pp.DESCONOCIDO,
        timeout=240, n_conf=n_conf_molflex(pid), run=run,
        recovery={
            "source": "dataset:source",
            "seed": "constante_scripts/molflex.py:randomSeed=42",
            "conformer_id": "nombre_archivo_conf{cid}.out",
            "exhaustiveness": "constante_scripts/molflex.py:EXHAUSTIVENESS",
            "num_modes": "constante_scripts/molflex.py:NUM_MODES",
            "box": "constante_scripts/molflex.py:BOX_SIZE + "
                  "center.json_derivado_del_sdf",
            "preparation": "codigo_scripts/molflex.py + "
                           "rescoring/scripts/redock_pdbbind.py",
            "engine": "artifacts_molflex_v3.json:probe",
            "experiment_id": "runner_scripts/molflex_exp_v3.py",
            "created_at": "unknown_sin_registro_temporal_determinista",
            "n_conf": "artifacts_molflex_v3.json:e2.agregados|v4.complejos",
        },
    )
    return registro


def registro_flexible(pid):
    """Registro de provenance de flexible_redock (stem = pid)."""
    return pp.construir_registro(
        pid=pid, source="flexible_redock", file_stem=pid,
        seed=pp.DESCONOCIDO, conformer_id="crystal",
        exhaustiveness=EXH_RIGIDO, num_modes=NUM_MODES,
        box=caja(pid), preparation=prep_flexible(),
        engine={"name": "vina", "version": VINA_VERSION},
        experiment_id="historico_vina_redock_exh8",
        created_at=pp.DESCONOCIDO,
        timeout=300,
        recovery={
            "source": "dataset:source",
            "seed": "unknown_vina_invocado_sin_flag_seed",
            "conformer_id": "input_conformacion_cristal_rdkit_addhs",
            "exhaustiveness": "hardcodeado_rescoring/scripts/"
                              "redock_pdbbind.py:exhaustiveness=8",
            "num_modes": "hardcodeado_rescoring/scripts/redock_pdbbind.py:"
                         "num_modes=9",
            "box": "hardcodeado_rescoring/scripts/redock_pdbbind.py:size=25 + "
                  "centro_derivado_del_sdf",
            "preparation": "codigo_rescoring/scripts/redock_pdbbind.py",
            "engine": "artifacts_molflex_v3.json:probe",
            "experiment_id": "runner_rescoring/scripts/redock_pdbbind.py",
            "created_at": "unknown_sin_registro_temporal_determinista",
        },
    )


def registro_ruta_a(pid, stem):
    """Registro de provenance de ruta_a (stem = exh1|exh2|exh4)."""
    exh = int(stem.removeprefix("exh"))
    return pp.construir_registro(
        pid=pid, source="ruta_a", file_stem=stem,
        seed=pp.DESCONOCIDO, conformer_id="crystal",
        exhaustiveness=exh, num_modes=NUM_MODES,
        box=caja(pid), preparation=prep_ruta_a(),
        engine={"name": "vina", "version": VINA_VERSION},
        experiment_id="historico_ruta_a_exh_validation",
        created_at=pp.DESCONOCIDO,
        timeout=300, cpu=1, max_workers=4,
        recovery={
            "source": "dataset:source",
            "seed": "unknown_vina_sin_flag_seed_seed42_solo_cohorte",
            "conformer_id": "input_conformacion_cristal_meeko",
            "exhaustiveness": "nombre_archivo_exh{N}",
            "num_modes": "constante_scripts/ruta_a_exh_validation.py:"
                         "NUM_MODES",
            "box": "constante_scripts/molflex.py:BOX_SIZE + "
                  "centro_derivado_del_sdf",
            "preparation": "codigo_scripts/ruta_a_exh_validation.py + "
                           "molflex.py",
            "engine": "artifacts_molflex_v3.json:probe",
            "experiment_id": "runner_scripts/ruta_a_exh_validation.py",
            "created_at": "unknown_sin_registro_temporal_determinista",
        },
    )


# ───────────────────────── flujo principal ─────────────────────────────────

def cargar_poses_dataset():
    """Poses de los tres splits (solo lectura, orden determinista)."""
    poses = []
    for nombre in SPLITS:
        ruta = DATASET_DIR / nombre
        for linea in ruta.read_text(encoding="utf-8").splitlines():
            linea = linea.strip()
            if linea:
                poses.append(json.loads(linea))
    return poses


def construir_registros(poses):
    """{clave: registro} para todas las corridas presentes en el dataset."""
    registros = {}
    por_pid = {}
    for pose in poses:
        pid, fuente, stem = (str(pose["pid"]), str(pose["source"]),
                             str(pose["file_stem"]))
        clave = pp._clave(pid, fuente, stem)
        if clave in registros:
            continue
        por_pid.setdefault(pid, set()).add(fuente)
        if fuente == "molflex":
            cid = int(stem.removeprefix("conf").removesuffix(".out"))
            registros[clave] = registro_molflex(pid, stem, cid)
        elif fuente == "flexible_redock":
            registros[clave] = registro_flexible(pid)
        elif fuente == "ruta_a":
            registros[clave] = registro_ruta_a(pid, stem)
        else:
            raise ValueError(f"fuente desconocida en el dataset: {fuente}")
    return registros


def verificar_centros_rdkit(pids):
    """Compara el centroide stdlib contra rp.find_binding_center (RDKit).

    Verificación opcional: si las dependencias no están disponibles devuelve
    {"status": "no_verificado"} sin fallar.
    """
    try:
        sys.path.insert(0, str(PROJECT_ROOT / "rescoring" / "scripts"))
        import redock_pdbbind as rp  # noqa: F401
    except Exception:
        return {"status": "no_verificado",
                "razon": "rdkit_o_redock_pdbbind_no_importable"}
    discrepancias = []
    n = 0
    for pid in sorted(pids):
        sdf = PDBBIND / pid / f"{pid}_ligand.sdf"
        try:
            mine = centro_pesados_sdf(sdf.read_text(encoding="utf-8"))
            theirs = rp.find_binding_center(str(sdf))
        except Exception:
            discrepancias.append({"pid": pid, "razon": "excepcion"})
            continue
        n += 1
        if mine is None or theirs is None:
            discrepancias.append({"pid": pid,
                                  "razon": "uno_de_los_dos_ilegible"})
            continue
        t = [round(float(v), 3) for v in theirs]
        if any(abs(a - b) > 0.0015 for a, b in zip(mine, t)):
            discrepancias.append({"pid": pid, "stdlib": mine, "rdkit": t})
    return {"status": "ok" if not discrepancias else "con_discrepancias",
            "n_comparados": n, "discrepancias": discrepancias}


def consistencia_n_conf(registros):
    """n_conf del artefacto vs máximo conformer id presente en el dataset."""
    max_cid = {}
    for clave, reg in registros.items():
        if reg["source"] != "molflex":
            continue
        max_cid[reg["pid"]] = max(max_cid.get(reg["pid"], -1),
                                  reg["conformer_id"])
    notas = []
    for pid in sorted(max_cid):
        reg = next(r for c, r in registros.items()
                   if r["source"] == "molflex" and r["pid"] == pid)
        n_conf = reg.get("n_conf")
        if n_conf is None:
            notas.append({"pid": pid,
                          "nota": "n_conf_sin_artefacto",
                          "max_cid_plus_1": max_cid[pid] + 1})
        elif max_cid[pid] + 1 > n_conf:
            notas.append({"pid": pid, "n_conf": n_conf,
                          "nota": "max_cid_plus_1_supera_n_conf",
                          "max_cid_plus_1": max_cid[pid] + 1})
    return {"ok": not notas, "notas": notas}


def reporte_backfill(poses, registros, verificacion):
    """Resumen determinista de la recuperación (backfill_report.json)."""
    n_por_fuente = {}
    for reg in registros.values():
        n_por_fuente[reg["source"]] = n_por_fuente.get(reg["source"], 0) + 1
    recuperacion = {
        "source": "dataset_original",
        "seed": "molflex: constante randomSeed=42; resto: unknown",
        "conformer_id": "molflex: nombre conf{cid}.out; resto: crystal",
        "exhaustiveness": "molflex/flexible: constante 8; ruta_a: nombre exh{N}",
        "num_modes": "constante 9 en los tres generadores",
        "box": "size 25 (constante) + centro derivado determinista del SDF",
        "preparation": "cadenas documentadas en los scripts generadores",
        "engine": "artifacts_molflex_v3.json:probe (vina 1.2.7)",
        "experiment_id": "runner documentado en cada script generador",
        "created_at": "unknown: sin registro temporal determinista",
    }
    caveats = []
    if PID_MIXTO in {r["pid"] for r in registros.values()}:
        caveats.append(
            "10gs molflex es mezcla e2+v4 por reuso del workdir: v4 "
            "reescribio conf0-18 y conf19-28 quedaron stale de e2; los "
            "parametros de motor son identicos entre corridas, pero n_conf "
            "y run se atribuyen a e2 (29 conformeros, consistente con los "
            "stems del dataset).")
    return {
        "n_poses": len(poses),
        "n_registros": len(registros),
        "registros_por_fuente": dict(sorted(n_por_fuente.items())),
        "recuperacion_por_campo": recuperacion,
        "verificacion_centros_rdkit": verificacion,
        "consistencia_n_conf": consistencia_n_conf(registros),
        "caveats": caveats,
        "nota_determinismo": "sin marcas de tiempo; dos corridas producen "
                             "bytes identicos",
    }


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    parser = argparse.ArgumentParser(
        prog="backfill_pose_provenance.py",
        description="Sidecar de provenance de las 4300 poses historicas "
                    "(FND-06).")
    parser.add_argument("--out", metavar="FILE",
                        default=str(PROJECT_ROOT / "scripts" /
                                    "artifacts_science" / "FND-06" /
                                    "poses_provenance.jsonl"),
                        help="ruta del sidecar de salida")
    parser.add_argument("--report-out", metavar="FILE",
                        default=str(PROJECT_ROOT / "scripts" /
                                    "artifacts_science" / "FND-06" /
                                    "backfill_report.json"),
                        help="ruta del reporte de backfill")
    args = parser.parse_args(argv)

    poses = cargar_poses_dataset()
    registros = construir_registros(poses)

    # Verificación contra el verificador del contrato (validar_lote).
    reporte = pp.validar_lote(poses, registros)
    print(pp.tabla_cobertura(reporte))

    pids = sorted({str(p["pid"]) for p in poses})
    verificacion = verificar_centros_rdkit(pids)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    lineas = [json.dumps(registros[k], ensure_ascii=False)
              for k in sorted(registros)]
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    tmp.replace(out)
    print(f"Sidecar escrito: {out} ({len(lineas)} registros)")

    rep = reporte_backfill(poses, registros, verificacion)
    rep_tmp = Path(args.report_out).with_suffix(
        Path(args.report_out).suffix + ".tmp")
    rep_tmp.write_text(json.dumps(rep, ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8")
    rep_tmp.replace(Path(args.report_out))
    print(f"Reporte de backfill: {args.report_out}")
    print(f"Verificacion centros vs RDKit: {verificacion['status']}")
    print(f"n_conf consistente: {rep['consistencia_n_conf']['ok']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
