# RC-F0-V2

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

Reconstruir el conjunto de poses aplicando el generador congelado a los tres splits produce un conjunto homogeneo, con el contrato original reproducido linea a linea y cobertura del oraculo medible

## Protocolo

Referencia: `RC-F0-V2-PRE sellado; build_pose_selector_dataset.py + ruta_c_fase1_5_v05.py reutilizados sin reimplementar; material de MF-02D y MF-02E`

## Gate

G1 reproduccion v1, G2 integridad cache, G2b reproduccion del extractor, G3 split conservado, G4 poses v1 intactas, G5 cobertura, G6 completitud

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `95c44c64dfd0a2c893f3586adacf3b24c64ae97f`, dirty=True

## Estado

- Creado: 2026-08-18T03:31:04.483610+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-18T03:31:32.354622+00:00)
- Finalizado: 2026-08-18T03:31:57.652231+00:00
- Razón de la decisión: Los siete gates pasan. El conjunto v2 tiene 34302 poses con 224 features cada una: 2087 conservadas de v1 (flexible_redock 1534, ruta_a 553) y 32215 nuevas de molflex, sobre 203 complejos. Cobertura del oraculo: train 67.2 a 79.3, val 75.0 a 87.5, test 87.2 a 97.9 por ciento; las cifras coinciden EXACTAMENTE con las medidas por la via independiente sobre el material crudo, dos caminos de codigo distintos con el mismo numero. Los dos gates de reproduccion son los que sostienen todo lo demas: antes de anadir una sola pose se reprodujo el conjunto v1 linea a linea desde los registros intermedios (2739/730/831 identicos, incluida la division por scaffold con semilla 42), y las 2087 poses heredadas se RECALCULARON en vez de copiarse del cache, coincidiendo 2087/2087. Reusar el cache habria sido mas barato; recalcular demuestra que el extractor sigue produciendo lo mismo. Consecuencias declaradas: la tarea cambia de rankear ~9 candidatos a ~169, de modo que v2 no es v1 ampliado y queda prohibido comparar cifras de v0.6 entre ambos sin re-entrenar; el gradiente train < val < test persiste (79.3 < 87.5 < 97.9) porque el split por scaffold concentro los scaffolds dificiles en train, asi que un selector entrenado ahi y evaluado en test tiene el generador a favor y esa ventaja no es suya; y test queda casi saturado con 46 de 47, donde ya no hay techo de generacion que ganar. Fuera de alcance: no se entrena ni evalua ningun selector, y NO se aplica la deduplicacion de MF-11-R1 porque su umbral de 1.5 A se eligio sobre una union 6.9 veces menos densa y reusarlo sin re-derivarlo seria extrapolarlo a otro regimen.
- Hashes de dataset: 4 archivo(s) con SHA-256
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
