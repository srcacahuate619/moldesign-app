#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SUP-03-VALIDADOR-LIGANDO: ¿qué química con actividad medida rechazan las reglas bloqueantes del validador?

Aplica `entrada/REGISTRO_PREVIO.md`: pasa cada SMILES por `chem.validator.validate_smiles` con la configuración por defecto del
producto, asigna cada rechazo a su regla (R1–R4 u «otra») por el texto del error y escribe `metrics.json`, `per_complex.jsonl`
(sólo los rechazados) y `failures.jsonl`.

Uso: python scripts/sup03_validador/medir.py
"""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "backend"))
from rdkit import RDLogger  # noqa: E402

from chem.validator import validate_smiles  # noqa: E402

RDLogger.DisableLog("rdApp.*")
ART = RAIZ / "scripts" / "artifacts_science"
EXP = ART / "SUP-03-VALIDADOR-LIGANDO"
ENTRADA = EXP / "entrada"
CON_ACTIVIDAD = ("A", "B", "C")

#: Regla → fragmento del mensaje de error que la identifica (`chem/validator.py`).
REGLAS = {
    "R2": "carga formal",          # «Átomo … con carga formal …» (se comprueba antes que la neta)
    "R1": "Carga formal neta",
    "R3": "radicales",
    "R4": "fragmentos desconectados",
}


def _conjuntos() -> dict[str, list[str]]:
    a = [json.loads(p.read_text(encoding="utf-8"))["smiles"]
         for p in sorted((ART / "CAL-D-01-R4-2-VMAT2-8T69" / "_work" / "panel").glob("shard-*/panel-*.terminal.json"))]
    with open(ART / "CAL-8HFI-01" / "entrada" / "panel_congelado.csv", encoding="utf-8") as fh:
        b = [fila["smiles"] for fila in csv.DictReader(fh)]
    # C, D y E no están versionados en `data/`: se copiaron a la entrada antes de sellar (`entrada/fuentes.json` guarda el SHA-256
    # de cada original); E es la lista de `completed_smiles` de los diez checkpoints, sin duplicados.
    def _lineas(nombre: str) -> list[str]:
        return [l.split()[0] for l in (ENTRADA / nombre).read_text(encoding="utf-8").splitlines()
                if l.strip() and not l.startswith("#")]
    return {"A": a, "B": b, "C": _lineas("C_chembl_5ht1a_actives.txt"), "D": _lineas("D_dude_5ht1a_decoys.smi"),
            "E": _lineas("E_benchmark_smiles.txt")}


def _regla(errores: list[str]) -> str:
    texto = " ".join(errores)
    if "Carga formal neta" in texto or "carga formal neta" in texto:
        return "R1"
    for regla in ("R2", "R3", "R4"):
        if REGLAS[regla].lower() in texto.lower():
            return regla
    return "otra"


def main() -> None:
    conjuntos = _conjuntos()
    rechazados, fallos = [], []
    cuenta: dict[str, Counter] = defaultdict(Counter)
    for nombre, smiles in conjuntos.items():
        for s in smiles:
            try:
                r = validate_smiles(s)
            except Exception as exc:  # noqa: BLE001 - se registra
                fallos.append({"conjunto": nombre, "smiles": s, "motivo": f"{type(exc).__name__}: {exc}"})
                continue
            if r.is_valid:
                cuenta[nombre]["aceptadas"] += 1
                continue
            regla = _regla(list(r.errors))
            cuenta[nombre][regla] += 1
            rechazados.append({"conjunto": nombre, "smiles": s, "regla": regla, "errores": list(r.errors)})
    por_regla = {}
    for regla in ("R1", "R2", "R3", "R4"):
        n = sum(cuenta[c][regla] for c in CON_ACTIVIDAD)
        por_regla[regla] = {"rechazadas_con_actividad": n, "decision": "GO" if n == 0 else "NO_GO"}
    n_actividad = sum(len(conjuntos[c]) for c in CON_ACTIVIDAD)
    salida = {
        "experiment_id": "SUP-03-VALIDADOR-LIGANDO",
        "tamanos": {k: len(v) for k, v in conjuntos.items()},
        "con_actividad_medida": n_actividad,
        "por_conjunto": {k: dict(cuenta[k]) for k in conjuntos},
        "por_regla": por_regla,
        "otras_con_actividad": sum(cuenta[c]["otra"] for c in CON_ACTIVIDAD),
        "decision": "GO" if all(v["decision"] == "GO" for v in por_regla.values()) else "NO_GO",
    }
    (EXP / "metrics.json").write_text(json.dumps(salida, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    with open(EXP / "per_complex.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        fh.writelines(json.dumps(f, ensure_ascii=False) + "\n" for f in rechazados)
    with open(EXP / "failures.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        fh.writelines(json.dumps(f, ensure_ascii=False) + "\n" for f in fallos)
    print(json.dumps(salida, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
