# MolGraph v2 — Evolución del Knowledge Graph Químico

> **Documentación técnica** · SELF-CONTAINED (no requiere leer código para entender WHAT / WHY / HOW / RESULTS)

| Campo | Valor |
|---|---|
| **Proyecto** | MolDesign (drug discovery app de escritorio) |
| **Backend** | Python 3.11 · FastAPI · SQLite (WAL) |
| **Frontend** | Next.js 14 · Tauri 2 |
| **Cambio SDD** | `molgraph-v2-evolution` — **Fase A** (fundación) |
| **Estado** | ✅ **COMPLETA + ARCHIVED** (2026-08-01/02) · Fases B/C/D pendientes |
| **DBs** | Live: `~/MolDesign/data/molgraph.db` · Seeds: `data/molgraph_seed.db` (x2) |
| **Cobertura nueva** | 56% en `services/ai/molgraph.py` (antes 0%) · **37 pytest PASS** |

---

## Resumen Ejecutivo

**MolGraph** es el knowledge graph químico de MolDesign: guarda moléculas, blancos (targets) y evaluaciones (docking) como nodos, y las relaciones entre ellos (docking, same_target, similar, modified_from) como edges, sobre **SQLite + FTS5**. Almacena fingerprints de similitud química en pickle y alimenta un *early-exit*: si una molécula es muy similar a vecinos de bajo score, no hace falta gastar tiempo en docking.

**El problema**: la v1.x tenía 10 riesgos verificados (de un scoring key-partido hasta drift de FTS5 con 5324 filas faltantes) y **cero tests**. Además, la hipótesis original de "propagar scores por el grafo con una GNN" está **refutada por la literatura**: el *Laplacian smoothing* colapsa los scores de un cluster al promedio (efecto documentado), y los KGEs no clusterizan entidades similares. El techo real está en **pool-based Active Learning + ranking sobre fingerprints** (ECFP + CatBoost).

**La v2** re-arquitecta la fundación: nodos **evaluated** vs **catalog**, un **score canónico único** en escala `[0,100]`, migración idempotente con backup, **triggers FTS5** (sin drift posible), invalidación de cache en runtime, y ranking top-N **global real**. El proceso fue guiado por **SDD** (explore → proposal → spec → design → tasks → apply → verify → archive), con un bug crítico (C1) atrapado y resuelto en la verificación.

**Resultados verificados (Fase A)**: 0% falsos negativos en 7642 moléculas, 2628/2633 scored en DB live, FTS 0 orphans/0 mismatches, 37 tests PASS, lockstep SHA256 idéntico backend↔frontend, 11/11 requisitos de spec conformes.

---

## 1. Contexto: qué es MolGraph y por qué evolucionar

### 1.1 Qué hace MolGraph

MolGraph es un grafo dirigido de conocimiento químico con 4 tipos de nodos y 4 relaciones:

| Nodo | Rol | Ejemplo |
|---|---|---|
| `molecule` | Compuesto químico (SMILES) | aspirina |
| `evaluation` | Resultado de docking contra un target | docking de X contra 7E2Y |
| `target` | Blanco proteico (PDB) | 7E2Y |

| Edge (`relation`) | Significado |
|---|---|
| `docking` | evaluación ↔ target |
| `same_target` | dos moléculas evaluadas contra el mismo target |
| `similar` | dos moléculas con Tanimoto ≥ umbral |
| `modified_from` | análogo derivado de otro |

Además mantiene:
- **Fingerprints Morgan (ECFP)** serializados en pickle (`mol_fingerprints`) para similitud Tanimoto.
- **Índice FTS5** (`molgraph_fts`) para búsqueda textual por nombre/tipo/propiedades.
- Un **early-exit**: `predict_early_exit(smiles)` decide si dockear es innecesario comparando Tanimoto contra vecinos conocidos y su score promedio.

### 1.2 Schema v1 (verificado)

```sql
-- Nodos
CREATE TABLE mol_nodes (
    id              TEXT PRIMARY KEY,        -- f"mol_{smiles[:40]}"
    type            TEXT NOT NULL,           -- molecule | evaluation | target
    name            TEXT NOT NULL,
    smiles          TEXT,
    target_pdb      TEXT,
    properties_json TEXT,
    created_at      REAL NOT NULL
);

-- Edges (relaciones)
CREATE TABLE mol_edges (
    id            TEXT PRIMARY KEY,
    source_id     TEXT NOT NULL REFERENCES mol_nodes(id),
    target_id     TEXT NOT NULL REFERENCES mol_nodes(id),
    relation      TEXT NOT NULL,             -- docking | same_target | similar | modified_from
    weight        REAL DEFAULT 1.0,
    metadata_json TEXT,
    created_at    REAL NOT NULL
);

-- Fingerprints de similitud (pickle en BLOB)
CREATE TABLE mol_fingerprints (
    node_id TEXT PRIMARY KEY REFERENCES mol_nodes(id),
    fp_blob BLOB NOT NULL
);

-- Búsqueda textual (FTS5)
CREATE VIRTUAL TABLE molgraph_fts USING fts5(
    node_id UNINDEXED,
    name,
    type,
    properties_text,
    tokenize='unicode61'
);

-- Índices
CREATE INDEX idx_nodes_type     ON mol_nodes(type);
CREATE INDEX idx_nodes_smiles   ON mol_nodes(smiles);
CREATE INDEX idx_edges_source   ON mol_edges(source_id);
CREATE INDEX idx_edges_relation ON mol_edges(relation);
```

### 1.3 Los 10 riesgos verificados de la v1

La exploración SDD (`explore obs-276`) auditó `molgraph.py` línea por línea y encontró estos 10 problemas **reales**, no teóricos:

| # | Riesgo | Evidencia (código) | Impacto |
|---|---|---|---|
| 1 | Cache de fingerprints `_fp_cache` **nunca se invalida** tras inserts en runtime | l.33-60 v1 | Moléculas nuevas invisibles para similarity/early-exit hasta reiniciar |
| 2 | **Score-key partido**: writers guardan `score` (runtime), reads early-exit leen `composite→xgb_prob→0.5` | l.538 v1 | Las seed molecules rankean 0 en `get_top_molecules` |
| 3 | **FTS5 drift**: sin triggers, el path de UPDATE nunca sincroniza FTS | 5324 filas faltantes + 34 mismatches en DB live | Búsquedas con datos stale o huérfanas |
| 4 | **Hot paths O(N) de similitud**: loops Python naive por-pair Tanimoto, sin FPSim2 ni BulkTanimoto en app path | `query_molgraph_similar`, `query_scaffold_groups` | No escala; ChEMBL (2.4M) impensable |
| 5 | **LIMIT 200 hardcodeado** en SQL de `get_top_molecules` | l.366 v1 | Ignora el parámetro `limit`; nunca devuelve top-N real |
| 6 | **Contrato query_fts/chat_service roto**: FTS devuelve solo `node_id/name/type`; chat espera `smiles/properties` | `query_fts` vs `chat_service.py` | El chat recibe objetos incompletos |
| 7 | **Cero cobertura de tests** en molgraph | sin test suite | Regresiones invisibles (así nace C1) |
| 8 | **Conexión-por-llamada** `_conn()` sin pooling | l.201 | Overhead de open/close SQLite por query |
| 9 | **Inconsistencia topológica de edges**: seeds crean `docking` source=evaluation, runtime source=molecule | seeds vs runtime | Queries que asumen una topología fallan en la otra |
| 10 | **Early-exit valida SOLO scores de vecinos**, nunca el composite propio; umbral global sin calibración por familia | l.538 v1 | Decisiones con calibración frágil |

### 1.4 Por qué evolucionar (el mandato)

El objetivo era llevar MolGraph al "nivel 4" documentado: **ciclo cerrado MolGraph ↔ ML**, con early-exit inteligente, similitud a escala, substructure screening y replicación de ChEMBL/PubChem. La v1 no podía sostener eso por los 10 riesgos. La Fase A es la **fundación** para las Fases B (scale), C (ML) y D (datos).

---

## 2. Investigación de campo (por qué la GNN fracasó + qué SÍ es el techo)

> Esta sección documenta el **porqué técnico** que define la arquitectura v2. No es especulación: son resultados publicados y verificados en 2026.

### 2.1 Propagar scores por el grafo con una GNN estaba condenado

La hipótesis original de "nivel 4" era propagar labels/scores por el knowledge graph con una GNN. La literatura la refuta:

| Hallazgo | Fuente | Implicación directa |
|---|---|---|
| **La propagación GNN falla por diseño**: *Laplacian smoothing* converge las features de un cluster a su promedio → los scores de nodos vecinos se colapsan entre sí | Oono & Suzuki, ICLR 2020 (arXiv:1905.10947); Li et al., AAAI 2018 (arXiv:1801.07606) | Propagación continua en grafo = "diluido". Lo que veías era el comportamiento esperado, no un bug. |
| **Spearman mide el ranking completo; EF@1% mide el top 1%** — son métricas desacopladas | Truchon & Bayly 2007 (BEDROC) | Validar early-exit con Spearman podía esconder fracaso en el top-1%, que es justo lo que importa en drug discovery. |
| **Agregar estructura química a un KG de farmacología EMPEORA el PR-AUC** (0.5631→0.5785 sin estructura) | Abo-Dahab et al. 2026 (arXiv:2603.01537) | Evidencia directa **contra** modelar la química como grafo para predicción. |
| **Los KGEs no clusterizan entidades similares** — los embeddings no reflejan similitud química | Hubert et al. 2024 (arXiv:2310.10370) | El grafo no es el lugar donde vive la similitud. |
| **KG+GNN gana para LINK PREDICTION** (+69% en side-effects), no para propagación continua | Zitnik et al. 2018, Decagon (arXiv:1802.00543) | Si algún día se usa GNN, es para predecir links faltantes, NO scores continuos. |

### 2.2 El techo real: fingerprints + modelos clásicos + active learning

| Hallazgo | Fuente | Implicación |
|---|---|---|
| **RF/SVM + ECFP superan GNNs en 22 benchmarks ADMET de TDC**; el mejor es CatBoost + ECFP + Avalon + ErG; GNN solo como feature extra | Notwell & Wood 2023 (arXiv:2310.00174) | El ranking head debe ser **ECFP + CatBoost**, no un GNN. |
| **Early-exit moderno = pool-based Active Learning**: con 2.4% del library (100M compuestos) se encuentra el 87.9% del top-50k | Graff et al. 2021, Chem. Sci. (arXiv:2012.07127) | El early-exit v2 es un **AL cycle**: surrogate + acquisition (uncertainty ∪ diversity). |
| Con 8% de un pool de 4M se alcanza el 100% del Pareto front | Fromer et al. 2023 (arXiv:2310.10598) | Confirma el patrón Graff a escala. |

### 2.3 Decisiones de infraestructura (verificadas en 2026)

| Tema | Hallazgo | Decisión |
|---|---|---|
| **Graph DB** (Neo4j) | Kuzu **ARCHIVED** (Oct 10 2025, GitHub read-only); Neo4j = **GPLv3 copyleft**; RDF = overkill | **STAY on SQLite** — Fase A migra sobre el mismo motor |
| **Similitud a escala** | FPSim2 **ACTIVE**, corre ChEMBL/SureChEMBL en producción (GitHub); FAISS usa L2/cosine/Hamming ≠ **Tanimoto** | **FPSim2** en Fase B (índice .h5, Tanimoto sublinear) |
| **Substructure screen** | RDKit `SubstructLibrary` + verificación VF2 | Fase B: screen-then-verify |
| **Replicación de datos** | ChEMBL fingerprints públicos (chembl_37.fps.gz 168MB / .h5 314MB), PubChem identifiers | Fase D |

> **Conclusión rectora**: el score NO se propaga por el grafo. El grafo es un **índice relacional** (¿quién se evaluó contra qué target?); la similitud química vive en los **fingerprints**; la predicción vive en **modelos sobre fingerprints**; y el ahorro de cómputo vive en **active learning pool-based**.

---

## 3. La arquitectura v2 (evaluated vs catalog + decisiones con evidencia)

### 3.1 El modelo de nodos: evaluated vs catalog

La decisión arquitectónica más importante de la v2 es separar dos clases de nodos `molecule`:

| Atributo | `evaluated` | `catalog` |
|---|---|---|
| `is_catalog` | `0` | `1` |
| Qué es | Moléculas evaluadas en tu pipeline (docking/ML propio) | Moléculas de **conocimiento** (drogas/PubChem), jamás evaluadas |
| Porta `score` canónico | ✅ Sí | ❌ **Nunca** (MG-A2) |
| Participa en early-exit | ✅ Sí | ❌ **Excluida** (MG-A6) |
| Participa en ranking | ✅ Sí | ❌ Excluida por default (MG-A8) |
| Buscable por FTS (nombre/aliases) | ✅ | ✅ |
| Aporta fingerprint de similitud | ✅ | ✅ |

**Por qué es crítico**: si un nodo *catalog* entrara al early-exit sin score, se mezclaría como `0.5` silencioso (el bug de la v1) y contaminaría el ranking con moléculas que jamás se evaluaron. El guard `is_catalog=0` **protege la garantía de 0% falsos negativos** documentada en `plan_early_exit.md`.

**Precedencia de evidencia**: si una molécula ya existe como *evaluated* y luego se agrega como *catalog* (mismo `node_id`), el catálogo **appendea** `common_name` + `aliases` **sin tocar** `is_catalog` ni `score`. La evidencia evaluada manda.

### 3.2 El score canónico único: `score` ∈ [0,100]

La v1 tenía **3 keys de score legacy** con escalas distintas. La v2 las unifica:

```text
_SCORE_KEYS = ("composite", "xgb_prob", "vina_score", "score")
Precedencia (primero no-null gana): composite → xgb_prob → vina_score → score
```

**Evidencia de escala unificada**:

| Origen | Fórmula legacy | Escala | Conversión a canónico |
|---|---|---|---|
| Runtime | `total_score = clamp_score(...)` | [0,100] | ya canónico (`scoring/normalizer.py`) |
| Seed composite | `composite = prob*0.70 + vina_norm*0.30` (`stacking_ef.py:65-72`) | [0,1] | `×100` |
| Seed xgb_prob | probabilidad [0,1] | [0,1] | `×100` |
| Seed vina_score | afinidad kcal/mol | sin tope | `min(1, |v|/12) × 100` |

```python
def _legacy_to_100(key, value):
    if key == "vina_score":
        return round(min(1.0, abs(value) / 12.0) * 100.0, 2)
    return round(float(value) * 100.0, 2)
```

**Validación empírica** (DB live, mediana tras migración): runtime mediana ≈ **51.30**, seed composite×100 mediana ≈ **50.30** → escalas compatibles. El umbral de early-exit pasa de `0.45` → **`45.0`**.

Las keys legacy se **preservan read-only** en `properties_json` para auditoría; `score` es la única fuente de verdad para scoring.

### 3.3 Los 11 requisitos de spec (MG-A1..A8 + MG-C1..C3)

| Req | Descripción | Estatus |
|---|---|---|
| MG-A1 | Migración de schema v1→v2 idempotente + backup | ✅ PASS |
| MG-A2 | Semántica `is_catalog` (catalog nunca recibe score) | ✅ PASS |
| MG-A3 | Invalidación de cache de fingerprints en runtime | ✅ PASS |
| MG-A4 | Score-key canónico único (`score`, escala [0,100]) | ✅ PASS |
| MG-A5 | Consistencia FTS5 vía triggers (0 drift) | ✅ PASS |
| MG-A6 | Early-exit con guard `is_catalog=0` y threshold 45.0 | ✅ PASS |
| MG-A7 | `add_catalog_molecule(smiles, common_name, aliases, properties)` | ✅ PASS |
| MG-A8 | Ranking excluye catalog por default (`include_catalog=False`) | ✅ PASS |
| MG-C1 | Suite de tests (0% → 56% coverage) | ✅ PASS |
| MG-C2 | Lockstep: backend y frontend resources byte-idénticos | ✅ PASS |
| MG-C3 | Backward compatibility (v1 data se lee y migra sin pérdida) | ✅ PASS |

---

## 4. Proceso SDD (Spec-Driven Development)

La Fase A se ejecutó con el pipeline SDD del proyecto (modo **engram**, sin `openspec/`). Cada artefacto es una observación persistente trazable:

| Fase del pipeline | Estado | Artefacto engram |
|---|---|---|
| explore (mapa de código + riesgos) | ✅ COMPLETA | `#276` |
| proposal (intent + scope) | ✅ COMPLETA | `#277` |
| spec (delta MG-A1..A8, MG-C1..C3) | ✅ COMPLETA | `#279` |
| design (delta, decisiones con evidencia) | ✅ COMPLETA | `#281` |
| tasks (breakdown 40/40) | ✅ COMPLETA | `#282` |
| apply (implementación) | ✅ COMPLETA | `#283` |
| verify → **re-verify** (C1 detectado y resuelto) | ✅ PASS (0 CRITICAL, 0 WARNING) | `#288`, `#286` |
| **archive** (cierre + roadmap) | ✅ **COMPLETA** | `#291`, `#278` |

**Lección clave del proceso**: el verify-before-archive **atrapó el bug C1** que habría matado el early-exit en producción y quedado congelado en el archive. El gate de verificación independiente no es burocracia: es donde se ganó la Fase A.

---

## 5. Implementación Fase A

### 5.1 Schema v2 y migración (`_migrate_schema`)

```sql
-- Columnas nuevas en mol_nodes (v2)
is_catalog   INTEGER NOT NULL DEFAULT 0,
common_name  TEXT NULL,
aliases_json TEXT NULL
```

```text
PRAGMA user_version: 0 → 2   (idempotente: >=2 → no-op)
```

| Paso | Detalle |
|---|---|
| 1. Check | `user_version >= 2` → return (no-op) |
| 2. Check columnas | `is_catalog` ya existe → solo setea `user_version=2` (DB fresca) |
| 3. **Backup** | `wal_checkpoint(FULL)` + `shutil.copy2` → `molgraph.db.bak_v0_<ts>` (rollback-safe) |
| 4. ALTER | 3× `ALTER TABLE mol_nodes ADD COLUMN` |
| 5. **Backfill FTS5** | filas faltantes (INSERT SELECT) + mismatches (UPDATE con `COALESCE(substr(props,1,1000),'')`) |
| 6. user_version | `PRAGMA user_version = 2` |

`init_graph()` **siempre** corre `_migrate_schema` (fresh y existente). La ruta fresh crea directamente las columnas v2 en el `CREATE TABLE`.

**Backups reales generados**: `molgraph.db.bak_v0_20260801_200445` (pre-ALTER) y `molgraph.db.bak_v2_prescore_20260801_202323`.

### 5.2 Backfill de scores canónicos (`_backfill_canonical_scores`)

```text
SELECT id, properties_json FROM mol_nodes
WHERE type='molecule' AND is_catalog=0 AND properties_json IS NOT NULL
```

| Regla | Comportamiento |
|---|---|
| Ya tiene `score` | **no-op** (idempotente) |
| Tiene `composite`/`xgb_prob`/`vina_score` | se normaliza a `score` [0,100] |
| `properties_json` vacío (`{}`, sin keys legacy) | **queda sin score** — correcto (MG-A4: nodo sin score nunca se mezcla como 0.5) |
| Catálogo (`is_catalog=1`) | **nunca** recibe score (MG-A2) |

### 5.3 Triggers FTS5 (MG-A5)

Se elimina el sync manual app-level; los triggers garantizan consistencia total:

```sql
-- AFTER INSERT: indexa el nodo nuevo
CREATE TRIGGER mol_fts_ai AFTER INSERT ON mol_nodes BEGIN
    INSERT INTO molgraph_fts(node_id,name,type,properties_text)
    VALUES (NEW.id, NEW.name, NEW.type, COALESCE(substr(NEW.properties_json,1,1000),''));
END;

-- AFTER UPDATE (name/type/properties_json): resincroniza
CREATE TRIGGER mol_fts_au AFTER UPDATE OF name,type,properties_json ON mol_nodes BEGIN
    UPDATE molgraph_fts SET
        name=NEW.name, type=NEW.type,
        properties_text=COALESCE(substr(NEW.properties_json,1,1000),'')
    WHERE node_id=NEW.id;
END;

-- AFTER DELETE: elimina la fila FTS
CREATE TRIGGER mol_fts_ad AFTER DELETE ON mol_nodes BEGIN
    DELETE FROM molgraph_fts WHERE node_id=OLD.id;
END;
```

`COALESCE(substr(properties_json,1,1000),'')` es **NULL-safe** y respeta la regla de truncación de 1000 chars heredada de v1.

### 5.4 Cache: invalidación en runtime (MG-A3)

```python
def _invalidate_fp_cache():
    global _fp_cache
    with _fp_cache_lock:
        _fp_cache = None
```

- Se llama **post-commit** en todos los writers (`add_molecule_node`, `add_catalog_molecule`, evaluación runtime).
- El reload es **lazy**: el próximo `_load_fingerprint_cache()` repuebla desde DB.
- Resultado: una molécula nueva es visible para similarity/early-exit **sin reiniciar el proceso** (riesgo #1 de v1 eliminado).

### 5.5 `add_catalog_molecule` (MG-A7)

```python
def add_catalog_molecule(
    smiles: str,
    common_name: str,
    aliases: list[str] | None = None,
    properties: dict[str, Any] | None = None,
) -> str:
    # node_id = f"mol_{smiles[:40]}"  (mismo scheme que evaluated)
```

| Rama | Comportamiento |
|---|---|
| Nodo ya existe | appendea `common_name` + `aliases` SIN tocar `is_catalog` ni `score` (la evidencia evaluada manda) |
| Nodo nuevo | INSERT con `is_catalog=1`; properties **nunca** exponen la key `score` (`cat_props.pop("score", None)`) |

`common_name` + `aliases` se guardan **dentro** de `properties_json` (para que el trigger FTS5 los indexe y `query_fts` los resuelva) **y** en las columnas `common_name`/`aliases_json` (para SQL/admin).

### 5.6 Early-exit v2 (`predict_early_exit`)

```sql
SELECT n.id, n.properties_json FROM mol_nodes n
WHERE n.type = 'molecule' AND n.is_catalog = 0
```

| Elemento | v1 | v2 |
|---|---|---|
| Filtro catálogo | — | ✅ `is_catalog=0` (MG-A6) |
| Score leído | `composite→xgb_prob→0.5` | **solo `score`** (MG-A4) |
| Nodo sin score | se mezclaba como 0.5 | **excluido del mean** (nunca 0.5 silencioso) |
| Umbral | `0.45` (escala [0,1]) | **`45.0`** (escala [0,100]) |

Decisión final: `skip=True` solo si `mean < threshold AND std < 0.05` (bajo score + vecinos consistentes); si hay varianza (`std > 0.1`) → `skip=False` (`reason="variance"`, se dockeya).

### 5.7 Ranking top-N global real (`get_top_molecules`)

Fix de W-NEW-1 (riesgo #5 de v1): el LIMIT deja el SQL, el sort pasa a Python sobre **todos** los candidatos y el slice recorta al final:

```python
rows = c.execute(
    "SELECT name, smiles, properties_json, type FROM mol_nodes "
    "WHERE type='molecule' AND (is_catalog=0 OR ?)",
    (1 if include_catalog else 0,),
).fetchall()
# ...sort Python por score (desc) o affinity (asc)...
return results[:limit]
```

| Métrica | Antes (v1) | Después (v2) |
|---|---|---|
| Top-5 live | `[62, 55, None, None, None]` | `[74.67, 66.8, 66.48, 65.29, 64.4]` |

Con 2633 moléculas, traer todo + sort Python es correcto y barato. El `LIMIT 200` hardcodeado quedó superseded: ya no hay cap.

---

## 6. El bug C1 (transparencia)

> Esta sección se documenta por honestidad técnica: muestra **cómo** un diseño aparentemente correcto casi mata el early-exit en producción, y **cómo** el proceso de verificación lo salvó.

### 6.1 Timeline

| Paso | Qué pasó |
|---|---|
| 1. Apply | Migración in-place: `ALTER` + backfill FTS5 + `user_version=2`. El design decía "regenerar seeds con normalizer" |
| 2. Verificación | `_backfill_canonical_scores` **no existía**. La normalización se agregó a `poblar_molgraph.py`, que **nunca toca los datos ya existentes** |
| 3. Resultado | Solo **5/2633** moléculas live tenían `score` canónico. Las 2628 restantes seguían con keys legacy |
| 4. Impacto | `predict_early_exit` en sample de 300: **cold_start 300/300** (v1: 87/300 con decisiones reales). Early-exit **funcionalmente muerto** sobre datos existentes |
| 5. Root cause | "Migración in-place = schema + datos, no solo DDL". El ALTER agrega columnas; los **datos** necesitan backfill explícito |
| 6. Fix | `_backfill_canonical_scores(c)` idempotente (MG-A4) + tests **fail-before / pass-after** (TDD) |

### 6.2 El fix

```text
_before(): predict_early_exit(sample) → cold_start 300/300   (FAIL → red)
_after() : backfill corre → 92 cold_start + 208 variance     (PASS → green)
```

Resultados post-fix (DB live):

| Métrica | Antes | Después |
|---|---|---|
| Moléculas con score canónico | 5/2633 | **2628/2633 (99.8%)** |
| Legacy-sin-score | 2628 | **0** |
| Mediana de score | — | **50.3** [44.07–74.67] |
| Out-of-range [0,100] | — | **0** |
| `predict_early_exit` (sample 300) | cold_start 300/300 | **92 cold_start + 208 variance** |

### 6.3 Validación reescrita

`validate_early_exit.py` se reescribió para llamar al **`predict_early_exit` real** (antes simulaba la lógica): **7642 moléculas × 3 targets → 0% falsos negativos**, ~95s. El screening `--screening` se hizo ASCII-safe (fix S-NEW-1, `UnicodeEncodeError` cp1252 con `→`).

> **Lección durable**: un score-key partido no se ve en el DDL ni en el schema — solo se ve en la **distribución de decisiones**. Por eso MG-A4 y el backfill son idempotentes y por eso C1 fue el finding que justificó el re-verify antes de archive.

---

## 7. Resultados verificados

> Todos los números de esta sección fueron **re-verificados independientemente** en 2026-08-01/02 (queries sqlite3 directas + pytest + SHA256). No son claims: son mediciones.

### 7.1 Tests

```text
$ python -m pytest tests/test_molgraph_migration.py tests/test_molgraph_scores.py \
       tests/test_molgraph_catalog.py tests/test_molgraph_fts.py tests/test_molgraph_cache.py -q
.....................................  [100%]
37 passed in 2.05s
```

| Suite | Tests | Cubre |
|---|---|---|
| `test_molgraph_migration.py` | 37 total (comparten) | migración v1→v2, idempotencia, backup, C1 fail-before/pass-after |
| `test_molgraph_scores.py` | | `_normalize_properties`, escala [0,100], precedencia, out-of-range |
| `test_molgraph_catalog.py` | | A2/A7/A8: catalog nunca scored, exclusión ranking/early-exit |
| `test_molgraph_fts.py` | | A5: triggers INSERT/UPDATE/DELETE, 0 orphans/ghosts/mismatches |
| `test_molgraph_cache.py` | | A3: invalidación post-commit, reload lazy |

Cobertura en `services/ai/molgraph.py`: **0% → 56%**.

### 7.2 Validación de early-exit

| Métrica | Valor |
|---|---|
| Moléculas validadas | **7642** (`validate_early_exit.py --all`) |
| Falsos negativos | **0%** |
| Skip (ahorro docking) | 0.0% |
| Cold start | **22.6%** |

### 7.3 DB live (`C:\Users\Johan Amezcua\MolDesign\data\molgraph.db`)

| Métrica | Valor verificado |
|---|---|
| `PRAGMA user_version` | **2** |
| Nodos totales | **7996** (2633 molecule / 5358 evaluation / 5 target) |
| `is_catalog=1` | **0** (catálogo aún vacío — habilitado por A7) |
| Moléculas con `score` canónico | **2628/2633** |
| Moléculas bare (sin score) | **5** (aspirina/ibuprofeno demo — correcto, MG-A4) |
| Edges | **74580** |
| Fingerprints | **2633** |
| FTS5 filas | **7996** |
| FTS orphans | **0** (era 5324 faltantes + 34 mismatches en v1) |
| FTS ghosts / name-mismatch / props-mismatch | **0 / 0 / 0** |
| Scores out-of-range [0,100] | **0** |
| Triggers activos | `mol_fts_ai`, `mol_fts_au`, `mol_fts_ad` |

### 7.4 Seed DBs (ambas)

| Métrica | `data/molgraph_seed.db` | `resources/data/molgraph_seed.db` |
|---|---|---|
| `user_version` | 2 | 2 |
| Nodos | **7980** | 7980 |
| Moléculas | **2630** | — |
| Moléculas scored | **2625/2630** | — |
| `is_catalog=1` | 0 | 0 |

### 7.5 Lockstep SHA256 (MG-C2)

Archivo byte-idéntico backend ↔ `frontend/src-tauri/resources/backend/`:

| Archivo | SHA256 |
|---|---|
| `services/ai/molgraph.py` | `27B065F0745B6C6BE88D7F55ED2B2626EC480E5D7DFB3144968078115C620C1C` |
| `services/ai/tools/molgraph_tool.py` | `2B1423753D3D32D9A9205F05B3D3226C3BE89CC897FF7EBDF002070DE0BEA408` |
| `services/ai/chat_service.py` | `4958343B7D2229B0867CBEEFEA3BF8E8BA064EF7063BF0FEA612F8524F6B153E` |

### 7.6 Conformidad de spec

**11/11 requisitos PASS** (MG-A1..A8 + MG-C1..C3).

### 7.7 Archivos de la Fase A

| Archivo | Rol |
|---|---|
| `backend/services/ai/molgraph.py` (~950 líneas) | Core: schema v2, migración, backfill, cache, catálogo, early-exit, ranking |
| `backend/services/ai/tools/molgraph_tool.py` | Tools de IA sobre MolGraph (similar/scaffolds) |
| `scripts/poblar_molgraph.py` | Seed builder (normalizer aplicado a seeds) |
| `scripts/migrate_seed_db.py` | **NUEVO**: migra seed DBs → v2 |
| `scripts/validate_early_exit.py` | **Reescrito**: valida contra `predict_early_exit` real, `--screening` ASCII-safe |
| `backend/tests/test_molgraph_{migration,scores,catalog,fts,cache}.py` | **NUEVOS** (5 suites) |
| `backend/tests/conftest.py` | Extendido: fixture `_fresh_db` |

---

## 8. Datos para entender el sistema

### 8.1 Schema v2 completo (state actual)

```sql
CREATE TABLE mol_nodes (
    id              TEXT PRIMARY KEY,          -- mol_<smiles[:40]>
    type            TEXT NOT NULL,             -- molecule | evaluation | target
    name            TEXT NOT NULL,
    smiles          TEXT,
    target_pdb      TEXT,
    properties_json TEXT,                      -- contiene 'score' canónico [0,100]
    created_at      REAL NOT NULL,
    is_catalog      INTEGER NOT NULL DEFAULT 0, -- 0=evaluated | 1=catalog (v2)
    common_name     TEXT NULL,                 -- v2
    aliases_json    TEXT NULL                  -- v2
);

CREATE TABLE mol_edges (
    id            TEXT PRIMARY KEY,
    source_id     TEXT NOT NULL REFERENCES mol_nodes(id),
    target_id     TEXT NOT NULL REFERENCES mol_nodes(id),
    relation      TEXT NOT NULL,
    weight        REAL DEFAULT 1.0,
    metadata_json TEXT,
    created_at    REAL NOT NULL
);

CREATE TABLE mol_fingerprints (
    node_id TEXT PRIMARY KEY REFERENCES mol_nodes(id),
    fp_blob BLOB NOT NULL
);

CREATE VIRTUAL TABLE molgraph_fts USING fts5(
    node_id UNINDEXED, name, type, properties_text, tokenize='unicode61'
);

-- Índices: idx_nodes_type, idx_nodes_smiles, idx_edges_source, idx_edges_relation
-- Triggers: mol_fts_ai / mol_fts_au / mol_fts_ad
-- PRAGMA user_version = 2
```

### 8.2 Ejemplos de `properties_json`

**Evaluada con score canónico (runtime)**:

```json
{
  "score": 61.24,
  "affinity_kcal": -8.1,
  "log_p": 2.3,
  "molecular_weight": 180.16
}
```

**Seed legacy post-backfill** (keys legacy preservadas read-only + score canónico):

```json
{
  "composite": 0.62,
  "xgb_prob": 0.58,
  "vina_score": -9.1,
  "score": 62.0,
  "common_name": "aspirina",
  "aliases": ["ácido acetilsalicílico", "ASA"]
}
```

**Catálogo puro** (is_catalog=1, SIN `score`):

```json
{
  "common_name": "aspirina",
  "aliases": ["ácido acetilsalicílico"],
  "pubchem_cid": 2244
}
```

### 8.3 Diagrama del early-exit v2

```text
                 ┌──────────────────────────────────────────────┐
 SMILES ──────►  │ predict_early_exit(smiles, min_neighbors=3,  │
                 │                min_similarity=0.6,            │
                 │                score_threshold=45.0)          │
                 └──────────────────────┬───────────────────────┘
                                        │
                         Tanimoto vs vecinos (is_catalog=0)
                                        │
        ┌───────────────────────┬───────┴────────┬──────────────────────┐
        ▼                       ▼                ▼                       ▼
 n < min_neighbors        mean<thresh        std > 0.1              else
        │                AND std<0.05           │                       │
        ▼                       ▼               ▼                       ▼
 "cold_start"              skip=True      "variance"              "ok_<mean>"
 skip=False                ahorrás        skip=False              skip=False
 dockeás todo            el docking       dockeás (dudosa)        dockeás
```

Decisión: **nodo sin `score` se excluye del mean** (nunca 0.5 silencioso); **catálogo jamás entra** (is_catalog=0).

### 8.4 Comandos útiles

```powershell
# Verificar versión de schema y estado
python -c "import sqlite3; db=sqlite3.connect(r'$HOME\MolDesign\data\molgraph.db'); print('v:', db.execute('PRAGMA user_version').fetchone()[0]); print('nodes:', db.execute('SELECT COUNT(*) FROM mol_nodes').fetchone()[0]); db.close()"

# Correr la suite de Fase A
cd D:\moldesign-app\backend
python -m pytest tests/test_molgraph_migration.py tests/test_molgraph_scores.py tests/test_molgraph_catalog.py tests/test_molgraph_fts.py tests/test_molgraph_cache.py -q

# Validar early-exit (todos los targets, 0% falsos negativos)
python scripts/validate_early_exit.py --all

# Verificar lockstep (backend vs frontend resources)
certutil -hashfile backend\services\ai\molgraph.py SHA256
certutil -hashfile frontend\src-tauri\resources\backend\services\ai\molgraph.py SHA256
```

---

## 9. Roadmap futuro

### 9.1 Fase B — Escala (SIGUIENTE, lista para arrancar)

| Ítem | Detalle |
|---|---|
| **FPSim2 .h5** | Tanimoto **sublinear** (bounds Swamidass-Baldi); ChEMBL 37 en .h5 = **314MB** para 2.4M compuestos |
| **Substructure screen-then-verify** | RDKit `SubstructLibrary` + verificación VF2 |
| **Fix contrato `query_fts`** | devolver `smiles`/`properties` para `chat_service.py` |
| **Pooling de conexiones** | reemplazar `_conn()` connection-per-call (riesgo #8 de v1) |
| **Sugerencias S1–S4** | ver 9.3 |

Nombre de change sugerido: **`molgraph-v2-evolution-phase-b`**.

### 9.2 Fases C y D

| Fase | Contenido |
|---|---|
| **C — ML** | Early-exit **pool-based Active Learning** (surrogate + acquisition uncertainty∪diversity, patrón Graff/Fromer); ranking head **ECFP + CatBoost**; métricas **EF@1% / BEDROC** con **scaffold-split** (NO Spearman); calibración de `score_threshold` por familia |
| **D — Datos** | Replicación **ChEMBL fingerprints** (`chembl_37.fps.gz` **168MB** / .h5 314MB); **PubChem** identifiers por intersección de CID; enrichment masivo vía `add_catalog_molecule` (A7 ya lo habilita) |

### 9.3 Sugerencias heredadas (S1–S4, de obs-288)

| # | Sugerencia | Fase |
|---|---|---|
| S1 | `pyproject.toml` sin `pythonpath=["."]` → añadirlo | B |
| S2 | `common_name`/`aliases` guardados **al final** de `properties_json` → riesgo de truncamiento FTS (1000 chars). Moverlos al inicio | B/D |
| S3 | `add_evaluation_node` recibe `**norm_props` → footgun: puede sobrescribir el argumento `score` | B |
| S4 | Typo `"alqueno"` → `"alcano"` en `test_molgraph_catalog.py:26` | B |

---

## 10. Referencias

### 10.1 Papers (con arXiv IDs)

| Tema | Fuente |
|---|---|
| Colapso por Laplacian smoothing | Oono & Suzuki, **ICLR 2020** · arXiv:1905.10947 |
| Laplacian smoothing en GNNs | Li et al., **AAAI 2018** · arXiv:1801.07606 |
| Métricas top-weighted (EF/BEDROC) | Truchon & Bayly, **2007** |
| Estructura química en KG de farmacología HURT PR-AUC | Abo-Dahab et al., **2026** · arXiv:2603.01537 |
| KGEs no clusterizan entidades similares | Hubert et al., **2024** · arXiv:2310.10370 |
| KG+GNN para link prediction (Decagon) | Zitnik et al., **2018** · arXiv:1802.00543 |
| RF/SVM+ECFP > GNNs en TDC ADMET | Notwell & Wood, **2023** · arXiv:2310.00174 |
| Pool-based AL: 87.9% del top-50k en 2.4% | Graff et al., **2021** · Chem. Sci. · arXiv:2012.07127 |
| AL: 100% Pareto front en 8% del pool | Fromer et al., **2023** · arXiv:2310.10598 |

### 10.2 Artefactos engram (proyecto `molecular-design`)

| Artefacto | Topic key | Obs ID |
|---|---|---|
| Exploración (mapa + 10 riesgos) | — | `#276` |
| Change proposal | — | `#277` |
| DAG state (ARCHIVED) | `sdd/molgraph-v2-evolution/state` | `#278` |
| Spec (MG-A1..A8, MG-C1..C3) | — | `#279` |
| Design | — | `#281` |
| Tasks (40/40) | — | `#282` |
| Apply / fixes | — | `#283` |
| Verify report (final PASS) | — | `#286` |
| Re-verify (C1/W1/W2 + W-NEW-1/S-NEW-1) | — | `#288` |
| **Archive report** | `sdd/molgraph-v2-evolution/archive-report` | `#291` |
| Conocimiento de arquitectura (main spec) | `architecture/molgraph-v2-archived` | — |

---

> **Estado final**: Fase A fundación completa, verificada (0 CRITICAL, 0 WARNING) y **ARCHIVED**. La siguiente iteración es `molgraph-v2-evolution-phase-b` (FPSim2 + substructure + contrato query_fts + pooling).
