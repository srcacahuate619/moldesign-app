from pathlib import Path
import copy,importlib.util,json,os,sys
import pytest
S=Path(__file__).resolve().parents[1]
if S.name=="scripts":S=S.parent
SPEC=importlib.util.spec_from_file_location("cohortes_fase1b",S/"scripts/analisis_fase1b_cohortes.py")
M=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(M)
ROOT=Path(os.environ.get("FASE1B_REPO_ROOT",S))
ART=ROOT/"scripts/artifacts_science"
def leer(exp,file="per_complex.jsonl"):
 p=ART/exp/file
 return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()] if file.endswith("jsonl") else json.loads(p.read_text(encoding="utf-8"))
@pytest.fixture(scope="module")
def resultados():return M.analizar(ROOT)["resultados"]
def test_106_desenlaces_y_falta_un_miembro(resultados):
 assert resultados["SCI-B-106"]["discrepancias_desenlace"]==[]
 rs=leer("MF-21")
 with pytest.raises(ValueError):M.exigir_miembros(M.indice(rs[:-1]),M.indice(rs))
def test_110_particiones_y_fuga(resultados):
 assert resultados["SCI-B-110"]=={"train":116,"valtest":87,"interseccion":0,"coinciden_con_particiones_RC_F0_SYM":True}
 rs=leer("MF-24");vt=leer("MF-24","per_complex_valtest.jsonl")
 with pytest.raises(ValueError):M.exigir_miembros(M.indice(vt+[rs[0]]),M.indice(vt))
def test_116_ausentes_pueden_cambiar_lectura(resultados):
 r=resultados["SCI-B-116"]
 assert r["cota_max_50"]==.1 and r["lectura_peor_caso"]=="MIXTO"
 assert r["cota_min_50"]<.1
def test_123_conteos_no_equivalentes(resultados):
 r=resultados["SCI-B-123"]
 assert r["n_miembros_fijados"]==50 and r["n_rdkit_le_6"]==48
 assert r["solo_torsdof"]==["1mmr","1nm6"]
def test_119_soporte_unidades_sin_certificar_atomos(resultados):
 r=resultados["SCI-B-119"]
 assert r["n_derivas"]==r["n_cor"]==48 and r["mediana_A"]==.3425
 assert r["cobertura_atomos_no_almacenada"] is True
def test_121_falta_semilla_y_score():
 rs=leer("MF-29-EMP-EXT")
 assert M.validar_semillas(rs,{42,7,13})==6
 rs[0]["brazo_masivo"]["corridas"].pop()
 with pytest.raises(ValueError):M.validar_semillas(rs,{42,7,13})
def test_121_score_no_finito():
 rs=leer("MF-29-EMP-EXT");rs[0]["brazo_masivo"]["corridas"][0]["score"]=float("nan")
 with pytest.raises(ValueError):M.validar_semillas(rs,{42,7,13})
def test_124_equivalencia_identidades_no_solo_n(resultados):
 assert resultados["SCI-B-124"]["miembros_iguales"]
 with pytest.raises(ValueError):M.exigir_miembros({"a","b"},{"a","c"})
def test_126_duplicados_y_fuente_incompleta(resultados):
 assert set(resultados["SCI-B-126"]["solapes"].values())=={48}
 with pytest.raises(ValueError):M.indice([{"pid":"a"},{"pid":"a"}])
 with pytest.raises(ValueError):M.exigir_subconjunto({"a","b"},{"a"})
def test_127_el_estrato_cambia_el_denominador(resultados):
 r=resultados["SCI-B-127"]
 assert r["TODOS"]["tabla"]==[[4,3],[2,39]]
 assert r["COLOCACION"]["tabla"]==[[4,3],[2,24]]
 assert r["TODOS"]["cociente_descriptivo"]!=r["COLOCACION"]["cociente_descriptivo"]
def test_128_falta_caso_y_cobertura_corrupta(resultados):
 assert resultados["SCI-B-128"]["cubiertos"]==107
 rs=leer("MF-33-EXT")
 with pytest.raises(ValueError):M.cobertura_estricta(rs[:-1],M.indice(rs))
 rs[0]["cubierto"]=not rs[0]["cubierto"]
 with pytest.raises(ValueError):M.cobertura_estricta(rs,M.indice(rs))
def test_130_tabla_y_control_sin_asociacion(resultados):
 assert resultados["SCI-B-130"]["estratos"]["TODOS"]["fisher_unilateral_exploratorio"]==pytest.approx(.000245386439573929)
 r=M.tabla_asociacion([{"e":a,"y":b} for a in [False,True] for b in [False,True]],lambda x:x["e"],lambda x:x["y"])
 assert r["cociente_descriptivo"]==1
def test_137_no_confundir_banda_alta_con_m_igual_K(resultados):
 r=resultados["SCI-B-137"]
 assert r["intercambiables"]==62 and r["m_igual_K"]==45
 assert r["bandas_entre_cubiertos"]["p_ge_08"]==64
 # El caso de banda alta m/K=4/5 sigue siendo intercambiable.
 rs=[{"pid":"x","n_docks":5,"corridas":[{"conf":str(i),"rmsd_min":1 if i<4 else 3} for i in range(5)],"cubierto":True}]
 r=M.probabilidad_orden(rs)
 assert r["bandas_entre_cubiertos"]["p_ge_08"]==1 and r["intercambiables"]==1
 rs[0]["corridas"].pop()
 with pytest.raises(ValueError):M.probabilidad_orden(rs)
def test_138_dos_peptidos_no_son_panel_completo(resultados):
 assert resultados["SCI-B-138"]["panel"]==55
 h=leer("MMGBSA-H13-AZUFRE-AMBER");panel=M.indice(leer("MMGBSA-H5-R1"))
 with pytest.raises(ValueError):M.gate_h13([r for r in h if r["caso"].startswith("pep_")],panel)
def test_138_windows_ausente():
 h=leer("MMGBSA-H13-AZUFRE-AMBER");h[0].pop("windows")
 with pytest.raises(ValueError):M.gate_h13(h,M.indice(leer("MMGBSA-H5-R1")))
def test_139_windows_y_errores_son_obligatorios(resultados):
 assert resultados["SCI-B-139"]["br_i_evaluables"]==23
 rs=leer("MMGBSA-H5-R1");m=leer("MMGBSA-H5-R1","metrics.json")
 m["pasa_gate_windows"]=False
 with pytest.raises(ValueError):M.gate_h5(rs,m)
 m["pasa_gate_windows"]=True;rs[0]["estado"]="error"
 with pytest.raises(ValueError):M.gate_h5(rs,m)
def test_139_no_confundir_sander_con_linux():
 rs=leer("MMGBSA-H5-R1");m=leer("MMGBSA-H5-R1","metrics.json")
 assert any(r.get("pasa_windows") is False for r in rs) # ese flag contrasta con Sander
 assert M.gate_h5(rs,m)["pasa_con_windows_y_sin_fallos"]
 rs[0]["condiciones"]["vacuum"]["windows"]["diferencia_energia_contra_openmm_linux_kcal_mol"]=1
 with pytest.raises(ValueError):M.gate_h5(rs,m)
def test_145_reproduccion_no_decorativa(resultados):
 assert resultados["SCI-B-145"]["n"]==203
 rs=leer("RC-F0-SYM");rs[0]["repro_ok"]=False
 with pytest.raises(ValueError):M.validar_simetria(rs)
 rs=leer("RC-F0-SYM");rs[0]["_poses"].pop()
 with pytest.raises(ValueError):M.validar_simetria(rs)
def test_153_la_fuente_actual_si_reproduce(resultados):
 r=resultados["SCI-B-153"]
 assert r["n_reproducen_fuente"]==116 and r["n_refs_distintas"]==0 and r["max_delta"]==0
 e={x["pid"]:x for x in r["ejemplos"]}
 assert e["1fkh"]["mf13"]==2.55 and e["1ew8"]["mf13"]==2.064
 # Sustituir el ejemplo narrativo por fuente debe revelar la discrepancia, no ocultarla.
 assert abs(-1.631-e["1fkh"]["rec09_con_aguas"])>.1
def test_162_marginales_no_todos_bajos(resultados):
 r=resultados["SCI-B-162"]
 assert r["por_estrato"]=={"0-4":4,"5-9":1,"10-14":1}
 assert not all(x["rot_bonds"]<=4 for x in r["detalle"])
 bad=leer("MF-01");bad.append(bad[0])
 with pytest.raises(ValueError):M.marginales(bad)
def test_165_endpoint_no_es_mediana_de_cambios(resultados):
 r=resultados["SCI-B-165"]["COLOCACION"]
 assert r["descenso_8_a_128"]==pytest.approx(.784) and r["lectura_regla_continua"]=="PRESUPUESTO"
 assert r["mediana_mejoras_pareadas"]==pytest.approx(.007) and r["variacion_neta_aciertos"]==0
 rs=leer("MF-25");rs[0]["barrido"].pop()
 with pytest.raises(ValueError):M.presupuesto(rs)


def test_153_flag_no_sustituye_comparacion_de_fuente():
 a=leer("MF-13");b=leer("REC-09")
 a[0]["score_cristal"]+=1
 r=M.comparar_scores(a,b)
 assert r["n_reproducen_fuente"]==115 and r["n_flags_true"]==116
 assert len(r["no_reproducen"])==1
 with pytest.raises(ValueError):M.comparar_scores(a,b[:-1])

def test_119_derivas_ausentes_no_pasan_con_la_mediana_de_un_subconjunto():
 rs=leer("MF-29-EMP-COR");keys=M.indice(rs)
 rs[0]["rmsd_deriva_local"]=None
 with pytest.raises(ValueError):M.resumen_derivas(rs,keys)
 with pytest.raises(ValueError):M.resumen_derivas(rs[1:],keys)
