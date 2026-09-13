# MF-10-PRE

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

Una minimizacion local dentro del bolsillo con un force field bien parametrizado (amber14 + Sage 2.2.1 + cargas NAGL) acerca la pose dockeada a la conformacion bioactiva; es la unica palanca de la hipotesis original sin probar tras agotar caja y reinicios

## Protocolo

Referencia: `MF-10-PRE/PREREGISTRO.md; contenedor moldesign-lab del servidor; 878 poses top-20 por score de los 48 complejos de MF-08/MF-02F; proteina restringida k=100 kcal/mol/A2, ligando libre, 500 iteraciones`

## Gate

G1 capacidad por sondeo, G2 >=95% con energia finita, G3 mediana de delta RMSD negativa, G4 >=5 poses de la banda 2-3 A cruzan el umbral

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `a052e413e5881256f24ebc94bfeff564e707f040`, dirty=True

## Estado

- Creado: 2026-08-18T07:43:43.624938+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-18T07:43:44.385499+00:00)
- Finalizado: 2026-08-18T07:44:05.745817+00:00
- Razón de la decisión: Prerregistro sellado antes de la corrida completa; solo el sondeo de capacidad se ejecuto y queda declarado. Es la unica palanca de la hipotesis original del maintainer que sigue sin probarse: el multi-modo ya estaba saturado con num_modes=9 y la flexibilidad de receptor apuntaba a complejos con fallo conformacional. Las dos palancas geometricas se agotaron sobre la misma cohorte, convirtiendo 3 de 33 cada una y moviendo la mediana 0.8 A. NO PUEDE CORRER EN LOCAL: la fase 3 de molflex degrada a vina --local_only porque Python 3.14 bloquea openff-toolkit, diagnostico documentado en la biblioteca del proyecto original; el contenedor tiene Python 3.11 y RS-03-PARAM-A ya valido la parametrizacion ahi. Sus datos NO se degradan con RS-14 porque son magnitudes fisicas -RMSD antes y despues, y energias- que no dependen de que modelo estadistico gane: con GO son mejores candidatas para el mismo selector y con NO_GO siguen siendo la medicion de si el campo de fuerza acerca la pose. El sondeo descubrio tres dependencias ausentes del contenedor (openmmforcefields, pdbfixer, lxml) que se anadieron a la imagen antes de preregistrar; si hubiera fallado, ese habria sido el resultado, porque la pregunta se responde con un no rotundo si el FF no se puede parametrizar. Prediccion declarada: 67 de las 878 poses caen en la banda 2-3 A, la unica donde una minimizacion local puede plausiblemente convertir, y la banda no se redefine despues. G3 y G4 son distintos a proposito: un FF puede acercar sistematicamente sin convertir a nadie, o convertir a unos pocos por azar sin tendencia. Advertencia declarada: minimizar optimiza hacia el minimo del campo de fuerza y no hacia el cristal, asi que se reporta cuantas poses empeoran.
- Hashes de dataset: 2 archivo(s) con SHA-256
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
