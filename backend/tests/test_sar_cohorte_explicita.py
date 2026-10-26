"""
CAS-02: SAR sobre una cohorte explícita de corridas, no sobre la proyección más
reciente de cada molécula.

El hallazgo (auditoría DevOps SOL, caso de 40 corridas): 20 moléculas se evaluaron
como únicas (K=1) y luego se reevaluaron en ensemble (K=30). La tabla SAR de la
primera corrida única tomaba a los análogos de `evaluation_results`, la
proyección MÁS RECIENTE de cada molécula, que ya era ensemble: K distinto, la API
se abstenía (correctamente) de restar y quedaban **0 comparables entre 20
filas**. No era pérdida del snapshot ni un delta indebido: era una limitación de
selección de cohorte.

Lo que se fija:

1. por defecto nada cambia (proyección más reciente);
2. con `task_id` la base es lo que ESA corrida produjo, y con `cohort_task_ids`
   los análogos son los de las corridas pedidas, leídas de sus snapshots
   inmutables: la cohorte histórica se reconstruye aunque las moléculas se
   hayan reevaluado después;
3. la abstención sigue gobernando el delta: una cohorte explícita no vuelve
   comparable lo que no lo es;
4. una cohorte pedida se cumple entera o se rechaza nombrando la corrida —ajena,
   desconocida, fallida, de otro receptor, o demasiado grande—, nunca se
   sustituye en silencio por otra;
5. la respuesta declara de dónde salió la tabla.
"""

from __future__ import annotations

import uuid

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import core.database as db_mod
from api.dependencies import get_current_user_optional
from api.routers.sar import MAX_COHORTE_EXPLICITA, router as sar_router
from core.database import get_db
from core.models import (
    Base,
    EvaluationResultORM,
    EvaluationRunORM,
    MoleculeORM,
    TargetORM,
    UserORM,
)
from db.repository import Repository

RECEPTOR = "8b94" + "a" * 60
CAJA = {"box_center": [43.21, 2.19, 46.19], "box_size": [25.4, 25.4, 25.4]}
SMILES = ["CCO", "CCN", "CCC", "CCCl"]


def _protocolo(k: int) -> dict:
    return {
        "engine": "vina",
        "exhaustiveness": 8,
        "num_poses": 9,
        "conformers_generated": k,
        "execution_provenance": dict(CAJA),
    }


def _estado() -> dict:
    return {
        "protonacion": {"aplicada": True, "motor": "dimorphite-dl", "ph": 7.4},
        "tautomeria": {"aplicada": True, "modo": "canonico"},
        "smiles_acoplado": "CCO",
        "carga_formal_neta": 0,
    }


def _rellenar(resultado: EvaluationResultORM, *, k: int, afinidad: float) -> None:
    resultado.affinity_kcal = afinidad
    resultado.total_score = 60.0 + afinidad
    resultado.docking_protocol = _protocolo(k)
    resultado.ligand_state = _estado()
    resultado.vina_version = "1.2.7"
    resultado.vina_random_seed = 42
    resultado.receptor_sha256 = RECEPTOR


class _Entorno:
    def __init__(self, ruta):
        self.ruta = ruta
        self.engine = None
        self.factory = None
        self.usuario: UserORM | None = None
        self.ajeno: UserORM | None = None
        self.moleculas: list[uuid.UUID] = []
        self.otra_molecula: uuid.UUID | None = None

    async def arrancar(self):
        self.engine = create_async_engine(f"sqlite+aiosqlite:///{self.ruta}")
        self.factory = async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def apagar(self):
        if self.engine is not None:
            await self.engine.dispose()
        self.engine = None

    async def sembrar(self):
        """Tres moléculas: únicas (K=1) con snapshot, luego reevaluadas en ensemble."""
        async with self.factory() as s:
            self.usuario = UserORM(id=uuid.uuid4(), email="a@b.c", username="ana", hashed_password="x", is_active=True)
            self.ajeno = UserORM(id=uuid.uuid4(), email="o@b.c", username="otro", hashed_password="x", is_active=True)
            receptor = TargetORM(
                id=uuid.uuid4(), pdb_id="3F75", name="COX-2", chain="A",
                grid_center_x=1.0, grid_center_y=2.0, grid_center_z=3.0,
                grid_size_x=20.0, grid_size_y=20.0, grid_size_z=20.0,
            )
            otro_receptor = TargetORM(
                id=uuid.uuid4(), pdb_id="7E2Y", name="5-HT1A", chain="A",
                grid_center_x=1.0, grid_center_y=2.0, grid_center_z=3.0,
                grid_size_x=20.0, grid_size_y=20.0, grid_size_z=20.0,
            )
            s.add_all([self.usuario, self.ajeno, receptor, otro_receptor])
            await s.flush()
            for i in range(3):
                mol = MoleculeORM(
                    id=uuid.uuid4(), smiles=SMILES[i], name=f"M{i}", smiles_hash=f"{i}" * 64,
                    user_id=self.usuario.id, target_id=receptor.id,
                )
                s.add(mol)
                self.moleculas.append(mol.id)
            ajena = MoleculeORM(
                id=uuid.uuid4(), smiles="CCCl", name="ajena", smiles_hash="9" * 64,
                user_id=self.ajeno.id, target_id=receptor.id,
            )
            en_otro = MoleculeORM(
                id=uuid.uuid4(), smiles="CCBr", name="otro-receptor", smiles_hash="8" * 64,
                user_id=self.usuario.id, target_id=otro_receptor.id,
            )
            s.add_all([ajena, en_otro])
            await s.commit()
            self.otra_molecula = ajena.id
            self.molecula_otro_receptor = en_otro.id

        # Fase 1: corridas únicas, congeladas.
        async with self.factory() as s:
            repo = Repository(s)
            for i, mid in enumerate(self.moleculas):
                resultado = EvaluationResultORM(molecule_id=mid)
                _rellenar(resultado, k=1, afinidad=-5.0 - i)
                s.add(resultado)
                await s.flush()
                await repo.snapshot_evaluation_run(mid, f"unica-{i}")
            # Una corrida de un tercero y otra de un receptor distinto.
            for mid, tarea in ((self.otra_molecula, "ajena-0"), (self.molecula_otro_receptor, "otro-receptor-0")):
                resultado = EvaluationResultORM(molecule_id=mid)
                _rellenar(resultado, k=1, afinidad=-6.0)
                s.add(resultado)
                await s.flush()
                await repo.snapshot_evaluation_run(mid, tarea)
            await s.commit()

        # Fase 2: las mismas tres moléculas, reevaluadas en ensemble. La
        # proyección cambia; los snapshots de la fase 1 no.
        async with self.factory() as s:
            repo = Repository(s)
            for i, mid in enumerate(self.moleculas):
                resultado = await repo.get_evaluation_result(mid)
                _rellenar(resultado, k=30, afinidad=-8.0 - i)
                await s.flush()
                await repo.snapshot_evaluation_run(mid, f"ensemble-{i}")
            await s.commit()

        # Una corrida fallida: existe en el libro pero no produjo evaluación.
        async with self.factory() as s:
            corrida = await Repository(s).get_evaluation_run("unica-1")
            fallida = EvaluationRunORM(
                task_id="fallida-0", molecule_id=corrida.molecule_id,
                snapshot_json=dict(corrida.snapshot_json), status="FAILURE",
            )
            s.add(fallida)
            await s.commit()

    def cliente(self, usuario: UserORM | None = None) -> httpx.AsyncClient:
        yo = usuario or self.usuario

        async def db_override():
            async with self.factory() as session:
                yield session

        async def usuario_override():
            return yo

        app = FastAPI()
        app.include_router(sar_router)
        app.dependency_overrides[get_db] = db_override
        app.dependency_overrides[get_current_user_optional] = usuario_override
        return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost")


@pytest_asyncio.fixture
async def entorno(tmp_path):
    await db_mod.reset_engine()
    env = _Entorno(tmp_path / "sar.db")
    await env.arrancar()
    await env.sembrar()
    try:
        yield env
    finally:
        await env.apagar()
        await db_mod.reset_engine()


def _filas(respuesta) -> dict[str, dict]:
    """Filas por task_id, para no depender del orden."""
    return {f["task_id"]: f for f in respuesta.json()["results"]}


# ── 1. Por defecto, nada cambia ──────────────────────────────────────


@pytest.mark.asyncio
async def test_sin_parametros_la_tabla_es_la_proyeccion_mas_reciente(entorno):
    async with entorno.cliente() as c:
        r = await c.get(f"/sar/{entorno.moleculas[0]}")
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["cohort"] == {"source": "latest_projection", "base_task_id": None, "task_ids": None}
    # La proyección ya es ensemble (K=30): -8.0 de la molécula 0, no -5.0.
    base = next(f for f in cuerpo["results"] if f["is_base"])
    assert base["affinity_kcal"] == -8.0


# ── 2. La reproducción de la auditoría ───────────────────────────────


@pytest.mark.asyncio
async def test_base_unica_contra_proyeccion_ensemble_no_tiene_comparables(entorno):
    """El defecto: base = corrida única, análogos = proyecciones (ahora ensemble).

    K distinto en TODAS las filas → la API se abstiene en todas. Es la
    «0 comparables» de la auditoría, ahora reproducida en el contrato.
    """
    async with entorno.cliente() as c:
        r = await c.get(f"/sar/{entorno.moleculas[0]}", params={"task_id": "unica-0"})
    assert r.status_code == 200, r.text
    otros = [f for f in r.json()["results"] if not f["is_base"]]
    assert otros, "sin análogos la prueba no mide nada"
    assert all(f["comparison_state"] == "abstained" for f in otros)
    assert all(f["delta_affinity"] is None for f in otros)


@pytest.mark.asyncio
async def test_la_cohorte_explicita_reconstruye_las_corridas_unicas(entorno):
    """La corrección: las tres corridas únicas, leídas de sus snapshots."""
    cohorte = ["unica-0", "unica-1", "unica-2"]
    async with entorno.cliente() as c:
        r = await c.get(
            f"/sar/{entorno.moleculas[0]}", params={"task_id": "unica-0", "cohort_task_ids": cohorte}
        )
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["cohort"] == {"source": "explicit_runs", "base_task_id": "unica-0", "task_ids": cohorte}
    filas = _filas(r)
    assert set(filas) == set(cohorte)
    # Las afinidades son las de las corridas ÚNICAS (-5, -6, -7), no las del
    # ensemble que ahora vive en la proyección (-8, -9, -10).
    assert [filas[t]["affinity_kcal"] for t in cohorte] == [-5.0, -6.0, -7.0]
    # Y como comparten protocolo y condición, SÍ se compara: hay deltas.
    assert filas["unica-0"]["is_base"] is True
    for tarea, delta in (("unica-1", -1.0), ("unica-2", -2.0)):
        assert filas[tarea]["comparison_state"] == "descriptive"
        assert filas[tarea]["delta_affinity"] == delta
    assert sum(1 for f in filas.values() if f["is_base"]) == 1


@pytest.mark.asyncio
async def test_la_cohorte_de_ensembles_tambien_se_reconstruye_por_separado(entorno):
    cohorte = ["ensemble-0", "ensemble-1", "ensemble-2"]
    async with entorno.cliente() as c:
        r = await c.get(
            f"/sar/{entorno.moleculas[0]}", params={"task_id": "ensemble-0", "cohort_task_ids": cohorte}
        )
    filas = _filas(r)
    assert [filas[t]["affinity_kcal"] for t in cohorte] == [-8.0, -9.0, -10.0]
    assert filas["ensemble-1"]["delta_affinity"] == -1.0


# ── 3. La abstención sigue gobernando ────────────────────────────────


@pytest.mark.asyncio
async def test_una_cohorte_mixta_no_vuelve_comparable_lo_que_no_lo_es(entorno):
    cohorte = ["unica-0", "unica-1", "ensemble-2"]
    async with entorno.cliente() as c:
        r = await c.get(
            f"/sar/{entorno.moleculas[0]}", params={"task_id": "unica-0", "cohort_task_ids": cohorte}
        )
    filas = _filas(r)
    assert filas["unica-1"]["comparison_state"] == "descriptive"
    mezclada = filas["ensemble-2"]
    assert mezclada["comparison_state"] == "abstained"
    assert mezclada["delta_affinity"] is None
    assert mezclada["affinity_kcal"] == -10.0  # la cruda sigue visible
    assert "confórmeros" in mezclada["comparison_reason"] or "conformeros" in mezclada["comparison_reason"].lower()


# ── 4. Una cohorte pedida se cumple entera o se rechaza ──────────────


@pytest.mark.asyncio
async def test_una_corrida_desconocida_se_rechaza_nombrandola(entorno):
    async with entorno.cliente() as c:
        r = await c.get(
            f"/sar/{entorno.moleculas[0]}",
            params={"task_id": "unica-0", "cohort_task_ids": ["unica-0", "no-existe-9"]},
        )
    assert r.status_code == 404
    assert "no-existe-9" in r.json()["detail"]


@pytest.mark.asyncio
async def test_una_corrida_fallida_no_entra_y_se_nombra(entorno):
    async with entorno.cliente() as c:
        r = await c.get(
            f"/sar/{entorno.moleculas[0]}",
            params={"task_id": "unica-0", "cohort_task_ids": ["unica-0", "fallida-0"]},
        )
    assert r.status_code == 409
    assert "fallida-0" in r.json()["detail"]
    assert "FAILURE" in r.json()["detail"]


@pytest.mark.asyncio
async def test_la_corrida_de_otra_cuenta_no_se_lee(entorno):
    async with entorno.cliente() as c:
        r = await c.get(
            f"/sar/{entorno.moleculas[0]}",
            params={"task_id": "unica-0", "cohort_task_ids": ["unica-0", "ajena-0"]},
        )
    assert r.status_code == 403
    assert "ajena-0" in r.json()["detail"]


@pytest.mark.asyncio
async def test_una_corrida_de_otro_receptor_no_entra_en_la_misma_tabla(entorno):
    async with entorno.cliente() as c:
        r = await c.get(
            f"/sar/{entorno.moleculas[0]}",
            params={"task_id": "unica-0", "cohort_task_ids": ["unica-0", "otro-receptor-0"]},
        )
    assert r.status_code == 409
    detalle = r.json()["detail"]
    assert "otro-receptor-0" in detalle and "7E2Y" in detalle and "3F75" in detalle


@pytest.mark.asyncio
async def test_la_base_pedida_debe_ser_de_esa_molecula(entorno):
    """`task_id` de la molécula 1 con la molécula 0 en la ruta: no se sustituye."""
    async with entorno.cliente() as c:
        r = await c.get(f"/sar/{entorno.moleculas[0]}", params={"task_id": "unica-1"})
    assert r.status_code == 404
    assert "unica-1" in r.json()["detail"]


@pytest.mark.asyncio
async def test_una_cohorte_demasiado_grande_se_rechaza(entorno):
    cohorte = [f"corrida-{i}" for i in range(MAX_COHORTE_EXPLICITA + 1)]
    async with entorno.cliente() as c:
        r = await c.get(f"/sar/{entorno.moleculas[0]}", params={"cohort_task_ids": cohorte})
    assert r.status_code == 422
    assert str(MAX_COHORTE_EXPLICITA) in r.json()["detail"]


@pytest.mark.asyncio
async def test_los_duplicados_de_la_cohorte_no_duplican_filas(entorno):
    async with entorno.cliente() as c:
        r = await c.get(
            f"/sar/{entorno.moleculas[0]}",
            params={"task_id": "unica-0", "cohort_task_ids": ["unica-0", "unica-1", "unica-1"]},
        )
    assert len(r.json()["results"]) == 2
    assert r.json()["cohort"]["task_ids"] == ["unica-0", "unica-1"]
