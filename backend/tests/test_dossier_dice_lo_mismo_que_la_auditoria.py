"""El PDF y el paquete dicen de las especies del sitio lo mismo que la auditoría de Preparación.

Hasta el 2026-10-22 eran dos cálculos distintos de la misma pregunta («¿qué retiró la preparación junto al sitio?»):

- la auditoría (`POST /evaluation/dossier/{id}/preparacion`, y `preparacion/audit.json` en el ZIP) usa la distancia al ligando
  y marca ABSTENCIÓN si se retiró un metal o un cofactor orgánico a 6 Å o menos, o un cofactor que el ligando no desplaza
  (hemo, FAD, FMN, NADP, Fe–S) como ligando del cristal;
- la tabla «Preparación del sistema y supuestos» del PDF (`model._campo_de_especies`) usaba la caja y un solo estado, REVISAR,
  y dejaba REGISTRADO un hemo retirado como ligando del cristal.

El mismo ZIP llevaba, pues, un PDF que decía «REVISAR» y un `audit.json` que decía «ABSTENCIÓN» del mismo zinc. Un paquete cuyo
propósito es que un tercero lea las mismas decisiones no puede decir dos cosas. Lo hallaron Sol 6.1 (MET_datos, MET-D-A05) y la
lectura del código; estas pruebas fijan que el dossier copia los campos de la auditoría en vez de recalcularlos.
"""

from __future__ import annotations

import pytest

from services.dossier.contexto_estructural import ContextoEstructural, no_medido
from services.dossier.model import build_case_dossier
from services.dossier.preparacion import build_preparacion
from services.dossier.taxonomy import Estado
from tests.fixtures_dossier import caso_completo, resultado_completo
from tests.test_diff_de_especies_de_la_corrida import _diff

CLAVES = ("entorno.metales_cofactores", "entorno.aguas", "entorno.otras_especies")


def _caso(receptor_prep: dict):
    caso = caso_completo()
    resultado = resultado_completo()
    protocolo = dict(resultado.docking_protocol)
    protocolo["execution_provenance"] = {"receptor_prep": receptor_prep}
    resultado.docking_protocol = protocolo
    caso["eval_result"] = resultado
    return caso


def _ambos(receptor_prep: dict, contexto: ContextoEstructural | None):
    caso = _caso(receptor_prep)
    dossier = build_case_dossier(**caso, contexto=contexto)
    auditoria = build_preparacion(dossier, caso["eval_result"], caso["projection"], contexto)
    requisitos = {r["clave"]: r for bloque in auditoria["bloques"] for r in bloque["requisitos"]}
    return dossier, requisitos


def _con_diff(retiradas: list[dict]) -> dict:
    diff = _diff()
    diff["near_site"] = {**diff["near_site"], "removed": retiradas}
    return {"source": "meeko_report", "species_diff": diff}


def _fila(nombre: str, categoria: str, cadena: str = "A", numero: str = "301", distancia: float = 0.0) -> dict:
    return {"name": nombre, "category": categoria, "chain": cadena, "residue_number": numero,
            "insertion_code": "", "distance_to_box_A": distancia}


def _medido(**distancias: float) -> ContextoEstructural:
    """Un contexto medido: `distancias` es «NOMBRE_cadena_numero» → Å al ligando."""
    especies = {}
    for clave, d in distancias.items():
        nombre, cadena, numero = clave.split("_")
        especies[(cadena, numero, "", nombre)] = d
    return ContextoEstructural(medido=True, referencia="Pose top-1 y ligando del cristal LIG A:601", especies=especies)


CASOS = {
    "sin_diff": ({"source": "meeko_report", "recipe_hash": "a" * 64}, None),
    "congelado": ({"source": "durable_receptor_snapshot"}, None),
    "zinc_y_hemo_desde_la_caja": ({"source": "meeko_report", "species_diff": _diff()}, None),
    "zinc_y_hemo_no_medidos": ({"source": "meeko_report", "species_diff": _diff()}, no_medido("No se pudieron medir las distancias al ligando: las distancias se miden desde la caja.")),
    # El caso de 1RKP: el metal está dentro de la caja pero a más de 6 Å del ligando.
    "metal_lejos_del_ligando": (
        {"source": "meeko_report", "species_diff": _diff()}, _medido(ZN_A_301=7.0, HEM_B_701=8.5)),
    "metal_junto_al_ligando": (
        {"source": "meeko_report", "species_diff": _diff()}, _medido(ZN_A_301=2.1, HEM_B_701=8.5)),
    # El caso de 4NY4 al revés: un cofactor que el ligando no desplaza, retirado como ligando del cristal.
    "hemo_retirado_como_ligando": (_con_diff([_fila("HEM", "site_ligand", numero="601")]), None),
    "solo_aguas_y_ligando": (
        _con_diff([_fila("HOH", "water", numero="401"), _fila("LIG", "site_ligand", numero="601")]), None),
    "otra_especie": (_con_diff([_fila("SO4", "other_heteroatom", numero="501")]), None),
}


@pytest.mark.parametrize("nombre", sorted(CASOS))
def test_el_dossier_copia_de_la_auditoria_las_especies_del_sitio(nombre):
    receptor_prep, contexto = CASOS[nombre]
    dossier, requisitos = _ambos(receptor_prep, contexto)
    campos = {c.etiqueta: c.as_dict() for c in dossier.preparacion}
    for clave in CLAVES:
        pedido = requisitos[clave]
        assert pedido["etiqueta"] in campos, f"el dossier no tiene «{pedido['etiqueta']}» ({clave})"
        propio = campos[pedido["etiqueta"]]
        for atributo in ("estado", "valor", "razon", "valor_es_clasificacion"):
            assert propio[atributo] == pedido[atributo], (clave, atributo)


def test_el_zinc_retirado_junto_al_sitio_abstiene_en_el_pdf_como_en_la_auditoria():
    dossier, requisitos = _ambos(*CASOS["zinc_y_hemo_desde_la_caja"])
    metales = next(c for c in dossier.preparacion if c.etiqueta == "Metales y cofactores junto al sitio")
    assert requisitos["entorno.metales_cofactores"]["estado"] == Estado.ABSTENCION.value
    assert metales.estado == Estado.ABSTENCION
    assert "ZN A:301" in metales.texto and "HEM B:701" in metales.texto


def test_un_metal_a_mas_de_6_A_del_ligando_no_abstiene_ni_en_el_pdf():
    """Lo que la auditoría ya distinguía y el PDF no: el metal estaba en la caja, pero lejos del ligando."""
    dossier, requisitos = _ambos(*CASOS["metal_lejos_del_ligando"])
    metales = next(c for c in dossier.preparacion if c.etiqueta == "Metales y cofactores junto al sitio")
    assert requisitos["entorno.metales_cofactores"]["estado"] == Estado.REGISTRADO.value
    assert metales.estado == Estado.REGISTRADO
    assert "ZN A:301 (7 Å)" in metales.texto


def test_un_hemo_retirado_como_ligando_del_cristal_no_sale_registrado_en_el_pdf():
    dossier, _ = _ambos(*CASOS["hemo_retirado_como_ligando"])
    metales = next(c for c in dossier.preparacion if c.etiqueta == "Metales y cofactores junto al sitio")
    assert metales.estado == Estado.ABSTENCION


def test_la_referencia_de_las_distancias_viaja_al_pdf_cuando_se_midio():
    dossier, requisitos = _ambos(*CASOS["metal_junto_al_ligando"])
    etiquetas = [c.etiqueta for c in dossier.preparacion]
    assert requisitos["entorno.referencia"]["etiqueta"] in etiquetas


def test_sin_contexto_el_dossier_sigue_construyendose_como_antes():
    """`build_case_dossier` sin `contexto` (pruebas, instantáneas): la auditoría mide desde la caja."""
    caso = _caso({"source": "meeko_report", "species_diff": _diff()})
    dossier = build_case_dossier(**caso)
    assert any(c.etiqueta == "Metales y cofactores junto al sitio" for c in dossier.preparacion)


def test_un_diff_sin_margen_es_no_evaluado_en_el_pdf():
    """El PDF antiguo lo decía y la auditoría copiada no puede perderlo: sin margen no hay «a X Å o menos»."""
    diff = _diff()
    diff["near_site"] = {k: v for k, v in diff["near_site"].items() if k != "margin_A"}
    dossier = build_case_dossier(**_caso({"source": "meeko_report", "species_diff": diff}))
    metales = next(c for c in dossier.preparacion if c.etiqueta == "Metales y cofactores junto al sitio")
    assert metales.estado == Estado.NO_EVALUADO
    assert "margen del sitio" in metales.razon


def test_los_recuentos_globales_van_aparte_y_sin_veredicto():
    """Es lo único del diff que la auditoría no trae: registros HETATM de toda la estructura, no moléculas."""
    dossier, _ = _ambos(*CASOS["zinc_y_hemo_desde_la_caja"])
    campo = next(c for c in dossier.preparacion if c.etiqueta == "Registros HETATM retirados del ensamblaje")
    assert campo.estado == Estado.REGISTRADO
    assert campo.valor.startswith("aguas ") and "metales " in campo.valor


def test_sin_diff_no_hay_fila_de_recuentos_globales():
    dossier, _ = _ambos(*CASOS["sin_diff"])
    assert not any(c.etiqueta == "Registros HETATM retirados del ensamblaje" for c in dossier.preparacion)


ETIQUETAS_DEL_SITIO = ("Metales y cofactores junto al sitio", "Aguas junto al sitio", "Otras especies junto al sitio",
                       "Referencia de las distancias", "Registros HETATM retirados del ensamblaje",
                       "Especies conservadas como otro residuo (Å a la caja)")


@pytest.mark.parametrize("nombre", sorted(CASOS))
def test_el_pdf_en_ingles_traduce_las_filas_del_sitio(nombre):
    """Las filas que el PDF ahora copia de la auditoría no pueden quedar en castellano en la versión inglesa."""
    from core.i18n_plantillas import traducir
    from services.dossier.localization import traducir_dossier

    receptor_prep, contexto = CASOS[nombre]
    dossier, _ = _ambos(receptor_prep, contexto)
    en = traducir_dossier(dossier, "en")
    es = {c.etiqueta: c for c in dossier.preparacion}
    pendientes = []
    for c in en.preparacion:
        original = next((o for o in dossier.preparacion if traducir(o.etiqueta, "en") == c.etiqueta), None)
        if original is None or original.etiqueta not in ETIQUETAS_DEL_SITIO:
            continue
        for parte, antes, despues in (("etiqueta", original.etiqueta, c.etiqueta), ("razon", original.razon, c.razon),
                                      ("valor", original.valor if original.estado.es_afirmativo
                                       or original.valor_es_clasificacion else None, c.valor)):
            # La fila de conversiones no lleva palabras («MSE A:2 (0.0 Å) → MET»): idéntica en los dos idiomas a propósito.
            if antes and antes == despues and not (parte == "valor" and "→" in antes):
                pendientes.append((original.etiqueta, parte, antes[:90]))
    assert not pendientes, pendientes


def test_la_conversion_de_selenometionina_sigue_en_el_pdf():
    """El PDF antiguo decía «conservado MSE A:2 … como MET»; la auditoría no lo dice y no se puede perder."""
    dossier, _ = _ambos(*CASOS["zinc_y_hemo_desde_la_caja"])
    campo = next(c for c in dossier.preparacion if c.etiqueta.startswith("Especies conservadas como otro residuo"))
    assert campo.estado == Estado.REGISTRADO
    assert campo.valor == "MSE A:2 (0.0 Å) → MET"


def test_sin_conversiones_no_hay_fila():
    diff = _diff()
    diff["near_site"] = {**diff["near_site"], "preserved": []}
    dossier, _ = _ambos({"source": "meeko_report", "species_diff": diff}, None)
    assert not any(c.etiqueta.startswith("Especies conservadas como otro residuo") for c in dossier.preparacion)
