# Eficiencia normalizada por tamaño — medición sobre la cohorte de Vina

**Fecha:** 2026-09-04
**Cohorte:** 8 dianas, 17 431 moléculas con score de Vina y SMILES parseable
(`data/gnn_v31/checkpoints/benchmark_checkpoint_*.json`)
**Motivo:** decidir si las métricas normalizadas por tamaño de la literatura
reducen de verdad la dependencia con el número de átomos pesados en ESTE
producto, antes de exponerlas — y antes de plantearse siquiera meterlas en el
ranking.

---

## Qué se midió

Correlación de Spearman de cada métrica contra el número de átomos pesados
(HA). Cero significa que la métrica no depende del tamaño; que es la propiedad
que se busca.

Se reporta el promedio del valor absoluto **por diana**, no sobre el conjunto
mezclado: dianas distintas tienen distribuciones de tamaño distintas y
mezclarlas introduce una correlación que no es de la métrica.

| Métrica | ρ medio (abs) | Peor diana | Mejor diana |
|---|---:|---:|---:|
| \|Vina\| crudo | 0.817 | 0.880 | 0.696 |
| **LE = \|Vina\| / HA** (Hopkins et al. 2004) | **0.824** | 0.949 | 0.594 |
| SILE = \|Vina\| / HA^0.3 (Nissink 2009) | 0.370 | 0.642 | 0.174 |
| **FQ = LE / LE_scale(HA)** (Reynolds et al. 2008, proxy) | **0.216** | 0.398 | 0.015 |

Con signo, para ver qué hace cada una:

| Diana | n | \|Vina\| | LE | SILE | FQ |
|---|---:|---:|---:|---:|---:|
| 5ht1a | 2544 | +0.851 | −0.683 | +0.642 | −0.015 |
| ca2 | 1933 | +0.845 | −0.949 | +0.174 | +0.120 |
| cdk2 | 2532 | +0.740 | −0.762 | +0.385 | −0.292 |
| er_alpha | 2043 | +0.829 | −0.594 | +0.595 | +0.145 |
| factor_xa | 1975 | +0.849 | −0.932 | +0.279 | +0.166 |
| glp1r | 1926 | +0.847 | −0.924 | +0.231 | +0.208 |
| hiv_protease | 2533 | +0.696 | −0.816 | +0.224 | −0.398 |
| thrombin | 1945 | +0.880 | −0.930 | +0.426 | +0.384 |

---

## El resultado que decide

**LE no corrige el sesgo de tamaño. Lo empeora ligeramente** (0.824 frente a
0.817 del score crudo). Lo único que hace es invertir el signo: el score de
Vina premia el tamaño y LE lo castiga, con casi la misma fuerza.

Eso confirma con datos lo que ya se había visto por álgebra al auditar los
mensajes del producto: los umbrales fijos de LE (0.25 / 0.45) se traducen en
una afinidad exigida que crece linealmente con la molécula, de modo que un
fragmento siempre superaba el corte alto y una molécula de 50 átomos no podía
alcanzarlo nunca.

**FQ reduce la dependencia unas 3.8 veces respecto de LE** (0.216 frente a
0.824). No la elimina: sigue habiendo dianas donde queda en ±0.4, y el signo
cambia entre dianas, así que no es una corrección uniforme. SILE queda en
medio.

Distribución de tamaños de la cohorte: HA mínimo 7, mediana 16, máximo 64. El
**30.7 %** de las moléculas cae fuera del rango 15-50 del ajuste de Reynolds y
recibe la escala sujetada al extremo, como recomiendan los autores. No es un
caso raro: es un tercio del conjunto, y por eso el resultado marca
`escala_sujetada`.

---

## Qué se implementó, y qué no

Implementado en `backend/scoring/eficiencia.py`, expuesto como campos
calculados de `EvaluationResultRead` (`sile_vina`, `fq_vina_proxy`) y como
bloque con fórmula y referencia en el dossier:

- Los cuatro coeficientes de Reynolds, **verificados contra la tabla 3 del
  artículo** antes de escribirlos. Reproducen las cuatro filas dentro del
  redondeo (delta < 5·10⁻⁵). `tests/test_eficiencia_normalizada.py` las ancla.
- El límite [15, 50] del ajuste, con el hecho de haberlo aplicado en el
  resultado en vez de implícito.
- SILE con exponente 0.3, **sin umbral**: Nissink no publica ninguno.

**No implementado a propósito:**

- Ninguna de las dos entra en `total_score`. Reducir la correlación con HA no
  es lo mismo que mejorar el ranking; eso hay que medirlo aparte, con las
  etiquetas de actividad de la cohorte, y no se ha hecho.
- No hay umbral de FQ ni de SILE. FQ ≈ 1 significa proximidad a la envolvente
  eficiente del conjunto de Reynolds **para ese tamaño**, no probabilidad de
  unión ni calidad de pose.

---

## Lo que estas métricas NO arreglan

Corrigen el sesgo de tamaño mejor que `|Vina|/HA`. No corrigen:

- una pose equivocada,
- un receptor equivocado,
- la incertidumbre de la propia función de puntuación de Vina,
- la procedencia de la afinidad.

Y hay discusión metodológica posterior sobre si merecen llamarse
«independientes del tamaño». Encajan aquí como métricas normalizadas y
auditables. No como veredictos.

## Una precisión sobre el proxy

Reynolds ajustó `LE_scale` contra afinidades experimentales (Ki), no contra
scores de acoplamiento. El artículo sugiere que la escala puede resultar útil
con scores de docking pero no publica una calibración específica de Vina. Por
eso el campo se llama `fq_vina_proxy` y no `fit_quality`: el nombre carga la
advertencia.

La conversión kcal/mol → unidades log usa 1.37, el valor convencional en
química medicinal. Dividiendo la columna en kcal de la tabla 3 entre la columna
en pKi, el factor implícito del artículo es **1.36788**, un 0.15 % menor. La
diferencia es irrelevante frente a la incertidumbre de tratar un score de Vina
como un pKi, y se deja escrita para que nadie la encuentre como si fuera un
error.

## Reproducir

```
python -c "..."   # el script de medición vive en el commit;
                  # cohorte en data/gnn_v31/checkpoints/
```

Las correlaciones se recalculan con `scipy.stats.spearmanr` sobre
`(heavy_atoms, métrica)` por diana, con RDKit contando los átomos pesados desde
el SMILES de cada registro.
