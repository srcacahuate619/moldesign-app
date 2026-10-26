# REC-07-R1

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

Con la Cys25 dentro del receptor acoplado (altloc coherente), el control de docking de REC-07 sigue colocando E64c a <= 5 A de Cys25 SG en el grid recomendado: el resultado de REC-07 no dependia de la ausencia de la cisteina

## Protocolo

Referencia: `scripts/artifacts_science/REC-07-R1/PREREGISTRO.md (repeticion de REC-07 con altloc coherente y aborto sin ancla; SCI-B-022)`

## Gate

G0 ancla en el receptor + G1-G7 de REC-07 sin cambios; GO = los ocho pasan

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.11.9
- Seeds: 42
- Git: rama `claude/fase-1b`, commit `422b89316a8c1fbde233e3f816fe45bd8876a6be`, dirty=True

## Estado

- Creado: 2026-10-22T17:38:35.213916+00:00
- Status: finished
- Decisión: NO_GO
- Sellado: sí (2026-10-22T17:53:05.526344+00:00)
- Finalizado: 2026-10-22T17:53:05.676591+00:00
- Razón de la decisión: Con la Cys25 dentro del receptor (G0 PASS: SG, NE2 y ND2 a 0,0 A del PDB), el grid recomendado G_ADAPT no coloca E64c en contacto con Cys25 SG en ninguna de 5 semillas (top-1 a 12,95-13,06 A, score mediano -5,30); G_MP igual (12,91-13,06 A). Fallan G4 (0 de 5) y G5 (G_DB 4 de 5). Solo la caja actual del catalogo G_DB llega a <=5 A (2,46-5,89 A, mediana 3,09) con scores pobres (-0,94 a -3,17) y 7-8 modos; dos de sus distancias bajan de 3 A, lo que el preregistro advertia como posible choque. G0, G1, G2, G3, G6 (3 repeticiones identicas) y G7 pasan. El contacto 5/5 de REC-07 era el ligando en el hueco de la Cys25 ausente: su recomendacion de G_ADAPT queda refutada, y la geometria de cajas (G1, G2) no cambia. Corrige SCI-B-022.
- Hashes de dataset: 2 archivo(s) con SHA-256
- Hashes de binarios: 1 archivo(s) con SHA-256
- Hashes de assets: 6 archivo(s) con SHA-256

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
