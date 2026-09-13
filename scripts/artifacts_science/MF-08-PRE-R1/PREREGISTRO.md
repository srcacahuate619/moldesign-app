# MF-08-PRE-R1 — Sub-prerregistro: la caja adaptativa entra como brazo principal

**Fecha:** 2026-08-17
**Estado:** PREREGISTRO (nada ejecutado bajo este registro ni bajo el anterior)
**Sustituye a:** `MF-08-PRE` (sellado, **sin ejecutar**). Lo demás de aquel registro —hipótesis, cohorte, métrica, prohibiciones, advertencia de transferencia a producción— se mantiene **sin cambios**.

---

## 1. Qué cambia y de dónde sale

Revisando la biblioteca del proyecto original (`D:\moldesign-app\docs`) apareció **`propuestas_de_mejora.md` §3, «Caja de Docking Adaptativa»**, escrito en julio de 2026 — **muy anterior a estos resultados**:

> «Si el tamaño real de la conformación 3D del ligando supera las dimensiones de la caja, AutoDock Vina recortará la estructura […] Calcular las dimensiones máximas del conformero en Å […] Si cualquiera de las dimensiones del ligando más un **margen de solvatación de 4.0 Å** supera la dimensión de la caja, redimensionar dinámicamente el Grid Box.»

Es **el mismo criterio físico** que MF-08-PRE §2 derivó de forma independiente para descartar la caja de 15 Å, pero mejor operacionalizado: en vez de un lado fijo, un lado **por ligando**.

Importa el orden temporal: el criterio es anterior a los resultados que motivan MF-08, así que incorporarlo **no es ajustar el diseño mirando el desenlace**.

## 2. El brazo nuevo

`B_ADAPT`: lado = **dimensión máxima del ligando + 4 Å de margen por lado**. Mediana resultante **18.2 Å** (rango 10.6–25.8).

Es estrictamente mejor que la caja fija de 20 Å como prueba de la hipótesis:

| Caja | Excluye el subsitio decoy | Ligandos que no caben | Margen de deslizamiento mediano (`L/2 − radio`) |
|---|---:|---:|---:|
| `B30` | — | 0 | 8.6 Å |
| `B25` (actual) | 6/33 | 1 | 6.12 Å |
| `B20` | 19/33 | 0 | 3.62 Å |
| **`B_ADAPT`** | **21/33** | **0** | **2.83 Å** |

Y resuelve el flanco débil del diseño anterior: los 4 complejos excluidos a priori por no caber en 20 Å (`1aaq`, `1h22`, `1hn4`, `1kpm`) **sí caben** con caja adaptativa. Se mantienen fuera de la cohorte para que los cuatro brazos se comparen sobre los mismos 33, y se reportan aparte como adenda.

## 3. Reformulación honesta del mecanismo

Los desplazamientos medidos son de **3–6 Å**, no de 20–40. Eso **no** es el ligando acoplándose en otro sitio de la proteína: es un **deslizamiento o volteo del modo de unión dentro del mismo bolsillo** — por ejemplo, correrse un subsitio en una hendidura tipo proteasa.

Dos hipótesis alternativas quedaron **refutadas con datos** antes de ejecutar:

- **Cofactores/metales ausentes en el receptor**: aparecen en 16% de los fallos frente a 29% de los cubiertos. Los complejos con metal en el bolsillo van *mejor*.
- **Copia simétrica del sitio en un multímero** (MolFlex no recorta cadenas, `moldesign-app/docs/SESSION_SUMMARY_v1.6.md` bug #7): multi-cadena aparece en 30% de los fallos frente a 41% de los cubiertos. Además la magnitud no encaja: otra protómero implicaría decenas de Å.

Por eso el brazo se llama adaptativo y no «anti-decoy»: lo que la caja recorta es **margen de deslizamiento**, y esa es la variable que los cuatro brazos ordenan de forma monótona.

## 4. Gates revisados

| ID | Gate | Criterio |
|---|---|---|
| G1 | Validez | ≥95% de las corridas completan sin error |
| G2 | **Recuperación** (primario) | `B_ADAPT` recupera **≥7 de los 33** — un tercio de los 21 abordables por geometría |
| G3 | **Monotonía** (mecanismo) | cobertura `B_ADAPT` ≥ `B20` ≥ `B25` ≥ `B30`, es decir monótona en el margen de deslizamiento (2.83 < 3.62 < 6.12 < 8.6 Å) |
| G4 | No regresión | `B_ADAPT` pierde como mucho 1 del control de 15 |
| G5 | Determinismo | 2 complejos repetidos dan el mismo RMSD |

G3 gana poder: pasa de tres puntos a **cuatro**, ordenados por una variable física continua. Un efecto sin monotonía sería efecto sin mecanismo y se registraría como tal.

## 5. Lo que no cambia

Cohorte (33 dominados por colocación + 15 de control), métrica (`rmsd_pose_pocket` sin alinear sobre todas las poses dockeadas, éxito ≤2.0 Å), configuración congelada (`n_conf=30`, `exhaustiveness=8`, `num_modes=9`, `top_k=3`, semillas 42), prohibiciones, y la advertencia de §7 del registro anterior: **la caja está centrada en el ligando cristalográfico**, así que un GO mide el mecanismo y **no** propone un cambio de producción — REC-03 midió el top-1 de MolPocket a 8 Å de mediana del ligando.
