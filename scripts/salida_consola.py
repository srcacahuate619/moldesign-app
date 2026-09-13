"""Escribir en la consola sin que un carácter tire el proceso.

# El fallo que arregla

En Windows, `python script.py > archivo` o `python script.py | otra-cosa` deja
`sys.stdout` con la codificación del sistema —**cp1252** en una instalación en
español— y no con UTF-8. Cualquier carácter fuera de esa tabla deja de ser un
detalle tipográfico y se convierte en un `UnicodeEncodeError` que aborta el
programa **después** de haber hecho el trabajo:

    UnicodeEncodeError: 'charmap' codec can't encode character '\\u2192'

Medido el 2026-09-06: `check_openbabel_boundary.py` completó sus nueve
comprobaciones, todas verdes, y murió con código 1 al imprimir una flecha `→`.
Un gate que aprueba y luego revienta al escribir el informe es indistinguible de
un gate que falla, y en CI habría bloqueado el build por un byte.

`generate_sbom.py` ya había pagado esta lección y la resolvió evitando emoji.
Evitar caracteres funciona hasta que alguien escribe `…` sin pensarlo; esto
arregla la causa en vez del síntoma.

# Por qué `errors="replace"` y no fallar

Porque el mensaje es el informe, no el resultado. Si la consola no sabe pintar
una flecha, es preferible un `?` en el texto a perder el trabajo hecho. El
código de salida —que es lo que lee CI— deja de depender de la tabla de
caracteres del sistema operativo, que es todo lo que se pretende.

# Uso

    from salida_consola import consola_utf8
    consola_utf8()

Se llama una vez, al principio. Es idempotente y no hace nada si la salida ya
admite UTF-8.
"""

from __future__ import annotations

import sys


def consola_utf8() -> None:
    """Deja `stdout` y `stderr` en UTF-8 tolerante. Idempotente."""
    for flujo in (sys.stdout, sys.stderr):
        # `reconfigure` existe en los flujos de texto desde 3.7. Si alguien
        # redirigió la salida a un objeto propio que no lo tenga, no se toca:
        # romper la salida por intentar arreglarla sería el mismo error, al revés.
        reconfigurar = getattr(flujo, "reconfigure", None)
        if reconfigurar is None:
            continue
        try:
            reconfigurar(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            # Flujo ya cerrado o no reconfigurable. El programa sigue: esto es
            # una comodidad de presentación, nunca un requisito.
            pass
