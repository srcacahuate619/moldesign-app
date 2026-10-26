"""SC-9 — «curado» no es «calibrado», y el catálogo no puede decir que sí.

El catálogo tiene 387 receptores curados **estructuralmente**: los 387 tienen
familia, caja y preparación, y 384 tienen hotspots minados. Eso está bien hecho
y no es lo que un revisor va a impugnar.

Lo impugnable es el salto de ahí a «validado». `spearman_rho` —la medida de que
el ranking del motor correlaciona con afinidad real **para ese receptor**— sólo
existe en 2 de 387, y los dos valen exactamente `0.0`, que es el valor por
defecto y además significaría ausencia de correlación. Ninguna de las dos
lecturas permite llamarlo calibrado.

Y hay una segunda capa: el contrato M4 alpha no declara hoy ninguna familia con
stacking ML calibrado. Todas usan pesos conservadores comunes y CL-GNN pesa cero
hasta validar externamente el checkpoint exacto.

Esta prueba fija los cuatro niveles y, sobre todo, fija que **el nivel se
calcula en un solo sitio**: si cada superficie lo dedujera por su cuenta, la
advertencia se perdería en la que se olvidara.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from services.targets.calibracion import (
    FAMILIAS_CON_PIPELINE_CALIBRADO,
    NivelDeCalibracion,
    estado_de_calibracion,
    rho_es_utilizable,
)


@pytest.fixture
def verificado(monkeypatch, tmp_path):
    """Una entrada de Verificados que supera el protocolo, para `pdb_id`."""
    import json
    from services.docking.preparer import RECEPTOR_RECIPE_VERSION
    from services.targets import seccion_catalogo as sc

    def poner(pdb_id="7E2Y", rho=0.62):
        entrada = {
            "receta_receptor": RECEPTOR_RECIPE_VERSION,
            "receptor_sha256": "0" * 64,
            "pose": {"semillas": 5, "semillas_rmsd_ok": 4, "posebusters_valida": True},
            "calibracion": {"rho": rho, "ic95": [0.31, 0.80], "n": 48, "endpoint": "Ki",
                            "panel": "CHEMBL0"},
            "protocolo": {"exhaustiveness": 8, "num_poses": 9, "semilla": 42},
            "condiciones": [],
        }
        ruta = tmp_path / "verificados.json"
        ruta.write_text(json.dumps({"verificados": {pdb_id: entrada}}), encoding="utf-8")
        monkeypatch.setattr(sc, "RUTA_VERIFICADOS", ruta)
        sc._leer.cache_clear()
        return entrada

    yield poner
    sc._leer.cache_clear()


def _receptor(**campos):
    base = {
        "pdb_id": "7E2Y",
        "structural_family": "gpcr",
        "spearman_rho": None,
        "is_prepared": True,
        "hotspots": [{"name": "ASP116", "importance": 1.0}],
    }
    base.update(campos)
    return SimpleNamespace(**base)


class TestElValorDeRho:
    def test_cero_no_es_una_calibracion(self):
        """Es el valor por defecto; y si fuera real, diría «no correlaciona»."""
        assert rho_es_utilizable(0.0) is False

    def test_ninguno_no_es_una_calibracion(self):
        assert rho_es_utilizable(None) is False

    def test_un_valor_fuera_de_rango_no_es_una_calibracion(self):
        assert rho_es_utilizable(1.4) is False
        assert rho_es_utilizable(-2.0) is False

    def test_una_correlacion_real_si_lo_es(self):
        assert rho_es_utilizable(0.62) is True
        assert rho_es_utilizable(-0.55) is True, "una anticorrelación también es medida"


class TestLosCuatroNiveles:
    def test_una_rho_suelta_en_la_fila_no_es_calibrado(self):
        """SCI-D-001: sin n, IC ni protocolo, un número no suprime la reserva."""
        estado = estado_de_calibracion(_receptor(spearman_rho=0.62))

        assert estado.nivel is not NivelDeCalibracion.CALIBRADO
        assert estado.requiere_advertencia is True
        assert estado.spearman_rho is None
        assert estado.respaldo is None
        assert estado.rho_registrada_sin_respaldo == 0.62, "se conserva, aparte"

    @pytest.mark.parametrize("rho", [-0.8, 0.9])
    def test_una_rho_suelta_de_cualquier_signo_tampoco(self, rho):
        estado = estado_de_calibracion(_receptor(spearman_rho=rho))
        assert estado.nivel is not NivelDeCalibracion.CALIBRADO

    def test_con_la_medida_de_verificados_es_calibrado(self, verificado):
        verificado()
        estado = estado_de_calibracion(_receptor(spearman_rho=None))

        assert estado.nivel is NivelDeCalibracion.CALIBRADO
        assert estado.spearman_rho == 0.62
        assert estado.respaldo["n"] == 48 and estado.respaldo["ic95"] == [0.31, 0.80]
        assert estado.respaldo["protocolo"]["semilla"] == 42

    def test_la_medida_de_otro_receptor_no_cuenta(self, verificado):
        verificado(pdb_id="8HFI")
        assert estado_de_calibracion(_receptor()).nivel is not NivelDeCalibracion.CALIBRADO

    def test_un_receptor_propio_no_hereda_la_medida_del_catalogo(self, verificado):
        verificado()
        estado = estado_de_calibracion(_receptor(is_private=True))
        assert estado.nivel is not NivelDeCalibracion.CALIBRADO

    def test_sin_rho_en_familia_conocida_sigue_siendo_curado_estructural(self):
        estado = estado_de_calibracion(_receptor(structural_family="kinase"))

        assert estado.nivel is NivelDeCalibracion.CURADO_ESTRUCTURAL
        assert estado.spearman_rho is None

    def test_una_familia_sin_pipeline_se_queda_en_curado_estructural(self):
        estado = estado_de_calibracion(_receptor(structural_family="polymerase"))

        assert estado.nivel is NivelDeCalibracion.CURADO_ESTRUCTURAL

    def test_sin_familia_ni_preparacion_es_sin_curar(self):
        estado = estado_de_calibracion(
            _receptor(structural_family=None, is_prepared=False, hotspots=None)
        )

        assert estado.nivel is NivelDeCalibracion.SIN_CURAR

    def test_los_dos_receptores_reales_del_catalogo_no_son_calibrados(self):
        """3OSK y 2W96 tienen ρ, pero valen 0.0. No cuentan."""
        for pdb, familia in (("3OSK", "protein_interaction"), ("2W96", "kinase")):
            estado = estado_de_calibracion(
                _receptor(pdb_id=pdb, structural_family=familia, spearman_rho=0.0)
            )
            assert estado.nivel is not NivelDeCalibracion.CALIBRADO


class TestLaAdvertencia:
    def test_todo_lo_que_no_esta_calibrado_trae_advertencia(self):
        for familia, esperado in (
            ("kinase", NivelDeCalibracion.CURADO_ESTRUCTURAL),
            ("polymerase", NivelDeCalibracion.CURADO_ESTRUCTURAL),
        ):
            estado = estado_de_calibracion(_receptor(structural_family=familia))
            assert estado.nivel is esperado
            assert estado.advertencia, f"{familia} tiene que advertir"
            assert estado.requiere_advertencia is True

    def test_un_receptor_calibrado_no_advierte(self, verificado):
        verificado()
        estado = estado_de_calibracion(_receptor())

        assert estado.requiere_advertencia is False
        assert estado.advertencia == ""

    def test_la_advertencia_no_llama_validado_a_estar_en_el_catalogo(self):
        estado = estado_de_calibracion(_receptor(structural_family="polymerase"))

        texto = (estado.advertencia + " " + estado.resumen).lower()
        assert "validado" not in texto, (
            "«validado» es justo la palabra que el catálogo no puede usar"
        )
        assert "no está calibrado" in texto or "sin calibrar" in texto

    def test_la_advertencia_dice_que_es_lo_que_falta(self):
        estado = estado_de_calibracion(_receptor(structural_family="polymerase"))

        assert "spearman" in estado.advertencia.lower() or "ρ" in estado.advertencia
        assert estado.motivo


class TestLasFamiliasConPipeline:
    def test_alpha_no_declara_familias_calibradas(self):
        assert FAMILIAS_CON_PIPELINE_CALIBRADO == frozenset()

    def test_coinciden_con_las_del_frontend(self):
        """Dos listas que se desincronizan son una mentira esperando su turno."""
        from pathlib import Path

        definiciones = (
            Path(__file__).resolve().parents[2]
            / "frontend" / "lib" / "pipelineDefinitions.ts"
        ).read_text(encoding="utf-8")

        for familia in FAMILIAS_CON_PIPELINE_CALIBRADO:
            assert f"\n  {familia}: {{" in definiciones, (
                f"el backend declara pipeline calibrado para '{familia}' y el "
                "frontend no lo tiene"
            )


class TestSerializacion:
    def test_el_estado_viaja_como_contrato_y_no_como_texto_suelto(self):
        estado = estado_de_calibracion(_receptor(structural_family="polymerase"))
        payload = estado.to_dict()

        assert payload["nivel"] == "curado_estructural"
        assert payload["requiere_advertencia"] is True
        assert "advertencia" in payload and "resumen" in payload
        assert payload["spearman_rho"] is None

    def test_un_receptor_ausente_no_finge_estar_curado(self):
        estado = estado_de_calibracion(None)

        assert estado.nivel is NivelDeCalibracion.SIN_CURAR
        assert estado.requiere_advertencia is True


class TestElControlDeLaComprobacionPrevia:
    """SCI-D-001: el control sólo pasa con la medida, y la nombra."""

    def _control(self, calibracion):
        from services.docking.preflight import _calibration_controls
        return _calibration_controls(calibracion)[0]

    def test_calibrado_sin_respaldo_no_pasa(self):
        control = self._control({"nivel": "calibrado", "requiere_advertencia": False,
                                 "spearman_rho": 0.62, "resumen": "Calibrado"})
        assert control.state == "advertencia"
        assert "no está respaldado" in control.reason

    def test_calibrado_con_respaldo_pasa_y_dice_n_ic_y_protocolo(self, verificado):
        verificado()
        control = self._control(estado_de_calibracion(_receptor()).to_dict())
        assert control.state == "pasa"
        assert "n = 48" in control.observation and "[0.31; 0.80]" in control.observation
        assert "semilla 42" in control.reason

    def test_las_dos_frases_tienen_ingles(self, verificado):
        from core.i18n_plantillas import traducir
        verificado()
        control = self._control(estado_de_calibracion(_receptor()).to_dict())
        for texto in (control.observation, control.reason):
            assert traducir(texto, "en") != texto
        sin = self._control({"nivel": "calibrado", "requiere_advertencia": False})
        assert traducir(sin.reason, "en") != sin.reason
