# CAL-D-01-R4-2 — desviaciones (append-only)

## 2026-10-24 — firma antes de medir

- `REGISTRO_PREVIO_PILOTO.md` SHA-256 `d6ab34b3c84e8477629b7c50c2f54a0f225be4f6867e0ee62d276ee12bbecbbe`. Desde aquí no se edita.
- Script `scripts/cal_d01r4_2/piloto_467.py` SHA-256 `848533909de680b6e3e1b2b7451c80a787df368bd81e5be84bbf7a51f6721051`; producto `efdf4438` (árbol limpio salvo este script).

## 2026-10-24 — resultado del piloto (un intento)

- **COMPLETA.** SUCCESS en 343,3 s de evaluación (antes, FAILURE a los 1200 s en dos intentos). Vina 1.2.7, 4 CPU, semilla 42,
  exhaustividad 8, 9 poses; microestado igual al congelado; receptor preparado `8fc027ca…`, **el mismo que R4** (el cambio de
  producto desde `6f3ff1b5` no lo altera).
- La validación física de las poses queda `not_evaluated` con `VALIDADOR_EXCEDIO_EL_PLAZO` (300 s), como se esperaba
  (PoseBusters `energy_ratio`/ETKDG con el biciclopentano). El acoplamiento no se ve afectado.
- Se miraron sólo las claves y el estado de `structural_evidence`; el score, el RMSD y la pose siguen sin leer
  (`piloto/crudo.json`, SHA-256 `62ec8c5b…a448d`).
- Pendiente de decisión antes del panel: cómo cuenta una validación física `not_evaluated` en la regla de «cero fallos
  persistentes» de R4.

## 2026-10-24 — registro previo del panel (decisión del propietario)

- El propietario aceptó la recomendación: la regla de R4 sin cambios; una validación física `not_evaluated` con score cuenta
  como evaluada y se declara aparte, con su sensibilidad, sin decidir.
- `REGISTRO_PREVIO_R4_2.md` SHA-256 `aa84631fbec33538eb089f4b8065e7114f701447fcfc3c6bb30ab2cbdf73b0c1`. Desde aquí no se edita.
- Arnés `scripts/cal_d01r4_2/cal_d01r4_2.py` SHA-256 `13d108e64593e813f75dbd6585a045eccd7c3b9346cd272a60da713cf9c2aff5`;
  importa sin editar `scripts/cal_d01r4/`. El crudo del piloto sigue sin leer y no se usa.

## 2026-10-24 — antes de la primera corrida: hash del arnés de R4

- El primer `ejecutar --fase pose` se detuvo antes de evaluar nada: `cmd_ejecutar` de R4 compara `cal_d01r4.py` con el hash
  de `protocolo.json` (`f2f37dd5…`, versión `78797fdb`), anterior al arreglo del análisis que R4 declaró en su desviación 3.
  El manifiesto sellado de R4 guarda el de la versión actual (`556c77d7…`, `d8150aca`).
- El arnés de R4-2 trae su propio `ejecutar`, copia del de R4 salvo que compara `cal_d01r4.py` con el hash del sello de R4;
  el resto (panel, `rho_peor.py`, `capsula.mjs`, `calibracion_receptor.py`) sigue contra `protocolo.json`. No toca
  docking, entradas, umbrales ni estadístico. Arnés nuevo SHA-256 `bc87ad9eca58d7459c95b866833ae11ecd43e4833fed579fbae952b008cce5a6`. Ningún score visto.
- El `ejecutar` nuevo leía el hash de la clave equivocada del manifiesto de R4 (`dataset_hashes`; el arnés está en `assets_hashes`) y falló con KeyError antes de evaluar. Corregido; arnés SHA-256 `a4a754e7874ca752709b5284d5a1f2d7b795ce9179a4916380620353bc1ecfb3`.

## 2026-10-24 — ejecución y resultado

- Producto `889cbdef` (sólo el arnés y el registro de cambios sobre `18eb7e13`; nada del backend). Árbol limpio durante toda la campaña.
- Puerta de pose: 5 de 5 semillas, RMSD 0,671–0,714 Å, todas `passed`. GO.
- Panel: 89 de 89 SUCCESS en el primer intento, dos shards en paralelo; ningún reintento, ninguna deriva. 4-67 completa en
  334,7 s con la validación física `not_evaluated` (`VALIDADOR_EXCEDIO_EL_PLAZO`). Sensibilidad S-4-31-118: SUCCESS. 3,73 CPU-core-h.
- P1: ρ = 0,392 (IC 95 % 0,216–0,540), ρ_peor = 0,322 (0,140–0,475), cero fallos persistentes, cero desviaciones. **GO.**
- Declarado (no decide): 1 advertencia (4-67); sin ella, ρ = 0,391 (0,219–0,537) y ρ_peor = 0,320 (0,139–0,473). Los 88 padres
  comunes con R4 dan la misma energía top-1 (diferencia máxima 0,000 kcal/mol). Estados del panel: 46 passed, 37 review, 5 failed, 1 not_evaluated.
- El crudo del piloto sigue sin leer y no entra en el análisis.
- Corrección de la línea anterior: la campaña corrió sobre `53a7905b` (el arreglo de la clave `assets_hashes`), no sobre `889cbdef`; la guardia del arnés exigía ese HEAD fijo y el árbol limpio.
