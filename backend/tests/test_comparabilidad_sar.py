"""
Comparabilidad SAR: las condiciones químicas participan (SOL-04 / AMP-02).

El hallazgo que motiva este archivo (auditoría DevOps SOL, 2026-09-30, y su
ampliación real):

- La tabla SAR restaba afinidades entre corridas cuya preparación química
  era distinta. Reproducción real: la misma serie benzoica contra 3F75, base
  a pH 7,4 —especie acoplada `O=C([O-])c1ccccc1`, carga −1— reevaluada a
  pH 2 —especie `O=C(O)c1ccccc1`, carga 0, otro hash de SDF—. El Δ que
  mostraba la tabla confluaba el cambio de molécula con el cambio de
  ESPECIE: no era una comparación dentro de un protocolo común.
- La sonda del auditor (`.tmp/codex-devops-sol-20260930/sar-ph-probe.json`)
  lo probó extrayendo por AST la firma del árbol de entonces: comparaba
  receptor, versión, semilla, motor, exhaustividad, poses, confórmeros y
  caja — y OMITÍA el pH y la preparación del ligando.

La regla que este archivo protege, con la decisión de producto aprobada el
2026-10-02:

    Las diferencias de afinidad sólo se certifican entre corridas con la
    MISMA condición de preparación química y el mismo protocolo estructural.
    Si la condición difiere o no está registrada, SAR SE ABSTIENE: el delta
    no se fabrica y el motivo se escribe nombrando ambos valores.

Lo que se compara son CONDICIONES, no especies: los análogos acoplan
moléculas distintas por diseño — exigirles el mismo hash de ligando vaciaría
la tabla. Lo que debe coincidir es la regla con la que cada una fue
preparada: pH de protonación, motor, modo de tautómero, receptor, caja,
semilla, exhaustividad, poses, confórmeros.

Y `delta_score` es SIEMPRE ausente: el score agregado no es una magnitud
termodinámica; restar scores de modelos no mide nada y el producto no lo
certifica.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from services.sar.comparabilidad import (
    Comparabilidad,
    campos_ausentes,
    comparar_corridas,
    condicion_quimica_publica,
)


# ── Datos de prueba ──────────────────────────────────────────────────

RECEPTOR = "8b94" + "a" * 60
CAJA = {"box_center": [43.21, 2.19, 46.19], "box_size": [25.4, 25.4, 25.4]}


def _estado(
    *,
    aplicada=True,
    motor="dimorphite-dl",
    ph=7.4,
    modo="canonico",
    tautomeria_aplicada=True,
    smiles_acoplado="O=C([O-])c1ccccc1",
    carga=-1,
):
    """`estado_del_ligando` con la forma real que persiste el conformador."""
    return {
        "protonacion": {"aplicada": aplicada, "motor": motor, "ph": ph},
        "tautomeria": {"aplicada": tautomeria_aplicada, "modo": modo},
        "smiles_acoplado": smiles_acoplado,
        "carga_formal_neta": carga,
    }


def _corrida(**overrides):
    """Registro sintético con la forma real de `EvaluationResultORM`."""
    registro = {
        "receptor_sha256": RECEPTOR,
        "vina_version": "1.2.7",
        "vina_random_seed": 42,
        "docking_protocol": {
            "engine": "vina",
            "exhaustiveness": 8,
            "num_poses": 9,
            "conformers_generated": 1,
            "execution_provenance": dict(CAJA),
        },
        "ligand_state": _estado(),
        "affinity_kcal": -5.548,
        "total_score": 61.0,
    }
    registro.update(overrides)
    return SimpleNamespace(**registro)


#: La repetición real de la auditoría: benzoico a pH 2, especie neutra.
BENZOICO_PH2 = _corrida(
    ligand_state=_estado(ph=2.0, smiles_acoplado="O=C(O)c1ccccc1", carga=0),
    affinity_kcal=-5.412,
)


# ── 1. La reproducción de la auditoría ───────────────────────────────


def test_el_ph_distinto_no_es_comparable():
    """SOL-04/AMP-02: base a pH 7,4 (carga −1) contra la misma molécula a
    pH 2 (carga 0) NO es «protocolo coincidente»: son especies distintas."""
    comparacion = comparar_corridas(_corrida(), BENZOICO_PH2)
    assert not comparacion.comparable
    assert comparacion.estado == "abstained"
    # El motivo NOMBRa ambos valores en conflicto, no dice sólo «distinto».
    assert "pH de protonación" in comparacion.motivo
    assert "7.4 en la base" in comparacion.motivo
    assert "2 en el análogo" in comparacion.motivo


def test_la_misma_condicion_es_comparable():
    comparacion = comparar_corridas(_corrida(), _corrida(affinity_kcal=-5.2))
    assert comparacion.comparable
    assert comparacion.estado == "descriptive"
    assert comparacion.motivo is None


def test_sin_protonacion_en_ambas_es_una_condicion_legitima():
    """Dimorphite ausente en las dos corridas: forma neutra acoplada en
    ambas. Es la MISMA condición, no un dato faltante."""
    neutra = dict(ligand_state=_estado(aplicada=False, motor=None, ph=None, smiles_acoplado="CCO", carga=0))
    comparacion = comparar_corridas(_corrida(**neutra), _corrida(**neutra))
    assert comparacion.comparable


def test_protonada_contra_neutra_no_es_comparable():
    """Una corrida protonó y la otra acopló la forma neutra: la diferencia
    de afinidad confluaria molécula y preparación."""
    neutra = _corrida(
        ligand_state=_estado(aplicada=False, motor=None, ph=None, carga=0)
    )
    comparacion = comparar_corridas(_corrida(), neutra)
    assert not comparacion.comparable
    assert "protonación aplicada" in comparacion.motivo


def test_el_estado_del_ligando_ausente_abstiene():
    """Registro anterior a la columna: la condición química no está
    registrada y no se puede afirmar que coincida."""
    comparacion = comparar_corridas(_corrida(), _corrida(ligand_state=None))
    assert not comparacion.comparable
    assert "no se puede comparar" in comparacion.motivo
    assert "estado químico" in comparacion.motivo


def test_la_abstencion_por_dato_ausente_nombra_el_lado():
    """Quién no registró qué: sin ese dato el motivo no sirve para corregir."""
    base_sin_estado = comparar_corridas(_corrida(ligand_state=None), _corrida())
    assert "en la corrida base" in base_sin_estado.motivo

    analogo_sin_caja = comparar_corridas(_corrida(), _corrida(docking_protocol={}))
    assert "en el análogo" in analogo_sin_caja.motivo


def test_el_modo_de_tautomerio_distinto_no_es_comparable():
    """Canonizar o respetar la entrada son reglas de preparación distintas."""
    entrada = _corrida(ligand_state=_estado(modo="entrada", tautomeria_aplicada=False))
    comparacion = comparar_corridas(_corrida(), entrada)
    assert not comparacion.comparable
    assert "modo de tautómero" in comparacion.motivo


def test_la_diferencia_estructural_tampoco_es_comparable():
    otra_semilla = _corrida(vina_random_seed=7)
    comparacion = comparar_corridas(_corrida(), otra_semilla)
    assert not comparacion.comparable
    assert "semilla" in comparacion.motivo
    assert "42 en la base" in comparacion.motivo
    assert "7 en el análogo" in comparacion.motivo


def test_la_procedencia_incompleta_abstiene():
    incompleta = _corrida(
        docking_protocol={"engine": "vina", "exhaustiveness": 8}
    )
    assert campos_ausentes(incompleta)  # declara lo que falta, no lo calla
    comparacion = comparar_corridas(_corrida(), incompleta)
    assert not comparacion.comparable


def test_el_ruido_de_coma_flotante_en_la_caja_no_abstiene():
    """22.5 y 22.500000000004 son la misma caja: la abstención espuria
    bloquearía la tabla sola, como le pasaba al fingerprint del preflight."""
    ruidosa = _corrida(
        docking_protocol={
            "engine": "vina", "exhaustiveness": 8, "num_poses": 9,
            "conformers_generated": 1,
            "execution_provenance": {
                "box_center": [43.21, 2.19, 46.19],
                "box_size": [25.4, 25.400000000000004, 25.4],
            },
        }
    )
    comparacion = comparar_corridas(_corrida(), ruidosa)
    assert comparacion.comparable


# ── 2. Todos los campos firmados participan ─────────────────────────


@pytest.mark.parametrize(
    "análogo",
    [
        # estructurales (la firma heredada del árbol de la auditoría)
        _corrida(receptor_sha256="7f29" + "b" * 60),
        _corrida(vina_version="1.2.5"),
        _corrida(vina_random_seed=7),
        _corrida(docking_protocol={"engine": "qvina2", "exhaustiveness": 8,
                                  "num_poses": 9, "conformers_generated": 1,
                                  "execution_provenance": dict(CAJA)}),
        _corrida(docking_protocol={"engine": "vina", "exhaustiveness": 16,
                                   "num_poses": 9, "conformers_generated": 1,
                                   "execution_provenance": dict(CAJA)}),
        _corrida(docking_protocol={"engine": "vina", "exhaustiveness": 8,
                                   "num_poses": 5, "conformers_generated": 1,
                                   "execution_provenance": dict(CAJA)}),
        _corrida(docking_protocol={"engine": "vina", "exhaustiveness": 8,
                                   "num_poses": 9, "conformers_generated": 30,
                                   "execution_provenance": dict(CAJA)}),
        _corrida(docking_protocol={"engine": "vina", "exhaustiveness": 8,
                                   "num_poses": 9, "conformers_generated": 1,
                                   "execution_provenance": {
                                       "box_center": [9.0, 9.0, 9.0],
                                       "box_size": [25.4, 25.4, 25.4]}}),
        # químicas (lo que SOL-04/AMP-02 añade)
        BENZOICO_PH2,
        _corrida(ligand_state=_estado(aplicada=False, motor=None, ph=None, carga=0)),
        _corrida(ligand_state=_estado(modo="entrada", tautomeria_aplicada=False)),
        _corrida(ligand_state=_estado(tautomeria_aplicada=False)),
    ],
    ids=[
        "receptor", "versión", "semilla", "motor", "exhaustividad", "poses",
        "confórmeros", "caja", "pH", "protonación", "modo-tautómero",
        "canonicalización-tautómero",
    ],
)
def test_cada_campo_firmado_produce_abstención(análogo):
    """La regresión del criterio de cierre: cambiar cualquier condición
    que define la comparación deja de ser comparable."""
    comparacion = comparar_corridas(_corrida(), análogo)
    assert not comparacion.comparable, comparacion.motivo
    assert comparacion.motivo  # y siempre dice por qué


# ── 3. La condición química que la fila expone ───────────────────────


def test_la_condicion_quimica_publica_dice_que_especie_se_acoplo():
    publicada = condicion_quimica_publica(BENZOICO_PH2)
    assert publicada["ph_protonacion"] == 2.0
    assert publicada["smiles_acoplado"] == "O=C(O)c1ccccc1"
    assert publicada["carga_formal_neta"] == 0


def test_la_condicion_quimica_publica_sin_registro_queda_ausente():
    publicada = condicion_quimica_publica(_corrida(ligand_state=None))
    assert publicada == {"ph_protonacion": None, "smiles_acoplado": None,
                         "carga_formal_neta": None}


# ── 4. La fila del router: la abstención no fabrica delta ────────────


def _analogo():
    return SimpleNamespace(
        molecule=SimpleNamespace(
            id="mol-2", name="4-fluorobenzoico",
            smiles="Oc1ccc(F)cc1C(=O)O", smiles_hash="b" * 64,
        ),
        total_score=58.0,
        affinity_kcal=-5.323,
        clgnn_score=None, xgb_score=0.42, gnn_score=None,
        molecular_weight=140.1, log_p=2.1, tpsa=37.3, lipinski_pass=True,
        sa_score=1.8,
        ligand_state=_estado(smiles_acoplado="O=C([O-])c1ccc(F)cc1", carga=-1),
    )


def _fila(**kwargs):
    from api.routers.sar import _fila_sar

    return _fila_sar(
        _analogo(),
        similarity=0.83,
        base_affinity=-5.548,
        es_base=False,
        **kwargs,
    )


def test_la_fila_comparable_lleva_el_delta_de_afinidad():
    fila = _fila(comparacion=Comparabilidad(comparable=True, motivo=None))
    assert fila["comparison_state"] == "descriptive"
    assert fila["comparison_reason"] is None
    assert fila["delta_affinity"] == round(-5.323 - (-5.548), 2)
    assert fila["highlight"]


def test_la_fila_abstenida_no_fabrica_el_delta():
    motivo = "condiciones distintas — pH de protonación: 7.4 en la base, 2 en el análogo"
    fila = _fila(comparacion=Comparabilidad(comparable=False, motivo=motivo))
    assert fila["comparison_state"] == "abstained"
    assert fila["comparison_reason"] == motivo
    assert fila["highlight"] == motivo  # el motivo es lo que la fila enseña
    # La afinidad cruda SIGUE visible; lo que no se fabrica es la resta.
    assert fila["affinity_kcal"] == -5.323
    assert fila["delta_affinity"] is None


def test_el_score_agregado_nunca_produce_delta():
    """Decisión aprobada 2026-10-02: el score agregado no es una magnitud
    termodinámica; restar scores de modelos no mide nada."""
    comparable = _fila(comparacion=Comparabilidad(comparable=True, motivo=None))
    abstenido = _fila(comparacion=Comparabilidad(comparable=False, motivo="m"))
    assert comparable["delta_score"] is None
    assert abstenido["delta_score"] is None


def test_la_fila_expone_su_condicion_quimica():
    fila = _fila(comparacion=Comparabilidad(comparable=True, motivo=None))
    assert fila["ph_protonacion"] == 7.4
    assert fila["smiles_acoplado"] == "O=C([O-])c1ccc(F)cc1"
    assert fila["carga_formal_neta"] == -1
