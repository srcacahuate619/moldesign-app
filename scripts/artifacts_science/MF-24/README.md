# MF-24

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

Existen predictores del coste de colocacion calculables antes de dockear, medibles sin la circularidad de la cohorte estratificada

## Protocolo

Referencia: `medicion correlacional sobre los 116 de train (no seleccionados por desenlace) y despues sobre los 87 de val+test; seis predictores`

## Gate

medicion sin gates; correlacional, ordena candidatos y no identifica causas

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `6bae87c3cda6de687a37b19f2b7dd219cd53e053`, dirty=True

## Estado

- Creado: 2026-08-19T03:53:08.582750+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-19T03:53:09.378098+00:00)
- Finalizado: 2026-08-19T03:53:09.573265+00:00
- Razón de la decisión: El coste de colocacion escala con el tamano y la flexibilidad del ligando: los que convierten tienen 5 torsiones y 16 pesados; los que fallan, 12 y 31. Correlaciones con el coste: rmsd_conf 0.581, torsiones 0.530, n_conformeros 0.515, pesados 0.509, radio de giro 0.480, ocupacion de caja 0.451. El ENTERRAMIENTO va en direccion contraria (rho -0.308): los que convierten estan MAS enterrados (1.87 frente a 1.46 contactos por atomo). Un bolsillo cerrado restringe la busqueda y ayuda; uno abierto la deja vagar. Es el unico predictor que no es tamano disfrazado. Se salio deliberadamente de la cohorte de 48 porque se estratifico POR desenlace de colocacion, lo que hace circular cualquier comparacion de coste entre sus estratos. Limitacion: seis predictores fuertemente correlacionados entre si y n=116; no se ajusto ningun modelo multivariante ni se derivo umbral operativo.
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
