"""MET-01-R1: the MET-01 producer, re-run on a product that keeps the cofactor whitelist.

Generated from scripts/artifacts_science/MET-01-ION-DEL-SITIO/source/met01.py by counted
substitutions (see CAMBIOS_DESDE_MET01.md). Same population, configuration, seeds, gate,
RMSD and validity rules. No product patches."""
from __future__ import annotations
import argparse, collections, gzip, hashlib, importlib.util, json, math, os
import subprocess, sys, time, urllib.request, urllib.error
from pathlib import Path
from datetime import datetime, timezone

ROOT=next(p for p in Path(__file__).resolve().parents if (p/'curated_targets.json').is_file())
EXP=ROOT/'scripts/artifacts_science/MET-01-R1-ION-DEL-SITIO'
MET01=ROOT/'scripts/artifacts_science/MET-01-ION-DEL-SITIO'
PRE=(EXP/'entrada') if (EXP/'manifest.json').exists() else ROOT/'scripts/met01r1'
WORK=(EXP/'_work') if (EXP/'manifest.json').exists() else PRE/'tmp/_work'
SOURCE=Path(__file__).resolve().parent
PRODUCT='9ce8b10490fcdd1c21b5dc0cf1efa8f3eae76d70'
os.environ['PYTHONDONTWRITEBYTECODE']='1'
sys.dont_write_bytecode=True
sys.path.insert(0,str(ROOT/'scripts'))
import calibracion_receptor as cal
import medir_metales_del_sitio as metal

def now(): return datetime.now(timezone.utc).isoformat(timespec='seconds')
def sha(data): return hashlib.sha256(data).hexdigest()
def write(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
def read(path): return json.loads(path.read_text(encoding='utf-8'))
def population():
    ev=read(ROOT/'docs/auditorias/metales_junto_al_sitio_2026-10-11.json')
    cat={x['pdb_id'].upper():x for x in read(ROOT/'curated_targets.json')}
    out=[]
    for pid in sorted({r['pdb_id'] for r in ev['filas']}):
        e=dict(cat[pid]); e['ions']=[r for r in ev['filas'] if r['pdb_id']==pid]
        e['principal']=any(r['lo_coordina_el_ligando'] for r in e['ions'])
        lines=metal._lineas_del_deposito(ROOT/f'data/targets/{pid}.pdb.gz')
        ligs=collections.defaultdict(list)
        for l in lines:
            if l.startswith('HETATM') and l[17:20].strip()==e['site_ligand']: ligs[(l[21],l[22:27])].append(l)
        center=tuple(e[f'grid_center_{c}'] for c in 'xyz')
        key=min(ligs,key=lambda k:min(math.dist(metal._xyz(a),center) for a in ligs[k]))
        e['crystal_instance']=[e['site_ligand'],key[0],int(key[1][:4])]
        e['source_sha256']=sha((ROOT/f'data/targets/{pid}.pdb.gz').read_bytes())
        for ion in e['ions']:
            c,n=ion['metal_id'].split(':')
            atom=next(l for l in lines if l.startswith('HETATM') and l[17:20].strip()==ion['metal'] and l[21]==c and int(l[22:26])==int(n))
            ion['xyz']=metal._xyz(atom)
        out.append(e)
    assert len(out)==41 and sum(e['principal'] for e in out)==35
    return out

class Capsule:
    def __init__(self,path):
        self.path=path; s=read(path/'private-session.json'); self.base=s['base']; self.secret=s['secret']; self.env=s['env']; self.token=None
        self.login()
    def login(self):
        req=urllib.request.Request(self.base+'/auth/desktop-login',headers={'X-MolDesign-Launch':self.secret})
        with urllib.request.urlopen(req,timeout=120) as r: self.token=json.load(r)['access_token']
    def api(self,method,path,body=None,expected=(200,),timeout=600):
        return cal._arnes()._json(self.base,method,path,body=body,token=self.token,expected=set(expected),timeout=timeout)
    def variants(self,e,label):
        out={}
        for arm in ['SIN','CON']:
            wl=[] if arm=='SIN' else sorted({r['metal'] for r in e['ions']})
            try:
                v=self.api('POST',f"/targets/{e['pdb_id']}/variants",{'name':f"MET01R1-{label}-{e['pdb_id']}-{arm}",'cofactors_whitelist':wl},expected=(201,))
                assert v['chain']==e['chain']
                assert all(v[f'grid_{kind}_{c}']==e[f'grid_{kind}_{c}'] for kind in ['center','size'] for c in 'xyz')
                out[arm]={'state':'PREPARED','target':v,'whitelist':wl}
            except Exception as ex: out[arm]={'state':'NOT_REPRESENTABLE','error':str(ex),'whitelist':wl}
        return out

def launch(path,n):
    r=subprocess.run(['node',str(SOURCE/'capsula.mjs'),str(ROOT),'D:/moldesign-build',str(path),str(n)],capture_output=True,text=True)
    if r.returncode: raise RuntimeError(r.stderr)
    return Capsule(path)
def stop(c,n):
    r=subprocess.run(['node',str(SOURCE/'capsula.mjs'),str(ROOT),'D:/moldesign-build',str(c.path),str(n),'down'],capture_output=True,text=True)
    if r.returncode: raise RuntimeError(r.stderr)

def probe_catalog(e,env):
    code=r'''
import asyncio,json,sys,hashlib
sys.path.insert(0,sys.argv[1])
from services.docking.preparer import prepare_target
from utils.local_storage import path_for
from pathlib import Path
e=json.loads(sys.stdin.read())
try:
 p=asyncio.run(prepare_target(e['pdb_id'],e['chain'],tuple(e['grid_center_'+c] for c in 'xyz'),tuple(e['grid_size_'+c] for c in 'xyz'),force_reprepare=True,cofactors_whitelist=[],site_chains=e.get('site_chains'),site_ligand=e.get('site_ligand')))
 p=path_for(p)
 print(json.dumps({'state':'PREPARED','sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'path':str(p)}))
except Exception as ex: print(json.dumps({'state':'UNPREPARABLE','error':str(ex)}))
'''
    r=subprocess.run([str(ROOT/'python-embed/python.exe'),'-c',code,str(ROOT/'backend')],input=json.dumps(e),env=env,cwd=ROOT/'backend',capture_output=True,text=True)
    if r.returncode: raise RuntimeError(r.stderr[-2000:])
    return json.loads(r.stdout.strip().splitlines()[-1])

def recon():
    pop=population(); results=[]
    for repeat in [1,2]:
        path=WORK/f'capsules/recon-{repeat}'
        c=launch(path,1)
        try:
            rows=[]
            for e in pop:
                c.login(); cat=probe_catalog(e,c.env); variants=c.variants(e,f'recon{repeat}')
                row={'pdb_id':e['pdb_id'],'catalog':cat,'variants':variants}
                rows.append(row); write(WORK/f'recon-{repeat}.json',rows)
                print(e['pdb_id'],repeat,cat['state'],{a:r['state'] for a,r in variants.items()},flush=True)
            results.append(rows)
        finally: stop(c,1)
    clean=[]
    for e,a,b in zip(pop,*results):
        checks={}
        for arm in ['SIN','CON']:
            x,y=a['variants'][arm],b['variants'][arm]
            hx=(x.get('target') or {}).get('prepared_receptor_sha256'); hy=(y.get('target') or {}).get('prepared_receptor_sha256')
            checks[arm]={'sha256':hx,'repeat_sha256':hy,'reproducible':bool(hx and hx==hy),'state':x['state'],'error':x.get('error')}
        checks['SIN_matches_catalog']=checks['SIN']['sha256']==a['catalog'].get('sha256')==b['catalog'].get('sha256') and checks['SIN']['reproducible']
        e['recognition']=checks; e['catalog_preparation']=a['catalog']
        clean.append(e)
    write(PRE/'reconocimiento.json',{'created':now(),'entries':clean,'capsules_public':[read(WORK/f'capsules/recon-{r}/public-session.json') for r in [1,2]],'no_docking':True})
    print('Recognition saved',flush=True)

def ccd():
    from Bio.PDB.MMCIF2Dict import MMCIF2Dict
    from rdkit import Chem
    folder=PRE/'ccd'; folder.mkdir(parents=True,exist_ok=True)
    rows={}
    for code in sorted({e['site_ligand'] for e in population()}):
        path=folder/f'{code}.cif'; stamp=folder/f'{code}.source.json'
        url=f'https://files.rcsb.org/ligands/download/{code}.cif'
        old=MET01/'entrada/ccd'/f'{code}.cif'
        if not path.exists() and old.exists():
            path.write_bytes(old.read_bytes()); stamp.write_bytes((MET01/'entrada/ccd'/f'{code}.source.json').read_bytes())
        if not path.exists():
            with urllib.request.urlopen(url,timeout=60) as response: data=response.read()
            path.write_bytes(data); write(stamp,{'url':url,'downloaded_at':now(),'sha256':sha(data)})
        d=MMCIF2Dict(str(path))
        descriptors=[dict(zip(['type','program','version','smiles'],v)) for v in zip(*(d['_pdbx_chem_comp_descriptor.'+x] for x in ['type','program','program_version','descriptor'])) if v[0]=='SMILES_CANONICAL']
        descriptors.sort(key=lambda v:(0 if v['program'].startswith('OpenEye') else 1,v['program'],v['version'],v['smiles']))
        selected=next(v for v in descriptors if Chem.MolFromSmiles(v['smiles']) is not None)
        rows[code]={'source':read(stamp),'descriptor':selected,'smiles':Chem.MolToSmiles(Chem.MolFromSmiles(selected['smiles']),isomericSmiles=True)}
        print('CCD',code,flush=True)
    write(PRE/'ccd.json',rows)

def crystal(e):
    # Reuse CAL's exact template-assignment method, with MET population parameters.
    # Apply the population's declared first-model, blank/A-altloc selection to the input.
    original_root=cal.RAIZ
    prepared_root=PRE/'reference_inputs'
    target=prepared_root/f"data/targets/{e['pdb_id']}.pdb.gz"
    if not target.exists():
        target.parent.mkdir(parents=True,exist_ok=True)
        selected='\n'.join(metal._lineas_del_deposito(ROOT/f"data/targets/{e['pdb_id']}.pdb.gz"))+'\nEND\n'
        target.write_bytes(gzip.compress(selected.encode(),mtime=0))
    cal.PDB_ID=e['pdb_id']; cal.LIGANDO_CRISTAL=tuple(e['crystal_instance']); cal.SMILES_CRISTAL=e['ccd']['smiles']
    ion=e['ions'][0]; chain,num=ion['metal_id'].split(':'); cal.CLORURO=(ion['metal'],chain,int(num))
    cal.RAIZ=prepared_root
    try: return cal._cristal()[0]
    finally: cal.RAIZ=original_root

def anchor(e,ref):
    """Independent prespecified chemical hypothesis; never a population estimate."""
    from rdkit import Chem
    if not any(i['metal']=='ZN' and i['lo_coordina_el_ligando'] for i in e['ions']): return None
    rules=[('sulfonamide_N','[SX4](=[OX1])(=[OX1])[NX3;H1,H2]',3),('hydroxamate_O','[CX3](=[OX1])[NX3][OX2H1]',3),('thiol_S','[SX2H1]',0)]
    matches=[]
    for name,smarts,which in rules:
        for m in ref.GetSubstructMatches(Chem.MolFromSmarts(smarts)):
            idx=m[which]; p=tuple(ref.GetConformer().GetAtomPosition(idx))
            if min(math.dist(p,i['xyz']) for i in e['ions'] if i['metal']=='ZN')<=2.8:
                matches.append((name,idx,smarts))
    if not matches: return None
    # One anchoring group: deterministic lowest crystal atom name within rule priority.
    name,idx,smarts=min(matches,key=lambda m:(next(j for j,r in enumerate(rules) if r[0]==m[0]),ref.GetAtomWithIdx(m[1]).GetPDBResidueInfo().GetName().strip()))
    m=Chem.RWMol(ref); a=m.GetAtomWithIdx(idx); h=a.GetTotalNumHs()
    a.SetFormalCharge(a.GetFormalCharge()-1); a.SetNumExplicitHs(h-1); a.SetNoImplicit(True)
    diag=m.GetMol(); Chem.SanitizeMol(diag)
    return {'rule':name,'smarts':smarts,'crystal_atom':a.GetPDBResidueInfo().GetName().strip(),'smiles':Chem.MolToSmiles(diag,isomericSmiles=True),'source':'Independent MET-01 rule: remove one proton from the matched N/O/S within 2.8 A of Zn. Hypothesis of anchoring, not a validated bound population.'}

def freeze_ligands():
    cc=read(PRE/'ccd.json'); pop=population(); refs={}; errors=[]
    for e in pop:
        e['ccd']=cc[e['site_ligand']]
        try:
            refs[e['pdb_id']]=crystal(e)
            e['diagnostic']=anchor(e,refs[e['pdb_id']])
        except (Exception,SystemExit) as ex:
            e['reference_error']=str(ex); e['diagnostic']=None; errors.append(e['pdb_id'])
    inputs=sorted({e['ccd']['smiles'] for e in pop}|{e['diagnostic']['smiles'] for e in pop if e.get('diagnostic')})
    # Exact CAL microstate probe; isolate its profile as well as LOCAL_DATA_DIR.
    private=read(WORK/'capsules/recon-1/private-session.json')
    os.environ.update(private['env'])
    aa=cal._microestados(inputs,WORK/'microstates/proc-1'); bb=cal._microestados(inputs,WORK/'microstates/proc-2')
    for e in pop:
        sm=e['ccd']['smiles']; e['microstate']=aa[sm]; e['microstate']['repeat']=bb[sm]; e['microstate']['reproducible']=aa[sm]['smiles_acoplado']==bb[sm]['smiles_acoplado'] and aa[sm]['carga']==bb[sm]['carga']
        e['microstate']['sha256']=sha((aa[sm]['smiles_acoplado'] or '').encode())
        if e.get('diagnostic'):
            d=e['diagnostic']; d['product_microstate']=aa[d['smiles']]; d['repeat']=bb[d['smiles']]
            from rdkit import Chem
            canonical=lambda s:Chem.MolToSmiles(Chem.MolFromSmiles(s),isomericSmiles=True)
            d['representable_at_default_ph']=canonical(aa[d['smiles']]['smiles_acoplado'])==canonical(d['smiles'])==canonical(bb[d['smiles']]['smiles_acoplado'])
    write(PRE/'ligandos.json',{'created':now(),'entries':pop,'reference_errors':errors})
    print('Ligands frozen',len(pop),'reference errors',errors,'diagnostics',sum(bool(e.get('diagnostic')) for e in pop),'representable',sum(bool((e.get('diagnostic') or {}).get('representable_at_default_ph')) for e in pop),flush=True)

def diagnostic_states():
    from rdkit import Chem
    from rdkit.Chem import AllChem
    lig=read(PRE/'ligandos.json'); pop=lig['entries']; inputs=[]
    for e in pop:
        try:
            ref=crystal(e)
            e.pop('reference_error',None)
            # Preserve the normal microstate outside the anchoring group.
            main=AllChem.AssignBondOrdersFromTemplate(Chem.MolFromSmiles(e['microstate']['smiles_acoplado']),ref)
            e['diagnostic']=anchor(e,main)
            if e.get('diagnostic'): inputs.append(e['diagnostic']['smiles'])
        except (Exception,SystemExit) as ex: e['reference_error']=str(ex); e['diagnostic']=None
    code=r'''
import asyncio,json,sys
sys.path.insert(0,sys.argv[1])
from chem.conformer import generate_conformer
out={}
for s in json.loads(sys.stdin.read()):
 out[s]={}
 for ph in [7.4,10.0,12.0]:
  r=asyncio.run(generate_conformer(s,ph=ph)); e=r.get('estado_del_ligando') or {}
  out[s][str(ph)]={'smiles_acoplado':e.get('smiles_acoplado'),'charge':e.get('carga_formal_neta'),'ph':e.get('protonacion',{}).get('ph')}
print(json.dumps(out))
'''
    env=read(WORK/'capsules/recon-1/private-session.json')['env']; probes=[]
    for repeat in [1,2]:
        own=dict(env); own['LOCAL_DATA_DIR']=str(WORK/f'diagnostic-states/proc-{repeat}')
        Path(own['LOCAL_DATA_DIR']).mkdir(parents=True,exist_ok=True)
        r=subprocess.run([str(ROOT/'python-embed/python.exe'),'-c',code,str(ROOT/'backend')],input=json.dumps(sorted(set(inputs))),capture_output=True,text=True,cwd=ROOT/'backend',env=own)
        if r.returncode: raise RuntimeError(r.stderr[-2000:])
        probes.append(json.loads(r.stdout.strip().splitlines()[-1]))
    canon=lambda s:Chem.MolToSmiles(Chem.MolFromSmiles(s),isomericSmiles=True)
    for e in pop:
        if not e.get('diagnostic'): continue
        d=e['diagnostic']; d['probes']=[p[d['smiles']] for p in probes]
        accepted=[ph for ph in ['7.4','10.0','12.0'] if all(canon(p[d['smiles']][ph]['smiles_acoplado'])==canon(d['smiles']) for p in probes)]
        d['ph']=float(accepted[0]) if accepted else None
        d['representable']=bool(accepted)
        d['sha256']=sha(d['smiles'].encode())
        if accepted: d['expected_microstate']=probes[0][d['smiles']][accepted[0]]['smiles_acoplado']
    lig['reference_errors']=[e['pdb_id'] for e in pop if e.get('reference_error')]
    write(PRE/'ligandos.json',lig)
    print('Diagnostic forms',[(e['pdb_id'],e['diagnostic']['ph']) for e in pop if e.get('diagnostic')],'reference errors',lig['reference_errors'],flush=True)

def prepared_path(capsule,target):
    paths=list((capsule/'data/targets'/target['pdb_id']).glob('prepared-*.pdbqt'))
    return next(p for p in paths if sha(p.read_bytes())==target['prepared_receptor_sha256'])

def retained_ions(path,e):
    lines=path.read_text(encoding='utf-8').splitlines()
    result=[]
    for ion in e['ions']:
        chain,num=ion['metal_id'].split(':')
        matches=[l for l in lines if l.startswith(('ATOM','HETATM')) and l[17:20].strip().upper()==ion['metal'] and l[21]==chain and l[22:26].strip()==num]
        result.append({'metal':ion['metal'],'metal_id':ion['metal_id'],'present':any(math.dist(metal._xyz(l),ion['xyz'])<=0.005 for l in matches)})
    return result

def crystal_probe():
    from rdkit import Chem
    from rdkit.Chem import AllChem
    from meeko import MoleculePreparation,PDBQTWriterLegacy
    sys.path.insert(0,str(ROOT/'backend'))
    from services.chemistry.pose_physical_validity import evaluar_pose_fisica
    rec={e['pdb_id']:e for e in read(WORK/'recon-1.json')}; pop=read(PRE/'ligandos.json')['entries']; rows=[]
    cap=WORK/'capsules/recon-1'
    # These are crystal poses, not docking outputs. Do not calculate RMSD here.
    env=read(cap/'private-session.json')['env']; os.environ.update(env)
    for e in pop:
        row={'pdb_id':e['pdb_id'],'no_docking':True,'state':'NOT_EVALUABLE'}
        try:
            ref=crystal(e)
            ref=AllChem.AssignBondOrdersFromTemplate(Chem.MolFromSmiles(e['microstate']['smiles_acoplado']),ref)
            mol=Chem.AddHs(ref,addCoords=True)
            setup=MoleculePreparation().prepare(mol)[0]
            pdbqt,ok,message=PDBQTWriterLegacy.write_string(setup,add_index_map=True)
            if not ok: raise RuntimeError(message)
            pairs=[]
            for l in pdbqt.splitlines():
                if l.startswith('REMARK INDEX MAP'):
                    ints=list(map(int,l.split()[3:])); pairs.extend((ints[j+1],ints[j]-1) for j in range(0,len(ints),2))
            assert pairs
            row['arms']={}
            for arm in ['SIN','CON']:
                v=rec[e['pdb_id']]['variants'][arm]
                if v['state']!='PREPARED': row['arms'][arm]={'state':v['state'],'error':v.get('error')}; continue
                p=prepared_path(cap,v['target'])
                keep=retained_ions(p,e)
                evidence=evaluar_pose_fisica(pdbqt,plantilla=mol,index_map=pairs,receptor_path=p)
                own=PRE/f"receptores/{e['pdb_id']}-{arm}.pdbqt"; own.parent.mkdir(parents=True,exist_ok=True); own.write_bytes(p.read_bytes())
                row['arms'][arm]={'receptor_sha256':sha(p.read_bytes()),'ions':keep,'evidence':evidence}
            row['state']='EVALUATED'
        except (Exception,SystemExit) as ex: row['error']=str(ex)
        rows.append(row); write(PRE/'posebusters_cristal.json',{'created':now(),'condition':'Product canonical H reconstruction MF-33-H-COR; microstate frozen at pH 7.4; original crystal heavy coordinates; no docking, no RMSD','rows':rows})
        print('Crystal PB',e['pdb_id'],row['state'],{a:x.get('evidence',{}).get('status') for a,x in row.get('arms',{}).items()},flush=True)

def inspect_validator():
    # Set the private profile before importing modules that may cache TEMP.
    os.environ.update(read(WORK/'capsules/recon-1/private-session.json')['env'])
    import tempfile
    tempfile.tempdir=None
    from rdkit import Chem
    from posebusters.tools.protein import get_atom_type_mask
    sys.path.insert(0,str(ROOT/'backend'))
    from services.chemistry.pose_physical_validity import receptor_como_pdb
    rows=read(PRE/'posebusters_cristal.json'); pop={e['pdb_id']:e for e in population()}
    for row in rows['rows']:
        own=PRE/f"receptores/{row['pdb_id']}-CON.pdbqt"
        if not own.exists(): continue
        pdb=receptor_como_pdb(own)
        try:
            receptor=Chem.MolFromPDBFile(str(pdb),sanitize=False,removeHs=False,proximityBonding=False)
            if receptor is None: raise RuntimeError('Receptor not loaded')
            inorg=get_atom_type_mask(receptor,{'hydrogens','protein','organic_cofactors','waters'})
            protein=get_atom_type_mask(receptor,{'hydrogens','organic_cofactors','inorganic_cofactors','waters'})
            selected=[]
            for atom in receptor.GetAtoms():
                info=atom.GetPDBResidueInfo()
                if atom.GetSymbol().upper() not in ['ZN','MG','CA','K']: continue
                selected.append({'element':atom.GetSymbol(),'chain':info.GetChainId(),'residue':info.GetResidueNumber(),'record_hetero':info.GetIsHeteroAtom(),'selected_for_inorganic_checks':inorg[atom.GetIdx()],'selected_for_protein_checks':protein[atom.GetIdx()]})
            row['metal_classification_by_actual_PB_masks']=selected
        finally:
            if pdb!=own:
                # Product receptor_como_pdb leaves its mkstemp descriptor open on Windows.
                # Do not patch the product; let process exit close it, in capsule TEMP.
                try: pdb.unlink(missing_ok=True)
                except PermissionError: pass
    rows['classification_condition']='Exact product receptor_como_pdb conversion; RDKit mol_cond loading parameters from dock.yml; actual PoseBusters get_atom_type_mask. Meeko writes ATOM metals. Inorganic tests ignore ATOM records as protein, protein tests ignore inorganic elements: metals can be omitted from both masks. PASA is then vacuous for ion contacts.'
    write(PRE/'posebusters_cristal.json',rows)
    selected=[a for r in rows['rows'] for a in r.get('metal_classification_by_actual_PB_masks',[])]
    print('Retained metals loaded',len(selected),'inorganic masks',sum(a['selected_for_inorganic_checks'] for a in selected),'protein masks',sum(a['selected_for_protein_checks'] for a in selected),'hetero',sum(a['record_hetero'] for a in selected))

def sign_p(favor,against):
    n=favor+against
    return min(1.0,2*sum(math.comb(n,k) for k in range(min(favor,against)+1))/2**n) if n else 1.0
def power(n,q,delta):
    # Exact multinomial enumeration: D~Bin(n,q), F|D~Bin(D,(q+delta)/(2q)).
    theta=(q+delta)/(2*q)
    return sum(math.comb(n,d)*q**d*(1-q)**(n-d)*sum(math.comb(d,f)*theta**f*(1-theta)**(d-f) for f in range(d+1) if f>d-f and sign_p(f,d-f)<=.05) for d in range(n+1))
def power_report():
    obj={'alpha':.05,'sidedness':'two','minimum_effect_rate_difference':.4,'design_discordance_probability':.5,'target_power':.8,'minimum_evaluable_n':25,'assumption':'Power is conditional on the declared multinomial discordance model; it is not guaranteed for unknown discordance rates. This catalogue is a fixed cohort, not a random population sample.',
         'significance_boundary':{'minimum_discordant_n':6,'favor':6,'against':0,'p':sign_p(6,0),'minimum_observed_rate_difference_at_n35':6/35},
         'critical_splits':[{'discordant_n':n,'minimum_favor':next((f for f in range(n//2+1,n+1) if sign_p(f,n-f)<=.05),None)} for n in range(1,36)],
         'power_table':[{'n':n,'q':q,'delta':d,'power':power(n,q,d)} for n in [25,30,35] for q in [.4,.5,.6,.8,1.] for d in [.2,.3,.35,.4] if d<=q],
         'difference_detectable_at_80_percent_given_q05':{str(n):next(d/1000 for d in range(1,501) if power(n,.5,d/1000)>=.8) for n in [25,30,35]}}
    write(PRE/'potencia.json',obj); print('Power written')

def reproduce(rows):
    # CAL gate verbatim: >=3 RMSD successes AND all RMSD successes physically valid.
    ok=[r for r in rows if r.get('rmsd_top1_A') is not None and r['rmsd_top1_A']<=2.0]
    return len(rows)==5 and len(ok)>=3 and all(r.get('physical_status')=='passed' for r in ok)
def decision(favor,against,n,excluded,controls_harm,controls_sufficient=True):
    p=sign_p(favor,against)
    if n<25 or excluded/35>.3: return 'INCONCLUSIVE'
    if p>.05 or favor<=against or controls_harm: return 'NO_GO'
    return 'GO' if controls_sufficient else 'INCONCLUSIVE'

class Recorder:
    def __init__(self): self.g=cal._arnes(); self.preflight=None
    def _json(self,*args,**kw):
        result=self.g._json(*args,**kw)
        if args[2]=='/evaluation/preflight': self.preflight=result
        return result
    def _request(self,*args,**kw): return self.g._request(*args,**kw)

def summary_row(e,arm,seed,raw):
    from rdkit import Chem
    from rdkit.Chem import rdMolAlign
    result=raw['resultado']; dp=result['docking_protocol']; prov=dp['execution_provenance']
    mol,energy,matched=cal._top1(raw)
    if not matched: raise RuntimeError('CAL top-1 SDF/PDBQT correspondence failed')
    ref=cal._neutro_sin_h(crystal(e)); top_rmsd=float(rdMolAlign.CalcRMS(cal._neutro_sin_h(mol),ref))
    supplier=Chem.SDMolSupplier(); supplier.SetData(raw['poses_sdf'],removeHs=False)
    poses=[p for p in supplier if p is not None]
    if len(poses)!=len(result['docking_poses']): raise RuntimeError('Number of SDF and PDBQT poses differs')
    rmsds=[float(rdMolAlign.CalcRMS(cal._neutro_sin_h(p),ref)) for p in poses]
    top=next(p for p in result['structural_evidence']['poses'] if p['rank']==1)
    state=result.get('ligand_state') or {}
    expected=e['diagnostic']['expected_microstate'] if arm.startswith('DIAG') else e['microstate']['smiles_acoplado']
    variant_arm='CON' if arm.endswith('CON') else 'SIN'
    expected_sha=e['recognition'][variant_arm]['sha256']
    assert state.get('smiles_acoplado')==expected,('Microstate drift',state.get('smiles_acoplado'),expected)
    assert prov.get('receptor_sha256')==expected_sha,('Receptor drift',prov.get('receptor_sha256'),expected_sha)
    assert dp.get('seed')==seed and dp.get('exhaustiveness')==8 and dp.get('num_poses')==9
    assert result.get('vina_version')=='1.2.7'
    assert prov.get('cpu')==4
    if top.get('status')=='passed':
        assert top.get('engine','').startswith('posebusters:0.6.5:dock'),top.get('engine')
    req=raw['preparacion']; blocks=req['bloques']; requirements=[r for b in (blocks if isinstance(blocks,list) else blocks.values()) for r in b['requisitos']]
    selected=[r for r in requirements if r['clave'] in ['entorno.metales_cofactores','receptor.protonacion','entorno.referencia']]
    text=json.dumps(selected,ensure_ascii=False)
    distances=[]
    if variant_arm=='CON':
        conf=mol.GetConformer()
        for ion in e['ions']:
            donor=min(math.dist(tuple(conf.GetAtomPosition(a.GetIdx())),ion['xyz']) for a in mol.GetAtoms() if a.GetSymbol() in ['N','O','S'])
            crystal_donor=min(math.dist(tuple(crystal(e).GetConformer().GetAtomPosition(a.GetIdx())),ion['xyz']) for a in crystal(e).GetAtoms() if a.GetSymbol() in ['N','O','S'])
            distances.append({'metal':ion['metal'],'metal_id':ion['metal_id'],'top1_donor_A':donor,'crystal_donor_A':crystal_donor,'within_2_8_A':donor<=2.8})
    return {'id':f"{e['pdb_id']}-{arm}-s{seed}",'entry':e['pdb_id'],'arm':arm,'seed':seed,'outcome':'SUCCESS','cofactors_whitelist':[] if variant_arm=='SIN' else sorted({i['metal'] for i in e['ions']}),'receptor_sha256':prov['receptor_sha256'],'recipe':prov.get('receta_receptor'),'receptor_prep':prov.get('receptor_prep'),'microstate_smiles':state['smiles_acoplado'],'microstate_sha256':sha(state['smiles_acoplado'].encode()),'ligand_state':state,'task_id':raw['task_id'],'molecule_id':result['molecule_id'],'rmsd_top1_A':top_rmsd,'rmsd_poses_A':rmsds,'best_of_returned_poses_A':min(rmsds),'returned_poses':len(rmsds),'physical_status':top['status'],'physical_evidence':top,'failed_checks':[x for x in top.get('checks',[]) if x.get('estado')=='FALLA'],'ion_distances':distances,'vina_energy_kcal':energy,'preparation_requirements':selected,'histidine_warning':('His que coordinan un metal conservado con el hidrógeno' in text),'product_commit':PRODUCT,'seconds':raw['segundos']}

def evaluate(c,e,arm,seed):
    c.login(); recorder=Recorder(); be=cal.Backend(c.path); be.base=c.base; be.token=c.token; be.gate=recorder
    variant_arm='CON' if arm.endswith('CON') else 'SIN'
    smiles=e['diagnostic']['smiles'] if arm.startswith('DIAG') else e['ccd']['smiles']
    original_config=cal.CONFIG_CASO
    cal.CONFIG_CASO=json.loads(json.dumps(original_config))
    if arm.startswith('DIAG'): cal.CONFIG_CASO['stage_params']['conformer']['ph']=e['diagnostic']['ph']
    try: raw=be.evaluar(smiles,e['runtime_variants'][variant_arm]['target']['pdb_id'],e['chain'],seed,f"MET01R1-{e['pdb_id']}-{arm}-{seed}")
    finally: cal.CONFIG_CASO=original_config
    result=raw['resultado']; mid=result['molecule_id']; task=raw['task_id']
    persisted=c.api('GET',f'/evaluation/result/{mid}?task_id={task}')
    if recorder.g._critical_result(result)!=recorder.g._critical_result(persisted): raise RuntimeError('Live/persisted scientific fields differ')
    raw['persisted_result']=persisted; raw['preflight_full']=recorder.preflight
    old_smiles=recorder.g.SMILES; recorder.g.SMILES=smiles
    try: projection=recorder.g._projection(task,recorder.preflight['input_fingerprint'],recorder.preflight)
    finally: recorder.g.SMILES=old_smiles
    projection['case_id']=f"met01r1-{e['pdb_id']}-{arm}-{seed}"; projection['name']=projection['case_id']
    projection['inputs']['receptor']['origin']='user'
    raw['projection']=projection
    raw['preparacion']=c.api('POST',f'/evaluation/dossier/{mid}/preparacion',projection)
    return raw

def run_shard(phase,shard):
    protocol=read(EXP/'entrada/protocolo.json'); entries=protocol['entries']; eligible=[e for e in entries if not e.get('exclusion')]
    if phase=='pilot': eligible=[next(e for e in eligible if e['pdb_id']==protocol['pilot_entry'])]
    else: eligible=[e for i,e in enumerate(eligible) if i%3==shard-1]
    out=EXP/f'_work/{phase}/shard-{shard}'; out.mkdir(parents=True,exist_ok=True)
    frozen_head=subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip()
    def guard():
        if (EXP/'_work/STOP').exists(): raise RuntimeError('Shared STOP marker exists')
        head=subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip()
        dirty=subprocess.check_output(['git','-C',str(ROOT),'status','--porcelain','--untracked-files=no'],text=True).strip()
        if head!=frozen_head or dirty: raise RuntimeError('Frozen worktree changed')
        if subprocess.check_output(['git','-C',str(ROOT),'diff',PRODUCT,'--','backend','frontend','rescoring','tools','curated_targets.json'],text=True).strip(): raise RuntimeError('Product differs from fixed base')
    guard()
    # Vina's Windows std::ofstream cannot create a path beyond MAX_PATH.
    # Keep the isolated profile under the authorized, ignored scripts tree.
    session=ROOT/f'scripts/met01r1/tmp/c-{phase[0]}{shard}-{time.time_ns():x}'
    c=launch(session,shard)
    write(out/f'freeze-{session.name}.json',{'head':frozen_head,'started':now(),'protocol_sha256':sha((EXP/'entrada/protocolo.json').read_bytes()),'product_commit':PRODUCT,'capsule':read(session/'public-session.json')})
    failures=attempts=0
    try:
        for e in eligible:
            pending=[]
            arms=['SIN','CON']+(['DIAG_SIN','DIAG_CON'] if (e.get('diagnostic') or {}).get('representable') else [])
            for arm in arms:
                for seed in range(42,47):
                    ident=f"{e['pdb_id']}-{arm}-s{seed}"
                    if not (out/f'{ident}.terminal.json').exists(): pending.append((arm,seed,ident))
            if not pending: continue
            guard(); c.login()
            # The recognition materialized the gzipped catalogue deposit by
            # preparing its parent first. Repeat that same product path in every
            # fresh capsule before the variants endpoint reads its raw PDB.
            cat=probe_catalog(e,c.env)
            if cat['state']!='PREPARED' or cat['sha256']!=e['recognition']['SIN']['sha256']:
                raise RuntimeError(f"Catalogue preparation drift {e['pdb_id']}: {cat}")
            e['runtime_variants']=c.variants(e,phase)
            for arm,v in e['runtime_variants'].items():
                if v['state']!='PREPARED' or v['target']['prepared_receptor_sha256']!=e['recognition'][arm]['sha256']: raise RuntimeError(f"Variant preparation drift {e['pdb_id']} {arm}: {v}")
                if arm=='CON' and not all(i['present'] for i in retained_ions(prepared_path(session,v['target']),e)): raise RuntimeError('Ion retention drift')
            write(out/f"{e['pdb_id']}-variants-{session.name}.json",e['runtime_variants'])
            for arm,seed,ident in pending:
                guard(); t0=time.monotonic(); row=None
                for attempt in [1,2]:
                    attempts+=1
                    try:
                        raw=evaluate(c,e,arm,seed)
                        raw_file=out/f'{ident}-attempt{attempt}.json.gz'
                        if raw_file.exists(): raise RuntimeError('Refusing to overwrite raw evidence')
                        raw_file.write_bytes(gzip.compress(json.dumps(raw,ensure_ascii=False,allow_nan=False).encode(),mtime=0))
                        row=summary_row(e,arm,seed,raw); row['raw']=str(raw_file.relative_to(EXP)).replace('\\','/')
                        row['raw_sha256']=sha(raw_file.read_bytes()); row['attempts']=attempt; break
                    except Exception as ex:
                        error={'id':ident,'attempt':attempt,'created':now(),'error':str(ex),'seconds':time.monotonic()-t0}
                        with (out/'attempt-errors.jsonl').open('a',encoding='utf-8',newline='\n') as f:f.write(json.dumps(error,ensure_ascii=False)+'\n')
                        # Deterministic product rejection is a scientific outcome, not infrastructure.
                        if 'preflight bloqueado' in str(ex) or 'HTTP 400' in str(ex) or 'HTTP 409' in str(ex) or 'HTTP 422' in str(ex):
                            row={'id':ident,'entry':e['pdb_id'],'arm':arm,'seed':seed,'outcome':'PRODUCT_REJECTED','error':str(ex),'physical_status':None,'rmsd_top1_A':None,'attempts':attempt}; break
                if row is None:
                    failures+=1; row={'id':ident,'entry':e['pdb_id'],'arm':arm,'seed':seed,'outcome':'INFRASTRUCTURE_FAILURE','error':error['error'],'physical_status':None,'rmsd_top1_A':None,'attempts':2}
                v_arm='CON' if arm.endswith('CON') else 'SIN'
                row.setdefault('cofactors_whitelist',e['runtime_variants'][v_arm]['whitelist'])
                row.setdefault('receptor_sha256',e['recognition'][v_arm]['sha256'])
                row.setdefault('microstate_expected',e['diagnostic']['expected_microstate'] if arm.startswith('DIAG') else e['microstate']['smiles_acoplado'])
                row.setdefault('task_id',None); row.setdefault('product_commit',PRODUCT)
                row['phase']=phase
                row['total_seconds']=time.monotonic()-t0
                write(out/f'{ident}.terminal.json',row)
                print(phase,shard,ident,row['outcome'],round(row['total_seconds'],1),flush=True)
                terminals=[read(p) for p in (EXP/f'_work/{phase}').glob('shard-*/*.terminal.json')]
                frac=sum(r['outcome']=='INFRASTRUCTURE_FAILURE' for r in terminals)/len(terminals)
                if frac>.3:
                    write(EXP/'_work/STOP',{'reason':'Infrastructure failures >30%','fraction':frac,'created':now()}); raise RuntimeError('Infrastructure stop rule')
        guard()
    finally:
        stop(c,shard)
        write(out/f'stopped-{session.name}.json',{'head':frozen_head,'stopped':now(),'attempts_this_session':attempts,'infrastructure_failures_this_session':failures})

def analyze_rows(entries,rows):
    by=collections.defaultdict(list)
    for row in rows: by[(row['entry'],row['arm'])].append(row)
    report=[]; favor=against=0; n=0; excluded=0; controls_harm=0; controls_complete=True; controls_n=0
    for e in entries:
        entry={'entry':e['pdb_id'],'principal':e['principal'],'ions':e['ions'],'exclusion':e.get('exclusion'),'diagnostic':e.get('diagnostic'),'arms':{}}
        evaluable=not e.get('exclusion')
        for arm in ['SIN','CON','DIAG_SIN','DIAG_CON']:
            rr=by[(e['pdb_id'],arm)]
            if len({r['seed'] for r in rr})!=len(rr): raise RuntimeError(f'Duplicate seeds {e["pdb_id"]} {arm}')
            if not rr and arm.startswith('DIAG'): continue
            complete=len(rr)==5 and all(r['outcome'] in ['SUCCESS','PRODUCT_REJECTED'] for r in rr)
            entry['arms'][arm]={'n':len(rr),'complete':complete,'reproduces':complete and reproduce(rr),'rmsd_successes':sum(r.get('rmsd_top1_A') is not None and r['rmsd_top1_A']<=2 for r in rr),'joint_successes':sum(r.get('rmsd_top1_A') is not None and r['rmsd_top1_A']<=2 and r.get('physical_status')=='passed' for r in rr),'physical_passed':sum(r.get('physical_status')=='passed' for r in rr),'histidine_warning_n':sum(bool(r.get('histidine_warning')) for r in rr),'infra_failure_n':sum(r['outcome']=='INFRASTRUCTURE_FAILURE' for r in rr),'rejected_n':sum(r['outcome']=='PRODUCT_REJECTED' for r in rr)}
            if arm in ['SIN','CON'] and not complete: evaluable=False
        entry['paired_evaluable']=evaluable
        if e['principal']:
            if evaluable:
                n+=1; sin=entry['arms']['SIN']['reproduces']; con=entry['arms']['CON']['reproduces']
                favor+=int(con and not sin); against+=int(sin and not con)
            else: excluded+=1
        else:
            if not evaluable: controls_complete=False
            else:
                controls_n+=1
                if entry['arms']['SIN']['reproduces'] and not entry['arms']['CON']['reproduces']: controls_harm+=1
        report.append(entry)
    primary_rows=[r for r in rows if r['arm'] in ['SIN','CON']]
    seed_rates={arm:{'n':sum(r['arm']==arm for r in primary_rows),'successes':sum(r['arm']==arm and r.get('rmsd_top1_A') is not None and r['rmsd_top1_A']<=2 and r.get('physical_status')=='passed' for r in primary_rows)} for arm in ['SIN','CON']}
    elements={}
    for element in ['ZN','MG','CA','K']:
        elements[element]=[e['entry'] for e in report if e['paired_evaluable'] and any(i['metal']==element for i in e['ions'])]
    return {'experiment':'MET-01-R1-ION-DEL-SITIO','product_commit':PRODUCT,'principal':{'population_n':35,'paired_n':n,'excluded_n':excluded,'favor_CON':favor,'favor_SIN':against,'exact_two_sided_p':sign_p(favor,against),'rate_difference':(favor-against)/n if n else None},'controls':{'population_n':6,'evaluable_n':controls_n,'all_evaluable':controls_complete,'harm_n':controls_harm,'minimum_n':4},'decision':decision(favor,against,n,excluded,controls_harm,controls_n>=4),'seed_rates':seed_rates,'elements_membership':elements,'entries':report,'failures_n':sum(r['outcome']=='INFRASTRUCTURE_FAILURE' for r in rows),'product_rejections_n':sum(r['outcome']=='PRODUCT_REJECTED' for r in rows),'total_runs':len(rows),'no_demuestra':['No demuestra afinidad ni energía de coordinación, actividad, calibración experimental, readiness para FEP ni compatibilidad con FEP+.','Redocking en el receptor de su propio cristal; no cross-docking ni otra versión de Vina.','La potencia es condicional al modelo de discordancias declarado; no demuestra ausencia de un efecto moderado.','Las formas diagnósticas son hipótesis químicas independientes; el pH usado para expresarlas no estima una población de unión.','El requisito de no daño sólo se verifica en al menos cuatro controles evaluables; no acredita ausencia de daño en los controles excluidos.','PoseBusters omite los iones Meeko ATOM de las máscaras inorgánica y de proteína; su PASA no valida contactos con el metal.']}

def selftest():
    from rdkit import Chem
    from rdkit.Chem import rdMolAlign
    e=read(EXP/'entrada/protocolo.json')['entries'][0]
    ref=cal._neutro_sin_h(crystal(e)); same=Chem.Mol(ref); shifted=Chem.Mol(ref)
    assert rdMolAlign.CalcRMS(same,ref)<1e-10
    for i in range(shifted.GetNumAtoms()):
        p=shifted.GetConformer().GetAtomPosition(i); shifted.GetConformer().SetAtomPosition(i,(p.x+3,p.y,p.z))
    rms=float(rdMolAlign.CalcRMS(shifted,ref)); assert abs(rms-3)<1e-8
    seeds=lambda value,status:[{'seed':i,'rmsd_top1_A':value,'physical_status':status,'outcome':'SUCCESS','entry':'A','arm':'SIN'} for i in range(42,47)]
    assert reproduce(seeds(0,'passed')) and not reproduce(seeds(rms,'passed')) and not reproduce(seeds(0,'review'))
    assert sign_p(6,0)==.03125 and sign_p(0,0)==1 and sign_p(3,3)==1
    assert decision(6,0,35,0,0)=='GO' and decision(0,6,35,0,0)=='NO_GO' and decision(6,0,35,0,1)=='NO_GO'
    assert decision(20,0,24,11,0)=='INCONCLUSIVE' and decision(6,0,35,0,0,False)=='INCONCLUSIVE'
    dummy=[{'pdb_id':str(i),'principal':i<35,'ions':[],'exclusion':'excluded' if i==0 else None} for i in range(41)]
    rows=[]
    for x in dummy:
        for arm in ['SIN','CON']:
            for r in seeds(0,'passed'): rows.append(dict(r,entry=x['pdb_id'],arm=arm))
    result=analyze_rows(dummy,rows); assert result['principal']['paired_n']==34 and result['principal']['excluded_n']==1
    assert sum(x['paired_evaluable'] for x in result['entries'])==40
    print('Autotest PASSED: crystal zero, translation 3 A, validity gate, exact signs, harm, missing controls, excluded denominator')

def merge():
    files=sorted((EXP/'_work/confirmatory').glob('shard-*/*.terminal.json'))
    rows=sorted([read(p) for p in files],key=lambda r:(r['entry'],r['arm'],r['seed']))
    if len({r['id'] for r in rows})!=len(rows): raise RuntimeError('Duplicate run IDs across shards')
    (EXP/'per_complex.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False,sort_keys=True,allow_nan=False)+'\n' for r in rows),encoding='utf-8',newline='\n')
    (EXP/'failures.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in rows if r['outcome']=='INFRASTRUCTURE_FAILURE'),encoding='utf-8',newline='\n')
    print('Merged',len(rows),'confirmatory records; pilot excluded')

def analyze():
    protocol=read(EXP/'entrada/protocolo.json')
    rows=[json.loads(l) for l in (EXP/'per_complex.jsonl').read_text(encoding='utf-8').splitlines()]
    if len({r['id'] for r in rows})!=len(rows): raise RuntimeError('Duplicate run IDs')
    metrics=analyze_rows(protocol['entries'],rows)
    metrics['principal']['test_applicable']=bool(metrics['principal']['paired_n'])
    if (EXP/'piloto/parada.json').exists():
        metrics['pilot_stop']=read(EXP/'piloto/parada.json')
        metrics['no_demuestra'].append('La comparación confirmatoria no se inició: el piloto CON ejecutó SIN. No hay estimación del efecto del ion ni una prueba de equivalencia.')
    memberships=metrics['elements_membership']; summaries={}
    for element,members in memberships.items():
        summaries[element]={'entries':len(members),'arms':{}}
        for arm in ['SIN','CON']:
            rr=[r for r in rows if r['entry'] in members and r['arm']==arm]
            successes=[r for r in rr if r.get('rmsd_top1_A') is not None and r['rmsd_top1_A']<=2 and r.get('physical_status')=='passed']
            summaries[element]['arms'][arm]={'seeds_n':len(rr),'joint_successes':len(successes),'reproducing_entries':sum(e['entry'] in members and e['arms'][arm]['reproduces'] for e in metrics['entries'])}
    metrics['per_element_descriptive']=summaries
    metrics['per_element_condition']='Membership is nonexclusive for entries containing more than one element; seed observations are correlated, not independent sample units.'
    metrics['coordination_descriptive']={}
    for arm in ['CON','DIAG_CON']:
        rr=[r for r in rows if r['arm']==arm and r['outcome']=='SUCCESS']
        ii=[i for r in rr for i in r['ion_distances']]
        metrics['coordination_descriptive'][arm]={'runs_n':len(rr),'ion_seed_observations_n':len(ii),'donor_within_2_8_A_n':sum(i['within_2_8_A'] for i in ii),'physical_passed_runs_n':sum(r['physical_status']=='passed' for r in rr),'histidine_warning_runs_n':sum(r['histidine_warning'] for r in rr)}
    metrics['best_of_returned_poses_descriptive']={arm:{'successful_runs_n':sum(r['arm']==arm and r['outcome']=='SUCCESS' for r in rows),'best_geometric_rmsd_le2_n':sum(r['arm']==arm and r.get('best_of_returned_poses_A',math.inf)<=2 for r in rows),'poses_returned_histogram':dict(sorted(collections.Counter(str(r['returned_poses']) for r in rows if r['arm']==arm and r['outcome']=='SUCCESS').items()))} for arm in ['SIN','CON','DIAG_SIN','DIAG_CON']}
    write(EXP/'metrics.json',metrics)
    print(json.dumps({k:metrics[k] for k in ['principal','controls','decision','total_runs','failures_n','product_rejections_n']},ensure_ascii=False,indent=2))

def verify():
    protocol=read(PRE/'protocolo.json'); entries={e['pdb_id']:e for e in protocol['entries']}
    rows=[json.loads(l) for l in (EXP/'per_complex.jsonl').read_text(encoding='utf-8').splitlines()]
    done=0
    for row in rows:
        if row['outcome']!='SUCCESS': continue
        path=EXP/row['raw']; assert sha(path.read_bytes())==row['raw_sha256']
        raw=json.loads(gzip.decompress(path.read_bytes())); e=entries[row['entry']]
        recalculated=summary_row(e,row['arm'],row['seed'],raw)
        for key,value in recalculated.items():
            if row.get(key)!=value: raise RuntimeError(f"Raw/summary mismatch {row['id']} {key}")
        assert raw['task_id']==row['task_id']
        done+=1
    before=sha((EXP/'metrics.json').read_bytes()); analyze(); after=sha((EXP/'metrics.json').read_bytes()); assert before==after
    obj={'verified_successful_rows':done,'total_rows':len(rows),'metrics_deterministic':True,'checks':['raw SHA256','CAL SDF/PDBQT top-1 correspondence','CAL symmetric heavy RMSD with no alignment, all returned poses','effective seed/configuration/CPU/Vina version','frozen microstate/receptor hash','physical status and preparation requirements','ion distances','raw task identity'],'product_commit':PRODUCT}
    write(EXP/'verificacion.json',obj)
    print('Raw evidence and deterministic analysis verified',done)

def preregister():
    """Prepare a reviewable protocol; never executed once any docking result exists."""
    if any((EXP/'_work').glob('**/*.terminal.json')): raise RuntimeError('Cannot change preregistration after docking')
    rec={e['pdb_id']:e for e in read(PRE/'reconocimiento.json')['entries']}
    lig=read(PRE/'ligandos.json')['entries']; raw={r['pdb_id']:r for r in read(WORK/'recon-1.json')}
    cap=WORK/'capsules/recon-1'
    for e in lig:
        e['recognition']=rec[e['pdb_id']]['recognition']; e['catalog_preparation']=rec[e['pdb_id']]['catalog_preparation']; reasons=[]
        if e['catalog_preparation']['state']!='PREPARED': reasons.append('CATALOG_UNPREPARABLE: '+e['catalog_preparation'].get('error',''))
        for arm in ['SIN','CON']:
            v=raw[e['pdb_id']]['variants'][arm]
            if v['state']!='PREPARED': reasons.append(arm+'_NOT_REPRESENTABLE: '+v.get('error',''))
            elif not e['recognition'][arm]['reproducible']: reasons.append(arm+'_RECEPTOR_NOT_REPRODUCIBLE')
            else:
                p=prepared_path(cap,v['target']); retained=retained_ions(p,e)
                e['recognition'][arm]['retained_ions']=retained
                own=PRE/f"receptores/{e['pdb_id']}-{arm}.pdbqt"; own.parent.mkdir(parents=True,exist_ok=True); own.write_bytes(p.read_bytes())
                if arm=='CON' and not all(i['present'] for i in retained): reasons.append('CON_ION_REMOVED_BY_PREPARATION')
        if e['catalog_preparation']['state']=='PREPARED' and not e['recognition']['SIN_matches_catalog']:
            reasons.append('SIN_DIFFERS_FROM_CATALOG')
            if e['pdb_id']=='8UBR':
                e['recognition']['SIN_catalog_divergence']='Variant SIN retains 70 additional atoms of ATP A1502/A1503; every shared protein atom is identical. Catalogue preparation passes site_ligand=ATP and removes that reference cofactor; variant ingestion omits site_ligand during prepare_target for the new USR ID, retaining the other ATP instances. Thus SIN is not the catalogue baseline. Excluded before docking; no product patch.'
                reasons.append(e['recognition']['SIN_catalog_divergence'])
        if e.get('reference_error'): reasons.append('CAL_REFERENCE_UNMAPPABLE: '+e['reference_error'])
        if not e['microstate']['reproducible']: reasons.append('MICROSTATE_NOT_REPRODUCIBLE')
        e['exclusion']=reasons or None
    n=sum(e['principal'] and not e['exclusion'] for e in lig); controls=sum(not e['principal'] and not e['exclusion'] for e in lig)
    protocol={'experiment':'MET-01-R1-ION-DEL-SITIO','replicates':'MET-01-ION-DEL-SITIO','change_from_MET01':'Product moved from f0e64086 to 9ce8b104, which includes a27ded64: evaluation keeps cofactors_whitelist instead of re-preparing the receptor without it (the MET-01 pilot failure). Population, configuration, seeds, gate, RMSD, validity, power and stop rules are MET-01 verbatim. CCD files are byte-identical copies of MET-01. Recognition, microstates, diagnostic forms and crystal probes are re-derived on the new product, before any docking.','registered_at':now(),'product_commit':PRODUCT,'entries':lig,'population':{'principal':35,'controls':6,'evaluable_principal':n,'evaluable_controls':controls},'power':read(PRE/'potencia.json'),'configuration':cal.CONFIG_CASO,'seeds':[42,43,44,45,46],'pilot_entry':next(e['pdb_id'] for e in lig if not e['exclusion']),'pilot_excluded_from_analysis':True,'freeze':'Tracked source, protocol and HEAD unchanged from the first confirmatory capsule until the last evaluation; only ignored output files are written. Any harness repair requires shutting down every capsule, documenting and committing the repair, then resuming without overwriting terminal records.',
              'crystal_selection':'Same first model and blank/A altlocs as medir_metales_del_sitio; site_ligand instance nearest box center. CAL _cristal unmodified receives this explicitly selected input. Cases it cannot map are excluded before docking, not repaired.',
              'rmsd':'Unmodified CAL _neutro_sin_h and _top1; symmetric heavy-atom rdMolAlign.CalcRMS, no alignment. Do not round before the 2.0 A threshold. All returned poses recorded; Vina may return fewer than the requested 9.',
              'microstates':'Original CCD SMILES through normal product pH 7.4, entrada tautomer. Expected SMILES and charge frozen in two processes by CAL _microestados; assert exact effective identity at every seed. Conformers generated by the product independently from crystal coordinates.',
              'diagnostic':'Independent sulfonamide N / hydroxamate O / thiol S SMARTS hypotheses within 2.8 A of Zn, preserving the main microstate elsewhere. Fixed candidate pHs [7.4,10.0,12.0], select lowest yielding exactly the prescribed full graph in two processes. pH is an explicitly changed ligand-preparation parameter, not a claimed binding pH. Unrepresentable hypotheses recorded but not docked; no post-docking selection.',
              'pose_gate':'CAL exact gate: at least 3/5 top-1 RMSDs <=2.0 A, AND every RMSD-successful top-1 passed PoseBusters dock MF-33-H-COR. A fourth near-crystal seed that fails physical validity fails the entry, as CAL does.',
              'gate':{'test':'Exact bilateral paired sign test, alpha 0.05. Rate effect is (favor_CON-favor_SIN)/paired_n.','minimum_effect':.4,'design_q':.5,'minimum_n':25,'inconclusive_precedence':'Paired n<25 or >30% principal exclusions -> INCONCLUSIVE, irrespective of observed effect.','GO':'Significant favor_CON>favor_SIN, no evaluable control loses reproduction, and at least four of six controls evaluable.','NO_GO':'Adequate principal n and nonsignificant or adverse comparison, or an evaluable control demonstrably loses reproduction.','missing_controls':'Favorable significant result with fewer than four evaluable controls -> INCONCLUSIVE. Excluded controls are not claimed to be unharmed.','change_before_measurement':'Original all-six control criterion cannot yield GO because recognition excludes 5I3T (unpreparable without ion) and 8WGR (CAL reference unmatchable, CON unrepresentable). Requiring no harm in all evaluable controls and at least four keeps more than half the planned controls and a test capable of GO without pretending the omitted systems were tested. Conclusion and whitelist proposals restricted to evaluable entries.'},
              'analysis_denominator':'Preexcluded entries excluded even if a stray terminal record exists. Missing or infrastructural failed seed makes paired entry incomplete, never a success. Product technical rejection is a scientific zero, recorded separately. Principal and control denominators stay explicit.',
              'statistical_assumption':'Exact sign probabilities assume independently exchangeable discordance signs under the null. The unit fixed by the task is a PDB entry, not an independent protein target; repeated target families may correlate. The p-value addresses this entry-level model and must not be generalized to independent targets or all metalloproteins.',
              'stop_rule':'Stop all capsules if >30% terminal confirmatory evaluations are infrastructural failures. One identical technical retry, retaining both attempts; product deterministic rejection is not infrastructure.',
              'recommendation':'GO: propose whitelist only for coordinated, favor-CON entries. NO_GO: keep removal and abstention; CON is baseline for a future coordination model. INCONCLUSIVE: abstain from catalogue change, list missing evidence per entry. Owner decides; this branch never changes the catalogue.',
              'capsule':'API only, reuses QA entornoBackend/puertosDe/carpetasDe unchanged, skips frontend and completarWorktree to obey scripts/docs-only scope; python-embed and real Vina, VINA_CPU=4, fully isolated profile/data. PYTHONDONTWRITEBYTECODE=1; read-only shared model/OpenBabel resources; no build/stage/smoke.',
              'posebusters_crystal_probe':'entrada/posebusters_cristal.json, measured before docking; exact product evaluar_pose_fisica with Meeko index map and frozen normal microstate. Actual PoseBusters masks omit Meeko ATOM metal ions from both inorganic and protein checks: PASA is not validation of metal contacts. No validator adjustment; distances to ions recorded independently, outside the gate.',
              'sources':[{'url':'https://www.wwpdb.org/data/ccd','opened':'2026-10-11','use':'CCD descriptions and stereochemical SMILES; each downloaded CIF URL/date/hash accompanies the entry.'},{'url':'https://posebusters.readthedocs.io/en/latest/api.html','opened':'2026-10-11','use':'Intermolecular distance/volume checks distinguish inorganic cofactors; the product behavior is measured separately.'},{'url':'https://autodock-vina.readthedocs.io/en/latest/docking_zinc.html','opened':'2026-10-11','use':'AutoDock4Zn requires its distinct force field and pseudoatoms; MET uses the product Vina scoring, not that protocol.'}]}
    write(PRE/'protocolo.json',protocol)
    print('Protocol ready',n,'principal',controls,'controls','exclusions',[(e['pdb_id'],e['exclusion']) for e in lig if e['exclusion']],flush=True)

def report():
    if (EXP/'piloto/parada.json').exists():
        spec=importlib.util.spec_from_file_location('met01_stop_report',SOURCE/'pilot_stop.py')
        module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        module.report(); return
    metrics=read(EXP/'metrics.json'); protocol=read(PRE/'protocolo.json'); reg=read(PRE/'registration_commit.json')['commit']
    principal=metrics['principal']; controls=metrics['controls']; verdict=metrics['decision']
    excluded=[e for e in protocol['entries'] if e['exclusion']]
    masks=[a for r in read(PRE/'posebusters_cristal.json')['rows'] for a in r.get('metal_classification_by_actual_PB_masks',[])]
    probe=read(PRE/'posebusters_cristal.json')['rows']; probed=[r for r in probe if r.get('arms',{}).get('CON',{}).get('evidence')]
    crystal_metal_fail=[r['pdb_id'] for r in probed if any(c['estado']=='FALLA' and c['check'] in ['minimum_distance_to_inorganic_cofactors','volume_overlap_with_inorganic_cofactors'] for c in r['arms']['CON']['evidence']['checks'])]
    rows=[json.loads(l) for l in (EXP/'per_complex.jsonl').read_text(encoding='utf-8').splitlines()]
    con_rows=[r for r in rows if r['arm']=='CON' and r['outcome']=='SUCCESS']
    his=sum(r['histidine_warning'] for r in con_rows)
    diagnostic=[e for e in protocol['entries'] if (e.get('diagnostic') or {}).get('representable') and not e['exclusion']]
    diagnostic_rows=[r for r in rows if r['arm'].startswith('DIAG')]
    recommendation=('Proponer whitelist únicamente en entradas coordinadas con reproducción sólo CON; decisión del propietario.' if verdict=='GO' else 'Mantener retirada y abstención. CON aporta una línea base para un futuro modelo de coordinación (M5).' if verdict=='NO_GO' else 'Mantener la abstención y resolver la evidencia que falta antes de cambiar el catálogo.')
    title=f'Metales del sitio con Vina: {verdict} en el redocking pareado'
    lead=f"MET-01-R1 repite MET-01 sobre un producto que sí conserva la whitelist y compara conservar y retirar el ion en {principal['paired_n']} de 35 entradas coordinadas evaluables, con cinco semillas por brazo. Discordancias: {principal['favor_CON']} a favor de CON y {principal['favor_SIN']} a favor de SIN; p bilateral = {principal['exact_two_sided_p']:.6g}."
    power35=power(35,.5,.4); power_actual=power(principal['paired_n'],.5,.4) if principal['paired_n'] else 0
    paper=f'''---
titulo: {json.dumps(title,ensure_ascii=False)}
entradilla: {json.dumps(lead,ensure_ascii=False)}
---

**{verdict}.** {recommendation}

El catálogo retira los metales que no declara. MET-01-R1 pregunta si conservarlos,
con el Vina que ejecuta MolDesign, mejora la reproducción de la pose de su propio
cristal. El ion no introduce por sí solo un modelo de coordinación: el protocolo
AutoDock4Zn descrito por los autores requiere parámetros, mapas y pseudoátomos
distintos. Aquí se usa Vina del producto. [Documentación de AutoDock](https://autodock-vina.readthedocs.io/en/latest/docking_zinc.html).

## Qué se fijó antes de acoplar

Producto `{PRODUCT}`, Meeko 0.7.1, Vina 1.2.7, PoseBusters 0.6.5 `dock` con
reconstrucción de H MF-33-H-COR. Exhaustividad 8, nueve poses solicitadas, un
conformador y semillas 42–46. El prerregistro es el commit `{reg}`;
el piloto se conserva aparte y la entrada vuelve a medirse.

La población fija son 41 entradas, 52 iones: 35 entradas coordinadas
geométricamente y seis controles. Una entrada es el receptor y la instancia de
`site_ligand` más cercana a su caja. SIN y CON se crean por la API de variantes,
con caja y cadena heredadas. Dos procesos de preparación contrastan sus hashes,
y SIN se contrasta con el receptor del catálogo. Los SMILES estereoquímicos
proceden del CCD, con definición, URL, fecha y SHA-256 archivados; las coordenadas
del conformador no proceden del cristal. [Diccionario wwPDB](https://www.wwpdb.org/data/ccd).

Se reutilizan sin modificar `Backend.evaluar`, `_cristal`, `_neutro_sin_h` y
`_top1` de CAL-8HFI-01. El RMSD es simétrico de átomos pesados, sin alinear.
El gate exacto de CAL exige al menos tres RMSD ≤2 Å y validez de **todas** las
semillas cuyo RMSD cumple. El mejor de las poses devueltas es descriptivo.
Vina puede devolver menos de las nueve solicitadas.

## Potencia y exclusiones

La prueba de signos es exacta, bilateral, α=0,05. Seis discordantes 6:0 bastan
para p=0,03125: 17,1 puntos sobre 35 entradas. Ese límite de significación no es
un efecto detectable con 80 % de potencia. Se declaró como efecto mínimo una
diferencia de 40 puntos, bajo un modelo con 50 % de discordancias: potencia
{100*power35:.2f} % con 35, 82,02 % con 25 y {100*power_actual:.2f} % con el n final.
Las diferencias detectables al 80 % con ese modelo son 33,7 puntos con 35 y
39,4 con 25. La tabla sellada incluye otros niveles de discordancia; estas
potencias dependen del modelo y no garantizan detectar efectos moderados.
La probabilidad exacta presupone signos discordantes independientes e
intercambiables bajo la nula. La unidad del encargo es una entrada PDB: varias
comparten diana/familia, lo que puede correlacionarlas. La p no se generaliza
a dianas independientes ni a metaloenzimas en conjunto.

Hubo {len(excluded)} exclusiones fijadas antes de docking;
{principal['excluded_n']} de las 35 principales quedan fuera al cierre.
Las causas por entrada están en el informe: receptor no preparable, brazo CON
no representable o referencia que el método de CAL no puede casar. No se
sustituye ninguna. {'Todos los controles fueron evaluables.' if controls['all_evaluable'] else f"Controles evaluables: {controls['evaluable_n']} de {controls['population_n']}."}
Un n<25 o más del 30 % de exclusiones principales fuerza INCONCLUSIVE.
Antes de docking se cambió el requisito de los seis controles: dos no son
evaluables por preparación/referencia, lo que habría impedido cualquier GO.
Se exige no pérdida en todos los controles evaluables y al menos cuatro de seis
medidos. Con menos de cuatro, una señal favorable queda INCONCLUSIVE. El alcance
se restringe a las entradas evaluables; no se afirma ausencia de daño en las omitidas.

## Qué salió

| Medida | Resultado |
|---|---:|
| Entradas principales pareadas | {principal['paired_n']}/35 |
| Reproduce sólo CON | {principal['favor_CON']} |
| Reproduce sólo SIN | {principal['favor_SIN']} |
| Diferencia pareada de tasas | {(principal['rate_difference'] or 0)*100:.2f} puntos |
| p bilateral exacta | {principal['exact_two_sided_p']:.8g} |
| Controles con pérdida demostrada | {controls['harm_n']} |
| Corridas confirmatorias | {metrics['total_runs']} |
| Fallos de infraestructura | {metrics['failures_n']} |
| Rechazos del producto | {metrics['product_rejections_n']} |

## El metal, PoseBusters y la histidina

Antes de Vina se pasó el cristal, con el microestado normal congelado, por
`evaluar_pose_fisica` del producto, con mapa de Meeko y cada receptor preparado.
En {len(probed)} entradas se pudo evaluar CON; en {len(crystal_metal_fail)} falló
algún control de distancia o volumen frente a cofactores inorgánicos
({', '.join(crystal_metal_fail) or 'ninguna'}). Los restantes fallos del cristal
se conservan con su nombre: no se atribuyen automáticamente al ion.
La batería ofrece controles de cofactores inorgánicos, pero **el producto no
comprueba estos contactos con el metal**: Meeko escribe el ion como `ATOM`;
la máscara inorgánica lo excluye como proteína y la máscara de proteína lo
excluye por su elemento inorgánico. La inspección con las máscaras reales está
archivada ({len(masks)} átomos metálicos cargados, {sum(a['selected_for_inorganic_checks'] for a in masks)} seleccionados
por la máscara inorgánica y {sum(a['selected_for_protein_checks'] for a in masks)} por la de proteína).
Por ello los PASA inorgánicos son vacuos en este caso, no una
validación de coordinación. No se alteró el validador. [API de PoseBusters](https://posebusters.readthedocs.io/en/latest/api.html).

Preparación avisó de His con H en el nitrógeno coordinante en {his}/{len(con_rows)}
corridas CON normales. No se corrigió ninguna durante el experimento.

## Diagnóstico del ligando, fuera del gate

Se fijaron reglas químicas independientes para retirar un protón del N de una
sulfonamida, O de un hidroxamato o S de un tiol que queda a ≤2,8 Å de Zn.
Se conserva el microestado normal en los demás centros. Son hipótesis de anclaje,
no poblaciones de unión validadas. {len(diagnostic)} entradas admitieron exactamente
esa forma mediante la opción pública de preparación a pH 7,4, 10 o 12, verificada
en dos procesos: {len(diagnostic_rows)} corridas diagnósticas en los dos brazos.
El pH que cambia se declara por entrada; no se interpreta como pH experimental
de unión. Las hipótesis que el producto reprotona o cambia en otros centros
quedan no representables y no se disfrazan de un diagnóstico ejecutado.

## Qué no dice

Este redocking usa la estructura de su propio cristal, un escenario favorable;
no demuestra cross-docking, actividad, afinidad, energía de coordinación,
calibración ni transferencia a FEP. Una distancia corta es geometría, no energía.
Los scores de SIN y CON describen receptores diferentes y no se comparan como
energías de unión. Una falta de significación tampoco prueba equivalencia.

## Consecuencia y reproducción

{recommendation} No se cambió el catálogo, M5 ni el producto.

El informe por receptor está en
`docs/auditorias/metales-con-y-sin-ion-R1-2026-10-21.md`. Protocolo, potencia,
CCD, preparados, salida cruda, filas y métricas están en
`scripts/artifacts_science/MET-01-R1-ION-DEL-SITIO/`.
`python scripts/medir_met01r1.py selftest` verifica controles sintéticos;
`python scripts/medir_met01r1.py analyze` reconstruye las métricas sin la sesión.
El MET-01 original (INCONCLUSIVE) está en `docs/papers/MET-01-ION-DEL-SITIO.md`.
El runtime no se distribuye por git y se declara en `sellos_no_distribuidos.json`.
'''
    table=['| Entrada | Metal | Coordina | SIN RMSD / válido / conjunto | CON RMSD / válido / conjunto | Reproduce SIN / CON | His CON | Recomendación |','|---|---|---|---|---|---|---|---|']
    exclusions=[]
    for x in metrics['entries']:
        def cell(arm):
            r=x['arms'].get(arm,{})
            return '—' if not r.get('n') else f"{r['rmsd_successes']}/5 · {r['physical_passed']}/5 · {r['joint_successes']}/5"
        sin=x['arms']['SIN']; con=x['arms']['CON']; local='sí' if con['reproduces'] and not sin['reproduces'] else 'no'
        if x['exclusion']: rec='Abstenerse: excluida'; exclusions.append(f"- **{x['entry']}**: "+'; '.join(x['exclusion']))
        elif verdict=='GO' and x['principal'] and local=='sí': rec='Proponer whitelist al propietario'
        elif verdict=='NO_GO': rec='Retirar y abstenerse; baseline M5'
        else: rec='Abstenerse de cambiar el catálogo'
        table.append(f"| {x['entry']} | {', '.join(sorted({i['metal'] for i in x['ions']}))} | {'sí' if x['principal'] else 'control'} | {cell('SIN')} | {cell('CON')} | {'sí' if sin['reproduces'] else 'no'} / {'sí' if con['reproduces'] else 'no'} | {con.get('histidine_warning_n',0)}/5 | {rec} |")
    audit=f'''# MET-01-R1: metales con y sin ion — 2026-10-21

**{verdict}.** {recommendation}

Producto `{PRODUCT}`, prerregistro `{reg}`, Vina 1.2.7, Meeko 0.7.1,
PoseBusters 0.6.5 dock MF-33-H-COR, 8/9/1, semillas 42–46.
La tabla compara el brazo normal a pH 7,4. RMSD / válido / conjunto son tres
conteos separados: RMSD ≤2 Å, PoseBusters passed y ambos a la vez. El gate
exacto de CAL además exige que todos los RMSD exitosos sean físicamente válidos.
Un guion es no medido, no cero de reproducción. Las cifras de cada corrida,
los nueve RMSD solicitados (o las poses realmente devueltas), distancias a cada
ion y requisitos completos están en `per_complex.jsonl` y sus crudos sellados.

{chr(10).join(table)}

## Exclusiones anteriores al docking

{chr(10).join(exclusions)}

Las exclusiones de referencia describen el alcance del método CAL, no prueban
que el depósito sea erróneo. Los HTTP 500 de variantes se contrastan con el
fallo determinista del preparador del catálogo; no son corridas fallidas de Vina.
Los errores completos y hashes están en el protocolo.

## Potencia, gate y límites

Discordancias CON:SIN={principal['favor_CON']}:{principal['favor_SIN']},
n={principal['paired_n']}, p={principal['exact_two_sided_p']:.8g},
exclusiones principales={principal['excluded_n']}/35.
Efecto mínimo preregistrado=40 puntos; q=0,5 declarado; potencia
con n=35: {100*power35:.2f} %, con n evaluable: {100*power_actual:.2f} %.
Las tablas exactas y los repartos significativos están en `entrada/potencia.json`.
Controles completos={controls['all_evaluable']}; pérdidas demostradas={controls['harm_n']}.
No se aplica selección retrospectiva ni se proponen entradas Verificadas.

## Reproducción mínima

1. Aprovisionar el runtime declarado y verificar sus hashes.
2. `python scripts/medir_met01r1.py selftest` y `analyze` reconstruyen el análisis
   desde los archivos versionados, sin cápsula ni token.
3. Para una nueva corrida, crear cápsulas nuevas. Para cada entrada/arm:
   `POST /targets/{{pdb_id}}/variants` con `name` y `cofactors_whitelist` de
   `entrada/protocolo.json`; heredar caja/cadena y verificar SHA-256 esperado.
4. El arnés llama sin modificación a `calibracion_receptor.Backend.evaluar`:
   preflight → submit → status → result persistido → SDF de poses → Preparación.
   `run --phase confirmatory --shard 1` (también 2 y 3) omite registros terminales;
   para repetir evidencia hay que usar un directorio nuevo, nunca reescribirla.
5. Verificar `scripts/validar_sellos.py --check`. Los privados de las cápsulas
   no se distribuyen; las salidas científicas necesarias sí.

## Condiciones diagnósticas y del validador

Reglas SMARTS, forma completa, pH y dos comprobaciones por proceso están en
el prerregistro. {len(diagnostic)} entradas diagnósticas ejecutables,
{len(diagnostic_rows)} corridas, fuera del gate. El producto no ofrece una
opción general para fijar cualquier protonación de ligando; las formas
no representables están declaradas.

Cristales CON con fallo de controles inorgánicos:
{', '.join(crystal_metal_fail) or 'ninguno de los evaluados'}.
Avisos de His coordinante con H: {his}/{len(con_rows)} corridas CON normales.
No se corrige preparación ni PoseBusters para conseguir otro veredicto.

La decisión es del propietario. Redocking no mide actividad ni energía de
coordinación; no acredita compatibilidad con FEP ni generaliza al catálogo.
'''
    outputs={'paper.md':('docs/papers/MET-01-R1-ION-DEL-SITIO.md',paper),'audit.md':('docs/auditorias/metales-con-y-sin-ion-R1-2026-10-21.md',audit)}
    for name,(dest,text) in outputs.items():
        p=ROOT/dest; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(text,encoding='utf-8',newline='\n')
        p=EXP/'publicacion'/name; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(text,encoding='utf-8',newline='\n')
    print('Paper and audit written')

if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('command',choices=['recon','ccd','ligands','diagnostics','crystal-probe','inspect-validator','power','preregister','run','selftest','merge','analyze','verify','report']); ap.add_argument('--phase',choices=['pilot','confirmatory']); ap.add_argument('--shard',type=int,choices=[1,2,3],default=1); a=ap.parse_args()
    if a.command=='recon': recon()
    elif a.command=='ccd': ccd()
    elif a.command=='ligands': freeze_ligands()
    elif a.command=='diagnostics': diagnostic_states()
    elif a.command=='crystal-probe': crystal_probe()
    elif a.command=='power': power_report()
    elif a.command=='run':
        if not a.phase: ap.error('--phase is required')
        run_shard(a.phase,a.shard)
    elif a.command=='selftest': selftest()
    elif a.command=='analyze': analyze()
    elif a.command=='merge': merge()
    elif a.command=='verify': verify()
    elif a.command=='preregister': preregister()
    elif a.command=='report': report()
    elif a.command=='inspect-validator': inspect_validator()
