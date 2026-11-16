"""Sondas post hoc de R3. Usa 5VA1 y los parámetros del estudio original."""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

from rdkit import Chem

sys.path.insert(0, str(Path(__file__).resolve().parent))
from medir import CHAINS, CENTER, ROOT, SIZE, compounds, save, sha

AMOXICILLIN = "amoxicillin"
BASES = ("haloperidol", "cisapride", "droperidol")


def alternates(name, archived):
    mol = Chem.RWMol(Chem.MolFromSmiles(archived))
    nitrogen = [atom for atom in mol.GetAtoms() if atom.GetAtomicNum() == 7]
    if name == AMOXICILLIN:
        lactam, = [atom for atom in nitrogen if atom.GetFormalCharge() == 1
                   and mol.GetRingInfo().IsAtomInRingOfSize(atom.GetIdx(), 4)]
        primary, = [atom for atom in nitrogen if atom.GetDegree() == 1 and atom.GetFormalCharge() == 0]
        lactam.SetFormalCharge(0)
        lactam.SetNumExplicitHs(0)
        Chem.SanitizeMol(mol)
        yield "anion", Chem.MolToSmiles(mol)
        primary.SetFormalCharge(1)
        primary.SetNumExplicitHs(3)
        primary.SetNoImplicit(True)
        Chem.SanitizeMol(mol)
        yield "zwitterion", Chem.MolToSmiles(mol)
    else:
        tertiary, = [atom for atom in nitrogen if atom.GetFormalCharge() == 0 and not atom.GetIsAromatic()
                    and atom.GetDegree() == 3 and mol.GetRingInfo().IsAtomInRingOfSize(atom.GetIdx(), 6)]
        tertiary.SetFormalCharge(1)
        tertiary.SetNumExplicitHs(1)
        tertiary.SetNoImplicit(True)
        Chem.SanitizeMol(mol)
        yield "cation_amina", Chem.MolToSmiles(mol)


async def measure(data, group):
    sys.path.insert(0, str(ROOT / "scripts"))
    from invariancia_catalogo_receptores import _entorno

    output = data / "contrarreplica" / group
    _entorno(output / "runtime")
    os.environ["VINA_CPU"] = "2"
    scratch = ROOT / ".experiment-runs" / f"herg-contrarreplica-{group}"
    scratch.mkdir(parents=True, exist_ok=True)
    os.environ["VINA_TEMP_DIR"] = str(scratch)

    import dimorphite_dl
    from chem.conformer import generate_conformer
    from services.docking.vina_service import run_vina_docking

    original = {item["compound"]: item for item in compounds(data)}
    metadata = json.loads((data / "preparacion.json").read_bytes())
    digest = metadata["receptor_sha256"]
    receptor = (data / "runtime" / "runs" / "receptors" / f"{digest}.pdbqt").read_bytes()
    if sha(receptor) != digest:
        raise ValueError("Huella del receptor distinta de la del piloto")
    names = (AMOXICILLIN,) if group == "amoxicilina" else BASES
    enumerate_protons = dimorphite_dl.protonate_smiles

    for name in names:
        auto = output / f"{name}-automatico.json"
        if not auto.is_file():
            seen = {}

            def capture(smiles, **kwargs):
                choices = enumerate_protons(smiles, **kwargs)
                seen.update(entrada_al_enumerador=smiles, candidatos=choices, parametros=kwargs)
                return choices

            with patch.object(dimorphite_dl, "protonate_smiles", side_effect=capture):
                prepared = await generate_conformer(original[name]["smiles"], ph=7.4)
            save(auto, dict(seen, elegido=prepared["canonical_smiles"],
                            protonacion=prepared["estado_del_ligando"]["protonacion"]))

        archive = json.loads((data / "corridas" / f"{name}-42.json").read_bytes())
        for state, alternate in alternates(name, archive["microstate"]):
            # A 42 se comparan todas. A 43 se usan los pares que tenían esa semilla
            # en el registro inicial. Se conserva la selección automática aparte.
            seeds = (42, 43) if (data / "corridas" / f"{name}-43.json").is_file() else (42,)
            with patch.object(dimorphite_dl, "protonate_smiles", return_value=[alternate]):
                fixed = await generate_conformer(alternate, ph=7.4, tautomero="entrada")
            if fixed["canonical_smiles"] != alternate:
                raise ValueError(f"El estado preparado no coincide con la intervención en {name}")
            for seed in seeds:
                out = output / f"{name}-{state}-{seed}.json"
                if out.is_file():
                    continue
                result = await run_vina_docking(
                    smiles_hash=fixed["smiles_hash"], smiles=alternate, target_pdb_id="5VA1",
                    target_chain="A", target_center=CENTER, target_size=SIZE, site_chains=CHAINS,
                    prepared_receptor_bytes=receptor, exhaustiveness=8, num_poses=9, seed=seed,
                )
                save(out, {"compound": name, "state": state, "smiles": alternate, "seed": seed,
                           "score": result.best_affinity, "result": result.model_dump(mode="json")})
                print(name, state, seed, result.best_affinity, flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("data", type=Path)
    parser.add_argument("group", choices=("amoxicilina", "bases"))
    args = parser.parse_args()
    asyncio.run(measure(args.data, args.group))
