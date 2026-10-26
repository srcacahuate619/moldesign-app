r"""CAL-D-01-R4-2, piloto: ¿completa 4-67 contra 8T69 con el producto actual y el protocolo congelado de R4?

Importa sin modificarlo el arnés de R4 (`scripts/cal_d01r4/cal_d01r4.py`, activo sellado) y usa su cápsula de API.
No imprime ni lee el score, el RMSD ni la pose: los guarda en `crudo.json` para no ver el resultado de un compuesto
del panel antes de registrar el panel completo. Registro previo: D:\moldesign-audits\CAL_D_01_R4_2\REGISTRO_PREVIO_PILOTO.md.

    python-embed\python.exe scripts\cal_d01r4_2\piloto_467.py --salida D:\moldesign-audits\CAL_D_01_R4_2\piloto
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import time
from pathlib import Path

AQUI = Path(__file__).resolve().parent
R4 = AQUI.parent / "cal_d01r4" / "cal_d01r4.py"
RECEPTOR_R4 = "8fc027cae876631f30518b27823ce175e844bbe9e7bc10554653a7766e21468d"


def _r4():
    spec = importlib.util.spec_from_file_location("cal_d01r4", R4)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _fila_467(r4) -> dict:
    with open(r4.ENTRADA / "panel_congelado.csv", encoding="utf-8", newline="") as f:
        return next(fila for fila in csv.DictReader(f) if fila["padre"] == "4-67")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--salida", required=True, type=Path)
    a = ap.parse_args()
    a.salida.mkdir(parents=True, exist_ok=False)
    r4 = _r4()
    fila = _fila_467(r4)
    capsula = r4.Capsula(a.salida / f"c-{time.time_ns():x}", 1)
    inicio = time.time()
    try:
        try:
            raw = capsula.evaluar(fila["smiles"], r4.SEMILLA_PANEL, "piloto-4-67")
            estado, error = "SUCCESS", None
        except Exception as exc:  # el producto devolvió FAILURE o se agotó el tiempo
            raw, estado, error = None, "FAILURE", f"{type(exc).__name__}: {exc}"
    finally:
        capsula.parar()
    segundos = round(time.time() - inicio, 1)

    resumen = {"padre": "4-67", "estado": estado, "error": error, "segundos_totales": segundos}
    if raw is not None:
        (a.salida / "crudo.json").write_text(json.dumps(raw, ensure_ascii=False, default=str), encoding="utf-8")
        res = raw["resultado"]
        dp = res["docking_protocol"]
        prov = dp.get("execution_provenance") or {}
        top1 = next((p for p in (res.get("structural_evidence") or {}).get("poses") or [] if p.get("rank") == 1), {})
        acoplado = (res.get("ligand_state") or {}).get("smiles_acoplado")
        resumen.update({
            "segundos_evaluacion": raw.get("segundos"), "vina": res.get("vina_version"), "cpu": prov.get("cpu"),
            "semilla": dp.get("seed"), "exhaustividad": dp.get("exhaustiveness"), "poses": dp.get("num_poses"),
            "microestado_coincide": acoplado == fila["smiles_acoplado_esperado"],
            "receptor_sha256": prov.get("receptor_sha256"),
            "receptor_igual_que_r4": prov.get("receptor_sha256") == RECEPTOR_R4,
            "validacion_fisica_top1": top1.get("status"),
            "crudo_sha256": hashlib.sha256((a.salida / "crudo.json").read_bytes()).hexdigest(),
        })
        parametros = (resumen["vina"], resumen["cpu"], resumen["semilla"], resumen["exhaustividad"], resumen["poses"])
        resumen["resultado"] = ("COMPLETA" if resumen["microestado_coincide"] and parametros == ("1.2.7", 4, 42, 8, 9)
                                else "DERIVA")
    else:
        resumen["resultado"] = "NO_COMPLETA"
    (a.salida / "resumen.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(resumen, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
