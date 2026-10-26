# RS-03-PARAM-A-R1

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

RS-03-PARAM-A declaro energia finita, serializable y mapeo biyectivo sin calcularlos: medidos sobre los 116 ligandos reconstruidos en el mismo contenedor (SCI-B-155, SCI-B-156)

## Protocolo

Referencia: `RS-03-PARAM-A-R1/PREREGISTRO.md (7dccb5dd); scripts/run_rs03_param_a_r1.py en moldesign-science (openff-toolkit 0.18.0, openmm 8.5.2, NAGL 1.0.0 sha 7981e7f5), 4 trabajadores, sin docking`

## Gate

G0 entradas, G1 cargas <=1e-5, G2 energia finita 116/116, G3 serializacion <=1e-6 kJ/mol, G4 correspondencia indice a indice y particulas=atomos, G5 controles negativos detectados

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.11.9
- Seeds: 42
- Git: rama `claude/fase-1b`, commit `7dccb5ddb4deccfbe8db9024c4e9e64531794a78`, dirty=True

## Estado

- Creado: 2026-10-22T20:40:19.077690+00:00
- Status: finished
- Decisión: NO_GO
- Sellado: sí (2026-10-22T20:40:43.814809+00:00)
- Finalizado: 2026-10-22T20:40:44.577043+00:00
- Razón de la decisión: NO_GO preregistrado: 1nw5 (tiol con H implicito) da 52 particulas para 51 atomos del SDF, asi que el mapeo biyectivo declarado por RS-03-PARAM-A no existe ahi. En los otros 115: entradas iguales, cargas a 5e-7 e, energia finita y serializacion exacta (dE=0), y elementos, cargas y conectividad identicos indice a indice; 31 fallan el criterio preregistrado solo por la etiqueta aromatica del enlace (diagnostico posterior declarado). Controles 229/229.
- Hashes de dataset: 1 archivo(s) con SHA-256
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
