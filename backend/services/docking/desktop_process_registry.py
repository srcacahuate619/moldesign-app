"""Registro task-scoped de subprocesos auxiliares del dispatcher desktop.

MM-GBSA y selectividad pueden sobrevivir al flujo principal de una evaluación.
Como el dispatcher permite varios jobs a la vez, sus procesos no pueden vivir
en una lista global: cancelar una tarea debe afectar solamente sus hijos.
"""

from __future__ import annotations

import threading

from utils.procesos import kill_process_tree
from typing import Any

_lock = threading.RLock()
_processes: dict[str, dict[str, list[Any]]] = {}


def register_process(task_id: str, kind: str, process: Any) -> None:
    """Asocia un subprocess vivo a una tarea y categoría concreta."""
    with _lock:
        _processes.setdefault(task_id, {}).setdefault(kind, []).append(process)


def unregister_process(task_id: str, kind: str, process: Any) -> None:
    """Elimina una asociación al terminar o expirar el subprocess."""
    with _lock:
        by_kind = _processes.get(task_id)
        if not by_kind:
            return
        processes = by_kind.get(kind)
        if processes:
            try:
                processes.remove(process)
            except ValueError:
                pass
            if not processes:
                by_kind.pop(kind, None)
        if not by_kind:
            _processes.pop(task_id, None)


def cancel_processes(task_id: str, kind: str) -> int:
    """Termina únicamente subprocesses vivos de ``task_id`` y ``kind``."""
    with _lock:
        by_kind = _processes.get(task_id)
        processes = list(by_kind.pop(kind, [])) if by_kind else []
        if by_kind is not None and not by_kind:
            _processes.pop(task_id, None)

    killed = 0
    for process in processes:
        try:
            if process.returncode is None:
                kill_process_tree(process)
                killed += 1
        except Exception:
            # Best-effort: no impedir el cierre del job por un proceso que
            # terminó entre el snapshot protegido y kill().
            pass
    return killed


def clear_registered_processes() -> None:
    """Limpia sólo el registro; útil para aislar tests, no mata procesos."""
    with _lock:
        _processes.clear()
