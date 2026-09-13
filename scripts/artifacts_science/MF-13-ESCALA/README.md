# MF-13-ESCALA

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

MF-13 arrastra el mismo desajuste de escala que MF-29-EMP-COR acaba de medir: comparo su cristal RIGIDO (TORSDOF 0) contra score_top1_dock del conjunto v2, y si esas poses son flexibles la comparacion no es homogenea y su diagnostico ~70% busqueda seria un artefacto.

## Protocolo

Referencia: `MEDICION SIN COMPUTO NUEVO sobre datos ya sellados. Lee data/pose_selector_dataset/v2/poses_train.jsonl y clasifica la fuente del top-1 de cada complejo segun la clasificacion de protocolo de RC-F0-V2-EXT, confirmada en molflex.docking_conformero donde la fuente molflex pasa a --ligand el conf{cid}.rigid.pdbqt. Recalcula el gate G2 de MF-13 -fraccion de COLOCACION donde el cristal relajado gana al mejor dock- restringiendo el mejor dock a poses de fuente rigida, que es la comparacion a escala homogenea con su cristal rigido. Script: scripts/analisis_mf13_escala_fuentes.py.`

## Gate

COMPROBACION SIN GATES DE DECISION PROPIOS. Cantidad: el gate G2 de MF-13 con todas las fuentes frente al mismo gate restringido a poses rigidas, leidos con los umbrales que MF-13 preregistro (>=0.70 BUSQUEDA, <=0.30 PUNTUACION, intermedio MIXTO). Si la fraccion no se mueve, MF-13 no tiene el desajuste y la sospecha registrada al cerrar MF-29-EMP-COR se retira. LIMITACION DECLARADA: no relee MF-13 ni lo toca -esta sellado- y solo comprueba el conteo del gate, no la magnitud de la ventaja del cristal.

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `4de518238c6c48ece8a0b1d5848b58459a2eaa6c`, dirty=True

## Estado

- Creado: 2026-08-20T19:57:10.766643+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-20T19:57:12.617420+00:00)
- Finalizado: 2026-08-20T19:57:33.232664+00:00
- Razón de la decisión: LA SOSPECHA SE RETIRA: MF-13 no arrastra el desajuste de escala. En 102 de los 116 complejos el top-1 que MF-13 uso viene de la fuente molflex, que docka conf{cid}.rigid.pdbqt -confirmado en molflex.docking_conformero, donde la variable que se pasa a --ligand es rig = w / conf{cid}.rigid.pdbqt-, es decir TORSDOF 0, la MISMA escala que su cristal rigido. Los otros 14 vienen de flexible_redock (12) y ruta_a (2). Restringiendo el mejor dock a poses de fuente rigida, el gate G2 de COLOCACION queda IDENTICO: 23 de 33 = 0.6970 en ambos calculos, MIXTO en los dos. Ni un solo complejo cambia de veredicto, pese a que 6 de los 33 de COLOCACION tenian su top-1 en una fuente flexible. El motivo es aritmetico y va en la direccion correcta: una pose flexible paga la penalizacion torsional y por tanto puntua PEOR, de modo que el minimo por complejo tiende a salir igualmente de una pose rigida; cuando no sale, la ventaja que eso regala al cristal no basta para cruzar ningun umbral en estos datos. CONSECUENCIA: el diagnostico MIXTO de MF-13 -0.697, tres milesimas por debajo de BUSQUEDA- se sostiene tal como esta sellado, y con el se sostiene el ~70% de fallo de busqueda que el paragrafo 8 y la justificacion de la cartera C usan. Queda RETRACTADA la deuda de primera prioridad que se registro en la 12.2 del roadmap al cerrar MF-29-EMP-COR, y corregida la indicacion exploratoria que la acompanaba: aquel 0.396 -> 0.021 comparaba un cristal FLEXIBLE contra poses RIGIDAS, que es el desajuste inverso y tan invalido como el que MF-29-EMP-COR retiro. El error estuvo en suponer la flexibilidad de las poses del conjunto v2 en vez de comprobarla; RC-F0-V2-EXT ya habia medido que el 93.9% viene del protocolo rigido. LO QUE SIGUE EN PIE SIN CAMBIOS: MF-29-EMP-COR es correcto y su lectura no depende de esto, porque alli el desajuste era real -MF-13 rigido contra el brazo masivo de MF-29-EMP, que docka conf0.flex.pdbqt- y quedo medido en 1.055 kcal/mol de salto de escala. LIMITES: no relee MF-13 ni lo toca; solo comprueba el conteo del gate y no la magnitud de la ventaja del cristal, que si esta afectada en los 14 complejos de fuente flexible y no se corrige aqui.
- Hashes de dataset: 2 archivo(s) con SHA-256
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
