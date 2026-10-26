# Entrega: intentos publicados de verificación

> **Nota de reubicación (2026-10-11).** El worktree `catalogo-demostracion` se retiró el 2026-10-11. La rama `sol/intentos-publicados` sigue existiendo. Índice: [REUBICACIONES_2026-10-11.md](docs/REUBICACIONES_2026-10-11.md).

Fecha: 2026-10-09. Versión de destino: 1.0.2. Rama: `sol/intentos-publicados`.
Base: `8ccee31e` de `codex/release-hygiene`. Worktree:
`D:\moldesign-build\.worktrees\catalogo-demostracion`.

Se publica el resultado real de `CAL-8HFI-01` en los selectores compartido y de
Molcy, en la tarjeta de 8HFI y en las insignias completas de resultados. **8HFI
permanece en Demostración**: la pose pasa en 3/5 semillas, pero la calibración es
NO_GO, con rho 0,13, IC 95 % [-0,16; 0,41], n = 57, Ki, CHEMBL853189.
El registro real de Verificados sigue vacío.

## Commits y archivos

Cada punto tiene su commit, sus pruebas y una fila continua en
`docs/versions/1.0.2_cambios.md`. Ese archivo aparece en los cuatro commits.

| Punto | Commit | Resultado |
|---|---|---|
| 2.2 | `134ef5f9` | Prueba de instalación de Molecular Nodes con reloj controlado, promesas esperadas y estado coherente tras el sondeo. |
| 2.1 | `745346f3` | Intentos publicados bilingües, línea compacta accesible, resumen en resultados y búsqueda conservada. |
| 2.3 | `76139f3f` | Advertencia por receptor preparado distinto, leyendo las dos declaraciones de SHA-256. |
| 2.4 | `108fc7cf` | Traducción estable de `receptor.seccion_catalogo` en Preparación. |

Archivos de `134ef5f9`, además del registro de cambios:

- `frontend/app/molcy/__tests__/page.test.tsx`.

Archivos de `745346f3`, además del registro de cambios:

- `frontend/lib/api.ts`, `frontend/lib/seccionCatalogo.ts` y
  `frontend/lib/__tests__/fixtures/intentoPublicado.ts`.
- `frontend/context/traducciones/catalogo.ts`.
- `frontend/components/science/IntentosDeVerificacion.tsx`,
  `InsigniaDelCatalogo.tsx`, `SeccionDelCatalogo.tsx` y
  `__tests__/IntentosDeVerificacion.test.tsx` en ese directorio.
- `frontend/components/interfaces/pro/TargetSelectorModal.tsx` y
  `__tests__/TargetSelectorModal.render.test.tsx` en ese directorio.
- `frontend/components/molcy/CatalogoReceptoresMolcy.tsx` y
  `__tests__/CatalogoReceptoresMolcy.test.tsx` en ese directorio.

Archivos de `76139f3f`, además del registro de cambios:

- `frontend/lib/seccionCatalogo.ts` y
  `frontend/context/traducciones/catalogo.ts`.
- `frontend/components/science/InsigniaDelCatalogo.tsx`,
  `__tests__/InsigniaDelCatalogo.test.tsx` y
  `__tests__/ListasDelCatalogo.test.tsx` en ese directorio.
- `frontend/components/MoldexCard.tsx` y `frontend/app/moldex/page.tsx`.

Archivos de `108fc7cf`, además del registro de cambios:

- `frontend/app/preparacion/page.tsx` y
  `frontend/app/preparacion/__tests__/seccionDelCatalogo.test.tsx`.

El commit de cierre añade esta entrega, capturas y registros de comprobación;
actualiza las referencias de las cuatro filas e introduce una corrección de
ortografía inglesa: `catalogue` pasa a `catalog` en el texto alternativo para
intentos GO. El guardián de inglés americano detectó ese error en la primera
ejecución global. Se corrigió el texto, conservando el guardián y sus reglas.
El hash del cierre se obtiene con `git log -1 --oneline` en esta rama.

## Causa de la prueba intermitente de Molcy

La página sondea `estadoAddonMolcy` cada 2 segundos. El mock global devolvía
siempre `{ estado: "inactivo" }`, incluso después de que el mock de
`instalarAddonMolcy` hubiera devuelto `{ estado: "instalando" }`. Al llegar el
primer sondeo, la página sustituía correctamente su estado por el nuevo dato del
mock y desaparecía el botón `cy_addon_installing`. Con carga, la espera real de
5 segundos podía observar la página después de esa sustitución.

La causa se reprodujo con el reloj falso y las promesas esperadas mediante
`act`, manteniendo el mock global anterior. La aserción del botón inmediatamente
después de instalar pasó; tras avanzar exactamente 2000 ms pasó la aserción de
dos consultas de estado, y falló la del botón de instalación. El registro
[del control negativo](docs/verificacion/intentos-20261009/intentos-molcy-causa.log)
termina con 1 fallo y 46 pruebas omitidas, salida 1, en la aserción posterior al
sondeo. Se ejecutó sólo esta prueba para el diagnóstico.

La prueba definitiva devuelve `inactivo` en la consulta inicial y `instalando`
en las posteriores, controla el reloj y verifica el botón deshabilitado antes
y después del sondeo, además del número de llamadas. `finally` limpia el montaje
y restaura el reloj real. **No se aumentó el timeout ni se cambió la página.**

Se contrastó por lectura con `backend/services/molcy/addon.py`: `iniciar` publica
`instalando` bajo un lock antes de despachar el trabajo y retornar; `estado`
copia ese estado bajo el mismo lock. El mock anterior contradice esa transición.
Esto identifica un defecto del escenario de prueba; no demuestra una instalación
real de Molecular Nodes ni elimina la posibilidad de errores del instalador.

Para repetir el control negativo en una copia aislada, se elimina únicamente la
línea local `mockResolvedValueOnce(...).mockResolvedValue(...)` de esta prueba,
manteniendo el reloj falso y ambas aserciones. No se deja esa variante en la rama.

## Comprobaciones

Comandos ejecutados desde `frontend/`, con las dependencias existentes mediante
junction. Se añadieron 30 casos de prueba y dos archivos de pruebas: la suite
pasa de 1694/182 a 1724/184. No se añadieron paquetes.

| Comando o grupo | Salida observada |
|---|---|
| Control negativo de Molcy: `npx vitest run app/molcy/__tests__/page.test.tsx -t "ofrece instalación explícita"` | Salida 1 esperada; 1 fallo, 46 omitidas; 4,84 s. |
| Archivo completo de Molcy después de corregirlo | 47/47; 19,54 s; salida 0. |
| 20 veces consecutivas: `npx vitest run app/molcy/__tests__/page.test.tsx --reporter=dot` | 20/20 ejecuciones con salida 0; 47/47 en cada una; 940 ejecuciones de casos, 428,29 s acumulados. |
| Grupo 2.1: componentes, selectores y diccionario | 61/61 en 5 archivos; salida 0. |
| Grupo 2.3: sello, listas y contrato del catálogo | 47/47 en 3 archivos; salida 0. |
| Preparación, requisito nuevo e identidad del receptor | 4/4 en 2 archivos; salida 0. |
| `npx vitest run lib/__tests__/idiomasCompletos.test.ts lib/__tests__/interfazSinTextoFijo.test.ts` | 13/13 en 2 archivos; salida 0. |
| Guardián de inglés americano y componente de intentos tras la corrección ortográfica | 19/19 en 2 archivos; salida 0; 2,61 s. |
| Primera suite global, antes de corregir `catalogue` | Salida 1; 1723 pasan, 1 falla por esa palabra; 183 archivos pasan, 1 falla; 362,70 s. Molcy pasó. |
| `npm run test:run`, final 1 | Salida 0; 1724/1724, 184/184 archivos; 290,18 s. |
| `npm run test:run`, final 2 | Salida 0; 1724/1724, 184/184 archivos; 312,79 s. |
| `npx tsc --noEmit`, final | Salida 0; sin diagnósticos; 8,27 s. |
| `npm run lint`, final | Salida 0; 0 errores y 39 advertencias; 34,33 s. |

Las 20 ejecuciones no usan `-t`: ejecutan las 47 pruebas del archivo, sin fallos
ni reintentos entre ellas. Parte del bucle coincidió con una suite global, bajo
carga. Sus salidas individuales y su resumen están en
[docs/verificacion/intentos-20261009](docs/verificacion/intentos-20261009/).
Los registros `.log` se añaden expresamente a git pese a estar ignorados por la
regla general del repositorio.

Un primer lint concurrente con la suite acabó con salida 2: `ENOENT` al abrir
`components/MutanteInvisibleDelGuardian.tsx`. El guardián de textos crea y borra
ese mutante como control negativo mientras ESLint recorre archivos. Se conserva
ese registro como `intentos-lint-concurrente.log`; el lint final se ejecuta
después de las pruebas, sin modificar el guardián ni ampliar sus excepciones.
Las 39 advertencias corresponden al mismo total de la entrega de base y no
bloquean el comando; se conserva su salida íntegra para revisión. Las salidas
globales definitivas están en `intentos-suite-final-1.log` y
`intentos-suite-final-2.log`; la de TypeScript está vacía porque no hubo
diagnósticos, con su salida 0 registrada en `resultados.json`.

## Capturas y datos

Hay 12 PNG en [docs/capturas/intentos-20261009](docs/capturas/intentos-20261009/):
selector, bloque completo y tarjeta en ES/EN, a viewports de 1440 y 375 px.
Se revisaron visualmente los bloques completos en ambos anchos y las tarjetas
compactas a 375 px, incluyendo las cifras, condiciones y etiquetas visibles.

Se montó el `TargetSelectorModal` real con `AuthProvider`, `LanguageProvider` y
los estilos locales. Los números se leyeron de
`backend/data/intentos_de_verificacion.json`, SHA-256
`ed62af0df8c1682a0728915271706f55a12b16380f3f195a0ea425f98d7f3d0a`.
El nombre y la familia proceden de `backend/data/target_aliases.json`. El arnés
incluye sólo 8HFI y no rellena metadata estructural ausente ni inventa cifras.

El script comprobó igualdad de los intentos con el JSON original, cifras y RMSD
formateados, experimento, tarjeta dentro de Demostración, ausencia del sello
Verificado en la tarjeta y equivalencia del `title` y el `aria-label` completos.
Los cuatro escenarios terminaron sin errores de página ni desbordamiento
horizontal de los fragmentos. Resultado en `comprobaciones.json` junto a las
capturas. El acceso del navegador se limitó al servidor local.

Las capturas `selector-*` muestran el modal en su viewport. Las `intento-*` y
`tarjeta-*` copian el DOM ya renderizado a un contenedor con el ancho original
para documentar su contenido completo sin el recorte vertical del scroll del
modal. **Son fragmentos de documentación**, no pantallas de la aplicación
instalada. No acreditan el export estático ni la CSP de Tauri. La metadata
estructural no incluida aparece con el estado previo de falta de datos; ese
panel existente sigue siendo estrecho en la tarjeta móvil.

El arnés usado se conserva para revisión en
`docs/verificacion/intentos-20261009/arnes-capturas/`. Para reproducirlo, se
copian sus cinco archivos a `frontend/.tmp/`, se ejecuta
`node .tmp/intentos-vite.mjs` desde `frontend/` y, en otro proceso,
`node .tmp/intentos-capturas.mjs`. Requiere las dependencias existentes y Edge.
El servidor genera su entrada desde los JSON del backend; el único ajuste de
entorno del arnés es `process.env: {}` para resolver código del frontend en Vite.

## Decisiones y diferencias con el encargo

- Un intento informa; no altera `seccionDelReceptor` ni la validación del sello.
  Se excluyen intentos ajenos al PDB y receptores propios o comunitarios, como
  hace la autoridad del backend. Ausencia, `null` o lista vacía no añaden UI.
- El texto «no superó» exige tanto NO_GO como `CALIBRACION_NO_SUPERADA`. Un GO
  hipotético o una conclusión nueva usa el texto genérico con los códigos y
  conserva sus cifras. Para un listado que contiene GO se añadió una explicación
  neutral bilingüe, para evitar afirmar que todos los intentos fallaron.
- Si existe un intento medido, la ayuda de Demostración usa un texto neutral
  bilingüe: la ayuda anterior afirmaba que no había verificación de pose ni
  calibración y resultaría contradictoria junto al resultado publicado. Sin
  intentos se conserva el texto anterior. La variante compacta muestra sólo su
  etiqueta; la completa incluye el resumen del intento.
- La línea compacta de la tarjeta expone conclusión, cifras, pose, protocolo,
  todas las condiciones, RMSD, experimento y fecha en `title` y `aria-label`.
  Las condiciones desconocidas conservan su código mediante el texto genérico.
- El bloque de intentos consume los receptores ya filtrados por el selector.
  La búsqueda, agrupación y disponibilidad conservan su lógica previa. Se
  mantiene la caché compartida, sin petición adicional por tarjeta.
- La comparación del receptor considera ambos hashes declarados, incluso si
  son contradictorios: cualquiera distinto genera aviso. No calcula hashes
  nuevos. Ausencia y `null` no inventan diferencia, siguiendo la regla explícita
  del encargo. El backend es más estricto con la ausencia y lee el hash anidado;
  esa diferencia se declara, sin modificarlo.
- `receptor.seccion_catalogo` se traduce por su clave estable, no por la etiqueta
  cruda del backend. Las pruebas montan la página en ambos idiomas y conservan
  el estado REVIEW recibido.
- Se aplicó la guía local de UI/UX para etiquetas largas y acceso al texto
  íntegro. La búsqueda específica de Next.js no produjo una pauta pertinente;
  se mantuvo el componente y el lenguaje visual existentes.

## Límites y limpieza

No se ejecutaron `tauri:build`, `stage:desktop` ni `smoke:prod`, según el encargo.
No se probó la instalación real del addon, Blender, una evaluación científica
nueva, el instalador ni una transferencia FEP. Las pruebas de esta entrega son
de frontend; el backend y los artefactos científicos se consultaron por lectura.

`CustomReceptorModal.tsx`, el flujo de subida y `uploadCustomTarget` permanecen
sin cambios respecto de `8ccee31e`. En `api.ts` sólo cambia la importación del
tipo y el campo opcional. En `TargetSelectorModal.tsx` sólo cambia el montaje del
bloque de Verificados mediante un componente nuevo. No se tocaron CSP, puertas
de build, `tools/molcy/` ni `scripts/artifacts_science/`.

El servidor temporal de capturas y su caché se retiraron. El junction se verificó
por su ruta, tipo y destino y se quitó con
`cmd.exe /d /c rmdir D:\moldesign-build\.worktrees\catalogo-demostracion\frontend\node_modules`.
Se comprobó que desapareció y que `D:\moldesign-build\frontend\node_modules\vitest\package.json`
sigue presente. Los registros temporales originales permanecen ignorados; sus
copias de entrega están versionadas, con el terminador final normalizado.
No hay push, fusión ni rebase; la rama queda para revisión e integración.
