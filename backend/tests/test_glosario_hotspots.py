import importlib.util
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location("auditar_catalogo_hotspots",ROOT/"scripts/auditar_catalogo_i18n.py")
audit=importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)

@pytest.mark.parametrize("es,en",[("Hotspots del catálogo","Catalog hot spots"),("Hotspot seleccionado","Selected hot spot"),("HOTSPOTS","HOT SPOTS")])
def test_auditor_detecta_hotspots_separados(es,en):
    assert any("hotspot" in p for p in audit.problemas_entrada(es,en))

@pytest.mark.parametrize("es,en",[("Hotspots del catálogo","Catalog hotspots"),("Hotspot seleccionado","Selected hotspot"),("Lugar cálido","A hot spot")])
def test_auditor_admite_palabra_unida_y_contexto_ajeno(es,en):
    assert not any("hotspot" in p for p in audit.problemas_entrada(es,en))

def test_catalogo_plantillas_y_glosario_comparten_grafia():
    from core.i18n_catalog import ENGLISH_MESSAGES
    from core.i18n_plantillas import PLANTILLAS_ES_EN
    for es,en in list(ENGLISH_MESSAGES.items())+list(PLANTILLAS_ES_EN):
        if "hotspot" in es.lower(): assert "hot spots" not in en.lower()
    text=(ROOT/"docs/GLOSARIO_EN.md").read_text(encoding="utf-8")
    assert "hotspots" in text and "hot spots" not in text
