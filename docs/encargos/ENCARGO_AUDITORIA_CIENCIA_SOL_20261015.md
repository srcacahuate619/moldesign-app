# Encargo: auditoría científica de MolDesign — GPT Sol 6.1

**Fecha del encargo:** 2026-10-15
**Commit anclado:** `bef67706` (rama `codex/release-hygiene`)
**Auditor:** GPT Sol 6.1
**Naturaleza:** tarea larga, en cuatro fases con puerta de aceptación. No se
espera que termine en una sesión. Se espera que **sobreviva** a varias.
**Idioma de todos los entregables:** castellano.

---

## 0. Antes de leer nada más

Tres frases que gobiernan este encargo:

1. **CIENCIA > CALIDAD > EFICIENCIA.** Si un cálculo es ambiguo, el sistema se
   abstiene y lo declara. Nunca fabrica un número ni disimula una incertidumbre.
2. **Un número sin su condición es un número falso.** Ejemplo vivo del propio
   repositorio: la validez física de PoseBusters pasa de 2,64 % a 99,48 % según
   el protocolo de reconstrucción de hidrógenos (`docs/papers/MF-33-H-COR.md`).
   La misma cifra, sin su condición, es propaganda.
3. **Si encuentras una afirmación que no puedas rastrear hasta una medida,
   trátala como un defecto y dilo.** Es la regla de cierre de `AGENTS.md`, y
   este encargo la convierte en instrumento.

Lee `AGENTS.md` completo antes de empezar. Está escrito para agentes y describe
lo que el producto **es hoy, medido**, no lo que aspira a ser. No lo audites
como marketing: audítalo como el inventario de afirmaciones que el propietario
cree verdaderas. Tu trabajo incluye decirle cuáles no lo son.

---

## 1. La pregunta que rige toda la auditoría

MolDesign no ejecuta FEP, no predice actividad biológica y no sustituye
validación experimental. Su propuesta de valor es más estrecha:

> **saber cuándo *no* confiar en un número, y transferir esa duda al siguiente
> cálculo junto con la evidencia.**

De ahí la pregunta que gobierna las cuatro fases:

> **¿Qué de lo que MolDesign afirma, detecta o calibra hoy sostiene esa promesa,
> y qué no?**

No audites si Vina es bueno: eso está publicado y medido (PoseBusters 2024:
Vina 58 %, DiffDock 12 % con validez física exigida). Audita si **este producto
dice la verdad sobre lo que Vina le da**.

---

## 2. Reglas de la auditoría (no negociables)

Estas reglas existen porque auditorías anteriores de este proyecto fallaron por
no tenerlas. Una auditoría que las incumpla se rechaza entera, no por hallazgo.

### 2.1 Evidencia

- **Toda afirmación del informe lleva `ruta:línea` o un SHA-256.** Sin
  excepción. Un hallazgo sin ruta no es un hallazgo: es una impresión.
- **Todo hallazgo lleva el comando exacto que lo reproduce** en el entorno de la
  sección 3, o la declaración de que no es reproducible por comando y por qué.
- **Prohibido inferir de un nombre.** Un fichero llamado `validado.json` no
  acredita nada. Un test llamado `test_calibracion` no prueba que haya
  calibración. Ábrelos.
- **Prohibido citar una cifra del repositorio como si la hubieras medido.** Si
  la citas sin volver a medirla, márcala `citada_no_verificada`. Si la mides,
  anota el comando. Las dos cosas son aceptables; confundirlas, no.
- **El documento no es el artefacto.** Este proyecto ya perdió un instalador por
  eso: 688 pruebas verdes sobre el *código* mientras la aplicación instalada
  tenía cinco fallos simultáneos. Si una afirmación es sobre lo que la build
  hace, mídela sobre la build, no sobre el `.py`.

### 2.2 Veredictos obligatorios

Cada entrada del ledger cierra con **uno** de estos, y la lista es cerrada:

| Veredicto | Significado |
|---|---|
| `SUSTENTADA` | hay una medida, con su condición, y la afirmación no la excede |
| `SOBREAFIRMADA` | hay medida, pero la afirmación dice más de lo que mide, o la emite sin su condición |
| `NO_TRAZABLE` | no se encuentra la medida que la sostendría |
| `FALSA` | hay medida y la contradice |
| `NO_VERIFICABLE` | no se puede decidir con el acceso de esta auditoría; **di qué haría falta** |

`NO_VERIFICABLE` no es un fracaso: es información. Usarlo honestamente vale más
que un veredicto inventado. **Lo que no vale es el silencio:** una afirmación
que mirabas y dejaste sin fila es un agujero en la auditoría.

### 2.3 Prerregistro y gate

- **Cada fase se prerregistra antes de mirar:** escribe pregunta, método,
  cohorte o muestreo, criterio de hallazgo y presupuesto en
  `fase_<x>/prerregistro.md`, y **no lo cambies después de ver resultados**. Si
  el método resulta inadecuado, escribe una enmienda fechada que diga qué viste
  antes de cambiarlo. Esa es la regla del laboratorio de este proyecto
  (`docs/49_PROGRAMA_EXPERIMENTAL_CIENTIFICO.md`, §2) y se te aplica igual.
- **No muevas el criterio después del resultado.** Ni para aprobar ni para
  reprobar.

### 2.4 Alcance

- **No propongas motores nuevos.** DiffDock y ColabFold están medidos y
  rechazados con razón escrita (`AGENTS.md`, «Por qué DiffDock y ColabFold no
  están»). Reabrirlos exige una medida nueva, no una opinión.
- **No propongas que el producto ejecute FEP.** No es el hueco que ocupa.
- **No audites estilo, tipado, rendimiento ni UX** salvo cuando degraden una
  afirmación científica (por ejemplo: una interfaz que muestra un número sin su
  condición **sí** es un hallazgo científico).
- **No amplíes el encargo.** Si ves algo grave fuera de alcance, escríbelo en
  `hallazgos_fuera_de_alcance.md` en una línea y sigue.

### 2.5 El repositorio

- **No edites nada del árbol.** Ni un `.md`. Tus entregables viven fuera (§3.3).
  Al terminar cada sesión, `git status` del worktree debe estar limpio.
- **No hagas commits ni push.** Nunca. Hay un hook `pre-push` que rechaza refs
  con rutas retenidas, y la rama de desarrollo no se publica.
- **No toques `scripts/artifacts_science/`.** Son artefactos sellados con
  hashes: cambiar un byte invalida el sellado de experimentos enteros.
- **No ejecutes `--force`, `init --force` ni nada que escriba sobre resultados.**
  Un `init --force` de este proyecto borra resultados; reusar un directorio de
  salida destruyó 102 resultados de `RS-03-PARAM-B`.

---

## 3. Entorno de trabajo

### 3.1 Worktree aparte (obligatorio)

Trabajas en un worktree propio, **nunca en `D:\moldesign-build`**. El árbol
principal tiene trabajo sin commitear de otras sesiones y nunca se le cambia de
rama.

```powershell
git -C D:\moldesign-build worktree add --detach D:\moldesign-worktrees\auditoria-ciencia bef67706
cd D:\moldesign-worktrees\auditoria-ciencia
python scripts\bootstrap_dev_tree.py --fetch
```

`bootstrap_dev_tree.py --fetch` baja los ~2,2 GB que **no viajan en el
repositorio** (el intérprete embebido, los motores nativos, la base sembrada) y
los coloca sin pisar nada rastreado. Sin ese paso no puedes ejecutar la suite ni
validar sellos, y confundirás «no está aprovisionado» con «está roto».

El worktree queda en HEAD desprendido en `bef67706`: **todo hallazgo se ancla a
ese SHA**. Si el propietario avanza la rama durante la auditoría, no sigas la
punta: anota la divergencia y termina la fase sobre `bef67706`.

### 3.2 Qué puedes ejecutar y qué no

**Sí:**

- la suite de backend con el intérprete que se distribuye, desde `backend/`:
  `..\python-embed\python.exe -m pytest tests -ra -p no:cacheprovider`
- la de `scripts/` y la de `rescoring/` igual que en `.github/workflows/ci.yml`
- los `--check` de `ci.yml` con python-embed: `validar_sellos.py`,
  `report_test_counts.py` (ojo: §5), `generate_openapi_contract.py`,
  `generate_runtime_inventory.py`, `generate_sbom.py`, `check_docs_links.py`,
  `check_stacking_weights_ui.py`, `check_model_license_boundary.py`
- scripts de medida que **sólo leen**: `scripts/medir_metales_del_sitio.py`,
  `scripts/invariancia_catalogo_receptores.py`, los de lectura de catálogo
- la suite de frontend (`npm run test:run`) si la necesitas para una afirmación
  de interfaz

**No, en esta auditoría:**

- **corridas nuevas de docking con Vina, ni cómputo pesado.** No está
  presupuestado. Donde haga falta una medida nueva, **diseña el experimento y
  presupuéstalo** (fases C y D lo piden explícitamente); no lo lances.
- descargas de pesos (ESMFold son 8,4 GB), Blender, ni nada de red más allá del
  `--fetch` del runtime.
- `tauri:build` (dieciséis puertas, horas de CPU).

Si una fase se bloquea sin cómputo, escríbelo en la puerta y para: el
propietario decide si abre presupuesto. **No lo abras tú.**

### 3.3 Dónde van los entregables

Fuera del árbol, en la convención de esta casa:

```
D:\moldesign-audits\AUDIT_ciencia_bef67706\
  ESTADO.md                  <- estado vivo para retomar (§7)
  bitacora.md                <- append-only, una entrada por sesión
  ledger.json                <- el ledger acumulado (§4)
  fase_a\prerregistro.md  informe_fase_a.md
  fase_b\prerregistro.md  informe_fase_b.md
  fase_c\prerregistro.md  informe_fase_c.md  taxonomia.md
  fase_d\prerregistro.md  informe_fase_d.md  protocolo_calibracion.md
  hallazgos_fuera_de_alcance.md
  lo_que_no_pude_medir.md    <- obligatorio (§4.3)
```

---

## 4. Entregables

### 4.1 El ledger (`ledger.json`)

Una fila por hallazgo, acumulativa entre fases. Es el entregable primario: el
propietario escribirá, a partir de él, pruebas que fallen mientras el hallazgo
siga abierto. Por eso tiene que ser legible por máquina y tiene que ser exacto.

```json
{
  "id": "SCI-A-001",
  "fase": "A",
  "titulo": "una línea, sin adjetivos",
  "objeto": "la afirmación literal auditada, citada tal cual, o el ID del sello",
  "superficie": "dónde la ve el usuario: interfaz | dossier | PDF | web | README | AGENTS.md | sólo interno",
  "evidencia": [
    {"ruta": "docs/papers/MF-33.md", "linea": 118, "sha256": null, "cita": "texto literal"}
  ],
  "comando_que_reproduce": "cd backend && ..\\python-embed\\python.exe -m pytest tests/test_x.py -k y",
  "medida_que_la_sostendria": "qué experimento la volvería SUSTENTADA",
  "veredicto": "SOBREAFIRMADA",
  "nivel_E_declarado": "E4",
  "nivel_E_sostenible": "E2",
  "severidad": "S2",
  "clase_de_coste": "C1",
  "arreglo_propuesto": "el cambio mínimo, no el ideal",
  "confianza": "ALTA",
  "citada_no_verificada": false
}
```

**Severidad** (la consecuencia, no el esfuerzo):

| | |
|---|---|
| **S1** | afirmación **falsa** que el usuario ve, o que viajaría a un cálculo externo |
| **S2** | afirmación sobreafirmada, o emitida sin la condición que la hace cierta |
| **S3** | sello cuyo nivel de madurez real no sostiene el uso que se le da |
| **S4** | hueco de cobertura con consecuencia demostrada en el cálculo posterior |
| **S5** | deuda ya declarada, sin consecuencia inmediata |

**Clase de coste** (escalera del propietario; sirve para ordenar el roadmap):

| | |
|---|---|
| **C0** | redactar, declarar o retirar una afirmación — horas |
| **C1** | código más su prueba, sin cómputo científico — 1 a 3 días |
| **C2** | experimento con cohorte y datos que ya existen — 1 a 2 semanas de CPU |
| **C3** | experimento con datos o cohorte nuevos — meses |
| **C4** | no factible hoy; dilo y di qué lo haría factible |

**Nivel E** es la escalera de madurez de
`docs/49_PROGRAMA_EXPERIMENTAL_CIENTIFICO.md` §3 (E0 hipótesis → E6 producción).
La regla de la casa: «un experimento que llega a E3 es prometedor, no
científicamente validado; los claims públicos requieren E4». Buena parte de la
auditoría es comparar el nivel que una afirmación **presume** con el nivel que su
evidencia **sostiene**.

### 4.2 El informe por bloque

Un `.md` por fase, en prosa, con una sección por hallazgo: qué se auditó, qué se
encontró, con qué evidencia, qué significa para el producto y qué cuesta
arreglarlo. El modelo de formato y de tono es
`docs/85_CORRECCIONES_AUDITORIA_SOL_20261001.md` (así se cerró tu auditoría
anterior: un ID por hallazgo, su diagnóstico, su decisión y su commit).

Cada informe abre con **tres párrafos** y ni uno más: lo que se auditó, el
hallazgo más grave, y lo que cambiarías del rumbo si sólo pudieras cambiar una
cosa.

### 4.3 `lo_que_no_pude_medir.md` (obligatorio)

Una lista de lo que quedó fuera de alcance de la medida y **por qué**: acceso,
presupuesto de cómputo, datos no redistribuibles, o límite del método. **Una
fase sin esta sección se rechaza**, aunque sus hallazgos sean buenos. Una
auditoría que no declara sus límites está afirmando que no tiene ninguno, y eso
siempre es falso.

---

## 5. Falsos positivos conocidos: esto NO es un hallazgo

Cada punto costó tiempo real a alguien. Si los presentas como hallazgos, el
informe pierde credibilidad y el propietario tiene que verificarte entero.

1. **`validar_sellos.py` reporta AUSENTES en un worktree.**
   `scripts/artifacts_science/*/_work/` está en `.gitignore`: un clon o worktree
   puede no traerlos. Un AUSENTE sólo es hallazgo si el fichero **está
   rastreado** (`git ls-files`) o si **no** está declarado en
   `scripts/sellos_no_distribuidos.json`. Si ves muchos, es **un** hallazgo meta
   («el sellado depende de ficheros que git no versiona»), no uno por fichero.
2. **Hashes que no cuadran por fin de línea.** CRLF contra `-text` en
   `.gitattributes` es un fallo conocido y declarado; en 2026-09-23 sólo
   validaban 12 de 167 sellos en un clon limpio por esa causa.
3. **Pruebas saltadas con python-embed.** Entre 22 y 63 según el árbol, la mayoría
   por `importorskip` de dependencias que no viajan en el bundle (`pypdf`, 18 de
   ellas). Está medido y declarado en `AGENTS.md`.
4. **El manifiesto de la instantánea del dossier con otro reportlab.** 4.2.0 en
   runtime y CI, 4.5.1 en desarrollo; la prueba salta el manifiesto a propósito.
5. **`report_test_counts.py --check` pasa aunque el conteo haya crecido.** Es la
   guardia contra un `importorskip` perdido, por diseño. No ejecutes `--write`:
   escribiría en el árbol.
6. **Los cinco motores que no aparecen en el menú** (QuickVina 2, DiffDock,
   ColabFold, ESMFold Pro, RFdiffusion). Decisión del propietario del
   2026-10-07, con tres guardianes (`ENG-001`, `ENG-003`, `ENG-004`).
7. **«Falta validación experimental»** como hallazgo genérico. Está declarado en
   cada informe del producto. Sólo es hallazgo con un caso concreto en el que el
   producto **no** lo declara donde debería.
8. **La sección «Verificados» del catálogo está vacía.** Es intencional y hay un
   guardián que falla si deja de estarlo sin un protocolo sellado detrás.

---

## 6. Las cuatro fases

Cada fase: prerregistro → trabajo → ledger → informe → **puerta**. No empieces
una fase sin que el propietario haya aceptado la anterior. Si te quedas sin
contexto a mitad de fase, `ESTADO.md` es lo que te permite retomar (§7).

---

### FASE A — Trazabilidad: afirmación → medida → condición

**Pregunta:** ¿Qué afirmación científica que MolDesign **emite** hoy no se
sostiene en una medida, con su condición?

**El eje que importa, y que nadie ha auditado todavía:**

> **declarado en `docs/` ≠ declarado al usuario.**

Toda la promesa del producto es que la incertidumbre **llega al investigador**.
Una condición que vive sólo en un paper de `docs/papers/` no acompaña al número
que sale en pantalla, en el dossier o en su PDF. Si el número viaja sin su
condición, la condición no existe para quien decide.

**Insumos, en este orden de prioridad:**

1. **Lo que el usuario ve:** cadenas de la interfaz (`frontend/` y sus catálogos
   de i18n, en **los dos idiomas** — una traducción puede perder la condición),
   el dossier y su PDF, Moldex, lotes, Molcy, la certificación.
2. **Lo que el producto promete fuera:** `README.md`, la web pública, el deck y
   la documentación científica de `docs/`.
3. **`AGENTS.md`** entero, afirmación por afirmación. Es el inventario de lo que
   el propietario cree verdadero; audítalo como tal.
4. `docs/papers/` (80 papers) y `docs/19_LIMITATIONS.md`.

**Método:** inventario de afirmaciones → para cada una, la medida que la
sostendría → ¿existe? → ¿con qué condición? → ¿viaja la condición con el número
hasta la superficie donde el usuario lo ve? → veredicto.

**Prioriza** las afirmaciones que: (a) el usuario ve, (b) viajarían a un cálculo
externo dentro del paquete transferible, (c) sostienen una decisión de producto
ya tomada. Las puramente internas van al final.

**Puerta A:** el propietario acepta la fase cuando cada afirmación del inventario
tiene veredicto y evidencia, y las `FALSA` y `SOBREAFIRMADA` traen su ruta y su
arreglo mínimo. Si no encuentras ninguna, la puerta se cruza igual **siempre que
el método sea auditable y lo diga el informe** — pero mira la sección 5 antes de
concluirlo, porque el propietario ya tiene una lista sellada de defectos
conocidos y va a comparar.

---

### FASE B — Validez interna de los experimentos sellados

**Pregunta:** ¿Cuál de los 187 experimentos sellados tiene un defecto de diseño
que invalida o debilita su conclusión?

**Muestreo (no exhaustivo, y declarado en el prerregistro):** audita, en este
orden, (1) los sellos que sostienen una afirmación marcada en la Fase A, (2)
todos los que cerraron en **GO**, (3) los que decidieron algo de producción
(E5/E6), (4) los que el propietario cita en `AGENTS.md`.

**Qué buscar en cada uno:**

- **Prerregistro contra lectura:** ¿el gate estaba escrito antes? ¿se leyó `val`
  una sola vez? ¿se movió el criterio después de ver el resultado?
- **Leakage:** ¿poses del mismo complejo cruzando train/eval? ¿identidad de
  receptor? ¿scaffold? ¿series de ligandos relacionados? La regla del laboratorio
  dice que los complejos se agrupan; verifica que se cumplió.
- **Potencia:** n, intervalo de confianza, prueba pareada, comparaciones
  múltiples sin corregir, y si el IC permite la conclusión que se saca.
- **Control negativo:** ¿existe? Un experimento sin control negativo rara vez
  distingue su efecto del artefacto de su tubería.
- **Reuso del test histórico:** el test de 47 complejos «ya influyó en múltiples
  decisiones» (`docs/49`, §4) y sólo sirve como benchmark histórico. Busca
  cualquier conclusión viva que todavía dependa de él.
- **El código productor:** ¿el sello acredita el código que produjo el número, o
  sólo que los bytes no cambiaron? `validar_sellos.py` distingue `VERIFICADO` de
  `MANTENIDO`; un `MANTENIDO` **no acredita el productor**. ¿Alguna afirmación
  viva descansa en un `MANTENIDO`?
- **Nivel E:** declara el nivel que sostiene y compáralo con el uso real.

**Puerta B:** todo sello que sostiene una afirmación de producto tiene veredicto,
y cada defecto de diseño trae dicho explícitamente **qué conclusión deja de
valer** y qué la recuperaría.

---

### FASE C — Cobertura de readiness estructural

**Pregunta:** ¿Qué modos de fallo estructural que FEP, MD o ABFE dan por hechos
**no detecta** hoy el producto, y cuáles de ésos importan de verdad?

Ésta es la fase que más rige el rumbo, porque la identidad declarada del producto
es ser el auditor de readiness anterior al cálculo caro.

**Orden obligatorio, y es el punto crítico del método:**

1. **Primero construye la taxonomía, sin mirar el producto.** Desde la
   literatura y la práctica de preparación para energía libre: unidad biológica y
   cadenas, huecos del esqueleto, extremos y cierres, estados de protonación
   (receptor y ligando), tautomería, estereoquímica, altlocs, puentes disulfuro,
   metales y su coordinación, cofactores, aguas estructurales contra
   desplazables, iones de la red cristalográfica, especies químicas del ligando,
   pose inicial, correspondencia atómica entre análogos, covalentes, membrana,
   campo de fuerzas y sus huecos de parametrización (halógenos, azufre,
   macrociclos). Escribe **la consecuencia de cada modo de fallo en el cálculo
   posterior**: ΔΔG sesgado, corrida que no arranca, o —el peor— resultado que
   parece bueno y no lo es.
2. **Séllala** (`fase_c/taxonomia.md`, con fecha, antes de seguir).
3. **Sólo entonces** mapea la cobertura del producto contra ella, en cuatro
   estados: **detecta y bloquea** / **detecta y avisa** / **declara como
   incertidumbre sin detectar** / **silencio**. El silencio es el hallazgo: un
   defecto que ni se detecta ni se declara viaja al cálculo externo como si no
   existiera.

**Evidencia que ya existe y hay que usar, no repetir:** `FEP-09` y `FEP-09-R1`
(sensibilidad con defectos plantados: huecos del sitio 15/15, estereoquímica
21/21, falsa alarma 0/585; agua puente 0/9 y protonación del sitio 0/5;
decisión global INCONCLUSIVE por falta de casos), `MET-01` (INCONCLUSIVE, y lo
que destapó), `FEP-01`/`FEP-02`/`FEP-03`, la curación de receptores del
2026-10-11 y `docs/auditorias/metales_junto_al_sitio_2026-10-11.json`.

**Cuidado con una trampa de interpretación:** en este producto, «comprobación
previa» (`check_preparation`) y la **pestaña Preparación** son cosas distintas.
No atribuyas a una lo que mide la otra.

**Entregable extra:** los diez huecos ordenados por **daño × probabilidad ÷
coste**, cada uno con su clase C0–C4 y el experimento mínimo que lo cerraría.

**Puerta C:** la taxonomía está sellada **antes** del mapeo (se verifica por
fecha), la matriz de cobertura está completa, y los diez huecos están ordenados
con su coste. Un orden sin coste no sirve para decidir.

---

### FASE D — Calibración, abstención e incertidumbre

**Pregunta:** ¿La señal de confianza que MolDesign emite es honesta, y qué
protocolo mínimo sostendría la sección «Verificados»?

**El hecho que la motiva:** ninguno de los 381 receptores del catálogo está
calibrado. El único intento publicado, `CAL-8HFI-01`, salió **NO_GO**: ρ = 0,13,
IC 95 % [−0,16; 0,41], n = 57. Vina no ordenó esa serie de análogos mejor que el
azar. Y el producto promete saber cuándo no confiar.

**Qué se te pide:**

1. **Potencia y factibilidad.** Para el gate vigente (límite inferior del IC
   95 % de ρ > 0, más 3 de 5 semillas a RMSD ≤ 2 Å y pose válida en
   PoseBusters): ¿qué n hace falte a valores plausibles de ρ? Con los paneles de
   datos que realmente existen, ¿cuántos receptores del catálogo son candidatos
   siquiera? **¿Es el gate alcanzable, o está diseñado para no cruzarse nunca?**
   Ésa es una pregunta legítima y el propietario quiere la respuesta aunque sea
   incómoda.
2. **El umbral de pose.** ¿3 de 5 semillas a 2 Å es defendible, o es un número
   heredado? Qué dice la evidencia del propio repositorio.
3. **La señal que se muestra.** Audita qué incertidumbre ve el usuario hoy por
   corrida, y si es calibrada, ordinal o decorativa. Incluye los tiers S/A/B/C/D
   de Moldex, el proxy de validez física (y su **falso rechazo del 14,2 %**,
   `docs/50_ROADMAP.md:604`), el rescoring y el stacking. Un indicador de
   confianza no calibrado es peor que ninguno: el caso DiffDock de este mismo
   repositorio —`position_confidence` **anticorrelacionado** con la validez
   física— es el ejemplo de por qué.
4. **El protocolo mínimo**, ejecutable, con presupuesto en CPU-horas, para
   promover **un** receptor a «Verificados» con honestidad. Y el veredicto: ¿es
   alcanzable en 1.0.3?
5. **La abstención.** ¿`BLOCKED`/`REVIEW`/`READY` se emiten por una regla
   medida, o por heurística? ¿Qué pasaría si se midiera su tasa de falso
   bloqueo, como se midió el 14,2 % del proxy?

**Puerta D:** hay un protocolo con presupuesto, un veredicto de factibilidad, y
un dictamen explícito sobre si la señal de confianza actual es honesta. Diseñas
los experimentos; **no los ejecutas**.

---

## 7. Cómo sobrevive una tarea larga

Esto no es burocracia: es lo que hace que la fase 4 valga tanto como la 1.

- **`ESTADO.md` se actualiza al final de cada sesión** y contiene, sin prosa:
  fase actual, qué quedó cerrado, qué está a medias y **con qué fichero
  abierto**, siguiente acción concreta, y las decisiones ya tomadas que no se
  reabren. Escríbelo para alguien que no estuvo: en la práctica, ése serás tú.
- **`bitacora.md` es append-only.** Una entrada por sesión: fecha, qué miraste,
  qué midiste, qué comandos, qué concluiste. No la reescribas; si te
  equivocaste, añade una corrección fechada. Los negativos se preservan.
- **El ledger es acumulativo.** No se renumera, no se borran filas. Un hallazgo
  retirado pasa a `veredicto: SUSTENTADA` con una nota de por qué cambió.
- **Una fase, un paquete.** No mezcles fases en un informe.
- **Si el contexto se va a agotar a mitad de un análisis, para y escribe el
  estado.** Un análisis a medias bien documentado vale más que una conclusión
  apresurada.

---

## 8. Lo que el propietario va a hacer con esto

Para que calibres el nivel de detalle: el ledger se convierte en roadmap. Los
hallazgos S1 y S2 se arreglan antes de buscar usuarios; los C0 (redactar o
retirar una afirmación) se aplican casi de inmediato; los C2 y C3 compiten por
el presupuesto de cómputo de los próximos meses. Las fases C y D deciden **hacia
dónde va el producto**.

Por eso el arreglo propuesto importa tanto como el hallazgo, y por eso se pide
el **mínimo** y no el ideal: un arreglo de tres días que cierra el 80 % del daño
se aplica; uno de tres meses se discute.

**Y por eso un hallazgo inventado es más caro que un hallazgo omitido:** cada
uno obliga a una verificación completa y erosiona la confianza en el resto del
informe. Si dudas, márcalo `confianza: BAJA` y dilo. Eso es aceptable y útil.
Afirmar con seguridad lo que no mediste, no.

---

## 9. Las cinco preguntas de cierre

Al final de la Fase D, además de los informes, contesta estas cinco en dos
páginas, con las cifras que las sostengan:

1. **¿Cuál es la afirmación científica más fuerte que MolDesign puede hacer hoy
   con honestidad**, y en qué se diferencia de la que hace?
2. **¿Cuál es el hallazgo que más daño haría si un primer usuario externo lo
   encontrara antes que nosotros?**
3. **Si sólo se pudiera ejecutar un experimento en los próximos tres meses**,
   ¿cuál compra más honestidad por CPU-hora, y por qué ése?
4. **¿Es «auditor de readiness para FEP» el hueco correcto** dada la cobertura
   que midió la Fase C, o la evidencia apunta a otro hueco adyacente?
5. **¿Qué debería MolDesign dejar de ofrecer** porque no puede sostenerlo con
   medida?

---

## 10. Confirmación antes de empezar

Responde, antes de tocar el repositorio, con: el prerregistro de la Fase A, la
confirmación de que el worktree está creado y aprovisionado, y **una lista de las
afirmaciones de este encargo que te parezcan dudosas**. Este encargo también
puede estar mal: si una de sus premisas no se sostiene, dilo en la primera
sesión y no en la última.
