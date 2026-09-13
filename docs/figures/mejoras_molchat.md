35_MOLCHAT_PRODUCTION_READINESS.md — Guía de implementación de mejoras
Estado: Draft de integración — pendiente de revisión

Autor: Sesión de robustecimiento MolChat (agosto 2026)

Scope: Backend (services/data/, services/api/observability.py, api/routers/history.py, services/ai/security/middleware.py, tests/adversarial_suite.py), Infraestructura (infra/).

Continúa: 34_MOLCHAT_V3.md — base determinista y verificada.

0. Resumen ejecutivo
MolChat v3 ha demostrado que la separación entre lógica factual (Python) y explicación conceptual (LLM) elimina alucinaciones, reduce latencia y garantiza corrección química. Este documento detalla cómo escalar el sistema hacia producción sin comprometer su arquitectura híbrida: gestión de datos a largo plazo, observabilidad, multi-tenancia segura, testing adversarial y orquestación de modelos. Todas las propuestas respetan el principio rector: "el código decide lo factual, el modelo explica lo conceptual".

1. Contexto y principios de implementación
Principio	Aplicación en esta fase
Determinismo primero	Las mejoras son aditivas (auditoría, enrutamiento ligero, lifecycle); nunca reintroduce el LLM como fuente de verdad factual.
Observabilidad transparente	Cada respuesta incluye metadata de proveniencia y acceso controlado a datos crudos.
Multi-tenancia estricta	user_id validado en capa de aplicación y base de datos; nada se comparte entre sesiones sin explícita autorización.
CI/CD determinista	La suite de calidad se expande con casos adversariales y se añade regresión de latencia a pipelines automáticas.
2. Componentes a implementar
2.1 services/data/session_lifecycle.py (NUEVO)
Objetivo: Gestionar el crecimiento indefinido del historial tras eliminar la puerta is_saved.
Implementación:
Particionamiento lógico por user_id + rangos de created_at (0–2 años: caliente; >2 años: frío/parquet).
Tareas asíncronas (Celery/RQ o asyncio.Task) que ejecuten compactación y archival sin bloquear /chat.
Endpoint /history/archive?user_id=...&before=YYYY-MM-DD para limpieza manual.
Tradeoff: Slightly más complejidad operativa a cambio de escalabilidad ilimitada y cumplimiento de retención.
2.2 services/api/observability.py (NUEVO) + api/routers/ai.py (MODIFICADO)
Proveniencia en respuestas: Cada respuesta determinista incluye un campo "provenience": "tool_result" | "history_tool_text" | "template".
Debug toggle: GET /chat?show_raw=true devuelve el JSON crudo del tool + la respuesta final. Útil para auditoría y integración con dashboards químicos.
Audit Trail: tabla separada evaluations_audit(id, user_id, query_hash, source_tool, status, timestamp) que graba solo metadatos operativos (no datos sensibles).
2.3 services/ai/security/middleware.py (NUEVO)
Filtrado estricto: Validación de user_id en cada tool (query_history, rank_session_molecules, etc.) antes de cualquier consulta a DB o memoria.
Row-Level Security (RLS): En PostgreSQL, aplicar políticas como CREATE POLICY user_eval_policy ON evaluations USING (owner_id = current_user_id);. En SQLite/demo, validación estricta en Python.
Rate Limiting: Redis-based sliding window (60 req/min/IP o 100 req/hr/user) con header X-RateLimit-Remaining.
2.4 services/ai/classifier.py + _METRICS (MODIFICADO)
Fallback estructurado: Si la pregunta cae fuera del vocabulario de sinónimos, el sistema no delega ciegamente al LLM. Retorna un template de clarificación: "¿Molécula A o B? ¿Unidad de medida preferida?".
Expansión semántica ligera (opcional): Integrar sentence-transformers ligero (<0.2GB) para detectar sinónimos químicos no listados ("acetil salicílico" → "aspirina"). Solo activa en dev/test hasta validación adversarial.
Fix de anáfora cruzada: Reforzar _last_shared_smiles con fallback a query_history cuando el contexto actual sea < 3 tokens o contenga ambigüedades estéricas.
2.5 tests/adversarial_suite.py (NUEVO — extensiones)
Casos añadidos:
Nombres ambiguos ("ibuprofeno" vs "fenóxiibuprofeno")
Unidades mixtas (g/mol, kg/mol, mg/kg)
Anáforas de múltiple turno con cambios de contexto químico
SMILES malformados o tautólogos que deben ser rechazados honestamente
Validación: Añade assertions en p95/p90 latencia y verifica que las respuestas deterministas nunca cambien sin cambios de datos.
2.6 services/ai/model_router.py (NUEVO — opcional avanzado)
Enruta consultas conceptuales simples (< 15 tokens, sin términos técnicos complejos) a modelos <0.3B para reducir consumo.
Escala a Qwen 2.5-1.5B solo cuando se detectan: razonamiento multi-paso, mención de mecanismos metabólicos, o longitud > 30 tokens con alta entropía léxica.
Se implementa como feature flag; por defecto permanece en el modelo base verificado.
3. Roadmap de integración
Fase	Plazo	Deliverables	Impacto
Fase 1 (Fundamento)	5-7 días	Observability, provenience, audit trail, /chat?show_raw, RLS checks básicos, rate limiting.	Transparencia inmediata, seguridad mínima para multi-tenant.
Fase 2 (Resiliencia)	10-14 días	session_lifecycle.py (async archival), expansión adversarial de suite, fallback estructurado, indexación optimizada.	Escalabilidad de datos, reducción de fallos en edge cases.
Fase 3 (Orquestación)	2-3 semanas	model_router, CI/CD con regresión de latencia, health checks, containerización hardened, monitoring métricas p95/p99.	Produção estable, observabilidad completa, escalabilidad controlada.
4. Decisiones de arquitectura (ADRs implícitos)
ADR	Problema	Decisión	Tradeoff
A1: Observability sin ruido	Auditar cada consulta sin inflar latencia o DB.	Metadata ligera en JSON + tabla de audit separada.	Slight increase in memory footprint; compensado con batching asíncrono.
A2: Multi-tenancia estricta desde el día 1	Partir un sistema multi-sesión a producción sin filtrado.	Validación en middleware + RLS/DB policy.	Requiere migración incremental de user_id a todas las tools.
A3: Fallback determinista ante ambigüedad	Delegar a LLM cuando el clasificador falla.	Template de clarificación o error estructurado.	Respuestas menos fluidas, pero 0 alucinaciones y latencia <10ms.
5. Limitaciones conocidas durante la implementación
Particionamiento de DB: Si se usa SQLite para demo/test, el archival debe ejecutarse en Python puro; en Postgres se aprovechan pg_partman o índices partitionados.
Model routing dinámico: Requiere métricas de complejidad léxica/semántica validadas contra la suite adversarial antes de producción.
Audit Trail tamaño: Se recomienda rotación automática de logs > 90 días a archives compactos; no se almacenan payloads completos por default.
6. Cómo continuar
Validar Phase 1 con python -m tests.adversarial_suite --phase=1 y verificar que la suite original mantenga 43/43.
Integrar observabilidad en el endpoint /chat y confirmar que show_raw=true no impacta latencia determinista (<5ms overhead).
Ejecutar archival de prueba con dataset histórico real; ajustar TTL y compresión según métricas de almacenamiento.
Rodeo CI/CD: añadir checks de latencia p95, validación de RLS, y suite adversarial en GitHub Actions/GitLab CI.
✅ Este documento puede ejecutarse como checklist de integración. Todas las modificaciones son compatibles con la arquitectura v3 y no reintroducen dependencias del LLM para datos factuales.

Para snippets de código, migrations de DB o configuraciones Docker específicas, solicita el módulo correspondiente y se genera el artifact listo para git add.