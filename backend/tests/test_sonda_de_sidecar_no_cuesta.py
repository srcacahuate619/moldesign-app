"""Preguntar qué motores hay no puede costar dos segundos.

═══════════════════════════════════════════════════════════════════════════
LO QUE PASÓ
═══════════════════════════════════════════════════════════════════════════

`MotorSidecar.estado()` era:

    return estado_de(self.motor, encendido=self.responde(), error=self._error)

Python evalúa los argumentos ANTES de llamar, así que `responde()` —una
petición HTTP a `127.0.0.1:8100` con `TIMEOUT_SONDA_S = 2.0`— corría en TODAS
las llamadas. Incluso cuando `estado_de` iba a devolver «no instalado» sin
mirar siquiera ese valor, porque los pesos no están descargados.

MEDIDO sobre el runtime empaquetado, con ESMFold sin descargar:

    inventario_de_motores()               2 022 ms
      estados_de_motores_descargables()     2 012 ms   <- la sonda
      archivos_que_faltan(esmfold)              0.8 ms
      dependencias_que_faltan(esmfold)          1.0 ms

Dos segundos clavados —el timeout— en cada apertura del panel de opciones y en
cada arranque de la interfaz. Y se pagaban justo donde más duele: una
instalación recién hecha nunca ha descargado los pesos, así que SIEMPRE
esperaba. La máquina del revisor de la Store, siempre. Tras la guarda: 18 ms.

Lo que estas pruebas fijan es la regla, no el número: **no se sondea un motor
que no puede estar vivo**, y **sí se sondea uno que sí puede**, porque la sonda
es lo único que autoriza a decir «listo».
"""

from __future__ import annotations

import time
from unittest.mock import patch

from services.motores import sidecar as mod


def _sidecar_de_esmfold():
    sc = mod.sidecar_de("esmfold")
    assert sc is not None, "el catálogo dejó de declarar el sidecar de esmfold"
    return sc


def test_sin_pesos_descargados_no_se_sondea():
    """La instalación recién hecha. Es el caso por defecto, no el raro."""
    sc = _sidecar_de_esmfold()
    with patch.object(mod, "archivos_que_faltan", return_value=["esmfold/models/pytorch_model.bin"]), \
         patch.object(sc, "responde", side_effect=AssertionError("no debería sondear")) as sonda:
        estado = sc.estado()
    assert sonda.call_count == 0
    assert estado.estado == "no_instalado"


def test_con_los_pesos_puestos_SI_se_sondea():
    """La sonda es lo único que autoriza a decir «listo». Saltársela por
    rapidez convertiría «descargado» en «funcionando», que no es lo mismo.

    Se parchea en los DOS módulos a propósito: la guarda nueva vive en
    `sidecar` y `estado_de` resuelve el suyo desde `catalogo`. Parchear sólo
    uno mediría media verdad.
    """
    from services.motores import catalogo

    sc = _sidecar_de_esmfold()
    with patch.object(mod, "archivos_que_faltan", return_value=[]), \
         patch.object(catalogo, "archivos_que_faltan", return_value=[]), \
         patch.object(catalogo, "dependencias_que_faltan", return_value=[]), \
         patch.object(sc, "responde", return_value=True) as sonda:
        estado = sc.estado()
    assert sonda.call_count == 1
    assert estado.disponible is True


def test_si_el_proceso_esta_vivo_se_sondea_aunque_falten_archivos():
    """Un proceso levantado manda sobre la comprobación de archivos: si está
    corriendo, lo que diga `/health` es la verdad."""
    sc = _sidecar_de_esmfold()
    with patch.object(mod, "archivos_que_faltan", return_value=["falta.bin"]), \
         patch.object(sc, "esta_vivo", return_value=True), \
         patch.object(sc, "responde", return_value=False) as sonda:
        sc.estado()
    assert sonda.call_count == 1


def test_el_inventario_completo_no_tarda_segundos():
    """La regla, en la unidad que el usuario nota.

    El umbral es deliberadamente flojo —medio segundo— porque esto corre en
    máquinas muy distintas y lo que se vigila es que no haya vuelto un timeout
    de red, no una décima de más. Medido: 2 022 ms antes, 18 ms después.
    """
    from api.routers.evaluation import inventario_de_motores

    inventario_de_motores()  # calentar imports
    t0 = time.perf_counter()
    inventario_de_motores()
    transcurrido = time.perf_counter() - t0

    assert transcurrido < 0.5, (
        f"el inventario de motores tardó {transcurrido * 1000:.0f} ms. "
        "Algo volvió a sondear por red un motor que no puede estar vivo."
    )


def test_el_contrato_sigue_diciendo_lo_mismo():
    """Acelerar no puede cambiar lo que se declara: mismos motores, mismas
    claves, y ESMFold sigue siendo una descarga bajo demanda."""
    from api.routers.evaluation import inventario_de_motores

    inventario = inventario_de_motores()
    assert set(inventario) == {"docking", "peptido"}

    por_id = {m["id"]: m for m in inventario["docking"] + inventario["peptido"]}
    assert por_id["vina"]["requiere"] == "binario_empaquetado"
    assert por_id["esmfold"]["requiere"] == "descarga_bajo_demanda"
    for motor in por_id.values():
        # `disponible` y `motivo` son el contrato con la interfaz: sin motivo,
        # un motor ausente no se puede explicar.
        assert "disponible" in motor
        assert motor["disponible"] or motor.get("motivo")
