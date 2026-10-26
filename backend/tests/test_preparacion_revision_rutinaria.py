"""Preparación separa la revisión rutinaria de la revisión del caso (2026-10-11).

Medido en el panel del 2026-10-10 (11 corridas con Vina real por la API): la
protonación por plantilla, la sección Demostración, el commit que el instalador no
declara y las advertencias previas de la ruta pedían revisión en LAS ONCE, y las
aguas junto al ligando también. El veredicto global decía «Revisión» igual para una
aspirina sin nada que decidir que para una warfarina con el tautómero y la
estereoquímica abiertos.

Una revisión es rutinaria si la pide toda corrida de esta ruta con el mismo motivo.
Sigue abierta y cuenta en `en_revision`; se nombra aparte. Lo que la convierte en
revisión del caso es un dato medido: una histidina con un nitrógeno del anillo que
toca al ligando, un agua que lo puentea con la proteína. Sin medida, es del caso.

Incluye la prueba que faltaba de `contexto_estructural.medir` de principio a fin:
`54c5ba44` dejó `_medir` con un nombre sin definir, la ruta capturaba el NameError
y toda auditoría medía desde la caja sin que ninguna prueba lo viera.
"""

from __future__ import annotations

import copy
import json
from dataclasses import replace
from types import SimpleNamespace

import pytest

from core.i18n_plantillas import _PARECE_CASTELLANO, traducir
from services.dossier import preparacion
from services.dossier.contexto_estructural import ContextoEstructural, medir, no_medido
from services.dossier.model import Campo, build_case_dossier
from services.dossier.preparacion import (
    HIS_PLANTILLA_SIN_MIRAR,
    RAZON_SOLO_RUTINARIA,
    RUTINA_COMMIT,
    RUTINA_DEMOSTRACION,
    RUTINA_PREVIAS_ADVERTENCIAS,
    RUTINA_PREVIAS_SIN_EVALUAR,
    RUTINA_PROTONACION_USUARIO,
    RUTINA_RECORTE,
    Requisito,
    build_preparacion,
    estado_global,
)
from services.dossier.taxonomy import Estado
from tests.test_diff_de_especies_de_la_corrida import _diff
from tests.test_preparacion_auditoria import _con_procedencia, _requisito
from tests.test_preparacion_desde_el_ligando import _contexto

RAZON_DEL_CASO = "Hay decisiones científicas abiertas que el cálculo siguiente heredaría."


def _agua() -> tuple[str, str, str, str]:
    fila = next(f for f in _diff()["near_site"]["removed"] if f["category"] == "water")
    return fila["chain"], fila["residue_number"], fila["insertion_code"], fila["name"]


def _caso(**prep) -> dict:
    caso = _con_procedencia(_diff())
    prov = copy.deepcopy(caso["eval_result"].docking_protocol["execution_provenance"])
    prov["receptor_prep"].update(prep)
    caso["eval_result"].docking_protocol = {**caso["eval_result"].docking_protocol, "execution_provenance": prov}
    return caso


def _auditar(caso: dict, contexto: ContextoEstructural | None, dossier=None) -> dict:
    return build_preparacion(dossier or build_case_dossier(**caso), caso["eval_result"], caso["projection"], contexto)


def _con_previa(caso: dict, **cambios) -> dict:
    proyeccion = caso["projection"]
    caso["projection"] = proyeccion.model_copy(update={"preflight": proyeccion.preflight.model_copy(update=cambios)})
    return caso


def _revisar(clave: str, rutinaria: str | None = None) -> Requisito:
    return Requisito(clave, Campo(clave, "dato", Estado.REVISAR, "motivo"), "prueba", False, rutinaria=rutinaria)


def _registrado(clave: str) -> Requisito:
    return Requisito(clave, Campo(clave, "dato", Estado.REGISTRADO), "prueba", True)


# ── Agregación ───────────────────────────────────────────────────────


class TestAgregacion:
    def test_si_solo_queda_lo_rutinario_se_dice(self):
        estado, razon = estado_global([_registrado("a"), _revisar("b", "toda corrida")])
        assert (estado, razon) == ("REVISION", RAZON_SOLO_RUTINARIA)
        # El techo sigue diciéndose: aun resuelta la rutina, FEP-06 no está sellado.
        assert "FEP-06" in razon

    def test_una_revision_del_caso_basta_para_la_razon_del_caso(self):
        estado, razon = estado_global([_revisar("a", "toda corrida"), _revisar("b")])
        assert (estado, razon) == ("REVISION", RAZON_DEL_CASO)

    def test_la_rutinaria_sigue_abierta_y_una_decision_la_resuelve(self):
        rutinaria = _revisar("b", "toda corrida")
        assert rutinaria.pide_revision
        decidida = replace(rutinaria, decision={"justificacion": "Plantilla aceptada", "registrada": None})
        assert decidida.decidido and not decidida.pide_revision
        _, razon = estado_global([_registrado("a"), decidida])
        assert razon.startswith("Todos los requisitos tienen dato registrado o una decisión justificada")

    def test_un_bloqueo_manda_sobre_la_rutina(self):
        bloquea = Requisito("c", Campo("c", None, Estado.ABSTENCION, "x"), "prueba", True)
        assert estado_global([_revisar("b", "toda corrida"), bloquea])[0] == "BLOQUEADO"

    def test_la_salida_nombra_la_rutina_sin_sacarla_de_en_revision(self):
        auditoria = _auditar(_caso(), _contexto(metal=19.2, agua=9.0, plantillas=[]))
        rutinarias = set(auditoria["en_revision_rutinaria"])
        assert rutinarias and rutinarias <= set(auditoria["en_revision"])
        assert {"receptor.protonacion", "receptor.seccion_catalogo"} <= rutinarias
        # El fixture tiene revisiones del caso (selector ≠ top-1) y bloqueos del ligando.
        assert auditoria["solo_rutinaria"] is False
        for bloque in auditoria["bloques"]:
            for r in bloque["requisitos"]:
                assert ("rutinaria" in r) == (r["clave"] in rutinarias or (
                    "rutinaria" in r and r["clave"] not in auditoria["en_revision"])), r["clave"]
                if "rutinaria" in r:
                    assert isinstance(r["rutinaria"]["motivo"], str) and r["rutinaria"]["motivo"]

    def test_con_solo_la_rutina_el_veredicto_lo_dice(self, monkeypatch):
        """Ligando y pose sin nada que decidir: queda lo que pide toda corrida de la ruta."""
        monkeypatch.setattr(preparacion, "_bloque_ligando", lambda *a, **k: [_registrado("ligando.identidad")])
        monkeypatch.setattr(preparacion, "_bloque_pose", lambda *a, **k: [_registrado("pose.origen")])
        caso = _caso(backbone_gaps=[], truncated_sidechains=[])
        contexto = _contexto(metal=19.2, agua=9.0, plantillas=[])
        contexto.no_estandar, contexto.segmentos_tm = {}, {"A": 0}
        auditoria = _auditar(caso, contexto)

        assert auditoria["estado"] == "REVISION"
        assert auditoria["bloqueantes"] == []
        assert auditoria["solo_rutinaria"] is True
        assert auditoria["razon"] == RAZON_SOLO_RUTINARIA
        assert auditoria["en_revision"] == auditoria["en_revision_rutinaria"]
        receptor = next(b for b in auditoria["bloques"] if b["id"] == "receptor")
        assert receptor["estado"] == "REVISION" and receptor["solo_rutinaria"] is True


# ── Protonación del receptor ─────────────────────────────────────────


class TestProtonacion:
    def test_una_his_que_toca_al_ligando_es_del_caso(self):
        contexto = _contexto(plantillas=[("A:131", "HIS", "HIE", 2.8)])
        contexto.anillos_his = {"A:131": 2.9}
        protonacion = _requisito(_auditar(_caso(), contexto), "receptor.protonacion")
        assert "rutinaria" not in protonacion
        assert ("Histidina(s) con un nitrógeno del anillo a 3.5 Å o menos del ligando: A:131 HIE (2.9 Å). "
                + HIS_PLANTILLA_SIN_MIRAR) in protonacion["razon"]

    def test_una_his_que_toca_sólo_con_el_esqueleto_no_cuenta(self):
        """Lo que la plantilla decide es dónde va el hidrógeno del anillo, no el esqueleto."""
        contexto = _contexto(plantillas=[("A:131", "HIS", "HIE", 2.8)])
        contexto.anillos_his = {"A:131": 5.1}
        protonacion = _requisito(_auditar(_caso(), contexto), "receptor.protonacion")
        assert protonacion["rutinaria"]["motivo"] == (
            "La pide toda corrida protonada por plantilla, y ninguna histidina tiene un nitrógeno del anillo "
            "a 3.5 Å o menos del ligando.")
        assert "Histidina(s)" not in protonacion["razon"]

    @pytest.mark.parametrize("contexto", [None, no_medido("sin crudo")], ids=["sin_contexto", "sin_medir"])
    def test_sin_medida_es_del_caso(self, contexto):
        assert "rutinaria" not in _requisito(_auditar(_caso(), contexto), "receptor.protonacion")

    def test_sin_informe_de_plantillas_es_del_caso(self):
        assert "rutinaria" not in _requisito(_auditar(_caso(), _contexto(plantillas=None)), "receptor.protonacion")

    def test_la_protonacion_declarada_por_quien_preparo_el_receptor_es_rutinaria(self):
        caso = _caso(protonacion_declarada={"plantillas_coinciden": True})
        protonacion = _requisito(_auditar(caso, None), "receptor.protonacion")
        assert protonacion["rutinaria"]["motivo"] == RUTINA_PROTONACION_USUARIO


# ── Aguas ────────────────────────────────────────────────────────────


class TestAguas:
    @staticmethod
    def _contexto(al_ligando: float, a_un_polar: float, a_la_proteina: float) -> ContextoEstructural:
        contexto = _contexto(agua=al_ligando)
        contexto.aguas_al_ligando_polar = {_agua(): a_un_polar}
        contexto.aguas_a_la_proteina = {_agua(): a_la_proteina}
        return contexto

    def test_un_agua_que_puentea_el_ligando_con_la_proteina_es_del_caso(self):
        aguas = _requisito(_auditar(_caso(), self._contexto(3.1, 3.1, 2.8)), "entorno.aguas")
        assert aguas["estado"] == "REVISAR" and "rutinaria" not in aguas
        assert aguas["razon"].endswith(
            "Aguas que pueden puentear el ligando con la proteína (a 3.5 Å o menos de un N u O de cada uno): "
            "HOH A:401 (3.1 Å).")

    @pytest.mark.parametrize("al_ligando,a_un_polar,a_la_proteina", [
        (3.1, 3.1, 3.9), (1.2, 1.2, 2.7), (3.8, 3.8, 2.7), (3.1, 3.9, 2.8)],
        ids=["lejos_de_la_proteina", "la_pose_la_desplaza", "lejos_del_ligando", "junto_a_un_carbono"])
    def test_un_agua_que_no_puentea_es_rutinaria(self, al_ligando, a_un_polar, a_la_proteina):
        aguas = _requisito(_auditar(_caso(), self._contexto(al_ligando, a_un_polar, a_la_proteina)), "entorno.aguas")
        assert aguas["estado"] == "REVISAR"
        assert aguas["rutinaria"]["motivo"].startswith(
            "Ninguna de las aguas retiradas puentea el ligando con la proteína (a 3.5 Å o menos de un N u O de "
            "cada uno)")

    def test_sin_aguas_junto_al_ligando_no_hay_nada_que_revisar(self):
        aguas = _requisito(_auditar(_caso(), _contexto(agua=9.0)), "entorno.aguas")
        assert aguas["estado"] == "REGISTRADO" and "rutinaria" not in aguas

    def test_sin_medida_las_aguas_son_del_caso(self):
        aguas = _requisito(_auditar(_caso(), None), "entorno.aguas")
        assert aguas["estado"] == "REVISAR" and "rutinaria" not in aguas


# ── Lo que pide la ruta ──────────────────────────────────────────────


class TestRuta:
    def test_el_recorte_multicadena_es_rutinario(self):
        contexto = _contexto(recorte={"radio_A": 26.0, "residuos_receptor": 176, "residuos_cadenas": 298,
                                      "cortes": 16, "cadenas": ["A", "P"]})
        assert _requisito(_auditar(_caso(), contexto), "receptor.recorte")["rutinaria"]["motivo"] == RUTINA_RECORTE

    def test_demostracion_es_rutinaria_y_un_sello_que_no_describe_la_corrida_no(self):
        caso = _caso()
        dossier = build_case_dossier(**caso)
        assert dossier.catalogo["seccion"] == "demostracion"
        seccion = _requisito(_auditar(caso, None, dossier), "receptor.seccion_catalogo")
        assert seccion["rutinaria"]["motivo"] == RUTINA_DEMOSTRACION

        verificado = replace(dossier, catalogo={
            **dossier.catalogo, "seccion": "verificados", "aplica_a_esta_corrida": False,
            "difiere_en": ["exhaustiveness"], "verificacion": {
                "calibracion": {}, "pose": {}, "receptor_sha256": "ab" * 32,
                "protocolo": {"exhaustiveness": 32, "num_poses": 9, "semilla": 42}}})
        sello = _requisito(_auditar(caso, None, verificado), "receptor.seccion_catalogo")
        assert sello["estado"] == "REVISAR" and "rutinaria" not in sello

    def test_sin_commit_es_rutinario_y_con_commit_no_pide_nada(self):
        caso = _caso()
        con_commit = _requisito(_auditar(caso, None), "procedencia.commit")
        assert con_commit["estado"] == "REGISTRADO" and "rutinaria" not in con_commit
        prov = caso["eval_result"].docking_protocol["execution_provenance"]
        prov.pop("git_commit")
        sin_commit = _requisito(_auditar(caso, None), "procedencia.commit")
        assert sin_commit["rutinaria"]["motivo"] == RUTINA_COMMIT

    def test_las_advertencias_previas_de_la_ruta_son_rutinarias(self):
        caso = _con_previa(_caso(), warnings=["CALIBRACION_RECEPTOR", "ESPECIES_DEL_SITIO_RETIRADAS",
                                              "RECEPTOR_PROTONACION_DECLARADA"])
        previa = _requisito(_auditar(caso, None), "procedencia.previa_advertencias")
        assert previa["rutinaria"]["motivo"] == RUTINA_PREVIAS_ADVERTENCIAS

    @pytest.mark.parametrize("codigo", ["METALES_ELIMINADOS", "GRID_VOLUMEN_AMPLIO", "LIGANDO_REVISION_QUIMICA"])
    def test_una_advertencia_previa_del_caso_no_lo_es(self, codigo):
        caso = _con_previa(_caso(), warnings=["CALIBRACION_RECEPTOR", codigo])
        assert "rutinaria" not in _requisito(_auditar(caso, None), "procedencia.previa_advertencias")

    def test_los_controles_previos_sin_evaluar_de_la_ruta_son_rutinarios(self):
        caso = _con_previa(_caso(), not_evaluated=[
            "RECEPTOR_PREPARADO_DISPONIBLE", "RECEPTOR_PROTONACION_DECLARADA", "LIGANDO_PROTONACION_TAUTOMERO",
            "ASSEMBLY_BIOLOGICA", "HUECOS_CERCA_DEL_SITIO"])
        previa = _requisito(_auditar(caso, None), "procedencia.previa_sin_evaluar")
        assert previa["rutinaria"]["motivo"] == RUTINA_PREVIAS_SIN_EVALUAR
        otro = _con_previa(_caso(), not_evaluated=["ASSEMBLY_BIOLOGICA", "CALIBRACION_RECEPTOR"])
        assert "rutinaria" not in _requisito(_auditar(otro, None), "procedencia.previa_sin_evaluar")

    def test_las_deudas_declaradas_de_la_comprobacion_previa_estan_en_la_lista(self):
        """Si la comprobación previa declara una deuda nueva, alguien tiene que decidir si es de la ruta."""
        from services.docking.preflight import _declared_debts

        assert {c.code for c in _declared_debts()} <= preparacion._SIN_EVALUAR_PREVIOS_DE_LA_RUTA


# ── Traducción ───────────────────────────────────────────────────────


def test_los_motivos_y_las_frases_nuevas_salen_en_ingles():
    frases = [
        RUTINA_PROTONACION_USUARIO, RUTINA_RECORTE, RUTINA_DEMOSTRACION, RUTINA_COMMIT,
        RUTINA_PREVIAS_ADVERTENCIAS, RUTINA_PREVIAS_SIN_EVALUAR, HIS_PLANTILLA_SIN_MIRAR, RAZON_SOLO_RUTINARIA,
        "La pide toda corrida protonada por plantilla, y ninguna histidina tiene un nitrógeno del anillo a "
        "3.5 Å o menos del ligando.",
        "Histidina(s) con un nitrógeno del anillo a 3.5 Å o menos del ligando: A:131 HIE (2.9 Å), A:94 HID (3.1 Å).",
        "Aguas que pueden puentear el ligando con la proteína (a 3.5 Å o menos de un N u O de cada uno): "
        "HOH A:401 (3.1 Å).",
        "Ninguna de las aguas retiradas puentea el ligando con la proteína (a 3.5 Å o menos de un N u O de cada "
        "uno): decidir "
        "cuáles conservar es la misma decisión en toda corrida contra un cristal.",
    ]
    for frase in frases:
        en = traducir(frase, "en")
        assert en != frase and not _PARECE_CASTELLANO.search(en), frase


def test_la_razon_compuesta_de_la_protonacion_sale_entera_en_ingles():
    contexto = _contexto(plantillas=[("A:131", "HIS", "HIE", 2.8)])
    contexto.anillos_his = {"A:131": 2.9}
    razon = _requisito(_auditar(_caso(), contexto), "receptor.protonacion")["razon"]
    en = traducir(razon, "en")
    assert en != razon and not _PARECE_CASTELLANO.search(en)
    assert "Histidine(s) with a ring nitrogen within 3.5 Å of the ligand: A:131 HIE (2.9 Å)." in en


# ── La medida, de principio a fin ────────────────────────────────────


def _pdb(registro: str, serie: int, nombre: str, residuo: str, numero: int, xyz, elemento: str) -> str:
    x, y, z = xyz
    return (f"{registro:<6}{serie:>5} {nombre:<4} {residuo:>3} A{numero:>4}    "
            f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00          {elemento:>2}")


@pytest.fixture
def corrida_medible(tmp_path, monkeypatch):
    """Un depósito mínimo con su receta, la pose, el informe de Meeko y un agua que puentea.

    His A:2 tiene NE2 a 2.9 Å del O del ligando; el agua A:401 está a 3.0 Å del ligando y a
    2.8 Å del OG de la Ser A:3.
    """
    from services.docking import preparer
    from utils import local_storage
    from utils.file_handlers import StoragePath

    monkeypatch.setattr(local_storage, "data_dir", lambda: tmp_path)
    lineas = [
        "HEADER    HYDROLASE",
        _pdb("ATOM", 1, "N", "HIS", 2, (0.0, 9.0, 0.0), "N"),
        _pdb("ATOM", 2, "CA", "HIS", 2, (0.0, 8.0, 0.0), "C"),
        _pdb("ATOM", 3, "ND1", "HIS", 2, (0.0, 5.0, 0.0), "N"),
        _pdb("ATOM", 4, "NE2", "HIS", 2, (0.0, 2.9, 0.0), "N"),
        _pdb("ATOM", 5, "CA", "SER", 3, (0.0, 0.0, 7.0), "C"),
        _pdb("ATOM", 6, "OG", "SER", 3, (0.0, 0.0, 5.8), "O"),
        _pdb("HETATM", 7, "O1", "LIG", 601, (0.0, 0.0, 0.0), "O"),
        _pdb("HETATM", 8, "C1", "LIG", 601, (1.4, 0.0, 0.0), "C"),
        _pdb("HETATM", 9, "O", "HOH", 401, (0.0, 0.0, 3.0), "O"),
        "END",
    ]
    archivo = tmp_path / "9ZZZ.pdb"
    archivo.write_bytes(("\n".join(lineas) + "\n").encode("utf-8"))
    monkeypatch.setattr(preparer, "receptor_source_path_no_network", lambda pdb_id: archivo)
    receta = preparer.receptor_recipe_hash(
        archivo.read_bytes().decode("utf-8"), chains={"A"}, cofactors_whitelist=None,
        center=(0.0, 0.0, 0.0), size=(20.0, 20.0, 20.0), site_ligand="LIG",
    )
    informe = local_storage.path_for(preparer._meeko_report_path(StoragePath.target_prepared("9ZZZ", receta)))
    informe.parent.mkdir(parents=True, exist_ok=True)
    # Como el informe real: sólo residuos titulables (medido en 1BN1: LYS, ASP, GLU, HIS, TYR, ARG, CYS).
    informe.write_text(json.dumps({"receptor_sha256": "c" * 64, "protonation_templates": {
        "A:2": {"template": "HIE", "input_resname": "HIS"}}}), encoding="utf-8")
    pose = "\n".join([
        "ATOM      1  O1  UNL     1       0.000   0.000   0.000  0.00  0.00    -0.300 OA",
        "ATOM      2  C1  UNL     1       1.400   0.000   0.000  0.00  0.00     0.100 C ",
    ])
    agua = {"chain": "A", "residue_number": "401", "insertion_code": "", "name": "HOH",
            "category": "water", "distance_to_box_A": 0.0}
    return SimpleNamespace(
        receptor_path=None,
        docking_poses=[{"rank": 1, "pdbqt_block": pose}],
        docking_protocol={"execution_provenance": {
            "box_center": [0.0, 0.0, 0.0], "box_size": [20.0, 20.0, 20.0], "receptor_sha256": "c" * 64,
            "receptor_prep": {"recipe_hash": receta, "chain": "A", "site_chains": ["A"], "species_diff": {
                "state": "evaluado", "site_ligand": "LIG",
                "near_site": {"margin_A": 6.0, "removed": [agua], "preserved": []}}},
        }},
    )


def test_medir_mide_de_verdad(corrida_medible):
    contexto = medir(corrida_medible, "9ZZZ")

    assert contexto.medido, contexto.razon
    assert contexto.referencia == "Pose top-1 y ligando del cristal LIG A:601"
    assert contexto.especies[("A", "401", "", "HOH")] == 3.0
    assert contexto.aguas_a_la_proteina[("A", "401", "", "HOH")] == 2.8
    assert contexto.aguas_al_ligando_polar[("A", "401", "", "HOH")] == 3.0
    assert contexto.anillos_his == {"A:2": 2.9}
    assert [fila[0] for fila in contexto.plantillas] == ["A:2"]
