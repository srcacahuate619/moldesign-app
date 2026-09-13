"""Llevar a una cuenta registrada el trabajo hecho como invitado.

`Desktop User` existe para que se pueda evaluar sin registrarse. Funciona, pero
sin una salida convierte a la cuenta invitada en el espacio compartido de la
máquina: quien prueba el producto, evalúa y luego se registra, se encuentra con
que su trabajo se quedó en una identidad que no es la suya y desde la que no
puede certificar.

Este módulo es la salida, y es deliberadamente aburrido: decide **qué** se puede
mover y falla temprano si algo no cuadra. El movimiento en sí lo hace el
endpoint dentro de una única transacción, porque partirlo en dos es como se
consigue una molécula cuyo resultado apunta a otra cuenta.

Cuatro reglas, y ninguna es negociable en el llamador:

* **selectivo** — se mueve lo que el investigador elige. No traspasar es una
  decisión legítima, así que el vacío es un caso normal, no un error;
* **transaccional** — si algo de lo pedido no existe o no es del invitado, no se
  mueve nada. Un traspaso parcial deja el historial mintiendo;
* **idempotente** — lo que ya es del destino se cuenta como hecho, no como
  fallo. Un doble clic o un reintento del cliente no pueden romperlo;
* **en un solo sentido** — del invitado a una cuenta registrada. Ni la cuenta
  invitada recibe, ni una cuenta toma de otra.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class TraspasoNoPermitido(Exception):
    """Lo pedido no se puede mover. Se lanza ANTES de tocar nada."""


@dataclass
class PlanDeTraspaso:
    """Qué se moverá y qué ya estaba, para poder informarlo sin mentir."""

    a_mover: list[Any] = field(default_factory=list)
    ya_estaban: list[Any] = field(default_factory=list)

    @property
    def esta_vacio(self) -> bool:
        return not self.a_mover and not self.ya_estaban


def planificar_traspaso(
    *,
    filas: list[Any],
    destino: Any,
    invitado: Any,
    solicitadas: list[Any],
) -> PlanDeTraspaso:
    """Decide qué se mueve, o explica por qué no se mueve nada.

    `filas` son las que la base encontró para los ids pedidos. Si falta alguna,
    el traspaso entero se rechaza: mover «lo que se pudo» es la variante
    silenciosa del traspaso parcial.
    """
    if not solicitadas:
        return PlanDeTraspaso()

    if destino == invitado:
        raise TraspasoNoPermitido(
            "la cuenta invitada no puede recibir un traspaso: el traspaso "
            "existe para salir de ella, no para volver"
        )

    encontradas = {fila.id: fila for fila in filas}
    faltan = [str(i) for i in solicitadas if i not in encontradas]
    if faltan:
        raise TraspasoNoPermitido(
            "no se traspasó nada: estos elementos no existen o no son "
            f"accesibles: {', '.join(sorted(faltan))}"
        )

    plan = PlanDeTraspaso()
    ajenas: list[str] = []
    for identificador in solicitadas:
        fila = encontradas[identificador]
        if fila.user_id == destino:
            plan.ya_estaban.append(identificador)
        elif fila.user_id == invitado:
            plan.a_mover.append(identificador)
        else:
            ajenas.append(str(identificador))

    if ajenas:
        raise TraspasoNoPermitido(
            "no se traspasó nada: estos elementos son de otra cuenta y el "
            f"traspaso sólo mueve lo que hizo el invitado: {', '.join(sorted(ajenas))}"
        )

    return plan
