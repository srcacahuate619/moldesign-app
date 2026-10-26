"""QA2-010: las corridas mantienen su identidad y sus cifras congeladas."""
import uuid
from datetime import datetime, timezone
import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from core.models import Base, UserORM, TargetORM, MoleculeORM, MoleculeStatus, EvaluationResultORM, EvaluationRunORM
from core.database import get_db
from api.dependencies import get_current_user
from api.routers import history

@pytest_asyncio.fixture
async def client(tmp_path):
    engine=create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'history.db'}")
    factory=async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn: await conn.run_sync(Base.metadata.create_all)
    owner=UserORM(id=uuid.uuid4(),email='qa2@local',username='qa2',hashed_password='x')
    other=UserORM(id=uuid.uuid4(),email='other@local',username='other',hashed_password='x')
    target=TargetORM(id=uuid.uuid4(),pdb_id='1HSG',name='HIV protease',grid_center_x=0,grid_center_y=0,grid_center_z=0)
    mol=MoleculeORM(id=uuid.uuid4(),user_id=owner.id,target_id=target.id,smiles='CCO',smiles_hash='abc',status=MoleculeStatus.EVALUATED)
    foreign=MoleculeORM(id=uuid.uuid4(),user_id=other.id,target_id=target.id,smiles='CCN',smiles_hash='def',status=MoleculeStatus.EVALUATED)
    legacy=MoleculeORM(id=uuid.uuid4(),user_id=owner.id,target_id=target.id,smiles='CCC',smiles_hash='ghi',status=MoleculeStatus.EVALUATED)
    async with factory() as db:
        db.add_all([owner,other,target,mol,foreign,legacy]);await db.flush()
        db.add(EvaluationResultORM(molecule_id=mol.id,task_id='run-new',affinity_kcal=-9.5,total_score=99,molecular_weight=300))
        db.add(EvaluationResultORM(molecule_id=legacy.id,task_id=None,affinity_kcal=-5,total_score=20))
        for molecule,task,affinity,when,status in [(mol,'run-old',-6.1,1,'SUCCESS'),(mol,'run-new',-8.2,2,'SUCCESS'),(foreign,'private-run',-99,3,'SUCCESS'),(mol,'run-failed',None,4,'FAILURE')]:
            db.add(EvaluationRunORM(molecule_id=molecule.id,task_id=task,status=status,created_at=datetime(2026,10,when,tzinfo=timezone.utc),snapshot_json={'blockchain_tx_id':'old-receipt' if task=='run-old' else None,'affinity_kcal':affinity,'task_id':task,'molecular_weight':100+when,'total_score':when*10,'evaluated_at':f'2026-10-0{when}T10:00:00+00:00'}))
        db.add(EvaluationRunORM(molecule_id=mol.id,task_id='projection-archive:old-copy',status='SUCCESS',snapshot_json={'task_id':'run-old','affinity_kcal':-6.1}))
        await db.commit()
    async def database():
        async with factory() as db: yield db
    app=FastAPI();app.include_router(history.router);app.dependency_overrides[get_db]=database;app.dependency_overrides[get_current_user]=lambda:owner
    async with AsyncClient(transport=ASGITransport(app=app),base_url='http://test') as c:
        c.fixture_factory=factory
        c.legacy_id=legacy.id
        yield c
    await engine.dispose()

@pytest.mark.asyncio
async def test_cada_corrida_tiene_snapshot_propio_sin_duplicar_la_proyeccion(client):
    data=(await client.get('/history/evaluations')).json()
    assert data['total']==4
    rows={r['task_id']:r for r in data['items']}
    assert set(rows)=={'run-old','run-new','run-failed',None}
    assert rows['run-old']['affinity_kcal']==-6.1
    assert rows['run-new']['affinity_kcal']==-8.2
    assert rows['run-old']['molecular_weight']==101
    assert rows['run-failed']['status']=='failed' and rows['run-failed']['affinity_kcal'] is None
    assert rows[None]['affinity_kcal']==-5

@pytest.mark.asyncio
async def test_conteos_por_corrida_y_legacy_pertenecen_a_la_misma_cuenta(client):
    data=(await client.get('/history/stats')).json()
    assert (data['total_evaluations'],data['completed_evaluations'],data['failed_evaluations'],data['unique_targets'])==(4,3,1,1)

@pytest.mark.asyncio
async def test_filtros_y_paginacion_usan_la_cifra_de_cada_corrida(client):
    data=(await client.get('/history/evaluations',params={'sort_by':'affinity_kcal','sort_order':'asc','page_size':1})).json()
    assert data['total']==4 and data['has_next'] is True
    assert data['items'][0]['task_id']=='run-new' and data['items'][0]['affinity_kcal']==-8.2
    second=(await client.get('/history/evaluations',params={'sort_by':'affinity_kcal','sort_order':'asc','page_size':1,'page':2})).json()
    assert second['items'][0]['task_id']=='run-old'
    filtered=(await client.get('/history/evaluations',params={'min_affinity':-7})).json()
    assert filtered['total']==1 and filtered['items'][0]['task_id']=='run-new'
    failed=(await client.get('/history/evaluations',params={'status':'failed'})).json()
    assert failed['total']==1 and failed['items'][0]['task_id']=='run-failed'

@pytest.mark.asyncio
async def test_recibo_usa_el_snapshot_de_la_corrida_solicitada(client, monkeypatch):
    captured={}
    def render(mol, snapshot):
        captured.update(snapshot)
        return b'%PDF-QA2-immutable'
    monkeypatch.setattr(history, 'render_history_receipt', render, raising=False)
    response=await client.get('/history/receipts/run-old')
    assert response.status_code==200
    assert captured['task_id']=='run-old' and captured['affinity_kcal']==-6.1
    assert captured['blockchain_tx_id']=='old-receipt'
    assert (await client.get('/history/receipts/private-run')).status_code==404
    assert (await client.get('/history/receipts/run-new')).status_code==409


@pytest.mark.asyncio
async def test_archivo_unico_retiene_la_identidad_original(client, monkeypatch):
    from sqlalchemy import delete
    async with client.fixture_factory() as db:
        await db.execute(delete(EvaluationRunORM).where(EvaluationRunORM.task_id=='run-old'))
        await db.commit()
    rows=(await client.get('/history/evaluations')).json()
    assert rows['total']==4
    old=next(item for item in rows['items'] if item['task_id']=='run-old')
    assert old['affinity_kcal']==-6.1

@pytest.mark.asyncio
async def test_recibo_heredado_exige_el_task_id_aun_conservado(client, monkeypatch):
    from sqlalchemy import update
    async with client.fixture_factory() as db:
        await db.execute(update(EvaluationResultORM).where(EvaluationResultORM.molecule_id==client.legacy_id).values(task_id='legacy-run',blockchain_tx_id='legacy-receipt'))
        await db.commit()
    monkeypatch.setattr(history,'render_history_receipt',lambda mol,snapshot:b'%PDF-legacy')
    assert (await client.get('/history/receipts/legacy-run')).status_code==200
    async with client.fixture_factory() as db:
        await db.execute(update(EvaluationResultORM).where(EvaluationResultORM.molecule_id==client.legacy_id).values(task_id='replacement'))
        await db.commit()
    assert (await client.get('/history/receipts/legacy-run')).status_code==404

@pytest.mark.asyncio
async def test_recibo_renderiza_un_pdf_con_datos_del_snapshot(client):
    import base64
    response=await client.get('/history/receipts/run-old')
    assert response.status_code==200
    assert base64.b64decode(response.json()['pdf_base64']).startswith(b'%PDF-')

@pytest.mark.asyncio
@pytest.mark.parametrize('locale,reason,expected', [
    ('es-MX','Corrida no encontrada','Corrida no encontrada'),
    ('en-US','Corrida no encontrada','Run not found'),
    ('es-MX','Esta corrida no conserva un recibo','Esta corrida no conserva un recibo'),
    ('en-US','Esta corrida no conserva un recibo','This run has no saved receipt'),
])
async def test_error_del_recibo_en_el_idioma_de_la_sesion(locale,reason,expected):
    import json
    from core import i18n
    from starlette.responses import StreamingResponse
    token=i18n.set_request_locale(locale)
    try:
        response=await i18n.localize_json_response(StreamingResponse(iter([json.dumps({'detail':reason}).encode()]),media_type='application/json'))
        body=b''.join([chunk async for chunk in response.body_iterator])
    finally:
        i18n.reset_request_locale(token)
    assert json.loads(body)['detail']==expected
