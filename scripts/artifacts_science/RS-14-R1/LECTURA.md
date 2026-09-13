# RS-14-R1 — Corregir el defecto ensanchó la brecha: la cartera D se cierra

## Decisión: NO_GO

| Gate | Criterio | Resultado |
|---|---|---|
| G1 validez | los 348 ajustes LOCO completan | PASS — 1,348 ajustes |
| G2 **superioridad** | condicional > baseline, CI95 BCa pareado excluyendo 0 | **FAIL** |
| G3 nulo | condicional > percentil 95 del nulo por permutación | PASS con holgura |

## El resultado

| | `RS-14` | **`RS-14-R1`** |
|---|---:|---:|
| Precisión condicional del selector | 0.4312 | **0.4601** |
| Precisión condicional del baseline | 0.4783 | **0.5543** |
| Diferencia pareada (92 complejos) | −0.0471 | **−0.0942** |
| CI95 BCa | [−0.1522, +0.0617] | **[−0.2138, +0.0217]** |
| Top-1 global (ITT) | 0.3420 / 0.3793 | 0.3649 / 0.4397 |
| Nulo: p95 / observada | 0.163 / 0.431 | 0.1848 / **0.4601** (p empírico 0.0) |

Cambió **una sola cosa**: la etiqueta de RMSD pasó de ingenua a corregida por simetría
(`RC-F0-SYM`). Features, contrato de v0.6, hiperparámetros, LOCO, semillas 42/43/44,
nulo de 200 permutaciones y gates quedaron congelados **por construcción**: el runner
importa el de `RS-14` y sólo sustituye el cargador de etiquetas.

La cobertura del oráculo es **idéntica** (92 de 116, 79.31%, mismo conjunto de
complejos), así que el denominador es literalmente el mismo y la comparación entre los
dos experimentos aísla el efecto de la etiqueta.

## El hallazgo: el defecto favorecía al selector, no al baseline

75 poses de train pasaron de negativa a positiva (+21.0% de la clase positiva). Con
esas etiquetas:

- el **selector** sube 0.4312 → 0.4601 (+2.9 pp);
- el **baseline** sube 0.4783 → 0.5543 (**+7.6 pp**, 7 complejos: `188l`, `1a99`,
  `1b8y`, `1bcd`, `1e4h`, `1ikt`, `1kav`).

**La brecha se duplica**, de −0.047 a −0.094. El defecto de simetría estaba ocultando
cuánto mejor es ya `vina_score`. Corregirlo no rescató al selector: lo dejó peor
situado.

## Las tres predicciones preregistradas se cumplieron

Declaradas por escrito, con hash registrado, **antes** de ejecutar:

| Predicción | Declarada | Observada |
|---|---|---|
| Condicional del selector | [0.45, 0.58] | **0.4601** ✓ |
| Diferencia pareada | [−0.15, +0.05] | **−0.0942** ✓ |
| G3 pasa con holgura | sí | 0.4601 vs p95 0.1848 ✓ |
| Decisión | **NO_GO** | **NO_GO** ✓ |

El selector **sigue aprendiendo señal real**: casi 2.5× el percentil 95 del nulo, con
p empírico 0.0. En régimen `p > n` no memoriza ruido. Simplemente, lo que aprende no
añade nada sobre el score de Vina.

## Consecuencia: la cartera D queda cerrada

El prerregistro declaró la regla de cierre **antes** de ver el resultado: un `NO_GO`
aquí cierra la línea de forma definitiva. Por la §19.1, el corrigendum no cambió la
decisión, así que **no reinicia el contador de futilidad**.

- `RS-11`, `RS-12` y `RS-13` quedan bloqueados de forma permanente bajo este diseño.
- Cualquier reapertura futura debe declarar un denominador en **número de complejos**
  —`RS-14` lo cuantificó en ~4×—, no más features, más semillas ni etiquetas más
  limpias. Las tres vías se han probado y ninguna movió la aguja.

**El límite de potencia sigue intacto**: con 92 complejos cubiertos el diseño no
resuelve diferencias menores a ~10 puntos porcentuales. El desplazamiento del baseline
(+7.6 pp) es del mismo orden que esa resolución, lo que refuerza que el criterio sea
la prueba pareada y no los puntos estimados.

## Limitación declarada

1,143 poses de 18,812 (6.1%) —`flexible_redock` y `ruta_a`— conservan su RMSD ingenuo
porque no son trazables al material. Como corregir simetría sólo puede bajar el RMSD,
el residuo sesga hacia **menos** positivas: la corrección aplicada es una cota inferior
y el sesgo va **en contra** de encontrar un GO. El runner verifica pose a pose que
`rmsd_sym <= rmsd` y aborta si no.

Val y test intactos: un NO_GO en train no consume el confirmatorio.

## Archivos

- `PREREGISTRO.md` (en `RS-14-R1-PRE`, escrito y con hash registrado antes de ejecutar).
- `metrics.json` — descomposición de la §9, por semilla, diferencia pareada con CI95 BCa, nulo, gates y el bloque `etiquetas` con procedencia y conteo de correcciones.
- `per_complex.jsonl` (116) — cubierto, acierto del baseline y del selector por semilla, poses y oráculo.
- `nulo.json` — las 200 réplicas.
- `scripts/run_rs14r1_selector_sym.py`.
