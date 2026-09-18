"""
Tests para la matriz de regresión de auditoría (sección 6) — fila
"Reporte PDF y resultado API" (contrato frontend/backend).

(a) `EvaluationResultRead` (core/models.py) es el response_model de
    GET /evaluation/result/{molecule_id} (api/routers/evaluation.py). El
    test valida que un payload canónico COMPLETO se acepta y que
    model_dump() expone todos los campos clave que frontend/lib/types.ts
    declara en EvaluationResult (afinidad, poses, scores, familia del
    target, warnings, hotspots, XAI y selectividad). También ejercita la
    coacción de columnas SQLite (JSONB→TEXT, valores doble-serializados)
    que los field validators del schema resuelven en producción.

(b) El generador del dossier PDF real (`generate_certificate_pdf` de
    services/blockchain/pdf_generator.py) construye el documento en
    memoria (reportlab + RDKit + matplotlib, todos disponibles) sin transmitir
    SMILES ni consultar servicios externos. Se asevera que el resultado es un
    PDF válido (%PDF...%EOF).
"""
from __future__ import annotations

import datetime
import io
import uuid

import pytest

from core.models import (
    DockingPose,
    EvaluationResultORM,
    EvaluationResultRead,
    MoleculeORM,
    TargetORM,
)


def _canonical_result_payload() -> dict:
    """Payload canónico COMPLETO del resultado de evaluación (campos del schema)."""
    return {
        "id": str(uuid.uuid4()),
        "molecule_id": str(uuid.uuid4()),
        # Docking
        "affinity_kcal": -9.42,
        "affinity_score": 87.3,
        "docking_poses": [
            {"rank": 1, "affinity": -9.5, "rmsd_lb": 0.0, "rmsd_ub": 0.0},
            {"rank": 2, "affinity": -8.7, "rmsd_lb": 1.2, "rmsd_ub": 1.9},
        ],
        "poses_file_path": "docking-poses/abc.sdf",
        "parsing_source": "sdf",
        "vina_version": "1.2.5",
        "vina_random_seed": 42,
        "scientific_warnings": ["grid no validado"],
        "celery_task_id": "task-123",
        # Propiedades fisicoquímicas
        "molecular_weight": 355.4,
        "log_p": 2.6,
        "tpsa": 88.1,
        "hbd": 2,
        "hba": 5,
        "rotatable_bonds": 6,
        "heavy_atom_count": 26,
        "ring_count": 3,
        "lipinski_pass": True,
        "veber_pass": True,
        "ghose_pass": True,
        "egan_pass": True,
        "muegge_pass": True,
        "muegge_score": 6,
        "fsp3": 0.31,
        "is_pains": False,
        "pains_matches": [],
        "qed": 0.72,
        "sa_score": 2.8,
        "sa_reasons": [],
        # Scores
        "adme_score": 79.0,
        "druglikeness_score": 81.0,
        "total_score": 84.5,
        "gnn_score": 0.612,
        "xgb_score": 0.71,
        "clgnn_score": 0.55,
        "quantum_score": 0.4,
        "ums_score": 0.2,
        "mmgbsa_score": -24.1,
        "stacking_vina_weight": 0.5,
        "stacking_xgb_weight": 0.3,
        "stacking_gnn_weight": 0.2,
        "target_family": "gpcr",
        "engine_used": None,
        "fallback_reason": None,
        "in_applicability_domain": True,
        "model_used": "universal",
        "specificity_score": 74.0,
        "hotspots_hit": ["ASP116", "MET97"],
        "target_hotspots": [
            {"name": "ASP116", "importance": 1.0},
            {"name": "MET97", "importance": 0.8},
        ],
        "affinity_threshold": -7.5,
        "affinity_multiplier": 0.9,
        "specificity_multiplier": 0.8,
        "target_name": "5-HT1A serotonin receptor",
        "target_spearman_rho": 0.512,
        # ADMET
        "blood_viability_score": 75.0,
        "blood_solubility_logs": -4.2,
        "blood_ppb_category": "low",
        "blood_bbb_permeable": True,
        "blood_hia_permeable": True,
        "blood_systemic_reactivity": [],
        # XAI
        "shap_values": {"LogP": -0.21, "MW": 0.18},
        "gnn_attention": [0.1, 0.6, 0.2, 0.1],
        "gnn_attention_svg": "<svg/>",
        "gnn_pharmacophores": {"Aromaticos / Pi-Stacking": 45.0},
        # Selectividad (anti-targets)
        "selectivity_ratio": 2.1,
        "selectivity_verdict": "selectivo",
        "anti_target_results": [{"pdb_id": "3ERT", "affinity": -6.0, "status": "ok"}],
        "selectivity_ran": True,
        "is_control": False,
        "ai_report": "Reporte narrativo de la evaluación.",
        "blockchain_tx_id": None,
        "error_message": None,
        "evaluated_at": "2026-08-13T10:00:00Z",
    }


class TestEvaluationResultReadContract:
    """(a) GET /evaluation/result/{molecule_id} ↔ frontend/lib/types.ts."""

    def test_full_canonical_payload_validates(self):
        payload = _canonical_result_payload()
        model = EvaluationResultRead.model_validate(payload)
        dumped = model.model_dump()

        assert model.id == uuid.UUID(payload["id"])
        assert [p.model_dump() for p in model.docking_poses] == [
            # `conformer_index` es aditivo: None con confórmero único, que es
            # el protocolo por defecto. Con ensemble dice de qué conformación
            # salió cada pose.
            {**p, "pdbqt_block": None, "conformer_index": None, "source_provenance": None}
            for p in payload["docking_poses"]
        ]

        # ── Campos que types.ts declara en EvaluationResult ──────────────
        # Docking
        assert dumped["affinity_kcal"] == -9.42
        assert dumped["affinity_score"] == 87.3
        assert isinstance(dumped["docking_poses"], list)
        for pose in dumped["docking_poses"]:
            assert set(pose) >= {"rank", "affinity", "rmsd_lb", "rmsd_ub"}
        assert dumped["scientific_warnings"] == ["grid no validado"]
        assert dumped["poses_file_path"] == "docking-poses/abc.sdf"
        # Scores
        assert dumped["total_score"] == 84.5
        assert dumped["adme_score"] == 79.0
        assert dumped["druglikeness_score"] == 81.0
        assert dumped["gnn_score"] == 0.612
        assert dumped["target_family"] == "gpcr"
        assert dumped["stacking_vina_weight"] == 0.5
        assert dumped["stacking_xgb_weight"] == 0.3
        assert dumped["stacking_gnn_weight"] == 0.2
        # Hotspots / especificidad
        assert dumped["hotspots_hit"] == ["ASP116", "MET97"]
        assert dumped["target_hotspots"] == [
            {"name": "ASP116", "importance": 1.0},
            {"name": "MET97", "importance": 0.8},
        ]
        assert dumped["specificity_score"] == 74.0
        assert dumped["target_spearman_rho"] == 0.512
        # XAI
        assert dumped["shap_values"] == {"LogP": -0.21, "MW": 0.18}
        assert dumped["gnn_attention"] == [0.1, 0.6, 0.2, 0.1]
        assert dumped["gnn_attention_svg"] == "<svg/>"
        assert dumped["gnn_pharmacophores"] == {"Aromaticos / Pi-Stacking": 45.0}
        # Selectividad
        assert dumped["selectivity_ratio"] == 2.1
        assert dumped["selectivity_verdict"] == "selectivo"
        assert dumped["selectivity_ran"] is True
        assert dumped["anti_target_results"][0]["pdb_id"] == "3ERT"

    def test_computed_efficiencies_are_emitted(self):
        """LE y LLE (computed fields) viajan al frontend según types.ts."""
        payload = _canonical_result_payload()
        model = EvaluationResultRead.model_validate(payload)
        dumped = model.model_dump()

        assert dumped["ligand_efficiency"] == pytest.approx(
            round(-9.42 / 26, 3)
        )
        assert dumped["ligand_lipophilicity_efficiency"] == pytest.approx(
            round((-(-9.42) / 1.36) - 2.6, 3)
        )

    def test_sqlite_json_strings_are_coerced(self):
        """Columnas SQLite (JSONB→TEXT, doble-serializadas) no revientan el
        contrato: los field validators coaccionan str → list/dict."""
        payload = _canonical_result_payload()
        payload["docking_poses"] = (
            '[{"rank": 1, "affinity": -9.5, "rmsd_lb": 0.0, "rmsd_ub": 0.0}]'
        )
        payload["hotspots_hit"] = '["ASP116"]'
        payload["target_hotspots"] = '[{"name": "ASP116", "importance": 1.0}]'
        payload["shap_values"] = '{"LogP": -0.21}'
        payload["scientific_warnings"] = "null"  # el bug histórico SC-8

        model = EvaluationResultRead.model_validate(payload)
        dumped = model.model_dump()

        assert dumped["docking_poses"] == [
            {"rank": 1, "affinity": -9.5, "rmsd_lb": 0.0, "rmsd_ub": 0.0,
             "pdbqt_block": None, "conformer_index": None, "source_provenance": None}
        ]
        assert dumped["hotspots_hit"] == ["ASP116"]
        assert dumped["target_hotspots"] == [{"name": "ASP116", "importance": 1.0}]
        assert dumped["shap_values"] == {"LogP": -0.21}
        assert dumped["scientific_warnings"] is None

    def test_docking_pose_validates_shape(self):
        pose = DockingPose(rank=1, affinity=-9.5, rmsd_lb=0.0, rmsd_ub=0.0)
        assert pose.model_dump() == {
            "rank": 1,
            "affinity": -9.5,
            "rmsd_lb": 0.0,
            "rmsd_ub": 0.0,
            "pdbqt_block": None,
            "conformer_index": None,
            "source_provenance": None,
        }
        # types.ts usa la key "affinity" (no "best_affinity") en las poses.
        assert "affinity" in pose.model_dump()


class TestPdfReportContract:
    """(b) El generador de PDF produce bytes PDF válidos desde ORM reales."""

    @pytest.mark.skipif(
        __import__("importlib").util.find_spec("reportlab") is None,
        reason="reportlab no disponible en este entorno",
    )
    def test_generate_certificate_pdf_returns_valid_pdf(self):
        from services.blockchain import pdf_generator

        target = TargetORM(
            pdb_id="7E2Y",
            name="5-HT1A serotonin receptor",
            chain="R",
            grid_center_x=103.03,
            grid_center_y=114.79,
            grid_center_z=108.36,
            description=(
                "Receptor de serotonina 5-HT1A acoplado a proteína G, "
                "implicado en modulación serotoninérgica central."
            ),
            requires_cns=True,
            is_private=False,
            spearman_rho=0.512,
        )
        mol = MoleculeORM(
            smiles="CC(=O)Oc1ccccc1C(=O)O",
            name="Aspirina",
            smiles_hash="d" * 64,
        )
        mol.target = target  # relación ORM cargada (detached, sin DB)

        eval_result = EvaluationResultORM(
            molecule_id=uuid.uuid4(),
            affinity_kcal=-5.78,
            affinity_score=62.1,
            total_score=71.2,
            adme_score=68.0,
            druglikeness_score=70.0,
            gnn_score=0.5,
            docking_poses=[
                {"rank": 1, "affinity": -5.8, "rmsd_lb": 0.0, "rmsd_ub": 0.0},
                {"rank": 2, "affinity": -5.1, "rmsd_lb": 1.1, "rmsd_ub": 1.4},
            ],
            parsing_source="sdf",
            vina_version="1.2.5",
            vina_random_seed=42,
            scientific_warnings=["grid no validado"],
            hotspots_hit=["ASP116"],
            molecular_weight=180.16,
            log_p=1.4,
            tpsa=63.6,
            hbd=1,
            hba=4,
            rotatable_bonds=3,
            heavy_atom_count=13,
            ring_count=2,
            lipinski_pass=True,
            veber_pass=True,
            qed=0.93,
            sa_score=1.9,
            sa_reasons=[],
            blood_viability_score=82.0,
            blood_solubility_logs=-2.1,
            blood_ppb_category="high",
            blood_bbb_permeable=False,
            blood_hia_permeable=True,
            blood_systemic_reactivity=[],
            target_family="gpcr",
            stacking_vina_weight=0.5,
            stacking_xgb_weight=0.3,
            stacking_gnn_weight=0.2,
            specificity_score=74.0,
            evaluated_at=datetime.datetime(2026, 8, 13, 10, 0, tzinfo=datetime.timezone.utc),
        )

        buf = pdf_generator.generate_certificate_pdf(
            mol, eval_result, target_name=target.name
        )
        data = buf.getvalue()

        assert isinstance(data, bytes)
        assert data.startswith(b"%PDF"), (
            f"el PDF no empieza con %PDF (primeros bytes: {data[:16]!r})"
        )
        assert b"%%EOF" in data[-1024:], "el PDF no termina con %%EOF"
        assert len(data) > 10_000, f"PDF sospechosamente pequeño ({len(data)} bytes)"

        # Si pypdf está disponible, el contrato semántico evita que regresen el
        # Tier como veredicto o el overclaim "Proof of Discovery".
        if __import__("importlib").util.find_spec("pypdf") is not None:
            from pypdf import PdfReader

            text = "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(data)).pages)
            assert "DOSSIER DE EVIDENCIA COMPUTACIONAL" in text
            assert "Propósito del dossier" in text
            assert "SIGUIENTE ACCIÓN JUSTIFICABLE" in text
            assert "Matriz de evidencia por dimensión" in text
            assert "Validez física de poses" in text
            assert "Proof of Discovery" not in text
            assert "Control Nativo" not in text
            assert "Referencia Target" not in text
            assert "Índice compuesto heredado (no es probabilidad)" not in text

    def test_certificate_name_lookup_never_uses_network(self, monkeypatch):
        """El nombre de una molécula no sale del equipo al generar el PDF."""
        import urllib.request
        from services.blockchain import pdf_generator

        def fail_if_called(*_args, **_kwargs):
            raise AssertionError("El certificado no debe llamar a PubChem")

        monkeypatch.setattr(urllib.request, "urlopen", fail_if_called)

        assert pdf_generator.get_pubchem_names("CC(=O)Oc1ccccc1C(=O)O") == ("N/A", "N/A")
