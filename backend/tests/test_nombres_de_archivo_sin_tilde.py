"""
Los nombres de archivo del dossier y de la cohorte no convierten una tilde en un guion (QA1-001).

Medido al descargar el dossier de un caso «Inhibición de ACE — cribado inicial»:
`dossier_inhibici-n-de-ace-cribado-inicial.pdf`. La lista blanca ASCII (necesaria: ZIP, cabeceras de
descarga, otros sistemas) tiraba cada letra con tilde. Decisión del propietario (2026-10-04):
transliterar («Inhibicion»), no conservar la tilde.

Hay TRES saneadores con la misma lista blanca (dossier, cohorte y frontend). Los pares de aquí son los
mismos que los de `frontend/lib/__tests__/dossier.test.ts`: si uno cambia y otro no, falla uno de los dos.
"""

from __future__ import annotations

import pytest

from services.cohort import repository as cohort_repo
from services.dossier.package import raiz_paquete, sanitizar

#: (entrada, salida esperada) — compartidos con la prueba del frontend.
PARES = [
    ("Inhibición de ACE — cribado inicial", "Inhibicion-de-ACE-cribado-inicial"),
    ("Verificación de cápsula — ñandú", "Verificacion-de-capsula-nandu"),
    ("Ünïcödé", "Unicode"),
]


@pytest.mark.parametrize("entrada, esperado", PARES)
def test_el_dossier_transcribe_las_tildes(entrada, esperado):
    assert sanitizar(entrada) == esperado


@pytest.mark.parametrize("entrada, esperado", PARES)
def test_la_cohorte_transcribe_las_tildes_igual(entrada, esperado):
    # Paridad entre los dos saneadores del backend (el de cohorte además corta rutas).
    assert cohort_repo.sanitize_source_filename(entrada) == esperado


def test_el_nombre_de_un_archivo_subido_conserva_su_forma_y_pierde_la_tilde():
    assert cohort_repo.sanitize_source_filename("série_ñandú.csv") == "serie_nandu.csv"


def test_lo_que_ya_estaba_prohibido_sigue_prohibido():
    """Control negativo: la transliteración no abrió un camino que la lista blanca cerraba."""
    assert cohort_repo.sanitize_source_filename("../../etc/passwd") == "passwd"
    assert cohort_repo.sanitize_source_filename("C:\\Users\\ana\\cohorte.csv") == "cohorte.csv"
    assert sanitizar("../escape") == "escape"
    assert "/" not in raiz_paquete("caso/../../x", "t")
    assert ".." not in raiz_paquete("caso/../../x", "t")
    assert sanitizar("") == "sin-nombre"
    assert sanitizar("β") == "sin-nombre"  # sin equivalente ASCII: nada que conservar


def test_un_caracter_sin_equivalente_ascii_sigue_siendo_un_separador():
    assert sanitizar("a β b") == "a-b"
