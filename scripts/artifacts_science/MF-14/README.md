# MF-14

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

La cuenca de captura alrededor de la pose nativa tiene un radio medible: perturbando una pose correcta y volviendo a minimizar, la fraccion que regresa cae con la distancia y define un r50. Si la cuenca es amplia y lisa, el buscador solo necesita acercarse; si es estrecha o rugosa, acercarse no basta.

## Protocolo

Referencia: `REGISTRO RETROACTIVO, declarado como tal: el experimento se ejecuto el 2026-08-18 con scripts/run_mf14_radio_captura.py y sus resultados quedaron en scratch/mf14_resultados sin manifest. Este artefacto los incorpora al registro. NO existe prerregistro separado; la regla de lectura y los gates viven en el propio metrics.json que produjo el runner, y se sellan tal cual sin reinterpretarse. Diseno: 48 complejos (33 COLOCACION + 15 CONTROL), perturbacion de la mejor pose a radios 0.5, 1.0, 2.0, 3.0 y 4.0 A con 6 replicas por radio y rotacion maxima de 30 grados, semilla 42, caja 25 A; se mide la fraccion que regresa a <=2 A tras re-minimizar.`

## Gate

Los gates originales estan en el metrics.json sellado. Medicion descriptiva: curva de retorno por radio y r50 por estrato. SIN PRERREGISTRO SEPARADO, de modo que sus lecturas son POST-HOC por construccion y asi deben citarse.

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `6a3caa8ac15867ff371733814834fbe33a35ece5`, dirty=False

## Estado

- Creado: 2026-08-20T05:06:55.258362+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-20T05:06:55.980793+00:00)
- Finalizado: 2026-08-20T05:06:56.185893+00:00
- Razón de la decisión: REGISTRO RETROACTIVO de un experimento ejecutado el 2026-08-18 cuyos resultados llevaban desde entonces en scratch/ sin manifest, mientras el doc 49 seccion 20.1 lo CITABA COMO EVIDENCIA -'cuenca de captura r50 aprox 2 A y rugosa: 22% escapa desde 0.5 A'-. La cita era correcta y ahora esta respaldada. LA CUENCA EXISTE Y ES RUGOSA. En COLOCACION la curva de retorno cae 0.778, 0.727, 0.510, 0.303 y 0.136 para radios de 0.5, 1.0, 2.0, 3.0 y 4.0 A, con r50 mediano de 2.0 A y 4 complejos sin r50. En CONTROL: 0.967, 0.922, 0.722, 0.400 y 0.233, con r50 de 3.0 A y ningun complejo sin r50. DOS LECTURAS. Primera: la cuenca del estrato dificil es un TERCIO mas estrecha que la del control -r50 2.0 frente a 3.0 A- de modo que en los complejos que importan hay que acercarse mas para que la minimizacion termine el trabajo. Segunda y mas incomoda: incluso a 0.5 A, PARTIENDO PRACTICAMENTE DE LA POSE CORRECTA, el 22.2% no regresa en COLOCACION frente al 3.3% en control. Eso no es estrechez, es RUGOSIDAD: hay barreras dentro de la propia cuenca. Un buscador puede estar a media angstrom del minimo nativo y caer en otro sitio. LIMITACION ESTRUCTURAL DE ESTE REGISTRO: no existe prerregistro separado. Los gates y la regla de lectura viven en el metrics.json que produjo el runner, y se sellan tal cual sin reinterpretarse, pero eso significa que sus lecturas son POST-HOC por construccion y deben citarse asi. Sellarlo retroactivamente respalda la cita del doc 49; NO le concede el estatus de un experimento preregistrado.
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
