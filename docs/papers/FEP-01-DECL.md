---
titulo: "Declarar tautómeros sube FEP-01 al 89 %, pero sólo resuelve el 19 %"
entradilla: "El roadmap predijo que declarar el tautómero llevaría la preparación para FEP de 19 % a más del 80 %. Se cumple: 180 de 203. Y la descomposición enseña por qué esa cifra no puede citarse sola."
---

`FEP-01` midió que 164 de 203 ligandos tienen más de un tautómero enumerable y
que el pipeline no declaraba cuál acoplaba. El tautómero decide qué átomos donan
y cuáles aceptan puentes de hidrógeno; para un cálculo de energía libre, elegir
uno en silencio es elegir la molécula.

El roadmap escribió una predicción concreta: declarar los tautómeros subiría
FEP-01 **de 19 % a más del 80 % de un golpe**. Este experimento la pone a prueba
con la declaración que ya produce el conformador.

## Qué es «declarar»

RDKit enumera los candidatos; no decide cuál domina en disolución, y su
tautómero canónico es una representación reproducible, no una predicción. Así
que la declaración tiene tres estados:

- **un solo tautómero** enumerable;
- **varios candidatos**, la lista completa y ninguno descartado, porque no hay
  un modelo de poblaciones validado;
- **no resuelto**: la enumeración falló o pasó del tope de 32.

El criterio de FEP-01 pasa de «un solo tautómero» a «tautómero declarado»
(cualquiera de los dos primeros). Estereoquímica y atom mapping se toman tal
cual de los sellos anteriores.

## Qué salió

**GO: 180 de 203 (88,7 %).** La predicción se cumple. Pero:

| | ligandos |
|---|---:|
| Un solo tautómero | **39** (19,2 %) |
| Listos **sólo** porque su multiestado quedó declarado | **141** |
| No resueltos (más de 32 tautómeros) | 22 |
| Bloqueados por estereoquímica | 1 |

Los 39 únicos son exactamente los 39 del sello: declarar no resolvió ni uno
más. Lo que hizo es convertir 141 ambigüedades silenciosas en ambigüedades
escritas, con sus candidatos (mediana 4, entre 2 y 31) y los átomos que cambian.

En PDBBind completo, sin gate, sobre 4641 ligandos legibles: 1003 con un solo
tautómero, 3187 con varios y 451 no resueltos. El reparto es el mismo.

## Por qué el 89 % no puede citarse solo

Un paquete con varios tautómeros no está resuelto: exige a quien calcula
tratarlos todos o elegir uno con evidencia. Un tautómero que en disolución sólo
tiene el 1 % de la población, tratado como si costara cero, ya introduce unas
2,7 kcal/mol, más que la precisión que se espera de un cálculo relativo. Por eso
el producto no cuenta como resuelto lo que sólo está declarado, y la cifra que
describe el estado real es la del 19 %.

## Lo que sigue

Un modelo energético validado que permita descartar los candidatos fuera de una
ventana de 2-3 kcal/mol, y que el paquete de exportación lleve todos los que
queden, cada uno con su identificador.

## La limitación, declarada

En PDBBind, 4 ligandos cambian de «único» a «varios» respecto del sello porque
aquí se conserva la estereoquímica sp3 al enumerar y el sello usaba el
enumerador por defecto. En los 203 coinciden los 39.
