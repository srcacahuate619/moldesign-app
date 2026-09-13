# MF-28-PRE

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

El fallo de colocacion es de ESTRATEGIA DE EXPLORACION: un roadmap probabilistico del espacio libre del bolsillo alcanza la cuenca nativa que la busqueda sesgada de Vina no alcanza, con el mismo presupuesto de CPU.

## Protocolo

Referencia: `doc 49 seccion 20.11(a). Cohorte congelada: los 48 de MF-02F/cohorte.json (33 COLOCACION + 15 CONTROL), la misma de MF-25 y MF-13. DESVIACION DECLARADA: el espacio es SE(3) x T^n; T^n se DISCRETIZA por el ensemble ETKDG (cada conformero es un nodo modal, seccion 20.2), no se muestrea continuo. Justificacion: MF-02A-EXT midio que la conformacion esta disponible en 83.9% a K30, asi que la discretizacion no es el cuello. Nodos: conformero uniforme del ensemble x posicion uniforme en la caja de 25 A x rotacion uniforme (cuaternion). Un nodo es LIBRE si ningun atomo pesado del ligando queda a menos de d_clash=2.6 A de un atomo pesado del receptor y el ligando cabe en la caja; d_clash declarado ANTES. Aristas: k-vecinos por RMSD de colocacion con planificador local por interpolacion lineal + SLERP, 5 puntos intermedios, arista valida si todos son libres. Brazo control: Vina exh=8 semilla 42 sobre el MISMO ensemble, corrido en esta misma maquina. PARIDAD DE PRESUPUESTO POR CPU MEDIDA, no por evaluaciones de energia: Vina no expone su conteo de evaluaciones, asi que el roadmap recibe exactamente el wall-clock que consumio Vina en ese complejo. El conteo de chequeos de colision se reporta como secundario.`

## Gate

PRIMARIO: fraccion de complejos donde el roadmap alcanza <=2 A (rmsd_pose_pocket, sin alineamiento) superior a la de Vina, McNemar exacto bilateral pareado. MDE DECLARADO ANTES (seccion 20.9): con n=33 en COLOCACION y c=0 perdidas, McNemar exacto exige b>=6 para p<0.05 (2*0.5^6=0.031). El efecto minimo detectable son 6 COMPLEJOS ADICIONALES CONVERTIDOS de los 30 que hoy fallan; 3-5 conversiones NO alcanzan significacion y se reportaran como no concluyentes, nunca como tendencia. SECUNDARIO descriptivo, sin gate: fraccion de nodos libres, tamano de la componente conexa mayor y si el mejor nodo cae en ella. LO FALSIFICA: si el roadmap no alcanza la cuenca con el mismo CPU, el problema no es la estrategia de exploracion.

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `642f32466cd6cf422e8f99d2af550a360d30d754`, dirty=True

## Estado

- Creado: 2026-08-19T04:28:47.007536+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-20T20:16:25.224867+00:00)
- Finalizado: 2026-08-20T20:16:25.726324+00:00
- Razón de la decisión: Prerregistro de MF-28, sellado RETROACTIVAMENTE el 2026-08-20 al detectarse en el barrido del registro que habia quedado en status created y decision PENDING. La procedencia es verificable y anterior a la corrida pese al sello tardio: su manifest.json se commiteo el 2026-08-19 a las 00:44 en 9117a17 -experiment(mf-28, mf-29-emp): prerregistros y runners de la via del generador- mientras que los resultados de MF-28 se commitearon el mismo dia a las 21:30 en b010641. El contenido no se ha modificado: declara la cohorte congelada de los 48 de MF-02F, la desviacion de discretizar T^n por el ensemble ETKDG con su justificacion en MF-02A-EXT, d_clash=2.6 A declarado antes, la paridad de presupuesto por CPU medida -porque Vina no expone su conteo de evaluaciones- y el MDE de la seccion 20.9: con n=33 y c=0, McNemar exacto exige b>=6 para p<0.05, de modo que 3-5 conversiones se reportan como no concluyentes y nunca como tendencia.
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
