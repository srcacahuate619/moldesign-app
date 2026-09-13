"""
Lanzar un ejecutable de consola sin que parpadee una ventana negra.

# El fallo que arregla, y por qué el patrón anterior no arreglaba nada

En Windows, un `.exe` de consola lanzado desde un proceso GUI —que es lo que es
Tauri en producción— abre su propia ventana de consola salvo que se le pase
`CREATE_NO_WINDOW` (0x08000000). Vina, Open Babel y los subprocesos de MM-GBSA
corren decenas de veces por evaluación, así que el usuario ve destellos de CMD
y pierde el foco de la ventana mientras trabaja.

Tres sitios del backend ya intentaban evitarlo así:

    creationflags=getattr(_asyncio.subprocess, "CREATE_NO_WINDOW", 0)

**Ese `getattr` devuelve 0 siempre.** La constante vive en el módulo
`subprocess` de la biblioteca estándar, no en `asyncio.subprocess`, que sólo
expone `DEVNULL`, `PIPE`, `STDOUT`, `Process` y las dos funciones de creación.
Comprobado sobre el intérprete que se empaqueta (Python 3.11.9):

    hasattr(asyncio.subprocess, "CREATE_NO_WINDOW")  ->  False
    getattr(asyncio.subprocess, "CREATE_NO_WINDOW", 0) ->  0
    subprocess.CREATE_NO_WINDOW                       ->  0x8000000

Es decir: el valor por defecto del `getattr` convirtió un error de módulo en un
silencio. Los tres sitios «protegidos» pasaban `creationflags=0`, que es
exactamente lo mismo que no pasar nada. El idioma correcto ya existía en
`services/ai/local_llm.py` y `services/motores/sidecar.py`, sobre `subprocess`.

# Por qué una constante y no un `getattr` en cada sitio

Porque la forma equivocada se copió tres veces, y una auditoría externa
recomendó copiarla cuatro veces más. Con un solo nombre importable, el error no
se puede replicar sin verlo.

`CREATE_NEW_PROCESS_GROUP` va incluido: sin él, un Ctrl-C en la consola padre se
propaga a los hijos y mata un acoplamiento en curso.

En cualquier sistema que no sea Windows el valor es 0, que es lo que
`subprocess` exige ahí.
"""

from __future__ import annotations

import subprocess
import sys

#: `creationflags` para un ejecutable de consola que no debe mostrar ventana.
#: 0 fuera de Windows, donde el argumento debe ir a cero.
BANDERAS_SIN_VENTANA: int = 0

if sys.platform == "win32":
    BANDERAS_SIN_VENTANA = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) | getattr(
        subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200
    )
