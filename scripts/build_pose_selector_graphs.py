# -*- coding: utf-8 -*-
"""
build_pose_selector_graphs.py — Ruta C, Fase 2 (docs/42_RUTA_C_PROTOCOLO.md).

Construye los grafos PyG por pose para el GNN v1 PoseSelector a partir de los
registros congelados de Fase 0 (data/pose_selector_dataset/
poses_{train,val,test}.jsonl) y de los archivos de poses originales
(S1 flexible_redock, S2 molflex, S3 ruta_a).

Por cada registro se emite UN Data con:
  - grafo de ligando: atomos pesados de la pose (coords resueltas por el
    mapa serial->mol, MISMO mecanismo de Fase 0), features de 38 dims
    replica de rescoring/gnn_v2/data.py:_build_ligand_graph (30 one-hot de
    elemento + 4 hibridacion + grado/carga/aromatico/anillo), enlaces
    covalentes del CRISTAL (RDKit, misma indexacion que los mapas) mas
    enlaces espaciales 4 A sobre las coords de la pose;
  - grafo de proteina: residuos del pocket (Ca) de {pid}_protein.pdb dentro
    de 10 A de CUALQUIER atomo pesado de ESTA pose (pocket dependiente de la
    pose, principio C4 del protocolo), features 24 dims (21 one-hot AA + 3
    coords, igual que data.py), k=10 aristas NN;
  - aristas cruzadas ligando -> Ca a 8 A (convencion de data.py);
  - global_feat = [vina_score] (None/NaN -> -99.0 sentinel), y_rmsd (float),
    pid (str), group_size (int, poses de ese pid en el split).

Reanudable: data/pose_selector_dataset/graphs_progress.json (clave de
registro -> estado) mas archivos parciales gnn_{split}.pt.partial. El .pt
final se escribe de forma atomica (temp + os.replace) al completar el split.
"""

from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import molflex as mf  # noqa: E402
import build_pose_selector_dataset as bpsd  # noqa: E402
from rescoring.gnn_v2.data import (  # noqa: E402
    AA3_TO_AA1,
    AA_TO_IDX,
    CROSS_CUTOFF,
    ELEMENTS,
    ELEM_TO_IDX,
    POCKET_CUTOFF,
    PROT_KNN,
    SPATIAL_EDGE_CUTOFF,
    UNK_AA_IDX,
    _build_cross_edges,
)
from torch_geometric.data import Data  # noqa: E402

DATASET_DIR = PROJECT_ROOT / "data" / "pose_selector_dataset"
PROGRESS_PATH = DATASET_DIR / "graphs_progress.json"
SPLIT_ARCHIVOS = {s: DATASET_DIR / f"gnn_{s}.pt" for s in ("train", "val", "test")}
SENTINEL_VINA = -99.0
LOTE_PARCIAL = 250  # cada cuantos grafos se guarda el .pt.partial


# ───────────────────────── utilidades de consola/progreso ──────────────────

def configurar_salida() -> None:
    """Consola Windows: UTF-8 con reemplazo y silencio de RDKit."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    try:
        from rdkit import RDLogger
        RDLogger.DisableLog("rdApp.error")
        RDLogger.DisableLog("rdApp.warning")
    except Exception:
        pass


def ahora_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def guardar_progreso(prog: dict) -> None:
    tmp = PROGRESS_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(prog, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    import os
    os.replace(tmp, PROGRESS_PATH)


def cargar_progreso() -> dict:
    if PROGRESS_PATH.exists():
        try:
            return json.loads(PROGRESS_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"status": "en_progreso", "iniciado": ahora_iso(),
            "splits": {s: {"status": "pendiente", "records": {}}
                       for s in ("train", "val", "test")},
            "excluidos": {}}


# ───────────────────────── caches por proceso ───────────────────────────────

_trabajos_idx: dict | None = None
_cache_cristal: dict = {}
_cache_modelos: dict = {}
_cache_prot: dict = {}
_cache_lig_fijo: dict = {}


def obtener_trabajos_idx() -> dict:
    """{(pid, fuente, stem): trabajo} — reusa la enumeracion de Fase 0."""
    global _trabajos_idx
    if _trabajos_idx is None:
        _trabajos_idx = {(t["pid"], t["fuente"], t["stem"]): t
                         for t in bpsd.enumerar_trabajos()}
    return _trabajos_idx


def obtener_cristal(pid: str):
    if pid in _cache_cristal:
        return _cache_cristal[pid]
    mol = mf.leer_ligando(str(bpsd.mf.PDBBIND / pid / f"{pid}_ligand.sdf"))
    _cache_cristal[pid] = mol
    return mol


def obtener_modelos(t: dict):
    """Modelos parseados del archivo de poses (cache por trabajo)."""
    key = (t["pid"], t["fuente"], t["stem"])
    if key not in _cache_modelos:
        try:
            texto = t["out"].read_text(encoding="utf-8")
            _cache_modelos[key] = mf.parsear_out_vina(texto)
        except Exception:
            _cache_modelos[key] = None
    return _cache_modelos[key]


# ───────────────────────── grafo de ligando ─────────────────────────────────

def lig_fijo(pid: str):
    """Features (N, 38) y enlaces covalentes del CRISTAL por pid. La
    construccion de features replica rescoring/gnn_v2/data.py:
    _build_ligand_graph (misma indexacion heavy que los mapas serial->mol).
    Devuelve (idx_pesados, feats, pares_cov) o None."""
    if pid in _cache_lig_fijo:
        return _cache_lig_fijo[pid]
    crystal = obtener_cristal(pid)
    if crystal is None:
        _cache_lig_fijo[pid] = None
        return None
    from rdkit import Chem

    heavy = [i for i, a in enumerate(crystal.GetAtoms()) if a.GetAtomicNum() > 1]
    if not heavy:
        _cache_lig_fijo[pid] = None
        return None
    rango = {i: k for k, i in enumerate(heavy)}
    pt = Chem.GetPeriodicTable()
    feats = []
    for i in heavy:
        atom = crystal.GetAtomWithIdx(i)
        elem_idx = ELEM_TO_IDX.get(atom.GetSymbol(), len(ELEMENTS) - 1)
        elem_onehot = np.zeros(len(ELEMENTS), dtype=np.float32)
        elem_onehot[elem_idx] = 1.0

        hyb = str(atom.GetHybridization())
        hyb_onehot = np.zeros(4, dtype=np.float32)
        if "SP2" in hyb:
            hyb_onehot[1] = 1.0
        elif "SP3" in hyb:
            hyb_onehot[2] = 1.0
        elif "SP" in hyb:
            hyb_onehot[0] = 1.0
        else:
            hyb_onehot[3] = 1.0

        degree = min(atom.GetDegree(), 6)
        charge = atom.GetFormalCharge()
        aromatic = 1.0 if atom.GetIsAromatic() else 0.0
        in_ring = 1.0 if atom.IsInRing() else 0.0
        feat = np.concatenate([
            elem_onehot, hyb_onehot,
            np.array([degree / 6.0, (charge + 2.0) / 4.0, aromatic, in_ring],
                     dtype=np.float32),
        ])
        feats.append(feat)
    feats = np.array(feats, dtype=np.float32)

    pares_cov: set = set()
    for bond in crystal.GetBonds():
        hi = rango.get(bond.GetBeginAtomIdx())
        hj = rango.get(bond.GetEndAtomIdx())
        if hi is not None and hj is not None:
            pares_cov.add((hi, hj))
            pares_cov.add((hj, hi))
    _cache_lig_fijo[pid] = (heavy, feats, pares_cov)
    return _cache_lig_fijo[pid]


def lig_grafo_pose(pid: str, coords: np.ndarray):
    """Grafo de ligando de una pose: features fijas del cristal + enlaces
    covalentes del cristal + enlaces espaciales (< 4 A) sobre coords de la
    pose. Devuelve (x, pos, edge_index)."""
    heavy, feats, pares_cov = lig_fijo(pid)
    n = len(heavy)
    d = np.linalg.norm(coords[:, None, :] - coords[None, :, :], axis=2)
    mascara = d < SPATIAL_EDGE_CUTOFF
    for (hi, hj) in pares_cov:
        mascara[hi, hj] = False
    ii, jj = np.nonzero(np.triu(mascara, 1))
    # pares_cov ya incluye ambos sentidos (data.py); los espaciales se
    # agregan en ambos sentidos sobre los indices heavy.
    unicos = set(pares_cov)
    for a, b in zip(ii, jj):
        unicos.add((int(a), int(b)))
        unicos.add((int(b), int(a)))
    ei = (torch.tensor(sorted(unicos), dtype=torch.long).t().contiguous()
          if unicos else torch.empty((2, 0), dtype=torch.long))
    return (torch.tensor(feats, dtype=torch.float32),
            torch.tensor(coords, dtype=torch.float32), ei)


# ───────────────────────── grafo de proteina (por pose) ─────────────────────

def prot_cache(pid: str):
    """Residuos del PDB de proteina con su Ca, cacheados por pid. Replica
    la semantica de rescoring/gnn_v2/data.py:_build_protein_graph:
    MolFromPDBFile(removeHs, sanitize=False) + SanitizeMol; los residuos sin
    mapeo AA3->AA1 (agua, iones) se descartan; solo residuos con Ca
    participan como nodos."""
    if pid in _cache_prot:
        return _cache_prot[pid]
    from rdkit import Chem

    p = bpsd.mf.PDBBIND / pid / f"{pid}_protein.pdb"
    mol = Chem.MolFromPDBFile(str(p), removeHs=True, sanitize=False)
    if mol is None:
        _cache_prot[pid] = None
        return None
    try:
        Chem.SanitizeMol(mol, Chem.SanitizeFlags.SANITIZE_ALL
                         ^ Chem.SanitizeFlags.SANITIZE_PROPERTIES)
    except Exception:
        _cache_prot[pid] = None
        return None
    conf = mol.GetConformer()
    residuos: dict = {}
    ca_atoms: dict = {}
    for atom in mol.GetAtoms():
        info = atom.GetPDBResidueInfo()
        if info is None:
            continue
        key = (info.GetChainId().strip(), info.GetResidueName().strip(),
               info.GetResidueNumber())
        residuos.setdefault(key, []).append(atom.GetIdx())
        if info.GetName().strip() == "CA":
            ca_atoms[key] = atom.GetIdx()
    if not ca_atoms:
        _cache_prot[pid] = None
        return None
    out = []
    for key, aidxs in residuos.items():
        rn1 = AA3_TO_AA1.get(key[1], "")
        if not rn1:
            continue
        ca = ca_atoms.get(key)
        if ca is None:
            continue
        pos = np.array([conf.GetAtomPosition(a) for a in aidxs],
                       dtype=np.float64)
        ca_pos = np.array(conf.GetAtomPosition(ca), dtype=np.float64)
        aa_idx = AA_TO_IDX.get(rn1, UNK_AA_IDX)
        out.append({"aa": aa_idx, "pos": pos, "ca_pos": ca_pos,
                    "ca_orden": ca})
    if not out:
        _cache_prot[pid] = None
        return None
    _cache_prot[pid] = out
    return out


def prot_por_pose(pid: str, lig_coords: np.ndarray):
    """Subgrafo de proteinas: Ca de residuos con ALGUN atomo dentro de
    POCKET_CUTOFF de ALGUN atomo pesado de esta pose. Nodos ordenados por
    indice de atomo CA (igual que data.py). k=PROT_KNN aristas NN."""
    cache = prot_cache(pid)
    if cache is None:
        return None
    sel = []
    for r in cache:
        d2 = ((r["pos"][None, :, :] - lig_coords[:, None, :]) ** 2).sum(-1)
        if float(d2.min()) < POCKET_CUTOFF ** 2:
            sel.append(r)
    if not sel:
        return None
    sel.sort(key=lambda r: r["ca_orden"])
    x = np.zeros((len(sel), 24), dtype=np.float32)
    pos = np.zeros((len(sel), 3), dtype=np.float32)
    for k, r in enumerate(sel):
        x[k, r["aa"]] = 1.0
        pos[k] = r["ca_pos"]
    pos_t = torch.tensor(pos, dtype=torch.float32)
    k = min(PROT_KNN, len(pos) - 1)
    pares = []
    for i in range(len(pos)):
        dists = torch.norm(pos_t - pos_t[i], dim=1)
        _, idxs = torch.topk(dists, k + 1, largest=False)
        for j in idxs[1:]:
            pares.append((i, int(j)))
            pares.append((int(j), i))
    ei = (torch.tensor(pares, dtype=torch.long).t().contiguous()
          if pares else torch.empty((2, 0), dtype=torch.long))
    return Data(x=torch.tensor(x, dtype=torch.float32), pos=pos_t,
                edge_index=ei)


# ───────────────────────── construccion por registro ────────────────────────

def construir_grafo(r: dict, group_sizes: dict):
    """Data por registro o (None, razon_de_exclusion)."""
    pid, source, stem = r["pid"], r["source"], r["file_stem"]
    mi = int(r["model_idx"])
    job = obtener_trabajos_idx().get((pid, source, stem))
    if job is None:
        return None, "trabajo_faltante"

    mapa, razon = bpsd.obtener_mapa(job)
    if mapa is None:
        return None, razon
    crystal = obtener_cristal(pid)
    if crystal is None:
        return None, "sdf_ilegible"

    modelos = obtener_modelos(job)
    if modelos is None or mi >= len(modelos):
        return None, "modelo_faltante"
    pose = modelos[mi][1]

    por_mol = mf.coords_pose_a_por_mol(pose, mapa)
    heavy = [i for i, a in enumerate(crystal.GetAtoms())
             if a.GetAtomicNum() > 1]
    faltan = [i for i in heavy if i not in por_mol]
    if faltan:
        # Guardia conservadora heredada de Fase 0: malla incompleta.
        return None, "mapeo_incompleto"
    lig_coords = np.array([por_mol[i] for i in heavy], dtype=np.float32)

    lig = lig_grafo_pose(pid, lig_coords)
    prot = prot_por_pose(pid, lig_coords)
    if prot is None:
        return None, "pocket_sin_ca"
    cross = _build_cross_edges(lig[1], prot.pos)

    vina = r.get("vina_score")
    if vina is None or (isinstance(vina, float) and np.isnan(vina)):
        vina = SENTINEL_VINA

    clave = f"{pid}|{source}|{stem}|{mi}"
    data = Data(
        x=lig[0],
        lig_pos=lig[1],
        ligand_edge_index=lig[2],
        prot_x=prot.x,
        prot_pos=prot.pos,
        prot_edge_index=prot.edge_index,
        cross_edge_index=cross,
        global_feat=torch.tensor([float(vina)], dtype=torch.float32),
        y_rmsd=float(r["rmsd"]),
        pid=pid,
        group_size=int(group_sizes[pid]),
        source=source,
        file_stem=stem,
        model_idx=mi,
        key=clave,
    )
    return data, None


# ───────────────────────── flujo principal ──────────────────────────────────

def cargar_registros(split: str) -> list[dict]:
    """Registros del JSONL en orden canonico (pid, source, stem, model)."""
    path = DATASET_DIR / f"poses_{split}.jsonl"
    regs = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()
            if l.strip()]
    regs.sort(key=lambda r: (r["pid"], r["source"], r["file_stem"],
                             r["model_idx"]))
    return regs


def construir_split(split: str, prog: dict, t0: float) -> None:
    regs = cargar_registros(split)
    st = prog["splits"][split]
    if st.get("status") == "completo" and SPLIT_ARCHIVOS[split].exists():
        print(f"  [{split}] ya completo ({len(regs)} registros).")
        return
    group_sizes: dict = defaultdict(int)
    for r in regs:
        group_sizes[r["pid"]] += 1

    parcial_path = SPLIT_ARCHIVOS[split].with_suffix(".pt.partial")
    lista = []
    if parcial_path.exists():
        lista = torch.load(parcial_path, weights_only=False)
    hechos = st["records"]
    n_hechos_previos = sum(1 for v in hechos.values() if v == "hecho")
    if len(lista) != n_hechos_previos:
        # Estado parcial inconsistente (archivo corrupto o edicion manual):
        # se descarta el parcial y se reconstruye el split desde cero.
        lista = []
        hechos = {}
        st["records"] = {}
        print(f"  [{split}] parcial inconsistente: reinicio del split.")

    n_excluidos = 0
    for i, r in enumerate(regs):
        clave = f"{r['pid']}|{r['source']}|{r['file_stem']}|{r['model_idx']}"
        if clave in hechos:
            continue
        data, razon = construir_grafo(r, group_sizes)
        if data is not None:
            lista.append(data)
            hechos[clave] = "hecho"
        else:
            hechos[clave] = "excluido"
            prog["excluidos"][clave] = razon
            n_excluidos += 1
        if len(lista) % LOTE_PARCIAL == 0:
            torch.save(lista, parcial_path)
            guardar_progreso(prog)
            print(f"  [{split}] {len(lista)}/{len(regs)} grafos "
                  f"({time.monotonic() - t0:.0f}s)")

    torch.save(lista, parcial_path)
    final_tmp = SPLIT_ARCHIVOS[split].with_suffix(".pt.tmp")
    torch.save(lista, final_tmp)
    import os
    os.replace(final_tmp, SPLIT_ARCHIVOS[split])
    parcial_path.unlink(missing_ok=True)
    st["status"] = "completo"
    st["n_registros"] = len(regs)
    st["n_grafos"] = len(lista)
    st["n_complejos"] = len({d.pid for d in lista})
    guardar_progreso(prog)
    print(f"  [{split}] completo: {len(lista)} grafos, "
          f"{len({d.pid for d in lista})} complejos, "
          f"{n_excluidos} excluidos este paso.")


def main() -> None:
    configurar_salida()
    t0 = time.monotonic()
    print("== Fase 2: construccion de grafos pose-selector (Ruta C) ==")
    prog = cargar_progreso()
    if prog.get("status") == "completo":
        print("Grafos ya completos (graphs_progress.json: status=completo).")
        return
    for split in ("train", "val", "test"):
        construir_split(split, prog, t0)
    prog["status"] = "completo"
    prog["finalizado"] = ahora_iso()
    prog["duracion_total_s"] = round(time.monotonic() - t0, 1)
    guardar_progreso(prog)
    n_exc = sum(1 for v in prog["excluidos"].values())
    print(f"== Grafos completos: {time.monotonic() - t0:.0f}s, "
          f"{n_exc} registros excluidos en total ==")


if __name__ == "__main__":
    main()
