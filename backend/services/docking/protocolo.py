"""
El protocolo de la corrida: lo que se pidió y lo que se ejecutó.

═══════════════════════════════════════════════════════════════════════════
EL FALLO QUE ARREGLA
═══════════════════════════════════════════════════════════════════════════

`docking_protocol` lo escribía **un solo camino**: `services/pipeline/runner.py`,
que es el modo PRO. El camino normal —`services/docking/queue_handler.py`, el
que corre una evaluación cuando el usuario no abre el modal avanzado— llamaba a
`upsert_evaluation_result` sin ese argumento. Cero apariciones en el archivo.

Como el argumento es opcional y el repositorio no sobrescribe con `None`, no
había error, ni aviso, ni nada: la columna quedaba `NULL`. Y el dossier la lee.
Toda evaluación del modo normal producía un expediente sin su protocolo, y la
sección salía vacía sin decir por qué.

═══════════════════════════════════════════════════════════════════════════
Y EL QUE SÍ LO ESCRIBÍA, ESCRIBÍA LO PEDIDO
═══════════════════════════════════════════════════════════════════════════

El runner construía el protocolo desde `stage_params`, es decir desde lo que el
usuario solicitó. Pero `vina_service` puede ejecutar otra cosa:

    docking_engine="qvina2"  y el binario no está
      -> cae a Vina con exhaustiveness=4, escribe un `log.warning`
      -> el protocolo sellado seguía diciendo «qvina2» con el exhaustiveness
         solicitado

Un sello que describe una corrida que no ocurrió es peor que no tener sello. Por
eso `DockingResult` ahora trae `engine_efectivo`, `exhaustiveness_efectiva` y
`num_poses_solicitadas` —lo que de verdad se corrió— y este módulo prefiere esos
valores sobre los pedidos, guardando los dos cuando difieren.

═══════════════════════════════════════════════════════════════════════════
LA REGLA
═══════════════════════════════════════════════════════════════════════════

Se sella **lo pedido y lo conseguido por separado**, siempre. Un ensemble de 30
confórmeros que sólo embebió 22 tiene menos cobertura de la solicitada, y esa
diferencia es justo la que se perdería contando sólo lo que llegó al top-K
entregado. Lo mismo con el motor.
"""

from __future__ import annotations

from typing import Any

#: Versión del contrato. Cambiarla obliga a mirar `services/dossier/` y
#: `test_dossier_estructural.py`.
CONTRATO = "docking_protocol/v1"

#: Motores peptídicos que sustituyen a Vina por completo. Si uno de estos corrió,
#: es el motor de la corrida — no el `docking_engine` que venía por defecto.
_MOTORES_PEPTIDICOS = {
    "esmfold",
    "colabfold",
    "esmfold-pro",
    "esmfold-experimental",
}


def es_motor_peptidico(motor: str | None) -> bool:
    """`True` si el nombre identifica un motor peptídico explícito.

    Existe porque `docking_engine` vale `"vina"` por defecto **también** cuando
    corre la ruta peptídica: sin esta comprobación, el nombre de Vina acababa en
    la procedencia de una corrida que en realidad ejecutó ESMFold.
    """
    return motor in _MOTORES_PEPTIDICOS


def construir_protocolo(
    *,
    docking: Any,
    peptide_engine: str | None = None,
    docking_engine: str = "vina",
    docking_params: dict | None = None,
    conformer_ctx: dict | None = None,
) -> dict[str, Any]:
    """El contrato `docking_protocol/v1` a partir de lo que ejecutó la corrida.

    `docking` es el `DockingResult`; de él salen los valores efectivos. Los
    parámetros pedidos (`docking_params`) sólo se usan como respaldo y para
    dejar constancia cuando no coinciden con lo ejecutado.
    """
    params = docking_params or {}
    conformer = conformer_ctx or {}

    pedido_engine = str(peptide_engine) if es_motor_peptidico(peptide_engine) else str(
        params.get("engine") or docking_engine
    )
    pedido_exh = params.get("exhaustiveness")
    pedido_poses = params.get("num_poses")

    # Un motor peptídico no pasa por `vina_service`, así que no deja
    # `engine_efectivo`: ahí el pedido ES el ejecutado.
    ejecutado_engine = getattr(docking, "engine_efectivo", None)
    if es_motor_peptidico(peptide_engine):
        ejecutado_engine = pedido_engine
    ejecutado_exh = getattr(docking, "exhaustiveness_efectiva", None)
    ejecutado_poses = getattr(docking, "num_poses_solicitadas", None)

    protocolo: dict[str, Any] = {
        "contract": CONTRATO,
        "conformers_requested": conformer.get("conformers_requested", 1),
        "conformers_generated": conformer.get("conformers_generated", 1),
        "conformer_warnings": list(conformer.get("conformer_warnings") or []),
        "engine": ejecutado_engine or pedido_engine,
        "exhaustiveness": ejecutado_exh if ejecutado_exh is not None else pedido_exh,
        "num_poses": ejecutado_poses if ejecutado_poses is not None else pedido_poses,
        "seed": getattr(docking, "vina_random_seed", None),
    }

    # Lo pedido sólo se escribe cuando NO coincide con lo ejecutado. Guardarlo
    # siempre duplicaría el contrato; guardarlo nunca escondería el respaldo.
    solicitado: dict[str, Any] = {}
    if ejecutado_engine and pedido_engine and ejecutado_engine != pedido_engine:
        solicitado["engine"] = pedido_engine
    if pedido_exh is not None and ejecutado_exh is not None and pedido_exh != ejecutado_exh:
        solicitado["exhaustiveness"] = pedido_exh
    if pedido_poses is not None and ejecutado_poses is not None and pedido_poses != ejecutado_poses:
        solicitado["num_poses"] = pedido_poses
    if solicitado:
        protocolo["solicitado"] = solicitado

    return protocolo
