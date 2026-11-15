---
titulo: "El pKa único por clase se equivoca más en las aminas y las amidinas, pero todavía no hay con qué sustituirlo"
entradilla: "Para decidir la carga de un ligando a pH 7,4, MolDesign usa un pKa fijo por grupo químico. Contra 2345 pKa medidos de ChEMBL25, dos clases mejoran claramente con otro valor: las aminas alifáticas y las amidinas. Ninguna especie cambia, y los datos no dicen qué átomo se midió, así que el valor de la tabla se queda."
---

**GO para seguir evaluando dos clases; no autoriza cambiar ningún valor.** En andamios que el ajuste no vio, la mediana medida mejora
el error de la tabla en `amina_alifatica` (0,51 unidades de pKa, IC 95 % 0,18–0,88) y en `amidina` (1,81, IC 95 % 0,64–2,76). Las
otras doce clases no pasan el criterio.

## Qué se midió

MolDesign decide la especie de un ligando con una tabla: cada grupo ionizable tiene un pKa fijo (9,8 para las aminas alifáticas, por
ejemplo). Ese valor decide la carga que ve Vina, el LogD y el CNS-MPO. AMINA-PKA-01 ya había visto que en las aminas con un grupo
atractor cerca el 9,8 se pasa de largo. Este experimento lo mira con una colección independiente.

- **Datos:** la extracción de ChEMBL25 de Baltruschat y Czodrowski (DOI 10.12688/f1000research.22090.2), con pKa y temperatura medidos.
- **Unidad:** cada molécula con un solo grupo ionizable de la tabla. Quedaron 2345. Se descartaron 1360 mezclas o especies cargadas,
  2753 sin asignación única a una clase y 84 con mediciones que discrepaban más de una unidad.
- **Separación:** por andamio de Murcko, unos para calcular la mediana de cada clase y otros, distintos, para evaluarla.
- **Criterio, escrito antes:** al menos 20 moléculas de ajuste y 20 de evaluación, 10 andamios de evaluación, una mejora del error de
  0,5 unidades o más con el intervalo a favor, y ninguna especie que pase al lado equivocado de 7,4.

## Qué pasó

| Clase | n evaluación | Error de la tabla | Mediana medida | Mejora (IC 95 %) |
|---|---:|---:|---:|---:|
| `amina_alifatica` | 241 | 1,89 | 8,3 | 0,51 (0,18–0,88) |
| `amidina` | 27 | 3,78 | 8,0 | 1,81 (0,64–2,76) |
| `piridina` | 119 | 1,98 | 6,4 | 0,22 (−0,21–0,55) |
| `acido_carboxilico` | 91 | 0,97 | 4,0 | 0,03 (−0,05–0,08) |

- **Las dos clases que pasan sobrestiman el pKa** (sesgo de +1,70 y +3,71): la tabla las da más básicas de lo que se mide.
- **Las decisiones de especie no empeoran.** La tabla y la mediana aciertan el lado de 7,4 en el mismo número de moléculas sin
  ambigüedad: 139 de 193 aminas y 13 de 25 amidinas. Un recuento decimal que excluye los bordes de la banda da 139/188 y 13/24.
- **En las series del producto casi no hay medida directa:** 1 de los 203 ligandos de MolFlex y 0 de los 89 padres de 8T69 están en
  ChEMBL25. Como escenario, se aplicaron las medianas a los 67 de MolFlex y los 89 de 8T69 que se pudieron comparar. Ninguna
  especie cambia, pero el LogD cambia en 63 y 89 y el CNS-MPO en 66 y 89.

## Qué dice y qué no dice

- **Dice dónde está el error:** en las aminas y las amidinas, el pKa único es el punto débil de la tabla.
- **No dice qué valor poner.** ChEMBL25 da un pKa por molécula sin decir qué átomo se midió, y sustituir un valor exige ese dato.
  Por eso se conserva el 9,8.
- **Un número mejor por clase no arregla el problema de fondo:** el entorno químico mueve el pKa dentro de una misma clase. En
  AMINA-PKA-01, el 9,8 se equivoca de media 0,69 unidades en las aminas alifáticas normales y 3,39 en las que tienen un atractor.
- **Lo que se decidió después** es ampliar la «especie en revisión» a esas subclases sin tocar la tabla. Está pendiente de
  implementar. La evidencia completa está en la
  [ficha D-04 de la investigación de 1.0.4](../auditorias/investigacion-1.0.4/D04.md).
