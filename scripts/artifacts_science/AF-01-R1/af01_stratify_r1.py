#!/usr/bin/env python3
"""AF-01-R1 — corrigendum del estratificado por receptor de AF-01.

Corrige el bug de clasificación de af01_stratify.py (AF-01, sellada GO):
en la versión original `overlap == 1.0` se usaba como proxy de "secuencia
exacta". Eso es INCORRECTO: el coeficiente de solapamiento de k-meros
|A ∩ B| / min(|A|, |B|) con k=8 vale 1.0 también cuando los k-meros de una
cadena CORTA son subconjunto de los de una cadena larga (subsecuencia), no
solo cuando las secuencias son idénticas. Por esa razón 53 complejos del
holdout quedaron mal clasificados en receptor_seen_exact (debían estar en
receptor_near_identity).

Corrección: receptor_seen_exact = igualdad LITERAL de secuencia por par de
cadenas (seq_dev == seq_holdout), sin pasar por k-meros. El resto del método
queda idéntico (SEQRES por cadena, k=8, umbral 0.90 por solapamiento).

Los conteos canónicos (grupos de secuencia exacta cruzados, complejos
afectados, pares >= 0.90) ya usaban igualdad literal y NO cambian:
61 / 134 / 126 / 1600 / 2370.

Mismo método FND-05/FND-02 (k-meros k=8 sobre SEQRES por cadena; ver
scripts/build_confirm_cohort.py y scripts/artifacts_science/FND-05/DESIGN.md
§12):

  - Secuencias por cadena: SEQRES del PDB (fallback ATOM/CA documentado).
  - Similitud de un par de cadenas = coeficiente de solapamiento de k-meros
    |A ∩ B| / min(|A|, |B|) con k=8.
  - Similitud entre complejos = máximo sobre todos los pares de cadenas.
  - Estratos del holdout (contra TODAS las cadenas del pool de desarrollo):
      receptor_seen_exact      algún par de cadenas con secuencia literal
                               idéntica (seq_dev == seq_holdout)
      receptor_near_identity   0.90 <= solapamiento < 1.0 (o < 1.0 sin par
                               literal exacto)
      receptor_unrelated       solapamiento < 0.90

Solo lectura sobre data/pdbbind/{pid}/{pid}_protein.pdb. Determinista.
Dependencias: stdlib (json, hashlib, argparse). rdkit no es necesario.

Uso:
    python scripts/artifacts_science/AF-01-R1/af01_stratify_r1.py \
        --split rescoring/artifacts/split_config.json \
        --index data/pdbbind/INDEX_refined_data.2020.faseA_20260813_184439 \
        --pdbbind data/pdbbind \
        --predictions <workspace>/predictions_run.jsonl \
        --out scripts/artifacts_science/AF-01-R1

Escribe en --out: per_complex.jsonl, metrics_estratos.json y
estratos_report.txt (resumen legible).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

K_MER = 8
UMBRAL = 0.90

AA3_TO_1 = {
    "ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C",
    "GLN": "Q", "GLU": "E", "GLY": "G", "HIS": "H", "ILE": "I",
    "LEU": "L", "LYS": "K", "MET": "M", "PHE": "F", "PRO": "P",
    "SER": "S", "THR": "T", "TRP": "W", "TYR": "Y", "VAL": "V",
    "SEC": "U", "PYL": "O", "ASX": "B", "GLX": "Z", "UNK": "X",
}


def secuencias_pdb_texto(texto: str) -> dict[str, str]:
    """{cadena: secuencia} vía SEQRES; fallback ATOM/CA (método FND-05)."""
    lineas = texto.splitlines()
    seqres: dict[str, list[str]] = defaultdict(list)
    for l in lineas:
        if l.startswith("SEQRES"):
            cad = l[11:12].strip() or "?"
            for i in range(19, 70, 4):
                res = l[i:i + 3].strip()
                if res:
                    seqres[cad].append(AA3_TO_1.get(res, "X"))
    if seqres:
        return {c: "".join(seqres[c]) for c in sorted(seqres) if seqres[c]}
    por_cad: dict[str, dict[int, str]] = defaultdict(dict)
    for l in lineas:
        if l.startswith("ATOM") and l[12:16].strip() == "CA":
            cad = l[21:22].strip() or "?"
            try:
                num = int(l[22:26])
            except ValueError:
                continue
            por_cad[cad][num] = AA3_TO_1.get(l[17:20].strip(), "X")
    return {
        c: "".join(por_cad[c][n] for n in sorted(por_cad[c]))
        for c in sorted(por_cad) if por_cad[c]
    }


def kmers(seq: str, k: int = K_MER) -> set[str]:
    return {seq[i:i + k] for i in range(len(seq) - k + 1)}


def solapamiento(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def leer_pids(path: Path) -> list[str]:
    pids: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 6:
            pid = parts[0].lower()
            if pid not in pids:
                pids.append(pid)
    return pids


def cargar_cadenas(pdbbind: Path, pid: str) -> dict[str, str]:
    f = pdbbind / pid / f"{pid}_protein.pdb"
    if not f.exists():
        return {}
    return secuencias_pdb_texto(f.read_text(encoding="utf-8", errors="replace"))


def rankdata(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for t in range(i, j + 1):
            ranks[order[t]] = avg
        i = j + 1
    return ranks


def pearson(x: list[float], y: list[float]) -> float:
    n = len(x)
    mx = sum(x) / n
    my = sum(y) / n
    cov = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
    vx = sum((xi - mx) ** 2 for xi in x)
    vy = sum((yi - my) ** 2 for yi in y)
    if vx == 0.0 or vy == 0.0:
        return 0.0
    return cov / (vx * vy) ** 0.5


def spearman(x: list[float], y: list[float]) -> float:
    if len(x) < 2:
        return float("nan")
    return pearson(rankdata(x), rankdata(y))


def bootstrap_ci_spearman(
    x: list[float], y: list[float], n_iter: int = 10_000, seed: int = 42
) -> tuple[float, float]:
    """Bootstrap percentil 95% del Spearman (implementación propia, semilla fija)."""
    import random

    rng = random.Random(seed)
    n = len(x)
    stats = []
    for _ in range(n_iter):
        idx = [rng.randrange(n) for _ in range(n)]
        xs = [x[i] for i in idx]
        ys = [y[i] for i in idx]
        stats.append(spearman(xs, ys))
    stats.sort()
    lo = stats[int(n_iter * 0.025)]
    hi = stats[int(n_iter * 0.975)]
    return lo, hi


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--split", required=True)
    ap.add_argument("--index", required=True)
    ap.add_argument("--pdbbind", required=True)
    ap.add_argument("--predictions", default=None)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    split = json.loads(Path(args.split).read_text(encoding="utf-8"))
    holdout = [str(p).lower() for p in split["frozen_test_set"]]
    all_pids = leer_pids(Path(args.index))
    pool = [p for p in all_pids if p not in set(holdout)]
    pdbbind = Path(args.pdbbind)

    print(f"holdout: {len(holdout)}, pool: {len(pool)}, total: {len(all_pids)}")

    # Cadenas por complejo (secuencia -> dueños)
    dev_chains: dict[str, dict[str, str]] = {}
    hold_chains: dict[str, dict[str, str]] = {}
    n_fallback = 0
    for pid in pool:
        chains = cargar_cadenas(pdbbind, pid)
        dev_chains[pid] = chains
    for pid in holdout:
        chains = cargar_cadenas(pdbbind, pid)
        hold_chains[pid] = chains

    # Índice invertido de k-meros del desarrollo: kmer -> lista (pid, cad, kmers)
    km_index: dict[str, list[tuple[str, str, set[str]]]] = defaultdict(list)
    seq_owners_dev: dict[str, set[str]] = defaultdict(set)
    # CORRIGENDUM: índice de igualdad LITERAL de secuencia (fix del bug)
    # overlap == 1.0 también ocurre cuando los k-meros de una cadena corta
    # son subconjunto de los de otra (subsecuencia); visto exacto requiere
    # seq_dev == seq_holdout.
    exact_dev: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for pid, chains in dev_chains.items():
        for cad, seq in chains.items():
            ks = kmers(seq)
            for km in sorted(ks):
                km_index[km].append((pid, cad, ks))
            seq_owners_dev[seq].add(pid)
            exact_dev[seq].append((pid, cad))

    # Para cada complejo holdout: mejor par de cadenas vs desarrollo
    rows = []
    for pid in holdout:
        chains = hold_chains.get(pid, {})
        best = 0.0
        best_pair = None
        exact_pair = None
        if chains:
            for cad, seq in chains.items():
                # Fix del corrigendum: secuencia literal idéntica => visto exacto
                if exact_pair is None and seq in exact_dev:
                    exact_pair = (exact_dev[seq][0][0], exact_dev[seq][0][1], cad)
                ks = kmers(seq)
                seen: set[tuple[str, str]] = set()
                for km in sorted(ks):
                    for (dpid, dcad, dks) in km_index.get(km, ()):
                        if (dpid, dcad) in seen:
                            continue
                        seen.add((dpid, dcad))
                        o = solapamiento(ks, dks)
                        if o > best:
                            best = o
                            best_pair = (dpid, dcad, cad)
        if exact_pair is not None:
            estrato = "receptor_seen_exact"
            best = 1.0
            best_pair = exact_pair
        elif best >= UMBRAL:
            estrato = "receptor_near_identity"
        else:
            estrato = "receptor_unrelated"
        rows.append({
            "pid": pid,
            "stratum": estrato,
            "best_overlap": round(best, 6),
            "best_pair": best_pair,
        })

    # Grupos de secuencia exacta que cruzan desarrollo <-> holdout
    seq_owners_hold: dict[str, set[str]] = defaultdict(set)
    for pid, chains in hold_chains.items():
        for cad, seq in chains.items():
            seq_owners_hold[seq].add(pid)
    cross_seqs = sorted(
        seq for seq in seq_owners_dev if seq in seq_owners_hold
    )
    dev_affected = set()
    for seq in cross_seqs:
        dev_affected |= seq_owners_dev[seq]
    hold_affected = set()
    for seq in cross_seqs:
        hold_affected |= seq_owners_hold[seq]

    # Pares dev x holdout con algún par de cadenas >= 0.90 (nivel complejo)
    pares_complejos_ge90 = set()
    for pid in holdout:
        chains = hold_chains.get(pid, {})
        if not chains:
            continue
        for cad, seq in chains.items():
            ks = kmers(seq)
            seen: set[tuple[str, str]] = set()
            for km in sorted(ks):
                for (dpid, dcad, dks) in km_index.get(km, ()):
                    if (dpid, dcad) in seen:
                        continue
                    seen.add((dpid, dcad))
                    if solapamiento(ks, dks) >= UMBRAL:
                        pares_complejos_ge90.add((dpid, pid))

    # Pares de cadenas (dev x holdout) >= 0.90, deduplicados por par único
    chain_pairs_ge90 = set()
    for pid in holdout:
        chains = hold_chains.get(pid, {})
        if not chains:
            continue
        for cad, seq in chains.items():
            ks = kmers(seq)
            seen: set[tuple[str, str]] = set()
            for km in sorted(ks):
                for (dpid, dcad, dks) in km_index.get(km, ()):
                    if (dpid, dcad) in seen:
                        continue
                    seen.add((dpid, dcad))
                    if solapamiento(ks, dks) >= UMBRAL:
                        chain_pairs_ge90.add((dpid, dcad, pid, cad))

    # Estratos
    estratos = defaultdict(int)
    for r in rows:
        estratos[r["stratum"]] += 1

    # Merge con predicciones (si se proveen)
    preds = {}
    if args.predictions:
        for line in Path(args.predictions).read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            d = json.loads(line)
            preds[d["pid"].lower()] = (d["y_true"], d["y_pred"])

    spearman_estrato: dict[str, dict] = {}
    for estrato in ("receptor_seen_exact", "receptor_near_identity", "receptor_unrelated"):
        sub = [r for r in rows if r["stratum"] == estrato]
        out = {"n": len(sub)}
        with_pred = [r for r in sub if r["pid"] in preds]
        if len(with_pred) >= 2:
            xt = [preds[r["pid"]][0] for r in with_pred]
            xp = [preds[r["pid"]][1] for r in with_pred]
            rho = spearman(xt, xp)
            lo, hi = bootstrap_ci_spearman(xt, xp)
            out.update({
                "spearman": round(rho, 4),
                "spearman_ci95": [round(lo, 4), round(hi, 4)],
                "n_with_pred": len(with_pred),
            })
        spearman_estrato[estrato] = out

    metrics = {
        "metodo": "AF-01-R1 corrigendum: FND-05/FND-02 por cadena con fix de igualdad literal",
        "k_mer": K_MER,
        "umbral_cadena": UMBRAL,
        "n_holdout": len(holdout),
        "n_pool_dev": len(pool),
        "n_fallback_ca": n_fallback,
        "grupos_secuencia_exacta_cruzados": len(cross_seqs),
        "complejos_dev_afectados_exactos": len(dev_affected),
        "complejos_holdout_afectados_exactos": len(hold_affected),
        "pares_complejos_dev_holdout_ge90": len(pares_complejos_ge90),
        "pares_cadenas_dev_holdout_ge90": len(chain_pairs_ge90),
        "estratos": {
            estrato: spearman_estrato[estrato]
            for estrato in spearman_estrato
        },
    }

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    with open(out_dir / "metrics_estratos.json", "w", encoding="utf-8") as fh:
        json.dump(metrics, fh, indent=2, ensure_ascii=False)

    with open(out_dir / "per_complex.jsonl", "w", encoding="utf-8") as fh:
        for r in sorted(rows, key=lambda r: (r["stratum"], r["pid"])):
            rec = {"pid": r["pid"], "estrato_receptor": r["stratum"],
                   "best_overlap": r["best_overlap"]}
            if r["best_pair"]:
                rec["best_pair_dev_pid"] = r["best_pair"][0]
                rec["best_pair_dev_chain"] = r["best_pair"][1]
                rec["best_pair_holdout_chain"] = r["best_pair"][2]
            if r["pid"] in preds:
                rec["real"] = round(preds[r["pid"]][0], 6)
                rec["predicho"] = round(preds[r["pid"]][1], 6)
                rec["error"] = round(preds[r["pid"]][1] - preds[r["pid"]][0], 6)
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    with open(out_dir / "estratos_report.txt", "w", encoding="utf-8") as fh:
        fh.write("AF-01-R1 — solapamiento por receptor (fix igualdad literal, k-mers k=8, SEQRES por cadena)\n\n")
        fh.write(f"grupos de secuencia exacta que cruzan dev<->holdout: {len(cross_seqs)}\n")
        fh.write(f"complejos dev con cadena exacta compartida:   {len(dev_affected)}/{len(pool)}\n")
        fh.write(f"complejos holdout con cadena exacta compartida: {len(hold_affected)}/{len(holdout)}\n")
        fh.write(f"pares de complejos (dev x holdout) con cadena >=0.90: {len(pares_complejos_ge90)}\n")
        fh.write(f"pares de cadenas (dev x holdout) >=0.90: {len(chain_pairs_ge90)}\n\n")
        for estrato in ("receptor_seen_exact", "receptor_near_identity", "receptor_unrelated"):
            s = spearman_estrato[estrato]
            fh.write(f"{estrato}: n={s['n']}")
            if "spearman" in s:
                fh.write(f" spearman={s['spearman']} ci95={s['spearman_ci95']} (n_pred={s['n_with_pred']})")
            fh.write("\n")

    print(json.dumps(metrics, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
