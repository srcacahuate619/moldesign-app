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
CONTRATO = "docking_protocol/v2"

#: Motores peptídicos que sustituyen a Vina por completo. Si uno de estos corrió,
#: es el motor de la corrida — no el `docking_engine` que venía por defecto.
MOTORES_DOCKING_EJECUTABLES = frozenset({"vina"})
MOTORES_PEPTIDICOS_EJECUTABLES = frozenset({"esmfold"})


def validar_motor_solicitado(
    docking_engine: str = "vina", peptide_engine: str | None = None,
) -> None:
    """La misma puerta para las entradas HTTP y los llamadores internos."""
    if docking_engine not in MOTORES_DOCKING_EJECUTABLES:
        raise ValueError(f"motor de docking no ejecutable: {docking_engine}")
    if peptide_engine is not None and peptide_engine not in MOTORES_PEPTIDICOS_EJECUTABLES:
        raise ValueError(f"motor peptídico no ejecutable: {peptide_engine}")


def es_motor_peptidico(motor: str | None) -> bool:
    """`True` si el nombre identifica un motor peptídico explícito.

    Existe porque `docking_engine` vale `"vina"` por defecto **también** cuando
    corre la ruta peptídica: sin esta comprobación, el nombre de Vina acababa en
    la procedencia de una corrida que en realidad ejecutó ESMFold.
    """
    return motor in MOTORES_PEPTIDICOS_EJECUTABLES


def declarar_residuos_de_referencia(
    *,
    activos: list[dict] | None,
    elegidos: list[str] | None,
    catalogo: list[dict] | None,
    fuente_del_catalogo: str | None = None,
) -> dict[str, Any]:
    """Qué residuos de referencia USÓ de verdad la corrida, y de dónde salieron.

    Decisión del propietario (2026-10-04): resultado y dossier lo declaran. Antes el panel de
    resultados pintaba los residuos del CATÁLOGO aunque la corrida usara otra selección, y el dossier
    omitía la lista cuando estaba vacía: un tercero no podía saber qué se había usado.

    Las tres procedencias son tres hechos distintos (SOL-08, QA1-007):

        catalog   `elegidos is None`: nadie tocó la selección y se heredó el catálogo.
        selected  la persona eligió un subconjunto (puede incluir residuos fuera del catálogo).
        none      `elegidos == []`: la decisión explícita de NO usar residuos de referencia.

    `residues` es la lista que de verdad entró en el análisis de contactos (`activos`), no la pedida.
    """
    nombres = [str(h["name"]) for h in (activos or []) if isinstance(h, dict) and h.get("name")]
    del_catalogo = {str(h["name"]) for h in (catalogo or []) if isinstance(h, dict) and h.get("name")}
    if elegidos is None:
        origen = "catalog"
    elif len(elegidos) == 0:
        origen = "none"
    else:
        origen = "selected"
    return {
        "source": origen,
        "residues": nombres,
        "count": len(nombres),
        "catalog_count": len(del_catalogo),
        "catalog_source": fuente_del_catalogo,
    }


def construir_protocolo(
    *,
    docking: Any,
    peptide_engine: str | None = None,
    docking_engine: str = "vina",
    docking_params: dict | None = None,
    conformer_ctx: dict | None = None,
    residuos_de_referencia: dict | None = None,
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

    ejecutado_engine = getattr(docking, "engine_efectivo", None)
    if not ejecutado_engine:
        raise ValueError("No se puede sellar el motor sin engine_efectivo de la ejecución")
    ejecutado_exh = getattr(docking, "exhaustiveness_efectiva", None)
    ejecutado_poses = getattr(docking, "num_poses_solicitadas", None)

    protocolo: dict[str, Any] = {
        "contract": CONTRATO,
        "conformers_requested": conformer.get("conformers_requested", 1),
        "conformers_generated": conformer.get("conformers_generated", 1),
        "conformer_warnings": list(conformer.get("conformer_warnings") or []),
        "engine": ejecutado_engine,
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

    # En resultados heredados o de rutas que no miden estos bytes se declara la
    # ausencia. No se reconstruye una caja a partir de la petición del usuario.
    provenance = getattr(docking, "execution_provenance", None)
    protocolo["execution_provenance"] = provenance if provenance else None
    # Qué residuos de referencia se usaron (ver `declarar_residuos_de_referencia`). Se omite cuando el
    # llamador no lo declara —corridas anteriores—: el dossier distingue «sin dato» de «ninguno».
    if residuos_de_referencia is not None:
        protocolo["reference_residues"] = residuos_de_referencia
    return protocolo


# ── Configuración efectiva (SOL-02) ───────────────────────────────────


def resolver_modo_tautomero(params: dict | None) -> str:
    """No sustituye una elección desconocida por otra especie química."""
    mode = (params or {}).get("tautomero")
    if mode is None:
        # Un solo dueño del valor por defecto: el conformador (`entrada` desde el 2026-10-10).
        from chem.conformer import TAUTOMERO_POR_DEFECTO
        return TAUTOMERO_POR_DEFECTO
    if mode not in ("canonico", "entrada"):
        raise ValueError("tautomero debe ser canonico o entrada")
    return mode


def resolver_parametros_docking(
    *,
    pipeline_config: dict[str, Any] | None,
    size: tuple[float, float, float],
    docking_engine: str = "vina",
    exhaustiveness_declarada: int | None = None,
    num_poses_declarado: int | None = None,
    conformers_declarado: int | None = None,
) -> dict[str, Any]:
    """La ÚNICA resolución del protocolo de docking: `anidado ?? settings`.

    SOL-02 (auditoría 2026-09-30). Antes de esta función había tres fuentes
    con tres respuestas distintas para el mismo parámetro: el preflight
    declaraba `settings` (semilla 42 aunque la corrida ejecutara la anidada),
    el runner ejecutaba los anidados con literales propios (32/8/42), y el
    registry declaraba un tercer defecto (32/9). La revalidación del submit
    firmaba su documento con los anidados mientras el preflight original lo
    firmaba con los de nivel superior: dos huellas para la misma corrida y
    un 409 espurio.

    La cadena, para cada campo:

        `pipeline_config.stage_params` anidado  ??  `settings`

    `pipeline_config` es la única portadora del protocolo que llega a la
    ejecución: ni `EvaluationSubmitRequest` ni `/evaluation/evaluate` tienen
    campos de nivel superior para el protocolo, así que la revalidación del
    submit sólo puede re-transmitir los anidados. Honrar el nivel superior
    aquí declararía una corrida que ningún submit puede ejecutar.

    Los `*_declarada` son los campos de nivel superior del request del
    preflight: espejos que la UI mantiene en sincronía con los anidados. NO
    participan en la resolución — son asesores. Si contradicen lo que se va a
    ejecutar, vuelven en `conflictos` para que el informe los declare
    explícitamente en vez de ejecutarlos o ignorarlos en silencio.

    La semilla no tiene campo de nivel superior: es el caso más puro de la
    incoherencia original — no había forma de declararla por arriba y aun así
    el informe no decía la que iba a correr. Su canon es
    `settings.vina_seed` (42); una semilla explícita en
    `stage_params.docking.seed` la sustituye en declaración, huella y
    ejecución.
    """
    from chem.conformer_ensemble import normalizar_k
    from core.config import get_settings
    from services.docking.search_policy import effective_exhaustiveness

    settings = get_settings()
    stage_params = (pipeline_config or {}).get("stage_params") or {}
    anidado_docking = stage_params.get("docking") or {}
    anidado_conformer = stage_params.get("conformer") or {}
    resolver_modo_tautomero(anidado_conformer)

    seed_crudo = anidado_docking.get("seed")
    seed = int(seed_crudo) if seed_crudo is not None else int(settings.vina_seed)

    poses_crudo = anidado_docking.get("num_poses")
    num_poses = int(poses_crudo) if poses_crudo is not None else int(settings.vina_num_poses)

    # La política de volumen (search_policy) eleva SÓLO el defecto en cajas
    # grandes para Vina; lo explícito se respeta. Preflight y runner deben
    # ver el mismo resultado, así que la política vive dentro de la
    # resolución y no en cada consumidor.
    exhaustiveness = effective_exhaustiveness(
        requested=anidado_docking.get("exhaustiveness"),
        default=int(settings.vina_exhaustiveness),
        size=size,
        engine=docking_engine.strip().lower(),
    )

    conformers_crudo = anidado_conformer.get("conformers")
    conformers = normalizar_k(conformers_crudo) if conformers_crudo is not None else 1

    conflictos: list[dict[str, Any]] = []
    if (
        exhaustiveness_declarada is not None
        and int(exhaustiveness_declarada) != int(exhaustiveness)
    ):
        conflictos.append({
            "campo": "exhaustiveness",
            "declarado": int(exhaustiveness_declarada),
            "efectivo": int(exhaustiveness),
        })
    if num_poses_declarado is not None and int(num_poses_declarado) != int(num_poses):
        conflictos.append({
            "campo": "num_poses",
            "declarado": int(num_poses_declarado),
            "efectivo": int(num_poses),
        })
    if (
        conformers_declarado is not None
        and normalizar_k(conformers_declarado) != int(conformers)
    ):
        conflictos.append({
            "campo": "conformers",
            "declarado": normalizar_k(conformers_declarado),
            "efectivo": int(conformers),
        })

    return {
        "exhaustiveness": int(exhaustiveness),
        "num_poses": int(num_poses),
        "seed": int(seed),
        "conformers": int(conformers),
        "conflictos": conflictos,
    }
