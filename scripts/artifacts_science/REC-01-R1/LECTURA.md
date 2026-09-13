# REC-01-R1 — Lectura de resultados

> `README.md` lo regenera `experiment_manifest.py` y no debe editarse a mano.
> Esta es la lectura científica, y **sí** está sellada como asset.

**Decisión:** GO — los seis gates pasan.
**Tipo:** corrigendum de [`REC-01`](../REC-01/) (sellado GO el 2026-08-17).
**Fecha:** 2026-08-17. **Cómputo:** local, sin docking, sin red, sin re-derivar geometría.
**Preregistro:** [`PREREGISTRO.md`](PREREGISTRO.md).

> **No es una prueba ciega.** El desenlace de `E8` ya estaba declarado en
> `REC-01/LECTURA.md` §4 antes de ejecutar R1. Ver §1 del preregistro.

---

## 1. Corrigendum numérico de la narrativa de REC-01

**Este es el resultado más importante de R1 y no estaba previsto.**

El preregistro (§6) declaró, como expectativa derivada de `REC-01/LECTURA.md`,
que `S1_CRITICO` sería **23**. El observado es **11**. La comprobación
`expectativa_vs_observado` marcó `coincide: false` y obligó a auditar la
diferencia.

**Causa: un error de lectura en la narrativa de REC-01.** El número 23 es el
conteo del código `E2_LIGANDO_RECORTADO`, cuya condición es
`contencion_ligando < 1.0` — es decir, contención **incompleta**, no nula:

| | n |
|---|---:|
| HOLO con contención computable | 283 |
| `contencion_ligando == 0.00` (ni un átomo dentro) | **11** |
| `0 < contencion_ligando < 1.0` (recorte parcial) | **12** |
| **`E2_LIGANDO_RECORTADO` (<1.0) = suma** | **23** |

La frase de `REC-01/LECTURA.md` §2 —«en **23** targets la caja no contiene ni un
solo átomo del ligando nativo»— **es incorrecta**. La cifra correcta es **11**.
Los otros 12 tienen contención entre 0.16 y 0.91: el ligando está parcialmente
dentro.

**Los 12 mal atribuidos:** `5WBE` (0.16), `2OYU` (0.17), `3KK6` (0.23),
`2OYE` (0.33), `3N8W` (0.33), `3N8X` (0.33), `3N8Z` (0.33), `3N8Y` (0.53),
`1Q4G` (0.53), `1DIY` (0.59), `1CX2` (0.62), `3QXX` (0.91).

**Tratamiento.** `REC-01` está sellado y **no se modifica**: su `LECTURA.md`
conserva el error, y este corrigendum es el registro oficial de la corrección
(mismo patrón que `RS-01A` → `RS-01A-R1`). Todo consumo posterior debe citar
**11**, no 23.

El dato cuantitativo sellado de REC-01 (`per_complex.jsonl`, `metrics.json`) es
correcto — `E2 = 23` siempre significó «contención < 1.0». El error estuvo
exclusivamente en la prosa que lo interpretó.

**Lección de método:** la comprobación de expectativa preregistrada detectó un
error que ningún gate de REC-01 podía detectar, porque los gates de REC-01
validaban el *instrumento*, no la *narrativa*. Declarar el resultado esperado
antes de ejecutar un corrigendum tiene valor aunque el corrigendum no sea ciego.

## 2. Gates

| Gate | Criterio | Resultado |
|---|---|---|
| G1 | Entrada sellada íntegra | **PASS** — `per_complex.jsonl` de REC-01 coincide con `3f4da5ab…eee23` |
| G2 | Aceptación: `5TUN` capturado por `E8` con `S4_LEVE` | **PASS** |
| G3 | Conservación: ningún target pierde una excepción; `E1…E7` reproducidos | **PASS** — 0 pérdidas |
| G4 | Severidad total: 387 con exactamente un nivel `S0…S5` | **PASS** |
| G5 | Determinismo byte-a-byte | **PASS** — 2 corridas idénticas |
| G6 | Aislamiento: REC-01 intacto | **PASS** — `validate REC-01` → OK tras ejecutar R1 |

## 3. El falso negativo, cerrado

`5TUN` —el caso testigo del doc. 35 que REC-01 dejó pasar— queda capturado:

```text
excepciones   ["E8_HOTSPOT_FUERA_DE_CAJA"]
severidad     S4_LEVE          (APO: sin ligando nativo, no puede alcanzar S1-S3)
margen_min    -5.147 Å
```

`E8` no tiene umbral calibrable: la condición es `margen_min_hotspots < 0`, que
es geometría exacta, no una fracción discutible. Ese es precisamente el modo de
fallo que corrige — REC-01 usó un umbral fraccional (`< 0.80`) donde bastaba una
condición binaria, y `5TUN` cayó exactamente en la frontera (`0.800`).

## 4. Excepciones tras el corrigendum

| | REC-01 | REC-01-R1 |
|---|---:|---:|
| Targets con excepción | 57 (14.7%) | **109 (28.2%)** |
| Nuevos sólo por `E8` | — | **52** |

Los conteos `E1…E7` se reproducen exactamente (gate G3): R1 sólo añade.

## 5. Triaje por severidad — la cohorte accionable

| Nivel | n | % | Interpretación |
|---|---:|---:|---|
| `S0_SIN_EXCEPCION` | 278 | 71.8% | — |
| `S1_CRITICO` | **11** | 2.8% | La caja no contiene ni un átomo del ligando |
| `S2_GRAVE` | **14** | 3.6% | Sitio mayoritariamente fuera |
| `S3_MODERADO` | 9 | 2.3% | Recorte parcial |
| `S4_LEVE` | 69 | 17.8% | Sólo hotspots rozando o fuera del borde |
| `S5_METADATO` | 6 | 1.6% | Defecto de datos del catálogo |

**`S1_CRITICO` (11)** — para estos targets, ningún generador de poses puede
acertar: el sitio de unión está fuera de la caja.

`8UBR` (77.5 Å), `4JSX` (76.7 Å), `5J89` (51.0 Å), `3MG0` (49.7 Å),
`3HYE` (48.3 Å), `3GPT` (48.2 Å), `6MWA` (43.1 Å), `1IGZ` (42.5 Å),
`7XW6` (32.1 Å), `5TNH` (27.2 Å), `5U6X` (20.2 Å).

**`S2_GRAVE` (14)** — `1CX2`, `1DIY`, `1Q4G`, `2OYE`, `2OYU`, `3FHV`, `3KK6`,
`3N8W`, `3N8X`, `3N8Y`, `3N8Z`, `5F1A`, `5WBE`, `7ZYJ`.

Los 25 de `S1`+`S2` son la cohorte natural de prueba para REC-03. Nótese que
tres proteasomas (`3MG0`, `3HYE`, `3GPT`) y cuatro estructuras de la serie
`3N8*` aparecen juntos: el fallo parece tener componente de familia, hipótesis
que REC-03 puede probar y que R1 **no** afirma.

## 6. Lo que este experimento NO decide

- No corrige ningún grid. `5TUN` sigue siendo REC-07; la política general, REC-03.
- No afirma que un target `S1`/`S2` produzca peor docking — la escala de
  severidad es una **hipótesis de accionabilidad**, no una medición de impacto.
  Probarlo exige el experimento pareado de REC-03, con docking.
- No re-deriva geometría: toda la geometría procede de REC-01, verificada por hash.
- Las métricas del estrato APO siguen usando ground truth **débil** y son
  descriptivas.
- El 28.2% **no es un hallazgo independiente** del 14.7% de REC-01: es el mismo
  dato con el criterio corregido.

## 7. Siguiente paso propuesto

1. **`REC-07`** — `5TUN` como caso testigo, ya con evidencia numérica
   (`margen_min = −5.147 Å`, `E8`, `S4_LEVE`).
2. **`REC-03`** — política de centro/tamaño adaptativo sobre la cohorte
   `S1`+`S2` (25 targets), con el control de que la corrección no degrade los
   278 `S0`.
3. Auditar por qué familias enteras (proteasoma, serie `3N8*`) comparten el
   fallo: probable defecto sistemático de curación, no 25 errores
   independientes.
