from pathlib import Path
import importlib.util,json,os
S=Path(__file__).resolve().parents[1]
if S.name=="scripts":S=S.parent
spec=importlib.util.spec_from_file_location("proveniencia",S/"scripts/analisis_fase1b_procedencia.py")
M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)
ROOT=Path(os.environ.get("FASE1B_REPO_ROOT",S))
def test_huella_ve_una_mutacion(tmp_path):
 p=tmp_path/"entrada";p.write_text("antes");a=M.sha(p);p.write_text("despues")
 assert M.sha(p)!=a
def test_mf27_vacio_no_es_resultado_maquinable():
 r=M.manifestar(ROOT,"MF-27")
 assert r["salidas"]["metrics.json"]["vacio"] is True and r["salidas"]["per_complex.jsonl"]["filas_no_vacias"]==0
def test_no_inventar_huella_final_mf33():
 r=M.analizar(ROOT,False)["SCI-B-132"]["membresia_MF33"]
 assert r["sha256_actual"]==r["en_PRE"] and r["en_final"] is None

