"""
db/repository.py

Repositorio async mínimo para el MVP.

Responsabilidades:
- CRUD básico de targets, moléculas y evaluation_results
- deduplicación por smiles_hash + target
- siembra controlada del target fijo del MVP
- persistencia explícita de estados del pipeline
"""

from __future__ import annotations

import uuid
import enum
from datetime import UTC, datetime
from typing import Any
from types import SimpleNamespace

from sqlalchemy import select, func, update, or_, JSON
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from chem.validator import smiles_to_hash
from core.config import get_settings
from core.exceptions import DatabaseQueryError, TargetNotFound
from core.models import (
    DockingResult,
    EvaluationRunORM,
    EvaluationResultORM,
    MoleculeCreate,
    MoleculeORM,
    MoleculeStatus,
    MutationType,
    PhysicochemicalProperties,
    TargetORM,
    UserORM,
)
from utils.logger import get_logger

settings = get_settings()
log = get_logger(__name__)


def _property_values(properties: PhysicochemicalProperties) -> dict[str, Any]:
    """Mapeo único para pipeline y ADMET post-hoc; mismas conversiones."""
    result = SimpleNamespace()
    # Cast all numerics to native Python types
    # FIX (2026-08-04, UI-2 integration): los descriptores int pueden
    # llegar como None si RDKit no pudo calcularlos (átomos exóticos,
    # valencia rara, fallo silencioso). Antes, `int(None)` reventaba el
    # pipeline completo con "int() argument must be ... not 'NoneType'"
    # → evaluación FAILURE sin feedback útil. Guarda None consistente
    # con el resto del método (líneas de drug-likeness/ADMET ya lo
    # tenían). El frontend renderiza estos campos null-safe.
    result.molecular_weight = float(properties.molecular_weight) if properties.molecular_weight is not None else None
    result.log_p = float(properties.log_p) if properties.log_p is not None else None
    result.tpsa = float(properties.tpsa) if properties.tpsa is not None else None
    result.hbd = int(properties.hbd) if properties.hbd is not None else None
    result.hba = int(properties.hba) if properties.hba is not None else None
    result.rotatable_bonds = int(properties.rotatable_bonds) if properties.rotatable_bonds is not None else None
    result.heavy_atom_count = int(properties.heavy_atom_count) if properties.heavy_atom_count is not None else None
    result.ring_count = int(properties.ring_count) if properties.ring_count is not None else None
    result.lipinski_pass = bool(properties.lipinski_pass) if properties.lipinski_pass is not None else None
    result.veber_pass = bool(properties.veber_pass) if properties.veber_pass is not None else None
    result.qed = float(properties.qed) if properties.qed is not None else None
    result.sa_score = float(properties.sa_score) if properties.sa_score is not None else None
    result.sa_reasons = list(properties.sa_reasons) if properties.sa_reasons is not None else []

    # --- Persistir drug-likeness extendido (Ghose/Egan/Muegge/Fsp3/PAINS) ---
    # Valores ya calculados en chem/properties.py (etapa "properties") —
    # antes se descartaban silenciosamente en el save path.
    result.ghose_pass = bool(properties.ghose_pass) if properties.ghose_pass is not None else None
    result.egan_pass = bool(properties.egan_pass) if properties.egan_pass is not None else None
    result.muegge_pass = bool(properties.muegge_pass) if properties.muegge_pass is not None else None
    result.muegge_score = int(properties.muegge_score) if properties.muegge_score is not None else None
    result.fsp3 = float(properties.fsp3) if properties.fsp3 is not None else None
    result.is_pains = bool(properties.is_pains) if properties.is_pains is not None else None
    result.pains_matches = list(properties.pains_matches) if properties.pains_matches is not None else []

    # --- Persistir campos MPO / ADMET ---
    result.blood_viability_score = float(properties.blood_viability_score) if properties.blood_viability_score is not None else None
    result.blood_solubility_logs = float(properties.blood_solubility_logs) if properties.blood_solubility_logs is not None else None
    result.blood_ppb_category = str(properties.blood_ppb_category) if properties.blood_ppb_category is not None else None
    result.blood_bbb_permeable = bool(properties.blood_bbb_permeable) if properties.blood_bbb_permeable is not None else None
    result.blood_bbb_motivo = properties.blood_bbb_motivo
    result.blood_cns_mpo = float(properties.blood_cns_mpo) if properties.blood_cns_mpo is not None else None
    result.blood_hia_permeable = bool(properties.blood_hia_permeable) if properties.blood_hia_permeable is not None else None
    result.blood_systemic_reactivity = list(properties.blood_systemic_reactivity) if properties.blood_systemic_reactivity is not None else []
    result.blood_tabpfn_estado = properties.blood_tabpfn_estado

    return vars(result)


class Repository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_target_by_pdb_id(self, pdb_id: str) -> TargetORM | None:
        stmt = select(TargetORM).where(TargetORM.pdb_id == pdb_id.upper())
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_targets(self) -> list[TargetORM]:
        stmt = select(TargetORM).order_by(TargetORM.created_at.asc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_sar_analogs(
        self,
        target_pdb_id: str,
        user_id: uuid.UUID | None = None,
        limit: int = 50,
    ) -> list[EvaluationResultORM]:
        """Retorna evaluaciones contra el mismo target, ordenadas por score."""
        from core.models import EvaluationResultORM, MoleculeORM, TargetORM
        from sqlalchemy.orm import joinedload

        stmt = (
            select(EvaluationResultORM)
            .join(MoleculeORM, EvaluationResultORM.molecule_id == MoleculeORM.id)
            .join(TargetORM, MoleculeORM.target_id == TargetORM.id)
            .where(TargetORM.pdb_id == target_pdb_id.upper())
            .where(EvaluationResultORM.total_score.isnot(None))
            .options(
                joinedload(EvaluationResultORM.molecule).joinedload(MoleculeORM.target)
            )
            .order_by(EvaluationResultORM.total_score.desc())
            .limit(limit)
        )
        if user_id:
            stmt = stmt.where(MoleculeORM.user_id == user_id)

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_anti_targets(self) -> list[TargetORM]:
        """Retorna todos los targets marcados como anti-targets de seguridad."""
        stmt = select(TargetORM).where(TargetORM.is_anti_target == True)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def ensure_default_target(self) -> TargetORM:
        # 1. Target Base (7E2Y)
        target_7e2y = await self.get_target_by_pdb_id("7E2Y")
        if not target_7e2y:
            target_7e2y = TargetORM(
                pdb_id="7E2Y",
                name="5-HT1A serotonin receptor",
                chain="R",
                description="Target base del MVP científico de MolDesign.",
                grid_center_x=103.03, grid_center_y=114.79, grid_center_z=108.36,
                grid_size_x=25.0, grid_size_y=25.0, grid_size_z=25.0,
                requires_cns=True,
                structural_family="gpcr",
                organism="Homo sapiens",
                resolution=3.0,  # 3.00 Å Cryo-EM (Xu et al. 2021, Cell Research)
                is_prepared=True,
                spearman_rho=0.512,
                hotspots=[
                    {"name": "R:MET97", "importance": 0.8},
                    {"name": "R:ASP116", "importance": 1.0},
                    {"name": "R:VAL117", "importance": 0.7},
                    {"name": "R:SER190", "importance": 0.6},
                    {"name": "R:PHE361", "importance": 0.9}
                ]
            )
            self.db.add(target_7e2y)
            log.info("target 7E2Y creado con hotspots")

        # 2. Hot Target (6B3J) - GLP-1R ECD / Peptide Pocket
        # Estructura: GLP-1R (Cadena R) + Exendin-P5 peptídico (Cadena P)
        # Resolución: 3.3 Å Cryo-EM (Liang et al. 2018, Nature)
        # Bolsillo: Interfaz ECD (dominio extracelular) — ideal para peptidomiméticos
        # Hotspots verificados cristalográficamente: distancia < 5.0 Å al péptido Exendin-P5
        # Grid centrado en el centroide del péptido endógeno (verificado: diff=0.01 Å)
        target_6b3j = await self.get_target_by_pdb_id("6B3J")
        if not target_6b3j:
            target_6b3j = TargetORM(
                pdb_id="6B3J",
                name="GLP-1R (ECD / Peptide Pocket)",
                chain="R",
                description=(
                    "Receptor GLP-1 acoplado a proteína Gs en estado activo con agonista peptídico Exendin-P5 "
                    "(Cadena P). Resolución 3.3 Å Cryo-EM (Liang et al. 2018, Nature). "
                    "Bolsillo del Dominio Extracelular (ECD): indica complementariedad para análogos "
                    "peptídicos, peptidomiméticos y moléculas con anclaje N-terminal. "
                    "Para agonistas orales small-molecule, usar el target GLP-1R TMD (6X1A)."
                ),
                grid_center_x=93.23, grid_center_y=148.16, grid_center_z=103.33,
                grid_size_x=30.0, grid_size_y=30.0, grid_size_z=30.0,
                requires_cns=False,
                structural_family="GPCR",
                organism="Homo sapiens",
                resolution=3.3,
                is_prepared=True,
                is_hot=True,
                spearman_rho=0.485,
                affinity_threshold=-8.0,
                hotspots=[
                    # Verificados cristalográficamente vs Exendin-P5 (Cadena P) en 6B3J
                    # Fuente: distancias átomo-a-átomo calculadas del PDB oficial RCSB
                    {"name": "ARG121", "importance": 1.0},   # 2.34 Å — puente salino/H-bond principal
                    {"name": "GLU138", "importance": 1.0},   # 2.45 Å — anclaje ácido del N-terminal
                    {"name": "ARG299", "importance": 0.9},   # 2.51 Å — estabilización ECD
                    {"name": "TRP306", "importance": 0.8},   # 3.06 Å — pinza hidrofóbica
                    {"name": "TYR69",  "importance": 0.8},   # 3.19 Å — plataforma aromática ECD
                ]
            )
            self.db.add(target_6b3j)
            log.info("target 6B3J (ECD/Peptide pocket) creado con hotspots cristalográficos verificados")

        # 2b. Hot Target (6X1A) - GLP-1R TMD / Oral Agonist Pocket
        # Estructura: GLP-1R (Cadena R) + Danuglipron/UK4 small molecule (Cadena R)
        # Resolución: 2.5 Å Cryo-EM (Song et al. 2020, Cell) — mejor resolución disponible
        # Bolsillo: Dominio Transmembranal (TMD) — el sitio de unión de agonistas orales
        # Hotspots verificados: distancia átomo-a-átomo < 4.5 Å al ligando UK4 (Danuglipron)
        # Grid centrado en centroide de UK4 (verificado: diff=0.0000 Å vs PDB RCSB)
        target_6x1a = await self.get_target_by_pdb_id("6X1A")
        if not target_6x1a:
            target_6x1a = TargetORM(
                pdb_id="6X1A",
                name="GLP-1R (TMD / Oral Agonist Pocket)",
                chain="R",
                description=(
                    "Receptor GLP-1 en estado activo unido al agonista oral no peptídico Danuglipron "
                    "(PF-06882961, Pfizer; ligando UK4, Cadena R). Resolución 2.5 Å Cryo-EM "
                    "(Song et al. 2020, Cell). Bolsillo del Dominio Transmembranal (TMD): "
                    "TM1/TM2/TM3/TM7. Target primario para virtual screening de fármacos orales. "
                    "TRP33 es primate-específico y crítico para selectividad de especie."
                ),
                grid_center_x=131.35, grid_center_y=116.78, grid_center_z=155.04,
                grid_size_x=30.0, grid_size_y=30.0, grid_size_z=30.0,
                requires_cns=False,
                structural_family="GPCR",
                organism="Homo sapiens",
                resolution=2.5,
                is_prepared=True,
                is_hot=True,
                spearman_rho=0.0,  # Pendiente de benchmark con nuevo setup
                affinity_threshold=-7.5,
                hotspots=[
                    # Verificados cristalográficamente vs UK4 (Danuglipron) en 6X1A
                    # Fuente: distancias átomo-a-átomo calculadas del PDB oficial RCSB
                    {"name": "LYS197", "importance": 1.0},   # 3.08 Å — polar anchor, más próximo
                    {"name": "TRP203", "importance": 1.0},   # 3.31 Å — π-stacking benzimidazol
                    {"name": "ARG380", "importance": 0.9},   # 3.34 Å — H-bond con carboxilato
                    {"name": "TRP33",  "importance": 0.9},   # 3.57 Å — π-stacking, primate-específico
                    {"name": "THR298", "importance": 0.8},   # 3.54 Å — red H-bond TM5
                    {"name": "LEU141", "importance": 0.7},   # 3.61 Å — cierre hidrofóbico del bolsillo
                ]
            )
            self.db.add(target_6x1a)
            log.info("target 6X1A (TMD/Oral pocket) creado con hotspots cristalográficos verificados")

        # 3. PCSK9 Target (2P4E)
        target_2p4e = await self.get_target_by_pdb_id("2P4E")
        if not target_2p4e:
            target_2p4e = TargetORM(
                pdb_id="2P4E",
                name="PCSK9 (Proprotein Convertase)",
                chain="A",
                description="Inhibición de la interacción PCSK9-LDLR para hipercolesterolemia.",
                grid_center_x=-14.6, grid_center_y=24.5, grid_center_z=-45.7,
                grid_size_x=22.0, grid_size_y=22.0, grid_size_z=22.0,
                requires_cns=False,
                structural_family="hydrolase",
                organism="Homo sapiens",
                resolution=1.97,
                is_prepared=True,
                spearman_rho=0.0, # Pendiente de validación sistemática
                hotspots=[
                    {"name": "GLY292", "importance": 1.0},
                    {"name": "TYR293", "importance": 1.0},
                    {"name": "SER294", "importance": 1.0}
                ]
            )
            self.db.add(target_2p4e)
            log.info("target 2P4E (PCSK9) creado con hotspots")

        # 3b. PCSK9 Allosteric (6U26)
        target_6u26 = await self.get_target_by_pdb_id("6U26")
        if not target_6u26:
            target_6u26 = TargetORM(
                pdb_id="6U26",
                name="PCSK9 (Allosteric)",
                chain="A",
                description="Bolsillo de unión alostérico para inhibidores de pequeña molécula.",
                grid_center_x=10.1, grid_center_y=15.2, grid_center_z=-5.3,
                grid_size_x=20.0, grid_size_y=20.0, grid_size_z=20.0,
                requires_cns=False,
                structural_family="Serine Protease",
                organism="Homo sapiens",
                resolution=1.60,
                is_prepared=True,
                spearman_rho=0.0,
                affinity_threshold=-7.5,
                hotspots=[
                    {"name": "ASP186", "importance": 1.0},
                    {"name": "PHE187", "importance": 1.0},
                    {"name": "ASP367", "importance": 0.9}
                ]
            )
            self.db.add(target_6u26)
            log.info("target 6U26 (PCSK9 Allosteric) creado con hotspots")

        # 3c. CTLA-4 Immune Checkpoint (3OSK)
        target_3osk = await self.get_target_by_pdb_id("3OSK")
        if not target_3osk:
            target_3osk = TargetORM(
                pdb_id="3OSK",
                name="CTLA-4 Immune Checkpoint",
                chain="A",
                description="Receptor inmunitario (Checkpoint). Sitio de unión B7 (Loop MYPPPY).",
                grid_center_x=-2.132, grid_center_y=-19.592, grid_center_z=22.149,
                grid_size_x=25.0, grid_size_y=25.0, grid_size_z=25.0,
                requires_cns=False,
                structural_family="checkpoint",
                organism="Homo sapiens",
                resolution=2.5,
                is_prepared=True,
                spearman_rho=0.0,
                affinity_threshold=-7.0,
                hotspots=[
                    {"name": "MET99", "importance": 1.0},
                    {"name": "TYR100", "importance": 1.0},
                    {"name": "PRO101", "importance": 1.0},
                    {"name": "PRO102", "importance": 1.0},
                    {"name": "PRO103", "importance": 1.0},
                    {"name": "TYR104", "importance": 1.0}
                ]
            )
            self.db.add(target_3osk)
            log.info("target 3OSK (CTLA-4) creado con hotspots")

        # --- Targets de Cáncer de Mama (Oncológicos) ---
        breast_cancer_targets = [
            {
                "pdb_id": "3ERT",
                "name": "ER-alpha LBD (Tamoxifen)",
                "chain": "A",
                "description": "Receptor de estrogeno alfa humano (LBD) co-cristalizado con el modulador selectivo 4-Hidroxitamoxifeno (OHT). Diana principal en terapia endocrina de cancer de mama ER+.",
                "grid_center_x": 31.57, "grid_center_y": -1.59, "grid_center_z": 25.60,
                "requires_cns": False, "structural_family": "Nuclear Receptor",
                "organism": "Homo sapiens", "resolution": 1.9, "affinity_threshold": -7.5,
                "hotspots": [
                    {"name": "GLU353", "importance": 1.0},
                    {"name": "ARG394", "importance": 0.85},
                    {"name": "ASP351", "importance": 0.8},
                    {"name": "ALA350", "importance": 0.78},
                    {"name": "MET421", "importance": 0.72}
                ]
            },
            {
                "pdb_id": "5L2I",
                "name": "CDK6 (Palbociclib)",
                "chain": "A",
                "description": "Ciclina dependiente de quinasa 6 (CDK6) humana unida al inhibidor selectivo de quinasa Palbociclib (Ibrance). Control del ciclo celular G1/S en tumores ER+.",
                "grid_center_x": 13.98, "grid_center_y": 28.18, "grid_center_z": 9.65,
                "requires_cns": False, "structural_family": "Kinase",
                "organism": "Homo sapiens", "resolution": 2.75, "affinity_threshold": -7.5,
                "hotspots": [
                    {"name": "VAL101", "importance": 1.0},
                    {"name": "GLU99", "importance": 0.9},
                    {"name": "VAL27", "importance": 0.88},
                    {"name": "GLN149", "importance": 0.86},
                    {"name": "LEU152", "importance": 0.85}
                ]
            },
            {
                "pdb_id": "2W96",
                "name": "CDK4 (Apo/Cyclin D1)",
                "chain": "B",
                "description": "Ciclina dependiente de quinasa 4 (CDK4) humana en complejo activo con Ciclina D1. Bolsillo ATP alineado estructuralmente con Palbociclib para cribado selectivo.",
                "grid_center_x": 7.41, "grid_center_y": 2.10, "grid_center_z": 81.55,
                "requires_cns": False, "structural_family": "Kinase",
                "organism": "Homo sapiens", "resolution": 2.3, "affinity_threshold": -7.5,
                "hotspots": [
                    {"name": "LYS35", "importance": 1.0},
                    {"name": "VAL96", "importance": 0.91},
                    {"name": "ASP158", "importance": 0.91},
                    {"name": "ILE12", "importance": 0.84},
                    {"name": "GLU144", "importance": 0.79}
                ]
            },
            {
                "pdb_id": "4JPS",
                "name": "PIK3CA WT (Alpelisib)",
                "chain": "A",
                "description": "Subunidad catalitica p110alfa de fosfatidilinositol 3-quinasa (PI3K) salvaje en complejo con el inhibidor BYL719 (Alpelisib) indicado para resistencia endocrina.",
                "grid_center_x": -1.32, "grid_center_y": -9.51, "grid_center_z": 16.95,
                "requires_cns": False, "structural_family": "Kinase",
                "organism": "Homo sapiens", "resolution": 2.2, "affinity_threshold": -7.5,
                "hotspots": [
                    {"name": "SER854", "importance": 1.0},
                    {"name": "GLN859", "importance": 0.96},
                    {"name": "VAL851", "importance": 0.93},
                    {"name": "LYS802", "importance": 0.87},
                    {"name": "ILE800", "importance": 0.85}
                ]
            },
            {
                "pdb_id": "3O96",
                "name": "AKT1 (Allosteric Inhibitor VIII)",
                "chain": "A",
                "description": "RAC-alfa serina/treonina-proteina quinasa 1 (AKT1) en estado inactivo con inhibidor alosterico VIII. Bloqueo de la señalizacion aguas abajo de PI3K.",
                "grid_center_x": 8.37, "grid_center_y": -6.83, "grid_center_z": 12.62,
                "requires_cns": False, "structural_family": "Kinase",
                "organism": "Homo sapiens", "resolution": 2.7, "affinity_threshold": -7.5,
                "hotspots": [
                    {"name": "SER205", "importance": 1.0},
                    {"name": "ASP292", "importance": 0.94},
                    {"name": "TYR272", "importance": 0.92},
                    {"name": "CYS296", "importance": 0.91},
                    {"name": "LYS268", "importance": 0.87}
                ]
            },
            {
                "pdb_id": "3PP0",
                "name": "HER2 Kinase Domain (SYR-475)",
                "chain": "A",
                "description": "Dominio quinasa de la tirosina-proteina quinasa erbB-2 (HER2/Neu) en complejo con el inhibidor pirrolopirimidinico selectivo SYR-475.",
                "grid_center_x": 17.10, "grid_center_y": 16.55, "grid_center_z": 26.60,
                "requires_cns": False, "structural_family": "Kinase",
                "organism": "Homo sapiens", "resolution": 2.25, "affinity_threshold": -7.5,
                "hotspots": [
                    {"name": "MET801", "importance": 1.0},
                    {"name": "ASP863", "importance": 0.96},
                    {"name": "ASN850", "importance": 0.93},
                    {"name": "ALA751", "importance": 0.93},
                    {"name": "LEU796", "importance": 0.90}
                ]
            },
            {
                "pdb_id": "4ZZZ",
                "name": "PARP1 LBD (NMS-P118)",
                "chain": "A",
                "description": "Dominio catalitico de Poli(ADP-ribosa) polimerasa 1 (PARP1) unida al inhibidor de isoindolinona NMS-P118. Letalidad sintetica en tumores con mutacion BRCA.",
                "grid_center_x": 63.41, "grid_center_y": 6.48, "grid_center_z": 9.59,
                "requires_cns": False, "structural_family": "Polymerase",
                "organism": "Homo sapiens", "resolution": 1.9, "affinity_threshold": -7.5,
                "hotspots": [
                    {"name": "SER904", "importance": 1.0},
                    {"name": "GLY863", "importance": 0.99},
                    {"name": "HIS862", "importance": 0.84},
                    {"name": "TYR907", "importance": 0.80},
                    {"name": "PHE897", "importance": 0.76}
                ]
            },
            {
                "pdb_id": "1HVY",
                "name": "Thymidylate Synthase (Raltitrexed)",
                "chain": "A",
                "description": "Timidilato sintasa humana (dímero catalítico, Cadena A) en complejo cerrado con el analogo de folato Raltitrexed (D16) y dUMP. Blanco quimioterapeutico clasico.",
                "grid_center_x": 0.40, "grid_center_y": 12.39, "grid_center_z": 17.77,
                "requires_cns": False, "structural_family": "Transferase",
                "organism": "Homo sapiens", "resolution": 1.9, "affinity_threshold": -7.5,
                "hotspots": [
                    {"name": "ASP218", "importance": 1.0},
                    {"name": "GLY222", "importance": 0.89},
                    {"name": "GLU87", "importance": 0.78},
                    {"name": "MET311", "importance": 0.78},
                    {"name": "TRP109", "importance": 0.77}
                ]
            }
        ]

        for target_data in breast_cancer_targets:
            existing = await self.get_target_by_pdb_id(target_data["pdb_id"])
            if not existing:
                t = TargetORM(
                    pdb_id=target_data["pdb_id"],
                    name=target_data["name"],
                    chain=target_data["chain"],
                    description=target_data["description"],
                    grid_center_x=target_data["grid_center_x"],
                    grid_center_y=target_data["grid_center_y"],
                    grid_center_z=target_data["grid_center_z"],
                    grid_size_x=25.0,
                    grid_size_y=25.0,
                    grid_size_z=25.0,
                    requires_cns=target_data["requires_cns"],
                    structural_family=target_data["structural_family"],
                    organism=target_data["organism"],
                    resolution=target_data["resolution"],
                    is_prepared=True,
                    spearman_rho=0.0,
                    affinity_threshold=target_data["affinity_threshold"],
                    hotspots=target_data["hotspots"]
                )
                self.db.add(t)
                log.info(f"target {t.pdb_id} ({t.name}) onco-mama creado")

        await self.db.flush()
        return target_6x1a or target_6b3j or target_7e2y

    async def get_or_create_test_user(self) -> UserORM:
        stmt = select(UserORM).where(UserORM.username == "demo")
        result = await self.db.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing is not None:
            return existing

        import secrets

        from api.routers.auth import _hash_password

        # MOLDEX-BE-015: esta cuenta se creaba con la contraseña `demo123`
        # escrita aquí y `is_active=True`. Como `/auth/login` acepta username o
        # email, cualquiera que alcanzara la API entraba como demo y veía todo
        # lo que el espacio demo poseyera. Es una identidad de servicio, no una
        # cuenta de persona: no debe poder autenticarse.
        #
        # El invitado real del escritorio es otro —`Desktop User`, creado por
        # `/auth/desktop-login` con contraseña aleatoria—, así que nadie
        # necesita iniciar sesión como demo. Misma técnica que allí.
        user = UserORM(
            email="demo@moldesign.local",
            username="demo",
            hashed_password=_hash_password(secrets.token_hex(32)),
            is_active=True,
        )
        self.db.add(user)
        from core.database import flush_with_retry
        await flush_with_retry(self.db)
        log.info("usuario demo creado para flujo MVP", user_id=str(user.id))
        return user

    async def create_molecule(
        self,
        data: MoleculeCreate,
        user_id: uuid.UUID,
    ) -> MoleculeORM:
        target = await self.get_target_by_pdb_id(data.target_pdb_id)
        if target is None:
            raise TargetNotFound(data.target_pdb_id)

        molecule = MoleculeORM(
            smiles=data.smiles,
            name=data.name,
            status=MoleculeStatus.PENDING,
            mutation_type=data.mutation_type,
            parent_id=data.parent_id,
            user_id=user_id,
            target_id=target.id,
            smiles_hash=smiles_to_hash(data.smiles),
        )
        self.db.add(molecule)
        from core.database import flush_with_retry
        await flush_with_retry(self.db)
        log.info("molécula creada", molecule_id=str(molecule.id), target=target.pdb_id)
        return molecule

    async def get_molecule(self, molecule_id: uuid.UUID) -> MoleculeORM | None:
        stmt = (
            select(MoleculeORM)
            .options(
                selectinload(MoleculeORM.target),
                selectinload(MoleculeORM.evaluation_result),
            )
            .where(MoleculeORM.id == molecule_id)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_molecules_by_status(
        self,
        status_value: MoleculeStatus,
        limit: int = 500,
    ) -> list[MoleculeORM]:
        """Lista moléculas en un estado dado (p. ej. 'pending' huérfanas)."""
        stmt = (
            select(MoleculeORM)
            .where(MoleculeORM.status == status_value)
            .order_by(MoleculeORM.created_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_molecule_by_hash(
        self,
        smiles_hash: str,
        target_id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
    ) -> MoleculeORM | None:
        stmt = select(MoleculeORM).where(MoleculeORM.smiles_hash == smiles_hash)
        if target_id is not None:
            stmt = stmt.where(MoleculeORM.target_id == target_id)
        if user_id is not None:
            stmt = stmt.where(MoleculeORM.user_id == user_id)

        stmt = stmt.order_by(MoleculeORM.created_at.desc())
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def create_or_get_molecule(
        self,
        smiles: str,
        target_pdb_id: str | None = None,
        name: str | None = None,
        user_id: uuid.UUID | None = None,
        parent_id: uuid.UUID | None = None,
        mutation_type: MutationType | None = None,
    ) -> MoleculeORM:
        requested_pdb_id = (target_pdb_id or settings.default_target_pdb_id).strip().upper()
        target = await self.get_target_by_pdb_id(requested_pdb_id)
        if target is None:
            # EVAL-SCI-001. Sembrar el receptor base cuando ES el receptor base
            # lo pedido mantiene viva la primera corrida de una instalación
            # nueva. Aceptar cualquier otro id y archivar la molécula contra
            # 7E2Y escribía una procedencia falsa en la fila que después leen
            # el historial, el MolDex, el informe y el dossier.
            if requested_pdb_id != settings.default_target_pdb_id.strip().upper():
                from services.targets.resolution import TargetUnavailableError

                raise TargetUnavailableError(
                    f"No existe el receptor {requested_pdb_id} en el catálogo local: "
                    "la molécula no puede registrarse contra otro receptor."
                )
            target = await self.ensure_default_target()

        if user_id is None:
            user = await self.get_or_create_test_user()
            user_id = user.id

        smiles_hash = smiles_to_hash(smiles)
        # La deduplicación es por investigador, receptor y ligando. Compartir
        # una fila entre cuentas permitiría que una corrida sobrescribiera el
        # resultado de otra aunque la API luego ocultara la corrida ajena.
        existing = await self.get_molecule_by_hash(
            smiles_hash, target.id, user_id=user_id
        )
        if existing is not None:
            return existing

        molecule = MoleculeORM(
            smiles=smiles,
            name=name,
            status=MoleculeStatus.PENDING,
            mutation_type=mutation_type,
            parent_id=parent_id,
            user_id=user_id,
            target_id=target.id,
            smiles_hash=smiles_hash,
        )
        self.db.add(molecule)
        from core.database import flush_with_retry
        await flush_with_retry(self.db)
        return molecule

    async def set_molecule_status(
        self,
        molecule_id: uuid.UUID,
        status_value: MoleculeStatus,
    ) -> MoleculeORM:
        molecule = await self.get_molecule(molecule_id)
        if molecule is None:
            raise DatabaseQueryError(f"Molecule '{molecule_id}' no encontrada")

        molecule.status = status_value
        molecule.updated_at = datetime.now(UTC)
        from core.database import flush_with_retry
        await flush_with_retry(self.db)
        return molecule

    async def get_moldex_molecules(
        self,
        user_id: uuid.UUID,
        target_pdb_id: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> tuple[list[EvaluationResultORM], int]:
        """
        Obtiene las moléculas evaluadas y guardadas para la Pokedex (Moldex).

        Soporta paginación opcional:
          * limit:  número máximo de items a devolver (None = sin límite, all).
          * offset: índice a partir del cual empezar (default 0).
        Devuelve (results, total) donde total es el count SIN paginar
        (útil para construir `has_next` en el endpoint).
        """
        # ─── Base filters (sin paginación) ───
        base_filter = [
            MoleculeORM.user_id == user_id,
            MoleculeORM.status == MoleculeStatus.EVALUATED,
            MoleculeORM.is_saved == True,
        ]
        if target_pdb_id:
            base_filter.append(TargetORM.pdb_id == target_pdb_id.upper())

        # ─── Count total antes de paginar ───
        count_stmt = (
            select(func.count(MoleculeORM.id))
            .join(TargetORM, MoleculeORM.target_id == TargetORM.id)
            .where(*base_filter)
        )
        total = (await self.db.execute(count_stmt)).scalar() or 0

        # ─── Query principal con joinedload + orden ───
        stmt = (
            select(EvaluationResultORM)
            .join(MoleculeORM, EvaluationResultORM.molecule_id == MoleculeORM.id)
            .join(TargetORM, MoleculeORM.target_id == TargetORM.id)
            .where(*base_filter)
            .options(
                joinedload(EvaluationResultORM.molecule).joinedload(MoleculeORM.target)
            )
            .order_by(TargetORM.name.asc(), EvaluationResultORM.total_score.desc())
        )

        if limit is not None:
            stmt = stmt.limit(limit).offset(offset)

        result = await self.db.execute(stmt)
        rows = list(result.unique().scalars().all())
        return rows, total

    async def get_evaluation_result(
        self,
        molecule_id: uuid.UUID,
    ) -> EvaluationResultORM | None:
        stmt = (
            select(EvaluationResultORM)
            .join(MoleculeORM, EvaluationResultORM.molecule_id == MoleculeORM.id)
            .join(TargetORM, MoleculeORM.target_id == TargetORM.id)
            .where(EvaluationResultORM.molecule_id == molecule_id)
            .options(joinedload(EvaluationResultORM.molecule).joinedload(MoleculeORM.target))
        )
        result = await self.db.execute(stmt)
        return result.unique().scalar_one_or_none()

    async def get_evaluation_run(
        self, task_id: str, molecule_id: uuid.UUID | None = None
    ) -> EvaluationRunORM | None:
        filtros = [EvaluationRunORM.task_id == str(task_id)]
        if molecule_id is not None:
            filtros.append(EvaluationRunORM.molecule_id == molecule_id)
        result = await self.db.execute(select(EvaluationRunORM).where(*filtros))
        return result.scalar_one_or_none()

    async def snapshot_evaluation_run(
        self, molecule_id: uuid.UUID, task_id: str
    ) -> EvaluationRunORM:
        """Congela una corrida una sola vez; un retry con igual ID es idempotente."""
        existente = await self.get_evaluation_run(task_id, molecule_id)
        if existente is not None:
            return existente
        resultado = await self.get_evaluation_result(molecule_id)
        if resultado is None:
            raise ValueError("No hay resultado que congelar para esta corrida.")

        def json_seguro(valor):
            if isinstance(valor, uuid.UUID):
                return str(valor)
            if isinstance(valor, datetime):
                return valor.isoformat()
            if isinstance(valor, enum.Enum):
                return valor.value
            if isinstance(valor, dict):
                return {str(k): json_seguro(v) for k, v in valor.items()}
            if isinstance(valor, (list, tuple)):
                return [json_seguro(v) for v in valor]
            return valor

        snapshot = {
            columna.name: json_seguro(getattr(resultado, columna.name))
            for columna in EvaluationResultORM.__table__.columns
        }
        corrida = EvaluationRunORM(
            task_id=str(task_id),
            molecule_id=molecule_id,
            projected_result_id=resultado.id,
            snapshot_json=snapshot,
            status="SUCCESS",
            error_message=None,
        )
        self.db.add(corrida)
        await self.db.flush()
        return corrida

    async def mark_evaluation_run_failed(self, task_id: str, reason: str) -> bool:
        """Corrige el terminal sin alterar el snapshot cientifico congelado."""
        corrida = await self.get_evaluation_run(task_id)
        if corrida is None:
            return False
        corrida.status = "FAILURE"
        corrida.error_message = str(reason)
        await self.db.flush()
        return True

    async def update_evaluation_for_task(self, molecule_id, task_id, **values) -> bool:
        """Actualiza sólo si la proyección todavía pertenece a la corrida."""
        statement = update(EvaluationResultORM).where(
            EvaluationResultORM.molecule_id == molecule_id,
            EvaluationResultORM.task_id == task_id,
        ).values(**values).execution_options(synchronize_session=False)
        outcome = await self.db.execute(statement)
        return outcome.rowcount == 1

    async def update_properties_for_task(self, molecule_id, task_id, properties) -> bool:
        return await self.update_evaluation_for_task(
            molecule_id, task_id, **_property_values(properties))

    async def merge_selectivity_for_task(self, molecule_id, task_id, entries, **values):
        """Fusiona anti-dianas con CAS: ni otra corrida ni otro escritor se pierden.

        Devuelve la lista guardada o None si cambió la corrida/agotó los intentos.
        El caller confirma la transacción; un fallo no se declara persistido.
        """
        table = EvaluationResultORM
        for _ in range(5):
            row = (await self.db.execute(select(table.anti_target_results).where(
                table.molecule_id == molecule_id, table.task_id == task_id,
            ))).first()
            if row is None:
                return None
            previous = row[0]
            merged = {entry["pdb_id"]: entry for entry in (previous or [])
                      if isinstance(entry, dict) and entry.get("pdb_id")}
            for entry in entries:
                if isinstance(entry, dict) and entry.get("pdb_id"):
                    merged[entry["pdb_id"]] = entry
            expected = (or_(table.anti_target_results.is_(None), table.anti_target_results == JSON.NULL)
                        if previous is None else table.anti_target_results == previous)
            result = await self.db.execute(update(table).where(
                table.molecule_id == molecule_id, table.task_id == task_id, expected,
            ).values(anti_target_results=list(merged.values()), **values)
              .execution_options(synchronize_session=False))
            if result.rowcount == 1:
                return list(merged.values())
        return None

    async def set_selectivity_results(
        self,
        molecule_id: uuid.UUID,
        selectivity_ratio: float | None,
        selectivity_ran: bool,
        selectivity_verdict: str,
        anti_target_results: list[dict] | None,
    ) -> None:
        """
        v1.7.3: Persiste los resultados del panel de selectividad sobre la
        evaluation de una molécula. Cero accesos a atributos lazy del ORM —
        el runner pasa los datos ya serializados (PipelineParams snapshot).
        """
        result = await self.get_evaluation_result(molecule_id)
        if result is None:
            log.warning(
                "selectivity_result_skipped",
                molecule_id=str(molecule_id),
                reason="no_evaluation_result",
            )
            return

        result.selectivity_ratio = selectivity_ratio
        result.selectivity_ran = selectivity_ran
        result.selectivity_verdict = selectivity_verdict
        result.anti_target_results = anti_target_results or []
        from core.database import flush_with_retry
        await flush_with_retry(self.db)

    async def upsert_evaluation_result(
        self,
        molecule_id: uuid.UUID,
        properties: PhysicochemicalProperties | None = None,
        docking: DockingResult | None = None,
        scores: dict[str, Any] | None = None,
        ai_report: str | None = None,
        is_control: bool = False,
        error_message: str | None = None,
        task_id: str | None = None,
        structural_evidence: dict[str, Any] | None = None,
        pose_selection: dict[str, Any] | None = None,
        docking_protocol: dict[str, Any] | None = None,
        ligand_state: dict[str, Any] | None = None,
    ) -> EvaluationResultORM:
        result = await self.get_evaluation_result(molecule_id)
        if result is None:
            result = EvaluationResultORM(molecule_id=molecule_id)
            self.db.add(result)

        result.is_control = is_control

        # Sólo se escribe si llega algo. El upsert se llama varias veces por
        # evaluación —propiedades, luego docking— y un `None` intermedio no
        # puede borrar la evidencia que ya se calculó. Es también lo que hace
        # idempotente un reintento: recalcular y volver a escribir el mismo
        # contrato deja el registro igual, sin duplicar nada.
        if structural_evidence is not None:
            result.structural_evidence = structural_evidence

        # Misma regla que arriba: un `None` intermedio no borra lo ya calculado,
        # y recalcular escribe el mismo contrato sin duplicar nada.
        if pose_selection is not None:
            result.pose_selection = pose_selection

        # Misma regla: un `None` intermedio no borra lo ya escrito.
        if docking_protocol is not None:
            result.docking_protocol = docking_protocol

        # Qué se le hizo al SMILES antes de acoplarlo. Misma regla de upsert.
        if ligand_state is not None:
            result.ligand_state = ligand_state

        if properties is not None:
            for name, value in _property_values(properties).items():
                setattr(result, name, value)

        if docking is not None:
            # Ensure all numerics in DockingResult are native types
            result.affinity_kcal = float(docking.best_affinity)
            # For poses, cast all numerics in each pose
            def cast_pose(p):
                return {
                    "rank": int(p.rank),
                    "affinity": float(p.affinity),
                    "rmsd_lb": float(p.rmsd_lb),
                    "rmsd_ub": float(p.rmsd_ub),
                    "pdbqt_block": getattr(p, "pdbqt_block", None),
                    "conformer_index": getattr(p, "conformer_index", None),
                }
            result.docking_poses = [cast_pose(pose) for pose in docking.poses]
            # Only allow output SDF from docking as poses_file_path
            if hasattr(docking, 'poses_file_path') and docking.poses_file_path and docking.poses_file_path.endswith('.sdf'):
                result.poses_file_path = str(docking.poses_file_path)
            else:
                result.poses_file_path = None
            result.parsing_source = str(docking.parsing_source) if docking.parsing_source is not None else None
            result.vina_version = str(docking.vina_version) if docking.vina_version is not None else None
            result.vina_random_seed = int(docking.vina_random_seed) if docking.vina_random_seed is not None else None
            result.receptor_path = getattr(docking, "receptor_path", None)
            result.receptor_sha256 = getattr(docking, "receptor_sha256", None)
            result.scientific_warnings = list(docking.scientific_warnings) if docking.scientific_warnings is not None else []
            result.hotspots_hit = list(docking.hotspots_hit) if hasattr(docking, "hotspots_hit") and docking.hotspots_hit is not None else []

        if scores is not None:
            # Cast all scores to native float
            def safe_float(val):
                try:
                    return float(val) if val is not None else None
                except Exception:
                    return None
            result.affinity_score = safe_float(scores.get("affinity_score"))
            result.adme_score = safe_float(scores.get("adme_score"))
            result.druglikeness_score = safe_float(scores.get("druglikeness_score"))
            result.total_score = safe_float(scores.get("total_score"))
            result.gnn_score = safe_float(scores.get("gnn_score"))  # RTMScore GNN (Nivel 2)
            result.specificity_score = safe_float(scores.get("specificity_score"))
            result.ligand_efficiency = safe_float(scores.get("ligand_efficiency"))
            result.ligand_lipophilicity_efficiency = safe_float(scores.get("lipophilic_efficiency"))
            result.affinity_threshold = safe_float(scores.get("affinity_threshold"))
            result.affinity_multiplier = safe_float(scores.get("affinity_multiplier"))
            result.specificity_multiplier = safe_float(scores.get("specificity_multiplier"))
            result.gnn_factor = safe_float(scores.get("gnn_factor"))
            result.sa_factor = safe_float(scores.get("sa_factor"))
            result.blood_factor = safe_float(scores.get("blood_factor"))
            # ML Scores (Nivel 3 — antes se perdian silenciosamente)
            #
            # `ml_pki` es la REGRESION de XGBoost. Hasta el 2026-09-04 no tenia
            # columna: se convertia a kcal/mol y se escribia sobre
            # `affinity_kcal`, borrando el score de Vina. Ahora conviven, y el
            # unico que escribe `affinity_kcal` es el bloque de `docking`.
            result.ml_pki = safe_float(scores.get("ml_pki"))
            _aplicada = scores.get("ml_pki_aplicada")
            result.ml_pki_aplicada = bool(_aplicada) if _aplicada is not None else None
            result.xgb_score = safe_float(scores.get("xgb_score"))
            result.clgnn_score = safe_float(scores.get("clgnn_score"))
            result.quantum_score = safe_float(scores.get("quantum_score"))
            result.ums_score = safe_float(scores.get("ums_score"))
            result.mmgbsa_score = safe_float(scores.get("mmgbsa_score"))
            result.stacking_vina_weight = safe_float(scores.get("stacking_vina_weight"))
            result.stacking_xgb_weight = safe_float(scores.get("stacking_xgb_weight"))
            result.stacking_gnn_weight = safe_float(scores.get("stacking_gnn_weight"))
            result.stacking_clgnn_weight = safe_float(scores.get("stacking_clgnn_weight"))
            result.stacking_effective_weights = (
                dict(scores["stacking_effective_weights"])
                if scores.get("stacking_effective_weights") is not None else None
            )
            result.stacking_degraded = bool(scores["stacking_degraded"]) if scores.get("stacking_degraded") is not None else None
            result.stacking_missing_components = list(scores["degraded_missing"]) if scores.get("degraded_missing") is not None else None
            # M5-Zn. `None` en las cuatro = el protocolo no se ejecuto en esta
            # corrida; jamas un score de cero. Ver services/pipeline/protocols/m5.
            result.m5_protocol_id = (
                str(scores["m5_protocol_id"]) if scores.get("m5_protocol_id") else None
            )
            result.m5_score = safe_float(scores.get("m5_score"))
            result.m5_scientific_status = (
                str(scores["m5_scientific_status"])
                if scores.get("m5_scientific_status") else None
            )
            result.m5_missing_components = (
                list(scores["m5_missing_components"])
                if scores.get("m5_missing_components") is not None else None
            )
            result.ums_warhead = safe_float(scores.get("ums_warhead"))
            result.target_family = str(scores["target_family"]) if scores.get("target_family") else None

            # F-21: transparencia del modelo usado. engine_used no se produce en
            # el pipeline de evaluación (model_manager no usa el router gpu/cpu)
            # → None; evaluaciones viejas en caché también quedan None.
            result.engine_used = str(scores.get("engine_used")) if scores.get("engine_used") else None
            result.fallback_reason = str(scores.get("fallback_reason")) if scores.get("fallback_reason") else None
            result.in_applicability_domain = bool(scores.get("in_applicability_domain")) if scores.get("in_applicability_domain") is not None else None
            result.model_used = str(scores.get("model_used")) if scores.get("model_used") else None

            # XAI
            if "shap_values" in scores:
                result.shap_values = scores["shap_values"]
            if "gnn_attention" in scores:
                result.gnn_attention = scores["gnn_attention"]
            if "gnn_attention_svg" in scores:
                result.gnn_attention_svg = scores["gnn_attention_svg"]
            if "gnn_pharmacophores" in scores:
                result.gnn_pharmacophores = scores["gnn_pharmacophores"]

        if ai_report is not None:
            result.ai_report = ai_report

        result.error_message = error_message
        if error_message is not None:
            # Si hay error, limpiar scores y docking previos para evitar datos stale
            result.total_score = None
            result.affinity_score = None
            result.adme_score = None
            result.druglikeness_score = None
            result.affinity_kcal = None
            result.docking_poses = None
            result.poses_file_path = None
            result.scientific_warnings = []
            result.ai_report = None

        if task_id is not None:
            result.task_id = task_id

        result.evaluated_at = datetime.now(UTC)
        await self.db.flush()
        return result

    async def list_user_molecules(
        self,
        user_id: uuid.UUID,
        limit: int = 50,
    ) -> list[MoleculeORM]:
        stmt = (
            select(MoleculeORM)
            .options(
                selectinload(MoleculeORM.target),
                selectinload(MoleculeORM.evaluation_result),
            )
            .where(MoleculeORM.user_id == user_id)
            .order_by(MoleculeORM.created_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def delete_molecule(self, molecule_id: uuid.UUID) -> bool:
        """Elimina una molécula y sus resultados asociados (vía CASCADE)."""
        molecule = await self.db.get(MoleculeORM, molecule_id)
        if molecule:
            await self.db.delete(molecule)
            await self.db.flush()
            log.info("molécula eliminada por limpieza automática", molecule_id=str(molecule_id))
            return True
        return False


def get_repository(db: AsyncSession) -> Repository:
    return Repository(db)
