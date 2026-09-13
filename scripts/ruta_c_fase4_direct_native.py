# -*- coding: utf-8 -*-
"""Ruta C Fase 4.B — prueba preregistrada de objetivo nativo directo.

Ver docs/47_RUTA_C_FASE4_PREREGISTRO.md. Este script carga SOLO train y val;
no abre el test de desarrollo historico. No reentrena ni reemplaza v0.6.

Uso:
    python scripts/ruta_c_fase4_direct_native.py
    python scripts/ruta_c_fase4_direct_native.py --output ruta.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
DATASET_DIR = PROJECT_ROOT / "data" / "pose_selector_dataset"
V06_MODEL = PROJECT_ROOT / "rescoring" / "artifacts" / "pose_selector_v06.xgb"
V06_META = PROJECT_ROOT / "rescoring" / "artifacts" / "pose_selector_v06_meta.json"
DEFAULT_OUTPUT = SCRIPTS_DIR / "artifacts_ruta_c_fase4_direct_native.json"
SEED = 42
N_FOLDS = 5
UMBRAL_POSITIVA = 2.0
N_ESTIMATORS = 52
PARAMS = {
    "n_estimators": N_ESTIMATORS,
    "max_depth": 6,
    "learning_rate": 0.05,
    "subsample": 0.8,
    "n_jobs": 4,
    "seed": SEED,
    "random_state": SEED,
}
MODEL_ORDER = ("continuo_pairwise", "native_pairwise", "native_ndcg")

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


def cargar_registros(nombre: str) -> list[dict]:
    return v06.cargar_split(nombre)


def preparar_233(registros: list[dict], raw: np.ndarray) -> tuple[np.ndarray, list[int], list[str]]:
    grupos, pids = v06.grupos_por_pid(registros)
    z = v06.z_por_pid(raw, grupos)
    z[np.isnan(z)] = 0.0
    pct = v06.pct_por_pid(raw, grupos, v06.PCT_INDICES)
    pct[np.isnan(pct)] = 0.0
    x = np.hstack((z, pct))
    if x.shape != (len(registros), 233):
        raise RuntimeError(f"matriz 233 inesperada: {x.shape}")
    return x, grupos, pids


def indice_por_pid(registros: list[dict]) -> dict[str, list[int]]:
    resultado: dict[str, list[int]] = defaultdict(list)
    for indice, registro in enumerate(registros):
        resultado[registro["pid"]].append(indice)
    return dict(resultado)


def folds_estratificados(registros: list[dict]) -> list[list[str]]:
    """Cinco folds por complejo, equilibrando si contiene alguna pose positiva."""
    por_pid = indice_por_pid(registros)
    positivos, negativos = [], []
    for pid in sorted(por_pid):
        tiene = any(float(registros[i]["rmsd"]) <= UMBRAL_POSITIVA for i in por_pid[pid])
        (positivos if tiene else negativos).append(pid)
    generador = np.random.default_rng(SEED)
    generador.shuffle(positivos)
    generador.shuffle(negativos)
    folds = [[] for _ in range(N_FOLDS)]
    for grupo in (positivos, negativos):
        for i, pid in enumerate(grupo):
            folds[i % N_FOLDS].append(pid)
    for fold in folds:
        fold.sort()
    if any(not fold for fold in folds):
        raise RuntimeError("un fold quedo vacio")
    return folds


def indices_de_pids(por_pid: dict[str, list[int]], pids: list[str]) -> list[int]:
    return [indice for pid in pids for indice in por_pid[pid]]


def grupos_de_registros(registros: list[dict], indices: list[int]) -> list[int]:
    pids = [registros[i]["pid"] for i in indices]
    grupos: list[int] = []
    previo = None
    contador = 0
    for pid in pids:
        if previo is not None and pid != previo:
            grupos.append(contador)
            contador = 0
        previo = pid
        contador += 1
    if contador:
        grupos.append(contador)
    return grupos


def etiquetas(registros: list[dict], indices: list[int], modelo: str) -> np.ndarray:
    rmsd = np.array([float(registros[i]["rmsd"]) for i in indices], dtype=np.float64)
    if modelo == "continuo_pairwise":
        return -rmsd
    return (rmsd <= UMBRAL_POSITIVA).astype(np.float64)


def entrenar_y_predecir(modelo: str, x_train: np.ndarray, y_train: np.ndarray,
                        grupos_train: list[int], x_eval: np.ndarray) -> np.ndarray:
    from xgboost import XGBRanker

    if modelo == "continuo_pairwise":
        estimador = XGBRanker(objective="rank:pairwise", **PARAMS)
    elif modelo == "native_pairwise":
        estimador = XGBRanker(objective="rank:pairwise", **PARAMS)
    elif modelo == "native_ndcg":
        estimador = XGBRanker(objective="rank:ndcg", **PARAMS)
    else:
        raise ValueError(f"modelo desconocido: {modelo}")
    estimador.fit(x_train, y_train, group=grupos_train, verbose=False)
    return np.asarray(estimador.predict(x_eval), dtype=np.float64)


def metricas_por_complejo(registros: list[dict], scores: np.ndarray) -> tuple[dict, dict[str, bool]]:
    por_pid = indice_por_pid(registros)
    seleccion: dict[str, bool] = {}
    rmsds, spearmans = [], []
    con_candidato, aciertos_con_candidato = 0, 0
    for pid in sorted(por_pid):
        indices = por_pid[pid]
        orden = sorted(indices, key=lambda i: (-float(scores[i]), i))
        top = orden[0]
        top_ok = float(registros[top]["rmsd"]) <= UMBRAL_POSITIVA
        seleccion[pid] = top_ok
        rmsds.append(float(registros[top]["rmsd"]))
        tiene = any(float(registros[i]["rmsd"]) <= UMBRAL_POSITIVA for i in indices)
        if tiene:
            con_candidato += 1
            aciertos_con_candidato += int(top_ok)
        if len(indices) >= 2:
            from scipy.stats import spearmanr
            rmsd = np.array([float(registros[i]["rmsd"]) for i in indices])
            pred = np.array([float(scores[i]) for i in indices])
            if np.std(rmsd) > 0 and np.std(pred) > 0:
                valor = spearmanr(pred, rmsd).correlation
                if valor is not None and np.isfinite(valor):
                    spearmans.append(float(valor))
    n = len(por_pid)
    aciertos = sum(seleccion.values())
    return {
        "n_complejos": n,
        "top1_exitos": aciertos,
        "top1_global": round(aciertos / n, 4),
        "top1_con_candidato_exitos": aciertos_con_candidato,
        "top1_con_candidato_n": con_candidato,
        "top1_con_candidato": round(aciertos_con_candidato / con_candidato, 4) if con_candidato else None,
        "rmsd_mediana": round(float(np.median(rmsds)), 4),
        "spearman_media": round(float(np.mean(spearmans)), 4) if spearmans else None,
    }, seleccion


def p_binomial_dos_lados(exitos: int, total: int) -> float | None:
    """Prueba exacta de signos/McNemar para los desacuerdos pareados."""
    if total == 0:
        return None
    menor = min(exitos, total - exitos)
    acumulada = sum(math.comb(total, k) for k in range(menor + 1)) / (2 ** total)
    return round(float(min(1.0, 2.0 * acumulada)), 6)


def comparacion_pareada(control: dict[str, bool], candidato: dict[str, bool]) -> dict:
    recupera = sum(not control[pid] and candidato[pid] for pid in control)
    degrada = sum(control[pid] and not candidato[pid] for pid in control)
    return {
        "candidato_recupera_control_falla": recupera,
        "candidato_degrada_control_acierta": degrada,
        "neto_aciertos": recupera - degrada,
        "n_desacuerdos": recupera + degrada,
        "p_mcnemar_exacto_dos_lados": p_binomial_dos_lados(recupera, recupera + degrada),
    }


def ejecutar_oof(registros: list[dict], x: np.ndarray) -> tuple[dict, list[dict]]:
    por_pid = indice_por_pid(registros)
    folds = folds_estratificados(registros)
    scores = {modelo: np.full(len(registros), np.nan, dtype=np.float64) for modelo in MODEL_ORDER}
    descripcion_folds: list[dict] = []
    todos_pids = sorted(por_pid)
    for n_fold, pids_eval in enumerate(folds):
        pids_train = [pid for pid in todos_pids if pid not in set(pids_eval)]
        i_train = indices_de_pids(por_pid, pids_train)
        i_eval = indices_de_pids(por_pid, pids_eval)
        g_train = grupos_de_registros(registros, i_train)
        positivos_eval = sum(any(float(registros[i]["rmsd"]) <= UMBRAL_POSITIVA
                                 for i in por_pid[pid]) for pid in pids_eval)
        descripcion_folds.append({
            "fold": n_fold,
            "n_train_complejos": len(pids_train),
            "n_eval_complejos": len(pids_eval),
            "n_eval_con_candidato_cristalino": positivos_eval,
            "pids_eval": pids_eval,
        })
        for modelo in MODEL_ORDER:
            y_train = etiquetas(registros, i_train, modelo)
            scores[modelo][i_eval] = entrenar_y_predecir(
                modelo, x[i_train], y_train, g_train, x[i_eval]
            )
    if any(np.isnan(valor).any() for valor in scores.values()):
        raise RuntimeError("OOF incompleto")
    return scores, descripcion_folds


def ganador_oof(metricas: dict[str, dict], selecciones: dict[str, dict[str, bool]]) -> dict:
    control = metricas["continuo_pairwise"]
    candidatos = []
    for modelo in ("native_pairwise", "native_ndcg"):
        par = comparacion_pareada(selecciones["continuo_pairwise"], selecciones[modelo])
        mediana_ok = metricas[modelo]["rmsd_mediana"] <= control["rmsd_mediana"] + 0.10
        pasa = par["neto_aciertos"] >= 3 and mediana_ok
        candidatos.append({"modelo": modelo, "pareado_vs_control": par,
                           "mediana_ok": mediana_ok, "pasa_gate_oof": pasa})
    orden = sorted(candidatos, key=lambda x: (
        not x["pasa_gate_oof"],
        -metricas[x["modelo"]]["top1_exitos"],
        metricas[x["modelo"]]["rmsd_mediana"],
        -(metricas[x["modelo"]]["spearman_media"] or -np.inf),
        x["modelo"],
    ))
    elegido = orden[0]
    return {"candidatos": candidatos, "ganador": elegido["modelo"],
            "gate_oof_superado": elegido["pasa_gate_oof"]}


def guardar_atomico(path: Path, artefacto: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporal = path.with_suffix(path.suffix + ".tmp")
    temporal.write_text(json.dumps(artefacto, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporal, path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else PROJECT_ROOT / args.output
    if output.exists() and not args.overwrite:
        raise SystemExit(f"la salida ya existe: {output} (use --overwrite para sustituirla)")

    train = cargar_registros("train")
    val = cargar_registros("val")
    raw = v06.construir_X_raw({"train": train, "val": val})
    x_train, _, _ = preparar_233(train, raw["train"])
    x_val, _, _ = preparar_233(val, raw["val"])

    scores_oof, folds = ejecutar_oof(train, x_train)
    metricas_oof, selecciones_oof = {}, {}
    for modelo in MODEL_ORDER:
        metricas_oof[modelo], selecciones_oof[modelo] = metricas_por_complejo(train, scores_oof[modelo])
    decision = ganador_oof(metricas_oof, selecciones_oof)

    val_resultado = {"ejecutado": False,
                     "motivo": "ningun objetivo nativo supero el gate OOF preregistrado"}
    if decision["gate_oof_superado"]:
        modelo = decision["ganador"]
        indices_train = list(range(len(train)))
        pred_val = entrenar_y_predecir(
            modelo, x_train, etiquetas(train, indices_train, modelo),
            v06.grupos_por_pid(train)[0], x_val,
        )
        metrica_val, _ = metricas_por_complejo(val, pred_val)
        pasa_val = metrica_val["top1_exitos"] >= 25
        val_resultado = {
            "ejecutado": True,
            "modelo": modelo,
            "metricas": metrica_val,
            "referencia_v06_historica_top1": 0.575,
            "referencia_v06_historica_exitos": 23,
            "gate": "al menos 25/40 Top-1",
            "pasa_gate_val": pasa_val,
        }

    artefacto = {
        "generated_at": ahora_iso(),
        "protocolo": "docs/47_RUTA_C_FASE4_PREREGISTRO.md",
        "fase": "4.B — objetivo nativo directo, seleccion sin test historico",
        "hipotesis": "H-C1.1: optimizar RMSD <=2 Å directamente mejora Top-1 global",
        "integridad": {
            "poses_train_sha256": sha256_archivo(DATASET_DIR / "poses_train.jsonl"),
            "poses_val_sha256": sha256_archivo(DATASET_DIR / "poses_val.jsonl"),
            "v06_modelo_sha256": sha256_archivo(V06_MODEL),
            "v06_meta_sha256": sha256_archivo(V06_META),
            "test_historico_leido": False,
        },
        "config_congelada": {"seed": SEED, "n_folds": N_FOLDS,
                              "umbral_positiva_ang": UMBRAL_POSITIVA,
                              "params": PARAMS, "modelos": list(MODEL_ORDER)},
        "folds": folds,
        "oof": {"metricas": metricas_oof, "decision": decision},
        "validacion_val": val_resultado,
        "conclusion": (
            "La hipotesis avanza a confirmacion en val" if val_resultado.get("pasa_gate_val")
            else "La hipotesis no avanza; v0.6 permanece sin cambios"
        ),
        "no_promocion_automatica": True,
    }
    guardar_atomico(output, artefacto)
    print(f"Artefacto guardado: {output}")
    for modelo in MODEL_ORDER:
        m = metricas_oof[modelo]
        print(f"OOF {modelo}: {m['top1_exitos']}/{m['n_complejos']} = {m['top1_global']} | mediana {m['rmsd_mediana']}")
    print(f"Ganador OOF: {decision['ganador']} | gate: {decision['gate_oof_superado']}")
    print(f"Val ejecutado: {val_resultado['ejecutado']}")


if __name__ == "__main__":
    main()
