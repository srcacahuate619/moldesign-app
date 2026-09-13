# 84 — El arnés de QA para una VM limpia, y los cuatro fallos falsos que corrige

**Fecha:** 2026-09-07
**Código:** `scripts/qa_vm_audit.py`, `scripts/tests/test_qa_vm_audit.py`
**Artefactos:** `qa_comprehensive_report.json`, `qa_exec.log`
**Estado:** 🟢 corregido y probado. 24 autotests verdes; comprobado además
contra el backend real de este árbol.

---

## 0. Qué pasó

Una auditoría corrió sobre una VM con Windows limpio y produjo
`qa_comprehensive_report.json` y `qa_exec.log` con fallos que no eran fallos.
Cuatro clases distintas, y ninguna decía nada sobre el producto:

| Lo que reportó | Lo que en realidad pasaba |
|---|---|
| «`/evaluation/dock` devuelve 404» | Ese endpoint **no existe** y no debe existir |
| «422 en la evaluación» | Mandaba `target` donde el esquema declara `target_pdb_id` |
| «El backend no arranca» | Arrancaba; la VM de 3 núcleos con disco emulado tardaba más que la única pregunta que el arnés hacía |
| «ESMFold falla», «6 motores fallan» | Ausencias **por diseño**: pesos que se bajan bajo demanda y motores que viven en otro proceso |

Un informe de QA que produce cuatro clases de falso positivo no es un informe
con ruido: es un informe que **no se puede leer**, porque ya no distingue lo que
está roto de lo que está bien. Y —como pasó con los dos guardianes del doc 70
§2— un guardián con falsos positivos acaba desactivado, que es la peor forma de
perderlo.

**El arnés original no está versionado.** Se buscó por nombre y por contenido
en el árbol de trabajo, en las diez ramas, en el disco `D:` entero, en las
carpetas de usuario de `C:` y en el registro persistente del proyecto. No
aparece en ninguno: los dos artefactos se generaron en la VM desde un script que
vivía sólo allí. Así que
esto no es un parche sobre aquél; es su sustituto, con los mismos dos nombres de
salida para que ocupe su lugar sin ambigüedad.

---

## 1. El flujo canónico, y por qué `submit` y no `evaluate`

```
POST /evaluation/preflight   {smiles, target_pdb_id, …}  → 200  input_fingerprint
POST /evaluation/submit      {…, preflight_fingerprint}  → 202  task_id
GET  /evaluation/status/{task_id}                        → 200  hasta SUCCESS/FAILURE
```

`/evaluation/evaluate` y `/evaluation/submit` ejecutan **el mismo pipeline** y
pasan por **las mismas puertas** (`_enforce_submission_gates`, EVAL-BE-005: dos
puertas al mismo cálculo con reglas distintas no es un atajo, es un agujero).
La diferencia que decide es otra:

> `evaluate` es un `StreamingResponse` de SSE y sólo emite `task_id[:8]`
> —`backend/api/routers/evaluation.py:357` y `:430`—. Ocho caracteres no sirven
> para `GET /evaluation/status/{task_id}`.

Sin el `task_id` completo no hay forma de correlacionar la evidencia de un fallo
con la corrida que lo produjo, que es justo lo que el punto 6 del encargo pide.
Por eso el arnés entra por `submit`. Es una consecuencia del contrato, no una
preferencia.

---

## 2. Las cuatro correcciones, y cómo cada una se sostiene sola

### 2.1 Ninguna ruta se escribe de memoria

Las seis rutas que el arnés usa están declaradas en `RUTAS_REQUERIDAS`, y antes
de llamar a ninguna se comprueban contra el **OpenAPI vivo** del backend que se
está auditando (`/openapi.json`; si no responde, `docs/api/openapi-current.json`
como respaldo declarado en el informe).

Una ruta que el contrato no declara **aborta la auditoría con código 2** y no se
llega a pedir. La distinción importa:

- **1** — el producto falló. Es un veredicto.
- **2** — el arnés no pudo auditar. **No** es un veredicto sobre el producto, y
  el informe lo dice en su campo `aborto`.

El arnés anterior no tenía esa distinción, y por eso su bug se publicó como un
404 del backend.

### 2.2 El cuerpo se deriva del esquema

`Contrato.payload_de(ruta, método, valores)` busca el esquema que el propio
OpenAPI asocia a esa ruta, y falla si:

- se envía un campo que el esquema no declara — **y dice cuáles sí valen**;
- falta un campo `required`.

Contra el contrato de hoy, `{"smiles": …, "target": "7E2Y"}` produce:

```
POST /evaluation/preflight: el esquema PreflightRequest no declara ['target'].
Propiedades válidas: [… 'smiles', 'target_pdb_id']
```

Ahí muere el segundo fallo falso, con el nombre del campo bueno en el mismo
mensaje. Un `None` no se envía: el backend distingue «sin override» de «override
nulo» al recalcular la huella, y enviar `null` cambiaría el `input_fingerprint`.

### 2.3 Readiness explícito, en dos medidas separadas

| Fase | Presupuesto | Variable de entorno |
|---|---|---|
| `readiness.health` | `--cold-start-timeout` (600 s) | `MOLDESIGN_QA_COLD_START_TIMEOUT_S` |
| `readiness.targets` | `--targets-timeout` (300 s) | `MOLDESIGN_QA_TARGETS_TIMEOUT_S` |
| `evaluation.poll` | `--eval-timeout` (1800 s) | `MOLDESIGN_QA_EVAL_TIMEOUT_S` |

Son **dos relojes**, no uno, y la razón se midió en esta máquina —6 núcleos,
SSD, sin virtualizar— corriendo el arnés contra el backend real:

```
readiness.health    3,2 s   (3 intentos: 2 conexiones rechazadas, 1 × 200)
readiness.targets  23,9 s   (1 intento, 380 receptores)
```

`/health` contesta en 3 segundos; `/targets/` tarda **ocho veces más**, porque su
primera llamada siembra el catálogo (`ensure_default_target`) y es la primera
consulta cara del proceso. Un arnés que mide «el backend está listo» con una sola
sonda no puede distinguir «tarda» de «no arrancó» — y en una VM de 3 núcleos con
disco emulado esos 23,9 s se multiplican.

**Un timeout real nunca se disfraza.** Se anota como `TIMEOUT`, hunde el
veredicto igual que un `FAIL`, y el informe conserva el presupuesto (`timeout_s`),
lo que tardó (`elapsed_s`), cuántos intentos hubo y un histograma de los códigos
vistos. Un `/health` que contesta 503 durante diez minutos no es «el backend no
arrancó», y hay que poder leer la diferencia.

`TIMEOUT` y `SKIP` son estados distintos a propósito: `SKIP` es «no se intentó»
y no hunde nada; `TIMEOUT` es «se intentó y se agotó el plazo» y sí. Confundirlos
es exactamente el error que esta auditoría existe para no repetir, y hay un test
cuyo nombre lo dice: `test_arranque_en_frio_agotado_es_timeout_y_no_skip`.

### 2.4 Las ausencias esperadas se clasifican por el contrato, no por una lista

La clasificación lee el campo `requiere` que **declara el backend**
(`inventario_de_motores`, `backend/api/routers/evaluation.py:84-193`):

| `requiere` | Si no está disponible | Por qué |
|---|---|---|
| `binario_empaquetado` | **FAIL** | El instalador lo empaqueta: Vina. Si falta, falta de verdad |
| `binario_externo` | `EXPECTED` | QuickVina 2 no viaja en esta versión |
| `servicio_externo` | `EXPECTED` | Los «Próximamente»: viven en otro proceso |
| `descarga_bajo_demanda` | `EXPECTED` | ESMFold y compañía: pesos que se bajan aparte |
| cualquier otro valor | **FAIL** | Ver abajo |

No hay ninguna lista de nombres de motor en el arnés. La consecuencia buscada es
que si mañana ESMFold se empaquetara, su ausencia pasaría a ser un fallo **sin
tocar este archivo**.

La última fila es la que impide que esto se convierta en una amnistía: un
`requiere` que el arnés no sabe leer **no se excusa**, se marca FAIL diciendo que
no puede decidir. Una clasificación que perdona lo que no entiende deja de
clasificar.

Contra el backend real de este árbol, las seis ausencias que la VM reportaba como
fallos quedan así:

```
[PASS    ] motores.vina                    disponible (listo)
[EXPECTED] motores.qvina2                  binario_externo    / no_instalado
[EXPECTED] motores.diffdock                servicio_externo   / servicio_no_instalado
[EXPECTED] motores.esmfold                 descarga_bajo_demanda / no_instalado
[EXPECTED] motores.esmfold-pro             servicio_externo   / servicio_no_instalado
[EXPECTED] motores.esmfold-experimental    servicio_externo   / servicio_no_instalado
[EXPECTED] motores.colabfold               servicio_externo   / servicio_no_instalado
```

---

## 3. Qué conserva el informe cuando algo falla

Toda fase que cae lleva un bloque `evidencia` con las cuatro cosas que hacen
falta para reproducir el fallo sin volver a la VM:

```json
{
  "request":  {"method": "POST", "path": "/evaluation/submit", "body": {"…": "el cuerpo exacto"}},
  "response": {"status": 404, "body": "…", "body_truncated": false, "transport_error": null},
  "task_id":  "…",
  "backend_log": {"path": "…/backend_20260907_120000.log", "lines_total": 812, "tail": ["…"]}
}
```

Tres detalles que no son gratis:

1. **El cuerpo de un error se lee siempre.** `urllib` lanza en 4xx/5xx y el
   cuerpo se va con la excepción si nadie lo lee; ahí es donde el arnés anterior
   perdía el detalle del 422 —que es justamente lo que dice qué campo sobraba—.
2. **La petición que lanzó la corrida viaja con el fallo del polling**
   (`submit_request`): sin ella el `task_id` no se puede reproducir.
3. **El log del backend se localiza como lo escribe el producto**:
   `backend.latest.log` no es un log, es un archivo que contiene el **nombre** del
   log vivo (`frontend/src-tauri/src/backend.rs:609-623`). Se busca en
   `MOLDESIGN_LOG_DIR`, en `<repo>/logs` y en `%TEMP%/MolDesign/logs`.

Junto al informe quedan `preflight.json`, `motores.json`, `resultado.json` y —en
modo `spawn`— el log del backend de esa corrida. **Un directorio por corrida,
nunca reutilizado**: reusar el directorio de salida ya destruyó 102 resultados en
este proyecto, así que el arnés se niega a arrancar si el `--out-dir` que le dan
ya contiene un informe. Sobrescribirlo exige `--force`, que es una decisión que
alguien toma, no un descuido.

---

## 4. Cómo se ejecuta

```bash
# Contra el backend que ya levantó la aplicación de escritorio
python scripts/qa_vm_audit.py --base-url http://127.0.0.1:53017

# Levantando el backend desde el árbol (o el runtime staged, con MOLDESIGN_GATE_BUNDLE=1)
python scripts/qa_vm_audit.py --out-dir tmp/qa-vm-manual

# Sin docking: readiness, contrato, motores y preflight
python scripts/qa_vm_audit.py --base-url http://127.0.0.1:53017 --skip-evaluation
```

Códigos de salida: **0** todo bien · **1** hay `FAIL` o `TIMEOUT` · **2** el arnés
no pudo auditar (contrato roto o entorno imposible).

---

## 5. Los autotests

`scripts/tests/test_qa_vm_audit.py`, 24 pruebas, ejecutadas con el intérprete
embebido:

```
python-embed/python.exe -m pytest scripts/tests/test_qa_vm_audit.py -q
24 passed in 13.72s
```

El backend de las pruebas es un `ThreadingHTTPServer` **de verdad**, no un
monkeypatch: así se ejercita el camino real de `urllib`, incluida la lectura del
cuerpo de un `HTTPError`. Y responde con `ensure_ascii=False` como FastAPI —la
primera versión del falso escapaba los acentos y la prueba estaba midiendo el
falso, no el arnés—.

Las cuatro respuestas que pedía el encargo, y las demás:

| Prueba | Qué fija |
|---|---|
| `test_submit_404_falla_conservando_la_evidencia` | 404 → FAIL con cuerpo, petición y log; polling en SKIP |
| `test_preflight_422_conserva_el_detalle_de_validacion` | 422 → el detalle de validación llega entero al informe |
| `test_arranque_en_frio_agotado_es_timeout_y_no_skip` | timeout → `TIMEOUT`, veredicto FAIL, posteriores SKIP |
| `test_la_corrida_que_no_termina_es_timeout_no_failure` | timeout de la corrida ≠ fallo de la corrida |
| `test_success_recorre_el_flujo_canonico` | SUCCESS → salida 0 y las seis fases en PASS |
| `test_failure_conserva_task_id_peticion_respuesta_y_log` | FAILURE → las cuatro piezas de evidencia |
| `test_el_arnes_no_conoce_evaluation_dock` | recorre el **AST**: `/evaluation/dock` sólo puede aparecer en la prosa que explica por qué no existe |
| `test_payload_rechaza_un_campo_que_el_esquema_no_declara` | `target` muere nombrando `target_pdb_id` |
| `test_el_contrato_real_del_repositorio_sostiene_el_flujo` | el payload se deriva del OpenAPI **vigente**, no de la maqueta |
| `test_un_arranque_lento_pero_bueno_no_es_un_fallo` | la muestra que **no** debe marcar: 503 tres veces y luego 200 → PASS |
| `test_un_4xx_en_el_polling_es_fail_no_timeout` | 404 en `/status` es contrato roto, no lentitud |
| `test_los_motores_ausentes_por_diseno_no_hunden_el_veredicto` | las cuatro ausencias → EXPECTED, salida 0 |
| `test_vina_ausente_si_es_un_fallo_real` | la contrapartida: lo empaquetado no se excusa |
| `test_un_requisito_desconocido_no_se_excusa` | la clasificación no es una amnistía general |
| `test_no_pisa_el_informe_de_una_auditoria_anterior` | el `--out-dir` con informe previo aborta; `--force` es explícito |

La penúltima y la antepenúltima van en pareja a propósito. Un guardián que sólo
demuestra lo que detecta no ha demostrado que sirva: hay que enseñar también lo
que **no** marca, o el día que marque de más nadie lo sabrá hasta que lo apaguen.

---

## 6. Lo que este arnés **no** demuestra

- **No corrió en la VM.** Las medidas de §2.3 son de esta máquina —6 núcleos, SSD,
  sin virtualizar—. Sirven para justificar por qué hay dos relojes y presupuestos
  configurables; **no** son la medida de la VM, y los presupuestos por defecto
  (600 s / 300 s / 1800 s) son una estimación, no un número medido allí. La
  primera corrida real en la VM debería anotar sus `elapsed_s` aquí.
- **No se ejecutó una corrida completa con Vina real** en esta verificación: la
  comprobación contra el backend real fue con `--skip-evaluation`. El camino
  `submit` → `status` → `SUCCESS` está cubierto por los autotests contra un
  backend falso, y por el gate `scripts/accept_evaluation_runtime.py`, que sí
  ejecuta Vina de verdad.
- **No sustituye a los gates de aceptación** (`accept_*_runtime.py`). Aquéllos
  prueban ciencia, persistencia y aislamiento entre cuentas; éste prueba que una
  instalación recién hecha responde el contrato y llega a un resultado.
- **No se tocó código de producto.** Esta corrección es del arnés. No se
  encontró ningún defecto del backend ni del frontend al derivar el flujo del
  OpenAPI y el código actual.

---

## 7. Referencias

- `backend/api/routers/evaluation.py` — `evaluate_sync` (:307), `submit_evaluation`
  (:651), `get_evaluation_status` (:726), `evaluation_preflight` (:936),
  `_enforce_submission_gates` (:553), `inventario_de_motores` (:84)
- `backend/services/docking/preflight.py:713` — la forma del informe de preflight
- `frontend/src-tauri/src/backend.rs:609` — dónde y cómo se escribe el log
- Doc 70 §2 — «todo guardián lleva autotest»; las dos veces que un guardián mintió
- Doc 73 §1 — `PYTHONUTF8`: sin él, el intérprete embebido lee texto corrompido
  **sin lanzar excepción**
