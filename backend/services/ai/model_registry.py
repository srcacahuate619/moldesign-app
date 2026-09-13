"""
services/ai/model_registry.py

Registry de modelos GGUF: buscar en HuggingFace, descargar, listar locales.

Fuentes oficiales:
  - HuggingFace Hub Search API (https://huggingface.co/api/models)
  - Solo modelos con tag "gguf" (cuantizados, listos para llama.cpp)
  - Descarga via huggingface_hub con progreso trackeable
"""

from __future__ import annotations

import threading
import time
import uuid
from pathlib import Path

from utils.logger import get_logger

log = get_logger(__name__)

# ── Downloads tracking ──────────────────────────────────────────────
_downloads: dict[str, dict] = {}
_downloads_lock = threading.Lock()


def _get_hf_list_models(
    query: str, limit: int = 16, user_id: str | None = None
) -> list[dict]:
    """
    Buscar modelos GGUF en HuggingFace via API REST.
    No requiere autenticacion ni token (endpoint publico).
    """
    import urllib.request
    import json as _json

    url = (
        f"https://huggingface.co/api/models"
        f"?search={urllib.parse.quote(query)}"
        f"&sort=downloads"
        f"&direction=-1"
        f"&limit={min(limit, 30)}"
        f"&full=false"
    )
    # Buscar un modelo manda el texto de búsqueda a HuggingFace: es una salida
    # de la máquina como cualquier otra, y pasa por la misma puerta que las
    # herramientas (`services/ai/red.py`).
    from services.ai.tools.web_tools import _http_get_json

    try:
        data = _http_get_json(url, timeout=10, user_id=user_id)
        if data is None:
            return []
    except Exception as e:
        log.warning("hf_search_failed", error=str(e)[:100])
        return []

    results = []
    for model in data:
        tags = model.get("tags", []) or []
        pipeline_tag = model.get("pipeline_tag", "") or ""

        is_gguf = any(
            "gguf" in (t.lower() if isinstance(t, str) else "") for t in tags
        ) or "gguf" in pipeline_tag.lower()

        if not is_gguf:
            continue

        model_id = model.get("id") or model.get("modelId", "")
        if not model_id:
            continue

        results.append({
            "id": model_id,
            "author": model.get("author", ""),
            "downloads": model.get("downloads", 0),
            "likes": model.get("likes", 0),
            "pipeline_tag": pipeline_tag,
            "tags": [t for t in tags if isinstance(t, str)][:10],
            "url": f"https://huggingface.co/{model_id}",
            "created_at": model.get("createdAt", ""),
        })

    return results


def _scan_logical_gguf_files(model_id: str, user_id: str | None = None) -> list[dict]:
    """Obtener archivos .gguf disponibles para un modelo via HF API."""
    import urllib.request
    import json as _json

    from services.ai.tools.web_tools import _http_get_json

    try:
        url = f"https://huggingface.co/api/models/{model_id}?full=true"
        data = _http_get_json(url, timeout=10, user_id=user_id)
        if data is None:
            return []
    except Exception:
        return []

    siblings = data.get("siblings", []) or []
    gguf_files = []
    for sib in siblings:
        if not isinstance(sib, dict):
            continue
        fname = sib.get("rfilename", "")
        if fname.lower().endswith(".gguf"):
            size_mb = round((sib.get("size", 0) or 0) / (1024 * 1024), 1)
            size_gb = round(size_mb / 1024, 1) if size_mb > 0 else 0
            display_size = f"{size_gb:.1f} GB" if size_gb >= 1 else f"{size_mb:.0f} MB"
            quant = _extract_quant(fname)
            gguf_files.append({
                "filename": fname,
                "size_mb": size_mb,
                "size_display": display_size,
                "quant": quant,
            })
    gguf_files.sort(key=lambda x: x.get("size_mb", 0))
    return gguf_files


def _extract_quant(filename: str) -> str:
    """Extraer nivel de cuantizacion del nombre del archivo."""
    import re
    patterns = ["Q8_0", "Q6_K", "Q5_K_M", "Q5_K_S", "Q4_K_M", "Q4_K_S",
                "Q3_K_M", "Q3_K_S", "Q2_K", "IQ4_XS", "IQ3_XXS", "F16", "F32"]
    fname_upper = filename.upper()
    for p in patterns:
        if re.search(p.replace("_", "_"), fname_upper, re.IGNORECASE):
            return p
    return "?"


def get_local_models() -> list[dict]:
    """
    Escanear archivos .gguf disponibles localmente en MODEL_SEARCH_PATHS.
    Retorna lista con {filename, path, size_mb, size_display, quant}.
    """
    from services.ai.local_llm import MODEL_SEARCH_PATHS

    results = []
    seen = set()
    for search_dir in MODEL_SEARCH_PATHS:
        try:
            for f in search_dir.glob("*.gguf"):
                fname = f.name
                if fname in seen:
                    continue
                seen.add(fname)
                size_mb = round(f.stat().st_size / (1024 * 1024), 1)
                size_gb = round(size_mb / 1024, 1)
                display_size = f"{size_gb:.1f} GB" if size_gb >= 1 else f"{size_mb:.0f} MB"
                results.append({
                    "filename": fname,
                    "path": str(f),
                    "size_mb": size_mb,
                    "size_display": display_size,
                    "quant": _extract_quant(fname),
                })
        except Exception:
            pass
    results.sort(key=lambda x: x.get("filename", ""))
    return results


# ── Quantization recommendation ─────────────────────────────────────

# map quant level → (label, quality_descr, approx_model_size_gb, min_ram_gb)
_QUANT_INFO: dict[str, tuple[str, str, float, float]] = {
    "Q4_K_M": ("Q4_K_M", "Calidad media-alta. Recomendado (Qwen2.5 1.1 GB)", 1.1, 2.5),
    "Q4_K_S": ("Q4_K_S", "Calidad media. Más chico, más rápido, menos preciso", 2.2, 3.5),
    "Q5_K_M": ("Q5_K_M", "Calidad buena. Mejor precisión que Q4", 3.0, 5.0),
    "Q5_K_S": ("Q5_K_S", "Calidad buena (compacto). Buen balance", 2.7, 4.5),
    "Q6_K": ("Q6_K", "Calidad alta. Casi sin pérdida perceptible", 3.5, 5.5),
    "Q8_0": ("Q8_0", "Calidad muy alta. Uso profesional", 4.5, 7.0),
    "F16": ("F16", "Precisión completa (FP16). Sin cuantización", 7.5, 11.0),
    "F32": ("F32", "Precisión total (FP32). Solo para investigación", 14.0, 18.0),
    "IQ4_XS": ("IQ4_XS", "Importance-matrix Q4. Calidad ~Q4_K_M, más chico", 2.2, 3.5),
    "IQ3_XXS": ("IQ3_XXS", "Importance-matrix Q3. Compacto extremo", 2.0, 3.0),
}


def recommend_quantization(ram_free_gb: float = 0.0, vram_free_gb: float = -1.0) -> dict:
    """
    Recomendar nivel de cuantización según recursos disponibles.

    Prioriza GPU si hay VRAM suficiente. Si no, usa RAM del sistema.
    Retorna {recommended, options: [{quant, label, description, fits, is_recommended}]}
    """
    available = max(ram_free_gb, vram_free_gb if vram_free_gb > 0 else 0)
    use_gpu = vram_free_gb > 0
    resource_type = "VRAM" if use_gpu else "RAM"
    resource_gb = vram_free_gb if use_gpu else ram_free_gb

    options = []
    recommended = "Q4_K_M"
    best_score = -1

    for quant, (label, desc, model_size, min_ram) in _QUANT_INFO.items():
        fits = available >= min_ram
        score = 0
        if fits:
            score += 1
            if model_size <= available * 0.7:
                score += 1
            if use_gpu and model_size <= vram_free_gb:
                score += 1
            if quant in ("Q4_K_M", "Q5_K_M", "Q6_K"):
                score += 1

            if score > best_score:
                best_score = score
                recommended = quant

        options.append({
            "quant": quant,
            "label": label,
            "description": desc,
            "model_size_gb": model_size,
            "min_ram_gb": min_ram,
            "fits": fits,
            "is_recommended": False,
        })

    for opt in options:
        if opt["quant"] == recommended:
            opt["is_recommended"] = True
            break

    options.sort(key=lambda x: x["model_size_gb"])

    return {
        "recommended": recommended,
        "resource_type": resource_type,
        "resource_available_gb": round(resource_gb, 1),
        "using_gpu": use_gpu,
        "options": options,
    }


def start_download(model_id: str, filename: str) -> dict:
    """
    Iniciar descarga de un archivo GGUF. Corre en background thread.

    Returns:
        {download_id, status: "downloading", filename, model_id}
    """
    dl_id = str(uuid.uuid4())[:8]

    with _downloads_lock:
        _downloads[dl_id] = {
            "id": dl_id,
            "model_id": model_id,
            "filename": filename,
            "status": "downloading",
            "progress_pct": 0.0,
            "downloaded_mb": 0.0,
            "total_mb": 0.0,
            "started_at": time.time(),
            "error": None,
            "local_path": None,
        }

    thread = threading.Thread(
        target=_run_download, args=(dl_id, model_id, filename), daemon=True,
    )
    thread.start()
    return _downloads[dl_id]


def _run_download(dl_id: str, model_id: str, filename: str):
    """Background thread: descargar el modelo y actualizar progreso."""
    try:
        from huggingface_hub import hf_hub_download

        target_dir = Path(__file__).parent.parent.parent.parent / "models" / "llm"
        target_dir.mkdir(parents=True, exist_ok=True)

        def _on_progress(total_mb: float, downloaded_mb: float):
            pct = round((downloaded_mb / total_mb) * 100, 1) if total_mb > 0 else 0
            with _downloads_lock:
                if dl_id in _downloads:
                    _downloads[dl_id].update(
                        progress_pct=pct,
                        downloaded_mb=round(downloaded_mb, 1),
                        total_mb=round(total_mb, 1),
                    )

        local_path = hf_hub_download(
            repo_id=model_id,
            filename=filename,
            local_dir=str(target_dir),
            local_dir_use_symlinks=False,
            resume_download=True,
        )

        with _downloads_lock:
            if dl_id in _downloads:
                _downloads[dl_id].update(
                    status="completed",
                    progress_pct=100.0,
                    local_path=local_path,
                )
        log.info("model_download_complete", model=model_id, file=filename)

    except Exception as e:
        with _downloads_lock:
            if dl_id in _downloads:
                _downloads[dl_id].update(
                    status="failed",
                    error=str(e)[:200],
                )
        log.error("model_download_failed", model=model_id, error=str(e)[:150])


def get_download_status(dl_id: str) -> dict | None:
    with _downloads_lock:
        dl = _downloads.get(dl_id)
        if dl:
            return dict(dl)
    return None


def cleanup_old_downloads(max_age_s: float = 3600):
    now = time.time()
    with _downloads_lock:
        expired = [
            k for k, v in _downloads.items()
            if v["status"] in ("completed", "failed")
            and (now - v.get("started_at", 0)) > max_age_s
        ]
        for k in expired:
            del _downloads[k]
