# MF-02C-PRE — Sub-prerregistro: completar la aplicación del generador a los 116 de train

**Fecha:** 2026-08-17
**Rama:** `experimentos/ruta-c-molflex`
**Estado:** PREREGISTRO (nada ejecutado bajo este registro)
**Refina:** `MF-02-PRE` sellado (`a09b770`, maintain `cd1c39a`). No lo modifica ni lo des-sella.
**Entrada sellada:** `MF-02B` GO (`1af5dab`) — 30 de 38 recuperados, cobertura del oráculo 67.2% → 93.1%.

---

## 1. Qué queda por hacer y por qué

`MF-02B` aplicó el pipeline MolFlex congelado a **50** de los 116 complejos de train: los 38 sin cobertura y 12 de control. Quedan **66** a los que el generador sigue sin aplicarse.

Completarlos no es cosmético. Toda evaluación futura de un selector necesita un denominador homogéneo: si 50 complejos tienen poses de MolFlex y 66 no, cualquier diferencia entre estratos puede ser un artefacto de a cuáles se les corrió el generador. Es exactamente el sesgo que produjo el conjunto actual, donde MolFlex se aplicó a 13 de 116.

## 2. Protocolo

**Idéntico a MF-02B, sin excepción.** El runner de MF-02C **importa y reutiliza sin modificar** la función de ejecución del runner sellado de MF-02B, de modo que el protocolo por complejo es byte-idéntico: `n_conf=30`, caja de 25 Å, `exhaustiveness=8`, `num_modes=9`, `top_k=3`, `cpu=1`, semilla ETKDG 42, semilla Vina 42.

**Cohorte**: los 66 complejos de train que no corrieron en MF-02B. Cero val, cero test, cero `D-RC-CONFIRM`.

**Métrica**: mejor RMSD a cristal entre las poses entregadas (top-K relajadas), igual que en MF-02B. La cobertura se calcula sobre la **unión** `dataset ∪ MolFlex`, nunca sustituyendo.

## 3. Gates

| ID | Gate | Criterio |
|---|---|---|
| G1 | **Validez** | ≥95% de los 66 completan el pipeline sin error |
| G2 | **No regresión** | la unión no reduce la cobertura de ningún complejo |
| G3 | **Cobertura** | la cobertura del oráculo de train con la unión alcanza **≥90%** |

**GO** = los tres pasan. **NO_GO** = falla G2 o G3.

G3 se fija en 90% y no en un número mayor porque MF-02B ya dejó la cobertura en 93.1% con 50 complejos corridos: el gate verifica que completar los 66 **no la degrade**, no que la suba. Subirla más allá dependería de complejos que ya estaban cubiertos.

## 4. Lo que este experimento NO hace

- **No reconstruye `poses_train.jsonl`.** Medir cobertura del oráculo es una cosa; producir el dataset de features que consume el selector (`vina_score`, contactos, densidad de cluster, procedencia por pose) es ingeniería de datos con su propio contrato y su propio prerregistro. Queda **fuera de alcance** y se declara aquí para que nadie lea este GO como «el dataset ya está reconstruido».
- **No mide precisión condicional ni evalúa ningún selector.** Eso exige un prerregistro propio con protocolo OOF, y es el paso siguiente.
- **No toca val, test ni `D-RC-CONFIRM`.**

## 5. Prohibiciones

- Prohibido cambiar cualquier parámetro del pipeline respecto de MF-02B: si se cambiara, los 116 dejarían de ser homogéneos y el propósito del experimento se perdería.
- Prohibido sustituir poses del dataset por las nuevas: la operación es unión.
- Prohibido concluir nada sobre el selector desde aquí.
