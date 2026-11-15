# Lotes frente a Evaluación: qué heredó la ciencia de 1.0.4 y qué falta

| Campo | Registro |
|---|---|
| Fecha | 2026-11-15 |
| Código de referencia | `ffddd7e9`, rama `codex/release-hygiene`, sin empujar |
| Origen | Dirección del propietario (2026-11-15): «batch está muy por detrás de la ciencia que estamos haciendo en Evaluación; hay que pasarle lo que ya confirmamos» |
| Medido | Lectura de `backend/api/routers/batch.py`, `backend/services/cohort/*`, `frontend/app/evaluation/batch/page.tsx` y `frontend/lib/cohorts.ts` |

## Lo primero: «Lotes» son dos sistemas

La pantalla **Lotes** (`/evaluation/batch`) **no usa** el endpoint `/evaluation/batch`. Es el sistema de **cohortes**; el Batch histórico sigue publicado «para no
romper a quien lo use» y la interfaz no lo toca (`frontend/lib/cohorts.ts:8`, cabecera de la página).

| | **Cohortes** (lo que ve la persona) | **Batch histórico** (`batch.py`) |
|---|---|---|
| Quién lo llama | La interfaz de Lotes | Nadie en la interfaz; sólo clientes externos de la API |
| Motor científico | `run_pipeline` con cinco etapas (validación, propiedades, filtro SA, conformador, docking); excluye GNN, OpenMM, selectividad y ADMET-AI por diseño | `submit_recorded_evaluation`: la misma ruta durable que una evaluación individual |
| Orden y EF/AUC | **Afinidad de Vina** (`evidence.py: sort_by_observed_affinity`, `build_labeled_metrics`) | Hasta hoy: `total_score` (EF/AUC) y, desde el 2026-11-15 por la tanda anterior, Vina (orden de la exportación) |
| `total_score` | No aparece en ninguna superficie de cohorte | Columna `TotalScore` en CSV y XLSX, sin rótulo de «heredado» |
| Evidencia por fila | `structural_evidence` (PoseBusters), `pose_selection`, semilla efectiva y observada | ~25 campos copiados del resultado |

**Consecuencia:** lo que se creía atrasado en Lotes —que el ranking, EF y AUC usaran el índice compuesto— **ya estaba resuelto en la pantalla viva** y sólo seguía así
en el endpoint histórico. Eso es lo que se corrigió hoy.

## Hecho hoy en el Batch histórico

- **EF/AUC por afinidad de Vina**, una sola base para todos los lotes (antes `total_score`, y `affinity_score` si los pesos del apilado diferían entre filas).
  `score_basis` pasa a ser siempre `affinity_kcal`. Una afinidad ausente o no finita cuenta como el peor score, igual que antes (`backend/api/routers/batch.py`,
  `BASE_DE_EF_AUC`; pruebas en `backend/tests/test_fase3_enriquecimiento.py`, incluida una que **invierte** el índice frente a Vina y comprueba que manda Vina).
- **`ranking_policy`** dice ahora `por_diana_y_afinidad_de_vina`; decía `por_diana_y_componentes_completos_primero`, que describía el orden por índice.
- **Se conserva** `TotalScore` en la exportación y `ranking_mixto` en la respuesta (ya no gobiernan nada; dicen si las filas mezclan pesos, que es lo que vuelve
  incomparable esa columna). Cambiar los nombres de columna rompería a quien parsee el CSV.

## Lo que falta en Cohortes frente a Evaluación (medido, sin implementar)

| # | Falta | Qué hace Evaluación | Estado en cohortes | Coste y riesgo |
|---|---|---|---|---|
| 1 | **Etiqueta del catálogo (Demostración o Verificado) en el dossier de la cohorte** | Viaja a la portada del dossier y a su PDF, en los dos idiomas | La pantalla la pinta (`InsigniaDelCatalogo`, líneas 682, 976 y 1164 de `page.tsx`); el paquete de dossier de cohorte (`services/cohort/dossier.py`) **no la menciona** | Bajo: reusar `services/targets/seccion_catalogo.py`. Cambia el contenido de los paquetes nuevos; las cohortes ya guardadas no se reescriben |
| 2 | **Declaración de la especie del ligando por fila** (hoy «Especie acoplada: registrada/revisar») | `motivos_de_revision` de `chem/especie_en_revision.py` marca revisión en el dossier, Preparación y el panel 3D | Sólo declara el *modo* de tautómero de la cohorte (`schemas.modo_tautomero_de`); ninguna fila dice qué especie se acopló ni si merece revisión | Medio: una columna y un conteo en el dossier. **Depende de D-04**: con él, las cuatro clases nuevas aparecen sin más código ([plan](plan-d04-especie-en-revision-2026-11-15.md), fase 5) |
| 3 | **Estado de Preparación del receptor** (huecos, metales, cofactores, aguas, confianza de un modelo predicho y su fuente declarada) | La pestaña Preparación y el dossier lo calculan por corrida | El dossier de cohorte guarda PDB, cadena, SHA-256 y tamaño del receptor preparado, nada de lo que la preparación midió | Alto: es lo que más se acerca a «ciencia de Evaluación»; hay que decidir qué subconjunto se congela con la cohorte y cómo entra en su huella |
| 4 | **Rótulo `TotalScore` como «índice compuesto heredado»** en la exportación histórica | Evaluación lo rotula así desde 1.0.4 (SUP-02) | CSV/XLSX del Batch histórico llevan el nombre pelado | Bajo, pero cambia un contrato de exportación que nadie en la interfaz usa: decisión del propietario |

Fuera de alcance por diseño: **selectividad, ADMET, GNN y XGBoost** no pasan a cohortes. El contrato de cohorte es «el docking terminó», no un veredicto, y esas capas
son el tipo de lectura que una cohorte comparativa no debe mezclar (`services/cohort/execution.py`, cabecera).

## Qué decide el propietario

1. **¿Se retira el Batch histórico o se congela?** Mientras exista, cada mejora de ciencia hay que repetirla en dos sitios. No hay ningún llamador en la interfaz;
   desconozco clientes externos (no hay usuarios externos según AGENTS.md), así que retirarlo es una decisión de producto y no una limpieza.
2. ¿Se hacen los puntos 1 y 2 de la tabla en 1.0.4? Son baratos y cierran la distancia más visible; el 3 es una tarea propia.
3. ¿Se rotula `TotalScore` en el Batch histórico (punto 4)?
