"""
Contrato de la comprobación previa (`/evaluation/preflight`).

Lo que estas pruebas protegen, en orden de gravedad:

1. **El preflight no ejecuta la corrida.** Si algún día alguien conecta aquí el
   docking, el rescoring o MM-GBSA, la comprobación «previa» pasaría a costar
   minutos y a consumir el presupuesto que venía a ahorrar.
2. **Nada se declara `pasa` sin haberse comprobado.** Un artefacto ausente
   produce `no_evaluado` o `bloquea`; nunca un visto bueno.
3. **El fingerprint identifica la corrida.** Si cambia cualquier entrada que
   pueda alterar el resultado, cambia; si no cambia nada, no cambia. Es lo
   único que permite afirmar que la corrida lanzada es la que se inspeccionó.
4. **El diff sale de la ruta real**, no de una lista teórica.
5. **No se filtran rutas absolutas** del disco del usuario.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.conftest import rdkit_available

from services.docking import preflight as pf


# ── Datos de prueba ──────────────────────────────────────────────────

ASPIRIN = "CC(=O)Oc1ccccc1C(=O)O"

#: PDB mínimo con lo justo para ejercitar la clasificación: dos cadenas,
#: aguas, un metal, un cofactor de la lista del producto y un ligando ajeno.
MINIMAL_PDB = """\
ATOM      1  N   ALA A   1      11.104  13.207  10.000  1.00 20.00           N
ATOM      2  CA  ALA A   1      12.560  13.207  10.000  1.00 20.00           C
ATOM      3  C   ALA A   1      13.100  14.600  10.000  1.00 20.00           C
ATOM      4  O   ALA A   1      12.400  15.600  10.000  1.00 20.00           O
ATOM      5  N   GLY A   2      14.400  14.700  10.000  1.00 20.00           N
ATOM      6  CA  GLY A   2      15.100  15.900  10.000  1.00 20.00           C
ATOM      7  N   SER B   1      30.000  30.000  30.000  1.00 20.00           N
ATOM      8  CA  SER B   1      31.000  31.000  31.000  1.00 20.00           C
HETATM    9  ZN   ZN A 101      13.000  14.000  11.000  1.00 20.00          ZN
HETATM   10  O   HOH A 201      16.000  16.000  16.000  1.00 20.00           O
HETATM   11  O   HOH A 202      17.000  17.000  17.000  1.00 20.00           O
HETATM   12  C1  NAD A 301      14.000  14.000  12.000  1.00 20.00           C
HETATM   13  C1  LIG A 401      15.000  15.000  13.000  1.00 20.00           C
END
"""


def _build(**overrides):
    """Informe con los argumentos mínimos; cada test cambia lo suyo."""
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
    raise AssertionError(f"El informe no incluye el control {code}: {[c['code'] for c in report['controls']]}")


# ── 1. No ejecuta la corrida ─────────────────────────────────────────


@rdkit_available
def test_preflight_never_runs_docking_or_expensive_models(monkeypatch):
    """
    El presupuesto entero del preflight: cero subprocesos, cero modelos.

    Se sabotean las entradas reales al trabajo caro. Si el informe se genera
    igual, es que ninguna de ellas se tocó.
    """
    import asyncio
    import subprocess

    def _explode(*args, **kwargs):  # pragma: no cover - sólo si hay regresión
        raise AssertionError("el preflight intentó lanzar un proceso externo")

    monkeypatch.setattr(subprocess, "run", _explode)
    monkeypatch.setattr(subprocess, "Popen", _explode)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", _explode)

    report = _build()

    assert report["schema_version"] == pf.PREFLIGHT_SCHEMA_VERSION
    assert report["execution_route"] == "docking_vina"


@rdkit_available
def test_preflight_does_not_download_the_receptor(monkeypatch, tmp_path):
    """
    Sin fuente en disco no se va a la red: se bloquea hasta poder sellarla.

    Un preflight que descarga deja de ser barato y deja de funcionar sin
    conexión, justo cuando el usuario más necesita saber qué le falta.
    """
    import utils.file_handlers as file_handlers

    async def _explode(*args, **kwargs):  # pragma: no cover
        raise AssertionError("el preflight intentó descargar del RCSB")

    monkeypatch.setattr(file_handlers, "download_pdb_from_rcsb", _explode)
    monkeypatch.setattr(pf, "_source_pdb_path", lambda pdb_id: None)
    monkeypatch.setattr(pf, "_prepared_pdbqt_path", lambda pdb_id: None)

    report = _build()

    fuente = _control(report, "RECEPTOR_FUENTE_DISPONIBLE")
    assert fuente["state"] == "bloquea"
    assert "no se pudo sellar" in fuente["observation"]


# ── 2. Nada pasa sin comprobarse ─────────────────────────────────────


@rdkit_available
def test_missing_artifacts_are_never_reported_as_passing(monkeypatch):
    monkeypatch.setattr(pf, "_source_pdb_path", lambda pdb_id: None)
    monkeypatch.setattr(pf, "_prepared_pdbqt_path", lambda pdb_id: None)

    report = _build()

    assert _control(report, "RECEPTOR_FUENTE_DISPONIBLE")["state"] == "bloquea"
    for code in (
        "RECEPTOR_PREPARADO_DISPONIBLE",
        "RECEPTOR_CADENA_PRESENTE",
        "ESPECIES_DEL_SITIO_RETIRADAS",
    ):
        assert _control(report, code)["state"] == "no_evaluado", code

    assert report["preparation_diff"]["state"] == "no_evaluado"
    assert report["preparation_diff"]["reason"]


@rdkit_available
def test_every_control_declares_one_of_the_four_states():
    report = _build()
    allowed = {"pasa", "advertencia", "bloquea", "no_evaluado"}
    for control in report["controls"]:
        assert control["state"] in allowed, control
        # Ningún control puede presentarse sin decir en qué se apoya.
        assert control["observation"].strip()
        assert control["reason"].strip()
        assert control["provenance"].strip()


@rdkit_available
def test_report_carries_no_composite_score():
    """No hay nota 0-100 ni veredicto: sólo estados y hechos."""
    report = _build()
    flat = json.dumps(report, ensure_ascii=False).lower()
    for forbidden in ("score_total", "overall_score", "probabilidad", "puntuacion"):
        assert forbidden not in flat


# ── 3. Fingerprint ───────────────────────────────────────────────────


@rdkit_available
def test_fingerprint_is_deterministic():
    first = _build()["input_fingerprint"]
    second = _build()["input_fingerprint"]
    assert first == second
    assert first.startswith("sha256:")


@rdkit_available
def test_fingerprint_changes_when_pipeline_configuration_changes():
    """El protocolo PRO también forma parte de la identidad de la corrida."""
    base = _build(
        pipeline_config={
            "enabled_stages": ["validation", "docking"],
            "stage_params": {"docking": {"exhaustiveness": 8}},
            "docking_engine": "vina",
        }
    )["input_fingerprint"]
    changed = _build(
        pipeline_config={
            "enabled_stages": ["validation", "docking"],
            "stage_params": {"docking": {"exhaustiveness": 16}},
            "docking_engine": "vina",
        }
    )["input_fingerprint"]

    assert changed != base


@rdkit_available
@pytest.mark.parametrize(
    "override",
    [
        {"smiles": "CCO"},
        {"target_pdb_id": "2XYZ"},
        {"chain": "B"},
        {"grid_center": (9.0, 9.0, 9.0)},
        {"grid_size": (30.0, 30.0, 30.0)},
        {"custom_hotspots": ["TYR123"]},
        {"docking_engine": "qvina2"},
        {"exhaustiveness": 16},
        {"num_poses": 12},
    ],
)
def test_fingerprint_changes_when_the_run_would_change(override):
    base = _build()["input_fingerprint"]
    assert _build(**override)["input_fingerprint"] != base, override


@rdkit_available
def test_fingerprint_ignores_what_cannot_change_the_run():
    """
    El orden de los hotspots y la forma del SMILES no cambian la corrida.

    Sin esta normalización el botón de ejecutar se bloquearía solo al
    reordenar una lista o al escribir la misma molécula de otra manera.
    """
    a = _build(custom_hotspots=["TYR123", "ASP45"])["input_fingerprint"]
    b = _build(custom_hotspots=["ASP45", "TYR123"])["input_fingerprint"]
    assert a == b

    # Dos escrituras de la misma aspirina: mismo canónico, misma corrida.
    assert (
        _build(smiles="CC(=O)Oc1ccccc1C(=O)O")["input_fingerprint"]
        == _build(smiles="O=C(C)Oc1ccccc1C(=O)O")["input_fingerprint"]
    )


@rdkit_available
def test_fingerprint_tolerates_float_noise():
    """22.5 y 22.500000000000004 son la misma caja."""
    a = _build(grid_size=(22.5, 22.5, 22.5))["input_fingerprint"]
    b = _build(grid_size=(22.500000000000004, 22.5, 22.5))["input_fingerprint"]
    assert a == b


@rdkit_available
def test_fingerprint_document_has_no_timestamp():
    document = json.loads(_build()["input_document"])
    assert "generated_at" not in document
    assert set(document) == {
        "schema",
        "route",
        "smiles",
        "target_pdb_id",
        "chain",
        "grid_center",
        "grid_size",
        "custom_hotspots",
        "docking_engine",
        "exhaustiveness",
        "num_poses",
        "seed",
        "source_sha256",
        "prepared_sha256",
    }


# ── 4. Ligando ───────────────────────────────────────────────────────


@rdkit_available
def test_invalid_smiles_produces_an_explicit_blocker():
    report = _build(smiles="C1CC")  # anillo sin cerrar

    control = _control(report, "LIGANDO_SMILES_VALIDO")
    assert control["state"] == "bloquea"
    assert "LIGANDO_SMILES_VALIDO" in report["technical_blockers"]
    assert report["ligand"]["canonical_smiles"] is None
    assert report["ligand"]["error"]
    # Y no se finge que los átomos se comprobaron.
    assert _control(report, "LIGANDO_ATOMOS_VINA")["state"] == "no_evaluado"


@rdkit_available
def test_unsupported_atom_produces_a_technical_control():
    """
    Ferroceno-like: hierro en la molécula. Vina no tiene parámetros para él.

    En `strict_science_mode` el validador de producción lo convierte en error,
    así que el control bloquea; con el modo relajado, advierte. Las dos
    lecturas son correctas — lo que no puede pasar es que no diga nada.
    """
    report = _build(smiles="CC(=O)Oc1ccccc1C(=O)[Fe]")
    control = _control(report, "LIGANDO_ATOMOS_VINA")
    assert control["state"] in {"bloquea", "advertencia"}
    # El elemento se NOMBRA. Un control que dijera sólo «hay un problema» no
    # sirve para decidir nada.
    assert "Fe" in control["observation"]
    assert "Fe" in report["ligand"]["vina_atom_compatibility"]["unsupported_elements"]
    # Y jamás sale como `no_evaluado`: se miró y se encontró.
    assert control["state"] != "no_evaluado"


@rdkit_available
def test_valid_ligand_reports_its_canonical_form():
    report = _build(smiles="O=C(C)Oc1ccccc1C(=O)O")
    assert report["ligand"]["canonical_smiles"] == "CC(=O)Oc1ccccc1C(=O)O"
    assert report["ligand"]["smiles_hash"]
    assert _control(report, "LIGANDO_SMILES_VALIDO")["state"] == "pasa"


# ── 5. Diff y política, desde la ruta real ───────────────────────────


@rdkit_available
def test_diff_comes_from_the_real_filter(monkeypatch, tmp_path):
    """
    El diff se calcula llamando a la función que ejecuta la corrida.

    Se comprueba contra recuentos conocidos del PDB de prueba: 2 aguas, 1
    metal, 1 cofactor de la lista y 1 ligando ajeno, todos en la cadena A.
    """
    source = tmp_path / "1ABC.pdb"
    source.write_text(MINIMAL_PDB, encoding="utf-8")
    monkeypatch.setattr(pf, "_source_pdb_path", lambda pdb_id: source)
    monkeypatch.setattr(pf, "_prepared_pdbqt_path", lambda pdb_id: None)

    report = _build()
    diff = report["preparation_diff"]

    assert diff["state"] == "evaluado"
    assert diff["source"]["waters"] == 2
    assert diff["source"]["metals"] == 1
    assert diff["source"]["organic_cofactors"] == 1
    assert diff["source"]["other_hetatm"] == 1
    assert sorted(diff["source"]["chains"]) == ["A", "B"]

    # La ruta de docking: aguas fuera, metal fuera, cofactor de la lista dentro.
    assert diff["removed"]["waters"] == 2
    assert diff["removed"]["metals"] == 1
    assert diff["removed"]["other_hetatm"] == 1
    assert {item["residue_code"] for item in diff["removed_species"]} == {"HOH", "LIG", "ZN"}
    assert next(item for item in diff["removed_species"] if item["residue_code"] == "ZN") == {
        "residue_code": "ZN",
        "atom_count": 1,
        "category": "metal",
    }
    assert diff["preserved"]["organic_cofactors"] == 1
    # Y la cadena B no entra.
    assert diff["route_input"]["chains"] == ["A"]


@rdkit_available
def test_removed_metals_raise_a_warning_not_a_block(monkeypatch, tmp_path):
    source = tmp_path / "1ABC.pdb"
    source.write_text(MINIMAL_PDB, encoding="utf-8")
    monkeypatch.setattr(pf, "_source_pdb_path", lambda pdb_id: source)
    monkeypatch.setattr(pf, "_prepared_pdbqt_path", lambda pdb_id: None)

    report = _build()

    metales = _control(report, "METALES_ELIMINADOS")
    assert metales["state"] == "advertencia"
    assert "ZN (1 átomo)" in metales["observation"]
    assert "METAL_COFACTORS" not in metales["provenance"]
    assert "METALES_ELIMINADOS" not in report["technical_blockers"]
    assert "METALES_ELIMINADOS" in report["warnings"]


@rdkit_available
def test_policy_declares_that_the_whitelist_reaches_the_docking_route(monkeypatch, tmp_path):
    """
    La selección explícita se aplica al mismo filtro que usará la corrida.
    """
    source = tmp_path / "1ABC.pdb"
    source.write_text(MINIMAL_PDB, encoding="utf-8")
    monkeypatch.setattr(pf, "_source_pdb_path", lambda pdb_id: source)
    monkeypatch.setattr(pf, "_prepared_pdbqt_path", lambda pdb_id: None)

    report = _build(cofactors_whitelist=["ZN"])

    policy = report["effective_config"]["heteroatom_policy"]
    assert policy["cofactors_whitelist_declared"] == ["ZN"]
    assert policy["cofactors_whitelist_applied"] is True
    control = _control(report, "POLITICA_HETEROATOMOS")
    assert control["state"] == "pasa"
    assert "aplicará" in control["observation"]
    assert report["preparation_diff"]["removed"]["metals"] == 0


@rdkit_available
def test_a_chain_that_leaves_no_atoms_blocks_before_wasting_the_run(monkeypatch, tmp_path):
    source = tmp_path / "1ABC.pdb"
    source.write_text(MINIMAL_PDB, encoding="utf-8")
    monkeypatch.setattr(pf, "_source_pdb_path", lambda pdb_id: source)
    monkeypatch.setattr(pf, "_prepared_pdbqt_path", lambda pdb_id: None)

    report = _build(chain="Z")

    control = _control(report, "RECEPTOR_CADENA_PRESENTE")
    assert control["state"] == "bloquea"
    assert "RECEPTOR_CADENA_PRESENTE" in report["technical_blockers"]


# ── 6. Hashes sobre archivos reales ──────────────────────────────────


@rdkit_available
def test_hashes_are_computed_over_the_real_files(monkeypatch, tmp_path):
    import hashlib

    source = tmp_path / "1ABC.pdb"
    source.write_text(MINIMAL_PDB, encoding="utf-8")
    prepared = tmp_path / "prepared.pdbqt"
    prepared.write_text("ATOM      1  N   ALA A   1       0.0   0.0   0.0  1.00  0.00     0.000 N\n", encoding="utf-8")

    monkeypatch.setattr(pf, "_source_pdb_path", lambda pdb_id: source)
    monkeypatch.setattr(pf, "_prepared_pdbqt_path", lambda pdb_id: prepared)

    report = _build()

    expected_source = "sha256:" + hashlib.sha256(source.read_bytes()).hexdigest()
    expected_prepared = "sha256:" + hashlib.sha256(prepared.read_bytes()).hexdigest()
    assert report["receptor"]["source_sha256"] == expected_source
    assert report["receptor"]["prepared_sha256"] == expected_prepared
    assert _control(report, "RECEPTOR_PREPARADO_DISPONIBLE")["state"] == "pasa"


@rdkit_available
def test_fingerprint_changes_when_the_source_artifact_changes(monkeypatch, tmp_path):
    source = tmp_path / "1ABC.pdb"
    source.write_text(MINIMAL_PDB, encoding="utf-8")
    monkeypatch.setattr(pf, "_source_pdb_path", lambda pdb_id: source)
    monkeypatch.setattr(pf, "_prepared_pdbqt_path", lambda pdb_id: None)

    first = _build()["input_fingerprint"]
    source.write_text(MINIMAL_PDB.replace("20.00", "21.00", 1), encoding="utf-8")
    second = _build()["input_fingerprint"]

    assert first != second


@rdkit_available
def test_prepared_receptor_absent_is_not_evaluated(monkeypatch, tmp_path):
    source = tmp_path / "1ABC.pdb"
    source.write_text(MINIMAL_PDB, encoding="utf-8")
    monkeypatch.setattr(pf, "_source_pdb_path", lambda pdb_id: source)
    monkeypatch.setattr(pf, "_prepared_pdbqt_path", lambda pdb_id: None)

    report = _build()

    assert report["receptor"]["prepared_sha256"] is None
    assert _control(report, "RECEPTOR_PREPARADO_DISPONIBLE")["state"] == "no_evaluado"


@rdkit_available
def test_prepared_receptor_for_another_chain_is_not_reused_or_hashed_as_input(monkeypatch, tmp_path):
    source = tmp_path / "1ABC.pdb"
    source.write_text(MINIMAL_PDB, encoding="utf-8")
    prepared = tmp_path / "prepared.pdbqt"
    prepared.write_text(
        "ATOM      1  N   ALA B   1       0.0   0.0   0.0  1.00  0.00     0.000 N\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(pf, "_source_pdb_path", lambda pdb_id: source)
    monkeypatch.setattr(pf, "_prepared_pdbqt_path", lambda pdb_id: prepared)

    report = _build(chain="A")

    assert report["receptor"]["prepared_compatible"] is False
    assert report["receptor"]["prepared_chains"] == ["B"]
    assert _control(report, "RECEPTOR_PREPARADO_OBSOLETO")["state"] == "advertencia"
    assert json.loads(report["input_document"])["prepared_sha256"] is None


# ── 7. Sin rutas absolutas ───────────────────────────────────────────


@rdkit_available
def test_no_absolute_paths_leak_into_the_response(monkeypatch, tmp_path):
    source = tmp_path / "1ABC.pdb"
    source.write_text(MINIMAL_PDB, encoding="utf-8")
    prepared = tmp_path / "prepared.pdbqt"
    prepared.write_text("ATOM\n", encoding="utf-8")
    monkeypatch.setattr(pf, "_source_pdb_path", lambda pdb_id: source)
    monkeypatch.setattr(pf, "_prepared_pdbqt_path", lambda pdb_id: prepared)

    import re

    payload = json.dumps(_build(), ensure_ascii=False)

    assert str(tmp_path) not in payload
    assert str(Path.home()) not in payload
    assert source.name in payload  # el NOMBRE del archivo sí es procedencia útil
    # Ninguna ruta absoluta: ni unidad de Windows (`C:\`) ni raíz POSIX.
    assert re.search(r"[A-Za-z]:[\/]", payload) is None, payload[:400]
    assert re.search(r'"(/[A-Za-z]|\\)', payload) is None


# ── 8. Configuración efectiva ────────────────────────────────────────


@rdkit_available
def test_user_override_wins_over_the_catalog_grid():
    report = _build(
        grid_center=(1.0, 2.0, 3.0),
        catalog_grid_center=(9.0, 9.0, 9.0),
    )
    assert report["effective_config"]["grid_center"] == [1.0, 2.0, 3.0]
    assert report["effective_config"]["grid_center_origin"] == "override_usuario"


@rdkit_available
def test_catalog_grid_is_used_when_there_is_no_override():
    report = _build(grid_center=None, grid_size=None, catalog_grid_center=(5.0, 6.0, 7.0), catalog_grid_size=(18.0, 18.0, 18.0))
    assert report["effective_config"]["grid_center"] == [5.0, 6.0, 7.0]
    assert report["effective_config"]["grid_center_origin"] == "catalogo_target"
    assert _control(report, "GRID_EFECTIVO")["state"] == "pasa"


@rdkit_available
def test_a_zero_center_declares_the_box_the_run_will_derive(monkeypatch, tmp_path):
    """
    La interfaz envía (0,0,0) mientras nadie abra «Opciones», y la corrida
    sustituye ese centro por uno derivado del PDB. El preflight enseña el
    derivado: si no, mostraría una caja que no se va a usar.
    """
    source = tmp_path / "1ABC.pdb"
    source.write_text(MINIMAL_PDB, encoding="utf-8")
    monkeypatch.setattr(pf, "_source_pdb_path", lambda pdb_id: source)
    monkeypatch.setattr(pf, "_prepared_pdbqt_path", lambda pdb_id: None)

    report = _build(grid_center=(0.0, 0.0, 0.0))
    effective = report["effective_config"]

    control = _control(report, "GRID_EFECTIVO")
    if effective["grid_center_origin"] == "derivado_dinamico":
        assert effective["grid_center"] != [0.0, 0.0, 0.0]
        assert effective["derived_box"] is not None
        assert control["state"] == "advertencia"
    else:
        # Si no se pudo derivar, se dice — nunca se presenta (0,0,0) como una
        # caja válida.
        assert control["state"] == "bloquea"


@rdkit_available
def test_unsupported_docking_route_blocks_instead_of_borrowing_vina_controls():
    report = _build(docking_engine="diffdock")
    assert _control(report, "RUTA_PREFLIGHT_SOPORTADA")["state"] == "bloquea"
    assert "RUTA_PREFLIGHT_SOPORTADA" in report["technical_blockers"]


@rdkit_available
def test_missing_hotspots_are_not_evaluated_rather_than_passing():
    report = _build(catalog_hotspots=[])
    assert _control(report, "HOTSPOTS_EFECTIVOS")["state"] == "no_evaluado"


# ── 9. Deudas declaradas ─────────────────────────────────────────────


@rdkit_available
def test_known_debts_are_declared_not_hidden():
    report = _build()
    for code in ("LIGANDO_PROTONACION_TAUTOMERO", "ASSEMBLY_BIOLOGICA", "HUECOS_CERCA_DEL_SITIO"):
        control = _control(report, code)
        assert control["state"] == "no_evaluado"
        assert code in report["not_evaluated"]
        assert "deuda declarada" in control["provenance"]


# ── 10. Clasificación de especies con las listas vivas ───────────────


def test_species_counter_uses_the_live_product_lists():
    counts = pf.count_species(MINIMAL_PDB)
    assert counts.atom_records == 8
    assert counts.waters == 2
    assert counts.metals == 1
    assert counts.organic_cofactors == 1
    assert counts.other_hetatm == 1
    assert counts.chains == {"A", "B"}


def test_organic_cofactor_list_is_derived_from_the_preparer():
    """
    Si alguien añade un cofactor al filtro real, el recuento lo sigue.

    Es la garantía de que el preflight no describe una política distinta de la
    que ejecuta (docs/53 §6.2).
    """
    from services.docking import preparer

    assert "NAD" in preparer.ORGANIC_COFACTORS_KEPT
    assert "ALA" not in preparer.ORGANIC_COFACTORS_KEPT
    assert "MSE" not in preparer.ORGANIC_COFACTORS_KEPT
    assert preparer.ORGANIC_COFACTORS_KEPT <= preparer.STANDARD_RESIDUES


# ── 11. Hotspots que no están en el receptor ─────────────────────────


@rdkit_available
def test_hotspots_on_a_chain_that_is_not_docked_raise_a_warning(monkeypatch, tmp_path):
    """
    Hallazgo real (7E2Y): el catálogo declara quince residuos de referencia y
    doce están en la cadena `R`, mientras el receptor de docking conserva sólo
    la `A`. El sitio que describen no existe en la estructura que se acopla.
    """
    source = tmp_path / "1ABC.pdb"
    source.write_text(MINIMAL_PDB, encoding="utf-8")
    monkeypatch.setattr(pf, "_source_pdb_path", lambda pdb_id: source)
    monkeypatch.setattr(pf, "_prepared_pdbqt_path", lambda pdb_id: None)

    report = _build(chain="A", catalog_hotspots=["B:TYR400", "A:CYS351"])

    control = _control(report, "HOTSPOTS_FUERA_DEL_RECEPTOR")
    assert control["state"] == "advertencia"
    assert "B" in control["observation"]
    # Es advertencia, no bloqueo: el usuario puede saber algo que el catálogo
    # no sabe.
    assert "HOTSPOTS_FUERA_DEL_RECEPTOR" not in report["technical_blockers"]


@rdkit_available
def test_hotspots_inside_the_docked_chain_pass(monkeypatch, tmp_path):
    source = tmp_path / "1ABC.pdb"
    source.write_text(MINIMAL_PDB, encoding="utf-8")
    monkeypatch.setattr(pf, "_source_pdb_path", lambda pdb_id: source)
    monkeypatch.setattr(pf, "_prepared_pdbqt_path", lambda pdb_id: None)

    report = _build(chain="A", catalog_hotspots=["A:CYS351", "A:GLY352"])
    assert _control(report, "HOTSPOTS_FUERA_DEL_RECEPTOR")["state"] == "pasa"


@rdkit_available
def test_hotspots_without_a_chain_prefix_are_not_evaluated(monkeypatch, tmp_path):
    # Adivinar la cadena sería inventar la comprobación.
    source = tmp_path / "1ABC.pdb"
    source.write_text(MINIMAL_PDB, encoding="utf-8")
    monkeypatch.setattr(pf, "_source_pdb_path", lambda pdb_id: source)
    monkeypatch.setattr(pf, "_prepared_pdbqt_path", lambda pdb_id: None)

    report = _build(chain="A", catalog_hotspots=["CYS351"])
    assert _control(report, "HOTSPOTS_FUERA_DEL_RECEPTOR")["state"] == "no_evaluado"
