import math
from core.models import PhysicochemicalProperties


def clamp_score(value: float) -> float:
    """Asegura que cualquier score quede en el rango [0, 100]."""
    return round(max(0.0, min(100.0, value)), 2)


def normalize_affinity(
    affinity_kcal: float,
    heavy_atoms: int | None = None,
    log_p: float | None = None,
    threshold: float = -7.5,
    is_control: bool = False
) -> float:
    """
    Normaliza afinidad usando una función sigmoidea (Curva de Hill) basada en 
    Ligand Efficiency (LE) y validada por Lipophilic Efficiency (LLE).
    
    V6.0 "Scientific Rigor - Potency Floor":
    - LE = affinity / heavy_atoms
    - Sigmoide centrada en LE = -0.30
    - Penalizador por Potencia Absoluta: Si afinidad > threshold, el score cae.
    """
    if not heavy_atoms or heavy_atoms <= 0:
        # Fallback a afinidad absoluta con sigmoide
        mid_abs = threshold
        k_abs = 2.0
        score = 100 / (1 + math.exp(k_abs * (affinity_kcal - mid_abs)))
        return clamp_score(score)

    le = affinity_kcal / heavy_atoms

    # --- [CIENCIA DILUCIDADA] LE de referencia decae fisiológicamente con el tamaño ---
    # Fragmentos pequeños necesitan mayor densidad de energía; ligandos grandes tienen límites de empaquetamiento estérico.
    if heavy_atoms < 15:
        mid_le = -0.42
    elif heavy_atoms > 45:
        mid_le = -0.20
    else:
        # Interpolación lineal entre 15 y 45 átomos pesados
        mid_le = -0.42 + (heavy_atoms - 15) * (0.22 / 30)

    # Adaptive k_le to maintain consistent discriminatory power (Bug #4)
    if heavy_atoms < 15:
        k_le = 20.0
    elif heavy_atoms > 45:
        k_le = 10.0
    else:
        k_le = 20.0 - (heavy_atoms - 15) * (10.0 / 30.0)

    base_score = 100 / (1 + math.exp(k_le * (le - mid_le)))

    # --- PENALIZADOR DE POTENCIA ABSOLUTA OPTIMIZADO ---
    # Si la molécula es más débil que el threshold, se aplica un castigo sigmoideo suave.
    # Si cumple o supera el threshold, no hay penalización (potency_factor = 1.0).
    if affinity_kcal > threshold and not is_control:
        # Continuous linear decay with a 0.5 kcal/mol slack zone (Bug #3)
        slack = 0.5
        if affinity_kcal > threshold + slack:
            excess = affinity_kcal - (threshold + slack)
            potency_factor = max(0.1, 1.0 - (excess * 0.3))
            base_score *= potency_factor

    # ═════════════════════════════════════════════════════════════════════
    # AQUÍ ESTABA EL FACTOR LLE, Y ROMPÍA LA REGLA DE ORO DEL PROPIO MOTOR
    # ═════════════════════════════════════════════════════════════════════
    #
    # `scoring/engine.py` declara en su cabecera:
    #
    #     «REGLA DE ORO v2.0 — DESACOPLAMIENTO DE MÉTRICAS. El ranking de
    #      afinidad (total_score) usa SOLO docking + ML + MM-GBSA. ADME,
    #      Drug-likeness, SA Score y Blood Viability son "flags" de perfil
    #      farmacocinético para el químico medicinal — NUNCA alteran el score
    #      de afinidad.»
    #
    # Y sin embargo esta función recibía `log_p` y hacía:
    #
    #     lle = (-affinity / 1.36) - log_p
    #     if lle < 3.0:  base_score *= max(0.4, lle / 3.0)     # hasta −60 %
    #     elif lle > 7.0: base_score *= 1.05                    # +5 %
    #
    # logP es una propiedad fisicoquímica del perfil farmacocinético: justo lo
    # que la regla dice que no debe tocar la afinidad. El efecto medible es que
    # una molécula lipofílica y potente en docking caía en el ranking de
    # AFINIDAD por ser lipofílica, y el usuario leía una afinidad peor sin que
    # nada dijera que la habían penalizado por otra cosa.
    #
    # La eficiencia lipofílica sigue siendo una métrica valiosa —y se sigue
    # calculando y mostrando— pero en el bloque de propiedades, que es donde el
    # químico medicinal la interpreta junto a su contexto. No dentro del número
    # que dice cuánto se une.
    #
    # `log_p` se conserva en la firma para no romper a los llamadores; ya no
    # modula nada.

    # --- Penalizador por Tamaño ---
    if heavy_atoms < 12:
        size_penalty = (12 - heavy_atoms) * 8.0
        base_score = max(0.0, base_score - size_penalty)

    return clamp_score(base_score)



def calculate_adme_score(properties: PhysicochemicalProperties) -> float:
    """
    Score ADME basado en el perfil de absorción/distribución estimado.

    Compuesto de tres factores:
      - TPSA: penaliza absorción oral pobre (>90Å²) y BBB impenetrable (>120Å²)
      - logP: penaliza lipofilia extrema (<0 o >4.5) que afecta distribución y toxicidad
      - SA Score: penaliza complejidad sintética elevada (>4.0)

    A diferencia del QED (que da un único score holístico de drug-likeness),
    este score captura el perfil ADME de forma más mecánicamente interpretable.

    Rango: 0–100 (100 = perfil ADME ideal)
    """
    score = 100.0

    # 1. Penalización TPSA — absorción oral e intestinal
    tpsa = properties.tpsa
    if tpsa > 120.0:
        # Rango pobre de BBB o absorción oral muy limitada
        score -= min(30.0, (tpsa - 120.0) * 0.75)
    elif tpsa > 90.0:
        # Absorción oral limitada (Veber: TPSA≤140 para biodisponibilidad oral)
        score -= (tpsa - 90.0) * 0.5
    elif tpsa < 10.0:
        # TPSA anormalmente baja (<10 Å²): indica molécula sin grupos polares.
        # Aunque parece "buena" para permeabilidad, en la realidad implica:
        # toxicidad sistémica, sin solubilidad acuosa, y potencial reactividad.
        # Referencia: Ertl et al. J.Med.Chem. 2000 — zona útil TPSA: 20-90 Å²
        score -= min(25.0, (10.0 - tpsa) * 3.0)

    # 2. Penalización logP — lipofilia extrema en ambos sentidos
    log_p = properties.log_p
    if log_p > 4.5:
        # Riesgo de hERG, acumulación en tejido graso, baja solubilidad
        score -= min(25.0, (log_p - 4.5) * 5.0)
    elif log_p < 0.0:
        # Hidrofilia extrema → posible baja permeabilidad celular
        score -= min(15.0, abs(log_p) * 3.0)

    # 3. Penalización SA Score — accesibilidad sintética reforzada
    # SA Score (Ertl & Schuffenhauer 2009): 1=trivial, 10=imposible.
    # Umbral de gracia: SA ≤ 3.5 → sin penalización.
    # SA 3.5–5: penalización progresiva moderada.
    # SA 5–7: penalización significativa (química especializada de alto costo).
    # SA > 7: penalización severa (síntesis no viable para uso terapéutico).
    sa = properties.sa_score
    if sa > 7.0:
        # Síntesis prácticamente inviable o requiere >10 pasos altamente especializados
        score -= min(40.0, 20.0 + (sa - 7.0) * 10.0)
    elif sa > 5.0:
        # Química difícil, viable solo en laboratorio especializado
        score -= min(20.0, (sa - 5.0) * 10.0)
    elif sa > 3.5:
        # Complejidad moderada, 3-6 pasos sintéticos
        score -= (sa - 3.5) * 4.0

    return clamp_score(score)


def calculate_druglikeness_score(properties: PhysicochemicalProperties) -> float:
    """
    Score de Drug-likeness basado en QED (Bickerton et al., Nat. Chem. 2012).

    QED combina 8 propiedades moleculares ponderadas (MW, logP, HBD, HBA,
    PSA, RotBonds, Aromáticos, Alertas estructurales) en una métrica unificada
    de 0 a 1 que reproduce el juicio de expertos en química medicinal.

    Rango mapeado: 0–100 (100 = QED=1.0, molécula drug-like ideal)
    """
    return clamp_score(properties.qed * 100.0)


def normalize_logp(log_p: float) -> float:
    """
    Normaliza el logP usando una función simétrica respecto al óptimo de 2.5.
    Mantiene compatibilidad con auditorías y tests de regresión.
    """
    dist = abs(log_p - 2.5)
    score = 0.0 if dist >= 3.5 else (1.0 - dist / 3.5) * 100.0
    return clamp_score(score)


def normalize_tpsa(tpsa: float) -> float:
    """
    Normaliza el TPSA con una ventana óptima de 20-90 Å².
    Mantiene compatibilidad con auditorías y tests de regresión.
    """
    if tpsa >= 140.0:
        score = 0.0
    elif 20.0 <= tpsa <= 90.0:
        score = 100.0
    elif tpsa < 20.0:
        score = (tpsa / 20.0) * 100.0
    else:
        score = ((140.0 - tpsa) / 50.0) * 100.0
    return clamp_score(score)


def normalize_rotatable_bonds(rotatable_bonds: int) -> float:
    """
    Normaliza la flexibilidad molecular (rotatable bonds).
    Mantiene compatibilidad con auditorías y tests de regresión.
    """
    if rotatable_bonds <= 3:
        score = 100.0
    elif rotatable_bonds >= 15:
        score = 0.0
    elif rotatable_bonds <= 10:
        score = 100.0 - ((rotatable_bonds - 3) / 7.0) * 40.0
    else:
        score = 60.0 - ((rotatable_bonds - 10) / 5.0) * 60.0
    return clamp_score(score)

