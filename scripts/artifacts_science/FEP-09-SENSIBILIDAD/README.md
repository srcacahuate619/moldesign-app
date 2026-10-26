# FEP-09-SENSIBILIDAD

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

Preparacion por API cambia los requisitos de riesgo ante defectos dentro de su cobertura declarada; variantes pareadas de PLB, no sensibilidad a problemas reales.

## Protocolo

Referencia: `docs/auditorias/FEP-09-prerregistro.md; inventory.json; producto f183e0af; camino B respetar; Vina 8/9/42; pH 7.4`

## Gate

Por categoria declarada n>=8, CP95 inferior>=0.5 y falsa alarma<=0.10. NO_GO si alguna falla, GO solo si todas pasan, de otro modo INCONCLUSIVE. Parar si infraestructura>30%.

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `sol/fep-09-sensibilidad`, commit `45d4490ee6ce6d6132b3024067e602efe3fe90f8`, dirty=True

## Estado

- Creado: 2026-10-11T19:48:18.736933+00:00
- Status: finished
- Decisión: INCONCLUSIVE
- Sellado: sí (2026-10-11T20:40:13.324102+00:00)
- Finalizado: 2026-10-11T20:41:24.319158+00:00
- Razón de la decisión: 127 corridas confirmatorias, producto f183e0af, B/respetar, Vina 8/9/42. Huecos: 15/15, CP95 [0.7819806391, 1.0], gate GO; falsa alarma 0.007207207207207207. Estereo n=3, tautómero minoritario y especie con pKa independientes n=0: no permiten GO global. Proxies, límites y brazo C fuera del gate estricto. Modo tautomérico efectivo entrada; descripción preregistrada canónica incorrecta, publicada sin modificar protocolo ni reintentar corridas. Duración: reloj de fase confirmatoria entre primer inicio y último término, cápsulas paralelas.
- Hashes de dataset: 31 archivo(s) con SHA-256
- Hashes de binarios: 4 archivo(s) con SHA-256
- Hashes de assets: 1387 archivo(s) con SHA-256

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
