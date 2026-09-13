# ADR 78 — Distribución de pesos y runtime

Estado: decisión vigente desde 2026-09-10.

1. GitHub y el instalador incluyen los modelos propios ligeros necesarios:
   XGBoost/pose selector y los dos artefactos CL-GNN.
2. Cada artefacto debe estar versionado, manifestado y verificado por SHA-256.
3. ESMFold, LLM y otros pesos pesados siguen siendo descargas explícitas.
4. Los modelos propios usan PolyForm Noncommercial 1.0.0; el uso comercial
   exige un acuerdo separado.
5. Las licencias de MolDesign no relicencian material de terceros.

El checkpoint CL-GNN actual se incluye para eliminar la degradación por ausencia
de artefacto. No hereda los AUC externos históricos, que pertenecen a otro
checkpoint. Hasta evaluar y sellar el SHA-256 distribuido, CL-GNN es una señal
experimental con peso cero en el stacking de release.

Resuelto 2026-09-12 (determinación del autor; no es un permiso de terceros). Los
pesos se distribuyen como obra del autor. El dataset PDBbind v2020 se reconoce
como fuente de entrenamiento pero **no se redistribuye** ni en estructuras de
complejos ni en tablas de afinidades. Los artefactos que reproducen afinidades
derivadas (`backend/data/benchmark_pdbbind*.json`, `pocket_dataset*.json`,
`rescoring/artifacts/pdbbind_audit_report.json`) se **excluyen del canal de
distribución**: el empaquetado MSIX los retira del layout en
`scripts/build_msix.py`. La atribución quedó en
`frontend/public/legal/THIRD_PARTY_NOTICES.md`.
