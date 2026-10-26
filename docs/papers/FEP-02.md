---
titulo: "Los nueve que fallaron tienen saltos de numeración, nueve de nueve"
entradilla: "El 41 % de los receptores pasa los dos criterios de cribado del código, que no es estar listo para FEP. Y los nueve que fallaron tienen saltos de numeración, nueve de nueve: compatible con cortes de cadena, no una confirmación."
---

La mitad de un complejo proteína-ligando es la proteína, y sus defectos son menos visibles
que los del ligando. Una cadena con residuos ausentes, un sitio de unión repartido entre
dos cadenas, un metal sin coordinar, una decena de aguas cuyo papel nadie decidió: todo eso
se procesa sin error y sale con aspecto normal.

Esta auditoría cuenta cuántos de los 203 receptores tendrían documentado lo necesario para
un cálculo de energía libre.

## Qué salió

**83 de 203 (41%)** quedarían documentados. Y el desglose de lo que falta:

| Defecto | Complejos |
|---|---:|
| Huecos de numeración en la cadena | **86 (42%)** |
| Sitio repartido entre más de una cadena | **43 (21%)** |
| Metales en el sitio | 52 |
| Aguas en el sitio (mediana) | **10**, ninguna clasificada |

Ese 21% con el sitio repartido entre cadenas es un modo de fallo que el propio documento de
limitaciones del proyecto marcaba como conocido — y que **nadie había contado**. Estaba en
la lista de cosas sabidas, sin número al lado, que es una forma cómoda de no saber.

Las aguas merecen mención aparte: mediana de 10 por sitio, **ninguna documentada** como
estructural (parte del sitio, hay que conservarla) o desplazable (el ligando la echa al
unirse). Esa decisión cambia el resultado de un cálculo de energía libre, y hoy la toma por
omisión quien escribió el preparador.

## La verificación que no se buscaba

Meses antes, un experimento de campo de fuerza había fallado la parametrización en 9
complejos, todos con el mismo error de plantilla. El diagnóstico propuesto entonces fue que
tenían **cortes de cadena** dejados como extremos sin capar. Era una explicación plausible y
nadie podía comprobarla.

Esta auditoría, que se hacía por otro motivo, la comprueba:

> Los 9 complejos que fallaron tienen huecos de cadena. **9 de 9.**
>
> Tasa base en el conjunto: **42.4%**. Probabilidad de que salga así por azar: 0.424⁹ ≈
> **0.0004**.

El diagnóstico queda respaldado —la asociación es compatible con él, no lo confirma (SCI-B-007)—, y con
él la decisión que dependía de él: **no volver a
correr aquel experimento** para recuperar esos 9 complejos, porque su fallo no informaba
sobre el campo de fuerza sino sobre la preparación del receptor.

Es un buen ejemplo de por qué vale la pena registrar los diagnósticos aunque no se puedan
comprobar en su momento: escrito con precisión, un diagnóstico se puede verificar después
por un experimento que no existía cuando se formuló.

## La limitación, declarada

Un salto en la numeración de residuos **no siempre es un hueco físico**: hay convenciones de
numeración no consecutiva, sobre todo en estructuras alineadas a una referencia.

Así que los 86 son **candidatos, no defectos confirmados**. Cada uno exige mirar la
estructura.

Los 9 del caso anterior sí lo eran, lo cual da alguna confianza en el criterio pero no lo
valida en general. La cifra honesta es «86 estructuras a revisar», no «86 estructuras
rotas».

## Correcciones

**2026-10-20**, a raíz de la Fase B de la auditoría científica del producto. Ninguna cifra sellada cambia y no se repitió ningún cálculo; esto corrige lo que el texto afirmaba a partir de ellas. Detalle y procedencia en `docs/101_CORRIGENDA_SELLOS_AUDITORIA_20261020.md`.

- SCI-B-007. Que los 9 fallos de MF-10 tengan saltos de numeración, y la probabilidad de 0,424⁹, son **compatibles** con el diagnóstico de cortes de cadena; no lo confirman. Es una asociación, y la probabilidad supone una independencia que no se estableció.

**2026-10-22**, a raíz de la Fase B de la auditoría científica (fase 1b del plan de arreglos,
`docs/102_FASE_1B_CORRECCIONES.md`). Ninguna cifra sellada cambia.

- SCI-B-040. «Documentados» quiere decir que pasan los **dos criterios de cribado** que aplica
  el código: sin saltos de numeración y sin sitio entre cadenas. Metales, cofactores y aguas del
  sitio no entran en el criterio. Ni los 83 de 203 ni los 1543 de 3887 de PDBBind son receptores
  listos para FEP.
- SCI-B-041. `FEP-02-PDBBIND` declaró «comparable» sin margen ni gate, y su universo contiene a
  los 203. Excluyéndolos: 1460 de 3684 (39.6 %) frente a 83 de 203 (40.9 %). Es una coincidencia
  descriptiva, no una equivalencia probada; y la copia local no tenía 1438 receptores.

**2026-10-25** (inventario SUPUESTOS-01, C-232). El título y la entradilla seguían diciendo «huecos de cadena», «quedarían
documentados» y que la auditoría «verificó» el diagnóstico con p ≈ 0.0004, por encima de las correcciones SCI-B-007 y SCI-B-040.
Se reescriben con su alcance. Ninguna cifra cambia.

**2026-10-22.** El cuerpo decía todavía «el diagnóstico queda confirmado», que SCI-B-007 rebajó a compatible (hallazgo L2-SOL-005 de la revisión de papers de Sol).

## FEP-02-PDBBIND: el inventario del sitio conserva límites de la copia local de PDBBind

**GO de auditoría descriptiva.** Añade el inventario auxiliar, sin convertir la coincidencia de cribados de SCI-B-041 en equivalencia.

Entre los receptores legibles, el contador marca sitio entre cadenas en 938 casos, metales próximos en 819 y cofactores en 2; la mediana de aguas es 11. Son observaciones sobre `_protein.pdb` ya limpiados por PDBBind: lo que la fuente retiró no puede contarse como conservado ni perdido aquí.

La ausencia de archivos no se demostró aleatoria. **SCI-B-040 y SCI-B-041**, desarrolladas arriba, delimitan el cribado y la población comparada. No se vuelve a llamar completo al filtro de numeración y cadenas. No comprobado por mí: reconstruir inventarios desde los depósitos originales. Fuente: `FEP-02-PDBBIND`.
