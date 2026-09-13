# RS-03-PARAM-B — Qué tan parecidas son las cargas NAGL a la referencia AM1-BCC

> **Lo que este experimento NO hace.** B es caracterización descriptiva. AM1-BCC
> es referencia estratificada, **no verdad absoluta**. El PRE maestro §4 prohíbe
> seleccionar NAGL mirando RMSD o Top-1, y **ninguna cifra de aquí acepta ni
> rechaza NAGL**. Quien decida sobre NAGL será RS-03-PARAM agregando A y B contra
> el contrato del PRE maestro, y el claim físico solo se juega en RS-03.

## Cobertura

**115 de 116 ligandos train (99.14%)**. El único fallo es `1nw5`: `antechamber`
aborta porque `sqm` no converge. Es un fallo **químico real y reproducible**, no
de presupuesto — ya había fallado igual con 1200 s de margen.

Los otros cuatro ligandos que aparecían como fallo en la primera fusión
(`1a4w`, `1aaq`, `1hpx`, `1jq8`) eran **artefacto de mi propia paralelización**:
terminan bien en solitario, pero los tres shards simultáneos sobre 4 cores los
empujaron por encima del timeout de pared de 1200 s. Repetidos en solitario con
2400 s pasaron los cuatro. Queda registrado porque es un fallo de diseño de la
ejecución, no del método: **el timeout medía contención, no química**.

## Los tres chequeos de integridad, antes de mirar ninguna diferencia

| Chequeo | Resultado |
|---|---|
| Mapeo biyectivo verificado (elemento a elemento **y** por coordenadas) | **115/115**, `max\|Δr\| = 0.0005 Å` |
| Conservación de carga de AM1-BCC frente a la carga formal | `max \|Σq − formal\| = 0.006 e` |
| Energía finita y sistema serializable con Sage 2.2.1 (ambos juegos de cargas) | **115/115** |

El primero importa más de lo que parece: el runner anterior comparaba cargas
**por índice, a ciegas**. Ahora, si `antechamber` alterara el orden atómico, el
ligando sale como FAIL en vez de producir una comparación silenciosamente falsa.
No alteró el orden en ninguno de los 115, y eso ahora es un hecho verificado y no
un supuesto.

## Diferencia NAGL − AM1-BCC

| Magnitud | Media | Mediana | Máximo |
|---|---:|---:|---:|
| `\|Δq\|` por átomo (e) | 0.0142 | 0.0118 | **0.4255** |
| `\|Δμ\|` dipolo (D) | 0.71 | — | 3.74 |
| `\|ΔE\|` punto único con Sage (kJ/mol) | 33.6 | 24.3 | **216.4** |

**En promedio las cargas coinciden bien** —una centésima de electrón por átomo—
**pero la cola no es despreciable**: 13 de los 115 ligandos tienen algún átomo
con más de 0.2 e de diferencia. Los extremos (`1mmr` 0.426 e, `1mmq` 0.420 e,
`1jn4` 0.414 e) son diferencias de casi medio electrón en un átomo concreto.

La consecuencia energética es la cifra que hay que mirar con más cuidado:
cambiar solo las cargas, con el mismo force field y la misma geometría, mueve la
energía de punto único una **mediana de 24 kJ/mol** y hasta **216 kJ/mol**
(`1b38`). No es ruido numérico: es del orden de magnitud de las diferencias que
un rescoring pretende resolver. Cuál de los dos juegos está más cerca de la
realidad, B **no puede decirlo**.

## Por estrato

| Eje | Estrato | n | `\|Δq\|` medio (e) |
|---|---|---:|---:|
| Azufre/fósforo | **con S/P** | 45 | **0.0168** |
| | sin S/P | 70 | 0.0125 |
| Halógenos | con halógenos | 18 | 0.0098 |
| | sin halógenos | 97 | 0.0150 |
| Ionización | ionizados | 29 | 0.0124 |
| | neutros | 86 | 0.0148 |
| Peso molecular | >500 | 19 | **0.0177** |
| | 300–500 | 55 | 0.0137 |
| | <300 | 41 | 0.0132 |
| Rotables | >10 | 37 | 0.0157 |
| | 5–10 | 41 | 0.0155 |
| | <5 | 37 | 0.0113 |
| Semejanza a fármaco | drug-like | 80 | 0.0155 |
| | fuera de dominio | 4 | 0.0152 |
| | fragmentos | 31 | 0.0107 |

Tres lecturas, todas descriptivas:

1. **El azufre y el fósforo son donde más divergen** (0.0168 vs 0.0125 e), y ahí
   está también el máximo global (`1mmr`, 0.426 e). Es el estrato a vigilar.
2. **El tamaño y la flexibilidad aumentan la divergencia** de forma monótona:
   fragmentos 0.0107 → drug-like 0.0155; <5 rotables 0.0113 → >10 rotables 0.0157.
3. **Los ionizados y los halogenados divergen menos que sus complementarios**, lo
   contrario de lo que sugeriría la intuición de que los casos cargados son los
   difíciles. No se ofrece explicación mecanística: es una observación, y con
   n=18 halogenados la incertidumbre es amplia.

## Qué queda pendiente

RS-03-PARAM (agregación A + B) es quien confronta esto con el contrato del PRE
maestro. B entrega: cobertura 99.14%, integridad verificada en los tres
chequeos, y un mapa de dónde difieren los dos métodos de carga. **No entrega un
veredicto sobre NAGL, y cualquier lectura que lo extraiga de aquí está violando
el prerregistro.**

## Archivos

- `DESIGN.md` — método, incidencia de sobrescritura y cobertura punto por punto del prerregistro.
- `metrics.json` — agregados, estratos, procedencia de los 4 shards y notas de gobernanza.
- `per_complex.jsonl` (115) — por ligando: cargas AM1-BCC, `\|Δq\|` medio y máximo, cargas moleculares, dipolos de ambos métodos, energías de ambos métodos, verificación de orden atómico y estratos.
- `failures.jsonl` (1) — `1nw5`, con el mensaje de `sqm`.
- `RS-03-PARAM-B-S1..S4` — artefactos crudos por shard, sin fusionar.
