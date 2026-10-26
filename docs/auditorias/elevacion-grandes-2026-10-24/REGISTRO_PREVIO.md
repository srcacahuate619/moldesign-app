# Ligandos grandes en la elevación 2D → 3D: registro previo (2026-10-24)

Escrito y commiteado **antes** de ejecutar ninguno de los tres experimentos.
Los resultados irán en `RESULTADOS.md`; si algo se desvía de lo escrito aquí,
se dirá allí, junto al motivo.

## Punto de partida (medido, `26df919c`)

En 37 moléculas de 35 a 51 átomos pesados (`../elevacion-abstencion-2026-10-24/grandes.jsonl`,
de artefactos versionados de `scripts/artifacts_science`), con el producto
tal como queda (16 candidatos por semilla, 3 semillas):

- se abstienen **8/37** (razón > 1 enlace);
- el conformador elegido queda una mediana de **11,5 kcal/mol** (MMFF94, fase gas)
  por encima del más bajo encontrado.

Son dos problemas distintos: (1) el dibujo plano y extendido no se parece a
ningún 3D de una molécula grande y flexible, y (2) elegir por parecido al
dibujo puede escoger geometrías de energía alta, o puede que la cifra de MMFF en
fase gas exagere. Ningún experimento añade dependencias: RDKit 2025.09.6 y xTB
6.7.1 ya viajan en el producto.

## Conjuntos

- **G37**: las 37 grandes.
- **O167**: las 167 del conjunto original (`../elevacion-abstencion-2026-10-24/moleculas.jsonl`),
  sólo en E1, como control de que no se estropea lo que ya funciona.

## E1 — un dibujo que se ajusta al 3D

`rdDepictor.GenerateDepictionMatching3DStructure` genera coordenadas 2D que
reproducen las distancias de una geometría 3D. Se compara con el dibujo actual
(`dibujo_2d`, `rdDepictor.Compute2DCoords`).

Geometría de entrada, dos casos:

- **proxy de pose**: el primer conformador ETKDGv3 + MMFF94 de la semilla 1, sin
  elegir por parecido al dibujo (una pose de Vina tampoco se elige así). Es el
  caso de Moldex. Es un proxy: no son poses reales.
- **elegido**: el conformador que el producto enseña en «Escrita». Es el caso del
  editor cuando no hay dibujo de Ketcher o el visor se abstiene.

Métricas, sobre los átomos pesados, con L = longitud media de enlace del dibujo:

- razón de ajuste: RMS del ajuste de `_ajuste` (los mismos pesos) / L;
- **solapamientos**: pares de átomos no enlazados a menos de 0,4·L;
- **cruces**: pares de enlaces sin átomo común cuyos segmentos se cortan;
- un dibujo es **legible** si no tiene ni solapamientos ni cruces.

Decisión:

- **GO como respaldo** (sólo cuando el dibujo normal se abstiene): en G37 con el
  proxy de pose, al menos el 75 % de las que se abstienen con el dibujo normal
  pasan a ≤ 1 enlace con el dibujo ajustado, **y** al menos el 75 % de esos
  dibujos ajustados son legibles.
- **GO como dibujo por defecto**: además, en G37 ∪ O167 con el proxy de pose, la
  fracción de dibujos ajustados legibles es al menos 0,9 veces la de los dibujos
  normales, y no se abstienen más moléculas que con el normal.
- Si no, **NO_GO**.

Se guarda una lámina SVG con 12 moléculas de G37 (dibujo normal frente a
ajustado) para la revisión visual del propietario: las métricas no miden la
estética.

## E2 — ¿la cifra de ΔE de MMFF exagera?

Para cada molécula de G37 se rehacen los candidatos del producto (mismas
semillas, mismos parámetros, 16 por semilla) y a cada candidato se le calcula,
sobre su geometría MMFF94 (sin reoptimizar):

- E(MMFF94), la que ya da el producto;
- E(GFN2-xTB, ALPB agua), como la calcula `services/xtb/service.py`;
- E(GFN2-xTB, fase gas), para separar el método del disolvente.

ΔE del elegido = su energía menos la del candidato más bajo del mismo conjunto,
en cada superficie.

Decisión, con la mediana de G37:

- **MMFF exagera** si ΔE(xTB-ALPB) ≤ 0,5 · ΔE(MMFF);
- **se sostiene** si ΔE(xTB-ALPB) ≥ 0,8 · ΔE(MMFF);
- **parcial** entre medias.

Secundario: correlación de Spearman entre las energías relativas MMFF y
xTB-ALPB de los candidatos, molécula a molécula (mediana de las ρ).

Límites que ya se saben: son puntos únicos sobre geometrías MMFF, no
optimizaciones xTB; ALPB no es un disolvente explícito; ninguna de las tres
energías es una población conformacional.

Consecuencia prevista: si MMFF exagera, el texto y el umbral del aviso de ΔE del
visor se revisan con el propietario; si se sostiene, el siguiente paso es medir
una ventana de energía. Calcular xTB en el visor no entra en este registro.

## E3 — plegado restringido al dibujo

ETKDGv3 con `coordMap`: los átomos aromáticos se fijan en su posición del dibujo
normal, escalado para que el enlace aromático medio mida 1,40 Å. Mismas semillas
(1, 2, 3), 16 candidatos, la misma optimización MMFF94 sin restricciones después
y la misma elección por parecido al dibujo. Las moléculas con menos de dos
anillos aromáticos no cambian y se cuentan aparte. Un embebido que falla se
cuenta.

Métricas en G37: abstención (mediana de semillas, como el producto), ΔE MMFF del
elegido sobre el más bajo del conjunto **unido** (producto ∪ E3, la misma
referencia para los dos) y tiempo.

Decisión: **GO** si se abstienen ≤ 4/37, la mediana de ΔE no sube más de
2 kcal/mol respecto del producto con esa misma referencia, y el tiempo mediano no
pasa de 1,5 veces el del producto. Si no, **NO_GO**.

## Lo que ningún resultado de aquí decide solo

Cambiar el producto. Un GO dice que vale la pena proponer el cambio; el cambio
se decide con el propietario y lleva sus propias pruebas.
