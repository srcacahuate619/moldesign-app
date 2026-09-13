> **Documento histórico — julio de 2026.** Escrito para el árbol anterior del
> proyecto (`moldesign-app`) y traído aquí por trazabilidad. Puede describir un
> estado que ya no es el vigente: la versión 1.0.0 es una aplicación de
> escritorio y no tiene componente en la nube. No se ha reescrito su contenido.

# Batch Virtual Screening — v1.5

> **Subi un archivo con moleculas, evalua contra multiples targets, y obten resultados rankeados con metricas EF.**

---

## Endpoint

```
POST /evaluation/batch?target_pdb_id=ALL&num_workers=3&early_exit=true
```

---

## Features

### Multi-Target

El parametro `target_pdb_id=ALL` corre contra todos los targets registrados en la DB (386 en v1.5). El dropdown del frontend incluye:
- **ALL** — todos los targets precurados
- **Buscar Target** — modal con 4 tabs (oficiales, custom, comunidad, RCSB search)
- **PDB ID directo** — input para escribir cualquier codigo de 4 caracteres

### Early Exit (pre-filtro MolGraph)

Toggle ON por defecto. Antes de dockear cada molecula, consulta el knowledge graph MolGraph:
- Si hay moleculas similares con scores bajos → predice inactividad → salta el docking
- Ahorra ~40% de CPU en batches grandes (>100 moleculas)
- Moleculas saltadas aparecen como `early_exit` en resultados

### EF Metrics (si el upload tiene labels)

Si el archivo CSV/Excel tiene una columna `active` (1/0), al terminar el batch se computa:
- **EF@1%** — Enrichment Factor al 1%
- **EF@5%** — Enrichment Factor al 5%
- **EF@10%** — Enrichment Factor al 10%
- **ROC-AUC** — Area bajo la curva ROC

Se muestran en una tarjeta cyan en los resultados.

### Concurrencia

`asyncio.Semaphore(num_workers)` — controla cuantos dockings corren en paralelo. Sin threads, compatible con Windows ProactorEventLoop.

---

## Formatos Soportados

| Formato | Extension | Columnas |
|---------|-----------|----------|
| CSV | `.csv` | `smiles`, `name` (opcional), `active` (opcional) |
| Excel | `.xlsx`, `.xls` | mismas columnas |
| SDF | `.sdf` | SMILES + nombre extraidos automaticamente |
| SMILES | `.smi`, `.txt` | un SMILES por linea, nombre y label opcionales |

---

## Export

- **Excel** (`.xlsx`): 22 columnas con formato (PAINS en rojo, header styling)
- **CSV**: 18 columnas

---

## Flujo Completo

```
1. Usuario sube archivo (max 500 moleculas)
2. Backend valida SMILES, desaliniza, canonicaliza
3. Si target no existe en DB → auto-ingesta (download PDB + discover pocket + prepare)
4. Early Exit: MolGraph pre-filtra inactivos obvios
5. asyncio.Semaphore controla concurrencia de dockings
6. Cada molecula: conformer → Vina docking → ML rescoring → scoring
7. Resultados parciales disponibles via polling (cada 2s)
8. Si hay labels active/inactive → computo de EF metrics
9. Descarga Excel/CSV
```

---

## Archivos

| Archivo | Rol |
|---------|-----|
| `backend/api/routers/batch.py` | Endpoints REST + procesamiento background |
| `frontend/app/evaluation/batch/page.tsx` | UI de batch screening |
| `frontend/components/interfaces/pro/TargetSelectorModal.tsx` | Selector de targets |
| `backend/services/docking/queue_handler.py` | Auto-ingesta de targets desconocidos |
| `backend/services/ai/molgraph.py` | Early exit via fingerprint cache |
