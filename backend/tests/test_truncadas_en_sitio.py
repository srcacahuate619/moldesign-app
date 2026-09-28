"""B-3: una diana disponible puede tener el sitio incompleto, y se dice antes.

Con la receta v7, 125 dianas volvieron a estar disponibles truncando a ALA o GLY
las cadenas laterales que el cristal no resolvía. Algunas de esas cadenas caen
en el sitio: la corrida lo avisa como CRÍTICO, pero el selector de dianas no
podía decirlo antes de elegir. El barrido de disponibilidad lo mide y `Target`
lo publica.

La ausencia de medida no se lee como «ninguna».
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from services.targets import disponibilidad

RAIZ = Path(__file__).resolve().parents[2]


@pytest.fixture
def archivo(tmp_path, monkeypatch):
    def escribir(datos: dict) -> None:
        ruta = tmp_path / "disponibilidad.json"
        ruta.write_text(json.dumps(datos), encoding="utf-8")
        monkeypatch.setattr(disponibilidad, "RUTA_DISPONIBILIDAD", ruta)
        disponibilidad._datos.cache_clear()
        disponibilidad._no_disponibles.cache_clear()

    yield escribir
    disponibilidad._datos.cache_clear()
    disponibilidad._no_disponibles.cache_clear()


def test_sin_barrido_no_hay_medida(archivo):
    archivo({"no_disponibles": {}})
    assert disponibilidad.cadenas_truncadas_en_sitio("5VA1") is None


def test_con_barrido_distingue_ninguna_de_sin_medir(archivo):
    archivo({
        "no_disponibles": {"1FEM": {"motivo": "Meeko no puede construir el receptor"}},
        "truncadas_en_sitio": {"4NC3": ["A:140 LYS→ALA (2.1 Å)"]},
    })
    assert disponibilidad.cadenas_truncadas_en_sitio("4nc3") == ["A:140 LYS→ALA (2.1 Å)"]
    # Preparada por el barrido y sin truncados en el sitio.
    assert disponibilidad.cadenas_truncadas_en_sitio("5VA1") == []
    # No disponible: no se preparó, así que no hay medida.
    assert disponibilidad.cadenas_truncadas_en_sitio("1FEM") is None
    assert disponibilidad.cadenas_truncadas_en_sitio(None) is None


def test_write_y_check_conservan_lo_medido_por_el_barrido():
    ruta = RAIZ / "scripts" / "generate_catalog_availability.py"
    spec = importlib.util.spec_from_file_location("generate_catalog_availability", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)

    anterior = {
        "no_disponibles": {},
        "truncadas_en_sitio": {"4NC3": ["A:140 LYS→ALA (2.1 Å)"]},
        "barrido_meeko": {"receta_receptor": 7},
    }
    nuevo = {"receta_receptor": 7, "no_disponibles": {}}
    salida = modulo.conservar_medidas(nuevo, anterior)
    assert salida["truncadas_en_sitio"] == anterior["truncadas_en_sitio"]
    assert list(salida)[-2:] == ["truncadas_en_sitio", "barrido_meeko"]
