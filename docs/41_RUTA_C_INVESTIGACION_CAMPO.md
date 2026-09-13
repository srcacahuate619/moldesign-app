# 41 - Ruta C: Investigación de campo cross-disciplinaria

**Fecha**: 2026-08-14 · **Estado**: investigación concluida, diseño pendiente
**Objetivo**: extraer mecanismos de otras disciplinas para el re-ranker ML que
selecciona la pose tipo-cristal entre N poses de docking (Ruta C).

---

## 1. El problema que Ruta C ataca

El score de Vina NO selecciona la pose tipo-cristal (confirmado 3 veces: R4 y
la recomputación pocket-frame 2026-08-14): poses con buena geometría interna
quedan desplazadas 8-13 Å del sitio bioactivo, con scores energéticos casi
degenerados entre poses buenas y malas. GNINA (3D CNN) logra Top1 73% vs 58%
de Vina porque su score aprendido correlaciona con RMSD — no refina energía.

Activos propios: corpus redocked PDBbind con poses + RMSD-to-crystal como
ground truth; pipeline de generación barato (docking exh=4 estándar desde
hoy); experiencia GNN propia (MolGraph/MolChamb).

## 2. Método

Investigación de campo en 3 disciplinas, en el orden de prioridad pedido:
fisiología/biología → ingeniería física/hardware → ingeniería de software.
Fuentes reales consultadas por fetch directo (Wikipedia como ancla; PMC/PNAS/
PLOS, ESA Navipedia, NIST/SEMATECH, Marposs, Radartutorial, arXiv, Microsoft
Research). Las fuentes clásicas con paywall se marcan "no verificado".

## 3. Hallazgos por disciplina

### 3.1 Fisiología / biología

| Mecanismo | Idea transferible |
|---|---|
| **Prueba conformacional** (Savir & Tlusty 2007, PNAS) | La discriminación exige una señal de verificación que penaliza ASIMÉTRICAMENTE a los parecidos-al-correcto; especificidad ξ∼exp(k·Δ·d) |
| **Kinetic proofreading** (Hopfield 1974; TCR McKeithan 1995) | "Primera suposición, luego VERIFICAR" con señal independiente, en cascada; amplifica diferencias pequeñas |
| **Selección conformacional / MWC** | El receptor decide entre estados pre-existentes con una señal de estado ≠ energía de unión |
| **Código combinatorio olfativo** | La identidad es un PATRÓN poblacional de activación, no el máximo de una señal única |
| **Integración multisensorial bayesiana** | Combinar señales con pesos ∝ confiabilidad; discrepancia fuerte entre señales → rechazar, no promediar |
| **Control de calidad del RE (UGGT/BiP/ERAD)** | Verificador cuya señal es DIFERENTE del score del generador, con presupuesto de intentos y rechazo irreversible |
| **Recocido de chaperoninas (GroEL/ES)** | Candidato atrapado en mínimo local: perturbación parcial + reintento (top-k refine loop) |
| **Selección clonal / maduración de afinidad** | Diversidad barata + selección iterativa; re-entrenar sobre los casos difíciles |
| **Hiperagudeza (vernier)** | Lectura poblacional sub-sensor: interpolar entre candidatos discretos |
| **Paisajes de aptitud rugosos** | No descartar poses de score intermedio; re-evaluación contextual por blanco |

### 3.2 Ingeniería física / hardware

| Mecanismo | Idea transferible |
|---|---|
| **RAIM/FDE (GNSS)** | Con redundancia, la verdad se identifica por CONSISTENCIA MUTUA: residuo = observado − esperado; detectar y EXCLUIR el canal defectuoso; solution separation |
| **Filtro de Kalman** | Combinar canales pesando por covarianza; el prior/modelo es otra señal independiente |
| **MHT + track-before-detect** | Posterior sobre TODAS las hipótesis; diferir el compromiso; acumular evidencia antes de decidir |
| **TMR / N-version programming** | Comité diverso + votación — PERO Knight & Leveson 1986: la independencia de fallos NO se asume, se valida |
| **Ensamblaje selectivo** | No arregles el generador: MIDE la salida real y empareja (justificación exacta de Ruta C) |
| **Filtro adaptado / compresión de pulsos** | Detección óptima = correlación contra plantilla aprendida con pico AGUDO (margen) y control de lóbulos secundarios |
| **MRC / rake receiver** | No descartar canales débiles si su error es independiente; calibrar (alinear) antes de sumar |
| **LDPC / belief propagation** | Restricciones locales redundantes localizan QUÉ parte es defectuosa (síndrome estructurado) |
| **FDI por residuales** | El residual contra la predicción de un modelo calibrado es la señal más limpia |
| **Marzullo / NTP** | Consenso de intervalos: el ganador es la región de acuerdo del mayor número de estimadores |
| **Proof-of-work** | Asimetría generar/verificar: verificación barata y repetible |

### 3.3 Ingeniería de software / sistemas ML

| Mecanismo | Idea transferible |
|---|---|
| **Learning to Rank (LambdaRank/LambdaMART)** | Optimizar el ORDEN relativo, no el valor absoluto; margen ∝ ganancia de la métrica (NDCG→RMSD) |
| **RANSAC** | La hipótesis correcta maximiza el consenso con un modelo externo (inliers); los outliers no votan consistente |
| **Fuzzing + oráculo diferencial** | Dos verificadores independientes que discrepan señalan casos ambiguos sin ground truth |
| **QuickCheck shrinking** | Reducir el error al núcleo causal mínimo (diagnóstico + data augmentation de pares duros) |
| **MCTS/UCT** | Con recompensas ruidosas, la rama con más apoyo acumulado gana; exploración evita mínimos locales |
| **Stacking + calibración + conformal** | Combinar scorers diversos con meta-modelo; abstenerte cuando el modelo no sabe |
| **Detección de anomalías (one-class)** | Modelar la densidad de lo NATIVO (la clase mala es heterogénea e ilimitada) |
| **Cascadas + reglas de deferral** | Gasta el verificador caro solo en casos duros (margen bajo entre poses) |
| **Contrastive learning (InfoNCE)** | Aprender la distancia correcta: pares bueno/bueno cerca, bueno/malo lejos |
| **Metamorphic testing** | Validar el selector con invarianzas (rotación, perturbación débil) sin gastar cristales |

## 4. Principios convergentes (lo más valioso)

Seis patrones aparecen INDEPENDIENTEMENTE en las tres disciplinas — cuando la
naturaleza, el hardware y el software convergen en la misma solución, es la
señal más fuerte de que es el principio correcto:

### C1. Señal de verificación ORTOGONAL al generador
Biología (proofreading, BiP), hardware (RAIM residual, matched filter) y
software (LTR ≠ BM25, RANSAC ≠ sampler) coinciden: el selector debe usar una
señal que NO comparta la función objetivo del generador. → El head de Ruta C
predice native-likeness/RMSD, jamás re-pondera la energía.

### C2. Combinar por confiabilidad + rechazar al discrepar
Kalman (covarianza), integración multisensorial (pesos por confiabilidad),
MRC (SNR), RAIM (excluir), Marzullo (consenso), conformal (abstención):
combinar señales débiles por su confiabilidad aprendida, y cuando discrepan
fuertemente, RECHAZAR en vez de promediar.

### C3. Amplificar diferencias pequeñas
Prueba conformacional (ξ∼exp(k·Δ·d)), TCR (umbrales secuenciales), compresión
de pulsos (pico agudo), LambdaRank (margen ∝ ganancia): el entrenamiento debe
separar parejas casi-degeneradas con márgenes proporcionales a ΔRMSD.

### C4. Consenso/consistencia entre candidatos ES la señal
Código olfativo (patrón poblacional), hiperagudeza, RAIM solution separation,
MHT, RANSAC inliers, ensembles: la pose correcta es consistente con el
receptor y con las demás evidencias; la densidad de poses vecinas es
informativa.

### C5. Posterior + compromiso diferido + presupuesto
MHT/TBD, centros germinales, ciclo ER, cascadas: emitir posterior sobre las N
poses; gastar verificación cara solo en casos de baja confianza; abstenerse
antes que adivinar.

### C6. No arregles el generador: mide y empareja
Ensamblaje selectivo, SPC, two-stage retrieval: la precisión del sistema sale
del verificador, no del generador. Es la justificación conceptual de Ruta C.

## 5. Mapeo preliminar a arquitectura (para la fase de diseño)

- **Backbone**: GNN sobre el complejo proteína-ligando (familia MolGraph),
  head doble: native-likeness + incertidumbre calibrada (C1, C2).
- **Función de pérdida**: ranking pairwise/listwise estilo LambdaRank con
  márgenes ∝ ΔRMSD, amplificados para pares difíciles (C3); pérdida
  contrastiva auxiliar para la representación (C4).
- **Señales del ensemble**: score Vina (contexto), score GNN, consenso
  geométrico tipo RANSAC (contactos tipo-cristal), densidad de clúster de
  poses, features de anomalía (C2, C4); stacker calibrado + conformal para
  abstinencia (C5).
- **Decisión**: posterior sobre poses (no argmax), top-k con deferral a
  verificación cara cuando el margen es bajo (C5); salida por "bins" de
  confianza (C6).
- **Diagnóstico**: síndrome/shrinking para localizar la inconsistencia mínima
  de una pose rechazada (C4, QuickCheck) — genera explicabilidad y pares de
  entrenamiento duros.

## 6. Ranking de prioridad para el diseño

1. **C1 (señal ortogonal) + LambdaRank** — head nativo + pérdida de ranking
   con margen ∝ ΔRMSD: el núcleo del re-ranker.
2. **C2 (fusión ponderada + abstención conformal)** — ensemble calibrado;
   resolver "no sé" con honestidad.
3. **C4 (consenso tipo RANSAC + patrón poblacional)** — feature barata,
   explicable, independiente del docking.
4. **C5 (cascada con deferral)** — gastar verificación cara solo en casos
   degenerados (nuestro fallo exacto: 8-13 Å con scores empatados).
5. **C3/C6** — diseño de pérdida y de pipeline (no arquitectura nueva).

## 7. Fuentes (consultadas por fetch directo)

Biología: en.wikipedia.org/wiki/Monod–Wyman–Changeux_model ·
pmc/articles/PMC1868595 (Savir & Tlusty) · en.wikipedia.org/wiki/Conformational_proofreading ·
pmc/articles/PMC434344 (Hopfield) · en.wikipedia.org/wiki/Kinetic_proofreading ·
pmc/articles/PMC41844 (McKeithan) · en.wikipedia.org/wiki/Clonal_selection ·
en.wikipedia.org/wiki/Affinity_maturation · pmc/articles/PMC39481 (Todd et al.) ·
en.wikipedia.org/wiki/Chaperonin · en.wikipedia.org/wiki/Unfolded_protein_response ·
en.wikipedia.org/wiki/Olfactory_receptor · en.wikipedia.org/wiki/Vibration_theory_of_olfaction ·
en.wikipedia.org/wiki/Multisensory_integration · en.wikipedia.org/wiki/Hyperacuity ·
en.wikipedia.org/wiki/Fitness_landscape · en.wikipedia.org/wiki/Allostasis ·
en.wikipedia.org/wiki/Metabolite_channeling
(No verificados: Boehr/Nussinov/Wright 2009; Ernst & Banks 2002; Alon et al. 2007 — paywall.)

Hardware: en.wikipedia.org/wiki/Receiver_autonomous_integrity_monitoring ·
gssc.esa.int/navipedia/index.php/RAIM_Algorithms · en.wikipedia.org/wiki/Trilateration ·
en.wikipedia.org/wiki/Kalman_filter · radartutorial.eu/10.processing/sp25.en.html ·
en.wikipedia.org/wiki/Track-before-detect · en.wikipedia.org/wiki/Triple_modular_redundancy ·
en.wikipedia.org/wiki/N-version_programming · marposs.com/eng/application/sel-assembly ·
en.wikipedia.org/wiki/Statistical_process_control · itl.nist.gov/div898/handbook/pmc/section3/pmc31.htm ·
en.wikipedia.org/wiki/Acceptance_sampling · en.wikipedia.org/wiki/Proof_of_work ·
en.wikipedia.org/wiki/Matched_filter · en.wikipedia.org/wiki/Pulse_compression ·
en.wikipedia.org/wiki/Maximum-ratio_combining · en.wikipedia.org/wiki/Rake_receiver ·
en.wikipedia.org/wiki/Low-density_parity-check_code · en.wikipedia.org/wiki/Fault_detection_and_isolation ·
en.wikipedia.org/wiki/State_observer · en.wikipedia.org/wiki/Structural_health_monitoring ·
en.wikipedia.org/wiki/Marzullo%27s_algorithm

Software: en.wikipedia.org/wiki/Learning_to_rank · microsoft.com/en-us/research/publication/from-ranknet-to-lambdarank-to-lambdamart-an-overview ·
en.wikipedia.org/wiki/Random_sample_consensus · en.wikipedia.org/wiki/Fuzzing ·
lcamtuf.coredump.cx/afl/technical_details.txt · en.wikipedia.org/wiki/QuickCheck ·
en.wikipedia.org/wiki/Monte_Carlo_tree_search · en.wikipedia.org/wiki/Ensemble_learning ·
en.wikipedia.org/wiki/Conformal_prediction · en.wikipedia.org/wiki/Anomaly_detection ·
en.wikipedia.org/wiki/Belief_propagation · en.wikipedia.org/wiki/Byzantine_fault ·
arxiv.org/abs/2405.19261 · research.google/blog/speculative-cascades-a-hybrid-approach-for-smarter-faster-llm-inference ·
arxiv.org/abs/2002.05709 (SimCLR) · arxiv.org/abs/1807.03748 (CPC) ·
en.wikipedia.org/wiki/Metamorphic_testing

## 8. Addendum experimental — 2026-08-15

La operacionalización de C1/C4 se documenta y preregistra en
[`47_RUTA_C_FASE4_PREREGISTRO.md`](47_RUTA_C_FASE4_PREREGISTRO.md). Dos
hipótesis de bajo costo se cerraron negativamente sin volver a consultar el
test histórico: objetivo nativo directo (`rank:pairwise`/`rank:ndcg`) y
ensamble de rangos v0.6–Vina. El siguiente experimento debe añadir señal
física direccional nueva; reponderar los mismos 233 descriptores no ha dado
una mejora reproducible. La generación de poses es un frente independiente:
seis de 47 complejos históricos no tienen ninguna pose <=2 Å.
