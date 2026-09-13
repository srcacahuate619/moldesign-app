# REC-01-R1 — Corrigendum del criterio de excepción: `E8_HOTSPOT_FUERA_DE_CAJA` y triaje por severidad

**Estado:** preregistrado, **sin ejecutar**.
**Fecha de preregistro:** 2026-08-17.
**Tipo:** corrigendum de [`REC-01`](../REC-01/) (sellado GO el 2026-08-17).
**Nivel de madurez (doc. 49 §3):** E1. No puede afectar producción.

---

## 1. Honestidad sobre la naturaleza de este experimento

**Este corrigendum NO es una prueba ciega y no debe presentarse como tal.**

El desenlace numérico ya se conoce: se computó durante la lectura de REC-01 y
está declarado en [`REC-01/LECTURA.md`](../REC-01/LECTURA.md) §4, que reporta
que un criterio de margen negativo capturaría 52 targets adicionales (57 → 109,
14.7% → 28.2%) y que `5TUN` es el segundo peor de esa lista.

El propósito de R1 **no es descubrir** ese número, sino:

1. convertir `E8` en criterio **oficial y sellado**, no en una observación al
   margen de un README;
2. producir la **lista corregida completa** como artefacto reproducible que
   REC-07 y REC-03 puedan consumir por hash;
3. añadir un **triaje por severidad** que hoy no existe y sin el cual las 109
   excepciones no son accionables;
4. dejar registrado el modo de fallo del criterio original, para que no se repita
   en REC-03 ni en REC-08.

Cualquier lectura que presente el 28.2% como un hallazgo independiente de REC-01
sería incorrecta: es el mismo dato, con el criterio corregido.

## 2. El falso negativo que motiva el corrigendum

REC-01 no capturó `5TUN`, el caso testigo del doc. 35:

```text
estrato               APO          -> E1 no aplica (ground truth débil)
contencion_hotspots   0.800        -> umbral E3 es "< 0.80" -> no dispara (frontera exacta)
hotspots_validos      1.000        -> E4 no dispara
n_hotspots            15           -> E5 no dispara
margen_min_hotspots   -5.147 Å     <- hotspot 5.1 Å FUERA de la caja
excepciones           []           <- pasa limpio
```

**Diagnóstico del modo de fallo:** un criterio de contención por *fracción* mide
cuántos hotspots están dentro, no *cuán fuera* está el peor. Un desalineamiento
severo concentrado en 2 o 3 residuos de 15 queda por debajo de cualquier umbral
fraccional razonable. El doc. 35 lo había detectado por inspección visual
precisamente porque el ojo mide margen, no fracción.

Es un fallo **estructural del criterio**, no un umbral mal elegido: bajar el
umbral de 0.80 a 0.85 capturaría `5TUN` por accidente y seguiría sin ver un
target con 1 hotspot de 30 a −20 Å.

## 3. Alcance y prohibiciones

**Dentro de alcance:** post-procesamiento del `per_complex.jsonl` **sellado** de
REC-01 (387 registros), que ya contiene `margen_min_hotspots`,
`contencion_ligando`, `contencion_hotspots`, `d_centro` y `estrato`.

**Fuera de alcance y prohibido:**

- **no se re-deriva geometría**: R1 no vuelve a parsear PDBs. La geometría quedó
  sellada en REC-01 y se consume verificando su SHA-256;
- **no se modifica REC-01** ni ninguno de sus assets sellados. `run_rec01_grid_audit.py`
  está sellado y se reutiliza **por composición**, nunca editándolo (doc. 49 §17);
- **cero docking**, cero red, cero escrituras en catálogo, DB o `rescoring/`;
- no se corrige ningún grid: eso es REC-07 (`5TUN`) y REC-03 (política general);
- no se afirma que un target excepcional produzca peor docking. Esa es la
  hipótesis de REC-03 y exige un experimento pareado con docking.

## 4. Definiciones congeladas

### 4.1. Nuevo código de excepción

| Código | Condición | Estrato aplicable |
|---|---|---|
| `E8_HOTSPOT_FUERA_DE_CAJA` | `margen_min_hotspots < 0` | todos, cuando exista al menos un hotspot localizado en el PDB |

Cuando no se localiza ningún hotspot en el PDB, `margen_min_hotspots` es `null`
y `E8` **no** dispara; esos targets ya los captura `E4_HOTSPOTS_INVALIDOS`
(`hotspots_validos < 0.80`). No se introduce doble conteo.

El umbral es **cero por construcción**, no un parámetro ajustable: «el residuo
está fuera de la caja» no admite calibración. Esto es deliberado — el fallo de
REC-01 vino de usar un umbral fraccional discutible donde bastaba una condición
geométrica exacta.

Los siete códigos `E1…E7` de REC-01 **se conservan sin cambios**. R1 sólo añade.

### 4.2. Triaje por severidad

Las 109 excepciones esperadas no son equivalentes: un target cuya caja no
contiene ni un átomo del ligando es irrecuperable para cualquier generador,
mientras que un hotspot 1.5 Å fuera es cosmético. Se preregistra una escala
ordenada por **una única pregunta: ¿puede un docking en esta caja producir una
pose correcta?**

| Nivel | Condición (primera que aplique, en este orden) | Interpretación |
|---|---|---|
| `S1_CRITICO` | `contencion_ligando == 0.0` (HOLO) | La caja no contiene ni un átomo del sitio real. Ningún generador puede acertar |
| `S2_GRAVE` | `d_centro > 15 Å` con ground truth fuerte, **o** `0 < contencion_ligando < 0.5` | El sitio está mayoritariamente fuera |
| `S3_MODERADO` | `E1` (6–15 Å), **o** `0.5 <= contencion_ligando < 1.0` | Recorte parcial; probable pérdida de poses válidas |
| `S4_LEVE` | sólo problemas de hotspots (`E3` y/o `E8`) sin recorte de ligando | Geometría del sitio plausible; la caja roza el borde |
| `S5_METADATO` | sólo `E4`, `E5`, `E6` o `E7` | Defecto de datos del catálogo, no de geometría |
| `S0_SIN_EXCEPCION` | sin ningún código | — |

La escala se fija ahora y no se ajusta tras ver la distribución resultante.

### 4.3. Prueba de aceptación

`5TUN` **debe** quedar clasificado con `E8` y severidad `S4_LEVE` (es APO, sin
ligando nativo, por lo que no puede alcanzar `S1`–`S3`). Si no ocurre, R1 es
NO_GO: el corrigendum no habría corregido el fallo que lo motiva.

## 5. Gates

| ID | Gate | Criterio |
|---|---|---|
| G1 | **Integridad de entrada** | el `per_complex.jsonl` de REC-01 coincide con su SHA-256 sellado `3f4da5ab…eee23`; si no, abortar |
| G2 | **Aceptación** | `5TUN` capturado por `E8` con severidad `S4_LEVE` |
| G3 | **Conservación** | ningún target pierde una excepción que REC-01 le había asignado; los conteos `E1…E7` se reproducen exactamente |
| G4 | **Severidad total** | los 387 targets reciben exactamente un nivel `S0…S5`, sin nulos |
| G5 | **Determinismo** | dos corridas → `per_complex.jsonl` byte-idéntico |
| G6 | **Aislamiento** | REC-01 conserva los SHA-256 de todos sus assets tras la corrida |

**GO** = los seis gates pasan. **NO_GO** = falla cualquiera.

Igual que en REC-01, el GO califica al **instrumento**, no al catálogo: la
fracción de excepciones y su reparto por severidad son el resultado, no el gate.

## 6. Resultado esperado, declarado antes de ejecutar

Por §1, se declara la expectativa para que cualquier desviación sea visible:

- excepciones totales: **57 → 109** (14.7% → 28.2%);
- targets nuevos por `E8`: **52**;
- targets con algún hotspot fuera de caja: **65 de 380** con margen computable,
  de los que 13 ya estaban marcados;
- `S1_CRITICO` esperado: **23** (los de `contencion_ligando = 0.00`).

Una discrepancia con estas cifras indica un error de implementación en R1, no un
hallazgo nuevo.

## 7. Artefactos

```text
scripts/artifacts_science/REC-01-R1/
  PREREGISTRO.md      (este archivo)
  manifest.json
  metrics.json        conteos por código, severidad, estrato y familia
  per_complex.jsonl   387 registros con excepciones corregidas y severidad
  failures.jsonl
  LECTURA.md          lectura científica (README.md lo regenera la herramienta)
```

Ejecutor: `scripts/run_rec01_r1_triage.py` (nuevo). Importa
`scripts/run_rec01_grid_audit.py` por composición para reutilizar sus constantes
sin modificarlo.

Semilla preregistrada: 42. El experimento es determinista y no usa aleatoriedad.
