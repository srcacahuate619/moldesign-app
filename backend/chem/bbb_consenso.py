"""
El veredicto de barrera hematoencefálica, y por qué cada regla sigue ahí.

═══════════════════════════════════════════════════════════════════════════
EL FALLO QUE ARREGLA
═══════════════════════════════════════════════════════════════════════════

Este consenso se escribió y se ajustó mientras la predicción del modelo valía
**cero para toda molécula**. La causa está documentada en `blood_viability.py`:
`int()` truncaba la probabilidad de ADMET-AI, y como ninguna probabilidad llega
a 1.0 exacto, `admet_bbb` era 0 siempre. Las cinco capas se afinaron contra una
entrada muerta.

Al arreglar el `int()`, la entrada se despertó — y la condición que la recibía
era ésta, tal cual, sin un solo paréntesis:

    if cns_mpo >= 4.0 and not is_too_polar and not is_pgp_efflux \\
       or admet_bbb == 1 \\
       or is_small_neutral and not is_pgp_efflux:

Por precedencia, `or admet_bbb == 1` es un término suelto: salta por encima de
los filtros de polaridad y de eflujo por P-gp, y no pondera la confianza. Un
0.51 pesaba igual que un 0.98.

Medido sobre 41 fármacos de difusión pasiva con veredicto clínico conocido
(`tests/test_bbb_consenso.py` trae la tabla entera, con la probabilidad que
devolvió el modelo empaquetado para cada uno):

    antes del arreglo del int()   37/41 aciertos    4 falsos positivos
    con el modelo ya vivo         33/41 aciertos    8 falsos positivos  ← peor
    con este módulo               39/41 aciertos    2 falsos positivos

Arreglar el truncamiento, sin tocar nada más, **empeoraba** el producto: el
modelo entraba por una puerta que no comprobaba nada. Los cinco que se
estropearon son atenolol, sulpirida, cimetidina, hidroclorotiazida y dopamina
—todos hidrofílicos de manual, todos con la probabilidad entre 0.46 y 0.79.

═══════════════════════════════════════════════════════════════════════════
LO QUE DECIDE, Y EN QUÉ ORDEN
═══════════════════════════════════════════════════════════════════════════

    BLOQUEOS  (estructurales; ganan sobre cualquier señal positiva)
      0  carga permanente          amonio cuaternario, sulfonato, fosfonato
      1  anión a pH 7.4            fracción ionizada del ácido dominante >= 0.5
      2a PPB > 99 %                atrapada por proteína plasmática
      2b PPB > 92 % y >= 3 anillos aromáticos

    POSITIVAS (la primera que acierta decide)
      3  el modelo, con confianza  p >= 0.90 — anula las heurísticas
      4  el modelo, moderado       p >= 0.50 **y** ni demasiado polar ni P-gp

    Por defecto: no permeable.

La forma es la que pedía el problema: **el modelo entrenado es la señal
primaria, y las heurísticas sólo pueden recortar lo que el modelo permite.**
Un voto flojo del modelo pasa por los filtros mecanísticos; uno seguro, no.

═══════════════════════════════════════════════════════════════════════════
LAS DOS REGLAS QUE SE RETIRARON, Y LA MEDICIÓN QUE LO JUSTIFICA
═══════════════════════════════════════════════════════════════════════════

**El CNS MPO ya no decide.** Era la capa 3 de la versión anterior. Sobre los 46
fármacos medidos, la ruta del MPO no aporta un solo acierto que la capa 4 no dé
ya, y sí aporta un falso positivo: dopamina (MPO 4.27 con las rampas de Wager
correctas, probabilidad 0.463). Es decir, el MPO estaba contradiciendo un
negativo del modelo — el mismo error que el `or admet_bbb == 1`, con los papeles
cambiados. Wager et al. presentan el MPO como una función de deseabilidad para
priorizar una serie, no como un clasificador, y así se comporta al medirlo.

El MPO se sigue calculando y se sigue mostrando (`blood_cns_mpo`), con las seis
rampas del artículo ya corregidas: informa, no dictamina.

**«Pequeña y neutra» ya no decide.** Era la capa 5: `MW < 250 y logP > 0 y
TPSA < 100 y sin ácido ionizable`. Nunca comprobó la neutralidad de las bases,
sólo la de los ácidos, así que la dopamina —catión en más del 99 % a pH 7.4—
entraba por ella. Al añadirle la carga real la regla deja de disparar en los 46
fármacos: no decide ninguno. Una regla que no decide nada, pero que puede
anular un negativo del modelo, sólo puede hacer daño.

═══════════════════════════════════════════════════════════════════════════
LO QUE ESTE CONSENSO NO PUEDE ACERTAR, Y NO SE ESCONDE
═══════════════════════════════════════════════════════════════════════════

Modela **difusión pasiva**. La entrada o la exclusión por transportador queda
fuera, y los casos que lo demuestran están en el conjunto de referencia en vez
de curados fuera de él:

    levodopa, gabapentina, ácido valproico   entran por acarreador (LAT1, MCT)
                                             y aquí salen «no permeable»
    loperamida                               la expulsa P-gp; aquí acierta,
                                             pero por la regla de PPB, no por
                                             el eflujo

Los dos falsos positivos que quedan entre los de difusión pasiva son ranitidina
y sulpirida: bases polares cuyo pKa real está lejos del representativo de clase
que `ionizacion.py` les asigna. Se dejan como están. Subir el umbral de la capa
4 a 0.70 corrige la sulpirida y a 0.80 pierde la lamotrigina: eso no es
calibrar, es ajustar a catorce letras de una tabla.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from chem.ionizacion import analizar_ionizacion

#: Binarización estándar de las cabezas de clasificación de ADMET-AI, entrenadas
#: con BCE sobre TDC. Es el mismo umbral que usa `blood_viability.predict_admet_ai`.
UMBRAL_MODELO: float = 0.50

#: A partir de aquí el modelo anula las heurísticas.
#:
#: NO ESTÁ CALIBRADO, y decirlo importa. Sobre los 46 fármacos medidos, cualquier
#: valor entre 0.80 y 0.99 produce los mismos 46 veredictos: la capa 3 nunca llega
#: a cambiar uno, porque en este conjunto los filtros y el modelo coinciden
#: siempre que el modelo está seguro. Lo que la medición sí determina es la
#: FORMA —que el voto moderado pase por los filtros y el seguro no—, no el número.
#:
#: Existe para que una regla de pulgar no pueda vetar una predicción firme. Si
#: algún día un fármaco la ejerce, será visible en la capa que devuelve la
#: decisión, y entonces habrá evidencia para elegir el valor.
UMBRAL_MODELO_ANULA_HEURISTICAS: float = 0.90

#: Fracción del ácido dominante ionizada a pH 7.4 a partir de la cual la especie
#: se considera aniónica. 0.5 es el punto en que el pKa cruza el pH.
#:
#: Sustituye a `tiene COOH y MW > 150`. Ese corte de masa no venía de ningún
#: sitio: dejaba pasar el ácido salicílico (138 Da, anión completo a pH 7.4, que
#: el consenso declaraba permeable) por estar tres unidades por debajo.
FRACCION_ANIONICA: float = 0.5

#: Unión a proteína plasmática (%) por encima de la cual la molécula está
#: secuestrada pase lo que pase.
PPB_ATRAPAMIENTO_TOTAL: float = 99.0

#: PPB alta que sólo bloquea acompañada de multiples anillos aromáticos: es el
#: patrón del atrapamiento por albúmina de los lipofílicos poliaromáticos.
PPB_ATRAPAMIENTO_AROMATICO: float = 92.0
ANILLOS_AROMATICOS_ATRAPAMIENTO: int = 3


@dataclass(frozen=True)
class DecisionBBB:
    """El veredicto y, sobre todo, quién lo tomó."""

    #: `None` cuando no hay predicción del modelo y ninguna regla estructural
    #: se pronuncia. No es lo mismo que «no permeable».
    permeable: bool | None
    #: Identificador de la regla que decidió. Va al log y a las pruebas.
    capa: str
    #: La frase para quien lea el panel.
    motivo: str
    #: La probabilidad que dio el modelo, para que el número que decidió sea visible.
    p_modelo: float | None = None
    #: Lo que se reconoció por SMARTS y sirvió para decidir.
    hallazgos: list[str] = field(default_factory=list)


def _sin_modelo(capa: str, motivo: str) -> DecisionBBB:
    return DecisionBBB(permeable=None, capa=capa, motivo=motivo)


def decidir_bbb(
    smiles: str,
    *,
    p_modelo: float | None,
    mw: float,
    logp: float,
    tpsa: float,
    hbd: int,
    hba: int,
    ppb: float | None,
    anillos_aromaticos: int | None = None,
) -> DecisionBBB:
    """Aplica el consenso. Función pura: no toca modelos, base de datos ni disco.

    `p_modelo` es P(BBB+) según ADMET-AI, en [0, 1]. `None` significa que el
    modelo no se pudo consultar — y entonces el resultado es `None`, no `False`,
    salvo que una regla estructural se pronuncie por su cuenta.
    """
    estado = analizar_ionizacion(smiles, logp)

    # ── 0. Carga permanente ──────────────────────────────────────────────
    # Un amonio cuaternario no tiene pKa: tiene carga, a todo pH. No difunde,
    # y no hay probabilidad que lo matice.
    if estado.tiene_carga_permanente:
        return DecisionBBB(
            permeable=False,
            capa="0_carga_permanente",
            motivo=(
                "Carga permanente ("
                + ", ".join(estado.cargas_permanentes)
                + "): ningún pH la neutraliza, así que no hay especie neutra "
                "que difunda a través de la membrana."
            ),
            p_modelo=p_modelo,
            hallazgos=list(estado.cargas_permanentes),
        )

    # ── 1. Anión a pH 7.4 ────────────────────────────────────────────────
    # La asimetría con las bases es deliberada: un catión conserva una fracción
    # neutra que difunde, y el endotelio de la barrera tiene la superficie
    # luminal aniónica. Los fármacos del SNC con amina básica son la norma; con
    # ácido libre, la excepción — y las excepciones reales (valproato,
    # gabapentina) entran por acarreador, que es justo lo que esto no modela.
    fraccion_acido = estado.fraccion_acido_ionizada or 0.0
    if fraccion_acido >= FRACCION_ANIONICA:
        acidos = [c[0] for c in estado.centros if c[2] == "acido"]
        return DecisionBBB(
            permeable=False,
            capa="1_anion",
            motivo=(
                f"Aniónica a pH 7.4: el centro ácido dominante está ionizado en "
                f"un {fraccion_acido * 100:.0f} %. Una especie con carga negativa "
                f"no atraviesa la barrera por difusión pasiva. Si esta molécula "
                f"entra al cerebro, será por un transportador, y eso no se evalúa aquí."
            ),
            p_modelo=p_modelo,
            hallazgos=acidos,
        )

    # ── 2. Secuestro por proteína plasmática ─────────────────────────────
    if ppb is not None and ppb > PPB_ATRAPAMIENTO_TOTAL:
        return DecisionBBB(
            permeable=False,
            capa="2a_ppb_total",
            motivo=(
                f"Unión a proteína plasmática del {ppb:.1f} %: prácticamente no "
                f"queda fracción libre que pueda cruzar."
            ),
            p_modelo=p_modelo,
        )

    if (
        ppb is not None
        and ppb > PPB_ATRAPAMIENTO_AROMATICO
        and (anillos_aromaticos or 0) >= ANILLOS_AROMATICOS_ATRAPAMIENTO
    ):
        return DecisionBBB(
            permeable=False,
            capa="2b_ppb_aromatico",
            motivo=(
                f"Unión a proteína plasmática del {ppb:.1f} % con "
                f"{anillos_aromaticos} anillos aromáticos: el patrón del "
                f"atrapamiento por albúmina de los lipofílicos poliaromáticos."
            ),
            p_modelo=p_modelo,
        )

    # ── Sin modelo no hay veredicto positivo posible ─────────────────────
    # Las reglas de arriba son estructurales y se sostienen solas. Las de abajo
    # son el modelo. Sin él se declara desconocido, que no es «no permeable».
    if p_modelo is None:
        return _sin_modelo(
            "sin_prediccion",
            "No hay predicción de permeabilidad: el modelo ADMET no estaba "
            "disponible en esta corrida y ninguna regla estructural se pronuncia.",
        )

    # ── 3. El modelo, con confianza ──────────────────────────────────────
    if p_modelo >= UMBRAL_MODELO_ANULA_HEURISTICAS:
        return DecisionBBB(
            permeable=True,
            capa="3_modelo_confiado",
            motivo=(
                f"El modelo de permeabilidad da p = {p_modelo:.3f}. Por encima de "
                f"{UMBRAL_MODELO_ANULA_HEURISTICAS:.2f} su predicción no se somete "
                f"a las heurísticas fisicoquímicas."
            ),
            p_modelo=p_modelo,
        )

    # ── 4. El modelo, moderado — y entonces sí, los filtros ──────────────
    # Estos dos filtros son las únicas heurísticas que quedan, y sólo pueden
    # RESTAR. Medido: el de polaridad decide correctamente atenolol, cimetidina
    # e hidroclorotiazida, que el modelo solo habría dado por permeables. El de
    # P-gp no llega a decidir ninguno de los 46 (metotrexato, sacarosa y
    # digoxina lo disparan, pero ya los había resuelto otra regla); se conserva
    # porque el mecanismo es real y el conjunto de referencia no lo representa.
    demasiado_polar = logp < 1 and tpsa > 80 and hbd >= 3
    eflujo_pgp = hba >= 8 and logp < 3

    if p_modelo >= UMBRAL_MODELO:
        if demasiado_polar:
            return DecisionBBB(
                permeable=False,
                capa="4_polar_vence_al_modelo",
                motivo=(
                    f"El modelo da p = {p_modelo:.3f}, por debajo de "
                    f"{UMBRAL_MODELO_ANULA_HEURISTICAS:.2f}, y el perfil es el de "
                    f"una molécula demasiado polar para difundir (logP {logp:.2f}, "
                    f"TPSA {tpsa:.0f} Å², {hbd} donadores)."
                ),
                p_modelo=p_modelo,
            )
        if eflujo_pgp:
            return DecisionBBB(
                permeable=False,
                capa="4_pgp_vence_al_modelo",
                motivo=(
                    f"El modelo da p = {p_modelo:.3f}, por debajo de "
                    f"{UMBRAL_MODELO_ANULA_HEURISTICAS:.2f}, y el perfil "
                    f"({hba} aceptores con logP {logp:.2f}) es el de un sustrato "
                    f"de P-glicoproteína, que la bombea de vuelta a la sangre."
                ),
                p_modelo=p_modelo,
            )
        return DecisionBBB(
            permeable=True,
            capa="4_modelo_moderado",
            motivo=(
                f"El modelo da p = {p_modelo:.3f} y ni la polaridad ni el perfil "
                f"de P-gp lo contradicen."
            ),
            p_modelo=p_modelo,
        )

    return DecisionBBB(
        permeable=False,
        capa="defecto",
        motivo=(
            f"El modelo da p = {p_modelo:.3f}, por debajo de {UMBRAL_MODELO:.2f}, "
            f"y ninguna regla lo contradice."
        ),
        p_modelo=p_modelo,
    )
