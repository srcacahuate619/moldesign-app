"""Audita las coincidencias exactas del catálogo inglés del backend."""

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
OUTPUT = ROOT / "docs" / "api" / "i18n-catalogo-auditoria.json"

ESPANOL = re.compile(r"[¿¡ñáéíóúüÁÉÍÓÚÜÑ]")
BRITANICAS = re.compile(
    r"\b(?:centre|centres|catalogue|catalogues|licence|licences|authorised|"
    r"initialise|analyse|minimise|minimises|minimised|minimisation|optimise|"
    r"optimised|optimisation|recognised|summarise|summarises|judgement|"
    r"labelled|cancelled|sulphur|towards|artefact|artefacts|favour|colour|"
    r"colours|behaviour|normalise|normalised|organise|visualise|customise|"
    r"grey|whilst|dialogue|programme|modelling|analysed|neighbour|neighbours|metre)\b"
    r"|\bhaemat",
    re.IGNORECASE,
)
MARCADORES = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")
PARES_PROHIBIDOS = (
    (re.compile(r"\bdestiny\b", re.IGNORECASE), re.compile(r"\bdestino\b", re.IGNORECASE), "destino como destiny"),
    (re.compile(r"\bmajor\b", re.IGNORECASE), re.compile(r"\bmayor\b", re.IGNORECASE), "mayor como major"),
    (re.compile(r"\bplus\b", re.IGNORECASE), re.compile(r"\bmás\b", re.IGNORECASE), "más como plus"),
    (re.compile(r"\bfacility\b", re.IGNORECASE), re.compile(r"\binstalación\b", re.IGNORECASE), "instalación como facility"),
    (re.compile(r"\brace\b", re.IGNORECASE), re.compile(r"\bcorrida\b", re.IGNORECASE), "corrida como race"),
    (re.compile(r"\bhot\s+spots?\b", re.IGNORECASE), re.compile(r"\bhotspots?\b", re.IGNORECASE), "hotspots debe escribirse sin espacio"),
    # Revisión del 2026-10-04 (fusión con Molcy): estas traducciones sobrevivieron a la auditoría de la Fase 1 y llegaban a la pantalla en inglés.
    # "G protein-coupled receptor" is the biological name, not a translation
    # of ligand docking. Other occurrences in the same message still count.
    (re.compile(r"(?<!protein-)\b(?:couple[sd]?|coupling|connecting)\b", re.IGNORECASE), re.compile(r"\bacopl\w*", re.IGNORECASE), "acoplar como couple/connect (en docking es dock)"),
    (re.compile(r"\bstrings?\b", re.IGNORECASE), re.compile(r"\bcadenas?\b(?!\s+de\s+(?:texto|herramientas))", re.IGNORECASE), "cadena como string (es chain)"),
    (re.compile(r"\bliving\b", re.IGNORECASE), re.compile(r"\bligando\b", re.IGNORECASE), "ligando como living (es ligand)"),
    (re.compile(r"\bjunction\b", re.IGNORECASE), re.compile(r"\bsitio\b", re.IGNORECASE), "sitio de unión como junction site (es binding site)"),
    (re.compile(r"\bunion\b", re.IGNORECASE), re.compile(r"\bunión\b", re.IGNORECASE), "unión como union (es binding)"),
    (re.compile(r"\bno one else\b", re.IGNORECASE), re.compile(r"\botr[ao]s?\b", re.IGNORECASE), "otra/otro como no one else (nadie más)"),
)
#: Nombres de código y rutas del español (`preparer.filter_pdb_content`, `stage_params`, `docs/76_….md`): una traducción no los toca.
#: Segmentos de dos o más letras: así «l.b.» o «u.b.» (abreviaturas que SÍ se traducen) no cuentan como identificadores.
IDENTIFICADORES = re.compile(r"\bdocs/[\w./-]+\.md\b|\b[A-Za-z][A-Za-z0-9]+(?:[._][A-Za-z0-9]{2,})+\b")
GLOSARIO = (
    (re.compile(r"\bcaja\s+de\s+búsqueda\b", re.IGNORECASE), re.compile(r"\bsearch\s+box\b", re.IGNORECASE), "caja de búsqueda como search box"),
    (re.compile(r"\bacoplamiento\b", re.IGNORECASE), re.compile(r"\bdocking\b", re.IGNORECASE), "acoplamiento como docking"),
    (re.compile(r"\bexhaustividad\b", re.IGNORECASE), re.compile(r"\bexhaustiveness\b", re.IGNORECASE), "exhaustividad como exhaustiveness"),
    (re.compile(r"\bcorrida\b", re.IGNORECASE), re.compile(r"\brun\b", re.IGNORECASE), "corrida como run"),
    (re.compile(r"\bsemilla\b", re.IGNORECASE), re.compile(r"\bseed\b", re.IGNORECASE), "semilla como seed"),
    (re.compile(r"\bcohorte\b", re.IGNORECASE), re.compile(r"\bcohort\b", re.IGNORECASE), "cohorte como cohort"),
    (re.compile(r"\bno evaluad[oa]\b", re.IGNORECASE), re.compile(r"\bnot evaluated\b", re.IGNORECASE), "no evaluado como not evaluated"),
    (re.compile(r"\bafinidad Vina observada\b", re.IGNORECASE), re.compile(r"\bobserved Vina affinity\b", re.IGNORECASE), "afinidad Vina observada según glosario"),
)


def normalizar(texto: str) -> str:
    return " ".join(texto.split())


def evaluar_texto_estatico(nodo: ast.AST) -> str | None:
    if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str):
        return nodo.value
    if isinstance(nodo, ast.JoinedStr):
        partes: list[str] = []
        for valor in nodo.values:
            if not isinstance(valor, ast.Constant) or not isinstance(valor.value, str):
                return None
            partes.append(valor.value)
        return "".join(partes)
    if isinstance(nodo, ast.BinOp) and isinstance(nodo.op, ast.Add):
        izquierda = evaluar_texto_estatico(nodo.left)
        derecha = evaluar_texto_estatico(nodo.right)
        if izquierda is not None and derecha is not None:
            return izquierda + derecha
    return None


def _es_docstring(nodo: ast.Constant) -> bool:
    padre = getattr(nodo, "_audit_parent", None)
    if not isinstance(padre, ast.Expr):
        return False
    contenedor = getattr(padre, "_audit_parent", None)
    cuerpo = getattr(contenedor, "body", [])
    return bool(cuerpo and cuerpo[0] is padre)


class _Fuente(ast.NodeVisitor):
    """Distingue mensajes completos de piezas interpoladas o concatenadas."""

    def __init__(self, ruta: str):
        self.ruta = ruta
        self.completos: dict[str, set[str]] = defaultdict(set)
        self.fragmentos: dict[str, set[str]] = defaultdict(set)

    def _referencia(self, nodo: ast.AST) -> str:
        return f"{self.ruta}:{getattr(nodo, 'lineno', 1)}"

    def _agregar_fragmentos(self, nodo: ast.AST) -> None:
        for hijo in ast.walk(nodo):
            if isinstance(hijo, ast.Constant) and isinstance(hijo.value, str):
                self.fragmentos[hijo.value].add(self._referencia(hijo))

    def _agregar_frases_terminales(self, nodo: ast.AST) -> None:
        """Treat whole sentences inside dynamic concatenations as translatable units."""
        for hijo in ast.walk(nodo):
            if not isinstance(hijo, ast.Constant) or not isinstance(hijo.value, str):
                continue
            for frase in re.split(r"(?<=[.!?])\s+", hijo.value):
                frase = frase.strip()
                if (
                    frase.endswith((".", "!", "?"))
                    and frase not in {".", "!", "?"}
                    and not es_fragmento_obvio(frase)
                ):
                    self.completos[frase].add(self._referencia(hijo))

    def visit_JoinedStr(self, nodo: ast.JoinedStr) -> None:
        valor = evaluar_texto_estatico(nodo)
        if valor is not None:
            self.completos[valor].add(self._referencia(nodo))
            return
        partes: list[str] = []
        numero = 0
        for elemento in nodo.values:
            if isinstance(elemento, ast.Constant) and isinstance(elemento.value, str):
                partes.append(elemento.value)
                self.fragmentos[elemento.value].add(self._referencia(elemento))
            elif isinstance(elemento, ast.FormattedValue):
                numero += 1
                partes.append(f"{{n{numero}}}")
                # Un literal pasado a una función traductora dentro de la
                # expresión es un mensaje completo, no un fragmento del f-string.
                self.visit(elemento.value)
        self.fragmentos["".join(partes)].add(self._referencia(nodo))

    def visit_BinOp(self, nodo: ast.BinOp) -> None:
        if isinstance(nodo.op, ast.Add):
            valor = evaluar_texto_estatico(nodo)
            if valor is not None:
                self.completos[valor].add(self._referencia(nodo))
            else:
                self._agregar_frases_terminales(nodo)
                self._agregar_fragmentos(nodo)
            return
        if isinstance(nodo.op, ast.Mod) and isinstance(nodo.left, ast.Constant) and isinstance(nodo.left.value, str):
            self._agregar_fragmentos(nodo.left)
            return
        self.generic_visit(nodo)

    def visit_Call(self, nodo: ast.Call) -> None:
        funcion = nodo.func
        receptor = funcion.value if isinstance(funcion, ast.Attribute) and funcion.attr == "format" else None
        if isinstance(receptor, ast.Constant) and isinstance(receptor.value, str):
            self.fragmentos[receptor.value].add(self._referencia(receptor))
            for argumento in nodo.args:
                self.visit(argumento)
            for palabra in nodo.keywords:
                self.visit(palabra.value)
            return
        self.generic_visit(nodo)

    def visit_Constant(self, nodo: ast.Constant) -> None:
        if not isinstance(nodo.value, str) or _es_docstring(nodo):
            return
        self.completos[nodo.value].add(self._referencia(nodo))

    def visit(self, nodo: ast.AST) -> Any:
        for hijo in ast.iter_child_nodes(nodo):
            setattr(hijo, "_audit_parent", nodo)
        return super().visit(nodo)


def fuentes_desde(raiz: Path, excluir_catalogo: bool = False) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    completos: dict[str, set[str]] = defaultdict(set)
    fragmentos: dict[str, set[str]] = defaultdict(set)
    for archivo in sorted(raiz.rglob("*.py")):
        relativo = archivo.relative_to(raiz)
        if excluir_catalogo and relativo.as_posix() == "core/i18n_catalog.py":
            continue
        try:
            arbol = ast.parse(archivo.read_text(encoding="utf-8"), filename=relativo.as_posix())
        except (OSError, UnicodeError, SyntaxError) as exc:
            raise ValueError(f"No se pudo analizar {relativo}: {exc}") from exc
        visitante = _Fuente(relativo.as_posix())
        visitante.visit(arbol)
        for texto, referencias in visitante.completos.items():
            completos[texto].update(referencias)
        for texto, referencias in visitante.fragmentos.items():
            fragmentos[texto].update(referencias)
    return completos, fragmentos


def fuentes_backend() -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    raiz = BACKEND
    completos: dict[str, set[str]] = defaultdict(set)
    fragmentos: dict[str, set[str]] = defaultdict(set)
    for archivo in sorted(raiz.rglob("*.py")):
        relativo = archivo.relative_to(raiz)
        if any(parte in {"tests", "migrations", "scripts"} for parte in relativo.parts):
            continue
        if relativo.as_posix() == "core/i18n_catalog.py":
            continue
        try:
            arbol = ast.parse(archivo.read_text(encoding="utf-8"), filename=relativo.as_posix())
        except (OSError, UnicodeError, SyntaxError) as exc:
            raise SystemExit(f"No se pudo analizar {relativo}: {exc}") from exc
        visitante = _Fuente(relativo.as_posix())
        visitante.visit(arbol)
        for texto, referencias in visitante.completos.items():
            completos[texto].update(referencias)
        for texto, referencias in visitante.fragmentos.items():
            fragmentos[texto].update(referencias)
    return completos, fragmentos


def es_fragmento_obvio(clave: str) -> bool:
    """Detecta límites abiertos sin confundir rótulos y oraciones completas."""
    limpio = clave.lstrip()
    inicia_abierto = (
        limpio.startswith(("'", "’", ")", ",", ";", "%", "</"))
    )
    termina_comilla_abierta = (
        clave.endswith("'") and clave.count("'") % 2 == 1
    ) or (
        clave.endswith("’") and clave.count("’") % 2 == 1
    )
    termina_delimitador_abierto = any(
        clave.count(abierto) > clave.count(cierre)
        for abierto, cierre in (("(", ")"), ("[", "]"), ("{", "}"))
    ) and clave.rstrip().endswith(("(", "[", "{"))
    return inicia_abierto or termina_comilla_abierta or termina_delimitador_abierto


def problemas_entrada(es: str, en: str) -> list[str]:
    problemas: list[str] = []
    if normalizar(es) == normalizar(en):
        problemas.append("idéntica")
    if ESPANOL.search(en):
        problemas.append("caracteres_españoles")
    if BRITANICAS.search(en):
        problemas.append("inglés_británico")
    if sorted(MARCADORES.findall(es)) != sorted(MARCADORES.findall(en)):
        problemas.append("marcadores_distintos")
    for traduccion, origen, etiqueta in PARES_PROHIBIDOS:
        if traduccion.search(en) and origen.search(es):
            problemas.append("sospechosa:" + etiqueta)
    for origen, traduccion, etiqueta in GLOSARIO:
        if origen.search(es) and not traduccion.search(en):
            problemas.append("glosario:" + etiqueta)
    if re.search(r"\b(?:he|she)\b", en, re.IGNORECASE):
        problemas.append("sospechosa:pronombre_he_she")
    for identificador in dict.fromkeys(IDENTIFICADORES.findall(es)):
        if identificador not in en:
            problemas.append("identificador_alterado:" + identificador)
    return problemas


def analizar_catalogo(catalogo: dict[str, str], completos: dict[str, set[str]], fragmentos: dict[str, set[str]]) -> dict[str, Any]:
    filas: list[dict[str, Any]] = []
    por_problema: Counter[str] = Counter()
    completos_normalizados: dict[str, set[str]] = defaultdict(set)
    fragmentos_normalizados: dict[str, set[str]] = defaultdict(set)
    for texto, referencias in completos.items():
        completos_normalizados[normalizar(texto)].update(referencias)
    for texto, referencias in fragmentos.items():
        fragmentos_normalizados[normalizar(texto)].update(referencias)
    for clave, traduccion in sorted(catalogo.items()):
        normalizada = normalizar(clave)
        problemas = problemas_entrada(clave, traduccion)
        if normalizada not in completos_normalizados:
            problemas.append("clave_muerta")
        if normalizada in fragmentos_normalizados and normalizada not in completos_normalizados:
            problemas.append("fragmento")
        if es_fragmento_obvio(clave):
            problemas.append("fragmento")
        problemas = list(dict.fromkeys(problemas))
        por_problema.update(problemas)
        filas.append({
            "es": clave,
            "en": traduccion,
            "problemas": problemas,
            "referencias": sorted(
                completos_normalizados.get(normalizada, set())
                | fragmentos_normalizados.get(normalizada, set())
            ),
        })
    return {
        "version": 1,
        "criterio": "coincidencia completa por literal o concatenación estática; se excluyen docstrings y piezas de f-string, .format y concatenaciones dinámicas",
        "resumen": {
            "entradas": len(catalogo),
            "con_problemas": sum(bool(fila["problemas"]) for fila in filas),
            "por_problema": dict(sorted(por_problema.items())),
        },
        "entradas": filas,
    }


def cargar_catalogo() -> dict[str, str]:
    if str(BACKEND) not in sys.path:
        sys.path.insert(0, str(BACKEND))
    from core.i18n_catalog import ENGLISH_MESSAGES

    return dict(ENGLISH_MESSAGES)


def autotest() -> int:
    import tempfile

    with tempfile.TemporaryDirectory() as temporal:
        raiz = Path(temporal)
        (raiz / "muestra.py").write_text(
            'mensaje = "El receptor no está disponible."\n'
            'dinamico = f"Falló {motor} al preparar el receptor."\n'
            'concatenado = "Error: " + detalle\n'
            'oracion_dinamica = "La preparación quedó declarada." + detalle + " Revise el receptor antes de continuar."\n'
            'estatico = "Dossier " + "no disponible."\n'
            'multilinea = "La salida del verificador se divide en\\nvarias líneas para conservar el README."\n'
            "rotulo = f\"{translate_text('Dossier de cohorte')} · {nombre}\"\n",
            encoding="utf-8",
        )
        completos, fragmentos = fuentes_desde(raiz)
        catalogo = {
            "El receptor no está disponible.": "The receptor is unavailable.",
            "Falló {n1} al preparar el receptor.": "Docking engine {n1} failed during receptor preparation.",
            "Falló ": "Failed ",
            "Error: ": "Error: ",
            "Dossier no disponible.": "Dossier unavailable.",
            "La preparación quedó declarada.": "The preparation was recorded.",
            "Revise el receptor antes de continuar.": "Review the receptor before continuing.",
            "La preparación quedó": "The preparation was recorded",
            "La salida del verificador se divide en varias líneas para conservar el README.": (
                "The verifier output is split across several lines to preserve the README."
            ),
            "Dossier de cohorte": "Cohort dossier",
        }
        informe = analizar_catalogo(catalogo, completos, fragmentos)
        filas = {fila["es"]: fila for fila in informe["entradas"]}
        assert filas["El receptor no está disponible."]["problemas"] == []
        assert {"clave_muerta", "fragmento"} <= set(filas["Falló {n1} al preparar el receptor."]["problemas"])
        assert {"clave_muerta", "fragmento"} <= set(filas["Falló "]["problemas"])
        assert {"clave_muerta", "fragmento"} <= set(filas["Error: "]["problemas"])
        assert filas["Dossier no disponible."]["problemas"] == []
        assert filas["La preparación quedó declarada."]["problemas"] == []
        assert filas["Revise el receptor antes de continuar."]["problemas"] == []
        assert filas["La preparación quedó"]["problemas"] == ["clave_muerta"]
        assert filas[
            "La salida del verificador se divide en varias líneas para conservar el README."
        ]["problemas"] == []
        assert filas["Dossier de cohorte"]["problemas"] == []
        assert "sospechosa:destino como destiny" in problemas_entrada(
            "' no es un destino declarado.", "'It's not a stated destiny."
        )
        assert "glosario:corrida como run" in problemas_entrada(
            "La corrida terminó.", "The race ended."
        )
        assert problemas_entrada("La pose está disponible.", "The pose is available.") == []
    assert any("hotspots" in p for p in problemas_entrada("Hotspots del catálogo", "Catalog hot spots"))
    assert any("hotspots" in p for p in problemas_entrada("Hotspot seleccionado", "Selected hot spot"))
    assert not any("hotspots" in p for p in problemas_entrada("Hotspots del catálogo", "Catalog hotspots"))
    assert not any("hotspots" in p for p in problemas_entrada("Lugar cálido", "A hot spot"))
    print("Autotest de auditoría: detecta defectos y acepta las muestras sanas.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--autotest", action="store_true")
    parser.add_argument("--check", action="store_true", help="falla si queda algún defecto")
    parser.add_argument("--write", action="store_true", help="escribe el informe JSON")
    args = parser.parse_args()
    if args.autotest:
        return autotest()
    informe = analizar_catalogo(cargar_catalogo(), *fuentes_backend())
    resumen = informe["resumen"]
    print(json.dumps(resumen, ensure_ascii=False, sort_keys=True))
    if args.write:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(json.dumps(informe, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"Generado: {OUTPUT.relative_to(ROOT)}")
    if args.check and resumen["con_problemas"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
