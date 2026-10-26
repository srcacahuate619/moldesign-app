"""Fotos de Molcy: la escena se prepara una vez y de ella salen las fotos que se pidan.

Decisiones del propietario (2026-10-08): la CPU ya no genera vídeo, toma FOTOS; con GPU también se pueden pedir. Todas se rinden
con Cycles (en CPU o en GPU), así que la foto no depende del equipo: medido en 4FK3 a 1080×1920, la de CPU y la de GPU difieren
0,03/255 de media. Resolución de 720p (el piso) a 4K (el techo, para imprimir). Primero las tomas sugeridas y, como segunda
opción, cualquier fotograma de la escena.

Una sesión de fotos es un trabajo de Molcy como un vídeo (su carpeta, su `estado.json`, la misma cola de Blender):

1. Preparar: el motor construye la escena (`correr_foto.py preparar`) y rinde una miniatura de cada momento sugerido.
2. Foto: un fotograma a 720p, 1080p, 1440p o 4K. MolDesign le pone la marca y la procedencia (`marca_foto.py`) y borra el PNG
   sin marca: lo que se entrega siempre lleva el emblema.
3. Vista: un fotograma libre al tamaño de una miniatura, para elegirlo viendo.

La escena no se reconstruye para cada foto: el motor abre el `.blend` de la preparación, comprobado por su SHA-256. Una foto que
falla o se cancela no estropea la sesión: la escena sigue sirviendo para la siguiente.
"""
from __future__ import annotations

import hashlib
import json
import statistics
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from utils.windows_paths import ruta_para_programa
from . import cpu, disk, marca_foto, renderer, storage
from . import presentacion as receta_visual
from .process import run_owned
from .python_auxiliar import python_auxiliar

#: Lado corto de cada resolución. El piso es 720p y el techo 4K, que a 300 ppp da 32,5 × 18,3 cm: más que una figura a doble
#: columna de una revista (~17,5 cm de ancho).
RESOLUCIONES = {"720p": 720, "1080p": 1080, "1440p": 1440, "4k": 2160}
ORIENTACIONES = {"horizontal": "biblioteca", "vertical": "social_vertical"}
ESCENAS = ("resultado", "receptor", "busqueda", "ensamble")
#: Muestras de Cycles de una foto, con muestreo adaptativo y OpenImageDenoise (las fija el motor; aquí sólo se piden).
MUESTRAS_FOTO = 128
#: Una vista previa libre: como las miniaturas de las tomas sugeridas.
LADO_VISTA, MUESTRAS_VISTA = 480, 16
#: Vistas previas que se conservan por sesión: cada una es una miniatura de ~0,2 MB.
MAXIMO_VISTAS = 24
#: Medido el 2026-10-08 en 4FK3 (Ryzen 5 5500 con 8 hilos / GTX 1660 SUPER, 128 muestras): preparar 38 s en CPU; una foto
#: 720×1280, 81 s en CPU y 24 s en GPU; 1080×1920, 104 s y 25 s; 4K, 13,4 min y 90 s. Los límites dejan margen para
#: equipos lentos y pocos hilos sin dejar un Blender colgado para siempre.
LIMITE_PREPARAR_S = 3600
LIMITE_FOTO_S = {"gpu": 3600, "cpu": 6 * 3600}


class SesionNoDisponible(ValueError):
    """La sesión no admite la operación pedida (no es de fotos, no está preparada o está ocupada)."""


def dimensiones(orientacion: str, resolucion: str) -> tuple[int, int]:
    """(ancho, alto) en 16:9 o 9:16: 720p → 1280×720, 4K → 3840×2160."""
    if orientacion not in ORIENTACIONES or resolucion not in RESOLUCIONES:
        raise ValueError("Resolución u orientación desconocida.")
    corto = RESOLUCIONES[resolucion]
    largo = corto * 16 // 9
    return (largo, corto) if orientacion == "horizontal" else (corto, largo)


def _sufijo(estado: dict[str, Any]) -> str:
    return estado["id"].replace("-", "")[:12]


def _comando(cfg: dict[str, Any], orden: str, *args: str) -> list[str]:
    """El lanzador de fotos del motor con el Python auxiliar de Molcy (lleva Pillow), como `contraste.py` del vídeo.

    No el del paquete: en la app instalada ese Python está en WindowsApps y no es fiable arrancarlo como hijo (ver
    python_auxiliar.py). El auxiliar sólo necesita la biblioteca estándar y Pillow, que es lo que usa correr_foto.py.
    """
    engine = Path(cfg["motor"])
    return [ruta_para_programa(python_auxiliar()), ruta_para_programa(engine / "scripts" / "correr_foto.py"), orden, *args]


def _lanzar(root: Path, estado: dict[str, Any], cmd: list[str], *, hilos: int | None, limite_s: int, registro: str):
    cfg = estado["renderizador"]
    output = root / "salida"
    output.mkdir(exist_ok=True)
    env, threads, cpu_rate = renderer.entorno(root, output, cfg, idioma=estado.get("idioma", "es"), hilos=hilos)
    cancel_event = renderer._cancel_events.get(estado["id"])
    if cancel_event is None or cancel_event.is_set():
        raise InterruptedError("Render cancelado por el usuario.")

    def on_start(process):
        with renderer._lock:
            renderer._processes[estado["id"]] = process

    def vigilar():
        if disk.free_bytes(root) < disk.RESERVE_BYTES:
            raise RuntimeError("Molcy detuvo la foto porque la unidad del caso tiene menos de 1 GiB libre.")

    with (root / registro).open("a", encoding="utf-8") as log:
        desde = log.tell()       # el registro es de toda la sesión: el motivo se busca sólo en lo que escriba ESTA operación
        result = run_owned(cmd, env=env, stdout=log, cancel=cancel_event, on_start=on_start,
                           timeout=limite_s, cpu_rate=cpu_rate, monitor=vigilar, cwd=ruta_para_programa(root))
    if cancel_event.is_set():
        raise InterruptedError("Render cancelado por el usuario.")
    if result.returncode != 0:
        motivo = _fallo_del_registro(root / registro, desde)
        raise RuntimeError(_MOTIVOS.get(motivo, f"Molcy no pudo terminar ({motivo or result.returncode}); revisa {registro}."))
    return threads


#: Lo que el lanzador del motor dice al fallar, en palabras de quien lo lee.
_MOTIVOS = {
    "QC_ABORTADO": "El control de calidad del motor no deja encuadrar esta escena; el acta del caso dice por qué.",
    "SIN_GPU_CYCLES": "Cycles no encontró la GPU de este equipo. Toma la foto con la CPU o vuelve a comprobar el renderizador.",
    "ESPACIO_INSUFICIENTE": "Molcy detuvo la foto porque el espacio libre cayó por debajo de la reserva de 1 GiB.",
    "BLEND_NO_COINCIDE": "La escena preparada cambió desde que se preparó; prepara la escena otra vez.",
    "SIN_BLENDER": "No se encontró Blender; vuelve a comprobar el renderizador.",
}


def _fallo_del_registro(path: Path, desde: int = 0) -> str | None:
    try:
        with path.open("rb") as stream:
            stream.seek(desde)
            lineas = stream.read().decode("utf-8", errors="replace").splitlines()
    except OSError:
        return None
    ultimo = next((l for l in reversed(lineas) if l.startswith("FALLO ")), None)
    return ultimo.split(" ", 1)[1].split("(")[0].strip() if ultimo else None


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"{path.name} no es un acta de Molcy.")
    return value


def _dentro(carpeta: Path, nombre: Any) -> Path:
    """Un fichero que el acta nombra, sin salir de `carpeta` ni seguir redirecciones."""
    if not isinstance(nombre, str) or not nombre or Path(nombre).name != nombre or nombre.startswith("."):
        raise RuntimeError("El acta nombra un fichero fuera de su carpeta.")
    path = carpeta / nombre
    if path.is_symlink() or not path.is_file() or path.resolve().parent != carpeta.resolve():
        raise RuntimeError(f"Falta {nombre} o salió de su carpeta.")
    return path


# ── 1. preparar ──────────────────────────────────────────────────────────
def iniciar(root: Path, *, job_id: str, pdb_id: str, sujeto: str, escena: str, orientacion: str, dispositivo: str,
            capacidad: dict[str, Any], fuente: dict[str, Any], cpu_hilos: int | None = None,
            presentacion: dict | None = None, ensamble_fluido: dict | None = None) -> None:
    if orientacion not in ORIENTACIONES or dispositivo not in {"cpu", "gpu"} or escena not in ESCENAS:
        raise ValueError("Sesión de fotos mal pedida.")
    estado = {"id": job_id, "tipo": "fotos", "estado": "en_cola", "fase": "preparando",
              "formato": ORIENTACIONES[orientacion], "orientacion": orientacion, "escena": escena,
              "sujeto": sujeto, "pdb_id": pdb_id, "dispositivo": dispositivo, "idioma": renderer.idioma_actual(),
              "fuente": fuente, "renderizador": {**capacidad, **cpu.recursos()},
              "momentos": [], "fotos": [], "vistas": {}, "creado_s": time.time()}
    if dispositivo == "cpu":
        estado["cpu_hilos"] = cpu.validar_hilos(cpu_hilos)
    receta_visual.guardar(root, estado, presentacion=presentacion, ensamble_fluido=ensamble_fluido)
    renderer.guardar_estado(root, estado)
    renderer.encolar(job_id, _preparar, root, estado)


def _preparar(root: Path, estado: dict[str, Any]) -> None:
    output = root / "salida"
    suffix = _sufijo(estado)
    try:
        disk.assert_photo_budget(root, "4k")
        estado["estado"] = "renderizando"
        renderer.guardar_estado(root, estado)
        cfg = estado["renderizador"]
        cmd = _comando(cfg, "preparar", "--pdb", estado["pdb_id"],
                       "--guion", renderer.GUION_DE_SUJETO.get(estado["sujeto"], "sitio_activo"),
                       "--sujeto", estado["sujeto"], "--formato", estado["formato"], "--sufijo", suffix,
                       "--carpeta", ruta_para_programa(output), "--blender", ruta_para_programa(cfg["blender"]),
                       "--dispositivo", estado["dispositivo"])
        receta = receta_visual.ruta_verificada(root, estado)
        if receta is not None:
            cmd.extend(["--ajustes", ruta_para_programa(receta)])
        t0 = time.time()
        _lanzar(root, estado, cmd, hilos=estado.get("cpu_hilos"), limite_s=LIMITE_PREPARAR_S, registro="fotos.log")
        tomas = _json(output / f"tomas_{suffix}.json")
        escena_json = _dentro(output, f"escena_fotos_{suffix}.json")
        if tomas.get("schema") != "molcy.fotos.tomas/1" or tomas.get("escena") != escena_json.name:
            raise RuntimeError("El motor no dejó el acta de las tomas.")
        escena_sha = marca_foto.sha256(escena_json)
        if tomas.get("escena_sha256") != escena_sha:
            raise RuntimeError("El acta de las tomas no es de esta escena.")
        escena = _json(escena_json)
        if escena.get("schema") != "molcy.fotos.escena/1" or escena.get("pdb_id") != estado["pdb_id"]:
            raise RuntimeError("El acta de la escena no es de este receptor.")
        if "ajustes" in estado and (escena.get("ajustes") or {}).get("entrada") != estado["ajustes"]:
            raise RuntimeError("La escena preparada no acredita la receta visual solicitada.")
        carpeta_tomas = output / f"tomas_{suffix}"
        momentos = []
        for m in tomas.get("momentos") or []:
            png = _dentro(carpeta_tomas, m.get("archivo"))
            if marca_foto.sha256(png) != m.get("sha256"):
                raise RuntimeError("Una miniatura no coincide con su SHA-256.")
            momentos.append({k: m.get(k) for k in ("id", "fotograma", "beat", "tipo", "etiquetas", "pose", "orden")}
                            | {"miniatura": png.name, "miniatura_sha256": m["sha256"]})
        if not momentos:
            raise RuntimeError("La escena no tiene momentos que fotografiar.")
        estado.update({"estado": "completo", "fase": None, "momentos": momentos,
                       "escena_fotos": {"archivo": escena_json.name, "sha256": escena_sha,
                                        "fotogramas_fuente": escena["fotogramas_fuente"],
                                        "beats": escena["beats"], "papeles": escena.get("papeles") or {},
                                        "formato": {k: escena["formato"][k] for k in ("nombre", "ancho", "alto")},
                                        "blend_sha256": escena["blend"]["sha256"]},
                       "preparacion": {"segundos": round(time.time() - t0, 1), **(tomas.get("segundos") or {}),
                                       "render": _render_resumido(tomas.get("render_ajustes") or {})}})
    except InterruptedError as exc:
        estado.update({"estado": "cancelado", "fase": None, "motivo": str(exc)})
    except (OSError, RuntimeError, subprocess.TimeoutExpired, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        estado.update({"estado": "fallido", "fase": None, "motivo": _motivo(exc)})
    finally:
        _cerrar(root, estado)


def _motivo(exc: BaseException) -> str:
    if isinstance(exc, subprocess.TimeoutExpired):
        return f"Molcy superó el tiempo máximo ({round(exc.timeout / 60)} min) y se detuvo."
    return str(exc)[:500]


def _render_resumido(ajustes: dict[str, Any]) -> dict[str, Any]:
    return {k: ajustes.get(k) for k in ("motor", "blender", "dispositivo", "tipo_gpu", "gpus", "muestras", "denoiser",
                                        "semilla", "hilos_cpu", "resolucion")}


def _cerrar(root: Path, estado: dict[str, Any]) -> None:
    renderer.limpiar_temporales(root)
    estado["terminado_s"] = time.time()
    try:
        renderer.guardar_estado(root, estado)
    except OSError:
        pass
    finally:
        renderer.soltar(estado["id"])


# ── 2 y 3. foto y vista ──────────────────────────────────────────────────
def _sesion_lista(value: dict[str, Any] | None) -> dict[str, Any]:
    if value is None:
        raise LookupError("Trabajo no encontrado.")
    if value.get("tipo") != "fotos":
        raise SesionNoDisponible("Este trabajo es un vídeo, no una sesión de fotos.")
    if value.get("estado") != "completo" or not value.get("escena_fotos"):
        raise SesionNoDisponible("La escena de esta sesión todavía no está preparada.")
    return value


def pedir(user_id: str, job_id: str, *, operacion: str, fotograma: int, dispositivo: str,
          capacidad: dict[str, Any], resolucion: str | None = None, cpu_hilos: int | None = None) -> dict[str, Any]:
    """Encola una foto (`operacion="foto"`) o una vista previa (`"vista"`) en una sesión preparada. Devuelve el estado.

    Quien llama ya tiene la reserva del trabajo (`renderer.reservar`): es la que garantiza un solo Blender a la vez.
    """
    if operacion not in {"foto", "vista"} or dispositivo not in {"cpu", "gpu"}:
        raise ValueError("Operación de fotos desconocida.")
    with renderer._lock:
        if job_id not in renderer._reserved:
            raise RuntimeError("pedir() necesita la reserva del trabajo.")
    root = renderer.raiz_trabajo(user_id, job_id)
    estado = _sesion_lista(renderer.leer_estado(user_id, job_id))
    n = estado["escena_fotos"]["fotogramas_fuente"]
    if type(fotograma) is not int or not 1 <= fotograma <= n:
        raise ValueError(f"El fotograma tiene que estar entre 1 y {n}.")
    if operacion == "foto":
        ancho, alto = dimensiones(estado["orientacion"], resolucion or "")
        disk.assert_photo_budget(root, resolucion)
    else:
        formato = estado["escena_fotos"]["formato"]
        ancho, alto = ((LADO_VISTA, round(LADO_VISTA * formato["alto"] / formato["ancho"]))
                       if formato["ancho"] >= formato["alto"] else
                       (round(LADO_VISTA * formato["ancho"] / formato["alto"]), LADO_VISTA))
    hilos = cpu.validar_hilos(cpu_hilos) if dispositivo == "cpu" else None
    if dispositivo == "gpu" and not capacidad.get("foto_gpu_disponible"):
        raise SesionNoDisponible(capacidad.get("motivo_foto_gpu") or "Cycles no encontró una GPU en este equipo.")
    n_foto = len(estado.get("fotos") or []) + 1
    op = {"tipo": operacion, "estado": "en_cola", "fotograma": fotograma, "dispositivo": dispositivo,
          "ancho": ancho, "alto": alto, "muestras": MUESTRAS_FOTO if operacion == "foto" else MUESTRAS_VISTA,
          "resolucion": resolucion if operacion == "foto" else None, "cpu_hilos": hilos,
          "nombre": (f"foto_{n_foto:02d}_{_sufijo(estado)}" if operacion == "foto"
                     else f"vista_{fotograma:04d}_{_sufijo(estado)}"),
          "pedido_s": time.time()}
    estado.update({"estado": "renderizando", "fase": operacion, "operacion": op, "motivo": None,
                   "renderizador": {**estado["renderizador"], **capacidad, **cpu.recursos()}})
    renderer.guardar_estado(root, estado)
    renderer.encolar(job_id, _tomar, root, estado)
    return estado


def _tomar(root: Path, estado: dict[str, Any]) -> None:
    output = root / "salida"
    op = estado["operacion"]
    try:
        cmd = _comando(estado["renderizador"], "tomar",
                       "--escena", ruta_para_programa(output / estado["escena_fotos"]["archivo"]),
                       "--fotograma", str(op["fotograma"]), "--ancho", str(op["ancho"]), "--alto", str(op["alto"]),
                       "--muestras", str(op["muestras"]), "--nombre", op["nombre"],
                       "--carpeta", ruta_para_programa(output), "--blender", ruta_para_programa(estado["renderizador"]["blender"]),
                       "--dispositivo", op["dispositivo"])
        hilos = _lanzar(root, estado, cmd, hilos=op["cpu_hilos"], limite_s=LIMITE_FOTO_S[op["dispositivo"]],
                        registro="fotos.log")
        acta_path = _dentro(output, f"{op['nombre']}.json")
        acta = _verificar_acta(_json(acta_path), estado, op, hilos)
        bruto = _dentro(output, acta["png"]["archivo"])
        if marca_foto.sha256(bruto) != acta["png"]["sha256"]:
            raise RuntimeError("La foto del motor no coincide con su SHA-256.")
        if op["tipo"] == "foto":
            estado["fotos"] = [*(estado.get("fotos") or []), _entregar(root, estado, op, acta, acta_path, bruto)]
        else:
            vistas = dict(estado.get("vistas") or {})
            vistas[str(op["fotograma"])] = {"archivo": bruto.name, "sha256": acta["png"]["sha256"],
                                            "acta": acta_path.name, "segundos": acta.get("segundos"),
                                            "creado_s": time.time()}
            for viejo in sorted(vistas, key=lambda k: vistas[k].get("creado_s") or 0)[:-MAXIMO_VISTAS]:
                _borrar_de(output, vistas.pop(viejo))
            estado["vistas"] = vistas
        estado["ultima_operacion"] = {**op, "estado": "completo", "terminado_s": time.time()}
    except InterruptedError as exc:
        estado["ultima_operacion"] = {**op, "estado": "cancelado", "motivo": str(exc)}
    except (OSError, RuntimeError, subprocess.TimeoutExpired, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        estado["ultima_operacion"] = {**op, "estado": "fallido", "motivo": _motivo(exc)}
    finally:
        entregada = any(f.get("acta") == f"{op['nombre']}.json" for f in estado.get("fotos") or [])
        if op["tipo"] == "foto" and not entregada:
            # Una foto que no se entregó no deja en la carpeta su PNG sin marca: lo que sale de Molcy siempre la lleva.
            (output / f"{op['nombre']}.png").unlink(missing_ok=True)
        # La escena preparada sigue sirviendo pase lo que pase con esta foto.
        estado.update({"estado": "completo", "fase": None})
        estado.pop("operacion", None)
        _cerrar(root, estado)


def _borrar_de(carpeta: Path, entrada: dict[str, Any]) -> None:
    for clave in ("archivo", "acta"):
        try:
            _dentro(carpeta, entrada.get(clave)).unlink()
        except (RuntimeError, OSError):
            pass


def _verificar_acta(acta: dict[str, Any], estado: dict[str, Any], op: dict[str, Any], hilos: int) -> dict[str, Any]:
    """Lo que el acta tiene que acreditar para entregar la foto: lo pedido, con Cycles, de ESTA escena."""
    ajustes = acta.get("render_ajustes") or {}
    png = acta.get("png") or {}
    problemas = []
    if acta.get("schema") != "molcy.foto/1":
        problemas.append("no es un acta de foto")
    if acta.get("fotograma") != op["fotograma"]:
        problemas.append("otro fotograma")
    if (png.get("ancho"), png.get("alto")) != (op["ancho"], op["alto"]):
        problemas.append("otra resolución")
    if png.get("archivo") != f"{op['nombre']}.png":
        problemas.append("otro fichero")
    if ajustes.get("motor") != "CYCLES" or ajustes.get("dispositivo") != op["dispositivo"].upper():
        problemas.append("otro renderizador")
    if ajustes.get("muestras") != op["muestras"]:
        problemas.append("otras muestras")
    if (acta.get("escena") or {}).get("sha256") != estado["escena_fotos"]["sha256"]:
        problemas.append("otra escena")
    if acta.get("blend_sha256") != estado["escena_fotos"]["blend_sha256"]:
        problemas.append("otro .blend")
    if (op["dispositivo"] == "cpu" and estado["renderizador"].get("cpu_hilos_configurables")
            and ajustes.get("hilos_cpu") != hilos):
        problemas.append("otros hilos de CPU")
    if problemas:
        raise RuntimeError("El acta de la foto no acredita lo pedido: " + ", ".join(problemas) + ".")
    return acta


def _entregar(root: Path, estado: dict[str, Any], op: dict[str, Any], acta: dict[str, Any],
              acta_path: Path, bruto: Path) -> dict[str, Any]:
    """Marca y procedencia sobre la foto del motor; el PNG sin marca no se queda en la carpeta."""
    from core.version import APP_VERSION

    output = root / "salida"
    n = len(estado.get("fotos") or []) + 1
    nombre = f"{estado['pdb_id']}_{estado['escena']}_{op['fotograma']:04d}_{op['ancho']}x{op['alto']}_{n:02d}.png"
    if Path(nombre).name != nombre:
        raise RuntimeError("Nombre de foto inválido.")
    cfg = estado["renderizador"]
    ajustes = acta.get("render_ajustes") or {}
    fuente = estado.get("fuente") or {}
    creado = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    procedencia = {
        "schema": "moldesign.molcy.foto/1", "moldesign": APP_VERSION, "creado": creado,
        "molcy": {"motor_commit": cfg.get("motor_commit"), "motor_licencia": cfg.get("motor_licencia"),
                  "blender": ajustes.get("blender")},
        "escena": estado["escena"], "guion": acta.get("guion"), "formato": acta.get("formato"),
        "fotograma": op["fotograma"], "fotogramas_fuente": acta.get("fotogramas_fuente"),
        "beat": acta.get("beat"), "momento": acta.get("momento"), "tipo": acta.get("tipo"),
        "resolucion": [op["ancho"], op["alto"]], "ppp": marca_foto.PPP,
        "render": _render_resumido(ajustes),
        "fuente": {k: fuente.get(k) for k in ("origen", "task_id", "molecule_id", "pdb_id", "target_name", "chain",
                                             "receptor_sha256", "poses_sha256") if fuente.get(k) is not None},
        "png_del_motor_sha256": acta["png"]["sha256"],
        "escena_sha256": estado["escena_fotos"]["sha256"],
        "ajustes": estado.get("ajustes"), "ajustes_sha256": estado.get("ajustes_sha256"),
    }
    receptor = fuente.get("target_name") or estado["pdb_id"]
    textos = {
        "Title": f"{receptor} · {estado['pdb_id']} · Molcy",
        "Software": f"MolDesign {APP_VERSION} · Molcy {str(cfg.get('motor_commit') or '')[:7]} · Blender {ajustes.get('blender') or ''}".strip(),
        "Source": "MolDesign · Molcy (Cycles)",
        "Description": (f"Escena {estado['escena']} de {estado['pdb_id']}, fotograma {op['fotograma']}"
                        + (f", corrida {fuente['task_id']}" if fuente.get("task_id") else "")
                        + ". Evidencia computacional: no sustituye la validación experimental."),
        "Creation Time": creado,
    }
    destino = output / nombre
    marca = marca_foto.aplicar(bruto, destino, esquinas=acta["png"].get("esquinas"),
                               procedencia=procedencia, textos=textos)
    bruto.unlink()
    return {"id": f"{n:02d}", "archivo": nombre, "sha256": marca["sha256"], "bytes": marca["bytes"],
            "fotograma": op["fotograma"], "momento": acta.get("momento"), "tipo": acta.get("tipo"),
            "beat": acta.get("beat"), "resolucion": op["resolucion"], "ancho": op["ancho"], "alto": op["alto"],
            "dispositivo": op["dispositivo"], "cpu_hilos": op["cpu_hilos"],
            "render": _render_resumido(ajustes), "segundos": acta.get("segundos"),
            "marca": {k: marca[k] for k in ("esquina", "lado_px", "alto_px", "opacidad")},
            "acta": acta_path.name, "png_del_motor_sha256": acta["png"]["sha256"],
            "equipo": _equipo(op["dispositivo"], cfg), "creado_s": time.time()}


def _equipo(dispositivo: str, cfg: dict[str, Any]) -> str:
    """Qué equipo hizo la foto, para comparar tiempos sólo con otros del mismo."""
    if dispositivo == "gpu":
        return "gpu:" + "|".join([str(cfg.get("foto_gpu_tipo"))] + list(cfg.get("foto_gpu_nombres") or []))
    return "cpu:" + str(cfg.get("cpu_equipo_sha256"))


# ── lectura ──────────────────────────────────────────────────────────────
def ruta_de(user_id: str, job_id: str, clase: str, clave: str) -> tuple[Path, str]:
    """(ruta, sha256) de una miniatura (`toma`, por fotograma), una vista (`vista`, por fotograma) o una foto (`foto`, por id)."""
    value = renderer.leer_estado(user_id, job_id)
    if value is None or value.get("tipo") != "fotos":
        raise LookupError("Sesión de fotos no encontrada.")
    output = renderer.raiz_trabajo(user_id, job_id) / "salida"
    if clase == "toma":
        entrada = next((m for m in value.get("momentos") or [] if str(m.get("fotograma")) == clave), None)
        if entrada is None:
            raise LookupError("Toma no encontrada.")
        path = _dentro(output / f"tomas_{_sufijo(value)}", entrada["miniatura"])
        return path, entrada["miniatura_sha256"]
    if clase == "vista":
        entrada = (value.get("vistas") or {}).get(clave)
    elif clase == "foto":
        entrada = next((f for f in value.get("fotos") or [] if f.get("id") == clave), None)
    else:
        raise LookupError("Clase desconocida.")
    if not entrada:
        raise LookupError("Imagen no encontrada.")
    return _dentro(output, entrada["archivo"]), entrada["sha256"]


def leer_png(user_id: str, job_id: str, clase: str, clave: str) -> bytes:
    try:
        path, esperado = ruta_de(user_id, job_id, clase, clave)
    except RuntimeError as exc:
        raise LookupError(str(exc)) from exc
    datos = path.read_bytes()
    if hashlib.sha256(datos).hexdigest() != esperado:
        raise ValueError("La imagen ya no coincide con su SHA-256.")
    return datos


def estimar(trabajos: list[dict[str, Any]], *, orientacion: str, resolucion: str, dispositivo: str,
            capacidad: dict[str, Any], cpu_hilos: int | None = None) -> dict[str, Any]:
    """Cuánto tardará una foto, medido con las fotos anteriores de ESTE equipo (y, en CPU, con los mismos hilos).

    Sin fotos anteriores no se inventa un número. El tiempo de la escena se escala por megapíxeles; lo demás (abrir la escena,
    la capa de rótulos) se suma tal cual.
    """
    ancho, alto = dimensiones(orientacion, resolucion)
    equipo = _equipo(dispositivo, {**capacidad, **cpu.recursos()})
    muestras = []
    for job in trabajos[:40]:
        if job.get("tipo") != "fotos":
            continue
        for foto in reversed(job.get("fotos") or []):
            segundos = foto.get("segundos") or {}
            mp = (foto.get("ancho") or 0) * (foto.get("alto") or 0) / 1e6
            escena_s, total_s = segundos.get("escena"), segundos.get("total")
            if (foto.get("equipo") != equipo or foto.get("dispositivo") != dispositivo or mp <= 0
                    or (dispositivo == "cpu" and foto.get("cpu_hilos") != cpu_hilos)
                    or type(escena_s) not in (int, float) or type(total_s) not in (int, float)
                    or escena_s <= 0 or total_s < escena_s):
                continue
            muestras.append((escena_s / mp, total_s - escena_s))
    if not muestras:
        return {"estimado_s": None, "muestras": 0}
    muestras = muestras[:5]
    estimado = statistics.median(r for r, _ in muestras) * ancho * alto / 1e6 + statistics.median(o for _, o in muestras)
    return {"estimado_s": round(estimado), "muestras": len(muestras)}


def detalles(user_id: str, value: dict[str, Any]) -> dict[str, Any]:
    """Para el historial: la ruta local de la última foto, si sigue intacta."""
    fotos = value.get("fotos") or []
    if not fotos:
        return {}
    try:
        path, _ = ruta_de(user_id, value["id"], "foto", fotos[-1]["id"])
        return {"foto_ruta": str(path.resolve())}
    except (LookupError, RuntimeError, OSError, ValueError):
        return {}


def ultima_foto(user_id: str, job_id: str) -> Path:
    value = renderer.leer_estado(user_id, job_id)
    fotos = (value or {}).get("fotos") or []
    if not fotos:
        raise LookupError("Esta sesión todavía no tiene fotos.")
    path, esperado = ruta_de(user_id, job_id, "foto", fotos[-1]["id"])
    if marca_foto.sha256(path) != esperado:
        raise ValueError("La foto ya no coincide con su SHA-256.")
    storage.validar_raiz(user_id, job_id, renderer.raiz_trabajo(user_id, job_id))
    return path
