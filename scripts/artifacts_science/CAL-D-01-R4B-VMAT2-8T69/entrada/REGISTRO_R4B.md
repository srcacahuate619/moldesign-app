# CAL-D-01, R4B — reanálisis enmendado sin 4-67

**Fecha:** 2026-10-22. **Lo pide:** el propietario («registra el intento sin 4-67»). **Lo escribe:** Claude.

## Qué es, y qué no es

R4 (`CAL-D-01-R4-VMAT2-8T69`, sellado, `764846d5`) terminó **NO_GO formal** porque su registro previo exigía cero
fallos persistentes y el compuesto 4-67 (biciclo[1.1.1]pentano) no completó el pipeline del producto (1200 s, dos
intentos). Sus 88 scores, la puerta de pose y todos los números ya existían cuando se escribió esto.

**R4B no acopla nada.** Reanaliza los 88 scores de R4 con **una sola enmienda**, y esa enmienda se redacta
**después de ver los scores** (de hecho, el análisis de R4 ya se calculó sobre esos 88). Por eso:

- no es confirmatorio y no puede promocionar a Verificados;
- su decisión en el registro es **INCONCLUSIVE por construcción**, aunque el criterio enmendado se cumpla;
- no cuenta como réplica ni como holdout: es el quinto paso de la misma decisión (1IAS → 8WRE → 8T69 → regla nueva R4 →
  R4B), con M = 1 resultado computacional.

## La enmienda (la única)

> Un fallo persistente **del producto** en un compuesto concreto, declarado con su identificador y su causa, no impide
> el criterio si quedan **≥ 85** padres evaluados. El compuesto se publica como excluido y no se sustituye.

Todo lo demás es el registro previo R4 (`0a1a4aed…`) sin cambios: receptor, receta, Vina 1.2.7, Q = −E(top-1),
puerta de pose (ya superada: 5 de 5), ρ y ρ_peor con F = 1015/703, IC95 % percentil por bootstrap pareado por padre
(10 000 réplicas, semilla 20261021), P2 y sensibilidades.

## Qué se afirma, si se cumple el criterio

Con 8T69, esta receta y Vina 1.2.7, el orden de Q de 88 de los 89 padres de la tabla publicada de
US11718618B2 (Example 11) correlaciona positivamente con los Ki publicados, incluso en la peor asignación binaria
de lote con F = 1015/703. **No** se afirma comparabilidad entre lotes, afinidad absoluta, otra serie ni otra diana,
ni que 4-67 se comporte como el resto (se desconoce su score).

## Qué cambia en el producto

Nada. 8T69 sigue en Demostración. Para promocionarlo haría falta un protocolo confirmatorio nuevo, escrito antes
de acoplar, y que el catálogo, el dossier y Preparación puedan llevar ρ_peor y la condición de lote.
