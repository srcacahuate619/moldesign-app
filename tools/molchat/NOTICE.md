# MolChat Agent: licencia y procedencia

**Licencia: GNU General Public License v3.0 o posterior** (`GPL-3.0-or-later`).
El texto completo está en `LICENSE`, copiado sin cambios del publicado en
`https://github.com/srcacahuate619/moldesign-molcy` (verificado byte a byte en
la Fase 0, SHA-256 `8ceb4b9ee5adedde47b31e975c1d90c73ad27b6b165a1dcd80c7c545eb65b903`;
allí procede de la distribución de Blender 5.2.2,
`license/spdx/GPL-3.0-or-later.txt`). No se incorporó código funcional de Molcy:
solo su texto estándar de licencia.

## Por qué GPL

MolChat Agent es un **programa independiente** que conversa, planifica y presenta
resultados, y se comunica con MolDesign por API HTTP versionada. Sigue el patrón
exacto de Molcy (ADR 92/95 de MolDesign): fuente única en su propio repositorio
público, copia vendorizada y verificada contra manifiesto en MolDesign, ejecución
como proceso independiente. `GPL-3.0-or-later` es la licencia que coincide con la
de Molcy y la que permite a terceros tomar el núcleo, escribir su propio
adaptador y devolver mejoras bajo las mismas condiciones.

Esto no es asesoramiento jurídico. Quien lo distribuya debe ofrecer el código
fuente completo y conservar este aviso.

## Código fuente

El código fuente completo y correspondiente de cada versión que viaje con
MolDesign estará en `https://github.com/srcacahuate619/moldesign-molchat`
(repositorio por crear al cierre de la Fase 0). El fichero
`molchat-manifest.json` de la copia incluida en MolDesign nombrará el commit
exacto del que sale y el SHA-256 de cada fichero (Fase 6). Hasta entonces, la
fuente de verdad es este árbol y su historial git.

## Relación con MolDesign

MolDesign (PolyForm Noncommercial 1.0.0, condiciones comerciales separadas) lo
ejecuta como **programa independiente**, lanzado como proceso propio en loopback
y sin importar ninguno de sus módulos; la comunicación es por HTTP con esquema
versionado (`moldesign.molchat.*`). MolChat no redistribuye dependencias, datos,
modelos ni el runtime científico de MolDesign. La mera conexión por API no
equivale a copiar ni a enlazar su código.

## Dependencias y servicios externos

- `httpx` (BSD-3-Clause): cliente HTTP. Compatibilidad preliminar; revisar avisos
  transitivos al distribuir un ejecutable.
- `starlette`, `uvicorn` (BSD-3-Clause): API HTTP del sidecar (extra `server`).
  Solo se usan en `molchat_agent.server`; el núcleo sigue dependiendo de `httpx`.
- Meta Model API (Muse Spark): servicio remoto opcional. La licencia GPL del
  cliente no cambia las condiciones del modelo ni del servicio; no se
  redistribuyen pesos.
- RDKit / Vina / bibliotecas científicas: siguen en MolDesign. Antes de
  distribuir un ejecutable combinado hay que auditar las obligaciones propias de
  cada dependencia.

## Marca

Los nombres y emblemas de MolDesign y Molcy **no quedan licenciados como marcas**
por la GNU GPL. Una versión modificada debe quitarlos o sustituirlos. La UI usa
la marca solo en el modo integrado con MolDesign.
