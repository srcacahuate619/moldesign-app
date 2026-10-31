"""Local model files: find installed .gguf, download new ones (simplified).

Search is machine-agnostic: explicit directories, ``~/.molchat/models`` and
a relative ``models/llm``. Downloads are operator-invoked (CLI), streamed
with a byte cap, and verified against SHA-256 when the operator provides one.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlsplit

import httpx

DEFAULT_MODEL_DIRS: tuple[str, ...] = (".molchat/models", "models/llm")
DOWNLOAD_CAP = 20_000_000_000  # 20 GB: rejects absurd content-lengths early


class ModelError(RuntimeError):
    """A model file operation failed loudly."""


@dataclass(frozen=True)
class ModelInfo:
    name: str
    path: Path
    bytes: int


def default_model_dirs() -> list[Path]:
    return [Path.home() / ".molchat" / "models", Path("models") / "llm"]


def find_models(extra_dirs: list[Path] | None = None) -> list[ModelInfo]:
    """List installed .gguf files, biggest last, duplicates by name collapsed."""
    seen: dict[str, ModelInfo] = {}
    for directory in [*(extra_dirs or []), *default_model_dirs()]:
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.gguf")):
            try:
                seen.setdefault(path.name, ModelInfo(
                    name=path.name, path=path, bytes=path.stat().st_size))
            except OSError:
                continue
    return sorted(seen.values(), key=lambda m: m.bytes)


def resolve_model(name_or_path: str | Path,
                  extra_dirs: list[Path] | None = None) -> Path:
    """Resolve a model path or filename. Raises ModelError when missing."""
    candidate = Path(name_or_path)
    if candidate.is_file():
        return candidate
    if not candidate.is_absolute():
        for directory in [*(extra_dirs or []), *default_model_dirs()]:
            found = directory / candidate.name
            if found.is_file():
                return found
    raise ModelError(f"Modelo no encontrado: {name_or_path} "
                     f"(buscado en {[str(d) for d in default_model_dirs()]})")


def download_model(url: str, dest: Path, *, sha256_hex: str | None = None,
                   max_bytes: int = DOWNLOAD_CAP,
                   transport: httpx.BaseTransport | None = None) -> Path:
    """Download a model over HTTPS with cap + optional hash check.

    Sync (operator CLI context): streams to ``dest`` with ``.part`` staging
    and atomic rename. Only https URLs; redirects are not followed.
    """
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname:
        raise ModelError("solo se descargan modelos por https")
    dest.parent.mkdir(parents=True, exist_ok=True)
    staging = dest.with_suffix(dest.suffix + ".part")
    digest = sha256()
    total = 0
    client = httpx.Client(transport=transport) if transport is not None \
        else httpx.Client(follow_redirects=False, timeout=60.0)
    try:
        with client.stream("GET", url) as response:
            if response.status_code >= 400:
                raise ModelError(f"descarga falló: HTTP {response.status_code}")
            declared = response.headers.get("content-length")
            if declared and declared.isdigit() and int(declared) > max_bytes:
                raise ModelError(f"el modelo supera el tope de {max_bytes} bytes")
            with open(staging, "wb") as out:
                for chunk in response.iter_bytes():
                    total += len(chunk)
                    if total > max_bytes:
                        raise ModelError(f"el modelo supera el tope de {max_bytes} bytes")
                    digest.update(chunk)
                    out.write(chunk)
    except httpx.RequestError as exc:
        raise ModelError(f"no se pudo descargar: {exc}") from exc
    finally:
        client.close()
    if sha256_hex is not None and digest.hexdigest() != sha256_hex.lower():
        staging.unlink(missing_ok=True)
        raise ModelError("el SHA-256 descargado no coincide; nada instalado")
    staging.replace(dest)
    return dest
