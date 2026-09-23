# MMGBSA-PARTICIONES-BRI-V1

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

Asignacion fija de los 122 ligandos de PDBBind con Br o I a entrenamiento, validacion y prueba (60/20/20) por scaffold de Bemis-Murcko, sin ningun scaffold compartido entre particiones, para reutilizarla sin cambios en H1, H2, H3 y H10 de docs/validacion_mmgbsa.md.

## Protocolo

Referencia: `backend/audits/lcpo_bri_h1.py curar y particionar (RDKit 2025.09.6, esta maquina, sin mirar ninguna energia ni area): grupos por scaffold (aciclicos por InChIKey), orden SHA-256(semilla:grupo), cada grupo a la particion con mayor deficit relativo, por separado para ligandos con Br y con I. Semilla 20260923. Determinista: tres ejecuciones dan la misma asignacion.`

## Gate

medicion sin gate: la asignacion se sella antes de cualquier medida de H1 y no se cambia despues

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 20260923
- Git: rama `codex/release-hygiene`, commit `27b2917fca0963cff2520dc4be25507e59017a1d`, dirty=True

## Estado

- Creado: 2026-09-23T18:16:38.761005+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-09-23T18:16:39.417147+00:00)
- Finalizado: 2026-09-23T18:16:39.567092+00:00
- Razón de la decisión: Asignacion sellada antes de medir H1: 122 ligandos en 83 grupos de scaffold (114 InChIKey distintos). Entrenamiento 72 ligandos / 46 grupos (Br 67 atomos, I 21), validacion 24 / 18 (Br 20, I 6), prueba 26 / 19 (Br 27, I 13). Ningun scaffold en dos particiones. Entornos: Br 109 arilo y 5 alifatico, I 39 y 1. 5mlj marcada como geometria imposible (regla de MMGBSA-H5-R1). Tres ejecuciones dan la misma asignacion.
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
