"""SCI-A-020, 043, 046, 047 y 048: sin anotación curada no se afirma una función biológica.

La clasificación por subcadenas sobre el PDB entero se retiró. Estas pruebas usan
los cinco depósitos reales que citó la auditoría (versionados en `data/targets/`)
y comprueban que ninguno recibe una clase funcional, que su clasificación y su
título del depósito se conservan como dato, y que todo sale en inglés.
"""
import gzip
from pathlib import Path

import pytest

from core.i18n_plantillas import traducir
from services.blockchain.certificate_context import SIN_CONTEXTO, generate_physiological_context

DEPOSITOS = Path(__file__).resolve().parents[2] / "data" / "targets"

#: Lo que la regla vieja afirmaba de cada uno, y lo que es.
CASOS = {
    "3ERT": "Receptor Acoplado a Proteínas G",   # receptor nuclear de estrógenos
    "5TOL": "Proteína Quinasa",                   # BACE1, aspartil proteasa
    "1BN1": "Hidrolasa / Proteasa",               # anhidrasa carbónica II (LYASE)
    "6E53": "Canal Iónico",                       # transcriptasa inversa de la telomerasa
    "1SM3": "catalizador o transductor",          # anticuerpo con su epítopo
}
CLASES_RETIRADAS = ("GPCR", "Quinasa", "Proteasa", "Canal Iónico", "catalizador",
                    "transductor", "Hidrolasa")


def _deposito(pdb_id: str) -> str:
    ruta = DEPOSITOS / f"{pdb_id}.pdb.gz"
    if not ruta.is_file():
        pytest.skip(f"{ruta.name} no está en este árbol")
    return gzip.decompress(ruta.read_bytes()).decode("utf-8", errors="replace")


@pytest.mark.parametrize("pdb_id", sorted(CASOS))
def test_ningun_deposito_real_recibe_una_clase_funcional_por_una_palabra(pdb_id):
    texto = generate_physiological_context(pdb_id, _deposito(pdb_id))
    assert texto.startswith(SIN_CONTEXTO)
    for clase in CLASES_RETIRADAS:
        assert clase not in texto, (pdb_id, clase)


@pytest.mark.parametrize("pdb_id, clasificacion", [("1BN1", "LYASE"), ("3ERT", None)])
def test_la_clasificacion_del_deposito_se_conserva_como_dato(pdb_id, clasificacion):
    contenido = _deposito(pdb_id)
    texto = generate_physiological_context(pdb_id, contenido)
    real = next(l for l in contenido.splitlines() if l.startswith("HEADER"))[10:50].strip()
    assert f"Clasificación del depósito: {real}" in texto
    if clasificacion:
        assert real.startswith(clasificacion)


def test_los_remark_y_la_cristalizacion_no_se_leen():
    pdb = ("HEADER    LYASE                                   01-JAN-00   1ABC\n"
           "REMARK   3   IMPROPER ANGLES MPRO\n"
           "REMARK 280 CRYSTALLIZATION: POTASSIUM CHLORIDE\n"
           "COMPND   2 FRAGMENT: KINASE DOMAIN;\n")
    texto = generate_physiological_context("1ABC", pdb)
    assert texto == f"{SIN_CONTEXTO} Clasificación del depósito: LYASE."


def test_sin_encabezado_no_hay_contexto():
    assert generate_physiological_context("7E2Y", None) == SIN_CONTEXTO
    assert generate_physiological_context("7E2Y", "ATOM      1  N   ALA A   1\n") == SIN_CONTEXTO


def test_un_titulo_largo_se_recorta():
    pdb = "TITLE     " + "X" * 70 + "\nTITLE    2 " + "Y" * 69 + "\nTITLE    3 " + "Z" * 69 + "\n"
    texto = generate_physiological_context("1ABC", pdb)
    assert texto.endswith("….") and len(texto) < len(SIN_CONTEXTO) + 200


@pytest.mark.parametrize("pdb_id", sorted(CASOS))
def test_sale_en_ingles(pdb_id):
    texto = generate_physiological_context(pdb_id, _deposito(pdb_id))
    ingles = traducir(texto, "en")
    assert ingles.startswith("Physiological context unavailable: the receptor has no curated functional annotation.")
    assert "depósito" not in ingles and "Clasificación" not in ingles


def test_sin_encabezado_tambien_en_ingles():
    assert traducir(SIN_CONTEXTO, "en") != SIN_CONTEXTO
