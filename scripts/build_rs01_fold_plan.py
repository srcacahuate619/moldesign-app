#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_rs01_fold_plan.py — RS-01 IT1, B2 del maintainer.

Genera scripts/artifacts_science/RS-01/fold_plan.json con las membresías
EXACTAS del cross-fitting RS-01B (K=5) sobre los 116 complejos train de la
unión MF-01-UNION:

  - Bloqueo SIMULTÁNEO por scaffold del ligando Y componente de similitud de
    cadenas del receptor (k-meros k=8, umbral 0.90, union-find con cierre
    transitivo). Funciones reutilizadas por composición de
    scripts/build_confirm_cohort.py (sellado, FND-05): cadenas_receptor,
    clusters_cadenas, quimica_ligando, leer_ligando.
  - Política química FND-05 para acíclicos: scaffold_class = "acyclic:<ik14>"
    (clase propia como unidad de scaffold), igual que D-RC-CONFIRM.
  - Componentes combinadas = componentes conexas del grafo (nodos = 116
    complejos; aristas por MISMO scaffold_class O MISMA componente de cadenas
    de receptor). Ninguna componente cruza folds.
  - Asignación determinista: componentes ordenadas por (tamaño desc, clave
    canónica asc) asignadas a los 5 folds por "fold menos lleno" (empate →
    índice de fold menor). Sin semilla, sin aleatoriedad.
  - Estadísticas por fold: tamaño y balance del estrato hard/control de
    D-MF-HARD train (cohort.jsonl sellado, solo lectura).

Determinista: sin timestamps; dos corridas producen bytes idénticos.
Sin pip, sin red, sin commits. NO abre poses_val.jsonl ni poses_test.jsonl.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import build_confirm_cohort as bcc  # noqa: E402 (composición, sellado FND-05)

PDBBIND = ROOT / "data" / "pdbbind"
UNION_TRAIN = ROOT / "scripts" / "artifacts_science" / "MF-01-UNION" / "union_candidates_train.jsonl"
COHORT = ROOT / "scripts" / "artifacts_science" / "D-MF-HARD" / "cohort.jsonl"
OUT_PLAN = ROOT / "scripts" / "artifacts_science" / "RS-01" / "fold_plan.json"

N_FOLDS = 5
K_MER = bcc.K_MER              # 8
UMBRAL = bcc.UMBRAL_CADENA     # 0.90
MODULO_REUTILIZADO_SHA = "a77c8d17e3d829560979a1dd49473163f1d134daf7ceeab994911105061fd3b3"

ABIERTOS: list[str] = []


def registrar(path: Path, modo: str) -> None:
    ABIERTOS.append(f"{modo}:{path.as_posix()}")


def cargar_pids_union() -> list[str]:
    """116 pids únicos en orden de primera aparición (orden canónico)."""
    pids: list[str] = []
    vistos: set[str] = set()
    with open(UNION_TRAIN, encoding="utf-8") as fh:
        registrar(UNION_TRAIN, "lectura")
        for linea in fh:
            if not linea.strip():
                continue
            ident = json.loads(linea)["identity"]
            pid = ident.split("|")[1]
            if pid not in vistos:
                vistos.add(pid)
                pids.append(pid)
    if len(pids) != 116:
        print(f"FATAL: se esperaban 116 pids únicos, hay {len(pids)}")
        sys.exit(1)
    return pids


def cargar_estrato_dmfhard() -> dict[str, str]:
    """{pid: 'hard'|'control'} solo para split=train de D-MF-HARD."""
    estrato: dict[str, str] = {}
    with open(COHORT, encoding="utf-8") as fh:
        registrar(COHORT, "lectura")
        for linea in fh:
            if not linea.strip():
                continue
            r = json.loads(linea)
            if r.get("split") == "train":
                estrato[str(r["pid"])] = str(r["stratum"])
    return estrato


def scaffold_id_12(clase: str) -> str:
    return hashlib.sha256(clase.encode("utf-8")).hexdigest()[:12]


def asignar_folds(componentes: list[tuple[str, list[str]]]) -> list[int]:
    """Greedy determinista: componente mayor primero; fold menos lleno
    (empate → índice de fold menor). Devuelve fold por componente."""
    orden = sorted(
        range(len(componentes)),
        key=lambda i: (-len(componentes[i][1]), componentes[i][0]),
    )
    tamaños = [0] * N_FOLDS
    fold_por_comp = [0] * len(componentes)
    for i in orden:
        mejor = min(range(N_FOLDS), key=lambda f: (tamaños[f], f))
        fold_por_comp[i] = mejor
        tamaños[mejor] += len(componentes[i][1])
    return fold_por_comp


def main() -> int:
    pids = cargar_pids_union()
    estrato_dmf = cargar_estrato_dmfhard()

    # ── química: scaffold_class con política FND-05 ──
    quim: dict[str, dict] = {}
    for pid in pids:
        mol = bcc.leer_ligando(PDBBIND, pid)
        if mol is None:
            quim[pid] = {"scaffold_class": None, "scaffold_id": None,
                         "inchikey14": None, "n_rings": None,
                         "ligando_ilegible": True, "aciclico": False}
            continue
        q = bcc.quimica_ligando(mol)
        clase = q.get("scaffold_class")
        quim[pid] = {
            "scaffold_class": clase,
            "scaffold_id": scaffold_id_12(clase) if clase else None,
            "inchikey14": q.get("inchikey14"),
            "n_rings": q.get("n_rings"),
            "ligando_ilegible": False,
            "aciclico": bool(clase and clase.startswith("acyclic:")),
        }

    # ── receptor: componentes de cadenas (k=8, 0.90, union-find) ──
    unidades = [(pid, bcc.cadenas_receptor(PDBBIND, pid)) for pid in pids]
    cluster_por_indice, tamanos_desc, vecinos = bcc.clusters_cadenas(unidades)
    receptor_comp = {pids[i]: cluster_por_indice[i] for i in range(len(pids))}
    n_sin_secuencia = sum(1 for _, cads in unidades if not cads)

    # ── grafo combinado: union-find sobre pids ──
    idx = {pid: i for i, pid in enumerate(pids)}
    padre = list(range(len(pids)))
    rango = [0] * len(pids)

    def find(x: int) -> int:
        while padre[x] != x:
            padre[x] = padre[padre[x]]
            x = padre[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra == rb:
            return
        if rango[ra] < rango[rb]:
            ra, rb = rb, ra
        padre[rb] = ra
        if rango[ra] == rango[rb]:
            rango[ra] += 1

    # aristas receptor: misma componente de cadenas
    por_comp_rec: dict[int, list[int]] = {}
    for pid, c in receptor_comp.items():
        por_comp_rec.setdefault(c, []).append(idx[pid])
    for miembros in por_comp_rec.values():
        for j in range(1, len(miembros)):
            union(miembros[0], miembros[j])
    # aristas scaffold: misma clase (política FND-05, incluye acyclic:<ik14>)
    por_scaffold: dict[str, list[int]] = {}
    for pid in pids:
        clase = quim[pid]["scaffold_class"]
        if clase:
            por_scaffold.setdefault(clase, []).append(idx[pid])
    for miembros in por_scaffold.values():
        for j in range(1, len(miembros)):
            union(miembros[0], miembros[j])

    # ── componentes combinadas ──
    por_raiz: dict[int, list[str]] = {}
    for pid in pids:
        por_raiz.setdefault(find(idx[pid]), []).append(pid)
    componentes = sorted(
        (( ";".join(sorted(m)) , sorted(m)) for m in por_raiz.values()),
        key=lambda c: c[0],
    )
    n_componentes = len(componentes)
    tamanos = sorted((len(m) for _, m in componentes), reverse=True)
    max_componente = tamanos[0] if tamanos else 0

    # ── asignación de folds ──
    fold_por_comp = asignar_folds(componentes)
    fold_por_pid: dict[str, int] = {}
    for f, (_, miembros) in zip(fold_por_comp, componentes):
        for pid in miembros:
            fold_por_pid[pid] = f
    fold_sizes = [sum(1 for f in fold_por_pid.values() if f == k)
                  for k in range(N_FOLDS)]

    # ── estadísticas por fold (D-MF-HARD train) ──
    per_fold = []
    for f in range(N_FOLDS):
        pids_f = sorted(pid for pid, k in fold_por_pid.items() if k == f)
        hard = sum(1 for pid in pids_f if estrato_dmf.get(pid) == "hard")
        control = sum(1 for pid in pids_f if estrato_dmf.get(pid) == "control")
        per_fold.append({
            "fold": f,
            "n_complejos": len(pids_f),
            "dmfhard_train": {"hard": hard, "control": control,
                              "n_en_cohorte": hard + control},
        })

    # ── verificaciones contra el pre-audit del maintainer ──
    n_aciclicos = sum(1 for pid in pids if quim[pid]["aciclico"])
    multiset_folds = sorted(fold_sizes, reverse=True)
    verificacion = {
        "componentes_combinadas_38": bool(n_componentes == 38),
        "componente_mayor_55": bool(max_componente == 55),
        "folds_55_16_15_15_15": bool(multiset_folds == [55, 16, 15, 15, 15]),
        "aciclicos_19": bool(n_aciclicos == 19),
        "detalle": {
            "n_componentes_real": n_componentes,
            "max_componente_real": max_componente,
            "folds_reales": fold_sizes,
            "n_aciclicos_real": n_aciclicos,
            "n_sin_secuencia_receptor": n_sin_secuencia,
            "n_sin_scaffold": sum(1 for pid in pids if quim[pid]["scaffold_class"] is None),
            "tamanos_componentes_desc": tamanos,
        },
    }

    plan = {
        "schema": "rs01_fold_plan_v1",
        "experimento": "RS-01B",
        "n_complejos": len(pids),
        "n_folds": N_FOLDS,
        "bloqueo": {
            "scaffold_politica": "FND-05: Murcko 'm:<smiles>'; aciclicos 'acyclic:<ik14>' "
                                 "(clase propia como unidad); oligosacaridos heuristicos 'oligo:n:o'; "
                                 "ligando ilegible -> sin aristas de scaffold (documentado)",
            "receptor": f"cadenas SEQRES (fallback CA); k-meros k={K_MER}; arista si algun par "
                        f"de cadenas >= {UMBRAL}; union-find con cierre transitivo "
                        "(build_confirm_cohort.clusters_cadenas, ITERACION 3)",
            "claim_honesto": "near-identity-receptor-disjoint + Murcko-disjoint donde Murcko esta definido",
            "modulo_reutilizado": {
                "archivo": "scripts/build_confirm_cohort.py",
                "sha256_sellado": MODULO_REUTILIZADO_SHA,
                "funciones": ["cadenas_receptor", "clusters_cadenas",
                              "quimica_ligando", "leer_ligando"],
            },
        },
        "asignacion": {
            "regla": "componentes ordenadas por (tamaño desc, clave canonica asc); "
                     "asignadas al fold menos lleno (empate -> índice de fold menor); "
                     "sin semilla, sin aleatoriedad",
            "componentes_por_fold": fold_sizes,
        },
        "verificacion_preaudit": verificacion,
        "por_pid": [
            {
                "pid": pid,
                "fold": fold_por_pid[pid],
                "componente": next(c for c, m in componentes if pid in m),
                "scaffold_class": quim[pid]["scaffold_class"],
                "scaffold_id": quim[pid]["scaffold_id"],
                "inchikey14": quim[pid]["inchikey14"],
                "n_rings": quim[pid]["n_rings"],
                "aciclico": quim[pid]["aciclico"],
                "receptor_componente": receptor_comp[pid],
                "dmfhard_train_estrato": estrato_dmf.get(pid),
            }
            for pid in pids
        ],
        "por_componente": [
            {
                "componente": clave,
                "n_complejos": len(miembros),
                "pids": miembros,
                "fold": fold_por_comp[i],
            }
            for i, (clave, miembros) in enumerate(componentes)
        ],
        "por_fold": per_fold,
        "archivos_abiertos_por_el_script": ABIERTOS,
        "garantia_cuarentena": "el script NO abre poses_val.jsonl ni poses_test.jsonl; "
                               "solo union train sellada, pdbbind (estructuras) y "
                               "cohort.jsonl sellado de D-MF-HARD",
        "determinismo": "sin timestamps ni aleatoriedad; dos corridas producen bytes idénticos",
    }
    with open(OUT_PLAN, "w", encoding="utf-8") as fh:
        registrar(OUT_PLAN, "escritura")
        json.dump(plan, fh, ensure_ascii=False, indent=2)
        fh.write("\n")

    print(f"componentes={n_componentes} (esperado 38) | max={max_componente} "
          f"(esperado 55) | folds={fold_sizes} (esperado 55/16/15/15/15) | "
          f"aciclicos={n_aciclicos} (esperado 19) | sin_secuencia_receptor={n_sin_secuencia}")
    for v in verificacion["detalle"]:
        if v.startswith("n_"):
            print(f"  {v}={verificacion['detalle'][v]}")
    return 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    sys.exit(main())
