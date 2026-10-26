# CAL-D-01-R4-2 — repetición de R4 con el producto de 1.0.4 (registro previo)

Firmado antes de medir, el 2026-10-24. Decisión del propietario (2026-10-24): repetir el panel con la regla de R4 sin
cambios, y declarar aparte, sin que decida, la validación física «no evaluada».

## 1. Qué se pregunta

Si, con el producto actual (`codex/release-hygiene`, `18eb7e13`, con la validación física en proceso hijo de `48b22820`),
el protocolo congelado de R4 completa los 89 padres —4-67 incluido— y si, con ellos, se cumple el criterio P1 de R4.

## 2. Qué no es

- **No es ciego.** R4 y R4B están publicados: los 88 scores sin 4-67 son conocidos (ρ = 0,39, IC 95 % 0,22–0,54), y con la
  misma semilla, el mismo receptor (`8fc027ca…`, comprobado en el piloto) y las mismas CPU se espera que se repitan. Lo nuevo
  es si el producto completa 4-67 y si con él el criterio se sigue cumpliendo.
- **No cambia la regla de R4.** Sólo se interpreta, antes de ver el score de 4-67, qué significa una etapa que R4 no
  previó: la validación física que no termina en su plazo (ver §4). El piloto (`REGISTRO_PREVIO_PILOTO.md`, SHA-256
  `d6ab34b3…`) se decidió y se firmó antes de esta interpretación, y su crudo (`piloto/crudo.json`) **no se usa ni se lee**:
  4-67 se vuelve a evaluar dentro del panel.

## 3. Qué se fija (idéntico a R4)

- Entrada: la de `scripts/artifacts_science/CAL-D-01-R4-VMAT2-8T69/entrada/`, copiada byte a byte (panel de 89 padres,
  microestados esperados, receptor preparado `8fc027cae876631f30518b27823ce175e844bbe9e7bc10554653a7766e21468d`, protocolo).
- Arnés: `scripts/cal_d01r4/cal_d01r4.py`, `rho_peor.py` y `capsula.mjs`, importados sin editar; el arnés comprueba sus
  hashes contra `protocolo.json` antes de acoplar.
- Vina 1.2.7, exhaustividad 8, 9 poses, 4 CPU por proceso; semillas 42–46 en la puerta de pose y 42 en el panel; tope
  168 CPU-core-h.
- Fases: puerta de pose (5 redockings de YHL), panel (89 padres, dos shards en paralelo) y sensibilidad (S-4-31-118).

## 4. Decisión (la de R4 §5 y §6, sin cambios)

- **Puerta de pose:** ≥ 3 de 5 semillas con RMSD ≤ 2 Å y el top-1 de cada una válido en PoseBusters (`passed`). Una
  validación «no evaluada» en el cristal **no** es válida: la puerta falla, como en R4. Si falla: NO_GO, no se acopla el panel.
- **P1:** GO sólo si el límite inferior del IC 95 % de ρ y el de ρ_peor (F = 1015/703; bootstrap pareado por padre,
  10 000 réplicas, semilla 20261021) son > 0, con la puerta superada, **cero fallos persistentes** y cero desviaciones críticas.
- **Fallo persistente** (R4): el padre se queda sin score de Vina tras el reintento idéntico (FAILURE o tiempo agotado).
- **Menos de 85 padres evaluados:** EXPLORATORIO. **Deriva** (microestado, receptor o parámetros): parada.
- **Interpretación declarada antes de medir:** una evaluación SUCCESS con `structural_evidence.stage_status =
  "not_evaluated"` tiene score y **cuenta como evaluada**; no es un fallo persistente y entra en P1. En R4, PoseBusters
  sólo decidía en la puerta de pose; contarla como fallo endurecería la regla después de ver el caso.

## 5. Lo que se declara y no decide

- **Advertencia «validación física no evaluada»:** número de padres del panel cuya evaluación SUCCESS trae
  `stage_status = "not_evaluated"` (o sin `structural_evidence`), sus identificadores y su `reason_code`. Los estados
  `passed`, `review` y `failed` son validaciones evaluadas: se cuentan y se publican, como en R4, y tampoco deciden.
- **Sensibilidad:** ρ, ρ_peor y sus IC 95 % (mismo bootstrap y semilla) **sin** los padres con esa advertencia. Se publica
  junto a P1, pase o no; no cambia la decisión.
- **Reproducibilidad frente a R4:** para los 88 padres que R4 evaluó, cuántos dan la misma energía top-1 que R4 (a 0,001
  kcal/mol) y la mayor diferencia. Una diferencia no es deriva si el microestado, el receptor y los parámetros coinciden;
  se publica.
- P2 (concordancia de pares) y las sensibilidades de 4-31/4-118, como en R4.

## 6. Qué se haría con el resultado

- **GO:** 8T69 pasa a ser candidato a «Verificados». La promoción a `receptores_verificados.json` es decisión del
  propietario y va en un commit aparte, con `supera_el_protocolo`; no la hace este experimento. R4 sigue sellado NO_GO.
- **NO_GO o EXPLORATORIO:** 8T69 sigue en Demostración, con el motivo publicado.

Un timeout o fallo técnico de la cápsula permite un reintento idéntico (R4 §6). Toda desviación se anota en
`DESVIACIONES.md` (append-only) antes de analizar.
