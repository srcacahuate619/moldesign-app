# Molcy: licencia y procedencia

**Licencia: GNU General Public License v3.0 o posterior** (`GPL-3.0-or-later`). El texto completo está en `LICENSE`, copiado sin
cambios de la distribución de Blender 5.2.2 (`license/spdx/GPL-3.0-or-later.txt`).

## Por qué GPL

Este código se ejecuta *dentro* de Blender (`blender -b --python scripts/maestro.py`), usa su API de Python (`bpy`) y activa la extensión
Molecular Nodes para construir la escena. Blender se publica bajo GPL-3.0-or-later (© Blender Foundation) y Molecular Nodes declara
`SPDX:GPL-3.0-or-later` (© 2022 Brady Johnston). Un programa que importa `bpy` y se carga en Blender se publica bajo una licencia GPL
compatible; GPL-3.0-or-later es la que coincide con la de Molecular Nodes.

Esto no es asesoramiento jurídico. Quien lo distribuya debe ofrecer el código fuente completo y conservar este aviso.

## Código fuente

El código fuente completo y correspondiente de cada versión que viaja con MolDesign está en
<https://github.com/srcacahuate619/moldesign-molcy>. El fichero `molcy-manifest.json` de la copia incluida en MolDesign nombra el
commit exacto del que sale (`fuente.commit`) y el SHA-256 de cada fichero.

## Relación con MolDesign

MolDesign (PolyForm Noncommercial 1.0.0) lo ejecuta como **programa independiente**, por subproceso y con ruta explícita, y no importa
ninguno de sus módulos; la comunicación es por ficheros (`scene.json`, geometría, acta y MP4). La frontera está en el ADR 92 y el ADR 95
de MolDesign.

## Material que no es código

- `moldesign/assets/blender/plantilla_arte.blend`: direccion de arte (materiales, luces, etiquetas) sin claves de animación; se
  distribuye bajo esta misma licencia.
- `moldesign/assets/marca/*.png`: emblema de MolDesign usado en el cierre de los vídeos. **Nombre y emblema son marca**: la GPL concede
  derechos sobre el código y los ficheros, no sobre la marca; una versión modificada debe quitarlos o sustituirlos.

## El cierre de MolDesign en los vídeos

El motor, tal como se publica aquí, añade el cierre de MolDesign al final de **todo** vídeo y no tiene ajuste, formato ni argumento que lo
omita (`scripts/pruebas/test_cierre_obligatorio.py` lo comprueba). Eso es una decisión de diseño del motor, no una condición de la
licencia: la GPL-3.0-or-later permite modificar el código, también esa parte, y no se le añade ninguna restricción. Lo que no se concede es
el derecho a usar el nombre ni el emblema de MolDesign en una versión modificada (ver arriba). Los vídeos que genera el motor son del
usuario que los genera: la GPL sólo cubre el resultado de ejecutar un programa si ese resultado es en sí una obra derivada del programa
(GPLv3, sección 2), y Blender no restringe el uso comercial de lo que se crea con él.
