# -*- coding: utf-8 -*-
"""run_rs01a_corrigendum.py — CORRIGENDUM de RS-01A (metrics.json).

Correcciones exactas del maintainer (sin re-ejecutar la auditoria completa;
solo se recomputa lo necesario):

  1. Contrafactual NO invariante: el contrafactual de los 31 empates
     cross-source muestra SENSIBILIDAD al desempate de fuente. Valores reales
     observados (verificados aqui por recomputacion): base 0.6379;
     alternativas 0.6293, 0.6379, 0.6466 (7 cambian ganador, 2 cambian hit).
     Se corrige metrics.json (resumen con rango y declaracion).
  2. Estadisticos pareados distinguidos: las cuatro cantidades EXACTAS
     (recalculadas desde per_complex.jsonl):
       - diferencia de medianas: +0.032 A (1.457 - 1.425, medianas por brazo)
       - mediana de diferencias pareadas: 0.000 A  -> PRIMARIO RS-01B
       - media pareada: +0.0731 A
       - suma pareada: +8.476 A  -> secundaria
     El gate de RS-01B usa la MEDIANA PAREADA (mediana de RMSD_dedup -
     RMSD_original por complejo) como estadistico primario; el bootstrap de
     RMSD de RS-01B debe usar esa mediana pareada.
  3. Manifest RS-01A: git_state y dependencies corregidos aparte (ver
     manifest.json; no se regenera aqui).
  4. Nota de sello en DESIGN.md (apart e; no se regenera aqui).

Recomputa (por composicion de run_rs01a_audit.py):
  - el contrafactual completo de los 31 empates (mismas funciones del runner:
    cargar_insumos, cargar_features, cargar_densas, densidad_historica,
    evaluar_brazo, recomputar_medoids, contrafactual_empates) y verifica
    contra lo almacenado en metrics.json;
  - los 4 estadisticos pareados desde per_complex.jsonl.
Si cualquier valor no coincide con el esperado, ABORTA sin escribir.

Determinismo: salidas sin timestamps ni aleatoriedad; dos corridas producen
metrics.json byte-identico.

Uso:
  python scripts/run_rs01a_corrigendum.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import numpy as np  # noqa: E402

import run_rs01a_audit as aud  # noqa: E402

RS01A = PROJECT_ROOT / "scripts" / "artifacts_science" / "RS-01A"
R_METRICS = RS01A / "metrics.json"
R_PER_COMPLEX = RS01A / "per_complex.jsonl"

# Valores EXACTOS esperados (corrigendum del maintainer)
BASE_TOP1_ESPERADO = 0.6379
ALTERNATIVAS_ESPERADAS = [0.6293, 0.6379, 0.6466]
N_ALTERNATIVAS_ESPERADAS = 31
N_CAMBIAN_GANADOR_ESPERADO = 7
N_CAMBIAN_HIT_ESPERADO = 2
PAR_DIF_MEDIANAS = 0.032   # 1.457 - 1.425 (medianas por brazo, bloque A1)
PAR_MEDIANA = 0.000
PAR_MEDIA = 0.0731
PAR_SUMA = 8.476


def recomputar_contrafactual():
    ins = aud.cargar_insumos()
    selector = aud.PoseSelector(
        str(aud.R_CHECKPOINT), str(aud.R_META),
        abstention_threshold=aud.UMBRAL_ABSTENCION)
    if selector.load_error is not None or selector.booster is None:
        raise SystemExit(f"ERROR: checkpoint: {selector.load_error}")
    meta = selector.meta
    indices_pct = [meta["feature_names_raw_224"].index(f) for f in aud.PCT_RAW]
    feats = aud.cargar_features(ins)
    densas = aud.cargar_densas(ins)
    labels = {l["identity"]: l for l in ins["labels"]}
    candidatos = {c["identity"]: c for c in ins["candidatos"]}
    ids_dedup = ins["dedup_ids"]
    ids_original = sorted(candidatos.keys(), key=aud.clave_identidad)
    pids = sorted({i.split("|")[1] for i in ids_original})

    dens_dedup = aud.densidad_historica(densas, ids_dedup)
    feats_dedup = {}
    for i in ids_dedup:
        fila = feats[i].copy()
        fila[8] = float(dens_dedup[i])
        feats_dedup[i] = fila
    res_dedup = aud.evaluar_brazo(selector, indices_pct, ids_dedup,
                                  feats_dedup, labels)
    recomputo = aud.recomputar_medoids(ins, candidatos)
    if not recomputo["verificacion"]["coincide_con_sellado"]:
        raise SystemExit("ERROR: recomputacion de medoids no coincide con el "
                         "sidecar sellado")
    cf = aud.contrafactual_empates(
        selector, indices_pct, feats, feats_dedup, densas, labels, ids_dedup,
        res_dedup["detalle_por_pid"], recomputo["clusters_cross"], pids)
    return res_dedup, cf


def recomputar_pareados():
    filas = [json.loads(l) for l in
             R_PER_COMPLEX.read_text(encoding="utf-8").splitlines() if l.strip()]
    if len(filas) != 116:
        raise SystemExit(f"ERROR: per_complex.jsonl con {len(filas)} filas")
    ro = np.array([f["a1_original"]["rmsd"] for f in filas], dtype=np.float64)
    rd = np.array([f["a1_dedup"]["rmsd"] for f in filas], dtype=np.float64)
    d = rd - ro
    return {
        "mediana_original": float(np.median(ro)),
        "mediana_dedup": float(np.median(rd)),
        "mediana_pareada": round(float(np.median(d)), 3),
        "media_pareada": round(float(np.mean(d)), 4),
        "suma_pareada": round(float(np.sum(d)), 3),
    }


def main() -> None:
    aud.configurar_salida()
    t0 = time.monotonic()
    print("== RS-01A CORRIGENDUM ==")

    m_prev = json.loads(R_METRICS.read_text(encoding="utf-8"))

    # ── recomputo del contrafactual ──
    res_dedup, cf = recomputar_contrafactual()
    resumen_cf = cf["resumen"]
    vals = sorted({a["top1_rate_global_alt"]
                   for c in cf["detalle_clusters"] for a in c["alternativas"]})
    assert resumen_cf["n_alternativas_evaluadas"] == N_ALTERNATIVAS_ESPERADAS
    assert resumen_cf["n_alternativas_cambian_ganador"] == N_CAMBIAN_GANADOR_ESPERADO
    assert resumen_cf["n_alternativas_cambian_hit"] == N_CAMBIAN_HIT_ESPERADO
    assert vals == ALTERNATIVAS_ESPERADAS, f"alternativas {vals}"
    assert res_dedup["top1_rate"] == BASE_TOP1_ESPERADO

    prev_cf = m_prev["empates_contrafactual"]
    assert prev_cf["resumen"]["n_alternativas_evaluadas"] == N_ALTERNATIVAS_ESPERADAS
    assert prev_cf["resumen"]["n_alternativas_cambian_ganador"] == N_CAMBIAN_GANADOR_ESPERADO
    assert prev_cf["resumen"]["n_alternativas_cambian_hit"] == N_CAMBIAN_HIT_ESPERADO
    prev_vals = sorted({a["top1_rate_global_alt"]
                        for c in prev_cf["detalle_clusters"]
                        for a in c["alternativas"]})
    assert prev_vals == ALTERNATIVAS_ESPERADAS, f"almacenadas {prev_vals}"
    assert prev_cf["detalle_clusters"] == cf["detalle_clusters"]
    print(f"  contrafactual recomputado: base {BASE_TOP1_ESPERADO} | "
          f"alternativas {ALTERNATIVAS_ESPERADAS} | {N_CAMBIAN_GANADOR_ESPERADO} "
          f"cambian ganador | {N_CAMBIAN_HIT_ESPERADO} cambian hit | identico al almacenado")

    # ── 4 estadisticos pareados desde per_complex.jsonl ──
    par = recomputar_pareados()
    dif_medianas = round(m_prev["a1"]["deduplicado"]["rmsd_mediana_ganador"]
                         - m_prev["a1"]["original"]["rmsd_mediana_ganador"], 3)
    assert dif_medianas == PAR_DIF_MEDIANAS, f"dif medianas {dif_medianas}"
    assert par["mediana_pareada"] == PAR_MEDIANA, par
    assert par["media_pareada"] == PAR_MEDIA, par
    assert par["suma_pareada"] == PAR_SUMA, par
    print(f"  pareados: dif_medianas {dif_medianas} | mediana_pareada "
          f"{par['mediana_pareada']} | media {par['media_pareada']} | "
          f"suma {par['suma_pareada']}")

    # ── aplica las correcciones sobre una copia fresca ──
    m = json.loads(R_METRICS.read_text(encoding="utf-8"))
    r = m["empates_contrafactual"]["resumen"]
    r["base_top1_global"] = BASE_TOP1_ESPERADO
    r["valores_top1_global_observados_alternativas"] = ALTERNATIVAS_ESPERADAS
    r["rango_top1_global_alternativas"] = {"min": ALTERNATIVAS_ESPERADAS[0],
                                           "max": ALTERNATIVAS_ESPERADAS[-1]}
    r["sensibilidad_desempate_fuente"] = True
    r["declaracion"] = ("el contrafactual muestra SENSIBILIDAD al desempate de "
                        "fuente (rango 0.6293-0.6466), NO invarianza")

    m["a1"]["pareado"]["estadisticos_pareados_rmsd"] = {
        "definicion": ("por complejo: d = rmsd_ganador_a1_dedup - "
                       "rmsd_ganador_a1_original (recalculado desde "
                       "per_complex.jsonl, rmsd a 4 decimales)"),
        "diferencia_de_medianas": {
            "valor": 0.032,
            "calculo": "1.457 - 1.425 (medianas por brazo del bloque A1)",
            "rol": "NO usar como estadistico primario",
        },
        "mediana_diferencias_pareadas": {
            "valor": 0.0,
            "rol": ("PRIMARIO: el gate de RS-01B (degradacion mediana <= 0.1 A) "
                    "usa la MEDIANA de diferencias pareadas; el bootstrap de "
                    "RMSD de RS-01B debe usar ESTE estadistico"),
        },
        "media_diferencias_pareadas": {"valor": 0.0731, "rol": "descriptivo"},
        "suma_diferencias_pareadas": {"valor": 8.476,
                                      "rol": "SECUNDARIA (puede conservarse)"},
    }
    m["a1"]["pareado"]["bootstrap_bc"]["nota_corrigendum"] = (
        "estadistico usado aqui: suma de diferencias pareadas (SECUNDARIA); "
        "el estadistico PRIMARIO de RS-01B es la MEDIANA de diferencias "
        "pareadas de RMSD del ganador")
    m["corrigendum"] = {
        "autor": "maintainer (corrigendum RS-01A)",
        "correcciones": [
            {"id": 1, "titulo": "contrafactual NO invariante",
             "detalle": ("base 0.6379; alternativas observadas 0.6293, 0.6379, "
                         "0.6466 (7 cambian ganador, 2 cambian hit); sensibilidad "
                         "al desempate de fuente, rango 0.6293-0.6466")},
            {"id": 2, "titulo": "estadisticos pareados distinguidos",
             "detalle": ("diferencia de medianas +0.032; mediana pareada 0.000 "
                         "(PRIMARIA); media pareada +0.0731; suma pareada +8.476 "
                         "(secundaria); RS-01B usa la mediana pareada como "
                         "estadistico primario")},
            {"id": 3, "titulo": "manifest RS-01A",
             "detalle": "git_state (branch/commit/dirty) y dependencies (runtime real) corregidos en manifest.json"},
            {"id": 4, "titulo": "nota de sello",
             "detalle": ("DESIGN.md documenta que el sello de RS-01A incluira "
                         "como datasets los 116 records/{pid}.json + runner, "
                         "checkpoint, entradas y resultados")},
        ],
    }

    with open(R_METRICS, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(m, ensure_ascii=False, indent=2) + "\n")

    print(f"  metrics.json corregido ({time.monotonic() - t0:.1f}s)")


if __name__ == "__main__":
    main()
