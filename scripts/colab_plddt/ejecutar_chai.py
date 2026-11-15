"""Corre Chai-1 sobre un FASTA y guarda, además de sus archivos, los tensores que devuelve ``run_inference``.

Se ejecuta DENTRO del entorno virtual de Chai-1 (``/content/venvs/chai/bin/python``), no en el del cuaderno: así sus
dependencias no chocan con las de Boltz. El tensor ``plddt`` que se guarda en ``salida_del_modelo.npz`` es la
referencia contra la que ``analisis_plddt.py`` compara el factor B del CIF.

Sólo pasa a ``run_inference`` los argumentos que la versión instalada acepta y deja escrito cuáles omitió: el registro
no puede decir que se pidió algo que la función no recibió.
"""

from __future__ import annotations

import argparse
import dataclasses
import inspect
import json
import sys
import time
from importlib import metadata
from pathlib import Path


def _serializable(valor, profundidad: int = 0):
    import numpy as np
    import torch

    if profundidad > 6:
        return repr(valor)[:200]
    if torch.is_tensor(valor):
        valor = valor.detach().float().cpu().numpy()
    if isinstance(valor, np.ndarray):
        return valor.round(6).tolist() if valor.size <= 2000 else {"forma": list(valor.shape)}
    if isinstance(valor, (np.floating, np.integer)):
        return valor.item()
    if isinstance(valor, Path):
        return str(valor)
    if dataclasses.is_dataclass(valor) and not isinstance(valor, type):
        return {f.name: _serializable(getattr(valor, f.name), profundidad + 1) for f in dataclasses.fields(valor)}
    if isinstance(valor, dict):
        return {str(k): _serializable(v, profundidad + 1) for k, v in valor.items()}
    if isinstance(valor, (list, tuple)):
        return [_serializable(v, profundidad + 1) for v in valor]
    if isinstance(valor, (str, int, float, bool)) or valor is None:
        return valor
    return repr(valor)[:200]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fasta", required=True)
    parser.add_argument("--salida", required=True, help="directorio nuevo y vacío")
    parser.add_argument("--semilla", type=int, default=42)
    parser.add_argument("--msa-servidor", type=int, choices=(0, 1), default=1)
    parser.add_argument("--muestras", type=int, default=5)
    args = parser.parse_args()

    import numpy as np
    import torch
    from chai_lab.chai1 import run_inference

    salida = Path(args.salida)
    salida.mkdir(parents=True, exist_ok=False)
    resumen: dict = {
        "chai_lab": metadata.version("chai_lab"), "torch": torch.__version__, "cuda": torch.version.cuda,
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "bf16": bool(torch.cuda.is_available() and torch.cuda.is_bf16_supported()),
        "python": sys.version.split()[0],
    }
    firma = inspect.signature(run_inference).parameters
    deseados = {
        "fasta_file": Path(args.fasta), "output_dir": salida, "num_trunk_recycles": 3,
        "num_diffn_timesteps": 200, "num_diffn_samples": args.muestras, "seed": args.semilla,
        "device": "cuda:0", "use_esm_embeddings": True, "use_msa_server": bool(args.msa_servidor),
    }
    kwargs = {k: v for k, v in deseados.items() if k in firma}
    resumen["argumentos_pasados"] = {k: str(v) for k, v in kwargs.items()}
    resumen["argumentos_no_aceptados_por_esta_version"] = sorted(set(deseados) - set(kwargs))
    resumen["firma_de_run_inference"] = [str(p) for p in firma.values()]
    if args.msa_servidor and "use_msa_server" not in firma:
        resumen["error"] = "esta versión de chai_lab no acepta use_msa_server: no se corre sin decirlo"
        (salida / "resumen_chai.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")
        return 2

    t0 = time.time()
    try:
        candidatos = run_inference(**kwargs)
    except Exception as exc:  # se registra (memoria, bf16…) y el cuaderno lo cuenta como «no terminó»
        resumen["segundos"] = round(time.time() - t0, 1)
        resumen["error"] = f"{type(exc).__name__}: {str(exc)[:2000]}"
        (salida / "resumen_chai.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")
        raise
    resumen["segundos"] = round(time.time() - t0, 1)

    tensores, otros = {}, {}
    campos = ([f.name for f in dataclasses.fields(candidatos)] if dataclasses.is_dataclass(candidatos)
              else [n for n in vars(candidatos)])
    for nombre in campos:
        valor = getattr(candidatos, nombre)
        if torch.is_tensor(valor):
            tensores[nombre] = valor.detach().float().cpu().numpy()
        else:
            otros[nombre] = _serializable(valor)
    np.savez_compressed(salida / "salida_del_modelo.npz", **tensores)
    resumen["tensores"] = {k: list(v.shape) for k, v in tensores.items()}
    resumen["cif_paths"] = [str(p) for p in getattr(candidatos, "cif_paths", [])]
    resumen["otros_campos"] = otros
    (salida / "resumen_chai.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: resumen[k] for k in ("chai_lab", "gpu", "bf16", "segundos", "tensores")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
