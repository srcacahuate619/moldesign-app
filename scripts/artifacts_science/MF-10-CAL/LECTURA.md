# MF-10-CAL — El instrumento tenía resolución, y el minimizador estaba convergido

## Decisión: GO — los tres gates pasan

| Gate | Criterio | Resultado |
|---|---|---|
| C1 suelo | reportar la deriva del cristal minimizado | **0.401 Å** mediana |
| C2 suelo informativo | deriva mediana < 1.0 Å | **PASS** |
| C3 convergencia | mejora ≤ 0.1 Å al subir de 500 a 10,000 iteraciones | **PASS — 0.061 Å** |

43.9 min en el contenedor `moldesign-lab`, reutilizando el mismo constructor de
sistema que `MF-10` para que toda diferencia venga del protocolo de minimización y no
de la preparación.

## Por qué existió este experimento

La auditoría de `MF-10` encontró dos controles ausentes que limitaban la
interpretación de su NO_GO sin invalidarlo. Este experimento los añadió **antes** de
sellar, en vez de sellar una conclusión no del todo ganada.

## Brazo A — el suelo del instrumento

Minimizar la **pose cristalográfica** con el protocolo idéntico de `MF-10`:

| | Valor |
|---|---:|
| Deriva mediana | **0.401 Å** |
| p90 / máximo | 0.787 / 1.939 Å |
| Complejos válidos | 39 de 48 |
| Fuerza RMS residual del ligando | 3.20 kcal/mol/Å |

El campo de fuerza en vacío con la proteína restringida **sí** desplaza el cristal, y
lo hace 4× más que lo que movió a las poses dockeadas de `MF-10` (mediana 0.099 Å).
Pero 0.401 Å está **muy por debajo** del ~1 Å que `MF-10` habría necesitado convertir:
el instrumento tenía resolución de sobra para detectar una conversión si hubiera
existido. **El NO_GO de `MF-10` es un negativo real, no ceguera del aparato.**

Los 9 complejos que fallan son exactamente los mismos que en `MF-10`, con el mismo
error de plantilla: confirma que la causa es la preparación del receptor y no la pose.

## Brazo B — la convergencia

24 poses de la banda 2–3 Å elegidas **por score**, con barrido de presupuesto:

| Iteraciones | Δ mediano | Cruzan 2.0 Å | Fuerza RMS |
|---:|---:|---:|---:|
| 500 | −0.050 | 3 | 4.67 |
| 2,000 | −0.095 | 4 | 4.80 |
| 10,000 | −0.111 | 4 | 4.95 |

Multiplicar el presupuesto por **20** mejora el Δ mediano **0.061 Å** y convierte una
pose más. Está por debajo del umbral preregistrado de 0.1 Å, así que **C3 pasa**: el
`G3` de `MF-10` es una medición del campo de fuerza, no un artefacto de presupuesto
agotado.

**Matiz que no hay que perder**: el efecto no es cero. Con 5–7 poses parecía nulo y
con las 21 válidas se ve pequeño pero real. La lectura correcta es «el presupuesto
influye poco», no «no influye». Y aun exprimiendo el minimizador 20×, el Δ llega a
−0.111 Å frente al ~1 Å necesario: **un orden de magnitud corto**.

## Lo que este experimento NO dice

- **No rehabilita `MF-10`**: los dos gates que fallaban (G2 validez, G3 mejora) siguen
  fallando por sus propias causas.
- **No mide el desplazamiento del mínimo en solvente.** Todo es en vacío, como
  `MF-10`. La deriva de 0.401 Å incluye el efecto de esa elección y no lo separa.
- **No toca val, test ni `D-RC-CONFIRM`.**

## Archivos

- `PREREGISTRO.md` (en `MF-10-CAL-PRE`, escrito antes de ejecutar).
- `metrics.json` — gates, deriva por percentiles, barrido por iteraciones.
- `brazo_a.jsonl` (48) — deriva, energías y fuerza residual por complejo.
- `brazo_b.jsonl` (24) — barrido de `maxIterations` por pose.
- `scripts/run_mf10cal_control.py`.
