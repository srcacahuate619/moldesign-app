"""
Veredicto de selectividad a partir del cociente de energías libres. OBSOLETO.

Se conserva porque hay corridas guardadas cuyo `selectivity_verdict` se escribió
con esta escala, y para poder releerlas sin reinterpretarlas. **No se debe usar
para corridas nuevas.**

El cociente ΔG_on / ΔG_off que recibe no es una razón de selectividad: es un
cociente de energías libres, sin sentido termodinámico. Daba el mismo 2.00 —y
por tanto el mismo veredicto— a un margen de 5 kcal/mol y a uno de 3, que se
diferencian por un factor de treinta en selectividad real, y se indefinía justo
cuando la molécula no se unía a la anti-diana, que es el mejor caso posible.

Para código nuevo: `services/docking/selectividad_margen.py::veredicto_de_margen`,
que trabaja sobre ΔΔG en kcal/mol y define UNA escala compartida con el frontend.
"""

from __future__ import annotations


def selectivity_verdict(ratio: float | None) -> str:
    """Escala heredada. Sólo para releer veredictos ya guardados."""
    if ratio is None:
        return "Sin datos suficientes"
    if ratio > 10:
        return "ALTAMENTE SELECTIVO - Excelente perfil de seguridad"
    if ratio > 3:
        return "SELECTIVO - Buen margen terapeutico"
    if ratio > 1.5:
        return "MODERADAMENTE SELECTIVO - Monitorear off-targets"
    if ratio > 1.0:
        return "BAJA SELECTIVIDAD - Riesgo de efectos secundarios"
    return "NO SELECTIVO - La molecula prefiere anti-targets. ALTO RIESGO"
