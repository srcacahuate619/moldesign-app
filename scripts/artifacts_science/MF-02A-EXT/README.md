# MF-02A-EXT

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

El techo conformacional del ensemble ETKDG medido en los 116 de train generaliza al conjunto de PDBBind, y su curva permite saber cuanto compra anadir conformeros a escala

## Protocolo

Referencia: `Declarado en MF-02-PRE seccion 4, sellado antes de ejecutar; mismo metodo que MF-02A (ETKDG seed 42, prune 0.4, GetBestRMS alineado, curva acumulada sobre un unico embebido de 150) en el contenedor Ubuntu`

## Gate

Sin gates de aceptacion: es una medicion descriptiva del generador

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `e3df898ab254f33018a72ddf97832613b7ec5a39`, dirty=True

## Estado

- Creado: 2026-08-18T06:51:07.629534+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-18T06:51:33.164888+00:00)
- Finalizado: 2026-08-18T06:51:33.329479+00:00
- Razón de la decisión: Medicion descriptiva sin gates, declarada en MF-02-PRE seccion 4 antes de ejecutar. Sobre 4636 complejos de PDBBind medidos (de 5316; 680 fallaron el embebido de RDKit, un 12.8 por ciento que no pasa ni la primera fase del generador), la curva de disponibilidad conformacional a <=2 A es 75.2, 81.2, 83.9, 86.2, 87.2 y 88.1 por ciento para K5, K15, K30, K60, K90 y K150. TRES LECTURAS. (1) El techo generaliza: alrededor del 12 por ciento de PDBBind no tiene la conformacion bioactiva en el ensemble ETKDG ni con 150 conformeros, y eso es propiedad del metodo de embebido y no de la cohorte de 116. (2) CORRIGE A MF-02A: sobre los 116 la curva se aplanaba en 80.2 por ciento desde K60 y declare saturacion; sobre 4636 sigue subiendo alrededor de 1 punto por duplicacion (86.2 a 87.2 a 88.1), de modo que el plateau aparente era en parte artefacto del tamano de muestra. La conclusion cualitativa se mantiene -rendimientos decrecientes, 5x de coste de K30 a K150 para 4.2 puntos- pero la palabra satura era demasiado fuerte. (3) El conjunto de train es MAS DIFICIL que PDBBind en general: a K30 la disponibilidad es 83.9 por ciento en PDBBind frente a 77.6 en los 116, coherente con el gradiente train menor que val menor que test que encontro RC-F0-V2, lo que sugiere sesgo en como se armo la cohorte y no en el generador. Junto con MF-09, que mostro que en 30 de 33 complejos dificiles no existe pose buena entre 751 candidatas, las dos mediciones acotan el problema por ambos lados: el material conformacional suele estar disponible y el docking no lo coloca.
- Hashes de assets: 5 archivo(s) con SHA-256

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
