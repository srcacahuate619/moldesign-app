"""
Script para descargar de forma robusta los pesos de ESMFold v1 (8.44 GB)
con soporte de reanudación (Range requests), verificación de SHA-256
y colocación en D:\\moldesign-build\\esmfold\\models\\pytorch_model.bin.
"""

import hashlib
import os
import sys
import time
import urllib.request
from pathlib import Path

URL = "https://huggingface.co/srcacahuate/moldesign-models/resolve/a12fe0cc72c86cb0f8326fba17879c300508a04e/v1.0.0/esmfold/models/pytorch_model.bin"
EXPECTED_SHA256 = "2ee07356b125d1e3e57503c204111fd7323347fc4735d41d3caac57c2a78e116"
EXPECTED_BYTES = 8442062570

ROOT = Path(__file__).resolve().parents[1]
DEST_DIR = ROOT / "esmfold" / "models"
TARGET_FILE = DEST_DIR / "pytorch_model.bin"
PART_FILE = DEST_DIR / "pytorch_model.bin.part"


def verify_sha256(path: Path, expected: str) -> bool:
    print(f"Calculando SHA-256 de {path} ({path.stat().st_size / 1024 / 1024:.1f} MB)...")
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1024 * 1024 * 4):
            hasher.update(chunk)
    actual = hasher.hexdigest()
    if actual == expected:
        print("  SHA-256 verificado con exito!")
        return True
    else:
        print(f"  ERROR: SHA-256 no coincide.")
        print(f"    Esperado: {expected}")
        print(f"    Obtenido: {actual}")
        return False


def download():
    DEST_DIR.mkdir(parents=True, exist_ok=True)

    if TARGET_FILE.exists():
        if TARGET_FILE.stat().st_size == EXPECTED_BYTES:
            print("El archivo pytorch_model.bin ya existe y tiene el tamaño exacto.")
            if verify_sha256(TARGET_FILE, EXPECTED_SHA256):
                print("ESMFold ya está completamente listo.")
                return
            else:
                print("El archivo existente está dañado. Se reemplazará...")
        else:
            print(f"Tamaño actual ({TARGET_FILE.stat().st_size}) difiere de lo esperado ({EXPECTED_BYTES}).")

    existing_bytes = 0
    if PART_FILE.exists():
        existing_bytes = PART_FILE.stat().st_size
        print(f"Reanudando descarga existente desde byte {existing_bytes} ({existing_bytes / 1024 / 1024:.2f} MB)...")

    req = urllib.request.Request(
        URL,
        headers={
            "User-Agent": "MolDesign-Launcher/1.0",
        }
    )
    if existing_bytes > 0:
        req.add_header("Range", f"bytes={existing_bytes}-")

    print(f"Conectando a Hugging Face...")
    t_start = time.time()
    try:
        with urllib.request.urlopen(req) as resp:
            status = resp.status
            total_content_len = resp.headers.get("Content-Length")
            print(f"Respuesta HTTP {status} (Content-Length: {total_content_len})")

            mode = "ab" if (existing_bytes > 0 and status == 206) else "wb"
            if mode == "wb":
                existing_bytes = 0

            downloaded = existing_bytes
            total_size = EXPECTED_BYTES

            last_report = time.time()
            bytes_since_report = 0

            with open(PART_FILE, mode) as f:
                while True:
                    chunk = resp.read(1024 * 1024)  # 1 MB
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    bytes_since_report += len(chunk)

                    now = time.time()
                    if now - last_report >= 5.0 or downloaded == total_size:
                        dt = now - last_report
                        speed_mb = (bytes_since_report / 1024 / 1024) / dt if dt > 0 else 0
                        pct = (downloaded / total_size) * 100
                        remaining_bytes = max(0, total_size - downloaded)
                        eta_sec = (remaining_bytes / (bytes_since_report / dt)) if bytes_since_report > 0 and dt > 0 else 0
                        eta_min = eta_sec / 60
                        print(f"[{pct:5.1f}%] {downloaded/1024/1024:7.1f} / {total_size/1024/1024:.1f} MB | {speed_mb:5.2f} MB/s | ETA: {eta_min:4.1f} min")
                        last_report = now
                        bytes_since_report = 0

    except Exception as e:
        print(f"Error durante la descarga: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Descarga finalizada en {(time.time() - t_start)/60:.1f} min. Verificando SHA-256...")
    if verify_sha256(PART_FILE, EXPECTED_SHA256):
        if TARGET_FILE.exists():
            TARGET_FILE.unlink()
        PART_FILE.rename(TARGET_FILE)
        print(f"Instalación exitosa en: {TARGET_FILE}")
    else:
        print("La verificación falló. El archivo .part no se renombrará.")
        sys.exit(2)


if __name__ == "__main__":
    download()
