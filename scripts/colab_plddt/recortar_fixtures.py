"""Recortes de los archivos reales de Boltz-2 y Chai-1 para las pruebas del backend, con su procedencia.

Los originales son los de la segunda ejecución del cuaderno de Colab (acta en
``docs/auditorias/convencion-plddt-boltz-chai-2026-11-15/``), archivados fuera del repositorio. Antes de recortar se
comprueba que cada original tiene el SHA-256 que declara el manifiesto del acta, así que un recorte sólo sale de un
archivo que se puede citar.

El recorte es el mismo que el de los fixtures de AlphaFold DB: los residuos 1-90 de la cadena A en ``ATOM`` (PDB) y en
``_atom_site`` y ``_ma_qa_metric_local`` (mmCIF). Todo lo demás queda tal cual, byte a byte: la cabecera (o su
ausencia), el ligando con su pLDDT por átomo, los ``CONECT`` que sólo tocan átomos conservados y las demás tablas.

    python scripts/colab_plddt/recortar_fixtures.py [--archivo CARPETA] [--salida CARPETA] [--check]

``--check`` no escribe: falla si algún recorte del repositorio no es el que sale de los originales.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
ACTA = RAIZ / "docs" / "auditorias" / "convencion-plddt-boltz-chai-2026-11-15"
ARCHIVO = Path(r"F:\Backups\moldesign-evidencia\2026-11-15-colab-plddt-boltz-chai")
SALIDA = RAIZ / "backend" / "tests" / "data" / "receptores_propios"
PROCEDENCIA = "boltz_chai_procedencia.json"
ULTIMO_RESIDUO = 90
CADENA = "A"

_RESULTADOS = "descarga-20261115T011719Z/moldesign_plddt_boltz_chai/resultados/"
#: recorte → original dentro del archivo.
RECORTES = {
    "boltz_cdk2_lig_recortado.pdb":
        _RESULTADOS + "boltz/cdk2_lig__pdb/boltz_results_cdk2_lig/predictions/cdk2_lig/cdk2_lig_model_0.pdb",
    "boltz_cdk2_apo_recortado.cif":
        _RESULTADOS + "boltz/cdk2_apo__mmcif/boltz_results_cdk2_apo/predictions/cdk2_apo/cdk2_apo_model_0.cif",
    "chai_cdk2_apo_recortado.cif": _RESULTADOS + "chai/cdk2_apo__mmcif/pred.model_idx_0.cif",
}
#: Tablas del mmCIF que se recortan; las demás no se tocan.
TABLAS_RECORTADAS = ("_atom_site.", "_ma_qa_metric_local.")
_TOKEN = re.compile(r"'[^']*'(?=\s|$)|\"[^\"]*\"(?=\s|$)|\S+")


def _sha256(datos: bytes) -> str:
    return hashlib.sha256(datos).hexdigest()


def recortar_pdb(texto: str) -> str:
    """Quita los ``ATOM`` de la cadena A más allá del residuo 90 y los ``CONECT`` que apuntan a ellos."""
    conservados: set[int] = set()
    lineas = []
    for linea in texto.splitlines(keepends=True):
        if linea.startswith(("ATOM", "HETATM")):
            if linea.startswith("ATOM") and linea[21] == CADENA and int(linea[22:26]) > ULTIMO_RESIDUO:
                continue
            conservados.add(int(linea[6:11]))
        elif linea.startswith("CONECT"):
            serie = [int(linea[i:i + 5]) for i in range(6, len(linea.rstrip("\r\n")), 5) if linea[i:i + 5].strip()]
            if not set(serie) <= conservados:
                continue
        lineas.append(linea)
    return "".join(lineas)


def recortar_mmcif(texto: str) -> str:
    """Quita las filas de ``_atom_site`` y ``_ma_qa_metric_local`` de la cadena A más allá del residuo 90.

    Se recorta sobre el texto para dejar todo lo demás intacto. Cada fila tiene que estar en una sola línea y tener
    tantos valores como columnas; si no, se aborta en vez de adivinar.
    """
    lineas = texto.splitlines(keepends=True)
    salida: list[str] = []
    i = 0
    while i < len(lineas):
        linea = lineas[i]
        if linea.strip() != "loop_":
            salida.append(linea)
            i += 1
            continue
        etiquetas, j = [], i + 1
        while j < len(lineas) and lineas[j].startswith("_"):
            etiquetas.append(lineas[j].split()[0])
            j += 1
        tabla = etiquetas[0].rsplit(".", 1)[0] + "." if etiquetas else ""
        salida.extend(lineas[i:j])
        i = j
        if tabla not in TABLAS_RECORTADAS:
            continue
        cols = [e.rsplit(".", 1)[1] for e in etiquetas]
        seq = cols.index("label_seq_id")
        cadena = cols.index("label_asym_id")
        while i < len(lineas) and not lineas[i].startswith(("loop_", "_", "#", "data_")) and lineas[i].strip():
            valores = _TOKEN.findall(lineas[i])
            if len(valores) != len(cols):
                raise ValueError(f"{tabla} fila {i + 1}: {len(valores)} valores para {len(cols)} columnas")
            fuera = valores[cadena] == CADENA and valores[seq] not in (".", "?") and int(valores[seq]) > ULTIMO_RESIDUO
            if not fuera:
                salida.append(lineas[i])
            i += 1
    return "".join(salida)


def construir(archivo: Path) -> tuple[dict[str, bytes], dict]:
    manifiesto = json.loads((ACTA / "manifiesto.json").read_text(encoding="utf-8"))["archivos"]
    recortes: dict[str, bytes] = {}
    originales: dict[str, str] = {}
    for nombre, relativo in RECORTES.items():
        datos = (archivo / relativo).read_bytes()
        sha = _sha256(datos)
        if manifiesto.get(relativo, {}).get("sha256") != sha:
            raise SystemExit(f"{relativo}: el SHA-256 no es el del manifiesto del acta ({sha})")
        originales[relativo] = sha
        texto = datos.decode("utf-8")
        recortado = recortar_pdb(texto) if nombre.endswith(".pdb") else recortar_mmcif(texto)
        recortes[nombre] = recortado.encode("utf-8")
    procedencia = {
        "fuente": "Segunda ejecución del cuaderno de Colab (2026-11-15, NVIDIA L4): Boltz 2.2.1 y chai_lab 0.6.1",
        "acta": "docs/auditorias/convencion-plddt-boltz-chai-2026-11-15/README.md",
        "archivo": str(ARCHIVO),
        "originales": originales,
        "recortes": {n: _sha256(d) for n, d in recortes.items()},
        "recorte": (f"residuos 1-{ULTIMO_RESIDUO} de la cadena {CADENA}: ATOM en el PDB; _atom_site y "
                    "_ma_qa_metric_local en el mmCIF. La cabecera (o su ausencia), el ligando, los CONECT de átomos "
                    "conservados y las demás tablas, tal cual"),
        "script": "scripts/colab_plddt/recortar_fixtures.py",
    }
    return recortes, procedencia


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--archivo", type=Path, default=ARCHIVO)
    parser.add_argument("--salida", type=Path, default=SALIDA)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    recortes, procedencia = construir(args.archivo)
    if args.check:
        distintos = [n for n, d in recortes.items() if not (args.salida / n).is_file()
                     or (args.salida / n).read_bytes() != d]
        guardada = json.loads((args.salida / PROCEDENCIA).read_text(encoding="utf-8"))
        if guardada["recortes"] != procedencia["recortes"] or guardada["originales"] != procedencia["originales"]:
            distintos.append(PROCEDENCIA)
        print("recortes iguales a los de los originales" if not distintos else f"distintos: {distintos}")
        return 1 if distintos else 0
    for nombre, datos in recortes.items():
        (args.salida / nombre).write_bytes(datos)
    (args.salida / PROCEDENCIA).write_text(json.dumps(procedencia, ensure_ascii=False, indent=2) + "\n",
                                           encoding="utf-8")
    for nombre, datos in recortes.items():
        print(f"{nombre}: {len(datos)} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
