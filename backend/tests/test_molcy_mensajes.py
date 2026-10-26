"""Los mensajes de Molcy que ve el usuario no llevan jerga de desarrollo y existen en inglés.

# Qué se midió (2026-10-04)

Con el equipo sin Blender, la pantalla de Molcy decía «Renderizador no disponible: No se encontró Blender; configura
MOLCY_BLENDER_PATH.»: una variable de entorno que un investigador no puede fijar desde una aplicación de escritorio (y que el
instalador de Blender administrado ya hace innecesaria). Y de los mensajes de configuración, instalación y trabajo, sólo UNO
(«Esta versión de Molcy no admite paquetes de corrida.») tenía traducción: con el idioma en inglés la pantalla de configuración
estaba en español.

Esta prueba extrae por AST todo mensaje ESTÁTICO de los módulos de Molcy (el texto de cada `raise`, `HTTPException` y cada
`motivo` de un diccionario) y exige que tenga traducción, para que el mensaje que se añada mañana no vuelva a quedar fuera.
Los mensajes que se construyen con f-string o con `str(exc)` no son estáticos y no se miden aquí.
"""

import ast
import re
from pathlib import Path

import pytest

from core import i18n
from core.i18n_catalog import ENGLISH_MESSAGES

RAIZ = Path(__file__).resolve().parents[1]
MODULOS = ["services/molcy/renderer.py", "services/molcy/installation.py", "services/molcy/addon.py",
           "services/molcy/cierre.py", "api/routers/molcy.py", "services/molcy/gpu.py", "services/molcy/process.py", "services/molcy/cpu.py", "services/molcy/salidas.py",
           "services/molcy/fotos.py", "services/molcy/marca_foto.py"]
EXCEPCIONES = {"ValueError", "RuntimeError", "InterruptedError", "OSError", "KeyError"}
CLAVES_DE_MOTIVO = {"motivo", "motivo_cpu", "motivo_gpu", "motivo_foto", "motivo_foto_gpu"}
JERGA = re.compile(r"MOLCY_[A-Z_]+|MOLDESIGN_[A-Z_]+|LOCAL_DATA_DIR|\bPYTHONPATH\b|variable de entorno")


def mensajes_estaticos(fuente: str) -> set[str]:
    """Mensajes de texto fijo con significado (al menos una palabra con espacios) que el módulo muestra al usuario."""
    encontrados: set[str] = set()

    def texto(nodo):
        if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str) and " " in nodo.value.strip():
            encontrados.add(nodo.value)

    arbol = ast.parse(fuente)
    # Constantes de módulo que son mensajes por convención: `MENSAJE_...` (no cualquier MAYÚSCULAS: `OFFICIAL_REPOSITORY` lleva espacios).
    for nodo in arbol.body:
        if isinstance(nodo, ast.Assign) and any(isinstance(t, ast.Name) and t.id.startswith("MENSAJE_") for t in nodo.targets):
            texto(nodo.value)
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Call):
            nombre = getattr(nodo.func, "id", getattr(nodo.func, "attr", ""))
            if nombre in EXCEPCIONES and nodo.args:
                texto(nodo.args[0])
            elif nombre == "HTTPException":
                if len(nodo.args) > 1:
                    texto(nodo.args[1])
                for palabra in nodo.keywords:
                    if palabra.arg == "detail":
                        texto(palabra.value)
        elif isinstance(nodo, ast.Dict):
            for clave, valor in zip(nodo.keys, nodo.values):
                if isinstance(clave, ast.Constant) and clave.value in CLAVES_DE_MOTIVO:
                    texto(valor)
    return encontrados


def en_ingles(mensaje: str) -> str:
    token = i18n.set_request_locale("en-US")
    try:
        return i18n.translate_text(mensaje)
    finally:
        i18n.reset_request_locale(token)


# --- El extractor tiene que demostrar que ve (AGENTS.md, restricción 2) -------------------------------------------------

def test_el_extractor_ve_lo_que_debe_ver():
    fuente = '''
MENSAJE_SIN_CIERRE = "El acta no acredita el cierre"
OFFICIAL_REPOSITORY = 'url: "https://x/"'
def f():
    raise ValueError("Elige el blender.exe existente")
    raise RuntimeError("Blender no se instaló. Revisa el espacio")
    raise HTTPException(409, "Espera a que termine el render")
    raise HTTPException(status_code=404, detail="Trabajo no encontrado.")
    return {"disponible": False, "motivo": "No se encontró Blender aquí."}
    return {"motivo_cpu": "Actualiza el motor Molcy", "motivo_gpu": None}
'''
    assert mensajes_estaticos(fuente) == {
        "El acta no acredita el cierre", "Elige el blender.exe existente", "Blender no se instaló. Revisa el espacio",
        "Espera a que termine el render", "Trabajo no encontrado.", "No se encontró Blender aquí.", "Actualiza el motor Molcy"}


def test_el_extractor_ignora_lo_que_no_es_estatico_ni_es_mensaje():
    fuente = '''
def f(exc, n):
    raise HTTPException(409, str(exc))
    raise RuntimeError(f"Molcy terminó con código {n}; revisa render.log")
    raise ValueError("clave")
    otro = {"nombre": "esto no es un motivo de abstención"}
    log("Cualquier otra cosa con espacios")
'''
    assert mensajes_estaticos(fuente) == set()


def test_el_recorrido_encuentra_los_mensajes_de_verdad():
    total = {m for ruta in MODULOS for m in mensajes_estaticos((RAIZ / ruta).read_text(encoding="utf-8"))}
    assert len(total) >= 60, len(total)
    assert "Trabajo no encontrado." in total


# --- Lo que se exige ------------------------------------------------------------------------------------------------------

def _todos():
    return sorted({m for ruta in MODULOS for m in mensajes_estaticos((RAIZ / ruta).read_text(encoding="utf-8"))})


@pytest.mark.parametrize("mensaje", _todos())
def test_todo_mensaje_estatico_de_molcy_tiene_traduccion_y_no_lleva_jerga(mensaje: str):
    assert not JERGA.search(mensaje), f"jerga de desarrollo en un mensaje para el usuario: {mensaje!r}"
    ingles = en_ingles(mensaje)
    assert ingles != mensaje, f"sin traducción al inglés: {mensaje!r}"
    assert not re.search(r"[áéíóúñ¿¡]", ingles), f"la traducción conserva español: {ingles!r}"


def test_los_motivos_de_configuracion_dicen_que_hacer_sin_nombrar_variables():
    for es in ("No se encontró Blender. Descárgalo desde la configuración de abajo o elige tu blender.exe.",
               "No se encontró el motor Molcy. Elige su carpeta en la configuración de abajo."):
        assert es in _todos()
        assert not JERGA.search(es)
    assert "configura MOLCY_BLENDER_PATH" not in " ".join(_todos())
    assert "MOLCY_ENGINE_DIR" not in " ".join(_todos())


def test_las_traducciones_nuevas_no_pisan_ninguna_anterior():
    """El catálogo es un diccionario: un `update` repetido cambiaría en silencio el inglés de otra pantalla."""
    fuente = (RAIZ / "core" / "i18n_catalog.py").read_text(encoding="utf-8")
    inicio = fuente.index("# Molcy (2026-10-04)")
    desde = fuente[inicio:].split("\n", 2)[2]  # desde `ENGLISH_MESSAGES.update({`
    # El bloque termina en su propio `})`: detrás pueden venir los de otras tareas (el del dossier traducido, por ejemplo).
    cierre = desde.index("\n})") + len("\n})")
    bloque = ast.parse(desde[:cierre])
    claves = [k.value for n in ast.walk(bloque) if isinstance(n, ast.Dict) for k in n.keys]
    assert len(claves) == len(set(claves)), "claves repetidas dentro del bloque"
    anterior = ast.parse(fuente[:inicio])
    previas = [k.value for n in ast.walk(anterior) if isinstance(n, ast.Dict) for k in n.keys
               if isinstance(k, ast.Constant)]
    assert not set(claves) & set(previas), "el bloque pisa claves que ya tenían traducción"
    posterior = ast.parse(desde[cierre:])
    posteriores = [k.value for n in ast.walk(posterior) if isinstance(n, ast.Dict) for k in n.keys
                   if isinstance(k, ast.Constant)]
    assert not set(claves) & set(posteriores), "un bloque posterior pisa claves de Molcy"
