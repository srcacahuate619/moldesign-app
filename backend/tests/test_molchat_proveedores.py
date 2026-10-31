"""Proveedores de IA por cuenta: catálogo verificado, claves cifradas y autorización por destino.

Lo que se prueba es la frontera, no la química: ninguna respuesta lleva una clave,
cada cuenta ve sólo lo suyo, la clave sólo sale hacia el host autorizado y sólo al
sidecar, y MolDesign no guarda nada fuera de `provider_config_store`.
El almacén se aísla en un directorio temporal: nunca toca `~/.moldesign`.
"""

import json
import secrets
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.dependencies import get_current_user
from api.routers import molchat_host
from services import provider_config_store as pcs
from services.molchat_host import launcher, proveedores

CLAVE = "sk-prueba-0123456789abcdef7890"

CATALOGO = {
    "schema": "moldesign.molchat-catalogo/1",
    "proveedores": [
        {"id": "openai", "nombre": "OpenAI", "familia": "openai_chat",
         "base_url": "https://api.openai.com/v1", "remoto": True, "requiere_clave": True,
         "modelo_por_defecto": "", "modelos_ejemplo": ["gpt-4o-mini"], "prefijo_clave": "sk-",
         "documentacion": "https://platform.openai.com/docs", "que_sale": "El texto del chat."},
        {"id": "deepseek", "nombre": "DeepSeek", "familia": "openai_chat",
         "base_url": "https://api.deepseek.com", "remoto": True, "requiere_clave": True,
         "modelo_por_defecto": "deepseek-flash", "modelos_ejemplo": [],
         "documentacion": "https://api-docs.deepseek.com/", "que_sale": "El texto del chat."},
        {"id": "llama-server", "nombre": "llama-server", "familia": "openai_chat",
         "base_url": "http://127.0.0.1:8400/v1", "remoto": False, "requiere_clave": False,
         "modelo_por_defecto": "", "modelos_ejemplo": [], "que_sale": "Nada: corre en esta máquina."},
    ],
}


def _copia_con_catalogo(carpeta: Path, catalogo: dict) -> Path:
    ruta = carpeta / proveedores.CATALOGO_RELATIVO
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(catalogo), encoding="utf-8")
    return carpeta


@pytest.fixture
def almacen(tmp_path, monkeypatch):
    """Almacén de claves y copia de MolChat verificada, ambos en un directorio temporal."""
    store = tmp_path / "store"
    store.mkdir()
    (store / "secret_key").write_text(secrets.token_hex(32), encoding="utf-8")
    monkeypatch.setattr(pcs, "_STORE_DIR", store)
    monkeypatch.setattr(pcs, "_STORE_FILE", store / "provider_config.json")
    monkeypatch.setattr(pcs, "_SECRET_KEY_FILE", store / "secret_key")
    monkeypatch.setattr(pcs, "_fernet_cache", None)
    copia = _copia_con_catalogo(tmp_path / "copia", CATALOGO)
    monkeypatch.setattr(launcher, "localizar", lambda: (copia, "ok"))
    return copia


def _cuenta(valor: str = "") -> str:
    return valor or str(uuid.uuid4())


def test_catalogo_acepta_lo_valido_y_rechaza_lo_inseguro(tmp_path):
    copia = _copia_con_catalogo(tmp_path / "ok", CATALOGO)
    hosts = {e["id"]: e["host"] for e in proveedores.leer_catalogo(copia)}
    assert hosts == {"openai": "api.openai.com", "deepseek": "api.deepseek.com",
                     "llama-server": "127.0.0.1"}

    def rechaza(cambio):
        catalogo = json.loads(json.dumps(CATALOGO))
        cambio(catalogo["proveedores"])
        with pytest.raises(ValueError):
            proveedores.leer_catalogo(_copia_con_catalogo(tmp_path / secrets.token_hex(4), catalogo))

    rechaza(lambda p: p[0].update(base_url="http://api.openai.com/v1"))        # remoto sin https
    rechaza(lambda p: p[0].update(base_url="https://127.0.0.1/v1"))            # remoto en loopback
    rechaza(lambda p: p[2].update(base_url="http://10.0.0.5:8400/v1"))         # local fuera de la máquina
    rechaza(lambda p: p[0].update(familia="desconocida"))                      # familia sin adaptador
    rechaza(lambda p: p[1].update(id="openai"))                                # id repetido
    rechaza(lambda p: p[0].update(id="No Válido"))                             # id con mayúsculas


def test_estado_nunca_devuelve_la_clave(almacen):
    cuenta = _cuenta()
    proveedores.guardar_y_autorizar(cuenta, "openai", CLAVE, "api.openai.com")
    estado = proveedores.estado(cuenta)
    texto = json.dumps(estado)
    assert CLAVE not in texto and "0123456789abcdef" not in texto
    fila = next(f for f in estado["proveedores"] if f["id"] == "openai")
    assert fila["clave"] == {"configurada": True, "pista": "••••7890"}
    assert fila["autorizado"] is True and fila["host"] == "api.openai.com"
    assert fila["modelo"] == ""  # el catálogo de la prueba no fija modelo por defecto para OpenAI


def test_guardar_exige_el_host_que_se_mostro(almacen):
    cuenta = _cuenta()
    with pytest.raises(proveedores.ProveedorError) as exc:
        proveedores.guardar_y_autorizar(cuenta, "openai", CLAVE, "evil.example")
    assert exc.value.estado == 409
    assert exc.value.detalle["motivo"] == "destino_cambiado"
    assert proveedores.estado(cuenta)["proveedores"][0]["clave"]["configurada"] is False


def test_guardar_valida_formato_y_local_no_pide_clave(almacen):
    cuenta = _cuenta()
    with pytest.raises(proveedores.ProveedorError) as exc:
        proveedores.guardar_y_autorizar(cuenta, "openai", "corta", "api.openai.com")
    assert exc.value.estado == 422
    with pytest.raises(proveedores.ProveedorError) as exc:
        proveedores.guardar_y_autorizar(cuenta, "llama-server", CLAVE, "127.0.0.1")
    assert exc.value.estado == 400


def test_credencial_solo_con_clave_y_autorizacion(almacen):
    cuenta = _cuenta()
    with pytest.raises(proveedores.ProveedorError) as exc:
        proveedores.credencial(cuenta, "openai", "api.openai.com")
    assert exc.value.detalle["motivo"] == "sin_clave"
    proveedores.guardar_y_autorizar(cuenta, "openai", CLAVE, "api.openai.com")
    entrega = proveedores.credencial(cuenta, "openai", "api.openai.com")
    assert entrega["api_key"] == CLAVE and entrega["proveedor"] == "openai"
    pcs.borrar_consentimientos_de(cuenta, "openai")  # la autorización ya no existe
    with pytest.raises(proveedores.ProveedorError) as exc:
        proveedores.credencial(cuenta, "openai", "api.openai.com")
    assert exc.value.detalle["motivo"] == "sin_autorizacion"


def test_credencial_nunca_va_a_otro_host(almacen):
    cuenta = _cuenta()
    proveedores.guardar_y_autorizar(cuenta, "openai", CLAVE, "api.openai.com")
    with pytest.raises(proveedores.ProveedorError) as exc:
        proveedores.credencial(cuenta, "openai", "evil.example")
    assert exc.value.estado == 403 and exc.value.detalle["motivo"] == "destino_distinto"


def test_las_claves_son_de_cada_cuenta(almacen):
    ana, luis = _cuenta(), _cuenta()
    proveedores.guardar_y_autorizar(ana, "openai", CLAVE, "api.openai.com")
    assert proveedores.estado(luis)["proveedores"][0]["clave"]["configurada"] is False
    with pytest.raises(proveedores.ProveedorError) as exc:
        proveedores.credencial(luis, "openai", "api.openai.com")
    assert exc.value.detalle["motivo"] == "sin_clave"


def test_retirar_la_clave_revoca_todo(almacen):
    cuenta = _cuenta()
    proveedores.guardar_y_autorizar(cuenta, "openai", CLAVE, "api.openai.com")
    proveedores.elegir_activo(cuenta, "openai")
    proveedores.retirar_clave(cuenta, "openai")
    estado = proveedores.estado(cuenta)
    assert estado["activo"] is None
    assert estado["proveedores"][0]["clave"]["configurada"] is False
    assert estado["proveedores"][0]["autorizado"] is False
    assert pcs.cargar_consentimientos(cuenta) == {}


def test_elegir_activo_exige_clave_y_autorizacion(almacen):
    cuenta = _cuenta()
    with pytest.raises(proveedores.ProveedorError) as exc:
        proveedores.elegir_activo(cuenta, "openai")
    assert exc.value.detalle["motivo"] == "sin_clave"
    proveedores.guardar_y_autorizar(cuenta, "openai", CLAVE, "api.openai.com")
    assert proveedores.elegir_activo(cuenta, "openai")["activo"] == "openai"
    assert proveedores.elegir_activo(cuenta, None)["activo"] is None


def test_local_no_necesita_clave_para_el_sidecar(almacen):
    cuenta = _cuenta()
    entrega = proveedores.credencial(cuenta, "llama-server", "127.0.0.1")
    assert entrega["api_key"] is None and entrega["proveedor"] == "llama-server"


def test_sin_llave_disponible_se_declara(monkeypatch, almacen):
    monkeypatch.setattr(launcher, "localizar", lambda: (None, "sin sidecar incluido"))
    estado = proveedores.estado(_cuenta())
    assert estado == {"disponible": False, "motivo": "sin sidecar incluido",
                      "activo": None, "proveedores": []}
    with pytest.raises(proveedores.ProveedorError) as exc:
        proveedores.guardar_y_autorizar(_cuenta(), "openai", CLAVE, "api.openai.com")
    assert exc.value.estado == 503


@pytest.fixture
def cliente(almacen):
    app = FastAPI()
    app.include_router(molchat_host.router)
    usuario = SimpleNamespace(id=uuid.uuid4())
    app.dependency_overrides[get_current_user] = lambda: usuario
    cliente = TestClient(app)
    cliente.usuario = usuario
    return cliente


def test_la_api_no_devuelve_la_clave_en_ningun_paso(cliente):
    cuerpo = {"api_key": CLAVE, "host_visto": "api.openai.com"}
    respuesta = cliente.put("/molchat-host/proveedores/openai/clave", json=cuerpo)
    assert respuesta.status_code == 200
    assert CLAVE not in respuesta.text
    assert CLAVE not in cliente.get("/molchat-host/proveedores").text


def test_credencial_solo_con_sesion_del_sidecar(cliente):
    cliente.put("/molchat-host/proveedores/openai/clave",
                json={"api_key": CLAVE, "host_visto": "api.openai.com"})
    cuerpo = {"proveedor": "openai", "host": "api.openai.com"}
    assert cliente.post("/molchat-host/credencial", json=cuerpo).status_code == 403
    desde_sidecar = cliente.post("/molchat-host/credencial", json=cuerpo,
                                 headers={"Authorization": "Bearer mh1.sesion-de-prueba"})
    assert desde_sidecar.status_code == 200
    assert desde_sidecar.json()["api_key"] == CLAVE


def test_activo_y_retirada_por_la_api(cliente):
    cliente.put("/molchat-host/proveedores/openai/clave",
                json={"api_key": CLAVE, "host_visto": "api.openai.com"})
    activo = cliente.put("/molchat-host/proveedores/activo", json={"proveedor": "openai"})
    assert activo.status_code == 200 and activo.json()["activo"] == "openai"
    retirada = cliente.delete("/molchat-host/proveedores/openai/clave")
    assert retirada.status_code == 200 and retirada.json()["activo"] is False
    assert retirada.json()["clave"] == {"configurada": False, "pista": "••••"}
    assert cliente.put("/molchat-host/proveedores/activo",
                       json={"proveedor": "openai"}).status_code == 409


def test_campos_desconocidos_se_rechazan(cliente):
    respuesta = cliente.put("/molchat-host/proveedores/openai/clave",
                            json={"api_key": CLAVE, "host_visto": "api.openai.com", "url": "x"})
    assert respuesta.status_code == 422


@pytest.mark.skipif(not (Path(__file__).resolve().parents[2] / "tools" / "molchat").is_dir(),
                    reason="sin copia de MolChat vendorizada")
def test_el_catalogo_de_la_copia_real_trae_openai_primero():
    real = Path(__file__).resolve().parents[2] / "tools" / "molchat"
    if not (real / proveedores.CATALOGO_RELATIVO).is_file():
        pytest.skip("la copia vendorizada aún no trae catálogo de proveedores")
    entradas = proveedores.leer_catalogo(real)
    assert entradas[0]["id"] == "openai" and entradas[0]["host"] == "api.openai.com"
    deepseek = next(e for e in entradas if e["id"] == "deepseek")
    assert deepseek["host"] == "api.deepseek.com"
