# SUP-03-VALIDADOR-LIGANDO

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

Las cuatro reglas bloqueantes del validador del ligando (carga neta y atomica mayor que 2 en valor absoluto, radicales, varios fragmentos tras quitar sales) no rechazan moleculas con actividad medida

## Protocolo

Referencia: `scripts/artifacts_science/SUP-03-VALIDADOR-LIGANDO/entrada/REGISTRO_PREVIO.md`

## Gate

Por regla: GO si rechaza 0 moleculas con actividad medida; si rechaza alguna, NO_GO (la regla bloquea quimica real y, por la preferencia del propietario, deberia avisar y no bloquear salvo que el pipeline no pueda ejecutarla)

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.11.9
- Seeds: 42
- Git: rama `codex/release-hygiene`, commit `52cfa4523854c7c09187d30fd444872a555f2aa6`, dirty=True

## Estado

- Creado: 2026-10-25T18:34:52.111737+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-10-25T18:40:31.840497+00:00)
- Finalizado: 2026-10-25T18:40:32.447547+00:00
- Razón de la decisión: Las cuatro reglas bloqueantes del validador (carga neta y atomica >2 en valor absoluto, radicales, varios fragmentos tras SaltRemover) rechazan 0 de 640 moleculas con actividad medida (VMAT2 89, NET 57, 5-HT1A 494). En los descriptivos, R4 rechaza 6 solvatos; 19 con boro y 49 peptidos > 1000 Da caen por otras reglas.
- Hashes de dataset: 5 archivo(s) con SHA-256
- Hashes de assets: 2 archivo(s) con SHA-256

## Flujo de trabajo

1. `init`: crea este directorio con `manifest.json` prellenado y skeletons vacíos.
2. Ejecutar el experimento: escribir `metrics.json`, `per_complex.jsonl` y `failures.jsonl`.
3. `validate`: verifica `manifest.json` contra `manifest.schema.json`.
4. `seal`: registra los SHA-256 de datasets/modelos/binarios/assets y congela el manifest.
5. `finish`: escribe la decisión (GO/NO_GO/INCONCLUSIVE), la razón y la duración.
6. `maintain`: documenta de forma auditada los assets sellados que cambian tras el sello.

Después del `seal`, `validate` falla si cualquier archivo sellado cambia o desaparece.

## Inmutabilidad post-seal

- No se permite volver a sellar un experimento ya sellado (protege el cegamiento FND-05).
- `finish` y `maintain` son las únicas operaciones que modifican `manifest.json` después del sellado.
- `maintain` solo actualiza `assets_hashes` y registra cada cambio en `seal_maintenance`; datasets/modelos/binarios son inmutables.
- El README.md regenerado por `seal`/`finish`/`maintain` es la excepción documentada a la regla anterior.
- Los artefactos de producción permanecen fuera de este árbol (docs/49, sección 17).

## Archivos

- `manifest.json`: registro único del experimento (config, hashes, código, ambiente, salida).
- `metrics.json`: métricas agregadas del experimento.
- `per_complex.jsonl`: una línea JSON por complejo evaluado.
- `failures.jsonl`: una línea JSON por fallo.
- `README.md`: este archivo.
