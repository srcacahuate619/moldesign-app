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
    def test_con_rho_medido_es_calibrado(self):
        estado = estado_de_calibracion(_receptor(spearman_rho=0.62))

        assert estado.nivel is NivelDeCalibracion.CALIBRADO
        assert estado.spearman_rho == 0.62

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

    def test_un_receptor_calibrado_no_advierte(self):
        estado = estado_de_calibracion(_receptor(spearman_rho=0.62))

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
