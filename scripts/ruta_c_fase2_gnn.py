# -*- coding: utf-8 -*-
"""
ruta_c_fase2_gnn.py — Ruta C, Fase 2 (docs/42_RUTA_C_PROTOCOLO.md).

Entrena y evalua el GNN v1 PoseSelector contra el campeon v0.6 (XGBoost
top-1 test 0.6596, holdout congelado de 47 complejos).

Arquitectura: encoders reutilizados de rescoring/gnn_v2/models.py
(ProteinEncoder GAT-Ca 24->64 2 capas, LigandEncoder GIN 38->64 3 capas,
CrossAttention con bias de distancia y tipo de residuo), pooling global
Set2Set (precedente GNNv2Classifier), fusion opcional del score Vina crudo
(flag use_vina; ablacion R-RC1) y dos cabezas MLP: score (native-likeness,
usada para la seleccion) y rmsd auxiliar. Dropout 0.3 en los MLP y activo
en inferencia para incertidumbre MC-dropout (mc_samples=20, precedente
GNNv2Classifier.predict_proba). Restriccion: params <= 1.2 M (se reporta).

Perdida (C3, por complejo): para cada par (i, j) con rmsd_i <= rmsd_j
(empates incluidos) margen = clip(0.3 + 0.5*(rmsd_j - rmsd_i), 0.3, 2.0);
L_pair = mean(max(0, margen - (s_i - s_j))) normalizada por el total de
pares. Auxiliar: L_aux = MSE(rmsd_head, rmsd) sobre las poses con rmsd
valido, lambda = 0.5. Los grupos de 1 pose solo reciben la auxiliar.

Optimizacion de computo (6 GB VRAM): en cada epoca se hace UN forward por
pose sobre todo el split de entrenamiento (lotes de 64 poses, grafo de
autograd retenido) y la perdida pairwise se calcula VECTORIZADA sobre
TODOS los pares en un unico backward. El gradiente es identico al de lotes
de pares (la media de pares es una combinacion lineal de los scores), pero
cada grafo se recorre UNA sola vez en backward. Early stop con paciencia
12 sobre el top-1 crystal-like de val (rmsd seleccionado <= 2.0 A).

Reanudable: data/pose_selector_dataset/train_gnn_progress.json + checkpoints
gnn_v1_best.pt (modelo con contexto Vina) y gnn_v1_novina_best.pt (ablacion
R-RC1). Artefacto: scripts/artifacts_ruta_c_fase2.json (escritura
incremental temp + os.replace).
"""

from __future__ import annotations

import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from torch import nn

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from rescoring.gnn_v2.models import (  # noqa: E402
    CrossAttention,
    LigandEncoder,
    ProteinEncoder,
)
from torch_geometric.data import Batch, Data  # noqa: E402
from torch_geometric.nn import Set2Set  # noqa: E402

DATASET_DIR = PROJECT_ROOT / "data" / "pose_selector_dataset"
ARTIFACTOS = PROJECT_ROOT / "scripts" / "artifacts_ruta_c_fase2.json"
CKPTS = {"v1": DATASET_DIR / "gnn_v1_best.pt",
         "novina": DATASET_DIR / "gnn_v1_novina_best.pt"}
PROGRESO_ENTRENO = DATASET_DIR / "train_gnn_progress.json"

SEMILLA = 42
HIDDEN = 64
DROPOUT = 0.3
SET2SET_STEPS = 4
LR = 1e-3
WEIGHT_DECAY = 1e-5
MAX_EPOCHS = 60
PACENCIA = 12
LAMBDA_AUX = 0.5
BATCH_POSES = 64
MC_SAMPLES = 20
UMBRAL_POSITIVA = 2.0
TOP1_V06_TEST = 0.6596
TOP1_VINA_TEST = 0.5319
LIMITE_PARAMS = 1_200_000

ETAPAS = (
    {"nombre": "v1", "use_vina": True,
     "desc": "GNN v1 (contexto Vina, modelo principal)"},
    {"nombre": "novina", "use_vina": False,
     "desc": "GNN v1 sin contexto Vina (ablacion R-RC1)"},
)


# ───────────────────────── utilidades ───────────────────────────────────────

def configurar_salida() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def ahora_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def guardar_artefacto(art: dict, etapa: str) -> None:
    art["_ultima_etapa"] = etapa
    tmp = ARTIFACTOS.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(art, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    os.replace(tmp, ARTIFACTOS)


def guardar_progreso_entreno(prog: dict) -> None:
    tmp = PROGRESO_ENTRENO.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(prog, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    os.replace(tmp, PROGRESO_ENTRENO)


def cargar_progreso_entreno() -> dict:
    if PROGRESO_ENTRENO.exists():
        try:
            return json.loads(PROGRESO_ENTRENO.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"etapas": {}}


def chunks(lista, n):
    for i in range(0, len(lista), n):
        yield lista[i:i + n]


# ───────────────────────── modelo ───────────────────────────────────────────

class PoseSelector(nn.Module):
    """GNN v1 PoseSelector: encoders de gnn_v2 + Set2Set + contexto Vina
    opcional + cabezas score/rmsd."""

    def __init__(self, prot_in: int = 24, lig_in: int = 38,
                 hidden_dim: int = HIDDEN, dropout: float = DROPOUT,
                 set2set_steps: int = SET2SET_STEPS, use_vina: bool = True):
        super().__init__()
        self.use_vina = use_vina
        self.prot_encoder = ProteinEncoder(in_channels=prot_in,
                                           hidden_dim=hidden_dim,
                                           dropout=dropout)
        self.lig_encoder = LigandEncoder(in_channels=lig_in,
                                         hidden_dim=hidden_dim,
                                         dropout=dropout)
        self.cross_attn = CrossAttention(hidden_dim=hidden_dim,
                                         dropout=dropout)
        self.lig_pool = Set2Set(hidden_dim, processing_steps=set2set_steps)
        self.prot_pool = Set2Set(hidden_dim, processing_steps=set2set_steps)
        score_in = hidden_dim * 4 + (1 if use_vina else 0)
        self.score_head = nn.Sequential(
            nn.Linear(score_in, hidden_dim), nn.ELU(), nn.Dropout(dropout),
            nn.Linear(hidden_dim, hidden_dim // 2), nn.ELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim // 2, 1))
        self.rmsd_head = nn.Sequential(
            nn.Linear(hidden_dim * 4, hidden_dim), nn.ELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, hidden_dim // 2), nn.ELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim // 2, 1))

    def forward(self, prot_x, prot_edge_index, lig_x, lig_edge_index,
                cross_edge_index, lig_pos, prot_pos, lig_batch, prot_batch,
                global_feat=None):
        h_prot = self.prot_encoder(prot_x, prot_edge_index)
        h_lig = self.lig_encoder(lig_x, lig_edge_index)
        h_lig = self.cross_attn(h_lig, h_prot, cross_edge_index, lig_pos,
                                prot_pos, prot_x)
        lig_global = self.lig_pool(h_lig, lig_batch)
        prot_global = self.prot_pool(h_prot, prot_batch)
        emb = torch.cat([lig_global, prot_global], dim=-1)
        rmsd_pred = self.rmsd_head(emb).squeeze(-1)
        if self.use_vina:
            if global_feat is None:
                global_feat = torch.zeros(emb.size(0), 1, device=emb.device)
            emb = torch.cat([emb, global_feat.view(-1, 1)], dim=-1)
        score = self.score_head(emb).squeeze(-1)
        return score, rmsd_pred


def contar_params(modelo: nn.Module) -> int:
    return sum(p.numel() for p in modelo.parameters() if p.requires_grad)


# ───────────────────────── datos ────────────────────────────────────────────

def cargar_dataset() -> dict:
    out = {}
    for s in ("train", "val", "test"):
        datos = torch.load(DATASET_DIR / f"gnn_{s}.pt", weights_only=False)
        datos.sort(key=lambda d: (d.pid, d.key))
        out[s] = datos
    return out


def colacionar(data_list: list) -> dict:
    """Bachea un lote de Data en un dicto estilo train_gnn_v31 (los
    edge_index cruzados se reindexan a mano)."""
    ligs = [Data(x=d.x, pos=d.lig_pos, edge_index=d.ligand_edge_index)
            for d in data_list]
    prots = [Data(x=d.prot_x, pos=d.prot_pos, edge_index=d.prot_edge_index)
             for d in data_list]
    lig_batch = Batch.from_data_list(ligs)
    prot_batch = Batch.from_data_list(prots)
    cross_list = []
    po, lo = 0, 0
    for d in data_list:
        c = d.cross_edge_index
        if c.numel() > 0:
            c2 = c.clone()
            c2[0] += lo
            c2[1] += po
            cross_list.append(c2)
        lo += d.x.size(0)
        po += d.prot_x.size(0)
    cross = (torch.cat(cross_list, dim=1) if cross_list
             else torch.empty((2, 0), dtype=torch.long))
    global_feat = torch.stack([d.global_feat for d in data_list])
    return {"prot_x": prot_batch.x, "prot_edge_index": prot_batch.edge_index,
            "prot_pos": prot_batch.pos, "prot_batch": prot_batch.batch,
            "lig_x": lig_batch.x, "lig_edge_index": lig_batch.edge_index,
            "lig_pos": lig_batch.pos, "lig_batch": lig_batch.batch,
            "cross_edge_index": cross, "global_feat": global_feat}


def a_dispositivo(b: dict, device) -> dict:
    return {k: v.to(device) if torch.is_tensor(v) else v for k, v in b.items()}


def grupos_de(datos: list) -> tuple[list, list]:
    """Conteos por pid en orden de filas + lista de pids (contiguos)."""
    grupos, pids = [], []
    n = 0
    for d in datos:
        if not pids or d.pid != pids[-1]:
            if pids:
                grupos.append(n)
                n = 0
            pids.append(d.pid)
        n += 1
    if n:
        grupos.append(n)
    return grupos, pids


def construir_pares(y: np.ndarray, grupos: list) -> tuple:
    """Todos los pares ordenados (i, j), i != j, con rmsd_i <= rmsd_j
    (empates incluidos: ambas direcciones califican) + margenes
    clip(0.3 + 0.5*(rmsd_j - rmsd_i), 0.3, 2.0)."""
    ii, jj, margs = [], [], []
    ini = 0
    for g in grupos:
        if g < 2:
            ini += g
            continue
        yy = y[ini:ini + g]
        m = yy[:, None] <= yy[None, :]
        m[np.arange(g), np.arange(g)] = False
        a, b = np.nonzero(m)
        if a.size:
            ii.append(a + ini)
            jj.append(b + ini)
            margs.append(np.clip(0.3 + 0.5 * (yy[b] - yy[a]), 0.3, 2.0))
        ini += g
    return (np.concatenate(ii), np.concatenate(jj), np.concatenate(margs))


def forward_todo(modelo, datos, device, modo_entreno: bool):
    """Forward de todas las poses en lotes. En modo entrenamiento devuelve
    tensores con grafo de autograd retenido; en evaluacion, numpy
    desacoplado."""
    scores, rpreds = [], []
    if modo_entreno:
        modelo.train()
        for ch in chunks(datos, BATCH_POSES):
            b = a_dispositivo(colacionar(ch), device)
            s, r = modelo(b["prot_x"], b["prot_edge_index"], b["lig_x"],
                          b["lig_edge_index"], b["cross_edge_index"],
                          b["lig_pos"], b["prot_pos"], b["lig_batch"],
                          b["prot_batch"], b["global_feat"])
            scores.append(s)
            rpreds.append(r)
        return torch.cat(scores), torch.cat(rpreds)
    modelo.eval()
    with torch.no_grad():
        for ch in chunks(datos, BATCH_POSES):
            b = a_dispositivo(colacionar(ch), device)
            s, r = modelo(b["prot_x"], b["prot_edge_index"], b["lig_x"],
                          b["lig_edge_index"], b["cross_edge_index"],
                          b["lig_pos"], b["prot_pos"], b["lig_batch"],
                          b["prot_batch"], b["global_feat"])
            scores.append(s.cpu())
            rpreds.append(r.cpu())
    return (torch.cat(scores).numpy(), torch.cat(rpreds).numpy())


# ───────────────────────── evaluacion ───────────────────────────────────────

def metricas_por_pid(scores: np.ndarray, datos: list, pids: list) -> dict:
    """Top-1 crystal-like por complejo (argmax del score, empates -> primer
    orden canonico), RMSD mediano de la pose seleccionada y Spearman(score,
    rmsd) promedio por complejo (>= 2 poses no constantes)."""
    from scipy.stats import spearmanr

    por_pid = defaultdict(list)
    for d, s in zip(datos, scores):
        por_pid[d.pid].append((d, float(s)))
    top1_ok = 0
    rmsds_sel = []
    spears = []
    for pid in pids:
        filas = por_pid[pid]
        mejor = max(filas, key=lambda ds: ds[1])[0]
        rmsds_sel.append(mejor.y_rmsd)
        if float(mejor.y_rmsd) <= UMBRAL_POSITIVA:
            top1_ok += 1
        if len(filas) >= 2:
            ps = np.array([s for _, s in filas])
            rs = np.array([d.y_rmsd for d, _ in filas])
            if np.std(ps) > 1e-12 and np.std(rs) > 1e-12:
                sp = spearmanr(ps, rs).correlation
                if sp is not None and not np.isnan(sp):
                    spears.append(float(sp))
    n = len(pids)
    return {"top1_rate": round(top1_ok / n, 4),
            "mediana_rmsd": round(float(np.median(rmsds_sel)), 3),
            "spearman_pred_vs_rmsd_media": (round(float(np.mean(spears)), 4)
                                            if spears else None),
            "spearman_abs_media": (round(float(np.mean(np.abs(spears))), 4)
                                   if spears else None),
            "n_complejos": n, "n_complejos_spearman": len(spears)}


def evaluar(modelo, datos, pids, device) -> dict:
    scores, _ = forward_todo(modelo, datos, device, modo_entreno=False)
    return metricas_por_pid(scores, datos, pids)


def evaluar_mc(modelo, datos, pids, device, mc_samples: int = MC_SAMPLES) -> dict:
    """MC-dropout sobre test: matriz (N, mc) de scores; por complejo se
    elige la pose por la media y se reporta la varianza del score de la
    pose seleccionada a traves de las muestras."""
    modelo.train()
    cols = []
    with torch.no_grad():
        for _ in range(mc_samples):
            col = []
            for ch in chunks(datos, BATCH_POSES):
                b = a_dispositivo(colacionar(ch), device)
                s, _ = modelo(b["prot_x"], b["prot_edge_index"],
                              b["lig_x"], b["lig_edge_index"],
                              b["cross_edge_index"], b["lig_pos"],
                              b["prot_pos"], b["lig_batch"],
                              b["prot_batch"], b["global_feat"])
                col.append(s.cpu())
            cols.append(torch.cat(col).numpy())
    S = np.stack(cols, axis=1)
    medias = S.mean(axis=1)
    por_pid = defaultdict(list)
    for k, d in enumerate(datos):
        por_pid[d.pid].append(k)
    var_sel, std_sel = [], []
    for pid in pids:
        idxs = por_pid[pid]
        sel = idxs[int(np.argmax([medias[i] for i in idxs]))]
        var_sel.append(float(S[sel].var()))
        std_sel.append(float(S[sel].std()))
    return {"varianza_media_pose_seleccionada": round(float(np.mean(var_sel)), 5),
            "varianza_mediana_pose_seleccionada": round(float(np.median(var_sel)), 5),
            "std_media_pose_seleccionada": round(float(np.mean(std_sel)), 5),
            "n_complejos": len(pids), "mc_samples": mc_samples}


def baseline_vina(datos: list, pids: list) -> dict:
    """Por complejo: pose de MENOR vina_score (empates -> primer orden
    canonico), replica del baseline de Fase 1 sobre el dataset de grafos."""
    por_pid = defaultdict(list)
    for d in datos:
        por_pid[d.pid].append(d)
    rmsds_sel = []
    for pid in pids:
        filas = por_pid[pid]
        mejor = min(enumerate(filas),
                    key=lambda kd: (float(kd[1].global_feat[0]), kd[0]))[1]
        rmsds_sel.append(float(mejor.y_rmsd))
    return {"top1_rate": round(float(np.mean([s <= UMBRAL_POSITIVA
                                              for s in rmsds_sel])), 4),
            "mediana_rmsd": round(float(np.median(rmsds_sel)), 3),
            "n_complejos": len(pids)}


def smoke_cpu(use_vina: bool, ckpt_path: Path, datos: list) -> dict:
    """Inferencia CPU (requisito de produccion): ms por pose sobre val."""
    modelo = PoseSelector(use_vina=use_vina)
    ck = torch.load(ckpt_path, weights_only=False, map_location="cpu")
    modelo.load_state_dict(ck["modelo"])
    modelo.eval()
    t0 = time.monotonic()
    with torch.no_grad():
        for ch in chunks(datos, 32):
            b = colacionar(ch)
            modelo(b["prot_x"], b["prot_edge_index"], b["lig_x"],
                   b["lig_edge_index"], b["cross_edge_index"], b["lig_pos"],
                   b["prot_pos"], b["lig_batch"], b["prot_batch"],
                   b["global_feat"])
    t = time.monotonic() - t0
    return {"n_poses": len(datos),
            "duracion_s": round(t, 2),
            "ms_por_pose": round(1000.0 * t / max(len(datos), 1), 2)}


# ───────────────────────── entrenamiento ────────────────────────────────────

def entrenar(etapa: dict, train, val, pids_val, device,
             i_idx, j_idx, marg_dev, y_train_dev, prog: dict) -> dict:
    """Entrena una etapa con reanudacion. Devuelve el historial."""
    nombre = etapa["nombre"]
    ckpt_path = CKPTS[nombre]
    st = prog.setdefault(nombre, {"status": "pendiente", "epoch": -1,
                                  "mejor_val_top1": -1.0, "paciencia": 0,
                                  "historial": [], "duracion_s": 0.0,
                                  "reanudado": False})
    if st.get("status") == "completo" and ckpt_path.exists():
        print(f"  [{nombre}] entrenamiento ya completo "
              f"(mejor val top1 = {st['mejor_val_top1']}).")
        return st["historial"]

    modelo = PoseSelector(use_vina=etapa["use_vina"]).to(device)
    n_params = contar_params(modelo)
    optim = torch.optim.Adam(modelo.parameters(), lr=LR,
                             weight_decay=WEIGHT_DECAY)
    ep_inicio = 0
    if ckpt_path.exists() and st.get("status") == "en_progreso":
        ck = torch.load(ckpt_path, weights_only=False, map_location=device)
        modelo.load_state_dict(ck["modelo"])
        optim.load_state_dict(ck["optimizador"])
        ep_inicio = ck["epoch"] + 1
        st["reanudado"] = True
        print(f"  [{nombre}] reanudando desde epoca {ep_inicio} "
              f"(mejor val top1 = {st['mejor_val_top1']}).")
    st["status"] = "en_progreso"
    st["n_params"] = n_params
    guardar_progreso_entreno(prog)
    print(f"  [{nombre}] {etapa['desc']} | params: {n_params:,} | "
          f"pares train: {len(i_idx):,}")

    t0 = time.monotonic()
    for ep in range(ep_inicio, MAX_EPOCHS):
        t_ep = time.monotonic()
        modelo.train()
        optim.zero_grad()
        s, r = forward_todo(modelo, train, device, modo_entreno=True)
        perdida_par = F.relu(marg_dev - (s[i_idx] - s[j_idx])).mean()
        perdida_aux = F.mse_loss(r, y_train_dev)
        perdida = perdida_par + LAMBDA_AUX * perdida_aux
        perdida.backward()
        torch.nn.utils.clip_grad_norm_(modelo.parameters(), 1.0)
        optim.step()
        met_val = evaluar(modelo, val, pids_val, device)
        if met_val["top1_rate"] > st["mejor_val_top1"]:
            st["mejor_val_top1"] = met_val["top1_rate"]
            st["paciencia"] = 0
            torch.save({"modelo": modelo.state_dict(),
                        "optimizador": optim.state_dict(),
                        "epoch": ep, "config": {"use_vina": etapa["use_vina"],
                                                "hidden": HIDDEN,
                                                "dropout": DROPOUT,
                                                "set2set_steps": SET2SET_STEPS,
                                                "lr": LR,
                                                "weight_decay": WEIGHT_DECAY,
                                                "lambda_aux": LAMBDA_AUX,
                                                "semilla": SEMILLA},
                        "n_params": n_params, "val": met_val}, ckpt_path)
        else:
            st["paciencia"] += 1
        st["epoch"] = ep
        st["historial"].append({
            "epoch": ep, "loss_pair": round(float(perdida_par.item()), 4),
            "loss_aux": round(float(perdida_aux.item()), 4),
            "loss_total": round(float(perdida.item()), 4),
            "val_top1": met_val["top1_rate"],
            "val_mediana": met_val["mediana_rmsd"],
            "val_spearman": met_val["spearman_pred_vs_rmsd_media"],
            "t_s": round(time.monotonic() - t_ep, 1)})
        guardar_progreso_entreno(prog)
        print(f"  [{nombre}] ep {ep}: pair {float(perdida_par.item()):.4f} "
              f"aux {float(perdida_aux.item()):.4f} | val top1 "
              f"{met_val['top1_rate']} mediana {met_val['mediana_rmsd']} "
              f"| paciencia {st['paciencia']}/{PACENCIA} "
              f"({time.monotonic() - t_ep:.0f}s)")
        if st["paciencia"] >= PACENCIA:
            print(f"  [{nombre}] early stop en epoca {ep} "
                  f"(paciencia {PACENCIA} agotada).")
            break
    st["status"] = "completo"
    st["duracion_s"] = round(time.monotonic() - t0, 1)
    guardar_progreso_entreno(prog)
    return st["historial"]


# ───────────────────────── flujo principal ──────────────────────────────────

def main() -> None:
    configurar_salida()
    t0 = time.monotonic()
    print("== Ruta C Fase 2: GNN v1 PoseSelector (docs/42) ==")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"  dispositivo: {device} "
          f"({torch.cuda.get_device_name(0) if device.type == 'cuda' else 'CPU'})")
    torch.manual_seed(SEMILLA)
    if device.type == "cuda":
        torch.cuda.manual_seed(SEMILLA)

    datos = cargar_dataset()
    for s in ("train", "val", "test"):
        n = len({d.pid for d in datos[s]})
        print(f"  {s}: {len(datos[s])} grafos, {n} complejos")
    grupos_train, pids_train = grupos_de(datos["train"])
    _gv, pids_val = grupos_de(datos["val"])
    _gt, pids_test = grupos_de(datos["test"])

    y_train = np.array([d.y_rmsd for d in datos["train"]], dtype=np.float64)
    i_arr, j_arr, marg = construir_pares(y_train, grupos_train)
    i_idx = torch.tensor(i_arr, dtype=torch.long, device=device)
    j_idx = torch.tensor(j_arr, dtype=torch.long, device=device)
    marg_dev = torch.tensor(marg, dtype=torch.float32, device=device)
    y_train_dev = torch.tensor(y_train, dtype=torch.float32, device=device)
    print(f"  pares de entrenamiento (i<=j, empates incluidos): {len(i_arr):,}")

    prog = cargar_progreso_entreno()
    art: dict = {
        "generated_at": ahora_iso(),
        "protocolo": "docs/42_RUTA_C_PROTOCOLO.md",
        "fase": "2 (GNN v1 PoseSelector)",
        "hipotesis": ("un score de native-likeness APRENDIDO con perdida de "
                      "ranking pairwise intra-complejo y margenes "
                      "proporcionales a Delta-RMSD supera al campeon v0.6 "
                      "(0.6596) en el holdout congelado"),
        "gate_criterio": f"gnn_v1_test_top1 > {TOP1_V06_TEST} (top-1 v0.6)",
        "config": {
            "arquitectura": {
                "prot_encoder": "GAT-Ca 24->64, 4 cabezas, 2 capas (models.py)",
                "lig_encoder": "GIN 38->64, 3 capas (models.py)",
                "cross_attention": "ligando->proteina, bias distancia 3.5 A "
                                   "+ bias tipo residuo (models.py)",
                "pooling": "Set2Set x2 (ligando+proteina), 4 pasos",
                "fusion_contexto": "concat vina_score crudo (flag use_vina)",
                "score_head": "MLP 257/256->64->32->1 (native-likeness)",
                "rmsd_head": "MLP 256->64->32->1 (auxiliar)",
                "dropout": DROPOUT,
            },
            "perdida": {
                "pairwise": ("por complejo, todos los pares (i,j) con "
                             "rmsd_i <= rmsd_j (empates incluidos, ambas "
                             "direcciones), i != j; normalizada por total "
                             "de pares"),
                "margen": "clip(0.3 + 0.5*(rmsd_j - rmsd_i), 0.3, 2.0)",
                "auxiliar": "MSE(rmsd_head, rmsd)",
                "lambda_aux": LAMBDA_AUX,
                "grupos_1_pose": "solo auxiliar",
            },
            "optimizacion": {
                "opt": "Adam", "lr": LR, "weight_decay": WEIGHT_DECAY,
                "max_epochs": MAX_EPOCHS, "paciencia_val_top1": PACENCIA,
                "batch_poses": BATCH_POSES, "semilla": SEMILLA,
                "dispositivo": str(device),
                "esquema_computo": ("1 forward por pose por epoca (lote 64, "
                                    "grafo retenido) + perdida pairwise "
                                    "vectorizada sobre TODOS los pares en un "
                                    "solo backward; gradiente equivalente a "
                                    "lotes de pares"),
                "n_pares_train": int(len(i_arr)),
            },
            "mc_dropout": {"mc_samples": MC_SAMPLES,
                           "dropout_activo_en_inferencia": True},
            "umbral_pose_positiva_angstrom": UMBRAL_POSITIVA,
            "split": "holdout congelado Fase 0 (scaffold-disjoint, seed 42)",
        },
        "vina_baseline_recomputado": {
            s: baseline_vina(datos[s], {"train": pids_train, "val": pids_val,
                                        "test": pids_test}[s])
            for s in ("train", "val", "test")},
    }
    guardar_artefacto(art, "config")
    print("  vina recomputado:", {s: art["vina_baseline_recomputado"][s]
                                  ["top1_rate"]
                                  for s in ("train", "val", "test")})

    historiales = {}
    for etapa in ETAPAS:
        hist = entrenar(etapa, datos["train"], datos["val"], pids_val,
                        device, i_idx, j_idx, marg_dev, y_train_dev, prog)
        historiales[etapa["nombre"]] = hist
        art[f"entrenamiento_{etapa['nombre']}"] = {
            "descripcion": etapa["desc"],
            "n_params": prog[etapa["nombre"]]["n_params"],
            "limite_params": LIMITE_PARAMS,
            "params_dentro_limite": prog[etapa["nombre"]]["n_params"]
                <= LIMITE_PARAMS,
            "epochs_ejecutadas": len(hist),
            "mejor_epoch": (min((h["epoch"] for h in hist
                                if h["val_top1"] == prog[etapa["nombre"]]
                                ["mejor_val_top1"]), default=None)),
            "mejor_val_top1": prog[etapa["nombre"]]["mejor_val_top1"],
            "early_stopped": (prog[etapa["nombre"]]["paciencia"] >= PACENCIA),
            "duracion_s": prog[etapa["nombre"]]["duracion_s"],
            "reanudado": prog[etapa["nombre"]].get("reanudado", False),
            "val_top1_cada_5": {h["epoch"]: h["val_top1"] for h in hist
                                if h["epoch"] % 5 == 0},
            "historial": hist,
        }
        guardar_artefacto(art, f"entrenado_{etapa['nombre']}")

    # ── Evaluacion final (val + test + MC test) para ambos modelos ──
    metricas = {}
    for etapa in ETAPAS:
        nombre = etapa["nombre"]
        modelo = PoseSelector(use_vina=etapa["use_vina"])
        ck = torch.load(CKPTS[nombre], weights_only=False,
                        map_location=device)
        modelo.load_state_dict(ck["modelo"])
        modelo = modelo.to(device)
        met = {}
        for s, pids in (("val", pids_val), ("test", pids_test)):
            met[s] = evaluar(modelo, datos[s], pids, device)
        met["mc_test"] = evaluar_mc(modelo, datos["test"], pids_test, device)
        met["smoke_cpu"] = smoke_cpu(etapa["use_vina"], CKPTS[nombre],
                                     datos["val"])
        metricas[nombre] = met
        art[f"evaluacion_{nombre}"] = met
        guardar_artefacto(art, f"evaluado_{nombre}")
        print(f"  [{nombre}] val top1 {met['val']['top1_rate']} | "
              f"test top1 {met['test']['top1_rate']} | "
              f"test mediana {met['test']['mediana_rmsd']} | "
              f"MC var media {met['mc_test']['varianza_media_pose_seleccionada']}")

    # ── Tabla comparativa con fases previas ──
    previos = {}
    for nombre_archivo in ("artifacts_ruta_c_fase1.json",
                           "artifacts_ruta_c_fase1_5.json",
                           "artifacts_ruta_c_fase1_6.json"):
        p = PROJECT_ROOT / "scripts" / nombre_archivo
        if p.exists():
            try:
                previos[nombre_archivo] = json.loads(
                    p.read_text(encoding="utf-8"))
            except Exception:
                pass
    a1 = previos.get("artifacts_ruta_c_fase1.json", {})
    a5 = previos.get("artifacts_ruta_c_fase1_5.json", {})
    a6 = previos.get("artifacts_ruta_c_fase1_6.json", {})
    tabla = {}
    for split in ("val", "test"):
        tabla[split] = {
            "vina_top1": a1.get("vina_baseline", {}).get(split, {}).get(
                "top1_rate"),
            "vina_mediana": a1.get("vina_baseline", {}).get(split, {}).get(
                "mediana_rmsd"),
            "v0_top1": a1.get("v0", {}).get(split, {}).get("top1_rate"),
            "v0_mediana": a1.get("v0", {}).get(split, {}).get("mediana_rmsd"),
            "v05_top1": a5.get("v05", {}).get(split, {}).get("top1_rate"),
            "v05_mediana": a5.get("v05", {}).get(split, {}).get(
                "mediana_rmsd"),
            "v06B_top1": a6.get("modelo_B", {}).get(split, {}).get(
                "top1_rate"),
            "v06B_mediana": a6.get("modelo_B", {}).get(split, {}).get(
                "mediana_rmsd"),
            "gnn_v1_top1": metricas["v1"][split]["top1_rate"],
            "gnn_v1_mediana": metricas["v1"][split]["mediana_rmsd"],
            "gnn_v1_spearman": metricas["v1"][split][
                "spearman_pred_vs_rmsd_media"],
            "gnn_novina_top1": metricas["novina"][split]["top1_rate"],
            "gnn_novina_mediana": metricas["novina"][split]["mediana_rmsd"],
            "gnn_novina_spearman": metricas["novina"][split][
                "spearman_pred_vs_rmsd_media"],
        }
    art["comparacion"] = tabla

    # ── Gate ──
    gnn_test = metricas["v1"]["test"]["top1_rate"]
    art["gate"] = {
        "criterio": f"gnn_v1_test_top1 > {TOP1_V06_TEST} (campeon v0.6)",
        "gnn_v1_top1_test": gnn_test,
        "v06B_top1_test": TOP1_V06_TEST,
        "vina_top1_test": TOP1_VINA_TEST,
        "delta_vs_v06B": round(gnn_test - TOP1_V06_TEST, 4),
        "resultado": "PASS" if gnn_test > TOP1_V06_TEST else "FAIL",
    }
    print(f"  Gate: {art['gate']['resultado']} "
          f"(GNN v1 {gnn_test} vs v0.6 {TOP1_V06_TEST})")

    # ── Refutacion R-RC1 ──
    novina_test = metricas["novina"]["test"]["top1_rate"]
    delta_rc1 = round(gnn_test - novina_test, 4)
    if abs(delta_rc1) <= 0.02:
        lectura = ("sin cambio material: el score aprendido NO depende del "
                   "contexto Vina — la senal grafo es autosuficiente para "
                   "la seleccion (no es mero re-ranking de energia)")
    else:
        lectura = ("cambio material: el contexto Vina aporta informacion a "
                   "la seleccion; la senal aprendida es parcialmente "
                   "complementaria al score de energia")
    art["refutacion_R_RC1"] = {
        "pregunta": "cambia el top-1 test al quitar el contexto vina_score?",
        "gnn_v1_top1_test": gnn_test,
        "gnn_novina_top1_test": novina_test,
        "delta": delta_rc1,
        "lectura": lectura,
    }
    print(f"  R-RC1: delta {delta_rc1} ({lectura[:60]}...)")

    art["caveats_honestos"] = [
        ("La perdida pairwise se retropropaga en UN solo backward "
         "vectorizado sobre todos los pares (no en lotes de 128 pares): el "
         "gradiente es matematicamente identico y cada grafo se recorre una "
         "vez en backward; es la unica desviacion del esquema literal del "
         "encargo, motivada por el costo computacional."),
        ("Val tiene solo 40 complejos: el early stop es ruidoso; la "
         "comparacion del gate es sobre el test congelado (47 complejos)."),
        ("MC-dropout usa dropout 0.3 activo en inferencia (modelo en modo "
         "train), precedente predict_proba de GNNv2Classifier; las "
         "varianzas son un proxy de incertidumbre, no calibradas."),
        ("Si el entrenamiento se reanudo tras un crash, la secuencia RNG "
         "difiere de una corrida ininterrumpida (se registra la bandera "
         "'reanudado' por etapa)."),
        ("El dataset de grafos se construyo re-resolviendo los archivos de "
         "poses originales con los MISMOS mapas serial->mol de Fase 0; los "
         "registros excluidos quedan registrados en graphs_progress.json."),
        ("group_size proviene de los JSONL de Fase 0 (poblacion completa "
         "del split); si algun registro quedo excluido en el grafo, el "
         "grupo evaluable es menor (caveat de cobertura)."),
        ("Vina recomputado sobre el dataset de grafos usa el orden canonico "
         "para desempates, igual que Fase 1."),
    ]
    art["duracion_total_s"] = round(time.monotonic() - t0, 1)
    guardar_artefacto(art, "completo")
    print(f"  artefacto: {ARTIFACTOS} ({art['duracion_total_s']}s)")


if __name__ == "__main__":
    main()
