"""Lo que se descarga tiene que caer donde el motor lo busca.

EL DEFECTO QUE ESTO IMPIDE

El launcher compone la ruta de descarga como `get_resource_dir()` + el destino
que declara `launcher-manifest.json`. Cuando el paquete MSIX redirigió las
descargas al perfil del usuario, `get_resource_dir()` pasó a devolver
`%USERPROFILE%\\MolDesign\\models`, y el manifiesto ya declaraba `models/llm/`.
El resultado era una ruta con el segmento duplicado:

    %USERPROFILE%\\MolDesign\\models\\models\\llm\\      <- se escribía aquí
    %USERPROFILE%\\MolDesign\\models\\llm\\              <- el backend buscaba aquí

La descarga terminaba bien y la interfaz la marcaba correcta. El motor no
encontraba el modelo. Un fallo así cuesta 1,1 GB en el caso de Qwen y 8,4 GB en
el de ESMFold **antes** de que nadie note que algo va mal, y no lo delata ningún
error: sólo una función que sigue diciendo «no disponible».

Por eso esta prueba no comprueba una ruta escrita a mano: compara las dos
fuentes de verdad que tienen que coincidir —el manifiesto de descarga y los
directorios donde el backend busca— y falla si alguien mueve una sin la otra.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "backend"))

MANIFIESTO = RAIZ / "launcher-manifest.json"

#: La raíz que `model_root()` devuelve en un paquete MSIX. Escrita a mano a
#: propósito: si alguien la cambia en downloader.rs, esta prueba debe fallar en
#: vez de adaptarse. Ver el comentario de `model_root` en
#: frontend/src-tauri/src/downloader.rs.
RAIZ_EN_MSIX = Path.home() / "MolDesign"


def _modulos() -> dict[str, str]:
    """{id del módulo: destino declarado} de launcher-manifest.json."""
    datos = json.loads(MANIFIESTO.read_text(encoding="utf-8"))
    modulos = datos.get("modules") or datos.get("modulos") or []
    salida = {}
    for m in modulos:
        destino = m.get("destination") or m.get("destino") or m.get("target_dir")
        if destino:
            salida[m.get("id") or m.get("nombre")] = destino
    return salida


def test_el_manifiesto_declara_los_dos_modulos():
    modulos = _modulos()
    assert "llm-qwen15" in modulos, "falta el módulo del LLM local"
    assert "esmfold-weights" in modulos, "falta el módulo de pesos de ESMFold"


def test_el_llm_aterriza_donde_local_llm_lo_busca():
    """MODEL_SEARCH_PATHS tiene que contener el destino compuesto."""
    from services.ai.local_llm import MODEL_SEARCH_PATHS

    destino = _modulos()["llm-qwen15"]
    compuesto = (RAIZ_EN_MSIX / destino.strip("/")).resolve()

    buscados = {Path(p).resolve() for p in MODEL_SEARCH_PATHS}
    assert compuesto in buscados, (
        f"La descarga del LLM aterriza en {compuesto}, que no está en "
        f"MODEL_SEARCH_PATHS:\n  "
        + "\n  ".join(str(p) for p in sorted(buscados))
        + "\n\nO el destino del manifiesto o las rutas de búsqueda se movieron "
        "sin la otra. Tal cual, la descarga de 1,1 GB terminaría bien y el "
        "modelo seguiría 'no disponible'."
    )


def test_esmfold_aterriza_donde_el_catalogo_de_motores_lo_busca():
    """Los archivos declarados tienen que resolver bajo un directorio de búsqueda."""
    from services.motores.catalogo import ESMFOLD_ARCHIVOS, directorios_de_busqueda

    destino = _modulos()["esmfold-weights"]
    raiz_descarga = (RAIZ_EN_MSIX / destino.strip("/")).resolve()

    # Los archivos se declaran relativos a un directorio de búsqueda; el destino
    # de la descarga tiene que ser el prefijo de alguno de ellos.
    esperados = {
        (Path(d) / rel).resolve().parent
        for d in directorios_de_busqueda()
        for rel in ESMFOLD_ARCHIVOS
    }
    assert raiz_descarga in esperados, (
        f"ESMFold se descargaría en {raiz_descarga}, y el catálogo de motores "
        f"busca sus archivos en:\n  "
        + "\n  ".join(str(p) for p in sorted(esperados))
        + "\n\nSon 8,4 GB que terminarían en el sitio equivocado sin un solo "
        "error visible."
    )


@pytest.mark.parametrize("modulo", ["llm-qwen15", "esmfold-weights"])
def test_ningun_destino_duplica_el_segmento_de_la_raiz(modulo):
    """El fallo concreto: `…/models` + `models/llm/` = `…/models/models/llm`."""
    destino = _modulos()[modulo]
    compuesto = RAIZ_EN_MSIX / destino.strip("/")
    partes = [p.lower() for p in compuesto.parts]
    for i in range(len(partes) - 1):
        assert partes[i] != partes[i + 1], (
            f"Segmento repetido en {compuesto}: '{partes[i]}' dos veces "
            "seguidas. Es la firma de una raíz que ya incluye lo que el "
            "destino vuelve a añadir."
        )
