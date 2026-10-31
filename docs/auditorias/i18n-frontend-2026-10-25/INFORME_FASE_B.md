# Informe de Fase B — i18n frontend

**Fecha:** 2026-10-26  
**Estado:** B aceptada tras las correcciones previas a C; la Fase C se documenta en INFORME_FASE_C.md.
**Rama aislada:** `sol/i18n-frontend`  
**Base:** `4fc7a9281fecb209a94784d15983475d64b517e8`

## Alcance completado

- Se rehízo Fase A en `bd3788f5`, quitando del repositorio la evidencia pesada y archivando los originales en `F:\Backups\moldesign-evidencia\2026-10-25-i18n-fase-a\`. El manifiesto SHA-256 `9440755aecb5e052208160dc6e08eff91736d1e6033fb935d5c79af98482b2f1` está citado en [ARCHIVO_EVIDENCIA.md](ARCHIVO_EVIDENCIA.md).
- Se corrigieron falsos amigos y grafías del diccionario inglés, incluidos “Earrings”, “It’s” y “Healing”, y se ampliaron las pruebas de inglés americano.
- Se sustituyeron comparaciones con frases castellanas por valores estructurados y se añadieron pruebas. Los casos cubren tipo estable de repositorio, resumen de receptor y caja, códigos de motivo de Moldex y claves de etapa de procedencia. Selectividad usa el valor numérico, no texto presentado.
- Se añadieron descriptores para errores producidos por el frontend. Los mensajes backend/Rust siguen siendo texto externo; no se reconocen por frase ni se traducen desde la interfaz.
- Se localizaron las superficies frontend de Casos, Preparación, Evaluación, Moldex, Lotes, Molcy, Registro, Comunidad, Historial, opciones y asistentes.
- No se alteraron formatos persistidos. En particular, `public/registro/index.json` permanece intacto; I18N-251 se resolvió en la capa de presentación con la clave estable `rg_index_warning`.
- `auditar-i18n-fase-a.cjs` quedó bajo `herramientas/`, como solicitó el propietario. Fase C no se inició.

## Inventario y pendientes

El inventario tiene 294 entradas: 248 cerradas y 46 pendientes, todas estas últimas con motivo.

| Pendiente | Cantidad | Motivo |
|---|---:|---|
| Afirmación «grid box calibrado» del selector (I18N-113) | 1 | Excluida expresamente de B; requiere decisión de producto/ciencia. |
| Documentos legales bajo `public/` (I18N-249–250) | 2 | Excluidos expresamente; requieren revisión legal/editorial. |
| Origen Rust (I18N-252–254) | 3 | Fuera de B; conservar el texto del productor nativo hasta un encargo de ese origen. |
| Origen backend (I18N-255–293) | 39 | Fuera de B; conservar el texto del productor backend hasta un encargo de ese origen. |
| QuickVina «Coming soon» en Lotes (I18N-294) | 1 | Excluido expresamente; es una afirmación de disponibilidad de producto. |
| **Total pendiente** | **46** | |

I18N-251, advertencia de Registro, está cerrada: la interfaz presenta la clave traducida y no cambia el documento fuente ni su formato.

## Commits de producto

- `bd3788f5`: sustitución ligera de la entrega A.
- `4535d6e8`: diccionario y contexto.
- `8a9ddda4`: presentación de tipo de repositorio.
- `832d58ae`: resumen estructurado de receptor y caja.
- `169edf65`: razones estructuradas y nombres en Moldex.
- `b7fd5710`: procedencia por claves de etapa.
- `493173bf`: mensajes comunes, sesión y asistentes.
- `82879b72`: Lotes y errores locales.
- `e64816da`: Molcy y estados.
- `a32fc030`: presentación del Registro.
- `bc70acf7`: Casos y Preparación.
- `da7e8450`: resultados y Moldex.
- `75496282`: trinquete de textos visibles y exclusión de bloques de código del escaneo.

## Pruebas y QA

| Comando | Resultado |
|---|---|
| `npm run test:run -- --maxWorkers 8 --reporter dot` | Pasó: 257 archivos, 2310 pruebas. |
| `npm run typecheck` | Pasó. |
| `npm run lint` | Pasó: 0 errores, 31 avisos. |
| `npm run test:e2e` | Pasó: 13/13. |
| `npm run test:ux` | Pasó: 12/12. |
| `npm run smoke:prod` | No pasó en el primer paso: falta el runtime staged en `frontend/src-tauri/resources`. |

La cápsula QA se reconstruyó desde el código B y está disponible en [http://localhost:13011](http://localhost:13011); el backend responde en `127.0.0.1:18011`. La autoverificación informó login de escritorio 200, CORS del origen propio correcto, bloqueo del origen ajeno y `/health = healthy`. Las nueve capturas de interfaz inglesa se inspeccionaron visualmente y suman 633 313 bytes:

`b-inicio-en.jpg`, `b-preparacion-en.jpg`, `b-evaluacion-en.jpg`, `b-lotes-en.jpg`, `b-moldex-en.jpg`, `b-molcy-en.jpg`, `b-historial-en.jpg`, `b-comunidad-en.jpg` y `b-registro-en.jpg`.

## Límites de esta entrega

- `smoke:prod` requiere el runtime staged. No se ejecutó `npm run stage:desktop`, que está expresamente fuera de esta fase/autorización.
- No se regeneraron capturas del tutorial: hacerlo requeriría Blender o el addon que la instrucción prohíbe descargar.
- Las 31 advertencias de lint no son errores; el comando terminó correctamente.
- No hubo push, merge ni inicio de Fase C.

La entrega queda detenida aquí para revisión del propietario.


## Correcciones posteriores a la aceptación

La cifra al corte original de B era 248 cerradas y 46 pendientes. Al reabrir I18N-115/116 con 111b28bf, el corte de entrada a C quedó en 246 cerradas y 48 pendientes. Se restauraron los finales LF originales de 30 archivos en el commit propio 8988a55b; 38c6c272 quitó la exclusión general de <code>/<pre>, sustituyéndola por evaluación del contenido visible. smoke:prod y las capturas del tutorial corresponden al propietario al integrar.
