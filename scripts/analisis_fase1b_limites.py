"""Inventario de evidencia faltante, sin parametrización, energía, docking ni entrenamiento."""
from pathlib import Path
import argparse,hashlib,json,math

def propiedades_almacenadas(r):
    return {"energia_finita_registrada":isinstance(r.get("energy_nagl_kjmol"),(int,float)) and math.isfinite(r["energy_nagl_kjmol"]),
            "xml_system_registrado":bool(r.get("system_xml") or r.get("system_xml_sha256")),
            "mapa_atomico_explicito_registrado":bool(r.get("atom_mapping") or r.get("heavy_atom_mapping"))}

def analizar(root):
    art=root/"scripts/artifacts_science";huellas={}
    def read(name,file="per_complex.jsonl"):
        p=art/name/file;huellas[p.relative_to(root).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
        return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()] if file.endswith("jsonl") else json.loads(p.read_text(encoding="utf-8"))
    mod=read("MF-33-EXT-MOD");ex=[r for r in mod if not r["en_cohorte_48"]]
    a=read("RS-03-PARAM-A");ma=read("RS-03-PARAM-A","metrics.json");b=read("RS-03-PARAM-B")
    bx={r["pid"]:r for r in b}
    common=[r for r in a if r["pid"] in bx]
    energia_b=[r for r in common if bx[r["pid"]].get("energy_finite") is True and all(isinstance(bx[r["pid"]].get(k),(int,float)) and math.isfinite(bx[r["pid"]][k]) for k in ["energy_nagl_kjmol","energy_am1bcc_kjmol"])]
    mapping_b=[r for r in common if bx[r["pid"]].get("atom_order_match") is True]
    info={"n_A":len(a),"gates_A_reportados":ma["gates"],"campos_openmm_system_A":sorted(set().union(*(set(r.get("openmm_system",{})) for r in a))),
          "propiedades_A":{k:sum(propiedades_almacenadas(r)[k] for r in a) for k in propiedades_almacenadas(a[0])},
          "n_B_con_energia_finita":len(energia_b),"n_B_con_mapeo_reportado":len(mapping_b),
          "A_sin_B":sorted({r["pid"] for r in a}-set(bx)),
          "mismo_sdf_A_B_comunes":all(r["sdf_sha256"]==bx[r["pid"]]["sdf_sha256"] for r in common),
          "duracion_historica_A_s":ma["duration_seconds"],
          "nota":"B aporta evidencia posterior del subconjunto que midió; no es una comprobación ejecutada por G5/G9 de A ni certifica el System original."}
    return {"inputs_sha256":huellas,"resultados":{
      "SCI-B-131":{"n_fuera_de_cohorte":len(ex),"n_no_nulos_por_predictor":{k:sum(r.get(k) is not None for r in ex) for k in ["torsdof","rot_bonds","diversidad","n_heavy","n_conformeros"]},
       "materiales_locales":{str(p): (root/p).exists() for p in ["data/pdbbind","data/molflex_train_v2"]},
       "computo_futuro":"Parseo y descriptores RDKit con entradas identificadas y nuevas salidas; no necesita repetir docking, sí recuperar las estructuras/conformeros que faltan."},
      "SCI-B-155":info,"SCI-B-156":info},
      "alcance":"Lectura de salidas históricas. No se calcula ninguna energía, carga ni correspondencia atómica nueva."}
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--raiz",type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument("--salida",type=Path,required=True);a=p.parse_args()
    if a.salida.resolve().is_relative_to((a.raiz/"scripts/artifacts_science").resolve()):raise ValueError("Salida sellada prohibida")
    r=analizar(a.raiz);a.salida.parent.mkdir(parents=True,exist_ok=True);a.salida.write_text(json.dumps(r,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("Inventario escrito en "+str(a.salida))
if __name__=="__main__":main()

