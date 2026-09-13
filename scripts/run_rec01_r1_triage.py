#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_rec01_r1_triage.py — REC-01-R1: corrigendum del criterio de excepción.

Preregistro: scripts/artifacts_science/REC-01-R1/PREREGISTRO.md
Corrigendum de: scripts/artifacts_science/REC-01/ (sellado GO 2026-08-17)

Añade el código `E8_HOTSPOT_FUERA_DE_CAJA` (margen_min_hotspots < 0), que cierra
el falso negativo estructural de REC-01 —la contención por FRACCIÓN no ve
desalineamientos concentrados en pocos hotspots, y por eso el caso testigo 5TUN
del doc. 35 pasó limpio— y asigna un triaje de severidad S0..S5 ordenado por una
única pregunta: ¿puede un docking en esta caja producir una pose correcta?

NO re-deriva geometría: consume el `per_complex.jsonl` SELLADO de REC-01 y
verifica su SHA-256 contra el manifest antes de leerlo (gate G1). Reutiliza
`scripts/run_rec01_grid_audit.py` por COMPOSICIÓN, sin modificarlo (doc. 49 §17:
un asset sellado no se edita).

Este corrigendum NO es una prueba ciega: su desenlace numérico ya estaba
declarado en REC-01/LECTURA.md §4. Ver §1 y §6 del preregistro.

Uso:
    python scripts/run_rec01_r1_triage.py
    python scripts/run_rec01_r1_triage.py --dry-run
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import platform
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXPERIMENT_ID = "REC-01-R1"
FUENTE_ID = "REC-01"
SRC_DIR = PROJECT_ROOT / "scripts" / "artifacts_science" / FUENTE_ID
OUT_DIR = PROJECT_ROOT / "scripts" / "artifacts_science" / EXPERIMENT_ID

SEED = 42

# ── Umbrales preregistrados (§4 del PREREGISTRO; no ajustar tras ver datos) ───
# E8 no tiene umbral calibrable: "el residuo está fuera de la caja" es exacto.
UMBRAL_E8_MARGEN = 0.0
SEV_GRAVE_D_CENTRO = 15.0     # d_centro > 15 A con ground truth fuerte -> S2
SEV_GRAVE_CONTENCION = 0.5    # contencion_ligando < 0.5 -> S2

CODIGOS_REC01 = (
    "E1_CENTRO_LEJOS", "E2_LIGANDO_RECORTADO", "E3_HOTSPOTS_FUERA",
    "E4_HOTSPOTS_INVALIDOS", "E5_HOTSPOTS_AUSENTES", "E6_SIN_PDB",
    "E7_PDB_NO_PARSEABLE",
)
CODIGO_NUEVO = "E8_HOTSPOT_FUERA_DE_CAJA"
CODIGOS_METADATO = {"E4_HOTSPOTS_INVALIDOS", "E5_HOTSPOTS_AUSENTES",
                    "E6_SIN_PDB", "E7_PDB_NO_PARSEABLE"}
CODIGOS_HOTSPOT = {"E3_HOTSPOTS_FUERA", CODIGO_NUEVO}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def _cargar_ejecutor_rec01():
    """Importa scripts/run_rec01_grid_audit.py sin modificarlo (composición)."""
    ruta = PROJECT_ROOT / "scripts" / "run_rec01_grid_audit.py"
    if not ruta.exists():
        raise FileNotFoundError(f"Ejecutor de REC-01 no encontrado: {ruta}")
    spec = importlib.util.spec_from_file_location("_rec01_ejecutor", ruta)
    if spec is None or spec.loader is None:
        raise ImportError(f"No se pudo cargar {ruta}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod, ruta


# ── G1: integridad de la entrada sellada ─────────────────────────────────────

def verificar_entrada_sellada() -> dict[str, Any]:
    """El per_complex.jsonl de REC-01 debe coincidir con su SHA-256 sellado."""
    manifest = json.loads((SRC_DIR / "manifest.json").read_text(encoding="utf-8"))
    assets = manifest.get("assets_hashes", {})
    clave = next((k for k in assets if k.endswith("REC-01/per_complex.jsonl")), None)
    if clave is None:
        raise RuntimeError("REC-01/per_complex.jsonl no figura en assets_hashes del manifest sellado")
    esperado = assets[clave]
    real = sha256_file(SRC_DIR / "per_complex.jsonl")
    return {
        "criterio": "per_complex.jsonl de REC-01 coincide con su SHA-256 sellado",
        "sha256_esperado": esperado,
        "sha256_real": real,
        "decision_fuente": manifest.get("decision"),
        "pass": esperado == real,
    }


# ── Criterio E8 y severidad ──────────────────────────────────────────────────

def aplicar_e8(fila: dict) -> bool:
    """True si el target dispara E8. margen None -> no dispara (ya lo cubre E4)."""
    margen = fila.get("margen_min_hotspots")
    return margen is not None and margen < UMBRAL_E8_MARGEN


def asignar_severidad(fila: dict, excepciones: list[str]) -> str:
    """Primera condición que aplica, en el orden preregistrado §4.2."""
    if not excepciones:
        return "S0_SIN_EXCEPCION"

    cont = fila.get("contencion_ligando")
    d = fila.get("d_centro")
    fuerte = fila.get("ground_truth") == "fuerte"

    # S1: la caja no contiene ni un átomo del ligando nativo
    if cont is not None and cont == 0.0:
        return "S1_CRITICO"

    # S2: sitio mayoritariamente fuera
    if fuerte and d is not None and d > SEV_GRAVE_D_CENTRO:
        return "S2_GRAVE"
    if cont is not None and 0.0 < cont < SEV_GRAVE_CONTENCION:
        return "S2_GRAVE"

    # S3: recorte parcial
    if "E1_CENTRO_LEJOS" in excepciones:
        return "S3_MODERADO"
    if cont is not None and SEV_GRAVE_CONTENCION <= cont < 1.0:
        return "S3_MODERADO"

    # S4: sólo problemas de hotspots, sin recorte de ligando
    if any(c in CODIGOS_HOTSPOT for c in excepciones):
        return "S4_LEVE"

    # S5: sólo defectos de datos
    if all(c in CODIGOS_METADATO for c in excepciones):
        return "S5_METADATO"

    return "S4_LEVE"


# ── Agregados ────────────────────────────────────────────────────────────────

def construir_metricas(filas: list[dict], base: list[dict], g1: dict,
                       dur_s: float, hashes_rec01: dict, ejecutor_sha: str) -> dict:
    n = len(filas)

    def _p(num: int, den: int) -> float:
        return round(num / den, 4) if den else 0.0

    cod = Counter()
    for f in filas:
        for e in f["excepciones"]:
            cod[e] += 1
    cod_base = Counter()
    for f in base:
        for e in f.get("excepciones", []):
            cod_base[e] += 1

    con_exc = [f for f in filas if f["es_excepcion"]]
    con_exc_base = [f for f in base if f.get("es_excepcion")]
    sev = Counter(f["severidad"] for f in filas)

    # G3: conservación — ningún target pierde una excepción previa
    perdidas = []
    idx_base = {f["pdb_id"]: set(f.get("excepciones", [])) for f in base}
    for f in filas:
        faltan = idx_base.get(f["pdb_id"], set()) - set(f["excepciones"])
        if faltan:
            perdidas.append({"pdb_id": f["pdb_id"], "perdidas": sorted(faltan)})

    nuevos_e8 = [f for f in filas
                 if CODIGO_NUEVO in f["excepciones"] and not idx_base.get(f["pdb_id"])]

    # G2: prueba de aceptación sobre 5TUN
    t5 = next((f for f in filas if f["pdb_id"] == "5TUN"), None)
    g2 = {
        "criterio": "5TUN capturado por E8 con severidad S4_LEVE",
        "encontrado": t5 is not None,
        "excepciones": t5["excepciones"] if t5 else None,
        "severidad": t5["severidad"] if t5 else None,
        "margen_min_hotspots": t5.get("margen_min_hotspots") if t5 else None,
        "pass": bool(t5 and CODIGO_NUEVO in t5["excepciones"]
                     and t5["severidad"] == "S4_LEVE"),
    }

    por_familia = defaultdict(lambda: {"n": 0, "excepciones": 0, "S1_CRITICO": 0})
    for f in filas:
        e = por_familia[f["familia"]]
        e["n"] += 1
        e["excepciones"] += 1 if f["es_excepcion"] else 0
        e["S1_CRITICO"] += 1 if f["severidad"] == "S1_CRITICO" else 0

    esperado = {"excepciones_totales": 109, "nuevos_por_E8": 52, "S1_CRITICO": 23}
    observado = {"excepciones_totales": len(con_exc),
                 "nuevos_por_E8": len(nuevos_e8),
                 "S1_CRITICO": sev.get("S1_CRITICO", 0)}

    return {
        "experiment_id": EXPERIMENT_ID,
        "corrigendum_de": FUENTE_ID,
        "prueba_ciega": False,
        "nota_epistemica": (
            "El desenlace numerico ya estaba declarado en REC-01/LECTURA.md seccion 4 "
            "antes de ejecutar R1. No es un hallazgo independiente: es el mismo dato "
            "con el criterio corregido. Ver PREREGISTRO seccion 1."
        ),
        "seed": SEED,
        "umbrales_preregistrados": {
            "E8_margen": UMBRAL_E8_MARGEN,
            "severidad_grave_d_centro_A": SEV_GRAVE_D_CENTRO,
            "severidad_grave_contencion": SEV_GRAVE_CONTENCION,
        },
        "alcance": {"n_targets": n, "fuente": f"{FUENTE_ID}/per_complex.jsonl (sellado)",
                    "sin_docking": True, "sin_re_derivar_geometria": True},
        "expectativa_vs_observado": {
            "declarado_en_preregistro": esperado,
            "observado": observado,
            "coincide": esperado == observado,
        },
        "excepciones": {
            "antes_REC01": {"n_targets": len(con_exc_base),
                            "pct": _p(len(con_exc_base), n),
                            "por_codigo": dict(sorted(cod_base.items()))},
            "despues_R1": {"n_targets": len(con_exc),
                           "pct": _p(len(con_exc), n),
                           "por_codigo": dict(sorted(cod.items()))},
            "delta_targets": len(con_exc) - len(con_exc_base),
            "nuevos_solo_por_E8": sorted(f["pdb_id"] for f in nuevos_e8),
        },
        "severidad": {k: {"n": v, "pct": _p(v, n)} for k, v in sorted(sev.items())},
        "cohorte_accionable": {
            "S1_CRITICO": sorted(f["pdb_id"] for f in filas if f["severidad"] == "S1_CRITICO"),
            "S2_GRAVE": sorted(f["pdb_id"] for f in filas if f["severidad"] == "S2_GRAVE"),
        },
        "por_familia": {k: {**v, "pct_excepcion": _p(v["excepciones"], v["n"])}
                        for k, v in sorted(por_familia.items())},
        "gates": {
            "G1_integridad_entrada": g1,
            "G2_aceptacion_5TUN": g2,
            "G3_conservacion": {
                "criterio": "ningun target pierde una excepcion de REC-01; codigos E1-E7 se reproducen",
                "n_targets_con_perdidas": len(perdidas),
                "perdidas": perdidas,
                "codigos_E1_E7_reproducidos": {c: (cod_base.get(c, 0) == cod.get(c, 0))
                                               for c in CODIGOS_REC01},
                "pass": len(perdidas) == 0 and all(
                    cod_base.get(c, 0) == cod.get(c, 0) for c in CODIGOS_REC01),
            },
            "G4_severidad_total": {
                "criterio": "los 387 con exactamente un nivel S0-S5, sin nulos",
                "n_sin_severidad": sum(1 for f in filas if not f.get("severidad")),
                "niveles_usados": sorted(sev.keys()),
                "pass": all(f.get("severidad") for f in filas) and sum(sev.values()) == n,
            },
            "G5_determinismo": {
                "criterio": "dos corridas -> per_complex.jsonl byte-identico",
                "pass": None,
            },
            "G6_aislamiento": {
                "criterio": "REC-01 conserva los SHA-256 de sus assets",
                "hashes_rec01_post": hashes_rec01,
                "pass": None,
            },
        },
        "entorno": {
            "python": platform.python_version(),
            "so": f"{platform.system()} {platform.release()}",
            "duracion_s": round(dur_s, 2),
            "ejecutor_rec01_sha256": ejecutor_sha,
            "generado_utc": datetime.now(timezone.utc).isoformat(),
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="REC-01-R1: corrigendum E8 + triaje de severidad")
    ap.add_argument("--dry-run", action="store_true", help="no escribe artefactos")
    args = ap.parse_args()

    t0 = time.time()

    # Composición sobre el ejecutor sellado de REC-01 (no se modifica)
    ejecutor, ruta_ejecutor = _cargar_ejecutor_rec01()
    ejecutor_sha = sha256_file(ruta_ejecutor)
    assert ejecutor.UMBRAL_E3_HOTSPOTS == 0.80, "el umbral E3 de REC-01 cambió; abortar"

    # ── G1: integridad de la entrada sellada ──
    g1 = verificar_entrada_sellada()
    print(f"[R1] G1 integridad de entrada: {'PASS' if g1['pass'] else 'FAIL'}", flush=True)
    if not g1["pass"]:
        print(f"[R1] esperado {g1['sha256_esperado'][:16]}  real {g1['sha256_real'][:16]}")
        print("[R1] ABORTA: la entrada sellada no coincide con su hash.")
        return 2

    base = [json.loads(l) for l in
            (SRC_DIR / "per_complex.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    print(f"[R1] targets leidos de {FUENTE_ID}: {len(base)}", flush=True)

    # ── Aplicar E8 y severidad ──
    filas: list[dict] = []
    for f in sorted(base, key=lambda r: r["pdb_id"]):
        nueva = dict(f)
        exc = list(f.get("excepciones", []))
        if aplicar_e8(f) and CODIGO_NUEVO not in exc:
            exc.append(CODIGO_NUEVO)
        exc = sorted(set(exc))
        nueva["excepciones"] = exc
        nueva["es_excepcion"] = bool(exc)
        nueva["severidad"] = asignar_severidad(f, exc)
        nueva["excepciones_rec01"] = sorted(f.get("excepciones", []))
        filas.append(nueva)

    hashes_rec01 = {p.name: sha256_file(p) for p in sorted(SRC_DIR.iterdir())
                    if p.is_file() and p.name != "README.md"}
    metricas = construir_metricas(filas, base, g1, time.time() - t0,
                                  hashes_rec01, ejecutor_sha)

    # ── Resumen ──
    print("\n" + "=" * 68)
    print("REC-01-R1 — CORRIGENDUM E8 + TRIAJE DE SEVERIDAD")
    print("=" * 68)
    e = metricas["excepciones"]
    print(f"Excepciones: {e['antes_REC01']['n_targets']} "
          f"({e['antes_REC01']['pct']*100:.1f}%)  ->  "
          f"{e['despues_R1']['n_targets']} ({e['despues_R1']['pct']*100:.1f}%)   "
          f"[+{e['delta_targets']}]")
    print(f"\nNuevos sólo por {CODIGO_NUEVO}: {len(e['nuevos_solo_por_E8'])}")
    print("\nSeveridad:")
    for k, v in metricas["severidad"].items():
        print(f"  {k:<20} {v['n']:>4}  ({v['pct']*100:5.1f}%)")
    ev = metricas["expectativa_vs_observado"]
    print(f"\nExpectativa preregistrada vs observado: "
          f"{'COINCIDE' if ev['coincide'] else 'DISCREPA'}")
    if not ev["coincide"]:
        print(f"  declarado: {ev['declarado_en_preregistro']}")
        print(f"  observado: {ev['observado']}")
    print("\nGates:")
    for g, d in metricas["gates"].items():
        estado = {True: "PASS", False: "FAIL", None: "PENDIENTE"}[d["pass"]]
        print(f"  {g:<28} {estado}")

    if args.dry_run:
        print("\n[R1] --dry-run: no se escriben artefactos.")
        return 0

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_DIR / "per_complex.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for fila in filas:
            f.write(json.dumps(fila, ensure_ascii=False, sort_keys=True) + "\n")
    with open(OUT_DIR / "failures.jsonl", "w", encoding="utf-8", newline="\n") as f:
        pass  # R1 no puede fallar por target: la entrada ya está sellada y validada
    with open(OUT_DIR / "metrics.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(metricas, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")

    print(f"\n[R1] artefactos escritos en {OUT_DIR.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
