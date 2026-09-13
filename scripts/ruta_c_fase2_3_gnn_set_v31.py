# -*- coding: utf-8 -*-
"""
ruta_c_fase2_3_gnn_set_v31.py — Ruta C, Fase 2.3 (variante estricta):
GNN set-level (B) con warm-start desde gnn_v31_best.pt.

Antes de cerrar la linea GNN de Ruta C (B dio 0.5106 test en Fase 2.2),
se re-entrena la MISMA arquitectura set-level (PoseSelectorSet) cambiando
UNICAMENTE la fuente de inicializacion de los componentes per-pose:
del pose_selector_v2_best.pt (0.5106 test) al MEJOR activo GNN del
proyecto: rescoring/artifacts/gnn_v31_best.pt (GNNv31Classifier,
hidden 128, test ROC-AUC 0.877 sobre PDBbind). Es la variante estricta:
misma arquitectura, mismos datos, misma perdida, mismo protocolo — solo
cambia la fuente de inicializacion.

Mapeo de inicializacion (variante estricta):

  Se cargan desde gnn_v31_best.pt (state_dict bruto, 82 claves) por
  coincidencia de nombre+forma: prot_encoder.* (14), lig_encoder.* (32),
  cross_attn.* (11), lig_pool.* (4), prot_pool.* (4) y ecif_encoder.* (4
  tras la adaptacion) = 69 claves. Se OMITEN por diseno las cabezas del
  clasificador v31: fusion.* (4), classification_head.* (4), delta_head.*
  (4) y el parametro ecif_missing_flag (1, sin contraparte en B) = 13.
  El hidden dim del checkpoint (128) coincide con el de B: no se ajusta.

  ADAPTACION (unica diferencia de arquitectura respecto de B, exigida por
  el checkpoint): la rama ECIF de B era MLP de una capa
  Linear(152->64)+ReLU; el checkpoint v31 la define como
  Linear(152->128) + ELU + Dropout(0.2) + Linear(128->64) + ELU +
  Dropout(0.2) (claves ecif_encoder.0.* y ecif_encoder.3.*). Se adopta la
  definicion del checkpoint para poder cargar sus pesos; la salida sigue
  siendo 64-dim, por lo que h_proj (581->256) no cambia.

  Aleatorio (seed 42): h_proj, set_encoder (atencion cross-pose),
  fusion y cabezas score/rmsd — identico a B.

Todo lo demas es IDENTICO a B (scripts/ruta_c_fase2_2_gnn_set.py):
perdida pairwise por complejo con margen clip(0.3 + 0.5*(rmsd_j - rmsd_i),
0.3, 2.0) + MSE auxiliar sobre rmsd centrado (lambda 0.1); Adam lr 1e-3
(backbone/ECIF) y 3e-3 (atencion+fusion+cabezas), weight_decay 1e-5,
seed 42, <= 60 epocas, early stop en top-1 val (paciencia 12), GPU,
MC-dropout (mc_samples=20). Checkpoint:
data/pose_selector_dataset/pose_selector_set_v31init_best.pt.

Evaluacion: por pid argmax(score) -> top-1 crystal-like (<= 2.0 A),
mediana RMSD, Spearman medio por pid en val (por epoca) y test (final).
Tabla: Vina 0.5319 / v0.6 0.6596 / GNN v1 0.4894 / GNN v2 0.5106 /
B 0.5106 / B+v31init (esta corrida).
Gate (regla preacordada): test top-1 > 0.6596 -> la linea GNN se REABRE;
si no -> la linea se cierra y v0.6 se promueve como selector.

Bonus interpretabilidad: peso medio de atencion hacia la pose seleccionada
(capa final del set-encoder, media sobre cabezas).

Artefacto: scripts/artifacts_ruta_c_fase2_3.json (escritura incremental).
Pipeline ECIF reutiliza data/pose_selector_dataset/ecif_152_progress.jsonl.
Entrenamiento reanudable:
data/pose_selector_dataset/train_gnn_set_v31init_progress.json.

Uso:
  python scripts/ruta_c_fase2_3_gnn_set_v31.py            # pipeline completo
  python scripts/ruta_c_fase2_3_gnn_set_v31.py --smoke    # chequeo rapido sin entrenar
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
CKPT_V31 = PROJECT_ROOT / "rescoring" / "artifacts" / "gnn_v31_best.pt"
CKPT_SET = DATASET_DIR / "pose_selector_set_v31init_best.pt"
ARTIFACTOS = PROJECT_ROOT / "scripts" / "artifacts_ruta_c_fase2_3.json"
ECIF_CACHE = DATASET_DIR / "ecif_152_progress.jsonl"
PROGRESO_ENTRENO = DATASET_DIR / "train_gnn_set_v31init_progress.json"
LOG_PATH = DATASET_DIR / "train_gnn_set_v31init.log"

SEMILLA = 42
HIDDEN = 128          # coincide con el hidden del checkpoint v31 (128): sin ajuste
DROPOUT = 0.3
SET2SET_STEPS = 4
ECIF_DIM = 152
ECIF_EMB = 64         # salida de la rama ECIF v31 (64) — igual que en B
ECIF_ENC_HIDDEN = 128  # capa intermedia de la rama ECIF de v31 (152->128->64)
ECIF_DROPOUT = 0.2    # dropout de la rama ECIF en v31 (config de su entrenamiento)
D_MODEL = 256         # dim del embedding per-pose h_i
NHEAD = 4
TF_LAYERS = 2
TF_DROPOUT = 0.2
FF_DIM = 128          # DESVIACION honesta: ver docstring y caveats
CTX_DIM = 5           # [vina_raw, z_vina, pct_vina, z_cluster, pct_cluster]
FUSION_HIDDEN = 128   # salida de la fusion (entrada de las cabezas)
LR_ENC = 1e-3         # backbone + ecif + proyeccion per-pose
LR_SET = 3e-3         # atencion + fusion + cabezas
WEIGHT_DECAY = 1e-5
MAX_EPOCHS = 60
PACENCIA = 12
LAMBDA_AUX = 0.1
BATCH_POSES = 64
MC_SAMPLES = 20
UMBRAL_POSITIVA = 2.0
TOP1_V06_TEST = 0.6596
TOP1_VINA_TEST = 0.5319
LIMITE_PARAMS = 1_600_000

CLAVES_OMITIR_V31 = ("fusion.", "classification_head.", "delta_head.")


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


# ───────────────────────── pipeline ECIF (reutilizado) ──────────────────────

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
    """{key: {"vina": [5]}} para todos los splits. Cada split se normaliza
    de forma independiente (convencion v0.6)."""
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
            }
        resumen[nombre] = {"registros": len(regs)}
    return ctx, resumen


# ───────────────────────── modelo ───────────────────────────────────────────

def estadisticas_por_grupo(h: torch.Tensor, grupos: list,
                           device) -> tuple[torch.Tensor, torch.Tensor]:
    """Media y maximo por complejo (grupos contiguos) expandidos a cada
    fila: devuelve (media_complejo, max_complejo), ambos (N, D)."""
    n_grupos = len(grupos)
    idx = torch.repeat_interleave(
        torch.arange(n_grupos, device=device),
        torch.tensor(grupos, dtype=torch.long, device=device))
    suma = torch.zeros(n_grupos, h.size(1), device=device, dtype=h.dtype)
    suma.index_add_(0, idx, h)
    media = suma / torch.tensor(grupos, device=device,
                                dtype=h.dtype).unsqueeze(1)
    maxima = torch.full((n_grupos, h.size(1)), float("-inf"),
                        device=device, dtype=h.dtype)
    maxima = maxima.scatter_reduce(0, idx.unsqueeze(1).expand(-1, h.size(1)),
                                   h, reduce="amax", include_self=True)
    return media[idx], maxima[idx]


def mascara_bloques(grupos: list, device) -> torch.Tensor:
    """Mascara ADITIVA (N, N) float: -inf = bloqueado, 0.0 = permitido.
    Solo el bloque diagonal de cada complejo queda libre (poses de pids
    distintos jamas se atienden; la diagonal queda libre: cada pose se
    atiende a si misma). Se pasa como src_mask (mascara aditiva)."""
    n_total = sum(grupos)
    m = torch.full((n_total, n_total), float("-inf"),
                   dtype=torch.float32, device=device)
    ini = 0
    for g in grupos:
        m[ini:ini + g, ini:ini + g] = 0.0
        ini += g
    return m


class PoseSelectorSet(nn.Module):
    """GNN set-level (opcion B): encoder per-pose (warm-start v31) +
    atencion cross-pose intra-complejo (C4) + fusion + cabezas.

    La rama ECIF usa la DEFINICION del checkpoint v31 (dos capas con ELU
    y dropout 0.2) en lugar del MLP de una capa de B — unica diferencia
    de arquitectura, exigida por el mapeo de pesos (ver docstring).

    extraer_h()  produce el embedding per-pose h_i (dim 256, dropout 0.3).
    adelante_set()  aplica el TransformerEncoder con mascara en bloques,
    la agregacion simetrica por complejo (media/max, invariante a
    permutacion) y las cabezas score/rmsd.
    """

    def __init__(self, prot_in: int = 24, lig_in: int = 38,
                 hidden_dim: int = HIDDEN, dropout: float = DROPOUT,
                 set2set_steps: int = SET2SET_STEPS, ecif_dim: int = ECIF_DIM,
                 ecif_emb_dim: int = ECIF_EMB,
                 ecif_enc_hidden: int = ECIF_ENC_HIDDEN,
                 ecif_dropout: float = ECIF_DROPOUT,
                 ctx_dim: int = CTX_DIM,
                 d_model: int = D_MODEL, nhead: int = NHEAD,
                 tf_layers: int = TF_LAYERS, tf_dropout: float = TF_DROPOUT,
                 ff_dim: int = FF_DIM, fusion_hidden: int = FUSION_HIDDEN):
        super().__init__()
        self.hidden_dim = hidden_dim
        self.ctx_dim = ctx_dim
        self.d_model = d_model
        # ── encoder per-pose (clases de v2; pesos warm-start v31) ──
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
        # rama ECIF con la DEFINICION de GNNv31Classifier (dropout 0.2)
        self.ecif_encoder = nn.Sequential(
            nn.Linear(ecif_dim, ecif_enc_hidden), nn.ELU(),
            nn.Dropout(ecif_dropout),
            nn.Linear(ecif_enc_hidden, ecif_emb_dim), nn.ELU(),
            nn.Dropout(ecif_dropout))
        # proyeccion per-pose: [graph_emb 4*hidden, ecif_emb, ctx] -> h_i
        self.h_proj = nn.Sequential(
            nn.Linear(hidden_dim * 4 + ecif_emb_dim + ctx_dim, d_model),
            nn.ReLU(), nn.Dropout(dropout))
        # ── atencion cross-pose (C4) ──
        capa = nn.TransformerEncoderLayer(
            d_model=d_model, nhead=nhead, dim_feedforward=ff_dim,
            dropout=tf_dropout, activation="relu", batch_first=True)
        self.set_encoder = nn.TransformerEncoder(
            capa, num_layers=tf_layers, enable_nested_tensor=False)
        # ── fusion + cabezas ──
        self.fusion = nn.Sequential(
            nn.Linear(d_model * 4, fusion_hidden), nn.ReLU(),
            nn.Dropout(dropout))
        self.score_head = nn.Linear(fusion_hidden, 1)
        self.rmsd_head = nn.Linear(fusion_hidden, 1)

    def extraer_h(self, prot_x, prot_edge_index, lig_x, lig_edge_index,
                  cross_edge_index, lig_pos, prot_pos, lig_batch, prot_batch,
                  ecif=None, ctx=None):
        """Embedding per-pose h_i (B, d_model) con dropout 0.3."""
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
        return self.h_proj(torch.cat([graph_emb, ecif_emb, ctx], dim=-1))

    def adelante_set(self, h: torch.Tensor,
                     mascara: torch.Tensor | None) -> tuple:
        """h: (N, d_model) TODAS las poses del lote; mascara: (N, N) float
        aditiva (-inf = bloqueado) o None para un unico complejo.
        Devuelve (score, rmsd_pred), ambos (N,)."""
        grupos = [h.size(0)]  # unico complejo: sin mascara
        hp = self.set_encoder(h, mask=mascara)
        media, maxima = estadisticas_por_grupo(hp, grupos, h.device)
        fusionado = self.fusion(
            torch.cat([hp, media, maxima, h - media], dim=-1))
        score = self.score_head(fusionado).squeeze(-1)
        rmsd_pred = self.rmsd_head(fusionado).squeeze(-1)
        return score, rmsd_pred

    def adelante_set_complejos(self, h: torch.Tensor, grupos: list,
                               device) -> tuple:
        """Variante con varios complejos contiguos en el mismo lote."""
        mascara = mascara_bloques(grupos, device)
        hp = self.set_encoder(h, mask=mascara)
        media, maxima = estadisticas_por_grupo(hp, grupos, device)
        fusionado = self.fusion(
            torch.cat([hp, media, maxima, h - media], dim=-1))
        score = self.score_head(fusionado).squeeze(-1)
        rmsd_pred = self.rmsd_head(fusionado).squeeze(-1)
        return score, rmsd_pred


def contar_params(modelo: nn.Module) -> int:
    return sum(p.numel() for p in modelo.parameters() if p.requires_grad)


def cargar_warm_start_v31(modelo: PoseSelectorSet) -> dict:
    """Inicializa los componentes per-pose desde gnn_v31_best.pt
    (GNNv31Classifier, hidden 128, test ROC-AUC 0.877) por coincidencia
    de nombre+forma. Se omiten por diseno las cabezas del clasificador
    (fusion.*, classification_head.*, delta_head.*) y el parametro
    ecif_missing_flag (sin contraparte en B). La rama ECIF de B ya fue
    adaptada a la definicion del checkpoint (ver docstring)."""
    ck = torch.load(CKPT_V31, map_location="cpu", weights_only=False)
    sd = dict(ck)  # state_dict bruto: 82 claves, sin envoltura "modelo"
    propio = modelo.state_dict()
    coinciden: list[str] = []
    nuevas: list[str] = []
    omitidas_cabezas: list[str] = []
    omitidas_flag: list[str] = []
    omitidas_forma: list[str] = []
    for k, v in propio.items():
        if (k in sd and sd[k].shape == v.shape
                and not k.startswith(CLAVES_OMITIR_V31)):
            propio[k] = sd[k]
            coinciden.append(k)
        else:
            nuevas.append(k)
    for k in sd:
        if k.startswith(CLAVES_OMITIR_V31):
            omitidas_cabezas.append(k)
        elif k not in propio:
            omitidas_flag.append(k)
        elif sd[k].shape != propio[k].shape:
            omitidas_forma.append(k)
    modelo.load_state_dict(propio)
    contexto_v31: dict = {}
    res_v31 = PROJECT_ROOT / "rescoring" / "artifacts" / "gnn_v31_results.json"
    if res_v31.exists():
        try:
            r31 = json.loads(res_v31.read_text(encoding="utf-8"))
            contexto_v31 = {
                "best_val_auc": r31.get("best_val_auc"),
                "best_epoch": r31.get("best_epoch"),
                "test_roc_auc": r31.get("test_metrics", {}).get("roc_auc"),
                "test_pr_auc": r31.get("test_metrics", {}).get("pr_auc"),
                "n_params_v31": r31.get("n_params"),
                "config_v31": r31.get("config"),
            }
        except Exception:
            contexto_v31 = {"error": "gnn_v31_results.json no legible"}
    return {
        "fuente": str(CKPT_V31.relative_to(PROJECT_ROOT)),
        "formato_checkpoint": ("state_dict bruto (OrderedDict de 82 claves, "
                               "sin envoltura 'modelo'); contexto tomado de "
                               "gnn_v31_results.json"),
        "contexto_v31": contexto_v31,
        "total_claves_v31": len(sd),
        "coincidentes": len(coinciden),
        "omitidas_cabezas_v31": omitidas_cabezas,
        "omitidas_flag_v31": omitidas_flag,
        "omitidas_forma": omitidas_forma,
        "nuevas_aleatorias": nuevas,
        "hidden_dim": ("128 en checkpoint y en B: sin ajuste de "
                       "dimensionalidad"),
        "adaptacion_ecif": ("la rama ECIF de B era Linear(152->64)+ReLU; se "
                            "adopto la definicion de GNNv31Classifier: "
                            "Linear(152->128)+ELU+Dropout(0.2)+"
                            "Linear(128->64)+ELU+Dropout(0.2) "
                            "(claves ecif_encoder.0.* y ecif_encoder.3.*, "
                            "4 pesos cargados). La salida sigue siendo 64-dim "
                            "y h_proj (581->256) no cambia."),
        "mapeo": ("coincidencia por nombre de submodulo: prot_encoder.* "
                  "(14), lig_encoder.* (32), cross_attn.* (11), lig_pool.* "
                  "(4), prot_pool.* (4), ecif_encoder.* (4, tras adaptar "
                  "la rama a la definicion v31); omitidas las cabezas del "
                  "clasificador v31 (fusion/classification_head/"
                  "delta_head) y ecif_missing_flag"),
        "coincidentes_lista": coinciden,
    }


# ───────────────────────── datos ────────────────────────────────────────────

def cargar_dataset(ctx_por_clave: dict, modo_ctx: str = "vina") -> dict:
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
                d.ctx = torch.zeros(CTX_DIM, dtype=torch.float32)
                total["sin_ctx"] += 1
            else:
                d.ctx = torch.tensor(c[modo_ctx], dtype=torch.float32)
        out[s] = datos
    return out, total


def colacionar(data_list: list, modo_ctx: str = "vina") -> dict:
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


def extraer_h_todo(modelo: PoseSelectorSet, datos: list, device,
                   modo_ctx: str) -> torch.Tensor:
    """Extrae h_i de TODAS las poses (GNN bacheada por memoria) -> (N, 256)."""
    hs = []
    for ch in chunks(datos, BATCH_POSES):
        b = a_dispositivo(colacionar(ch, modo_ctx), device)
        hs.append(modelo.extraer_h(
            b["prot_x"], b["prot_edge_index"], b["lig_x"],
            b["lig_edge_index"], b["cross_edge_index"], b["lig_pos"],
            b["prot_pos"], b["lig_batch"], b["prot_batch"],
            b["ecif"], b["ctx"]))
    return torch.cat(hs, dim=0)


def forward_todo_set(modelo: PoseSelectorSet, datos: list, device,
                     modo_ctx: str, modo_entreno: bool):
    """Forward de TODAS las poses: GNN per-pose en lotes + set-encoder con
    mascara en bloques sobre el lote completo. En entrenamiento devuelve
    tensores con autograd; en evaluacion, numpy."""
    grupos, _ = grupos_de(datos)
    mascara = mascara_bloques(grupos, device)
    if modo_entreno:
        modelo.train()
        h = extraer_h_todo(modelo, datos, device, modo_ctx)
        s, r = modelo.adelante_set_complejos(h, grupos, device)
        return s, r
    modelo.eval()
    with torch.no_grad():
        h = extraer_h_todo(modelo, datos, device, modo_ctx)
        s, r = modelo.adelante_set_complejos(h, grupos, device)
        return s.cpu().numpy(), r.cpu().numpy()


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


def evaluar(modelo: PoseSelectorSet, datos: list, pids: list, device,
            modo_ctx: str) -> dict:
    scores, _ = forward_todo_set(modelo, datos, device, modo_ctx, False)
    return metricas_por_pid(scores, datos, pids)


def evaluar_mc(modelo: PoseSelectorSet, datos: list, pids: list, device,
               modo_ctx: str, mc_samples: int = MC_SAMPLES) -> dict:
    """MC-dropout: matriz (N, mc) de scores; por complejo se elige por la
    media y se reporta la varianza del score de la pose seleccionada."""
    modelo.train()
    grupos, _ = grupos_de(datos)
    mascara = mascara_bloques(grupos, device)
    cols = []
    with torch.no_grad():
        for _ in range(mc_samples):
            h = extraer_h_todo(modelo, datos, device, modo_ctx)
            s, _ = modelo.adelante_set_complejos(h, grupos, device)
            cols.append(s.cpu().numpy())
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


def smoke_cpu(ckpt_path: Path, datos: list, modo_ctx: str) -> dict:
    """Inferencia CPU por COMPLEJO (el set-encoder requiere las poses
    juntas): ms por pose sobre val."""
    modelo = PoseSelectorSet()
    ck = torch.load(ckpt_path, weights_only=False, map_location="cpu")
    modelo.load_state_dict(ck["modelo"])
    modelo.eval()
    grupos, _ = grupos_de(datos)
    t0 = time.monotonic()
    ini = 0
    with torch.no_grad():
        for g in grupos:
            ch = datos[ini:ini + g]
            b = colacionar(ch, modo_ctx)
            h = modelo.extraer_h(b["prot_x"], b["prot_edge_index"],
                                 b["lig_x"], b["lig_edge_index"],
                                 b["cross_edge_index"], b["lig_pos"],
                                 b["prot_pos"], b["lig_batch"],
                                 b["prot_batch"], b["ecif"], b["ctx"])
            _s, _r = modelo.adelante_set(h, None)
            ini += g
    t = time.monotonic() - t0
    return {"n_poses": len(datos), "n_complejos": len(grupos),
            "duracion_s": round(t, 2),
            "ms_por_pose": round(1000.0 * t / max(len(datos), 1), 2)}


def atencion_hacia_seleccionada(modelo: PoseSelectorSet, datos: list,
                                pids: list, device,
                                modo_ctx: str) -> dict | None:
    """Bonus interpretabilidad (solo si es trivial): peso medio de
    atencion que las poses del complejo asignan a la pose finalmente
    seleccionada (argmax del score), usando la capa de atencion FINAL del
    set-encoder, media sobre las 4 cabezas. Recomputa la atencion de la
    ultima capa a mano (no altera el modelo)."""
    try:
        modelo.eval()
        grupos, _ = grupos_de(datos)
        mascara = mascara_bloques(grupos, device)
        with torch.no_grad():
            h = extraer_h_todo(modelo, datos, device, modo_ctx)
            hp = modelo.set_encoder(h, mask=mascara)
            media, maxima = estadisticas_por_grupo(hp, grupos, device)
            fusionado = modelo.fusion(
                torch.cat([hp, media, maxima, h - media], dim=-1))
            scores = modelo.score_head(fusionado).squeeze(-1).cpu().numpy()
            capas = modelo.set_encoder.layers
            h_prev = h
            for capa in capas[:-1]:
                h_prev = capa(h_prev, src_mask=mascara)
            ultima = capas[-1]
            qkv = F.linear(h_prev, ultima.self_attn.in_proj_weight,
                           ultima.self_attn.in_proj_bias)
            q, k, _v = qkv.chunk(3, dim=-1)
            n_nodos, d_total = q.shape
            hd = d_total // NHEAD
            q = q.view(n_nodos, NHEAD, hd)
            k = k.view(n_nodos, NHEAD, hd)
            atn = torch.einsum("nhd,mhd->nhm", q, k) / (hd ** 0.5)
            atn = atn + mascara[:, None, :]  # aditivo: -inf bloquea
            atn = F.softmax(atn, dim=-1)
            A = atn.mean(dim=1).cpu().numpy()  # (N, N)
        por_pid = defaultdict(list)
        for kk, d in enumerate(datos):
            por_pid[d.pid].append(kk)
        pesos = []
        for pid in pids:
            idxs = por_pid[pid]
            sel = idxs[int(np.argmax([scores[i] for i in idxs]))]
            pesos.append(float(np.mean([A[i, sel] for i in idxs])))
        return {"peso_medio_hacia_seleccionada": round(float(np.mean(pesos)), 5),
                "peso_mediano_hacia_seleccionada": round(float(np.median(pesos)), 5),
                "n_complejos": len(pids),
                "nota": ("atencion de la ultima capa (media sobre 4 cabezas), "
                         "sin dropout; valores sobre la diagonal de bloques "
                         "intra-complejo")}
    except Exception as e:
        return {"error": f"{type(e).__name__}: {str(e)[:80]}",
                "computado": False}


# ───────────────────────── entrenamiento ────────────────────────────────────

def entrenar(train, val, pids_val, device, i_idx, j_idx, marg_dev,
             y_centr_dev, prog: dict, reporte_warm: dict) -> dict:
    """Entrena la etapa unica (set) con reanudacion. Devuelve el historial."""
    st = prog.setdefault("set", {"status": "pendiente", "epoch": -1,
                                 "mejor_val_top1": -1.0, "paciencia": 0,
                                 "historial": [], "duracion_s": 0.0,
                                 "reanudado": False})
    if st.get("status") == "completo" and CKPT_SET.exists():
        pr(f"  [set] entrenamiento ya completo "
           f"(mejor val top1 = {st['mejor_val_top1']}).")
        return st["historial"]

    modelo = PoseSelectorSet()
    n_params = contar_params(modelo)
    grupos_opt = [
        {"params": (list(modelo.prot_encoder.parameters())
                    + list(modelo.lig_encoder.parameters())
                    + list(modelo.cross_attn.parameters())
                    + list(modelo.lig_pool.parameters())
                    + list(modelo.prot_pool.parameters())
                    + list(modelo.ecif_encoder.parameters())
                    + list(modelo.h_proj.parameters())),
         "lr": LR_ENC},
        {"params": (list(modelo.set_encoder.parameters())
                    + list(modelo.fusion.parameters())
                    + list(modelo.score_head.parameters())
                    + list(modelo.rmsd_head.parameters())),
         "lr": LR_SET},
    ]
    optim = torch.optim.Adam(grupos_opt, lr=LR_ENC,
                             weight_decay=WEIGHT_DECAY)
    ep_inicio = 0
    if CKPT_SET.exists() and st.get("status") == "en_progreso":
        ck = torch.load(CKPT_SET, weights_only=False, map_location=device)
        modelo.load_state_dict(ck["modelo"])
        optim.load_state_dict(ck["optimizador"])
        ep_inicio = ck["epoch"] + 1
        st["reanudado"] = True
        pr(f"  [set] reanudando desde epoca {ep_inicio} "
           f"(mejor val top1 = {st['mejor_val_top1']}).")
    modelo = modelo.to(device)
    st["status"] = "en_progreso"
    st["n_params"] = n_params
    st["warm_start"] = reporte_warm
    guardar_progreso_entreno(prog)
    pr(f"  [set] GNN set-level (B + warm-start v31) | params: {n_params:,} "
       f"(limite {LIMITE_PARAMS:,}) | pares train: {len(i_idx):,}")

    t0 = time.monotonic()
    for ep in range(ep_inicio, MAX_EPOCHS):
        t_ep = time.monotonic()
        modelo.train()
        optim.zero_grad()
        s, r = forward_todo_set(modelo, train, device, "vina", True)
        perdida_par = F.relu(marg_dev - (s[i_idx] - s[j_idx])).mean()
        perdida_aux = F.mse_loss(r, y_centr_dev)
        perdida = perdida_par + LAMBDA_AUX * perdida_aux
        perdida.backward()
        torch.nn.utils.clip_grad_norm_(modelo.parameters(), 1.0)
        optim.step()
        met_val = evaluar(modelo, val, pids_val, device, "vina")
        if met_val["top1_rate"] > st["mejor_val_top1"]:
            st["mejor_val_top1"] = met_val["top1_rate"]
            st["paciencia"] = 0
            torch.save({"modelo": modelo.state_dict(),
                        "optimizador": optim.state_dict(),
                        "epoch": ep, "config": {
                            "hidden": HIDDEN, "dropout": DROPOUT,
                            "set2set_steps": SET2SET_STEPS,
                            "ecif_dim": ECIF_DIM, "ecif_emb": ECIF_EMB,
                            "ecif_enc_hidden": ECIF_ENC_HIDDEN,
                            "ecif_dropout": ECIF_DROPOUT,
                            "ctx_dim": CTX_DIM, "ctx": "vina",
                            "d_model": D_MODEL, "nhead": NHEAD,
                            "tf_layers": TF_LAYERS,
                            "tf_dropout": TF_DROPOUT,
                            "ff_dim": FF_DIM,
                            "fusion_hidden": FUSION_HIDDEN,
                            "lr_enc": LR_ENC, "lr_set": LR_SET,
                            "weight_decay": WEIGHT_DECAY,
                            "lambda_aux": LAMBDA_AUX,
                            "semilla": SEMILLA},
                        "n_params": n_params, "val": met_val,
                        "warm_start": reporte_warm}, CKPT_SET)
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
        pr(f"  [set] ep {ep}: pair {float(perdida_par.item()):.4f} "
           f"aux {float(perdida_aux.item()):.4f} | val top1 "
           f"{met_val['top1_rate']} mediana {met_val['mediana_rmsd']} "
           f"| paciencia {st['paciencia']}/{PACENCIA} "
           f"({time.monotonic() - t_ep:.0f}s)")
        if st["paciencia"] >= PACENCIA:
            pr(f"  [set] early stop en epoca {ep} "
               f"(paciencia {PACENCIA} agotada).")
            break
    st["status"] = "completo"
    st["duracion_s"] = round(time.monotonic() - t0, 1)
    guardar_progreso_entreno(prog)
    return st["historial"]


# ───────────────────────── flujo principal ──────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true",
                        help="chequeo rapido: warm-start + params + forward "
                             "CPU de 2 complejos, sin entrenar")
    args = parser.parse_args()

    configurar_salida()
    t0 = time.monotonic()
    pr("== Ruta C Fase 2.3: GNN set-level (B) con warm-start estricto desde "
       "gnn_v31_best.pt (docs/42) ==")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    pr(f"  dispositivo: {device} "
       f"({torch.cuda.get_device_name(0) if device.type == 'cuda' else 'CPU'})")
    torch.manual_seed(SEMILLA)
    if device.type == "cuda":
        torch.cuda.manual_seed(SEMILLA)

    if args.smoke:
        registros = cargar_todos_los_registros()
        construir_cache_ecif(registros)
        ctx_por_clave, _ = construir_ctx()
        datos, conteos = cargar_dataset(ctx_por_clave, "vina")
        modelo = PoseSelectorSet()
        rep = cargar_warm_start_v31(modelo)
        n_params = contar_params(modelo)
        pr(f"  smoke: params {n_params:,} | coinciden "
           f"{rep['coincidentes']}/{rep['total_claves_v31']} | omitidas "
           f"cabezas {len(rep['omitidas_cabezas_v31'])} | omitidas flag "
           f"{len(rep['omitidas_flag_v31'])} | nuevas aleatorias "
           f"{len(rep['nuevas_aleatorias'])}")
        ch = datos["val"][:2]
        with torch.no_grad():
            h = extraer_h_todo(modelo, ch, torch.device("cpu"), "vina")
            s, r = modelo.adelante_set_complejos(
                h, grupos_de(ch)[0], torch.device("cpu"))
        pr(f"  smoke: forward ok — h {tuple(h.shape)}, score {tuple(s.shape)}")
        pr("  smoke completo.")
        return

    # ── ECIF + contexto ──
    registros = cargar_todos_los_registros()
    resumen_ecif = construir_cache_ecif(registros)
    ctx_por_clave, resumen_ctx = construir_ctx()

    prog = cargar_progreso_entreno()
    art: dict = {
        "generated_at": ahora_iso(),
        "protocolo": "docs/42_RUTA_C_PROTOCOLO.md",
        "fase": ("2.3 variante estricta (GNN set-level B con warm-start "
                 "desde gnn_v31_best.pt — el mejor activo GNN del "
                 "proyecto, test ROC-AUC 0.877)"),
        "hipotesis": ("el fracaso de B (0.5106) no es de arquitectura sino "
                      "de INICIALIZACION: el backbone per-pose venia del "
                      "selector v2 (0.5106, correlacionado con el mismo "
                      "regimen de falla). Al warm-startear desde "
                      "gnn_v31_best.pt (tarea distinta: clasificacion "
                      "P(binder)+delta pKi sobre PDBbind, ROC-AUC 0.877), "
                      "el encoder per-pose aporta representaciones "
                      "diversas y la relatividad cross-pose (C4) puede "
                      "superar al campeon v0.6 (0.6596) en el holdout "
                      "congelado"),
        "gate_criterio": f"pose_selector_set_v31init_test_top1 > "
                         f"{TOP1_V06_TEST} (top-1 v0.6)",
        "config": {
            "arquitectura": {
                "encoder_per_pose": ("ProteinEncoder GAT-Ca 24->128 (4 "
                                     "cabezas, 2 capas) + LigandEncoder GIN "
                                     "38->128 (3 capas) + CrossAttention "
                                     "(bias distancia 3.5 A + tipo residuo) "
                                     "+ Set2Set x2 (4 pasos), clases de "
                                     "rescoring/gnn_v2/models.py; warm-start "
                                     "desde rescoring/artifacts/"
                                     "gnn_v31_best.pt (GNNv31Classifier, "
                                     "hidden 128, dropout 0.2, test "
                                     "ROC-AUC 0.877)"),
                "hidden_dim": HIDDEN,
                "ecif_rama": (f"definicion del checkpoint v31: Linear("
                              f"{ECIF_DIM}->{ECIF_ENC_HIDDEN}) + ELU + "
                              f"Dropout({ECIF_DROPOUT}) + Linear("
                              f"{ECIF_ENC_HIDDEN}->{ECIF_EMB}) + ELU + "
                              f"Dropout({ECIF_DROPOUT}) — adaptada desde el "
                              f"MLP de una capa de B para cargar los pesos "
                              f"v31"),
                "ctx_rama": ("por complejo dentro de cada split (v0.6): "
                             "z-score (std=0 -> 0) y percentil (empates -> "
                             "rango promedio; complejo de 1 pose -> 50) de "
                             "vina_score y cluster_density"),
                "ctx_principal": ("[vina_raw, z_vina, pct_vina, z_cluster, "
                                  "pct_cluster] (5)"),
                "h_i": (f"concat(graph_emb {4 * HIDDEN}, ecif_emb "
                        f"{ECIF_EMB}, ctx {CTX_DIM}) = 581 -> Linear(581->"
                        f"{D_MODEL}) + ReLU + dropout {DROPOUT} "
                        f"(embedding per-pose {D_MODEL})"),
                "atencion_cross_pose": (
                    f"{TF_LAYERS} capas de nn.TransformerEncoderLayer "
                    f"(d_model {D_MODEL}, nhead {NHEAD}, dim_feedforward "
                    f"{FF_DIM}, dropout {TF_DROPOUT}, batch_first) con "
                    "mascara intra-complejo en bloques sobre el lote "
                    "completo (poses de pids distintos jamas se atienden); "
                    "invariante a permutacion por agregacion simetrica "
                    "(media/max por complejo)"),
                "fusion": (f"concat[h'_i, mean(h')_complejo, "
                           f"max(h')_complejo, h_i - mean(h')_complejo] "
                           f"(4 x {D_MODEL} = {4 * D_MODEL}) -> Linear("
                           f"{4 * D_MODEL}->{FUSION_HIDDEN}) + ReLU + "
                           f"dropout {DROPOUT}"),
                "cabezas": ("score (Linear 128->1) + rmsd aux "
                            "(Linear 128->1)"),
                "desviaciones_honestas": [
                    ("dim_feedforward=128 (el default es 2048): con el "
                     "backbone warm-start de ~613 K params, un ff mayor "
                     "excede el limite de 1.6 M; la atencion multi-cabeza "
                     "completa (4 cabezas x 64) se conserva."),
                    ("fusion de UNA capa Linear(1024->128) en lugar de un "
                     "MLP de dos capas (1024->256->128): una fusion de dos "
                     "capas + 2 capas de atencion d_model 256 excederian "
                     "el limite de 1.6 M params."),
                ],
            },
            "perdida": {
                "pairwise": ("por complejo, todos los pares (i,j) con "
                             "rmsd_i <= rmsd_j (empates incluidos, ambas "
                             "direcciones), i != j; normalizada por total "
                             "de pares (C3, igual que v2)"),
                "margen": "clip(0.3 + 0.5*(rmsd_j - rmsd_i), 0.3, 2.0)",
                "auxiliar": ("MSE(rmsd_head, rmsd - mediana_del_complejo) "
                             "sobre poses con rmsd valido"),
                "lambda_aux": LAMBDA_AUX,
                "grupos_1_pose": "solo auxiliar",
            },
            "optimizacion": {
                "opt": "Adam", "lr_enc": LR_ENC, "lr_set": LR_SET,
                "weight_decay": WEIGHT_DECAY, "max_epochs": MAX_EPOCHS,
                "paciencia_val_top1": PACENCIA,
                "batch_poses_gnn": BATCH_POSES, "semilla": SEMILLA,
                "dispositivo": str(device),
                "grupos_parametros": ("backbone+ecif+h_proj lr 1e-3; "
                                      "set_encoder+fusion+cabezas lr 3e-3"),
                "esquema_computo": ("1 forward por pose por epoca (GNN en "
                                    "lotes de 64) + set-encoder sobre "
                                    "TODAS las poses del split con mascara "
                                    "en bloques + perdida pairwise "
                                    "vectorizada en un solo backward"),
                "n_pares_train": None,
                "limite_params": LIMITE_PARAMS,
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

    # ── Warm start desde gnn_v31_best.pt ──
    modelo_sonda = PoseSelectorSet()
    reporte_warm = cargar_warm_start_v31(modelo_sonda)
    del modelo_sonda
    pr(f"  warm-start v31: {reporte_warm['coincidentes']}/"
       f"{reporte_warm['total_claves_v31']} claves coinciden; "
       f"omitidas cabezas: {len(reporte_warm['omitidas_cabezas_v31'])}; "
       f"omitidas flag: {len(reporte_warm['omitidas_flag_v31'])}; "
       f"nuevas aleatorias: {len(reporte_warm['nuevas_aleatorias'])}")
    art["warm_start"] = reporte_warm
    guardar_artefacto(art, "warm_start")

    # ── Datos ──
    datos, conteos = cargar_dataset(ctx_por_clave, "vina")
    for s in ("train", "val", "test"):
        n = len({d.pid for d in datos[s]})
        pr(f"  [set] {s}: {len(datos[s])} grafos, {n} complejos")
    art["adjuntos_ecif_ctx"] = conteos
    guardar_artefacto(art, "datos_cargados")

    # ── Pares ──
    grupos_train, pids_train = grupos_de(datos["train"])
    _gv, pids_val = grupos_de(datos["val"])
    _gt, pids_test = grupos_de(datos["test"])
    y_train = np.array([d.y_rmsd for d in datos["train"]], dtype=np.float64)
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
        s: baseline_vina(datos[s], {"train": pids_train, "val": pids_val,
                                    "test": pids_test}[s])
        for s in ("train", "val", "test")}
    pr("  vina recomputado: " + json.dumps(
        {s: art["vina_baseline_recomputado"][s]["top1_rate"]
         for s in ("train", "val", "test")}, ensure_ascii=False))
    guardar_artefacto(art, "vina_recomputado")

    # ── Entrenamiento ──
    hist = entrenar(datos["train"], datos["val"], pids_val, device,
                    i_idx, j_idx, marg_dev, y_centr_dev, prog,
                    reporte_warm)
    art["entrenamiento_set"] = {
        "descripcion": ("GNN set-level (B) con warm-start estricto desde "
                        "gnn_v31_best.pt + atencion cross-pose C4"),
        "n_params": prog["set"]["n_params"],
        "limite_params": LIMITE_PARAMS,
        "params_dentro_limite": prog["set"]["n_params"] <= LIMITE_PARAMS,
        "epochs_ejecutadas": len(hist),
        "mejor_epoch": (min((h["epoch"] for h in hist
                            if h["val_top1"] == prog["set"]
                            ["mejor_val_top1"]), default=None)),
        "mejor_val_top1": prog["set"]["mejor_val_top1"],
        "early_stopped": (prog["set"]["paciencia"] >= PACENCIA),
        "duracion_s": prog["set"]["duracion_s"],
        "reanudado": prog["set"].get("reanudado", False),
        "val_top1_cada_5": {h["epoch"]: h["val_top1"] for h in hist
                            if h["epoch"] % 5 == 0},
        "historial": hist,
    }
    guardar_artefacto(art, "entrenado_set")

    # ── Evaluacion final (val + test + MC test + smoke CPU + bonus) ──
    modelo = PoseSelectorSet()
    ck = torch.load(CKPT_SET, weights_only=False, map_location=device)
    modelo.load_state_dict(ck["modelo"])
    modelo = modelo.to(device)
    met = {}
    for s, pids in (("val", pids_val), ("test", pids_test)):
        met[s] = evaluar(modelo, datos[s], pids, device, "vina")
    met["mc_test"] = evaluar_mc(modelo, datos["test"], pids_test, device,
                                "vina")
    met["smoke_cpu"] = smoke_cpu(CKPT_SET, datos["val"], "vina")
    met["atencion_bonus_test"] = atencion_hacia_seleccionada(
        modelo, datos["test"], pids_test, device, "vina")
    art["evaluacion_set"] = met
    guardar_artefacto(art, "evaluado_set")
    pr(f"  [set] val top1 {met['val']['top1_rate']} | "
       f"test top1 {met['test']['top1_rate']} | "
       f"test mediana {met['test']['mediana_rmsd']} | "
       f"test spearman {met['test']['spearman_pred_vs_rmsd_media']} | "
       f"MC var media {met['mc_test']['varianza_media_pose_seleccionada']}")

    # ── Tabla comparativa con fases previas ──
    previos = {}
    for nombre_archivo in ("artifacts_ruta_c_fase1.json",
                           "artifacts_ruta_c_fase1_5.json",
                           "artifacts_ruta_c_fase1_6.json",
                           "artifacts_ruta_c_fase2.json",
                           "artifacts_ruta_c_fase2_1.json",
                           "artifacts_ruta_c_fase2_2.json"):
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
    a21 = previos.get("artifacts_ruta_c_fase2_1.json", {})
    a22 = previos.get("artifacts_ruta_c_fase2_2.json", {})
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
            "gnn_v2_top1": a21.get("evaluacion_v2", {}).get(split, {}).get(
                "top1_rate"),
            "gnn_v2_mediana": a21.get("evaluacion_v2", {}).get(
                split, {}).get("mediana_rmsd"),
            "gnn_set_B_top1": a22.get("evaluacion_set", {}).get(
                split, {}).get("top1_rate"),
            "gnn_set_B_mediana": a22.get("evaluacion_set", {}).get(
                split, {}).get("mediana_rmsd"),
            "gnn_set_B_v31init_top1": met[split]["top1_rate"],
            "gnn_set_B_v31init_mediana": met[split]["mediana_rmsd"],
            "gnn_set_B_v31init_spearman": met[split][
                "spearman_pred_vs_rmsd_media"],
        }
    art["comparacion"] = tabla

    # ── Gate ──
    set_test = met["test"]["top1_rate"]
    if set_test > TOP1_V06_TEST:
        veredicto = ("PASS — B+v31init supera a v0.6: la linea GNN de "
                     "Ruta C se REABRE (el orquestador decide el siguiente "
                     "paso)")
    else:
        veredicto = ("FAIL — B+v31init no supera a v0.6: se cierra "
                     "honestamente la linea GNN de Ruta C y v0.6 (XGBoost) "
                     "se promueve como selector de poses de Ruta C "
                     "(regla preacordada)")
    art["gate"] = {
        "criterio": f"pose_selector_set_v31init_test_top1 > "
                    f"{TOP1_V06_TEST} (campeon v0.6)",
        "regla_de_decision": ("si B+v31init test top-1 > 0.6596 -> la "
                              "linea GNN se REABRE; si NO -> la linea GNN "
                              "se cierra y v0.6 XGBoost se promueve como "
                              "selector de Ruta C (regla preacordada antes "
                              "de cerrar la linea)"),
        "B_v31init_top1_test": set_test,
        "B_fase2_2_top1_test": a22.get("evaluacion_set", {}).get(
            "test", {}).get("top1_rate"),
        "v06B_top1_test": TOP1_V06_TEST,
        "vina_top1_test": TOP1_VINA_TEST,
        "delta_vs_v06B": round(set_test - TOP1_V06_TEST, 4),
        "resultado": "PASS" if set_test > TOP1_V06_TEST else "FAIL",
        "veredicto": veredicto,
    }
    guardar_artefacto(art, "gate")
    pr(f"  Gate: {art['gate']['resultado']} "
       f"(B+v31init {set_test} vs v0.6 {TOP1_V06_TEST})")

    # ── Curvas de perdida ──
    art["curvas_perdida"] = {
        "epochs": [h["epoch"] for h in hist],
        "loss_pair": [h["loss_pair"] for h in hist],
        "loss_aux": [h["loss_aux"] for h in hist],
        "loss_total": [h["loss_total"] for h in hist],
        "val_top1": [h["val_top1"] for h in hist],
    }

    art["caveats_honestos"] = [
        ("dim_feedforward del TransformerEncoderLayer = 128 (default "
         "2048): con el backbone warm-start (~613 K params), 2 capas "
         "de atencion d_model 256 + ff mayor exceden el limite de 1.6 M "
         "params; la atencion multi-cabeza completa (4 x 64) se conserva."),
        ("La fusion es de UNA capa Linear(1024->128) + ReLU + dropout 0.3; "
         "una fusion de dos capas (1024->256->128) excederia el limite de "
         "1.6 M params."),
        ("La rama ECIF fue ADAPTADA a la definicion del checkpoint v31 "
         "(Linear 152->128 + ELU + Dropout(0.2) + Linear 128->64 + ELU + "
         "Dropout(0.2)) en lugar del MLP de una capa de B; es la unica "
         "diferencia de arquitectura respecto de B, exigida por el mapeo "
         "de pesos."),
        ("El dropout de los encoders GAT/GIN/cross y de h_proj/fusion es "
         "0.3 (protocolo de B); el checkpoint v31 entreno esos modulos con "
         "dropout 0.2. Solo la rama ECIF usa el dropout del checkpoint "
         "(0.2). El dropout no afecta el mapeo de pesos."),
        ("El checkpoint v31 entreno para OTRA tarea (clasificacion "
         "P(binder) + delta pKi sobre PDBbind curado 568/70/70, "
         "ROC-AUC 0.877): hay cambio de dominio y de objetivo respecto "
         "del ranking de poses de Ruta C; sus pesos traen sesgos de esa "
         "tarea."),
        ("ecif_missing_flag (parametro v31 de 1 dim para ECIF faltante) "
         "se OMITE: B rellena ECIF faltante con 0.0 y su fusion no "
         "consume bandera."),
        ("gnn_v31_best.pt es un state_dict bruto sin metadatos de "
         "entrenamiento; el contexto (epochs, AUC) se toma de "
         "gnn_v31_results.json."),
        ("La rama ECIF usa extract_from_pose con skip_prolif=True (cache "
         "reutilizado de v2, 4300/4300 registros ok)."),
        ("Registros sin ECIF computable se rellenan con 0.0 + bandera "
         "ecif_ok=False; la fusion NO consume la bandera."),
        ("Val tiene solo 40 complejos: el early stop es ruidoso; la "
         "comparacion del gate es sobre el test congelado (47 complejos)."),
        ("MC-dropout usa dropout activo en inferencia (modelo en modo "
         "train); las varianzas son un proxy de incertidumbre, no "
         "calibradas."),
        ("Si el entrenamiento se reanudo tras un crash, la secuencia RNG "
         "difiere de una corrida ininterrumpida (bandera 'reanudado')."),
        ("En inferencia de produccion el modelo set-level requiere TODAS "
         "las poses del complejo juntas (no es per-pose); complejos de 1 "
         "pose degeneran a auto-atencion."),
        ("La atencion intra-complejo incluye la diagonal (cada pose se "
         "atiende a si misma); poses de pids distintos jamas se atienden."),
    ]
    art["duracion_total_s"] = round(time.monotonic() - t0, 1)
    guardar_artefacto(art, "completo")
    pr(f"  artefacto: {ARTIFACTOS} ({art['duracion_total_s']}s)")


if __name__ == "__main__":
    main()
