# MF-33-EXT-MOD-R1 — lectura

**Decisión preregistrada: GO.** Las dos puertas pasan: las funciones del productor de MF-33-DOSIS
reproducen exactamente sus valores en los 48 de la cohorte, y los cuatro descriptores están
completos en 65 de los 68 externos (`diversidad` falta en 1ai7, 1e4h y 1nki). En los 68, los
cuatro sobreviven a Benjamini-Hochberg contra `beneficio_ensemble`:

| Predictor | n | ρ | p |
|---|---:|---:|---:|
| `torsdof` | 68 | 0.409 | 0.0005 |
| `rot_bonds` | 68 | 0.428 | 0.0003 |
| `diversidad` | 65 | 0.334 | 0.0065 |
| `n_heavy` | 68 | 0.398 | 0.0008 |
| `n_conformeros` (confundido, no cuenta) | 68 | 0.538 | 2e-6 |

ρ detectable al 80 % con n = 68: 0.334. Con la respuesta barajada (semilla 42) no sobrevive ninguno.
Según el PRE, los cuatro pasan a ser **candidatos** a una política adaptativa.

**Lo que esa decisión no dice** (diagnóstico posterior, declarado, que no cambia el GO): los cuatro
están muy correlacionados entre sí y con `n_conformeros` (ρ de 0.80 a 0.95), y `n_conformeros` es
el K del ensemble, que el preregistro ya declaraba confundido con la dosis. **Controlando por
`n_conformeros`, ninguno conserva asociación** (ρ parciales de −0.17 a −0.09, p ≥ 0.17;
`diagnostico_parcial.json`). Lo que los cuatro detectan es que los ligandos grandes y flexibles
reciben más confórmeros y por eso más beneficio del ensemble; no muestran que un descriptor
estático prediga el beneficio más allá de la dosis. Una política que use estos descriptores para
decidir K estaría usando una correlación con el propio K.

**No dice** nada sobre los bloques 1, 2 y 4 ni reabre el escenario de MF-33-EXT-MOD.
