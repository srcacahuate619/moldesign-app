"""Distingue «el peso no se distribuye» de «el peso esta roto».

El repositorio publica codigo, manifiestos, metadatos y hashes; los pesos
entrenados viajan aparte, bajo su propia licencia. En la maquina del mantenedor
estan todos, asi que la diferencia era invisible: cualquier gate o prueba que
tocara un `.pt` pasaba en local y reventaba en un clon limpio con un
FileNotFoundError que no explicaba nada.

Un artefacto ausente no es un fallo del contrato: es un artefacto que no viene
en el paquete. Un artefacto presente con el hash cambiado si lo es. Este modulo
sostiene esa distincion en un solo sitio.

Salida de emergencia: `RESCORING_EXIGE_PESOS=1` convierte la ausencia en fallo.
Donde los pesos SI estan —la maquina del mantenedor, el job de release que los
descarga— nadie quiere una omision silenciosa si desaparecen.
"""

from __future__ import annotations

import os
from pathlib import Path

#: Extensiones de peso entrenado que el repositorio Git no distribuye.
EXTENSIONES_DE_PESO = (".pt", ".pth", ".ckpt", ".safetensors", ".bin", ".onnx")

VARIABLE_EXIGIR = "RESCORING_EXIGE_PESOS"


def se_exigen_pesos() -> bool:
    return os.environ.get(VARIABLE_EXIGIR) == "1"


def pesos_ausentes(directorio: Path, nombres: object) -> list[str]:
    """Los nombres declarados que son peso entrenado y no estan en disco."""
    faltan = []
    for nombre in nombres:
        if not str(nombre).endswith(EXTENSIONES_DE_PESO):
            continue
        if not (directorio / str(nombre)).exists():
            faltan.append(str(nombre))
    return sorted(faltan)


def motivo(faltan: list[str], contexto: str = "") -> str:
    detalle = ", ".join(faltan)
    sufijo = f" ({contexto})" if contexto else ""
    return (
        f"pesos entrenados no distribuidos por el repositorio Git: {detalle}{sufijo}. "
        f"Se descargan aparte bajo LICENSE-MODELS; define {VARIABLE_EXIGIR}=1 "
        "para exigir su presencia."
    )
