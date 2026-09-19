#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""servidor_inventario.py — qué bloques de validación puede hospedar esta máquina.

Por qué existe
--------------
`backend/audits/VALIDACION_EN_SERVIDOR.md` cierra con cuatro cosas que hay que
saber antes de concretar el plan de 24 h: núcleos y RAM, si es Linux nativo, si
hay GPU CUDA y cuánto disco libre queda. Preguntarlas por chat da una respuesta
de memoria; ejecutar esto en el servidor da una medida.

El script **no ejecuta ningún experimento y no escribe nada fuera de su salida**.
Sólo mide la máquina y dice, bloque por bloque, qué puede hospedar y qué no, con
el motivo. Se puede correr con cualquier Python 3.9+ y sólo biblioteca estándar:
el servidor no tiene por qué tener el entorno del proyecto montado todavía.

Uso
---
    python3 scripts/servidor_inventario.py
    python3 scripts/servidor_inventario.py --json inventario.json
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

#: Lo que cada bloque necesita de la máquina. La columna que importa es la
#: última: por qué se queda fuera, para que nadie lo dé por descartado sin
#: motivo escrito.
BLOQUES = {
    "1-piloto-ens05": {
        "titulo": "Piloto técnico del arreglo ENS-05 (2-3 h)",
        "necesita": ["vina", "python_proyecto"],
        "nota": "Se corre igual de bien en la estación de trabajo; no necesita servidor.",
    },
    "2-determinismo-vina": {
        "titulo": "Determinismo de Vina con vina_cpu=0 (30 min)",
        "necesita": ["vina"],
        "nota": "Barato. Su valor está en repetirlo en OTRA máquina con otro número de núcleos.",
    },
    "3-ens-prod-01": {
        "titulo": "ENS-PROD-01, 248 complejos (~2 días a exh=32)",
        "necesita": ["vina", "python_proyecto", "cpu>=8", "disco>=200GB", "dedicada"],
        "nota": "Una corrida prerregistrada NO comparte máquina. La contención ya tiró un dock de 970.",
    },
    "4-mmgbsa-dominio": {
        "titulo": "MM-GBSA puerta 1: ampliar halógenos (2-3 CPU-h)",
        "necesita": ["linux_nativo", "ambertools"],
        "nota": "La adjudicación del cloro ya está hecha sin AmberTools. Lo que falta es F, Br, I y curar ~50 ligandos.",
    },
    "5-clon-limpio": {
        "titulo": "Batería completa sobre clon limpio, cada noche",
        "necesita": ["git", "no_es_la_maquina_de_build"],
        "nota": "La mejor relación valor/hora y la única permanente. En Linux corre el backend; los catorce gates del instalador son de Windows.",
    },
    "6-mmgbsa-puerta-3": {
        "titulo": "MM-GBSA puerta 3: sistemas completos",
        "necesita": ["gpu_cuda"],
        "nota": "En CPU son 10-30 min por pose: un piloto de 50 se va a ~25 h. Sin CUDA, espera.",
    },
    "7-huecos": {
        "titulo": "Stacking M4 y re-auditoría FEP-01/02/03",
        "necesita": ["python_proyecto"],
        "nota": "Cómputo barato; el trabajo es de datos. Cabe en cualquier hueco.",
    },
}


def _ejecutar(cmd: list[str]) -> str | None:
    try:
        proceso = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    except Exception:                                              # noqa: BLE001
        return None
    if proceso.returncode != 0:
        return None
    return (proceso.stdout or "").strip() or None


def _ram_mb() -> int | None:
    try:
        if hasattr(os, "sysconf") and "SC_PAGE_SIZE" in os.sysconf_names:
            return (os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")) // (1024 ** 2)
    except Exception:                                              # noqa: BLE001
        pass
    if os.name == "nt":
        # `wmic` ya no viene en Windows 11, así que se pregunta a la API, igual
        # que hace `experiment_manifest.py`. Sigue siendo biblioteca estándar.
        try:
            import ctypes

            class _Estado(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong),
                            ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong),
                            ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong),
                            ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong),
                            ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

            estado = _Estado()
            estado.dwLength = ctypes.sizeof(_Estado)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(estado)):
                return int(estado.ullTotalPhys) // (1024 ** 2)
        except Exception:                                          # noqa: BLE001
            pass
    salida = _ejecutar(["wmic", "computersystem", "get", "TotalPhysicalSize"])
    if salida:
        for linea in salida.splitlines():
            if linea.strip().isdigit():
                return int(linea.strip()) // (1024 ** 2)
    return None


def _vina(raiz: Path) -> str | None:
    """Vina puede no estar en el PATH: en este repositorio vive en `tools/`.

    Buscar sólo en el PATH habría contestado «no hay Vina» en la misma máquina
    que lo trae empaquetado.
    """
    for candidato in (raiz / "tools" / "vina" / "vina.exe",
                      raiz / "tools" / "vina" / "vina"):
        if candidato.exists():
            return str(candidato)
    return shutil.which("vina") or shutil.which("vina.exe")


def _es_wsl() -> bool:
    """WSL no es Linux nativo para lo que pide el bloque 4.

    No es purismo: el rendimiento de E/S y la disponibilidad de AmberTools
    difieren, y el plan lo distingue explícitamente.
    """
    if platform.system() != "Linux":
        return False
    if "microsoft" in platform.release().lower():
        return True
    try:
        return "microsoft" in Path("/proc/version").read_text(errors="replace").lower()
    except Exception:                                              # noqa: BLE001
        return False


def _gpu() -> dict:
    salida = _ejecutar(["nvidia-smi",
                        "--query-gpu=name,memory.total,driver_version",
                        "--format=csv,noheader"])
    if not salida:
        return {"cuda": False, "detalle": "nvidia-smi no responde o no está"}
    tarjetas = [l.strip() for l in salida.splitlines() if l.strip()]
    return {"cuda": bool(tarjetas), "tarjetas": tarjetas}


def _carga() -> dict:
    """Lo que la máquina está haciendo AHORA.

    El bloque 3 pide una máquina en reposo y comprobarlo antes de lanzar. Un
    número aquí no sustituye esa comprobación, pero la hace visible.
    """
    datos: dict = {}
    try:
        datos["load_average_1_5_15"] = [round(v, 2) for v in os.getloadavg()]
    except (AttributeError, OSError):
        datos["load_average_1_5_15"] = None
    return datos


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", default=None, help="además, escribe el inventario aquí")
    ap.add_argument("--raiz", default=".", help="raíz del proyecto, para medir el disco")
    args = ap.parse_args()

    raiz = Path(args.raiz).resolve()
    uso = shutil.disk_usage(raiz if raiz.exists() else Path.home())
    gpu = _gpu()
    nucleos = os.cpu_count() or 0
    ram = _ram_mb()

    hechos = {
        "medido_utc": datetime.now(timezone.utc).isoformat(),
        "hostname": platform.node(),
        "sistema": platform.platform(),
        "es_linux_nativo": platform.system() == "Linux" and not _es_wsl(),
        "es_wsl": _es_wsl(),
        "nucleos_logicos": nucleos,
        "ram_mb": ram,
        "disco_libre_gb": round(uso.free / 1024 ** 3, 1),
        "disco_total_gb": round(uso.total / 1024 ** 3, 1),
        "gpu": gpu,
        "carga": _carga(),
        "herramientas": {
            "git": shutil.which("git"),
            "python3": sys.executable,
            "version_python": platform.python_version(),
            "vina": _vina(raiz),
            "ambertools_sander": shutil.which("sander"),
            "obabel": shutil.which("obabel"),
            "nvcc": shutil.which("nvcc"),
        },
    }

    capacidades = {
        "vina": bool(hechos["herramientas"]["vina"]),
        "git": bool(hechos["herramientas"]["git"]),
        "gpu_cuda": bool(gpu.get("cuda")),
        "linux_nativo": hechos["es_linux_nativo"],
        "ambertools": bool(hechos["herramientas"]["ambertools_sander"]),
        "cpu>=8": nucleos >= 8,
        "disco>=200GB": hechos["disco_libre_gb"] >= 200,
        # Estas dos no las puede medir el script: dependen de una decisión.
        "python_proyecto": None,
        "dedicada": None,
        "no_es_la_maquina_de_build": None,
    }

    veredicto = {}
    for clave, bloque in BLOQUES.items():
        faltan = [r for r in bloque["necesita"] if capacidades.get(r) is False]
        indecisos = [r for r in bloque["necesita"] if capacidades.get(r) is None]
        veredicto[clave] = {
            "titulo": bloque["titulo"],
            "puede": not faltan,
            "faltan": faltan,
            "no_lo_decide_esta_maquina": indecisos,
            "nota": bloque["nota"],
        }

    informe = {"hechos": hechos, "capacidades": capacidades, "bloques": veredicto}

    print(f"== {hechos['hostname']} ==")
    print(f"  {hechos['sistema']}")
    print(f"  {nucleos} núcleos lógicos, "
          f"{f'{ram / 1024:.1f} GiB' if ram else 'RAM desconocida'} de RAM")
    print(f"  Linux nativo: {hechos['es_linux_nativo']}"
          f"{'  (es WSL)' if hechos['es_wsl'] else ''}")
    print(f"  disco libre: {hechos['disco_libre_gb']} GB de {hechos['disco_total_gb']} GB")
    print(f"  GPU CUDA: {gpu.get('cuda')}"
          + (f" — {', '.join(gpu.get('tarjetas', []))}" if gpu.get("cuda") else ""))
    print(f"  carga: {hechos['carga']['load_average_1_5_15']}")
    print("\n== Bloques ==")
    for clave, datos in veredicto.items():
        marca = "sí " if datos["puede"] else "NO "
        print(f"  [{marca}] {clave}: {datos['titulo']}")
        if datos["faltan"]:
            print(f"        falta: {', '.join(datos['faltan'])}")
        if datos["no_lo_decide_esta_maquina"]:
            print(f"        decisión, no medida: "
                  f"{', '.join(datos['no_lo_decide_esta_maquina'])}")

    print("\nLo que este inventario NO resuelve: la cohorte de ENS-PROD-01, el "
          "umbral de relevancia práctica, la decisión de dominio sobre halógenos "
          "ni las licencias. Y una máquina capaz no es una máquina dedicada.")

    if args.json:
        Path(args.json).write_text(
            json.dumps(informe, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"\nEscrito: {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
