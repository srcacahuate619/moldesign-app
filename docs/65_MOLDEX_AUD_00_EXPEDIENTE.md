# MOLDEX-AUD-00 — Expediente de auditoría de la pestaña Moldex

**Fecha:** 2026-08-30
**Plan de referencia:** [61_PLAN_CIERRE_APP_ORQUESTACION_CLAUDE.md](61_PLAN_CIERRE_APP_ORQUESTACION_CLAUDE.md) §7
**Paso del método:** 1 (AUD) y primeros paquetes de escritura.
**Prioridad del mandato:** validez científica → calidad → eficiencia.

La auditoría de §1-§2 se hizo en lectura pura. Los paquetes de escritura
posteriores están anotados bajo cada hallazgo con su evidencia; la tabla de §2
lleva el estado real. **Ningún gate se declara verde aquí**: el Gate de Moldex
exige además las comprobaciones de aceptación del §7 del plan 61.

Orden de ejecución seguido (§6): SCI-002 → INT-007 → SCI-001 → SCI-003+004 →
BE-005+INT-006+BE-015 → UX-008+UX-012 → INT-013+INT-009+UX-011, con
TRANS-ANON-002 intercalado a petición del propietario.

**Todos los hallazgos del expediente están implementados.** Eso no hace verde la
pestaña: faltan las comprobaciones de aceptación del §7 del plan 61 —corrida
real, reinicio, dos cuentas— y quedan cuatro decisiones del propietario
pendientes (§7 de este documento).
Durante ese trabajo aparecieron tres hallazgos que la lectura no había visto
(SCI-014, UX-012, INT-013); dos de ellos los encontró el compilador en cuanto el
contrato dejó de ser `any`.

Precedentes que condicionan esta pestaña: el Gate de Evaluación
([63](63_GATE_RUNTIME_EVALUACION.md)) y el de Batch
([64](64_GATE_RUNTIME_BATCH.md)) están aprobados. Moldex hereda de ellos dos
hechos: `evaluation_results` es una **proyección mutable** de la última
evaluación de una molécula, y la identidad durable de una corrida vive en
`evaluation_runs.task_id` (EVAL-P0-02, expediente [62](62_EVAL_AUD_00_EXPEDIENTE.md)).
Casi todos los P0 de abajo salen de que Moldex todavía lee la proyección mutable
y no la corrida inmutable.

---

## 1. Mapa real del flujo (lectura)

```
cuenta ─▶ GET /moldex ──▶ repo.get_moldex_molecules(user_id, target_pdb_id, limit, offset)
             │              filtra: MoleculeORM.user_id == user
             │                      status == EVALUATED, is_saved == True
             │              lee:    EvaluationResultORM  ← proyección MUTABLE
             ▼
   catálogo (id, name, smiles, target, metrics, warnings, hotspots_hit, blockchain)
             │
             ├─▶ Virtuoso (lista virtualizada) ─▶ MoldexCard ─▶ insignia CERTIFIED
             │
             ├─▶ panel de detalle ─▶ MoleculeViewer3D
             │        ├─ GET /evaluation/files/poses/{molecule_id}     (autorizado)
             │        ├─ GET /evaluation/files/protein/{molecule_id}   (autorizado, EVAL-BE-003)
             │        ├─ <a> GET /evaluation/files/complex/{id}        (SIN token)
             │        └─ <a> GET /blockchain/certificate/{id}          (SIN token)
             │
             ├─▶ MolecularComparison (2 moléculas, sin control de compatibilidad)
             │
             └─▶ CertificationModal ─▶ POST /blockchain/certify           (institucional)
                                    ─▶ GET  /blockchain/certify/{id}/prepare + POST /certify/link (wallet)
                                          │
                                          ▼
                            memo Solana devnet:
                            MolDesign-v1|CC0|<smiles_hash>|<total_score>|<pdb_id>|<iso8601>|<wallet?>
                                          │
                                          ▼
                            evaluation_results.blockchain_tx_id  ← la MISMA fila mutable
```

Hechos del mapa que condicionan todo lo demás:

- **El sello se ancla a la proyección mutable, no a la corrida.** `blockchain_tx_id`
  es una columna de `evaluation_results` (`core/models.py:408`), la fila que
  `upsert_evaluation_result` (`db/repository.py:762`) reescribe en cada
  reevaluación de la misma molécula.
- **El memo sella cuatro campos y ninguno es una condición de cálculo.**
  `certifier.py:259-270`: hash del SMILES, `total_score`, PDB ID y timestamp. No
  viaja `task_id`, `receptor_sha256`, versión de Vina, semilla ni caja.
- **El catálogo no transporta procedencia.** `api/moldex.py:55-84` emite métricas
  desnudas; ni `task_id` ni el protocolo de docking llegan al cliente.
- **La red es devnet**, fijada por defecto en `core/config.py:248` y escrita a
  mano en los dos enlaces del explorador.
- **Sí hay virtualización real** (`react-virtuoso`) y memoización del visor 3D.
  El eje EFF no es donde está el problema de esta pestaña.

## 2. Hallazgos

Prioridad según §4 del plan. El estado de cada uno está en la última columna.

| ID | P | Eje | Dónde | Estado |
|---|---|---|---|---|
| MOLDEX-SCI-001 | P0 | Ciencia | `core/models.py:408`, `db/repository.py:762`, `api/moldex.py:80-83` | **implementado** 2026-08-30 |
| MOLDEX-SCI-002 | P0 | Ciencia | `api/routers/blockchain.py:144,227` | **implementado** 2026-08-30 |
| MOLDEX-SCI-003 | P0 | Ciencia | `components/MolecularComparison.tsx:72,96,116-119,126` | **implementado** 2026-08-30 |
| MOLDEX-SCI-004 | P0 | Ciencia | `components/MolecularComparison.tsx` (comparación completa) | **implementado** 2026-08-30 |
| MOLDEX-BE-005 | P1 | Backend | `api/routers/blockchain.py:330` | **implementado** 2026-08-30 |
| MOLDEX-INT-006 | P1 | Intersección | `app/moldex/page.tsx:799,811` vs `lib/api.ts:100` | **implementado** 2026-08-30 |
| MOLDEX-INT-007 | P1 | Intersección | `api/moldex.py:55-84` | **implementado** 2026-08-30 |
| MOLDEX-UX-008 | P1 | UX | `components/MoldexCard.tsx:138-141`, `app/moldex/page.tsx:757-770` | **implementado** 2026-08-30 |
| MOLDEX-INT-009 | P2 | Intersección | `components/MolecularComparison.tsx:9-10`, `app/moldex/page.tsx:108` | **implementado** 2026-08-30 |
| MOLDEX-INT-010 | P2 | Intersección | `components/MolecularComparison.tsx:18-27` | **implementado** 2026-08-30 |
| MOLDEX-UX-011 | P2 | UX | `app/moldex/page.tsx:221,282` | **implementado** 2026-08-30 |
| MOLDEX-UX-012 | P1 | UX | `app/moldex/page.tsx:629` | **implementado** 2026-08-30 |
| MOLDEX-INT-013 | P2 | Intersección | `api/moldex.py:17-29` | **implementado** 2026-08-30 |
| MOLDEX-SCI-014 | P0 | Ciencia | `components/MoldexCard.tsx:85-99,134-136` | **implementado** 2026-08-30 |
| MOLDEX-BE-015 | P0 | Backend | `db/repository.py:461` | **implementado** 2026-08-30 |
| TRANS-ANON-002 | P1 | Transversal | `api/routers/evaluation.py`, `core/models.py:184` | **implementado** 2026-08-30 |

---

### MOLDEX-SCI-001 · P0 · La ficha certificada puede mostrar cifras que el sello nunca atestiguó

**Evidencia.** `blockchain_tx_id` es una columna de `evaluation_results`
(`core/models.py:408`). `upsert_evaluation_result` (`db/repository.py:762-900`)
reescribe sobre esa misma fila `affinity_kcal`, `total_score`, `receptor_sha256`,
`vina_version`, `vina_random_seed` y `docking_protocol` cuando la molécula se
reevalúa — y **no toca `blockchain_tx_id` en ninguna rama**. `api/moldex.py:80-83`
deriva `certified: bool(res.blockchain_tx_id)` de esa fila ya sobrescrita.

**Impacto científico.** Secuencia: el investigador certifica la molécula M con
score 91 → la cadena sella `…|91.00|7E2Y|…` → reevalúa M con otra caja o semilla
→ la fila pasa a score 63 → Moldex muestra **63 con la insignia CERTIFIED** y un
enlace al explorador que dice 91. Nada en el producto detecta la divergencia. Es
la afirmación engañosa del §4: el sello parece respaldar un número que no selló.

**Causa raíz.** La certificación se ancla a la proyección mutable en lugar de a
la corrida inmutable que ya existe desde EVAL-P0-02 (`evaluation_runs`, con
`task_id` y `snapshot_json`).

**Corrección propuesta.** Anclar la certificación a `task_id`: registrar en el
sello y en la fila qué corrida se certificó, y que Moldex compare el snapshot
sellado con el vigente. Si difieren, la ficha no dice CERTIFIED a secas — dice
que el sello corresponde a una corrida anterior y ofrece abrirla.

**Prueba que fallará antes y pasará después.** Certificar una molécula,
reevaluarla con un score distinto y exigir que `GET /moldex` no la presente como
certificada sin declarar la discrepancia.

#### Implementado — 2026-08-30 (esquema v14)

**Corrección.** Dos columnas aditivas nullable en `evaluation_results`,
`certified_task_id` y `certified_total_score`, registran **qué corrida** se
certificó y **qué score** quedó atestiguado. Las escriben las dos rutas de
certificación a través de un único helper, `_valores_del_sello`. En
`POST /certify/link` el score sellado se toma del **memo verificado en la
cadena**, no de la fila local: el memo es lo que realmente quedó atestiguado, y
la fila pudo cambiar entre la firma y el enlace.

`api/moldex.py::_estado_del_sello` compara ese registro con la corrida vigente y
publica `matches_current_run` con tres valores que significan cosas distintas:

- `true` — el sello describe la corrida que la ficha muestra;
- `false` — la molécula se reevaluó después de certificarla;
- `null` — **indeterminado**: no hay sello, o es anterior a v14 y no consta qué
  cubrió.

**Los sellos heredados no se rellenan.** Sería trivial copiarles el `task_id`
vigente y dejarlos en verde, y sería exactamente el defecto que se está
corrigiendo: afirmar una correspondencia que nadie comprobó. Se declaran
indeterminados. Esto es lo que hace que D-02 siga siendo una decisión abierta y
no un problema resuelto en silencio.

En la interfaz, `leerSello` traduce el estado a la única afirmación sostenible.
La insignia dice `CERTIFICADO` sólo cuando el sello está vigente; si no, dice
`SELLO DESFASADO` o `SELLO SIN CORRIDA`, y el panel de detalle muestra ambas
cifras —la sellada y la vigente— para que el lector no tenga que adivinar cuál
respalda la cadena.

**Archivos del paquete:**

- `backend/core/models.py`, `backend/core/database.py` (v14 documentada)
- `backend/api/routers/blockchain.py`, `backend/api/moldex.py`
- `backend/tests/test_sello_anclado_a_su_corrida.py` (nuevo)
- `frontend/lib/moldex.ts`, `frontend/components/MoldexCard.tsx`,
  `frontend/app/moldex/page.tsx`, `frontend/lib/__tests__/moldexContract.test.ts`

**Evidencia reproducida:**

- regresión antes del arreglo: `9 failed`;
- después: `10 passed` (incluye la migración v13→v14 sobre SQLite real: las dos
  columnas aparecen, la fila anterior y su firma sobreviven intactas, y el sello
  heredado queda en `NULL`);
- frontend focal: `10 passed`;
- backend completo `994 passed`; frontend completo `558 passed` en 55 archivos;
- `tsc --noEmit`, `py_compile`, `git diff --check`: limpios; OpenAPI `--diff` sin
  incompatibilidades.

**Corrección al update optimista.** Tras certificar con éxito, el cliente
actualizaba la molécula en memoria poniendo sólo `certified` y `tx_signature`.
Con el contrato nuevo eso habría mostrado `SELLO SIN CORRIDA` justo después de
una certificación correcta; ahora registra también la correspondencia, que en
ese instante es cierta por construcción.

---

### MOLDEX-SCI-002 · P0 · El sello escribe un cero fabricado, y lo escribe de forma irreversible

**Evidencia.** Las dos rutas de certificación colapsan un score ausente a cero:

- `api/routers/blockchain.py:144` — `total_score=evaluation.total_score or 0.0`
  (ruta institucional, el valor entra en `BlockchainRecord` y de ahí al memo).
- `api/routers/blockchain.py:227` — `total_score = evaluation.total_score or 0.0`
  (ruta wallet, el valor entra en el memo que el usuario firma).

`total_score` es nullable: `upsert_evaluation_result` lo escribe con `safe_float`,
que devuelve `None` ante un valor ausente o no convertible (`db/repository.py:879`).

**Impacto científico.** Es exactamente el linaje de BATCH-SCI-001 (batch heredado)
y EVAL-SCI-012 (SAR): un cero que no es una medida débil sino una medida
inexistente. Aquí es peor por dos razones. Primera: se escribe **en una cadena
pública, y no se puede corregir**. Segunda: `0.00` no se lee como "faltante",
se lee como el peor resultado posible, y el memo lleva licencia CC0 y timestamp,
o sea que se presenta como registro de procedencia.

**Corrección propuesta.** La certificación de una corrida sin `total_score` se
rechaza con 400 y un mensaje que explique qué falta. Si se decidiera permitirla,
el memo debe sellar el faltante explícitamente, nunca `0.00`.

**Prueba.** Certificar una evaluación con `total_score = None` por ambas rutas y
exigir 400; ningún memo construido puede contener `|0.00|` procedente de un nulo.

#### Implementado — 2026-08-30

**Reproducción previa.** Con `total_score = None`, `prepare_certification`
devolvía sin error el memo que el usuario habría firmado:

```
MolDesign-v1|CC0|aaaa…aaaa|0.00|7E2Y|2026-08-30T20:36:38.851659|1111…1111
```

**Corrección.** Un único helper compartido, `_score_sellable`
(`api/routers/blockchain.py:66`), reemplaza el `or 0.0` de las dos rutas
(líneas 181 y 264). Distingue las dos cosas que el idiom confundía: un score
ausente bloquea la certificación con 400 y un mensaje que explica por qué; un
score de `0.0` **realmente medido** sigue siendo certificable, porque es un
valor válido del extremo inferior de la escala 0-100. El `except HTTPException:
raise` del endpoint POST (línea 228) deja pasar el 400 sin convertirlo en 500.

Detalle que conviene registrar: `BlockchainRecord.total_score` ya era
`float = Field(..., ge=0, le=100)`, es decir, **el esquema habría rechazado el
`None`**. El `or 0.0` lo convertía en un cero válido antes de que Pydantic
pudiera verlo. La validación existía; el laundering la derrotaba.

**Archivos del paquete:**

- `backend/api/routers/blockchain.py`
- `backend/tests/test_certificacion_no_sella_cero_fabricado.py` (nuevo)

**Evidencia reproducida:**

- regresión antes del arreglo: `3 failed, 3 passed` — los 3 que ya pasaban son
  los que fijan el cero real y el score normal, para que la corrección no
  pudiera sobrecorregir rechazándolos;
- después del arreglo: `6 passed`;
- suites focales de certificado, reporte y blockchain: `42 passed`;
- suite backend completa: `981 passed`, sin fallos;
- `py_compile` y `git diff --check`: limpios;
- OpenAPI: el helper no es una ruta ni un modelo, así que no altera el
  contrato; `--diff` no reporta incompatibilidades y no aparece ninguna ruta de
  blockchain en la deriva. El `--check` marca el contrato desactualizado por
  trabajo en vuelo **ajeno a este paquete**, y no se ejecutó `--write` para no
  barrer cambios de otros routers.

**Limitación conocida.** Esto impide sellos futuros con un cero fabricado. **No
repara los sellos ya emitidos**: ver decisión D-01.

---

### MOLDEX-SCI-003 · P0 · El comparador fabrica ceros y calcula deltas contra ellos

**Evidencia.** `components/MolecularComparison.tsx`:

- líneas 116-119: `log_p ?? 0`, `mw ?? 0`, `tpsa ?? 0`, `score ?? 0` para las
  cuatro filas de la tabla comparativa;
- línea 126: la columna DIFERENCIA calcula `(valB - valA).toFixed(2)` sobre esos
  ceros y la colorea en verde o rojo;
- líneas 72 y 96: `molA?.metrics?.affinity?.toFixed(2) || "0.00"` — una afinidad
  ausente se renderiza como `0.00`.

Los campos son genuinamente nulables: `db/repository.py:809-811` escribe `log_p`,
`tpsa` y `molecular_weight` como `None` cuando RDKit no pudo calcularlos.

**Impacto científico.** Una molécula sin logP calculable se compara como si su
logP fuera 0, y el delta contra la otra se pinta como si significara algo. Es el
defecto que EVAL-SCI-012 retiró de SAR el 2026-08-30 y que **sobrevivió intacto
en esta superficie**.

**Corrección propuesta.** Semántica nula: valor ausente se muestra como ausente,
y no hay delta si falta cualquiera de los dos lados. El cero real sigue siendo
válido y debe distinguirse del faltante. Es el mismo contrato ya implementado
para SAR, reutilizable.

**Prueba.** Comparar dos moléculas con `log_p: null` y exigir que no aparezca
`0.00` ni una diferencia calculada.

---

### MOLDEX-SCI-004 · P0 · El comparador no comprueba compatibilidad antes de restar

**Evidencia.** `MolecularComparison` recibe dos moléculas y construye la tabla de
diferencias sin verificar **nada**: ni que compartan target (las líneas 74 y 94
se limitan a imprimir cada `pdb_id`, que pueden ser distintos), ni receptor, ni
caja, ni motor, ni semilla, ni protocolo. El payload de `/moldex` ni siquiera
transporta esos campos, así que la comprobación es hoy imposible en el cliente.

**Impacto científico.** Se pueden restar afinidades obtenidas contra receptores
distintos, con cajas distintas o con protocolos distintos, y la interfaz pinta el
resultado en verde o rojo como si fuera una mejora. Un caso concreto ya conocido
en este proyecto: un docking rígido y uno flexible no son comparables — la
penalización torsional vale del orden de 1 kcal/mol, suficiente para invertir el
orden de dos candidatos.

Es el punto que el gate de la pestaña exige literalmente: *"Comparación rechaza
entradas incompatibles con una explicación científica"* (§7 del plan).

**Corrección propuesta.** Exigir compatibilidad declarada antes de comparar:
mismo target y mismo `receptor_sha256`, y mismo protocolo de docking. Si no
coinciden, no se muestra delta — se explica por qué no son comparables. Depende
de MOLDEX-INT-007, que es quien debe hacer llegar esos campos al cliente.

**Prueba.** Comparar dos moléculas con `receptor_sha256` distinto y exigir que la
columna de diferencia no se renderice y aparezca la explicación.

#### Implementado — 2026-08-30 (SCI-003 + SCI-004 + INT-010)

Los tres van juntos porque viven en el mismo archivo y el plan prohíbe abrir dos
paquetes de escritura sobre él a la vez.

**SCI-004 — compatibilidad.** `compararMoleculas` (`lib/moldex.ts`) decide si dos
fichas pueden restarse comprobando target, `receptor_sha256` y protocolo de
docking, y **acumula todos los motivos**, no sólo el primero. Cuando la
procedencia no consta —corridas anteriores al registro— el veredicto es *no
comparable*: no saber contra qué se midió es precisamente el motivo para no
restar, y suponer compatibilidad sería el mismo error que rellenar un sello
heredado. Si no son comparables, la tabla de diferencias **no se renderiza**; en
su lugar se explica por qué, y se aclara que las propiedades de cada molécula
siguen siendo válidas por separado: lo que no puede calcularse es la diferencia.

**SCI-003 — semántica nula.** `filaComparativa` conserva el faltante como
faltante: `—` en vez de `0.00`, y **sin delta** si falta cualquiera de los dos
lados. El cero realmente medido sigue siendo un valor y sí produce delta — es la
distinción que el `?? 0` borraba. La afinidad de cada panel muestra `sin dato`
en vez de `0.00`, y ahora lleva su unidad: `kcal/mol`.

**INT-010 — estado de error.** El `Promise.all(...).then(...)` sin `.catch(...)`
dejaba el visor vacío para siempre si la pose o el receptor no se podían
recuperar. Ahora hay tres estados explícitos y el fallo se dice: artefacto no
disponible o no autorizado. Se añadió también guarda de desmontaje (`activo`),
que antes no existía.

De paso, la cabecera de la tabla declara unidades (`PESO MOL. (Da)`,
`TPSA (Å²)`, `SCORE (0-100)`), las celdas de cabecera de fila son `th` con
`scope`, la tabla tiene `caption` y el botón de cerrar tiene `aria-label`.

**Archivos del paquete:**

- `frontend/lib/moldex.ts`
- `frontend/components/MolecularComparison.tsx`
- `frontend/lib/__tests__/moldexComparacion.test.ts` (nuevo)

**Evidencia reproducida:**

- regresión antes del arreglo: `11 failed` (`compararMoleculas is not a function`);
- después: `11 passed`;
- frontend completo: `569 passed` en 56 archivos; `tsc --noEmit` limpio.

**Nota de alcance.** `MOLDEX-INT-009` (contratos sin tipar) queda cerrado para
esta superficie: `MolecularComparison` ya no recibe `any`. Sigue abierto para la
normalización de `page.tsx:108`.

---

### MOLDEX-BE-005 · P1 · El certificado en PDF se sirve a cualquiera dentro del espacio demo

**Evidencia.** `api/routers/blockchain.py:330`:

```python
if mol.user_id != current_user_id and mol.user_id != demo_user.id:
    raise HTTPException(status_code=403, detail="No autorizado…")
```

con `current_user_id = current_user.id if current_user else demo_user.id`
(línea 328) y `get_current_user_optional`, que devuelve `None` sin token
(`api/dependencies.py:137-138`).

Dos consecuencias:

1. **La segunda cláusula abre el espacio demo a todo el mundo.** Cualquier
   molécula con `user_id == demo_user.id` entrega su certificado PDF completo a
   cualquier cuenta y también a un llamador **sin autenticar**. En escritorio las
   moléculas se crean con el usuario demo mientras no hay login — el comentario
   del propio código (líneas 320-324) lo dice.
2. **Responde 403, que confirma existencia.** BATCH-BE-002 eligió deliberadamente
   404 para no revelar que un recurso ajeno existe; aquí se revela.

El PDF no es un dato menor: `pdf_generator.py` incluye SMILES, poses, receptor y
metodología completa.

**Corrección propuesta.** Resolver la propiedad como en el resto de superficies ya
cerradas y responder 404 ante un recurso que no pertenece a la cuenta. El acceso
demo, si debe existir, tiene que ser explícito y no heredable por una cuenta real.

**Prueba.** Alice y Bob en la misma máquina: Bob recibe 404 sobre el certificado
de Alice; un llamador sin token recibe 404 sobre una molécula del espacio demo.

---

### MOLDEX-INT-006 · P1 · Los dos enlaces de descarga no llevan el token

**Evidencia.** `app/moldex/page.tsx:799` y `:811` son anclas crudas:

```tsx
<a href={`${apiUrl}/blockchain/certificate/${selectedId}`} download>DESCARGAR PDF</a>
<a href={`${apiUrl}/evaluation/files/complex/${selectedId}`} …>
```

El Bearer vive únicamente en el envoltorio de `fetch` (`lib/api.ts:100-101`, leído
de `localStorage`). Una navegación del navegador no lo adjunta.

**Impacto funcional.** Para una cuenta real, el backend ve `current_user = None`,
resuelve `current_user_id = demo_user.id`, y la molécula —propiedad de la
cuenta— falla la comparación de la línea 330: **403**. Los botones "DESCARGAR PDF"
y la descarga del complejo están rotos para todo usuario autenticado; sólo
funcionan sobre el espacio demo, que es justamente el agujero de MOLDEX-BE-005.

**Corrección propuesta.** Descargar por `fetch` autenticado y entregar el blob, o
emitir un enlace firmado de un solo uso. No relajar la autorización del endpoint
para que el ancla funcione.

**Prueba.** Con sesión iniciada y una molécula propia, la descarga del certificado
devuelve 200 y un PDF; sin sesión, 404.

---

### MOLDEX-INT-007 · P1 · El catálogo no transporta la identidad de la corrida

**Evidencia.** `api/moldex.py:55-84` construye cada ficha con `id`, `name`,
`smiles`, `smiles_hash`, `created_at`, `target`, ocho métricas, advertencias,
hotspots y el bloque blockchain. **No emite** `task_id`, `receptor_sha256`,
`vina_version`, `vina_random_seed`, `docking_protocol` ni `evaluated_at`.

**Impacto.** El gate de la pestaña exige que *"cada valor mostrado y exportado
conserve origen, unidad y corrida"*. Hoy una ficha de Moldex no puede decir de
qué corrida salió su número, y por eso MOLDEX-SCI-001 y MOLDEX-SCI-004 no son
siquiera detectables en el cliente. Efecto derivado: el orden "RECIENTES"
(`page.tsx:221`) lee `a.evaluated_at || a.created_at`; como `evaluated_at` no
existe en el payload ni se sintetiza en la normalización (`page.tsx:108-114`),
ordena por la fecha de creación de la molécula, no por la de su evaluación.

**Corrección propuesta.** Emitir la procedencia desde `evaluation_runs` y tiparla
en TypeScript, con una prueba de contrato que detecte campos omitidos o
renombrados — el mismo patrón con el que se cerró EVAL-INT-008.

#### Implementado — 2026-08-30

**Hallazgo revisado durante la implementación.** La auditoría proponía traer la
procedencia desde `evaluation_runs`. No hizo falta: `task_id`, `receptor_sha256`,
`vina_version`, `vina_random_seed`, `docking_protocol` y `evaluated_at` **ya son
columnas de `EvaluationResultORM`**, es decir, de la fila que el catálogo ya
carga. La corrección no añade join, consulta, migración ni coste. Lo que faltaba
era emitirlos.

Esto no cancela MOLDEX-SCI-001: `task_id` en la fila mutable dice cuál fue la
*última* corrida, no cuál se certificó. Anclar el sello sigue necesitando el
snapshot inmutable.

**Corrección.** `api/moldex.py` emite ahora un bloque `provenance` (`task_id`,
`receptor_sha256`, `engine_version`, `random_seed`, `docking_protocol`) y el
campo `evaluated_at`. `receptor_path` se omite deliberadamente: EVAL-INT-008 ya
fijó que la ruta local del usuario no se publica, y para decidir compatibilidad
basta el hash.

Del lado del consumidor se creó `frontend/lib/moldex.ts` con el contrato tipado
(`MoldexMolecule`, `MoldexProvenance`, `MoldexCatalog`) y `getMoldex` dejó de
devolver `Promise<any>`.

**Efecto derivado, ahora corregido.** El orden «RECIENTES» leía `evaluated_at`,
un campo que el backend nunca enviaba, así que ordenaba por la fecha de creación
de la molécula. Al emitirse el campo, el orden pasa a ser el que el código ya
pedía. El comparador salió a `lib/moldex.ts` para poder probarlo; antes cacheaba
un `_ts` **mutando la propia molécula** con `as any`.

**Archivos del paquete:**

- `backend/api/moldex.py`
- `backend/tests/test_moldex_procedencia.py` (nuevo)
- `frontend/lib/moldex.ts` (nuevo)
- `frontend/lib/api.ts`
- `frontend/app/moldex/page.tsx`
- `frontend/lib/__tests__/moldexContract.test.ts` (nuevo)

**Evidencia reproducida:**

- regresión antes del arreglo: `3 failed, 1 passed` — `KeyError: 'provenance'` y
  `KeyError: 'evaluated_at'`. La que ya pasaba es la que vigila que no se filtre
  la ruta local, para que la adición no pudiera introducir la fuga;
- después: backend `4 passed`, frontend `6 passed`;
- backend completo: `985 passed`; frontend completo: `554 passed` en 55 archivos;
- `tsc --noEmit`: limpio; `py_compile` y `git diff --check`: limpios.

**Limitación de contrato.** `GET /moldex` sigue declarando `dict[str, Any]` sin
`response_model`, así que **no aparece en `openapi-current.json`** y la guarda
automática (`evaluationResultContract.test.ts`) no puede cubrirlo. Mientras siga
así, `lib/moldex.ts` y su prueba son la única definición del contrato. Declarar
el `response_model` es trabajo pendiente, no cubierto por este paquete.

---

### MOLDEX-UX-008 · P1 · La insignia CERTIFIED no dice qué certifica ni en qué red

**Evidencia.** El lenguaje del producto es **disciplinado donde se firma** y mudo
donde se muestra:

- `CertificationModal.tsx:255` — *"Este registro prueba integridad y precedencia
  de la revisión publicada. No demuestra que la pose sea válida ni que la
  conclusión científica sea correcta."* Correcto. Además muestra la red
  (`health.network`, líneas 232 y 322).
- `pdf_generator.py:1268` — *"El registro acredita integridad y fecha, no
  descubrimiento ni validez científica."* Correcto.
- `MoldexCard.tsx:138-141` — una insignia que dice `CERTIFIED`, sin más.
- `app/moldex/page.tsx:757-770` — encabezado **"Evidencia Digital"** y botón
  **"VERIFICAR EN SOLANA"** con `cluster=devnet` escrito a mano, sin declarar que
  devnet es una red de pruebas ni repetir el alcance del sello.

**Impacto.** La superficie que el investigador ve todo el tiempo —la ficha— es la
que omite la limitación que el modal y el PDF sí formulan. "Evidencia Digital"
sobre una red de desarrollo invita a leer el sello como validación.

**Corrección propuesta.** Llevar a la ficha y al panel el mismo lenguaje que ya
existe en el modal y el PDF, y declarar la red junto al enlace en vez de
codificarla en la URL.

---

### MOLDEX-INT-009 · P2 · Contratos sin tipar en la superficie de comparación

`MolecularComparison.tsx:9-10` declara `molA: any; molB: any`; `page.tsx:108`
normaliza con `(m: any)`. No existe ninguna prueba de contrato que detecte un
campo backend renombrado u omitido en esta pestaña.

---

### MOLDEX-INT-010 · P2 · El comparador no tiene estado de error

`MolecularComparison.tsx:18-27` encadena `Promise.all([...]).then(...)` sin
`.catch(...)`. Si la pose o la proteína no se pueden recuperar —artefacto
ausente, huérfano o no autorizado— el visor queda vacío de forma indefinida sin
decir por qué. El gate pide *"estados explícitos para artefacto ausente,
incompatible, todavía generándose o no autorizado"*.

---

### MOLDEX-UX-011 · P2 · Recuperación por recarga y orden por fecha equivocada

`page.tsx:282` ofrece `window.location.reload()` como única recuperación ante un
error de carga. El orden por fecha quedó corregido dentro de MOLDEX-INT-007; la
recuperación por recarga sigue abierta.

---

### MOLDEX-UX-012 · P1 · La afinidad se etiqueta `kcal`, no `kcal/mol`

**Evidencia.** `app/moldex/page.tsx:629` renderiza el número principal de la
ficha como `{…affinity?.toFixed(1)} kcal`. La afinidad de Vina está en
**kcal/mol**; el propio modelo lo documenta (`core/models.py`, `affinity_kcal`:
*"kcal/mol, negativo = mejor"*), y el panel de estadísticas de la misma página
sí rotula bien el resto (`Da`, `Å²`, `LogP`, líneas 743-747).

**Impacto.** Es la magnitud más visible de la pestaña y la única mal etiquetada.
Una energía por mol y una energía no son la misma cantidad; el gate exige que
cada valor mostrado conserve su unidad.

**Corrección propuesta.** Rotular `kcal/mol`. Cambio de una línea, pero es una
corrección científica, no cosmética: va en su propio paquete y no mezclado con
retoques visuales.

---

### MOLDEX-INT-013 · P2 · `/moldex` es invisible para la guarda de contrato

**Evidencia.** `api/moldex.py:17-29` declara `-> dict[str, Any]` sin
`response_model`. FastAPI no puede derivar esquema, así que la ruta no aparece en
`docs/api/openapi-current.json` y `evaluationResultContract.test.ts` —la prueba
que detecta campos renombrados u omitidos— no la cubre.

**Impacto.** El contrato del catálogo depende hoy de que alguien recuerde
actualizar `lib/moldex.ts` a mano. Es exactamente la clase de deriva que la
guarda existe para impedir.

**Corrección propuesta.** Declarar un `response_model` Pydantic para el catálogo
y regenerar el contrato. No se hizo dentro de MOLDEX-INT-007 porque regenerar
`openapi-current.json` arrastraría trabajo en vuelo de otros routers ajeno al
paquete.

---

### MOLDEX-SCI-014 · P0 · Una molécula sin score se etiquetaba `D-Tier`

**Cómo apareció.** No estaba en la auditoría de lectura. Salió al tipar el estado
de la página (`any[]` → `MoldexMolecule[]`) dentro de MOLDEX-SCI-001: TypeScript
señaló ocho comparaciones sobre un valor que puede ser `null`.

**Evidencia.** `MoldexCard.tsx:85` guardaba el rango con
`molecule.metrics?.score !== undefined`. Un `null` **atraviesa esa guarda**, y
las cinco comparaciones siguientes (`score >= 85`, `>= 70`, `>= 55`, `>= 40`)
son todas falsas contra `null`, así que la cascada caía al último ramo: `D-Tier`.
En la misma tarjeta, `score?.toFixed(1) || "0.0"` mostraba `0.0`.

**Impacto científico.** Una molécula cuyo score el pipeline **no produjo** se
presentaba con el peor rango de la escala y una cifra de `0.0`. No es una
degradación conservadora: es emitir un juicio de calidad a partir de un dato que
no existe, y es la misma familia de BATCH-SCI-001, EVAL-SCI-012 y MOLDEX-SCI-002.

**Corrección.** La guarda es ahora `score !== null`. Sin score no hay rango: la
tarjeta muestra `SIN SCORE` en gris y `—` en lugar de la cifra. El cero real
sigue siendo un score válido y conserva su color.

**Prueba.** Cubierto por el tipo (`MoldexMetrics.score: number | null`) y por
`tsc --noEmit`, que ahora falla si alguien vuelve a comparar el score sin
guardarlo. Queda pendiente una prueba de render de `MoldexCard`, que hoy no
tiene ninguna.

---

#### Implementado — 2026-08-30 (BE-005 + INT-006 + BE-015)

**BE-005.** La autorización vive ahora en `_require_certificate_owner`: exige
sesión, exige propiedad exacta y responde **404**, no 403 —un 403 revela que el
dossier ajeno existe, que ya es información (misma elección que BATCH-BE-002)—.

El motivo histórico de la laxitud estaba escrito en el propio código: *«en modo
DESKTOP las moléculas se crean con el usuario demo (sin login)»*. **Ya no es
cierto.** El escritorio inicia sesión solo como `Desktop User`
(`GET /auth/desktop-login`, `auth.py:502`), una cuenta con identidad propia y
contraseña aleatoria. El espacio demo dejó de ser el invitado real, así que la
excepción que lo abría a todos perdió su razón de ser.

**BE-015.** El usuario `demo` se creaba con la contraseña `demo123` escrita en
el código y `is_active=True`. Como `/auth/login` acepta username o email,
**cualquiera que alcanzara la API entraba como demo**. Ahora recibe un secreto
aleatorio (`secrets.token_hex(32)`), la misma técnica que ya usaba
`/auth/desktop-login`: es una identidad de servicio, no una cuenta de persona, y
nadie necesita autenticarse con ella.

**INT-006.** Los dos `<a href>` crudos de Moldex pasan a `fetch` autenticado.
No hizo falta inventar nada: `downloadCertificate` ya existía y ya la usaban
Historial, el runner de evaluación y el visor PDF — **Moldex era la única
superficie que no la usaba**. Para el complejo se añadió `downloadComplexFile`
sobre el `getComplexFile` autenticado que ya existía. Los botones muestran
progreso, se deshabilitan durante la descarga y el fallo se comunica en la
misma superficie de error de la página, en vez de no pasar nada.

**Archivos del paquete:**

- `backend/api/routers/blockchain.py`, `backend/db/repository.py`
- `backend/tests/test_certificado_exige_dueno.py` (nuevo)
- `backend/tests/_fuente.py` (nuevo, compartido)
- `frontend/lib/api.ts`, `frontend/app/moldex/page.tsx`

**Evidencia reproducida:**

- regresión antes del arreglo: `7 failed`; después: `6 passed`;
- backend completo `1005 passed`; frontend completo `569 passed`;
- `tsc --noEmit`, `py_compile`, `git diff --check`: limpios.

**Limitación conocida.** Esto cierra la superficie de Moldex. El mismo patrón
—`current_user.id if current_user else demo_user.id`— sigue vivo en otras siete
posiciones: ver **D-05**.

---

### TRANS-ANON-002 · P1 · El cupo de evaluaciones anónimas medía máquinas

**Evidencia.** `_enforce_submission_gates` aplicaba un cupo de evaluaciones
gratuitas contado por dirección IP (`AnonymousLimitORM.ip_address` como clave
primaria, `mol_owner_ip` con TTL de 24 h). En escritorio todo es `127.0.0.1`:
el cupo no medía personas, medía máquinas. El ajuste ya estaba neutralizado con
`default=999` y la descripción «Sin límite en desktop», pero el contador seguía
escribiendo en la base y el 403 seguía existiendo al llegar al tope, con un
mensaje —«Regístrate para continuar diseñando»— que en una app local no aplica.
El endpoint `GET /evaluation/limit-status` y su cliente `getLimitStatus` no
tenían ningún consumidor.

**Decisión del propietario (2026-08-30).** Sin cuenta se **evalúa** sin límite;
la cuenta hace falta para **guardar** en Moldex y para **certificar**.

**Corrección.** Se retiraron el bloque de cupo, el endpoint, su cliente, los dos
helpers del repositorio, el ajuste de configuración y la clase
`AnonymousLimitORM`. **La tabla `anonymous_limits` de las bases existentes no se
toca**: una instalación nueva ya no la crea, y borrarla sería destructivo sin
aportar nada, porque ya nadie la lee.

Dos pruebas de EVAL-BE-005 afirmaban el cupo. No se borraron: la que exigía el
403 se **invirtió** —ahora exige que no se bloquee— y la otra conserva lo que
sigue importando, que el dueño de la tarea quede registrado antes de ejecutar.
El repositorio espía de ese archivo ahora lanza si alguien vuelve a consultar un
contador anónimo.

**Evidencia:** regresión `3 failed` → `4 passed`; backend completo `999 passed`.

**Aviso de contrato.** OpenAPI marca `ruta eliminada: /evaluation/limit-status`
como incompatibilidad. Es intencional y sin consumidores, pero no se regeneró el
contrato para no arrastrar trabajo en vuelo de otros routers: hace falta
`--write --allow-breaking` cuando eso se asiente.

---

#### Implementado — 2026-08-30 (UX-008 + UX-012 + INT-013 + INT-009 + UX-011)

**UX-012 — la unidad.** La afinidad se rotulaba `kcal`. Es **kcal/mol**: una
energía por mol y una energía no son la misma cantidad, y era la única magnitud
mal etiquetada de la ficha, mientras el panel de al lado ya usaba `Da`, `Å²` y
`LogP` correctamente. De paso, una afinidad ausente muestra `—` en vez de una
cifra vacía.

**UX-008 — qué afirma la ficha y sobre qué red.** El alcance del sello vive
ahora en una sola constante, `ALCANCE_DEL_SELLO`, con el mismo texto que ya
decían el modal y el PDF: acredita integridad y fecha, no valida la pose ni la
conclusión, ni sustituye evidencia experimental. La ficha lo muestra, y el
encabezado pasó de «Evidencia Digital» —que invita a leerlo como evidencia
científica— a «Registro de integridad».

La red dejó de estar escrita a mano. `cluster=devnet` aparecía literal en dos
enlaces; ahora `urlDelExplorador` la construye desde `/blockchain/health`, y
`esRedDePruebas` la declara en pantalla. Ese helper responde `true` ante una red
desconocida **a propósito**: no saber dónde se selló no puede leerse como «se
selló en producción». El modal de certificación se alineó al mismo helper.

**INT-013 — contrato declarado.** `GET /moldex` ya no devuelve `dict[str, Any]`:
`MoldexCatalogRead` y sus cuatro submodelos declaran el esquema, así que la ruta
entra en el OpenAPI versionado y queda bajo la guarda que detecta campos
renombrados u omitidos. Todos los campos científicos son opcionales y ninguno
lleva valor por defecto: `null` significa «no se midió», nunca cero.

**INT-009 y UX-011.** La normalización del catálogo dejó de ser `(m: any)`. La
recuperación ante un error de carga dejó de ser `window.location.reload()` —que
tira la sesión de la vista entera— y vuelve a pedir el catálogo.

**Un hallazgo más, del mismo linaje que SCI-014.** El orden por score usaba
`(b.score || 0) - (a.score || 0)`. Una molécula **sin** score entraba en el
ranking como si valiera cero: en descendente se hundía al fondo como la peor, y
en ascendente encabezaba la lista como la mejor. `porScore` la deja siempre al
final en los dos sentidos; el cero medido sigue participando con normalidad.

**Evidencia:** UX-008 `7 failed` → `7 passed`; INT-013 `5 failed` → `5 passed`;
orden por score `4 failed` → `4 passed`. Backend completo **`1010 passed`**;
frontend completo **`580 passed`**; `tsc --noEmit`, `py_compile` y
`git diff --check` limpios. La única incompatibilidad que reporta OpenAPI sigue
siendo la ruta retirada a propósito en TRANS-ANON-002.

---

## 3. Cobertura de pruebas existente

| Superficie | Cobertura |
|---|---|
| `api/moldex.py` | ninguna prueba dedicada |
| `app/moldex/page.tsx` | **ninguna** |
| `MoldexCard.tsx` | **ninguna** |
| `MolecularComparison.tsx` | **ninguna** |
| `CertificationModal.tsx` | `components/__tests__/CertificationModal.test.tsx` |
| certificado / reporte / blockchain (backend) | `test_certifier.py`, `test_certificate_context.py`, `test_certificate_figures.py`, `test_report_context.py`, `test_report_contract.py`, `test_evaluation_reports.py`, `test_blockchain_privacy.py` |

Las tres superficies visibles de la pestaña no tienen ninguna prueba. Es
coherente con que MOLDEX-SCI-003 sea el mismo defecto que ya se corrigió en SAR:
no había nada que impidiera su supervivencia aquí.

## 4. Lo que está bien y no debe tocarse

- **Aislamiento del catálogo.** `get_moldex_molecules` (`db/repository.py:608-651`)
  filtra por `MoleculeORM.user_id` en el `count` y en la consulta principal, y
  `api/moldex.py:32-40` devuelve un catálogo vacío sin sesión. El listado no
  filtra por cuenta en el cliente.
- **Eficiencia.** La lista usa `react-virtuoso` (`page.tsx:14`) y las props del
  visor 3D están memoizadas (`page.tsx:162-176`). El eje EFF de esta pestaña no
  parece ser el problema; se medirá igualmente antes de cerrar.
- **Lenguaje del PDF y del modal.** `pdf_generator.py` distingue con cuidado
  señal de scoring y energía libre experimental, declara la validez física como
  no evaluada y separa procedencias. Es el estándar al que deben subir la ficha
  y el panel, no al revés.

## 5. Qué se ejecutó en esta auditoría

Lectura estática exclusivamente: `api/moldex.py`, `api/routers/blockchain.py`,
`db/repository.py` (catálogo y upsert), `core/models.py`, `services/blockchain/`,
`app/moldex/page.tsx`, `MoldexCard.tsx`, `MolecularComparison.tsx`,
`CertificationModal.tsx`, `lib/api.ts`, `api/dependencies.py` y el inventario de
pruebas. **No se ejecutaron suites ni se modificó ningún archivo de producto.**

## 6. Orden de ataque propuesto

El mandato es ciencia primero, y los cuatro P0 son científicos. Dos de ellos
(001 y 004) dependen de que la procedencia llegue al cliente, así que el orden
natural es:

1. **MOLDEX-SCI-002** — cerrar el cero fabricado antes de que se selle otro. Es
   el único hallazgo cuyo daño es irreversible; también el más acotado.
2. **MOLDEX-INT-007** — emitir procedencia y `task_id` en el catálogo. Habilita
   los dos P0 restantes.
3. **MOLDEX-SCI-001** — anclar la certificación a la corrida inmutable.
4. **MOLDEX-SCI-003 + MOLDEX-SCI-004** — semántica nula y compatibilidad en el
   comparador; van juntos porque tocan el mismo archivo.
5. **MOLDEX-BE-005 + MOLDEX-INT-006** — autorización y descargas; van juntos
   porque el segundo hoy depende del agujero del primero.
6. **MOLDEX-UX-008**, y después los P2.

Cada punto es un paquete de ≤1 día y ≤10 archivos, con regresión roja primero.

## 7. Decisiones acumuladas para el propietario

Se acumulan aquí en vez de interrumpir cada paquete. Ninguna bloquea el trabajo
en curso; todas deben resolverse antes de cerrar el gate de Moldex.

| ID | Decisión | Nace en | Estado |
|---|---|---|---|
| D-01 | Qué se hace con los sellos ya emitidos sobre un score fabricado | MOLDEX-SCI-002 | pendiente |
| D-02 | Qué se hace con los sellos cuya corrida fue sobrescrita después | MOLDEX-SCI-001 | pendiente |
| D-03 | Si el espacio demo debe seguir existiendo como espacio compartido | MOLDEX-BE-005 | **resuelta**: cerrarlo |
| D-04 | devnet vs mainnet, y cómo se declara la red en la ficha | MOLDEX-UX-008 | pendiente |
| D-05 | Retirar el fallback demo y acotar qué puede hacer el invitado | MOLDEX-BE-005 | **resuelta**, sin implementar |
| D-06 | Traspaso `Desktop User` → cuenta nueva al registrarse | TRANS-ANON-002 | especificada; **requisito de D-05** |

### D-01 · Sellos ya emitidos sobre un cero fabricado

La corrección impide sellos futuros, pero **lo que ya está en la cadena no se
puede corregir**. Si existen certificados emitidos cuando `total_score` era
nulo, hoy dicen `0.00` y el producto los presenta como certificados válidos.

Opciones: (a) detectar en Moldex los sellos cuyo score sellado no coincide con
el vigente y declararlos como no interpretables; (b) no hacer nada y documentar
la limitación; (c) inventariar primero cuántos hay y decidir con el dato.

**Inventario intentado 2026-08-30.** Las tres bases de desarrollo del repo están
vacías a este efecto: `backend/moldesign.db` y `backend/molecular_design.db` no
tienen ninguna tabla, y `backend/moldesign_local.db` sólo tiene `users` y
`anonymous_limits`. En esta máquina **no hay ningún sello emitido**, así que el
alcance real de D-01 sólo puede medirse sobre la base de una instalación de
escritorio con datos. La consulta es:

```sql
SELECT COUNT(*) FROM evaluation_results
WHERE blockchain_tx_id IS NOT NULL AND total_score IS NULL;
```

Si ese número resulta ser 0 en las instalaciones reales, D-01 se cierra sin
trabajo: bastaría documentar que el defecto existió y nunca llegó a emitir un
sello.

### D-02 · Sellos cuya corrida fue sobrescrita

Mismo problema, distinto origen: el sello es correcto pero la fila que lo
acompaña ya no es la corrida certificada.

**Estado tras MOLDEX-SCI-001 (2026-08-30).** Los sellos **nuevos** quedan
anclados a su corrida y la divergencia se detecta sola. Los **anteriores a v14**
tienen `certified_task_id` a `NULL` y la interfaz los declara `SELLO SIN
CORRIDA`. Deliberadamente **no se rellenaron**: copiarles el `task_id` vigente
los dejaría en verde afirmando una correspondencia que nadie comprobó.

Lo que queda por decidir es qué hacer con ellos: (a) dejarlos indeterminados
para siempre; (b) ofrecer al dueño re-certificar la corrida vigente, lo que
emite un sello nuevo y cuesta comisión de red; (c) intentar reconstruir el
vínculo leyendo el score del memo on-chain y buscándolo en `evaluation_runs`
—posible, pero un empate de scores lo haría ambiguo, y un vínculo probable no es
un vínculo—. La opción (a) es la única que no puede equivocarse.

### D-03 · El espacio demo — RESUELTA 2026-08-30

La premisa de esta decisión era falsa. Arreglarlo **no** rompía el flujo de
escritorio, porque ese flujo no depende del espacio demo: el escritorio inicia
sesión solo como `Desktop User` (`/auth/desktop-login`), una cuenta con
identidad propia. El espacio demo es un segundo invitado, redundante, con una
credencial pública.

Decisión del propietario: cerrarlo. Cerrado en la superficie de Moldex
(MOLDEX-BE-005) y neutralizada la credencial (MOLDEX-BE-015). Lo que queda es
D-05.

### D-05 · El fallback demo y los permisos del invitado — RESUELTA 2026-08-30

`current_user.id if current_user else demo_user.id` sigue vivo en siete
posiciones fuera de Moldex:

| Dónde | Qué hace |
|---|---|
| `evaluation.py:306`, `:617` | autorización de tarea y de resultado |
| `evaluation_access.py:35-37` | la política **compartida** de archivos y reportes |
| `db/repository.py:563` | asigna el demo como dueño de una molécula sin `user_id` |
| `services/cohort/repository.py:120` | `resolve_owner_id` de las cohortes |
| `services/ai/tools/evaluation_tools.py:40`, `session_tools.py:206` | contexto de MolChat |

**Decisión del propietario (2026-08-30).** Eliminar la cuenta demo por
completo. La única identidad sin registro es `Desktop User`, y su alcance queda
definido así:

| Acción | Invitado (`Desktop User`) | Cuenta registrada |
|---|---|---|
| Ejecutar evaluaciones | **sí**, sin límite (TRANS-ANON-002) | sí |
| Guardar en Moldex (`is_saved`) | **no** | sí |
| Certificar en blockchain | **no** | sí |

**Aviso: esa restricción todavía no existe.** Verificado el 2026-08-30:
`history.py:357` pone `is_saved = True` sin comprobar qué cuenta lo pide, y
certificar sólo exige `get_current_user`, que `Desktop User` cumple. Hoy el
invitado guarda y certifica igual que una cuenta real. La decisión describe el
destino, no el estado.

El paquete que la implemente tiene tres partes, y la tercera es la delicada:

1. retirar el fallback `else demo_user.id` de las siete posiciones, y con él la
   cuenta demo;
2. poner la puerta de «guardar» y «certificar» detrás de una cuenta registrada,
   con un mensaje que explique por qué y ofrezca registrarse;
3. **decidir qué pasa con lo que el invitado ya guardó.** En instalaciones
   existentes hay moléculas de `Desktop User` marcadas `is_saved` y quizá
   certificadas, porque hasta hoy estaba permitido. No pueden desaparecer de la
   vista sin más. Esto convierte a **D-06 en requisito, no en mejora**: el
   traspaso al registrarse es la vía por la que ese trabajo llega a una cuenta.

Alcance a tener en cuenta: las siete posiciones son Evaluación, Batch y MolChat,
y **las dos primeras ya pasaron su gate** — cambiar su autorización obliga a
repetirlo. Además `evaluation_access.py` documenta la laxitud como intencional,
así que el paquete debe retirar también esa declaración.

### D-06 · Traspaso del trabajo del invitado a la cuenta nueva

Especificación acordada, pendiente de implementar. `Desktop User` es una cuenta
real con `user_id`, así que **no hace falta ninguna columna nueva**: el traspaso
es mover filas de una cuenta a otra.

Al registrarse, se cuenta lo que hay bajo `Desktop User` —moléculas guardadas en
Moldex y casos— y se pregunta: *«Hay este trabajo previo sin cuenta, ¿quieres
traspasar algo a la cuenta que acabas de crear?»*, con selección de qué llevarse.
Lo que no se traspase se queda donde está, y cerrar sesión devuelve al invitado
y a su trabajo.

Los casos viven en el cliente (`tauriCaseRepository`, con `ownerUserId` en el
manifiesto), así que su traspaso es una reescritura de manifiesto, no una query.
Las moléculas sí son un `UPDATE` en backend.

### D-04 · Red del sello

Decisión comercial del §14 del plan. Independientemente de cuál se elija, la
ficha debe declarar la red y el alcance del sello, que hoy sólo aparecen en el
modal y en el PDF.

---

## 8. Riesgos y trabajo no verificado

- **No se reprodujo ningún hallazgo en ejecución.** Todo lo anterior es lectura
  de código con líneas citadas. Antes de cada corrección hay que escribir la
  regresión que lo demuestre, como exige el protocolo.
- **MOLDEX-SCI-001 y 002 pueden ya haber ocurrido** en datos existentes. Si hay
  sellos emitidos sobre un `total_score` nulo o sobre corridas posteriormente
  sobrescritas, no se pueden reparar en la cadena: habrá que decidir cómo se
  declaran en la interfaz. Es una decisión del propietario, no mía.
- **La política de red (devnet vs mainnet)** es una decisión comercial del §14 del
  plan, no un hallazgo técnico. Aquí sólo se registra que la ficha no la declara.
- **No se auditó** `MoleculeViewer3D` (liberación de recursos WebGL) ni la
  navegación Evaluación↔Moldex, ambas dentro del alcance §7. Quedan para
  MOLDEX-AUD-01.

---

## 9. Estado de ejecución — corte del 2026-08-31

Las secciones 1–8 son el **expediente histórico**: la auditoría de lectura, sus
hallazgos y las decisiones tal como se plantearon. No se reescriben — un
documento histórico no se actualiza, se le añade el corte siguiente.

Esta sección es el **estado actual**, y separa lo que antes iba mezclado: qué
está hecho, con qué evidencia ejecutada, qué decisiones siguen abiertas y qué
falta para el gate.

### Gate runtime — APROBADO 2026-08-31

Protocolo y evidencia: [68_GATE_RUNTIME_MOLDEX_Y_MOLCHAT.md](68_GATE_RUNTIME_MOLDEX_Y_MOLCHAT.md).
Ejecutor reproducible: `scripts/accept_moldex_runtime.py`.

Corrida real con Vina/Meeko (`-5.489 kcal/mol`), guardado en Moldex, reinicio del
backend, recuperación por el `task_id` exacto, comparación de dos corridas,
reevaluación sin alterar la corrida anterior, y una segunda cuenta rechazada en
cinco superficies (`403/403/403/403/404`) incluida la certificación (`403`).
Descargas del dueño: poses `200`, complejo `200`, dossier PDF `200`. Ausencia de
score comprobada como ausencia, no como cero ni tier.

**Moldex no se declara aprobado del todo:** el gate no emitió un sello real
—eso exige red y una cartera con fondos— así que la transición a «sello
desfasado» tiene su precondición verificada pero no su ejercicio. Depende de
D-04.

### Pruebas de render, que faltaban

`components/__tests__/MoldexRender.test.tsx` (`6 passed`) fija lo que
MOLDEX-SCI-014 corrigió en el código y nadie vigilaba en la pantalla: una
molécula sin score no se etiqueta `D-Tier`, no se pinta como cero y declara la
ausencia con un guion — y un score de cero **sí** es un cero, que es el contraste
que hace útil a la prueba.

### Decisiones: lo que este corte resuelve y lo que no

**D-01 · Sellos emitidos sobre un cero fabricado — CERRADA, sin trabajo.**
El inventario se ejecutó sobre la base de escritorio real de esta máquina, en
sólo lectura:

| Consulta | Resultado |
|---|---|
| `evaluation_results` | 210 |
| con `blockchain_tx_id` | **2** |
| con sello y `total_score IS NULL` | **0** |

Los dos sellos existentes tienen score (`1.02` y `13.89`). El defecto existió y
**nunca llegó a emitir un sello con un cero fabricado**, al menos aquí. Queda
documentado como limitación histórica; no hay nada que reparar en la cadena.

**D-02 · Sellos sin corrida identificada — CUANTIFICADA, decisión abierta.**
La base de esta máquina es **anterior a la columna `certified_task_id`**: no
existe. Los dos sellos son, por tanto, pre-v14, y no se puede saber qué corrida
atestiguaron. La interfaz ya los declara `SELLO SIN CORRIDA` y **no se les
rellena** el vínculo, que sería afirmar una correspondencia que nadie comprobó.

Lo que hay que decidir sobre esos **2 sellos** sigue siendo lo del §7: (a)
dejarlos indeterminados para siempre —la única opción que no puede
equivocarse—; (b) ofrecer re-certificar, que emite un sello nuevo y cuesta
comisión; (c) reconstruir el vínculo por el score del memo, que un empate haría
ambiguo. Mi lectura no cambia: (a).

**D-04 · Red del sello (devnet vs mainnet) — ABIERTA.** Decisión comercial del
§14 del plan. Bloquea la parte del gate que emitiría un sello real.

**D-05 · Permisos del invitado — resuelta a medias, y la mitad hecha.**
Los `else demo_user.id` **ya no existen**: el espacio anónimo dejó de ser un
espacio compartido. El filtro era `user_id not in {cuenta, demo}`, así que
cualquier cuenta registrada leía todo lo anónimo, y la comprobación de IP que
protege lo anónimo llegaba *después* de conceder el acceso. Ahora una molécula
tiene un dueño y sólo uno. Evidencia:
`backend/tests/test_el_espacio_anonimo_no_es_de_todos.py` (`12 passed`), y los
gates de Evaluación y Batch **re-ejecutados** después del cambio, como exige el
protocolo cuando se toca autorización.

**Lo que sigue abierto de D-05:** si el invitado puede guardar en Moldex y
certificar. No se ha tocado, porque es una decisión de producto y no de
implementación.

**D-06 · Traspaso del trabajo del invitado — IMPLEMENTADO en backend.**
`POST /auth/traspaso` mueve moléculas y cohortes del invitado a la cuenta que lo
pide. Es **selectivo** (listas explícitas; no traspasar es una decisión
legítima), **transaccional** (si algo de lo pedido no existe o es de otra cuenta,
no se mueve nada), **idempotente** (lo que ya es del destino se cuenta como
hecho) y **en un solo sentido** (ni el invitado recibe, ni una cuenta toma de
otra). Las corridas de cohorte siguen a su cohorte. Evidencia:
`backend/tests/test_traspaso_del_invitado.py` (`10 passed`).

**Falta la mitad de interfaz:** el ofrecimiento al registrarse —contar lo que hay
bajo `Desktop User` y preguntar qué llevarse— no está construido. Y el traspaso
de **casos** sigue pendiente: viven en el cliente
(`tauriCaseRepository`, con `ownerUserId` en el manifiesto), así que es una
reescritura de manifiesto y no una query.

### Pendiente

1. **D-04**, que bloquea el sello real del gate.
2. **La mitad de D-05 que es de producto**: permisos del invitado para guardar y
   certificar.
3. **La interfaz del traspaso** y el traspaso de casos del lado cliente.
4. **`MoleculeViewer3D`** (liberación de recursos WebGL) y la navegación
   Evaluación↔Moldex: siguen sin auditar, como declara el §8.
