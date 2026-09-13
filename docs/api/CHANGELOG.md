# Changelog del contrato HTTP

Registro de los cambios **incompatibles** del contrato publicado en
[`openapi-current.json`](openapi-current.json). Las adiciones no se anotan aquí:
el mapa de [45_API_CONTRACT_CURRENT.md](../45_API_CONTRACT_CURRENT.md) y el
propio snapshot ya las llevan.

Por qué existe este archivo: `scripts/generate_openapi_contract.py` se niega a
escribir un snapshot con incompatibilidades salvo que se le pase
`--allow-breaking`. Esa bandera es una decisión, y una decisión sin registro es
una decisión perdida. Cada uso de `--allow-breaking` deja una entrada aquí.

## 2026-08-31 — se acepta la retirada de `GET /evaluation/limit-status`

**Regenerado con:** `python scripts/generate_openapi_contract.py --write --allow-breaking`
**SHA-256 del snapshot resultante:** `29f810895bea529ab1b933fd25becca99dd444abc622b874b3831ffc52e11d58`

### Qué se retira

| Método | Ruta | Operación |
|---|---|---|
| `GET` | `/evaluation/limit-status` | `get_limit_status_evaluation_limit_status_get` |

### Por qué

TRANS-ANON-002 retiró el cupo de evaluaciones gratuitas contado por dirección
IP. En un producto de escritorio local la IP es siempre `127.0.0.1`, así que el
cupo no medía personas sino máquinas, y ya estaba neutralizado con
`default=999`. Al desaparecer el cupo desapareció la única razón de ser del
endpoint, que sólo servía para preguntarle cuántas evaluaciones quedaban.

El código se retiró en un paquete anterior; lo que faltaba era **registrar la
ruptura**, porque regenerar el snapshot sin dejar constancia habría borrado la
única señal de que una ruta publicada dejó de existir.

### Comprobación de consumidores

- **Frontend:** ninguna llamada. `getLimitStatus` no existe en `frontend/lib/`
  ni en ningún componente.
- **Backend:** la ruta no está registrada en ningún router; `Repository` ya no
  expone `get_anonymous_limit` ni `increment_anonymous_count`.
- **Vigilancia permanente:** `backend/tests/test_sin_limite_de_evaluaciones_anonimas.py`
  falla si la ruta o sus contadores reaparecen, y
  `test_evaluacion_sincrona_comparte_gates.py` usa un repositorio espía que
  lanza si alguien vuelve a consultar la cuota.
- **Bases existentes:** la tabla `anonymous_limits` **no se borra**. Eliminarla
  sería destructivo para una base ya instalada y no aporta nada: queda inerte.

### Alcance

Anterior a 1.0. El contrato no tiene compromiso de compatibilidad publicado
todavía, y no hay integraciones externas conocidas. Después de 1.0 una retirada
como ésta exigiría un período de deprecación anunciado.

### Cambios aditivos que entraron en la misma regeneración

El snapshot llevaba varios paquetes sin registrar. Ninguno es incompatible, pero
conviene saber qué se incorporó al regenerar:

- `GET/POST /ai/consent` y `DELETE /ai/consent/{provider_id}` — consentimiento
  de destino por cuenta (MOLCHAT-NET-005).
- `GET /evaluation/cohorts/{cohort_id}/runs/latest` — recuperación de la última
  corrida de una cohorte desde el backend, sin depender de `localStorage`.
- Identidad opcional en las sondas de arranque de MolChat (`/ai/providers`,
  `/ai/status`), que pasaron a devolver la vista de la cuenta cuando hay sesión.
- Esquemas de Moldex (`MoldexCatalogRead`, `MoldexMetricsRead`,
  `MoldexMoleculeRead`, `MoldexProvenanceRead`, `MoldexSealRead`,
  `MoldexTargetRead`).
- `maxLength` en `ChatMessage.content` y `maxItems` en `AIChatRequest.messages`
  — topes de tamaño del turno de MolChat.
