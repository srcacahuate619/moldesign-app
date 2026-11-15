"""Imprime las cifras de los contrastes secundarios de 1.0.4."""
import hashlib
import json
import math
import os
import subprocess
import sys
import tempfile
from collections import Counter
from contextlib import redirect_stdout
from pathlib import Path
from statistics import mean
from unittest.mock import patch

import numpy as np
from scipy.stats import binom, rankdata

ROOT = Path(__file__).resolve().parents[3]
BASE = "77aeb73775fd334a24bbe5e3e7382dd2d456379e"
ART = ROOT / "scripts" / "artifacts_science"
sys.path.insert(0, str(ROOT / "backend"))
os.environ["MOLDESIGN_TESTING"] = "1"


def read_git(rev, name):
    return subprocess.check_output(["git", "show", f"{rev}:{name}"], cwd=ROOT)


def read_jsonl(exp):
    return [
        json.loads(line) for line in (ART / exp / "per_complex.jsonl").read_text(encoding="utf-8").splitlines()
    ]


def exact_power(n, discordance, effect):
    k = np.arange(n + 1)
    critical = binom.ppf(0.025, k, 0.5).astype(int)
    critical -= 2 * binom.cdf(critical, k, 0.5) > 0.05
    favor_new = (discordance + effect) / (2 * discordance)
    probability = binom.cdf(critical, k, favor_new) + binom.sf(k - critical - 1, k, favor_new)
    return float(np.dot(binom.pmf(k, n, discordance), probability))


def aguas():
    rows = read_jsonl("REC-11")
    q = sum(r["discordante"] for r in rows) / len(rows)
    effects = (0.05, 0.10)
    return {
        "n": len(rows),
        "cobertura": {a: sum(r[a]["cubierto"] for r in rows) for a in ("CON", "SIN")},
        "discordancias_CON_SIN": [sum(r["gana_" + a] for r in rows) for a in ("CON", "SIN")],
        "q": q,
        "potencia_116": {str(d): exact_power(len(rows), q, d) for d in effects},
        "primer_n_con_potencia_80": {
            str(d): next(n for n in range(1, 2000) if exact_power(n, q, d) >= 0.8) for d in effects
        },
    }


def pka():
    from rdkit import Chem
    from rdkit.Chem import Crippen, Descriptors, rdMolDescriptors
    from chem.blood_viability import _calculate_cns_mpo
    from chem.conformer import _construir_conformero
    from chem.especie_en_revision import motivos_de_revision
    from chem.ionizacion import analizar_ionizacion

    raw = read_git("665a473b", "scripts/amina_pka_01/resultados.json")
    cohort = json.loads(raw)["compuestos"]
    included = [r for r in cohort if r["puntuado"]]
    classes = sorted({r["estrato"] for r in included})
    stats = {}
    for group in classes:
        errors = [9.8 - r["pka_mediana"] for r in included if r["estrato"] == group]
        stats[group] = {"n": len(errors), "mae": mean(map(abs, errors)), "sesgo": mean(errors)}

    clopidogrel = next(r for r in cohort if r["id"] == "S5-01")
    smiles = clopidogrel["smiles"]
    mol = Chem.MolFromSmiles(smiles)
    logp = Crippen.MolLogP(mol)
    args = (
        Descriptors.MolWt(mol), logp, rdMolDescriptors.CalcTPSA(mol),
        rdMolDescriptors.CalcNumHBD(mol), rdMolDescriptors.CalcNumHBA(mol), smiles,
    )
    ion = analizar_ionizacion(smiles, logp)
    mpo = _calculate_cns_mpo(*args)
    state = _construir_conformero(smiles, 7.4, None)["estado_del_ligando"]
    docked = state["smiles_acoplado"]
    previous = {"pka": ion.pka_mas_basico, "logd": ion.logd, "cns_mpo": mpo}
    ion.pka_mas_basico = 4.55
    ion.logd = round(logp - math.log10(1 + 10 ** (4.55 - 7.4)), 2)
    with patch("chem.ionizacion.analizar_ionizacion", return_value=ion):
        estimated = _calculate_cns_mpo(*args)
    return {
        "amina_archivo_sha256": hashlib.sha256(raw).hexdigest(),
        "por_estrato": stats,
        "clopidogrel": {
            "smiles": smiles, "smiles_acoplado": docked,
            "carga_acoplada": Chem.GetFormalCharge(Chem.MolFromSmiles(docked)),
            "motivos_de_revision": [str(v) for v in motivos_de_revision(docked)],
            "logp_crippen": logp,
            "producto": previous,
            "sensibilidad_4_55": {"logd": ion.logd, "cns_mpo": estimated, "fraccion_protonada": 1 / (1 + 10 ** (7.4 - 4.55))},
        },
    }


def metales():
    report = ROOT / "docs/auditorias/metales_junto_al_sitio_2026-10-11.json"
    ions = json.loads(report.read_text(encoding="utf-8"))["filas"]
    kinds = sorted({r["metal"] for r in ions})
    stats = {}
    for kind in kinds:
        metal = [r for r in ions if r["metal"] == kind]
        linked = [r for r in metal if r["lo_coordina_el_ligando"]]
        stats[kind] = {
            "iones": len(metal), "coordinados": len(linked),
            "entradas": len({r["pdb_id"] for r in metal}),
            "entradas_coordinadas": len({r["pdb_id"] for r in linked}),
        }
    rows = read_jsonl("MET-01-R1-ION-DEL-SITIO")
    audit = {}
    for entry in ("1BN1", "2AW1", "4QA0", "2JDI", "4WUD", "4PHL"):
        chosen = [r for r in rows if r["entry"] == entry and r["arm"] == "CON" and r["phase"] == "confirmatory"]
        passed = [r for r in chosen if r["physical_status"] == "passed"]
        audit[entry] = {
            "n": len(chosen), "pasaron": len(passed),
            "pasaron_y_cerca_del_ion_del_cristal": sum(
                any(i["crystal_donor_A"] <= 2.8 and i["within_2_8_A"] for i in r["ion_distances"]) for r in passed
            ),
            "pasaron_y_algun_ion_cerca": sum(any(i["within_2_8_A"] for i in r["ion_distances"]) for r in passed),
        }
    return {"por_metal": stats, "lectura_seis_pdb": audit}


def exhaustividad():
    rows = read_jsonl("SUP-04-EXHAUSTIVIDAD-8T69")
    n = len(rows)
    indices = np.random.default_rng(20261025).integers(0, n, size=(10000, n))
    values = np.array([r["pki"] for r in rows])

    def correlations(x, y):
        a, b = rankdata(x, axis=-1), rankdata(y, axis=-1)
        a -= a.mean(axis=-1, keepdims=True)
        b -= b.mean(axis=-1, keepdims=True)
        return (a * b).sum(axis=-1) / np.sqrt((a * a).sum(axis=-1) * (b * b).sum(axis=-1))

    stats = {}
    for arm in ("e8", "e8s43", "e16", "e32"):
        q = np.array([r["Q_" + arm] for r in rows])
        samples = correlations(q[indices], values[indices])
        stats[arm] = {"n": n, "rho": float(correlations(q, values)), "ic95": np.quantile(samples, [0.025, 0.975]).tolist()}
    return stats


def torsiones():
    import meeko
    from rdkit import Chem
    from rdkit.Chem import AllChem

    pairs = [("N", "CA"), ("CA", "C"), ("C", "N")]
    out = {}
    for sequence in ("AAA", "APA", "AGKV"):
        mol = Chem.AddHs(Chem.MolFromSequence(sequence))
        params = AllChem.ETKDGv3()
        params.randomSeed = 42
        if AllChem.EmbedMolecule(mol, params) < 0:
            raise RuntimeError(f"No se pudo embeber {sequence}")
        setup, = meeko.MoleculePreparation().prepare(mol)
        counts = {f"{a}-{b}": [0, 0] for a, b in pairs}
        for (ai, bi), bond in setup.bond_info.items():
            a, b = [mol.GetAtomWithIdx(i).GetPDBResidueInfo() for i in (ai, bi)]
            if a is None or b is None:
                continue
            if a.GetResidueNumber() > b.GetResidueNumber():
                a, b = b, a
            names = a.GetName().strip(), b.GetName().strip()
            same = a.GetResidueNumber() == b.GetResidueNumber()
            for x, y in pairs:
                match = (names == ("C", "N")) if (x, y) == ("C", "N") and not same else (
                    {x, y} == set(names) and (x, y) != ("C", "N") and same
                )
                if match:
                    counts[f"{x}-{y}"][0] += int(bond.rotatable)
                    counts[f"{x}-{y}"][1] += 1
        out[sequence] = counts
    return {"meeko": meeko.__version__, "rotables_total": out}


def catalogo():
    catalog = json.loads(read_git(BASE, "curated_targets.json"))
    panel = json.loads(read_git(BASE, "backend/data/anti_dianas_bowes44.json"))["dianas"]
    return {
        "sin_ligando": sum(not p.get("site_ligand") for p in catalog),
        "total_catalogo": len(catalog),
        "panel": dict(Counter(str(r.get("sitio_adjudicado")) for r in panel)),
    }


def main():
    with tempfile.TemporaryDirectory(prefix="decisiones-104-") as tmp, redirect_stdout(sys.stderr):
        os.environ["LOCAL_DATA_DIR"] = tmp
        out = {
            "D03": aguas(), "D04": pka(), "D05": metales(), "D06": exhaustividad(),
            "D09": catalogo(), "D10": torsiones(),
        }
    print(json.dumps(out, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
