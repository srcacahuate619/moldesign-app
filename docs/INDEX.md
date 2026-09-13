# Índice Documental — MolDesign (`moldesign-build`)

> **Propósito**: identificar la documentación normativa sin contrastar decenas de
> archivos manualmente. Cada entrada tiene estado, fecha de verificación y código
> asociado. Creado por hallazgo F-06 (auditoría 2026-08-09).
>
> **Estados**: 🟢 Vigente (normativo hoy) · 🔵 Plan (intención futura) ·
> 🟡 Evidencia (resultados experimentales, citar con fecha) ·
> ⚪ Histórico (snapshot, no actuar según él) · 🔴 Pendiente (hallazgo abierto)

**Fecha de verificación de este índice**: 2026-08-30

---

## Documentos citados que NO se distribuyen

El repositorio público no lleva todo lo que este índice y el código citan. Si
llegas aquí desde una referencia que da 404, está en esta lista y es
deliberado:

| Qué | Por qué no viaja |
|---|---|
| `PAPER_UMS`, `PAPER_MOLGRAPH`, `PAPER_MOLPOCKET`, el manuscrito y esqueleto `MF-33`, `27_PAPER_OUTLINE`, `COVER_LETTER_MOLGRAPH` | Manuscritos sin enviar a revista y su material. Publicarlos sería divulgación previa. |
| `docs/figures/*.pdf` y `*.png` | Figuras de esos manuscritos. Se comprobó una por una: cada figura la referencia sólo `PAPER_UMS`, `PAPER_MOLPOCKET` o `PAPER_MOLGRAPH`. |
| `26_UNIVERSAL_METAL_SCORE_RESULTS`, `28_CONSOLIDATED_RESULTS`, `MULTI_TARGET_FINAL_REPORT`, `CL_GNN_MULTITARGET_RESULTS` | Son los resultados que sostienen esos manuscritos. |
| `DECK_EJECUTIVO_INSTITUCIONAL`, `MILESTONE_1`–`MILESTONE_4` | Material de inversión; no le sirve a quien usa la aplicación. |
| `35_GRID_APO_5TUN_PENDIENTE`, `36_POR_ARREGLAR_Y_VALIDAR`, `86_AUDITORIA_LEGAL_RELEASE_PUBLICO_Y_STORE` | Registros internos con hallazgos abiertos. |

**`77_CORRIGENDUM_SITIO_DEL_BENCHMARK_M5_ZN` sí se distribuye**, y conviene decir
por qué se revisó esa decisión. Corrige los §4.2 y §4.3 de
[`75_DECISION_CIENTIFICA_M5_ZN_V1.md`](75_DECISION_CIENTIFICA_M5_ZN_V1.md), que
sí se publica y que abre con la advertencia de que dos de los tres perfiles están
en cuarentena. Publicar la advertencia sin la evidencia que la sostiene habría
dejado al lector sin poder verificarla. El propio corrigendum lo dice de su
primera versión: *«un corrigendum que esconde su propio corrigendum no sirve de
nada»*.

Las citas se conservan tal cual en el código y en los manifiestos —varios de
ellos están verificados por hash y editarlos rompería su gate—, así que una
referencia a un documento ausente es exactamente eso y no un descuido.

---

## Ruta vigente hacia MolDesign 1.0

1. [61_PLAN_CIERRE_APP_ORQUESTACION_CLAUDE.md](61_PLAN_CIERRE_APP_ORQUESTACION_CLAUDE.md) — orden, prioridades y gates.
2. [62_EVAL_AUD_00_EXPEDIENTE.md](62_EVAL_AUD_00_EXPEDIENTE.md) — evidencia y hallazgos cerrados de Evaluación.
3. [63_GATE_RUNTIME_EVALUACION.md](63_GATE_RUNTIME_EVALUACION.md) — siguiente ejecución obligatoria antes de abrir Batch.

**Baseline verificada 2026-08-30:** backend `927 passed, 3 skipped`; frontend
`546 passed` en 54 archivos; TypeScript limpio. Evaluación aún no está verde:
falta ejecutar el protocolo runtime 63 con reinicio y dos cuentas.

---

## Documentación normativa (léase primero)

| # | Documento | Estado | Tema |
|---|---|---|---|
| 80 | [80_INVENTARIO_TECNOLOGICO_INTEGRAL.md](80_INVENTARIO_TECNOLOGICO_INTEGRAL.md) | 🟢 | Mapa normativo del stack: qué se ejecuta, qué viaja, dónde se usa, por qué existe, licencias, residuos y brechas del SBOM. |
| 84 | [84_ARNES_QA_VM_LIMPIA.md](84_ARNES_QA_VM_LIMPIA.md) | 🟢 | El arnés de QA para una VM limpia: flujo canónico del contrato, readiness en dos medidas, ausencias esperadas y evidencia de fallo. Corrige cuatro clases de falso positivo. |
| 79 | [79_ADR_FRONTERA_OPEN_BABEL.md](79_ADR_FRONTERA_OPEN_BABEL.md) | 🟢 | ADR: Open Babel viaja en el instalador como programa GPL-2.0-only independiente, invocado por CLI. Qué queda prohibido, cómo se verifica y qué sigue abierto. |
| 37 | [37_INTEGRATION_POLICY.md](37_INTEGRATION_POLICY.md) | 🟢 | Política de integraciones externas (0-telemetría, opt-in). Normativa de producto. |
| 19 | [19_LIMITATIONS.md](19_LIMITATIONS.md) | 🟢 | Limitaciones honestas del pipeline (silent-fails, dynamic box, dominios). |
| 34 | [34_MOLCHAT_V3.md](34_MOLCHAT_V3.md) | 🟢 | Arquitectura actual de MolChat (determinista + guard 5 capas). |
| 33 | [33_MIGRATION_LLAMA_SERVER.md](33_MIGRATION_LLAMA_SERVER.md) | 🟢 | Por qué MolChat usa `llama-server.exe` (subprocess, no lib). |
| 08 | [08_SCIENTIFIC_VALIDATION.md](08_SCIENTIFIC_VALIDATION.md) | 🟢 | Validación formal: holdout scaffold-disjoint 0.6094, ProLIF excluido. |
| 30 | [30_SECURITY_CSP_AUDIT.md](30_SECURITY_CSP_AUDIT.md) | 🟢 | Auditoría CSP (nonce Next.js, producción sin `unsafe-eval`). |
| 36 | [36_POR_ARREGLAR_Y_VALIDAR.md](36_POR_ARREGLAR_Y_VALIDAR.md) | 🟢 | Lista abierta de hallazgos a validar en el pipeline de evaluación. |
| — | [AUDITORIA_CONSOLIDACION_DESKTOP_2026-08-09.md](AUDITORIA_CONSOLIDACION_DESKTOP_2026-08-09.md) | 🟢 | Auditoría fuente de la consolidación desktop (F-01…F-23 + addenda). |
| — | [DOCUMENTACION_TECNICA_CIENTIFICA_MOLDESIGN.md](DOCUMENTACION_TECNICA_CIENTIFICA_MOLDESIGN.md) | ⚪ | Histórico de julio de 2026; reemplazado por AGENTS.md y el doc 80. |
| 43 | [43_PLAN_ACCION_MADUREZ.md](43_PLAN_ACCION_MADUREZ.md) | 🟢 | Plan operativo vigente: Código → Calidad → Eficiencia → Ciencia. |
| 44 | [44_RELEASE_BASELINE_2026-08-15.md](44_RELEASE_BASELINE_2026-08-15.md) | 🟢 | Baseline recuperable del runtime desktop antes de la campaña de estabilización. |
| 45 | [45_API_CONTRACT_CURRENT.md](45_API_CONTRACT_CURRENT.md) | 🟢 | Mapa generado del OpenAPI vigente; el schema versionado vive en `docs/api/`. |
| 46 | [46_RUNTIME_INVENTORY.md](46_RUNTIME_INVENTORY.md) | 🟢 | Inventario generado del catálogo local y de los modelos declarados por manifest v4. |
| — | [ARCHITECTURE_DESKTOP.md](ARCHITECTURE_DESKTOP.md) | 🟢 | Arquitectura normativa del runtime local, recursos instalados, procesos y almacenamiento. |
| 55 | [55_MVP_DESKTOP_RELEASE.md](55_MVP_DESKTOP_RELEASE.md) | 🟢 | Receta, checksum, evidencia de instalación y límites del release candidate desktop. |
| 56 | [56_DOSSIER_REPRODUCIBLE_CONTRACT.md](56_DOSSIER_REPRODUCIBLE_CONTRACT.md) | 🟢 | Contrato del dossier de caso y del paquete reproducible (PDF + ZIP con manifiesto). |
| 57 | [57_COHORT_PREFLIGHT_V1.md](57_COHORT_PREFLIGHT_V1.md) | 🟢 | Cohortes: contrato de ingesta y comprobación previa. Qué identifica el fingerprint, qué significa `eligible` y qué NO afirma. |
| 58 | [58_COHORT_PERSISTENCE_V1.md](58_COHORT_PERSISTENCE_V1.md) | 🟢 | Cohortes congeladas: qué queda inmutable, por qué se guarda el archivo entero y qué consumirá la ejecución. |
| 59 | [59_COHORT_EXECUTION_V1.md](59_COHORT_EXECUTION_V1.md) | 🟢 | Ejecución durable de una cohorte: qué congela la corrida, `failed` frente a `not_evaluated`, duplicados y recuperación tras reinicio. |
| 60 | [60_AUDITORIA_FINAL_MVP_PRODUCTO.md](60_AUDITORIA_FINAL_MVP_PRODUCTO.md) | 🟢 | Veredicto de producto, interpretación de resultados, valor y condiciones de piloto. |
| 61 | [61_PLAN_CIERRE_APP_ORQUESTACION_CLAUDE.md](61_PLAN_CIERRE_APP_ORQUESTACION_CLAUDE.md) | 🟢 | Plan de cierre vertical hacia 1.0: orden de pestañas, cuatro ejes por pestaña, gates y protocolo de trabajo. |
| 62 | [62_EVAL_AUD_00_EXPEDIENTE.md](62_EVAL_AUD_00_EXPEDIENTE.md) | 🟡 | Expediente de la pestaña Evaluación: hallazgos con evidencia, matriz de trazabilidad, qué se corrigió y qué falta para su gate. |
| 63 | [63_GATE_RUNTIME_EVALUACION.md](63_GATE_RUNTIME_EVALUACION.md) | 🔴 | Protocolo pendiente: corrida real, reinicio, igualdad con dossier y aislamiento entre dos cuentas. |

## Papeles científicos

| # | Documento | Estado | Tema |
|---|---|---|---|
| — | [PAPER_MOLPOCKET.md](PAPER_MOLPOCKET.md) | 🟢 | Detección de pockets APO sin ligando co-cristalizado. |
| — | [PAPER_MOLGRAPH.md](PAPER_MOLGRAPH.md) | 🟢 | Knowledge graph químico de evaluación. |
| — | [PAPER_UMS.md](PAPER_UMS.md) | 🟢 | Universal Metal Score (6 SMARTS sobre zinc metaloenzimas). |
| — | [COVER_LETTER_MOLGRAPH.md](COVER_LETTER_MOLGRAPH.md) | 🟢 | Cover letter del manuscrito MolGraph. |

## Producto y negocio

| # | Documento | Estado | Tema |
|---|---|---|---|
| — | [modelo_negocio.md](modelo_negocio.md) | 🟢 | Estrategia de monetización. |
| — | [DECK_EJECUTIVO_INSTITUCIONAL.md](DECK_EJECUTIVO_INSTITUCIONAL.md) | ⚪ | Borrador histórico; no usar como material público. |
| — | [USER_VALIDATION_FORMS.md](USER_VALIDATION_FORMS.md) | 🟢 | Encuesta de validación de usuarios v2.0. |
| 53 | [53_MAPA_ALINEACION_PRODUCTO.md](53_MAPA_ALINEACION_PRODUCTO.md) | 🟢 | Contrato actual del producto: casos, evidencia, controles, incertidumbre e informe. |
| — | [MILESTONE_1_ROADMAP.md](MILESTONE_1_ROADMAP.md) | ⚪ | Milestone 1 (junio) — snapshot histórico. |
| — | [MILESTONE_2_BUSINESS_FOUNDATION.md](MILESTONE_2_BUSINESS_FOUNDATION.md) | ⚪ | Milestone 2 (julio) — snapshot histórico. |
| — | [MILESTONE_3_TECHNICAL_ARCHITECTURE.md](MILESTONE_3_TECHNICAL_ARCHITECTURE.md) | ⚪ | Milestone 3 (julio) — snapshot histórico. |
| — | [MILESTONE_4_USER_VALIDATION.md](MILESTONE_4_USER_VALIDATION.md) | ⚪ | Milestone 4 (julio) — snapshot histórico. |
| — | [design-dna-moldesign.md](design-dna-moldesign.md) | ⚪ | Design DNA — histórico. |

## Planes y roadmaps

| # | Documento | Estado | Tema |
|---|---|---|---|
| 18 | [18_OSS_ROADMAP.md](18_OSS_ROADMAP.md) | 🔵 | Roadmap open source (6 fases). |
| 23 | [23_BUCKET_C_RESEARCH_TRACK.md](23_BUCKET_C_RESEARCH_TRACK.md) | 🔵 | GNN-v3 universal research track. |
| 25 | [25_FRONTEND_UNIFICATION_PLAN.md](25_FRONTEND_UNIFICATION_PLAN.md) | 🔵 | Unificación frontend PRO + Hallmark. |
| 27 | [27_PAPER_OUTLINE.md](27_PAPER_OUTLINE.md) | 🔵 | Outline del paper UMS. |
| — | [molgraph_v2.md](molgraph_v2.md) | 🔵 | Evolución del knowledge graph (fase B). |
| 48 | [48_INVENTARIO_REUTILIZACION_MOLFLEX_RESCORING.md](48_INVENTARIO_REUTILIZACION_MOLFLEX_RESCORING.md) | 🔵 | Inventario reuse-first de MolFlex, Ruta C, MolChamb, UMS y ZnCoord. |
| 49 | [49_PROGRAMA_EXPERIMENTAL_CIENTIFICO.md](49_PROGRAMA_EXPERIMENTAL_CIENTIFICO.md) | 🔵 | Programa maestro de experimentos: receptor → poses → rescoring → FEP+ ready. |

## Evidencia experimental (citar con fecha, no como estado actual)

| # | Documento | Estado | Tema |
|---|---|---|---|
| 07 | [07_SPEARMAN_BENCHMARK_LOG.md](07_SPEARMAN_BENCHMARK_LOG.md) | 🟡 | Bitácora de 8 experimentos Spearman. |
| 10 | [10_VINA_GPU_HYBRID.md](10_VINA_GPU_HYBRID.md) | 🟡 | Resultados Vina-GPU (NO en producción). |
| 17 | [17_EF_BENCHMARK_FIXES.md](17_EF_BENCHMARK_FIXES.md) | 🟡 | Fixes y re-corrida EF@1% (AUC 0.958). |
| 21 | [21_ABLATION_MOLCHAMB_5HT1A.md](21_ABLATION_MOLCHAMB_5HT1A.md) | 🟡 | Ablation MolChamb 5HT1A. |
| 22 | [22_ABLATION_MOLCHAMB_CDK2.md](22_ABLATION_MOLCHAMB_CDK2.md) | 🟡 | Ablation MolChamb CDK2. |
| 22b | [22_METAL_FEATURES.md](22_METAL_FEATURES.md) | 🟡 | Features de metaloenzimas (Zn). |
| 26 | [26_UNIVERSAL_METAL_SCORE_RESULTS.md](26_UNIVERSAL_METAL_SCORE_RESULTS.md) | 🟡 | Validación del Universal Metal Score. |
| 28 | [28_CONSOLIDATED_RESULTS.md](28_CONSOLIDATED_RESULTS.md) | 🟡 | Resultados finales consolidados UMS. |
| — | [CL_GNN_MULTITARGET_RESULTS.md](CL_GNN_MULTITARGET_RESULTS.md) | 🟡 | Evaluación multi-target CL-GNN (2026-07-26). |
| — | [MULTI_TARGET_FINAL_REPORT.md](MULTI_TARGET_FINAL_REPORT.md) | 🟡 | Reporte final multi-target (night batch). |
| — | [STOCHASTICITY_REPORT.md](STOCHASTICITY_REPORT.md) | 🟡 | Reporte honesto de estocasticidad CL-GNN. |
| — | [metricas_experimentales.md](metricas_experimentales.md) | 🟡 | Historial versionado de métricas del scoring engine. |

## Históricos (snapshots — NO actuar según ellos)

| # | Documento | Estado | Nota |
|---|---|---|---|
| 16 | [16_AUDIT_FIXES.md](16_AUDIT_FIXES.md) | ⚪ | Registro de 3 auditorías hasta v1.5. |
| 24 | [24_OSS_READINESS_CHECKLIST.md](24_OSS_READINESS_CHECKLIST.md) | ⚪ | Snapshot 2026-07-25; declara ausentes archivos que ya existen. |
| 29 | [29_SESSION_CLOSE_STATUS.md](29_SESSION_CLOSE_STATUS.md) | ⚪ | Estado al cierre de sesión 2026-07-29. |
| 31 | [31_PIPELINE_DATA_INVENTORY.md](31_PIPELINE_DATA_INVENTORY.md) | ⚪ | Snapshot 2026-07-29; describe UI mock ya superada. |
| 32 | [32_CROSS_VALIDATION_EVALUATION_TAB.md](32_CROSS_VALIDATION_EVALUATION_TAB.md) | ⚪ | Snapshot 2026-07-29; inventario de endpoints, no estado actual. |

## Pendientes de validación

| # | Documento | Estado | Nota |
|---|---|---|---|
| 35 | [35_GRID_APO_5TUN_PENDIENTE.md](35_GRID_APO_5TUN_PENDIENTE.md) | 🔴 | Grid desalineado en targets APO (5TUN) — hallazgo abierto. |
| 36 | [36_POR_ARREGLAR_Y_VALIDAR.md](36_POR_ARREGLAR_Y_VALIDAR.md) | 🔴 | Lista abierta de validaciones del pipeline. |
| 63 | [63_GATE_RUNTIME_EVALUACION.md](63_GATE_RUNTIME_EVALUACION.md) | 🟢 | Gate runtime de Evaluación aprobado con Vina real, reinicio y aislamiento. |
| 64 | [64_GATE_RUNTIME_BATCH.md](64_GATE_RUNTIME_BATCH.md) | 🟢 | Gate runtime de Batch aprobado con Vina real, recuperación y dossier. |
| 67 | [67_GATE_MOLCHAT.md](67_GATE_MOLCHAT.md) | 🟢 | Gate de MolChat aprobado con suite adversarial; dos exclusiones declaradas (MOLCHAT-BE-009 y gate runtime). |
| 68 | [68_GATE_RUNTIME_MOLDEX_Y_MOLCHAT.md](68_GATE_RUNTIME_MOLDEX_Y_MOLCHAT.md) | 🟢 | Gates runtime de Moldex y MolChat con Vina y modelo local reales; dos fallos encontrados y corregidos. |
| 69 | [69_GATE_DE_RELEASE.md](69_GATE_DE_RELEASE.md) | 🟡 | Actualización sin pérdida de datos y SBOM verdes; instalador, firma, VMs y piloto siguen bloqueados por recursos del propietario. |

---

## Convenciones

- **Owner**: todas las decisiones pasan por el maintainer de la sesión activa;
  los papers tienen autoría en sus propios documentos.
- **Verificación**: la fecha de verificación de cada entrada es la fecha del
  documento o la de su última actualización registrada en su encabezado.
- **Código asociado**: los documentos normativos referencian rutas concretas
  (`backend/…`, `rescoring/…`, `frontend/…`) en su contenido.
- **Regla de edición**: un documento histórico NO se edita para "actualizarlo";
  se archiva o se crea uno nuevo con fecha vigente.
