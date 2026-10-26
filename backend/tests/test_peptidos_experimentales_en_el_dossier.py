"""La vía de péptidos se marca EXPERIMENTAL en el dossier (decisión del propietario, 2026-10-04).

AGENTS.md: «La ciencia de ESMFold no está validada: está probado que carga y sirve poses, no que las poses sean
buenas». Un científico que reciba el dossier de un péptido tiene que leerlo en el documento, no sólo en la
pantalla; si no, el resultado de un péptido se lee con la misma confianza que el de una molécula pequeña.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from services.dossier.model import _campos_de_protocolo_y_abstencion


def _campos(docking_protocol, afinidad=-4.2):
    resultado = SimpleNamespace(docking_protocol=docking_protocol, ligand_state=None)
    return [c.as_dict() for c in _campos_de_protocolo_y_abstencion(resultado, {"top_pose_affinity": afinidad})]


def _validacion(campos):
    return [c for c in campos if c["etiqueta"] == "Validación del método peptídico"]


@pytest.mark.parametrize("motor", ["esmfold", "ESMFold", "colabfold"])
def test_una_corrida_peptidica_lleva_la_marca_experimental(motor):
    marca = _validacion(_campos({"engine_executed": motor}))
    assert len(marca) == 1
    assert marca[0]["estado"] == "REVISAR"
    assert marca[0]["valor_es_clasificacion"] is True
    assert marca[0]["valor"].startswith("EXPERIMENTAL")
    assert "no está validada" in marca[0]["valor"]
    assert "no hereda validez" in marca[0]["razon"]


def test_la_marca_va_tambien_cuando_no_hubo_afinidad():
    # El caso en que la estructura se plegó y no se pudo acoplar: sigue siendo experimental.
    assert len(_validacion(_campos({"engine_executed": "esmfold"}, afinidad=None))) == 1


@pytest.mark.parametrize("protocolo", [{"engine_executed": "vina"}, {"engine": "vina"}, {}, None])
def test_una_molecula_pequena_no_lleva_la_marca(protocolo):
    # Control negativo: la marca no se pone a todo.
    assert _validacion(_campos(protocolo)) == []
