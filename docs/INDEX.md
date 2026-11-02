# Índice Documental — MolDesign (`moldesign-build`)

> **Propósito**: localizar la documentación vigente sin contrastar decenas de
> archivos manualmente. El estado de cada documento está en su cabecera.
> Creado por hallazgo F-06 (auditoría 2026-08-09).

**Fecha de revisión de cobertura y estados**: 2026-11-01. Las medidas históricas conservan su fecha; el inventario no implica revalidarlas.

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

## Guías y decisiones vigentes

Para construir y verificar desde un clon, empieza por [CONTRIBUTING.md](../CONTRIBUTING.md) y [BUILD_GUIDE.md](../BUILD_GUIDE.md). [AGENTS.md](../AGENTS.md) describe las restricciones y el mapa del producto. El estado de implementación no acredita una nueva validación científica ni del instalador; cada documento conserva sus límites.

| Documento | Tema |
|---|---|
| [50_ROADMAP.md](50_ROADMAP.md) | Roadmap vigente |
| [53_MAPA_ALINEACION_PRODUCTO.md](53_MAPA_ALINEACION_PRODUCTO.md) | Identidad y contrato del producto |
| [ARCHITECTURE_DESKTOP.md](ARCHITECTURE_DESKTOP.md) | Arquitectura de escritorio |
| [45_API_CONTRACT_CURRENT.md](45_API_CONTRACT_CURRENT.md) | Contrato OpenAPI generado |
| [46_RUNTIME_INVENTORY.md](46_RUNTIME_INVENTORY.md) | Inventario runtime generado |
| [56_DOSSIER_REPRODUCIBLE_CONTRACT.md](56_DOSSIER_REPRODUCIBLE_CONTRACT.md) | Contrato del dossier y paquete |
| [78_DECISION_DISTRIBUCION_DE_PESOS_Y_RUNTIME.md](78_DECISION_DISTRIBUCION_DE_PESOS_Y_RUNTIME.md) | Distribución de pesos y runtime |
| [79_ADR_FRONTERA_OPEN_BABEL.md](79_ADR_FRONTERA_OPEN_BABEL.md) | Frontera de Open Babel |
| [83_ADR_SOLANA_DEVNET_POC.md](83_ADR_SOLANA_DEVNET_POC.md) | Alcance del POC en devnet |
| [84_ARNES_QA_VM_LIMPIA.md](84_ARNES_QA_VM_LIMPIA.md) | Arnés de QA en VM |
| [95_ADR_MOTOR_MOLCY_EN_EL_INSTALADOR.md](95_ADR_MOTOR_MOLCY_EN_EL_INSTALADOR.md) | Motor Molcy independiente |
| [100_ADR_MOLCHAT_EXTERNO.md](100_ADR_MOLCHAT_EXTERNO.md) | MolChat independiente y host |
| [101_PROTOCOLO_MOLCHAT.md](101_PROTOCOLO_MOLCHAT.md) | Contrato con MolChat |
| [LICENSING.md](LICENSING.md) | Explicación de licencias; mandan los textos de raíz |

## Evidencia e históricos

- [55_MVP_DESKTOP_RELEASE.md](55_MVP_DESKTOP_RELEASE.md) — histórico de 1.0.0; sus bytes, tamaño y checksum no describen la distribución actual.
- [80_INVENTARIO_TECNOLOGICO_INTEGRAL.md](80_INVENTARIO_TECNOLOGICO_INTEGRAL.md) — corte histórico; las versiones actuales están en el lock y el SBOM.
- [91_AUDITORIA_PROCEDENCIA_CATALOGO_RECEPTORES.md](91_AUDITORIA_PROCEDENCIA_CATALOGO_RECEPTORES.md) — evidencia de septiembre; no es un inventario vigente del catálogo.
- Los documentos 33, 34, 61, 67 y 68 conservan las rutas y medidas anteriores a la extracción de MolChat; sus cabeceras los identifican como históricos.
- [Plan histórico del launcher](historicos/ROADMAP_LAUNCHER_202607.md) — antigua ubicación ROADMAP.md; no es una propuesta vigente de arquitectura o telemetría.

## Inventario completo de documentos de primer nivel

Este listado localiza todos los ficheros públicos de `docs/`. La inclusión no les concede estado normativo: consulta la cabecera, la fecha y los corrigenda de cada documento. La revisión de cobertura del índice no significa que se hayan repetido sus experimentos. Los números 86, 100 y 101 están repetidos: cita siempre el nombre completo.

- [00_INDEX.md](00_INDEX.md)
- [01_PIPELINE.md](01_PIPELINE.md)
- [02_DESKTOP.md](02_DESKTOP.md)
- [03_API.md](03_API.md)
- [04_ARCHITECTURE.md](04_ARCHITECTURE.md)
- [05_CLOUD_DEPLOY.md](05_CLOUD_DEPLOY.md)
- [06_FAMILY_RETRAINING.md](06_FAMILY_RETRAINING.md)
- [07_SPEARMAN_BENCHMARK_LOG.md](07_SPEARMAN_BENCHMARK_LOG.md)
- [08_SCIENTIFIC_VALIDATION.md](08_SCIENTIFIC_VALIDATION.md)
- [09_PACKAGING_STRATEGY.md](09_PACKAGING_STRATEGY.md)
- [100_ADR_MOLCHAT_EXTERNO.md](100_ADR_MOLCHAT_EXTERNO.md)
- [100_CORRECCIONES_AUDITORIA_CIENCIA_20261015.md](100_CORRECCIONES_AUDITORIA_CIENCIA_20261015.md)
- [101_CORRIGENDA_SELLOS_AUDITORIA_20261020.md](101_CORRIGENDA_SELLOS_AUDITORIA_20261020.md)
- [101_PROTOCOLO_MOLCHAT.md](101_PROTOCOLO_MOLCHAT.md)
- [102_FASE_1B_CORRECCIONES.md](102_FASE_1B_CORRECCIONES.md)
- [10_VINA_GPU_HYBRID.md](10_VINA_GPU_HYBRID.md)
- [11_GPU_BENCHMARK_RESULTS.md](11_GPU_BENCHMARK_RESULTS.md)
- [12_STRESS_TEST_1000.md](12_STRESS_TEST_1000.md)
- [13_DIARIO_EXPERIMENTOS_GPU.md](13_DIARIO_EXPERIMENTOS_GPU.md)
- [14_TARGET_LIBRARY.md](14_TARGET_LIBRARY.md)
- [15_BATCH_SCREENING.md](15_BATCH_SCREENING.md)
- [16_AUDIT_FIXES.md](16_AUDIT_FIXES.md)
- [17_EF_BENCHMARK_FIXES.md](17_EF_BENCHMARK_FIXES.md)
- [17_STEAM_DEPLOYMENT.md](17_STEAM_DEPLOYMENT.md)
- [18_OSS_ROADMAP.md](18_OSS_ROADMAP.md)
- [19_LIMITATIONS.md](19_LIMITATIONS.md)
- [21_ABLATION_MOLCHAMB_5HT1A.md](21_ABLATION_MOLCHAMB_5HT1A.md)
- [22_ABLATION_MOLCHAMB_CDK2.md](22_ABLATION_MOLCHAMB_CDK2.md)
- [22_METAL_FEATURES.md](22_METAL_FEATURES.md)
- [23_BUCKET_C_RESEARCH_TRACK.md](23_BUCKET_C_RESEARCH_TRACK.md)
- [24_OSS_READINESS_CHECKLIST.md](24_OSS_READINESS_CHECKLIST.md)
- [25_FRONTEND_UNIFICATION_PLAN.md](25_FRONTEND_UNIFICATION_PLAN.md)
- [29_SESSION_CLOSE_STATUS.md](29_SESSION_CLOSE_STATUS.md)
- [30_SECURITY_CSP_AUDIT.md](30_SECURITY_CSP_AUDIT.md)
- [31_PIPELINE_DATA_INVENTORY.md](31_PIPELINE_DATA_INVENTORY.md)
- [32_CROSS_VALIDATION_EVALUATION_TAB.md](32_CROSS_VALIDATION_EVALUATION_TAB.md)
- [33_MIGRATION_LLAMA_SERVER.md](33_MIGRATION_LLAMA_SERVER.md)
- [34_MOLCHAT_V3.md](34_MOLCHAT_V3.md)
- [37_INTEGRATION_POLICY.md](37_INTEGRATION_POLICY.md)
- [38_FASE_B_BASELINE.md](38_FASE_B_BASELINE.md)
- [39_FASE_B_RUNBOOK.md](39_FASE_B_RUNBOOK.md)
- [40_MOLFLEX_PROTOCOL.md](40_MOLFLEX_PROTOCOL.md)
- [41_RUTA_C_INVESTIGACION_CAMPO.md](41_RUTA_C_INVESTIGACION_CAMPO.md)
- [42_RUTA_C_PROTOCOLO.md](42_RUTA_C_PROTOCOLO.md)
- [43_PLAN_ACCION_MADUREZ.md](43_PLAN_ACCION_MADUREZ.md)
- [44_RELEASE_BASELINE_2026-08-15.md](44_RELEASE_BASELINE_2026-08-15.md)
- [45_API_CONTRACT_CURRENT.md](45_API_CONTRACT_CURRENT.md)
- [46_RUNTIME_INVENTORY.md](46_RUNTIME_INVENTORY.md)
- [47_RUTA_C_FASE4_PREREGISTRO.md](47_RUTA_C_FASE4_PREREGISTRO.md)
- [48_INVENTARIO_REUTILIZACION_MOLFLEX_RESCORING.md](48_INVENTARIO_REUTILIZACION_MOLFLEX_RESCORING.md)
- [49_PROGRAMA_EXPERIMENTAL_CIENTIFICO.md](49_PROGRAMA_EXPERIMENTAL_CIENTIFICO.md)
- [50_ROADMAP.md](50_ROADMAP.md)
- [51_POLITICA_DE_AGUAS.md](51_POLITICA_DE_AGUAS.md)
- [53_MAPA_ALINEACION_PRODUCTO.md](53_MAPA_ALINEACION_PRODUCTO.md)
- [55_MVP_DESKTOP_RELEASE.md](55_MVP_DESKTOP_RELEASE.md)
- [56_DOSSIER_REPRODUCIBLE_CONTRACT.md](56_DOSSIER_REPRODUCIBLE_CONTRACT.md)
- [57_COHORT_PREFLIGHT_V1.md](57_COHORT_PREFLIGHT_V1.md)
- [58_COHORT_PERSISTENCE_V1.md](58_COHORT_PERSISTENCE_V1.md)
- [59_COHORT_EXECUTION_V1.md](59_COHORT_EXECUTION_V1.md)
- [60_AUDITORIA_FINAL_MVP_PRODUCTO.md](60_AUDITORIA_FINAL_MVP_PRODUCTO.md)
- [61_PLAN_CIERRE_APP_ORQUESTACION_CLAUDE.md](61_PLAN_CIERRE_APP_ORQUESTACION_CLAUDE.md)
- [62_AUDITORIA_TERCEROS_Y_LAUNCHER.md](62_AUDITORIA_TERCEROS_Y_LAUNCHER.md)
- [62_EVAL_AUD_00_EXPEDIENTE.md](62_EVAL_AUD_00_EXPEDIENTE.md)
- [63_GATE_RUNTIME_EVALUACION.md](63_GATE_RUNTIME_EVALUACION.md)
- [64_GATE_RUNTIME_BATCH.md](64_GATE_RUNTIME_BATCH.md)
- [65_MOLDEX_AUD_00_EXPEDIENTE.md](65_MOLDEX_AUD_00_EXPEDIENTE.md)
- [66_MOLCHAT_AUD_00_EXPEDIENTE.md](66_MOLCHAT_AUD_00_EXPEDIENTE.md)
- [67_GATE_MOLCHAT.md](67_GATE_MOLCHAT.md)
- [68_GATE_RUNTIME_MOLDEX_Y_MOLCHAT.md](68_GATE_RUNTIME_MOLDEX_Y_MOLCHAT.md)
- [69_GATE_DE_RELEASE.md](69_GATE_DE_RELEASE.md)
- [70_BITACORA_PRIMERA_VERSION_EN_VM.md](70_BITACORA_PRIMERA_VERSION_EN_VM.md)
- [71_HALLAZGO_CADENA_RECEPTOR_Y_PENDIENTES.md](71_HALLAZGO_CADENA_RECEPTOR_Y_PENDIENTES.md)
- [72_PRIMERA_TANDA_DEL_SELLO_DEL_CATALOGO.md](72_PRIMERA_TANDA_DEL_SELLO_DEL_CATALOGO.md)
- [73_AUDITORIA_WINDOWS_MAQUINA_LIMPIA.md](73_AUDITORIA_WINDOWS_MAQUINA_LIMPIA.md)
- [74_ARQUITECTURA_DISPATCHER_DE_PROTOCOLOS.md](74_ARQUITECTURA_DISPATCHER_DE_PROTOCOLOS.md)
- [75_DECISION_CIENTIFICA_M5_ZN_V1.md](75_DECISION_CIENTIFICA_M5_ZN_V1.md)
- [76_DECISION_TRANSFERENCIA_ESMFOLD_A_LIGANDO_V1.md](76_DECISION_TRANSFERENCIA_ESMFOLD_A_LIGANDO_V1.md)
- [77_CORRIGENDUM_SITIO_DEL_BENCHMARK_M5_ZN.md](77_CORRIGENDUM_SITIO_DEL_BENCHMARK_M5_ZN.md)
- [78_DECISION_DISTRIBUCION_DE_PESOS_Y_RUNTIME.md](78_DECISION_DISTRIBUCION_DE_PESOS_Y_RUNTIME.md)
- [79_ADR_FRONTERA_OPEN_BABEL.md](79_ADR_FRONTERA_OPEN_BABEL.md)
- [80_INVENTARIO_TECNOLOGICO_INTEGRAL.md](80_INVENTARIO_TECNOLOGICO_INTEGRAL.md)
- [81_HANDOFF_RUNTIME_ALPHA.md](81_HANDOFF_RUNTIME_ALPHA.md)
- [82_CLON_LIMPIO_CONSTRUIBLE.md](82_CLON_LIMPIO_CONSTRUIBLE.md)
- [83_ADR_SOLANA_DEVNET_POC.md](83_ADR_SOLANA_DEVNET_POC.md)
- [84_ARNES_QA_VM_LIMPIA.md](84_ARNES_QA_VM_LIMPIA.md)
- [85_CORRECCIONES_AUDITORIA_SOL_20261001.md](85_CORRECCIONES_AUDITORIA_SOL_20261001.md)
- [85_VALIDACION_EXTERNA_PIPELINES_ALPHA.md](85_VALIDACION_EXTERNA_PIPELINES_ALPHA.md)
- [86_CORRECCIONES_AUDITORIA_LUNA_20261002.md](86_CORRECCIONES_AUDITORIA_LUNA_20261002.md)
- [86_DISTRIBUCION_MSIX_MICROSOFT_STORE.md](86_DISTRIBUCION_MSIX_MICROSOFT_STORE.md)
- [87_ADR_CONTRATO_STACKING_CLGNN_ALPHA.md](87_ADR_CONTRATO_STACKING_CLGNN_ALPHA.md)
- [88_EXPLORACION_NEEDLE_3.md](88_EXPLORACION_NEEDLE_3.md)
- [89_FASE6_PREREG_CLASIFICADOR.md](89_FASE6_PREREG_CLASIFICADOR.md)
- [90_FASE6_DECISION_M4.md](90_FASE6_DECISION_M4.md)
- [91_AUDITORIA_PROCEDENCIA_CATALOGO_RECEPTORES.md](91_AUDITORIA_PROCEDENCIA_CATALOGO_RECEPTORES.md)
- [92_ADR_MOLCY_RENDERIZADOR_EXTERNO.md](92_ADR_MOLCY_RENDERIZADOR_EXTERNO.md)
- [93_MOLCY_RECURSOS_Y_LIMITES.md](93_MOLCY_RECURSOS_Y_LIMITES.md)
- [94_PLAN_TRADUCCION_DEL_ENTREGABLE.md](94_PLAN_TRADUCCION_DEL_ENTREGABLE.md)
- [95_ADR_MOTOR_MOLCY_EN_EL_INSTALADOR.md](95_ADR_MOTOR_MOLCY_EN_EL_INSTALADOR.md)
- [96_DISENO_MOTOR_EXTERNO_VIA_API.md](96_DISENO_MOTOR_EXTERNO_VIA_API.md)
- [97_PLAN_MOTOR_EXTERNO_VIA_API.md](97_PLAN_MOTOR_EXTERNO_VIA_API.md)
- [98_ARQUITECTURA_MODULAR_DE_MOTORES.md](98_ARQUITECTURA_MODULAR_DE_MOTORES.md)
- [99_EXPERIMENTOS_MOLCHAT_MODELOS_PEQUENOS.md](99_EXPERIMENTOS_MOLCHAT_MODELOS_PEQUENOS.md)
- [ARCHITECTURE_DESKTOP.md](ARCHITECTURE_DESKTOP.md)
- [asistente_laboratorio.md](asistente_laboratorio.md)
- [AUDITORIA_CONSOLIDACION_DESKTOP_2026-08-09.md](AUDITORIA_CONSOLIDACION_DESKTOP_2026-08-09.md)
- [campana_multitarget.md](campana_multitarget.md)
- [COMERCIAL.md](COMERCIAL.md)
- [CREACION_DE_HERRAMIENTAS_MOLCHAT.md](CREACION_DE_HERRAMIENTAS_MOLCHAT.md)
- [DEPENDENCY_SECURITY_AUDIT.md](DEPENDENCY_SECURITY_AUDIT.md)
- [design-dna-moldesign.md](design-dna-moldesign.md)
- [DOCUMENTACION_TECNICA_CIENTIFICA_MOLDESIGN.md](DOCUMENTACION_TECNICA_CIENTIFICA_MOLDESIGN.md)
- [EFICIENCIA_NORMALIZADA_COHORTE_2026-09-04.md](EFICIENCIA_NORMALIZADA_COHORTE_2026-09-04.md)
- [GLOSARIO_EN.md](GLOSARIO_EN.md)
- [gnn_v2_arquitectura.md](gnn_v2_arquitectura.md)
- [ideas_futuras.md](ideas_futuras.md)
- [Interprete_IA.md](Interprete_IA.md)
- [LICENSING.md](LICENSING.md)
- [metricas_experimentales.md](metricas_experimentales.md)
- [metricas_experimentales_2026-07.md](metricas_experimentales_2026-07.md)
- [MODO_SOMBRA_MOLCHAT.md](MODO_SOMBRA_MOLCHAT.md)
- [molchamb_v2.md](molchamb_v2.md)
- [MOLCY_DEVOPS_CPU.md](MOLCY_DEVOPS_CPU.md)
- [MolGraph.md](MolGraph.md)
- [molgraph_v2.md](molgraph_v2.md)
- [plan_early_exit.md](plan_early_exit.md)
- [posibles_problemas_y_mejoras.md](posibles_problemas_y_mejoras.md)
- [posibles_tecnologias.md](posibles_tecnologias.md)
- [propuestas_de_mejora.md](propuestas_de_mejora.md)
- [README.md](README.md)
- [REUBICACIONES_2026-10-11.md](REUBICACIONES_2026-10-11.md)
- [roadmap.md](roadmap.md)
- [SCIENTIFIC_ARTIFACTS_LICENSE.md](SCIENTIFIC_ARTIFACTS_LICENSE.md)
- [SESSION_SUMMARY_v1.3.md](SESSION_SUMMARY_v1.3.md)
- [SESSION_SUMMARY_v1.4.md](SESSION_SUMMARY_v1.4.md)
- [SESSION_SUMMARY_v1.5.md](SESSION_SUMMARY_v1.5.md)
- [SESSION_SUMMARY_v1.6.md](SESSION_SUMMARY_v1.6.md)
- [SESSION_SUMMARY_v1.7.md](SESSION_SUMMARY_v1.7.md)
- [STOCHASTICITY_REPORT.md](STOCHASTICITY_REPORT.md)
- [STORE_RUNFULLTRUST_JUSTIFICATION.md](STORE_RUNFULLTRUST_JUSTIFICATION.md)
- [STORE_SUBMISSION_LEGAL.md](STORE_SUBMISSION_LEGAL.md)
- [STORE_WACK_DIAGNOSTICO.md](STORE_WACK_DIAGNOSTICO.md)
- [TRAZA_BUSQUEDA_MOLCY.md](TRAZA_BUSQUEDA_MOLCY.md)
- [validacion_mmgbsa.md](validacion_mmgbsa.md)

## Convenciones

Las medidas se citan con fecha y fuente; las decisiones, con el nombre completo del archivo. Los registros históricos conservan sus resultados originales. Una ruta retenida del público se contrasta con `scripts/retenidos_del_publico.txt` antes de declararla rota.
