from pathlib import Path
import importlib.util,os
S=Path(__file__).resolve().parents[1]
if S.name=="scripts":S=S.parent
spec=importlib.util.spec_from_file_location("limites",S/"scripts/analisis_fase1b_limites.py")
M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)
ROOT=Path(os.environ.get("FASE1B_REPO_ROOT",S))
def test_flag_de_gate_y_conteo_de_particulas_no_prueban_energia():
 p=M.propiedades_almacenadas({"G9":True,"atom_order_hash":"NOT_A_BIJECTION","openmm_system":{"n_particles":40,"n_forces":5,"serialization_time_s":1}})
 assert not any(p.values())
 p=M.propiedades_almacenadas({"energy_nagl_kjmol":1.0,"system_xml_sha256":"abc","heavy_atom_mapping":[[0,0]]})
 assert all(p.values()) # Sólo presencia reportada: no valida autenticidad física ni el mapa.
def test_prospectivo_no_fue_medido():
 r=M.analizar(ROOT)["resultados"]["SCI-B-131"]
 assert r["n_fuera_de_cohorte"]==68
 assert r["n_no_nulos_por_predictor"]=={"torsdof":0,"rot_bonds":0,"diversidad":0,"n_heavy":0,"n_conformeros":68}
def test_A_no_satisface_por_si_solo_promesa():
 r=M.analizar(ROOT)["resultados"]["SCI-B-155"]
 assert r["n_A"]==116 and not any(r["propiedades_A"].values())
 assert r["n_B_con_energia_finita"]==115 and len(r["A_sin_B"])==1

