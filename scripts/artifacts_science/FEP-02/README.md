# FEP-02

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

La integridad del receptor (cadenas, huecos, disulfuros, metales, cofactores, aguas) esta documentada en el material actual

## Protocolo

Referencia: `auditoria sin docking sobre los 203; huecos de numeracion, sitios entre cadenas, disulfuros y contenido del sitio`

## Gate

auditoria sin gates; verificacion adicional del diagnostico de MF-10

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `6bae87c3cda6de687a37b19f2b7dd219cd53e053`, dirty=True

## Estado

- Creado: 2026-08-19T03:53:18.108035+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-19T03:53:18.927029+00:00)
- Finalizado: 2026-08-19T03:53:19.119695+00:00
- Razón de la decisión: 83 de 203 complejos (41%) quedarian documentados. 86 de 203 (42%) tienen huecos de numeracion y 43 (21%) tienen el sitio repartido entre mas de una cadena -modo de fallo que 19_LIMITATIONS marcaba como conocido y que nadie habia contado-. 52 tienen metales en el sitio y la mediana de aguas en el sitio es 10, ninguna documentada como estructural o desplazable. VERIFICACION DEL DIAGNOSTICO DE MF-10: los 9 complejos que fallaron con error de plantilla de OpenMM tienen huecos de cadena, los 9 de 9, frente a una tasa base del 42.4%. La probabilidad de que salga asi por azar es 0.424^9 ~ 0.0004. El diagnostico -cortes de cadena dejados como terminos- queda CONFIRMADO, y con el la decision de no re-correr MF-10 para recuperarlos. Limitacion: un salto de numeracion no siempre es hueco fisico (hay convenciones de numeracion no consecutiva); los 86 son candidatos, no defectos confirmados, aunque los 9 de MF-10 si lo eran.
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
