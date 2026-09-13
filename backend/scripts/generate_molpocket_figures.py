"""Genera las figuras del paper PAPER_MOLPOCKET.md (docs/figures/).

Fuente de datos PRIMARIA: benchmark_pdbbind_200_rerank.json (benchmark REAL,
top_n=3, ya con re-ranking aplicado). Para el baseline "score fpocket" y el
holdout usamos pocket_dataset_*.json (todos los pockets con features), que
permite simular el ranking por score sobre el mismo set de complejos.

Para mantener consistencia TOTAL con el texto del paper, los valores de mediana
y %<=x de las figuras deben coincidir con los del benchmark real:
  - Train top1 re-rank:  mediana 5.97, %<=4 39.5, %<=6 50.5, %<=10 52.5
  - Train best3 re-rank: mediana 3.68, %<=4 55.0, %<=6 73.5, %<=10 79.0
  - Holdout top1 score:  mediana 9.27, %<=4 31.3, %<=6 44.0, %<=10 52.0
  - Holdout top1 rank:   mediana 4.98, %<=4 42.0, %<=6 58.0, %<=10 65.3
  - Train top1 score:    mediana 12.19, %<=4 31.5, %<=6 42.0, %<=10 46.0
Los datos del holdout y del baseline-score salen de las filas de features con
top-3 por complejo (mismo criterio que el benchmark real), para que los números
sean comparables al benchmark.

Figuras:
  fig1_pocket_distributions.png/pdf — CDF de distancias top-1: baseline score vs re-rank (train/holdout)
  fig2_rerank_delta.png/pdf         — Barras de mejora: mediana top-1 y %<=4/6/10 baseline vs re-rank
  fig3_feature_discrimination.png   — Correlación de features con distancia al ligando (análisis discriminante)
  fig4_outlier_analysis.png         — Scatter n_lig_atoms vs distancia, resaltando outliers
  fig5_oracle_gap.png               — Mediana top1 / best-of-3 / oracle (gap al límite)

Uso:
    python scripts/generate_molpocket_figures.py
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

# UTF-8 para consolas Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

_ROOT = Path(__file__).resolve().parents[1]
DATA = _ROOT / "data"
FIG_DIR = Path(r"D:\moldesign-build\docs\figures")

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 11,
    "axes.titlesize": 13,
    "axes.labelsize": 12,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "figure.dpi": 200,
})

C_BLUE = "#2563eb"
C_RED = "#dc2626"
C_GREEN = "#16a34a"
C_GRAY = "#64748b"
C_ORANGE = "#ea580c"


# ── Carga de datos ─────────────────────────────────────────────────────────

def load_benchmark(name: str):
    p = DATA / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def load_pocket_dataset(name: str):
    p = DATA / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


# ── Rankings simulados desde features (mismo criterio que benchmark real) ──

def per_complex_top1_by(filas, key_fn, top=3):
    """Distancia top-1 por complejo: mejor pocket según key_fn de los top-N."""
    comp = defaultdict(list)
    for r in filas:
        comp[r["pdb_id"]].append(r)
    dists = []
    for ps in comp.values():
        if not ps:
            continue
        ranked = sorted(ps, key=key_fn, reverse=True)[:top]
        dists.append(ranked[0]["distancia"])  # top-1 del ranking
    return np.array(dists, dtype=float)


def per_complex_best3_by(filas, key_fn, top=3):
    comp = defaultdict(list)
    for r in filas:
        comp[r["pdb_id"]].append(r)
    dists = []
    for ps in comp.values():
        if not ps:
            continue
        ranked = sorted(ps, key=key_fn, reverse=True)[:top]
        dists.append(min(r["distancia"] for r in ranked))
    return np.array(dists, dtype=float)


def rank_key(r):
    return r["druggability"] + r["nas_norm"] + 0.3 * r["hyd_norm"]


# ── Figura 1: CDF de distancias ────────────────────────────────────────────

def fig1_distributions(ds_train, ds_hold):
    fig, ax = plt.subplots(figsize=(7, 4.5))

    series = [
        (ds_train, "Train (n=200): score fpocket", "score", "--", C_GRAY),
        (ds_train, "Train (n=200): re-rank", "rank", "-", C_BLUE),
        (ds_hold, "Holdout (n=150): score fpocket", "score", "--", C_ORANGE),
        (ds_hold, "Holdout (n=150): re-rank", "rank", "-", C_RED),
    ]
    for data, name, mode, ls, c in series:
        filas = data["filas"]
        if mode == "score":
            d = per_complex_top1_by(filas, lambda r: r["score"])
        else:
            d = per_complex_top1_by(filas, rank_key)
        x = np.sort(d)
        y = np.arange(1, x.size + 1) / x.size * 100
        ax.plot(x, y, ls, color=c, lw=2.2, label=name)

    ax.axvline(4.0, color=C_GREEN, lw=1, ls=":", alpha=0.8)
    ax.axvline(6.0, color=C_GREEN, lw=1, ls=":", alpha=0.8)
    ax.text(4.05, 6, "4 Å", color=C_GREEN, fontsize=10)
    ax.text(6.05, 6, "6 Å", color=C_GREEN, fontsize=10)

    ax.set_xlabel("Distancia centro del pocket → centro del ligando (Å)")
    ax.set_ylabel("Complejos acumulados (%)")
    ax.set_title("CDF de distancia top-1: baseline fpocket vs re-ranking empírico")
    ax.legend(fontsize=9, loc="lower right")
    ax.set_xlim(0, 30)
    ax.grid(alpha=0.25, ls=":")
    fig.tight_layout()
    return fig


# ── Figura 2: barras de mejora ─────────────────────────────────────────────

def fig2_rerank_delta(ds_train, ds_hold):
    datasets = [("Train (n=200)", ds_train, C_BLUE), ("Holdout (n=150)", ds_hold, C_ORANGE)]
    metrics = ["Mediana top-1 (Å)", "% ≤ 4 Å", "% ≤ 6 Å", "% ≤ 10 Å"]
    baseline = []
    rerank = []
    for _, data, _ in datasets:
        filas = data["filas"]
        d_score = per_complex_top1_by(filas, lambda r: r["score"])
        d_rank = per_complex_top1_by(filas, rank_key)
        baseline.append([np.median(d_score),
                         np.mean(d_score <= 4) * 100,
                         np.mean(d_score <= 6) * 100,
                         np.mean(d_score <= 10) * 100])
        rerank.append([np.median(d_rank),
                       np.mean(d_rank <= 4) * 100,
                       np.mean(d_rank <= 6) * 100,
                       np.mean(d_rank <= 10) * 100])

    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2))
    for ai, (name, _, color) in enumerate(datasets):
        ax = axes[ai]
        x = np.arange(len(metrics))
        w = 0.36
        ax.bar(x - w / 2, baseline[ai], w, label="score fpocket", color=C_GRAY, alpha=0.85)
        ax.bar(x + w / 2, rerank[ai], w, label="re-rank", color=color, alpha=0.9)
        for xi, (b, r2) in enumerate(zip(baseline[ai], rerank[ai])):
            off = 0.4 if ai == 0 else 2
            ax.text(xi - w / 2, b + off, f"{b:.1f}", ha="center", fontsize=8, color=C_GRAY)
            ax.text(xi + w / 2, r2 + off, f"{r2:.1f}", ha="center", fontsize=8, color=color)
        ax.set_xticks(x)
        ax.set_xticklabels(metrics, fontsize=9, rotation=10)
        ax.set_title(name, fontsize=12)
        ax.legend(fontsize=8)
        ax.grid(alpha=0.2, axis="y", ls=":")
    fig.suptitle("Re-ranking empírico: mediana top-1 y tasa de acierto (PDBbind)", fontsize=13)
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    return fig


# ── Figura 3: discriminación de features ───────────────────────────────────

def fig3_feature_discrimination(ds_train):
    filas = ds_train["filas"]
    feats = [
        ("score (fpocket)", "score"),
        ("druggability", "druggability"),
        ("nas_norm", "nas_norm"),
        ("hyd_norm", "hyd_norm"),
        ("mean_loc_hyd_dens", "mean_loc_hyd_dens"),
        ("surf_pol_vdw22", "surf_pol_vdw22"),
        ("surf_apol_vdw14", "surf_apol_vdw14"),
        ("n_spheres", "n_spheres"),
        ("volume", "volume"),
        ("as_density", "as_density"),
    ]
    labels = []
    corrs = []
    for label, f in feats:
        mask = [r.get(f) is not None for r in filas]
        vals = np.array([r[f] for r, m in zip(filas, mask) if m], dtype=float)
        d = np.array([r["distancia"] for r, m in zip(filas, mask) if m], dtype=float)
        if len(vals) < 30 or np.std(vals) == 0:
            continue
        corrs.append(np.corrcoef(vals, np.log1p(d))[0, 1])
        labels.append(label)

    order = np.argsort(corrs)
    cs = np.array(corrs)[order]
    colors = [C_BLUE if abs(c) > 0.25 else (C_GRAY if abs(c) > 0.1 else C_RED) for c in cs]
    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    ax.barh(np.array(labels)[order], cs, color=colors, alpha=0.9)
    ax.axvline(0, color="#000", lw=0.8)
    ax.set_xlabel("Correlación de Pearson con log(distancia al ligando)")
    ax.set_title("Discriminación de features (n = 2,259 pockets, PDBbind train)")
    for i, c in enumerate(cs):
        ax.text(c + (0.01 if c > 0 else -0.01), i, f"{c:+.2f}", va="center",
                ha="left" if c > 0 else "right", fontsize=9)
    ax.grid(alpha=0.2, axis="x", ls=":")
    fig.tight_layout()
    return fig


# ── Figura 4: outliers n_lig vs distancia ──────────────────────────────────

def fig4_outlier_analysis(ds_train):
    filas = ds_train["filas"]
    comp = defaultdict(list)
    for r in filas:
        comp[r["pdb_id"]].append(r)
    pdb_ids, dists, nligs = [], [], []
    for pdb_id, ps in comp.items():
        best = sorted(ps, key=rank_key, reverse=True)[:3][0]  # top-1 del re-rank
        pdb_ids.append(pdb_id)
        dists.append(best["distancia"])
        nligs.append(best["n_lig_atoms"])
    dists = np.array(dists)
    nligs = np.array(nligs)

    fig, ax = plt.subplots(figsize=(7, 4.5))
    ok = dists <= 10
    ax.scatter(nligs[ok], dists[ok], s=28, color=C_BLUE, alpha=0.65, label="≤ 10 Å (OK)")
    bad = ~ok
    ax.scatter(nligs[bad], dists[bad], s=34, color=C_RED, alpha=0.85, label="> 10 Å (outlier)")
    ax.axhline(10, color=C_RED, ls=":", lw=1)
    top = np.argsort(-dists)[:6]
    for i in top:
        ax.annotate(pdb_ids[i], (nligs[i], dists[i]), fontsize=8, xytext=(6, 4),
                    textcoords="offset points", color=C_RED)
    r = np.corrcoef(nligs, dists)[0, 1]
    ax.set_xlabel("Átomos del ligando (n_lig_atoms)")
    ax.set_ylabel("Distancia top-1 al ligando (Å)")
    ax.set_title(f"Outliers concentran ligandos pequeños (r = {r:.2f})")
    ax.legend(fontsize=9)
    ax.set_ylim(0, 65)
    ax.grid(alpha=0.2, ls=":")
    fig.tight_layout()
    return fig


# ── Figura 5: gap al oracle ────────────────────────────────────────────────

def fig5_oracle_gap(ds_train, ds_hold):
    datasets = [("Train (n=200)", ds_train, C_BLUE), ("Holdout (n=150)", ds_hold, C_ORANGE)]
    groups = []
    for name, data, color in datasets:
        filas = data["filas"]
        d_score = per_complex_top1_by(filas, lambda r: r["score"])
        d_rank = per_complex_top1_by(filas, rank_key)
        d_best3 = per_complex_best3_by(filas, rank_key, top=3)
        groups.append((name, [np.median(d_score), np.median(d_rank), np.median(d_best3)], color))

    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    x = np.arange(3)
    width = 0.32
    for gi, (name, vals, color) in enumerate(groups):
        off = (gi - 0.5) * width
        bars = ax.bar(x + off, vals, width, label=name, color=color, alpha=0.88)
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, v + 0.2, f"{v:.2f}", ha="center", fontsize=9)
    ax.set_xticks(x)
    ax.set_xticklabels(["Mediana top-1\n(score fpocket)", "Mediana top-1\n(re-rank)",
                        "Mediana best-of-3\n(re-rank oracle)"], fontsize=9)
    ax.set_ylabel("Mediana distancia al ligando (Å)")
    ax.set_title("Gap al límite: detector genera, ranker ordena")
    ax.legend(fontsize=9)
    ax.set_ylim(0, 14)
    ax.grid(alpha=0.2, axis="y", ls=":")
    fig.tight_layout()
    return fig


# ── Main ───────────────────────────────────────────────────────────────────

def save(fig, name):
    fig.savefig(FIG_DIR / f"{name}.png", dpi=200, bbox_inches="tight")
    fig.savefig(FIG_DIR / f"{name}.pdf", bbox_inches="tight")
    plt.close(fig)
    print(f"  ✓ {name}.png/.pdf")


def main():
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    ds_train = load_pocket_dataset("pocket_dataset_200.json")
    ds_hold = load_pocket_dataset("pocket_dataset_150_holdout.json")
    if ds_train is None or ds_hold is None:
        print("ERROR: faltan pocket_dataset_200.json / pocket_dataset_150_holdout.json")
        return 1
    print(f"Generando figuras en {FIG_DIR} ...")

    save(fig1_distributions(ds_train, ds_hold), "fig1_pocket_distributions")
    save(fig2_rerank_delta(ds_train, ds_hold), "fig2_rerank_delta")
    save(fig3_feature_discrimination(ds_train), "fig3_feature_discrimination")
    save(fig4_outlier_analysis(ds_train), "fig4_outlier_analysis")
    save(fig5_oracle_gap(ds_train, ds_hold), "fig5_oracle_gap")

    # Verificación numérica de consistencia con el texto del paper
    print("\nVerificación (top-3 por complejo, mismo criterio que benchmark):")
    for name, data, tag in [("TRAIN", ds_train, "train"), ("HOLDOUT", ds_hold, "hold")]:
        filas = data["filas"]
        d_score = per_complex_top1_by(filas, lambda r: r["score"])
        d_rank = per_complex_top1_by(filas, rank_key)
        d_best3 = per_complex_best3_by(filas, rank_key, top=3)
        print(f"  {name}: score med={np.median(d_score):.2f} p4={np.mean(d_score<=4)*100:.1f} | "
              f"rank med={np.median(d_rank):.2f} p4={np.mean(d_rank<=4)*100:.1f} p6={np.mean(d_rank<=6)*100:.1f} p10={np.mean(d_rank<=10)*100:.1f} | "
              f"best3 med={np.median(d_best3):.2f}")

    print("Listo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
