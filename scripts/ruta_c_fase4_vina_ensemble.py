# -*- coding: utf-8 -*-
"""Ruta C Fase 4.C — ensamble preregistrado de rangos v0.6/Vina.

Ver docs/47_RUTA_C_FASE4_PREREGISTRO.md. Trabaja exclusivamente con train y,
si el gate OOF pasa, con val. Nunca abre el test de desarrollo historico.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
DATASET_DIR = PROJECT_ROOT / "data" / "pose_selector_dataset"
DEFAULT_OUTPUT = SCRIPTS_DIR / "artifacts_ruta_c_fase4_vina_ensemble.json"
ALPHAS = (0.00, 0.25, 0.50, 0.75, 1.00)

sys.path.insert(0, str(SCRIPTS_DIR))
import ruta_c_fase4_direct_native as direct  # noqa: E402


def ahora_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def sha256_archivo(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for bloque in iter(lambda: fh.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def scores_ensamble(registros: list[dict], scores_modelo: np.ndarray, alpha: float) -> np.ndarray:
    """Rangos 0..1 por complejo: 1 es mejor; desempate por indice canonico."""
    por_pid = direct.indice_por_pid(registros)
    salida = np.zeros(len(registros), dtype=np.float64)
    for pid in sorted(por_pid):
        indices = por_pid[pid]
        n = len(indices)
        orden_modelo = sorted(indices, key=lambda i: (-float(scores_modelo[i]), i))
        orden_vina = sorted(indices, key=lambda i: (float(registros[i]["vina_score"]), i))
        rango_modelo = {i: 1.0 - pos / max(1, n - 1) for pos, i in enumerate(orden_modelo)}
        rango_vina = {i: 1.0 - pos / max(1, n - 1) for pos, i in enumerate(orden_vina)}
        for i in indices:
            salida[i] = alpha * rango_modelo[i] + (1.0 - alpha) * rango_vina[i]
    return salida


def guardar_atomico(path: Path, artefacto: dict) -> None:
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

    train = direct.cargar_registros("train")
    val = direct.cargar_registros("val")
    raw = direct.v06.construir_X_raw({"train": train, "val": val})
    x_train, _, _ = direct.preparar_233(train, raw["train"])
    x_val, _, _ = direct.preparar_233(val, raw["val"])
    oof_scores, folds = direct.ejecutar_oof(train, x_train)
    base_oof = oof_scores["continuo_pairwise"]

    metricas, selecciones = {}, {}
    for alpha in ALPHAS:
        clave = f"alpha_{alpha:.2f}"
        metricas[clave], selecciones[clave] = direct.metricas_por_complejo(
            train, scores_ensamble(train, base_oof, alpha)
        )
    control = "alpha_1.00"
    candidatos = []
    for alpha in ALPHAS[:-1]:
        clave = f"alpha_{alpha:.2f}"
        pareado = direct.comparacion_pareada(selecciones[control], selecciones[clave])
        mediana_ok = metricas[clave]["rmsd_mediana"] <= metricas[control]["rmsd_mediana"] + 0.10
        candidatos.append({"alpha": alpha, "clave": clave, "pareado_vs_v06": pareado,
                           "mediana_ok": mediana_ok,
                           "pasa_gate_oof": pareado["neto_aciertos"] >= 3 and mediana_ok})
    candidatos.sort(key=lambda c: (not c["pasa_gate_oof"], -metricas[c["clave"]]["top1_exitos"],
                                    metricas[c["clave"]]["rmsd_mediana"], -c["alpha"]))
    elegido = candidatos[0]

    validacion = {"ejecutado": False, "motivo": "ningun peso supero el gate OOF"}
    if elegido["pasa_gate_oof"]:
        indices_train = list(range(len(train)))
        pred_val = direct.entrenar_y_predecir(
            "continuo_pairwise", x_train,
            direct.etiquetas(train, indices_train, "continuo_pairwise"),
            direct.v06.grupos_por_pid(train)[0], x_val,
        )
        m_val, _ = direct.metricas_por_complejo(val, scores_ensamble(val, pred_val, elegido["alpha"]))
        validacion = {"ejecutado": True, "alpha": elegido["alpha"], "metricas": m_val,
                      "gate": "al menos 25/40 Top-1", "pasa_gate_val": m_val["top1_exitos"] >= 25}

    artefacto = {
        "generated_at": ahora_iso(), "protocolo": "docs/47_RUTA_C_FASE4_PREREGISTRO.md",
        "fase": "4.C — ensamble v0.6/Vina", "hipotesis": "H-C4.1",
        "integridad": {"poses_train_sha256": sha256_archivo(DATASET_DIR / "poses_train.jsonl"),
                       "poses_val_sha256": sha256_archivo(DATASET_DIR / "poses_val.jsonl"),
                       "test_historico_leido": False},
        "config_congelada": {"alphas": list(ALPHAS), "source_scores": "OOF continuo_pairwise H-C1.1"},
        "folds": folds, "oof": {"metricas": metricas, "candidatos": candidatos, "elegido": elegido},
        "validacion_val": validacion, "no_promocion_automatica": True,
        "conclusion": "pendiente de gate" if validacion["ejecutado"] else "H-C4.1 no avanza; v0.6 permanece sin cambios",
    }
    guardar_atomico(output, artefacto)
    print(f"Artefacto guardado: {output}")
    for clave, metrica in metricas.items():
        print(f"{clave}: {metrica['top1_exitos']}/{metrica['n_complejos']} = {metrica['top1_global']} | mediana {metrica['rmsd_mediana']}")
    print(f"Elegido: alpha={elegido['alpha']} | gate OOF={elegido['pasa_gate_oof']} | val={validacion['ejecutado']}")


if __name__ == "__main__":
    main()
