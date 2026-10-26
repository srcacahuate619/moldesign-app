# Desviaciones y sucesos de CAL-D-01-R4-VMAT2-8T69 (declaradas, ninguna cambia un umbral ni una entrada)

1. **Fallo persistente de 4-67** (`COc1cc2c(cc1OCC13CC(C(F)(F)F)(C1)C3)CCN1C[C@@H](CC(C)(C)C)[C@H](O)C[C@H]21`,
   con un biciclo[1.1.1]pentano). El docking termina (8 poses) y el análisis posterior del pipeline no acaba: el
   producto lo corta a los 1200 s, dos veces (1204,6 y 1209,1 s). Los dos intentos están en
   `_work/panel/shard-1/panel-4-67.terminal.json`. Antes hubo un intento interrumpido a mano a los ~28 min
   (`_work/INCIDENTE_proceso1.json`), sin registro terminal. Según el registro previo (GO sólo con cero fallos
   persistentes) la decisión formal no puede ser GO. n = 88 de 89 (≥ 85, no EXPLORATORIO).
2. **Hilos zombi.** Los intentos agotados siguen calculando dentro del backend y frenaron los compuestos siguientes
   (116 s). Se reinició el arnés y el backend del proceso 1 (`_work/INCIDENTE_proceso1_b.json`); lo hecho se conservó.
3. **Análisis corregido tras congelar.** `_extraer_pose` calculaba el RMSD frente al cristal también para los compuestos
   del panel (otras moléculas) y se detenía. Ahora sólo lo calcula en el redocking. Cambia `cal_d01r4.py` respecto del
   hash de `protocolo.json`; no toca docking, entradas, umbrales ni estadístico. `rho_peor.py` no cambió.
4. El proceso 2 fue 44 compuestos sin incidentes; el proceso 1, 45 (44 acoplados + 4-67).
