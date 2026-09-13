# MF-13

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

La funcion de puntuacion de Vina prefiere la pose nativa cuando se la entregan; separar fallo de busqueda de fallo de puntuacion

## Protocolo

Referencia: `MF-13-PRE/PREREGISTRO.md; contenedor moldesign-lab; 116 complejos de train; score_only y local_only sobre la pose cristalografica en su propio receptor y caja`

## Gate

G1 >=95% con score finito; G2 fraccion de COLOCACION donde el cristal relajado gana al mejor dock: >=0.70 BUSQUEDA, <=0.30 PUNTUACION, intermedio MIXTO

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `23ac6d11cfadfdbd1d98de59392ebdaa66539cee`, dirty=True

## Estado

- Creado: 2026-08-18T20:19:52.057823+00:00
- Status: finished
- Decisión: INCONCLUSIVE
- Sellado: sí (2026-08-18T20:19:52.606587+00:00)
- Finalizado: 2026-08-18T20:19:52.745338+00:00
- Razón de la decisión: Diagnostico MIXTO: 23 de 33 = 0.6970, tres milesimas por debajo del umbral de 0.70 preregistrado para BUSQUEDA. Se predijo BUSQUEDA y no se acerto; el prerregistro prohibe mover el umbral tras ver la fraccion, asi que queda MIXTO y la decision es INCONCLUSIVE respecto a la pregunta binaria. G1 pasa con 116/116. Pero MIXTO aqui no significa "no sabemos": la banda 0.30-0.70 estaba preregistrada precisamente para el caso en que los dos modos de fallo conviven, y eso es lo que se midio. En ~70% de los complejos dificiles el fallo es de BUSQUEDA y es flagrante: el percentil mediano del cristal es 0.0 en los tres estratos -en el complejo mediano la pose cristalografica puntua mejor que TODAS las dockeadas-, la ventaja mediana es +2.39 kcal/mol llegando a +8.80, y la deriva local de 0.322 A confirma que el cristal es un minimo local estable de la funcion. En ~30% el decoy gana y ahi ninguna busqueda ayuda. Pista registrada como hipotesis y no como conclusion: un cristal que puntua -1.63 (1fkh) o -2.18 (1ew8) kcal/mol no es fallo de puntuacion sino sistema mal montado -cofactor, metal o agua estructural ausente, o protonacion incorrecta-, lo que apunta a REC-04/REC-05 de la cartera B. Comprobacion de cordura declarada y cumplida: CONTROL da 0.533 frente a 0.697 de COLOCACION, la inversion predicha. El prerregistro prohibe leer el componente de busqueda como permiso para reabrir MF-03/04/05/07/12: esos ajustan parametros del mismo buscador y MF-02F ya mostro que triplicar reinicios no basta; justifica un buscador distinto, no mas parametros del mismo.
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
