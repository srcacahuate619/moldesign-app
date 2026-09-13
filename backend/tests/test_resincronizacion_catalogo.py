"""La sincronizacion del catalogo, probada contra una base de verdad.

Reproduce el escenario exacto que motivo el modulo: una base sembrada con el
catalogo ANTIGUO -como la de la VM donde se hizo la primera evaluacion completa-
y el catalogo nuevo en disco. Sin esto, `_auto_seed_curated_targets_if_empty`
salta cualquier `pdb_id` existente y las correcciones no llegan jamas.

Lo que se comprueba no es que el codigo corra, sino las cuatro propiedades de
las que depende que sea seguro ejecutarlo solo en cada arranque:

  1. actualiza lo que el catalogo posee;
  2. NO toca lo que es del usuario -ni sus receptores ni su calibracion-;
  3. invalida el `.pdbqt` cuando la cadena o la caja cambian;
  4. es idempotente: la segunda vuelta no hace nada.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from core.models import Base, TargetORM
from services.targets.resincronizacion import (
    es_del_catalogo,
    resincronizar_catalogo,
    sanear_hotspots,
)

CATALOGO = Path(__file__).resolve().parents[2] / "curated_targets.json"


@pytest_asyncio.fixture
async def sesion(tmp_path):
    motor = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'prueba.db'}")
    async with motor.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    fabrica = async_sessionmaker(motor, expire_on_commit=False)
    async with fabrica() as db:
        yield db
    await motor.dispose()


#: El receptor de referencia. 5COP es la proteasa del VIH salvaje: sitio en la
#: interfaz del dimero, con ligando co-cristalizado. Antes era 1TW7, retirado
#: del catalogo por tener los hotspots a 16-25 A del sitio.
REFERENCIA = "5COP"


def _del_catalogo(pdb_id: str) -> dict:
    """Falla, no salta: un `skip` apagaria estas pruebas sin dejar rastro."""
    for fila in json.loads(CATALOGO.read_text(encoding="utf-8")):
        if (fila.get("pdb_id") or "").upper() == pdb_id:
            return fila
    raise AssertionError(
        f"{pdb_id} ya no esta en el catalogo: estas pruebas se quedarian sin "
        "material. Elige otro receptor y actualiza REFERENCIA."
    )


# ── 1. Lo que el catalogo posee se actualiza ─────────────────────────────────

@pytest.mark.asyncio
async def test_una_base_vieja_recibe_las_correcciones(sesion):
    """El caso de la VM: la proteasa sembrada con la cadena 'A' y sin sitio medido.

    Es el receptor del doc 71: la proteasa del VIH, cuyo sitio activo esta en la
    interfaz del dimero. Con `chain='A'` y `site_chains=None` la interfaz decia
    «Sitio sin medir» y la preparacion conservaba media cavidad.
    """
    esperado = _del_catalogo(REFERENCIA)
    sesion.add(TargetORM(
        pdb_id=REFERENCIA, name="viejo", chain="A",
        grid_center_x=0.0, grid_center_y=0.0, grid_center_z=0.0,
        grid_size_x=20.0, grid_size_y=20.0, grid_size_z=20.0,
        structural_family="protease", is_prepared=True,
        prepared_file_path="targets/1TW7/prepared.pdbqt",
    ))
    await sesion.commit()

    resumen = await resincronizar_catalogo(sesion, CATALOGO)
    assert resumen["estado"] == "aplicado"

    t = (await sesion.execute(select(TargetORM).where(TargetORM.pdb_id == REFERENCIA))).scalar_one()
    assert t.chain == esperado["chain"]
    assert t.site_chains == esperado["site_chains"]
    assert t.site_evidence == esperado["site_evidence"]
    assert t.grid_center_x == pytest.approx(esperado["grid_center_x"])
    assert t.resolution == esperado["resolution"]


@pytest.mark.asyncio
async def test_anade_los_objetivos_que_la_base_no_tenia(sesion):
    """Una base sembrada antes de que un receptor entrara al catalogo."""
    resumen = await resincronizar_catalogo(sesion, CATALOGO)
    assert resumen["anadidos"] == len(json.loads(CATALOGO.read_text(encoding="utf-8")))
    total = len((await sesion.execute(select(TargetORM))).scalars().all())
    assert total == resumen["anadidos"]


# ── 2. Lo del usuario no se toca ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_no_toca_los_receptores_del_usuario(sesion):
    """Un receptor subido a mano no esta en el JSON. Ni se actualiza ni se
    retira por no estar: retirarlo seria destruir lo suyo."""
    propio = TargetORM(
        pdb_id="USR_MIO", name="mi receptor", chain="Z",
        grid_center_x=1.0, grid_center_y=2.0, grid_center_z=3.0,
        grid_size_x=25.0, grid_size_y=25.0, grid_size_z=25.0,
        structural_family="kinase", is_private=True,
    )
    sesion.add(propio)
    await sesion.commit()

    await resincronizar_catalogo(sesion, CATALOGO)

    t = (await sesion.execute(select(TargetORM).where(TargetORM.pdb_id == "USR_MIO"))).scalar_one()
    assert t.chain == "Z"
    assert t.retired_reason is None


@pytest.mark.asyncio
async def test_no_toca_una_variante_de_preparacion(sesion):
    """Una variante lleva el mismo `pdb_id` que su padre a proposito.

    Sobreescribirla con los valores del catalogo destruiria justo lo que la
    hace una variante: la caja o la cadena que el usuario eligio.
    """
    padre = uuid.uuid4()
    variante = TargetORM(
        pdb_id=REFERENCIA, name="mi variante de la referencia", chain="B",
        grid_center_x=9.0, grid_center_y=9.0, grid_center_z=9.0,
        grid_size_x=30.0, grid_size_y=30.0, grid_size_z=30.0,
        structural_family="protease", is_private=True,
        preparation_parent_id=padre,
    )
    sesion.add(variante)
    await sesion.commit()

    await resincronizar_catalogo(sesion, CATALOGO)

    t = (await sesion.execute(
        select(TargetORM).where(TargetORM.preparation_parent_id == padre))).scalar_one()
    assert t.chain == "B"
    assert t.grid_center_x == 9.0


@pytest.mark.asyncio
async def test_no_borra_la_calibracion_local(sesion):
    """`spearman_rho` y `calibration_date` los produce la maquina del usuario.

    Sobreescribirlos con el `null` del catalogo seria borrar su trabajo para
    poner un hueco: exactamente lo que este modulo existe para evitar en la
    otra direccion.
    """
    from datetime import datetime, timezone

    fecha = datetime(2026, 1, 15, tzinfo=timezone.utc)
    sesion.add(TargetORM(
        pdb_id=REFERENCIA, name="viejo", chain="A",
        grid_center_x=0.0, grid_center_y=0.0, grid_center_z=0.0,
        grid_size_x=20.0, grid_size_y=20.0, grid_size_z=20.0,
        structural_family="protease",
        spearman_rho=0.71, calibration_date=fecha, is_hot=True,
    ))
    await sesion.commit()

    await resincronizar_catalogo(sesion, CATALOGO)

    t = (await sesion.execute(select(TargetORM).where(TargetORM.pdb_id == REFERENCIA))).scalar_one()
    assert t.spearman_rho == 0.71
    assert t.is_hot is True
    # Y aun asi la correccion del catalogo SI se aplico. Se comprueba con
    # `site_chains` y no con `chain`: la cadena de 5COP en el catalogo ES «A»
    # -esta entre las que forman el sitio, asi que nunca hizo falta cambiarla-
    # y una asercion sobre ella pasaria por casualidad.
    assert t.site_chains == _del_catalogo(REFERENCIA)["site_chains"]
    assert t.site_chains is not None


# ── 3. El receptor preparado se invalida ─────────────────────────────────────

@pytest.mark.asyncio
async def test_invalida_el_pdbqt_cuando_cambia_la_cadena_o_la_caja(sesion):
    """Servir el `.pdbqt` viejo con la anotacion nueva es peor que cualquiera
    de los dos por separado."""
    sesion.add(TargetORM(
        pdb_id=REFERENCIA, name="viejo", chain="A",
        grid_center_x=0.0, grid_center_y=0.0, grid_center_z=0.0,
        grid_size_x=20.0, grid_size_y=20.0, grid_size_z=20.0,
        structural_family="protease",
        is_prepared=True, prepared_file_path="targets/1TW7/prepared.pdbqt",
    ))
    await sesion.commit()

    resumen = await resincronizar_catalogo(sesion, CATALOGO)

    t = (await sesion.execute(select(TargetORM).where(TargetORM.pdb_id == REFERENCIA))).scalar_one()
    assert t.is_prepared is False
    assert t.prepared_file_path is None
    assert REFERENCIA in resumen["preparacion_invalidada"]


@pytest.mark.asyncio
async def test_no_invalida_si_solo_cambio_algo_descriptivo(sesion):
    """Cambiar el organismo o la resolucion no obliga a volver a preparar."""
    fila = _del_catalogo(REFERENCIA)
    sesion.add(TargetORM(
        pdb_id=REFERENCIA, name=REFERENCIA, chain=fila["chain"],
        grid_center_x=fila["grid_center_x"], grid_center_y=fila["grid_center_y"],
        grid_center_z=fila["grid_center_z"], grid_size_x=fila["grid_size_x"],
        grid_size_y=fila["grid_size_y"], grid_size_z=fila["grid_size_z"],
        structural_family=fila["structural_family"],
        site_chains=fila["site_chains"],
        organism="ORGANISMO VIEJO",           # lo unico distinto
        is_prepared=True, prepared_file_path="targets/1TW7/prepared.pdbqt",
    ))
    await sesion.commit()

    resumen = await resincronizar_catalogo(sesion, CATALOGO)

    t = (await sesion.execute(select(TargetORM).where(TargetORM.pdb_id == REFERENCIA))).scalar_one()
    assert t.organism == fila["organism"]
    assert t.is_prepared is True
    assert REFERENCIA not in resumen["preparacion_invalidada"]


# ── 4. Los retirados ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_marca_los_retirados_sin_borrarlos(sesion):
    """2ONV salio del catalogo (doc 72): un cristal de hexapeptido.

    La fila se conserva porque puede haber evaluaciones colgando de ella. Se
    marca, y `list_targets` deja de ofrecerlo.
    """
    sesion.add(TargetORM(
        pdb_id="2ONV", name="peptido amiloide", chain="A",
        grid_center_x=1.6, grid_center_y=10.5, grid_center_z=1.2,
        grid_size_x=22.0, grid_size_y=22.0, grid_size_z=22.0,
        structural_family="protein_interaction",
    ))
    await sesion.commit()

    resumen = await resincronizar_catalogo(sesion, CATALOGO)

    t = (await sesion.execute(select(TargetORM).where(TargetORM.pdb_id == "2ONV"))).scalar_one()
    assert t.retired_reason, "un retirado tiene que decir por que"
    assert "2ONV" in resumen["retirados"]
    assert t.name == "peptido amiloide", "no se borra la fila ni sus datos"


# ── 5. Idempotencia ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_la_segunda_vuelta_no_hace_nada(sesion):
    """Corre en CADA arranque. Si no fuera idempotente, cada arranque
    invalidaria la preparacion y el usuario esperaria de mas para siempre."""
    primera = await resincronizar_catalogo(sesion, CATALOGO)
    assert primera["estado"] == "aplicado"

    segunda = await resincronizar_catalogo(sesion, CATALOGO)
    assert segunda["estado"] == "al_dia"
    assert "actualizados" not in segunda


# ── El saneado de hotspots ───────────────────────────────────────────────────

@pytest.mark.parametrize("crudo,esperado", [
    ([{"name": "A:TYR66"}], [{"name": "A:TYR66"}]),
    ('[{"name": "A:TYR66"}]', [{"name": "A:TYR66"}]),
    ('"[{\\"name\\": \\"A:TYR66\\"}]"', [{"name": "A:TYR66"}]),  # doble serializado
    ("null", None),
    ("[]", None),
    ([], None),
    (None, None),
])
def test_los_tres_formatos_historicos_dan_lo_mismo(crudo, esperado):
    """El campo se guardo como lista, como cadena JSON y como cadena DOBLEMENTE
    serializada -el bug del doble escape-. Sanearlo en un solo sitio evita que
    dos implementaciones diverjan."""
    assert sanear_hotspots(crudo) == esperado


def test_nunca_devuelve_una_cadena():
    """La columna es JSON y su serializador ya hace `json.dumps`: meterle un
    texto lo serializaria dos veces, que es como se llego al bug historico."""
    for crudo in ("null", "[]", "texto suelto", '"cadena"'):
        assert not isinstance(sanear_hotspots(crudo), str)


def test_es_del_catalogo_distingue_lo_del_usuario():
    class T:
        is_private = False
        is_community = False
        preparation_parent_id = None

    assert es_del_catalogo(T())
    for campo, valor in (("is_private", True), ("is_community", True),
                         ("preparation_parent_id", uuid.uuid4())):
        t = T()
        setattr(t, campo, valor)
        assert not es_del_catalogo(t), f"{campo} deberia excluirlo"
