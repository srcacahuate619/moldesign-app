"""Convergencia del desajuste con el número de conformadores candidatos.

Pregunta: ¿el desajuste de una molécula es una propiedad suya o sólo depende de
cuántos conformadores se muestrean? El producto recorta a 16/8/4 según el tamaño;
si el valor sigue bajando al subir los candidatos, el recorte mide el muestreo.
Cada cifra es el MÍNIMO sobre los candidatos (como en el producto) y la mediana
sobre tres semillas.
"""
import json
import pathlib
import statistics
import sys
import time

from rdkit import Chem

RAIZ = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ / "backend"))
from chem import elevacion as el  # noqa: E402

SALIDA = pathlib.Path(sys.argv[1])
SALIDA.mkdir(parents=True, exist_ok=True)

MOLECULAS = {
    "imatinib": "Cc1ccc(NC(=O)c2ccc(CN3CCN(C)CC3)cc2)cc1Nc1nccc(-c2cccnc2)n1",
    "atorvastatina": "CC(C)c1n(CC[C@@H](O)C[C@@H](O)CC(=O)O)c(-c2ccccc2)c(C(=O)Nc2ccccc2)c1-c1ccc(F)cc1",
    "CHEMBL1182041": "FC(F)(F)OCCN(Cc1ccccc1C(F)(F)F)C1CCNCC1",
    "CHEMBL1182019": "CC(C)CN(Cc1ccc(C(F)(F)F)cc1)C1CCNCC1",
    "paclitaxel": "CC1=C2C(C(=O)C3(C(CC4C(C3C(C(C2(C)C)(CC1OC(=O)C(C(C5=CC=CC=C5)NC(=O)C6=CC=CC=C6)O)O)OC(=O)C7=CC=CC=C7)(CO4)OC(=O)C)O)C",
    "cafeina": "Cn1cnc2c1c(=O)n(C)c(=O)n2C",
    "ciclohexano": "C1CCCCC1",
}
CANDIDATOS = (4, 8, 16, 32, 64)
SEMILLAS = (1, 2, 3)

filas = []
for nombre, smi in MOLECULAS.items():
    mol = Chem.MolFromSmiles(smi)
    if mol is None:
        print("SMILES no válido:", nombre, flush=True)
        continue
    enlace = None
    for n in CANDIDATOS:
        valores, tiempos, reales = [], [], []
        for s in SEMILLAS:
            inicio = time.time()
            modelo = el.modelo_desde_conformador(smi, conformadores=n, semilla=s)
            tiempos.append(time.time() - inicio)
            valores.append(modelo["desajuste_px"])
            reales.append(modelo["conformador"]["candidatos"])
        enlace = enlace or el.dibujo_2d(Chem.MolFromSmiles(smi))  # solo para el registro de escala
        fila = {
            "molecula": nombre,
            "pesados": mol.GetNumAtoms(),
            "candidatos_pedidos": n,
            "candidatos_obtenidos": statistics.median(reales),
            "desajuste_mediana_px": round(statistics.median(valores), 3),
            "desajuste_rango_px": round(max(valores) - min(valores), 3),
            "segundos_mediana": round(statistics.median(tiempos), 2),
        }
        filas.append(fila)
        print(json.dumps(fila, ensure_ascii=False), flush=True)

with open(SALIDA / "convergencia.jsonl", "w", encoding="utf-8") as f:
    for fila in filas:
        f.write(json.dumps(fila, ensure_ascii=False) + "\n")
print("listo", flush=True)
