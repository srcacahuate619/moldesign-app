#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""run_vinadet01_determinismo.py — VINA-DET-01: ¿es reproducible una corrida de Vina?

La pregunta
-----------
El producto promete un «paquete estructural reproducible». Esa promesa apoya en
un supuesto que nunca se midió: que Vina, con la MISMA entrada y la MISMA
semilla, produce la MISMA salida.

El supuesto es dudoso por construcción. `core/config.py:108` declara
`vina_cpu: int = Field(default=0)` — auto-detección de núcleos — y
`vina_service.py:576` lo pasa tal cual a `--cpu`. La búsqueda de Vina reparte el
trabajo entre hilos; si el reparto depende del orden de finalización, la semilla
no basta para fijar el resultado.

Quedó anotado explícitamente como NO medido en `ENSEMBLE_REVIEW.md`, §«El
ensemble acoplaba la misma geometría K veces»:

    «Con la misma entrada, semilla y caja cabría esperarlo, pero `vina_cpu` vale
    0 por defecto y la búsqueda paralela de Vina no garantiza reproducibilidad
    bit a bit. No se comprobó, y por tanto no se afirma.»

Este script lo comprueba.

El diseño
---------
Seis celdas: exhaustividad ∈ {8, 32} × `--cpu` ∈ {0, 1, 12}. Diez repeticiones
por celda, todas con semilla 42, la misma caja, el mismo receptor y el mismo
ligando ya preparados.

  * `--cpu 0` es lo que ejecuta el producto hoy. Es la celda primaria.
  * `--cpu 1` es la condición de las corridas selladas (`MF-33`, `REC-07`), y la
    única en la que cabría esperar determinismo por construcción.
  * `--cpu 12` fija explícitamente el número de núcleos de esta máquina: separa
    «paralelo» de «auto-detectado», que no son la misma condición aunque aquí
    resuelvan al mismo número.

  * exh=32 es lo que ejecuta el producto (`runner.py:696`).
  * exh=8 es lo que corrió la evidencia sellada del ensemble (`MF-33-B-RET-R2`).

Lo que produce y lo que no
--------------------------
**Produce** un hecho en cualquier dirección: o los bytes coinciden, o no. Si no
coinciden, la promesa de «paquete reproducible» necesita una condición escrita
—igual que la validez física necesita la suya de reconstrucción de hidrógenos
(`MF-33-H-COR`)—, y este artefacto es la medida que la sostiene.

**No demuestra** que las poses sean buenas, ni que una condición sea mejor que
otra. Dos salidas idénticas no son dos salidas correctas. Y un resultado de
determinismo obtenido con UN ligando sobre UN receptor no se generaliza a todos:
lo que se afirma es lo que se midió.

Condición de la máquina
-----------------------
La celda de `--cpu 0` y la de `--cpu 12` piden los doce hilos. Se ejecutan en
serie y se registra la carga declarada en el manifiesto: una medida de
determinismo bajo contención no es la misma medida. Ver la lección de
`MF-33-B-RET-R1`, donde compartir máquina tiró un dock de 970 complejos.

Uso
---
    python scripts/run_vinadet01_determinismo.py --salida scripts/artifacts_science/VINA-DET-01
    python scripts/run_vinadet01_determinismo.py --reanudar   # continúa donde quedó
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from statistics import median

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ── Congelado antes de correr ────────────────────────────────────────────────
SEMILLA = 42
NUM_MODES = 9
REPETICIONES = 10
EXHAUSTIVIDADES = (8, 32)
CPUS = (0, 1, 12)

# Caja G_ADAPT de REC-07: la mínima que contiene los 15 hotspots más la tríada,
# con 4.0 Å de padding. No se re-deriva aquí; se cita de su preregistro.
CENTRO = (11.104, 135.221, 21.288)
TAMANO = (19.0, 25.3, 25.9)

# Entradas ya preparadas. Se COPIAN al directorio de trabajo con su hash: el
# origen está sellado y no se toca.
ORIGEN_RECEPTOR = PROJECT_ROOT / "scripts/artifacts_science/REC-07/_work/5TUN_receptor.pdbqt"
ORIGEN_LIGANDO = PROJECT_ROOT / "scripts/artifacts_science/REC-07/_work/E6C.pdbqt"

RE_AFINIDAD = re.compile(r"^REMARK VINA RESULT:\s+(-?\d+\.\d+)", re.MULTILINE)


def _sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with ruta.open("rb") as fh:
        for bloque in iter(lambda: fh.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def _version_de_vina(binario: Path) -> str:
    try:
        proceso = subprocess.run([str(binario), "--version"], capture_output=True,
                                 text=True, timeout=30)
        return (proceso.stdout or proceso.stderr).strip().splitlines()[0]
    except Exception as exc:                                       # noqa: BLE001
        return f"desconocida ({type(exc).__name__})"


def _corrida(binario: Path, receptor: Path, ligando: Path, salida: Path,
             exh: int, cpu: int) -> dict:
    """Una corrida de Vina. Devuelve la fila cruda, sin interpretarla."""
    cmd = [str(binario),
           "--receptor", str(receptor), "--ligand", str(ligando),
           "--center_x", str(CENTRO[0]), "--center_y", str(CENTRO[1]),
           "--center_z", str(CENTRO[2]),
           "--size_x", str(TAMANO[0]), "--size_y", str(TAMANO[1]),
           "--size_z", str(TAMANO[2]),
           "--exhaustiveness", str(exh), "--num_modes", str(NUM_MODES),
           "--seed", str(SEMILLA), "--cpu", str(cpu),
           "--out", str(salida)]
    t0 = time.time()
    proceso = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    wall = round(time.time() - t0, 2)

    fila: dict = {"exh": exh, "cpu": cpu, "rc": proceso.returncode, "wall_s": wall}
    if proceso.returncode != 0 or not salida.exists():
        fila["error"] = (proceso.stderr or proceso.stdout)[-400:]
        return fila

    bytes_salida = salida.read_bytes()
    texto = bytes_salida.decode("utf-8", errors="replace")
    fila["sha256_pdbqt"] = hashlib.sha256(bytes_salida).hexdigest()
    fila["bytes_pdbqt"] = len(bytes_salida)
    fila["afinidades"] = [float(x) for x in RE_AFINIDAD.findall(texto)]
    fila["n_modos"] = len(fila["afinidades"])
    return fila


def _resumen_de_celda(filas: list[dict]) -> dict:
    """Lo que la celda permite afirmar, y nada más."""
    buenas = [f for f in filas if f.get("rc") == 0 and f.get("sha256_pdbqt")]
    hashes = {f["sha256_pdbqt"] for f in buenas}
    vectores = {tuple(f["afinidades"]) for f in buenas}
    top1 = [f["afinidades"][0] for f in buenas if f["afinidades"]]

    return {
        "corridas": len(filas),
        "corridas_validas": len(buenas),
        "hashes_distintos": len(hashes),
        "identico_byte_a_byte": len(hashes) == 1 and len(buenas) == len(filas),
        "vectores_de_afinidad_distintos": len(vectores),
        "afinidad_top1_min": min(top1) if top1 else None,
        "afinidad_top1_max": max(top1) if top1 else None,
        "rango_top1_kcal": round(max(top1) - min(top1), 4) if top1 else None,
        "wall_s_mediana": round(median([f["wall_s"] for f in buenas]), 2) if buenas else None,
        "wall_s_total": round(sum(f["wall_s"] for f in filas), 1),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--salida", default=str(PROJECT_ROOT / "scripts/artifacts_science/VINA-DET-01"))
    ap.add_argument("--vina", default=str(PROJECT_ROOT / "tools/vina/vina.exe"))
    ap.add_argument("--repeticiones", type=int, default=REPETICIONES)
    ap.add_argument("--reanudar", action="store_true",
                    help="continúa una corrida interrumpida sin repetir lo hecho")
    args = ap.parse_args()

    binario = Path(args.vina)
    if not binario.exists():
        print(f"No existe el binario de Vina: {binario}", file=sys.stderr)
        return 2
    for origen in (ORIGEN_RECEPTOR, ORIGEN_LIGANDO):
        if not origen.exists():
            print(f"Falta la entrada preparada: {origen}", file=sys.stderr)
            return 2

    destino = Path(args.salida)
    trabajo = destino / "_work"
    trabajo.mkdir(parents=True, exist_ok=True)
    jsonl = destino / "per_complex.jsonl"

    if jsonl.exists() and jsonl.stat().st_size > 0 and not args.reanudar:
        print(f"Ya hay resultados en {jsonl}. Usa --reanudar, o escribe en otro "
              f"directorio: reusar el de salida ya destruyó 102 resultados de "
              f"RS-03-PARAM-B.", file=sys.stderr)
        return 2

    receptor = trabajo / "receptor.pdbqt"
    ligando = trabajo / "ligando.pdbqt"
    if not receptor.exists():
        shutil.copy2(ORIGEN_RECEPTOR, receptor)
    if not ligando.exists():
        shutil.copy2(ORIGEN_LIGANDO, ligando)

    hechas: set[tuple[int, int, int]] = set()
    if args.reanudar and jsonl.exists():
        for linea in jsonl.read_text(encoding="utf-8").splitlines():
            if linea.strip():
                f = json.loads(linea)
                hechas.add((f["exh"], f["cpu"], f["repeticion"]))
        print(f"Reanudando: {len(hechas)} corridas ya registradas.")

    entorno = {
        "vina_binario": str(binario),
        "vina_sha256": _sha256(binario),
        "vina_version": _version_de_vina(binario),
        "receptor_sha256": _sha256(receptor),
        "receptor_origen": str(ORIGEN_RECEPTOR.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "ligando_sha256": _sha256(ligando),
        "ligando_origen": str(ORIGEN_LIGANDO.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "plataforma": platform.platform(),
        "procesador": platform.processor(),
        "nucleos_logicos": __import__("os").cpu_count(),
        "semilla": SEMILLA,
        "num_modes": NUM_MODES,
        "centro": list(CENTRO),
        "tamano": list(TAMANO),
        "inicio_utc": datetime.now(UTC).isoformat(),
    }
    (destino / "entorno.json").write_text(
        json.dumps(entorno, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(entorno, ensure_ascii=False, indent=2))

    total = len(EXHAUSTIVIDADES) * len(CPUS) * args.repeticiones
    hecho = 0
    with jsonl.open("a", encoding="utf-8") as registro:
        for exh in EXHAUSTIVIDADES:
            for cpu in CPUS:
                for rep in range(1, args.repeticiones + 1):
                    hecho += 1
                    if (exh, cpu, rep) in hechas:
                        continue
                    salida_pdbqt = trabajo / f"out_exh{exh}_cpu{cpu}_r{rep}.pdbqt"
                    fila = _corrida(binario, receptor, ligando, salida_pdbqt, exh, cpu)
                    fila["repeticion"] = rep
                    fila["salida"] = salida_pdbqt.name
                    # Se escribe al momento: una corrida larga que muere sin
                    # checkpoint es una corrida que hay que repetir entera.
                    registro.write(json.dumps(fila, ensure_ascii=False, sort_keys=True) + "\n")
                    registro.flush()
                    print(f"[{hecho}/{total}] exh={exh} cpu={cpu} r={rep} "
                          f"rc={fila['rc']} {fila['wall_s']}s "
                          f"top1={fila.get('afinidades', [None])[0]} "
                          f"sha={str(fila.get('sha256_pdbqt'))[:12]}", flush=True)

    filas = [json.loads(l) for l in jsonl.read_text(encoding="utf-8").splitlines() if l.strip()]
    celdas: dict[str, dict] = {}
    for exh in EXHAUSTIVIDADES:
        for cpu in CPUS:
            clave = f"exh{exh}_cpu{cpu}"
            celdas[clave] = _resumen_de_celda(
                [f for f in filas if f["exh"] == exh and f["cpu"] == cpu])

    metricas = {
        "experimento": "VINA-DET-01",
        "pregunta": "¿Produce Vina la misma salida con la misma entrada y semilla?",
        "fin_utc": datetime.now(UTC).isoformat(),
        "entorno": entorno,
        "celdas": celdas,
        "lectura": {
            "celda_del_producto": "exh32_cpu0",
            "celda_de_la_evidencia_sellada": "exh8_cpu1",
            "no_demuestra": (
                "Que las poses sean correctas, ni que una condición sea mejor. "
                "Un ligando sobre un receptor: lo medido no se generaliza solo."
            ),
        },
    }
    (destino / "metrics.json").write_text(
        json.dumps(metricas, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("\n== Resumen ==")
    for clave, resumen in celdas.items():
        print(f"{clave:14s} hashes_distintos={resumen['hashes_distintos']} "
              f"identico={resumen['identico_byte_a_byte']} "
              f"vectores={resumen['vectores_de_afinidad_distintos']} "
              f"rango_top1={resumen['rango_top1_kcal']} "
              f"mediana={resumen['wall_s_mediana']}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
