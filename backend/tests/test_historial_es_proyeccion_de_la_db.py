"""HIST-BE-001, HIST-BE-002 y HIST-FE-003 — el Historial tiene que ser una proyección
fiel de la DB, no un segundo almacén con su propia contabilidad.

Tres defectos medidos sobre el código, no supuestos:

**HIST-BE-001.** `/history/evaluations` lista **todas** las moléculas de la cuenta —la
política declarada en el propio router: «todas las evaluaciones se registran
automáticamente; `is_saved` sólo significa promovido a Moldex»—, mientras `/history/stats`
calcula sus seis agregados con `is_saved == True`, que es el filtro de **Moldex**
(`db/repository.py`). El panel de estadísticas y la tabla que tiene debajo cuentan
poblaciones distintas: una cuenta con veinte evaluaciones y ninguna promovida lee
«Total 0» encima de veinte filas.

**HIST-BE-002.** `POST /history/save/{id}` autorizaba con
`mol.user_id is not None and mol.user_id != current_user.id`, de modo que una molécula
sin dueño la adoptaba —`mol.user_id = current_user.id`— cualquier cuenta que supiera su
id. `MoleculeORM.user_id` es `nullable=False` desde la política de invitado, así que esa
rama sólo puede alcanzar filas heredadas; es exactamente el caso que el traspaso
(`POST /auth/traspaso`) existe para cubrir, y es una segunda puerta que se lo salta.

**HIST-FE-003.** `MoleculeStatus` vale `pending/validated/docking/evaluated/failed`, y el
mapa de la insignia sólo conocía `completed/SUCCESS/failed/FAILURE/running/PENDING`. El
estado más común —`evaluated`, una evaluación terminada— caía al `??` y se pintaba crudo
y en inglés, contradiciendo a Evaluación, que dice «Completada».
"""

from __future__ import annotations

import inspect
import re
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from api.routers import history as history_router
from core.models import MoleculeStatus

ROOT = Path(__file__).resolve().parents[2]
PAGINA_HISTORIAL = ROOT / "frontend" / "app" / "history" / "page.tsx"


# ── HIST-BE-001 — la misma población en la tabla y en el marcador ────────────


def _codigo_sin_comentarios(funcion) -> str:
    """El texto que se ejecuta, sin comentarios ni docstring: la prosa no es un filtro."""
    lineas = [
        l.split("#", 1)[0]
        for l in inspect.getsource(funcion).splitlines()
        if not l.strip().startswith("#")
    ]
    cuerpo = "\n".join(lineas)
    return re.sub(r'""".*?"""', "", cuerpo, flags=re.S)


def test_las_estadisticas_no_filtran_por_una_poblacion_distinta_de_la_lista():
    """`is_saved` es el filtro de Moldex. En Historial cuenta otra cosa que la tabla."""
    fuente = _codigo_sin_comentarios(history_router.get_stats)
    assert "is_saved" not in fuente, (
        "get_stats sigue contando sólo lo promovido a Moldex mientras la lista "
        "muestra todas las evaluaciones de la cuenta"
    )


def test_la_lista_y_las_estadisticas_declaran_el_mismo_dueno():
    """Las dos superficies filtran por la cuenta autenticada y por nada más."""
    for funcion in (history_router.list_evaluations, history_router.get_stats):
        fuente = inspect.getsource(funcion)
        assert "current_user.id" in fuente, f"{funcion.__name__} no filtra por cuenta"


# ── HIST-BE-002 — nadie adopta una molécula sin dueño ────────────────────────


def _molecula(owner_id):
    return SimpleNamespace(
        id=uuid.uuid4(), user_id=owner_id, name=None, is_saved=False, smiles="CCO"
    )


def test_una_molecula_sin_dueno_no_se_adopta_al_guardarla():
    with pytest.raises(HTTPException) as error:
        history_router._require_molecule_owner(_molecula(None), SimpleNamespace(id=uuid.uuid4()))
    assert error.value.status_code == 404


def test_la_molecula_de_otra_cuenta_responde_404_y_no_403():
    """El 403 confirmaría que la molécula existe, como ya decidió BATCH-BE-002."""
    with pytest.raises(HTTPException) as error:
        history_router._require_molecule_owner(
            _molecula(uuid.uuid4()), SimpleNamespace(id=uuid.uuid4())
        )
    assert error.value.status_code == 404


def test_el_dueno_pasa():
    yo = SimpleNamespace(id=uuid.uuid4())
    history_router._require_molecule_owner(_molecula(yo.id), yo)


def test_guardar_no_reasigna_el_dueno():
    """Ninguna rama de `save_molecule` puede escribir `user_id`."""
    fuente = inspect.getsource(history_router.save_molecule)
    assert not re.search(r"\.user_id\s*=", fuente), (
        "save_molecule vuelve a asignar el dueño; el traspaso del invitado es "
        "POST /auth/traspaso y no este endpoint"
    )


# ── HIST-FE-003 — la insignia conoce los estados que la DB produce ───────────


def test_la_insignia_del_historial_cubre_todos_los_estados_reales():
    pagina = PAGINA_HISTORIAL.read_text(encoding="utf-8")
    # La clave puede escribirse `evaluated:` o `"evaluated":`; lo que importa es que el
    # mapa la traduzca y no que caiga al `??` que pinta el enum crudo.
    faltan = [
        e.value
        for e in MoleculeStatus
        if not re.search(rf'^\s*"?{e.value}"?\s*:\s*\{{', pagina, flags=re.M)
    ]
    assert not faltan, (
        "la insignia del historial no traduce estos estados y los pinta crudos: "
        + ", ".join(faltan)
    )


def test_el_historial_no_promete_un_guardado_que_ya_no_existe():
    """El router declara que ya no hay botón de guardar; el título decía lo contrario."""
    pagina = PAGINA_HISTORIAL.read_text(encoding="utf-8")
    assert "has decidido conservar" not in pagina, (
        "el encabezado sigue diciendo que el historial son las evaluaciones que el "
        "investigador decidió conservar, y lista todas"
    )
