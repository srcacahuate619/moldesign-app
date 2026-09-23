---
titulo: "Reajustar LCPO no arregla los anillos con cuatro o cinco bromos"
entradilla: "Con coeficientes propios, el yodo casi aprueba y el bromo pasa validación. La prueba trae una cola que ningún juego de coeficientes corrige: los polibromados de la familia TBB, inhibidores de la CK2."
---

Tras el fracaso del LCPO del cloro para el bromo y el yodo (`MMGBSA-H1`), el
siguiente paso declarado era ajustar los cuatro coeficientes por elemento, sólo
con los átomos de entrenamiento, manteniendo el radio de Bondi fijo. Una
salvaguarda adicional (H10) comprobaba que lo aprendido no dependía de haber
visto los mismos scaffolds.

## Qué salió

**NO_GO: fallan 2 de 4 casos.**

- **Bromo.** Con los coeficientes elegidos en validación —casi los del cloro
  publicado—, validación **pasa** (mediana 0,94 Å², p90 4,85) y prueba **falla**
  (mediana 2,96, p90 9,70). La cola de la prueba aparece con cualquier juego de
  coeficientes: 9,44 con los de H1, 9,83 con el ajuste completo. Reajustar no la
  toca.
- **Yodo.** Prueba **pasa** (mediana 1,83, p90 4,04) y validación **falla** sólo
  por el intervalo del sesgo, con 6 átomos.
- **H10.** El bromo generaliza por scaffold; el yodo falla por 0,05 Å² sobre el
  margen, con 8 átomos.

## De dónde sale la cola del bromo

De anillos con cuatro o cinco bromos, la familia TBB de inhibidores de la CK2.
Ahí dos esferas grandes vecinas se solapan de una forma que LCPO no representa,
y el error crece con el enterramiento del átomo. Como en un complejo el
halógeno suele estar enterrado, la hipótesis siguiente fue dejar LCPO y calcular
el término no polar con una SASA numérica (`MMGBSA-H12A-FREESASA`).

## Una lección de método

Los coeficientes sueltos **no están identificados**: el de un término del yodo
varía un 1402 % entre remuestreos. La predicción, en cambio, es estable (≤ 0,74
Å²). Por eso el criterio de estabilidad dejó de exigir un CV < 20 % a los cuatro
coeficientes y pasó a pedirlo sólo al primero, junto con una dispersión de la
predicción ≤ 1,0 Å². Se cambió **antes** de ajustar con datos reales: ni con
datos sintéticos sin ruido se cumplía el criterio original.
