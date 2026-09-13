---
titulo: "El contrato que llevaba semanas sin cerrarse"
entradilla: "Dos experimentos lo alimentaron y uno de ellos prohibió expresamente concluir sin él. La agregación nunca se ejecutó, y el programa siguió adelante dando su conclusión por hecha."
---

`RS-03-PARAM-A` parametrizó los 116 ligandos de entrenamiento con OpenFF Sage y NAGL, pasó
los once requisitos primarios del contrato congelado, y terminó su sello con una frase:

> «Siguiente: `RS-03-PARAM-B` (AM1-BCC estratificado) y luego `RS-03-PARAM` (agregación)».

`RS-03-PARAM-B` produjo la referencia y cerró el suyo con una prohibición todavía más
explícita:

> «**PROHIBIDO concluir sobre NAGL desde B**: la decisión es de `RS-03-PARAM` agregando A y
> B contra el contrato del PRE maestro».

La agregación nunca se ejecutó. Durante semanas, el resto del programa usó las cargas nuevas
dando la decisión por hecha, mientras el artefacto que debía tomarla no existía.

Este experimento la toma. No calcula ninguna carga: **verifica los once requisitos contra
los artefactos sellados** y emite lo que el contrato define.

## El veredicto

**Once de once requisitos pasan**, evaluados y sellados por A:

| | Exigido | Obtenido |
|---|---|---|
| Cobertura global | ≥ 95% | **100%** |
| Cobertura por estrato | ≥ 90% en los 6 | **100%** en los 6 |
| Determinismo | ≤ 1e-6 | **2.78e-17** |
| \|Σq − carga formal\| | ≤ 1e-4 | **1e-15** |
| Fallback silencioso | 0 | **0** |
| Energía finita y serializable | 100% | 100% |
| Mapeo biyectivo + hash de orden | Sí | Sí |
| Versión y SHA del modelo | Registrados | Registrados |

> **Decisión del contrato: aceptar NAGL como base de cargas**, en sustitución del tipado
> heurístico que nadie había validado.

## La asimetría que hace válida esta decisión, y que no puse yo

Viene del contrato congelado, escrito antes de ejecutar nada:

- AM1-BCC es **referencia estratificada, no verdad absoluta**;
- queda **prohibido seleccionar NAGL mirando RMSD o Top-1**.

Es decir: **B caracteriza, no decide.**

Y eso importa aquí más que en ningún otro sitio, porque B encontró divergencia sustancial:
diferencia de carga mediana de **0.0118 e** por átomo, y una diferencia de energía de punto
único con mediana de **24.3 kJ/mol** y máxima de **216.4** — del orden de lo que un
rescoring pretende resolver.

Sin la asimetría declarada de antemano, habría sido natural leer esa divergencia como un
suspenso. No lo es:

> La divergencia **documenta un límite. No reprueba el método.**

Reprobarlo exigiría que A fallara un requisito primario, o un experimento de **rendimiento**
que el contrato prohíbe expresamente usar en esta decisión.

Es el mejor ejemplo del programa de por qué se escribe el criterio antes: con los números
delante, la tentación de dejar que 216 kJ/mol decidieran habría sido difícil de resistir, y
habría sido una decisión tomada por el dato más llamativo en vez de por el criterio
acordado.

## El caveat que viaja con la aceptación

Aceptar NAGL **no** significa que las diferencias con AM1-BCC sean irrelevantes.

Son del tamaño del efecto que un rescoring quiere medir. Divergen más en azufre y fósforo. Y
**crecen con el tamaño y la flexibilidad** del ligando — justo donde el programa trabaja.

Cualquier experimento de rescoring físico debe declarar qué juego de cargas usa y por qué.
No es una formalidad: es la diferencia entre medir un efecto y medir una elección de
parametrización.

## Por qué un contrato sin cerrar es un problema

Nada de lo que el programa hizo con esas cargas era incorrecto — A había pasado sus once
gates y estaba sellado. Pero durante semanas la afirmación operativa «NAGL sustituye al
tipado heurístico» no tenía artefacto que la sostuviera, sólo un experimento que la
preparaba y otro que prohibía sacarla de él.

Cerrar el contrato costó dos milisegundos. Dejarlo abierto costó semanas de una conclusión
usada sin registro.
