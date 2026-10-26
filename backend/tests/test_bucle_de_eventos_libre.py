"""El backend sigue contestando mientras evalúa (2026-10-10).

Medido en una cápsula con el backend instrumentado: en la PRIMERA evaluación de cada sesión el bucle de eventos se
quedaba hasta 23 s sin atender nada —ni `/health`— y la interfaz, cuya comprobación de arranque espera 3 s por intento,
decía «El motor se desconectó». La segunda evaluación iba bien (`/health` máx. 235 ms): eran los imports pesados de la
primera vez, hechos en el hilo del bucle por código síncrono llamado desde funciones `async`:

* `cpu_efectivo_de_vina` llamaba a `detect_hardware()` entero (torch, pyopencl, openmm y 0,3 s de medida) para contar
  núcleos; y la estimación de la pestaña Evaluación también, al abrirla;
* XGBoost (`get_ml_rescore`) cargaba modelos e importaba scipy, xgboost, prolif y MDAnalysis;
* CL-GNN (`predict_clgnn`) importaba torch_geometric y cargaba el modelo.

Ahora lo caro va en un hilo (`asyncio.to_thread`) y Vina cuenta núcleos con `nucleos_logicos()`. Estas pruebas miden
el latido del bucle con lo caro simulado por un `time.sleep`, y un guardián impide volver a llamarlo a pelo desde `async`.
"""
from __future__ import annotations

import ast
import asyncio
import os
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

BACKEND = Path(__file__).resolve().parents[1]
LENTO_S = 0.6
HUECO_MAXIMO_S = 0.25


async def _con_latido(coro):
    """Ejecuta `coro` mientras un latido de 10 ms mide el hueco más largo del bucle de eventos."""
    huecos: list[float] = []
    parar = asyncio.Event()

    async def latido():
        ultimo = time.perf_counter()
        while not parar.is_set():
            await asyncio.sleep(0.01)
            ahora = time.perf_counter()
            huecos.append(ahora - ultimo)
            ultimo = ahora

    tarea = asyncio.create_task(latido())
    await asyncio.sleep(0.05)
    try:
        resultado = await coro
    finally:
        parar.set()
        await tarea
    return resultado, max(huecos)


def test_vina_cuenta_nucleos_sin_mirar_la_gpu(monkeypatch):
    """Para decidir los núcleos de Vina no se importa torch ni se mide nada: `detect_hardware` ni se llama."""
    import psutil

    from core import hardware
    from services.docking import vina_service

    def prohibido():
        raise AssertionError("cpu_efectivo_de_vina no debe llamar a detect_hardware")

    monkeypatch.setattr(hardware, "detect_hardware", prohibido)
    monkeypatch.setattr(vina_service.settings, "vina_cpu", 0)
    assert vina_service.cpu_efectivo_de_vina() == hardware.nucleos_logicos()
    assert hardware.nucleos_logicos() == (psutil.cpu_count(logical=True) or os.cpu_count())


def _hardware_lento():
    from core.hardware import HardwareInfo

    time.sleep(LENTO_S)
    return HardwareInfo(cpu_cores_physical=4, cpu_cores_logical=8)


@pytest.mark.parametrize("endpoint", ["estimar_esta_corrida", "hardware_info", "estimate_time"])
def test_los_endpoints_de_hardware_no_congelan_el_bucle(monkeypatch, endpoint):
    """La estimación de la pestaña Evaluación (y /hardware) detectaba el hardware en el bucle de eventos."""
    from api import main

    monkeypatch.setattr(main, "detect_hardware", _hardware_lento)
    llamadas = {
        "estimar_esta_corrida": lambda: main.estimar_esta_corrida(
            exhaustiveness=8, conformers=1, target_pdb_id=None, grid_size_x=20.0, grid_size_y=20.0,
            grid_size_z=20.0, rotables=None, anti_targets=0, mmgbsa=False, ligandos=1),
        "hardware_info": lambda: main.hardware_info(),
        "estimate_time": lambda: main.estimate_time(mode="pro", anti_targets=0, mmgbsa=False),
    }
    resultado, hueco = asyncio.run(_con_latido(llamadas[endpoint]()))
    assert resultado
    assert hueco < HUECO_MAXIMO_S, f"{endpoint}: el bucle estuvo {hueco:.2f} s sin atender"


def test_el_rescoring_ml_no_congela_el_bucle(monkeypatch):
    """XGBoost: comprobar el puente (carga modelos) y predecir son síncronos y caros; van en un hilo."""
    import services.rescoring_service as servicio
    from services.docking import rescoring_client

    def disponible_lento():
        time.sleep(LENTO_S)
        return True

    def prediccion_lenta(**_):
        time.sleep(LENTO_S)
        return {"fallback": False, "score_a": 7.0}

    monkeypatch.setattr(rescoring_client, "_DIRECT_BRIDGE_AVAILABLE", None)
    monkeypatch.setattr(servicio, "is_available", disponible_lento)
    monkeypatch.setattr(servicio, "predict_rescore", prediccion_lenta)
    propiedades = SimpleNamespace(molecular_weight=180.2, log_p=1.2, tpsa=63.6, hbd=1, hba=4, rotatable_bonds=3, qed=0.55)
    resultado, hueco = asyncio.run(_con_latido(rescoring_client.get_ml_rescore(
        smiles="CC(=O)Oc1ccccc1C(=O)O", target_pdb_path="x.pdb",
        poses=[{"affinity": -6.0, "pdbqt_block": ""}], properties=propiedades)))
    assert resultado == {"fallback": False, "score_a": 7.0}
    assert hueco < HUECO_MAXIMO_S, f"el bucle estuvo {hueco:.2f} s sin atender"


def test_la_comprobacion_previa_no_congela_el_bucle_al_consultar_las_plantillas(monkeypatch):
    """La comprobación previa consulta las plantillas de Meeko (la regla de prepare_target, 2026-10-11).

    La primera consulta importa meeko: 3,35 s en frío con el backend ya arrancado. `build_preflight` es síncrono y
    la ruta lo llama desde `async`, así que la caché se llena antes, en un hilo; después la consulta es inmediata.
    """
    from api.routers import evaluation
    from services.docking import preflight, preparer

    llena: list[bool] = []

    def plantillas_lentas():
        if not llena:
            time.sleep(LENTO_S)
            llena.append(True)
        return frozenset()

    def informe(**_):
        preparer.residuos_con_plantilla()
        return {"input_fingerprint": "sha256:" + "0" * 64, "technical_blockers": [], "warnings": [],
                "not_evaluated": []}

    async def sin_receptor(*_, **__):
        return None

    monkeypatch.setattr(preparer, "residuos_con_plantilla", plantillas_lentas)
    monkeypatch.setattr(preflight, "build_preflight", informe)
    monkeypatch.setattr(evaluation, "get_target_for_user", sin_receptor)
    resultado, hueco = asyncio.run(_con_latido(evaluation.evaluation_preflight(
        data=evaluation.PreflightRequest(smiles="CCO", target_pdb_id="1ABC"), db=None, current_user=None)))
    assert resultado["technical_blockers"] == []
    assert llena, "la consulta lenta no se ejecutó: la prueba no mediría nada"
    assert hueco < HUECO_MAXIMO_S, f"el bucle estuvo {hueco:.2f} s sin atender"


class _RegistroLento:
    """Un registro de proveedores cuyo recorrido tarda: lo que pasaba con Ollama sin instalar."""

    def list_providers(self, *_, **__):
        time.sleep(LENTO_S)
        return []

    def get_active_info(self, *_, **__):
        time.sleep(LENTO_S)
        return None


@pytest.mark.parametrize("endpoint", ["list_providers", "listar_consentimientos"])
def test_molchat_al_abrir_la_app_no_congela_el_bucle(monkeypatch, endpoint):
    """Al abrir la app, MolChat pide /ai/providers y /ai/consent: recorrían los proveedores en el bucle de eventos."""
    from api.routers import ai

    monkeypatch.setattr(ai, "_bootstrap_providers", lambda: None)
    monkeypatch.setattr(ai, "_bootstrap_tools", lambda: None)
    monkeypatch.setattr(ai, "get_provider_registry", lambda: _RegistroLento())

    def destinos_lentos(registro, *_, **__):
        return registro.list_providers()

    monkeypatch.setattr(ai.consent, "estado_de_destinos", destinos_lentos)
    usuario = SimpleNamespace(id="00000000-0000-0000-0000-000000000001", is_superuser=False)
    llamadas = {
        "list_providers": lambda: ai.list_providers(current_user=None),
        "listar_consentimientos": lambda: ai.listar_consentimientos(current_user=usuario),
    }
    _, hueco = asyncio.run(_con_latido(llamadas[endpoint]()))
    assert hueco < HUECO_MAXIMO_S, f"{endpoint}: el bucle estuvo {hueco:.2f} s sin atender"


def test_el_sondeo_de_ollama_se_reutiliza_y_no_espera_a_conectar(monkeypatch):
    """Sin Ollama, cada sondeo tardaba 4,4 s (localhost) y la app lo pedía varias veces al abrirse."""
    from services.ai.providers import ollama_provider as op
    from services.ai.providers.base import ProviderConfig

    pedidos = []

    def get(url, timeout):
        pedidos.append((url, timeout))
        raise op.httpx.ConnectError("rechazada")

    monkeypatch.setattr(op, "_sondeos", {})
    monkeypatch.setattr(op.httpx, "get", get)
    proveedor = op.OllamaProvider(config=ProviderConfig(base_url="http://localhost:11434"))
    assert proveedor.get_info().available_models == []
    assert proveedor.validate_config()[0] is False
    assert proveedor.get_info().configured is False
    assert len(pedidos) == 1, "tres consultas seguidas: un solo sondeo"
    assert pedidos[0][1].connect <= 0.5


# ── Guardián: lo caro no se llama a pelo desde código `async` ─────────────────────────────────────────────────

CARAS = frozenset({
    "detect_hardware", "predict_clgnn", "predict_rescore", "_is_direct_available",
    # Sondean proveedores de IA por red (Ollama en localhost: 4,4 s por intento sin Ollama instalado, medido):
    "list_providers", "get_active_info", "estado_de_destinos",
    # Lee y analiza el PDB de cada receptor del catálogo:
    "get_residue_coordinates",
    # Interacciones proteína-ligando de una pose (segundos con un receptor grande):
    "analyze_complex",
})
VIGILADOS = ("api", "services", "core")


def llamadas_caras_en_async(fuente: str) -> list[tuple[int, str]]:
    """Llamadas directas a funciones caras dentro de un `async def` (sin entrar en `def` anidados, que pueden ir a un
    hilo). `asyncio.to_thread(detect_hardware)` no es una llamada a `detect_hardware`: la función va como argumento."""
    encontradas: list[tuple[int, str]] = []

    def recorrer(nodo: ast.AST) -> None:
        for hijo in ast.iter_child_nodes(nodo):
            if isinstance(hijo, (ast.FunctionDef, ast.Lambda, ast.ClassDef)):
                continue
            if isinstance(hijo, ast.Call):
                nombre = hijo.func.id if isinstance(hijo.func, ast.Name) else (
                    hijo.func.attr if isinstance(hijo.func, ast.Attribute) else None)
                if nombre in CARAS:
                    encontradas.append((hijo.lineno, nombre))
            recorrer(hijo)

    for nodo in ast.walk(ast.parse(fuente)):
        if isinstance(nodo, ast.AsyncFunctionDef):
            recorrer(nodo)
    return sorted(set(encontradas))


def test_el_guardian_ve_lo_que_debe_y_nada_mas():
    """Autotest: un guardián tiene que demostrar que ve (AGENTS.md, restricción 2)."""
    assert llamadas_caras_en_async("async def f():\n    return detect_hardware()\n") == [(2, "detect_hardware")]
    assert llamadas_caras_en_async("async def f():\n    x = rescoring.predict_rescore(a=1)\n") == [(2, "predict_rescore")]
    assert llamadas_caras_en_async("async def f():\n    if _is_direct_available():\n        pass\n") == [(2, "_is_direct_available")]
    assert llamadas_caras_en_async("async def f():\n    async def g():\n        predict_clgnn(1)\n") == [(3, "predict_clgnn")]
    assert llamadas_caras_en_async("async def f():\n    return await asyncio.to_thread(detect_hardware)\n") == []
    assert llamadas_caras_en_async("async def f():\n    await asyncio.to_thread(predict_rescore, a=1)\n") == []
    assert llamadas_caras_en_async("def f():\n    return detect_hardware()\n") == []
    assert llamadas_caras_en_async("async def f():\n    def g():\n        return detect_hardware()\n") == []


def test_ningun_async_llama_a_pelo_a_lo_caro():
    archivos = [p for carpeta in VIGILADOS for p in (BACKEND / carpeta).rglob("*.py") if "__pycache__" not in p.parts]
    assert len(archivos) > 100
    culpables = []
    for archivo in archivos:
        for linea, nombre in llamadas_caras_en_async(archivo.read_text(encoding="utf-8")):
            culpables.append(f"{archivo.relative_to(BACKEND)}:{linea} {nombre}()")
    assert culpables == [], "Desde `async`, en un hilo (asyncio.to_thread): " + ", ".join(culpables)
