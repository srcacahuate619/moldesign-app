"""
Tests de regresión ligera del benchmark de concurrencia SQLite (F-15).

Valida — contra una DB temporal — que el patrón de escritura simulado por
scripts/benchmark_sqlite_concurrency.py NO produce fallos ni corrupción de
datos con 2 evaluaciones concurrentes (2 workers).

Duración objetivo: <60 s. Nunca toca moldesign_local.db: usa tmp_path con
el engine réplica del script (mismos pragmas/helpers de producción).
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_BENCH_SCRIPT = (
    Path(__file__).resolve().parents[2] / "scripts" / "benchmark_sqlite_concurrency.py"
)


def _load_benchmark():
    """Carga el script del benchmark como módulo (scripts/ no es paquete)."""
    spec = importlib.util.spec_from_file_location(
        "benchmark_sqlite_concurrency", str(_BENCH_SCRIPT)
    )
    assert spec is not None
    mod = importlib.util.module_from_spec(spec)
    # Registrar en sys.modules ANTES de exec: las dataclasses del script
    # resuelven su __module__ contra sys.modules durante la definición.
    sys.modules["benchmark_sqlite_concurrency"] = mod
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


_bench = _load_benchmark()


@pytest.mark.asyncio
async def test_dos_evaluaciones_concurrentes_sin_fallos_y_consistentes(tmp_path):
    """
    F-15: 2 workers concurrentes → 0 fallos + invariante de consistencia
    (cada molécula EVALUATED con exactamente 1 resultado y sus poses).
    """
    engine = await _bench.setup_benchmark_env(tmp_path / "bench_concurrency_test.db")
    try:
        stats = await _bench.run_round(concurrency=2, evals=2, poses_per_eval=5, timeout_s=60)

        assert not stats.timed_out, "la ronda agotó el timeout de 60 s"
        assert stats.failures == 0, f"fallos inesperados: {stats.failures}"
        assert stats.completed == 2, f"se esperaban 2 workers, hubo {stats.completed}"

        report = await _bench.verify_consistency(engine, stats.workers, poses_per_eval=5)
        assert report.consistent, report.errors
        assert report.expected_molecules == 2
        assert report.poses_ok == 2
    finally:
        await engine.dispose()
