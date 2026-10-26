"""Molcy como programa externo, bajo demanda y fuera del arranque."""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import subprocess
import sys
import threading
import time
import shutil
from contextlib import contextmanager
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from core.config import get_settings
from services.molcy import presentacion as receta_visual
from utils.local_storage import data_dir
from utils.procesos import BANDERAS_SIN_VENTANA
from utils.windows_paths import ruta_para_programa
from . import autodeteccion, cierre, cpu, disk, gpu, installation, motor, storage
from .process import carpeta_de_proceso, run_owned
from .python_auxiliar import python_auxiliar

_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="molcy-render")
_futures: dict[str, Any] = {}
_lock = threading.RLock()
_cancel_events: dict[str, threading.Event] = {}
_processes: dict[str, Any] = {}
_reserved: set[str] = set()
#: Intentos de `os.replace` sobre `estado.json` si otro hilo lo tiene abierto (Windows): ~2 s en total.
ESTADO_REINTENTOS = 20
_ultima_capacidad: dict[str, Any] = {}
#: Un sondeo lanza Blender DOS veces (Cycles CPU y EEVEE; 7-11 s en caliente, ~49 s cuando dos sondeos coinciden en frío) y la
#: página lo pedía al cargar, al cambiar de idioma y otra vez al pulsar «Generar». Sólo un sondeo a la vez y, si salió bien y
#: nada de lo que lo determina cambió, se reutiliza. Un resultado NEGATIVO no se guarda: quien ve «falta Molecular Nodes» está
#: arreglándolo y el siguiente sondeo tiene que ver el arreglo.
CACHE_SONDEO_S = 600.0
#: El motor sólo se ha ejecutado en Blender 5.2.2. Medido el 2026-10-04 con las últimas LTS: en 4.2.23 la plantilla de arte (guardada
#: con 5.2) ni se abre («not a blend file») y en 4.5.14, con Molecular Nodes 4.5.11, el motor aborta su propio control de calidad
#: («el radio de las dianas es el 348 % de la distancia») y el motor EEVEE de 4.x se llama distinto, así que la GPU no se ofrece.
VERSION_MINIMA_BLENDER = (5, 2)
_sondeo_lock = threading.Lock()
_sondeo_guardado: dict[str, Any] = {}
#: Los tipos de dispositivo de Cycles, en el orden en que los prueba el motor (`scripts/foto.py`): el que se anuncia es el que se usará.
TIPOS_GPU_CYCLES = ("CUDA", "OPTIX", "HIP", "ONEAPI", "METAL")
#: Segundo sondeo, sin Molecular Nodes: EEVEE (el vídeo) y Cycles en GPU (las fotos), cada uno con un render de 8×8. Encontrar una GPU
#: no basta: se rinde con ella, o una GPU cuyos núcleos no cargan se anunciaría como disponible. Un fallo de una parte no tapa la otra.
SONDEO_GPU = "\n".join([
    "import bpy, gpu, json",
    "sc = bpy.context.scene",
    "sc.render.resolution_x = 8; sc.render.resolution_y = 8; sc.render.resolution_percentage = 100",
    "try:",
    "    sc.render.engine = 'BLENDER_EEVEE'; bpy.ops.render.render()",
    "    print('MOLCY_EEVEE_OK', flush=True)",
    "    print('MOLCY_GPU:' + json.dumps({'gpu_vendor': gpu.platform.vendor_get(), 'gpu_nombre': gpu.platform.renderer_get()}), flush=True)",
    "except Exception as exc:",
    "    print('MOLCY_EEVEE_FALLO:' + type(exc).__name__, flush=True)",
    "try:",
    "    prefs = bpy.context.preferences.addons['cycles'].preferences",
    f"    for tipo in {TIPOS_GPU_CYCLES!r}:",
    "        try:",
    "            prefs.compute_device_type = tipo",
    "        except TypeError:",
    "            continue",
    "        prefs.get_devices_for_type(tipo)",
    "        gpus = [d for d in prefs.devices if d.type == tipo]",
    "        if not gpus:",
    "            continue",
    "        for d in prefs.devices:",
    "            d.use = d.type == tipo",
    "        sc.render.engine = 'CYCLES'; sc.cycles.device = 'GPU'; sc.cycles.samples = 1; sc.cycles.use_denoising = False",
    "        bpy.ops.render.render()",
    "        print('MOLCY_CYCLES_GPU:' + json.dumps({'tipo': tipo, 'nombres': [d.name for d in gpus]}), flush=True)",
    "        break",
    "except Exception as exc:",
    "    print('MOLCY_CYCLES_GPU_FALLO:' + type(exc).__name__, flush=True)",
])


def motor_con_fotos(engine: Path) -> bool:
    """El motor sabe tomar fotos: su lanzador, su script de Blender y el modo `--fotos` del maestro."""
    scripts = engine / "scripts"
    try:
        return ((scripts / "correr_foto.py").is_file() and (scripts / "foto.py").is_file()
                and '"--fotos"' in (scripts / "maestro.py").read_text(encoding="utf-8"))
    except OSError:
        return False


def sha256_archivo(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _blender_candidatos() -> list[Path]:
    user_settings = installation.settings()
    managed = installation.blender_path()
    if user_settings.get("modo") == "administrado":
        return [managed] if managed else []
    if user_settings.get("modo") == "existente":
        return [Path(user_settings["blender"])] if user_settings.get("blender") else []
    if managed and managed.is_file():
        return [managed]
    cfg = get_settings().molcy_blender_path
    if cfg:
        return [Path(cfg)]
    return [c.ruta for c in autodeteccion.preferidos(VERSION_MINIMA_BLENDER)]


def motor_elegido() -> tuple[Path, str]:
    """(carpeta, origen) del motor Molcy: el que viaja con MolDesign o, sólo con `motor_propio_permitido()`, el que fijó la configuración o
    `MOLCY_ENGINE_DIR` (un desarrollador). Origen: «incluido», «configurado» o «ninguno». Nada se adivina: sin ninguno, no hay motor."""
    if motor.motor_propio_permitido():
        fijado = installation.settings().get("motor")
        if fijado:
            return Path(fijado), "configurado"
        ajuste = get_settings().molcy_engine_dir
        if ajuste:
            return Path(ajuste), "configurado"
    incluido = motor.directorio_incluido()
    if incluido is not None:
        return incluido, "incluido"
    return Path(""), "ninguno"


def busqueda_disponible() -> bool:
    """Capability declared by the committed motor source, without importing it."""
    engine, origen = motor_elegido()
    if origen != "incluido" or motor.verificar_integridad(engine):
        return False
    return "vina_monte_carlo_bfgs_interno" in (engine / "scripts/sujetos/busqueda_montecarlo.py").read_text(encoding="utf-8")


#: Las escenas que cuentan una película propia fijan su guion; el resto (resultado,
#: receptor) usa `sitio_activo` con el sujeto que corresponda.
GUION_DE_SUJETO = {"busqueda_montecarlo": "x", "ensamble_conformacional": "y"}


def ensamble_disponible() -> bool:
    """El motor incluido trae la escena Ensamble (guion `y` y su sujeto), sin importarlo.

    Un motor anterior sólo tenía un hueco declarado (`poses_ensamble`): lanzar la
    escena contra él fallaría tarde y en Blender, así que se comprueba antes.
    """
    engine, origen = motor_elegido()
    if origen != "incluido" or motor.verificar_integridad(engine):
        return False
    return all((engine / "scripts" / ruta).is_file()
               for ruta in ("guiones/y.py", "sujetos/ensamble_conformacional.py"))


def _firma(path: Path) -> tuple[int, int] | None:
    try:
        stat = path.stat()
    except OSError:
        return None
    return (stat.st_size, stat.st_mtime_ns)


def _procedencia_del_motor(engine: Path, origen: str) -> dict[str, Any]:
    """Quién es el motor que se va a ejecutar: de dónde viene y, si viaja con MolDesign, su commit y su licencia."""
    datos: dict[str, Any] = {"motor_origen": origen}
    if origen == "incluido":
        manifiesto = motor.manifiesto_de(engine)
        datos.update(motor_commit=(manifiesto.get("fuente") or {}).get("commit"),
                     motor_licencia=manifiesto.get("licencia_spdx"))
    return datos


def _clave_de_sondeo() -> tuple:
    """Lo que, si cambia, obliga a lanzar Blender otra vez: el ejecutable elegido y el código y la plantilla del motor.

    Se ignoran `__pycache__` y todo lo que no sea código del motor: Blender escribe bytecode al ejecutarlo y eso no es un cambio.
    """
    blender = next((p.resolve() for p in _blender_candidatos() if p.is_absolute() and p.is_file()), None)
    engine, origen = motor_elegido()
    ficheros: list[tuple[str, tuple[int, int] | None]] = []
    if engine.is_absolute() and engine.is_dir():
        for path in sorted(engine.rglob("*")):
            relativa = path.relative_to(engine)
            if "__pycache__" in relativa.parts or not path.is_file():
                continue
            # El motor que viaja es pequeño (~2 MB) y su integridad se comprueba entera: cualquier fichero cuenta. Una carpeta del
            # desarrollador puede traer GB de casos y vídeos: ahí sólo el código y la plantilla.
            if (origen == "incluido" or relativa.parts[:1] == ("scripts",) and path.suffix in {".py", ".ps1"}
                    or path.name == "plantilla_arte.blend"):
                ficheros.append((relativa.as_posix(), _firma(path)))
    return (str(blender) if blender else None, _firma(blender) if blender else None, str(engine), tuple(ficheros))


def invalidar() -> None:
    """Olvida el último sondeo bueno y lo hallado en disco (configuración cambiada, instalación terminada…)."""
    autodeteccion.invalidar()
    with _sondeo_lock:
        _sondeo_guardado.clear()


def detectar(*, forzar: bool = False) -> dict[str, Any]:
    """Capacidad del renderizador. `forzar` (botón «Comprobar», fin de una instalación) ignora la caché."""
    if forzar:
        autodeteccion.invalidar()  # «Comprobar» vuelve a mirar el disco: el usuario acaba de instalar o mover Blender
    with _sondeo_lock:
        clave = _clave_de_sondeo()
        vigente = (not forzar and _sondeo_guardado.get("clave") == clave
                   and time.monotonic() - _sondeo_guardado["t"] < CACHE_SONDEO_S)
        if vigente:
            result = dict(_sondeo_guardado["resultado"])
        else:
            result = _detectar()
            _sondeo_guardado.clear()
            if result.get("disponible"):
                _sondeo_guardado.update(clave=clave, t=time.monotonic(), resultado=dict(result))
    result = {**result, "motor_incluido": motor.directorio_incluido() is not None,
              "blenders_encontrados": autodeteccion.para_la_pantalla(autodeteccion.listar(), VERSION_MINIMA_BLENDER)}
    with _lock:
        _ultima_capacidad.clear()
        _ultima_capacidad.update(result)
    return result


def capacidad_estimada() -> dict[str, Any]:
    """Usa la última comprobación explícita, sin sondear Blender por cada ajuste."""
    with _lock:
        return dict(_ultima_capacidad)


def _detectar() -> dict[str, Any]:
    """No afirma disponibilidad hasta comprobar Blender, addon y adaptador."""
    blender = next((p.resolve() for p in _blender_candidatos() if p.is_absolute() and p.is_file()), None)
    if blender is None:
        # Con su código, como las demás razones: el menú de Descargas lo lee para ofrecer «Descargar e instalar». Sin él caía
        # en «Molcy no puede usar esta instalación» (2026-10-10; la interfaz ya lo esperaba en su tipo y nadie lo enviaba).
        return {"disponible": False, "motivo_codigo": "falta_blender",
                "motivo": "No se encontró Blender. Descárgalo desde la configuración de abajo o elige tu blender.exe."}
    engine, origen = motor_elegido()
    if not engine.is_absolute() or not engine.is_dir():
        return {"disponible": False, "motivo": "No se encontró el motor Molcy. Elige su carpeta en la configuración de abajo.",
                "blender": str(blender)}
    engine = engine.resolve()
    if origen == "incluido":
        # El motor que viaja se ejecuta sólo si es el que se distribuyó: un fichero alterado daría un vídeo cuya procedencia
        # no sería la declarada. No se repara: se abstiene y dice qué hacer.
        problemas = motor.verificar_integridad(engine)
        if problemas:
            return {"disponible": False, "motivo_codigo": "motor_alterado",
                    "motivo": "El motor Molcy incluido en MolDesign está dañado o fue modificado. Reinstala MolDesign.",
                    "blender": str(blender), "motor": str(engine), "motor_origen": origen, "motor_problemas": problemas[:10]}
    maestro = engine / "scripts" / "maestro.py"
    runner = engine / "scripts" / "correr_caso.ps1"
    arte = engine / "moldesign" / "assets" / "blender" / "plantilla_arte.blend"
    if not all(p.is_file() for p in (maestro, runner, arte)):
        return {"disponible": False, "motivo": "La carpeta del motor Molcy está incompleta: faltan scripts/maestro.py, scripts/correr_caso.ps1 o la plantilla de arte.",
                "blender": str(blender), "motor": str(engine)}
    if "MOLCY_OUTPUT_DIR" not in maestro.read_text(encoding="utf-8") or "Sujeto" not in runner.read_text(encoding="utf-8"):
        return {"disponible": False, "motivo": "Esta versión de Molcy no admite paquetes de corrida.",
                "blender": str(blender), "motor": str(engine)}
    probe = (
        "import bpy,json,pathlib,tomllib; "
        "print('MOLCY_BLENDER_VERSION:'+json.dumps(list(bpy.app.version)),flush=True); "
        "import bl_ext.blender_org.molecularnodes as mn; "
        "manifest=pathlib.Path(mn.__file__).parent/'blender_manifest.toml'; "
        "version=tomllib.loads(manifest.read_text(encoding='utf-8'))['version']; "
        "print('MOLCY_CAPS:'+json.dumps({'version':list(bpy.app.version),"
        "'molecular_nodes':version}),flush=True); "
        "sc=bpy.context.scene; sc.render.engine='CYCLES'; sc.cycles.device='CPU'; "
        "sc.cycles.samples=1; sc.render.resolution_x=8; sc.render.resolution_y=8; "
        "sc.render.resolution_percentage=100; bpy.ops.render.render(); "
        "print('MOLCY_CPU_OK',flush=True)"
    )
    try:
        result = subprocess.run(
            [str(blender), "-b", "--factory-startup", "--addons",
             "bl_ext.blender_org.molecularnodes", "--python-exit-code", "1",
             "--python-expr", probe], capture_output=True, text=True,
            timeout=90, check=False, env=installation.environment(blender),
            creationflags=BANDERAS_SIN_VENTANA, cwd=carpeta_de_proceso(),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"disponible": False, "motivo": f"No se pudo comprobar Blender: {type(exc).__name__}."}
    marker = next((l.split("MOLCY_CAPS:", 1)[1] for l in result.stdout.splitlines()
                   if "MOLCY_CAPS:" in l), None)
    version_marker = next((l.split("MOLCY_BLENDER_VERSION:", 1)[1] for l in result.stdout.splitlines()
                           if "MOLCY_BLENDER_VERSION:" in l), None)
    try:
        info = json.loads(marker) if marker else None
        version = json.loads(version_marker) if version_marker else None
    except json.JSONDecodeError:
        return {"disponible": False, "motivo": "Blender devolvió una comprobación ilegible.",
                "blender": str(blender), "motor": str(engine)}
    if version and tuple(version[:2]) < VERSION_MINIMA_BLENDER:
        # Se mira ANTES de pedir Molecular Nodes: instalar la extensión en un Blender que el motor no soporta no arregla nada.
        return {"disponible": False, "motivo": "Molcy requiere Blender 5.2 o superior. Usa el Blender de MolDesign (recomendado) o actualiza el tuyo.",
                "motivo_codigo": "blender_antiguo", "version_blender": version,
                "blender": str(blender), "motor": str(engine)}
    if marker is None:
        missing = "No module named 'bl_ext" in (result.stdout + result.stderr)
        return {"disponible": False,
                "motivo_codigo": "falta_addon" if missing else "addon_no_carga",
                "motivo": ("Falta Molecular Nodes en este Blender. Instálalo para generar vídeos."
                           if missing else "Blender no pudo cargar Molecular Nodes sin conexión."),
                "blender": str(blender), "motor": str(engine)}
    assert info is not None
    if result.returncode != 0 or "MOLCY_CPU_OK" not in result.stdout:
        return {"disponible": False, "motivo_codigo": "cpu_no_disponible",
                "motivo": "Blender no pudo renderizar con Cycles en CPU.",
                "blender": str(blender), "motor": str(engine)}
    gpu_info: dict[str, Any] = {}
    cycles_gpu: dict[str, Any] | None = None
    try:
        gpu_result = subprocess.run(
            [str(blender), "-b", "--factory-startup", "--python-exit-code", "1",
             "--python-expr", SONDEO_GPU], capture_output=True, text=True,
            timeout=90, check=False, env=installation.environment(blender),
            creationflags=BANDERAS_SIN_VENTANA, cwd=carpeta_de_proceso(),
        )
        gpu_disponible = gpu_result.returncode == 0 and "MOLCY_EEVEE_OK" in gpu_result.stdout
        gpu_marker = next((line.split("MOLCY_GPU:", 1)[1] for line in gpu_result.stdout.splitlines() if "MOLCY_GPU:" in line), None)
        if gpu_marker:
            data = json.loads(gpu_marker)
            if isinstance(data, dict) and all(isinstance(data.get(key), str) for key in ("gpu_vendor", "gpu_nombre")):
                gpu_info = {key: data[key] for key in ("gpu_vendor", "gpu_nombre")}
        cycles_marker = next((line.split("MOLCY_CYCLES_GPU:", 1)[1] for line in gpu_result.stdout.splitlines()
                              if "MOLCY_CYCLES_GPU:" in line), None)
        if cycles_marker and gpu_result.returncode == 0:
            data = json.loads(cycles_marker)
            if (isinstance(data, dict) and data.get("tipo") in TIPOS_GPU_CYCLES and isinstance(data.get("nombres"), list)
                    and data["nombres"] and all(isinstance(n, str) for n in data["nombres"])):
                cycles_gpu = {"tipo": data["tipo"], "nombres": data["nombres"][:8]}
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        gpu_disponible = False
    try:
        disk.validate_engine(engine)
    except (OSError, ValueError, KeyError, SyntaxError) as exc:
        return {"disponible": False, "motivo": str(exc),
                "blender": str(blender), "motor": str(engine)}
    huella = cpu.huella_motor(engine)
    threads_module = engine / "scripts/variables/cpu.py"
    configurable = (threads_module.is_file() and "MOLCY_CPU_THREADS" in threads_module.read_text(encoding="utf-8")
                    and all("hilos_cpu()" in p.read_text(encoding="utf-8")
                            for p in (engine / "scripts/salida/render.py", engine / "scripts/marca/cierre.py") if p.is_file())
                    and all(p.is_file() for p in (engine / "scripts/salida/render.py", engine / "scripts/marca/cierre.py")))
    fotos = motor_con_fotos(engine)
    disponible = fotos or gpu_disponible
    return {"disponible": disponible,
            "motivo": None if disponible else "EEVEE no funciona en este equipo y este motor Molcy no sabe tomar fotos: actualiza MolDesign.",
            "blender": str(blender),
            "motor": str(engine), "version_blender": info["version"],
            "molecular_nodes": info["molecular_nodes"], "motor_sha256": huella, **cpu.recursos(), **_procedencia_del_motor(engine, origen),
            "cpu_hilos_configurables": configurable,
            # Vídeo: sólo GPU (EEVEE). Fotos: Cycles en CPU siempre y en GPU si Cycles encontró una que funciona.
            "gpu_disponible": gpu_disponible, **gpu_info,
            "motivo_gpu": None if gpu_disponible else "El vídeo necesita una GPU que funcione con EEVEE. Con la CPU puedes tomar fotos de la escena.",
            "foto_disponible": fotos,
            "motivo_foto": None if fotos else "Este motor Molcy no sabe tomar fotos: actualiza MolDesign.",
            "foto_gpu_disponible": bool(fotos and cycles_gpu),
            "foto_gpu_tipo": cycles_gpu["tipo"] if cycles_gpu else None,
            "foto_gpu_nombres": cycles_gpu["nombres"] if cycles_gpu else [],
            "motivo_foto_gpu": None if cycles_gpu else "Cycles no encontró una GPU compatible (CUDA, OptiX, HIP u oneAPI): las fotos se harán con la CPU."}


def raiz_trabajo(user_id: str, job_id: str) -> Path:
    return storage.raiz_trabajo(user_id, job_id)


def raiz_salida() -> Path:
    return data_dir() / "molcy"


def _estado_path(root: Path) -> Path:
    return root / "estado.json"


def leer_estado(user_id: str, job_id: str) -> dict[str, Any] | None:
    try:
        root = raiz_trabajo(user_id, job_id)
    except (OSError, ValueError) as exc:
        return {"id": job_id, "estado": "fallido", "motivo": str(exc)}
    path = _estado_path(root)
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"id": job_id, "estado": "fallido", "motivo": "El estado del trabajo está dañado o no se pudo leer."}
    if not isinstance(value, dict) or value.get("id") != job_id:
        return {"id": job_id, "estado": "fallido", "motivo": "El estado del trabajo está dañado o no se pudo leer."}
    if value.get("estado") in {"en_cola", "renderizando"}:
        with _lock:
            vivo = job_id in _reserved
        if not vivo:
            # El hilo de render pudo terminar (y guardar su estado final) entre la lectura de arriba y esta comprobación:
            # se vuelve a leer antes de dar el trabajo por interrumpido, o se pisaría la causa real del fallo.
            try:
                actual = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                actual = None
            if isinstance(actual, dict) and actual.get("id") == job_id and actual.get("estado") not in {"en_cola", "renderizando"}:
                return actual
            if value.get("tipo") == "fotos" and value.get("fase") in {"foto", "vista"}:
                # La escena ya estaba preparada: una foto cortada no estropea la sesión, que sigue sirviendo para la siguiente.
                value = {**value, "estado": "completo", "fase": None,
                         "ultima_operacion": {**(value.get("ultima_operacion") or {}), "estado": "fallido",
                                              "motivo": "La foto se interrumpió al cerrar MolDesign."}}
            else:
                value = {**value, "estado": "fallido", "motivo": "Render interrumpido al cerrar MolDesign."}
            try:
                guardar_estado(root, value)
            except OSError:
                # Incluso con el volumen lleno, la API debe informar el fallo.
                pass
    if value.get("estado") == "renderizando" and value.get("tipo") != "fotos":
        value = {**value, **_progreso(root, value)}
    return value


def _progreso(root: Path, value: dict[str, Any]) -> dict[str, Any]:
    """ETA del render principal medida en fotogramas reales de este equipo."""
    output = root / "salida"
    suffix = value["id"].replace("-", "")[:12]
    formato = value["formato"]
    parcial = output / f"build_{formato}_{suffix}.parcial.json"
    final = output / f"build_{formato}_{suffix}.json"
    acta = parcial if parcial.is_file() else final
    if not acta.is_file():
        return {}
    try:
        datos = json.loads(acta.read_text(encoding="utf-8"))
        # Con pausas de lectura el vídeo repite PNG ya rendidos: lo que Blender deja en
        # disco son los fotogramas DISTINTOS, no los del vídeo.
        total = int(datos.get("fotogramas_render_unicos") or datos["fotogramas"])
        frames = sorted((p for p in (output / f"render_{formato}_{suffix}").glob("f_*.png")
                         if p.is_file()), key=lambda p: p.name)
        hechos = total if final.is_file() and not frames else min(len(frames), total)
        result: dict[str, Any] = {"progreso": {"fotogramas": hechos, "total": total}}
        if 5 <= hechos < total:
            recientes = frames[-5:]
            segundos = (recientes[-1].stat().st_mtime - recientes[0].stat().st_mtime) / 4
            if segundos > 0:
                result["restante_render_principal_s"] = round((total - hechos) * segundos)
        return result
    except (OSError, ValueError, KeyError, json.JSONDecodeError):
        return {}


#: Los fotogramas que Blender va dejando en `render_<formato>_<sufijo>/`: la pantalla enseña el más reciente mientras se forma el vídeo.
_FOTOGRAMA = re.compile(r"^f_(\d{4,})\.png$")
#: Los últimos 12 bytes de todo PNG entero (el trozo IEND): uno cortado a medio escribir no los tiene.
_FIN_PNG = b"\x00\x00\x00\x00IEND\xaeB`\x82"


def _png_entero(path: Path) -> bool:
    try:
        with path.open("rb") as stream:
            stream.seek(-len(_FIN_PNG), os.SEEK_END)
            return stream.read() == _FIN_PNG
    except OSError:
        return False


def fotograma_reciente(user_id: str, job_id: str, value: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """El último fotograma COMPLETO del render principal de un trabajo que está renderizando.

    Devuelve `{"indice", "orden", "total", "ruta"}`, o None si no hay ninguno (aún no empezó, ya terminó o el trabajo no
    existe). Se mira desde el más nuevo: el último PNG puede estar escribiéndose y entonces se enseña el anterior. Son
    fotogramas del render PRINCIPAL: los rótulos de pantalla se rinden aparte y el cierre se añade al codificar, así que
    no salen aquí.

    `indice` es el fotograma del GUION (el nombre del PNG) y sirve de cursor. `total` cuenta los fotogramas que se rinden,
    que con pausas de lectura y fotogramas reutilizados son menos que los del guion, así que `indice` no va sobre `total`:
    la pantalla decía «Fotograma 681 de 667». Lo que va sobre `total` es `orden`, la posición de este PNG entre los ya
    rendidos (la misma cuenta que la barra de progreso, y como ella, nunca por encima del total).
    """
    value = value if value is not None else leer_estado(user_id, job_id)
    if not value or value.get("estado") != "renderizando":
        return None
    carpeta = raiz_trabajo(user_id, job_id) / "salida" / f"render_{value['formato']}_{value['id'].replace('-', '')[:12]}"
    if carpeta.is_symlink() or not carpeta.is_dir():
        return None
    try:
        nombres = sorted((p.name for p in carpeta.iterdir() if _FOTOGRAMA.match(p.name)), reverse=True)
    except OSError:
        return None
    total = (value.get("progreso") or {}).get("total")
    for posicion, nombre in enumerate(nombres[:3]):
        ruta = carpeta / nombre
        if not ruta.is_symlink() and _png_entero(ruta):
            orden = len(nombres) - posicion
            return {"indice": int(_FOTOGRAMA.match(nombre).group(1)),
                    "orden": min(orden, total) if total else orden, "total": total, "ruta": ruta}
    return None


def guardar_estado(root: Path, value: dict[str, Any]) -> None:
    path = _estado_path(root)
    temp = root / (".estado-" + uuid.uuid4().hex + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        # En Windows `os.replace` falla con PermissionError mientras otro hilo tiene abierto el fichero, y la interfaz lo lee
        # al sondear: sin reintento, un sondeo que coincide con el primer guardado del hilo de render lo mataba.
        for intento in range(ESTADO_REINTENTOS):
            try:
                os.replace(temp, path)
                break
            except PermissionError:
                if intento == ESTADO_REINTENTOS - 1:
                    raise
                time.sleep(0.01 * (intento + 1))
    finally:
        temp.unlink(missing_ok=True)


#: El vídeo se genera sólo con GPU (EEVEE). Medido el 2026-10-07: tres segundos de vídeo por CPU no enseñaban nada de lo que da
#: valor al vídeo y costaban minutos; la CPU toma fotos (`fotos.py`).
MENSAJE_VIDEO_SOLO_GPU = "El vídeo se genera sólo con GPU. Con la CPU puedes tomar fotos de la escena."


def idioma_actual() -> str:
    from core.i18n import current_locale
    return "en" if current_locale() == "en" else "es"


def entorno(root: Path, output: Path, cfg: dict[str, Any], *, idioma: str,
            hilos: int | None = None) -> tuple[dict[str, str], int, int]:
    """(entorno, hilos, límite de CPU en centésimas de %) para lanzar el motor sobre el trabajo `root`.

    Las rutas del proceso externo pierden el prefijo de ruta larga de Windows (PowerShell 5.1 y otros programas no lo
    entienden); las comprobaciones de propiedad las hace quien llama con sus Path canónicos.
    """
    engine = Path(cfg["motor"])
    env = {**installation.environment(Path(cfg["blender"])),
           "MOLCY_SCENES_DIR": ruta_para_programa(root / "escenas"),
           "MOLCY_OUTPUT_DIR": ruta_para_programa(output), "MOLCY_CASES_DIR": ruta_para_programa(root),
           "MOLCY_IDIOMA": "en" if idioma == "en" else "es",
           "MOLCY_BRAND_CACHE_DIR": ruta_para_programa(raiz_salida() / "cache" / "cierre"),
           "MOLCY_ART_TEMPLATE": ruta_para_programa(engine / "moldesign" / "assets" / "blender" / "plantilla_arte.blend")}
    for variable in ("BLENDER_USER_RESOURCES", "BLENDER_USER_CONFIG", "BLENDER_USER_EXTENSIONS"):
        if variable in env:
            env[variable] = ruta_para_programa(env[variable])
    resources = cpu.recursos()
    threads = cpu.validar_hilos(hilos, resources)
    env["MOLCY_CPU_THREADS"] = str(threads)
    for variable in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        env[variable] = str(threads)
    cpu_rate = max(1, min(7500, threads * 10000 // resources.get("cpu_logicos", resources["cpu_hilos_disponibles"])))
    temp_dir = root / "temporales"
    temp_dir.mkdir(exist_ok=True)
    env.update({"TEMP": ruta_para_programa(temp_dir), "TMP": ruta_para_programa(temp_dir)})
    return env, threads, cpu_rate


def limpiar_temporales(root: Path) -> None:
    temp_dir = root / "temporales"
    if temp_dir.is_dir() and not temp_dir.is_symlink() and temp_dir.resolve().parent == root.resolve():
        shutil.rmtree(temp_dir, ignore_errors=True)


def soltar(job_id: str) -> None:
    """El trabajo deja de ocupar el renderizador (fin, fallo o cancelación)."""
    with _lock:
        _futures.pop(job_id, None)
        _reserved.discard(job_id)
        _processes.pop(job_id, None)
        _cancel_events.pop(job_id, None)


def encolar(job_id: str, funcion, *args) -> None:
    """Pone `funcion(*args)` en la única cola de Blender; `job_id` queda reservado hasta que `funcion` lo suelte."""
    with _lock:
        _cancel_events[job_id] = threading.Event()
        _reserved.add(job_id)
        _futures[job_id] = _pool.submit(funcion, *args)


def iniciar(root: Path, *, job_id: str, pdb_id: str, sujeto: str,
            formato: str, dispositivo: str, capacidad: dict[str, Any], fuente: dict[str, Any], cpu_hilos: int | None = None,
            gpu_presupuesto: dict | None = None, presentacion: dict | None = None,
            ensamble_fluido: dict | None = None) -> None:
    if dispositivo != "gpu" or cpu_hilos is not None:
        raise ValueError(MENSAJE_VIDEO_SOLO_GPU)
    estado = {"id": job_id, "estado": "en_cola", "formato": formato,
              "sujeto": sujeto, "dispositivo": dispositivo, "idioma": idioma_actual(),
              "fuente": fuente, "renderizador": capacidad}
    estado["gpu_memoria"] = "presupuesto" if gpu_presupuesto is not None else "automatica"
    if gpu_presupuesto is not None:
        estado["gpu_presupuesto"] = gpu_presupuesto
    estado["creado_s"] = time.time()
    receta_visual.guardar(root, estado, presentacion=presentacion, ensamble_fluido=ensamble_fluido)
    guardar_estado(root, estado)
    encolar(job_id, _ejecutar, root, estado, pdb_id)


def _ejecutar(root: Path, estado: dict[str, Any], pdb_id: str) -> None:
    output = root / "salida"
    cfg = estado["renderizador"]
    engine = Path(cfg["motor"])
    powershell = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    suffix = estado["id"].replace("-", "")[:12]
    guion = GUION_DE_SUJETO.get(estado["sujeto"], "sitio_activo")
    cancel_event = _cancel_events.get(estado["id"], threading.Event())
    try:
        if cancel_event.is_set():
            raise InterruptedError("Render cancelado por el usuario.")
        env, _threads, cpu_rate = entorno(root, output, cfg, idioma=estado.get("idioma", "es"))
        estado["cpu_limite_pct"] = cpu_rate / 100
        monitor = None
        if estado["dispositivo"] == "gpu" and estado.get("gpu_presupuesto") is not None:
            requested = (estado.get("gpu_presupuesto") or {}).get("gpu_vram_presupuesto_mib")
            budget = gpu.validar_presupuesto(requested, gpu.recursos(cfg))
            estado["gpu_presupuesto"] = budget
            monitor = gpu.Vigilancia(budget)
            monitor()
        disk.assert_budget(root, estado["formato"])
        disk.assert_brand_budget(raiz_salida(), estado["formato"])
        output.mkdir(exist_ok=True)
        estado["estado"] = "renderizando"
        guardar_estado(root, estado)
        # Después de las comprobaciones de disco: si la unidad está llena, el mensaje de espacio sale antes que una copia que falle.
        # El halo del título y el sellado corren con un Python que PowerShell sí puede arrancar: el del paquete, en WindowsApps,
        # da «Acceso denegado» como proceso hijo (ver python_auxiliar.py).
        python_del_motor = python_auxiliar()
        # Las comprobaciones de propiedad conservan sus Path canónicos. Sólo
        # los argumentos y directorios del proceso externo pierden \\?\:
        # Join-Path/Out-File de PowerShell 5.1 fallan antes de lanzar Blender.
        cmd = [str(powershell), "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
               "-File", str(engine / "scripts" / "correr_caso.ps1"),
               "-Pdb", pdb_id, "-Sufijo", suffix, "-Carpeta", str(output),
               "-Formato", estado["formato"], "-Renderizador", estado["dispositivo"],
               "-Guion", guion,
               "-Sujeto", estado["sujeto"], "-Root", str(engine),
               "-Blender", cfg["blender"], "-Python", str(python_del_motor)]
        cmd[0] = ruta_para_programa(cmd[0])
        for argumento in ("-File", "-Carpeta", "-Root", "-Blender", "-Python"):
            posicion = cmd.index(argumento) + 1
            cmd[posicion] = ruta_para_programa(cmd[posicion])
        receta = receta_visual.ruta_verificada(root, estado)
        if receta is not None:
            cmd.extend(["-Ajustes", ruta_para_programa(receta)])
        with (root / "render.log").open("w", encoding="utf-8") as log:
            def on_start(process):
                with _lock:
                    _processes[estado["id"]] = process
            gpu_monitor = monitor
            def vigilar():
                if gpu_monitor is not None:
                    gpu_monitor()
                if (disk.free_bytes(root) < disk.RESERVE_BYTES
                        or disk.free_bytes(raiz_salida()) < disk.RESERVE_BYTES):
                    raise RuntimeError("Molcy detuvo el render porque la unidad del caso o del cierre "
                                       "tiene menos de 1 GiB libre.")
            # El render corre en la carpeta del trabajo, no en la del backend (BUG-molcy-render-WindowsApps).
            result = run_owned(cmd, env=env, stdout=log, cancel=cancel_event, on_start=on_start,
                               timeout=7200, cpu_rate=cpu_rate, monitor=vigilar, cwd=ruta_para_programa(root))
        if cancel_event.is_set():
            raise InterruptedError("Render cancelado por el usuario.")
        if result.returncode != 0:
            failure = next(output.glob("FALLO_*.txt"), None)
            if failure and "ESPACIO_INSUFICIENTE" in failure.read_text(encoding="utf-8", errors="replace"):
                raise RuntimeError("Molcy detuvo el render porque el espacio libre cayó por debajo de la reserva de 1 GiB.")
            run_log = next(output.glob("run_*.log"), None)
            if run_log and "ESPACIO_INSUFICIENTE" in run_log.read_text(encoding="utf-8", errors="replace"):
                raise RuntimeError("Molcy detuvo el render porque el espacio libre cayó por debajo de la reserva de 1 GiB.")
            raise RuntimeError(f"Molcy terminó con código {result.returncode}; revisa render.log")
        video = output / f"{pdb_id}_{guion}_{estado['formato']}_{suffix}.mp4"
        build = output / f"build_{estado['formato']}_{suffix}.json"
        if not video.is_file() or not build.is_file():
            raise RuntimeError("Molcy no produjo MP4 y acta final")
        digest = sha256_archivo(video)
        acta = json.loads(build.read_text(encoding="utf-8"))
        if acta.get("render_ajustes", {}).get("motor") != "BLENDER_EEVEE":
            raise RuntimeError("El acta no acredita el renderizador solicitado")
        # El cierre de MolDesign es obligatorio en todo video y en los tres formatos: lo certifica el acta y lo mide el MP4.
        cierre.verificar(acta, video, idioma=estado.get("idioma", "es"))
        if "ajustes" in estado and (acta.get("ajustes") or {}).get("entrada") != estado["ajustes"]:
            raise RuntimeError("El acta no acredita la receta visual solicitada.")
        if acta.get("video", {}).get("sha256") != digest:
            raise RuntimeError("El SHA-256 del MP4 no coincide con el acta")
        estado.update({"estado": "completo", "video": video.name,
                       "video_sha256": digest, "acta": build.name})
    except InterruptedError as exc:
        estado.update({"estado": "cancelado", "motivo": str(exc)})
    except (OSError, RuntimeError, subprocess.TimeoutExpired, json.JSONDecodeError, ValueError) as exc:
        estado.update({"estado": "fallido", "motivo": str(exc)[:500]})
    finally:
        # Ningún fotograma parcial queda consumiendo espacio después de terminar.
        for folder in output.glob("render_*"):
            if folder.is_dir() and not folder.is_symlink() and folder.resolve().parent == output.resolve():
                shutil.rmtree(folder, ignore_errors=True)
        limpiar_temporales(root)
        estado["terminado_s"] = time.time()
        try:
            guardar_estado(root, estado)
        except OSError:
            pass
        finally:
            soltar(estado["id"])


@contextmanager
def reservar(job_id: str):
    """Un trabajo a la vez: limita RAM, CPU y reserva de disco compartida."""
    with _lock:
        if _reserved:
            raise ValueError("Molcy ya tiene un render activo. Espera o cancélalo antes de generar otro vídeo.")
        _reserved.add(job_id)
    try:
        yield
    finally:
        with _lock:
            if job_id not in _futures:
                _reserved.discard(job_id)


def cancelar(user_id: str, job_id: str) -> dict[str, Any] | None:
    value = leer_estado(user_id, job_id)
    if value is None:
        return None
    with _lock:
        event = _cancel_events.get(job_id)
        if event:
            event.set()
            future = _futures.get(job_id)
            if future and future.cancel():
                if value.get("tipo") == "fotos" and value.get("escena_fotos"):
                    # Cancelar una foto en cola no deshace la escena preparada.
                    value.update(estado="completo", fase=None, ultima_operacion={
                        **(value.get("operacion") or {}), "estado": "cancelado", "motivo": "Foto cancelada por el usuario."})
                    value.pop("operacion", None)
                else:
                    value.update(estado="cancelado", motivo="Render cancelado por el usuario.")
                guardar_estado(raiz_trabajo(user_id, job_id), value)
                _futures.pop(job_id, None)
                _cancel_events.pop(job_id, None)
                _reserved.discard(job_id)
    return leer_estado(user_id, job_id)


def listar(user_id: str) -> list[dict[str, Any]]:
    uuid.UUID(user_id)
    root = raiz_salida() / user_id
    jobs = []
    if root.is_dir():
        for folder in root.iterdir():
            try:
                uuid.UUID(folder.name)
                value = leer_estado(user_id, folder.name)
                if value:
                    try:
                        jobs.append(_detalles_historial(user_id, value))
                    except (ValueError, OSError):
                        jobs.append(value)
            except (ValueError, OSError):
                continue
    def created(value):
        timestamp = value.get("creado_s")
        return timestamp if type(timestamp) in (int, float) and math.isfinite(timestamp) else 0
    return sorted(jobs, key=created, reverse=True)


def _detalles_historial(user_id: str, value: dict[str, Any]) -> dict[str, Any]:
    """Añade al contrato de historial la identidad del receptor y las rutas locales del trabajo."""
    job = dict(value)
    root = raiz_trabajo(user_id, str(job["id"]))
    job["carpeta_ruta"] = str(root.resolve())

    scenes = root / "escenas"
    if scenes.is_dir() and not scenes.is_symlink():
        for folder in scenes.iterdir():
            scene_path = folder / "scene.json"
            if folder.is_symlink() or not folder.is_dir() or scene_path.is_symlink() or not scene_path.is_file():
                continue
            try:
                scene = json.loads(scene_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            receptor = scene.get("receptor") if isinstance(scene, dict) else None
            if not isinstance(receptor, dict):
                continue
            source = scene.get("procedencia") if isinstance(scene.get("procedencia"), dict) else {}
            saved_source = job.get("fuente") if isinstance(job.get("fuente"), dict) else {}
            job["receptor"] = {
                "pdb_id": receptor.get("pdb_id") or folder.name,
                "nombre": receptor.get("nombre"),
                "cadena": receptor.get("cadena_principal"),
                "target_id": source.get("target_id") or saved_source.get("target_id"),
            }
            break

    if job.get("tipo") == "fotos":
        from . import fotos
        job.update(fotos.detalles(user_id, job))
    elif job.get("estado") == "completo" and isinstance(job.get("video"), str):
        name = Path(job["video"]).name
        output = root / "salida"
        video = output / name
        if name and not output.is_symlink() and video.is_file() and not video.is_symlink():
            try:
                if video.resolve().parent == output.resolve():
                    job["video_ruta"] = str(video.resolve())
            except OSError:
                pass
    return job


def revelar(user_id: str, job_id: str) -> dict[str, str] | None:
    """Abre en el explorador el MP4 terminado (o la última foto de una sesión) o, si aún no existe, la carpeta del trabajo."""
    value = leer_estado(user_id, job_id)
    if value is None:
        return None

    root = raiz_trabajo(user_id, job_id)
    storage.validar_raiz(user_id, job_id, root)

    target = root
    es_video = False
    if value.get("tipo") == "fotos":
        if value.get("fotos"):
            from . import fotos
            try:
                target = fotos.ultima_foto(user_id, job_id)
            except (LookupError, RuntimeError) as exc:
                raise ValueError("La foto de este trabajo ya no está en su carpeta de salida.") from exc
            es_video = True     # se selecciona el fichero, como un vídeo
    elif value.get("estado") == "completo":
        name = value.get("video")
        if not isinstance(name, str) or not name or Path(name).name != name:
            raise ValueError("El trabajo no conserva un nombre de vídeo válido.")
        output = root / "salida"
        target = output / name
        if (output.is_symlink() or not output.is_dir() or output.resolve().parent != root.resolve()
                or target.is_symlink() or not target.is_file() or target.resolve().parent != output.resolve()):
            raise ValueError("El vídeo de este trabajo ya no está en su carpeta de salida.")
        if not value.get("video_sha256") or sha256_archivo(target) != value["video_sha256"]:
            raise ValueError("El vídeo ya no coincide con su SHA-256.")
        es_video = True

    ruta = str(target.resolve())
    if sys.platform == "win32":
        if es_video:
            from utils.file_explorer import seleccionar_windows
            seleccionar_windows(target.resolve())
            return {"ruta": ruta, "tipo": "foto" if value.get("tipo") == "fotos" else "video"}
        command = ["explorer.exe", ruta]
    elif sys.platform == "darwin":
        command = ["open", "-R", ruta] if es_video else ["open", ruta]
    else:
        command = ["xdg-open", str(target.parent.resolve() if es_video else target.resolve())]
    subprocess.Popen(command, creationflags=BANDERAS_SIN_VENTANA, cwd=carpeta_de_proceso())
    return {"ruta": ruta, "tipo": ("foto" if value.get("tipo") == "fotos" else "video") if es_video else "carpeta"}


def eliminar(user_id: str, job_id: str) -> bool:
    root = raiz_trabajo(user_id, job_id)
    value = leer_estado(user_id, job_id)
    if value is None:
        return False
    with _lock:
        if job_id in _reserved:
            raise ValueError("Cancela el render y espera a que termine antes de eliminarlo.")
        storage.validar_raiz(user_id, job_id, root)
        shutil.rmtree(root)
        storage.retirar_indice(user_id, job_id)
    return True
