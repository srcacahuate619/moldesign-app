"""
rescoring/feature_extractor.py  —  v4.1 (RDKit-direct + shell counts + ECIF)

Extracción de features 3D de interacción proteína-ligando para ML rescoring.

═══════════════════════════════════════════════════════════════════════════
Estrategia de features:
  - El vector del modelo tiene 167 campos: 8 descriptores 1D/2D, 4 de
    docking, 3 de tamaño, 96 shell counts y 56 ECIF-lite.
  - Este extractor entrega 164 campos 3D: los 155 campos geométricos usados
    por el modelo y 9 conteos ProLIF sólo para trazabilidad/visualización.
  A. Features de interacción 3D ProLIF (9 features + 3 size-norm = 12):
     hbond_donor/acceptor_count, hydrophobic_contacts, salt_bridges,
     pi_stacking, pi_cation, metal_coordination,
     close_contacts_4A/6A, heavy_atom_count, contacts_per_ha_4A/6A
  D. Shell atom counts (96 features, RF-Score style):
     4 protein elements × 8 ligand elements × 3 distance shells
     Ref: Li et al., BMC Bioinformatics 2014;15:291
  D. ECIF-lite (56 features):
     8 protein extended types × 7 ligand element types at 6Å cutoff
     Ref: Sánchez-Cruz et al., Bioinformatics 2021;37(10):1376

═══════════════════════════════════════════════════════════════════════════
Librería: ProLIF (Protein-Ligand Interaction Fingerprints)
  Ref: Bouysset & Fiorucci, 2021, DOI: 10.1186/s13321-021-00548-6
  ProLIF detecta interacciones no-covalentes usando criterios geométricos
  (distancia, ángulo) publicados en la literatura.

Arquitectura de carga optimizada (v3):
  - Proteína PDB: se carga con RDKit.Chem.MolFromPDBFile()
    (0.08s vs ~20s vía MDAnalysis + bond order inference).
    RDKit asigna bonds por distancia interatómica, suficiente para PDB.
  - Ligando SDF: se carga con RDKit.Chem.SDMolSupplier (robusto).
  - Ligando PDBQT (inferencia): MDAnalysis → ProLIF.Molecule.from_mda()
    Coordenadas 3D extraídas del conformer de ProLIF/RDKit (no de MDAnalysis
    .atoms.positions) para garantizar consistencia de orden de átomos.
  - Close contacts: numpy pairwise distance (vectorizado, <0.01s).

ProLIF interactions solicitadas (TARGETED_INTERACTIONS):
  Solo pedimos las 7 interacciones que mapeamos a nuestras features.
  Excluimos VdWContact (no la usamos; close_contacts se calcula aparte).

Binding site filtering:
  ProLIF acepta ``residues=`` para limitar qué residuos de proteína analizar.
  Identificamos residuos con algún átomo < BINDING_SITE_CUTOFF Å del ligando
  y solo esos pasan a ProLIF.

Degradación elegante:
  Si ProLIF no está disponible, o si archivos son ilegibles, se retornan
  features en 0.0 con warning explícito.  El pipeline de training reporta
  ``n_success_3d`` y ``n_failed_3d`` para auditoría.

Limitaciones documentadas:
  - Protonación: PDB de PDBbind rara vez tienen H optimizados.
    RDKit agrega H heurísticamente — esto afecta dirección de H-bonds.
  - Aromaticidad: RDKit puede diferir de la realidad cuántica para
    π-stacking y π-catión.
  - Close contacts incluyen H si el PDB los tiene.
  - MetalAcceptor requiere iones metálicos en el PDB (no siempre presentes).
  - ProLIF fingerprint toma ~20s por complejo (inherent per-residue iteration).
    Para batch training, usar multiprocessing en el orchestrator.

─── Historial ───
  v1: ODDT (no compila en Python >= 3.13 por dep 'six').
  v2: ProLIF vía MDAnalysis (20-25s/complejo, valence issues en H).
  v3: RDKit-direct loading + numpy close contacts.
"""

from __future__ import annotations

import os
import tempfile
import warnings
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
from logger import get_logger

log = get_logger(__name__)


# ─────────────────────────────────────────────────────────────
# Constantes públicas — contrato con train_pipeline.py
# ─────────────────────────────────────────────────────────────

# Cache version — increment when features change to invalidate cache
CACHE_VERSION: int = 4

INTERACTION_FEATURES: list[str] = [
    "hbond_donor_count",        # H-bonds donde el ligando es donor
    "hbond_acceptor_count",     # H-bonds donde el ligando es acceptor
    "hydrophobic_contacts",     # Contactos hidrofóbicos (C-C, ~4.5 Å)
    "salt_bridges",             # Puentes salinos (carga+ ↔ carga-, ~4.0 Å)
    "pi_stacking",              # π-stacking (face-to-face + edge-to-face)
    "pi_cation",                # Interacciones π-catión
    "metal_coordination",       # Coordinación con iones metálicos
    "close_contacts_4A",        # Átomos de proteína a < 4 Å del ligando
    "close_contacts_6A",        # Átomos de proteína a < 6 Å del ligando
]

# ─── Shell atom count features (RF-Score style) ───
# Ref: Li et al., BMC Bioinformatics 2014;15:291
# Count protein-ligand heavy-atom pairs binned by element and distance shell.
# Purely geometric — no dependence on interaction assignments or protonation.
# Universal for any protein-ligand complex.
PROTEIN_ELEMENTS: tuple[str, ...] = ('C', 'N', 'O', 'S')
LIGAND_ELEMENTS: tuple[str, ...] = ('C', 'N', 'O', 'S', 'F', 'P', 'Cl', 'Br')
SHELL_BINS: tuple[tuple[int, int], ...] = ((0, 4), (4, 8), (8, 12))

SHELL_FEATURES: list[str] = [
    f"shell_{pe}_{le}_{lo}_{hi}"
    for pe in PROTEIN_ELEMENTS
    for le in LIGAND_ELEMENTS
    for lo, hi in SHELL_BINS
]  # 4 × 8 × 3 = 96

_PROTEIN_ELEMENTS_SET = frozenset(PROTEIN_ELEMENTS)
_LIGAND_ELEMENTS_SET = frozenset(LIGAND_ELEMENTS)

# ─── ECIF-lite features ───
# Ref: Sánchez-Cruz et al., Bioinformatics 2021;37(10):1376
# Protein: extended types (element + aromaticity + donor/acceptor).
# Ligand: element-only (consistent between training SDF and inference PDBQT).
# Protein always loaded with RDKit → full typing available.
# Ligand may come from PDBQT (inference) → aromaticity not reliable.
PROT_ECIF_TYPES: tuple[str, ...] = (
    'C_ali', 'C_aro', 'N_don', 'N_acc', 'O_don', 'O_acc', 'S', 'other',
)
LIG_ECIF_TYPES: tuple[str, ...] = (
    'C', 'N', 'O', 'S', 'F', 'Hal', 'other',
)
ECIF_CUTOFF: float = 6.0

ECIF_FEATURES: list[str] = [
    f"ecif_{pt}_{lt}"
    for pt in PROT_ECIF_TYPES
    for lt in LIG_ECIF_TYPES
]  # 8 × 7 = 56

# ─── Size-normalization features ───
# Break MW bias: contacts-per-atom captures binding efficiency,
# not just absolute molecular size.
SIZE_NORM_FEATURES: list[str] = [
    "heavy_atom_count",
    "contacts_per_ha_4A",
    "contacts_per_ha_6A",
]

# ─── Full v4 model feature contract ───
# ═══════════════════════════════════════════════════════════════════════
# IMPORTANTE (fix #3 Spearman): INTERACTION_FEATURES (ProLIF) están
# EXCLUIDOS de ALL_3D_FEATURES porque actúan como ruido en regresión.
#
# Benchmark 5-HT1A: Interaction score ρ=-0.035 (no correlaciona con pKi).
# Los conteos de interacciones ProLIF son herramientas de validación
# VISUAL (frontend 3D viewer), NO features para XGBoost.
#
# En GPCRs como 5-HT1A, la afinidad no la dicta la cantidad de
# interacciones sino la especificidad (ej: puente salino con ASP116).
# ═══════════════════════════════════════════════════════════════════════
ALL_3D_FEATURES: list[str] = (
    SHELL_FEATURES + ECIF_FEATURES + SIZE_NORM_FEATURES
)

# Output contract of the extractor. ProLIF counts remain available for
# transparency in the API, but are intentionally not part of ALL_3D_FEATURES
# nor of the 167-field Model A vector.
EXTRACTED_3D_FEATURES: list[str] = INTERACTION_FEATURES + ALL_3D_FEATURES

# Cutoff en Å para selección de binding site.
# Solo residuos de proteína con algún átomo dentro de este radio son
# pasados a ProLIF. 10 Å es estándar en drug design (Vina usa ~8 Å para grid).
BINDING_SITE_CUTOFF: float = 10.0

# Interacciones solicitadas a ProLIF (excluye VdWContact que no mapeamos).
TARGETED_INTERACTIONS: list[str] = [
    "HBDonor", "HBAcceptor", "Hydrophobic",
    "Anionic", "Cationic",
    "PiStacking", "FaceToFace", "EdgeToFace",
    "PiCation", "CationPi",
    "MetalAcceptor",
]

# Mapeo: ProLIF interaction type → nuestra feature acumulativa.
_PROLIF_TYPE_TO_FEATURE: dict[str, str] = {
    "HBDonor":       "hbond_donor_count",
    "HBAcceptor":    "hbond_acceptor_count",
    "Hydrophobic":   "hydrophobic_contacts",
    "Anionic":       "salt_bridges",
    "Cationic":      "salt_bridges",
    "PiStacking":    "pi_stacking",
    "FaceToFace":    "pi_stacking",
    "EdgeToFace":    "pi_stacking",
    "PiCation":      "pi_cation",
    "CationPi":      "pi_cation",
    "MetalAcceptor": "metal_coordination",
}


# ─────────────────────────────────────────────────────────────
# Funciones utilitarias públicas
# ─────────────────────────────────────────────────────────────

def zero_interaction_features() -> dict[str, float]:
    """
    Retornar dict de features 3D en cero.

    Uso legítimo:
      - Degradación elegante cuando la extracción falla.
      - skip_structure_checks=True en el pipeline de training.
      - Ablation testing con features vaciadas.
    """
    return {feat: 0.0 for feat in INTERACTION_FEATURES}


def zero_all_3d_features() -> dict[str, float]:
    """
    Retornar el vector geométrico v4 del modelo en cero (155 features).

    Incluye: shell atom counts + ECIF + size-norm (excluye interacciones
    ProLIF — fix #3 Spearman: son ruido en regresión).
    """
    return {feat: 0.0 for feat in ALL_3D_FEATURES}


def zero_extracted_3d_features() -> dict[str, float]:
    """Retornar el contrato completo del extractor (164 fields) en cero.

    Incluye los nueve conteos ProLIF para que una extracción degradada tenga
    exactamente las mismas claves que una exitosa. Estos conteos no alimentan
    el modelo A; se conservan para auditoría y visualización.
    """
    return {feat: 0.0 for feat in EXTRACTED_3D_FEATURES}


def check_prolif_available() -> bool:
    """Verificar que ProLIF y MDAnalysis son importables."""
    try:
        import MDAnalysis  # noqa: F401
        import prolif  # noqa: F401
        return True
    except ImportError:
        return False


# ─────────────────────────────────────────────────────────────
# Clase principal
# ─────────────────────────────────────────────────────────────

class InteractionFeatureExtractor:
    """
    Extrae features de interacción 3D proteína-ligando.

    Dos modos de operación:

    1. **Training** (PDBbind): ``extract_from_files(protein_pdb, ligand_sdf)``
       Lee archivos de estructura cristalográfica.
       Usa RDKit-direct para carga rápida + ProLIF para fingerprint.

    2. **Inferencia** (post-docking): ``extract_from_pose(pdbqt, target_pdb)``
       Recibe el output PDBQT de Vina + el PDB del target.

    En ambos casos, el output sigue ``EXTRACTED_3D_FEATURES`` (164 campos):
    los 155 campos geométricos del modelo y 9 conteos ProLIF de auditoría.
    """

    def __init__(self) -> None:
        self._prolif_ok = check_prolif_available()
        if not self._prolif_ok:
            log.warning(
                "prolif_not_available",
                msg="ProLIF no disponible. Features 3D serán cero. "
                    "pip install prolif",
            )

    @property
    def is_available(self) -> bool:
        """True si ProLIF + MDAnalysis están instalados."""
        return self._prolif_ok

    # ─── Training: archivos PDB + SDF ────────────────────────

    def extract_from_files(
        self,
        protein_pdb_path: str | Path,
        ligand_sdf_path: str | Path,
    ) -> dict[str, float]:
        """
        Extraer features 3D desde archivos PDB (proteína) + SDF (ligando).

        Pipeline optimizado (v4):
          1. Cargar ligando con RDKit SDMolSupplier (fallback relajado)
          2. Cargar proteína con RDKit MolFromPDBFile (~0.08s)
          3. Crear ProLIF Molecules
          4. Binding site residues (numpy distances)
          5. ProLIF Fingerprint solo en binding site
          6. Mapear interacciones → 9 categorías
          7. Close contacts + shell atom counts + ECIF
          8. Size-normalized features

        Returns:
            dict con las 164 keys de EXTRACTED_3D_FEATURES.
            Valores 0.0 si algo falla.
        """
        # Pipeline optimizado (v4)
        protein_pdb_path = Path(protein_pdb_path)
        ligand_sdf_path = Path(ligand_sdf_path)

        if not protein_pdb_path.exists():
            log.warning("protein_file_missing", path=str(protein_pdb_path))
            return zero_extracted_3d_features()

        if not ligand_sdf_path.exists():
            log.warning("ligand_file_missing", path=str(ligand_sdf_path))
            return zero_extracted_3d_features()

        try:
            return self._extract_pdb_sdf(
                str(protein_pdb_path), str(ligand_sdf_path)
            )
        except Exception as e:
            log.warning(
                "extraction_failed_files",
                error=str(e),
                protein=protein_pdb_path.name,
                ligand=ligand_sdf_path.name,
            )
            return zero_extracted_3d_features()

    # ─── Inferencia: PDBQT pose + PDB target ─────────────────

    def extract_from_pose(
        self,
        pose_pdbqt_block: str,
        target_pdb_path: str | Path,
        smiles: str = "",
        skip_prolif: bool = False,
    ) -> dict[str, float]:
        """
        Extraer features 3D de una pose de docking (output de Vina).

        Args:
            pose_pdbqt_block: Contenido PDBQT de la pose dockeada
            target_pdb_path: Ruta al archivo PDB del target
            smiles: SMILES para logging
            skip_prolif: Si True, saltea ProLIF (ahorra ~2s por molecula).
                         Solo se usa para ML inference donde las interacciones
                         ProLIF ya no son features de training (fix #3 Spearman).

        Returns:
            dict con keys de EXTRACTED_3D_FEATURES (164 fields).
            Valores 0.0 si algo falla.
        """
        if not self._prolif_ok and not skip_prolif:
            return zero_extracted_3d_features()

        try:
            return self._extract_pdbqt(
                pose_pdbqt_block, str(target_pdb_path), skip_prolif=skip_prolif
            )
        except Exception as e:
            log.warning(
                "extraction_failed_pose",
                error=str(e),
                smiles=smiles[:50] if smiles else "N/A",
            )
            return zero_extracted_3d_features()

    # ─────────────────────────────────────────────────────────
    # Implementación interna — Training path
    # ─────────────────────────────────────────────────────────

    def _extract_pdb_sdf(
        self,
        protein_pdb: str,
        ligand_sdf: str,
    ) -> dict[str, float]:
        """
        Core pipeline: PDB + SDF → 164 interaction features (v4).

        Usa RDKit-direct para cargar proteína (0.08s vs 20s en v2)
        y ProLIF para fingerprint de interacciones.
        Shell atom counts y ECIF calculados con numpy.
        """

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")

            # 1. Ligando (RDKit, con fallback relajado)
            lig_rdmol = _load_ligand_sdf(ligand_sdf)
            if lig_rdmol is None:
                log.warning("ligand_sdf_unreadable", path=ligand_sdf)
                return zero_extracted_3d_features()

            lig_coords = _get_conformer_coords(lig_rdmol)
            if lig_coords is None:
                log.warning("ligand_no_3d_coords", path=ligand_sdf)
                return zero_extracted_3d_features()

            # 2. Proteína (RDKit-direct, rápido)
            prot_rdmol = _load_protein_pdb(protein_pdb)
            if prot_rdmol is None:
                log.warning("protein_pdb_unreadable", path=protein_pdb)
                return zero_extracted_3d_features()

            # 3. ProLIF Molecules (Opcional)
            features = zero_extracted_3d_features()
            
            if self._prolif_ok:
                try:
                    import prolif
                    prot_mol = prolif.Molecule(prot_rdmol)
                    lig_mol = prolif.Molecule(lig_rdmol)

                    if len(prot_mol.residues) > 0:
                        # 4. Binding site residues (numpy distances)
                        bs_resids = _find_binding_site_residues(
                            prot_mol, lig_coords, BINDING_SITE_CUTOFF
                        )

                        # 5. ProLIF fingerprint (binding site only)
                        fp = prolif.Fingerprint(interactions=TARGETED_INTERACTIONS)
                        fp.run_from_iterable(
                            [lig_mol], prot_mol,
                            residues=bs_resids if bs_resids else None,
                            progress=False,
                            n_jobs=1,
                        )
                        df = fp.to_dataframe()

                        # 6. Mapear interacciones
                        if not df.empty:
                            features.update(_map_prolif_dataframe(df))
                except Exception as e:
                    log.warning("prolif_runtime_failed", error=str(e))

            # 7. Close contacts + shell counts + ECIF (numpy, <0.1s total)
            prot_coords = _get_conformer_coords(prot_rdmol)
            if prot_coords is not None:
                # Close contacts (original 2 features)
                cc4, cc6 = _compute_close_contacts(prot_coords, lig_coords)
                features["close_contacts_4A"] = cc4
                features["close_contacts_6A"] = cc6

                # Shell atom counts — RF-Score style (96 features)
                features.update(_compute_shell_atom_counts(
                    prot_rdmol, lig_rdmol, prot_coords, lig_coords,
                ))

                # ECIF-lite — extended type pairs (56 features)
                features.update(_compute_ecif_features(
                    prot_rdmol, lig_rdmol, prot_coords, lig_coords,
                ))

            # 8. Size-normalized features
            hac = sum(
                1 for a in lig_rdmol.GetAtoms() if a.GetAtomicNum() > 1
            )
            features["heavy_atom_count"] = float(hac)
            cc4 = features.get("close_contacts_4A", 0.0)
            cc6 = features.get("close_contacts_6A", 0.0)
            features["contacts_per_ha_4A"] = cc4 / max(hac, 1)
            features["contacts_per_ha_6A"] = cc6 / max(hac, 1)

        return features

    # ─────────────────────────────────────────────────────────
    # Implementación interna — Inference path
    # ─────────────────────────────────────────────────────────

    def _extract_pdbqt(
        self,
        pdbqt_block: str,
        target_pdb: str,
        skip_prolif: bool = False,
    ) -> dict[str, float]:
        """
        Core pipeline: PDBQT (docking pose) + PDB (target) → features.

        PDBQT se escribe a archivo temporal para parseo con MDAnalysis.
        Proteína se carga con RDKit-direct.

        Cuando skip_prolif=True (v1.3), saltea ProLIF completamente y solo
        calcula features geometricas con numpy (Shell + ECIF + size-norm).
        Esto ahorra ~2s por molecula porque ProLIF es O(n_lig × n_prot).

        ═══════════════════════════════════════════════════════════════
        IMPORTANTE (v1.3): Las features de interaccion ProLIF ya NO se
        usan en el modelo ML (fix #3). Se retornan como 0.0 en el dict
        para mantener compatibilidad con el contrato ALL_3D_FEATURES.
        ═══════════════════════════════════════════════════════════════
        """
        from rdkit import Chem

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")

            # Proteína (RDKit-direct)
            prot_rdmol = _load_protein_pdb(target_pdb)
            if prot_rdmol is None:
                log.warning("protein_unreadable_inference", path=target_pdb)
                return zero_extracted_3d_features()

            features = zero_extracted_3d_features()
            lig_coords = None
            lig_mol = None

            # ── ProLIF (solo si no estamos en modo fast-path) ──
            if not skip_prolif and self._prolif_ok:
                try:
                    import MDAnalysis as mda
                    import prolif
                    prot_mol = _get_prolif_protein_cached(target_pdb)
                    if prot_mol is None:
                        prot_mol = prolif.Molecule(prot_rdmol)
                    tmp_path = None

                    try:
                        clean_lines = []
                        for line in pdbqt_block.splitlines():
                            if line.startswith(("ATOM", "HETATM")):
                                clean_lines.append(line[:66])
                            elif line.startswith(("MODEL", "ENDMDL", "TER")):
                                clean_lines.append(line)
                        clean_block = "\n".join(clean_lines)
                        rd_lig = Chem.MolFromPDBBlock(clean_block)
                        if rd_lig is not None and rd_lig.GetNumConformers() > 0:
                            lig_mol = prolif.Molecule(rd_lig)
                            lig_coords = _get_conformer_coords(lig_mol)
                    except Exception as rd_err:
                        log.debug("clean_rdkit_pdb_load_failed", error=str(rd_err))

                    if lig_mol is None:
                        fd, tmp_path = tempfile.mkstemp(suffix=".pdb")
                        os.close(fd)
                        try:
                            with open(tmp_path, "w", encoding="utf-8") as tmp_file:
                                tmp_file.write(pdbqt_block)
                            lig_u = mda.Universe(tmp_path)
                            from MDAnalysis.topology.guessers import guess_types
                            elements = guess_types(lig_u.atoms.names)
                            lig_u.add_TopologyAttr('elements', elements)
                            lig_u.add_TopologyAttr('types', elements)
                            lig_mol = prolif.Molecule.from_mda(lig_u)
                            lig_coords = _get_conformer_coords(lig_mol)
                        except Exception as mda_err:
                            log.warning("mda_loading_failed", error=str(mda_err))
                            lig_coords = _manual_parse_pdbqt_coords(pdbqt_block)
                            if lig_coords is not None:
                                log.info("coords_extracted_via_manual_fallback", n_atoms=len(lig_coords))
                        finally:
                            if tmp_path and os.path.exists(tmp_path):
                                try:
                                    os.unlink(tmp_path)
                                except OSError:
                                    pass

                    if lig_mol and len(prot_mol.residues) > 0:
                        bs_resids = _find_binding_site_residues(
                            prot_mol, lig_coords, BINDING_SITE_CUTOFF
                        )
                        fp = prolif.Fingerprint(interactions=TARGETED_INTERACTIONS)
                        fp.run_from_iterable(
                            [lig_mol], prot_mol,
                            residues=bs_resids if bs_resids else None,
                            progress=False,
                            n_jobs=1,
                        )
                        df = fp.to_dataframe()
                        if not df.empty:
                            features.update(_map_prolif_dataframe(df))
                except Exception as e:
                    log.warning("prolif_inference_failed", error=str(e))

            # ═════════════════════════════════════════════════════════
            # FAST PATH (v1.3): Solo features geometricas con numpy
            # Saltamos ProLIF y cargamos coordenadas con RDKit-direct.
            # ═════════════════════════════════════════════════════════
            if lig_coords is None or len(lig_coords) == 0:
                # PDBQT-aware parser: RDKit's MolFromPDBBlock does NOT understand AD4 atom
                # types (A, NA, OA, HD, etc.) and takes 30-50s to fail on each molecule.
                # Go directly to the AD4→Element manual parser instead.
                try:
                    from rdkit.Geometry import Point3D
                    AD4_TO_ELEMENT = {
                        "C": "C", "A": "C", "N": "N", "NA": "N", "NS": "N",
                        "O": "O", "OA": "O", "OS": "O", "H": "H", "HD": "H", "HS": "H", "HO": "H",
                        "S": "S", "SA": "S", "P": "P", "F": "F", "Cl": "Cl", "Br": "Br", "I": "I",
                        "Mg": "Mg", "Ca": "Ca", "Zn": "Zn", "Fe": "Fe", "Mn": "Mn",
                        "G": "C",   # AD4 generic carbon (some Vina outputs use 'G')
                    }
                    atoms = []
                    coords = []
                    for line in pdbqt_block.splitlines():
                        if not (line.startswith("ATOM") or line.startswith("HETATM")):
                            continue
                        if len(line) < 79:
                            continue
                        ad4_type = line[77:79].strip()
                        elem = AD4_TO_ELEMENT.get(ad4_type, "C")
                        try:
                            x = float(line[30:38])
                            y = float(line[38:46])
                            z = float(line[46:54])
                        except ValueError:
                            continue
                        atoms.append(elem)
                        coords.append((x, y, z))
                    if atoms:
                        editable = Chem.RWMol()
                        for elem in atoms:
                            editable.AddAtom(Chem.Atom(elem))
                        editable.UpdatePropertyCache(strict=False)
                        conf = Chem.Conformer(len(atoms))
                        for i, (x, y, z) in enumerate(coords):
                            conf.SetAtomPosition(i, Point3D(x, y, z))
                        editable.AddConformer(conf)
                        lig_mol = editable.GetMol()
                        try:
                            Chem.SanitizeMol(lig_mol, Chem.SanitizeFlags.SANITIZE_SYMMRINGS | Chem.SanitizeFlags.SANITIZE_FINDRADICALS)
                        except Exception:
                            pass
                        try:
                            Chem.FastFindRings(lig_mol)
                        except Exception:
                            pass
                        lig_coords = np.array(coords)
                except Exception:
                    pass

            if lig_coords is None or len(lig_coords) == 0:
                return zero_extracted_3d_features()

            # Close contacts + shell counts + ECIF (numpy, <0.05s)
            prot_coords = _get_conformer_coords(prot_rdmol)
            if prot_coords is not None:
                cc4, cc6 = _compute_close_contacts(prot_coords, lig_coords)
                features["close_contacts_4A"] = cc4
                features["close_contacts_6A"] = cc6
                if lig_mol is not None:
                    features.update(_compute_shell_atom_counts(
                        prot_rdmol, lig_mol, prot_coords, lig_coords,
                    ))
                    features.update(_compute_ecif_features(
                        prot_rdmol, lig_mol, prot_coords, lig_coords,
                    ))

            # Size-normalization
            hac = sum(1 for a in lig_mol.GetAtoms() if a.GetAtomicNum() > 1) if lig_mol else 0
            features["heavy_atom_count"] = float(hac)
            cc4 = features.get("close_contacts_4A", 0.0)
            cc6 = features.get("close_contacts_6A", 0.0)
            features["contacts_per_ha_4A"] = cc4 / max(hac, 1)
            features["contacts_per_ha_6A"] = cc6 / max(hac, 1)

        return features


# ═════════════════════════════════════════════════════════════
# Funciones helper (privadas, module-level)
# ═════════════════════════════════════════════════════════════

def _load_ligand_sdf(sdf_path: str):
    """
    Cargar ligando desde SDF con RDKit.

    Intento 1: SDMolSupplier estándar.
    Intento 2: MolFromMolFile con sanitización relajada
               (sin SANITIZE_PROPERTIES) para SDF de PDBbind con
               marcado aromático inconsistente.

    Returns:
        RDKit Mol con coordenadas 3D, o None.
    """
    from rdkit import Chem

    # Estándar
    supplier = Chem.SDMolSupplier(sdf_path, removeHs=False)
    try:
        mol = next(supplier)
        if mol is not None:
            return mol
    except StopIteration:
        pass

    # Relajado
    mol = Chem.MolFromMolFile(sdf_path, removeHs=False, sanitize=False)
    if mol is not None:
        try:
            Chem.SanitizeMol(
                mol,
                Chem.SanitizeFlags.SANITIZE_ALL
                ^ Chem.SanitizeFlags.SANITIZE_PROPERTIES,
            )
            return mol
        except Exception:
            return None
    return None


@lru_cache(maxsize=16)
def _load_protein_pdb(pdb_path: str):
    """
    Cargar proteína desde PDB con RDKit (rápido: ~0.08s).

    Usa sanitización relajada que tolera H con valence issues
    comunes en PDB de PDBbind (aguas residuales, H bridging, etc.).

    RDKit.Chem.MolFromPDBFile asigna bonds por distancia interatómica
    — no necesita la inferencia de bond orders de MDAnalysis.

    Intentos:
      1. removeHs=False, sanitize=False + SanitizeMol relajado
      2. removeHs=True (elimina H problemáticos; pierde H-bond exactos)

    Returns:
        RDKit Mol con residue info preservada por PDB, o None.
    """
    from rdkit import Chem

    # Intento 1: con H, sanitización relajada
    try:
        mol = Chem.MolFromPDBFile(pdb_path, removeHs=False, sanitize=False)
        if mol is not None:
            Chem.SanitizeMol(
                mol,
                Chem.SanitizeFlags.SANITIZE_ALL
                ^ Chem.SanitizeFlags.SANITIZE_PROPERTIES,
            )
            return mol
    except Exception:
        pass

    # Intento 2: sin H (más robusto)
    try:
        mol = Chem.MolFromPDBFile(pdb_path, removeHs=True, sanitize=False)
        if mol is not None:
            Chem.SanitizeMol(
                mol,
                Chem.SanitizeFlags.SANITIZE_ALL
                ^ Chem.SanitizeFlags.SANITIZE_PROPERTIES,
            )
            log.info(
                "protein_loaded_without_H",
                path=pdb_path,
                msg="H removidos por valence issues",
            )
            return mol
    except Exception:
        pass

    return None


@lru_cache(maxsize=16)
def _get_prolif_protein_cached(pdb_path: str):
    prot_rdmol = _load_protein_pdb(pdb_path)
    if prot_rdmol is None:
        return None
    import prolif
    return prolif.Molecule(prot_rdmol)


def _get_conformer_coords(rdmol) -> np.ndarray | None:
    """
    Extraer coordenadas 3D de un RDKit Mol como ndarray (n_atoms, 3).

    Returns:
        ndarray float32 shape (n_atoms, 3), o None si sin conformer.
    """
    try:
        conf = rdmol.GetConformer()
        return np.array(conf.GetPositions(), dtype=np.float32)
    except Exception:
        return None


def _find_binding_site_residues(
    prot_mol,  # prolif.Molecule
    lig_coords: np.ndarray,
    cutoff: float,
) -> list:
    """
    Identificar residuos de proteína en el binding site.

    Para cada residuo, calcula la distancia mínima de cualquiera de sus
    átomos a cualquier átomo del ligando.  Si < cutoff → incluido.

    Vectorizado: concatena todas las coords de residuos en una sola matriz
    y hace una única cdist contra el ligando, luego agrupa por residuo.
    Una sola operación O((N_res_atoms * N_lig_atoms)) vs el bucle anterior
    que recreaba el broadcasting por residuo.

    Args:
        prot_mol: prolif.Molecule de la proteína (con .residues)
        lig_coords: ndarray (n_lig, 3) — coordenadas del ligando
        cutoff: radio en Å

    Returns:
        Lista de prolif ResidueId dentro del binding site.
    """
    cutoff_sq = cutoff * cutoff

    # Recolectar coords de todos los residuos en una sola pasada
    all_res_coords = []
    res_atom_ranges: list[tuple[Any, int, int]] = []  # (resid, start, end)
    cursor = 0
    for resid, res in prot_mol.residues.items():
        try:
            res_coords = _get_conformer_coords(res)
            if res_coords is None or len(res_coords) == 0:
                continue
            all_res_coords.append(res_coords)
            res_atom_ranges.append((resid, cursor, cursor + len(res_coords)))
            cursor += len(res_coords)
        except Exception:
            continue

    if not all_res_coords:
        return []

    # Concatenar y computar distancias al cuadrado contra el ligando
    # (n_total_res_atoms, 3) - (1, n_lig, 3) → (n_total_res_atoms, n_lig, 3)
    res_coords_cat = np.concatenate(all_res_coords, axis=0).astype(np.float32, copy=False)
    diff = res_coords_cat[:, np.newaxis, :] - lig_coords[np.newaxis, :, :]
    dist_sq = (diff * diff).sum(axis=2)
    # Min distancia por átomo del residuo: (n_total_res_atoms,)
    min_per_atom = dist_sq.min(axis=1)

    # Para cada residuo, si algún átomo está dentro del cutoff → incluir
    bs_resids = []
    for resid, start, end in res_atom_ranges:
        if min_per_atom[start:end].min() < cutoff_sq:
            bs_resids.append(resid)

    return bs_resids


def _map_prolif_dataframe(df) -> dict[str, float]:
    """
    Convertir DataFrame de ProLIF a nuestro dict de 9 features.

    ProLIF produce DataFrame con multi-index de columnas:
      (ligand_residue, protein_residue, interaction_type)

    Cada celda es True/False.  Acumulamos conteos por tipo de interacción.
    Los tipos que no mapeamos (e.g. si ProLIF agrega nuevos) se ignoran
    sin error silencioso.

    Returns:
        dict con las 9 features (incluyendo close_contacts en 0.0).
    """
    features = zero_interaction_features()

    if df is None or df.empty:
        return features

    # Aggregate all conformers/frames with .any() so interactions seen in ANY pose
    # are counted — iloc[0] silently discarded all rows beyond the first.
    col_active = df.any(axis=0)

    for col in df.columns:
        if not col_active[col]:
            continue
        interaction_type = col[-1] if isinstance(col, tuple) else str(col)
        our_feature = _PROLIF_TYPE_TO_FEATURE.get(interaction_type)
        if our_feature is not None:
            features[our_feature] += 1.0

    return features


def _compute_close_contacts(
    prot_coords: np.ndarray,
    lig_coords: np.ndarray,
) -> tuple[float, float]:
    """
    Contar átomos de proteína cercanos al ligando (numpy vectorizado).

    Para cada átomo de proteína, calcula la distancia mínima a cualquier
    átomo del ligando.  Reporta conteos < 4 Å (van der Waals directos)
    y < 6 Å (primera esfera del binding site).

    Para evitar OOM en proteínas grandes, se procesa en chunks de 500
    átomos de proteína si necesario.

    Complejidad: O(n_prot × n_lig) pero numpy vectoriza eficientemente.
    Proteínas típicas (~3000 atoms) × ligandos (~50 atoms): <0.02s.

    Returns:
        (n_atoms_within_4A, n_atoms_within_6A)
    """
    n_prot = len(prot_coords)
    n_lig = len(lig_coords)

    if n_prot == 0 or n_lig == 0:
        return (0.0, 0.0)

    # Para proteínas grandes, chunk para evitar allocar n_prot×n_lig×3 float32
    # 500 * 100 * 3 * 4 bytes = 600 KB por chunk → seguro.
    CHUNK = 500
    n_4a = 0
    n_6a = 0

    for start in range(0, n_prot, CHUNK):
        end = min(start + CHUNK, n_prot)
        chunk = prot_coords[start:end]  # (chunk_size, 3)
        diff = chunk[:, np.newaxis, :] - lig_coords[np.newaxis, :, :]
        dist_sq = (diff * diff).sum(axis=2)   # (chunk_size, n_lig)
        min_dist_sq = dist_sq.min(axis=1)     # (chunk_size,)
        n_4a += int((min_dist_sq < 16.0).sum())  # 4² = 16
        n_6a += int((min_dist_sq < 36.0).sum())  # 6² = 36

    return (float(n_4a), float(n_6a))


# ─────────────────────────────────────────────────────────────
# Shell atom counts (RF-Score style) — v4 features
# ─────────────────────────────────────────────────────────────

def _compute_shell_atom_counts(
    prot_rdmol,
    lig_rdmol,
    prot_coords: np.ndarray,
    lig_coords: np.ndarray,
) -> dict[str, float]:
    """
    RF-Score style: count protein-ligand heavy-atom pairs in distance shells.

    For each (protein_element, ligand_element, distance_bin), count how many
    atom pairs fall in that bin.  This is purely geometric — no dependence on
    force field parameters, protonation state, or interaction heuristics.
    Universal for any protein-ligand complex.

    Only heavy atoms (Z > 1) are counted — standard in RF-Score.

    Performance: ~0.05s for typical complex (500 near atoms × 50 ligand atoms).
    Pre-filters protein to atoms within 12Å of any ligand atom.

    Ref: Li et al., BMC Bioinformatics 2014;15:291
    """
    features = {name: 0.0 for name in SHELL_FEATURES}

    if len(prot_coords) == 0 or len(lig_coords) == 0:
        return features

    # Get element symbols for heavy atoms only
    prot_atoms = prot_rdmol.GetAtoms()
    lig_atoms = lig_rdmol.GetAtoms()

    prot_heavy_mask = np.array([a.GetAtomicNum() > 1 for a in prot_atoms])
    lig_heavy_mask = np.array([a.GetAtomicNum() > 1 for a in lig_atoms])

    if not prot_heavy_mask.any() or not lig_heavy_mask.any():
        return features

    prot_h_coords = prot_coords[prot_heavy_mask]
    lig_h_coords = lig_coords[lig_heavy_mask]

    prot_h_syms = np.array([
        a.GetSymbol() for a in prot_atoms if a.GetAtomicNum() > 1
    ])
    lig_h_syms = np.array([
        a.GetSymbol() for a in lig_atoms if a.GetAtomicNum() > 1
    ])

    max_shell = max(hi for _, hi in SHELL_BINS)
    max_shell_sq = float(max_shell * max_shell)

    # Pre-filter: only protein atoms within max_shell Å of any ligand atom
    CHUNK = 500
    near_mask = np.zeros(len(prot_h_coords), dtype=bool)
    for start in range(0, len(prot_h_coords), CHUNK):
        end = min(start + CHUNK, len(prot_h_coords))
        diff = (
            prot_h_coords[start:end, np.newaxis, :]
            - lig_h_coords[np.newaxis, :, :]
        )
        dist_sq = (diff * diff).sum(axis=2)
        near_mask[start:end] = dist_sq.min(axis=1) < max_shell_sq

    near_idx = np.where(near_mask)[0]
    if len(near_idx) == 0:
        return features

    near_coords = prot_h_coords[near_idx]
    near_syms = prot_h_syms[near_idx]

    # Pairwise distances for near protein atoms vs all ligand heavy atoms
    diff = near_coords[:, np.newaxis, :] - lig_h_coords[np.newaxis, :, :]
    dists = np.sqrt((diff * diff).sum(axis=2))  # (n_near, n_lig_heavy)

    # Count by element pair and distance shell
    for pe in PROTEIN_ELEMENTS:
        pe_mask = near_syms == pe
        if not pe_mask.any():
            continue
        pe_dists = dists[pe_mask]

        for le in LIGAND_ELEMENTS:
            le_mask = lig_h_syms == le
            if not le_mask.any():
                continue
            pair_dists = pe_dists[:, le_mask]

            for lo, hi in SHELL_BINS:
                count = int(((pair_dists >= lo) & (pair_dists < hi)).sum())
                if count > 0:
                    features[f"shell_{pe}_{le}_{lo}_{hi}"] = float(count)

    return features


# ─────────────────────────────────────────────────────────────
# ECIF-lite (Extended Connectivity Interaction Features) — v4
# ─────────────────────────────────────────────────────────────

def _assign_prot_ecif_type(atom) -> str:
    """
    Assign ECIF protein atom type.

    Extended typing captures binding-site characteristics:
      - C_ali vs C_aro: hydrophobic packing vs π-stacking potential
      - N_don vs N_acc: H-bond direction prediction
      - O_don vs O_acc: same
      - S: rare but critical in Cys/Met interactions
      - other: metals, P, etc. (grouped to avoid sparse features)

    This function is only used for PROTEIN atoms, which are always
    loaded with RDKit from PDB (both training and inference).
    """
    sym = atom.GetSymbol()
    if sym == 'C':
        return 'C_aro' if atom.GetIsAromatic() else 'C_ali'
    if sym == 'N':
        return 'N_don' if atom.GetTotalNumHs() > 0 else 'N_acc'
    if sym == 'O':
        return 'O_don' if atom.GetTotalNumHs() > 0 else 'O_acc'
    if sym == 'S':
        return 'S'
    return 'other'


def _assign_lig_ecif_type(atom) -> str:
    """
    Assign ECIF ligand atom type (element-level only).

    Uses element symbols only (not aromaticity or hybridization) to ensure
    consistency between training (ligand from SDF/RDKit) and inference
    (ligand from PDBQT/MDAnalysis where aromaticity isn't reliable).

    Cl, Br, I grouped as 'Hal' (halogen bonding).
    """
    sym = atom.GetSymbol() if hasattr(atom, 'GetSymbol') else str(atom)
    if sym == 'C':
        return 'C'
    if sym == 'N':
        return 'N'
    if sym == 'O':
        return 'O'
    if sym == 'S':
        return 'S'
    if sym == 'F':
        return 'F'
    if sym in ('Cl', 'Br', 'I'):
        return 'Hal'
    return 'other'


def _compute_ecif_features(
    prot_rdmol,
    lig_rdmol,
    prot_coords: np.ndarray,
    lig_coords: np.ndarray,
) -> dict[str, float]:
    """
    ECIF-lite: count (protein_type, ligand_type) atom pairs within 6Å.

    Richer than element-only shell counts on the protein side because it
    distinguishes aromatic Cs (π-stacking competent) from aliphatic Cs
    (hydrophobic packing) and N/O donors from acceptors.

    The ligand side uses element-only types for train/inference consistency.

    Only heavy atoms (Z > 1) are counted.

    Ref: Sánchez-Cruz et al., Bioinformatics 2021;37(10):1376
    """
    features = {name: 0.0 for name in ECIF_FEATURES}

    if len(prot_coords) == 0 or len(lig_coords) == 0:
        return features

    prot_atoms_list = list(prot_rdmol.GetAtoms())
    lig_atoms_list = list(lig_rdmol.GetAtoms())

    # Heavy atoms only
    prot_heavy_idx = [
        i for i, a in enumerate(prot_atoms_list) if a.GetAtomicNum() > 1
    ]
    lig_heavy_idx = [
        i for i, a in enumerate(lig_atoms_list) if a.GetAtomicNum() > 1
    ]

    if not prot_heavy_idx or not lig_heavy_idx:
        return features

    prot_h_coords = prot_coords[prot_heavy_idx]
    lig_h_coords = lig_coords[lig_heavy_idx]

    prot_h_types = np.array([
        _assign_prot_ecif_type(prot_atoms_list[i]) for i in prot_heavy_idx
    ])
    lig_h_types = np.array([
        _assign_lig_ecif_type(lig_atoms_list[i]) for i in lig_heavy_idx
    ])

    cutoff_sq = ECIF_CUTOFF * ECIF_CUTOFF

    # Pre-filter: protein atoms within cutoff of any ligand atom
    CHUNK = 500
    near_mask = np.zeros(len(prot_h_coords), dtype=bool)
    for start in range(0, len(prot_h_coords), CHUNK):
        end = min(start + CHUNK, len(prot_h_coords))
        diff = (
            prot_h_coords[start:end, np.newaxis, :]
            - lig_h_coords[np.newaxis, :, :]
        )
        dist_sq = (diff * diff).sum(axis=2)
        near_mask[start:end] = dist_sq.min(axis=1) < cutoff_sq

    near_idx = np.where(near_mask)[0]
    if len(near_idx) == 0:
        return features

    near_coords = prot_h_coords[near_idx]
    near_types = prot_h_types[near_idx]

    # Pairwise squared distances
    diff = near_coords[:, np.newaxis, :] - lig_h_coords[np.newaxis, :, :]
    dist_sq = (diff * diff).sum(axis=2)  # (n_near, n_lig_heavy)
    within = dist_sq < cutoff_sq

    # Count by type pair
    for pt in PROT_ECIF_TYPES:
        pt_mask = near_types == pt
        if not pt_mask.any():
            continue
        pt_within = within[pt_mask]

        for lt in LIG_ECIF_TYPES:
            lt_mask = lig_h_types == lt
            if not lt_mask.any():
                continue
            count = int(pt_within[:, lt_mask].sum())
            if count > 0:
                features[f"ecif_{pt}_{lt}"] = float(count)

    return features


# ─────────────────────────────────────────────────────────────
# Multiprocessing helper (para train_orchestrator.py)
# ─────────────────────────────────────────────────────────────

def extract_single_complex(
    protein_pdb: str,
    ligand_sdf: str,
) -> dict[str, float]:
    """
    Top-level function para extracción paralela (multiprocessing).

    ``concurrent.futures.ProcessPoolExecutor`` requiere funciones pickleable
    en top-level del módulo.  Esta función crea un ``InteractionFeatureExtractor``
    descartable y procesa un complejo.

    Args:
        protein_pdb: ruta absoluta al PDB de proteína
        ligand_sdf: ruta absoluta al SDF del ligando

    Returns:
        dict con el contrato ``EXTRACTED_3D_FEATURES`` (zeros si falla).
    """
    ext = InteractionFeatureExtractor()
    return ext.extract_from_files(protein_pdb, ligand_sdf)


def _manual_parse_pdbqt_coords(pdbqt_block: str) -> np.ndarray | None:
    """
    Parser manual de emergencia para extraer coordenadas de un PDBQT.
    Útil cuando MDAnalysis/RDKit fallan por temas de valencia o hidrógenos.
    """
    coords = []
    try:
        for line in pdbqt_block.splitlines():
            if line.startswith(("ATOM", "HETATM")):
                # PDB format: x(31-38), y(39-46), z(47-54)
                try:
                    x = float(line[30:38].strip())
                    y = float(line[38:46].strip())
                    z = float(line[46:54].strip())
                    coords.append([x, y, z])
                except (ValueError, IndexError):
                    continue
        if not coords:
            return None
        return np.array(coords, dtype=np.float32)
    except Exception:
        return None
