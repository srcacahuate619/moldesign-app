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
rígido —salvo los comparadores `D-MF-HARD-EXH4` y `D-MF-HARD-EXH4-VAL`, con ligando flexible— y se
remediría distinto con flexible. Son los que habría que rehacer primero.

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

## Correcciones

**2026-10-22**, a raíz de la Fase B de la auditoría científica (fase 1b del plan de arreglos,
`docs/102_FASE_1B_CORRECCIONES.md`). Ninguna cifra sellada cambia.

- SCI-B-147. La lista obtenida por coincidencias de nombres y rutas es un inventario de
  posibles referencias a la familia de datasets. Incluye versiones distintas y no constituye un
  grafo de consumidores directos del material v2. No se usa su tamaño para fijar cuántas
  corridas habría que repetir. Esa decisión exigiría enlazar ruta exacta, hash y dependencia
  efectiva, sin invalidar automáticamente conclusiones previas.

**2026-10-22.** La categoría 1 atribuía docking rígido también a los comparadores EXH4, que usan ligando flexible (hallazgo L2-SOL-001 de la revisión de papers de Sol).

## D-MF-HARD: la cohorte de desarrollo separa flexibilidad y controles

**GO operacional.** Define la población de los comparadores históricos citados arriba; no prueba eficacia del generador.

Se seleccionaron 22 ligandos hard con al menos 15 torsiones y otros tantos controles con no más de 4. En cada estrato hay 17 de train y 5 de val. El emparejamiento sin reemplazo se hizo dentro del split, minimizando primero diferencia de átomos pesados y después masa y tamaño del receptor. No garantiza equilibrio químico.

El universo conservado tiene 156 miembros de train+val; la intersección con test es 0. Oracle_gap es un indicador secundario dependiente de etiqueta; no decide pertenencia, emparejamiento ni parámetros. Val es piloto, no confirmatorio. Esto no convierte el inventario de SCI-B-147 en un grafo de dependencias directas.

Fuente: `D-MF-HARD`. No comprobado por mí: regenerar las propiedades moleculares usadas en la selección.

## D-MF-HARD-CURVE: el presupuesto elegido no rehabilita la cobertura hard

**GO de elección de presupuesto para el piloto.** Añade el comparador de desarrollo sin cambiar la composición del conjunto descrito en este paper.

Se compararon prefijos de confórmeros bajo el protocolo congelado. La cobertura es oráculo con RMSD de bolsillo de 2.0 Å o menos, no precisión de una pose seleccionada.

| Train | Miembros | Cubiertos con K = 15 | Cubiertos con K = 30 |
|---|---:|---:|---:|
| Hard | 17 | 3 | 4 |
| Control | 17 | 15 | 15 |

La regla enmendada elige el menor presupuesto admisible por pérdida de cubiertos y degradación del RMSD mediano. El gate técnico también fue enmendado: acepta modelos efectivamente emitidos si el proceso termina bien y sus scores de REMARK VINA RESULT son finitos. No se atribuye esa enmienda al diseño original.

No se demuestra saturación ni equivalencia entre presupuestos. La propia lectura califica NO_GO la cobertura hard del presupuesto elegido. No comprobado por mí: repetir las corridas. Fuente: `D-MF-HARD-CURVE`.

## D-MF-HARD-CURVE-VAL: la validación del presupuesto es un piloto descriptivo

**GO de ejecución piloto.** Añade val del presupuesto fijado sin reajustarlo ni convertir train en confirmación externa.

Se conservó K = 15, configuración y métrica de bolsillo del ensayo de desarrollo. Los intervalos Wilson son los archivados.

| Val | Cubiertos / miembros | IC 95 % de cobertura |
|---|---:|---|
| Hard | 2 / 5 | [0,118; 0,769] |
| Control | 4 / 5 | [0,376; 0,964] |

No hubo fallos ITT registrados. El tamaño limitado y los intervalos no prueban equivalencia con train. No comprobado por mí: reconstruir las corridas. Fuente: `D-MF-HARD-CURVE-VAL`.

## D-MF-HARD-EXH4: el comparador flexible supera a MolFlex en esta cohorte de desarrollo

**GO limitado al contraste de desarrollo.** Añade el comparador histórico, sin demostrar superioridad en sitios desconocidos ni modificar v2.

Usó vina 1.2.7, ligando flexible, receptor rígido, exhaustividad 4, semilla 42 y caja cristalográfica de 25 Å. También la conformación inicial era cristalográfica. La cobertura es el oráculo sobre todas las poses del brazo, con el criterio de bolsillo, no el top-1.

| Train hard | Resultado |
|---|---:|
| Cubiertos por el comparador flexible | 11 / 17 |
| Cubiertos por MolFlex del presupuesto elegido | 3 / 17 |
| Discordancias a favor / en contra del comparador | 8 / 0 |
| McNemar exacto bilateral archivado | 0,0078125 |
| CPU-h hard del comparador, medida | 0,67 |
| CPU-h hard de MolFlex, estimación con P50 por corrida | 2,214 |

El coste de referencia es un estimador, no una medición pareada. Los otros contrastes y control no establecen la misma superioridad. El ajuste de multiplicidad del registro es sensibilidad post-hoc, no parte del prerregistro. No comprobado por mí: repetir docking, inferencia o tiempos. Fuente: `D-MF-HARD-EXH4`.

## D-MF-HARD-EXH4-VAL: la extensión a val no es confirmación ciega

**GO de ejecución descriptiva.** Añade val sin modificar el presupuesto ni la decisión de train.

Con la configuración del comparador flexible anterior se cubrieron 2 de 5 hard y 2 de 5 controles. Ambas fracciones tienen IC Wilson del 95 % archivado [0,118; 0,769]. No hubo fallos ITT registrados.

Es la primera ejecución de este brazo sobre val, pero esa cohorte ya se examinó con MolFlex. El sello la declara no ciega ni confirmatoria. La igualdad observada entre estratos no demuestra equivalencia. No comprobado por mí: repetir corridas o intervalos. Fuente: `D-MF-HARD-EXH4-VAL`.
