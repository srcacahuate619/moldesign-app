"""Los dos ejecutores tienen que sellar qué especie se acopló.

Auditoría de backend del 2026-09-04, §3.1: el backend tiene dos motores de
pipeline en paralelo —`services/docking/queue_handler.py` para el modo normal y
`services/pipeline/runner.py` para el modo PRO— y la consecuencia que la
auditoría predice es que una corrección hecha en uno no llega al otro.

Es exactamente lo que pasó dos veces seguidas:

* `docking_protocol` sólo lo escribía el runner PRO; en modo normal la columna
  quedaba NULL sin error (arreglado el 2026-09-03).
* `ligand_state` sólo lo escribía `queue_handler`; en modo PRO la columna
  quedaba NULL sin error, así que el dossier de una corrida PRO no podía decir
  qué tautómero ni qué microestado de protonación se acoplaron. Arreglado aquí.

Las dos veces el fallo fue silencioso —una columna nullable que nadie rellena no
levanta ninguna excepción— y las dos veces apareció leyendo el código a mano.
Esta prueba es la red para la tercera, mientras los dos ejecutores sigan siendo
dos. Es una comprobación estática a propósito: recorrer los dos caminos de punta
a punta exige Vina y un receptor preparado, y esta clase de olvido se ve sin
ejecutar nada.
"""

from __future__ import annotations

from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
QUEUE_HANDLER = BACKEND / "services" / "docking" / "queue_handler.py"
RUNNER = BACKEND / "services" / "pipeline" / "runner.py"

# Campos que describen CÓMO se ejecutó la corrida y que el dossier lee. No son
# resultados: son la procedencia, y por eso un NULL aquí no se nota hasta que
# alguien abre el dossier y falta.
CAMPOS_DE_PROCEDENCIA = ("docking_protocol", "ligand_state")


@pytest.mark.parametrize("campo", CAMPOS_DE_PROCEDENCIA)
@pytest.mark.parametrize(
    "ruta", [QUEUE_HANDLER, RUNNER], ids=["queue_handler", "runner_pro"]
)
def test_los_dos_ejecutores_escriben_cada_campo_de_procedencia(campo: str, ruta: Path):
    fuente = ruta.read_text(encoding="utf-8")
    assert f"{campo}=" in fuente, (
        f"{ruta.name} no pasa `{campo}` al upsert. Es una columna nullable: no "
        "va a fallar, simplemente quedará vacía y el dossier de las corridas de "
        "este camino no podrá decirlo. Ver el docstring de este módulo."
    )


def test_el_repositorio_sigue_aceptando_los_dos_campos():
    """Si el upsert deja de aceptarlos, la prueba de arriba pasa en falso."""
    import inspect

    from db.repository import Repository

    firma = inspect.signature(Repository.upsert_evaluation_result)
    for campo in CAMPOS_DE_PROCEDENCIA:
        assert campo in firma.parameters, (
            f"upsert_evaluation_result ya no acepta `{campo}`: las comprobaciones "
            "de arriba estarían mirando un argumento que nadie recibe."
        )
