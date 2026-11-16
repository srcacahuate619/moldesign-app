"""Reanaliza los scores públicos y mide el panel de bloqueo en 5VA1."""

import argparse
import asyncio
import csv
import hashlib
import json
import math
import os
import sys
import time
from pathlib import Path

from scipy.stats import spearmanr

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SOURCE_SHA = "9d0cd23c08c93071a69661f9538c3b001a4f41e1bd6bc4db382c522f5a0d537c"
CENTER = (73.15, 73.15, 78.53)
SIZE = (28.8, 28.8, 30.0)
CHAINS = ["A", "B", "C", "D"]
# IC50 de patch clamp en micromolar. Los tres límites inferiores están censurados.
PANEL = (
    ("amiodarone", 2157, .546, False), ("cisapride", 6917698, .091, False),
    ("droperidol", 3168, .307, False), ("haloperidol", 3559, .015, False),
    ("quinidine", 441074, 1.5, False), ("sotalol", 5253, 556, False),
    ("sparfloxacin", 60464, 24, False), ("terfenadine", 5405, .061, False),
    ("moxifloxacin", 152946, 235, False), ("tamoxifen", 2733526, .777, False),
    ("ziprasidone", 60854, .165, False), ("amoxicillin", 33613, 50000, True),
    ("aspirin", 2244, 100000, True), ("captopril", 44093, 3000, True),
    ("propranolol", 4946, 9.9, False), ("verapamil", 2520, .94, False),
)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def save(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def wilson(events, total):
    if not total:
        return None
    z = 1.959963984540054
    rate = events / total
    middle = rate + z ** 2 / (2 * total)
    radius = z * math.sqrt(rate * (1 - rate) / total + z ** 2 / (4 * total ** 2))
    scale = 1 + z ** 2 / total
    return [max(0.0, (middle - radius) / scale), min(1.0, (middle + radius) / scale)]


def compare(rows, positive):
    report = {}
    for limit in (-7.0, -7.5):
        tp = sum(positive(row) and row["score"] < limit for row in rows)
        fn = sum(positive(row) and row["score"] >= limit for row in rows)
        tn = sum(not positive(row) and row["score"] >= limit for row in rows)
        fp = sum(not positive(row) and row["score"] < limit for row in rows)
        report[str(limit)] = {"tp": tp, "fn": fn, "tn": tn, "fp": fp,
                              "sensibilidad_ic95": wilson(tp, tp + fn), "especificidad_ic95": wilson(tn, tn + fp)}
    return {"n": len(rows), "umbrales": report,
            "discordantes": [dict(row, positivo=positive(row)) for row in rows if -7.5 <= row["score"] < -7.0]}


def published(data):
    raw = data / "data_clean.csv"
    if sha(raw.read_bytes()) != SOURCE_SHA:
        raise ValueError("Hash de la tabla publicada distinto del registro")
    with raw.open(encoding="utf-8-sig", newline="") as handle:
        source = list(csv.DictReader(handle))
    rows = [{"compound": row["Name"], "score": float(row["vina"]), "tdp": int(float(row["TdP"]))}
            for row in source]
    if len(rows) != 53 or {row["tdp"] for row in rows} != {0, 1}:
        raise ValueError("La tabla no corresponde al panel registrado")
    return compare(rows, lambda row: row["tdp"] == 1)


def compounds(data):
    selected = []
    for name, cid, ic50, censored in PANEL:
        item = data / f"{name}.json"
        props, = json.loads(item.read_bytes())["PropertyTable"]["Properties"]
        if props["CID"] != cid:
            raise ValueError(f"Identidad PubChem distinta en {name}")
        selected.append({"compound": name, "cid": cid, "inchi_key": props["InChIKey"], "smiles": props["SMILES"],
                         "ic50_um": ic50, "lower_bound": censored, "pubchem_sha256": sha(item.read_bytes())})
    return selected


async def measure(data, workers):
    sys.path.insert(0, str(ROOT / "scripts"))
    from invariancia_catalogo_receptores import _entorno

    work = data / "runtime"
    _entorno(work)
    os.environ["VINA_CPU"] = "2"

    from chem.conformer import generate_conformer
    from services.docking.preparer import RECEPTOR_RECIPE_VERSION, _meeko_report_path, prepare_target, resolve_effective_docking_box
    from services.docking.vina_service import run_vina_docking
    from utils.local_storage import read_bytes

    entries = data / "corridas"
    entries.mkdir(exist_ok=True)
    center, size = resolve_effective_docking_box(pdb_id="5VA1", chain_id="A", center=CENTER, size=SIZE, site_chains=CHAINS)
    if tuple(center) != CENTER or tuple(size) != SIZE:
        raise ValueError(f"La caja efectiva difiere del registro: {(center, size)}")
    path = await prepare_target(pdb_id="5VA1", chain_id="A", center=center, size=size, site_chains=CHAINS)
    receptor = await read_bytes(path)
    report = json.loads(await read_bytes(_meeko_report_path(path)))
    vina = ROOT / "tools" / "vina" / "vina.exe"
    metadata = {"receptor_sha256": sha(receptor), "deposito_sha256": sha((ROOT / "data/targets/5VA1.pdb.gz").read_bytes()),
                "recipe_hash": report["recipe_hash"], "receptor_recipe": RECEPTOR_RECIPE_VERSION,
                "vina_sha256": sha(vina.read_bytes()), "centro": center, "tamano": size, "cadenas": CHAINS}
    save(data / "preparacion.json", metadata)
    print("Receptor", metadata["receptor_sha256"], flush=True)
    capacity = asyncio.Semaphore(workers)

    async def run(entry):
        async with capacity:
            conf = None
            for seed in (42, 43):
                dest = entries / f"{entry['compound']}-{seed}.json"
                if dest.exists():
                    row = json.loads(dest.read_bytes())
                else:
                    started = time.monotonic()
                    row = dict(entry, seed=seed, receptor_sha256=metadata["receptor_sha256"])
                    try:
                        if conf is None:
                            conf = await generate_conformer(entry["smiles"], ph=7.4)
                        result = await run_vina_docking(
                            smiles_hash=conf["smiles_hash"], smiles=entry["smiles"], target_pdb_id="5VA1",
                            target_chain="A", target_center=center, target_size=size, site_chains=CHAINS,
                            prepared_receptor_bytes=receptor, exhaustiveness=8, num_poses=9, seed=seed,
                        )
                        row.update(score=result.best_affinity, microstate=conf["canonical_smiles"],
                                   protocol=result.model_dump(mode="json"))
                    except Exception as exc:
                        row["error"] = f"{type(exc).__name__}: {exc}"
                    row["elapsed_s"] = time.monotonic() - started
                    save(dest, row)
                print(entry["compound"], seed, row.get("score", row.get("error")), flush=True)
                if seed == 42 and ("score" not in row or not -7.8 <= row["score"] <= -6.7):
                    break

    await asyncio.gather(*(run(entry) for entry in compounds(data)))


def local(data):
    files = sorted((data / "corridas").glob("*.json"))
    records = []
    for path in files:
        record = json.loads(path.read_bytes())
        record.pop("protocol", None)
        records.append(record)
    rows = [row for row in records if row["seed"] == 42 and "score" in row]
    summary = {key: compare(rows, lambda row: not row["lower_bound"] and row["ic50_um"] <= limit)
               for key, limit in (("hasta_10_um", 10), ("hasta_1_um", 1))}
    margin = [row for row in rows if not 5 <= row["ic50_um"] <= 20]
    summary["hasta_10_um_sin_5_a_20_um"] = compare(margin, lambda row: not row["lower_bound"] and row["ic50_um"] <= 10)
    quantitative = [row for row in rows if not row["lower_bound"]]
    if len(quantitative) > 2:
        statistic = spearmanr([-r["score"] for r in quantitative], [-math.log10(r["ic50_um"]) for r in quantitative])
        summary["spearman"] = {"rho": statistic.statistic, "p": statistic.pvalue, "n": len(quantitative)}
    summary["semillas_y_fallos"] = records
    summary["hashes_crudos"] = {path.name: sha(path.read_bytes()) for path in files}
    return summary


async def contract():
    from types import SimpleNamespace

    sys.path.insert(0, str(ROOT / "backend"))
    from scoring.normalizer import normalize_affinity
    from services.docking.selectivity import seleccionar_anti_dianas, texto_de_alerta

    catalog = json.loads((ROOT / "curated_targets.json").read_bytes())
    row = next(entry for entry in catalog if entry["pdb_id"] == "5VA1")
    floor = row["affinity_threshold"]

    async def target(pdb_id):
        return SimpleNamespace(pdb_id=pdb_id, affinity_threshold=floor)

    repo = SimpleNamespace(get_target_by_pdb_id=target)
    default, _ = await seleccionar_anti_dianas(None, repo)
    selected, _ = await seleccionar_anti_dianas(["5VA1"], repo)
    cuts = [next(entry["affinity_threshold"] for entry in items if entry["pdb_id"] == "5VA1")
            for items in (default, selected)]
    return {"anti_diana_panel_por_defecto": cuts[0], "anti_diana_panel_elegido": cuts[1],
            "normalizacion_catalogo": floor, "ejemplo_score": -7.3, "alerta_ejemplo": -7.3 < cuts[0],
            "ejemplo_redondeo_tamoxifeno": texto_de_alerta("hERG", -7.004, cuts[0], "", True).split(" Riesgo:")[0],
            "normalizacion_molecula_de_30_atomos_con_score_menos_6_8": {
                str(cut): normalize_affinity(-6.8, 30, threshold=cut) for cut in (floor, cuts[0])}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("publicada", "medir", "local", "contrato"))
    parser.add_argument("data", nargs="?", type=Path)
    parser.add_argument("--workers", default=4, type=int)
    args = parser.parse_args()
    if args.mode == "contrato":
        print(json.dumps(asyncio.run(contract()), indent=2))
    elif args.data is None:
        parser.error("indica el directorio de evidencia")
    elif args.mode == "medir":
        asyncio.run(measure(args.data, args.workers))
    else:
        result = published(args.data) if args.mode == "publicada" else local(args.data)
        print(json.dumps(result, indent=2))
