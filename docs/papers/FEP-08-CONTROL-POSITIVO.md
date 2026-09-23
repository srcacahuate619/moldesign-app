---
titulo: "El auditor distingue una preparación experta, y contar tautómeros no la mide"
entradilla: "Sobre un benchmark preparado por expertos para FEP relativo, el auditor documenta el doble de receptores que en PDBBind. Pero el número de tautómeros sale igual: depende de la molécula. Y en uno de cada seis ligandos, los curadores eligieron un tautómero distinto del que acoplaría MolDesign."
---

MolDesign quiere ser un auditor de *readiness* para energía libre: decir qué le
falta a un sistema antes de un cálculo caro. Un auditor así tiene que pasar un
control positivo. Si marca igual una estructura preparada por expertos que una
sin preparar, no está midiendo preparación.

El control es el protein-ligand-benchmark de OpenFF («Best practices for
constructing, preparing, and evaluating protein-ligand binding affinity
benchmarks», Hahn et al.; dataset DOI 10.5281/zenodo.4813735; datos CC BY 4.0):
15 dianas con la proteína preparada y 369 ligandos con la protonación y el
tautómero elegidos por sus curadores. Se le aplicaron **sin modificarlas** las
mismas funciones selladas que auditaron PDBBind.

## Dos predicciones, fijadas antes de medir

**(a)** Lo que depende de la preparación tiene que distinguir. **(b)** Lo que
depende de la química, no.

## Qué salió

**GO: se cumplen las dos.**

| | OpenFF | PDBBind |
|---|---:|---:|
| Receptores documentables (sin huecos, sitio en una cadena) | **80,0 %** (12/15) | 39,7 % |
| Ligandos con un único tautómero enumerable | 18,2 % | 21,6 % |
| Ligandos con estereoquímica indefinida | 0 de 369 | 48 de 4641 |

El auditor de receptores ve la preparación: el doble de sistemas documentables.
Los tres que fallan lo hacen con motivo: cdk2 y trombina conservan un hueco de
numeración, y en tnks2 el sitio se reparte entre dos cadenas.

El recuento de tautómeros **no** la ve. Los curadores prepararon cada ligando a
conciencia y aun así el 82 % admite más de un tautómero. Contar tautómeros
describe la molécula, no el trabajo que se hizo con ella. La readiness de un
ligando no puede depender de cuántos tautómeros existen, sino de **quién eligió
uno y con qué evidencia**.

## El hallazgo que cambia el producto

En **62 de 369 ligandos (16,8 %)** el tautómero que eligieron los curadores no es
el canónico de RDKit. Y no están dispersos, sino que son series casi enteras:
cdk8 (19), tnks2 (18), syk (15) y cdk2 (10).

MolDesign acopla el canónico de RDKit. Si un investigador le entregara estas
moléculas, el producto sustituiría la elección de los curadores por la de un
canonicalizador que no pretende predecir poblaciones. Lo avisa, pero la
sustituye. Para docking con Vina apenas importa; para un paquete que va a un
cálculo de energía libre, la elección de una fuente curada es evidencia y no
debería perderse.

## La limitación, declarada

Con 15 dianas, cada receptor mueve la fracción siete puntos. El control dice si
el auditor distingue una preparación experta, no si las elecciones de los
curadores son correctas. El artefacto guarda nombres y resultados, no
estructuras del benchmark.
