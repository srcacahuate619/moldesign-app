# MF-28

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

El fallo de colocacion es de ESTRATEGIA DE EXPLORACION: un roadmap probabilistico del espacio libre del bolsillo alcanza la cuenca nativa que la busqueda sesgada de Vina no alcanza, con el mismo presupuesto de CPU.

## Protocolo

Referencia: `Prerregistro MF-28-PRE, commiteado el 2026-08-19 00:44 en 9117a17, anterior a la corrida. Doc 49 seccion 20.11(a). Cohorte congelada de los 48 de MF-02F/cohorte.json (33 COLOCACION + 15 CONTROL), la misma de MF-25 y MF-13. DESVIACION DECLARADA: T^n se discretiza por el ensemble ETKDG y no se muestrea continuo, justificado en que MF-02A-EXT midio la conformacion disponible en 83.9% a K30. Nodo LIBRE si ningun atomo pesado del ligando queda a menos de d_clash=2.6 A de uno del receptor; aristas por k-vecinos con planificador local de interpolacion lineal + SLERP a 5 puntos. Brazo control Vina exh=8 semilla 42 sobre el MISMO ensemble. PARIDAD POR CPU MEDIDA: el roadmap recibe el wall-clock que consumio Vina en ese complejo, porque Vina no expone su conteo de evaluaciones. Script: scripts/run_mf28_roadmap.py.`

## Gate

PRIMARIO: fraccion de complejos donde el roadmap alcanza <=2 A (rmsd_pose_pocket, sin alineamiento) superior a la de Vina, McNemar exacto bilateral pareado. MDE DECLARADO ANTES (seccion 20.9): con n=33 en COLOCACION y c=0, McNemar exacto exige b>=6 para p<0.05; 3-5 conversiones NO alcanzan significacion y se reportan como no concluyentes, nunca como tendencia. SECUNDARIO descriptivo sin gate: fraccion de nodos libres, tamano de la componente conexa mayor y si el mejor nodo cae en ella. LO FALSIFICA: si el roadmap no alcanza la cuenca con el mismo CPU, el problema no es la estrategia de exploracion.

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `5a32d163894336f3bd6673b2df1a63e59ab66f3c`, dirty=True

## Estado

- Creado: 2026-08-20T20:16:48.593057+00:00
- Status: finished
- Decisión: NO_GO
- Sellado: sí (2026-08-20T20:17:11.880223+00:00)
- Finalizado: 2026-08-20T20:17:12.268268+00:00
- Razón de la decisión: SELLADO RETROACTIVO el 2026-08-20. El experimento corrio completo el 2026-08-19 -48 de 48 complejos, 40247 s, resultados commiteados a las 21:30 en b010641- pero su directorio se quedo SIN manifest.json, y el paragrafo 1 del roadmap lo daba por sellado NO_GO desde entonces. El barrido del registro lo detecto; esto cierra el hueco sin recomputar nada. Su prerregistro MF-28-PRE se commiteo el 2026-08-19 a las 00:44 en 9117a17, anterior a la corrida. LA HIPOTESIS QUEDA FALSIFICADA EN LA DIRECCION DECLARADA. En COLOCACION (n=33) Vina alcanza <=2 A en 26 complejos y el roadmap en 4. McNemar exacto pareado: b=1 complejo donde gana el roadmap, c=23 donde gana Vina, p=0.0. El MDE preregistrado exigia b>=6 con c=0 para declarar mejora; se obtuvo b=1 con c=23, es decir, no solo no hay mejora sino perdida masiva y significativa. RMSD mediano 1.184 A para Vina contra 4.437 A para el roadmap. En CONTROL (n=15) el patron se repite: Vina 15 de 15, roadmap 7, b=0 c=8 p=0.0078. EL PORQUE, QUE ES LO QUE VALE: la fraccion mediana de nodos libres es 0.00417 en COLOCACION -cuatro de cada mil configuraciones muestreadas no chocan- y 0.0213 en CONTROL. El espacio libre del bolsillo es tan escaso que un roadmap probabilistico uniforme casi no encuentra donde poner nodos, y en 2 complejos de CONTROL no hallo NINGUNA configuracion libre. La busqueda sesgada de Vina no es un defecto a corregir con mejor exploracion: es lo que hace viable el problema. CONSECUENCIA: la cartera C no se reabre por la via de la estrategia de exploracion, y H2 se lleva el presupuesto de atencion. Junto con MF-29-EMP -que midio que subir el presupuesto del mismo buscador tampoco rinde- cierra las dos vias de exploracion que quedaban abiertas. NOTA DE INTEGRIDAD DEL ARTEFACTO, ya presente en metrics.json y que se conserva: el metrics.json se reconstruyo desde per_complex.jsonl tras un TypeError en la fase de resumen -median() recibio None de los 2 complejos sin configuracion libre-. Los 48 se ejecutaron completos y no se recomputo ningun docking. La metrica se verifico contra molflex.rmsd_pose_pocket en 46 complejos con delta_max 0.0 a 4 decimales.
- Hashes de assets: 2 archivo(s) con SHA-256

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
