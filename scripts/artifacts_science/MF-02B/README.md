# MF-02B

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

Aplicar el pipeline MolFlex congelado a los complejos de train que nunca lo recibieron recupera cobertura del oraculo que el conjunto sellado no tenia

## Protocolo

Referencia: `MF-02-PRE sellado (a09b770, maintain cd1c39a); molflex.py protocolo congelado docs/40 con n_conf=30, caja 25 A, exhaustiveness=8, semillas 42; Vina 1.2.7 local`

## Gate

G1 validez >=95%, G2 recuperacion >=10 de 38 con A8, G3 no regresion de la union, G4 determinismo, G5 coste descriptivo

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `cd1c39ac345036a8ce7251e2f97eed4cd8622f13`, dirty=True

## Estado

- Creado: 2026-08-17T23:22:21.094925+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-17T23:22:46.928507+00:00)
- Finalizado: 2026-08-17T23:22:47.080267+00:00
- Razón de la decisión: Los cinco gates pasan. G2 primario: A8 entrega pose <=2.0 A en 30 de los 38 complejos sin cobertura, muy por encima del umbral preregistrado de 10. La cobertura del oraculo de train sube de 67.2% a 93.1% (78/116 -> 108/116) ejecutando el pipeline MolFlex CONGELADO, sin cambiar un parametro. En los 38, el mejor RMSD entregado baja de mediana 4.234 A a 1.433 A (mejora mediana 2.56 A, maxima 8.92 A); de los 32 que no tenian ninguna pose de MolFlex en el conjunto sellado se recuperan 27. Control: A8 entrega <=2 A en 9 de 12, mejora el mejor RMSD en 7 de 12 y no pierde cobertura en ninguno, confirmando que la fuente se anade a la union y no la sustituye. Determinismo exacto 2/2, validez 50/50, coste mediana 344 s por complejo (11 h de CPU para reconstruir los 116, ~1.1 h de reloj con 10 procesos). Los 8 no recuperados son casi-aciertos entre 2.2 y 3.1 A y todos mejoran sobre el dataset; dos de ellos (1a4w, 1elb) ya estaban marcados por MF-02A como techo conformacional duro. Consecuencia registrada: el conjunto de poses sobre el que se evaluaron RS-01, RS-04-OOF y RS-08 se construyo sin la salida de MolFlex en el 89% de los complejos, de modo que esos experimentos midieron Top-1 global sobre un universo con un tercio inganable por construccion. No los reabre —cada uno tiene su gate sellado— pero cambia el denominador que la seccion 19.1 exige para reabrir la cartera. Declarado antes de ejecutar y se repite aqui: anadir una fuente a una union SOLO puede subir la cobertura; el hallazgo es cuanto sube, a que coste, y que la fuente no estaba. Este GO no dice nada sobre el selector: la precision condicional sobre el conjunto ampliado sigue sin medirse y exige su propio prerregistro.
- Hashes de dataset: 1 archivo(s) con SHA-256
- Hashes de binarios: 1 archivo(s) con SHA-256
- Hashes de assets: 7 archivo(s) con SHA-256

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
