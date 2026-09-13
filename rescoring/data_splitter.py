"""
rescoring/data_splitter.py

Lógica de partición de datos para entrenamiento ML.

Implementa:
  1. Scaffold-split cross-validation (Bemis-Murcko scaffolds)
  2. Frozen test set (~500 complejos representativos de todas las familias)
  3. LTR ranking groups (complejos agrupados por target/proteína)

El scaffold-split es OBLIGATORIO per ML_RESCORING_ARCHITECTURE.md.
Random split sobreestima performance porque moléculas de la misma serie
caen en train y test → "memory leak".

Referencia: Yang et al., "Analyzing Learned Molecular Representations
for Property Prediction", J Chem Inf Model 2019.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from logger import get_logger

log = get_logger(__name__)


@dataclass
class DataSplit:
    """Un split de datos con IDs train/val/test."""
    train_ids: list[str]
    val_ids: list[str]
    test_ids: list[str]
    # Metadata
    split_method: str = ""
    n_train: int = 0
    n_val: int = 0
    n_test: int = 0
    fold: int = 0  # Para CV
    scaffold_groups: dict[str, list[str]] | None = None

    def __post_init__(self):
        self.n_train = len(self.train_ids)
        self.n_val = len(self.val_ids)
        self.n_test = len(self.test_ids)


@dataclass
class LTRGroup:
    """
    Grupo de ranking para Learning-to-Rank.

    En XGBoost rank:pairwise, cada grupo contiene ligandos del MISMO target
    que se comparan entre sí. No tiene sentido comparar afinidad de
    un inhibidor de kinasa contra un agonista de GPCR.
    """
    group_id: str  # PDB ID del target o UniProt ID
    pdb_ids: list[str] = field(default_factory=list)
    pkis: list[float] = field(default_factory=list)
    n_members: int = 0


def get_bemis_murcko_scaffold(smiles: str) -> str:
    """
    Obtener scaffold Bemis-Murcko de un SMILES.

    El scaffold reduce la molécula a su esqueleto de anillos + linkers.
    Moléculas con el mismo scaffold son de la misma "serie química".

    Returns:
        SMILES canónico del scaffold, o hash del SMILES si falla
    """
    try:
        from rdkit import Chem
        from rdkit.Chem.Scaffolds import MurckoScaffold

        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            # Fallback: usar hash del SMILES como "scaffold único"
            return f"UNPARSEABLE_{hashlib.md5(smiles.encode()).hexdigest()[:8]}"

        scaffold = MurckoScaffold.GetScaffoldForMol(mol)
        scaffold_smiles = Chem.MolToSmiles(scaffold)

        if not scaffold_smiles:
            # Molécula sin anillos → scaffold vacío
            # Agrupar todos los acíclicos juntos sería incorrecto
            # Cada uno es su propio "scaffold"
            return f"ACYCLIC_{hashlib.md5(smiles.encode()).hexdigest()[:8]}"

        return scaffold_smiles

    except Exception:
        return f"ERROR_{hashlib.md5(smiles.encode()).hexdigest()[:8]}"


def group_by_scaffold(
    complexes: list[Any],
) -> dict[str, list[str]]:
    """
    Agrupar complejos por scaffold Bemis-Murcko.

    Args:
        complexes: PDBBindComplex con ligand_smiles

    Returns:
        {scaffold_smiles: [pdb_id, ...]}
    """
    scaffold_groups: dict[str, list[str]] = defaultdict(list)

    for cpx in complexes:
        scaffold = get_bemis_murcko_scaffold(cpx.ligand_smiles)
        scaffold_groups[scaffold].append(cpx.pdb_id)

    log.info(
        "scaffold_grouping",
        n_complexes=sum(len(v) for v in scaffold_groups.values()),
        n_scaffolds=len(scaffold_groups),
        largest_group=max(len(v) for v in scaffold_groups.values()) if scaffold_groups else 0,
        singletons=sum(1 for v in scaffold_groups.values() if len(v) == 1),
    )

    return dict(scaffold_groups)


HOLDOUT_SELECTION_METHOD = "scaffold_disjoint_stratified"


def create_frozen_test_set(
    complexes: list[Any],
    family_classifications: dict[str, Any],
    test_size: int = 500,
    seed: int = 42,
) -> list[str]:
    """
    Crear test set congelado, representativo de todas las familias.

    Garantías (v2 — A1 scaffold-disjoint):
    - SCAFFOLD-DISJOINT: la unidad de selección es el scaffold Bemis-Murcko
      COMPLETO. Si un scaffold entra al holdout, TODOS sus complejos entran.
      Así NINGÚN scaffold compartido puede filtrar información train→test:
      el train nunca ve moléculas de la misma serie química del holdout.
    - Representación proporcional de cada familia estructural
    - Mínimo 10 complejos por familia (si hay suficientes)
    - Estratificación aproximada de pKi (orden por pKi medio del scaffold)
    - Determinístico (mismo seed → mismo split)
    - El split resultante A1 es 100% verificable: verificar_con márgenes
      mediante `verify_scaffold_disjoint()`.

    IMPORTANTE (cambio de contrato A1 vs v1): la selección v1 era
    muestreo estratificado por complejo individual y NO garantizaba
    disjunción por scaffold. Regenerar `split_config.json` invalida el
    holdout anterior (327 complejos seed=42): ver
    `verify_scaffold_disjoint()` y el script de regeneración integrado
    (data_splitter.py --rebuild-split-config).

    Args:
        complexes: complejos VIP (pasaron auditoría)
        family_classifications: {pdb_id: FamilyClassification}
        test_size: tamaño del test set
        seed: semilla para reproducibilidad

    Returns:
        lista de PDB IDs para el test set (por scaffolds completos)
    """
    rng = np.random.RandomState(seed)

    # Organizar por familia
    by_family: dict[str, list[Any]] = defaultdict(list)
    for cpx in complexes:
        family = "other"
        if cpx.pdb_id in family_classifications:
            fc = family_classifications[cpx.pdb_id]
            family = fc.family if hasattr(fc, "family") else fc
        by_family[family].append(cpx)

    total = len(complexes)
    test_ids = []

    # Asignar cuota proporcional por familia, con mínimo 10
    quotas = {}
    remaining = test_size
    for family, members in by_family.items():
        proportion = len(members) / total
        quota = max(10, int(test_size * proportion))
        quota = min(quota, len(members) // 2)  # Nunca más de la mitad
        quotas[family] = quota
        remaining -= quota

    # Si sobran slots, distribuir proporcionalmente
    if remaining > 0:
        for family in sorted(quotas.keys()):
            extra = min(remaining, len(by_family[family]) // 2 - quotas[family])
            if extra > 0:
                quotas[family] += extra
                remaining -= extra

    # Selección SCAFFOLD-DISJOINT por familia: se eligen scaffolds COMPLETOS
    for family, members in by_family.items():
        quota = quotas.get(family, 0)
        if quota == 0:
            continue

        # Agrupar miembros de la familia por scaffold
        family_scaffolds: dict[str, list[Any]] = defaultdict(list)
        for cpx in members:
            family_scaffolds[get_bemis_murcko_scaffold(cpx.ligand_smiles)].append(cpx)

        # Ordenar scaffolds por pKi medio (estratificación aproximada),
        # rompiendo empates con clave estable (scaffold string) para
        # determinismo independiente del orden de hash.
        ordered_scaffolds = sorted(
            family_scaffolds.keys(),
            key=lambda s: (sum(c.pki for c in family_scaffolds[s]) / len(family_scaffolds[s]),
                           s),
        )

        selected: list[str] = []
        n_selected = 0
        # Greedy intercalado dirigido por la semilla: cada paso decide con
        # rng si tomar del inicio o del final de la lista ordenada por pKi
        # medio (aproximación uniforme sobre la distribución). NUNCA se
        # parte un scaffold.
        # [A1 fix] La semilla gobierna la dirección de cada paso y los
        # desempates de la pasada de completado (misma seed → misma
        # selección; seeds distintas → selecciones distintas).
        # [A1 fix] Los scaffolds que exceden el margen 1.5x NO se descartan:
        # se difieren a la pasada de completado (atomicidad + cobertura).
        deferred: list[str] = []
        while ordered_scaffolds and n_selected < quota:
            take_high = bool(rng.randint(0, 2))
            scaffold = ordered_scaffolds.pop(0) if take_high else ordered_scaffolds.pop()
            group_ids = [c.pdb_id for c in family_scaffolds[scaffold]]

            # Margen: permitir exceder cuota solo hasta 1.5x; si el grupo
            # es demasiado grande, diferirlo y probar el siguiente.
            if n_selected + len(group_ids) > quota * 1.5:
                deferred.append(scaffold)
                continue
            selected.extend(group_ids)
            n_selected += len(group_ids)

        def _tiebreak_keys(scaffolds: list[str]) -> dict[str, float]:
            return {s: rng.random() for s in scaffolds}

        # Pasada de completado con los grupos diferidos, más pequeños
        # primero (empates resueltos con la semilla).
        if n_selected < quota and deferred:
            tie = _tiebreak_keys(deferred)
            for scaffold in sorted(
                deferred,
                key=lambda s: (len(family_scaffolds[s]), tie[s]),
            ):
                if n_selected >= quota:
                    break
                group_ids = [c.pdb_id for c in family_scaffolds[scaffold]]
                selected.extend(group_ids)
                n_selected += len(group_ids)

        # Si con scaffolds completos no alcanzamos la cuota, completar con
        # los grupos restantes más pequeños primero hasta cubrir la cuota.
        if n_selected < quota and ordered_scaffolds:
            tie = _tiebreak_keys(ordered_scaffolds)
            for scaffold in sorted(
                ordered_scaffolds,
                key=lambda s: (len(family_scaffolds[s]), tie[s]),
            ):
                if n_selected >= quota:
                    break
                group_ids = [c.pdb_id for c in family_scaffolds[scaffold]]
                selected.extend(group_ids)
                n_selected += len(group_ids)

        overshoot = len(selected) - quota
        if overshoot > 0:
            log.info(
                "frozen_test_overshoot_scaffold_atomicity",
                family=family, quota=quota, selected=len(selected),
                overshoot=overshoot,
            )

        test_ids.extend(selected)

    log.info(
        "frozen_test_set_created",
        method=HOLDOUT_SELECTION_METHOD,
        test_size=len(test_ids),
        target_size=test_size,
        families={f: quotas.get(f, 0) for f in by_family},
    )

    return test_ids


def verify_scaffold_disjoint(
    test_ids: list[str],
    complexes: list[Any],
) -> tuple[bool, dict[str, list[str]]]:
    """
    Verificar que el holdout es scaffold-disjoint: ningún scaffold del test
    set aparece en complejos fuera del test set.

    Args:
        test_ids: IDs del frozen test set
        complexes: todos los complejos considerados (train pool incluido)

    Returns:
        (ok, violations) donde violations = {scaffold: [pdb_ids fuera del
        test que comparten scaffold]} — vacío si el holdout es disjunto.
    """
    test_set = set(test_ids)
    violations: dict[str, list[str]] = defaultdict(list)

    # Precomputar scaffold → ids UNA sola vez (evita O(n^2) con RDKit)
    scaffold_to_ids: dict[str, list[str]] = defaultdict(list)
    for cpx in complexes:
        scaffold_to_ids[get_bemis_murcko_scaffold(cpx.ligand_smiles)].append(cpx.pdb_id)

    test_scaffolds = {
        s for s, ids in scaffold_to_ids.items() if any(pid in test_set for pid in ids)
    }

    for cpx in complexes:
        if cpx.pdb_id in test_set:
            continue
        scaffold = get_bemis_murcko_scaffold(cpx.ligand_smiles)
        if scaffold in test_scaffolds:
            violations[scaffold].append(cpx.pdb_id)

    ok = not violations
    if ok:
        log.info("scaffold_disjoint_verified", method=HOLDOUT_SELECTION_METHOD, n_test=len(test_set))
    else:
        n_violations = sum(len(v) for v in violations.values())
        log.error(
            "scaffold_disjoint_VIOLATED",
            n_violations=n_violations,
            n_scaffolds=len(violations),
            msg=(
                "El holdout comparte scaffolds con el train pool. "
                "Regenerar con create_frozen_test_set v2 o auditar el seed."
            ),
        )
    return ok, dict(violations)


def scaffold_split_cv(
    complexes: list[Any],
    test_ids: list[str],
    n_folds: int = 5,
    seed: int = 42,
) -> list[DataSplit]:
    """
    Scaffold-split cross-validation.

    El split se hace a nivel de scaffold, no de molécula individual:
    - Todas las moléculas con el mismo scaffold van al mismo fold
    - Esto evita data leakage por series químicas

    Args:
        complexes: complejos VIP con SMILES
        test_ids: IDs del frozen test set (se excluyen)
        n_folds: número de folds
        seed: reproducibilidad

    Returns:
        lista de DataSplit (uno por fold)
    """
    rng = np.random.RandomState(seed)
    test_id_set = set(test_ids)

    # Excluir test set
    train_pool = [c for c in complexes if c.pdb_id not in test_id_set]

    # Agrupar por scaffold
    scaffold_groups = group_by_scaffold(train_pool)

    # Crear mapping pdb_id → scaffold
    id_to_scaffold = {}
    for scaffold, ids in scaffold_groups.items():
        for pdb_id in ids:
            id_to_scaffold[pdb_id] = scaffold

    # Barajar scaffolds determinísticamente
    scaffolds = list(scaffold_groups.keys())
    rng.shuffle(scaffolds)

    # Asignar scaffolds a folds round-robin (balanceado por tamaño)
    fold_sizes = [0] * n_folds
    fold_scaffolds: dict[int, list[str]] = {i: [] for i in range(n_folds)}

    # Ordenar scaffolds de mayor a menor para mejor balance
    scaffolds_sorted = sorted(scaffolds, key=lambda s: len(scaffold_groups[s]), reverse=True)

    for scaffold in scaffolds_sorted:
        # Asignar al fold con menos miembros
        min_fold = min(range(n_folds), key=lambda i: fold_sizes[i])
        fold_scaffolds[min_fold].append(scaffold)
        fold_sizes[min_fold] += len(scaffold_groups[scaffold])

    # Generar DataSplits
    splits = []
    for fold_idx in range(n_folds):
        val_scaffolds = set(fold_scaffolds[fold_idx])

        val_ids = []
        train_ids = []
        for cpx in train_pool:
            scaffold = id_to_scaffold.get(cpx.pdb_id, "")
            if scaffold in val_scaffolds:
                val_ids.append(cpx.pdb_id)
            else:
                train_ids.append(cpx.pdb_id)

        split = DataSplit(
            train_ids=train_ids,
            val_ids=val_ids,
            test_ids=test_ids,
            split_method="scaffold_split_cv",
            fold=fold_idx,
        )
        splits.append(split)

    log.info(
        "scaffold_split_cv_created",
        n_folds=n_folds,
        fold_sizes=[s.n_val for s in splits],
        train_sizes=[s.n_train for s in splits],
        test_size=len(test_ids),
    )

    return splits


def build_ltr_groups(
    complexes: list[Any],
    pdb_ids: list[str],
) -> tuple[list[int], list[float]]:
    """
    Construir grupos de ranking para XGBoost LTR.

    Para rank:pairwise, XGBoost necesita:
    - group: array donde cada elemento es el número de items en cada grupo
    - labels: array de relevancia (pKi) alineado con las features

    Grupos = complejos del mismo target. Solo targets con ≥ 2 ligandos
    forman un grupo (no tiene sentido hacer ranking con 1 solo ligando).

    Implementation note: En PDBbind, cada PDB ID es un complejo único
    (1 target + 1 ligand). Para agrupar por target necesitamos la
    identidad del target, que no siempre está explícita. Usamos el
    PDB ID de 4 letras como proxy — todos los complejos con la misma
    proteína cristalográfica son del mismo target. Esto es una
    aproximación conservadora (bajo recall, alta precision).

    Para un pipeline ideal se usarían UniProt IDs.

    Args:
        complexes: todos los complejos
        pdb_ids: IDs a incluir (e.g., train set)

    Returns:
        (groups, labels) donde:
          groups: list[int] tamaños de cada grupo
          labels: list[float] pKi para cada complejo, ordenados por grupo
    """
    id_set = set(pdb_ids)
    cpx_map = {c.pdb_id: c for c in complexes if c.pdb_id in id_set}

    # En PDBbind, muchas proteínas aparecen múltiples veces con diferentes
    # ligandos. Para simplificar, cada complejo es su propio "grupo" de
    # tamaño 1 a menos que compartimos proteína.
    # Este es un punto donde el diseño puede mejorarse con UniProt mapping.

    # Por ahora: cada PDB ID es un grupo de 1 (pointwise learning).
    # XGBoost rank:pairwise con grupos de 1 se reduce a regresión.
    # Esto es HONEST about the limitation: sin mapping de target,
    # no podemos hacer verdadero pairwise ranking.

    # NOTA: Cuando se integre UniProt mapping, esta función se actualiza
    # para crear grupos reales multi-ligando.

    ordered_ids = sorted(pdb_ids)  # Orden determinístico
    groups = [1] * len(ordered_ids)  # Cada complejo es su grupo
    labels = [cpx_map[pid].pki for pid in ordered_ids if pid in cpx_map]

    # Verificar alineación
    actual_ids = [pid for pid in ordered_ids if pid in cpx_map]
    if len(actual_ids) != len(labels):
        log.warning(
            "ltr_groups_mismatch",
            expected=len(ordered_ids),
            actual=len(actual_ids),
        )

    log.info(
        "ltr_groups_built",
        n_complexes=len(actual_ids),
        n_groups=len(groups),
        label_range=[round(min(labels), 2), round(max(labels), 2)] if labels else None,
    )

    return groups, labels


def save_split_config(
    test_ids: list[str],
    splits: list[DataSplit],
    output_path: str | Path,
    seed: int = 42,
    holdout_method: str | None = None,
) -> None:
    """
    Guardar configuración de splits para reproducibilidad.

    Este archivo permite reproducir exactamente los mismos splits.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "seed": seed,
        "holdout_method": holdout_method or HOLDOUT_SELECTION_METHOD,
        "scaffold_disjoint": True,
        "frozen_test_set": sorted(test_ids),
        "n_test": len(test_ids),
        "n_folds": len(splits),
        "folds": [
            {
                "fold": s.fold,
                "n_train": s.n_train,
                "n_val": s.n_val,
                "train_ids": sorted(s.train_ids),
                "val_ids": sorted(s.val_ids),
            }
            for s in splits
        ],
    }

    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)

    log.info("split_config_saved", path=str(output_path))


# ═══════════════════════════════════════════════════════════════════════
# CLI — regeneración del split_config.json con holdout SCAFFOLD-DISJOINT
# ═══════════════════════════════════════════════════════════════════════

def _rebuild_split_config(
    data_dir: str | Path,
    output_dir: str | Path,
    test_size: int = 500,
    seed: int = 42,
    n_folds: int = 5,
    skip_structure_checks: bool = False,
    include_other: bool = True,
) -> dict[str, Any]:
    """Reconstruir split_config.json con el holdout scaffold-disjoint (A1).

    Réplica de los pasos 1-5 de train_orchestrator.run_training_pipeline
    (parser → curación → VIP audit → clasificación familiar → frozen test
    set SCAFFOLD-DISJOINT → scaffold-split CV → guardar config), de modo
    que el .json resultante es consumible por train_families.py (paso 3.5)
    sin tocar el código de entrenamiento.

    Returns:
        report con n_loaded, n_curated, n_vip, family_summary, n_test,
        violaciones scaffold (deben ser 0) y rutas escritas.
    """
    from data_curator import DataCurator
    from pdbbind_parser import PDBBindParser
    from structural_family import StructuralFamilyClassifier
    from vip_audit import VIPAuditor, get_vip_complexes

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    parser = PDBBindParser(data_dir)
    n_loaded = parser.load(include_other=include_other)
    if n_loaded == 0:
        raise RuntimeError(f"No se pudieron cargar datos de PDBbind desde {data_dir}")

    curator = DataCurator()
    curated_complexes, curation_report = curator.curate(parser.complexes)
    curator.save_report(curation_report, output_dir / "data_curation_report.json")

    auditor = VIPAuditor(skip_structure_checks=skip_structure_checks)
    audit_report = auditor.audit_all(curated_complexes)
    vip_ids = get_vip_complexes(audit_report)
    vip_complexes = [c for c in curated_complexes if c.pdb_id in set(vip_ids)]

    classifier = StructuralFamilyClassifier()
    family_classifications = classifier.classify_all(vip_complexes)
    family_summary = classifier.get_family_summary(family_classifications)

    test_ids = create_frozen_test_set(
        vip_complexes, family_classifications, test_size=test_size, seed=seed,
    )
    splits = scaffold_split_cv(vip_complexes, test_ids, n_folds=n_folds, seed=seed)
    # Verificación A1: el holdout NO comparte scaffolds con el train pool
    ok, violations = verify_scaffold_disjoint(test_ids, vip_complexes)
    if not ok:
        n_violations = sum(len(v) for v in violations.values())
        raise RuntimeError(
            f"Holdout scaffold-disjoint VIOLADO: {n_violations} complejos "
            "del train pool comparten scaffold con el test set."
        )

    save_split_config(test_ids, splits, output_dir / "split_config.json", seed=seed,
                      holdout_method=HOLDOUT_SELECTION_METHOD)

    report = {
        "n_loaded": n_loaded,
        "n_curated": len(curated_complexes),
        "n_vip": len(vip_complexes),
        "families": family_summary.get("by_family", {}),
        "holdout_method": HOLDOUT_SELECTION_METHOD,
        "n_test": len(test_ids),
        "n_folds": n_folds,
        "fold_sizes": [{"train": s.n_train, "val": s.n_val} for s in splits],
        "scaffold_violations": len(violations),
        "split_config_path": str(output_dir / "split_config.json"),
    }
    log.info("split_config_rebuilt", method=HOLDOUT_SELECTION_METHOD, report=report)
    return report


if __name__ == "__main__":
    import argparse
    import json

    ap = argparse.ArgumentParser(
        description=(
            "Regenerar split_config.json con holdout SCAFFOLD-DISJOINT "
            "(A1). Bonito mutate el contrato del frozen test set: el train "
            "nunca vuelve a tocar complejos que comparten scaffold con el "
            "holdout."
        )
    )
    ap.add_argument("--data-dir", default="data/pdbbind",
                    help="Directorio PDBbind (default: data/pdbbind)")
    ap.add_argument("--output-dir", default="artifacts",
                    help="Directorio de artefactos (default: artifacts)")
    ap.add_argument("--test-size", type=int, default=500)
    ap.add_argument("--n-folds", type=int, default=5)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--skip-structure-checks", action="store_true")
    ap.add_argument("--refined-only", action="store_true")
    args = ap.parse_args()

    report = _rebuild_split_config(
        args.data_dir, args.output_dir,
        test_size=args.test_size, seed=args.seed, n_folds=args.n_folds,
        skip_structure_checks=args.skip_structure_checks,
        include_other=not args.refined_only,
    )
    print(json.dumps(report, indent=2, default=str))
