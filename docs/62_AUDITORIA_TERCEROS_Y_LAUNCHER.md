# 62 — Auditoría de terceros, launcher y release comercial

> **Documento histórico (2026-09-06).** Esta auditoría describe el launcher y el paquete base de una iteración anterior. No es el contrato vigente: el runtime va embebido en la build y sólo Qwen/ESMFold son módulos opcionales. Consulta `AGENTS.md`, `BUILD_GUIDE.md` y `launcher-manifest.json` para el estado actual.


Fecha: 31 de agosto de 2026  
Prioridad: alta  
Criterio: validez científica > calidad > eficiencia

## Resultado ejecutivo

La aplicación ya tenía un gestor Tauri funcional para descarga, cancelación, reanudación, extracción y comprobación SHA-256, pero estaba oculto del flujo normal y la pantalla `/launcher` no regresaba correctamente a MolDesign. Se publicó el acceso desde Opciones, se añadió una campana de estado global y se convirtió el manifiesto en un contrato visible de procedencia, licencia, tamaño e integridad.

La auditoría también separó tres categorías que antes se confundían:

1. **Incluido en el runtime:** Vina, Meeko, RDKit, Open Babel, xTB, llama.cpp y demás dependencias empaquetadas.
2. **Descargable bajo demanda:** paquete base, Qwen GGUF y pesos ESMFold; cada uno conserva licencia y SHA-256 propios.
3. **Servicio externo configurado por el investigador:** DiffDock, ColabFold y RFdiffusion/ESMFold-Pro. Existen adaptadores backend, pero sus runtimes/pesos no forman parte del instalador base.

## Cambios de producto

- `Acerca de MolDesign` es el escaparate de capacidades, autores y procedencia científica.
- `Legal y privacidad` concentra términos, privacidad, copyleft, atribuciones y acceso a avisos completos.
- `Modelos y motores` administra descargas y muestra antes de instalar: origen, licencia, tamaño y estado.
- La campana de navegación muestra descargas, instalaciones, errores y acceso directo al gestor.
- El botón antiguo `JUGAR` se sustituyó por `Abrir MolDesign` y ahora navega a `/`.
- TabPFN se inicia con telemetría y apertura de navegador desactivadas.

## Integridad de artefactos

| Artefacto | Bytes | SHA-256 |
|---|---:|---|
| `base-v1.0.0.zip` | 872210118 | `3e3c42c5a08f2e7e313b765e88c1e6cd2038825367ee3e5b7c9b25cf3abeca49` |
| `qwen2.5-1.5b-instruct-q4_k_m.gguf` | 1117320736 | `6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e` |
| ESMFold `pytorch_model.bin` | 8442062570 | `2ee07356b125d1e3e57503c204111fd7323347fc4735d41d3caac57c2a78e116` |

La fuente canónica ejecutable está en `launcher-manifest.json` y en el fallback tipado de `DownloadProvider`. Ambos deben permanecer sincronizados.

## Licencias con obligaciones relevantes

- Código MolDesign: AGPL-3.0-only.
- Open Babel: GPL-2.0-or-later según upstream; conservar fuente y avisos.
- Meeko 0.7.1: LGPL-2.1 (upstream lo presenta como LGPL v2+); conservar texto y capacidad práctica de sustitución.
- xTB 6.7.1: LGPL-3.0-or-later; se ejecuta como proceso independiente reemplazable.
- rpc-websockets 9.3.9: LGPL-3.0-only; dependencia transitiva de Solana Web3.js reconstruible desde lockfile.
- llama.cpp: MIT.
- Qwen2.5 1.5B GGUF: Apache-2.0.
- ESMFold v1: MIT.
- TabPFN: Prior Labs License 1.2 y atribución visible `Built with PriorLabs-TabPFN`.

Los textos y avisos públicos viven en `frontend/public/legal/`; `bundle_helper.py` los copia al runtime instalado.

## Bloqueo P0 cerrado — RTMScore

El 1 de septiembre de 2026 se verificó la licencia MIT publicada por `sc8668/RTMScore` y se incorporó su texto íntegro en `rescoring/RTMScore/LICENSE` (Copyright (c) 2023 sc8668). El empaquetador conserva el gate: aborta si una actualización futura vuelve a dejar el snapshot sin `LICENSE`, `LICENSE.txt` o `COPYING`.

## SBOM

`docs/api/sbom.json` inventaría:

- 170 distribuciones del Python embebido;
- 1353 dependencias npm de producción;
- 590 crates fijadas por Cargo.lock;
- Vina, xTB y llama-server con tamaño y SHA-256.

Cuando Cargo no dispone de todas las crates en caché, el inventario de nombre/versión se obtiene honestamente de Cargo.lock y no se inventa una licencia. Para el release final debe ejecutarse `cargo metadata --locked --offline` con la caché completa y revisar los campos vacíos.

## Gate de salida pendiente

Antes de firmar 1.0.0:

1. fijar etiqueta/commit público del código fuente y comprobar que el enlace de producto sea permanente;
2. regenerar SBOM con caché Cargo completa y revisar licencias vacías/no estándar;
3. ejecutar suite frontend, backend y build Tauri limpia;
5. abrir el instalador resultante y comprobar que `licenses/`, manifiestos y avisos estén presentes;
6. descargar cada módulo desde una instalación vacía, cortar/reanudar red y comprobar hash incorrecto;
7. hacer revisión jurídica profesional de AGPL/GPL/LGPL y de la licencia propia de modelos antes de la venta.
---

## Addendum del 2026-09-01 — ENG-001: el menú avanzado ofrecía seis motores que no existen

Auditoría previa a la primera build pública. El modal de opciones avanzadas de
Evaluación ofrece **siete motores**. Esto es lo que hay detrás de cada uno en una
instalación limpia:

| Opción del menú | ¿Se puede ejecutar? | Qué hay realmente |
|---|---|---|
| **AutoDock Vina 1.2.7** | **Sí** | El binario que el instalador empaqueta. Es el único motor real |
| QuickVina 2 | No | `qvina2_executable_path` vale `"qvina2"` y ese binario **no se distribuye** — `resources/tools/` trae vina, xtb y llama |
| DiffDock | No | `diffdock_api_url = None`: cliente HTTP de un servidor externo que nadie levanta |
| ESMFold | No | Sidecar en `localhost:8100`. **`local_services/` no existe en el árbol** ni en el instalador |
| ESMFold Pro | No | Sidecar en `localhost:8300`, GPU requerida. Igual |
| RFdiffusion (`esmfold-experimental`) | No | El mismo sidecar 8300 |
| ColabFold | No | `colabfold_api_url = None` |

**El módulo descargable de ESMFold no habilita ESMFold.** El manifiesto ofrece
8.4 GB de pesos (`esmfold-weights` → `esmfold/models/`), pero **ningún código
carga pesos locales**: `services/esmfold/service.py` es un cliente HTTP y nada
arranca un proceso que los sirva. Descargarlos hoy no cambia nada. Es una
decisión de producto pendiente: **quitar el módulo del manifiesto o construir el
sidecar que lo consuma**; no puede publicarse una descarga de 8.4 GB que no
habilita la función que anuncia.

### Qué hacía la aplicación cuando el motor no estaba

**En la ruta de moléculas pequeñas, bien:** el preflight del caso bloquea. Sin el
binario, `MOTOR_DOCKING_DISPONIBLE` pasa a `bloquea` con su motivo —«el fallback
silencioso no forma parte del contrato del caso»— y cualquier motor que no sea
Vina o QuickVina cae en `RUTA_PREFLIGHT_SOPORTADA`, también bloqueante.

**En la ruta peptídica, mal.** `run_peptide_docking_helper` caía a Vina con
`exhaustiveness=4` **y una caja fija de (20, 30, 28) con 30 Å de lado** cuando el
caso no declaraba una. Eso no es un resultado degradado: es un docking en un sitio
arbitrario del receptor, presentado como el resultado del caso. El aviso lo
llamaba «fallback rápido de compatibilidad».

### Corregido

1. **Sin caja declarada, no hay corrida.** El motor ausente lanza `RuntimeError`
   nombrando el motor en vez de inventar el sitio de unión.
2. **Con caja, la sustitución se declara.** El aviso pasa a `MOTOR SUSTITUIDO`,
   nombra el motor que se pidió, dice que la pose la produjo Vina y prohíbe
   comparar ese resultado con uno plegado.
3. **`GET /evaluation/engines`** publica qué puede ejecutar esta instalación:
   binario presente para Vina/QuickVina, URL configurada para los servicios
   externos. No hace red hacia ellos —configurado no es disponible, y el contrato
   los distingue.
4. **El modal consulta ese inventario** y apaga cada motor con su motivo en la
   descripción, con la etiqueta `SERVICIO APARTE` o `NO INSTALADO`. Mientras la
   respuesta no llega no apaga nada: un motor real no puede quedar deshabilitado
   por una consulta lenta.

Guardas: `backend/tests/test_motores_declarados_son_los_que_existen.py`
(6 pruebas). Una de ellas fija que **Vina es el único disponible de fábrica**: si
algún día se empaqueta QuickVina o se levanta un sidecar, esa prueba falla y hay
que actualizarla a propósito, porque la promesa del menú habrá cambiado.

El test de contrato peptídico se reescribió: el anterior **fijaba la caja
inventada** —`target_center == (20.0, 30.0, 28.0)`— como comportamiento esperado.

---

## ENG-002 — infraestructura de motores descargables (2026-09-01)

El addendum anterior cerraba con una decisión pendiente: retirar el módulo de
ESMFold del manifiesto o construir lo que lo consuma. **Se construyó.**

### Qué faltaba, exactamente

El servicio de ESMFold **ya existía** en este árbol, en `<raíz>/esmfold/`. No
funcionaba por cuatro razones independientes, y cada una habría bastado:

1. **El instalador no lo copiaba.** `bundle_helper` copia `backend/`, `rescoring/`,
   `tools/` y `data/`. `esmfold/` no estaba en la lista: el instalador salía sin
   el servicio, así que los pesos descargados no tenían quién los sirviera.
2. **Nadie lo encendía.** El backend hablaba con `localhost:8100` como si algo
   escuchara ahí. Nada lo arrancaba.
3. **Cargaba el modelo por su nombre.** `from_pretrained("facebook/esmfold_v1")`
   resuelve contra HuggingFace: ignoraba el `model_dir` que el propio predictor
   registra en su log y **volvía a descargar 8.4 GB** en una aplicación que
   declara cero red implícita.
4. **El módulo descargable estaba incompleto.** `from_pretrained` necesita
   `config.json`, `vocab.txt`, `tokenizer_config.json` y
   `special_tokens_map.json` además del tensor. El manifiesto bajaba sólo
   `pytorch_model.bin`: **8.4 GB que por sí solos no cargan**.

Y uno más, que apareció al encenderlo por primera vez: el servicio se escribió
con la sintaxis de structlog (`log.info("evento", clave=valor)`) sobre un
`logging.Logger` pelado. Reventaba en el arranque con `Logger.info() got multiple
values for argument 'msg'`, en la línea que anuncia el predictor creado. **No
llegaba a servir una sola petición.** Que nadie lo hubiera visto dice lo que hay
que saber sobre si este motor estaba conectado.

### Lo que hay ahora

| Pieza | Dónde | Qué hace |
|---|---|---|
| Catálogo | `backend/services/motores/catalogo.py` | Único sitio que sabe qué motores hay, qué archivos necesita cada uno, qué librerías, y en qué estado está |
| Supervisor | `backend/services/motores/sidecar.py` | Enciende el proceso, drena su salida, espera a `/health`, lo apaga. Idempotente, y con `atexit` |
| Servicio | `backend/sidecars/esmfold/` | Movido desde `<raíz>/esmfold/`, que es el árbol que el instalador **sí** copia |
| Contrato | `GET /evaluation/engines` | Estado por motor con su motivo y su acción |
| Encendido | `POST /evaluation/engines/{id}/encender` | Explícito e idempotente |
| Tokenizer | `bundle_helper` paso 4b | Los KB viajan en el instalador; los GB se descargan |

**Cinco estados, porque llevan a cinco acciones distintas.** `no_instalado` →
descargar, y el aviso dice cuánto pesa antes de empezar; una descarga a medias se
distingue de no haber empezado. `dependencias_faltantes` → no se arregla
descargando otra vez. `instalado_apagado` → encender. `listo` → el único que
declara `disponible: true`, y sólo cuando `/health` contesta. `error` → con el
motivo del arranque fallido.

**El pipeline enciende lo que ya está instalado.** Si la corrida eligió ESMFold y
está en disco, `run_peptide_docking_helper` lo arranca —pedirle al investigador
dos gestos para una decisión sería absurdo—. Lo que **no** hace es descargar:
bajar 8.4 GB dentro de una corrida, sin avisar y sin poder cancelarla, no lo
decide el pipeline.

### Verificado

El ciclo completo corre en **modo stub**, que existe justamente para esto: probar
lanzar, sondear, servir y apagar sin depender de un checkpoint de 8.4 GB ni de una
GPU. Comprobado de punta a punta —supervisor → sidecar → cliente del backend—:
5 poses devueltas, con el aviso `Resultado STUB: no usar para investigación`.

`backend/tests/test_motores_descargables.py` (12 pruebas) fija que el catálogo
exija el tokenizer, que el instalador lo lleve, que el módulo del launcher exista,
que cada estado traiga su acción, que el checkpoint se cargue con
`local_files_only`, que el servicio viva en el árbol empaquetado y que no quede
una copia fuera. Suites: backend **1303 passed**, frontend **658 passed**.

### Lo que falta para que un usuario lo use de verdad

1. **`transformers` en el runtime empaquetado.** `python-embed` trae torch,
   fastapi, uvicorn y rdkit, pero no `transformers`. Sin él los pesos no cargan.
   `backend/requirements-desktop.txt` ya lo declara (`transformers>=4.45.0`), así
   que es aprovisionar el runtime y regenerar el SBOM — no un cambio de diseño.
   Mientras tanto la aplicación lo dice con todas las letras en vez de fallar.
2. **Subir el resto de pesos** a `huggingface.co/srcacahuate/moldesign-models` y
   añadirlos al manifiesto. Para cada motor nuevo: una entrada en `modules` del
   manifiesto y otra en `CATALOGO`, con sus archivos, su tamaño, sus dependencias
   y su `SidecarSpec`. El resto —estado, encendido, interfaz, avisos— ya funciona
   para todos.
3. **Una corrida real con los 8.4 GB** en modo `fast`. El modo stub prueba la
   infraestructura; no prueba la ciencia.

---

## ENG-003 y cierre de motores — 2026-09-01, antes de la build pública

### `diffpepdock` era una etiqueta sin motor detrás

Estaba en el `Literal` de `EvaluationSubmitRequest`, en los motores peptídicos
explícitos de `pipeline/runner.py` y en la detección de péptidos de
`queue_handler`. La API lo aceptaba y el pipeline lo trataba como elección válida.

**No existía ninguna rama que lo ejecutara.** El despacho distingue `colabfold`,
`esmfold-experimental` y —en el `elif` final, sin condición sobre el motor— todo
lo demás, que va a ESMFold. No hay `services/diffpepdock/`, ni pesos, ni sidecar.

El resultado no era «motor no disponible». Era peor:

> se ejecutaba **ESMFold** y la corrida quedaba registrada como **DiffPepDock**,
> porque `_protocol_engine` devuelve el motor que pidió el usuario.

Una mentira de procedencia en el dossier: el documento reproducible nombraría un
método que no se usó, y nadie podría explicar por qué no se reproducen los
números. Retirado del contrato en las seis superficies —API, pipeline, despacho y
los tres archivos del frontend—. Vuelve cuando exista, con implementación y pesos.
`test_diffpepdock_no_se_hace_pasar_por_esmfold.py` incluye la guarda general que
lo habría atrapado: **todo motor peptídico del contrato tiene que tener una rama
que lo despache**.

### `transformers` en el runtime empaquetado

Instalado en `python-embed`: `transformers 4.52.0` —la versión que
`backend/requirements.txt` fija—, con `tokenizers 0.21.4` y `regex`. Todo
Apache-2.0: **ninguna obligación de copyleft nueva**. El SBOM pasa de 170 a 173
distribuciones y sus cuatro avisos de licencia siguen siendo los mismos de antes
(GridDataFormats, meeko, paramiko, rpc-websockets).

`huggingface_hub` bajó de 1.23.0 a 0.36.2 por resolución de dependencias.
Comprobado que la única llamada del backend —`hf_hub_download(repo_id=…)` en
`services/ai/model_registry.py`— sigue siendo compatible, y que el backend importa.

### ESMFold cargado de verdad

No con el stub: con el checkpoint completo de 8.44 GB y **sin red**
(`HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1`). `EsmForProteinFolding` se construyó
desde el directorio local. Los dos avisos que emite —`contact_head` no
inicializado y `position_embeddings` sin usar— son los normales al cargar este
checkpoint para plegar, no un problema de la descarga.

Con esto la cadena entera queda demostrada: **descarga → disco → carga sin red →
proceso → cliente del backend → poses**.

### Estado del repositorio de modelos

`huggingface.co/srcacahuate/moldesign-models` contiene hoy:

| Archivo | Estado |
|---|---|
| `v1.0.0/base-v1.0.0.zip` | publicado |
| `v1.0.0/esmfold/models/pytorch_model.bin` | **publicado**, y su SHA-256 coincide con el manifiesto |
| `launcher-manifest.json` | publicado, desactualizado |

Pendiente de publicar, y son kilobytes: los cuatro archivos del tokenizer
—`config.json`, `vocab.txt`, `tokenizer_config.json`, `special_tokens_map.json`—
y el manifiesto al día. **No bloquean la build**: esos cuatro viajan en el
instalador desde el paso 4b de `bundle_helper`, y la aplicación no lee el
manifiesto remoto, usa el compilado.

`scripts/publicar_modelos_hf.py` lo deja hecho con un comando. Antes de subir
nada recalcula el SHA-256 y se niega si no coincide con el manifiesto; sin
`--subir` sólo informa; y no publica lo que viene de otro repositorio —el GGUF de
Qwen se descarga del repositorio oficial de Qwen, y duplicarlo aquí crearía una
copia que se queda atrás—.

    set HF_TOKEN=hf_...
    python scripts/publicar_modelos_hf.py --raiz-archivos D:/moldesign-app          # informe
    python scripts/publicar_modelos_hf.py --raiz-archivos D:/moldesign-app --subir  # publica

### Lo que NO se puede publicar, y por qué

DiffDock, ColabFold y RFdiffusion **no tienen pesos que subir**: no hay ninguno en
este equipo, y subirlos tampoco bastaría. Cada uno necesita su propio motor de
inferencia —ColabFold, además, bases de datos de MSA que se miden en cientos de
GB—, y en este árbol son clientes HTTP sin servicio detrás. Añadirlos es un
proyecto por motor, no una descarga.

La infraestructura ya está lista para recibirlos: una entrada en `modules` del
manifiesto y otra en `CATALOGO` con sus archivos, tamaño, dependencias y
`SidecarSpec`. Estado, encendido, interfaz, avisos y guardas funcionan para
cualquier motor que entre por ahí.
