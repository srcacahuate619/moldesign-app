---
titulo: "Un GO que certifica la auditoría, no el resultado"
entradilla: "Reprodujo exactamente las métricas históricas y midió el efecto de la deduplicación: −4 aciertos, 0 recuperaciones, cero pérdidas de cobertura. El sello dice explícitamente que esto no demuestra equivalencia."
---

Antes de cambiar la entrada de un modelo congelado hay que saber qué le hace ese cambio. La
deduplicación de poses reduce el volumen; la pregunta es si al reducirlo altera el
comportamiento del selector que ya está en producción.

Este experimento es la auditoría de ese cambio, en el propio conjunto donde el modelo se
desarrolló.

## Qué se midió

**Primero, que el punto de partida es el correcto.** Se reprodujeron exactamente las
métricas históricas del checkpoint congelado. Sin eso, cualquier diferencia observada
después podría ser un artefacto de haber cargado mal el modelo.

**Después, el efecto:**

| | Resultado |
|---|---:|
| Cambio en aciertos Top-1 | **−4** |
| Recuperaciones (fallos que pasan a aciertos) | **0** |
| Mediana pareada del cambio de RMSD | **0.000 Å** |
| Pérdidas de cobertura del oráculo | **0** |
| McNemar | p = 0.25 |
| Intervalo agrupado de aciertos | [−10, 0] |

El intervalo no excluye el cero. La lectura estadística es que **no se demuestra
diferencia**, en ninguna dirección.

Lo más informativo es la combinación de dos números: **−4 aciertos con 0 recuperaciones**.
No es que el cambio reordene y salgan las cuentas parecidas; es que sólo quita. Cuatro
complejos que el modelo acertaba dejan de acertarse y ninguno de los que fallaba se
recupera.

## El contrafactual, y lo que reveló

Se ejecutó además un análisis contrafactual completo sobre los 31 empates, y mostró
**sensibilidad al criterio de desempate por fuente**.

Ese detalle es más importante de lo que parece. Significa que parte del comportamiento del
selector en los casos ajustados no lo decide el modelo, sino la regla arbitraria que decide
qué pose gana cuando dos puntúan igual — y esa regla depende de qué generador produjo cada
una.

Una porción del rendimiento medido no es del modelo. Es del orden en que le llegan las
cosas.

## La declaración que acompaña al GO

El sello es explícito sobre su propio alcance, y merece citarse porque es el contenido
principal de este registro:

> Este GO certifica **la ejecución de la auditoría**. No demuestra equivalencia, ni
> compatibilidad científica, ni mejora generalizable.

Y una segunda limitación, declarada también: todo esto es **dentro de la muestra**. Se
midió en el conjunto donde el modelo se desarrolló, así que ni siquiera las diferencias
observadas se pueden extrapolar.

## Por qué se selló así

Porque es exactamente el tipo de registro que en seis meses se leería mal. «RS-01A: GO» en
un listado, junto a un experimento sobre deduplicación, invita a concluir que la
deduplicación quedó validada.

No quedó validada. Quedó **auditada**, que es otra cosa: se sabe qué hace, se sabe que no
pierde cobertura, se sabe que quita cuatro aciertos sin recuperar ninguno, y se sabe que
nada de eso es estadísticamente distinguible del ruido con este tamaño de muestra.

La decisión de producción que salió de aquí fue no adoptarla por defecto.
