# CAL-8HFI-01

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

Con la receta 7 y la configuracion por defecto de un caso (exhaustividad 8, 9 poses, semilla 42), 8HFI reproduce la pose cristalografica de la desipramina (RMSD <= 2 A sin alinear en >= 3 de 5 semillas, top-1 valido en PoseBusters) y el top-1 de Vina ordena el panel CHEMBL853189 (57 padres, Ki) con rho de Spearman cuyo IC 95 % bootstrap tiene limite inferior > 0.

## Protocolo

Referencia: `scripts/artifacts_science/CAL-8HFI-01/entrada/protocolo.json; scripts/calibracion_receptor.py; decisiones del propietario 2026-10-09`

## Gate

GO si verificacion de pose (>= 3/5 semillas con RMSD <= 2 A y top-1 valido) Y calibracion (limite inferior del IC 95 % de rho(Q, pKi) > 0, cero fallos tras un reintento) Y un unico receptor_sha256; si no, NO_GO y 8HFI sigue en Demostracion con su resultado publicado.

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `claude/cal-8hfi`, commit `36405e18540a949179ef6638d4ae58e2e829463d`, dirty=True

## Estado

- Creado: 2026-10-09T12:54:41.284857+00:00
- Status: finished
- Decisión: NO_GO
- Sellado: sí (2026-10-09T13:19:31.142411+00:00)
- Finalizado: 2026-10-09T13:19:31.280281+00:00
- Razón de la decisión: Verificacion de pose GO en el limite: 3 de 5 semillas reproducen la desipramina (RMSD 0,52/0,56/0,64 A; 3,68 y 4,12 A fallan) y los cinco top-1 son validos. Calibracion NO_GO: rho(-E, pKi) = 0,13, IC 95 % bootstrap [-0,16; 0,41], Fisher [-0,14; 0,38], n = 57, cero fallos, un solo receptor_sha256, parametros 8/9/42 y microestados congelados sin desviacion. El top-1 de Vina no ordena esta serie congenerica en 8HFI. 8HFI sigue en Demostracion con este resultado publicado; no se cambia el panel.
- Hashes de dataset: 6 archivo(s) con SHA-256
- Hashes de assets: 66 archivo(s) con SHA-256

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
