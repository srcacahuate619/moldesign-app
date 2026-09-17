"""Ejecuta MM-GBSA fuera del servidor, con cancelación y plazo reales."""
from __future__ import annotations

import asyncio
import json
import math
import sys
from pathlib import Path

from utils.procesos import BANDERAS_SIN_VENTANA, communicate_managed


async def run_mmgbsa_pose_subprocess(
    protein_pdb: str, smiles: str, pose_sdf: str, *, max_iter: int, timeout: float = 300.0,
) -> dict:
    process = await asyncio.create_subprocess_exec(
        sys.executable, str(Path(__file__).with_name("mmgbsa_subprocess.py")),
        protein_pdb, smiles, str(max_iter), "--poses", pose_sdf,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        creationflags=BANDERAS_SIN_VENTANA,
    )
    stdout, stderr = await communicate_managed(process, timeout=timeout)
    try:
        result = json.loads(stdout.decode("utf-8"))
        if not isinstance(result, dict):
            raise ValueError("MM-GBSA devolvió un resultado que no es un objeto")
    except (ValueError, UnicodeError) as exc:
        raise RuntimeError(
            f"Respuesta inválida de MM-GBSA (exit={process.returncode}): "
            + stderr.decode("utf-8", "replace")[-1000:]
        ) from exc
    if process.returncode:
        raise RuntimeError(result.get("error") or f"MM-GBSA terminó con exit={process.returncode}")
    score = result.get("mmgbsa")
    if score is not None and (not isinstance(score, (int, float)) or not math.isfinite(score)):
        raise RuntimeError("MM-GBSA devolvió una energía no finita o inválida")
    return result
