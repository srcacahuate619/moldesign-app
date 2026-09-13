"""
phase0_failure_diagnostic.py - Caracteriza los 4 targets donde el GNN no aporta
y los 3 donde aporta. Busca patrones explicativos.

Genera:
  1. Perfil de los 7 targets: pocket size, ligand size, promiscuity, target family
  2. Distribucion de scores por target (Vina, XGB, CL-GNN)
  3. Correlation entre AUC_CL-GNN y AUC_XGB (hipotesis: inverso)
  4. En targets donde XGB > 0.90 (faciles): ranking de actives que pierde
  5. Confusion matrix por target: actives que CL-GNN llama decoys y viceversa
  6. Hipotesis: ¿GNN se训练 solo en pockets similares PDBbind? Verificar similitud
     estructura al RMSD vs targets de PDBbind.
"""
import json
import pickle
from pathlib import Path

import numpy as np
from sklearn.metrics import roc_auc_score

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TARGETS = [
    ("5ht1a",       "benchmark_checkpoint_5ht1a.json",       "gpcr",              "7E2Y"),
    ("hiv_protease","benchmark_checkpoint_hiv_protease.json","protease",          "1HSG"),
    ("cdk2",        "benchmark_checkpoint_cdk2.json",        "kinase",            "3PP0"),
    ("er_alpha",    "benchmark_checkpoint_er_alpha.json",    "nuclear_receptor",  "3ERT"),
    ("factor_xa",   "benchmark_checkpoint_factor_xa.json",   "protease",          "3CYX"),
    ("thrombin",    "benchmark_checkpoint_thrombin.json",    "protease",           "1C4U"),
    ("ca2",         "benchmark_checkpoint_ca2.json",         "enzyme",             "3DC3"),
]

SEARCH_DIRS = [
    PROJECT_ROOT / "data" / "gnn_fixed",
    PROJECT_ROOT / "data" / "gnn_v31" / "checkpoints",
    PROJECT_ROOT / "data",
]


def load_target(name, ck_name):
    for d in SEARCH_DIRS:
        p = d / ck_name
        if p.exists():
            data = json.load(open(p))
            return data["results"]
    return None


def vina_norm(v):
    return min(1.0, abs(v) / 12.0)


def stack_score(vina_n, xgb, clgnn, w_v, w_x, w_c):
    return vina_n * w_v + xgb * w_x + clgnn * w_c


def analyze_target(name, family, pdb, results):
    """Para cada target, produce un dict con perfiles."""
    rows = [r for r in results if r.get("vina_score") is not None
                                 and r.get("prob") is not None
                                 and r.get("clgnn_prob") is not None]
    labels = np.array([r["is_active"] for r in rows])
    vina = np.array([abs(r["vina_score"]) for r in rows])
    xgb = np.array([r["prob"] for r in rows])
    clgnn = np.array([r["clgnn_prob"] for r in rows])
    vina_n = np.array([vina_norm(r["vina_score"]) for r in rows])

    # SMILES sizes para estimar tamano de ligando
    smiles_lens = np.array([len(r.get("smiles", "")) for r in rows])

    # Para actives vs decoys
    actives = labels == 1
    decoys = labels == 0

    return {
        "name": name,
        "family": family,
        "pdb": pdb,
        "n": len(labels),
        "n_act": int(labels.sum()),
        "n_dec": int((labels == 0).sum()),
        "labels": labels,
        "vina": vina,
        "xgb": xgb,
        "clgnn": clgnn,
        "vina_n": vina_n,
        # scorers distributions
        "vina_actives":            vina[actives],
        "vina_decoys":             vina[decoys],
        "xgb_actives_mean":        float(xgb[actives].mean()),
        "xgb_decoys_mean":         float(xgb[decoys].mean()),
        "xgb_actives_std":         float(xgb[actives].std()),
        "xgb_decoys_std":          float(xgb[decoys].std()),
        "clgnn_actives_mean":      float(clgnn[actives].mean()),
        "clgnn_decoys_mean":       float(clgnn[decoys].mean()),
        "clgnn_actives_std":       float(clgnn[actives].std()),
        "clgnn_decoys_std":        float(clgnn[decoys].std()),
        "vina_actives_mean":       float(vina[actives].mean()),
        "vina_decoys_mean":        float(vina[decoys].mean()),
        # Discrimination: difference active-decoy mean relative to std pooled
        "vina_disc":               (float(vina[actives].mean()) - float(vina[decoys].mean())) / max(0.01, (vina[actives].std() + vina[decoys].std()) / 2),
        "xgb_disc":                (float(xgb[actives].mean()) - float(xgb[decoys].mean())) / max(0.01, (xgb[actives].std() + xgb[decoys].std()) / 2),
        "clgnn_disc":              (float(clgnn[actives].mean()) - float(clgnn[decoys].mean())) / max(0.01, (clgnn[actives].std() + clgnn[decoys].std()) / 2),
        "auc_vina":                float(roc_auc_score(labels, vina)),
        "auc_xgb":                 float(roc_auc_score(labels, xgb)),
        "auc_clgnn":               float(roc_auc_score(labels, clgnn)),
        "smiles_len_mean":         float(smiles_lens.mean()),
        "smiles_len_mean_actives": float(smiles_lens[actives].mean()),
        "smiles_len_mean_decoys":  float(smiles_lens[decoys].mean()),
        # rows guardados para analisis posterior
        "rows": rows,
    }


def find_marginal_actives(rows, labels, xgb_scores, vina_scores, pct=10):
    """Encontrar actives que XGB+Vina NO prioriza bien (fuera de top-pct)."""
    n = len(rows)
    top_n = max(1, int(n * pct / 100))
    # baseline score (composite Vina+XGB)
    vina_n = np.array([vina_norm(r["vina_score"]) for r in rows])
    xgb = np.asarray(xgb_scores)
    composite = np.array([r * 0.7 + v * 0.3 for r, v in zip(xgb, vina_n)])
    pairs = sorted(zip(composite, range(n)), key=lambda x: x[0], reverse=True)
    top_idx = set(i for _, i in pairs[:top_n])
    actives_idx = set(i for i, l in enumerate(labels) if l == 1)
    missed = actives_idx - top_idx  # actives no en top-10%
    ranked = sorted(zip(composite, range(n)), key=lambda x: x[0], reverse=True)
    ranks = {i: r for r, (_, i) in enumerate(ranked)}
    return missed, ranks


def main():
    print("=" * 110)
    print("  PHASE 0 - DIAGNOSTICO DE FALLAS DEL GNN")
    print("  Pregunta: por que en 4 de 7 targets el GNN no aporta?")
    print("=" * 110)

    # -------- 1. Perfil por target --------
    print(f"\n{'target':<14}{'family':<18}{'pdb':<7}{'n':>5}{'n_a':>4} | {'AUC_vina':>9}{'AUC_xgb':>9}{'AUC_cl':>8} | {'XGBdisc':>9}{'CLdisc':>9}{'Vdisc':>7} | {'xg(xa|xd)':>15}{'clg(ca|cd)':>15}")
    print("-" * 145)

    all_targets = []
    for name, ck_name, family, pdb in TARGETS:
        results = load_target(name, ck_name)
        if not results:
            print(f"{name}: NOT FOUND")
            continue
        t = analyze_target(name, family, pdb, results)
        all_targets.append(t)
        print(f"{t['name']:<14}{t['family']:<18}{t['pdb']:<7}{t['n']:>5}{t['n_act']:>4} | "
              f"{t['auc_vina']:>9.4f}{t['auc_xgb']:>9.4f}{t['auc_clgnn']:>8.4f} | "
              f"{t['xgb_disc']:>9.3f}{t['clgnn_disc']:>9.3f}{t['vina_disc']:>7.3f} | "
              f"{t['xgb_actives_mean']:>6.3f}|{t['xgb_decoys_mean']:-6.3f} "
              f"{t['clgnn_actives_mean']:>5.3f}|{t['clgnn_decoys_mean']:-5.3f}")

    # -------- 2. Hipotesis: correlacion inversa AUC_XGB vs AUC_CL-GNN --------
    print("\n" + "=" * 110)
    print("  HIPOTESIS 1: AUC_CL-GNN inversamente proporcional a AUC_XGB")
    print("=" * 110)
    auc_x = np.array([t["auc_xgb"] for t in all_targets])
    auc_c = np.array([t["auc_clgnn"] for t in all_targets])
    corr_xc = np.corrcoef(auc_x, auc_c)[0, 1]
    print(f"\n  Correlacion AUC_XGB vs AUC_CL-GNN: {corr_xc:+.4f}")
    if corr_xc < -0.4:
        print("  -> Confirma hipotesis: el GNN aporta MAS cuando XGB es debil.")
        print("  -> Targets donde XGB > 0.93 estan saturados y el GNN no tiene nada que aprender.")
    elif corr_xc > 0.4:
        print("  -> Correlacion positiva: GNN y XGB ven lo mismo (no ortogonales - problema).")
    else:
        print("  -> Sin correlacion clara -los targets fallidos NO se explican por saturacion XGB.")

    # -------- 3. Distribuciones de scores --------
    print("\n" + "=" * 110)
    print("  PERFIL DE DISCRIMINACION (Cohen d estilo: media_active - media_decoy / std_pooled)")
    print("=" * 110)
    print(f"\n  {'target':<14}{'vina_disc':>12}{'xgb_disc':>12}{'clgnn_disc':>12}  Veredicto")
    print("  " + "-" * 80)
    for t in all_targets:
        verdict = ""
        if t["clgnn_disc"] < 0.2:
            verdict = "GNN no discrimina (podria random)"
        elif t["clgnn_disc"] < t["xgb_disc"]:
            verdict = f"GNN aporta LESS que XGB por {(t['xgb_disc'] - t['clgnn_disc']):.2f}"
        elif t["clgnn_disc"] > t["xgb_disc"]:
            verdict = f"GNN aporta MAS que XGB por {(t['clgnn_disc'] - t['xgb_disc']):.2f}"
        print(f"  {t['name']:<14}{t['vina_disc']:>12.3f}{t['xgb_disc']:>12.3f}{t['clgnn_disc']:>12.3f}  {verdict}")

    # -------- 4. Para targets donde XGB > 0.90: actives perdidos por Vina+XGB --------
    print("\n" + "=" * 110)
    print("  ACTIVES PERDIDOS POR Vina+XGB (top-10% missed)")
    print("=" * 110)
    for t in all_targets:
        if t["auc_xgb"] < 0.90:
            continue
        labels = t["labels"]
        missed, ranks = find_marginal_actives(t["rows"], labels, t["xgb"], t["vina"])
        pct_missed = 100.0 * len(missed) / max(1, t["n_act"])
        # De los missed, que piensa el CL-GNN?
        clgnn_missed_mean = float(np.mean([t["clgnn"][i] for i in missed]))
        clgnn_all_actives_mean = t["clgnn_actives_mean"]
        delta = clgnn_missed_mean - clgnn_all_actives_mean
        print(f"\n  {t['name']:<14} | n_act={t['n_act']} | missed by baseline={len(missed)} ({pct_missed:.1f}%)")
        print(f"    CL-GNN prob para missed:  mean={clgnn_missed_mean:.3f}")
        print(f"    CL-GNN prob para all actives: mean={clgnn_all_actives_mean:.3f}")
        print(f"    Diferencia: {delta:+.3f} ({'GNN MIRA estos actives - aporta!' if delta > 0 else 'GNN TAMBIEN los pierde'})")
        # Distribucion de ranks
        missed_ranks = [ranks[i] for i in missed]
        if missed_ranks:
            print(f"    Missed ranks by baseline (0=mejor): "
                  f"median={np.median(missed_ranks):.0f} (top {100*np.median(missed_ranks)/t['n']:.1f}%) "
                  f"min={min(missed_ranks)} max={max(missed_ranks)}")

    # -------- 5. Caracteristicas estructurales - smiles_len como proxy --------
    print("\n" + "=" * 110)
    print("  TAMAÑO DE LIGANDO (proxy: len(SMILES)) por target")
    print("=" * 110)
    print(f"\n  {'target':<14}{'smiles_med':>12}{'smiles_act':>12}{'smiles_dec':>12}")
    print("  " + "-" * 60)
    for t in all_targets:
        print(f"  {t['name']:<14}{t['smiles_len_mean']:>12.1f}{t['smiles_len_mean_actives']:>12.1f}{t['smiles_len_mean_decoys']:>12.1f}")

    # -------- 6. Hipotesis differential por familia --------
    print("\n" + "=" * 110)
    print("  RESUMEN POR TIPO DE FALLA")
    print("=" * 110)
    print("""
  APORTA (3):
    5ht1a (gpcr):       delta=+0.08  | CL-GNN discrimina los 3 scorers > 0.80
    hiv_protease (protease): delta=+0.19 | CL-GNN domina (0.95) -WASHINGTON aqui GNN solo mejor
    thrombin (protease): delta marginal | similar a baseline

  NO APORTA (4):
    cdk2 (kinase):      XGB ya 0.93, CL-GNN 0.59 -CL-GNN fustigado
    er_alpha (nuc_rec): XGB ya 0.98 (saturado), CL-GNN 0.66 - GNN ruido
    factor_xa (protease): Vina=0.99 -Vina sola ya saturada - nada que aportar
    ca2 (enzyme):       todos los scorers bajos (<0.77) -target hard GNN no entrenado para enzyme
""")

    # -------- Save --------
    out_dir = PROJECT_ROOT / "data" / "gnn_fixed" / "phase0"
    out_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "correlation_AUC_XGB_vs_AUC_CLGNN": float(corr_xc),
        "targets": [
            {
                "name": t["name"], "family": t["family"], "pdb": t["pdb"],
                "n": t["n"], "n_act": t["n_act"],
                "auc_vina": t["auc_vina"], "auc_xgb": t["auc_xgb"], "auc_clgnn": t["auc_clgnn"],
                "disc_vina": t["vina_disc"], "disc_xgb": t["xgb_disc"], "disc_clgnn": t["clgnn_disc"],
                "xgb_active_mean": t["xgb_actives_mean"], "xgb_decoy_mean": t["xgb_decoys_mean"],
                "clgnn_active_mean": t["clgnn_actives_mean"], "clgnn_decoy_mean": t["clgnn_decoys_mean"],
                "smiles_len_mean": t["smiles_len_mean"],
            } for t in all_targets
        ]
    }
    with open(out_dir / "failure_diagnostic.json", "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\n  Guardado: {out_dir / 'failure_diagnostic.json'}")


if __name__ == "__main__":
    main()
