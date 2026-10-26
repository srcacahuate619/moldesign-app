# MF-33-EXT-MOD-R1

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

El BLOQUE 3 de MF-33-EXT-MOD (regla de decision) no se ejecuto: cuatro de cinco predictores quedaron vacios en los 68 externos. Calculados con el productor de MF-33-DOSIS, decide si algun descriptor estatico sobrevive BH q=0.05 (SCI-B-131)

## Protocolo

Referencia: `MF-33-EXT-MOD-R1/PREREGISTRO.md (01395459); scripts/run_mf33extmod_r1.py importa sin modificar los productores sellados de MF-33-DOSIS y MF-33-EXT-MOD; CPU local, sin docking`

## Gate

G0 reproduccion exacta de MF-33-DOSIS en los 48; G1 completitud >=65/68; GO si alguno de torsdof/rot_bonds/diversidad/n_heavy sobrevive BH, NO_GO si ninguno

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.11.9
- Seeds: 42
- Git: rama `claude/fase-1b`, commit `013954592e94efea8fa22a18f9fe77f16ba2533b`, dirty=True

## Estado

- Creado: 2026-10-22T20:46:58.417342+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-10-22T20:47:57.022507+00:00)
- Finalizado: 2026-10-22T20:47:57.874579+00:00
- Razón de la decisión: GO preregistrado: reproduccion exacta de MF-33-DOSIS en los 48, completitud 65/68, y torsdof, rot_bonds, diversidad y n_heavy sobreviven BH en los 68 externos (rho 0.33-0.43); control barajado sin supervivientes. Diagnostico posterior declarado: controlando n_conformeros (K, confundido con la dosis) ninguno conserva asociacion (rho parcial -0.17 a -0.09): candidatos segun el PRE, sin senal propia mas alla de K.
- Hashes de dataset: 2 archivo(s) con SHA-256
- Hashes de assets: 4 archivo(s) con SHA-256

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
