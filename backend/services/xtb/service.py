"""
services/xtb/service.py  [ARCHIVED — 2026-08-03]

Capa de servicio async para GFN2-xTB (binario xtb.exe).
Procesa conformadores 3D para generar cargas parciales cuánticas (CM5/Mulliken).

═══════════════════════════════════════════════════════════════════
ESTADO REAL (verificado por auditoría 2026-08-03):
- El ÚNICO caller es services/docking/quantum_ad4_service.py:39,62-66
  — que a su vez está ARCHIVED con 0 callers. Por transitividad,
  este módulo está efectivamente muerto en runtime.
- La afirmación previa de "uso indirecto via scripts/compute_quantum_features.py"
  era FALSA: ese script tiene su PROPIO wrapper síncrono (subprocess.run
  a xtb.exe en compute_quantum_features.py:118-121) y NO importa este módulo.
- Existen DOS adapters a xtb.exe en el codebase:
    (a) este, async (XTBService, dataclass XTBResult, logging) — SIN callers
    (b) el sync dentro de compute_quantum_features.py — VIVO (6 callers)

VEREDICTO: código archivado, NO activo. Se conserva porque su interfaz
(async, XTBResult dataclass, XTBHOME/share auto-detect, OMP_NUM_THREADS)
es MÁS LIMPIA que el wrapper sync del script.

OPCIÓN FUTURA (si se quiere consolidar):
Hacer que compute_quantum_features.py importe esta XTBService en lugar
de su propio subprocess. Eso elimina la duplicación, unifica el manejo
de XTBHOME/share y deja UNA sola forma de invocar xtb.exe.
═══════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

from utils.procesos import BANDERAS_SIN_VENTANA, communicate_managed

import asyncio
import os
import shutil
import tempfile
from pathlib import Path
from dataclasses import dataclass

from utils.logger import get_logger

log = get_logger(__name__)

@dataclass
class XTBResult:
    success: bool
    charges: list[float] | None = None
    error: str | None = None
    execution_time_s: float | None = None

class XTBService:
    def __init__(self):
        # Find xTB binary: PATH first, then known locations
        self._xtb_cmd = shutil.which("xtb") or self._find_xtb_windows()
        self._xtb_home = None
        if self._xtb_cmd:
            # XTBHOME must point to directory containing bin/ and share/
            exe_dir = os.path.dirname(self._xtb_cmd)
            parent_dir = os.path.dirname(exe_dir)
            # If bin/ is inside the directory, use the parent (which has share/)
            if os.path.basename(exe_dir) == "bin":
                self._xtb_home = parent_dir
            else:
                # Look for share/xtb/ in the tree
                for level in [parent_dir, os.path.dirname(parent_dir)]:
                    if os.path.exists(os.path.join(level, "share", "xtb")):
                        self._xtb_home = level
                        break
                if not self._xtb_home:
                    self._xtb_home = parent_dir  # fallback
            os.environ["XTBHOME"] = self._xtb_home
            os.environ["OMP_NUM_THREADS"] = "3"  # 6 cores, use half

    def _find_xtb_windows(self) -> str | None:
        """Find xTB binary in Windows tool paths. Prefer bin/xtb.exe for proper share/ access."""
        candidates = [
            Path(__file__).resolve().parent.parent.parent.parent / "tools" / "xtb" / "xtb-6.7.1" / "bin" / "xtb.exe",
            Path(__file__).resolve().parent.parent.parent.parent / "tools" / "xtb" / "xtb.exe",
            # Aqui habia dos rutas absolutas a un directorio de una version
            # anterior del repositorio, que ya no existe. En otra maquina
            # apuntan a la nada -o peor, a lo que haya en ese disco-. Las
            # dos candidatas relativas de arriba son las que de verdad
            # resuelven una instalacion.
        ]
        for p in candidates:
            if p.exists():
                return str(p)
        return None

    @property
    def is_configured(self) -> bool:
        return self._xtb_cmd is not None

    async def generate_partial_charges(self, sdf_content: str, smiles_hash: str) -> XTBResult:
        """
        Calcula cargas GFN2-xTB para la molecula.
        Convierte SDF a XYZ internamente (xTB prefiere XYZ).
        """
        if not self.is_configured:
            return XTBResult(success=False, error="Binario 'xtb' no encontrado en el sistema.")

        import time
        start_time = time.monotonic()

        # `ignore_cleanup_errors`: en Windows no se puede borrar un archivo que
        # alguien tenga abierto, y aqui dentro corren procesos hijos -Meeko, Vina,
        # Open Babel- mas el antivirus escaneando lo recien escrito. Sin esto, la
        # limpieza puede levantar PermissionError DESPUES de que el trabajo haya
        # terminado bien, y tirar una corrida completa por no poder borrar un
        # temporal. Dejar un archivo suelto es mucho mejor que perder el resultado.
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
            tmp_path = Path(tmp_dir)

            # Convert SDF to XYZ (xTB works better with XYZ on Windows)
            try:
                from rdkit import Chem
                mol = Chem.MolFromMolBlock(sdf_content, removeHs=False, sanitize=False)
                if mol is None:
                    return XTBResult(success=False, error="Could not parse SDF")
            except Exception:
                return XTBResult(success=False, error="SDF parse failed")

            # Detect formal charge from RDKit molecule (sum of atom formal charges)
            formal_charge = sum(a.GetFormalCharge() for a in mol.GetAtoms())

            conf = mol.GetConformer()
            atoms = [a.GetSymbol() for a in mol.GetAtoms()]
            lines = [f"{atoms[i]} {conf.GetAtomPosition(i).x:.6f} {conf.GetAtomPosition(i).y:.6f} {conf.GetAtomPosition(i).z:.6f}"
                    for i in range(mol.GetNumAtoms())]
            xyz = f"{mol.GetNumAtoms()}\n\n" + "\n".join(lines)
            input_file = tmp_path / f"{smiles_hash}.xyz"
            input_file.write_text(xyz, encoding="ascii")

            # Single-point GFN2-xTB con solvente implícito ALPB (agua por defecto).
            # NOTA: --sp = single-point (sin geometry optimization).
            #       --alpb water = Born solvation analítica (aproxima GBSA).
            #       --chrg detectado del SDF (default 0 si no se puede determinar).
            # Para "production-graded" charges usar solvento explícito o COSMO-RS.
            command = [
                self._xtb_cmd, str(input_file),
                "--sp",                        # single-point energy
                "--gfn", "2",                   # GFN2-xTB tight-binding
                "--chrg", str(formal_charge),   # carga formal detectada del SDF
                "--alpb", "water",              # solvatación implícita (agua, ALPB)
            ]

            env = os.environ.copy()
            if self._xtb_home:
                env["XTBHOME"] = self._xtb_home
            env.setdefault("OMP_NUM_THREADS", "2")

            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=str(tmp_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                creationflags=BANDERAS_SIN_VENTANA,
                env=env,
            )
            stdout, stderr = await communicate_managed(process, timeout=600.0)

            if process.returncode != 0:
                log.warning("Fallo en xtb", error=stderr.decode() or stdout.decode())
                return XTBResult(success=False, error="xtb falló al procesar la molécula")

            # XTB genera un archivo llamado 'charges' en el directorio de trabajo
            charges_file = tmp_path / "charges"
            if not charges_file.exists():
                return XTBResult(success=False, error="xtb no generó el archivo de cargas")

            # Leer cargas
            charges_text = charges_file.read_text(encoding="utf-8")
            charges = [float(line.strip()) for line in charges_text.splitlines() if line.strip()]

            return XTBResult(
                success=True,
                charges=charges,
                execution_time_s=round(time.monotonic() - start_time, 2)
            )

_xtb_service: XTBService | None = None

def get_xtb_service() -> XTBService:
    global _xtb_service
    if _xtb_service is None:
        _xtb_service = XTBService()
    return _xtb_service
