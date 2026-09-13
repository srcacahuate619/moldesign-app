# RS-14-R1-PRE — Prerregistro: RS-14 con las etiquetas de simetría corregidas

**Fecha:** 2026-08-18
**Rama:** `experimentos/ruta-c-molflex`
**Estado:** PREREGISTRO — nada ejecutado bajo este registro.
**Corrige:** `RS-14` (sellado NO_GO el 2026-08-18).
**Entradas selladas o registradas:** `RC-F0-V2` (conjunto v2), `RC-F0-SYM` (etiquetas
corregidas y cobertura verificada), `MF-09-SYM` (el baseline estaba subestimado),
`RS-14` (protocolo congelado que se reutiliza sin tocar).

---

## 1. Por qué esto es legal bajo la §19.1, y no una segunda oportunidad

La cartera D está suspendida. Su regla de futilidad admite exactamente una excepción
que aplica aquí — la **condición 2**:

> «ninguno de esos NO_GO se explica por un defecto de implementación ya corregido (un
> corrigendum reinicia el contador **sólo si cambia la decisión**)».

`RC-F0-SYM` documentó un defecto de implementación en la métrica canónica: `rmsd_pose_pocket`
compara átomo *i* contra átomo *i* por índice de fichero y **no corrige simetría**.
Consecuencia medida sobre el conjunto v2:

| Split | Positivas ingenuas | Positivas corregidas | Cambio |
|---|---:|---:|---:|
| train | 357 | **432** | **+21.0%** |
| val | 187 | 196 | +4.8% |
| test | 216 | 252 | +16.7% |

**`RS-14` entrenó con el 21% de sus poses positivas de train etiquetadas como
negativas.** Eso es un defecto de implementación, no una arquitectura desafortunada:
no se cambia el modelo, ni la pérdida, ni la seed, ni el espacio de features. Se
corrige una etiqueta mal calculada.

**Este prerregistro no pide una segunda oportunidad y lo declara por adelantado:** un
`NO_GO` aquí **cierra la cartera D de forma definitiva**, y ningún experimento
posterior de rescoring se preregistrará sin multiplicar el número de complejos (§7).

## 2. Qué cambia exactamente: una sola cosa

| | `RS-14` | `RS-14-R1` |
|---|---|---|
| **Etiqueta de RMSD** | `rmsd` (ingenuo) | **`rmsd_sym`** (mínimo sobre automorfismos, sin alinear) |
| Features | 233 (224 raw + contrato v0.6) | idénticas |
| Transformación | z por columna dentro de complejo + percentiles | idéntica |
| Modelo e hiperparámetros | `XGBRanker` `rank:pairwise`, v0.6 congelado | idénticos |
| Evaluación | LOCO, 116 ajustes × 3 semillas (42/43/44) | idéntica |
| Nulo | 200 permutaciones dentro de complejo | idéntico |
| Baseline | `vina_score` crudo | idéntico, **re-evaluado** con la etiqueta corregida |
| Gates | G1 validez, G2 superioridad, G3 nulo | idénticos |

El runner (`scripts/run_rs14r1_selector_sym.py`) **importa** el de `RS-14` y sólo
sustituye el cargador de etiquetas y el directorio de salida. Reutilización por
import, no por copia: si algo más cambiara, la comparación mezclaría dos causas.

## 3. La cobertura NO cambia, y por eso la comparación es limpia

`RC-F0-SYM` verificó que la corrección **no mueve ni un complejo** de estado en
ninguno de los tres splits: train sigue en **92 de 116 cubiertos** (79.31%), con el
**mismo conjunto** de complejos.

Eso hace que `RS-14` y `RS-14-R1` compartan denominador **literalmente idéntico**: los
mismos 92 complejos, la misma covariable de la §9. La única diferencia entre los dos
experimentos es la etiqueta. No hay confusión posible entre «cambió el generador» y
«cambió el selector».

## 4. Lo que ya se sabe antes de ejecutar, y se declara aquí

El baseline es determinista: no depende de ningún modelo, así que se puede calcular
antes y **debe** declararse para que no parezca un hallazgo posterior.

| Baseline `vina_score`, sobre los 92 cubiertos | Valor |
|---|---:|
| Precisión condicional con etiqueta ingenua (`RS-14`) | 44/92 = **0.4783** |
| Precisión condicional con etiqueta corregida | 51/92 = **0.5543** |
| Top-1 global (ITT, 116) | 0.3793 → **0.4397** |

Los 7 complejos que el baseline gana: `188l`, `1a99`, `1b8y`, `1bcd`, `1e4h`, `1ikt`,
`1kav`. Complejos de train con al menos una etiqueta corregida: **25**, todos ellos
cubiertos.

**El listón sube 7.6 puntos porcentuales antes de que el selector haga nada.** Ese es
el hecho central de este experimento y estaba oculto detrás del defecto.

## 5. Predicción declarada

Se declara ahora y no se redefine después:

1. **El selector también sube.** Con 75 positivas más en train y una evaluación
   igualmente corregida, la precisión condicional del selector subirá desde el 0.4312
   de `RS-14`. Se predice que aterriza en el rango **[0.45, 0.58]**.
2. **La diferencia pareada seguirá sin excluir el cero.** Se predice que se mantiene
   dentro de **[−0.15, +0.05]** y que **G2 falla**.
3. **G3 (nulo) seguirá pasando con holgura.** El nulo de `RS-14` tenía p95 en 0.163 y
   el selector alcanzó 0.431 con p empírico 0.0; corregir etiquetas no crea
   memorización de ruido.

Es decir: **se predice `NO_GO`**. Preregistrar una predicción negativa es incómodo y
por eso importa dejarla escrita — si el resultado la contradice, el GO será
informativo de verdad.

**Diagnóstico obligatorio, declarado por adelantado.** Se reportará si el selector
gana sobre los **mismos 25 complejos relabelados** en los que gana el baseline, o
sobre otros. Distingue dos historias que el número agregado confunde: «el selector
aprovecha la corrección igual que Vina» frente a «la corrección sólo beneficia al
baseline».

## 6. Gates

Idénticos a los de `RS-14`. No se relaja ninguno.

| ID | Gate | Criterio |
|---|---|---|
| G1 | **Validez** | los 348 ajustes LOCO completan sin error |
| G2 | **Superioridad** (primario) | precisión condicional > baseline, con CI95 BCa de la diferencia **pareada por complejo** excluyendo el cero |
| G3 | **Nulo** | la condicional observada supera el percentil 95 del nulo por permutación (200 réplicas, barajando dentro de cada complejo) |
| G4 | **Determinismo** | misma semilla reproduce el mismo resultado |

**GO** = los cuatro pasan. **NO_GO** = falla G2 o G3.

Un GO **no promueve nada a producción** ni consume val: habilitaría una confirmación
sobre val con su propio prerregistro.

## 7. Regla de cierre, preregistrada

- **`NO_GO` → la cartera D se cierra definitivamente.** El corrigendum no cambió la
  decisión, así que por la §19.1 no reinicia el contador de futilidad. `RS-11`, `RS-12`
  y `RS-13` quedan bloqueados de forma permanente bajo el diseño actual, y cualquier
  reapertura futura exige **multiplicar el número de complejos** —la palanca que
  `RS-14` cuantificó en ~4×—, no más features, más semillas ni etiquetas más limpias.
- **`GO` → el corrigendum cambió la decisión** y reinicia el contador. Habilita una
  confirmación sobre `val`, nunca sobre `D-RC-CONFIRM` directamente.

## 8. Lo que este experimento NO puede hacer

**No arregla el límite de potencia y no se pretende que lo haga.** Con 92 complejos
cubiertos, la diferencia observada de `RS-14` (−0.047) equivalía a 4.3 complejos y el
intervalo de ±0.10 a ±9. **El diseño sigue sin poder resolver diferencias menores a
~10 puntos porcentuales.** Ninguna etiqueta lo cambia.

De hecho el desplazamiento del baseline (+7.6 pp) es **del mismo orden que la
resolución del diseño**, lo que refuerza que el criterio sea la **prueba pareada** y
no los puntos estimados.

`RS-14-R1` se justifica exclusivamente como corrección de defecto. Si alguien lo lee
como un segundo intento de ganar el gate, lo está leyendo mal.

## 9. Limitaciones declaradas

1. **El 6% de las poses conserva su RMSD ingenuo.** Sólo las de fuente `molflex`
   (17,669 de 18,812 en train) son trazables al material y tienen `rmsd_sym`; las de
   `flexible_redock` y `ruta_a` no. Como corregir sólo puede **bajar** el RMSD, el
   residuo sesga hacia **menos** positivas: la corrección aplicada es una **cota
   inferior** de la real, y el sesgo va en contra de encontrar un GO.
2. **El invariante se verifica, no se asume.** El runner aborta si alguna pose tiene
   `rmsd_sym > rmsd`: sería imposible bajo la definición de la métrica y señalaría un
   error de emparejamiento.
3. **Train se re-etiqueta entero**, entrenamiento y evaluación. No se mezclan
   etiquetas de dos generaciones dentro del mismo experimento.
4. **Val y test se re-etiquetarían igual si alguna vez se usan**, y eso exigirá su
   propio prerregistro. Aquí no se tocan.

## 10. Prohibiciones

- Prohibido comparar cifras con v1 o con v0.6 entrenado sobre v1.
- Prohibido tocar val, test o `D-RC-CONFIRM`.
- Prohibido ajustar hiperparámetros, features o semillas: todo congelado desde v0.6.
- Prohibido redefinir el umbral de 2.0 Å o la métrica después de ver resultados.
- Prohibido reportar el Top-1 global como si fuera el gate: el gate es la precisión
  condicional (§9), con la cobertura declarada como covariable.
- Prohibido reinterpretar un `NO_GO` como «faltaba limpiar más etiquetas»: la regla de
  cierre de §7 está escrita antes de ejecutar.

## 11. Presupuesto

Mismo trabajo que `RS-14`: **1,348 ajustes** (348 LOCO + 200 permutaciones × 5-fold),
**~32 min** de reloj medidos en la máquina local. Sin GPU y sin contenedor: no depende
del servidor.

## 12. Artefactos previstos

`scripts/artifacts_science/RS-14-R1/` con `metrics.json` (descomposición de la §9 por
separado, diferencia pareada con CI95 BCa, nulo, gates, y el bloque `etiquetas` con la
procedencia y el conteo de correcciones), `per_complex.jsonl` (116) y `nulo.json` (200
réplicas). Runner: `scripts/run_rs14r1_selector_sym.py`.
