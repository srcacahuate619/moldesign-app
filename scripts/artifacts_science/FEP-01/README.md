# FEP-01

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

La integridad quimica del ligando (estereo, tautomero, protonacion, carga, atom mapping) esta declarada en el material actual

## Protocolo

Referencia: `auditoria sin docking sobre los 203 de train+val/test; centros quirales sin asignar, dobles sin estereo, enumeracion de tautomeros y biyectividad del index_map`

## Gate

auditoria sin gates; se cuenta cuantos complejos pasarian los cuatro campos

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `6bae87c3cda6de687a37b19f2b7dd219cd53e053`, dirty=True

## Estado

- Creado: 2026-08-19T03:53:16.948926+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-19T03:53:17.738656+00:00)
- Finalizado: 2026-08-19T03:53:17.911928+00:00
- Razón de la decisión: Solo 39 de 203 complejos (19%) pasan hoy los cuatro campos. Dos campos estan LIMPIOS y contradicen la sospecha de partida: 138 ligandos tienen centros quirales y CERO estan sin asignar, pese a que el pipeline llama a Molecule.from_rdkit con allow_undefined_stereo=True -ese flag permite algo que en la practica no ocurre-; y el atom mapping es biyectivo y cubre los pesados en los 203, lo que verifica por primera vez la base de todos los RMSD del programa. El cuello es el TAUTOMERO: 164 de 203 (81%) tienen mas de un tautomero enumerable y 48 alcanzan el tope de 10. El pipeline no declara cual usa. Para docking con Vina apenas importa; para FEP+ es determinante, porque el tautomero define que atomos donan y cuales aceptan puentes de hidrogeno. Limitacion: la enumeracion de RDKit es heuristica de transformaciones, no calculo de poblaciones; >1 senala AMBIGUEDAD NO DECLARADA, no error.
- Hashes de assets: 1 archivo(s) con SHA-256

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
