---
titulo: "La métrica que alineaba las moléculas y borraba 12 complejos"
entradilla: "La cobertura estaba medida con un RMSD que alinea las dos moléculas antes de compararlas. Eso oculta desplazamientos: una pose a 7.83 Å del sitio real reportaba 2.755 Å."
---

Este experimento tenía que ser rutinario: aplicar el pipeline congelado a los 116
complejos de entrenamiento, dejar el material en disco, y reproducir un resultado anterior
para demostrar que el pipeline no tiene variabilidad oculta.

Cuatro de sus cinco criterios pasan, y el producto se entrega: **116 de 116 complejos con
material en disco**, 17,596 poses dockeadas, mediana de 171 por complejo, cada una con su
mapa de índices y su receptor.

La reproducción salió perfecta: **38 de 38** complejos comparables idénticos, sin ninguna
discrepancia. El pipeline es determinista.

El quinto criterio falló, y ahí está lo que importa.

## El número que no se sostuvo

El gate exigía una cobertura del oráculo de al menos 90%. Salió **79.3%**.

El umbral del 90% se había fijado sobre una medición anterior que daba 93.1%. Esa cifra
estaba **mal medida**.

La causa es una elección de métrica que parece inocua y no lo es. Hay dos formas de
comparar una pose con el cristal:

| Métrica | Qué hace | Qué oculta |
|---|---|---|
| RMSD con alineamiento | Superpone las dos moléculas antes de medir | **Dónde está la pose** |
| RMSD en marco de pocket | Compara coordenada a coordenada, receptor fijo | Nada |

La primera responde «¿tiene la forma correcta?». La segunda responde «¿está en el sitio
correcto?». Para conformación libre, la primera es la adecuada. Para una pose dockeada, es
justo la pregunta equivocada.

El caso que lo ilustra: el complejo `10gs` reportaba **2.755 Å** con alineamiento. Su pose
entregada está a **7.83 Å** del sitio bioactivo. La molécula tenía la forma correcta, en el
sitio equivocado, y la métrica sólo miraba la forma.

## La corrección, en números

Recalculando con la métrica correcta sobre el conjunto que realmente consume el pipeline:

| | Con la métrica equivocada | Con la correcta |
|---|---:|---:|
| Cobertura de train | 93.1% | **79.3%** |
| Complejos recuperados | 30 | **14** |
| Ganancia declarada | +26 puntos | **+12 puntos** |

**Doce complejos que la métrica alineada contaba como cubiertos no se sostienen.** La
ganancia real es menos de la mitad de la anunciada.

## Lo incómodo: ya estaba documentado

El repositorio tenía esto anotado como lección de una auditoría anterior. La advertencia
estaba escrita, con el nombre de la función culpable, semanas antes de que este
experimento la confirmara en datos.

Estaba escrita y no estaba comprobada por nada. Un aviso en un documento no impide que
alguien llame a la función equivocada; sólo lo impide un test o una función única que haga
lo correcto por defecto. De aquí sale la práctica de que la métrica de pose del programa
tiene **una sola implementación**, documentada con la razón de por qué no usa alineamiento,
y que cualquier implementación nueva se verifica contra ella.

## Qué sobrevive y qué no

**El material entregado es válido** y no depende de la métrica: son poses en disco, con su
procedencia. Nada de eso cambia.

**Lo que no sobrevive es el número.** Y como el número era la base de todo lo que se
construyó encima —la reconstrucción del conjunto, la precisión condicional, la reapertura
de la cartera de rescoring— todo eso tuvo que partir de 79.3% en vez de 93.1%.

Un NO_GO que entrega su producto y corrige la contabilidad del programa entero vale más
que un GO que la deja mal.
