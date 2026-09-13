---
titulo: "Reproduce al tercer decimal con 4.6 veces más poses"
entradilla: "0.1858 aquí contra 0.186 antes. La ausencia de embudo no era un artefacto de muestreo escaso, y corregir la simetría no la mueve ni un decimal."
---

Un resultado incómodo merece que se intente tirarlo abajo antes de construir encima. La
medición anterior había encontrado que en el estrato difícil no hay embudo —correlación
0.186 entre distancia al cristal y puntuación— y de esa medición dependían decisiones
importantes: descartar familias enteras de métodos de optimización.

Había dos formas plausibles de que esa cifra fuera un artefacto:

1. **Muestreo escaso.** Con pocas poses por complejo, un Spearman bajo puede ser ruido.
2. **La métrica de simetría.** Un anillo rotado 180° es la misma molécula; si el RMSD no lo
   trata bien, las etiquetas están sucias y cualquier correlación se degrada.

Este experimento prueba las dos.

## Verificación primero

Antes de nada, reproducir lo anterior sobre el material nuevo: **0.1858** frente a
**0.186**. Coincide al tercer decimal.

Eso verifica que la lectura del material es correcta, y es la clase de comprobación que
distingue una extensión de un experimento nuevo con el mismo nombre.

## Qué pasó con las dos explicaciones

**Muestreo escaso: descartada.** Con **751 poses por complejo** —4.6 veces más que antes—
la cifra no se mueve:

| Estrato | ρ |
|---|---:|
| Colocación | **0.186** |
| Control | **0.507** |

Y por radios, dentro del estrato difícil:

| Radio | ρ |
|---|---:|
| ≤ 4 Å | 0.279 |
| ≤ 6 Å | 0.140 |

Ni siquiera acercándose mejora de forma útil.

**Simetría: descartada.** Corregir la métrica de simetría deja el valor en **0.1858 con
ambas métricas**. Idéntico. El embudo —o su ausencia— es invariante a esa elección.

Esa segunda comprobación importa más de lo que parece, porque en otro experimento del
programa la corrección de simetría **sí** cambió las cosas: reveló un 21% de etiquetas
positivas mal marcadas y duplicó la brecha entre un selector y su baseline. Que aquí no
cambie nada no era predecible, y por eso había que medirlo.

## Lo que sigue sin poder medirse

A radios de 2 Å o menos **siguen sin existir complejos medibles** en el estrato difícil,
incluso con 751 poses.

La razón no es estadística sino física: en 30 de 33 complejos **no hay ninguna pose ahí**.
No se puede calcular una correlación en una región del espacio que el generador nunca
visitó, por muchas poses que se generen fuera de ella.

## Por qué este registro existe

Porque el resultado que verifica es de los que cierran puertas. Descartar familias de
métodos basándose en una correlación medida sobre 163 poses por complejo habría sido
imprudente; hacerlo sobre 751, con la métrica de simetría comprobada por ambos caminos, es
otra cosa.

Un negativo que sostiene decisiones grandes necesita que alguien haya intentado tumbarlo.
