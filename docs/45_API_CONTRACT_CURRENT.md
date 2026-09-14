# 45 — Contrato API actual (generado)

**Estado:** 🟢 Contrato vigente generado desde el backend.

Este mapa y el snapshot JSON se derivan de `backend/api/main.py`; no se editan manualmente. `docs/31_PIPELINE_DATA_INVENTORY.md` y `docs/32_CROSS_VALIDATION_EVALUATION_TAB.md` permanecen como inventarios históricos de UX.

## Identidad del snapshot

- Paths: **113**
- Operaciones HTTP: **119**
- Versión declarada: `1.0.0`
- SHA-256: `a35cc4721039f98bf917cb73ffe8c0c042cd0b7c3e517cf7a5bce488f40e823b`
- Schema completo: [api/openapi-current.json](api/openapi-current.json)
- Regenerar: `python scripts/generate_openapi_contract.py --write`
- Verificar en CI: `python scripts/generate_openapi_contract.py --check`
- Revisar incompatibilidades: `python scripts/generate_openapi_contract.py --diff`

## Operaciones

| Método | Ruta | operationId | Resumen | Tags |
|---|---|---|---|---|
| `GET` | `/` | `root__get` | Root | Meta |
| `POST` | `/ai/chat` | `chat_completion_ai_chat_post` | Chat Completion | MolChat |
| `GET` | `/ai/consent` | `listar_consentimientos_ai_consent_get` | Listar Consentimientos | MolChat |
| `POST` | `/ai/consent` | `otorgar_consentimiento_ai_consent_post` | Otorgar Consentimiento | MolChat |
| `GET` | `/ai/consent/red` | `listar_destinos_de_red_ai_consent_red_get` | Listar Destinos De Red | MolChat |
| `POST` | `/ai/consent/red` | `otorgar_destino_de_red_ai_consent_red_post` | Otorgar Destino De Red | MolChat |
| `DELETE` | `/ai/consent/red/{servicio}` | `revocar_destino_de_red_ai_consent_red__servicio__delete` | Revocar Destino De Red | MolChat |
| `DELETE` | `/ai/consent/{provider_id}` | `revocar_consentimiento_ai_consent__provider_id__delete` | Revocar Consentimiento | MolChat |
| `GET` | `/ai/conversations` | `list_conversations_ai_conversations_get` | List Conversations | MolChat |
| `POST` | `/ai/conversations` | `create_conversation_ai_conversations_post` | Create Conversation | MolChat |
| `DELETE` | `/ai/conversations/{conv_id}` | `delete_conversation_ai_conversations__conv_id__delete` | Delete Conversation | MolChat |
| `GET` | `/ai/conversations/{conv_id}` | `get_conversation_ai_conversations__conv_id__get` | Get Conversation | MolChat |
| `GET` | `/ai/models` | `list_models_ai_models_get` | List Models | MolChat |
| `POST` | `/ai/models/download` | `start_model_download_ai_models_download_post` | Start Model Download | MolChat |
| `GET` | `/ai/models/download/{dl_id}` | `get_model_download_status_ai_models_download__dl_id__get` | Get Model Download Status | MolChat |
| `GET` | `/ai/models/local` | `list_local_models_ai_models_local_get` | List Local Models | MolChat |
| `POST` | `/ai/models/open-folder` | `open_models_folder_ai_models_open_folder_post` | Open Models Folder | MolChat |
| `GET` | `/ai/models/recommend-quant` | `recommend_quantization_ai_models_recommend_quant_get` | Recommend Quantization | MolChat |
| `GET` | `/ai/models/search` | `search_models_ai_models_search_get` | Search Models | MolChat |
| `GET` | `/ai/providers` | `list_providers_ai_providers_get` | List Providers | MolChat |
| `GET` | `/ai/providers/active` | `get_active_provider_ai_providers_active_get` | Get Active Provider | MolChat |
| `POST` | `/ai/providers/active` | `set_active_provider_ai_providers_active_post` | Set Active Provider | MolChat |
| `POST` | `/ai/providers/configure` | `configure_provider_ai_providers_configure_post` | Configure Provider | MolChat |
| `PATCH` | `/ai/settings` | `update_ai_settings_ai_settings_patch` | Update Ai Settings | MolChat |
| `POST` | `/ai/speech-to-text` | `speech_to_text_ai_speech_to_text_post` | Speech To Text | MolChat |
| `GET` | `/ai/speech-to-text/status` | `speech_to_text_status_ai_speech_to_text_status_get` | Speech To Text Status | MolChat |
| `GET` | `/ai/startup` | `startup_detection_ai_startup_get` | Startup Detection | MolChat |
| `GET` | `/ai/status` | `ai_status_ai_status_get` | Ai Status | MolChat |
| `GET` | `/auth/desktop-login` | `desktop_auto_login_auth_desktop_login_get` | Auto-login para modo DESKTOP | Autenticación |
| `POST` | `/auth/login` | `login_auth_login_post` | Iniciar sesión | Autenticación |
| `GET` | `/auth/me` | `get_me_auth_me_get` | Perfil del usuario autenticado | Autenticación |
| `POST` | `/auth/oauth` | `oauth_login_auth_oauth_post` | Iniciar sesión con OAuth (Google / Microsoft) | Autenticación |
| `POST` | `/auth/refresh` | `refresh_auth_refresh_post` | Refrescar access token | Autenticación |
| `POST` | `/auth/register` | `register_auth_register_post` | Registrar nuevo usuario | Autenticación |
| `POST` | `/auth/traspaso` | `traspasar_del_invitado_auth_traspaso_post` | Llevar a esta cuenta el trabajo hecho como invitado | Autenticación |
| `GET` | `/blockchain/certificate/{molecule_id}` | `get_certificate_blockchain_certificate__molecule_id__get` | Get Certificate | blockchain |
| `GET` | `/blockchain/certificate/{molecule_id}/preview` | `get_certificate_preview_blockchain_certificate__molecule_id__preview_get` | Get Certificate Preview | blockchain |
| `POST` | `/blockchain/certify` | `certify_molecule_blockchain_certify_post` | Certify Molecule | blockchain |
| `POST` | `/blockchain/certify/link` | `link_certification_blockchain_certify_link_post` | Link Certification | blockchain |
| `GET` | `/blockchain/certify/{molecule_id}/prepare` | `prepare_certification_blockchain_certify__molecule_id__prepare_get` | Prepare Certification | blockchain |
| `GET` | `/blockchain/health` | `blockchain_health_blockchain_health_get` | Blockchain Health | blockchain |
| `GET` | `/blockchain/verify/{signature}` | `verify_certification_blockchain_verify__signature__get` | Verify Certification | blockchain |
| `POST` | `/chem/conformer` | `conformer_endpoint_chem_conformer_post` | Genera estructura 3D | Química computacional |
| `POST` | `/chem/properties` | `properties_endpoint_chem_properties_post` | Calcula propiedades fisicoquímicas | Química computacional |
| `GET` | `/chem/render/{molecule_id}` | `render_2d_molecule_chem_render__molecule_id__get` | Renderiza molécula en 2D | Química computacional |
| `POST` | `/chem/validate` | `validate_endpoint_chem_validate_post` | Valida un SMILES | Química computacional |
| `POST` | `/evaluation/ai-report/{molecule_id}` | `generate_ai_report_endpoint_evaluation_ai_report__molecule_id__post` | Generar reporte IA bajo demanda para una molécula evaluada | Evaluación científica, Evaluación científica |
| `GET` | `/evaluation/ai-report/{molecule_id}/stream` | `generate_ai_report_stream_endpoint_evaluation_ai_report__molecule_id__stream_get` | Generar reporte IA bajo demanda (Streaming SSE) | Evaluación científica, Evaluación científica |
| `POST` | `/evaluation/batch` | `submit_batch_evaluation_batch_post` | Submit Batch | Batch Screening |
| `GET` | `/evaluation/batch/{batch_id}` | `get_batch_status_evaluation_batch__batch_id__get` | Get Batch Status | Batch Screening |
| `GET` | `/evaluation/batch/{batch_id}/csv` | `export_batch_csv_evaluation_batch__batch_id__csv_get` | Export Batch Csv | Batch Screening |
| `GET` | `/evaluation/batch/{batch_id}/export` | `export_batch_excel_evaluation_batch__batch_id__export_get` | Export Batch Excel | Batch Screening |
| `POST` | `/evaluation/cancel` | `cancel_evaluation_evaluation_cancel_post` | Cancelar una evaluación desktop por task_id | Evaluación científica |
| `GET` | `/evaluation/cohort-runs/{run_id}` | `read_run_evaluation_cohort_runs__run_id__get` | Estado, progreso, configuración efectiva, procedencia y filas | Evaluación científica, Cohortes |
| `POST` | `/evaluation/cohort-runs/{run_id}/cancel` | `cancel_run_evaluation_cohort_runs__run_id__cancel_post` | Pedir la cancelación de una corrida | Evaluación científica, Cohortes |
| `POST` | `/evaluation/cohort-runs/{run_id}/dossier/package` | `dossier_package_evaluation_cohort_runs__run_id__dossier_package_post` | Paquete verificable de la cohorte (ZIP con manifiesto y hashes) | Evaluación científica, Cohortes |
| `POST` | `/evaluation/cohort-runs/{run_id}/dossier/preview` | `dossier_preview_evaluation_cohort_runs__run_id__dossier_preview_post` | Dossier de cohorte en PDF (inline) | Evaluación científica, Cohortes |
| `GET` | `/evaluation/cohort-runs/{run_id}/evidence` | `read_evidence_evaluation_cohort_runs__run_id__evidence_get` | Resumen científico de la corrida (cobertura, evidencia y métricas) | Evaluación científica, Cohortes |
| `POST` | `/evaluation/cohort-runs/{run_id}/resume` | `resume_run_evaluation_cohort_runs__run_id__resume_post` | Reanudar una corrida interrumpida o con excepciones | Evaluación científica, Cohortes |
| `GET` | `/evaluation/cohorts` | `list_cohorts_evaluation_cohorts_get` | Cohortes congeladas (resumen: sin filas y sin archivo) | Evaluación científica, Cohortes |
| `POST` | `/evaluation/cohorts` | `create_cohort_evaluation_cohorts_post` | Congelar una cohorte comprobada (no ejecuta nada) | Evaluación científica, Cohortes |
| `POST` | `/evaluation/cohorts/preflight` | `cohort_preflight_evaluation_cohorts_preflight_post` | Comprobación previa de una cohorte (no ejecuta docking ni la persiste) | Evaluación científica, Cohortes |
| `GET` | `/evaluation/cohorts/{cohort_id}` | `get_cohort_evaluation_cohorts__cohort_id__get` | Una cohorte congelada: definición, snapshot, resumen y filas | Evaluación científica, Cohortes |
| `POST` | `/evaluation/cohorts/{cohort_id}/runs` | `open_run_evaluation_cohorts__cohort_id__runs_post` | Abrir una corrida sobre una cohorte congelada | Evaluación científica, Cohortes |
| `GET` | `/evaluation/cohorts/{cohort_id}/runs/latest` | `read_latest_run_evaluation_cohorts__cohort_id__runs_latest_get` | Última corrida durable de una cohorte | Evaluación científica, Cohortes |
| `POST` | `/evaluation/dossier/{molecule_id}/package` | `dossier_package_evaluation_dossier__molecule_id__package_post` | Paquete reproducible del caso (ZIP con manifiesto y hashes) | Evaluación científica, Dossier de caso |
| `POST` | `/evaluation/dossier/{molecule_id}/preview` | `dossier_preview_evaluation_dossier__molecule_id__preview_post` | Dossier del caso en PDF (inline) | Evaluación científica, Dossier de caso |
| `GET` | `/evaluation/engines` | `listar_motores_evaluation_engines_get` | Qué motores de docking puede ejecutar esta instalación | Evaluación científica |
| `POST` | `/evaluation/engines/{motor_id}/encender` | `encender_motor_evaluation_engines__motor_id__encender_post` | Encender un motor descargable que ya está instalado | Evaluación científica |
| `POST` | `/evaluation/evaluate` | `evaluate_sync_evaluation_evaluate_post` | Evaluacion sincrona con SSE progress | Evaluación científica |
| `GET` | `/evaluation/files/complex/{molecule_id}` | `get_complex_file_evaluation_files_complex__molecule_id__get` | Complejo proteína-ligando fusionado (un único PDB para visualización 3D correcta) | Evaluación científica, Evaluación científica |
| `GET` | `/evaluation/files/poses/{molecule_id}` | `get_pose_file_evaluation_files_poses__molecule_id__get` | Descargar SDF de poses de docking | Evaluación científica, Evaluación científica |
| `GET` | `/evaluation/files/protein/{molecule_id}` | `get_protein_file_evaluation_files_protein__molecule_id__get` | Descargar PDB del target biológico | Evaluación científica, Evaluación científica |
| `GET` | `/evaluation/gnn-attention/{molecule_id}` | `get_gnn_attention_evaluation_gnn_attention__molecule_id__get` | Leer SVG de atención GNN on-demand (UI-7, fuera del polling) | Evaluación científica |
| `GET` | `/evaluation/interactions/{molecule_id}` | `get_interactions_evaluation_interactions__molecule_id__get` | Get Interactions | Interaction Analysis |
| `POST` | `/evaluation/preflight` | `evaluation_preflight_evaluation_preflight_post` | Comprobación previa factual de una corrida (no ejecuta docking) | Evaluación científica |
| `GET` | `/evaluation/result/{molecule_id}` | `get_evaluation_result_evaluation_result__molecule_id__get` | Leer resultado persistido de una molécula | Evaluación científica |
| `GET` | `/evaluation/status/{task_id}` | `get_evaluation_status_evaluation_status__task_id__get` | Consultar estado de un job de evaluación | Evaluación científica |
| `GET` | `/evaluation/stream/{task_id}` | `stream_pipeline_events_evaluation_stream__task_id__get` | Suscribirse al flujo de eventos del pipeline (SSE) | Evaluación científica |
| `POST` | `/evaluation/submit` | `submit_evaluation_evaluation_submit_post` | Enviar evaluación molecular asíncrona | Evaluación científica |
| `GET` | `/hardware` | `hardware_info_hardware_get` | Hardware detection and recommendations | Meta |
| `GET` | `/hardware/estimate` | `estimate_time_hardware_estimate_get` | Estimate evaluation time | Meta |
| `GET` | `/health` | `health_health_get` | Estado integral del sistema | Meta |
| `GET` | `/history/evaluations` | `list_evaluations_history_evaluations_get` | Listar evaluaciones del usuario | Historial de evaluaciones |
| `POST` | `/history/save/{molecule_id}` | `save_molecule_history_save__molecule_id__post` | Guardar molécula explícitamente en la cuenta | Historial de evaluaciones |
| `GET` | `/history/stats` | `get_stats_history_stats_get` | Estadísticas del usuario | Historial de evaluaciones |
| `GET` | `/moldex` | `get_moldex_moldex_get` | Obtiene el catálogo de moléculas evaluadas (Moldex) | Moldex |
| `POST` | `/pro/admet/{molecule_id}` | `run_admet_endpoint_pro_admet__molecule_id__post` | Perfil ADMET de una molecula ya evaluada, calculado despues del acoplamiento | PRO Features |
| `GET` | `/pro/anti-targets` | `list_anti_targets_pro_anti_targets_get` | List Anti Targets | PRO Features |
| `GET` | `/pro/gpu` | `gpu_status_pro_gpu_get` | Gpu Status | PRO Features |
| `POST` | `/pro/mmgbsa/{molecule_id}` | `run_mmgbsa_endpoint_pro_mmgbsa__molecule_id__post` | Run Mmgbsa Endpoint | PRO Features |
| `POST` | `/pro/selectivity/dock-target/{molecule_id}` | `dock_single_anti_target_pro_selectivity_dock_target__molecule_id__post` | Dock Single Anti Target | PRO Features |
| `POST` | `/pro/selectivity/save/{molecule_id}` | `save_selectivity_results_endpoint_pro_selectivity_save__molecule_id__post` | Save Selectivity Results Endpoint | PRO Features |
| `POST` | `/pro/selectivity/stream/{molecule_id}` | `run_selectivity_stream_pro_selectivity_stream__molecule_id__post` | Run Selectivity Stream | PRO Features |
| `POST` | `/pro/selectivity/{molecule_id}` | `run_selectivity_pro_selectivity__molecule_id__post` | Run Selectivity | PRO Features |
| `POST` | `/proteins/surgery/detect-metals` | `detect_metals_endpoint_proteins_surgery_detect_metals_post` | Detectar iones metalicos en estructura proteica | Protein Surgery |
| `POST` | `/proteins/surgery/dynamic-box` | `dynamic_box_endpoint_proteins_surgery_dynamic_box_post` | Calcular caja de docking optima desde ligando | Protein Surgery |
| `POST` | `/proteins/surgery/metal-features` | `metal_features_endpoint_proteins_surgery_metal_features_post` | Detectar grupos quelantes de metales | Protein Surgery |
| `POST` | `/proteins/surgery/prepare` | `prepare_target_endpoint_proteins_surgery_prepare_post` | Preparar receptor para docking | Protein Surgery |
| `POST` | `/proteins/surgery/validate-atoms` | `validate_vina_atoms_endpoint_proteins_surgery_validate_atoms_post` | Validar atomos compatibles con Vina | Protein Surgery |
| `POST` | `/rescore` | `rescore_inline_rescore_post` | Rescore Inline | Rescoring |
| `GET` | `/rescoring/health` | `rescoring_health_rescoring_health_get` | Rescoring Health | ML Rescoring |
| `GET` | `/rescoring/info` | `rescoring_info_rescoring_info_get` | Rescoring Info | ML Rescoring |
| `GET` | `/rescoring/ram` | `rescoring_ram_rescoring_ram_get` | Rescoring Ram | ML Rescoring |
| `GET` | `/sar/{molecule_id}` | `get_sar_table_sar__molecule_id__get` | Get Sar Table | SAR Analysis |
| `GET` | `/stats/global` | `get_global_stats_stats_global_get` | Get Global Stats | Estadísticas |
| `GET` | `/stats/leaderboard` | `get_leaderboard_stats_leaderboard_get` | Evaluaciones compartidas por afinidad observada | Estadísticas |
| `POST` | `/suggestions/generate` | `generate_suggestions_suggestions_generate_post` | Generar sugerencias de modificación molecular | Generación de novo |
| `GET` | `/targets/` | `list_targets_targets__get` | Listar todos los targets biológicos disponibles | Targets biológicos |
| `GET` | `/targets/alphafold/lookup/{uniprot_id}` | `alphafold_lookup_targets_alphafold_lookup__uniprot_id__get` | Buscar proteína en AlphaFold DB por UniProt ID | Targets biológicos |
| `GET` | `/targets/alphafold/search` | `alphafold_search_targets_alphafold_search_get` | Buscar proteínas por nombre de gen | Targets biológicos |
| `GET` | `/targets/community` | `get_community_targets_targets_community_get` | Targets compartidos por la comunidad | Targets biológicos |
| `POST` | `/targets/community/download/{pdb_id}` | `download_community_target_targets_community_download__pdb_id__post` | Descargar target de la comunidad | Targets biológicos |
| `POST` | `/targets/ingest` | `ingest_target_targets_ingest_post` | Ingesta científica de una nueva proteína | Targets biológicos |
| `POST` | `/targets/resolve-name` | `resolve_target_name_targets_resolve_name_post` | Buscar estructuras en RCSB PDB por nombre de proteína | Targets biológicos |
| `POST` | `/targets/upload` | `upload_custom_target_targets_upload_post` | Subir y preparar un target personalizado | Targets biológicos |
| `POST` | `/targets/{pdb_id}/variants` | `create_target_variant_targets__pdb_id__variants_post` | Crear una variante privada e inmutable de preparación | Targets biológicos |
| `GET` | `/targets/{target_id_or_pdb}/pdb` | `get_target_pdb_targets__target_id_or_pdb__pdb_get` | Descargar archivo PDB de un target por ID o PDB ID | Targets biológicos |
| `POST` | `/targets/{target_id}/share` | `share_target_with_community_targets__target_id__share_post` | Compartir un target privado con la comunidad | Targets biológicos |
