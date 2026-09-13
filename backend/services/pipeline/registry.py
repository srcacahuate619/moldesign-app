from __future__ import annotations
from dataclasses import dataclass, field


def admet_requested(properties_params: dict | None) -> bool:
    """ADMET-AI sólo corre ante un booleano ``True`` explícito."""
    return bool(properties_params and properties_params.get("run_admet_ai") is True)


@dataclass
class Stage:
    id: str
    label: str
    description: str
    dependencies: list[str] = field(default_factory=list)
    enabled: bool = True
    required: bool = False
    params: dict = field(default_factory=dict)
    cost_estimate: str = "Bajo"

# Definición de las etapas oficiales
STAGE_REGISTRY: dict[str, Stage] = {
    "validation": Stage(
        id="validation",
        label="RDKit Engine / Curación",
        description="Valida el SMILES y sanitiza la estructura 2D de la molécula.",
        dependencies=[],
        required=True,
    ),
    "properties": Stage(
        id="properties",
        label="Propiedades fisicoquímicas",
        description=(
            "Calcula descriptores locales (Lipinski, QED, logP). ADMET-AI es "
            "experimental y sólo se carga cuando la corrida lo solicita explícitamente."
        ),
        dependencies=["validation"],
        required=True,
        params={"run_admet_ai": False},
    ),
    "sa_filter": Stage(
        id="sa_filter",
        label="SA Score / Sintetizabilidad",
        description="Filtro rápido que rechaza compuestos imposibles de sintetizar.",
        dependencies=["properties"],
        required=True,
    ),
    "conformer": Stage(
        id="conformer",
        label="Generación 3D (ETKDG)",
        description=(
            "Genera la conformación 3D de entrada con ETKDG y minimización MMFF94. "
            "Con `conformers` > 1 genera un ensemble: cada conformación se acopla por "
            "separado y las poses se juntan en una sola piscina. El ensemble amplía la "
            "cobertura geométrica; en la medición interna NO mejoró la elección del "
            "top-1, así que no está activo por defecto."
        ),
        dependencies=["properties"],
        required=True,
        # UNO por defecto, y a propósito: el protocolo por defecto no cambia
        # porque exista la opción. El ensemble se pide o no ocurre.
        params={"conformers": 1},
    ),
    "docking": Stage(
        id="docking",
        label="Molecular Docking (Vina)",
        description="Acoplamiento estocástico contra el receptor usando AutoDock Vina.",
        dependencies=["conformer"],
        required=True,
        params={"exhaustiveness": 32, "num_poses": 9},
        cost_estimate="Alto"
    ),
    "xgb": Stage(
        id="xgb",
        label="XGBoost",
        description="Clasificador XGBoost de afinidad (binder probability) sobre las poses de Vina.",
        dependencies=["docking"],
        required=True,
        cost_estimate="Medio"
    ),
    "clgnn": Stage(
        id="clgnn",
        label="CL-GNN",
        description="Score CL-GNN de aprendizaje contrastivo + explainability de la interacción.",
        dependencies=["docking"],
        required=False,
        cost_estimate="Medio"
    ),
    "openmm": Stage(
        id="openmm",
        label="L3 OpenMM",
        description="Minimización de alta resolución con campo de fuerzas AMBER14SB y solvente implícito.",
        dependencies=["docking"],
        required=False,
        enabled=False,  # Opcional por defecto
        params={"iterations": 100},
        cost_estimate="Muy Alto"
    ),
    "selectivity": Stage(
        id="selectivity",
        label="Selectividad (Safety Panel)",
        description=(
            "Docking contra panel de anti-targets (hERG, CYP3A4, 5-HT2B, PDE3, NaV1.5) "
            "para calcular selectividad ON/OFF y flags de seguridad."
        ),
        dependencies=["docking"],
        required=False,
        enabled=False,  # Solo corre si el usuario activa "Selectividad" en el modal
        params={"num_workers": 2},
        cost_estimate="Alto"
    ),
}

def validate_order(
    ordered_ids: list[str], *, required_stage_ids: set[str] | None = None
) -> tuple[list[str], list[str]]:
    """
    Devuelve un orden topológico válido y advertencias si el orden propuesto 
    por el usuario no cumplía las dependencias.
    """
    # La resolución es una operación pura: callers reutilizan stage_order para
    # auditoría/SSE y no deben recibir etapas requeridas inyectadas por efecto
    # lateral.
    ordered_ids = list(ordered_ids)
    active = set(ordered_ids)
    warnings = []

    # Asegurar requeridos. `None` conserva el contrato histórico. Algunos
    # flujos controlados (cohortes) pueden declarar un subconjunto explícito
    # sin cambiar qué es obligatorio para Evaluación/PRO.
    required = required_stage_ids or {
        stage_id for stage_id, stage in STAGE_REGISTRY.items() if stage.required
    }
    for stage_id, stage in STAGE_REGISTRY.items():
        if stage.required and stage_id in required and stage_id not in active:
            ordered_ids.append(stage_id)
            active.add(stage_id)
            warnings.append(f"La etapa {stage_id} es obligatoria y fue añadida.")

    # Filtrar válidos
    valid_ids = [s for s in ordered_ids if s in STAGE_REGISTRY]

    # Topo sort manual (Burbuja topológica) para preservar la intención del usuario lo más posible
    changed = True
    while changed:
        changed = False
        for i in range(len(valid_ids)):
            for j in range(i + 1, len(valid_ids)):
                id_i = valid_ids[i]
                id_j = valid_ids[j]

                # Si i depende de j, j debe ir antes
                if id_j in STAGE_REGISTRY[id_i].dependencies:
                    valid_ids[i], valid_ids[j] = valid_ids[j], valid_ids[i]
                    changed = True
                    warnings.append(f"Reordenamiento ajustado: {id_j} debe correr antes que {id_i}.")

    # Remover duplicados de warnings
    return valid_ids, list(dict.fromkeys(warnings))


def expand_legacy_alias(
    enabled_stages: list[str] | None,
    stage_order: list[str] | None,
    stage_params: dict[str, dict] | None,
) -> tuple[list[str] | None, list[str] | None, dict[str, dict] | None]:
    """
    v2.0: Expande el alias legacy "rescoring" → ["xgb", "clgnn"] en secuencia.

    Clientes viejos que mandan enabled_stages=["...", "rescoring"] siguen
    recibiendo ambas señales (XGBoost + CL-GNN) sin perder nada. La expansión
    ocurre ANTES de validate_order para que el alias nunca llegue filtrado por
    ids desconocidos (validate_order filtra todo lo que no está en el registro).

    - enabled_stages: quita "rescoring", agrega "xgb" y "clgnn" al final.
    - stage_order: idem, para respetar el orden pedido por el cliente.
    - stage_params: los params legacy de "rescoring" se fusionan en "xgb" y
      "clgnn" (los params específicos del stage ganan sobre los legacy).

    NO muta las listas/dicts de entrada: devuelve nuevas estructuras.
    """
    if enabled_stages and "rescoring" in enabled_stages:
        enabled_stages = [s for s in enabled_stages if s != "rescoring"] + ["xgb", "clgnn"]
    if stage_order and "rescoring" in stage_order:
        stage_order = [s for s in stage_order if s != "rescoring"] + ["xgb", "clgnn"]
    if stage_params and "rescoring" in stage_params:
        legacy_params = dict(stage_params["rescoring"])
        expanded: dict[str, dict] = {k: v for k, v in stage_params.items() if k != "rescoring"}
        for sid in ("xgb", "clgnn"):
            merged = dict(legacy_params)
            merged.update(expanded.get(sid, {}))
            expanded[sid] = merged
        stage_params = expanded
    return enabled_stages, stage_order, stage_params


def resolve_stage_order(
    enabled_stages: list[str] | None,
    stage_order: list[str] | None = None,
    *,
    selectivity_enabled: bool = False,
    required_stage_ids: set[str] | None = None,
) -> list[str]:
    """
    Decide el orden final de etapas del pipeline: filtra por habilitadas,
    agrega las requeridas faltantes y aplica el orden topológico.

    ``selectivity`` es una etapa canónica pero opcional: sólo se ejecuta si
    la opción de producto ``pro_selectivity`` la solicita. Su activación no
    depende de que el frontend la repita en ``enabled_stages``; así el mismo
    registro define plan, eventos ``stage_skipped`` y contrato de ejecución.

    Es la decisión que el runner usa para ejecutar etapas y para emitir
    stage_skipped sobre las del registro que quedaron fuera.
    """
    if stage_order is None:
        stage_order = list(STAGE_REGISTRY.keys())
    required = required_stage_ids or {
        stage_id for stage_id, stage in STAGE_REGISTRY.items() if stage.required
    }
    requested_ids = [
        s
        for s in stage_order
        if s != "selectivity"
        and (
            (enabled_stages and s in enabled_stages)
            or (
                STAGE_REGISTRY.get(s) is not None
                and STAGE_REGISTRY[s].required
                and s in required
            )
        )
    ]
    if selectivity_enabled:
        requested_ids.append("selectivity")

    ordered_ids, _ = validate_order(requested_ids, required_stage_ids=required)
    return ordered_ids


def skipped_stage_ids(ordered_ids: list[str]) -> list[str]:
    """
    Etapas del registro que NO corren en este pipeline → el runner las emite
    como eventos stage_skipped (contrato SSE: stage_id, label, reason).
    """
    return [sid for sid in STAGE_REGISTRY if sid not in ordered_ids]
