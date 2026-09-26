# Fase 7 — bitácora de calidad y eficiencia

Fecha: 2026-09-25. Rama local: codex/audit-phase-7. Worktree: D:\moldesign-build\.worktrees\audit-phase-7. Padre: d5707975ce770004f780c8707466af14ccaac1f2 (fase 6). Commit local de fase 7: 06d27b670e551b9322ee747f41ccd23cf551ec1b. No se hizo push ni se modificó main. El árbol del worktree quedó limpio. Los temporales y la caché de pytest se dirigieron a D:\moldesign-build\.worktrees\audit-phase-7\.tmp; se reutilizó el intérprete embebido y el node_modules anterior mediante junctions. No se instaló software en C.

## Decisión general

La fase 7 mezclaba defectos de ejecución, errores de contrato y discrepancias de features que exigirían reentrenamiento. Corregí los caminos de ejecución y la procedencia que podían arreglarse sin cambiar pesos científicos. Dejé SCORE-018 **parcial**: la pose elegida por Model A queda declarada, pero no alteré los conteos de contactos ni la definición de poses_passing_ratio con un modelo ya entrenado. La reconstrucción y evaluación de XGBoost, junto con MMGBSA y TabPFN, pertenece a la sesión de rescate científico solicitada por el usuario. Ninguna de esas tecnologías se declara validada o reactivada por esta fase.

| Hallazgo | Resultado verificable | Límite |
|---|---|---|
| PROV-018 | /evaluate y batch registran EvaluationRequestORM y usan el dispatcher; el Vina del backend comparte un candado entre procesos. | El candado coordina procesos que comparten local_data_dir. |
| ORQ-004 | El batch ya no publica num_workers; corre en serie y no divide su estimación por un paralelismo inexistente. | Los 25 s por combinación siguen siendo una estimación, no una medida. |
| ORQ-005 | Prueba de latidos con trabajo bloqueante determinista de 0,2 s. | La prueba ADMET real se omite si termina en menos de 0,1 s: no sería una medición de bloqueo. |
| ORQ-006 | Logs de llama-server y ESMFold fuera del árbol de instalación, en directorios de datos o temporales de prueba. | No se construyó instalador en esta fase. |
| API-017 | Traducción por clave exacta en campos de mensaje; nombres y datos del usuario se conservan. | Los mensajes dinámicos no presentes como clave exacta permanecen sin traducir. |
| SCORE-018 | Rescoring devuelve pose_rank_used y vina_score_used y avisa si Model A usa otra pose. | Paridad de close_contacts y poses_passing_ratio pendiente de reentrenamiento y validación. |
| SCORE-020 | Retiradas funciones CL-GNN/ProLIF sin llamadores; el monitor deja la normalización antigua como no evaluable y el CLI no propone el parámetro inerte. | La recalibración real del motor LE requiere un nuevo protocolo. |
| SCORE-021 | ml_result se inicializa antes del bloque que puede fallar. | No cambia el comportamiento del predictor. |
| ENG-A15 | Eliminada get_anti_target_list, función muerta que perdía anti-dianas personalizadas. | El endpoint vivo de anti-dianas se conserva. |
| ENG-A18 | AlphaFold ya figuraba en services.ai.red.DESTINOS; se documentó en config.py y se añadió una prueba rutas ↔ inventario. | AlphaFold sigue siendo una fuente externa explícita, no un motor local. |
| API-019 | 404 uniforme en blockchain; mensajes sin rutas locales; errores de red controlados; carga de 31 MiB bajo el límite HTTP de 32 MiB; ajuste de proveedor inerte eliminado; descarga y apertura de modelos LLM usan la misma carpeta. | No se hizo una auditoría general de todas las respuestas API fuera de los sitios señalados. |
| PHYS-008 | SMARTS ajustados para formas ionizadas y azoles N-sustituidos; excluyen sulfonamidas terciarias y carbamatos; docstring veraz. | Son rasgos diagnósticos; no se conectaron a XGBoost ni se alteró UMS/M5 sellado. |
| PHYS-012 | La ruta opcional de refinamiento peptídico deja aviso PEPTIDE_REFINEMENT_NO_VALIDADO y conserva la pose original. | OpenMM/Amber y el respaldo UFF requieren una validación separada antes de reactivarse. |

## Ejecución y procedencia: PROV-018 / ORQ-004

El SSE de /evaluation/evaluate llamaba al pipeline directamente y publicaba un task_id truncado. Ahora crea la solicitud durable antes de iniciar la corrida, consulta el estado del dispatcher y envía el identificador completo. El evento final utiliza el snapshot de esa tarea; ya no relee una proyección mutable que podría corresponder a una corrida posterior. El error SSE público es genérico, y el detalle operativo queda en el estado de la tarea.

Cada par molécula–diana del batch se registra del mismo modo antes de esperar el resultado. El estado del lote expone active_task_id mientras corre. POST /evaluation/batch/{batch_id}/cancel verifica el propietario, solicita cancelar el trabajo activo y omite las filas pendientes; el estado final queda cancelled. El parámetro num_workers se retiró del contrato OpenAPI porque el bucle siempre fue secuencial. Se conserva num_workers=1 sólo como metadato interno de compatibilidad.

Un semáforo local de un permiso y un FileLock bajo local_data_dir rodean exactamente la creación y espera del proceso Vina. El candado de archivo cubre otros procesos MolDesign que usan ese mismo directorio, incluido selectivity_subprocess. Como el límite efectivo es un Vina, se mantiene vina_cpu=0; sólo un hijo puede utilizar todos los núcleos a la vez. Se comprobó con seis tareas simuladas concurrentes, una cancelación y un segundo proceso real que sostuvo el candado durante 0,5 s. La liberación tras cancelación se verifica.

## Ciencia y comportamiento conservador

SCORE-018: el filtro geométrico puede descartar la pose 1. Model A extrae de la primera pose válida; la respuesta ahora identifica su índice de entrada y su afinidad Vina, también por el puente directo de escritorio, y advierte la discrepancia. No se cambió la afinidad principal del motor ni el vector de features entrenado. La paridad entre SDF con hidrógenos completos y PDBQT con hidrógenos polares, y la diferencia de significado de poses_passing_ratio, siguen abiertas. Corregirlas exige generar datos de entrenamiento compatibles, reentrenar y repetir las puertas científicas.

PHYS-008: se probó un panel propio de 26 SMILES, con ácidos/carboxilatos, tiol/tiolato, sulfonamidas primarias/secundarias frente a terciarias, hidroxamatos, imidazoles N-sustituidos y bencimidazol, además de controles negativos. metal_features sólo sirve de diagnóstico y endpoint; no modifica el scorer. No se unificaron sus SMARTS con UMS/M5 porque esos protocolos y sus umbrales tienen evidencia sellada propia; esa migración requiere una nueva versión y evaluación.

PHYS-012: el XML OpenMM legado no representa una ruta validada y UFF podía devolver una geometría sin declarar qué ocurrió. Si se solicita el refinamiento opcional, se informa explícitamente y se preserva la pose original. La función pública de refinamiento rechaza la invocación directa para impedir que un consumidor futuro lo trate como resultado refinado. El código experimental privado permanece disponible para la sesión de rescate, sin quedar conectado al flujo de producto.

SCORE-020: el CLI de recalibración no participaba en producción y proponía affinity_normalization_range, que el motor actual no lee. El control de cobertura antiguo informa UNABLE y el CLI deja de proponer ese ajuste; una prueba impide reintroducirlo. Se quitaron dos funciones CL-GNN/ProLIF sin llamadores que embebían un confórmero aleatorio y un divisor arbitrario. Esto no toca el CL-GNN que sí se usa.

## API, red y archivos

API-017: localize_payload sólo traduce campos semánticos de mensaje. Se retiró el barrido de todo el catálogo por cada cadena y el reemplazo de subcadenas, que podía modificar nombres de dianas y datos suministrados por el usuario. Las cadenas sin traducción exacta se conservan.

API-019: blockchain responde 404 tanto para moléculas inexistentes como ajenas; los mensajes públicos de RCSB, evaluación y archivos de receptor no incluyen rutas absolutas. AlphaFold y la descarga comunitaria responden 503 ante fallos de conexión; 403 queda reservado al bloqueo de la puerta de red. El límite de archivo de diana se fijó en 31 MiB para dejar margen al sobre multipart bajo BodyLimitMiddleware de 32 MiB. Se eliminó provider_config_path, que ningún consumidor leía. Los modelos descargados desde Hugging Face aterrizan en la carpeta que abre /ai/models/open-folder.

ENG-A18: los dos endpoints AlphaFold montados se contrastaron con alphafold@alphafold.ebi.ac.uk en el catálogo de destinos, que ya existía al partir de fase 6. La documentación de config.py ahora distingue ese servicio activo de los routers dormidos.

## Verificación y límites

Sobre el commit 06d27b6, con python-embed 3.11.9 y MOLDESIGN_TESTING=1: 164 pruebas backend focalizadas pasaron, 1 se omitió y hubo 4 advertencias de pytest, en 33,28 s. La omisión corresponde a la prueba de latido del ADMET real, que no alcanzó el umbral de duración; el caso determinista de bloqueo sí pasó. El panel PHYS-008 aporta 26 casos. La suite rescoring separada terminó 17/17 y la peptídica separada 10/10. Se separaron porque ambas importan un módulo llamado config y ejecutarlas en un mismo proceso de pytest causa una colisión de importación del arnés, no del producto. git diff --check quedó limpio y el worktree quedó sin cambios tras el commit.

No se ejecutó el conjunto completo de más de 2500 pruebas, ni se construyó instalador, ni se midió rendimiento de Vina real; la verificación de concurrencia usó procesos ligeros y dobles de Vina. Tampoco se ejecutó un benchmark científico nuevo en el servidor, pues la fase 7 no alteró pesos ni predicciones entrenadas. No se consultó Internet. El auditor debe decidir la integración a main y mantener SCORE-018 como deuda explícita para la sesión de rescate.
