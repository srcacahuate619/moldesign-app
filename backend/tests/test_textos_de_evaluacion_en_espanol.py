"""
Los textos que la investigadora lee en Evaluación están en español con tilde (QA1-011).

Medido en un único recorrido (preflight, opciones y resultado del mismo caso):

- el detalle de la validez física decía «PoseBusters en configuracion `dock` -sin verdad
  de terreno, que en produccion no existe-. Ningun control de quimica o geometria
  falla.», y el del proxy «Bateria completa no ejecutada… PROXY ENERGETICO…»;
- el aviso de duración mezclaba idiomas («la exhaustiveness es 8») cuando el
  protocolo de esa misma pantalla dice «Exhaustividad 8».

Las tildes no se pueden comprobar con una lista de frases (el texto cambia con la
corrida): se recorre el árbol del módulo y se revisan las cadenas que acaban en los
campos `detail`/`label` y en `razon_degradacion`.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from services import estimacion
from services.chemistry import pose_physical_validity as pv

MODULO = Path(pv.__file__)

#: `pose_physical_validity.py` está SELLADO: lo hashean `PROD-PV-H-01` y `PROD-PV-H-01-PRE`, y
#: `validar_sellos.py --check` (paso de la CI) falla si cambia un solo byte. Corregir las tildes
#: de sus textos exige re-sellar esos dos experimentos, y eso es decisión del propietario. Mientras
#: tanto las dos pruebas que miran ese fichero se marcan `xfail(strict=True)`: la deuda queda escrita
#: y, si alguien corrige el módulo, la prueba pasa a XPASS y falla hasta quitar la marca.
DEUDA_SELLADA = pytest.mark.xfail(
    strict=True,
    reason="pose_physical_validity.py está sellado por PROD-PV-H-01 y PROD-PV-H-01-PRE: "
           "corregir sus tildes exige re-sellar (decisión del propietario)",
)

#: Palabras que en este texto sólo existen CON tilde. («solo» y «fallo» no están: la
#: RAE admite «solo» sin tilde, y «fallo» es también un sustantivo.)
SIN_TILDE = re.compile(
    r"\b(configuracion|produccion|quimica|geometria|ningun|preparacion|energetico|"
    r"bateria|conformeros|razon|asi|midio|direccion|revision|medicion|fallo al)\b",
    re.IGNORECASE,
)


def cadenas_para_la_usuaria(codigo: str) -> list[str]:
    """Las cadenas que acaban en `detail`/`label` o en `razon_degradacion`/`detalle`."""
    arbol = ast.parse(codigo)
    nodos: list[ast.AST] = []
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Dict):
            for clave, valor in zip(nodo.keys, nodo.values):
                if isinstance(clave, ast.Constant) and clave.value in {"detail", "label"}:
                    nodos.append(valor)
        elif isinstance(nodo, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id in {"razon_degradacion", "detalle", "FRASE_OBLIGATORIA"} for t in nodo.targets
        ):
            nodos.append(nodo.value)
        elif isinstance(nodo, ast.AugAssign) and isinstance(nodo.target, ast.Name) and nodo.target.id == "detalle":
            nodos.append(nodo.value)
    return [c for n in nodos for c in _constantes_de_texto(n)]


def _constantes_de_texto(nodo: ast.AST):
    """Las cadenas de TEXTO del nodo; lo que va dentro de `{...}` de una f-string es código."""
    if isinstance(nodo, ast.Constant):
        if isinstance(nodo.value, str):
            yield nodo.value
    elif isinstance(nodo, ast.JoinedStr):
        for parte in nodo.values:
            if isinstance(parte, ast.Constant) and isinstance(parte.value, str):
                yield parte.value
    else:
        for hijo in ast.iter_child_nodes(nodo):
            yield from _constantes_de_texto(hijo)


# ── El guardián tiene que demostrar que ve ───────────────────────────


def test_el_guardian_ve_una_cadena_sin_tilde_y_no_se_queja_de_una_correcta():
    malo = 'detalle = "Ningun control de quimica o geometria falla. "\n'
    assert any(SIN_TILDE.search(c) for c in cadenas_para_la_usuaria(malo))
    bueno = 'detalle = "Ningún control de química o geometría falla. "\n'
    assert not any(SIN_TILDE.search(c) for c in cadenas_para_la_usuaria(bueno))
    # Fuera de los campos que lee la usuaria (un comentario, un nombre de clave) no vigila nada.
    ajeno = '# quimica sin tilde en un comentario\nclave = {"quimica": 1}\n'
    assert cadenas_para_la_usuaria(ajeno) == []


def test_el_guardian_encuentra_cadenas_que_comprobar_en_el_modulo_real():
    cadenas = cadenas_para_la_usuaria(MODULO.read_text(encoding="utf-8"))
    # Si no encontrara casi nada, «ninguna sin tilde» no significaría nada.
    assert len(cadenas) >= 25, f"sólo {len(cadenas)} cadenas: el guardián no ve"


# ── La guardia real ──────────────────────────────────────────────────


@DEUDA_SELLADA
def test_los_textos_de_validez_fisica_llevan_tilde():
    cadenas = cadenas_para_la_usuaria(MODULO.read_text(encoding="utf-8"))
    malas = sorted({c.strip() for c in cadenas if SIN_TILDE.search(c)})
    assert not malas, "textos para la investigadora sin tilde:\n  " + "\n  ".join(malas)


@DEUDA_SELLADA
def test_la_frase_obligatoria_lleva_tilde():
    assert "preparación" in pv.FRASE_OBLIGATORIA
    assert not SIN_TILDE.search(pv.FRASE_OBLIGATORIA)


# ── El aviso de duración habla como el resto de la pantalla ──────────


def test_el_aviso_de_duracion_dice_exhaustividad_no_exhaustiveness():
    e = estimacion.estimar_corrida(cpu=4, exhaustiveness=8)
    aviso = next(a for a in e["avisos"] if "tandas" in a)
    assert "exhaustividad" in aviso
    assert "exhaustiveness" not in aviso.lower()
    assert "4 núcleos" in aviso
