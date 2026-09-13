"""El espacio anónimo dejó de ser un espacio compartido.

`evaluation_access.py` lo decía en su propia docstring: *«Obtiene una molécula
si pertenece al usuario **o al espacio demo público**»*. Y el filtro era
literalmente `molecule.user_id not in {current_user_id, demo_user.id}`.

Dos consecuencias, y la segunda es la grave:

1. sin sesión, `current_user_id` **caía** a la cuenta demo, así que cualquier
   petición anónima entraba en ese espacio;
2. con sesión, una cuenta registrada podía leer todo lo que hubiera en el
   espacio anónimo. La comprobación de IP que protege lo anónimo se aplicaba
   *después* de haber concedido el acceso por pertenecer a demo.

Una molécula tiene un dueño y sólo uno. La regla que fijan estas pruebas:

* una cuenta registrada ve **lo suyo**, nunca lo anónimo;
* una petición sin sesión ve **lo anónimo desde la misma máquina**, nunca lo de
  una cuenta;
* `demo` es una identidad de servicio que no puede autenticarse
  (MOLDEX-BE-015), así que nadie puede reclamar ser su dueño.

TRANS-ANON-002 sigue en pie: sin cuenta se evalúa sin límite. Lo que se retira
no es la evaluación anónima, es que su resultado sea de todos.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from api.routers.evaluation_access import dueno_de_la_peticion, puede_operar

ALICE = uuid.uuid4()
BOB = uuid.uuid4()
DEMO = uuid.uuid4()


def _molecula(dueno):
    return SimpleNamespace(id=uuid.uuid4(), user_id=dueno)


class TestQuienEsElDueno:
    def test_con_sesion_el_dueno_es_la_cuenta(self):
        usuario = SimpleNamespace(id=ALICE)

        assert dueno_de_la_peticion(usuario, DEMO) == ALICE

    def test_sin_sesion_el_dueno_es_el_espacio_anonimo(self):
        assert dueno_de_la_peticion(None, DEMO) == DEMO


class TestUnaCuentaRegistrada:
    def test_ve_lo_suyo(self):
        assert puede_operar(_molecula(ALICE), SimpleNamespace(id=ALICE), DEMO) is True

    def test_no_ve_lo_de_otra_cuenta(self):
        assert puede_operar(_molecula(BOB), SimpleNamespace(id=ALICE), DEMO) is False

    def test_no_ve_lo_anonimo(self):
        """El agujero real: `{current_user_id, demo_user.id}` lo permitía."""
        assert puede_operar(_molecula(DEMO), SimpleNamespace(id=ALICE), DEMO) is False


class TestUnaPeticionSinSesion:
    def test_ve_lo_anonimo(self):
        assert puede_operar(_molecula(DEMO), None, DEMO) is True

    def test_no_ve_lo_de_una_cuenta(self):
        assert puede_operar(_molecula(ALICE), None, DEMO) is False


class TestLasTresPuertasUsanLaMismaRegla:
    """Tres sitios comprobaban propiedad. Tres es donde una se queda atrás."""

    @pytest.mark.parametrize(
        "ruta,funcion",
        [
            ("api.routers.evaluation", "_autorizar_corrida"),
            ("api.routers.evaluation", "get_evaluation_result"),
            ("api.routers.evaluation_access", "require_owned_molecule"),
        ],
    )
    def test_ninguna_vuelve_a_deducir_la_propiedad(self, ruta, funcion):
        import importlib
        import inspect

        modulo = importlib.import_module(ruta)
        fuente = inspect.getsource(getattr(modulo, funcion))

        assert "puede_operar(" in fuente, (
            f"{ruta}.{funcion} tiene que usar la regla compartida"
        )
        assert "demo_user.id}" not in fuente, (
            "el conjunto {cuenta, demo} es exactamente el espacio compartido "
            "que se retira"
        )


class TestLaDocstringYaNoPromete:
    def test_nadie_llama_publico_al_espacio_anonimo(self):
        import inspect

        from api.routers import evaluation_access

        fuente = inspect.getsource(evaluation_access)

        assert "espacio demo público" not in fuente
        assert "público" not in fuente or "no público" in fuente


class TestElContratoHttp:
    @pytest.mark.asyncio
    async def test_una_cuenta_que_pide_lo_anonimo_recibe_403(self):
        from api.routers.evaluation_access import require_owned_molecule

        molecula = _molecula(DEMO)

        class _Repo:
            async def get_or_create_test_user(self):
                return SimpleNamespace(id=DEMO)

        class _Db:
            async def get(self, _modelo, _id):
                return molecula

        with pytest.raises(HTTPException) as error:
            await require_owned_molecule(
                repository=_Repo(),
                db=_Db(),
                molecule_id=molecula.id,
                current_user=SimpleNamespace(id=ALICE),
                forbidden_detail="Sin permiso",
            )

        assert error.value.status_code == 403
