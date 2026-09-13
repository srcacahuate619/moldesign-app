# MF-09-SYM — «30 de 33» sobrevive; el margen del selector encoge un 25%

**Tipo: medición.** Sin prerregistro propio ni gates de aceptación: relee el mismo
material sellado de `MF-02D` + `MF-02F` que leyó `MF-09`, con la misma cohorte
(`MF-02F/cohorte.json`) y el mismo umbral de 2.0 Å, cambiando **una sola cosa**: la
métrica. Cero cómputo nuevo.

**Origen:** la auditoría de `MF-10` del 2026-08-18 encontró que `rmsd_pose_pocket` no
corrige simetría (doc. 49 §5.1). `MF-09` sostiene el cierre de la cartera C con la
frase «en 30 de 33 complejos difíciles no existe pose ≤2 Å entre ~751 candidatas».
Este análisis rehace ese número exacto con la métrica corregida.

## Verificación de validez: reproduce `MF-09` línea a línea

Bajo la métrica ingenua, los cuatro números que definen `MF-09` salen idénticos:

| | `MF-09` sellado | `MF-09-SYM` ingenuo |
|---|---:|---:|
| Poses por complejo (mediana, COLOCACION) | 751 | **751** |
| Oráculo mediano (COLOCACION) | 2.961 Å | **2.961 Å** |
| Existe pose ≤2 Å (COLOCACION) | 3 de 33 | **3 de 33** |
| Top-1 por score acierta (COLOCACION) | 0 | **0** |
| Existe pose ≤2 Å (CONTROL) | 15 de 15 | **15 de 15** |
| Top-1 por score acierta (CONTROL) | 7 | **7** |

Sin esa reproducción, cualquier diferencia posterior sería indistinguible de un error
de lectura del material.

## El resultado

21,692 poses, 48 complejos.

| | COLOCACION (33) | | CONTROL (15) | |
|---|---:|---:|---:|---:|
| | ingenuo | corregido | ingenuo | corregido |
| Oráculo mediano | 2.961 Å | **2.905 Å** | 0.956 Å | **0.849 Å** |
| Existe pose ≤2 Å | 3 | **4** | 15 | 15 |
| Top-1 por score acierta | 0 | **1** | 7 | **9** |
| **Margen de selección** | 3 | **3** | **8** | **6** |

Poses que cruzan el umbral sólo por corregir simetría: **14 de 21,692 (0.06%)**.

## Lo que no cambia: la conclusión de MF-09 se sostiene

**«30 de 33» pasa a «29 de 33».** Un complejo —`1l83`, lisozima T4 L99A— gana
cobertura: su mejor pose mide **2.106 Å** con la métrica ingenua y **0.942 Å**
corregida, con 12 automorfismos. Es exactamente el caso que la auditoría anticipó.

Un complejo de 33 no mueve la conclusión: **sigue siendo muestreo, no puntuación**.
El generador no visita la región correcta en el 88% de la cohorte difícil, y ningún
selector puede elegir lo que no está. El oráculo mediano se mueve 0.056 Å.

## Lo que sí cambia, y afecta a la cartera D

**El top-1 de Vina es mejor de lo que se midió.** Corrigiendo simetría, el baseline
acierta en **9 de 15** controles en vez de 7, y en 1 de 33 dominados en vez de 0. Tres
complejos cambian de veredicto:

| Complejo | Estrato | Top-1 ingenuo | Top-1 corregido | Automorfismos |
|---|---|---:|---:|---:|
| `1l83` | COLOCACION | 2.106 Å | **0.942 Å** | 12 |
| `188l` | CONTROL | 2.353 Å | **0.951 Å** | 2 |
| `1bcd` | CONTROL | 2.273 Å | **1.506 Å** | 12 |

**Y por tanto el margen del selector encoge.** El «hallazgo colateral que vale más que
la respuesta» de `MF-09` —8 de 15 controles donde la pose correcta existe y el score
no la pone primera— es en realidad **6 de 15**. Una cuarta parte de ese margen no era
margen: era la métrica penalizando un anillo girado.

**Consecuencia para `RS-14`, y va en la dirección incómoda.** `RS-14` midió un selector
contra el baseline `vina_score` y falló el gate de superioridad por −0.047 con CI95
[−0.152, +0.062]. Ese baseline estaba **subestimado**: con la métrica corregida Vina
acierta más. El NO_GO de `RS-14` no sólo se sostiene — **es más robusto de lo que se
selló**, porque el rival real es más fuerte que el medido.

Añadido: las etiquetas del conjunto v2 (`rmsd <= 2.0` → positiva) se calcularon con la
métrica ingenua. Un puñado de poses está etiquetado como malo siendo bueno. El efecto
es pequeño (0.06% de las poses) pero se concentra en los ligandos simétricos, que son
los pequeños y rígidos del control — justo donde el selector tenía margen.

## La distribución del sesgo: raro pero concentrado

| Complejo | Estrato | Sesgo máximo | Poses que cruzan | Automorfismos |
|---|---|---:|---:|---:|
| `187l` | CONTROL | **3.036 Å** | 2 | 4 |
| `1l83` | COLOCACION | 2.283 Å | 5 | 12 |
| `188l` | CONTROL | 1.402 Å | 1 | 2 |
| `1bcd` | CONTROL | 0.767 Å | 3 | 12 |
| `1bju` | CONTROL | 0.679 Å | 2 | 4 |

El sesgo mediano por complejo es 0.0096 Å en COLOCACION y **0.0** en CONTROL: para la
inmensa mayoría de las poses la corrección no hace nada. Pero donde actúa, actúa
fuerte, y son siempre los mismos ligandos —benceno, fenol, xileno sobre lisozima T4—
que son pequeños, rígidos y muy simétricos. `1nq7` tiene **72 automorfismos** y aun así
sesgo máximo de 0.295 Å: no basta con tener simetría, hay que estar en una pose donde
la permutación importe.

## Qué NO hace este análisis

- **No reabre `MF-09`.** Su sello es inmutable y su decisión no cambia; esto es una
  relectura declarada, con su propio registro.
- **No recalcula artefactos sellados** (doc. 49 §5.1): el sesgo es de signo conocido
  —corregir sólo puede bajar el RMSD— así que toda cobertura publicada es una cota
  inferior y ningún `NO_GO` por falta de cobertura se voltea.
- **No toca val ni test**, ni el conjunto v2. Re-etiquetarlo con la métrica corregida
  exige su propio prerregistro y cambiaría el denominador de la cartera D otra vez.

## Archivos

- `metrics.json` — resumen por estrato con ambas métricas y la lista de complejos que ganan cobertura.
- `per_complex.jsonl` (48) — por complejo: oráculo y top-1 bajo ambas métricas, número de automorfismos, sesgo mediano y máximo, poses que cruzan.
- `scripts/analisis_simetria_mf09.py`.
