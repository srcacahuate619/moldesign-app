"""
services/denovo/__init__.py

Servicio de generación de novo de moléculas.

La generación de novo usa modelos generativos para sugerir modificaciones
moleculares que podrían mejorar la afinidad, propiedades ADME o drug-likeness.

Estrategia de implementación:
  Fase 1 (actual): Sugerencias basadas en reglas de química medicinal (RDKit)
  Fase 2 (futura): Integración con modelos generativos (REINVENT, MolGPT)

Principios científicos obligatorios:
1. Las sugerencias son HIPÓTESIS computacionales, no verdades comprobadas.
2. Cada sugerencia debe explicar su razonamiento.
3. Nunca se garantiza que una modificación mejorará la actividad biológica.
4. Las sugerencias deben respetar las reglas de química medicinal.
5. El usuario siempre decide si acepta o modifica la sugerencia.
"""
