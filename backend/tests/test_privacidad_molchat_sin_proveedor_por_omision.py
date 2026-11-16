"""B-7 (revisión final 1.0.4): la política de privacidad no puede afirmar que MolChat
corre con un modelo local «por omisión» mientras el asistente no tenga ningún proveedor
activo hasta que la persona elige uno.

Qwen2.5 1.5B es el modelo local del intérprete de informes (`services/llm/local_llm.py`),
no el de MolChat: `registry.py` arranca con `active_id=None` y el motor se abstiene con
«No hay proveedor de IA activo». Las tres copias del texto (raíz, la que viaja en el
paquete y la página pública) tienen que decir lo mismo y decirlo bien.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

COPIAS = {
    "PRIVACY.md": ROOT / "PRIVACY.md",
    "frontend/public/legal/PRIVACY.md": ROOT / "frontend" / "public" / "legal" / "PRIVACY.md",
    "site/privacy/index.html": ROOT / "site" / "privacy" / "index.html",
}

# Lo que una copia no puede decir: un modelo local «por omisión» para el asistente.
AFIRMACION_FALSA = re.compile(
    r"(por omisi[oó]n,? el modelo es local|by default,? the model is local)", re.IGNORECASE
)
# Lo que sí tiene que decir, en cada idioma que lleve la copia.
LECTURA_VERDADERA = (
    re.compile(r"no trae un proveedor de IA activo por omisi[oó]n"),
    re.compile(r"has no active AI provider by default"),
)


def incumplimientos(texto: str) -> list[str]:
    fallos = []
    if AFIRMACION_FALSA.search(texto):
        fallos.append("afirma un modelo local por omisión")
    if not any(patron.search(texto) for patron in LECTURA_VERDADERA):
        fallos.append("no dice que MolChat no trae proveedor activo por omisión")
    return fallos


def test_las_copias_de_la_politica_no_prometen_un_modelo_local_por_omision():
    for nombre, ruta in COPIAS.items():
        texto = ruta.read_text(encoding="utf-8")
        assert incumplimientos(texto) == [], f"{nombre}: {incumplimientos(texto)}"


def test_la_guardia_demuestra_que_ve():
    """Control negativo: el texto anterior, tal cual estuvo, tiene que fallar."""
    anterior_es = "Por omisión, el modelo es local (Qwen2.5 1.5B) y la conversación no sale del equipo."
    anterior_en = "By default, the model is local (Qwen2.5 1.5B) and the conversation does not leave the device."
    assert "afirma un modelo local por omisión" in incumplimientos(anterior_es)
    assert "afirma un modelo local por omisión" in incumplimientos(anterior_en)
    bueno = "MolChat no trae un proveedor de IA activo por omisión: hasta que la persona elige uno, no responde."
    assert incumplimientos(bueno) == []


def test_las_copias_de_privacy_md_son_la_misma():
    assert COPIAS["PRIVACY.md"].read_bytes().replace(b"\r\n", b"\n") == (
        COPIAS["frontend/public/legal/PRIVACY.md"].read_bytes().replace(b"\r\n", b"\n")
    )


def test_el_motivo_sigue_siendo_cierto_en_molchat():
    """Si MolChat vuelve a traer un proveedor por defecto, esta prueba obliga a revisar el texto."""
    registro = (ROOT / "tools" / "molchat" / "src" / "molchat_agent" / "providers" / "registry.py").read_text(
        encoding="utf-8"
    )
    motor = (ROOT / "tools" / "molchat" / "src" / "molchat_agent" / "conversation" / "engine.py").read_text(
        encoding="utf-8"
    )
    assert "sin proveedor de IA activo" in registro
    assert "no hay proveedor de IA activo" in motor
