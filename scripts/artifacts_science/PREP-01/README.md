# PREP-01

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

Las tres politicas de heteroatomos que la auditoria del codigo encontro producen receptores MEDIBLEMENTE distintos sobre las mismas estructuras, y la que validaron los experimentos del programa no es la que ejecuta el producto.

## Protocolo

Referencia: `Descriptivo y sin computo pesado. Sobre los 116 de MF-13, con la MISMA fuente para las tres rutas: la entrada original de RCSB que REC-12-R1 descargo. RUTA 1 dataset_experimental: el rec.pdbqt de data/molflex_train_v2, que es lo que consumieron REC-08-EXT, REC-09, REC-11 y la serie MF-33. RUTA 2 producto_docking: el filtro real de services/docking/preparer.py, IMPORTADO y no reimplementado. Se aplica `_filter_pdb_content` con keep_hetatm=True y cofactors_whitelist vacio, que es el estado de los 387 targets del catalogo. No se ejecuta meeko: meeko anade hidrogenos y cargas DESPUES y no cambia que residuos entran, que es lo unico que aqui se mide. RUTA 3 producto_mmgbsa: `removeHeterogens(keepWater=False)` de molchamb_v2, modelado como conservar solo registros ATOM, que es lo que hace. La clasificacion de especies usa backend/data/site_species_vocabulary.json, dato versionado cuya version viaja en el metrics. El ligando cristalografico se descarta por solapamiento dentro de 0.5 A: es el sitio, y sacarlo del receptor es correcto, no una perdida. Script: scripts/analisis_politicas_preparacion.py.`

## Gate

SIN GATE. Es una MEDICION: cuenta lo que cada politica conserva y descarta, y no decide cual es correcta. No hay umbral y no hay decision que dependa de un numero. PROHIBIDO: leer 'pierde una especie del sitio' como defecto sin mirar QUE especie -un aditivo de cristalizacion y un cofactor funcional cuentan igual en ese contador y no valen lo mismo-; concluir que una ruta es mejor que otra, porque este analisis no mide docking ni cobertura; y extrapolar a los 387 targets del catalogo, cuya cadena la fija el catalogo por target y aqui se usa la mayoritaria. LO QUE SI AUTORIZA es corregir afirmaciones existentes que se hicieron por lectura de codigo y ahora estan medidas, en docs/51 y docs/53.

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `codex/mejora-producto`, commit `8d69c5533ac20e01c74e73f1030341d1bc05e6fb`, dirty=True

## Estado

- Creado: 2026-08-23T07:39:06.230817+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-23T07:41:01.255960+00:00)
- Finalizado: 2026-08-23T07:41:01.426454+00:00
- Razón de la decisión: MEDICION, no experimento con gate: convierte en numero lo que hasta ahora era lectura de codigo. Sobre los 116 y con la fuente RCSB identica para las tres rutas. CONFIRMA lo que la auditoria afirmo: la ruta de docking del producto ELIMINA TODAS LAS AGUAS en 115 de 115 complejos que las tienen, que es lo contrario de la politica que docs/51 declara; y pierde algun metal en 55 de 116 complejos, cinco veces mas que el dataset experimental, que los pierde en 11. CORRIGE una afirmacion propia, y esta es la parte que no se esperaba: EL DATASET EXPERIMENTAL TAMBIEN PIERDE COSAS. Contra la fuente original de RCSB pierde algun metal en 11 complejos, algun cofactor conocido en 8 y alguna especie no aditiva del sitio en 22. La conservacion completa que REC-08-EXT midio -1788 de 1788 aguas, 42 de 42 metales- es cierta RELATIVA AL _protein.pdb DE PDBBIND, que ya venia limpiado, y NO relativa a la estructura depositada. Es exactamente lo que REC-12-R1 predijo: la fuente limpiada ocultaba la pregunta. docs/51 debe declarar respecto a que fuente mide su politica. HALLAZGO CONTRAINTUITIVO: la ruta de docking del producto pierde MENOS cofactores organicos conocidos -5 complejos- que el dataset experimental -8-, porque tiene una lista positiva codificada -HEM, NAD, FAD, FMN, ATP, ADP, SAM y los clusters hierro-azufre- mientras el dataset heredo lo que PDBBind hubiera dejado. En cofactores el producto es MEJOR que el conjunto sobre el que se valido la ciencia. Sigue siendo peor en aguas y en metales. DEFECTO PROPIO CORREGIDO ANTES DE REGISTRAR: la primera pasada contaba el ligando cristalografico como especie del sitio perdida, y daba 110 de 116 en las TRES rutas, una alarma sin contenido. Sacar el ligando del receptor es lo correcto. Se descarta por solapamiento dentro de 0.5 A, igual que hace el modulo sellado de REC-12, y las cifras utiles bajan a 22, 41 y 41.
- Hashes de dataset: 1 archivo(s) con SHA-256
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
