---
titulo: "INCONCLUSIVE: retirar las aguas que chocan deja una lectura mixta"
entradilla: "En 116 complejos, se normalizan 2 de 6 referencias con score clasificado como absurdo: fracción 0,3333. La salida es MIXTO e INCONCLUSIVE; el contraste de scoring no decide la política de aguas del docking."
---

**INCONCLUSIVE.** Se mantiene la lectura MIXTO de la regla escrita. El experimento no autoriza una retirada general de aguas ni cambia por sí mismo una política de producto.

## Por qué se hizo

Algunas referencias cristalográficas tenían un score desfavorable en el receptor experimental. La pregunta era si las aguas conservadas que chocaban con la referencia podían explicar ese comportamiento. No se confundió esta prueba de scoring con el problema de encontrar una pose de novo.

## Qué se midió

Sobre 116 complejos de train se comparó el mismo PDBQT rígido de ligando frente al receptor CON y frente al receptor tras retirar los registros de agua a 2,6 Å o menos de algún átomo pesado del cristal. Se usaron score_only, caja de 25 Å y semilla 42. La diferencia es CON menos SIN: un valor positivo indica score menor al retirarlos.

«Absurdo» es aquí la etiqueta operacional para score CON ≥ -3,0 kcal/mol. La normalización exige bajar de ese corte. La regla conserva un tramo intermedio entre 0,30 y 0,70; la rama superior requiere además mediana de control menor que 0,5 kcal/mol. Estos nombres de ramas no son diagnósticos biológicos.

El manifiesto no fija las versiones y hashes del ejecutable ni el helper del contenedor. Se revisan los valores almacenados; no se reproduce físicamente la corrida.

## Qué pasó

| Cantidad | Resultado | Condición |
|---|---:|---|
| Reproducción G1 de scores de MF-13 | 1,0000 | Fracción dentro de 0,10 kcal/mol |
| Referencias con score clasificado como absurdo | 6 | Definición anterior |
| Referencias normalizadas | 2 | Entre las anteriores |
| Fracción primaria | 0,3333 | Lectura MIXTO |
| Mediana del delta en controles no absurdos | 0,000 kcal/mol | Mismo contraste pareado |
| Complejos con algún registro bloqueante | 26 | Criterio geométrico frente al cristal |

En 1fkh se marcaron 2 registros de agua: el score pasa de +2,550 a -10,369 kcal/mol y el delta archivado es 12,919 kcal/mol. Es un contraste de esa función de puntuación en ese sistema, no una medida de afinidad experimental ni una demostración sobre todos los fallos.

## Qué dice y qué no dice

Las aguas conservadas pueden cambiar mucho el score de una referencia concreta. La fracción global no alcanza una rama concluyente de la regla. El criterio geométrico no distingue un agua desplazable de una que media una interacción. No se evaluó su efecto sobre búsqueda de novo, ni se decide que todas deban retirarse.

## Correcciones

**Vigentes al 2026-10-22.**

- **SCI-B-153:** la comparación por identificador confirma coincidencia de los scores CON de REC-09 con los scores de cristal de MF-13. En 1fkh el valor archivado es +2,550; en 1ew8, +2,064; -0,610 kcal/mol corresponde a 1eld. Se retiran los ejemplos narrativos anteriores que mezclaban complejos. La discordancia estaba en el texto, no en una falta observada de reproducción entre esas salidas.

Detalle: `docs/102_FASE_1B_CORRECCIONES.md`; estado en `docs/100_CORRECCIONES_AUDITORIA_CIENCIA_20261015.md`. Se contrastaron por identidad los valores almacenados. No comprobado por mí: regeneración del ligando, el receptor y los scores desde sus entradas originales, ausentes del worktree.
