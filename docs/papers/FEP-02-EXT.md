---
titulo: "Esta vez medir la consecuencia casi no ayudó"
entradilla: "El mismo movimiento que redujo los tautómeros a un tercio apenas divide los huecos de cadena por dos: 41 de los 86 están justo en el bolsillo. Esperaba lo contrario, y esperarlo habría sido extrapolar sin medir."
---

`FEP-02` midió que **86 de 203 receptores (42%) tienen huecos de numeración** — tramos de
cadena ausentes en la estructura. Ese número quedó como una de las dos razones por las que
sólo 83 de 203 estarían documentados para energía libre.

Pero contaba **existencia**, no **relevancia**. Un tramo ausente a cincuenta residuos del
bolsillo no afecta a un cálculo de energía libre de unión; uno que corta el propio sitio,
sí. El propio `FEP-02` lo declaró: «los 86 son candidatos, no defectos confirmados».

Este experimento aplica a los huecos el mismo tratamiento que `FEP-01-EXT` aplicó a los
tautómeros.

## Qué salió

Cada hueco se clasificó por la distancia mínima de sus dos residuos flanqueantes a
cualquier átomo pesado del ligando, con un radio de 8 Å. `FEP-02` definió «sitio» a 6 Å al contar
cadenas, metales y aguas, así que estos conteos no son comparables con los suyos (SCI-B-005).

| Clasificación | Complejos |
|---|---:|
| **EN EL SITIO** (≤ 8 Å) | **41** |
| Periférico (8–15 Å) | 29 |
| Lejano (> 15 Å) | 16 |

86 de 86 analizables, cero errores, 1.9 segundos.

## Lo informativo es que no se repitió el resultado anterior

| | Contado por el original | Accionable de verdad |
|---|---:|---:|
| `FEP-01-EXT` — tautómeros | 164 | **54** (un tercio) |
| `FEP-02-EXT` — huecos | 86 | **41** (casi la mitad) |

Yo esperaba la misma reducción drástica. No se produjo, y **asumirla habría sido extrapolar
de un experimento a otro sin medir** — exactamente el error que `MF-26` cometió al declarar
una especificación desde una curva de `train`.

Casi la mitad de los huecos está justo donde importa. Este problema es más real de lo que
el de los tautómeros resultó ser.

## La asimetría entre huecos y complejos

Hay **337 huecos** en total y sólo **55 están en el sitio**: un **16% por hueco**, frente a
un **48% por complejo**.

La razón es aritmética y merece anotarse porque cambia qué se reporta: basta **un** hueco
cerca del bolsillo para que el complejo sea accionable. Contar huecos subestima el problema;
la unidad correcta es el complejo.

## Lo que gana la cartera H

Deja de tener una lista de 86 y pasa a tener tres grupos con acción distinta:

- **41 hay que reparar** antes de poder declarar el receptor;
- **29 son frontera** y exigen mirar caso por caso;
- **16 basta con declararlos**.

## El control que existía y ya no se puede ejecutar

`FEP-02` había verificado algo notable: los 9 complejos que fallaron la parametrización con
error de plantilla en `MF-10` tienen huecos de cadena, **9 de 9**, contra una tasa base del
42.4% — probabilidad de coincidencia ≈ 0.0004.

Comprobar si **esos** huecos están en el sitio habría validado el criterio de este
experimento contra un fallo real, independiente y ya observado. Era el mejor control
disponible y era gratis.

No se pudo: **el `failures.jsonl` de `MF-10` está vacío** y los identificadores no son
recuperables desde el artefacto.

Es una instancia concreta de lo que `FND-08` encontró sobre dato crudo ausente, y el coste
se paga aquí. No es una molestia abstracta de contabilidad: es un control que existía, que
no costaba nada, y que ya no se puede hacer.

## Lo que este experimento tiene prohibido concluir

Declarado antes de correr: un hueco **lejano no garantiza** que la estructura sea utilizable
— puede romper el plegamiento o la dinámica global. Lo medido es qué fracción tiene el
defecto **en la región que decide la unión**, que es la única que obliga a reparar antes de
declarar el receptor.

Un hueco lejano se declara. Uno en el sitio se arregla.

Y queda expresamente prohibido concluir que los 16 lejanos están listos para energía libre:
`FEP-02` exige además documentar cadenas, disulfuros, metales, cofactores y aguas, y nada de
eso se toca aquí.

## Correcciones

**2026-10-20**, a raíz de la Fase B de la auditoría científica del producto. Ninguna cifra sellada cambia y no se repitió ningún cálculo; esto corrige lo que el texto afirmaba a partir de ellas. Detalle y procedencia en `docs/101_CORRIGENDA_SELLOS_AUDITORIA_20261020.md`.

- SCI-B-005. Este análisis usa un radio de **8 Å** y decía que era el mismo con el que FEP-02 definió el sitio, que es de **6 Å**. Su 41 es un conteo a 8 Å, no una medida comparable con FEP-02.

**2026-10-22**, a raíz de la Fase B de la auditoría científica (fase 1b del plan de arreglos,
`docs/102_FASE_1B_CORRECCIONES.md`). Ninguna cifra sellada cambia.

- SCI-B-042. La extensión a PDBBind (`FEP-02-EXT-PDBBIND`, sin paper propio) cuenta como
  `SIN_HUECOS` los 1438 receptores que `FEP-02-PDBBIND` no pudo leer (`SIN_PDB`), e informa cero
  errores. Con el estado del padre: 3887 evaluables, **2210 sin huecos (56.9 %)**, no 3648 de
  5325 (68.5 %). Las cifras condicionadas a tener huecos (468 en el sitio de 1677) no cambian.
  Productor: `scripts/analisis_fep02ext_pdbbind_cobertura.py`.

**2026-10-22.** El método repetía que el radio de 8 Å era el de FEP-02, lo que SCI-B-005 ya había corregido (hallazgo L2-SOL-006 de la revisión de papers de Sol).

## FEP-02-EXT-PDBBIND: la distribución por hueco y por complejo responde preguntas distintas

**GO de medición descriptiva.** Completa la clasificación de la extensión más allá del grupo del sitio ya publicado en Correcciones.

Entre los complejos analizables con saltos de numeración, 592 se clasifican periféricos y 617 lejanos. El límite periférico es 15,0 Å; se conserva el radio de sitio propio de la extensión, distinto del cribado base.

En la unidad hueco hay 633 próximos al sitio de 4610 totales. Ese denominador no se sustituye por el de complejos: varios huecos pueden pertenecer a la misma estructura. Rigen **SCI-B-005, SCI-B-039 y SCI-B-042** para radio, identidad y cobertura de fuente. No comprobado por mí: recontar distancias desde estructuras originales. Fuente: `FEP-02-EXT-PDBBIND`.
