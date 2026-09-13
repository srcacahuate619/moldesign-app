"""
El mensaje de MolChat cuando no puede responder.

En la maquina limpia decia, siempre y con independencia de la causa real:

    MolChat Local no está configurado. llama-server.exe no está disponible.
    Verificá que el binario existe en tools/llama-cuda/ (build CUDA) o
    tools/llama/ (fallback CPU) y que hay RAM suficiente (mínimo 4 GB libre).

    Detalles: docs/33_MIGRATION_LLAMA_SERVER.md

Tres cosas mal, por orden de gravedad:

1. ERA FALSO. El instalador SI empaqueta `tools/llama/llama-server.exe`; lo que
   no empaqueta es ningun `.gguf` —los modelos se descargan desde Opciones—.
   La comprobacion que fallaba era la del modelo, y el mensaje mandaba al
   usuario a buscar un binario que estaba en su sitio.
2. `tools/llama-cuda/` NI SIQUIERA VIAJA en el paquete.
3. Citaba una ruta de documentacion interna que el usuario no tiene.
"""

import pytest

from services.ai import local_llm


class _SinBinario(FileNotFoundError):
    pass


def test_falta_el_binario_se_dice_sin_mandar_a_buscar_rutas(monkeypatch):
    monkeypatch.setattr(
        local_llm,
        "_resolve_server_executable_static",
        lambda: (_ for _ in ()).throw(FileNotFoundError("no esta")),
    )
    ok, motivo = local_llm.diagnosticar_llm_local()
    assert ok is False
    assert "no está instalado" in motivo
    assert "tools/" not in motivo
    assert "docs/" not in motivo


def test_falta_el_modelo_no_se_acusa_al_binario(monkeypatch):
    """La causa real en una instalacion limpia. Es la que salia mal."""
    monkeypatch.setattr(local_llm, "_resolve_server_executable_static", lambda: "ok")
    monkeypatch.setattr(
        local_llm.LocalLLM,
        "_resolve_model_path_static",
        staticmethod(lambda: (_ for _ in ()).throw(FileNotFoundError("sin gguf"))),
    )
    ok, motivo = local_llm.diagnosticar_llm_local()
    assert ok is False
    assert "modelo" in motivo.lower()
    assert "llama-server" not in motivo
    assert "Opciones" in motivo
    # Y se dice que el resto de la aplicacion no depende de esto.
    assert "sin él" in motivo


def test_falta_memoria_se_dice_con_la_cifra(monkeypatch):
    monkeypatch.setattr(local_llm, "_resolve_server_executable_static", lambda: "ok")
    monkeypatch.setattr(
        local_llm.LocalLLM, "_resolve_model_path_static", staticmethod(lambda: "modelo.gguf")
    )

    from services.ai import resource_manager

    class _RM:
        def _get_ram_free_gb(self):
            return 1.5

    monkeypatch.setattr(resource_manager, "get_resource_manager", lambda: _RM())
    ok, motivo = local_llm.diagnosticar_llm_local()
    assert ok is False
    assert "1.5" in motivo
    assert "memoria" in motivo.lower()


def test_todo_en_su_sitio(monkeypatch):
    monkeypatch.setattr(local_llm, "_resolve_server_executable_static", lambda: "ok")
    monkeypatch.setattr(
        local_llm.LocalLLM, "_resolve_model_path_static", staticmethod(lambda: "modelo.gguf")
    )

    from services.ai import resource_manager

    class _RM:
        def _get_ram_free_gb(self):
            return 32.0

    monkeypatch.setattr(resource_manager, "get_resource_manager", lambda: _RM())
    assert local_llm.diagnosticar_llm_local() == (True, "OK")


@pytest.mark.parametrize(
    "escenario",
    ["binario", "modelo", "memoria"],
)
def test_ningun_mensaje_filtra_documentacion_interna(monkeypatch, escenario):
    """La regla, sin excepciones: nada de `docs/` en un texto que lee el usuario."""
    monkeypatch.setattr(local_llm, "_resolve_server_executable_static", lambda: "ok")
    monkeypatch.setattr(
        local_llm.LocalLLM, "_resolve_model_path_static", staticmethod(lambda: "modelo.gguf")
    )
    from services.ai import resource_manager

    class _RM:
        def _get_ram_free_gb(self):
            return 32.0

    monkeypatch.setattr(resource_manager, "get_resource_manager", lambda: _RM())

    if escenario == "binario":
        monkeypatch.setattr(
            local_llm,
            "_resolve_server_executable_static",
            lambda: (_ for _ in ()).throw(FileNotFoundError()),
        )
    elif escenario == "modelo":
        monkeypatch.setattr(
            local_llm.LocalLLM,
            "_resolve_model_path_static",
            staticmethod(lambda: (_ for _ in ()).throw(FileNotFoundError())),
        )
    else:
        class _Poca:
            def _get_ram_free_gb(self):
                return 0.5

        monkeypatch.setattr(resource_manager, "get_resource_manager", lambda: _Poca())

    _, motivo = local_llm.diagnosticar_llm_local()
    assert "docs/" not in motivo
    assert ".md" not in motivo
    assert "llama-cuda" not in motivo
