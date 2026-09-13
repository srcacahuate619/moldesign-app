"""
core/hardware.py

Hardware detection for adaptive pipeline configuration.
Reports CPU cores, RAM, GPU availability to let the user
configure parallelism and GPU acceleration.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


@dataclass
class HardwareInfo:
    cpu_cores_physical: int = 0
    cpu_cores_logical: int = 0
    cpu_usage_percent: float = 0.0
    cpu_model: str = ""
    ram_total_gb: float = 0.0
    ram_available_gb: float = 0.0
    gpu_available: bool = False
    gpu_name: str = ""
    gpu_vram_gb: float = 0.0
    gpu_vram_free_gb: float = 0.0
    gpu_cuda: bool = False
    gpu_opencl: bool = False
    openmm_gpu_platforms: list[str] = field(default_factory=list)
    torch_cuda: bool = False
    reserved_cpu_cores: int = 1
    recommended_workers: int = 1
    recommended_parallel_docks: int = 1
    warnings: list[str] = field(default_factory=list)


def detect_hardware() -> HardwareInfo:
    info = HardwareInfo()

    # ── CPU ────────────────────────────────────────────────────────
    if HAS_PSUTIL:
        info.cpu_cores_physical = psutil.cpu_count(logical=False) or 1
        info.cpu_cores_logical = psutil.cpu_count(logical=True) or 1
        # cpu_percent necesita dos llamadas para obtener un valor real:
        # la primera retorna 0.0 (desde el boot), la segunda captura el delta.
        psutil.cpu_percent(interval=0)  # warm-up (descarta el primer valor)
        info.cpu_usage_percent = round(psutil.cpu_percent(interval=0.3), 1)
        info.ram_total_gb = round(psutil.virtual_memory().total / (1024**3), 1)
        info.ram_available_gb = round(psutil.virtual_memory().available / (1024**3), 1)
    else:
        info.cpu_cores_physical = os.cpu_count() or 1
        info.cpu_cores_logical = info.cpu_cores_physical
        info.cpu_usage_percent = 0.0
        info.ram_total_gb = 0.0
        info.ram_available_gb = 0.0

    # CPU model
    try:
        if os.name == "nt":
            # `wmic` ESTA ELIMINADO de Windows 11 moderno. Comprobado en la
            # maquina de desarrollo (build 26200): `where wmic` no lo encuentra
            # y `subprocess.run` levanta FileNotFoundError. Como el bloque vive
            # dentro de un `except Exception`, el fallo no se veia: el modelo de
            # CPU caia al respaldo «6C/12T CPU», y eso es lo que acababa en la
            # seccion de entorno del dossier.
            #
            # El registro da el nombre real -«AMD Ryzen 5 5500»- sin lanzar
            # ningun proceso y sin depender de una herramienta que Microsoft
            # puede volver a quitar. `winreg` es de la biblioteca estandar y
            # solo existe en Windows, por eso el import va aqui dentro.
            try:
                import winreg

                ruta_cpu = "HARDWARE" + chr(92) + "DESCRIPTION" + chr(92) + "System"
                ruta_cpu += chr(92) + "CentralProcessor" + chr(92) + "0"
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, ruta_cpu) as clave:
                    nombre = winreg.QueryValueEx(clave, "ProcessorNameString")[0]
                if nombre and nombre.strip():
                    info.cpu_model = nombre.strip()
            except Exception:
                # `platform.processor()` da familia y fabricante -menos legible,
                # pero cierto- y nunca falla en Windows.
                import platform

                identificador = platform.processor()
                if identificador:
                    info.cpu_model = identificador.strip()
        elif os.path.exists("/proc/cpuinfo"):
            with open("/proc/cpuinfo") as f:
                for line in f:
                    if "model name" in line:
                        info.cpu_model = line.split(":")[1].strip()
                        break
    except Exception:
        info.cpu_model = f"{info.cpu_cores_physical}C/{info.cpu_cores_logical}T CPU"

    # ── GPU (CUDA via PyTorch) ─────────────────────────────────────
    try:
        import torch

        if torch.cuda.is_available():
            info.gpu_available = True
            info.gpu_cuda = True
            info.torch_cuda = True
            info.gpu_name = torch.cuda.get_device_name(0) or "NVIDIA GPU"
            try:
                props = torch.cuda.get_device_properties(0)
                vram_total = props.total_memory
                vram_used = torch.cuda.memory_allocated(0)
                info.gpu_vram_gb = round(vram_total / (1024**3), 1)
                info.gpu_vram_free_gb = round((vram_total - vram_used) / (1024**3), 1)
            except Exception:
                info.gpu_vram_gb = 0.0
                info.gpu_vram_free_gb = 0.0
    except ImportError:
        pass

    # ── GPU (OpenCL via pyopencl) ──────────────────────────────────
    if not info.gpu_available:
        try:
            import pyopencl as cl
            platforms = cl.get_platforms()
            for p in platforms:
                devices = p.get_devices(cl.device_type.GPU)
                if devices:
                    info.gpu_available = True
                    info.gpu_opencl = True
                    info.gpu_name = devices[0].name
                    try:
                        mem = devices[0].global_mem_size
                        info.gpu_vram_gb = round(mem / (1024**3), 1)
                    except Exception:
                        pass
                    break
        except ImportError:
            pass

    # ── OpenMM platforms ───────────────────────────────────────────
    try:
        import openmm
        for i in range(openmm.Platform.getNumPlatforms()):
            p = openmm.Platform.getPlatform(i)
            name = p.getName()
            info.openmm_gpu_platforms.append(name)
    except ImportError:
        pass

    # ── Adaptive workers: reserva 1 core físico (≈2 workers) para el sistema ──
    available_physical = max(1, info.cpu_cores_physical - info.reserved_cpu_cores)
    available_logical = max(1, info.cpu_cores_logical - (info.reserved_cpu_cores * 2))

    if info.gpu_cuda:
        # GPU CUDA: la GPU es el bottleneck compartido → menos workers para evitar contención
        info.recommended_workers = min(available_physical, 4)
        info.recommended_parallel_docks = min(3, max(1, available_physical // 2))
    elif info.gpu_opencl:
        info.recommended_workers = min(available_physical, 3)
        info.recommended_parallel_docks = min(2, max(1, available_physical // 2))
    else:
        # CPU-only: menos paralelismo para evitar contention
        info.recommended_workers = max(1, available_physical)
        info.recommended_parallel_docks = 1

    # CPU usage info (no se usa para decisiones de paralelismo — la medicion
    # es puntual y puede reflejar picos transitorios, no carga sostenida).
    if info.cpu_usage_percent > 90:
        info.warnings.append(
            f"CPU al {info.cpu_usage_percent}% de uso alto."
        )
    if info.gpu_available and info.gpu_vram_free_gb is not None and info.gpu_vram_free_gb < 1:
        info.recommended_workers = min(info.recommended_workers, 2)
        info.warnings.append(
            f"VRAM libre < 1 GB. Workers reducidos a {info.recommended_workers}."
        )

    # ── Warnings ───────────────────────────────────────────────────
    if info.ram_total_gb > 0 and info.ram_total_gb < 8:
        info.warnings.append("RAM < 8 GB: algunas funciones pueden usar swap. Cerrá otras apps.")
    if info.ram_available_gb < 2:
        info.warnings.append("RAM disponible < 2 GB: rendimiento severamente degradado.")
    if not info.gpu_available:
        info.warnings.append(
            "No se detectó GPU. MM-GBSA y GNN rescoring correrán en CPU (más lento)."
        )
    if info.cpu_cores_physical < 4 and not info.gpu_available:
        info.warnings.append(
            "CPU de 2 cores sin GPU: las evaluaciones PRO completas pueden tomar >15 min."
        )

    return info


def estimate_evaluation_time(
    hardware: HardwareInfo,
    mode: str = "edu",
    num_anti_targets: int = 0,
    use_mmgbsa: bool = False,
) -> dict[str, Any]:
    """
    Estimate evaluation time based on hardware and selected features.
    """
    estimates = {
        "validation_properties": "1-3s",
        "conformer_docking": "",
        "rescoring": "1-2s",
        "anti_targets": "",
        "mmgbsa": "",
        "total_seconds_min": 0,
        "total_seconds_max": 0,
    }

    # Docking time estimation
    base_dock_time = 45  # seconds baseline
    if hardware.cpu_cores_physical >= 8:
        base_dock_time = 25
    elif hardware.cpu_cores_physical >= 4:
        base_dock_time = 35

    estimates["conformer_docking"] = f"{base_dock_time}s"
    total_min = base_dock_time
    total_max = base_dock_time * 2

    # Anti-targets (additional docks in parallel)
    if num_anti_targets > 0:
        parallel = min(hardware.recommended_parallel_docks, num_anti_targets + 1)
        batches = (num_anti_targets + 1) // parallel
        anti_time = batches * base_dock_time
        estimates["anti_targets"] = f"+{num_anti_targets} targets en {batches} batches (~{anti_time}s)"
        total_min += anti_time
        total_max += anti_time * 2

    # MM-GBSA
    if use_mmgbsa:
        if hardware.gpu_cuda:
            gbsa_time = 15
            estimates["mmgbsa"] = "15s (GPU CUDA acelerado)"
        elif hardware.gpu_opencl:
            gbsa_time = 30
            estimates["mmgbsa"] = "30s (GPU OpenCL)"
        else:
            gbsa_time = 120
            estimates["mmgbsa"] = "120s (CPU — lento)"

        total_min += gbsa_time
        total_max += gbsa_time * 1.5

    estimates["total_seconds_min"] = total_min
    estimates["total_seconds_max"] = int(total_max)

    if mode == "edu":
        estimates["total_description"] = "Evaluación rápida"
    elif total_max < 120:
        estimates["total_description"] = "Evaluación completa rápida"
    elif total_max < 300:
        estimates["total_description"] = "Evaluación completa — toma unos minutos"
    else:
        estimates["total_description"] = "Evaluación exhaustiva — puede demorar unos minutos"

    return estimates
