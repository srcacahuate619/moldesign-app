# 97 — Plan: dar vida al motor externo «Vía API» (NVIDIA)

**Estado:** plan, sin código. **Versión objetivo: 1.0.3** (no entra en 1.0.2). Fecha: 2026-10-07. Continúa
[`docs/96_DISENO_MOTOR_EXTERNO_VIA_API.md`](96_DISENO_MOTOR_EXTERNO_VIA_API.md), que fijó *dónde* encaja la plaza
en el menú. Este documento fija *cómo se construye* y en qué orden.

> **La arquitectura general de motores** (capacidades, manifiesto, resultado neutro, migración) está en
> [`docs/98_ARQUITECTURA_MODULAR_DE_MOTORES.md`](98_ARQUITECTURA_MODULAR_DE_MOTORES.md). Este documento es el caso concreto
> de NVIDIA y se apoya en ella: su Fase 1 corresponde a los pasos 3 y 4 de ese plan.

**Lo que hay que decir primero.** Los experimentos anteriores con claves de NVIDIA (Boltz-2 y otros motores)
**no dejaron rastro** en el repositorio, en la memoria del proyecto ni en las carpetas hermanas que revisé, y el
propietario aclaró el 2026-10-07 que **no importan**: se empieza de cero con claves temporales. Lo único medido que
consta es el resultado de DiffDock vía NIM en `AGENTS.md`. Por eso la Fase 0 hace el mínimo con una clave, y todo
detalle de los endpoints de NVIDIA (rutas, esquema, polling, límites) está **por confirmar** ahí, no dado por cierto
aquí.

---

## 1. Punto de partida, verificado en el repositorio

| Hecho | Dónde | Consecuencia para el plan |
|---|---|---|
| DiffDock vía NIM, 19 complejos posteriores a su corte: 84 % RMSD < 2 Å, **21 %** poses físicamente válidas; su `position_confidence` está **anticorrelacionado** con la validez (filtrar por «alta confianza» baja al 14 %) | `AGENTS.md` | La confianza del proveedor no se muestra como evidencia. Hay que juzgar las poses **en local** |
| Los modelos de co-plegado (AlphaFold 3, Boltz-2, Protenix-v2) tienen un modo de fallo documentado en canales iónicos: colapsan la cavidad del poro | `backend/services/docking/anti_target_sitio.py` | Un externo no sustituye a las estructuras experimentales en el panel de anti-dianas |
| El cliente actual de DiffDock habla con un servidor genérico (`/predict`, `/health`, payload propio), **no** con el esquema de NIM. Usa `urllib` síncrono, 300 s y sin circuit breaker. Sus rutas están apagadas tras `MONTAR_ROUTERS_DORMIDOS` | `backend/services/diffdock/service.py`, `api/main.py` | Se reaprovecha la idea (degradación elegante), no el código |
| El circuit breaker ya existe, dentro del cliente de ESMFold | `backend/services/esmfold/service.py:111` | Subirlo a `utils/` y compartirlo |
| MolChat ya guarda claves de usuario **cifradas** (Fernet, clave derivada de `~/.moldesign/secret_key`), **por cuenta** (D-09), con **consentimientos ligados al destino** (MOLCHAT-NET-005) | `backend/services/ai/provider_config_store.py` | Es el patrón a reutilizar para las conexiones. Su límite honesto: la clave de cifrado vive en el mismo disco que el archivo |
| La política de integraciones exige: off por defecto, consentimiento visible, degradación elegante y una fila en su inventario (datos, endpoint, finalidad, default, cómo apagarla) | `docs/37_INTEGRATION_POLICY.md` | El motor externo es una integración nueva: lleva su fila |
| La validez física de poses ya se calcula en producción | `backend/services/chemistry/pose_physical_validity.py` (PROD-PV-H-01) | Es la palanca de confianza: la pose externa se juzga con la vara local |
| Hay una guarda que bloquea claves `nvapi-` al empujar | `scripts/check_push_publico.py` | La clave nunca entra a un artefacto; se prueba también en el dossier y los logs |
| El roadmap dice que no se compite en benchmarks de pose contra DiffDock, Boltz o Chai | `docs/50_ROADMAP.md` | El valor no es «mejores poses», es otra cosa (§2) |

## 2. Hipótesis de valor (a probar, no afirmada)

MolDesign existe para decir cuándo **no** confiar en un número. Un segundo motor independiente da exactamente
eso: **el acuerdo o el desacuerdo** entre la pose de Vina y la del motor externo (RMSD entre ambas) es una señal
de confianza que ningún motor aislado tiene. La Fase 5 mide si esa señal sirve. Hasta entonces el motor externo
es **experimental** y no se presenta como «mejor».

**Principio de diseño:** el motor externo es un **generador de hipótesis**. MolDesign valida y etiqueta en local
y nunca importa la confianza del proveedor como si fuera evidencia (lección de DiffDock).

## 3. Lo que los motores reales cambian en el diseño de docs/96

1. **No todos usan caja.** DiffDock hace *blind docking*; Boltz-2 co-pliega desde **secuencia + SMILES**. Cada
   conexión declara sus **capacidades**: qué entradas toma (estructura, secuencia, SMILES), qué parámetros
   expone (¿caja? ¿número de poses? ¿semilla?) y qué devuelve (poses, confianza propia, afinidad predicha).
2. **La columna de la caja vuelve a necesitar «No aplica» por motor.** Se retiró con los motores muertos; para un
   externo sin caja hay que reponerla, gobernada por las capacidades y no por una lista de ids.
3. **«`docking_engine` se queda en `vina`» (docs/96 §4) vale sólo si el externo entrega poses al pipeline.** Para
   co-plegado la estructura llega en **su** marco de coordenadas: hay que superponerla al receptor (por Cα)
   antes de compararla con la caja.
4. **Qué sale del equipo.** Boltz-2 pide la **secuencia** del receptor y DiffDock su **PDB**: hay que decir cuál,
   porque un receptor propio puede ser confidencial.

## 4. Fases

| Fase | Qué | Quién | Esfuerzo (estimación, sin medir) |
|---|---|---|---|
| **0** | **Spike con tu clave.** Un script suelto en `scripts/` (no sellado) llama a DiffDock y Boltz-2 de NIM con 3 casos de los goldens. Mide: rutas y esquema reales, async y polling, latencia, límites de la clave gratuita, tamaño de payload, si las poses vuelven en el marco del receptor, y los **términos de uso**. Sale una nota con payloads y respuestas reales (clave redactada) | backend | ½–1 día |
| **1** | **Capa de adaptadores.** `services/motores_externos/` con una interfaz común (`capacidades`, `verificar()`, `ejecutar()`); cliente `httpx` async con timeout, reintentos acotados y circuit breaker compartido. Alta de conexiones sobre el almacén cifrado de MolChat (extraer el cifrado a una utilidad común). `/evaluation/engines` añade `externos`; nuevos `POST` de alta y de «probar conexión». Nunca se devuelve la clave: sólo «guardada: sí/no». Pruebas con un **servidor falso local**, sin red | backend | 2–3 días |
| **2** | **Ejecución y trazabilidad.** En el pipeline, si hay motor externo: enviar → recibir → normalizar al marco del receptor → **validar en local** (`pose_physical_validity`, lector bajo `MF-33-H-COR`) → rescoring local. La procedencia sube a `docking_protocol/v3` con: `origen: "api"`, proveedor, **nombre y versión que reporta el servicio**, hash de la petición y de la respuesta, y la confianza externa **en un campo aparte**, nunca mezclada con kcal/mol. Si el servicio falla, la corrida **se abstiene o falla; no cae a Vina** | backend | 2–3 días |
| **3** | **Consentimiento y privacidad** (en paralelo a 2). Diálogo antes de la primera corrida y cada vez que cambie el destino: qué sale (SMILES, secuencia o PDB, tamaño), a qué host y bajo qué términos. Consentimiento ligado a destino (`guardar_consentimiento`). Insignia «ejecutado fuera del equipo» en la corrida y en el dossier. Fila nueva en `docs/37` | backend + interfaz | 1–2 días |
| **4** | **Interfaz** (para Opus 5.5). La plaza pasa a lista de conexiones; alta con un preajuste «NVIDIA»; «Probar conexión»; tarjeta elegible sólo si está verificada; tipo `MotorElegido` (docs/96 §3); caja con «No aplica» por capacidades; textos ES/EN; pruebas de que no hay clave en `localStorage`, URL ni payload | frontend | 2–3 días |
| **5** | **Validación científica**, cuando haya cómputo en la nube y en paralelo a la de ESMFold. En moléculas pequeñas: Vina frente a DiffDock-NIM y Boltz-2; RMSD, validez PoseBusters, tasa de abstención y, sobre todo, si el **acuerdo con Vina** predice el éxito. Se reutilizan los 19 complejos posteriores al corte de DiffDock. Criterios fijados antes de correr | ciencia | por definir |

**Total, Fases 0–4:** unos 8–12 días de trabajo. La Fase 0 decide si se integran los dos motores o sólo uno, y
puede reducir o ampliar el resto.

**Fase 0, ya preparada.** [`scripts/spike_nvidia_nim.py`](../scripts/spike_nvidia_nim.py) envía sólo datos públicos
(proteasa del VIH-1, indinavir y el PDB 1HSG de RCSB), lee la clave de un archivo **fuera del repo** o de
`NVIDIA_API_KEY`, la redacta en todo lo que escribe y guarda lo observado en `D:\moldesign-dev-data\spike-nvidia\`.
`--dry-run` valida las cargas sin red ni clave. Una prueba (`test_spike_nvidia_no_filtra_clave.py`) fija que la clave no
se filtra.

**Lo que la documentación pública confirma, y lo que no** (consultada el 2026-10-07):

- **Boltz-2:** toma polímeros por secuencia (hasta 4096 residuos y 12 cadenas) y hasta 20 ligandos por SMILES o CCD;
  devuelve estructuras en mmCIF y puntuaciones de confianza; la afinidad es opcional, sólo para un ligando y alarga
  la ejecución. Su ruta en el contenedor propio es `/biology/mit/boltz2/predict`.
- **DiffDock:** toma el ligando (SMILES, SDF o Mol2) y la proteína en PDB; devuelve poses en SDF con una confianza.
  Su ruta en el contenedor propio es `/molecular-docking/diffdock/generate`.
- **Condiciones:** el servicio alojado de prueba se rige por las *NVIDIA API Trial Service Terms of Use* (decisión 1
  de §6).
- **No confirmado:** la URL del servicio **alojado**, el formato exacto de la autenticación y el esquema alojado. Las
  páginas públicas no los dan; salen de la pestaña de código de build.nvidia.com o de ejecutar el spike. Las rutas del
  script son suposiciones y el cuerpo de un 4xx dirá cuáles fallan.

## 4b. Resultados de la Fase 0 (2026-10-07, clave temporal del propietario)

Sólo se enviaron datos públicos: un fragmento de KRAS, la proteasa del VIH-1 con indinavir y EGFR (1M17) con
erlotinib. Lo guardado está en `D:\moldesign-dev-data\spike-nvidia\` y no contiene la clave.

**Quedó confirmado** lo que la documentación pública no daba (la lista «no confirmado» de arriba ya no vale):

- **URL alojada:** `https://health.api.nvidia.com/v1/biology/mit/<modelo>/…`; para Boltz-2, `…/boltz2/predict`, y para
  DiffDock, `…/diffdock`.
- **Autenticación:** `Authorization: Bearer nvapi-…`. El ejemplo de `localhost:8000` del propietario es el de un NIM
  **propio**, sin autenticación; no sirve tal cual contra la API alojada.
- **Es síncrono** en lo observado: ninguna respuesta fue 202 y no hubo sondeo. Cada una trae `nvcf-reqid` y
  `nvcf-status`. **No se vio ninguna cabecera de límite de uso** en cinco llamadas.

| Motor | Resultado |
|---|---|
| **DiffDock** | **HTTP 200 en 2,0 s**, 218 KB. El cuerpo que se había supuesto se aceptó a la primera. Devuelve `ligand_positions` (5 poses en molblock, sin hidrógenos), `position_confidence` (5 valores, de +0,109 a −0,333, ordenados de mayor a menor), `protein` (el PDB de vuelta, 202 KB), `trajectory`, `status` y `details`. Las 5 poses quedan dentro de la caja del catálogo y a **0,4–0,7 Å del centro del sitio**: encuentra el bolsillo correcto |
| **Boltz-2** | **Bloqueado por NVIDIA.** Cuatro intentos, con la carga mínima y con la completa, dieron HTTP 422 en menos de 1,3 s con `InfrastructureError … CUDA error: an illegal memory access` y `nvcf-status: errored`. Es un fallo de GPU del servicio alojado, no de nuestra entrada ni de la clave |

Qué cambia en el plan:

1. **El adaptador de DiffDock es directo** y puede arrancar la Fase 1; Boltz-2 queda detrás de una comprobación
   periódica hasta que NVIDIA lo arregle.
2. **Lo medido es el sitio, no la pose.** Para el RMSD hace falta el ligando del cristal de 1M17, que no está en el
   equipo (el archivo local es sólo proteína, la preparación quita ligando y aguas). Habría que bajarlo de RCSB
   (unos 200 KB). Tampoco se comprobó si el `protein` devuelto conserva el marco de coordenadas de entrada.
3. **Sin medir todavía:** límites de uso y ritmo, el comportamiento 202 con entradas grandes, y los demás modelos del
   catálogo (OpenFold3, OpenFold2).
4. **Qué cabe en el hueco.** Del catálogo de build.nvidia.com, encajan Boltz-2, OpenFold3 y OpenFold2 (estructura de
   complejo), DiffDock (docking) y MSA-search (preparación del plegado). GenMol y MolMIM (generación), RFdiffusion y
   ProteinMPNN (diseño) y Evo2 (ADN) son otra cosa: no devuelven la pose de un ligando conocido y no caben en el
   contrato «pose + validación local». Propongo que el hueco se limite a motores que devuelven una **pose o un
   complejo**.

## 4c. Compatibilidad con el resto de MolDesign (análisis del 2026-10-07)

**¿Puede «SMILES + receptor (del catálogo o propio) + motor externo + Evaluar» funcionar con todo lo demás? Sí,
con un puente bien definido.** La etapa de docking es una sola función (`_dock_una`, en
`backend/services/pipeline/runner.py`) que devuelve un `DockingResult`; `xgb`, `clgnn`, la selectividad, los
hotspots, la validez física, el dossier y el PDF leen de ese objeto. Basta con que el motor externo produzca un
`DockingResult` **verdadero**. Lo que éste exige es lo que una pose externa no trae: cada `DockingPose` lleva
`affinity` (kcal/mol de Vina) y `pdbqt_block`, y el reescorado recibe `vina_score` más ese bloque. El repositorio no
fabrica números (la ruta de ESMFold devuelve `None` cuando no hay afinidad), así que el puente es:

1. **Enviar lo mismo que vería Vina:** el receptor que MolDesign ya prepara y el SMILES ya protonado, con su tautómero.
2. **Recibir las poses** (SDF).
3. **Casar los átomos con el grafo del SMILES** y guardar el SDF de poses.
4. **Convertir cada pose a PDBQT** con Meeko.
5. **Reescorar en local con `vina --score_only`.** Es la pieza nueva: hoy el backend no usa `--score_only` ni
   `--local_only`. Da la afinidad en la misma unidad y con la misma función que el resto de corridas.
6. **Validar en local y declarar la procedencia:** `engine_efectivo` es el externo, **nunca «vina»**; la confianza del
   proveedor va aparte; el protocolo sube a `docking_protocol/v3`.

La pose tiene que volver en el marco de coordenadas del receptor enviado. DiffDock devuelve también la proteína y no
se comprobó que coincida; para co-plegado (Boltz-2) habría que superponer. Por eso DiffDock va primero.

| Pieza | Con un motor externo |
|---|---|
| Propiedades, SA, generación 3D | Sin cambios: corren antes del docking |
| `xgb`, `clgnn` | Compatibles tras el reescorado local, **con reserva**: se calibraron sobre poses de Vina. Hay que declarar que la pose viene de otro generador |
| Validez física, hotspots, interacciones | Compatibles: sólo necesitan coordenadas |
| Dossier, PDF, certificación | Hay que añadir «ejecutado fuera del equipo» y el bloque de procedencia; certificar algo generado por un tercero tiene que decirlo |
| **Selectividad** | **Bloqueada por diseño:** `validar_protocolo_panel` exige `engine == "vina"` y sin ensemble. La guarda funciona sola siempre que la procedencia diga la verdad sobre quién produjo la pose |
| Ensemble (K confórmeros) | No aplica: el motor genera sus propias conformaciones. Se deshabilita el control |
| Caja, exhaustividad, semilla | No son del motor externo. La caja sigue sirviendo para reescorar y contar hotspots |
| Caché | La huella de Vina (`_docking_cache_fingerprint`) no sirve: el servicio cambia con su versión. Se guarda la respuesta y se reutiliza por su hash |
| Batch y cohortes | Fuera al principio: privacidad, ritmo y coste |
| Receptor propio | Funciona, pero **sale del equipo**: el consentimiento tiene que decir el tamaño y las cadenas |

## 4d. Sobre un editor 3D de poses (feature 001)

**Recomendación: no es un requisito previo, y el motor externo va primero.**

1. **Los motores externos no consumen una pose puesta a mano.** DiffDock hace *blind docking* y Boltz-2 acepta
   restricciones (residuos de contacto, enlaces), no coordenadas. Una pose manual sólo la puede usar Vina en local, con
   `--score_only` o `--local_only`, que es justo la pieza del paso 5. Esa pieza es el sustrato común de las dos ideas:
   se construye una vez.
2. **La propia ficha 001 pone el adaptador de motores en P0 y la edición manual de poses en P2**, y avisa de que
   «posición manual ≠ docking» y de que no se debe reemplazar Ketcher.
3. **Una pose manual es una hipótesis del usuario**, no un resultado de búsqueda. Tiene que evaluarse con
   `--score_only`, pasar la validez física y quedar etiquetada así, para no invitar al sesgo de confirmación.
4. **Hoy no hay manipulación 3D en el visor** (no hay `TransformControls`, ni arrastre, ni edición). Sí hay Mol*,
   `3dmol`, `three` y `@react-three/drei`, y `PoseComparisonDialog` para comparar dos poses.

Escalones, de menor a mayor coste (estimaciones sin medir):

| Escalón | Qué es | Coste |
|---|---|---|
| 0 | Superponer la pose externa y la de Vina en el visor que ya existe, con el RMSD entre ellas: la señal de acuerdo | días |
| 1 | Mover y girar el ligando como cuerpo rígido con el receptor bloqueado y un botón «Evaluar esta pose» (`score_only` más validez) | 1–2 semanas |
| 2 | Barras de torsión del ligando, con restricciones | semanas |
| 3 | Editor 3D de átomos («Ketcher 3D») | meses; es otro producto (Avogadro, Chimera, Maestro) |

Orden propuesto: `score_only` → puente de DiffDock → conexión en la interfaz → escalón 0 → (si se pide) escalón 1.

## 5. Criterios de aceptación (lo que se prueba, no lo que se dice)

1. Sin conexión **verificada** no hay nada elegible (extiende ENG-001).
2. **Sin consentimiento no sale una sola petición**: una prueba que bloquea los sockets y comprueba que no hay
   intento de conexión.
3. La clave no aparece en logs, URL, `localStorage`, payload ni dossier (prueba con patrón `nvapi-` sobre todos
   los artefactos, como la guarda de `check_push_publico.py`).
4. Si el servicio falla, la corrida se **abstiene o falla** y no devuelve poses de Vina con otro nombre.
5. El dossier trae origen, proveedor, versión, hashes y la validez **local** de cada pose.
6. Todo corre en CI con un servidor falso; **nada** depende de la red ni de una clave real.

## 6. Decisiones que son tuyas

1. **Términos de uso.** La API gratuita de NVIDIA se ofrece para prueba y desarrollo. El producto es PolyForm
   Noncommercial y se venden licencias comerciales aparte. Hay que leer sus términos **antes** de ofrecerlo a
   usuarios (no es un dictamen legal).
2. **Clave del usuario, no del producto.** Recomiendo que cada persona traiga la suya. Una clave embebida
   implica coste, abuso y fuga.
3. **Dónde vive la clave.** Almacén Fernet de MolChat (rápido, protege contra leer el JSON, no contra quien tenga
   el perfil del usuario) o el almacén de credenciales de Windows vía Tauri (más fuerte, más trabajo).
4. **La promesa «sin red».** Opt-in por conexión y por corrida es lo que propongo; es una decisión de producto.
5. **Boltz-2 devuelve una afinidad predicha.** Sin validación no se muestra como resultado; se guarda como dato
   externo etiquetado.
6. **Los routers dormidos** `/docking/diffdock` y `/docking/colabfold` describen un servidor que no existe:
   reemplazarlos o borrarlos cuando llegue la Fase 1.
7. **ESMFold Pro** (docs/96 §7d): si se quiere, es la primera conexión de otro tipo, no una entrada fija.

## 7. Qué necesito de ti para empezar

- Qué motores quieres probar primero (propongo DiffDock y Boltz-2, que son los dos con API alojada en NIM).
- Una clave temporal entregada **sin que quede escrita en el repositorio, en la memoria ni en un commit**. Dos
  formas, de más a menos recomendable: (a) un archivo **fuera del repo**, por ejemplo
  `D:\moldesign-dev-data\secretos\nvidia.key`, que el script lee al ejecutarse y nunca imprime; (b) pegarla en el
  chat, sabiendo que queda en la transcripción de la sesión. En ambos casos conviene **revocarla al terminar**.
