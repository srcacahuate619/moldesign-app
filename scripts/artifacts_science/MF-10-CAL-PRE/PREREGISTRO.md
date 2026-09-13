# MF-10-CAL — Prerregistro: control positivo y convergencia de MF-10

**Fecha:** 2026-08-18
**Estado:** PRERREGISTRO escrito antes de ejecutar (regla del laboratorio, doc. 49 §2).
**Refina:** `MF-10`, cuyos artefactos están ejecutados pero **sin sellar**.
**Entradas:** el mismo `mf10_poses.json` (878 poses, 48 complejos) y la misma caché de
receptores preparados (`_mf10/`, 96 ficheros) que usó `MF-10`.
**Entorno:** contenedor `moldesign-lab` (Python 3.11.15, OpenMM 8.5.2, OpenFF 0.18.0,
RDKit 2026.03.1, openmmforcefields 0.15.1, PDBFixer). Plataforma CPU, 4 núcleos.

---

## 1. Por qué existe este experimento

La auditoría de `MF-10` del 2026-08-18 limpió seis riesgos metodológicos y encontró
dos **controles ausentes**. Ninguno invalida el NO_GO, pero ambos limitan lo que ese
NO_GO puede afirmar. Este experimento los añade **antes** de sellar `MF-10`, en vez de
sellar una conclusión que no está del todo ganada.

**Hueco 1 — no hay control positivo.** `MF-10` midió cuánto acerca el campo de fuerza
una pose dockeada al cristal, pero nunca midió **dónde pone el campo de fuerza al
propio cristal**. La minimización es en vacío y con la proteína restringida: el
mínimo del FF no tiene por qué coincidir con la conformación cristalográfica. Sin ese
número no se distingue «el FF no ayuda» de «el mínimo del FF está a *X* Å del cristal,
y *X* es el suelo del instrumento».

**Hueco 2 — no se registró la convergencia.** `minimizeEnergy(maxIterations=500)` no
deja constancia de si paró por tolerancia o por presupuesto. PDBFixer añade **todos**
los hidrógenos de la proteína en posiciones idealizadas y esos hidrógenos quedan
**libres** (el restraint de k=100 kcal/mol/Å² es sólo sobre pesados). El minimizador
tiene por delante miles de grados de libertad con gradiente grande que no son el
ligando. El dato que lo sugiere: la correlación entre caída de energía y movimiento
del ligando en `MF-10` fue **0.134** — las caídas medianas de 1,422 kcal/mol no se
gastaron en mover el ligando.

## 2. Diseño

Se reutiliza **exactamente** el mismo constructor de sistema de `MF-10`
(`construir_sistema`, importado, no copiado), para que cualquier diferencia medida
provenga del protocolo de minimización y no de la preparación.

### Brazo A — control positivo (48 complejos, 1 minimización cada uno)

Minimizar la **pose cristalográfica** con el protocolo idéntico de `MF-10` y medir el
RMSD del ligando respecto del cristal después de minimizar (`rmsd_pose_pocket`, sin
alinear, mismos átomos pesados). Ese número es el **suelo del instrumento**.

### Brazo B — convergencia (24 poses)

Para cada pose de la submuestra, minimizar con `maxIterations` ∈ **{500, 2000,
10000}** y registrar, además del RMSD, la **fuerza RMS residual sobre los átomos
pesados del ligando**. Esa fuerza es el diagnóstico directo: si ya es pequeña a 500
iteraciones, el ligando estaba en un mínimo local y el hueco 2 queda refutado,
independientemente de cuántas iteraciones se gastaran en la proteína.

**Submuestra declarada aquí y no redefinible:** las **24 poses de mejor score** (más
negativo) entre todas las que caen en la banda 2.0–3.0 Å, que es la única donde una
minimización local podría convertir. Se eligen **por score, nunca por RMSD**, igual
que en `MF-10`.

## 3. Predicción declarada

La deriva del cristal minimizado será **mayor que cero y menor que 1.0 Å**. El
movimiento máximo observado en las 714 poses de `MF-10` fue 0.73 Å, y no hay razón
para que el cristal se mueva más que una pose dockeada bajo el mismo restraint.

Si la deriva mediana resultara **≥ 1.0 Å**, la lectura cambia por completo: el
instrumento no podría detectar una conversión ni aunque existiera, y `MF-10` habría
medido principalmente el desplazamiento del mínimo del campo de fuerza en vacío.

## 4. Gates

| ID | Gate | Criterio |
|---|---|---|
| C1 | **Suelo** | se reporta la deriva mediana del cristal minimizado (medición, sin umbral) |
| C2 | **Suelo informativo** | la deriva mediana es < 1.0 Å, el orden que `MF-10` habría necesitado convertir |
| C3 | **Convergencia** | el Δ mediano **no** mejora más de 0.1 Å al pasar de 500 a 10000 iteraciones |

**Lectura preregistrada de C3**, declarada antes de ver el resultado:

- **C3 PASS** → `MF-10` midió con el minimizador convergido para el ligando, y su
  NO_GO es una medición legítima del campo de fuerza.
- **C3 FAIL** → `MF-10` midió con el presupuesto agotado antes de llegar al ligando, y
  su **G3 debe releerse como inconcluso**, no como negativo.

## 5. Presupuesto

~3.5 h de reloj en el contenedor (4 núcleos, un proceso). Brazo A ~16 min reutilizando
la caché de receptores; brazo B domina por las corridas de 10000 iteraciones.

## 6. Prohibiciones

- Prohibido redefinir la submuestra del brazo B después de ver resultados.
- Prohibido elegir poses por RMSD: se eligen por score.
- Prohibido sellar `MF-10` antes de leer este resultado — es su razón de existir.
- No se toca val, test ni `D-RC-CONFIRM`: la cohorte es de train.
- Un `C3 FAIL` **no** convierte a `MF-10` en GO: lo convierte en inconcluso sobre G3,
  y G2 seguiría fallando por su propia causa (fallo de parametrización en 9 complejos).
