"""Las traducciones por plantilla preservan datos y son todo-o-nada."""

from collections import Counter
import re

from core import i18n
from core.i18n_catalog import ENGLISH_MESSAGES
from core.i18n_plantillas import (
    PLANTILLAS_ES_EN,
    _aplicar_plantilla,
    _compilar,
    traducir,
)


def test_una_coincidencia_exacta_y_espacios_normalizados(monkeypatch):
    monkeypatch.setitem(ENGLISH_MESSAGES, "Receptor no disponible.", "Receptor unavailable.")

    assert traducir("Receptor no disponible.", "en") == "Receptor unavailable."
    assert traducir("Receptor   no\ndisponible.", "en-US") == "Receptor unavailable."


def test_plantilla_conserva_numeros_sin_reformatear():
    texto = (
        "Se pidieron 004 conformaciones y se generaron 03.500: "
        "la cobertura geométrica es menor que la solicitada."
    )

    assert traducir(texto, "en") == (
        "004 conformers were requested and 03.500 were generated: "
        "geometric coverage is lower than requested."
    )


def test_plantilla_con_varios_marcadores_preserva_la_lista():
    lista = "CC(O)N; [datos del usuario]"
    texto = f"2 elegidos de 8 del catálogo: {lista}"

    assert traducir(texto, "en") == f"2 selected out of 8 in the catalog: {lista}"


def test_plantillas_de_la_capa_dossier_traducen_composiciones_completas():
    assert traducir(
        "7E2Y · cadenas A (medido sobre los bytes del PDBQT hasheado)", "en"
    ) == "7E2Y · chains A (measured from the hashed PDBQT bytes)"  # antes daba «cadenas A» por bueno (B01 de la QA)
    assert traducir(
        "0.2750 · M5-Zn-v1 — score de ranking derivado, no una afinidad ni una medida experimental",
        "en",
    ) == (
        "0.2750 · M5-Zn-v1 — derived ranking score, not an affinity or experimental measurement"
    )
    assert traducir(
        "3 truncada(s); 1 en el sitio: A:42 SER→ALA (4.2 Å)", "en"
    ) == "Truncated side-chain count: 3; site count: 1; residues: A:42 SER→ALA (4.2 Å)"
    assert traducir(
        "Pose principal: top-1 de Vina (#2) · sin recomendación del selector", "en"
    ) == "Primary pose: Vina top-1 (#2) · no selector recommendation"
    assert traducir(
        "El ligando del cristal (ATP A:501) se retiró como parte de la corrida.", "en"
    ) == "The crystal ligand (ATP A:501) was removed as part of the run."
    assert traducir(
        "15 elegidos de 15 del catálogo: A:ALA28, A:ARG8, B:ASP25 … y 3 más", "en"
    ) == "15 selected out of 15 in the catalog: A:ALA28, A:ARG8, B:ASP25 … and 3 more"
    assert traducir("1HSG · cadena A", "en") == "1HSG · chain A"
    assert traducir(
        "1HSG · cadenas A+B — el caso declaró la cadena A; el PDBQT acoplado "
        "contiene A+B (medido sobre los bytes del PDBQT hasheado)",
        "en",
    ) == (
        "1HSG · chains A+B — the case declared chain A; the docked PDBQT "
        "contains A+B (measured from the hashed PDBQT bytes)"
    )
    assert traducir(
        "Microstate closest to the one predicted at pH 7.4, de 4 enumerados", "en"
    ) == "Microstate closest to the one predicted at pH 7.4, out of 4 enumerated"
    assert traducir(
        "9 de 9 poses recibieron veredicto y ninguna falla los controles de química o geometría. "
        "Motor: posebusters:0.6.5:dock. Cobertura 9/9 poses.",
        "en",
    ) == (
        "9 of 9 poses received a verdict, and none failed the chemistry or geometry checks. "
        "Engine: posebusters:0.6.5:dock. Coverage: 9/9 poses."
    )
    assert traducir(
        "universal model; fallback: Family 'protease' has no validated model "
        "(quality gate: p 0.266 >= 0.05) — the universal model was used.. "
        "El motor de acoplamiento y su version se declaran en la traza de "
        "reproducibilidad, no aqui: son identidades distintas.",
        "en",
    ) == (
        "universal model; fallback: Family 'protease' has no validated model "
        "(quality gate: p 0.266 >= 0.05) — the universal model was used. "
        "The docking engine and its version are listed in the reproducibility "
        "trace, not here; they are distinct identities."
    )
    assert traducir(
        "El PDB «1BN1» no es ninguno de los tres perfiles de M5-Zn "
        "(1GKC/MMP9, 1O86/ACE, 3DC3/CA2). M5-Zn prepara, conserva el Zn, "
        "ejecuta Vina y calcula señales diagnósticas, pero no hereda los pesos "
        "de otra diana: el score compuesto queda sin calcular.",
        "en",
    ) == (
        "PDB “1BN1” is not one of the three M5-Zn profiles "
        "(1GKC/MMP9, 1O86/ACE, 3DC3/CA2). M5-Zn prepares the receptor, retains Zn, "
        "runs Vina, and calculates diagnostic signals, but does not inherit weights "
        "from another target; the composite score is not calculated."
    )
    assert traducir(
        "Preparación en condición desolvatada: se retiraron 2 aguas cristalográficas "
        "de la caja de acoplamiento, 1 de ellas con 3 o más contactos a menos de "
        "3.5 Å con el receptor (la mejor coordinada, 5). Si alguna de esas aguas "
        "forma parte del reconocimiento en esta diana —la catalítica de la proteasa "
        "del VIH-1, la red de la bisagra en varias quinasas—, los contactos de esta "
        "corrida no la incluyen.",
        "en",
    ).startswith("Desolvated preparation: 2 crystallographic waters were removed")
    assert traducir(
        "Se persistieron los pesos normalizados usados realmente en esta corrida. "
        "Componentes ausentes en esta corrida: vina.",
        "en",
    ) == (
        "The normalized weights actually used in this run were persisted. "
        "Components missing from this run: vina."
    )


def test_plantilla_preserva_espacios_y_saltos_de_linea_dentro_del_dato():
    lista = "CCO  ;\t[datos]\nID   "
    texto = f"2 elegidos de 8 del catálogo:\n{lista}"

    assert traducir(texto, "en") == f"2 selected out of 8 in the catalog: {lista}"


def test_marcador_repetido_captura_una_vez_y_reutiliza_el_valor():
    plantilla = _compilar(
        "La corrida {task_id} cita {task_id}.",
        "Run {task_id} cites {task_id}.",
    )

    assert _aplicar_plantilla(plantilla, "La corrida run-0007 cita run-0007.") == (
        "Run run-0007 cites run-0007."
    )
    assert _aplicar_plantilla(plantilla, "La corrida run-0007 cita run-0008.") is None


def test_las_plantillas_declaradas_usan_los_mismos_marcadores():
    for español, inglés in PLANTILLAS_ES_EN:
        marcadores_es = Counter(re.findall(r"\{([A-Za-z_][A-Za-z0-9_]*)\}", español))
        marcadores_en = Counter(re.findall(r"\{([A-Za-z_][A-Za-z0-9_]*)\}", inglés))
        assert marcadores_es == marcadores_en


def test_varias_frases_se_traducen_solo_si_todas_coinciden(monkeypatch):
    primera = "Esta corrida es anterior al sellado de los residuos de referencia."
    segunda = "No se sustituyen por los del catálogo: podrían no ser los que se usaron."
    monkeypatch.setitem(ENGLISH_MESSAGES, primera, "This run predates the recording of reference residues.")
    monkeypatch.setitem(
        ENGLISH_MESSAGES,
        segunda,
        "They are not replaced with the catalog ones: they may not be the ones used.",
    )
    texto = primera + " " + segunda
    monkeypatch.delitem(ENGLISH_MESSAGES, texto, raising=False)

    assert traducir(texto, "en") == (
        "This run predates the recording of reference residues. "
        "They are not replaced with the catalog ones: they may not be the ones used."
    )
    assert traducir("Nombre de molécula del catálogo: aspirina", "en") == (
        "Nombre de molécula del catálogo: aspirina"
    )
    assert traducir("2 del catálogo: Aspirina", "en") == "2 from the catalog: Aspirina"

    monkeypatch.delitem(ENGLISH_MESSAGES, segunda)
    assert traducir(texto, "en") == texto


def test_traduccion_por_frases_conserva_el_separador_original(monkeypatch):
    primera = "La corrida terminó correctamente."
    segunda = "El resultado sigue siendo provisional."
    monkeypatch.setitem(ENGLISH_MESSAGES, primera, "The run completed successfully.")
    monkeypatch.setitem(ENGLISH_MESSAGES, segunda, "The result remains provisional.")
    separador = "\n\t"
    texto = primera + separador + segunda

    assert traducir(texto, "en") == (
        "The run completed successfully." + separador + "The result remains provisional."
    )


def test_nombre_de_molecula_que_parece_plantilla_no_casa_sin_la_frase_completa():
    nombre = "Se pidieron 4 conformaciones"

    assert traducir(nombre, "en") == nombre


def test_espanol_y_textos_sin_coincidencia_salen_byte_a_byte_iguales():
    texto = "Se pidieron 4 conformaciones y se generaron 2: cobertura parcial."

    assert traducir(texto, "es") == texto
    assert traducir(texto, "fr") == texto
    assert traducir(texto, "en") == texto


def test_translate_text_delega_al_mismo_motor_con_el_locale_de_la_peticion():
    texto = "2 elegidos de 9 del catálogo: CCO"
    token = i18n.set_request_locale("en-US")
    try:
        assert i18n.translate_text(texto) == "2 selected out of 9 in the catalog: CCO"
    finally:
        i18n.reset_request_locale(token)
