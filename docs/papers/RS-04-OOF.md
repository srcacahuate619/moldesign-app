---
titulo: "La tensión de la pose no distingue falsos mínimos"
entradilla: "Una pose forzada debería delatarse por su energía interna. Añadir esa señal al selector bajó los aciertos de 47 a 39, con regresión concentrada en el estrato difícil."
---

Un motor de docking puede producir una pose que encaja geométricamente pero que exige a la
molécula una conformación absurda: ángulos forzados, enlaces tensionados, una geometría
que ninguna molécula real adoptaría. Esa pose es un falso mínimo, y la función empírica de
Vina no la penaliza lo suficiente porque no modela bien la energía interna.

La señal para detectarlo es directa: la **tensión** — la diferencia entre la energía del
confórmero tal como quedó en la pose y la de ese mismo confórmero relajado en aislamiento.
Mucha tensión significa que el motor torció la molécula para que cupiera.

Es una de esas ideas que son físicamente correctas y que aun así no funcionan.

## Qué pasó

| | Aciertos Top-1 fuera de muestra |
|---|---:|
| Selector base | 47/116 |
| **Con la tensión añadida** | **39/116** |
| Exigido por el gate | ≥50/116 |

No sólo no llega: **baja 8 aciertos** respecto a no añadirla. Y la regresión se concentra
precisamente en el estrato difícil, que es donde la señal tenía que ayudar.

El resto de criterios sí se cumplen, y conviene decirlo porque acota la interpretación:

- mediana pareada del cambio de RMSD: **0.000 Å** — la señal es neutra en calidad de pose;
- cobertura: **100%** — se calculó para todas las poses, no falló en ninguna;
- costes en el percentil 95: dentro de presupuesto.

El test de McNemar da p = 0.115, que no es significativo. Así que la lectura estadística
honesta es que **no se demuestra degradación**, sólo que no hay mejora y el gate exigía una.

## Qué significa exactamente

La tensión MMFF94s es **coste-neutral y sin poder de selección en esta cohorte**. No hace
daño a la calidad de las poses; simplemente no contiene información que ayude a ordenarlas
que no esté ya en el score.

Hay una explicación plausible que este experimento no puede confirmar: puede que las poses
tensionadas ya estén filtradas antes de llegar aquí, porque el propio Vina las penaliza
lo bastante como para que no lleguen al top. En ese caso la señal es redundante por
construcción, no inútil por naturaleza.

## Dónde encaja en la historia más larga

Este es uno de los negativos que la regla de futilidad contó para cerrar la línea del
selector. Junto con la deduplicación, el enrutador de decidibilidad y los dos intentos
posteriores sobre el conjunto reconstruido, forma un patrón: **cada señal nueva que se
añade al espacio de características no mueve la aguja frente a `vina_score`**.

Y hay un contrapunto que este experimento no vio venir. `MF-16-R1` midió después que un
potencial físico **relajado** —que es la misma idea llevada un paso más allá: no medir la
tensión, sino quitarla antes de puntuar— sí supera a Vina en el estrato difícil. La
diferencia entre las dos es que aquí la tensión se usó como *característica* y allí como
*transformación del paisaje*.

El selector de producción no cambió. `val` y el conjunto confirmatorio quedaron intactos.
