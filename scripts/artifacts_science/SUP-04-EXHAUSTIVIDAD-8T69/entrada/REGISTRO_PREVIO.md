# SUP-04-EXHAUSTIVIDAD-8T69 — registro previo (2026-10-25)

Escrito y commiteado **antes** de acoplar ninguna molécula con exhaustividad distinta de 8. Sale del inventario SUPUESTOS-01
(semilla S33–S35; bloque 2 de la fase 2, aprobado por el propietario el 2026-10-25).

## La pregunta

Todas las corridas del producto, y el sello de 8T69 en Verificados, usan exhaustividad 8. El código lo justifica con
«8 = sweet spot, > 16 no mejora ranking» (`backend/core/config.py`) y el índice con «Vina exhaust=8: sweet spot validado»
(`docs/00_INDEX.md`). No hay un experimento sellado que lo mida. La pregunta es si, en la serie donde hay datos (89 padres
de VMAT2 con Ki publicados), subir la exhaustividad a 16 o 32 cambia lo que el producto afirma: la ordenación (ρ) y la
reproducción de la pose del cristal.

## Datos y protocolo (los de CAL-D-01-R4-2, salvo la exhaustividad)

- Entrada copiada byte a byte de `scripts/artifacts_science/CAL-D-01-R4-2-VMAT2-8T69/entrada/`: panel de 89 padres,
  microestados esperados, receptor preparado `8fc027ca…`, protocolo.
- Arnés: `scripts/cal_d01r4/cal_d01r4.py` y `rho_peor.py` importados sin editar; el arnés de este experimento
  (`scripts/sup04_exhaustividad/medir.py`) sólo cambia la exhaustividad pedida, la comprobación de deriva que la acompaña y
  dónde escribe.
- Vina 1.2.7, 9 poses, 4 CPU por proceso, la configuración por defecto de un caso en lo demás.
- Brazos:

| Brazo | Exhaustividad | Semilla del panel | Redocking de YHL (semillas 42–46) |
|---|---:|---:|---|
| `e8` | 8 | 42 | sí |
| `e8s43` | 8 | 43 | no |
| `e16` | 16 | 42 | sí |
| `e32` | 32 | 42 | sí |

`e8` repite R4-2 con el producto de hoy; `e8s43` mide cuánto cambia ρ sólo por la semilla, que es el ruido contra el que se
lee cualquier diferencia. Deriva (microestado, receptor, semilla, exhaustividad efectiva, Vina o CPU distintos de lo pedido)
detiene el brazo. Un fallo técnico permite un reintento idéntico (R4 §6). Tope: 168 CPU-core-h por brazo.

## Medidas

- **Primaria:** Δρ = ρ(`e32`) − ρ(`e8`), con ρ de Spearman entre −E top-1 y pKi sobre los padres evaluados en los dos brazos;
  IC 95 % por bootstrap pareado por padre (10 000 réplicas, semilla 20261025, percentiles 2,5 y 97,5).
- Declaradas, sin decidir: Δρ(`e16` − `e8`) y Δρ(`e8s43` − `e8`) con el mismo bootstrap; ρ y ρ_peor (F = 1015/703, `rho_peor.py`)
  de cada brazo; por padre, la diferencia de energía top-1 (cuántos bajan más de 0,1 y de 0,5 kcal/mol al pasar de 8 a 32: la
  búsqueda a 8 no había convergido); ρ de Spearman entre las energías de `e8` y `e32`; RMSD del redocking por semilla y brazo
  y cuántas semillas quedan a ≤ 2 Å; CPU-core-h por brazo.
- `e8` frente a R4-2: cuántos padres repiten la energía top-1 a 0,001 kcal/mol (se espera que todos).

## Regla de decisión

- **NO_GO** (la exhaustividad 8 se queda corta en esta serie): el IC 95 % de Δρ excluye el cero por encima, **o** el redocking
  de `e8` deja menos semillas a ≤ 2 Å que el de `e32`.
- **GO** (8 basta en esta serie): no es NO_GO y el IC 95 % de Δρ cae entero dentro de [−0,10; +0,10]. El margen de 0,10 es
  un tercio de la anchura del IC 95 % de ρ que publica el sello de 8T69 (0,22–0,54): una diferencia menor no cambia ninguna
  afirmación del producto.
- **INCONCLUSIVE** en cualquier otro caso (por ejemplo, un IC que cruza el cero pero sale del margen).
- Menos de 85 padres comunes a `e8` y `e32`: EXPLORATORIO.

Consecuencia que se propondrá al propietario (no la decide este experimento): con GO, sustituir «sweet spot validado» por la
medida y su condición (un receptor, una serie); con NO_GO, proponer subir el valor por defecto y repetir el sello de 8T69 con él.

## Lo que no es ciego

La ρ a exhaustividad 8 y semilla 42 es pública (R4-2: 0,392). Las de 16, 32 y la semilla 43 no se han calculado ni mirado.

## Límites declarados de antemano

- Un receptor, una serie congenérica y una caja de 30 Å de lado. Un GO no dice que 8 baste en otro receptor, en una caja
  mayor (de más de 27 000 Å³ el producto ya sube a 32) ni con ligandos más flexibles.
- Una semilla por brazo en el panel: `e8s43` da una sola medida del ruido de semilla, no su distribución.
- No mide el tiempo que el usuario espera, sólo las CPU-core-h.
