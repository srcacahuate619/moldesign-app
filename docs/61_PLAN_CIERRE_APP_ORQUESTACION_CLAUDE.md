# Plan de trabajo hacia MolDesign 1.0 comercial

**Fecha:** 2026-08-28  
**Modelo de trabajo:** auditoría y cierre vertical, pestaña por pestaña.  
**Orquestador y revisor:** Codex.  
**Obrero de implementación:** Claude CLI.  

## 1. Mandato y orden de prioridades

La aplicación se terminará con este orden, que no puede invertirse:

1. **Validez científica.** Los datos, métodos, límites, advertencias, procedencia y
   conclusiones deben ser científicamente defendibles. Un resultado inválido o una certeza
   exagerada bloquean la pestaña, aunque la interfaz funcione y sea rápida.
2. **Calidad.** Corrección funcional, integridad de datos, persistencia, aislamiento entre
   cuentas, mantenibilidad, pruebas, accesibilidad y UX.
3. **Eficiencia.** Rendimiento, consumo de memoria/CPU, tamaño, latencia y fluidez. Sólo se
   optimiza después de fijar y probar la semántica científica y funcional.

Regla de decisión: si una optimización puede cambiar resultados, precisión, reproducibilidad
o procedencia, se trata como un cambio científico y vuelve al punto 1.

## 2. Orden de las pestañas

### Camino crítico

1. **Evaluación**
2. **Batch**
3. **Moldex**
4. **MolChat**

No se inicia el cierre profundo de la siguiente pestaña hasta que la anterior pase su gate.
Puede hacerse inventario de lectura en paralelo, pero sólo habrá un paquete de escritura activo.

### Camino secundario

5. **Historial**
6. **Comunidad**
7. **Ciencia**

Estas tres pestañas no bloquean las auditorías del camino crítico. Sí deben alcanzar el mínimo
comercial antes de publicar 1.0: no romper, no filtrar datos, no contradecir resultados y no
hacer afirmaciones científicas sin evidencia.

## 3. Las cuatro revisiones obligatorias por pestaña

Cada pestaña tendrá un expediente propio y se auditará siempre sobre los mismos cuatro ejes.

| Eje | Preguntas que deben quedar respondidas |
|---|---|
| Frontend | ¿Representa todos los estados reales? ¿Valida entradas? ¿Evita estado duplicado o obsoleto? ¿Es accesible y comprobable? |
| Backend | ¿El cálculo es válido, reproducible, persistente, autorizado y recuperable? ¿Los fallos son explícitos? |
| Intersección backend–frontend | ¿Cada dato producido se persiste, serializa, tipa, consume, muestra, exporta y reaparece sin pérdidas? |
| UX | ¿El investigador entiende qué hará, qué está ocurriendo, qué obtuvo, con qué límites y cómo recuperarse? |

La intersección se comprobará con una **matriz de trazabilidad de campos**:

`entrada UI → payload → esquema backend → cálculo → DB → respuesta/evento → tipo TS → vista → exportación → reapertura`

Para cada campo científico relevante debe existir evidencia de todos los eslabones aplicables.
Una corrida no se considera persistida porque conserve sólo su estado: deben reaparecer el
resultado, configuración, versiones, seed, advertencias, artefactos y procedencia necesarios.

## 4. Método de cierre vertical

Cada pestaña atraviesa, en este orden, siete pasos.

1. **AUD — Inventario y auditoría de sólo lectura.** Codex mapea rutas, componentes,
   endpoints, servicios, tablas, estados, contratos y pruebas; registra hallazgos con evidencia.
2. **SCI — Validez científica.** Se resuelven primero P0 científicos: método, unidades,
   supuestos, dominio de aplicación, reproducibilidad, controles y comunicación de incertidumbre.
3. **BE — Backend.** Persistencia, propiedad por usuario, idempotencia, concurrencia,
   errores, migraciones, cancelación/reanudación y observabilidad.
4. **INT — Intersección.** Contratos, serialización, estados terminales, eventos, archivos,
   reapertura y cobertura campo a campo.
5. **FE/UX — Frontend y experiencia.** Flujo, jerarquía, estados vacíos/carga/error,
   recuperación, accesibilidad y claridad científica. La revisión visual usa una rúbrica Hallmark,
   sin imponer apariencia sobre legibilidad o rigor.
6. **EFF — Eficiencia medida.** Se perfila antes de optimizar y se demuestra que los cambios
   no alteran el resultado científico.
7. **GATE — Pruebas y aceptación.** Codex reproduce las pruebas y revisa el diff. Sólo entonces
   la pestaña se marca verde.

### Expediente de auditoría

Cada hallazgo tendrá:

- ID estable (`EVAL-SCI-001`, `BATCH-INT-003`, etc.).
- prioridad y eje;
- archivo/línea o endpoint/tabla;
- evidencia reproducible;
- impacto científico o funcional;
- causa raíz;
- corrección propuesta;
- prueba que fallará antes y pasará después;
- estado: abierto, implementado, verificado o aceptado con limitación.

La prioridad se asigna así:

- **P0:** invalidez científica, pérdida/corrupción de resultados, fuga entre cuentas,
  afirmación engañosa o flujo crítico imposible.
- **P1:** error funcional, recuperación deficiente, contrato incompleto, accesibilidad o UX
  que induce errores de investigación.
- **P2:** eficiencia, deuda interna o pulido que no compromete ciencia ni datos.

## 5. Pestaña 1 — Evaluación

### Alcance inicial conocido

- Frontend: `frontend/app/evaluation/page.tsx`, `frontend/components/cases/`,
  `frontend/components/evaluation/`, `frontend/components/interfaces/pro/` y sus contextos/API.
- Backend: `backend/api/routers/evaluation*.py`, servicios de pipeline, repositorio/ORM,
  dossier, reportes y archivos.

### EVAL-AUD — Mapa y reproducción

- Dibujar el flujo real: cuenta → caso → molécula/objetivo → preflight → configuración →
  submit → progreso → terminal → resultado → dossier → reinicio → reapertura.
- Reproducir casos feliz, inválido, cancelado, timeout, cierre de pestaña, reinicio de backend
  y cambio de cuenta.
- Construir la matriz de trazabilidad de todos los campos de configuración y resultado.
- Inventariar qué ya está cubierto por unitarios, integración, contrato, E2E y motor real.

### EVAL-SCI — Validez científica

- Verificar preparación de ligando/receptor, protonación/cargas, caja de docking, unidades,
  exhaustividad, seed y versión del motor.
- Separar claramente docking, rescoring, predicción, heurística y evidencia observada.
- Validar selección de pose, signos/escalas, agregaciones y umbrales; impedir comparaciones
  incompatibles o conclusiones causales no sustentadas.
- Mostrar dominio de aplicación, cobertura, incertidumbre y motivos de abstención.
- Asegurar que fallos parciales no produzcan un resultado aparentemente completo.
- Garantizar un dossier reproducible con inputs, hashes, parámetros, versiones y advertencias.

### EVAL-BE — Backend

- Garantizar propiedad y autorización uniforme de casos, corridas, archivos, reportes y eventos.
- Hacer durable la máquina de estados y reconciliar tareas interrumpidas tras reinicio.
- Comprobar persistencia atómica del resultado antes de emitir éxito.
- Definir idempotencia de submit/retry/cancel y evitar dobles corridas accidentales.
- Tipar y categorizar errores científicos, operativos y de infraestructura.

### EVAL-INT — Intersección

- Contrato único para submit, status, SSE, resultado, dossier y archivos.
- Tests de cobertura que detecten campos backend omitidos o renombrados en TypeScript.
- Verificar que `success` sólo llegue cuando el resultado recuperable tenga identidad estable.
- Probar desconexión/reconexión SSE, expiración de sesión, carrera entre polling y eventos,
  y reapertura sin depender de `localStorage`.
- Comparar el resultado recibido en vivo, el leído de DB y el exportado: deben conservar
  semántica, valores, unidades, `null`, advertencias y procedencia.

### EVAL-FE/UX — Frontend y experiencia

- Una sola máquina de estados visible: sin loaders eternos, resultados vacíos ni mensajes que
  culpen genéricamente al backend.
- Preflight accionable y bloqueante sólo cuando corresponda; explicar cómo corregir cada fallo.
- Mantener cuenta, caso y corrida activos siempre identificables.
- Progreso honesto por etapas; distinguir en cola, ejecutando, persistiendo, completo,
  incompleto, cancelado y fallido.
- Resultados con jerarquía científica: conclusión condicionada, evidencia, calidad/cobertura,
  incertidumbre, advertencias y detalles reproducibles.
- Recuperación explícita: reintentar de forma segura, abrir último resultado, descargar
  diagnóstico y continuar después de reiniciar.
- Navegación completa por teclado, foco, contraste y textos que no dependan sólo del color.

### EVAL-EFF — Eficiencia

- Medir latencia UI→submit, tiempo por etapa, escritura/lectura DB, volumen SSE, CPU, RAM y
  coste del visor 3D.
- Eliminar solicitudes duplicadas, renderizados masivos y polling coexistente innecesario.
- Cargar bajo demanda visores/artefactos pesados y limitar cachés por usuario/caso.
- Mantener determinismo y equivalencia de resultados antes/después.

### Gate de Evaluación

- Corrida real pequeña, offline y determinista con el motor empaquetado.
- Persistencia comprobada después de cerrar la app y reiniciar el backend.
- Segunda cuenta no puede listar, leer, descargar, cancelar ni inferir la corrida.
- Resultado vivo = resultado reabierto = dossier exportado en campos científicos críticos.
- Casos feliz y de fallo cubiertos en unitario, contrato, integración y navegador.
- Cero P0/P1 abiertos; P2 medidos y documentados.

**Estimación:** 6–9 días de trabajo, dependiendo de los hallazgos científicos.

## 6. Pestaña 2 — Batch

### Alcance inicial conocido

- Frontend: `frontend/app/evaluation/batch/page.tsx`, `frontend/lib/cohorts*` y dossier.
- Backend: `backend/api/routers/evaluation_cohorts.py`,
  `evaluation_cohort_runs.py`, `backend/services/cohort/` y persistencia asociada.

### Trabajo científico y funcional

- Auditar importación, canonicalización, duplicados, inválidos, denominadores y exclusiones.
- Comprobar que todas las moléculas comparables usan configuración científica compatible y
  que cualquier desviación queda registrada.
- Definir tratamiento de fallos parciales, reintentos, ranking, empates, `null`, cobertura y
  agregaciones; nunca ocultar descartes en porcentajes o promedios.
- Persistir cohorte, snapshot de inputs/configuración, progreso por ítem, resultados parciales,
  errores, versiones y dossier.
- Reconciliar y reanudar después de reinicio sin repetir silenciosamente trabajos completos.
- Aislar cohortes, archivos, progreso y exportaciones por cuenta.

### Intersección y UX

- Reutilizar el catálogo canónico y el mismo selector de receptores de Evaluación; Batch no
  mantiene una lista paralela. La selección debe transferir PDB ID y cadena al contrato de
  cohorte, limpiar datos del receptor anterior y conservar entrada manual si el catálogo falla.
- La propiedad de receptores privados debe resolverse y autorizarse en backend con la cuenta
  autenticada; nunca confiar en una lista de IDs privados aportada por el cliente.
  **Verificado 2026-08-28:** catálogo, archivo PDB, compartir, Evaluación, cohortes, Batch
  histórico, PLIF, SAR, selectividad, MM-GBSA, estadísticas y MolChat aplican una política
  backend común con pruebas Alice/Bob.
- Probar contrato por ítem y resumen: recibido, aceptado, excluido, fallido y completo.
- Progreso derivado de estados reales; no usar porcentajes cosméticos.
- Tabla grande virtualizada con filtros, selección, comparación y exportación verificables.
- El usuario debe poder identificar por qué falló una molécula y reintentar sólo las elegibles.
- Advertir antes de ejecutar costo estimado, configuración compartida y cambios que invaliden
  comparabilidad.

### Gate de Batch

- Los 387 receptores del catálogo canónico están disponibles desde Batch sin duplicar datos,
  y el preflight recibe exactamente el PDB ID y la cadena seleccionados.
- Los receptores privados/personalizados del selector están aislados y autorizados por backend
  entre dos cuentas, incluso si una conoce el ID de un receptor ajeno.
- Fixtures con duplicados, inválidos, fallos parciales y resultados nulos.
- Reinicio a mitad de cohorte y recuperación consistente.
- Igualdad entre conteos UI, DB, API y dossier.
- Dos cuentas no comparten cohortes ni configuraciones.
- Prueba de escala con presupuesto definido, sin cambiar resultados frente a ejecución serial.

**Estimación:** 5–8 días.

## 7. Pestaña 3 — Moldex

### Alcance inicial conocido

- Frontend: `frontend/app/moldex/page.tsx`, `MoldexCard`, `MolecularComparison`, visores,
  reportes y certificación.
- Backend: `backend/api/moldex.py`, repositorios de moléculas/resultados, archivos de pose y
  proteína, reportes y certificación.

### Trabajo científico y funcional

- Definir qué representa exactamente cada ficha: cálculo, snapshot, curación o certificación.
- Trazar cada propiedad, pose, proteína, comparación y sello hasta su corrida y versión.
- Validar unidades, redondeo, ausencia de datos y compatibilidad antes de comparar moléculas.
- Impedir que “certificado” se interprete como validación experimental si sólo certifica
  integridad/procedencia computacional.
- Auditar propiedad por cuenta de resultados y artefactos, enlaces rotos y archivos huérfanos.
- Probar la navegación Evaluación→Moldex y Moldex→Evaluación sin perder contexto ni duplicar
  entidades.

### Intersección, UX y eficiencia

- Contratos tipados para lista, detalle, proteína, pose, reporte y certificación.
- Estados explícitos para artefacto ausente, incompatible, todavía generándose o no autorizado.
- Búsqueda/filtros/orden conservados por cuenta; comparación accesible y fácil de deshacer.
- Virtualización y carga diferida medidas para colecciones y visores grandes.
- Liberar recursos WebGL y cancelar descargas/renderizados al cambiar selección.

### Gate de Moldex

- Cada valor mostrado y exportado conserva origen, unidad y corrida.
- Ningún enlace/ID permite cruzar cuentas.
- Comparación rechaza entradas incompatibles con una explicación científica.
- Lista grande y navegación repetida no degradan memoria fuera del presupuesto acordado.

**Estimación:** 4–6 días.

## 8. Pestaña 4 — MolChat

### Alcance inicial conocido

- Frontend: `frontend/context/AIContext.tsx`, `frontend/components/ai/` y configuración.
- Backend: `backend/api/routers/ai.py`, `backend/services/ai/`, proveedores y herramientas.

### MOLCHAT-SCI — Veracidad y límites

- Clasificar respuestas: cálculo determinista, lectura de dato persistido, inferencia de modelo,
  recuperación externa o explicación general.
- Exigir citas internas/procedencia para cualquier afirmación sobre un caso o corrida.
- Prohibir fabricar moléculas, resultados, tareas, herramientas ejecutadas o certeza clínica.
- Validar argumentos y resultados de herramientas; el modelo no puede saltarse preflight,
  autorización ni restricciones científicas de Evaluación/Batch.
- Incorporar abstención cuando falte contexto, el método quede fuera de dominio o una herramienta
  falle; presentar sugerencias como hipótesis, no como resultados.

### Backend, intersección y privacidad

- Aislar conversaciones, memoria, proveedor, claves, configuración y contexto por cuenta.
- Fijar explícitamente caso/corrida activa en cada turno; no inferir contexto desde estado global.
- Autenticar todos los endpoints AI y tool calls, incluido streaming, abort y retry.
- Persistir mensajes y metadatos de herramienta de forma atómica y recuperable.
- Consentimiento por cuenta antes de enviar datos a un proveedor remoto: destino, contenido,
  retención conocida y revocación. El camino local/offline debe ser inequívoco.
- Sanitizar Markdown/archivos, limitar tamaños/tiempos y redactar secretos en logs.

### UX y eficiencia

- Mostrar proveedor y modo local/remoto, caso activo y herramientas usadas.
- Distinguir texto del modelo de resultados computados; los resultados enlazan a su evidencia.
- Streaming cancelable, reintento idempotente y recuperación después de reinicio.
- Errores accionables sin borrar el borrador ni duplicar mensajes.
- Presupuestos de contexto, caché y carga del modelo; medir tiempo a primer token y memoria sin
  degradar grounding o exactitud.

### Gate de MolChat

- Suite adversarial de alucinación, prompt injection, fuga entre usuarios y tool calls inválidos.
- Conversación y configuración reaparecen sólo para su propietario.
- Cero llamadas remotas sin consentimiento verificable.
- Toda afirmación específica del experimento enlaza a datos persistidos o se etiqueta como
  hipótesis/no verificada.

**Estimación:** 6–9 días.

## 9. Pestañas secundarias

Se atienden después de los cuatro gates críticos y con un alcance comercial mínimo.

### Historial

- Debe ser una proyección fiel de DB, no otro almacén de estado.
- Aislamiento por usuario, filtros estables, paginación y apertura del caso/corrida exactos.
- Estados/resultados consistentes con Evaluación y Batch, incluida eliminación o archivado.

### Comunidad

- Todo envío es opt-in explícito y muestra exactamente qué datos salen de la PC.
- Privacidad, moderación, autoría, licencias y revocación antes de enriquecer funciones sociales.
- Debe poder desactivarse por completo sin afectar los flujos científicos locales.

### Ciencia

- Contenido, glosario y metodología sincronizados con la implementación real.
- Claims versionados y respaldados por fuentes/benchmarks; límites y fecha de validez visibles.
- No usar contenido educativo como sustituto de evidencia específica de una corrida.

**Estimación conjunta:** 4–6 días.

## 10. Carril transversal bajo responsabilidad de Codex

Estos controles no compiten con las pestañas: se aplican en cada gate y se cierran globalmente
antes de 1.0.

- Autenticación, autorización, sesiones y aislamiento de archivos/DB/cache.
- Modelado de amenazas, límites de recursos, subprocess seguros y validación de rutas.
- Migraciones idempotentes, backup, rollback y compatibilidad con datos anteriores.
- Contratos versionados, códigos de error y observabilidad con correlation IDs.
- Logs y ZIP de soporte redactados: sin estructuras, SMILES, tokens ni rutas sensibles por defecto.
- Cero red implícita; consentimiento por cuenta para RCSB/UniProt, proveedores AI, Comunidad,
  blockchain y cualquier integración externa.
- SBOM, licencias, vulnerabilidades alcanzables, hashes y manifiesto de release.
- Actualización/desinstalación segura, instalador reproducible, Authenticode y clean-room test.
- Accesibilidad WCAG AA en recorridos principales y presupuestos de rendimiento medidos.

Las 124 alertas npm observadas se clasificarán por alcanzabilidad. Ninguna vulnerabilidad crítica
alcanzable en runtime puede llegar a 1.0; no se usarán actualizaciones masivas con `--force`.

## 11. Gates comerciales

### Baseline que no se debe perder

| Suite | Evidencia local 2026-08-28 |
|---|---:|
| Backend | 870 passed, 3 skipped |
| Frontend unitario/contrato | 531 passed |
| Browser E2E sesiones/persistencia | 1 passed |
| Rust/Tauri | 78 passed |
| TypeScript y Ruff crítico | limpios |
| Runtime staged | Vina/imports/health correctos |

No se acepta sustituir una prueba por un mock de la ciencia real, un `skip` o un warning.

### Gate beta privada

- Evaluación, Batch, Moldex y MolChat verdes.
- Dos cuentas en la misma PC completamente aisladas.
- Instalador funciona sin repositorio, Node, Rust ni Python externo.
- Upgrade desde una DB anterior probado y recuperable.
- Suite completa verde en checkout y PC/VM limpios.
- SBOM, notices, hashes, limitaciones y bundle de soporte disponibles.

### Gate 1.0 comercial

- Historial, Comunidad y Ciencia alcanzan su mínimo comercial.
- Instalación, upgrade, desinstalación y firma probados en Windows 10/11.
- Piloto observado con 5–10 investigadores y corrección de sus P0/P1.
- Sin P0/P1 abiertos; P2 restantes documentados con impacto y fecha.
- Limitaciones científicas publicadas y coherentes con la UI, dossier y MolChat.

## 12. Protocolo Codex → Claude

### Responsabilidades

- **Codex:** audita, define alcance, prioriza, escribe el brief, revisa el diff, reproduce pruebas,
  verifica ciencia/contratos/UX y decide el gate.
- **Claude:** implementa un paquete acotado, agrega pruebas y entrega evidencia. No decide por sí
  solo ampliar arquitectura, cambiar semántica científica ni declarar una pestaña terminada.
- **Humano:** autoriza git/push/release, provee certificado/PC de prueba y decide asuntos externos
  que impliquen dinero, datos o política de distribución.

### Tamaño y secuencia de los encargos

- Un encargo = uno o varios hallazgos relacionados, idealmente ≤1 día y ≤10 archivos de producto.
- Primero prueba de regresión roja, luego corrección mínima, después suites focales.
- Sólo un paquete de escritura activo en el worktree compartido.
- Después de cada entrega, Codex revisa antes de emitir el siguiente prompt.
- Cada 3–5 paquetes se ejecuta la suite amplia para detectar interacción acumulada.
- Al cerrar una pestaña se ejecutan unitarios, contratos, integración, E2E, persistencia/reinicio,
  aislamiento de dos cuentas y motor real cuando aplique.

### Prohibiciones permanentes para Claude

- No `git reset`, `checkout --`, limpieza global, commit ni push sin autorización.
- No `npm audit fix --force`, upgrades masivos ni reemplazos de arquitectura fuera de alcance.
- No mocks para satisfacer gates científicos, no silenciar excepciones y no convertir fallos en
  `skip`, fallback engañoso o resultado vacío.
- No cambiar un contrato backend sin actualizar consumidor, persistencia, documentación y tests.
- No mezclar mejoras visuales con cambios científicos en el mismo paquete.

### Plantilla de encargo

```text
Eres el obrero de implementación en D:\moldesign-build. El worktree contiene cambios del
usuario: presérvalos. No hagas commit, push, reset, checkout destructivo ni limpieza global.

PESTAÑA: <nombre>
PAQUETE: <ID>
HALLAZGOS AUTORIZADOS: <IDs>
OBJETIVO: <resultado observable>
ARCHIVOS PERMITIDOS: <lista>
NO CAMBIAR: <límites científicos/arquitectónicos>

Antes de editar, reproduce el fallo y agrega o identifica la prueba que lo demuestra. Implementa
la corrección mínima y conserva compatibilidad salvo autorización explícita.

ACEPTACIÓN:
1. <prueba científica/funcional>
2. <prueba de contrato backend–frontend>
3. <prueba de persistencia/reinicio o aislamiento>
4. <comandos focales exactos>

ENTREGA:
- causa raíz y diseño;
- archivos modificados;
- comandos y resultados exactos;
- riesgos, limitaciones y trabajo no verificado.

Detente si el arreglo exige cambiar semántica científica, migrar datos de forma destructiva,
salir de los archivos permitidos o tomar una decisión no cubierta por este brief.
```

## 13. Estado de ejecución y próxima acción

### EVAL-P0-01 — contrato terminal durable (verificado 2026-08-29)

**Hallazgo:** una corrida local podía terminar con `SUCCESS` y `molecule_id`, pero una única
lectura/serialización transitoria de SQLite devolvía `FAILURE` al frontend. La interfaz persistía
ese falso terminal y detenía el polling aunque la evidencia estuviera disponible en la siguiente
consulta.

**Corrección:** `desktop_job_status` sólo publica `SUCCESS` con un `EvaluationResultRead`
serializable. Una hidratación todavía no visible responde `STARTED/99` hasta cinco consultas; una
lectura posterior exitosa limpia el contador. El límite evita loaders infinitos. `SUCCESS` sin
`molecule_id` falla inmediatamente y cancelación/watchdog prevalecen aunque terminen mientras se
consulta SQLite. Los estados transitorios no se congelan en caché.

**Archivos del paquete:**

- `backend/services/docking/desktop_job_status.py`
- `backend/tests/test_desktop_job_status.py`
- `backend/tests/test_early_exit_no_sustituye_la_corrida.py` (contrato histórico alineado)

**Evidencia reproducida:**

- regresión antes del arreglo: 4 fallos nuevos; carrera concurrente: 2 fallos adicionales;
- suites focales backend ampliadas: `25 passed`;
- suite backend completa con `--basetemp` dentro del workspace: `911 passed, 3 skipped`;
- contrato frontend de runner + SSE: `42 passed`;
- `py_compile`: limpio; `git diff --check`: limpio;
- Ruff no estaba instalado en los intérpretes disponibles y no se declara como ejecutado.

### EVAL-P0-02 — recuperación por corrida inmutable (verificado 2026-08-29)

**Hallazgo:** `evaluation_results` es deliberadamente una proyección mutable de la última
evaluación de una molécula. Al reevaluar la misma molécula, esa fila cambiaba de `task_id`; tras
reiniciar, un caso anterior ya no podía autorizarse ni recuperarse, y el fallback de la interfaz
pedía sólo `molecule_id`, con riesgo de mostrar como histórica la evidencia de una corrida nueva.

**Corrección:** `evaluation_runs` conserva el snapshot científico por `task_id`. Status, SSE y
reapertura consultan primero esa corrida inmutable y sólo usan la proyección mutable para datos
anteriores al schema v11. `GET /evaluation/result/{molecule_id}` acepta `task_id` y, cuando se
especifica, falla cerrado si no existe esa combinación; el runner siempre lo envía al reabrir un
caso. Schema v12 añade el terminal `status/error_message`, de modo que cancelación o watchdog
puedan prevalecer incluso si el snapshot ya se había congelado.

**Evidencia reproducida:**

- la regresión roja inicial demostró tres fallos: sustitución de la primera corrida, autorización
  perdida tras reinicio y endpoint incapaz de leer un snapshot exacto;
- dos corridas sobre la misma molécula reaparecen con sus scores originales (`71` y `92`);
- la cuenta propietaria recupera la corrida anterior y una segunda cuenta recibe `403`;
- una corrida marcada `FAILURE` después de congelarse no resucita tras reiniciar;
- migración v11→v12 agrega el terminal y rellena snapshots antiguos como `SUCCESS`;
- backend focal: `41 passed`; backend completo: `916 passed, 3 skipped`;
- frontend runner/SSE: `42 passed`; suite frontend completa y TypeScript: verdes;
- OpenAPI regenerado y verificado; `py_compile` y `git diff --check`: limpios.

### EVAL-INT-006 — cadena idéntica entre preflight y submit (verificado 2026-08-29)

`EvaluationSubmitRequest` y `submitEvaluation` transportan la cadena que el caso comprobó. La
revalidación backend la incorpora a la huella fresca y rechaza con 409 una cadena distinta de la
registrada para el receptor. No se declara soporte multi-chain por corrida: introducirlo exige
persistir esa selección también en resultado, snapshot y dossier.

Evidencia: la regresión inicial recibió `None`; después, 6 pruebas backend y 18 frontend focales
pasaron, junto con TypeScript. La suite amplia quedó en `918 passed, 3 skipped`; la suite frontend
completa, OpenAPI, `py_compile` y `git diff --check` quedaron verdes.

### EVAL-INT-008 — procedencia reproducible visible (verificado 2026-08-29)

El contrato TypeScript y la vista activa ya exponen `receptor_sha256` y `docking_protocol`, con
conformaciones solicitadas/generadas, motor, exhaustividad, poses, semilla y advertencias. El hash
completo queda disponible para copiar y auditar. `receptor_path` se conserva en el contrato para
trazabilidad interna, pero la interfaz no muestra rutas locales de la cuenta.

Evidencia: la prueba de contrato exige los campos de procedencia; la prueba de UI comprueba el hash
y el protocolo completos, el comportamiento de corridas heredadas y que una ruta privada de
Windows nunca aparezca en pantalla.

### EVAL-FE-009 — una sola superficie y máquina de estados (verificado 2026-08-29)

Se retiraron `EvaluationContext.tsx` y `ProResults.tsx`, ambos sin consumidores, junto con los campos
fantasma de `EvaluationResult` que sólo alimentaban esa superficie. La vista activa usa el PDB ID
del target seleccionado en lugar de un campo inexistente del resultado. Los archivos eliminados
siguen recuperables desde el historial de Git.

### EVAL-EFF-010 — polling sin transportar el SDF (verificado 2026-08-29)

`GET /evaluation/status/{task_id}` ya no abre ni serializa el archivo de poses en cada consulta. El
SDF se obtiene únicamente mediante `/evaluation/files/poses/{id}` cuando la vista 3D lo necesita.
El campo backend `poseData`, sin consumidor frontend, se retiró también del contrato.

### EVAL-SCI-011 — preparación versionada de receptores, MVP (verificado 2026-08-29)

Evaluación permite derivar una variante privada e inmutable desde cualquier receptor accesible a
la cuenta. La variante conserva el receptor padre, la receta canónica (cadena, caja, cofactores,
política de aguas y altloc), la identidad del toolchain y SHA-256 separados de la fuente y del
PDBQT preparado. El receptor original y sus artefactos nunca se sobrescriben.

La whitelist de metales/cofactores ya no es sólo informativa: llega desde preflight hasta las rutas
de ejecución Vina. El MVP elimina todas las aguas y no declara todavía edición de protonación,
mutaciones, residuos faltantes ni estados alternativos; esos controles requieren una fase
científica posterior y validación explícita.

Evidencia: aislamiento de cuenta y autorización del receptor padre, migración aditiva v13,
determinismo/sensibilidad de hashes, contrato HTTP y formulario de UI cubiertos por pruebas.

### EVAL-SCI-012 — semántica nula y evidencia real en SAR (verificado 2026-08-30)

La superficie SAR ya no convierte métricas ausentes en cero, no calcula deltas cuando falta la
base o el análogo y no presenta 100 % de similitud si RDKit no pudo calcularla. Se retiraron los
seis análogos ficticios del frontend y se alineó la explicación con el fingerprint topológico
RDKit realmente utilizado. El selector de receptores reemplazó los `alert()` bloqueantes al
compartir por feedback accesible e impide dobles envíos.

Evidencia: helpers nulos y conservación de cero real cubiertos en backend; adapter y ausencia de
datos demo cubiertos en frontend; backend completo `927 passed, 3 skipped`, frontend completo
`546 passed` en 54 archivos y TypeScript limpio.

**Evidencia consolidada de los paquetes de Evaluación:** backend `923 passed, 3 skipped`; frontend
`542 passed` en 51 archivos; `tsc --noEmit`, OpenAPI vigente, diff OpenAPI sin incompatibilidades,
`py_compile` y `git diff --check`, verdes.

### Gate runtime de Evaluación — APROBADO 2026-08-30

Protocolo y evidencia: [63_GATE_RUNTIME_EVALUACION.md](63_GATE_RUNTIME_EVALUACION.md).

La aceptación ejecutó una corrida real con Vina/Meeko, reinició el backend sobre la misma
SQLite, recuperó por `task_id` el snapshot inmutable, comparó el resultado vivo/reabierto,
generó el dossier y comprobó seis superficies con una segunda cuenta. El polling no
transportó poses. Evidencia: `tmp/evaluation-runtime-20260830T180225Z/`; suite posterior:
backend `933 passed, 3 skipped`.

### Gate runtime de Batch — APROBADO 2026-08-30

Protocolo y evidencia: [64_GATE_RUNTIME_BATCH.md](64_GATE_RUNTIME_BATCH.md).

La aceptación ejecutó Vina/Meeko real, verificó semilla solicitada/observada/protocolizada,
duplicados, preparación automática y SHA-256 del receptor, dossier PDF/ZIP, reinicio y
recuperación de la última corrida desde backend. Una segunda cuenta recibió `404` en seis
superficies. Evidencia: `tmp/batch-runtime-20260830T182915Z/`; suites completas: backend
`937 passed, 3 skipped`, frontend `548 passed`; TypeScript limpio.

### Moldex — 16 hallazgos implementados, gate pendiente

Expediente: [65_MOLDEX_AUD_00_EXPEDIENTE.md](65_MOLDEX_AUD_00_EXPEDIENTE.md).

### MolChat — en curso desde 2026-08-30

Expediente: [66_MOLCHAT_AUD_00_EXPEDIENTE.md](66_MOLCHAT_AUD_00_EXPEDIENTE.md), §9 lleva el
marcador de estado.

Ocho hallazgos abiertos por la auditoría de lectura. **Tres cerrados y dos cerrados a medias:**
MOLCHAT-BE-002 (17 rutas exigen sesión; el cliente nunca había enviado cabeceras, así que en la
práctica la pestaña no tenía identidad de usuario), MOLCHAT-BE-004 (dueño de la conversación en
las cuatro capas, con migración idempotente de `ai_memory.db` y D-07 resuelta a favor del
invitado) y MOLCHAT-BE-006 (estado de conversación por cuenta en vez de por proceso).
MOLCHAT-BE-003 cerró la reconfiguración anónima del proveedor pero no la declaración de destino;
MOLCHAT-INT-007 cerró la identidad pero no la asimetría de capacidades entre ramas de transporte.

Evidencia recomprobada 2026-08-31: `17 passed` en las dos suites nuevas de la pestaña. Los cuatro
hallazgos abiertos se reconfirmaron leyendo el código, no por suposición.

**Decisiones D-08 y D-09, resueltas por el propietario el 2026-08-31.** D-08 = sí: el chat
lanza evaluaciones en segundo plano, y el motivo declarado es del eje SCI, no de capacidad
—«para sacar datos exactos y precisos, para no inventar información»—, así que fija tres
criterios de aceptación: mismo camino que `/evaluation/submit`, estado visible sin bloquear el
turno, y resultado citado a su `task_id` o abstención. D-09 = el proveedor y sus claves son por
cuenta.

**D-09 implementado el mismo día.** El almacén cifrado gana dimensión de cuenta con migración
que preserva lo heredado sin asignarle dueño; el registro se parte en catálogo de máquina y
configuración resuelta por cuenta, retirando la mutación del singleton que hacía
`providers/configure`; el proveedor activo pasa a ser por cuenta; y las dos sondas abiertas
adoptan identidad opcional, porque `configured` pasó a ser un dato de cuenta. Evidencia:
regresión `14 failed` → `14 passed`, backend completo **`1041 passed`**, diff OpenAPI sin
incompatibilidades nuevas.

**MOLCHAT-NET-005 y la mitad de interfaz de MOLCHAT-BE-003, implementados el mismo día.**
El destino de los datos se calcula del host resuelto para la cuenta y no del nombre del
proveedor —un `ollama` apuntado afuera sale de la máquina igual—; el turno no sale sin
consentimiento de esa cuenta para ese destino; el permiso se otorga a la huella
`proveedor@host`, así que mover el `base_url` no lo hereda; `providers/configure` rechaza con
409 un cambio de host sin confirmar y revoca el permiso anterior al aplicarlo; y la interfaz
declara el destino de forma permanente, avisando antes de que el investigador escriba. El
consentimiento no se hereda nunca, ni siquiera al invitado. Evidencia: regresión `5 failed` →
`21 passed`, backend **`1062 passed`**, frontend **`595 passed`**, `tsc` limpio.

**Con esto los cuatro P0 de MolChat quedan cerrados.**

**MOLCHAT-INT-007, implementado el mismo día.** `chat_with_info` era una segunda
implementación que no exponía herramientas ni pasaba por el ruteo de intención; ahora acumula lo
que produce `chat()`, así que hay una sola. La regresión midió el hallazgo en una línea:
`stream=true` usó `chat_with_tools` y `stream=false` no, y con las herramientas reales la misma
pregunta se contestaba con cálculo por una rama y con generación por la otra. Al implementarlo
apareció que dentro de `chat()` el parámetro `stream` no significa «responde de una vez» sino
«no emitas», de modo que la delegación va con `stream=True` y junta los trozos. Se retiró además
el fallback al usuario demo (D-05) en `evaluation_tools` y `session_tools`, que devolvían el
historial de una cuenta sintética como si fuera el de quien preguntaba, y `fallback_used` pasó a
describir el turno y no la conversación entera. Evidencia: `3 failed` → `8 passed`, backend
**`1070 passed`**, frontend **`595 passed`**.

**Las siete tareas restantes, cerradas el 2026-08-31.** En orden: la herramienta de docking
entra ahora por `registrar_corrida`, extraída del router para que el chat y `POST
/evaluation/submit` usen literalmente la misma puerta —identidad, receptor, preflight, gates y
dueño del `task_id`—, corre en segundo plano y cita su resultado o se abstiene; la persistencia
dejó de tragarse sus errores, con 503 al crear, 404 real al borrar y un aviso en el turno cuando
el disco no acepta un mensaje; la fuga por el índice de búsqueda se cerró en los tres almacenes
que la tarea nombraba —era la peor, porque `_prepare_messages_with_context` consultaba el FTS en
cada turno sin filtro y metía en el prompt de una cuenta los mensajes de otra—; la auditoría SCI
dejó de ser una nota y pasó a ser un mecanismo, con `clase` y `procedencia` obligatorias en las
27 herramientas, impresas en el bloque del turno y exigidas por prueba; la auditoría de frontend
hizo visible el turno que falla, devolvió el borrador, añadió reintento idempotente y separó la
evidencia de la prosa del modelo; la higiene puso topes de tamaño y tiempo donde no había,
redactó los secretos antes del log y quitó un escape doble que deformaba `MW < 500`; y el gate
llegó con su suite adversarial.

### Gate de MolChat — APROBADO 2026-08-31, con dos exclusiones declaradas

Protocolo y evidencia: [67_GATE_MOLCHAT.md](67_GATE_MOLCHAT.md).

La suite adversarial (`18 passed`) cubre los cuatro frentes del §8 y encontró dos fallos reales
que ninguna auditoría de lectura había visto. **Prompt injection podía elegir de quién era el
historial:** `execute_tool_step` ejecutaba el `user_id` que escribiera el modelo, y el turno de
MolChat lleva dentro texto de terceros (PubChem, ChEMBL, RCSB), así que bastaba con conseguir una
línea de llamada a herramienta con otra cuenta para reabrir la fuga que MOLCHAT-BE-004 había
cerrado. Y **una llamada remota sin autorizar en cada turno:** `pubchem_autolookup` salía a
PubChem sin mirar `allow_web` ni el consentimiento de NET-005. Los dos, corregidos.

Evidencia del gate de suite: backend **`1145 passed`**, frontend **`622 passed`** en 64 archivos,
`tsc` limpio. (Cifra del intérprete de desarrollo en ese corte; ver más abajo la corrección de
conteos, que declara el intérprete y las genera automáticamente.)

**Lo que el gate declara abierto en vez de medio arreglar.** **MOLCHAT-BE-009 (P1):**
`molgraph.db` es un cuarto almacén sin dimensión de cuenta que siete herramientas del chat leen.
No se filtró la lectura a propósito: el id de nodo es `mol_<smiles>`, compartido, y
`add_evaluation_node` sobrescribe sus propiedades con la última evaluación, así que filtrar sólo
la lectura dejaría a una cuenta pisando el score de otra **y encima ocultándolo** — el dato mal
en vez de sólo compartido. Cerrarlo exige **D-10**, una decisión de producto: qué es MolGraph,
el corpus público que el instalador distribuye o la memoria de cada cuenta. Y el gate es de
suite, no de runtime: falta una conversación real contra un modelo cargado y una evaluación
lanzada desde el chat con motor real.

**Queda anotado, sin declararse resuelto:** el consentimiento cubre el turno del chat y ahora
también el interruptor de las herramientas de red, pero sigue siendo un interruptor y no un
permiso por host. Es la misma política transversal que TRANS-NET-001 dejó abierta para
RCSB/UniProt.

## 14. Decisiones que seguirán requiriendo al propietario

- Autorizar branch, commit, push y ejecución remota de CI.
- Comprar/elegir el certificado Authenticode y custodiar la clave.
- Proporcionar PC/VM limpia con Windows 10/11.
- Elegir canal de distribución, política de updates y condiciones comerciales.
- Reclutar pilotos y aprobar qué datos pueden recopilarse con consentimiento.
- **D-10 (nueva, 2026-08-31):** decidir qué es MolGraph —corpus compartido que el instalador
  distribuye, o memoria por cuenta—. Bloquea MOLCHAT-BE-009. Opciones y lectura recomendada en el
  §7 del [expediente de MolChat](66_MOLCHAT_AUD_00_EXPEDIENTE.md).
- Autorizar `--write --allow-breaking` del snapshot OpenAPI. **Hecho el 2026-08-31** con la
  ruptura registrada en [docs/api/CHANGELOG.md](api/CHANGELOG.md); la decision queda documentada.

---

## 15. Dos sprints de cierre — corte del 2026-08-31

Doce encargos en dos tandas. Lo que sigue es el estado de cada uno, con su
evidencia y, donde lo hay, lo que quedó fuera y por qué.

### Sprint 1 (encargos 1–6)

**1 · Receptores realmente calibrados — hecho el software, pendiente la ciencia.**
`services/targets/calibracion.py` calcula el nivel en **un solo sitio** y lo
transporta el contrato: catálogo, preflight, resultado, dossier y MolChat. Cuatro
niveles distinguidos —calibrado, pipeline de familia, curado estructuralmente,
sin curar— y `ρ = 0.0` **no cuenta como calibración**: es el valor por defecto de
los dos únicos registros del catálogo y, de ser real, diría que no correlaciona.
La advertencia se muestra antes de ejecutar y junto al resultado. Se retiraron
dos frases que afirmaban de más: «validado en benchmark ciego» y «Spearman
pendiente de recálculo», que presentaba la ausencia de evidencia como un trámite.
Vigilado por `test_calibracion_de_receptores.py`,
`test_la_advertencia_de_calibracion_no_se_pierde.py` y
`RespaldoDelReceptor.test.tsx`. **El cálculo científico —holdout de 327,
calibraciones, benchmarks externos— sigue pendiente y ningún código lo sustituye.**

**2 · MolGraph público separado de la memoria privada — hecho.** Corpus
inmutable + almacén por cuenta, compuestos por vistas SQLite: una vista con
`UNION ALL` **no acepta escrituras**, así que ninguna lectura puede acabar
escribiendo en el corpus compartido. La clave del almacén privado es
`(user_id, id)`, de modo que dos cuentas que evalúan la misma molécula ya no se
pisan el score — que es lo que un simple filtro de lectura no habría arreglado.
Lo que no venía en el seed se migra como heredado sin dueño. Verificado sobre una
**copia de la base real**. `test_molgraph_publico_y_privado.py` (`16 passed`).

**3 · Gate runtime de Moldex — APROBADO.** `scripts/accept_moldex_runtime.py`.
Ver [68](68_GATE_RUNTIME_MOLDEX_Y_MOLCHAT.md).

**4 · Gate runtime de MolChat — APROBADO**, con modelo local y Vina reales.
Encontró **dos fallos que ninguna auditoría de lectura vio**: el texto del
investigador entraba sin escapar en la consulta FTS5 y devolvía HTTP 500 en la
primera pregunta con un SMILES dentro; y una corrida lanzada desde el chat
llegaba sin `docking_protocol`, con menos procedencia que una de la pestaña.

**5 · Política de invitado — hecha la parte técnica.** Los `else demo_user.id`
desaparecieron: el filtro era `user_id not in {cuenta, demo}`, así que **cualquier
cuenta registrada leía todo lo anónimo**. Ahora una molécula tiene un dueño y
sólo uno. `POST /auth/traspaso` mueve el trabajo del invitado a una cuenta
registrada: selectivo, transaccional, idempotente y en un solo sentido. Los gates
de Evaluación y Batch se **re-ejecutaron** tras el cambio de autorización, como
exige el protocolo. Falta el ofrecimiento en la interfaz al registrarse, el
traspaso de casos del lado cliente, y la decisión de producto sobre si el
invitado puede guardar y certificar.

**6 · Contrato OpenAPI — resuelto.** Ningún cliente usaba
`GET /evaluation/limit-status`; la ruptura se aceptó formalmente y se registró en
[docs/api/CHANGELOG.md](api/CHANGELOG.md). `--check` verde y en CI.

### Sprint 2 (encargos 7–12)

**7 · Consentimiento de red por host y servicio — hecho.** `services/ai/red.py`
es la **única** puerta de salida. Cada destino declara servicio, host, finalidad
y **qué datos salen**; el permiso es por cuenta y por destino con la misma huella
y el mismo almacén que el proveedor de chat; mover el host revoca; y hay modo
offline verificable (`MOLDESIGN_OFFLINE=1`) que niega todo aunque haya permiso.
Lo que lo hace real: la suite **intercepta la salida HTTP** y falla si algo llega
ahí sin permiso, y una prueba impide que cualquier módulo abra conexiones por su
cuenta. Se encontró una segunda vía —HuggingFace, en la búsqueda de modelos— y se
enrutó también. `test_consentimiento_de_red_por_destino.py` (`17 passed`).

**8 · Consolidación — hecha salvo lo que exige autorización.** En este árbol
había artefactos de **otro producto**: routers `.damaged` de LegalDesk, 91 MB de
binarios de terceros y una SQLite con datos, algunos depositados hoy mismo. Se
movieron **fuera del repositorio sin borrar nada**, a
`../moldesign-artefactos-fuera-del-repo/`, y quedan patrones en `.gitignore` para
que no vuelvan. El instalador nunca los habría recogido —copia árboles concretos,
no la raíz— pero ahora además excluye `*.damaged`, respaldos y `.hallmark/`.
La discrepancia de conteos tenía causa: **dos intérpretes**. El de desarrollo da
`1263 passed`; `python-embed`, el que se distribuye, `1225 passed, 3 skipped`. La
diferencia eran 36 pruebas del contrato del dossier que se saltaban por falta de
`pypdf` —ni en CI ni en el runtime embebido—, así que **ese contrato no se
verificaba en ningún sitio**. Ahora hay `requirements-test.txt`, CI lo instala, y
`scripts/report_test_counts.py --check` falla si una suite deja de recolectar en
silencio. Los commits coherentes y CI sobre checkout limpio siguen necesitando
autorización de commit y push.

**9 · Expediente de Moldex saneado.** §9 nuevo con estado actual separado de la
historia. **D-01 cerrada con datos**: de 210 evaluaciones hay 2 selladas y
**ninguna** con score nulo, así que el defecto nunca llegó a emitir un cero
fabricado. **D-02 cuantificada**: esos 2 sellos son anteriores a
`certified_task_id` —la columna no existe en esa base— y siguen declarados «SELLO
SIN CORRIDA» sin rellenarles el vínculo. D-04 (devnet/mainnet) sigue abierta y
bloquea la parte del gate que emitiría un sello real.

**10 · Ruido de las suites — de 180 a 2 avisos**, sin silenciar nada propio. La
causa principal era una línea nuestra: `dir()` sobre un modelo Pydantic tocaba
atributos deprecados 104 veces por corrida. Los de terceros se silencian uno a
uno y con su motivo; nunca un `ignore::DeprecationWarning` global, que taparía el
próximo aviso propio. El frontend queda sin ruido: los errores esperados se
silencian por su prefijo, y los componentes que se montaban sin `LanguageProvider`
ahora se montan con el árbol real.

**11 · UX verificable — hecha la parte automatizable.**
`frontend/e2e/ux-accesibilidad.spec.ts` (`12 passed`) corre en un navegador real
—jsdom no calcula layout ni color— y comprueba desborde a cuatro escalas,
tabulación con foco visible, nombres accesibles, contraste WCAG AA y truncamiento
recuperable. Encontró y se corrigieron: `--text-dim` daba **4.10:1** sobre el
fondo de tarjeta, por debajo de AA para texto de 14 px, y **tres controles sin
nombre accesible**. **No sustituye a mirar la aplicación en Windows a 125 % y
150 %**: el escalado de sistema afecta a fuentes y densidad de una forma que el
zoom del navegador sólo aproxima. Eso sigue siendo trabajo humano.

**12 · Gate de release — parcial.** Ver [69](69_GATE_DE_RELEASE.md). Cerradas dos
piezas: que **actualizar no destruya trabajo** (10 pruebas sobre las cuatro
migraciones de esta tanda, incluida la que mueve filas entre archivos) y el
**SBOM con licencias**. El SBOM encontró algo que bloqueaba publicar:
`ua-parser-js` bajo **AGPL-3.0-or-later** en el árbol de producción, por
`@solana/wallet-adapter-wallets` — una dependencia **declarada y jamás
importada**. Retirada: la AGPL desaparece y npm de producción baja de 1920 a 1353
paquetes. Instalador, firma Authenticode, VMs limpias, vulnerabilidades y piloto
siguen bloqueados por recursos del §14.

---

## 16. Pestaña Ciencia — deuda editorial cerrada, corte del 2026-08-31

La pestaña secundaria **Ciencia** publica el registro experimental: 151 artefactos
sellados leídos de sus manifests por `scripts/build_registro_cientifico.py`. Su mínimo
comercial del §9 pide contenido sincronizado con la implementación real, claims
respaldados, límites visibles y **no contradecir resultados**. Fallaba en los cuatro.

**La deuda estaba declarada por el propio constructor y nadie la leía.** El script imprime
al final los hallazgos y refutaciones sin paper —las dos columnas que sostienen claims— y
eran ocho. Se escribieron los que **abren línea editorial propia**, que son ocho:

| Paper | Categoría | Qué faltaba decir |
|---|---|---|
| `MF-28` | refutación | El roadmap probabilístico convierte 4 de 33 contra 26 de Vina, y el porqué vale más que el veredicto: la fracción mediana de nodos libres del bolsillo es **0.00417** |
| `MF-29-EMP` | hallazgo | 64× de `exhaustiveness` mueve 3 complejos de 48, y el testigo que decía lo contrario medía en otra escala |
| `MF-29-EMP-COR` | hallazgo | El salto de escala por `TORSDOF 0` vale **1.055** kcal/mol y el déficit leído como fallo de búsqueda valía 0.491 |
| `MF-33-EXT` | hallazgo | Cobertura 0.9224 contra el listón 0.90 que `MF-02D` falló con 0.7931 |
| `MF-33-ORD` | hallazgo | El orden real **atenúa** la desviación: `p_perm` = 0.9773, y `conf0` es un confórmero medio |
| `MF-33-TOP1` | hallazgo | La cobertura sube 26.7 pp y al top-1 llegan 11.2 |
| `MF-33-A3` | medición | **Cierra el defecto abierto de `MF-33`**: 261 poses desde el mismo confórmero dan el mismo 19 que 9 poses |
| `MF-33-H-COR` | corrigendum | El 2.64% medía nuestra reconstrucción de hidrógenos: 99.48% con los pesados a 0.0 Å de desplazamiento |

**Dos registros se declararon `no-paper-standalone` en vez de escribirles ficha, y esa fue
una corrección de criterio del propietario.** `MF-29-EMP-EXT` recupera dos complejos que
expiraron contra un `timeout` en duro: es mantenimiento de cohorte, no un experimento con
línea editorial, y su evidencia vive dentro del paper de `MF-29-EMP`. `MF-33-PB` tiene su
cifra de cabecera invalidada, así que su valor editorial está en el corrigendum que la
reemplaza. No se escriben papers para llenar columnas.

**Eso obligó a resolver el aviso de otra forma, y la nueva es mejor.** Si el aviso de
«estas cifras ya no valen» vive en la prosa, un registro sin paper no lo tiene. Ahora vive
en el contrato: `_taxonomia.json` declara el mapa `reemplazos`, el constructor lo emite
como `reemplazado_por`, y la vista lo pinta en la tarjeta y como aviso enlazado en la
ficha. Un lector que entra por enlace directo a `MF-33-PB` ve que su 2.64% fue reemplazado
por `MF-33-H-COR` sin depender de que alguien escribiera un párrafo.

**Dos contradicciones con manifests sellados, corregidas.** El paper de `MF-33` decía que
su magnitud «no es citable hasta que `MF-33-A3` la resuelva» y que la etapa 2 seguía
pendiente. Las dos cosas habían ocurrido: `MF-33-A2` partió la brecha —7 complejos el
presupuesto, 7 el ensemble— y la razón sellada de `MF-33-A3` **ordena expresamente levantar
la etiqueta**. La ficha llevaba diez días contradiciendo a dos artefactos propios.

En consecuencia `_taxonomia.json` separa `defecto-abierto` de `defecto-levantado`:
`MF-33` y `MF-33-A2` pasan al segundo; `MF-33-PB` y `MF-33-TOP1` **conservan el primero a
propósito**, porque sus tasas quedan reemplazadas para siempre y no reparadas —lectura de
la que dependen [52](52_PAPER_MF33_ESQUELETO.md) y [54](54_PAPER_MF33_MANUSCRITO.md)—.

**Fecha de validez visible.** El pie del registro decía cuántas fichas tienen paper y quién
las generó, pero no **cuándo**. `generado_en` ya viajaba en el JSON sin pintarse; ahora se
muestra, con la advertencia de que un experimento sellado después de esa fecha todavía no
está ahí.

**Y una guarda, porque el modo de fallo es silencioso.** `frontend/public/registro/` es
JSON estático: sellar un experimento o escribir un paper sin reconstruir deja la pestaña
contando una realidad vieja y nada falla. `backend/tests/test_registro_cientifico.py`
(8 pruebas) exige registro al día, cero deuda en las dos columnas protagonistas, `titulo` y
`entradilla` en todo paper, ningún paper huérfano, y que **todo registro etiquetado
`defecto-abierto` declare su reemplazo en el contrato** y que ese campo llegue al JSON
publicado.

Evidencia: la guarda de deuda falla sobre el estado anterior con siete IDs. Después:
`8 passed`, `build_registro_cientifico.py --check` al día con **64 de 151 con paper**
—eran 56—, `tsc --noEmit` limpio y suite frontend `642 passed`. Los 2 fallos restantes de
esa suite son de `DownloadNotifications.test.tsx`, trabajo en curso del §62 que monta el
componente sin `AuthProvider`, y no se tocaron.

**Lo que sigue abierto en Ciencia**, y no lo cierra código: los 87 registros sin paper de
las columnas de contexto —mediciones, prerregistros e inconclusos— publican su ficha
generada desde el manifest, que es la política declarada y no una deuda; y el cálculo
científico del §15.1 —holdout de 327, calibraciones, benchmarks externos— sigue pendiente,
con la advertencia de calibración mostrándose antes de ejecutar y junto al resultado.

---

## 17. Historial y traspaso del invitado — corte del 2026-09-01

### Historial: tres defectos medidos, no supuestos

El §9 pide que Historial sea **una proyección fiel de DB, no otro almacén de estado**.
Tenía su propia contabilidad.

**HIST-BE-001 — el marcador y la tabla contaban poblaciones distintas.**
`/history/evaluations` lista **todas** las moléculas de la cuenta, que es la política que
el propio router declara: «todas las evaluaciones se registran automáticamente; `is_saved`
sólo significa promovido a Moldex». Pero las seis cifras de `/history/stats` filtraban por
`is_saved == True`, que es literalmente el filtro de **Moldex** en `db/repository.py`. Una
cuenta con veinte evaluaciones y ninguna promovida leía **«Total 0» encima de veinte
filas**. Corregido en las seis: total, completadas, fallidas, mejor score, promedio y
targets únicos.

**HIST-BE-002 — una molécula sin dueño la adoptaba quien la pidiera.**
`POST /history/save/{id}` autorizaba con `mol.user_id is not None and mol.user_id !=
current_user.id`, y a continuación hacía `if mol.user_id is None: mol.user_id =
current_user.id`. Mover trabajo del invitado es `POST /auth/traspaso` —selectivo,
transaccional, idempotente—, y esto era una segunda puerta que se lo saltaba. Ahora hay una
guarda con nombre, `_require_molecule_owner`, que responde **404 y no 403** por la razón
que ya fijó BATCH-BE-002: el 403 confirma que el recurso existe.

**HIST-FE-003 — el estado más común se pintaba crudo y en inglés.**
`MoleculeStatus` vale `pending/validated/docking/evaluated/failed`. El mapa de la insignia
conocía `completed/SUCCESS/failed/FAILURE/running/PENDING`: nombres de tarea, no de
molécula. Una evaluación terminada —`evaluated`— caía al `??` y se mostraba como
**«evaluated»** mientras Evaluación decía «Completada» **para la misma corrida**.

Además, el encabezado prometía «evaluaciones que has decidido conservar» sobre una lista
que las trae todas; y el contrato declaraba en TypeScript un `sa_score` que el backend
nunca enviaba.

**Y lo que faltaba para «apertura del caso/corrida exactos»:** el resumen no llevaba
`task_id`, que es la identidad con la que `evaluation_runs` recupera el snapshot inmutable
(EVAL-P0-02). Ahora viaja en el contrato y se muestra por fila, junto a la marca de las que
además están en Moldex. **Abrir el caso desde el historial sigue abierto (HIST-INT-004)**:
exige materializar un caso desde Evaluación a partir de `(molecule_id, task_id)`, y eso es
una decisión de arquitectura que este paquete no toma por su cuenta.

Guarda: `backend/tests/test_historial_es_proyeccion_de_la_db.py` (8 pruebas). Rojo antes
con 7 fallos; verde después. Backend completo **`1282 passed`**; OpenAPI regenerado —los
tres campos nuevos son aditivos— y `--check` verde.

### Traspaso del invitado: el ofrecimiento que faltaba

El sprint 1 dejó hecho el backend y anotó lo que faltaba: «el ofrecimiento en la interfaz
al registrarse, el traspaso de casos del lado cliente». Las dos piezas están.

**Recordar de quién se viene.** `_persist` sobrescribe `moldesign_auth`, así que la
identidad del invitado desaparecía justo en el acto que la necesita. Ahora el auto-login de
escritorio —la **única** puerta por la que se entra como invitado— la registra. No se
deduce del email ni del nombre: deducir la identidad de una cuenta por su texto es como se
acaba tratando de invitado a un usuario real.

**Saber qué ofrecer sin romper el aislamiento.** Una cuenta registrada no puede listar el
trabajo del invitado, y así debe seguir. Quien sí lo sabe es el equipo: los casos viven en
el cliente bajo el id de su dueño y cada corrida conserva su `moleculeId`.

**Mover también los casos.** El backend mueve moléculas y cohortes; los casos son del
cliente y se quedaban atrás, de modo que el investigador recuperaba los resultados **sin la
hipótesis que los explicaba**. `adoptCase` es una operación nueva y separada de
`updateCase` a propósito: aquélla comprueba que el caso ya existe para no crear por
accidente, y ésta es crear con el dueño cambiado a petición explícita. Tenerlas separadas
impide que un `updateCase` distraído mueva casos entre cuentas.

**Orden deliberado: backend primero, casos después.** Si el backend falla no se ha tocado
un solo caso, el ofrecimiento sigue en pie y reintentar es seguro porque el endpoint es
idempotente. Al revés quedarían casos de una cuenta apuntando a moléculas de otra.

La superficie no mueve nada sola, cuenta lo que hay —«3 casos, 1 con resultado», no «3
evaluaciones»— y se puede rechazar. Un caso que no se puede mover **se cuenta**, en vez de
desaparecer.

Evidencia: `frontend/lib/__tests__/traspaso.test.ts` (`10 passed`) cubre que nada se mueva
sin pedirlo, que un fallo del backend no deje casos huérfanos, que no se ofrezca traspaso a
la propia cuenta invitada —el 403 del backend— y que un caso irrecuperable se reporte.
Suite frontend **`652 passed`**, `tsc --noEmit` limpio.

**Declarado y no hecho:** las cohortes no entran en el ofrecimiento porque no hay
inventario local de cribados; el endpoint ya acepta `cohort_ids`, así que la pieza que falta
es el inventario, no el traspaso. Y sigue siendo del propietario la decisión de producto
sobre si el invitado puede guardar y certificar.

### Lo que queda del §61, y por qué no lo cierra código

- **Comunidad** — excluida por decisión del propietario en esta tanda.
- **Escalado de Windows al 125% y 150%** (encargo 11) — `ux-accesibilidad.spec.ts` cubre lo
  automatizable; el escalado del sistema afecta a fuentes y densidad de una forma que el
  zoom del navegador sólo aproxima. Es trabajo humano.
- **Gate de release** (encargo 12 y doc 62) — instalador, firma Authenticode, VMs limpias,
  el piloto sigue bloqueado por los recursos del §14; la licencia MIT de RTMScore quedó resuelta el 2026-09-01.
- **La calibración científica** (encargo 1) — holdout de 327 y benchmarks externos: es
  cómputo, no código.

---

## 18. Verificación previa a la primera build pública — 2026-09-01

### Los cuatro caminos, ejecutados con motor real

| Gate | Resultado | Evidencia |
|---|---|---|
| Evaluación runtime | **PASS** | `tmp/evaluation-runtime-20260901T061702Z` — Vina 1.2.7, afinidad −5.489 kcal/mol, reinicio del backend, reapertura por `task_id`, dossier, y 6 negativas a la segunda cuenta |
| Batch runtime | **PASS** | `tmp/batch-runtime-20260901T061819Z` |
| Moldex runtime | **PASS** | `tmp/moldex-runtime-20260901T062527Z` |
| Backend completo | **1289 passed** | intérprete de desarrollo |
| Frontend | **652 passed** en 69 archivos | 2 fallos restantes en `DownloadNotifications.test.tsx`, trabajo en curso del §62 |
| TypeScript | limpio | `tsc --noEmit` |
| OpenAPI | vigente | regenerado; el campo nuevo es aditivo |

El resultado vivo y el reabierto coinciden campo a campo, y el `receptor_sha256`
viaja en los dos.

### Eficiencia: lo que costaba y ya no

El mandato era que la aplicación se sienta rápida en equipos modestos. Cuatro
cosas medibles, todas en el camino crítico:

**1 · El selector de receptores animaba 387 tarjetas, una por una.** Una
coreografía GSAP les daba opacidad, desplazamiento, escala y `filter: blur(3px)`
escalonados por familia. `filter: blur` fuerza repintado de capa; animar cientos
de nodos a la vez satura el hilo de composición. Retirada entera.

**2 · Y esperaba 300 ms fingidos antes de enseñarlas.** `setTimeout(..., 300)` con
un orbe girando: el catálogo ya estaba en memoria cuando el modal se abría. Esa
espera no cargaba nada. Retirada.

**Y había un defecto escondido detrás:** las tarjetas nacían con `opacity-0` en la
clase y sólo GSAP las hacía visibles. Si la animación no llegaba a correr —un
re-render rápido, StrictMode, el modal reabierto— el catálogo se quedaba **en
blanco con los datos ya cargados**. Ahora aparecen porque están, y
`content-visibility: auto` deja que el navegador se salte el trazado de las
familias fuera de pantalla.

**3 · Tres desenfoques de pantalla completa apilados** (`backdrop-blur-xl`,
`-2xl`, `-md`) recomponiéndose en cada frame sobre el modal. Sustituidos por
fondos sólidos. Y `transition-all` —que anima también sombra y layout— pasó a
`transition-colors` en tarjetas, pestañas y botones.

**4 · El orbe de carga escribía `width` y `height` sesenta veces por segundo.**
Dos propiedades que fuerzan **layout**, en un `setInterval` que además **no se
frena cuando la ventana pasa a segundo plano**: seguía recalculando con la
aplicación minimizada. Ahora es `requestAnimationFrame` y sólo escribe `transform`
y `opacity`, que el compositor resuelve sin volver a medir. Se ve igual.

**5 · La previsualización 3D de la caja de docking giraba a 60 fps para una caja
que no se mueve.** Era un `useFrame` cuyo cuerpo salía sin hacer nada en
prácticamente todos los fotogramas. Ahora la cámara se recoloca en un efecto y el
`Canvas` renderiza **bajo demanda**: un fotograma cuando algo cambia, ninguno
mientras nadie toca nada.

Guardas: `components/interfaces/pro/__tests__/TargetSelectorModal.test.ts` (7
pruebas) fija que no vuelvan el GSAP por tarjeta, la espera fingida, el
`opacity-0` fantasma, los desenfoques ni el `transition-all`.

### ENG-001 — el menú avanzado ofrecía seis motores que no existen

Detalle completo en [62](62_AUDITORIA_TERCEROS_Y_LAUNCHER.md). En corto: de los
siete motores del menú, **sólo AutoDock Vina se puede ejecutar**. QuickVina 2 no
se empaqueta; DiffDock, ESMFold, ESMFold Pro, RFdiffusion y ColabFold son clientes
de servicios externos que este instalador no trae ni levanta. El módulo
descargable de ESMFold —8.4 GB— **no habilita ESMFold**: ningún código carga pesos
locales.

La ruta de moléculas pequeñas ya lo bloqueaba en preflight. La peptídica no: caía
a Vina con exhaustividad 4 **y una caja fija de (20, 30, 28)** cuando el caso no
declaraba una. Corregido: sin caja no hay corrida, y con caja el aviso dice
`MOTOR SUSTITUIDO` con el nombre del motor que se pidió. `GET /evaluation/engines`
publica qué puede ejecutar la instalación y el modal apaga lo demás con su motivo.

**Decisión pendiente del propietario:** qué se hace con el módulo de ESMFold del
manifiesto. Publicar una descarga de 8.4 GB que no habilita la función que anuncia
no es defendible; las salidas son retirarlo del manifiesto para 1.0 o construir el
sidecar que lo consuma.
