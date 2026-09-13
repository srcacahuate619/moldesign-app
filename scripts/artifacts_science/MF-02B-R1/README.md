# MF-02B-R1

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

El mismo dato de MF-02B, juzgado con la metrica que corresponde a poses dockeadas (rmsd_pose_pocket, sin alinear), da una recuperacion menor; el gate preregistrado de >=10 de 38 decide si la decision GO se sostiene

## Protocolo

Referencia: `MF-02B-R1/PREREGISTRO.md; corrigendum de MF-02B (1af5dab) sobre el material de MF-02D, que lo reprodujo 38/38 sin discrepancias; nada se reejecuta`

## Gate

G2 original de MF-02B intacto: A8 recupera >=10 de los 38 sin cobertura, evaluado con la metrica corregida

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `284db6b3e92cd35b8d0f7f870df6faebe6fb1135`, dirty=True

## Estado

- Creado: 2026-08-18T01:23:37.874920+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-18T01:23:38.563717+00:00)
- Finalizado: 2026-08-18T01:23:55.515884+00:00
- Razón de la decisión: La decision GO de MF-02B se sostiene y su magnitud se corrige a la mitad. El gate preregistrado (A8 recupera >=10 de los 38) se evalua con la metrica corregida sin tocar el umbral: 14 recuperados, PASA. MF-02B habia contado 30 porque midio con rmsd_best_to_crystal de molflex, calculado con AllChem.GetBestRMS, que ALINEA las moleculas y mide geometria interna, mientras el conjunto de poses etiqueta con rmsd_pose_pocket, sin alinear, que mide si la pose esta en el sitio. El repositorio tenia la advertencia escrita desde el 2026-08-14 en el docstring de la funcion correcta. El sesgo mediano es 1.002 A y tiene signo conocido: 16 complejos pierden el estatus de recuperados y NINGUNO lo gana. Se recalculo sobre una definicion MAS generosa que la de MF-02B -minimo sobre las 17596 poses dockeadas en vez del top-K entregado- y aun asi el numero baja de 30 a 14, de modo que la correccion no depende de haber elegido un criterio mas estricto. Nada se reejecuto: MF-02D reprodujo MF-02B 38/38 sin discrepancias y conservo las poses. Cobertura del oraculo en train corregida: 67.2% -> 79.3% (+12 puntos, no +26). Sigue siendo cierto que MolFlex se habia aplicado a 13 de 116 complejos y que el conjunto sobre el que se evaluaron RS-01, RS-04-OOF y RS-08 estaba incompleto. MF-02A no esta afectado: alli el alineamiento es correcto a proposito porque mide disponibilidad conformacional, y asi se declaro antes de ejecutar. MF-02B queda sellado con sus cifras; este corrigendum dice cuales las sustituyen.
- Hashes de dataset: 2 archivo(s) con SHA-256
- Hashes de assets: 5 archivo(s) con SHA-256

## Mantenimiento del sello

- 2026-08-18T03:22:52.330617+00:00: `scripts/analisis_pocket_mf02d.py` `a9eca54e→ec6522ef` — Mismo cambio que en MF-02D: override por variable de entorno en el script de analisis, spawn-safe. No altera ningun numero del corrigendum. (commit PENDIENTE)

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
