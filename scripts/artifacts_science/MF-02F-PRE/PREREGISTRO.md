# MF-02F-PRE — Prerregistro: los confórmeros como reinicios de búsqueda (K30 → K60 → K90)

**Fecha:** 2026-08-17
**Estado:** PREREGISTRO (nada ejecutado bajo este registro)
**Refina:** `MF-02` (doc. 49 §8) por el eje de **muestreo**, no el conformacional.
**Entradas selladas:** `D-MF-HARD-CURVE` (curva K5/K15/K30 con docking), `MF-02D` (material K30 de los 116 de train), `MF-08-PRE-R1` (cohorte de fallos por colocación).

---

## 1. La corrección que motiva este experimento

`MF-02A` midió el **techo conformacional** —RMSD alineado del ensemble ETKDG contra el cristal— y encontró saturación entre 60 y 90 confórmeros. De ahí escribí en `docs/49` que «añadir confórmeros es la palanca equivocada».

**Eso era demasiado fuerte, y el registro sellado lo contradice.** En MolFlex **cada confórmero es una corrida de docking independiente** (`dock_rigido_archivo` por `cid`, una invocación de Vina = 9 modos). `n_conf` tiene por tanto **dos papeles**: diversidad conformacional y **número de reinicios de búsqueda**. MF-02A sólo midió el primero.

`D-MF-HARD-CURVE` (sellado) mide el segundo:

| K | cobertura hard (17) | mediana | cobertura control (17) |
|---:|---:|---:|---:|
| 5 | 5.9% | 5.278 Å | 82.3% |
| 15 | 17.6% | 4.024 Å | 88.2% |
| **30** | **23.5%** | 4.011 Å | 88.2% |

Ganancia pareada K15→K30: **−0.289 Å, CI95 BCa [−1.01, −0.099]** (excluye el cero). El artefacto declara explícitamente que «NO se declara saturación completa». **Los controles saturan en K15; los hard no.** Y nadie ha medido K60/K90 con docking.

Esto importa porque el modo de fallo dominante es la **colocación** (33 de 50), y más reinicios es una intervención sobre la colocación.

## 2. Anidamiento verificado antes de diseñar

`construir_ensemble` usa `EmbedMultipleConfs(numConfs=N, randomSeed=42, pruneRmsThresh=0.4)`. Se verificó que el ensemble de 30 es **prefijo byte-idéntico** del de 90:

| pid | ensemble K30 | ensemble K90 | prefijo idéntico |
|---|---:|---:|---|
| `10gs` | 29 | 76 | 29/29 |
| `1a30` | 29 | 86 | 29/29 |
| `1dgm` | 23 | 46 | 23/23 |
| `1eld` | 24 | 47 | 24/24 |

Dos consecuencias:

1. El brazo K30 **es literalmente el material sellado de MF-02D**: no se recomputa, y la comparación no arrastra ninguna diferencia de ejecución.
2. Sólo hay que dockear los confórmeros **más allá del prefijo ya dockeado**, lo que reduce el coste en un tercio.

El anidamiento se verifica **para toda la cohorte** durante la corrida y es un gate (G5): si algún complejo no anida, sus arms no son comparables y se excluye.

## 3. Diseño

**Cohorte**: los mismos **33 dominados por colocación** + **15 de control** de `MF-08-PRE-R1`, para que ambos experimentos sean comparables sobre la misma cohorte.

**Brazos**: `K30` (material de MF-02D), `K60`, `K90` — definidos por el `numConfs` **solicitado**; el número efectivo tras el pruning se reporta por complejo.

Todo lo demás congelado: caja 25 Å centrada en el ligando, `exhaustiveness=8`, `num_modes=9`, `cpu=1`, semillas ETKDG 42 y Vina 42.

**Métrica**: mínimo `rmsd_pose_pocket` (sin alinear) sobre todas las poses dockeadas del brazo; éxito ≤ 2.0 Å.

## 4. Lo que NO es evidencia, declarado por adelantado

Con prefijos anidados, el conjunto de poses de K90 **contiene** al de K60 y éste al de K30. Por tanto **la cobertura sólo puede subir o quedarse igual: la monotonía está garantizada por construcción y NO es un resultado.**

Lo único informativo es la **magnitud** —cuántos complejos cruzan el umbral— y el **coste por complejo recuperado**. Cualquier lectura que presente la monotonía como hallazgo estaría describiendo una tautología.

## 5. Gates

| ID | Gate | Criterio |
|---|---|---|
| G1 | Validez | ≥95% de las corridas completan sin error |
| G2 | **Recuperación** (primario) | `K90` recupera **≥3 de los 33** dominados por colocación |
| G3 | **Saturación** | si `K60`→`K90` no añade ningún complejo, se declara el eje de reinicios **saturado en K60** y se registra como tal |
| G4 | Determinismo | 2 complejos repetidos dan el mismo RMSD |
| G5 | Anidamiento | el ensemble K30 es prefijo exacto del K90 en todos los complejos de la cohorte |

**Umbral de G2, derivado y no inventado**: `D-MF-HARD-CURVE` ganó **+5.9 puntos** de cobertura hard al duplicar de K15 a K30 (1 complejo de 17). De K30 a K90 hay 1.58 duplicaciones, que a la misma tasa dan ≈9% → **3 de 33**. Se exige exactamente eso; pedir más sería exigir que la curva acelere cuando la evidencia dice que desacelera.

**GO** = G1, G2, G4 y G5 pasan. **NO_GO** = falla G2. G3 no decide: informa.

## 6. Relación con MF-08

`MF-08` y `MF-02F` atacan el **mismo** modo de fallo —colocación— por vías distintas y sobre la **misma cohorte**:

- `MF-08` quita **espacio para deslizarse** (caja adaptativa);
- `MF-02F` da **más intentos** (reinicios).

Se ejecutan por separado y con un solo grado de libertad cada uno. Si ambos dan GO, la combinación exige su propio experimento: **queda prohibido** asumir que los efectos se suman.

## 7. Prohibiciones

- Prohibido presentar la monotonía como evidencia (§4).
- Prohibido cambiar el umbral de G2 tras ver resultados: su derivación está en §5.
- Prohibido mezclar este eje con el de la caja en la misma corrida.
- No se toca val, test ni `D-RC-CONFIRM`.
