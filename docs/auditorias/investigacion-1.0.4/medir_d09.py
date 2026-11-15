"""Verifica los centroides de D-09 y proyecta la pimozida de 8ZYQ sobre 5VA1."""
import gzip
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
TARGETS = ROOT / "data" / "targets"
PANEL = ROOT / "backend" / "data" / "anti_dianas_bowes44.json"
SITES = {"7SRQ", "6LQA", "8WE8", "9EQG", "5IKR", "7KWE"}
DEFAULT_7SRQ_CENTER = (152.587, 158.245, 155.595)


def atoms(pdb, record):
    with gzip.open(TARGETS / f"{pdb}.pdb.gz", "rt", encoding="ascii", errors="replace") as handle:
        for line in handle:
            if line.startswith(record) and line[76:78].strip() not in {"H", "D"} and line[16] in " A":
                yield line, [float(line[i:i + 8]) for i in (30, 38, 46)]


def ligands(pdb):
    groups = defaultdict(list)
    for line, xyz in atoms(pdb, "HETATM"):
        groups[line[17:27]].append(xyz)
    return groups


def centres():
    panel = json.loads(PANEL.read_text(encoding="utf-8"))["dianas"]
    out = {}
    for row in panel:
        pdb = row.get("pdb_id")
        if pdb not in SITES:
            continue
        center = np.array(DEFAULT_7SRQ_CENTER if pdb == "7SRQ" else row["center"])
        candidates = [(key, np.linalg.norm(np.mean(xyz, axis=0) - center)) for key, xyz in ligands(pdb).items()]
        ligand, distance = min(candidates, key=lambda pair: pair[1])
        out[pdb] = {"residuo_PDB": ligand, "distancia_al_centro_A": distance}
    return out


def project():
    def ca(pdb, chain):
        residues = {
            int(line[22:26]): point for line, point in atoms(pdb, "ATOM  ")
            if line[21] == chain and line[12:16].strip() == "CA"
        }
        return np.array([residues[i] for i in range(620, 661)])

    receptor = ca("5VA1", "A")
    ligand, = [np.array(xyz) for key, xyz in ligands("8ZYQ").items() if key.startswith("1II")]
    center = np.array((73.15, 73.15, 78.53))
    half = np.array((14.4, 14.4, 15.0))
    out = {}
    for chain in "ABCD":
        moving = ca("8ZYQ", chain)
        x, y = moving.mean(axis=0), receptor.mean(axis=0)
        u, _, vt = np.linalg.svd((moving - x).T @ (receptor - y))
        if np.linalg.det(u @ vt) < 0:
            u[:, -1] *= -1
        rot = u @ vt
        moved = (ligand - x) @ rot + y
        residual = (moving - x) @ rot + y - receptor
        out[chain] = {
            "rmsd_Ca_A": np.sqrt(np.mean(np.sum(residual ** 2, axis=1))),
            "centroide_a_centro_A": np.linalg.norm(moved.mean(axis=0) - center),
            "max_distancia_por_eje_A": np.max(np.abs(moved - center), axis=0).tolist(),
            "atomos_dentro": int(np.all(np.abs(moved - center) <= half, axis=1).sum()),
            "atomos_pimozida": len(ligand),
        }
    return out


if __name__ == "__main__":
    print(json.dumps({"centroides": centres(), "pimozida_sobre_5VA1": project()}, indent=2))
