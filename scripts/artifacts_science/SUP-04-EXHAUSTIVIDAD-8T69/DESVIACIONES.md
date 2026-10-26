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
