"""
Un `async def` que llama a un cálculo síncrono largo para el backend entero.

MM-GBSA minimiza con OpenMM: de decenas de segundos a varios minutos. El
endpoint `POST /pro/mmgbsa/{molecule_id}` es `async def` y llamaba
`compute_mmgbsa_from_pose(...)` directamente, es decir DENTRO del bucle de
eventos. Mientras duraba, uvicorn no atendía nada más: ni el sondeo del trabajo
que hace la pestaña cada 2 s, ni `/health`, ni el dossier. La aplicación
parecía colgada, y el fallo real —fuera el que fuera— quedaba escondido detrás
de esa parálisis.

La prueba es estructural a propósito. Medir «no bloquea» de verdad exigiría
levantar el servidor y correr una minimización; lo que hace falta garantizar es
más simple y se puede comprobar leyendo el árbol sintáctico: que la llamada cara
no cuelgue directamente de una corrutina.
"""

import ast
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]

#: (módulo, función cara). Cada una tarda minutos y no puede correr en el bucle.
LLAMADAS_CARAS = [
    ("api/routers/pro_features.py", "compute_mmgbsa_from_pose"),
]


def _corrutinas(arbol: ast.AST) -> list[ast.AsyncFunctionDef]:
    return [n for n in ast.walk(arbol) if isinstance(n, ast.AsyncFunctionDef)]


def _nombre_llamado(nodo: ast.Call) -> str:
    objetivo = nodo.func
    if isinstance(objetivo, ast.Name):
        return objetivo.id
    if isinstance(objetivo, ast.Attribute):
        return objetivo.attr
    return ""


def _llamadas_directas(corrutina: ast.AsyncFunctionDef, nombre: str) -> list[ast.Call]:
    """Llamadas a `nombre` que NO están envueltas en un `await` de descarga.

    Una llamada válida aparece como argumento de `run_sync`/`to_thread`, casi
    siempre dentro de un `functools.partial`; entonces el nodo `Call` de la
    función cara no se ejecuta ahí, sólo se construye el parcial.
    """
    envueltas: set[int] = set()
    for nodo in ast.walk(corrutina):
        if not isinstance(nodo, ast.Call):
            continue
        if _nombre_llamado(nodo) not in {"run_sync", "to_thread", "run_in_threadpool", "partial"}:
            continue
        for hijo in ast.walk(nodo):
            if isinstance(hijo, ast.Call) and _nombre_llamado(hijo) == nombre:
                envueltas.add(id(hijo))
            # `partial(funcion, ...)` pasa la función POR NOMBRE, sin llamarla.
            if isinstance(hijo, ast.Name) and hijo.id == nombre:
                envueltas.add(id(hijo))

    directas = []
    for nodo in ast.walk(corrutina):
        if isinstance(nodo, ast.Call) and _nombre_llamado(nodo) == nombre:
            if id(nodo) not in envueltas:
                directas.append(nodo)
    return directas


@pytest.mark.parametrize(("ruta", "funcion"), LLAMADAS_CARAS)
def test_el_calculo_caro_no_corre_en_el_bucle_de_eventos(ruta: str, funcion: str):
    archivo = RAIZ / ruta
    arbol = ast.parse(archivo.read_text(encoding="utf-8"))

    encontrada = False
    for corrutina in _corrutinas(arbol):
        directas = _llamadas_directas(corrutina, funcion)
        if any(
            isinstance(n, (ast.Call, ast.Name))
            and (
                (isinstance(n, ast.Call) and _nombre_llamado(n) == funcion)
                or (isinstance(n, ast.Name) and n.id == funcion)
            )
            for n in ast.walk(corrutina)
        ):
            encontrada = True
        assert not directas, (
            f"{ruta}:{corrutina.name} llama a `{funcion}()` dentro del bucle de "
            f"eventos (línea {directas[0].lineno}). Pásala por "
            f"`anyio.to_thread.run_sync` o el backend deja de responder mientras "
            f"dura el cálculo."
        )

    assert encontrada, (
        f"`{funcion}` ya no aparece en {ruta}: si se movió, mueve también esta "
        f"prueba en vez de dejarla pasando en vacío."
    )
