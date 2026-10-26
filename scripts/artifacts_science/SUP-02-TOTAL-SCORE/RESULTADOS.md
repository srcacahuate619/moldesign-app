# SUP-02-TOTAL-SCORE — acta de cierre

**Decisión: NO_GO.** El `total_score` de 0 a 100 no ordena las afinidades experimentales mejor que el score de Vina sin transformar.
En 8T69 ordena igual, porque es casi una transformación de Vina. En 8HFI ordena peor, aunque la diferencia no es significativa. No
hay daño demostrado: ningún IC excluye el cero por debajo. Criterio en `entrada/REGISTRO_PREVIO.md` (`bbef7ffe`), commiteado antes de
calcular ninguna correlación.

| Serie | n | ρ total_score | ρ Vina | Δ (IC 95 %) | ρ total_score ~ Vina | total_score: mediana [rango] |
|---|---:|---:|---:|---|---:|---|
| 8T69 (VMAT2) | 89 | 0,397 | 0,392 | +0,005 (−0,058; +0,061) | 0,97 | 40,0 [14,3–67,2] |
| 8HFI (NET) | 57 | 0,029 | 0,129 | −0,101 (−0,334; +0,134) | 0,63 | 54,5 [33,8–72,7] |

- **Control interno:** las ρ de Vina reproducen las de los sellos: 0,39 en `CAL-D-01-R4-2-VMAT2-8T69` y 0,13 en `CAL-8HFI-01`.
- **Ningún compuesto en el techo ni en el suelo:** ninguno ≥ 99,5 ni ≤ 0,5, así que el resultado no viene de una saturación de la
  escala.
- **En 8HFI el `total_score` se aparta de Vina** (ρ 0,63 entre los dos), y no hacia el orden experimental. La causa no se midió.
  - No es el tamaño: 8HFI va de 18 a 26 átomos pesados (DE 1,9) y 8T69, de 24 a 35 (DE 2,4).
  - Su `total_score` se calculó con el código del 2026-10-09, que pudo tener otros términos.
- Bootstrap pareado por compuesto: 10 000 remuestreos, semilla 42, ninguno no finito. Ningún crudo faltó (`failures.jsonl` vacío).

## Qué significa

- El producto presenta como **índice de calidad** un número que no aporta información sobre la afinidad que no esté ya en el score
  de Vina, y que en una de las dos series disponibles la empeora. Lo muestra en la tabla SAR, en Comunidad y como score certificado
  de Moldex.
- El PDF ya lo rotula «índice compuesto heredado (escala histórica 0–100)». La propuesta al propietario es hacer lo mismo en todas
  partes, o dejar de mostrarlo como calidad.

## Límites

- Son dos series congenéricas, con poco rango de tamaño. No prueba que el `total_score` nunca ayude entre quimiotipos distintos;
  prueba que no está demostrado donde hay datos.
- El `total_score` es el que el producto calculó en cada corrida (8HFI, el 2026-10-09), no un recálculo con el código de hoy.
- No mide el factor de especificidad por hotspots, que sólo actúa con hotspots `curated_experimental`.
