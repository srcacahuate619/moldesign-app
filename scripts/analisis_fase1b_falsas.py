#!/usr/bin/env python3
"""Relecturas de SCI-B-133/144/159/164. Sólo salidas selladas y AST; sin modelos ni docking."""
from __future__ import annotations
import argparse, ast, hashlib, json, math
from collections import Counter
from pathlib import Path
RAIZ=Path(__file__).resolve().parents[1]
BASE=Path("scripts/artifacts_science")
def jsonl(p):
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
def fuente(p,root):
    return {"ruta":p.relative_to(root).as_posix(),"sha256":hashlib.sha256(p.read_bytes()).hexdigest()}
def ajustar_geometrica(filas):
    if not filas: raise ValueError("Sin unidades")
    ids=[r["pid"] for r in filas]
    if len(set(ids))!=len(ids): raise ValueError("PID duplicado")
    eventos=[]; censuras=[]; ks=[]
    for r in filas:
        k=r.get("n_conformeros"); t=r.get("primer_dock_que_cubre"); cub=r.get("cubierto_ensemble")
        if not isinstance(k,int) or isinstance(k,bool) or k<1: raise ValueError("K inválido")
        if cub is True:
            if not isinstance(t,int) or isinstance(t,bool) or not 1<=t<=k: raise ValueError("Evento sin índice válido")
            eventos.append(t)
        elif cub is False:
            if t is not None: raise ValueError("Censura con evento")
            censuras.append(k)
        else: raise ValueError("Desenlace ausente")
        ks.append(k)
    exposicion=sum(eventos)+sum(censuras)
    p=len(eventos)/exposicion
    ingenua=len(eventos)/sum(eventos) if eventos else None
    curva=[]
    for k in range(1,max(ks)+1):
        curva.append({"k":k,"n":len(filas),"cubiertos_observados":sum(t<=k for t in eventos),
          "cobertura_observada":sum(t<=k for t in eventos)/len(filas),
          "cobertura_modelo_K_heterogeneo":sum(1-(1-p)**min(k,ki) for ki in ks)/len(ks)})
    return {"n":len(filas),"eventos":len(eventos),"censuras":len(censuras),
      "suma_primeros_aciertos":sum(eventos),"exposicion_censurada":sum(censuras),
      "exposicion_total":exposicion,"p_condicionado_solo_cubiertos_1_media":ingenua,
      "p_MLE_censura_derecha":p,"K_min":min(ks),"K_max":max(ks),"K_frecuencias":dict(sorted(Counter(ks).items())),
      "curva":curva,
      "condicion":"Modelo homogéneo e independiente; K observado fija la censura. No valida homogeneidad ni una regla de parada.",
      "contraste_formal":"No se calcula p de bondad de ajuste: las coberturas acumuladas no son observaciones independientes y el contraste previo no fijó esta relectura."}
def contar_simetria(filas):
    ids=[r["pid"] for r in filas]
    if len(set(ids))!=len(ids): raise ValueError("PID duplicado")
    out={}
    for row in filas:
        sp=row["split"];d=out.setdefault(sp,{"complejos":0,"poses_recalculadas":0,"positivas_ingenuas":0,
            "positivas_corregidas":0,"negativas_que_pasan_a_positivas":0,"positivas_que_pasan_a_negativas":0,
            "poses_otras_fuentes_sin_recalcular":0,"cubiertos_ingenuos_con_otras":0,"cubiertos_corregidos_con_otras":0})
        d["complejos"]+=1;d["poses_otras_fuentes_sin_recalcular"]+=row.get("n_otras_fuentes",0)
        seen=set();orig=[];corr=[]
        for p in row.get("_poses",[]):
            key=(p["file_stem"],p["model_idx"])
            if key in seen: raise ValueError("Pose duplicada")
            seen.add(key)
            a,b=p.get("positiva"),p.get("positiva_sym")
            if not isinstance(a,bool) or not isinstance(b,bool): raise ValueError("Etiqueta no booleana")
            for val,flag in [(p["rmsd"],a),(p["rmsd_sym"],b)]:
                if abs(val-2.0)>0.00051 and (val<=2.0)!=flag: raise ValueError("Etiqueta contradice RMSD redondeado")
            orig.append(p["rmsd"]);corr.append(p["rmsd_sym"])
            d["poses_recalculadas"]+=1;d["positivas_ingenuas"]+=a;d["positivas_corregidas"]+=b
            d["negativas_que_pasan_a_positivas"]+=(not a and b)
            d["positivas_que_pasan_a_negativas"]+=(a and not b)
        other=row.get("mejor_otras_fuentes")
        if other is not None: orig.append(other);corr.append(other)
        d["cubiertos_ingenuos_con_otras"]+=bool(orig and min(orig)<=2.0)
        d["cubiertos_corregidos_con_otras"]+=bool(corr and min(corr)<=2.0)
    for d in out.values():
        a,b=d["positivas_ingenuas"],d["positivas_corregidas"];gan=d["negativas_que_pasan_a_positivas"]
        d["aumento_relativo_sobre_positivas_originales"]= (b-a)/a if a else None
        d["fraccion_de_positivas_corregidas_antes_negativas"]=gan/b if b else None
        d["alcance"]="Etiquetas almacenadas de poses recomputables; las demás fuentes conservan su RMSD anterior."
    return out
def interseccion(a,b):
    if len(a)!=2 or len(b)!=2 or a[0]>a[1] or b[0]>b[1]:raise ValueError("Intervalo inválido")
    lo,hi=max(a[0],b[0]),min(a[1],b[1])
    return {"intervalo":[lo,hi] if lo<=hi else None,"longitud":max(0.0,hi-lo),"solapan":lo<=hi}
def contrato_repro(texto):
    tree=ast.parse(texto)
    main=next(n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name=="main")
    llamadas_entrenar=[n.lineno for n in ast.walk(main) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=="entrenar_clon"]
    bloques=[n for n in ast.walk(main) if isinstance(n,ast.If) and ast.unparse(n.test)=="args.repro"]
    spot=next(n for n in bloques if any(isinstance(c,ast.Name) and c.id=="spot_ok" for c in ast.walk(n)))
    abortos=[n.lineno for n in ast.walk(spot) if isinstance(n,(ast.Raise,ast.Assert,ast.Return))]
    escrituras=[n.lineno for n in ast.walk(main) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id in {"escribir_json","escribir_jsonl"} and n.lineno>1000]
    return {"entrenar_clon_lineas":llamadas_entrenar,"spot_repro_linea":spot.lineno,
      "abortos_en_spot":abortos,"spot_fallido_no_aborta":not abortos,
      "escritura_salidas_antes_spot":any(i<spot.lineno for i in escrituras),
      "alcance":"AST del contrato; no se entrenó ni se comprobó determinismo físico."}
def analizar(root):
    root=Path(root);files={}
    for name,rel in {"mod":"MF-33-EXT-MOD/per_complex.jsonl","mod_metrics":"MF-33-EXT-MOD/metrics.json",
       "sym":"RC-F0-SYM/per_complex.jsonl","mf26":"MF-26/metrics.json"}.items(): files[name]=root/BASE/rel
    files["rs04"]=root/"scripts/run_rs04_oof.py"
    geo=ajustar_geometrica(jsonl(files["mod"]))
    mod=json.loads(files["mod_metrics"].read_text(encoding="utf-8"))
    geo["p_publicada"]=mod["BLOQUE_4_ACIERTO_VS_DOSIS"]["p_estimada_por_conformero"]
    met=json.loads(files["mf26"].read_text(encoding="utf-8"))
    train=met["curva_conversion_por_torsiones"]["9-12"]; val=met["validacion_val_test"]["curva_conversion_por_torsiones"]["9-12"]
    return {"SCI-B-133":geo,"SCI-B-144":contar_simetria(jsonl(files["sym"])),
      "SCI-B-159":contrato_repro(files["rs04"].read_text(encoding="utf-8")),
      "SCI-B-164":{"train":train,"val_test":val,"interseccion_Wilson_sin_redondeo_narrativo":interseccion(train["wilson95"],val["wilson95"]),
        "interseccion_citada_en_paper":interseccion([0.097,0.419],[0.342,0.742]),
        "interpretacion":"El solapamiento no es una prueba de igualdad ni reemplaza un contraste directo."},
      "fuentes":[fuente(p,root) for p in files.values()]}
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument("--raiz",type=Path,default=RAIZ);ap.add_argument("--salida",type=Path);a=ap.parse_args()
    result=analizar(a.raiz);text=json.dumps(result,ensure_ascii=False,indent=2)+"\n"
    if a.salida:
        if a.salida.resolve().is_relative_to((a.raiz/"scripts/artifacts_science").resolve()):raise SystemExit("Salida sellada prohibida")
        a.salida.parent.mkdir(parents=True,exist_ok=True);a.salida.write_text(text,encoding="utf-8")
    else:print(text)
    return 0
if __name__=="__main__":raise SystemExit(main())

