"""Diagnóstico completo de bottlenecks del modelo ML rescoring."""
import glob
import json
import os
from collections import defaultdict

import numpy as np

r = json.load(open(r"d:\molecular-design\data\pdbbind\artifacts\training_report.json"))

print("=== SHAP (features ordenados por importancia) ===")
shap = r["shap_summary"]
for k, v in sorted(shap.items(), key=lambda x: -x[1]):
    bar = "#" * int(v * 40)
    print(f"  {k:25s} {v:.4f}  {bar}")

print()
print("=== ABLATION ===")
for a in r["ablation"]:
    cfg = a["config"]
    nf = a["n_features"]
    sp = a["metrics"]["spearman"]
    pe = a["metrics"]["pearson"]
    print(f"  {cfg:10s}  features={nf:2d}  spearman={sp:.4f}  pearson={pe:.4f}")

print()
print("=== CV FOLDS (Model A vs NULL) ===")
cv_a = r["cross_validation"]["model_a"]
cv_n = r["cross_validation"]["model_null"]
print(f"  Model A:    Spearman {cv_a['spearman']['mean']:.4f} +/- {cv_a['spearman']['std']:.4f}  (min={cv_a['spearman']['min']:.4f}, max={cv_a['spearman']['max']:.4f})")
print(f"  Model NULL: Spearman {cv_n['spearman']['mean']:.4f} +/- {cv_n['spearman']['std']:.4f}  (min={cv_n['spearman']['min']:.4f}, max={cv_n['spearman']['max']:.4f})")
print(f"  Delta:      +{cv_a['spearman']['mean'] - cv_n['spearman']['mean']:.4f}")

print()
print("=== 3D EXTRACTION QUALITY ===")
cache_dir = r"d:\molecular-design\data\pdbbind\feature_cache"
files = glob.glob(os.path.join(cache_dir, "*.json"))
n_total = len(files)
n_all_zero = 0
n_nonzero = 0
nonzero_counts = []
for f in files:
    d = json.load(open(f))
    nz = sum(1 for v in d.values() if v > 0)
    if nz == 0:
        n_all_zero += 1
    else:
        n_nonzero += 1
        nonzero_counts.append(nz)

print(f"  Total cached: {n_total}")
print(f"  All-zero (failed): {n_all_zero} ({100*n_all_zero/n_total:.1f}%)")
print(f"  With features: {n_nonzero} ({100*n_nonzero/n_total:.1f}%)")
if nonzero_counts:
    print(f"  Nonzero per complex: mean={np.mean(nonzero_counts):.1f}, median={np.median(nonzero_counts):.0f}")

# Feature distributions
feat_vals = defaultdict(list)
for f in files:
    d = json.load(open(f))
    for k, v in d.items():
        feat_vals[k].append(v)

print()
print("=== FEATURE DISTRIBUTIONS (9 interaction features) ===")
for k in ["hbond_donor_count", "hbond_acceptor_count", "hydrophobic_contacts",
          "salt_bridges", "pi_stacking", "pi_cation", "metal_coordination",
          "close_contacts_4A", "close_contacts_6A"]:
    vals = np.array(feat_vals[k])
    nz = np.sum(vals > 0)
    print(f"  {k:25s}  mean={np.mean(vals):7.1f}  nonzero={int(nz):5d} ({100*nz/len(vals):5.1f}%)  max={np.max(vals):.0f}")

print()
print("=== FEATURES WITH ZERO SHAP ===")
zero_shap = [k for k, v in shap.items() if v == 0]
print(f"  {len(zero_shap)} features contribute NOTHING: {zero_shap}")

print()
print("=== DIAGNOSIS ===")
print()
print("1. MW DOMINANCE")
print(f"   mw SHAP = {shap['mw']:.3f} (next best = {sorted(shap.values(), reverse=True)[1]:.3f})")
print("   mw es >1.8x mas importante que cualquier otro feature.")
print("   Esto es un sesgo conocido de PDBbind: moleculas grandes -> mas contactos -> mayor afinidad")
print()
print("2. FEATURES 1D/2D REDUNDANTES")
print("   6 de 7 features 1D/2D tienen SHAP=0 (logp, tpsa, hbd, hba, rotbonds, qed)")
print("   XGBoost usa mw como proxy de todas. Las de mas no agregan info incremental.")
print()
print("3. GROUP B (VINA) = ZERO")
print("   4 features de Vina son siempre 0.0 porque entrenamos en cristales PDBbind, no re-docked.")
print("   20% de los features del modelo estan desperdiciados.")
print()
print("4. INTERACCIONES RARAS")
pi_nz = int(np.sum(np.array(feat_vals["pi_stacking"]) > 0))
salt_nz = int(np.sum(np.array(feat_vals["salt_bridges"]) > 0))
metal_nz = int(np.sum(np.array(feat_vals["metal_coordination"]) > 0))
print(f"   salt_bridges: solo {salt_nz} complejos ({100*salt_nz/n_total:.1f}%) -> SHAP=0")
print(f"   pi_stacking: {pi_nz} complejos ({100*pi_nz/n_total:.1f}%) -> SHAP bajo")
print(f"   metal_coord: {metal_nz} complejos ({100*metal_nz/n_total:.1f}%) -> SHAP bajo")
print()
print("5. ALTA VARIANZA ENTRE FOLDS")
print(f"   Fold Spearman range: {cv_a['spearman']['min']:.3f} - {cv_a['spearman']['max']:.3f}")
print(f"   Std = {cv_a['spearman']['std']:.3f} -> modelo inestable en diferentes subconjuntos")
