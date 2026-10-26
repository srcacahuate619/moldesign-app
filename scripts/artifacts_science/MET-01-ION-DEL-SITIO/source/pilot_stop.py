"""Post-stop audit of pilot evidence; never submits or changes product inputs."""
import ast
import collections
import gzip
import importlib.util
import json
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('met01_audit', HERE / 'met01.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
EXP, ROOT = m.EXP, m.ROOT


def produce():
    from rdkit import Chem
    from rdkit.Chem import rdMolAlign
    protocol = m.read(EXP / 'entrada/protocolo.json')
    e = next(x for x in protocol['entries'] if x['pdb_id'] == '1BN1')
    # Execute only these two original pure functions, extracted unchanged.
    src = ROOT / 'backend/core/models.py'
    tree = ast.parse(src.read_text(encoding='utf-8-sig'))
    functions = [x for x in tree.body if isinstance(x, ast.FunctionDef)
                 and x.name in ['_coerce_hotspots', '_coerce_json_value']]
    assert len(functions) == 2
    ns = {}
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(src), 'exec'), ns)
    probes = []
    for val in [['ZN'], ['MG'], ['CA'], ['K'], json.dumps(['ZN']), [{'name': 'ZN'}]]:
        probes.append({'input': val, 'output': ns['_coerce_hotspots'](val)})
    assert all(x['output'] == [] for x in probes[:5])
    assert probes[-1]['output'] == [{'name': 'ZN'}]
    for rel in ['backend/core/models.py', 'backend/services/pipeline/runner.py',
                'backend/api/routers/evaluation.py']:
        dest = EXP / 'source/product_sources' / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        data = (ROOT / rel).read_bytes()
        if dest.exists(): assert dest.read_bytes() == data
        else: dest.write_bytes(data)

    sessions = []
    for folder in [EXP / '_work/pilot', EXP / '_work/pilot-setup-failures']:
        for p in folder.glob('**/private-session.json'):
            sessions.append(p.parent)
    sessions += list((ROOT / 'scripts/met01/tmp').glob('c-p1-*'))
    records = []
    expected_sin = e['recognition']['SIN']['sha256']
    expected_con = e['recognition']['CON']['sha256']
    assert expected_sin != expected_con
    ref = m.cal._neutro_sin_h(m.crystal(e))
    for path in sorted((EXP / '_work/pilot/shard-1').glob('*-attempt*.json.gz')):
        raw = json.loads(gzip.decompress(path.read_bytes()))
        match = re.fullmatch(r'1BN1-(SIN|CON)-s(\d+)-attempt(\d+)\.json\.gz', path.name)
        arm, seed, attempt = match[1], int(match[2]), int(match[3])
        result = raw['resultado']
        dp = result['docking_protocol']
        prov = dp['execution_provenance']
        actual = prov['receptor_sha256']
        expected = expected_sin if arm == 'SIN' else expected_con
        assert actual == expected_sin
        assert dp['seed'] == seed and dp['exhaustiveness'] == 8 and dp['num_poses'] == 9
        assert prov['cpu'] == 4 and result['vina_version'] == '1.2.7'
        state = result['ligand_state']
        assert state['smiles_acoplado'] == e['microstate']['smiles_acoplado']
        snapshot_rel = f'runs/receptors/{actual}.pdbqt'
        dest = EXP / 'piloto/receptores_utilizados' / f'{actual}.pdbqt'
        session = next((p for p in sessions if (p / 'data' / snapshot_rel).is_file()),None)
        snapshot = (session / 'data' / snapshot_rel).read_bytes() if session else dest.read_bytes()
        assert m.sha(snapshot) == actual
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists(): assert dest.read_bytes() == snapshot
        else: dest.write_bytes(snapshot)
        metal_atoms = [l for l in snapshot.decode().splitlines()
                       if l.startswith(('ATOM', 'HETATM')) and l.split()[-1].upper() in ['ZN','MG','CA','K']]
        assert not metal_atoms
        mol, energy, matched = m.cal._top1(raw)
        assert matched
        supplier = Chem.SDMolSupplier()
        supplier.SetData(raw['poses_sdf'], removeHs=False)
        poses = list(supplier)
        assert all(p is not None for p in poses) and len(poses) == len(result['docking_poses'])
        rmsds = [float(rdMolAlign.CalcRMS(m.cal._neutro_sin_h(p), ref)) for p in poses]
        top = next(p for p in result['structural_evidence']['poses'] if p['rank'] == 1)
        assert raw['persisted_result']['docking_protocol'] == dp
        declared = raw['preflight_full']['effective_config']['heteroatom_policy']['cofactors_whitelist_declared']
        used = prov['receptor_prep']['cofactors_whitelist']
        assert declared == used == []
        log_rel = prov['log_path']
        # Resolve the unique session containing this run log, never its backend log.
        log_dest = EXP / 'piloto/vina_logs' / f'{path.name[:-8]}.log'
        log_session = next((p for p in sessions if (p / 'data' / log_rel).is_file()),None)
        log = (log_session / 'data' / log_rel).read_bytes() if log_session else log_dest.read_bytes()
        assert m.sha(log) == prov['log_sha256']
        log_dest.parent.mkdir(parents=True, exist_ok=True)
        if log_dest.exists(): assert log_dest.read_bytes() == log
        else: log_dest.write_bytes(log)
        blocks = raw['preparacion']['bloques']
        reqs = [r for b in (blocks if isinstance(blocks,list) else blocks.values()) for r in b['requisitos']]
        reqs = [r for r in reqs if r['clave'] in ['entorno.metales_cofactores','receptor.protonacion','entorno.referencia']]
        distances = [{'metal': i['metal'], 'metal_id': i['metal_id'],
                      'reference_position_only': True, 'ion_present_in_used_receptor': False,
                      'top1_donor_A': min(m.math.dist(tuple(mol.GetConformer().GetAtomPosition(a.GetIdx())),i['xyz'])
                                         for a in mol.GetAtoms() if a.GetSymbol() in ['N','O','S']),
                      'crystal_donor_A': min(m.math.dist(tuple(m.crystal(e).GetConformer().GetAtomPosition(a.GetIdx())),i['xyz'])
                                            for a in m.crystal(e).GetAtoms() if a.GetSymbol() in ['N','O','S'])}
                     for i in e['ions']] if arm == 'CON' else []
        records.append({'id': path.name[:-8], 'entry':'1BN1', 'requested_arm':arm,
                        'effective_arm':'SIN', 'seed':seed, 'attempt':attempt,
                        'phase':'pilot', 'in_confirmatory_gate':False,
                        'outcome':'VALID_PILOT_SIN' if actual == expected else 'INVALID_RECEPTOR',
                        'whitelist_requested':[] if arm == 'SIN' else ['ZN'],
                        'whitelist_preflight':declared, 'whitelist_execution':used,
                        'receptor_expected_sha256':expected, 'receptor_used_sha256':actual,
                        'receptor_used_snapshot':str(dest.relative_to(EXP)).replace('\\','/'),
                        'recipe':prov['receta_receptor'], 'execution_provenance':prov,
                        'microstate_smiles':state['smiles_acoplado'],
                        'microstate_sha256':m.sha(state['smiles_acoplado'].encode()),
                        'task_id':raw['task_id'], 'rmsd_top1_A':float(rdMolAlign.CalcRMS(m.cal._neutro_sin_h(mol),ref)),
                        'rmsd_poses_A':rmsds, 'returned_poses':len(poses),
                        'physical_status':top['status'], 'physical_evidence':top,
                        'failed_checks':[x for x in top.get('checks',[]) if x.get('estado')=='FALLA'],
                        'ion_distances':distances, 'vina_energy_kcal':energy,
                        'preparation_requirements':reqs,
                        'histidine_warning': 'His que coordinan un metal conservado con el hidrógeno' in json.dumps(reqs,ensure_ascii=False),
                        'seconds':raw['segundos'], 'raw':str(path.relative_to(EXP)).replace('\\','/'),
                        'raw_sha256':m.sha(path.read_bytes()), 'vina_log':str(log_dest.relative_to(EXP)).replace('\\','/'),
                        'vina_log_sha256':m.sha(log), 'product_commit':m.PRODUCT})
    assert len(records) == 11
    counts = dict(collections.Counter(r['outcome'] for r in records))
    assert counts == {'INVALID_RECEPTOR':6, 'VALID_PILOT_SIN':5}
    lines = ''.join(json.dumps(r,ensure_ascii=False,sort_keys=True,allow_nan=False)+'\n' for r in records)
    (EXP/'piloto/per_attempt.jsonl').write_text(lines,encoding='utf-8',newline='\n')
    stop = m.read(EXP/'_work/STOP')
    assert stop['fraction'] == 3/8
    summary = {'phase':'pilot','complete':False,'confirmation_started':False,
               'planned_confirmatory_runs':380,'confirmatory_runs':0,
               'valid_principal_pairs':0,'valid_control_pairs':0,
               'valid_pilot_SIN_seed_seconds':[r['seconds'] for r in records if r['requested_arm']=='SIN'],
               'raw_completed_Vina_attempts':11,'outcomes':counts,
               'setup_Vina_failures':2,'final_pilot_terminal_records':8,
               'final_pilot_guard_failures':3,'terminal_guard_failure_fraction':3/8,
               'stop_record':stop,'closed_reason':'PRODUCT_ARM_INVALIDATION',
               'mechanism':'_coerce_hotspots filters list elements to dict, dropping metal strings before preflight and pipeline; CON was re-prepared without Zn.',
               'pure_original_function_probes':probes,
               'prepared_CON_sha256':expected_con,'used_CON_sha256':expected_sin,
               'prepared_CON_whitelist':['ZN'],'used_CON_whitelist':[],
               'invalid_CON_seeds':[42,43,44], 'attempts_each':2,
               'planned_principal_n':28,'conditional_power_at_planned_n':m.power(28,.5,.4),
               'no_time_forecast':'Pilot did not complete valid SIN/CON pairing; no full-cohort runtime forecast is warranted.',
               'no_demuestra':'No estimate of the effect of retaining the ion; pilot is outside the gate, and no valid CON was docked.',
               'product_commit':m.PRODUCT,'preregistration_commit':'32e552ebe823d8e289582102d52424bce3cd6d4a'}
    m.write(EXP/'piloto/parada.json',summary)
    print(json.dumps({k:summary[k] for k in ['outcomes','terminal_guard_failure_fraction','conditional_power_at_planned_n','closed_reason']},ensure_ascii=False))


def report():
    p=m.read(EXP/'entrada/protocolo.json')
    s=m.read(EXP/'piloto/parada.json')
    metrics=m.read(EXP/'metrics.json')
    assert metrics['decision']=='INCONCLUSIVE' and metrics['principal']['paired_n']==0
    reg=s['preregistration_commit']
    preexcluded=[e for e in p['entries'] if e['exclusion']]
    attempts=[json.loads(line) for line in (EXP/'piloto/per_attempt.jsonl').read_text(encoding='utf-8').splitlines()]
    sin=[r for r in attempts if r['requested_arm']=='SIN']
    rmsd_ok=sum(r['rmsd_top1_A']<=2 for r in sin)
    valid=sum(r['physical_status']=='passed' for r in sin)
    joint=sum(r['rmsd_top1_A']<=2 and r['physical_status']=='passed' for r in sin)
    refs=m.read(EXP/'entrada/posebusters_cristal.json')['rows']
    masks=[a for r in refs for a in r.get('metal_classification_by_actual_PB_masks',[])]
    assert len(masks)==52 and not any(a['selected_for_inorganic_checks'] or a['selected_for_protein_checks'] for a in masks)
    title='MET-01 no puede comparar el ion: la evaluación pierde la whitelist'
    lead='INCONCLUSIVE. La variante CON conserva Zn, pero las seis tentativas CON del piloto 1BN1 usaron el receptor SIN. No se inició la fase confirmatoria ni se estimó el efecto del ion.'
    paper=f'''---
titulo: {json.dumps(title,ensure_ascii=False)}
entradilla: {json.dumps(lead,ensure_ascii=False)}
---

**INCONCLUSIVE.** MET-01 se detuvo en el piloto porque el producto cambió el
receptor del brazo CON. La evidencia no responde si conservar el ion mejora
el redocking. Se mantiene la abstención; cualquier arreglo del producto y
repetición requieren otro encargo y un experimento MET-01-R1.

## Qué se fijó antes de acoplar

Producto `{m.PRODUCT}`, Vina 1.2.7, Meeko 0.7.1, Python embebido 3.11.9,
RDKit 2025.9.6 y PoseBusters 0.6.5 `dock`, con H reconstruidos bajo
MF-33-H-COR. Exhaustividad 8, nueve poses solicitadas, un conformador,
CPU=4 y semillas 42–46. Prerregistro: `{reg}`.

La población fija tiene 41 entradas y 52 iones: 35 entradas coordinan un ion
por geometría del cristal y seis son controles. Los SMILES del CCD, sus URL,
fechas y hashes, microestados normales y formas diagnósticas se congelaron
antes de Vina. Se conservaron las definiciones completas.
[Diccionario wwPDB](https://www.wwpdb.org/data/ccd).

Se reutilizan sin modificar `Backend.evaluar`, `_cristal`, `_neutro_sin_h`
y `_top1` de CAL-8HFI-01. RMSD simétrico de átomos pesados, sin alinear,
del top-1 comprobado contra el PDBQT; todos los RMSD de las poses devueltas
se conservan. Reproduce una entrada si ≥3 de 5 semillas dan RMSD ≤2 Å
y **todas** las semillas cuyo RMSD cumple son físicamente válidas.

## Potencia y reconocimiento

Prueba pareada exacta de signos, bilateral, α=0,05. Seis discordancias 6:0
dan p=0,03125: 17,14 puntos sobre n=35, un límite de significación, no de
potencia. El efecto mínimo preregistrado fue 40 puntos de tasa pareada,
bajo el supuesto explícito de 50 % de discordancias: potencia de 94,76 %
con n=35, 82,02 % con n=25 y {100*s['conditional_power_at_planned_n']:.2f} % con las 28 entradas
principales previstas. A 80 % de potencia son detectables 33,7 puntos con
35 y 39,4 con 25 bajo ese mismo modelo. La tabla de sensibilidad está sellada.
No se garantiza esa potencia para tasas desconocidas de discordancia.

Dos preparaciones en procesos distintos dieron hashes repetibles en 39 SIN
y 37 CON. SIN coincide con el catálogo en 38 de las 39 preparables. Se
excluyeron antes de docking nueve entradas: {', '.join(e['pdb_id'] for e in preexcluded)}.
Son siete principales y dos controles. 8UBR conserva dos ATP adicionales
en la variante, al perderse `site_ligand` durante la ingesta; se excluyó
antes de Vina, sin arreglarlo. Las demás causas de preparación o referencia
no casable se documentan por entrada. Quedaban 28 principales y cuatro controles.

Se fijó antes de medir un cambio del gate propuesto: no pérdida de
reproducción en todos los controles evaluables, con mínimo cuatro de seis.
Dos controles ya eran inevaluables por preparación/referencia. Un n<25 o
más de 30 % de exclusiones principales exige INCONCLUSIVE. El cambio no
permite afirmar ausencia de daño en los controles omitidos.

## Qué reveló el piloto

La API creó CON de 1BN1 con `cofactors_whitelist=["ZN"]` y hash
`{s['prepared_CON_sha256']}`. Preflight y pipeline usan
`_coerce_hotspots`, cuya implementación conserva sólo elementos `dict`:
la lista de cadenas se convierte en `[]`. La evaluación vuelve a preparar
el receptor sin Zn. Su hash es `{s['used_CON_sha256']}`, el de SIN.
La copia del receptor **utilizado**, los logs de Vina, los resultados
persistidos y los seis crudos CON confirman el mismo cambio.
Las funciones originales prueban también el descarte de `MG`, `CA` y `K`;
esto demuestra el mecanismo, no resultados de redocking en esas entradas.

| Evidencia del piloto | Cantidad |
|---|---:|
| SIN con resultado completo y receptor esperado | 5 semillas |
| Intentos solicitados CON que utilizaron SIN | 6, dos por semilla 42–44 |
| Terminales rechazados por el guardián de receptor | 3 de 8 (37,5 %) |
| Pares válidos en el piloto | 0 |
| Corridas confirmatorias | 0 de 380 previstas |
| Pares principales / controles al cierre | 0 / 0 |

El limitador detuvo y cerró la cápsula al superar 30 %. El error es una
invalidación del brazo por el producto; no prueba que Vina fallara ni que el
ion empeorara. Los terminales originales conservan la etiqueta genérica
`INFRASTRUCTURE_FAILURE` del guardián, junto con la causa exacta. No se
reclasifican como poses fallidas para inflar el resultado científico.
Antes hubo dos fallos de Vina por MAX_PATH y dos detenciones de montaje
sin evaluación: se conservan aparte y las correcciones del arnés están en
la bitácora. No se sobrescribió ningún crudo ni terminal.

Los cinco SIN del piloto dieron {rmsd_ok}/5 RMSD ≤2 Å, {valid}/5 top-1 válidos
y {joint}/5 ambos. Son datos del piloto, fuera del gate. Los seis intentos
CON no son seis semillas independientes ni un brazo con metal.
La prueba de signos no es aplicable con cero pares; el p=1 del JSON es la
convención del algoritmo para cero discordancias, no una inferencia.
El piloto pareado quedó incompleto y no permite estimar el tiempo total.

## El límite de PoseBusters y del diagnóstico

El reconocimiento usó coordenadas del cristal, nunca poses acopladas.
Meeko escribe los iones como `ATOM`; PoseBusters los excluye de la máscara
inorgánica por considerarlos proteína y de la máscara de proteína por su
elemento. Los 52 átomos metálicos cargados quedaron fuera de ambas máscaras:
46 pertenecían a la población y seis eran iones adicionales conservados por
código de residuo. Un PASA no valida su coordinación.
[API de PoseBusters](https://posebusters.readthedocs.io/en/latest/api.html).

Las seis formas diagnósticas representables para Zn se fijaron con reglas
químicas independientes y se contrastaron en dos procesos. No se ejecutaron.
El pH usado para expresarlas no estima su población de unión. Tampoco se
pudo medir la frecuencia de His con H en el nitrógeno coordinante durante
corridas CON reales, porque ningún receptor CON se acopló.

## Qué no dice y qué queda

No hay un NO_GO científico contra conservar el ion, una demostración de
equivalencia ni una recomendación de whitelist por receptor. El redocking
previsto usa el propio cristal: aun completo no demostraría cross-docking,
afinidad, actividad, energía de coordinación, calibración ni readiness FEP.
Las entradas comparten familias proteicas; no equivalen a 35 dianas
independientes. Vina tampoco añade por conservar un ion los parámetros y
pseudoátomos del protocolo AutoDock4Zn.
[Documentación de AutoDock](https://autodock-vina.readthedocs.io/en/latest/docking_zinc.html).

Se conservan el prerregistro y toda la evidencia producida. El catálogo,
M5 y el producto siguen en f0e64086. La confirmación no se lanzó, por lo que
no hubo intervalo confirmatorio con ediciones. Los sellos usan rutas del
repositorio y los archivos científicos están versionados. La única
desviación de alcance fue un temporal propio creado fuera de scripts/docs
durante la primera inspección de PoseBusters, retirado después; consta en
la bitácora. El runtime no viaja por git y sus hashes sí.
'''
    table=['| Entrada | Metal | Coordina | Preparación SIN / CON | SIN x/5 | CON x/5 | PoseBusters de docking | His CON | Recomendación |',
           '|---|---|---|---|---|---|---|---|---|']
    reasons=[]
    for e in p['entries']:
        state=lambda arm:'sí' if e['recognition'][arm].get('sha256') else 'no'
        rec='Abstenerse: exclusión previa' if e['exclusion'] else 'Abstenerse: comparación detenida'
        table.append(f"| {e['pdb_id']} | {', '.join(sorted({i['metal'] for i in e['ions']}))} | {'sí' if e['principal'] else 'control'} | {state('SIN')} / {state('CON')} | — | — | no medido | no medido | {rec} |")
        if e['exclusion']: reasons.append(f"- **{e['pdb_id']}**: "+'; '.join(e['exclusion']))
    audit=f'''# MET-01: metales con y sin ion — 2026-10-11

**INCONCLUSIVE: el producto pierde la whitelist al evaluar.** Se abstiene de
cambiar el catálogo. La medición confirmatoria no se inició; el experimento
queda cerrado y una repetición requiere MET-01-R1, después del arreglo.

Producto `{m.PRODUCT}`, prerregistro `{reg}`, Python 3.11.9, Vina 1.2.7,
Meeko 0.7.1, PoseBusters 0.6.5 `dock` con MF-33-H-COR. Parámetros 8/9/1,
CPU=4, semillas 42–46. El gate CAL exige ≥3 RMSD ≤2 Å y validez de todos
los top-1 cuyo RMSD cumple. La tabla describe **confirmación**: un guion
significa no medido, nunca cero de reproducción ni pose fallida.

{chr(10).join(table)}

## Exclusiones fijadas antes de Vina

{chr(10).join(reasons)}

Quedaban 28 principales y cuatro controles. Los errores de referencia son
límites del método CAL, no prueba de que el depósito sea erróneo. En 8UBR
SIN cambia por los ATP adicionales al omitirse `site_ligand`; no se arregló.
Los fallos deterministas de preparación se distinguen de infraestructura.

## Piloto y decisión

1BN1 tuvo cinco SIN válidos como corridas: RMSD ≤2 Å {rmsd_ok}/5,
PoseBusters passed {valid}/5 y ambos {joint}/5. Son datos fuera del gate.
Seis intentos CON, semillas 42–44 dos veces cada una, utilizaron el receptor
SIN: la variante tenía `['ZN']`, preflight y ejecución `[]`. El hash usado
coincide con SIN, y su snapshot no contiene metal. Se conservan todos los
crudos y logs de Vina en `_work/pilot` y `piloto/`; las distancias de esos
intentos sólo se refieren al lugar del ion del cristal, no a un ion conservado.

El guardián rechazó 3/8 terminales (37,5 %) y cerró la cápsula. El fallo del
brazo se observa en 1BN1. Las funciones originales descartan cualquier
cadena de Zn/Mg/Ca/K; no se ejecutaron otras entradas para fingir un pareado.
La frecuencia de advertencias de His en CON y el brazo diagnóstico quedan
sin medir. Cero pares principales y cero controles medidos: no hay prueba
de signos aplicable ni una lista de receptores beneficiados.

Potencia condicional preregistrada para 40 puntos y q=0,5: 94,76 % con 35,
82,02 % con 25 y {100*s['conditional_power_at_planned_n']:.2f} % con 28. Mínimo significativo 6:0,
p=0,03125; no confundir con potencia. Se había fijado un mínimo de cuatro
controles evaluables sin pérdidas, porque dos estaban excluidos; no llegó
a comprobarse. El gate no se cambió después de las poses.

## Reproducción y alcance

`python scripts/medir_met01.py selftest` verifica los controles exigidos.
`merge`, `analyze` y `verify` reconstruyen la confirmación vacía sin usar
el piloto. `python scripts/artifacts_science/MET-01-ION-DEL-SITIO/source/pilot_stop.py`
reconstruye los once intentos desde sus crudos, snapshots y logs versionados;
verifica top-1 SDF/PDBQT, RMSD, microestados, hashes y el descarte de la
whitelist con las dos funciones originales. Funciona sin cápsula ni token.
`python scripts/validar_sellos.py --check` comprueba los sellos; el runtime
no se distribuye por git, declarado en `sellos_no_distribuidos.json`.
El productor realmente ejecutado se conserva en `source/executed/`.

El reconocimiento demuestra que los 52 átomos metálicos cargados quedaron
fuera de ambas máscaras de PoseBusters: PASA no valida coordinación. Son
46 iones de la población y seis adicionales retenidos por código. La
geometría no es energía y SIN/CON no admitirían comparar scores como
afinidades. No se midió efecto del ion ni se validó M5, FEP o cross-docking.
'''
    for name, dest, text in [('paper.md','docs/papers/MET-01-ION-DEL-SITIO.md',paper),
                             ('audit.md','docs/auditorias/metales-con-y-sin-ion-2026-10-11.md',audit)]:
        for path in [ROOT/dest,EXP/'publicacion'/name]:
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(text,encoding='utf-8',newline='\n')
    print('Stopped-pilot paper and 41-entry audit written')


if __name__ == '__main__':
    produce()
