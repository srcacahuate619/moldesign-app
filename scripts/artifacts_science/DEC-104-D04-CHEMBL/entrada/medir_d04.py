"""Contrasta los pKa de clase de MolDesign con la extracción ChEMBL25 indicada."""
import argparse
import csv
import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
from unittest.mock import patch

import numpy as np
from rdkit import Chem, RDLogger
from rdkit.Chem import Crippen, Descriptors, rdMolDescriptors
from rdkit.Chem.MolStandardize import rdMolStandardize
from rdkit.Chem.Scaffolds import MurckoScaffold

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend"))

from chem import ionizacion as ion
from chem.blood_viability import _calculate_cns_mpo

EXP = ROOT / "scripts/artifacts_science"
ARCHIVE = EXP / "DEC-104-D04-CHEMBL"
PH = 7.4
CHEMBL_SHA = "d727e142e729b1f47b27bf5fc695b3accd98d3bdfb3335b330190139c1990ad6"
FINDER = ion._explorar_centros


def sha(contents):
    return hashlib.sha256(contents).hexdigest()


def key(mol, stereo=True):
    return Chem.MolToSmiles(mol, isomericSmiles=stereo)


def parent(mol):
    return rdMolStandardize.Uncharger().uncharge(rdMolStandardize.FragmentParent(mol))


def reference_data(path):
    if sha(path.read_bytes()) != CHEMBL_SHA:
        raise ValueError("SDF fuera del registro")
    rows = defaultdict(list)
    excluded = Counter()
    for i, mol in enumerate(Chem.SDMolSupplier(str(path)), 1):
        if mol is None or not mol.HasProp("pKa"):
            excluded["sin_estructura_o_pka"] += 1
            continue
        pka = float(mol.GetProp("pKa"))
        if not math.isfinite(pka):
            excluded["pka_no_finito"] += 1
            continue
        if len(Chem.GetMolFrags(mol)) != 1 or Chem.GetFormalCharge(mol) or any(a.GetFormalCharge() for a in mol.GetAtoms()):
            excluded["mezcla_o_carga"] += 1
            continue
        temp = float(mol.GetProp("temp")) if mol.HasProp("temp") else math.nan
        rows[key(mol)].append({"fila_sdf": i, "pka": pka, "temperatura_original": temp if math.isfinite(temp) else None})
    data = {}
    for smiles, records in rows.items():
        m = Chem.MolFromSmiles(smiles)
        sites, complete = FINDER(m)
        if not complete or len(sites) != 1 or ion._clases_sin_pka(m):
            excluded["sin_asignacion_univoca"] += 1
            continue
        pka = [r["pka"] for r in records]
        if max(pka) - min(pka) > 1:
            excluded["mediciones_discordantes"] += 1
            continue
        scaffold = MurckoScaffold.MurckoScaffoldSmiles(mol=m) or smiles
        base, predicted, kind = sites[0]
        data[smiles] = {
            "pka": float(np.median(pka)), "clase": base, "centro": kind,
            "tabla": predicted, "andamio": scaffold,
            "ajuste": int(sha(scaffold.encode()), 16) % 10 < 7,
            "mediciones": records,
        }
    return data, excluded


def evaluate(data):
    groups = defaultdict(list)
    for r in data.values():
        groups[r["clase"]].append(r)
    stats, alternatives = {}, {}
    for name, rows in sorted(groups.items()):
        a = [r for r in rows if r["ajuste"]]
        t = [r for r in rows if not r["ajuste"]]
        errors = np.array([r["tabla"] - r["pka"] for r in rows])
        s = dict(n=len(rows), n_ajuste=len(a), n_evaluacion=len(t), tipo=rows[0]["centro"],
                 mae_tabla=float(np.abs(errors).mean()), sesgo_tabla=float(errors.mean()), autorizado=False)
        stats[name] = s
        if not a or not t:
            continue
        pka = float(np.median([r["pka"] for r in a]))
        diffs = defaultdict(list)
        expected = [r for r in t if abs(r["pka"] - PH) > .3]
        before = sum((r["pka"] > PH) == (r["tabla"] > PH) for r in expected)
        after = sum((r["pka"] > PH) == (pka > PH) for r in expected)
        for r in t:
            diffs[r["andamio"]].append(abs(r["tabla"] - r["pka"]) - abs(pka - r["pka"]))
        sizes = np.array([len(v) for v in diffs.values()])
        sums = np.array([sum(v) for v in diffs.values()])
        ids = np.random.default_rng(20261114).integers(len(sizes), size=(2000, len(sizes)))
        boot = sums[ids].sum(axis=1) / sizes[ids].sum(axis=1)
        interval = np.quantile(boot, [.025, .975]).tolist()
        benefit = float(sums.sum() / len(t))
        s.update(
            pka_mediana_ajuste=pka, andamios_evaluacion=len(diffs),
            mejora_mae_evaluacion=benefit, ic95_mejora=interval,
            no_ambiguos=len(expected), correctos_tabla=before, correctos_mediana=after,
        )
        if len(a) >= 20 and len(t) >= 20 and len(diffs) >= 10 and benefit >= .5 and interval[0] > 0 and after >= before:
            s["autorizado"] = True
            alternatives[name] = pka
    return stats, alternatives


def corpora():
    mols = []
    for line in (EXP / "FEP-01/per_complex.jsonl").read_text(encoding="utf-8").splitlines():
        pid = json.loads(line)["pid"]
        file = ROOT / "data" / "pdbbind" / pid / f"{pid}_ligand.sdf"
        m = Chem.MolFromMolFile(str(file)) if file.exists() else None
        mols.append((pid, m))
    with (EXP / "CAL-D-01-R4-2-VMAT2-8T69/entrada/panel_congelado.csv").open(encoding="utf-8", newline="") as f:
        vmat = [(r["padre"], Chem.MolFromSmiles(r["smiles"])) for r in csv.DictReader(f) if r["rol"] == "primario"]
    assert len(mols) == 203 and len(vmat) == 89
    return {"MolFlex": mols, "8T69": vmat}


def best_species(mol, table):
    from dimorphite_dl import protonate_smiles

    smiles = key(mol)
    lp = Crippen.MolLogP(mol)
    args = (Descriptors.MolWt(mol), lp, rdMolDescriptors.CalcTPSA(mol), rdMolDescriptors.CalcNumHBD(mol),
            rdMolDescriptors.CalcNumHBA(mol), smiles)
    candidates = protonate_smiles(smiles, ph_min=PH, ph_max=PH, precision=0, max_variants=128)

    def amended(m):
        centers, complete = FINDER(m)
        return [(name, table.get(name, pka), char) for name, pka, char in centers], complete

    with patch("chem.ionizacion._explorar_centros", side_effect=amended):
        docked, _ = ion.elegir_microestado(smiles, candidates, PH)
        logd = ion.analizar_ionizacion(smiles, lp).logd
        mpo = _calculate_cns_mpo(*args)
    docked_mol = Chem.MolFromSmiles(docked)
    return dict(especie=key(docked_mol), carga=Chem.GetFormalCharge(docked_mol), logd=logd, cns_mpo=mpo)


def exposures(data, alternatives):
    relaxed = defaultdict(list)
    for smiles in data:
        relaxed[key(Chem.MolFromSmiles(smiles), stereo=False)].append(smiles)
    output = {}
    details = []
    for name, rows in corpora().items():
        counts = Counter()
        for ident, mol in rows:
            if mol is None:
                counts["falta_grafo"] += 1
                continue
            counts["leidos"] += 1
            m = parent(mol)
            exact = data.get(key(m))
            counts["medido_entrada_exacta"] += key(mol) in data
            counts["medido_normalizado_isomerico"] += exact is not None
            counts["solo_conectividad"] += exact is None and bool(relaxed.get(key(m, stereo=False)))
            sites, complete = FINDER(m)
            replace = {cl: alternatives[cl] for cl, _, _ in sites if cl in alternatives}
            if not replace and exact is None:
                continue
            try:
                before = best_species(m, {})
                after = best_species(m, replace) if complete and replace else None
                measured = best_species(m, {exact["clase"]: exact["pka"]}) if exact else None
            except Exception as exc:
                counts["fallo_modelo"] += 1
                details.append({"conjunto": name, "id": ident, "error": f"{type(exc).__name__}: {exc}"})
                continue
            for kind, result in [("ajuste_por_clase", after), ("referencia_medida", measured)]:
                if not result:
                    continue
                counts[f"comparados_{kind}"] += 1
                for label in ("carga", "especie", "logd", "cns_mpo"):
                    counts[f"cambia_{label}_{kind}"] += result[label] != before[label]
                if before != result:
                    # Los derivados de PDBbind sólo identifican el PDB, sin SMILES.
                    numeric = lambda x: {k: v for k, v in x.items() if k != "especie"}
                    details.append({"conjunto": name, "id": ident, "brazo": kind, "antes": numeric(before),
                                    "despues": numeric(result), "especie_cambia": before["especie"] != result["especie"]})
        output[name] = {"n": len(rows), **dict(counts)}
    return output, details


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sdf", type=Path)
    parser.add_argument("--archivar", action="store_true")
    args = parser.parse_args()
    RDLogger.DisableLog("rdApp.*")
    data, exclusions = reference_data(args.sdf)
    stats, alternatives = evaluate(data)
    exposure, details = exposures(data, alternatives)
    metrics = dict(n_admitidos=len(data), descartes=dict(exclusions), por_clase=stats, candidatos=alternatives,
                   corpus=exposure, cambios=details)
    if args.archivar:
        if json.loads((ARCHIVE / "procedencia.json").read_text(encoding="utf-8"))["salidas"]:
            raise SystemExit("Experimento ya cerrado")
        (ARCHIVE / "metrics.json").write_text(json.dumps(metrics, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
        (ARCHIVE / "per_complex.jsonl").write_text(
            "".join(json.dumps({"id_anonimo": sha(smi.encode()), **row}) + "\n" for smi, row in sorted(data.items())),
            encoding="utf-8",
        )
    print(json.dumps({**metrics, "cambios": len(details)}, ensure_ascii=True))


if __name__ == "__main__":
    main()
