"""
core/pipeline_params.py

Snapshot inmutable de parámetros para el pipeline de evaluación.

PROBLEMA QUE RESUELVE:
  El pipeline (tanto run_pipeline en runner.py como _run_full_evaluation_async
  en queue_handler.py) abre una sesión de DB, carga target/molecule como ORM
  entities, y luego accede a sus atributos (target.pdb_id, target.chain, etc.)
  a lo largo de 500+ líneas con commits/flushes intermedios.

  Si algún commit, rollback o cascade expiration detachea el ORM del identity
  map, los accesos subsiguientes disparan DetachedInstanceError:
      Instance <TargetORM at 0x...> is not bound to a Session

  Este dataclass CAPTURA todos los valores necesarios como datos puros al
  inicio del pipeline. Después, las 500+ líneas trabajan exclusivamente
  con PipelineParams — NUNCA contra el ORM.

  Zero ORM access fuera de repository calls. Cero DetachedInstanceError.

Por qué dataclass y no Pydantic:
  - No necesita validación (el ORM ya la hizo).
  - No necesita serialización JSON (va a la API como primer dict anónimo).
  - Menos overhead que Pydantic BaseModel.
  - frozen=True = inmutable. El pipeline nunca puede mutar parámetros.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class PipelineParams:
    """
    Snapshot inmutable capturado al inicio de cada pipeline.

    Construido UNA VEZ desde el ORM (TargetORM + MoleculeORM + user overrides).
    Después, el pipeline solo trabaja contra esta estructura.

    Convención de override:
      - Campos con sufijo _override vienen del usuario (frontend ProOptionsModal).
      - Si son None, prevalece el valor de DB (target.grid_center_x, etc.)
      - Las propiedades computed (effective_*) resuelven la precedencia.
    """

    # ════════════════════════════════════════════════════════════════
    # ── Identidad del target (del ORM, leídos al inicio) ────────
    # ════════════════════════════════════════════════════════════════
    target_pdb_id: str
    target_name: str
    target_chain: str
    #: Doc 71. Las cadenas que FORMAN el sitio, medidas sobre el PDB del RCSB.
    #: `target_chain` dice cuál se declara; ésta dice cuáles hay que conservar
    #: para no acoplar contra media cavidad. `None` en corridas anteriores al
    #: campo: se lee como «una sola», que es el comportamiento histórico.
    target_site_chains: list[str] | None
    target_structural_family: str | None
    target_is_hot: bool

    # ════════════════════════════════════════════════════════════════
    # ── Grid box base (del ORM — coordenadas calibradas) ────────
    # ════════════════════════════════════════════════════════════════
    target_grid_center_x: float
    target_grid_center_y: float
    target_grid_center_z: float
    target_grid_size_x: float
    target_grid_size_y: float
    target_grid_size_z: float
    target_hotspots_base: list[dict[str, Any]]
    target_cofactors_whitelist: list[str]

    # ════════════════════════════════════════════════════════════════
    # ── Identidad de la molécula ─────────────────────────────────
    #   NOTA: sin defaults — deben ir ANTES de los campos opcionales
    #   (dataclass: non-default fields first).
    # ════════════════════════════════════════════════════════════════
    molecule_id: uuid.UUID
    molecule_smiles: str
    molecule_smiles_hash: str

    # ════════════════════════════════════════════════════════════════
    # ── Override del usuario (ProOptionsModal → frontend → params) ─
    #   None = usar valor del ORM. No None = el usuario lo cambió.
    # ════════════════════════════════════════════════════════════════
    grid_center_override: tuple[float, float, float] | None = None
    grid_size_override: tuple[float, float, float] | None = None
    custom_hotspots: list[str] | None = None
    peptide_docking_engine: str | None = None
    docking_engine: str = "vina"
    enable_selectivity: bool = False
    selected_anti_targets: list[str] = field(default_factory=list)

    # ════════════════════════════════════════════════════════════════
    # ── Recursos/hardware del PRO (ProOptionsModal → advancedOpts) ─
    # ════════════════════════════════════════════════════════════════
    num_workers: int | None = None        # pro_workers: cuántos anti-targets en paralelo
    parallel_docks: int | None = None     # pro_parallel_docks: docks concurrentes
    gnn_precision: str | None = None      # "fp32" | "fp16" (RTMScore GNN)

    # ════════════════════════════════════════════════════════════════
    # ── Thresholds cuánticos del target ──────────────────────────
    # ════════════════════════════════════════════════════════════════
    affinity_threshold: float = -7.5
    specificity_floor: float = 0.5

    is_control: bool = False

    # ════════════════════════════════════════════════════════════════
    # ── Pipeline config raw (del frontend, enterito) ─────────────
    #   Pasa directo a scoring_engine y demás si se necesita.
    # ════════════════════════════════════════════════════════════════
    pipeline_config_raw: dict[str, Any] | None = None

    # ════════════════════════════════════════════════════════════════
    # ── MM-GBSA (del usuario, toggle en ProOptions) ──────────────
    # ════════════════════════════════════════════════════════════════
    mmgbsa_enabled: bool = False
    mmgbsa_steps: int = 1000

    # ════════════════════════════════════════════════════════════════
    # ── Spearman rho (opcional, para metadatos) ─────────────────
    # ════════════════════════════════════════════════════════════════
    target_spearman_rho: float | None = None

    # ════════════════════════════════════════════════════════════════
    # ── Propiedades computadas (resuelven override vs base) ──────
    # ════════════════════════════════════════════════════════════════

    @property
    def effective_grid_center(self) -> tuple[float, float, float]:
        """
        Centro del grid box que se usará en docking.

        User override (grid_center_override) gana sobre DB (target_grid_center_*).
        """
        if self.grid_center_override is not None:
            return self.grid_center_override
        return (
            self.target_grid_center_x,
            self.target_grid_center_y,
            self.target_grid_center_z,
        )

    @property
    def effective_grid_size(self) -> tuple[float, float, float]:
        """
        Tamaño del grid box que se usará usar.

        User override (grid_size_override) gana sobre DB (target_grid_size_*).
        """
        if self.grid_size_override is not None:
            return self.grid_size_override
        return (
            self.target_grid_size_x,
            self.target_grid_size_y,
            self.target_grid_size_z,
        )

    @property
    def effective_hotspots(self) -> list[dict[str, Any]]:
        """
        Residuos activos para la simulación de docking.

        Si el usuario seleccionó un subconjunto, devuelve ESE subconjunto con
        los `importance` values de los hotspots base (si no existen, default 1.0).
        Si no, devuelve todos los del target (base).
        """
        if self.custom_hotspots:
            hotspot_map: dict[str, float] = {
                h["name"]: h.get("importance", 1.0)
                for h in self.target_hotspots_base
            }
            return [
                {"name": h_name, "importance": hotspot_map.get(h_name, 1.0)}
                for h_name in self.custom_hotspots
            ]
        return self.target_hotspots_base

    # ════════════════════════════════════════════════════════════════
    # ── Constructor de fábrica — from ORM + overrides ────────
    # ════════════════════════════════════════════════════════════════

    @classmethod
    def from_orm(
        cls,
        *,
        # ── ORM entities (se leen solo para construir el snapshot) ──
        target_pdb_id: str,
        target_name: str,
        target_chain: str,
        target_structural_family: str | None,
        target_is_hot: bool,
        target_grid_center_x: float,
        target_grid_center_y: float,
        target_grid_center_z: float,
        target_grid_size_x: float,
        target_grid_size_y: float,
        target_grid_size_z: float,
        target_hotspots_base: list[dict[str, Any]],
        target_cofactors_whitelist: list[str],
        affinity_threshold: float | None,
        specificity_floor: float,
        target_spearman_rho: float | None,
        # ── Molecule ────────────────────────────────────
        molecule_id: uuid.UUID,
        molecule_smiles: str,
        molecule_smiles_hash: str,
        is_control: bool,
        # ── User overrides ──────────────────────────────────
        grid_center_override: tuple[float, float, float] | None = None,
        grid_size_override: tuple[float, float, float] | None = None,
        custom_hotspots: list[str] | None = None,
        peptide_docking_engine: str | None = None,
        docking_engine: str = "vina",
        enable_selectivity: bool = False,
        target_site_chains: list[str] | None = None,
        selected_anti_targets: list[str] | None = None,
        num_workers: int | None = None,
        parallel_docks: int | None = None,
        gnn_precision: str | None = None,
        mmgbsa_enabled: bool = False,
        mmgbsa_steps: int = 1000,
        pipeline_config_raw: dict[str, Any] | None = None,
    ) -> "PipelineParams":
        return cls(
            target_pdb_id=target_pdb_id,
            target_name=target_name,
            target_chain=target_chain,
            target_site_chains=target_site_chains,
            target_structural_family=target_structural_family,
            target_is_hot=target_is_hot,
            target_grid_center_x=target_grid_center_x,
            target_grid_center_y=target_grid_center_y,
            target_grid_center_z=target_grid_center_z,
            target_grid_size_x=target_grid_size_x,
            target_grid_size_y=target_grid_size_y,
            target_grid_size_z=target_grid_size_z,
            target_hotspots_base=target_hotspots_base,
            target_cofactors_whitelist=target_cofactors_whitelist,
            molecule_id=molecule_id,
            molecule_smiles=molecule_smiles,
            molecule_smiles_hash=molecule_smiles_hash,
            grid_center_override=grid_center_override,
            grid_size_override=grid_size_override,
            custom_hotspots=custom_hotspots,
            peptide_docking_engine=peptide_docking_engine,
            docking_engine=docking_engine,
            enable_selectivity=enable_selectivity,
            selected_anti_targets=selected_anti_targets or [],
            num_workers=num_workers,
            parallel_docks=parallel_docks,
            gnn_precision=gnn_precision,
            affinity_threshold=affinity_threshold,
            specificity_floor=specificity_floor,
            is_control=is_control,
            target_spearman_rho=target_spearman_rho,
            pipeline_config_raw=pipeline_config_raw,
            mmgbsa_enabled=mmgbsa_enabled,
            mmgbsa_steps=mmgbsa_steps,
        )
