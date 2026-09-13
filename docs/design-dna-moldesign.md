# Design DNA — MolDesign Evaluation Results

> Extraído mediante análisis de 6 referencias de diseño científico. Portable para cualquier AI agent (Claude Code, Cursor, Codex, opencode).

---

## Referencias Estudiadas

| # | Referencia | URL | Qué analizamos |
|---|-----------|-----|---------------|
| 1 | **RCSB PDB** (7E2Y) | rcsb.org/structure/7E2Y | Gold standard: cómo mostrar datos de estructura proteína-ligando |
| 2 | **SwissDock** | swissdock.ch | Competencia directa: wizard de docking molecular con 3D interactivo |
| 3 | **ChEMBL** (Compound Cards) | ebi.ac.uk/chembl | Cómo se presenta una ficha de compuesto con bioactividad |
| 4 | **Nature** SAR Figures | nature.com (patrón observado) | Cómo Nature muestra comparativas estructura-actividad en papers |
| 5 | **Schrödinger Maestro** | (referencia conceptual) | UI de diseño molecular industrial: multi-panel workspace |
| 6 | **PyMOL** / MolStar | (referencia conceptual) | Cómo el visor 3D domina el layout científico |

---

## 1. Macrostructure

### Patrón extraído: HERO → DOT → COLUMNS → VERIFY

```
┌─────────────────────────────────────────────────────┐
│  [2D SMILE]                    [3D MOLECULE VIEWER] │  ← siempre visible
│  Ketcher canvas                MolStar interactive  │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌──── HERO ─────┐                                  │
│  │  78.5          │  ← total_score en tamaño XL     │
│  │  Score compuesto│  (único valor que domina)       │
│  │  TIER:       A │  ← badge S/A/B/C/D              │
│  │  Δ vs prev: +2.3│ ← comparación con anterior      │
│  └────────────────┘                                  │
│                                                     │
│  ┌─ DOT (Cómo se calculó) ──────────────────────┐   │
│  │  Vina(-9.4) → XGBoost(0.82) → GNN(0.76)     │   │
│  │  · MM-GBSA: -8.2 kcal/mol (converged ✓)      │   │
│  │  · Family: gpcr · Weights: 0.4/0.4/0.2      │   │
│  └──────────────────────────────────────────────┘   │
│                                                     │
│  ┌─ COLUMNS ───────────┬── COLUMNS ─────────────┐   │
│  │ DRUG-LIKENESS        │ ADMET & VIABILITY       │   │
│  │ ✓ Lipinski  ✓ Veber  │ LogS  -4.2  ████░░     │   │
│  │ ✓ Ghose  ✗ Muegge    │ PPB   low   ██░░░░     │   │
│  │ ✓ Egan  ✓ Fsp3 0.38 │ HIA   ✓     █████░     │   │
│  │ PAINS: ✓ None        │ BBB   ✗     ███░░░     │   │
│  │                       │ Blood score: 82/100     │   │
│  └──────────────────────┴─────────────────────────┘   │
│                                                     │
│  ┌─ XAI ───────────────┬── SELECTIVITY ──────────┐   │
│  │ [SVG: GNN attention] │ hERG:    -6.2 (safe)    │   │
│  │ [Radar: pharmacoph.] │ CYP3A4:  -7.1 (safe)    │   │
│  │ [SHAP: features]     │ 5-HT2B:  -8.9 (risky)   │   │
│  └──────────────────────┴─────────────────────────┘   │
│                                                     │
│  ┌─ VERIFY ─────────────────────────────────────┐   │
│  │  📜 Certificado PDF  │  🔗 Solana Explorer  │   │
│  │  Guardar en Moldex   │  💾 Download Complex  │   │
│  └──────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

### Reglas de macrostructure

1. **Hero numérico**: UN solo valor domina la jerarquía visual (total_score). Nada compite con él. Tamaño ~4rem.
2. **DOT (Diagram of Thought)**: timeline horizontal del pipeline de scoring. 4-5 nodos conectados (Validation → Docking → ML → MM-GBSA → Score). Cada nodo muestra el valor intermedio. Responde "¿cómo llegamos a este score?"
3. **COLUMNAS emparejadas**: pares semánticos lado a lado (Drug-likeness ↔ ADMET, XAI ↔ Selectivity). El ojo compara horizontalmente.
4. **VERIFY footer**: acciones al final, después de que el científico ya entendió qué pasó.
5. **Visores siempre visibles**: el 2D (Ketcher) y 3D (MolStar) ocupan espacio fijo arriba, no colapsan. El científico necesita ver la molécula mientras interpreta los datos.

---

## 2. Type Pairing

### Primaria (Headlines, scores, tier)

```
Font: "Space Grotesk" o "DM Sans"
Weight: 700 (bold)
Uso: total_score, tier badge, títulos de sección
```

Alternativa si no se puede instalar: `Inter` (ya presente) con weight 800.

### Secundaria (Labels, valores métricos)

```
Font: "JetBrains Mono" (ya presente en el proyecto — globals.css:7)
Weight: 400-700
Uso: todos los valores numéricos, identificadores, SMILES, códigos
```

### Terciaria (Texto de apoyo, descripciones)

```
Font: Inter
Weight: 400
Uso: descripciones, tooltips, leyendas
```

### Escala tipográfica

| Rol | Size | Weight | Font |
|-----|------|--------|------|
| Hero score | 4rem (64px) | 800 | Space Grotesk |
| Tier badge | 1.5rem (24px) | 800 | Space Grotesk |
| Section titles | 0.75rem (12px) | 700 | Space Grotesk, uppercase, tracking 0.1em |
| Metric labels | 0.625rem (10px) | 600 | Inter, uppercase, tracking 0.05em |
| Metric values | 0.875rem (14px) | 400 | JetBrains Mono |
| SMILES/IDs | 0.75rem (12px) | 400 | JetBrains Mono |
| Body/captions | 0.75rem (12px) | 400 | Inter |

---

## 3. Colour Anchor

### Primary palette

| Token | Hex | Uso |
|-------|-----|-----|
| `--bg` | `#050508` | Fondo principal (negro profundo) |
| `--surface` | `#0d0e12` | Cards, paneles |
| `--surface-raised` | `#1a1b23` | Cards elevadas, hover states |
| `--text-primary` | `#f8fafc` | Texto principal |
| `--text-secondary` | `#94a3b8` | Labels, metadatos |
| `--text-muted` | `#475569` | Valores inactivos/placeholder |

### Accent (sistema de calidad — NO genérico "morado bonito")

| Tier | Hex | Significado científico |
|------|-----|----------------------|
| S (≥85) | `#f8fafc` (blanco) | Excepcional — candidato clínico potencial |
| A (≥70) | `#a78bfa` (violeta) | Excelente — optimización recomendada |
| B (≥55) | `#60a5fa` (azul) | Bueno — viable con mejoras |
| C (≥40) | `#fbbf24` (ámbar) | Regular — requiere rediseño significativo |
| D (<40) | `#9ca3af` (gris) | Pobre — descartar o rediseñar desde cero |

### Sistema de estados (verde/rojo semántico)

```
✓ Pass / Safe    → #22c55e (emerald-500) — NO genérico "green-500"
✗ Fail / Risk    → #ef4444 (red-500)     — NO genérico "rose-500"
⚠ Warning        → #f59e0b (amber-500)
ℹ Info/Neutral   → #64748b (slate-500)
```

### Regla anti-slop de color

- **NUNCA**: gradientes morados genéricos como decoración de fondo
- **NUNCA**: `bg-gradient-to-r from-purple-500 to-pink-500` (el slop máximo del AI)
- **SIEMPRE**: el color comunica estado — si algo es violeta, es porque tiene un significado (tier A, métrica positiva, o valor activo)
- **REGLA**: ningún elemento decorativo usa color de acento. Solo datos.

---

## 4. Escala espacial

| Token | Valor | Uso |
|-------|-------|-----|
| `--space-xs` | 4px | Gap entre ícono y texto en badges |
| `--space-sm` | 8px | Gap entre métricas en un card |
| `--space-md` | 16px | Gap entre cards, padding interno |
| `--space-lg` | 24px | Gap entre secciones |
| `--space-xl` | 32px | Margen de sección a borde de viewport |
| `--radius-sm` | 6px | Badges, chips |
| `--radius-md` | 10px | Cards |
| `--radius-lg` | 16px | Modales, secciones principales |

---

## 5. Reglas de composición

### R1: No centrado vertical
Ningún card se centra verticalmente en su contenedor. Todo fluye desde arriba. El ojo científico escanea en F-pattern, no en simetría.

### R2: Monospace para lo cuantificable
Todo valor numérico, identificador (PDB ID, SMILES hash, transaction ID), o dato técnico usa `font-mono`. Las descripciones usan `font-sans`.

### R3: Badge-driven scanning
Las reglas de drug-likeness usan badges (✓ verde / ✗ rojo) en vez de texto. El ojo detecta patrones en milisegundos.

### R4: Líneas, no cajas
Los separadores entre cards son líneas finas (`border-white/5`), no shadows pesados. Menos "container", más "documento científico".

### R5: Siempre visible: 2D + 3D
Los visores de molécula (Ketcher 2D + MolStar 3D) ocupan la fila superior y nunca colapsan. El científico necesita ver la estructura mientras interpreta métricas.

### R6: DOT pipeline visible
El "cómo se calculó" es tan importante como el resultado. Un timeline horizontal de nodos conectados muestra Validation → Docking → ML → MM-GBSA → Score con sus valores intermedios.

### R7: El número grande dice todo
El `total_score` es el elemento tipográfico más grande de la página (4rem). Es el ancla visual. Todo lo demás es subordinado.

### R8: Unidad + precisión siempre visibles
`-9.4 kcal/mol` no `-9.4`. `78.5 / 100` no solo `78.5`. Las unidades son parte del valor.

---

## 6. DNA aplicado a las 6 secciones de datos

De la taxonomía de 52 campos, cada sección recibe un tratamiento visual específico:

### Sección 1: Score Principal (5 campos)
- total_score: **4rem, bold**, centrado en su card
- Tier badge: debajo del score, tamaño moderado
- Δ vs molécula anterior (si existe en SAR)
- Timestamp de evaluación
- botón "Ejecutar MM-GBSA" (bajo demanda)

### Sección 2: Pipeline Timeline (4 nodos, 12 campos)
- Nodo Vina → affinity_kcal + vina_version + seed
- Nodo XGBoost → xgb_score + stacking_xgb_weight
- Nodo GNN → gnn_score + clgnn_score + stacking_gnn_weight
- Nodo MM-GBSA → mmgbsa_score + quantum_score + energy_change
- Barra conectora entre nodos (línea fina, color según estado)
- target_family y target_spearman_rho como footnote

### Sección 3: Drug-likeness Grid (12 campos en 4×3 + badge)
- 6 reglas como badges ✓/✗ en grid 2×3
- QED como gauge pequeño (0-1)
- SA Score como barra 1-10 con zonas
- fsp3 como porcentaje
- PAINS como badge (✓ None / ✗ 3 matches)
- rotatable_bonds + ring_count como pares

### Sección 4: ADMET Range Bars (8 campos)
- blood_viability_score como gauge
- Cada métrica ADMET como barra horizontal con rana fisiológica coloreada:
  - Verde: rango seguro
  - Ámbar: borderline
  - Rojo: riesgo
- blood_systemic_reactivity como lista de warnings

### Sección 5: XAI Visualizaciones (5 visualizaciones grandes)
- gnn_attention_svg como imagen SVG full-width
- gnn_pharmacophores como radar chart (ya implementado)
- shap_values como waterfall chart o tabla ordenada
- ai_report como texto colapsable
- scientific_warnings como alertas

### Sección 6: Verificación + Metadatos (10 campos)
- blockchain_tx_id con link a explorer
- selectivity_verdict + ratio (con badge visual)
- anti_target_results en mini-tabla
- vina_version, parsing_source, is_control como footer técnico
- affinity_threshold mostrado como línea de referencia

---

## 7. Referencia de implementación

### Stack ya disponible (NO agregar deps innecesarias)

| Necesidad | Librería | Estado |
|-----------|----------|--------|
| Animaciones | framer-motion | ✅ ya instalado |
| Animaciones de texto | GSAP | ✅ instalado en item anterior |
| Gráficos (radar, barras) | CSS puro + SVG | ✅ sin dep |
| Tipografía mono | JetBrains Mono | ✅ en globals.css |
| Iconos | lucide-react | ✅ ya instalado |
| Visor 3D | MolStar | ✅ ya integrado |
| Editor 2D | Ketcher | ✅ ya integrado |
| Orbs loading | ThinkingOrb.tsx | ✅ creado en item anterior |

---

## 8. Anti-patrones a EVITAR

Extraídos de las 57 reglas de Hallmark + observación directa:

| Anti-patrón | Por qué es malo | Qué hacer en su lugar |
|-------------|----------------|---------------------|
| Cards con `shadow-2xl` y `rounded-3xl` | Parece dashboard SaaS, no herramienta científica | Bordes finos (`border-white/5`), radius moderado (10px) |
| Gradientes púrpura decorativos de fondo | El slop más común de AI. Comunica "genérico", no "preciso" | Fondo sólido `#050508`. Color solo en datos |
| Tipografía Inter por defecto en todo | Inter es la Helvetica de 2024 — genérica, sin carácter | Space Grotesk para headlines, JetBrains Mono para datos |
| Iconos con `strokeWidth={2}` | Se ven gruesos, pesados, "de template" | `strokeWidth={1.5}` consistente en todo lucide-react |
| Texto centrado en cards de datos | El ojo científico escanea en F, no en centro | Alinear labels a la izquierda, valores a la derecha |
| Spinners `animate-spin` como loading | Genérico, no científico | ThinkingOrb (ya implementado) |
| Badges con `bg-purple-500/20 text-purple-300` | Sin significado semántico | Color solo si el dato tiene estado (verde=pass, rojo=fail, ámbar=warn) |
| "Loading..." | Slop textual | "Minimizando energía libre (OpenMM OBC2)..." — específico y científico |
