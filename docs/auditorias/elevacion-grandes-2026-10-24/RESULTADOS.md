# Ligandos grandes en la elevación: resultados (2026-10-24)

Criterios de `REGISTRO_PREVIO.md` (`fcbb9d1e`), aplicados tal como quedaron
escritos por `resumen.py`. Datos: `e1.jsonl`, `e2.jsonl`, `e3.jsonl`. Producto
de referencia: `26df919c`. Los tres scripts reproducen la elección del producto
(`comun.comprobar_reproduccion`, comprobado en 5 moléculas antes de medir).

| | Veredicto | Por qué |
|---|---|---|
| E1 dibujo ajustado al 3D | **NO_GO** (respaldo y por defecto) | rescata 10 de 25 abstenciones (hacía falta el 75 %) |
| E2 ΔE con xTB | **parcial** | ΔE(xTB-ALPB) = 0,69 · ΔE(MMFF) (exagera si ≤ 0,5; se sostiene si ≥ 0,8) |
| E3 plegado restringido | **NO_GO** | 5/37 abstenciones (hacían falta ≤ 4) y 11 de 29 moléculas sin ningún embebido |

## E1 — dibujo que se ajusta al 3D

| conjunto · geometría | se abstienen, dibujo normal | se abstienen, ajustado | razón mediana normal → ajustado | legibles normal → ajustado |
|---|---:|---:|---:|---:|
| G37 · proxy de pose | 25/37 | 16/37 | 1,21 → 0,96 | 37 → 28 |
| G37 · elegido | 6/37 | 14/37 | 0,73 → 0,84 | 37 → 29 |
| O167 · proxy de pose | 42/167 | 11/167 | 0,60 → 0,52 | 167 → 166 |
| O167 · elegido | 1/167 | 4/167 | 0,33 → 0,39 | 167 → 166 |

- **Respaldo: NO_GO.** De las 25 de G37 que se abstienen con el dibujo normal y
  el proxy de pose, el dibujo ajustado deja a ≤ 1 enlace sólo 10 (40 %; hacía
  falta el 75 %). De esas 10, 8 son legibles (este criterio sí se cumplía).
- **Por defecto: NO_GO**, porque el registro exige además el criterio de
  respaldo. Sus dos condiciones propias se cumplían: 194 de 204 dibujos
  ajustados son legibles (≥ 184) y se abstienen 27 frente a 67.
- Con el conformador **elegido** el dibujo ajustado es peor que el normal: el
  elegido ya es el que más se parece al dibujo normal.
- Lo que no estaba previsto y conviene saber: **con una geometría que no se elige
  por parecido al dibujo, se abstienen 25 de 37 grandes y 42 de 167 del conjunto
  original** con el dibujo normal. Es un proxy de pose, no poses reales, pero
  apoya la decisión de `3ea0aa92`: en Moldex la abstención será frecuente, y
  enseñar la pose en 3D sin levantarla evita esconderla.
- Lámina para revisión visual: `e1_lamina.svg` (12 moléculas de G37, normal y
  ajustado, con el proxy de pose).

## E2 — ¿la cifra de ΔE de MMFF exagera?

1776 candidatos (48 por molécula), sin un solo cálculo xTB fallido.

| superficie | ΔE mediana del elegido (kcal/mol) |
|---|---:|
| MMFF94, fase gas (la que declara el producto) | 11,5 |
| GFN2-xTB, fase gas | 9,9 |
| GFN2-xTB, ALPB agua | **8,0** |

- **Parcial.** El disolvente y el método bajan la cifra un 31 %, pero no se
  desploma: con ALPB, 27 de 37 siguen por encima de 5 kcal/mol y 12 por encima
  de 10. El conformador que más se parece al dibujo paga energía de verdad, no
  sólo en MMFF.
- Las dos superficies ordenan parecido a los candidatos: ρ de Spearman mediana
  0,72.
- Límites: puntos únicos sobre geometrías MMFF, sin reoptimizar con xTB; ALPB no
  es disolvente explícito; nada de esto es una población conformacional.
- El registro no fijaba consecuencia para «parcial»: se decide con el
  propietario.

## E3 — plegado restringido al dibujo

- 29 de 37 tienen al menos dos anillos aromáticos y se restringieron. **En 11 de
  ellas ningún embebido fue posible** (33 semillas fallidas en total): fijar los
  aromáticos en su sitio del dibujo plano pide distancias que la molécula no
  puede cumplir en 3D. Esas moléculas se cuentan como el producto.
- Se abstienen 5/37 (el producto, 8/37; hacían falta ≤ 4). ΔE mediana 13,9 frente
  a 13,1 kcal/mol con la misma referencia (sube 0,8; el límite era 2). Tiempo
  mediano 7,8 s frente a 7,2 s.
- **NO_GO** por una molécula en la abstención, y sobre todo porque falla en un
  tercio de las que debía ayudar.

## Qué queda

Ningún cambio del producto sale de aquí. Lo que el producto ya hace (`3ea0aa92`:
la pose se enseña en 3D aunque no se levante; `26df919c`: 16 candidatos) es lo
que mejor se sostiene. Abierto, para decidir con el propietario: qué hacer con el
aviso de ΔE ahora que se sabe que MMFF en fase gas exagera cerca de un tercio
pero no invierte el problema.

## E4 — ventana de energía (registro previo `4517768f`, `REGISTRO_PREVIO_E4.md`)

Datos: `e4.jsonl` (204 moléculas, ninguna sin parámetros MMFF; xTB-ALPB sólo en
G37). Veredicto con 5 kcal/mol: **NO_GO**. La abstención sube 18 en O167 (el
límite era 3) y 15 en G37 (el límite era 4).

| conjunto | regla | se abstienen | razón mediana | ΔE MMFF mediana | ΔE xTB-ALPB mediana |
|---|---|---:|---:|---:|---:|
| G37 | producto (sin ventana) | 8/37 | 0,81 | 11,5 | 8,0 |
| G37 | ventana 3 | 27/37 | 1,24 | 1,4 | 2,3 |
| G37 | **ventana 5** | **23/37** | 1,07 | 2,9 | 3,8 |
| G37 | ventana 10 | 16/37 | 0,97 | 6,3 | 5,0 |
| O167 | producto (sin ventana) | 1/167 | 0,35 | 5,8 | — |
| O167 | ventana 3 | 29/167 | 0,52 | 0,9 | — |
| O167 | **ventana 5** | **19/167** | 0,44 | 2,3 | — |
| O167 | ventana 10 | 5/167 | 0,37 | 4,5 | — |

- El intercambio es directo: cada kcal/mol que se le quita al conformador
  enseñado se paga en parecido al dibujo. Con 5 kcal/mol, 23 de las 37 grandes
  (62 %) y 19 de las 167 se abstendrían.
- La ventana MMFF sí baja la energía en la otra superficie: el ΔE xTB-ALPB del
  enseñado pasa de 8,0 a 3,8 kcal/mol en G37. No es un artefacto de MMFF.
- Ni la ventana más ancha (10) se acerca al producto en G37 (16 frente a 8).
- Dato de paso: en O167 el ΔE MMFF mediano del producto es 5,8 kcal/mol (la cifra
  de 4,9 que se citó antes era de una submuestra de 56).

Conclusión de E1–E4: para la vista «Escrita», parecerse al dibujo y ser de baja
energía son objetivos opuestos en moléculas flexibles; ninguna de las
alternativas medidas consigue las dos cosas. El producto se queda como está, con
el ΔE declarado.

## E5 — enderezar cadenas y girar colas, como MolTalk (registro previo `aa22435e`)

Datos: `e5.jsonl` (204 moléculas). Veredicto: **NO_GO**: G37 baja de 8/37 a 7/37, y hacía falta ≤ 4.

| | se abstienen | razón mediana | ΔE MMFF | ΔE xTB-ALPB | tiempo mediano | paso intentado / conservado |
|---|---:|---:|---:|---:|---:|---:|
| G37 producto → E5 | 8 → 7 /37 | 0,81 → 0,79 | 11,5 → 11,2 | 8,0 → 7,1 | 7,6 → 7,7 s | 20 / 11 |
| O167 producto → E5 | 1 → 1 /167 | 0,35 → 0,34 | 5,8 → 6,0 | — | 4,7 → 4,7 s | 62 / 45 |

Ningún centro R/S cambia. Las refinaciones son baratas y no empeoran nada,
pero apenas mueven la abstención: el desajuste de las moléculas grandes no
viene sólo de cadenas arrugadas o colas plegadas.

## E6 — animación por torsiones frente a línea recta (registro previo `74b2d17f`)

Datos: `e6.jsonl`; script `e6_animacion_por_torsiones.py`. Cuentan las moléculas
que el producto levanta: 29 de G37 y 166 de O167. Veredicto: **NO_GO**.

| | cruces A → B | deformación mediana A → B | acercamiento mínimo mediano A → B |
|---|---:|---:|---:|
| G37 (29) | 2 → 4 | 0,56 → 0,48 | 0,89 → 0,84 |
| O167 (166) | 0 → 0 | 0,41 → 0,34 | 1,24 → 1,24 |

- **El problema que debía resolver casi no existe.** Con la línea recta del
  producto, sólo 2 de las 29 grandes que se levantan tienen dos átomos que se
  cruzan a mitad de camino, y ninguna de las 166 del conjunto original. El
  registro exigía al menos 4 para que valiera la pena.
- **Las torsiones no lo mejoran:** B tiene 4 cruces en G37. Girar enlaces en 3D
  desde una forma plana hace pasar ramas cerca unas de otras.
- La deformación baja un 14 % en G37 y un 19 % en O167; hacía falta la mitad.
  Esta métrica penaliza a B por diseño: B lleva cada enlace a su longitud final
  en el primer cuarto del camino y después la conserva, que es lo físico, pero
  se mide contra una variación lineal en todo el camino. Se declara aquí y no
  cambia el veredicto.
- Barato: 0,014 s y 12,5 kB medianos en G37; los extremos coinciden exactos.

Conclusión: la interpolación lineal del visor se queda. Su deformación es una
propiedad de la transición, no de la molécula, y el giro final, que es lo que
se lee, es el conformador sin deformar.
