# Auditoría metodológica de MF-10, antes de sellar

**Fecha:** 2026-08-18
**Alcance:** preparación de muestras, correspondencia de átomos, calibración de la
métrica, convergencia del minimizador y sesgos de cohorte.
**Motivo:** verificación explícita pedida antes de cerrar el registro. `MF-10` corrió
7 h 14 min en el contenedor `moldesign-lab` y devolvió **NO_GO**; esta auditoría
decide si ese NO_GO es una medición válida o un artefacto.

**Veredicto: el NO_GO se sostiene.** Se limpian seis riesgos, se encuentran dos
defectos reales —uno acotado y menor, otro con alcance de programa— y se identifican
**dos controles ausentes** que el prerregistro debió incluir y que no invalidan la
decisión pero sí limitan lo que puede afirmarse a partir de ella.

---

## 1. Lo que se verificó y está limpio

### 1.1. La métrica antes/después es la misma función — el error de `MF-02B-R1` no se repitió

Es el riesgo mayor de este diseño: `rmsd_antes` viene precomputado en el fichero de
poses de entrada, y `rmsd_despues` lo calcula el runner. Si fueran métricas
distintas, `delta` mezclaría dos definiciones y G3/G4 medirían un cambio de
convención en vez de un cambio físico. Es exactamente lo que pasó en `MF-02B`, con un
sesgo mediano de 1.00 Å.

Se recomputaron las **878** poses de entrada con la misma función que usa el runner
para la salida (`rmsd_pocket`, sin alinear, sobre los mismos índices de átomo pesado)
y se compararon contra el valor almacenado:

| | Valor |
|---|---:|
| Poses comparadas | 878 / 878 |
| Discrepancia máxima | **0.0005 Å** |
| Discrepancia media | 0.00025 Å |

La discrepancia es exactamente el redondeo a tres decimales del fichero. **`delta` es
internamente consistente.**

### 1.2. La correspondencia de átomos no se rompe

El RMSD compara átomo *i* del cristal contra átomo *i* de la pose minimizada. Entre
uno y otro la molécula pasa por RDKit → `AddHs` → OpenFF → topología OpenMM →
`Modeller`, y cualquier reordenamiento en esa cadena produciría un RMSD sin sentido.

- El fichero de poses mapea coordenadas **por índice de átomo del cristal**
  (`coords["42"]`), no por posición en una lista: la correspondencia es explícita y no
  depende del orden de iteración.
- Se verificó en los 48 complejos que `AddHs` **nunca** altera el orden de los átomos
  pesados: los añade al final. El filtro de pesados sobre `off.atoms` devuelve por
  tanto la misma secuencia que `pesados` en el cristal.
- 0 complejos con mapeo incompleto (`MAPEO_INCOMPLETO` no se disparó ni una vez).

### 1.3. Las poses se eligieron por score, nunca por RMSD

La prohibición central del prerregistro. Verificado sobre el fichero de entrada: las
listas de cada complejo están **ordenadas por score ascendente** y se toman
`min(20, n_total)`. 0 complejos con selección inconsistente. Total 878, con 8
complejos que aportan menos de 20 porque no tenían más poses.

### 1.4. La predicción declarada cuadra exactamente

El prerregistro declaró **67 poses en la banda 2–3 Å**. La aritmética cierra sin
residuo:

```
67 declaradas  −  3 perdidas por fallo de parametrización  =  64 medidas
```

No es «cerca»: es exacto. La banda no se redefinió y la merma está explicada.

### 1.5. La merma de cohorte NO sesga hacia el NO_GO

9 complejos perdieron sus 20 poses (§2.1). Si los perdidos hubieran sido los más
cercanos a convertir, el NO_GO sería un artefacto de la merma. Es al revés:

| Grupo (estrato COLOCACION) | n | Mejor RMSD (mediana) | Poses en banda 2–3 Å |
|---|---:|---:|---:|
| Perdidos | 8 | **4.450 Å** | 2 |
| Retenidos | 25 | 4.024 Å | 9 |

Los perdidos estaban **más lejos** de convertir. Excluirlos favorece ligeramente al
`GO`, y aun así el gate falla. **La decisión es conservadora, no un artefacto.**

### 1.6. La minimización hizo trabajo real

| | Valor |
|---|---:|
| Caída de energía (mediana) | **1,422 kcal/mol** |
| Caída p95 | 1.13 × 10⁴ kcal/mol |
| Poses con energía final positiva | **0 de 714** |
| Poses con energía inicial > 10⁴ (choques) | 36, todas resueltas |

No hay poses que quedaran en un estado inválido ni energías infinitas.

---

## 2. Defectos encontrados

### 2.1. Fallo de parametrización concentrado en 9 complejos — es preparación, no ruido

Los 164 errores no están repartidos: son **9 complejos que fallaron 20/20 poses** con
el mismo error de plantilla de OpenMM (`residue match NVAL, but the set of externally
bonded atoms has 1 N atom too many`).

`1b38`, `1c4u`, `1d3p`, `1d9i`, `1dgm`, `1mu8`, `1nm6`, `1nw5` (COLOCACION) y `1flr`
(CONTROL).

**Causa:** el protocolo vacía `missingResidues` a propósito para no reconstruir loops
ausentes. Los cortes de cadena resultantes quedan como **términos**, y amber14 no
reconoce el patrón de enlace externo de un residuo terminal así generado.

**Efecto:** G2 falla (81.3% frente al 95% exigido) y la cohorte efectiva del estrato
objetivo baja de **33 a 25**. Es un fallo de **preparación de muestra**, no del campo
de fuerza: no informa sobre la hipótesis.

**Es reparable** —fijar los términos de los cortes de cadena en PDBFixer— pero
recuperar 8 complejos no cambiaría la decisión: el Δ mediano es +0.007 Å y el
movimiento máximo observado en 714 poses es 0.73 Å (§2.3).

### 2.2. Hidrógenos retenidos en 7 complejos — defecto latente, impacto acotado

`Chem.MolFromMolFile` con `removeHs=True` **no** elimina todos los hidrógenos: en
`1c4u`, `1eb2`, `1ezq`, `1f0t`, `1f0u`, `1bju` y `1g3d` sobrevive uno. El runner mueve
los átomos **pesados** a las coordenadas de la pose y deja ese hidrógeno en su
coordenada **del cristal**, de modo que el enlace queda estirado por la distancia
entre pose y cristal.

Cuantificado, el impacto es menor: los 6 complejos afectados que llegaron a correr
tienen energías iniciales medianas (−1,740 a −3,058 kcal/mol) y deltas en el mismo
rango que el resto (mediana −2,625 kcal/mol), y sólo 9 de las 36 poses de energía
inicial alta caen en ellos.

**Se declara como defecto latente**: en una cohorte con más hidrógenos retenidos, o
con poses más alejadas del cristal, produciría geometrías iniciales inválidas de forma
sistemática. La corrección es de una línea —fijar también los hidrógenos explícitos, o
leer con `removeHs=True` y `sanitize=True` verificando el conteo.

### 2.3. La métrica del programa no corrige simetría — alcance más allá de MF-10

`rmsd_pose_pocket` compara átomo *i* contra átomo *i* por índice de fichero. La
auditoría del 2026-08-14 hizo bien en rechazar `GetBestRMS` porque **alinea**, pero
`GetBestRMS` hacía **dos** cosas —corregir simetría y alinear— y se descartaron ambas.

Medido sobre las 878 poses, comparando contra el mínimo sobre automorfismos
**igualmente sin alinear**:

| | Valor |
|---|---:|
| Ligandos con automorfismos | **37 de 48** |
| Sesgo mediano | 0.004 Å |
| Poses con sesgo > 0.5 Å / > 1.0 Å | 18 / 10 |
| Sesgo máximo | **3.04 Å** |
| Poses que cruzan 2.0 Å sólo por corregir | **13** (92 → 105) |
| Complejos que ganan cobertura | **1** (`1l83`, COLOCACION) |

`1l83` mide **2.106 Å** con la métrica ingenua y **0.498 Å** corrigiendo simetría: una
pose prácticamente perfecta contabilizada como fallo de cobertura.

**No altera la decisión de MF-10**: `delta` es una diferencia de dos RMSD medidos
igual, y con un movimiento máximo de 0.73 Å la permutación óptima no cambia entre
antes y después. **Sí afecta a las cifras absolutas de cobertura de todo el
programa**, siempre en la misma dirección: corregir sólo puede bajar el RMSD, así que
toda cobertura publicada es una **cota inferior**. Documentado en la §5.1 del doc. 49.

---

## 3. Controles ausentes — lo que el prerregistro debió incluir

Estos dos no son errores de ejecución: son huecos de diseño que limitan la
**interpretación** del NO_GO, no su validez.

### 3.1. No hay control positivo: nunca se minimizó la pose cristalográfica

El experimento mide cuánto acerca el campo de fuerza una pose dockeada al cristal,
pero **nunca midió dónde pone el campo de fuerza al propio cristal**. Sin ese número
no se puede distinguir:

- **(A)** «el FF no ayuda porque la pose ya está en un mínimo local del que no sale», de
- **(B)** «el FF tiene su mínimo a *X* Å del cristal, y por tanto *X* es el suelo de
  este instrumento: ninguna pose puede acercarse más que eso».

Si el cristal minimizado se aleja 0.3 Å, entonces un Δ de −0.069 Å en la banda es
indistinguible del ruido alrededor de un mínimo que **no está en el cristal**. El
sondeo de capacidad sobre `10gs` usó la pose cristalográfica pero sólo calculó
energía; nunca minimizó.

Agravante: la minimización es **en vacío**, sin solvente. En vacío los grupos polares
colapsan unos sobre otros y el mínimo del campo de fuerza se desplaza
sistemáticamente respecto del cristal. La magnitud de ese desplazamiento es
justamente lo que el control mediría.

### 3.2. No se registró la convergencia del minimizador

`minimizeEnergy(maxIterations=500)` no deja constancia de si terminó por
**tolerancia** o por **agotar el presupuesto**. Y hay una razón concreta para
sospechar lo segundo: PDBFixer acaba de añadir **todos** los hidrógenos de la proteína
en posiciones idealizadas, y esos hidrógenos están libres (el restraint de
k = 100 kcal/mol/Å² se aplica sólo a **pesados** de proteína). El minimizador tiene
por delante miles de grados de libertad con gradiente grande que no son el ligando.

El dato que lo sugiere:

> **Correlación entre caída de energía y movimiento del ligando: 0.134.**

Es decir: las caídas de 1,400 kcal/mol **no** se están gastando en mover el ligando.
Compatible con «el ligando ya está en un mínimo», pero igualmente compatible con «el
presupuesto se fue en relajar hidrógenos de proteína antes de llegar al ligando».

Mientras no se separen, la afirmación «un FF bien parametrizado no acerca la pose» no
está del todo ganada: podría ser «nuestra minimización no llegó a probarlo».

---

## 4. Efecto sobre la decisión

| Gate | Resultado | ¿Lo toca la auditoría? |
|---|---|---|
| G1 capacidad | PASS | No |
| G2 validez | FAIL (81.3%) | **Sí** — el fallo es de preparación (§2.1), no del FF. Sigue siendo FAIL |
| G3 mejora | FAIL (+0.007 Å) | Parcialmente — §3.2 deja abierto si está bien medido |
| G4 conversión | PASS (9 de 64) | No, pero ver abajo |

**El NO_GO se mantiene.** G2 falla por una causa identificada y G3 falla con un Δ
mediano indistinguible de cero. Y por debajo de los gates hay un número que ninguna de
las objeciones anteriores toca:

> **0 complejos convertidos.** Las 9 poses que cruzan 2.0 Å pertenecen a 7 complejos
> que **ya tenían** una pose por debajo del umbral antes de relajar, y 8 de las 9 son
> del estrato CONTROL. Ningún complejo que fallaba pasó a acertar.

G4 pasó tal como se preregistró —cuenta poses— y así debe registrarse, sin
redefinirlo. Pero la lectura honesta es que la conversión a nivel de **pose** no se
tradujo en una sola conversión a nivel de **complejo**, que es la unidad que decide en
toda la línea `MF-08`/`MF-02F`/`MF-09`.

---

## 5. Recomendación

1. **Sellar `MF-10` como NO_GO**, incorporando esta auditoría al registro y declarando
   §2.1, §2.2, §3.1 y §3.2 como limitaciones del experimento.
2. **No re-correr la cohorte completa** para reparar §2.1: 7 h de cómputo para 8
   complejos cuyo Δ esperado es ~0.1 Å.
3. **Sí correr `MF-10-CAL`** antes o junto con el sello: control positivo (§3.1) y
   prueba de convergencia (§3.2). Es barato —48 minimizaciones del cristal más un
   barrido de `maxIterations` sobre una submuestra— y es lo que separa «el FF no
   ayuda» de «no lo medimos bien». Con su resultado, la lectura de `MF-10` queda
   cerrada en un sentido u otro.
