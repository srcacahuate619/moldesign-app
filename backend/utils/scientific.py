"""
utils/scientific.py

Utilidades para auditoría científica profunda de resultados de docking y propiedades.
Genera advertencias relevantes para el usuario final (químicos medicinales).
"""


#: Umbrales convencionales de eficiencia de ligando en optimización de cabezas
#: de serie. El concepto y la magnitud vienen de Hopkins, Groom, Alex,
#: *Drug Discov. Today* 9 (2004) 430-431, que define LE = ΔG / átomos pesados;
#: 0.3 kcal/mol por átomo es la referencia habitual para un cabeza de serie
#: viable, y estos dos cortes la rodean.
#:
#: NO son universales: dependen del tamaño, y ahí estaba el fallo (ver
#: `_avisos_de_eficiencia`).
LE_BAJA = 0.25
LE_ALTA = 0.45


def _avisos_de_eficiencia(
    afinidad: float, atomos_pesados: int, regimen: str | None, cumple_ro3: bool | None
) -> list[str]:
    """Eficiencia de ligando, leída en el régimen donde el umbral significa algo.

    ═════════════════════════════════════════════════════════════════════
    EL VEREDICTO LO DECIDÍA EL TAMAÑO, NO LA MOLÉCULA
    ═════════════════════════════════════════════════════════════════════

    Aquí se comparaba `|afinidad| / átomos_pesados` contra 0.25 y 0.45 fijos,
    para cualquier molécula. Como LE es una división por el número de átomos,
    esos cortes se traducen en una afinidad exigida que crece con el tamaño:

        átomos    «excepcional» exige      «baja» si
             6        |aff| > 2.7           < 1.5
            13        |aff| > 5.9           < 3.2
            37        |aff| > 16.7          < 9.2
            50        |aff| > 22.5          < 12.5

    Vina no produce afinidades por debajo de unos -12 kcal/mol. Así que una
    molécula de 6 átomos pesados supera el corte «excepcional» con cualquier
    acoplamiento útil —siempre se la felicita— y una de 50 no puede alcanzarlo
    nunca —casi siempre se le dice que es «demasiado grande»—. Medido con el
    propio módulo: benceno con Vina -4.5 recibía a la vez

        «Eficiencia de Ligando Excepcional (LE=0.75)»
        «Afinidad débil en la escala de Vina (-4.5)»

    dos frases que se contradicen delante del usuario.

    LE es *conocidamente* dependiente del tamaño; la literatura tiene métricas
    normalizadas para eso (Reynolds, Tounge, Bembenek, *J. Med. Chem.* 51
    (2008) 2432, «fit quality»; Nissink, *J. Chem. Inf. Model.* 49 (2009) 1617,
    SILE). Ninguna se implementa aquí todavía: lo que se hace es **no emitir un
    veredicto donde el umbral no discrimina**, y decir por qué.
    """
    if atomos_pesados <= 0:
        return []

    le = abs(afinidad) / atomos_pesados
    exigida_alta = LE_ALTA * atomos_pesados
    exigida_baja = LE_BAJA * atomos_pesados

    if regimen == "bro5":
        return [
            f"Eficiencia de ligando LE={le:.2f} (kcal/mol por átomo pesado). "
            "Los umbrales convencionales (0.25 / 0.45, Hopkins et al. 2004) "
            "están calibrados en espacio Ro5 y no se aplican a esta molécula: "
            "a este tamaño LE decrece por construcción. Se informa el valor sin "
            "veredicto."
        ]

    # Ro3 por masa: el umbral alto se cruza con casi cualquier acoplamiento.
    if cumple_ro3 and le > LE_ALTA:
        return [
            f"Eficiencia de ligando LE={le:.2f}. A {atomos_pesados} átomos "
            f"pesados, el umbral de 0.45 se cruza con cualquier afinidad mejor "
            f"que {-exigida_alta:.1f} kcal/mol, así que superarlo no distingue "
            "una unión buena de una mediocre. En este rango de masa (< 300 Da, "
            "Rule of Three) la eficiencia por átomo es alta por construcción: "
            "sirve para comparar entre moléculas del mismo tamaño, no como "
            "veredicto."
        ]

    if le < LE_BAJA:
        return [
            f"Baja eficiencia de ligando (LE={le:.2f}): la molécula aporta "
            f"{atomos_pesados} átomos pesados para {afinidad:.1f} kcal/mol. "
            f"Superar 0.25 a este tamaño exigiría una afinidad mejor que "
            f"{-exigida_baja:.1f} kcal/mol. Considerar recortar átomos que no "
            "contribuyen a la unión."
        ]

    if le > LE_ALTA:
        return [
            f"Eficiencia de ligando alta (LE={le:.2f}): buena economía de "
            f"átomos para este nivel de unión, con el umbral convencional de "
            "0.45 (Hopkins et al. 2004) evaluado dentro del espacio Ro5 para "
            "el que está calibrado."
        ]

    return []


def audit_scientific_quality(
    affinity_kcal: float,
    heavy_atom_count: int,
    log_p: float,
    docking_poses: list[dict],
    hotspots: list[dict],
    hotspots_hit: list[str],
    regimen: str | None = None,
    cumple_ro3: bool | None = None,
) -> list[str]:
    """
    Analiza los resultados crudos y genera advertencias científicas dinámicas.

    `regimen` y `cumple_ro3` vienen de `chem/regimenes.py` y viajan con la
    validación. Son opcionales para no romper a quien llame sin ellos, pero sin
    ellos los umbrales de eficiencia de ligando se aplican como antes: fuera
    del régimen donde están calibrados.
    """
    warnings = []

    # 1. Ligand Efficiency (LE)
    warnings.extend(
        _avisos_de_eficiencia(affinity_kcal, heavy_atom_count, regimen, cumple_ro3)
    )

    # 2. Lipophilic Efficiency (LLE)
    lle = abs(affinity_kcal) - log_p
    if lle < 1.0:
        warnings.append(
            f"Baja Eficiencia Lipofílica (LLE={lle:.2f}): El compuesto depende demasiado de la hidrofobicidad para unirse. Riesgo de baja selectividad y toxicidad."
        )

    # 3. Estabilidad del modo de enlace (RMSD Diversification)
    if len(docking_poses) > 2:
        # Vina suele dar RMSD lb/ub. Usamos lb como proxy de distancia al centro.
        # Un análisis más real requeriría calcular distancias entre poses.
        # Pero podemos usar la diferencia de afinidad como proxy de "seguridad" del modo 1.
        gap = abs(docking_poses[1]['affinity'] - docking_poses[0]['affinity'])
        if gap < 0.1:
            warnings.append(
                "Incertidumbre de Pose: Hay múltiples modos de enlace con energías casi idénticas. El modo 1 podría no ser el único biológicamente relevante."
            )

    # 4. Análisis de Hotspots
    if hotspots:
        total_hotspots = len(hotspots)
        hits_count = len(hotspots_hit)
        hit_ratio = hits_count / total_hotspots if total_hotspots > 0 else 0

        if hit_ratio == 0:
            warnings.append(
                "Fracaso de Farmacóforo: La molécula no interactúa con ningún residuo crítico definido para este target."
            )
        elif hit_ratio < 0.4:
            warnings.append(
                f"Interacción Subóptima: Solo impacta el {hit_ratio*100:.0f}% de los hotspots. Potencial para mejorar la afinidad mediante derivatización dirigida."
            )

        # Buscar hotspots de alta importancia no impactados
        critical_missed = [h['name'] for h in hotspots if h['importance'] >= 0.9 and h['name'] not in hotspots_hit]
        if critical_missed:
            warnings.append(
                f"Oportunidad Crítica: Se han fallado residuos de importancia máxima ({', '.join(critical_missed)})."
            )

    # 5. Afinidad débil en la escala de Vina
    #
    # DOC 71, DEFECTO C1 (crítico). Aquí decía: «Los niveles de binding
    # calculados están en el rango micromolar alto. Probablemente insuficiente
    # para actividad farmacológica in vivo».
    #
    # Eran dos saltos que el propio informe declara inválidos dos párrafos antes,
    # cuando explica que una afinidad de Vina NO es energía libre:
    #
    #   1. de un score de Vina a una CONSTANTE DE DISOCIACIÓN («micromolar»).
    #      La función de puntuación de Vina está entrenada para ORDENAR
    #      candidatos, no para predecir una Kd; convertir -5,8 kcal/mol en una
    #      concentración es leer una regla graduada en unidades que no tiene.
    #   2. de esa constante a ACTIVIDAD IN VIVO, que además atraviesa
    #      permeabilidad, metabolismo, unión a proteínas plasmáticas y dosis.
    #
    # Se corrige BORRANDO la inferencia, no matizándola: un «probablemente» no
    # arregla una afirmación cuya premisa el documento ya negó. Lo que sí se
    # puede decir —y se dice— es dónde cae el número EN LA ESCALA DE VINA, que
    # es la única en la que ese número significa algo.
    if affinity_kcal > -6.0:
        # El corte de -6 está pensado para moléculas de tipo Ro5. Por debajo de
        # 300 Da una afinidad de -4 o -5 kcal/mol es lo ESPERADO —es el punto
        # de partida del cribado por fragmentos, no un defecto—, y decir «sirve
        # para descartar» ahí contradecía al aviso de eficiencia de ligando que
        # se emitía a la vez. Se conserva el número, se cambia la lectura.
        if cumple_ro3:
            warnings.append(
                f"Afinidad de {affinity_kcal:.1f} kcal/mol en la escala de Vina. "
                "Por debajo de 300 Da (Rule of Three) una afinidad en este rango "
                "es lo habitual y no descalifica la molécula: el criterio en "
                "espacio de fragmentos es la eficiencia por átomo, no la afinidad "
                "absoluta. El score de Vina ordena candidatos; no es energía "
                "libre ni se traduce a una concentración."
            )
        else:
            warnings.append(
                f"Afinidad débil en la escala de Vina ({affinity_kcal:.1f} kcal/mol): por encima "
                "de -6 el score deja de discriminar bien entre unir y no unir, así que este "
                "resultado sirve para descartar, no para priorizar. El score de Vina ordena "
                "candidatos; no es energía libre ni se traduce a una concentración."
            )

    return warnings
