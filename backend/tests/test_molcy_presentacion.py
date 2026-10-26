"""La receta visual viaja con su trabajo; no altera ciencia ni preferencias globales."""
import hashlib
import json
import uuid

import pytest
from pydantic import ValidationError

from services.molcy import presentacion as receta, renderer


def test_defaultes_son_automaticos_y_no_cambian_el_titulo_de_la_fuente():
    ajustes = receta.normalizar()
    p = ajustes["presentacion"]
    assert p == {"schema": "moldesign.presentacion/1", "titulo": None, "color_receptor": None,
                 "color_residuos": None, "colores_lineas": {"polar": None, "apolar": None},
                 "receptor": "automatico", "muestra_anterior": True, "etiquetas": True, "contactos": True}
    assert "ensamble_fluido" not in ajustes


@pytest.mark.parametrize("cambio", [
    {"titulo": ""}, {"titulo": " "}, {"titulo": "a" * 81}, {"titulo": "uno\ndos"},
    {"titulo": "uno\u200bdos"}, {"titulo": 42}, {"color_receptor": "red"},
    {"color_residuos": "#12345"}, {"colores_lineas": {"polar": "#000000ff"}},
    {"receptor": "ocultar"}, {"etiquetas": "false"}, {"contactos": 0},
    {"colores_lineas": {"apolar": "#123456", "energia": 0}}, {"exhaustiveness": 999},
])
def test_la_receta_rechaza_controles_tipos_ambiguos_y_parametros_cientificos(cambio):
    with pytest.raises(ValidationError):
        receta.normalizar(cambio)


def test_cada_trabajo_congela_su_receta_y_su_huella(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir(); b.mkdir()
    estado_a, estado_b = {}, {}
    receta.guardar(a, estado_a, presentacion={"titulo": "  Serie A  ", "color_receptor": "#aabbcc", "etiquetas": False},
                   ensamble_fluido={"variante": "lenta", "conformero": 3})
    bytes_a = (a / "ajustes.json").read_bytes()
    receta.guardar(b, estado_b, presentacion={"titulo": "Serie B", "contactos": False})
    assert estado_a["ajustes"]["presentacion"]["titulo"] == "Serie A"
    assert estado_a["ajustes"]["presentacion"]["color_receptor"] == "#AABBCC"
    assert estado_a["ajustes"]["ensamble_fluido"] == {"variante": "lenta", "conformero": 3}
    assert estado_b["ajustes"]["presentacion"]["etiquetas"] is True
    assert (a / "ajustes.json").read_bytes() == bytes_a
    assert estado_a["ajustes_sha256"] == hashlib.sha256(bytes_a).hexdigest()
    assert receta.ruta_verificada(a, estado_a) == a / "ajustes.json"
    (a / "ajustes.json").write_text(json.dumps(estado_b["ajustes"]), encoding="utf-8")
    with pytest.raises(ValueError, match="SHA-256"):
        receta.ruta_verificada(a, estado_a)


def test_no_se_reconstruye_silenciosamente_una_receta_nueva_perdida(tmp_path):
    assert receta.ruta_verificada(tmp_path, {"id": "heredado"}) is None
    receta.guardar(tmp_path, estado := {})
    (tmp_path / "ajustes.json").unlink()
    with pytest.raises(OSError):
        receta.ruta_verificada(tmp_path, estado)


@pytest.mark.parametrize("cambio", [
    {"variante": "rapida"}, {"variante": "lenta", "conformero": -1},
    {"variante": "lenta", "conformero": True}, {"variante": "lenta", "conformero": "1"},
])
def test_la_ilustracion_fluida_no_admite_indices_ambiguos(cambio):
    with pytest.raises(ValidationError):
        receta.normalizar(ensamble_fluido=cambio)


def test_el_lanzador_guarda_la_receta_antes_de_encolar_y_get_la_conserva(tmp_path, monkeypatch):
    from api.routers import molcy
    from types import SimpleNamespace
    user, job = str(uuid.uuid4()), str(uuid.uuid4())
    llamadas = []
    monkeypatch.setattr(renderer, "encolar", lambda *args: llamadas.append(args))
    monkeypatch.setattr(renderer, "raiz_trabajo", lambda *_: tmp_path)
    renderer.iniciar(tmp_path, job_id=job, pdb_id="TEST", sujeto="receptor_solo", formato="biblioteca",
                     dispositivo="gpu", capacidad={}, fuente={"task_id": "run"},
                     presentacion={"titulo": "Mi receptor", "receptor": "oculto"})
    saved = json.loads((tmp_path / "estado.json").read_text(encoding="utf-8"))
    assert len(llamadas) == 1
    assert saved["ajustes"]["presentacion"]["titulo"] == "Mi receptor"
    assert receta.ruta_verificada(tmp_path, saved).is_file()
    # La cola es un doble; protegemos en_cola del detector de tareas interrumpidas.
    with renderer._lock:
        renderer._reserved.add(job)
    try:
        got = molcy.estado(uuid.UUID(job), SimpleNamespace(id=user))
        assert got["ajustes"] == saved["ajustes"]
        assert got["ajustes_sha256"] == saved["ajustes_sha256"]
    finally:
        with renderer._lock:
            renderer._reserved.discard(job)
