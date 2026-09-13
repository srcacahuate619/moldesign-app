# RC-F0-V2-EXT

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

La fraccion del conjunto de poses del programa que proviene del protocolo RIGIDO es mayoritaria, de modo que el hueco de cobertura que MF-33 midio entre rigido y flexible afecta al material sobre el que descansan varias conclusiones selladas.

## Protocolo

Referencia: `Medicion de alcance SIN COMPUTO NUEVO. Lee la composicion por fuente del conjunto v2 desde RC-F0-V2/metrics.json y clasifica cada fuente por si su generador tuvo libertad torsional durante la busqueda: molflex es RIGIDO -molflex.dock_rigido_archivo, TORSDOF 0-, flexible_redock y ruta_a son flexibles. Despues localiza que artefactos SELLADOS hashean o referencian los ficheros de poses, es decir que conclusiones consumen ese material. Solo lectura.`

## Gate

MEDICION DE ALCANCE SIN GATES DE DECISION. Cantidades: fraccion de poses de origen rigido en el conjunto v2, y lista de artefactos sellados que consumen ese material. LIMITACION DECLARADA ANTES Y QUE FORMA PARTE DEL RESULTADO: NO se afirma que las conclusiones de los consumidores sean incorrectas. MF-33 midio el hueco de COBERTURA entre rigido y flexible; los experimentos de seleccion midieron PRECISION CONDICIONAL sobre lo cubierto, que es otra cantidad, y un techo de cobertura mas alto cambia el denominador sin invalidar automaticamente una comparacion pareada hecha dentro de el. Ademas el 1/33 de MF-33 es del estrato DIFICIL: extrapolarlo a los 203 seria injustificado, porque en CONTROL el rigido alcanza 15/15. Lo que se establece es el ALCANCE de lo que habria que rehacer si se decidiera medir sobre material flexible. PROHIBIDO usar este artefacto para declarar invalidada ninguna conclusion sellada.

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `79d00a93a258c1ee8a21ac1d99e8aa0deb4b9223`, dirty=True

## Estado

- Creado: 2026-08-20T05:00:41.337961+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-20T05:01:12.559159+00:00)
- Finalizado: 2026-08-20T05:01:12.801226+00:00
- Razón de la decisión: EL 93.9% DEL CONJUNTO DE POSES DEL PROGRAMA VIENE DEL PROTOCOLO RIGIDO. De las 34,302 poses del conjunto v2: molflex 32,215 (93.9%), flexible_redock 1,534 (4.5%), ruta_a 553 (1.6%). Solo el 6.1% se genero con libertad torsional durante la busqueda. Diecisiete artefactos sellados consumen ese material, entre ellos RS-14, RS-09, RS-01, RS-01A, MF-02D, FND-02, FND-06 y el propio RC-F0-V2. ESE ES EL ALCANCE de lo que MF-33 destapo: el protocolo que alcanza 1 de 33 en el estrato dificil, mientras los MISMOS conformeros dockeados flexibles alcanzan 26 de 33, produjo casi todo el material sobre el que descansa la cartera D. LO QUE ESTE NUMERO NO AUTORIZA A CONCLUIR, y se declaro antes de calcularlo: (1) NO se afirma que las conclusiones de los 17 consumidores sean incorrectas. MF-33 midio el hueco de COBERTURA; los experimentos de seleccion midieron PRECISION CONDICIONAL SOBRE LO CUBIERTO, que es otra cantidad. Un techo de cobertura mas alto cambia el denominador, no invalida automaticamente una comparacion pareada hecha dentro de el. RS-14 y RS-14-R1 concluyeron que el selector no supera a vina_score sobre los complejos cubiertos, y mas cobertura significa mas complejos evaluables, no un veredicto distinto sobre los ya evaluados. (2) El 1/33 de MF-33 es del estrato DIFICIL. Extrapolarlo a los 203 seria injustificado: en CONTROL el rigido alcanza 15 de 15 y con la MEJOR mediana de los tres brazos (0.861 A). El protocolo rigido no esta roto en general; falla en el estrato que motivo el programa. (3) Ademas MF-33 tiene su propio defecto abierto -el brazo B conserva 261 poses de mediana contra 9- y su magnitud esta suspendida hasta MF-33-A3. Lo que este artefacto establece es una sola cosa y hay que citarla asi: cuanto material habria que rehacer si se decidiera medir sobre poses flexibles. Sin computo nuevo: lectura de dos artefactos sellados.
- Hashes de dataset: 1 archivo(s) con SHA-256
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
