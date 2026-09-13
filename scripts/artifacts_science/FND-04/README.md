# FND-04

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

Una biblioteca comun de incertidumbre evita que cada experimento implemente sus propios estadisticos, y permite reverificar los intervalos ya sellados con codigo independiente

## Protocolo

Referencia: `FND-04/README; Wilson, McNemar exacto, bootstrap BCa pareado y Benjamini-Hochberg; 12 sanity tests perfect/random; reverificacion de RS-14 y RS-14-R1`

## Gate

G1 todos los sanity tests pasan; G2 la diferencia pareada recomputada coincide con la sellada (<=0.01) y el veredicto del gate no cambia

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `6bae87c3cda6de687a37b19f2b7dd219cd53e053`, dirty=True

## Estado

- Creado: 2026-08-19T03:52:54.248997+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-19T03:52:55.168423+00:00)
- Finalizado: 2026-08-19T03:52:55.360193+00:00
- Razón de la decisión: P0 declarado y sin artefacto mientras RS-14, RS-14-R1, MF-08, REC-03 y el entregable 8 usaban cada uno su propia implementacion. 12/12 sanity tests. Reverificacion independiente: RS-14 recomputado -0.0471 CI [-0.1594,+0.0616] frente al sellado -0.0471 [-0.1522,+0.0617]; RS-14-R1 recomputado -0.0942 [-0.2101,+0.0217] frente a -0.0942 [-0.2138,+0.0217]. Los puntos coinciden al cuarto decimal y los CI dentro del ruido de remuestreo. Es la primera vez que un CI del programa se verifica con una implementacion distinta de la que lo produjo. Un sanity test fallo en la primera pasada por un defecto del TEST, no de la biblioteca: comparaba un float con == 1.0 cuando el borde de Wilson para 10/10 vale 1.0 solo analiticamente; corregido con tolerancia. Se anadio ademas efecto_minimo_detectable y n_necesario, y su aplicacion retrospectiva mostro que RS-14 solo podia detectar 22.3 pp -no ~10- y que harian falta 1,972 complejos para resolver 5 pp, no los ~370 estimados. MF-19 y MF-08 tambien resultan formalmente indetectables por diseno.
- Hashes de assets: 3 archivo(s) con SHA-256

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
