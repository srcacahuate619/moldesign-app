"""El estado de un trabajo de Molcy sobrevive a un sondeo que coincide con un guardado del hilo de render (Windows).

Medido con tres hilos leyendo `estado.json` mientras otro lo reemplaza: 3446 de 4000 `os.replace` fallan con `PermissionError`. En la aplicación, la
interfaz sondea el trabajo justo después de crearlo y el hilo de render hace en ese mismo momento su primer guardado: el hilo moría, el sondeo veía el trabajo
sin hilo y escribía «Render interrumpido al cerrar MolDesign» encima, tapando la causa. Se vio en una corrida real en español: 0 s, sin `render.log`.
"""
import json
import os
import uuid

import pytest

from services.molcy import renderer


def test_guardar_estado_reintenta_si_el_fichero_esta_abierto(monkeypatch, tmp_path):
    reales = os.replace
    llamadas = []

    def replace(origen, destino):
        llamadas.append(1)
        if len(llamadas) <= 3:
            raise PermissionError(5, "Acceso denegado")
        return reales(origen, destino)

    monkeypatch.setattr(renderer.os, "replace", replace)
    monkeypatch.setattr(renderer.time, "sleep", lambda _s: None)
    renderer.guardar_estado(tmp_path, {"id": "x", "estado": "renderizando"})
    assert len(llamadas) == 4
    assert json.loads((tmp_path / "estado.json").read_text(encoding="utf-8"))["estado"] == "renderizando"
    assert [p.name for p in tmp_path.iterdir()] == ["estado.json"], "no deja temporales"


def test_guardar_estado_no_reintenta_para_siempre(monkeypatch, tmp_path):
    llamadas = []

    def replace(_origen, _destino):
        llamadas.append(1)
        raise PermissionError(5, "Acceso denegado")

    monkeypatch.setattr(renderer.os, "replace", replace)
    monkeypatch.setattr(renderer.time, "sleep", lambda _s: None)
    with pytest.raises(PermissionError):
        renderer.guardar_estado(tmp_path, {"id": "x", "estado": "renderizando"})
    assert len(llamadas) == renderer.ESTADO_REINTENTOS
    assert [p.name for p in tmp_path.iterdir()] == [], "no deja temporales"


def test_un_sondeo_no_pisa_el_estado_final_que_el_hilo_guarda_entre_la_lectura_y_la_comprobacion(monkeypatch, tmp_path):
    job = str(uuid.uuid4())
    (tmp_path / "estado.json").write_text(json.dumps({"id": job, "estado": "en_cola"}), encoding="utf-8")
    monkeypatch.setattr(renderer, "raiz_trabajo", lambda _usuario, _job: tmp_path)
    monkeypatch.setattr(renderer, "_reserved", set())
    final = {"id": job, "estado": "fallido", "motivo": "el motivo real del fallo", "terminado_s": 1.0}
    reales = json.loads
    lecturas = []

    def loads(texto, *args, **kwargs):
        valor = reales(texto, *args, **kwargs)
        lecturas.append(1)
        if len(lecturas) == 1:
            # Entre esta lectura y la comprobación de `_reserved`, el hilo de render termina y guarda su estado final.
            (tmp_path / "estado.json").write_text(json.dumps(final), encoding="utf-8")
        return valor

    monkeypatch.setattr(renderer.json, "loads", loads)
    estado = renderer.leer_estado("usuario", job)
    assert estado["motivo"] == "el motivo real del fallo"
    assert reales((tmp_path / "estado.json").read_text(encoding="utf-8"))["motivo"] == "el motivo real del fallo"


def test_un_trabajo_sin_hilo_que_sigue_en_cola_se_da_por_interrumpido(monkeypatch, tmp_path):
    """Lo de siempre se conserva: tras cerrar la aplicación, un trabajo a medias no se queda «renderizando» para siempre."""
    job = str(uuid.uuid4())
    (tmp_path / "estado.json").write_text(json.dumps({"id": job, "estado": "renderizando"}), encoding="utf-8")
    monkeypatch.setattr(renderer, "raiz_trabajo", lambda _usuario, _job: tmp_path)
    monkeypatch.setattr(renderer, "_reserved", set())
    estado = renderer.leer_estado("usuario", job)
    assert estado["estado"] == "fallido" and "interrumpido" in estado["motivo"]
