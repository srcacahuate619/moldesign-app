---
titulo: "Las aguas no se pierden: se conservan todas, y nadie lo decidió"
entradilla: "Buscaba metales desaparecidos y encontré 1,788 aguas cristalográficas dentro del receptor que Vina usa. No es un fallo de la preparación. Es una política de modelado que opera sin estar escrita."
---

`REC-08` comprobó que la preparación del receptor no pierde **cadenas** del sitio de unión.
Quedaba la otra mitad de lo que `FEP-02` había contado y nadie había verificado: **52
complejos con metales en el sitio** y una **mediana de 10 aguas, ninguna documentada** como
estructural o desplazable.

La pregunta era la misma que en `REC-08`, con otra entidad: ¿sobreviven a la preparación?

## Los metales: cero pérdidas

| | |
|---|---:|
| Complejos con metal en el sitio | 29 |
| Iones totales | **42** |
| Conservados | **42** |
| Perdidos | **0** |

Especies implicadas: Ca, Cu, Mg, Mn, Zn.

Es el resultado que esperaba y es una buena noticia aburrida: perder un ion coordinado al
ligando habría sido un defecto de producción serio, y no ocurre.

## Las aguas: el resultado que no buscaba

**1,788 aguas cristalográficas en los sitios de unión, conservadas al 100%.**

Y ese «100%» no significa lo que parece. No es que la preparación las respete: es que **las
mantiene todas**.

Lo verifiqué directamente sobre el fichero que Vina usa:

| Complejo | Átomos en `rec.pdbqt` | De ellos, agua |
|---|---:|---:|
| `10gs` | 4,137 | 169 |
| `1a30` | 2,049 | **216** |
| `1bcd` | 2,710 | 213 |

En `1a30`, `HOH` es el **segundo residuo más común del receptor**. Vina las trata como parte
de la proteína: ocupan volumen y entran en la rejilla de afinidad.

## Lo que esto convierte

`FEP-02` había dejado esto como documentación pendiente: «ninguna documentada como
estructural o desplazable». Sonaba a un hueco que había que rellenar decidiendo algo.

No lo es. **Ya hay una decisión operando**, y es «conservarlas todas».

> El ítem de la cartera deja de ser *decidir qué hacer con las aguas* y pasa a ser
> *declarar o cambiar una política que lleva tiempo ejecutándose*.

Es una decisión de modelado perfectamente legítima —también lo es la contraria, y el campo
está dividido— pero es una decisión, tiene consecuencias, y no está escrita en ningún sitio.
Un tercero que reciba el paquete no puede saber que se tomó.

## El antecedente que lo conecta

`REC-07` registró un incidente durante su ejecución: pasar el PDB crudo con sus **387
aguas** al preparador devolvió scores positivos de +23 a +33, cifras sin sentido físico. Se
corrigió la preparación **para ese experimento** y se repitió la tanda.

El material de producción de MolFlex sigue conservándolas.

## Una hipótesis que no afirmo

Una pose que exija **desplazar** una agua conservada no puede encontrarse: el agua ocupa el
sitio donde tendría que ir un átomo del ligando. Eso convierte a las aguas retenidas en un
candidato para parte del déficit de cobertura del estrato difícil.

**No lo afirmo, y hay evidencia en contra.** `MF-33` alcanzó 26 de 33 con **este mismo
receptor**, simplemente dockeando flexible en vez de rígido. Si las aguas fueran el bloqueo
principal, ese cambio no habría bastado.

Queda como hipótesis contrastable para los siete que siguen sin cubrirse, no como
explicación.

## Limitaciones

El emparejamiento entre original y preparado es **por coordenada**, con 0.5 Å de tolerancia,
y no por identidad de residuo — porque la preparación renumera, cosa que `REC-08` ya había
observado. Un átomo desplazado más de 0.5 Å contaría como perdido, así que el recuento de
pérdidas es una **cota superior**. Salió cero, lo que refuerza el negativo en vez de
debilitarlo.

Cobertura **116 de 203**: los 87 restantes son todos de `valtest` y carecen de `rec.pdbqt`.
Es la misma asimetría de material que `REC-08` registró, y vuelve a aparecer aquí.

## Correcciones

**2026-10-22**, a raíz de la Fase B de la auditoría científica (fase 1b del plan de arreglos,
`docs/102_FASE_1B_CORRECCIONES.md`). Ninguna cifra sellada cambia.

- SCI-B-023. El emparejamiento entre el depósito y el receptor preparado es por **proximidad de
  coordenadas**, sin exigir el mismo elemento ni pareo uno a uno. Un átomo distinto que quede
  cerca puede contar como conservado, así que las pérdidas no son una cota superior garantizada.
  El cero que se publicó describe correspondencias geométricas aproximadas.

## REC-12-R1: el depósito original revela especies que la fuente limpia no mostraba

**GO del inventario desde la nueva fuente.** Amplía la referencia de conservación; no modifica receptores ni atribuye a las ausencias fallos de docking.

Desde RCSB, el gate de validez marca HETATM que no son agua ni metal en 115 de 116 estructuras. Basta presencia en cualquier región para ese gate de fuente; no cuenta cofactores funcionales.

El contador excluye una lista previa de 51 especies aditivas y el propio ligando por solapamiento. Con radio de sitio 8,0 Å, conserva 15 casos con especie no aditiva próxima que el pareo geométrico no encuentra en `rec.pdbqt`. La lista nominal está en el artefacto; no se deduce de la puntuación de Vina.

Una especie no listada cuenta nominalmente como cofactor; su necesidad funcional requiere otra prueba. El depósito es unidad asimétrica, no ensamblaje biológico. Sigue vigente **SCI-B-023**: proximidad no es identidad química uno a uno. No comprobado por mí: reproducir el inventario desde depósitos y receptores originales. Fuente: `REC-12-R1`.
