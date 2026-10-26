"""Presupuesto vigilado de VRAM. EEVEE no ofrece una cuota de asignación.

NVML mide la tarjeta completa: actividad de terceros también puede detener el
render. Se vigila sólo una tarjeta NVIDIA identificada por el sondeo de Blender;
si no podemos medirla o identificarla, nos abstenemos de ofrecer GPU protegida.
"""
from __future__ import annotations

import ctypes
import math
import os
import time
from functools import lru_cache
from pathlib import Path

MIB = 2**20


@lru_cache(maxsize=1)
def _biblioteca():
    path = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "nvml.dll"
    library = ctypes.CDLL(str(path) if os.name == "nt" else "libnvidia-ml.so.1")
    library.nvmlInit_v2.argtypes = []
    library.nvmlInit_v2.restype = ctypes.c_int
    if library.nvmlInit_v2() != 0:
        raise OSError("No se pudo iniciar la medición de VRAM.")
    for name, args in {
        "nvmlDeviceGetCount_v2": [ctypes.POINTER(ctypes.c_uint)],
        "nvmlDeviceGetHandleByIndex_v2": [ctypes.c_uint, ctypes.POINTER(ctypes.c_void_p)],
        "nvmlDeviceGetName": [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint],
        "nvmlDeviceGetUUID": [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint],
        "nvmlDeviceGetMemoryInfo": [ctypes.c_void_p, ctypes.c_void_p],
    }.items():
        function = getattr(library, name)
        function.argtypes = args
        function.restype = ctypes.c_int
    return library


def _tarjetas() -> list[dict]:
    class Memory(ctypes.Structure):
        _fields_ = [("total", ctypes.c_ulonglong), ("free", ctypes.c_ulonglong), ("used", ctypes.c_ulonglong)]
    try:
        library = _biblioteca()
        count = ctypes.c_uint()
        if library.nvmlDeviceGetCount_v2(ctypes.byref(count)) != 0:
            return []
        cards = []
        for index in range(min(count.value, 32)):
            handle = ctypes.c_void_p()
            name, uuid = ctypes.create_string_buffer(96), ctypes.create_string_buffer(96)
            memory = Memory()
            calls = [library.nvmlDeviceGetHandleByIndex_v2(index, ctypes.byref(handle))]
            if calls[0] != 0:
                continue
            calls += [library.nvmlDeviceGetName(handle, name, len(name)),
                      library.nvmlDeviceGetUUID(handle, uuid, len(uuid)),
                      library.nvmlDeviceGetMemoryInfo(handle, ctypes.byref(memory))]
            if any(calls) or not memory.total or memory.free > memory.total or memory.used > memory.total:
                continue
            cards.append({"uuid": uuid.value.decode("utf-8"), "nombre": name.value.decode("utf-8"),
                          "total_mib": memory.total // MIB, "libre_mib": memory.free // MIB,
                          "usada_mib": math.ceil(memory.used / MIB)})
        return cards
    except (OSError, AttributeError, UnicodeError):
        return []


def recursos(capacidad: dict) -> dict:
    cards = _tarjetas() if "nvidia" in capacidad.get("gpu_vendor", "").lower() else []
    matches = [card for card in cards if card["nombre"].casefold() in capacidad.get("gpu_nombre", "").casefold()]
    result = {"gpu_vram_monitorizable": False}
    if len(matches) != 1:
        return result
    card = matches[0]
    reserve = max(1024, math.ceil(card["total_mib"] * 0.25))
    maximum = max(0, (card["libre_mib"] - reserve) // 128 * 128)
    return {**result, "gpu_vram_monitorizable": True, "gpu_vram_uuid": card["uuid"],
            "gpu_vram_total_mib": card["total_mib"], "gpu_vram_libre_mib": card["libre_mib"],
            "gpu_vram_usada_mib": card["usada_mib"], "gpu_vram_reserva_mib": reserve,
            "gpu_vram_max_mib": maximum,
            "gpu_vram_recomendado_mib": min(maximum, max(128, min(2048, maximum // 2 // 128 * 128)))}


def validar_presupuesto(value: int | None, info: dict) -> dict:
    if not info.get("gpu_vram_monitorizable"):
        raise ValueError("No podemos vigilar la VRAM de la tarjeta utilizada por Blender. Elige CPU.")
    maximum = info["gpu_vram_max_mib"]
    selected = info["gpu_vram_recomendado_mib"] if value is None else value
    if type(selected) is not int or not 128 <= selected <= maximum:
        raise ValueError(f"Con la VRAM libre actual puedes elegir de 128 a {maximum} MiB adicionales. Actualiza los recursos o elige CPU.")
    return {**info, "gpu_vram_presupuesto_mib": selected}


class Vigilancia:
    """Umbral de parada a intervalos de 1 s, nunca una reserva de memoria."""
    def __init__(self, info: dict):
        self.info = info
        self.last = -math.inf

    def __call__(self):
        now = time.monotonic()
        if now - self.last < 1:
            return
        self.last = now
        current = next((card for card in _tarjetas() if card["uuid"] == self.info["gpu_vram_uuid"]), None)
        if current is None:
            raise RuntimeError("Se perdió la medición de VRAM. Molcy detuvo el render; elige CPU o vuelve a comprobar la GPU.")
        if (current["libre_mib"] < self.info["gpu_vram_reserva_mib"] or
                current["usada_mib"] - self.info["gpu_vram_usada_mib"] > self.info["gpu_vram_presupuesto_mib"]):
            raise RuntimeError("Molcy detuvo el render porque se superó el presupuesto de VRAM o cayó el margen libre. Cierra aplicaciones, ajusta el presupuesto o elige CPU.")
