"""Recursos y proyecciones CPU locales; no inicia Blender ni descarga nada."""
from __future__ import annotations

import ctypes
import hashlib
import json
import math
import os
import platform
from pathlib import Path
from typing import Any


def _afinidad() -> int | None:
    try:
        if hasattr(os, "sched_getaffinity"):
            return len(os.sched_getaffinity(0))
        if os.name == "nt":
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel.GetCurrentProcess.restype = ctypes.c_void_p
            kernel.GetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t), ctypes.POINTER(ctypes.c_size_t)]
            process_mask, system_mask = ctypes.c_size_t(), ctypes.c_size_t()
            if kernel.GetProcessAffinityMask(kernel.GetCurrentProcess(), ctypes.byref(process_mask), ctypes.byref(system_mask)):
                return process_mask.value.bit_count() or None
    except (OSError, AttributeError):
        pass
    return None


def _modelo() -> str:
    if os.name == "nt":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as key:
                return str(winreg.QueryValueEx(key, "ProcessorNameString")[0]).strip()
        except OSError:
            pass
    return platform.processor()


def recursos() -> dict[str, Any]:
    total = max(1, os.cpu_count() or 1)
    available = max(1, min(total, _afinidad() or total, 1024))
    # Identidad local conservadora: evita reutilizar medidas de otra CPU/afinidad.
    model = _modelo()
    identity = [model, platform.machine(), total, available, "molcy-cpu-headroom/1"]
    # El margen es una política de MolDesign, no una promesa de núcleos ociosos.
    reserve = max(1, math.ceil(available * 0.25))
    load = _carga_actual()
    maximum = max(1, available - reserve)
    if load is not None:
        maximum = min(maximum, max(1, math.floor(available * (1 - load / 100)) - reserve))
    return {"cpu_modelo": model, "cpu_logicos": total, "cpu_hilos_disponibles": available,
            "cpu_hilos": min(maximum, max(1, available // 2)),
            "cpu_hilos_maximos": maximum, "cpu_hilos_reserva": min(reserve, available),
            "cpu_uso_actual_pct": load,
            "cpu_equipo_sha256": hashlib.sha256(json.dumps(identity).encode()).hexdigest()}


def _carga_actual() -> float | None:
    try:
        import psutil
        value = psutil.cpu_percent(interval=0.2)
        return round(value, 1) if math.isfinite(value) and 0 <= value <= 100 else None
    except (ImportError, OSError):
        return None


def maximo_hilos(info: dict) -> int:
    available = info["cpu_hilos_disponibles"]
    return min(max(1, available - math.ceil(available * 0.25)), info.get("cpu_hilos_maximos", available))


def validar_hilos(value: int | None, info: dict | None = None) -> int:
    info = info or recursos()
    maximum = maximo_hilos(info)
    selected = min(info["cpu_hilos"], maximum) if value is None else value
    if type(selected) is not int or not 1 <= selected <= maximum:
        raise ValueError(f"Con la carga actual puedes usar entre 1 y {maximum} hilos. Dejamos margen para otras aplicaciones; actualiza los recursos y vuelve a intentarlo.")
    return selected


def huella_motor(engine: Path) -> str:
    digest = hashlib.sha256()
    paths = sorted((engine / "scripts").rglob("*.py")) + sorted((engine / "scripts").rglob("*.ps1"))
    paths += [engine / "moldesign/assets/blender/plantilla_arte.blend"]
    for path in paths:
        if path.is_file():
            digest.update(path.relative_to(engine).as_posix().encode() + path.read_bytes())
    return digest.hexdigest()
