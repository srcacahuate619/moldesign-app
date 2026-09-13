# -*- coding: utf-8 -*-
"""
ruta_c_fase2_gnn_v2.py — Ruta C, Fase 2.1: GNN v2 PoseSelector
(docs/42_RUTA_C_PROTOCOLO.md).

Segunda iteracion del selector de poses basado en grafos, contra el campeon
v0.6 (XGBoost top-1 test 0.6596, holdout congelado de 47 complejos). La GNN
v1 (ruta_c_fase2_gnn.py) fallo (0.4894) porque la perdida pairwise quedo
dominada por el MSE auxiliar (lambda 0.5) y el encoder no tenia relatividad
intra-complejo.

Cambios v2 (protocolo seccion 11.5):
  1. Warm-start contrastivo: el backbone (ProteinEncoder + LigandEncoder +
     CrossAttention + Set2Set, mismas clases de models.py) se inicializa con
     rescoring/artifacts/contrastive_v31_pretrained.pt por coincidencia de
     claves. Ese checkpoint se entreno con hidden_dim=128, por lo que el
     backbone v2 usa hidden 128 (no 64 como v1) para que TODAS las claves de
     encoder coincidan exactamente (53/57; las 4 de projection se descartan).
     Parametros siguen dentro del limite (<= 1.5 M).
  2. Rama ECIF: 152 features ECIF/Shell por pose (extractor del repositorio,
     feature_extractor.InteractionFeatureExtractor.extract_from_pose con
     skip_prolif=True — la MISMA definicion que produjo
     data/gnn_v31/ecif_pdbbind_docked.npz) -> MLP(152->64, ReLU).
  3. Rama contexto: por complejo (dentro de cada split, como v0.6), z-score
     y percentil de solo vina_score y cluster_density. Contexto principal:
     [vina_raw, z_vina, pct_vina, z_cluster, pct_cluster] (5 dims). Ablacion
     R-RC1 (novina): [cluster_raw, z_cluster, pct_cluster] (3 dims).
  4. Fusion: concat(graph_emb 512, ecif_emb 64, ctx) -> MLP(128, ReLU,
     dropout 0.3) -> cabeza score (native-likeness, seleccion) y cabeza
     rmsd auxiliar (ambas Linear(128,1)).
  5. Perdida: pairwise por complejo con margen
     clip(0.3 + 0.5*(rmsd_j - rmsd_i), 0.3, 2.0) (dominante) + MSE auxiliar
     sobre el rmsd CENTRADO POR COMPLEJO (rmsd - mediana del complejo) con
     lambda 0.1 (en v1 era 0.5 sobre rmsd crudo y domino el entrenamiento).
  6. MC-dropout conservado (dropout activo en inferencia, mc_samples=20).

Pipeline ECIF reanudable: data/pose_selector_dataset/ecif_152_progress.jsonl
(clave registro -> 152 floats + bandera ok). Registros sin ECIF computable:
se rellenan con 0.0 + bandera de mascara (se reporta el conteo).

Entrenamiento reanudable: data/pose_selector_dataset/train_gnn_v2_progress.json
+ checkpoints pose_selector_v2_best.pt / pose_selector_v2_novina_best.pt.
Artefacto: scripts/artifacts_ruta_c_fase2_1.json (escritura incremental).

Uso:
  python scripts/ruta_c_fase2_gnn_v2.py            # pipeline completo
  python scripts/ruta_c_fase2_gnn_v2.py --solo-ecif  # solo cache ECIF
"""

from __future__ import annotations

import argparse
import hashlib
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
sys.path.insert(0, str(PROJECT_ROOT / "rescoring"))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from rescoring.gnn_v2.models import (  # noqa: E402
    CrossAttention,
    LigandEncoder,
    ProteinEncoder,
)
from torch_geometric.data import Batch, Data  # noqa: E402
from torch_geometric.nn import Set2Set  # noqa: E402

DATASET_DIR = PROJECT_ROOT / "data" / "pose_selector_dataset"
PDBBIND = PROJECT_ROOT / "data" / "pdbbind"
WORK_V3 = PROJECT_ROOT / "scripts" / ".work_molflex_v3"
RUTA_A = PROJECT_ROOT / "tmp" / "ruta_a"
PRETRAINED = (PROJECT_ROOT / "rescoring" / "artifacts"
              / "contrastive_v31_pretrained.pt")
ARTIFACTOS = PROJECT_ROOT / "scripts" / "artifacts_ruta_c_fase2_1.json"
ECIF_CACHE = DATASET_DIR / "ecif_152_progress.jsonl"
CKPTS = {"v2": DATASET_DIR / "pose_selector_v2_best.pt",
         "novina": DATASET_DIR / "pose_selector_v2_novina_best.pt"}
PROGRESO_ENTRENO = DATASET_DIR / "train_gnn_v2_progress.json"
LOG_PATH = DATASET_DIR / "train_gnn_v2.log"

SEMILLA = 42
HIDDEN = 128          # requerido por el warm-start CL (checkpoint hidden=128)
DROPOUT = 0.3
SET2SET_STEPS = 4
ECIF_DIM = 152
ECIF_EMB = 64
FUSION_HIDDEN = 128
CTX_DIM = 5           # [vina_raw, z_vina, pct_vina, z_cluster, pct_cluster]
CTX_DIM_NOVINA = 3    # [cluster_raw, z_cluster, pct_cluster]
LR_ENC = 1e-3         # backbone + ecif
LR_HEAD = 3e-3        # fusion + cabezas
WEIGHT_DECAY = 1e-5
MAX_EPOCHS = 60
PACENCIA = 12
LAMBDA_AUX = 0.1
BATCH_POSES = 64
MC_SAMPLES = 20
UMBRAL_POSITIVA = 2.0
TOP1_V06_TEST = 0.6596
TOP1_VINA_TEST = 0.5319
LIMITE_PARAMS = 1_500_000

ETAPAS = (
    {"nombre": "v2", "ctx": "vina", "ctx_dim": CTX_DIM,
     "desc": "GNN v2 (contexto vina + cluster, warm-start CL, modelo principal)"},
    {"nombre": "novina", "ctx": "novina", "ctx_dim": CTX_DIM_NOVINA,
     "desc": "GNN v2 sin contexto vina (ablacion R-RC1)"},
)


# ───────────────────────── utilidades ───────────────────────────────────────

def configurar_salida() -> None:
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


def pr(msg: str) -> None:
    """Imprime y anexa al log de entrenamiento (durabilidad)."""
    print(msg, flush=True)
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(msg + "\n")
    except Exception:
        pass


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


def sha256_archivo(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for bloque in iter(lambda: fh.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


# ───────────────────────── registros congelados ─────────────────────────────

def clave_de(r: dict) -> str:
    return f"{r['pid']}|{r['source']}|{r['file_stem']}|{r['model_idx']}"


def cargar_registros(nombre: str) -> list[dict]:
    """Registros de un split en orden canonico (pid, fuente, stem, model)."""
    registros: list[dict] = []
    path = DATASET_DIR / f"poses_{nombre}.jsonl"
    for linea in path.read_text(encoding="utf-8").splitlines():
        if linea.strip():
            registros.append(json.loads(linea))
    registros.sort(key=lambda r: (r["pid"], r["source"], r["file_stem"],
                                  r["model_idx"]))
    return registros


def cargar_todos_los_registros() -> list[dict]:
    out: list[dict] = []
    for nombre in ("train", "val", "test"):
        out.extend(cargar_registros(nombre))
    return out


def grupos_por_pid(registros: list[dict]) -> tuple[list[int], list[str]]:
    grupos: list[int] = []
    pids_orden: list[str] = []
    n = 0
    for r in registros:
        if not pids_orden or r["pid"] != pids_orden[-1]:
            if pids_orden:
                grupos.append(n)
                n = 0
            pids_orden.append(r["pid"])
        n += 1
    if n:
        grupos.append(n)
    return grupos, pids_orden


# ───────────────────────── pipeline ECIF ────────────────────────────────────

def claves_ecif() -> list[str]:
    from feature_extractor import ALL_3D_FEATURES
    claves = [k for k in ALL_3D_FEATURES
              if k.startswith("shell_") or k.startswith("ecif_")]
    assert len(claves) == ECIF_DIM, f"esperaba 152, hay {len(claves)}"
    return claves


def modelos_de_archivo(texto: str) -> list[list[str]]:
    """Bloques ATOM/HETATM por MODEL del PDBQT de salida de Vina. Si el
    archivo no tiene marcadores MODEL (caso local_only), todo el archivo
    es un unico bloque."""
    bloques: list[list[str]] = []
    cur: list[str] = []
    hay_model = any(l.startswith("MODEL") for l in texto.splitlines())
    for l in texto.splitlines():
        if l.startswith("MODEL"):
            cur = []
        elif l.startswith(("ATOM", "HETATM")):
            cur.append(l)
        elif l.startswith("ENDMDL") and cur:
            bloques.append(cur)
            cur = []
    if not hay_model and cur:
        bloques.append(cur)
    return bloques


def ruta_archivo_poses(reg: dict) -> Path | None:
    pid, src, stem = reg["pid"], reg["source"], reg["file_stem"]
    if src == "flexible_redock":
        return PDBBIND / "vina_redock_work" / pid / f"{pid}_out.pdbqt"
    if src == "molflex":
        return WORK_V3 / pid / f"{stem}.pdbqt"
    if src == "ruta_a":
        return RUTA_A / pid / stem / "out.pdbqt"
    return None


def cargar_cache_ecif() -> tuple[dict, dict]:
    """Lee el cache existente. Devuelve (cabecera, {key: (vec, ok)})."""
    cabecera: dict = {}
    cache: dict = {}
    if not ECIF_CACHE.exists():
        return cabecera, cache
    try:
        for linea in ECIF_CACHE.read_text(encoding="utf-8").splitlines():
            if not linea.strip():
                continue
            reg = json.loads(linea)
            if reg.get("tipo") == "cabecera":
                cabecera = reg
                continue
            cache[reg["key"]] = (reg["ecif"], bool(reg.get("ok", False)))
    except Exception:
        return {}, {}
    return cabecera, cache


def construir_cache_ecif(registros: list[dict]) -> dict:
    """Computa el ECIF 152-dim de todos los registros (reanudable). Usa el
    extractor del repositorio (feature_extractor), la misma definicion que
    produjo ecif_pdbbind_docked.npz. Registros fallidos: 0.0 + ok=false."""
    from feature_extractor import InteractionFeatureExtractor

    resumen = {"fuente": "feature_extractor.InteractionFeatureExtractor."
                         "extract_from_pose(skip_prolif=True)",
               "reimplementado": False,
               "n_total": len(registros), "n_ok": 0, "n_fallo": 0,
               "n_reutilizado": 0, "t_s": 0.0, "cache": str(ECIF_CACHE)}
    cabecera, cache = cargar_cache_ecif()
    sha_splits = {n: sha256_archivo(DATASET_DIR / f"poses_{n}.jsonl")
                  for n in ("train", "val", "test")}
    claves = claves_ecif()
    valido = (cabecera.get("sha256_splits") == sha_splits
              and cabecera.get("n_features") == ECIF_DIM)
    if not valido:
        pr("  cache ECIF inexistente o invalido (sha256 distinto): se reinicia.")
        ECIF_CACHE.unlink(missing_ok=True)
        cache = {}
        with open(ECIF_CACHE, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"tipo": "cabecera", "version": 1,
                                 "n_features": ECIF_DIM,
                                 "feature_keys": claves,
                                 "sha256_splits": sha_splits,
                                 "extractor": resumen["fuente"],
                                 "generated_at": ahora_iso()}) + "\n")
            fh.flush()
    else:
        pr(f"  cache ECIF valido: {len(cache)} registros ya computados.")

    ext = InteractionFeatureExtractor()
    t0 = time.monotonic()
    texto_cache: dict[str, list[list[str]]] = {}
    prot_de = lambda pid: PDBBIND / pid / f"{pid}_protein.pdb"

    pendientes = [r for r in registros if clave_de(r) not in cache]
    n_nuevos_ok = n_nuevos_fallo = 0
    with open(ECIF_CACHE, "a", encoding="utf-8") as fh:
        for i, r in enumerate(pendientes):
            clave = clave_de(r)
            vec = np.zeros(ECIF_DIM, dtype=np.float32)
            ok = False
            error = None
            ruta = ruta_archivo_poses(r)
            try:
                if ruta is not None and ruta.exists():
                    if str(ruta) not in texto_cache:
                        texto_cache[str(ruta)] = modelos_de_archivo(
                            ruta.read_text(encoding="utf-8"))
                    bloques = texto_cache[str(ruta)]
                    if r["model_idx"] < len(bloques):
                        feats = ext.extract_from_pose(
                            "\n".join(bloques[r["model_idx"]]),
                            str(prot_de(r["pid"])), skip_prolif=True)
                        for j, k in enumerate(claves):
                            try:
                                vec[j] = float(feats.get(k, 0.0))
                            except (TypeError, ValueError):
                                pass
                        ok = bool((vec != 0).any())
                    else:
                        error = "model_idx fuera de rango"
                else:
                    error = "archivo de poses faltante"
            except Exception as e:
                error = f"{type(e).__name__}: {str(e)[:60]}"
            if ok:
                n_nuevos_ok += 1
            else:
                n_nuevos_fallo += 1
            fh.write(json.dumps({"key": clave, "pid": r["pid"],
                                 "source": r["source"],
                                 "file_stem": r["file_stem"],
                                 "model_idx": r["model_idx"],
                                 "ecif": [float(x) for x in vec],
                                 "ok": ok, "error": error}) + "\n")
            if (i + 1) % 50 == 0:
                fh.flush()
                pr(f"  ECIF [{i + 1}/{len(pendientes)}] "
                   f"ok={n_nuevos_ok} fallo={n_nuevos_fallo} "
                   f"({time.monotonic() - t0:.0f}s)")
    resumen["n_reutilizado"] = len(cache)
    resumen["n_ok"] = len(cache) + n_nuevos_ok
    resumen["n_fallo"] = n_nuevos_fallo
    resumen["t_s"] = round(time.monotonic() - t0, 1)
    pr(f"  ECIF completo: ok={resumen['n_ok']} fallo={resumen['n_fallo']} "
       f"reutilizado={resumen['n_reutilizado']} "
       f"({resumen['t_s']}s)")
    return resumen


# ───────────────────────── contexto intra-complejo ──────────────────────────

def z_por_pid(X: np.ndarray, grupos: list[int]) -> np.ndarray:
    """Z-score por columna DENTRO de cada complejo (filas contiguas).
    std_pid == 0 -> z = 0 (convencion v0.6)."""
    Z = np.zeros_like(X, dtype=np.float64)
    ini = 0
    for g in grupos:
        cols = X[ini:ini + g]
        m = cols.mean(axis=0)
        s = cols.std(axis=0)
        z = np.zeros_like(cols)
        ok = s > 0
        z[:, ok] = (cols[:, ok] - m[ok]) / s[ok]
        Z[ini:ini + g] = z
        ini += g
    return Z


def pct_por_pid(X: np.ndarray, grupos: list[int]) -> np.ndarray:
    """Rango percentil 0-100 por complejo (empates -> rango promedio).
    Complejo de 1 pose -> 50.0 (convencion v0.6)."""
    from scipy.stats import rankdata
    P = np.zeros_like(X, dtype=np.float64)
    ini = 0
    for g in grupos:
        if g == 1:
            P[ini:ini + g] = 50.0
            ini += g
            continue
        for j in range(X.shape[1]):
            x = X[ini:ini + g, j]
            r = rankdata(x)
            P[ini:ini + g, j] = 100.0 * (r - 1.0) / (g - 1.0)
        ini += g
    return P


def construir_ctx() -> tuple[dict, dict]:
    """{key: {"vina": [5], "novina": [3]}} para todos los splits. Cada split
    se normaliza de forma independiente (convencion v0.6)."""
    ctx: dict = {}
    resumen: dict = {}
    for nombre in ("train", "val", "test"):
        regs = cargar_registros(nombre)
        grupos, _ = grupos_por_pid(regs)
        X = np.array([[float(r["vina_score"]), float(r["cluster_density"])]
                      for r in regs], dtype=np.float64)
        Z = z_por_pid(X, grupos)
        P = pct_por_pid(X, grupos)
        for i, r in enumerate(regs):
            ctx[clave_de(r)] = {
                "vina": [X[i, 0], Z[i, 0], P[i, 0], Z[i, 1], P[i, 1]],
                "novina": [X[i, 1], Z[i, 1], P[i, 1]],
            }
        resumen[nombre] = {"registros": len(regs)}
    return ctx, resumen


# ───────────────────────── modelo ───────────────────────────────────────────

class PoseSelectorV2(nn.Module):
    """GNN v2 PoseSelector: backbone CL (hidden 128) + rama ECIF (152->64)
    + contexto intra-complejo + fusion MLP(128) + cabezas score/rmsd."""

    def __init__(self, prot_in: int = 24, lig_in: int = 38,
                 hidden_dim: int = HIDDEN, dropout: float = DROPOUT,
                 set2set_steps: int = SET2SET_STEPS, ecif_dim: int = ECIF_DIM,
                 ecif_emb_dim: int = ECIF_EMB, ctx_dim: int = CTX_DIM,
                 fusion_hidden: int = FUSION_HIDDEN):
        super().__init__()
        self.hidden_dim = hidden_dim
        self.ctx_dim = ctx_dim
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
        self.ecif_encoder = nn.Sequential(
            nn.Linear(ecif_dim, ecif_emb_dim), nn.ReLU())
        self.fusion_in = hidden_dim * 4 + ecif_emb_dim + ctx_dim
        self.fusion = nn.Sequential(
            nn.Linear(self.fusion_in, fusion_hidden), nn.ReLU(),
            nn.Dropout(dropout))
        self.score_head = nn.Linear(fusion_hidden, 1)
        self.rmsd_head = nn.Linear(fusion_hidden, 1)

    def forward(self, prot_x, prot_edge_index, lig_x, lig_edge_index,
                cross_edge_index, lig_pos, prot_pos, lig_batch, prot_batch,
                ecif=None, ctx=None):
        h_prot = self.prot_encoder(prot_x, prot_edge_index)
        h_lig = self.lig_encoder(lig_x, lig_edge_index)
        h_lig = self.cross_attn(h_lig, h_prot, cross_edge_index, lig_pos,
                                prot_pos, prot_x)
        lig_global = self.lig_pool(h_lig, lig_batch)
        prot_global = self.prot_pool(h_prot, prot_batch)
        graph_emb = torch.cat([lig_global, prot_global], dim=-1)
        if ecif is None:
            ecif = torch.zeros(graph_emb.size(0), ECIF_DIM,
                               device=graph_emb.device)
        if ctx is None:
            ctx = torch.zeros(graph_emb.size(0), self.ctx_dim,
                              device=graph_emb.device)
        ecif_emb = self.ecif_encoder(ecif)
        fusionado = self.fusion(torch.cat([graph_emb, ecif_emb, ctx], dim=-1))
        score = self.score_head(fusionado).squeeze(-1)
        rmsd_pred = self.rmsd_head(fusionado).squeeze(-1)
        return score, rmsd_pred


def contar_params(modelo: nn.Module) -> int:
    return sum(p.numel() for p in modelo.parameters() if p.requires_grad)


def cargar_warm_start(modelo: PoseSelectorV2) -> dict:
    """Carga el estado del backbone desde contrastive_v31_pretrained.pt por
    coincidencia de nombre+forma. Reporta claves coincidentes, ignoradas
    (projection) y nuevas (inicializacion aleatoria)."""
    ck = torch.load(PRETRAINED, map_location="cpu", weights_only=False)
    sd = ck["model_state_dict"]
    propio = modelo.state_dict()
    coinciden: list[str] = []
    nuevas: list[str] = []
    for k, v in propio.items():
        if k in sd and sd[k].shape == v.shape:
            propio[k] = sd[k]
            coinciden.append(k)
        else:
            nuevas.append(k)
    ignoradas = [k for k in sd if k not in propio]
    modelo.load_state_dict(propio)
    return {
        "fuente": str(PRETRAINED.relative_to(PROJECT_ROOT)),
        "epoch_pretrain": int(ck.get("epoch", -1)),
        "loss_pretrain": float(ck.get("loss", float("nan"))),
        "config_pretrain": dict(ck.get("config", {})),
        "total_claves_pretrain": len(sd),
        "coincidentes": len(coinciden),
        "ignoradas_projection": ignoradas,
        "nuevas_aleatorias": nuevas,
        "mapeo": ("coincidencia exacta por nombre de submodulo: "
                  "prot_encoder.*, lig_encoder.*, cross_attn.*, "
                  "lig_pool.*, prot_pool.* (backbone reconstruido con "
                  "hidden_dim=128, el del checkpoint CL); projection.* "
                  "descartadas"),
        "coincidentes_lista": coinciden,
    }


# ───────────────────────── datos ────────────────────────────────────────────

def cargar_dataset(ctx_por_clave: dict, modo_ctx: str) -> dict:
    """Carga gnn_{split}.pt y adjunta tensores ecif/ctx (no reconstruye
    grafos). Registros sin ECIF: 0.0 + d.ecif_ok=False."""
    cabecera, cache = cargar_cache_ecif()
    out = {}
    total = {"ok": 0, "fallo": 0, "sin_ctx": 0, "sin_ecif": 0}
    for s in ("train", "val", "test"):
        datos = torch.load(DATASET_DIR / f"gnn_{s}.pt", weights_only=False)
        datos.sort(key=lambda d: (d.pid, d.key))
        for d in datos:
            vec, ok = cache.get(d.key, (None, False))
            if vec is None:
                d.ecif = torch.zeros(ECIF_DIM, dtype=torch.float32)
                d.ecif_ok = False
                total["sin_ecif"] += 1
            else:
                d.ecif = torch.tensor(vec, dtype=torch.float32)
                d.ecif_ok = bool(ok)
            if ok:
                total["ok"] += 1
            else:
                total["fallo"] += 1
            c = ctx_por_clave.get(d.key)
            if c is None:
                d.ctx = torch.zeros(CTX_DIM if modo_ctx == "vina"
                                    else CTX_DIM_NOVINA, dtype=torch.float32)
                total["sin_ctx"] += 1
            else:
                d.ctx = torch.tensor(c[modo_ctx], dtype=torch.float32)
        out[s] = datos
    return out, total


def colacionar(data_list: list, modo_ctx: str) -> dict:
    """Bachea un lote de Data en dictos (edge_index cruzados reindexados a
    mano) incluyendo ecif y ctx."""
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
    ecif = torch.stack([d.ecif for d in data_list])
    ctx = torch.stack([d.ctx for d in data_list])
    return {"prot_x": prot_batch.x, "prot_edge_index": prot_batch.edge_index,
            "prot_pos": prot_batch.pos, "prot_batch": prot_batch.batch,
            "lig_x": lig_batch.x, "lig_edge_index": lig_batch.edge_index,
            "lig_pos": lig_batch.pos, "lig_batch": lig_batch.batch,
            "cross_edge_index": cross, "ecif": ecif, "ctx": ctx}


def a_dispositivo(b: dict, device) -> dict:
    return {k: v.to(device) if torch.is_tensor(v) else v for k, v in b.items()}


def grupos_de(datos: list) -> tuple[list, list]:
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
    """Todos los pares (i, j), i != j, con rmsd_i <= rmsd_j (empates
    incluidos) + margenes clip(0.3 + 0.5*(rmsd_j - rmsd_i), 0.3, 2.0)."""
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


def forward_todo(modelo, datos, device, modo_ctx, modo_entreno: bool):
    """Forward de todas las poses en lotes. En modo entrenamiento devuelve
    tensores con grafo de autograd retenido; en evaluacion, numpy."""
    scores, rpreds = [], []
    if modo_entreno:
        modelo.train()
        for ch in chunks(datos, BATCH_POSES):
            b = a_dispositivo(colacionar(ch, modo_ctx), device)
            s, r = modelo(b["prot_x"], b["prot_edge_index"], b["lig_x"],
                          b["lig_edge_index"], b["cross_edge_index"],
                          b["lig_pos"], b["prot_pos"], b["lig_batch"],
                          b["prot_batch"], b["ecif"], b["ctx"])
            scores.append(s)
            rpreds.append(r)
        return torch.cat(scores), torch.cat(rpreds)
    modelo.eval()
    with torch.no_grad():
        for ch in chunks(datos, BATCH_POSES):
            b = a_dispositivo(colacionar(ch, modo_ctx), device)
            s, r = modelo(b["prot_x"], b["prot_edge_index"], b["lig_x"],
                          b["lig_edge_index"], b["cross_edge_index"],
                          b["lig_pos"], b["prot_pos"], b["lig_batch"],
                          b["prot_batch"], b["ecif"], b["ctx"])
            scores.append(s.cpu())
            rpreds.append(r.cpu())
    return (torch.cat(scores).numpy(), torch.cat(rpreds).numpy())


# ───────────────────────── evaluacion ───────────────────────────────────────

def metricas_por_pid(scores: np.ndarray, datos: list, pids: list) -> dict:
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


def evaluar(modelo, datos, pids, device, modo_ctx) -> dict:
    scores, _ = forward_todo(modelo, datos, device, modo_ctx, False)
    return metricas_por_pid(scores, datos, pids)


def evaluar_mc(modelo, datos, pids, device, modo_ctx,
               mc_samples: int = MC_SAMPLES) -> dict:
    """MC-dropout: matriz (N, mc) de scores; por complejo se elige por la
    media y se reporta la varianza del score de la pose seleccionada."""
    modelo.train()
    cols = []
    with torch.no_grad():
        for _ in range(mc_samples):
            col = []
            for ch in chunks(datos, BATCH_POSES):
                b = a_dispositivo(colacionar(ch, modo_ctx), device)
                s, _ = modelo(b["prot_x"], b["prot_edge_index"], b["lig_x"],
                              b["lig_edge_index"], b["cross_edge_index"],
                              b["lig_pos"], b["prot_pos"], b["lig_batch"],
                              b["prot_batch"], b["ecif"], b["ctx"])
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


def smoke_cpu(ctx_dim: int, ckpt_path: Path, datos: list, modo_ctx) -> dict:
    """Inferencia CPU (requisito de produccion): ms por pose sobre val."""
    modelo = PoseSelectorV2(ctx_dim=ctx_dim)
    ck = torch.load(ckpt_path, weights_only=False, map_location="cpu")
    modelo.load_state_dict(ck["modelo"])
    modelo.eval()
    t0 = time.monotonic()
    with torch.no_grad():
        for ch in chunks(datos, 32):
            b = colacionar(ch, modo_ctx)
            modelo(b["prot_x"], b["prot_edge_index"], b["lig_x"],
                   b["lig_edge_index"], b["cross_edge_index"], b["lig_pos"],
                   b["prot_pos"], b["lig_batch"], b["prot_batch"],
                   b["ecif"], b["ctx"])
    t = time.monotonic() - t0
    return {"n_poses": len(datos),
            "duracion_s": round(t, 2),
            "ms_por_pose": round(1000.0 * t / max(len(datos), 1), 2)}


# ───────────────────────── entrenamiento ────────────────────────────────────

def entrenar(etapa: dict, train, val, pids_val, device,
             i_idx, j_idx, marg_dev, y_centr_dev, prog: dict,
             reporte_warm: dict) -> dict:
    """Entrena una etapa con reanudacion. Devuelve el historial."""
    nombre = etapa["nombre"]
    ctx_dim = etapa["ctx_dim"]
    modo_ctx = etapa["ctx"]
    ckpt_path = CKPTS[nombre]
    st = prog.setdefault(nombre, {"status": "pendiente", "epoch": -1,
                                  "mejor_val_top1": -1.0, "paciencia": 0,
                                  "historial": [], "duracion_s": 0.0,
                                  "reanudado": False})
    if st.get("status") == "completo" and ckpt_path.exists():
        pr(f"  [{nombre}] entrenamiento ya completo "
           f"(mejor val top1 = {st['mejor_val_top1']}).")
        return st["historial"]

    modelo = PoseSelectorV2(ctx_dim=ctx_dim)
    n_params = contar_params(modelo)
    grupos_opt = [
        {"params": (list(modelo.prot_encoder.parameters())
                    + list(modelo.lig_encoder.parameters())
                    + list(modelo.cross_attn.parameters())
                    + list(modelo.lig_pool.parameters())
                    + list(modelo.prot_pool.parameters())
                    + list(modelo.ecif_encoder.parameters())),
         "lr": LR_ENC},
        {"params": (list(modelo.fusion.parameters())
                    + list(modelo.score_head.parameters())
                    + list(modelo.rmsd_head.parameters())),
         "lr": LR_HEAD},
    ]
    optim = torch.optim.Adam(grupos_opt, lr=LR_ENC,
                             weight_decay=WEIGHT_DECAY)
    ep_inicio = 0
    if ckpt_path.exists() and st.get("status") == "en_progreso":
        ck = torch.load(ckpt_path, weights_only=False, map_location=device)
        modelo.load_state_dict(ck["modelo"])
        optim.load_state_dict(ck["optimizador"])
        ep_inicio = ck["epoch"] + 1
        st["reanudado"] = True
        pr(f"  [{nombre}] reanudando desde epoca {ep_inicio} "
           f"(mejor val top1 = {st['mejor_val_top1']}).")
    modelo = modelo.to(device)
    st["status"] = "en_progreso"
    st["n_params"] = n_params
    st["warm_start"] = reporte_warm
    guardar_progreso_entreno(prog)
    pr(f"  [{nombre}] {etapa['desc']} | params: {n_params:,} | "
       f"pares train: {len(i_idx):,}")

    t0 = time.monotonic()
    for ep in range(ep_inicio, MAX_EPOCHS):
        t_ep = time.monotonic()
        modelo.train()
        optim.zero_grad()
        s, r = forward_todo(modelo, train, device, modo_ctx, True)
        perdida_par = F.relu(marg_dev - (s[i_idx] - s[j_idx])).mean()
        perdida_aux = F.mse_loss(r, y_centr_dev)
        perdida = perdida_par + LAMBDA_AUX * perdida_aux
        perdida.backward()
        torch.nn.utils.clip_grad_norm_(modelo.parameters(), 1.0)
        optim.step()
        met_val = evaluar(modelo, val, pids_val, device, modo_ctx)
        if met_val["top1_rate"] > st["mejor_val_top1"]:
            st["mejor_val_top1"] = met_val["top1_rate"]
            st["paciencia"] = 0
            torch.save({"modelo": modelo.state_dict(),
                        "optimizador": optim.state_dict(),
                        "epoch": ep, "config": {
                            "hidden": HIDDEN, "dropout": DROPOUT,
                            "set2set_steps": SET2SET_STEPS,
                            "ecif_dim": ECIF_DIM, "ecif_emb": ECIF_EMB,
                            "fusion_hidden": FUSION_HIDDEN,
                            "ctx_dim": ctx_dim, "ctx": modo_ctx,
                            "lr_enc": LR_ENC, "lr_head": LR_HEAD,
                            "weight_decay": WEIGHT_DECAY,
                            "lambda_aux": LAMBDA_AUX, "semilla": SEMILLA},
                        "n_params": n_params, "val": met_val,
                        "warm_start": reporte_warm}, ckpt_path)
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
        pr(f"  [{nombre}] ep {ep}: pair {float(perdida_par.item()):.4f} "
           f"aux {float(perdida_aux.item()):.4f} | val top1 "
           f"{met_val['top1_rate']} mediana {met_val['mediana_rmsd']} "
           f"| paciencia {st['paciencia']}/{PACENCIA} "
           f"({time.monotonic() - t_ep:.0f}s)")
        if st["paciencia"] >= PACENCIA:
            pr(f"  [{nombre}] early stop en epoca {ep} "
               f"(paciencia {PACENCIA} agotada).")
            break
    st["status"] = "completo"
    st["duracion_s"] = round(time.monotonic() - t0, 1)
    guardar_progreso_entreno(prog)
    return st["historial"]


# ───────────────────────── flujo principal ──────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--solo-ecif", action="store_true",
                        help="solo construye el cache ECIF y termina")
    args = parser.parse_args()

    configurar_salida()
    t0 = time.monotonic()
    pr("== Ruta C Fase 2.1: GNN v2 PoseSelector (docs/42) ==")

    if args.solo_ecif:
        registros = cargar_todos_los_registros()
        resumen = construir_cache_ecif(registros)
        pr(json.dumps(resumen, ensure_ascii=False, indent=2))
        return

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    pr(f"  dispositivo: {device} "
       f"({torch.cuda.get_device_name(0) if device.type == 'cuda' else 'CPU'})")
    torch.manual_seed(SEMILLA)
    if device.type == "cuda":
        torch.cuda.manual_seed(SEMILLA)

    # ── ECIF + contexto ──
    registros = cargar_todos_los_registros()
    resumen_ecif = construir_cache_ecif(registros)
    ctx_por_clave, resumen_ctx = construir_ctx()

    prog = cargar_progreso_entreno()
    art: dict = {
        "generated_at": ahora_iso(),
        "protocolo": "docs/42_RUTA_C_PROTOCOLO.md",
        "fase": "2.1 (GNN v2 PoseSelector, warm-start CL + ECIF + contexto)",
        "hipotesis": ("un score de native-likeness aprendido con perdida de "
                      "ranking pairwise intra-complejo (dominante), warm-start "
                      "contrastivo, rama ECIF 152 y contexto relativizado "
                      "intra-complejo supera al campeon v0.6 (0.6596) en el "
                      "holdout congelado"),
        "gate_criterio": f"pose_selector_v2_test_top1 > {TOP1_V06_TEST} "
                         f"(top-1 v0.6)",
        "config": {
            "arquitectura": {
                "backbone": ("ProteinEncoder GAT-Ca 24->128 (4 cabezas, 2 "
                             "capas) + LigandEncoder GIN 38->128 (3 capas) + "
                             "CrossAttention (bias distancia 3.5 A + tipo "
                             "residuo) + Set2Set x2 (4 pasos), clases de "
                             "rescoring/gnn_v2/models.py"),
                "hidden_dim": HIDDEN,
                "nota_hidden_128": ("v1 uso 64; v2 usa 128 porque el "
                                    "checkpoint CL (contrastive_v31_"
                                    "pretrained.pt) se entreno con hidden=128 "
                                    "y el warm-start exige coincidencia "
                                    "exacta de formas"),
                "ecif_rama": f"MLP {ECIF_DIM}->{ECIF_EMB}, ReLU",
                "ctx_rama": ("por complejo dentro de cada split (v0.6): "
                             "z-score (std=0 -> 0) y percentil (empates -> "
                             "rango promedio; complejo de 1 pose -> 50) de "
                             "vina_score y cluster_density"),
                "ctx_principal": ("[vina_raw, z_vina, pct_vina, z_cluster, "
                                  "pct_cluster] (5)"),
                "ctx_novina": "[cluster_raw, z_cluster, pct_cluster] (3)",
                "fusion": (f"concat(graph_emb {4 * HIDDEN}, ecif_emb "
                           f"{ECIF_EMB}, ctx) -> MLP({FUSION_HIDDEN}, ReLU, "
                           f"dropout {DROPOUT})"),
                "cabezas": "score (Linear 128->1) + rmsd (Linear 128->1)",
                "dropout": DROPOUT,
            },
            "perdida": {
                "pairwise": ("por complejo, todos los pares (i,j) con "
                             "rmsd_i <= rmsd_j (empates incluidos, ambas "
                             "direcciones), i != j; normalizada por total "
                             "de pares"),
                "margen": "clip(0.3 + 0.5*(rmsd_j - rmsd_i), 0.3, 2.0)",
                "auxiliar": ("MSE(rmsd_head, rmsd - mediana_del_complejo) "
                             "sobre poses con rmsd valido"),
                "lambda_aux": LAMBDA_AUX,
                "nota_aux": ("en v1 lambda=0.5 sobre rmsd crudo y la aux "
                             "domino (pair quedo plana en ~1.23); v2 centra "
                             "por complejo y baja lambda a 0.1"),
                "grupos_1_pose": "solo auxiliar",
            },
            "optimizacion": {
                "opt": "Adam", "lr_enc": LR_ENC, "lr_head": LR_HEAD,
                "weight_decay": WEIGHT_DECAY, "max_epochs": MAX_EPOCHS,
                "paciencia_val_top1": PACENCIA,
                "batch_poses": BATCH_POSES, "semilla": SEMILLA,
                "dispositivo": str(device),
                "grupos_parametros": ("backbone+ecif_encoder lr 1e-3; "
                                      "fusion+score_head+rmsd_head lr 3e-3"),
                "esquema_computo": ("1 forward por pose por epoca (lote 64, "
                                    "grafo retenido) + perdida pairwise "
                                    "vectorizada sobre TODOS los pares en un "
                                    "solo backward (mismo esquema v1)"),
                "n_pares_train": None,
            },
            "mc_dropout": {"mc_samples": MC_SAMPLES,
                           "dropout_activo_en_inferencia": True},
            "umbral_pose_positiva_angstrom": UMBRAL_POSITIVA,
            "split": "holdout congelado Fase 0 (scaffold-disjoint, seed 42)",
            "ecif": resumen_ecif,
            "contexto": resumen_ctx,
        },
    }
    guardar_artefacto(art, "config")
    pr("  ECIF: " + json.dumps(
        {k: resumen_ecif[k] for k in
         ("n_total", "n_ok", "n_fallo", "n_reutilizado")},
        ensure_ascii=False))

    # ── Warm start (una sola vez; vale para ambas etapas) ──
    modelo_sonda = PoseSelectorV2(ctx_dim=CTX_DIM)
    reporte_warm = cargar_warm_start(modelo_sonda)
    del modelo_sonda
    pr(f"  warm-start CL: {reporte_warm['coincidentes']}/"
       f"{reporte_warm['total_claves_pretrain']} claves coinciden; "
       f"ignoradas (projection): {len(reporte_warm['ignoradas_projection'])}; "
       f"nuevas aleatorias: {len(reporte_warm['nuevas_aleatorias'])}")
    art["warm_start"] = reporte_warm
    guardar_artefacto(art, "warm_start")

    # ── Datos por etapa ──
    datos_etapas = {}
    conteos_adjuntos = {}
    for etapa in ETAPAS:
        datos_etapas[etapa["nombre"]], conteos_adjuntos[etapa["nombre"]] = \
            cargar_dataset(ctx_por_clave, etapa["ctx"])
        for s in ("train", "val", "test"):
            n = len({d.pid for d in datos_etapas[etapa["nombre"]][s]})
            pr(f"  [{etapa['nombre']}] {s}: "
               f"{len(datos_etapas[etapa['nombre']][s])} grafos, {n} complejos")
    art["adjuntos_ecif_ctx"] = {
        etapa["nombre"]: conteos_adjuntos[etapa["nombre"]]
        for etapa in ETAPAS}
    guardar_artefacto(art, "datos_cargados")

    # ── Pares (mismos para ambas etapas) ──
    train_ref = datos_etapas["v2"]["train"]
    grupos_train, pids_train = grupos_de(train_ref)
    _gv, pids_val = grupos_de(datos_etapas["v2"]["val"])
    _gt, pids_test = grupos_de(datos_etapas["v2"]["test"])
    y_train = np.array([d.y_rmsd for d in train_ref], dtype=np.float64)
    i_arr, j_arr, marg = construir_pares(y_train, grupos_train)
    i_idx = torch.tensor(i_arr, dtype=torch.long, device=device)
    j_idx = torch.tensor(j_arr, dtype=torch.long, device=device)
    marg_dev = torch.tensor(marg, dtype=torch.float32, device=device)
    # rmsd centrado por complejo (mediana del complejo en train)
    y_centr = np.empty_like(y_train)
    ini = 0
    for g in grupos_train:
        seg = y_train[ini:ini + g]
        y_centr[ini:ini + g] = seg - np.median(seg)
        ini += g
    y_centr_dev = torch.tensor(y_centr, dtype=torch.float32, device=device)
    art["config"]["optimizacion"]["n_pares_train"] = int(len(i_arr))
    pr(f"  pares de entrenamiento (i<=j, empates incluidos): {len(i_arr):,}")

    art["vina_baseline_recomputado"] = {
        s: baseline_vina(datos_etapas["v2"][s],
                         {"train": pids_train, "val": pids_val,
                          "test": pids_test}[s])
        for s in ("train", "val", "test")}
    pr("  vina recomputado: " + json.dumps(
        {s: art["vina_baseline_recomputado"][s]["top1_rate"]
         for s in ("train", "val", "test")}, ensure_ascii=False))
    guardar_artefacto(art, "vina_recomputado")

    # ── Entrenamiento ──
    historiales = {}
    for etapa in ETAPAS:
        hist = entrenar(etapa, datos_etapas[etapa["nombre"]]["train"],
                        datos_etapas[etapa["nombre"]]["val"], pids_val,
                        device, i_idx, j_idx, marg_dev, y_centr_dev, prog,
                        reporte_warm)
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

    # ── Evaluacion final (val + test + MC test + smoke CPU) ──
    metricas = {}
    for etapa in ETAPAS:
        nombre = etapa["nombre"]
        modelo = PoseSelectorV2(ctx_dim=etapa["ctx_dim"])
        ck = torch.load(CKPTS[nombre], weights_only=False,
                        map_location=device)
        modelo.load_state_dict(ck["modelo"])
        modelo = modelo.to(device)
        met = {}
        for s, pids in (("val", pids_val), ("test", pids_test)):
            met[s] = evaluar(modelo, datos_etapas[nombre][s], pids, device,
                             etapa["ctx"])
        met["mc_test"] = evaluar_mc(modelo, datos_etapas[nombre]["test"],
                                    pids_test, device, etapa["ctx"])
        met["smoke_cpu"] = smoke_cpu(etapa["ctx_dim"], CKPTS[nombre],
                                     datos_etapas[nombre]["val"],
                                     etapa["ctx"])
        metricas[nombre] = met
        art[f"evaluacion_{nombre}"] = met
        guardar_artefacto(art, f"evaluado_{nombre}")
        pr(f"  [{nombre}] val top1 {met['val']['top1_rate']} | "
           f"test top1 {met['test']['top1_rate']} | "
           f"test mediana {met['test']['mediana_rmsd']} | "
           f"MC var media {met['mc_test']['varianza_media_pose_seleccionada']}")

    # ── Tabla comparativa con fases previas ──
    previos = {}
    for nombre_archivo in ("artifacts_ruta_c_fase1.json",
                           "artifacts_ruta_c_fase1_5.json",
                           "artifacts_ruta_c_fase1_6.json",
                           "artifacts_ruta_c_fase2.json"):
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
    a2 = previos.get("artifacts_ruta_c_fase2.json", {})
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
            "gnn_v1_top1": a2.get("evaluacion_v1", {}).get(split, {}).get(
                "top1_rate"),
            "gnn_v1_mediana": a2.get("evaluacion_v1", {}).get(split, {}).get(
                "mediana_rmsd"),
            "gnn_v2_top1": metricas["v2"][split]["top1_rate"],
            "gnn_v2_mediana": metricas["v2"][split]["mediana_rmsd"],
            "gnn_v2_spearman": metricas["v2"][split][
                "spearman_pred_vs_rmsd_media"],
            "gnn_v2_novina_top1": metricas["novina"][split]["top1_rate"],
            "gnn_v2_novina_mediana": metricas["novina"][split]["mediana_rmsd"],
            "gnn_v2_novina_spearman": metricas["novina"][split][
                "spearman_pred_vs_rmsd_media"],
        }
    art["comparacion"] = tabla

    # ── Gate ──
    gnn_test = metricas["v2"]["test"]["top1_rate"]
    art["gate"] = {
        "criterio": f"pose_selector_v2_test_top1 > {TOP1_V06_TEST} "
                    f"(campeon v0.6)",
        "v2_top1_test": gnn_test,
        "v06B_top1_test": TOP1_V06_TEST,
        "vina_top1_test": TOP1_VINA_TEST,
        "delta_vs_v06B": round(gnn_test - TOP1_V06_TEST, 4),
        "resultado": "PASS" if gnn_test > TOP1_V06_TEST else "FAIL",
    }
    pr(f"  Gate: {art['gate']['resultado']} "
       f"(GNN v2 {gnn_test} vs v0.6 {TOP1_V06_TEST})")

    # ── Refutacion R-RC1 ──
    novina_test = metricas["novina"]["test"]["top1_rate"]
    delta_rc1 = round(gnn_test - novina_test, 4)
    if abs(delta_rc1) <= 0.02:
        lectura = ("sin cambio material: el score aprendido NO depende del "
                   "contexto Vina — la senal grafo+ECIF+cluster es "
                   "autosuficiente para la seleccion (C1 se sostiene)")
    else:
        lectura = ("cambio material: el contexto Vina aporta informacion a "
                   "la seleccion; la senal aprendida es parcialmente "
                   "complementaria al score de energia")
    art["refutacion_R_RC1"] = {
        "pregunta": "cambia el top-1 test al quitar el contexto vina?",
        "gnn_v2_top1_test": gnn_test,
        "gnn_v2_novina_top1_test": novina_test,
        "delta": delta_rc1,
        "lectura": lectura,
    }
    pr(f"  R-RC1: delta {delta_rc1} ({lectura[:60]}...)")

    # ── Curvas de perdida resumidas ──
    art["curvas_perdida"] = {
        nombre: {
            "epochs": [h["epoch"] for h in historiales[nombre]],
            "loss_pair": [h["loss_pair"] for h in historiales[nombre]],
            "loss_aux": [h["loss_aux"] for h in historiales[nombre]],
            "loss_total": [h["loss_total"] for h in historiales[nombre]],
            "val_top1": [h["val_top1"] for h in historiales[nombre]],
        } for nombre in ("v2", "novina")}

    art["caveats_honestos"] = [
        ("Backbone con hidden=128 (v1 uso 64) para coincidir con el "
         "checkpoint CL; el limite de parametros (<= 1.5 M) se cumple igual."),
        ("La rama ECIF usa extract_from_pose con skip_prolif=True: las "
         "interacciones ProLIF NO forman parte de los 152 dims (estan "
         "excluidas de ALL_3D_FEATURES por el fix #3 Spearman), asi que la "
         "definicion 152 es identica a la del productor del npz docked."),
        ("El ligando de cada pose se parsea con el parser AD4 del extractor "
         "(tipos de ligando por elemento, sin aromaticidad — el ECIF de "
         "ligando es por diseno solo de elemento)."),
        ("Registros sin ECIF computable se rellenan con 0.0 + bandera "
         "ecif_ok=False; la fusion NO consume la bandera (solo se reporta)."),
        ("Val tiene solo 40 complejos: el early stop es ruidoso; la "
         "comparacion del gate es sobre el test congelado (47 complejos)."),
        ("MC-dropout usa dropout 0.3 activo en inferencia (modelo en modo "
         "train), precedente predict_proba de GNNv2Classifier; las "
         "varianzas son un proxy de incertidumbre, no calibradas."),
        ("Si el entrenamiento se reanudo tras un crash, la secuencia RNG "
         "difiere de una corrida ininterrumpida (se registra la bandera "
         "'reanudado' por etapa)."),
        ("El warm-start inicializa el backbone con pesos CL entrenados sobre "
         "el dataset PDBbind docked del proyecto (708 complejos), NO sobre "
         "las poses de Ruta C."),
    ]
    art["duracion_total_s"] = round(time.monotonic() - t0, 1)
    guardar_artefacto(art, "completo")
    pr(f"  artefacto: {ARTIFACTOS} ({art['duracion_total_s']}s)")


if __name__ == "__main__":
    main()
