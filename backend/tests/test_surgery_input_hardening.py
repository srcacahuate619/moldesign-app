import pytest
from fastapi import HTTPException
from api.routers import protein_surgery as api


@pytest.mark.asyncio
async def test_invalid_ligand_does_not_produce_default_box():
    with pytest.raises(HTTPException) as error:
        await api.dynamic_box_endpoint(api.DynamicBoxRequest(ligand_pdb_content="invalid ligand"))
    assert error.value.status_code == 422


@pytest.mark.asyncio
async def test_valid_box_preserves_existing_calculation():
    from rdkit import Chem
    mol = Chem.MolFromSmiles("CC")
    conf = Chem.Conformer(2)
    conf.SetAtomPosition(0, (1., 2., 3.))
    conf.SetAtomPosition(1, (7., 4., 5.))
    mol.AddConformer(conf)
    result = await api.dynamic_box_endpoint(api.DynamicBoxRequest(ligand_pdb_content=Chem.MolToMolBlock(mol)))
    assert (result.center_x, result.center_y, result.center_z) == (4, 3, 4)
    assert (result.ligand_span_x, result.ligand_span_y, result.ligand_span_z) == (6, 2, 2)
    assert result.size == 14
