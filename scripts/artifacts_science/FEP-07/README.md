# FEP-07

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

Las tres auditorias de la cartera H miran piezas distintas y ninguna responde cuantos calculos FEP+ se pueden correr HOY. Cruzandolas, la cifra ejecutable es sustancialmente menor que las 91 parejas aptas que conto FEP-03, porque un calculo de energia libre relativa necesita las tres condiciones a la vez y sobre LOS DOS miembros de la pareja.

## Protocolo

Referencia: `Cruce de artefactos ya sellados, SIN COMPUTO NUEVO. Fuentes: FEP-03/parejas.jsonl (las 91 con apta_fep=true), FEP-01-EXT (ligandos donde el proton se mueve, es decir con decision de tautomero pendiente), FEP-02-EXT (receptores con hueco EN EL SITIO, es decir con reparacion estructural pendiente) y FEP-02 (documentado_para_fep, el criterio completo de receptor). Una pareja se clasifica EJECUTABLE_HOY si ninguno de sus dos extremos tiene tautomero pendiente ni hueco en el sitio; BLOQUEADA_POR_TAUTOMERO si el unico defecto es de tautomero; BLOQUEADA_POR_RECEPTOR si algun extremo necesita reparacion estructural. El orden de precedencia es deliberado: el receptor domina porque su arreglo es mas caro.`

## Gate

CRUCE DESCRIPTIVO SIN GATES DE DECISION. Cantidades de interes: numero de parejas EJECUTABLE_HOY y su fraccion sobre las 91 aptas; numero que se desbloquearia solo con declarar tautomeros, que es una decision quimica documentada y no modelado estructural; numero de complejos distintos implicados en las ejecutables. LIMITACION DECLARADA ANTES: 'ejecutable hoy' significa SIN LOS DOS BLOQUEOS MEDIDOS, no 'lista para produccion'. FEP-02 exige ademas documentar cadenas, disulfuros, metales, cofactores y aguas; ese criterio completo se reporta APARTE y NO se usa para clasificar, porque lo cumplen muy pocos y absorberia toda la senal. La cifra es por tanto una COTA SUPERIOR de lo ejecutable. PROHIBIDO citarla como 'parejas listas para FEP+'.

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `beee39bffee2bf6f0af39d96ee27c5c3bdeaad0f`, dirty=True

## Estado

- Creado: 2026-08-20T04:44:01.480847+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-20T04:44:38.485822+00:00)
- Finalizado: 2026-08-20T04:44:38.700529+00:00
- Razón de la decisión: EL NUMERO QUE NINGUNA DE LAS CINCO AUDITORIAS ANTERIORES CONTENIA. De las 91 parejas congenericas que FEP-03 declaro aptas: 75 EJECUTABLES HOY -ningun extremo con tautomero pendiente ni con hueco en el sitio-, 7 bloqueadas solo por tautomero y 9 por receptor. Las 75 abarcan 45 complejos distintos. Declarar los tautomeros de esos 7 sube la cifra a 82, y es una decision quimica documentada, no modelado estructural. LAS DOS CIFRAS HAY QUE DARLAS JUNTAS, Y LA SEGUNDA ES LA INCOMODA: bajo el criterio COMPLETO de FEP-02 -documentado_para_fep en ambos extremos, que exige ademas cadenas, disulfuros, metales, cofactores y aguas- solo quedan 19 parejas. La distancia entre 75 y 19 NO son defectos: es DOCUMENTACION AUSENTE. Ninguna de esas 56 parejas esta rota; lo que les falta es que alguien declare que hace con las aguas del sitio, con los metales y con las cadenas. Esa distincion decide como se planifica H2, porque documentar y reparar cuestan ordenes de magnitud distintos. POR QUE LA VISTA POR PAREJA ES MAS FAVORABLE QUE LA VISTA POR COMPLEJO: FEP-01 y FEP-02 reportan 19% y 41% sobre los 203, pero las 91 parejas aptas ya son un subconjunto filtrado por FEP-03 -pocas dianas con muchos analogos- y ese subconjunto esta mejor preparado que la media. No es contradiccion entre auditorias: es que la unidad de inferencia de un calculo FEP+ es la PAREJA y no el complejo, y nadie habia contado en esa unidad. LIMITACION DECLARADA ANTES DE CORRER: 'ejecutable hoy' significa SIN LOS DOS BLOQUEOS MEDIDOS, no 'lista para produccion'. Los 75 son una COTA SUPERIOR y queda PROHIBIDO citarlos como 'parejas listas para FEP+'. El criterio completo se reporto aparte y no se uso para clasificar precisamente porque lo cumplen tan pocos que absorberia toda la senal. Sin computo nuevo: cruce de cinco artefactos ya sellados, 0.011 s.
- Hashes de dataset: 3 archivo(s) con SHA-256
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
