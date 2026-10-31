# SUP-04-EXHAUSTIVIDAD-8T69 — desviaciones (append-only)

## 2026-10-25 — primera puesta en marcha (`4da324a5`)

- El shard 1 de `e8 pose` no llegó a evaluar nada: su cápsula usaba el puerto 18011, que ocupa la cápsula de QA de otra sesión
  (`sol-i18n`), y el inicio de sesión respondió 403. El shard 2 completó `redock-s43` y `redock-s45` con exhaustividad 8 sin
  deriva; sus scores no se han mirado. Se detuvo la campaña.
- Arreglo: las cápsulas de este experimento son la 3 y la 4 (puertos 18013 y 18014). No cambia docking, entradas, umbrales
  ni análisis. La campaña se reanuda: los dos registros terminales del shard 2 se conservan.

## 2026-10-25 — pausa a petición del propietario (producto `3ca7f633`)

- Campaña detenida a las 21:5x (hora de México) para liberar la máquina. Hechos: `e8` completo (5 redockings y 89 del panel),
  `e32` con sus 5 redockings y 22 de 89 del panel. Sin fallos, sin deriva y sin crudos huérfanos; la corrida que estaba
  en curso en cada shard se perdió sin dejar registro y se repetirá entera. Ningún score se ha mirado.
- **Condición para reanudar:** el código que acopla tiene que ser el de `3ca7f633`. Antes de relanzar `campana.sh`,
  `git diff --stat 3ca7f633 HEAD -- backend tools scripts/cal_d01r4 scripts/sup04_exhaustividad` debe salir vacío (o la
  diferencia se anota aquí antes de acoplar). La guardia de deriva sigue comprobando receptor, microestado, semilla,
  exhaustividad, Vina y CPU en cada corrida.

## 2026-10-25 — diferencia de código antes de reanudar

- Desde `3ca7f633` sólo cambia en `backend/` el PDF del dossier (`services/dossier/pdf.py`: `splitInRow=1` en las tablas de
  campos) y una prueba nueva. No toca preparación, docking, Vina ni la lectura de resultados que usa el análisis; la guardia de
  deriva sigue comprobando cada corrida.

## 2026-10-26 — reanudación y cierre de la campaña (producto `c0341284`)

- Relanzada `campana.sh` a las 00:05 (hora de México) sobre `c0341284`, con la condición de arriba comprobada: entre `3ca7f633`
  y `c0341284` sólo cambian `services/dossier/pdf.py` y su prueba. Los registros terminales de `e8` y de los 22 del panel de
  `e32` hechos sobre `3ca7f633` no se repitieron; el resto de `e32`, `e16` y `e8s43` corrió sobre `c0341284`. Los registros no
  guardan el commit: lo fijan la hora de `campana.log` y esta nota.
- Campaña completa a las 02:20: 371 registros terminales (89 del panel en cada uno de los cuatro brazos y 5 redockings en `e8`,
  `e16` y `e32`), todos SUCCESS, sin fallos ni deriva.
- Mientras corría, en otro worktree se ejecutó dos veces la puerta 12 (`accept_evaluation_runtime.py`, dos evaluaciones de
  aspirina contra 3F75 cada vez) y unas pruebas del frontend. Comparten la CPU y alargan el tiempo de pared; no cambian lo que
  Vina calcula con semilla, exhaustividad y CPU fijas, y la guardia de deriva lo comprueba en cada corrida.
- Hacia las 01:2x, un fallo de la guarda de publicación (`check_push_publico.py`, push desde un worktree) escribió
  `core.bare = true` en `.git/config` durante unos minutos. Con eso `git status` falla y la guardia del experimento habría
  abortado la corrida en curso; no ocurrió (ningún registro ni log lo menciona y e16 pose terminó 5/5). Corregido a mano y en
  la guarda.
- `e8` repite exactamente las 89 energías de `CAL-D-01-R4-2-VMAT2-8T69` (diferencia máxima 0,0 kcal/mol), como predecía el
  registro.
