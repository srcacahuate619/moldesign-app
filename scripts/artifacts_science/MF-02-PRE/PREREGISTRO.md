# MF-02-PRE — Prerregistro maestro: ¿por qué falta la pose buena en un tercio de train?

**Fecha:** 2026-08-17
**Rama:** `experimentos/ruta-c-molflex`
**Estado:** PREREGISTRO
**Refina:** `MF-02` de la cartera C (doc. 49 §8) — «el número óptimo de conformeros depende de flexibilidad». Este registro lo descompone en dos ejes medibles por separado y en máquinas distintas.

---

## 1. La medición que obliga a este experimento

El doc. 49 §9 impone desde el 2026-08-17 la descomposición

> `Top-1 global = cobertura del oráculo × precisión condicional`

y ordena que el gate se evalúe sobre la **precisión condicional**, porque «un NO_GO debe poder distinguir *el selector no mejoró* de *el generador no dio material*». Esa descomposición **nunca se había calculado**. Calculada sobre los conjuntos de poses ya sellados:

| | Train (116) | Test (47) |
|---|---:|---:|
| **Cobertura del oráculo** (≥1 pose ≤2 Å) | **67.2%** (78/116) | **87.2%** (41/47) |
| Top-1 por `vina_score` | 41.4% | 53.2% |
| **Precisión condicional** | **61.5%** | **61.0%** |

Tres consecuencias que quedan declaradas antes de ejecutar nada:

1. **En 38 de 116 complejos de train no existe pose que seleccionar.** Todo experimento de selección evaluado sobre Top-1 global se midió sobre un universo del que un tercio era inganable por construcción.
2. **La precisión condicional es prácticamente idéntica en train y test (61.5% vs 61.0%)**: toda la diferencia de Top-1 la explica la cobertura del oráculo, no el selector. Esa diferencia venía confundiendo silenciosamente las comparaciones del programa.
3. El factor limitante es el **generador**, no el selector.

**Aviso de cuarentena**: estas cifras se calcularon sobre `poses_train.jsonl` y `poses_test.jsonl`. Es una medición del generador y no una selección de modelo, pero los números de test quedan a la vista y se registra así. `D-RC-CONFIRM` no se tocó.

## 2. Los dos ejes, y por qué se separan

Que falte la pose buena admite dos causas físicamente distintas:

- **(A) techo conformacional** — el ensemble ETKDG nunca contuvo la conformación bioactiva. Ningún presupuesto de búsqueda lo arregla.
- **(B) fallo de búsqueda o colocación** — el ensemble sí la contenía y el docking no la produjo, o el pipeline no la entregó.

Confundirlos es exactamente el error que la §9 prohíbe una escala más arriba. Se miden por separado, y en máquinas distintas porque tienen necesidades distintas: (A) es química pura (RDKit) y corre en el contenedor Ubuntu, que **no tiene Vina**; (B) necesita Vina y corre en la máquina local.

## 3. MF-02A — techo conformacional (medición, sin gates)

**Ya ejecutado y declarado aquí**, siguiendo el precedente de REC-07 §6 y REC-03-PRE §7: es una medición determinista sin parámetros libres ni criterio de aceptación, y su resultado es la condición de partida del resto.

Método: se replica el ensemble de `molflex.py::construir_ensemble` (ETKDG con preferencias de torsión CSD, `useBasicKnowledge`, `pruneRmsThresh=0.4`, `randomSeed=42`) y se mide el **RMSD mínimo ALINEADO** (`GetBestRMS`, átomos pesados, simetría incluida) entre cualquier confórmero y el ligando cristalográfico. Se alinea a propósito: la pregunta es sobre conformación interna, no sobre colocación — la decisión contraria a REC-03, donde se midió in situ porque allí se juzgaba el acierto de colocación.

Resultado (116 train, curva acumulada sobre un único embebido de 150):

| `n_conf` | mediana RMSD | ≤1.0 Å | ≤2.0 Å |
|---:|---:|---:|---:|
| 15 | 1.159 Å | 47.4% | 73.3% |
| **30** (protocolo congelado) | 1.085 Å | 49.1% | **77.6%** |
| 60 | 0.967 Å | 52.6% | 80.2% |
| 90 | 0.954 Å | 53.4% | 80.2% |
| 150 | 0.954 Å | 53.4% | **80.2%** |

**La curva satura entre 60 y 90 confórmeros.** Pasar de 30 a 150 —5× el coste— compra 2.6 puntos de techo.

Y el desglose que decide el resto del programa, sobre los **38 sin cobertura de pose**:

| Situación | n | Lectura |
|---|---:|---|
| conformación **ya disponible** con `n_conf=30` | **32** | fallo de búsqueda o colocación |
| se vuelve disponible solo con 150 confórmeros | 1 | `1aaq` |
| sin conformación válida ni con 150 | 5 | `1bjv`, `1mmr`, `1elb`, `1g3e`, `1a4w` — techo duro |

Más aún: el grupo **sin** cobertura tiene *mejor* disponibilidad conformacional a ≤2 Å (84%) que el grupo **con** cobertura (74%). La disponibilidad conformacional **no discrimina**: no es el cuello de botella.

**Conclusión declarada antes de ejecutar B**: añadir confórmeros es la palanca equivocada — rescata 1 de 38. La palanca está en la búsqueda.

## 4. MF-02A-EXT — ¿el techo conformacional generaliza? (medición, sin gates)

Misma medición sobre los **5332 complejos de PDBBind** disponibles en local, en el contenedor. Responde si el ~20% de techo duro es propiedad de esta cohorte de 116 o del método de embebido en general, y deja un activo reutilizable para cualquier ampliación futura del denominador (lo que la §19.1 exige para reabrir una cartera).

**Prohibición declarada**: la disponibilidad conformacional medida aquí **no puede usarse como filtro** para construir cohortes futuras sin declararlo en el prerregistro correspondiente; sería seleccionar complejos por una propiedad correlacionada con el éxito del docking.

## 5. Segundo hallazgo, también declarado antes de ejecutar B: MolFlex nunca se aplicó

Al preparar B se inspeccionó la procedencia de las poses de train. El conjunto no es lo que el nombre sugiere:

| | Complejos | Con poses `molflex` | Solo `flexible_redock` |
|---|---:|---:|---:|
| Con cobertura | 78 | 7 (9%) | 57 (73%) |
| Sin cobertura | 38 | 6 (16%) | 30 (79%) |

**MolFlex se aplicó a 13 de los 116 complejos.** En los otros 103 la cobertura del oráculo es, en la práctica, la de `flexible_redock` (redocking flexible de Vina). Tener poses de MolFlex tampoco correlaciona con estar cubierto (53.8% con vs 68.9% sin, n=13: sin poder).

La calibración de coste lo hace concreto. `1nki` figura **sin cobertura** en el conjunto sellado —sus 9 poses son todas `flexible_redock`, la mejor a 2.067 Å— y el pipeline MolFlex congelado, ejecutado hoy sin cambiar ningún parámetro, **entrega una pose a 0.199 Å en 6.4 s**.

Es decir: el tercio sin cobertura no es un fallo de búsqueda de MolFlex ni de su ensemble. Es que **a esos complejos nunca se les corrió MolFlex**.

## 6. MF-02B — aplicar el generador a la cohorte que nunca lo recibió (experimento con gates)

Esto prueba la hipótesis de **MF-01** («MolFlex añade candidatos que Vina flexible no genera») sobre una **cohorte nueva**: el conjunto de train completo en vez de `D-MF-HARD`. Vive bajo este prerregistro porque es MF-02A quien establece que el eje conformacional está agotado y que, por tanto, la pregunta pendiente es ésta.

**Cohorte**: los **38 sin cobertura** (primario) más **12 con cobertura** de control, muestreados con `random.Random(42).sample` sobre la lista ordenada de los 78.

**Brazos** (única variable = el presupuesto de búsqueda de Vina):

| Brazo | `exhaustiveness` | Resto |
|---|---:|---|
| `A8` | 8 (protocolo congelado, docs/40) — **brazo primario** | idéntico |
| `A32` | 32 — solo para el Pareto coste/beneficio | idéntico |

Mismo ensemble ETKDG (`n_conf=30`, seed 42), misma caja de 25 Å, misma semilla de Vina (42), `num_modes=9`, `top_k=3`, `cpu=1`. El valor efectivo de `exhaustiveness` se emite en `provenance.json`.

**Métrica primaria**: mejor RMSD a cristal entre las poses **entregadas** (top-K relajadas) por complejo y brazo; éxito = ≤ 2.0 Å. Se mide lo que el selector vería. **Limitación declarada**: una pose buena que exista entre las ~270 dockeadas y no llegue al top-K es pérdida de curación, no de generación, y queda fuera de alcance.

**Advertencia de interpretación, declarada por adelantado**: añadir una fuente a una unión **solo puede subir** la cobertura del oráculo. Que suba no es el hallazgo; el hallazgo es **cuánto** sube y **a qué coste**, y que el conjunto sellado sobre el que se evaluaron RS-01, RS-04-OOF y RS-08 estaba construido sin esta fuente en el 89% de los complejos.

**Gates**:

| ID | Gate | Criterio |
|---|---|---|
| G1 | **Validez** | ≥95% de los complejos completan el pipeline sin error |
| G2 | **Recuperación** (primario) | `A8` entrega pose ≤2 Å en **≥10 de los 38** — subiría la cobertura global del oráculo de 67.2% a ≥75.9% |
| G3 | **No regresión** | en el control, la unión con las poses nuevas no reduce la cobertura de ningún complejo (verificación de que se une, no se sustituye) |
| G4 | **Determinismo** | 2 complejos repetidos con la misma semilla dan el mismo RMSD y el mismo score |
| G5 | **Coste** | se reporta CPU por complejo y el Pareto `A8` vs `A32`; **sin umbral**, es descriptivo |

**GO** = G1–G4 pasan. **NO_GO** = falla G2 o G3. Si falla G1, se repite y no se interpreta.

Un GO **no cambia el protocolo de producción ni reabre la cartera D**: obliga a reconstruir el conjunto de poses antes de que ningún experimento de selección vuelva a evaluarse, que es cosa distinta y exige su propio prerregistro.

## 6. Prohibiciones

- No se toca `D-RC-CONFIRM`.
- No se ajusta el ensemble, la caja, las semillas ni `num_modes`: la única variable de B es `exhaustiveness`.
- Prohibido reportar la cobertura sobre las ~270 poses dockeadas como si fuera la métrica primaria: la primaria es la pose **entregada**.
- Prohibido concluir de A o de A-EXT nada sobre el selector: son mediciones del generador.
