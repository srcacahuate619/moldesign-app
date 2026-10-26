#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""VISION-MOLECULAR-01: reúne E1–E6 de la elevación 2D → 3D en un experimento y escribe sus salidas.

Los seis se registraron y se midieron por separado (`docs/auditorias/elevacion-grandes-2026-10-24/`), cada uno con su registro
previo commiteado antes de su resultado. Este script no vuelve a medir: aplica los criterios de cada registro a los datos ya
escritos (`e1.jsonl` … `e6.jsonl`) con los resúmenes de sus propios scripts, sin editarlos, y escribe `metrics.json`,
`per_complex.jsonl` (una fila por experimento) y `failures.jsonl`.

Uso: python scripts/vision_molecular_01/resumir.py
"""
from __future__ import annotations

import contextlib
import io
import json
import re
import runpy
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
EXP = RAIZ / "scripts" / "artifacts_science" / "VISION-MOLECULAR-01"
DATOS = RAIZ / "docs" / "auditorias" / "elevacion-grandes-2026-10-24"
PRODUCTO_DE_REFERENCIA = "26df919c"

#: Cada experimento: registro previo, commit del registro, commit del resultado y de dónde sale su veredicto.
EXPERIMENTOS = {
    "E1": ("Dibujo ajustado al 3D", "REGISTRO_PREVIO.md", "fcbb9d1e", "f526bae8"),
    "E2": ("ΔE del conformador con xTB", "REGISTRO_PREVIO.md", "fcbb9d1e", "f526bae8"),
    "E3": ("Plegado restringido al dibujo", "REGISTRO_PREVIO.md", "fcbb9d1e", "f526bae8"),
    "E4": ("Ventana de energía", "REGISTRO_PREVIO_E4.md", "4517768f", "8f864f52"),
    "E5": ("Enderezar cadenas y girar colas (MolTalk)", "REGISTRO_PREVIO_E5.md", "aa22435e", "81ad8c82"),
    "E6": ("Animación por torsiones frente a línea recta", "REGISTRO_PREVIO_E6.md", "74b2d17f", "d7498799"),
}


def _salida(funcion) -> str:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        funcion()
    return buf.getvalue()


def _resumenes() -> dict[str, str]:
    sys.path.insert(0, str(DATOS))
    r = runpy.run_path(str(DATOS / "resumen.py"), run_name="vision_molecular_01")
    salidas = {"E1": _salida(r["e1"]), "E2": _salida(r["e2"]), "E3": _salida(r["e3"])}
    for clave, script in (("E4", "e4_ventana_de_energia.py"), ("E5", "e5_cadenas_y_colas.py"),
                          ("E6", "e6_animacion_por_torsiones.py")):
        salidas[clave] = _salida(runpy.run_path(str(DATOS / script), run_name="vision_molecular_01")["resumir"])
    return salidas


def _veredicto(clave: str, texto: str) -> str:
    if clave == "E1":
        finales = re.findall(r"-> (NO_GO|GO)\s*$", texto, flags=re.M)
        if len(finales) != 2:
            raise SystemExit(f"E1: se esperaban dos veredictos (respaldo y por defecto), hay {finales}")
        return "GO" if all(v == "GO" for v in finales) else "NO_GO"
    patron = {"E2": r"-> (parcial|GO|NO_GO)\s*$", "E3": r"-> (NO_GO|GO)\s*$", "E4": r"-> (NO_GO|VIABLE)\s*$",
              "E5": r"^E5 -> (NO_GO|GO)\s*$", "E6": r"^Veredicto E6: (NO_GO|GO)\s*$"}[clave]
    hallados = re.findall(patron, texto, flags=re.M)
    if len(hallados) != 1:
        raise SystemExit(f"{clave}: se esperaba un veredicto, hay {hallados}")
    return {"VIABLE": "GO", "parcial": "PARCIAL"}.get(hallados[0], hallados[0])


def main() -> None:
    salidas = _resumenes()
    filas = []
    for clave, (nombre, registro, commit_registro, commit_resultado) in EXPERIMENTOS.items():
        filas.append({
            "experimento": clave,
            "nombre": nombre,
            "registro_previo": f"docs/auditorias/elevacion-grandes-2026-10-24/{registro}",
            "commit_del_registro": commit_registro,
            "commit_del_resultado": commit_resultado,
            "veredicto": _veredicto(clave, salidas[clave]),
            "resumen": salidas[clave].strip().splitlines(),
        })
    adoptados = [f["experimento"] for f in filas if f["veredicto"] == "GO"]
    metrics = {
        "experiment_id": "VISION-MOLECULAR-01",
        "producto_de_referencia": PRODUCTO_DE_REFERENCIA,
        "conjuntos": {"G37": "37 moléculas de 35 a 51 átomos pesados", "O167": "las 167 del conjunto original"},
        "veredictos": {f["experimento"]: f["veredicto"] for f in filas},
        "alternativas_adoptadas": adoptados,
        "decision": "GO" if adoptados else "NO_GO",
        "nota": "Ninguna alternativa entra en el producto. E2 (parcial) sólo mide la cifra: MMFF en fase gas exagera el ΔE cerca de "
                "un tercio (xTB-ALPB = 0,69 · MMFF) sin invertir el problema; el producto conserva el ΔE declarado.",
    }
    EXP.mkdir(parents=True, exist_ok=True)
    (EXP / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    with open(EXP / "per_complex.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for f in filas:
            fh.write(json.dumps(f, ensure_ascii=False) + "\n")
    (EXP / "failures.jsonl").write_text("", encoding="utf-8", newline="\n")
    for f in filas:
        print(f["experimento"], f["veredicto"], f["nombre"])
    print("decisión:", metrics["decision"])


if __name__ == "__main__":
    main()
