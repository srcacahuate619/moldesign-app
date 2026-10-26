"""El cierre de MolDesign es obligatorio en todo video: esto es lo que el backend exige antes de dar un video por completo.

La firma de marca al final de cada video generado es parte del producto. El motor ya no ofrece ningún mando para quitarla (ver `tools/molcy`,
`variables/formato.py`), pero el backend no se fía de una sola afirmación: además del acta (que escribe el propio motor) mide el MP4 con un
analizador de contenedor de biblioteca estándar. Un video que dura lo de la escena y no lo de la escena MÁS el cierre no se entrega.

Qué NO impide, y conviene decirlo: el motor es GPL y quien lo modifique puede quitar el cierre de SU copia; el motor incluido se verifica contra
su manifiesto (`motor.py`) y en esta aplicación no hay forma de elegir otro motor desde la pantalla. Quitarlo de un video ya generado es editar
el video a mano, como cualquier otro.
"""
from __future__ import annotations

import math
import struct
from pathlib import Path
from typing import Any

#: Segundos mínimos del cierre. Los formatos del motor traen 3,6 s (previsualización y vertical) y 4,4 s (horizontal).
CIERRE_MINIMO_S = 3.0
#: Cuánto puede quedarse corto el MP4 respecto de lo que declara el acta (redondeo de fotogramas y del contenedor).
TOLERANCIA_S = 0.25

MENSAJE_SIN_CIERRE = "El acta no acredita el cierre de MolDesign; el video no se entrega."
MENSAJE_SIN_DURACION = "El video no dura lo que declara su acta: falta el cierre de MolDesign."


def _numero(valor: Any) -> bool:
    return isinstance(valor, (int, float)) and not isinstance(valor, bool) and math.isfinite(valor)


def duracion_mp4_s(ruta: Path) -> float | None:
    """Duración (s) de la cabecera `mvhd` de un MP4, o None si no es un MP4 legible. Sólo biblioteca estándar.

    Recorre las cajas de primer nivel sin leer `mdat` (los fotogramas), así que cuesta lo mismo en un video de 2 MB que en uno de 2 GB.
    """
    try:
        with ruta.open("rb") as flujo:
            tamano_total = ruta.stat().st_size
            posicion = 0
            while posicion + 8 <= tamano_total:
                flujo.seek(posicion)
                cabecera = flujo.read(8)
                if len(cabecera) < 8:
                    return None
                tamano, tipo = struct.unpack(">I4s", cabecera)
                inicio_datos = posicion + 8
                if tamano == 1:                                  # tamaño de 64 bits a continuación
                    ampliado = flujo.read(8)
                    if len(ampliado) < 8:
                        return None
                    tamano = struct.unpack(">Q", ampliado)[0]
                    inicio_datos += 8
                elif tamano == 0:                                # hasta el final del fichero
                    tamano = tamano_total - posicion
                if tamano < inicio_datos - posicion:
                    return None
                if tipo == b"moov":
                    return _duracion_en_moov(flujo, inicio_datos, posicion + tamano)
                posicion += tamano
    except (OSError, struct.error):
        return None
    return None


def _duracion_en_moov(flujo, inicio: int, fin: int) -> float | None:
    if fin - inicio > 64 * 1024 * 1024:                         # una `moov` real pesa kilobytes
        return None
    flujo.seek(inicio)
    datos = flujo.read(fin - inicio)
    posicion = 0
    while posicion + 8 <= len(datos):
        tamano, tipo = struct.unpack(">I4s", datos[posicion:posicion + 8])
        if tamano < 8:
            return None
        if tipo == b"mvhd":
            cuerpo = datos[posicion + 8:posicion + tamano]
            version = cuerpo[0] if cuerpo else None
            if version == 0 and len(cuerpo) >= 20:
                escala, duracion = struct.unpack(">II", cuerpo[12:20])
            elif version == 1 and len(cuerpo) >= 32:
                escala, duracion = struct.unpack(">IQ", cuerpo[20:32])
            else:
                return None
            return duracion / escala if escala else None
        posicion += tamano
    return None


def verificar(acta: dict[str, Any], video: Path, *, idioma: str = "es") -> None:
    """Lanza RuntimeError si el video no lleva, de verdad y según su acta, el cierre de MolDesign."""
    formato = acta.get("formato")
    cierre = acta.get("cierre")
    if not isinstance(formato, dict) or not isinstance(cierre, dict):
        raise RuntimeError(MENSAJE_SIN_CIERRE)
    expected = "en" if idioma == "en" else "es"
    motto = "REPRODUCIBLE STRUCTURAL EVIDENCE" if expected == "en" else "EVIDENCIA ESTRUCTURAL REPRODUCIBLE"
    if cierre.get("idioma") != expected or cierre.get("lema") != motto:
        raise RuntimeError("El acta no acredita el cierre de MolDesign en el idioma pedido con un lema válido.")
    cierre_s = formato.get("cierre_s")
    if not _numero(cierre_s) or cierre_s < CIERRE_MINIMO_S:
        raise RuntimeError(MENSAJE_SIN_CIERRE)
    if (not _numero(cierre.get("segundos")) or abs(cierre["segundos"] - cierre_s) > 0.1
            or not _numero(cierre.get("fotogramas")) or cierre["fotogramas"] <= 0 or not cierre.get("huella")):
        raise RuntimeError(MENSAJE_SIN_CIERRE)
    escena = acta.get("duracion_s")
    declarado = (acta.get("video") or {}).get("segundos")
    if not _numero(escena) or escena <= 0 or not _numero(declarado):
        raise RuntimeError(MENSAJE_SIN_CIERRE)
    esperado = escena + cierre_s
    if abs(declarado - esperado) > TOLERANCIA_S:
        raise RuntimeError(MENSAJE_SIN_CIERRE)
    real = duracion_mp4_s(video)
    if real is None or real < esperado - TOLERANCIA_S:
        raise RuntimeError(MENSAJE_SIN_DURACION)
