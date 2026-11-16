"""Compara la preparación en serie y al arrancar en paralelo.

Ejecutar cada modo en un proceso nuevo para que Dimorphite-DL empiece sin caché.
"""

import argparse
import asyncio
import sys
from pathlib import Path
from threading import Lock
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from medir import ROOT, compounds, save

NAMES = ("amiodarone", "cisapride", "droperidol", "haloperidol")


async def probe(data, mode, run):
    sys.path.insert(0, str(ROOT / "scripts"))
    from invariancia_catalogo_receptores import _entorno

    output = data / "contrarreplica"
    output.mkdir(exist_ok=True)
    label = f"{mode}-{run}"
    _entorno(output / f"arranque-{label}")

    import dimorphite_dl
    from chem.conformer import generate_conformer
    from dimorphite_dl.protonate.data import PKaData

    entries = [item for item in compounds(data) if item["compound"] in NAMES]
    if PKaData._instance is not None:
        raise RuntimeError("La tabla ya estaba inicializada al entrar a la sonda")
    if mode == "paralelo-caliente":
        PKaData()

    original = dimorphite_dl.protonate_smiles
    candidates = {}
    lock = Lock()

    def capture(smiles, **params):
        choices = original(smiles, **params)
        with lock:
            candidates[smiles] = {"candidatos": sorted(choices), "p": params}
        return choices

    async def prepare(entry):
        result = await generate_conformer(entry["smiles"], ph=7.4)
        info = result["estado_del_ligando"]["protonacion"]
        return {"compound": entry["compound"], "elegido": result["canonical_smiles"],
                "alternativas": info["alternativas"], "version_motor": info["version_motor"]}

    with patch.object(dimorphite_dl, "protonate_smiles", side_effect=capture):
        if mode == "serie":
            rows = [await prepare(entry) for entry in entries]
        else:
            rows = await asyncio.gather(*(prepare(entry) for entry in entries))
    save(output / f"arranque-{label}.json", {
        "modo": mode, "repeticion": run, "reglas_finales": len(PKaData._data),
        "resultado": rows, "candidatos": candidates,
    })
    print(label, *(f"{row['compound']}={row['alternativas']}" for row in rows), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("data", type=Path)
    parser.add_argument("mode", choices=("serie", "paralelo-frio", "paralelo-caliente"))
    parser.add_argument("run", type=int)
    args = parser.parse_args()
    asyncio.run(probe(args.data, args.mode, args.run))
