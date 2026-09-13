"""
services/diffdock/__init__.py

Servicio de integración con DiffDock — docking basado en deep learning.

DiffDock (Corso et al., ICLR 2023) es un modelo generativo de difusión
para molecular docking que opera de manera fundamentalmente diferente a
AutoDock Vina:

- Vina: optimiza una función de scoring empírica mediante búsqueda estocástica
- DiffDock: muestrea poses directamente de una distribución aprendida

Ventajas científicas de DiffDock sobre Vina:
- Mejor rendimiento en benchmarks recientes (PDBBind, CASF)
- No requiere definir grid box (busca sitio de binding global)
- Mejor para blind docking (cuando no se conoce el sitio activo)
- Proporciona scores de confianza por pose

Limitaciones de DiffDock (transparencia científica):
- Modelo entrenado en PDBBind — posible overfitting a ciertos tipos de targets
- Requiere GPU para inferencia rápida (CPU es ~100x más lento)
- No es un oráculo — ambos métodos son aproximaciones computacionales
- Para la versión actual, requiere servicio externo (API) o GPU local

Estrategia de integración:
  DiffDock se ejecuta como servicio complementario a Vina, no como reemplazo.
  Cuando ambos están disponibles, los resultados se comparan y se reportan
  AMBOS para validación cruzada. Nunca se promedian ciegamente.
"""
