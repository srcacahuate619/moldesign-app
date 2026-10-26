"""Preparación mide «junto al sitio» desde el ligando, no desde la caja (punto 2, 2026-10-10).

Medido con Vina real en la auditoría del 10-10: el hueco que bloqueaba 4NC3 estaba a
20 Å de la serotonina acoplada (14 Å del ligando del cristal) y de 70 a 347 aguas
listadas por corrida sólo 1 a 10 estaban a ≤ 4 Å del ligando. Con las distancias
medidas (`services/dossier/contexto_estructural.py`) cuentan las especies a ≤ 6 Å,
las aguas a ≤ 4 Å y los huecos y residuos a ≤ 8 Å. Sin ellas, el criterio de la caja
de siempre, y la auditoría dice por qué.
"""

from __future__ import annotations

import copy

import pytest

from core.i18n_plantillas import _PARECE_CASTELLANO
from services.dossier.contexto_estructural import ContextoEstructural, no_medido
from services.dossier.localization import traducir_dossier
from services.dossier.model import build_case_dossier
from services.dossier.preparacion import _pka_cerca_del_ph, build_preparacion
from tests.test_diff_de_especies_de_la_corrida import _diff
from tests.test_preparacion_auditoria import _con_procedencia, _requisito

HUECO = {"chain": "A", "after": "ALA 197", "before": "VAL 199", "c_n_distance_A": 4.79,
         "missing_declared": 1, "distance_to_box_A": 1.25, "site_critical": True}


def _caso(**ligand_state) -> dict:
    caso = _con_procedencia(_diff(), **ligand_state)
    prov = copy.deepcopy(caso["eval_result"].docking_protocol["execution_provenance"])
    prov["receptor_prep"]["backbone_gaps"] = [dict(HUECO)]
    prov["receptor_prep"]["truncated_sidechains"] = [
        {"chain": "A", "residue_number": "118", "insertion_code": "", "name": "GLU",
         "action": "truncado a ALA", "distance_to_box_A": 0.0, "site_critical": True}]
    caso["eval_result"].docking_protocol = {**caso["eval_result"].docking_protocol, "execution_provenance": prov}
    return caso


def _especies(distancia_metal: float, distancia_agua: float) -> dict:
    """Las especies del fixture a la distancia pedida: metales y cofactores a una, aguas a otra."""
    salida = {}
    for fila in _diff()["near_site"]["removed"] + _diff()["near_site"]["preserved"]:
        clave = (fila["chain"], fila["residue_number"], fila["insertion_code"], fila["name"])
        salida[clave] = distancia_agua if fila["category"] == "water" else distancia_metal
    return salida


def _contexto(*, metal: float = 19.2, agua: float = 9.0, hueco: float = 20.2, truncada: float = 16.9,
              **extra) -> ContextoEstructural:
    return ContextoEstructural(
        medido=True, referencia="Pose top-1 y ligando del cristal LIG A:601",
        especies=_especies(metal, agua),
        huecos={("A", "ALA 197", "VAL 199"): hueco},
        truncadas={("A", "118", ""): truncada},
        excluidas=extra.pop("excluidas", {}),
        plantillas=extra.pop("plantillas", [("A:131", "HIS", "HIE", 2.8), ("A:57", "ASP", "ASH", 4.1)]),
        disulfuros_rotos=extra.pop("disulfuros_rotos", []), disulfuros_totales=extra.pop("disulfuros_totales", 2),
        disulfuros_sin_evaluar=extra.pop("disulfuros_sin_evaluar", None),
        altlocs=extra.pop("altlocs", []), recorte=extra.pop("recorte", None),
    )


def _auditar(caso: dict, contexto: ContextoEstructural | None) -> dict:
    return build_preparacion(build_case_dossier(**caso), caso["eval_result"], caso["projection"], contexto)


class TestEspecies:
    def test_un_metal_lejos_del_ligando_no_bloquea(self):
        auditoria = _auditar(_caso(), _contexto(metal=19.2))
        metales = _requisito(auditoria, "entorno.metales_cofactores")
        assert metales["estado"] == "REGISTRADO"
        assert metales["valor"].startswith("Ninguno retirado a 6 Å o menos del ligando; más lejos: ")
        assert "ZN A:301 (19.2 Å)" in metales["valor"]
        assert "entorno.metales_cofactores" not in auditoria["bloqueantes"]

    def test_un_metal_junto_al_ligando_bloquea(self):
        auditoria = _auditar(_caso(), _contexto(metal=2.3))
        metales = _requisito(auditoria, "entorno.metales_cofactores")
        assert metales["estado"] == "ABSTENCION"
        assert metales["valor"].startswith("Retirados a 6 Å o menos del ligando: ")
        assert "ZN A:301 (2.3 Å)" in metales["valor"]

    def test_sin_medida_el_criterio_de_la_caja_sigue_y_se_declara(self):
        auditoria = _auditar(_caso(), no_medido("No se encontró el archivo de origen del receptor: las "
                                                "distancias se miden desde la caja."))
        assert _requisito(auditoria, "entorno.metales_cofactores")["estado"] == "ABSTENCION"
        referencia = _requisito(auditoria, "entorno.referencia")
        assert referencia["estado"] == "NO_EVALUADO"
        assert "desde la caja" in referencia["razon"]

    def test_sin_contexto_no_hay_requisitos_nuevos(self):
        """Quien llama sin contexto (pruebas antiguas, otras rutas) ve la auditoría de siempre."""
        caso = _caso()
        auditoria = build_preparacion(build_case_dossier(**caso), caso["eval_result"], caso["projection"])
        claves = {r["clave"] for b in auditoria["bloques"] for r in b["requisitos"]}
        assert not claves & {"entorno.referencia", "receptor.altlocs", "receptor.disulfuros", "receptor.recorte"}

    def test_las_aguas_que_pueden_puentear_se_nombran_y_el_resto_se_cuenta(self):
        cerca = _requisito(_auditar(_caso(), _contexto(agua=3.1)), "entorno.aguas")
        assert cerca["estado"] == "REVISAR"
        assert cerca["valor"].startswith("1 retirada(s) a 4 Å o menos del ligando: HOH A:401 (3.1 Å)")
        lejos = _requisito(_auditar(_caso(), _contexto(agua=9.0)), "entorno.aguas")
        assert lejos["estado"] == "REGISTRADO"
        # El recuento incluye el margen del sitio: «en la caja» no lo decía (FEP-06-PRE: 11 frente a 7 en P01).
        assert lejos["valor"].startswith("Ninguna retirada a 4 Å o menos del ligando; 1 retirada(s) a 6 Å o menos "
                                         "de la caja")
        ingles = _requisito(traducir_dossier(_auditar(_caso(), _contexto(agua=9.0)), "en"), "entorno.aguas")
        assert "1 removed within 6 Å of the box" in ingles["valor"]


class TestResiduos:
    def test_un_hueco_lejos_del_ligando_no_bloquea_aunque_toque_la_caja(self):
        """4NC3: 1,25 Å de la caja, 20 Å de la pose."""
        auditoria = _auditar(_caso(), _contexto(hueco=20.2))
        huecos = _requisito(auditoria, "receptor.huecos")
        assert huecos["estado"] == "REVISAR"
        assert "todos a más de 8 Å del ligando" in huecos["valor"]
        assert "20.2 Å del ligando" in huecos["valor"]
        assert "receptor.huecos" not in auditoria["bloqueantes"]

    def test_las_poses_de_otro_rango_junto_a_un_hueco_se_dicen(self):
        """La pose 1 lejos del corte no basta: las demás también se ofrecen al investigador."""
        contexto = _contexto(hueco=20.2)
        contexto.poses_medidas = 9
        contexto.huecos_poses = {("A", "ALA 197", "VAL 199"): [3, 5]}
        auditoria = _auditar(_caso(), contexto)
        huecos = _requisito(auditoria, "receptor.huecos")
        assert huecos["estado"] == "REVISAR"
        assert ("2 de las 9 poses guardadas quedan a 8 Å o menos de un corte del esqueleto (rangos 3,5): acoplan "
                "contra el bucle ausente") in huecos["razon"]
        ingles = _requisito(traducir_dossier(auditoria, "en"), "receptor.huecos")
        assert "2 of the 9 saved poses lie within 8 Å of a backbone break (ranks 3,5)" in ingles["razon"]
        assert not _PARECE_CASTELLANO.search(ingles["razon"]), ingles["razon"]

    def test_un_hueco_que_alcanza_la_caja_sin_poses_cerca_se_dice(self):
        """5TBO: VAL343→GLU356 a 1,6 Å de la caja y a 20 Å del inhibidor; ninguna de las 9 poses llegó."""
        contexto = _contexto(hueco=20.2)
        contexto.poses_medidas = 9
        contexto.huecos_poses = {("A", "ALA 197", "VAL 199"): []}
        auditoria = _auditar(_caso(), contexto)
        huecos = _requisito(auditoria, "receptor.huecos")
        assert huecos["estado"] == "REVISAR"
        assert ("1 corte(s) a 6 Å o menos de la caja: Vina busca junto a ellos, y ninguna de las 9 poses "
                "guardadas quedó a 8 Å o menos.") in huecos["razon"]
        ingles = _requisito(traducir_dossier(auditoria, "en"), "receptor.huecos")
        assert "none of the 9 saved poses came within 8 Å" in ingles["razon"]
        assert not _PARECE_CASTELLANO.search(ingles["razon"]), ingles["razon"]

    def test_sin_poses_medidas_el_hueco_lejano_dice_lo_de_siempre(self):
        huecos = _requisito(_auditar(_caso(), _contexto(hueco=20.2)), "receptor.huecos")
        assert huecos["razon"].endswith("necesita esos extremos capados o modelados.")

    def test_un_hueco_junto_al_ligando_bloquea(self):
        """3GEN: el lazo rico en glicina a 3,7 Å del ibrutinib."""
        auditoria = _auditar(_caso(), _contexto(hueco=3.65))
        huecos = _requisito(auditoria, "receptor.huecos")
        assert huecos["estado"] == "ABSTENCION"
        assert huecos["ubicacion"][0]["distance_to_ligand_A"] == 3.65
        assert auditoria["estado"] == "BLOQUEADO"

    def test_las_truncadas_se_miden_desde_el_ligando(self):
        lejos = _requisito(_auditar(_caso(), _contexto(truncada=16.9)), "receptor.cadenas_truncadas")
        # Las de lejos también llevan su identificador (P04 de FEP-06-PRE sólo decía «2 truncada(s)»).
        assert lejos["valor"] == "1 truncada(s); todas a más de 8 Å del ligando; resto: A:118 GLU→ALA (16.9 Å)"
        ingles = _requisito(traducir_dossier(_auditar(_caso(), _contexto(truncada=16.9)), "en"),
                            "receptor.cadenas_truncadas")
        assert ingles["valor"] == "1 truncated; all more than 8 Å from the ligand; rest: A:118 GLU→ALA (16.9 Å)"
        cerca = _requisito(_auditar(_caso(), _contexto(truncada=5.6)), "receptor.cadenas_truncadas")
        assert cerca["valor"] == "1 truncada(s); 1 a 8 Å o menos del ligando: A:118 GLU→ALA (5.6 Å)"

    def test_la_proteina_excluida_cuenta_desde_el_ligando(self):
        vacia = _requisito(_auditar(_caso(), _contexto(excluidas={})), "receptor.cadenas_excluidas")
        assert vacia["estado"] == "REGISTRADO"
        llena = _requisito(_auditar(_caso(), _contexto(excluidas={"B": 6})), "receptor.cadenas_excluidas")
        assert llena["estado"] == "REVISAR"
        assert llena["valor"].endswith("por cadena: B 6")

    def test_las_his_del_sitio_se_dicen(self):
        protonacion = _requisito(_auditar(_caso(), _contexto()), "receptor.protonacion")
        assert "His a 8 Å o menos del ligando: A:131 HIE (2.8 Å)." in protonacion["razon"]
        assert "Estados no estándar a 8 Å o menos del ligando: A:57 ASH (4.1 Å)." in protonacion["razon"]

    def test_recorte_disulfuros_y_altlocs(self):
        contexto = _contexto(
            recorte={"radio_A": 26.0, "residuos_receptor": 176, "residuos_cadenas": 298, "cortes": 16,
                     "cadenas": ["A", "P"]},
            disulfuros_rotos=["A:18–A:45"], disulfuros_totales=4,
            altlocs=[("A:481 CYS", "A 0.50/B 0.50 → A", 3.43)])
        auditoria = _auditar(_caso(), contexto)
        recorte = _requisito(auditoria, "receptor.recorte")
        assert recorte["estado"] == "REVISAR" and "176 de 298 residuos" in recorte["valor"]
        assert "16 corte(s)" in recorte["valor"]
        disulfuros = _requisito(auditoria, "receptor.disulfuros")
        assert disulfuros["valor"] == "1 de 4 puente(s) disulfuro quedan como tiol libre en el receptor: A:18–A:45"
        altlocs = _requisito(auditoria, "receptor.altlocs")
        assert altlocs["estado"] == "REVISAR" and "A:481 CYS A 0.50/B 0.50 → A (3.43 Å)" in altlocs["valor"]
        assert not {"receptor.recorte", "receptor.disulfuros", "receptor.altlocs"} & set(auditoria["bloqueantes"])


class TestPkaCercaDelPh:
    def test_el_imidazol_tiene_las_dos_formas_pobladas(self):
        ph, grupos = _pka_cerca_del_ph({"smiles_entrada": "NCCc1c[nH]cn1", "protonacion": {"ph": 7.4}})
        assert ph == 7.4 and grupos == ["imidazol (pKa ≈ 7; 28 % en la otra forma)"]

    @pytest.mark.parametrize("smiles", ["CC(=O)Oc1ccccc1C(=O)O", "Cc1ccc(S(=O)(=O)NC(=O)NCCCC)cc1"])
    def test_lejos_del_ph_no_se_marca(self, smiles):
        assert _pka_cerca_del_ph({"smiles_entrada": smiles, "protonacion": {"ph": 7.4}}) is None

    def test_la_especie_registrada_pasa_a_revision(self):
        caso = _caso(smiles_entrada="NCCc1c[nH]cn1", protonacion={
            "aplicada": True, "ph": 7.4, "alternativas": 2,
            "seleccion": {"criterio": "cargas_esperadas_ph_7.4", "quimica_resuelta": True}})
        especie = _requisito(_auditar(caso, _contexto()), "ligando.especie")
        assert especie["estado"] == "REVISAR"
        assert especie["razon"].startswith("Grupos con pKa a 1.5 unidades o menos del pH 7.4: imidazol")


@pytest.mark.parametrize("contexto", [
    _contexto(metal=2.3, agua=3.1, hueco=3.65, truncada=5.6, excluidas={"B": 6},
              recorte={"radio_A": 26.0, "residuos_receptor": 176, "residuos_cadenas": 298, "cortes": 16,
                       "cadenas": ["A", "P"]},
              disulfuros_rotos=["A:18–A:45"], disulfuros_totales=4,
              altlocs=[("A:481 CYS", "A 0.50/B 0.50 → A", 3.43)]),
    _contexto(),
    no_medido("La corrida no conserva la pose principal: las distancias se miden desde la caja."),
])
def test_sale_en_ingles(contexto):
    caso = _caso(smiles_entrada="NCCc1c[nH]cn1", protonacion={
        "aplicada": True, "ph": 7.4, "alternativas": 2,
        "seleccion": {"criterio": "cargas_esperadas_ph_7.4", "quimica_resuelta": True}})
    ingles = traducir_dossier(_auditar(caso, contexto), "en")
    claves = ("entorno.metales_cofactores", "entorno.aguas", "entorno.referencia", "receptor.huecos",
              "receptor.cadenas_truncadas", "receptor.cadenas_excluidas", "receptor.protonacion",
              "receptor.recorte", "receptor.disulfuros", "receptor.altlocs", "ligando.especie")
    for bloque in ingles["bloques"]:
        for requisito in bloque["requisitos"]:
            if requisito["clave"] not in claves:
                continue
            for campo in ("valor", "razon", "accion_recomendada"):
                texto = requisito.get(campo)
                if isinstance(texto, str):
                    assert not _PARECE_CASTELLANO.search(texto), (requisito["clave"], campo, texto)


def test_los_puentes_que_no_quedan_como_tiol_libre_no_se_dan_por_conservados():
    """3F75: parte de los puentes queda fuera del recorte; no son «conservados como CYX»."""
    disulfuros = _requisito(_auditar(_caso(), _contexto(disulfuros_totales=4)), "receptor.disulfuros")
    assert disulfuros["estado"] == "REGISTRADO"
    assert disulfuros["valor"] == ("4 puente(s) disulfuro en la estructura; ninguno queda como tiol libre "
                                   "en el receptor")
    ingles = traducir_dossier(_auditar(_caso(), _contexto(disulfuros_totales=4)), "en")
    assert _requisito(ingles, "receptor.disulfuros")["valor"].startswith("4 disulfide bridge(s) in the structure")


# ── SCI-C-001: sin plantilla no hay estado químico del puente ──────────────

def test_un_puente_sin_plantilla_queda_no_evaluado_y_no_se_da_por_conservado():
    auditoria = _auditar(_caso(), _contexto(disulfuros_totales=2, disulfuros_sin_evaluar=["A:18–A:45"]))
    disulfuros = _requisito(auditoria, "receptor.disulfuros")
    assert disulfuros["estado"] == "NO_EVALUADO"
    assert "ninguno queda como tiol libre" not in disulfuros["valor"]
    assert "A:18–A:45" in disulfuros["valor"]
    ingles = _requisito(traducir_dossier(auditoria, "en"), "receptor.disulfuros")
    assert ingles["valor"].startswith("1 of 2 disulfide bridge(s) in the structure without a recorded")
    assert not _PARECE_CASTELLANO.search(ingles["razon"])


def test_un_puente_roto_sigue_mandando_aunque_otro_no_se_evaluara():
    auditoria = _auditar(_caso(), _contexto(disulfuros_totales=2, disulfuros_rotos=["A:3–A:9"],
                                            disulfuros_sin_evaluar=["A:18–A:45"]))
    assert _requisito(auditoria, "receptor.disulfuros")["estado"] == "REVISAR"
