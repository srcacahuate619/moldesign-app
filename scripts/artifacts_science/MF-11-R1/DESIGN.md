# MF-11-R1 — Deduplicación con contrato ORIGINAL: diámetro controlado + medoid geométrico (SOLO train)

**Fecha:** 2026-08-16
**Rama:** `experimentos/ruta-c-molflex`
**Referencia:** `docs/49_PROGRAMA_EXPERIMENTAL_CIENTIFICO.md` §15 entregable 9,
Cartera C, MF-11. Recuperación del contrato original autorizado por el
maintainer. MF-11 (commit próximo a `2f617ec`) quedó sellada NO_GO por usar
representante = primera identidad (desviación D2) y por procesar val junto
con train (desviación D1); ambas están registradas en `MF-11/DESIGN.md`.

## 1. Alcance

Deduplicar la unión materializada sellada `MF-01-UNION` reduciendo poses
redundantes SIN perder el oráculo (cobertura min-RMSD ≤ 2.0 Å), con el
contrato ORIGINAL: clustering con DIÁMETRO controlado y representante
primario = MEDOID GEOMÉTRICO (empate por identidad).

- **SOLO train**: `union_candidates_train.jsonl` + `union_labels_train.jsonl`
  (116 complejos / 2739 poses). Cero val, cero test, cero denylist.
- **Desviación D1 heredada**: la val de MF-11 ya fue procesada y queda
  inhabilitada para validar variantes. MF-11-R1 la EXCLUYE por completo de
  selección y confirmación; la regla se evalúa únicamente sobre train.
- Análisis PURO sobre poses existentes: SIN docking, SIN scoring v0.6, SIN
  acceso a test histórico.
- Los brazos sellados `D-MF-HARD-CURVE` y `D-MF-HARD-EXH4` NO se tocan.

## 2. Contrato exacto (preregistrado ANTES de evaluar)

1. **Métrica (geometría pose-vs-pose):** RMSD pocket-frame entre poses del
   MISMO complejo: átomos pesados, matching 1:1 por serial del PDBQT, SIN
   alineamiento, sobre coordenadas absolutas del marco del receptor fijo.
   Extensión por pares de `molflex.rmsd_pose_pocket` (misma definición de
   marco: traslación/rotación de la pose NO se compensan). Caveat heredado:
   matching 1:1 SIN simetría química — una pose relacionada por simetría
   (p. ej. flip de anillo) puede reportar RMSD inflado; el clustering puede
   ser conservador. La métrica simetría-corregida es trabajo futuro.
2. **Clustering con diámetro controlado** — ver §3 (regla de admisión exacta,
   definida ANTES de correr).
3. **Representante primario = MEDOID GEOMÉTRICO**: miembro del cluster que
   minimiza la suma de RMSDs a los demás miembros; empate por identidad
   ascendente. Label-blind (solo geometría; nunca usa labels).
4. **Umbrales PREREGISTRADOS: 0.5, 0.75, 1.0, 1.5, 2.0 Å** — los 5 en una
   sola pasada determinista.
5. **Selección del umbral** — ver §4.
6. **"Mejor Vina score" SOLO como ablation secundaria** — ver §6. NO es el
   representante primario.
7. **Labels**: leídas SOLO para evaluar preservación (§5 condiciones a/b),
   NUNCA para admisión ni elección de representante. Verificado por test
   sintético: alterar los labels deja los candidatos byte-idénticos.

## 3. Regla de admisión EXACTA (definida ANTES de correr)

> **Regla (diámetro estricto):** greedy determinista por identidad
> ascendente. Una pose entra al PRIMER cluster existente (orden de creación)
> si su RMSD pose-vs-pose a TODOS los miembros del cluster es ≤ U. Si ningún
> cluster es compatible, abre cluster nuevo.

**Garantía:** como cada miembro fue admitido siendo ≤ U de todos los
previos, todo par de miembros del cluster está a ≤ U → diámetro controlado
por construcción.

**Justificación de la elección frente a la alternativa:** el contrato
autorizaba "a TODOS los miembros … — o al menos al medoid; define y
documenta la regla de admisión exacta". Se elige la lectura de diámetro
estricto porque (1) el nombre del punto 2 del contrato es "clustering con
DIÁMETRO controlado", (2) la frase primaria es "a TODOS los miembros ≤ umbral
(diámetro)", y (3) garantiza la propiedad de diámetro sin depender de un
medoid dinámico durante la admisión. El medoid se calcula AL FINAL del
cluster SOLO para elegir representante; la alternativa "admisión solo contra
el medoid" no controla el diámetro (dos miembros podrían quedar a ~2U) y fue
descartada para la corrida primaria.

## 4. Regla de selección de umbral (preregistrada)

Elegir el **MAYOR** umbral que cumpla las tres condiciones:

- **(a) CERO pérdidas de cobertura de oráculo**: todo complejo cubierto
  antes (min rmsd ≤ 2.0 Å) sigue cubierto después (min rmsd de los medoids
  representantes ≤ 2.0 Å).
- **(b) Degradación mediana de min-RMSD ≤ 0.1 Å**: mediana sobre los 116
  complejos de (min rmsd de medoids − mejor rmsd antes). Nota: la
  degradación es ≥ 0 por construcción (los representantes son un subconjunto
  de las poses originales); la mediana se computa sobre los 116 complejos.
- **(c) Reducción de candidatos ≥ 10%**.

Si ninguno cumple, el experimento reporta NO_GO con la tabla completa (sin
elegir a dedo). Fallback preregistrado para `per_complex.jsonl` (solo si
ninguno cumple): umbral con 0 pérdidas y MENOR degradación mediana (empate:
mayor U); si ninguno tiene 0 pérdidas, el mayor U.

## 5. Resultados (train, 116 complejos / 2739 poses)

| U (Å) | N antes | N después | Reducción % | Pérdidas | Degradación mediana (Å) | (a) | (b) | (c) | ¿Cumple? |
|---|---|---|---|---|---|---|---|---|---|
| 0.5 | 2739 | 2706 | 1.20 | 0 | 0.000 | ✔ | ✔ | ✘ | ✘ |
| 0.75 | 2739 | 2660 | 2.88 | 0 | 0.000 | ✔ | ✔ | ✘ | ✘ |
| 1.0 | 2739 | 2585 | 5.62 | 0 | 0.000 | ✔ | ✔ | ✘ | ✘ |
| **1.5** | **2739** | **2413** | **11.90** | **0** | **0.000** | **✔** | **✔** | **✔** | **✔** |
| 2.0 | 2739 | 2137 | 21.98 | 3 | 0.000 | ✘ | ✔ | ✔ | ✘ |

Cobertura de oráculo antes: 78/116 (0.6724). En los umbrales válidos la
cobertura queda intacta (78/78). **Umbral elegido por la regla: 1.5 Å**
(mayor umbral válido): 2413 candidatos, reducción 11.90 %, 0 pérdidas,
degradación mediana 0.000.

A 2.0 Å el medoid pierde 3 complejos de frontera (`1alw`, `1bcd`, `1bn4`):
el medoid geométrico NO es la mejor pose cristalográfica del cluster, así
que con diámetro 2.0 tres clusters quedaron representados por medoids con
rmsd > 2.0. La regla preregistrada lo descarta y elige 1.5, que preserva el
oráculo al 100 %.

Tamaños de cluster (U=1.5): P50=1, P90=1, max=8, media=1.14. Supervivencia
por fuente (U=1.5): flexible_redock 97.42 %, molflex 86.59 %, ruta_a 69.07 %.
(A 2.0: 90.14 / 74.25 / 63.23 %.)

**Sidecar de membresía (U=1.5):** `cluster_members_train_1.5.jsonl`, 2413
registros (uno por cluster): representante medoid, miembros por identidad
ascendente con fuentes y provenance_keys, tamaño y diámetro máximo —
permite auditar qué poses se descartaron sin reejecutar el algoritmo.
**Empates del medoid (U=1.5):** 212 clusters no-singleton, 141 empates, 31
cross-source (cuantificación completa en `metrics.json` → `empates_medoid` y
en §7).

## 6. Ablation SECUNDARIA: representante = mejor Vina score

**NO es el representante primario.** Se reporta en `metrics.json` qué pasaría
si el representante fuera la pose con mejor (menor) `vina_score` del cluster
(empate por identidad ascendente; label-blind, `vina_score` vive en el
candidato). El clustering NO cambia; solo cambia el representante.

| U (Å) | Cubiertos (medoid) | Cubiertos (Vina) | Pérdidas (medoid) | Pérdidas (Vina) |
|---|---|---|---|---|
| 0.5–1.5 | 78 | 78 | 0 | 0 |
| 2.0 | 75 | 76 | 3 (`1alw`, `1bcd`, `1bn4`) | 2 (`1alw`, `1bcd`) |

A 2.0 Å, mejor-Vina recuperaría `1bn4` (3→2 pérdidas) pero seguiría
perdiendo `1alw`/`1bcd`. **Nota obligatoria:** mezcla deduplicación con una
señal de scoring que RS-01 evaluará después; puede favorecer
fuentes/configuraciones de Vina (p. ej. redocks con mejor score sin ser
cristalográficamente mejores). No se usa para la decisión.

## 7. Caveats

- **Métrica 1:1 sin simetría química** (heredado de `rmsd_pose_pocket`):
  flips simétricos pueden inflar el RMSD → clustering conservador.
- El objetivo del medoid es source-agnostic; el desempate determinista por
  identidad puede introducir preferencia de fuente en empates. Se cuantifica
  y conserva como caveat para RS-01.

  **Cuantificación (U=1.5 Å, bloque `empates_medoid` de metrics.json):**
  212 clusters no-singleton; 141 empates de medoid (2+ miembros con la misma
  suma exacta de distancias); 31 empates cross-source; fuente elegida en los
  empates cross-source: flexible_redock 31/31. El orden lexicográfico de la
  identidad (`split|pid|source|file_stem|model_idx`) coloca `flexible_redock`
  antes que `molflex` y `ruta_a`, por lo que en todo empate cross-source el
  desempate por identidad favorece a flexible_redock.
- **El medoid no es la mejor pose cristalográfica**: minimiza distancia
  geométrica, no rmsd al cristal. Por eso a 2.0 Å aparecen 3 pérdidas de
  frontera; la regla de selección (0 pérdidas) es la que protege el oráculo.
- **Degradación mediana = 0** en todos los umbrales: en la mayoría de los
  complejos la mejor pose sobrevive como medoid de su cluster; la mediana
  no detecta las colas (los 3 complejos perdidos a 2.0), por eso la
  condición (a) es la decisiva.

## 8. Determinismo y verificación

- 2 corridas → SHA-256 byte-idénticos de las 14 salidas:

  | Archivo | SHA-256 |
  |---|---|
  | `dedup_candidates_train_0.5.jsonl` | `87e4246bbe47a59b865b9cf37b543abc666fcd8ebd23b9bfe3f5720089cf4cee` |
  | `dedup_candidates_train_0.75.jsonl` | `0dcd1b0385dd891c377a3226ffa521347c120abac4b518226c2605774aae6aea` |
  | `dedup_candidates_train_1.0.jsonl` | `8d039152a702834221f209543b8e130e616209d97314c3aaf4632e0f7aab9eec` |
  | `dedup_candidates_train_1.5.jsonl` | `fef90c21c92d3527a3431d8e880601d33208a1c12688057f8ebf95642589fa78` |
  | `dedup_candidates_train_2.0.jsonl` | `fb2c765721c07ae72b5434d857c819164b318f58b67db0485526b6db666c9ab6` |
  | `dedup_labels_train_0.5.jsonl` | `f049d2c51fe8be211b74394eed50083554d40e59f0fc93f92e99fefa53d5d6b0` |
  | `dedup_labels_train_0.75.jsonl` | `98877ef2c9be1dae3e35172cab4257ff8f6c16ba4f84d28a8955441b5872a5ff` |
  | `dedup_labels_train_1.0.jsonl` | `c828889fef534cfcadaba2525dbaa8ff5066f179032e943e8dd904e57a3bef0c` |
  | `dedup_labels_train_1.5.jsonl` | `e07a9fec590ebfa646ae90f217f1c4727dd2c334f545d9476c977502e6e9f815` |
  | `dedup_labels_train_2.0.jsonl` | `f6c3fc15ae184036251e3f081fc9ce452d78ca0ccbb866922c00aa47f6124557` |
  | `cluster_members_train_1.5.jsonl` | `7026b8dea49062d49e4765ab116864fe6bd550ac660c76da646aabb7a645d0a0` |
  | `failures.jsonl` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` (vacío: 0 anomalías) |
  | `metrics.json` | `2d271875f10270e197f72a0bedb39fb52f0b347109781a931432dcdca4c0c5cd` |
  | `per_complex.jsonl` | `a9bdac2c4e8276039db78ffd69c653bd7a3cce94004f1638ccb959b542b0bcc5` |

- Test sintético `scripts/test_dedup_pose_union_medoid.py`: 8/8 OK — medoid
  ≠ identity-first (el medoid se elige por mínima suma de distancias), empate
  por identidad ascendente, admisión por DIÁMETRO (una pose a ≤U del
  representante pero >U de otro miembro NO entra), ablation mejor-Vina da
  OTRO representante, label-blind (labels alterados → candidatos
  byte-idénticos), determinismo de dos corridas, solo-train (archivos val
  envenenados ignorados; 0 identidades val en salidas), selección del mayor
  umbral válido end-to-end.
- `validate MF-11-R1` OK, `validate MF-11` OK (sellada NO_GO intacta),
  `validate MF-01-UNION` OK (unión sellada intacta).
- 0 pids val/test/denylist en cualquier salida: 0 coincidencias de `|val` y
  `"split": "val"` en las 13 salidas; 0 intersecciones con los 47 test pids
  (manifest sellado del dataset, integridad `test_pids_sha256` verificada) y
  con los 112 pids de la denylist FND-05 D-RC-CONFIRM (integridad
  `sha256_candidates` verificada).

## 9. Salidas

| Archivo | Contenido |
|---|---|
| `dedup_candidates_train_{U}.jsonl` (×5) | representante = medoid por cluster (identity + PDBQT + vina_score + campos de la unión), SIN rmsd, ordenado por identidad |
| `dedup_labels_train_{U}.jsonl` (×5) | labels del medoid keyed por identidad + `cluster_id`, `cluster_size` y `cluster_best_*` (dato de evaluación) |
| `cluster_members_train_1.5.jsonl` | sidecar de membresía del umbral elegido: 2413 registros (cluster_key, representante medoid, miembros/fuentes/provenance_keys, tamaño, diámetro máximo) |
| `metrics.json` | tabla por umbral (N, reducción, cobertura, pérdidas, degradación), selección, ablation mejor-Vina (secundaria), `empates_medoid`, exclusiones |
| `per_complex.jsonl` (116) | por complejo, umbral elegido (1.5): n antes/después, cobertura, degradación |
| `failures.jsonl` | anomalías (vacío: 0) |
| `DESIGN.md` | este documento |

## 10. Nota final

**MF-11-R1 prepara una unión más limpia para reabrir RS-01; NO rehabilita
MF-11 (sellada NO_GO).** El experimento queda SIN seal y SIN finish por
instrucción del protocolo (decisión PENDING en el manifest; el maintainer
decide el camino).
