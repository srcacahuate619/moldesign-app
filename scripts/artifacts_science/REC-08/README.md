# REC-08

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

La preparacion del receptor conserva todas las cadenas que forman el sitio de union. Si alguna se pierde, ese complejo se dockeo contra un bolsillo incompleto y todo lo medido sobre el arrastra un error no declarado.

## Protocolo

Referencia: `ID declarado en la cartera B del doc 49 y nunca ejecutado. Version barata que responde la pregunta con material ya existente. FEP-02 midio 43 de 203 complejos con el sitio repartido entre varias cadenas y su docstring dejo anotado el riesgo de que _detect_dominant_chain recorte una sola cadena y destruya un sitio inter-cadena; ese riesgo nunca se comprobo. Para cada uno de los 203: (1) cadenas que forman el sitio = las que aportan algun residuo con un atomo a <=8 A de algun atomo pesado del ligando cristalografico, medido sobre data/pdbbind/<pid>/<pid>_protein.pdb; (2) cadenas presentes en el receptor PREPARADO, data/molflex_train_v2/<pid>/<pid>/rec.pdbqt, que es el que Vina realmente usa; (3) perdida = cadenas de (1) ausentes de (2), con el recuento de residuos de sitio que se van con ellas. El radio de 8 A se reusa de FEP-02 para que las mediciones sean comparables. Solo lectura.`

## Gate

MEDICION SIN GATES DE DECISION. Cantidad de interes: numero y fraccion de complejos con SITIO MUTILADO -alguna cadena que aporta residuos al sitio ausente del receptor preparado-, con el recuento de residuos de sitio perdidos y el cruce contra los que FEP-02 marco como sitio inter-cadena. LIMITACION DECLARADA ANTES: se compara PRESENCIA DE CADENA, no identidad residuo a residuo; una cadena presente pero recortada en su extremo no se detecta con este criterio, de modo que el resultado es una COTA INFERIOR del dano. A diferencia del resto de la cartera H, esto no es documentacion: un sitio mutilado es un defecto de PRODUCCION y su hallazgo obliga a revisar el pipeline de preparacion, no solo a declararlo.

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `7fe43084cddf4c17149dd3dee9ce2fa06c2c57f2`, dirty=True

## Estado

- Creado: 2026-08-20T04:37:47.714959+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-20T04:38:44.943722+00:00)
- Finalizado: 2026-08-20T04:38:45.213632+00:00
- Razón de la decisión: EL RIESGO NO SE MATERIALIZA. 0 de 116 complejos tienen el sitio mutilado: ninguna cadena que aporta residuos al sitio de union desaparece en el receptor preparado. 26 de los 116 tienen sitio formado por mas de una cadena -hasta 4 cadenas en un caso- y los 26 conservan todas. El riesgo que FEP-02 dejo anotado en su docstring -que _detect_dominant_chain recorte una sola cadena y destruya un sitio inter-cadena- no ocurre en el material examinado. Es un negativo limpio y es buena noticia: no hay defecto de produccion que reparar por esta via. COBERTURA, QUE ES LA LIMITACION PRINCIPAL: 116 de 203, el 57%. Los 87 restantes son TODOS de valtest y fallan por la misma causa unica -no existe data/molflex_train_v2/<pid>/<pid>/rec.pdbqt para ellos-, no por un fallo del analisis. El receptor preparado solo se genero para train, de modo que la afirmacion vale para train y NO se extiende a val ni a test. Esto NO es una excusa metodologica: es una asimetria real del material que conviene tener presente en cualquier experimento futuro que compare receptores preparados entre splits. LIMITACION DECLARADA ANTES DE CORRER: se compara PRESENCIA DE CADENA, no identidad residuo a residuo. Una cadena presente pero recortada en su extremo, o con residuos ausentes en medio, NO se detecta con este criterio. El resultado es por tanto una COTA INFERIOR del dano: dice que no se pierden cadenas enteras, no que el receptor preparado sea identico al original en la region del sitio. Medir eso exigiria comparacion residuo a residuo y es el paso natural si alguna vez se sospecha del recorte fino. El radio de 8 A se reuso de FEP-02 en vez de elegir uno nuevo, para que ambas mediciones sean comparables.
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
