# MF-33-A2-PRE

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

La brecha de 14 complejos que MF-33 midio entre el brazo A (1 conformero flexible) y el brazo B (K conformeros flexibles) se debe al ENSEMBLE y no al PRESUPUESTO. Si igualando la CPU un solo conformero alcanza lo que alcanza el ensemble, la brecha era CPU y MolFlex vuelve a ser redundante.

## Protocolo

Referencia: `Etapa 2 declarada como condicional en MF-33-PRE y activada porque B supero a A (14 discordantes a favor, 0 en contra, p=0.0001). Brazo A2: conf0.flex.pdbqt -el MISMO ligando del brazo A, primero por indice sin mirar RMSD- con exhaustiveness escalado POR COMPLEJO hasta igualar la CPU medida del brazo B: exh_A2 = round(8 * cpu_B / cpu_A), acotado a [8, 1024] y registrando cuando el tope actua. Vina escala aproximadamente lineal en exhaustiveness, asi que ese cociente iguala presupuesto sin tener que medirlo por ensayo y error. Todo lo demas congelado: semilla 42, num_modes=9, caja 25 A, mismo receptor, metrica rmsd_pose_pocket sin alineamiento, oraculo por brazo. Los brazos A y B se REUSAN de MF-33 sin recomputo. Cohorte: los mismos 48 (33 COLOCACION + 15 CONTROL).`

## Gate

PRIMARIO A2 vs B pareado en COLOCACION (n=33), McNemar exacto bilateral, con las mismas cifras declaradas en MF-33. TRES LECTURAS ESCRITAS ANTES: (1) LA BRECHA ERA CPU si A2 alcanza equivalencia con B -CI95 de la diferencia dentro de +-4 complejos-; entonces el ensemble NO aporta, MolFlex vuelve a ser redundante y la cartera C NO se reabre pese al resultado de MF-33; (2) LA BRECHA ERA EL ENSEMBLE si B sigue superando a A2 con 6 o mas discordantes a favor de B y 0 en contra; entonces la reapertura de la cartera C queda confirmada y el claim externo se autoriza; (3) MIXTA si A2 recupera parte de la brecha sin alcanzar equivalencia; se reporta la fraccion recuperada y NO se autoriza ningun claim de atribucion causal limpia. SECUNDARIO descriptivo: A2 vs A, que mide cuanto compra el presupuesto solo. PROHIBIDO: cambiar el conformero, elegirlo por RMSD, o reinterpretar MF-33 en funcion de este resultado sin sellar un corrigendum.

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `b5c11ab2459be03e41e23806d5cd0acb089f83eb`, dirty=True

## Estado

- Creado: 2026-08-19T19:52:57.375466+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-20T03:06:40.977152+00:00)
- Finalizado: 2026-08-20T03:06:41.166838+00:00
- Razón de la decisión: Prerregistro de la etapa 2 declarado ANTES de ejecutar: brazo A2 con exhaustiveness escalado por complejo para igualar la CPU de B, y las TRES lecturas posibles escritas con antelacion (CPU / ENSEMBLE / MIXTA). Se sella GO por convencion al declararse, NO por haber superado nada. El resultado activo la lectura (3).
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
