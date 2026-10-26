"""QA local de Molcy: base aislada, evaluación Vina real y API; sin build.

La sesión QA sólo existe en memoria. No escribirla en informes ni capturas.
Para repetir: iniciar este servidor y Next dev en 3001 con API 8037;
si falta la instalación QA, solicitar Blender y Molecular Nodes desde Molcy
antes de ejecutar qa_molcy_maduracion.cjs. No usar contra datos de usuario.
"""
import asyncio
import json
import os
import secrets
import sys
import uuid
from pathlib import Path

ROOT = Path(r"D:\moldesign-build\dist\molcy-maduracion-20260929")
ROOT.mkdir(parents=True, exist_ok=True)
(ROOT / "instalacion-prueba").mkdir(exist_ok=True)
os.environ.update(LOCAL_DATA_DIR=str(ROOT / "datos"), SECRET_KEY=secrets.token_hex(32),
    MOLDESIGN_INSTALL_DIR=str(ROOT / "instalacion-prueba"),
    VINA_EXECUTABLE_PATH=r"D:\moldesign-build\tools\vina\vina.exe",
    MOLDESIGN_OPENBABEL_DIR=r"D:\moldesign-build\tools\openbabel", ENVIRONMENT="testing")
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))
sys.path.insert(1, str(REPO))
from core.models import Base, UserORM, TargetORM, MoleculeORM, EvaluationRunORM
from core.database import get_engine, get_session_factory
from api.routers import molcy, evaluation
from api.auth import create_access_token
from services.molcy import installation
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient
from sqlalchemy import select

USER = uuid.uuid4()
TARGET = uuid.uuid4()
SOURCE = Path(r"D:\moldesign-build\dist\molcy-cpu-gpu-qa-20260928\scenes\1AJ6")
scene = json.loads((SOURCE / "scene.json").read_text(encoding="utf-8"))
center = scene["encuadre"]["objetivo"]
box = scene["encuadre"]["caja"]
raw = ROOT / "datos" / "targets" / "1AJ6" / "raw.pdb"
raw.parent.mkdir(parents=True, exist_ok=True)
raw.write_bytes((SOURCE / "geometry" / "deposited.pdb").read_bytes())

async def seed():
    async with get_engine().begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with get_session_factory()() as db:
        target = await db.scalar(select(TargetORM).where(TargetORM.pdb_id == "1AJ6"))
        if target is None:
            target = TargetORM(id=TARGET,pdb_id="1AJ6",name="1AJ6 — receptor QA",chain="A",
                grid_center_x=center[0],grid_center_y=center[1],grid_center_z=center[2],
                grid_size_x=box[0],grid_size_y=box[1],grid_size_z=box[2])
            db.add(target)
        db.add(UserORM(id=USER,email=f"qa-{USER}@example.test",username=f"qa_{USER.hex[:12]}",is_active=True))
        await db.commit()

asyncio.run(seed())
installation.configure("administrado",None,r"E:\proyect3d-worktrees\molcy")
app=FastAPI()
app.state.limiter=evaluation.limiter
app.add_middleware(CORSMiddleware,allow_origins=["http://localhost:3001","http://127.0.0.1:3001"],
                   allow_methods=["*"],allow_headers=["*"],expose_headers=["Content-Disposition","Content-Range"])
app.include_router(molcy.router)
app.include_router(evaluation.router)
TOKEN=create_access_token(str(USER))
HEADERS={"Authorization":"Bearer "+TOKEN}

with TestClient(app) as client:
    response=client.post("/evaluation/evaluate",headers=HEADERS,json={
        "smiles":"CC(=O)Oc1ccccc1C(=O)O", "target_pdb_id":"1AJ6", "molecule_name":"Aspirina — QA Molcy",
        "grid_center":center,"grid_size":box,
        "pipeline_config":{"enabled_stages":["validation","properties","sa_filter","conformer","docking"],
                           "stage_params":{"docking":{"exhaustiveness":1,"num_poses":1,"seed":42},
                                           "conformer":{"conformers":1}}}})
    # Sólo datos de evaluación; nunca la sesión o el token.
    (ROOT / "evaluacion-qa.sse").write_text(response.text,encoding="utf-8")
    print("Evaluación QA HTTP",response.status_code,flush=True)
    if response.status_code != 200 or '"type": "done"' not in response.text:
        print(response.text[-1200:],flush=True)
        raise SystemExit(1)

async def save():
    async with get_session_factory()() as db:
        rows=(await db.execute(select(MoleculeORM).where(MoleculeORM.user_id==USER))).scalars().all()
        for molecule in rows: molecule.is_saved=True
        await db.commit()
        run=await db.scalar(select(EvaluationRunORM).where(EvaluationRunORM.molecule_id==rows[0].id))
        return str(rows[0].id),run.task_id
MOLECULE,TASK=asyncio.run(save())

@app.get("/qa/sesion",include_in_schema=False)
def session():
    return {"token":TOKEN,"user":{"user_id":str(USER),"username":"QA Molcy","email":"qa@example.test"},
            "molecule":MOLECULE,"task_id":TASK}

if __name__ == "__main__":
    import uvicorn
    print("API QA preparada; datos y SQLite aislados. Puerto 8037.",flush=True)
    uvicorn.run(app,host="127.0.0.1",port=8037,log_level="warning",access_log=False)
