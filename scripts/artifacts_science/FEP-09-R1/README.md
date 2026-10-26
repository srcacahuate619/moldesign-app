# FEP-09-R1

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

Con P01 arreglado, Preparación mide desde el ligando en el camino B: los huecos del sitio siguen detectándose, la estereoquímica sin asignar se detecta con n>=8, y agua puente y protonación del sitio siguen siendo límites de alcance, no efectos de P01.

## Protocolo

Referencia: `docs/auditorias/FEP-09-R1-prerregistro.md; inventory.json (127 casos de FEP-09 sin cambios y 36 de estereoquímica); producto ee2d6c78; camino B respetar; Vina 8/9/42; pH 7.4`

## Gate

Idéntico a FEP-09: por categoría declarada n>=8, CP95 inferior>=0.5 y falsa alarma<=0.10. NO_GO si alguna falla, GO sólo si todas pasan, de otro modo INCONCLUSIVE (global INCONCLUSIVE por construcción: tautómero minoritario y especie con n=0). Parar si infraestructura>30%.

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `claude/integracion-fep09-evaluacion`, commit `ee2d6c7846f6df703b5af2d7add12158ca53c917`, dirty=True

## Estado

- Creado: 2026-10-11T22:30:41.261948+00:00
- Status: finished
- Decisión: INCONCLUSIVE
- Sellado: sí (2026-10-11T23:21:59.633568+00:00)
- Finalizado: 2026-10-11T23:22:33.281185+00:00
- Razón de la decisión: 163 auditorías confirmatorias, producto ee2d6c78 (P01 arreglado), camino B respetar, Vina 8/9/42, pH 7.4, modo tautomérico efectivo entrada en las 163; prerregistro 68d36882; 0 fallos. entorno.referencia REGISTRADO 163/163 (FEP-09: 0/127). Huecos en el sitio 15/15, CP95 [0.7819806391, 1.0], GO, ahora midiendo desde el ligando. Estereoquímica sin asignar 21/21 en 7 dianas (3 por diana), CP95 [0.8389023848, 1.0], GO. Falsa alarma 0/585 (FEP-09: 4/555, por procedencia.commit con el arnés editado); acuerdo de bases 1170/1170. Agua puente 0/9 y protonación del sitio 0/5 (saturadas) iguales caso a caso que en FEP-09: límites de alcance, no efectos de P01. Tautómero minoritario y especie con n=0: INCONCLUSIVE global por construcción, como se preregistró. Las seis predicciones se cumplen. Duración: del primer inicio al último término de la fase confirmatoria, tres cápsulas en paralelo.
- Hashes de dataset: 31 archivo(s) con SHA-256
- Hashes de binarios: 4 archivo(s) con SHA-256
- Hashes de assets: 1690 archivo(s) con SHA-256

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
