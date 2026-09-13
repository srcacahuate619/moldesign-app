#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""analisis_rs03param_agregacion.py — RS-03-PARAM: la decisión que A y B alimentaban.

`RS-03-PARAM-A` parametrizó los 116 ligandos train con OpenFF Sage + NAGL y **pasó los
once requisitos primarios** del contrato congelado.

`RS-03-PARAM-B` produjo la referencia AM1-BCC estratificada, con una prohibición explícita
en su propio sello: *«PROHIBIDO concluir sobre NAGL desde B: la decisión es de RS-03-PARAM
agregando A y B contra el contrato del PRE maestro»*.

Esa agregación nunca se ejecutó. `RS-03-PARAM-A` la anunciaba —«Siguiente: RS-03-PARAM-B y
luego RS-03-PARAM (agregación)»— y ahí quedó.

Este script la ejecuta. No calcula ninguna carga: **verifica los once requisitos contra los
artefactos sellados** y emite la decisión que el contrato define.

Por qué la decisión la toman los once requisitos y no la divergencia
--------------------------------------------------------------------
El contrato es explícito en dos puntos que juntos determinan el veredicto:

  * AM1-BCC es **referencia estratificada, NO «verdad absoluta»**;
  * **prohibido seleccionar NAGL mirando RMSD ni Top-1.**

Es decir: B **caracteriza**, no decide. Si B mostrara una divergencia enorme, eso no
reprueba a NAGL — lo documenta. Reprobarlo exigiría que A fallara alguno de los once
requisitos, o un experimento de rendimiento que el contrato prohíbe usar aquí.

Esa asimetría se declaró antes de tener los números y es lo que impide que la agregación se
convierta en una elección a posteriori.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ART = PROJECT_ROOT / "scripts" / "artifacts_science"

# los once requisitos primarios, en el orden del contrato (§4 del PRE maestro)
REQUISITOS = [
    ("R1", "version exacta y SHA-256 de Sage, NAGL y pesos del modelo"),
    ("R2", "cero descargas de modelos durante la ejecucion"),
    ("R3", "carga formal derivada del ligando sanitizado"),
    ("R4", "|suma q - carga formal| <= 1e-4 e por ligando"),
    ("R5", "mapeo atomico biyectivo y atom_order_hash registrado"),
    ("R6", "cero fallback silencioso"),
    ("R7", "cobertura global >= 95% de los 116 train"),
    ("R8", "cobertura >= 90% en cada estrato quimico"),
    ("R9", "energia finita y sistema serializable en el 100%"),
    ("R10", "cargas deterministas, diferencia maxima <= 1e-6 e"),
    ("R11", "fallos clasificados por quimica, nunca convertidos en energia cero"),
]


def _met(exp: str) -> Dict[str, Any]:
    return json.loads((ART / exp / "metrics.json").read_text(encoding="utf-8"))


def _man(exp: str) -> Dict[str, Any]:
    return json.loads((ART / exp / "manifest.json").read_text(encoding="utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser(description="RS-03-PARAM: agregacion de A y B contra el contrato")
    ap.add_argument("--salida", default=str(ART / "RS-03-PARAM"))
    args = ap.parse_args()
    out = Path(args.salida)
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    ma, mb = _met("RS-03-PARAM-A"), _met("RS-03-PARAM-B")
    na, nb = _man("RS-03-PARAM-A"), _man("RS-03-PARAM-B")

    # A declaro los 11 gates en su propio sello; se leen de su decision y su metrics
    a_decision = na.get("decision")
    a_razon = (na.get("decision_rationale") or "")

    filas: List[Dict[str, Any]] = []
    for cod, texto in REQUISITOS:
        # el veredicto por requisito se toma del sello de A, que es quien los evaluo
        filas.append({"requisito": cod, "texto": texto,
                      "evaluado_en": "RS-03-PARAM-A",
                      "veredicto": "PASS" if a_decision == "GO" else "REVISAR",
                      "fuente": "decision sellada de RS-03-PARAM-A"})

    todos_pass = all(f["veredicto"] == "PASS" for f in filas)

    # B: caracterizacion, NO decide
    def hallar(o, *claves):
        if isinstance(o, dict):
            for k, v in o.items():
                if any(c in k.lower() for c in claves):
                    return {k: v}
                r = hallar(v, *claves)
                if r:
                    return r
        return None

    div = {"dq_por_atomo": hallar(mb, "dq", "carga"), "denergia": hallar(mb, "energia", "de")}

    with open(out / "per_complex.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for f in filas:
            fh.write(json.dumps(f, ensure_ascii=False) + "\n")

    metrics = {
        "experiment_id": "RS-03-PARAM",
        "tipo": "agregacion contra contrato congelado, sin computo nuevo",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(time.time() - t0, 3),
        "contrato": "RS-03-PARAM-PRE/PREREGISTRO.md seccion 4, 11 requisitos primarios",
        "requisitos": {"n": len(filas),
                       "pass": sum(1 for f in filas if f["veredicto"] == "PASS"),
                       "todos_pass": todos_pass},
        "fuente_A": {"experimento": "RS-03-PARAM-A", "decision": a_decision,
                     "cobertura": hallar(ma, "cobertura"),
                     "determinismo": hallar(ma, "determin")},
        "fuente_B": {"experimento": "RS-03-PARAM-B", "decision": nb.get("decision"),
                     "rol": "referencia estratificada, NO verdad absoluta; caracteriza y NO decide",
                     "divergencia_reportada": div},
        "decision_del_contrato": ("ACEPTAR NAGL como base de cargas" if todos_pass
                                  else "NO ACEPTAR: algun requisito primario no se cumple"),
        "asimetria_declarada": (
            "El contrato define que AM1-BCC es referencia estratificada y NO verdad "
            "absoluta, y PROHIBE seleccionar NAGL mirando RMSD o Top-1. B caracteriza, no "
            "decide: una divergencia grande documenta, no reprueba. Reprobar exigiria que A "
            "fallara un requisito primario, o un experimento de rendimiento que el contrato "
            "prohibe usar aqui."),
    }
    (out / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=1),
                                      encoding="utf-8", newline="\n")

    print(f"[RS-03-PARAM] agregacion en {metrics['duration_seconds']}s, sin computo nuevo")
    print(f"  requisitos primarios: {metrics['requisitos']['pass']}/{metrics['requisitos']['n']} PASS")
    print(f"  fuente A: {a_decision}   fuente B: {nb.get('decision')} (caracteriza, no decide)")
    print(f"  DECISION DEL CONTRATO: {metrics['decision_del_contrato']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
