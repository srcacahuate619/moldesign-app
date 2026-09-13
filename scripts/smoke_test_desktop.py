"""
scripts/smoke_test_desktop.py

Smoke test E2E del backend DESKTOP — SIN docking real (audit línea ~185).

Prueba el camino completo de evaluación con infraestructura REAL y AISLADA:
  1. SQLite temporal + local_data_dir temporal (NUNCA los reales).
  2. `submit_evaluation_job` REAL de services.docking.queue_handler, con el
     pipeline científico falso — el mismo patrón de monkeypatch que
     tests/test_queue_handler_desktop.py: nunca se lanza Vina ni MM-GBSA.
  3. El pipeline falso SÍ ejercita el código REAL de persistencia
     (db/repository.py sobre SQLite) y de storage (utils/local_storage.py).
  4. Polling de `get_job_status` REAL hasta estado terminal (timeout 30s).
  5. Verifica SUCCESS + resultado persistido (nueva conexión SQLite, no la
     sesión en memoria) + artefacto de poses legible vía local_storage.
  6. Imprime línea resumen PASS/FAIL. Exit 0/1.

Uso:
    python scripts/smoke_test_desktop.py

No es un test pytest: los fakes se inyectan por atributo directo sobre el
módulo real (equivalente a monkeypatch.setattr(qh, ...)).
"""
from __future__ import annotations

import asyncio
import sqlite3
import sys
import tempfile
import time
import traceback
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "backend"))

# ── Contrato del smoke test ────────────────────────────────────────────────────

ASPIRIN = "CC(=O)Oc1ccccc1C(=O)O"  # aspirina, SMILES de referencia
TARGET_PDB_ID = "7E2Y"             # target default (ensure_default_target real)
POLL_TIMEOUT_S = 30.0
EXPECTED_TOTAL_SCORE = 88.0
EXPECTED_AFFINITY_KCAL = -9.4
POSES_CONTENT = (
    "SMOKE-TEST-POSES\n"
    "  SMOKE\n"
    "  1  0  0  0  0  0  0  0  0  0999 V2000\n"
    "    0.0000    0.0000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0\n"
    "M  END\n"
    "$$$$\n"
)

# Importaciones del backend REAL (el smoke test no reemplaza estos módulos).
import services.docking.queue_handler as qh
import utils.local_storage as ls
from chem.properties import calculate_properties
from core.database import commit_with_retry, get_db_session, set_engine
from core.models import Base, DockingPose, DockingResult, MoleculeStatus
from db.repository import Repository
from utils.file_handlers import StoragePath


# ── Pipeline científico falso (solo se finge docking/scoring) ─────────────────

async def _fake_pipeline(**kwargs) -> dict:
    """Stub determinista de _run_full_evaluation_async.

    Espeja el fake de tests/test_queue_handler_desktop.py, pero además
    ejercita la persistencia REAL (Repository + SQLite) y el storage REAL
    (utils.local_storage) para probar el camino E2E completo sin Vina.
    """
    task_id = kwargs["task_id"]
    smiles = kwargs["smiles"]
    target_pdb_id = kwargs["target_pdb_id"]

    async with get_db_session() as db:
        repository = Repository(db)
        target = await repository.get_target_by_pdb_id(target_pdb_id)
        if target is None:
            target = await repository.ensure_default_target()
        molecule = await repository.create_or_get_molecule(
            smiles=smiles,
            target_pdb_id=target.pdb_id,
            name=kwargs.get("molecule_name"),
        )
        await commit_with_retry(db)

        properties = calculate_properties(smiles, run_admet_ai=False)
        poses_path = StoragePath.docking_poses(str(molecule.smiles_hash), target.pdb_id)

        await repository.set_molecule_status(molecule.id, MoleculeStatus.VALIDATED)
        await repository.upsert_evaluation_result(
            molecule_id=molecule.id,
            properties=properties,
            docking=DockingResult(
                best_affinity=EXPECTED_AFFINITY_KCAL,
                poses=[DockingPose(rank=1, affinity=EXPECTED_AFFINITY_KCAL, rmsd_lb=0.5, rmsd_ub=0.8)],
                poses_file_path=poses_path,
                parsing_source="sdf",
                vina_version="smoke-fake-1.0",
                vina_random_seed=42,
                scientific_warnings=["SMOKE: docking simulado, sin Vina real"],
            ),
            scores={"total_score": EXPECTED_TOTAL_SCORE, "affinity_score": 91.0},
            # El schema desktop conserva ``celery_task_id`` sólo como alias de
            # migración. El contrato de escritura vigente es ``task_id``.
            task_id=task_id,
        )
        await repository.set_molecule_status(molecule.id, MoleculeStatus.EVALUATED)
        await commit_with_retry(db)

        molecule_id = str(molecule.id)
        smiles_hash = str(molecule.smiles_hash)

    # Artefacto de poses vía local_storage REAL (contrato lógico poses/{hash}/{pdb}/poses.sdf)
    await ls.write_text(poses_path, POSES_CONTENT)

    return {
        "task_id": task_id,
        "molecule_id": molecule_id,
        "smiles_hash": smiles_hash,
        "target_pdb_id": target_pdb_id,
        "total_score": EXPECTED_TOTAL_SCORE,
        "best_affinity": EXPECTED_AFFINITY_KCAL,
        "evaluation_result_id": None,
        "poses_file_path": poses_path,
    }


# ── Verificación de persistencia cross-connection ─────────────────────────────

def _query_fresh_connection(db_path: Path) -> tuple[int, int, str | None, str | None]:
    """Abre una conexión sqlite3 NUEVA (no la sesión del pipeline) para probar
    que el resultado quedó persistido en disco.

    Retorna (n_molecules, n_evaluations, smiles_hash, target_pdb_id_persistido).
    El pdb_id persistido es el que el pipeline REAL eligió (ensure_default_target
    devuelve 6X1A, no 7E2Y, cuando no hay ingesta) — las poses deben validarse
    contra ESE id, no contra el solicitado."""
    conn = sqlite3.connect(str(db_path))
    try:
        n_molecules = conn.execute("SELECT COUNT(*) FROM molecules").fetchone()[0]
        n_evaluations = conn.execute("SELECT COUNT(*) FROM evaluation_results").fetchone()[0]
        row = conn.execute(
            "SELECT m.smiles_hash, t.pdb_id "
            "FROM molecules m JOIN targets t ON m.target_id = t.id "
            "WHERE m.smiles = ? LIMIT 1",
            (ASPIRIN,),
        ).fetchone()
        return n_molecules, n_evaluations, (row[0] if row else None), (row[1] if row else None)
    finally:
        conn.close()


# ── Main ──────────────────────────────────────────────────────────────────────

async def _main(tmp_root: Path) -> int:
    from sqlalchemy.ext.asyncio import create_async_engine

    data_dir = tmp_root / "data"
    vina_dir = tmp_root / "vina"
    db_path = tmp_root / "moldesign_local.db"
    vina_dir.mkdir(parents=True, exist_ok=True)

    # 1. Aislar storage: local_data_dir y vina_temp_dir apuntan a tmp (nunca ~/MolDesign)
    ls.settings.local_data_dir = str(data_dir)
    ls.settings.vina_temp_dir = str(vina_dir)

    # 2. SQLite temporal: archivo real en tmp, engine inyectado ANTES de cualquier uso
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    set_engine(engine)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 3. Estado desktop limpio + fakes científicos (patrón de test_queue_handler_desktop.py)
    with qh._desktop_lock:
        qh._desktop_jobs.clear()
    qh._run_full_evaluation_async = _fake_pipeline
    try:
        import services.ai.memory_store as memory_store
        memory_store.store_evaluation = lambda **kwargs: None  # aislar sqlite de IA (~/MolDesign)
    except ImportError:
        pass  # el wrapper ya degrada con except ImportError

    # 4. Submit REAL del SMILES de referencia
    task = qh.submit_evaluation_job(
        smiles=ASPIRIN,
        target_pdb_id=TARGET_PDB_ID,
        molecule_name="aspirina-smoke",
    )
    print(f"Job enviado: {task.id}")

    # 5. Polling de get_job_status REAL con timeout acotado
    deadline = time.monotonic() + POLL_TIMEOUT_S
    status = None
    while True:
        status = await qh.get_job_status(task.id)
        if status.status in ("SUCCESS", "FAILURE"):
            break
        if time.monotonic() > deadline:
            print(f"FAIL: timeout tras {POLL_TIMEOUT_S}s esperando estado terminal "
                  f"(último: {status.status})")
            return 1
        await asyncio.sleep(0.05)

    # 6. Asserts del contrato E2E
    failures: list[str] = []
    if status.status != "SUCCESS":
        failures.append(f"estado esperado SUCCESS, obtenido {status.status} (error={status.error})")
    if status.progress != 100:
        failures.append(f"progress esperado 100, obtenido {status.progress}")
    if status.error is not None:
        failures.append(f"error inesperado: {status.error}")
    if status.result is None:
        failures.append("result es None (no se recuperó de DB)")
    elif status.result.total_score != EXPECTED_TOTAL_SCORE:
        failures.append(f"total_score esperado {EXPECTED_TOTAL_SCORE}, obtenido {status.result.total_score}")

    # 7. Persistencia: nueva conexión sqlite3 al archivo (no la sesión del pipeline)
    try:
        n_molecules, n_evaluations, smiles_hash, persisted_pdb_id = _query_fresh_connection(db_path)
        if n_molecules != 1:
            failures.append(f"molecules persistidas esperadas 1, obtenidas {n_molecules}")
        if n_evaluations != 1:
            failures.append(f"evaluation_results persistidas esperadas 1, obtenidas {n_evaluations}")
        if smiles_hash is None or persisted_pdb_id is None:
            failures.append("no se encontró la molécula de aspirina en el SQLite temporal")
    except Exception as exc:
        failures.append(f"verificación de persistencia falló: {exc}")

    # 8. Poses legibles vía local_storage (contrato poses/{hash}/{pdb}/poses.sdf)
    #    contra el pdb_id PERSISTIDO (el que eligió el pipeline real).
    if smiles_hash and persisted_pdb_id:
        poses_obj = StoragePath.docking_poses(smiles_hash, persisted_pdb_id)
        try:
            content = await ls.read_text(poses_obj)
            if "SMOKE-TEST-POSES" not in content:
                failures.append("el contenido de poses.sdf no contiene el marcador SMOKE-TEST-POSES")
            on_disk = Path(ls.settings.local_data_dir) / poses_obj
            if not on_disk.is_file():
                failures.append(f"poses.sdf no existe en disco: {on_disk}")
        except Exception as exc:
            failures.append(f"lectura de poses vía local_storage falló: {exc}")

    await engine.dispose()

    if failures:
        print("FAIL: " + " | ".join(failures))
        return 1

    print(
        f"PASS: submit->poll->persist OK | job={task.id} status=SUCCESS "
        f"total_score={status.result.total_score} | target_persistido={persisted_pdb_id} "
        f"molecules={n_molecules} evaluation_results={n_evaluations} | poses legibles en "
        f"{StoragePath.docking_poses(smiles_hash, persisted_pdb_id)}"
    )
    return 0


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="moldesign_smoke_") as tmp:
        tmp_root = Path(tmp)
        try:
            return asyncio.run(_main(tmp_root))
        except Exception:
            print("FAIL: excepción no controlada:")
            traceback.print_exc()
            return 1


if __name__ == "__main__":
    raise SystemExit(main())
