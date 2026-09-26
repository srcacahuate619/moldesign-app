"""ORQ-001: no degradar a conectividad sin estereoquímica por dict, FTS o caché."""
import sqlite3
import time

import pytest


def test_pubchem_pide_y_lee_smiles_isomerico(monkeypatch):
    from services.ai import name_resolver as resolver
    urls = []

    def fake_get(url, timeout):
        urls.append(url)
        return {"PropertyTable": {"Properties": [{"SMILES": "C[C@H](O)C(=O)O", "ConnectivitySMILES": "CC(O)C(=O)O"}]}}

    monkeypatch.setattr(resolver, "_HAS_WEB_TOOLS", True)
    monkeypatch.setattr(resolver, "_http_get_json", fake_get)
    assert resolver._pubchem_name_to_smiles("lactic acid", 2) == "C[C@H](O)C(=O)O"
    assert "/property/MolecularWeight,XLogP,SMILES/JSON" in urls[0]


@pytest.mark.asyncio
async def test_nombre_cuarentena_no_cae_en_molgraph_ni_pubchem(monkeypatch, tmp_path):
    from services.ai import name_resolver as resolver

    def forbidden(*args, **kwargs):
        raise AssertionError("No se debe buscar una estructura no verificada")

    monkeypatch.setattr(resolver, "_query_molgraph_fts", forbidden)
    monkeypatch.setattr(resolver, "_pubchem_name_to_smiles", forbidden)
    # La cuarentena quedó vacía el 2026-09-26; el mecanismo se prueba con un
    # nombre ficticio para que siga protegido si vuelve a hacer falta.
    monkeypatch.setattr(resolver, "NOMBRES_ESTEREO_PENDIENTE", frozenset({"cuarentenol"}))
    result = await resolver.resolve_molecule_name(
        "cuarentenol", allow_web=True, molgraph_db_path=tmp_path / "none.db")
    assert result.smiles is None


@pytest.mark.asyncio
async def test_reincorporados_se_resuelven_localmente_con_estereoquimica(monkeypatch, tmp_path):
    from rdkit import Chem

    from services.ai import name_resolver as resolver

    def forbidden(*args, **kwargs):
        raise AssertionError("un nombre verificado localmente no consulta MolGraph ni PubChem")

    monkeypatch.setattr(resolver, "_query_molgraph_fts", forbidden)
    monkeypatch.setattr(resolver, "_pubchem_name_to_smiles", forbidden)
    for nombre, inchikey in (("paroxetina", "AHOUBRCZNHFOSL-YOEHRIQHSA-N"),
                             ("nicotina", "SNICXCGAKADSCV-JTQLQIEISA-N"),
                             ("naproxeno", "CMWTZPSULFXXJA-VIFPVBQESA-N")):
        result = await resolver.resolve_molecule_name(
            nombre, allow_web=True, molgraph_db_path=tmp_path / "none.db")
        assert Chem.MolToInchiKey(Chem.MolFromSmiles(result.smiles)) == inchikey


def test_cache_antigua_de_conectividad_no_se_reutiliza(monkeypatch, tmp_path):
    from services.ai import name_resolver as resolver
    db = tmp_path / "pubchem_cache.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE cache (smiles TEXT PRIMARY KEY, data_json TEXT, fetched_at REAL)")
    conn.execute("INSERT INTO cache VALUES (?, ?, ?)", ("CC(O)C(=O)O", '{"name": "lactic acid", "canonical_smiles": "CC(O)C(=O)O"}', time.time()))
    conn.commit()
    conn.close()
    monkeypatch.setattr(resolver, "_HAS_WEB_TOOLS", True)
    monkeypatch.setattr(resolver, "_pubchem_conn", lambda: sqlite3.connect(db))
    assert resolver._pubchem_cached_smiles_for("lactic acid") is None
