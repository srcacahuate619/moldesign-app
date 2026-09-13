"""El trabajo hecho como invitado se puede llevar a una cuenta registrada.

`Desktop User` existe para que se pueda evaluar sin registrarse, y funciona:
tiene `user_id`, sus corridas se persisten y se recuperan. El problema es lo que
pasa después. Un investigador prueba el producto, evalúa diez moléculas, decide
que le sirve, se registra… y su trabajo se queda en la cuenta invitada, donde no
puede certificarlo ni asociarlo a su identidad.

Hasta ahora la única salida era seguir usando el invitado, que es exactamente lo
contrario de «identidad aislada»: convertía la cuenta invitada en el espacio
compartido de la máquina.

Reglas que fijan estas pruebas:

* **selectivo**: se traspasa lo que el investigador elige, no todo por defecto.
  Su trabajo es suyo, incluida la decisión de dejar algo atrás;
* **transaccional**: o se mueve todo lo pedido o no se mueve nada. Un traspaso a
  medias deja moléculas cuyo resultado apunta a otra cuenta;
* **idempotente**: repetirlo no duplica ni falla. Un clic doble, una reconexión
  o un reintento del cliente no pueden romperlo;
* **en un solo sentido**: del invitado a una cuenta registrada. Nadie puede
  tomar de una cuenta registrada, ni el invitado tomar de nadie.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from services.accounts.traspaso import (
    TraspasoNoPermitido,
    planificar_traspaso,
)

INVITADO = uuid.uuid4()
ALICE = uuid.uuid4()
BOB = uuid.uuid4()


class _Fila:
    def __init__(self, id_, user_id):
        self.id = id_
        self.user_id = user_id


class TestQuePuedeTraspasarse:
    def test_lo_del_invitado_se_traspasa(self):
        molecula = _Fila(uuid.uuid4(), INVITADO)

        plan = planificar_traspaso(
            filas=[molecula], destino=ALICE, invitado=INVITADO, solicitadas=[molecula.id]
        )

        assert plan.a_mover == [molecula.id]
        assert plan.ya_estaban == []

    def test_lo_que_ya_es_del_destino_no_es_un_error(self):
        """Idempotencia: repetir el traspaso no puede fallar."""
        molecula = _Fila(uuid.uuid4(), ALICE)

        plan = planificar_traspaso(
            filas=[molecula], destino=ALICE, invitado=INVITADO, solicitadas=[molecula.id]
        )

        assert plan.a_mover == []
        assert plan.ya_estaban == [molecula.id]

    def test_lo_de_otra_cuenta_no_se_toca_y_se_rechaza_entero(self):
        de_bob = _Fila(uuid.uuid4(), BOB)
        del_invitado = _Fila(uuid.uuid4(), INVITADO)

        with pytest.raises(TraspasoNoPermitido) as error:
            planificar_traspaso(
                filas=[de_bob, del_invitado],
                destino=ALICE,
                invitado=INVITADO,
                solicitadas=[de_bob.id, del_invitado.id],
            )

        assert str(de_bob.id) in str(error.value)

    def test_lo_que_no_existe_se_rechaza_entero(self):
        """Transaccional: si algo de lo pedido no está, no se mueve nada."""
        del_invitado = _Fila(uuid.uuid4(), INVITADO)
        fantasma = uuid.uuid4()

        with pytest.raises(TraspasoNoPermitido) as error:
            planificar_traspaso(
                filas=[del_invitado],
                destino=ALICE,
                invitado=INVITADO,
                solicitadas=[del_invitado.id, fantasma],
            )

        assert str(fantasma) in str(error.value)


class TestElSentidoDelTraspaso:
    def test_el_invitado_no_puede_recibir(self):
        molecula = _Fila(uuid.uuid4(), ALICE)

        with pytest.raises(TraspasoNoPermitido):
            planificar_traspaso(
                filas=[molecula],
                destino=INVITADO,
                invitado=INVITADO,
                solicitadas=[molecula.id],
            )

    def test_una_cuenta_no_puede_tomar_de_otra_cuenta(self):
        molecula = _Fila(uuid.uuid4(), BOB)

        with pytest.raises(TraspasoNoPermitido):
            planificar_traspaso(
                filas=[molecula], destino=ALICE, invitado=INVITADO, solicitadas=[molecula.id]
            )


class TestLaSeleccion:
    def test_nada_se_mueve_si_no_se_pide(self):
        """Por defecto no se traspasa: es una decisión del investigador."""
        molecula = _Fila(uuid.uuid4(), INVITADO)

        plan = planificar_traspaso(
            filas=[molecula], destino=ALICE, invitado=INVITADO, solicitadas=[]
        )

        assert plan.a_mover == []
        assert plan.esta_vacio is True

    def test_se_mueve_solo_lo_elegido(self):
        una = _Fila(uuid.uuid4(), INVITADO)
        otra = _Fila(uuid.uuid4(), INVITADO)

        plan = planificar_traspaso(
            filas=[una, otra], destino=ALICE, invitado=INVITADO, solicitadas=[una.id]
        )

        assert plan.a_mover == [una.id]


class TestElEndpoint:
    @pytest.mark.asyncio
    async def test_la_cuenta_invitada_no_puede_pedir_un_traspaso(self):
        from types import SimpleNamespace

        from api.routers.auth import traspasar_del_invitado
        from core.identity import GUEST_EMAIL
        from core.models import TraspasoRequest

        invitado = SimpleNamespace(id=INVITADO, email=GUEST_EMAIL)

        with pytest.raises(HTTPException) as error:
            await traspasar_del_invitado(
                data=TraspasoRequest(molecule_ids=[], cohort_ids=[]),
                current_user=invitado,
                db=None,
            )

        assert error.value.status_code == 403

    @pytest.mark.asyncio
    async def test_un_traspaso_vacio_no_toca_la_base(self):
        from types import SimpleNamespace

        from api.routers.auth import traspasar_del_invitado
        from core.models import TraspasoRequest

        class _DbQueDelata:
            async def execute(self, *_a, **_kw):  # pragma: no cover
                raise AssertionError("un traspaso vacío no tiene nada que consultar")

        respuesta = await traspasar_del_invitado(
            data=TraspasoRequest(molecule_ids=[], cohort_ids=[]),
            current_user=SimpleNamespace(id=ALICE, email="alice@x.com"),
            db=_DbQueDelata(),
        )

        assert respuesta.moleculas_traspasadas == 0
        assert respuesta.cohortes_traspasadas == 0
