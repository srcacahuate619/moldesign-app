"""
rescoring/data_curator.py

Curacion de datos pre-entrenamiento para PDBbind.

Ejecuta ANTES del VIP audit (vip_audit.py). El VIP audit valida calidad
individual de cada complejo (resolucion, SMILES, features 3D). Este modulo
opera a nivel de DATASET: filtra ruido sistematico, datos dudosos y
duplicados que contaminarian el training del ML.

Filosofia: Es mejor entrenar con 8,000 datos limpios que con 19,000
datos donde 5,000 son ruido. El ML no puede distinguir "ruido de medicion"
de "señal biologica real" — esa responsabilidad es nuestra.

Filtros implementados (en orden de ejecucion):
  1. Precision de binding   → Solo datos con operador "=" (medicion directa)
  2. Tipo de binding        → Solo Ki o Kd (constantes termodinamicas)
  3. Rango de afinidad      → pKi entre 2.0 y 13.0
  4. Resolucion pre-filtro  → ≤ 3.0 A (VIP audit tightens to ≤ 2.5 A)
  5. Archivos estructurales → Proteina PDB + ligando SDF deben existir
  6. Archivos no vacios     → Verificar que PDB/SDF no estan truncados
  7. Deduplicacion          → Si PDB ID aparece en refined Y other, mantener refined
  8. Outliers estadisticos  → pKi con |z-score| > 4σ respecto al dataset

Justificacion cientifica de cada filtro:

  Filtro 1 (Precision): Los valores con ~ son estimaciones de la literatura
  que PDBbind recopilo pero que NO tienen medicion experimental precisa.
  Los valores con > o < son limites de deteccion del ensayo, no valores reales.
  Incluirlos enseña al ML a predecir "rangos" como si fueran "puntos",
  degradando la calibracion del modelo.

  Filtro 2 (Tipo): IC50 depende de condiciones experimentales (concentracion
  de sustrato, tipo de ensayo). Dos IC50 del mismo compuesto en ensayos
  diferentes pueden diferir 10-100x. Ki y Kd son constantes termodinamicas
  intrinsecas — comparables entre estudios. (Ref: Kalliokoski et al., PLoS ONE 2013)

  Filtro 3 (Rango): pKi < 2.0 (Kd > 10 mM) no es union real — es interaccion
  inespecifica o artefacto. pKi > 13.0 (Kd < 0.1 pM) es sub-picomolar — solo
  un puñado de compuestos reales logran esto, y la mayoria de estos valores
  son errores de conversion de unidades en la literatura.

  Filtro 4 (Resolucion): Pre-filtro generoso a 3.0 A. Complementa el VIP audit
  que aplica ≤ 2.5 A. Este paso elimina tempranamente estructuras NMR (sin
  resolucion) y estructuras de muy baja resolucion de cryo-EM.

  Filtro 5-6 (Archivos): Complejos sin archivos de estructura son inutiles para
  feature extraction 3D. Archivos vacios (<100 bytes para PDB, <50 bytes para SDF)
  indican descarga corrupta o estructura problematica.

  Filtro 7 (Deduplicacion): PDBbind puede tener el mismo PDB ID en refined y
  other sets. El refined tiene mejor curacion → prioridad.

  Filtro 8 (Outliers): Un valor de afinidad a > 4σ de la media del dataset
  es probablemente un error de entrada, conversion de unidades, o condicion
  experimental anomala. Eliminarlos previene que el ML ajuste a estos puntos
  extremos y distorsione predicciones para complejos normales.

Output: artifacts/data_curation_report.json
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from logger import get_logger

log = get_logger(__name__)


# ─── Configuracion de filtros ───────────────────────────────────

# Tipos de binding aceptados para training de ML
ACCEPTED_BINDING_TYPES = {"Ki", "Kd"}

# Solo datos con medicion exacta (operador =)
ACCEPTED_PRECISIONS = {"exact"}

# Rango de pKi aceptable
# pKi < 2.0 → Kd > 10 mM (interaccion inespecifica)
# pKi > 13.0 → Kd < 0.1 pM (probablemente error)
PKI_MIN = 2.0
PKI_MAX = 13.0

# Resolucion maxima pre-filtro (A)
# Mas generoso que VIP audit (2.5 A) — este paso elimina lo peor temprano
MAX_RESOLUTION_PREFILTER = 3.0

# Tamaño minimo de archivos (bytes) para considerar que no estan corruptos
MIN_PDB_SIZE_BYTES = 100
MIN_SDF_SIZE_BYTES = 50

# Umbral de z-score para deteccion de outliers
OUTLIER_ZSCORE_THRESHOLD = 4.0


@dataclass
class CurationFilter:
    """Resultado de un filtro individual."""
    name: str
    description: str
    n_before: int = 0
    n_after: int = 0
    n_removed: int = 0
    removed_ids: list[str] = field(default_factory=list)
    # Solo guardar primeros 100 IDs removidos (para reportes manejables)
    max_removed_ids: int = 100


@dataclass
class CurationReport:
    """Reporte completo de curacion de datos."""
    # Input
    n_input_total: int = 0
    n_input_refined: int = 0
    n_input_other: int = 0
    # Output
    n_output: int = 0
    # Filtros aplicados en orden
    filters: list[CurationFilter] = field(default_factory=list)
    # Resumen
    overall_removal_rate_pct: float = 0.0
    # Distribucion de pKi despues de curacion
    pki_stats_curated: dict[str, float] = field(default_factory=dict)
    # Metadata
    timestamp: str = ""
    duration_seconds: float = 0.0
    config: dict[str, Any] = field(default_factory=dict)


class DataCurator:
    """
    Curador de datos pre-entrenamiento para PDBbind.

    Aplica filtros de calidad secuenciales para eliminar ruido sistematico
    antes de que el VIP audit (vip_audit.py) valide calidad individual.

    Uso:
        from data_curator import DataCurator
        curator = DataCurator()
        curated, report = curator.curate(parser.complexes)
        curator.save_report(report, "artifacts/data_curation_report.json")

    Despues de curar:
        → Pasar `curated` al VIP audit para validacion individual
        → El VIP audit aplicara checks de ligando, resolucion ≤2.5A, etc.
    """

    def __init__(
        self,
        accepted_binding_types: set[str] | None = None,
        accepted_precisions: set[str] | None = None,
        pki_min: float = PKI_MIN,
        pki_max: float = PKI_MAX,
        max_resolution: float = MAX_RESOLUTION_PREFILTER,
        outlier_zscore: float = OUTLIER_ZSCORE_THRESHOLD,
        min_pdb_size: int = MIN_PDB_SIZE_BYTES,
        min_sdf_size: int = MIN_SDF_SIZE_BYTES,
    ):
        self._accepted_binding_types = accepted_binding_types or ACCEPTED_BINDING_TYPES
        self._accepted_precisions = accepted_precisions or ACCEPTED_PRECISIONS
        self._pki_min = pki_min
        self._pki_max = pki_max
        self._max_resolution = max_resolution
        self._outlier_zscore = outlier_zscore
        self._min_pdb_size = min_pdb_size
        self._min_sdf_size = min_sdf_size

    def curate(
        self, complexes: list[Any]
    ) -> tuple[list[Any], CurationReport]:
        """
        Aplicar todos los filtros de curacion en secuencia.

        Args:
            complexes: lista de PDBBindComplex del parser

        Returns:
            (complejos_curados, reporte)
        """
        start_time = time.time()
        report = CurationReport()
        report.n_input_total = len(complexes)
        report.n_input_refined = sum(
            1 for c in complexes if c.source_set == "refined"
        )
        report.n_input_other = sum(
            1 for c in complexes if c.source_set == "other"
        )
        report.config = {
            "accepted_binding_types": sorted(self._accepted_binding_types),
            "accepted_precisions": sorted(self._accepted_precisions),
            "pki_range": [self._pki_min, self._pki_max],
            "max_resolution_prefilter": self._max_resolution,
            "outlier_zscore_threshold": self._outlier_zscore,
            "min_pdb_size_bytes": self._min_pdb_size,
            "min_sdf_size_bytes": self._min_sdf_size,
        }

        current = list(complexes)

        # ─── Filtro 1: Precision de binding ───
        current = self._filter_precision(current, report)

        # ─── Filtro 2: Tipo de binding ───
        current = self._filter_binding_type(current, report)

        # ─── Filtro 3: Rango de afinidad ───
        current = self._filter_affinity_range(current, report)

        # ─── Filtro 4: Resolucion pre-filtro ───
        current = self._filter_resolution(current, report)

        # ─── Filtro 5: Archivos estructurales existentes ───
        current = self._filter_structural_files(current, report)

        # ─── Filtro 6: Archivos no vacios ───
        current = self._filter_file_sizes(current, report)

        # ─── Filtro 7: Deduplicacion refined > other ───
        current = self._deduplicate(current, report)

        # ─── Filtro 8: Outliers estadisticos ───
        current = self._filter_outliers(current, report)

        # ─── Calcular estadisticas finales ───
        report.n_output = len(current)
        report.overall_removal_rate_pct = round(
            (1 - len(current) / max(len(complexes), 1)) * 100, 1
        )

        pkis = [c.pki for c in current if c.pki > 0]
        if pkis:
            arr = np.array(pkis)
            report.pki_stats_curated = {
                "n": len(pkis),
                "mean": round(float(np.mean(arr)), 3),
                "std": round(float(np.std(arr)), 3),
                "min": round(float(np.min(arr)), 3),
                "max": round(float(np.max(arr)), 3),
                "median": round(float(np.median(arr)), 3),
                "q25": round(float(np.percentile(arr, 25)), 3),
                "q75": round(float(np.percentile(arr, 75)), 3),
            }

        report.duration_seconds = round(time.time() - start_time, 2)
        report.timestamp = datetime.now(timezone.utc).isoformat()

        log.info(
            "data_curation_complete",
            input=len(complexes),
            output=len(current),
            removed=len(complexes) - len(current),
            removal_rate_pct=report.overall_removal_rate_pct,
            duration_s=report.duration_seconds,
        )

        return current, report

    # ─── Filtros individuales ───────────────────────────────────

    def _filter_precision(
        self, complexes: list[Any], report: CurationReport
    ) -> list[Any]:
        """
        Filtro 1: Solo datos con binding exacto (operador =).

        Rechaza: ~ (aproximado), > (limite inferior), < (limite superior).
        Razon: Los valores aproximados o bounded no son mediciones reales.
        Entrenar con ellos enseña al ML que un "rango" es un "punto",
        degradando la calibracion del modelo de forma silenciosa.
        """
        f = CurationFilter(
            name="binding_precision",
            description=(
                "Solo datos de binding exactos (operador '='). "
                "Rechaza valores aproximados (~), limites inferiores (>), "
                "y limites superiores (<)."
            ),
            n_before=len(complexes),
        )

        kept = []
        for cpx in complexes:
            if cpx.binding_precision in self._accepted_precisions:
                kept.append(cpx)
            else:
                if len(f.removed_ids) < f.max_removed_ids:
                    f.removed_ids.append(
                        f"{cpx.pdb_id} ({cpx.binding_precision}: {cpx.binding_data_raw})"
                    )

        f.n_after = len(kept)
        f.n_removed = f.n_before - f.n_after
        report.filters.append(f)

        if f.n_removed > 0:
            log.info(
                "curation_filter_precision",
                removed=f.n_removed,
                remaining=f.n_after,
                msg=f"Eliminados {f.n_removed} complejos con datos de binding no exactos",
            )

        return kept

    def _filter_binding_type(
        self, complexes: list[Any], report: CurationReport
    ) -> list[Any]:
        """
        Filtro 2: Solo Ki o Kd.

        Rechaza: IC50, EC50, otros.
        Razon: IC50 depende del ensayo experimental. Dos IC50 del mismo
        compuesto medidos con diferente concentracion de sustrato pueden
        diferir 10-100x. Ki y Kd son constantes termodinamicas definidas.
        Ref: Kalliokoski et al., PLoS ONE 2013.
        """
        f = CurationFilter(
            name="binding_type",
            description=(
                f"Solo tipos de binding aceptados: {sorted(self._accepted_binding_types)}. "
                "IC50/EC50 no son comparables entre estudios."
            ),
            n_before=len(complexes),
        )

        kept = []
        for cpx in complexes:
            if cpx.binding_type in self._accepted_binding_types:
                kept.append(cpx)
            else:
                if len(f.removed_ids) < f.max_removed_ids:
                    f.removed_ids.append(
                        f"{cpx.pdb_id} (tipo: {cpx.binding_type})"
                    )

        f.n_after = len(kept)
        f.n_removed = f.n_before - f.n_after
        report.filters.append(f)

        if f.n_removed > 0:
            log.info(
                "curation_filter_binding_type",
                removed=f.n_removed,
                remaining=f.n_after,
            )

        return kept

    def _filter_affinity_range(
        self, complexes: list[Any], report: CurationReport
    ) -> list[Any]:
        """
        Filtro 3: pKi debe estar en [2.0, 13.0].

        Rechaza extremos:
        - pKi < 2.0 (Kd > 10 mM): interaccion inespecifica, no union real.
          A estas concentraciones, la mayoria de moleculas organicas muestran
          alguna "union" por efectos hidrofobicos inespecificos.
        - pKi > 13.0 (Kd < 0.1 pM): sub-picomolar. Solo ~10 compuestos
          conocidos logran esto. La gran mayoria de valores pKi > 13 son
          errores de conversion de unidades en la literatura original.
        """
        f = CurationFilter(
            name="affinity_range",
            description=(
                f"pKi debe estar en [{self._pki_min}, {self._pki_max}]. "
                "Fuera de rango = interaccion inespecifica o error de dato."
            ),
            n_before=len(complexes),
        )

        kept = []
        for cpx in complexes:
            if cpx.pki <= 0:
                # No se pudo parsear → rechazar
                if len(f.removed_ids) < f.max_removed_ids:
                    f.removed_ids.append(f"{cpx.pdb_id} (pKi=0, no parseable)")
                continue

            if self._pki_min <= cpx.pki <= self._pki_max:
                kept.append(cpx)
            else:
                if len(f.removed_ids) < f.max_removed_ids:
                    f.removed_ids.append(
                        f"{cpx.pdb_id} (pKi={cpx.pki:.2f}, Kd={cpx.binding_value_nm:.1f} nM)"
                    )

        f.n_after = len(kept)
        f.n_removed = f.n_before - f.n_after
        report.filters.append(f)

        if f.n_removed > 0:
            log.info(
                "curation_filter_affinity_range",
                removed=f.n_removed,
                remaining=f.n_after,
            )

        return kept

    def _filter_resolution(
        self, complexes: list[Any], report: CurationReport
    ) -> list[Any]:
        """
        Filtro 4: Resolucion cristalografica ≤ 3.0 A.

        Pre-filtro generoso. El VIP audit posterior aplica ≤ 2.5 A.
        Este paso elimina tempranamente:
        - Estructuras NMR (resolucion = 0 o no reportada)
        - Cryo-EM de baja resolucion (> 3.0 A)
        - Entradas sin resolucion reportada

        Nota: Si la resolucion no esta disponible (= 0), el complejo se rechaza.
        Sin resolucion no hay forma de evaluar la confiabilidad de las coordenadas
        atomicas que el ML usara para features 3D.
        """
        f = CurationFilter(
            name="resolution_prefilter",
            description=(
                f"Resolucion cristalografica > 0 y ≤ {self._max_resolution} A. "
                "Elimina NMR, cryo-EM baja resolucion, y entradas sin metadatos."
            ),
            n_before=len(complexes),
        )

        kept = []
        for cpx in complexes:
            if 0 < cpx.resolution <= self._max_resolution:
                kept.append(cpx)
            else:
                if len(f.removed_ids) < f.max_removed_ids:
                    reason = (
                        "sin resolucion"
                        if cpx.resolution <= 0
                        else f"resolucion={cpx.resolution:.2f}A"
                    )
                    f.removed_ids.append(f"{cpx.pdb_id} ({reason})")

        f.n_after = len(kept)
        f.n_removed = f.n_before - f.n_after
        report.filters.append(f)

        if f.n_removed > 0:
            log.info(
                "curation_filter_resolution",
                removed=f.n_removed,
                remaining=f.n_after,
            )

        return kept

    def _filter_structural_files(
        self, complexes: list[Any], report: CurationReport
    ) -> list[Any]:
        """
        Filtro 5: Deben existir proteina PDB y ligando SDF.

        Sin archivos de estructura, no se pueden extraer features 3D
        (interacciones proteina-ligando). Estos complejos serian inutiles
        para el pipeline de entrenamiento.
        """
        f = CurationFilter(
            name="structural_files_exist",
            description=(
                "Proteina PDB y ligando SDF deben existir en disco."
            ),
            n_before=len(complexes),
        )

        kept = []
        for cpx in complexes:
            has_protein = cpx.protein_pdb_path and Path(cpx.protein_pdb_path).exists()
            has_ligand = (
                (cpx.ligand_sdf_path and Path(cpx.ligand_sdf_path).exists())
                or (cpx.ligand_mol2_path and Path(cpx.ligand_mol2_path).exists())
            )

            if has_protein and has_ligand:
                kept.append(cpx)
            else:
                if len(f.removed_ids) < f.max_removed_ids:
                    missing = []
                    if not has_protein:
                        missing.append("protein_pdb")
                    if not has_ligand:
                        missing.append("ligand_sdf/mol2")
                    f.removed_ids.append(
                        f"{cpx.pdb_id} (faltan: {', '.join(missing)})"
                    )

        f.n_after = len(kept)
        f.n_removed = f.n_before - f.n_after
        report.filters.append(f)

        if f.n_removed > 0:
            log.info(
                "curation_filter_structural_files",
                removed=f.n_removed,
                remaining=f.n_after,
            )

        return kept

    def _filter_file_sizes(
        self, complexes: list[Any], report: CurationReport
    ) -> list[Any]:
        """
        Filtro 6: Archivos PDB y SDF no deben estar vacios o truncados.

        Un PDB de menos de 100 bytes no puede contener una proteina real.
        Un SDF de menos de 50 bytes no puede contener un ligando real.
        Estos son indicadores de descarga corrupta o estructura problematica.
        """
        f = CurationFilter(
            name="file_sizes",
            description=(
                f"PDB >= {self._min_pdb_size} bytes, "
                f"SDF >= {self._min_sdf_size} bytes. "
                "Detecta archivos truncados o corruptos."
            ),
            n_before=len(complexes),
        )

        kept = []
        for cpx in complexes:
            try:
                pdb_ok = True
                sdf_ok = True

                if cpx.protein_pdb_path:
                    pdb_size = os.path.getsize(cpx.protein_pdb_path)
                    if pdb_size < self._min_pdb_size:
                        pdb_ok = False

                ligand_path = cpx.ligand_sdf_path or cpx.ligand_mol2_path
                if ligand_path:
                    sdf_size = os.path.getsize(ligand_path)
                    if sdf_size < self._min_sdf_size:
                        sdf_ok = False

                if pdb_ok and sdf_ok:
                    kept.append(cpx)
                else:
                    if len(f.removed_ids) < f.max_removed_ids:
                        issues = []
                        if not pdb_ok:
                            issues.append(f"PDB={pdb_size}B")
                        if not sdf_ok:
                            issues.append(f"SDF={sdf_size}B")
                        f.removed_ids.append(
                            f"{cpx.pdb_id} (truncado: {', '.join(issues)})"
                        )
            except OSError as e:
                # Error al leer tamano de archivo → rechazar
                if len(f.removed_ids) < f.max_removed_ids:
                    f.removed_ids.append(f"{cpx.pdb_id} (OS error: {e})")

        f.n_after = len(kept)
        f.n_removed = f.n_before - f.n_after
        report.filters.append(f)

        if f.n_removed > 0:
            log.info(
                "curation_filter_file_sizes",
                removed=f.n_removed,
                remaining=f.n_after,
            )

        return kept

    def _deduplicate(
        self, complexes: list[Any], report: CurationReport
    ) -> list[Any]:
        """
        Filtro 7: Deduplicacion refined > other.

        Si el mismo PDB ID aparece tanto en refined como en other,
        mantener solo la version refined (mejor curacion).

        Adicionalmente, si hay PDB IDs duplicados dentro del mismo set,
        mantener el primero encontrado.
        """
        f = CurationFilter(
            name="deduplication",
            description=(
                "Eliminar PDB IDs duplicados. Si un ID esta en refined y other, "
                "priorizar refined (mejor curacion)."
            ),
            n_before=len(complexes),
        )

        # Primero: separar por source_set para priorizar refined
        refined_ids: set[str] = set()
        seen_ids: set[str] = set()
        kept = []

        # Primer paso: identificar todos los IDs del refined set
        for cpx in complexes:
            if cpx.source_set == "refined":
                refined_ids.add(cpx.pdb_id)

        # Segundo paso: iterar manteniendo prioridad refined > other
        for cpx in complexes:
            pdb_id = cpx.pdb_id

            if pdb_id in seen_ids:
                # Ya vimos este ID → skip (duplicado)
                if len(f.removed_ids) < f.max_removed_ids:
                    f.removed_ids.append(
                        f"{pdb_id} (duplicado, set={cpx.source_set})"
                    )
                continue

            if cpx.source_set == "other" and pdb_id in refined_ids:
                # Esta en other pero tambien en refined → skip other
                if len(f.removed_ids) < f.max_removed_ids:
                    f.removed_ids.append(
                        f"{pdb_id} (other descartado, existe en refined)"
                    )
                continue

            seen_ids.add(pdb_id)
            kept.append(cpx)

        f.n_after = len(kept)
        f.n_removed = f.n_before - f.n_after
        report.filters.append(f)

        if f.n_removed > 0:
            log.info(
                "curation_filter_dedup",
                removed=f.n_removed,
                remaining=f.n_after,
            )

        return kept

    def _filter_outliers(
        self, complexes: list[Any], report: CurationReport
    ) -> list[Any]:
        """
        Filtro 8: Detectar outliers estadisticos de afinidad.

        Un pKi con |z-score| > 4σ respecto a la distribucion global
        es probablemente un error de entrada, conversion de unidades,
        o condicion experimental anomala.

        Ejemplo: Si la media del dataset es pKi=7.0 y σ=2.0,
        un complejo con pKi=15.5 tiene z-score = (15.5-7.0)/2.0 = 4.25
        → se rechaza.

        Nota: Usamos z-score global, no por target, porque no todos los
        targets tienen suficientes complejos para una estadistica local
        robusta. Para el caso por familia, el train_orchestrator puede
        agregar filtros adicionales post-curacion.
        """
        f = CurationFilter(
            name="pki_outliers",
            description=(
                f"Detectar valores pKi con |z-score| > {self._outlier_zscore}σ "
                "respecto a la distribucion global del dataset."
            ),
            n_before=len(complexes),
        )

        if len(complexes) < 10:
            # Dataset muy pequeño — no tiene sentido aplicar z-score
            f.n_after = len(complexes)
            f.n_removed = 0
            report.filters.append(f)
            return complexes

        pkis = np.array([c.pki for c in complexes])
        mean_pki = np.mean(pkis)
        std_pki = np.std(pkis)

        if std_pki < 0.01:
            # Desviacion casi nula — no tiene sentido filtrar
            f.n_after = len(complexes)
            f.n_removed = 0
            report.filters.append(f)
            return complexes

        kept = []
        for cpx in complexes:
            z = abs(cpx.pki - mean_pki) / std_pki
            if z <= self._outlier_zscore:
                kept.append(cpx)
            else:
                if len(f.removed_ids) < f.max_removed_ids:
                    f.removed_ids.append(
                        f"{cpx.pdb_id} (pKi={cpx.pki:.2f}, z={z:.2f}σ)"
                    )

        f.n_after = len(kept)
        f.n_removed = f.n_before - f.n_after
        report.filters.append(f)

        if f.n_removed > 0:
            log.info(
                "curation_filter_outliers",
                removed=f.n_removed,
                remaining=f.n_after,
                mean_pki=round(float(mean_pki), 2),
                std_pki=round(float(std_pki), 2),
                threshold=self._outlier_zscore,
            )

        return kept

    # ─── Utilidades ─────────────────────────────────────────────

    @staticmethod
    def save_report(report: CurationReport, output_path: str | Path) -> None:
        """
        Guardar reporte de curacion en JSON para revision manual.

        El reporte es intencionalmente verbose: cada filtro muestra cuantos
        complejos elimino y por que. Un cientifico debe poder auditar
        que la curacion no elimino datos valiosos ni introdujo sesgos.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "summary": {
                "input_total": report.n_input_total,
                "input_refined": report.n_input_refined,
                "input_other": report.n_input_other,
                "output_curated": report.n_output,
                "overall_removal_rate_pct": report.overall_removal_rate_pct,
                "timestamp": report.timestamp,
                "duration_seconds": report.duration_seconds,
            },
            "config": report.config,
            "filters": [
                {
                    "name": f.name,
                    "description": f.description,
                    "n_before": f.n_before,
                    "n_after": f.n_after,
                    "n_removed": f.n_removed,
                    "removed_sample": f.removed_ids[:50],
                }
                for f in report.filters
            ],
            "pki_distribution_after_curation": report.pki_stats_curated,
        }

        with open(output_path, "w", encoding="utf-8") as fp:
            json.dump(data, fp, indent=2, ensure_ascii=False)

        log.info("curation_report_saved", path=str(output_path))

    @staticmethod
    def print_summary(report: CurationReport) -> None:
        """Imprimir resumen legible de la curacion."""
        print("\n" + "=" * 70)
        print("  REPORTE DE CURACION DE DATOS - PDBbind")
        print("=" * 70)
        print(
            f"\n  Input:  {report.n_input_total} complejos "
            f"(refined={report.n_input_refined}, other={report.n_input_other})"
        )
        print(f"  Output: {report.n_output} complejos curados")
        print(
            f"  Eliminados: {report.n_input_total - report.n_output} "
            f"({report.overall_removal_rate_pct}%)"
        )
        print()

        for f in report.filters:
            status = "OK" if f.n_removed == 0 else f"X -{f.n_removed}"
            print(f"  [{status:>8}]  {f.name}: {f.n_before} -> {f.n_after}")

        if report.pki_stats_curated:
            s = report.pki_stats_curated
            print(f"\n  pKi curado: media={s.get('mean', '?')}, "
                  f"std={s.get('std', '?')}, "
                  f"rango=[{s.get('min', '?')}, {s.get('max', '?')}]")

        print(f"\n  Duracion: {report.duration_seconds}s")
        print("=" * 70 + "\n")
