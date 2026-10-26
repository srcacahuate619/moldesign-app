---
titulo: "Reproduce al tercer decimal con 4.6 veces más poses"
entradilla: "0.1858 aquí contra 0.186 antes. La ausencia de embudo no era un artefacto de muestreo escaso, y corregir la simetría no la mueve ni un decimal."
---

Un resultado incómodo merece que se intente tirarlo abajo antes de construir encima. La
medición anterior había encontrado que en el estrato difícil no hay embudo —correlación
0.186 entre distancia al cristal y puntuación— y de esa medición dependían decisiones
importantes, entre ellas descartar familias enteras de métodos de optimización, algo que excedía lo
medido (SCI-B-089).

Había dos formas plausibles de que esa cifra fuera un artefacto:

1. **Muestreo escaso.** Con pocas poses por complejo, un Spearman bajo puede ser ruido.
2. **La métrica de simetría.** Un anillo rotado 180° es la misma molécula; si el RMSD no lo
   trata bien, las etiquetas están sucias y cualquier correlación se degrada.

Este experimento prueba las dos.

## Verificación primero

Antes de nada, reproducir lo anterior sobre el material nuevo: **0.1858** frente a
**0.186**. Coincide al tercer decimal.

Eso verifica que la lectura del material es correcta, y es la clase de comprobación que
distingue una extensión de un experimento nuevo con el mismo nombre.

## Qué pasó con las dos explicaciones

**Muestreo escaso: descartada.** Con **751 poses por complejo** —4.6 veces más que antes—
la cifra no se mueve:

| Estrato | ρ |
|---|---:|
| Colocación | **0.186** |
| Control | **0.507** |

Y por radios, dentro del estrato difícil:

| Radio | ρ |
|---|---:|
| ≤ 4 Å | 0.279 |
| ≤ 6 Å | 0.140 |

Ni siquiera acercándose mejora de forma útil.

**Simetría: descartada.** Corregir la métrica de simetría deja el valor en **0.1858 con
ambas métricas**. Idéntico. El embudo —o su ausencia— es invariante a esa elección.

Esa segunda comprobación importa más de lo que parece, porque en otro experimento del
programa la corrección de simetría **sí** cambió las cosas: reveló un 21% de etiquetas
positivas mal marcadas y duplicó la brecha entre un selector y su baseline. Que aquí no
cambie nada no era predecible, y por eso había que medirlo.

## Lo que sigue sin poder medirse

A radios de 2 Å o menos **siguen sin existir complejos medibles** en el estrato difícil,
incluso con 751 poses.

La razón no es estadística sino física: en 30 de 33 complejos **no hay ninguna pose ahí**.
No se puede calcular una correlación en una región del espacio que el generador nunca
visitó, por muchas poses que se generen fuera de ella.

## Por qué este registro existe

Porque el resultado que verifica es de los que cierran puertas. Descartar familias de
métodos basándose en una correlación medida sobre 163 poses por complejo habría sido
imprudente; hacerlo sobre 751, con la métrica de simetría comprobada por ambos caminos, es
otra cosa.

Un negativo que sostiene decisiones grandes necesita que alguien haya intentado tumbarlo.

## Correcciones

**2026-10-22**, a raíz de la Fase B de la auditoría científica (fase 1b del plan de arreglos,
`docs/102_FASE_1B_CORRECCIONES.md`). Ninguna cifra cambia.

- SCI-B-092. Las 4,6 veces más poses no resuelven el embudo a radios cortos ni demuestran su
  ausencia: el total de poses no es cobertura local. En el estrato difícil, a 2 Å o menos
  sigue sin haber ningún complejo medible (0 de 33), a 3 Å hay 2, y las cifras por radio
  de la tabla tienen detrás 11 complejos (0.279 a 4 Å) y 27 (0.140 a 6 Å); sólo 2 son
  medibles en todos los radios con medida. Lo que la extensión sí descarta es que la ρ
  global del estrato fuera un artefacto de muestreo escaso o de la simetría. La lectura
  «no hay embudo» se limita a los radios y complejos con muestra; a 2 Å o menos no es
  estimable con este material. Productor de la cobertura:
  `scripts/analisis_mf15_cobertura_por_radio.py`.
- Por SCI-B-089 (paper de MF-15): «descartar familias enteras de métodos de optimización»
  excede lo medido; la correlación entre poses fijas no mide navegabilidad.
- SCI-B-093. Reproducir el Spearman global de `MF-09` con el mismo material (MF-02D + MF-02F)
  es una comprobación de consistencia de la lectura, no una réplica independiente.
- SCI-B-094. La corrección por simetría enumera como mucho 5000 automorfismos. Contados para
  los 52 ligandos de la cohorte de `MF-02F`, el máximo es **144** (1eld): el tope no recortó
  ninguno. Productor: `scripts/analisis_mf15ext_tope_automorfismos.py`.
- SCI-B-095. El sello fija el analizador, no el material ni `metrics.json`.
- SCI-B-144. «Reveló un 21 % de etiquetas» es el aumento de positivas de train sobre las
  originales (75 de 357). La fracción de positivas corregidas que antes eran negativas es 75 de
  432, el 17.4 %. Productor: `scripts/analisis_fase1b_falsas.py`.

**2026-10-22.** La introducción presentaba como decisión el descarte de familias enteras de métodos, que SCI-B-089 había limitado (hallazgo L2-SOL-008 de la revisión de papers de Sol).

## MF-17: el contraste por desenlace está confundido con el estrato

**GO de cruce descriptivo.** Añade la composición de los grupos del diagnóstico; no valida el embudo como predictor independiente.

Se cruzaron MF-09, MF-13, MF-14 y MF-15-EXT, con desenlace de disponer de alguna pose dentro del corte de bolsillo. RESUELTO y FALLA son etiquetas del oráculo, no juicios sobre afinidad.

| Grupo archivado | COLOCACION | CONTROL | Mediana de ρ del embudo |
|---|---:|---:|---:|
| RESUELTO | 3 | 15 | 0,4796 |
| FALLA | 30 | 0 | 0,2105 |

La separación casi reproduce el estrato definido por desenlace. No permite aislar el efecto del embudo, diagnosticar una causa ni declarar ausentes otros mecanismos por falta de contraste. **SCI-B-101** sólo se sostiene parcialmente: la revisión posterior hace coincidir los r50 usados con MF-14 sellado, pero el runner dependía de una ruta scratch sin hash de entrada. Esa coincidencia no sanea la procedencia original. No comprobado por mí: reconstruir aquel scratch o recalcular embudos. Fuentes: `MF-17` y `docs/102_FASE_1B_CORRECCIONES.md`.
