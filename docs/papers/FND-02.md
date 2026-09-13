---
titulo: "Fuga entre conjuntos: 85 pares de receptor idéntico"
entradilla: "La auditoría buscaba confirmar que los conjuntos estaban limpios. Encontró 2 pares de ligando idéntico y 85 de secuencia de receptor idéntica cruzando train, val y test."
---

Este es el experimento que más gente se salta, porque su resultado esperado es «todo está
bien» y su ejecución no produce ninguna cifra publicable. Es también el que decide si
todas las demás cifras significan algo.

Si el mismo ligando, o la misma proteína, aparece en `train` y en `test`, cualquier
rendimiento medido en `test` está inflado por memorización. El modelo no generaliza: ya
vio la respuesta.

El gate era simple y absoluto: **cero fuga**, por PDB, por ligando, por scaffold y por
fuente. Los duplicados que quedaran tenían que estar justificados.

## Qué pasó

El gate no se cumple, por dos vías independientes.

**Ligando idéntico cruzando conjuntos — 2 pares:**

| Par | Conjuntos |
|---|---|
| `1ft7` / `1lcp` | val ↔ test |
| `1hmr` / `1hmt` | train ↔ val |

La causa es concreta y merece anotarse porque es un modo de fallo silencioso: el criterio
de separación usaba el **scaffold** de la molécula, y en ligandos **acíclicos** el
scaffold está vacío. Dos moléculas sin anillos comparten un scaffold vacío con todas las
demás, así que el criterio no las distingue y el respaldo por scaffold no llegó a
activarse. La regla funcionaba para todos los casos que alguien había mirado.

**Secuencia de receptor idéntica cruzando conjuntos — 85 pares**, en 14 familias de
proteína, afectando a **57 de 203 complejos**.

Ese segundo número es el grave. Más de una cuarta parte del conjunto comparte proteína con
otro complejo al otro lado de la línea.

## Qué significa para el resto del programa

Que la separación entre conjuntos es **por ligando, no por proteína**. Un modelo entrenado
aquí y evaluado en `test` ha visto antes esa proteína, aunque no ese ligando.

No invalida todo — para muchas preguntas la unidad de inferencia correcta es el par
ligando-proteína y la fuga por receptor es tolerable si se declara. Lo que invalida es
afirmar generalización **a proteínas no vistas**, que es una afirmación distinta y mucho
más fuerte.

De aquí sale la práctica de reportar los resultados estratificados por relación con el
receptor —visto / casi idéntico / no relacionado— en lugar de dar una cifra global. `AF-01`
fue el primero en aplicarlo, y por eso su decisión se selló como «reproducido **con
limitación de alcance**» en vez de simplemente «reproducido».

## Por qué un NO_GO aquí es una buena noticia

El resultado deseable de una auditoría de fuga es encontrarla. Si esta hubiera devuelto
«cero fuga» sin haber probado el caso de los ligandos acíclicos, el programa habría
seguido adelante creyendo en una separación que no existía, y cada número posterior habría
llevado ese error dentro sin que nada lo señalara.

Un NO_GO en un experimento de fundamentos no es un fracaso del proyecto. Es el instrumento
funcionando.
