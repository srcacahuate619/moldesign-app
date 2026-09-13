# MF-29-EMP-COR-PRE

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

El deficit del testigo de MF-29-EMP es un artefacto de escala: MF-13 puntuo el cristal como PDBQT RIGIDO (TORSDOF 0, sin penalizacion torsional) y MF-29-EMP dockeo conf0.flex.pdbqt FLEXIBLE con hasta 6 torsiones, y Vina normaliza la afinidad dividiendo por (1 + w_rot * N_rot). Preparar el cristal con la MISMA flexibilidad debe eliminar el deficit o dejarlo por debajo del ruido.

## Protocolo

Referencia: `Corrigendum del testigo de MF-29-EMP. Repite MF-13 cambiando UNA SOLA COSA: escribe el flex_str de molflex.escribir_pdbqt en vez del rigid_str. Mismo tipado de Meeko, mismo receptor rec.pdbqt, misma caja de 25 A, misma semilla 42, mismo --score_only y --local_only con re-puntuacion de la pose relajada. Contenedor moldesign-lab del servidor, el mismo de MF-13 y MF-29-EMP, con vina 1.2.7 en /usr/local/bin/vina. Cohorte: los 48 con lectura en MF-29-EMP. Script sellado: scripts/run_mf29cor_escala_torsional.py.`

## Gate

GATES DE VALIDEZ PRIMERO. G1: el TORSDOF del cristal flexible coincide con el de conf0.flex.pdbqt en >=95% de los complejos; si no, no son la misma molecula preparada igual y el experimento NO SE LEE. G2: la deriva mediana de --local_only respecto del cristal se mantiene <=2.0 A; si se va, deja de ser el cristal. CANTIDAD PRIMARIA: f = fraccion de los 48 donde score_cristal_local_FLEX < score_min(masivo) - 0.10. TRES LECTURAS ESCRITAS ANTES: (1) f<=0.30 ARTEFACTO DE ESCALA, el testigo no sostiene fallo de busqueda y la cantidad primaria de MF-29-EMP queda como unico instrumento valido, con lo que su lectura OBJETIVO se sostiene sola y su decision pasa a GO; (2) f>=0.70 EL TESTIGO SOBREVIVE, el cristal gana tambien a igual escala y MF-29-EMP se queda INCONCLUSIVE; (3) intermedio MIXTO, se reporta la fraccion y MF-29-EMP se queda INCONCLUSIVE. PROHIBIDO: mover estos umbrales despues de ver f; reabrir la cantidad primaria de MF-29-EMP, que es masivo vs produccion y no la toca ningun resultado de aqui; leer cualquier cosa de esto como certificado de optimalidad global, porque MF-29 sigue ABIERTO.

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `83079e9e5f67e1e912037345395e458cb6f91039`, dirty=True

## Estado

- Creado: 2026-08-20T19:36:39.758995+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-20T19:36:40.812055+00:00)
- Finalizado: 2026-08-20T19:36:54.175036+00:00
- Razón de la decisión: Prerregistro sellado ANTES de ejecutar, con el hash del script que contiene la regla de lectura. Motivo del corrigendum: el testigo de MF-29-EMP comparo score_cristal_local de MF-13 -PDBQT RIGIDO, TORSDOF 0- contra el mejor score del brazo masivo -conf0.flex.pdbqt, hasta 6 torsiones activas-. Vina divide la afinidad por (1 + w_rot * N_rot), de modo que el rigido puntua sistematicamente mejor PARA LA MISMA POSE y las dos cifras no estan en la misma escala. La aritmetica con w_rot=0.05846 y el TORSDOF real predice un deficit artefactual mediano de 1.367 kcal/mol frente a 0.491 observado, es decir, el artefacto por si solo predice mas deficit del que hay; pero eso es un modelo de la formula y no una medicion, y una decision de gate no se cambia con un modelo cuando medirlo cuesta minutos. Se declaran dos gates de validez antes del primario -G1 mismo TORSDOF que conf0 en >=95%, G2 deriva del local_only <=2.0 A medianos- porque con torsiones libres el relajado puede alejarse mas que los 0.322 A que derivo el rigido de MF-13, y si se aleja deja de ser el cristal. Se declara explicitamente fuera de alcance la cantidad primaria de MF-29-EMP -masivo vs produccion, 3 de 48- que ningun resultado de aqui puede tocar, y se declara que MF-29 sigue ABIERTO pase lo que pase, porque una cota empirica no certifica optimalidad global.
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
