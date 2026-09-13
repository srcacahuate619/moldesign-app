"""ENG-003 — `diffpepdock` era una etiqueta sin motor detrás.

Encontrado el 2026-09-01, preparando la primera build pública.

`diffpepdock` estaba en el `Literal` de `EvaluationSubmitRequest`, en la lista de
motores peptídicos explícitos de `services/pipeline/runner.py` y en la detección
de péptidos de `queue_handler`. Es decir: la API lo aceptaba y el pipeline lo
trataba como una elección válida.

**Pero no hay ninguna rama que lo ejecute.** El despacho de
`run_peptide_docking_helper` distingue `colabfold`, `esmfold-experimental` y
—en el `elif` final, sin condición sobre el motor— todo lo demás, que va a
**ESMFold**. No existe `services/diffpepdock/`, ni pesos, ni sidecar, ni cliente.

El resultado no era «motor no disponible». Era peor:

> se ejecutaba **ESMFold** y la corrida quedaba registrada como **DiffPepDock**,
> porque `_protocol_engine` devuelve el motor que pidió el usuario.

Eso es una mentira de procedencia en el dossier: el documento reproducible
nombraría un método que no se usó. Un revisor que intente reproducirlo con
DiffPepDock no obtendría estos números, y no habría forma de saber por qué.

La corrección es retirarlo del contrato. Cuando exista un motor DiffPepDock de
verdad —con su implementación, sus pesos y su entrada en el catálogo— vuelve, y
esta prueba se actualiza a propósito.
"""

from __future__ import annotations

import inspect
import re
from pathlib import Path

from api.routers import evaluation as evaluation_router
from services.pipeline import runner as pipeline_runner

ROOT = Path(__file__).resolve().parents[2]


def _codigo(modulo_o_texto) -> str:
    """Lo que se ejecuta, sin comentarios ni cadenas de documentación.

    Un comentario que explica por qué se retiró el motor no es el motor. Es la
    tercera vez que una guarda de este repositorio se lee su propia prosa; el
    filtro vive aquí para que la explicación pueda quedarse donde hace falta.
    """
    texto = (
        modulo_o_texto if isinstance(modulo_o_texto, str)
        else inspect.getsource(modulo_o_texto)
    )
    sin_comentarios = [
        linea.split("#", 1)[0]
        for linea in texto.splitlines()
        if not linea.strip().startswith("#")
    ]
    cuerpo = chr(10).join(sin_comentarios)
    return re.sub(r'"""[\s\S]*?"""', "", cuerpo)


def test_el_contrato_de_la_api_no_acepta_un_motor_sin_implementacion():
    fuente = _codigo(evaluation_router)
    assert "diffpepdock" not in fuente, (
        "`diffpepdock` sigue en el contrato de la API y no hay ninguna rama que lo "
        "ejecute: la corrida saldría por ESMFold con el nombre de otro motor"
    )


def test_el_pipeline_no_lo_trata_como_motor_valido():
    fuente = _codigo(pipeline_runner)
    assert "diffpepdock" not in fuente, (
        "`_is_explicit_peptide_engine` seguía aceptándolo, así que `_protocol_engine` "
        "lo escribía como motor de la corrida"
    )


def test_el_despacho_no_tiene_un_camino_silencioso_para_el():
    from services.docking import peptide_docking, queue_handler

    for modulo in (peptide_docking, queue_handler):
        fuente = _codigo(modulo)
        assert "diffpepdock" not in fuente, (
            f"{modulo.__name__} todavía lo nombra; si no lo ejecuta, no debe nombrarlo"
        )


def test_el_frontend_tampoco_lo_ofrece():
    for relativo in (
        "frontend/lib/api.ts",
        "frontend/components/evaluation/CaseEvaluationRunner.tsx",
        "frontend/components/interfaces/pro/ProEvaluation.tsx",
    ):
        fuente = (ROOT / relativo).read_text(encoding="utf-8")
        assert "diffpepdock" not in fuente, (
            f"{relativo} sigue declarando un motor que el backend ya no acepta"
        )


def test_los_motores_declarados_tienen_todos_una_rama_que_los_ejecuta():
    """La guarda general: cada motor peptídico del contrato se despacha.

    Es la prueba que habría atrapado esto desde el principio. `esmfold` es el
    caso por defecto del `elif` final, así que se comprueba aparte.
    """
    from services.docking import peptide_docking

    despacho = inspect.getsource(peptide_docking.run_peptide_docking_helper)
    fuente_router = inspect.getsource(evaluation_router)

    for motor in ("colabfold", "esmfold-experimental"):
        assert f'== "{motor}"' in despacho, (
            f"{motor} está en el contrato y no tiene rama propia en el despacho"
        )
        assert motor in fuente_router

    assert "esmfold" in fuente_router
