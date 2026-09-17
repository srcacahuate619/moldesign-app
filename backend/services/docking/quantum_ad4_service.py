"""
services/docking/quantum_ad4_service.py  [ARCHIVED — 2026-08-03]

Implementación aislada del "Nivel 4" (GFN2-xTB + AutoDock 4).
Ejecuta docking sobre receptores con el campo de fuerzas de AD4,
usando cargas cuánticas ultra-precisas para organometálicos.

═══════════════════════════════════════════════════════════════════
ESTADO REAL (verificado por auditoría 2026-08-03):
- 0 callers en todo el repo. `run_quantum_ad4_docking` aparece SOLO
  en su propia definición. NINGÚN archivo lo importa.
- La afirmación previa de que "alimenta el stacking engine con
  quantum_score" era FALSA: el `quantum_score` que consume
  scoring/engine.py:295,348-362 SIEMPRE proviene de
  scripts/compute_quantum_features.py (vía queue_handler.py:995 y
  pipeline/runner.py:720), NUNCA de este módulo.
- El paper docs/PAPER_UMS.md NO contempla quantum docking como parte
  del framework UMS/M5 — al contrario, lo lista en §1.2 como
  "literature prior work, computationally prohibitive".
- Usa ``utils.local_storage.py`` (exists, read_text, write_text y
  temp_file) para materializar archivos en disco local.

VEREDICTO: código archivado, NO activo. Se conserva como referencia
histórica del prototipo "Nivel 4" y por si un paper/poster futuro
quiere reportarlo como módulo prototipado pero no desplegado.

SI SE REACTIVA ALGÚN DÍA (no recomendado para producción):
1. El storage ya resuelve a disco local (utils/local_storage.py, F-03).
2. Cablear el caller (hoy no existe): desde services/docking/vina_service
   como alternativa a run_vina_docking para targets metaloenzima.
3. Considerar si aporta vs el enfoque M5 del paper (SMARTS UMS).
   El paper sugiere que NO — la mejora real para metaloenzimas viene
   de portar scripts/universal_metal_score.py al runtime, no de un
   docking cuántico AD4.
═══════════════════════════════════════════════════════════════════
"""

import asyncio
from utils.procesos import BANDERAS_SIN_VENTANA, communicate_managed
import tempfile
from pathlib import Path

from core.config import get_settings
from core.exceptions import DockingFailed
from core.models import DockingResult
from services.xtb.service import get_xtb_service
from services.docking.vina_service import _parse_vina_stdout, _parse_vina_metadata, _resolve_executable
from utils.file_handlers import StoragePath
from utils.local_storage import exists, read_text, temp_file, write_text
from services.avisos import Severidad, aviso
from utils.logger import get_logger

log = get_logger(__name__)

async def _prepare_quantum_ligand_pdbqt(smiles_hash: str) -> str:
    """
    1. Descarga el SDF original.
    2. Usa xTB para generar cargas GFN2.
    3. Usa Meeko programáticamente para convertir a PDBQT reteniendo las cargas.
    """
    settings = get_settings()
    object_name = StoragePath.ligand_vina_input(smiles_hash)
    # Evitar re-preparar si ya existe
    if await exists(object_name):
        return object_name

    conformer_path = StoragePath.ligand_conformer(smiles_hash)
    sdf_content = await read_text(conformer_path)

    # Nivel 4: Calcular cargas GFN2-xTB
    xtb_service = get_xtb_service()
    if not xtb_service.is_configured:
        raise DockingFailed(molecule_id=smiles_hash, detail="xTB no está configurado o instalado.")

    xtb_res = await xtb_service.generate_partial_charges(sdf_content, smiles_hash)
    if not xtb_res.success or not xtb_res.charges:
        raise DockingFailed(molecule_id=smiles_hash, detail=f"xTB falló: {xtb_res.error}")

    # Guardar temporalmente el SDF y pasarlo a RDKit
    Path(settings.vina_temp_dir).mkdir(parents=True, exist_ok=True)
    # `ignore_cleanup_errors`: en Windows no se puede borrar un archivo que
    # alguien tenga abierto, y aqui dentro corren procesos hijos -Meeko, Vina,
    # Open Babel- mas el antivirus escaneando lo recien escrito. Sin esto, la
    # limpieza puede levantar PermissionError DESPUES de que el trabajo haya
    # terminado bien, y tirar una corrida completa por no poder borrar un
    # temporal. Dejar un archivo suelto es mucho mejor que perder el resultado.
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True, dir=settings.vina_temp_dir) as tmp_dir:
        input_sdf = Path(tmp_dir) / f"{smiles_hash}_quantum.sdf"
        input_sdf.write_text(sdf_content, encoding="utf-8")

        try:
            from rdkit import Chem
            mol = next(Chem.ForwardSDMolSupplier(str(input_sdf), sanitize=False))
            if not mol:
                raise ValueError("No se pudo cargar el SDF original")

            # Inyectamos cargas atómicas
            for atom, charge in zip(mol.GetAtoms(), xtb_res.charges):
                atom.SetDoubleProp("xTB_Charge", charge)

            from meeko import MoleculePreparation

            # Configuramos Meeko para leer nuestra propiedad inyectada
            preparator = MoleculePreparation(charge_model="read", charge_atom_prop="xTB_Charge")
            preparator.prepare(mol)
            pdbqt_string = preparator.write_pdbqt_string()

            await write_text(object_name, pdbqt_string)
        except Exception as e:
            raise DockingFailed(
                molecule_id=smiles_hash,
                detail=f"Error en preparación Meeko con cargas cuánticas: {str(e)}",
            )

    return object_name


async def run_quantum_ad4_docking(
    smiles_hash: str,
    target_pdb_id: str,
    grid_center_x: float,
    grid_center_y: float,
    grid_center_z: float,
    grid_size_x: float,
    grid_size_y: float,
    grid_size_z: float,
    exhaustiveness: int = 16,
) -> DockingResult:
    """
    Ejecuta AutoDock 4 (Nivel 4) con cargas cuánticas xTB.
    """
    settings = get_settings()
    vina_cmd = _resolve_executable(settings.vina_executable_path)
    if not vina_cmd:
        raise DockingFailed(molecule_id=smiles_hash, target_pdb_id=target_pdb_id, detail="Vina no encontrado.")

    # 1. Preparar ligando con xTB
    ligand_pdbqt_path = await _prepare_quantum_ligand_pdbqt(smiles_hash)
    receptor_pdbqt_path = StoragePath.target_prepared(target_pdb_id)

    async with temp_file(ligand_pdbqt_path, suffix=".pdbqt") as local_ligand:
        async with temp_file(receptor_pdbqt_path, suffix=".pdbqt") as local_receptor:

            # `ignore_cleanup_errors`: en Windows no se puede borrar un archivo que
            # alguien tenga abierto, y aqui dentro corren procesos hijos -Meeko, Vina,
            # Open Babel- mas el antivirus escaneando lo recien escrito. Sin esto, la
            # limpieza puede levantar PermissionError DESPUES de que el trabajo haya
            # terminado bien, y tirar una corrida completa por no poder borrar un
            # temporal. Dejar un archivo suelto es mucho mejor que perder el resultado.
            with tempfile.TemporaryDirectory(ignore_cleanup_errors=True, dir=settings.vina_temp_dir) as tmp_dir:
                output_pdbqt = Path(tmp_dir) / f"{smiles_hash}_ad4_out.pdbqt"

                # Ejecutar vina con la función de puntuación de AutoDock 4
                command = [
                    vina_cmd,
                    "--receptor", str(local_receptor),
                    "--ligand", str(local_ligand),
                    "--center_x", str(grid_center_x),
                    "--center_y", str(grid_center_y),
                    "--center_z", str(grid_center_z),
                    "--size_x", str(grid_size_x),
                    "--size_y", str(grid_size_y),
                    "--size_z", str(grid_size_z),
                    "--exhaustiveness", str(exhaustiveness),
                    "--out", str(output_pdbqt),
                    "--scoring", "ad4"  # CLAVE PARA NIVEL 4
                ]

                import time
                start_time = time.monotonic()

                process = await asyncio.create_subprocess_exec(
                    *command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    creationflags=BANDERAS_SIN_VENTANA,
                )
                stdout_bytes, stderr_bytes = await communicate_managed(process, timeout=600.0)
                execution_time = time.monotonic() - start_time

                stdout = stdout_bytes.decode("utf-8", errors="replace")
                stderr = stderr_bytes.decode("utf-8", errors="replace")

                if process.returncode != 0:
                    raise DockingFailed(
                        molecule_id=smiles_hash,
                        target_pdb_id=target_pdb_id,
                        vina_exit_code=process.returncode,
                        detail=stderr or stdout,
                    )

                if not output_pdbqt.exists():
                    raise DockingFailed(
                        molecule_id=smiles_hash,
                        target_pdb_id=target_pdb_id,
                        detail="AutoDock 4 no generó el archivo de salida (steric clash severo o fallo interno).",
                    )

                out_content = output_pdbqt.read_text(encoding="utf-8", errors="replace")

                # Guardar resultados en el storage local (agregamos sufijo ad4)
                poses_object_name = f"docking-poses/targets/{target_pdb_id}/ligands/{smiles_hash}_ad4.pdbqt"
                await write_text(poses_object_name, out_content)

                poses = _parse_vina_stdout(stdout)
                vina_version, random_seed = _parse_vina_metadata(stdout)

                return DockingResult(
                    poses=poses,
                    best_affinity=poses[0].affinity if poses else 0.0,
                    poses_file_path=poses_object_name,
                    parsing_source="pdbqt",
                    vina_version=f"{vina_version} (AD4 Scoring)",
                    vina_random_seed=random_seed,
                    execution_time_s=round(execution_time, 2),
                    scientific_warnings=[aviso(
                        "MOTOR_AD4_XTB", Severidad.INFO,
                        "Afinidad calculada con campo de fuerzas AD4 y cargas GFN2-xTB.",
                    )],
                )
