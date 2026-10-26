"""Ayudas de las pruebas de Molcy: un MP4 mínimo con duración conocida y un acta que acredita el cierre de MolDesign."""
from __future__ import annotations

import struct
from pathlib import Path


def gpu_simulada(monkeypatch):
    """Telemetría estable sólo para alcanzar las guardas de acta/cierre."""
    from services.molcy import gpu
    info = {"gpu_vram_monitorizable": True, "gpu_vram_uuid": "GPU-TEST", "gpu_vram_max_mib": 4096,
            "gpu_vram_recomendado_mib": 2048, "gpu_vram_usada_mib": 1024, "gpu_vram_reserva_mib": 2048}
    monkeypatch.setattr(gpu, "recursos", lambda _: dict(info))
    monkeypatch.setattr(gpu, "_tarjetas", lambda: [{"uuid": "GPU-TEST", "usada_mib": 1024, "libre_mib": 6144}])
    return info


def caja(tipo: bytes, datos: bytes, *, ampliada: bool = False) -> bytes:
    if ampliada:
        return struct.pack(">I4sQ", 1, tipo, 16 + len(datos)) + datos
    return struct.pack(">I4s", 8 + len(datos), tipo) + datos


def mvhd(segundos: float, *, escala: int = 1000, version: int = 0) -> bytes:
    duracion = round(segundos * escala)
    if version == 1:
        cuerpo = bytes([1, 0, 0, 0]) + struct.pack(">QQIQ", 0, 0, escala, duracion) + b"\0" * 80
    else:
        cuerpo = bytes([0, 0, 0, 0]) + struct.pack(">IIII", 0, 0, escala, duracion) + b"\0" * 80
    return caja(b"mvhd", cuerpo)


def mp4_falso(segundos: float, *, escala: int = 1000, version: int = 0, moov_al_principio: bool = False,
              ampliado: bool = False) -> bytes:
    """Bytes de un MP4 mínimo (ftyp + mdat + moov/mvhd) cuya cabecera dice `segundos`. No es reproducible: sólo contiene lo que el analizador lee."""
    ftyp = caja(b"ftyp", b"isom\0\0\2\0isomiso2mp41")
    mdat = caja(b"mdat", b"\0" * 2048, ampliada=ampliado)
    moov = caja(b"moov", mvhd(segundos, escala=escala, version=version))
    return ftyp + (moov + mdat if moov_al_principio else mdat + moov)


def escribir_mp4(ruta: Path, segundos: float, **kwargs) -> Path:
    ruta.write_bytes(mp4_falso(segundos, **kwargs))
    return ruta


def acta_con_cierre(*, escena_s: float = 3.0, cierre_s: float = 3.6, **sobrescribir) -> dict:
    """El acta que escribe el motor para un video con su cierre (los campos que el backend lee)."""
    acta = {
        "formato": {"nombre": "previsualizacion", "cierre_s": cierre_s, "fps": 30},
        "fotogramas": round(escena_s * 30), "duracion_s": escena_s,
        "cierre": {"segundos": cierre_s, "fotogramas": round(cierre_s * 30), "muestras": 48, "huella": "h" * 64, "blender": "5.2.2", "idioma": "es", "lema": "EVIDENCIA ESTRUCTURAL REPRODUCIBLE"},
        "video": {"segundos": round(escena_s + cierre_s, 2)},
    }
    acta.update(sobrescribir)
    return acta
