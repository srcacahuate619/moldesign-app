"""Reproduce cuatro FALSA y prueba que los analizadores ven cambios; sólo relectura."""
import copy,json,os,sys
from pathlib import Path
import pytest
HERE=Path(__file__).resolve().parents[1]
SCRIPTS=HERE if (HERE/"analisis_fase1b_falsas.py").exists() else HERE/"scripts"
sys.path.insert(0,str(SCRIPTS))
import analisis_fase1b_falsas as a
ROOT=Path(os.environ.get("FASE1B_REPO_ROOT",str(SCRIPTS.parent)))
def test_mle_incluye_censura_y_K_variable():
    rows=[{"pid":"a","n_conformeros":3,"cubierto_ensemble":True,"primer_dock_que_cubre":1},
          {"pid":"b","n_conformeros":4,"cubierto_ensemble":False,"primer_dock_que_cubre":None}]
    r=a.ajustar_geometrica(rows)
    assert r["p_MLE_censura_derecha"]==pytest.approx(0.2)
    assert r["p_condicionado_solo_cubiertos_1_media"]==1
    assert r["curva"][-1]["cobertura_modelo_K_heterogeneo"]==pytest.approx(((1-.8**3)+(1-.8**4))/2)
def test_133_relectura_sellada():
    r=a.analizar(ROOT)["SCI-B-133"]
    assert (r["n"],r["eventos"],r["censuras"],r["exposicion_total"])==(116,107,9,377)
    assert r["p_MLE_censura_derecha"]==pytest.approx(107/377)
    assert round(r["p_condicionado_solo_cubiertos_1_media"],4)==r["p_publicada"]
def test_133_negativo_cambiar_exposicion_de_un_fallo_cambia_ajuste():
    rows=a.jsonl(ROOT/a.BASE/"MF-33-EXT-MOD/per_complex.jsonl")
    original=a.ajustar_geometrica(rows)
    changed=copy.deepcopy(rows);next(r for r in changed if not r["cubierto_ensemble"])["n_conformeros"]+=10
    assert a.ajustar_geometrica(changed)["p_MLE_censura_derecha"]<original["p_MLE_censura_derecha"]
def test_133_falla_con_evento_fuera_de_K_o_pid_duplicado():
    x={"pid":"x","n_conformeros":1,"cubierto_ensemble":True,"primer_dock_que_cubre":2}
    with pytest.raises(ValueError):a.ajustar_geometrica([x])
    x["primer_dock_que_cubre"]=1
    with pytest.raises(ValueError):a.ajustar_geometrica([x,x])
def test_144_reproduce_las_tres_tablas_y_denomina_bien():
    r=a.analizar(ROOT)["SCI-B-144"]
    assert [(r[k]["positivas_ingenuas"],r[k]["positivas_corregidas"]) for k in ["train","val","test"]]==[(357,432),(187,196),(216,252)]
    assert r["train"]["fraccion_de_positivas_corregidas_antes_negativas"]==pytest.approx(75/432)
    assert r["train"]["aumento_relativo_sobre_positivas_originales"]==pytest.approx(75/357)
def test_144_negativo_etiqueta_falsa_y_duplicado_se_detectan():
    rows=a.jsonl(ROOT/a.BASE/"RC-F0-SYM/per_complex.jsonl")
    x=copy.deepcopy(rows);x[0]["_poses"][0]["positiva"]=not x[0]["_poses"][0]["positiva"]
    with pytest.raises(ValueError):a.contar_simetria(x)
    x=copy.deepcopy(rows);x[0]["_poses"].append(x[0]["_poses"][0])
    with pytest.raises(ValueError):a.contar_simetria(x)
def test_159_el_spot_actual_no_falla_y_se_escribio_antes():
    text=(ROOT/"scripts/run_rs04_oof.py").read_text(encoding="utf-8")
    r=a.contrato_repro(text)
    assert len(r["entrenar_clon_lineas"])==2
    assert r["spot_fallido_no_aborta"] is True
    assert r["escritura_salidas_antes_spot"] is True
def test_159_control_negativo_el_detector_ve_un_aborto_real():
    text=(ROOT/"scripts/run_rs04_oof.py").read_text(encoding="utf-8")
    changed=text.replace("        spot_ok = True","        spot_ok = True\n        if not spot_ok:\n            raise RuntimeError('fallo')")
    assert a.contrato_repro(changed)["spot_fallido_no_aborta"] is False
def test_164_interseccion_de_los_dos_intervalos_sellados():
    r=a.analizar(ROOT)["SCI-B-164"]["interseccion_Wilson_sin_redondeo_narrativo"]
    assert r["intervalo"]==[0.3421,0.419]
    assert r["longitud"]==pytest.approx(0.0769)
def test_164_control_negativo_no_declara_solape_en_intervalos_disjuntos():
    assert a.interseccion([0.1,0.2],[0.3,0.4])=={"intervalo":None,"longitud":0.0,"solapan":False}

