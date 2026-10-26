"""
Configuración efectiva del protocolo de docking: UNA resolución (SOL-02).

El hallazgo que motiva este archivo (auditoría DevOps SOL, 2026-09-30):

- El preflight declaraba `effective_config.seed = settings.vina_seed` (42)
  SIEMPRE, mientras el runner ejecutaba la semilla anidada de
  `pipeline_config.stage_params.docking.seed` (123 en la reproducción de la
  auditoría, con `vina_random_seed=123` registrado en el resultado).
- El documento canónico del fingerprint se firmaba con los campos de nivel
  superior del request, pero la revalidación del submit los derivaba de los
  anidados: la MISMA configuración producía dos huellas distintas y un 409
  espurio («La hipótesis o la preparación cambió») sin que nada cambiara.
- El runner mantenía además tres defaults incoherentes para el mismo
  parámetro: literales 32/8/42, registry 32/9 y settings 8/5/42.

La regla que este archivo protege:

    LO DECLARADO = LO EJECUTADO = LO SELLADO

preflight, fingerprint, revalidación de submit y runner consumen la MISMA
resolución (`services.docking.protocolo.resolver_parametros_docking`):
`stage_params` anidado gobierna, `settings` es el respaldo. Los campos de
nivel superior del request del preflight son espejos de la UI y NO participan
en la resolución: ninguna puerta de ejecución (`/submit`, `/evaluate`) los
lleva, así que honrarlos declararía una corrida que ningún submit puede
ejecutar. Si contradicen lo que se ejecutará, el informe lo declara como
control explícito — no lo ejecuta en silencio.

La semilla canónica de MolDesign es y sigue siendo 42 (`settings.vina_seed`):
sin semilla explícita, preflight declara 42, el fingerprint firma 42 y el
runner ejecuta 42. El 123 de la auditoría era sólo el caso sintético para
verificar la trazabilidad.
"""

from __future__ import annotations

import json
from pathlib import Path

from tests.conftest import rdkit_available

from services.docking import preflight as pf
from services.docking.protocolo import resolver_parametros_docking

RAIZ = Path(__file__).resolve().parents[1]

ASPIRIN = "CC(=O)Oc1ccccc1C(=O)O"

ETAPAS = ["validation", "properties", "sa_filter", "conformer", "docking", "xgb", "clgnn"]


def _config(**anidados: dict) -> dict:
    """pipeline_config válido con sólo los stage_params que el test declare."""
    return {
        "enabled_stages": ETAPAS,
        "docking_engine": "vina",
        "stage_params": dict(anidados),
    }


def _build(**overrides):
    """Informe con los argumentos mínimos; cada test cambia lo suyo.

    Igual que `test_evaluation_preflight._build`: `1ABC` no existe en disco,
    así que el informe trae bloqueantes de receptor, pero effective_config y
    fingerprint se calculan igual — que es justo lo que se prueba aquí.
    """
    kwargs = dict(
        smiles=ASPIRIN,
        target_pdb_id="1ABC",
        chain="A",
        target_origin="curado",
        target_reference="ref-1",
        grid_center=(1.0, 2.0, 3.0),
        grid_size=(20.0, 20.0, 20.0),
        custom_hotspots=None,
        catalog_grid_center=None,
        catalog_grid_size=None,
        catalog_hotspots=None,
        cofactors_whitelist=None,
        docking_engine="vina",
    )
    kwargs.update(overrides)
    return pf.build_preflight(**kwargs)


def _control(report: dict, code: str) -> dict:
    for control in report["controls"]:
        if control["code"] == code:
            return control
    raise AssertionError(
        f"El informe no incluye el control {code}: {[c['code'] for c in report['controls']]}"
    )


# ── 1. El resolutor: la cadena anidado ?? settings ────────────────────


def test_la_semilla_anidada_gobierna_la_resolucion():
    resuelto = resolver_parametros_docking(
        pipeline_config=_config(docking={"seed": 123}),
        size=(20.0, 20.0, 20.0),
    )
    assert resuelto["seed"] == 123


def test_el_canon_de_semilla_es_cuarenta_y_dos():
    """Sin semilla explícita, la resuelta es la canónica de settings (42)."""
    from core.config import get_settings

    resuelto = resolver_parametros_docking(pipeline_config=None, size=(20.0, 20.0, 20.0))
    assert resuelto["seed"] == get_settings().vina_seed
    # El canon declarado del producto: si esto cambia, cambia la identidad de
    # TODAS las corridas ordinarias y hay que decirlo en el dossier.
    assert resuelto["seed"] == 42


def test_la_exhaustividad_explicita_respeta_el_valor_sin_ajuste_de_politica():
    """La política de volumen eleva el default, nunca lo que se pidió."""
    resuelto = resolver_parametros_docking(
        pipeline_config=_config(docking={"exhaustiveness": 16}),
        size=(40.0, 40.0, 40.0),  # caja grande: la política sólo aplicaría al default
    )
    assert resuelto["exhaustiveness"] == 16


def test_el_default_de_exhaustividad_sigue_la_politica_de_volumen():
    from core.config import get_settings

    caja_chica = resolver_parametros_docking(pipeline_config=None, size=(20.0, 20.0, 20.0))
    assert caja_chica["exhaustiveness"] == get_settings().vina_exhaustiveness

    caja_grande = resolver_parametros_docking(pipeline_config=None, size=(31.0, 31.0, 31.0))
    assert caja_grande["exhaustiveness"] == 32  # LARGE_BOX_DEFAULT_EXHAUSTIVENESS


def test_poses_y_conformers_anidados_gobiernan():
    resuelto = resolver_parametros_docking(
        pipeline_config=_config(docking={"num_poses": 9}, conformer={"conformers": 30}),
        size=(20.0, 20.0, 20.0),
    )
    assert resuelto["num_poses"] == 9
    assert resuelto["conformers"] == 30

    por_defecto = resolver_parametros_docking(pipeline_config=None, size=(20.0, 20.0, 20.0))
    assert por_defecto["conformers"] == 1


def test_el_conflicto_con_el_nivel_superior_se_declara_no_se_ejecuta():
    """Los espejos de la UI contradicen lo ejecutable: vuelven en `conflictos`."""
    resuelto = resolver_parametros_docking(
        pipeline_config=_config(docking={"exhaustiveness": 32, "num_poses": 1}),
        size=(20.0, 20.0, 20.0),
        exhaustiveness_declarada=8,
        num_poses_declarado=9,
        conformers_declarado=1,
    )
    campos = {c["campo"]: c for c in resuelto["conflictos"]}
    assert set(campos) == {"exhaustiveness", "num_poses"}
    assert campos["exhaustiveness"]["declarado"] == 8
    assert campos["exhaustiveness"]["efectivo"] == 32


def test_el_nivel_superior_coincidente_no_es_conflicto():
    resuelto = resolver_parametros_docking(
        pipeline_config=_config(docking={"exhaustiveness": 8, "num_poses": 9}),
        size=(20.0, 20.0, 20.0),
        exhaustiveness_declarada=8,
        num_poses_declarado=9,
    )
    assert resuelto["conflictos"] == []


def test_conformers_imposibles_caen_al_defecto_no_revientan():
    """K anidado imposible no tumba la resolución: normalizar_k lo declara."""
    resuelto = resolver_parametros_docking(
        pipeline_config=_config(conformer={"conformers": 0}),
        size=(20.0, 20.0, 20.0),
    )
    assert resuelto["conformers"] == 1


# ── 2. El preflight declara lo que el runner ejecutará ───────────────


@rdkit_available
def test_el_preflight_declara_la_semilla_que_ejecutara():
    """SOL-02, reproducción literal: semilla anidada 123, informe dice 123.

    Antes declaraba 42 (settings) aunque la corrida ejecutara 123: la
    preparación que el investigador aprueba no describía el protocolo.
    """
    report = _build(pipeline_config=_config(docking={"seed": 123}))
    assert report["effective_config"]["seed"] == 123


@rdkit_available
def test_el_canon_de_semilla_en_el_flujo_ordinario():
    """El caso ordinario de la UI (sin semilla anidada) sigue declarando 42."""
    report = _build()
    assert report["effective_config"]["seed"] == 42


@rdkit_available
def test_el_documento_canonico_firma_la_semilla_resuelta():
    """La huella firma lo que se ejecutará, no lo que settings tiene por defecto."""
    report = _build(pipeline_config=_config(docking={"seed": 123}))
    document = json.loads(report["input_document"])
    assert document["seed"] == 123


@rdkit_available
def test_el_fingerprint_no_depende_de_los_campos_de_nivel_superior():
    """La propiedad que mata el 409 espurio.

    La revalidación del submit construye su comprobación fresca derivando los
    campos de nivel superior de los anidados (no puede hacer otra cosa: el
    submit no los lleva). Si el documento dependiera de los espejos, dos
    llamadas con el MISMO pipeline_config firmarían huellas distintas y el
    submit rechazaría con 409 una configuración que nadie cambió.

    Reproduce la sonda de la auditoría: nivel superior 8/9/30 contra anidados
    32/1.
    """
    config = _config(docking={"exhaustiveness": 32, "num_poses": 1},
                     conformer={"conformers": 1})
    con_espejos = _build(
        exhaustiveness=8, num_poses=9, conformers=30, pipeline_config=config
    )["input_fingerprint"]
    sin_espejos = _build(pipeline_config=config)["input_fingerprint"]
    assert con_espejos == sin_espejos


@rdkit_available
def test_el_conflicto_de_nivel_superior_es_un_control_del_informe():
    config = _config(docking={"exhaustiveness": 32})
    report = _build(exhaustiveness=8, num_poses=9, pipeline_config=config)

    control = _control(report, "PROTOCOLO_DECLARADO_CONFLICTIVO")
    assert control["state"] == "advertencia"
    # El control NOMBRa ambos valores: «hay un problema» no sirve para decidir.
    assert "8" in control["observation"]
    assert "32" in control["observation"]
    # El conflicto no bloquea ni cambia lo efectivo: informa, el documento firma.
    assert report["effective_config"]["exhaustiveness"] == 32
    assert control["code"] not in report["technical_blockers"]


@rdkit_available
def test_sin_conflicto_no_hay_control_de_ruido():
    config = _config(docking={"exhaustiveness": 8, "num_poses": 9})
    report = _build(exhaustiveness=8, num_poses=9, pipeline_config=config)
    assert all(
        c["code"] != "PROTOCOLO_DECLARADO_CONFLICTIVO" for c in report["controls"]
    )


@rdkit_available
def test_los_conformers_anidados_gobiernan_la_configuracion_efectiva():
    """La otra cara de CAS-05: declarar K=30 arriba no puede fingir un ensemble
    que la ejecución haría con K=1 anidado."""
    config = _config(conformer={"conformers": 1})
    report = _build(conformers=30, pipeline_config=config)
    assert report["effective_config"]["conformers"] == 1

    documento = json.loads(report["input_document"])
    assert "conformers" not in documento  # K=1 no entra: la huella histórica no cambia


@rdkit_available
def test_el_ensemble_declarado_en_el_lugar_correcto_se_conserva():
    config = _config(conformer={"conformers": 30})
    report = _build(conformers=30, pipeline_config=config)
    assert report["effective_config"]["conformers"] == 30
    assert json.loads(report["input_document"])["conformers"] == 30


# ── 3. El runner ejecuta lo mismo que se declaró ─────────────────────


def test_el_runner_resuelve_el_protocolo_con_el_resolutor_unico():
    """El docking del runner consume `resolver_parametros_docking`.

    Los literales `32/8/42` eran una segunda fuente de verdad con OTROS
    valores que settings (8/5/42) y que el registry (32/9): declaraban una
    corrida distinta de la que el preflight había firmado. Source-text,
    el mismo enfoque que `test_los_dos_caminos_sellan_el_protocolo`.
    """
    fuente = (RAIZ / "services" / "pipeline" / "runner.py").read_text(encoding="utf-8")
    assert "resolver_parametros_docking(" in fuente
    assert 'params.get("exhaustiveness", 32)' not in fuente
    assert 'params.get("num_poses", 8)' not in fuente
    assert 'params.get("seed", 42)' not in fuente


def test_el_registry_no_declara_un_segundo_defecto_de_protocolo():
    """Los `params` del registry son eco del defecto de settings, no una
    tercera fuente: 32/9 contradecía los 8/5 que settings declara."""
    from core.config import get_settings
    from services.pipeline.registry import STAGE_REGISTRY

    settings = get_settings()
    assert STAGE_REGISTRY["docking"].params == {
        "exhaustiveness": int(settings.vina_exhaustiveness),
        "num_poses": int(settings.vina_num_poses),
    }
