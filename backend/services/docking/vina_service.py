"""
services/docking/vina_service.py

Orquestación del docking real con AutoDock Vina.

Estrategia del MVP:
- preparar receptor con Meeko,
- preparar ligando desde SDF con Meeko,
- ejecutar Vina con parámetros explícitos,
- exportar poses a SDF con Meeko,
- parsear poses y cachear resultado.

Si alguna herramienta necesaria no existe, el servicio falla explícitamente.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import shutil
import sys
import tempfile
import time
from contextlib import asynccontextmanager
from pathlib import Path

from core.config import get_settings
from core.exceptions import DockingFailed, VinaExecutableNotFound
from core.models import DockingPose, DockingResult
from services.docking.preparer import prepare_target, resolve_effective_docking_box
from services.external_tools import open_babel
from utils.cache import cache
from utils.file_handlers import (
    StoragePath,
    parse_vina_output_sdf,
    parse_vina_output_pdbqt,
    extract_pdbqt_poses,
    validate_pdbqt_content,
)
from utils.local_storage import (
    exists,
    read_bytes,
    # `read_text` faltaba, y el censo de aguas lo llama. El `except Exception`
    # que lo envuelve convertía el NameError en «no se pudo medir», así que el
    # censo añadido el 2026-09-04 no funcionó una sola vez: cada corrida
    # registraba la advertencia genérica de desolvatación en lugar del conteo.
    read_text,
    temp_file,
    write_bytes,
    write_file,
    write_text,
)
from services.avisos import Severidad, aviso
from services.chemistry.censo_de_aguas import (
    censar_aguas,
    censo_en_cache,
    describir_censo,
    guardar_censo,
)
from utils.procesos import BANDERAS_SIN_VENTANA
from utils.logger import get_logger

settings = get_settings()
log = get_logger(__name__)


def _docking_cache_fingerprint(
    *,
    receptor_sha256: str,
    target_chain: str,
    center: tuple[float, float, float],
    size: tuple[float, float, float],
    hotspots: list[dict] | None,
    docking_engine: str,
    exhaustiveness: int,
    num_poses: int,
    seed: int,
) -> str:
    """Identifica el protocolo real, no sólo la pareja ligando/PDB.

    El caché histórico ignoraba cadena, caja, receptor preparado y parámetros
    de Vina. Dos hipótesis distintas podían por ello compartir un resultado.
    """

    document = {
        "receptor_sha256": receptor_sha256,
        "target_chain": target_chain,
        "center": [round(float(value), 3) for value in center],
        "size": [round(float(value), 3) for value in size],
        "hotspots": sorted(
            hotspots or [],
            key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":")),
        ),
        "docking_engine": docking_engine,
        "exhaustiveness": int(exhaustiveness),
        "num_poses": int(num_poses),
        "seed": int(seed),
    }
    encoded = json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()



def _is_valid_sdf(s: str) -> bool:
    """Validate that a string represents a well-formed SDF block."""
    if not s or not isinstance(s, str):
        return False
    lines = s.splitlines()
    if not any("M  END" in line for line in lines):
        return False
    if len(lines) < 4:
        return False
    try:
        atom_count = int(lines[3][0:3])
    except Exception:
        atom_count = 0
    atom_lines = lines[4:4 + atom_count]
    has_atoms = any(len(l.strip()) > 0 for l in atom_lines)
    return has_atoms and atom_count > 0


def _resolve_executable(path_or_name: str) -> str | None:
    candidate = Path(path_or_name)
    if candidate.exists():
        return str(candidate)

    found = shutil.which(path_or_name)
    if found:
        return found

    # Fallbacks for Windows Python environments
    search_dirs = [
        Path(sys.executable).resolve().parent,
        Path(sys.executable).resolve().parent / "Scripts",
        Path(sys.prefix) / "Scripts",
        Path.home() / "AppData" / "Roaming" / "Python" / "Python314" / "Scripts"
    ]

    for sdir in search_dirs:
        for ext in ["", ".exe", ".py"]:
            c = sdir / f"{path_or_name}{ext}"
            if c.exists():
                return str(c)

    return None


def _parse_vina_stdout(stdout: str) -> list[DockingPose]:
    mode_table_pattern = re.compile(
        r"^\s*(\d+)\s+([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s+([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s+([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s*$"
    )

    poses: list[DockingPose] = []
    in_mode_table = False

    for line in stdout.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        if stripped.lower().startswith("mode |"):
            in_mode_table = True
            continue

        if not in_mode_table:
            continue

        if stripped.startswith("-----+"):
            continue

        match = mode_table_pattern.match(stripped)
        if not match:
            if poses:
                break
            continue

        rank, affinity, rmsd_lb, rmsd_ub = match.groups()

        try:
            poses.append(
                DockingPose(
                    rank=int(rank),
                    affinity=float(affinity),
                    rmsd_lb=float(rmsd_lb),
                    rmsd_ub=float(rmsd_ub),
                )
            )
        except ValueError:
            continue

    return poses


def _parse_vina_metadata(stdout: str) -> tuple[str | None, int | None]:
    version_match = re.search(r"AutoDock Vina\s+v([\d\.]+)", stdout)
    seed_match = re.search(r"random seed:\s*(-?\d+)", stdout)

    vina_version = version_match.group(1) if version_match else None
    random_seed = int(seed_match.group(1)) if seed_match else None
    return vina_version, random_seed


def _relative_error_pct(observed: float, reference: float) -> float:
    denominator = max(abs(reference), 1e-12)
    return abs(observed - reference) / denominator * 100.0


# ── Open Babel: por qué aquí no hay ninguna resolución de ejecutable ─────
#
# Antes vivía aquí un `_obabel_del_bundle()` que buscaba el binario dentro de
# `site-packages/openbabel/bin/` y, si no lo encontraba, devolvía la cadena
# `"obabel"` para que el PATH la resolviera. Las dos mitades eran un problema:
#
#   - la primera ataba producción al ENTORNO PYTHON de Open Babel, que es
#     justamente lo que la frontera de licencia exige separar;
#   - la segunda ejecutaba en silencio un binario ajeno de la máquina del
#     usuario y después atribuía el resultado a la versión declarada.
#
# Ahora hay un único adaptador —`services.external_tools.open_babel`— que
# ejecuta SÓLO el programa empaquetado, verificado contra su hash, y devuelve
# errores tipados en vez de degradarse. Ver `docs/79_ADR_FRONTERA_OPEN_BABEL.md`.

#: Cuando una etapa no SABE contra que receptor corre, lo dice. Antes ponia la
#: constante por defecto, que es afirmar algo falso en el informe de error.
DESCONOCIDO = "(receptor no informado en esta etapa)"


async def _prepare_ligand_pdbqt(
    smiles_hash: str,
    smiles: str | None = None,
    target_pdb_id: str | None = None,
) -> str:
    """Prepara el PDBQT del ligando con Meeko. NO ejecuta Vina.

    EL FALLO QUE ARREGLA. Los errores de esta funcion se reportaban con dos
    datos falsos, y juntos mandaban a investigar el sitio equivocado:

      1. `target_pdb_id=settings.default_target_pdb_id`. Esta funcion no
         recibia el receptor, asi que ponia la CONSTANTE por defecto -7E2Y-.
         Un usuario que habia elegido 1TW7 leyo «falló contra target 7E2Y» y
         se paso el rato mirando una estructura que no intervenia.
      2. `vina_exit_code=process.returncode`, cuando el proceso que fallo era
         `mk_prepare_ligand` de Meeko. El mensaje decia «Vina exit code: 1»
         sobre un fallo en el que Vina ni siquiera habia llegado a arrancar.

    En una herramienta cuyo producto es la trazabilidad, un mensaje de error
    que nombra el receptor equivocado y la etapa equivocada no es un detalle
    cosmetico: es la misma clase de mentira de procedencia que ENG-003.
    """
    ligand_prepare_cmd = _resolve_executable(settings.meeko_prepare_ligand_path)
    if not ligand_prepare_cmd:
        raise DockingFailed(
            molecule_id=smiles_hash,
            target_pdb_id=target_pdb_id or DESCONOCIDO,
            detail=(
                "PREPARACIÓN DEL LIGANDO (Meeko), antes de ejecutar Vina: no se "
                "encontró 'mk_prepare_ligand.py'. Instala Meeko o configura "
                "MEEKO_PREPARE_LIGAND_PATH correctamente."
            ),
        )

    object_name = StoragePath.ligand_vina_input(smiles_hash)
    if await exists(object_name):
        return object_name

    conformer_path = StoragePath.ligand_conformer(smiles_hash)
    if smiles:
        try:
            from chem.validator import validate_smiles_or_raise
            v = validate_smiles_or_raise(smiles)
            cand_path = StoragePath.ligand_conformer(v.smiles_hash)
            if await exists(cand_path):
                conformer_path = cand_path
        except Exception:
            pass

    if not await exists(conformer_path):
        # Fallback: generate conformer on-the-fly if smiles is known or can be fetched
        target_smiles = smiles
        if not target_smiles:
            try:
                from core.database import get_db_session
                from db.repository import Repository
                async with get_db_session() as db:
                    repo = Repository(db)
                    mol = await repo.get_molecule_by_hash(smiles_hash)
                    if mol:
                        target_smiles = mol.smiles
            except Exception:
                pass
        if target_smiles:
            try:
                from chem.conformer import generate_conformer
                conf_res = await generate_conformer(target_smiles)
                sdf_str = conf_res.get("sdf_content") if isinstance(conf_res, dict) else (conf_res if isinstance(conf_res, str) else None)
                if sdf_str:
                    await write_text(conformer_path, sdf_str)
                    await write_text(StoragePath.ligand_conformer(smiles_hash), sdf_str)
                    if isinstance(conf_res, dict) and conf_res.get("smiles_hash"):
                        await write_text(StoragePath.ligand_conformer(conf_res["smiles_hash"]), sdf_str)
                        conformer_path = StoragePath.ligand_conformer(conf_res["smiles_hash"])
            except Exception as e:
                log.warning("conformer_generation_fallback_failed", error=str(e))

    async with temp_file(conformer_path, suffix=".sdf") as local_sdf:
        Path(settings.vina_temp_dir).mkdir(parents=True, exist_ok=True)
        # `ignore_cleanup_errors`: en Windows no se puede borrar un archivo que
        # alguien tenga abierto, y aqui dentro corren procesos hijos -Meeko, Vina,
        # Open Babel- mas el antivirus escaneando lo recien escrito. Sin esto, la
        # limpieza puede levantar PermissionError DESPUES de que el trabajo haya
        # terminado bien, y tirar una corrida completa por no poder borrar un
        # temporal. Dejar un archivo suelto es mucho mejor que perder el resultado.
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True, dir=settings.vina_temp_dir) as tmp_dir:
            output_pdbqt = Path(tmp_dir) / f"{smiles_hash}.pdbqt"
            # Se invoca el MODULO con el interprete del backend, nunca el .exe
            # de Scripts/.
            #
            # EL FALLO QUE ARREGLA. Los lanzadores que pip genera en Windows
            # llevan INCRUSTADA la ruta absoluta del interprete con el que se
            # instalaron. Los tres de Meeko que viajan en el instalador dicen
            #
            #     D:\moldesign-build\python-embed\python.exe
            #
            # ...la ruta de la maquina de construccion. En cualquier otro
            # equipo ese interprete no existe, el lanzador falla y devuelve 1,
            # asi que TODA evaluacion moria antes de llegar a Vina. En la
            # maquina donde se construye funciona, que es lo que lo hizo
            # invisible hasta probarlo en una VM.
            #
            # `preparer.py` ya lo resolvia asi para el receptor -«usar
            # exactamente el interprete del backend instalado por el
            # launcher»-. Esta ruta y la del export no lo habian aprendido.
            command = [
                sys.executable,
                "-m", "meeko.cli.mk_prepare_ligand",
                "-i", str(local_sdf),
                "-o", str(output_pdbqt),
            ]

            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                creationflags=BANDERAS_SIN_VENTANA,
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                salida = (stderr.decode("utf-8", errors="replace")
                          or stdout.decode("utf-8", errors="replace"))
                raise DockingFailed(
                    molecule_id=smiles_hash,
                    target_pdb_id=target_pdb_id or DESCONOCIDO,
                    # `vina_exit_code` se deja vacio A PROPOSITO: el que fallo
                    # fue Meeko y Vina no ha llegado a ejecutarse.
                    detail=(
                        f"PREPARACIÓN DEL LIGANDO (Meeko `mk_prepare_ligand`) terminó "
                        f"con codigo {process.returncode}, antes de ejecutar Vina."
                        + chr(10) + chr(10) + salida
                    ),
                )

            content = output_pdbqt.read_text(encoding="utf-8", errors="replace")
            is_valid, validation_error = validate_pdbqt_content(content)
            if not is_valid:
                raise DockingFailed(
                    molecule_id=smiles_hash,
                    target_pdb_id=target_pdb_id or DESCONOCIDO,
                    detail=(
                        "PREPARACIÓN DEL LIGANDO (Meeko), antes de ejecutar Vina: "
                        f"el PDBQT resultante es inválido: {validation_error}"
                    ),
                )

            await write_file(output_pdbqt, object_name)

    return object_name


async def _run_vina_subprocess(
    receptor_path: Path,
    ligand_path: Path,
    output_path: Path,
    log_path: Path,
    target_pdb_id: str,
    center: tuple[float, float, float],
    size: tuple[float, float, float],
    molecule_id: str = "unknown",
    exhaustiveness: int | None = None,
    docking_engine: str = "vina",
    num_poses: int | None = None,
    seed: int | None = None,
) -> str:
    # ── Select executable based on docking engine ──
    if docking_engine == "qvina2":
        vina_executable = _resolve_executable(settings.qvina2_executable_path)
        if not vina_executable:
            log.warning({
                "event": "qvina2_not_found",
                "path": settings.qvina2_executable_path,
                "message": "QuickVina 2 binary not found, falling back to Vina (lower exhaustiveness=4)",
            })
            vina_executable = _resolve_executable(settings.vina_executable_path)
    else:
        vina_executable = _resolve_executable(settings.vina_executable_path)

    if not vina_executable:
        raise VinaExecutableNotFound(
            settings.qvina2_executable_path if docking_engine == "qvina2" else settings.vina_executable_path
        )

    exh = exhaustiveness if exhaustiveness is not None else settings.vina_exhaustiveness
    modes = num_poses if num_poses is not None else settings.vina_num_poses
    sd = seed if seed is not None else settings.vina_seed

    command = [
        vina_executable,
        "--receptor", str(receptor_path),
        "--ligand", str(ligand_path),
        "--center_x", str(center[0]),
        "--center_y", str(center[1]),
        "--center_z", str(center[2]),
        "--size_x", str(size[0]),
        "--size_y", str(size[1]),
        "--size_z", str(size[2]),
        "--exhaustiveness", str(exh),
        "--num_modes", str(modes),
        "--cpu", str(settings.vina_cpu),
        "--seed", str(sd),
        "--out", str(output_path),
    ]

    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        creationflags=BANDERAS_SIN_VENTANA,
    )
    arranque = time.monotonic()
    try:
        # Timeout de 10 minutos para soportar ex=32 en GPCRs
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            process.communicate(), timeout=600.0
        )
    except asyncio.TimeoutError:
        process.kill()
        await process.communicate()  # clean up
        raise DockingFailed(
            molecule_id=molecule_id,
            target_pdb_id=target_pdb_id,
            detail="AutoDock Vina excedió el timeout de 600 segundos. "
                   "La molécula puede ser demasiado grande o compleja para este setup.",
        )

    stdout = stdout_bytes.decode("utf-8", errors="replace")
    stderr = stderr_bytes.decode("utf-8", errors="replace")

    log_content = (
        f"# target={target_pdb_id}\n"
        f"# receptor={receptor_path}\n"
        f"# ligand={ligand_path}\n"
        f"# exhaustiveness={settings.vina_exhaustiveness}\n"
        f"# num_modes={settings.vina_num_poses}\n\n"
        f"STDOUT:\n{stdout}\n\nSTDERR:\n{stderr}\n"
    )
    log_path.write_text(log_content, encoding="utf-8")

    if process.returncode != 0:
        raise DockingFailed(
            molecule_id=ligand_path.stem,
            target_pdb_id=target_pdb_id,
            vina_exit_code=process.returncode,
            detail=stderr or stdout,
        )

    # Lo que de verdad tardó, en ESTA máquina. Es lo que convierte la estimación
    # que se le ensena al usuario antes de pulsar «Evaluar» en una medida en vez
    # de una tabla. Sólo cuentan los acoplamientos que terminaron bien: uno que
    # falló a los dos segundos no dice cuánto cuesta uno que funciona.
    #
    # Va en un `try` amplio a proposito, y es el unico sitio de este archivo
    # donde eso es correcto: calibrar es accesorio, y perder una estimacion
    # nunca puede costar una corrida que el motor ya completo.
    try:
        from services.estimacion import registrar_docking

        registrar_docking(
            segundos=time.monotonic() - arranque,
            cpu=int(settings.vina_cpu),
            exhaustiveness=exh,
            volumen_caja=float(size[0]) * float(size[1]) * float(size[2]),
        )
    except Exception:  # noqa: BLE001
        pass

    return stdout


def _check_ligand_fits_box(
    ligand_pdbqt: Path,
    box_size: tuple[float, float, float],
    target_pdb_id: str,
    margin: float = 4.0,
) -> str | None:
    """Verifica que el ligando quepa en la caja de docking con margen de solvatacion.

    Retorna un warning string si el ligando excede la caja, None si esta OK.
    """
    try:
        coords = []
        with open(ligand_pdbqt) as f:
            for line in f:
                if line.startswith(("ATOM", "HETATM")):
                    x = float(line[30:38].strip())
                    y = float(line[38:46].strip())
                    z = float(line[46:54].strip())
                    coords.append([x, y, z])
        if not coords:
            return None
        coords = __import__("numpy").array(coords)
        ligand_dim = coords.max(axis=0) - coords.min(axis=0)
        for i, axis in enumerate(["X", "Y", "Z"]):
            if ligand_dim[i] + margin > box_size[i]:
                return (
                    f"Ligando excede caja de docking en eje {axis}: "
                    f"{ligand_dim[i]:.1f}A + {margin:.1f}A margen > {box_size[i]:.1f}A caja. "
                    f"Target: {target_pdb_id}. Posible clipping estructural."
                )
    except Exception:
        pass
    return None


async def run_vina_docking(
    smiles_hash: str,
    target_pdb_id: str,
    target_chain: str = "A",
    target_center: tuple[float, float, float] = (0.0, 0.0, 0.0),
    target_size: tuple[float, float, float] = (20.0, 20.0, 20.0),
    force_redock: bool = False,
    hotspots: list[dict] | None = None,
    docking_engine: str = "vina",
    exhaustiveness: int | None = None,
    num_poses: int | None = None,
    seed: int | None = None,
    smiles: str | None = None,
    prepared_receptor_bytes: bytes | None = None,
    cofactors_whitelist: list[str] | None = None,
    site_chains: list[str] | None = None,
) -> DockingResult:
    """Ejecuta docking real o devuelve cache si ya existe un cálculo idéntico.

    Args:
        docking_engine: 'vina' (exhaustiveness=8) o 'qvina2' (exhaustiveness=4, ~3x rapido)
        site_chains: las cadenas que FORMAN el sitio, del catalogo. Con dos o
            mas, el receptor se prepara en modo multicadena y se recorta al
            sitio. Sin esto, un sitio de interfaz se acopla contra media
            cavidad (doc 71, modo C).
    """
    receptor_object_path = None
    if prepared_receptor_bytes is None:
        receptor_object_path = await prepare_target(
            pdb_id=target_pdb_id,
            chain_id=target_chain,
            center=target_center,
            size=target_size,
            force_reprepare=False,
            cofactors_whitelist=cofactors_whitelist,
            site_chains=site_chains,
        )
        effective_center, effective_size = resolve_effective_docking_box(
            pdb_id=target_pdb_id,
            chain_id=target_chain,
            center=target_center,
            size=target_size,
        )
        receptor_content = await read_bytes(receptor_object_path)
    else:
        # Una corrida durable usa exactamente el receptor que congeló al
        # abrirse. No consulta ni reprepara el objeto mutable del catálogo.
        receptor_content = bytes(prepared_receptor_bytes)
        effective_center = tuple(float(v) for v in target_center)
        effective_size = tuple(float(v) for v in target_size)
    receptor_sha256 = hashlib.sha256(receptor_content).hexdigest()
    receptor_snapshot_path = StoragePath.prepared_receptor_snapshot(receptor_sha256)
    # Se materializa incluso ante cache hit: caches creados antes de este
    # contrato sólo guardaban el hash y no podían reconstruir el input.
    await write_bytes(receptor_content, receptor_snapshot_path)
    effective_exhaustiveness = (
        int(exhaustiveness)
        if exhaustiveness is not None
        else (4 if docking_engine == "qvina2" else int(settings.vina_exhaustiveness))
    )
    effective_num_poses = int(num_poses) if num_poses is not None else int(settings.vina_num_poses)
    effective_seed = int(seed) if seed is not None else int(settings.vina_seed)
    effective_engine_identity = docking_engine
    if docking_engine == "qvina2" and not _resolve_executable(settings.qvina2_executable_path):
        effective_engine_identity = "vina_fallback_from_qvina2"
    cache_fingerprint = _docking_cache_fingerprint(
        receptor_sha256=receptor_sha256,
        target_chain=target_chain,
        center=effective_center,
        size=effective_size,
        hotspots=hotspots,
        docking_engine=effective_engine_identity,
        exhaustiveness=effective_exhaustiveness,
        num_poses=effective_num_poses,
        seed=effective_seed,
    )

    if not force_redock:
        cached = await cache.get_docking_result(
            smiles_hash,
            target_pdb_id,
            cache_fingerprint,
        )
        if cached is not None:
            log.info(
                {
                    "event": "vina_cache_hit",
                    "smiles_hash": smiles_hash,
                    "target_pdb_id": target_pdb_id,
                    "config": cache_fingerprint[:12],
                }
            )
            cached["receptor_sha256"] = receptor_sha256
            cached["receptor_path"] = receptor_snapshot_path
            return DockingResult(**cached)

    # Use a unique subdirectory for each job to avoid race conditions in parallel runs
    job_temp_dir = Path(tempfile.mkdtemp(prefix=f"vina-{smiles_hash[:8]}-{target_pdb_id}-", dir=settings.vina_temp_dir))

    try:
        ligand_object_path = await _prepare_ligand_pdbqt(
            smiles_hash, smiles=smiles, target_pdb_id=target_pdb_id
        )

        export_cmd = _resolve_executable(settings.meeko_export_path)
        if not export_cmd:
            raise DockingFailed(
                molecule_id=smiles_hash,
                target_pdb_id=target_pdb_id,
                detail=(
                    "No se encontró 'mk_export.py'. La exportación a SDF es necesaria para "
                    "conservar conectividad y órdenes de enlace de forma defendible."
                ),
            )

        @asynccontextmanager
        async def receptor_file():
            if prepared_receptor_bytes is not None:
                snapshot_path = job_temp_dir / "receptor_snapshot.pdbqt"
                snapshot_path.write_bytes(receptor_content)
                yield snapshot_path
            else:
                assert receptor_object_path is not None
                async with temp_file(receptor_object_path, suffix=".pdbqt") as local:
                    yield local

        async with receptor_file() as receptor_local:
            async with temp_file(ligand_object_path, suffix=".pdbqt") as ligand_local:
                # We use the job_temp_dir we created
                tmp_dir_path = job_temp_dir
                output_pdbqt = tmp_dir_path / f"{smiles_hash}_{target_pdb_id}_out.pdbqt"
                output_sdf = tmp_dir_path / f"{smiles_hash}_{target_pdb_id}_out.sdf"
                output_log = tmp_dir_path / f"{smiles_hash}_{target_pdb_id}.log"

                scientific_warnings: list[dict] = []

                # ── Qué aguas tenía el sitio antes de quitarlas ─────────────
                #
                # `preparer.py` elimina TODAS las aguas cristalográficas, que es
                # lo estándar en acoplamiento generalista y no se cambia aquí.
                # Lo que faltaba era decirlo con números: el dossier declaraba
                # «condición desolvatada» en abstracto, igual para un sitio seco
                # que para uno con treinta aguas y ocho bien coordinadas.
                #
                # Se mide sobre el PDB DEPOSITADO, que es el único que todavía
                # las tiene; el preparado ya no. Ver
                # `services/chemistry/censo_de_aguas.py` para la medición sobre
                # el catálogo que desaconseja conservarlas por conteo de puentes.
                #
                # LA LECTURA ESTABA EN EL CAMINO CALIENTE. El censo es
                # determinista en (pdb_id, centro, tamaño): mismo receptor y
                # misma caja, mismo resultado. El cálculo son ~4 ms, pero leer el
                # PDB depositado es E/S por corrida sobre cientos de KB. Se
                # consulta la caché ANTES de leer, que es donde está el ahorro.
                try:
                    _censo = censo_en_cache(
                        target_pdb_id, effective_center, effective_size
                    )
                    if _censo is None:
                        _crudo = await read_text(StoragePath.target_raw(target_pdb_id))
                        _censo = censar_aguas(_crudo, effective_center, effective_size)
                        guardar_censo(
                            target_pdb_id, effective_center, effective_size, _censo
                        )
                    scientific_warnings.append(aviso(
                        "SITIO_DESOLVATADO", Severidad.INFO, describir_censo(_censo),
                    ))
                except Exception as _err:  # noqa: BLE001 — declarativo, nunca bloquea
                    # Sin el crudo no se puede censar. Se dice, en vez de callar:
                    # un dossier sin la línea de aguas y uno con «no se pudo
                    # medir» no significan lo mismo.
                    log.debug("censo_de_aguas_no_disponible",
                              target=target_pdb_id, error=str(_err)[:120])
                    scientific_warnings.append(aviso(
                        "SITIO_DESOLVATADO", Severidad.INFO,
                        "Preparación en condición desolvatada: se retiraron las aguas "
                        "cristalográficas del receptor. No se pudo leer la estructura "
                        "depositada para contar cuántas había en el sitio.",
                    ))

                # v1.5: Validar que el ligando cabe en la caja de docking
                _ligand_size_warning = _check_ligand_fits_box(
                    ligand_local, effective_size, target_pdb_id
                )
                if _ligand_size_warning:
                    # El ligando no cabe en la caja: la búsqueda está recortada y
                    # la mejor pose puede ser un artefacto del recorte.
                    scientific_warnings.append(aviso(
                        "LIGANDO_EXCEDE_CAJA", Severidad.CRITICA, _ligand_size_warning,
                    ))

                stdout = await _run_vina_subprocess(
                    receptor_path=receptor_local,
                    ligand_path=ligand_local,
                    output_path=output_pdbqt,
                    log_path=output_log,
                    target_pdb_id=target_pdb_id,
                    center=effective_center,
                    size=effective_size,
                    molecule_id=smiles_hash,
                    exhaustiveness=effective_exhaustiveness,
                    docking_engine=docking_engine,
                    num_poses=effective_num_poses,
                    seed=effective_seed,
                )

                # Mismo motivo que en la preparacion del ligando: el .exe de
                # Scripts/ apunta al interprete de la maquina de construccion.
                export_process = await asyncio.create_subprocess_exec(
                    sys.executable,
                    "-m", "meeko.cli.mk_export",
                    str(output_pdbqt),
                    "-s",
                    str(output_sdf),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    creationflags=BANDERAS_SIN_VENTANA,
                )
                try:
                    export_stdout, export_stderr = await asyncio.wait_for(
                        export_process.communicate(), timeout=60.0
                    )
                except asyncio.TimeoutError:
                    export_process.kill()
                    await export_process.communicate()  # cleanup
                    raise DockingFailed(
                        molecule_id=smiles_hash,
                        target_pdb_id=target_pdb_id,
                        detail="La exportación de Meeko (mk_export) excedió el timeout de 60 segundos.",
                    )

                if export_process.returncode != 0 or not output_sdf.exists():
                    raise DockingFailed(
                        molecule_id=smiles_hash,
                        target_pdb_id=target_pdb_id,
                        detail=(
                            export_stderr.decode("utf-8", errors="replace")
                            or export_stdout.decode("utf-8", errors="replace")
                            or "mk_export.py no generó el SDF esperado"
                        ),
                    )

                sdf_content = output_sdf.read_text(encoding="utf-8", errors="replace")
                def cast_pose_dict(p):
                    return {
                        "rank": int(p["rank"]),
                        "affinity": float(p["affinity"]),
                        "rmsd_lb": float(p["rmsd_lb"]),
                        "rmsd_ub": float(p["rmsd_ub"]),
                    }

                pdbqt_content = output_pdbqt.read_text(encoding="utf-8", errors="replace")
                pdbqt_pose_blocks = extract_pdbqt_poses(pdbqt_content)

                parsed_poses = parse_vina_output_sdf(sdf_content) if _is_valid_sdf(sdf_content) else []
                poses: list[DockingPose] = []
                for i, pose_dict in enumerate(parsed_poses):
                    # Asignamos el bloque PDBQT correspondiente si existe
                    block = pdbqt_pose_blocks[i] if i < len(pdbqt_pose_blocks) else None
                    poses.append(DockingPose(**cast_pose_dict(pose_dict), pdbqt_block=block))

                parsing_source = "sdf" if poses else None

                # ── QUÉ SDF SE ENTREGA ───────────────────────────────────
                #
                # EL FALLO QUE ARREGLA. Después del respaldo de Open Babel, la
                # persistencia era literal e incondicional:
                #
                #     await write_file(output_sdf, poses_path)
                #
                # es decir, se guardaba SIEMPRE el SDF de Meeko —el inválido, el
                # que había obligado a llamar al respaldo— mientras las poses del
                # informe salían del SDF de Open Babel, que se borraba a
                # continuación. El dossier citaba unas poses y entregaba un
                # archivo que no las contenía.
                #
                # A partir de aquí el archivo entregado es una decisión
                # explícita: `sdf_a_persistir` es siempre aquel del que salieron
                # las poses que se van a informar.
                #: El SDF que produjo un conversor externo, cuando fue de ahí de
                #: donde salieron las poses. `None` —el caso normal y el de
                #: todas las corridas anteriores— significa que se entrega el
                #: archivo de Meeko tal cual.
                sdf_a_persistir: str | None = None
                #: Qué programa externo produjo ese archivo, con su procedencia.
                conversor_estructural: dict | None = None

                # ── Respaldo: Open Babel convierte el PDBQT a SDF ────────
                #
                # Se llega aquí cuando Meeko exportó un SDF zombi. Open Babel es
                # un PROGRAMA INDEPENDIENTE (GPL-2.0-only) que se invoca por
                # subproceso a través del adaptador único; ni se importa ni se
                # enlaza. Ver `docs/79_ADR_FRONTERA_OPEN_BABEL.md`.
                #
                # No hay `except Exception` aquí. El error del adaptador es
                # tipado y su estado se declara: convertir un fallo en «no
                # disponible» es exactamente cómo cuatro componentes de este
                # árbol se apagaron sin que nadie lo notara.
                if not poses:
                    try:
                        conversion = await open_babel.convertir_pdbqt_a_sdf(pdbqt_content)
                    except open_babel.OpenBabelNoDisponible as ob_exc:
                        # Open Babel viaja en el instalador: su ausencia o su
                        # alteración es una instalación dañada, no una función
                        # opcional. Se registra con el motivo y NO se atribuye
                        # nada a Open Babel, porque no llegó a ejecutarse.
                        log.warning(
                            "respaldo_open_babel_no_disponible",
                            estado=ob_exc.estado.value,
                            detalle=ob_exc.detalle,
                        )
                        scientific_warnings.append(aviso(
                            "CONVERSOR_ESTRUCTURAL_NO_DISPONIBLE", Severidad.CRITICA,
                            "La exportación de Meeko no produjo un SDF utilizable y el "
                            "conversor estructural empaquetado (Open Babel) no se pudo "
                            f"usar [{ob_exc.estado.value}]: {ob_exc.detalle} "
                            "La evidencia estructural de esta corrida queda incompleta.",
                        ))
                    else:
                        parsed_poses = parse_vina_output_sdf(conversion.contenido)
                        poses = []
                        for i, pose_dict in enumerate(parsed_poses):
                            # El bloque PDBQT original viaja intacto: la
                            # trazabilidad hacia lo que Vina escribió de verdad
                            # no depende de la conversión.
                            block = pdbqt_pose_blocks[i] if i < len(pdbqt_pose_blocks) else None
                            poses.append(DockingPose(**cast_pose_dict(pose_dict), pdbqt_block=block))
                        if poses:
                            parsing_source = "sdf_openbabel_cli"
                            sdf_a_persistir = conversion.contenido
                            conversor_estructural = {
                                "herramienta": "Open Babel",
                                "invocacion": "subproceso CLI",
                                "version_declarada": conversion.version_declarada,
                                "licencia_spdx": conversion.licencia_spdx,
                                "ruta_relativa": conversion.ruta_relativa,
                                "sha256": conversion.sha256,
                                "motivo": "la exportación de Meeko no produjo un SDF utilizable",
                            }
                            log.warning(
                                "respaldo_open_babel_usado",
                                version=conversion.version_declarada,
                                sha256=conversion.sha256[:12],
                                poses=len(poses),
                            )
                            scientific_warnings.append(aviso(
                                "CONVERSION_ESTRUCTURAL_DE_RESPALDO", Severidad.INFO,
                                "El SDF de poses lo produjo Open Babel "
                                f"{conversion.version_declarada} (GPL-2.0-only, invocado "
                                "como herramienta externa) a partir del PDBQT de Vina, "
                                "porque la exportación de Meeko no era utilizable. Las "
                                "afinidades no cambian: salen del mismo parser.",
                            ))
                        else:
                            # MEDIDO el 2026-09-05, y por eso esto no añade un
                            # aviso al dossier: con un PDBQT de Vina éste es el
                            # camino NORMAL, no una anomalía.
                            #
                            # Open Babel convierte bien y produce un SDF válido,
                            # pero escribe los datos de Vina en una propiedad
                            # `> <REMARK>`, y `parse_vina_output_sdf` sólo lee
                            # `> <meeko>` y `> <minimizedAffinity>`. Resultado:
                            # cero poses desde el SDF convertido, y las
                            # afinidades acaban saliendo del parser de PDBQT
                            # justo debajo — que las extrae de las mismas líneas
                            # `REMARK VINA RESULT`, así que el número es idéntico.
                            #
                            # La consecuencia incómoda es que en este camino el
                            # archivo entregado sigue siendo el SDF de Meeko,
                            # que no contiene las poses del informe. Arreglarlo
                            # exige enseñar al parser a leer el bloque
                            # `<REMARK>`, y eso CAMBIA la procedencia y los
                            # bytes persistidos de corridas existentes: es una
                            # decisión con efecto sobre el estado científico y
                            # no se toma de paso en un cambio de arquitectura.
                            # Queda declarado en `docs/79_ADR_FRONTERA_OPEN_BABEL.md` §10.
                            log.info(
                                "respaldo_open_babel_sin_metadatos_en_el_sdf",
                                detalle=(
                                    "Open Babel produjo un SDF válido; sus datos de "
                                    "Vina viajan en `> <REMARK>`, que parse_vina_output_sdf "
                                    "no lee. Las afinidades se extraen del PDBQT, de las "
                                    "mismas líneas REMARK VINA RESULT."
                                ),
                                version=conversion.version_declarada,
                            )

                # Fallback: if still no poses, try parsing PDBQT for affinity only
                if not poses:
                    pdbqt_content = output_pdbqt.read_text(encoding="utf-8", errors="replace")
                    pdbqt_pose_blocks = extract_pdbqt_poses(pdbqt_content)
                    parsed_poses_pdbqt = parse_vina_output_pdbqt(pdbqt_content)
                    poses = []
                    for i, pose in enumerate(parsed_poses_pdbqt):
                        block = pdbqt_pose_blocks[i] if i < len(pdbqt_pose_blocks) else None
                        poses.append(DockingPose(**cast_pose_dict(pose), pdbqt_block=block))
                    if poses:
                        parsing_source = "pdbqt"
                        log.warning("Affinity fallback: Extracted from REMARK VINA RESULT because SDF lacked numeric metadata.")

                if not poses:
                    if not settings.docking_allow_stdout_fallback:
                        raise DockingFailed(
                            molecule_id=smiles_hash,
                            target_pdb_id=target_pdb_id,
                            detail=(
                                "No se pudieron extraer poses estructuradas desde SDF/PDBQT y el fallback "
                                "a stdout está deshabilitado por rigor científico."
                            ),
                        )

                    poses_stdout = _parse_vina_stdout(stdout)
                    pdbqt_pose_blocks = extract_pdbqt_poses(pdbqt_content)
                    poses = []
                    for i, pose in enumerate(poses_stdout):
                        block = pdbqt_pose_blocks[i] if i < len(pdbqt_pose_blocks) else None
                        poses.append(DockingPose(**cast_pose_dict(pose.model_dump()), pdbqt_block=block))
                    if poses:
                        parsing_source = "vina_stdout"
                        scientific_warnings.append(aviso(
                            "PARSEO_DESDE_STDOUT", Severidad.INFO,
                            "Las afinidades se extrajeron de la tabla de stdout de Vina; "
                            "revisa el log para trazabilidad completa.",
                        ))

                if not poses:
                    raise DockingFailed(
                        molecule_id=smiles_hash,
                        target_pdb_id=target_pdb_id,
                        detail="Vina terminó pero no se pudieron parsear poses válidas.",
                    )

                if poses[0].affinity > -3.0:
                    # PRECAUCION, no nota: por encima de -6 el score de Vina deja
                    # de discriminar bien entre unir y no unir, y por encima de
                    # -3 la corrida no sostiene una lectura de unión.
                    scientific_warnings.append(aviso(
                        "AFINIDAD_DEBIL", Severidad.PRECAUCION,
                        "La mejor afinidad es débil (> -3.0 kcal/mol); interpretar como "
                        "baja evidencia de unión en este setup de docking.",
                    ))

                # v1.8.1: Afinidad POSITIVA = docking no productivo.
                # Vina devuelve afinidades positivas cuando NO encuentra ninguna
                # pose favorable (receptor mal preparado, grid box fuera del sitio
                # activo, o ligando incompatible con el pocket). Un valor > 0
                # viola la convención termodinámica (kcal/mol debe ser negativo
                # para unión favorable) y rompía DockingResult con ValidationError
                # de Pydantic. Ahora lo tratamos como DockingFailed con un mensaje
                # accionable para el usuario (caso real: 4EJJ con grid desplazado).
                if poses[0].affinity > 0.0:
                    log.warning(
                        "vina_affinity_positiva",
                        target_pdb_id=target_pdb_id,
                        best_affinity=poses[0].affinity,
                        n_poses=len(poses),
                        hint="receptor_o_box_probablemente_mal_preparado",
                    )
                    raise DockingFailed(
                        molecule_id=smiles_hash,
                        target_pdb_id=target_pdb_id,
                        detail=(
                            "Vina no produjo poses con afinidad favorable (todas las poses > 0 kcal/mol, "
                            f"mejor={poses[0].affinity:.2f}). Esto suele indicar que el receptor no está "
                            "preparado correctamente o que la caja de docking no cubre el sitio activo del "
                            "target. Verifica la preparación del receptor o selecciona otro target."
                        ),
                    )

                stdout_poses = _parse_vina_stdout(stdout)
                if stdout_poses:
                    best_delta_pct = _relative_error_pct(poses[0].affinity, stdout_poses[0].affinity)
                    if best_delta_pct > settings.docking_max_consistency_error_pct:
                        raise DockingFailed(
                            molecule_id=smiles_hash,
                            target_pdb_id=target_pdb_id,
                            detail=(
                                "Inconsistencia numérica de afinidad entre parser estructurado y stdout de Vina "
                                f"({best_delta_pct:.4f}% > {settings.docking_max_consistency_error_pct:.4f}%)."
                            ),
                        )

                vina_version, vina_random_seed = _parse_vina_metadata(stdout)
                if vina_random_seed is not None and vina_random_seed != effective_seed:
                    # La reproducibilidad de la corrida deja de estar garantizada:
                    # repetirla con la misma configuración puede dar otras poses.
                    scientific_warnings.append(aviso(
                        "SEMILLA_DISCREPANTE", Severidad.PRECAUCION,
                        "La semilla reportada por Vina difiere de la semilla configurada; "
                        "revisar reproducibilidad del entorno.",
                    ))

                poses_path = StoragePath.docking_poses_run(
                    smiles_hash, target_pdb_id, cache_fingerprint
                )
                log_path = StoragePath.docking_log_run(
                    smiles_hash, target_pdb_id, cache_fingerprint
                )

                # ── EL ARCHIVO ENTREGADO ES AQUEL DEL QUE SALIERON LAS POSES ─
                #
                # Para `sdf`, `pdbqt` y `vina_stdout` las poses se leyeron del
                # archivo de Meeko, y ese archivo se entrega TAL CUAL con
                # `write_file`, que copia bytes y no reescribe el texto: el
                # estado persistido de esos tres caminos es idéntico al de antes
                # de este cambio.
                #
                # Sólo el camino de Open Babel entrega otro contenido —el suyo—,
                # que es exactamente el defecto que esto corrige.
                #
                # La comprobación de coherencia no es decorativa: el defecto
                # original consistía precisamente en que la procedencia decía una
                # cosa y el archivo era otra, y nada lo notaba.
                if (parsing_source == "sdf_openbabel_cli") != (sdf_a_persistir is not None):
                    raise DockingFailed(
                        molecule_id=smiles_hash,
                        target_pdb_id=target_pdb_id,
                        detail=(
                            "Incoherencia interna: la procedencia declarada "
                            f"({parsing_source!r}) no corresponde con el archivo que se "
                            "iba a entregar. Se aborta antes de persistir un dossier que "
                            "cite unas poses y adjunte otras."
                        ),
                    )
                if sdf_a_persistir is not None:
                    await write_text(poses_path, sdf_a_persistir)
                else:
                    await write_file(output_sdf, poses_path)
                await write_text(log_path, output_log.read_text(encoding="utf-8"))

                # --- [NUEVO] Análisis de Hotspots Dinámico ---
                hotspots_hit = []
                if hotspots and poses and poses[0].pdbqt_block:
                    try:
                        hotspots_hit = _analyze_hotspot_interactions(
                            receptor_local,
                            poses[0].pdbqt_block,
                            hotspots
                        )
                        if hotspots_hit:
                            log.info("Hotspots hit detectados", hits=hotspots_hit)
                        else:
                            scientific_warnings.append(aviso(
                                "SIN_HOTSPOTS", Severidad.PRECAUCION,
                                "No se detectaron interacciones con los residuos críticos "
                                "(hotspots) del receptor.",
                            ))
                    except Exception as e:
                        log.error("Error analizando hotspots", error=str(e))
                        scientific_warnings.append(aviso(
                            "HOTSPOTS_ERROR", Severidad.CRITICA,
                            f"Error en análisis de hotspots: {e}",
                        ))

                result = DockingResult(
                    best_affinity=poses[0].affinity,
                    poses=poses,
                    poses_file_path=poses_path,
                    parsing_source=parsing_source,
                    conversor_estructural=conversor_estructural,
                    vina_version=vina_version,
                    vina_random_seed=vina_random_seed,
                    # Lo que de verdad se ejecutó. `effective_engine_identity`
                    # ya distingue el respaldo («vina_fallback_from_qvina2»).
                    engine_efectivo=effective_engine_identity,
                    exhaustiveness_efectiva=effective_exhaustiveness,
                    num_poses_solicitadas=effective_num_poses,
                    receptor_sha256=receptor_sha256,
                    receptor_path=receptor_snapshot_path,
                    scientific_warnings=scientific_warnings,
                    hotspots_hit=hotspots_hit,
                )
                await cache.set_docking_result(
                    smiles_hash,
                    target_pdb_id,
                    result.model_dump(),
                    cache_fingerprint,
                )

                log.info(
                    f"docking completado: smiles_hash={smiles_hash}, target={target_pdb_id}, best_affinity={result.best_affinity}, poses={len(result.poses)}"
                )
                return result
    finally:
        shutil.rmtree(job_temp_dir, ignore_errors=True)

def _analyze_hotspot_interactions(
    receptor_path: Path,
    ligand_pdbqt: str,
    hotspots: list[dict]
) -> list[str]:
    """
    Analiza si el ligando interactúa con los residuos críticos.
    Lógica: Distancia mínima < 4.0 Å entre cualquier átomo del ligando
    y cualquier átomo de la cadena lateral del residuo hotspot.
    """
    if not hotspots:
        return []

    # 1. Extraer coordenadas de los átomos del ligando
    ligand_coords = []
    for line in ligand_pdbqt.splitlines():
        if line.startswith(("ATOM", "HETATM")):
            try:
                x = float(line[30:38])
                y = float(line[38:46])
                z = float(line[46:54])
                ligand_coords.append((x, y, z))
            except (ValueError, IndexError):
                continue

    if not ligand_coords:
        return []

    # 2. Extraer coordenadas del receptor para los residuos hotspot
    # Formato esperado de hotspot['name']: "MET97", "ASP116", "A:TYR100"
    hotspot_names_full = {h["name"].upper() for h in hotspots}

    # Precomputar una versión sin cadena para fallbacks
    hotspot_names_no_chain = {}
    for h in hotspot_names_full:
        if ":" in h:
            hotspot_names_no_chain[h.split(":")[1]] = h
        else:
            hotspot_names_no_chain[h] = h

    receptor_atoms = {} # name -> list of coords

    with open(receptor_path, "r") as f:
        for line in f:
            if line.startswith(("ATOM", "HETATM")):
                res_name = line[17:20].strip()
                res_chain = line[21].strip() # Capturar cadena si existe
                res_seq = line[22:26].strip()

                full_res_no_chain = f"{res_name}{res_seq}"
                full_res_with_chain = f"{res_chain}:{res_name}{res_seq}" if res_chain else full_res_no_chain

                # Verificar si alguna de las formas está en hotspots
                matched_id = None
                if full_res_with_chain in hotspot_names_full:
                    matched_id = full_res_with_chain
                elif full_res_no_chain in hotspot_names_full:
                    matched_id = full_res_no_chain
                elif full_res_no_chain in hotspot_names_no_chain:
                    # Fallback: si el PDBQT perdió la cadena, usar la versión sin cadena
                    matched_id = hotspot_names_no_chain[full_res_no_chain]

                if matched_id:
                    try:
                        x = float(line[30:38])
                        y = float(line[38:46])
                        z = float(line[46:54])
                        if matched_id not in receptor_atoms:
                            receptor_atoms[matched_id] = []
                        receptor_atoms[matched_id].append((x, y, z))
                    except (ValueError, IndexError):
                        continue

    # 3. Calcular distancias mínimas
    hits = []
    # Aumentamos a 5.0 Å para capturar interacciones hidrofóbicas/apilamiento (stacking)
    # que son comunes en hotspots y tienen un rango mayor que los H-bonds.
    THRESHOLD_SQ = 5.0 * 5.0

    for res_name, res_coords in receptor_atoms.items():
        min_dist_sq = float('inf')
        for r_coord in res_coords:
            for l_coord in ligand_coords:
                d2 = (r_coord[0]-l_coord[0])**2 + (r_coord[1]-l_coord[1])**2 + (r_coord[2]-l_coord[2])**2
                if d2 < min_dist_sq:
                    min_dist_sq = d2

        min_dist = min_dist_sq**0.5
        log.info(f"Hotspot distance: {res_name} -> {min_dist:.2f} A")

        if min_dist_sq < THRESHOLD_SQ:
            hits.append(res_name)

    return hits
