#!/usr/bin/env python3
"""Procedencia histórica del lote1b: sólo manifiestos,salidas y Git de lectura; no re-sella."""
from __future__ import annotations
import argparse,ast,hashlib,json,subprocess
from pathlib import Path
RAIZ=Path(__file__).resolve().parents[1];BASE=Path("scripts/artifacts_science")
UNIDADES={
"SCI-B-107":["MF-21"],"SCI-B-111":["MF-24"],"SCI-B-112":["MF-27"],
"SCI-B-113":["MF-27"],"SCI-B-115":["MF-28-PRE","MF-28"],
"SCI-B-117":["MF-29-EMP"],"SCI-B-118":["MF-29-EMP-COR-PRE","MF-29-EMP-COR"],
"SCI-B-120":["MF-29-EMP-COR"],"SCI-B-122":["MF-29-EMP-EXT"],
"SCI-B-129":["MF-33-EXT"],"SCI-B-132":["MF-33-EXT-MOD-PRE","MF-33-EXT-MOD"],
"SCI-B-134":["MF-33-EXT-MOD-PRE","MF-33-EXT-MOD"],"SCI-B-135":["MF-33-EXT-MOD-PRE","MF-33-EXT-MOD"],
"SCI-B-141":["PREP-01"],"SCI-B-149":["REC-01"],"SCI-B-157":["RS-09"]}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def manifestar(root,name):
    folder=Path(root)/BASE/name;m=json.loads((folder/"manifest.json").read_text(encoding="utf-8"))
    d={"id":name,"manifest_sha256":sha(folder/"manifest.json"),
       "created_at":m.get("created_at"),"sealed_at":m.get("sealed_at"),"finished_at":m.get("finished_at"),
       "git_state":m.get("git_state"),"dependencies":m.get("dependencies"),
       "hashes":{k:m.get(k,{}) for k in ["dataset_hashes","model_hashes","binary_hashes","assets_hashes"]},
       "seal_maintenance":m.get("seal_maintenance"),"salidas":{}}
    for file in ["metrics.json","per_complex.jsonl"]:
        p=folder/file
        if not p.exists():d["salidas"][file]={"existe":False};continue
        data=p.read_text(encoding="utf-8")
        out={"existe":True,"bytes":p.stat().st_size,"sha256":sha(p)}
        if file.endswith(".jsonl"):out["filas_no_vacias"]=sum(bool(l.strip()) for l in data.splitlines())
        else:
            obj=json.loads(data);out.update(tipo=type(obj).__name__,vacio=(not bool(obj)))
        d["salidas"][file]=out
    return d
def leer_git(root,path):
    cp=subprocess.run(["git","--no-optional-locks","-C",str(root),"log","--reverse","--diff-filter=A","--format=%H %cI","--",path],capture_output=True,text=True,encoding="utf-8")
    if cp.returncode:raise RuntimeError(cp.stderr)
    return cp.stdout.strip().splitlines()
def analizar(root,con_git=True):
    root=Path(root);out={id:{"manifiestos":[manifestar(root,n) for n in ns]} for id,ns in UNIDADES.items()}
    pre=root/BASE/"MF-33-EXT-MOD-PRE/manifest.json";fin=root/BASE/"MF-33-EXT-MOD/manifest.json"
    a=json.loads(pre.read_text(encoding="utf-8"));b=json.loads(fin.read_text(encoding="utf-8"))
    key="scripts/artifacts_science/MF-33/per_complex.jsonl";p=root/key
    out["SCI-B-132"]["membresia_MF33"]={"sha256_actual":sha(p),"en_PRE":a.get("dataset_hashes",{}).get(key),"en_final":b.get("dataset_hashes",{}).get(key)}
    out["SCI-B-149"]["G5_publicado"]=json.loads((root/BASE/"REC-01/metrics.json").read_text(encoding="utf-8"))["gates"]["G5_solo_lectura"]
    # El estado actual de la copia no acredita el previous_hash histórico.
    p=root/"scripts/historical_sources/PREP-01/preparer.py"
    out["SCI-B-141"]["copia_preparer"]={"ruta":p.relative_to(root).as_posix(),"existe":p.exists(),"sha256":sha(p) if p.exists() else None}
    out["SCI-B-123"]={"cohorte_actual_sha256":sha(root/BASE/"MF-29-EMP/cohorte.json")}
    if con_git:
        rel="scripts/artifacts_science/MF-29-EMP/cohorte.json"
        commits=leer_git(root,rel)
        cp=subprocess.run(["git","--no-optional-locks","-C",str(root),"show",commits[0].split()[0]+":"+rel],capture_output=True)
        if cp.returncode:raise RuntimeError("No se pudo leer la cohorte del primer commit")
        now=(root/rel).read_bytes()
        out["SCI-B-123"].update(
            primer_anclaje_cohorte=commits,
            primer_anclaje_resultados=leer_git(root,"scripts/artifacts_science/MF-29-EMP/per_complex.jsonl"),
            sha256_cohorte_primer_commit=hashlib.sha256(cp.stdout).hexdigest(),
            mismos_bytes_normalizando_EOL=cp.stdout.replace(b"\r\n",b"\n")==now.replace(b"\r\n",b"\n"),
            ids_primer_commit=[r["pid"] for r in json.loads(cp.stdout)["cohorte"]],
            limite="El commit de miembros precede al cierre, pero no acredita por sí solo un compromiso anterior al inicio de la ejecución.")
        out["SCI-B-118"]["anclajes_git"]={rel:leer_git(root,rel) for rel in [
            "scripts/artifacts_science/MF-29-EMP-COR-PRE/manifest.json",
            "scripts/artifacts_science/MF-29-EMP-COR/manifest.json",
            "scripts/artifacts_science/MF-29-EMP-COR/per_complex.jsonl"]}
    out["alcance"]="Inventario de vínculos presentes/ausentes; ninguna firma o hash contemporáneo faltante se reconstruye retrospectivamente. SCI-B-045 gobierna sellos nuevos desde2026-10-23."
    return out
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument("--raiz",type=Path,default=RAIZ);ap.add_argument("--salida",type=Path);ap.add_argument("--sin-git",action="store_true");a=ap.parse_args()
    txt=json.dumps(analizar(a.raiz,not a.sin_git),ensure_ascii=False,indent=2)+"\n"
    if a.salida:
        if a.salida.resolve().is_relative_to((a.raiz/"scripts/artifacts_science").resolve()):raise SystemExit("Salida sellada prohibida")
        a.salida.parent.mkdir(parents=True,exist_ok=True);a.salida.write_text(txt,encoding="utf-8")
    else:print(txt)
    return 0
if __name__=="__main__":raise SystemExit(main())

