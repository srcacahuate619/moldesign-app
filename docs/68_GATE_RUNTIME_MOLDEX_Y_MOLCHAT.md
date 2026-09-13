# Gates runtime de Moldex y MolChat — APROBADOS

**Fecha:** 2026-08-31
**Estado:** 🟢 ambos aprobados con motor real, con exclusiones nombradas
**Ejecutores reproducibles:** `scripts/accept_moldex_runtime.py`, `scripts/accept_molchat_runtime.py`

Los dos gates comparten el arnés de [`accept_evaluation_runtime.py`](../scripts/accept_evaluation_runtime.py)
—arranque del backend, espera, autenticación, parada— en vez de reescribirlo.
Tres arneses serían tres arneses que se desincronizan, y el que mintiera sería el
más nuevo.

Ninguno toca `~/MolDesign`: cada uno crea su SQLite, artefactos, logs y evidencia
dentro de `tmp/`.

---

## Moldex — APROBADO

**Evidencia:** `tmp/moldex-runtime-20260831T224033Z/`

| Criterio del expediente | Resultado |
|---|---|
| Corrida real con Vina/Meeko | afinidad `-5.489 kcal/mol`, molécula `1c7c5d48…` |
| Guardado en Moldex | la molécula aparece en el catálogo de su cuenta |
| Reinicio del backend | superado; segundo arranque sobre la misma SQLite |
| Recuperación por `task_id` exacto | afinidad idéntica tras reiniciar |
| Un `task_id` inexistente no devuelve resultado | verificado |
| Comparación compatible e incompatible | dos moléculas, dos protocolos distintos |
| Reevaluación no altera la corrida anterior | verificado: el snapshot es inmutable |
| Cuenta B no lista, ve, descarga ni certifica | `403/403/403/403/404`, certificar `403` |
| Descargas del dueño | poses `200`, complejo `200`, dossier PDF `200` |
| Ausencia de score ≠ cero ni D-Tier | verificado en el catálogo servido |

**Lo que este gate NO cubre, y hay que decirlo:**

- **No se emitió un sello real.** Certificar contra Solana devnet exige una
  cartera con fondos y red; el gate comprueba que la cuenta ajena **no puede**
  certificar, no que la propia sí. Con ello, tampoco se ejerció el estado «sello
  desfasado»: se verificó su precondición —que reevaluar deja intacta la corrida
  anterior— pero no la transición del sello. Queda ligado a la decisión
  devnet/mainnet del §7 del expediente de Moldex.

## MolChat — APROBADO

**Evidencia:** `tmp/molchat-runtime-20260831T225134Z/` (incluye `transcripcion.json`)

Ejecutado con el modelo local real: `llama-server.exe` + `qwen2.5-1.5b-instruct-q4_k_m.gguf`.

| Criterio | Resultado |
|---|---|
| Modelo local cargado y hablando | `startup_mode=auto_start`, proveedores resueltos |
| Pregunta que exige herramienta | `compute_properties` corrió: `MW: 180.2 Da, LogP: 1.31…` |
| El bloque llega clasificado | `[cálculo · RDKit (descriptores sobre el SMILES dado)]` |
| Evaluación lanzada desde el chat | `task_id=482ae3e4…`, sin número en ese turno |
| Entró por `registrar_corrida` | `receptor_sha256`, `docking_protocol` y `vina_version` presentes |
| La corrida terminó de verdad | afinidad `-5.5375 kcal/mol` |
| Reinicio y cita de la corrida | la corrida citada es la misma, verificado contra el backend |
| Abstención con corrida inexistente | ninguna afinidad inventada |
| Cuenta B no lee la corrida de A | `403` |
| El chat de B no menciona el trabajo de A | verificado sobre el texto |
| Conversaciones separadas | alice 2, bob 1, sin intersección |
| Advertencia de calibración en el chat | «⚠️ Este receptor no tiene Spearman ρ medido…» |

### Dos fallos reales que encontró este gate

**1. El texto del investigador rompía la búsqueda del historial — HTTP 500.**
La primera pregunta real, con un SMILES dentro, devolvió:

```
PersistenciaFallida: ai_memory.db falló la operación: no such column: SMILES
```

`search_chat_history` construía la expresión `MATCH` pegando las palabras del
mensaje. En FTS5, `algo:` es un filtro por columna, `"` abre un literal, `*` es
prefijo y `NEAR`/`AND`/`OR`/`NOT` son operadores: «calcula las propiedades de
este SMILES: CC(=O)O» se convertía en una consulta contra una columna
inexistente. El texto de quien pregunta entraba **sin escapar** en un lenguaje de
consulta; la forma de esto es una inyección, aunque aquí sólo alcanzara a romper
la búsqueda.

Y era invisible hasta ahora porque MOLCHAT-BE-008 acababa de dejar de tragarse
los errores de `ai_memory.db`. Esa corrección es correcta para la conversación
—perder un turno guardado importa— pero el índice de búsqueda es **derivado**:
si falla, se degrada la búsqueda, no el turno. Se corrigieron las dos mitades.
Regresión: `backend/tests/test_busqueda_fts_no_rompe_el_turno.py`, `11 passed`.

**2. Una corrida lanzada desde el chat tenía menos procedencia que una de la
pestaña.** Llegaba sin `docking_protocol`: el pipeline sólo lo sella cuando
`properties` y `docking` corrieron ambas, y `run_docking` no enviaba
configuración explícita. Contradecía el criterio 1 de D-08 —el mismo camino—
justo en la superficie donde el número se narra. Ahora la herramienta envía un
`pipeline_config` explícito y modesto: el chat lanza en segundo plano mientras el
investigador sigue escribiendo, y no es el sitio para arrancar el pipeline más
caro sin pedirlo.

**Lo que este gate NO cubre:**

- **Un proveedor remoto real.** Sólo se ejercitó el motor local. El camino
  remoto tiene su consentimiento por destino cubierto por suite
  (`test_consentimiento_destino_remoto.py`), pero no se llamó a ninguna API de
  pago.
- **La calidad de las respuestas.** El gate comprueba que la herramienta corre,
  que el dato se cita y que no se inventa nada. No juzga si el modelo redacta
  bien: eso depende del modelo cargado y no es un contrato del producto.

---

## Verificación automatizada tras ambos gates

- backend completo: **`1263 passed`** con el intérprete de desarrollo y
  **`1225 passed, 3 skipped`** con `python-embed`. Las cifras se generan con
  `scripts/report_test_counts.py`; `docs/api/test-counts.json` es el registro y
  `--check` falla si una suite deja de recolectar en silencio
- frontend completo: **`638 passed`** en 66 archivos
- `tsc --noEmit`: limpio
- gates runtime: Evaluación `PASS`, Batch `PASS`, Moldex `PASS`, MolChat `PASS`

Evaluación y Batch se re-ejecutaron **después** de cambiar la política de
propiedad (se retiró el espacio anónimo compartido), como exige el protocolo:
un cambio de autorización invalida los gates anteriores.
