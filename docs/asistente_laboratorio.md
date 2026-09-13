> **Documento histórico — julio de 2026.** Escrito para el árbol anterior del
> proyecto (`moldesign-app`) y traído aquí por trazabilidad. Puede describir un
> estado que ya no es el vigente: la versión 1.0.0 es una aplicación de
> escritorio y no tiene componente en la nube. No se ha reescrito su contenido.

# MolChat — Asistente de Laboratorio Inteligente

> **Documento vivo**. Arquitectura, capacidades y roadmap del asistente de
> laboratorio más avanzado para drug discovery asistido por IA.
>
> **Versión**: Julio 2026 | **Estado**: Pre-producción — generación de análogos integrada

---

## Índice

1. [Visión](#1-visión)
2. [Arquitectura del sistema](#2-arquitectura-del-sistema)
3. [Herramientas disponibles](#3-herramientas-disponibles)
4. [Generación de Análogos — BRICS Engine](#4-generación-de-análogos--brics-engine)
5. [MolChamb — Features Cuánticas](#5-molchamb--features-cuánticas)
6. [Pipeline de Scoring Integrado](#6-pipeline-de-scoring-integrado)
7. [Optimización de Tokens](#7-optimización-de-tokens)
8. [Propiedad Intelectual](#8-propiedad-intelectual)
9. [Roadmap del Asistente](#9-roadmap-del-asistente)
10. [Métricas de Uso](#10-métricas-de-uso)

---

## 1. Visión

MolChat no es un chatbot genérico con acceso a GPT. Es un **asistente de
laboratorio inteligente** que entiende química medicinal, puede ejecutar
experimentos computacionales (docking, scoring, generación de moléculas),
y explica sus decisiones en lenguaje natural.

### ¿Qué lo hace único?

| Capacidad | ChatGPT/GPT-4 | MolChat |
|-----------|:---:|:------:|
| Docking molecular (Vina) | ❌ | ✅ ~6s/mol |
| Scoring ML (XGBoost + CL-GNN) | ❌ | ✅ ~0.1s/mol |
| Features cuánticas (MolChamb) | ❌ | ✅ ~0.1s/mol |
| Generación de análogos (BRICS) | ❌ | ✅ ~1s/mol |
| ADME/Tox prediction | ❌ (solo tablas) | ✅ ~3s/mol |
| Early Exit (no waste) | ❌ | ✅ 0% FN |
| 100% offline | ❌ | ✅ GTX 1660 SUPER |
| Fragmentación química real | ❌ (alucina SMILES) | ✅ BRICS + Murcko |
| Scaffold hopping químico | ❌ (inventa) | ✅ Fragment library real |

### Analogía

ChatGPT es un estudiante de química que leyó Wikipedia. MolChat es un **químico
medicinal senior con acceso al laboratorio**. No solo sabe teoría — ejecuta,
mide, y explica.

---

## 2. Arquitectura del sistema

```
Usuario: "generame 20 analogos del hit y rankealos por afinidad"
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ MolChat (Qwen2.5-1.5B / Claude / Gemini / Ollama)               │
│                                                                 │
│ 1. Interpreta intención: "generate_analogs + score"             │
│ 2. Decide herramientas: 🛠️ generate_analogs | smiles=...        │
│ 3. Recibe resultados: 15 análogos con QED/SA/scaffold           │
│ 4. Explica: "El top analog reemplaza el éster por cetona,       │
│    baja logP 0.5 y mantiene afinidad. Sintetizable en 3 pasos." │
└─────────────────────────────────────────────────────────────────┘
    │                    │                    │
    ▼                    ▼                    ▼
┌──────────┐    ┌──────────────┐    ┌─────────────────┐
│ BRICS    │    │ Property     │    │ Scoring Pipeline │
│ Engine   │    │ Filters      │    │ Vina+XGB+CLGNN+ │
│          │    │ QED,SA,Lipin │    │ MolChamb        │
└──────────┘    └──────────────┘    └─────────────────┘
    │                    │                    │
    ▼                    ▼                    ▼
┌──────────────────────────────────────────────────────────────────┐
│ AnalogGenerator.generate()                                       │
│                                                                  │
│ 1. BRICS decompose hit → scaffold + substituents                 │
│ 2. Fragment library lookup → alternative cores/subs (2,756 frag) │
│ 3. Recombine + validate → 100-500 candidates                     │
│ 4. Filter → QED≥0.2, SA≤6, 100≤MW≤600                           │
│ 5. Rank → QED + SA + diversity → top N                          │
│ 6. (Optional) Score → Vina+XGB+CLGNN+MolChamb → final rank      │
└──────────────────────────────────────────────────────────────────┘
```

---

## 3. Herramientas disponibles

MolChat puede invocar herramientas especializadas que ejecutan código real,
no generan texto inventado.

### 3.1 Herramientas de Química Computacional

| Tool | Categoría | Descripción | Tiempo |
|------|:---------:|-------------|:------:|
| `compute_properties` | chem | MW, LogP, TPSA, HBD, HBA, rings | 0.01s |
| `validate_smiles` | chem | Validación y canonicalización | 0.01s |
| `check_druglikeness` | chem | Lipinski, Veber, PAINS | 0.01s |
| `compare_molecules` | chem | Comparación A/B de propiedades | 0.01s |

### 3.2 Herramientas de Docking & Scoring

| Tool | Categoría | Descripción | Tiempo |
|------|:---------:|-------------|:------:|
| `run_docking` | docking | Docking molecular (Vina) | 30-60s |
| `get_rescoring` | docking | XGBoost + CL-GNN scoring | 0.5s |
| `predict_admet` | admet | BBB, HIA, hepatotox, PPB | 3-5s |

### 3.3 Herramientas de Knowledge Graph

| Tool | Categoría | Descripción | Tiempo |
|------|:---------:|-------------|:------:|
| `query_molgraph` | molgraph | Búsqueda en grafo de conocimiento | 0.1s |
| `molgraph_neighbors` | molgraph | Moléculas relacionadas | 0.1s |
| `molgraph_similar` | molgraph | Búsqueda por Tanimoto | 0.3s |
| `molgraph_impact` | molgraph | SAR: qué modificaciones mejoraron | 0.2s |
| `molgraph_scaffolds` | molgraph | Series químicas por fingerprint | 0.3s |

### 3.4 Herramientas de Generación (ANALOG) — NUEVAS

| Tool | Categoría | Descripción | Tiempo |
|------|:---------:|-------------|:------:|
| `generate_analogs` | analog | Scaffold hopping + substituent swap + BRICS | 1-2s |
| `explain_fragments` | analog | Scaffold Murcko + BRICS decomposition + props | 0.1s |
| `run_mmgbsa` | docking | MM-GBSA con cargas MolChamb (GFN2-xTB) | 30-300s |

### 3.5 Herramientas Web (requieren internet)

| Tool | Categoría | Descripción |
|------|:---------:|-------------|
| `pubchem_lookup` | web | Datos experimentales de PubChem |
| `chembl_activity` | web | Bioactividad de ChEMBL |

---

## 4. Generación de Análogos — BRICS Engine

### 4.1 ¿Qué es BRICS?

**BRICS** = **B**reaking of **R**etrosynthetically **I**nteresting **C**hemical
**S**ubstructures (Degen et al., JCIM 2008).

Fragmenta moléculas en puntos de retrosíntesis lógica — los mismos enlaces que
un químico orgánico rompería para sintetizar.

16 reglas de fragmentación: ésteres (R1), amidas (R2), éteres (R3), aminas (R4),
iminas (R5), anillos aromáticos (R6-R16), etc.

### 4.2 Fragment Library

Construida a partir de:
- Activos de ChEMBL (5-HT1A, CDK2, HIV-proteasa)
- Decoys DUD-E propiedad-matched
- **2,756 fragmentos**: 1,023 cores + 1,733 sustituyentes

Top cores: fenilo (freq=180), linker propil (166), aminopirimidina (164), amida (125)

Top sustituyentes: fenil (440), acetil (313), dimetilamino (309), tert-butil (262)

### 4.3 Estrategias de generación

| Estrategia | Descripción | Análogos típicos |
|-----------|-------------|:----------------:|
| `scaffold_hop` | Mantiene sustituyentes, cambia el core | 5-20 |
| `substituent_swap` | Mantiene el core, cambia sustituyentes | 10-50 |
| `diversity` | BRICS recombination individual | 3-15 |
| `all` | Las 3 combinadas | 10-60 |

### 4.4 Ejemplo real

**Hit**: Aspirina `CC(=O)Oc1ccccc1C(=O)O`

```
BRICS decomposition:
  Core:  c1ccccc1 (benceno)
  Frags: [3*]Oc1ccccc1[16*], [6*]C(=O)O, [1*]C(=O)C

Análogos generados:
  1. CC(=O)Cc1ccccc1C(=O)O     Éster → cetona-CH2 (QED=0.76, SA=4.5)
  2. CN(C)Cc1ccccc1C(=O)O      Éster → N-dimetil-CH2 (QED=0.76, SA=5.7)
  3. CC(=O)c1ccccc1C(=O)O      Éster → cetona directa (QED=0.68, SA=4.5)
```

Cada análogo es químicamente válido, sintetizable, y filtrado por drug-likeness.

---

## 5. MolChamb — Features Cuánticas

Ver documentación completa en [metricas_experimentales.md §17](metricas_experimentales.md#17-molchamb--features-cuánticas-propias)
y [datos_para_paper.md §13](datos_para_paper.md#13-molchamb--tecnología-propia-de-features-cuánticas).

En el contexto del asistente:
- MolChat puede invocar MolChamb para **explicar la química electrónica** de un hit
- "¿Por qué este análogo es mejor?" → MolChamb muestra que las cargas parciales
  están mejor alineadas con el pocket del receptor
- HIV-proteasa: MolChamb + stacking → EF@1% 20.1x → **35.9x** (+79%)

---

## 6. Pipeline de Scoring Integrado

Cuando el usuario pide evaluar un análogo, MolChat puede ejecutar el pipeline completo:

```
SMILES → Vina docking → XGBoost classifier → CL-GNN inference → MolChamb Score
                                                                    │
                              ┌─────────────────────────────────────┘
                              ▼
                     Stacking (per-family weights)
                              │
                              ▼
                     ScoreBreakdown (24 campos)
                              │
                              ▼
                     MolChat: "Afinidad: -8.5 kcal/mol, Score: 82/100,
                               CL-GNN: 0.87, MolChamb: 0.52.
                               ADME: BBB+, HIA+, hepatotox-.
                               Conclusión: LEAD candidate."
```

---

## 7. Optimización de Tokens

MolChat usa un LLM local (Qwen2.5-1.5B, 8K context). Cada tool definition
consume tokens del system prompt. Optimizaciones implementadas:

### 7.1 Descripciones comprimidas

| Tool | Verbose (chars) | Slim (chars) | Ahorro |
|------|:---:|:---:|:------:|
| `generate_analogs` | 287 | 84 | -71% |
| `explain_fragments` | 235 | 81 | -66% |
| **Total analog tools** | **522** | **165** | **-68%** |

### 7.2 Activación por query

Las tools "analog" solo se incluyen en el system prompt cuando el usuario
menciona palabras clave relevantes:

```
Keywords: analog, derivado, modific, scaffold, fragment, brics, receta,
          genera, crea, inventa, nuev, optimiz, mejora, cambia, sustitu,
          reemplaza
```

| Escenario | Query | Tokens analog | Acción |
|-----------|-------|:---:|--------|
| "generame analogos" | Match | 74 | Tools incluidas |
| "que pesa la aspirina" | No match | 0 | Tools excluidas |

### 7.3 Presupuesto total de tokens

| Escenario | Tools base | + Analog (match) | Total aprox |
|-----------|:---:|:---:|:---:|
| Propiedades / docking | ~850 | 0 | ~1,550 |
| Generación de análogos | ~850 | ~74 | ~1,624 |
| **Ahorro vs pre-optimización** | — | **-178 tokens (-71%)** | **-178 tokens (-10%)** |

---

## 8. Propiedad Intelectual

### 8.1 ¿Qué es tecnología propia?

| Componente | Estado | Tipo de protección |
|-----------|:------:|:-------------------|
| **Fragment library (2,756 frags)** | Propio | Trade secret — curación y clasificación de BRICS fragments desde ChEMBL + DUD-E |
| **Estrategias de generación** (scaffold hop, substituent swap, diversity) | Propio | Trade secret — combinación y parámetros de las 3 estrategias |
| **Fórmula de ranking** (QED + SA + diversidad) | Propio | Trade secret |
| **Integración MolChat + AnalogGenerator** (query-based activation, "receta") | Propio | Trade secret — arquitectura del asistente |
| **BRICS Engine** (RDKit) | Open source | BSD license |
| **Murcko Scaffold** (RDKit) | Open source | BSD license |
| **QED, SA Score, Lipinski** (RDKit) | Open source | BSD license |
| **MolChat LLM** (Qwen2.5-1.5B) | Open source | Apache 2.0 |

### 8.2 Modelo de negocio

```
OPEN SOURCE (MIT)                    TRADE SECRET
─────────────────                    ────────────
- BRICS Engine wrapper               - Pesos de estrategias
- Fragment library format            - Biblioteca de 2,756 fragmentos
- AnalogGenerator API                - Curación de datos (qué datasets usar)
- MolChat tool interface             - Fórmula de ranking
- explain_fragments                  - Umbrales de filtro (QED≥0.2, SA≤6)
- "Receta" — explicación de análogos - Activación por query (keywords)
```

**Estrategia**: La comunidad académica puede clonar el pipeline (código abierto).
Pero la **biblioteca de fragmentos curada** y los **parámetros de las estrategias**
son el diferencial competitivo. Sin ellos, los análogos generados son químicamente
válidos pero clínicamente irrelevantes.

### 8.3 Estado de la tecnología

| Fase | Hito | Estado |
|:----:|------|:------:|
| 1 | Fragment library (BRICS from ChEMBL + DUD-E) | ✅ Hecho |
| 2 | AnalogGenerator (3 estrategias + filtros) | ✅ Hecho |
| 3 | MolChat tool integration (generate_analogs + explain_fragments) | ✅ Hecho |
| 4 | Token optimization (slim + query-based) | ✅ Hecho |
| 5 | Scoring pipeline integration (Vina + XGB + CLGNN + MolChamb) | 🔲 Pendiente |
| 5.1 | MolChamb v2 MM-GBSA via pose dockeada | 🔲 Pendiente |
| 6 | "Receta" explicativa (LLM explica cada análogo) | 🔲 Pendiente |
| 7 | MolGraph hybrid (retrieval + generation) | 🔲 Pendiente |
| 8 | R-group enumeration (scaffold hopping real) | 🔲 Pendiente |

---

## 9. Roadmap del Asistente

### Fase 1 — Asistente de Análisis (HOY)
- [x] Docking + scoring interactivo
- [x] Propiedades fisicoquímicas
- [x] ADME/Tox prediction
- [x] MolGraph knowledge queries
- [x] Generación de análogos (BRICS)
- [x] Explicación de fragmentación

### Fase 2 — Asistente de Diseño (PRÓXIMO)
- [ ] Scoring de análogos con pipeline completo
- [ ] MolChamb v2 MM-GBSA integrado (top-200, GPU)
- [ ] "Receta" explicativa por análogo
- [ ] MolGraph hybrid: retrieval + generation
- [ ] Scaffold hopping real (R-group enumeration)
- [ ] Bioisostere knowledge base

### Fase 3 — Asistente Autónomo (FUTURO)
- [ ] Diseño de novo multi-objetivo (afinidad + ADME + sintetizabilidad)
- [ ] Planificación de síntesis (retrosíntesis)
- [ ] Aprendizaje activo: sugiere qué molécula dockear después
- [ ] Reporte automático de campaña de screening
- [ ] Integración con LIMS (laboratory information management)

---

## 10. Métricas de Uso

### 10.1 Velocidad de respuesta

| Operación | Tiempo típico | Modo |
|-----------|:---:|------|
| Propiedades (compute_properties) | 0.01s | Instantáneo |
| Explicar fragmentación | 0.1s | Instantáneo |
| Generar 20 análogos (sin scoring) | 0.7-1.5s | Rápido |
| Generar 20 análogos + scoring pipeline | 30-60s | Lento (Vina docking) |
| Docking + scoring completo | 10-30s | Moderado |
| Early Exit (cold start) | <0.1s | Instantáneo |

### 10.2 Eficiencia de tokens

| Métrica | Sin optimizar | Optimizado | Mejora |
|---------|:---:|:---:|:---:|
| Analog tools (system prompt) | 356 | 74 | **-79%** |
| System prompt total | ~1,906 | ~1,624 | **-15%** |
| Contexto libre para conversación | ~6,300 | ~6,600 | **+5%** |

---

## Apéndice A: Comandos de referencia

```powershell
# Probar generación de análogos
cd D:\moldesign-app
python -c @"
import sys; sys.path.insert(0,'backend')
from services.chemistry.analog_generator import AnalogGenerator, AnalogStrategy
from services.chemistry.fragment_library import get_fragment_library
from pathlib import Path

data_dir = Path('data')
chembl = [str(f) for f in data_dir.glob('chembl_*_actives.txt')] + [str(f) for f in data_dir.glob('multitarget/*/actives.txt')]
decoys = [str(f) for f in data_dir.glob('multitarget/*/decoys.smi')]
lib = get_fragment_library(chembl_files=chembl, decoy_files=decoys, force_rebuild=True)
gen = AnalogGenerator(fragment_library=lib)

c = gen.generate('CC(=O)Oc1ccccc1C(=O)O', n_analogs=10, strategy=AnalogStrategy.ALL)
for cand in c:
    print(f'{cand.smiles:50s} QED={cand.qed:.2f} SA={cand.sa_score:.1f}')
"@

# Probar MolChat tool (async)
python -c @"
import sys, asyncio; sys.path.insert(0,'backend')
from services.ai.tools.analog_tools import register_analog_tools, generate_analogs
register_analog_tools(verbose=False)
result = asyncio.run(generate_analogs('CC(=O)Oc1ccccc1C(=O)O', n='5'))
print(result[:500])
"@
```

---

## Changelog

| Fecha | Cambio |
|-------|--------|
| 2026-07-05 | Documento inicial: arquitectura completa del asistente |
| 2026-07-05 | MolChamb v2.0 MM-GBSA añadido a herramientas y roadmap fase 2 |
