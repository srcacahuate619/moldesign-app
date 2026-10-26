"""Selección de un archivo en el Explorador sin interpretar argumentos de shell."""
from __future__ import annotations

from pathlib import Path

from .windows_paths import ruta_para_programa


def seleccionar_windows(path: Path) -> None:
    # Imports bajo demanda: el arranque no necesita las APIs del escritorio.
    import ctypes
    from ctypes import wintypes

    shell = ctypes.WinDLL("shell32", use_last_error=True)
    ole = ctypes.WinDLL("ole32", use_last_error=True)
    ole.CoInitializeEx.argtypes = [ctypes.c_void_p, wintypes.DWORD]
    ole.CoInitializeEx.restype = ctypes.c_long
    ole.CoUninitialize.argtypes = []
    ole.CoUninitialize.restype = None
    ole.CoTaskMemFree.argtypes = [ctypes.c_void_p]
    ole.CoTaskMemFree.restype = None
    shell.SHParseDisplayName.argtypes = [wintypes.LPCWSTR, ctypes.c_void_p,
                                       ctypes.POINTER(ctypes.c_void_p), wintypes.DWORD,
                                       ctypes.POINTER(wintypes.DWORD)]
    shell.SHParseDisplayName.restype = ctypes.c_long
    shell.SHOpenFolderAndSelectItems.argtypes = [ctypes.c_void_p, wintypes.UINT,
                                               ctypes.c_void_p, wintypes.DWORD]
    shell.SHOpenFolderAndSelectItems.restype = ctypes.c_long

    initialized = ole.CoInitializeEx(None, 2)  # COINIT_APARTMENTTHREADED
    # RPC_E_CHANGED_MODE: el hilo ya tiene COM inicializado en otro modelo.
    if initialized < 0 and initialized != -2147417850:
        raise OSError(f"Windows no pudo inicializar el Explorador (0x{initialized & 0xffffffff:08X}).")
    pidl = ctypes.c_void_p()
    try:
        # Rust canonicaliza carpetas de Windows con prefijo de ruta extendida.
        # El namespace del Shell recibe la escritura de unidad/UNC habitual.
        name = ruta_para_programa(path)
        result = shell.SHParseDisplayName(name, None, ctypes.byref(pidl), 0, None)
        if result >= 0 and pidl.value:
            # cidl=0 recibe el PIDL absoluto del archivo: abre su carpeta y lo selecciona.
            result = shell.SHOpenFolderAndSelectItems(pidl, 0, None, 0)
        if result < 0 or not pidl.value:
            raise OSError(f"Windows no pudo mostrar el MP4 (0x{result & 0xffffffff:08X}).")
    finally:
        if pidl.value:
            ole.CoTaskMemFree(pidl)
        if initialized >= 0:
            ole.CoUninitialize()
