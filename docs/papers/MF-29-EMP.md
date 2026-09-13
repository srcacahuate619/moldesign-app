---
titulo: "Sesenta y cuatro veces más búsqueda mueve tres complejos de cuarenta y ocho"
entradilla: "83.3 horas de CPU contra 4.1, y ninguna ganancia llega a un tercio de kcal/mol. El brazo masivo está saturado, que era justo la condición que le daba sentido a la cota."
---

Hay una pregunta que precede a todas las demás de esta cartera: **¿el buscador ya encontró
lo que hay que encontrar?**

Si Vina a `exhaustiveness=8` ya está devolviendo el mínimo de su propia función, entonces
todo lo que falla es la **función**, y no hay nada que arreglar en la búsqueda. Si no lo
está, hay margen y el diagnóstico cambia por completo.

La forma correcta de contestarla sería certificar el óptimo global. Se intentó: la jerarquía
de Lasserre se declaró **no implementable en este hardware** antes de correr. Lo que queda es
una **cota empírica** —subir el presupuesto hasta que deje de comprar— y una cota empírica no
certifica nada. Por eso `MF-29`, el certificado, sigue **abierto**.

El diseño: dos brazos sobre el mismo ligando flexible, `exh=8` con 5 semillas contra
`exh=512` con 3. Cohorte de 50 con ≤6 torsiones en el PDBQT, que es la dimensión que Vina
realmente busca.

## Qué salió

La cantidad primaria se declaró antes: fracción de complejos donde el brazo masivo mejora el
score por más de 0.10 kcal/mol, el ruido declarado.

| Criterio preregistrado | Resultado |
|---|---|
| ≥0.30 → **BÚSQUEDA** · <0.10 → **OBJETIVO** | **3/48 = 0.0625 → OBJETIVO** |

Los tres complejos que se mueven, y el tamaño del movimiento:

| Complejo | Estrato | TORSDOF | Producción | Masivo | Ganancia |
|---|---|---:|---:|---:|---:|
| `1d7i` | COLOCACION | 2 | −2.371 | −2.653 | **+0.282** |
| `1m2x` | RESTO | 6 | −5.882 | −6.120 | +0.238 |
| `1bn1` | RESTO | 6 | −7.143 | −7.268 | +0.125 |

Ninguno llega a un tercio de kcal/mol. En **45 de 48** la diferencia cabe en el ruido, y en
**19** el masivo salió *peor* que producción —nunca por más de 0.05—.

| Estrato | n | Mejoran | Ganancia mediana | Ganancia máxima |
|---|---:|---:|---:|---:|
| COLOCACION | 7 | 1 | 0.003 | 0.282 |
| CONTROL | 12 | 0 | 0.002 | 0.039 |
| RESTO | 29 | 2 | 0.001 | 0.238 |

**El coste: 83.3 h de CPU contra 4.1 h.** Veinte veces el tiempo —con tres semillas contra
cinco— para mover tres complejos menos de un tercio de kcal/mol.

Y la condición que valida la lectura: la desviación estándar entre semillas baja de **0.013
a 0.009** medianos. El brazo masivo está **saturado**. Si no lo estuviera, «no mejora» sólo
significaría «no busqué bastante»; saturado, significa que ahí no hay nada más.

## La enmienda: un instrumento se retiró, no un umbral

Esta lectura se selló primero como `INCONCLUSIVE`, y merece contarse por qué.

Había un segundo instrumento preregistrado, un **testigo**: `MF-13` puntuó el cristal
relajado sobre el mismo receptor y la misma caja, y su prerregistro lo declaró cota superior
independiente del mínimo global. La regla era «si el cristal puntúa mejor que el brazo
masivo, la búsqueda falló». El cruce daba **34 de 48 (70.8%)** a favor del cristal, con
déficit mediano de 0.49 kcal/mol. Parecía «aterriza en la cuenca y no baja al fondo».

Los dos instrumentos apuntaban en direcciones opuestas, y con dos instrumentos válidos en
conflicto la única salida honesta era `INCONCLUSIVE`.

`MF-29-EMP-COR` —prerregistrado y sellado **antes** de correr— midió que **uno de los dos no
medía lo que decía medir**: el testigo comparaba un ligando escrito con `TORSDOF 0` contra
uno con hasta seis torsiones activas, y Vina divide la afinidad por `(1 + w_rot · N_rot)`. El
salto de escala solo es de **+1.055** kcal/mol medianos, más del doble del déficit que se
estaba leyendo como fallo de búsqueda. Corregido a igual escala, el déficit se invierte:
**−0.406**, el masivo puntúa mejor, y en 36 de 48.

> No se movió ningún umbral ni se eligió instrumento después de ver el resultado. Se retiró
> un instrumento **inválido**, con un experimento propio, preregistrado, que costó 98
> segundos.

Con el testigo fuera, la cantidad primaria queda sola, su lectura preregistrada `OBJETIVO`
se sostiene, y la decisión pasa de `INCONCLUSIVE` a `GO`.

Queda anulado, además, el **confusor del confórmero** que esta lectura había declarado como
siguiente paso obligado: no hay que comprobarlo, porque el déficit que se le iba a atribuir
no existe.

## Cuarenta y ocho y no cincuenta: dos plazos vencidos

`1mmr` y `1nm6` aparecen como `VINA_FALLO` en las tres semillas del brazo masivo, con
`t_total_s: 0`, que **parece** una caída instantánea. No lo es: ese campo sólo suma las
corridas con éxito. El tiempo de fila menos el del brazo de producción da **43,200.4 s** y
**43,200.6 s** — exactamente 3 × el `timeout=14400` que estaba **en duro** en el runner.

Es la trampa que este laboratorio ya tenía registrada: *un timeout por debajo del tiempo de
un complejo produce síntomas idénticos a un fallo real*. A `exh=512` estos dos necesitan más
de cuatro horas por semilla.

`MF-29-EMP-EXT` los recuperó con el plazo convertido en parámetro. Mejora uno: la unión
queda en **4/50 = 0.08**, sigue siendo `OBJETIVO`, y la lectura de aquí no cambia.

## Qué autoriza y qué no

**Autoriza** cerrar la vía de «subir el presupuesto del mismo buscador». Está medido, está
saturado, y cuesta 20× para nada. Refuerza lo que `MF-25` vio con 16×.

**No autoriza** declarar resuelto el diagnóstico de `MF-13`, que quedó `MIXTO` con un
componente de búsqueda flagrante. Ese `MIXTO` se midió contra el mejor dock del conjunto v2
—otro protocolo, ~751 poses por complejo— y no contra el brazo masivo de aquí. Se comprobó
además, en `MF-13-ESCALA`, que `MF-13` **no** arrastra el desajuste de escala que el
corrigendum retiró: su top-1 viene de `molflex`, que dockea el PDBQT rígido, y su gate queda
idéntico —23/33 = 0.6970— al restringirlo a poses rígidas.

**No certifica optimalidad global.** Una cota empírica no es un certificado, y `MF-29` sigue
abierto.

**No extrapola** fuera del régimen de ≤6 torsiones, ni reabre `MF-03/04/05/07/12`: son
parámetros del mismo buscador, y esto es una razón más para no volver ahí.

## Nota de registro

El artefacto se creó **retroactivamente** al cerrar la corrida: el experimento se lanzó al
servidor sin manifest, y `created_at` es del sellado y no del lanzamiento — el mismo caso que
`MF-14` y `MF-19`. El prerregistro real es el docstring del script, sellado por hash en
`assets_hashes`, y es anterior a la corrida.
