"""La tabla SAR automática elige por similitud ANTES de cortar (auditoría científica 1.0.4, S1-3.3).

La consulta anterior exigía `total_score`, ordenaba por estado del stacking e índice heredado y cortaba a 50 antes de
medir ninguna similitud. Un análogo antiguo y muy parecido, con índice bajo o sin índice, quedaba fuera aunque fuera
el más parecido a la referencia, y la vista —que sí ordena por similitud— sólo recibía lo que esa consulta había
dejado pasar.

Decisión del propietario (con Opinión 1 y Opinión 2 de acuerdo):

* candidatas = últimas evaluaciones del mismo dueño y receptor, SIN error registrado y con `affinity_kcal` finita; el
  índice no interviene;
* se mide el Tanimoto de TODAS, se ordena antes de redondear, se desempata por fecha y por id y después se corta a 50;
* la referencia sale de la corrida pedida (o de la última evaluación) y NO gasta plaza;
* el núcleo común máximo sólo se calcula para las filas que se devuelven.

El oráculo de estas pruebas recalcula la huella con RDKit y los parámetros documentados (Morgan r=2, 1024 bits), no con
las funciones del router: si alguien cambia el criterio de selección, esta prueba lo ve.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from rdkit import Chem, DataStructs
from rdkit.Chem import rdFingerprintGenerator
from sqlalchemy import update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import api.routers.sar as sar_mod
import core.database as db_mod
from api.dependencies import get_current_user_optional
from api.routers.sar import router as sar_router
from core.database import get_db
from core.models import Base, EvaluationResultORM, MoleculeORM, TargetORM, UserORM
from db.repository import Repository
from services.sar.seleccion import (
    LIMITE_COMPARACIONES,
    Candidata,
    clave_de_orden,
    seleccionar,
)

BASE = "CC(=O)Nc1ccc(O)cc1"
RECEPTOR_SHA = "8b94" + "a" * 60
CAJA = {"box_center": [43.21, 2.19, 46.19], "box_size": [25.4, 25.4, 25.4]}
SUSTITUYENTES = [
    "F", "Cl", "Br", "I", "C", "CC", "CCC", "OC", "OCC", "N", "C#N", "C(F)(F)F", "[N+](=O)[O-]", "S", "SC",
    "C(=O)O", "C(N)=O", "OC(C)=O", "CO", "CN", "C=C", "C#C", "OCC(C)C", "C(C)C", "NC",
]


#: Análogos con una similitud moderada a la base: por debajo del corte, pero con núcleo común.
MODERADOS = [
    ("mod-sulfonamida", "CS(=O)(=O)Nc1ccc(O)cc1"),
    ("mod-fluoro-orto", "CC(=O)Nc1ccc(O)cc1F"),
    ("mod-n-metil", "CC(=O)N(C)c1ccc(O)cc1"),
    ("mod-etilamida", "CCNC(=O)c1ccc(O)cc1"),
    ("mod-aminofenol", "Nc1ccc(O)cc1"),
    ("mod-fenol", "Oc1ccccc1"),
]


def _serie() -> list[tuple[str, str]]:
    """Los análogos distintos de la base, con el núcleo de acetanilida (o parte de él).

    Calculada con el oráculo de abajo, la 50.ª por similitud es `mod-sulfonamida` (0,4815) y la 51.ª, `anillo-22`
    (0,4688): el corte cae entre dos valores distintos y la prueba mide el corte, no un desempate. Por encima
    quedan 28 con más de 0,5 y 21 cadenas empatadas en 0,5 que entran completas (el desempate tiene su propia
    prueba). El tamaño de la cadena (n = 2 a 26) es lo que ajusta el empate.
    """
    cadenas = [(f"cadena-{n}", "C" * n + "C(=O)Nc1ccc(O)cc1") for n in range(2, 27)]
    anillo = [
        ("antiguo-sin-indice" if i == 4 else f"anillo-{i}", f"CC(=O)Nc1ccc({s})cc1")
        for i, s in enumerate(SUSTITUYENTES)
    ]
    return cadenas + anillo + MODERADOS


#: Nada que ver con la base, pero con el índice más alto: lo que la consulta anterior habría puesto primero.
SEUELOS = [
    ("seuelo-etanol", "CCO"),
    ("seuelo-decano", "CCCCCCCCCC"),
    ("seuelo-ciclohexano", "C1CCCCC1"),
    ("seuelo-glicol", "OCCO"),
]


def _tanimoto(a: str, b: str) -> float:
    """El oráculo: Morgan r=2, 1024 bits, sin redondear."""
    generador = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=1024)
    fa = generador.GetFingerprint(Chem.MolFromSmiles(a))
    fb = generador.GetFingerprint(Chem.MolFromSmiles(b))
    return float(DataStructs.TanimotoSimilarity(fa, fb))


def _protocolo(k: int = 1, exhaustividad: int = 8) -> dict:
    return {
        "engine": "vina",
        "exhaustiveness": exhaustividad,
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


class _Mundo:
    def __init__(self, ruta):
        self.ruta = ruta
        self.engine = None
        self.factory = None
        self.ana: UserORM | None = None
        self.otro: UserORM | None = None
        self.anonimo: UserORM | None = None
        self.receptor_id: uuid.UUID | None = None
        self.otro_receptor_id: uuid.UUID | None = None
        self.ids: dict[str, uuid.UUID] = {}

    async def arrancar(self):
        self.engine = create_async_engine(f"sqlite+aiosqlite:///{self.ruta}")
        self.factory = async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with self.factory() as s:
            self.anonimo = await Repository(s).get_or_create_test_user()
            self.ana = UserORM(id=uuid.uuid4(), email="a@b.c", username="ana", hashed_password="x", is_active=True)
            self.otro = UserORM(id=uuid.uuid4(), email="o@b.c", username="otro", hashed_password="x", is_active=True)
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
            s.add_all([self.ana, self.otro, receptor, otro_receptor])
            await s.commit()
            self.receptor_id = receptor.id
            self.otro_receptor_id = otro_receptor.id

    async def apagar(self):
        if self.engine is not None:
            await self.engine.dispose()
        self.engine = None

    async def agregar(self, filas: list[dict]) -> None:
        """Una molécula con su última evaluación por fila. Sólo `nombre` y `smiles` son obligatorios."""
        async with self.factory() as s:
            for fila in filas:
                duenyo = fila.get("dueno", self.ana)
                receptor = fila.get("receptor", self.receptor_id)
                molecula = MoleculeORM(
                    id=uuid.uuid4(), smiles=fila["smiles"], name=fila["nombre"],
                    smiles_hash=hashlib.sha256(fila["nombre"].encode()).hexdigest(),
                    user_id=duenyo.id, target_id=receptor,
                )
                s.add(molecula)
                await s.flush()
                resultado = EvaluationResultORM(
                    molecule_id=molecula.id,
                    affinity_kcal=fila.get("afinidad", -6.0),
                    total_score=fila.get("indice"),
                    error_message=fila.get("error"),
                    docking_protocol=_protocolo(fila.get("k", 1), fila.get("exhaustividad", 8)),
                    ligand_state=_estado(),
                    vina_version="1.2.7",
                    vina_random_seed=42,
                    receptor_sha256=RECEPTOR_SHA,
                )
                if fila.get("fecha") is not None:
                    resultado.evaluated_at = fila["fecha"]
                s.add(resultado)
                self.ids[fila["nombre"]] = molecula.id
            await s.commit()

    async def sin_fecha(self, nombre: str) -> None:
        async with self.factory() as s:
            await s.execute(
                update(EvaluationResultORM)
                .where(EvaluationResultORM.molecule_id == self.ids[nombre])
                .values(evaluated_at=None)
            )
            await s.commit()

    def cliente(self, usuario: UserORM | None) -> httpx.AsyncClient:
        async def db_override():
            async with self.factory() as session:
                yield session

        async def usuario_override():
            return usuario

        app = FastAPI()
        app.include_router(sar_router)
        app.dependency_overrides[get_db] = db_override
        app.dependency_overrides[get_current_user_optional] = usuario_override
        return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost")

    async def tabla(self, nombre: str, usuario="ana", **params) -> dict:
        quien = self.ana if usuario == "ana" else usuario
        async with self.cliente(quien) as c:
            r = await c.get(f"/sar/{self.ids[nombre]}", params=params)
        assert r.status_code == 200, r.text
        return r.json()


@pytest_asyncio.fixture
async def mundo(tmp_path):
    await db_mod.reset_engine()
    m = _Mundo(tmp_path / "sar_seleccion.db")
    await m.arrancar()
    try:
        yield m
    finally:
        await m.apagar()
        await db_mod.reset_engine()


def _nombres(cuerpo: dict) -> list[str]:
    return [fila["name"] for fila in cuerpo["results"]]


def _candidatas() -> list[tuple[str, str]]:
    return _serie() + SEUELOS


def _filas_de_serie() -> list[dict]:
    """La serie con y sin índice, los señuelos con el índice más alto y el análogo antiguo sin índice."""
    filas = []
    for i, (nombre, smiles) in enumerate(_serie()):
        fila = {"nombre": nombre, "smiles": smiles, "afinidad": -6.0 - (i % 5) * 0.1,
                "indice": None if i % 2 == 0 else 40.0 + i % 10}
        if nombre == "antiguo-sin-indice":
            # El análogo más parecido a la base (un metilo donde ella tiene el hidroxilo), evaluado en 2020 y sin índice.
            fila.update(afinidad=-5.5, indice=None, fecha=datetime(2020, 1, 1, tzinfo=UTC))
        filas.append(fila)
    filas += [{"nombre": n, "smiles": s, "afinidad": -12.0, "indice": 99.0} for n, s in SEUELOS]
    return filas


async def _sembrar_serie(mundo: _Mundo) -> None:
    await mundo.agregar([{"nombre": "base", "smiles": BASE, "afinidad": -6.0, "indice": 70.0}])
    await mundo.agregar(_filas_de_serie())


# ── 1. La selección ──────────────────────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_entran_las_cincuenta_mas_parecidas_y_la_referencia_no_gasta_plaza(mundo):
    await _sembrar_serie(mundo)
    cuerpo = await mundo.tabla("base")
    filas = cuerpo["results"]

    candidatas = _candidatas()
    ordenadas = sorted(((_tanimoto(BASE, smiles), nombre) for nombre, smiles in candidatas), reverse=True)
    # Sin un empate en la frontera la prueba no mide el corte: el 50.º y el 51.º no pueden valer lo mismo.
    assert ordenadas[LIMITE_COMPARACIONES - 1][0] > ordenadas[LIMITE_COMPARACIONES][0]
    esperadas = {nombre for _t, nombre in ordenadas[:LIMITE_COMPARACIONES]}

    assert len(filas) == LIMITE_COMPARACIONES + 1
    assert filas[0]["is_base"] is True and filas[0]["molecule_id"] == str(mundo.ids["base"])
    assert sum(1 for f in filas if f["is_base"]) == 1
    assert len({f["molecule_id"] for f in filas}) == len(filas), "la referencia no se repite como comparación"
    assert set(_nombres(cuerpo)[1:]) == esperadas
    assert cuerpo["total_analogs"] == LIMITE_COMPARACIONES + 1

    # En el orden de selección: la más parecida primero, no por índice.
    similitudes = [f["similarity"] for f in filas[1:]]
    assert similitudes == sorted(similitudes, reverse=True)
    del_oraculo = {nombre: _tanimoto(BASE, smiles) for nombre, smiles in candidatas}
    for fila in filas[1:]:
        assert fila["similarity"] == pytest.approx(del_oraculo[fila["name"]], abs=0.0006)

    assert cuerpo["cohort"] == {"source": "latest_projection", "base_task_id": None, "task_ids": None}
    assert cuerpo["selection"] == {
        "criterion": "tanimoto_morgan_r2_1024",
        "limit": LIMITE_COMPARACIONES,
        "eligible": len(candidatas),
        "without_fingerprint": 0,
        "selected": LIMITE_COMPARACIONES,
        "reason": None,
    }


@pytest.mark.asyncio
async def test_el_indice_alto_de_un_senuelo_no_lo_hace_entrar(mundo):
    """Lo que la consulta anterior ponía primero —el índice más alto— ya no decide quién entra."""
    await _sembrar_serie(mundo)
    nombres = _nombres(await mundo.tabla("base"))
    ordenadas = sorted(((_tanimoto(BASE, s), n) for n, s in _candidatas()), reverse=True)
    corte = ordenadas[LIMITE_COMPARACIONES - 1][0]
    for nombre, smiles in SEUELOS:
        assert _tanimoto(BASE, smiles) < corte, "el señuelo debe ser menos parecido que la última que entra"
        assert nombre not in nombres


@pytest.mark.asyncio
async def test_un_analogo_antiguo_y_sin_indice_entra_si_es_de_los_mas_parecidos(mundo):
    """El defecto: `total_score IS NOT NULL` lo dejaba fuera aunque casi fuera la referencia."""
    await _sembrar_serie(mundo)
    cuerpo = await mundo.tabla("base")
    fila = next(f for f in cuerpo["results"] if f["name"] == "antiguo-sin-indice")
    assert fila["total_score"] is None
    assert fila["affinity_kcal"] == -5.5
    assert fila["is_base"] is False
    # Un metilo donde la base tiene el hidroxilo: de los dos más parecidos. La premisa se comprueba con el oráculo.
    por_similitud = [n for _t, n in sorted(((_tanimoto(BASE, s), n) for n, s in _candidatas()), reverse=True)]
    assert por_similitud.index("antiguo-sin-indice") <= 1
    assert _nombres(cuerpo).index("antiguo-sin-indice") <= 2  # 0 es la referencia


@pytest.mark.asyncio
async def test_la_misma_consulta_devuelve_siempre_lo_mismo(mundo):
    await _sembrar_serie(mundo)
    primera = [f["molecule_id"] for f in (await mundo.tabla("base"))["results"]]
    segunda = [f["molecule_id"] for f in (await mundo.tabla("base"))["results"]]
    assert primera == segunda


# ── 2. Qué se admite ─────────────────────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_no_entra_lo_que_fallo_ni_lo_que_no_tiene_afinidad_finita_ni_lo_ilegible(mundo):
    parecido = "CC(=O)Nc1ccc(OC)cc1"
    await mundo.agregar([
        {"nombre": "base", "smiles": BASE, "afinidad": -6.0, "indice": 70.0},
        {"nombre": "valida", "smiles": parecido, "afinidad": -6.5, "indice": None},
        # Una proyección fallida: el registro del error limpia el índice y la afinidad.
        {"nombre": "fallida", "smiles": parecido + "C", "afinidad": None, "indice": None, "error": "Vina murió"},
        # Un error viejo que conserva una afinidad de una corrida anterior: tampoco es evidencia.
        {"nombre": "error-viejo", "smiles": parecido + "CC", "afinidad": -9.0, "indice": 80.0, "error": "x"},
        {"nombre": "infinita", "smiles": parecido + "CCC", "afinidad": float("inf"), "indice": 80.0},
        # Propiedades calculadas, sin acoplar todavía.
        {"nombre": "solo-propiedades", "smiles": parecido + "CCCC", "afinidad": None, "indice": None},
        {"nombre": "ilegible", "smiles": "no-es-un-smiles", "afinidad": -7.0, "indice": 50.0},
    ])
    cuerpo = await mundo.tabla("base")

    assert _nombres(cuerpo) == ["base", "valida"]
    assert cuerpo["selection"]["eligible"] == 2
    assert cuerpo["selection"]["without_fingerprint"] == 1
    assert cuerpo["selection"]["selected"] == 1
    assert cuerpo["total_analogs"] == 2


@pytest.mark.asyncio
async def test_si_la_base_no_se_lee_no_se_inventan_comparaciones(mundo):
    await mundo.agregar([
        {"nombre": "base", "smiles": "no-es-un-smiles", "afinidad": -6.0, "indice": 70.0},
        {"nombre": "otra", "smiles": BASE, "afinidad": -6.5, "indice": 60.0},
    ])
    cuerpo = await mundo.tabla("base")

    assert _nombres(cuerpo) == ["base"]
    assert cuerpo["results"][0]["is_base"] is True
    assert cuerpo["results"][0]["similarity"] is None
    assert cuerpo["selection"]["selected"] == 0
    assert cuerpo["selection"]["reason"]
    assert cuerpo["selection"]["eligible"] == 1


@pytest.mark.asyncio
async def test_una_base_sin_indice_conserva_su_fila(mundo):
    await mundo.agregar([
        {"nombre": "base", "smiles": BASE, "afinidad": -6.0, "indice": None},
        {"nombre": "otra", "smiles": "CC(=O)Nc1ccc(OC)cc1", "afinidad": -6.5, "indice": 60.0},
    ])
    cuerpo = await mundo.tabla("base")

    assert cuerpo["results"][0]["name"] == "base"
    assert cuerpo["results"][0]["is_base"] is True
    assert cuerpo["results"][0]["total_score"] is None
    assert cuerpo["base_score"] is None
    assert cuerpo["base_affinity"] == -6.0


# ── 3. Quién entra: dueño y receptor ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_lo_ajeno_no_entra_aunque_sea_estructuralmente_identico(mundo):
    await mundo.agregar([
        {"nombre": "base", "smiles": BASE, "afinidad": -6.0, "indice": 70.0},
        {"nombre": "mia", "smiles": "CC(=O)Nc1ccc(OC)cc1", "afinidad": -6.5, "indice": 60.0},
        # Idénticas a la base, contra el mismo receptor, pero de otro dueño.
        {"nombre": "de-otro", "smiles": BASE, "afinidad": -9.0, "indice": 90.0, "dueno": mundo.otro},
        {"nombre": "anonima", "smiles": BASE, "afinidad": -9.0, "indice": 90.0, "dueno": mundo.anonimo},
        # Mía y idéntica, pero contra otro receptor.
        {"nombre": "otro-receptor", "smiles": BASE, "afinidad": -9.0, "indice": 90.0, "receptor": mundo.otro_receptor_id},
    ])
    assert _nombres(await mundo.tabla("base")) == ["base", "mia"]


@pytest.mark.asyncio
async def test_sin_sesion_se_ve_lo_anonimo_y_nada_mas(mundo):
    await mundo.agregar([
        {"nombre": "base", "smiles": BASE, "afinidad": -6.0, "indice": 70.0, "dueno": mundo.anonimo},
        {"nombre": "anonima", "smiles": "CC(=O)Nc1ccc(OC)cc1", "afinidad": -6.5, "dueno": mundo.anonimo},
        {"nombre": "de-ana", "smiles": BASE, "afinidad": -9.0, "indice": 90.0},
    ])
    cuerpo = await mundo.tabla("base", usuario=None)
    assert _nombres(cuerpo) == ["base", "anonima"]


# ── 4. Desempates ────────────────────────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_un_empate_exacto_se_resuelve_por_fecha_y_despues_por_id(mundo):
    gemela = "CC(=O)Nc1ccc(OC)cc1"
    await mundo.agregar([
        {"nombre": "base", "smiles": BASE, "afinidad": -6.0, "indice": 70.0},
        {"nombre": "antigua", "smiles": gemela, "fecha": datetime(2020, 1, 1, tzinfo=UTC)},
        {"nombre": "reciente", "smiles": gemela, "fecha": datetime(2026, 6, 1, tzinfo=UTC)},
        {"nombre": "sin-fecha", "smiles": gemela},
        {"nombre": "mismo-dia-a", "smiles": gemela, "fecha": datetime(2023, 3, 3, tzinfo=UTC)},
        {"nombre": "mismo-dia-b", "smiles": gemela, "fecha": datetime(2023, 3, 3, tzinfo=UTC)},
    ])
    await mundo.sin_fecha("sin-fecha")
    cuerpo = await mundo.tabla("base")
    nombres = _nombres(cuerpo)

    assert nombres[:3] == ["base", "reciente", "mismo-dia-a"] or nombres[:3] == ["base", "reciente", "mismo-dia-b"]
    # El mismo día, por id ascendente; la evaluación sin fecha, al final; la antigua, antes que ella.
    pareja = [f["molecule_id"] for f in cuerpo["results"] if f["name"].startswith("mismo-dia")]
    assert pareja == sorted(pareja)
    assert nombres[-2:] == ["antigua", "sin-fecha"]


def test_el_orden_no_redondea_el_tanimoto_antes_de_comparar():
    """0,8004 y 0,8001 se muestran como 0,800, pero no empatan: gana la más parecida aunque sea más vieja."""
    mas_parecida = Candidata("b" * 8, "C", datetime(2020, 1, 1, tzinfo=UTC), -5.0)
    menos_parecida = Candidata("a" * 8, "C", datetime(2026, 1, 1, tzinfo=UTC), -5.0)
    assert round(0.8004, 3) == round(0.8001, 3)
    assert clave_de_orden(0.8004, mas_parecida) < clave_de_orden(0.8001, menos_parecida)


def test_la_clave_tolera_fechas_con_y_sin_zona_y_ordena_la_ausente_al_final():
    con_zona = Candidata("2", "C", datetime(2026, 1, 1, tzinfo=UTC), -5.0)
    sin_zona = Candidata("3", "C", datetime(2025, 1, 1), -5.0)  # SQLite devuelve fechas sin zona
    sin_fecha = Candidata("1", "C", None, -5.0)
    ordenadas = sorted([sin_fecha, sin_zona, con_zona], key=lambda c: clave_de_orden(0.5, c))
    assert [c.molecule_id for c in ordenadas] == ["2", "3", "1"]


def test_seleccionar_respeta_el_limite_y_descarta_lo_no_finito():
    base = "CC(=O)Nc1ccc(O)cc1"
    candidatas = [
        Candidata(f"id-{i}", smiles, None, afinidad)
        for i, (smiles, afinidad) in enumerate([
            ("CC(=O)Nc1ccc(OC)cc1", -6.0),
            ("CC(=O)Nc1ccc(F)cc1", -6.1),
            ("CC(=O)Nc1ccc(Cl)cc1", float("nan")),
            ("CC(=O)Nc1ccc(Br)cc1", float("inf")),
            ("CC(=O)Nc1ccc(C)cc1", None),
            ("CCO", -5.0),
        ])
    ]
    def huella(molecula):
        return rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=1024).GetFingerprint(molecula)

    seleccion = seleccionar(candidatas, base, huella, limite=2)

    assert seleccion.admitidas == 3  # las tres con afinidad finita
    assert [c.molecule_id for c, _t in seleccion.elegidas] != []
    assert {c.molecule_id for c, _t in seleccion.elegidas} == {"id-0", "id-1"}  # el etanol queda fuera del corte
    assert seleccion.elegidas[0][1] >= seleccion.elegidas[1][1]
    assert seleccion.motivo is None


# ── 5. La corrida pedida como referencia ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_una_corrida_historica_como_base_no_duplica_la_proyeccion_de_su_molecula(mundo):
    await mundo.agregar([
        {"nombre": "base", "smiles": BASE, "afinidad": -5.0, "indice": 70.0},
        {"nombre": "comparable", "smiles": "CC(=O)Nc1ccc(OC)cc1", "afinidad": -6.0, "indice": 60.0},
    ])
    async with mundo.factory() as s:
        repo = Repository(s)
        await repo.snapshot_evaluation_run(mundo.ids["base"], "base-historica")
        # La proyección de la base cambia después: otra afinidad, otro protocolo.
        resultado = await repo.get_evaluation_result(mundo.ids["base"])
        resultado.affinity_kcal = -9.0
        resultado.docking_protocol = _protocolo(30)
        await s.commit()

    cuerpo = await mundo.tabla("base", task_id="base-historica")

    de_la_base = [f for f in cuerpo["results"] if f["molecule_id"] == str(mundo.ids["base"])]
    assert len(de_la_base) == 1
    assert de_la_base[0]["is_base"] is True
    assert de_la_base[0]["affinity_kcal"] == -5.0, "la fila de la referencia es la de la corrida, no la proyección"
    assert de_la_base[0]["task_id"] == "base-historica"
    assert cuerpo["base_affinity"] == -5.0
    assert cuerpo["cohort"] == {"source": "latest_projection", "base_task_id": "base-historica", "task_ids": None}
    assert _nombres(cuerpo) == ["base", "comparable"]
    # El delta se mide contra la afinidad de la corrida pedida.
    assert cuerpo["results"][1]["delta_affinity"] == -1.0


@pytest.mark.asyncio
async def test_una_comparacion_con_otro_protocolo_entra_pero_no_se_resta(mundo):
    await mundo.agregar([
        {"nombre": "base", "smiles": BASE, "afinidad": -6.0, "indice": 70.0},
        {"nombre": "comparable", "smiles": "CC(=O)Nc1ccc(OC)cc1", "afinidad": -7.0},
        {"nombre": "otro-protocolo", "smiles": "CC(=O)Nc1ccc(F)cc1", "afinidad": -8.0, "k": 30},
    ])
    cuerpo = await mundo.tabla("base")
    filas = {f["name"]: f for f in cuerpo["results"]}

    assert filas["comparable"]["comparison_state"] == "descriptive"
    assert filas["comparable"]["delta_affinity"] == -1.0
    assert filas["otro-protocolo"]["comparison_state"] == "abstained"
    assert filas["otro-protocolo"]["delta_affinity"] is None
    assert filas["otro-protocolo"]["comparison_reason"]
    assert filas["otro-protocolo"]["affinity_kcal"] == -8.0, "la afinidad cruda sigue visible"


# ── 6. Lo que no cambia y lo que cuesta ──────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_una_cohorte_explicita_no_se_reselecciona_ni_se_corta_a_cincuenta(mundo):
    total = LIMITE_COMPARACIONES + 5
    await mundo.agregar([
        {"nombre": f"m{i}", "smiles": "C" * (i + 2) + "C(=O)Nc1ccc(O)cc1", "afinidad": -5.0 - i * 0.01,
         "indice": 50.0 + i * 0.1}
        for i in range(total)
    ])
    tareas = []
    async with mundo.factory() as s:
        repo = Repository(s)
        for i in range(total):
            await repo.snapshot_evaluation_run(mundo.ids[f"m{i}"], f"corrida-{i}")
            tareas.append(f"corrida-{i}")
        await s.commit()

    cuerpo = await mundo.tabla("m0", task_id="corrida-0", cohort_task_ids=tareas)

    assert len(cuerpo["results"]) == total
    assert cuerpo["total_analogs"] == total
    assert cuerpo["cohort"]["source"] == "explicit_runs"
    assert cuerpo["selection"] is None
    # La cohorte explícita conserva su orden por índice.
    indices = [f["total_score"] for f in cuerpo["results"]]
    assert indices == sorted(indices, reverse=True)


@pytest.mark.asyncio
async def test_el_nucleo_comun_se_calcula_solo_para_las_filas_que_se_devuelven(mundo, monkeypatch):
    llamadas: list[str] = []

    def _contado(base, otro):
        llamadas.append(otro)
        return None

    monkeypatch.setattr(sar_mod, "cambio_estructural", _contado)
    await _sembrar_serie(mundo)
    cuerpo = await mundo.tabla("base")

    candidatas = len(_candidatas())
    assert candidatas > LIMITE_COMPARACIONES
    assert len(llamadas) == len(cuerpo["results"]) == LIMITE_COMPARACIONES + 1, (
        f"{len(llamadas)} cálculos de núcleo común para {len(cuerpo['results'])} filas y {candidatas} candidatas"
    )


@pytest.mark.asyncio
async def test_la_consulta_ligera_no_trae_el_orm_completo(mundo):
    """Las candidatas son filas de cuatro campos; el ORM completo sólo se carga para las elegidas."""
    await _sembrar_serie(mundo)
    async with mundo.factory() as s:
        repo = Repository(s)
        filas = await repo.get_sar_candidatas("3F75", mundo.ana.id, excluir_molecula_id=mundo.ids["base"])
        assert len(filas) == len(_candidatas())
        assert all(len(f) == 4 for f in filas)
        assert mundo.ids["base"] not in {f[0] for f in filas}
        elegidas = [f[0] for f in filas[:3]]
        completas = await repo.get_sar_evaluaciones("3F75", mundo.ana.id, elegidas)
        assert {e.molecule_id for e in completas} == set(elegidas)
        assert all(e.molecule is not None and e.molecule.target is not None for e in completas)
        assert await repo.get_sar_evaluaciones("3F75", mundo.ana.id, []) == []


def test_el_modulo_de_seleccion_no_toca_la_base_ni_el_bucle():
    """Es puro: recibe filas y devuelve una decisión. Nada de ORM, sesiones ni asyncio."""
    import services.sar.seleccion as modulo

    fuente = open(modulo.__file__, encoding="utf-8").read()
    for prohibido in ("sqlalchemy", "AsyncSession", "asyncio", "core.models", "db.repository"):
        assert prohibido not in fuente, prohibido
