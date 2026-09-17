"""Exclusión por ligando para proyecciones y artefactos compartidos.

Distintos ligandos siguen ejecutándose en paralelo. No modifica la química.
Los locks son cross-loop; la espera es cancelable sin hilos bloqueados.
"""
from __future__ import annotations

import asyncio
import functools
import inspect
import threading

_guard = threading.Lock()
_locks: dict[str, list] = {}


def serialize_ligand_evaluation(*, delegate_pro=False):
    def decorate(fn):
        signature = inspect.signature(fn)

        @functools.wraps(fn)
        async def wrapped(*args, **kwargs):
            params = signature.bind(*args, **kwargs).arguments
            if delegate_pro and params.get("pipeline_config"):
                return await fn(*args, **kwargs)
            key = params["smiles"]
            with _guard:
                entry = _locks.setdefault(key, [threading.Lock(), 0])
                entry[1] += 1
            acquired = False
            try:
                while not acquired:
                    acquired = entry[0].acquire(blocking=False)
                    if not acquired:
                        await asyncio.sleep(0.05)
                return await fn(*args, **kwargs)
            finally:
                if acquired:
                    entry[0].release()
                with _guard:
                    entry[1] -= 1
                    if entry[1] == 0:
                        _locks.pop(key, None)
        return wrapped
    return decorate
