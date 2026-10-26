# ABS-TR-01-VALIDEZ-R1 — registro previo

Firmado antes de evaluar ningún sistema, el 2026-10-24. Decisión del propietario: repetir ABS-TR-01-VALIDEZ con la regla
de metales en dos niveles (`14fd5e4d`) y los arreglos de 1.0.4.

## Qué cambia y qué no

- **No cambia la referencia.** Los revisores LLM juzgaron los 29 depósitos, no la salida del producto; su decisión está
  congelada en `entrada/referencia_revisores.json` de ABS-TR-01-VALIDEZ y se copia byte a byte (mismo SHA-256). No se relanza
  el panel.
- **No cambian** los sistemas (`sistemas.json`), los CCD, los microestados esperados, la configuración de un caso (Vina 1.2.7,
  exhaustividad 8, 9 poses, semilla 42, 4 CPU), los dos intentos por sistema ni el tope de 30 CPU-core-h.
- **Cambia el producto:** `codex/release-hygiene` en el commit que congela este registro (metales desde el ligando del
  cristal y en dos niveles, aviso de Cys–metal, cabeceras del depósito, receptor del rescoring).
- El arnés `scripts/abs_tr_01/abs_tr_01.py` (activo sellado) se importa sin editarlo; sólo cambia dónde escribe
  (`scripts/abs_tr_01_r1/`).

## Hipótesis y regla de decisión (las de ABS-TR-01-VALIDEZ, sin cambios)

La decisión de Preparación (detenerse, avisar, seguir) coincide con la del panel. NO_GO si hay una falsa autorización en un
sistema que detienen los cinco revisores o si el límite inferior 95 % del falso bloqueo supera el 10 %; GO si el límite
superior es ≤ 10 % y no hay ninguna falsa autorización; si no, INCONCLUSIVE.

## Lo que ya se sabe y hay que decir

**No es una medida ciega.** MET-02-R1 ya predijo los cambios de esta regla en 1RKP y 6KE5 (dejan de abstenerse) y 4NY4 (pide
revisión). Con 18 negativos el límite superior unilateral no baja del 15,3 % ni con cero errores, así que **GO es inalcanzable
por diseño** y el resultado esperable es INCONCLUSIVE o NO_GO. Lo que mide de verdad es la tabla: cuántos falsos bloqueos y
falsas autorizaciones quedan con la regla nueva, y si alguno aparece donde no se predijo. Se informa así.

8WTW sigue sin prepararse (Meeko); si se prepara, se anota en DESVIACIONES y cuenta.
