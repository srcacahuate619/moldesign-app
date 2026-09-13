"""SC-9 — la advertencia tiene que sobrevivir a todas las superficies.

El nivel de calibración se calcula en un solo sitio
(`services/targets/calibracion.py`). Eso resuelve la mitad del problema: que no
haya cuatro definiciones distintas. La otra mitad es que el dato **llegue**, y
esa se pierde de una forma muy concreta: alguien añade un campo al contrato, se
propaga a tres pantallas y se olvida de la cuarta, y esa cuarta presenta un
score sin decir que el receptor no está calibrado.

Estas pruebas recorren las superficies una a una: preflight (antes de ejecutar),
resultado (junto al número), catálogo (al elegir receptor), dossier (el
documento que lee un revisor) y MolChat (donde el chat lanza corridas). Si
alguien retira el campo de cualquiera de ellas, esto falla.

También vigila la palabra: **«validado» no puede usarse como sinónimo de «está
en el catálogo»**. Es el punto exacto que un revisor impugnaría.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from services.targets.calibracion import NivelDeCalibracion, estado_de_calibracion

SIN_CALIBRAR = SimpleNamespace(
    pdb_id="7E2Y",
    name="5-HT1A",
    chain="R",
    structural_family="gpcr",
    spearman_rho=None,
    is_prepared=True,
    hotspots=[{"name": "ASP116", "importance": 1.0}],
    id="target-1",
    is_private=False,
    is_community=False,
    grid_center_x=None,
    grid_center_y=None,
    grid_center_z=None,
    grid_size_x=None,
    grid_size_y=None,
    grid_size_z=None,
    cofactors_whitelist=[],
)


class TestAntesDeEjecutar:
    def test_el_preflight_trae_el_control_de_calibracion(self):
        from services.docking.preflight import build_preflight

        informe = build_preflight(
            smiles="CC(=O)Oc1ccccc1C(=O)O",
            target_pdb_id="7E2Y",
            chain="R",
            target_origin="catalogo",
            target_reference="target-1",
            grid_center=None,
            grid_size=None,
            custom_hotspots=None,
            catalog_grid_center=None,
            catalog_grid_size=None,
            catalog_hotspots=[],
            cofactors_whitelist=[],
            calibracion=estado_de_calibracion(SIN_CALIBRAR).to_dict(),
        )

        codigos = {c["code"] for c in informe["controls"]}
        assert "CALIBRACION_RECEPTOR" in codigos
        assert "CALIBRACION_RECEPTOR" in informe["warnings"]
        assert informe["receptor"]["calibracion"]["nivel"] == "curado_estructural"

    def test_no_calibrado_advierte_pero_no_bloquea(self):
        """Explorar un receptor sin ρ es legítimo; creerse el número, no."""
        from services.docking.preflight import build_preflight

        informe = build_preflight(
            smiles="CC(=O)Oc1ccccc1C(=O)O",
            target_pdb_id="7E2Y",
            chain="R",
            target_origin="catalogo",
            target_reference="target-1",
            grid_center=None,
            grid_size=None,
            custom_hotspots=None,
            catalog_grid_center=None,
            catalog_grid_size=None,
            catalog_hotspots=[],
            cofactors_whitelist=[],
            calibracion=estado_de_calibracion(SIN_CALIBRAR).to_dict(),
        )

        assert "CALIBRACION_RECEPTOR" not in informe["technical_blockers"]

    def test_sin_dato_de_calibracion_se_declara_no_evaluado(self):
        """No saber qué respaldo hay no es lo mismo que saber que lo hay."""
        from services.docking.preflight import build_preflight

        informe = build_preflight(
            smiles="CC(=O)Oc1ccccc1C(=O)O",
            target_pdb_id="ZZZZ",
            chain="A",
            target_origin="desconocido",
            target_reference=None,
            grid_center=None,
            grid_size=None,
            custom_hotspots=None,
            catalog_grid_center=None,
            catalog_grid_size=None,
            catalog_hotspots=[],
            cofactors_whitelist=[],
            calibracion=None,
        )

        control = next(
            c for c in informe["controls"] if c["code"] == "CALIBRACION_RECEPTOR"
        )
        assert control["state"] == "no_evaluado"


class TestJuntoAlResultado:
    def test_el_contrato_del_resultado_transporta_la_calibracion(self):
        from core.models import EvaluationResultRead

        assert "target_calibracion" in EvaluationResultRead.model_fields

    def test_el_estado_del_job_congela_la_calibracion_de_la_corrida(self):
        import inspect

        from services.docking import desktop_job_status

        fuente = inspect.getsource(desktop_job_status)
        assert "target_calibracion" in fuente
        assert "estado_de_calibracion" in fuente


class TestEnElCatalogo:
    def test_el_receptor_declara_su_respaldo(self):
        from core.models import Target

        assert "calibracion" in Target.model_fields

    def test_el_listado_lo_calcula_para_cada_receptor(self):
        import inspect

        from api.routers import targets

        fuente = inspect.getsource(targets.list_targets)
        assert "estado_de_calibracion" in fuente


class TestEnElDossier:
    def test_la_portada_declara_el_respaldo_del_receptor(self):
        from services.dossier.model import _respaldo_del_receptor

        texto = _respaldo_del_receptor(SIN_CALIBRAR)

        assert "calibrado" in texto.lower()
        assert "validado" not in texto.lower()

    def test_la_falta_de_calibracion_es_una_incertidumbre_declarada(self):
        import inspect

        from services.dossier import model

        fuente = inspect.getsource(model)
        assert "incertidumbres.insert(0, calibracion.advertencia)" in fuente


class TestEnMolChat:
    def test_la_corrida_lanzada_desde_el_chat_lleva_su_aviso(self):
        from services.evaluation_submission import CorridaRegistrada

        corrida = CorridaRegistrada(
            task_id="t-1",
            target_pdb_id="7E2Y",
            smiles_hash="h",
            canonical_smiles="CCO",
            calibracion=estado_de_calibracion(SIN_CALIBRAR).to_dict(),
        )

        assert corrida.aviso_de_calibracion
        assert "⚠️" in corrida.aviso_de_calibracion

    def test_un_receptor_calibrado_no_ensucia_la_respuesta(self):
        from services.evaluation_submission import CorridaRegistrada

        calibrado = SimpleNamespace(**{**SIN_CALIBRAR.__dict__, "spearman_rho": 0.71})
        corrida = CorridaRegistrada(
            task_id="t-1",
            target_pdb_id="7E2Y",
            smiles_hash="h",
            canonical_smiles="CCO",
            calibracion=estado_de_calibracion(calibrado).to_dict(),
        )

        assert corrida.aviso_de_calibracion == ""

    def test_la_herramienta_antepone_el_aviso_al_lanzar(self):
        import inspect

        from services.ai.tools import docking_tools

        fuente = inspect.getsource(docking_tools.run_docking)
        assert "aviso_de_calibracion" in fuente


class TestLaPalabraValidado:
    @pytest.mark.parametrize(
        "nivel",
        [
            NivelDeCalibracion.PIPELINE_DE_FAMILIA,
            NivelDeCalibracion.CURADO_ESTRUCTURAL,
            NivelDeCalibracion.SIN_CURAR,
        ],
    )
    def test_ningun_texto_de_un_receptor_no_calibrado_dice_validado(self, nivel):
        from services.targets.calibracion import ADVERTENCIA, MOTIVO, RESUMEN

        junto = " ".join((RESUMEN[nivel], ADVERTENCIA[nivel], MOTIVO[nivel])).lower()

        assert "validado" not in junto
        assert "validad" not in junto, "tampoco «validada», «validados»…"
