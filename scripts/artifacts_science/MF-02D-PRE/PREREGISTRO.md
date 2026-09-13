# MF-02D-PRE — Sub-prerregistro: generación de registro de los 116 de train

**Fecha:** 2026-08-17
**Rama:** `experimentos/ruta-c-molflex`
**Estado:** PREREGISTRO (nada ejecutado bajo este registro)
**Refina:** `MF-02-PRE` sellado (`a09b770`, maintain `cd1c39a`).
**Entrada sellada:** `MF-02B` GO (`1af5dab`).
**Sustituye a:** `MF-02C-PRE` (sellado `MF-02C-PRE`), que **no llegó a ejecutarse** — ver §2.

---

## 1. Qué produce este experimento

MF-02B demostró el efecto: aplicar el pipeline MolFlex congelado a los 38 complejos sin cobertura recupera 30 y sube la cobertura del oráculo de 67.2% a 93.1%. Pero MF-02B corrió en **directorios temporales**: molflex los borra al terminar y solo sobrevivió el resumen JSON.

**Sin coordenadas de pose no se puede hacer nada de lo que viene después**: ni reconstruir el dataset de features que consume el selector, ni re-puntuar la unión con una función común, ni auditar una pose concreta. Este experimento produce ese material para los **116** complejos de train, conservándolo en `data/molflex_train_v2/`.

## 2. Por qué sustituye a MF-02C-PRE

`MF-02C-PRE` se selló para correr solo los 66 complejos que faltaban, reutilizando el runner de MF-02B. Al lanzarlo se detectó —antes de que produjera ningún resultado— que ese runner **descarta las poses**, de modo que MF-02C habría gastado ~40 minutos para producir un número de cobertura que MF-02B ya permitía anticipar, sin dejar material.

MF-02C-PRE queda sellado y **sin ejecución**, y se registra aquí el motivo. No se modifica ni se des-sella: en este laboratorio un prerregistro superado se documenta, no se reescribe.

## 3. Por qué los 116 y no los 66 restantes

El pipeline es determinista con semillas fijas (ETKDG 42, Vina 42). Correr también los 50 de MF-02B **debe reproducir su resultado**, y esa reproducción se convierte en un gate (G3), no en un subproducto. Un experimento que produce el material de referencia del programa tiene que demostrar que reproduce el hallazgo que lo motivó.

## 4. Protocolo

Idéntico a MF-02B salvo la conservación de artefactos: `n_conf=30`, caja de 25 Å, `exhaustiveness=8`, `num_modes=9`, `top_k=3`, `cpu=1`, semilla ETKDG 42, semilla Vina 42, más `--keep --out-dir`.

**Cohorte**: los 116 de train. Cero val, cero test, cero `D-RC-CONFIRM`.

**Salida**: poses en `data/molflex_train_v2/<pid>/` (material, fuera del árbol de artefactos por la §17 del doc. 49), resúmenes por complejo y, por pose entregada, `conf_id`, `rigid_score`, `relaxed_score` y `rmsd_to_crystal`.

## 5. Gates

| ID | Gate | Criterio |
|---|---|---|
| G1 | **Validez** | ≥95% de los 116 completan sin error |
| G2 | **Material** | todo complejo con éxito deja sus `.pdbqt` de pose en disco — un experimento cuyo producto es material falla si el material no está |
| G3 | **Reproducción** | reproduce la decisión de MF-02B en los 38 sin cobertura, complejo a complejo, sin discrepancias |
| G4 | **No regresión** | la unión no reduce la cobertura de ningún complejo |
| G5 | **Cobertura** | la cobertura del oráculo de train con la unión alcanza ≥90% |

**GO** = los cinco pasan. **NO_GO** = falla cualquiera de G2, G3 o G4. Si falla G1 se repite y no se interpreta.

## 6. Fuera de alcance, declarado

- **No reconstruye `poses_train.jsonl`** con features (`vina_score`, contactos, densidad de cluster, procedencia por pose). Eso es ingeniería de datos con su propio contrato y su propio prerregistro.
- **No evalúa ningún selector** ni mide precisión condicional. Ese es el paso siguiente y, por la §19.1, su prerregistro tendrá que declarar explícitamente que el denominador cambió y en cuánto.
- **No toca val, test ni `D-RC-CONFIRM`.**

## 7. Prohibiciones

- Prohibido cambiar cualquier parámetro del pipeline: la homogeneidad de los 116 es el propósito.
- Prohibido sustituir poses del dataset por las nuevas: la operación es unión.
- Prohibido leer el GO como «el dataset ya está reconstruido».
