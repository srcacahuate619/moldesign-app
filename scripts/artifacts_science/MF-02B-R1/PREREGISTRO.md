# MF-02B-R1-PRE — Corrigendum de MF-02B: el mismo dato con la métrica correcta

**Fecha:** 2026-08-17
**Rama:** `experimentos/ruta-c-molflex`
**Tipo:** corrigendum de `MF-02B` (sellado GO, `1af5dab`). MF-02B **no se modifica ni se des-sella**.
**Precedente:** `REC-01-R1` y `RS-04-OOF-R1` — mismo dato, criterio corregido.
**Material:** `MF-02D` (sellado NO_GO), 17,596 poses dockeadas de los 116 de train.

---

## 1. Qué estuvo mal

MF-02B midió el éxito de una pose con `rmsd_best_to_crystal` de `molflex.ejecutar_complejo`, que se calcula con `rmsd_pesados` → `AllChem.GetBestRMS`. **GetBestRMS alinea** las dos moléculas antes de comparar, de modo que mide si la geometría interna del ligando coincide, no si la pose está en el sitio correcto.

El conjunto de poses contra el que se comparaba etiqueta con `rmsd_pose_pocket`: RMSD de átomos pesados **en el marco del pocket, sin alinear**.

El repositorio ya tenía la advertencia escrita —lección de auditoría del 2026-08-14, en el docstring de `rmsd_pose_pocket`—: *«GetBestRMS ALINEA los dos mols y oculta desplazamientos; una pose movida ~4 Å del pocket puede reportar RMSD ~0. Para poses dockeadas usar ESTA función.»* No la apliqué.

El sesgo tiene signo conocido: el RMSD alineado es **siempre ≤** el de pocket. Por construcción, MF-02B solo podía sobreestimar.

## 2. Qué se recalcula, y sobre qué

**Nada se vuelve a ejecutar.** El corrigendum usa el material de MF-02D, que reprodujo MF-02B **exactamente** (38/38 complejos, cero discrepancias): las poses son las mismas, solo cambia la regla con que se juzgan.

**Métrica corregida**: mínimo `rmsd_pose_pocket` sobre **todas** las poses dockeadas (`conf*.out.pdbqt`, todos los MODEL de todos los conformeros) — el conjunto exacto que consume `build_pose_selector_dataset.py` en su fuente S2. Es una definición **más generosa** que la de MF-02B, que solo miraba el top-K entregado: si aun así el número baja, la corrección no admite discusión.

**Umbral**: 2.0 Å, sin cambios.

**Cohorte**: los mismos 38 complejos sin cobertura y los mismos 12 de control. Sin altas ni bajas.

## 3. Gate

El gate preregistrado de MF-02B era **G2: `A8` recupera ≥10 de los 38**. El corrigendum lo evalúa con la métrica corregida y **no lo cambia**: cambiar el umbral al reevaluar sería exactamente el vicio que el preregistro existe para impedir.

- Si el número corregido sigue ≥10, la **decisión GO de MF-02B se sostiene** y lo que se corrige es la magnitud.
- Si cae por debajo, MF-02B pasa a NO_GO y así se registra.

## 4. Lo que este corrigendum no hace

- No modifica `MF-02B`: queda sellado con sus cifras, y este documento dice cuáles las sustituyen.
- No reejecuta nada ni cambia el pipeline.
- No toca la conclusión de `MF-02A`, donde el alineamiento es **correcto a propósito**: allí se mide disponibilidad conformacional (geometría interna, libre en el espacio) y GetBestRMS es la función adecuada. Eso quedó declarado en su prerregistro antes de ejecutar.
