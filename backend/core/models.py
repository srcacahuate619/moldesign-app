"""
core/models.py

Contrato de datos de todo el sistema. Hay dos capas aquí:

1. ORM Models (SQLAlchemy): representan las tablas de SQLite
   (plataforma de referencia, modo DESKTOP). Se usan para leer/escribir
   en la DB. Solo viven en db/repository.py.

2. Pydantic Schemas: representan los datos que viajan entre servicios
   y que se exponen en la API. Se usan en routers, servicios y workers.

Por qué separarlos:
- Los ORM models tienen relaciones lazy-loaded que explotan fuera de
  una sesión de DB activa. Los Pydantic schemas son simples dataclasses
  serializables que funcionan en cualquier contexto.
- Los endpoints nunca deben exponer ORM objects directamente —
  siempre se convierten a Pydantic schemas antes de salir.
"""

import enum
import uuid
from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, Field, computed_field, field_validator, model_validator
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    JSON,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.sql import func


# ── Base ORM ──────────────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    """Base declarativa para todos los ORM models."""
    pass


class SQLiteJSON(JSON):
    """
    Columna JSON para SQLite — plataforma de referencia en modo DESKTOP.

    Reemplaza al JSONB de PostgreSQL (hallazgo de auditoría F-04) manteniendo
    el contrato de las DB existentes:

    - DDL: TEXT (afinidad TEXT), idéntico a lo que emitía el compensador
      @compiles de JSONB→TEXT que vivía en core/database.py.
    - Escritura: serializa con el json_serializer del engine
      (core/database._json_serializer) — json.dumps con soporte UUID/datetime.
    - Lectura: deserializa con el json_deserializer del engine — devuelve
      listas/dicts de Python, nunca strings.

    INVARIANTE (ver api/main.py): asignar SIEMPRE listas/dicts crudos de
    Python — nunca strings pre-serializados. El serializer hace json.dumps.
    """
    pass


@compiles(SQLiteJSON, "sqlite")
def _compile_sqlite_json_to_text(type_, compiler, **kw):  # noqa: ANN001
    """SQLite no tiene tipo JSON nativo: emitir TEXT (afinidad TEXT)."""
    return "TEXT"


# ── Enums ─────────────────────────────────────────────────────────────────────

class MoleculeStatus(str, enum.Enum):
    """
    Ciclo de vida de una molécula en el sistema.

    PENDING   → recién creada, esperando validación química
    VALIDATED → SMILES válido, propiedades calculadas
    DOCKING   → job de docking en cola o corriendo
    EVALUATED → docking completo, score calculado
    FAILED    → algún paso falló (ver error_message en EvaluationResult)
    """
    PENDING   = "pending"
    VALIDATED = "validated"
    DOCKING   = "docking"
    EVALUATED = "evaluated"
    FAILED    = "failed"


class MutationType(str, enum.Enum):
    """
    Tipo de transformación química que el usuario aplicó.
    Se guarda para poder reconstruir el árbol de modificaciones.
    """
    SUBSTITUTION    = "substitution"     # sustitución de grupo funcional
    BIOISOSTERE     = "bioisostere"      # reemplazo bioisostérico
    RING_CLOSURE    = "ring_closure"     # ciclación
    RING_OPENING    = "ring_opening"     # apertura de anillo
    ADDITION        = "addition"         # adición de grupo
    DELETION        = "deletion"         # eliminación de grupo
    STEREOCHEMISTRY = "stereochemistry"  # cambio estereoquímico
    SCAFFOLD        = "scaffold"         # cambio de scaffold completo


# ═════════════════════════════════════════════════════════════════════════════
# ORM MODELS — tablas de SQLite (plataforma de referencia, modo DESKTOP)
# ═════════════════════════════════════════════════════════════════════════════

class TargetORM(Base):
    """
    Target biologico (proteina) contra el que se hace el docking.
    Soporta cualquier PDB ID valido del RCSB Protein Data Bank.
    19+ targets pre-cargados en el instalador (GPCRs, quinasas,
    receptores nucleares, checkpoints inmunitarios, safety panel).
    El target por defecto es 5-HT1A (7E2Y, cadena R).
    La tabla permite agregar mas targets sin cambiar el schema.
    """
    __tablename__ = "targets"

    id          = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pdb_id      = Column(String(10), unique=True, nullable=False, index=True)
    name        = Column(String(200), nullable=False)
    chain       = Column(String(5), nullable=False, default="A")
    description = Column(Text, nullable=True)

    grid_center_x = Column(Float, nullable=False)
    grid_center_y = Column(Float, nullable=False)
    grid_center_z = Column(Float, nullable=False)
    grid_size_x   = Column(Float, nullable=False, default=20.0)
    grid_size_y   = Column(Float, nullable=False, default=20.0)
    grid_size_z   = Column(Float, nullable=False, default=20.0)

    # Novedad Multi-Target
    requires_cns      = Column(Boolean, default=False, nullable=False)
    structural_family = Column(String(50), nullable=True)
    therapeutic_family = Column(String(100), nullable=True)
    organism          = Column(String(100), nullable=True)
    resolution        = Column(Float, nullable=True)
    hotspots          = Column(SQLiteJSON, nullable=True) # Lista de residuos críticos: [{"name": "MET97", "importance": 1.0}, ...]

    # ── Composición del sitio de unión (doc 71) ──────────────────────────────
    # `chain` dice qué cadena se PREPARA; estos campos dicen qué cadenas FORMAN
    # el sitio. Separarlos es lo que evita el defecto que documenta el doc 71:
    # un sitio en la interfaz de un dímero anotado como si fuera monomérico.
    # Los mide `scripts/anotar_sitio_en_catalogo.py` sobre el PDB del RCSB; el
    # modo de preparación se DERIVA de aquí, nunca se anota como política.
    site_chains       = Column(SQLiteJSON, nullable=True)  # ["H", "I"], por aporte descendente
    site_chain_atoms  = Column(SQLiteJSON, nullable=True)  # {"H": 49, "I": 5}
    #: Con qué se sabe: "cocrystal_ligand" (contactos a <=4,5 A del ligando
    #: cristalizado, la evidencia fuerte) o "box_volume" (átomos dentro de la
    #: caja, que no distingue el bolsillo de la vecindad). La distinción viaja
    #: hasta la tarjeta: presentarlas como equivalentes afirma de más.
    site_evidence     = Column(String(30), nullable=True)
    site_ligand       = Column(String(10), nullable=True)  # el ligando que lo demuestra
    #: De donde salen los hotspots. NINGUNO viene del RCSB: los genero este
    #: repositorio. "auto_pocket_top15" son los 15 residuos mas cercanos al
    #: ligando holo AUTODETECTADO por `discover_pocket_from_pdb`;
    #: "box_ligand_contacts" son los residuos a <=4,5 A del ligando que ocupa la
    #: caja del catalogo, redereivados cuando los primeros describian otro sitio.
    #: El campo existe para que la interfaz no pueda presentarlos como oficiales.
    hotspots_source   = Column(String(30), nullable=True)
    #: Por que este receptor ya no forma parte del catalogo curado. `None` es lo
    #: normal. Se rellena cuando la resincronizacion encuentra en la base un
    #: objetivo que el catalogo ya no trae -2ONV y 5TXJ, los dos cristales de
    #: hexapeptido del doc 72-. NO se borra la fila: puede haber evaluaciones
    #: colgando de ella, y borrar el trabajo de alguien para limpiar una tabla
    #: no es una operacion que el arranque deba hacer solo.
    retired_reason    = Column(Text, nullable=True)
    affinity_threshold = Column(Float, nullable=True, default=-7.5) # Suelo de afinidad absoluta
    specificity_floor  = Column(Float, nullable=True, default=0.5)  # [NUEVO] Mínimo del multiplier de especificidad (0.1–0.5)
    is_hot             = Column(Boolean, default=False, nullable=False)
    spearman_rho       = Column(Float, nullable=True)
    calibration_date   = Column(DateTime(timezone=True), nullable=True)

    # Ruta lógica local del archivo .pdbqt preparado (listo para Vina)
    prepared_file_path = Column(String(500), nullable=True)
    is_prepared        = Column(Boolean, default=False, nullable=False)
    created_at         = Column(DateTime(timezone=True), server_default=func.now())
    cofactors_whitelist = Column(SQLiteJSON, nullable=True, default=[])

    # Custom Targets
    is_private         = Column(Boolean, default=False, nullable=False)
    is_community       = Column(Boolean, default=False, nullable=False)
    is_anti_target     = Column(Boolean, default=False, nullable=False)
    anti_target_risk   = Column(Text, nullable=True)  # Descripcion del riesgo de inhibir este target
    creator_id         = Column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    creator_username   = Column(String(50), nullable=True)

    # Preparaciones versionadas (MVP). Una variante es otro target privado e
    # inmutable: nunca sobrescribe el receptor fuente ni sus artefactos.
    preparation_parent_id = Column(
        Uuid(as_uuid=True), ForeignKey("targets.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    receptor_source_sha256 = Column(String(64), nullable=True, index=True)
    prepared_receptor_sha256 = Column(String(64), nullable=True, index=True)
    preparation_fingerprint = Column(String(64), nullable=True, index=True)
    preparation_recipe = Column(SQLiteJSON, nullable=True)
    preparation_toolchain = Column(SQLiteJSON, nullable=True)

    creator   = relationship("UserORM")
    molecules = relationship("MoleculeORM", back_populates="target")


# TRANS-ANON-002 (2026-08-30): aquí vivía `AnonymousLimitORM`, un cupo de
# evaluaciones gratuitas contado por dirección IP. En escritorio todo es
# `127.0.0.1`: el cupo medía máquinas, no personas. Sin cuenta se evalúa sin
# límite; la cuenta hace falta para guardar en Moldex y para certificar.
#
# La clase se retira para que una instalación nueva no cree la tabla. Las bases
# existentes **conservan** `anonymous_limits` con sus filas: eliminarla sería
# destructivo y no aporta nada, porque ya nadie la lee ni la escribe.


class UserORM(Base):
    """Usuario del sistema. Mínimo para el MVP."""
    __tablename__ = "users"

    id           = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email        = Column(String(320), unique=True, nullable=False, index=True)
    username     = Column(String(50), unique=True, nullable=False)
    hashed_password = Column(String(200), nullable=True) # Nullable for OAuth
    auth_provider = Column(String(50), default="local") # e.g. "supabase", "local"
    subscription_tier = Column(String(50), default="free") # "free" or "premium"
    solana_wallet_address = Column(String(64), nullable=True) # wallet auto-asignada o vinculada
    is_active    = Column(Boolean, default=True, nullable=False)
    created_at   = Column(DateTime(timezone=True), server_default=func.now())

    molecules = relationship("MoleculeORM", back_populates="user")


class MoleculeORM(Base):
    """
    Molécula diseñada por el usuario.

    parent_id permite reconstruir el árbol de modificaciones:
    lead_inicial → modificación_1 → modificación_2 → ...
    Esto es la base del sistema de "árbol evolutivo" del juego.
    """
    __tablename__ = "molecules"

    id        = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    smiles    = Column(Text, nullable=False)
    name      = Column(String(200), nullable=True)   # nombre opcional del usuario
    status    = Column(
        Enum(
            MoleculeStatus,
            values_callable=lambda e: [x.value for x in e],
            create_type=False,
        ),
        default=MoleculeStatus.PENDING,
        nullable=False,
        index=True,
    )
    mutation_type = Column(
        Enum(
            MutationType,
            values_callable=lambda e: [x.value for x in e],
            create_type=False,
        ),
        nullable=True,
    )

    # Árbol de modificaciones
    parent_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("molecules.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Foreign keys
    user_id   = Column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    target_id = Column(Uuid(as_uuid=True), ForeignKey("targets.id"), nullable=False)

    # Hash SHA-256 del SMILES canonicalizado.
    # Permite detectar moléculas duplicadas y usar cache de docking.
    smiles_hash = Column(String(64), nullable=False, index=True)
    is_saved    = Column(Boolean, default=False, server_default='false', nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relaciones
    user             = relationship("UserORM", back_populates="molecules")
    target           = relationship("TargetORM", back_populates="molecules")
    parent           = relationship("MoleculeORM", remote_side="MoleculeORM.id")
    evaluation_result = relationship(
        "EvaluationResultORM",
        back_populates="molecule",
        uselist=False,   # one-to-one
        cascade="all, delete-orphan",
    )


class EvaluationResultORM(Base):
    """
    Resultado completo de la evaluación de una molécula.
    One-to-one con MoleculeORM — cada molécula tiene como máximo un resultado.
    """
    __tablename__ = "evaluation_results"

    id          = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    molecule_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("molecules.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    # ── Docking (AutoDock Vina) ──────────────────────────────────────────────
    affinity_kcal    = Column(Float, nullable=True)   # kcal/mol, negativo = mejor
    affinity_score   = Column(Float, nullable=True)   # normalizado 0-100
    docking_poses    = Column(SQLiteJSON, nullable=True)   # lista de poses [{affinity, rmsd_lb, rmsd_ub}]
    poses_file_path  = Column(String(500), nullable=True)  # ruta .sdf local
    receptor_path    = Column(String(500), nullable=True)  # snapshot PDBQT por hash
    receptor_sha256  = Column(String(64), nullable=True)
    parsing_source   = Column(String(50), nullable=True)
    vina_version     = Column(String(50), nullable=True)
    vina_random_seed = Column(Integer, nullable=True)
    scientific_warnings = Column(SQLiteJSON, nullable=True)
    #: Evidencia geométrica/física por pose. ADITIVA y NULLABLE a propósito: las
    #: evaluaciones anteriores a esta etapa no la tienen, y su ausencia significa
    #: «no se validó», nunca «la pose falló». Ver
    #: `services/chemistry/structural_evidence.py` para el contrato versionado.
    structural_evidence = Column(SQLiteJSON, nullable=True)
    #: Recomendacion del selector de pose. ADITIVA y NULLABLE: una evaluacion
    #: anterior a la etapa se lee como `unavailable`, nunca como error. El
    #: selector RECOMIENDA; la pose principal sigue siendo Vina top-1. Ver
    #: `services/chemistry/pose_selection.py`.
    pose_selection = Column(SQLiteJSON, nullable=True)
    #: Protocolo de generacion 3D que ESTA corrida ejecuto. ADITIVA y NULLABLE:
    #: `None` en corridas anteriores, que se leen como «no informado» —que es lo
    #: que el dossier ya decia—, nunca como confórmero único confirmado.
    #:
    #: Se persiste en vez de derivarse de las poses porque las poses solo
    #: cuentan las conformaciones REPRESENTADAS en el top-K entregado. Cuantas
    #: se pidieron y cuantas se consiguieron de verdad es justo el denominador
    #: que se perderia, y es el que dice si la cobertura del ensemble fue la
    #: solicitada.
    docking_protocol = Column(SQLiteJSON, nullable=True)
    task_id          = Column(String(200), nullable=True)  # ID del dispatcher local
    hotspots_hit     = Column(SQLiteJSON, nullable=True)        # residuos con los que interactuó
    specificity_score = Column(Float, nullable=True)       # normalizado 0-100
    affinity_threshold = Column(Float, nullable=True)     # [NUEVO] Umbral del target usado en esta evaluación

    @property
    def celery_task_id(self) -> str | None:
        """Alias de lectura temporal para clientes API anteriores a schema v3.

        La columna SQLite antigua se copia a ``task_id`` durante el arranque.
        No usar este nombre dentro del backend nuevo.
        """
        return self.task_id

    # ── Propiedades fisicoquímicas (RDKit) ───────────────────────────────────
    molecular_weight = Column(Float, nullable=True)
    log_p            = Column(Float, nullable=True)
    tpsa             = Column(Float, nullable=True)   # Topological Polar Surface Area
    hbd              = Column(Integer, nullable=True) # H-bond donors
    hba              = Column(Integer, nullable=True) # H-bond acceptors
    rotatable_bonds  = Column(Integer, nullable=True)
    heavy_atom_count = Column(Integer, nullable=True)
    ring_count       = Column(Integer, nullable=True)
    sa_score         = Column(Float, nullable=True)   # Synthetic Accessibility Score (1-10)
    sa_reasons       = Column(SQLiteJSON, nullable=True)   # Lista de motivos (tensión de anillo, etc.)

    # ── Viabilidad Sanguínea (Capa 3: ADMET-AI & TabPFN) ─────────────────────
    blood_viability_score = Column(Float, nullable=True)
    blood_solubility_logs = Column(Float, nullable=True)
    blood_ppb_category    = Column(String(50), nullable=True)
    blood_bbb_permeable   = Column(Boolean, nullable=True)
    # v15: por qué salió ese veredicto de BBB, y el CNS MPO que lo acompaña.
    # El booleano solo no dejaba distinguir «lo dijo el modelo con p=0.98» de
    # «lo dijo una regla de polaridad contra el modelo».
    blood_bbb_motivo      = Column(Text, nullable=True)
    blood_cns_mpo         = Column(Float, nullable=True)
    blood_hia_permeable   = Column(Boolean, nullable=True)
    blood_systemic_reactivity = Column(SQLiteJSON, nullable=True)  # Lista de alertas de toxicidad
    # "evaluado" | "fallo" | "no_evaluado". Una lista de alertas vacía tiene dos
    # causas —el clasificador miró y no encontró nada, o no llegó a mirar— y
    # hasta el 2026-09-04 la interfaz las pintaba iguales, en verde. Ver
    # `chem/blood_viability.py`.
    blood_tabpfn_estado = Column(String(20), nullable=True)

    # ── Drug-likeness ────────────────────────────────────────────────────────
    lipinski_pass    = Column(Boolean, nullable=True)
    veber_pass       = Column(Boolean, nullable=True)
    qed              = Column(Float, nullable=True)  # QED: Bickerton et al., Nat Chem 2012

    # ── Drug-likeness extendido (Ghose/Egan/Muegge/Fsp3/PAINS) ─────────────
    ghose_pass       = Column(Boolean, nullable=True)  # Ghose drug-likeness filter
    egan_pass        = Column(Boolean, nullable=True)  # Egan bioavailability filter
    muegge_pass      = Column(Boolean, nullable=True)  # Muegge drug-likeness (>=2 passes)
    muegge_score     = Column(Integer, nullable=True)  # Muegge raw score (0-9)
    fsp3             = Column(Float, nullable=True)    # Fraction of sp3-hybridized carbons
    is_pains         = Column(Boolean, nullable=True)  # Matchea alguna subestructura PAINS
    pains_matches    = Column(SQLiteJSON, nullable=True)    # Subestructuras PAINS matcheadas

    # ── Scores normalizados (0–100 cada uno) ────────────────────────────────
    adme_score       = Column(Float, nullable=True)
    druglikeness_score = Column(Float, nullable=True)
    total_score      = Column(Float, nullable=True, index=True)  # score final del juego
    gnn_score        = Column(Float, nullable=True)              # score GNN RTMScore (Nivel 2)
    affinity_multiplier = Column(Float, nullable=True)
    specificity_multiplier = Column(Float, nullable=True)
    is_control       = Column(Boolean, default=False)           # si es True, se ignoran penalizaciones ADME

    # ── ML Scores (Nivel 3: stacking + multi-model) ──────────────────────────
    #
    # ml_pki: la REGRESION de XGBoost, en unidades de pKi. Es un numero
    # distinto de `xgb_score`, que es la probabilidad del CLASIFICADOR.
    #
    # POR QUE EXISTE ESTA COLUMNA. Hasta el 2026-09-04 esta prediccion no se
    # guardaba: se convertia a kcal/mol con -1.36 x pKi y se escribia ENCIMA de
    # `affinity_kcal`, que es donde vive el score de Vina. El dato primario se
    # perdia, y el aviso posterior seguia llamando al resultado «escala de
    # Vina». Ahora las dos predicciones se conservan por separado y
    # `affinity_kcal` no la toca nadie mas que el acoplamiento.
    ml_pki            = Column(Float, nullable=True)  # regresion XGBoost (pKi). NO es affinity_kcal.
    ml_pki_aplicada   = Column(Boolean, nullable=True)  # si el modelo estaba en dominio (ver in_applicability_domain)
    xgb_score         = Column(Float, nullable=True)  # XGBoost binder classifier probability
    clgnn_score       = Column(Float, nullable=True)  # CL-GNN contrastive learning score
    quantum_score     = Column(Float, nullable=True)  # xTB + MMFF94 quantum features
    ums_score         = Column(Float, nullable=True)  # Universal Metal Score (SMARTS warheads Zn2+, M5 para metaloenzimas)
    mmgbsa_score      = Column(Float, nullable=True)  # MM-GBSA delta G (OpenMM OBC2)
    # ── Los CUATRO pesos del stacking, cada uno con su nombre ────────────
    #
    # El engine resuelve cuatro —vina, xgb, gnn legacy y clgnn— y aqui solo se
    # guardaban tres. `stacking_gnn_weight` recibia el peso de la GNN LEGACY
    # (RTMScore, deprecada) y estaba comentado, descrito en la API, resumido en
    # la evidencia y IMPRESO EN EL PDF como si fuera el de CL-GNN.
    #
    # No es un detalle de nomenclatura. Para GPCR el artefacto vigente asigna
    # `gnn: 0.40` y no declara `clgnn`, que resuelve a 0.00. El dossier decia
    # «CL-GNN 0.40» sobre un modelo cuyo peso real era cero, y el 0.40 iba a un
    # modelo deprecado. El documento de evidencia atribuia una influencia al
    # modelo equivocado.
    stacking_vina_weight = Column(Float, nullable=True)  # peso de Vina
    stacking_xgb_weight  = Column(Float, nullable=True)  # peso del clasificador XGBoost
    stacking_gnn_weight  = Column(Float, nullable=True)  # peso de la GNN LEGACY (RTMScore, deprecada)
    #: v17. `NULL` en corridas anteriores significa «no se registro por
    #: separado», JAMAS «el peso era cero»: en esas filas el valor de CL-GNN es
    #: indeterminado y no se puede reconstruir.
    stacking_clgnn_weight = Column(Float, nullable=True)  # peso de CL-GNN
    stacking_effective_weights = Column(SQLiteJSON, nullable=True)
    stacking_degraded = Column(Boolean, nullable=True)
    stacking_missing_components = Column(SQLiteJSON, nullable=True)
    target_family     = Column(String(50), nullable=True)  # familia estructural del target

    #: ── M5-Zn (SCHEMA 20) ────────────────────────────────────────────
    #:
    #: El protocolo de metaloenzimas de zinc estuvo implementado y SIN LLAMADOR
    #: desde que se escribio: `zinc.py::calcular` no lo invocaba nadie en
    #: produccion. Estas columnas existen para que la corrida guarde lo que
    #: calculo, y para que el dossier lo LEA en vez de afirmarlo.
    #:
    #: `NULL` en las cuatro significa que M5-Zn no se ejecuto en esa corrida
    #: —porque no era un caso de metal, o porque es anterior a esta version—,
    #: nunca que el score fuera cero.
    m5_protocol_id = Column(String(64), nullable=True)
    #: `NULL` en los estados sin score. En REVIEW puede conservarse el numero
    #: calculado como evidencia auditable; solo VALIDATED habilita una conclusion.
    m5_score = Column(Float, nullable=True)
    #: VALIDATED | NOT_EVALUATED_MISSING_COMPONENT |
    #: REVIEW_OUT_OF_VALIDATED_TARGET | REVIEW_OUT_OF_VALIDATED_STRUCTURE |
    #: REVIEW_INVALID_BENCHMARK_SITE | REVIEW_BENCHMARK_PROVENANCE_INCOMPLETE |
    #: REVIEW_BENCHMARK_TOP1_NOT_METAL_COORDINATING | BLOCKED_PROTOCOL_NOT_AVAILABLE.
    #: Siempre presente cuando el caso es metalico: dice POR QUE el score es lo que es.
    m5_scientific_status = Column(String(48), nullable=True)
    #: Componentes requeridos que faltaron en esta corrida de perfil. Nullable para
    #: distinguir corridas anteriores al esquema 20 de una lista vacia real.
    m5_missing_components = Column(SQLiteJSON, nullable=True)
    #: El UMS SMARTS-only del §2 del ADR, que es la senal AUTORIZADA de los tres
    #: perfiles. NO es `ums_score`, que es el UMS historico —warheads + donantes
    #: + MolChamb— y sigue existiendo porque hay artefactos que lo usaron.
    #: Mezclarlos es el error que el §9.4 documenta, asi que viajan separados.
    ums_warhead = Column(Float, nullable=True)

    # ── Transparencia del modelo usado (F-21) ────────────────────────────────
    engine_used              = Column(String(50), nullable=True)   # motor hardware del router (gpu/cpu); None en pipeline eval
    fallback_reason          = Column(String(300), nullable=True)  # motivo del fallback a modelo universal
    in_applicability_domain  = Column(Boolean, nullable=True)      # dominio de aplicabilidad (dist. Mahalanobis)
    model_used               = Column(String(50), nullable=True)   # "family" | "universal" | None

    # ── Explainable AI (XAI) ──────────────────────────────────────────────────
    shap_values      = Column(SQLiteJSON, nullable=True)  # { "LogP": -0.2, "MW": +0.5 }
    gnn_attention    = Column(SQLiteJSON, nullable=True)  # [0.1, 0.8, 0.2, ...] pesos atómicos
    gnn_attention_svg= Column(Text, nullable=True)   # Mapa 2D de RDKit en formato SVG
    gnn_pharmacophores = Column(SQLiteJSON, nullable=True) # {"Aromaticos / Pi-Stacking": 45.0, ...} (ASCII keys, ver gnn_explainability.py + docs/36 UI-6)

    # ── Reporte IA ───────────────────────────────────────────────────────────
    ai_report        = Column(Text, nullable=True)   # reporte narrativo de Claude

    # ── Blockchain ───────────────────────────────────────────────────────────
    blockchain_tx_id  = Column(String(200), nullable=True)
    blockchain_hash   = Column(String(64), nullable=True)
    #: MOLDEX-SCI-001. Esta fila es una proyección mutable: `upsert_evaluation_result`
    #: la reescribe entera al reevaluar la molécula, y el sello sobrevivía a esa
    #: reescritura sin enterarse. Estas dos columnas anclan el sello a lo que
    #: realmente certificó, de modo que Moldex pueda detectar la divergencia en
    #: vez de mostrar CERTIFIED junto a un número que la cadena nunca atestiguó.
    #: `NULL` en sellos anteriores a v14: indeterminado, jamás «coincide».
    certified_task_id     = Column(String(200), nullable=True)
    certified_total_score = Column(Float, nullable=True)

    # ── Selectividad (Anti-Targets) ───────────────────────────────────────────
    # `selectivity_ratio` es el cociente ΔG_on/ΔG_off, que NO tiene sentido
    # termodinámico (ver `services/docking/selectividad_margen.py`). Se conserva
    # sin tocar porque hay corridas guardadas con él y borrar datos del usuario
    # no es una opción; lo que se dejó de hacer es DERIVAR conclusiones de él.
    selectivity_ratio   = Column(Float, nullable=True)
    #: ΔΔG = ΔG_off − ΔG_on, en kcal/mol. La magnitud correcta, y la que manda
    #: en el veredicto. Nullable: las corridas anteriores no la tienen.
    selectivity_delta_delta_g = Column(Float, nullable=True)
    #: Qué se le hizo al SMILES antes de acoplarlo: tautómero elegido, estado
    #: de protonación a pH 7.4, alternativas descartadas y carga formal neta.
    #: Ver `chem/conformer.py`. Nullable: las corridas anteriores no lo tienen.
    ligand_state        = Column(SQLiteJSON, nullable=True)
    selectivity_verdict = Column(String(160), nullable=True)
    selectivity_ran     = Column(Boolean, default=False)
    anti_target_results = Column(SQLiteJSON, nullable=True)

    # ── Metadatos ────────────────────────────────────────────────────────────
    error_message    = Column(Text, nullable=True)   # si status == FAILED
    evaluated_at     = Column(DateTime(timezone=True), server_default=func.now())

    molecule = relationship("MoleculeORM", back_populates="evaluation_result")


class BatchRunORM(Base):
    """Estado operativo durable del batch legacy; no modifica scores."""

    __tablename__ = "batch_runs"
    batch_id = Column(String(36), primary_key=True)
    owner_id = Column(String(200), nullable=False)
    status = Column(String(20), nullable=False)
    payload_json = Column(SQLiteJSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class EvaluationRequestORM(Base):
    """Solicitud operativa durable; no modifica el contrato científico."""

    __tablename__ = "evaluation_requests"
    task_id = Column(String(200), primary_key=True)
    owner_id = Column(String(200), nullable=False)
    client_ip = Column(String(200), nullable=True)
    configuration_json = Column(SQLiteJSON, nullable=False)
    status = Column(String(16), nullable=False, default="PENDING")
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    finished_at = Column(DateTime(timezone=True), nullable=True)


class EvaluationRunORM(Base):
    """Snapshot inmutable de una corrida terminada.

    ``evaluation_results`` sigue siendo la proyección más reciente de una
    molécula para no romper la API histórica. Esta tabla conserva lo que cada
    ``task_id`` produjo realmente, de modo que casos y cohortes no cambien al
    ejecutar de nuevo la misma molécula.
    """

    __tablename__ = "evaluation_runs"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(String(200), unique=True, nullable=False, index=True)
    molecule_id = Column(
        Uuid(as_uuid=True), ForeignKey("molecules.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    projected_result_id = Column(Uuid(as_uuid=True), nullable=True)
    snapshot_json = Column(SQLiteJSON, nullable=False)
    # El snapshot cientifico es inmutable; el estado terminal puede corregirse
    # si cancelacion/watchdog ganan la carrera justo despues de congelarlo.
    status = Column(String(16), nullable=False, default="SUCCESS")
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class CohortORM(Base):
    """
    Cohorte comprobada y CONGELADA. La fuente inmutable de una ejecución futura.

    # Por qué guarda el archivo entero

    Una cohorte se define por lo que se subió. Si sólo guardáramos las filas ya
    interpretadas, dentro de seis meses nadie podría comprobar que la
    interpretación fue fiel; y si sólo guardáramos el archivo, la ejecución
    tendría que volver a interpretarlo con las reglas de ese día. Se guardan
    **los dos**: `source_bytes` es lo que la persona entregó y
    `preflight_snapshot_json` es el veredicto que se le enseñó.

    BLOB en SQLite, no un archivo aparte: el límite de ingesta son 8 MB, y una
    ruta en disco introduce el estado que este producto no quiere —una fila que
    afirma tener un archivo que ya no está, o un archivo que sobrevive a la
    fila. Con el BLOB, la cohorte se guarda entera o no se guarda.

    # Qué NO tiene esta tabla

    No hay `UPDATE`. Ni receptor, ni configuración, ni filas, ni fingerprint
    cambian nunca: cambiar cualquiera de ellos produce OTRA cohorte, con su
    propio preflight. Tampoco hay unicidad sobre `cohort_fingerprint` — dos
    cohortes idénticas pueden coexistir a propósito, porque deduplicar en
    silencio le quitaría a alguien un registro que creó a conciencia.

    # Estado

    `status` es sólo `ready` en este sprint. Es una cadena y no un Enum porque
    5C añadirá los estados de ejecución y un Enum de un solo valor no gana
    nada; el vocabulario vivo está en `services/cohort/schemas.py`.
    """

    __tablename__ = "cohorts"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    #: Versión del contrato de preflight con el que se congeló.
    schema_version = Column(Integer, nullable=False)
    name = Column(String(300), nullable=False)
    status = Column(String(16), nullable=False, default="ready")
    #: `sha256:<64 hex>`. Indexado para poder encontrar cohortes equivalentes;
    #: NO es único: ver el docstring de la clase.
    cohort_fingerprint = Column(String(80), nullable=False, index=True)

    # ── El archivo, tal como llegó ───────────────────────────────────────────
    #: Sólo el nombre base y saneado. Nunca una ruta del equipo de nadie.
    source_filename = Column(String(255), nullable=False)
    source_content_type = Column(String(128), nullable=True)
    source_sha256 = Column(String(64), nullable=False, index=True)
    source_bytes = Column(LargeBinary, nullable=False)
    source_size_bytes = Column(Integer, nullable=False)

    # ── Lo congelado ─────────────────────────────────────────────────────────
    normalized_study_json = Column(SQLiteJSON, nullable=False)
    #: `CohortPreflightResult` completo, filas inválidas y duplicadas incluidas.
    #: Es el veredicto que se le enseñó a quien aceptó la cohorte, y es lo que
    #: la ejecución de 5C tiene que consumir: recalcular la elegibilidad con
    #: otra versión de RDKit produciría una cohorte distinta de la aceptada.
    preflight_snapshot_json = Column(SQLiteJSON, nullable=False)
    #: Versiones y sello temporal de la congelación. Sólo lo obtenible de
    #: verdad: una versión ausente se omite, no se inventa.
    provenance_json = Column(SQLiteJSON, nullable=False)

    user_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class CohortRunORM(Base):
    """
    Una EJECUCIÓN de una cohorte congelada.

    # Por qué es una tabla y no un estado dentro de `cohorts`

    La cohorte es inmutable: es lo que alguien aceptó. Una corrida es lo que le
    pasó a esa cohorte una vez. Meter el estado de ejecución en `cohorts`
    obligaría a hacer `UPDATE` sobre el registro congelado —el mismo `UPDATE`
    que 5B se prohibió— y una cohorte no podría ejecutarse dos veces sin
    borrar la historia de la primera.

    **Ningún estado de ejecución toca `CohortORM`.** Ni el status, ni los
    contadores, ni el último error.

    # Por qué el fingerprint de la corrida es distinto del de la cohorte

    `cohort_fingerprint` identifica QUÉ se va a ejecutar. `run_fingerprint`
    identifica CÓMO: la caja efectiva, el receptor preparado concreto —por su
    SHA-256—, el motor y su versión, la semilla. La misma cohorte ejecutada
    contra un receptor repreparado es la misma cohorte y otra corrida, y los
    dos hashes juntos lo dicen sin ambigüedad.
    """

    __tablename__ = "cohort_runs"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cohort_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("cohorts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    #: Vocabulario vivo en `services/cohort/execution.py`.
    status = Column(String(32), nullable=False, default="queued", index=True)
    #: Copiado de la cohorte al crear la corrida. Redundante a propósito: deja
    #: la corrida legible sin tener que ir a buscar la cohorte.
    cohort_fingerprint = Column(String(80), nullable=False)
    run_fingerprint = Column(String(80), nullable=False, index=True)
    #: Caja, motor, exhaustividad, poses y semilla EFECTIVOS. Si la cohorte
    #: omitió la caja, aquí está la que se resolvió del catálogo — resuelta una
    #: vez, al crear la corrida, y nunca por fila.
    effective_config_json = Column(SQLiteJSON, nullable=False)
    #: Qué receptor preparado se usó, con su SHA-256 y de dónde salió.
    receptor_provenance_json = Column(SQLiteJSON, nullable=False)
    #: Copia exacta e inmutable del PDBQT usado. El objeto del catálogo es
    #: mutable; el hash solo detecta cambios, pero no permite reproducirlos.
    receptor_prepared_bytes = Column(LargeBinary, nullable=True)

    #: Contadores DERIVADOS de las filas. Se recalculan desde ellas al arrancar
    #: la aplicación: un contador que sobrevive a un corte sin que las filas lo
    #: respalden es un contador que miente.
    total_rows = Column(Integer, nullable=False, default=0)
    eligible_rows = Column(Integer, nullable=False, default=0)
    completed_rows = Column(Integer, nullable=False, default=0)
    failed_rows = Column(Integer, nullable=False, default=0)
    not_evaluated_rows = Column(Integer, nullable=False, default=0)

    #: Intención de cancelar. NO es un estado: es una bandera que el ejecutor
    #: consulta antes de empezar cada fila. Las filas ya terminadas se conservan.
    cancel_requested = Column(Boolean, nullable=False, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)

    cohort = relationship("CohortORM")
    rows = relationship(
        "CohortRunRowORM", back_populates="run", cascade="all, delete-orphan"
    )


class CohortRunRowORM(Base):
    """
    Una molécula dentro de una corrida. La unidad durable del progreso.

    # Sólo entran las filas `eligible`

    Las `invalid_input` del snapshot NO se insertan: no son trabajo científico
    pendiente, son entradas que nunca van a ejecutarse. Insertarlas como
    `not_evaluated` las mezclaría con las moléculas que sí entraron y el motor
    no pudo evaluar, que es un hecho completamente distinto.

    Sus cantidades no desaparecen: `eligible_rows` frente a
    `snapshot.summary.total_rows` sigue diciendo cuántas quedaron fuera, y el
    detalle de la corrida publica los dos números.

    # Por qué el estado se persiste ANTES de ejecutar

    `running` se escribe y se confirma antes de llamar al pipeline. Si el
    proceso muere a mitad de un docking, al arrancar queda una fila en
    `running` que el arranque convierte en `interrupted`. Escribir el estado
    después dejaría una fila `pending` indistinguible de una que nunca empezó,
    y la reanudación repetiría trabajo ya hecho o lo daría por no hecho.
    """

    __tablename__ = "cohort_run_rows"
    __table_args__ = (
        # Una fila del archivo aparece UNA vez por corrida. Sin esto, un
        # reintento a medias podría duplicar el trabajo de una molécula.
        UniqueConstraint("run_id", "source_row_index", name="uq_cohort_run_row"),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("cohort_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    #: Índice en el ARCHIVO original, tal como lo fijó el preflight. Es el
    #: vínculo con el snapshot congelado, no una posición en esta tabla.
    source_row_index = Column(Integer, nullable=False)
    #: Congelado del snapshot. NUNCA se recanonicaliza: recalcularlo con otra
    #: versión de RDKit ejecutaría una molécula distinta de la aceptada.
    canonical_smiles = Column(Text, nullable=False)
    source_name = Column(String(300), nullable=True)
    control_role = Column(String(16), nullable=False, default="none")
    active_label = Column(Boolean, nullable=True)
    #: Del snapshot: qué fila del ARCHIVO repite esta molécula.
    duplicate_of_row = Column(Integer, nullable=True)

    status = Column(String(24), nullable=False, default="pending", index=True)
    molecule_id = Column(Uuid(as_uuid=True), nullable=True)
    result_id = Column(Uuid(as_uuid=True), nullable=True)
    #: De EJECUCIÓN: qué fila corrió de verdad el docking que esta reutiliza.
    #: Distinto de `duplicate_of_row`, que es procedencia del archivo.
    reused_from_row = Column(Integer, nullable=True)
    error_code = Column(String(64), nullable=True)
    error_detail = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)

    run = relationship("CohortRunORM", back_populates="rows")


# ═════════════════════════════════════════════════════════════════════════════
# PYDANTIC SCHEMAS — contratos de datos entre servicios y API
# ═════════════════════════════════════════════════════════════════════════════

class PhysicochemicalProperties(BaseModel):
    """
    Propiedades fisicoquímicas calculadas por RDKit.
    Viajan desde chem/properties.py hacia scoring/engine.py y la API.
    """
    molecular_weight: float = Field(..., ge=0, description="Peso molecular en Da")
    log_p:            float = Field(..., description="Coeficiente de partición octanol/agua")
    tpsa:             float = Field(..., ge=0, description="Área polar topológica superficial en Å²")
    hbd:              int   = Field(..., ge=0, description="Número de dadores de H-bond")
    hba:              int   = Field(..., ge=0, description="Número de aceptores de H-bond")
    rotatable_bonds:  int   = Field(..., ge=0)
    heavy_atom_count: int   = Field(..., ge=1)
    ring_count:       int   = Field(..., ge=0)
    qed:              float = Field(..., ge=0, le=1, description="QED score")
    sa_score:         float = Field(..., ge=1, le=10, description="Synthetic Accessibility Score (1-10, lower is easier)")
    sa_reasons:       list[str] = Field(default_factory=list, description="Motivos de la dificultad sintética")
    lipinski_pass:    bool
    veber_pass:       bool
    ghose_pass:       bool | None = Field(None, description="Ghose drug-likeness filter")
    egan_pass:        bool | None = Field(None, description="Egan bioavailability filter")
    muegge_pass:      bool | None = Field(None, description="Muegge drug-likeness score (>=2 passes)")
    muegge_score:     int  | None = Field(None, ge=0, le=9, description="Muegge raw score (0-9)")
    fsp3:             float | None = Field(None, ge=0, le=1, description="Fraction of sp3-hybridized carbons")

    # ── PAINS filter ──────────────────────────────────────────────────────
    is_pains:         bool = Field(False, description="Does the molecule match any PAINS substructure?")
    pains_matches:    list[dict] = Field(default_factory=list, description="List of matched PAINS substructures")

    # ── Viabilidad Sanguínea (ADMET-AI & TabPFN) ────────────────────────────
    blood_viability_score: float | None = Field(None, description="Score combinado MPO de viabilidad sanguínea")
    blood_solubility_logs: float | None = Field(None, description="Solubilidad acuosa logS")
    blood_ppb_category: str | None = Field(None, description="Categoría de unión a proteínas plasmáticas (low, high, extreme)")
    blood_bbb_permeable: bool | None = Field(None, description="¿Cruza la barrera hematoencefálica?")
    blood_bbb_motivo: str | None = Field(None, description="Qué regla del consenso decidió la permeabilidad, y con qué números")
    blood_cns_mpo: float | None = Field(None, ge=0, le=6, description="CNS MPO de Pfizer (Wager et al. 2010), 0-6. Informa; no decide la permeabilidad")
    blood_hia_permeable: bool | None = Field(None, description="¿Se absorbe en el intestino?")
    blood_systemic_reactivity: list[str] = Field(default_factory=list, description="Alertas de toxicidad TabPFN/PAINS")
    blood_tabpfn_estado: str | None = Field(
        None,
        description=(
            '"evaluado" | "fallo" | "no_evaluado". Sin esto, una lista de '
            "alertas vacía no distingue «no encontró nada» de «no corrió»."
        ),
    )

    @model_validator(mode="after")
    def validate_lipinski_consistency(self) -> "PhysicochemicalProperties":
        """
        Verifica que lipinski_pass sea coherente con los valores calculados.
        Lipinski: MW ≤ 500, logP ≤ 5, HBD ≤ 5, HBA ≤ 10.
        Si hay inconsistencia, es un bug en chem/properties.py.
        """
        expected = (
            self.molecular_weight <= 500
            and self.log_p <= 5
            and self.hbd <= 5
            and self.hba <= 10
        )
        if self.lipinski_pass != expected:
            raise ValueError(
                f"lipinski_pass={self.lipinski_pass} es inconsistente con "
                f"MW={self.molecular_weight}, logP={self.log_p}, "
                f"HBD={self.hbd}, HBA={self.hba}. "
                f"Valor esperado: {expected}"
            )
        return self


class DockingPose(BaseModel):
    """Una sola pose de docking retornada por AutoDock Vina."""
    rank:     int   = Field(..., ge=1)
    affinity: float = Field(..., description="Energía de unión en kcal/mol. Más negativo = mejor.")
    rmsd_lb:  float = Field(..., ge=0, description="RMSD lower bound vs pose 1")
    rmsd_ub:  float = Field(..., ge=0, description="RMSD upper bound vs pose 1")
    pdbqt_block: str | None = Field(None, description="Bloque PDBQT de la pose para rescoring.")
    #: De qué conformación de entrada salió esta pose.
    #:
    #: `None` con confórmero único —el protocolo por defecto—, que es la mayoría
    #: de las corridas y todas las anteriores a esta etapa. Con ensemble, las
    #: poses de las K corridas de Vina se juntan en una sola piscina y se
    #: reordenan por afinidad: sin este campo, la pose 1 podría venir de una
    #: conformación y la 2 de otra sin que nada lo dijera, y el lector no
    #: podría saber si dos poses parecidas son la misma solución encontrada dos
    #: veces o dos soluciones distintas.
    conformer_index: int | None = Field(
        None, ge=0, description="Índice 0-based de la conformación de origen. None si K=1."
    )


class DockingResult(BaseModel):
    """Resultado completo del docking de una molécula contra un target."""
    best_affinity: float              = Field(..., description="Mejor afinidad (pose 1) en kcal/mol")
    poses:         list[DockingPose]  = Field(..., min_length=1)
    poses_file_path: str | None       = None   # ruta .sdf local
    #: De dónde salieron las poses que este resultado informa.
    #:
    #: `sdf_openbabel_cli` se añadió el 2026-09-05 y arregla un defecto real:
    #: cuando la exportación de Meeko producía un SDF zombi, `vina_service`
    #: rescataba la conversión con Open Babel y asignaba `"openbabel"`, que
    #: **no estaba en este `Literal`**. Construir el resultado reventaba con un
    #: `ValidationError` justo en el caso en que el respaldo había funcionado.
    #:
    #: El nombre dice las dos cosas que hay que saber: el formato del que se
    #: parseó (`sdf`) y que lo produjo Open Babel invocado como herramienta de
    #: línea de órdenes (`openbabel_cli`), no como biblioteca enlazada. Esa
    #: distinción es la frontera de licencia descrita en
    #: `docs/79_ADR_FRONTERA_OPEN_BABEL.md`, y por eso viaja en la procedencia.
    parsing_source: Literal["sdf", "pdbqt", "vina_stdout", "sdf_openbabel_cli"] = "sdf"
    #: Qué programa externo produjo el archivo de poses, cuando no fue Meeko.
    #:
    #: `None` en todas las corridas normales y en todas las anteriores a esta
    #: etapa. Sólo se rellena en el camino de respaldo, y lleva versión, hash,
    #: licencia y ruta relativa del programa que de verdad se ejecutó: un
    #: informe no debería tener que volver a preguntarle al disco quién produjo
    #: su evidencia.
    conversor_estructural: dict | None = None
    vina_version: str | None = None
    vina_random_seed: int | None = None
    # ── El protocolo EJECUTADO ────────────────────────────────────────────
    # Lo que se pidió y lo que se corrió pueden diferir, y hasta ahora sólo
    # viajaba lo pedido. Ejemplo medido: con `docking_engine="qvina2"` y el
    # binario ausente, `vina_service` cae a Vina con exhaustiveness=4 y escribe
    # un `log.warning` — pero el protocolo que se sellaba en el dossier seguía
    # diciendo «qvina2» con el exhaustiveness solicitado. El sello describía una
    # corrida que no ocurrió.
    engine_efectivo: str | None = None
    exhaustiveness_efectiva: int | None = None
    num_poses_solicitadas: int | None = None
    #: SHA-256 del receptor preparado que ESTA corrida acoplo. Viaja el hash y
    #: no los bytes: el receptor pesa cientos de KB y este objeto se cachea.
    #: Con el hash, la validacion posterior puede COMPROBAR que el receptor del
    #: disco sigue siendo el mismo, y abstenerse si se repreparo.
    receptor_sha256: str | None = None
    #: Ruta lógica content-addressed a los bytes exactos. A diferencia de
    #: ``targets/{pdb}/prepared.pdbqt``, esta ruta no cambia al repreparar.
    receptor_path: str | None = None
    execution_time_s: float | None = None
    # `str` sigue aceptándose: es lo que guardaron las corridas anteriores a la
    # severidad declarada, y la columna es JSON, así que no hay migración. Ver
    # `services/avisos.py` para por qué la severidad ya no se deduce del texto.
    scientific_warnings: list[str | dict] = Field(default_factory=list)
    hotspots_hit: list[str] = Field(default_factory=list)
    #: Manifiesto de transferencia ESMFold->ligando, si el protocolo peptidico lo produjo.
    peptide_transfer_manifest: dict[str, Any] | None = None

    @field_validator("best_affinity")
    @classmethod
    def affinity_must_be_non_positive(cls, v: float) -> float:
        """
        Las afinidades de Vina son siempre negativas si hay interacción.
        Un valor > 0 indica un error en el parsing del output de Vina.
        Permitimos 0.0 como caso borde de "ausencia de interacción" para evitar
        crashes de validación, aunque se tratará como score cero.
        """
        if v > 0:
            raise ValueError(
                f"La afinidad de docking debe ser negativa o cero (got {v}). "
                "Un valor > 0 indica un error en el parsing de Vina."
            )
        return v


class MoleculeCreate(BaseModel):
    """Schema para crear una molécula nueva. Input del endpoint POST /molecules."""
    smiles:        str              = Field(..., min_length=1, max_length=2000)
    name:          str | None       = Field(None, max_length=200)
    target_pdb_id: str              = Field(..., min_length=4, max_length=10)
    parent_id:     uuid.UUID | None = None
    mutation_type: MutationType | None = None

    @field_validator("smiles")
    @classmethod
    def smiles_must_not_be_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("SMILES no puede ser un string vacío o solo espacios")
        return stripped


class MoleculeRead(BaseModel):
    """Schema de respuesta al leer una molécula. Output de la API."""
    id:            uuid.UUID
    smiles:        str
    name:          str | None
    status:        MoleculeStatus
    mutation_type: MutationType | None
    parent_id:     uuid.UUID | None
    user_id:       uuid.UUID
    target_id:     uuid.UUID
    smiles_hash:   str
    is_saved:      bool
    created_at:    datetime
    updated_at:    datetime | None

    model_config = {"from_attributes": True}  # permite crear desde ORM object


class EvaluationResultRead(BaseModel):
    """Schema de respuesta completa de evaluación. Output principal de la API."""
    id:            uuid.UUID
    molecule_id:   uuid.UUID

    # Docking
    affinity_kcal:   float | None
    affinity_score:  float | None
    docking_poses:   list[DockingPose] | None
    poses_file_path: str | None        # ruta local al .sdf de poses
    receptor_path: str | None = None
    receptor_sha256: str | None = None
    parsing_source:  str | None
    vina_version:    str | None
    vina_random_seed: int | None
    #: Cada aviso es `{codigo, severidad, mensaje}`; las corridas antiguas
    #: guardaron cadenas sueltas y se leen como `severidad="heredada"`.
    scientific_warnings: list[str | dict] | None
    #: Contrato versionado de `services/chemistry/structural_evidence.py`.
    #: `None` en evaluaciones anteriores a la etapa; el cliente debe leerlo como
    #: «no evaluada», no como error.
    structural_evidence: dict[str, Any] | None = None
    #: Contrato versionado de `services/chemistry/pose_selection.py`. `None` en
    #: evaluaciones anteriores; el cliente debe leerlo como `unavailable`.
    pose_selection: dict[str, Any] | None = None
    #: Protocolo de generacion 3D de esta corrida. `None` en corridas anteriores.
    docking_protocol: dict[str, Any] | None = None
    task_id: str | None = None
    # Alias temporal de API: se retira en una versión mayor tras dar tiempo de
    # actualización a integraciones que aún lean este campo.
    celery_task_id: str | None = None

    # Propiedades
    molecular_weight: float | None
    log_p:            float | None
    tpsa:             float | None
    hbd:              int | None
    hba:              int | None
    rotatable_bonds:  int | None
    heavy_atom_count: int | None
    ring_count:       int | None
    lipinski_pass:    bool | None
    veber_pass:       bool | None
    ghose_pass:       bool | None = None
    egan_pass:        bool | None = None
    muegge_pass:      bool | None = None
    muegge_score:     int | None = None
    fsp3:             float | None = None
    is_pains:         bool | None = None
    pains_matches:    list[dict] | None = None
    qed:              float | None
    sa_score:         float | None
    sa_reasons:       list[str] | None

    # Scores
    adme_score:         float | None
    druglikeness_score: float | None
    total_score:        float | None   # 0–100, el score del juego
    gnn_score:          float | None = None  # Score GNN RTMScore (Nivel 2, opcional)

    # ML Scores (Nivel 3) — serializados desde ORM (EvaluationResultORM)
    #: Regresión de XGBoost en pKi. NO es `affinity_kcal`; ver el ORM.
    ml_pki:               float | None = None
    #: Si esa predicción cayó dentro del dominio de aplicabilidad del modelo.
    ml_pki_aplicada:      bool | None = None
    xgb_score:            float | None = None  # XGBoost binder classifier probability
    clgnn_score:          float | None = None  # CL-GNN contrastive learning score
    quantum_score:        float | None = None  # xTB + MMFF94 quantum features
    ums_score:            float | None = None  # Universal Metal Score (SMARTS warheads Zn2+, M5)
    mmgbsa_score:         float | None = None  # MM-GBSA delta G (OpenMM OBC2)
    stacking_vina_weight: float | None = None  # peso de Vina
    stacking_xgb_weight:  float | None = None  # peso del clasificador XGBoost
    stacking_gnn_weight:  float | None = None  # peso de la GNN LEGACY (RTMScore)
    stacking_clgnn_weight: float | None = None  # peso de CL-GNN
    # M5-Zn (SCHEMA 20). `None` = el protocolo no se ejecuto en esta corrida.
    stacking_effective_weights: dict[str, float] | None = None
    stacking_degraded: bool | None = None
    stacking_missing_components: list[str] | None = None
    m5_protocol_id:       str | None = None
    m5_score:             float | None = None
    m5_scientific_status: str | None = None
    m5_missing_components: list[str] | None = None
    ums_warhead:          float | None = None
    target_family:        str | None = None    # familia estructural del target

    # Transparencia del modelo usado (F-21) — valores persistidos por WS2
    engine_used:              str | None = None  # "gpu"/"cpu" del router hardware; None en pipeline eval (no usa router)
    fallback_reason:          str | None = None  # motivo del fallback (p. ej. familia sin modelo validado por quality gate)
    in_applicability_domain:  bool | None = None # dominio de aplicabilidad del modelo (dist. Mahalanobis vs umbral core)
    model_used:               str | None = None  # "family" | "universal" | None (target sin modelo de familia)

    specificity_score:  float | None = None
    hotspots_hit:       list[str] | None = None
    target_hotspots:    list[dict] | None = None
    affinity_threshold: float | None = None
    affinity_multiplier: float | None = None
    specificity_multiplier: float | None = None
    target_name:        str | None = None
    target_spearman_rho: float | None = None
    #: SC-9: el respaldo del receptor **en el momento de la corrida**. Se
    #: congela con el resultado para que el dossier y la reapertura digan lo que
    #: se sabía al ejecutar, no lo que se sepa hoy.
    target_calibracion: dict[str, Any] | None = None

    # MPO / ADMET Predicts
    blood_viability_score: float | None = None
    blood_solubility_logs: float | None = None
    blood_ppb_category:    str | None = None
    blood_bbb_permeable:   bool | None = None
    blood_bbb_motivo:      str | None = None
    blood_cns_mpo:         float | None = None
    blood_hia_permeable:   bool | None = None
    blood_systemic_reactivity: list[str] | None = None
    blood_tabpfn_estado: str | None = None

    # XAI
    shap_values:        dict[str, float] | None = None
    gnn_attention:      list[float] | None = None
    gnn_attention_svg:  str | None = None
    gnn_pharmacophores: dict[str, float] | None = None

    # Selectividad (anti-targets)
    selectivity_ratio: float | None = None
    #: ΔΔG en kcal/mol. `None` en corridas anteriores a esta métrica.
    selectivity_delta_delta_g: float | None = None
    #: Estado químico del ligando acoplado. `None` en corridas anteriores.
    ligand_state: dict[str, Any] | None = None
    selectivity_verdict: str | None = None
    anti_target_results: list[dict] | None = None  # per-anti-target docking results
    selectivity_ran: bool | None = None  # si se ejecuto el panel

    @computed_field
    @property
    def ligand_efficiency(self) -> float | None:
        """
        LE = affinity_kcal / heavy_atom_count
        """
        if self.affinity_kcal is not None and self.heavy_atom_count and self.heavy_atom_count > 0:
            return round(self.affinity_kcal / self.heavy_atom_count, 3)
        return None

    @computed_field
    @property
    def ligand_lipophilicity_efficiency(self) -> float | None:
        """
        LLE = (-affinity_kcal / 1.36) - log_p
        """
        if self.affinity_kcal is not None and self.log_p is not None:
            return round((-self.affinity_kcal / 1.36) - self.log_p, 3)
        return None

    # ── Eficiencia normalizada por tamaño ────────────────────────────────
    #
    # `ligand_efficiency` de arriba depende del tamaño de forma sistemática.
    # Medido sobre la cohorte de acoplamiento de este proyecto (8 dianas,
    # 17 431 moléculas), correlación de Spearman con el número de átomos
    # pesados, en valor absoluto y promediada por diana:
    #
    #     |Vina| crudo           0.817
    #     LE = |Vina| / HA       0.824   <- no corrige nada; sólo invierte el signo
    #     SILE (HA^0.3)          0.370
    #     FQ (Reynolds, proxy)   0.216
    #
    # Las dos de abajo son las métricas normalizadas de la literatura. Se
    # derivan igual que LE —de `affinity_kcal`, que desde el 2026-09-04 vuelve
    # a ser el score de Vina sin transformar— en vez de guardarse en columnas
    # nuevas: así no pueden quedar desincronizadas con la afinidad.
    #
    # NINGUNA entra en `total_score`. Ver `scoring/eficiencia.py`.

    @computed_field
    @property
    def sile_vina(self) -> float | None:
        """SILE = |afinidad| / HA^0.3 (Nissink, J. Chem. Inf. Model. 49:1617, 2009).

        Sin umbral: el artículo no publica ninguno.
        """
        from scoring.eficiencia import calcular

        metricas = calcular(self.affinity_kcal, self.heavy_atom_count or 0)
        return metricas.sile_vina if metricas else None

    @computed_field
    @property
    def fq_vina_proxy(self) -> float | None:
        """Fit Quality de Reynolds (J. Med. Chem. 51:2432, 2008) sobre un proxy.

        PROXY, y por eso el nombre: Reynolds ajustó la escala contra Ki
        experimental, no contra scores de acoplamiento. FQ ≈ 1 es proximidad a
        la envolvente eficiente de su conjunto PARA ESE TAMAÑO; no es una
        probabilidad de unión ni una medida de calidad de pose.
        """
        from scoring.eficiencia import calcular

        metricas = calcular(self.affinity_kcal, self.heavy_atom_count or 0)
        return metricas.fq_vina_proxy if metricas else None

    is_control:        bool = False

    # Reporte
    ai_report:         str | None
    # Blockchain
    blockchain_tx_id:  str | None

    error_message: str | None
    evaluated_at:  datetime

    model_config = {"from_attributes": True}

    @model_validator(mode="after")
    def _normalize_legacy_task_id(self):
        """Acepta payloads v2 y devuelve ambos nombres durante la transición."""
        if self.task_id is None:
            self.task_id = self.celery_task_id
        self.celery_task_id = self.task_id
        return self

    @model_validator(mode="after")
    def _pose_selection_siempre_declarada(self):
        """
        Una evaluación ANTERIOR a la etapa abre como `unavailable`, no como
        `null`.

        En la columna el valor sigue siendo NULL —la migración es aditiva y no
        reescribe historia—, pero un `null` cruzando la API obliga a cada
        cliente a decidir por su cuenta si significa «no se evaluó», «se
        abstuvo» o «falló», y esas tres respuestas no son intercambiables.
        Aquí se resuelve una vez, en el modelo de LECTURA, para que todos los
        endpoints digan lo mismo.

        Sólo normaliza la ausencia: lo que la etapa escribió pasa tal cual.
        """
        if not self.pose_selection:
            try:
                from services.chemistry.pose_selection import (
                    pose_selection_para_lectura,
                )

                self.pose_selection = pose_selection_para_lectura(self.pose_selection)
            except Exception:                                      # noqa: BLE001
                # Import local y protegido: `core` no depende de `services` en
                # el arranque, y una lectura de resultado NO puede caerse por el
                # sustituto de un campo. Sin él, el cliente ve `null`, que es lo
                # que veía antes de esta etapa.
                self.pose_selection = None
        return self

    @field_validator("target_hotspots", mode="before")
    @classmethod
    def _parse_target_hotspots(cls, v):
        """Normaliza target_hotspots: acepta list[dict] o string JSON (la
        columna JSONB→TEXT de SQLite llega como str)."""
        return _coerce_hotspots(v)

    @field_validator("docking_poses", "scientific_warnings", "hotspots_hit",
                     "sa_reasons", "pains_matches", "blood_systemic_reactivity",
                     "gnn_attention", "anti_target_results", mode="before")
    @classmethod
    def _parse_json_list_fields(cls, v, info):
        """Coacciona campos JSONB→TEXT (list) de SQLite que llegan como str
        simple o doble-serializado. Sin esto, model_validate explota con
        ValidationError y el except en queue_handler lo traga → result=None
        → el frontend muestra el MOCK demo como si fuera real."""
        return _coerce_json_value(v, expect="list")

    @field_validator("shap_values", "gnn_pharmacophores", mode="before")
    @classmethod
    def _parse_json_dict_fields(cls, v, info):
        """Ídem para campos JSONB→TEXT de tipo dict."""
        return _coerce_json_value(v, expect="dict")


def _coerce_hotspots(v):
    """Convierte hotspots desde SQLite (str JSONB→TEXT) a list[dict].

    Reutilizable para asignaciones directas fuera de Pydantic (las
    asignaciones `modelo.campo = ...` NO pasan por validators por defecto,
    así que el valor crudo hay que coaccionarlo antes de guardarlo).
    """
    result = _coerce_json_value(v, expect="list")
    if isinstance(result, list):
        return [h for h in result if isinstance(h, dict)]
    return result


def _coerce_json_value(v, expect: str = "list"):
    """Coacciona un valor JSONB→TEXT de SQLite (str simple o doble-escape)
    a list o dict. Devuelve el valor original si ya es del tipo esperado,
    None si no se puede parsear.

    expect: "list" → list | None | "dict" → dict | None
    """
    if v is None:
        return None
    if expect == "list" and isinstance(v, list):
        return v
    if expect == "dict" and isinstance(v, dict):
        return v
    if isinstance(v, str):
        s = v.strip()
        if s in ("", "null", "[]", "{}"):
            return None if expect == "list" else None
        try:
            import json as _json
            parsed = _json.loads(s)
            # Doble-escape: el string contiene otro string JSON
            if isinstance(parsed, str):
                parsed = _json.loads(parsed)
            if expect == "list" and isinstance(parsed, list):
                return parsed
            if expect == "dict" and isinstance(parsed, dict):
                return parsed
            return None
        except Exception:
            return None
    return None


class ScoreBreakdown(BaseModel):
    """
    Desglose del score para mostrar al usuario en la UI del juego.
    Le permite entender por qué su molécula tiene ese puntaje
    y qué dimensión mejorar en el siguiente intento.
    """
    affinity_score:     float = Field(..., ge=0, le=100)
    adme_score:         float = Field(..., ge=0, le=100)
    druglikeness_score: float = Field(..., ge=0, le=100)
    total_score:        float = Field(..., ge=0, le=100)
    viability_adjusted_score: float | None = Field(None, description="Score ajustado por viabilidad (ADME+Tox+SA). NO usar para ranking cientifico.")
    gnn_score:          float | None = Field(None, description="Score RTMScore GNN (Nivel 2). None si el GNN no está disponible.")
    clgnn_score:        float | None = Field(None, description="Score CL-GNN (contrastive learning). None si no disponible.")
    xgb_score:          float | None = Field(None, description="Probabilidad XGBoost classifier. None si no disponible.")
    mmgbsa_score:       float | None = Field(None, description="MM-GBSA delta G (OpenMM OBC2). None si no disponible.")
    quantum_score:      float | None = Field(None, description="Score cuantico (xTB+MMFF94). None si no disponible.")
    ums_score:          float | None = Field(None, description="Universal Metal Score (SMARTS warheads Zn2+, scorer ortogonal M5 para metaloenzimas). None si no disponible.")
    stacking_vina_weight:  float | None = Field(None, description="Peso de Vina en el stacking por familia.")
    stacking_xgb_weight:   float | None = Field(None, description="Peso del clasificador XGBoost en el stacking por familia.")
    stacking_effective_weights: dict[str, float] | None = None
    stacking_gnn_weight:   float | None = Field(None, description="Peso de la GNN LEGACY (RTMScore, deprecada) en el stacking por familia. NO es el de CL-GNN: hasta v17 se describia asi y el dossier atribuia su valor a CL-GNN.")
    stacking_clgnn_weight: float | None = Field(None, description="Peso de CL-GNN en el stacking por familia. None en corridas anteriores a v17 significa «no registrado por separado», nunca «cero».")
    m5_protocol_id:       str | None = Field(None, description="Perfil M5-Zn resuelto por PDB exacto (M5_ZN_CA2_3DC3_V2 | M5_ZN_MMP9_1GKC_V2 | M5_ZN_ACE_1O86_V2). None si la corrida no es un caso de metal o el PDB no es ninguno de los tres validados.")
    m5_score:             float | None = Field(None, description="Score compuesto M5-Zn. Puede conservarse en estados REVIEW para auditoria; solo VALIDATED habilita una conclusion. Es un score de ranking derivado, no una afinidad.")
    m5_scientific_status: str | None = Field(None, description="Por que el score M5-Zn es lo que es: VALIDATED, NOT_EVALUATED_MISSING_COMPONENT, REVIEW_OUT_OF_VALIDATED_TARGET, REVIEW_OUT_OF_VALIDATED_STRUCTURE, REVIEW_INVALID_BENCHMARK_SITE, REVIEW_BENCHMARK_PROVENANCE_INCOMPLETE, REVIEW_BENCHMARK_TOP1_NOT_METAL_COORDINATING o BLOCKED_PROTOCOL_NOT_AVAILABLE.")
    ums_warhead:          float | None = Field(None, description="UMS SMARTS-only, la senal autorizada de los tres perfiles M5-Zn. NO es ums_score, que es el UMS historico con donantes y MolChamb.")
    stacking_degraded: bool = Field(False, description="[A3] True si el stacking corrió con componentes ausentes (sin fabricar 0.5); los pesos se re-normalizaron sobre los disponibles o cayó a regresión pura de afinidad.")
    degraded_missing: list[str] = Field(default_factory=list, description="[A3] Componentes del stacking ausentes (vina/xgb/gnn/clgnn) que causaron degradación.")
    target_family:       str | None = Field(None, description="Familia estructural del target (gpcr, kinase, protease, etc).")
    specificity_score:  float | None = None
    ligand_efficiency:  float | None = None
    lipophilic_efficiency: float | None = None
    affinity_threshold: float | None = None
    affinity_multiplier: float | None = None
    specificity_multiplier: float | None = None
    gnn_factor: float | None = None
    sa_factor: float | None = None
    blood_factor: float | None = None

    # Pesos usados en el cálculo (para transparencia)
    weight_affinity:     float
    weight_adme:         float
    weight_druglikeness: float

    # Feedback textual para la UI
    strongest_dimension:  str   # ej. "afinidad"
    weakest_dimension:    str   # ej. "ADME"
    improvement_hint:     str   # ej. "Reduce el logP por debajo de 3.5"


class Target(BaseModel):
    """Schema de target biológico para la UI."""
    id:          uuid.UUID
    pdb_id:      str
    name:        str
    chain:       str
    description: str | None
    is_prepared: bool
    requires_cns: bool
    structural_family: str | None
    therapeutic_family: str | None = None
    organism: str | None
    resolution: float | None
    hotspots: list[dict] | None = None
    #: Qué cadenas forman el sitio y con qué evidencia se sabe. `None` en
    #: receptores anteriores al campo o subidos por el usuario: el cliente debe
    #: leerlo como «sin medir», nunca como «una sola cadena».
    site_chains: list[str] | None = None
    site_chain_atoms: dict[str, int] | None = None
    site_evidence: str | None = None
    site_ligand: str | None = None
    #: Procedencia de los hotspots. Ninguno es del RCSB; ver `TargetORM`.
    hotspots_source: str | None = None
    #: Si no es `None`, este receptor salio del catalogo curado y la interfaz
    #: no debe ofrecerlo para evaluar.
    retired_reason: str | None = None
    affinity_threshold: float | None = -7.5
    is_hot: bool = False
    spearman_rho: float | None = None
    calibration_date: datetime | None = None
    grid_center_x: float | None = None
    grid_center_y: float | None = None
    grid_center_z: float | None = None
    grid_size_x: float | None = None
    grid_size_y: float | None = None
    grid_size_z: float | None = None
    cofactors_whitelist: list[str] | None = []
    is_private: bool = False
    #: SC-9. Qué respaldo científico tiene REALMENTE este receptor: calibrado,
    #: con pipeline de familia, sólo curado estructuralmente, o sin curar. Lo
    #: calcula `services/targets/calibracion.py` y viaja con el receptor para
    #: que ninguna superficie tenga que deducirlo. `None` en respuestas
    #: anteriores al campo; el cliente debe leerlo como «sin comprobar», nunca
    #: como «calibrado».
    calibracion: dict[str, Any] | None = None
    is_community: bool = False
    is_anti_target: bool = False
    anti_target_risk: str | None = None
    creator_username: str | None = None
    preparation_parent_id: uuid.UUID | None = None
    receptor_source_sha256: str | None = None
    prepared_receptor_sha256: str | None = None
    preparation_fingerprint: str | None = None
    preparation_recipe: dict | None = None
    preparation_toolchain: dict | None = None

    # ── Campos calculados para la UI (no vienen de la DB directa) ──────────
    # calibration_status: estado de calibración del grid/hotspots que el
    # usuario final entiende: "listo" | "revisar" | "sin_datos".
    calibration_status: str = "sin_datos"
    hotspot_count: int = 0

    @computed_field  # type: ignore[prop-decorator]
    @property
    def grid_calibrated(self) -> bool:
        """True si el grid center no es (0,0,0) — señal de grid razonable."""
        gx = self.grid_center_x or 0
        gy = self.grid_center_y or 0
        gz = self.grid_center_z or 0
        return not (gx == 0 and gy == 0 and gz == 0)

    @field_validator("hotspots", mode="before")
    @classmethod
    def _parse_hotspots(cls, v):
        """Normaliza hotspots: acepta list[dict] o string JSON (la columna
        JSONB→TEXT de SQLite llega como str). Evita 500 en /targets/."""
        if v is None or isinstance(v, list):
            return v
        if isinstance(v, str):
            s = v.strip()
            if s in ("", "null", "[]"):
                return None
            try:
                import json as _json
                parsed = _json.loads(s)
                if isinstance(parsed, list):
                    return [h for h in parsed if isinstance(h, dict)]
                if isinstance(parsed, str):
                    inner = _json.loads(parsed)
                    if isinstance(inner, list):
                        return [h for h in inner if isinstance(h, dict)]
                return None
            except Exception:
                return None
        return v

    @model_validator(mode="after")
    def _compute_calibration(self):
        """Deriva calibration_status y hotspot_count para la UI.

        - "listo": is_prepared + grid no-nulo + (≥5 hotspots O target manual
          con grid explícito). En modo manual (.pdbqt) el usuario ya proveyó
          el grid — el receptor está listo aunque no haya hotspots minados.
        - "revisar": preparado con grid pero hotspots escasos (1-4) — el
          ligando de referencia puede no ser drug-like
        - "sin_datos": sin preparar, grid nulo o sin hotspots
        """
        n_hs = len(self.hotspots) if isinstance(self.hotspots, list) else 0
        self.hotspot_count = n_hs
        grid_ok = self.grid_calibrated
        # Target manual = subido como .pdbqt con grid explícito (USR_*)
        is_manual = bool(self.pdb_id and self.pdb_id.startswith("USR_"))
        if self.is_prepared and grid_ok and (n_hs >= 5 or is_manual):
            self.calibration_status = "listo"
        elif self.is_prepared and grid_ok and n_hs >= 1:
            self.calibration_status = "revisar"
        else:
            self.calibration_status = "sin_datos"
        return self

    model_config = {"from_attributes": True}


class ValidationResult(BaseModel):
    """
    Resultado de la validación química de un SMILES.
    Retornado por el endpoint POST /chem/validate.
    """
    is_valid:         bool
    canonical_smiles: str | None   # SMILES canonicalizado por RDKit
    smiles_hash:      str | None   # SHA-256 del canonical SMILES
    errors:           list[str]    # vacío si is_valid == True
    warnings:         list[str]    # problemas no fatales (ej. valencia inusual pero válida)
    heavy_atom_count: int | None
    molecular_formula: str | None  # ej. "C9H8O4" (aspirina)
    #: Regimen de tamano segun criterios publicados: "ro5" | "bro5" |
    #: "fuera_de_alcance". Ver `chem/regimenes.py`. Decide para que esta
    #: calibrado el resto del pipeline, asi que viaja con el resultado en vez
    #: de recalcularse en cada consumidor.
    regimen: str | None = None
    regimen_etiqueta: str | None = None
    regimen_criterio: str | None = None
    #: Si cumple el corte de masa de la Rule of Three (< 300 Da). Subconjunto
    #: del espacio Ro5, no un regimen aparte.
    cumple_ro3: bool | None = None


class JobStatus(BaseModel):
    """
    Estado de un job asíncrono de docking.
    El frontend hace polling a GET /docking/status/{task_id}.
    """
    task_id:    str
    status:     str   # "PENDING" | "STARTED" | "SUCCESS" | "FAILURE" | "RETRY"
    progress:   int   = Field(default=0, ge=0, le=100)   # 0-100
    result:     EvaluationResultRead | None = None
    error:      str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class AIReportRequest(BaseModel):
    """
    Input del servicio de IA (services/ai/interpreter.py).
    Datos estructurados que Claude convierte en reporte narrativo.
    """
    molecule_smiles:  str
    target_name:      str
    affinity_kcal:    float
    affinity_score:   float
    properties:       PhysicochemicalProperties
    score_breakdown:  ScoreBreakdown
    parent_smiles:    str | None = None   # para comparar con la versión anterior
    mutation_type:    MutationType | None = None
    is_control:       bool = False
    hotspots_hit:     list[str] | None = None
    target_hotspots:  list[dict] | None = None
    delta_a_null:     float | None = None
    #: Cuenta dueña de la evaluación. Sólo se usa para acotar la memoria que se
    #: inyecta en el prompt del reporte: sin ella no se inyecta ninguna, porque
    #: el catálogo de `ai_memory.db` no tenía dimensión de cuenta y el reporte
    #: de una podía compararse con las evaluaciones de otra.
    user_id:          str | None = None

    model_config = {"from_attributes": True}


class BlockchainRecord(BaseModel):
    """Registro que se envía a Solana al certificar una molécula."""
    smiles_hash:  str   = Field(..., min_length=64, max_length=64)
    total_score:  float = Field(..., ge=0, le=100)
    target_pdb_id: str
    user_wallet:  str
    timestamp:    datetime

    @field_validator("smiles_hash")
    @classmethod
    def hash_must_be_hex(cls, v: str) -> str:
        try:
            int(v, 16)
        except ValueError:
            raise ValueError(f"smiles_hash debe ser un string hexadecimal válido, got: {v[:10]}...")
        return v


# ═════════════════════════════════════════════════════════════════════════════
# MOLCHAT — Schemas para el chatbot IA
# ═════════════════════════════════════════════════════════════════════════════


#: MOLCHAT-AUD-01, higiene del §8. Un turno sin tope de tamaño entra al prompt,
#: viaja al proveedor y se persiste en `ai_memory.db`. 32 000 caracteres son
#: ~8 000 tokens: mucho más de lo que cabe en una pregunta real y muy por
#: debajo de lo que agota memoria o disco.
MAX_CHARS_POR_MENSAJE = 32_000
MAX_MENSAJES_POR_TURNO = 200
MAX_CHARS_CONTEXTO_MOLECULA = 64_000


class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(system|user|assistant)$")
    content: str = Field(..., min_length=1, max_length=MAX_CHARS_POR_MENSAJE)


class StartupDetectionResult(BaseModel):
    mode: str = Field(..., description="auto_start | notify_fallback | manual_only")
    reason: str
    working_providers: list[dict] = Field(default_factory=list)
    failed_providers: list[dict] = Field(default_factory=list)
    local_available: bool = True
    auto_start_local: bool = False


class ProviderInfoResponse(BaseModel):
    id: str
    name: str
    description: str
    requires_api_key: bool
    requires_base_url: bool
    default_base_url: str = ""
    default_model: str = ""
    available_models: list[str] = Field(default_factory=list)
    configured: bool = False
    active: bool = False


class TraspasoRequest(BaseModel):
    """Qué se lleva el investigador de la cuenta invitada a la suya.

    Listas explícitas, no un `todo=True`: el traspaso es selectivo porque el
    trabajo es suyo, incluida la decisión de dejar algo atrás. Las listas vacías
    son un caso normal —«todavía no, gracias»—, no un error.
    """

    molecule_ids: list[uuid.UUID] = Field(default_factory=list, max_length=1000)
    cohort_ids: list[uuid.UUID] = Field(default_factory=list, max_length=1000)


class TraspasoResponse(BaseModel):
    """Lo que de verdad pasó. `ya_estaban` hace visible la idempotencia."""

    moleculas_traspasadas: int = 0
    cohortes_traspasadas: int = 0
    corridas_de_cohorte_traspasadas: int = 0
    moleculas_ya_estaban: int = 0
    cohortes_ya_estaban: int = 0


class AIChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(
        ..., min_length=1, max_length=MAX_MENSAJES_POR_TURNO
    )
    provider_id: str | None = Field(None, description="ID del proveedor a usar. Null = usa el activo.")
    stream: bool = Field(default=True, description="Usar SSE streaming")
    molecule_context: dict[str, Any] | None = Field(
        None,
        description="Datos de la molécula actual para contexto automático",
    )
    mode: str = Field(
        default="speed",
        description="Modo de respuesta: 'speed' (rapido, conciso) o 'reasoning' (profundo, detallado)",
        pattern="^(speed|reasoning)$",
    )
    allow_web: bool = Field(
        default=False,
        description=(
            "Modo online: si True, el agente puede usar herramientas web "
            "verificadas (PubChem, ChEMBL, RCSB PDB, UniProt, BindingDB) ademas "
            "de las locales. Si False (default), solo tools offline — el modelo "
            "nunca sale a internet. Override global via env MOLCHAT_ALLOW_WEB=1."
        ),
    )

    @field_validator("molecule_context")
    @classmethod
    def _contexto_acotado(cls, value: dict | None) -> dict | None:
        """El contexto de molécula también entra al prompt, así que también tiene tope."""
        if value is None:
            return value
        import json as _json

        tamano = len(_json.dumps(value, ensure_ascii=False, default=str))
        if tamano > MAX_CHARS_CONTEXTO_MOLECULA:
            raise ValueError(
                f"molecule_context ocupa {tamano} caracteres; el maximo es "
                f"{MAX_CHARS_CONTEXTO_MOLECULA}."
            )
        return value


class AIChatResponse(BaseModel):
    content: str
    provider: str
    conversation_id: str | None = None
    warning: str | None = Field(None, description="Advertencia: ej. proveedor sin saldo, se usó fallback")
    fallback_used: bool = Field(False, description="True si el provider activo falló y se usó fallback")
