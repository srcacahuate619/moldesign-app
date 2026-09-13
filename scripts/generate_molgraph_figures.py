"""
scripts/generate_molgraph_figures.py -- Generate all 6 figures for the MolGraph paper.

Scientific validity > quality > efficiency.
Uses ONLY verified numbers from the live DB (verified 2026-08-02) and the
v2 verify reports. No invented numbers.

Figures:
  1. fig1_schema_evolution  - mol_nodes schema v1 -> v2 (conceptual diagram)
  2. fig2_score_distribution - canonical score bucket histogram (post-C1 fix)
  3. fig3_early_exit         - early-exit decisions before vs after C1 fix
  4. fig4_fts_consistency    - FTS5 drift eliminated (before vs after v2)
  5. fig5_test_coverage      - test suite / coverage growth (0 -> 37, 0% -> 56%)
  6. fig6_score_key_gap      - score-key normalization closed by the C1 fix

Each figure is saved as PNG (dpi=200) AND PDF in docs/figures/.
Windows-safe: matplotlib Agg backend; cp1252-safe console output (ASCII only).
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

PROJECT = Path(__file__).resolve().parent.parent
OUT_DIR = PROJECT / "docs" / "figures"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Style ──
plt.rcParams.update({
    "font.family": "serif",
    "font.size": 11,
    "axes.titlesize": 13,
    "axes.labelsize": 12,
    "figure.dpi": 150,
    "savefig.dpi": 200,
    "savefig.bbox": "tight",
    "axes.grid": True,
    "grid.alpha": 0.25,
    "axes.axisbelow": True,
})

# Palette
C_RED = "#e74c3c"      # cold_start / before / failure
C_BLUE = "#3498db"     # variance / after / success
C_GREEN = "#2ecc71"    # skip / good
C_BLACK = "#2c3e50"    # errors / neutral
C_GREY = "#95a5a6"     # before state
C_ORANGE = "#e67e22"


def _save(fig, name: str) -> None:
    fig.savefig(OUT_DIR / f"fig{name}.png", dpi=200)
    fig.savefig(OUT_DIR / f"fig{name}.pdf")
    plt.close(fig)
    print(f"[OK] fig{name}.png / fig{name}.pdf")


# ═══════════════════════════════════════════════════════
# Figure 1: Schema Evolution v1 -> v2 (conceptual diagram)
# ═══════════════════════════════════════════════════════

def fig1_schema_evolution():
    fig, ax = plt.subplots(figsize=(13, 6.5))
    ax.axis("off")

    v1_cols = ["id  (TEXT PK)", "type  (TEXT)", "name  (TEXT)",
               "smiles  (TEXT)", "target_pdb  (TEXT)",
               "properties_json  (TEXT)", "created_at  (REAL)"]
    v2_new = ["is_catalog  (INTEGER DEFAULT 0)",
              "common_name  (TEXT NULL)",
              "aliases_json  (TEXT NULL)"]

    box_w, box_h = 0.30, 0.68
    box_y = 0.30
    left_x = 0.10
    right_x = 0.58
    row_h = box_h / 8.0

    def draw_table(x0, title, cols, new_cols, facecolor):
        ax.add_patch(plt.Rectangle((x0, box_y), box_w, box_h,
                                   facecolor=facecolor, edgecolor="black",
                                   linewidth=1.2, zorder=2))
        ax.text(x0 + box_w / 2, box_y + box_h + 0.035, title,
                ha="center", va="bottom", fontsize=13, fontweight="bold")
        y = box_y + box_h - 0.045
        for i, c in enumerate(cols):
            if c in new_cols:
                ax.add_patch(plt.Rectangle((x0 + 0.012, y - 0.028), box_w - 0.024, 0.040,
                                           facecolor="#d4efdf", edgecolor="none", zorder=3))
            ax.text(x0 + box_w / 2, y, c, ha="center", va="center",
                    fontsize=8.5, family="monospace", zorder=4)
            y -= row_h

    draw_table(left_x, "mol_nodes  v1", v1_cols, [], "#f2f3f4")
    v2_all = v1_cols + v2_new
    draw_table(right_x, "mol_nodes  v2", v2_all, v2_new, "#ebf5fb")

    # Notes
    note1 = "user_version = 0\nno triggers\nFTS: manual sync\npickle fingerprints\nLIMIT 200"
    note2 = ("user_version = 2\n3 FTS5 triggers\n"
             "(ai / au / ad)\ncache invalidation\nglobal top-N")
    ax.text(left_x + box_w / 2, 0.13, note1, ha="center", va="center",
            fontsize=9.5, bbox=dict(boxstyle="round,pad=0.45",
                                    facecolor="#fdf3e7", edgecolor=C_ORANGE))
    ax.text(right_x + box_w / 2, 0.13, note2, ha="center", va="center",
            fontsize=9.5, bbox=dict(boxstyle="round,pad=0.45",
                                    facecolor="#e8f8f5", edgecolor=C_GREEN))

    # Arrow: migration
    ax.annotate("", xy=(right_x - 0.012, box_y + box_h / 2),
                xytext=(left_x + box_w + 0.012, box_y + box_h / 2),
                arrowprops=dict(arrowstyle="-|>", color=C_BLACK, lw=2))
    ax.text((left_x + box_w + right_x) / 2, box_y + box_h / 2 + 0.05,
            "_migrate_schema()\nidempotent + backup", ha="center", va="bottom",
            fontsize=9.5, fontweight="bold", color=C_BLACK)

    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_title("MolGraph schema evolution: mol_nodes v1 -> v2", fontsize=14, pad=15)
    _save(fig, "1_schema_evolution")


# ═══════════════════════════════════════════════════════
# Figure 2: Canonical Score Distribution (post-fix)
# ═══════════════════════════════════════════════════════

def fig2_score_distribution():
    fig, ax = plt.subplots(figsize=(9, 5.5))

    ranges = ["40-49", "50-59", "60-69", "70-79"]
    counts = [1133, 1470, 24, 1]
    colors = [C_BLUE, C_BLUE, C_BLUE, C_BLUE]

    bars = ax.bar(ranges, counts, color=colors, edgecolor="white", linewidth=0.8,
                  width=0.62)
    for bar, c in zip(bars, counts):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 20,
                f"{c}", ha="center", fontsize=11, fontweight="bold")

    median_x = (50.3 - 40) / 10.0   # score -> bucket coordinate
    ax.axvline(x=median_x, color=C_RED, linestyle="--", linewidth=1.8)
    ax.text(median_x, 1450, "median = 50.3", color=C_RED, fontsize=11,
            fontweight="bold", ha="center")

    ax.set_xlabel("Canonical score range [0, 100]")
    ax.set_ylabel("Number of molecules")
    ax.set_title("Canonical score distribution (n = 2628 scored molecules)")

    ax.text(0.985, 0.955, "scale [0,100]\nn = 2628\nrange [44.07, 74.67]",
            transform=ax.transAxes, ha="right", va="top", fontsize=9.5,
            bbox=dict(boxstyle="round", facecolor="white", edgecolor=C_GREY, alpha=0.9))
    ax.set_ylim(0, 1700)
    _save(fig, "2_score_distribution")


# ═══════════════════════════════════════════════════════
# Figure 3: Early-Exit Decisions: Before vs After C1 Fix
# ═══════════════════════════════════════════════════════

def fig3_early_exit():
    fig, ax = plt.subplots(figsize=(9.5, 5.5))

    cats = ["cold_start", "variance", "skip", "errors"]
    colors = [C_RED, C_BLUE, C_GREEN, C_BLACK]
    before = [300, 0, 0, 0]
    after = [92, 208, 0, 0]

    x = np.arange(len(cats))
    width = 0.35

    b1 = ax.bar(x - width / 2, before, width, label="Before C1 fix",
                color=C_GREY, edgecolor="white", linewidth=0.7)
    b2 = ax.bar(x + width / 2, after, width, label="After C1 fix",
                color=colors, edgecolor="white", linewidth=0.7)

    for bars, vals in ((b1, before), (b2, after)):
        for bar, v in zip(bars, vals):
            if v > 0:
                ax.text(bar.get_x() + bar.get_width() / 2, v + 6,
                        f"{v}", ha="center", fontsize=10.5, fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels(cats)
    ax.set_ylabel("Molecules (decisions)")
    ax.set_title("Early-exit decision distribution (n = 300 molecule sample)")
    ax.legend(fontsize=10)
    ax.set_ylim(0, 340)

    ax.text(0.985, 0.955, "Before: cold_start 300/300\n(feature-dead early exit)\n"
                          "After: 92 cold_start + 208 variance\n0 skip, 0 errors",
            transform=ax.transAxes, ha="right", va="top", fontsize=9.5,
            bbox=dict(boxstyle="round", facecolor="white", edgecolor=C_GREY, alpha=0.9))
    _save(fig, "3_early_exit")


# ═══════════════════════════════════════════════════════
# Figure 4: FTS5 Consistency: Drift Eliminated
# ═══════════════════════════════════════════════════════

def fig4_fts_consistency():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    # LEFT: BEFORE (log scale)
    cats1 = ["missing rows", "mismatches"]
    vals1 = [5324, 34]
    bars1 = ax1.bar(cats1, vals1, color=[C_RED, C_ORANGE],
                    edgecolor="white", linewidth=0.7, width=0.55)
    ax1.set_yscale("log")
    for bar, v in zip(bars1, vals1):
        ax1.text(bar.get_x() + bar.get_width() / 2, v * 1.15, f"{v}",
                 ha="center", fontsize=11, fontweight="bold")
    ax1.set_ylim(1, 20000)
    ax1.set_title("v1 (before v2): FTS5 drift")
    ax1.set_ylabel("Rows (log scale)")

    # RIGHT: AFTER
    cats2 = ["orphans", "ghosts", "name\nmismatch", "props\nmismatch"]
    vals2 = [0, 0, 0, 0]
    bars2 = ax2.bar(cats2, vals2, color=C_GREEN, edgecolor="white", linewidth=0.7,
                    width=0.55)
    for bar in bars2:
        ax2.text(bar.get_x() + bar.get_width() / 2, 1.2, "0",
                 ha="center", fontsize=11, fontweight="bold", color=C_GREEN)
    ax2.set_ylim(0, 2)
    ax2.set_title("v2 (after): drift structurally impossible")
    ax2.set_ylabel("Count")
    ax2.text(0.5, -0.32, "total FTS5 rows = 7,996 (equals node count)",
             transform=ax2.transAxes, ha="center", fontsize=10.5,
             fontweight="bold", color=C_BLACK)

    fig.suptitle("FTS5 consistency: drift eliminated by v2 triggers", fontsize=14, y=1.02)
    fig.tight_layout()
    _save(fig, "4_fts_consistency")


# ═══════════════════════════════════════════════════════
# Figure 5: Test Coverage Growth
# ═══════════════════════════════════════════════════════

def fig5_test_coverage():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    # Tests
    cats = ["Before", "After"]
    tests = [0, 37]
    coverage = [0, 56]

    bars1 = ax1.bar(cats, tests, color=[C_GREY, C_BLUE],
                    edgecolor="white", linewidth=0.7, width=0.5)
    for bar, v in zip(bars1, tests):
        ax1.text(bar.get_x() + bar.get_width() / 2, v + 1, f"{v}",
                 ha="center", fontsize=11, fontweight="bold")
    ax1.set_title("Test suite size")
    ax1.set_ylabel("Number of tests")
    ax1.set_ylim(0, 45)

    # Coverage (%)
    bars2 = ax2.bar(cats, coverage, color=[C_GREY, C_GREEN],
                    edgecolor="white", linewidth=0.7, width=0.5)
    for bar, v in zip(bars2, coverage):
        ax2.text(bar.get_x() + bar.get_width() / 2, v + 1.5, f"{v}%",
                 ha="center", fontsize=11, fontweight="bold")
    ax2.set_title("Statement coverage")
    ax2.set_ylabel("Coverage (%)")
    ax2.set_ylim(0, 65)

    fig.suptitle("MolGraph test suite growth (v1 -> v2)", fontsize=14, y=1.02)
    fig.tight_layout()
    _save(fig, "5_test_coverage")


# ═══════════════════════════════════════════════════════
# Figure 6: The Score-Key Gap Closed (C1 fix)
# ═══════════════════════════════════════════════════════

def fig6_score_key_gap():
    fig, ax = plt.subplots(figsize=(9, 5.5))

    cats = ["Before C1 fix", "After C1 fix"]
    scored = [5, 2628]
    legacy = [2628, 0]

    x = np.arange(len(cats))
    width = 0.35

    b1 = ax.bar(x - width / 2, scored, width, label="with canonical score",
                color=C_BLUE, edgecolor="white", linewidth=0.7)
    b2 = ax.bar(x + width / 2, legacy, width, label="legacy-without-score",
                color=C_RED, edgecolor="white", linewidth=0.7)

    for bars, vals in ((b1, scored), (b2, legacy)):
        for bar, v in zip(bars, vals):
            if v > 0:
                ax.text(bar.get_x() + bar.get_width() / 2, v + 40,
                        f"{v}", ha="center", fontsize=10.5, fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels(cats)
    ax.set_ylabel("Molecules")
    ax.set_title("Canonical score-key coverage (n = 2633 molecules)")
    ax.legend(fontsize=10)
    ax.set_ylim(0, 3000)

    ax.text(0.985, 0.955, "After: 2628 / 2633 scored\n= 99.8%\nlegacy-without-score = 0",
            transform=ax.transAxes, ha="right", va="top", fontsize=10,
            fontweight="bold", color=C_BLUE,
            bbox=dict(boxstyle="round", facecolor="white", edgecolor=C_GREY, alpha=0.9))
    _save(fig, "6_score_key_gap")


# ═══════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════

if __name__ == "__main__":
    print("Generating MolGraph paper figures...")
    print(f"Output: {OUT_DIR}")
    fig1_schema_evolution()
    fig2_score_distribution()
    fig3_early_exit()
    fig4_fts_consistency()
    fig5_test_coverage()
    fig6_score_key_gap()
    print("\nAll 6 figures saved to", OUT_DIR)
    print("Files: fig1_schema_evolution.{png,pdf}, fig2_score_distribution.{png,pdf}, "
          "fig3_early_exit.{png,pdf}, fig4_fts_consistency.{png,pdf}, "
          "fig5_test_coverage.{png,pdf}, fig6_score_key_gap.{png,pdf}")
