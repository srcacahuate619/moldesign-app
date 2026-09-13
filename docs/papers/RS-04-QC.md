---
titulo: "Comprobar que se puede medir, antes de medir"
entradilla: "Mapeo biyectivo del 99.49%, los átomos pesados no se mueven ni una milésima, y 14 poses degeneradas declaradas como no computables en vez de rellenadas con un número."
---

Antes de preguntar si la tensión de una pose ayuda a seleccionarla, hay que comprobar que
la tensión **se puede calcular de forma fiable** sobre este material. Suena obvio y casi
nunca se hace: lo normal es calcular la característica, meterla en el modelo, y si el
modelo no mejora concluir que la característica no sirve.

Ese razonamiento tiene un agujero. Si la característica estaba mal calculada en un 20% de
los casos, el experimento no midió si la tensión ayuda: midió si la tensión mal calculada
ayuda. Y la respuesta a esa pregunta no interesa a nadie.

## Qué se comprobó

| Criterio | Exigido | Obtenido |
|---|---|---|
| Mapeo biyectivo de átomos | ≥99% | **99.49%** |
| Los átomos pesados no se mueven | — | **0.0 Å exacto** |
| Cobertura del campo de fuerza | ≥95%, sin recurrir a uno peor | **116/116**, sin respaldos |
| Determinismo | — | Byte a byte |
| Coste en frío, percentil 95 | ≤5 s/ligando | **55.7 ms** |
| Coste con caché, percentil 95 | ≤100 ms/pose | **68.0 ms** |
| Coste por complejo, percentil 95 | ≤3 s | **1,726 ms** |

Dos de estos merecen comentario.

**«Los átomos pesados no se mueven: 0.0 Å exacto».** Calcular la tensión exige añadir
hidrógenos y preparar la molécula. Si en ese proceso los átomos pesados se desplazan
aunque sea un poco, la tensión calculada corresponde a una pose ligeramente distinta de la
que se está evaluando. El resultado es exactamente cero, así que la geometría evaluada es
la geometría real.

**El coste está entre 20 y 90 veces por debajo de su presupuesto.** Eso importa porque
convierte la característica en algo que puede usarse en producción, no sólo en un
experimento. Una señal que tarda 5 segundos por ligando no entra en un cribado.

## Las 14 poses degeneradas

Dos complejos aportan 14 poses cuya geometría no permite calcular la tensión de forma
significativa. Se declaran como **no computables** y se marcan como tales.

Es la misma decisión que aparece en varios registros de este programa, y es la que separa
un conjunto de datos utilizable de uno envenenado: un valor «no computable» explícito
permite excluir esas filas después; un cero, o la mediana del resto, se propaga en silencio
por cada análisis posterior.

## Lo que este experimento autoriza

Con estos números, el experimento científico puede proceder sabiendo que un resultado
negativo será interpretable: si la tensión no ayuda a seleccionar, no será porque estuviera
mal calculada.

Y el resultado fue negativo — la tensión bajó los aciertos de 47 a 39. Ese negativo vale
porque este control existía. Sin él, la conclusión honesta habría tenido que ser «no
sabemos si la señal no sirve o si la medimos mal», que no es una conclusión.

Es fontanería. Toda la diferencia entre un resultado y una anécdota está en ella.
