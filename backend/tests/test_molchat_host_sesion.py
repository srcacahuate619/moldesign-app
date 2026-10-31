"""Sesiones mh1 del host: formato clavado, acuñado honesto, verificaciónestricta.

El vector dorado es un token acuñado con entradas fijas, comprobado a mano
contra `molchat_agent.server.auth.verify` (el sidecar lo acepta con la
misma identidad, permisos y caducidad): si este test pasa, ambos lados
hablan el mismo formato byte a byte.
"""

import base64
import hashlib
import hmac
import json

import pytest

from services.molchat_host import sesion

SECRETO = b"test-secret-32-bytes-0123456789ab"
AHORA = 1798765432
DORADO = ("mh1.eyJzdWIiOiJjdWVudGEtMSIsInNjb3BlcyI6WyJjaGF0IiwicmVhZCJdLCJleHAi"
          "OjE3OTg3NjYwMzIsImp0aSI6IjAxMjM0NTY3ODlhYmNkZWYiLCJhdWQiOiJtb2xjaGF0"
          "In0=.SvxzoCkg9xL0ErSn1ar7DkiKm4Yvpl5ppTBZRNTi9I8=")


@pytest.fixture(autouse=True)
def _secreto():
    sesion.fijar_secreto_host(SECRETO)
    yield
    sesion.fijar_secreto_host(SECRETO)


def test_vector_dorado_clava_el_formato():
    token = sesion.acunar("cuenta-1", {"chat", "read"}, 600, ahora=AHORA,
                          jti="0123456789abcdef")
    assert token == DORADO


def test_ida_y_vuelta_conserva_identidad_y_permisos():
    token = sesion.acunar("cuenta-1", ["approve", "chat"], 60, ahora=AHORA)
    visto = sesion.verificar_para_plataforma(token, ahora=AHORA)
    assert visto is not None
    assert visto["sub"] == "cuenta-1"
    assert visto["scopes"] == ["approve", "chat"]
    assert visto["exp"] == AHORA + 60


def _firmar(cuerpo: str) -> str:
    firma = hmac.new(SECRETO, cuerpo.encode("ascii"), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(firma).decode("ascii")


def _forjar(carga: dict) -> str:
    crudo = base64.urlsafe_b64encode(
        json.dumps(carga, separators=(",", ":")).encode("ascii")).decode("ascii")
    cuerpo = f"mh1.{crudo}"
    return f"{cuerpo}.{_firmar(cuerpo)}"


def test_verificacion_rechaza_todo_lo_malo():
    base = {"sub": "cuenta-1", "scopes": ["read"], "exp": AHORA + 60,
            "jti": "abc123", "aud": "molchat"}
    assert sesion.verificar_para_plataforma(_forjar(base), ahora=AHORA) is not None
    assert sesion.verificar_para_plataforma(
        _forjar({**base, "aud": "otro"}), ahora=AHORA) is None
    assert sesion.verificar_para_plataforma(
        _forjar({**base, "scopes": ["root"]}), ahora=AHORA) is None
    assert sesion.verificar_para_plataforma(
        _forjar({**base, "scopes": []}), ahora=AHORA) is None
    assert sesion.verificar_para_plataforma(
        _forjar({**base, "exp": AHORA}), ahora=AHORA) is None
    assert sesion.verificar_para_plataforma(
        _forjar({**base, "sub": "  "}), ahora=AHORA) is None
    assert sesion.verificar_para_plataforma(DORADO[:-2] + "xx", ahora=AHORA) is None
    assert sesion.verificar_para_plataforma("basura", ahora=AHORA) is None
    assert sesion.verificar_para_plataforma("", ahora=AHORA) is None


def test_sin_secreto_no_hay_ni_acunar_ni_verificar(monkeypatch):
    monkeypatch.setattr(sesion, "_SECRETO_HOST", None)
    with pytest.raises(sesion.SesionMolChatError):
        sesion.acunar("cuenta-1", {"read"}, 60)
    assert sesion.verificar_para_plataforma(DORADO) is None


def test_acunar_rechaza_entradas_malas():
    with pytest.raises(sesion.SesionMolChatError):
        sesion.acunar("  ", {"read"}, 60)
    with pytest.raises(sesion.SesionMolChatError):
        sesion.acunar("cuenta-1", set(), 60)
    with pytest.raises(sesion.SesionMolChatError):
        sesion.acunar("cuenta-1", {"root"}, 60)
    with pytest.raises(sesion.SesionMolChatError):
        sesion.acunar("cuenta-1", {"read"}, 0)
