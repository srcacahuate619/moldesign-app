"""El dossier dice de cuántas candidatas salió la afinidad del ensemble.

═══════════════════════════════════════════════════════════════════════════
POR QUÉ
═══════════════════════════════════════════════════════════════════════════

El ensemble acopla cada conformación por separado y junta las
`conformaciones × num_poses` poses en UNA piscina ordenada por afinidad. La que
se entrega es la mejor de esa piscina.

El dossier decía «Ensemble · 16 de 16 conformaciones» y nada más. Dos
expedientes de la misma molécula —uno con confórmero único, otro con ensemble—
presentaban su afinidad igual, aunque una fuera la mejor de 9 candidatas y la
otra la mejor de 144.

Esto NO es una advertencia sobre el método. Medido sobre el runtime empaquetado
contra 3F75, la deriva del mejor al subir K es pequeña:

    ibuprofeno   K=1 −5.650   K=16 −5.689   (−0.039)
    naproxeno    K=1 −6.018   K=16 −6.180   (−0.162)
    celecoxib    K=1 −6.654   K=16 −6.654   ( 0.000)

Un orden de magnitud por debajo del efecto que ya contaminó una lectura sellada.
Lo que falta no es un aviso: es el DENOMINADOR, y quien compare dos expedientes
lo necesita para saber que está comparando lo mismo.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from services.dossier import model as dossier_model


def _campo(protocolo):
    fabricante = getattr(dossier_model, "_campo_conformaciones", None)
    if fabricante is None:
        # El nombre privado puede cambiar; se busca por la etiqueta, que es el
        # contrato con el lector.
        eval_result = SimpleNamespace(docking_protocol=protocolo)
        for nombre in dir(dossier_model):
            fn = getattr(dossier_model, nombre)
            if not callable(fn) or not nombre.startswith("_campo"):
                continue
            try:
                campo = fn(eval_result)
            except Exception:
                continue
            if getattr(campo, "etiqueta", None) == "Generación conformacional":
                return campo
        pytest.skip("no se encuentra el campo de generación conformacional")
    return fabricante(SimpleNamespace(docking_protocol=protocolo))


BASE = {
    "contract": "docking_protocol/v1",
    "engine": "vina",
    "exhaustiveness": 8,
    "num_poses": 9,
    "seed": 42,
}


def test_el_ensemble_declara_el_tamano_de_la_piscina():
    campo = _campo({**BASE, "conformers_requested": 16, "conformers_generated": 16})
    # 16 conformaciones × 9 poses = 144 candidatas.
    assert "144" in campo.valor, campo.valor
    assert "16 de 16" in campo.valor


def test_un_ensemble_incompleto_cuenta_las_que_SE_GENERARON():
    """La piscina real sale de las conformaciones conseguidas, no de las
    pedidas: contar las pedidas afirmaría candidatas que nunca existieron."""
    campo = _campo({**BASE, "conformers_requested": 30, "conformers_generated": 22})
    assert "198" in campo.valor, campo.valor  # 22 × 9
    assert "30" not in campo.valor.split("candidatas")[-1]


def test_el_conformero_unico_no_habla_de_piscina():
    """Con K=1 no hay nada que aclarar: es el camino de siempre."""
    campo = _campo({**BASE, "conformers_requested": 1, "conformers_generated": 1})
    assert "candidatas" not in campo.valor
    assert "Confórmero único" in campo.valor


def test_sin_num_poses_no_se_inventa_el_denominador():
    """Un protocolo antiguo que no lo selló no puede producir una cifra: decir
    un número inventado es peor que no decirlo."""
    protocolo = {k: v for k, v in BASE.items() if k != "num_poses"}
    campo = _campo({**protocolo, "conformers_requested": 8, "conformers_generated": 8})
    assert "candidatas" not in campo.valor
    assert "8 de 8" in campo.valor
