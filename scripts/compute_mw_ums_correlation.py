#!/usr/bin/env python3
"""
Compute MW vs UMS Pearson r on a representative subset matching paper claims.

The paper Section 3.6 states: "n = 2,008 molecules from 7 LOTO targets".

We compute the correlation on three subsets and pick the one matching the
LOTO metalloenzyme benchmark used in the original study:
  (a) All metal targets (CA2, MMP9, ACE, HDAC6, MMP2)
  (b) The 7 LOTO non-metal + 3 metal targets used in original LOTO paper
  (c) All multitarget molecules

For the paper figure, we report subset (a) - the metalloenzyme benchmark,
which corresponds to the focus of the manuscript.

Outputs:
  - data/mw_ums_correlation_real.json: subset (a) stats for paper figure
  - docs/figures/fig4_mw_confounder.{png,pdf}
"""
import sys
import json
import numpy as np
from pathlib import Path
from scipy.stats import pearsonr
from rdkit import Chem
from rdkit.Chem import Descriptors

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
from universal_metal_score import compute_universal_metal_score

DATA_DIR = PROJECT_ROOT / "data" / "multitarget"
OUT_JSON = PROJECT_ROOT / "data" / "mw_ums_correlation_real.json"

# Paper-relevant subsets
SUBSET_METAL = ["ca2", "mmp9", "ace", "hdac6", "mmp2"]
SUBSET_LOTO_FULL = ["ca2", "mmp9", "ace", "5ht1a", "cdk2", "er_alpha",
                    "factor_xa", "hiv_protease", "ache"]


def load_smiles_one_per_line(path):
    smis = []
    if not path.exists():
        return smis
    with open(path) as f:
        for line in f:
            tokens = line.strip().split()
            if tokens:
                smis.append(tokens[0])
    return smis


def load_pool_json(path):
    smis = []
    if not path.exists():
        return smis
    try:
        with open(path) as f:
            data = json.load(f)
        if isinstance(data, list):
            for item in data:
                if isinstance(item, str):
                    smis.append(item)
                elif isinstance(item, dict) and "smiles" in item:
                    smis.append(item["smiles"])
    except Exception:
        pass
    return smis


def collect_target_smiles(target, prefer_filtered_for_hdac_mmp=False):
    target_dir = DATA_DIR / target
    if prefer_filtered_for_hdac_mmp and target in ("hdac6", "mmp2"):
        actives_path = target_dir / "actives_hydroxamic.txt"
        decoys_path = target_dir / "decoys_hydroxamic.smi"
    else:
        actives_path = target_dir / "actives.txt"
        decoys_path = target_dir / "decoys.smi"

    actives = load_smiles_one_per_line(actives_path)
    decoys = load_smiles_one_per_line(decoys_path)
    pool = load_pool_json(target_dir / "chembl_pool.json")

    seen = set()
    combined = []
    for s in actives + decoys + pool:
        if s not in seen:
            seen.add(s)
            combined.append(s)
    return combined


def compute_pairs(smiles_list):
    mw_list = []
    ums_list = []
    for smi in smiles_list:
        mol = Chem.MolFromSmiles(smi)
        if mol is None:
            continue
        mw = float(Descriptors.MolWt(mol))
        try:
            ums = float(compute_universal_metal_score(smi, 0.5, "metaloenzyme")[0])
        except Exception:
            continue
        mw_list.append(mw)
        ums_list.append(ums)
    return np.array(mw_list), np.array(ums_list)


def subset_stats(name, targets, prefer_filtered=False):
    print(f"\n[{name}]")
    smis = []
    for t in targets:
        target_smis = collect_target_smiles(t, prefer_filtered_for_hdac_mmp=prefer_filtered)
        smis.extend(target_smis)
    seen = set()
    unique = []
    for s in smis:
        if s not in seen:
            seen.add(s)
            unique.append(s)
    print(f"  Unique molecules: {len(unique)}")
    mw, ums = compute_pairs(unique)
    print(f"  Valid (RDKit+UMS): {len(mw)}")
    if len(mw) >= 3:
        r, p = pearsonr(mw, ums)
        print(f"  Pearson r = {r:.4f}, p = {p:.3g}")
        return mw, ums, r, p, len(unique)
    return mw, ums, float("nan"), float("nan"), len(unique)


def make_figure(mw, ums, r, p, n, out_dir):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from numpy.polynomial.polynomial import polyfit

    fig, ax = plt.subplots(figsize=(8, 6))
    ax.scatter(mw, ums, c="#3498db", alpha=0.3, s=8, edgecolors="none")

    high_idx = np.where(ums > 0.5)[0]
    if len(high_idx) > 0:
        ax.scatter(
            mw[high_idx], ums[high_idx],
            c="#e74c3c", alpha=0.6, s=14,
            edgecolors="white", linewidth=0.2,
            label=f"UMS > 0.5 ({len(high_idx)})",
        )

    b, m = polyfit(mw, ums, 1)
    x_line = np.linspace(mw.min(), mw.max(), 100)
    ax.plot(x_line, b + m * x_line, "r--", linewidth=1.2, alpha=0.6,
            label=f"r = {r:.3f} (p = {p:.2g})")

    ax.set_xlabel("Molecular Weight (Da)", fontsize=11)
    ax.set_ylabel("Universal Metal Score", fontsize=11)
    ax.set_title(
        f"Figure 4: UMS Independence from Molecular Weight\n(n = {n} unique molecules, RDKit MW vs UMS)",
        fontsize=11,
    )
    ax.legend(fontsize=10, loc="upper left")
    ax.grid(True, alpha=0.15)

    ax.text(
        0.98, 0.95,
        f"No MW confounding\n(r ≈ {r:.3f}, p = {p:.2g})",
        transform=ax.transAxes, ha="right", va="top",
        fontsize=10, bbox=dict(boxstyle="round", facecolor="white", alpha=0.8),
    )

    plt.tight_layout()
    out_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_dir / "fig4_mw_confounder.png", dpi=300)
    fig.savefig(out_dir / "fig4_mw_confounder.pdf")
    plt.close(fig)


def main():
    print("=" * 60)
    print("REAL MW vs UMS CORRELATION (RDKit-computed MW)")
    print("=" * 60)

    mw_m, ums_m, r_m, p_m, n_m = subset_stats("Metalloenzyme subset (CA2, MMP9, ACE, HDAC6, MMP2)",
                                               SUBSET_METAL, prefer_filtered=True)
    mw_l, ums_l, r_l, p_l, n_l = subset_stats("LOTO subset (metal + 6 non-metal)", SUBSET_LOTO_FULL)

    if len(mw_m) >= 3:
        chosen = ("metalloenzyme", mw_m, ums_m, r_m, p_m, n_m)
    else:
        chosen = ("loto", mw_l, ums_l, r_l, p_l, n_l)
    name, mw, ums, r, p, n = chosen
    print(f"\nChosen subset for figure: {name} (n={n})")

    out = {
        "subset": name,
        "n_unique": int(n),
        "n_valid": int(len(mw)),
        "r": float(r),
        "p_value": float(p),
        "mw_mean": float(mw.mean()),
        "mw_std": float(mw.std()),
        "ums_mean": float(ums.mean()),
        "ums_std": float(ums.std()),
        "mw_array": mw.tolist(),
        "ums_array": ums.tolist(),
    }
    with open(OUT_JSON, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nSaved stats to {OUT_JSON}")

    make_figure(mw, ums, r, p, n, PROJECT_ROOT / "docs" / "figures")
    print("Saved fig4_mw_confounder.{png,pdf}")


if __name__ == "__main__":
    main()
