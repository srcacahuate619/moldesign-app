# MF-33-ORD-PRE

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

La desviacion de la distribucion del primer acierto respecto a una geometrica homogenea que midio MF-33-EXT-MOD (chi2=11.04, gl=3, p=0.026) esta producida por el ORDEN NO INTERCAMBIABLE de los conformeros -conf0 es el primero de ETKDG y puede ser sistematicamente mejor- y no requiere heterogeneidad entre complejos para explicarse.

## Protocolo

Referencia: `RE-ANALISIS PURO, SIN COMPUTO DE DOCKING. MF-33-EXT guarda el rmsd_min de cada conformero por separado en corridas[], para los 116. Cada conformero se dockeo independientemente con la misma semilla, asi que su resultado NO depende del orden; el orden solo afecta al minimo acumulado y por tanto al indice del primer acierto. Permutar el orden es una RE-LECTURA EXACTA de los mismos datos, no una simulacion. Tres contrastes: (1) rango de conf0 entre sus K conformeros ordenados por rmsd_min, que bajo intercambiabilidad es uniforme con media normalizada 0.5; (2) 10000 permutaciones del orden por complejo, recalculando el primer acierto y el mismo chi2 contra la geometrica homogenea, con el procedimiento identico al de MF-33-EXT-MOD; (3) verificacion explicita de que el conjunto de nunca cubiertos es invariante bajo permutacion. Semilla 42. Script: scripts/analisis_mf33ord_permutaciones.py.`

## Gate

PRIMARIO, contraste (2): p_permutacion del chi2 observado contra la distribucion nula bajo orden intercambiable. DOS LECTURAS ESCRITAS ANTES: p_perm < 0.05 => LA DESVIACION ERA EL ORDEN, y C12 se reformula porque la desviacion proviene de la posicion de conf0 y no de heterogeneidad demostrada; p_perm >= 0.05 => LA DESVIACION SOBREVIVE AL ORDEN y la heterogeneidad entre complejos pasa a ser la explicacion en pie. El contraste (1) se reporta SIEMPRE, gane quien gane el (2), porque un conf0 con ventaja medida es un hecho de interes propio para el protocolo. PROHIBIDO: leer un p_perm >= 0.05 como que la heterogeneidad esta ESTABLECIDA -solo retira una explicacion alternativa, y establecer un componente refractario exigiria ajustar modelos de mezcla que aqui no se ajustan-; tocar C11, que es invariante por construccion y cuyo contraste (3) solo verifica; tocar la cobertura de MF-33-EXT, que tampoco depende del orden.

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `9fcb6f891963ee10e194d72024a62ac8c6b73adb`, dirty=True

## Estado

- Creado: 2026-08-21T15:50:39.080348+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-21T15:50:39.733984+00:00)
- Finalizado: 2026-08-21T15:50:39.944510+00:00
- Razón de la decisión: Prerregistro sellado con el hash del script ANTES de correrlo. Existe porque MF-33-EXT-MOD dejo dos explicaciones sin separar para su bloque 4, y una de ellas -el orden no intercambiable- resulta resoluble SIN COMPUTO NUEVO, cosa que no se advirtio al disenar aquel analisis. La clave es que cada conformero se dockeo independientemente y su rmsd_min esta guardado por separado en los 116 complejos: el orden solo entra en el minimo acumulado, asi que permutarlo es una re-lectura EXACTA y no una simulacion. Se declara de antemano el error de interpretacion mas probable y se prohibe: que un p_perm alto se lea como que la heterogeneidad queda ESTABLECIDA. No lo estaria; solo se habria retirado una explicacion alternativa, y afirmar un componente refractario exigiria ajustar modelos de mezcla -beta-geometrico o hurdle- que este analisis no ajusta y que el paper principal no necesita. Se declara tambien que el contraste (1) se reporta gane quien gane el (2): si conf0 tiene ventaja medida sobre un conformero al azar del mismo complejo, eso es un hecho del protocolo que interesa aunque no explique la curva.
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
