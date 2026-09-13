---
titulo: "El 93.9% del programa se construyó con el protocolo que falla"
entradilla: "De las 34,302 poses del conjunto, sólo 2,087 se generaron con libertad torsional. Diecisiete artefactos sellados consumen el resto. Esto mide el alcance, no invalida nada."
---

`MF-33` midió algo incómodo: sobre los 33 complejos difíciles, el protocolo congelado
—docking **rígido** del ensemble— alcanza **1 de 33**, mientras los **mismos confórmeros**
dockeados flexibles alcanzan **26 de 33**.

Eso plantea de inmediato una pregunta de alcance que nadie había hecho: **¿qué fracción del
material sobre el que descansa el programa salió de ese protocolo?**

Se responde leyendo dos artefactos ya sellados. Cero cómputo.

## La composición

| Fuente | Poses | % | Generador |
|---|---:|---:|---|
| `molflex` | **32,215** | **93.9%** | Rígido, TORSDOF 0 |
| `flexible_redock` | 1,534 | 4.5% | Flexible |
| `ruta_a` | 553 | 1.6% | Flexible |

**Sólo el 6.1% del conjunto se generó con libertad torsional durante la búsqueda.**

Y **17 artefactos sellados** consumen ese material, entre ellos `RS-14`, `RS-09`, `RS-01`,
`RS-01A`, `MF-02D`, `FND-02`, `FND-06` y el propio `RC-F0-V2`.

## Tres cosas que este número NO autoriza a concluir

Se declararon antes de calcularlo, porque un número así invita a leerse mal.

**1. No invalida a los 17 consumidores.**

`MF-33` midió el hueco de **cobertura** — cuántos complejos tienen alguna pose correcta
entre las candidatas. Los experimentos de selección midieron **precisión condicional sobre
lo cubierto**, que es otra cantidad.

Más cobertura significa **más complejos evaluables**, no un veredicto distinto sobre los ya
evaluados. `RS-14` concluyó que el selector no supera a `vina_score` sobre los 92 complejos
cubiertos; con más cobertura habría más complejos, y la pregunta de si el selector gana en
ellos sigue abierta exactamente igual que antes.

**2. El 1 de 33 es del estrato difícil.**

En `CONTROL` el protocolo rígido alcanza **15 de 15**, y con la **mejor mediana de los tres
brazos** (0.861 Å). Extrapolar el 1/33 a los 203 sería injustificado.

> El protocolo rígido no está roto en general. Falla exactamente en el estrato que motivó el
> programa.

**3. `MF-33` tiene su propio defecto abierto.**

Su brazo ganador conservaba 261 poses de mediana contra 9 del rival, y su magnitud está
suspendida hasta que corra `MF-33-A3`. Citar este alcance como si la comparación estuviera
cerrada sería encadenar dos afirmaciones que todavía no lo están.

## Lo que sí establece

Una sola cosa, y hay que citarla así:

> **Cuánto material habría que rehacer si se decidiera medir sobre poses flexibles.**

La respuesta es: casi todo. 32,215 de 34,302 poses, y con ellas el denominador de la cartera
de rescoring entera.

Eso no es una conclusión científica — es una cifra de planificación. Pero es la que decide
si «volver a generar con docking flexible» es un experimento o es un programa, y la
respuesta que da es inequívoca: es un programa.

## El triaje de los 17 consumidores

La cifra sola invita a la lectura catastrofista. Lo que la vuelve utilizable es separar los
consumidores por **qué miden**, porque no todos están igual de expuestos.

### Categoría 1 — miden generación o cobertura: los más expuestos

`D-MF-HARD-CURVE`, `D-MF-HARD-CURVE-VAL`, `D-MF-HARD-EXH4`, `D-MF-HARD-EXH4-VAL`,
`MF-02B`, `MF-02D`, `RC-F0-V2`.

Sus números **son** propiedades del régimen de generación. La curva de confórmeros, la
comparación de brazos generadores, la cobertura del oráculo: todo eso se midió con docking
rígido y se remediría distinto con flexible. Son los que habría que rehacer primero.

### Categoría 2 — miden selección sobre casos ya cubiertos

`RS-01`, `RS-01A`, `RS-14`, `RS-14-PRE`.

**No quedan invalidados.** Compararon un selector contra `vina_score` dentro del conjunto
de complejos cubiertos, y esa comparación pareada sigue siendo válida sobre el material que
usó. Lo que queda abierto es otra cosa: **si su conclusión generaliza a una cohorte
regenerada**, con más complejos cubiertos y poses de otra distribución.

Que el selector no supere a `vina_score` sobre 92 complejos cubiertos con material rígido no
prueba que tampoco lo haga sobre 120 con material flexible. Tampoco prueba lo contrario.

### Categoría 3 — auditoría, procedencia e infraestructura

`FND-02`, `FND-06`, `MF-01-UNION`, `RS-09`, y los prerregistros `MF-02-PRE` y
`RC-F0-V2-PRE`.

Prácticamente no cambian. La fuga entre splits, la trazabilidad de cada pose, la invarianza
del selector a rotación y orden, la materialización de la unión — **ninguna depende de si la
pose se generó rígida o flexible**. Un conjunto regenerado heredaría estas propiedades o las
volvería a exigir, pero los hallazgos se sostienen.

### La formulación correcta

Esa separación evita el error de decir «el 94% del programa está mal». **Eso no está
demostrado.** Lo demostrado es más acotado:

> El 94% de las poses históricas viene de una política de generación que ahora sabemos que
> **puede ser muy insuficiente en el estrato difícil**.

Y con eso la pregunta de planificación cambia de forma. Ya no es «¿corremos otra variante de
`MF-33`?». Es:

> **¿Vale la pena reconstruir casi toda la cohorte de poses para cambiar el régimen de
> generación?**

Eso no es un experimento. Es un **programa de regeneración y revalidación**, y decidirlo
exige saber antes qué se gana — que es justo lo que `MF-33-A3` todavía no ha dicho.

## Por qué merecía un artefacto propio

Podría haber sido una nota al pie de `MF-33`. No lo es, por dos razones.

La primera es que el número tiene vida propia: cualquiera que en el futuro proponga rehacer
el conjunto necesita saber que son 32,215 poses y 17 artefactos, no un par de tablas.

La segunda es que las tres limitaciones de arriba tenían que quedar selladas **junto** al
número. Un dato así, suelto y sin sus condiciones de uso, se convierte en «el 94% del
programa está mal» en la primera conversación en que alguien lo repita de memoria.
