"""La ruta peptídica reportaba −4.0 kcal/mol siempre.

Fase 0 de `docs/74_ARQUITECTURA_DISPATCHER_DE_PROTOCOLOS.md`: reparar los
contratos científicos ANTES de mover código. El §7.3 lo pone como correctivo
obligatorio, y al medirlo salió más rotundo de lo que el documento describe.

═══════════════════════════════════════════════════════════════════════════
LA CADENA COMPLETA, MEDIDA
═══════════════════════════════════════════════════════════════════════════

1. `sidecars/esmfold/predictor.py::_parse_vina_pdbqt` leía la afinidad real de
   `REMARK VINA RESULT`, la convertía en una «confianza» y TIRABA el número:

       # Calcular confianza desde la afinidad: más negativo = mejor
       conf = min(1.0, max(0.1, 1.0 - abs(afinidad) / 15.0))

   El comentario dice «más negativo = mejor» y la fórmula hace lo contrario:
   Vina −12 daba 0.200 y Vina −4 daba 0.733. **Cuanto mejor el acoplamiento,
   menos confianza.**

2. `services/docking/peptide_docking.py` —y su copia inline en
   `queue_handler.py`— reconvertían esa confianza en afinidad:

       aff = max(-12.0, min(-4.0, -1.5 * conf))

Encadenadas:

    Vina real   conf    afinidad persistida
       −2.0     0.867          −4.0
       −6.0     0.600          −4.0
      −12.0     0.200          −4.0

`-1.5 * conf` con conf en [0.1, 1.0] vale entre −1.5 y −0.15, y todos esos
valores son **mayores** que −4.0, así que `min(-4.0, ·)` devuelve −4.0 sin
excepción. El documento decía «prácticamente todas las poses»; es todas,
siempre, y se puede demostrar por álgebra.

Además, `_fallback_poses` devolvía la estructura plegada SIN acoplar como si
fuera una pose, con una confianza inventada de 0.5 — y aguas abajo eso también
se convertía en −4.0.
"""

from __future__ import annotations

from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
EJECUTORES = {
    "peptide_docking": BACKEND / "services" / "docking" / "peptide_docking.py",
    "queue_handler": BACKEND / "services" / "docking" / "queue_handler.py",
}


def _codigo(ruta: Path) -> list[str]:
    return [
        linea.strip()
        for linea in ruta.read_text(encoding="utf-8").splitlines()
        if not linea.strip().startswith("#")
    ]


# ── La demostración algebraica del defecto ───────────────────────────────

def test_la_formula_vieja_devolvia_siempre_menos_cuatro():
    """Ancla el porqué: sin esto, «siempre −4.0» parece una exageración."""
    def conf_desde_afinidad(vina: float) -> float:
        return min(1.0, max(0.1, 1.0 - abs(vina) / 15.0))

    def afinidad_desde_conf(conf: float) -> float:
        return max(-12.0, min(-4.0, -1.5 * conf))

    for vina in (-2.0, -4.0, -6.0, -8.0, -10.0, -12.0, -14.0):
        conf = conf_desde_afinidad(vina)
        assert afinidad_desde_conf(conf) == -4.0, (
            f"con Vina {vina} la cadena vieja daba algo distinto de −4.0; "
            "revisa la reconstrucción del defecto"
        )

    # Y la inversión: mejor afinidad, menos confianza.
    assert conf_desde_afinidad(-12.0) < conf_desde_afinidad(-4.0)


# ── El defecto no puede volver ───────────────────────────────────────────

@pytest.mark.parametrize("nombre,ruta", EJECUTORES.items(), ids=list(EJECUTORES))
def test_ningun_camino_convierte_confianza_en_afinidad(nombre: str, ruta: Path):
    culpables = [
        linea for linea in _codigo(ruta)
        if ("-1.5 *" in linea or "8.0 * " in linea)
        and ("aff" in linea.lower() or "min(-4" in linea)
    ]
    assert not culpables, (
        f"{nombre} vuelve a derivar una afinidad de una confianza: {culpables}. "
        "pLDDT e ipTM describen el plegado; convertirlos a kcal/mol inventa "
        "una medida que nadie hizo."
    )


def test_el_sidecar_conserva_la_afinidad_de_vina():
    fuente = (BACKEND / "sidecars" / "esmfold" / "predictor.py").read_text(encoding="utf-8")
    assert "vina_affinity_kcal_mol=current_affinity" in fuente, (
        "el parser volvió a descartar la afinidad de Vina"
    )
    culpables = [
        l for l in fuente.splitlines()
        if "1.0 - abs(" in l and not l.strip().startswith("#")
    ]
    assert not culpables, (
        f"volvió la conversión afinidad→confianza en el sidecar: {culpables}"
    )


def test_la_pose_declara_de_donde_salio_su_geometria():
    """Estructura plegada y pose acoplada dejan de ser indistinguibles."""
    import sys

    sys.path.insert(0, str(BACKEND / "sidecars" / "esmfold"))
    try:
        from predictor import (  # type: ignore[import-not-found]
            ORIGEN_SOLO_PLEGADO,
            ORIGEN_STUB,
            ORIGEN_VINA,
            PredictedPose,
        )
    finally:
        sys.path.pop(0)

    assert {ORIGEN_VINA, ORIGEN_SOLO_PLEGADO, ORIGEN_STUB} == {
        "vina_docked",
        "folded_structure_only",
        "stub",
    }
    pose = PredictedPose(rank=1, confidence=0.0, ligand_pdb="")
    assert hasattr(pose, "vina_affinity_kcal_mol")
    assert pose.vina_affinity_kcal_mol is None, (
        "sin afinidad explícita el campo tiene que quedar en None, no en 0.0: "
        "«afinidad cero» y «no hubo afinidad» no son lo mismo"
    )


def test_el_cliente_propaga_los_dos_campos():
    from services.esmfold.service import ESMFoldPose

    pose = ESMFoldPose(rank=1, confidence=0.9, ligand_pdb="")
    assert pose.vina_affinity_kcal_mol is None
    assert hasattr(pose, "origen")


def test_el_sidecar_los_expone_en_su_api():
    """Si no viajan por HTTP, el cliente no puede verlos."""
    fuente = (BACKEND / "sidecars" / "esmfold" / "app.py").read_text(encoding="utf-8")
    assert "vina_affinity_kcal_mol" in fuente and "origen" in fuente, (
        "el contrato HTTP del sidecar dejó de transmitir la afinidad real"
    )


# ── Sin acoplamiento no se fabrica una afinidad ──────────────────────────

@pytest.mark.parametrize("nombre,ruta", EJECUTORES.items(), ids=list(EJECUTORES))
def test_sin_pose_acoplada_se_avisa_en_critica(nombre: str, ruta: Path):
    fuente = ruta.read_text(encoding="utf-8")
    assert "PEPTIDO_SIN_ACOPLAMIENTO" in fuente, (
        f"{nombre} no distingue «hubo estructura» de «hubo acoplamiento». "
        "`DockingResult` exige una afinidad, y antes ese contrato se cumplía "
        "rellenándolo con −4.0."
    )


@pytest.mark.parametrize("nombre,ruta", EJECUTORES.items(), ids=list(EJECUTORES))
def test_la_afinidad_sale_de_la_pose_y_no_de_la_confianza(nombre: str, ruta: Path):
    fuente = ruta.read_text(encoding="utf-8")
    assert "vina_affinity_kcal_mol" in fuente, (
        f"{nombre} dejó de leer la afinidad real de la pose"
    )


def test_el_fallback_marca_que_no_hubo_docking():
    fuente = (BACKEND / "sidecars" / "esmfold" / "predictor.py").read_text(encoding="utf-8")
    bloque = fuente[fuente.index("def _fallback_poses") : fuente.index("# ── OpenMM")]
    assert "ORIGEN_SOLO_PLEGADO" in bloque, (
        "la estructura sin acoplar vuelve a salir como una pose normal"
    )
    assert "confidence=0.5" not in bloque, (
        "vuelve la confianza inventada de 0.5 para una estructura sin acoplar"
    )


# ── Lo que el documento 74 pide conservar por separado ───────────────────

def test_el_aviso_dice_que_el_plddt_no_es_una_afinidad():
    for ruta in EJECUTORES.values():
        fuente = ruta.read_text(encoding="utf-8")
        assert "describe el PLEGADO" in fuente or "describe el plegado" in fuente, (
            f"{ruta.name} dejó de separar confianza estructural de afinidad"
        )


def test_el_resultado_peptidico_se_declara_exploratorio():
    fuente = EJECUTORES["peptide_docking"].read_text(encoding="utf-8")
    assert "exploratorio" in fuente, (
        "el documento 74 §7.3 exige que Vina sobre péptidos se mantenga como "
        "resultado exploratorio hasta tener benchmark de poses y repetibilidad"
    )
