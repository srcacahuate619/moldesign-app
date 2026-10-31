# Informe de Fase C — guardianes i18n del frontend

Fecha: 2026-10-26. Rama sol/i18n-frontend, base 4fc7a9281fecb209a94784d15983475d64b517e8. Implementación de C: 09eae11a. Pendiente revisión del propietario.

## Correcciones previas a C

- 8988a55b restaura LF en los 30 archivos convertidos a CRLF, en un commit propio. En ese checkpoint git diff --shortstat 4fc7a928..HEAD y git diff --ignore-cr-at-eol --shortstat 4fc7a928..HEAD dieron ambos: 198 files changed, 12918 insertions(+), 765 deletions(-). git diff --ignore-cr-at-eol --exit-code 8988a55b^ 8988a55b terminó en 0.
- 111b28bf devuelve I18N-115/116 a pendiente junto con I18N-113, por decisión del propietario sobre la afirmación grid box calibrado de calibrationTooltip().
- 38c6c272 quita la exclusión indiscriminada de <code>/<pre>. Se clasifica por contenido técnico; un <pre> con frase castellana es control positivo.

## Guardianes

finish-i18n-frontend.cjs recorre candidatos de salida TS/TSX en lib/, hooks/ y context/, fuera de traducciones y pruebas. Reconoce retornos, propiedades de presentación, errores que llegan a un consumidor y constantes escalares usadas por una salida del módulo. No resuelve flujo entre módulos. i18n-source-review.json registra revisiones por ruta, ámbito y texto exactos; firmas nuevas u obsoletas hacen fallar la revisión.

npm run check:i18n es estricto. --json enumera regresiones sin revisar; una lista vacía no significa cero deuda. --source-json y --report-json exponen los candidatos. Hoy informa 0 literales JSX, 0 candidatos sin revisión, 112 diagnósticos pendientes y 0 revisiones obsoletas, y termina con salida 1. Son candidatos con posible consumidor, no 112 reproducciones dinámicas. I18N-295–401 representa 112 cadenas en 107 entradas pendientes.

La revisión específica de argumentos t() analizó 3463 llamadas; las únicas tres devoluciones compuestas sospechosas eran las de calibrationTooltip(), correspondientes a I18N-113/115/116. Se dejaron pendientes por la decisión de producto ya indicada.

npm run test:i18n:export construye el export desktop y lo sirve con CSP de producción. Playwright fija English, comprueba persistencia al recargar y recorre 48 estados reproducibles: rutas principales, selector, resultado sintético, pestañas, controles, ajustes, ayuda y errores HTTP/red. Inspecciona texto DOM y title, aria-label y placeholder, también fuera del viewport. Cada endpoint tiene fixture; no se ejecutan motores, Blender, modelos ni servicios externos.

Las excepciones tienen nombre y prueba: vocabulario técnico, Español, códigos de aviso, tres tooltips pendientes sólo en title, valores exactos fuente del Registro y claves/valores DTO dentro de elementos de datos. No se omiten regiones ni etiquetas code/pre. El autotest planta castellano en los cuatro canales.

## Fugas confirmadas en C

- I18N-402: Motor Molcy aparecía en Licencias. LegalModal ahora recibe la clave de nombre ya disponible; el documento legal fuente sigue pendiente. Pruebas en LegalIdiomas.test.tsx.
- I18N-403: «Ver los 1 controles que fallan» se componía en plantilla JSX. Ahora usa rx_open_failed_checks con {count}; conserva el español y presenta inglés natural. Pruebas es/en en ProAnalysisTabs.test.tsx.
- History comparaba errores con prosa castellana. Ahora renderiza el descriptor FrontendError. Pruebas es/en y error externo en history/__tests__/errorIdioma.test.tsx.

## Regresión demostrada

node scripts/probar-regresion-i18n.mjs repone temporalmente el CTA español de la base 4fc7a928; exige fallos del trinquete y del guardián de export en el detalle de la pose fallida; restaura el arreglo y comprueba el export limpio. --connection cubre History. Recibos: evidencia/control-regresion-c.json y evidencia/control-regresion-c-conexion.json. Los reportes DOM y capturas están en F:/Backups/moldesign-evidencia/2026-10-26-i18n-fase-c/; manifiesto SHA-256 evidencia/manifiesto-fase-c-sha256.json, SHA-256 c9300fefa31f69cd623ecc22fb0f51ad31094b6a0ada14dc39bff05da3761b76.

## Inventario y pendientes

403 registros: 248 cerrados, 155 pendientes. Por origen: frontend TSX 157 (153 cerrados, 4 pendientes); frontend lib 198 (89, 109); formato 6 (6, 0); backend 39 (0, 39); Rust 3 (0, 3).

| Superficie | Total | Cerrado | Pendiente |
|---|---:|---:|---:|
| Casos | 151 | 47 | 104 |
| Evaluación | 131 | 96 | 35 |
| MolChat | 52 | 48 | 4 |
| Inicio / global | 14 | 14 | 0 |
| Acceso | 6 | 6 | 0 |
| Batch | 6 | 5 | 1 |
| Preparación / Casos | 6 | 6 | 0 |
| Opciones | 8 | 6 | 2 |
| Resto | 29 | 20 | 9 |

Las 48 pendientes previas son I18N-113/115/116 (afirmación del selector), I18N-249/250 (documentos legales de public/), I18N-252–254 (Rust), I18N-255–293 (backend) e I18N-294 (QuickVina Coming soon). Las demás son las 107 entradas nuevas; todas quedan pendientes con motivo.

## Límites

El export usa respuestas simuladas y un resultado sintético; no equivale a corridas científicas ni cubre ramas que exigen Vina. Los textos backend/Rust siguen inventariados y no se traducen por comparación textual. El análisis estático es local al módulo y puede requerir revisión humana para separar ramas visibles de diagnóstico defensivo.

## Verificación

| Comando | Resultado |
|---|---|
| npm run test:run -- --maxWorkers 8 --reporter dot | Pasó: 260 archivos, 2325 pruebas. |
| npm run typecheck | Pasó. |
| npm run lint | Pasó: 0 errores, 30 avisos preexistentes. |
| npm run test:e2e | Pasó: 13/13. |
| npm run test:ux | Pasó: 12/12. |
| npm run test:i18n:export | Pasó: 48 estados, positivos en cuatro canales, 0 endpoints sin fixture. |
| finish-i18n-frontend.cjs --autotest | Pasó: 65 muestras. |
| finish-i18n-frontend.cjs --json | Pasó: lista vacía de regresiones sin revisar. |
| npm run check:i18n | Salida 1 esperada: quedan 112 diagnósticos pendientes para decisión/reproducción. |

smoke:prod y la regeneración de capturas del tutorial de Molcy corresponden al propietario al integrar. No se hizo push ni merge.
