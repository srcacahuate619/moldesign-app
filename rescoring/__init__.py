"""
rescoring — Microservicio de ML Rescoring para MolDesign.

Módulos principales:
  - app: API FastAPI (endpoints /health, /info, /rescore)
  - model_manager: Carga y gestión de modelos entrenados
  - feature_extractor: Extracción de features 1D/2D/3D
  - pose_filter: Filtro geométrico de poses de docking
  - applicability_domain: Verificación Mahalanobis de dominio
  - config: Configuración del microservicio
  - logger: Logging estructurado

Módulos de entrenamiento (Fase 2):
  - pdbbind_parser: Parser para PDBbind refined set
  - vip_audit: Auditoría de calidad de complejos
  - structural_family: Clasificación de proteínas por familia
  - data_splitter: Scaffold-split CV y frozen test set
  - train_pipeline: Pipeline de entrenamiento XGBoost LTR
  - train_orchestrator: Orquestador end-to-end de 14 pasos
"""
