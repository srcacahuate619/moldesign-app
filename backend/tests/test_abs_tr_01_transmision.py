"""ABS-TR-01, fidelidad semántica: el veredicto físico llega igual a todas las salidas.

Los detalles de cada pose son los que redacta el productor
(`test_detalle_fisico_en_ingles.DETALLES`), no frases inventadas para la prueba.

Diseño de la Fase D de la auditoría científica (`abstencion_y_falso_bloqueo.md`,
«dos tareas separadas»). Esta es la primera: fixtures con un estado lógico
conocido, que se siguen del productor a cada superficie que lo cuenta. No mide
química ni sensibilidad molecular; mide que **un fallo, una ausencia o una
reserva no se pierdan ni se conviertan en otra cosa por el camino**.

Regla previa del diseño, aplicada tal cual: una pérdida de un fallo o de una
ausencia crítica, o una salida favorable sin soporte, en una sola fixture, es
NO_GO de transmisión.

El control que se sigue es la validez física de la pose principal: es el que
todas las superficies cuentan y el que la auditoría encontró aplanado en varias
(SCI-A-004, 007, 027 y 059). Cinco estados lógicos × siete superficies:

    superficie                        lo que se lee
    ───────────────────────────────── ────────────────────────────────────────
    resumen del informe               dimensión `physical` y estado global
    modelo del dossier                estado físico de la pose principal
    Preparación                       requisito `pose.validez_fisica`
    ZIP del dossier                   `preparacion/audit.json` y el manifiesto
    dossier en inglés                 los mismos estados, sin castellano
    Molcy                             `controles_de` de la pose principal
    lote                              límite de validez física de la cohorte
"""

from __future__ import annotations

import copy
import io
import json
import zipfile

import pytest

from core.i18n_plantillas import _PARECE_CASTELLANO
from services.blockchain.evidence_summary import build_evidence_summary
from services.cohort.evidence import limite_de_validez_fisica
from services.dossier.localization import traducir_dossier
from services.dossier.model import build_case_dossier
from services.dossier.package import construir_paquete
from services.dossier.pdf import render_dossier_pdf
from services.dossier.preparacion import build_preparacion
from services.molcy.ensamble import controles_de
from tests.fixtures_dossier import caso_completo
from tests.test_detalle_fisico_en_ingles import DETALLES

#: Los estados lógicos de la fixture. `ausente` es «la corrida no trae evidencia
#: estructural»: distinto de `not_evaluated`, que es «el validador no dictaminó».
ESTADOS = ("passed", "review", "failed", "not_evaluated", "ausente")

#: Lo que cada superficie TIENE que decir en cada estado. Es la verdad de la
#: fixture, escrita antes de mirar las salidas: favorable sólo con `passed`.
ESPERADO = {
    #             resumen.physical   dossier/Preparación   Molcy            favorable
    "passed":        ("available",     "PASA",               "passed",        True),
    "review":        ("review",        "REVISAR",            "review",        False),
    "failed":        ("failed",        "ABSTENCION",         "failed",        False),
    "not_evaluated": ("not_evaluated", "NO_EVALUADO",        "not_evaluated", False),
    "ausente":       ("not_evaluated", "NO_EVALUADO",        None,            False),
}

#: Estados de Preparación que cuentan como «se puede seguir» en el manifiesto.
_FAVORABLES_PREPARACION = {"PASA", "REGISTRADO"}


def _caso(estado: str) -> dict:
    """El caso completo del dossier con la pose principal en el estado pedido."""
    caso = caso_completo()
    resultado = caso["eval_result"]
    if estado == "ausente":
        resultado.structural_evidence = None
        return caso
    evidencia = copy.deepcopy(resultado.structural_evidence)
    evidencia["stage_status"] = estado
    principal = next(p for p in evidencia["poses"] if p["rank"] == 1)
    principal["status"] = estado
    if estado == "failed":
        principal["checks"] = [{"check": "sanitization", "estado": "PASA"},
                               {"check": "internal_energy", "estado": "FALLA"}]
        principal["checks_que_fallan"] = ["internal_energy"]
        principal["detail"] = DETALLES["fallida"]
    elif estado == "review":
        principal["checks"] = [{"check": "sanitization", "estado": "PASA"},
                               {"check": "internal_energy", "estado": "NO_EVALUADO"}]
        principal["checks_que_fallan"] = []
        principal["detail"] = DETALLES["revision_no_evaluados"]
    elif estado == "not_evaluated":
        principal["checks"] = []
        principal["checks_que_fallan"] = []
        principal["detail"] = DETALLES["validador_lanzo"]
    if estado != "passed":
        # Ninguna otra pose «salva» la corrida: la fixture aísla la principal.
        for otra in evidencia["poses"]:
            if otra["rank"] != 1:
                otra.update({k: principal[k] for k in ("status", "checks", "checks_que_fallan", "detail")})
    resultado.structural_evidence = evidencia
    return caso


def _salidas(estado: str) -> dict:
    """Las siete superficies de una misma fixture."""
    caso = _caso(estado)
    dossier = build_case_dossier(**caso)
    auditoria = build_preparacion(dossier, caso["eval_result"], caso["projection"])
    datos, _, raiz = construir_paquete(
        dossier=dossier, pdf_bytes=render_dossier_pdf(dossier).getvalue(),
        projection_json=caso["projection"].model_dump_json(indent=2), preparacion=auditoria)
    with zipfile.ZipFile(io.BytesIO(datos)) as zf:
        zip_audit = json.loads(zf.read(f"{raiz}/preparacion/audit.json"))
        manifiesto = json.loads(zf.read(f"{raiz}/manifest.json"))
    snap = {"structural_evidence": caso["eval_result"].structural_evidence,
            "receptor_sha256": "e" * 64}
    return {
        "resumen": build_evidence_summary(caso["eval_result"], caso["target"], caso["molecule"]),
        "dossier": dossier,
        "preparacion": auditoria,
        "zip_audit": zip_audit,
        "manifiesto": manifiesto,
        "ingles": traducir_dossier(auditoria, "en"),
        "molcy": controles_de(snap, {"rank": 1, "affinity": -9.5}),
    }


def _requisito(auditoria: dict, clave: str = "pose.validez_fisica") -> dict:
    return next(r for b in auditoria["bloques"] for r in b["requisitos"] if r["clave"] == clave)


@pytest.fixture(scope="module", params=ESTADOS)
def salida(request):
    return request.param, _salidas(request.param)


class TestCadaSuperficieDiceLoQueLaFixtureEs:
    def test_resumen(self, salida):
        estado, s = salida
        fisica = next(d for d in s["resumen"]["dimensions"] if d["id"] == "physical")
        assert fisica["status"] == ESPERADO[estado][0], (estado, fisica)
        if not ESPERADO[estado][3]:
            assert s["resumen"]["status"] != "ready", (estado, s["resumen"]["status"])

    def test_dossier(self, salida):
        estado, s = salida
        principal = next((p for p in s["dossier"].evidencia_poses if p.es_vina_top1), None)
        if principal is None:
            assert estado == "ausente"
            control = next(c for c in s["dossier"].controles if c.codigo == "VALIDEZ_FISICA_POSES")
            assert control.estado.value == ESPERADO[estado][1]
        else:
            assert principal.estado_fisico.value == ESPERADO[estado][1], (estado, principal)

    def test_preparacion(self, salida):
        estado, s = salida
        validez = _requisito(s["preparacion"])
        assert validez["estado"] == ESPERADO[estado][1], (estado, validez)
        if validez["estado"] not in _FAVORABLES_PREPARACION:
            # Imprescindible y no superado: bloquea o pide revisión, nunca se calla.
            assert ("pose.validez_fisica" in s["preparacion"]["bloqueantes"]
                    or "pose.validez_fisica" in s["preparacion"]["en_revision"]), estado

    def test_zip(self, salida):
        estado, s = salida
        assert _requisito(s["zip_audit"]) == json.loads(json.dumps(_requisito(s["preparacion"])))
        resumen = s["manifiesto"]["preparacion"]
        for lista in ("bloqueantes", "en_revision"):
            assert resumen[lista] == s["preparacion"][lista], (estado, lista)

    def test_ingles(self, salida):
        estado, s = salida
        validez = _requisito(s["ingles"])
        assert validez["estado"] == ESPERADO[estado][1]
        for campo in ("etiqueta", "razon"):
            assert not _PARECE_CASTELLANO.search(validez.get(campo) or ""), (estado, campo, validez)

    def test_molcy(self, salida):
        estado, s = salida
        esperado = ESPERADO[estado][2]
        if esperado is None:
            assert s["molcy"] is None
        else:
            assert s["molcy"]["estado"] == esperado, (estado, s["molcy"])
        if estado == "failed":
            assert s["molcy"]["fallos"] == ["internal_energy"]


class TestNingunaSalidaFavorableSinSoporte:
    """El endpoint primario de transmisión, comprobado de una vez sobre todo."""

    def test_favorable_solo_con_passed(self, salida):
        estado, s = salida
        fisica = next(d for d in s["resumen"]["dimensions"] if d["id"] == "physical")
        favorables = {
            "resumen": fisica["status"] == "available",
            "preparacion": _requisito(s["preparacion"])["estado"] in _FAVORABLES_PREPARACION,
            "ingles": _requisito(s["ingles"])["estado"] in _FAVORABLES_PREPARACION,
            "molcy": (s["molcy"] or {}).get("estado") == "passed",
        }
        if ESPERADO[estado][3]:
            assert all(favorables.values()), (estado, favorables)
        else:
            assert not any(favorables.values()), (estado, favorables)

    def test_un_fallo_no_se_convierte_en_ausencia_ni_en_revision(self, salida):
        estado, s = salida
        if estado != "failed":
            pytest.skip("sólo aplica al fallo medido")
        fisica = next(d for d in s["resumen"]["dimensions"] if d["id"] == "physical")
        assert fisica["status"] not in {"not_evaluated", "review"}
        assert _requisito(s["preparacion"])["estado"] not in {"NO_EVALUADO", "REVISAR"}
        assert s["molcy"]["estado"] != "not_evaluated"


class TestElLoteCuentaLoQueRecibe:
    @pytest.mark.parametrize("veredictos,debe_decir,no_debe_decir", [
        ({}, "Ninguna pose", "superaron"),
        ({"passed": 0, "failed": 0, "review": 0}, "Ninguna pose", "superaron"),
        ({"passed": 3}, "", "Ninguna pose"),
        ({"passed": 2, "failed": 1}, "", "Ninguna pose"),
        ({"review": 4}, "", "Ninguna pose"),
    ])
    def test_el_limite_no_contradice_el_recuento(self, veredictos, debe_decir, no_debe_decir):
        texto = limite_de_validez_fisica(veredictos)
        assert debe_decir in texto
        assert no_debe_decir not in texto

    def test_un_fallo_en_el_lote_no_se_redacta_como_todas_superadas(self):
        todas = limite_de_validez_fisica({"passed": 3})
        con_fallo = limite_de_validez_fisica({"passed": 2, "failed": 1})
        assert todas != con_fallo
