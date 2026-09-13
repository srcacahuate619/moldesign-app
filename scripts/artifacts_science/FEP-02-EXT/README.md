# FEP-02-EXT

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

Los 86 receptores con huecos de numeracion que conto FEP-02 no son 86 defectos accionables: la mayoria tiene el hueco lejos del sitio de union, donde no afecta a un calculo de energia libre. La fraccion que obliga a reparar antes de declarar el receptor es sustancialmente menor.

## Protocolo

Referencia: `Extension de FEP-02 sobre su misma cohorte de 203, aplicando a los huecos el mismo tratamiento que FEP-01-EXT aplico a los tautomeros: medir CONSECUENCIA en vez de EXISTENCIA. Para cada receptor con huecos se leen los residuos del PDB original de PDBBind (solo ATOM, sin aguas ni heteros), se detectan los saltos de numeracion por cadena, y cada hueco se clasifica por la distancia MINIMA de sus dos residuos flanqueantes a cualquier atomo pesado del ligando cristalografico: EN_EL_SITIO si <=8 A, PERIFERICO si <=15 A, LEJANO si mas. El radio de 8 A NO se elige nuevo: se reusa el mismo con el que FEP-02 definio 'sitio' al contar cadenas, metales y aguas. Solo lectura.`

## Gate

MEDICION SIN GATES DE DECISION, declarada como tal. Cantidades de interes: (a) fraccion de los receptores con huecos cuya clasificacion es EN_EL_SITIO; (b) reparto EN_EL_SITIO / PERIFERICO / LEJANO por complejo y por hueco individual; (c) distancia minima al ligando. LIMITACION DECLARADA ANTES: un hueco LEJANO no garantiza que la estructura sea utilizable -puede romper plegamiento o dinamica global-; lo que se mide es que fraccion tiene el defecto EN la region que decide la union, que es la unica que obliga a reparar ANTES de declarar el receptor. Un hueco lejano se declara; uno en el sitio se arregla. PROHIBIDO concluir que los receptores clasificados LEJANO estan listos para FEP+: FEP-02 exige ademas documentar cadenas, disulfuros, metales, cofactores y aguas, y eso no se toca aqui.

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `7fe43084cddf4c17149dd3dee9ce2fa06c2c57f2`, dirty=True

## Estado

- Creado: 2026-08-20T04:17:13.279767+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-20T04:18:05.232405+00:00)
- Finalizado: 2026-08-20T04:18:05.453065+00:00
- Razón de la decisión: MEDICION SIN GATES. 86 de 86 analizables, cero errores, 1.9 s de computo. EL RESULTADO ES OPUESTO AL DE FEP-01-EXT, Y ESA ES LA PARTE INFORMATIVA. Alli medir consecuencia en vez de existencia redujo el trabajo a un tercio (164 -> 54). Aqui apenas lo divide por dos: de los 86 receptores con huecos, 41 (47.7%) tienen el hueco EN EL SITIO -a 8 A o menos de algun atomo pesado del ligando-, 29 son perifericos (8-15 A) y solo 16 son lejanos. La mitad de los huecos esta justo en el bolsillo. Yo esperaba la misma reduccion que en tautomeros y no se produjo; asumirla habria sido extrapolar de un experimento a otro sin medir. ASIMETRIA ENTRE HUECOS Y COMPLEJOS: hay 337 huecos en total y solo 55 estan en el sitio, o sea el 16% por hueco frente al 48% por complejo. La razon es que basta UN hueco cerca del sitio para que el complejo sea accionable, de modo que contar huecos subestima el problema y contar complejos es la unidad correcta. CONSECUENCIA OPERATIVA PARA H2: la cartera queda con tres grupos y no con una lista de 86. 41 complejos hay que REPARAR antes de poder declarar el receptor; 29 son frontera y exigen mirar caso por caso; 16 basta con DECLARARLOS. LIMITACION DECLARADA ANTES DE CORRER: un hueco LEJANO no garantiza que la estructura sea utilizable -puede romper plegamiento o dinamica global-; lo medido es que fraccion tiene el defecto en la region que decide la union. Queda PROHIBIDO concluir que los 16 lejanos estan listos para FEP+: FEP-02 exige ademas documentar cadenas, disulfuros, metales, cofactores y aguas, y nada de eso se toca aqui. EL RADIO NO SE ELIGIO NUEVO: se reuso el mismo de 8 A con el que FEP-02 definio 'sitio' al contar cadenas, metales y aguas, para que las dos mediciones sean comparables. CRUCE QUE NO SE PUDO HACER: FEP-02 verifico que los 9 complejos que fallaron la parametrizacion en MF-10 tienen huecos de cadena 9 de 9; comprobar si esos huecos estan EN EL SITIO habria validado el criterio de este experimento contra un fallo real e independiente, pero el failures.jsonl de MF-10 esta VACIO y los pid no son recuperables desde el artefacto. Es una instancia concreta del hallazgo de FND-08 sobre dato crudo ausente, y el coste de esa deuda se paga aqui.
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
