"""La auditoría de preparación de una corrida: bloques, estados y agregación.

Lo que fijan estas pruebas, además del techo que vigila FEP-GUARD:

1. Los cinco bloques y sus claves son estables: la interfaz los pinta por
   clave, no por etiqueta.
2. Un imprescindible sin dato o en abstención BLOQUEA; un imprescindible en
   REVISAR pide revisión. Son la «evidencia que falta» y la «decisión abierta»
   de la leyenda de la interfaz.
3. NO_APLICA no cuenta: la correspondencia de la serie no puede bloquear una
   auditoría de una corrida.
4. Los códigos de la comprobación previa sólo cuentan si la corrida
   corresponde a esos inputs.
5. La ruta devuelve lo mismo con el 404/403/409 del dossier.
"""

from __future__ import annotations

import copy

import pytest

from services.dossier.model import build_case_dossier
from services.dossier.preparacion import BLOQUES, build_preparacion
from tests.fixtures_dossier import caso_completo, caso_parcial
from tests.test_diff_de_especies_de_la_corrida import _diff


def _auditar(caso: dict) -> dict:
    return build_preparacion(build_case_dossier(**caso), caso["eval_result"], caso["projection"])


def _requisito(auditoria: dict, clave: str) -> dict:
    for bloque in auditoria["bloques"]:
        for requisito in bloque["requisitos"]:
            if requisito["clave"] == clave:
                return requisito
    raise AssertionError(f"Falta el requisito {clave}")


def _bloque(auditoria: dict, nombre: str) -> dict:
    return next(b for b in auditoria["bloques"] if b["id"] == nombre)


_PROCEDENCIA = {
    "box_center": [1.0, 2.0, 3.0], "box_size": [20.0, 20.0, 20.0],
    "receptor_sha256": "e" * 64, "ligand_input_sha256": "1" * 64,
    "ligand_pdbqt_sha256": "2" * 64, "poses_sha256": "3" * 64, "log_sha256": "4" * 64,
    "app_version": "1.0.2", "git_commit": "c711bd2",
    "toolchain": {"vina": "1.2.7", "meeko": "0.7.1", "rdkit": "2025.9.6"},
    "receptor_prep": {
        "source": "meeko_report", "recipe_hash": "5" * 64, "chain": "R", "site_chains": ["R"],
        "removed_residues": [], "cofactors_outside_site": [],
        "protonation_method": "Meeko 0.7.1; asignación por plantilla, sin pH experimental declarado",
    },
}


def _con_procedencia(species_diff: dict | None = None, **ligand_state) -> dict:
    caso = caso_completo()
    resultado = caso["eval_result"]
    procedencia = copy.deepcopy(_PROCEDENCIA)
    if species_diff is not None:
        procedencia["receptor_prep"]["species_diff"] = species_diff
    resultado.docking_protocol = {**resultado.docking_protocol, "execution_provenance": procedencia}
    resultado.ligand_state = {**resultado.ligand_state, **ligand_state}
    return caso


class TestForma:
    def test_huellas_distintas_no_prueban_que_hayan_cambiado_los_inputs(self):
        requisito = _requisito(_auditar(caso_parcial()), "procedencia.relacion")
        assert requisito["estado"] == "REVISAR"
        assert "no se puede confirmar" in requisito["razon"].lower()
        assert "cambiaron después" not in requisito["razon"].lower()

    def test_cinco_bloques_en_el_orden_de_la_interfaz(self):
        auditoria = _auditar(caso_completo())
        assert [b["id"] for b in auditoria["bloques"]] == list(BLOQUES)
        assert auditoria["schema"] == "preparacion/v1"

    def test_el_valor_solo_se_ve_si_es_afirmativo_o_la_clasificacion(self):
        for bloque in _auditar(caso_parcial())["bloques"]:
            for r in bloque["requisitos"]:
                if r["valor"] is not None:
                    assert r["estado"] in ("REGISTRADO", "PASA") or r["valor_es_clasificacion"], r


class TestAgregacion:
    def test_sin_diff_de_heteroatomos_el_entorno_bloquea(self):
        """Sin saber si se retiró un metal del sitio, no se puede entregar el sistema."""
        auditoria = _auditar(_con_procedencia())
        assert _requisito(auditoria, "entorno.metales_cofactores")["estado"] == "NO_EVALUADO"
        assert "entorno.metales_cofactores" in auditoria["bloqueantes"]
        assert auditoria["estado"] == "BLOQUEADO"

    def test_un_zinc_retirado_del_sitio_es_abstencion(self):
        auditoria = _auditar(_con_procedencia(_diff()))
        metales = _requisito(auditoria, "entorno.metales_cofactores")
        assert metales["estado"] == "ABSTENCION"
        assert "ZN A:301" in metales["valor"]
        assert _bloque(auditoria, "entorno")["estado"] == "BLOQUEADO"

    def test_sin_metales_retirados_el_entorno_no_bloquea(self):
        diff = _diff()
        diff["near_site"]["removed"] = [
            f for f in diff["near_site"]["removed"] if f["category"] in ("water", "site_ligand")
        ]
        auditoria = _auditar(_con_procedencia(diff))
        assert _requisito(auditoria, "entorno.metales_cofactores")["estado"] == "REGISTRADO"
        # Las aguas retiradas son una decisión abierta, no evidencia que falte.
        assert _requisito(auditoria, "entorno.aguas")["estado"] == "REVISAR"
        assert "entorno.metales_cofactores" not in auditoria["bloqueantes"]

    def test_la_correspondencia_de_la_serie_no_aplica_y_no_cuenta(self):
        auditoria = _auditar(_con_procedencia(_diff()))
        serie = _requisito(auditoria, "pose.correspondencia_serie")
        assert serie["estado"] == "NO_APLICA"
        assert "requiere una serie" in serie["razon"].lower()
        assert "pose.correspondencia_serie" not in auditoria["bloqueantes"] + auditoria["en_revision"]

    def test_tautomero_multiestado_pide_revision_y_no_bloquea(self):
        caso = _con_procedencia(tautomeria={"declaracion": {
            "estado": "MULTIESTADO_REQUERIDO", "n_candidatos": 3,
        }})
        auditoria = _auditar(caso)
        assert _requisito(auditoria, "ligando.tautomero")["estado"] == "REVISAR"
        assert "ligando.tautomero" in auditoria["en_revision"]
        assert "ligando.tautomero" not in auditoria["bloqueantes"]

    def test_una_corrida_sin_declaracion_de_tautomero_bloquea(self):
        auditoria = _auditar(_con_procedencia())
        assert _requisito(auditoria, "ligando.tautomero")["estado"] == "NO_EVALUADO"
        assert "ligando.tautomero" in auditoria["bloqueantes"]

    def test_una_cadena_excluida_que_toca_la_caja_pide_revision(self):
        auditoria = _auditar(_con_procedencia(_diff()))
        vecinas = _requisito(auditoria, "receptor.cadenas_excluidas")
        assert vecinas["estado"] == "REVISAR"
        assert "cadena B, 2 residuo(s)" in vecinas["valor"]

    def test_la_protonacion_por_plantilla_pide_revision(self):
        auditoria = _auditar(_con_procedencia())
        protonacion = _requisito(auditoria, "receptor.protonacion")
        assert protonacion["estado"] == "REVISAR"
        assert "sin pH experimental" in protonacion["valor"]

    def test_el_selector_discrepante_pide_revision(self):
        """En el fixture el selector sugiere la #2 y la top-1 de Vina es la #1."""
        regla = _requisito(_auditar(_con_procedencia()), "pose.regla_de_seleccion")
        assert regla["estado"] == "REVISAR"
        assert "#2" in regla["valor"]


class TestComprobacionPrevia:
    def test_sus_codigos_cuentan_si_la_corrida_corresponde(self):
        auditoria = _auditar(_con_procedencia())
        advertencias = _requisito(auditoria, "procedencia.previa_advertencias")
        assert advertencias["estado"] == "REVISAR"
        assert "ESPECIES_DEL_SITIO_RETIRADAS" in advertencias["valor"]
        bloqueantes = _requisito(auditoria, "procedencia.previa_bloqueantes")
        # Sin bloqueantes no es PASA: el caso no guarda los controles que pasan.
        assert bloqueantes["estado"] == "REGISTRADO"

    def test_de_otra_hipotesis_no_cuentan(self):
        """El caso parcial trae un bloqueante, pero la corrida es de otros inputs."""
        auditoria = _auditar(caso_parcial())
        bloqueantes = _requisito(auditoria, "procedencia.previa_bloqueantes")
        assert bloqueantes["estado"] == "NO_EVALUADO"
        assert bloqueantes["imprescindible"] is False
        assert _requisito(auditoria, "procedencia.relacion")["estado"] == "REVISAR"


class TestRuta:
    @pytest.fixture
    def proyeccion(self) -> dict:
        from tests.fixtures_dossier import proyeccion_completa
        return proyeccion_completa().model_dump(mode="json")

    def test_devuelve_la_auditoria(self, proyeccion):
        from tests.fixtures_dossier import molecula, resultado_completo
        from tests.test_dossier_api import MOLECULE_ID, _app

        respuesta = _app(molecula(), resultado_completo(), localization_middleware=True).post(
            f"/evaluation/dossier/{MOLECULE_ID}/preparacion", json=proyeccion,
            headers={"Accept-Language": "en"},
        )
        assert respuesta.status_code == 200
        cuerpo = respuesta.json()
        assert cuerpo["schema"] == "preparacion/v1"
        assert cuerpo["estado"] in ("BLOQUEADO", "REVISION")
        assert cuerpo["alcance"] == "FEP readiness auditor in development"
        assert cuerpo["bloques"][0]["requisitos"][0]["etiqueta"] == "Prepared receptor"

    def test_mismos_errores_que_el_dossier(self, proyeccion):
        from tests.fixtures_dossier import molecula, resultado_completo
        from tests.test_dossier_api import MOLECULE_ID, _app

        ruta = f"/evaluation/dossier/{MOLECULE_ID}/preparacion"
        assert _app(molecula(), resultado_completo(), autorizado=False).post(
            ruta, json=proyeccion).status_code == 403
        assert _app(None, None).post(ruta, json=proyeccion).status_code == 404
        otra = resultado_completo()
        otra.task_id = "task-de-otra-corrida"
        assert _app(molecula(), otra).post(ruta, json=proyeccion).status_code == 409
