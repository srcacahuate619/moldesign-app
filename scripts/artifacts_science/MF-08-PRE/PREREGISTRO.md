# MF-08-PRE — Prerregistro: ¿una caja generosa admite subsitios competidores?

**Fecha:** 2026-08-17
**Rama:** `experimentos/ruta-c-molflex`
**Estado:** PREREGISTRO (nada ejecutado bajo este registro)
**Refina:** `MF-08` de la cartera C (doc. 49 §8) — «la caja limita poses de MolFlex». Este registro invierte la dirección de la hipótesis y lo explica abajo.
**Entradas selladas:** `MF-02D` (material y métrica en marco de pocket), `MF-02B-R1` (cobertura corregida 79.3%).

---

## 1. De dónde sale la hipótesis

Descomponiendo el error de la mejor pose alcanzable de cada complejo de train en su componente **conformacional** (RMSD alineado: geometría interna del ligando) y su componente de **colocación** (el residuo ortogonal):

| | pocket | conformación | colocación |
|---|---:|---:|---:|
| Cubiertos (66) | 1.22 Å | 0.70 | 0.84 |
| **Fallidos (50)** | **3.71 Å** | **1.89** | **2.53** |

**En los fallidos la colocación domina en 33 de 50.** Hay casos con la conformación esencialmente resuelta y la pose en otro sitio: `1dgm` (conformación 0.90 Å, colocación 3.85), `1eld` (1.48 / 3.92), `10gs` (1.79 / 5.37).

Un desplazamiento de 4–6 Å dentro de una caja de 25 Å no es una puerta estérica entreabierta: es que **el ligando se acopla en otro subsitio que puntúa mejor**. La hipótesis es de **competencia de sitios**, no de estrechez de la caja.

Esto **invierte** el enunciado original de MF-08 («la caja limita poses»): se predice que la caja actual, lejos de limitar, es **demasiado generosa** y admite mínimos competidores.

## 2. Geometría ya computada, declarada antes de ejecutar

Con la caja centrada en el ligando cristalográfico y lado `L`, el centroide de una pose puede alejarse como mucho `L/2 − radio_ligando` antes de que la pose deje de caber. Medido sobre los 116 de train (radio = distancia máxima del centroide a un átomo pesado):

- **radio mediano del ligando: 7.04 Å** (máx 9.94).

| Caja | Excluiría el subsitio decoy | Ligandos que **no caben** |
|---:|---:|---:|
| 15 Å | 29/33 | **32 de 116** |
| **20 Å** | **19/33** | **4** |
| 25 Å (actual) | 6/33 | 1 |
| 30 Å | — | 0 |

**La caja de 15 Å queda descartada por física, no por resultados**: excluiría también la pose nativa en 32 de 116 complejos. El experimento usa **20 Å**.

**Predicción declarada**: con 20 Å el subsitio decoy queda fuera en **19 de los 33** complejos de la cohorte. Excluir el decoy es **necesario pero no suficiente** —el docking todavía tiene que encontrar la pose nativa—, así que se espera una recuperación menor que 19.

Los 19: `10gs`, `1afl`, `1apv`, `1b38`, `1bma`, `1c4u`, `1d3p`, `1d9i`, `1eb2`, `1ela`, `1eld`, `1ele`, `1ezq`, `1f0u`, `1fkh`, `1hpx`, `1jq8`, `1nm6`, `1nw5`.

## 3. Cohorte

- **Intervención (33)**: los complejos de train dominados por colocación (`colocación ≥ conformación`, pocket > 2.0 Å) que caben en 20 Å.
- **Control (15)**: complejos ya cubiertos, muestreados con `random.Random(42).sample`. Encoger la caja podría romper lo que funciona; el control lo mide.
- **Excluidos a priori por criterio físico** (radio > 10 Å, no caben en 20 Å): `1aaq`, `1h22`, `1hn4`, `1kpm`. Declarados **antes** de ejecutar, por geometría y no por resultado.

## 4. Brazos

| Brazo | Caja | Origen |
|---|---:|---|
| `B25` | 25 Å | **ya computado** — material de MF-02D, sin recomputar |
| `B20` | 20 Å | intervención principal |
| `B30` | 30 Å | **prueba de falsación** |

Todo lo demás idéntico y congelado: `n_conf=30`, `exhaustiveness=8`, `num_modes=9`, `top_k=3`, `cpu=1`, semillas ETKDG 42 y Vina 42, mismo centro de caja.

`B30` es lo que hace falsable la hipótesis: si el problema es competencia de sitios, **agrandar** la caja debe **empeorar** la cobertura. Si `B30` no empeora, el mecanismo propuesto es falso aunque `B20` mejore, y la mejora habría que atribuirla a otra cosa.

## 5. Métrica

Mínimo `rmsd_pose_pocket` (**sin alinear**) sobre **todas** las poses dockeadas del complejo; éxito = ≤ 2.0 Å. Idéntica a MF-02D y a la etiqueta del conjunto de poses.

## 6. Gates

| ID | Gate | Criterio |
|---|---|---|
| G1 | **Validez** | ≥95% de las corridas completan sin error |
| G2 | **Recuperación** (primario) | `B20` recupera **≥6 de los 33** — un tercio de los 19 que la geometría declara abordables |
| G3 | **Monotonía** (mecanismo) | cobertura en la cohorte: `B20` ≥ `B25` ≥ `B30`. Es el gate que prueba la **hipótesis**, no solo el efecto |
| G4 | **No regresión** | en el control de 15, `B20` pierde **como mucho 1** complejo cubierto |
| G5 | **Determinismo** | 2 complejos repetidos con la misma semilla dan el mismo RMSD |

**GO** = los cinco pasan. **NO_GO** = falla G2, G3 o G4.

Un GO con G3 fallando sería un efecto sin mecanismo: se registraría como tal y **no** se usaría para cambiar el protocolo.

## 7. Advertencia de transferencia a producción, declarada

La caja de MolFlex está **centrada en el ligando cristalográfico** (convención de re-docking, docs/40). Un GO aquí dice «con el sitio conocido con precisión, una caja más ajustada ayuda» — **no** dice que ajustar la caja ayude en producción, donde el centro sale de predicción de pocket. `REC-03` midió que el top-1 de MolPocket está a una mediana de **8 Å** del ligando: con ese error de centro, una caja de 20 Å perdería la pose nativa más a menudo que la de 25 Å.

Es decir: **este experimento mide el mecanismo, no propone un cambio de producción.** Cualquier despliegue exige antes resolver la precisión del centro.

## 8. Prohibiciones

- Prohibido elegir el tamaño de caja mirando el RMSD resultante: los tres brazos están congelados aquí.
- Prohibido reintroducir la caja de 15 Å: queda descartada por el criterio físico de §2, computado antes de ejecutar.
- Prohibido leer un GO como cambio de protocolo de producción (§7).
- No se toca val, test ni `D-RC-CONFIRM`: la cohorte es de train.
