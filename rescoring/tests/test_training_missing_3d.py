"""SCORE-006: datos de entrenamiento ilegibles no entran como contactos cero."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from train_orchestrator import _extract_features_for_all


def test_complejo_sin_archivos_se_marca_para_exclusion():
    complejo = SimpleNamespace(
        pdb_id="BAD", molecular_weight=46.0, logp=0.0, tpsa=20.0,
        hbd=1, hba=1, rotatable_bonds=0, qed=0.4,
        ligand_smiles="", vina_score=-8.0,
        protein_pdb_path=None, ligand_sdf_path=None,
    )
    fallidos = _extract_features_for_all([complejo], skip_structure=False,
                                         max_workers=1, cache_dir=None)
    assert fallidos == {"BAD"}
    assert "close_contacts_4A" not in complejo.features
