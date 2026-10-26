#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""analisis_mf16_r1_desde_mf10.py — el productor que el sello de MF-16-R1 no acredita.

MF-16-R1 se presenta como relectura de las energías **ya minimizadas** que MF-10 registró,
sin cómputo nuevo. Pero su manifiesto sella `scripts/run_mf16_embudo_ff.py`, que es el
runner de punto único de MF-16: no minimiza, no lee la salida de MF-10 y no emite los
campos de R1 (`rho_ff_relajado`, `rho_ff_punto_unico`). Lo encontró la auditoría
científica (SCI-B-096). Ese runner además reutiliza los hidrógenos de la primera pose al
puntuar las demás (SCI-B-097).

Este script recalcula R1 desde `MF-10/per_complex.jsonl`, que construye y minimiza cada
pose por separado (`run_mf10_relax_insitu.py`), y lo compara con lo sellado:

* `rho_ff_relajado`   = Spearman(rmsd_despues, energia_despues)
* `rho_ff_punto_unico` = Spearman(rmsd_antes, energia_antes)
* `rho_vina`          = Spearman(rmsd_antes, score)

El primero usa el RMSD **después** de relajar y los otros dos el de antes: relajar mueve
la pose, y R1 ya lo declara. Este script no cambia esa condición; sólo la hace trazable.

No toca los artefactos sellados: lee MF-10 y MF-16-R1 y escribe, si se le pide, en otra
carpeta.

Uso:
    python scripts/analisis_mf16_r1_desde_mf10.py --comprobar
    python scripts/analisis_mf16_r1_desde_mf10.py --salida <carpeta>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from statistics import median
from typing import Any, Dict, List, Optional, Sequence, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MF10 = Path("scripts/artifacts_science/MF-10/per_complex.jsonl")
R1 = Path("scripts/artifacts_science/MF-16-R1")
MIN_POSES = 8
ESTRATOS = ("COLOCACION", "CONTROL")


def _rangos(v: Sequence[float]) -> List[float]:
    n = len(v)
    orden = sorted(range(n), key=lambda i: v[i])
    r = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and v[orden[j + 1]] == v[orden[i]]:
            j += 1
        for k in range(i, j + 1):
            r[orden[k]] = (i + j) / 2 + 1
        i = j + 1
    return r


def spearman(a: Sequence[float], b: Sequence[float]) -> Optional[float]:
    """Spearman con rangos medios en los empates; None con menos de MIN_POSES o sin varianza."""
    n = len(a)
    if n < MIN_POSES:
        return None
    ra, rb = _rangos(a), _rangos(b)
    ma, mb = sum(ra) / n, sum(rb) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    da = sum((x - ma) ** 2 for x in ra) ** 0.5
    db = sum((y - mb) ** 2 for y in rb) ** 0.5
    return round(num / (da * db), 4) if da and db else None


def _rho(poses: List[Dict[str, Any]], x: str, y: str) -> Optional[float]:
    usables = [p for p in poses if p.get(x) is not None and p.get(y) is not None]
    return spearman([p[x] for p in usables], [p[y] for p in usables])


def reconstruir(complejos: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Filas y resumen de R1 desde las filas de MF-10. Entra un complejo si las tres ρ existen."""
    filas: List[Dict[str, Any]] = []
    for c in complejos:
        poses = c.get("poses") or []
        relajado = _rho(poses, "rmsd_despues", "energia_despues")
        punto = _rho(poses, "rmsd_antes", "energia_antes")
        vina = _rho(poses, "rmsd_antes", "score")
        if None in (relajado, punto, vina):
            continue
        antes = [p["energia_antes"] for p in poses if p.get("energia_antes") is not None]
        filas.append({
            "pid": c["pid"], "estrato": c["estrato"], "n_poses": len(poses),
            "rho_ff_relajado": relajado, "rho_ff_punto_unico": punto, "rho_vina": vina,
            "energia_antes_max": round(max(antes), 1),
            "delta_vs_vina": round(relajado - vina, 4),
        })
    resumen: Dict[str, Any] = {}
    for est in ESTRATOS:
        g = [f for f in filas if f["estrato"] == est]
        if not g:
            continue
        resumen[est] = {
            "n": len(g),
            "rho_ff_relajado_mediano": round(median(f["rho_ff_relajado"] for f in g), 4),
            "rho_ff_punto_unico_mediano": round(median(f["rho_ff_punto_unico"] for f in g), 4),
            "rho_vina_mediano": round(median(f["rho_vina"] for f in g), 4),
            "delta_mediano": round(median(f["delta_vs_vina"] for f in g), 4),
            "complejos_ff_mejor": sum(1 for f in g if f["delta_vs_vina"] > 0),
        }
    return filas, resumen


def _jsonl(ruta: Path) -> List[Dict[str, Any]]:
    return [json.loads(l) for l in ruta.read_text(encoding="utf-8").splitlines() if l.strip()]


def comprobar(raiz: Path) -> Dict[str, Any]:
    """Compara la reconstrucción con lo sellado en MF-16-R1, fila a fila y en el resumen."""
    fuente = raiz / MF10
    filas, resumen = reconstruir(_jsonl(fuente))
    sellado = {f["pid"]: f for f in _jsonl(raiz / R1 / "per_complex.jsonl")}
    nuestras = {f["pid"]: f for f in filas}
    claves = ("estrato", "rho_ff_relajado", "rho_ff_punto_unico", "rho_vina", "delta_vs_vina")
    distintas = sorted(pid for pid in sellado.keys() & nuestras.keys()
                       if any(sellado[pid].get(k) != nuestras[pid].get(k) for k in claves))
    resumen_sellado = json.loads((raiz / R1 / "metrics.json").read_text(encoding="utf-8"))["resumen"]
    return {
        "fuente": str(MF10).replace("\\", "/"),
        "fuente_sha256": hashlib.sha256(fuente.read_bytes()).hexdigest(),
        "filas_selladas": len(sellado),
        "filas_reconstruidas": len(nuestras),
        "solo_en_sellado": sorted(sellado.keys() - nuestras.keys()),
        "solo_reconstruidas": sorted(nuestras.keys() - sellado.keys()),
        "filas_distintas": distintas,
        "resumen_coincide": resumen == resumen_sellado,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="MF-16-R1 reconstruido desde MF-10")
    ap.add_argument("--raiz", type=Path, default=PROJECT_ROOT)
    ap.add_argument("--comprobar", action="store_true", help="comparar con lo sellado en MF-16-R1")
    ap.add_argument("--salida", type=Path, help="carpeta donde escribir per_complex.jsonl y resumen.json")
    args = ap.parse_args()
    if args.salida:
        filas, resumen = reconstruir(_jsonl(args.raiz / MF10))
        args.salida.mkdir(parents=True, exist_ok=True)
        with open(args.salida / "per_complex.jsonl", "w", encoding="utf-8", newline="\n") as fh:
            for f in filas:
                fh.write(json.dumps(f, ensure_ascii=False) + "\n")
        (args.salida / "resumen.json").write_text(
            json.dumps(resumen, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    if args.comprobar or not args.salida:
        informe = comprobar(args.raiz)
        print(json.dumps(informe, ensure_ascii=False, indent=1))
        iguales = (informe["resumen_coincide"] and not informe["filas_distintas"]
                   and not informe["solo_en_sellado"] and not informe["solo_reconstruidas"])
        return 0 if iguales else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
