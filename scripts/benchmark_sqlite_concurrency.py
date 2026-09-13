"""
scripts/benchmark_sqlite_concurrency.py

Benchmark de escritura SQLite bajo concurrencia — evidencia para el hallazgo
de auditoría F-15.

F-15: `backend/services/docking/queue_handler.py` define
`DESKTOP_MAX_CONCURRENCY = 4`, pero SQLite en modo WAL tiene UN solo
escritor; el código conserva retry de locks (`commit_with_retry`,
`flush_with_retry` en core/database.py).

Pregunta que responde este benchmark: ¿qué pasa REALMENTE con 1, 2 y 4
evaluaciones concurrentes escribiendo a la DB? Mide throughput, errores de
lock a nivel DBAPI, reintentos de lock (flush/commit), fallos por worker y
consistencia final de los datos.

SIMULACIÓN DEL PATRÓN DE ESCRITURA (fiel al flujo DESKTOP real):
    El runner DESKTOP (`_run_full_evaluation_async` en queue_handler.py)
    produce, por evaluación, esta secuencia de escrituras:
      1. INSERT molecule           → repository.create_or_get_molecule()
         (flush_with_retry interno, líneas ~577-580 de db/repository.py)
      2. commit_with_retry         → queue_handler línea ~500 (transacción corta)
      3. UPDATE status VALIDATED   → repository.set_molecule_status()
      4. commit_with_retry         → queue_handler línea ~578
      5. INSERT evaluation_result  → repository.upsert_evaluation_result()
         con `docking_poses` JSON (la app guarda las poses como JSON dentro
         de evaluation_results — NO existe tabla de poses separada) y scores
         JSON. El flush final de este método NO tiene retry (punto expuesto).
      6. UPDATE hotspots JSON sobre el MISMO target compartido (todos los
         workers tocan la misma fila → contención de escritor) + flush_with_retry
      7. UPDATE status EVALUATED   → repository.set_molecule_status()
      8. commit_with_retry final   → queue_handler línea ~1173

    Los workers usan la sesión real (`get_db_session`), el repositorio real
    (db/repository.py) y los helpers de retry reales de core/database.py.
    El engine es una réplica EXACTA de `_create_engine()` (NullPool, WAL,
    busy_timeout=60000, synchronous=NORMAL, foreign_keys=ON, serializers
    JSON) apuntando a una DB TEMPORAL — NUNCA toca moldesign_local.db.

USO:
    python scripts/benchmark_sqlite_concurrency.py
    python scripts/benchmark_sqlite_concurrency.py --concurrencies 1,2,4 \
        --evaluations-per-round 8 --poses-per-eval 8 --round-timeout 300 \
        --keep-db

EXIT CODES:
    0 = todas las rondas completaron sin fallos y la consistencia es íntegra
    1 = fallos de worker o corrupción de datos detectada
    2 = alguna ronda agotó su timeout (vuelve a correr con menos evaluaciones)
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _SCRIPT_DIR.parent / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

# ── Instrumentación de retries SIN tocar producción ───────────────────────────
# Los helpers reales de core/database.py loguean "db_locked_retry_flush" /
# "db_locked_retry_commit" vía structlog. Se configura structlog ANTES de
# importar los módulos del backend con un processor que cuenta esos eventos.
# El conteo es pasivo: no modifica el comportamiento de los helpers.

_lock_retry_events: list[tuple[str, int]] = []  # ("flush"|"commit", attempt)
DBAPI_LOCK_ERRORS: dict[str, int] = {"count": 0}  # OperationalError de lock a nivel DBAPI

import structlog


def _count_retry_processor(_logger, _method_name, event_dict):
    ev = event_dict.get("event")
    if ev == "db_locked_retry_flush":
        _lock_retry_events.append(("flush", event_dict.get("attempt", 0)))
    elif ev == "db_locked_retry_commit":
        _lock_retry_events.append(("commit", event_dict.get("attempt", 0)))
    return event_dict


structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        _count_retry_processor,
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
)

from sqlalchemy import event as sa_event  # noqa: E402
from sqlalchemy import select, text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402

from core.database import (  # noqa: E402
    _json_deserializer,
    _json_serializer,
    commit_with_retry,
    flush_with_retry,
    get_db_session,
    get_session_factory,
    set_engine,
)
from core.models import (  # noqa: E402
    Base,
    DockingPose,
    DockingResult,
    EvaluationResultORM,
    MoleculeORM,
    MoleculeStatus,
    PhysicochemicalProperties,
    TargetORM,
    UserORM,
)
from db.repository import Repository  # noqa: E402

# ── Constantes del benchmark ──────────────────────────────────────────────────

BENCH_TARGET_PDB = "BENCH1"
BENCH_USER_ID = uuid.UUID("00000000-0000-4000-8000-00000000f015")
BASE_HOTSPOTS = [
    {"name": "RES101", "importance": 1.0},
    {"name": "RES116", "importance": 0.9},
    {"name": "RES190", "importance": 0.8},
    {"name": "RES203", "importance": 0.7},
    {"name": "RES211", "importance": 0.6},
    {"name": "RES286", "importance": 0.5},
    {"name": "RES361", "importance": 0.4},
]


# ── Engine réplica de _create_engine() ────────────────────────────────────────


def build_benchmark_engine(db_path: Path) -> AsyncEngine:
    """
    Réplica fiel de `_create_engine()` de core/database.py (F-15):
    mismos connect_args, NullPool, pragmas WAL y serializers JSON.
    La única diferencia: el archivo .db es TEMPORAL (nunca el real).
    """
    _connect_args = {
        "check_same_thread": False,
        "timeout": 60,
    }

    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path}",
        echo=False,
        connect_args=_connect_args,
        poolclass=NullPool,
        json_serializer=_json_serializer,
        json_deserializer=_json_deserializer,
    )

    @sa_event.listens_for(engine.sync_engine, "connect")
    def _setup_sqlite_pragmas(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=60000")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    @sa_event.listens_for(engine.sync_engine, "handle_error")
    def _on_handle_error(context):
        # Cada OperationalError de lock que ESCAPA del driver se cuenta aquí.
        # Es la medida independiente de "errores de lock" (los helpers reales
        # pueden reintentarlos, pero el evento DBAPI ocurrió igualmente).
        if "database is locked" in str(context.original_exception):
            DBAPI_LOCK_ERRORS["count"] += 1

    return engine


async def setup_benchmark_env(db_path: Path) -> AsyncEngine:
    """
    Crea el engine temporal, lo inyecta vía set_engine() (mismo patrón que
    los tests) y siembra UN target sintético compartido + UN usuario.
    """
    engine = build_benchmark_engine(db_path)
    set_engine(engine)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with get_session_factory()() as db:
        user = UserORM(
            id=BENCH_USER_ID,
            email="bench@moldesign.local",
            username="bench_user",
            is_active=True,
        )
        target = TargetORM(
            pdb_id=BENCH_TARGET_PDB,
            name="Benchmark Target F-15",
            chain="A",
            description="Target sintético compartido por todos los workers del benchmark.",
            grid_center_x=0.0,
            grid_center_y=0.0,
            grid_center_z=0.0,
            grid_size_x=25.0,
            grid_size_y=25.0,
            grid_size_z=25.0,
            hotspots=[dict(h) for h in BASE_HOTSPOTS],
        )
        db.add_all([user, target])
        await db.commit()
    return engine


# ── Datos sintéticos (misma forma que los reales) ─────────────────────────────


def make_unique_smiles(eval_index: int) -> str:
    """Alcano de longitud creciente: SMILES válido y único por evaluación."""
    return "C" * (5 + eval_index)


def make_properties() -> PhysicochemicalProperties:
    """Propiedades sintéticas que pasan el validador de consistencia Lipinski."""
    return PhysicochemicalProperties(
        molecular_weight=350.0,
        log_p=2.5,
        tpsa=60.0,
        hbd=2,
        hba=4,
        rotatable_bonds=5,
        heavy_atom_count=25,
        ring_count=2,
        qed=0.7,
        sa_score=3.5,
        sa_reasons=[],
        lipinski_pass=True,
        veber_pass=True,
    )


def make_docking_result(poses_per_eval: int) -> DockingResult:
    """DockingResult sintético con N poses (la app las guarda como JSON)."""
    return DockingResult(
        best_affinity=-8.0,
        poses=[
            DockingPose(
                rank=i,
                affinity=-8.0 + (i - 1) * 0.2,
                rmsd_lb=(i - 1) * 0.1,
                rmsd_ub=(i - 1) * 0.1 + 0.5,
            )
            for i in range(1, poses_per_eval + 1)
        ],
        parsing_source="vina_stdout",
        vina_version="1.2.5",
        vina_random_seed=42,
        scientific_warnings=[],
        hotspots_hit=["RES101"],
    )


def make_scores() -> dict:
    """Scores sintéticos con la forma del breakdown real del pipeline."""
    return {
        "affinity_score": 82.0,
        "adme_score": 76.0,
        "druglikeness_score": 71.0,
        "total_score": 77.5,
        "gnn_score": 0.52,
        "specificity_score": 64.0,
        "ligand_efficiency": 0.35,
        "lipophilic_efficiency": 4.2,
        "affinity_threshold": -7.5,
        "affinity_multiplier": 1.0,
        "specificity_multiplier": 1.0,
        "gnn_factor": 1.0,
        "sa_factor": 1.0,
        "blood_factor": 1.0,
        "target_family": "bench",
        "stacking_vina_weight": 0.4,
        "stacking_xgb_weight": 0.3,
        "stacking_gnn_weight": 0.3,
    }


async def update_shared_target_hotspots(db, eval_index: int) -> None:
    """
    UPDATE de la columna JSON `hotspots` sobre el MISMO target compartido.
    Es el punto de contención de escritor por excelencia: N sesiones
    concurrentes reescriben la misma fila de `targets`.
    """
    stmt = select(TargetORM).where(TargetORM.pdb_id == BENCH_TARGET_PDB)
    target = (await db.execute(stmt)).scalar_one()
    base = list(target.hotspots or [])[:6]
    target.hotspots = [*base, {"name": f"EV{eval_index}", "importance": 0.5}]
    await flush_with_retry(db)


# ── Worker: UNA evaluación (patrón de escritura real) ─────────────────────────


@dataclass
class WorkerStats:
    index: int
    smiles: str
    molecule_id: uuid.UUID | None
    ok: bool
    error: str | None
    elapsed_s: float


async def run_evaluation_worker(
    index: int,
    poses_per_eval: int,
    sem: asyncio.Semaphore,
) -> WorkerStats:
    """
    Simula UNA evaluación DESKTOP con el patrón de escritura real.
    Usa get_db_session + Repository + helpers de retry REALES.
    """
    t0 = time.perf_counter()
    smiles = make_unique_smiles(index)
    molecule_id: uuid.UUID | None = None
    error: str | None = None
    try:
        async with sem:
            async with get_db_session() as db:
                repository = Repository(db)

                # 1. INSERT molecule (SELECT target + SELECT dedup + INSERT)
                molecule = await repository.create_or_get_molecule(
                    smiles=smiles,
                    target_pdb_id=BENCH_TARGET_PDB,
                    name=f"bench-eval-{index}",
                    user_id=BENCH_USER_ID,
                )
                molecule_id = molecule.id
                await commit_with_retry(db)  # queue_handler ~500

                # 2. UPDATE status VALIDATED
                await repository.set_molecule_status(molecule.id, MoleculeStatus.VALIDATED)
                await commit_with_retry(db)  # queue_handler ~578

                # 3. INSERT evaluation_result (poses + scores JSON; flush SIN retry)
                await repository.upsert_evaluation_result(
                    molecule_id=molecule.id,
                    properties=make_properties(),
                    docking=make_docking_result(poses_per_eval),
                    scores=make_scores(),
                    is_control=False,
                    task_id=f"bench-task-{index}",
                )

                # 4. UPDATE hotspots JSON sobre el target compartido
                await update_shared_target_hotspots(db, index)

                # 5. UPDATE status EVALUATED + commit final
                await repository.set_molecule_status(molecule.id, MoleculeStatus.EVALUATED)
                await commit_with_retry(db)  # queue_handler ~1173
        ok = True
    except Exception as exc:  # noqa: BLE001 — el worker reporta, no revienta
        error = f"{type(exc).__name__}: {str(exc)[:200]}"
        ok = False
    return WorkerStats(
        index=index,
        smiles=smiles,
        molecule_id=molecule_id,
        ok=ok,
        error=error,
        elapsed_s=time.perf_counter() - t0,
    )


# ── Ronda de benchmark ────────────────────────────────────────────────────────


@dataclass
class RoundStats:
    concurrency: int
    evals: int
    wall_s: float
    timed_out: bool
    workers: list[WorkerStats] = field(default_factory=list)
    retry_flush: int = 0
    retry_commit: int = 0
    dbapi_lock_errors: int = 0

    @property
    def failures(self) -> int:
        return sum(1 for w in self.workers if not w.ok)

    @property
    def completed(self) -> int:
        return len(self.workers)

    @property
    def throughput_evals_min(self) -> float:
        if self.wall_s <= 0:
            return 0.0
        return self.completed / (self.wall_s / 60.0)

    @property
    def avg_latency_s(self) -> float:
        if not self.workers:
            return 0.0
        return sum(w.elapsed_s for w in self.workers) / len(self.workers)

    @property
    def max_latency_s(self) -> float:
        if not self.workers:
            return 0.0
        return max(w.elapsed_s for w in self.workers)


async def run_round(
    concurrency: int,
    evals: int,
    poses_per_eval: int,
    timeout_s: float,
    base_index: int = 0,
) -> RoundStats:
    """
    Lanza `evals` workers (llegada simultánea, como un screening masivo)
    limitados por un semáforo de `concurrency`. Mide todo por ronda.
    """
    _lock_retry_events.clear()
    DBAPI_LOCK_ERRORS["count"] = 0

    sem = asyncio.Semaphore(concurrency)
    t0 = time.perf_counter()
    tasks = [
        asyncio.create_task(
            run_evaluation_worker(base_index + i, poses_per_eval, sem)
        )
        for i in range(evals)
    ]

    workers: list[WorkerStats] = []
    timed_out = False
    try:
        workers = await asyncio.wait_for(asyncio.gather(*tasks), timeout=timeout_s)
    except TimeoutError:
        timed_out = True
        for t in tasks:
            t.cancel()
        for t in tasks:
            try:
                workers.append(t.result())
            except Exception:
                pass

    retry_flush = sum(1 for kind, _ in _lock_retry_events if kind == "flush")
    retry_commit = sum(1 for kind, _ in _lock_retry_events if kind == "commit")
    return RoundStats(
        concurrency=concurrency,
        evals=evals,
        wall_s=time.perf_counter() - t0,
        timed_out=timed_out,
        workers=workers,
        retry_flush=retry_flush,
        retry_commit=retry_commit,
        dbapi_lock_errors=DBAPI_LOCK_ERRORS["count"],
    )


# ── Verificación de consistencia ──────────────────────────────────────────────


@dataclass
class ConsistencyReport:
    expected_molecules: int = 0
    molecules_ok: int = 0
    molecules_missing: int = 0
    status_bad: int = 0
    dupes: int = 0
    missing_results: int = 0
    poses_ok: int = 0
    poses_bad: int = 0
    integrity: str = ""
    errors: list[str] = field(default_factory=list)

    @property
    def consistent(self) -> bool:
        if self.integrity != "ok":
            return False
        if self.expected_molecules == 0:
            return False
        return (
            self.molecules_missing == 0
            and self.status_bad == 0
            and self.dupes == 0
            and self.missing_results == 0
            and self.poses_bad == 0
            and self.molecules_ok == self.expected_molecules
        )


async def verify_consistency(
    engine: AsyncEngine,
    workers: list[WorkerStats],
    poses_per_eval: int,
) -> ConsistencyReport:
    """
    Invariantes verificadas sobre los workers EXITOSOS:
      - la molécula existe y su status es EVALUATED
      - exactamente UNA fila de evaluation_results por molécula (sin dupes)
      - docking_poses JSON con la cantidad exacta de poses esperada
    Además: PRAGMA integrity_check de toda la DB.
    """
    rep = ConsistencyReport()
    ok_ids = [w.molecule_id for w in workers if w.ok and w.molecule_id is not None]
    rep.expected_molecules = len(ok_ids)
    if rep.expected_molecules == 0:
        rep.errors.append("no hay moléculas de workers exitosos que verificar")
        return rep

    async with get_session_factory()() as db:
        for mid in ok_ids:
            mol = (
                await db.execute(select(MoleculeORM).where(MoleculeORM.id == mid))
            ).scalar_one_or_none()
            if mol is None:
                rep.molecules_missing += 1
                continue
            if mol.status != MoleculeStatus.EVALUATED:
                rep.status_bad += 1
            results = (
                await db.execute(
                    select(EvaluationResultORM).where(
                        EvaluationResultORM.molecule_id == mid
                    )
                )
            ).scalars().all()
            if len(results) == 1:
                rep.molecules_ok += 1
                poses = results[0].docking_poses
                if isinstance(poses, list) and len(poses) == poses_per_eval:
                    rep.poses_ok += 1
                else:
                    rep.poses_bad += 1
            else:
                if not results:
                    rep.missing_results += 1
                else:
                    rep.dupes += 1

        # Dupes globales (cualquier molecule_id con >1 resultado)
        dupes_global = (
            await db.execute(
                text(
                    "SELECT molecule_id FROM evaluation_results "
                    "GROUP BY molecule_id HAVING COUNT(*) > 1"
                )
            )
        ).scalars().all()
        rep.dupes += len(dupes_global)

    async with engine.connect() as conn:
        rep.integrity = str((await conn.execute(text("PRAGMA integrity_check"))).scalar())

    if rep.integrity != "ok":
        rep.errors.append(f"integrity_check != ok: {rep.integrity}")
    return rep


# ── Main ──────────────────────────────────────────────────────────────────────


def _print_table(results: list[RoundStats]) -> None:
    header = (
        f"{'Ronda':>5} {'Concur.':>7} {'Evals':>6} {'Tiempo(s)':>10} "
        f"{'Eval/min':>9} {'LockErr':>8} {'RetryFl':>8} {'RetryCo':>8} "
        f"{'Fallos':>7} {'LatProm(s)':>10} {'LatMax(s)':>10}"
    )
    print("\n" + "=" * len(header))
    print(header)
    print("-" * len(header))
    for i, r in enumerate(results, start=1):
        print(
            f"{i:>5} {r.concurrency:>7} {r.completed:>6}/{r.evals:<3} "
            f"{r.wall_s:>10.2f} {r.throughput_evals_min:>9.1f} "
            f"{r.dbapi_lock_errors:>8} {r.retry_flush:>8} {r.retry_commit:>8} "
            f"{r.failures:>7} {r.avg_latency_s:>10.2f} {r.max_latency_s:>10.2f}"
        )
        if r.timed_out:
            print(f"     !!! ronda con TIMEOUT (limite {r.wall_s:.0f}s) — datos parciales")
    print("=" * len(header))


def _print_failures(results: list[RoundStats]) -> None:
    for r in results:
        for w in r.workers:
            if not w.ok:
                print(f"  [FALLO] concurrencia={r.concurrency} eval={w.index}: {w.error}")


async def _main_async(args: argparse.Namespace) -> int:
    concurrencies = [int(c.strip()) for c in args.concurrencies.split(",") if c.strip()]
    print(f"Benchmark F-15 — patrón de escritura SQLite del pipeline DESKTOP")
    print(f"  evaluaciones por ronda: {args.evals}")
    print(f"  poses JSON por evaluación: {args.poses_per_eval}")
    print(f"  concurrencias: {concurrencies}")

    keep_db = args.keep_db
    tmp_ctx = None
    if keep_db:
        tmp_dir = tempfile.mkdtemp(prefix="moldesign_bench_f15_")
        db_path = Path(tmp_dir) / "benchmark.db"
        print(f"  DB temporal (--keep-db): {db_path}")
    else:
        tmp_ctx = tempfile.TemporaryDirectory(prefix="moldesign_bench_f15_")
        db_path = Path(tmp_ctx.name) / "benchmark.db"
        print(f"  DB temporal (se elimina al final): {db_path}")

    engine: AsyncEngine | None = None
    results: list[RoundStats] = []
    reports: list[ConsistencyReport] = []
    try:
        engine = await setup_benchmark_env(db_path)
        base_index = 0
        for conc in concurrencies:
            print(f"\n--- Ronda con concurrencia {conc} ---")
            stats = await run_round(
                concurrency=conc,
                evals=args.evals,
                poses_per_eval=args.poses_per_eval,
                timeout_s=args.round_timeout,
                base_index=base_index,
            )
            base_index += args.evals
            results.append(stats)
            report = await verify_consistency(engine, stats.workers, args.poses_per_eval)
            reports.append(report)
            print(
                f"  ronda {conc}: {stats.completed}/{stats.evals} evals, "
                f"{stats.wall_s:.2f}s, fallos={stats.failures}, "
                f"lock_errors={stats.dbapi_lock_errors}, "
                f"retries(flush/commit)={stats.retry_flush}/{stats.retry_commit}, "
                f"consistencia={'OK' if report.consistent else 'FALLA'}"
            )
    finally:
        if engine is not None:
            await engine.dispose()
        if tmp_ctx is not None:
            tmp_ctx.cleanup()

    _print_table(results)
    if any(r.failures for r in results):
        print("\nDetalle de fallos:")
        _print_failures(results)

    print("\nVerificación de consistencia (por ronda, acumulada en la misma DB):")
    any_timeout = any(r.timed_out for r in results)
    any_fail = any(r.failures > 0 for r in results)
    any_corrupt = any(not rep.consistent for rep in reports)
    for r, rep in zip(results, reports):
        verdict = "OK" if rep.consistent else "FALLA"
        print(
            f"  concurrencia={r.concurrency}: molecules_ok={rep.molecules_ok}/"
            f"{rep.expected_molecules}, status_bad={rep.status_bad}, "
            f"dupes={rep.dupes}, sin_resultado={rep.missing_results}, "
            f"poses_bad={rep.poses_bad}, integrity_check={rep.integrity!r} -> {verdict}"
        )

    if any_timeout:
        print("\nRESULTADO: TIMEOUT en al menos una ronda → re-correr con menos evaluaciones.")
        return 2
    if any_fail or any_corrupt:
        print("\nRESULTADO: FALLO — hay errores de worker o corrupción de datos.")
        return 1
    print("\nRESULTADO: OK — todas las rondas completaron sin fallos ni corrupción.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Benchmark de concurrencia SQLite (F-15)")
    parser.add_argument(
        "--concurrencies",
        default="1,2,4",
        help="lista de concurrencias a medir (default: 1,2,4)",
    )
    parser.add_argument(
        "--evaluations-per-round",
        "--workers-per-round",
        dest="evals",
        type=int,
        default=8,
        help="evaluaciones por ronda (default: 8)",
    )
    parser.add_argument(
        "--poses-per-eval",
        type=int,
        default=8,
        help="poses JSON insertadas por evaluación, rango app 5-10 (default: 8)",
    )
    parser.add_argument(
        "--round-timeout",
        type=float,
        default=300.0,
        help="timeout por ronda en segundos (default: 300)",
    )
    parser.add_argument(
        "--keep-db",
        action="store_true",
        help="conserva la DB temporal para inspección (no la borra)",
    )
    args = parser.parse_args(argv)
    if args.evals <= 0:
        parser.error("--evaluations-per-round debe ser >= 1")
    if not (1 <= args.poses_per_eval <= 50):
        parser.error("--poses-per-eval debe estar entre 1 y 50")
    return asyncio.run(_main_async(args))


if __name__ == "__main__":
    sys.exit(main())
