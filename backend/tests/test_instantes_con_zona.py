"""La API sirve los instantes con su zona (UTC), y todo se escribe en UTC.

EL FALLO (B03 de la QA de release de 1.0.2, 2026-10-09). El Historial enseñaba cada
corrida seis horas adelantada en Ciudad de México. SQLite no guarda la zona: lo que se
escribe en UTC (`CURRENT_TIMESTAMP`, `datetime.now(UTC)`) se lee sin ella, la API lo
servía como `2026-10-10T00:52:18.887044` y el navegador lo tomaba por hora local.
Moldex (la fecha de cada ficha) y el resultado de una evaluación tenían lo mismo.

El arreglo repone la zona al servir (`utils/instantes.py`). Es correcto sólo si
TODO se escribe en UTC, y eso también se vigila aquí.
"""
from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

from core.models import EvaluationResultRead
from db.repository import Repository
from tests.test_moldex_guarda_corridas import _guardar, cliente, mundo  # noqa: F401  (fixtures)
from utils.instantes import instante_utc


# ── El ayudante ──────────────────────────────────────────────────────

def test_un_instante_sin_zona_es_utc():
    assert instante_utc(datetime(2026, 10, 10, 0, 52, 18, 887044)) == "2026-10-10T00:52:18.887044+00:00"


def test_un_instante_con_otra_zona_se_pasa_a_utc():
    cdmx = timezone(timedelta(hours=-6))
    assert instante_utc(datetime(2026, 10, 9, 18, 52, tzinfo=cdmx)) == "2026-10-10T00:52:00+00:00"


def test_la_cadena_de_una_instantanea_tambien_lleva_la_zona():
    # Así guarda `snapshot_json` el `evaluated_at` de una corrida, y no se reescribe.
    assert instante_utc("2026-10-10T00:52:18.887044") == "2026-10-10T00:52:18.887044+00:00"
    assert instante_utc("2026-10-10 00:52:18") == "2026-10-10T00:52:18+00:00"


def test_lo_que_no_es_un_instante_no_se_inventa():
    assert instante_utc(None) is None
    assert instante_utc("") is None
    assert instante_utc("sin fecha") == "sin fecha"


# ── Lo que sirve la API ──────────────────────────────────────────────

def _es_ahora_en_utc(texto: str) -> None:
    instante = datetime.fromisoformat(texto)
    # `+00:00` o `Z` (así lo escribe Pydantic): las dos son UTC para el navegador.
    assert instante.utcoffset() == timedelta(0), texto
    # Que diga «UTC» no basta: tiene que ser ESTE instante, no la hora local etiquetada.
    assert abs(datetime.now(UTC) - instante) < timedelta(minutes=5), texto


@pytest.mark.asyncio
async def test_el_historial_sirve_la_hora_con_su_zona(mundo, cliente):  # noqa: F811
    await mundo.evaluar("run-A", 40.0, -6.0)

    (fila,) = (await cliente.get("/history/evaluations")).json()["items"]

    _es_ahora_en_utc(fila["created_at"])
    _es_ahora_en_utc(fila["evaluated_at"])


@pytest.mark.asyncio
async def test_moldex_sirve_la_hora_con_su_zona(mundo, cliente):  # noqa: F811
    await mundo.evaluar("run-A", 40.0, -6.0)
    assert (await _guardar(cliente, mundo, "run-A")).status_code == 200

    (ficha,) = (await cliente.get("/moldex")).json()["results"]

    _es_ahora_en_utc(ficha["created_at"])
    _es_ahora_en_utc(ficha["evaluated_at"])


@pytest.mark.asyncio
async def test_el_resultado_de_una_evaluacion_sirve_la_hora_con_su_zona(mundo):  # noqa: F811
    await mundo.evaluar("run-A", 40.0, -6.0)
    async with mundo.factory() as db:
        repo = Repository(db)
        corrida = await repo.get_evaluation_run("run-A", mundo.molecule_id)
        instantanea = await repo.materialize_run_snapshot(corrida)
    # Lo que traía la instantánea de la corrida 27c62c96 en la QA: sin zona. Aquí la
    # hora se fijó en memoria y no pasó por SQLite, así que se pone a mano.
    instantanea["evaluated_at"] = "2026-10-10T00:52:18.887044"

    servido = EvaluationResultRead.model_validate(instantanea).model_dump(mode="json")

    assert datetime.fromisoformat(servido["evaluated_at"]) == datetime(
        2026, 10, 10, 0, 52, 18, 887044, tzinfo=UTC
    )


# ── Guardián: nadie escribe la hora local ────────────────────────────

BACKEND = Path(__file__).resolve().parents[1]
CARPETAS = ("api", "core", "db", "services", "chem", "scoring", "utils")
_HORA_LOCAL = re.compile(r"\b(?:datetime\.(?:now|today)\(\s*\)|date\.today\(\s*\)|datetime\.fromtimestamp\(\s*[^,()]+\))")


def _hora_local_en(fuente: str) -> list[str]:
    return [m.group(0) for m in _HORA_LOCAL.finditer(fuente)]


def test_el_guardian_ve_la_hora_local():
    muestra = (
        "a = datetime.now()\n"
        "b = datetime.now(UTC)\n"
        "c = date.today()\n"
        "d = datetime.fromtimestamp(t)\n"
        "e = datetime.fromtimestamp(t, tz=UTC)\n"
        "f = datetime.today()\n"
    )
    assert _hora_local_en(muestra) == [
        "datetime.now()", "date.today()", "datetime.fromtimestamp(t)", "datetime.today()",
    ]


def test_ningun_modulo_del_backend_escribe_la_hora_local():
    encontrados = []
    for carpeta in CARPETAS:
        for ruta in (BACKEND / carpeta).rglob("*.py"):
            if "tests" in ruta.parts:
                continue
            for hallazgo in _hora_local_en(ruta.read_text(encoding="utf-8", errors="replace")):
                encontrados.append(f"{ruta.relative_to(BACKEND)}: {hallazgo}")
    assert encontrados == []
