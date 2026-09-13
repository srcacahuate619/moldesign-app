"""
El consenso de BBB contra 46 fármacos con veredicto clínico conocido.

# Por qué esta prueba existe

La decisión de permeabilidad vivía dentro de `calculate_blood_viability`, que
necesita ADMET-AI cargado —veinte segundos y varios gigabytes— para ejecutarse
una sola vez. No se podía probar, así que no se probaba, y la condición central
llevaba la precedencia mal puesta desde el primer día:

    if cns_mpo >= 4.0 and not is_too_polar and not is_pgp_efflux
       or admet_bbb == 1 or is_small_neutral and not is_pgp_efflux:

`or admet_bbb == 1` es un término suelto: saltaba por encima de los filtros de
polaridad y de P-gp sin mirar la confianza del modelo. Ahora la decisión es una
función pura y esta prueba la ejerce entera sin cargar nada.

# De dónde salen los números

`p_bbb` y `ppb` son la salida del modelo ADMET-AI **empaquetado en esta
instalación**, medida una vez y fijada aquí. Los descriptores son de RDKit. Se
congelan a propósito: esta prueba mide la LÓGICA DEL CONSENSO, no el modelo. Si
algún día se cambia el modelo, la tabla hay que volver a medirla, y el cambio
será visible en el diff — que es justo lo que se quiere.

`clinico` es si el fármaco alcanza el SNC a dosis terapéutica según literatura
de farmacología, no según ningún ajuste de este proyecto.

`via` separa lo que este consenso puede acertar de lo que no. Modela difusión
pasiva; los seis marcados `transportador` entran o se excluyen por un acarreador
o una bomba, y están en la tabla —en vez de curados fuera de ella— para que el
límite se vea. No cuentan en el umbral de aciertos.

# Lo que mide

    antes del arreglo del int()   37/41    el modelo valía 0 para toda molécula
    con el modelo vivo, sin más   33/41    ← arreglar el int() empeoraba
    con este consenso             39/41
"""

from __future__ import annotations

import pytest

from chem.bbb_consenso import (
    UMBRAL_MODELO,
    UMBRAL_MODELO_ANULA_HEURISTICAS,
    decidir_bbb,
)

# (nombre, SMILES, p_bbb, ppb, mw, logp, tpsa, hbd, hba, anillos_aro, clinico, via)
REFERENCIA: list[tuple] = [
    ("imipramina", "CN(C)CCCN1c2ccccc2CCc2ccccc21",
     0.994, 85.54, 280.42, 3.875, 6.48, 0, 2, 2,
     True, "pasiva"),
    ("amitriptilina", "CN(C)CCC=C1c2ccccc2CCc2ccccc21",
     0.9937, 89.31, 277.41, 4.169, 3.24, 0, 1, 2,
     True, "pasiva"),
    ("mirtazapina", "CN1CCN2c3ncccc3Cc3ccccc3C2C1",
     0.9919, 63.79, 265.36, 2.479, 19.37, 0, 3, 2,
     True, "pasiva"),
    ("clozapina", "CN1CCN(CC1)C1=Nc2cc(Cl)ccc2Nc2ccccc21",
     0.9888, 90.93, 326.83, 3.723, 30.87, 1, 4, 2,
     True, "pasiva"),
    ("ketamina", "CNC1(c2ccccc2Cl)CCCCC1=O",
     0.9884, 46.68, 237.73, 2.898, 29.1, 1, 2, 1,
     True, "pasiva"),
    ("risperidona", "Cc1nc2CCCCn2c(=O)c1CCN1CCC(CC1)c1noc2cc(F)ccc12",
     0.9871, 78.77, 410.49, 3.59, 64.16, 0, 5, 3,
     True, "pasiva"),
    ("diazepam", "CN1c2ccc(Cl)cc2C(=NCC1=O)c1ccccc1",
     0.9835, 90.79, 284.75, 3.154, 32.67, 0, 2, 2,
     True, "pasiva"),
    ("cafeina", "Cn1cnc2c1c(=O)n(C)c(=O)n2C",
     0.9819, 21.09, 194.19, -1.029, 61.82, 0, 3, 2,
     True, "pasiva"),
    ("haloperidol", "O=C(CCCN1CCC(O)(c2ccc(Cl)cc2)CC1)c1ccc(F)cc1",
     0.9813, 86.17, 375.87, 4.426, 40.54, 1, 3, 2,
     True, "pasiva"),
    ("donepezilo", "COc1cc2CC(CC3CCN(Cc4ccccc4)CC3)C(=O)c2cc1OC",
     0.9795, 87.65, 379.5, 4.361, 38.77, 0, 4, 2,
     True, "pasiva"),
    ("olanzapina", "CN1CCN(CC1)C1=Nc2cc(C)sc2Nc2ccccc21",
     0.9781, 89.73, 312.44, 3.439, 30.87, 1, 5, 2,
     True, "pasiva"),
    ("fluoxetina", "CNCCC(Oc1ccc(cc1)C(F)(F)F)c1ccccc1",
     0.976, 84.9, 309.33, 4.435, 21.26, 1, 2, 2,
     True, "pasiva"),
    ("sertralina", "CN[C@H]1CC[C@@H](c2ccc(Cl)c(Cl)c2)c2ccccc12",
     0.9739, 92.76, 306.24, 5.18, 12.03, 1, 1, 2,
     True, "pasiva"),
    ("difenhidramina", "CN(C)CCOC(c1ccccc1)c1ccccc1",
     0.9723, 64.21, 255.36, 3.354, 12.47, 0, 2, 2,
     True, "pasiva"),
    ("quetiapina", "OCCOCCN1CCN(CC1)C1=Nc2ccccc2Sc2ccccc12",
     0.9709, 83.21, 383.52, 2.856, 48.3, 1, 6, 2,
     True, "pasiva"),
    ("nicotina", "CN1CCC[C@H]1c1cccnc1",
     0.9648, 12.48, 162.24, 1.848, 16.13, 0, 2, 1,
     True, "pasiva"),
    ("carbamazepina", "NC(=O)N1c2ccccc2C=Cc2ccccc21",
     0.9635, 74.46, 236.27, 3.387, 46.33, 1, 1, 2,
     True, "pasiva"),
    ("teofilina", "Cn1c(=O)c2[nH]cnc2n(C)c1=O",
     0.9618, 31.13, 180.17, -1.04, 72.68, 1, 3, 2,
     True, "pasiva"),
    ("zolpidem", "Cc1ccc(cc1)-c1nc2ccc(C)cn2c1CC(=O)N(C)C",
     0.9569, 85.92, 307.4, 3.249, 37.61, 0, 2, 3,
     True, "pasiva"),
    ("memantina", "CC12CC3(C)CC(N)(C1)CC(C3)C2",
     0.9561, 25.05, 179.31, 2.694, 26.02, 1, 1, 0,
     True, "pasiva"),
    ("propranolol", "CC(C)NCC(O)COc1cccc2ccccc12",
     0.9503, 66.0, 259.35, 2.578, 41.49, 2, 3, 2,
     True, "pasiva"),
    ("morfina", "CN1CC[C@]23c4c5ccc(O)c4O[C@H]2[C@@H](O)C=C[C@H]3[C@H]1C5",
     0.8949, 28.57, 285.34, 1.198, 52.93, 2, 4, 1,
     True, "pasiva"),
    ("fenitoina", "O=C1NC(=O)C(c2ccccc2)(c2ccccc2)N1",
     0.8405, 87.55, 252.27, 1.77, 58.2, 2, 2, 2,
     True, "pasiva"),
    ("lamotrigina", "Nc1nnc(-c2cccc(Cl)c2Cl)c(N)n1",
     0.769, 74.01, 256.1, 2.01, 90.71, 2, 5, 2,
     True, "pasiva"),
    ("domperidona", "O=C1Nc2ccccc2N1CCCN1CCC(CC1)N1C(=O)Nc2cc(Cl)ccc21",
     0.9556, 94.96, 425.92, 3.353, 78.82, 2, 3, 4,
     False, "pasiva"),
    ("sulpirida", "CCN1CCC[C@H]1CNC(=O)c1cc(S(N)(=O)=O)ccc1OC",
     0.786, 26.07, 341.43, 0.557, 101.73, 2, 5, 1,
     False, "pasiva"),
    ("cetirizina", "OC(=O)COCCN1CCN(CC1)C(c1ccccc1)c1ccc(Cl)cc1",
     0.7317, 88.21, 388.9, 3.148, 53.01, 1, 4, 2,
     False, "pasiva"),
    ("aspirina", "CC(=O)Oc1ccccc1C(=O)O",
     0.6582, 63.3, 180.16, 1.31, 63.6, 1, 3, 1,
     False, "pasiva"),
    ("ranitidina", "CNC(=C[N+](=O)[O-])NCCSCc1ccc(CN(C)C)o1",
     0.6006, 37.94, 314.41, 1.459, 83.58, 2, 7, 1,
     False, "pasiva"),
    ("atenolol", "CC(C)NCC(O)COc1ccc(CC(N)=O)cc1",
     0.555, 15.25, 266.34, 0.452, 84.58, 3, 4, 1,
     False, "pasiva"),
    ("acido_salicilico", "OC(=O)c1ccccc1O",
     0.5465, 62.34, 138.12, 1.09, 57.53, 2, 2, 1,
     False, "pasiva"),
    ("cimetidina", "CNC(=NC#N)NCCSCc1nc[nH]c1C",
     0.5395, 31.24, 252.35, 0.597, 88.89, 3, 4, 1,
     False, "pasiva"),
    ("hidroclorotiazida", "NS(=O)(=O)c1cc2c(cc1Cl)NCNS2(=O)=O",
     0.5303, 70.37, 297.75, -0.351, 118.36, 3, 5, 1,
     False, "pasiva"),
    ("manitol", "OC[C@@H](O)[C@@H](O)[C@H](O)[C@H](O)CO",
     0.482, 2.08, 182.17, -3.585, 121.38, 6, 6, 0,
     False, "pasiva"),
    ("dopamina", "NCCc1ccc(O)c(O)c1",
     0.4628, 23.66, 153.18, 0.599, 66.48, 3, 3, 1,
     False, "pasiva"),
    ("fexofenadina", "CC(C)(C(O)=O)c1ccc(cc1)C(O)CCCN1CCC(CC1)C(O)(c1ccccc1)c1ccccc1",
     0.3987, 73.63, 501.67, 5.511, 81.0, 3, 4, 3,
     False, "pasiva"),
    ("sacarosa", "OC[C@H]1O[C@@](CO)(O[C@H]2O[C@H](CO)[C@@H](O)[C@H](O)[C@H]2O)[C@@H](O)[C@@H]1O",
     0.3035, -1.78, 342.3, -5.396, 189.53, 8, 11, 0,
     False, "pasiva"),
    ("furosemida", "NS(=O)(=O)c1cc(C(=O)O)c(NCc2ccco2)cc1Cl",
     0.276, 86.61, 330.75, 1.891, 122.63, 3, 5, 2,
     False, "pasiva"),
    ("metotrexato", "CN(Cc1cnc2nc(N)nc(N)c2n1)c1ccc(cc1)C(=O)N[C@@H](CCC(O)=O)C(O)=O",
     0.2537, 56.19, 454.45, 0.268, 210.54, 5, 10, 3,
     False, "pasiva"),
    ("glicopirrolato", "C[N+]1(C)CCC(C1)OC(=O)C(O)(C1CCCC1)c1ccccc1",
     0.1504, 35.61, 318.44, 2.456, 46.53, 1, 3, 1,
     False, "pasiva"),
    ("penicilina_g", "CC1(C)S[C@@H]2[C@H](NC(=O)Cc3ccccc3)C(=O)N2[C@H]1C(O)=O",
     0.1477, 62.89, 334.4, 0.861, 86.71, 2, 4, 1,
     False, "pasiva"),
    ("acido_valproico", "CCCC(CCC)C(O)=O",
     0.9146, 50.58, 144.21, 2.287, 37.3, 1, 1, 0,
     True, "transportador"),
    ("verapamilo", "COc1ccc(CCN(C)CCCC(C#N)(C(C)C)c2ccc(OC)c(OC)c2)cc1OC",
     0.8799, 83.55, 454.61, 5.093, 63.95, 0, 6, 2,
     True, "transportador"),
    ("gabapentina", "OC(=O)CC1(CN)CCCCC1",
     0.7941, 23.77, 171.24, 1.37, 63.32, 2, 2, 0,
     True, "transportador"),
    ("levodopa", "N[C@@H](Cc1ccc(O)c(O)c1)C(O)=O",
     0.4323, 38.57, 197.19, 0.052, 103.78, 4, 4, 1,
     True, "transportador"),
    ("loperamida", "CN(C)C(=O)C(CCN1CCC(O)(c2ccc(Cl)cc2)CC1)(c1ccccc1)c1ccccc1",
     0.9149, 92.27, 477.05, 5.088, 43.78, 1, 3, 3,
     False, "transportador"),
    ("digoxina", "C[C@@H]1O[C@@H](O[C@@H]2[C@@H](C)O[C@@H](O[C@@H]3[C@@H](C)O[C@@H](O[C@@H]4CC[C@]5(C)[C@@H](CC[C@H]6[C@@H]5C[C@@H](O)[C@]5(C)[C@H](CC[C@]65O)C5=CC(=O)OC5)C4)C[C@H]3O)C[C@H]2O)C[C@H](O)[C@H]1O",
     0.1317, 84.11, 780.95, 2.218, 203.06, 6, 14, 0,
     False, "transportador"),
]

PASIVOS = [f for f in REFERENCIA if f[11] == "pasiva"]
TRANSPORTADOR = [f for f in REFERENCIA if f[11] == "transportador"]

#: Aciertos exigidos sobre los de difusión pasiva. Es lo medido, no una meta:
#: baja este número sólo con una medición que lo justifique.
ACIERTOS_MINIMOS_PASIVA = 39

#: Los dos que este consenso falla, nombrados. Son bases polares cuyo pKa real
#: está lejos del representativo de clase que `ionizacion.py` les asigna. Se
#: dejan fallando a propósito: subir el umbral del modelo a 0.70 arregla la
#: sulpirida y a 0.80 pierde la lamotrigina, y eso es ajustar a la tabla.
FALSOS_POSITIVOS_CONOCIDOS = {"ranitidina", "sulpirida"}

#: Los que entran (o no) por acarreador. Un consenso de difusión pasiva no puede
#: acertarlos, y no se le pide que lo haga.
TRANSPORTE_ACTIVO_CONOCIDO = {"levodopa", "gabapentina", "acido_valproico"}


def _decidir(fila):
    _n, smiles, p, ppb, mw, logp, tpsa, hbd, hba, aro, _clin, _via = fila
    return decidir_bbb(
        smiles, p_modelo=p, mw=mw, logp=logp, tpsa=tpsa, hbd=hbd, hba=hba,
        ppb=ppb, anillos_aromaticos=aro,
    )


def _fila(nombre):
    return next(f for f in REFERENCIA if f[0] == nombre)


# ── El número global ───────────────────────────────────────────────────────

def test_acierta_al_menos_lo_medido_en_difusion_pasiva():
    aciertos = sum(1 for f in PASIVOS if _decidir(f).permeable == f[10])
    fallos = [f[0] for f in PASIVOS if _decidir(f).permeable != f[10]]
    assert aciertos >= ACIERTOS_MINIMOS_PASIVA, (
        f"{aciertos}/{len(PASIVOS)} aciertos, por debajo de "
        f"{ACIERTOS_MINIMOS_PASIVA}. Fallan: {fallos}"
    )


def test_no_pierde_ningun_farmaco_del_snc_por_difusion_pasiva():
    """Un falso negativo es peor que un falso positivo: descarta una molécula."""
    perdidos = [f[0] for f in PASIVOS if f[10] and _decidir(f).permeable is not True]
    assert perdidos == [], f"declara no permeables a fármacos del SNC: {perdidos}"


def test_los_falsos_positivos_son_exactamente_los_declarados():
    """Si aparece uno nuevo, se sabe aquí y no en el panel del usuario."""
    actuales = {f[0] for f in PASIVOS if _decidir(f).permeable and not f[10]}
    assert actuales == FALSOS_POSITIVOS_CONOCIDOS, (
        f"sobran {actuales - FALSOS_POSITIVOS_CONOCIDOS}, "
        f"faltan {FALSOS_POSITIVOS_CONOCIDOS - actuales}"
    )


def test_el_limite_del_transporte_activo_esta_declarado():
    """Lo que no puede acertar se enseña, no se cura fuera del conjunto."""
    fallados = {f[0] for f in TRANSPORTADOR if _decidir(f).permeable != f[10]}
    assert fallados == TRANSPORTE_ACTIVO_CONOCIDO, (
        f"cambió el conjunto de casos de transportador que se fallan: {fallados}"
    )


# ── Los fallos concretos que originaron todo esto ──────────────────────────

def test_el_modelo_flojo_no_salta_por_encima_de_la_polaridad():
    """El atenolol: p = 0.555, y el betabloqueante hidrofílico de manual.

    Con `or admet_bbb == 1` suelto, ese 0.555 lo declaraba permeable pasando
    por encima del filtro de polaridad. Pesaba igual que un 0.98.
    """
    d = _decidir(_fila("atenolol"))
    assert d.permeable is False
    assert d.capa == "4_polar_vence_al_modelo", d.capa
    assert "0.555" in d.motivo


def test_la_dopamina_es_un_cation_no_una_molecula_pequena_y_neutra():
    """La capa «pequeña y neutra» sólo comprobaba la neutralidad de los ácidos.

    La dopamina —catión en más del 99 % a pH 7.4, y el ejemplo de manual de lo
    que NO entra al cerebro— pasaba por ella.
    """
    assert _decidir(_fila("dopamina")).permeable is False


def test_una_carga_permanente_bloquea_pase_lo_que_pase():
    """El glicopirrolato: amonio cuaternario, MPO 5.6 sobre 6, y no entra.

    Se le pasa una probabilidad alta a propósito: ni con el modelo seguro debe
    salir permeable, porque ningún pH neutraliza esa carga.
    """
    f = _fila("glicopirrolato")
    d = decidir_bbb(f[1], p_modelo=0.99, mw=f[4], logp=f[5], tpsa=f[6],
                    hbd=f[7], hba=f[8], ppb=f[3], anillos_aromaticos=f[9])
    assert d.permeable is False
    assert d.capa == "0_carga_permanente"
    assert "amonio_cuaternario" in d.hallazgos


def test_el_acido_salicilico_no_se_salva_por_pesar_138_dalton():
    """La regla anterior era `tiene COOH y MW > 150`. Ese 150 no venía de nada."""
    d = _decidir(_fila("acido_salicilico"))
    assert d.permeable is False
    assert d.capa == "1_anion"


def test_una_amina_basica_no_se_bloquea_como_anion():
    """La asimetría ácido/base es deliberada: un catión conserva fracción neutra."""
    for nombre in ("fluoxetina", "difenhidramina", "haloperidol", "morfina"):
        d = _decidir(_fila(nombre))
        assert d.permeable is True, f"{nombre}: {d.capa} — {d.motivo}"


# ── Las propiedades de la forma, no de los fármacos ────────────────────────

def test_sin_prediccion_del_modelo_el_veredicto_es_desconocido_no_negativo():
    """`None` y `False` no significan lo mismo, y el panel los pinta distinto."""
    d = decidir_bbb("CN(C)CCOC(c1ccccc1)c1ccccc1", p_modelo=None, mw=255.4,
                    logp=3.35, tpsa=12.5, hbd=0, hba=2, ppb=64.2,
                    anillos_aromaticos=2)
    assert d.permeable is None
    assert d.capa == "sin_prediccion"


def test_una_regla_estructural_se_pronuncia_aunque_no_haya_modelo():
    """El anión no necesita al modelo para no cruzar."""
    d = decidir_bbb("CC(=O)Oc1ccccc1C(=O)O", p_modelo=None, mw=180.16,
                    logp=1.31, tpsa=63.6, hbd=1, hba=3, ppb=63.3,
                    anillos_aromaticos=1)
    assert d.permeable is False
    assert d.capa == "1_anion"


def test_el_modelo_confiado_no_lo_veta_una_heuristica():
    """Lo que se pidió: más confianza para poder anular las reglas de pulgar."""
    polar = dict(mw=300.0, logp=0.5, tpsa=95.0, hbd=4, hba=5, ppb=50.0,
                 anillos_aromaticos=1)
    seguro = decidir_bbb("CCOc1ccccc1", p_modelo=0.97, **polar)
    flojo = decidir_bbb("CCOc1ccccc1", p_modelo=0.60, **polar)
    assert seguro.permeable is True and seguro.capa == "3_modelo_confiado"
    assert flojo.permeable is False and flojo.capa == "4_polar_vence_al_modelo"


@pytest.mark.parametrize("p", [0.0, 0.49])
def test_por_debajo_del_umbral_el_modelo_no_vota(p):
    d = decidir_bbb("CCOc1ccccc1", p_modelo=p, mw=200.0, logp=2.0, tpsa=30.0,
                    hbd=0, hba=2, ppb=50.0, anillos_aromaticos=1)
    assert d.permeable is False
    assert d.capa == "defecto"


def test_los_umbrales_estan_ordenados():
    assert 0.0 < UMBRAL_MODELO < UMBRAL_MODELO_ANULA_HEURISTICAS <= 1.0


def test_todo_veredicto_trae_su_motivo():
    """Un booleano sin explicación es lo que dejó pasar el fallo original."""
    for f in REFERENCIA:
        d = _decidir(f)
        assert d.capa, f[0]
        assert len(d.motivo) > 30, f"{f[0]}: motivo pobre — {d.motivo!r}"
        assert d.p_modelo == f[2]
