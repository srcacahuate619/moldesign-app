# MF-33-EXT-MOD-PRE

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

Sobre los 116 se pueden contestar tres cosas que los 33 no permitian: (1) si la ventaja del ensemble es general o esta concentrada en el estrato dificil; (2) si los seis predictores de MF-33-DOSIS replican, y sobre todo si sobreviven en los 68 complejos que NO estaban en la cohorte de 48; y (3) si el fenomeno es de DOSIS -mas oportunidades, mas espacio conformacional- o de ACIERTO -basta con que una inicializacion caiga en region favorable-, que es la hipotesis derivada de MF-33-A3 y MF-33-DOSIS y que hasta ahora no se podia contrastar.

## Protocolo

Referencia: `ANALISIS PREREGISTRADO ANTES DE QUE MF-33-EXT CIERRE, sobre los datos que su runner ya registra y sin computo nuevo. BLOQUE 1: curva_oraculo[0] ES el resultado de un solo conformero y el oraculo final el del ensemble, asi que la comparacion sale pareada por complejo sin coste. BLOQUE 2: los seis predictores de MF-33-DOSIS sobre los 116, declarados como REPLICACION y no como descubrimiento, porque ya se miraron en los 33. BLOQUE 3: los cinco prospectivos sobre los 68 que no estan en la cohorte de 48, con FDR propio; frac_vuelve queda excluido porque MF-14 solo cubrio 48 complejos y no tiene version fuera de muestra. BLOQUE 4: primer_dock_que_cubre contra una geometrica con p estimada por maxima verosimilitud. Spearman de rangos, Benjamini-Hochberg q=0.05. Script: scripts/analisis_mf33ext_moderadores.py.`

## Gate

BLOQUE 1, TRES LECTURAS ESCRITAS ANTES con umbrales de 5 y 15 puntos porcentuales fijados aqui y que NO se mueven: ESCENARIO A EFECTO REAL PERO CONCENTRADO si delta global < 5 pp y delta en COLOCACION >= 15 pp, y entonces NO se justifica regenerar la cohorte universalmente; ESCENARIO B EFECTO GENERAL si delta global >= 15 pp, y entonces la arquitectura debe cambiar y la regeneracion queda justificada; ESCENARIO C EFECTO GRANDE E IMPREDECIBLE si hay delta >= 15 pp en el global o en un subconjunto Y ningun predictor sobrevive los bloques 2 y 3, y entonces lo indicado es muestreo secuencial con criterio de parada y no una politica de descriptores estaticos. Cualquier otra combinacion se reporta como MIXTO con sus numeros, sin forzarla. BLOQUE 2 ES REPLICACION Y NO DESCUBRIMIENTO: los seis ya se miraron en los 33, no son hipotesis virgenes, y LA CONCLUSION SE TOMA DEL BLOQUE 3. Un predictor que aparezca en los 116 y desaparezca en los 68 externos es estructura de la cohorte original filtrandose por los 48 solapados. BLOQUE 3 ES LA REGLA DE DECISION: un predictor solo se declara candidato a politica adaptativa si sobrevive AQUI. BLOQUE 4: compatible con ACIERTO si la curva observada no se separa de la geometrica y el primer acierto no se concentra en la corrida 1; compatible con DOSIS si crece sostenidamente por encima de la geometrica; HETEROGENEIDAD si se queda por debajo, lo que indicaria complejos con p cercano a cero que ningun K rescata. PROHIBIDO: mover los umbrales de 5 y 15 pp; presentar el bloque 2 como descubrimiento; reabrir la cantidad primaria de MF-33-EXT, que es su cobertura contra el liston de 0.90 heredado del G5 de MF-02D y esta declarada en MF-33-EXT-PRE.

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `8a86edc5710495ea582cff38d8e16e12d2fa6f9c`, dirty=True

## Estado

- Creado: 2026-08-21T03:23:52.008882+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-21T03:23:54.053125+00:00)
- Finalizado: 2026-08-21T03:23:54.512162+00:00
- Razón de la decisión: Prerregistro sellado con el hash del script MIENTRAS MF-33-EXT AUN CORRE -iba por 10 de 116 al momento de sellar-, de modo que las tres reglas de lectura son demostrablemente anteriores a los datos. Es la unica forma de que este analisis no sea post-hoc, y la razon de sellarlo ahora y no manana. TRES DECISIONES QUE SE TOMAN AQUI Y NO DESPUES. PRIMERA, los umbrales de 5 y 15 puntos porcentuales del bloque 1 quedan fijados sin haber visto ninguna cobertura. SEGUNDA, y es la que mas protege: el bloque 2 se declara REPLICACION y no descubrimiento. Los seis predictores ya se miraron en los 33 de MF-33-DOSIS; volver a mirarlos en un conjunto que contiene a esos mismos 33 no los convierte en hipotesis nuevas, y presentarlo asi seria contar dos veces la misma observacion. Por eso la regla de decision se traslada explicitamente al bloque 3, los 68 complejos que no estaban. TERCERA, se declara de antemano que frac_vuelve no puede pasar el bloque 3, porque MF-14 solo cubrio 48 complejos: si acabara siendo el unico superviviente del bloque 2, no bastaria, y conviene saberlo antes de que la tentacion exista. EL BLOQUE 4 ES LA PRIMERA OPORTUNIDAD DE CONTRASTAR la hipotesis de acierto-contra-dosis, que hasta ahora era una lectura de dos nulos independientes -A3 mostro que multiplicar por 29 las poses desde el mismo conformero no mueve un complejo, y DOSIS que la dispersion del ensemble no correlaciona con su beneficio-. El campo primer_dock_que_cubre que el runner de MF-33-EXT ya registra permite compararla contra un modelo explicito, y se declara ademas el tercer desenlace -heterogeneidad, complejos con p cercano a cero- porque seria evidencia convergente con lo que MF-33-CRUCES y REC-09 sugirieron por otra via: que parte de los fallos no son de muestreo sino de especificacion.
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
