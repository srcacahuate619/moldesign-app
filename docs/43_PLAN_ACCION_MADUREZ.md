# 43 — Plan de acción para madurez de MolDesign

**Fecha:** 2026-08-15  
**Estado:** Plan operativo vigente  
**Fuente:** Rebaseline de `AUDITORIA_CONSOLIDACION_DESKTOP_2026-08-09.md`  
**Orden obligatorio:** **Código → Calidad → Eficiencia → Ciencia**

> **Repriorización 2026-08-15:** por decisión explícita del maintainer, instalación/release queda diferida y la campaña científica pasa a prioridad 1. Las salvaguardas de este plan siguen vigentes. El programa experimental detallado vive en [`49_PROGRAMA_EXPERIMENTAL_CIENTIFICO.md`](49_PROGRAMA_EXPERIMENTAL_CIENTIFICO.md).

---

## 1. Objetivo

Llevar MolDesign desde un pipeline desktop funcional y científicamente
prometedor hasta una plataforma madura, reproducible y preparada para crecer,
sin romper el flujo de producción que funciona actualmente.

Este plan separa deliberadamente cuatro tipos de trabajo:

1. **Código:** recuperar coherencia interna y eliminar regresiones.
2. **Calidad:** convertir esa coherencia en garantías automáticas de release.
3. **Eficiencia:** optimizar únicamente después de medir un baseline verde.
4. **Ciencia:** experimentar con libertad sobre una plataforma estable.

La fase científica se deja al final a propósito. Cuando empiece, debe existir un
núcleo de producción tan estable que sea posible probar ideas agresivas,
refutarlas y descartarlas sin contaminar el producto distribuido.

## 2. Reglas de protección

Estas reglas aplican durante todo el plan:

- No mezclar una corrección de producción con un experimento científico.
- No eliminar un adaptador legacy hasta que todos sus callers estén migrados y
  exista una prueba del contrato sustituto.
- No cambiar simultáneamente generación de poses, features, modelo y métrica.
- Todo artefacto de producción debe tener hash, schema, dataset, split, versión
  de código y métricas asociadas.
- Un resultado experimental sólo se promueve cuando supera un gate
  preregistrado; un NO-GO no se “arregla” cambiando el criterio después.
- Los tests pueden estar obsoletos, pero no se borran para conseguir verde: se
  documenta el contrato nuevo y después se actualizan.
- Cada fase termina con un punto recuperable: commit/tag, manifiesto y evidencia
  de pruebas. El working tree no es una estrategia de release.

## 3. Definición global de terminado

MolDesign alcanza una base madura cuando:

- una máquina Windows limpia puede instalar, construir y ejecutar la app desde
  instrucciones versionadas;
- backend, rescoring, frontend y Tauri pasan la matriz de release;
- el E2E científico mínimo usa Vina real y valida un resultado persistido;
- el runtime desktop no necesita Redis, Celery, MinIO ni PostgreSQL;
- documentación, OpenAPI, catálogo, manifiestos y código se verifican entre sí;
- los tiempos y memoria del pipeline tienen presupuestos medidos;
- la rama de experimentación científica no puede reemplazar artefactos de
  producción sin pasar gates explícitos.

---

# Fase 0 — Contención y baseline

**Propósito:** crear una frontera segura antes de tocar código.

## A-00.1 — Capturar el estado que funciona hoy

**Acciones:**

- Registrar commit base, estado del working tree y versión distribuida.
- Guardar hashes de modelos, binarios, catálogo de 387 targets y schema SQLite.
- Ejecutar y conservar el smoke desktop existente.
- Elegir 2–3 evaluaciones reales representativas: receptor curado, receptor
  subido ya preparado y receptor que requiere curación automática.
- Guardar sus entradas, configuración, outputs y tolerancias aceptables.

**Salida:** paquete `release-baseline` que permita responder “¿qué cambió?” y
volver al comportamiento conocido sin depender de memoria humana.

## A-00.2 — Congelar expansión funcional

Mientras Código y Calidad no estén verdes:

- no agregar nuevas etapas al pipeline principal;
- no promover nuevos modelos;
- no modificar pesos o thresholds científicos de producción;
- permitir investigación sólo en scripts/artefactos aislados que el runtime no
  cargue por defecto.

**Gate F0:** baseline capturado, recuperación comprobada y lista única de
regresiones actuales.

---

# Fase 1 — Código

**Meta:** conseguir coherencia funcional. El orden dentro de esta fase es
deliberado: build y contratos centrales antes de refactors o purga cloud.

## C-01 — Reparar el build frontend

**Problema:** `next build` compila el bundle, pero falla el type-check por dos
tipos incompatibles de Vite entre el árbol principal y Vitest.

**Acciones:**

- Inspeccionar el árbol efectivo con `npm ls vite vitest @vitejs/plugin-react`.
- Alinear versiones y deduplicar Vite; evitar casts que oculten el conflicto.
- Impedir que configuración exclusiva de tests contamine el type-check de
  producción si no necesita formar parte del proyecto Next.js.
- Verificar `npm test`, `npm run build:desktop` y build Tauri.

**Criterio:** build limpio desde `npm ci`, sin dependencia de `node_modules`
preexistente.

## C-02 — Alinear el registro del pipeline

**Problema:** `selectivity` entró en `STAGE_REGISTRY`, pero el contrato canónico
y sus pruebas conservan ocho etapas.

**Acciones:**

- Decidir si selectividad es etapa canónica, subpipeline opcional o job
  posterior independiente.
- Actualizar una única fuente para orden, dependencias, defaults, skipped events
  y labels frontend.
- Probar configuración legacy, default, todas habilitadas y cancelación.

**Criterio:** registro, runner, SSE, API y frontend derivan el mismo grafo.

## C-03 — Reparar MolChat streaming y llama-server

**Problemas:** tres tests de `AIContext` fallan; `[DONE]` se agrega al contenido,
warnings/partial desaparecen y los tests de `LocalLLM` muestran divergencia
sync/async.

**Acciones:**

- Definir formalmente el framing SSE: token, warning, done, error y cancel.
- Usar un decoder único compartido por tests y cliente.
- Separar probes sync y async de llama-server con interfaces explícitas.
- Garantizar que mocks de health nunca generen una conexión real.
- Probar UTF-8 fragmentado, aborto, respuesta parcial y cierre inesperado.

**Criterio:** ninguna pérdida de texto parcial y cero requests reales en tests.

## C-04 — Aislar el lifecycle de SQLite en tests

**Problema:** fixtures que inyectan una DB temporal pueden terminar usando el
engine global creado con `%USERPROFILE%/MolDesign/data`.

**Acciones:**

- Hacer explícito el lifecycle `set_engine/reset_engine/dispose`.
- Evitar capturar settings en import time cuando afecten paths persistentes.
- Añadir guard que prohíba tests contra la DB real.
- Probar arranque limpio, migración, reinicio y dos suites en distinto orden.

**Criterio:** todos los tests de DB operan dentro de su `basetemp` y dejan cero
handles abiertos.

## C-05 — Clasificar y reparar regresiones backend

**Bloques actuales:**

- certifier/Solana;
- llama-server;
- pipeline registry;
- health/bootstrap;
- target ingestion.

Para cada fallo registrar: contrato esperado, comportamiento actual, decisión y
prueba de regresión. Las integraciones opcionales deben degradar, no bloquear el
nucleo desktop.

**Criterio:** `backend/tests` verde sin red externa ni credenciales.

## C-06 — Recuperar coherencia del sidecar de rescoring

**Bloques actuales:**

- API esperada de `InteractionFeatureExtractor` frente a implementación actual;
- entrenamiento sintético sin las nuevas features `log_mw` y compañía;
- `PoseFilter` rechaza poses centrales de sus fixtures;
- `CURATED_FAMILIES` cambió casing/contenido;
- fallback GNN devuelve `NaN`, mientras el test histórico espera 0.5.

**Decisiones necesarias:**

- Un fallback científico no debe fabricar confianza. Preferencia: devolver
  `None/NaN` acompañado de estado explícito `unavailable`, y actualizar todos
  los consumidores para no tratarlo como número.
- Separar extractor de producción 167 features, extractor legacy y extractor de
  pose-selector; los nombres no deben referir a interfaces incompatibles.
- Las familias curadas deben derivar del catálogo fuente, con IDs normalizados.
- PoseFilter debe usar fixtures en coordenadas compatibles con su box real.

**Criterio:** `rescoring/tests` verde y contratos de ausencia explícitos.

## C-07 — Hacer seguro el manifiesto v4

**Problema:** el generador v3 elimina `pose_selector_v06`.

**Acciones:**

- Definir schema JSON v4.
- Generar todos los modelos desde un registro declarativo.
- Añadir `--check`, que compare sin escribir.
- Fallar ante downgrade de versión, artefacto perdido o hash distinto.
- Verificar el manifiesto en health y en build de release.

**Criterio:** dos ejecuciones producen bytes idénticos salvo que cambie una
entrada declarada; nunca se pierde un modelo existente.

## C-08 — Completar la purga cloud contract-first

Orden de remoción:

1. Implementar event bus local para progreso en vivo.
2. Migrar `/evaluation/stream` fuera de Redis.
3. Renombrar `CacheClient` hacia una abstracción local y retirar implementación
   Redis muerta.
4. Migrar aliases `upload/download/object` hacia nombres neutrales.
5. Retirar bootstrap/settings/excepciones MinIO.
6. Versionar el rename de `celery_task_id` sin romper SQLite existente ni API.
7. Eliminar traducciones frontend Celery/Redis cuando ya no puedan emitirse.

**Criterio:** búsqueda de imports/config cloud vacía en runtime; pruebas de
submit, polling, stream, cancelación, reinicio y storage verdes.

## C-09 — Refactor modular, únicamente con suites verdes

Orden sugerido:

- `chat_service.py`: transporte, memoria, tools y respuesta determinista.
- `queue_handler.py`: lifecycle de jobs, ejecución científica y persistencia.
- `evaluation.py`: submit/status, archivos, reportes y stream.
- `pdf_generator.py`: view-model científico y renderers de secciones.

Cada extracción debe ser mecánica, pequeña y sin cambiar resultados.

**Gate Código:** builds verdes; backend/rescoring/frontend verdes; Tauri
compila; manifiesto v4 estable; cloud fuera del runtime; resultados golden sin
cambios no explicados.

## C-10 — Hacer la cancelación local por tarea y durable

**Hallazgo de auditoría (2026-08-15):** el dispatcher permite hasta cuatro
evaluaciones concurrentes, pero los procesos MM-GBSA/selectividad activos se
guardan en listas globales. `POST /evaluation/cancel` termina todos los
procesos de esas listas, no sólo los pertenecientes a `task_id`. Además, no hay
un token de cancelación que el wrapper consulte antes y después del pipeline:
una evaluación ya en curso puede terminar y sobrescribir el `FAILURE` de la
cancelación con `SUCCESS`; tras reiniciar, SQLite puede recuperar el resultado
como éxito si no se persistió la cancelación. Es una carrera de lifecycle, no
un problema científico.

**Acciones:**

- registrar subprocesses y solicitud de cancelación por `task_id`;
- no iniciar un job cancelado que aún espera semáforo y no sobrescribir su
  estado terminal al volver del pipeline;
- persistir la cancelación asociada a la molécula cuando ya exista, sin borrar
  sus archivos/resultados históricos por defecto;
- diferenciar en la API el alcance real de la cancelación y emitir un evento
  SSE terminal coherente;
- probar dos jobs simultáneos, cancelación en cola, durante subprocess y justo
  antes de persistir, además de recuperación después de reinicio.

**Criterio:** cancelar A no termina procesos de B; A nunca reaparece como
`SUCCESS` después de ser cancelado y SQLite recupera el mismo estado terminal.

**Cierre operativo (2026-08-15):** MM-GBSA y selectividad en background se
registran ahora por `task_id`; el endpoint rechaza una cancelación sin ID,
termina sólo los hijos registrados de esa tarea y marca una solicitud de
cancelación durable. El wrapper no inicia un job cancelado en cola, no
sobrescribe un `FAILURE` terminal al regresar del pipeline y persiste ese
estado en SQLite sin borrar resultados ni archivos útiles para soporte. Los
contratos cubren dos tareas concurrentes, cancelación en cola/en carrera y
recuperación después de vaciar registro y cache.

**Límite deliberado:** esta es cancelación cooperativa. El docking o una
llamada nativa que ya está ejecutándose no se preempta de forma insegura; se
detiene al llegar a su límite propio y nunca vuelve a publicar éxito. Convertir
Vina y cada cálculo nativo en procesos preemptables requiere instrumentar esos
callers como trabajo separado y se mantiene fuera de este corte de estabilidad.

---

# Fase 2 — Calidad

**Meta:** impedir automáticamente que los problemas de la Fase 1 reaparezcan.

## Q-01 — Matriz CI de release

Jobs mínimos y separados:

1. Backend unit/integration en Python del runtime embebido.
2. Rescoring unit/integration y gates científicos baratos.
3. Frontend test + type-check + build desktop.
4. Rust fmt/clippy/check.
5. Smoke desktop con SQLite/filesystem reales.
6. Manifest `--check`, CSP y documentación.

Usar `npm ci` y dependencias Python bloqueadas. No anunciar CI verde si una
superficie distribuida no forma parte del workflow.

## Q-02 — Pirámide de pruebas

- **Unitarias:** parsers, features, scoring y transformaciones.
- **Contrato:** API, SSE, schemas, manifest y filesystem lógico.
- **Integración:** SQLite, dispatcher, sidecar y subprocess wrappers.
- **E2E de infraestructura:** smoke actual con ciencia falsa.
- **E2E científico mínimo:** Vina real sobre un caso pequeño y determinista.
- **Golden:** PDF/API/poses con tolerancias explícitas, no snapshots frágiles.

## Q-03 — OpenAPI y documentación como código

- Generar y versionar el OpenAPI actual, sin fijar a mano el conteo de rutas.
- Versionar snapshot y detectar breaking changes.
- Sustituir `docs/31` como referencia por un mapa actual generado.
- Actualizar INDEX con arquitectura y documentos 38–43.
- Derivar conteo de targets, modelos y métricas desde artefactos.
- Agregar link checker y detector de rutas inexistentes.

**Evidencia de auditoría (2026-08-15):** la generación actual produce 97
paths y 100 operaciones. Al revisar ese schema se detectó y retiró un segundo
handler inalcanzable para `POST /targets/{target_id}/share`, que retenía una
sincronización cloud muerta y generaba un `operationId` duplicado. El runtime
queda con 101 rutas declaradas y cero parejas método/ruta repetidas; existen
contratos para esa propiedad y para IDs de operación únicos. `docs/31` queda marcado como
inventario histórico de UX: enumera rutas sin los prefijos actuales y no debe
volver a usarse como referencia backend hasta que Q-03 genere el snapshot.

**Primer cierre Q-03 (2026-08-15):**
`scripts/generate_openapi_contract.py` genera el schema versionado
`docs/api/openapi-current.json` y `docs/45_API_CONTRACT_CURRENT.md` desde la
misma instancia FastAPI. El modo `--check` compara ambos contenidos de forma
determinista y ya es parte del job backend de CI; por tanto una ruta añadida,
retirada o alterada no puede dejar la documentación generada en silencio. Los
conteos y el SHA aparecen derivados del schema, no escritos a mano. Antes de
sobrescribir un snapshot que retire rutas/operaciones/respuestas 2xx o añada o
retire parámetros requeridos, el generador exige `--allow-breaking` explícito.

El mismo job ejecuta `scripts/check_docs_links.py --check`. El primer barrido
separó un falso positivo de un SMILES en código inline de 14 referencias
inequívocas: rutas relativas desde un documento histórico, enlaces a license/
contributing en raíz y referencias a informes históricos ausentes. Tras
corregirlas o marcarlas explícitamente como no incluidas, todos los enlaces
locales del directorio `docs/` son válidos. El diff de compatibilidad básico
ya detecta rutas/operaciones/respuestas 2xx retiradas y cambios de parámetros
requeridos; su contrato cubre tanto cambios aditivos como incompatibles.

Finalmente, `scripts/generate_runtime_inventory.py` deriva
`docs/46_RUNTIME_INVENTORY.md` desde `curated_targets.json`, los PDB locales y
el manifest v4. El estado actual contiene 387 entradas/IDs PDB únicos y los
387 tienen al menos un PDB local de nombre exacto; los 418 archivos encontrados
incluyen variantes y duplicados. El inventario enumera sólo los dos modelos que
declara el manifest y reproduce sus métricas/notas sin reinterpretarlas. El
check también corre en CI. `docs/44` conserva por diseño hashes de su baseline
histórico, no los suplanta como inventario actual.

## Q-04 — Seguridad y privacidad desktop

- Test de bind exclusivo a loopback.
- Test “cero red” para el pipeline base con integraciones deshabilitadas.
- Consentimiento explícito para RCSB, LLM remoto, comunidad y blockchain.
- Verificación CSP desde configuración de producción.
- Sanitización de uploads PDB/SDF/PDBQT y límites de tamaño/tiempo.
- Revisión de subprocess: argumentos como lista, paths controlados y timeout.

**Hallazgo/resolución inicial (2026-08-15):** la exportación de certificado
enviaba el SMILES a PubChem automáticamente y, si un target no tenía
descripción, consultaba RCSB, UniProt y Google Translate sin consentimiento.
Se retiraron ambos caminos del renderer/router: el PDF usa nombre, métricas,
poses y headers locales. Hay un contrato que bloquea toda llamada a `urlopen`
durante la resolución de nombres del certificado y otro que impide al
dispatcher base abrir conexiones que no sean loopback. RCSB on-demand para
targets, LLM, Solana y comunidad siguen siendo integraciones explícitas
separadas; falta el inventario de consentimientos UI.

## Q-05 — Calidad de artefactos de release

- Construir instalador desde entorno limpio.
- Instalar, arrancar, evaluar, reiniciar y desinstalar en una VM.
- Verificar recursos empacados, modelo, Vina, xTB, llama-server opcional y DB.
- Probar actualización sobre una DB de la versión anterior.
- Producir SBOM, hashes y release manifest.

## Q-06 — Observabilidad local

- Correlation ID por evaluación.
- Eventos estructurados por stage y duración.
- Diagnóstico visible: binario ausente, modelo inválido, DB bloqueada, timeout,
  fuera de dominio y componente opcional no disponible.
- Export de un bundle de soporte sin secretos ni moléculas si el usuario no da
  consentimiento.

**Gate Calidad:** CI representa el producto distribuido; instalación limpia y
upgrade pasan; API/docs no divergen; seguridad desktop tiene pruebas.

---

# Fase 3 — Eficiencia

**Meta:** reducir tiempo, memoria y trabajo redundante sin modificar la ciencia
por accidente.

## E-01 — Perfil end-to-end y presupuestos

Instrumentar por evaluación:

- curación/validación;
- conformer ETKDG;
- preparación PDBQT;
- Vina;
- extracción de features;
- XGBoost/GNN/pose-selector;
- persistencia/PDF;
- etapas opcionales.

Medir wall time, CPU, peak RAM, I/O, cache hit y tamaño de artefactos para tres
perfiles de hardware. No optimizar antes de conocer el porcentaje de cada etapa.

## E-02 — Planificador de recursos

- Sustituir el número fijo de workers por presupuesto de CPU/RAM y tipo de job.
- Mantener límite SQLite independiente del límite de cálculo.
- Evitar oversubscription entre ThreadPool, Vina, OpenMP, PyTorch y XGBoost.
- Priorizar evaluación interactiva sobre batch masivo.
- Aplicar backpressure y estimación de tiempo visible.

## E-03 — Caché científica con identidad completa

Una entrada sólo es reutilizable si coincide:

- SMILES canonical/protonación/tautómero;
- receptor preparado y hash;
- grid;
- versión/parámetros/seed del motor;
- feature schema y modelo.

Separar cache persistente reproducible de cache RAM efímera. Nunca reutilizar
poses por coincidir únicamente SMILES + PDB ID.

## E-04 — Docking y preparación

- Perfilar exhaustiveness 4/8/32 contra calidad, no sólo tiempo.
- Reutilizar receptor preparado y datos invariantes.
- Evitar conversiones PDB↔PDBQT↔SDF repetidas.
- Mantener semillas y provenance.
- Evaluar early stopping/cascada: barato primero, caro sólo para candidatos
  prometedores o inciertos.

## E-05 — Modelos y memoria

- Lazy-load de modelos opcionales.
- Un solo proceso/instancia por artefacto pesado.
- Cuantificar cold start y peak RAM.
- Cachear features inmutables con límite y política de invalidación.
- Mantener CPU como referencia; GPU debe acelerar, no cambiar el contrato.

## E-06 — SQLite y filesystem

- Medir writes, checkpoints WAL y crecimiento de DB.
- Política de cleanup para temporales/logs/poses.
- Índices basados en queries observadas.
- Batch de escrituras cortas sin mantener transacciones durante cómputo.
- Backup/restore verificable desde UI o CLI.

**Gate Eficiencia:** baseline y perfil posterior publicados; no regresión
científica; mejora medible en tiempo/RAM; estabilidad bajo batch y cancelación.

---

# Fase 4 — Ciencia: laboratorio de largo recorrido

**Entrada obligatoria:** Código, Calidad y Eficiencia cerrados. Esta fase puede
durar muchas iteraciones; no debe tener presión por convertir cada idea en
feature de producción.

## S-00 — Separar Production Track y Research Track

- Artefactos y configs distintos.
- Registry de experimentos con hipótesis, baseline, split y criterio GO/NO-GO.
- Holdouts sellados que no se consulten durante diseño.
- Promotion PR explícita para mover un modelo a producción.
- Reproducción por seed, hardware, datos y commit.

## S-01 — Explicar el shift Fase A/Fase B

Antes de otro modelo universal:

- comparar ambos holdouts por familia, scaffold, fecha, rango pKi, resolución,
  tamaño/flexibilidad y features ausentes;
- medir cobertura del dominio de aplicabilidad;
- separar ranking dentro de target de correlación global;
- evaluar calibración e intervalos, no sólo Spearman;
- determinar si conviene modelo universal, family-specific o mixture-of-experts.

## S-02 — Validar externamente Ruta C

- Mantener v0.6 como baseline oficial.
- Reportar métrica global, cobertura y métrica condicional a pose recuperable.
- Desglosar por fuente, familia, flexibilidad y dificultad.
- Ejecutar benchmark temporal/externo no usado para elegir features.
- Calibrar abstención y comparar contra Vina y alternativas públicas bajo el
  mismo protocolo.
- Investigar relatividad cross-pose sin asumir que una GNN es necesariamente
  superior.

## S-03 — Mejorar generación de poses

- Separar claramente “scoring de afinidad” de “pose selection”.
- Evaluar ensembles, clustering, rescoring geométrico y receptores múltiples.
- MolFlex continúa como hipótesis limitada: conservar resultados negativos de
  RMSD y costo.
- Probar induced fit de bajo costo sólo si mejora cobertura bajo protocolo.

## S-04 — Escalera hacia dinámica molecular accesible

No empezar con trayectorias largas. Construir una escalera:

1. minimización local robusta;
2. relax restringido de pocket/ligando;
3. normal modes o ensembles de receptor;
4. MD corta replicada para estabilidad de pose;
5. métricas de contactos, RMSD/RMSF y supervivencia de interacción;
6. adaptive sampling para gastar cómputo donde hay incertidumbre;
7. GPU opcional para campañas, manteniendo preparación/análisis local.

El objetivo inicial no es reemplazar días de GPU, sino identificar temprano qué
candidatos **no justifican** ese gasto y cuáles merecen simulación rigurosa.

## S-05 — FEP+ ready como contrato de salida

MolDesign debe preparar, no prometer equivalencia con FEP+:

- estados de protonación/tautomería y estereoquímica enumerados;
- series con transformación química coherente;
- atom mapping validado;
- receptor, waters/cofactors/metales y binding site trazables;
- pose seleccionada con confianza/abstención;
- chequeos de clashes, strain y red de H-bonds;
- carga, parámetros y excepciones explícitas;
- provenance completo y export reproducible;
- ranking de candidatos y razón de selección para el cálculo caro.

## S-06 — Validación prospectiva

La madurez científica final requiere salir de benchmarks retrospectivos:

- campaña ciega con químicos/colaboradores;
- predicciones congeladas antes de conocer resultados;
- comparación contra baselines simples;
- reporte de éxitos, fallos y costo por candidato útil;
- revisión de claims después, no antes, de la evidencia prospectiva.

**Gate Ciencia:** promoción sólo si supera baseline preregistrado en holdout y
validación externa, conserva reproducibilidad y aporta valor operativo medible.

---

## 3.1 Registro de ejecución

### 2026-08-15 — C-01: build desktop recuperado

Se alineó Vite en `5.4.21`, que es la versión requerida por Vitest 1.6, y se
eliminó la descarga implícita de Google Fonts. La configuración de Next ahora
genera una exportación estática sólo para `BUILD_TARGET=desktop`; excluye las
rutas API web y no lee el nonce del middleware durante la exportación. La
build web conserva SSR, middleware y rutas API.

**Evidencia verde:**

- `npm --prefix frontend run build`;
- `npm --prefix frontend run build:desktop` (13 rutas estáticas en `out/`);
- `npm --prefix frontend run test:run` (9 archivos, 83 pruebas);
- `npm --prefix frontend run tauri:build`;
- instalador Windows generado:
  `frontend/src-tauri/target/release/bundle/nsis/MolDesign AI_1.0.0_x64-setup.exe`
  (12,572,928 bytes, SHA-256
  `B71A75FA6135C6F5F24B8F97FD711176BD7E00404680F9C5E4AC918829A1818D`).

**Pendiente de cierre documental:** ejecutar `npm ci` en un runner limpio. El
`npm ci --dry-run` local quedó bloqueado resolviendo dependencias y se detuvo
sin modificar módulos. Los warnings de peer dependencies pertenecen a Ketcher
(`draft-js-custom-styles`) y no bloquean la build ni el instalador.

### 2026-08-15 — C-03: contrato SSE y llama-server estabilizado

El cliente ahora interpreta `event: warning` emitido por el backend y mantiene
compatibilidad con el marcador legado `__WARNING__:`. Las pruebas ahora usan
eventos SSE válidos, delimitados por una línea vacía, en lugar de fragmentos
que no representan el protocolo real. El subgrupo `AIContext` pasa 9/9 y el
suite frontend completo pasa 83/83.

El wrapper llama-server mantiene probes sync/async separados; sus pruebas
mockean el probe síncrono de `load()` y el context manager de `httpx.stream()`
correcto, por lo que ya no abren sockets reales. Cubre UTF-8 fragmentado,
temperatura, ausencia de binario y lifecycle del proceso.

**Evidencia verde:** `AIContext` (9 pruebas) y `test_llama_server.py` (5
pruebas).

### 2026-08-15 — C-02: selectividad consolidada como etapa canónica opcional

`selectivity` queda definida en el registro como una etapa canónica, opcional
y post-hoc. `resolve_stage_order()` es ahora la única decisión sobre su
activación: sólo `pro_selectivity=true` la agrega, aunque un cliente antiguo la
incluya en `enabled_stages`. El runner ya no altera el plan resuelto. El
frontend declara explícitamente que la etapa es válida sin orb porque su estado
se presenta en el Safety Panel.

**Evidencia verde:** `backend/tests/test_pipeline_registry.py` (31 pruebas) y
`frontend/lib/__tests__/pipelineStream.test.ts` (15 pruebas).

### 2026-08-15 — C-04: lifecycle SQLite aislado de la DB desktop

Se añadió `reset_engine()` como lifecycle oficial: dispone el engine y borra
la factory singleton. `close_engine()` ahora devuelve el módulo a ese estado.
Las fixtures de ingestión y dispatcher usan este lifecycle en lugar de asignar
privados. En modo test, `core.database` rechaza explícitamente
`~/MolDesign/data/moldesign_local.db`.

También se eliminó una contaminación por orden de suite en `test_api`: la
fixture ya no restaura todo `sys.modules` (lo que reinicializaba extensiones
PyO3) y devuelve las variables de entorno a su valor previo. La memoria IA se
mockea mediante import explícito, sin depender de otro test.

**Evidencia verde:** 30 pruebas SQLite/API/ingestión/dispatcher pasan tanto en
orden normal como inverso con bases bajo `tmp/pytest-*`.

### 2026-08-15 — C-05: backend desktop sin regresiones bloqueantes

El certifier Solana ahora devuelve `None` cuando `solders` no está instalado,
en vez de propagar un `ModuleNotFoundError`. Los tests de extracción de memo no
dependen de tipos de la SDK; la única prueba que valida la configuración RPC se
omite explícitamente cuando la integración opcional no existe.

**Gate backend verde:** `pytest backend/tests -q` → **285 passed, 1 skipped**.
El skip es la aserción específica de `solders`; no afecta al runtime desktop.

### 2026-08-15 — C-06: sidecar de rescoring con contrato v4 coherente

El extractor 3D declara ahora dos contratos distintos y verificables: 155
features geométricas que alimentan el vector del modelo y 164 campos que
expone el extractor, al incluir los nueve conteos ProLIF de trazabilidad. Las
rutas degradadas devuelven siempre esas mismas 164 claves. Se eliminó la
emisión de 1,024 fingerprints Morgan: no formaban parte del vector Model A de
167 campos y ampliaban innecesariamente `features_used` y la caché.

La caché de features incorpora un digest del bloque PDBQT de la pose elegida;
ya no reutiliza coordenadas 3D de una ejecución anterior sólo porque coincidan
SMILES y receptor. La tabla de familias normaliza IDs PDB al consultar y los
labels legacy `phosphodiesterase` a `soluble_enzyme`, que es parte de la
taxonomía pública. Las pruebas sintéticas, de filtros, API y GNN se actualizaron
al contrato v4 y a la semántica de ausencia explícita (`NaN`, nunca 0.5).

**Gate rescoring verde:** `pytest rescoring/tests -q` → **306 passed, 6
skipped**. Los seis skips cubren exclusivamente pruebas de fallback sin RDKit;
este runtime sí incluye RDKit, por lo que son rutas no aplicables, no fallos
ocultos. Quedan como warnings no bloqueantes las deprecaciones de
Torch/MDAnalysis/SHAP y el cache de pytest sin permisos de escritura.

### 2026-08-15 — C-07: manifiesto v4 determinista y con verificación de hash

Se reemplazó el generador v3 que sólo registraba el modelo universal por un
registro declarativo v4 que exige tanto `model_a_universal` como
`pose_selector_v06`. El nuevo documento no contiene timestamp de generación:
dos ejecuciones con las mismas entradas producen exactamente los mismos bytes.
Incluye schema JSON versionado, hashes de modelos y metadata, la procedencia de
datasets/splits y el `--check` sin escritura. Este último rechaza divergencia
de hash, downgrade de versión y cualquier regeneración que borraría un modelo
ya registrado.

El backend de fuente verifica los hashes antes de exponer el manifiesto y
`/health` reporta versión, modelos y errores de integridad. El build Tauri
ejecuta obligatoriamente `check:rescoring-manifest` antes del export estático y
del empaquetado.

**Evidencia verde:** `rescoring/tests` → **312 passed, 6 skipped**;
`backend/tests/test_api.py` → **4 passed**; `npm run tauri:build` produjo el
instalador NSIS incluyendo el nuevo gate.

**Riesgo que permanece deliberadamente abierto:**
`frontend/src-tauri/resources/rescoring` es una copia antigua, independiente
del sidecar fuente. Sus artefactos no contienen el manifiesto v4 ni el selector
actual. No se sincronizó automáticamente porque sustituirlos cambiaría los
modelos científicos del instalador que hoy funciona. El build valida el
manifiesto fuente, pero un release realmente reproducible requiere una tarea
explícita de sincronización/versionado de recursos embebidos y una decisión
sobre qué artefactos son producción. Esto bloquea declarar cerrado el gate de
release completo.

**Decisión vigente:** `rescoring/artifacts` v4 permanece como referencia
científica canónica para desarrollo y validación. La copia embebida se conserva
sin cambios como artefacto legacy del instalador vigente; no se la promociona ni
se le atribuyen las métricas del manifest v4 hasta contar con una sincronización
atómica, pruebas golden source-vs-installer y versionado visible en cada
evaluación.

### 2026-08-15 — C-08: runtime principal consolidado a desktop

El núcleo ejecutable ya no conserva una alternativa cloud para caché, eventos,
archivos, cola ni ruta de receptor:

- `/evaluation/stream/{task_id}` usa `LocalRuntimeStore`, un bus SSE por
  proceso con replay/suscripción atómicos. Retiene como máximo 1,000 eventos
  por job, 256 eventos pendientes por cliente y 10,000 claves efímeras globales;
  un cliente lento no puede hacer crecer la memoria sin límite.
- La abstracción Redis muerta se retiró por completo. El estado no persistente
  tiene TTL y LRU locales; SQLite y `utils.local_storage` siguen siendo las
  fuentes de verdad para resultados y archivos científicos.
- `queue_handler` dejó de usar aliases `upload/download/object`: lee, escribe y
  consulta directamente `read_text`, `write_text` y `exists` sobre disco local.
  Los prefijos lógicos de rutas no cambiaron, por lo que los archivos ya
  guardados conservan compatibilidad.
- Se retiraron settings, bootstrap y excepciones MinIO/S3. Una ausencia de un
  archivo se reporta ahora como `LocalFileNotFound`.
- `APP_MODE=CLOUD` heredado se normaliza a `DESKTOP`; ya no puede redirigir el
  pipeline a `/data`, a un intérprete de contenedor, límites SaaS ni CORS web.
  Los sidecars de rescoring y ESMFold-Pro se resuelven en localhost.
- Schema SQLite v3 añade `evaluation_results.task_id` y rellena los valores de
  la columna heredada al arrancar. La columna física anterior no se borra y la
  API expone `celery_task_id` como alias transitorio: esto permite rollback y
  clientes viejos sin que el runtime nuevo dependa de Celery.

**Evidencia verde:** `288 passed, 1 skipped` en `backend/tests`, incluyendo
stream SSE, submit/status/cancel/reinicio, almacenamiento local, migración v3 y
benchmark de concurrencia SQLite. El único skip es una integración opcional.
Además, `frontend` aprobó `62` pruebas Vitest tras incorporar el campo
`task_id` y conservar el alias de transición.

**Límite deliberado:** los proveedores de IA configurables por usuario, OAuth y
los endpoints opt-in de comunidad son integraciones externas de producto; no
participan en el pipeline científico desktop y no se desactivaron sin una
decisión de producto. `backend/Dockerfile`, `environment.yml` y
`requirements.txt` son artefactos históricos no usados por CI ni por el
instalador desktop; se mantienen hasta decidir su archivo o eliminación en una
limpieza documental separada.

### 2026-08-15 — C-09 (primer corte): ensamblado PDB fuera del router

La lógica pura que ensambla el receptor PDB y la primera pose SDF para el visor
3D se movió de `api/routers/evaluation.py` a
`services/docking/pdb_assembly.py`. El endpoint, formato de respuesta y
coordenadas no cambian. Dos contratos nuevos verifican que conserva el receptor,
asigna `LIG`/cadena `L`, desplaza seriales sin colisión y rechaza una pose no
legible.

El segundo corte eliminó cinco implementaciones duplicadas de autorización de
resultados: `evaluation_access.require_owned_molecule()` conserva la excepción
del espacio demo y los códigos/mensajes HTTP de cada endpoint. También extrajo
`GET /evaluation/files/protein/{molecule_id}` a `evaluation_files.py`, incluido
como subrouter bajo el mismo prefijo. La URL, el cache local y el fallback RCSB
se mantienen sin cambios.

El tercer corte movió también `GET /evaluation/files/poses/{molecule_id}` y
`GET /evaluation/files/complex/{molecule_id}` al mismo subrouter. Se preservan
las URLs, autorización compartida, errores HTTP, MIME, contenido y cabecera
`Content-Disposition`; el ensamblado sigue en el servicio puro ya extraído.
Tres contratos cubren la entrega SDF, la entrega PDB fusionada y que las tres
rutas permanezcan exactamente una vez bajo el prefijo `/evaluation`.

El cuarto corte extrajo a `services/ai/report_context.py` la construcción
determinista de `AIReportRequest`, antes duplicada entre el transporte HTTP y
SSE. Permisos, cache, proveedor, streaming, prompts y persistencia continúan
en sus rutas originales; ambas ahora reciben el mismo contexto científico. Un
contrato verifica afinidad, propiedades, score, hotspots y delta nulo.

El quinto corte movió los dos transportes de reporte a
`api/routers/evaluation_reports.py`, incluido bajo el mismo prefijo
`/evaluation`. Se preservan `GET /evaluation/ai-report/{id}/stream`,
`POST /evaluation/ai-report/{id}`, la limitación dinámica, los payloads cache
y SSE y los códigos de error. Dos contratos comprueban esos payloads cache y
que ambas rutas se registren una sola vez.

El sexto corte movió el docking peptídico a
`services/docking/peptide_docking.py`. El runner científico importa ya ese
servicio, mientras `queue_handler` conserva un alias para compatibilidad. El
contrato cubre ambos caminos y el fallback explícito a Vina cuando los
proveedores peptídicos no están disponibles; no se modificaron parámetros,
coordenadas, warnings ni el comportamiento del dispatcher.

El séptimo corte separó estado, presupuesto y compresión determinista de
MolChat en `services/ai/conversation_state.py`. `chat_service` reexporta
`Conversation`, por lo que sus consumidores no cambian; routing, tools,
providers y guards de no-fabricación permanecen donde estaban. El contrato
comprueba la identidad del símbolo, historial reciente, resumen y estimación
de tokens.

El octavo corte movió serialización, cache terminal y recuperación SQLite del
estado de jobs a `services/docking/desktop_job_status.py`. El módulo recibe el
registro y lock compartidos por inyección: no crea una segunda cola ni otra
fuente de verdad. `queue_handler` conserva sus símbolos públicos y el alias
interno histórico, mientras los contratos cubren timestamps inválidos, cache
terminal y la recuperación tras reinicio ya existente.

El noveno corte cerró C-10: el registro de subprocesses auxiliares dejó de ser
global, el cliente requiere `task_id` y un resultado que llega después de
cancelar no puede resucitar el job como `SUCCESS`. El comportamiento comprobado
conserva archivos/resultados para soporte y persiste `FAILURE` para la
recuperación SQLite; no altera parámetros de docking ni artefactos de
rescoring.

El décimo corte eliminó tres implementaciones del veredicto de selectividad.
`services/docking/selectivity_verdict.py` es ahora la fuente pura que usa la
API Pro y el subprocess de persistencia; el helper sin callers del runner se
retiró. Los límites estrictos `>10`, `>3`, `>1.5` y `>1` y cada texto
persistido se congelaron mediante seis contratos, por lo que este refactor no
reclasifica resultados ni cambia el flujo científico.

El undécimo corte desacopló el contexto fisiológico textual de certificados en
`services/blockchain/certificate_context.py`. El renderer PDF sólo lo consume;
la prioridad GPCR → kinase → proteasa → canal, los textos, los keywords y el
fallback se mantienen intactos y quedan cubiertos por contratos. No se tocó
ninguna métrica, estructura, heurística de contactos ni resultado científico.

El duodécimo corte extrajo los renderers de estructura 2D, perfil de energía,
SHAP, atención GNN y diagrama 2D de contactos a
`services/blockchain/certificate_figures.py`. El PDF conserva sus imports
públicos y sólo compone las secciones. Se validaron salida válida y fallbacks;
los contactos se siguen calculando en el módulo existente, sin reclasificación
ni cambio de umbrales.

El decimotercer corte retiró dos salidas cloud implícitas al exportar un
certificado: PubChem ya no recibe el SMILES y la ausencia de descripción de un
target ya no dispara RCSB, UniProt ni Google Translate. El certificado sigue
siendo local y el contrato comprueba que no use red; no se modificaron docking,
rescoring ni datos científicos calculados.

El decimocuarto corte completó Q-03 v1: OpenAPI actual y mapa legible se
generan, se comparan para detectar incompatibilidades HTTP básicas y requieren
reconocimiento explícito antes de sobrescribir un cambio breaking. Un segundo
check valida todos los enlaces locales y un tercer generador deriva el
inventario actual de 387 targets/PDB IDs y los dos modelos v4 declarados. No
reclasifica resultados ni convierte artefactos experimentales en producción.

**Evidencia verde posterior:** `327 passed, 1 skipped` en `backend/tests` con
el runtime Python embebido; los contratos específicos de estado y dispatcher
suman `10 passed`. Permanecen tres warnings no bloqueantes ya conocidos:
`importlib-resources` de `admet_ai`, extensión `.xgb` de XGBoost y una fixture
class-scoped de pytest. C-10 queda cerrado como cancelación cooperativa por
tarea; los trabajos nativos no se interrumpen a mitad de una llamada.

---

### 2026-08-15 — Q-01: matriz de release declarada y smoke recuperado

`.github/workflows/ci.yml` dejó de reunir todo bajo un único job Python. La
matriz Windows ahora declara gates separados para contratos backend, contratos
de rescoring y hashes del manifest, tests/build web y desktop del frontend,
`cargo fmt` + `clippy -D warnings` + `cargo check` de Tauri, y el smoke
SQLite/filesystem real. Todos usan Python 3.11, que coincide con el runtime
embebido distribuido, y el frontend usa `npm ci` sobre su lockfile.

Durante esta revisión el smoke aislado reveló que aún escribía el parámetro
retirado `celery_task_id`; se alineó al contrato `task_id` sin modificar el
dispatcher ni el pipeline. La comprobación local vuelve a cubrir
`submit → polling → SQLite → poses.sdf` y pasa. También pasan localmente
`cargo fmt --check`, `cargo clippy --all-targets -- -D warnings` y el check de
manifest v4. La ejecución de esa matriz en un runner Windows limpio sigue
pendiente: no se declara CI remota verde sin esa evidencia.

## 4. Tablero maestro

| ID | Prioridad | Trabajo | Depende de | Estado vigente |
|---|---:|---|---|---|
| A-00 | P0 | Baseline recuperable | — | **Completado** — ver docs/44. |
| C-01 | P0 | Build frontend | A-00 | **Completado funcionalmente** — build web, export desktop, tests e instalador verificados; falta `npm ci` en runner limpio. |
| C-02 | P0 | Registro selectivity | A-00 | **Completado** — registro/runner/SSE frontend con contrato explícito. |
| C-03 | P0 | SSE/MolChat/llama | A-00 | **Completado** — contratos SSE y llama-server sin red real en tests. |
| C-04 | P0 | Aislamiento SQLite tests | A-00 | **Completado** — lifecycle, guard y prueba de orden de suite. |
| C-05 | P0 | Suite backend | C-02…C-04 | **Completado** — 327 passed, 1 skip de integración opcional. |
| C-06 | P0 | Suite rescoring | A-00 | **Completado** — 306 passed, 6 skips de fallback no aplicable. |
| C-07 | P0 | Manifest v4 | A-00 | **Parcial** — generador, hashes, health fuente y gate Tauri verdes; falta sincronización segura del snapshot embebido. |
| C-08 | P1 | Purga cloud final | C-03, C-05 | **Completado (runtime principal)** — estado, storage, dispatcher, schema, certificados y rutas son desktop; integraciones externas opcionales quedan separadas. |
| C-09 | P2 | Modularización | Gate Código casi verde | **En curso** — PDB, autorización, archivos, reportes, docking peptídico, estado MolChat, dispatcher, selectividad, contexto y renderers de certificados están aislados con contrato; siguen otros servicios grandes. |
| C-10 | P0 | Cancelación task-scoped | C-09 | **Completado (cooperativa)** — subprocesos auxiliares aislados por tarea, FAILURE durable y contratos de carrera/reinicio; Vina nativo no se preempta a mitad de llamada. |
| Q-01 | P1 | Matriz CI de release | Gate Código | **En curso** — matriz Windows declarada y comandos locales verificados; falta la primera ejecución limpia/remota. |
| Q-02 | P1 | Pirámide de pruebas | Gate Código | Pendiente |
| Q-03 | P1 | OpenAPI y documentación como código | Gate Código | **Completado (v1)** — snapshot, mapa, diff breaking básico, enlaces e inventario runtime derivados/checkeados. |
| Q-04 | P1 | Seguridad y privacidad desktop | Gate Código | **En curso** — certificados y dispatcher base sin red externa implícita; matriz de consentimiento auditada, faltan decisiones/UI uniformes para Solana y comunidad. |
| Q-05…Q-06 | P1 | Calidad de release | Gate Código | Pendiente |
| E-01…E-06 | P1 | Perfil y eficiencia | Gate Calidad | Pendiente |
| S-00…S-06 | Investigación | Ciencia de largo recorrido | Gate Eficiencia | Reservada |

## 5. Primera secuencia de ejecución

La primera campaña debe ser corta y aburridamente concreta:

1. A-00: capturar baseline recuperable.
2. C-01: conseguir `next build` verde.
3. C-02: resolver `selectivity` como contrato único.
4. C-04: aislar SQLite para obtener resultados de tests confiables.
5. C-03: arreglar stream frontend y llama-server.
6. C-05: cerrar el resto de backend.
7. C-06: cerrar rescoring por bloques, sin mezclar modelos nuevos.
8. C-07: cerrar manifest v4.
9. Ejecutar matriz completa y fijar el **Gate Código v1**.
10. Sólo entonces iniciar C-08 y C-09.
11. C-10 cerrado: conservar sus contratos antes de declarar el lifecycle
    desktop apto para release.

## 6. Métrica de progreso

No medir avance por líneas cambiadas ni por número de tickets cerrados. Usar:

- builds verdes / builds requeridos;
- tests verdes / tests totales, separados por dominio;
- rutas API cubiertas por contrato;
- artefactos verificados / artefactos distribuidos;
- dependencias cloud alcanzables desde runtime;
- tiempo/RAM por evaluación golden;
- experimentos científicos reproducidos / ejecutados;
- claims con evidencia vigente / claims publicados.

El plan avanza cuando disminuye la incertidumbre operativa y científica, no
cuando aumenta el volumen del repositorio.
