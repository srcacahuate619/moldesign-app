"""Carpeta de salida opcional de Molcy: «para todos los vídeos» y «para este vídeo».

Lo que se fija: el valor por defecto no cambia (caso o datos de MolDesign), sólo se escribe en carpetas que el
selector nativo registró, cada trabajo va a una carpeta NUEVA dentro de `MolDesign-Molcy`, el trabajo se vuelve a
encontrar por su índice, y el espacio que se muestra es el del disco elegido.
"""
import json
import uuid

import pytest

from services.molcy import disk, salidas, storage


@pytest.fixture
def entorno(tmp_path, monkeypatch):
    datos = tmp_path / "datos"
    datos.mkdir()
    monkeypatch.setattr(storage, "data_dir", lambda: datos)
    monkeypatch.setattr(salidas, "data_dir", lambda: datos)
    elegida = tmp_path / "otro_disco" / "videos"
    elegida.mkdir(parents=True)
    ident = str(uuid.uuid4())
    registro = tmp_path / "molcy-salidas.json"
    registro.write_text(json.dumps({"version": 1, "folders": {ident: str(elegida)}}), encoding="utf-8")
    monkeypatch.setenv("MOLDESIGN_MOLCY_OUTPUTS", str(registro))
    return {"usuario": str(uuid.uuid4()), "id": ident, "carpeta": elegida, "datos": datos}


def test_sin_eleccion_nada_cambia(entorno):
    assert salidas.elegir(entorno["usuario"], None) is None


def test_este_video_gana_a_todos_y_predeterminada_la_ignora(entorno):
    salidas.fijar_preferencia(entorno["usuario"], entorno["id"])
    assert salidas.elegir(entorno["usuario"], None)["id"] == entorno["id"]
    assert salidas.elegir(entorno["usuario"], salidas.PREDETERMINADA) is None
    salidas.fijar_preferencia(entorno["usuario"], None)
    assert salidas.elegir(entorno["usuario"], None) is None


def test_una_carpeta_que_el_selector_no_registro_se_rechaza(entorno, tmp_path):
    with pytest.raises(ValueError, match="autorizada"):
        salidas.carpeta(str(uuid.uuid4()))
    with pytest.raises(ValueError):
        salidas.carpeta(str(tmp_path))  # una ruta no es un id
    with pytest.raises(ValueError):
        salidas.fijar_preferencia(entorno["usuario"], str(uuid.uuid4()))


def test_sin_registro_de_escritorio_no_hay_carpetas(entorno, monkeypatch):
    monkeypatch.delenv("MOLDESIGN_MOLCY_OUTPUTS")
    assert salidas.disponible() is False
    with pytest.raises(ValueError):
        salidas.carpeta(entorno["id"])


def test_crear_raiz_en_la_carpeta_elegida_y_reencontrarla(entorno):
    job = str(uuid.uuid4())
    raiz = storage.crear_raiz(entorno["usuario"], job, None, "Receptor Ñandú", "1HSG", None,
                              salida=salidas.carpeta(entorno["id"]))
    assert raiz.parent == (entorno["carpeta"] / salidas.SUBCARPETA).resolve()
    assert raiz.name.startswith("001_receptor_nandu_1HSG_") and raiz.is_dir()
    assert storage.raiz_trabajo(entorno["usuario"], job).resolve() == raiz.resolve()
    # El segundo trabajo es otra carpeta nueva: nunca se reutiliza ni se pisa.
    otro = storage.crear_raiz(entorno["usuario"], str(uuid.uuid4()), None, "x", "1HSG", None,
                              salida=salidas.carpeta(entorno["id"]))
    assert otro != raiz and otro.name.startswith("002_")
    storage.validar_raiz(entorno["usuario"], job, raiz)
    storage.retirar_indice(entorno["usuario"], job)


def test_si_el_disco_desaparece_el_trabajo_lo_dice(entorno):
    job = str(uuid.uuid4())
    storage.crear_raiz(entorno["usuario"], job, None, "x", "1HSG", None, salida=salidas.carpeta(entorno["id"]))
    import shutil
    shutil.rmtree(entorno["carpeta"])
    with pytest.raises(ValueError, match="no está disponible"):
        storage.raiz_trabajo(entorno["usuario"], job)


def test_el_espacio_es_el_del_disco_elegido(entorno, monkeypatch):
    from api.routers import molcy

    vistos = []
    monkeypatch.setattr(disk, "budget", lambda ruta, nombre, dispositivo="gpu":
                        vistos.append(ruta) or {"libre_bytes": 1, "necesario_bytes": 1, "disponible": True})
    monkeypatch.setattr(disk, "assert_brand_budget", lambda *a, **k: None)
    resultado = molcy._espacio(entorno["usuario"], None, entorno["id"])
    assert resultado["espacio_salida_id"] == entorno["id"]
    assert set(vistos) == {entorno["carpeta"].resolve()}
    # Una carpeta que ya no existe no da una cifra inventada: bloquea y explica.
    malo = molcy._espacio(entorno["usuario"], None, str(uuid.uuid4()))
    assert malo["espacio"] is None and "autorizada" in malo["espacio_motivo"]
