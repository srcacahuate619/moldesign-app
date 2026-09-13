# MF-26

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

Existe un umbral operativo de torsiones por encima del cual la colocacion colapsa

## Protocolo

Referencia: `medicion: reanalisis de MF-24 por bandas de torsiones con intervalos de Wilson; validacion externa en val+test`

## Gate

medicion sin gates; se busca la FORMA de la curva, no el valor de un punto

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `6bae87c3cda6de687a37b19f2b7dd219cd53e053`, dirty=True

## Estado

- Creado: 2026-08-19T03:53:09.756240+00:00
- Status: finished
- Decisión: NO_GO
- Sellado: sí (2026-08-19T03:53:10.612341+00:00)
- Finalizado: 2026-08-19T03:53:10.808689+00:00
- Razón de la decisión: EL ACANTILADO NO GENERALIZA. En train la tasa cae de 0.792 (3-5 torsiones) a 0.375 (6-8) y sigue a 0.217 (9-12), con CI de Wilson de las bandas extremas disjuntos. En val+test SUBE de 0.600 a 0.632 y en 9-12 da 0.550 frente a 0.217 de train, con intervalos que NO se solapan ([0.097,0.419] vs [0.342,0.742]). El coste de colocacion mediano llega a 6.45 A en train y no pasa de 1.97 A en val+test. La especificacion declarada a partir de train -"MolFlex coloca fiable hasta ~5 torsiones"- NO es valida. Es coherente con dos resultados ya sellados que no se conectaron a tiempo: MF-02A-EXT midio que train es mas dificil que PDBBind (77.6% vs 83.9%) y RC-F0-V2 documento el gradiente train<val<test (79.3/87.5/97.9). El acantilado es otra cara del sesgo de cohorte de train. Lo que SI sobrevive: el enterramiento favorece a los que convierten en 3 de 4 bandas en train y en 4 de 4 en val+test, sobreviviendo a la estratificacion por tamano y al cambio de split. Leccion de metodo registrada: se midio una curva en train y se declaro especificacion sin validarla fuera, que es el error que la seccion 20.9 propone evitar, cometido el mismo dia que se escribio esa seccion.
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
