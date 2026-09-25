"""PROV-018: todas las puertas del backend comparten un límite Vina."""
import asyncio

import pytest

from services.docking.vina_service import VINA_PROCESS_LIMIT, vina_process_slot


@pytest.mark.asyncio
async def test_seis_envios_y_cancelacion_no_superan_limite():
    active = maximum = 0

    async def fake_vina():
        nonlocal active, maximum
        async with vina_process_slot():
            active += 1
            maximum = max(maximum, active)
            try:
                await asyncio.sleep(0.03)
            finally:
                active -= 1

    tasks = [asyncio.create_task(fake_vina()) for _ in range(6)]
    await asyncio.sleep(0.005)
    tasks[-1].cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    assert maximum <= VINA_PROCESS_LIMIT
    assert active == 0
    await asyncio.wait_for(fake_vina(), timeout=1)


@pytest.mark.asyncio
async def test_otro_proceso_bloquea_vina_hasta_liberar_el_candado():
    import sys
    import time
    from services.docking.vina_service import _vina_lock_path

    lock_path = str(_vina_lock_path())
    child = await asyncio.create_subprocess_exec(
        sys.executable, "-c",
        "import sys,time; from filelock import FileLock; "
        "lock=FileLock(sys.argv[1]); lock.acquire(); "
        "print('READY',flush=True); time.sleep(0.5); lock.release()",
        lock_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        assert (await asyncio.wait_for(child.stdout.readline(), timeout=5)).strip() == b"READY"
        start = time.monotonic()
        async with vina_process_slot():
            elapsed = time.monotonic() - start
        assert elapsed >= 0.3
        assert await asyncio.wait_for(child.wait(), timeout=5) == 0
    finally:
        if child.returncode is None:
            child.kill()
            await child.wait()
