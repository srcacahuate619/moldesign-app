# Auditoría de cierre 1.0.4: Preparación e identidad

Revisión del 2026-10-26 sobre `codex/release-hygiene`, base `2ac842cf` y los
cambios sin confirmar del árbol. La auditoría inicial fue estática; las
regresiones posteriores ejecutan los componentes o funciones indicados. No
son una prueba del instalador ni una validación científica nueva.

## Hallazgos

1. **Moldex → Preparación, mismo caso.** Si el caso ya estaba seleccionado,
   la petición de Moldex lo vaciaba y no cambiaba el ID, por lo que el efecto
   de lectura no volvía a cargarlo. El caso podía quedar sin auditoría.
2. **Guardado tardío y cambio de caso.** Una decisión de A que terminara
   después de elegir B podía volver a mostrar A bajo el selector de B. Un
   borrador también podía permanecer al cambiar de caso. La condición requiere
   un orden concreto de respuestas asíncronas.
3. **Identidad del receptor PDBQT.** La huella del preflight descartaba el
   hash preparado y una copia de PDBQT ya preparada se reutilizaba sin
   comprobar sus bytes. La divergencia del receptor ejecutado requiere una
   alteración externa de la copia; no se identificó una ruta de interfaz que
   la cause.
4. **Parámetros de la API.** El pH y el motor peptídico pasados en la raíz de
   la solicitud podían influir en la ejecución sin quedar necesariamente
   reflejados en la huella. El cliente habitual usa la configuración del
   pipeline; el caso identificado corresponde a llamadas directas a la API.
5. **Sello NSIS.** Si `git rev-parse` funcionaba y `git status` fallaba, el
   manifiesto afirmaba `arbol_limpio: true`. El caso se reprodujo con el script
   real, un instalador ficticio y Git simulado.
6. **Textos de Inicio.** Vina se describía como si midiera afinidad y el
   tutorial atribuía una suma a cada archivo, incluido implícitamente
   `checksums.sha256`, que no se hashea a sí mismo. El tutorial de Molcy
   también llamaba de demostración a todo el catálogo pese a existir 8T69 en
   Verificados. Se corrigieron los textos en ambos idiomas; la afirmación del
   índice heredado queda limitada a lo demostrado en las dos series estudiadas.

## Correcciones y regresiones dirigidas

- Preparación vuelve a leer el caso solicitado por Moldex aunque sea el mismo;
  invalida el borrador al cambiar de selección, evita que respuestas tardías
  sustituyan otro caso y avisa si un guardado anterior falla. Si cambia la
  corrida dentro del mismo caso, vuelve a leer la decisión guardada sin cambiar
  la corrida elegida. Un aviso de fallo tardío se retira al guardar con éxito
  esa misma decisión, sin ocultar fallos de otras. Las regresiones del
  componente fallaron antes de sus arreglos y pasan tras ellos.
- El preflight firma el PDBQT subido. Antes de reutilizar la copia preparada,
  comprueba tanto ésta como el original frente al hash registrado. Para
  receptores del catálogo la huella sigue identificando fuente y receta: crear
  una caché no cambia la huella. La huella de los PDBQT propios sí cambia; una
  comprobación previa antigua debe repetirse. Una huella histórica diferente no
  demuestra por sí misma un cambio de inputs: dossier, Preparación, historial,
  informe y respuesta 409 indican que la correspondencia no está confirmada.
  Se conservan la revisión y la abstención. Las regresiones de esos mensajes
  fallaron antes del cambio y después pasaron las pruebas dirigidas.
- El pH y el motor peptídico de la raíz se incorporan a la configuración
  efectiva que firma el preflight. La configuración normal se comparte con el
  ejecutor. Un cliente directo puede pedir esa misma huella en
  `/evaluation/preflight` mediante `pipeline_config`, incluyendo el pH en
  `stage_params.conformer.ph` y el motor en `peptide_docking_engine`; el submit
  puede enviar esos valores en la raíz. Las regresiones del backend fallaron
  antes de los cambios y después pasaron 115 pruebas dirigidas con Python
  embebido, incluida la comparación entre preflight público y submit.
- El sello conserva el commit y registra `arbol_limpio: null` con un aviso si
  Git no responde al estado. La regresión falló antes del arreglo; después
  pasaron dos pruebas con un instalador ficticio y Git simulado.

## Alcance de la comprobación

Las pruebas de regresión de comportamiento se escribieron antes de los
arreglos. Ejecución final el 2026-10-26 sobre el árbol corregido:

| Comprobación | Resultado | Alcance y límites |
|---|---|---|
| Backend, Python embebido 3.11.9 | 5594 pasan, 26 omitidas, 2 fallos esperados | Entre las omisiones hay pruebas de extracción de PDF que necesitan `pypdf`, ausente del runtime. |
| Scripts, Python embebido | 262 pasan, 1 omitida | La prueba omitida exige un clon sin los artefactos de fuente locales. |
| Rescoring, Python embebido | 321 pasan, 9 omitidas | Incluye casos sin corpus local y pruebas de fallbacks sin RDKit. |
| Frontend Vitest | 2346 pasan en 265 archivos | Pruebas de componentes y contratos. |
| TypeScript y build para navegador | Pasan | No es el export ni el instalador de escritorio. |
| Playwright y accesibilidad | 13 y 12 pasan | Navegador con servidor local, no WebView2 instalado. |
| Rust `cargo test --all-targets --locked` | 103 pasan | Fuera del sandbox; dentro fallaban las escrituras atómicas con acceso denegado. |
| Rust `cargo fmt --check` y Clippy | Pasan | Clippy ejecutado sin red con `--all-targets --locked -- -D warnings`. |
| ESLint / Ruff | 0 errores; ESLint informa 30 avisos | Ruff 0.16.0 del entorno de desarrollo; no forma parte del Python embebido. |

La primera ejecución completa del backend se detuvo por una clave de traducción
muerta, corregida. Otra se detuvo al leer un checkpoint por falta de memoria
durante la compilación simultánea de Next; el archivo pasó 17 pruebas aisladas
y la suite completa pasó sin la compilación en paralelo. La siguiente encontró
el sitio público generado desactualizado: se regeneró y sus 24 pruebas pasaron.
El temporal original de Vitest dio errores de archivo ausente; las suites se
ejecutaron con `TEMP` y `TMP` en el proyecto.

`npm run check:i18n` no está en verde: declara 112 diagnósticos pendientes, los
mismos contabilizados en `HEAD`, y cero literales JSX nuevos, candidatos sin
revisión o revisiones obsoletas. OpenAPI, CSP, enlaces locales, sitio generado,
sellos, inventario y lock del runtime, SBOM, licencias, frontera de Open Babel,
manifiesto de modelos y pesos del stacking pasan sus comprobaciones. El gate de
importancia de Vina sigue **NO_VERIFICABLE**, aceptado por su bandera explícita;
no es evidencia del modelo distribuido. Estas pruebas no demuestran que el bundle o
el instalador funcionen: el estado de sus puertas sigue en
[`../versions/1.0.4_cambios.md`](../versions/1.0.4_cambios.md).
