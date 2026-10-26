"""Inventario AST de cadenas españolas que pueden llegar a la interfaz.

Genera ``docs/api/i18n-inventario.json``. ``--check`` compara el número de
cadenas pendientes con el último inventario y falla si el pendiente creció.
No importa los módulos de producto analizados: lee por AST el catálogo exacto
y los pares declarados de plantillas para marcar coincidencias.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
OUTPUT = ROOT / "docs" / "api" / "i18n-inventario.json"
PLANTILLAS = BACKEND / "core" / "i18n_plantillas.py"
#: Segundo registro de plantillas (receptores propios): se lee igual que el principal.
PLANTILLAS_RECEPTORES_PROPIOS = BACKEND / "core" / "i18n_receptores_propios.py"
#: Llamadas cuyos argumentos de texto traen SIEMPRE su par en inglés (es, en), así que su castellano no es pendiente.
LLAMADAS_BILINGUES = frozenset({"ErrorDeSubida"})
MARCA_ESPANOL = re.compile(r"[áéíóúñ¿¡]", re.IGNORECASE)
PALABRA_FUNCION = re.compile(
    r"\b(?:el|la|los|las|de|del|que|con|sin|una|un|por|para|se|no|es|en)\b",
    re.IGNORECASE,
)
#: Palabras función que no existen en inglés: si la «traducción» de un par (es, en) las lleva, no es inglés.
PALABRA_SOLO_ESPANOLA = re.compile(r"\b(?:el|la|los|las|del|que|con|sin|una|por|para|se|este|esta)\b", re.IGNORECASE)
DIRECTORIOS_EXCLUIDOS = frozenset({"tests", "migrations", "scripts"})


def _normalizar(texto: str) -> str:
    return " ".join(texto.split())


def _marcadores_posicionales(texto: str) -> str:
    """Canonicalize named and AST-generated markers by occurrence order."""
    numero = 0

    def reemplazar(_coincidencia: re.Match[str]) -> str:
        nonlocal numero
        numero += 1
        return f"{{n{numero}}}"

    return re.sub(r"\{[A-Za-z_][A-Za-z0-9_]*\}", reemplazar, texto)


def _parece_espanol(texto: str) -> bool:
    return (
        14 <= len(texto) <= 400
        and " " in texto
        and bool(MARCA_ESPANOL.search(texto) or PALABRA_FUNCION.search(texto))
    )


class _Cadenas(ast.NodeVisitor):
    def __init__(self, ruta: str) -> None:
        self.ruta = ruta
        self.cadenas: list[dict[str, Any]] = []

    @staticmethod
    def _es_argumento_de_llamada_bilingue(nodo: ast.AST) -> bool:
        actual = getattr(nodo, "_i18n_parent", None)
        while actual is not None:
            if isinstance(actual, ast.Call):
                funcion = actual.func
                nombre = (funcion.id if isinstance(funcion, ast.Name)
                          else funcion.attr if isinstance(funcion, ast.Attribute) else "")
                if nombre in LLAMADAS_BILINGUES:
                    return True
            if isinstance(actual, ast.Dict):
                # Un diccionario {"es": …, "en": …} lleva su traducción dentro.
                claves = {k.value for k in actual.keys if isinstance(k, ast.Constant)}
                if {"es", "en"} <= claves:
                    return True
            if isinstance(actual, ast.Tuple) and len(actual.elts) == 2:
                # Un par (castellano, inglés): la segunda cadena no tiene ninguna marca española.
                par = [e.value for e in actual.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)]
                if len(par) == 2 and _parece_espanol(par[0]) and not (
                        MARCA_ESPANOL.search(par[1]) or PALABRA_SOLO_ESPANOLA.search(par[1])):
                    return True
            actual = getattr(actual, "_i18n_parent", None)
        return False

    def _agregar(self, texto: str, nodo: ast.AST, tipo: str) -> None:
        if not _parece_espanol(texto) or self._es_argumento_de_llamada_bilingue(nodo):
            return
        self.cadenas.append({
            "fichero": self.ruta,
            "linea": getattr(nodo, "lineno", 1),
            "tipo": tipo,
            "texto_es": texto,
        })

    def visit_JoinedStr(self, node: ast.JoinedStr) -> None:
        partes: list[str] = []
        numero = 0
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                partes.append(value.value)
            elif isinstance(value, ast.FormattedValue):
                numero += 1
                partes.append(f"{{n{numero}}}")
        # Los fragmentos de un f-string no son salidas independientes. Un
        # f-string sin expresiones es un literal fijo, no una plantilla.
        if numero and not self._es_parte_de_concatenacion_dinamica(node):
            self._agregar("".join(partes), node, "f-string")
        self.generic_visit(node)

    def visit_BinOp(self, node: ast.BinOp) -> None:
        if isinstance(node.op, ast.Add):
            texto = self._texto_estatico(node)
            if texto is not None:
                if not self._es_parte_de_concatenacion_dinamica(node):
                    self._agregar(texto, node, "fija")
                return
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        if (
            isinstance(node.value, str)
            and not self._es_docstring(node)
            and not self._es_fragmento_fstring(node)
            and not self._es_parte_de_concatenacion_dinamica(node)
            and not self._es_prefijo_de_descripcion_generica(node)
        ):
            self._agregar(node.value, node, "fija")

    @staticmethod
    def _texto_estatico(node: ast.AST) -> str | None:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            izquierda = _Cadenas._texto_estatico(node.left)
            derecha = _Cadenas._texto_estatico(node.right)
            if izquierda is not None and derecha is not None:
                return izquierda + derecha
        return None

    @staticmethod
    def _es_parte_de_concatenacion_dinamica(node: ast.AST) -> bool:
        actual = node
        padre = getattr(actual, "_i18n_parent", None)
        while padre is not None:
            if isinstance(padre, ast.Call):
                funcion = padre.func
                nombre = (
                    funcion.id if isinstance(funcion, ast.Name)
                    else funcion.attr if isinstance(funcion, ast.Attribute)
                    else ""
                )
                if nombre in {"translate_text", "traducir"}:
                    return False
            if isinstance(padre, ast.AugAssign) and isinstance(padre.op, ast.Add):
                return True
            if isinstance(padre, ast.BinOp) and isinstance(padre.op, ast.Add):
                if _Cadenas._texto_estatico(padre) is None:
                    return True
            actual, padre = padre, getattr(padre, "_i18n_parent", None)
        return False

    @staticmethod
    def _es_docstring(node: ast.Constant) -> bool:
        padre = getattr(node, "_i18n_parent", None)
        if not isinstance(padre, ast.Expr) or padre.value is not node:
            return False
        contenedor = getattr(padre, "_i18n_parent", None)
        cuerpo = getattr(contenedor, "body", [])
        return bool(cuerpo and cuerpo[0] is padre)

    @staticmethod
    def _es_fragmento_fstring(node: ast.Constant) -> bool:
        padre = getattr(node, "_i18n_parent", None)
        return isinstance(padre, ast.JoinedStr)

    @staticmethod
    def _es_prefijo_de_descripcion_generica(node: ast.Constant) -> bool:
        """Ignore target-description sentinels used only by the fallback guard."""
        actual = getattr(node, "_i18n_parent", None)
        while actual is not None:
            if isinstance(actual, (ast.Tuple, ast.List)):
                asignacion = getattr(actual, "_i18n_parent", None)
                if isinstance(asignacion, ast.Assign) and any(
                    isinstance(destino, ast.Name) and destino.id == "_generic_prefixes"
                    for destino in asignacion.targets
                ):
                    return True
            actual = getattr(actual, "_i18n_parent", None)
        return False

    def visit(self, node: ast.AST) -> Any:
        for child in ast.iter_child_nodes(node):
            setattr(child, "_i18n_parent", node)
        return super().visit(node)


def _catalogo() -> set[str]:
    if str(BACKEND) not in sys.path:
        sys.path.insert(0, str(BACKEND))
    from core.i18n_catalog import ENGLISH_MESSAGES

    return {_normalizar(key) for key in ENGLISH_MESSAGES}


def extraer_plantillas(fuente: str, nombre_del_registro: str = "PLANTILLAS_ES_EN") -> set[str]:
    """Lee por AST los originales españoles del registro literal de plantillas."""
    arbol = ast.parse(fuente, filename="core/i18n_plantillas.py")
    valor: ast.AST | None = None
    for nodo in arbol.body:
        if isinstance(nodo, ast.Assign) and any(
            isinstance(destino, ast.Name) and destino.id == nombre_del_registro
            for destino in nodo.targets
        ):
            valor = nodo.value
            break
        if (
            isinstance(nodo, ast.AnnAssign)
            and isinstance(nodo.target, ast.Name)
            and nodo.target.id == nombre_del_registro
        ):
            valor = nodo.value
            break
    if valor is None:
        raise ValueError(f"No se encontró {nombre_del_registro}")

    pares = ast.literal_eval(valor)
    originales: set[str] = set()
    for par in pares:
        if (
            not isinstance(par, (tuple, list))
            or len(par) != 2
            or not all(isinstance(texto, str) for texto in par)
        ):
            raise ValueError(f"{nombre_del_registro} debe contener pares de textos")
        originales.add(_normalizar(_marcadores_posicionales(par[0])))
    return originales


def inventariar_fuente(fuente: str, ruta: str) -> list[dict[str, Any]]:
    """Extrae nodos de texto de un módulo con los mismos criterios del plan."""
    arbol = ast.parse(fuente, filename=ruta)
    visitante = _Cadenas(ruta)
    visitante.visit(arbol)
    return visitante.cadenas


def es_ruta_incluida(relativa: Path) -> bool:
    return not any(parte in DIRECTORIOS_EXCLUIDOS for parte in relativa.parts)


def pendiente_subio(anterior: int, actual: int) -> bool:
    """El ratchet sólo falla cuando el pendiente nuevo supera el anterior."""
    return actual > anterior


def construir_inventario() -> dict[str, Any]:
    catalogo = _catalogo()
    plantillas = extraer_plantillas(PLANTILLAS.read_text(encoding="utf-8"))
    plantillas |= extraer_plantillas(PLANTILLAS_RECEPTORES_PROPIOS.read_text(encoding="utf-8"), "PLANTILLAS")
    ocurrencias: list[dict[str, Any]] = []
    ficheros_analizados = 0
    for archivo in sorted(BACKEND.rglob("*.py")):
        relativo = archivo.relative_to(BACKEND)
        if not es_ruta_incluida(relativo):
            continue
        if relativo.as_posix() in {"core/i18n_catalog.py", "core/i18n_plantillas.py",
                                   "core/i18n_receptores_propios.py"}:
            continue
        ficheros_analizados += 1
        try:
            fuente = archivo.read_text(encoding="utf-8")
            cadenas = inventariar_fuente(fuente, relativo.as_posix())
        except (OSError, UnicodeError, SyntaxError) as exc:
            raise SystemExit(f"No se pudo analizar {relativo}: {exc}") from exc
        for cadena in cadenas:
            normalizada = _normalizar(_marcadores_posicionales(cadena["texto_es"]))
            traducida = normalizada in catalogo or normalizada in plantillas
            cadena["en_catalogo"] = traducida
            cadena["pendiente"] = not traducida
            ocurrencias.append(cadena)

    ocurrencias.sort(key=lambda item: (item["fichero"], item["linea"], item["tipo"], item["texto_es"]))
    tipos = Counter(item["tipo"] for item in ocurrencias)
    por_fichero: dict[str, dict[str, int]] = defaultdict(lambda: {
        "cadenas_fijas": 0, "f_strings": 0, "en_catalogo": 0, "pendientes": 0,
    })
    for item in ocurrencias:
        resumen = por_fichero[item["fichero"]]
        resumen["cadenas_fijas" if item["tipo"] == "fija" else "f_strings"] += 1
        resumen["en_catalogo"] += int(item["en_catalogo"])
        resumen["pendientes"] += int(item["pendiente"])

    textos_unicos = {item["texto_es"] for item in ocurrencias}
    textos_unicos_en_catalogo = {
        item["texto_es"] for item in ocurrencias if item["en_catalogo"]
    }

    return {
        "version": 1,
        "criterio": "AST; cadenas de 14–400 caracteres, con espacios y marca española o palabra función; backend sin tests/migrations/scripts; excluye fragmentos de f-strings y concatenaciones dinámicas; concatena literales estáticos; catálogo exacto y plantillas declaradas",
        "resumen": {
            "ficheros_analizados": ficheros_analizados,
            "ficheros_con_cadenas": len({item["fichero"] for item in ocurrencias}),
            "cadenas_fijas": tipos["fija"],
            "f_strings": tipos["f-string"],
            "en_catalogo": sum(int(item["en_catalogo"]) for item in ocurrencias),
            "cadenas_unicas": len(textos_unicos),
            "cadenas_unicas_en_catalogo": len(textos_unicos_en_catalogo),
            "pendientes": sum(int(item["pendiente"]) for item in ocurrencias),
        },
        "por_fichero": dict(sorted(por_fichero.items())),
        "cadenas": ocurrencias,
    }


def _leer_previo() -> dict[str, Any]:
    try:
        return json.loads(OUTPUT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"No se pudo leer el inventario anterior {OUTPUT}: {exc}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="falla si el pendiente aumenta; no escribe")
    args = parser.parse_args()
    actual = construir_inventario()

    if args.check:
        previo = _leer_previo()
        antes = int(previo.get("resumen", {}).get("pendientes", 0))
        ahora = int(actual["resumen"]["pendientes"])
        if pendiente_subio(antes, ahora):
            print(f"El pendiente subió: {antes} -> {ahora}")
            return 1
        print(f"Inventario verificado: {ahora} pendientes (ratchet: {antes})")
        return 0

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(actual, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Generado: {OUTPUT.relative_to(ROOT)}")
    print(json.dumps(actual["resumen"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
