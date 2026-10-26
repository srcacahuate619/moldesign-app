"""Valida el criterio TAL COMO QUEDA en el producto: llama a modelo_desde_conformador
(tres semillas, recorte de candidatos por tamaño) sobre las mismas 167 moléculas
que el análisis previo, y cuenta las abstenciones. Sólo lectura del repo."""
import json
import pathlib
import sys
import time

RAIZ = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ / "backend"))
from chem import elevacion as el  # noqa: E402

SALIDA = pathlib.Path(sys.argv[1])
SALIDA.mkdir(parents=True, exist_ok=True)
moleculas = [json.loads(linea) for linea in open(SALIDA.parent / "moleculas.jsonl", encoding="utf-8")]

filas = []
with open(SALIDA / "validacion.jsonl", "w", encoding="utf-8") as f:
    for m in moleculas:
        inicio = time.time()
        try:
            modelo = el.modelo_desde_conformador(m["smiles"])
            fila = {"id": m["id"], "smiles": m["smiles"], "pesados": m["pesados"],
                    "razon_enlaces": modelo["razon_enlaces"], "fiel": modelo["fiel"],
                    "desajuste_px": modelo["desajuste_px"], "enlace_px": modelo["enlace_px"],
                    "segundos": round(time.time() - inicio, 2)}
        except Exception as exc:  # noqa: BLE001 - se registra
            fila = {"id": m["id"], "smiles": m["smiles"], "error": f"{type(exc).__name__}: {exc}"}
        f.write(json.dumps(fila, ensure_ascii=False) + "\n")
        f.flush()
print("listo", flush=True)
