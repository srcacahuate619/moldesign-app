# MF-09-SYM

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

Corregir la simetria en la metrica de pose cambia la conclusion de MF-09 de que en 30 de 33 complejos dificiles no existe pose <=2 A

## Protocolo

Referencia: `medicion: relectura del material sellado de MF-02D + MF-02F, misma cohorte y mismo umbral, cambiando una sola cosa (minimo sobre automorfismos del RMSD sin alinear); sin computo nuevo`

## Gate

medicion sin gates de aceptacion; verificacion obligatoria: reproducir MF-09 bajo la metrica ingenua

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `23ac6d11cfadfdbd1d98de59392ebdaa66539cee`, dirty=True

## Estado

- Creado: 2026-08-18T20:19:49.499934+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-18T20:19:50.062683+00:00)
- Finalizado: 2026-08-18T20:19:50.204595+00:00
- Razón de la decisión: Medicion valida: reproduce MF-09 linea a linea bajo la metrica ingenua (751 poses medianas, oraculo 2.961 A, 3 de 33 cubiertos, top-1 0/33 y 7/15) antes de cambiar nada. Corregida la simetria sobre 21,692 poses: la conclusion de MF-09 SOBREVIVE -30 de 33 pasa a 29 de 33, gana 1l83 cuya mejor pose mide 2.106 A ingenua y 0.942 A corregida- y sigue siendo muestreo, no puntuacion. Pero el top-1 de Vina es mejor de lo que se midio (9 de 15 controles en vez de 7, 1 de 33 en vez de 0) y el margen del selector del control baja de 8 a 6 de 15: una cuarta parte de ese margen no era margen, era la metrica penalizando un anillo girado. Solo 14 de 21,692 poses (0.06%) cruzan el umbral al corregir, pero caen donde mas pesa.
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
