"""El manifiesto de M5-Zn se genera; no se mantiene a mano.

Gates §10.1 y §10.2 de `docs/75_DECISION_CIENTIFICA_M5_ZN_V1.md`.

═══════════════════════════════════════════════════════════════════════════
POR QUÉ UNA SOLA FUENTE
═══════════════════════════════════════════════════════════════════════════

Un manifiesto escrito a mano es una segunda fuente de verdad, y en cuanto hay
dos, divergen. Este proyecto ya tiene el precedente exacto: el §9.1 del ADR
enumera cuatro artefactos —`model-manifest.json`, `stacking_weights.json`, el
manuscrito y `scoring/engine.py`— describiendo cuatro políticas distintas de
metaloenzimas. Nadie lo hizo a propósito: se fueron separando.

Aquí la fuente única es `services/pipeline/protocols/m5/zinc.py` y el JSON es un
derivado determinista. `--check` compara BYTES, así que cambiar un peso sin
regenerar rompe el gate, y regenerar deja el cambio visible en el diff.

Además del contenido, se hashea la tabla de SMARTS de los warheads: el §2 dice
que modificar un patrón crea una versión de protocolo nueva, y sin ese hash
alguien podría afinar un SMARTS mientras el manifiesto sigue diciendo lo mismo.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
MANIFIESTO = (
    RAIZ / "backend" / "services" / "pipeline" / "protocols" / "m5" / "m5_zn_manifest.json"
)
GENERADOR = RAIZ / "scripts" / "generate_m5_manifest.py"


def _generador():
    spec = importlib.util.spec_from_file_location("generar_m5_manifiesto", GENERADOR)
    assert spec and spec.loader
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _manifiesto() -> dict:
    return json.loads(MANIFIESTO.read_text(encoding="utf-8"))


# ── La guardia ───────────────────────────────────────────────────────────

def test_el_manifiesto_commiteado_coincide_con_el_generado():
    """La comprobación que impide que se separen. Compara bytes."""
    modulo = _generador()
    esperado = modulo.serializar(modulo.construir())
    actual = MANIFIESTO.read_text(encoding="utf-8")
    assert actual == esperado, (
        "El manifiesto de M5-Zn no coincide con lo que produce el módulo de "
        "perfiles. Alguien cambió un peso, una constante o un SMARTS sin "
        "regenerar. Ejecuta:\n"
        "    python scripts/generate_m5_manifest.py"
    )


def test_la_generacion_es_determinista():
    """Dos ejecuciones del generador dan los mismos bytes."""
    modulo = _generador()
    assert modulo.serializar(modulo.construir()) == modulo.serializar(modulo.construir())


def test_el_manifiesto_no_se_escribe_a_mano():
    """Declara de dónde sale, para que el siguiente lector no lo edite."""
    d = _manifiesto()
    assert d["generado_por"] == "scripts/generate_m5_manifest.py"
    assert d["fuente_unica"] == "backend/services/pipeline/protocols/m5/zinc.py"


# ── El contenido que exige el §10.2 ──────────────────────────────────────

@pytest.mark.parametrize("pdb", ["3DC3", "1GKC", "1O86"])
def test_cada_perfil_trae_formula_constantes_y_hashes(pdb: str):
    perfil = _manifiesto()["profiles"][pdb]

    assert perfil["formula"], "sin fórmula legible"
    assert perfil["required_components"], "sin componentes obligatorios"
    assert perfil["normalizer"]["vina_reference_max"] > 0
    assert perfil["checkpoint"]["sha256_declarado"], "sin hash del checkpoint"
    assert perfil["reference_auc"]["m5"] > 0


@pytest.mark.parametrize("pdb", ["3DC3", "1GKC", "1O86"])
def test_el_hash_del_checkpoint_es_el_del_archivo(pdb: str):
    """Un AUC de referencia sin hash no dice sobre qué datos se midió.

    Antes se comparaban dos campos DEL MANIFIESTO (`sha256_actual` contra
    `sha256_declarado`), y el primero describía el disco de quien lo generó.
    El manifiesto declaraba así `presente: true` en un artefacto versionado, y
    ningún clon podía reproducirlo. Ahora el manifiesto sólo declara, y la
    comparación se hace contra el archivo real de esta máquina, que es lo que
    la prueba quería decir.
    """
    import hashlib

    perfil = _manifiesto()["profiles"][pdb]
    checkpoint = perfil["checkpoint"]
    ruta = RAIZ / checkpoint["path"]
    if not ruta.is_file():
        pytest.skip(
            f"checkpoint de benchmark no distribuido por el repositorio: "
            f"{checkpoint['path']}"
        )
    real = hashlib.sha256(ruta.read_bytes()).hexdigest()
    assert real == checkpoint["sha256_declarado"], (
        f"{pdb}: el checkpoint cambió y el perfil declara otro hash. Los AUC de "
        "referencia dejarían de corresponder a esos datos."
    )


def test_el_manifiesto_hashea_los_smarts():
    """§2: cambiar un patrón crea versión de protocolo nueva."""
    ums = _manifiesto()["ums"]
    assert ums["variant"] == "smarts_only"
    assert len(ums["warhead_smarts_sha256"]) == 64
    assert len(ums["warhead_keys"]) == 7


def test_cambiar_un_smarts_cambia_el_manifiesto(monkeypatch):
    """La comprobación de que ese hash sirve de algo."""
    from scoring import ums as modulo_ums

    modulo = _generador()
    antes = modulo.construir()["ums"]["warhead_smarts_sha256"]

    alterado = {k: list(v) for k, v in modulo_ums._WARHEAD_SMARTS.items()}
    alterado["thiol"] = ["[SH1]"]  # cambia el patrón
    monkeypatch.setattr(modulo_ums, "_WARHEAD_SMARTS", alterado)

    despues = _generador().construir()["ums"]["warhead_smarts_sha256"]
    assert antes != despues, (
        "cambiar un SMARTS no cambia el hash del manifiesto: el gate no "
        "detectaría una modificación de los patrones"
    )


def test_la_formula_del_ums_esta_escrita_en_el_manifiesto():
    """Para poder leerla sin abrir el código."""
    ums = _manifiesto()["ums"]
    assert "0.85" in ums["formula"] and "0.10" in ums["formula"]
    assert "min(n_warheads / 3, 1)" in ums["formula"]


def test_los_estados_fuera_de_perfil_estan_declarados():
    """§7: los cuatro casos, con `m5_score = null` en todos."""
    fuera = _manifiesto()["fuera_de_perfil"]
    assert fuera["otra_estructura"] == "REVIEW_OUT_OF_VALIDATED_STRUCTURE"
    assert fuera["otra_diana_de_zinc"] == "REVIEW_OUT_OF_VALIDATED_TARGET"
    assert fuera["otro_metal"] == "BLOCKED_PROTOCOL_NOT_AVAILABLE"
    assert fuera["componente_ausente"] == "NOT_EVALUATED_MISSING_COMPONENT"
    assert "null" in fuera["nota"]


# ── Coherencia con el módulo ─────────────────────────────────────────────

@pytest.mark.parametrize("pdb", ["3DC3", "1GKC", "1O86"])
def test_los_pesos_del_manifiesto_son_los_del_modulo(pdb: str):
    from services.pipeline.protocols.m5.zinc import PERFILES

    perfil = PERFILES[pdb]
    pesos = _manifiesto()["profiles"][pdb]["weights"]
    assert pesos["vina_norm"] == perfil.peso_vina
    assert pesos["xgboost"] == perfil.peso_xgb
    assert pesos["gnn_d"] == perfil.peso_gnn_d
    assert pesos["ums_warhead"] == perfil.peso_ums


def test_el_verificador_del_bundle_comprueba_la_copia_embebida():
    """Gate §10.8: el runtime empaquetado usa el mismo manifiesto."""
    fuente = (RAIZ / "scripts" / "verify_desktop_bundle.py").read_text(encoding="utf-8")
    assert "validate_m5_manifest" in fuente, (
        "el verificador del bundle dejó de comprobar el manifiesto de M5-Zn: "
        "el producto instalado podría puntuar con otros pesos"
    )
    assert "read_bytes() != copia.read_bytes()" in fuente, (
        "la comparación dejó de ser byte a byte"
    )
