# MOLCHAT-AUD-00 — Expediente de auditoría de la pestaña MolChat

**Fecha:** 2026-08-30
**Plan de referencia:** [61_PLAN_CIERRE_APP_ORQUESTACION_CLAUDE.md](61_PLAN_CIERRE_APP_ORQUESTACION_CLAUDE.md) §8
**Paso del método:** 1 (AUD, sólo lectura).
**Prioridad del mandato:** validez científica → calidad → eficiencia.

La auditoría de §1-§3 se hizo en lectura pura. Los paquetes de escritura
posteriores están anotados bajo cada hallazgo con su evidencia; la tabla de §3
lleva el estado real. **Ningún gate se declara verde aquí.**

Precedentes: Evaluación ([63](63_GATE_RUNTIME_EVALUACION.md)) y Batch
([64](64_GATE_RUNTIME_BATCH.md)) tienen gate aprobado; Moldex
([65](65_MOLDEX_AUD_00_EXPEDIENTE.md)) tiene sus 16 hallazgos implementados y el
gate pendiente. MolChat hereda un hallazgo abierto desde el expediente de
Evaluación: **MOLCHAT-INT-001**.

---

## 1. Tamaño y cobertura

| Superficie | Líneas |
|---|---:|
| `services/ai/` (backend, sin tools) | ~9.000 |
| `services/ai/tools/` (9 herramientas) | ~2.500 |
| `api/routers/ai.py` | 512 |
| `services/ai/chat_service.py` (núcleo) | 2.865 |
| `context/AIContext.tsx` + `components/ai/` | 2.729 |

Cobertura existente: `test_conversation_state.py`, `test_known_molecules.py`,
`test_llama_server.py`, `test_report_context.py` en backend, y
`context/__tests__/AIContext.test.tsx` en frontend. **Ninguna prueba cubre la
autorización de los endpoints AI ni el aislamiento de conversaciones.**

## 2. Mapa real del flujo (lectura)

```
cliente ──▶ POST /ai/chat  ← ÚNICO endpoint que recibe identidad
              │              (get_current_user_optional; sin sesión → None)
              │
              ├── stream=True  ──▶ chat_service.chat(..., user_id=user_id)   ✓ pasa identidad
              └── stream=False ──▶ chat_service.chat_with_info(...)          ✗ NO pasa identidad
                                        │
                                        ▼
                        ChatService  ← singleton de proceso (get_chat_service)
                         _conversations : dict     ← atributo de CLASE
                         _active_conv_id : str     ← atributo de CLASE, mutable global
                                        │
                                        ▼
                        memory_store → tabla `conversations`
                          (conv_id, messages_json, summary,
                           molecule_context_json, created_at, updated_at)
                           ▲
                           └── SIN columna user_id

otros 20 endpoints  ──▶ SIN autenticación de ningún tipo:
  POST /ai/providers/configure   ← escribe api_key y base_url
  POST /ai/providers/active
  GET/POST/DELETE /ai/conversations…
  POST /ai/speech-to-text
  POST /ai/models/download
  PATCH /ai/settings
  POST /ai/models/open-folder    ← os.startfile / xdg-open en la máquina
```

Hechos del mapa que condicionan todo lo demás:

- **La conversación no tiene dueño en ninguna capa.** Ni el objeto, ni el
  servicio, ni la tabla, ni los endpoints.
- **El estado del chat es de proceso, no de sesión.** `_conversations` y
  `_active_conv_id` son atributos de clase sobre un singleton.
- **La configuración del proveedor es global a la máquina** y se puede
  reescribir sin autenticación.
- **No existe ninguna puerta de consentimiento** antes de enviar datos a un
  proveedor remoto: cero coincidencias de `consent`/`autoriz` en el router, el
  servicio de chat y los proveedores.

## 3. Hallazgos

Prioridad según §4 del plan. El estado de cada uno está en la última columna.

| ID | P | Eje | Dónde | Estado |
|---|---|---|---|---|
| MOLCHAT-BE-002 | P0 | Backend | `api/routers/ai.py` (20 de 21 endpoints) | ✅ **implementado** 2026-08-30 · recomprobado 2026-08-31 |
| MOLCHAT-BE-003 | P0 | Backend | `api/routers/ai.py:172-204` | ✅ **implementado** — servidor 2026-08-30, destino declarado 2026-08-31 |
| MOLCHAT-BE-004 | P0 | Backend | `chat_service.py:85-165`, `memory_store.py:331` | ✅ **implementado** 2026-08-30 · recomprobado 2026-08-31 |
| MOLCHAT-NET-005 | P0 | Transversal | `services/ai/consent.py`, `chat_service.py` | ✅ **implementado** 2026-08-31 |
| MOLCHAT-INT-001 | P1 | Intersección | `services/ai/tools/docking_tools.py:59` | ⬜ abierto — import roto reconfirmado 2026-08-31; bloqueado por D-08 |
| MOLCHAT-BE-006 | P1 | Backend | `chat_service.py:116-153` | ✅ **implementado** 2026-08-30 · recomprobado 2026-08-31 |
| MOLCHAT-INT-007 | P1 → SCI | Intersección | `api/routers/ai.py:392`, `chat_service.py:2852` | ✅ **implementado** 2026-08-31 — una sola implementación |
| MOLCHAT-BE-008 | P2 | Backend | `chat_service.py:99-107` | ⬜ abierto — `except Exception: pass` reconfirmado 2026-08-31 |

Recomprobación del 2026-08-31 (sólo lectura + regresiones existentes):
`tests/test_ai_endpoints_exigen_sesion.py` y `tests/test_conversaciones_por_cuenta.py`
→ **`17 passed`**. Los cuatro hallazgos abiertos se reconfirmaron en el código, no por
suposición: `run_single_evaluation` sigue sin existir en `queue_handler`, no hay ninguna
coincidencia de `consent`/`autoriz` en el router ni en los proveedores, `chat_with_info`
sigue declarando en su docstring que no expone herramientas, y los tres `except Exception:
pass` de persistencia siguen en su sitio.

---

### MOLCHAT-BE-003 · P0 · Cualquiera puede redirigir el tráfico del chat a otro servidor

**Evidencia.** `POST /ai/providers/configure` (`api/routers/ai.py:172`) no tiene
ninguna dependencia de autenticación y acepta del cuerpo:

```python
if "api_key" in payload:  cfg.api_key  = payload["api_key"]
if "base_url" in payload: cfg.base_url = payload["base_url"]
```

y lo persiste con `save_provider_config`.

**Impacto.** Es el hallazgo más agudo de esta auditoría, y no por la clave sino
por el `base_url`: un llamador sin credenciales apunta el proveedor a un
servidor propio, y **a partir de ahí todo lo que el investigador escriba en el
chat —incluido el contexto de caso y molécula— se envía ahí**. No hay
indicación en la interfaz de que el destino cambió. Es una primitiva de
exfiltración, no sólo un fallo de autorización.

`POST /ai/providers/active` (línea 161) es la variante barata del mismo
problema: cambiar el proveedor activo sin autenticar.

**Corrección propuesta.** Autenticar, y tratar `base_url` como configuración
sensible: cambiarlo debe requerir confirmación explícita y quedar visible en la
interfaz junto al indicador de proveedor.

**Prueba.** Un `POST /ai/providers/configure` sin token responde 401; con un
`base_url` nuevo, la interfaz declara el destino antes del siguiente turno.

---

### MOLCHAT-BE-002 · P0 · Veinte de veintiún endpoints AI no piden identidad

**Evidencia.** `api/routers/ai.py` declara 21 rutas. **Sólo `POST /ai/chat`**
recibe `current_user` (`get_current_user_optional`, línea 322). Las demás no
tienen dependencia de usuario:

| Endpoint | Qué permite sin credenciales |
|---|---|
| `GET/POST/DELETE /ai/conversations…` | listar, leer y **borrar** conversaciones ajenas |
| `POST /ai/providers/configure` | ver MOLCHAT-BE-003 |
| `POST /ai/providers/active` | cambiar el proveedor activo |
| `POST /ai/speech-to-text` | subir audio para transcribir |
| `POST /ai/models/download` | iniciar una descarga de modelo |
| `PATCH /ai/settings` | cambiar configuración global (`keep_loaded`) |
| `POST /ai/models/open-folder` | `os.startfile` / `xdg-open` en la máquina |

El §8 del plan es explícito: *«Autenticar todos los endpoints AI y tool calls,
incluido streaming, abort y retry»*.

**Nota sobre `open-folder`.** La ruta es fija (`MODEL_SEARCH_PATHS[1]`), así que
no es ejecución de ruta arbitraria; pero es una acción sobre el escritorio del
usuario disparable sin credenciales, y pertenece al mismo grupo.

---

### MOLCHAT-BE-004 · P0 · Las conversaciones no tienen dueño en ninguna capa

**Evidencia.** El aislamiento falta en las cuatro capas a la vez:

1. **Objeto.** `Conversation` no tiene `user_id`.
2. **Servicio.** `ChatService._conversations` y `_active_conv_id` son
   **atributos de clase** (`chat_service.py:86-87`), sobre un singleton de
   proceso (`get_chat_service`, línea 2861).
3. **Persistencia.** La tabla `conversations` (`memory_store.py:331-340`) tiene
   `conv_id`, `messages_json`, `summary`, `molecule_context_json`, `created_at`
   y `updated_at`. **No hay columna de usuario.**
4. **API.** `create_conversation`, `list_conversations`,
   `load_conversation_from_db` y `delete_conversation` no reciben usuario.

**Impacto.** Toda cuenta de la máquina —y todo llamador sin autenticar, por
MOLCHAT-BE-002— comparte un único almacén de conversaciones: las lista, las lee
y las borra. `molecule_context_json` viaja dentro, así que no es sólo el texto
del chat: es el caso y la molécula sobre los que se conversó.

El gate de la pestaña exige lo contrario: *«Conversación y configuración
reaparecen sólo para su propietario»*.

**Corrección propuesta.** Columna `user_id` en `conversations` (aditiva),
dimensión de usuario en las cuatro operaciones, y estado de conversación por
sesión en vez de por proceso. Las conversaciones existentes no tienen dueño
conocido: **no se les puede asignar uno por suposición** —mismo criterio que con
los sellos heredados de MOLDEX-SCI-001—, así que hay que decidir qué se hace con
ellas (ver D-07).

---

### MOLCHAT-NET-005 · P0 · No hay consentimiento antes de enviar datos a un proveedor remoto

**Evidencia.** Búsqueda de `consent`, `consentimiento`, `autoriz`, `allow_remote`
en `api/routers/ai.py`, `chat_service.py` y `services/ai/providers/`: **cero
coincidencias**. No existe puerta alguna: si hay un proveedor remoto
configurado, el turno se envía.

El §8 lo pide con detalle: *«Consentimiento por cuenta antes de enviar datos a
un proveedor remoto: destino, contenido, retención conocida y revocación. El
camino local/offline debe ser inequívoco»*. Es además la misma política
transversal que TRANS-NET-001 dejó abierta en el expediente de Evaluación para
RCSB/UniProt.

**Corrección propuesta.** Consentimiento por cuenta, revocable, que declare
destino y qué se envía; y un indicador permanente de local/remoto en la
interfaz. Pertenece al mismo paquete que MOLCHAT-BE-003, porque ambos tratan
del destino de los datos.

---

### MOLCHAT-INT-001 · P1 · La herramienta de docking no puede funcionar (heredado)

**Evidencia, reconfirmada 2026-08-30.** `services/ai/tools/docking_tools.py:59`
hace `from services.docking.queue_handler import run_single_evaluation`, y esa
función **no existe** en el módulo. El `ImportError` se captura y la herramienta
devuelve siempre *«Pipeline de docking no disponible en este modo»*, aunque
`chat_service` la fuerce por intención.

**Impacto.** El usuario pide un docking, el chat dice que la capacidad no está
disponible, y la causa real es un import roto. Es la clase de fallo que el §8
prohíbe: *«no puede saltarse preflight, autorización ni restricciones
científicas»* — aquí ni siquiera llega a intentarlo, y el motivo que se comunica
no es el real.

**Corrección propuesta.** Decidir primero si MolChat debe poder lanzar
evaluaciones. Si sí, debe hacerlo por el mismo camino que `/evaluation/submit`,
con identidad de usuario, preflight y persistencia — no por una función privada
del pipeline. Si no, la herramienta se retira y el chat lo dice con verdad.

---

### MOLCHAT-BE-006 · P1 · Leer una conversación secuestra la activa del proceso

**Evidencia.** `load_conversation_from_db` (`chat_service.py:135-153`) asigna
`self._active_conv_id = conv_id` como efecto secundario de **leer**. Como ese
atributo es de clase y el servicio es un singleton, un `GET
/ai/conversations/{id}` —sin autenticar— cambia la conversación activa de todo
el proceso.

**Impacto.** Dos sesiones concurrentes se pisan la conversación activa; y un
tercero que simplemente consulte una conversación redirige el siguiente turno
de otra persona a un hilo distinto.

---

### MOLCHAT-INT-007 · P1 · La identidad depende de si el chat va en streaming

**Evidencia.** En `POST /ai/chat`, la rama `stream=True` llama a
`chat_service.chat(..., user_id=user_id)` (línea 341). La rama `stream=False`
llama a `chat_service.chat_with_info(...)` **sin `user_id` y sin `mode`**
(líneas 361-366).

**Corrección de esta auditoría (2026-08-30).** Al implementar MOLCHAT-BE-002
comprobé que el problema no es el que describí. `chat_with_info` **no expone
ninguna herramienta**: su propia docstring lo dice —*«por ahora esta path NO
expone tools nativas al modelo»*—. Así que no es que las herramientas corran con
otra identidad; es que **no corren**.

**Impacto real, y es peor.** Las dos ramas del mismo endpoint tienen
capacidades distintas y el cliente no puede saberlo. La misma pregunta
respondida con `stream=true` puede resolverse con una herramienta determinista,
y con `stream=false` la contesta el modelo por su cuenta. **Un parámetro de
transporte decide el estatuto epistémico de la respuesta**: cálculo o
generación. Eso pertenece al eje SCI del §8 —clasificar qué es cada respuesta—,
no al de intersección, y por eso el hallazgo se recalifica.

**Relación con D-05.** Dos de las siete posiciones del fallback demo que D-05
manda retirar están aquí: `tools/evaluation_tools.py:40` y
`tools/session_tools.py:206`. La sesión obligatoria de MOLCHAT-BE-002 hace que
el chat ya no caiga en ellas, pero las funciones siguen resolviendo a demo si
alguien las llama sin `user_id`.

**Avance parcial verificado 2026-08-31.** La rama `stream=false` ya pasa
`user_id=user_id` a `chat_with_info` (`api/routers/ai.py:392`), así que la mitad
de identidad del hallazgo original está cerrada. **Lo que sigue abierto es la
mitad recalificada y peor**: `chat_with_info` continúa sin exponer herramientas
—su propia docstring lo dice—, de modo que un parámetro de transporte sigue
decidiendo si la respuesta es cálculo o generación. No se cierra hasta que las
dos ramas tengan las mismas capacidades o el contrato declare la diferencia al
cliente.

---

### MOLCHAT-BE-008 · P2 · La persistencia de la conversación se traga sus errores

`create_conversation` envuelve `save_conversation` en `except Exception: pass`
(`chat_service.py:99-107`), y lo mismo hacen `load_conversation_from_db` y
`delete_conversation`. Una conversación puede existir en memoria y no en disco
sin que nadie se entere. El §8 pide persistencia *«atómica y recuperable»*.

---

#### Implementado — 2026-08-30 (BE-002 + BE-003)

**El servidor.** Diecisiete rutas pasan a exigir `get_current_user`. Cuatro se
declaran abiertas **una a una, con su motivo**, en la lista `ABIERTAS` de la
prueba: `/ai/startup`, `/ai/providers`, `/ai/status` y
`/ai/speech-to-text/status`. Son sondas que la interfaz consulta al montar,
antes del auto-login, no devuelven datos de ninguna cuenta y no exponen
secretos. La lista está pensada para ser incómoda de ampliar: una prueba exige
que cada entrada corresponda a una ruta que aún existe.

`POST /ai/chat` pasó de `get_current_user_optional` a `get_current_user`, así
que `user_id` deja de ser `None` y las herramientas dejan de caer al usuario
demo.

**El cliente, que era la mitad que faltaba.** `AIContext` hacía **todas** sus
llamadas con `fetch` crudo y sin cabeceras —`/ai/chat` incluido—, así que
`current_user` llegaba vacío incluso en el único endpoint que lo pedía. En la
práctica **MolChat nunca ha tenido identidad de usuario**. Las nueve llamadas
del contexto y las dos del dictado envían ahora `getAuthHeaders()`.

Sin esta mitad, autenticar el servidor habría dejado la pestaña inservible: era
exactamente el riesgo que la auditoría anotó en §8 y que había que comprobar en
vez de suponer.

**Archivos del paquete:**

- `backend/api/routers/ai.py`
- `backend/tests/test_ai_endpoints_exigen_sesion.py` (nuevo)
- `frontend/context/AIContext.tsx`, `frontend/hooks/useSpeechRecognition.ts`
- `frontend/context/__tests__/AIContextAuth.test.tsx` (nuevo)

**Evidencia reproducida:**

- regresión antes del arreglo: `5 failed`, con la lista de rutas desprotegidas
  en el propio mensaje de fallo; después: `5 passed`;
- prueba de cliente: `3 passed`;
- backend completo **`1015 passed`**; frontend completo **`583 passed`** en 58
  archivos; `tsc --noEmit`, `py_compile` y `git diff --check` limpios;
- OpenAPI: la única incompatibilidad sigue siendo la ruta retirada a propósito
  en TRANS-ANON-002.

**Lo que este paquete NO cierra.** `POST /ai/providers/configure` ya no acepta
llamadas anónimas, que era el daño mayor de MOLCHAT-BE-003. Pero cambiar
`base_url` sigue siendo un cambio de destino de datos **invisible en la
interfaz**: cualquier sesión válida puede hacerlo y nadie se entera. La
confirmación explícita y el indicador permanente de destino van con
MOLCHAT-NET-005, que es donde vive la política de consentimiento.

---

#### Implementado — 2026-08-30 (BE-004 + BE-006)

**La base.** `ai_memory.db` no pasa por `SCHEMA_VERSION` ni por
`_migrate_sqlite_db` —vive aparte, en `~/MolDesign/data/`—, así que la migración
va dentro de `init_conv_db()` y es idempotente: añade `user_id TEXT` si falta y
crea el índice `(user_id, updated_at)`. Las cuatro operaciones
(`save`, `load`, `load_all`, `delete`) reciben dueño y comparten un único filtro,
`_clausula_de_dueno`.

**El servicio.** `_conversations` y `_active_conv_id` eran atributos de **clase**
sobre un singleton de proceso. Ahora son de instancia, y la conversación activa
es un `dict` **por cuenta** (`_active_by_user`). Eso cierra BE-006 de raíz: leer
una conversación sigue fijándola como activa —que es lo que significa abrirla—
pero sólo para quien la pide, no para todo el proceso.

La caché en memoria también se filtra: sin eso, una conversación ajena que
siguiera cargada se colaba en el listado aunque la consulta a la base la
excluyera.

**La decisión D-07.** El correo del invitado se centraliza en
`core/identity.py::GUEST_EMAIL` con un predicado `es_invitado`. Sólo esa cuenta
recibe `incluir_heredadas=True`. Las filas anteriores **no se rellenan**: es el
mismo criterio que con los sellos heredados de MOLDEX-SCI-001, y por la misma
razón —asignarles dueño sería afirmar algo que nadie comprobó—.

Hay una prueba que lee el código de `/auth/desktop-login` y exige que el correo
que allí se crea sea el mismo de la constante. Si alguien cambia uno sin el
otro, el invitado dejaría de heredar en silencio.

**Archivos del paquete:**

- `backend/core/identity.py` (nuevo)
- `backend/services/ai/memory_store.py`, `chat_service.py`, `conversation_state.py`
- `backend/api/routers/ai.py`
- `backend/tests/test_conversaciones_por_cuenta.py` (nuevo)

**Evidencia reproducida:**

- regresión antes del arreglo: `10 failed`; después: `12 passed` (incluye la
  migración sobre una base construida a mano con el esquema anterior: la columna
  aparece, la fila sobrevive y queda en `NULL`);
- backend completo **`1027 passed`**; frontend completo **`583 passed`**;
- `py_compile` limpio.

**Limitación conocida.** El aislamiento es por `user_id` dentro de un archivo
que sigue siendo compartido: `ai_memory.db` está en el home de la máquina, no
por cuenta. La autorización lo cubre, pero quien tenga acceso al sistema de
archivos sigue viendo el archivo entero. Separarlo por cuenta es trabajo aparte,
y hay más tablas en esa base (`ai_catalog`, `ai_details`, índice FTS de chat)
que tampoco tienen dimensión de usuario — **el índice de búsqueda de mensajes no
se auditó todavía** y podría reintroducir la fuga por otra vía.

---

#### Implementado — 2026-08-31 (D-09: proveedor y claves por cuenta)

**El almacén.** `provider_config.json` era un mapa plano `provider_id → entrada`,
global a la máquina. El esquema v2 mete la cuenta en el medio y las seis
operaciones reciben dueño. Las entradas de v1 **no se les asigna dueño**: se
preservan bajo `__heredado__` y sólo las lee quien pide `incluir_heredadas`, que
es la cuenta invitada —mismo criterio que D-07 con las conversaciones y que
MOLDEX-SCI-001 con los sellos—. La migración es de lectura e idempotente: un
archivo v1 se normaliza al leerlo y se escribe en v2 en el primer guardado, sin
perder lo que había. Hay una prueba que lo comprueba justamente así, porque
migrar no puede ser una forma elegante de borrarle la clave al usuario.

**El registro, que era la mitad de fondo.** `ProviderRegistry` tenía la misma
enfermedad que `ChatService` antes de BE-006: `_providers` y
`_active_provider_id` como atributos de **clase**. Y `POST /ai/providers/configure`
escribía `provider.config` del objeto compartido, así que la clave, el modelo y
el `base_url` de una persona pasaban a ser los de todas las sesiones del proceso.

Ahora el registro se parte en dos: el **catálogo** sigue siendo de la máquina
—qué tipos de proveedor existen y qué trae el entorno—, y la **configuración
aplicada** se resuelve por cuenta en cada turno (`resolve_for_user`), que
construye una copia del proveedor con los valores de esa cuenta encima. Es
barato porque los proveedores no guardan estado entre llamadas —cada uno crea su
cliente dentro de `chat()`— y el modelo local sigue cargándose una sola vez por
máquina, que es lo correcto. `apply_persisted_configs` se convierte en
`apply_env_defaults` y deja de aplicar la configuración de nadie sobre el
catálogo.

**Las dos sondas abiertas.** `GET /ai/providers` y `GET /ai/status` declaran
`configured` y `active`, que desde esta decisión son datos de cuenta. Pasan a
`get_current_user_optional`: con sesión responden la vista de esa cuenta; sin
sesión, el catálogo con `configured=False`. Siguen siendo sondas de arranque
—la lista `ABIERTAS` no cambia— y ahora es verdad literal que no devuelven datos
de ninguna cuenta.

**El turno.** `chat_service._resolve_provider` recibe identidad y resuelve por
cuenta, incluidos los tres caminos de repliegue al proveedor local. Sin esto el
resto sería decorado: el turno de una persona seguía saliendo con la clave, y
hacia el `base_url`, que hubiera configurado otra.

**Archivos del paquete:**

- `backend/services/ai/provider_config_store.py`
- `backend/services/ai/providers/registry.py`
- `backend/services/ai/chat_service.py`
- `backend/api/routers/ai.py`
- `backend/tests/test_proveedor_por_cuenta.py` (nuevo)

**Evidencia reproducida:**

- regresión antes del arreglo: **`14 failed`**; después: **`14 passed`** (incluye
  la migración de un archivo v1 escrito a mano: lo heredado sobrevive, la cuenta
  normal no lo ve, el invitado sí, y lo propio gana a lo heredado);
- suites de la pestaña juntas: **`31 passed`**;
- backend completo: **`1041 passed`** (venía de 1027);
- frontend de la pestaña: `14 passed`. No hizo falta tocar el cliente:
  `providerConfigs` sólo vive en memoria de la sesión y el backend nunca envió
  las claves al cliente;
- `py_compile` limpio; diff OpenAPI: la única incompatibilidad sigue siendo la
  ruta retirada a propósito en TRANS-ANON-002.

**Lo que este paquete NO cierra.** El `base_url` ya no es global, pero cambiarlo
**sigue siendo invisible en la interfaz**: la cuenta que lo cambia redirige su
propio tráfico sin que nada lo declare. Esa mitad es de MOLCHAT-NET-005, y ahora
sí se puede escribir, porque el consentimiento se otorga a un destino que ya
tiene dueño.

**Limitación conocida.** El aislamiento es por `user_id` dentro de un archivo que
sigue siendo compartido: `~/.moldesign/provider_config.json` es de la máquina.
Las claves están cifradas en reposo con Fernet, así que un lector del sistema de
archivos no las obtiene sin el `secret_key` local —que está al lado—. Separar el
almacén por cuenta es trabajo aparte, del mismo tamaño que la limitación
equivalente de `ai_memory.db`.

---

#### Implementado — 2026-08-31 (NET-005 + la mitad de interfaz de BE-003)

**El destino se calcula, no se supone.** Es la decisión de fondo del paquete.
Un proveedor no es remoto por su nombre: `ollama` apuntado al servidor de otra
persona sale de la máquina, y un `openai` apuntado a un `llama.cpp` en
`localhost` no. `services/ai/consent.py` deriva el destino del **host resuelto
para esa cuenta** (D-09), y un host desconocido se trata como remoto: la duda no
se resuelve a favor de enviar. Una IP de la red local cuenta como remota, porque
es otra computadora.

**La puerta.** `chat()` y `chat_with_info()` comprueban el consentimiento
**antes** de tocar la conversación: si el destino no está autorizado, el turno no
sale y tampoco se guarda como si hubiera ocurrido. El aviso dice a dónde iba, qué
iba con él y cómo seguir; no es un «no disponible». `chat_with_info` no cae al
motor local por su cuenta: cambiar de motor cambia el estatuto de la respuesta, y
esa elección es del investigador.

**El consentimiento se otorga a un destino, no a un proveedor.** La huella es
`proveedor@host`, así que mover el `base_url` no hereda la autorización del
destino anterior — y eso cierra la mitad de BE-003 **donde se decide**, sin
depender de que la interfaz se acuerde de avisar. Además `providers/configure`
rechaza con 409 un cambio de host sin `confirmar_destino`, declarando en el
propio error de dónde a dónde iría, y revoca el permiso anterior al aplicarlo.

**No se hereda nunca.** La cuenta invitada hereda configuración (D-07/D-09) pero
**no consentimientos**: darlo por otorgado sería afirmar que alguien aceptó algo
que nadie comprobó. Es el mismo criterio que con los sellos de MOLDEX-SCI-001,
aplicado al permiso en vez de al dato.

**La interfaz.** La insignia decidía «nube» con `provider.id !== "local"`, que es
exactamente la suposición que esta auditoría desmonta; ahora declara el destino
que calcula el backend, y dice «sin comprobar» mientras no lo sepa, en vez de
suponer local por optimismo. El panel avisa del destino sin autorizar **antes**
de que el investigador escriba, con el botón para autorizarlo, y el modal pide
confirmación explícita antes de mover el destino.

**Archivos del paquete:**

- `backend/services/ai/consent.py` (nuevo)
- `backend/services/ai/provider_config_store.py`, `chat_service.py`
- `backend/api/routers/ai.py` (tres rutas nuevas: `GET/POST /ai/consent`,
  `DELETE /ai/consent/{provider_id}`)
- `backend/tests/test_consentimiento_destino_remoto.py` (nuevo)
- `frontend/context/AIContext.tsx`, `components/ai/ProviderBadge.tsx`,
  `ChatPanel.tsx`, `AISettingsModal.tsx`
- `frontend/components/ai/__tests__/DestinoDeclarado.test.tsx` (nuevo),
  `frontend/context/__tests__/AIContextConsentimiento.test.tsx` (nuevo)

**Evidencia reproducida:**

- regresión antes del arreglo: **`5 failed`**, incluidas las dos que importan
  —el turno salía a un servidor que la cuenta nunca autorizó, y el permiso de
  una cuenta servía para otra—; después: **`21 passed`** con el contrato HTTP;
- backend completo **`1062 passed`** (venía de 1041);
- frontend completo **`595 passed`** en 60 archivos; `tsc --noEmit` limpio;
- diff OpenAPI: las tres rutas nuevas son aditivas; la única incompatibilidad
  sigue siendo la ruta retirada a propósito en TRANS-ANON-002. **El snapshot no
  se regeneró**: hacerlo borraría ese aviso, que otro paquete todavía sigue.

**Dos pruebas ajenas cambiaron, y conviene saber por qué.** `AIContext.test.tsx`
contaba el total de llamadas al montar y esperaba 1; añadir la sonda de destinos
la rompía sin que cambiara lo vigilado, así que ahora comprueba lo que quería
decir: que no salió ningún turno. Y el parser de `AIContextAuth.test.tsx`
cortaba una llamada cuyo cuerpo termina en `getAuthHeaders(),` y la denunciaba
sola; se corrigió el patrón, no la exigencia.

**Lo que este paquete NO cierra.** El consentimiento cubre el turno del chat. Las
herramientas que salen a la red por su cuenta —el resolvedor de nombres, la
búsqueda web— **no pasan por esta puerta**, y son la misma política transversal
que TRANS-NET-001 dejó abierta para RCSB/UniProt en el expediente de Evaluación.
Queda anotado ahí y no se declara resuelto aquí.

---

#### Implementado — 2026-08-31 (INT-007 + retirada del fallback demo de D-05)

**Una sola implementación, no dos sincronizadas.** `chat_with_info` era un camino
paralelo de ~110 líneas: no exponía herramientas —lo decía su propia docstring—,
no pasaba por el ruteo de intención ni por los respondedores deterministas, y
aceptaba `allow_web` «por simetría de contrato» sin usarlo. Ahora acumula lo que
produce `chat()`. Copiar la lógica habría reabierto el mismo hallazgo en cuanto
una de las dos cambiara.

**Lo que la regresión midió, antes de tocar nada.** Con un proveedor espía que
anota *cómo* se le habla: `stream=true` usó `['chat_with_tools', 'chat']` y
`stream=false` usó `['chat']`. Y con las herramientas reales registradas, la
pregunta «¿cuál es el peso molecular de la aspirina?» se contestaba con
`compute_properties` —MW 180.2 Da, calculado— por una rama, y por la otra la
respondía el modelo. **Es el hallazgo entero en una sola línea de salida.**

**Un descubrimiento que cambió la corrección.** Dentro de `chat()`, `stream` no
significa «responde de una vez»: significa **«no emitas»**. Cada rama
determinista hace `if stream: yield resp` y luego persiste la respuesta en la
conversación, así que con `stream=False` el generador no produce nada y el
llamador tendría que ir a leerla al historial. Por eso `chat_with_info` delega
con `stream=True` y junta los trozos: mismo camino, misma respuesta, entregada
de una pieza. Queda anotado que el modo `stream=False` de `chat()` es ahora
código sin llamador y devuelve vacío en silencio — es una trampa para el
siguiente que lo use, y su limpieza pertenece al eje SCI pendiente.

**`fallback_used` describía la conversación, no el turno.** `fallback_provider`
se marcaba al caer al motor local y **no se limpiaba nunca**, así que el turno
siguiente seguía declarándose respondido por un respaldo. Ahora se reinicia en
cada turno: es una afirmación sobre de dónde salió *esta* respuesta.

**La retirada del fallback demo (D-05).** `evaluation_tools` y `session_tools`
resolvían a `get_or_create_test_user()` cuando no había `user_id`: contestaban
igual, pero el historial que leían era el de una cuenta sintética compartida.
Devolver datos de otra cuenta como si fueran tuyos es peor que no contestar, así
que ahora se abstienen y lo dicen. Una prueba recorre `services/ai/` entero y
falla si alguna herramienta vuelve a resolver a esa cuenta.

**Archivos del paquete:**

- `backend/services/ai/chat_service.py`
- `backend/services/ai/tools/evaluation_tools.py`, `tools/session_tools.py`
- `backend/api/routers/ai.py` (la rama no-streaming ya propaga `mode`)
- `backend/tests/test_paridad_entre_ramas_de_transporte.py` (nuevo)

**Evidencia reproducida:**

- regresión antes del arreglo: **`3 failed`** con la asimetría de herramientas
  citada arriba; después: **`8 passed`**;
- backend completo **`1070 passed`** (venía de 1062); frontend **`595 passed`**;
- `py_compile`, `git diff --check` y diff OpenAPI sin novedades.

**Una prueba mía estaba mal y lo dijo la suite completa.** Comparaba el turno 1
de una rama con el turno 2 de la otra: medía el historial, no la rama. En
aislamiento pasaba; con las herramientas reales registradas, no. Ahora cada rama
arranca sobre una conversación nueva.

---

## 4. Lo que está bien y no debe tocarse

- **Las claves de proveedor están cifradas en reposo.**
  `provider_config_store.py` usa Fernet (AES-128-CBC + HMAC-SHA256) con clave
  derivada del secreto local de la máquina. Es la parte mejor resuelta del
  módulo.
- **Ninguna respuesta publica la clave.** `ProviderInfoResponse`
  (`core/models.py:1305-1315`) expone `requires_api_key` y `configured`, pero
  nunca el valor. La escritura es el problema (MOLCHAT-BE-003), no la lectura.
- **El SSE ya está corregido** para respuestas multilínea, con el motivo
  documentado en el propio endpoint.

## 5. Qué se ejecutó en esta auditoría

Lectura estática de `api/routers/ai.py`, `services/ai/chat_service.py`
(ciclo de vida de conversación y ruteo de `user_id`), `memory_store.py`,
`provider_config_store.py`, `providers/registry.py`, `tools/docking_tools.py`,
`core/models.py` y el inventario de pruebas. **No se ejecutaron suites ni se
modificó ningún archivo de producto.**

Queda sin auditar, para MOLCHAT-AUD-01: los ejes **SCI** del §8 —clasificación
de respuestas, citas de procedencia, prohibición de fabricar resultados,
abstención— que exigen leer las ~2.500 líneas de `tools/` y el ruteo de
intención de `chat_service`; y toda la superficie de frontend
(`AIContext.tsx`, `components/ai/`).

## 6. Orden de ataque propuesto

Los cuatro P0 son de backend y privacidad, no de ciencia, así que el mandato
«ciencia primero» no los reordena: no hay validez científica que defender si el
canal por el que viajan los datos es abierto.

1. **MOLCHAT-BE-003 + MOLCHAT-BE-002** — autenticar los 20 endpoints y cerrar la
   reconfiguración del destino. Es el daño mayor y el arreglo más acotado.
2. **MOLCHAT-BE-004 + MOLCHAT-BE-006** — dueño de la conversación en las cuatro
   capas, y estado por sesión en vez de por proceso.
3. **MOLCHAT-INT-007** — una sola identidad, no una por rama de transporte.
   Coincide con la retirada del fallback demo de D-05.
4. **MOLCHAT-NET-005** — consentimiento y declaración de destino.
5. **MOLCHAT-INT-001** — decidir si el chat lanza evaluaciones (ver D-08).
6. **MOLCHAT-BE-008** y después la auditoría SCI pendiente (§5).

## 7. Decisiones acumuladas para el propietario

Se suman a las cuatro del expediente de Moldex ([65](65_MOLDEX_AUD_00_EXPEDIENTE.md) §7).

| ID | Decisión | Nace en | Estado |
|---|---|---|---|
| D-07 | Qué se hace con las conversaciones existentes, que no tienen dueño | MOLCHAT-BE-004 | **resuelta**: las hereda el invitado |
| D-08 | Si MolChat debe poder lanzar evaluaciones | MOLCHAT-INT-001 | **resuelta 2026-08-31**: sí, en segundo plano |
| D-09 | Si el proveedor y sus claves son por máquina o por cuenta | MOLCHAT-BE-003 | **resuelta 2026-08-31**: por cuenta |
| D-10 | Qué es MolGraph: corpus compartido o memoria por cuenta | MOLCHAT-BE-009 | **abierta** |

### D-07 · Conversaciones sin dueño

Al añadir `user_id` habrá filas antiguas con `NULL`. No se les puede asignar
propietario por suposición —es el mismo criterio que se aplicó a los sellos
heredados en MOLDEX-SCI-001—. Opciones: (a) dejarlas invisibles para todos,
recuperables sólo desde la base; (b) mostrarlas como «anteriores a las cuentas»
a la cuenta invitada `Desktop User`, coherente con D-05/D-06; (c) borrarlas.
Mi lectura: (b) encaja con la decisión que ya tomaste sobre el invitado.

### D-08 · ¿MolChat lanza evaluaciones?

Hoy dice que no puede por un import roto, no por diseño. Si la respuesta es sí,
la herramienta tiene que pasar por el mismo camino que la pestaña Evaluación
—identidad, preflight, persistencia, procedencia— y eso es un paquete de tamaño
real, no un arreglo de import. Si es no, se retira y el chat lo dice con verdad.

**Resuelta 2026-08-31 — sí.** El propietario lo justifica por el eje SCI, no por
capacidad: *«MolChat hace evaluaciones en segundo plano para sacar datos exactos
y precisos, para no inventar información»*. Es decir, la evaluación no es una
comodidad del chat: es el mecanismo por el que una respuesta deja de ser
generación y pasa a ser cálculo.

Consecuencias que esta lectura fija, y que valen como criterio de aceptación:

1. La herramienta pasa por el **mismo camino que `/evaluation/submit`**:
   identidad, preflight, persistencia y procedencia. No por una función privada
   del pipeline, que es lo que el import roto intentaba.
2. **En segundo plano y con estado visible.** Una evaluación real tarda; el
   turno no puede bloquearse ni fingir que ya terminó. El chat declara que la
   lanzó, da su identificador y la respuesta con el número llega cuando existe.
3. **El resultado se cita, no se narra.** Todo dato que venga de una evaluación
   enlaza a la corrida persistida —`task_id`— igual que la pestaña Evaluación.
   Si la evaluación falla o no se lanzó, el chat se abstiene: no rellena con una
   estimación del modelo.
4. Refuerza la tarea 3 (MOLCHAT-INT-007): si el propósito declarado del chat es
   no inventar, una rama de transporte que responde **sin herramientas** es una
   contradicción del producto, no un detalle de contrato.

### D-09 · ¿El proveedor es por máquina o por cuenta?

Hoy es global: una sola configuración y una sola clave para todas las cuentas
del equipo. El §8 pide aislarlo por cuenta. Si en tu modelo de producto el
equipo es de un solo investigador, «por máquina» es defendible siempre que esté
autenticado; si esperas equipos compartidos, la clave de una persona no puede
gastarse en el chat de otra.

**Resuelta 2026-08-31 — por cuenta.** Alinea con el §8 y cierra la vía por la
que la clave de una persona se gastaba en el chat de otra.

Alcance que esto abre, y que el paquete tiene que cubrir entero:

1. **El almacén** (`provider_config_store.py`) pasa de un mapa plano
   `provider_id → entrada` a uno con dimensión de cuenta. Las entradas
   existentes no tienen dueño conocido: **no se les asigna uno**, se preservan
   como heredadas y las lee sólo el invitado —mismo criterio que D-07—.
2. **El registro** (`providers/registry.py`) tiene la misma enfermedad que tenía
   `ChatService` antes de BE-006: `_providers` y `_active_provider_id` son
   atributos de **clase**, y `POST /ai/providers/configure` muta el objeto
   compartido. El catálogo puede seguir siendo de máquina —son los tipos de
   proveedor disponibles—, pero **la configuración aplicada tiene que resolverse
   por cuenta en cada turno**, no mutarse en el singleton.
3. **El proveedor activo es por cuenta.**
4. **Las dos sondas abiertas** (`GET /ai/providers` y `GET /ai/status`) declaran
   `configured` y `active`, que con esta decisión pasan a ser datos de cuenta.
   O piden identidad, o dejan de responder esos dos campos. Se resuelve con
   identidad opcional: con sesión, la vista de esa cuenta; sin sesión, el
   catálogo de la máquina y `configured=False` —así siguen sirviendo al arranque
   sin filtrar de quién es la clave—.
5. **El consentimiento de NET-005 es por cuenta y por destino**, que es lo que
   hace que ambas decisiones vayan en paquetes consecutivos.

### D-10 · ¿MolGraph es corpus compartido o memoria por cuenta?

`services/ai/molgraph.py` mantiene un grafo en `~/MolDesign/data/molgraph.db`
sin `user_id`. Cada evaluación de cualquier cuenta entra ahí desde
`queue_handler` (`add_evaluation_node`), y siete herramientas de MolChat lo leen:
`query_molgraph`, `molgraph_neighbors`, `molgraph_similar`, `molgraph_impact`,
`molgraph_scaffolds`, `molgraph_druglikeness`, `molgraph_admet`, más
`suggest_smiles`. Es la misma fuga que BE-004 cerró, por un cuarto almacén.

Lo que impide arreglarlo sin decidir: el producto **distribuye**
`molgraph_seed.db`, un corpus público que `api/main.py` copia en el primer
arranque, y las filas existentes sin dueño son una mezcla indistinguible de ese
corpus y de evaluaciones que hizo quien ya usó la máquina. Además el nodo de
molécula tiene id `mol_<smiles>` —compartido entre cuentas— y
`add_evaluation_node` sobrescribe sus propiedades con la última evaluación: si
sólo se filtrara la lectura, una cuenta seguiría pisando el score de otra, y
ahora además sin que se viera. Un arreglo a medias deja el dato **mal** en vez de
sólo compartido.

Opciones:

- **(a)** Marcar el seed al copiarlo y tratar todo lo no marcado como privado sin
  dueño, visible sólo para el invitado (mismo criterio que D-07). Conserva la
  referencia y cierra la fuga desde hoy; las filas mezcladas anteriores quedan
  con el invitado.
- **(b)** Declarar el grafo corpus compartido de sólo lectura y dejar de escribir
  en él las evaluaciones de las cuentas. Es el cambio más limpio y el que más
  capacidad quita: MolChat perdería el «qué modificaciones mejoraron la afinidad»
  sobre el trabajo propio del investigador.
- **(c)** Partirlo en dos bases —corpus distribuido y grafo por cuenta— y unir
  las consultas en lectura. Es lo que más conserva y lo que más cuesta.

Mi lectura: (a) es la que menos rompe y la que sigue el criterio ya establecido
para lo heredado; (c) es la correcta a plazo si el grafo va a seguir creciendo
con el trabajo de cada cuenta.

## 8. Riesgos y trabajo no verificado

- **Ningún hallazgo se reprodujo en ejecución.** Todo es lectura con líneas
  citadas; antes de cada corrección hay que escribir la regresión que lo
  demuestre.
- **La auditoría SCI está pendiente** (§5). Los hallazgos de arriba son de
  canal y aislamiento; la pregunta de si el chat afirma cosas que no puede
  sostener todavía no se ha respondido, y es la mitad del §8.
- **No se auditó el frontend** de la pestaña.
- Corregir MOLCHAT-BE-002 puede romper el arranque de la interfaz si alguna
  llamada de bootstrap se hace sin sesión. Hay que comprobarlo al implementar,
  no suponerlo.

---

## 9. Estado de ejecución — corte del 2026-08-31

Marcado a partir de lectura del código de hoy y de las regresiones existentes,
no del texto de los paquetes anteriores.

### Hecho y verificado

- ✅ **MOLCHAT-BE-002** — 17 rutas exigen `get_current_user`; 4 sondas de arranque
  declaradas una a una con su motivo; cliente enviando `getAuthHeaders()` en las
  once llamadas. Regresión: `5 failed` → `5 passed`.
- ✅ **MOLCHAT-BE-004** — `user_id` en `conversations` con migración idempotente,
  índice `(user_id, updated_at)`, filtro único `_clausula_de_dueno`, caché en
  memoria filtrada, y D-07 resuelta (hereda el invitado, sin rellenar filas).
- ✅ **MOLCHAT-BE-006** — `_conversations` y `_active_conv_id` pasan de atributos de
  clase a estado de instancia con activa por cuenta (`_active_by_user`).
- ✅ **MOLCHAT-BE-003** — cerrado en dos mitades: el servidor el 2026-08-30
  (`providers/configure` y `providers/active` ya no aceptan anónimos) y el
  destino declarado el 2026-08-31 (409 sin confirmar, permiso revocado al mover
  el host, y el destino visible de forma permanente en la insignia).
- ✅ **MOLCHAT-NET-005** (2026-08-31) — consentimiento por cuenta y por destino,
  con el destino calculado del host resuelto y no del nombre del proveedor. El
  turno no sale sin autorización y el camino local no pide nada.
- ✅ **MOLCHAT-INT-007** (2026-08-31) — una sola implementación detrás del
  contrato: la rama no-streaming acumula lo que produce la de streaming. Incluye
  la retirada del fallback demo (D-05) y `fallback_used` por turno.
- ⚠️ **MOLCHAT-INT-007 (parcial)** — `user_id` ya viaja en la rama no-streaming.
  **Falta** la paridad de capacidades entre ramas.

- ✅ **D-09 · proveedor y claves por cuenta** (2026-08-31) — almacén con dimensión
  de cuenta y migración que preserva lo heredado sin dueño, catálogo separado de
  la configuración aplicada, activo por cuenta, identidad opcional en las dos
  sondas y resolución por cuenta en el turno. Regresión: `14 failed` → `14 passed`.

Evidencia acumulada de la pestaña: **`60 passed`** en sus cinco suites de
backend; backend completo **`1070 passed`**; frontend completo **`595 passed`**.

**Los cuatro P0 están cerrados.** Lo que queda es P1, P2 y las dos mitades de la
auditoría que nunca se hicieron.

### En proceso

Ninguno. **Las siete tareas pendientes del corte anterior están hechas.**

### Cerrado el 2026-08-31 — las siete tareas

1. ✅ **MOLCHAT-INT-001 (P1) — la herramienta de docking.** `run_docking`
   llamaba a `run_single_evaluation`, que no existe; el `ImportError` se
   capturaba y el chat contestaba «pipeline no disponible en este modo», un
   motivo que no era el real. Ahora la corrida entra por
   `services/evaluation_submission.py::registrar_corrida`, **la misma puerta que
   `POST /evaluation/submit`**, que se extrajo del router para que las dos
   superficies usen una sola: identidad, receptor, preflight, gates y registro
   del dueño del `task_id`. MolChat pide preflight aunque no traiga huella
   (`exigir_preflight=True`), porque no tiene la pantalla donde el investigador
   lo acepta. Va en segundo plano y devuelve el `task_id`; la nueva
   `check_docking_status` lee el resultado con la política de propiedad del
   endpoint —`_autorizar_corrida`, también extraída para no tener dos reglas— y
   se abstiene mientras la corrida no exista. Regresión: `8 failed` → `8 passed`.

2. ✅ **MOLCHAT-BE-008 (P2) — la persistencia que se tragaba sus errores.** Los
   tres desenlaces se contaban como buenos aunque la base no hubiera hecho nada.
   Ahora `ai_memory.db` lanza `PersistenciaFallida`; crear devuelve 503 en vez de
   un id que no sobrevive al reinicio y no deja conversación fantasma en memoria;
   leer distingue el 404 legítimo del 503; borrar devuelve si borró **una fila** y
   contesta 404 cuando no. El turno es el caso aparte: `_persist_conv` corre
   después de que el modelo contestó, así que no estalla —marca la conversación
   como degradada y el turno lo declara por el canal `__WARNING__:`—. Regresión:
   `9 passed`.

3. ✅ **Fuga por el índice de búsqueda (P1).** Era la peor de las tres, porque no
   hacía falta que nadie pidiera nada: `_prepare_messages_with_context` consultaba
   `search_chat_history` **en cada turno** sin filtro, y metía en el prompt de una
   cuenta los mensajes de otra. `ai_catalog` gana `user_id` con migración aditiva;
   `ai_details` se filtra por su join, para que no haya dos verdades sobre de quién
   es una molécula; el índice FTS5 —que no admite `ALTER`— se reconstruye
   preservando lo anterior como heredado (D-07). Sin identidad no se lee nada.
   `store_evaluation` recibe el dueño desde `queue_handler`, y
   `build_context_for_llm` deja de inyectar el catálogo entero de la máquina en el
   reporte de una cuenta. Regresión: `12 passed`.

4. ✅ **MOLCHAT-AUD-01, eje SCI.** Lo que faltaba no era una nota: era un
   mecanismo. `ToolDef` declara ahora `clase` y `procedencia`, y una prueba falla
   si alguna de las 27 herramientas no las declara; `format_tool_results` imprime
   ambas en el bloque que entra al turno, y un error se presenta como abstención
   —«no se obtuvo dato», «no inventes el valor»— en vez de como una línea más.
   El prompt permanente gana dos reglas: conservar la clase al redactar y
   abstenerse. Se corrigieron dos **negativos fabricados** que la lectura
   encontró: «Sin alertas PAINS» cuando el catálogo no cargó, y «Fragmentos
   BRICS: 0» cuando la fragmentación falló. Y se retiró el `stream=False` de
   `chat()`, que desde INT-007 no tenía llamador y devolvía vacío en silencio: no
   significaba «responde de una vez» sino «no emitas». Regresión: `11 passed`.

5. ✅ **MOLCHAT-AUD-01, eje FE/UX.** `sendMessage` hacía `if (!res.ok) return;`:
   la pregunta quedaba en la lista, no llegaba respuesta y nada decía por qué —y
   los motivos accionables que esta pestaña acababa de añadir al backend morían
   ahí—. Ahora el turno devuelve su desenlace, el motivo se muestra con un
   reintento que reusa el mismo snapshot (idempotente: no duplica la pregunta), y
   `ChatInput` sólo limpia el borrador si el turno salió. La mitad SCI de la
   pantalla: `BloqueDeEvidencia` separa la evidencia de la prosa del modelo y
   pinta cada dato con su clase y su fuente; lo que llegue sin clasificar se
   marca como no verificado. Proveedor, destino y modo ya eran visibles y no se
   tocaron. Regresión: `13 passed` en frontend.

6. ✅ **Higiene transversal del §8.** *Tamaños:* `ChatMessage.content` y
   `AIChatRequest.messages` no tenían tope y `molecule_context` tampoco; los tres
   lo tienen ahora, y en el modelo —no en una ruta—, para que el siguiente
   consumidor no lo pierda. El audio de dictado se leía entero en memoria con
   `await request.body()` y sin mirar el `content-type` que sí calculaba: ahora se
   rechaza por cabecera cuando se puede y se corta al leer cuando no. *Tiempos:*
   el stream del motor local se abría sin tope de lectura, así que un motor que
   acepta la conexión y deja de emitir colgaba el turno para siempre. *Secretos:*
   `services/ai/redaccion.py` redacta credenciales antes de que un error de
   proveedor llegue a la pantalla o al log —el host se conserva, porque es el dato
   que NET-005 obliga a declarar—. *Markdown:* el renderizador escapaba a
   entidades HTML un texto que React ya escapa, así que `MW < 500` se leía
   `MW &lt; 500`; ahora se sanea lo activo (esquemas ejecutables, caracteres de
   control) y se deja intacta la puntuación científica. Regresión: `17 passed`
   backend, `6 passed` frontend.

7. ✅ **Gate de MolChat.** Protocolo y evidencia:
   [67_GATE_MOLCHAT.md](67_GATE_MOLCHAT.md). Suite adversarial de `18 passed`
   sobre los cuatro frentes del §8. Encontró dos fallos reales: **prompt injection
   podía elegir de quién era el historial** —`execute_tool_step` ejecutaba el
   `user_id` que escribiera el modelo, y el turno lleva dentro texto de terceros—
   y **una llamada remota sin autorizar en cada turno**, `pubchem_autolookup`, que
   no miraba `allow_web` ni el consentimiento. Los dos corregidos.

### Hallazgos nuevos que abrió esta tanda

- **MOLCHAT-BE-009 · P1 · `molgraph.db` no tiene dimensión de cuenta.** Apareció
  auditando la tarea 3: es el cuarto almacén, y siete herramientas del chat lo
  leen. No se ha medio arreglado a propósito —el id de nodo es `mol_<smiles>`,
  compartido, y `add_evaluation_node` sobrescribe las propiedades con la última
  evaluación, así que filtrar sólo la lectura dejaría a una cuenta pisando el
  score de otra y encima ocultándolo—. Detalle y opciones en el §7 (D-10) y en
  [67](67_GATE_MOLCHAT.md).



### Pendiente

**Ninguna de las siete.** Lo que queda abierto es lo que esta tanda encontró y
declaró en vez de medio arreglar:

1. **MOLCHAT-BE-009 (P1)** — `molgraph.db` sin dimensión de cuenta. Bloqueado por
   **D-10**, que es una decisión de producto y no de implementación: qué es
   MolGraph, corpus compartido o memoria por cuenta.
2. **Gate runtime de la pestaña** — el gate de hoy es de suite. Falta ejecutar
   una conversación real contra un modelo cargado y lanzar desde el chat una
   evaluación con motor real, leyéndola después por su `task_id`. Requiere modelo
   local descargado o clave de proveedor.
3. **Consentimiento por destino de herramienta**, no sólo del proveedor de chat.
   `allow_web` es un interruptor, no un permiso por host. Es la misma política
   transversal que TRANS-NET-001 dejó abierta para RCSB/UniProt.

**Evidencia consolidada de la pestaña**, con el intérprete declarado —porque
antes no lo estaba y por eso las cifras no cuadraban:

| Medida | Intérprete de desarrollo | `python-embed` (el que se distribuye) |
|---|---|---|
| backend completo | `1253 passed` | `1215 passed, 3 skipped` |

La diferencia no es ruido: 36 pruebas del contrato del dossier hacen
`pytest.importorskip("pypdf")`, y `pypdf` no estaba ni en el runtime embebido ni
en CI. **El contrato del PDF no se verificaba en ningún sitio** y el número
redondo lo tapaba. Ahora `backend/requirements-test.txt` la declara, CI la
instala, y `scripts/report_test_counts.py --check` falla si una suite vuelve a
dejar de recolectar en silencio. Los conteos de este expediente se generan; ya
no se copian a mano.

Suite adversarial: `18 passed`. Frontend completo: `638 passed` en 66 archivos.
`tsc --noEmit` limpio; `py_compile` limpio; ruff sin hallazgos nuevos.

**El snapshot OpenAPI no se regeneró.** Ya estaba desactualizado antes de esta
tanda, y su única incompatibilidad —`GET /evaluation/limit-status`, retirado por
TRANS-ANON-002— exige `--write --allow-breaking`, que es decisión del propietario
y de un paquete anterior. Lo que esta tanda añade al contrato es aditivo:
`maxLength` en `ChatMessage.content` y `maxItems` en `AIChatRequest.messages`.
