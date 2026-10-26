# SUP-04-EXHAUSTIVIDAD-8T69 — desviaciones (append-only)

## 2026-10-25 — primera puesta en marcha (`4da324a5`)

- El shard 1 de `e8 pose` no llegó a evaluar nada: su cápsula usaba el puerto 18011, que ocupa la cápsula de QA de otra sesión
  (`sol-i18n`), y el inicio de sesión respondió 403. El shard 2 completó `redock-s43` y `redock-s45` con exhaustividad 8 sin
  deriva; sus scores no se han mirado. Se detuvo la campaña.
- Arreglo: las cápsulas de este experimento son la 3 y la 4 (puertos 18013 y 18014). No cambia docking, entradas, umbrales
  ni análisis. La campaña se reanuda: los dos registros terminales del shard 2 se conservan.
