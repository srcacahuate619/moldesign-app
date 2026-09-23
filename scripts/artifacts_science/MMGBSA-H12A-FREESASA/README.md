# MMGBSA-H12A-FREESASA

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

FreeSASA (Lee-Richards) de la RDKit 2025.09.6 que viaja en el producto reproduce por atomo la SASA numericamente exacta (Shrake-Rupley, 50000 puntos) con los mismos radios (Bondi, sin H, sonda 1.4 A) en los 121 ligandos de PDBBind con Br o I, tambien en Br e I, con coste despreciable.

## Protocolo

Referencia: `backend/audits/freesasa_h12.py sobre las topologias de MMGBSA-H1-LCPO-BONDI, ejecutado con frontend/src-tauri/resources/python (el runtime que se entrega); referencia sasa_numerica de lcpo_vs_sasa_exacta.py sin modificar. Piloto previo declarado: un ligando (1zoh, 4 Br) dio <= 0.43 A2 por atomo y < 1 ms.`

## Gate

GO si, por atomo pesado, el p95 de |FreeSASA - exacta| <= 0.5 A2 y el maximo <= 1.0 A2 en el conjunto y por separado en Br y en I, no hay fallos de ejecucion, y la mediana del tiempo de FreeSASA por ligando <= 50 ms. NO_GO en otro caso.

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 20260923
- Git: rama `codex/release-hygiene`, commit `e9da28397188cee87fa599ec70836344a43ce269`, dirty=True

## Estado

- Creado: 2026-09-23T19:29:17.052107+00:00
- Status: finished
- Decisión: NO_GO
- Sellado: sí (2026-09-23T19:30:31.742750+00:00)
- Finalizado: 2026-09-23T19:30:31.924060+00:00
- Razón de la decisión: NO_GO por la letra del gate: el p95 de |FreeSASA - exacta| por atomo es 0.553 A2 (tope 0.5) y el maximo 1.221 A2 (tope 1.0) en 3088 atomos pesados; en Br p95 0.643 y maximo 1.177; en I p95 0.547 y maximo 0.664. Mediana 0.144 A2 (Br 0.261, I 0.163) y 0.55 ms por ligando. El techo lo pone la resolucion por defecto de Lee-Richards, que la RDKit 2025.09.6 no expone (SASAOpts solo tiene algoritmo, clasificador y sonda). No se reformula el gate: una R1 con un criterio energetico disenado despues de ver estos numeros pasaria por construccion. Caracterizacion: el error de FreeSASA es unas 20 veces menor que el error de fondo de LCPO (mediana 2.81 A2) y que el de LCPO en Br/I (H1, H2: medianas 1-5 A2, p90 hasta 9.8), y 1.22 A2 por 0.0072 kcal/mol/A2 son menos de 0.009 kcal/mol.
- Hashes de assets: 5 archivo(s) con SHA-256

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
