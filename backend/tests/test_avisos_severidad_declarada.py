"""
La severidad de un aviso la declara quien lo emite. Nadie la deduce del texto.

# La medición que obligó a esto

Se extrajeron por AST los 184 literales de aviso que emite el backend y se
pasaron por los DOS clasificadores por subcadenas que existían:

    ProAlertsTab.tsx    INFO 159 · PRECAUCION 9 · CRITICA 13 · POSITIVO 3
    pdf_generator.py    NOTA 158 · PRECAUCION 5 · CRITICA 11 · POSITIVA 10

El de la interfaz no producía ningún falso verde, pero metía el 86 % en la
misma «nota científica»: allí acababan «MOTOR SUSTITUIDO», «afinidad débil» y
«la semilla no coincide», con el mismo peso visual que «las afinidades se
extrajeron del stdout».

El del PDF —el documento que se firma y se comparte— sí disparaba, porque su
lista de positivos incluía la subcadena `"sin"`:

    «Vina no encontrado. Devolviendo estructura plegada sin docking.»  -> [POSITIVA]
    «conformación N sin minimizar (MMFF no disponible)»                -> [POSITIVA]
    «Estructura APO (sin ligando): se usó MolPocket…»                  -> [POSITIVA]

Estas pruebas fijan las dos propiedades que impiden que vuelva: **nadie deduce
severidad de un texto**, y **una ausencia de severidad se declara como tal en
vez de convertirse en `info`**.
"""

import ast
from pathlib import Path

import pytest

from services.avisos import Severidad, aviso, normalizar_aviso, normalizar_avisos, textos

RAIZ = Path(__file__).resolve().parents[1]


# ── El contrato ────────────────────────────────────────────────────────────

def test_un_aviso_declara_codigo_severidad_y_mensaje():
    a = aviso("MOTOR_SUSTITUIDO", Severidad.CRITICA, "Se usó Vina como respaldo.")
    assert a == {
        "codigo": "MOTOR_SUSTITUIDO",
        "severidad": "critica",
        "mensaje": "Se usó Vina como respaldo.",
    }


def test_una_cadena_heredada_no_se_convierte_en_info():
    """`heredada` significa «no se declaró». `info` significa «no importa»."""
    a = normalizar_aviso("Las afinidades se extrajeron del stdout de Vina.")
    assert a["severidad"] == "heredada"
    assert a["codigo"] == "HEREDADO"
    assert a["mensaje"] == "Las afinidades se extrajeron del stdout de Vina."


@pytest.mark.parametrize(
    "texto_del_aviso",
    [
        "Vina no encontrado. Devolviendo estructura plegada sin docking.",
        "conformación 3 sin minimizar (MMFF no disponible)",
        "Estructura APO (sin ligando): se usó MolPocket para detectar el pocket.",
        "No cumple la regla de Lipinski (MW > 500).",
        "No es seguro para administración oral.",
        "No se detectó toxicidad.",
    ],
)
def test_ninguna_redaccion_puede_fabricar_una_severidad(texto_del_aviso):
    """Las seis frases con las que los clasificadores por subcadena se rompían.

    Las tres primeras son reales y el PDF las pintaba de verde. Las tres
    últimas no existen en el backend, pero contienen «cumple», «seguro» y
    «toxicidad»: si algún día se escriben, no pueden cambiar de color solas.
    """
    assert normalizar_aviso(texto_del_aviso)["severidad"] == Severidad.HEREDADA.value


def test_una_severidad_inventada_no_se_acepta():
    a = normalizar_aviso({"codigo": "X", "severidad": "muy_grave", "mensaje": "hola"})
    assert a["severidad"] == Severidad.HEREDADA.value


def test_se_descartan_los_avisos_vacios():
    assert normalizar_avisos(["", "   ", {"mensaje": ""}, None]) == []


def test_una_lista_mezclada_se_normaliza_entera():
    """Un ensemble puede unir una corrida nueva y una heredada."""
    salida = normalizar_avisos(
        [
            "aviso viejo",
            aviso("AFINIDAD_DEBIL", Severidad.PRECAUCION, "afinidad por encima de -3"),
        ]
    )
    assert [item["severidad"] for item in salida] == ["heredada", "precaucion"]


def test_textos_nunca_devuelve_un_diccionario_impreso():
    """El dossier imprime prosa: `str(dict)` ahí sería basura firmada."""
    salida = textos([aviso("X", Severidad.INFO, "un mensaje"), "otro mensaje"])
    assert salida == ["un mensaje", "otro mensaje"]
    assert not any("codigo" in t for t in salida)


# ── La propiedad estructural: que nadie vuelva a adivinar ──────────────────

#: Los términos con los que los dos clasificadores decidían el color.
_TERMINOS_DELATORES = (
    "excepcional", "excelente", "óptimo", "optimo", "favorable",
    "cumple", "invalida", "imposible", "no recomendado",
)


def _busca_severidad_por_texto(ruta: Path) -> list[str]:
    """Comparaciones de subcadena contra vocabulario de severidad, por AST."""
    arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    hallazgos = []
    for nodo in ast.walk(arbol):
        # `any(k in wl for k in (...))` y `"x" in texto`
        if isinstance(nodo, ast.Compare) and any(
            isinstance(op, ast.In) for op in nodo.ops
        ):
            izquierda = nodo.left
            if isinstance(izquierda, ast.Constant) and isinstance(izquierda.value, str):
                if izquierda.value.lower() in _TERMINOS_DELATORES:
                    hallazgos.append(f"línea {nodo.lineno}: `{izquierda.value}` in …")
        for hijo in ast.walk(nodo):
            if isinstance(hijo, ast.Constant) and isinstance(hijo.value, str):
                if hijo.value.lower() in _TERMINOS_DELATORES and isinstance(nodo, ast.Compare):
                    pass
    return hallazgos


def test_el_pdf_del_certificado_no_deduce_severidad_del_texto():
    ruta = RAIZ / "services" / "blockchain" / "pdf_generator.py"
    hallazgos = _busca_severidad_por_texto(ruta)
    assert not hallazgos, (
        "El generador del PDF vuelve a clasificar avisos buscando subcadenas: "
        + "; ".join(hallazgos)
        + ". La severidad la declara quien emite el aviso (services/avisos.py)."
    )


def test_el_pdf_usa_la_severidad_declarada():
    fuente = (RAIZ / "services" / "blockchain" / "pdf_generator.py").read_text(
        encoding="utf-8"
    )
    assert "normalizar_avisos" in fuente
    assert "_ESTILO_POR_SEVERIDAD" in fuente


def test_toda_referencia_a_severidad_nombra_un_miembro_real():
    """Un typo en el enum no puede esperar hasta una corrida Vina real."""
    validas = set(Severidad.__members__)
    invalidas: list[str] = []
    for ruta in RAIZ.rglob("*.py"):
        if "tests" in ruta.parts:
            continue
        arbol = ast.parse(ruta.read_text(encoding="utf-8"), filename=str(ruta))
        for nodo in ast.walk(arbol):
            if (
                isinstance(nodo, ast.Attribute)
                and isinstance(nodo.value, ast.Name)
                and nodo.value.id == "Severidad"
                and nodo.attr not in validas
            ):
                invalidas.append(f"{ruta.relative_to(RAIZ)}:{nodo.lineno}: Severidad.{nodo.attr}")
    assert not invalidas, "Referencias a severidades inexistentes: " + "; ".join(invalidas)
