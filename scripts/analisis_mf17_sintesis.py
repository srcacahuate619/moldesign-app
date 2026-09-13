#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""analisis_mf17_sintesis.py — MF-17: ¿qué predice, complejo a complejo, el fallo de colocación?

**Tipo: medición.** Cruza artefactos ya producidos, sin cómputo nuevo:

  * `MF-09`      — ¿existe pose ≤2 Å? (cobertura del oráculo)
  * `MF-13`      — ¿la función prefiere la pose nativa? (ventaja del cristal)
  * `MF-14`      — ¿cuán ancha es la cuenca del mínimo nativo? (`r50`)
  * `MF-15-EXT`  — ¿hay embudo que lleve a ella? (Spearman rmsd–score)

La línea entera ha producido cuatro mediciones mecánicas sobre la **misma cohorte de
48 complejos**. Cada una explica una pieza, pero ninguna se ha contrastado contra el
desenlace: **¿cuál de las cuatro separa los complejos que el docking resuelve de los
que no?**

Es la pregunta que decide dónde invertir después. Si el embudo separa y la cuenca no,
la palanca es la función de puntuación. Si la cuenca separa y el embudo no, es el
muestreo. Si ninguna separa, la explicación mecánica que hemos construido no predice
el desenlace y hay que decirlo.

No hay gate: es descriptivo y correlacional sobre n=48. Con esa n **no se afirma
causalidad** ni se ajusta ningún modelo — se reportan las medianas por grupo y la
separación, y nada más.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from statistics import median
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ART = PROJECT_ROOT / "scripts" / "artifacts_science"
OUT_DIR = ART / "MF-17"
MF14_LOCAL = PROJECT_ROOT / "scratch" / "mf14_resultados" / "per_complex.jsonl"


def _cargar(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    mf09 = {r["pid"]: r for r in _cargar(ART / "MF-09" / "per_complex.jsonl")}
    mf13 = {r["pid"]: r for r in _cargar(ART / "MF-13" / "per_complex.jsonl")}
    mf14 = {r["pid"]: r for r in _cargar(MF14_LOCAL)}
    mf15 = {r["pid"]: r for r in _cargar(ART / "MF-15-EXT" / "per_complex.jsonl")}

    filas: List[Dict[str, Any]] = []
    for pid, a in mf09.items():
        b, c, d = mf13.get(pid, {}), mf14.get(pid, {}), mf15.get(pid, {})
        rho = None
        if d.get("spearman_ingenuo"):
            rho = d["spearman_ingenuo"].get("global", {}).get("rho")
        filas.append({
            "pid": pid,
            "estrato": a.get("estrato"),
            # DESENLACE: existe pose <=2 A entre todas las generadas
            "cubierto": bool(a.get("existe_pose_buena")),
            "oraculo": a.get("oraculo_rmsd"),
            "top1_acierta": a.get("top1_acierta"),
            # MECANISMOS
            "ventaja_cristal": b.get("ventaja_cristal_local"),
            "cristal_gana": b.get("cristal_local_gana"),
            "r50": c.get("r50"),
            "rho_embudo": rho,
        })

    # el desenlace se toma del oraculo, que es la definicion operativa de la linea
    for f in filas:
        if f["oraculo"] is not None:
            f["cubierto"] = bool(f["oraculo"] <= 2.0)

    ok = [f for f in filas if f["oraculo"] is not None]
    grupos: Dict[str, Any] = {}
    for etiq, cond in (("RESUELTO", True), ("FALLA", False)):
        g = [f for f in ok if f["cubierto"] is cond]
        if not g:
            continue

        def med(k) -> Optional[float]:
            v = [f[k] for f in g if f.get(k) is not None]
            return round(median(v), 4) if v else None

        grupos[etiq] = {
            "n": len(g),
            "estratos": {e: sum(1 for f in g if f["estrato"] == e)
                         for e in ("COLOCACION", "CONTROL")},
            "oraculo_mediano": med("oraculo"),
            "rho_embudo_mediano": med("rho_embudo"),
            "r50_mediano": med("r50"),
            "ventaja_cristal_mediana": med("ventaja_cristal"),
            "frac_cristal_gana": round(
                sum(1 for f in g if f.get("cristal_gana")) /
                max(1, sum(1 for f in g if f.get("cristal_gana") is not None)), 4),
            "sin_r50": sum(1 for f in g if f.get("r50") is None),
        }

    separacion = {}
    for k in ("rho_embudo", "r50", "ventaja_cristal"):
        a = grupos.get("RESUELTO", {}).get(k + "_mediano" if k != "rho_embudo"
                                           else "rho_embudo_mediano")
        b = grupos.get("FALLA", {}).get(k + "_mediano" if k != "rho_embudo"
                                        else "rho_embudo_mediano")
        if k == "ventaja_cristal":
            a = grupos.get("RESUELTO", {}).get("ventaja_cristal_mediana")
            b = grupos.get("FALLA", {}).get("ventaja_cristal_mediana")
        if k == "r50":
            a = grupos.get("RESUELTO", {}).get("r50_mediano")
            b = grupos.get("FALLA", {}).get("r50_mediano")
        separacion[k] = {"resuelto": a, "falla": b,
                         "diferencia": round(a - b, 4) if (a is not None and b is not None) else None}

    with open(OUT_DIR / "per_complex.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for f in filas:
            fh.write(json.dumps(f, ensure_ascii=False) + "\n")
    metrics = {
        "experiment_id": "MF-17",
        "tipo": "medicion descriptiva (cruce de artefactos, sin computo nuevo)",
        "n_complejos": len(filas), "n_con_desenlace": len(ok),
        "fuentes": ["MF-09", "MF-13", "MF-14", "MF-15-EXT"],
        "desenlace": "cubierto = existe pose <=2.0 A entre todas las generadas (oraculo)",
        "grupos": grupos,
        "separacion_por_mecanismo": separacion,
        "limitacion": ("n=48 y correlacional: NO se afirma causalidad, no se ajusta ningun "
                       "modelo y no se deriva ningun umbral operativo de aqui."),
    }
    (OUT_DIR / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=1) + "\n",
                                          encoding="utf-8", newline="\n")
    print(json.dumps({"grupos": grupos, "separacion": separacion}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
