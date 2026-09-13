# RS-14 — El selector aprende señal real, y aun así no supera a Vina

## Decisión: NO_GO

| Gate | Criterio | Resultado |
|---|---|---|
| G1 validez | los 348 ajustes LOCO completan | PASS — 1,348 ajustes en total |
| G2 **superioridad** | condicional > baseline, CI95 pareado excluyendo 0 | **FAIL** |
| G3 **nulo** | condicional > percentil 95 del nulo por permutación | **PASS con holgura** |

## La descomposición de la §9, medida por primera vez sobre el denominador corregido

| | Selector | Baseline `vina_score` |
|---|---:|---:|
| Cobertura del oráculo | 79.3% (covariable, idéntica para ambos) | — |
| **Precisión condicional** | **0.4312** | **0.4783** |
| Top-1 global (ITT) | 0.3420 | 0.3793 |

Diferencia pareada sobre los 92 complejos cubiertos: **−0.0471, CI95 [−0.1522, +0.0617]**.

## Lo que este NO_GO sí dice, y lo que no

**No dice que el selector no aprenda nada.** El nulo por permutación es contundente: con 200 permutaciones que barajan las etiquetas dentro de cada complejo, la distribución nula tiene media 0.104 y percentil 95 en **0.163**. El selector alcanza **0.431**, casi tres veces por encima, con **p empírico 0.0**. En el régimen `p > n` que temíamos —233 features, 116 complejos— el modelo **no está memorizando ruido**: extrae señal real y reproducible.

**No dice que el selector sea peor.** El intervalo de confianza **cruza el cero** ([−0.152, +0.062]). La lectura honesta no es «el selector pierde» sino **«el selector empata dentro del ruido, y el gate exigía superioridad demostrada»**. Se preregistró así a propósito: un selector que no supera al baseline no justifica su complejidad.

**Sí dice que lo que aprende no añade nada sobre el score de Vina.** Aprende, pero aprende aproximadamente lo mismo que ya sabía la función de puntuación.

## El límite de potencia, que es el hallazgo operativo

Con 92 complejos cubiertos, la diferencia observada de −0.047 equivale a **4.3 complejos**, y el intervalo de ±0.10 equivale a **±9 complejos**. Es decir: **este diseño no puede detectar diferencias menores a ~10 puntos porcentuales.**

Cualquier mejora realista de un selector sobre este baseline está por debajo de ese umbral. Con n=92 no se puede resolver, y **más semillas, más features o más árboles no lo arreglan** — la incertidumbre viene del número de complejos, no del modelo.

Eso es exactamente lo que la §19.1 dice desde el principio: *«con 233 features y n=116 complejos como unidad de inferencia, el régimen es p > n y la palanca es multiplicar complejos, no señales»*. El experimento lo confirma cuantitativamente por primera vez, y pone el número: **hacen falta ~4× más complejos** para resolver diferencias de 5 puntos.

## Contraste con MF-09

`MF-09` midió que en el control cubierto hay **8 de 15 complejos** donde la pose correcta está disponible y el top-1 por score no la elige, pero sí está entre las cinco primeras. Ese margen **existe** y el selector **no lo captura**.

Las dos mediciones juntas dicen algo preciso: el material para mejorar está ahí, la señal que el selector extrae es real, y aun así la conversión a Top-1 no llega. El cuello no es la disponibilidad de la pose ni la capacidad de aprender — es que las 233 features actuales no distinguen la pose correcta de sus vecinas mejor de lo que ya lo hace la función de puntuación.

## Variabilidad entre semillas

Condicional por semilla: **0.467, 0.380, 0.446**. El rango de 0.087 entre semillas es **casi el doble** de la diferencia con el baseline (0.047). Con tres semillas, buena parte de lo que se mide es ruido de inicialización — otra manifestación del mismo problema de potencia.

## Qué NO se hizo, y por qué

- **No se tocaron val ni test.** Un NO_GO en train no consume el confirmatorio.
- **No se compararon cifras con v1.** v0.6 se entrenó sobre v1 y la tarea cambió de ~9 a ~162 candidatos: cualquier comparación cruzada mezclaría cambio de datos con cambio de tarea.
- **No se ajustaron hiperparámetros.** Son los de v0.6, congelados en el prerregistro.
- **No se reportó Top-1 global como gate.** El gate es la precisión condicional, con la cobertura como covariable, según la §9.

## Consecuencia para el programa

La cartera D se reabrió con el denominador corregido —que era la condición que la §19.1 exigía— y el resultado es que **el problema no era el denominador**. Con cobertura del oráculo al 79.3% en vez del 67.2%, el selector sigue sin superar al baseline.

Eso deja la línea en un sitio distinto y más claro que antes: no es que faltaran poses buenas, ni que el modelo no aprenda. Es que **el espacio de features actual está agotado frente a `vina_score`**, y la resolución del experimento está limitada por el número de complejos, no por el modelo.

## Archivos

- `PREREGISTRO.md` (en `RS-14-PRE`, sellado antes de ejecutar) — el cambio de denominador declarado y el gate sobre la precisión condicional.
- `metrics.json` — descomposición de la §9, por semilla, diferencia pareada con CI95 y nulo por permutación.
- `per_complex.jsonl` (116) — por complejo: cubierto, acierto del baseline, acierto del selector por semilla, poses y oráculo.
- `nulo.json` — las 200 réplicas de la distribución nula.
- `scripts/run_rs14_selector_v2.py`.
