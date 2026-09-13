"""
rescoring/vip_audit.py

Auditoría de calidad ("VIP audit") para complejos de PDBbind.

Implementa 5 checks obligatorios definidos en ML_RESCORING_ARCHITECTURE.md
(Problema 1: Feature Extraction Hell). Solo los complejos que pasen
TODOS los checks se usan para entrenamiento.

Checks:
  1. Ligando: SMILES parseable por RDKit, sin átomos exóticos
  2. Resolución: ≤ 2.5 Å
  3. Completitud: Sin residuos faltantes en radio de 5 Å del binding site
  4. Datos de binding: Solo Ki o Kd (no IC50/EC50)
  5. Features: Interacciones 3D no triviales (no todas cero)

Output: artifacts/pdbbind_audit_report.json con estadísticas completas.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from logger import get_logger

log = get_logger(__name__)


# Elementos permitidos en ligandos (orgánicos comunes en drug discovery)
ALLOWED_ELEMENTS = {"C", "N", "O", "S", "F", "Cl", "Br", "I", "P", "H"}

# Resolución máxima permitida
MAX_RESOLUTION_A = 2.5

# Radio para check de completitud (Å)
BINDING_SITE_RADIUS_A = 5.0

# Tipos de binding aceptados
ACCEPTED_BINDING_TYPES = {"Ki", "Kd"}

# Mínimo de features no-cero para considerar que la extracción fue exitosa
MIN_NONZERO_FEATURES = 1


@dataclass
class AuditResult:
    """Resultado de la auditoría de un complejo."""
    pdb_id: str
    passed: bool
    checks: dict[str, bool] = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    # Detalle de features extraídas (si se llegó al check 5)
    n_features_nonzero: int = 0
    feature_values: dict[str, float] = field(default_factory=dict)


@dataclass
class AuditReport:
    """Reporte consolidado de la auditoría de PDBbind."""
    total_evaluated: int = 0
    total_accepted: int = 0
    total_rejected: int = 0
    rejection_reasons: dict[str, int] = field(default_factory=dict)
    rejected_ids: dict[str, list[str]] = field(default_factory=dict)
    # Distribución de binding affinity (aceptados vs rechazados)
    accepted_pki_stats: dict[str, float] = field(default_factory=dict)
    rejected_pki_stats: dict[str, float] = field(default_factory=dict)
    # Metadata
    timestamp: str = ""
    duration_seconds: float = 0.0
    # Todos los resultados individuales
    results: list[AuditResult] = field(default_factory=list)


class VIPAuditor:
    """
    Auditor de calidad para complejos PDBbind.

    Ejecuta los 5 checks VIP sobre cada complejo y produce un reporte
    detallado para revisión manual antes de proceder a entrenamiento.

    Uso:
        auditor = VIPAuditor()
        report = auditor.audit_all(parser.complexes, feature_extractor)
        auditor.save_report(report, "artifacts/pdbbind_audit_report.json")
    """

    def __init__(
        self,
        max_resolution: float = MAX_RESOLUTION_A,
        accepted_binding_types: set[str] | None = None,
        allowed_elements: set[str] | None = None,
        min_nonzero_features: int = MIN_NONZERO_FEATURES,
        skip_structure_checks: bool = False,
    ):
        """
        Args:
            max_resolution: resolución máxima en Å
            accepted_binding_types: tipos de binding aceptados
            allowed_elements: elementos permitidos en ligandos
            min_nonzero_features: mínimo de features 3D no-cero
            skip_structure_checks: si True, salta checks 3 y 5 (sin archivos PDB)
        """
        self._max_resolution = max_resolution
        self._accepted_binding_types = accepted_binding_types or ACCEPTED_BINDING_TYPES
        self._allowed_elements = allowed_elements or ALLOWED_ELEMENTS
        self._min_nonzero_features = min_nonzero_features
        self._skip_structure_checks = skip_structure_checks

    def audit_complex(
        self,
        cpx: Any,
        feature_extractor: Any | None = None,
    ) -> AuditResult:
        """
        Ejecutar los 5 checks sobre un complejo.

        Args:
            cpx: PDBBindComplex con metadata y paths
            feature_extractor: FeatureExtractor (opcional, para check 5)

        Returns:
            AuditResult con checks detallados
        """
        result = AuditResult(pdb_id=cpx.pdb_id, passed=True)

        # Check 1: Ligando parseable, sin átomos exóticos
        self._check_ligand(cpx, result)

        # Check 2: Resolución ≤ 2.5 Å
        self._check_resolution(cpx, result)

        # Check 3: Completitud del binding site
        if not self._skip_structure_checks:
            self._check_completeness(cpx, result)
        else:
            result.checks["completeness"] = True
            result.warnings.append("Check de completitud omitido (sin archivos PDB)")

        # Check 4: Tipo de binding (Ki/Kd, no IC50)
        self._check_binding_type(cpx, result)

        # Check 5: Features no triviales
        if not self._skip_structure_checks and feature_extractor is not None:
            self._check_features(cpx, feature_extractor, result)
        else:
            result.checks["features"] = True
            if self._skip_structure_checks:
                result.warnings.append("Check de features omitido (sin archivos PDB)")
            elif feature_extractor is None:
                result.warnings.append("Check de features omitido (sin feature_extractor)")

        # Un solo fallo → rechazado
        result.passed = all(result.checks.values())

        return result

    def _check_ligand(self, cpx: Any, result: AuditResult) -> None:
        """
        Check 1: SMILES parseable por RDKit, sin átomos exóticos.

        Rechaza: metales, ligandos covalentes, fragmentos mixtos, átomos raros.
        """
        try:
            from rdkit import Chem

            smiles = cpx.ligand_smiles

            # Si no tiene SMILES, intentar extraer del SDF
            if not smiles and cpx.ligand_sdf_path:
                try:
                    mol = Chem.MolFromMolFile(cpx.ligand_sdf_path, sanitize=True)
                    if mol:
                        smiles = Chem.MolToSmiles(mol)
                        cpx.ligand_smiles = smiles
                except Exception:
                    pass

            if not smiles:
                result.checks["ligand"] = False
                result.failures.append("No SMILES disponible")
                return

            mol = Chem.MolFromSmiles(smiles)
            if mol is None:
                result.checks["ligand"] = False
                result.failures.append(f"SMILES no parseable: {smiles}")
                return

            # Verificar elementos
            elements = set()
            for atom in mol.GetAtoms():
                elements.add(atom.GetSymbol())

            exotic = elements - self._allowed_elements
            if exotic:
                result.checks["ligand"] = False
                result.failures.append(
                    f"Átomos exóticos: {sorted(exotic)}"
                )
                return

            # Verificar peso molecular razonable (50-1000 Da)
            from rdkit.Chem import Descriptors
            mw = Descriptors.MolWt(mol)
            cpx.molecular_weight = mw
            cpx.n_heavy_atoms = mol.GetNumHeavyAtoms()

            if mw < 50:
                result.checks["ligand"] = False
                result.failures.append(f"MW muy bajo: {mw:.1f} Da")
                return

            if mw > 1000:
                result.checks["ligand"] = False
                result.failures.append(f"MW muy alto: {mw:.1f} Da (posible péptido)")
                return

            # Verificar que no es un fragmento mixto (múltiples componentes)
            frags = Chem.GetMolFrags(mol)
            if len(frags) > 1:
                result.checks["ligand"] = False
                result.failures.append(
                    f"Molécula con {len(frags)} fragmentos (complejo/sal)"
                )
                return

            result.checks["ligand"] = True

        except ImportError:
            result.checks["ligand"] = False
            result.failures.append("RDKit no disponible")
        except Exception as e:
            result.checks["ligand"] = False
            result.failures.append(f"Error en check de ligando: {e!s}")

    def _check_resolution(self, cpx: Any, result: AuditResult) -> None:
        """
        Check 2: Resolución cristalográfica ≤ max_resolution Å.

        Estructuras de baja resolución tienen posiciones atómicas imprecisas,
        lo que degrada la calidad de las features 3D.
        """
        resolution = cpx.resolution

        if resolution <= 0:
            result.checks["resolution"] = False
            result.failures.append("Resolución no disponible o inválida")
            return

        if resolution > self._max_resolution:
            result.checks["resolution"] = False
            result.failures.append(
                f"Resolución {resolution:.2f} Å > límite {self._max_resolution} Å"
            )
            return

        result.checks["resolution"] = True

    def _check_completeness(self, cpx: Any, result: AuditResult) -> None:
        """
        Check 3: Sin residuos faltantes en radio de 5 Å del binding site.

        Si la proteína tiene gaps en la región del binding site, las features
        de interacción serán incorrectas (falsos negativos de H-bonds, etc).

        LIMITACIÓN: Este check requiere archivos PDB con anotaciones REMARK 465
        (residuos faltantes) o análisis de secuencia. Implementamos la versión
        pragmática basada en REMARK 465.
        """
        protein_path = cpx.protein_pdb_path

        if not protein_path:
            result.checks["completeness"] = False
            result.failures.append("Archivo PDB de proteína no disponible")
            return

        try:
            protein_path = Path(protein_path)
            if not protein_path.exists():
                result.checks["completeness"] = False
                result.failures.append(f"PDB no encontrado: {protein_path}")
                return

            # Parsear REMARK 465 (residuos faltantes)
            missing_residues = self._parse_missing_residues(protein_path)

            if not missing_residues:
                # Sin anotaciones de residuos faltantes → pasa
                result.checks["completeness"] = True
                return

            # Verificar si algún residuo faltante está cerca del binding site
            # Esto requiere las coordenadas del ligando para calcular distancia
            if cpx.ligand_sdf_path and Path(cpx.ligand_sdf_path).exists():
                near_missing = self._check_missing_near_ligand(
                    protein_path,
                    Path(cpx.ligand_sdf_path),
                    missing_residues,
                    radius=BINDING_SITE_RADIUS_A,
                )
                if near_missing:
                    result.checks["completeness"] = False
                    result.failures.append(
                        f"{len(near_missing)} residuos faltantes cerca del binding site: "
                        f"{', '.join(near_missing[:5])}"
                    )
                    return

            result.checks["completeness"] = True

        except Exception as e:
            result.checks["completeness"] = False
            result.failures.append(f"Error en check de completitud: {e!s}")

    def _parse_missing_residues(self, pdb_path: Path) -> list[dict]:
        """
        Extraer residuos faltantes de REMARK 465 en un PDB.

        REMARK 465 format:
          REMARK 465     M RES C SSSEQI
          REMARK 465       ALA A    23
        """
        missing = []
        in_remark_465 = False

        with open(pdb_path) as f:
            for line in f:
                if line.startswith("REMARK 465"):
                    in_remark_465 = True
                    parts = line[10:].strip().split()
                    if len(parts) >= 3 and parts[0].isalpha() and len(parts[0]) == 3:
                        try:
                            resname = parts[0]
                            chain = parts[1]
                            resnum = int(parts[2])
                            missing.append({
                                "resname": resname,
                                "chain": chain,
                                "resnum": resnum,
                            })
                        except (ValueError, IndexError):
                            pass
                elif in_remark_465 and not line.startswith("REMARK"):
                    break

        return missing

    def _check_missing_near_ligand(
        self,
        protein_path: Path,
        ligand_path: Path,
        missing_residues: list[dict],
        radius: float,
    ) -> list[str]:
        """
        Verificar si hay residuos faltantes cerca del ligando.

        Usa las coordenadas ATOM del PDB para estimar posición de residuos
        adyacentes a los faltantes. Si un residuo faltante tiene vecinos
        dentro del radio del ligando, se reporta como problema.

        Returns:
            Lista de IDs de residuos problemáticos
        """
        try:
            from rdkit import Chem

            # Leer coordenadas del ligando
            lig_mol = Chem.MolFromMolFile(str(ligand_path), sanitize=False)
            if lig_mol is None:
                return []

            conf = lig_mol.GetConformer()
            lig_coords = np.array([
                conf.GetAtomPosition(i)
                for i in range(lig_mol.GetNumAtoms())
            ])

            lig_center = lig_coords.mean(axis=0)

            # Parsear coordenadas CA de la proteína para estimar posición
            # de residuos faltantes (usando vecinos)
            ca_coords = {}  # (chain, resnum) → (x, y, z)
            with open(protein_path) as f:
                for line in f:
                    if line.startswith("ATOM") and line[12:16].strip() == "CA":
                        try:
                            chain = line[21]
                            resnum = int(line[22:26].strip())
                            x = float(line[30:38])
                            y = float(line[38:46])
                            z = float(line[46:54])
                            ca_coords[(chain, resnum)] = np.array([x, y, z])
                        except (ValueError, IndexError):
                            pass

            near_missing = []
            for res in missing_residues:
                chain = res["chain"]
                resnum = res["resnum"]

                # Estimar posición del residuo faltante usando vecinos
                neighbor_coords = []
                for delta in [-1, 1, -2, 2]:
                    key = (chain, resnum + delta)
                    if key in ca_coords:
                        neighbor_coords.append(ca_coords[key])

                if not neighbor_coords:
                    continue

                # Posición estimada = media de vecinos
                estimated_pos = np.mean(neighbor_coords, axis=0)
                dist = np.linalg.norm(estimated_pos - lig_center)

                if dist <= radius:
                    near_missing.append(
                        f"{res['resname']}{chain}{resnum}"
                    )

            return near_missing

        except Exception as e:
            log.warning(
                "completeness_check_error",
                protein=str(protein_path),
                error=str(e),
            )
            return []

    def _check_binding_type(self, cpx: Any, result: AuditResult) -> None:
        """
        Check 4: Solo Ki o Kd (NO IC50, EC50, u otros).

        IC50 depende del ensayo y concentraciones experimentales, no es
        directamente comparable entre estudios. Ki/Kd son constantes
        termodinámicas definidas.
        """
        btype = cpx.binding_type

        if not btype or btype == "unknown":
            result.checks["binding_type"] = False
            result.failures.append("Tipo de binding no determinado")
            return

        if btype not in self._accepted_binding_types:
            result.checks["binding_type"] = False
            result.failures.append(
                f"Tipo de binding '{btype}' no aceptado "
                f"(permitidos: {sorted(self._accepted_binding_types)})"
            )
            return

        result.checks["binding_type"] = True

    def _check_features(
        self,
        cpx: Any,
        feature_extractor: Any,
        result: AuditResult,
    ) -> None:
        """
        Check 5: Features de interacción 3D no triviales.

        Si todas las features 3D son cero, indica un fallo silencioso
        en el parsing de ODDT (conformaciones incompatibles, formato
        incorrecto, etc.). Estos complejos contaminarían el training.
        """
        try:
            # Extraer features usando el extractor (desde archivos PDB/SDF)
            features = feature_extractor.extract_3d_features_from_files(
                protein_path=cpx.protein_pdb_path,
                ligand_path=cpx.ligand_sdf_path,
            )

            if features is None:
                result.checks["features"] = False
                result.failures.append("Extracción de features 3D falló")
                return

            # Contar features no-cero
            n_nonzero = sum(1 for v in features.values() if abs(v) > 1e-10)
            result.n_features_nonzero = n_nonzero
            result.feature_values = features

            if n_nonzero < self._min_nonzero_features:
                result.checks["features"] = False
                result.failures.append(
                    f"Solo {n_nonzero} features 3D no-cero "
                    f"(minimo: {self._min_nonzero_features}) - posible fallo de parsing"
                )
                return

            result.checks["features"] = True

        except Exception as e:
            result.checks["features"] = False
            result.failures.append(f"Error en check de features: {e!s}")

    def audit_all(
        self,
        complexes: list[Any],
        feature_extractor: Any | None = None,
        progress_interval: int = 500,
    ) -> AuditReport:
        """
        Ejecutar auditoría sobre todos los complejos.

        Args:
            complexes: lista de PDBBindComplex
            feature_extractor: FeatureExtractor (opcional)
            progress_interval: cada cuántos complejos logear progreso

        Returns:
            AuditReport con estadísticas completas
        """
        start_time = time.time()
        report = AuditReport()
        report.total_evaluated = len(complexes)

        accepted_pkis = []
        rejected_pkis = []

        for i, cpx in enumerate(complexes):
            result = self.audit_complex(cpx, feature_extractor)
            report.results.append(result)

            # Anotar el complejo
            cpx.audit_passed = result.passed
            cpx.audit_failures = result.failures

            if result.passed:
                report.total_accepted += 1
                if cpx.pki > 0:
                    accepted_pkis.append(cpx.pki)
            else:
                report.total_rejected += 1
                if cpx.pki > 0:
                    rejected_pkis.append(cpx.pki)

                # Contar razones de rechazo
                for failure in result.failures:
                    # Categorizar la razón
                    category = self._categorize_failure(failure)
                    report.rejection_reasons[category] = (
                        report.rejection_reasons.get(category, 0) + 1
                    )
                    if category not in report.rejected_ids:
                        report.rejected_ids[category] = []
                    report.rejected_ids[category].append(cpx.pdb_id)

            if (i + 1) % progress_interval == 0:
                log.info(
                    "audit_progress",
                    processed=i + 1,
                    total=len(complexes),
                    accepted=report.total_accepted,
                    rejected=report.total_rejected,
                )

        # Calcular estadísticas
        if accepted_pkis:
            report.accepted_pki_stats = {
                "mean": round(float(np.mean(accepted_pkis)), 3),
                "std": round(float(np.std(accepted_pkis)), 3),
                "min": round(float(np.min(accepted_pkis)), 3),
                "max": round(float(np.max(accepted_pkis)), 3),
                "median": round(float(np.median(accepted_pkis)), 3),
                "n": len(accepted_pkis),
            }

        if rejected_pkis:
            report.rejected_pki_stats = {
                "mean": round(float(np.mean(rejected_pkis)), 3),
                "std": round(float(np.std(rejected_pkis)), 3),
                "min": round(float(np.min(rejected_pkis)), 3),
                "max": round(float(np.max(rejected_pkis)), 3),
                "median": round(float(np.median(rejected_pkis)), 3),
                "n": len(rejected_pkis),
            }

        report.duration_seconds = round(time.time() - start_time, 2)

        from datetime import datetime, timezone
        report.timestamp = datetime.now(timezone.utc).isoformat()

        log.info(
            "audit_complete",
            total=report.total_evaluated,
            accepted=report.total_accepted,
            rejected=report.total_rejected,
            acceptance_rate=round(
                report.total_accepted / max(report.total_evaluated, 1) * 100, 1
            ),
            duration_s=report.duration_seconds,
        )

        return report

    @staticmethod
    def _categorize_failure(failure: str) -> str:
        """Categorizar un mensaje de fallo en categoría corta."""
        failure_lower = failure.lower()
        if "smiles" in failure_lower or "parseable" in failure_lower:
            return "ligand_unparseable"
        if "exótic" in failure_lower or "átomos" in failure_lower:
            return "exotic_atoms"
        if "mw" in failure_lower or "peso" in failure_lower:
            return "molecular_weight"
        if "fragment" in failure_lower:
            return "multi_fragment"
        if "resolución" in failure_lower or "resolution" in failure_lower:
            return "low_resolution"
        if "completitud" in failure_lower or "faltante" in failure_lower or "missing" in failure_lower:
            return "missing_residues"
        if "binding" in failure_lower or "tipo" in failure_lower:
            return "binding_type"
        if "feature" in failure_lower:
            return "trivial_features"
        return "other"

    @staticmethod
    def save_report(report: AuditReport, output_path: str | Path) -> None:
        """
        Guardar reporte de auditoría en JSON.

        El JSON es legible y revisable manualmente antes de entrenar.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "summary": {
                "total_evaluated": report.total_evaluated,
                "total_accepted": report.total_accepted,
                "total_rejected": report.total_rejected,
                "acceptance_rate_pct": round(
                    report.total_accepted / max(report.total_evaluated, 1) * 100, 1
                ),
                "timestamp": report.timestamp,
                "duration_seconds": report.duration_seconds,
            },
            "rejection_reasons": report.rejection_reasons,
            "rejected_ids_by_reason": {
                k: v[:50] for k, v in report.rejected_ids.items()  # Limitar a 50 por categoría
            },
            "pki_distribution": {
                "accepted": report.accepted_pki_stats,
                "rejected": report.rejected_pki_stats,
            },
            "individual_results": [
                {
                    "pdb_id": r.pdb_id,
                    "passed": r.passed,
                    "checks": r.checks,
                    "failures": r.failures,
                    "warnings": r.warnings,
                }
                for r in report.results
            ],
        }

        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)

        log.info("audit_report_saved", path=str(output_path))


def get_vip_complexes(report: AuditReport) -> list[str]:
    """
    Obtener lista de PDB IDs que pasaron la auditoría.

    Returns:
        Lista de PDB IDs aprobados
    """
    return [r.pdb_id for r in report.results if r.passed]
