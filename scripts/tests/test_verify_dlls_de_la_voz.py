"""Las dos DLL que paraban `verify:desktop-runtime` desde que la voz entró en el runtime (2026-11-15).

    python -m pytest scripts/tests/test_verify_dlls_de_la_voz.py -q

`onnxruntime` pide `msvcp140_1.dll` y `av` pide `avicap32.dll`. La primera NO es de Windows en una máquina limpia (la trae el
redistribuible de VC++) y por eso se empaqueta desde `tools/vc-runtime/`; la segunda sí es del sistema. La guarda no debe
aflojarse por esto: lo que no es de Windows y no viaja tiene que seguir fallando.
"""

from __future__ import annotations

import json
from pathlib import Path

import verify_desktop_bundle as vdb

RAIZ = Path(__file__).resolve().parents[2]


def test_avicap32_es_del_sistema_y_msvcp140_1_no():
    assert vdb._es_de_windows("avicap32.dll")
    # No es de Windows: si no viaja con el bundle, la guarda tiene que seguir señalándola.
    assert not vdb._es_de_windows("msvcp140_1.dll")
    assert not vdb._es_de_windows("onnxruntime_providers_shared.dll")


def test_msvcp140_1_viaja_en_tools_vc_runtime_con_su_manifiesto():
    manifiesto = json.loads((RAIZ / "tools" / "vc-runtime" / "vc-runtime-manifest.json").read_text(encoding="utf-8"))
    assert "msvcp140_1.dll" in manifiesto["files"]
    assert manifiesto["files"]["msvcp140_1.dll"]["file_version"] == manifiesto["version"] + ".0"
    assert (RAIZ / "tools" / "vc-runtime" / "x64" / "msvcp140_1.dll").is_file()


def test_la_guarda_sigue_viendo_una_dll_que_no_es_de_windows_ni_viaja():
    """Control negativo: una DLL cualquiera ajena a Windows no queda cubierta por la lista."""
    for nombre in ("msvcp140_2.dll", "libfoo.dll", "vcamp140.dll"):
        assert not vdb._es_de_windows(nombre), nombre
