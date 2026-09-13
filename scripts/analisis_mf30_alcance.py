#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""analisis_mf30_alcance.py — MF-30-ALCANCE: por que MF-30 deja de ser direccion de producto.

Sin computo. Lee artefactos sellados y registra evidencia externa declarada.

Que era MF-30
-------------
El doc 49 seccion 20.11(c) lo definio asi: *evaluar un modelo generativo preentrenado sobre
la cohorte de 48, con la metrica del programa y sin reentrenar*. **Gate**: cobertura <=2 A
superior al **3/33** de `MF-09`, con CI95 que excluya el cero. **Control obligatorio**:
verificar solapamiento entre la cohorte y el conjunto de entrenamiento del modelo.

Estaba en la **prioridad 3** de esa seccion, detras de `MF-29` y `MF-28`. Las dos ya
cerraron -`MF-29-EMP` con lectura OBJETIVO y `MF-28` con NO_GO-, asi que por el orden del
propio programa le tocaba.

**Este artefacto no lo cancela ni lo borra.** Registra por que deja de ser direccion de
producto, con las tres razones medidas, y declara que lo reabriria.

Razon 1 — el gate esta caducado, y por mucho
--------------------------------------------
El 3/33 de `MF-09` era el techo del generador con el protocolo **rigido**, y era el estado
del arte del programa cuando se escribio la seccion. `MF-33` midio despues que el **ensemble
flexible propio** alcanza **26/33** sobre la misma cohorte y el mismo estrato.

Un modelo generativo que consiguiera 8/33 **pasaria el gate escrito** siendo tres veces peor
que lo que ya existe en casa. Es comparar contra placebo cuando ya hay tratamiento estandar:
la superioridad sobre placebo no significa nada si el estandar es mejor. El gate necesita
**comparador activo**, y el activo de hoy no es 3/33.

Este script calcula la tabla de comparadores desde los artefactos sellados, para que la
afirmacion no dependa de la memoria de nadie.

Razon 2 — la premisa esta contradicha por evidencia externa
------------------------------------------------------------
La seccion 20.11(c) justifica la familia asi: *«si el fallo es de paisaje, reemplazar el
paisaje es la jugada»*, y coloca al generativo como **el de mayor techo**. Esa premisa es de
2023-2024 y ha sido medida desde entonces.

**PoseBusters** (Buttenschoen, Morris & Deane, *Chemical Science* 15, 3130, 2024) evaluo
cinco metodos de aprendizaje profundo contra los clasicos sobre 308 complejos, exigiendo no
solo RMSD <= 2 A sino **validez fisica** de la pose -estereoquimica, longitudes de enlace,
planaridad, energia UFF y ausencia de choques con receptor y cofactores-:

    AutoDock Vina  58%      Gold  55%      DiffDock (el mejor de los DL)  12%

Y el modo de fallo que reporta es especifico: los metodos aprendidos generan poses que
puntuan bien y son **fisicamente imposibles**. La seccion 20.11 ya anotaba reservas sobre
fuga de datos y generalizacion; PoseBusters las cuantifica y anade una tercera.

**Estas cifras son EXTERNAS y se registran como tales**, no como medicion propia. La
seccion 20.12 prohibe citar una analogia como evidencia; esto no es una analogia, es un
benchmark publicado, y se cita con su fuente para que se pueda auditar o refutar.

Razon 3 — choca con una restriccion de producto declarada
----------------------------------------------------------
MolDesign se declara **100% CPU**. La GPU es opcional, para quien la tenga, y **nunca una
limitante**. Un modelo generativo de difusion como dependencia de tiempo de ejecucion
convierte la GPU en requisito, que es exactamente lo que la restriccion prohibe.

La distincion que sobrevive: **la GPU puede estar en el laboratorio, no en el producto**.
Usar un modelo con GPU para construir o validar algo que se entrega en CPU es compatible con
la restriccion; entregarlo como motor, no.

Que se decide
-------------
`MF-30` pasa de **prioridad 3 de la cartera pesada y direccion de producto** a **benchmark
externo opcional**, sin prerregistro pendiente y sin hueco en la cartera.

Que lo reabriria, declarado ahora
---------------------------------
1. Un modelo generativo que corra **inferencia en CPU** en tiempo razonable, de modo que no
   introduzca la dependencia prohibida; **o** un uso estrictamente de laboratorio que
   produzca un artefacto entregable en CPU.
2. Un gate **reescrito con comparador activo** -el mejor brazo propio del momento, no el
   3/33 historico- y con el control de solapamiento del doc 49 intacto.
3. Evidencia externa posterior a PoseBusters que revierta el resultado de 2024 sobre validez
   fisica.

Ninguna de las tres se cumple hoy. Si alguna se cumpliera, este artefacto queda como el
registro de por que estuvo parado, y no habria que reconstruir el razonamiento.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
UMBRAL_A = 2.0

# Evidencia EXTERNA, declarada con fuente. No es medicion propia.
POSEBUSTERS = {
    "referencia": "Buttenschoen M, Morris GM, Deane CM. PoseBusters: AI-based docking methods "
                  "fail to generate physically valid poses or generalise to novel sequences. "
                  "Chemical Science 15, 3130 (2024).",
    "url": "https://pubs.rsc.org/sc/article/15/9/3130/827511/",
    "conjunto": "PoseBusters Benchmark, 308 complejos, re-docking del ligando cognado",
    "criterio": "RMSD <= 2 A Y validez fisica (PB-valid): estereoquimica, longitudes de enlace, "
                "planaridad, energia UFF, choques con receptor y cofactores",
    "resultados": {"AutoDock Vina": 0.58, "Gold": 0.55, "DiffDock": 0.12},
    "nota": "cifras externas citadas con fuente, no medidas por este programa",
}


def _jsonl(p: Path) -> List[Dict[str, Any]]:
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def main() -> int:
    ap = argparse.ArgumentParser(description="MF-30-ALCANCE: registro del cambio de alcance")
    ap.add_argument("--workspace", default=str(PROJECT_ROOT))
    args = ap.parse_args()
    art = Path(args.workspace) / "scripts" / "artifacts_science"
    out_dir = art / "MF-30-ALCANCE"
    out_dir.mkdir(parents=True, exist_ok=True)

    # ── comparadores propios, desde artefactos sellados ──
    comparadores: Dict[str, Any] = {}

    m09 = json.loads((art / "MF-09" / "metrics.json").read_text(encoding="utf-8"))
    col09 = m09["resumen"]["COLOCACION"]
    comparadores["MF-09_gate_escrito"] = {
        "que_es": "existe alguna pose <=2 A entre las ~751 del conjunto v2, protocolo RIGIDO",
        "aciertos": col09["existe_pose_buena"], "de": col09["n"],
        "fraccion": round(col09["existe_pose_buena"] / col09["n"], 4),
        "es_el_gate_del_doc49": True,
    }

    m33 = _jsonl(art / "MF-33" / "per_complex.jsonl")
    col33 = [r for r in m33 if r.get("estrato") == "COLOCACION"]
    for brazo, desc in (("C", "protocolo congelado, todos los conformeros RIGIDOS"),
                        ("A", "un solo conformero FLEXIBLE (conf0.flex)"),
                        ("B", "ensemble FLEXIBLE, todos los conformeros")):
        n = sum(1 for r in col33 if r.get("brazos", {}).get(brazo, {}).get("alcanza"))
        comparadores[f"MF-33_brazo_{brazo}"] = {
            "que_es": desc, "aciertos": n, "de": len(col33),
            "fraccion": round(n / len(col33), 4) if col33 else None}

    p_a3 = art / "MF-33-A3" / "per_complex.jsonl"
    if p_a3.exists():
        a3 = [r for r in _jsonl(p_a3) if r.get("estrato") == "COLOCACION"]
        n = sum(1 for r in a3 if r.get("alcanza"))
        comparadores["MF-33-A3_en_curso"] = {
            "que_es": "K corridas del MISMO conformero, poses y CPU igualadas a B",
            "aciertos": n, "de": len(a3),
            "fraccion": round(n / len(a3), 4) if a3 else None,
            "PARCIAL": True,
            "nota": "si A3 muestra que la ventaja de B era conteo de poses, el comparador "
                    "activo baja; sigue muy por encima del 3/33 del gate escrito"}

    activo = max((v for k, v in comparadores.items()
                  if not v.get("PARCIAL") and v.get("fraccion") is not None),
                 key=lambda v: v["fraccion"])
    gate = comparadores["MF-09_gate_escrito"]

    out = {
        "analisis_id": "MF-30-ALCANCE",
        "tipo": "registro de cambio de alcance, sin computo",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "experimento_afectado": "MF-30",
        "definicion_original": "doc 49 seccion 20.11(c): evaluar un modelo generativo preentrenado "
                               "sobre la cohorte de 48, con rmsd_pose_pocket y sin reentrenar. "
                               "Gate: cobertura <=2 A superior al 3/33 de MF-09 con CI95 que excluya "
                               "el cero. Control obligatorio: solapamiento con el conjunto de "
                               "entrenamiento del modelo.",
        "prioridad_original": "3 de 4 en la seccion 20.11, tras MF-29 y MF-28",
        "estado_de_las_prioridades_1_y_2": {
            "MF-29 -> MF-29-EMP": "cerrado, lectura OBJETIVO",
            "MF-28": "cerrado, NO_GO"},
        "RAZON_1_gate_caducado": {
            "gate_escrito": gate,
            "comparador_activo_hoy": activo,
            "factor": round(activo["fraccion"] / gate["fraccion"], 2) if gate["fraccion"] else None,
            "consecuencia": "un modelo que superase el gate escrito podria ser varias veces peor "
                            "que el mejor brazo propio y aun asi 'pasar'. El gate exige comparador "
                            "activo, y el activo no es el 3/33.",
            "todos_los_comparadores": comparadores},
        "RAZON_2_premisa_contradicha": POSEBUSTERS,
        "RAZON_3_restriccion_de_producto": {
            "restriccion": "MolDesign es 100% CPU; la GPU es opcional y nunca limitante",
            "conflicto": "un modelo de difusion como motor convierte la GPU en requisito",
            "distincion_que_sobrevive": "la GPU puede estar en el laboratorio y no en el producto: "
                                        "usarla para construir o validar un artefacto entregable en "
                                        "CPU es compatible; entregarla como motor, no"},
        "DECISION": {
            "de": "prioridad 3 de la cartera pesada y direccion de producto",
            "a": "benchmark externo opcional",
            "no_se_cancela": True,
            "no_hay_prerregistro_pendiente": True,
            "deja_hueco_en_la_cartera": False},
        "QUE_LO_REABRIRIA": [
            "un generativo con inferencia en CPU en tiempo razonable, o un uso estrictamente de "
            "laboratorio que produzca un artefacto entregable en CPU",
            "un gate reescrito con comparador activo del momento y el control de solapamiento intacto",
            "evidencia externa posterior a PoseBusters que revierta su resultado sobre validez fisica",
        ],
        "limites_declarados": [
            "las cifras de PoseBusters son EXTERNAS y se citan con fuente; no las ha medido este programa",
            "no cancela MF-30 ni cierra la seccion 20.11(c): la reordena y declara sus condiciones de reapertura",
            "el comparador activo puede moverse cuando MF-33-A3 cierre; eso cambia su magnitud, no la conclusion",
        ],
    }
    (out_dir / "metrics.json").write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                          encoding="utf-8", newline="\n")
    print(f"[MF-30-ALCANCE] gate escrito: {gate['aciertos']}/{gate['de']} = {gate['fraccion']}")
    print(f"  comparador activo: {activo['aciertos']}/{activo['de']} = {activo['fraccion']} "
          f"({activo['que_es']})")
    print(f"  factor: {out['RAZON_1_gate_caducado']['factor']}x")
    print(f"  externo: Vina {POSEBUSTERS['resultados']['AutoDock Vina']}, "
          f"DiffDock {POSEBUSTERS['resultados']['DiffDock']} (PoseBusters 2024)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
