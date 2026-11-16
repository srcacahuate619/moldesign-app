"""B-8 (revisión final 1.0.4): la receta del paquete dice dónde está el verificador y qué necesita.

Antes remitía a `python scripts/verify_dossier_package.py <archivo>.zip` sin decir de dónde salía
`scripts/`: un tercero con sólo el ZIP no tenía cómo ejecutarlo. Aquí se fija que el README del paquete de
caso y el de cohorte lo dicen, en los dos idiomas, y que lo que dicen es cierto en el árbol.

Lo que NO se afirma, y esta prueba no lo prueba: que el verificador corra solo, sin red y fuera de un checkout
completo. El texto exige «una copia completa del repositorio» precisamente porque eso no está medido.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

from core.i18n import set_request_locale
from services.dossier.package import texto_donde_obtener_el_verificador

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "verify_dossier_package.py"

CONTRATO = {
    "es": ("no viaja dentro de este paquete", "copia completa del repositorio", "scripts/verify_dossier_package.py",
           "Python 3.11 o posterior", "Commit de código"),
    "en": ("does not ship inside this package", "complete copy of the repository", "scripts/verify_dossier_package.py",
           "Python 3.11 or later", "Code commit"),
}


def faltantes(texto: str, idioma: str) -> list[str]:
    return [frase for frase in CONTRATO[idioma] if frase not in texto]


def test_el_texto_dice_donde_esta_que_necesita_y_que_revision_usar():
    for idioma in ("es", "en"):
        set_request_locale(idioma)
        assert faltantes(texto_donde_obtener_el_verificador(), idioma) == [], idioma


def test_el_texto_en_ingles_no_deja_castellano():
    set_request_locale("en")
    texto = texto_donde_obtener_el_verificador()
    assert not re.search(r"\b(verificador|paquete|repositorio|biblioteca|revisión)\b", texto)


def test_la_guardia_demuestra_que_ve():
    """Control negativo: la mención anterior, sola, incumple el contrato."""
    anterior = "python scripts/verify_dossier_package.py <este-archivo>.zip"
    assert "no viaja dentro de este paquete" in faltantes(anterior, "es")
    assert "copia completa del repositorio" in faltantes(anterior, "es")


def test_lo_que_el_texto_afirma_del_arbol_es_cierto():
    set_request_locale("es")
    texto = texto_donde_obtener_el_verificador()
    assert SCRIPT.is_file()
    for ruta in re.findall(r"`(backend/[a-z_/]+)`", texto):
        assert (ROOT / ruta).is_dir(), ruta
    # «Sólo necesita ... su biblioteca estándar»: ningún import del script fuera de la estándar o del propio backend.
    arbol = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    importados = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            importados |= {a.name.split(".")[0] for a in nodo.names}
        elif isinstance(nodo, ast.ImportFrom) and nodo.module and nodo.level == 0:
            importados.add(nodo.module.split(".")[0])
    import sys
    assert importados <= set(sys.stdlib_module_names) | {"core", "services"}, importados
    # El campo que el texto manda a mirar existe en el dossier con ese nombre.
    modelo = (ROOT / "backend" / "services" / "dossier" / "model.py").read_text(encoding="utf-8")
    assert '"Commit de código"' in modelo


def test_el_paquete_real_lo_dice_en_el_readme_y_en_reproduce_md():
    """El paquete que sale de `construir_paquete`, no el código fuente: las dos menciones de la receta."""
    import io
    import zipfile

    from core.i18n import reset_request_locale
    from tests.test_dossier_package import _paquete

    for idioma in ("es", "en"):
        token = set_request_locale(idioma)
        try:
            datos, _entradas, _raiz = _paquete()
        finally:
            reset_request_locale(token)
        with zipfile.ZipFile(io.BytesIO(datos)) as zip_:
            for sufijo in ("README.md", "run/reproduce.md"):
                nombre = next(n for n in zip_.namelist() if n.endswith(sufijo))
                assert faltantes(zip_.read(nombre).decode("utf-8"), idioma) == [], (idioma, nombre)


def test_los_dos_readme_llevan_el_texto():
    paquete = (ROOT / "backend" / "services" / "dossier" / "package.py").read_text(encoding="utf-8")
    cohorte = (ROOT / "backend" / "services" / "cohort" / "dossier.py").read_text(encoding="utf-8")
    assert "texto_donde_obtener_el_verificador()" in paquete
    assert "texto_donde_obtener_el_verificador()" in cohorte
