#!/usr/bin/env python3
"""SCI-B-148: relectura y adaptador externo de filas REC-01. No ejecuta main ni lee PDB."""
from __future__ import annotations
import argparse,ast,hashlib,json,math,platform
from collections import Counter,defaultdict
from datetime import datetime,timezone
from pathlib import Path
RAIZ=Path(__file__).resolve().parents[1]
def extraer(root):
    path=Path(root)/"scripts/run_rec01_grid_audit.py"
    tree=ast.parse(path.read_text(encoding="utf-8"))
    ns={"Counter":Counter,"defaultdict":defaultdict,"datetime":datetime,"timezone":timezone,
        "platform":platform,"math":math,"Path":Path,"PROJECT_ROOT":Path(root)}
    for n in tree.body:
        if isinstance(n,ast.Assign):
            try:val=ast.literal_eval(n.value)
            except (ValueError,TypeError):continue
            for target in n.targets:
                if isinstance(target,ast.Name):ns[target.id]=val
    for name in ["auditar_target","construir_metricas"]:
        node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
        mod=ast.Module(body=[ast.ImportFrom(module="__future__",names=[ast.alias(name="annotations")],level=0),node],type_ignores=[])
        exec(compile(ast.fix_missing_locations(mod),str(path),"exec"),ns)
    return ns
def normalizar_filas(filas):
    out=[]
    for fila in filas:
        r=dict(fila)
        exc=r.get("excepciones")
        if not isinstance(exc,list) or not all(isinstance(e,str) for e in exc):raise ValueError("Excepciones inválidas")
        esperado=bool(exc)
        if "es_excepcion" in r and (not isinstance(r["es_excepcion"],bool) or r["es_excepcion"]!=esperado):raise ValueError("Flag contradice excepciones")
        r["es_excepcion"]=esperado
        if not r.get("estrato"):raise ValueError("Sin estrato")
        out.append(r)
    return out
def sondas(root):
    ns=extraer(root);target={"pdb_id":"ABST","chain":"A","hotspots":[{"name":"A:1"}]*5}
    root=Path(root);ficticia=root/"data/no_se_abre_ABST.pdb"
    out=[]
    for modo in ["sin_pdb","parseo_vacio","parser_excepcion"]:
        def ligando(*args):
            if modo=="parser_excepcion":raise ValueError("control abstracto de parser")
            return {}
        ns["atomos_pesados_ligando"]=ligando;ns["parsear_ca_por_residuo"]=lambda *args:{}
        row=ns["auditar_target"](target,{} if modo=="sin_pdb" else {"ABST":ficticia},set(),set())
        try:
            ns["construir_metricas"]([row],0,0,{},{},"abstracto")
            old_error=None
        except KeyError as exc:old_error=str(exc)
        fixed=normalizar_filas([row]);met=ns["construir_metricas"](fixed,0,0,{},{},"abstracto")
        out.append({"modo":modo,"fila_original":row,"error_agregacion_original":old_error,
                    "con_adaptador":{"n_auditados":met["alcance"]["n_targets_catalogo"],
                       "excepciones":met["excepciones"],"estratos":met["estratos"]}})
    return out
def analizar(root):
    root=Path(root);p=root/"scripts/artifacts_science/REC-01/per_complex.jsonl"
    rows=[json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    normalized=normalizar_filas(rows)
    metrics=json.loads((p.parent/"metrics.json").read_text(encoding="utf-8"))
    ns=extraer(root)
    met=ns["construir_metricas"](normalized,metrics["alcance"]["n_pdb_ids_indexados"],0,{},{},"reanálisis externo")
    return {"SCI-B-148":{"n_filas_selladas":len(rows),"sin_flag_original":sum("es_excepcion" not in r for r in rows),
      "con_E6_E7":sum(any(e.startswith(("E6_","E7_")) for e in r["excepciones"]) for r in rows),
      "excepciones_reconstruidas":met["excepciones"],"excepciones_coinciden":met["excepciones"]==metrics["excepciones"],
      "sondas":sondas(root),"alcance":"El defecto se reproduce en tres rutas abstractas. La salida histórica se analiza separadamente; no se reauditan estructuras."},
      "fuentes":[{"ruta":x.relative_to(root).as_posix(),"sha256":hashlib.sha256(x.read_bytes()).hexdigest()} for x in [p,p.parent/"metrics.json",root/"scripts/run_rec01_grid_audit.py"]]}
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument("--raiz",type=Path,default=RAIZ);ap.add_argument("--salida",type=Path);a=ap.parse_args()
    txt=json.dumps(analizar(a.raiz),ensure_ascii=False,indent=2)+"\n"
    if a.salida:
        if a.salida.resolve().is_relative_to((a.raiz/"scripts/artifacts_science").resolve()):raise SystemExit("Salida sellada prohibida")
        a.salida.parent.mkdir(parents=True,exist_ok=True);a.salida.write_text(txt,encoding="utf-8")
    else:print(txt)
    return 0
if __name__=="__main__":raise SystemExit(main())

