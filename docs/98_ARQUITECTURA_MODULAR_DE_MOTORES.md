# 98 — Arquitectura modular de motores: de «un pipeline con Vina» a un entorno de trabajo

**Estado:** plan de arquitectura, sin código. **Versión objetivo: 1.0.3** (no entra en 1.0.2). Fecha: 2026-10-07.
**Decisión del propietario:** MolDesign → Evaluación → modularidad. Cambiar de motor tiene que ser fácil y útil, y
el producto debe poder crecer hacia un «IDE para el descubrimiento de fármacos», parecido a VS Code.

Relación con otros documentos:

- [`74`](74_ARQUITECTURA_DISPATCHER_DE_PROTOCOLOS.md) decide **qué flujo científico** corre para cada caso (M4, M5-Zn,
  péptidos). Este documento decide **quién ejecuta cada paso** de ese flujo. Son dos capas, y la de abajo es la que
  `ProtocolPlan.selected_engine` y «capacidades realmente instaladas» del doc 74 ya dan por supuesta.
- [`96`](96_DISENO_MOTOR_EXTERNO_VIA_API.md) y [`97`](97_PLAN_MOTOR_EXTERNO_VIA_API.md) son el caso concreto
  «motor externo por API (NVIDIA)». Aquí está la arquitectura general que ese caso va a usar.

---

## 1. La idea, y dónde acaba la analogía con VS Code

| VS Code | MolDesign |
|---|---|
| Extensión, con un manifiesto | **Motor**, con un manifiesto |
| Puntos de contribución (lenguajes, depuradores) | **Capacidades** (`pose.generate`, `pose.score`, `structure.predict`…) |
| *Extension host* (proceso aparte) | **Host de motores**: en proceso, subproceso, sidecar o API remota |
| Language Server Protocol | **Protocolo de motores**, versionado |
| Formularios de ajustes generados de un JSON Schema | **Formulario de parámetros** generado del esquema del motor |
| Workspace Trust | **Confianza y consentimiento por destino** (`docs/37`, `docs/96`) |
| Marketplace | Fase tardía; antes, un catálogo curado |

**Donde la analogía se rompe, y es lo que importa:** VS Code no tiene que demostrar que lo que muestra es verdad.
MolDesign existe para decir cuándo *no* confiar en un número. Por eso la API de un motor es **más estrecha** que la de
una extensión: **el motor aporta observaciones; el núcleo hace las afirmaciones.** El núcleo decide qué se valida, qué
se ordena, qué se muestra y cuándo se abstiene. Un motor no puede declararse válido.

## 2. Diagnóstico: cuánto depende hoy el backend de Vina (medido)

No es un nombre repetido, es una dependencia de diseño:

| Dónde | Qué lo ata a Vina |
|---|---|
| **107 archivos** de producción mencionan Vina (328 líneas en `services/docking`, 215 en `core`, 84 en `api`, 79 en `scoring`, 69 en `services/chemistry`, 60 en `services/dossier`) | Extensión, no un punto |
| `core/models.py` | `DockingPose.affinity` es «energía de Vina» y un validador exige que sea negativa; `pdbqt_block`; `parsing_source` incluye `"vina_stdout"`; `vina_version`, `vina_random_seed` |
| `core/database.py` | Columnas `affinity_kcal` («donde vive el score de Vina»), `vina_version`, `vina_random_seed`, `stacking_vina_weight` |
| `scoring/engine.py` | Las cuatro componentes del stacking son `vina`, `xgb`, `gnn`, `clgnn`; el ranking de M4 es «Vina solo»; hay métricas `sile_vina` y `fq_vina_proxy` |
| **50 archivos** hablan de PDBQT | El formato canónico del receptor y del ligando preparados es el de Vina |
| Protocolo sellado `docking_protocol/v2` | Sus parámetros son los de Vina: exhaustividad, semilla, número de poses |
| `core/config.py` | Bloque `vina_*`, `docking_engine`, `qvina2_executable_path` (un camino que no se ejecuta) |
| Dos ejecutores del pipeline | `queue_handler.py` (1723 líneas) y `runner.py` (1207) repiten la lógica (el doc 74 las estima en unas 2600 duplicadas) |
| `run_vina_docking` | **5 llamadas en 4 archivos:** `queue_handler`, `runner`, `selectivity` y dos en `api/routers/pro_features.py` |

La buena noticia: **el punto de entrada de las poses está acotado** (esas 5 llamadas) y ya hay precedentes de
modularidad que se pueden generalizar: el inventario de `/evaluation/engines` con su taxonomía `requiere`
(`binario_empaquetado`, `binario_externo`, `servicio_externo`, `descarga_bajo_demanda`), el ciclo de vida de sidecar
de `services/motores` (encender, comprobar, apagar), el registro de etapas de `services/pipeline/registry.py` y el
registro de proveedores de IA de MolChat con claves por cuenta.

## 3. El modelo

### 3.1 Capacidades, no «motores de docking»

El hueco no es «docking». Son verbos que varios motores pueden ofrecer:

| Capacidad | Ejemplos hoy o en el horizonte |
|---|---|
| `pose.generate` | Vina; DiffDock (API); Boltz-2 y OpenFold (co-plegado); un compuesto «ESMFold + Vina» |
| `pose.score` | Vina `--score_only`; los reescoradores locales (XGBoost, CL-GNN); MM-GBSA |
| `pose.validate` | La validez física local (hoy `pose_physical_validity`) |
| `structure.predict` | ESMFold, OpenFold, búsqueda de MSA |
| `ligand.prepare` / `receptor.prepare` | RDKit y Meeko hoy |
| `property.predict` | ADMET-AI |
| (futuro) `simulation.*`, `design.*` | MD, FEP, generación (GenMol, MolMIM) |

Empezar con tres (`pose.generate`, `pose.score`, `structure.predict`). Las demás se añaden cuando exista un motor
real que las necesite, no antes.

### 3.2 Manifiesto del motor (declarativo)

Lo que un motor **declara**, y la interfaz y el núcleo **leen** sin código específico:

```text
id, versión, protocolo_de_motores: 1
tipo:            integrado | subproceso | sidecar | api_remota
capacidades:     [pose.generate, …]
acepta:          entidades (molécula pequeña, péptido, proteína) y formatos (SMILES, SDF, PDB)
parametros:      un JSON Schema            ← genera el formulario y el «No aplica»
requiere:        red, claves, GPU, descarga  (reusa la taxonomía de `requiere`)
salida_de_datos: qué abandona el equipo   ← alimenta el consentimiento
determinismo:    con_semilla | estocástico | versionado_por_el_servicio
afirma:          estado científico propuesto y dominio de aplicabilidad (el núcleo lo contrasta)
```

El formulario de parámetros del diálogo deja de ser código por motor: Vina declara caja, exhaustividad y poses;
DiffDock, número de poses y pasos; ESMFold, nada. **El «No aplica» sale solo del esquema.**

### 3.3 Resultado neutro: poses y señales

La pieza que más pesa. Se separa lo que el motor **observó** de lo que el núcleo **interpreta**:

```text
PoseSet   poses (coordenadas, rango, conformación de origen, correspondencia de átomos)
Señal     nombre, valor, unidad, dirección (menor_es_mejor | mayor_es_mejor | ninguna),
          tipo (observación | interpretación), productor (motor@versión),
          dominio, comparable_con (lista explícita, vacía por defecto)
```

La afinidad de Vina pasa a ser **una señal más** (`vina_affinity`, kcal/mol), con su campo literal intacto. La
confianza de DiffDock es otra (sin unidad, **no comparable** con kcal/mol). La afinidad predicha de Boltz-2 es otra
(`log10 IC50`). **Nunca se mezclan sin una calibración declarada**: es la «separación de señales» del doc 74 §5.3
elevada a regla del modelo. La interfaz pinta las columnas a partir de los metadatos de cada señal, así que un motor
nuevo añade columnas **sin tocar el frontend**.

### 3.4 Procedencia que escribe el host, no el motor

La lección de `diffpepdock` (ENG-003): una corrida acabó etiquetada con un nombre que no había producido el
resultado. Un nombre que el motor se pone a sí mismo no es procedencia. El host escribe **qué manifiesto, qué
binario o qué servicio** respondió, con hashes y versión reportada, y lo contrasta con lo que el motor dice de sí.

### 3.5 El formato neutro del sistema

Hoy el artefacto canónico es `prepared.pdbqt` (Vina). Para que un motor distinto reciba lo mismo, el sistema se
guarda en un **formato neutro** —receptor PDB limpio, ligando SDF, parámetros, hashes— y **cada adaptador deriva el
suyo** (PDBQT para Vina, PDB y SMILES para DiffDock). Ese formato neutro es, además, el **paquete estructural
transferible** de la identidad del producto (readiness FEP-ready): se resuelven a la vez.

## 4. Lo que el núcleo garantiza siempre (invariantes)

1. **La procedencia la escribe el host** (§3.4).
2. **Ninguna sustitución silenciosa.** Si el motor pedido no responde, la corrida falla o se abstiene; no cae a otro.
   (Hoy la ruta de ESMFold sí cae a Vina con exhaustividad 4; la migración la corrige.)
3. **Las señales llevan unidad y dominio** y no se combinan sin calibración. El orden lo fija la **política del
   protocolo**, no el motor.
4. **La validación de las poses la hace el núcleo**, con su propia vara. DiffDock devuelve un 21 % de poses
   físicamente válidas; su confianza no lo arregla.
5. **La salida de datos está declarada y consentida** antes de enviar nada.
6. **El determinismo está declarado** y gobierna la caché y la reproducibilidad: un servicio remoto cambia con su
   versión, así que se guarda su respuesta y se reutiliza por hash.
7. **Ningún motor entra en el ranking sin pasar los gates del doc 74 §12.** Mientras tanto, sus señales **se
   muestran, no se ordenan**.

## 5. Migración por estrangulamiento (sin romper lo que funciona)

Cada paso es entregable por sí solo y deja los 8 goldens iguales **byte a byte**. Las estimaciones son mías, sin
medir.

| # | Paso | Criterio de salida | Esfuerzo |
|---|---|---|---|
| 0 | **Contrato y envoltorio.** Se define la interfaz de motor y un `VinaEngine` que envuelve `run_vina_docking` **sin cambiar el comportamiento**. Las 5 llamadas pasan por el registro | Goldens idénticos; una **guarda** (como `check_openbabel_boundary`) prohíbe importar `vina_service` fuera del adaptador | 3–5 d |
| 1 | **Modelo neutro, aditivo.** Se añaden `signals` y `provenance` junto a los campos de Vina; esquema de base de datos 30 **sólo aditivo**; lectura retrocompatible de corridas antiguas | El dossier de una corrida antigua sale idéntico; prueba de migración | 5–8 d |
| 2 | **ESMFold como motor compuesto** (`structure.predict` + `pose.generate`). Es el primer motor que no es Vina y valida el diseño con algo que ya existe y tiene ciclo de vida de sidecar | Golden peptídico idéntico; desaparece la caída silenciosa a Vina | 4–6 d |
| 3 | **`pose.score`** y `vina --score_only` (hoy no existe en el backend). Es el sustrato de reescorar poses ajenas y de evaluar una pose puesta a mano | Misma afinidad que la de la búsqueda sobre la pose que Vina devuelve | 2–3 d |
| 4 | **Host remoto**, primer conector: DiffDock de NVIDIA (`docs/97`) | Criterios de `docs/97` §5 | 4–6 d |
| 5 | **Interfaz dirigida por manifiestos:** selector de motor, formulario desde el esquema, columnas desde las señales, consentimiento desde la salida de datos | El diálogo no menciona ningún motor por nombre en el código | 6–10 d |
| 6 | **Converge con el dispatcher** (doc 74): `ProtocolPlan.selected_engine` sale del registro | Un caso con motor no instalado se abstiene de forma explicable | por definir |
| 7 | **Motores de terceros en local** (manifiesto + proceso) y confianza | Fuera de este plan hasta que 0–5 estén medidos | — |

**Pasos 0–5: unas 5–8 semanas.** Los pasos 0 y 3 son baratos y valen aunque todo lo demás se retrase.

Sobre **los dos ejecutores** (`queue_handler.py` y `runner.py`): el paso 0 sustituye las llamadas, que son
idénticas en los dos, así que es mecánico y **no exige unificarlos antes**. Unificarlos (doc 74, fase 6) puede ir
después sin rehacer nada.

## 6. «Cambiar de motor» tiene que ser **útil**, no sólo posible

- **Misma evaluación, dos motores, lado a lado.** El historial del caso ya muestra qué motor usó cada corrida; la
  comparación de dos corridas es la vista natural. El **acuerdo entre motores** (RMSD entre sus mejores poses) es una
  señal de confianza que ningún motor tiene aislado (hipótesis a medir, `docs/97` §2).
- **Un kit de conformidad.** Cualquier motor, propio o de terceros, tiene que pasar las mismas pruebas: procedencia,
  abstención ante fallo, determinismo declarado, salida de datos declarada, señales con unidad. Es lo que hace que
  «añadir un motor» no sea una apuesta, y lo que más se parece al *test suite* de un servidor de lenguaje.
- **Una barrera de licencia gratis.** Un motor en otro proceso mantiene la frontera de AGPL, GPL y LGPL que ya
  existe para Open Babel y Molcy. Por eso la API **no carga código de terceros dentro del backend**.

## 7. Lo que NO se hace

- **Cargar módulos arbitrarios de Python dentro del proceso del backend.** Ni por seguridad ni por licencias.
- **Una API pública de extensiones antes de tener tres motores reales** (Vina, ESMFold compuesto, DiffDock remoto).
  Con uno, el diseño se ajusta a ese uno; con tres, se ve lo que es común.
- **Renombrar o borrar los campos de Vina.** La migración es aditiva: `affinity_kcal` y compañía se quedan.
- **Mezclar señales de motores distintos** en un número «mejor».
- **Un marketplace** antes de que el kit de conformidad exista.

## 8. Riesgos

1. **`affinity_kcal` es ambiguo en corridas antiguas**: antes del esquema 16 podía ser un valor de XGBoost. El
   modelo neutro no puede heredar esa duda: las corridas antiguas entran con la señal marcada como «origen no
   verificable».
2. **El ranking y las puntuaciones** (`scoring/engine.py`) se calculan sobre componentes entre las que está Vina («Vina
   solo» en el ranking de M4). Con otro motor, ¿qué número encabeza? Hay que decidirlo antes del paso 5 (§9.4).
3. **El alcance.** «IDE» es una dirección, no un entregable. El riesgo es construir la plataforma antes de tener el
   segundo motor. El orden de §5 está pensado para impedirlo.
4. **El coste de la interfaz** (paso 5) es el menos conocido: depende de cuánto frontend asume hoy «Vina».

## 9. Decisiones que son tuyas

1. **Formato del manifiesto:** TOML o JSON.
2. **¿Todo fuera de proceso?** Recomiendo que sí, salvo los motores integrados (Vina, RDKit).
3. **¿Unificar los dos ejecutores antes o después del paso 1?** Recomiendo después.
4. **Qué número encabeza la evaluación cuando el motor no es Vina.** Propongo: ninguno encabeza hasta que el motor
   pase sus gates; se muestran sus señales y la afinidad de Vina reescorada sobre su pose, etiquetada.
5. **Orden de los motores reales:** propongo Vina, ESMFold compuesto, DiffDock remoto.
