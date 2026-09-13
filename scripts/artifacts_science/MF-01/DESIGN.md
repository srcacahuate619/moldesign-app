# MF-01 (primera parte) — Tabla de cobertura por fuente y flexibilidad sobre train/val

**Fecha:** 2026-08-16
**Rama:** `experimentos/ruta-c-molflex`
**Referencia:** `docs/49_PROGRAMA_EXPERIMENTAL_CIENTIFICO.md` §15, entregable 3 (Campaña 1, MF-01).

> "MolFlex añade candidatos que Vina flexible no genera" — Unir candidatos
> actuales por fuente antes de redockear. Gate: +3 complejos o +5 pp de
> cobertura en D-MF-HARD.

## 1. Qué es este artefacto

Es la **tabla de cobertura pre-unión**: caracteriza las poses EXISTENTES de
Ruta C (dataset sellado `data/pose_selector_dataset/`, D-RC-HIST) sobre
train+val = **156 complejos / 3469 poses**, sin generar ni re-dockear nada.

Por cada complejo (train 116 + val 40) se calcula:

- número de poses por fuente (`molflex` / `flexible_redock` / `ruta_a`);
- **oráculo por fuente**: mínimo RMSD pocket-frame de las poses de esa fuente;
- **oráculo de la unión**: mínimo RMSD global del complejo;
- `rot_bonds` del ligando cristalográfico (`data/pdbbind/{pid}/{pid}_ligand.sdf`);
- `oracle_covered` = min RMSD de la unión ≤ 2.0 Å.

El sidecar sellado de FND-06 (`poses_provenance.jsonl`, 560 corridas, clave
`pid|source|file_stem`) completa metadatos por corrida (seed, exhaustiveness,
num_modes, box) y se resume en `metrics.json:provenance_por_fuente`.

Insumos verificados: 2739 poses/116 pids (train), 730/40 (val), 3469/3469
poses con registro de provenance, 156/156 SDF cristalográficos parseables,
0 pids compartidos entre train y val, `failures.jsonl` vacío.

## 2. Qué NO es este artefacto

1. **NO incluye la unión materializada** — la cobertura de la unión aquí es
   PRE-materialización (cada pose cuenta una vez aunque dos fuentes generen la
   misma pose). La unión materializada SIN deduplicar es el entregable 4
   (experimento MF-01-UNION); la deduplicación por RMSD pocket-frame es el
   entregable 9 / MF-11, después de RS-01 (docs/49 §15).
2. **NO incluye scoring v0.6** — eso es RS-01, que puntuará la unión después.
3. **NO re-dockea ni amplía MolFlex** — no se ejecuta ningún generador; la
   decisión GO/NO-GO de ampliar MolFlex es el entregable 10.
4. **NO usa test histórico** (47 complejos / 831 poses): el programa lo
   excluye de decisiones nuevas (docs/49 §4).

## 3. Definiciones de métricas

| Métrica | Definición |
|---|---|
| Oráculo | `min RMSD pocket-frame ≤ 2.0 Å` por complejo (docs/49 §5, sin alineamiento rígido; campo `rmsd` del dataset) |
| `min_rmsd_{fuente}` | mínimo de `rmsd` entre las poses de esa fuente en el complejo |
| `min_rmsd_union` | mínimo de `rmsd` entre TODAS las poses del complejo |
| `oracle_covered` | `min_rmsd_union ≤ 2.0` |
| Cobertura por fuente | n complejos con min-RMSD de la fuente ≤ 2.0, sobre el total del subconjunto (156 / 116 / 40) — el denominador fijo del entregable |
| Cobertura condicional | n cubiertos / n complejos CON poses de la fuente (lectura de eficiencia de la fuente en su propia cohorte) |
| Mediana min-RMSD | mediana de los min-RMSD sobre complejos con poses de la fuente (denominador condicional) |
| `rot_bonds` | `Descriptors.NumRotatableBonds(AddHs(mol))` del SDF cristalográfico (convención `ruta_a_exh_validation.py`); `"unknown"` si el SDF no parsea |
| Estratos | `0-4` / `5-9` / `10-14` / `>=15` rot_bonds; `>=15` ≈ D-MF-HARD (docs/49 §4) |

## 4. Lectura inicial de los números

### 4.1 Cobertura por fuente (train+val, 156 complejos)

| Fuente | Cubiertos /156 | % | Mediana min-RMSD (Å) | Poses | Complejos con poses | % condicional |
|---|---|---|---|---|---|---|
| flexible_redock | 102 | 65.4% | 1.412 | 1169 | 143 | 71.3% |
| ruta_a | 16 | 10.3% | 1.369 | 366 | 20 | 80.0% |
| molflex | 8 | 5.1% | 1.518 | 1934 | 15 | 53.3% |
| **unión** | **108** | **69.2%** | **1.398** | 3469 | 156 | 69.2% |

**La fuente dominante es `flexible_redock`**: es la única con presencia amplia
(143/156 complejos) y sostiene 102 de los 108 complejos cubiertos.

**Contribución marginal de la unión: +6 complejos** respecto de
flexible_redock solo, y los seis los aporta molflex: `184l`, `187l`, `188l`,
`1a99`, `1ai4`, `1a4r` — todos de flexibilidad BAJA (rot_bonds ≤ 4). Es la
evidencia concreta de que MolFlex genera candidatos que Vina flexible no
genera, aunque hoy se concentre en complejos fáciles.

**ruta_a aporta 0 complejos marginales**: sus 16 cubiertos están subsumidos
en la cobertura de flexible_redock. Su valor no es cobertura sino calibración
de exhaustiveness (exh 1/2/4); su tasa condicional (80%) y su mediana
(1.369 Å) son las mejores de las tres fuentes.

### 4.2 Cobertura por estrato de flexibilidad (train+val)

| Estrato | n complejos | Unión cubiertos | % unión | flexible_redock | molflex | ruta_a |
|---|---|---|---|---|---|---|
| 0-4 | 44 | 33 | 75.0% | 29 (65.9%) | 5 (11.4%) | 3 (6.8%) |
| 5-9 | 56 | 38 | 67.9% | 37 (66.1%) | 2 (3.6%) | 4 (7.1%) |
| 10-14 | 34 | 22 | 64.7% | 21 (61.8%) | 1 (2.9%) | 2 (5.9%) |
| >=15 | 22 | 15 | 68.2% | 15 (68.2%) | 0 (0.0%) | 7 (31.8%) |

Distribución de poses por fuente y estrato: molflex concentra el 82% de sus
poses en 10-14 y >=15 (1042 + 547 de 1934) — su diseño histórico apuntaba a
ligandos flexibles — pero en esos estratos solo está presente en 8 complejos.

**En D-MF-HARD (>=15) el oráculo lo sostiene flexible_redock (15/22)**;
molflex está en solo 3 complejos del estrato y cubre 0. El gate de MF-01
("+3 complejos o +5 pp en D-MF-HARD") NO se alcanza con las poses existentes:
es lo esperado, porque la cohorte molflex histórica es pequeña (18 pids en
todo el dataset) y no se diseñó para D-MF-HARD. La decisión de ampliar
MolFlex (entregable 10) es posterior y se apoya en esta tabla.

### 4.3 Dónde falla el oráculo

48/156 complejos (30.8%) no tienen NINGUNA pose ≤ 2.0 Å. Por estrato: 0-4:
11/44 (25%), 5-9: 18/56 (32.1%), 10-14: 12/34 (35.3%), >=15: 7/22 (31.8%).
El peor estrato relativo es 10-14.

Los peores fallos absolutos (min-RMSD de unión > 7 Å) son complejos donde
SOLO existe flexible_redock: `1hk4` (12.9 Å), `1d2e` (12.2), `1njs` (10.6),
`1b57` (10.1), `1fh7` (9.3), `1f74` (8.9), `1f8b` (8.1), `1elb` (7.2).
Ninguna fuente actual genera una pose cercana ahí: son los candidatos
naturales para las curvas de conformeros (MF-02) y la decidibilidad (RS-08).

Caveat conocido (FND-06): `10gs` (molflex, rb=14, min unión 5.951 Å) es el
complejo con workdir mezclado entre olas e2+v4; sus poses no se descartan
pero su origen está documentado.

### 4.4 Provenance por fuente (sidecar FND-06, train+val)

3469/3469 poses con registro (0 sin). molflex: 244 corridas, seed=42,
exh=8, 9 modos. flexible_redock: 143 corridas, seed unknown, exh=8, 9 modos.
ruta_a: 60 corridas, seed unknown, exh 1/2/4 (20 cada una), 9 modos. Box
`center_from_crystal_ligand` (25 Å) en las tres fuentes.

## 5. Implementación y determinismo

- `scripts/mf01_coverage.py` (stdlib + RDKit): lectura read-only del dataset
  sellado y del sidecar, agregación por complejo, escritura atómica de
  `metrics.json`, `per_complex.jsonl` y `failures.jsonl`. Sin marcas de
  tiempo; claves y orden canónicos.
- Determinismo VERIFICADO: 2 corridas → SHA-256 idénticos para `metrics.json`
  (`C871DCF9…A3F3A0`) y `per_complex.jsonl` (`441B473B…DDD4E4`).
- Reproducción: `python scripts/mf01_coverage.py`.
