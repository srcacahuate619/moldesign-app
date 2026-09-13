# MF-33-A2

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

La brecha de 14 complejos que MF-33 midio entre el brazo A (1 conformero flexible) y el brazo B (K conformeros flexibles) se debe al ENSEMBLE y no al PRESUPUESTO. Si igualando la CPU un solo conformero alcanza lo que alcanza el ensemble, la brecha era CPU y MolFlex vuelve a ser redundante.

## Protocolo

Referencia: `MF-33-A2-PRE. Etapa 2 declarada condicional en MF-33-PRE y activada porque B supero a A (14 discordantes a favor, 0 en contra, p=0.0001). Brazo A2: el MISMO conf0.flex.pdbqt del brazo A -primero por indice, sin mirar RMSD- con exhaustiveness escalado POR COMPLEJO hasta igualar la CPU medida de B: exh_A2 = round(8 * cpu_B / cpu_A), acotado a [8,1024]. Vina escala aproximadamente lineal en exhaustiveness. Todo lo demas congelado: semilla 42, num_modes=9, caja 25 A, mismo receptor, rmsd_pose_pocket sin alineamiento, oraculo por brazo. Brazos A y B REUSADOS de MF-33 sin recomputo. Cohorte: los mismos 48.`

## Gate

PRIMARIO A2 vs B pareado en COLOCACION, McNemar exacto. (1) LA BRECHA ERA CPU si equivalencia dentro de +-4 complejos; (2) LA BRECHA ERA EL ENSEMBLE si 6 o mas discordantes a favor de B con 0 en contra; (3) MIXTA en otro caso: se reporta la fraccion recuperada y NO se autoriza atribucion causal limpia. SECUNDARIO: A2 vs A, cuanto compra el presupuesto solo.

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `b5c11ab2459be03e41e23806d5cd0acb089f83eb`, dirty=True

## Estado

- Creado: 2026-08-20T03:06:04.043961+00:00
- Status: finished
- Decisión: INCONCLUSIVE
- Sellado: sí (2026-08-20T03:06:12.110975+00:00)
- Finalizado: 2026-08-20T03:06:40.753345+00:00
- Razón de la decisión: LECTURA MIXTA, la tercera de las tres declaradas antes. La brecha de 14 complejos que MF-33 midio entre A y B se parte casi por la mitad: el presupuesto compra 7 (A 12/33 -> A2 19/33) y el ensemble aporta los otros 7 (A2 19/33 -> B 26/33). PARIDAD DE CPU VERIFICADA: la razon CPU(A2)/CPU(B) es 0.975 en COLOCACION y 0.941 en CONTROL, y el tope de exhaustiveness=1024 NO se activo en ningun complejo, de modo que el escalado exh_A2 = round(8*cpu_B/cpu_A) igualo el presupuesto sin dejar ningun complejo en desventaja no declarada. A2 vs B en COLOCACION: 1 discordante a favor de A2 contra 8 a favor de B, McNemar exacto p=0.0391, delta 7 complejos. En CONTROL no hay diferencia (14/15 contra 15/15, p=1.0). POR QUE INCONCLUSIVE Y NO GO. El gate (2) exigia '6 o mas discordantes a favor de B Y 0 en contra'. Observado: 8 a favor, 1 EN CONTRA. La condicion literal NO se cumple. El criterio estadistico que motivaba ese MDE si se cumple -p=0.0391 < 0.05- pero esta es la SEGUNDA vez que la redaccion de un gate propio se queda corta y, a diferencia de la primera (MF-33, detectada y declarada con 8 filas sobre la mesa y antes del resultado completo), esta ambiguedad se descubrio DESPUES de ver los datos. Cuando eso ocurre la unica salida honesta es tomar la lectura MAS ESTRICTA, que es la (3). Por la regla preregistrada de la lectura (3) se reporta la fraccion recuperada y NO se autoriza atribucion causal limpia. LO QUE SI QUEDA ESTABLECIDO Y ES DEFENDIBLE: a paridad de CPU medida el ensemble mantiene 7 complejos de ventaja sobre un solo conformero, con 8 victorias pareadas contra 1 y p=0.0391. La pregunta 'controlaste el computo' tiene respuesta afirmativa documentada, con el control disenado y preregistrado ANTES de ejecutarlo. CONFUNDIDO RESIDUAL, DECLARADO: B no solo aporta diversidad conformacional, aporta K REINICIOS INDEPENDIENTES de busqueda; A2 tiene UNO solo con mas exhaustiveness. Este diseno NO separa 'diversidad de conformaciones de partida' de 'numero de reinicios independientes' -la misma variable que toco MF-02F- y esa es la pregunta que sigue. CONSECUENCIA PARA MF-33: su decision GO no cambia, el ensemble sigue aportando; lo que cambia es la MAGNITUD del claim, de 14 complejos a 7. Cualquier cita de MF-33 debe acompanarse de este numero. No se toco val, test ni D-RC-CONFIRM.
- Hashes de dataset: 1 archivo(s) con SHA-256
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
