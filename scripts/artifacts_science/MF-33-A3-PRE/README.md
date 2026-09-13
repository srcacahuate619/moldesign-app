# MF-33-A3-PRE

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

La ventaja del ensemble medida en MF-33 y MF-33-A2 se explica por el numero de POSES CONSERVADAS y no por la diversidad conformacional. Igualando poses, corridas y CPU, un solo conformero alcanza lo que alcanza el ensemble.

## Protocolo

Referencia: `Corrigendum y etapa 3 de MF-33. DEFECTO QUE MOTIVA ESTE EXPERIMENTO: la metrica es de oraculo -mejor RMSD entre las poses que el brazo CONSERVA- y num_modes=9 limita las poses escritas POR CORRIDA, no las buscadas. El brazo B hace 29 corridas (mediana) y conserva 261 poses; los brazos A y A2 hacen una y conservan 9. B extrae su oraculo de 29x mas muestras, de modo que ganaria aunque la busqueda fuese identica. BRAZO A3: K corridas INDEPENDIENTES de Vina desde el MISMO conf0.flex.pdbqt, con K = n_docks del brazo B en ese complejo, exh=8, num_modes=9 y SEMILLAS DISTINTAS por corrida (42, 43, ... 42+K-1). Oraculo sobre las K*9 poses. Eso iguala a B en las tres variables confundidas -corridas independientes, poses conservadas y CPU aproximada- dejando como UNICA diferencia la conformacion de partida. Brazos A, A2, B y C se REUSAN de MF-33 y MF-33-A2 sin recomputo. Cohorte: los mismos 48.`

## Gate

PRIMARIO A3 vs B pareado en COLOCACION (n=33), McNemar exacto bilateral. DIRECCIONES DEFINIDAS EXPLICITAMENTE, porque la redaccion ambigua ya costo dos veces en esta serie: se llama g_A3 al numero de complejos donde A3 alcanza <=2 A y B no, y g_B al numero donde B alcanza y A3 no. TRES LECTURAS ESCRITAS ANTES: (1) LA VENTAJA ERA EL CONTEO DE POSES si A3 y B son equivalentes -diferencia de complejos dentro de +-4-; entonces la diversidad conformacional NO aporta, el claim de MF-33 sobre la magnitud COLAPSA y la cartera C no se reabre por esta via; (2) LA DIVERSIDAD CONFORMACIONAL ES REAL si g_B >= 6 con g_A3 = 0; entonces MF-33 sobrevive con su magnitud corregida y el claim externo se autoriza; (3) MIXTA en cualquier otro caso, incluido g_B >= 6 con g_A3 >= 1: se reporta la fraccion y NO se autoriza atribucion causal limpia. SECUNDARIO descriptivo: A3 vs A2, que separa 'muchas corridas poco profundas' de 'una corrida muy profunda' a igual CPU y distinto conteo de poses. PROHIBIDO: reinterpretar MF-33 o MF-33-A2 sin sellar el corrigendum correspondiente; elegir el conformero por RMSD; cambiar num_modes respecto de B.

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `b5c11ab2459be03e41e23806d5cd0acb089f83eb`, dirty=True

## Estado

- Creado: 2026-08-20T03:27:29.513234+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-20T03:29:09.061782+00:00)
- Finalizado: 2026-08-20T03:29:09.257088+00:00
- Razón de la decisión: Prerregistro de la etapa 3 sellado ANTES de ejecutar, junto con el runner que lo implementa (hash registrado). Declara el DEFECTO que motiva el experimento -el brazo B conserva 261 poses de mediana contra 9 de A y A2, de modo que gana el oraculo aunque la busqueda sea identica-, el diseno que lo corrige -K corridas independientes desde el mismo conformero, igualando corridas, poses conservadas y CPU, dejando la conformacion de partida como unica diferencia- y las TRES lecturas posibles. TERCERA VEZ QUE SE REDACTA UN GATE DE ESTA SERIE Y PRIMERA EN QUE LAS DIRECCIONES SE DEFINEN EXPLICITAMENTE: g_A3 = complejos donde A3 alcanza y B no; g_B = donde B alcanza y A3 no. Las dos anteriores costaron una aclaracion a posteriori en MF-33 y una lectura estricta forzada en MF-33-A2. Se sella GO por convencion al declararse, NO por haber superado nada. NO EJECUTADO: coste previsto ~42.6 CPU-h (4-6 h con 10 workers, CPU al 90% sostenido); se pospone deliberadamente para no encadenar tres experimentos largos en la misma maquina el mismo dia.
- Hashes de assets: 3 archivo(s) con SHA-256

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
