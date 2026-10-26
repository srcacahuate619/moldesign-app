"""Reanálisis de salidas existentes de Fase 1b. No importa ni ejecuta productores.
Uso: python-embed/python.exe -B scripts/analisis_fase1b_cohortes.py --salida <fuera_de_artifacts_science.json>
"""
from pathlib import Path
from statistics import median
from collections import Counter
import argparse, hashlib, json, math

def indice(filas, clave="pid"):
    out={}
    for r in filas:
        k=r.get(clave)
        if not isinstance(k,str) or not k or k in out:
            raise ValueError("Identidad ausente o duplicada: "+str(k))
        out[k]=r
    return out

def exigir_miembros(actual, esperado):
    a,b=set(actual),set(esperado)
    if a!=b: raise ValueError(f"Miembros distintos: faltan={sorted(b-a)}, sobran={sorted(a-b)}")
    return len(a)

def exigir_subconjunto(esperado, actual):
    if not set(esperado)<=set(actual):raise ValueError("Join incompleto")
    return len(set(esperado))

def validar_semillas(filas, esperado):
    for r in filas:
        cs=r["brazo_masivo"]["corridas"]
        ss=[c["seed"] for c in cs]
        if len(ss)!=len(set(ss)) or set(ss)!=set(esperado):
            raise ValueError("Semillas incompletas o duplicadas")
        if not all(isinstance(c.get("score"),(int,float)) and math.isfinite(c["score"]) for c in cs):
            raise ValueError("Score ausente o no finito")
    return sum(len(r["brazo_masivo"]["corridas"]) for r in filas)

def tabla_asociacion(filas, exposicion, evento):
    a=sum(bool(exposicion(r)) and bool(evento(r)) for r in filas)
    b=sum(bool(exposicion(r)) and not bool(evento(r)) for r in filas)
    c=sum(not bool(exposicion(r)) and bool(evento(r)) for r in filas)
    d=sum(not bool(exposicion(r)) and not bool(evento(r)) for r in filas)
    return {"tabla":[[a,b],[c,d]],"riesgo_expuestos":a/(a+b) if a+b else None,
            "riesgo_no_expuestos":c/(c+d) if c+d else None,
            "cociente_descriptivo":(a/(a+b))/(c/(c+d)) if a+b and c+d and c else None}

def cobertura_estricta(filas, esperado):
    ix=indice(filas);exigir_miembros(ix,esperado)
    if any(not isinstance(r.get("oraculo"),(int,float)) or not math.isfinite(r["oraculo"]) for r in filas):
        raise ValueError("Unidad no evaluable")
    for r in filas:
        if not isinstance(r.get("cubierto"),bool) or r["cubierto"]!=(r["oraculo"]<=2):
            raise ValueError("Etiqueta de cobertura contradictoria")
    n=sum(r["cubierto"] for r in filas)
    return {"n":len(filas),"cubiertos":n,"fraccion":n/len(filas),"pasa_liston":n/len(filas)>=.9}

def probabilidad_orden(filas):
    ix=indice(filas);detalle=[]
    for pid,r in sorted(ix.items()):
        cs=r["corridas"];K=r["n_docks"]
        if not cs or len(cs)!=K:raise ValueError("Docks incompletos")
        if len({c["conf"] for c in cs})!=K:raise ValueError("Conformero repetido")
        if any(c.get("rmsd_min") is None for c in cs):raise ValueError("RMSD ausente")
        m=sum(c["rmsd_min"]<=2 for c in cs)
        if (m>0)!=r["cubierto"]:raise ValueError("Cobertura incoherente")
        detalle.append({"pid":pid,"m":m,"K":K,"p_primero":m/K,"intercambiable":0<m<K})
    cub=[r for r in detalle if r["m"]]
    return {"n":len(detalle),"n_cubiertos":len(cub),
            "bandas_entre_cubiertos":{"p_ge_08":sum(r["p_primero"]>=.8 for r in cub),
              "02_lt_p_lt_08":sum(.2<r["p_primero"]<.8 for r in cub),
              "p_le_02":sum(r["p_primero"]<=.2 for r in cub)},
            "m_igual_K":sum(r["m"]==r["K"] for r in cub),
            "intercambiables":sum(r["intercambiable"] for r in cub),
            "fraccion_intercambiables":sum(r["intercambiable"] for r in cub)/len(cub),
            "condicion":"Permutación uniforme del multiconjunto finito de resultados observados; no probabilidad de éxito de un nuevo dock.",
            "detalle":detalle}

def validar_simetria(filas):
    indice(filas)
    if not all(r.get("repro_ok") is True and r.get("repro_err_max",math.inf)<=.001 for r in filas):
        raise ValueError("Reproducción de RMSD fallida")
    if any(r["n_recomputadas"]!=len(r["_poses"]) or r["n_recomputadas"]!=r["n_molflex_dataset"] for r in filas):
        raise ValueError("Cobertura de poses recomputables incompleta")
    return {"n":len(filas),"reproduccion_ok":True,"n_recomputadas":sum(r["n_recomputadas"] for r in filas),
            "n_otras_fuentes_sin_recomputar":sum(r["n_otras_fuentes"] for r in filas)}

def gate_h13(filas, panel):
    ix=indice(filas,"caso");pep=[r for r in filas if r["caso"].startswith("pep_")]
    exigir_miembros([r["caso"] for r in filas if not r["caso"].startswith("pep_")],panel)
    if len(pep)!=2 or not any(r.get("extension_maxima_A",0)>25 for r in pep):raise ValueError("Péptidos incompletos")
    for r in filas:
        if r["estado"]!="ok":raise ValueError("Fallo de ejecución")
        w=r.get("windows")
        if not w or w.get("mismas_entradas") is not True or w["diferencia_energia_kcal_mol"]>=1e-6 or w["diferencia_fuerza_kcal_mol_A"]>=1e-6:
            raise ValueError("Paridad entre plataformas ausente o fallida")
        if not r["geometria_imposible"] and r["resultado"]!="PASA":raise ValueError("Paridad física fallida")
    return {"n":len(ix),"panel":len(panel),"peptidos":len(pep),"geometria_indeterminada":sum(r["geometria_imposible"] for r in filas),"pasa_con_completitud":True,
            "limite":"Miembros contrastados con salida histórica H5-R1; no se fabrica una lista prerregistrada retroactiva."}

def gate_h5(filas, metricas):
    indice(filas)
    if any(r["estado"]!="ok" for r in filas) or metricas.get("fallos"):
        raise ValueError("Fallo de ejecución")
    if metricas.get("pasa_gate_windows") is not True:raise ValueError("Gate Windows no superado")
    if metricas.get("filtro_geometrico",{}).get("geometria_igual_en_windows") is not True:
        raise ValueError("Geometrías distintas")
    for r in filas:
        if r.get("mismas_entradas_en_windows") is not True:raise ValueError("Entradas distintas")
        for cond in ["vacuum","GBn2_no_SA"]:
            w=r["condiciones"][cond].get("windows")
            if not w or w["diferencia_energia_contra_openmm_linux_kcal_mol"]>=1e-6 or w["max_diferencia_fuerza_contra_openmm_linux_kcal_mol_A"]>=1e-6:
                raise ValueError("Paridad individual entre plataformas ausente o fallida")
    wp=metricas["windows_reproduce_linux"]
    if wp["comparaciones"]!=wp["esperadas"] or wp["comparaciones"]!=2*len(filas) or wp["mismas_entradas"]!=len(filas):
        raise ValueError("Comparaciones Windows incompletas")
    bri=[r for r in filas if ("Br" in r["halogenos"] or "I" in r["halogenos"])]
    ev=[r for r in bri if not r["indeterminado_por_geometria"]]
    if len(ev)<20 or any(r["gate_r1"]!="PASA" for r in ev):raise ValueError("Gate Br/I no superado")
    return {"n":len(filas),"br_i":len(bri),"br_i_evaluables":len(ev),"br_i_indeterminados":len(bri)-len(ev),
            "pasa_con_windows_y_sin_fallos":True}

def marginales(filas):
    indice(filas);det=[]
    for r in filas:
        if r["min_rmsd_union"] is None:raise ValueError("RMSD ausente")
        flex=r["min_rmsd"].get("flexible_redock")
        if r["min_rmsd_union"]<=2 and (flex is None or flex>2):
            rb=r["rot_bonds"]
            if not isinstance(rb,int):raise ValueError("Flexibilidad desconocida")
            grupo="0-4" if rb<=4 else "5-9" if rb<=9 else "10-14" if rb<=14 else ">=15"
            det.append({"pid":r["pid"],"rot_bonds":rb,"estrato":grupo,
                        "fuentes_cubren":[k for k,v in r["min_rmsd"].items() if v is not None and v<=2]})
    return {"n_marginales":len(det),"por_estrato":dict(Counter(r["estrato"] for r in det)),"detalle":det}

def presupuesto(filas):
    indice(filas);gs={}
    for est in sorted({r["estrato"] for r in filas}):
        group=[r for r in filas if r["estrato"]==est];vals={8:[],32:[],128:[]};hits={8:0,32:0,128:0}
        for r in group:
            bs={b["exh"]:b for b in r["barrido"]}
            if len(bs)!=3 or set(bs)!={8,32,128}:raise ValueError("Presupuesto incompleto")
            for k in vals:
                if "colocacion" not in bs[k]:raise ValueError("Respuesta ausente")
                vals[k].append(bs[k]["colocacion"]);hits[k]+=bool(bs[k]["acierta"])
        med={k:median(v) for k,v in vals.items()}
        dif=med[8]-med[128]
        gs[est]={"n":len(group),"medianas_colocacion":med,"descenso_8_a_128":dif,
                 "descenso_32_a_128":med[32]-med[128],"lectura_regla_continua":"PRESUPUESTO" if dif>.5 else "PAISAJE",
                 "aciertos":hits,"variacion_neta_aciertos":hits[128]-hits[8],
                 "mediana_mejoras_pareadas":median(a-b for a,b in zip(vals[8],vals[128]))}
    return gs

def resumen_derivas(filas,esperado):
    exigir_miembros(indice(filas),esperado)
    ds=[r.get("rmsd_deriva_local") for r in filas]
    if any(not isinstance(d,(int,float)) or not math.isfinite(d) or d<0 for d in ds):
        raise ValueError("Deriva ausente o inválida: no certificar soporte parcial")
    return {"n_cor":len(filas),"n_derivas":len(ds),"mediana_A":median(ds),"max_A":max(ds),
            "n_mayores_2A":sum(d>2 for d in ds),
            "ids_mayores_2A":[r["pid"] for r in filas if r["rmsd_deriva_local"]>2],
            "cobertura_atomos_no_almacenada":True}

def comparar_scores(mf13,rec09):
    d13=indice(mf13);r09=indice(rec09);exigir_miembros(d13,r09);compar=[]
    for pid,r in sorted(r09.items()):
        native=d13[pid]["score_cristal"];withwater=r["score_con_aguas"];ref=r["score_cristal_mf13"]
        delta=abs(withwater-native)
        compar.append({"pid":pid,"mf13":native,"rec09_referencia":ref,"rec09_con_aguas":withwater,"delta_actual":delta,
                       "delta_almacenado":r["g1_delta_vs_mf13"],"flag_almacenado":r["g1_reproduce"],
                       "reproduce_fuente_mf13":delta<=.1,"ref_coincide_fuente":abs(ref-native)<1e-6})
    return {"n":len(compar),"n_reproducen_fuente":sum(r["reproduce_fuente_mf13"] for r in compar),
                      "n_flags_true":sum(r["flag_almacenado"] for r in compar),
                      "n_refs_distintas":sum(not r["ref_coincide_fuente"] for r in compar),
                      "max_delta":max(r["delta_actual"] for r in compar),
                      "no_reproducen":[r for r in compar if not r["reproduce_fuente_mf13"]],
                      "ejemplos":[r for r in compar if r["pid"] in ["1fkh","1ew8","1eld"]],"detalle":compar}

def analizar(raiz):
    art=raiz/"scripts/artifacts_science";inputs={}
    def cargar(exp,archivo="per_complex.jsonl"):
        p=art/exp/archivo;inputs[p.relative_to(raiz).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
        if archivo.endswith(".jsonl"):return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
        return json.loads(p.read_text(encoding="utf-8"))
    out={}
    c=cargar("MF-02F","cohorte.json");expected=c["cohorte_colocacion"]+c["control_cubiertos"]
    m21=cargar("MF-21");m09=cargar("MF-09")
    exigir_miembros(indice(m21),expected);exigir_miembros(indice(m09),expected)
    if any(type(r.get("cubierto")) is not bool for r in m21):raise ValueError("Desenlace sin clasificar")
    disagree=[r["pid"] for r in m21 if r["cubierto"]!=indice(m09)[r["pid"]]["existe_pose_buena"]]
    out["SCI-B-106"]={"previstos":len(expected),"mf21":len(m21),"mf09":len(m09),"discrepancias_desenlace":disagree,
                       "grupos":dict(Counter(r["cubierto"] for r in m21)),"errores":sum("error" in r for r in m21)}
    sym=cargar("RC-F0-SYM");splits={s:{r["pid"] for r in sym if r["split"]==s} for s in ["train","val","test"]}
    train=cargar("MF-24");vt=cargar("MF-24","per_complex_valtest.jsonl")
    exigir_miembros(indice(train),splits["train"]);exigir_miembros(indice(vt),splits["val"]|splits["test"])
    if set(indice(train))&set(indice(vt)):raise ValueError("Solape train/valtest")
    if any(r.get("colocacion") is None or r.get("n_torsiones") is None for r in train+vt):raise ValueError("Filas excluibles")
    out["SCI-B-110"]={"train":len(train),"valtest":len(vt),"interseccion":0,"coinciden_con_particiones_RC_F0_SYM":True}
    base=cargar("MF-29-EMP");bx=indice(base);co=cargar("MF-29-EMP","cohorte.json")["cohorte"];exigir_miembros(bx,indice(co))
    ok=[r for r in base if "masivo_mejora" in r];missing=sorted(set(bx)-set(indice(ok)));mej=sum(r["masivo_mejora"] for r in ok);n=len(base)
    out["SCI-B-116"]={"planificados":n,"completos":len(ok),"eventos_completos":mej,"ausentes":missing,
                      "f_completos":mej/len(ok),"cota_min_50":mej/n,"cota_max_50":(mej+len(missing))/n,
                      "lectura_peor_caso":"MIXTO" if (mej+len(missing))/n>=.1 else "OBJETIVO"}
    out["SCI-B-123"]={"n_miembros_fijados":len(co),"todos_torsdof_le_6":all(r["torsdof"]<=6 for r in co),
                      "n_rdkit_le_6":sum(r["n_torsiones_rdkit"]<=6 for r in co),
                      "solo_torsdof":[r["pid"] for r in co if r["n_torsiones_rdkit"]>6],
                      "expirados_coinciden_con_solo_torsdof":set(missing)=={r["pid"] for r in co if r["n_torsiones_rdkit"]>6}}
    cor=cargar("MF-29-EMP-COR");exigir_miembros(indice(cor),indice(ok))
    out["SCI-B-119"]=resumen_derivas(cor,indice(ok))
    ext=cargar("MF-29-EMP-EXT");exigir_miembros(indice(ext),missing);seeds=validar_semillas(ext,{42,7,13})
    exigir_miembros(list(indice(ok))+list(indice(ext)),bx)
    out["SCI-B-121"]={"recuperados":len(ext),"semillas_con_score":seeds,"union":len(ok)+len(ext),
                      "mejoran":mej+sum(r["masivo_mejora"] for r in ext),"fraccion":(mej+sum(r["masivo_mejora"] for r in ext))/n}
    m33=cargar("MF-33");d33=indice(m33);exigir_miembros(d33,expected)
    cols=[r for r in m33 if r["estrato"]=="COLOCACION"];old=[r for r in m09 if r["estrato"]=="COLOCACION"]
    exigir_miembros(indice(cols),indice(old))
    a=sum(r["existe_pose_buena"] for r in old);b=sum(r["brazos"]["B"]["alcanza"] for r in cols)
    out["SCI-B-124"]={"miembros_iguales":True,"n":len(cols),"mf09_cubiertos":a,"mf33_B_cubiertos":b,"cociente":b/a,
                      "limite":"Cociente descriptivo entre protocolos distintos; no factor causal de un componente."}
    sources={k:indice(cargar(k)) for k in ["MF-14","REC-08-EXT","REC-09"]}
    ov={k:exigir_subconjunto(d33,v) for k,v in sources.items()}
    cru=cargar("MF-33-CRUCES");exigir_miembros(indice(cru),d33)
    out["SCI-B-126"]={"base":len(d33),"solapes":ov,"duplicados":0,"salida_cruces":len(cru)}
    out["SCI-B-127"]={k:tabla_asociacion([r for r in cru if k=="TODOS" or r["estrato"]==k],
                                      lambda r:not r["B_alcanza"],lambda r:r["absurdo"])
                       for k in ["TODOS","COLOCACION","CONTROL"]}
    cov=cargar("MF-33-EXT");mf13=cargar("MF-13");out["SCI-B-128"]=cobertura_estricta(cov,indice(mf13))
    r09=sources["REC-09"];exigir_miembros(indice(cov),r09)
    joined=[dict(r,absurdo=r09[r["pid"]]["absurdo"]) for r in cov]
    from scipy.stats import fisher_exact
    ta={k:tabla_asociacion([r for r in joined if k=="TODOS" or r["estrato"]==k],lambda r:r["absurdo"],lambda r:not r["cubierto"])
        for k in ["TODOS","COLOCACION","CONTROL","RESTO"]}
    for t in ta.values():t["fisher_unilateral_exploratorio"]=float(fisher_exact(t["tabla"],alternative="greater").pvalue)
    out["SCI-B-130"]={"post_hoc":True,"estratos":ta}
    out["SCI-B-137"]=probabilidad_orden(cov)
    h5=cargar("MMGBSA-H5-R1");h13=cargar("MMGBSA-H13-AZUFRE-AMBER")
    out["SCI-B-138"]=gate_h13(h13,indice(h5))
    out["SCI-B-139"]=gate_h5(h5,cargar("MMGBSA-H5-R1","metrics.json"))
    out["SCI-B-145"]=validar_simetria(sym)
    out["SCI-B-153"]=comparar_scores(mf13,list(r09.values()))
    out["SCI-B-162"]=marginales(cargar("MF-01"))
    out["SCI-B-165"]=presupuesto(cargar("MF-25"))
    return {"metodo":"Solo lectura, reanálisis posterior al resultado; no re-sellado ni nueva ejecución científica.","inputs_sha256":inputs,"resultados":out}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--raiz",type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument("--salida",type=Path,required=True)
    a=p.parse_args();root=a.raiz.resolve();dest=a.salida.resolve()
    if dest==root/"scripts/artifacts_science" or root/"scripts/artifacts_science" in dest.parents:raise ValueError("Salida en artefactos sellados")
    result=analizar(root);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"salida":str(dest),"registros":list(result["resultados"])},ensure_ascii=False))
if __name__=="__main__":main()

