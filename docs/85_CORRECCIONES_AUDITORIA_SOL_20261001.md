# Correcciones de la auditoría DevOps SOL — 2026-10-01

**Estado:** **cerrado el 2026-10-03** (cada hallazgo con su commit en el índice; lo que no se hizo, declarado en su sección).
**Objeto:** registrar cada corrección aplicada a partir de los informes de
auditoría de GPT-sol 6 sobre la pestaña Evaluación, con diagnóstico, decisión,
contratos afectados y pruebas de verificación.

**Fuentes de auditoría:**

- `D:\moldesign-audits\AUDIT_moldesign_ae4db6a\devops_sol\informe_devops_sol.md`
  (SOL-01 a SOL-16)
- `D:\moldesign-audits\AUDIT_moldesign_ae4db6a\devops_sol\informe_devops_sol_casos_40.md`
  (CAS-01 a CAS-07)
- `D:\moldesign-audits\AUDIT_moldesign_ae4db6a\devops_sol\informe_devops_sol_evaluacion_ampliada.md`
  (AMP-01 a AMP-11)

## Jerarquía de principios

Todas las decisiones de este documento se rigen por:

> **CIENCIA > CALIDAD > EFICIENCIA**

- **Ciencia:** honestidad epistemológica. Si un cálculo es ambiguo o no está
  resuelto, el sistema se abstiene y lo declara. Nunca fabrica un score ni
  disimula una incertidumbre. La preparación que el investigador ve y aprueba
  tiene que describir fielmente el protocolo que se ejecutará.
- **Calidad:** coherencia de contratos, tipado estricto, persistencia auditable,
  suites verdes y sincronizadas. Ninguna interfaz contradice a otra ni muestra
  estados complacientes.
- **Eficiencia:** sólo después de lo anterior. Ningún control o verificación
  física se sacrifica por ahorrar ciclos.

## Reglas del repositorio que gobiernan estas correcciones

- Dos motores y sólo dos: AutoDock Vina 1.2.7 y ESMFold. Nada de motores
  fantasma.
- Frontera GPL: Open Babel es un programa independiente; prohibido importar
  `openbabel`/`pybel` desde `backend/` o `rescoring/`.
- Prohibido tocar `scripts/artifacts_science/` (artefactos sellados).
- Si se agregan o adaptan pruebas de backend, ejecutar
  `python scripts/report_test_counts.py --write` para actualizar el registro
  de conteo (`docs/api/test-counts.json`).

## Metodología por hallazgo

1. Revisar la evidencia del informe de auditoría.
2. Formular el plan y el porqué de la solución.
3. Crear/adaptar la prueba que reproduzca el fallo.
4. Aplicar el cambio mínimo y robusto.
5. Verificar la suite local.
6. Actualizar este documento.
7. Presentar el cambio para revisión y commit.

Cada corrección se registra con la estructura:

- **ID del hallazgo.**
- **Diagnóstico del problema** (qué fallaba, componente, impacto).
- **Decisión tomada y el PORQUÉ** (racional científico y técnico, justificado
  bajo *Ciencia > Calidad > Eficiencia*).
- **Contratos y archivos modificados** (rutas y funciones).
- **Pruebas de verificación** (creadas/modificadas y resultado).

## Índice de hallazgos

| ID | Severidad | Resumen | Estado |
|---|---|---|---|
| SOL-01 | P1 | Receptores privados no superan el preflight desde la UI (falta `Authorization` en `requestPreflight`/`getTargetPdb`) | **Corregido (commit 4fb34bb)** |
| SOL-02 | P1 | La semilla anunciada en preflight difiere de la ejecutada; conflicto de fuentes top-level vs anidadas produce 409 | **Corregido (commit e75592c)** |
| SOL-03 | P1 | Badge «CALIBRACIÓN Listo» sobre receptor sin calibración medida | **Corregido (commit db371dc)** |
| SOL-04 | P1 | SAR acepta como coincidentes protocolos con pH diferente (firma omite condiciones químicas) | **Corregido junto con AMP-02 (commit 6f3ac86)** |
| SOL-05 | P2 | Estado global `ready` con controles físicos fallidos | **Corregido (commit 83372c9)** |
| SOL-06 | P2 | «Reproducibilidad técnica completa» exige sólo tres campos | **Corregido (commit 21d48bb)** |
| SOL-07 | P2 | Caja en espacio vacío pasa preflight sin reserva | **Corregido (commit 83372c9)** |
| SOL-08 | P2 | «Desmarcar todos» los hotspots se convierte en los 15 del catálogo | **Corregido junto con SOL-09 (commit 31e9e20)** |
| SOL-09 | P2 | La UI atribuye a los hotspots una guía de búsqueda que Vina no recibe | **Corregido junto con SOL-08 (commit 31e9e20)** |
| SOL-10 | P2 | Caso nuevo muestra aspirina sin persistirla como ligando | **Corregido junto con CAS-04 (commit 8130cd8)** |
| SOL-11 | P2 | El export pide recursos RSC inexistentes (smoke 14/15) | **No reproducible con el pipeline actual; guardia endurecida (commit 1f05fff)** |
| SOL-12 | P2 | Violación CSP al cargar WASM embebido (`data:` bloqueado por `connect-src`) | **Ruido aceptado por decisión del propietario: origen en Mol* (codificador MP4), CSP intacta (commit 1f05fff)** |
| SOL-13 | P2 | Centro de caja recortado silenciosamente a ±100 Å | **Corregido (commit a146c31)** |
| SOL-14 | P2 | Controles numéricos sin nombre accesible | **Corregido junto con SOL-13 (commit a146c31)** |
| SOL-15 | P2 | Textos nuevos de Evaluación fijados en español | **Corregido por el propietario (commit 29c6b33)** |
| SOL-16 | P2 | Pruebas de regresión desalineadas con contratos actuales | **Corregido (commit 74cb976)** |
| CAS-01 | P2 | Historial no muestra K en la descripción de protocolo | **Corregido (commit 4a75abe)** |
| CAS-02 | P2 | SAR no reconstruye la cohorte histórica de corridas únicas | **Corregido (commit 6da7969)** |
| CAS-03 | Ajuste | Identificar/filtrar/comparar 40 filas del historial | **Filtros, K y diferencias hechos; etiqueta de ligando pendiente de decisión de producto (commit 4a75abe)** |
| CAS-04 | P2 | Estimación de duración usa K=1 mientras se ejecuta K=30 | **Corregido junto con SOL-10 (commit 8130cd8)** |
| CAS-05 | P1 | Aplicar Opciones tras pasar a ensemble deja K anidado=1 y produce 409 | **Corregido (commit e75592c)** |
| CAS-06 | P1 | PDF de ensemble: HTTP 500 por fila de tabla imposible de paginar | **Corregido junto con AMP-04 (commit a60c52b)** |
| CAS-07 | P2 | Reservas del receptor repetidas 30 veces en ensemble | **Corregido (commit afbaf0a)** |
| AMP-02 | P1 | SAR compara especies acopladas a distinto pH (confirmación real de SOL-04) | **Corregido junto con SOL-04 (commit 6f3ac86)** |
| AMP-01 | P1 | Se pierde una disposición científica al editar inputs | **Corregido (commit 259f1a7)** |
| AMP-03 | P1 | El automático y el manual preparan el sitio anti-diana de forma distinta | **Corregido (commit 8bdd43a)** |
| AMP-04 | P1 | El PDF heredado vuelve a fallar en ensembles | **Corregido junto con CAS-06 (commit a60c52b)** |
| AMP-11 | P2 | El dossier debe distinguir receptor declarado y unidad acoplada | **Corregido (commit 21d48bb)** |
| AMP-05 | P2 | Notas del caso no llegan al dossier humano | **Corregido (commit dc592bc)** |
| AMP-06 | P2 | La interfaz guarda texto que el export rechaza | **Corregido (commit dc592bc)** |
| AMP-07 | P2 | Dos documentos con identidad ambigua | **Corregido (commit ad8483e)** |
| AMP-08 | P2 | Problemas de presentación y portabilidad del PDF | **Corregido junto con AMP-07 (commit ad8483e)** |
| AMP-09 | P2 | Progreso de selectividad no representa resultados recuperados | **Denominador corregido; el «0/0» no se reproduce (commit 364d768)** |
| AMP-10 | P2 | Una corrida histórica ofrece una ampliación que el servidor rechaza | **Corregido (commit 364d768)** |

---

## SOL-02 — La semilla anunciada en preflight puede diferir de la ejecutada

**Severidad:** P1 (procedencia). **Comprobación de auditoría:** API y docking reales.

### Diagnóstico

El contrato de la corrida tiene **dos fuentes de verdad** para el mismo
protocolo de docking, y cada consumidor lee una distinta:

| Fuente | Campos |
|---|---|
| Nivel superior de `PreflightRequest` | `exhaustiveness`, `num_poses`, `conformers` (no existe `seed` de nivel superior) |
| Anidados de `pipeline_config.stage_params` | `docking.{exhaustiveness,num_poses,seed}`, `conformer.{conformers,ph}` |

Qué lee cada pieza (verificado en código, 2026-10-01):

1. **Preflight** (`backend/services/docking/preflight.py`):
   - `effective["seed"] = int(settings.vina_seed)` (línea 1534) — **siempre**
     el valor global (42). Ignora `stage_params.docking.seed`.
   - `effective["exhaustiveness"]` y `effective["num_poses"]` se resuelven de
     los campos de **nivel superior** del request, con defaults de `settings`
     (`vina_exhaustiveness=8`, `vina_num_poses=5`).
   - El fingerprint se firma con estos valores efectivos **más** el
     `pipeline_config` completo dentro del documento
     (`canonical_input_document`, líneas 273-299).
2. **Submit** (`backend/api/routers/evaluation.py`, `_validar_antes_de_ejecutar`,
   líneas 697-741): la revalidación construye el `PreflightRequest` de la
   comprobación fresca leyendo **sólo los anidados**
   (`exhaustiveness=docking_params.get("exhaustiveness")`,
   `num_poses=docking_params.get("num_poses")`, y
   `conformers=stage_params.conformer.conformers`).
3. **Runner** (`backend/services/pipeline/runner.py`, líneas 502, 643-664):
   ejecuta los **anidados** con defaults **hardcodeados distintos de settings**:
   `exhaustiveness=params.get("exhaustiveness", 32)`,
   `num_poses=params.get("num_poses", 8)`,
   `seed=params.get("seed", 42)`. Además el registry declara
   `docking: {exhaustiveness: 32, num_poses: 9}`
   (`backend/services/pipeline/registry.py:70`) — un tercer juego de defaults.

Consecuencias reproducidas por la auditoría y confirmadas en la lectura:

- **Semilla falsa en la declaración:** con
  `pipeline_config.stage_params.docking.seed=123`, el preflight responde
  `effective_config.seed=42`, el submit acepta (el fingerprint incluye el
  `pipeline_config` completo, así que preflight original y revalidación
  coinciden por casualidad) y la corrida ejecuta `vina_random_seed=123`.
  La preparación que el investigador aprueba **no describe el protocolo
  ejecutado**.
- **409 espurio:** un preflight llamado con exhaustiveness/poses de nivel
  superior `8/9` y anidadas `32/1` firma un documento con `8/9` arriba; la
  revalidación del submit construye su documento con `32/1` (los anidados).
  Mismo input científico, dos documentos, fingerprint distinto → 409
  «La hipótesis o la preparación cambió» sin que nada cambiara.
- **Tres defaults incoherentes** para el mismo parámetro: settings (8/5/42),
  registry (32/9), literales del runner (32/8/42). Hoy la UI no envía
  `seed` anidada y ambas cifras coinciden en 42 **por casualidad**.

### Decisión tomada y el PORQUÉ

**Una sola resolución del protocolo, compartida por preflight, fingerprint,
revalidación y runner: `services.docking.protocolo.resolver_parametros_docking`.**

La cadena efectiva es `anidado ?? settings`, con la política de volumen de
`search_policy` aplicada dentro de la resolución (eleva sólo el *default* en
cajas grandes; lo explícito se respeta). Los campos de **nivel superior** del
request del preflight (`exhaustiveness`, `num_poses`, `conformers`) **no
participan en la resolución: son asesores**. Si contradicen lo que se va a
ejecutar, el informe emite el control `PROTOCOLO_DECLARADO_CONFLICTIVO`
(advertencia) nombrando ambos valores.

**Precisión sobre la cadena `anidado ?? nivel_superior ?? settings` del plan
aprobado.** Para la **semilla** —el hallazgo real de SOL-02— la cadena se
cumple literalmente: no existe campo de nivel superior, así que es
`anidado ?? settings`, con canon 42 (`settings.vina_seed`):
- Sin semilla explícita (caso ordinario/UI): preflight declara **42**,
  fingerprint firma **42**, runner ejecuta **42**.
- Semilla explícita en `pipeline_config.stage_params.docking.seed`: preflight
  la declara, el fingerprint la firma y el runner la ejecuta.
- Invariante: *lo declarado = lo ejecutado = lo sellado*.

Para exhaustividad/poses/confórmeros, honrar el nivel superior como escalón
intermedio **rompería el propio invariante**, y eso es un hecho estructural,
no una preferencia: ni `EvaluationSubmitRequest` ni `/evaluation/evaluate`
llevan campos de protocolo de nivel superior, y la revalidación del submit
sólo puede derivarlos de los anidados. Honrarlos declararía corridas que
ningún submit puede ejecutar y recrearía el bucle de 409 (el cliente
repetiría su preflight original, obtendría la misma huella y el submit la
rechazaría siempre). La auditoría pedía exactamente lo implementado: «una
única configuración efectiva; los conflictos se identifican explícitamente».
- **Ciencia:** `effective_config` ahora describe el protocolo que correrá de
  verdad; una discrepancia del cliente queda declarada, no ejecutada en
  silencio.
- **Calidad:** preflight original y revalidación firman el MISMO documento
  canónico por construcción (ambos son función de `pipeline_config` +
  geometría + ligando), no por casualidad. El runner consume la misma
  resolución: eliminados los literales `32/8/42` y el tercer defecto del
  registry (`32/9`, ahora eco de settings).
- **Eficiencia:** menos recomprobaciones forzosas por falsos conflictos; el
  resolutor es una función pura compartida.

**Compatibilidad:** el fingerprint sólo cambia para peticiones con protocolo
anidado que antes se declaraba mal (p. ej. semilla anidada ≠42) — el
anterior describía una corrida falsa, así que el cambio es la corrección.
Para el flujo ordinario de la UI (espejos sincronizados con lo anidado), el
documento canónico es idéntico al de antes: `conformers` sólo entra con K>1
y la semilla sigue siendo 42.

### Contratos y archivos modificados

- `backend/services/docking/protocolo.py` — nueva función
  `resolver_parametros_docking(...)`: resolución única (semilla, poses,
  exhaustividad con política de volumen, K) y detección de conflictos con
  el nivel superior.
- `backend/services/docking/preflight.py` — `_effective_configuration`
  recibe `pipeline_config` y resuelve el protocolo con el resolutor;
  emite `PROTOCOLO_DECLARADO_CONFLICTIVO`; `build_preflight` firma el
  documento con el K resuelto (`effective["conformers"]`) y pasa
  `pipeline_config` a la resolución.
- `backend/services/pipeline/runner.py` — la etapa docking consume
  `resolver_parametros_docking`; eliminados los literales `32/8/42`.
- `backend/services/pipeline/registry.py` — `STAGE_REGISTRY["docking"].params`
  pasa de `32/9` a eco de `settings` (8/5), documentado como no-fuente.
- `backend/api/routers/evaluation.py` — **sin cambios**: la revalidación ya
  derivaba los campos de los anidados; tras la unificación ambos caminos
  convergen.
- `backend/tests/test_evaluation_preflight.py` — actualización consciente de
  dos casos parametrizados (`{"exhaustiveness": 16}`, `{"num_poses": 12}` sin
  `pipeline_config`) que codificaban el contrato antiguo: huellas de corridas
  que ninguna puerta de ejecución podía realizar. Sustituidos por variantes
  con `pipeline_config` (que sí cambian la corrida) y por la contraparte
  explícita en «lo que no puede cambiar la corrida».

### Pruebas de verificación

Nuevas (`backend/tests/test_configuracion_efectiva_docking.py`, 18 pruebas):

- Reproducción SOL-02 en rojo antes del cambio: `effective_config.seed` era
  **42** con semilla anidada **123** (medido con el código previo); el
  documento firmaba 42. Ahora declara y firma 123.
- Canon 42 protegido por prueba explícita (resolución sin semilla ==
  `settings.vina_seed` == 42).
- Propiedad que mata el 409: el fingerprint de una llamada con espejos de
  nivel superior (8/9/30) y el de una sin ellos es **idéntico** para el
  mismo `pipeline_config` (antes: distintos, medido).
- Control `PROTOCOLO_DECLARADO_CONFLICTIVO`: advertencia que nombra ambos
  valores; no bloquea; sin conflicto no aparece.
- K anidado gobierna: declarar K=30 arriba con K=1 anificado declara K=1
  efectivo (antes: 30, medido) y el documento no cambia la huella histórica
  de K=1.
- Runner: source-text de que consume el resolutor y de que los literales
  desaparecieron; registry sin segundo defecto.

**Resultado:** 18/18 verde. Suite backend completa: **3018 pasan, 2 fallan
(preexistentes, verificados con `git stash`: `test_peptide_docking` de SOL-16
y `test_sonda_de_sidecar_no_cuesta`, ambos del sidecar ESMFold, ajenos a este
cambio), 4 saltan.** Registro de conteo actualizado con
`report_test_counts.py --write` (3024 recolectadas).

---

## CAS-05 — Reabrir y aplicar Opciones después de pasar a ensemble bloquea con 409

**Severidad:** P1 (bloqueo de flujo por configuración contradictoria).
**Comprobación de auditoría:** UI real, 409 reproducido.

### Diagnóstico

Cadena completa verificada en código (2026-10-01):

1. El caso corre primero con K=1. Al registrarse la corrida, el sistema
   estructural del caso congela el `pipelineConfig` de esa primera corrida
   (`structuralSystemFromRun`,
   `frontend/lib/cases/types.ts:702-739`) con
   `stage_params.conformer.conformers = 1`.
2. El usuario pasa a Ensemble K=30 desde el panel de Preparación.
   `onConformersChange` (`CaseEvaluationRunner.tsx:631-646`) escribe
   coherentemente `inputs.conformers = 30` **y**
   `inputs.pipelineConfig.stage_params.conformer.conformers = 30`. La corrida
   ensemble funciona.
3. El usuario abre Opciones y aplica **sin cambiar nada**. El `onApply` del
   modal (`ProEvaluation.tsx:1715-1745`) reconstruye el objeto anidado con:

   ```ts
   conformer: {
     conformers: initialRunConfiguration?.pipelineConfig?.stage_params?.conformer?.conformers ?? 1,
     ph: adv.protonationPh,
   },
   ```

   y `initialRunConfiguration` (`CaseEvaluationRunner.tsx:1199-1207`)
   prioriza `structuralSystem?.pipelineConfig` — el sistema **congelado de la
   primera corrida (K=1)** — por encima de los inputs vigentes (K=30).
4. Con el sistema sellado, `onRunConfigurationChange`
   (`CaseEvaluationRunner.tsx:1425-1441`) persiste
   `dockingEngine/exhaustiveness/numPoses/pipelineConfig` pero **no**
   `conformers` de nivel superior. Resultado exacto que midió la auditoría:
   `inputs.conformers = 30`, `stage_params.conformer.conformers = 1`.
5. Siguiente preflight: envía `conformers: 30` (nivel superior) con el
   anidado en 1. El backend responde 200 con «K efectivo 30» y firma un
   documento canónico con `conformers=30` **más** el `pipeline_config`
   anidado en 1.
6. Siguiente submit: la revalidación construye su comprobación fresca con
   `conformers = stage_params.conformer.conformers = 1` (sólo los anidados).
   El documento fresco ya no lleva la clave `conformers` (sólo entra con K>1)
   → fingerprint distinto al mostrado → **409**.

El backend se abstiene correctamente de ejecutar un protocolo distinto del
comprobado (la guardia funciona); el defecto está en la **configuración
contradictoria que construye la interfaz**, y en la doble fuente de verdad del
backend que la vuelve frágil (raíz compartida con SOL-02).

### Decisión tomada y el PORQUÉ

**El K vigente del caso gobierna; aplicar Opciones sin cambios no puede
modificar K.**

- **Ciencia:** K (número de confórmeros) define el protocolo que se ejecuta y
  firma la corrida. Que un modal que no ofrece control de K lo reescriba de
  facto a 1 es una decisión estructural tomada sin el investigador.
- **Calidad:** el `onApply` del modal lee el K **vigente** del caso (prop
  nueva `activeConformers`, obligatoria en el contrato de `ProEvaluation`),
  no el congelado en la primera corrida. Y el merge de
  `configuracionDelPipeline` es ahora **profundo, por etapa y clave**: un
  guardado parcial (`conformer: {ph}` sin `conformers`, `docking` a medias)
  ya no borra claves del protocolo — la raíz de QA-036 y de esta familia.
- **Eficiencia:** elimina recomprobaciones forzosas y corridas bloqueadas por
  una configuración que nadie cambió.

Con SOL-02 unificado en el backend, esta clase de contradicción dejó además
de producir un 409 opaco: preflight, revalidación y ejecución convergen sobre
la misma configuración efectiva, y una discrepancia residual se declara como
control. Ambas correcciones son complementarias: CAS-05 arregla la
construcción de la configuración en la UI; SOL-02 hace el contrato inmune a
la discrepancia.

**Nota de alcance:** no se añadió ningún control de semilla al modal de
Opciones — acordado: primero integridad de contratos y desaparición del 409;
el control visual se expone en un paso posterior.

### Contratos y archivos modificados

- `frontend/components/interfaces/pro/ProEvaluation.tsx` — prop nueva
  obligatoria `activeConformers: number`; el `onApply` construye
  `conformer.conformers` desde el K vigente (antes:
  `initialRunConfiguration?.pipelineConfig?.stage_params?.conformer?.conformers ?? 1`,
  que priorizaba el sistema sellado K=1).
- `frontend/components/evaluation/CaseEvaluationRunner.tsx` — pasa
  `activeConformers={inputs?.conformers ?? 1}`; `configuracionDelPipeline`
  fusiona por etapa y clave (deep merge por `docking`/`conformer`/
  `properties`, preservando etapas extra que el guardado traiga).
- `frontend/lib/cases/types.ts` / `schema.ts` — sin cambios de esquema.

### Pruebas de verificación

Nuevas (`frontend/components/evaluation/__tests__/configuracionEfectivaPipeline.test.tsx`,
9 pruebas):

- Reproducción en rojo antes del cambio: el mock del modal recibía
  `activeConformers` ausente y el recorrido persistía **K=1** anidado en un
  caso con K=30 y sistema sellado K=1 — la cadena exacta de la auditoría
  (medido: `expected 1 to be 30`).
- Merge: un `conformer: {ph}` sin `conformers` hereda el K vigente (antes lo
  perdía); un `docking` a medias conserva `num_poses` del defecto; sin
  guardado el defecto declara K=1/poses 9/ADMET apagado; un guardado completo
  pasa limpio.
- Cableado leído del fuente (patrón `AdmetOptIn.test.ts`): la prop es parte
  del contrato, el `onApply` ya no contiene la expresión del defecto, el
  runner pasa el K de los inputs.
- Recorrido con sistema sellado: el modal recibe K=30 aunque el congelado
  diga 1; aplicar sin cambios conserva K=30 en el anidado y no degrada el K
  de nivel superior del caso.
- Compatibilidad: las 3 pruebas preexistentes de QA-036
  (`configuracionDelPipeline.test.ts`) siguen verdes con el merge profundo.

**Resultado:** 9/9 verde. `tsc --noEmit` limpio. Suite frontend completa:
**122 archivos / 1116 pruebas, todas pasan** (incluye las familias de
evaluación, casos y pro: 436/436). El control visual de semilla quedó
explícitamente fuera de alcance.

---

## SOL-04 / AMP-02 — SAR compara especies acopladas a distinto pH

**Severidad:** P1 (honestidad de la comparación científica).
**Comprobación de auditoría:** SOL-04 por inspección + función real extraída
por AST; AMP-02 por uso real de la interfaz (serie benzoica contra 3F75).

### Diagnóstico

La auditoría citó `protocol_signature()` en `sar.py:196`. Verificado el
2026-10-02, ese código **no vivía en el árbol commiteado**: era trabajo sin
commitear que quedó en `stash@{0}` («cambios restantes conservados tras
retirar EGFR», 2026-10-01). Su firma comparaba receptor, versión, semilla,
motor, exhaustividad, poses, confórmeros y caja — **omitía el pH y la
preparación química del ligando**.

El `sar.py` vivo tenía algo peor: **ninguna compuerta de comparabilidad**.
`delta_affinity` y `delta_score` se restaban incondicionalmente entre
cualquier dos corridas del mismo target.

La reproducción real de AMP-02, con el dato que la hace científicamente
grave: la base a pH 7,4 registró `O=C([O-])c1ccccc1` (carga −1, SDF `9f98…`);
su repetición a pH 2 registró `O=C(O)c1ccccc1` (carga 0, SDF `c13f…`). El Δ
que mostraba la tabla confluaba el cambio de molécula con el cambio de
**especie química**.

Lo que hace viable la corrección: cada corrida **ya persiste** su microestado
en `ligand_state` (columna alimentada por `estado_del_ligando` de
`chem/conformer.py`): `protonacion.{aplicada, motor, ph}`,
`smiles_acoplado`, `carga_formal_neta`, `tautomeria.{modo, aplicada}`, más
`docking_protocol` y las columnas `receptor_sha256`/`vina_version`/
`vina_random_seed`. El dato existía; SAR no lo consultaba.

### Decisión tomada y el PORQUÉ

**Comparar CONDICIONES, no especies; abstenerse explícitamente cuando
difieren o faltan.** (Decisión de producto aprobada el 2026-10-02.)

Módulo puro `services/sar/comparabilidad.py`:

- La firma cubre el protocolo estructural (receptor, versión, semilla, motor,
  exhaustividad, poses, confórmeros, caja redondeada a 3 decimales — la
  lección del ruido de coma flotante que el preflight ya aprendió) **y la
  condición química**: protonación aplicada/no aplicada, motor, pH, modo de
  tautómero y canonicalización. Los análogos acoplan moléculas distintas por
  diseño — exigirles el mismo hash de ligando vaciaría la tabla; lo que debe
  coincidir es la REGLA de preparación.
- **`comparison_state="abstained"` con `comparison_reason` nombrando ambos
  valores** («pH de protonación: 7.4 en la base, 2 en el análogo») cuando una
  condición difiere. La abstención con motivo explícito se prefirió a la
  «comparación condicionada» con delta visible: un Δ citado sin su condición
  es un número falso; las afinidades crudas siguen visibles en sus columnas.
- **Dato faltante → abstención que nombra el lado** («falta estado químico
  del ligando… en la corrida base»). Criterio de cierre de la auditoría:
  «se abstiene cuando son diferentes o faltan». Una protonación NO aplicada
  (dimorphite ausente, forma neutra) es una condición legítima y compartida,
  no un faltante.
- **`delta_score` es siempre ausente**: el score agregado no es una magnitud
  termodinámica; restar scores de modelos no mide nada.
- La fila expone su condición química (`ph_protonacion`, `smiles_acoplado`,
  `carga_formal_neta`): la tabla puede decir «carga −1» en vez de enseñar el
  SMILES neutro que escribió el usuario mientras se acopló otra cosa.

- **Ciencia:** el sistema deja de certificar restas entre especies químicas
  distintas; la abstención viaja con su motivo, no como estado de error.
- **Calidad:** el módulo es puro y ORM-agnóstico (mismo enfoque que
  `protocolo.py`); la fila del router es una función pura testeable; el
  frontend muestra el motivo sin añadir literales fijos (el texto científico
  dinámico del backend sigue la convención de los controles del preflight).
- **Eficiencia:** la comparación son lecturas de diccionaro por fila; sin
  RDKit ni consultas extra.

**Nota de alcance:** CAS-02 (selección de cohorte por task_id) queda fuera;
la base sigue resolviéndose como hoy. El `stash@{0}` queda intacto: su
`sar.py` con la firma sin pH queda supersede por esta implementación; su
destino lo coordina el propietario con las sesiones paralelas.

### Contratos y archivos modificados

- `backend/services/sar/comparabilidad.py` (nuevo) — `Comparabilidad`,
  `comparar_corridas`, `campos_ausentes`, `condicion_quimica_publica`.
- `backend/services/sar/__init__.py` (nuevo) — paquete del servicio.
- `backend/api/routers/sar.py` — `_fila_sar` (pura) + el bucle consume
  `comparar_corridas`; filas con `comparison_state`, `comparison_reason`,
  `highlight`, condición química y `delta_score=None`.
- `frontend/components/interfaces/pro/ProSarTab.tsx` — `SarAnalog` gana
  `comparisonState`/`comparisonReason`; el mapper los conserva; la línea ✦
  se tinta ámbar en abstención y el modal muestra el motivo (`role="note"`),
  sin literales fijos nuevos.

### Pruebas de verificación

Nuevas (`backend/tests/test_comparabilidad_sar.py`, 28 pruebas):

- La reproducción de la auditoría en el contrato: pH 7,4 vs 2 abstiene y el
  motivo nombra ambos valores.
- Condición compartida → comparable; sin protonación en ambas → condición
  legítima; protonada vs neutra → abstención; `ligand_state` ausente →
  abstención que nombra el lado; modo de tautómero distinto → abstención;
  semilla distinta → abstención con ambos valores; procedencia incompleta →
  se declara lo que falta; ruido de caja `25.4` vs `25.400000000004` → la
  misma caja, sin abstención espuria.
- Los doce campos firmados, uno por caso parametrizado: cambiar cualquiera
  produce abstención (la regresión del criterio de cierre).
- Router: fila comparable con delta de afinidad; fila abstenta SIN delta y
  con la afinidad cruda visible; `delta_score` ausente en ambos casos; la
  fila expone su condición química.

Frontend (`components/__tests__/ProSarTab.test.ts`, +3): mapeo de
`comparison_state`/`comparison_reason` (abstenido, descriptivo y ausente
para respuestas viejas), y el motivo es la línea que la fila enseña.

**Resultado:** backend 28/28 verde; suite completa **3046 pasan, 2 fallan
(los mismos preexistentes del sidecar ESMFold ya verificados con
`git stash` en el Paso 1), 4 saltan**. Frontend: **122 archivos / 1119
pruebas, todas pasan**; `tsc` limpio. Registro de conteo actualizado con el
intérprete embebido (`--write`: 3016 recolectadas; `--check` verde).

---

## SOL-01 — Los receptores privados no superan el preflight desde la UI

**Severidad:** P1 (bloqueo del flujo para el propietario).
**Comprobación de auditoría:** UI y API reales (variante privada `USR_804B6F`
creada por el auditor).

### Diagnóstico

El backend protegía correctamente el target privado: la misma petición con
el token del propietario devolvía 200 con cero bloqueantes, sin token
devolvía 404 — el ocultamiento uniforme que `require_target_object_access`
promete. El defecto estaba en los **clientes del frontend**, que salían sin
credenciales, así que el dueño recibía un 404 de SU propia variante desde la
interfaz: el visor 3D se quedaba esperando coordenadas y «Comprobar
preparación» respondía «La comprobación previa no se pudo completar (HTTP
404)», culpando al motor cuando el origen era la falta de credenciales.

Verificado el 2026-10-02 con inspección completa del cliente:

- `frontend/lib/preflight.ts` (`requestPreflight`): sólo enviaba
  `Content-Type: application/json`.
- `frontend/lib/api.ts` (`getTargetPdb`): `fetch` plano sin headers.
- Ambos eran los **únicos** clientes sin sesión de todo el flujo: `request`
  (catálogo, por eso los privados SÍ aparecían en «Mis Receptores»), proApi,
  cohorts, dossier, pipelineStream y los `files/*` ya adjuntaban
  `getAuthHeaders()`. `proApi` había pasado por el mismo defecto antes
  («el único cliente de la app que no adjuntaba el token», ver
  `proApiAuth.test.ts`): quedaron los dos de arriba.

### Decisión tomada y el PORQUÉ

**Ambos clientes envían la sesión; el backend no se toca** (ya era correcto,
y la auditoría lo acreditó con sus sondas con y sin token).

- `getTargetPdb`: `headers: getAuthHeaders()`.
- `requestPreflight`: `headers: { "Content-Type": "application/json",
  ...getAuthHeaders() }`.
- Sin sesión, `getAuthHeaders()` devuelve `{}`: los targets públicos siguen
  siendo comprobables por cualquiera; no se inventa un token vacío ni se
  rompe el flujo anónimo.
- **Ciencia:** el dueño recupera el acceso a sus propias variantes y la
  evidencia de preparación que la API ya sabía producirle; el mensaje de
  error deja de señalar al motor.
- **Calidad:** se reusa el helper existente (`api.ts:201`, sesión en
  `moldesign_auth`) en vez de un mecanismo nuevo; el patrón es el mismo de
  los otros diez clientes autenticados.
- **Eficiencia:** nada que sacrificar; es un header en dos llamadas.

### Contratos y archivos modificados

- `frontend/lib/preflight.ts` — `requestPreflight` adjunta la sesión al
  POST `/evaluation/preflight`.
- `frontend/lib/api.ts` — `getTargetPdb` adjunta la sesión al GET
  `/targets/{pdbId}/pdb`.
- Backend: **sin cambios de código**. Se añadió la cobertura que fijaba el
  contrato del servidor.

### Pruebas de verificación

Nuevas — frontend (`frontend/lib/__tests__/authDeTargetsPrivados.test.ts`,
3 pruebas; rojo antes del fix, siguiendo el patrón de `proApiAuth.test.ts`):

- Con sesión activa en `moldesign_auth`: `requestPreflight` Y `getTargetPdb`
  envían `Authorization: Bearer <token>` — y el POST JSON no pierde su
  `Content-Type`.
- Sin sesión: ningún cliente inventa credenciales (los públicos siguen
  comprobables; se probó en rojo que antes el header simplemente no existía).

Nuevas — backend (`backend/tests/test_preflight_targets_privados.py`,
3 pruebas; fijan el contrato que la auditoría midió en vivo):

- Propietario (sesión del creador): el informe existe y declara
  `receptor.origin == "privado"`, con el ligando válido sin bloqueantes.
- Anónimo: 404.
- Usuario ajeno: el MISMO 404 que el anónimo — no distinguir «existe pero no
  es tuyo» es el ocultamiento que evita enumerar los privados de otras
  cuentas.

Durante el rojo, dos pruebas requirieron ajustar el DATO, no el contrato:
`CCO` como ligando producía un bloqueante legítimo de validación (3 átomos
pesados); se sustituyó por la aspirina, el mismo ligando de las corridas de
la auditoría.

**Resultado:** backend completo **3049 pasan, 2 fallan (los mismos
preexistentes del sidecar ESMFold), 4 saltan**; frontend **123 archivos /
1122 pruebas, todas pasan**; `tsc` exit 0; `report_test_counts.py --write`
con el intérprete embebido (3019 recolectadas) y `--check` verde.
`AGENTS.md` actualizado (3019 embebido / 3055 dev / 1122 frontend).

---

## AMP-03 — El automático y el manual preparan el sitio anti-diana de forma distinta

**Severidad:** P1 (el panel de seguridad acoplaba media cavidad con
`status: "ok"`).
**Comprobación de auditoría:** uso real — selectividad automática de 5VA1 y
4NC3 contra acción manual de hERG sobre la última corrida, con los dos
informes de preparación conservados.

### Diagnóstico

La selectividad MANUAL sobre hERG (`5VA1`) resolvía el sitio multicadena
contra el catálogo (`site_chains: ["A","B","C","D"]`); la AUTOMÁTICA en
segundo plano terminaba `status: "ok"` con `site_chains: null`, preparando
sólo la cadena A por fallback — **media cavidad**, y un número de seguridad
sobre un bolsillo que no existe, en la anti-diana cardíaca cuya razón de ser
es detectar el riesgo de QT prolongado.

Verificado el 2026-10-02 — era un defecto de CABLEADO, no de ciencia:

- `run_selectivity_panel` ya resuelve el sitio contra el catálogo cuando
  recibe `repository` (`selectivity.py:241,277`), y su docstring describe
  exactamente este fallo; `anti_target_sitio.py` es el módulo que manda: el
  catálogo es la única autoridad sobre `site_chains`.
- La ruta manual (`pro_features.py:219` y `:646`) pasa su repositorio.
- El subprocess de la ruta automática
  (`selectivity_subprocess.py::_run`) importaba `Repository` pero sólo lo
  usaba DESPUÉS, para persistir; llamaba al panel **sin `repository`** — el
  único llamador sin él de toda la base.
- Síntoma gemelo del mismo cableado: `seleccionar_anti_dianas` con
  `repository=None` degrada una anti-diana subida por el usuario a
  «desconocida», y el cociente se calcula con menos cobertura de la marcada
  sin decirlo.

### Decisión tomada y el PORQUÉ

**El subprocess abre su sesión, instancia el `Repository` y se lo entrega al
panel.** La sesión vive lo que dura el panel — igual que la sesión de la
petición en la ruta manual — y el gestor de `get_db_session` hace el
commit/rollback: sin fugas. En WAL una lectura no bloquea escritores
(`PRAGMA journal_mode=WAL` + `busy_timeout=60000` en `core/database.py`), así
que mantenerla abierta durante los acoplamientos no revive el «database is
locked» histórico. La persistencia post-hoc conserva SU sesión propia,
separada.

- **Ciencia:** la ruta automática deja de certificar seguridad sobre media
  cavidad; hERG se prepara con sus cuatro subunidades, como la manual. Y las
  anti-dianas del usuario vuelven al panel en vez de desaparecer.
- **Calidad:** paridad por construcción — ambas rutas llaman al MISMO panel
  con un repositorio vivo; no hay dos implementaciones que puedan divergir.
- **Eficiencia:** una sesión de lectura por subprocess; costo nulo frente al
  acoplamiento que ya hace.

### Contratos y archivos modificados

- `backend/services/docking/selectivity_subprocess.py` — `_run()`: sesión
  propia (`async with get_db_session()`), `Repository(db)` y
  `repository=repository` en la llamada al panel.
- Sin cambios en `selectivity.py`, `anti_target_sitio.py` ni en la ruta
  manual: el contrato del panel no se tocó.

### Pruebas de verificación

Nuevas (`backend/tests/test_paridad_sitio_anti_diana.py`, 3 pruebas):

- **Rojo primero (el defecto):** `main()` del subprocess invocado in-process
  con el panel interceptado; hoy fallaba con «el subprocess llamó al panel
  sin repositorio». Tras el fix: el panel recibe un repositorio vivo.
- **El contrato del panel (lo que la manual ya cumplía, ahora de ambas):**
  con un catálogo que declara `site_chains ["A","B","C","D"]` para 5VA1, la
  fila del resultado lleva esas cadenas y `procedencia_caja: "panel"`, y el
  acoplamiento recibió `site_chains` completos — no el fallback
  `chain="A"`.
- **La anti-diana del usuario:** con repositorio, una anti-diana subida se
  resuelve del catálogo con su umbral, no queda «desconocida».

Detalle del rojo documentado: la prueba del subprocess debió ser síncrona —
`main()` arranca su propio bucle con `asyncio.run()`, como el proceso real;
bajo `pytest.mark.asyncio` el bucle ya existía y colisionaban.

**Resultado:** 3/3 verde. Backend completo: **3052 pasan, 2 fallan (los
mismos preexistentes del sidecar ESMFold), 4 saltan**. Frontend sin cambios:
**123 archivos / 1122 pruebas, todas pasan; `tsc` exit 0**.
`report_test_counts.py --write` con el intérprete embebido (3022
recolectadas) y `--check` verde. `AGENTS.md` actualizado (3022 embebido /
3058 dev / 1122 frontend).

---

## CAS-06 / AMP-04 — El PDF heredado reventaba con contenido de ensemble

**Severidad:** P1 (una evaluación ensemble terminada no podía comunicarse
por su PDF; el botón fallaba en silencio).
**Comprobación de auditoría:** reproducción real — «Dossier PDF» sobre
ensemble-M01 y ensemble-M20 del caso de 40 corridas (HTTP 500), y vista
previa del documento heredado con un K30 y un K12 nuevos (HTTP 500). El
PDF de una corrida única sí salía; el dossier de caso de las mismas
corridas sí exportaba.

### Diagnóstico

El generador del PDF heredado (`services/blockchain/pdf_generator.py`) com-
ponía «Supuestos e incertidumbres abiertas» como **una tabla de UNA fila con
dos celdas mega**: todos los supuestos concatenados con `<br/>` en una, todas
las incertidumbres en la otra, todo dentro de `KeepTogether`
(`pdf_generator.py:546-560`). Las incertidumbres terminan con
`uncertainties.extend(scientific_warnings)`
(`evidence_summary.py:597`), así que en un ensemble entran los avisos que
el receptor repite por conformación (64 en ensemble-M01 — la duplicación de
CAS-07). ReportLab fragmenta tablas **entre filas, nunca dentro de una
fila**: una fila de 5.336 pt contra un marco de 498×745 pt no cabe en
ninguna página. La evidencia del auditor lo registra textual:
`LayoutError: Table ... 1 rows x 2 cols (tallest row 5336) ... too large on
page 3` (K12: 2.333 pt).

El fallo se propagaba en silencio a la interfaz: el botón «Dossier PDF» del
historial hacía `void downloadCertificate(...)` — el rechazo del HTTP 500
quedaba en consola y pulsar no producía nada visible
(`CaseRunHistoryModal.tsx:384`).

### Decisión tomada y el PORQUÉ

**Fragmentar el contenido en filas que ReportLab sepa partir; no recortar
nada.** Criterio de cierre de la auditoría: «La corrección no debe ocultar
incertidumbres para conseguir un PDF».

- La tabla pasa a tener **una fila por par de ítems**
  (supuesto[i], incertidumbre[i]) con `repeatRows=1`: el encabezado
  reaparece en cada página y las filas se reparten entre páginas de forma
  nativa. `KeepTogether` se conserva: tras el cambio es inofensivo — si el
  bloque no cabe en una página, ReportLab lo fragmenta; el error fatal venía
  de la fila única, no del `KeepTogether` (verificado por la prueba del
  contenido).
- El botón del historial declara el fallo: el rechazo de la descarga se
  captura y se muestra junto al botón (`role="alert"`), sin destruir el
  resultado abierto, y reintentar limpia el error. El mismo mecanismo cubre
  «Complejo 3D». Cero literales fijos nuevos: el mensaje es el del error
  capturado, el mismo patrón que ya usaba el modal para fallos de carga.
- **Ciencia:** el PDF de una corrida ensemble vuelve a existir con TODA su
  evidencia; una incertidumbre omitida por maquetación sería una asimetría
  entre lo que la corrida declaró y lo que el documento dice.
- **Calidad:** la prueba de contenido afirma los 90 avisos uno a uno en el
  texto extraído — paginar y recortar quedan diferenciados por contrato.
- **Eficiencia:** nada que sacrificar; misma cantidad de flowables.

**Interacción con CAS-07 (paso siguiente):** el PDF arreglado conserva los
avisos repetidos (completo pero ruidoso) hasta que la agrupación los
reduzca. La paginación estructural es necesaria de todos modos: el contenido
largo puede venir de preguntas extensas, contextos o series grandes, no sólo
de la duplicación de avisos.

### Contratos y archivos modificados

- `backend/services/blockchain/pdf_generator.py` — la sección «Supuestos e
  incertidumbres abiertas»: una fila por par de ítems, `repeatRows=1`.
- `frontend/components/cases/CaseRunHistoryModal.tsx` — `RunDetail` captura
  el rechazo de ambas descargas y lo muestra (`role="alert"`); reintento
  limpia.
- El dossier de caso (`services/dossier/`) no se tocó: no tiene esta
  estructura y ya exportaba bien.

### Pruebas de verificación

Nuevas — backend (`backend/tests/test_pdf_paginacion_ensemble.py`, 4
pruebas):

- **Rojo primero:** 90 avisos —más que los 64 medidos por la auditoría—
  mataban la composición con el mismo `LayoutError` de la evidencia; tras el
  cambio, PDF válido (`%PDF`, no vacío). El caso pequeño (pocos avisos, el
  que ya funcionaba) sigue igual.
- **Preservación del contenido** (con pypdf, `skipif` — no viaja en el
  bundle, el patrón del repo): cada uno de los 90 avisos aparece en el texto
  extraído, con el espacio normalizado porque el ajuste de línea de la celda
  parte los avisos; el documento crece a varias páginas y conserva el
  título de la sección.

Nuevas — frontend (`CaseRunHistoryModal.test.tsx`, +3): el PDF que el
servidor no puede componer declara su error junto al botón sin perder el
resultado abierto; reintentar limpia el error anterior; el complejo 3D
fallido también se declara. Rojo antes del fix: «Unable to find
role='alert'» — el rechazo vivía en la consola.

**Resultado:** backend completo **3056 pasan, 2 fallan (los mismos
preexistentes del sidecar ESMFold), 4 saltan** (46/46 en las familias PDF).
Frontend: **123 archivos / 1125 pruebas, todas pasan**; `tsc` exit 0.
`report_test_counts.py --write` con el intérprete embebido (3026
recolectadas; `--check` verde). `AGENTS.md` actualizado (3026 embebido /
3062 dev / 1125 frontend).

---

## CAS-07 — Las reservas del receptor repetidas 30 veces en ensemble

**Severidad:** P2 (sobrecarga de lectura e hinchado del bloque de
incertidumbres; alimentaba el fallo de PDF de CAS-06).
**Comprobación de auditoría:** medición real sobre el caso de 40 corridas —
ensemble-M01 conservaba **64 avisos** (30 `RECEPTOR_PROTONACION_DECLARADA`,
30 `SITIO_DESOLVATADO`, 4 propios del ensemble) donde la misma molécula en
corrida única tenía cinco.

### Diagnóstico

El punto de duplicación verificado: `services/docking/ensemble.py`, en la
fusión de miembros — `avisos.extend(normalizar_avisos(...))` por cada
conformación (línea 234). El receptor que acopla el ensemble es el mismo
para las K conformaciones, así que cada una arrastra una copia idéntica de
sus reservas. No son 30 receptores ni 30 decisiones: es una, repetida por
el mecanismo de fusión.

### Decisión tomada y el PORQUÉ

**Agrupar las reservas idénticas del sistema con su recuento, preservando
las incidencias particulares.** Nueva función pura
`agrupar_avisos_repetidos(avisos, acopladas)` en `ensemble.py`, aplicada al
fusionar:

- Un aviso estructurado (código/severidad/mensaje idénticos) repetido en
  TODAS las conformaciones que acoplaron se emite una vez con
  «(Aviso idéntico en las N conformaciones que acoplaron.)».
- Repetido en algunas: «(Repetido en n de N conformaciones.)» — el recuento
  parcial también se dice.
- Lo que no es repetición — un aviso exclusivo de una conformación, un
  fallo de acoplamiento, el resumen del ensemble — viaja tal cual.
- Los avisos en cadena (los fallos y el resumen, históricamente texto
  suelto) pasan intactos: agruparlos exigiría adivinarles un código que
  nadie declaró — y respeta el contrato de `CODIGOS_DE_AVISO` (B-5) sin
  añadir códigos nuevos.

- **Ciencia:** el recuento es información — «la misma decisión del
  receptor, 30 veces» dice algo que 30 copias ocultaban; la severidad y el
  contenido originales se conservan íntegros en el único aviso.
- **Calidad:** función pura inyectada en el punto exacto de la duplicación;
  cero cambios en consumidores (la anotación viaja en el `mensaje`, que el
  PDF, el dossier y la pestaña de alertas ya muestran) y cero cambios de
  contrato en las suites existentes del ensemble (verificado: 46/46).
- **Eficiencia:** el bloque de incertidumbres del PDF baja de 64 avisos a
  ~6 para un K=30 — menos páginas, misma evidencia.

**Interacción con CAS-06:** la paginación estructural del PDF (paso previo)
sigue siendo necesaria para contenido largo de otra índole; esta
agrupación reduce la fuente principal de ruido que la disparaba.

### Contratos y archivos modificados

- `backend/services/docking/ensemble.py` — `agrupar_avisos_repetidos`
  (pura, exportada para pruebas) + aplicación en `run_ensemble_docking`
  después de contar las conformaciones que acoplaron y antes del resumen.
- Sin cambios en frontend ni en consumidores de avisos.

### Pruebas de verificación

Nuevas (`backend/tests/test_ensemble_agrupa_avisos.py`, 5 pruebas, rojo
antes del fix — 30 copias, sin recuentos):

- **La reproducción de la auditoría:** 30 conformaciones con las dos
  reservas del receptor → UNA copia de cada una con «Aviso idéntico en las
  30 conformaciones que acoplaron» (antes: 60 avisos).
- El aviso exclusivo de una conformación viaja una vez, SIN recuento.
- El repetido en 5 de 30 declara el recuento parcial.
- El fallo particular de una conformación (cadena) viaja tal cual, y las
  reservas del sistema hablan de las que SÍ acoplaron (denominador honesto:
  4 de 5).
- El resumen «Ensemble conformacional: …» viaja único y sin anotar.

**Resultado:** 5/5 verde; familias de ensemble existentes 46/46 (contratos
previos intactos). Backend completo: **3061 pasan, 2 fallan (los mismos
preexistentes del sidecar ESMFold), 4 saltan**. Frontend sin cambios:
**123 archivos / 1125 pruebas, todas pasan; `tsc` exit 0**.
`report_test_counts.py --write` con el intérprete embebido (3031
recolectadas) y `--check` verde. `AGENTS.md` actualizado (3031 embebido /
3067 dev / 1125 frontend).

---

## AMP-01 — Se pierde una disposición científica al editar inputs

**Severidad:** P1 (trazabilidad de la decisión humana).
**Comprobación de auditoría:** reproducción real — guardar «Aceptar con
límites» con justificación, exportar el dossier, editar el SMILES y
restaurar el original: la disposición dejaba de existir en el caso
persistido, aunque los mismos seis IDs de corrida permanecían. El PDF ya
exportado la conservaba; el caso no permitía reconstruirla.

### Diagnóstico

Mecanismo verificado en `frontend/context/CaseContext.tsx::setInputs`
(línea 553): al invalidar los inputs, el destructuring retiraba el
`preflight` **y también la `disposition`** — la decisión científica con su
justificación, su huella y su fecha se borraba de `case.json`. El comentario
del propio código decía que «la corrida guardada NO se toca — sigue siendo
historia del caso»; la disposición no gozaba de la misma protección, y la
frase de la interfaz («la justificación queda guardada junto a la huella de
inputs») no se cumplía como historial durable.

### Decisión tomada y el PORQUÉ

**Historial durable por huella: al invalidar se RETIRA la vigente, no se
BORRA la decisión.** (Propuesta de la propia auditoría: «conservar
decisiones por task/fingerprint con fecha, y cambiar la vigencia de la
decisión actual».)

- `CaseRecord` gana `dispositions`: el historial completo, cada entrada con
  `kind`, `rationale`, `fingerprint` y `at`. Campo aditivo y opcional — sin
  bump de versión de esquema: los casos viejos cargan igual.
- `setDisposition` añade la decisión al historial además de fijarla como
  vigente.
- `setInputs` (invalidación) retira la vigente — describiría otra hipótesis
  y el caso pasa a `review`, como antes — pero la decisión queda en el
  historial, en disco. El caso permite reconstruirla.
- **Sin restauración automática:** si el investigador vuelve a la huella
  original, la decisión anterior es visible pero es ÉL quien vuelve a
  decidir — reactivar una conclusión sin que nadie la reafirme sería el
  mismo cambio de estado silencioso que el producto evita.
- El panel enseña las retiradas («Disposiciones anteriores de este caso»),
  con su justificación y fecha: la decisión es legible en el caso, no sólo
  en un PDF exportado antes del cambio. La proyección del dossier sigue
  llevando sólo la vigente (el PDF de su momento ya conservó cada decisión;
  ampliar el dossier a historial queda como decisión futura de producto).
- **Ciencia:** la decisión humana es evidencia; perder la justificación al
  editar una hipótesis destruía la trazabilidad de POR QUÉ se concluyó lo
  que se concluyó. Invalidar la vigencia es honesto; borrar el registro no
  lo era.
- **Calidad:** reusa la validación de `parseDisposition` por entrada (un
  historial corrupto se declara, no se recorta); i18n con clave nueva en
  es/en (`ca_disposicion_anteriores`); `tsc` estricto.
- **Eficiencia:** nada que sacrificar; es una lista en disco.

### Contratos y archivos modificados

- `frontend/lib/cases/types.ts` — `CaseRecord.dispositions` con su
  justificación de contrato.
- `frontend/lib/cases/schema.ts` — `parseDispositions` (valida cada entrada
  con el mismo criterio que la vigente) + parseo y serialización; ausencia
  y vacío no se distinguen, como todo lo demás del manifiesto.
- `frontend/context/CaseContext.tsx` — `setDisposition` añade al historial;
  `setInputs` retira la vigente y su comentario dice la verdad nueva.
- `frontend/components/cases/CaseDispositionPanel.tsx` — prop
  `dispositions`; sección de retiradas.
- `frontend/components/cases/CaseWorkspace.tsx` — pasa el historial al
  panel.
- `frontend/context/traducciones/casos.ts` — `ca_disposicion_anteriores`
  (es/en).

### Pruebas de verificación

Nuevas — contexto (`context/__tests__/CaseInputs.test.tsx`, +3, en el hogar
de las pruebas de invalidación; rojo antes del fix — la decisión
desaparecía):

- **La reproducción de la auditoría:** con disposición vigente «Aceptar
  con límites», editar el ligando retira la vigente (y el caso pasa a
  `review`) pero la decisión con su justificación y su huella queda en el
  historial — y en DISCO (`repository.readCase`), no sólo en memoria.
- Re-decidir añade al historial, no lo sobrescribe: dos entradas
  cronológicas, la vigente es la nueva.
- El historial sobrevive a cerrar y reabrir el caso (el roundtrip completo
  del esquema).

Nuevas — panel (`CaseDispositionPanel.test.tsx`, +3): la retirada es
visible y distinta de la vigente; sin vigente todo el historial es
anterior; sin historial la sección no aparece.

**Incidencia del propio paso, reportada:** al crear el archivo de pruebas
del panel se sobrescribió SIN advertirlo un archivo que ya existía en HEAD
(desde el commit del MVP) con 2 pruebas del contrato básico del panel. Se
detectó porque la aritmética de la suite no cerraba (1129 vs 1131
esperadas), se recuperaron de `git show` y se FUSIONARON con las nuevas (5
pruebas totales, todas verdes). Lección aplicada: verificar con
`git ls-files` antes de escribir un archivo «nuevo» en una ruta de pruebas
poblada.

**Resultado:** frontend **123 archivos / 1131 pruebas, todas pasan**
(1129 tras el error de sobrescritura, 1131 con las originales
recuperadas); `tsc` exit 0. Backend sin cambios: **3061 pasan, 2 fallan
(los mismos preexistentes del sidecar ESMFold), 4 saltan**; registro
`--write`/`--check` verde (3031 embebido, sin variación). `AGENTS.md`
actualizado (frontend 1131).

---

## SOL-03 — «CALIBRACIÓN Listo» sobre un receptor sin calibración medida

**Severidad:** P1 (confianza comunicada por encima de la evidencia).
**Comprobación de auditoría:** catálogo real y selector real — 3F75 con
badge verde «CALIBRACIÓN — Listo» mientras su objeto `calibracion` decía
`nivel: "curado_estructural"`, `spearman_rho: null`,
`requiere_advertencia: true` («Curado estructuralmente; sin calibrar y sin
pipeline de familia»).

### Diagnóstico

Verificado el 2026-10-02 — una inversión semántica de tres capas:

1. **El campo mide otra cosa bajo el nombre correcto.** `calibration_status`
   (`core/models.py:1586-1608`) se deriva de `is_prepared + grid_calibrated +
   hotspots`: readiness ESTRUCTURAL puro. Su propio docstring lo dice
   («estado de calibración del grid/hotspots»).
2. **El badge lo comunica como respaldo predictivo.**
   `TargetSelectorModal.tsx` lo rotulaba «CALIBRACIÓN» con «Listo» en
   verde. El tooltip del propio badge describía criterios estructurales
   («grid box calibrado y N residuos…»): el texto decía la verdad, el
   rótulo mentía.
3. **La verdad ya viajaba y nadie la leía.** `/targets` sirve el objeto
   real (`targets.py:261` → `estado_de_calibracion(t).to_dict()`, con
   nivel, Spearman ρ, resumen y `requiere_advertencia`); el tipo frontend
   lo declara (`Target.calibracion`) con un comentario de contrato SC-9
   que exige exactamente lo que faltaba: «la interfaz lo muestra… ausente
   se lee como “sin comprobar”, nunca como “calibrado”». Además existía el
   componente compartido para mostrarlo
   (`components/science/RespaldoDelReceptor.tsx`, usado por
   `ReproducibilityInfo` en el resultado) — el selector simplemente no lo
   consumía.

### Decisión tomada y el PORQUÉ

**Partir el badge en sus dos dimensiones reales** (criterio de cierre:
«readiness estructural y calibración predictiva se comunican con sus
condiciones y métricas respectivas»):

- El badge existente se re-rotula **«PREPARACIÓN»**: sigue con
  listo/revisar/sin_datos, que es exactamente lo que ese campo mide; su
  tooltip estructural se conserva.
- **La calibración predictiva se muestra con el componente SC-9 compartido**
  (`RespaldoDelReceptor compacto`), incrustado junto a los chips del sitio:
  nivel legible («Curado estructuralmente», «Pipeline de familia»…), el ρ
  cuando existe y el color por nivel — ámbar para `curado_estructural`,
  nunca verde. El selector y el resultado no pueden divergir: mismo
  componente, misma regla, calculada en un solo sitio en el backend.
- Los «Listo/Revisar/Sin datos» crudos pasan a claves del diccionario
  (`pn_prep_listo` y compañía, es/en).

- **Ciencia:** el lugar donde se elige el receptor deja de comunicar
  confianza predictiva que la evidencia no tiene; la preparación
  estructural (que sí está medida) y el respaldo del ranking quedan
  dichos por separado, cada uno con su condición.
- **Calidad:** cero segunda implementación — se reusa el componente SC-9
  ya probado (suite propia de 6 pruebas); i18n con claves en es/en.
- **Eficiencia:** un componente más por tarjeta del catálogo; ya existía y
  es un span.

**Frontera declarada:** `resolveTargetReadiness`
(`evaluationEvidence.ts:95`) sigue midiendo readiness estructural para
«¿puedo acoplar aquí?», semánticamente correcto para esa pregunta; el
aviso de calibración para la CORRIDA ya lo emite el control
`CALIBRACION_RECEPTOR` del preflight (siempre advertencia, SC-9).

### Contratos y archivos modificados

- `frontend/components/interfaces/pro/TargetSelectorModal.tsx` — badge
  re-rotulado a `pn_preparacion`; `calibrationLabel` devuelve claves;
  `RespaldoDelReceptor compacto` con `targetObj.calibracion`.
- `frontend/context/traducciones/paneles.ts` — `pn_preparacion`,
  `pn_prep_listo`, `pn_prep_revisar`, `pn_prep_sin_datos` (es/en).
- **Migración inducida por el trinquete i18n** (ver abajo):
  `components/OptionsPanel.tsx` y `components/ai/AISettingsModal.tsx` —
  sus «Listo» visibles pasaron a `t("pn_prep_listo")`.
- `frontend/lib/__tests__/textoPendienteDeTraducir.json` — las dos
  entradas resueltas salen del inventario (457 → 455).

### Pruebas de verificación

Nuevas (`TargetSelectorModal.test.ts`, +3, rojo antes del cambio — el
arnés de fuente-texto con que ya se prueba este componente):

- El badge estructual se rotula como preparación y YA NO usa
  `pn_calibracion` sobre `calibration_status`.
- La calibración predictiva viaja con el componente compartido SC-9
  (`<RespaldoDelReceptor calibracion={targetObj.calibracion}`).
- El estado de preparación usa claves de diccionario, no cadenas fijas.

**Incidencia del propio paso, reportada:** añadir los valores de
diccionario es: «Listo», en («Revisar», «Sin datos»…) dio clave de
traducción a DOS literales visibles «Listo» preexistentes
(`OptionsPanel`, `AISettingsModal` — estado de modelos descargados). El
trinquete i18n (`interfazSinTextoFijo`) lo detectó en la suite completa
(«expected 2 to be +0») y se resolvió con el flujo canónico: migración
con `finish-i18n-frontend.cjs --write` y regeneración del inventario. El
trinquete funcionó exactamente como fue diseñado: dar clave a castellano
visible obliga a migrarlo.

**Resultado:** frontend **123 archivos / 1134 pruebas, todas pasan**
(1131 + 3 nuevas); guardián i18n verde con inventario en 455; `tsc` exit
0. Backend sin cambios: **3061 pasan, 2 fallan (los mismos preexistentes
del sidecar ESMFold), 4 saltan**; registro `--write`/`--check` verde
(3031 embebido, sin variación). `AGENTS.md` actualizado (frontend 1134).

---

## SOL-08 / SOL-09 — Selección vacía de hotspots y guía de búsqueda inexistente

**Severidad:** P2 (pérdida de una decisión estructural explícita; texto que
promete lo que el motor no hace).
**Comprobación de auditoría:** UI y API reales («Desmarcar todos» + Aplicar
+ comprobar → 15 hotspots del catálogo como efectivos), inspección del
comando real de Vina (sin restraints ni mapas derivados de hotspots).

### Diagnóstico

**SOL-08:** la UI ya distingue las dos decisiones (`custom_hotspots: null`
cuando nunca se abrió Opciones; `[]` cuando se desmarcó todo). El backend
las colapsaba en cuatro puntos con chequeos *falsy*:
`preflight.py:1510` devolvía el catálogo ante `[]` (lo medido: 15
hotspots), `:1512` reportaba el origen como `catalogo_target` (mintiendo
sobre quién decidió), `canonical_input_document:269` firmaba `[]` igual
que la ausencia — **dos decisiones estructurales con la misma huella** — y
`runner.py:377` restauraba los hotspots base para el análisis de contactos.

**SOL-09:** dos textos atribuían a los hotspots una guía de búsqueda que
la inspección del comando de Vina no muestra: `op_hotspots_explicacion`
(«Define qué residuos del bolsillo guían la búsqueda», es/en) y la
explicación del sitio (`sitioDelReceptor.ts:327`: «…y que guían la
búsqueda»). La región la define la caja; los hotspots intervienen en caché
y análisis de contactos.

### Decisión tomada y el PORQUÉ

**`is None` en los cuatro puntos; la única mención de «guía de búsqueda»
es la negada.**

- Preflight: `custom_hotspots is not None` → la selección vacía produce
  `[]` efectivo, origen nuevo **`seleccion_vacia`** y el control
  `HOTSPOTS_EFECTIVOS` en **`pasa`** con la decisión nombrada («0 residuos
  por decisión del investigador… el análisis de contactos viajará sin
  lista»). Una elección consciente no es `no_evaluado`: se tomó, se
  registra. La ausencia (`None`) sigue heredando el catálogo — la
  distinción funciona en los dos sentidos o no funciona.
- Huella: `[]` serializa como `[]` y la ausencia como `null` — decisiones
  distintas, huellas distintas (criterio de cierre: «en UI, fingerprint,
  ejecución y dossier»).
- Runner: `is not None` → `[]` produce cero hotspots activos.
- Textos: `op_hotspots_explicacion` ahora dice «No guían la búsqueda de
  Vina: la región la define la caja. Son referencias para describir el
  sitio y analizar los contactos de las poses…» (es/en con la misma
  honestidad), y la explicación del sitio dice lo mismo.

- **Ciencia:** una decisión del investigador deja de ser revertida por un
  chequeo de lenguaje; y el producto deja de prometer que desmarcar un
  residuo cambia el espacio explorado — cuando la auditoría mostró que el
  motor nunca recibió esa instrucción.
- **Calidad:** la distinción `None`/`[]` existe en TODA la cadena, con la
  huella como notario; los textos en los dos idiomas dicen la misma cosa.
- **Eficiencia:** nada que sacrificar.

### Contratos y archivos modificados

- `backend/services/docking/preflight.py` — hotspots efectivos con `is
  None`, origen `seleccion_vacia`, control `pasa` con decisión nombrada;
  `canonical_input_document` firma `[]` ≠ `null`.
- `backend/services/pipeline/runner.py` — `is not None` en la selección de
  hotspots activos.
- `frontend/lib/sitioDelReceptor.ts` — la sección «¿Y los residuos
  marcados?» niega la guía y explica referencias + caja.
- `frontend/context/traducciones/opciones.ts` — `op_hotspots_explicacion`
  honesto en es/en.

### Pruebas de verificación

Nuevas — backend (`backend/tests/test_seleccion_vacia_de_hotspots.py`, 5
pruebas; rojo antes del fix: catálogo devuelto, huella idéntica, runner
falsy):

- **La reproducción de la auditoría:** `custom_hotspots=[]` con catálogo
  presente → `[]` efectivo, origen `seleccion_vacia`, control `pasa` con
  «decisión» en la observación (antes: los 2 del catálogo y origen
  `catalogo_target`).
- La ausencia (`None`) sigue heredando el catálogo; la selección con
  elementos no cambia.
- La huella: `[]` y `null` producen documentos y fingerprints distintos.
- El runner: source-text de `is not None` (patrón establecido).

Nuevas — frontend (+4): en `explicacionDelSitio.test.ts` (sobre el catálogo
real de 380), toda mención de «guían la búsqueda» debe estar negada y la
respuesta debe nombrar la caja o las referencias; en
`context/__tests__/textoHotspotsOpciones.test.ts` (nuevo), el valor de
`op_hotspots_explicacion` en ambos idiomas — la única mención de guía de
búsqueda es la negada — y el modal sigue pintando la clave.

Detalle del rojo documentado: la primera aserción («no contiene “guían la
búsqueda”») cazaba también la negación honesta; se corrigió a «toda mención
debe estar negada», que es el contrato real.

**Resultado:** backend **3066 pasan** (3061 + 5), los mismos 2 fallos
preexistentes del sidecar, 4 saltan. Frontend **124 archivos / 1138
pruebas, todas pasan** (1134 + 4); `tsc` exit 0. Registro: `--write`
embebido **3036** recolectadas, `--check` verde. `AGENTS.md` actualizado
(3036 embebido / 3072 dev / 1138 frontend).

---

## SOL-10 / CAS-04 — El editor declara su ejemplo y la estimación describe el protocolo vigente

**Severidad:** P2 (contradicción editor/caso en el primer recorrido;
estimación que describe otro protocolo).
**Comprobación de auditoría:** UI real — caso nuevo con aspirina visible y
botón pidiendo ligando (fue necesario vaciar y reescribir el SMILES para
desbloquear); con Ensemble K=30 la pantalla estimó 7–14 s mientras la
corrida tardó ~209 s.

### Diagnóstico

**SOL-10:** un caso nuevo inicializa el editor con aspirina SIN escribirla
en los inputs — una decisión de producto deliberada y documentada en el
código («guardar la aspirina de ejemplo como “hipótesis del usuario” sería
atribuirle una decisión que no tomó»). El defecto no era la decisión: era
que el editor NO la comunicaba. Estructura y SMILES parecían válidos
mientras «Comprobar preparación» pedía un ligando: el editor en
contradición con el caso, legible como fallo de preparación.

**CAS-04:** la estimación leía el K del sistema estructural CONGELADO en la
primera corrida (`initialRunConfiguration.pipelineConfig`, K=1) en vez del
K vigente del panel de preparación — el mismo K que el preflight va a
firmar. `ProEvaluation` ya recibía el K activo como prop (`activeConformers`,
añadida en CAS-05); el estimador simplemente no lo usaba.

### Decisión tomada y el PORQUÉ

**SOL-10 — comunicar el ejemplo, no persistirlo** (la segunda opción del
criterio de cierre de la auditoría; la primera contradiría la decisión de
producto documentada):

- `ProEvaluation` gana `ejemploEnEditor: boolean`, que el runner deriva de
  `!inputs?.ligand?.inputSmiles` — del ESTADO DEL CASO, no del editor: la
  nota se apaga sola en cuanto el ligando entra al caso, sin sincronizar
  dos estados.
- La nota (`role="status"`, ámbar, con icono) dice la verdad completa:
  «Ejemplo: lo que ves es una molécula de muestra, no la hipótesis de este
  caso. Introduce o dibuja tu ligando para que el caso lo guarde.» (es/en).

**CAS-04 — el estimador lee el K activo:** `EstimacionDeCorrida` recibe
`conformers={activeConformers}`; `conformerosCrudos`/`conformerosConfigurados`
(leían el congelado) se retiran. La estimación describe ahora el protocolo
que el preflight firmará — el criterio de cierre: «la solicitud de
estimación refleja K y el protocolo actuales».

- **Ciencia:** el investigador deja de leer una estructura como hipótesis
  del caso cuando no lo es, y deja de planificar con un tiempo que describe
  otra corrida (7–14 s contra ~209 s reales no es imprecisión: es otro
  protocolo).
- **Calidad:** una sola fuente del K vigente en toda la pantalla (la misma
  prop de CAS-05); i18n con clave es/en; la nota se autodestruye al
  persistir el ligando.
- **Eficiencia:** nada que sacrificar.

### Contratos y archivos modificados

- `frontend/components/interfaces/pro/ProEvaluation.tsx` — prop
  `ejemploEnEditor` + nota `role="status"` bajo la barra SMILES;
  `EstimacionDeCorrida conformers={activeConformers}`; retirados
  `conformerosCrudos`/`conformerosConfigurados`.
- `frontend/components/evaluation/CaseEvaluationRunner.tsx` —
  `ejemploEnEditor={!inputs?.ligand?.inputSmiles}`.
- `frontend/context/traducciones/evaluacion.ts` — `ev_editor_ejemplo`
  (es/en).

### Pruebas de verificación

Nuevas (`configuracionEfectivaPipeline.test.tsx`, +4 — el hogar del
cableado de K; rojo antes del fix):

- **CAS-04:** el estimador recibe `activeConformers` y YA NO
  `conformerosConfigurados` (source-text, patrón establecido).
- **SOL-10:** `ProEvaluation` pinta la nota con la clave de diccionario
  (source-text); el runner marca `ejemploEnEditor=true` para un caso SIN
  ligando y `false` con ligando guardado — cableado real con el arnés del
  runner y el mock de ProEvaluation, no inspección de cadenas.

**Resultado:** frontend **124 archivos / 1142 pruebas, todas pasan**
(1138 + 4); `tsc` exit 0. Backend sin cambios: **3066 pasan, 2 fallan (los
mismos preexistentes del sidecar ESMFold), 4 saltan**; registro
`--write`/`--check` verde (3036 embebido, sin variación). `AGENTS.md`
actualizado (frontend 1142).

---

## SOL-16 — Las pruebas de regresión ya no reflejan varios contratos actuales

**Severidad:** P2 (la suite no servía como gate verde).
**Comprobación de auditoría:** suites reales — 16 fallos (9 frontend + 7
backend) con revisión de cada familia.

### Diagnóstico

La auditoría contó 16 fallos. Verificado el 2026-10-02 con las corridas
completas de las Fases 1–3: **14 ya estaban resueltos por las sesiones
paralelas** — los 9 frontend (KetcherEditorInner, preflight.test,
ProSelectivityPanel ×4, interfazSinTextoFijo ×3) corren verdes en las
últimas cinco corridas completas (el trinquete i18n incluido), y 5 de los
7 backend (test_evaluation_files, test_evaluation_protein_file_access,
dos de tres de test_peptide_docking). **El alcance vivo eran 2 pruebas** —
y compartían una raíz:

**Ambos fixtures leían el disco real para los pesos de ESMFold.** En la
máquina de la auditoría no había pesos («ESMFold no se ejecutó en esta
campaña») y pasaban; en una con los pesos descargados fallan. Es la
versión de pruebas del defecto 1 de `AGENTS.md` («un test pasa según el
equipo en que corre» es un guardián que no ve):

1. `test_sonda_de_sidecar_no_cuesta::test_sin_pesos_descargados_no_se_sondea`
   parcheaba `archivos_que_faltan` del módulo sidecar (el guard) pero NO el
   de `catalogo` — y `estado_de` resuelve el suyo desde ahí. Con los pesos
   en disco, clasificaba `instalado_apagado` en vez de `no_instalado`. Su
   test hermano ya parcheaba ambos módulos «a propósito»; a éste le
   faltaba la mitad.
2. `test_peptide_docking::test_un_motor_descargable_sin_instalar…`
   quería el camino ENG-002 «no instalado → descárgalo, 8,4 GB», pero con
   los pesos presentes el sidecar clasificaba `instalado_apagado` y el
   helper intentaba **encender el motor de verdad**; el mensaje final
   hablaba de «configurar el servicio» — el sitio equivocado, por culpa
   del fixture, no del código.

**Ambas implementaciones son correctas** (verificado: `estado_de` declara
`no_instalado` con acción de descarga; el helper de péptidos sigue
ENG-002). Los fixtures eran deficientes.

### Decisión tomada y el PORQUÉ

**Sólo tests: cero cambios de implementación.**

1. Sonda: parche dual (sidecar + catalogo) con la misma lista de
   faltantes — determinista en cualquier equipo.
2. Péptidos: pesos declarados faltantes en ambos módulos +
   `sc.responde → False` — el test deja de depender del disco y de si hay
   un sidecar vivo en el puerto; ejercita el contrato real de ENG-002 con
   el motivo real («no está instalado… 8,4 GB»). `sidecar_de` es un
   singleton por motor, así que parchear la instancia alcanza al helper.
3. **Umbral del inventario 0,5 s → 1,0 s**, con la calibración medida en
   el docstring: 18 ms en la máquina original sin pesos; 511–514 ms
   estables (3 corridas) en un equipo de desarrollo con los pesos. El
   umbral de 0,5 s vivía pegado al trabajo legítimo del inventario — el
   modo de fallo real es un timeout de sonda de 2 000 ms, que 1,0 s
   detecta con margen de 2×. Sin atribuir causas componente a componente
   que no se midieron.

- **Ciencia/Calidad:** un gate que falla según el equipo en que corre no
  es un gate; con estos dos fixtures, la suite backend vuelve a ser
  **totalmente verde** (primera vez desde el inicio de esta remediación).
- **Eficiencia:** nada que sacrificar.

### Contratos y archivos modificados

- `backend/tests/test_sonda_de_sidecar_no_cuesta.py` — parche dual en
  `test_sin_pesos…`; umbral recalibrado y documentado en
  `test_el_inventario…`.
- `backend/tests/test_peptide_docking.py` — fixture determinista (pesos
  faltantes en ambos módulos + sonda falseada) en
  `test_un_motor_descargable…`.
- Sin cambios de implementación ni de frontend (los 9 fallos frontend de
  la auditoría ya estaban resueltos; verificado en cinco corridas
  completas).

### Pruebas de verificación

El rojo era el estado previo (medido en cada corrida completa de las
Fases 1–3): ambos tests fallaban en esta máquina con pesos descargados y
pasaban en máquinas limpias. Tras el fix:

- `test_sonda_de_sidecar_no_cuesta.py`: 5/5 verde (incluido el inventario
  con el umbral recalibrado).
- `test_peptide_docking.py`: 4/4 verde.
- **Suite backend completa: 3068 pasan, 0 fallan, 4 saltan** — primera
  corrida totalmente verde; los 2 fallos que venían de la auditoría
  (verificados ajenos al árbol de código con `git stash` en el Paso 1)
  cerrados en su causa real: fixtures dependientes del entorno.

**Resultado:** backend **3068 pasan, 0 fallan, 4 saltan**; registro
`--write`/`--check` verde (3036 embebido, sin variación — mismos tests,
mejores fixtures). Frontend sin cambios: **124 archivos / 1142 pruebas**
(última corrida completa, Paso 10). `AGENTS.md` sin variación numérica.

---

## SOL-15 — Textos fijos en español extraídos al catálogo i18n

**Severidad:** P2 (el idioma inglés declarado no estaba realmente
soportado). **Corregido por el propietario** (commit `29c6b33`): migración
COMPLETA de los textos fijos al catálogo, archivo por archivo, con el flujo
canónico (`finish-i18n-frontend.cjs`). El inventario de pendientes bajó de
455 a **0** cadenas; el trinquete `interfazSinTextoFijo` queda como
guardián en verde.

La parte de esta sesión: **alinear las 31 pruebas que afirmaban las
paráfrasis viejas** (6 archivos). El patrón era doble — (a) mocks de
`t()` anteriores a la migración que no traían las claves nuevas (el botón
se volvía imposible de encontrar porque el mock devolvía la clave cruda),
y (b) aserciones sobre el texto literal antiguo («Crear caso» → «Crear un
caso», «Score compuesto» → «Puntuación compuesta», «Selectividad
Anti-Target» → «Selectividad anti-diana», «Ejecutar POC» → «Ejecutar
prueba de concepto», «ex 8» → «Exhaustividad 8», «archivar» → «Archivar
(reversible)»). Incidencia propia documentada: dos pasadas con
PowerShell `Set-Content` dejaron BOM en los archivos; detectado por el
diff y eliminado. Resultado: **124 archivos / 1142 pruebas, todas pasan;
`tsc` exit 0**.

---

## SOL-05 — El estado global refleja los controles físicos

**Severidad:** P2 (cabecera, estado, incertidumbres y acción siguiente se
contradecían).
**Comprobación de auditoría:** función real `deriveEvaluationEvidence()`,
datos sintéticos — con todo lo demás en orden, `stage_status` en
`failed`/`review` mantenía el estado global en `ready` con la lista de
incertidumbres VACÍA.

### Diagnóstico

Verificado: `needsReview` no incluía `physicalValidity`, y
`uncertainties` sólo llevaba el detalle físico con `not_evaluated` — con
`failed`/`review` el fallo era invisible justo en el bloque donde el
investigador busca reservas, mientras `nextAction` sí se abstener/pedía
revisión: tres respuestas distintas a la misma pregunta.

### Decisión tomada y el PORQUÉ

**`failed`/`review` degradan el estado global a `review` y su detalle
viaja en `uncertainties`.** `failed` no va a `incomplete`: la evidencia
se produjo y se conserva (criterio de cierre) — lo que se corrige es que
el resumen deje de decir «todo en orden».

**Desviación del plan, declarada:** el plan inicial incluía
`not_evaluated` en la degradación; al escribir el rojo apareció el
contrato existente y deliberado (`evaluationEvidence.test.ts`: una
corrida ANTERIOR a la etapa de validación muestra «Evidencia disponible»
con su reserva ya listada y una acción conservadora) — eso no es
contradición: la reserva se ve. El criterio de cierre de la auditoría
nombra «fallo/revisión físicos»; se implementó eso, literal. Cambiar
`not_evaluated` habría volteado el rótulo de TODAS las corridas
históricas sin que la auditoría lo pidiera.

- **Ciencia:** el bloque de reservas es donde el investigador decide si
  continúa; un fallo físico invisible ahí es el defecto. La cabecera
  «Revisión necesaria» con el detalle visible es la semántica honesta.
- **Calidad:** estado, reservas y acción ahora cuentan UNA historia.
- **Eficiencia:** nada que sacrificar.

### Contratos y archivos modificados

- `frontend/lib/evaluationEvidence.ts` — `needsReview` incluye
  `failed`/`review` físicos; `uncertainties` lleva el detalle para todo
  estado no-aprobado.

### Pruebas de verificación

Nuevas (`evaluationEvidence.test.ts`, +3, rojo antes del fix): la sonda
de la auditoría parametrizada — `failed`/`review` → estado `review`,
etiqueta «Revisión necesaria», el detalle físico EN la lista de
incertidumbres y `nextAction` conservadora; guardia: `passed` sigue
pudiendo ser `ready` sin detalle físico en la lista, y el contrato de
`not_evaluated` (línea propia del arnés) queda explícitamente fuera del
alcance.

**Resultado:** ver abajo (cierre conjunto).

---

## SOL-07 — La caja en espacio vacío se declara

**Severidad:** P2 (una comprobación «sobre archivos reales» admitía una
búsqueda en el vacío sin advertencia).
**Comprobación de auditoría:** API real — centro `(9999, 9999, 9999)` Å,
tamaño `(5, 5, 5)` Å contra `3F75`: 200, cero bloqueantes,
`GRID_EFECTIVO=pasa`.

### Diagnóstico

`GRID_EFECTIVO` valida límites numéricos (lados 5-80, centro ±10000),
nunca PERTINENCIA. La estructura del receptor SÍ está disponible en ese
punto (`filtered_text`, el PDB filtrado de la ruta real) y el centro del
sitio del catálogo también — nadie los comparaba con la caja.

### Decisión tomada y el PORQUÉ

**Medir la relación geométrica y declararla; no bloquear.** Helper puro
`_geometria_caja_receptor`: extensión del receptor (min/max por eje del
PDB filtrado, columnas fijas del formato) y separación euclídea entre la
caja efectiva y esa extensión. Control nuevo `CAJA_VS_RECEPTOR`:

- `pasa`: la caja abarca volumen con átomos del receptor.
- `advertencia`: separación medida en Å, extensión del receptor,
  distancia al centro del sitio declarado cuando el catálogo lo trae, y
  el registro explícito: «la búsqueda ocurrirá en espacio vacío salvo que
  buscar lejos del receptor sea tu intención; queda registrado aquí».
- `no_evaluado`: sin estructura o sin coordenadas interpretables — no
  se inventa la comprobación.

`GRID_EFECTIVO` queda intacto (valida rangos; contrato estable). **Por
qué advertencia y no bloqueo:** la propia auditoría dice que una caja
fuera del bolsillo «puede ser intencional en exploración», y el preflight
del producto informa mientras el investigador decide — la misma filosofía
que SOL-08. Bloquear castigaría la exploración deliberada; lo que no
puede ser invisible es la condición.

- **Ciencia:** un score obtenido en el vacío no describe ningún bolsillo;
  el investigador tiene que poder ver esa condición ANTES de gastar el
  minuto de cómputo.
- **Calidad:** la distancia sale del PDB de la ruta real (la misma
  convención que lee la preparación), no de una segunda implementación.
- **Eficiencia:** un parseo O(n) sobre el texto ya en memoria.

### Contratos y archivos modificados

- `backend/services/docking/preflight.py` — `_geometria_caja_receptor`
  (pura) + control `CAJA_VS_RECEPTOR` en `_effective_configuration`, con
  la distancia al sitio del catálogo cuando existe.

### Pruebas de verificación

Nuevas (`backend/tests/test_caja_vs_receptor.py`, 7, rojo antes del fix —
el control no existía):

- **La reproducción de la auditoría:** caja `(9999,9999,9999)`/(5,5,5)
  contra un receptor en el origen → `advertencia` con la distancia
  medida; `GRID_EFECTIVO` sigue en `pasa` (el rango era válido; la
  pertinencia es otro eje).
- Caja que abarca el receptor → `pasa`; borde a borde → `pasa`, y 0.9 Å
  más allá → `advertencia` (la frontera no es caprichosa).
- Sin estructura y PDB sin coordenadas → `no_evaluado`, no error.
- La distancia al sitio del catálogo aparece cuando el receptor lo
  declara.
- La advertencia NO bloquea la corrida (exploración intencional).

Incidencia propia documentada: el primer fixture del test de borde estaba
mal calculado (la caja «solapante» no solapaba en Y) — el código daba la
respuesta correcta; se corrigió el fixture, no el código.

**Resultado (cierre conjunto SOL-05/SOL-07):** backend **3075 pasan, 0
fallan, 4 saltan** (54/54 en las familias de preflight). Frontend:
**124 archivos / 1145 pruebas, todas pasan** (`tsc` exit 0; 4 corridas
completas consecutivas verdes — un fallo intermitente de CaseWorkspace
apareció 2 veces bajo carga plena y no se reprodujo aislado ni en las
últimas 4 corridas; es ajeno a este cambio y queda registrado).
Registro: `--write` embebido **3043**, `--check` verde. `AGENTS.md`
actualizado (3043 embebido / 3079 dev / 1145 frontend).












---

## SOL-11 — El export pedía recursos RSC inexistentes (smoke 14/15)

**Severidad:** P2. **Comprobación de auditoría:** smoke oficial repetido y UI
exploratoria contra el export servido.

### Diagnóstico

El smoke de la auditoría falló en «sin errores de consola inesperados» con
404 en `/preparacion/__next.preparacion.__PAGE__.txt` y
`/molcy/__next.molcy.__PAGE__.txt`. Verificado el 2026-10-03 con una build
fresca (`npm run build:desktop`):

- **El defecto no se reproduce con el pipeline actual.** Next 16 exporta los
  segmentos RSC anidados (`<ruta>/__next.<ruta>/__PAGE__.txt`) y el navegador
  pide la forma plana (`<ruta>/__next.<ruta>.__PAGE__.txt`). Eso lo resuelve
  `scripts/normalize-next-rsc-export.mjs`, enganchado como `postbuild`, y con
  su salida las 11 rutas tienen su segmento plano; el smoke da 15/15.
- **Lo que sí reprodujo el fallo exacto de la auditoría:** retirar de `out/`
  un segmento plano (`out/molcy/__next.molcy.__PAGE__.txt`). El smoke da
  entonces 14/16 con los mismos 404. Es decir: la auditoría midió un `out/`
  sin normalizar (construido sin pasar por `postbuild`), no el artefacto que
  entrega `build:desktop`.
- **El defecto real que sí existía en la guardia:** el smoke sólo cargaba la
  portada y su único detector era «errores de consola», que se pierde en el
  ruido y no nombra el recurso. Un segmento ausente en una ruta que la
  portada no enlaza no se habría visto nunca.

### Decisión tomada y el PORQUÉ

**No se toca el normalizador; se endurece la guardia.**

- **Ciencia/Calidad:** «lo que se verifica tiene que ser lo que se entrega»
  (restricción 1). La guardia pasa a recorrer TODAS las rutas exportadas y a
  fallar nombrando cada recurso del propio origen que devuelva 404, en vez de
  depender de un mensaje genérico de consola.
- **Eficiencia:** ~1,5 s por ruta (11 rutas); sin impacto en la build.

### Contratos y archivos modificados

- `frontend/scripts/smoke-produccion.mjs` — `rutasExportadas()` (descubre las
  rutas desde `out/`, sin `_next`, `404` ni `_not-found`), registro de
  respuestas 404 del origen del export y la comprobación «el export no pide
  recursos inexistentes (N rutas recorridas)», que lista los recursos.

### Pruebas de verificación

El guardián demuestra que ve (restricción 2):

- Export completo: **16/16** (11 rutas recorridas, cero 404).
- Con `out/molcy/__next.molcy.__PAGE__.txt` retirado: **14/16**, y la nueva
  comprobación nombra `/molcy/__next.molcy.__PAGE__.txt`. El archivo se
  restituyó después.
- Sin cambios en las suites de frontend ni de backend.

---

## SOL-12 — Violación de CSP al cargar WASM embebido (`data:`)

**Severidad:** P2. **Comprobación de auditoría:** navegador con la CSP de
producción. **Decisión del propietario (2026-10-03): ruido aceptado; la CSP no
se relaja.**

### Diagnóstico

La auditoría no pudo atribuir el error («un chunk empaquetado»). Medido el
2026-10-03 abriendo un caso en el export servido con la CSP de
`tauri.conf.prod.json`:

- La conexión denegada es a `data:application/octet-stream;base64,AGFzbQ…`,
  y **no pertenece a Ketcher** sino a `public/molstar.js` (el visor 3D, Mol*
  5.9): lleva embebido un módulo Emscripten de ~700 KB cuyas exportaciones
  son `mp4v2` (codificador de vídeo MP4). Al iniciarse hace
  `fetch(<data: URI>)`; `connect-src` no admite `data:` y lo bloquea.
- **Es ruido, no una degradación:** el cargador de Emscripten cae a la
  decodificación síncrona de la misma URI. El editor de Ketcher dibuja, el
  visor carga y la corrida funciona. El codificador MP4 es una función de
  exportación de vídeo de Mol* que MolDesign no usa.
- Descartado con medida: cambiar Ketcher a `ketcher-standalone/dist/binaryWasm`
  (WASM como archivo propio). Se probó, el export dejó de embeber el WASM de
  Indigo, y la violación seguía igual porque venía de Mol*. Se revirtió.

### Decisión tomada y el PORQUÉ

**Opción 2: dejar la CSP como está y declarar el ruido.**

- **Ciencia/Calidad:** relajar `connect-src` (añadir `data:`) amplía la
  superficie de la política para silenciar un `fetch` cuyo resultado el
  código ya obtiene por otra vía. Con el fallo inofensivo y medido, la CSP
  estricta vale más que una consola limpia.
- **Qué no se afirma:** que el fallback funcione igual en WebView2 no está
  medido (la auditoría tampoco lo midió); sólo se verificó en Chrome.
- **Si cambia la decisión:** las alternativas evaluadas fueron `data:` en
  `connect-src` (cuatro sitios: `tauri.conf.json`, `.prod.json`, `.msix.json`
  y `proxy.ts`, más `check-prod-csp.js`) o parchear `molstar.js` para retirar
  el codificador MP4.

### Contratos y archivos modificados

Ninguno. El smoke sigue comprobando la violación de CSP sólo al cargar la
portada (donde el visor 3D no se monta), así que la violación documentada no
lo hace fallar; si algún día se añade al smoke el recorrido de un caso, esta
violación tendrá que declararse allí.

---

## SOL-06 — «Reproducibilidad técnica completa» sólo exigía tres campos

**Severidad:** P2 (honestidad del indicador). **Comprobación de auditoría:**
función real con datos sintéticos y etiqueta observada en la UI («COMPLETA —
3/3 trazas: versión del motor, semilla y parser»).

### Diagnóstico

La regla estaba duplicada, idéntica, en tres sitios:

- `frontend/lib/evaluationEvidence.ts` (matriz de la interfaz, «Completa»).
- `backend/services/blockchain/evidence_summary.py` (PDF heredado y
  `dimensions` del dossier, «COMPLETA»).
- `backend/services/dossier/model.py` (control `TRAZA_REPRODUCIBILIDAD`).

Contaba `vina_version`, semilla y `parsing_source`. Un resultado sin caja,
sin hashes, sin entradas ejecutadas y sin preparación alcanzaba «Completa» y,
con ello, el resumen «parámetros suficientes para revisión y reproducción
técnica» (el estado global quedaba en «ready» sólo por esas tres trazas).

Lo que sí existe para reconstruir una corrida lo mide la corrida misma en
`docking_protocol.execution_provenance` (caja efectiva, hashes de receptor,
entradas y salidas, versión de la aplicación), además de `ligand_state`.

### Decisión tomada y el PORQUÉ

**Tres escalones que no se confunden** (criterio de cierre de la auditoría:
«trazas mínimas presentes, archivos verificables y reconstrucción demostrada»):

1. **Trazas mínimas** (3): motor, semilla, parser.
2. **Elementos de reconstrucción registrados** (7): caja efectiva, protocolo
   de búsqueda (exhaustividad y poses), hash del receptor, hashes de entrada
   del ligando (SDF y PDBQT), hashes de salida (poses y registro),
   preparación del ligando (SMILES acoplado y protonación) y versión de la
   aplicación.
3. **Reconstrucción demostrada**: que un tercero reproduzca el paquete. Una
   corrida no puede afirmarlo; sólo una prueba de transferencia (`FEP-06`).
   La fila lo dice siempre: «Reconstrucción por un tercero: no demostrada».

- La fila se rotula **«Registrada»** (no «Completa») con 3/3 + 7/7; **«Parcial»**
  con cualquier carencia, y el detalle **nombra lo que falta**;
  «Insuficiente» sólo si no hay ni trazas ni elementos.
- El estado global pasa a **«review»** si falta cualquier elemento (antes
  bastaban tres trazas para «ready»), con la reserva «Faltan elementos para
  reconstruir la corrida: …» en la lista de incertidumbres. El resumen de
  «ready» ya no promete reproducción: dice que se conservan «los elementos
  registrados para intentar reconstruirla» y que la reconstrucción por un
  tercero no está demostrada.
- **Ciencia:** un indicador de completitud sólo puede afirmar lo que
  comprobó; tres metadatos no demuestran un paquete reproducible.
- **Calidad:** una sola lista de elementos, espejada con las mismas
  etiquetas en backend y frontend; el control de dossier
  `TRAZA_REPRODUCIBILIDAD` no se toca porque ya habla de **presencia** de los
  tres campos (no de completitud).
- **Consecuencia deliberada:** las corridas anteriores a los campos de
  procedencia (o de rutas que no los miden, como péptidos) pasan de «ready» a
  «review». Es la abstención correcta: no se reconstruye lo que no se midió.

### Contratos y archivos modificados

- `backend/services/blockchain/evidence_summary.py` — `TRAZAS_MINIMAS`,
  `_elementos_de_reconstruccion`; dimensión `reproducibility`, estado global,
  resumen, incertidumbres y `reproducibility.reconstruction`
  (`present_count`, `total_count`, `missing`, `demonstrated: false`).
- `frontend/lib/evaluationEvidence.ts` — espejo (`ELEMENTOS_DE_RECONSTRUCCION`,
  `reproducibility.reconstruction`); `frontend/lib/types.ts` —
  `DockingProtocol.execution_provenance`.

### Pruebas de verificación

- Backend (`test_evidence_summary.py`, +10): tres trazas sin nada más →
  «PARCIAL» y nombra lo que falta; resumen sin «suficientes para»; todo
  registrado → «REGISTRADA» con «no demostrada»; cada elemento ausente, uno
  por caso, produce «PARCIAL» que lo nombra; sin protocolo o sin preparación;
  sin nada → «INSUFICIENTE». El fixture base se enriqueció a corrida reciente.
- Frontend (`evaluationEvidence.test.ts`, +9): las mismas propiedades. Rojo
  verificado contra la implementación anterior: **9 fallos** (medido
  restituyendo el `HEAD` del archivo).

---

## AMP-11 — El dossier debe distinguir receptor declarado y unidad acoplada

**Severidad:** P2. **Comprobación de auditoría:** dossier nuevo sobre 3F75: el
PDF imprimía «3F75 · cadena A» y la preparación registraba A+P.

### Diagnóstico

«Receptor declarado» viene de la proyección del caso: lo que se pidió. Para
la unidad realmente acoplada no había campo propio: la corrida sólo guardaba
`receptor_prep.chain` (la pedida) y `site_chains`; las cadenas del PDBQT se
medían únicamente en el preflight. Quien recibe el PDF sin conocer la sesión
no podía saber que A se acopló junto a P.

### Decisión tomada y el PORQUÉ

**Medir en la corrida y mostrar las dos identidades.**

- `vina_service` mide `prepared_receptor_chains` sobre `receptor_content`, los
  **mismos bytes** que producen `receptor_sha256`, y lo guarda en
  `execution_provenance.receptor_prep.prepared_chains` (unidad acoplada,
  distinta de `chain`, que es lo pedido).
- El dossier añade «Receptor acoplado (unidad preparada)» junto al declarado:
  `3F75 · cadenas A+P — el caso declaró la cadena A; el PDBQT acoplado
  contiene A+P (medido sobre los bytes del PDBQT hasheado)`. Si coinciden no
  se inventa una discrepancia.
- **Corridas anteriores a la medida:** el campo queda `NO_DISPONIBLE` con la
  razón «la cadena declarada por el caso no prueba contra cuáles se acopló».
  No se reconstruye la unidad a partir de la petición.
- **Ciencia:** la identidad del sistema acoplado es evidencia medida, no
  declaración. **Calidad:** el valor sólo se imprime con estado afirmativo
  (regla del dossier), así que el hueco nunca pasa por contenido.

### Contratos y archivos modificados

- `backend/services/docking/vina_service.py` — `receptor_prep.prepared_chains`.
- `backend/services/dossier/model.py` — `_campo_unidad_acoplada` en `entradas`.

### Pruebas de verificación

Nuevas (`backend/tests/test_dossier_unidad_acoplada.py`, 8): A declarada y
A+P acoplada → se dicen las dos; coinciden → sin discrepancia inventada; la
declarada sigue apareciendo como declarada; sin medida (3 variantes) →
`NO_DISPONIBLE`; llega al PDF (pypdf); fuente: cadenas y hash salen del mismo
`receptor_content`.

---

## SOL-13 / SOL-14 — Centro de caja recortado en silencio y controles numéricos sin nombre

**Severidad:** P2. **Comprobación de auditoría:** interacción real y DOM.

### Diagnóstico

Ambos viven en el mismo componente, `NumberInput` de `ProOptionsModal.tsx`:

- **SOL-13.** Cada pulsación se recortaba al rango del campo (`Math.min(max,
  Math.max(min, v))`): teclear 150 en el centro X dejaba 100, sin mensaje. El
  rango de interfaz era centro ±100 Å y lado 5–50 Å; la ejecución (`preflight.py`,
  control `GRID_EFECTIVO`) admite centro finito hasta ±10000 Å y lados de
  5 a 80 Å. El origen de coordenadas lo fija cada estructura, así que un
  tope de interfaz más estrecho que el de ejecución desplaza la búsqueda sin
  que nadie lo decida. La auditoría no halló centros fuera de ±100 en el
  catálogo: el riesgo comprobado afecta a la edición y a estructuras del
  usuario. (El tope de 50 Å del lado no tenía justificación documentada y
  se trató igual: es la misma clase de defecto.)
- **SOL-14.** El `<label>` no estaba asociado al `<input>` (sin `id`/`htmlFor`/
  `aria-label`), los pasos se anunciaban «+» y «−», y los selectores de
  exhaustividad y poses repetían el patrón de etiqueta suelta. No hubo prueba
  con lector de pantalla; la evidencia es DOM e implementación.

### Decisión tomada y el PORQUÉ

- **Un solo juego de límites, nombrado.** `frontend/lib/limitesCaja.ts`
  (`CAJA_CENTRO_MAX_A`, `CAJA_LADO_MIN_A`, `CAJA_LADO_MAX_A`) espeja las
  constantes que `preflight.py` ahora define con esos mismos nombres y usa en
  el control. Una prueba lee el `.py` y falla si los números se separan. El
  volumen excesivo ya se advierte aparte (`search_policy`).
- **Lo tecleado vive en un borrador.** Sólo llega al estado un número dentro
  del rango. Una entrada fuera de rango o no numérica **no cambia el valor
  vigente** y se **rechaza con un mensaje** (`role="alert"`, `aria-invalid`,
  `aria-describedby`) que nombra lo tecleado, el rango y el valor que se
  conserva; el mensaje sigue visible al salir del campo hasta una entrada
  válida. «Conservar la entrada válida o informar su rechazo» (criterio de
  cierre) en vez de decidir por el usuario.
- **Nombre accesible completo.** El campo se asocia con `htmlFor`/`id`, y su
  nombre dice grupo y eje (`Centro del grid box (Å) · X`); los pasos son
  «Aumentar/Disminuir {campo}» y se deshabilitan en los límites. Los
  selectores pasan por `SelectorEtiquetado`.
- **Ciencia:** el valor que el investigador pidió es el que se ejecuta, o se le
  dice por qué no. **Calidad:** una fuente de verdad para los límites, con
  guardián de paridad. **Eficiencia:** nada que sacrificar.
- Textos en el catálogo es/en (`op_numero_*`), sin literales fijos nuevos.

### Contratos y archivos modificados

- `frontend/lib/limitesCaja.ts` (nuevo).
- `frontend/components/interfaces/pro/ProOptionsModal.tsx` — `NumberInput`
  (borrador, rechazo explícito, nombre accesible, pasos), `SelectorEtiquetado`,
  límites desde las constantes.
- `frontend/context/traducciones/opciones.ts` — `op_numero_disminuir`,
  `op_numero_aumentar`, `op_numero_fuera_de_rango`, `op_numero_no_valido`.
- `backend/services/docking/preflight.py` — `CAJA_LADO_MIN_A`,
  `CAJA_LADO_MAX_A`, `CAJA_CENTRO_MAX_A` (mismo comportamiento, sin literales).

### Pruebas de verificación

- `lib/__tests__/limitesCaja.test.ts` (5): paridad con `preflight.py`, el
  guardián ve una constante ausente, y el preflight no vuelve a literales.
- `components/interfaces/pro/__tests__/NumeroDeCaja.test.tsx` (10): 150 se
  conserva; 20000 se rechaza con mensaje y valor vigente; una entrada válida
  limpia el rechazo; el lado admite 80 y rechaza 81; nombres accesibles de
  ejes, pasos, selectores, pH y procesos; sin ruido de coma flotante. Rojo
  verificado contra el componente anterior: **9 de 9 fallan** (el décimo,
  de selectores, se añadió después).

**Resultado:** frontend **126 archivos / 1170 pruebas, todas pasan**, `tsc`
limpio; backend: preflight y caja 50/50.

---

## AMP-05 / AMP-06 — Notas del caso fuera del dossier y texto que el export rechaza

**Severidad:** P2. **Comprobación de auditoría:** uso real — siete campos de
contexto con marcadores y una pregunta de 4 366 caracteres.

### Diagnóstico

- **AMP-05.** Los siete textos guardaron sus marcadores; seis salían en el PDF.
  `context.notes` existía en `case_snapshot.json` del ZIP pero no en el modelo
  del dossier (`proposito`, `model.py`) ni en el PDF. La interfaz decía «Contexto
  libre. No entra en ningún cálculo» sin decir que viajaba en el paquete: un
  canal que sólo ve quien abre el ZIP, justo lo contrario de lo que el dossier
  pretende (lo que sale del equipo, se ve).
- **AMP-06.** El formulario aceptó y persistió 4 366 caracteres sin límite
  visible. `ContextoCientifico` admite 4 000 por texto (`max_length=4000`) y la
  actualización del dossier fallaba con HTTP 422 y un mensaje técnico en inglés
  (`String should have at most 4000 characters`), con la descarga inhabilitada
  hasta restaurar el texto. Con 3 759 el export funciona (diez páginas, sin
  desbordamiento en las inspeccionadas).

### Decisión tomada y el PORQUÉ

**AMP-05: las notas son parte del documento, y la interfaz lo dice.** La
auditoría pedía decidir explícitamente. Como las notas ya salen en el paquete,
dejarlas fuera del PDF no las hacía privadas: las hacía invisibles para quien
recibe el documento. Se hacen visibles, rotuladas como lo que son («Notas del
caso (contexto libre; no entra en ningún cálculo)»), y el campo del formulario
declara «Aparece en el dossier; no entra en ningún cálculo». Se imprimen sólo
cuando existen: un hueco en un campo opcional no es información. *La
alternativa —notas privadas— es un cambio de una línea en `projectContext` de
`lib/dossier.ts` si el propietario prefiere esa política.*

**AMP-06: avisar antes, no recortar.** El formulario no impone `maxLength`
(un pegado se cortaría en silencio y se perdería texto del investigador): cuenta
desde el 90 % del límite, y por encima marca el campo (`aria-invalid`,
`role="alert"`) diciendo cuánto sobra y que el texto no se ha modificado. Antes
de enviar, `verificarLimitesDelContexto` rechaza en español, **nombrando cada
campo excedido y el exceso**, y sin tocar el caso, en lugar de esperar el 422.

- **Ciencia:** la evidencia que viaja es la evidencia que se lee; el texto del
  investigador no se altera.
- **Calidad:** una constante (`CASE_CONTEXT_MAX_CHARS`) con prueba de paridad
  contra `schemas.py`; el mismo control protege la vista previa y el paquete
  porque ambos pasan por `sendProjection`.
- **Eficiencia:** un recorrido de cadenas antes de la petición; evita un viaje
  al backend que ya se sabe que fallará.

### Contratos y archivos modificados

- `backend/services/dossier/model.py` — «Notas del caso…» en `proposito`.
- `frontend/lib/cases/types.ts` — `CASE_CONTEXT_MAX_CHARS`, `contextOverLimit`,
  pista del campo de notas.
- `frontend/lib/dossier.ts` — `verificarLimitesDelContexto`, invocada en
  `sendProjection`.
- `frontend/components/cases/CaseContextPanel.tsx` — contador y aviso.
- `frontend/context/traducciones/casos.ts` — `ca_contexto_contador`,
  `ca_contexto_excede` (es/en).

### Pruebas de verificación

- Backend (`test_dossier_notas_del_caso.py`, 3): las notas con texto aparecen
  con su rótulo; sin notas no se imprime un hueco; llegan al PDF.
- Frontend: `limiteDelContexto.test.ts` (4: paridad con `schemas.py`, guardián
  que ve, `contextOverLimit`, pista de notas); `dossier.test.ts` (+4: 4 366
  caracteres no salen y se rechazan en español con campo y exceso; el paquete
  igual; se nombran todos los campos; 4 000 exactos son válidos);
  `CaseContextPanel.test.tsx` (7: contador, aviso, sin recorte, sin
  `maxLength`, desaparece al acortar, cada texto por separado, notas).
  Rojo verificado contra el panel y el dossier anteriores: **7 fallos**.

---

## AMP-07 / AMP-08 — Dos documentos con la misma identidad y problemas de presentación del PDF

**Severidad:** P2. **Comprobación de auditoría:** los dos PDF descargados sobre
el mismo resultado único, texto y metadatos extraídos, páginas renderizadas.

### Diagnóstico

- **AMP-07.** El dossier del caso (`/evaluation/dossier/…`) y el PDF heredado de
  resultado (`/blockchain/certificate/…`) llevaban el mismo título principal,
  «DOSSIER DE EVIDENCIA COMPUTACIONAL», con contenido distinto: el dossier trae
  contexto del caso, corrida, decisiones, incertidumbres y procedencia; el
  heredado, un resultado de molécula con descriptores y gráficos, sin task ID ni
  nombre de caso y con `Title`/`Author` «(anonymous)». Los botones alternaban
  «Informe», «Dossier PDF», «Descargar certificado blockchain», «Vista previa
  del certificado» y «Reporte científico». Además, el botón «Dossier PDF» del
  historial (`CaseRunHistoryModal`) descargaba **el heredado**, no el dossier.
  «Certificado blockchain» no describía nada real: ese PDF no es un registro de
  integridad (la integridad en Solana es un POC en devnet, aparte).
- **AMP-08, pie.** En el PDF heredado, el resumen de pie (receptor largo de 3F75
  · afinidad · estado) y «Página 1 de 7» se dibujan a la misma altura; con un
  nombre largo se pisaban.
- **AMP-08, portabilidad.** El dossier usaba Helvetica y Symbol sin incrustar;
  Poppler dejó huecos en α, β, Δ y ≤. El texto sí estaba en la extracción: es un
  problema de portabilidad del documento en ese visor, no pérdida de contenido
  (no se afirma que todo visor de Windows falle).
- **Hallazgo propio, mismo archivo.** La nota de caveats del PDF heredado decía
  siempre «la versión actual no ejecuta un validador geométrico de poses en
  producción», falsa desde P0-A. El dossier y el resumen ya lo habían corregido;
  aquí quedaba la frase escrita a mano.

### Decisión tomada y el PORQUÉ

Se adopta la propuesta de la auditoría: **«Dossier de evidencia» frente a
«Informe de evaluación»**.

- **El PDF heredado pasa a ser el «INFORME DE EVALUACIÓN»**: título, propósito y
  referencias internas dicen «informe»; la portada declara qué es (resultado de
  una molécula en una corrida), que el dossier del caso es otro documento, y
  la corrida (task ID, o «no identificada» si falta) para poder cruzarlos;
  metadatos propios (`Title` «Informe de evaluación · 3F75», `Author` MolDesign,
  `Subject`). El dossier conserva su título y metadatos.
- **Rótulos por función, no por formato ni por un registro que no existe:**
  «Descargar informe de evaluación», «Ver informe de evaluación», «Informe de
  evaluación — vista previa» y, en el historial, «Descargar informe». Las claves
  se renombraron (`ev_descargar_informe`, `ev_vista_previa_informe`,
  `ca_history_informe`) para que el nombre no mienta. «Certificado blockchain»
  queda reservado a un comprobante explícito de integridad (el modal de
  certificación existente).
- **El pie se ajusta al ancho** que deja «Página N de M»: sólo se acorta, con «…»,
  la parte del receptor (la primera página la imprime completa); afinidad y
  estado no se tocan.
- **El dossier incrusta una TrueType** (Arial en Windows; DejaVu/Liberation en
  Linux), de modo que α, β, Δ, ≤, ≥, →, ± y Å se ven igual en cualquier visor.
  Si el equipo no tiene ninguna, se compone con Helvetica como antes y
  `fuente_de_texto_incrustada()` lo declara: no se inventa una fuente.
- **La nota de validez física** pasa a depender del estado real: sin evaluación
  dice que no se evaluó y que eso no habla de las poses; con veredicto remite a
  él y recuerda que superar los controles no demuestra validez experimental.
- **Ciencia:** cada documento dice qué es y qué no; una frase falsa sobre el
  validador deja de imprimirse. **Calidad:** títulos, metadatos y rótulos
  coherentes. **Eficiencia:** nada que sacrificar.
- **No se hizo** (decisión futura declarada por la auditoría): el «informe breve»
  de 1–3 páginas, ni derivar ambos documentos de un único modelo, ni ampliar
  el alcance del ZIP (hoy: la corrida seleccionada y su proyección, no las N
  corridas del caso; no se diagnostica como pérdida).

### Contratos y archivos modificados

- `backend/services/blockchain/pdf_generator.py` — título, propósito,
  identidad de la corrida, metadatos, `_ajustar_a_ancho` y pie,
  `_nota_de_validez_fisica`, referencias a «informe».
- `backend/services/dossier/pdf.py` — familia TrueType incrustable
  (`_fuentes_de_texto`, `fuente_de_texto_incrustada`) en estilos y pie.
- `frontend/components/interfaces/pro/ProEvaluation.tsx`,
  `frontend/components/cases/CaseRunHistoryModal.tsx` y los catálogos
  `evaluacion.ts` y `casos.ts` (es/en) — rótulos.

### Pruebas de verificación

- `backend/tests/test_informe_vs_dossier_identidad.py` (14): títulos distintos;
  el informe dice que no es el dossier; corrida identificada o declarada
  ausente; metadatos propios sin «(anonymous)»; el pie largo se acorta sin perder
  el resto y **la caja dibujada de la izquierda no invade la de la derecha**
  (medida sobre el lienzo); el dossier incrusta TrueType y sobreviven
  α β Δ ≤ ≥ → ± Å; sin fuente del sistema se declara y el PDF se genera; la nota
  de validez física no repite la frase falsa. Rojo verificado contra los
  generadores anteriores: **14 de 14 fallan**.
- `CaseRunHistoryModal.test.tsx`: el botón se localiza por su nuevo nombre.

---

## AMP-09 / AMP-10 — Progreso de selectividad recuperado y ampliación rechazada sobre una corrida histórica

**Severidad:** P2. **Comprobación de auditoría:** uso real — panel de selectividad
reabierto tras terminar dos anti-dianas; «Reevaluar hERG» sobre una corrida que
ya no era la vigente del caso.

### Diagnóstico

- **AMP-10 (reproducido).** El backend rechaza con 409 («La corrida cambió; no se
  calcula selectividad para otra evaluación») cualquier ampliación sobre una
  evaluación que no es la vigente: la guardia es correcta y protege la proyección
  actual. El defecto está en el panel: `handleRunSingle` escribía la fila en
  «running» y, al fallar, la **sobrescribía** con `status: "failed"` y
  `affinity: null`, así que hERG pasaba a «Sin evaluar» sobre un resultado que la
  base seguía guardando; y `handleRunAll` repetía el rechazo contra cada
  anti-diana. El botón estaba habilitado sin que nada dijera que la ampliación no
  estaba disponible.
- **AMP-09 (parcialmente reproducido).** El contador `Progreso: …` tenía el
  denominador escrito a mano (`/5`) en un panel de **tres** anti-dianas
  (5VA1, 4NY4, 4NC3; la barra de al lado ya usaba `DEFAULT_ANTI_TARGETS.length`).
  Tras reabrir con dos afinidades recuperadas la pantalla decía **«2/5»**
  —medido renderizando el panel con ese estado—, declarando dos pendientes que
  no existen. **La cifra «0/0» de la auditoría no se reproduce con este código**
  (el mismo del commit auditado): con resultados recuperados el contador cuenta
  las filas con afinidad y el único defecto medido es el total. No se afirma
  haber explicado el «0/0» observado.

### Decisión tomada y el PORQUÉ

- **Un rechazo no borra evidencia.** Si la anti-diana tenía afinidad, el fallo se
  declara junto a ella («No se pudo reevaluar: … Se conserva el resultado
  anterior») y el resultado previo vuelve a la fila; sólo una anti-diana sin
  resultado previo queda «fallida» como antes. Un fallo cualquiera no guarda nada.
- **El 409 es de toda la evaluación.** `proApi` lanza ahora `ProApiError` (un
  `Error` con el mismo mensaje y además `status`); el panel lo distingue de un
  fallo de cálculo, muestra «No se puede ampliar esta evaluación. {motivo} Los
  resultados ya registrados se conservan tal como están» (`role="alert"`),
  **deshabilita** «Evaluar todo» y los botones por anti-diana, y «evaluar todo» se
  detiene en el primer 409 en lugar de repetirlo. No se puede saber antes del
  intento si la corrida es histórica (lo decide el servidor); declararlo tras
  el primer rechazo es lo honesto sin duplicar en el cliente la regla de vigencia.
- **Denominador real.** `DEFAULT_ANTI_TARGETS.length` en el contador y en la
  etiqueta de ejecución (antes `5` fijo): 2/3, 0/3.
- **Ciencia:** la evidencia registrada no desaparece de pantalla por un rechazo,
  ni el progreso exagera lo pendiente. **Calidad:** el contrato HTTP llega al
  consumidor sin cambiar a quien sólo lee `message`. **Eficiencia:** un 409 ya no
  se repite por cada anti-diana.

### Contratos y archivos modificados

- `frontend/lib/proApi.ts` — `ProApiError` (`status`); `assertOk` la lanza.
- `frontend/components/interfaces/pro/ProSelectivityPanel.tsx` — `resolverFallo`,
  estado `ampliacionNoDisponible` y `avisoDeReevaluacion`, banner, botones,
  corte del bucle en 409, denominador real.
- `frontend/context/traducciones/pro.ts` — `pr_sel_fallo_docking`,
  `pr_sel_ampliacion_no_disponible(_titulo)`, `pr_sel_reevaluacion_fallida` (es/en).

### Pruebas de verificación

- `ProSelectivityPanel.reevaluacion.test.tsx` (9): 2/3 y 0/3 (no 2/5, 0/0, 0/5);
  barra y contador con el mismo total; el 409 conserva la afinidad anterior y dice
  por qué; apaga la ampliación del panel; «evaluar todo» se detiene en el primer
  409 sin guardar nada encima; un fallo no-409 conserva el resultado sin apagar
  la ampliación; una anti-diana sin previo sigue fallida; una reevaluación
  correcta limpia el aviso. Rojo verificado contra el panel anterior: **7 de 9
  fallan** (las otras dos describen comportamiento que ya existía).
- `lib/__tests__/proApiRechazo.test.ts` (2): el 409 llega como `ProApiError` con
  `status` y el detalle del backend; sin cuerpo útil el mensaje cae al código.

**Resultado:** frontend **130 archivos / 1196 pruebas, todas pasan**, `tsc` limpio.
Backend sin cambios.

---

## CAS-01 / CAS-03 — Identificar, filtrar y comparar corridas en el historial

**Severidad:** CAS-01 P2; CAS-03 ajuste de uso. **Comprobación de auditoría:** caso de
40 corridas de la misma molécula (20 únicas y 20 ensemble), historial «Evaluaciones
anteriores».

### Diagnóstico

- **CAS-01.** La fila describía el protocolo con motor, exhaustividad y poses
  (`describeRunProtocol`) y no K, aunque `protocol.conformers` estaba guardado en
  el manifiesto. Los 20 ensembles se distinguían sólo por la marca «Otro
  protocolo», que decía *que* algo era distinto pero no *qué*.
- **CAS-03.** El historial ofrecía SMILES truncado, fecha, afinidad, estado y
  protocolo, sin filtro por modo, estado o texto. Con series repetidas, reconocer
  la corrida adecuada exigía abrir filas una a una. No se atribuye una confusión
  automática de identidad (se comprobó aparte).

### Decisión tomada y el PORQUÉ

Cambios sólo de **presentación**: el libro de corridas no se toca ni se reordena.

- **K en cada fila:** «Único K=1» / «Ensemble K=30» junto al protocolo
  (`runMode`; K>1 es ensemble). K es lo que más distingue dos corridas del mismo
  SMILES. El texto sale del catálogo es/en; el inglés usa «Ensemble (K=…)» y
  «Ensemble runs (…)» porque la guardia de idiomas rechaza cadenas idénticas a las
  del castellano.
- **Qué cambió frente al sistema inicial:** bajo «Otro protocolo», «Difiere del
  sistema inicial: K=30 (sistema: K=1)», con cada campo distinto (motor,
  exhaustividad, poses, K) y su valor de referencia (`runProtocolDifferences`).
  Sin protocolo registrado o sin sistema fijado **no se inventa** ni diferencia ni
  igualdad.
- **Filtros** (sólo con más de una corrida): modo (todas/únicas/ensembles, con su
  recuento), estado (sólo los presentes), búsqueda por SMILES o identificador de
  corrida, y «Mostrando N de M» (`filterRuns`, pura). Una corrida migrada **sin
  protocolo** no se afirma única ni ensemble: sólo aparece en «todas». Sin
  coincidencias se dice y se ofrece quitar los filtros.
- **Ciencia:** una fila deja de leerse como comparable a otra sólo porque ambas
  dicen «completada»; el protocolo se ve con su K. **Calidad:** funciones puras
  testeadas, UI accesible (`role="search"`, `aria-pressed`, `role="status"`).
  **Eficiencia:** filtrar no pide nada al backend.
- **No se hizo, por decisión de producto pendiente:** la *etiqueta de ligando que
  el usuario asigne a la corrida*. La interfaz no ofrece hoy dónde nombrar un
  ligando (`inputs.ligand.name` sólo existe por importación), así que guardar
  `ligandName` en cada corrida no tendría de dónde salir; requiere primero ese
  control. Tampoco se añadió un «informe histórico completo» nuevo: el botón
  «Descargar informe» del detalle ya conserva sus propias entradas y advertencias
  (AMP-07).

### Contratos y archivos modificados

- `frontend/lib/cases/types.ts` — `runMode`, `runProtocolDifferences`,
  `RunFilter`/`NO_RUN_FILTER`/`filterRuns`.
- `frontend/components/cases/CaseRunHistoryModal.tsx` — K en la fila, línea de
  diferencias, barra de filtros y estado vacío.
- `frontend/context/traducciones/casos.ts` — claves `ca_history_*` nuevas (es/en).

### Pruebas de verificación

- `lib/cases/__tests__/historialDeCorridas.test.ts` (13): modo único/ensemble con K;
  diferencias con los dos valores, varios campos en orden estable, y ausencia
  cuando no hay con qué comparar; filtros por modo, estado y texto, combinados, sin
  mutar el libro, y la corrida sin protocolo sólo en «todas». Libro sintético de
  42 corridas (20+20+fallida+migrada).
- `CaseRunHistoryModal.test.tsx` (+12): K y diferencias en la fila, filas iguales
  sin diferencias inventadas, filtros con recuentos, por estado, por texto, estado
  vacío, y que filtrar no pide nada al backend. Rojo verificado contra el modal
  anterior: **9 fallos**.

---

## CAS-02 — SAR no reconstruye la cohorte histórica de corridas únicas

**Severidad:** P2. **Comprobación de auditoría:** SAR sobre la primera evaluación única
tras reevaluar las mismas 20 moléculas en ensemble.

### Diagnóstico

`GET /sar/{molecule_id}` resolvía la base con `get_evaluation_result` (la
proyección más reciente de la molécula) y los análogos con `get_sar_analogs`
(también la proyección más reciente de cada molécula contra el mismo receptor,
tope 50). `evaluation_results` guarda **una fila por molécula**: al reevaluar un
ligando con otro protocolo, esa fila cambia. Tras pasar 20 moléculas de K=1 a
K=30, la tabla de la corrida única contenía los 20 ensembles: K distinto, la
comparabilidad (SOL-04/AMP-02) se abstenía en todas y quedaban **0 comparables
entre 20 filas**. No es pérdida del snapshot (`evaluation_runs` conserva cada
`task_id`) ni un delta indebido: es que la consulta no podía pedir esas corridas.

### Decisión tomada y el PORQUÉ

**La cohorte puede ser explícita; el valor por defecto no cambia.** Es lo que la
auditoría propone: «un conjunto explícito de task IDs/protocolo del caso,
conservando la abstención cuando las condiciones sean incompatibles».

- **Backend.** `task_id` (opcional): la base es lo que ESA corrida produjo.
  `cohort_task_ids` (repetible, hasta 200): los análogos son las corridas
  pedidas, leídas de sus **snapshots inmutables** con las addenda verificadas, el
  mismo mecanismo del dossier. Una cohorte pedida se **cumple entera o se
  rechaza nombrando la corrida**: desconocida o de otra molécula (404), que no
  terminó con éxito (409), de otra cuenta (403), contra otro receptor (409) o
  demasiado grande (422). Nunca se sustituye en silencio por otra. Los
  duplicados no duplican filas, y la fila base se marca por `task_id`.
- **La abstención sigue gobernando.** Una cohorte explícita no vuelve comparable
  lo que no lo es: una cohorte mixta (únicas y ensemble) abstiene en las filas
  de otro K, con su motivo, y la afinidad cruda sigue visible.
- **La respuesta declara de dónde salió la tabla:** `cohort.source`
  (`latest_projection`, que cambia al reevaluar, o `explicit_runs`, que se puede
  reconstruir), `base_task_id` y `task_ids`; cada fila lleva su `task_id`.
- **Interfaz.** Con un libro de corridas del caso, el SAR ofrece elegir entre
  «la evaluación más reciente de cada molécula» (por defecto, como siempre) y
  «las N corridas de este caso con el mismo protocolo que la que ves (K=…)»:
  terminadas, con resultado guardado y con el **mismo protocolo** (motor,
  exhaustividad, poses y K) que la de pantalla. Se declara sobre qué corridas
  se construyó la tabla, y si el servidor rechaza la cohorte el motivo se
  muestra en vez de caer a una tabla vacía muda. Sin libro, sin protocolo
  registrado en la corrida de referencia, o con menos de dos corridas, no hay
  nada que elegir y no se ofrece. Las corridas llegan por props
  (`CaseWorkspace → CaseEvaluationRunner → ProEvaluation → ProAnalysisTabs →
  ProSarTab`), de sólo lectura.
- **Ciencia:** una comparación SAR se puede reconstruir tal como se hizo, aunque
  las moléculas se reevalúen después, y sigue negándose a restar entre
  protocolos o especies distintos. **Calidad:** una sola vía de lectura de
  snapshots, compartida con el dossier. **Eficiencia:** un snapshot y una huella
  por corrida pedida, con tope.
- **No se hizo:** una cohorte «por protocolo» elegida libremente más allá de la
  del mismo protocolo que la corrida en pantalla (p. ej. cruzar a propósito
  únicas y ensembles); el backend ya lo admite con `cohort_task_ids`, la interfaz
  no lo ofrece.

### Contratos y archivos modificados

- `backend/api/routers/sar.py` — `_evaluacion_de_corrida`, `task_id` y
  `cohort_task_ids`, bloque `cohort`, `task_id` por fila, `MAX_COHORTE_EXPLICITA`.
- `frontend/lib/proApi.ts` — `getSarData(moleculeId, cohort?)`, `SarCohort`,
  `SarCohortInfo`.
- `frontend/components/interfaces/pro/ProSarTab.tsx` — `cohorteDelProtocolo`,
  selector, declaración de cohorte y aviso de rechazo.
- `frontend/components/interfaces/pro/ProAnalysisTabs.tsx`, `ProEvaluation.tsx`,
  `frontend/components/evaluation/CaseEvaluationRunner.tsx`,
  `frontend/components/cases/CaseWorkspace.tsx` — props `taskId` y `caseRuns`.
- `frontend/context/traducciones/paneles.ts` — `pn_sar_cohorte*` (es/en).

### Pruebas de verificación

- `backend/tests/test_sar_cohorte_explicita.py` (12, con SQLite real y los
  snapshots del flujo: tres moléculas únicas congeladas y reevaluadas en
  ensemble): por defecto no cambia; **la reproducción de la auditoría** (base
  única contra proyección ensemble: ningún comparable); la cohorte explícita
  reconstruye las únicas con sus afinidades originales y deltas; la de ensembles
  por separado; la cohorte mixta abstiene; corrida desconocida, fallida, ajena,
  de otro receptor, de otra molécula, demasiado grande y duplicados.
- `frontend/components/interfaces/pro/__tests__/ProSarTab.cohorte.test.tsx` (13):
  qué corridas forman la cohorte histórica (mismo protocolo, terminadas, con
  resultado, sin mezclar) y el comportamiento del selector, la declaración y el
  rechazo. `frontend/lib/__tests__/proApiSarCohorte.test.ts` (3): la consulta por
  defecto no cambia, la cohorte viaja como parámetros repetidos y codificados.

**Resultado:** backend **3122 pasan, 4 saltan** (intérprete de desarrollo), registro
embebido 3076; frontend **133 archivos / 1237 pruebas, todas pasan**, `tsc` limpio.
