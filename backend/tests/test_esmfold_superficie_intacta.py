"""
Que el sidecar de ESMFold conserve todos sus métodos.

# Por qué existe esta prueba

Al reescribir `_smiles_to_aa_sequence` sustituí un RANGO de texto —desde su
decorador hasta el siguiente `@staticmethod`— y entre medias vivía
`_fold_sequence`, que no lleva decorador porque es un método de instancia. Se
borró con el rango. Es **el método que pliega la secuencia con ESMFold**: sin
él, `predict()` levanta `AttributeError` en cuanto extrae la secuencia.

La suite entera siguió en verde, porque nada ejercita `predict()` —necesita el
modelo ESM cargado— y `_fold_sequence` sólo se nombra dentro de ese camino.
Lo detectó una pregunta, no una prueba. Esta es la prueba.

No comprueba comportamiento: comprueba **superficie**. Un método que
desaparece de una clase que la suite no puede ejecutar es invisible hasta que
alguien lo usa en producción.
"""

import sys
from pathlib import Path

import pytest

SIDECAR = Path(__file__).resolve().parents[1] / "sidecars" / "esmfold"
if str(SIDECAR) not in sys.path:
    sys.path.insert(0, str(SIDECAR))


def _modulo():
    import predictor

    return predictor


#: Lo que cada predictor debe seguir exponiendo. La lista se escribió leyendo
#: el árbol anterior a los cambios, no el actual: si se derivara del actual no
#: detectaría nada.
SUPERFICIE = {
    "StubPredictor": ("predict",),
    "ESMFoldFastPredictor": (
        "predict",
        "_smiles_to_aa_sequence",
        "_fold_sequence",
        # `_positions_to_pdb` se RETIRA el 2026-09-04, y esta prueba lo detectó,
        # que es exactamente para lo que existe. Fue deliberado: al ejecutar
        # ESMFold de verdad por primera vez salió que el método tenía cuatro
        # errores encadenados —índice del bloque de estructura, dimensión de
        # lote, `float()` sobre un array de 37 elementos, y nombres de átomo
        # sacados de un `set`— y el tercero lanzaba antes de devolver nada. Es
        # decir: el modo `fast` nunca produjo un PDB plegado.
        #
        # Se sustituye por `self._model.output_to_pdb(output)[0]`, el conversor
        # de la propia biblioteca, que toma el bloque final y resuelve los
        # nombres. Ver `sidecars/esmfold/predictor.py::_fold_sequence`.
        "_compute_plddt_from_pdb",
        "_parse_vina_pdbqt",
        "_fallback_poses",
    ),
    "ESMFoldProPredictor": ("predict",),
}


@pytest.mark.parametrize("clase", sorted(SUPERFICIE))
def test_la_clase_existe(clase):
    assert hasattr(_modulo(), clase)


@pytest.mark.parametrize(
    ("clase", "metodo"),
    [(c, m) for c, ms in SUPERFICIE.items() for m in ms],
)
def test_el_metodo_sigue_ahi(clase, metodo):
    objetivo = getattr(_modulo(), clase)
    assert hasattr(objetivo, metodo), (
        f"{clase}.{metodo} desapareció. Si se movió, actualiza esta lista; si "
        f"se borró sin querer —como pasó con `_fold_sequence`—, recupéralo."
    )


def test_el_conversor_a_pdb_es_el_de_la_biblioteca():
    """La contrapartida de haber retirado `_positions_to_pdb`.

    La superficie de arriba dice qué NO puede desaparecer. Esto dice qué tiene
    que seguir habiendo en su lugar: si alguien reintroduce un conversor
    artesanal, vuelven los cuatro errores que hicieron que el modo `fast` no
    plegara nunca.
    """
    import inspect

    fuente = inspect.getsource(_modulo().ESMFoldFastPredictor._fold_sequence)
    assert "output_to_pdb" in fuente, (
        "`_fold_sequence` dejó de usar el conversor de la biblioteca"
    )
    codigo = [l for l in fuente.splitlines() if not l.strip().startswith("#")]
    assert not [l for l in codigo if "_positions_to_pdb" in l], (
        "volvió el conversor artesanal de posiciones a PDB"
    )


def test_la_fabrica_sigue_ofreciendo_los_tres_modos():
    fabrica = _modulo().make_predictor
    import inspect

    fuente = inspect.getsource(fabrica)
    for modo in ("stub", "fast", "pro", "real"):
        assert f'"{modo}"' in fuente


def test_todo_lo_que_predict_invoca_de_si_mismo_existe():
    """La comprobación que generaliza el fallo: `self.X(` sin `X` definido.

    `_fold_sequence` se llamaba en `predict()` y su definición ya no estaba.
    Nada lo notaba porque la llamada vive dentro de una rama que la suite no
    recorre. Esto lo mira sobre el árbol sintáctico, sin ejecutar nada.
    """
    import ast

    fuente = (SIDECAR / "predictor.py").read_text(encoding="utf-8")
    arbol = ast.parse(fuente)

    faltan = []
    for clase in (n for n in ast.walk(arbol) if isinstance(n, ast.ClassDef)):
        definidos = {
            m.name
            for m in ast.walk(clase)
            if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        # También los atributos invocables asignados en `__init__`:
        # `self._model` y `self._tokenizer` se llaman como funciones pero no
        # son métodos. Sin esto la comprobación los denuncia como ausentes.
        definidos |= {
            objetivo.attr
            for asignacion in ast.walk(clase)
            if isinstance(asignacion, (ast.Assign, ast.AnnAssign))
            for objetivo in (
                asignacion.targets if isinstance(asignacion, ast.Assign)
                else [asignacion.target]
            )
            if isinstance(objetivo, ast.Attribute)
            and isinstance(objetivo.value, ast.Name)
            and objetivo.value.id == "self"
        }
        # Los heredados también valen: se acumulan los de las clases base.
        for base in clase.bases:
            nombre_base = getattr(base, "id", None)
            for otra in (n for n in ast.walk(arbol) if isinstance(n, ast.ClassDef)):
                if otra.name == nombre_base:
                    definidos |= {
                        m.name
                        for m in ast.walk(otra)
                        if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
                    }
                    definidos |= {
                        objetivo.attr
                        for asignacion in ast.walk(otra)
                        if isinstance(asignacion, ast.Assign)
                        for objetivo in asignacion.targets
                        if isinstance(objetivo, ast.Attribute)
                        and isinstance(objetivo.value, ast.Name)
                        and objetivo.value.id == "self"
                    }

        for nodo in ast.walk(clase):
            if not isinstance(nodo, ast.Call):
                continue
            f = nodo.func
            if not isinstance(f, ast.Attribute):
                continue
            receptor = f.value
            es_self = isinstance(receptor, ast.Name) and receptor.id == "self"
            es_clase = isinstance(receptor, ast.Name) and receptor.id == clase.name
            if not (es_self or es_clase):
                continue
            if f.attr.startswith("__"):
                continue
            if f.attr not in definidos:
                faltan.append(f"{clase.name}.{f.attr} (línea {nodo.lineno})")

    assert not faltan, "métodos invocados que ya no existen: " + ", ".join(faltan)
