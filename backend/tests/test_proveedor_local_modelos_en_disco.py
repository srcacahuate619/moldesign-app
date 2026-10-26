"""El proveedor local declara los modelos que el backend puede cargar.

EL FALLO. MolChat enseñaba «Modelo LLM no descargado» con un modelo en disco
que el motor local sí cargaba. La interfaz lo decidía mirando el destino de la
descarga de Tauri —con el SHA-256 de Qwen2.5 1.5B—, que en `tauri dev` no es
donde busca el backend, y que además ignora cualquier otro `.gguf` elegido. El
dato que decide es la lista de `.gguf` en `MODEL_SEARCH_PATHS`, y viaja en
`available_models` del proveedor local.
"""
from __future__ import annotations

import pytest

from services.ai import local_llm
from services.ai.providers.local_llm_provider import LocalLLMProvider


@pytest.fixture
def rutas(tmp_path, monkeypatch):
    primera, segunda = tmp_path / "repo" / "models" / "llm", tmp_path / "home" / "models" / "llm"
    primera.mkdir(parents=True)
    segunda.mkdir(parents=True)
    monkeypatch.setattr(local_llm, "MODEL_SEARCH_PATHS", [primera, segunda])
    return primera, segunda


def test_lista_los_gguf_de_todas_las_rutas_de_busqueda(rutas):
    primera, segunda = rutas
    (primera / "qwen2.5-1.5b-instruct-q4_k_m.gguf").write_bytes(b"x")
    (segunda / "Qwen3.5-4B-Q4_K_M.gguf").write_bytes(b"x")
    # Una descarga a medias no es un modelo que se pueda cargar.
    (segunda / "Otro-Q4_K_M.gguf.part").write_bytes(b"x")

    info = LocalLLMProvider().get_info()

    assert sorted(info.available_models) == [
        "Qwen3.5-4B-Q4_K_M.gguf",
        "qwen2.5-1.5b-instruct-q4_k_m.gguf",
    ]


def test_sin_gguf_la_lista_queda_vacia(rutas):
    info = LocalLLMProvider().get_info()

    assert info.available_models == []
    assert info.default_model == ""
