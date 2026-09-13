# MF-10 — El campo de fuerza no cierra la brecha: 0 complejos convertidos

## Decisión: NO_GO

| Gate | Criterio | Resultado |
|---|---|---|
| G1 capacidad | el stack parametriza con Sage 2.2.1 | PASS (declarado en el prerregistro) |
| G2 **validez** | ≥95% de poses con energía finita | **FAIL — 81.3%** (714 de 878) |
| G3 **mejora** | mediana de Δ RMSD negativa | **FAIL — +0.007 Å** |
| G4 conversión | ≥5 poses de la banda 2–3 Å cruzan | PASS — 9 de 64 |

7 h 14 min en el contenedor `moldesign-lab`. 48 complejos, 878 poses top-20 por score.

## El número que ninguna objeción toca

**Cero complejos convertidos.** Las 9 poses que cruzan 2.0 Å pertenecen a 7 complejos
que **ya tenían** una pose por debajo del umbral antes de relajar, y **8 de las 9 son
del estrato CONTROL**. Ningún complejo que fallaba pasó a acertar.

G4 pasó tal como se preregistró —cuenta poses— y así queda. Pero la conversión a
nivel de **pose** no se tradujo en una sola conversión a nivel de **complejo**, que es
la unidad que decide en toda la línea `MF-08`/`MF-02F`/`MF-09`.

## La magnitud cierra el argumento

| | Valor |
|---|---:|
| Δ RMSD mediano | **+0.007 Å** (337 mejoran, 374 empeoran) |
| Δ en la banda 2–3 Å | −0.069 Å |
| Movimiento máximo en 714 poses | **0.725 Å** |
| Poses que se mueven > 0.5 Å | 11 de 714 |
| Mejor RMSD por complejo (mediana) | 2.496 → 2.391 Å |

La minimización hace exactamente lo que hace una minimización local: mueve décimas de
ángstrom. Las poses necesitan bajar ~1 Å. La predicción declarada cuadró sin residuo:
**67 poses en la banda 2–3 Å**, 3 perdidas por fallo de parametrización, **64 medidas**.

## El fallo de G2 es de preparación, no del campo de fuerza

Los 164 errores no están repartidos: son **9 complejos que fallaron 20/20 poses** con
el mismo error de plantilla de OpenMM (`residue match NVAL/NILE/NTHR, but the set of
externally bonded atoms has 1 N atom too many`). Son `1b38`, `1c4u`, `1d3p`, `1d9i`,
`1dgm`, `1mu8`, `1nm6`, `1nw5` (COLOCACION) y `1flr` (CONTROL).

Causa: el protocolo vacía `missingResidues` a propósito para no reconstruir loops, y
los cortes de cadena quedan como términos que amber14 no reconoce. La cohorte efectiva
del estrato objetivo baja de **33 a 25**.

**Y no sesga hacia el NO_GO**: los 8 complejos COLOCACION perdidos tenían un mejor
RMSD mediano de **4.450 Å** frente a **4.024 Å** de los retenidos — estaban *más lejos*
de convertir. Excluirlos favorecía ligeramente al GO.

## Auditoría previa al sello

Antes de sellar se auditó el experimento de punta a punta (`AUDITORIA.md`). Seis
riesgos quedaron descartados —en particular que `rmsd_antes` y `rmsd_despues`
compartan función, verificado con discrepancia máxima de **0.0005 Å**, que es el
redondeo del fichero— y se encontraron dos defectos y dos controles ausentes.

Los dos controles ausentes se ejecutaron como `MF-10-CAL` y **ninguno invalida este
resultado**:

- **Suelo del instrumento**: el cristal minimizado bajo el mismo protocolo se desplaza
  **0.401 Å** (mediana). Muy por debajo del ~1 Å necesario, así que el instrumento
  tenía resolución de sobra: este NO_GO es un negativo real, no ceguera del aparato.
- **Convergencia**: subir de 500 a 10,000 iteraciones mejora el Δ mediano sólo
  **0.061 Å**, por debajo del umbral preregistrado de 0.1 Å. `MF-10` midió con el
  minimizador esencialmente convergido.

Defectos declarados que quedan como limitación: el fallo de plantilla de §G2 y un
hidrógeno explícito retenido en 7 complejos que conserva su coordenada cristalográfica
mientras los pesados se mueven a la pose. Este segundo es un defecto latente de
impacto acotado: los 6 complejos afectados que corrieron se comportan como el resto.

## Consecuencia para el programa

La micro-relajación in situ era la **última palanca sin probar** de la hipótesis
original del maintainer. El multi-modo ya estaba saturado, la flexibilidad de receptor
apuntaba a fallo conformacional, la caja (`MF-08`) y los reinicios (`MF-02F`)
convirtieron 3 de 33 cada uno, y el campo de fuerza bien parametrizado convierte **0**.

Coincide con `MF-09`: en 30 de 33 complejos difíciles no existe pose ≤2 Å que
refinar. No se puede acercar al cristal una pose que está a 7 Å con una minimización
que mueve 0.1.

**No se lee como cambio del protocolo de producción**: `molflex.py` seguiría
necesitando el stack de Python 3.11 que la máquina local no tiene.

## Archivos

- `PREREGISTRO.md` (en `MF-10-PRE`, sellado antes de ejecutar).
- `AUDITORIA.md` — la auditoría metodológica completa previa al sello.
- `metrics.json` — gates, deltas, banda 2–3 Å, energías y errores.
- `per_complex.jsonl` (48) — por complejo y pose: RMSD antes/después, delta, energías.
- `sondeo.json` — el gate G1 de capacidad.
- `scripts/run_mf10_relax_insitu.py`.
