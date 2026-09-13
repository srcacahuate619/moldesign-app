# `services/ai/experimental/` — Código experimental archivado

Este directorio contiene módulos que fueron implementados, descartados en
producción por incompatibilidad técnica, pero **preservados como plantilla**
para futuras investigaciones.

## Diferencia con "deprecated"

`experimental/` ≠ `deprecated/`. Lo deprecated dejará de funcionar en la
próxima release y debe migrarse. Lo experimental **nunca estuvo activo en
producción** — es deuda documentada, no pendiente de migración.

## Contenido actual

### `chemistry_draft.py`

Speculative decoding draft model para `llama-cpp-python`. Implementa
`LlamaDraftModel` con n-gram lookup (prompt-lookup style) más un fallback
safety que evita el crash de array vacío en CUDA del draft original de la
comunidad.

**Status:** Descartado en producción — la familia Qwen 2.x no soporta bien la
API `draft_model=` de `llama-cpp-python`.

**Preservado por:** si en el futuro experimentan con Phi-3 mini, Llama 3.2
o Gemma 2 (que sí tienen soporte MTP más estable), este draft es el punto
de partida. No fue un failure de implementación — fue un failure de modelo.

**History:** Parte original en `services/ai/local_llm_draft.py` (eliminado al
migrar a `llama-server.exe`, ver `docs/33_MIGRATION_LLAMA_SERVER.md §4.D5`).
El bloque MTP en `local_llm.py` (`MOLCHAT_MTP` env var, rama `n_gpu != 0`)
también se eliminó por la misma razón.

## Cómo reactivar si en el futuro querés probar de nuevo MTP

1. Elegí un modelo que SÍ soporte MTP nativo (ver comunidad `llama-cpp-python`
   issues sobre `draft_model=` con tu modelo candidato).
2. Reinstalá el bloque MTP en `local_llm.py` (o `local_llm_server.py` si ya
   migraste):
   - Importá `ChemistryDraftModel` desde `experimental.chemistry_draft`.
   - Inyectá `draft_model=ChemistryDraftModel(...)` a la constructor Llama.
3. Activá la feature flag con `MOLCHAT_MTP=1`.
4. Corré benchmarks antes de promocionar a producción.
