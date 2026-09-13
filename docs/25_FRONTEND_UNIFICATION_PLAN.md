# Plan de Unificación Frontend PRO + Hallmark + LoadingOrb

**Fecha**: Julio 2026  
**Estado**: Activo  
**Branch base**: `frontend/unify-pro`

---

## Decisiones de dirección

| Decisión | Detalle |
|----------|---------|
| **Modo único** | Unificar EDU/PRO en una sola experiencia **PRO** con toda la complejidad visible por defecto. |
| **Hallmark** | Instalar como skill en opencode (`~/.config/opencode/skills/hallmark/`) para aplicar reglas anti-slop al generar/rediseñar componentes. |
| **LoadingOrb (Orbs)** | Replicar la animación "thinking orbs" como componente propio React/CSS (`components/ui/LoadingOrb.tsx`) sin dependencia externa. |
| **Dependencias** | Sin límites — agregar lo necesario para que la app Windows sea profesional y de calidad. |

---

## Estado actual (hallazgos concretos)

- **Stack**: Next 14 App Router + Tailwind v4 + React 18.3 + framer-motion + lucide-react + three.js/molstar/ketcher + Tauri.
- **Tema tokenizado** en `app/globals.css:73‑100` (`--bg`, `--text`, `--accent`, `--accent-strong`, `--color-surface-*`, `--color-brand-*`) + `.light`/`.dark` + view-transitions.
- **Modo EDU/PRO** controlado por `context/InterfaceContext.tsx` (`interfaceMode: "GAMIFIED" | "PRO"`, toggle persistido en `localStorage`). Consumer principal: `Navigation.tsx:64‑83` y condicionales en `app/evaluation/page.tsx`.
- **Componentes PRO gigantes**: `ProEvaluation.tsx` (94 KB, 1736 líneas), `ProMoldex.tsx` (46 KB), `ProResults.tsx` (37 KB), `ProSelectivityPanel.tsx` (26 KB), `AdvancedMolstarViewer`/`SelectivityModal`/`CustomReceptorModal` (~20 KB c/u).
- **Carga actual**: `ProgressBar.tsx` (barra gradiente simple), `ui/Skeleton.tsx` (pulse gris), `ui/ScoreGauge.tsx` (SVG), spinners ad-hoc (`animate-spin` en fallbacks `dynamic(... loading: ...)`).
- **Colores hardcodeados**: `#0a0a0a`, `bg-zinc-800`, `bg-[#0a0a0a]`, `#22c55e`, `#3b82f6`, `#8b5cf6` dispersos (Navigation, ProgressBar, ScoreGauge, evaluation page) conviviendo con tokens CSS.
- **Rutas**: `/` (landing), `/evaluation`, `/evaluation/batch`, `/moldex`, `/login`, `/history`, `/launcher`. API por defecto `http://localhost:8010` (`lib/config.ts`).
- **Providers anidados** en `app/layout.tsx:84‑104`: Wallet → Auth → Theme → Language → Interface → AI, con `<ChatPanel/>` global.

---

## Plan de ejecución (7 fases)

### Fase 0 — Auditoría fina y baseline (1 día)
- [ ] Grep exhaustivo de `useInterface`, `interfaceMode`, `GAMIFIED`, `animate-spin`, `animate-pulse`, `setLoading`, `dark:bg-[#0a0a0a]`, colores hex hardcodeados → tabla `archivo:línea`.
- [ ] Capturar screenshots de pantallas actuales (landing, evaluation EDU, evaluation PRO, batch, login, moldex, history) como baseline visual.
- [ ] Crear branches: `frontend/unify-pro`, `frontend/loading-orb`, `frontend/design-system`, `frontend/hallmark-redesign`.

### Fase 1 — Setup Hallmark skill + consolidación design system (2 días)
- [ ] Instalar Hallmark: `npx skills add nutlope/hallmark` (copia `SKILL.md` + `references/` a `~/.config/opencode/skills/hallmark/`).
- [ ] Cargar skill en sesiones de rediseño. Usar verbo `audit <target>` sobre `evaluation/page.tsx`, `Navigation.tsx`, `ProEvaluation.tsx` para obtener punch-list de anti-patrones.
- [ ] Consolidar tokens: mapear todos los colores hardcodeados a `--color-surface-*` / `--color-brand-*` / `var(--accent)`. Definir escalas tipográfica, radio, shadow consistentes.
- [ ] Crear `components/ui/primitives.tsx` (Button, Card, Badge, Tabs, Modal, Field) consumiendo tokens — reemplaza clases Tailwind dispersas.
- [ ] Confirmar paleta: marca actual púrpura (`--color-brand-500: #7c3aed`, `--accent: #8c7a99`). ¿Mantenemos púrpura o cambiamos identidad antes de variantes Hallmark?

### Fase 2 — Unificación EDU/PRO (3‑4 días)
- [ ] Eliminar `context/InterfaceContext.tsx` y el toggle de `Navigation.tsx:64‑83` (desktop y mobile).
- [ ] Reescribir `app/evaluation/page.tsx` para que **siempre** renderice el flujo PRO (estado levantado → props de `ProEvaluation`).
- [ ] Migrar lógica de carga de targets, validación, submit, polling y handlers del flujo EDU al flujo unificado. Usar `context/EvaluationContext.tsx` para evitar pasar 20+ props a `ProEvaluation`.
- [ ] Borrar/archivar componentes del flujo EDU huérfanos (identificados en Fase 0).
- [ ] Actualizar `app/layout.tsx` quitando `<InterfaceProvider>`.
- [ ] Limpiar `localStorage.removeItem("moldesign_interface_mode")` con migration script en `app/layout.tsx` (head inline) para usuarios previos.
- [ ] Actualizar textos/labels que digan "Modo PRO" como si fuera opcional → ahora es simplemente "Evaluación".

### Fase 3 — Componente `LoadingOrb` (Orbs) y reemplazo de loaders (1‑2 días)
- [ ] Inspeccionar `https://orbs.jakubantalik.com/` (view-source) para replicar la animación: orbes flotantes con blur, gradientes, movimiento cíclico (CSS keyframes + framer-motion opcional).
- [ ] Crear `components/ui/LoadingOrb.tsx` con props: `size`, `tone` (mapea a `--accent`/`--brand`), `label`, `progress?`, `indeterminate?`. Variantes: `orb` (pensante), `bar` (lineal decorativa), `ring` (radial).
- [ ] Reemplazar:
  - `ProgressBar.tsx` → `<LoadingOrb variant="bar" progress={pct} />`.
  - Fallbacks `dynamic(... loading: ...)` de `ProEvaluation`, `PDFReportViewer`, `AdvancedMolstarViewer`, `TechNetwork3D` → `<LoadingOrb variant="orb" />`.
  - `ui/Skeleton.tsx` con versión "shimmer" alineada al orb.
  - `ScoreGauge` → opcionalmente rediseñar como ring animado (`LoadingOrb variant="ring"`).
- [ ] Mapear todos los `animate-spin`/`animate-pulse`/`spinner` a la nueva familia visual.

### Fase 4 — Refactor de componentes gigantes + extracción (2‑3 días)
- [ ] `ProEvaluation.tsx` (1736 líneas): extraer sub-componentes ya existentes (`TargetSelector`, `DockingConfig`, `PipelinePanel`, `ResultsTabs`, `ActionsBar`) a `components/interfaces/evaluation/`. Mover `SHAP_EXPLANATIONS` (`ProEvaluation.tsx:34‑78`) a `lib/shap-explanations.ts`.
- [ ] `evaluation/page.tsx` (1465 líneas): mover estado a `context/EvaluationContext.tsx` y dejar página como orquestador thin.
- [ ] `ProMoldex.tsx` / `ProResults.tsx` / `ProSelectivityPanel.tsx`: extraer tablas, gráficos y cards a piezas pequeñas y componerlas.
- [ ] Evaluar `react-window`/`@tanstack/react-virtual` para tablas largas (history, batch, SARTable).
- [ ] Meter `useTransition`/`useDeferredValue` en cambios de tab y filtros pesados.

### Fase 5 — Rediseño visual con Hallmark (3‑4 días)
- [ ] Aplicar Hallmark skill para generar macroestructura nueva (no color-swap) para: landing (`app/page.tsx`), evaluation unificado, batch, login y moldex.
- [ ] Hallmark: 57 slop-test gates — exigir tipografía no-Inter por defecto, espaciado no "centrado vertical", evitar gradientes morados genéricos, bordes 2xl/3xl saturados.
- [ ] Integrar resultado como componentes React + Tailwind v4 respetando tokens de Fase 1. Si la skill propone HTML/CSS suelto, portar a TSX.
- [ ] Reemplazar `TechNetwork3D` (Three.js pesado, `dynamic` SSR off) por alternativa más liviana o mantener evaluando bundle.
- [ ] Unificar iconografía (lucide-react `strokeWidth=1.5` consistente) y micro-interacciones con framer-motion (motion variants compartidas en `lib/motion.ts`).

### Fase 6 — Accesibilidad, performance y quality gates (2 días)
- [ ] Modales: focus trap, `role="dialog"`, `aria-modal`, Escape, restore-focus. Aplicar a `TargetSelectorModal`, `CertificationModal`, `AboutModal`, `TermsModal`, `AISettingsModal`, `CustomReceptorModal`. (`SelectivityModal` se retiró el 2026-09-02: era un duplicado sin usar.)
- [ ] Contraste: revisar `text-muted`/`text-dim` sobre `--bg` (WCAG AA). Validar con axe.
- [ ] Bundle: `next build` + analyzer; lazy-importar Ketcher/Molstar/Three solo en la ruta que los usa. Budget: main ≤ 200 KB gz (sin viz 3D).
- [ ] Tests: instalar Vitest + React Testing Library para UI primitivos y `LoadingOrb`. Añadir Storybook (opcional) para aislar visualmente.
- [ ] Lighthouse CI en build Tauri: objetivo performance ≥ 90, accesibilidad ≥ 95 en desktop.

### Fase 7 — Packaging Tauri (Windows) y QA (1‑2 días)
- [ ] Verificar `src-tauri/tauri.conf.json` (ventana, CSP, bundle Windows, íconos).
- [ ] Probar app empacada: sidecars (`localhost:8010` backend, `:8100` ESMFold), comportamiento offline, zoom (`data-zoom` para Steam Deck), `LoadingOrb` fluido a 60fps en hardware de consumo (GTX 1660).
- [ ] Smoke test flujo completo: login → evaluation (PRO unificado) → docking → resultados → batch → history.
- [ ] Documentar en `docs/` el nuevo design system y cómo usar `LoadingOrb` + Hallmark skill.

---

## Entregables

- `context/InterfaceContext.tsx` eliminado y toggle removido de Navigation.
- `app/evaluation/page.tsx` unificado PRO con estado en `EvaluationContext`.
- `components/ui/LoadingOrb.tsx` + variantes, reemplazando loaders viejos.
- `components/ui/primitives.tsx` (Button/Card/Tabs/Modal/Field) + tokens consolidados.
- Hallmark skill instalada en `~/.config/opencode/skills/hallmark/`.
- Rediseño de landing/evaluation/login con macroestructura Hallmark.
- Refactor de `ProEvaluation` en piezas < 300 líneas c/u.
- Vitest + axe + Lighthouse CI configurados.

---

## Cronograma sugerido (≈ 2 semanas)

| Día | Fase | Qué se logra |
|-----|------|--------------|
| 1 | 0 | Auditoría fina + baseline visual |
| 2‑3 | 1 | Hallmark skill instalada + design system consolidado |
| 4‑7 | 2 | Unificación EDU→PRO (incluye `EvaluationContext`) |
| 8‑9 | 3 | `LoadingOrb` y reemplazo de loaders |
| 10‑12 | 4 | Refactor de `ProEvaluation`/page |
| 13‑16 | 5 | Rediseño con Hallmark |
| 17‑18 | 6 | a11y + performance + tests |
| 19‑20 | 7 | Tauri packaging + QA final |

---

## Riesgos / tradeoffs

| Riesgo | Prob. | Impacto | Mitigación |
|--------|-------|---------|------------|
| Unificar EDU/PRO rompe UX de usuarios actuales | Media | Alto | Documentar cambio; añadir "modo guiado" opcional dentro del PRO (onboarding/tours). |
| Replicar Orbs sin licencia clara | Baja | Medio | Implementar animación inspirada con código propio, no copiar assets. Contactar autor si dudas. |
| Hallmark como skill consume tokens en sesiones | Media | Bajo | Cargarla solo en Fase 5. |
| Refactor `ProEvaluation` introduce regresiones en docking | Media | Alto | Mantener tests de integración de API (`lib/api.ts`) y smoke test manual tras cada extracción. |

---

## Próximos pasos inmediatos

1. Crear branch `frontend/unify-pro` y commitear este plan.
2. Ejecutar Fase 0 (auditoría fina + screenshots baseline).
3. Instalar Hallmark skill y ejecutar `audit` sobre componentes críticos.
4. Iniciar Fase 1 (consolidación tokens + primitives).