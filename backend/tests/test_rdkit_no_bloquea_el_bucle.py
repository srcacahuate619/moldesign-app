"""Qué parte del trabajo pesado deja respirar al bucle de eventos, medida.

Auditoría de backend del 2026-09-04, §3.3: varios endpoints `async def` llamaban
a RDKit —y `/chem/properties` al ensamble de ADMET-AI— sin un solo punto de
suspensión. Un `async def` que no cede el control bloquea el bucle entero:
mientras calcula, FastAPI no atiende nada más, incluido el sondeo con el que el
frontend dibuja el progreso de una corrida.

El trabajo se movió a `run_in_threadpool` en cinco sitios: `chem/conformer.py`,
`/chem/validate`, `/chem/properties`, `/chem/render/{id}` y `/sar/{id}`.

═══════════════════════════════════════════════════════════════════════════
LO QUE LA MEDICIÓN DIJO, Y QUE NO ES LO QUE LA AUDITORÍA SUPONÍA
═══════════════════════════════════════════════════════════════════════════

Mover trabajo a un hilo no garantiza que el bucle recupere TODO su tiempo: lo
que el trabajo pase reteniendo el GIL, el hilo del bucle lo sigue esperando.
Contando latidos de una tarea que despierta cada 10 ms, en esta máquina:

    trabajo                       duración   latidos   latidos si cediera
    ────────────────────────────────────────────────────────────────────
    conformer, en el bucle           312 ms       0            31
    conformer, en el pool            312 ms      17            31   <- arreglado
    calculate_properties, bucle      476 ms       0            47
    calculate_properties, pool    510-590 ms   11-13         51-58   <- parcial
    240 huellas Morgan (SAR), pool    41 ms       0             4
    60 SVG 2D, pool                   91 ms       2             9

ETKDG y MMFF94 sueltan el GIL: sacar `generate_conformer` del hilo async es una
mejora real y medida, y era además el caso más engañoso, porque era `async def`
con un único `await` al final y *parecía* que cedía.

CORRECCIÓN DE LA PRIMERA MEDICIÓN. La versión anterior de este archivo decía
que `calculate_properties` pasaba «de 0 latidos a 1» y concluía que el arreglo
**no** servía para ADMET. Esa cifra salió de UNA sola medida, tomada justo
después de cargar el modelo, y no se repitió. Medido después ocho veces
seguidas: 11-13 latidos, mediana 11.5. El bucle sí queda vivo.

Lo que sigue siendo cierto es que no recupera todo: ~11 de ~52 posibles, porque
ADMET-AI corre sobre torch y lightning y buena parte de ese tiempo está en
Python con el GIL tomado. Es una mejora sustancial y una limitación parcial, no
un arreglo que no funciona. Sacar ADMET a un subproceso lo cerraría del todo,
y es otra conversación.

Las rutas de SAR y del SVG resultaron no ser el problema que la auditoría
suponía: 240 huellas son 41 ms y 60 dibujos son 91 ms. El cambio se conserva
porque es gratis y porque el coste crece con el tamaño de la serie, no porque
midiera algo hoy.
"""

from __future__ import annotations

import asyncio

import pytest

# Margen deliberadamente holgado: se comprueba la diferencia entre «el bucle
# sigue vivo» y «el bucle está muerto» —cero latidos frente a decenas—, no
# rendimiento. Una máquina de CI cargada no debe volver esto inestable.
LATIDOS_MINIMOS = 3
PERIODO_LATIDO_S = 0.01


async def _latidos_durante(corutina):
    """Ejecuta `corutina` contando cuántas veces late el bucle mientras tanto."""
    latidos = 0

    async def latir() -> None:
        nonlocal latidos
        while True:
            await asyncio.sleep(PERIODO_LATIDO_S)
            latidos += 1

    tarea = asyncio.create_task(latir())
    try:
        resultado = await corutina
    finally:
        tarea.cancel()
        try:
            await tarea
        except asyncio.CancelledError:
            pass
    return resultado, latidos


@pytest.mark.asyncio
async def test_generate_conformer_deja_respirar_al_bucle():
    """El caso que sí se arregló, y el que más engañaba."""
    from chem.conformer import generate_conformer

    # Un dipéptido: ETKDG + MMFF tardan lo suficiente para que se note.
    resultado, latidos = await _latidos_durante(
        generate_conformer("CC(C)C[C@H](NC(=O)[C@@H](N)Cc1ccccc1)C(O)=O")
    )

    assert resultado["num_atoms_3d"] > 0, "el conformer dejó de generarse"
    assert latidos >= LATIDOS_MINIMOS, (
        f"El bucle latió {latidos} veces mientras se generaba el conformer, "
        "cuando antes del arreglo eran 0 y con el pool de hilos fueron 17. "
        "RDKit volvió al hilo async: usa run_in_threadpool."
    )


@pytest.mark.asyncio
async def test_el_cuerpo_sincrono_del_conformer_es_llamable_sin_bucle():
    """La contrapartida: el trabajo pesado se puede probar sin montar una app."""
    from chem.conformer import _construir_conformero

    datos = _construir_conformero("CC(=O)Oc1ccccc1C(=O)O")
    assert datos["num_atoms_3d"] > 0
    assert datos["sdf_content"].strip(), "el SDF salió vacío"
    # La ruta la decide el envoltorio, que es quien escribe: el cuerpo no la fija.
    assert "conformer_path" not in datos


@pytest.mark.asyncio
async def test_generate_conformer_devuelve_lo_mismo_que_antes_del_troceado():
    """Partir la función en dos no puede haber cambiado su contrato."""
    from chem.conformer import generate_conformer

    resultado = await generate_conformer("CC(=O)Oc1ccccc1C(=O)O")
    esperadas = {
        "canonical_smiles",
        "smiles_hash",
        "conformer_path",
        "num_atoms_3d",
        "optimization_converged",
        "had_macrocycle",
        "molecular_formula",
        "sdf_content",
        "estado_del_ligando",
    }
    assert esperadas <= set(resultado), (
        f"Faltan claves en el resultado: {sorted(esperadas - set(resultado))}"
    )
    assert resultado["conformer_path"].endswith("conformer.sdf")
    assert resultado["smiles_hash"] in resultado["conformer_path"], (
        "la ruta dejó de derivarse del hash post-protonación"
    )


@pytest.mark.asyncio
async def test_calcular_propiedades_deja_respirar_al_bucle():
    """El caso caro: ADMET-AI sobre torch, dentro de un endpoint `async def`.

    Cede menos de lo ideal —unos 11 latidos de ~52, porque torch retiene el GIL
    buena parte del cálculo— pero el bucle queda vivo, que es la diferencia
    entre una interfaz que va lenta y una que parece colgada. Se compara contra
    el mismo umbral holgado que el resto: lo que se comprueba es «vivo» frente
    a «muerto», no rendimiento.
    """
    from starlette.concurrency import run_in_threadpool

    from chem.properties import calculate_properties

    smiles = "CC(=O)Oc1ccccc1C(=O)O"
    # Primera pasada fuera de la medición: carga de modelos, que ocurre una vez
    # y fue la que dio la cifra atípica que este archivo llegó a documentar.
    await run_in_threadpool(calculate_properties, smiles)

    props, latidos = await _latidos_durante(
        run_in_threadpool(calculate_properties, smiles)
    )

    assert props.molecular_weight > 0, "las propiedades dejaron de calcularse"
    assert latidos >= LATIDOS_MINIMOS, (
        f"El bucle latió {latidos} veces durante calculate_properties, cuando "
        "en el hilo del bucle son 0 y en el pool fueron 11-13 sobre ocho "
        "medidas. El endpoint /chem/properties tiene que envolverla en "
        "run_in_threadpool."
    )


@pytest.mark.asyncio
async def test_el_ensemble_conformacional_deja_respirar_al_bucle(monkeypatch, tmp_path):
    """
    El caso que la auditoría del ensemble dejó abierto (ENS-05), medido.

    `generate_conformer_ensemble` delegaba en `generate_conformer` para la
    conformación 0 —que sí cede— y embebía las K-1 restantes DENTRO de la
    corrutina. El resultado: los únicos latidos de toda la etapa eran los de la
    conformación 0, y el resto del ensemble dejaba el bucle muerto. Medido con
    un dipéptido, tres corridas por celda:

        K    duración    antes        después
        8     ~452 ms    5 / 44-45    29-30 / 45
       16     ~870 ms    4 / 85-86    56-58 / 86-88

    El umbral es holgado a propósito: comprueba «vivo» frente a «muerto». Con
    K=8, «antes» daba exactamente los mismos 5 latidos que K=1, que es la firma
    del defecto —añadir siete conformaciones no añadía un solo punto de
    suspensión—.
    """
    import utils.local_storage as ls
    from chem.conformer_ensemble import generate_conformer_ensemble

    monkeypatch.setattr(ls.settings, "local_data_dir", str(tmp_path / "data"))

    smiles = "CC(C)C[C@H](NC(=O)[C@@H](N)Cc1ccccc1)C(O)=O"
    # Fuera de la medición: la primera importación de RDKit y el arranque del
    # pool de hilos, que ocurren una vez.
    await generate_conformer_ensemble(smiles, 1)

    resultado, latidos = await _latidos_durante(
        generate_conformer_ensemble(smiles, 8)
    )

    assert resultado["conformers_generated"] > 1, "el ensemble dejó de generarse"
    assert latidos >= 2 * LATIDOS_MINIMOS, (
        f"El bucle latió {latidos} veces generando ocho conformaciones, cuando "
        "antes del arreglo eran 5 —los mismos que con K=1— y con el pool de "
        "hilos fueron 29-30 de 45 posibles. El embebido de RDKit volvió al hilo "
        "del bucle: usa run_in_threadpool en cada conformación."
    )
