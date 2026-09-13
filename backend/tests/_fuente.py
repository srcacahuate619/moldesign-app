"""Ayuda para pruebas que vigilan un patrón de código.

Varias regresiones de esta suite comprueban que un idiom retirado no vuelva al
código —`total_score or 0.0`, la cuota anónima por IP—. Escanear el texto crudo
del módulo no sirve: encuentra el patrón dentro del comentario que explica por
qué está prohibido, que es justo lo contrario de lo que se quiere detectar.

Este helper devuelve sólo los tokens ejecutables, sin comentarios ni literales.
"""

from __future__ import annotations

import inspect
import tokenize


def codigo_ejecutable(modulo) -> str:
    """Fuente del módulo sin comentarios ni literales de texto."""
    ruta = inspect.getsourcefile(modulo)
    if ruta is None:  # pragma: no cover - módulos sin fuente en disco
        raise ValueError(f"el módulo {modulo!r} no tiene fuente en disco")

    with open(ruta, "rb") as handle:
        tokens = list(tokenize.tokenize(handle.readline))

    return " ".join(
        token.string
        for token in tokens
        if token.type not in (tokenize.COMMENT, tokenize.STRING)
    )


def codigo_con_literales(modulo) -> str:
    """Fuente sin comentarios ni docstrings, pero **conservando** los literales.

    Es el complemento de `codigo_ejecutable`. Para vigilar una credencial
    escrita a mano hace falta justo lo contrario: la contraseña ES un literal,
    así que no puede eliminarse, mientras que el comentario que explica por qué
    ya no se usa sí debe quedar fuera.

    Se apoya en `ast`, que descarta los comentarios al reconstruir el código;
    las docstrings se retiran a mano porque el árbol las conserva como
    sentencias de expresión.
    """
    import ast

    arbol = ast.parse(inspect.getsource(inspect.getmodule(modulo) or modulo))

    for nodo in ast.walk(arbol):
        if not isinstance(
            nodo, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            continue
        cuerpo = getattr(nodo, "body", [])
        if (
            cuerpo
            and isinstance(cuerpo[0], ast.Expr)
            and isinstance(cuerpo[0].value, ast.Constant)
            and isinstance(cuerpo[0].value.value, str)
        ):
            nodo.body = cuerpo[1:] or [ast.Pass()]

    return ast.unparse(arbol)
