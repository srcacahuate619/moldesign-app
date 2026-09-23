---
titulo: "El GBn2 de OpenMM no era el de Amber en cuanto había azufre"
entradilla: "Para el azufre, Amber usa una serie donde OpenMM integra, y además corta a 25 Å. Reproducidas esas dos ramas, el desacuerdo cae de 11,24 kcal/mol a una cienmilésima."
---

La paridad entre OpenMM y sander para bromo y yodo (`MMGBSA-H5`) dejó un cabo
suelto: con azufre, los dos programas discrepaban en GBn2 hasta 11,24 kcal/mol.
No era un detalle de ligandos raros. Toda metionina y toda cisteína de un
receptor lleva azufre.

## La causa, leída en el código

El fuente de Amber (`egb.F90`) calcula la integral del radio efectivo de dos
formas. Cuando la distancia entre átomos supera cuatro veces el radio
apantallado del vecino, usa una **serie de Taylor**. El azufre de GBn2 tiene un
factor de apantallamiento negativo, así que para él la serie se usa
**siempre**. OpenMM evalúa en todos los casos la integral cerrada. Además, Amber
corta la suma a 25 Å (`rgbmax`) y limita el radio inverso a 1/30 Å⁻¹.

## Qué se probó

Reescribir las expresiones de GBn2 en OpenMM con esas ramas
(`apply_amber_gbn2_descreening`) y comprobar que coincide con sander en
topologías con y sin azufre, y en dos péptidos con Met y Cys, uno de ellos de
56 Å para que el corte de 25 Å importe.

## Qué salió

**GO.**

| | sin la corrección | con la corrección |
|---|---:|---:|
| 14 topologías con azufre (residuo máximo) | 11,24 kcal/mol | 1,3·10⁻⁵ |
| 41 sin azufre | 2,0·10⁻⁵ | 2,0·10⁻⁵ (sin cambio) |
| Dipéptido Met-Cys (ff14SB) | 0,92 kcal/mol | 1,6·10⁻⁶ |

El OpenMM del Python que se entrega en Windows reproduce al de Linux en 57 de
57 comparaciones. Sin el corte de 25 Å el péptido largo deja 4,1·10⁻³ kcal/mol:
hacen falta las dos ramas.

## Qué significa

El MM-GBSA candidato sobre OpenMM **no calculaba el GBn2 parametrizado en
cuanto había una Met o una Cys**. Con la corrección, sí. Nada de esto está
conectado a la aplicación: MM-GBSA sigue desactivado hasta pasar sus puertas.
