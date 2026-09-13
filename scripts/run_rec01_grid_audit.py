#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_rec01_grid_audit.py — REC-01: auditoría de grids y hotspots (387 targets).

Preregistro: scripts/artifacts_science/REC-01/PREREGISTRO.md
Protocolo:   docs/49_PROGRAMA_EXPERIMENTAL_CIENTIFICO.md §7 (Cartera B, REC-01)

Reutiliza por COMPOSICIÓN `backend/scripts/audit_grid_hotspots.py` (política del
doc. 49 §17: un activo existente no se edita; se importa y se extiende). De ese
módulo se toman `SKIP_ARTIFACT`, `COFACTORS` y `native_ligand_info`.

Diferencias deliberadas respecto del activo original, documentadas porque
cambian el resultado:

  1. La fuente de targets es `curated_targets.json` (387 targets del catálogo),
     no la tabla `TargetORM` de la DB — las DB locales están vacías y el
     preregistro fija el alcance en los 387 del catálogo.
  2. El índice de PDBs se construye UNA vez con orden determinista y una regla
     de preferencia explícita. El `find_local_pdb` original devuelve el primer
     resultado de `rglob`, cuyo orden no está garantizado entre sistemas de
     archivos; eso rompería el gate G4 de determinismo.

SOLO LECTURA: no escribe en el catálogo, ni en ninguna DB, ni en rescoring/.
El gate G5 verifica esa propiedad por SHA-256 antes y después.

Uso:
    python scripts/run_rec01_grid_audit.py            # ejecuta y escribe artefactos
    python scripts/run_rec01_grid_audit.py --dry-run  # no escribe artefactos
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import platform
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXPERIMENT_ID = "REC-01"
OUT_DIR = PROJECT_ROOT / "scripts" / "artifacts_science" / EXPERIMENT_ID
CATALOG = PROJECT_ROOT / "curated_targets.json"
PDB_BASES = (PROJECT_ROOT / "data" / "target_library", PROJECT_ROOT / "data" / "targets")

# ── Constantes preregistradas (§4 del PREREGISTRO; no ajustar tras ver datos) ──
MIN_HEAVY_ATOMS_LIGANDO = 6      # umbral para considerar un HETATM ligando real
UMBRAL_E1_CENTRO_A = 6.0         # d_centro > 6.0 A -> E1_CENTRO_LEJOS
UMBRAL_E3_HOTSPOTS = 0.80        # contencion_hotspots < 0.80 -> E3
UMBRAL_E4_VALIDOS = 0.80         # hotspots_validos  < 0.80 -> E4
MIN_HOTSPOTS = 5                 # menos de 5 hotspots -> E5
SEED = 42

# Rutas cuya integridad verifica el gate G5 (solo lectura)
RUTAS_PROTEGIDAS = (
    PROJECT_ROOT / "curated_targets.json",
    PROJECT_ROOT / "curated_targets.csv",
)


# ── Carga del activo original por composición ────────────────────────────────

def _cargar_activo_original():
    """Importa backend/scripts/audit_grid_hotspots.py sin modificarlo."""
    ruta = PROJECT_ROOT / "backend" / "scripts" / "audit_grid_hotspots.py"
    if not ruta.exists():
        raise FileNotFoundError(f"Activo original no encontrado: {ruta}")
    spec = importlib.util.spec_from_file_location("_rec01_audit_original", ruta)
    if spec is None or spec.loader is None:
        raise ImportError(f"No se pudo cargar {ruta}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod, ruta


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


# ── Índice determinista de PDBs locales ──────────────────────────────────────

def construir_indice_pdb() -> dict[str, Path]:
    """Mapa PDB_ID -> ruta, determinista.

    Preferencia preregistrada, en orden:
      1. el archivo cuyo stem es exactamente el pdb_id (sin sufijos);
      2. entre los demás, el de nombre lexicográficamente menor.
    Así `7E2Y.pdb` gana a `7e2y_chainR.pdb` de forma estable.
    """
    candidatos: dict[str, list[Path]] = defaultdict(list)
    for base in PDB_BASES:
        if not base.exists():
            continue
        for p in sorted(base.rglob("*.pdb"), key=lambda q: str(q).lower()):
            key = p.stem.split("_")[0].upper()
            candidatos[key].append(p)

    indice: dict[str, Path] = {}
    for key, rutas in candidatos.items():
        exactos = [r for r in rutas if r.stem.upper() == key]
        elegidas = exactos if exactos else rutas
        indice[key] = sorted(elegidas, key=lambda q: q.name.lower())[0]
    return indice


# ── Parseo geométrico ────────────────────────────────────────────────────────

def parsear_ca_por_residuo(pdb_path: Path) -> dict[str, tuple[float, float, float]]:
    """Mapa 'CHAIN:RESNAME+SEQ' -> coordenada del CA. Solo registros ATOM."""
    salida: dict[str, tuple[float, float, float]] = {}
    contenido = pdb_path.read_text(encoding="utf-8", errors="replace")
    for linea in contenido.splitlines():
        if not linea.startswith("ATOM"):
            continue
        if len(linea) < 54:
            continue
        if linea[12:16].strip() != "CA":
            continue
        resname = linea[17:20].strip()
        chain = linea[21:22].strip() or "A"
        seq = linea[22:26].strip()
        clave = f"{chain}:{resname}{seq}"
        if clave in salida:
            continue  # primera ocurrencia gana (altloc A); determinista
        try:
            salida[clave] = (float(linea[30:38]), float(linea[38:46]), float(linea[46:54]))
        except ValueError:
            continue
    return salida


def atomos_pesados_ligando(pdb_path: Path, skip: set[str]) -> dict[str, list[tuple]]:
    """Grupos HETATM no-artefacto -> lista de coords de átomos pesados (sin H)."""
    grupos: dict[str, list[tuple[float, float, float]]] = defaultdict(list)
    contenido = pdb_path.read_text(encoding="utf-8", errors="replace")
    for linea in contenido.splitlines():
        if not linea.startswith("HETATM") or len(linea) < 54:
            continue
        rn = linea[17:20].strip()
        if rn in skip:
            continue
        elemento = linea[76:78].strip().upper() if len(linea) >= 78 else ""
        nombre = linea[12:16].strip()
        # excluir hidrógenos: por columna de elemento, o por nombre si falta
        if elemento == "H" or (not elemento and nombre[:1] == "H"):
            continue
        chain = linea[21:22].strip() or "A"
        seq = linea[22:26].strip()
        try:
            xyz = (float(linea[30:38]), float(linea[38:46]), float(linea[46:54]))
        except ValueError:
            continue
        grupos[f"{chain}:{rn}{seq}"].append(xyz)
    return dict(grupos)


def dentro_de_caja(p: tuple[float, float, float], centro: tuple[float, float, float],
                   tam: tuple[float, float, float]) -> bool:
    return all(abs(p[i] - centro[i]) <= tam[i] / 2.0 for i in range(3))


def margen_al_borde(p: tuple[float, float, float], centro: tuple[float, float, float],
                    tam: tuple[float, float, float]) -> float:
    """Distancia al borde más cercano; negativa si el punto está fuera."""
    return min(tam[i] / 2.0 - abs(p[i] - centro[i]) for i in range(3))


# ── Auditoría de un target ───────────────────────────────────────────────────

def auditar_target(t: dict[str, Any], indice: dict[str, Path],
                   skip: set[str], cofactores: set[str]) -> dict[str, Any]:
    pdb_id = str(t.get("pdb_id", "")).upper()
    fila: dict[str, Any] = {
        "pdb_id": pdb_id,
        "familia": t.get("structural_family") or "unknown",
        "cadena_catalogo": t.get("chain"),
        "excepciones": [],
    }

    centro = (float(t.get("grid_center_x") or 0.0),
              float(t.get("grid_center_y") or 0.0),
              float(t.get("grid_center_z") or 0.0))
    tam = (float(t.get("grid_size_x") or 0.0),
           float(t.get("grid_size_y") or 0.0),
           float(t.get("grid_size_z") or 0.0))
    fila["grid_centro"] = [round(c, 3) for c in centro]
    fila["grid_tam"] = [round(s, 3) for s in tam]

    # hotspots declarados
    hs_raw = t.get("hotspots")
    hs_lista = [h for h in hs_raw if isinstance(h, dict) and h.get("name")] if isinstance(hs_raw, list) else []
    fila["n_hotspots_declarados"] = len(hs_lista)
    if len(hs_lista) < MIN_HOTSPOTS:
        fila["excepciones"].append("E5_HOTSPOTS_AUSENTES")

    ruta = indice.get(pdb_id)
    if ruta is None:
        fila["pdb_encontrado"] = False
        fila["excepciones"].append("E6_SIN_PDB")
        fila["estrato"] = "INDETERMINADO"
        return fila
    fila["pdb_encontrado"] = True
    fila["pdb_ruta"] = str(ruta.relative_to(PROJECT_ROOT)).replace("\\", "/")

    try:
        grupos = atomos_pesados_ligando(ruta, skip)
        ca = parsear_ca_por_residuo(ruta)
    except Exception as exc:  # PDB ilegible
        fila["excepciones"].append("E7_PDB_NO_PARSEABLE")
        fila["estrato"] = "INDETERMINADO"
        fila["error_parseo"] = str(exc)[:200]
        return fila

    if not ca and not grupos:
        fila["excepciones"].append("E7_PDB_NO_PARSEABLE")
        fila["estrato"] = "INDETERMINADO"
        return fila

    # ── Clasificación de estrato (§4.1) ──
    reales = {k: v for k, v in grupos.items() if len(v) >= MIN_HEAVY_ATOMS_LIGANDO}
    def _codigo(rid: str) -> str:
        rn = rid.split(":")[1]
        return "".join(c for c in rn if c.isalpha()) or rn[:3]

    no_cofactor = {k: v for k, v in reales.items() if _codigo(k) not in cofactores}

    if no_cofactor:
        estrato = "HOLO"
        # desempate determinista: más átomos, luego id lexicográfico
        mejor = sorted(no_cofactor.items(), key=lambda kv: (-len(kv[1]), kv[0]))[0]
    elif reales:
        estrato = "HOLO_COFACTOR_ONLY"
        mejor = sorted(reales.items(), key=lambda kv: (-len(kv[1]), kv[0]))[0]
    else:
        estrato = "APO"
        mejor = None

    fila["estrato"] = estrato

    # ── Ground truth (§4.2) ──
    if estrato == "HOLO" and mejor is not None:
        rid, pts = mejor
        gt = tuple(sum(p[i] for p in pts) / len(pts) for i in range(3))
        fila["ligando_nativo"] = {"id": rid, "codigo": _codigo(rid), "n_atomos_pesados": len(pts)}
        fila["ground_truth"] = "fuerte"
        dentro = sum(1 for p in pts if dentro_de_caja(p, centro, tam))
        fila["contencion_ligando"] = round(dentro / len(pts), 4)
        fila["margen_min_ligando"] = round(min(margen_al_borde(p, centro, tam) for p in pts), 3)
        if fila["contencion_ligando"] < 1.0:
            fila["excepciones"].append("E2_LIGANDO_RECORTADO")
    else:
        gt = None
        fila["ground_truth"] = "debil"
        fila["contencion_ligando"] = None
        fila["margen_min_ligando"] = None
        if estrato == "HOLO_COFACTOR_ONLY" and mejor is not None:
            fila["ligando_nativo"] = {"id": mejor[0], "codigo": _codigo(mejor[0]),
                                      "n_atomos_pesados": len(mejor[1]), "es_cofactor": True}

    # ── Hotspots: validez y contención ──
    encontrados, contenidos, margenes = 0, 0, []
    for h in hs_lista:
        nombre = str(h.get("name", "")).strip()
        coord = ca.get(nombre)
        if coord is None:
            continue
        encontrados += 1
        margenes.append(margen_al_borde(coord, centro, tam))
        if dentro_de_caja(coord, centro, tam):
            contenidos += 1

    if hs_lista:
        fila["hotspots_validos"] = round(encontrados / len(hs_lista), 4)
        fila["contencion_hotspots"] = round(contenidos / len(hs_lista), 4)
        fila["margen_min_hotspots"] = round(min(margenes), 3) if margenes else None
        if fila["hotspots_validos"] < UMBRAL_E4_VALIDOS:
            fila["excepciones"].append("E4_HOTSPOTS_INVALIDOS")
        if fila["contencion_hotspots"] < UMBRAL_E3_HOTSPOTS:
            fila["excepciones"].append("E3_HOTSPOTS_FUERA")
    else:
        fila["hotspots_validos"] = None
        fila["contencion_hotspots"] = None
        fila["margen_min_hotspots"] = None

    # ground truth débil para APO: centroide de CA de hotspots hallados
    if gt is None and encontrados:
        pts_hs = [ca[str(h.get("name", "")).strip()] for h in hs_lista
                  if ca.get(str(h.get("name", "")).strip()) is not None]
        gt = tuple(sum(p[i] for p in pts_hs) / len(pts_hs) for i in range(3))

    # ── d_centro y E1 (E1 solo aplica a ground truth fuerte, §4.4) ──
    if gt is not None:
        fila["ground_truth_centro"] = [round(c, 3) for c in gt]
        d = math.dist(centro, gt)
        fila["d_centro"] = round(d, 3)
        if fila["ground_truth"] == "fuerte" and d > UMBRAL_E1_CENTRO_A:
            fila["excepciones"].append("E1_CENTRO_LEJOS")
    else:
        fila["ground_truth_centro"] = None
        fila["d_centro"] = None

    fila["es_excepcion"] = bool(fila["excepciones"])
    return fila


# ── Agregados ────────────────────────────────────────────────────────────────

def construir_metricas(filas: list[dict], indice_n: int, dur_s: float,
                       hashes_pre: dict, hashes_post: dict,
                       activo_sha: str) -> dict:
    def _p(num: int, den: int) -> float:
        return round(num / den, 4) if den else 0.0

    n = len(filas)
    por_estrato = Counter(f["estrato"] for f in filas)
    excepciones = Counter()
    for f in filas:
        for e in f["excepciones"]:
            excepciones[e] += 1

    holo = [f for f in filas if f["estrato"] == "HOLO"]
    d_holo = sorted(f["d_centro"] for f in holo if f.get("d_centro") is not None)

    def _banda(lim: float) -> dict:
        k = sum(1 for d in d_holo if d <= lim)
        return {"n": k, "pct": _p(k, len(d_holo))}

    def _mediana(xs: list[float]):
        if not xs:
            return None
        m = len(xs) // 2
        return round(xs[m] if len(xs) % 2 else (xs[m - 1] + xs[m]) / 2, 3)

    con_exc = [f for f in filas if f["es_excepcion"]]
    por_familia = defaultdict(lambda: {"n": 0, "excepciones": 0})
    for f in filas:
        e = por_familia[f["familia"]]
        e["n"] += 1
        e["excepciones"] += 1 if f["es_excepcion"] else 0

    contencion_lig = sorted(f["contencion_ligando"] for f in holo
                            if f.get("contencion_ligando") is not None)
    contencion_hs = sorted(f["contencion_hotspots"] for f in filas
                           if f.get("contencion_hotspots") is not None)

    return {
        "experiment_id": EXPERIMENT_ID,
        "seed": SEED,
        "alcance": {
            "n_targets_catalogo": n,
            "n_pdb_ids_indexados": indice_n,
            "fuente_targets": "curated_targets.json",
            "sin_docking": True,
        },
        "umbrales_preregistrados": {
            "min_heavy_atoms_ligando": MIN_HEAVY_ATOMS_LIGANDO,
            "E1_centro_A": UMBRAL_E1_CENTRO_A,
            "E3_contencion_hotspots": UMBRAL_E3_HOTSPOTS,
            "E4_hotspots_validos": UMBRAL_E4_VALIDOS,
            "E5_min_hotspots": MIN_HOTSPOTS,
        },
        "estratos": {k: {"n": v, "pct": _p(v, n)} for k, v in sorted(por_estrato.items())},
        "excepciones": {
            "n_targets_con_excepcion": len(con_exc),
            "pct_targets_con_excepcion": _p(len(con_exc), n),
            "por_codigo": dict(sorted(excepciones.items())),
        },
        "d_centro_holo": {
            "n": len(d_holo),
            "mediana": _mediana(d_holo),
            "p90": round(d_holo[int(len(d_holo) * 0.9)], 3) if d_holo else None,
            "max": round(d_holo[-1], 3) if d_holo else None,
            "bandas": {"le_4A": _banda(4.0), "le_6A": _banda(6.0),
                       "le_10A": _banda(10.0), "le_15A": _banda(15.0),
                       "gt_15A": {"n": sum(1 for d in d_holo if d > 15.0),
                                  "pct": _p(sum(1 for d in d_holo if d > 15.0), len(d_holo))}},
        },
        "contencion": {
            "ligando_holo": {"n": len(contencion_lig), "mediana": _mediana(contencion_lig),
                             "n_completa_1_0": sum(1 for c in contencion_lig if c >= 1.0)},
            "hotspots_todos": {"n": len(contencion_hs), "mediana": _mediana(contencion_hs)},
        },
        "por_familia": {k: {**v, "pct_excepcion": _p(v["excepciones"], v["n"])}
                        for k, v in sorted(por_familia.items())},
        "gates": {
            "G1_cobertura_total": {
                "criterio": "los 387 targets con veredicto explicito, 0 omisiones",
                "n_auditados": n,
                "n_esperados": 387,
                "pass": n == 387,
            },
            "G2_clasificacion_deterministica": {
                "criterio": "cada target con exactamente un estrato de {HOLO, APO, HOLO_COFACTOR_ONLY, INDETERMINADO}",
                "n_sin_estrato": sum(1 for f in filas if not f.get("estrato")),
                "pass": all(f.get("estrato") for f in filas),
            },
            "G3_excepciones_con_criterio": {
                "criterio": "toda excepcion cita codigo E1-E7",
                "codigos_validos": ["E1_CENTRO_LEJOS", "E2_LIGANDO_RECORTADO",
                                    "E3_HOTSPOTS_FUERA", "E4_HOTSPOTS_INVALIDOS",
                                    "E5_HOTSPOTS_AUSENTES", "E6_SIN_PDB",
                                    "E7_PDB_NO_PARSEABLE"],
                "pass": all(e.startswith("E") for f in filas for e in f["excepciones"]),
            },
            "G4_determinismo": {
                "criterio": "dos corridas producen per_complex.jsonl byte-identico",
                "nota": "se verifica ejecutando el script dos veces y comparando SHA-256",
                "pass": None,
            },
            "G5_solo_lectura": {
                "criterio": "catalogo y CSV conservan su SHA-256",
                "hashes_pre": hashes_pre,
                "hashes_post": hashes_post,
                "pass": hashes_pre == hashes_post,
            },
        },
        "entorno": {
            "python": platform.python_version(),
            "so": f"{platform.system()} {platform.release()}",
            "duracion_s": round(dur_s, 2),
            "activo_original_sha256": activo_sha,
            "generado_utc": datetime.now(timezone.utc).isoformat(),
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="REC-01: auditoría de grids y hotspots (387 targets)")
    ap.add_argument("--dry-run", action="store_true", help="no escribe artefactos")
    args = ap.parse_args()

    t0 = time.time()
    original, ruta_activo = _cargar_activo_original()
    skip = set(original.SKIP_ARTIFACT)
    cofactores = set(original.COFACTORS)
    activo_sha = sha256_file(ruta_activo)

    hashes_pre = {p.name: sha256_file(p) for p in RUTAS_PROTEGIDAS if p.exists()}

    targets = json.loads(CATALOG.read_text(encoding="utf-8"))
    targets = sorted(targets, key=lambda t: str(t.get("pdb_id", "")).upper())
    print(f"[REC-01] targets en catálogo: {len(targets)}", flush=True)

    indice = construir_indice_pdb()
    print(f"[REC-01] PDB IDs indexados: {len(indice)}", flush=True)

    filas: list[dict] = []
    fallos: list[dict] = []
    for i, t in enumerate(targets, 1):
        try:
            filas.append(auditar_target(t, indice, skip, cofactores))
        except Exception as exc:
            pid = str(t.get("pdb_id", "?")).upper()
            fallos.append({"pdb_id": pid, "causa": type(exc).__name__, "detalle": str(exc)[:300]})
            filas.append({"pdb_id": pid, "familia": t.get("structural_family") or "unknown",
                          "estrato": "INDETERMINADO", "excepciones": ["E7_PDB_NO_PARSEABLE"],
                          "es_excepcion": True, "pdb_encontrado": None})
        if i % 100 == 0:
            print(f"[REC-01]   {i}/{len(targets)}", flush=True)

    hashes_post = {p.name: sha256_file(p) for p in RUTAS_PROTEGIDAS if p.exists()}
    metricas = construir_metricas(filas, len(indice), time.time() - t0,
                                  hashes_pre, hashes_post, activo_sha)

    # ── Resumen a consola ──
    print("\n" + "=" * 68)
    print("REC-01 — AUDITORÍA DE GRIDS Y HOTSPOTS")
    print("=" * 68)
    print(f"Targets auditados: {metricas['alcance']['n_targets_catalogo']}")
    print("\nEstratos:")
    for k, v in metricas["estratos"].items():
        print(f"  {k:<20} {v['n']:>4}  ({v['pct']*100:5.1f}%)")
    dc = metricas["d_centro_holo"]
    if dc["n"]:
        print(f"\nd_centro en HOLO (n={dc['n']}): mediana {dc['mediana']} Å, "
              f"p90 {dc['p90']} Å, max {dc['max']} Å")
        for nombre, b in dc["bandas"].items():
            print(f"  {nombre:<8} {b['n']:>4}  ({b['pct']*100:5.1f}%)")
    exc = metricas["excepciones"]
    print(f"\nTargets con excepción: {exc['n_targets_con_excepcion']} "
          f"({exc['pct_targets_con_excepcion']*100:.1f}%)")
    for k, v in exc["por_codigo"].items():
        print(f"  {k:<26} {v:>4}")
    print("\nGates:")
    for g, d in metricas["gates"].items():
        estado = {True: "PASS", False: "FAIL", None: "PENDIENTE"}[d["pass"]]
        print(f"  {g:<34} {estado}")

    if args.dry_run:
        print("\n[REC-01] --dry-run: no se escriben artefactos.")
        return 0

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_DIR / "per_complex.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for fila in filas:
            f.write(json.dumps(fila, ensure_ascii=False, sort_keys=True) + "\n")
    with open(OUT_DIR / "failures.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for fal in fallos:
            f.write(json.dumps(fal, ensure_ascii=False, sort_keys=True) + "\n")
    with open(OUT_DIR / "metrics.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(metricas, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")

    print(f"\n[REC-01] artefactos escritos en {OUT_DIR.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
