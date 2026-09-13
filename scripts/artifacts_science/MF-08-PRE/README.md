# MF-08-PRE

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

El fallo de cobertura esta dominado por colocacion y no por conformacion; una caja de 25 A centrada en el ligando admite subsitios competidores que puntuan mejor, de modo que encoger a 20 A debe recuperar poses y agrandar a 30 A debe empeorarlas

## Protocolo

Referencia: `MF-08-PRE/PREREGISTRO.md; refina MF-08 del doc 49 invirtiendo la direccion de la hipotesis; molflex congelado salvo BOX_SIZE; B25 reutiliza el material sellado de MF-02D`

## Gate

G1 validez >=95%, G2 B20 recupera >=6 de 33, G3 monotonia B20>=B25>=B30 (mecanismo), G4 B20 pierde <=1 del control de 15, G5 determinismo

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `3e07fe51f44462efee34e2e67d5387ad345ea6c7`, dirty=True

## Estado

- Creado: 2026-08-18T02:01:18.445866+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-18T02:01:19.413050+00:00)
- Finalizado: 2026-08-18T02:01:19.701026+00:00
- Razón de la decisión: Prerregistro sellado antes de ejecutar, con la geometria computada y declarada. La descomposicion del error de la mejor pose alcanzable en los 116 de train muestra que en los 50 fallidos la colocacion domina en 33: mediana de colocacion 2.53 A frente a conformacion 1.89 A, con casos como 1dgm (conformacion 0.90, colocacion 3.85) donde el ligando tiene la forma correcta y esta en otro sitio. Eso invierte el enunciado original de MF-08: la caja no limita, es demasiado generosa. La caja de 15 A queda descartada POR FISICA y no por resultados: con radio mediano de ligando de 7.04 A, 32 de 116 ligandos no caben y se excluiria tambien la pose nativa. Con 20 A el subsitio decoy queda fuera en 19 de los 33, lista declarada por nombre; excluirlo es necesario pero no suficiente, asi que se espera menos de 19 y el gate exige 6. Se incluye el brazo B30 como PRUEBA DE FALSACION: si el mecanismo es competencia de sitios, agrandar debe empeorar, y si B30 no empeora el mecanismo es falso aunque B20 mejore. Cuatro complejos quedan excluidos a priori por no caber en 20 A. Declarado tambien que un GO NO transfiere a produccion: la caja esta centrada en el ligando cristalografico y REC-03 midio que el top-1 de MolPocket esta a 8 A de mediana del ligando, de modo que con ese error de centro una caja mas ajustada perderia la pose nativa mas a menudo.
- Hashes de dataset: 1 archivo(s) con SHA-256
- Hashes de binarios: 1 archivo(s) con SHA-256
- Hashes de assets: 5 archivo(s) con SHA-256

## Mantenimiento del sello

- 2026-08-18T02:13:43.561622+00:00: `scripts/run_mf08_caja.py` `d2aa7fdb→61ffb64f` — MF-08-PRE queda superado por MF-08-PRE-R1 antes de ejecutarse; el runner se extendio con el brazo B_ADAPT. Se registra el cambio de hash por la via auditada en vez de re-sellar. (commit PENDIENTE)

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
