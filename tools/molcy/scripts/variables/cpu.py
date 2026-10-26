"""Cantidad de hilos CPU solicitada por el programa que invoca Molcy."""
import os


def hilos_cpu() -> int:
    available = max(1, os.cpu_count() or 1)
    if hasattr(os, "sched_getaffinity"):
        available = min(available, len(os.sched_getaffinity(0)))
    available = min(available, 1024)
    raw = os.environ.get("MOLCY_CPU_THREADS")
    if raw is None:
        return max(1, available - 1)
    try:
        selected = int(raw)
    except ValueError as exc:
        raise ValueError("MOLCY_CPU_THREADS debe indicar una cantidad entera de hilos.") from exc
    if not 1 <= selected <= available:
        raise ValueError(f"MOLCY_CPU_THREADS debe estar entre 1 y {available}.")
    return selected
