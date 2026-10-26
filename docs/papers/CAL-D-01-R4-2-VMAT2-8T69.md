---
titulo: "GO: con el producto de 1.0.4, Vina ordena los 89 Ki de VMAT2 (8T69), 4-67 incluido"
entradilla: "Repetición de CAL-D-01-R4 con la regla original sin cambios. El producto completa ahora los 89 padres, también el biciclopentano 4-67 que R4 no terminó: ρ = 0,39 (IC 95 % 0,22–0,54) y ρ de peor caso = 0,32 (IC 95 % 0,14–0,47), sin fallos persistentes. No es ciego: los otros 88 scores ya se conocían, y se repiten exactos."
---

**GO.** Es la regla de R4, firmada el 2026-10-21 antes de cualquier score, aplicada al producto de 1.0.4. R4 sigue sellado
NO_GO, porque aquel producto no completaba 4-67; R4B sigue INCONCLUSIVE.

## Qué se midió

Lo mismo que R4, con la entrada sellada copiada byte a byte. El receptor es 8T69, cadena A, con la caja del catálogo y el
receptor preparado `8fc027ca…`. Vina 1.2.7, exhaustividad 8, 9 poses, 4 CPU y Q = −E del top-1. El panel son los 89 Ki
puntuales de la patente US11718618B2 (plaquetas humanas, [3H]DTBZ). El arnés de R4 se importa sin editarlo.

Lo único que cambió en el producto es la validación física: desde `48b22820` corre en un proceso hijo con un plazo de 300 s. En R4,
el `energy_ratio` de PoseBusters no terminaba con el biciclo[1.1.1]pentano de 4-67, y el pipeline se cortaba a los 1200 s.

Antes de medir, y sin ver el score de 4-67, se declaró cómo cuenta una validación que no termina en su plazo. Una evaluación
con score y la validación física «no evaluada» **cuenta como evaluada**. En R4, PoseBusters sólo decidía en la puerta de pose
del cristal; contarla como fallo habría endurecido la regla después de ver el caso. Esa validación se publica como
advertencia, con su sensibilidad, y no decide.

## Qué pasó

| Medida | R4 | R4-2 |
|---|---:|---:|
| Puerta de pose (semillas a RMSD ≤ 2 Å, válidas en PoseBusters) | 5 de 5 | 5 de 5 (0,67–0,71 Å) |
| Padres evaluados | 88 de 89 | **89 de 89** |
| Fallos persistentes | 1 (4-67) | **0** |
| ρ de Spearman (Q frente a pKi), IC 95 % | 0,39 (0,22–0,54), sin 4-67 | **0,39 (0,22–0,54)** |
| ρ de peor caso (F = 1015/703), IC 95 % | 0,32 (0,14–0,47), sin 4-67 | **0,32 (0,14–0,47)** |
| Concordancia de pares con cociente de Ki > F (P2) | — | 0,64 (0,58–0,70) |
| Decisión | NO_GO formal | **GO** |

- **4-67 completa en 335 s**, en el primer intento, con la validación física `not_evaluated`
  (`VALIDADOR_EXCEDIO_EL_PLAZO`). Es el único padre con esa advertencia. Sin él, ρ = 0,39 (0,22–0,54) y
  ρ_peor = 0,32 (0,14–0,47): no arrastra el resultado.
- **Los 88 padres comunes con R4 dan la misma energía top-1**, con una diferencia máxima de 0,000 kcal/mol. Con la misma
  semilla, el mismo receptor y las mismas CPU, Vina es determinista aquí, y el cambio de producto no movió ningún score.
- Validación física del top-1 en el panel: 46 `passed`, 37 `review`, 5 `failed` y 1 `not_evaluated`. Como en R4, no entra
  en la decisión, que sólo usa el score.
- Las sensibilidades de 4-31 y 4-118 (la misma molécula con dos Ki) dan ρ entre 0,37 y 0,39. Ninguna desviación, ningún
  reintento y ninguna deriva; 3,7 CPU-core-h.

## Qué significa y qué no

Con este receptor, esta caja y esta configuración, el score de Vina ordena esta serie de análogos de tetrabenazina mejor que
el azar, también con la asignación de lotes más desfavorable. Es una correlación moderada (ρ ≈ 0,4): ordena la serie, no
predice el Ki de una molécula.

**No es una confirmación ciega.** Los 88 scores de R4 eran públicos y se esperaba que se repitieran. Lo que R4-2 añade es que
el producto completa el panel entero y que, con 4-67 dentro, la regla original se cumple. Tampoco dice nada de otras series,
otros sitios ni otros receptores.

**8T69 queda como candidato a «Verificados», no promocionado.** La promoción a `receptores_verificados.json` es decisión del
propietario y va en un commit aparte, con `supera_el_protocolo`. Mientras tanto, 8T69 sigue en Demostración.

Sello: `scripts/artifacts_science/CAL-D-01-R4-2-VMAT2-8T69/`. Arnés: `scripts/cal_d01r4_2/`, que importa sin editar
`scripts/cal_d01r4/`. Registro previo: `entrada/REGISTRO_PREVIO_R4_2.md` (SHA-256 `aa84631f…`).
