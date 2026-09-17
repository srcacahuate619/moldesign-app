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

from contextlib import suppress

import subprocess
import sys

#: `creationflags` para un ejecutable de consola que no debe mostrar ventana.
#: 0 fuera de Windows, donde el argumento debe ir a cero.
BANDERAS_SIN_VENTANA: int = 0

if sys.platform == "win32":
    BANDERAS_SIN_VENTANA = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) | getattr(
        subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200
    )


async def communicate_managed(process, *, timeout: float, max_output_bytes: int = 32 * 1024 * 1024):
    """Drena ambos pipes y recoge al hijo incluso ante timeout/cancelación.

    Se protege communicate para no perder su lector al vencer wait_for. No se
    cambian argumentos ni salidas válidas. Se rechaza la salida excesiva, sin
    truncarla y tratarla como resultado completo. El plazo es tiempo de pared.
    """
    import asyncio

    async def read_bounded(stream):
        if stream is None:
            return None
        chunks = []
        size = 0
        exceeded = False
        while chunk := await stream.read(65536):
            size += len(chunk)
            if size > max_output_bytes:
                if not exceeded:
                    kill_process_tree(process)
                    exceeded = True
            elif not exceeded:
                chunks.append(chunk)
        if exceeded:
            raise RuntimeError(f"Salida de proceso externo excedió {max_output_bytes} bytes")
        return b"".join(chunks)

    async def collect():
        # Los dobles de prueba conservan el contrato communicate; todos los
        # procesos asyncio reales usan lectura acotada de ambos pipes.
        if not isinstance(process, asyncio.subprocess.Process):
            return await process.communicate()
        if process.stdin is not None:
            process.stdin.close()
        readers = [asyncio.create_task(read_bounded(stream))
                   for stream in (process.stdout, process.stderr)]
        try:
            output = await asyncio.gather(*readers)
            await process.wait()
            return tuple(output)
        finally:
            for reader in readers:
                if not reader.done():
                    reader.cancel()
            await asyncio.gather(*readers, return_exceptions=True)

    communication = asyncio.ensure_future(collect())
    try:
        return await asyncio.wait_for(asyncio.shield(communication), timeout)
    except BaseException as exc:
        kill_process_tree(process)
        try:
            await asyncio.wait_for(asyncio.shield(communication), 5.0)
        except (Exception, asyncio.CancelledError):
            communication.cancel()
            await asyncio.gather(communication, return_exceptions=True)
        if isinstance(exc, TimeoutError):
            raise TimeoutError(f"Proceso externo excedió el límite de {timeout:g} s") from exc
        raise


def kill_process_tree(process) -> None:
    """Termina los descendientes antes del padre (psutil ya está empaquetado).

    Es best-effort ante la carrera natural con procesos que ya terminaron.
    No enumera ni mata procesos fuera del árbol del hijo recibido.
    """
    try:
        import psutil
        descendants = psutil.Process(process.pid).children(recursive=True)
    except (ImportError, AttributeError, OSError):
        descendants = []
    except psutil.Error:
        descendants = []
    for child in reversed(descendants):
        with suppress(psutil.Error):
            child.kill()
    if process.returncode is None:
        with suppress(ProcessLookupError):
            process.kill()
