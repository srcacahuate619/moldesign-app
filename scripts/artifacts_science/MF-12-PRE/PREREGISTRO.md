# MF-12-PRE — Prerregistro: ¿se puede predecir el fallo de colocación antes de dockear?

**Fecha:** 2026-08-18
**Estado:** PREREGISTRO escrito antes de ejecutar (doc. 49 §2).
**Cartera C, ID MF-12** — declarado desde el inicio del programa, nunca ejecutado por
falta de predictores medidos.
**Entradas:** `MF-24` (predictores sobre 203 complejos), `MF-26`, `MF-27`, `FND-04`.

---

## 1. La pregunta

MF-12 se enunció como «la política debe activar MolFlex sólo donde ayuda». La versión
contrastable es:

> **¿Se puede predecir, sin dockear, que el docking va a fallar?**

No promete arreglar el docking. Promete saber cuándo no va a funcionar, que es más
modesto y mucho más verificable. Si la respuesta es sí, es una capacidad operativa
—enrutar los casos duros y no gastar CPU—; si es no, cierra MF-12 con evidencia en vez
de dejarlo abierto.

## 2. El problema de fuga, y cómo se trata

`MF-24` midió seis predictores, pero **tres usan el ligando cristalográfico** (radio de
giro, ocupación de caja y enterramiento se calculan sobre la pose real). En producción
esa pose no existe: usarlos sería fuga. Peor: en este conjunto **la caja misma** es
`center_from_crystal_ligand`.

Se declaran por tanto **dos niveles de disponibilidad** y se evalúan por separado:

**Nivel L (sólo ligando)** — disponible siempre, sin conocer el sitio:

| Predictor | Fuente |
|---|---|
| `n_torsiones` | PDBQT flexible del confórmero |
| `n_pesados` | ligando |
| `n_conformeros` | tamaño del ensemble ETKDG |
| `rg_conformero` | radio de giro del **confórmero 0**, no del cristal |
| `ocupacion_conformero` | extensión del confórmero 0 sobre el volumen de caja |

**Nivel L+S (ligando + sitio)** — añade descriptores del bolsillo, disponibles en cuanto
hay una caja, que es condición previa de cualquier docking:

| Predictor | Fuente |
|---|---|
| `prot_5A_centro`, `prot_8A_centro` | átomos pesados de proteína cerca del **centro de caja** |

**Limitación declarada y no negociable:** el centro de caja de este conjunto viene del
ligando cristalográfico, así que los predictores de sitio operan bajo el supuesto
favorable de **caja perfectamente centrada**. En producción con MolPocket el centro está
a ~8 Å de mediana (`REC-03`), lo que los degradaría. El nivel L+S mide un **techo**, no
un rendimiento de producción, y así debe leerse.

**Prohibido** usar `rmsd_conf`, `enterramiento` u `ocupacion_caja` de `MF-24`: los tres
requieren la pose cristalográfica.

## 3. Diseño

- **Entrenamiento**: los **116 de train**, exclusivamente.
- **Evaluación**: los **87 de val+test**, una sola vez, sin reentrenar ni ajustar nada
  después de mirarlos.
- **Modelo**: regresión logística sobre los predictores estandarizados. Deliberadamente
  simple: con n=116 y el efecto mínimo detectable de §4, un modelo con capacidad haría
  overfitting sin poder demostrarlo.
- **Desenlace**: `convierte` = existe pose ≤2.0 Å (`rmsd_pose_pocket`) entre las poses
  que el confórmero produjo. Tasa base: 0.431 en train, 0.586 en val+test.
- **Métrica**: **precisión balanceada** (media de sensibilidad y especificidad), porque
  las clases están desbalanceadas de forma distinta en cada split.

**Baseline obligatorio**: la regla trivial de predecir siempre la clase mayoritaria del
train. Un clasificador que no la supere no vale nada aunque su exactitud parezca alta.

## 4. Potencia, declarada antes de ejecutar

Aplicando `FND-04`: con **n=203** y discordancia esperada ~0.5, el **efecto mínimo
detectable al 80% es 0.136**. Este diseño resuelve diferencias de ~14 puntos y **no
menos**. Cualquier mejora observada por debajo de eso se reportará como no concluyente,
no como éxito.

Es la primera vez que un gate del programa declara esto antes de correr, según la regla
que la §20.9 propuso a partir del fallo de `RS-14`.

## 5. Gates

| ID | Gate | Criterio |
|---|---|---|
| G1 | **Validez** | los 203 complejos tienen los predictores del nivel L sin nulos |
| G2 | **Superioridad** (primario) | precisión balanceada en val+test > baseline mayoritario, con CI95 bootstrap que excluya el cero |
| G3 | **Honestidad del nivel** | se reportan L y L+S por separado; el claim se hace sobre **L**, que es el único sin supuesto de caja perfecta |

**GO** = G1 y G2 sobre el nivel L. **NO_GO** = G2 falla en L.

Un GO sobre L+S pero no sobre L **no es GO**: sería decir «puedo predecir el fallo si ya
sé dónde une el ligando», que en producción no sirve.

## 6. Predicción declarada

1. **El enterramiento del sitio cargará el peso.** Es el único predictor que ha
   sobrevivido a todo: a la estratificación por torsiones en train (3 de 4 bandas) y en
   val+test (**4 de 4**), y al cambio de split.
2. **Las torsiones aportarán poco una vez controlado el resto**, porque `MF-27` mostró
   que dentro del grupo flexible dejan de discriminar (cociente 0.97).
3. **El nivel L rendirá claramente peor que L+S**, y es posible que L no supere al
   baseline. Se predice precisión balanceada de **0.60–0.70 en L+S** y **0.55–0.65 en L**.

Se predice **GO marginal o NO_GO**, no un clasificador útil. Preregistrar una predicción
tibia es incómodo y por eso se escribe.

## 7. Prohibiciones

- Prohibido reentrenar, ajustar umbral o cambiar features después de mirar val+test.
- Prohibido presentar validación cruzada interna como generalización: es el error que
  `MF-26` cometió hoy al declarar un acantilado de torsiones que no sobrevivió al split
  externo.
- Prohibido leer un GO como política de producción sin medir antes el coste: enrutar mal
  un complejo que sí habría convertido tiene un coste que este experimento no mide.
- Prohibido usar los predictores derivados del cristal (§2).
