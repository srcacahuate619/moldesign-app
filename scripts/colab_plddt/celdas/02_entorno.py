# ── Entorno: GPU, Drive y registro de procedencia ──
import datetime as dt
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path("/content/plddt_boltz_chai")
RES = RAIZ / "resultados"
CACHE = Path("/content/cache")
VENVS = Path("/content/venvs")
DRIVE = Path("/content/drive/MyDrive/moldesign_plddt_boltz_chai/resultados")
for d in (RAIZ, RES, CACHE, VENVS):
    d.mkdir(parents=True, exist_ok=True)


def ahora():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def sello():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


#: Los entornos virtuales no heredan lo que Colab pone para su propio Python: PYTHONPATH mezclaría sus paquetes, y
#: su MPLBACKEND (matplotlib_inline) no existe en ellos, así que cualquier gráfico de Chai-1 fallaría al importarse.
ENTORNO_LIMPIO = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME", "MPLBACKEND")}
ENTORNO_LIMPIO["MPLBACKEND"] = "Agg"


def sh(cmd, log=None, env=None, check=False):
    """Ejecuta y devuelve (resultado, segundos). Con ``log``, la salida va a ese archivo y no a la celda."""
    env = ENTORNO_LIMPIO if env is None else env
    t0 = time.time()
    if log:
        with open(log, "w", encoding="utf-8") as f:
            r = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, text=True, env=env)
    else:
        r = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if check and r.returncode != 0:
        detalle = (r.stdout or "") + (r.stderr or "") if not log else f"mira {log}"
        raise RuntimeError(f"falló {' '.join(map(str, cmd[:4]))}: {detalle[-3000:]}")
    return r, round(time.time() - t0, 1)


PROC_RUTA = RES / "procedencia.json"


def cargar_procedencia():
    return json.loads(PROC_RUTA.read_text(encoding="utf-8")) if PROC_RUTA.exists() else {}


def guardar_procedencia(**cambios):
    p = cargar_procedencia()
    p.update(cambios)
    PROC_RUTA.write_text(json.dumps(p, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def drive_montado():
    return GUARDAR_EN_DRIVE and Path("/content/drive/MyDrive").exists()


def respaldar():
    if drive_montado():
        shutil.copytree(RES, DRIVE, dirs_exist_ok=True)


def apartar(ruta, motivo="fallido"):
    """Aparta un resultado anterior renombrándolo con la fecha, aquí y en su copia de Drive. Nunca se borra nada."""
    ruta = Path(ruta)
    nuevo = ruta.with_name(f"{ruta.stem}__{motivo}_{sello()}{ruta.suffix}")
    if drive_montado():
        copia = DRIVE / ruta.relative_to(RES)
        if copia.exists():
            copia.rename(DRIVE / nuevo.relative_to(RES))
    ruta.rename(nuevo)
    return nuevo


CLAVES = {"boltz": [f"{c['id']}__{f}" for c in CASOS for f in FORMATOS_BOLTZ[c["id"]]],
          "chai": [f"{c['id']}__mmcif" for c in CASOS]}


def pendientes():
    """Las corridas que faltan, por herramienta. Una terminada (código 0 y su carpeta) no se repite."""
    p = cargar_procedencia()
    return {h: [k for k in claves
                if not (p.get(f"corridas_{h}", {}).get(k, {}).get("codigo") == 0 and (RES / h / k).exists())]
            for h, claves in CLAVES.items()}


CHAI_LISTO = None  # lo decide la celda de instalación tras sondear parquet en el entorno de Chai-1

if GUARDAR_EN_DRIVE:
    from google.colab import drive

    drive.mount("/content/drive")
    if DRIVE.exists() and not any(RES.iterdir()):
        shutil.copytree(DRIVE, RES, dirs_exist_ok=True)  # retoma lo ya hecho en una ejecución anterior
        print("Retomado desde Drive:", sorted(p.name for p in RES.iterdir()))

r, _ = sh(["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"])
if r.returncode != 0 or not r.stdout.strip():
    raise SystemExit("No hay GPU. Entorno de ejecución → Cambiar tipo de entorno de ejecución → L4, y vuelve a ejecutar.")
nombre_gpu, memoria_gpu, driver = [x.strip() for x in r.stdout.strip().splitlines()[0].split(",")]
import torch  # el torch del propio Colab, sólo para leer la capacidad de la GPU

CAPACIDAD = float("%d.%d" % torch.cuda.get_device_capability(0))
gpu = {"nombre": nombre_gpu, "memoria": memoria_gpu, "driver": driver, "compute_capability": CAPACIDAD}
if CAPACIDAD < 8.0:
    print("Aviso: esta GPU es anterior a Ampere. Chai-1 pide bf16 y probablemente falle; Boltz irá sin kernels.")
parametros = {"semilla": SEMILLA, "msa_servidor": USAR_SERVIDOR_MSA, "version_boltz": VERSION_BOLTZ or "última",
              "version_chai": VERSION_CHAI or "última", "muestras_chai": MUESTRAS_CHAI, "casos": CASOS,
              "formatos_boltz": FORMATOS_BOLTZ, "referencia_afdb": REFERENCIA_AFDB}
previa = cargar_procedencia()
ejecuciones = previa.get("ejecuciones", [])
if not ejecuciones and previa.get("inicio"):  # la primera ejecución no llevaba esta lista: se reconstruye su entrada
    ejecuciones.append({"inicio": previa["inicio"], "fin": previa.get("fin"), "gpu": previa.get("gpu"),
                        "parametros": previa.get("parametros")})
ejecuciones.append({"inicio": ahora(), "gpu": gpu, "parametros": parametros, "pendientes_al_empezar": pendientes()})
guardar_procedencia(gpu=gpu, inicio=previa.get("inicio") or ahora(), python_del_cuaderno=sys.version.split()[0],
                    plataforma=platform.platform(), parametros=parametros, ejecuciones=ejecuciones)
print(gpu)
print("Pendiente:", pendientes())
