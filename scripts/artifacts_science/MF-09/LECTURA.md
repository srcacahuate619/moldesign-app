# MF-09 — Es muestreo, no puntuación: la pose buena no existe entre 751 candidatas

**Tipo: medición.** No tiene prerregistro propio ni gates de aceptación: es lectura del material ya sellado de `MF-02D` + `MF-02F`, sin parámetros libres y sin cómputo nuevo. El umbral de 2.0 Å y la métrica `rmsd_pose_pocket` se heredan de toda la línea. Sus cifras son **descriptivas** y no deciden nada por sí solas.

## La pregunta

`MF-08` (menos espacio de búsqueda) y `MF-02F` (más reinicios) agotaron las dos palancas geométricas sobre la misma cohorte y ambas convirtieron 3 de 33 moviendo la mediana ~0.8 Å. Quedaban dos causas posibles:

- **(A) muestreo**: entre todas las poses generadas no existe ninguna a ≤2 Å. Ningún selector puede arreglarlo.
- **(B) puntuación**: la pose buena existe pero el score no la rankea arriba. Ahí sí hay margen para un selector.

## La respuesta

| | Dominados por colocación (33) | Control cubiertos (15) |
|---|---:|---:|
| Poses por complejo (mediana) | **751** | 80 |
| Oráculo (mejor RMSD disponible) | 2.961 Å | 0.956 Å |
| RMSD del top-1 por score | 7.683 Å | 2.097 Å |
| **Existe pose ≤2 Å** | **3 de 33** | **15 de 15** |
| El top-1 por score acierta | **0** | 7 |
| Acierta en top-5 / top-9 / top-20 | 1 / 1 / 2 | 14 / 14 / 15 |
| **Margen de selección** | 3 | **8** |
| Spearman(score, RMSD) | 0.186 | 0.483 |
| Percentil de la mejor pose por score | 11.1% | 16.7% |

**En 30 de los 33 complejos difíciles no existe ninguna pose a ≤2 Å entre ~751 candidatas.** Es muestreo, no puntuación. Ningún selector, por bueno que sea, puede elegir algo que no está.

Eso cierra la línea: la caja no era el problema, los reinicios no eran el problema, y el score tampoco lo es en esta cohorte. **El generador no visita la región correcta del espacio**, con 86 confórmeros, 9 modos cada uno y tres tamaños de caja probados.

## El hallazgo colateral, que vale más que la respuesta

El **control** cuenta la historia opuesta y es donde estaba la información útil:

- Los 15 tienen pose buena disponible.
- El top-1 por score acierta en **7**.
- El top-5 acierta en **14**.

**Margen de selección: 8 de 15 complejos** tienen la pose correcta disponible y el score de Vina no la pone primera, pero sí entre las cinco primeras. Ahí un selector tiene un recorrido real y grande — más de la mitad de los fallos de top-1 son recuperables sin generar una sola pose nueva.

El Spearman lo confirma: **0.483 en el control frente a 0.186 en la cohorte difícil**. El score de Vina ordena razonablemente donde hay señal y es casi ciego donde no la hay.

## Qué significa para el programa

Esto es la descomposición `Top-1 = cobertura × precisión condicional` de la §9, medida por primera vez **a nivel de pose** y no de complejo:

1. **Donde el generador produce, el selector tiene margen amplio** (7/15 → 14/15 con solo mirar el top-5). Es exactamente el terreno del selector, y confirma que la cartera D tenía dónde mejorar — sobre los complejos cubiertos.
2. **Donde no produce, no hay nada que seleccionar** y ninguna cantidad de features lo arregla. Los 30 complejos irreparables de esta cohorte no son un fallo del selector: nunca lo fueron.

La consecuencia práctica es que el esfuerzo se reparte al revés de como venía haciéndose: **mejorar el generador donde falla** (30 complejos sin material) y **mejorar el selector donde hay material** (8 de 15 recuperables en el control), y no medir al selector sobre complejos que el generador nunca cubrió — que es justo el error que `MF-02B-R1` documentó en el conjunto v1.

## Incidencia de análisis

La primera versión de este script leía **solo** el directorio de `MF-02F`, que contiene únicamente los confórmeros posteriores al prefijo K30 —el prefijo vive en el material de `MF-02D`—, y por tanto perdía la mitad de las poses: reportaba 495 poses medianas, oráculo 4.01 Å y solo 38 de 48 complejos. Corregido para unir ambos directorios, el oráculo mediano pasa a 2.961 Å, que **coincide exactamente** con el que `MF-02F` reportó por su propia vía. Esa coincidencia es la verificación de que la unión es correcta.

## Archivos

- `metrics.json` — resumen por estrato y definiciones operativas de muestreo/puntuación.
- `per_complex.jsonl` (48) — por complejo: número de poses, oráculo, RMSD y score del top-1, rango y percentil de la mejor pose, Spearman, y si acierta en top-1/5/9/20.
- `scripts/analisis_muestreo_vs_score.py`.
