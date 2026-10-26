"""Los instantes que salen de la API llevan su zona: UTC, escrita.

SQLite no guarda la zona. `CURRENT_TIMESTAMP` (el `server_default=func.now()` de los
modelos) escribe UTC sin offset, y SQLAlchemy descarta el `tzinfo` de
`datetime.now(UTC)` al guardarlo. Al leer, todo instante es UTC sin zona, y su
`isoformat()` (`2026-10-10T00:52:18.887044`) lo toma el navegador por hora LOCAL:
el Historial enseñaba cada corrida seis horas adelantada en Ciudad de México (B03 de
la QA de release de 1.0.2). Que todo se escribe en UTC no es un supuesto: ningún
módulo del backend usa la hora local (`test_instantes_con_zona.py` lo vigila).

Las cohortes ya reponían la zona con su propio `_iso`; esto es lo mismo, compartido.
"""
from __future__ import annotations

from datetime import UTC, datetime


def en_utc(valor: datetime) -> datetime:
    """El mismo instante, con su zona: un `datetime` sin zona del backend es UTC."""
    if valor.tzinfo is None:
        return valor.replace(tzinfo=UTC)
    return valor.astimezone(UTC)


def instante_utc(valor: datetime | str | None) -> str | None:
    """ISO 8601 con offset UTC, o `None`.

    Acepta también la cadena ya serializada que guardan las instantáneas de una
    corrida (`snapshot_json`), que se escribió sin zona y no se reescribe. Una cadena
    que no es un instante se devuelve tal cual: no se inventa una fecha.
    """
    if valor is None or valor == "":
        return None
    if isinstance(valor, str):
        try:
            valor = datetime.fromisoformat(valor)
        except ValueError:
            return valor
    return en_utc(valor).isoformat()
