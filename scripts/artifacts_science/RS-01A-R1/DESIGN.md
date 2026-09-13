# RS-01A-R1 — Corrigendum estadístico del p de McNemar de RS-01A (DESIGN)

**Fecha:** 2026-08-16
**Rama:** `experimentos/ruta-c-molflex`
**Estado:** EJECUTADO (sin seal, sin finish — por instrucción del maintainer)
**Padre:** `scripts/artifacts_science/RS-01A/` (SELLADO, commit `2943a38`, sin modificar)
**Script:** `scripts/artifacts_science/RS-01A-R1/run_rs01a_r1_corrigendum.py`

## 1. Naturaleza del corrigendum

Corrigendum estadístico formal. Bug confirmado por el maintainer: la versión
ejecutada de `mcnemar_hits` multiplicaba por 2 el pvalue de
`scipy.stats.binomtest(...)`, que YA es bilateral. El p reportado en el
artefacto sellado de RS-01A estaba, por tanto, duplicado.

## 2. Qué cambió

Solo el p de McNemar, reexpresado sin tocar el sello histórico:

| Bloque (RS-01A) | b | c | p antiguo (sellado) | p corregido |
|---|---|---|---|---|
| `a1.pareado.mcnemar` | 4 | 0 | 0.25 | **0.125** |
| `a2.pareado.mcnemar` | 3 | 1 | 1.0 | **0.625** |

Fórmula corregida: `p = binomtest(min(b, c), b + c, 0.5).pvalue` (bilateral
nativo de SciPy); 0 pares discordantes → p = 1.0. Valores reproducidos por
`scripts/test_mcnemar_fix.py` ((4,0)→0.125, (11,7)→0.480682, (7,11)→0.480682,
(0,0)→1.0 → OK) y por el runner de este experimento (verificación dura contra
los valores esperados).

## 3. Qué NO cambia

- **Ningún gate ni decisión de RS-01A cambia.** A0 sigue reproduciendo el
  histórico exacto; A1 sigue observando −4 hits Top-1 con 0 recuperaciones y
  mediana pareada 0.000 Å; el contrafactual de los 31 empates sigue siendo
  sensible al desempate de fuente. El GO procedimental del sello histórico
  permanece intacto.
- **El sello histórico de RS-01A NO se modifica** (ningún archivo del padre
  se toca; `validate RS-01A` sigue OK — no se usa `maintain`). Este
  corrigendum vive en `RS-01A-R1`.
- El p corregido de A1 (0.125) sigue siendo NO significativo: la conclusión
  estadística del padre no cambia de sentido.

## 4. Procedimiento ejecutado

1. Verificación de integridad: `RS-01A/metrics.json` sha256
   `c6f4a2ef98d9646b…` (valor sellado) antes de leerlo.
2. Extracción de los bloques `a1.pareado.mcnemar` y `a2.pareado.mcnemar` del
   padre; validación de consistencia b+c = n_discordantes y de los p antiguos
   esperados (0.25 / 1.0).
3. Recálculo con la fórmula corregida → 0.125 / 0.625 (reproducción dura
   verificada contra los valores esperados).
4. Escritura de `metrics.json`, `failures.jsonl` (vacío) y este documento.
   Auditoría de `builtins.open` con whitelist (solo el metrics del padre y las
   salidas de RS-01A-R1): 0 acceso a val/test/CONFIRM.

## 5. Determinismo

Salidas sin timestamps ni aleatoriedad; dos corridas producen bytes
idénticos. `validate RS-01A-R1` OK y `validate RS-01A` OK (sello histórico
intacto).

## 6. Salidas

| Archivo | Contenido |
|---|---|
| `metrics.json` | correcciones a1/a2 (p antiguo vs corregido), bug/fix, referencia al padre (commit 2943a38, sha del metrics sellado), qué no cambia, auditoría de cuarentena |
| `failures.jsonl` | vacío |
| `run_rs01a_r1_corrigendum.py` | reproduce el cálculo (lee SOLO el metrics sellado del padre, verificado por sha) |
| `DESIGN.md` | este documento |

## 7. Estado

Ejecutado y validado; **sin seal y sin finish** (instrucción explícita del
maintainer). Sin commits, sin pip, sin red, sin modificación de ningún
artefacto sellado.
