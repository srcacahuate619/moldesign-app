"""Controles con respuesta conocida del SHAP que muestra la pestaña Explicabilidad.

Qué se comprueba y contra qué respuesta conocida:

  S01  aditividad: `base + sum(todas las contribuciones) = salida del modelo` (propiedad
       matemática del SHAP de árboles), sobre el modelo distribuido;
  S02  la salida de producción es `pKi de Vina + (base + sum(contribuciones))`: el SHAP explica
       el residuo sobre Vina, no el pKi total (`ModelManager.predict` real, pose real de Vina);
  S03  señal plantada: en un modelo entrenado con y = 2·alfa − beta, el SHAP debe señalar a
       alfa (+) y a beta (−) con cualquier orden de columnas, y un emparejamiento de nombres
       equivocado debe ser detectable (control negativo);
  S04  una característica que ningún árbol usa tiene SHAP exactamente 0 y no mueve la salida
       (control positivo: una que sí se usa, la mueve);
  S05  lo que no se muestra (top 10) no es despreciable: medido, la mediana de lo omitido es
       mayor que la barra más pequeña que sí se muestra;
  S06  la etiqueta de qué explica el SHAP sale del modelo, no es una constante;
  S07  el orden de los nombres del metadato es el del booster en TODOS los Modelos A (si no,
       el SHAP se emparejaría con otra característica);
  S08  la respuesta de producción sólo nombra características del modelo, ordenadas por magnitud.
"""

from __future__ import annotations

import json
import math
import os
import re
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

xgb = pytest.importorskip("xgboost")
pytest.importorskip("rdkit")
from rdkit import Chem  # noqa: E402
from rdkit.Chem import Crippen, Descriptors, QED, rdMolDescriptors  # noqa: E402

from _controles_xai import (  # noqa: E402
    colocar,
    construir_peptidos,
    escribir_sdf,
    extractor_geometrico,
    ligando_3d,
    modelos_pdbqt,
)
from model_manager import (  # noqa: E402
    EXPECTED_MODEL_A_FEATURES,
    SHAP_TOP_K,
    ModelManager,
    etiqueta_de_salida_shap,
    resumir_shap,
)

RESCORING = Path(__file__).resolve().parent.parent
ARTIFACTS = RESCORING / "artifacts"
FIXTURES = RESCORING.parent / "backend" / "tests" / "fixtures" / "meeko_export"

pytestmark = pytest.mark.skipif(
    not (ARTIFACTS / "model_a_universal.json").exists(), reason="faltan los artefactos del Modelo A"
)

_PANEL = [
    "CC(=O)Oc1ccccc1C(=O)O", "NC(=O)c1cccnc1", "Cc1ccsc1", "Fc1ccccc1", "Clc1ccccc1", "Brc1ccccc1",
    "COP(=O)(O)C", "OB(O)c1ccccc1", "CCOC(=O)c1ccccc1N", "CC(C)Cc1ccc(C(C)C(=O)O)cc1",
]


def _modelo(nombre: str):
    booster = xgb.Booster()
    booster.load_model(str(ARTIFACTS / f"{nombre}.json"))
    meta = json.loads((ARTIFACTS / f"{nombre}.metadata.json").read_text(encoding="utf-8"))
    return booster, meta["feature_names"], meta


def _modelos_a() -> list[str]:
    """Los Modelos A que el gestor sirve: los que cumplen el contrato de 167 características.
    `model_a_legacy_176` (176) lo rechaza `ModelManager.load_models` y no se sirve."""
    servidos = []
    for p in sorted(ARTIFACTS.glob("model_a_*.json")):
        if p.name.endswith(".metadata.json"):
            continue
        meta = p.with_name(p.name.replace(".json", ".metadata.json"))
        if meta.exists() and len(json.loads(meta.read_text(encoding="utf-8"))["feature_names"]) == EXPECTED_MODEL_A_FEATURES:
            servidos.append(p.name[: -len(".json")])
    return servidos


@pytest.fixture(scope="module")
def complejos(tmp_path_factory):
    """Veinte vectores de entrada realistas: 10 ligandos × 2 poses sobre un péptido, con las
    características que calcula el extractor de producción y los descriptores de RDKit."""
    pep = construir_peptidos(tmp_path_factory)["A"]
    centro = pep["mol"].GetConformer().GetPositions().mean(axis=0)
    d = tmp_path_factory.mktemp("complejos")
    ex = extractor_geometrico()
    filas = []
    for i, smi in enumerate(_PANEL):
        for j, (vina, desp) in enumerate(((-5.5, (4, 0, 0)), (-9.0, (0, 5, 0)))):
            m = ligando_3d(smi)
            colocar(m, centro, desp)
            f = ex._extract_pdb_sdf(pep["h"], escribir_sdf(m, d / f"l{i}_{j}.sdf"))
            mw = Descriptors.MolWt(m)
            f.update(
                mw=mw, log_mw=math.log(mw), logp=Crippen.MolLogP(m), tpsa=rdMolDescriptors.CalcTPSA(m),
                hbd=rdMolDescriptors.CalcNumHBD(m), hba=rdMolDescriptors.CalcNumHBA(m),
                rotatable_bonds=rdMolDescriptors.CalcNumRotatableBonds(m), qed=QED.qed(Chem.RemoveHs(m)),
                vina_best_score=vina, pose_score_variance=0.2, pose_score_range=0.8, poses_passing_ratio=0.5,
            )
            filas.append(f)
    return filas


def _dmatrix(fila: dict, nombres: list[str]):
    faltan = [n for n in nombres if n not in fila]
    assert not faltan, f"el control no construye estas características: {faltan[:5]}"
    return xgb.DMatrix(np.array([[fila[n] for n in nombres]], dtype=np.float64), feature_names=nombres)


# ─────────────────────────────────────────────────────────────────────────────
# S01 — aditividad
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("nombre", ["model_a_universal", "model_a_universal_faseb", "model_a_kinase"])
def test_s01_base_mas_contribuciones_reproduce_la_salida_del_modelo(complejos, nombre):
    booster, nombres, _ = _modelo(nombre)
    for fila in complejos:
        dm = _dmatrix(fila, nombres)
        margen = float(booster.predict(dm, output_margin=True)[0])
        completo = np.asarray(booster.predict(dm, pred_contribs=True))[0]
        assert abs(float(completo.sum()) - margen) < 1e-3
        r = resumir_shap(booster, dm, nombres)
        # Lo mostrado + lo omitido + la base reconstruye la salida: nada se pierde sin declararse.
        assert abs(r.base + sum(r.valores.values()) + r.omitido - margen) < 1e-3


# ─────────────────────────────────────────────────────────────────────────────
# S02/S08 — la ruta real de producción
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def prediccion_real(tmp_path_factory):
    """`ModelManager.predict` con una salida REAL de Vina (paracetamol, 9 poses)."""
    from schemas import PoseData, RescoreRequest

    if not (FIXTURES / "paracetamol_9_poses.pdbqt").exists():
        pytest.skip("faltan las salidas reales de Vina del backend")
    bloques = modelos_pdbqt(FIXTURES / "paracetamol_9_poses.pdbqt")
    puntuaciones = [float(re.search(r"VINA RESULT:\s+(-?\d+\.\d+)", b).group(1)) for b in bloques]
    xyz = np.array([[float(l[30:38]), float(l[38:46]), float(l[46:54])] for l in bloques[0].splitlines() if l.startswith("ATOM")])
    pep = construir_peptidos(tmp_path_factory)["A"]["mol"]
    conf = pep.GetConformer()
    for i, p in enumerate(conf.GetPositions() - conf.GetPositions().mean(axis=0) + xyz.mean(axis=0) + np.array([2.0, 0, 0])):
        conf.SetAtomPosition(i, p.tolist())
    pdb = tmp_path_factory.mktemp("receptor") / "receptor.pdb"
    Chem.MolToPDBFile(pep, str(pdb))

    anterior = os.getcwd()
    os.chdir(RESCORING)  # las rutas de los artefactos de `config.py` son relativas
    try:
        mm = ModelManager()
        mm.load_models()
        assert mm._is_loaded or mm.model_a is not None, "el Modelo A no cargó"
        m = Chem.MolFromSmiles("CC(=O)Nc1ccc(O)cc1")
        req = RescoreRequest(
            smiles="CC(=O)Nc1ccc(O)cc1", target_pdb_path=str(pdb),
            poses=[PoseData(pdbqt_block=b, vina_score=s) for b, s in zip(bloques, puntuaciones)],
            molecular_weight=Descriptors.MolWt(m), logp=Crippen.MolLogP(m), tpsa=rdMolDescriptors.CalcTPSA(m),
            hbd=rdMolDescriptors.CalcNumHBD(m), hba=rdMolDescriptors.CalcNumHBA(m),
            rotatable_bonds=rdMolDescriptors.CalcNumRotatableBonds(m), qed=QED.qed(m),
        )
        respuesta = mm.predict(req)
    finally:
        os.chdir(anterior)
    return mm, respuesta


def test_s02_la_salida_es_el_pki_de_vina_mas_base_mas_contribuciones(prediccion_real):
    mm, r = prediccion_real
    assert r.model_used == "universal" and r.shap_output == "delta_pKi"
    nombres = mm.model_a_artifact["feature_names"]
    vector = mm._prepare_feature_vector(r.features_used, "A")
    dm = xgb.DMatrix(vector.reshape(1, -1), feature_names=nombres)
    margen = float(mm.model_a.predict(dm, output_margin=True)[0])
    pki_vina = -r.features_used["vina_best_score"] / 1.36
    assert r.score_a == pytest.approx(pki_vina + margen, abs=2e-4)
    res = resumir_shap(mm.model_a, dm, list(nombres))
    # El SHAP sólo explica `margen`, no `pki_vina`: la base de Vina queda fuera de las barras.
    assert abs(res.base + sum(res.valores.values()) + res.omitido - margen) < 1e-3
    assert abs(pki_vina) > 1.0, "el control exige que la parte de Vina sea grande para distinguir ambas magnitudes"


def test_s08_la_respuesta_nombra_solo_caracteristicas_del_modelo_ordenadas_por_magnitud(prediccion_real):
    mm, r = prediccion_real
    nombres = set(mm.model_a_artifact["feature_names"])
    assert 0 < len(r.shap_values) <= SHAP_TOP_K
    assert set(r.shap_values) <= nombres
    magnitudes = [abs(v) for v in r.shap_values.values()]
    assert magnitudes == sorted(magnitudes, reverse=True)
    assert all(m > 1e-4 for m in magnitudes)


# ─────────────────────────────────────────────────────────────────────────────
# S03 — señal plantada y emparejamiento de nombres
# ─────────────────────────────────────────────────────────────────────────────

_NOMBRES = ["alfa", "beta", "gamma", "delta", "epsilon", "zeta"]


@pytest.mark.parametrize("orden", [[0, 1, 2, 3, 4, 5], [5, 4, 3, 2, 1, 0], [3, 0, 5, 1, 4, 2]],
                         ids=["natural", "invertido", "mezclado"])
def test_s03_el_shap_senala_la_senal_plantada_con_cualquier_orden_de_columnas(orden):
    rng = np.random.default_rng(0)
    X = rng.uniform(0, 1, (600, 6))
    y = 2.0 * X[:, 0] - 1.0 * X[:, 1]          # sólo alfa (+2) y beta (−1) importan
    nombres = [_NOMBRES[c] for c in orden]
    modelo = xgb.train(
        {"max_depth": 3, "eta": 0.3, "objective": "reg:squarederror", "seed": 1},
        xgb.DMatrix(X[:, orden], label=y, feature_names=nombres), 80,
    )
    x = np.array([[0.95, 0.95, 0.5, 0.5, 0.5, 0.5]])[:, orden]   # alfa alto (+), beta alto (−)
    dm = xgb.DMatrix(x, feature_names=nombres)
    r = resumir_shap(modelo, dm, nombres, k=6)
    ordenadas = list(r.valores)
    assert ordenadas[:2] == ["alfa", "beta"], r.valores
    assert r.valores["alfa"] > 0 and r.valores["beta"] < 0
    assert abs(r.valores["alfa"]) > abs(r.valores["beta"])
    for irrelevante in ("gamma", "delta", "epsilon", "zeta"):
        assert abs(r.valores.get(irrelevante, 0.0)) < 0.15 * abs(r.valores["alfa"])
    margen = float(modelo.predict(dm, output_margin=True)[0])
    assert abs(r.base + sum(r.valores.values()) + r.omitido - margen) < 1e-4
    # Control negativo: con los nombres al revés, la señal se atribuye a OTRA característica.
    mal = resumir_shap(modelo, dm, nombres[::-1], k=6)
    assert list(mal.valores)[0] != "alfa"


def test_s03_un_numero_de_nombres_distinto_al_de_columnas_se_rechaza():
    X = np.random.default_rng(1).uniform(0, 1, (50, 3))
    modelo = xgb.train({"max_depth": 2, "objective": "reg:squarederror"},
                       xgb.DMatrix(X, label=X[:, 0], feature_names=["a", "b", "c"]), 5)
    with pytest.raises(ValueError):
        resumir_shap(modelo, xgb.DMatrix(X[:1], feature_names=["a", "b", "c"]), ["a", "b"])


# ─────────────────────────────────────────────────────────────────────────────
# S04 — una característica que ningún árbol usa vale exactamente 0
# ─────────────────────────────────────────────────────────────────────────────


def test_s04_una_caracteristica_sin_uso_tiene_shap_cero_y_no_mueve_la_salida(complejos):
    booster, nombres, _ = _modelo("model_a_universal")
    usadas = set(booster.get_score(importance_type="weight"))
    sin_uso = [n for n in nombres if n not in usadas]
    assert sin_uso, "el control necesita al menos una característica sin uso"
    for fila in complejos[:5]:
        dm = _dmatrix(fila, nombres)
        base = float(booster.predict(dm, output_margin=True)[0])
        completo = np.asarray(booster.predict(dm, pred_contribs=True))[0]
        for n in sin_uso:
            assert completo[nombres.index(n)] == 0.0, n
        # Mover todas las que no se usan, mucho, no cambia nada...
        alterada = dict(fila, **{n: fila[n] + 500.0 for n in sin_uso})
        assert float(booster.predict(_dmatrix(alterada, nombres), output_margin=True)[0]) == base
        # ...y mover una que sí se usa, sí (control positivo: la prueba sabe ver un cambio).
        movida = dict(fila, vina_best_score=fila["vina_best_score"] + 3.0)
        assert abs(float(booster.predict(_dmatrix(movida, nombres), output_margin=True)[0]) - base) > 1e-3


# ─────────────────────────────────────────────────────────────────────────────
# S05 — lo que no se muestra pesa
# ─────────────────────────────────────────────────────────────────────────────


def test_s05_lo_omitido_por_el_top_10_no_es_despreciable(complejos):
    booster, nombres, _ = _modelo("model_a_universal")
    omitidos, mayor_que_la_menor_barra = [], 0
    for fila in complejos:
        r = resumir_shap(booster, _dmatrix(fila, nombres), nombres)
        assert len(r.valores) == SHAP_TOP_K
        omitidos.append(abs(r.omitido))
        mayor_que_la_menor_barra += abs(r.omitido) > min(abs(v) for v in r.valores.values())
    # Medido el 2026-11-08: mediana 0,85 pK, máximo 1,14. Por eso la interfaz declara que las
    # barras no suman la salida; si esto dejara de ser cierto, la nota sobraría.
    assert float(np.median(omitidos)) > 0.3
    assert mayor_que_la_menor_barra >= 0.8 * len(complejos)


# ─────────────────────────────────────────────────────────────────────────────
# S06/S07 — la etiqueta sale del modelo; el orden de nombres es el del booster
# ─────────────────────────────────────────────────────────────────────────────


def test_s06_la_etiqueta_de_salida_depende_del_modelo():
    assert etiqueta_de_salida_shap(True) == "delta_pKi"
    assert etiqueta_de_salida_shap(False) == "pKi"


@pytest.mark.parametrize("nombre", _modelos_a())
def test_s07_el_orden_de_nombres_del_metadato_es_el_del_booster_y_el_modelo_es_de_delta(nombre):
    booster, nombres, meta = _modelo(nombre)
    assert list(booster.feature_names) == nombres, "el SHAP se emparejaría con otra característica"
    assert len(nombres) == EXPECTED_MODEL_A_FEATURES
    # Lo que la interfaz afirma («corrección sobre Vina») es cierto para cada modelo que se sirve.
    assert meta["params"].get("is_delta_model") is True
    assert etiqueta_de_salida_shap(bool(meta["params"].get("is_delta_model"))) == "delta_pKi"
