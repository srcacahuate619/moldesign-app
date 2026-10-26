"""Procesos de render con cancelación y cierre de TODOS sus descendientes."""
from __future__ import annotations
import os
import subprocess
import time
from pathlib import Path

from utils.procesos import BANDERAS_SIN_VENTANA


def carpeta_de_proceso() -> str:
    """Directorio de trabajo de un proceso de Molcy que no tiene carpeta propia (sondeos, instalación del addon).

    Un proceso hereda el directorio de quien lo lanza, y Blender lo usa como suyo. En el paquete instalado el backend
    vive en `WindowsApps`: Molecular Nodes entra en la carpeta del .blend y, al salir (save_post), vuelve a la anterior,
    y Windows niega esa vuelta (`PermissionError: [WinError 5]`). Ver BUG-molcy-render-WindowsApps. Por eso ningún
    proceso del motor hereda la carpeta del backend. Importación diferida: este módulo lo carga también el
    intérprete empaquetado en la verificación del bundle, sin configurar la app.
    """
    from utils.local_storage import data_dir
    carpeta = data_dir() / "molcy"
    carpeta.mkdir(parents=True, exist_ok=True)
    return str(carpeta)


def terminate_owned(process) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        system_root = Path(os.environ.get("SystemRoot", r"C:\Windows"))
        taskkill = system_root / "System32/taskkill.exe"
        subprocess.run([str(taskkill), "/PID", str(process.pid), "/T", "/F"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
                       creationflags=BANDERAS_SIN_VENTANA, cwd=str(system_root / "System32"))
    else:
        import signal
        os.killpg(process.pid, signal.SIGKILL)
    if process.poll() is None:
        process.kill()
    process.wait(timeout=30)


class WindowsJob:
    """KILL_ON_JOB_CLOSE también ante cierre abrupto del backend."""
    def __init__(self, process, cpu_rate: int | None = None):
        self.handle = None
        if os.name != "nt":
            return
        import ctypes
        from ctypes import wintypes as w
        class Basic(ctypes.Structure):
            _fields_ = [("process_time", ctypes.c_longlong), ("job_time", ctypes.c_longlong),
                        ("flags", w.DWORD), ("minimum", ctypes.c_size_t), ("maximum", ctypes.c_size_t),
                        ("processes", w.DWORD), ("affinity", ctypes.c_size_t),
                        ("priority", w.DWORD), ("scheduling", w.DWORD)]
        class IO(ctypes.Structure):
            _fields_ = [(name, ctypes.c_ulonglong) for name in
                        ("reads", "writes", "other", "read_bytes", "write_bytes", "other_bytes")]
        class Extended(ctypes.Structure):
            _fields_ = [("basic", Basic), ("io", IO), ("process_memory", ctypes.c_size_t),
                        ("job_memory", ctypes.c_size_t), ("peak_process", ctypes.c_size_t),
                        ("peak_job", ctypes.c_size_t)]
        self.api = ctypes.WinDLL("kernel32", use_last_error=True)
        self.api.CreateJobObjectW.argtypes = [ctypes.c_void_p, w.LPCWSTR]
        self.api.CreateJobObjectW.restype = w.HANDLE
        self.api.SetInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD]
        self.api.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
        self.api.CloseHandle.argtypes = [w.HANDLE]
        self.api.TerminateJobObject.argtypes = [w.HANDLE, w.UINT]
        handle = self.api.CreateJobObjectW(None, None)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        info = Extended()
        info.basic.flags = 0x2000 | 0x20  # KILL_ON_JOB_CLOSE + PRIORITY_CLASS
        info.basic.priority = 0x4000  # BELOW_NORMAL_PRIORITY_CLASS, también descendientes
        if not self.api.SetInformationJobObject(handle, 9, ctypes.byref(info), ctypes.sizeof(info)) or not self.api.AssignProcessToJobObject(handle, w.HANDLE(int(process._handle))):
            error = ctypes.get_last_error()
            self.api.CloseHandle(handle)
            raise ctypes.WinError(error)
        self.handle = handle
        if cpu_rate is not None:
            class CpuRate(ctypes.Structure):
                _fields_ = [("flags", w.DWORD), ("rate", w.DWORD)]
            limit = CpuRate(0x1 | 0x4, cpu_rate)  # ENABLE + HARD_CAP
            if not self.api.SetInformationJobObject(handle, 15, ctypes.byref(limit), ctypes.sizeof(limit)):
                error = ctypes.get_last_error()
                self.close()
                raise ctypes.WinError(error)

    def close(self):
        if self.handle:
            self.api.TerminateJobObject(self.handle, 1)
            self.api.CloseHandle(self.handle)
            self.handle = None


def run_owned(cmd, *, env, stdout, cancel, on_start, timeout, cwd, cpu_rate=None, monitor=None):
    """Lanza `cmd` y lo vigila. `cwd` es obligatorio: un proceso del motor no hereda la carpeta del backend (ver `carpeta_de_proceso`)."""
    if cpu_rate is not None and (type(cpu_rate) is not int or not 1 <= cpu_rate <= 7500):
        raise ValueError("El límite CPU del render debe dejar al menos un 25% para otras aplicaciones.")
    process = subprocess.Popen(cmd, env=env, stdout=stdout, stderr=subprocess.STDOUT, cwd=str(cwd),
                               creationflags=BANDERAS_SIN_VENTANA, start_new_session=os.name != "nt")
    try:
        job = WindowsJob(process, cpu_rate=cpu_rate)
    except OSError:
        terminate_owned(process)
        raise
    started = time.monotonic()
    try:
        on_start(process)
        while process.poll() is None:
            if cancel.wait(0.2):
                raise InterruptedError("Render cancelado por el usuario.")
            if time.monotonic() - started > timeout:
                raise subprocess.TimeoutExpired(cmd, timeout)
            if monitor is not None:
                monitor()
        return subprocess.CompletedProcess(cmd, process.returncode)
    finally:
        job.close()
        terminate_owned(process)
