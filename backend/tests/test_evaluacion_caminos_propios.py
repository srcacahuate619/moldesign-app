"""Lo que la pestaña Evaluación dice de un receptor propio (caminos B y C).

El mismo error que P01 de FEP-09 en Preparación, ahora en Evaluación: código que da por hecha
la receta del catálogo, que retira todas las aguas, todos los metales y los cierres ACE/NME.
Medido con Vina real en una cápsula el 2026-10-11 sobre cdk2 y pde2 de OpenFF (camino A, B y C
con y sin origen):

- el aviso de aguas decía «se retiraron N aguas» de receptores que las conservaban;
- el supuesto del dossier decía «se eliminaron todas las aguas» de cualquier corrida;
- el receptor y el complejo de un PDBQT subido sin origen daban 404 (no hay `raw.pdb`);
- las interacciones de toda corrida B o C caían al análisis por distancias, sin química:
  el Zn y el Mg se escribían como «Z» y «M» (RDKit rechazaba el receptor) y el ACE A:-1
  rompía ProLIF, que guarda el número de residuo sin signo.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from rdkit import Chem
from rdkit.Chem import AllChem

CAJA = ((0.0, 0.0, 0.0), (20.0, 20.0, 20.0))


def _pdbqt(serial, nombre, residuo, numero, xyz, tipo):
    x, y, z = xyz
    return (f"ATOM  {serial:5d} {nombre:<4} {residuo:>3} A{numero:4d}    "
            f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00    {0.0:6.3f} {tipo:<2}")


def _depositado(serial, nombre, residuo, numero, xyz, elemento, registro="HETATM"):
    x, y, z = xyz
    return (f"{registro}{serial:5d} {nombre:<4} {residuo:>3} A{numero:4d}    "
            f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00          {elemento:>2}")


PROTEINA = _pdbqt(1, "N", "ALA", 1, (6.0, 0.0, 0.0), "N")
AGUA = _pdbqt(2, "OW", "HOH", 101, (1.0, 1.0, 1.0), "OA")
CRUDO_UNA = "\n".join([_depositado(1, "N", "ALA", 1, (6.0, 0.0, 0.0), "N", "ATOM  "),
                       _depositado(2, "O", "HOH", 101, (1.0, 1.0, 1.0), "O")]) + "\n"
CRUDO_DOS = CRUDO_UNA + _depositado(3, "O", "HOH", 102, (-2.0, 1.0, 1.0), "O") + "\n"


async def _avisos_de_aguas(tmp_path, monkeypatch, *, receptor: str, crudo: str | None, modo: str | None):
    """`run_vina_docking` con Vina y Meeko simulados: sólo importa el aviso de aguas."""
    from services.chemistry import censo_de_aguas
    from services.docking import vina_service as vina
    from utils import local_storage as storage
    from utils.cache import LocalRuntimeStore

    temporal = tmp_path / "temp"
    temporal.mkdir(exist_ok=True)
    monkeypatch.setattr(storage.settings, "local_data_dir", str(tmp_path / "data"))
    monkeypatch.setattr(storage.settings, "vina_temp_dir", str(temporal))
    monkeypatch.setattr(vina, "cache", LocalRuntimeStore())
    censo_de_aguas.invalidar_censo()
    contenido = (receptor + "\n").encode()
    fuente = "targets/USR_AGUA/prepared.pdbqt"
    await storage.write_bytes(contenido, fuente)
    await storage.write_bytes(b"ligand", "ligands/test/vina_input.pdbqt")
    informe = {"receptor_sha256": hashlib.sha256(contenido).hexdigest(), "protonation_templates": {},
               **({"modo_de_preparacion": modo} if modo else {})}
    await storage.write_bytes(json.dumps(informe).encode(), "targets/USR_AGUA/prepared.report.json")
    if crudo is not None:
        await storage.write_text("targets/USR_AGUA/raw.pdb", crudo)
    monkeypatch.setattr(vina, "prepare_target", AsyncMock(return_value=fuente))
    monkeypatch.setattr(vina, "resolve_effective_docking_box", lambda **kw: CAJA)
    monkeypatch.setattr(vina, "_resolve_executable", lambda path: "available")
    monkeypatch.setattr(vina, "_is_valid_sdf", lambda content: True)
    monkeypatch.setattr(vina, "parse_vina_output_sdf", lambda content: [
        {"rank": 1, "affinity": -8.0, "rmsd_lb": 0.0, "rmsd_ub": 0.0}])
    monkeypatch.setattr(vina, "_parse_vina_stdout", lambda content: [])
    monkeypatch.setattr(vina, "fusionar_rmsd_desde_pdbqt",
                        lambda poses, content: (poses, {"fusionado": True, "afinidades_discrepantes": []}))
    monkeypatch.setattr(vina, "verificar_pares_sdf_pdbqt", lambda *args: None)
    monkeypatch.setattr(vina, "_check_ligand_fits_box", lambda *args: None)
    monkeypatch.setattr(vina, "_prepare_ligand_pdbqt", AsyncMock(return_value="ligands/test/vina_input.pdbqt"))

    async def vina_simulado(**kwargs):
        kwargs["output_path"].write_text("MODEL 1\nENDMDL\n")
        kwargs["log_path"].write_text("registro")
        return ""

    async def exportar(*args, **kwargs):
        Path(args[-1]).write_text("SDF exportado")
        return SimpleNamespace(returncode=0, communicate=AsyncMock(return_value=(b"", b"")))

    monkeypatch.setattr(vina, "_run_vina_subprocess", vina_simulado)
    monkeypatch.setattr(vina.asyncio, "create_subprocess_exec", exportar)
    resultado = await vina.run_vina_docking("test", "USR_AGUA", force_redock=True)
    return [w for w in resultado.scientific_warnings
            if w["codigo"] in {"SITIO_DESOLVATADO", "AGUAS_DEL_SITIO_CONSERVADAS"}]


# ── El aviso de aguas mide el receptor que entró a Vina ───────────────────────

@pytest.mark.asyncio
async def test_camino_b_que_conserva_el_agua_no_dice_que_se_retiro(tmp_path, monkeypatch):
    avisos = await _avisos_de_aguas(tmp_path, monkeypatch, receptor=f"{PROTEINA}\n{AGUA}",
                                    crudo=CRUDO_UNA, modo="respetar")
    assert [a["codigo"] for a in avisos] == ["AGUAS_DEL_SITIO_CONSERVADAS"]
    assert "conserva las 1 agua(s)" in avisos[0]["mensaje"]
    assert "retiraron" not in avisos[0]["mensaje"] and avisos[0]["severidad"] == "info"


@pytest.mark.asyncio
async def test_si_conserva_menos_de_las_que_trae_el_origen_dice_cuantas(tmp_path, monkeypatch):
    avisos = await _avisos_de_aguas(tmp_path, monkeypatch, receptor=f"{PROTEINA}\n{AGUA}",
                                    crudo=CRUDO_DOS, modo="pdbqt_con_origen")
    assert "conserva 1 de las 2 aguas" in avisos[0]["mensaje"]
    assert "las otras 1 no están en el receptor" in avisos[0]["mensaje"]


@pytest.mark.asyncio
async def test_receta_del_catalogo_sigue_diciendo_lo_que_retiro(tmp_path, monkeypatch):
    """Control: sin aguas en el receptor acoplado, la frase de siempre, byte a byte."""
    from services.chemistry.censo_de_aguas import censar_aguas, describir_censo

    avisos = await _avisos_de_aguas(tmp_path, monkeypatch, receptor=PROTEINA, crudo=CRUDO_UNA, modo=None)
    assert [a["codigo"] for a in avisos] == ["SITIO_DESOLVATADO"]
    assert avisos[0]["mensaje"] == describir_censo(censar_aguas(CRUDO_UNA, *CAJA))
    assert "se retiraron 1 aguas" in avisos[0]["mensaje"]


@pytest.mark.asyncio
async def test_pdbqt_sin_origen_con_aguas_las_declara_conservadas(tmp_path, monkeypatch):
    avisos = await _avisos_de_aguas(tmp_path, monkeypatch, receptor=f"{PROTEINA}\n{AGUA}",
                                    crudo=None, modo="pdbqt_sin_origen")
    assert [a["codigo"] for a in avisos] == ["AGUAS_DEL_SITIO_CONSERVADAS"]
    assert "sin la estructura de origen" in avisos[0]["mensaje"]


@pytest.mark.asyncio
async def test_pdbqt_sin_origen_y_sin_aguas_no_afirma_que_se_retiraran(tmp_path, monkeypatch):
    avisos = await _avisos_de_aguas(tmp_path, monkeypatch, receptor=PROTEINA, crudo=None,
                                    modo="pdbqt_sin_origen")
    assert [a["codigo"] for a in avisos] == ["SITIO_DESOLVATADO"]
    assert "no se sabe si las tenía" in avisos[0]["mensaje"]
    assert "retiraron" not in avisos[0]["mensaje"]


@pytest.mark.asyncio
async def test_catalogo_sin_depositado_conserva_su_frase(tmp_path, monkeypatch):
    avisos = await _avisos_de_aguas(tmp_path, monkeypatch, receptor=PROTEINA, crudo=None, modo=None)
    assert "No se pudo leer la estructura depositada" in avisos[0]["mensaje"]


# ── El supuesto del dossier y de la certificación ────────────────────────────

@pytest.mark.parametrize("modo, esperado", [
    ("respetar", "archivo"), ("pdbqt_con_origen", "archivo"), ("pdbqt_sin_origen", "archivo"),
    ("automatico", "desolvatado"), (None, "desolvatado"),
])
def test_el_supuesto_de_aguas_depende_del_camino(modo, esperado):
    from services.blockchain import evidence_summary as es
    from tests.test_evidence_summary import _result, _target

    resultado = _result()
    if modo:
        resultado.docking_protocol["execution_provenance"] = {
            **resultado.docking_protocol["execution_provenance"], "receptor_prep": {"modo_de_preparacion": modo}}
    supuestos = es.build_evidence_summary(resultado, _target())["assumptions"]
    assert supuestos[-1] == (es.SUPUESTO_AGUAS_DEL_ARCHIVO if esperado == "archivo" else es.SUPUESTO_DESOLVATADO)
    if esperado == "archivo":
        assert "se eliminaron todas" not in " ".join(supuestos)


# ── Receptor y complejo de un PDBQT subido sin origen ────────────────────────

def _sin_crudo_con_copia(monkeypatch, tmp_path, copia: str | None):
    from api.routers import evaluation_files
    from services.docking import preparer
    from tests.test_evaluation_files import _files_fixture
    from utils import file_handlers, local_storage

    molecule_id, owner, db = _files_fixture(monkeypatch)
    db.molecule.target = SimpleNamespace(pdb_id="USR_SINORIGEN", is_private=True, creator_id=owner.id)
    ruta = tmp_path / "USR_SINORIGEN.pdb"
    if copia is not None:
        ruta.write_text(copia, encoding="utf-8")
    monkeypatch.setattr(preparer, "get_target_pdb_path", lambda pdb_id: str(ruta))
    # El recurso verificable es el snapshot preparado, nunca la copia mutable de la subida.
    import hashlib
    preparado = copia or "ATOM      1  N   ALA A   1       6.000   0.000   0.000  1.00 20.00     0.000 N\n"
    db.result.receptor_sha256 = hashlib.sha256(preparado.encode()).hexdigest()
    monkeypatch.setattr(local_storage, "exists", AsyncMock(side_effect=lambda path: copia is not None and path == db.result.receptor_path))
    monkeypatch.setattr(local_storage, "read_text", AsyncMock(side_effect=lambda path: preparado if path == db.result.receptor_path else "pose\nM  END\n"))
    descarga = AsyncMock()
    monkeypatch.setattr(file_handlers, "download_pdb_from_rcsb", descarga)
    return evaluation_files, molecule_id, owner, db, descarga


@pytest.mark.asyncio
async def test_receptor_sin_origen_sirve_su_snapshot_preparado(monkeypatch, tmp_path):
    copia = _depositado(1, "N", "ALA", 1, (6.0, 0.0, 0.0), "N", "ATOM  ") + "\n"
    files, molecule_id, owner, db, descarga = _sin_crudo_con_copia(monkeypatch, tmp_path, copia)
    respuesta = await files.get_protein_file(molecule_id, owner, db)
    assert respuesta.status_code == 200 and "ALA" in respuesta.body.decode()
    descarga.assert_not_awaited()


@pytest.mark.asyncio
async def test_complejo_sin_origen_se_arma_con_el_snapshot_preparado(monkeypatch, tmp_path):
    import services.docking.pdb_assembly as pdb_assembly

    copia = _depositado(1, "N", "ALA", 1, (6.0, 0.0, 0.0), "N", "ATOM  ") + "\n"
    files, molecule_id, owner, db, descarga = _sin_crudo_con_copia(monkeypatch, tmp_path, copia)
    monkeypatch.setattr(pdb_assembly, "merge_protein_ligand_pdb", lambda proteina, sdf: proteina + "LIGANDO\n")
    respuesta = await files.get_complex_file(molecule_id, owner, db)
    assert respuesta.status_code == 200 and "ALA" in respuesta.body.decode() and "LIGANDO" in respuesta.body.decode()
    descarga.assert_not_awaited()


@pytest.mark.asyncio
async def test_sin_copia_sigue_siendo_404_y_no_se_pide_a_rcsb(monkeypatch, tmp_path):
    from fastapi import HTTPException

    files, molecule_id, owner, db, descarga = _sin_crudo_con_copia(monkeypatch, tmp_path, None)
    for endpoint in (files.get_protein_file, files.get_complex_file):
        with pytest.raises(HTTPException) as error:
            await endpoint(molecule_id, owner, db)
        assert error.value.status_code == 404
    descarga.assert_not_awaited()


# ── Interacciones: metales y numeración negativa ─────────────────────────────

def test_los_metales_del_pdbqt_conservan_su_elemento():
    from api.routers.interactions import _pdbqt_receptor_a_pdb

    pdb = _pdbqt_receptor_a_pdb("\n".join([
        _pdbqt(1, "ZN", "ZN", 401, (0.0, 0.0, 0.0), "Zn"),
        _pdbqt(2, "MG", "MG", 402, (3.0, 0.0, 0.0), "Mg"),
        _pdbqt(3, "CA", "CA", 403, (6.0, 0.0, 0.0), "Ca"),
        _pdbqt(4, "NA", "NA", 404, (9.0, 0.0, 0.0), "Na"),
        _pdbqt(5, "NE2", "HIE", 57, (12.0, 0.0, 0.0), "NA"),
        _pdbqt(6, "CB", "ALA", 58, (15.0, 0.0, 0.0), "C"),
    ]))
    elementos = [linea[76:78] for linea in pdb.splitlines() if linea.startswith("ATOM")]
    # El calcio no es carbono, el sodio no es el nitrógeno aceptor `NA` de AutoDock.
    assert elementos == ["ZN", "MG", "CA", "NA", " N", " C"]
    molecula = Chem.MolFromPDBBlock(pdb, removeHs=False, sanitize=True)
    assert molecula is not None
    assert [a.GetSymbol() for a in molecula.GetAtoms()] == ["Zn", "Mg", "Ca", "Na", "N", "C"]


def test_un_residuo_con_numero_negativo_no_tira_prolif(tmp_path):
    from services.interactions.analyzer import analyze_complex

    receptor = Chem.AddHs(Chem.MolFromSmiles("CCCC"))
    ligando = Chem.AddHs(Chem.MolFromSmiles("CCCC"))
    assert AllChem.EmbedMolecule(receptor, randomSeed=3) == 0
    assert AllChem.EmbedMolecule(ligando, randomSeed=4) == 0
    conformero = ligando.GetConformer()
    for i in range(ligando.GetNumAtoms()):
        p = conformero.GetAtomPosition(i)
        conformero.SetAtomPosition(i, (p.x + 3.8, p.y, p.z))
    bloque = Chem.MolToPDBBlock(receptor).replace("HETATM", "ATOM  ")
    # Residuo -1, como el ACE A:-1 que conserva el camino B en cdk2 de OpenFF.
    bloque = "\n".join(l[:22] + f"{-1:4d}" + l[26:] if l.startswith("ATOM") else l for l in bloque.splitlines())
    pdb = tmp_path / "protein.pdb"
    pdb.write_text(bloque + "\n", encoding="utf-8")
    sdf = tmp_path / "ligand.sdf"
    sdf.write_text(Chem.MolToMolBlock(ligando) + "\n$$$$\n", encoding="utf-8")

    informe = analyze_complex(pdb, sdf)
    assert informe.engine.startswith("prolif:"), informe.engine
    assert informe.interactions and {i.residue_number for i in informe.interactions} == {-1}


# ── En inglés ────────────────────────────────────────────────────────────────

def test_las_frases_nuevas_se_leen_en_ingles():
    from core.i18n_plantillas import _PARECE_CASTELLANO, traducir
    from services.blockchain.evidence_summary import SUPUESTO_AGUAS_DEL_ARCHIVO
    from services.chemistry.censo_de_aguas import CensoDeAguas, describir_aguas_conservadas

    frases = [
        SUPUESTO_AGUAS_DEL_ARCHIVO,
        describir_aguas_conservadas(3, None),
        describir_aguas_conservadas(3, CensoDeAguas(5, 3, 1, 4)),
        describir_aguas_conservadas(1, CensoDeAguas(5, 3, 1, 4)),
        "Preparación en condición desolvatada: el receptor acoplado no trae aguas cristalográficas dentro de "
        "la caja de acoplamiento. Se subió sin su estructura de origen, así que no se sabe si las tenía.",
    ]
    for frase in frases:
        en = traducir(frase, "en")
        assert en != frase and not _PARECE_CASTELLANO.search(en), frase
