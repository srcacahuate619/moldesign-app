#!/usr/bin/env python3
"""Ablation study: SMARTS-only vs +donor vs +MolChamb vs full UMS.

Runs two dataset variants per target for transparency:
  (a) dude_original  - full DUD-E actives+decoys from data/multitarget/{t}/{actives,decoys}
                       with molchamb_score=0.5 for all (no MolChamb dependency)
  (b) molchamb_loto  - subset that survived Vina docking in the MolChamb LOTO checkpoint
                       (vina_score is not None); uses real molchamb_score where present
"""
import sys
sys.path.insert(0, "scripts")
import json
from pathlib import Path
from sklearn.metrics import roc_auc_score

TARGETS = {
    "ca2":  {"ckpt": "data/molchamb_loto/checkpoints/benchmark_checkpoint_ca2.json"},
    "mmp9": {"ckpt": "data/benchmark_checkpoint_mmp9.json"},
    "ace":  {"ckpt": "data/benchmark_checkpoint_ace.json"},
}


def compute_warhead_only(smiles, family="metaloenzyme"):
    """SMARTS-only: warhead component."""
    from universal_metal_score import detect_warheads
    wh = detect_warheads(smiles)
    any_wh = any(wh.values())
    if family == "metaloenzyme" and any_wh:
        return 0.85 + 0.10 * min(sum(1 for v in wh.values() if v) / 3.0, 1.0)
    return 0.0


def compute_warhead_donor(smiles, family="metaloenzyme"):
    """SMARTS + donor count."""
    from rdkit import Chem
    wh_score = compute_warhead_only(smiles, family)
    if family != "metaloenzyme":
        return 0.3 * 0.5 + 0.7 * 0.5
    try:
        mol = Chem.MolFromSmiles(smiles)
        donor = sum(1 for a in mol.GetAtoms() if a.GetAtomicNum() in (7, 8, 16)) if mol else 0
    except Exception:
        donor = 0
    donor_comp = min(1.0, donor / 30.0)
    return 0.60 * wh_score + 0.20 * donor_comp + 0.20 * 0.5


def compute_warhead_molchamb(smiles, molchamb, family="metaloenzyme"):
    """SMARTS + MolChamb (no donor)."""
    from universal_metal_score import detect_warheads
    wh = detect_warheads(smiles)
    any_wh = any(wh.values())
    wh_comp = (0.85 + 0.10 * min(sum(1 for v in wh.values() if v) / 3.0, 1.0)) if any_wh else 0.0
    return 0.60 * wh_comp + 0.40 * float(molchamb)


def compute_full(smiles, molchamb, family="metaloenzyme"):
    from universal_metal_score import compute_universal_metal_score
    return compute_universal_metal_score(smiles, molchamb, family)[0]


def load_dude_original(target_name):
    """Load SMILES from data/multitarget/{t}/{actives.txt,decoys.smi}."""
    base = Path("data/multitarget") / target_name
    actives = [line.split()[0] for line in open(base / "actives.txt") if line.strip()]
    decoys = [line.strip().split()[0] for line in open(base / "decoys.smi") if line.strip()]
    mols = [{"smiles": s, "is_active": True, "molchamb": 0.5} for s in actives] + \
           [{"smiles": s, "is_active": False, "molchamb": 0.5} for s in decoys]
    return mols


def load_molchamb_loto(ckpt_path):
    """Load from checkpoint, keep only vina_score != None, use real molchamb_score."""
    data = json.loads(Path(ckpt_path).read_bytes().decode("utf-8", errors="replace"))
    results = data.get("results", [])
    mols = []
    for r in results:
        smi = r.get("smiles", "")
        if not smi:
            continue
        if r.get("vina_score") is None:
            continue
        mc = r.get("molchamb_score", 0.5)
        if mc is None:
            mc = 0.5
        mols.append({"smiles": smi, "is_active": r.get("is_active", False), "molchamb": mc})
    return mols


def run_ablation(mols, label, target_name):
    y = [1 if m["is_active"] else 0 for m in mols]
    n_act = sum(y)
    wh_scores = [compute_warhead_only(m["smiles"]) for m in mols]
    whd_scores = [compute_warhead_donor(m["smiles"]) for m in mols]
    wh_mc_scores = [compute_warhead_molchamb(m["smiles"], m["molchamb"]) for m in mols]
    full_scores = [compute_full(m["smiles"], m["molchamb"]) for m in mols]
    return {
        "n": len(mols), "n_act": n_act,
        "auc_warhead_only": round(roc_auc_score(y, wh_scores), 4),
        "auc_warhead_donor": round(roc_auc_score(y, whd_scores), 4),
        "auc_warhead_molchamb": round(roc_auc_score(y, wh_mc_scores), 4),
        "auc_full": round(roc_auc_score(y, full_scores), 4),
    }


print(f"{'Target':8s} {'Variant':16s} {'n':6s} {'act':5s} | {'WH-only':8s} {'WH+Donor':9s} {'WH+MolChamb':12s} {'Full UMS':8s}")
print("-" * 80)

results = {}
for name, cfg in TARGETS.items():
    results[name] = {}
    for variant, mols in [
        ("dude_original",   load_dude_original(name)),
        ("molchamb_loto",   load_molchamb_loto(cfg["ckpt"])),
    ]:
        r = run_ablation(mols, variant, name)
        results[name][variant] = r
        print(f"{name:8s} {variant:16s} {r['n']:6d} {r['n_act']:5d} | "
              f"{r['auc_warhead_only']:8.4f} {r['auc_warhead_donor']:9.4f} "
              f"{r['auc_warhead_molchamb']:12.4f} {r['auc_full']:8.4f}")

Path("data/molchamb_loto/ablation_study.json").write_text(json.dumps(results, indent=2))
print(f"\nSaved to data/molchamb_loto/ablation_study.json")
