"""Motores que no caben en el instalador y se descargan bajo demanda.

`catalogo` dice qué existe y en qué estado está; `sidecar` lo enciende.
"""

from services.motores.catalogo import (  # noqa: F401
    CATALOGO,
    POR_ID,
    EstadoMotor,
    MotorDescargable,
    estado_de,
)
from services.motores.sidecar import (  # noqa: F401
    MotorSidecar,
    estados_de_motores_descargables,
    sidecar_de,
)
