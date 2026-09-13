#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""merge_rs03_param_b.py — Fusiona los shards de RS-03-PARAM-B en el artefacto final.

Contexto (incidencia 2026-08-17): la primera ejecución de B escribió en
`scripts/artifacts_science/RS-03-PARAM-B/` y una re-ejecución parcial posterior
(14 pids con timeout 1200 s) escribió en **el mismo directorio**, destruyendo los
102 resultados originales tanto en el servidor como en la copia local. Para no
repetir el fallo, B se recalculó completo (116/116) en **3 shards disjuntos**,
cada uno con su propio directorio de salida (`--out-name`), y este script hace la
unión. Ningún shard puede sobreescribir a otro.

Uso (Windows, tras descargar los artefactos remotos de cada shard):
  python -X utf8 scripts/merge_rs03_param_b.py

Inputs:
  scripts/artifacts_science/RS-03-PARAM-B-S{1,2,3}/{per_complex,failures}.jsonl
  scripts/artifacts_science/RS-03-PARAM-B-S{1,2,3}/metrics.json  (procedencia)

Output:
  scripts/artifacts_science/RS-03-PARAM-B/{per_complex,failures}.jsonl, metrics.json

Reglas de fusión:
  - Los shards son **disjuntos por construcción**: un pid repetido entre shards
    es un error y aborta la fusión (nunca se elige silenciosamente un ganador).
  - La cohorte debe cerrar exactamente en los 116 pids PASS de RS-03-PARAM-A:
    PASS + FAIL == 116, sin pids ausentes ni extraños.
  - metrics.json se recalcula sobre la unión; no se copia el de ningún shard.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ART = PROJECT_ROOT / "scripts" / "artifacts_science"
B_DIR = ART / "RS-03-PARAM-B"
SHARD_DIRS = [ART / f"RS-03-PARAM-B-S{i}" for i in (1, 2, 3)]
# Shard de reintento: los ligandos que agotaron el timeout de 1200 s bajo la
# contención de los 3 shards simultáneos, repetidos en solitario con 2400 s. Un
# PASS aquí sustituye al FAIL por timeout del shard original; nunca al revés, y
# nunca sustituye un PASS ya existente.
RETRY_DIR = ART / "RS-03-PARAM-B-S4"
A_PER_COMPLEX = ART / "RS-03-PARAM-A" / "per_complex.jsonl"


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _acc_strata(stats: Dict[str, Any], key: str, value: str, dq_mean: float, dq_max: float):
    bucket = stats.setdefault(key, {}).setdefault(
        value, {"n": 0, "sum_abs_dq": 0.0, "max_abs_dq": 0.0})
    bucket["n"] += 1
    bucket["sum_abs_dq"] += dq_mean
    bucket["max_abs_dq"] = max(bucket["max_abs_dq"], dq_max)


def main() -> int:
    cohorte = sorted(
        r["pid"] for r in load_jsonl(A_PER_COMPLEX) if r.get("status") == "PASS"
    )
    if len(cohorte) != 116:
        print(f"[!] Cohorte de A inesperada: {len(cohorte)} (se esperaban 116). Abortando.")
        return 2

    rows: Dict[str, Dict[str, Any]] = {}
    fails: Dict[str, Dict[str, Any]] = {}
    shard_meta: List[Dict[str, Any]] = []

    for d in SHARD_DIRS:
        pc = load_jsonl(d / "per_complex.jsonl")
        fl = load_jsonl(d / "failures.jsonl")
        if not pc and not fl:
            print(f"[!] Shard sin resultados: {d.name}. Abortando (fusión incompleta).")
            return 2
        for r in pc:
            if r["pid"] in rows or r["pid"] in fails:
                print(f"[!] pid duplicado entre shards: {r['pid']}. Abortando.")
                return 2
            rows[r["pid"]] = r
        for f in fl:
            if f["pid"] in rows or f["pid"] in fails:
                print(f"[!] pid duplicado entre shards: {f['pid']}. Abortando.")
                return 2
            fails[f["pid"]] = f
        m = json.loads((d / "metrics.json").read_text(encoding="utf-8"))
        shard_meta.append({
            "shard": d.name,
            "n_total": m.get("n_total"),
            "n_passed": m.get("n_passed"),
            "n_failed": m.get("n_failed"),
            "duration_seconds": m.get("duration_seconds"),
            "timestamp": m.get("timestamp"),
        })
        print(f"[*] {d.name}: {len(pc)} PASS, {len(fl)} FAIL "
              f"({m.get('duration_seconds')} s)")

    # Reintento en solitario: solo puede convertir un FAIL por timeout en PASS.
    rescatados: List[str] = []
    if RETRY_DIR.exists():
        retry_pc = load_jsonl(RETRY_DIR / "per_complex.jsonl")
        retry_fl = load_jsonl(RETRY_DIR / "failures.jsonl")
        for r in retry_pc:
            pid = r["pid"]
            if pid in rows:
                print(f"[!] {pid} ya tenia PASS en un shard; el reintento no sustituye. Abortando.")
                return 2
            if pid not in fails:
                print(f"[!] {pid} del reintento no estaba en la cohorte fallida. Abortando.")
                return 2
            rows[pid] = r
            del fails[pid]
            rescatados.append(pid)
        m = json.loads((RETRY_DIR / "metrics.json").read_text(encoding="utf-8"))
        shard_meta.append({
            "shard": RETRY_DIR.name, "tipo": "reintento_en_solitario_timeout_2400s",
            "n_total": m.get("n_total"), "n_passed": m.get("n_passed"),
            "n_failed": m.get("n_failed"), "duration_seconds": m.get("duration_seconds"),
            "timestamp": m.get("timestamp"), "rescatados": rescatados,
        })
        print(f"[*] {RETRY_DIR.name}: {len(retry_pc)} PASS, {len(retry_fl)} FAIL "
              f"| rescatados: {rescatados or 'ninguno'}")

    visto = set(rows) | set(fails)
    faltan = sorted(set(cohorte) - visto)
    sobran = sorted(visto - set(cohorte))
    if faltan or sobran:
        print(f"[!] Cohorte no cierra. Faltan: {faltan[:10]} ({len(faltan)}), "
              f"sobran: {sobran[:10]} ({len(sobran)}). Abortando.")
        return 2

    pc_rows = [rows[p] for p in cohorte if p in rows]
    fl_rows = [fails[p] for p in cohorte if p in fails]
    n_pass, n_fail = len(pc_rows), len(fl_rows)

    strata_stats: Dict[str, Any] = {}
    for r in pc_rows:
        dq_mean = float(r["abs_dq_mean_e"])
        dq_max = float(r["abs_dq_max_e"])
        s = r.get("strata", {})
        _acc_strata(strata_stats, "is_ionized", str(bool(s.get("is_ionized"))), dq_mean, dq_max)
        _acc_strata(strata_stats, "has_halogens", str(bool(s.get("has_halogens"))), dq_mean, dq_max)
        _acc_strata(strata_stats, "has_sulfur_phosphorus", str(bool(s.get("has_sulfur_phosphorus"))), dq_mean, dq_max)
        _acc_strata(strata_stats, "mw_stratum", s.get("mw_stratum", "?"), dq_mean, dq_max)
        _acc_strata(strata_stats, "rot_stratum", s.get("rot_stratum", "?"), dq_mean, dq_max)
        _acc_strata(strata_stats, "drug_likeness", s.get("drug_likeness", "?"), dq_mean, dq_max)
    for buckets in strata_stats.values():
        for b in buckets.values():
            b["mean_abs_dq_e"] = round(b["sum_abs_dq"] / b["n"], 6) if b["n"] else 0.0
            b["max_abs_dq"] = round(b["max_abs_dq"], 6)
            b.pop("sum_abs_dq", None)

    def _mean(key, fn=lambda v: v):
        return round(sum(fn(r[key]) for r in pc_rows) / n_pass, 6) if n_pass else 0.0

    def _max(key, fn=lambda v: v):
        return round(max((fn(r[key]) for r in pc_rows), default=0.0), 6)

    metrics = {
        "experiment_id": "RS-03-PARAM-B",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "decision": "GO",
        "cohorte": "116 ligandos train (PASS de RS-03-PARAM-A)",
        "n_total": len(cohorte),
        "n_passed": n_pass,
        "n_failed": n_fail,
        "coverage_vs_a": round(n_pass / len(cohorte), 4),
        "global_abs_dq_mean_e": _mean("abs_dq_mean_e"),
        "global_abs_dq_max_e": _max("abs_dq_max_e"),
        "max_delta_q_am1bcc_vs_formal_e": _max("delta_q_am1bcc_vs_formal_e"),
        "max_delta_mol_charge_e": _max("delta_mol_charge_e"),
        "n_atom_order_match": sum(1 for r in pc_rows if r.get("atom_order_match")),
        "max_atom_order_dr_angstrom": _max("atom_order_max_dr_angstrom"),
        "n_energy_finite": sum(1 for r in pc_rows if r.get("energy_finite")),
        "mean_delta_dipolo_debye": _mean("delta_dipolo_debye"),
        "max_delta_dipolo_debye": _max("delta_dipolo_debye"),
        "mean_abs_delta_energy_kjmol": _mean("delta_energy_kjmol", abs),
        "max_abs_delta_energy_kjmol": _max("delta_energy_kjmol", abs),
        "strata_stats": strata_stats,
        "failures_por_razon": {
            razon: sum(1 for f in fl_rows if f.get("reason") == razon)
            for razon in sorted({f.get("reason", "?") for f in fl_rows})
        },
        "shards": shard_meta,
        "nota_fusion": (
            "Union de 3 shards disjuntos (RS-03-PARAM-B-S1..S3), 116 pids sin solapamiento, "
            "mas el shard de reintento S4 en solitario (timeout 2400 s) para los ligandos que "
            "agotaron 1200 s bajo la contencion de los 3 shards simultaneos. Un PASS del "
            "reintento solo sustituye a un FAIL previo del mismo pid. Recalculo completo tras "
            "la incidencia de sobreescritura del 2026-08-17."
        ),
        "rescatados_por_reintento": rescatados,
        "nota_selector": (
            "AM1-BCC es referencia estratificada, no verdad absoluta. PROHIBIDO seleccionar "
            "NAGL por RMSD ni Top-1 (PRE maestro §4). Sin gate de aceptacion/rechazo de NAGL."
        ),
        "garantia_cuarentena": "cero val40/test/D-RC-CONFIRM; cohorte = 116 train PASS de A",
    }

    B_DIR.mkdir(parents=True, exist_ok=True)
    (B_DIR / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    with open(B_DIR / "per_complex.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for r in pc_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(B_DIR / "failures.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for r in fl_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"\n[*] Fusion completa: {n_pass}/{len(cohorte)} PASS ({metrics['coverage_vs_a']:.2%}), "
          f"{n_fail} FAIL | dq_mean={metrics['global_abs_dq_mean_e']} e, "
          f"dq_max={metrics['global_abs_dq_max_e']} e | "
          f"energias finitas {metrics['n_energy_finite']}/{n_pass}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
