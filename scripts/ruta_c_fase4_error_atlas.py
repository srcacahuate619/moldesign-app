# -*- coding: utf-8 -*-
"""Atlas de errores reproducible para Ruta C (no modifica produccion).

El selector v0.6 ya es el campeon operativo de Ruta C, pero su 0.6596
Top-1 en los 47 complejos de desarrollo todavia queda por debajo de la meta
global de 0.70. Este script responde una pregunta anterior a entrenar otro
modelo: de cada fallo, ¿existia una pose <= 2 A que el ranking pudiera haber
recuperado?

Usa exclusivamente el dataset congelado y el artefacto v0.6 ya publicado.
No reentrena, no sobrescribe modelos y rehusa sobrescribir su salida salvo
que se solicite de forma explicita. El "test" empleado aqui ya participo en
iteraciones anteriores; por ello el resultado se etiqueta como *desarrollo*,
no como confirmacion ciega de una mejora futura.

Salida por defecto:
    scripts/artifacts_ruta_c_fase4_error_atlas.json

Uso:
    python scripts/ruta_c_fase4_error_atlas.py
    python scripts/ruta_c_fase4_error_atlas.py --output ruta.json
    python scripts/ruta_c_fase4_error_atlas.py --overwrite
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
DATASET_DIR = PROJECT_ROOT / "data" / "pose_selector_dataset"
MODEL_PATH = PROJECT_ROOT / "rescoring" / "artifacts" / "pose_selector_v06.xgb"
MODEL_META_PATH = PROJECT_ROOT / "rescoring" / "artifacts" / "pose_selector_v06_meta.json"
DEFAULT_OUTPUT = SCRIPTS_DIR / "artifacts_ruta_c_fase4_error_atlas.json"
UMBRAL_POSITIVA = 2.0
TOP1_V06_REFERENCIA = 0.6596

sys.path.insert(0, str(SCRIPTS_DIR))
import ruta_c_fase1_6_v06 as v06  # noqa: E402


def ahora_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def sha256_archivo(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for bloque in iter(lambda: fh.read(1 << 20), b""):
            digest.update(bloque)
    return digest.hexdigest()


def wilson_95(exitos: int, total: int) -> dict[str, float] | None:
    """Intervalo Wilson bilateral 95 %, preferible a p +/- 1.96*SE con n=47."""
    if total <= 0:
        return None
    z = 1.959963984540054
    p = exitos / total
    denom = 1.0 + z * z / total
    centro = (p + z * z / (2.0 * total)) / denom
    radio = z * np.sqrt((p * (1.0 - p) + z * z / (4.0 * total)) / total) / denom
    return {"lower": round(float(centro - radio), 4),
            "upper": round(float(centro + radio), 4)}


def valor_redondeado(valor: object) -> float | int | None:
    if valor is None:
        return None
    try:
        valor_float = float(valor)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(valor_float):
        return None
    return round(valor_float, 4)


def resumen_pose(registro: dict, raw: np.ndarray, score: float, rank: int) -> dict:
    """Expone solo las señales base interpretables; las 215 ricas siguen en cache."""
    indices = {nombre: v06.FEATURES_TOTAL.index(nombre) for nombre in v06.FEATURES_V0}
    return {
        "rank_selector": rank,
        "rmsd": valor_redondeado(registro["rmsd"]),
        "crystal_like": bool(float(registro["rmsd"]) <= UMBRAL_POSITIVA),
        "selector_score": round(float(score), 6),
        "source": registro["source"],
        "model_idx": int(registro["model_idx"]),
        "features_base": {
            nombre: valor_redondeado(raw[indices[nombre]])
            for nombre in v06.FEATURES_V0
        },
    }


def clasificar_caso(tiene_pose_buena: bool, top1_ok: bool, margen: float) -> str:
    if not tiene_pose_buena:
        return "generacion_sin_pose_cristalina"
    if top1_ok:
        return "seleccion_correcta"
    if margen < 0.097663:
        return "fallo_ranking_recuperable_margen_bajo"
    return "fallo_ranking_recuperable_margen_alto"


def cargar_y_puntuar() -> tuple[list[dict], np.ndarray, np.ndarray]:
    """Reconstruye exactamente X_B v0.6 y lo puntua con el booster publicado."""
    if not MODEL_PATH.is_file() or not MODEL_META_PATH.is_file():
        raise RuntimeError("faltan el modelo o metadata v0.6 de produccion")

    splits = {nombre: v06.cargar_split(nombre) for nombre in ("train", "val", "test")}
    grupos = {nombre: v06.grupos_por_pid(registros)[0]
              for nombre, registros in splits.items()}
    raw = v06.construir_X_raw(splits)
    preparados = v06.preparar_modelos(raw, grupos)

    import xgboost

    booster = xgboost.Booster()
    booster.load_model(str(MODEL_PATH))
    scores = np.asarray(
        booster.predict(xgboost.DMatrix(preparados["test"]["B"])), dtype=np.float64
    )
    if len(scores) != len(splits["test"]):
        raise RuntimeError("el booster devolvio un numero de scores inesperado")
    return splits["test"], raw["test"], scores


def analizar(registros: list[dict], raw: np.ndarray, scores: np.ndarray) -> dict:
    por_pid: dict[str, list[tuple[int, dict, np.ndarray, float]]] = defaultdict(list)
    for indice, (registro, raw_fila, score) in enumerate(zip(registros, raw, scores)):
        por_pid[registro["pid"]].append((indice, registro, raw_fila, float(score)))

    detalles: list[dict] = []
    for pid in sorted(por_pid):
        filas = por_pid[pid]
        orden_selector = sorted(filas, key=lambda fila: (-fila[3], fila[0]))
        orden_vina = sorted(filas, key=lambda fila: (float(fila[1]["vina_score"]), fila[0]))
        top = orden_selector[0]
        vina_top = orden_vina[0]
        buenas = [fila for fila in orden_selector if float(fila[1]["rmsd"]) <= UMBRAL_POSITIVA]
        tiene_pose_buena = bool(buenas)
        mejor_buena = min(buenas, key=lambda fila: (float(fila[1]["rmsd"]), fila[0])) if buenas else None
        rank_mejor_buena = (orden_selector.index(mejor_buena) + 1) if mejor_buena else None
        top1_ok = float(top[1]["rmsd"]) <= UMBRAL_POSITIVA
        vina_ok = float(vina_top[1]["rmsd"]) <= UMBRAL_POSITIVA
        margen = float(orden_selector[0][3] - orden_selector[1][3]) if len(orden_selector) > 1 else 0.0
        caso = clasificar_caso(tiene_pose_buena, top1_ok, margen)
        detalle = {
            "pid": pid,
            "n_poses": len(filas),
            "min_rmsd": round(min(float(f[1]["rmsd"]) for f in filas), 4),
            "tiene_pose_cristalina": tiene_pose_buena,
            "top1_ok": top1_ok,
            "vina_top1_ok": vina_ok,
            "margin_top1_top2": round(margen, 6),
            "caso": caso,
            "top_selector": resumen_pose(top[1], top[2], top[3], 1),
            "top_vina": resumen_pose(vina_top[1], vina_top[2], vina_top[3], 1),
            "mejor_pose_cristalina": (
                resumen_pose(mejor_buena[1], mejor_buena[2], mejor_buena[3], rank_mejor_buena)
                if mejor_buena else None
            ),
        }
        detalles.append(detalle)

    conteos = defaultdict(int)
    for detalle in detalles:
        conteos[detalle["caso"]] += 1
    fallos_recuperables = [d for d in detalles if d["caso"].startswith("fallo_ranking")]
    cambios_vina = {
        "v06_recupera_fallo_vina": sum(d["top1_ok"] and not d["vina_top1_ok"] for d in detalles),
        "v06_empeora_acierto_vina": sum(not d["top1_ok"] and d["vina_top1_ok"] for d in detalles),
        "ambos_aciertan": sum(d["top1_ok"] and d["vina_top1_ok"] for d in detalles),
        "ambos_fallan": sum(not d["top1_ok"] and not d["vina_top1_ok"] for d in detalles),
    }
    n = len(detalles)
    aciertos = sum(d["top1_ok"] for d in detalles)
    candidatos = sum(d["tiene_pose_cristalina"] for d in detalles)
    necesarios_para_070 = max(0, int(np.ceil(0.70 * n)) - aciertos)
    return {
        "resumen": {
            "n_complejos": n,
            "top1_v06": round(aciertos / n, 4),
            "top1_v06_exitos": aciertos,
            "intervalo_wilson_95_top1": wilson_95(aciertos, n),
            "techo_por_generacion": round(candidatos / n, 4),
            "techo_por_generacion_exitos": candidatos,
            "fallos_ranking_recuperables": len(fallos_recuperables),
            "fallos_sin_pose_cristalina": conteos["generacion_sin_pose_cristalina"],
            "casos_necesarios_para_top1_global_070": necesarios_para_070,
            "top1_si_se_recuperan_esos_casos": round((aciertos + necesarios_para_070) / n, 4),
            "casos_por_tipo": dict(sorted(conteos.items())),
            "comparacion_v06_vs_vina": cambios_vina,
        },
        "fallos_recuperables": fallos_recuperables,
        "fallos_sin_pose_cristalina": [
            d for d in detalles if d["caso"] == "generacion_sin_pose_cristalina"
        ],
        "todos_los_complejos": detalles,
    }


def guardar_atomico(path: Path, artefacto: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporal = path.with_suffix(path.suffix + ".tmp")
    temporal.write_text(json.dumps(artefacto, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporal, path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--overwrite", action="store_true",
                        help="permite sustituir una salida anterior de este mismo atlas")
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else PROJECT_ROOT / args.output
    if output.exists() and not args.overwrite:
        raise SystemExit(f"la salida ya existe: {output} (use --overwrite para sustituirla)")

    registros, raw, scores = cargar_y_puntuar()
    resultado = analizar(registros, raw, scores)
    top1 = resultado["resumen"]["top1_v06"]
    if abs(top1 - TOP1_V06_REFERENCIA) > 0.0001:
        raise RuntimeError(
            f"reproduccion v0.6 inesperada: {top1} != {TOP1_V06_REFERENCIA}; se aborta"
        )

    manifest = json.loads((DATASET_DIR / "manifest.json").read_text(encoding="utf-8"))
    artefacto = {
        "generated_at": ahora_iso(),
        "protocolo_base": "docs/42_RUTA_C_PROTOCOLO.md",
        "continuidad_investigacion": "docs/41_RUTA_C_INVESTIGACION_CAMPO.md",
        "fase": "4.A — atlas de errores y techo recuperable",
        "hipotesis": (
            "un objetivo global >=0.70 es alcanzable solo si al menos dos de los "
            "fallos con pose cristalina existente se recuperan sin degradar los aciertos"
        ),
        "alcance": "diagnostico read-only; no se reentrena ni se promueve ningun modelo",
        "validez": {
            "nombre_split": "test de desarrollo historico",
            "advertencia": (
                "este split fue consultado en iteraciones anteriores de Ruta C; no debe "
                "usarse como confirmacion ciega de un nuevo modelo. La seleccion de la "
                "siguiente hipotesis se hara con train/val y requerira confirmacion nueva."
            ),
        },
        "integridad": {
            "dataset_manifest_sha256": manifest.get("sha256"),
            "poses_test_sha256": manifest.get("sha256", {}).get("poses_test.jsonl"),
            "modelo_v06_sha256": sha256_archivo(MODEL_PATH),
            "modelo_meta_sha256": sha256_archivo(MODEL_META_PATH),
        },
        **resultado,
    }
    guardar_atomico(output, artefacto)
    resumen = artefacto["resumen"]
    print(f"Atlas guardado: {output}")
    print(f"v0.6 Top-1: {resumen['top1_v06_exitos']}/{resumen['n_complejos']} = {resumen['top1_v06']}")
    print(f"Techo por generacion: {resumen['techo_por_generacion_exitos']}/{resumen['n_complejos']} = {resumen['techo_por_generacion']}")
    print(f"Fallos recuperables por ranking: {resumen['fallos_ranking_recuperables']}")
    print(f"Casos necesarios para >=0.70: {resumen['casos_necesarios_para_top1_global_070']}")


if __name__ == "__main__":
    main()
