# RS-09 — Robustez metamórfica del selector v0.6

**Decisión: NO_GO** — el selector v0.6 NO es robusto a perturbación débil de
coordenadas (σ = 0.1 Å), con 9 flips ok→mal (criterio G3: ≤ 2).

## Resumen ejecutivo

RS-09 evaluó el checkpoint de producción `pose_selector_v06.xgb` (SHA-256
`9827ddb9...5e31`, congelado) sobre la cohorte train bajo tres metamorfosis:
A) invarianza rígida (R + t), B) permutación del orden de poses, C)
perturbación gaussiana de 0.1 Å sobre los átomos pesados del ligando.

| Gate | Criterio | Resultado | Verdicto |
|---|---|---|---|
| G1 invarianza rígida | 109/109 Top-1 idéntico, max_dif ≤ 1e-6 | 109/109, max_dif = 0.0 | PASS |
| G2 orden | 109/109 Top-1 idéntico | 109/109 | PASS |
| G3 flips ok→mal | ≤ 2 | **9** | **FAIL** |
| G4 cambios en terciles 1-2 | ≥ 60% | 95.65% | PASS |
| G5 drift re-extracción | 0 mismatches | 0 | PASS |
| G6 aislamiento checkpoint | SHA idéntico | OK | PASS |

**Decisión: NO_GO** (G3).

## Hallazgos

1. **Invarianza rígida perfecta (G1)**. Las 224 features del extractor v0.5
   son exactamente invariantes a rotación/traslación del sistema completo
   (pose + receptor): max_dif_224 = 0.0 en los 109 complejos. Es un resultado
   de construcción (contactos y shells son invariantes rígidos), confirmado
   empíricamente.

2. **Invariancia al orden (G2)**. La puntuación z intra-complejo + percentil
   es invariante al orden de entrada: 109/109 Top-1 idéntico bajo permutación
   determinista. Confirma la propiedad matemática del pipeline.

3. **Sensibilidad a perturbación (G3/G4)**. Bajo ruido σ = 0.1 Å:
   - 23/109 complejos (21.1%) cambian su Top-1.
   - 9 complejos (8.3%) hacen **flip ok→mal** (una pose buena deja de ser
     seleccionada y gana una mala). Criterio G3 (≤ 2) NO se cumple.
   - Los cambios se concentran en márgenes bajos: tercil 1 (margen ≤ 0.123):
     43.2% de complejos cambian; tercil 2: 16.7%; tercil 3: 2.8%.
     G4 (≥ 60% en terciles 1-2) se cumple con 95.65% de los cambios.

4. **Determinismo del extractor (G5)**. Re-extracción limpia idéntica a la
   canónica en 109/109 complejos: el extractor es determinista y el resultado
   NO se explica por drift de re-extracción.

## Interpretación

El selector es **robusto por construcción** a transformaciones rígidas y al
orden de entrada, pero **sensible a perturbaciones atómicas** de 0.1 Å. Esta
sensibilidad es esperable y acotada: la magnitud del ruido (0.1 Å) es
comparable a la precisión posicional de los dockings, y los flips se
concentran en complejos con margen de puntuación pequeño (media 0.27, mediana
0.21). El comportamiento es coherente con la hipótesis de robustez
**condicional al margen** (§4 de RS-09-PRE): complejos con margen bajo son
inherentemente inestables ante cualquier perturbación de entrada.

NO_GO implica que el criterio G3 fue definido de forma estricta (≤ 2 flips).
El resultado NO invalida el uso del selector: 91.7% de los complejos no
sufren flip bajo perturbación, y los flips ocurren donde el margen ya
indicaba indecisión. Implicación práctica: el margen de puntuación debe
tratarse como señal de confianza (coherente con el router margin-only de
RS-03) y el pipeline debe congelar coordenadas antes de la extracción de
features en producción.

## Desviación de ejecución (documentada)

- El prerregistro RS-09-PRE declaró 116/116 complejos. La ejecución cubrió
  **109/116 (93.97%)**: 7 complejos molflex puros (10gs, 184l, 187l, 188l,
  1a30, 1a99, 1ai4) no tienen receptor en ninguna fuente disponible
  (`scripts/.work_molflex_v3` no existe en el worktree; sin rec.pdbqt
  nativo ni fallback). Se declaran NO cubiertos por indisponibilidad de
  datos, no como fallos del selector.
- Fuente de coordenadas canónicas: `lig_pos` de
  `data/pose_selector_dataset/gnn_train.pt` (dataset congelado; 2739/2739
  poses con lig_pos, mapeo serial→mol ya aplicado por el pipeline).
- Receptores: fuente nativa (`v05.obtener_receptor`) con fallback a
  `vina_redock_work/{pid}/{pid}_rec.pdbqt` y `dmfhard_curve_work/{pid}/rec.pdbqt`
  para molflex. Equivalencia verificada: bolsillo `prot_pos` del dataset
  congelado ⊆ receptor fallback, match atómico ≤ 1e-3 Å en los complejos
  control (186l, 1a4w, 1aaq, 1add, 1afk, 1afl).

## Artefactos

- `metrics.json` — gates, métricas por test, cobertura y márgenes.
- `per_complex.jsonl` — resultado por complejo (A/B/C, margen).
- `failures.jsonl` — fallos A y B (vacío: ningún complejo falló A/B).
- `run_rs09_robustez.py` — runner (reproducible, seeds 1000+i / 2000+i / 42+i).
- Prerregistro: `scripts/artifacts_science/RS-09-PRE/PREREGISTRO.md`.
