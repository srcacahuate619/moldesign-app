"""Dictado con whisper.cpp: tasa de error por palabra, término clave y latencia en CPU.

Usa `whisper-server` con el modelo cargado una vez, como lo usaría el producto
(el mismo patrón que `llama-server`), y le manda cada WAV del guion.

Uso:
  WHISPER_SERVER=...\\whisper-server.exe MODELO=...\\ggml-small-q5_1.bin AUDIO=dir_wav \
  SALIDA=res.json [PROMPT=1] [HILOS=8] python run_whisper.py
"""
import json
import os
import re
import subprocess
import sys
import time
import unicodedata
from pathlib import Path

import httpx

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
from guion import FRASES, PROMPT_VOCABULARIO  # noqa: E402

SERVIDOR = os.environ["WHISPER_SERVER"]
MODELO = os.environ["MODELO"]
AUDIO = Path(os.environ["AUDIO"])
SALIDA = os.environ["SALIDA"]
CON_PROMPT = os.environ.get("PROMPT") == "1"
HILOS = os.environ.get("HILOS", "8")
PUERTO = os.environ.get("PUERTO", "8431")


def normalizar(texto: str) -> list[str]:
    """Minúsculas, sin puntuación ni guiones; las tildes se conservan (en español cambian la palabra)."""
    texto = unicodedata.normalize("NFC", texto.lower())
    texto = texto.replace("-", "")
    texto = re.sub(r"[^\w\sáéíóúüñ]", " ", texto)
    return texto.split()


def distancia(a: list[str], b: list[str]) -> int:
    fila = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        previa, fila[0] = fila[0], i
        for j, y in enumerate(b, 1):
            previa, fila[j] = fila[j], min(fila[j] + 1, fila[j - 1] + 1, previa + (x != y))
    return fila[-1]


def main() -> int:
    args = [SERVIDOR, "-m", MODELO, "--port", PUERTO, "-l", "es", "-t", HILOS]
    if CON_PROMPT:
        args += ["--prompt", PROMPT_VOCABULARIO]
    t0 = time.perf_counter()
    proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{PUERTO}"
    filas = []
    try:
        with httpx.Client(timeout=httpx.Timeout(600.0, connect=1.0)) as cli:
            for _ in range(600):
                try:
                    if cli.get(url).status_code < 500:
                        break
                except httpx.HTTPError:
                    time.sleep(0.25)
            carga_s = time.perf_counter() - t0
            for fid, frase, clave in FRASES:
                wav = AUDIO / f"{fid}.wav"
                t1 = time.perf_counter()
                with open(wav, "rb") as f:
                    r = cli.post(f"{url}/inference", files={"file": (wav.name, f, "audio/wav")},
                                 data={"response_format": "json", "language": "es", "temperature": "0"})
                r.raise_for_status()
                texto = r.json().get("text", "").strip()
                ms = (time.perf_counter() - t1) * 1000
                ref, hip = normalizar(frase), normalizar(texto)
                errores = distancia(ref, hip)
                clave_ok = " ".join(normalizar(clave)) in " ".join(hip)
                filas.append({"id": fid, "referencia": frase, "transcripcion": texto, "palabras": len(ref),
                              "errores": errores, "clave": clave, "clave_ok": clave_ok, "ms": round(ms)})
                print(f"{'OK' if clave_ok else 'XX'} {fid} [{ms:5.0f} ms] err={errores}/{len(ref)}  {texto}", flush=True)
    finally:
        proc.terminate()
        proc.wait(timeout=10)
    total = sum(f["palabras"] for f in filas)
    wer = sum(f["errores"] for f in filas) / total
    claves = sum(f["clave_ok"] for f in filas)
    ms = sorted(f["ms"] for f in filas)
    resumen = {"modelo": Path(MODELO).name, "prompt": CON_PROMPT, "hilos": HILOS, "carga_s": round(carga_s, 1),
               "wer": round(wer, 4), "claves_ok": claves, "n": len(filas), "ms_p50": ms[len(ms) // 2], "ms_max": ms[-1]}
    print(json.dumps(resumen, ensure_ascii=False))
    json.dump({"resumen": resumen, "filas": filas}, open(SALIDA, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
