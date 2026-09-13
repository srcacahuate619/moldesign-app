# Curated Targets — Distribución por Familia

> **Estado Julio 2026:** Esta biblioteca curada tiene **sesgo parcial hacia GPCRs en el orden**
> del CSV, pero la distribución global entre familias es razonable. Ver
> `datos_para_paper.md §6` para análisis de brecha multi-familia.

---

## Distribución por Familia (CSV, 80 targets)

Análisis de `curated_targets.csv` agrupado por `family`:

| Familia | Count |
|---------|-------|
| kinase | 15 |
| gpcr | 14 |
| protease | 11 |
| nuclear_receptor | 10 |
| cytochrome | 5 |
| transferase | 4 |
| hydrolase | 4 |
| ion_channel | 3 |
| phosphodiesterase | 3 |
| protein_interaction | 2 |
| oxidoreductase | 2 |
| reductase | 1 |
| isomerase | 1 |
| bromodomain | 1 |
| chaperone | 1 |
| transporter | 1 |
| gtpase | 1 |
| checkpoint | 1 |
| **Total** | **80** |

**17 familias distintas** en 80 targets. Distribución razonable.

---

## JSON Extendida (386 targets)

El JSON hermano (`curated_targets.json`) contiene 386 PDB IDs pero muchos tienen
`family: null`. **Análisis proporcional de la diversidad protein-family pending.**

---

## Sesgo de Orden (observación menor)

**Inspección de las primeras 10 filas del CSV:**

| # | PDB | Target | Familia |
|---|-----|--------|---------|
| 1 | 7E2Y | 5-HT1A | GPCR |
| 2 | 6X1A | GLP-1R | GPCR |
| 3 | 6CM4 | μ-Opioid | GPCR |
| 4 | 5TGZ | CB1 | GPCR |
| 5 | 4BVN | A2A | GPCR |
| 6 | 6PS2 | β-2 Adrenergic | GPCR |
| 7 | 7DFL | H1 Histamine | GPCR |
| 8 | 6WHA | M2 Muscarinic | GPCR |
| 9 | 5NDD | CCR5 | GPCR |
| 10 | 6MEO | CXCR4 | GPCR |

**Nota:** Las primeras 10 son todas GPCRs pero la distribución global (15 kinase,
14 GPCR, 11 protease, ...) es razonable. El número 7E2Y (5-HT1A) está marcado como
target primario en la documentación del proyecto por su uso extensivo en demos
y tests. No refleja sesgo en la calidad del modelo, solo en el orden del archivo.

---

## Recomendaciones

1. **Para benchmarks rigurosos**: usar listas externas como
   DUD-E (102 targets balanceados por familia) o LIT-PCBA (descartado por data
   leakage documentado en `moldesign-app/docs/08_SCIENTIFIC_VALIDATION.md`).

2. **BLAST clustering 30% sobre 386 targets**: pendiente. Sin este análisis, no
   podemos reportar "386 targets diversos". Probablemente sean 273 clusters
   únicos (estimación de docs `moldesign-app/docs/14_TARGET_LIBRARY.md`).

3. **Documentar en papers**: cualquier trabajo que use esta biblioteca como
   benchmark debe declarar la distribución por familia en §Methods y mitigarlo
   con validación multi-target externa si es necesario.

---

## TODO

- [ ] BLAST clustering 30% sobre los 386 PDB IDs y reportar clusters únicos.
- [ ] Análisis family=null en JSON (descartar o asignar manualmente).
- [ ] Reportar distribución JSON (386) por familia una vez completada asignación.
- [ ] Expandir a 10 targets de ≥4 familias siguiendo `datos_para_paper.md §11.2`.

---

*Documentado como parte de remediación post-auditoría 2026-07-23.*