"""FEP-GUARD — la pestaña Preparación no puede afirmar una transferencia FEP no demostrada.

`AGENTS.md`: hasta superar `FEP-05` y `FEP-06`, la formulación correcta es
«auditor de readiness para FEP en desarrollo», no «sistema compatible con
FEP+». La auditoría tiene techo en REVISIÓN mientras
`TRANSFERENCIA_FEP_DEMOSTRADA` valga `False`, y esta prueba falla a propósito
si alguien la activa sin el experimento sellado que la sostiene.

Existe por la misma razón que ENG-001: un contrato que ofrece algo que la build
no ha demostrado es una mentira de procedencia, y la de «listo para FEP» sería
la más cara del producto, porque es su identidad.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.dossier import preparacion
from services.dossier.model import Campo, build_case_dossier
from services.dossier.taxonomy import Estado
from tests.fixtures_dossier import caso_completo, caso_parcial

ARTEFACTOS = Path(__file__).resolve().parents[2] / "scripts" / "artifacts_science"


def _fep06_sellados_go() -> list[Path]:
    """Manifiestos de `FEP-06*` terminados, sellados y con decisión GO."""
    sellados = []
    for manifiesto in sorted(ARTEFACTOS.glob("FEP-06*/manifest.json")):
        datos = json.loads(manifiesto.read_text(encoding="utf-8"))
        if (datos.get("sealed") is True and datos.get("decision") == "GO"
                and datos.get("status") == "finished"):
            sellados.append(manifiesto)
    return sellados


def _completo(clave: str, imprescindible: bool = True) -> preparacion.Requisito:
    return preparacion.Requisito(clave, Campo(clave, "dato", Estado.REGISTRADO), "prueba", imprescindible)


class TestFepGuard:
    def test_la_constante_solo_vale_true_con_fep06_sellado_go(self):
        if preparacion.TRANSFERENCIA_FEP_DEMOSTRADA:
            assert _fep06_sellados_go(), (
                "TRANSFERENCIA_FEP_DEMOSTRADA = True sin un scripts/artifacts_science/FEP-06* "
                "sellado GO. Un tercero todavía no ha reconstruido el paquete fuera de la "
                "sesión: la pestaña afirmaría una transferencia que nadie midió."
            )

    def test_con_todo_registrado_el_techo_es_revision(self):
        estado, razon = preparacion.estado_global([_completo("a"), _completo("b", False)])
        assert estado == "REVISION"
        assert "FEP-06" in razon

    def test_el_guardian_ve(self, monkeypatch):
        """Si la constante no gobernara la salida, las dos pruebas de arriba no verían nada."""
        monkeypatch.setattr(preparacion, "TRANSFERENCIA_FEP_DEMOSTRADA", True)
        estado, _ = preparacion.estado_global([_completo("a")])
        assert estado == "TRANSFERIBLE"

    @pytest.mark.parametrize("caso", [caso_completo, caso_parcial])
    def test_ninguna_corrida_real_llega_a_transferible(self, caso):
        datos = caso()
        auditoria = preparacion.build_preparacion(
            build_case_dossier(**datos), datos["eval_result"], datos["projection"],
        )
        assert auditoria["estado"] != "TRANSFERIBLE"
        assert auditoria["transferencia_fep_demostrada"] is False
        assert auditoria["alcance"] == "Auditor de readiness para FEP en desarrollo"
        # El paquete que ofrece la pestaña es el de la corrida, nunca «paquete FEP».
        assert "No es un paquete FEP" in auditoria["paquete"]["aviso"]

    def test_la_salida_no_promete_readiness(self):
        datos = caso_completo()
        texto = json.dumps(preparacion.build_preparacion(
            build_case_dossier(**datos), datos["eval_result"], datos["projection"],
        ), ensure_ascii=False).lower()
        for promesa in ("fep-ready", "fep ready", "listo para fep", "compatible con fep"):
            assert promesa not in texto, promesa
