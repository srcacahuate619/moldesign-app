"""M5_gated está publicado y no se ejecuta: la familia no casa por ortografía.

Auditoría del 2026-09-04, y **corrección de esa misma auditoría el mismo día**.

═══════════════════════════════════════════════════════════════════════════
LO QUE SE CONCLUYÓ MAL PRIMERO
═══════════════════════════════════════════════════════════════════════════

`rescoring/artifacts/stacking_weights.json` trae para metaloenzimas:

    {"vina": 0.0, "prob": 0.0, "gnn": 0.0, "clgnn": 1.0,
     "_auc": 0.5, "_delta": 0.0453}

Se leyó como una calibración degenerada —Vina a cero y el ranking entero en un
modelo con `_auc` 0.5— y se añadió un filtro que la descartaba. **Estaba mal**,
y estas pruebas existen para que no se repita:

1. Esos pesos son el **diseño publicado**. `docs/PAPER_UMS.md` §2.1.3 los
   documenta y los justifica: «Metalloenzyme: Vina = 0.00 (validated: Vina AUC
   < 0.56 on all three metal targets with full pipeline). CL-GNN dominates
   (0.90–1.00). UMS is added with weight w5 tuned per target», y declara este
   archivo como el artefacto donde viven.

2. `_auc` **no mide el pipeline de metaloenzimas**. Lo escribe
   `scripts/benchmark_ef_vina.py`, cuyo grid recorre sólo `vina/xgb/clgnn` —UMS
   no entra—. Para esta familia eso deja fuera al único scorer que discrimina:
   sobre CA2, vina 0.558, xgb 0.766, clgnn 0.592 y **UMS 0.978**
   (`docs/26_UNIVERSAL_METAL_SCORE_RESULTS.md` §1.3). Un 0.5 ahí no dice «la
   calibración es basura»: dice «los tres solos no discriminan aquí», que es
   la premisa por la que existe M5.

Descartar esos pesos devolvía las metaloenzimas a M4, la línea base que el
paper mide como peor: CA2 pasa de M5_gated 0.926 a M4 0.804.

═══════════════════════════════════════════════════════════════════════════
LO QUE SÍ ES UN FALLO
═══════════════════════════════════════════════════════════════════════════

La puerta de UMS acepta las dos grafías (`_is_metalloenzyme_family`), pero la
búsqueda de pesos casa literal contra la clave del JSON, que es `metaloenzyme`
(una L). El catálogo curado escribe `metalloenzyme` (dos). `scoring/ums.py`
documenta esa divergencia como «gotcha crítico» y dice que se normaliza en los
dos sitios — se normaliza en uno.

Resultado: los receptores de esa familia reciben los pesos `default`, que son
los de M4. **M5_gated, tal como está publicado, no se ha ejecutado nunca sobre
el catálogo.**
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
PESOS = RAIZ / "rescoring" / "artifacts" / "stacking_weights.json"
ENGINE = RAIZ / "backend" / "scoring" / "engine.py"
OPTIMIZADOR = RAIZ / "scripts" / "benchmark_ef_vina.py"


def _pesos_guardados() -> dict:
    return json.loads(PESOS.read_text(encoding="utf-8"))


def _sin_metadatos(pesos: dict) -> dict:
    return {k: v for k, v in pesos.items() if not k.startswith("_")}


# ── Lo que no se puede volver a romper ───────────────────────────────────

def test_los_pesos_publicados_viven_ahora_en_perfiles_exactos():
    """Esta prueba anclaba el estado ANTERIOR, y falló cuando debía.

    Su versión previa exigía que la entrada genérica `metaloenzyme` de
    `stacking_weights.json` siguiera aplicándose con `vina=0.0, clgnn=1.0`,
    porque `docs/PAPER_UMS.md` §2.1.3 la documenta así. Y decía, literalmente,
    que cuando se decidiera activar M5 sobre el catálogo tenía que fallar.

    `docs/75_DECISION_CIENTIFICA_M5_ZN_V1.md` tomó esa decisión: no hay un peso
    familiar genérico. Los pesos del paper son por diana y no coinciden con la
    entrada genérica —CA2 usa GNN-D, no CL-GNN; MMP9 no usa Vina ni GNN; ACE no
    usa GNN— así que la entrada se retira y los tres perfiles exactos viven en
    `services/pipeline/protocols/m5/zinc.py`.

    Lo que se comprueba ahora es que esos pesos siguen existiendo donde toca.
    """
    from services.pipeline.protocols.m5.zinc import PERFILES

    ca2 = PERFILES["3DC3"]
    assert ca2.peso_vina == 0.20 and ca2.peso_gnn_d == 0.20 and ca2.peso_ums == 0.40
    mmp9 = PERFILES["1GKC"]
    assert mmp9.peso_vina == 0.0 and mmp9.peso_xgb == 0.75 and mmp9.peso_ums == 0.25
    ace = PERFILES["1O86"]
    assert ace.peso_vina == 0.20 and ace.peso_xgb == 0.40 and ace.peso_ums == 0.40


def test_no_se_filtran_calibraciones_por_un_auc_que_no_ve_ums():
    """El filtro que se añadió y se retiró el mismo día."""
    fuente = ENGINE.read_text(encoding="utf-8")
    codigo = [
        linea for linea in fuente.splitlines() if not linea.strip().startswith("#")
    ]
    culpables = [
        linea.strip()
        for linea in codigo
        if "_auc" in linea and ("<" in linea or ">=" in linea)
    ]
    assert not culpables, (
        f"vuelve un filtro sobre `_auc`: {culpables}. Ese número mide "
        "vina+xgb+clgnn SIN UMS, así que en metaloenzimas no puede ver el "
        "scorer que decide (UMS, AUC 0.978 en CA2)."
    )


def test_el_optimizador_no_pone_piso_de_auc():
    """Un piso rechazaría la calibración que el propio paper valida."""
    fuente = OPTIMIZADOR.read_text(encoding="utf-8")
    codigo = [
        linea for linea in fuente.splitlines() if not linea.strip().startswith("#")
    ]
    assert not [l for l in codigo if "AUC_MINIMO" in l], (
        "el optimizador volvió a rechazar calibraciones por AUC absoluto. Para "
        "metaloenzimas el subconjunto que mide está cerca del azar POR DISEÑO."
    )


def test_el_archivo_de_pesos_declara_que_su_auc_no_incluye_ums():
    """Sin esa nota, un 0.5 se vuelve a leer como calibración inválida."""
    fuente = OPTIMIZADOR.read_text(encoding="utf-8")
    assert "_auc_mide" in fuente, (
        "el optimizador dejó de anotar qué mide `_auc`. Es la línea que evita "
        "que el siguiente lector repita la conclusión equivocada."
    )


# ── El fallo real, todavía abierto ───────────────────────────────────────

def test_las_dos_grafias_reciben_ya_lo_mismo():
    """La otra prueba que anclaba el defecto, y que también debía fallar.

    Su versión previa exigía que `metaloenzyme` y `metalloenzyme` recibieran
    pesos DISTINTOS, porque esa discrepancia ortográfica era lo único que
    impedía que los tres receptores del catálogo cayeran en la política
    genérica `clgnn=1.0`. Estaba escrito así a propósito: normalizar la grafía
    sin ajustar los pesos habría activado el stack equivocado.

    El ADR §6 hace las dos cosas en el mismo cambio: canónica `metalloenzyme`,
    alias de lectura para expedientes antiguos, y la entrada genérica retirada.
    Ahora las dos grafías reciben `default`, que es lo correcto: el score de
    metal no lo calcula este motor.
    """
    from scoring.engine import _get_stacking_weights

    una_ele = _sin_metadatos(_get_stacking_weights("metaloenzyme"))
    dos_eles = _sin_metadatos(_get_stacking_weights("metalloenzyme"))
    por_defecto = _sin_metadatos(_get_stacking_weights(None))

    assert una_ele == dos_eles, "la normalización de grafía dejó de aplicarse"
    assert dos_eles == por_defecto, (
        "una de las grafías volvió a recibir pesos propios en el motor de M4. "
        "El score compuesto de metal lo calcula el perfil M5-Zn."
    )


def test_el_catalogo_escribe_la_grafia_que_no_casa():
    """La premisa de lo anterior, medida sobre el catálogo real."""
    catalogo = json.loads((RAIZ / "curated_targets.json").read_text(encoding="utf-8"))
    if isinstance(catalogo, dict):
        catalogo = catalogo.get("targets", [])

    familias = {(t.get("structural_family") or "").strip().lower() for t in catalogo}
    en_el_json = set(_pesos_guardados())

    metal_en_catalogo = {f for f in familias if "metal" in f}
    metal_en_pesos = {f for f in en_el_json if "metal" in f}

    assert metal_en_catalogo, "el catálogo dejó de tener metaloenzimas"
    assert metal_en_pesos, "el archivo de pesos dejó de tener metaloenzimas"
    if metal_en_catalogo & metal_en_pesos:
        pytest.fail(
            f"las grafías ya coinciden ({metal_en_catalogo & metal_en_pesos}): "
            "M5 se activaría sobre el catálogo. Comprueba w5 antes de dar por "
            "buena esta prueba."
        )


def test_la_puerta_de_ums_declara_la_diferencia_de_w5():
    """0.06 aquí, 0.25-0.40 en el paper. Escrito, no arreglado en silencio."""
    fuente = ENGINE.read_text(encoding="utf-8")
    assert "0.25-0.40" in fuente or "0.25–0.40" in fuente, (
        "desapareció la nota sobre w5. El peso que se aplica a UMS aquí es "
        "0.06 como máximo y encogiendo; el que valida `scripts/bootstrap_ci.py` "
        "es 0.40 (CA2) y 0.25 (MMP9), constante."
    )


def test_ums_solo_se_activa_en_metaloenzimas():
    """El family-gating del paper: cero regresión en las demás familias."""
    from scoring.ums import _is_metalloenzyme_family

    assert _is_metalloenzyme_family("metaloenzyme")
    assert _is_metalloenzyme_family("metalloenzyme")
    for otra in ("gpcr", "kinase", "protease", "nuclear_receptor", None, ""):
        assert not _is_metalloenzyme_family(otra), (
            f"UMS se activaría en «{otra}»: rompe la garantía de cero regresión"
        )


# ── El manifiesto (esto sí quedó bien) ───────────────────────────────────

def test_el_clgnn_actual_no_hereda_metricas_de_otro_checkpoint():
    """Los AUC historicos no se pueden atribuir al SHA-256 que distribuimos."""
    manifiesto = json.loads(
        (RAIZ / "rescoring" / "artifacts" / "model-manifest.json").read_text(encoding="utf-8")
    )
    entrada = manifiesto["models"].get("gnn_v2_cl")
    assert entrada is not None, "el CL-GNN volvio a quedar fuera del manifiesto"
    assert entrada["metrics"]["external_metrics_for_exact_sha256"] is None
    assert entrada["metrics"]["checkpoint_self_reported_val_auc"] == pytest.approx(0.6109756097560977)
    assert "PENDING" in entrada["scientific_status"]
    assert "historical_metrics_not_attributable_to_current_sha256" in entrada


def test_el_manifiesto_liga_las_metricas_a_los_bytes_del_checkpoint():
    """Un AUC sin SHA-256 no dice de qué modelo se está hablando."""
    import hashlib

    manifiesto = json.loads(
        (RAIZ / "rescoring" / "artifacts" / "model-manifest.json").read_text(
            encoding="utf-8"
        )
    )
    entrada = manifiesto["models"]["gnn_v2_cl"]
    checkpoint = RAIZ / "rescoring" / "artifacts" / entrada["file"]
    if not checkpoint.exists():
        # El peso no viaja en el repositorio Git: se descarga aparte bajo
        # LICENSE-MODELS (doc. 78). Su ausencia no es una discrepancia entre
        # checkpoint y manifiesto, que es lo que esta prueba vigila.
        import os

        if os.environ.get("RESCORING_EXIGE_PESOS") == "1":
            raise AssertionError(f"peso exigido y ausente: {checkpoint.name}")
        pytest.skip(
            f"{checkpoint.name} no se distribuye en el repositorio Git; "
            "define RESCORING_EXIGE_PESOS=1 para exigirlo"
        )
    real = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    assert real == entrada["sha256"], (
        f"el checkpoint cambió y el manifiesto no: {checkpoint.name}. "
        "Regenera con rescoring/scripts/generate_model_manifest.py."
    )
