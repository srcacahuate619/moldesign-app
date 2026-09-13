# MF-33-A3 — Multiplicar por 29 las poses no mueve un solo complejo

## Diagnóstico: `LA DIVERSIDAD CONFORMACIONAL ES REAL` — decisión `GO`

| Criterio preregistrado | Umbral | Resultado |
|---|---|---|
| **Primario** A3 vs B pareado en COLOCACION (n=33) | `g_B ≥ 6` con `g_A3 = 0` → lectura (2) | **`g_B` = 7, `g_A3` = 0**, McNemar exacto **p = 0.0156** |

La hipótesis que motivó el corrigendum **queda falsificada en la dirección declarada**. El
defecto era real como confundido; no era la explicación.

## Las tres variables igualadas, y por qué no hay escapatoria

`MF-33` se selló con un `defecto-abierto` porque su métrica es de oráculo —el mejor RMSD
entre las poses que el brazo **conserva**— y `num_modes=9` limita las poses escritas *por
corrida*, no las buscadas. El brazo B hacía 29 corridas y conservaba 261 poses; A y A2 hacían
una y conservaban 9. B podía ganar sólo por conservar más.

A3 corre **K corridas independientes desde el mismo `conf0.flex.pdbqt`**, con K = `n_docks`
de B en ese complejo. Eso iguala las tres:

| Variable | B | A3 |
|---|---:|---:|
| Corridas independientes | K | **K** (la misma) |
| Poses conservadas (mediana) | 261 | **261** |
| CPU (mediana, COLOCACION) | 3821.7 s | **4570.2 s** |

La razón de CPU es **1.196**: A3 gastó un **20% más** que B. Cualquier sesgo residual de
presupuesto favorecía a A3.

**Y aun así B alcanza 26 de 33 y A3 19.** Los 7 complejos de diferencia van todos en la misma
dirección: **no hay ni uno solo donde A3 alcance y B no**.

## El secundario es lo más limpio del experimento

| Brazo | Qué es | CPU | Poses conservadas | Alcanza |
|---|---|---|---:|---:|
| `C` | protocolo congelado, conformeros **rígidos** | baja | — | **1 / 33** |
| `A` | un conformero flexible, una corrida | baja | 9 | 12 / 33 |
| `A2` | **paridad de CPU**, una corrida muy profunda | igualada | **9** | **19 / 33** |
| `A3` | **paridad de CPU**, K corridas del mismo conformero | igualada | **261** | **19 / 33** |
| `B` | ensemble flexible, K conformeros distintos | referencia | 261 | **26 / 33** |

Lee la comparación `A2` contra `A3`: **misma CPU, 9 poses contra 261, y el mismo 19**.

Multiplicar por 29 el número de poses conservadas desde el mismo confórmero **no mueve ni un
complejo**. El conteo de poses —la explicación alternativa que este experimento venía a
descartar— está medido y **no aporta nada**. Los 7 complejos de diferencia son atribuibles a
la única variable que quedaba libre: **la conformación de partida**.

## Comprobación de cordura, declarada y cumplida

En CONTROL (n=15) todos los brazos convergen: `C` 15, `A` 14, `A2` 14, `A3` 15, `B` 15, con
`g_A3` = `g_B` = 0. El efecto es **específico del estrato difícil** y no un artefacto general
del brazo. Cero corridas fallidas en los 48 complejos.

## Qué se desbloquea

- **Se levanta la etiqueta `defecto-abierto` de `MF-33` y de `MF-33-A2`.**
- **La magnitud de `MF-33` es citable**: 1/33 rígido → 12/33 un confórmero flexible →
  26/33 ensemble flexible. La regla (2) autoriza expresamente el claim externo.
- `MF-33-A2` se relee **sin cambiar su número**: su 19/33 no era una limitación de conteo de
  poses, era el techo de un solo confórmero por mucha CPU que se le eche.
- **`MF-33-EXT` ya sabe cómo titularse.** Su prerregistro declaró que la elección entre
  «cobertura final» y «cobertura a presupuesto igualado» dependía de esta respuesta. Como la
  ventaja **no** es presupuesto, el titular es la **cobertura final**; la curva contra
  presupuesto queda como secundario descriptivo.
- **`MF-30-ALCANCE` no se mueve**: el comparador activo sigue siendo 26/33 y su gate sigue
  caducado 8.67×.

## Límites declarados

1. `n=33` en COLOCACION con un MDE de 6 complejos: esto **detecta** el efecto, no lo
   cuantifica con precisión.
2. **No dice por qué** la diversidad conformacional ayuda. Dice que ayuda.
3. No toca si esos confórmeros son alcanzables en producción. `MF-02A-EXT` midió ese techo en
   **83.9% a K30**, y sigue siendo el límite de arriba.
