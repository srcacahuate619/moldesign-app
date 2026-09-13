# MF-02D

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

Aplicar el pipeline MolFlex congelado a los 116 de train conservando las poses produce el material de referencia del programa y reproduce el hallazgo de MF-02B

## Protocolo

Referencia: `MF-02D-PRE sellado; molflex congelado docs/40 con --keep; metrica primaria rmsd_pose_pocket sobre todas las poses dockeadas`

## Gate

G1 validez >=95%, G2 material en disco, G3 reproduccion de MF-02B sin discrepancias, G4 no regresion, G5 cobertura >=90%

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `284db6b3e92cd35b8d0f7f870df6faebe6fb1135`, dirty=True

## Estado

- Creado: 2026-08-18T01:21:42.268083+00:00
- Status: finished
- Decisión: NO_GO
- Sellado: sí (2026-08-18T01:21:43.148406+00:00)
- Finalizado: 2026-08-18T01:21:59.046941+00:00
- Razón de la decisión: Cuatro de cinco gates pasan y el experimento entrega su producto: 116/116 complejos con material en disco (17596 poses dockeadas, mediana 171 por complejo, con index_map y receptor) y reproduccion EXACTA de MF-02B en los 38 complejos comparables, 38/38 sin discrepancias, lo que demuestra que el pipeline no tiene variabilidad oculta. Falla G5: la cobertura del oraculo de train con la union es 79.3%, por debajo del 90% exigido. El umbral se fijo sobre la cifra de MF-02B (93.1%), que estaba mal medida: MF-02B consumio rmsd_best_to_crystal de molflex, calculado con AllChem.GetBestRMS, que ALINEA las moleculas y oculta desplazamientos, mientras el dataset etiqueta con rmsd_pose_pocket, sin alinear. El repositorio ya lo tenia documentado como leccion de auditoria del 2026-08-14 y este experimento lo confirma en datos: 10gs reporta 2.755 A alineado y su pose entregada esta a 7.83 A del sitio bioactivo. Con la metrica correcta, sobre todas las poses dockeadas que es el conjunto que consume build_pose_selector_dataset fuente S2, la cobertura pasa de 67.2% a 79.3% (78 -> 92 de 116) y los recuperados son 14 y no 30; 12 complejos que la metrica alineada contaba no se sostienen. La ganancia real es de +12 puntos y no de +26. El material entregado es valido y no depende de la metrica; lo que no sobrevive es el numero, y todo lo que se construya encima -reconstruccion del dataset, precision condicional, reapertura de la cartera D- debe partir de 79.3%.
- Hashes de dataset: 1 archivo(s) con SHA-256
- Hashes de binarios: 1 archivo(s) con SHA-256
- Hashes de assets: 9 archivo(s) con SHA-256

## Mantenimiento del sello

- 2026-08-18T03:22:52.028798+00:00: `scripts/analisis_pocket_mf02d.py` `a9eca54e→ec6522ef` — El script de analisis gana override por variable de entorno (MF_POSES_DIR, MF_RESUMEN_DIR) para poder apuntarlo a otro material sin reasignar globals. Motivo tecnico: en Windows ProcessPoolExecutor usa spawn y cada worker reimporta el modulo, de modo que reasignar la global en el proceso padre NO llega a los hijos; ese patron ya causo dos incidencias hoy (MF-02E escribiendo en el directorio de train, y un analisis que devolvio 0 complejos). El entorno SI se hereda. No cambia ningun calculo: mismos defaults, misma metrica, mismos resultados. (commit PENDIENTE)

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
