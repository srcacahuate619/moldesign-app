"""Los bloques del dossier que separan observación, interpretación y abstención.

`docs/74_ARQUITECTURA_DISPATCHER_DE_PROTOCOLOS.md` §10 y
`docs/75_DECISION_CIENTIFICA_M5_ZN_V1.md` §5 y §7.

Viven aparte de `model.py` porque son la parte del dossier que depende del
PROTOCOLO, y esa es la dimensión que el dispatcher va a hacer crecer: M5-Fe,
macrociclos, ligandos covalentes. Meterlos en el constructor general habría
sido repetir la mezcla que el documento 74 quiere deshacer.

# Las tres cosas que no pueden confundirse

    observación     lo que un motor midió: el score de Vina, el pLDDT
    interpretación  lo que un modelo dedujo: la regresión de XGBoost, un score
                    compuesto — con su dominio de validez al lado
    abstención      que no hay dato, y por qué no lo hay

Un valor neutral fabricado —un 0.5, un −4.0— no es ninguna de las tres. El §5
del ADR 75 lo dice para M5-Zn y aquí vale para todo: si falta un componente, el
campo va vacío con su motivo.
"""

from __future__ import annotations

from typing import Any

from services.dossier.taxonomy import Estado


def campos_de_m4(Campo, campo_dato, leer, eval_result, resumen) -> list:
    """M4: la observación de Vina y la interpretación de XGBoost, separadas.

    Hasta el 2026-09-04 no se podían separar porque no coexistían: la regresión
    se convertía con −1.36·pKi y se escribía SOBRE `affinity_kcal`. El dossier
    heredaba esa confusión y llamaba «escala de Vina» a un número que no lo era.

    `Campo`, `campo_dato` y `leer` se reciben por parámetro para no crear un
    import circular con `model.py`, que es quien los define.
    """
    campos = []

    afinidad = resumen.get("top_pose_affinity")
    campos.append(campo_dato(
        "Observación · afinidad AutoDock Vina",
        (f"{afinidad:.2f} kcal/mol (score de Vina, sin transformar)"
         if afinidad is not None else None),
        "La corrida no produjo afinidad de acoplamiento.",
    ))

    ml_pki = leer(eval_result, "ml_pki")
    if ml_pki is None:
        campos.append(Campo(
            "Interpretación · regresión XGBoost (pKi)",
            None,
            Estado.NO_EVALUADO,
            "El rescoring de ML no produjo regresión para esta corrida. En "
            "evaluaciones anteriores al 2026-09-04 este campo está vacío porque "
            "el valor se perdía al sobrescribir la afinidad de Vina.",
        ))
    else:
        en_dominio = leer(eval_result, "ml_pki_aplicada")
        equivalente = -1.36 * float(ml_pki)
        if en_dominio is True:
            campos.append(Campo(
                "Interpretación · regresión XGBoost (pKi)",
                f"pKi {float(ml_pki):.2f} · equivale a {equivalente:.2f} kcal/mol "
                "· dentro del dominio de aplicabilidad",
                Estado.REGISTRADO,
                "Se informa JUNTO a la afinidad de Vina, no en su lugar: son dos "
                "cantidades con distinto error y distinto dominio de validez.",
            ))
        elif en_dominio is False:
            campos.append(Campo(
                "Interpretación · regresión XGBoost (pKi)",
                f"pKi {float(ml_pki):.2f} · equivale a {equivalente:.2f} kcal/mol",
                Estado.REVISAR,
                "FUERA del dominio de aplicabilidad del modelo: la molécula no se "
                "parece a las del conjunto de entrenamiento. Se muestra como "
                "referencia, no como predicción. La afinidad del caso es la de Vina.",
            ))
        else:
            campos.append(Campo(
                "Interpretación · regresión XGBoost (pKi)",
                f"pKi {float(ml_pki):.2f}",
                Estado.REVISAR,
                "La corrida no registró si la predicción cayó dentro del dominio "
                "de aplicabilidad, así que no se puede afirmar que lo hiciera.",
            ))

    modelo = leer(eval_result, "model_used")
    familia = leer(eval_result, "target_family")

    # ── La grafía histórica se conserva COMO PROCEDENCIA ─────────────
    #
    # §6.5 del ADR 75: los artefactos sellados no se editan, su grafía se
    # normaliza al cargarlos. Así que la clasificación usa la canónica y el
    # dossier muestra las dos cuando difieren — un expediente antiguo que
    # guardó `metaloenzyme` debe seguir diciendo lo que guardó, y a la vez
    # dejar claro con qué familia se le trató.
    from scoring.ums import normalizar_familia

    canonica = normalizar_familia(familia)
    if familia and canonica and canonica != familia.strip().lower():
        texto_familia = f"{canonica} (registrada como «{familia}»)"
    else:
        texto_familia = canonica

    campos.append(campo_dato(
        "Modelo de rescoring y familia estructural",
        (f"{modelo} · familia {texto_familia}" if modelo and texto_familia
         else (modelo or texto_familia or None)),
        "La corrida no registró qué modelo de rescoring se usó.",
    ))

    pesos_efectivos = leer(eval_result, "stacking_effective_weights")
    if isinstance(pesos_efectivos, dict):
        orden = ("vina", "xgb", "gnn", "clgnn")
        texto_pesos = " | ".join(
            f"{nombre}={float(pesos_efectivos[nombre]):.4f}"
            for nombre in orden
            if nombre in pesos_efectivos
        )
        degradado = bool(leer(eval_result, "stacking_degraded"))
        ausentes = leer(eval_result, "stacking_missing_components") or []
        campos.append(Campo(
            "Pesos efectivos del stacking M4",
            texto_pesos or None,
            Estado.REVISAR if degradado else Estado.REGISTRADO,
            (
                "Se persistieron los pesos normalizados usados realmente en esta corrida."
                + (f" Componentes ausentes: {', '.join(map(str, ausentes))}." if ausentes else "")
            ) if texto_pesos else "La corrida no registro los pesos efectivos.",
            valor_es_clasificacion=True,
        ))
    return campos


def campos_de_m5_zn(Campo, campo_dato, leer, eval_result, resumen, target) -> list:
    """M5-Zn: el perfil, su fórmula, sus componentes y su score — o la razón.

    Los tres estados que el dossier tiene que saber contar:

      1. perfil exacto y completo                       fórmula y score
      2. perfil exacto, falta un componente con peso≠0  score null
      3. otra metaloenzima de zinc                      señales sí, score no

    En 2 y 3 el score es `null` y nunca un valor neutral: el §5 del ADR 75 dice
    que un 0.5 fabricado no cuenta como evaluación.
    """
    from scoring.ums import normalizar_familia
    from services.pipeline.protocols.m5.zinc import perfil_para

    familia = leer(eval_result, "target_family") or ""
    if normalizar_familia(familia) != "metalloenzyme":
        return []  # No es un caso de metal: el bloque no aplica.

    # ── El PDB sale del OBJETIVO, no del resultado ───────────────────
    #
    # Esta línea leía `target_pdb_id` del `eval_result`, y ese campo NO EXISTE:
    # `evaluation_results` no tiene esa columna, y el snapshot congelado de una
    # corrida se construye desde `EvaluationResultORM.__table__.columns`, así
    # que tampoco la lleva. El PDB vive en `targets` y llega por el objetivo de
    # la molécula.
    #
    # La consecuencia: `perfil_para(None)` devolvía None SIEMPRE. En el producto
    # instalado, una corrida contra 3DC3 —el más completo de los tres perfiles—
    # se documentaba como `REVIEW_OUT_OF_VALIDATED_TARGET`, con su motivo bien
    # redactado y el PDB «sin declarar». El dossier contaba con exactitud lo que
    # había calculado; lo que estaba mal era lo que había calculado.
    #
    # Ninguna prueba lo veía: todas le pasaban un diccionario CON
    # `target_pdb_id` dentro. Lo encontró `scripts/verify_embedded_dossier.py`
    # pidiendo el dossier por HTTP sobre filas reales de SQLite.
    #
    # `target` es obligatorio y sin valor por defecto a propósito: un `None`
    # implícito reproduciría el fallo en silencio en el próximo sitio que llame
    # a esta función.
    pdb = str(leer(target, "pdb_id") or "")
    perfil = perfil_para(pdb)
    # La señal AUTORIZADA es `ums_warhead` —SMARTS puro—, no `ums_score`, que
    # es el UMS histórico con donantes y MolChamb. Este campo se llamaba
    # «(UMS, SMARTS)» y leía el histórico: el mismo error de etiqueta que ponía
    # el peso de la GNN legacy bajo el nombre de CL-GNN.
    #
    # En corridas anteriores a SCHEMA 18 `ums_warhead` es NULL. Ahí se muestra
    # el histórico DICIENDO que lo es, en vez de callar el dato o presentarlo
    # como si fuera el otro.
    ums = leer(eval_result, "ums_warhead")
    if isinstance(ums, (int, float)):
        campo_ums = campo_dato(
            "Señal · warheads de zinc (UMS, SMARTS)",
            f"{float(ums):.4f}",
            "No se calculó la señal de warheads.",
        )
    else:
        historico = leer(eval_result, "ums_score")
        campo_ums = campo_dato(
            "Señal · warheads de zinc (UMS, SMARTS)",
            (f"{float(historico):.4f} — UMS HISTÓRICO (warheads + donantes + "
             "MolChamb), no la variante SMARTS-only del ADR 75. La corrida es "
             "anterior a SCHEMA 18 y no registró la señal autorizada."
             if isinstance(historico, (int, float)) else None),
            "No se calculó la señal de warheads.",
        )

    # ── Estado 3: fuera de las tres dianas validadas ─────────────────
    if perfil is None:
        return [
            Campo(
                "Protocolo M5-Zn",
                "REVIEW_OUT_OF_VALIDATED_TARGET",
                Estado.ABSTENCION,
                f"El PDB «{pdb or 'sin declarar'}» no es ninguno de los tres "
                "perfiles validados (3DC3/CA2, 1GKC/MMP9, 1O86/ACE). M5-Zn "
                "prepara el receptor, conserva el zinc, ejecuta Vina y calcula "
                "señales diagnósticas, pero NO hereda los pesos de otra diana.",
                valor_es_clasificacion=True,
            ),
            Campo(
                "Score compuesto M5-Zn",
                None,
                Estado.NO_EVALUADO,
                "Sin perfil validado no hay fórmula que aplicar. Las señales "
                "individuales sí están disponibles y se muestran por separado.",
            ),
            campo_ums,
        ]

    # ── Estados 1 y 2: hay perfil exacto ─────────────────────────────
    # `gnn_d` NO es `gnn_score`. `gnn_score` es la GNN legacy de RTMScore; GNN-D
    # es otro modelo, y esta línea leía el primero para decir que el segundo
    # estaba presente. Es el mismo error de etiqueta que ponía el peso de la GNN
    # legacy bajo el nombre de CL-GNN.
    #
    # La corrida actual conserva los ausentes en `m5_missing_components`. El
    # fallback de abajo sólo sirve para expedientes anteriores al esquema 20,
    # donde ese detalle no existía; no decide el estado del protocolo.
    disponibles: dict[str, Any] = {
        "vina": resumen.get("top_pose_affinity"),
        "xgb": leer(eval_result, "xgb_score"),
        "gnn_d": leer(eval_result, "gnn_d_prob"),
        "ums": ums,
    }
    persistidos = leer(eval_result, "m5_missing_components")
    if isinstance(persistidos, list):
        # La corrida actual es la fuente de verdad; sólo las corridas anteriores
        # al esquema 20 necesitan la reconstrucción conservadora de abajo.
        ausentes = [str(componente) for componente in persistidos]
        presentes = [c for c in perfil.componentes_requeridos if c not in ausentes]
    else:
        ausentes = [c for c in perfil.componentes_requeridos if disponibles.get(c) is None]
        presentes = [c for c in perfil.componentes_requeridos if disponibles.get(c) is not None]

    campos = [
        campo_dato("Protocolo M5-Zn", perfil.protocol_id, "No se resolvió el perfil."),
        campo_dato("Fórmula del perfil", perfil.formula,
                   "El perfil no declara su fórmula."),
        campo_dato(
            "Componentes requeridos y presentes",
            f"requeridos: {' · '.join(perfil.componentes_requeridos)} — "
            f"presentes: {' · '.join(presentes) if presentes else 'ninguno'}",
            "El perfil no declara sus componentes.",
        ),
        campo_dato(
            "Normalización de Vina (congelada por perfil)",
            f"vina_reference_max = {perfil.vina_reference_max}",
            "El perfil no declara su normalizador.",
        ),
        campo_ums,
    ]

    # El score SIEMPRE sale de lo persistido. `ausentes` se usa para enriquecer
    # el motivo, no para deducir un estado: si la corrida no ejecutó el
    # protocolo, «falta un componente» sería una conclusión del dossier sobre
    # un cálculo que nadie intentó.
    campos.append(_campo_del_score(Campo, campo_dato, leer, eval_result, ausentes))

    return campos


def _campo_del_score(Campo, campo_dato, leer, eval_result, ausentes=()):
    """El score compuesto: el número PERSISTIDO, o por qué no hay número.

    ═══════════════════════════════════════════════════════════════════════
    ESTE CAMPO AFIRMABA UN CÁLCULO QUE NO OCURRE
    ═══════════════════════════════════════════════════════════════════════

    Decía «calculado con el perfil exacto» en cuanto el perfil resolvía y sus
    componentes estaban presentes. No mostraba ningún número, y sobre todo: no
    lo calculaba nadie. `services/pipeline/protocols/m5/zinc.py::calcular` no
    tiene NINGÚN llamador en producción —la única referencia viva al módulo es
    `perfil_para`, aquí al lado—, así que el protocolo M5-Zn está implementado
    y no ejecutado.

    Mientras el perfil no resolvía, el bloque se abstenía y la frase no se
    alcanzaba. Al arreglar la resolución del PDB el 2026-09-04, la frase pasó a
    imprimirse: una corrida contra 3DC3 declaraba un cálculo que nunca se hizo.
    Un dossier que afirma más de lo que sabe es el defecto exacto que este
    producto existe para no cometer.

    La regla es la de siempre: el dossier INFORMA, no calcula. Lee lo que la
    corrida persistió. Si no hay nada persistido, lo dice y dice por qué.
    """
    m5 = leer(eval_result, "m5_score")
    estado = leer(eval_result, "m5_scientific_status")

    if m5 is not None:
        protocolo = leer(eval_result, "m5_protocol_id")
        etiqueta = (
            f"{float(m5):.4f}"
            + (f" · {protocolo}" if protocolo else "")
            + " — score de ranking derivado, no una afinidad ni una medida "
              "experimental"
        )
        # ── CERRADO POR DEFECTO ──────────────────────────────────────
        #
        # Sólo `VALIDATED` se presenta como dato registrado. Cualquier otro
        # estado —los conocidos, los que se añadan mañana y la ausencia de
        # estado— sale como REVISAR con su motivo.
        #
        # Antes se preguntaba al revés: si el estado estaba en una lista de
        # advertencias, REVISAR; si no, REGISTRADO. Eso es una lista negra, y
        # una lista negra deja pasar por omisión lo que no conoce. El invariante
        # `test_invariante_solo_validated_decide` lo encontró inyectando un
        # score de 0.99 junto a `NOT_EVALUATED_MISSING_COMPONENT`: el dossier lo
        # presentaba como conclusión.
        from services.pipeline.protocols.interpretabilidad import es_interpretable

        if es_interpretable(estado):
            return campo_dato("Score compuesto M5-Zn", etiqueta,
                              "No se pudo calcular.")

        # Hay número Y hay advertencia. Ocultar el número sería peor: dejaría de
        # poder auditarse justo cuando hace falta auditarlo.
        return Campo(
            "Score compuesto M5-Zn",
            etiqueta + " · " + _MOTIVOS_CON_SCORE.get(
                str(estado), "NO HABILITA UNA CONCLUSIÓN"
            ),
            Estado.REVISAR,
            _MOTIVOS.get(str(estado)) or (
                f"El estado «{estado}» no es VALIDATED, así que este número no "
                "habilita ninguna conclusión: no entra en el ranking, ni en la "
                "recomendación, ni en el veredicto. Se muestra para que pueda "
                "auditarse."
            ),
            valor_es_clasificacion=True,
        )

    if estado:
        # La corrida SÍ ejecutó el protocolo y se abstuvo. El estado dice por
        # qué, y esa frase es el contenido del campo: sin ella el dossier
        # imprimiría «NO EVALUADO» a secas, que no distingue «faltó un
        # componente» de «esta diana no tiene perfil».
        return Campo(
            "Score compuesto M5-Zn",
            str(estado),
            Estado.NO_EVALUADO,
            _MOTIVOS.get(
                str(estado),
                "El protocolo se ejecutó y no produjo score compuesto.",
            ) + (
                f" Componentes ausentes en esta corrida: {', '.join(ausentes)}."
                if ausentes else ""
            ),
            valor_es_clasificacion=True,
        )

    return Campo(
        "Score compuesto M5-Zn",
        "NOT_EVALUATED_PROTOCOL_NOT_EXECUTED",
        Estado.NO_EVALUADO,
        "La corrida no registró ningún estado de M5-Zn: es anterior a SCHEMA 18, "
        "cuando el protocolo se conectó al pipeline. Hasta entonces estaba "
        "implementado y sin llamador, así que estos casos se puntuaron con M4 y "
        "los pesos por defecto del stacking. Las señales individuales de arriba "
        "sí son de esta corrida.",
        valor_es_clasificacion=True,
    )


#: Los estados que SÍ traen número, con la etiqueta corta que lo acompaña.
#: El número se muestra siempre: ocultarlo dejaría de poder auditarse justo
#: cuando hace falta auditarlo.
_MOTIVOS_CON_SCORE = {
    "REVIEW_INVALID_BENCHMARK_SITE": "BENCHMARK EN REVISIÓN",
    "REVIEW_BENCHMARK_PROVENANCE_INCOMPLETE": "PROCEDENCIA SIN VERIFICAR",
    "REVIEW_BENCHMARK_TOP1_NOT_METAL_COORDINATING": "TOP-1 SIN COORDINAR EL METAL",
}

#: Por qué el protocolo no produjo score. Se redactan aquí y no en el ejecutor
#: porque el vocabulario del §5 y §7 es corto a propósito —lo lee una máquina—
#: y la explicación larga es para quien lee el documento.
_MOTIVOS = {
    "NOT_EVALUATED_MISSING_COMPONENT": (
        "Faltó al menos un componente con peso distinto de cero en la fórmula "
        "del perfil. No se renormalizan pesos ni se sustituye un modelo por "
        "otro (§5). El caso de CA2/3DC3 es GNN-D: no existe productor de esa "
        "señal en producción —sólo aparece en los checkpoints de benchmark— y "
        "el §4.1 prohíbe sustituirla por CL-GNN."
    ),
    "REVIEW_OUT_OF_VALIDATED_TARGET": (
        "Es una metaloenzima de zinc, pero su PDB no es ninguno de los tres "
        "perfiles validados. M5-Zn prepara el receptor, conserva el zinc, "
        "ejecuta Vina y calcula señales diagnósticas, y NO hereda los pesos de "
        "otra diana (§7.2)."
    ),
    "REVIEW_OUT_OF_VALIDATED_STRUCTURE": (
        "El PDB corresponde a un perfil validado pero no se confirmó el zinc en "
        "la estructura. Un carboxilato, tiol o sulfonamida en el ligando es una "
        "feature del ligando, no un centro metálico (§8)."
    ),
    "REVIEW_INVALID_BENCHMARK_SITE": (
        "El score está calculado y es reproducible, pero se DEMOSTRÓ que el "
        "benchmark que validó este perfil no acopló en el sitio del zinc "
        "catalítico. En MMP9/1GKC ningún zinc cae dentro de la caja declarada "
        "por el criterio por eje —el catalítico queda fuera por Δz = −17.34 con "
        "semilado 12.5—, el inhibidor cristalográfico tiene sólo 4 de sus 22 "
        "átomos dentro, y el único metal dentro es un ion de calcio a 4.7 Å del "
        "centro. Medido átomo a átomo, el donante más cercano de un activo está "
        "a 15.99 Å del zinc. El componente que depende de la pose pesa 0.75. El "
        "número sirve para comparar corridas entre sí y NO debe leerse como "
        "evidencia de acoplamiento metaloproteico. Ver "
        "docs/77_CORRIGENDUM_SITIO_DEL_BENCHMARK_M5_ZN.md §1.1."
    ),
    "REVIEW_BENCHMARK_PROVENANCE_INCOMPLETE": (
        "El score está calculado y es reproducible, y NO se ha demostrado que el "
        "sitio sea incorrecto: en ACE/1O86 el zinc está dentro de la caja —es su "
        "centro exacto— y las poses también. Lo que no se puede verificar es la "
        "procedencia: falta el complejo cristalográfico para comprobar el "
        "bolsillo del inhibidor, ningún artefacto registra la caja efectiva, y "
        "el checkpoint tiene 44 registros sin pose y 21 sin features. El "
        "componente que depende de la pose pesa 0.60. «No se puede comprobar que "
        "esté bien» no es «está mal», y tampoco es «está validado». Ver "
        "docs/77_CORRIGENDUM_SITIO_DEL_BENCHMARK_M5_ZN.md §1.2 y §7."
    ),
    "REVIEW_BENCHMARK_TOP1_NOT_METAL_COORDINATING": (
        "El score está calculado y es reproducible. La caja del benchmark SÍ "
        "contenía el zinc —en ACE/1O86 es su centro exacto, y las poses caen "
        "dentro— y aun así, de los 47 activos evaluables NINGUNA POSE TOP-1 "
        "coloca un átomo donante (N/O/S) a ≤4.0 Å del metal: mínima 6.13 Å, "
        "mediana 11.04 Å. Esas top-1 son las que produjeron las features y "
        "sostienen el AUC, así que su AUC no es evidencia de reconocimiento del "
        "metal. Los inhibidores de ACE del tipo lisinopril quelan zinc. NO se "
        "sabe si alguna pose descartada sí coordinaba: el checkpoint guardó sólo "
        "la top-1, y afirmar que la búsqueda nunca exploró la coordinación sería "
        "convertir un oráculo ausente en un muestreo fallido. Ver "
        "docs/77_CORRIGENDUM_SITIO_DEL_BENCHMARK_M5_ZN.md §8."
    ),
    "BLOCKED_PROTOCOL_NOT_AVAILABLE": (
        "La diana es metálica y este producto no tiene protocolo validado para "
        "ese metal. Se declara en vez de degradarse a M4 en silencio (§6.1)."
    ),
}
