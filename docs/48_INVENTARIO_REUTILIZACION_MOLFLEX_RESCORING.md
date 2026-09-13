# Inventario de reutilización — MolFlex y rescoring

**Fecha:** 2026-08-15  
**Estado:** auditoría de activos científicos antes de crear descriptores nuevos.  
**Alcance:** mejorar conjuntamente la cobertura de poses de MolFlex y la selección de poses de Ruta C, sin modificar `pose_selector_v06`.

## Dictamen ejecutivo

MolDesign ya contiene los componentes necesarios para el siguiente experimento de alto valor. La prioridad no es crear otra familia genérica de features: es **conectar correctamente generación y selección**.

1. MolFlex puede producir conformeros/poses complementarios para ligandos flexibles, pero Vina no elige de forma fiable la pose cristalina de ese ensemble.
2. Ruta C v0.6 es un selector de conjuntos de poses, pero hasta ahora no se ha validado de forma limpia sobre un conjunto aumentado por MolFlex con la procedencia de cada pose preservada.
3. UMS y FastMolChamb son propiedades del SMILES: para un mismo ligando son constantes entre poses y, por definición, no pueden modificar su ranking intra-complejo.
4. MolChamb/MM-GBSA por pose y ZnCoord sí varían con la geometría; son candidatos a segunda etapa, pero requieren su propia validación de pose-ranking antes de entrar al selector.

La primera prueba reutilizable debe ser **MolFlex → unión de candidatos → selector**, evaluada con `rmsd_pose_pocket`, no una nueva red/GNN ni una reponderación de features existentes.

## Matriz de activos

| Activo existente | Qué aporta | MolFlex | Rescoring | Estado de evidencia | Decisión |
|---|---|---|---|---|---|
| `scripts/molflex.py` | ETKDG, poses rígidas, mapa átomo↔PDBQT, score Vina, relax local | Sí | Entrega candidatos | Cobertura de conformeros: 78% <1.5 Å; selección Vina refutada | **Reutilizar como generador**, nunca como selector final. |
| `scripts/ruta_a_exh_validation.py` | Redock flexible Vina exh 1/2/4 y benchmark estratificado | Fallback de generación | Entrega candidatos | exh=4, no exh=2, fue el mínimo defendible tras corregir RMSD | Reutilizar como fallback controlado; no como atajo barato universal. |
| `molflex.rmsd_pose_pocket` | RMSD pesado, índice a índice, en marco del pocket | Validación | Validación | Corrige el falso RMSD alineado que ocultaba poses a 8–13 Å | **Métrica obligatoria** para toda pose dockeada futura. |
| `rescoring/pose_selector` v0.6 | 233 features relativas por conjunto + XGBRanker | Selecciona conjunto mezclado | Sí | 31/47 Top-1 histórico; estable en producción | Baseline inmutable y primer selector a medir sobre poses MolFlex. |
| `rescoring/feature_extractor.py` | Shell (96), ECIF-lite (56), size/contactos y contrato de extracción | Puede describir poses | Sí | Shell/ECIF son el núcleo que sobrevivió ablaciones | Reutilizar extractor/contrato; no duplicar conteos. |
| ProLIF del extractor | H-bonds, π, salt bridges, metal, por interacción | Auditoría visual | Candidato sólo dirigido | Conteos globales: ruido para afinidad; PDBQT degrada aromaticidad/protonación | No reintroducir conteos globales al ML. |
| `backend/services/chemistry/molchamb_v2.py` | MM-GBSA OpenMM por pose, con cargas xTB/Gasteiger | No genera | Posible cascade top-K | API existe; no hay validación Ruta C de ranking de poses | Probar como scorer de segunda etapa, no feature masiva. |
| `scripts/compute_quantum_features.py` | xTB GFN2 (cargas/energía) y MMFF | Priorización de conformeros | Apoyo a MM-GBSA | xTB es dependiente de binario; fallback/éxito deben auditarse | Reutilizar sólo detrás de un probe reproducible. |
| `scripts/fast_molchamb.py` | Proxy RDKit de carga, logP, MR, TPSA, HBA/HBD | Priorización de moléculas | No intra-pose | Smoke correcto; es SMILES-only | No usar para elegir entre poses; puede ser metadato barato. |
| `scripts/universal_metal_score.py` | SMARTS de seis warheads Zn + prior químico | Priorizar librería metal | No intra-pose | Ablación favorece SMARTS; familia-gated | Usar sólo como prior de ligando para metaloenzimas compatibles. |
| `scripts/zn_coordination_features.py` | Distancia/átomos donadores respecto de Zn | Puede guiar generación metal | Posible scorer de pose | Señal fuerte en CA2; código experimental específico | Extraer funciones y validar para Zn catalítico; no generalizar a otros metales. |

## 1. MolFlex: activo principal para cerrar el lazo

### Lo que sí está listo para reutilizar

`scripts/molflex.py` contiene una cadena útil y concreta:

- `construir_ensemble`: RDKit ETKDG con preferencias torsionales CSD, seed fijo y deduplicación geométrica;
- `escribir_pdbqt`: genera PDBQT flexible y rígido más el mapa de seriales a átomos RDKit;
- `dock_rigido_archivo`: docking Vina por conformero, con soporte de mapas de grid;
- `rmsd_pose_pocket`: métrica de referencia correcta para poses dockeadas;
- `relax_pose_archivo`: relax local de Vina, explícitamente degradable cuando OpenMM/SMIRNOFF no está disponible.

La evidencia útil de [doc. 40](40_MOLFLEX_PROTOCOL.md) es que ETKDG cubre la conformación bioactiva en una fracción relevante de casos y que el score de Vina **no** elige con fiabilidad esa conformación. Esto es complementariedad, no fracaso: MolFlex debe entregar diversidad de poses a un selector especializado.

### Límites que no se deben ocultar

- El relax actual degrada a `vina --local_only`; no resolvió cobertura y no sustituye MD/FF parametrizado.
- El cache de grids se investigó: la hipótesis de que dominaba el tiempo fue refutada; el coste principal sigue siendo la búsqueda Monte Carlo.
- Las features de dispersión del flexible y MolFlex no son intercambiables: en la validación v3, el score primario correlacionó (`rho=0.861`), pero varianza/rango no (`-0.524` / `-0.592`). No se deben inyectar como si provinieran del mismo proceso generativo.
- Toda cifra anterior a la corrección de RMSD de 2026-08-14 debe leerse sólo con la auditoría adjunta: `GetBestRMS` alineaba una pose desplazada y el unpacking podía convertir un dock flexible en rígido.

### Reuso propuesto: experimento E-REUSE-1

**Pregunta:** ¿la unión de poses flexibles/Ruta A y poses MolFlex aumenta la cobertura de pose cristalina y permite a v0.6 seleccionar mejor, sin mezclar métricas incompatibles?

Diseño que se debe preregistrar antes de ejecutar:

1. Usar sólo complejos de `train` para elegir política y `val` una sola vez; el test histórico Ruta C queda sellado.
2. Disparar MolFlex sólo para ligandos de alta flexibilidad o timeout, con su `source`, `conformer_id`, energía/conformero y score Vina guardados como **provenance**, no como features automáticas.
3. Unir las poses por complejo; recalcular features por pose con el extractor v0.6 y las estadísticas relativas sobre el conjunto unido.
4. Medir primero el oráculo de generación: `min(rmsd_pose_pocket) <=2 Å`; después Top-1 del baseline v0.6. Reportar ambos por fuente y por número de enlaces rotables.
5. Gate de generación y gate de selección separados. Una mejora de oráculo no es una mejora de ranking hasta que el selector la capture.

Este experimento reutiliza MolFlex y Ruta C sin fabricar un descriptor nuevo y ataca directamente los seis casos sin candidato cristalino.

## 2. Extractores de rescoring existentes

### Shell, ECIF y features relativas

Los 233 campos de v0.6 ya incluyen las 224 features físicas de Shell/ECIF/código por residuo/contactos y las transformaciones intra-complejo (z-score y rangos). `rescoring/pose_selector/feature_extractor.py` implementa además el contrato de producción equivalente. Éste es el extractor que debe recalcularse sobre un conjunto de poses aumentado; crear otro conteo de distancias antes de medirlo sería duplicación.

El modelo universal de 167 features es un recurso distinto: fue entrenado para afinidad/binder, no para seleccionar la pose cristalina de un mismo complejo. Se puede reutilizar su **implementación de Shell/ECIF** y sus controles de contrato, pero no usar su predicción de pKi como evidencia de pose nativa sin un benchmark nuevo de pose-ranking.

### ProLIF: reutilización restringida

ProLIF ya expone h-bonds, contactos hidrofóbicos, π, puentes salinos y metal. La evidencia en [validación científica](08_SCIENTIFIC_VALIDATION.md) descarta sus **conteos globales** como feature general: score de interacción `rho=-0.035` en 5-HT1A y ablaciones inferiores a Shell/ECIF.

No se reincorpora como vector global. Si un experimento futuro lo usa, debe ser una hipótesis distinta y específica: interacciones con residuos o cofactores previamente definidos para una familia, con química/protonación de entrada verificable. No debe llamarse simplemente “más features físicas”.

## 3. MolChamb y MM-GBSA

Hay tres activos con nombres parecidos que deben distinguirse:

| Componente | Dependencia de pose | Utilidad real para Ruta C |
|---|---|---|
| FastMolChamb (`fast_molchamb.py`) | No; sólo SMILES | Ninguna para Top-1 intra-ligando. |
| xTB/MMFF (`compute_quantum_features.py`) | La implementación actual calcula conformero aislado desde SMILES | Priorización/energía de conformero y cargas, no selección directa de pose. |
| MolChamb v2 MM-GBSA (`compute_mmgbsa_from_pose`) | Sí; usa coordenadas de pose | Candidato real para desempatar top-K. |

`compute_mmgbsa_from_pose` es aprovechable como **cascada C5**, no para puntuar cada pose. Debe recibir un SDF de la pose real (`ligand_sdf_path`) para evitar el histórico de hidrógenos apilados/energías NaN; soporta explícitamente C/H/O/N/S/P y recurre a Gasteiger cuando xTB no entrega cargas.

Hay una ambigüedad que bloquearía una promoción inmediata: tras el fallback, `has_molchamb` puede indicar que existen cargas, no necesariamente que provengan de xTB. El experimento debe registrar `charge_source = xtb | gasteiger`, versión/binario xTB, tiempo por pose, elemento no soportado y energía finita. El directorio `tools/xtb` existe, pero su disponibilidad funcional no se infiere de la existencia de la carpeta.

**E-REUSE-2 posterior:** sobre top-2/top-3 del selector en folds train, comparar Vina/v0.6 frente a MM-GBSA por pose; fijar por adelantado budget de tiempo y política de fallo. Sólo si mejora OOF y `val` podrá actuar como desempate para complejos de margen bajo. No es todavía una mejora demostrada.

## 4. UMS y ZnCoord

[El paper UMS](PAPER_UMS.md) y `data/molchamb_loto/ablation_study.json` respaldan una conclusión estrecha: en metaloenzimas de Zn cubiertas por los seis warheads, el patrón SMARTS domina y MolChamb/donor count no añaden valor estable. Por ejemplo, en el subset LOTO de MMP9 y ACE, `warhead_only` fue 0.9308/0.8002 AUC frente a 0.9061/0.7620 del UMS completo.

- **UMS:** como depende sólo del SMILES, puede priorizar moléculas y activar una rama de metaloenzima; no puede elegir entre sus poses.
- **ZnCoord:** sí es pose-dependiente (distancia a Zn, donadores, presencia de warhead) y obtuvo una señal fuerte en CA2. El script actual está orientado a CA2 y a Zn; se deben extraer/reutilizar sus funciones (`get_zn_coords`, `compute_zn_features`) detrás de validaciones para PDB con múltiples metales, identidad de ion y receptor curado.
- **No generalizar:** no se aplica a GPCR, quinasas, hemo-Fe ni metaloenzimas sin quelación Zn. Fuera de su gate, el paper respalda retorno al baseline.

**E-REUSE-3 posterior:** benchmark de ZnCoord sobre los complejos de Zn de train/val como un scorer de pose separado. No se mezcla con Ruta C general ni se reporta como FEP-ready global.

## 5. Orden científico recomendado

1. **E-REUSE-1, MolFlex→Ruta C:** máxima prioridad; añade candidatos y prueba el enlace generación–selección.
2. **E-REUSE-2, MM-GBSA top-K:** sólo después, si E-REUSE-1 deja fallos de margen bajo con candidatos correctos disponibles.
3. **E-REUSE-3, ZnCoord:** rama separada para receptores Zn compatibles.
4. Sólo si los tres activos no aportan señal, diseñar un descriptor nuevo. En ese caso debe ser direccional/específico y no un conteo global ProLIF renombrado.

## Salvaguardas

- No modificar `pose_selector_v06`, su manifest ni la ruta de producción durante estos experimentos.
- No volver a escoger variantes con el test histórico de 47; crear un holdout confirmatorio antes de cualquier anuncio `>=0.70`.
- Persistir hashes de inputs, binarios y outputs; preservar resultados negativos.
- Reportar siempre: cobertura/oráculo de generación, Top-1 global, Top-1 condicionado a candidato, RMSD en marco del pocket, tiempo y tasa de fallo.

El programa completo de hipótesis, campañas y gates está en
[`49_PROGRAMA_EXPERIMENTAL_CIENTIFICO.md`](49_PROGRAMA_EXPERIMENTAL_CIENTIFICO.md).
