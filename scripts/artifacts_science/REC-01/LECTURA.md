# REC-01 — Lectura de resultados

> `README.md` lo regenera `experiment_manifest.py` desde el manifest y no debe
> editarse a mano. Este archivo contiene la lectura científica y **sí** está
> sellado como asset.

**Decisión:** GO — los cinco gates del instrumento pasan.
**Fecha:** 2026-08-17. **Cómputo:** local, sin docking, sin red.
**Preregistro:** [`PREREGISTRO.md`](PREREGISTRO.md), con los gates fijados antes de ejecutar.

> El GO significa **«la auditoría es válida y reproducible»**, no que el catálogo
> esté sano. La fracción de excepciones es el resultado, no el gate.

---

## 1. Gates

| Gate | Criterio | Resultado |
|---|---|---|
| G1 | 387 targets con veredicto explícito, 0 omisiones | **PASS** — 387/387, `failures.jsonl` vacío |
| G2 | Estrato determinista por target | **PASS** — 0 sin estrato |
| G3 | Toda excepción cita código `E1…E7` y el valor que la dispara | **PASS** |
| G4 | Corridas repetidas → `per_complex.jsonl` byte-idéntico | **PASS** — 3 corridas, incluida una tras borrar y reconstruir el directorio; SHA-256 `3f4da5ab…eee23` |
| G5 | Catálogo y CSV conservan su SHA-256 | **PASS** |

## 2. Resultado

### Estratos (derivados del PDB, §4.1 del preregistro)

| Estrato | n | % |
|---|---:|---:|
| HOLO (ligando nativo ≥6 átomos pesados) | 283 | 73.1% |
| APO (sin ligando no-artefacto) | 99 | 25.6% |
| HOLO_COFACTOR_ONLY | 5 | 1.3% |

### Alineamiento del grid en HOLO (ground truth fuerte, n=283)

Mediana `d_centro` = **0.004 Å**: la mayoría de los grids está calibrada
exactamente contra el ligando nativo. La cola, en cambio, es larga.

| Banda | n | % |
|---|---:|---:|
| ≤ 4 Å | 240 | 84.8% |
| ≤ 6 Å | 249 | 88.0% |
| ≤ 10 Å | 254 | 89.8% |
| ≤ 15 Å | 258 | 91.2% |
| **> 15 Å** | **25** | **8.8%** |

p90 = 11.307 Å · máximo = 77.483 Å.

### Excepciones

**57 de 387 targets (14.7%)** disparan al menos un código.

| Código | n |
|---|---:|
| `E1_CENTRO_LEJOS` (>6 Å, sólo HOLO) | 34 |
| `E2_LIGANDO_RECORTADO` (contención <1.0) | 23 |
| `E3_HOTSPOTS_FUERA` (<0.80) | 17 |
| `E4_HOTSPOTS_INVALIDOS` (<0.80) | 8 |
| `E5_HOTSPOTS_AUSENTES` (<5 declarados) | 7 |
| `E6_SIN_PDB` | 0 |
| `E7_PDB_NO_PARSEABLE` | 0 |

### Los doce peores casos HOLO

| PDB | `d_centro` | Familia | Contención ligando |
|---|---:|---|---:|
| 8UBR | 77.48 Å | ion_channel | 0.00 |
| 4JSX | 76.70 Å | kinase | 0.00 |
| 5J89 | 51.00 Å | protein_interaction | 0.00 |
| 3MG0 | 49.74 Å | proteasome | 0.00 |
| 3HYE | 48.34 Å | proteasome | 0.00 |
| 3GPT | 48.18 Å | proteasome | 0.00 |
| 6MWA | 43.05 Å | ion_channel | 0.00 |
| 1IGZ | 42.48 Å | oxidoreductase | 0.00 |
| 7XW6 | 32.08 Å | gpcr | 0.00 |
| 5TNH | 27.17 Å | ion_channel | 0.00 |
| 2OYU | 20.30 Å | oxidoreductase | 0.17 |
| 2OYE | 20.27 Å | oxidoreductase | 0.33 |

En **23 targets la caja no contiene ni un solo átomo del ligando nativo**
(`contencion_ligando = 0.00`). Ahí ningún generador de poses puede producir una
pose correcta: el sitio de unión está fuera de la caja. Esos casos no son un
problema de muestreo conformacional ni de selector.

## 3. Frente a la hipótesis preregistrada

La fila REC-01 del doc. 49 §7 hablaba de **«los 12 grids problemáticos»**. La
auditoría completa encuentra **57 targets con excepción (14.7%)**, de los cuales
**25 tienen el grid a más de 15 Å** del sitio real: ~4.75× el orden de magnitud
que asumía el plan.

Esto respalda la reasignación de prioridad del doc. 49 §19.1 — el margen está en
generación y receptor, no en el selector — y da a REC-03 una cohorte de prueba
natural.

## 4. Hallazgo negativo sobre el propio instrumento

**El caso testigo `5TUN` (doc. 35) NO fue capturado por el criterio preregistrado.**

```text
estrato               APO          -> E1 no aplica (ground truth débil, §4.4)
contencion_hotspots   0.800        -> umbral E3 es "< 0.80" -> no dispara (frontera exacta)
hotspots_validos      1.000        -> E4 no dispara
n_hotspots            15           -> E5 no dispara
margen_min_hotspots   -5.147 Å     <- hay un hotspot 5.1 Å FUERA de la caja
excepciones           []           <- pasa limpio
```

El doc. 35 documentó exactamente esto por inspección visual (`TYR89` y `GLU84`
fuera de la caja). El criterio de contención por **fracción** no lo ve porque 12
de 15 hotspots sí están dentro; lo que falta es un criterio de **margen**.

Siguiendo la regla del preregistro —«no se ajustará tras ver la distribución»—
**el umbral no se toca y REC-01 se sella con este falso negativo declarado.**
La corrección va en un experimento sucesor, no en una enmienda retroactiva.

### Cuantificación para `REC-01-R1`

Un código adicional `E8_HOTSPOT_FUERA_DE_CAJA`, definido como
`margen_min_hotspots < 0`, capturaría:

| | n |
|---|---:|
| Targets con algún hotspot fuera de la caja | 65 / 380 |
| — ya marcados por `E1…E5` | 13 |
| — **nuevos, hoy invisibles** | **52** |
| Excepciones totales: hoy → con `E8` | 57 (14.7%) → **109 (28.2%)** |

`5TUN` es el segundo peor de esos 52 (−5.15 Å), detrás de `1IRU` (−5.49 Å).

## 5. Lo que este experimento NO decide

- No corrige ningún grid: `5TUN` pasa a REC-07 y la política de caja a REC-03.
- No afirma que un target excepcional produzca peor docking — eso exige el
  experimento pareado de REC-03, con docking, no autorizado aquí.
- No mide cobertura de oráculo ni Top-1.
- Las métricas del estrato APO usan ground truth **débil** (centroide de CA de
  hotspots) y son descriptivas, sin inferencia fuerte.

## 6. Nota operativa — trampa de `experiment_manifest.py`

Durante el montaje se selló `README.md` como asset. `seal` **regenera**
`README.md` desde el manifest justo después de registrar los hashes, de modo que
`validate` falla de inmediato con un hash mismatch autoinfligido, y `maintain`
—la vía prevista— exige un `--content-commit` que aún no existe.

Como nada estaba commiteado y el experimento es determinista, se borró el
directorio y se rehízo el ciclo completo sin `README.md` entre los assets. El
`per_complex.jsonl` reconstruido resultó **byte-idéntico** (`3f4da5ab…eee23`),
lo que de paso fortalece G4.

**Regla derivada:** `README.md` nunca debe incluirse en `--assets`; la lectura
científica va en un archivo propio (`LECTURA.md`) que sí es sellable.

## 7. Siguiente paso propuesto

1. **`REC-01-R1`** — enmienda preregistrada que añade `E8_HOTSPOT_FUERA_DE_CAJA`
   y reaudita, para cerrar el falso negativo antes de tocar el catálogo.
2. **`REC-07`** — resolver `5TUN` como caso testigo, con la evidencia ya
   cuantificada (`margen_min = −5.147 Å`).
3. **`REC-03`** — política de centro/tamaño adaptativo, usando como cohorte los
   25 casos `>15 Å` y los 23 de contención cero.
