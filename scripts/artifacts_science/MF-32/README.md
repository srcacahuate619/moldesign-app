# MF-32

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

La lectura de la linea C sobrevive a una auditoria adversarial: umbral arbitrario, regresion a la media y varianza por semilla

## Protocolo

Referencia: `auditoria adversarial: reanalisis de MF-08 desde la posicion de un revisor hostil; sensibilidad al umbral, regresion a la media y degradacion de controles`

## Gate

medicion sin gates; cada ataque prospera o no segun criterios declarados

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `6bae87c3cda6de687a37b19f2b7dd219cd53e053`, dirty=True

## Estado

- Creado: 2026-08-19T03:53:13.383567+00:00
- Status: finished
- Decisión: INCONCLUSIVE
- Sellado: sí (2026-08-19T03:53:14.175815+00:00)
- Finalizado: 2026-08-19T03:53:14.371010+00:00
- Razón de la decisión: Tres ataques, tres resultados distintos. ATAQUE 1 (el umbral de 2.0 A hace el trabajo): PROSPERA PARCIALMENTE. Mover el umbral a 2.5 A multiplica las conversiones por tres o mas (B_ADAPT de 3 a 10, B20 de 1 a 9) y hay 12-13 complejos en la banda 2.0-3.0 A por brazo. Pero el ORDEN de los brazos se mantiene en los cuatro umbrales y el patron "mejora que no basta" persiste: a 2.5 A el mejor brazo sigue fallando en 23 de 33. Obliga a reportar la curva completa y a dejar de tratar 2.0 A como si fuera fisico. ATAQUE 2a (regresion a la media): PROSPERA. rho 0.390 en COLOCACION y 0.533 global entre el oraculo de partida y la mejora, la firma clasica. ATAQUE 2b (test decisivo): EL ATAQUE SE CAE. Si fuera regresion a la media pura, los controles -seleccionados por el extremo opuesto- tendrian que EMPEORAR. No lo hacen: mejoran levemente (-0.042, CI [-0.126,-0.002]) y se reparten 5/4. El efecto sobrevive, atenuado. ATAQUE 3 (varianza por semilla): no contrastable sin ejecutar Vina; se identifico como el hueco mas grave y motivo la ejecucion de FND-03, que despues lo respondio: sd mediana 0.283 A y error estandar de la mediana 0.049 A, de modo que los efectos de ~0.8 A son 15.8x ese error y el ataque no prospera a nivel agregado.
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
