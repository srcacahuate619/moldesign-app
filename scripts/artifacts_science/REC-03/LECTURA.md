# REC-03 — La predicción de pocket repara parte del catálogo roto, pero rompe parte del sano

## Decisión: NO_GO

Dos gates fallan, uno técnico y uno sustantivo:

| Gate | Criterio | Resultado |
|---|---|---|
| G1 validez | ≥98% de corridas válidas | **FAIL — 87.1%** (324/372) |
| G2 sólo lectura | catálogo conserva SHA-256 | PASS |
| G3 **reparación** | `G_MP_SCORE` repara ≥5 de los 25 accionables | **PASS — 6** |
| G4 **no regresión** | `G_MP_SCORE` conserva ≥70% de lo que repara `G_CAT` en el control | **FAIL — 4 frente a 5 exigidos** |
| G5 determinismo | misma semilla → mismo score y mismo RMSD | PASS — 4/4 idénticos |

El prerregistro es explícito: si falla la validez técnica, **el experimento se repite, no se interpreta**. Así que lo que sigue es **descriptivo y no constituye claim**; el claim exige REC-03-R1.

Dicho eso, la validez no falló de forma difusa. Falló **entera y exclusivamente en 4 targets**, que perdieron sus 12 corridas cada uno —las 4 cajas × 3 semillas— mientras los otros 27 targets dieron **324 de 324 corridas válidas (100%)**. Como los 4 caen igual en todos los brazos, **no distorsionan la comparación entre brazos**: no aportan a ningún lado.

Las cuatro causas, diagnosticadas una a una:

| Target | Causa | Naturaleza |
|---|---|---|
| `3MG0` | el ligando contiene **boro**; Vina no tiene tipo de átomo para B | límite del motor, no del grid |
| `6MWA` | 37 torsiones (fosfatidilcolina) — timeout a 1800 s | coste |
| `7E2Y` | 43 torsiones — timeout | coste |
| `4CA8` | 20 torsiones / 56 átomos — timeout | coste |

## Lo que muestran los números

### El catálogo falla en la cohorte accionable, como estaba declarado

`G_CAT` repara **0 de 21** accionables, con RMSD mediano de 19.97 Å. Esto **no es un hallazgo**: el prerregistro ya declaró que en los 11 `S1_CRITICO` la contención del ligando es 0.0 y el fracaso está determinado por construcción.

### La reparación funciona, y funciona cerca de su techo

`G_MP_SCORE` —el pocket elegido por mejor score de Vina, nunca por posición del ligando— repara **6 de los 19 accionables evaluables**. El techo geométrico dentro de esos 19 era **9**: la reparación alcanza **6 de los 9 casos que la geometría permitía**, el 67%.

Los seis: `1DIY`, `1Q4G`, `2OYE`, `3N8Y`, `3N8Z` (todos `S2_GRAVE`) y `7XW6` (`S1_CRITICO`). El patrón es nítido: **se repara donde la caja del catálogo contenía parcialmente el ligando, no donde estaba completamente fuera de sitio**. `1Q4G` es el caso interesante: se reparó sin estar en el techo, es decir, contención parcial bastó.

### Y sin embargo rompe lo que funcionaba

En los 8 targets de control evaluables:

| Target | `G_CAT` | `G_MP_SCORE` |
|---|---|---|
| `2AM9` | 3/3 · 0.253 Å | 3/3 · 0.243 Å |
| `6PU8` | 3/3 · 0.537 Å | 3/3 · 0.526 Å |
| `3RUT` | 3/3 · 0.463 Å | 2/3 · 0.464 Å |
| `1F0R` | 3/3 · 1.223 Å | 3/3 · 1.454 Å |
| **`2H02`** | 3/3 · 1.338 Å | **0/3 · 61.07 Å** |
| **`7JVU`** | 2/3 · 1.976 Å | **1/3 · 13.09 Å** |
| `1X7R` | 0/3 · 7.217 Å | 0/3 · 7.219 Å |
| `6KE5` | 0/3 · 10.878 Å | 0/3 · 15.04 Å |

6 → 4. Y las dos pérdidas **no son marginales**: en `2H02` el pocket predicho manda el ligando a 61 Å del sitio real. Cuando la predicción se equivoca, no se equivoca por poco.

### Un número de calibración que no buscábamos

`1X7R` y `6KE5` fallan el re-docking **con la caja exacta del catálogo**, centrada a 0.00 Å del ligando nativo (7.2 y 10.9 Å de RMSD). Con grid perfecto, el re-docking acierta en **6 de 8** targets sanos: **75%**. Ese techo es del motor de docking, no del catálogo, y conviene tenerlo presente antes de atribuir a los grids cualquier fallo de pose.

## Qué se concluye y qué no

**No se concluye** que la predicción de pocket sirva para reparar el catálogo: falla el gate de no regresión, y además el gate de validez bloquea el claim.

**Se registra** que la reparación automática global **no es viable con este motor**: sustituir el grid del catálogo por el pocket predicho gana 6 targets rotos y pierde 2 sanos, y las pérdidas son catastróficas cuando ocurren. Los 25 targets accionables de REC-01-R1 siguen siendo **deuda de curación por target**, no un problema resoluble con una política global.

Esto es coherente con REC-07, que ya había mostrado que una excepción geométrica del catálogo no implica un fallo de docking. El programa acumula dos evidencias en la misma dirección: **la geometría del grid no es un buen predictor de la calidad del docking**, ni para condenar un grid ni para reemplazarlo.

## Camino a un claim: REC-03-R1

Un corrigendum tendría que congelar antes de ejecutar:

1. **Criterio de elegibilidad por coste**, declarado por adelantado: excluir ligandos por encima de un número de torsiones (los tres timeouts tienen 20, 37 y 43) y ligandos con elementos sin tipo en Vina (boro), en vez de descubrirlos al fallar.
2. **Presupuesto por corrida** acorde a la caja: 1800 s no alcanza para ~31 Å con `exhaustiveness=32` en ligandos muy flexibles.
3. **Control más grande**: con 8 targets evaluables, la diferencia 6 vs 4 es demasiado frágil para sostener una política.

## Archivos

- `PREREGISTRO.md` (en `REC-03-PRE`, sellado antes de ejecutar) — cohorte, brazos, métrica, gates y techo geométrico declarado.
- `metrics.json` — gates, tasas por brazo y estrato, determinismo, hashes de entrada y de las rutas protegidas.
- `per_complex.jsonl` (31) — por target: éxitos, RMSD mediano y mínimo, y score por brazo, más las selecciones de `G_MP_SCORE` semilla a semilla.
- `corridas.jsonl` (372) — una línea por corrida de Vina.
- `failures.jsonl` — 6 fallos de preparación y las corridas inválidas.
- `scripts/run_rec03_grid_repair.py`, `scripts/rec03_preflight.py`.
