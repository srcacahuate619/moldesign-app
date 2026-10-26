"""La anti-diana predeterminada conserva un esqueleto continuo en su caja medida."""
import gzip
import json
from pathlib import Path
import pytest
from services.docking.selectivity import ANTI_TARGET_PANEL
from services.docking.preparer import huecos_del_esqueleto
ROOT = Path(__file__).resolve().parents[2]

def serotonin():
    return next(row for row in ANTI_TARGET_PANEL if 'HTR2B' in row['name'])

def test_se_sustituye_4nc3_por_la_candidata_medida():
    assert serotonin()['pdb_id'] == '7SRQ'

def test_caja_y_cadenas_del_nuevo_sitio_son_las_del_ligando():
    row = serotonin()
    assert tuple(row['center']) == (152.587, 158.245, 155.595)
    assert tuple(row['size']) == (18.0, 18.0, 18.0)
    cat = next(r for r in json.loads((ROOT/'curated_targets.json').read_text(encoding='utf-8')) if r['pdb_id']==row['pdb_id'])
    assert cat['chain'] == 'R' and cat['site_chains'] == ['R'] and cat['site_ligand'] == '7LD'

def test_el_receptor_predeterminado_no_tiene_huecos_criticos():
    row=serotonin()
    cat = next(r for r in json.loads((ROOT/'curated_targets.json').read_text(encoding='utf-8')) if r['pdb_id']==row['pdb_id'])
    text=gzip.open(ROOT/'data/targets'/f"{row['pdb_id']}.pdb.gz",'rt').read()
    filtered='\n'.join(l for l in text.splitlines() if not l.startswith(('ATOM','HETATM')) or l[21:22] in cat['site_chains'])
    assert not any(g['site_critical'] for g in huecos_del_esqueleto(filtered,text,row['center'],row['size']))

@pytest.mark.asyncio
async def test_api_expone_la_medida_del_default_y_su_limitacion(monkeypatch):
    from api.routers import pro_features as api
    class Repo:
        def __init__(self, db): pass
        async def get_anti_targets(self): return []
    monkeypatch.setattr(api,'Repository',Repo)
    response=await api.list_anti_targets(current_user=None,db=None)
    row=next(r for r in response['anti_targets'] if 'HTR2B' in r['name'])
    assert row['estructura']['pdb_id']=='7SRQ'
    assert row['estructura']['pose_reproducida'] is True
    assert row['estructura']['resolucion_A']==2.7
    assert row['estructura']['distancia_centroides_A']==0.7
    assert row['por_defecto'] and row['disponible']
    assert row['estructura']['truncadas_en_sitio']==4

def test_generador_conserva_el_default_y_la_medida_nueva():
    import importlib.util
    spec=importlib.util.spec_from_file_location('build_bowes',ROOT/'scripts/build_bowes44_panel.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    row=next(r for r in module.construir()['dianas'] if r['assay']=='5-HT2B')
    assert row['pdb_id']=='7SRQ'
    assert row['redock']['rmsd_pose1_A']==1.81
