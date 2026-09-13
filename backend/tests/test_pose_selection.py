"""
El selector de pose como evidencia: recomienda, nunca sustituye.

Lo que protegen, en orden de gravedad:

1. **Vina top-1 se conserva siempre.** El selector emite una recomendación con
   su margen; nada la aplica en silencio. Cuando no hay recomendación, la
   referencia es `vina_top1` etiquetada como **fallback** — no como un éxito
   del selector.

2. **Una pose sugerida que falla los controles físicos NO se sustituye.** Se
   declara revisión y se listan las alternativas que pasan, sin elegir ninguna:
   escoger «la siguiente que pase» sería una decisión que nadie tomó y para la
   que el modelo no fue entrenado.

3. **Desacoplado del rescoring.** El selector se carga de sus artefactos, sin
   `ModelManager` y sin la etapa `xgb`, que sigue fuera del camino obligatorio.

4. **Se abstiene antes que adivinar.** Modelo ausente, receptor irrecuperable o
   fallo del selector producen `unavailable`/`error` con razón estable.
"""

from __future__ import annotations

import hashlib
import json

import pytest

from services.chemistry import pose_selection as ps
from tests.conftest import rdkit_available


def _pose(rank: int, afinidad: float = -8.0, pdbqt: str | None = "ATOM 1\n") -> dict:
    return {"rank": rank, "affinity": afinidad, "rmsd_lb": 0.0, "rmsd_ub": 0.0,
            "pdbqt_block": pdbqt}


POSES = [_pose(1, -8.3), _pose(2, -7.9), _pose(3, -7.1)]


def _evidencia_fisica(estados: dict[int, str]) -> dict:
    """Evidencia estructural de P0-A, reducida a lo que el selector lee."""
    return {
        "version_schema": 1,
        "stage_status": "review",
        "poses": [{"rank": r, "status": e} for r, e in sorted(estados.items())],
    }


@pytest.fixture
def receptor_pdb(tmp_path):
    ruta = tmp_path / "receptor.pdb"
    ruta.write_text(
        "ATOM      1  N   ALA A   1      11.104   6.134  -6.504  1.00  0.00           N\n",
        encoding="utf-8",
    )
    return ruta


@pytest.fixture
def selector_simulado(monkeypatch, tmp_path):
    """
    Sustituye el booster por una salida controlada.

    NO se toca el modelo, ni las features, ni el umbral: se sustituye el punto
    de entrada `PoseSelector` para poder ejercitar el CONTRATO —abstención,
    fallback, revisión física— sin convertir la suite en un banco de inferencia.
    """
    import sys
    import types

    artefactos = tmp_path / "artifacts"
    artefactos.mkdir()
    modelo = artefactos / "pose_selector_v06.xgb"
    meta = artefactos / "pose_selector_v06_meta.json"
    modelo.write_bytes(b"booster simulado")
    meta.write_text(json.dumps({"modelo": "v0.6 simulado"}), encoding="utf-8")
    monkeypatch.setenv("RESCORING_POSE_SELECTOR_MODEL_PATH", str(modelo))
    monkeypatch.setenv("RESCORING_POSE_SELECTOR_META_PATH", str(meta))

    estado: dict = {"resultado": None, "motivo": "", "load_error": None, "explota": False}

    class _Falso:
        def __init__(self, model_path, meta_path, abstention_threshold=0.097663):
            self.abstention_threshold = abstention_threshold
            self.load_error = estado["load_error"]
            self.nombre_modelo = "pose_selector_v06"
            self.meta = {"modelo": "v0.6 simulado"}

        def seleccionar_pose(self, pose_blocks, vina_scores, target_pdb_path):
            if estado["explota"]:
                raise RuntimeError("el selector reventó")
            return estado["resultado"], estado["motivo"]

    modulo = types.ModuleType("pose_selector.selector")
    modulo.PoseSelector = _Falso
    modulo.UMBRAL_ABSTENCION_DEFECTO = 0.097663
    paquete = types.ModuleType("pose_selector")
    monkeypatch.setitem(sys.modules, "pose_selector", paquete)
    monkeypatch.setitem(sys.modules, "pose_selector.selector", modulo)

    estado["modelo_path"] = modelo
    estado["meta_path"] = meta
    return estado


# ── 1. Selección normal ──────────────────────────────────────────────


def test_seleccion_normal_recomienda_sin_sustituir(selector_simulado, receptor_pdb):
    selector_simulado["resultado"] = {
        "pose_scores": [0.1, 0.9, 0.2], "selected_pose_rank": 1,
        "pose_confidence": 0.7, "pose_abstained": False,
        "pose_selector_model": "pose_selector_v06", "warnings": [],
    }

    contrato = ps.build_pose_selection(
        poses=POSES, receptor_pdb_path=receptor_pdb,
        structural_evidence=_evidencia_fisica({1: "passed", 2: "passed", 3: "review"}),
    )

    assert contrato["status"] == ps.STATUS_SELECTED
    assert contrato["strategy"] == ps.STRATEGY_SELECTOR
    assert contrato["strategy_is_fallback"] is False
    # El índice 1 del selector es la pose de rank 2.
    assert contrato["selected_pose_rank"] == 2
    assert contrato["confidence"] == 0.7
    assert contrato["abstained"] is False
    # Y lo esencial: Vina top-1 SIGUE declarado, no se pierde.
    assert contrato["vina_top1_rank"] == 1
    assert "RECOMENDACIÓN" in contrato["detail"] or "recomienda" in contrato["detail"]


def test_los_scores_se_publican_por_rank_real(selector_simulado, receptor_pdb):
    selector_simulado["resultado"] = {
        "pose_scores": [0.1, 0.9, 0.2], "selected_pose_rank": 1,
        "pose_confidence": 0.7, "pose_abstained": False,
        "pose_selector_model": "pose_selector_v06", "warnings": ["aviso de cluster"],
    }

    contrato = ps.build_pose_selection(poses=POSES, receptor_pdb_path=receptor_pdb)

    # El índice interno del selector es 0-based; el contrato habla en `rank`.
    assert contrato["pose_scores"] == [
        {"rank": 1, "score": 0.1}, {"rank": 2, "score": 0.9}, {"rank": 3, "score": 0.2},
    ]
    assert contrato["warnings"] == ["aviso de cluster"]


# ── 5. Vina top-1 y afinidades intactas ──────────────────────────────


def test_vina_top1_y_las_afinidades_se_conservan_intactas(selector_simulado, receptor_pdb):
    selector_simulado["resultado"] = {
        "pose_scores": [0.1, 0.9, 0.2], "selected_pose_rank": 1,
        "pose_confidence": 0.7, "pose_abstained": False,
        "pose_selector_model": "pose_selector_v06", "warnings": [],
    }
    antes = json.dumps(POSES)

    contrato = ps.build_pose_selection(poses=POSES, receptor_pdb_path=receptor_pdb)

    # Ni una pose se reordena ni una afinidad se toca.
    assert json.dumps(POSES) == antes
    assert contrato["inputs"]["pose_ranks"] == [1, 2, 3]
    assert contrato["inputs"]["vina_affinities"] == [-8.3, -7.9, -7.1]
    assert contrato["vina_top1_rank"] == 1


# ── 2. Abstención ────────────────────────────────────────────────────


def test_la_abstencion_no_recomienda_y_cae_a_vina_top1_como_fallback(
    selector_simulado, receptor_pdb
):
    selector_simulado["resultado"] = {
        "pose_scores": [0.50, 0.52, 0.49], "selected_pose_rank": 1,
        "pose_confidence": 0.02, "pose_abstained": True,
        "pose_selector_model": "pose_selector_v06", "warnings": [],
    }

    contrato = ps.build_pose_selection(poses=POSES, receptor_pdb_path=receptor_pdb)

    assert contrato["status"] == ps.STATUS_ABSTAINED
    assert contrato["abstained"] is True
    assert contrato["abstention_reason"] == ps.MARGEN_BAJO_UMBRAL
    # NO hay recomendación…
    assert contrato["selected_pose_rank"] is None
    # …y la referencia es Vina top-1, marcada como fallback.
    assert contrato["strategy"] == ps.STRATEGY_VINA_TOP1
    assert contrato["strategy_is_fallback"] is True
    assert contrato["vina_top1_rank"] == 1
    # Pero lo medido se conserva: se puede auditar por qué se abstuvo.
    assert contrato["confidence"] == 0.02
    assert len(contrato["pose_scores"]) == 3
    assert contrato["would_have_suggested_rank"] == 2


def test_una_sola_pose_se_abstiene_por_no_haber_margen(selector_simulado, receptor_pdb):
    selector_simulado["resultado"] = {
        "pose_scores": [0.7], "selected_pose_rank": 0, "pose_confidence": 0.0,
        "pose_abstained": True, "pose_selector_model": "pose_selector_v06", "warnings": [],
    }

    contrato = ps.build_pose_selection(poses=[_pose(1)], receptor_pdb_path=receptor_pdb)

    assert contrato["status"] == ps.STATUS_ABSTAINED
    assert contrato["abstention_reason"] == ps.UNA_SOLA_POSE


# ── 3 y 4. Modelo ausente y error ────────────────────────────────────


def test_modelo_ausente_es_unavailable_con_fallback_declarado(monkeypatch, receptor_pdb, tmp_path):
    monkeypatch.setenv("RESCORING_POSE_SELECTOR_MODEL_PATH", str(tmp_path / "no_existe.xgb"))
    monkeypatch.setenv("RESCORING_POSE_SELECTOR_META_PATH", str(tmp_path / "no_existe.json"))

    contrato = ps.build_pose_selection(poses=POSES, receptor_pdb_path=receptor_pdb)

    assert contrato["status"] == ps.STATUS_UNAVAILABLE
    assert contrato["abstention_reason"] == ps.MODELO_AUSENTE
    assert contrato["strategy"] == ps.STRATEGY_VINA_TOP1
    assert contrato["strategy_is_fallback"] is True
    assert contrato["vina_top1_rank"] == 1
    # `unavailable` NO es `abstained`: nadie se abstuvo, el modelo no estaba.
    assert contrato["abstained"] is False


def test_un_modelo_que_no_carga_es_unavailable_no_error(selector_simulado, receptor_pdb):
    selector_simulado["load_error"] = "pose_selector_load_failed: ValueError: meta rota"

    contrato = ps.build_pose_selection(poses=POSES, receptor_pdb_path=receptor_pdb)

    assert contrato["status"] == ps.STATUS_UNAVAILABLE
    assert "meta rota" in contrato["detail"]


def test_un_selector_que_revienta_es_error_y_no_tumba_nada(selector_simulado, receptor_pdb):
    selector_simulado["explota"] = True

    contrato = ps.build_pose_selection(poses=POSES, receptor_pdb_path=receptor_pdb)

    assert contrato["status"] == ps.STATUS_ERROR
    assert contrato["abstention_reason"] == ps.SELECTOR_FALLO
    assert contrato["strategy_is_fallback"] is True
    assert contrato["vina_top1_rank"] == 1


def test_un_selector_que_devuelve_none_es_error_con_su_motivo(selector_simulado, receptor_pdb):
    selector_simulado["resultado"] = None
    selector_simulado["motivo"] = "pose 0 ilegible o PDB no disponible"

    contrato = ps.build_pose_selection(poses=POSES, receptor_pdb_path=receptor_pdb)

    assert contrato["status"] == ps.STATUS_ERROR
    assert "pose 0 ilegible" in contrato["detail"]


def test_sin_receptor_legible_no_se_opina(selector_simulado, tmp_path):
    contrato = ps.build_pose_selection(
        poses=POSES, receptor_pdb_path=tmp_path / "no_existe.pdb")

    assert contrato["status"] == ps.STATUS_UNAVAILABLE
    assert contrato["abstention_reason"] == ps.RECEPTOR_NO_DISPONIBLE


def test_una_pose_sin_pdbqt_impide_comparar(selector_simulado, receptor_pdb):
    contrato = ps.build_pose_selection(
        poses=[_pose(1), _pose(2, pdbqt=None)], receptor_pdb_path=receptor_pdb)

    assert contrato["status"] == ps.STATUS_UNAVAILABLE
    assert contrato["abstention_reason"] == ps.SIN_PDBQT_DE_POSE


def test_sin_poses_no_hay_nada_que_seleccionar(selector_simulado, receptor_pdb):
    contrato = ps.build_pose_selection(poses=[], receptor_pdb_path=receptor_pdb)

    assert contrato["status"] == ps.STATUS_UNAVAILABLE
    assert contrato["abstention_reason"] == ps.SIN_POSES


# ── 6 y 7. Estado físico de la pose sugerida ─────────────────────────


def test_una_pose_sugerida_que_pasa_los_controles_se_declara(selector_simulado, receptor_pdb):
    selector_simulado["resultado"] = {
        "pose_scores": [0.1, 0.9, 0.2], "selected_pose_rank": 1,
        "pose_confidence": 0.7, "pose_abstained": False,
        "pose_selector_model": "pose_selector_v06", "warnings": [],
    }

    contrato = ps.build_pose_selection(
        poses=POSES, receptor_pdb_path=receptor_pdb,
        structural_evidence=_evidencia_fisica({1: "passed", 2: "passed", 3: "failed"}),
    )

    assert contrato["selected_pose_rank"] == 2
    assert contrato["suggested_pose_physical_status"] == "passed"
    assert contrato["physical_review"] is False
    # Las alternativas que pasan se listan aunque la sugerida esté bien: el
    # lector puede querer verlas. Nunca incluyen a la propia sugerida.
    assert contrato["physically_valid_alternatives"] == [{"rank": 1, "physical_status": "passed"}]


def test_una_pose_sugerida_que_FALLA_no_se_sustituye_automaticamente(
    selector_simulado, receptor_pdb
):
    """
    La regla más importante del sprint.

    El selector recomendó la pose 2 y esa pose falla los controles oficiales.
    NO se elige la 1 ni la 3: se declara revisión y se muestran las que pasan.
    Escoger «la siguiente que pase» sería una decisión que nadie tomó y para la
    que el modelo no fue entrenado.
    """
    selector_simulado["resultado"] = {
        "pose_scores": [0.1, 0.9, 0.2], "selected_pose_rank": 1,
        "pose_confidence": 0.7, "pose_abstained": False,
        "pose_selector_model": "pose_selector_v06", "warnings": [],
    }

    contrato = ps.build_pose_selection(
        poses=POSES, receptor_pdb_path=receptor_pdb,
        structural_evidence=_evidencia_fisica({1: "passed", 2: "failed", 3: "passed"}),
    )

    # La sugerida NO cambia…
    assert contrato["selected_pose_rank"] == 2
    assert contrato["suggested_pose_physical_status"] == "failed"
    # …se declara revisión…
    assert contrato["physical_review"] is True
    # …y las alternativas se MUESTRAN, sin seleccionar ninguna.
    assert contrato["physically_valid_alternatives"] == [
        {"rank": 1, "physical_status": "passed"},
        {"rank": 3, "physical_status": "passed"},
    ]
    assert contrato["status"] == ps.STATUS_SELECTED


def test_sin_evidencia_fisica_el_estado_de_la_sugerida_es_desconocido(
    selector_simulado, receptor_pdb
):
    selector_simulado["resultado"] = {
        "pose_scores": [0.1, 0.9, 0.2], "selected_pose_rank": 1,
        "pose_confidence": 0.7, "pose_abstained": False,
        "pose_selector_model": "pose_selector_v06", "warnings": [],
    }

    contrato = ps.build_pose_selection(
        poses=POSES, receptor_pdb_path=receptor_pdb, structural_evidence=None)

    # `None`, no `passed`: no se supone que pase lo que nadie midió.
    assert contrato["suggested_pose_physical_status"] is None
    assert contrato["physical_review"] is True
    assert contrato["physically_valid_alternatives"] == []


# ── 9. Modelo y hash persistidos ─────────────────────────────────────


def test_el_modelo_su_version_y_su_hash_viajan_en_el_contrato(selector_simulado, receptor_pdb):
    selector_simulado["resultado"] = {
        "pose_scores": [0.1, 0.9, 0.2], "selected_pose_rank": 0,
        "pose_confidence": 0.8, "pose_abstained": False,
        "pose_selector_model": "pose_selector_v06", "warnings": [],
    }

    contrato = ps.build_pose_selection(poses=POSES, receptor_pdb_path=receptor_pdb)

    modelo = contrato["model"]
    assert modelo["name"] == "pose_selector_v06"
    assert modelo["version"] == "v0.6 simulado"
    assert modelo["model_path"] == "pose_selector_v06.xgb"
    esperado = hashlib.sha256(selector_simulado["modelo_path"].read_bytes()).hexdigest()
    assert modelo["model_sha256"] == esperado
    assert modelo["meta_sha256"]
    assert modelo["abstention_threshold"] == 0.097663
    # Y la procedencia de las entradas.
    assert contrato["inputs"]["pose_pdbqt_source"] == "docking_poses[].pdbqt_block"
    assert contrato["evaluated_at"]


def test_el_hash_del_modelo_REAL_se_puede_calcular():
    """El artefacto de producción existe y se puede sellar por su contenido."""
    modelo, meta = ps.rutas_de_artefactos()

    assert modelo is not None and meta is not None
    if not modelo.exists():  # pragma: no cover - runtime sin sidecar
        pytest.skip("El sidecar de rescoring no está en este runtime")
    assert modelo.name == "pose_selector_v06.xgb"
    assert len(ps._sha256_de(modelo) or "") == 64


# ── Resultado antiguo ────────────────────────────────────────────────


def test_una_evaluacion_antigua_es_unavailable_no_error():
    contrato = ps.seleccion_ausente()

    assert contrato["status"] == ps.STATUS_UNAVAILABLE
    assert contrato["abstention_reason"] == ps.SELECCION_AUSENTE
    assert contrato["strategy"] == ps.STRATEGY_VINA_TOP1
    assert contrato["strategy_is_fallback"] is True
    assert "no es que se abstuviera" in contrato["detail"].lower()


# ── El contrato tiene las mismas claves en los cuatro estados ────────


def test_las_claves_del_contrato_no_dependen_del_estado(selector_simulado, receptor_pdb, tmp_path):
    """
    Un lector no debería tener que preguntar si puede preguntar.

    Si `physical_review` sólo existiera cuando hay recomendación, cualquier
    cliente que la consultara reventaría justo en los casos que esta etapa
    existe para señalar: la abstención y el fallo.
    """
    selector_simulado["resultado"] = {
        "pose_scores": [0.1, 0.9, 0.2], "selected_pose_rank": 1,
        "pose_confidence": 0.7, "pose_abstained": False,
        "pose_selector_model": "pose_selector_v06", "warnings": [],
    }
    seleccionado = ps.build_pose_selection(poses=POSES, receptor_pdb_path=receptor_pdb)

    selector_simulado["resultado"] = dict(
        selector_simulado["resultado"], pose_confidence=0.01, pose_abstained=True)
    abstenido = ps.build_pose_selection(poses=POSES, receptor_pdb_path=receptor_pdb)

    selector_simulado["explota"] = True
    fallo = ps.build_pose_selection(poses=POSES, receptor_pdb_path=receptor_pdb)

    ausente = ps.seleccion_ausente()

    nucleo = set(ausente)
    for contrato in (seleccionado, abstenido, fallo):
        assert nucleo <= set(contrato), nucleo - set(contrato)
        assert contrato["status"] in ps.STATUSES
        # Y las cuatro claves que un lector consulta SIEMPRE.
        for clave in ("status", "strategy", "strategy_is_fallback", "vina_top1_rank",
                      "physical_review", "suggested_pose_physical_status",
                      "physically_valid_alternatives", "abstained"):
            assert clave in contrato, clave

    # Sin recomendación, `physical_review` es `None` —no hay pose sugerida que
    # revisar—, que no es lo mismo que «revisada y en orden».
    assert abstenido["physical_review"] is None
    assert fallo["physical_review"] is None
    assert ausente["physical_review"] is None
    assert seleccionado["physical_review"] is True  # sin evidencia física


# ── 12. Desacople del rescoring ──────────────────────────────────────


def test_el_selector_no_pasa_por_el_pipeline_de_rescoring():
    """
    Desacople real: ni `ModelManager`, ni `rescore`, ni la etapa `xgb`.

    Se mira el CÓDIGO y no los comentarios: este módulo explica por escrito de
    qué se desacopla, y buscar el nombre en el texto crudo encontraría esa
    misma explicación.
    """
    import inspect
    import re

    fuente = inspect.getsource(ps)
    codigo = re.sub(r'"""[\s\S]*?"""', "", fuente)
    codigo = re.sub(r"^[ \t]*#.*$", "", codigo, flags=re.MULTILINE)

    assert "ModelManager" not in codigo
    assert "rescore" not in codigo.lower().replace("rescoring_bridge", "")
    assert "total_score" not in codigo
    # Lo único que se reutiliza del sidecar es la resolución de PATHS.
    assert "get_artifact_defaults" in codigo or "get_sidecar_dir" in codigo


def test_xgboost_sigue_fuera_del_camino_obligatorio_de_cohortes():
    """
    Regresión: integrar el selector no reintrodujo la etapa `xgb`.

    Son cosas distintas: el selector ES un XGBRanker propio, y la etapa `xgb`
    es el rescoring del pipeline. Confundirlas devolvería al camino obligatorio
    justo lo que se sacó.
    """
    from services.cohort import execution as ex
    from services.pipeline.registry import resolve_stage_order

    assert "xgb" not in ex.COHORT_RUN_STAGES
    orden = resolve_stage_order(
        list(ex.COHORT_RUN_STAGES), list(ex.COHORT_RUN_STAGES),
        required_stage_ids=set(ex.COHORT_RUN_STAGES),
    )
    assert "xgb" not in orden and "clgnn" not in orden


# ── La validación física no toca los scores del selector ─────────────


def test_la_validacion_fisica_no_altera_los_scores_del_selector(
    selector_simulado, receptor_pdb
):
    selector_simulado["resultado"] = {
        "pose_scores": [0.1, 0.9, 0.2], "selected_pose_rank": 1,
        "pose_confidence": 0.7, "pose_abstained": False,
        "pose_selector_model": "pose_selector_v06", "warnings": [],
    }

    sin_fisica = ps.build_pose_selection(poses=POSES, receptor_pdb_path=receptor_pdb)
    con_fallos = ps.build_pose_selection(
        poses=POSES, receptor_pdb_path=receptor_pdb,
        structural_evidence=_evidencia_fisica({1: "failed", 2: "failed", 3: "failed"}),
    )

    # Los scores y la confianza son idénticos: la física se declara al lado,
    # no se mezcla con la recomendación.
    assert sin_fisica["pose_scores"] == con_fallos["pose_scores"]
    assert sin_fisica["confidence"] == con_fallos["confidence"]
    assert sin_fisica["selected_pose_rank"] == con_fallos["selected_pose_rank"]
