# MF-33-A3

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

La ventaja del ensemble flexible de MF-33 no es diversidad conformacional sino ARTEFACTO DE CONTEO DE POSES: la metrica es de oraculo -mejor RMSD entre las poses que el brazo CONSERVA- y num_modes=9 limita las poses por corrida, no las buscadas, de modo que el brazo B extraia su oraculo de 29 veces mas muestras que A y A2.

## Protocolo

Referencia: `Prerregistro MF-33-A3-PRE, sellado antes de correr. Corrigendum y etapa 3 de MF-33. BRAZO A3: K corridas INDEPENDIENTES de Vina desde el MISMO conf0.flex.pdbqt, con K = n_docks del brazo B en ese complejo, exh=8, num_modes=9 y semillas distintas 42..42+K-1. El oraculo se toma sobre las K*9 poses. Eso iguala a B en las tres variables confundidas -corridas independientes, poses conservadas y CPU aproximada- dejando como UNICA diferencia la conformacion de partida. Brazos A, B y C se reusan de MF-33 y A2 de MF-33-A2, sin recomputo. Cohorte: los mismos 48. Corrio en la maquina local con 10 workers, 24691 s. Script: scripts/run_mf33a3_reinicios.py.`

## Gate

PRIMARIO A3 vs B pareado en COLOCACION (n=33), McNemar exacto bilateral, con g_A3 = complejos donde A3 alcanza <=2 A y B no, y g_B = donde B alcanza y A3 no. TRES LECTURAS ESCRITAS ANTES: (1) LA VENTAJA ERA EL CONTEO DE POSES si A3 y B son equivalentes -diferencia dentro de +-4 complejos-, y entonces la magnitud de MF-33 COLAPSA; (2) LA DIVERSIDAD CONFORMACIONAL ES REAL si g_B >= 6 con g_A3 = 0, y entonces MF-33 sobrevive con su magnitud corregida y el claim externo se autoriza; (3) MIXTA en cualquier otro caso, incluido g_B >= 6 con g_A3 >= 1. SECUNDARIO descriptivo: A3 vs A2, que separa 'muchas corridas poco profundas' de 'una corrida muy profunda' a igual CPU y distinto conteo de poses. PROHIBIDO: reinterpretar MF-33 o MF-33-A2 sin sellar el corrigendum; elegir el conformero por RMSD; cambiar num_modes respecto de B.

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `55112383f5c72b0dbe3359ce19c3431f880666eb`, dirty=False

## Estado

- Creado: 2026-08-21T02:21:24.531043+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-21T02:21:25.166442+00:00)
- Finalizado: 2026-08-21T02:21:50.424300+00:00
- Razón de la decisión: LECTURA (2) DEL PRERREGISTRO: LA DIVERSIDAD CONFORMACIONAL ES REAL. En COLOCACION (n=33), g_B = 7 y g_A3 = 0, McNemar exacto bilateral p = 0.0156. El umbral declarado antes de correr era g_B >= 6 con g_A3 = 0, y se cumple exactamente. LA HIPOTESIS QUEDA FALSIFICADA EN LA DIRECCION DECLARADA: el defecto que motivo este corrigendum -que el brazo B extraia su oraculo de 29 veces mas muestras- era real como confundido y NO explica su ventaja. A3 igualo a B en las TRES variables confundidas y la comparacion no deja escapatoria: corridas independientes K = n_docks de B por complejo; poses conservadas 261 medianas, las mismas que B; y CPU con razon A3/B = 1.196, es decir, A3 gasto un 20% MAS que B, de modo que cualquier sesgo residual de presupuesto favorecia a A3. Aun asi B alcanza 26 de 33 y A3 19, y los 7 complejos de diferencia van todos en la misma direccion: no hay ni uno solo donde A3 alcance y B no. EL SECUNDARIO CIERRA EL ARGUMENTO, Y ES LO MAS LIMPIO DEL EXPERIMENTO: A3 alcanza 19 y A2 alcanza 19. Identico. A2 tenia paridad de CPU con 9 poses conservadas; A3 tiene paridad de CPU con 261. Multiplicar por 29 el numero de poses conservadas desde el mismo conformero NO MUEVE NI UN COMPLEJO. El conteo de poses, que era la explicacion alternativa que este experimento venia a descartar, esta medido y no aporta nada; los 7 complejos de diferencia son atribuibles a la unica variable que quedaba libre, la conformacion de partida. CONSECUENCIAS PARA EL REGISTRO: se levanta la etiqueta defecto-abierto de MF-33 y de MF-33-A2. La magnitud de MF-33 -1/33 rigido, 12/33 un conformero flexible, 26/33 ensemble flexible- es citable, y el claim externo queda autorizado por la regla (2). MF-33-A2 se relee sin cambiar su numero: su 19/33 no era una limitacion de conteo de poses. CONSECUENCIA PARA MF-33-EXT, que estaba esperando esta respuesta: su titular es la COBERTURA FINAL y no la cobertura a presupuesto igualado, porque la ventaja del ensemble no es presupuesto. La curva de cobertura contra presupuesto que su prerregistro declara se conserva como secundario descriptivo. CONSECUENCIA PARA MF-30-ALCANCE: el comparador activo se mantiene en 26/33 y su gate caducado sigue caducado 8.67x. COMPROBACION DE CORDURA DECLARADA Y CUMPLIDA: en CONTROL (n=15) todos los brazos convergen -C 15, A 14, A2 14, A3 15, B 15- con g_A3 = g_B = 0. El efecto es especifico del estrato dificil y no un artefacto general del brazo. Cero corridas fallidas en los 48 complejos. LIMITES: n=33 en COLOCACION y el MDE declarado era de 6 complejos, asi que esto detecta el efecto pero no lo cuantifica con precision; no dice POR QUE la diversidad conformacional ayuda, solo que ayuda; y no toca la cuestion de si esos conformeros son alcanzables en produccion, que es el techo que MF-02A-EXT midio en 83.9% a K30.
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
