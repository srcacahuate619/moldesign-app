# MF-29-EMP-EXT — Los dos que expiraron se recuperan, y el caso de borde no se materializa

## Diagnóstico: `OBJETIVO` — decisión `GO`

`MF-29-EMP` se leyó sobre **48** de 50. `1mmr` y `1nm6` figuraban en su `failures.jsonl`
con plazos vencidos —43200.4 y 43200.6 s, tres veces el `timeout=14400` en duro—. Esta
extensión los recupera con el plazo convertido en parámetro, **72000 s**, que era el único
cambio de protocolo declarado.

| Instrumento | Criterio preregistrado | Resultado | Estado |
|---|---|---|---|
| **Cantidad primaria** | fracción con `min(exh=512) < min(exh=8) − 0.10` sobre la unión; ≥0.30 BÚSQUEDA, <0.10 OBJETIVO, intermedio MIXTO | **4/50 = 0.08** | **Válido → OBJETIVO** |
| **Caso de borde declarado antes** | si mejoran los DOS: 5/50 = 0.1000 → MIXTO, y cambiaría `MF-29-EMP` | mejora **uno** → 4/50 = 0.0800 | **No se materializó** |

## Lo que queda establecido

**Los dos complejos no fallaron: expiraron.** Con plazo suficiente completan sus tres
semillas, y la cohorte queda en **50 de 50**.

| Complejo | Estrato | TORSDOF | Producción | Masivo (`exh`=512) | Ganancia | ¿Mejora? |
|---|---|---:|---:|---:|---:|---|
| `1mmr` | `RESTO` | 6 | −6.608 | **−6.770** | **+0.162** | **Sí** |
| `1nm6` | `COLOCACION` | 2 | −8.724 | −8.713 | −0.011 | No |

Las seis corridas cayeron entre **33546.6 s** (`1mmr` s42) y **51275.8 s** (`1nm6` s7):
**todas** por encima del plazo antiguo de 14400 s. El `timeout` en duro era el problema, no
la química — la trampa ya registrada de esta máquina. Coste total 132221 s (36.7 h) para
mover un complejo 0.162 kcal/mol.

La `sd` entre semillas es **0.094** en `1mmr` y **0.040** en `1nm6`, consistente con el
brazo masivo saturado que `MF-29-EMP` ya había medido.

## Por qué existía este prerregistro

Recuperar dos complejos de una cohorte de 50 parece trivial. No lo era:

| Desenlace | Unión | Lectura |
|---|---:|---|
| No mejora ninguno | 3/50 = 0.0600 | `OBJETIVO` |
| **Mejora uno** ← ocurrió | **4/50 = 0.0800** | **`OBJETIVO`** |
| Mejoran los dos | 5/50 = **0.1000** | `MIXTO` — **habría cambiado `MF-29-EMP`** |

La regla dice **< 0.10** para `OBJETIVO`, y 0.1000 no es menor que 0.10. Escribir los tres
desenlaces antes de mirar es lo único que impedía discutir el umbral después. `1nm6` se
quedó a −0.011, o sea que ni se acercó al listón de 0.10 que habría hecho falta.

## Lo que NO queda establecido

- **`MF-29-EMP` no se re-sella.** Queda leído sobre 48 con su limitación declarada; esto es
  una extensión con registro propio, como `REC-08-EXT` o `FEP-02-EXT`.
- **El brazo de producción no se recomputó**, tal como se declaró: se reusaron los valores
  ya medidos.
- **`MF-29` —el certificado— sigue `ABIERTO`.** La jerarquía de Lasserre se declaró NO
  IMPLEMENTABLE en este hardware antes de correr, y una cota empírica no certifica
  optimalidad global.
- **Los tiempos son orientativos**: el servidor puede estar compartido. La cantidad
  primaria es el score, no el reloj.

## Procedencia

| Artefacto | Qué aporta |
|---|---|
| `MF-29-EMP-EXT-PRE` | Prerregistro sellado el 2026-08-20 con el hash del runner y el caso de borde escrito antes |
| `MF-29-EMP` | Los 48 leídos, el brazo de producción reusado y el `failures.jsonl` que documenta los dos plazos vencidos |

Ejecutado en el contenedor del servidor. Artefactos descargados con SHA-256 verificado
contra el remoto; el hash de `scripts/run_mf29empext_recuperar_expirados.py` coincide con
el sellado en `MF-29-EMP-EXT-PRE` tanto en local como en el servidor.
