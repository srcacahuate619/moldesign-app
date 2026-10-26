# ABS-TR-01, validez de la decisión de Preparación — resultados

**INCONCLUSIVE** (regla del registro previo). Medido el 2026-10-22 con el producto de `be59c74a` (rama
`claude/cal-d-01-r4`, sobre `claude/auditoria-ciencia-arreglos`; el código del producto no cambia hasta el
protocolo congelado en `d6f9fb99`), 1,7 CPU-core-h.

Preparación **no autoriza nada que el panel detenga**: nunca dice «seguir» (0 de 28 sistemas), así que la falsa
autorización es 0 de 10 (límite superior 95 % 26 %). Pero **detiene 3 de los 18 sistemas que el panel no
detiene** (16,7 %; límite unilateral 95 % [4,7 %; 37,7 %]): por encima del objetivo del 10 % en la estimación
puntual, sin potencia para concluirlo. Y **deja pasar con aviso 4 de los 10 que el panel detiene**.

## Tabla final

Votos: un cuadro lleno por revisor que da NO_APTO, en el orden Astra 6, Sol 6.1, GLM 5.3, step5preview, Opus 5.5
(ronda 1). «Críticos» son los controles que algún revisor marcó CRITICO. Referencia primaria: detener con 3 o más
votos.

| R2 | PDB | Ligando | Votos | Críticos | Preparación | Motivo de Preparación (bloqueo, o revisiones no rutinarias) | ¿Coincide? |
|---|---|---|---|---|---|---|---|
| S07 | 1C3S | SHH | ■■■■■ 5/5 | C05 | **Detiene** | metal o cofactor retirado junto al ligando | sí |
| S23 | 1DIY | COH | ■■■■■ 5/5 | C05, C07 | **Detiene** | ligando con Co: Vina sin parámetros (preflight) | sí |
| S06 | 2AW1 | COX | ■■■■■ 5/5 | C05 | **Detiene** | metal o cofactor retirado junto al ligando | sí |
| S27 | 2X8Z | X8Z | ■■■■■ 5/5 | C05 | **Detiene** | metal o cofactor retirado junto al ligando | sí |
| S38 | 4WUD | ANP | ■■■■■ 5/5 | C04, C05, C06 | **Detiene** | metal o cofactor retirado junto al ligando | sí |
| S17 | 4NY4 | 2QH | ■■■■■ 5/5 | C05 | Avisa | huecos lejanos, campo de fuerzas (hemo), especie del ligando | aviso sin bloqueo |
| S29 | 6SXC | OHT | ■■■■■ 5/5 | C04, C07 | Avisa | tautómero, membrana, advertencias previas | aviso sin bloqueo |
| S18 | 8WTW | 0A1 | ■■■■■ 5/5 | C04, C07 | — | la corrida falla al preparar el receptor (Meeko), dos veces | sin auditoría |
| S33 | 4FK3 | 325 | ■■■■· 4/5 | C01 | **Detiene** | hueco del esqueleto junto al sitio | sí |
| S41 | 3G0E | B49 | ■■·■■ 4/5 | C07 | Avisa | tautómero, «covalente» (falso: ver abajo), aguas | aviso sin bloqueo |
| S10 | 6HW5 | GRT | ■■■·■ 4/5 | C07 | Avisa | ligando covalente (THR H:1), cadena vecina, estereoquímica | aviso sin bloqueo |
| S12 | 3S43 | 478 | ···■· 1/5 | C07, C08 | Avisa | altlocs, aguas, otras especies | sí |
| S20 | 4EU2 | WPI | ····■ 1/5 | C07 | Avisa | cadena vecina, especie, estereoquímica | sí |
| S01 | 1RKP | IBM | ····· 0/5 | — | **Detiene** | Zn retirado a 5,17 Å del ligando (Mg a 6,87 Å) | **falso bloqueo** |
| S11 | 6KE5 | D6C | ····· 0/5 | — | **Detiene** | Ca retirado a 4,06 Å del ligando | **falso bloqueo** |
| S08 | 4JVB | 1M0 | ····· 0/5 | — | **Detiene** | hueco ALA112→GLN116, extremos a 6,09 Å del ligando | **falso bloqueo** |
| S32 | 1HSG | MK1 | ····· 0/5 | — | Avisa | especie, aguas, advertencias previas | sí |
| S30 | 1M17 | AQ4 | ····· 0/5 | — | Avisa | huecos, altlocs, aguas | sí |
| S37 | 2HZI | JIN | ····· 0/5 | — | Avisa | cadenas truncadas, altlocs, regla de selección | sí |
| S25 | 3RUU | 37G | ····· 0/5 | — | Avisa | cadenas truncadas, protonación, regla de selección | sí |
| S02 | 4NJT | 017 | ····· 0/5 | — | Avisa | regla de selección, aguas, advertencias previas | sí |
| S21 | 5HYK | 65W | ····· 0/5 | — | Avisa | huecos, protonación | sí |
| S39 | 5WIU | AQD | ····· 0/5 | — | Avisa | cadenas truncadas, huecos, altlocs | sí |
| S26 | 5ZBH | 9AF | ····· 0/5 | — | Avisa | cadenas truncadas, regla de selección, membrana | sí |
| S15 | 6GUE | FB8 | ····· 0/5 | — | Avisa | huecos, campo de fuerzas, aguas | sí |
| S04 | 6HL1 | JN3 | ····· 0/5 | — | Avisa | huecos, protonación, altlocs | sí |
| S16 | 6PU8 | P3V | ····· 0/5 | — | Avisa | aguas, advertencias previas | sí |
| S31 | 8HFF | LNR | ····· 0/5 | — | Avisa | huecos, membrana | sí |
| S14 | 8X3K | SRO | ····· 0/5 | — | Avisa | huecos, membrana | sí |

## Endpoints

| | Referencia primaria (≥ 3 de 5) | Sólo unánimes (5/5 y 0/5) | Ronda 2 sin Opus |
|---|---|---|---|
| Sistemas auditados | 28 (10 detener, 18 no) | 23 (7 y 16; 5 disputados) | 28 (10 y 18) |
| Bloqueo correcto | 6/10 | 5/7 | 6/10 |
| Aviso sin bloqueo | 4/10 | 2/7 | 4/10 |
| **Falsa autorización** | **0/10** (≤ 25,9 %) | 0/7 (≤ 34,8 %) | 0/10 |
| **Falso bloqueo** | **3/18 = 16,7 %** [4,7; 37,7] | 3/16 [5,3; 41,7] | 3/18 |

Intervalos: unilaterales al 95 %, Clopper-Pearson. Contar o no a Opus no cambia nada: con los cuatro de la ronda 2
la referencia es la misma en los 28.

**Decisión: INCONCLUSIVE.** No hay falsa autorización en un sistema que detienen los cinco, y el límite inferior
del falso bloqueo (4,7 %) no supera el 10 %: no es NO_GO. Tampoco GO: el límite superior es 37,7 %, y con 18
negativos no podía bajar del 15,3 % ni con cero errores (dicho en el registro).

## Por qué discrepan

**Los tres falsos bloqueos son umbrales más estrictos que el criterio de los revisores, no errores de lectura.**
Preparación se abstiene si retira un metal a 6 Å o menos del ligando, y bloquea un hueco cuyos extremos quedan a
8 Å o menos. Los revisores vieron lo mismo y lo pesaron menos: C05 quedó en REVISAR para 3 de 5 en 1RKP y 4 de 5
en 6KE5 (en 6KE5 el ligando no coordina el Ca, según `docs/auditorias/metales_junto_al_sitio_2026-10-11.json`),
y C01 de 4JVB quedó INDETERMINADO para 3 y REVISAR para 2. Ninguno lo marcó CRITICO. Es la discusión «junto al
sitio» frente a «de lo que depende la unión».

**Los cuatro avisos sin bloqueo son cosas que Preparación no mira, o que mira y considera revisables:**

- **4NY4 (hemo coordinado por el ligando):** el N piridínico del inhibidor está a 2,58 Å del Fe. Preparación
  conserva el hemo (no lo retira, así que no se abstiene) y pide parámetros para él, pero no detecta que el
  ligando coordina el metal ni que Vina no lo representa. Es el hueco más claro.
- **6SXC (bolsillo completado por simetría):** el sitio necesita una copia de la cadena A generada por
  `REMARK 350`; Preparación no reconstruye el ensamblaje (la receta 8 no está integrada) y lo trata como sitio de
  una cadena.
- **6HW5 (aducto covalente con THR H:1):** Preparación lo detecta y pide revisión; los revisores lo bloquean.
  Diferencia de severidad, no de detección.
- **3G0E (sunitinib incompleto en el depósito):** Preparación no compara el ligando del cristal con su definición
  (C07 no tiene equivalente). Además declara una «ojiva: acrilamida (aceptor de Michael)» que **el sunitinib no
  tiene**: el detector toma el alqueno exocíclico del oxindol conjugado con la lactama. Es un falso positivo del
  detector de covalentes, que aquí sólo añade una revisión.

**8WTW** no tiene auditoría: el ligando del catálogo, 0A1, es según los revisores un residuo de un péptido unido
por enlaces peptídicos (SEQRES y LINK), y la corrida falla en `mk_prepare_receptor` las dos veces después de que el preflight la dejara
pasar. Los cinco revisores lo detienen. El producto se detiene también, pero fallando, no decidiendo.

## Por control (secundario)

Preparación avisa mucho más que los revisores en huecos lejanos (C01: 9 ACEPTABLE→REVISAR), cadenas truncadas
(C02: 7) e identidad del ligando (C08: 6), y menos en protonación (C09: 10 REVISAR→ACEPTABLE) y caja (C10: 5),
que sólo registra. Coinciden en aguas (C06: 10 REVISAR→REVISAR) y en altlocs del sitio (C03: 5). En metales
(C05) coinciden en los 4 bloqueos y discrepan en 4 sistemas: 2 que bloquea y los revisores revisan (1RKP, 6KE5),
uno que los revisores bloquean y Preparación acepta (4NY4) y uno sin auditoría (8WTW).

## Qué no dice

- La referencia es un panel de modelos de lenguaje, no de expertos, con dos modelos de la misma familia (Astra y
  Sol) y Opus juzgando con otra escala. Nadie adjudicó los 29 con artículos o informes de validación.
- 28 sistemas del catálogo con su ligando del cristal, por la ruta del catálogo; no dice nada de receptores
  propios (caminos A, B y C), de otros ligandos ni del resto del catálogo.
- «Avisar» es el estado de 19 de los 28: Preparación nunca dice «seguir» en estos sistemas, en parte porque
  siempre encuentra alguna revisión no rutinaria (advertencias previas, especie del ligando, regla de selección).
  Lo que eso cuesta en atención del usuario no está medido aquí.

Reproducción: `scripts/abs_tr_01/abs_tr_01.py` (congelar, ejecutar, analizar). Datos: `entrada/` (registro previo,
referencia de los revisores, CCD, sistemas, protocolo), `_work/corridas/` (respuestas crudas de la API),
`metrics.json`, `per_system.jsonl`, `failures.jsonl`, `DESVIACIONES.md`.
