"""El runtime de Microsoft Visual C++ x64 que MolDesign pone a disposición de los procesos auxiliares de Blender.

EL FALLO (VM-MOLCY-01, 2026-10-12; informe en `D:\\moldesign-audits\\molecular-nodes-1.0.2-20261012`). En un Windows sin el
redistribuible x64, «Descargar e instalar Molecular Nodes» terminaba en «Repository data ... not found, sync required» y
«No installable packages marked». Blender arrancaba bien —`blender.exe` lleva su runtime en `blender.crt/`, un ensamblado
privado con manifiesto—, pero el gestor de extensiones lanza por subproceso el Python de Blender
(`<versión>/python/bin/python.exe`), que no hereda ese ensamblado y no trae ninguna DLL de Visual C++ a su lado: moría con
0xC0000135 (STATUS_DLL_NOT_FOUND) antes de descargar el catálogo. Medido en un Blender 5.2.2 real: `python.exe` y
`python313.dll` piden `vcruntime140.dll`, y 52 módulos `.pyd` piden `vcruntime140_1.dll` y 49 `msvcp140.dll`.

QUÉ HACE. MolDesign ya distribuye ese runtime con su procedencia (`tools/vc-runtime/`: 14.50.35719 x64, el SHA-256 de cada
DLL y el instalador oficial de Microsoft del que salen). Este módulo sólo lo usa si cada byte coincide con su manifiesto, y:

- en el Blender ADMINISTRADO (el que MolDesign descargó en su carpeta de datos) copia las DLL junto a su `python.exe`. Es la
  única ubicación que cubre todo: el directorio de la aplicación es el primero que mira Windows —así gana también a un
  runtime del sistema más antiguo— y Python ≥ 3.8 resuelve las dependencias de sus `.pyd` sin mirar el PATH;
- en cualquier Blender, también en el del usuario, antepone la carpeta verificada al PATH **del subproceso**. No toca el PATH
  global ni un solo archivo del Blender personal: para ese caso es un respaldo, y `probar_python` dice si alcanzó.

No sustituye ni degrada nada del sistema: sólo escribe archivos que faltaban en la carpeta del Blender administrado, y
recuerda cuáles escribió (`moldesign-vc-runtime.json`) para no pisar nunca una DLL que trajera el propio Blender.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import subprocess
import uuid
from pathlib import Path

from utils.procesos import BANDERAS_SIN_VENTANA

# Biblioteca estándar: la verificación del bundle importa este módulo con el intérprete empaquetado y sin configurar la app.
log = logging.getLogger(__name__)

NOMBRE_MANIFIESTO = "vc-runtime-manifest.json"
#: Junto al `python.exe` del Blender administrado: qué DLL copió MolDesign y de qué versión.
NOMBRE_REGISTRO = "moldesign-vc-runtime.json"
#: 0xC0000135, STATUS_DLL_NOT_FOUND: el cargador de Windows no encontró una DLL que el ejecutable importa.
STATUS_DLL_NOT_FOUND = 0xC0000135
#: Lo que el gestor de extensiones necesita de su Python para sincronizar el catálogo e instalar: red con TLS, hashes, zip.
SONDA_PYTHON = "import sys, ssl, hashlib, zlib, json, urllib.request; print('MOLCY_PY_OK', sys.version.split()[0], flush=True)"

_cache: dict[str, object] = {}


def directorio_incluido() -> Path | None:
    """Carpeta `tools/vc-runtime` que viaja con MolDesign, o None si este arranque no la tiene.

    Orden: `MOLDESIGN_VC_RUNTIME_DIR` (pruebas y diagnóstico), la hermana de la carpeta de Open Babel que pasa Rust y, por la
    misma regla que el motor Molcy, `<raíz>/tools/vc-runtime` (raíz del repositorio en desarrollo, de los recursos instalados en
    producción). Cuenta sólo si trae su manifiesto.
    """
    candidatas: list[Path] = []
    if os.environ.get("MOLDESIGN_VC_RUNTIME_DIR"):
        candidatas.append(Path(os.environ["MOLDESIGN_VC_RUNTIME_DIR"]))
    if os.environ.get("MOLDESIGN_OPENBABEL_DIR"):
        candidatas.append(Path(os.environ["MOLDESIGN_OPENBABEL_DIR"]).parent / "vc-runtime")
    candidatas.append(Path(__file__).resolve().parents[3] / "tools" / "vc-runtime")
    for carpeta in candidatas:
        if carpeta.is_absolute() and (carpeta / NOMBRE_MANIFIESTO).is_file():
            return carpeta.resolve()
    return None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _firma(carpeta: Path) -> tuple:
    """Lo que, si cambia, obliga a volver a verificar: tamaño y fecha del manifiesto y de cada DLL."""
    rutas = [carpeta / NOMBRE_MANIFIESTO, *sorted((carpeta / "x64").glob("*.dll"))]
    firma = []
    for ruta in rutas:
        try:
            stat = ruta.stat()
            firma.append((ruta.name, stat.st_size, stat.st_mtime_ns))
        except OSError:
            firma.append((ruta.name, None, None))
    return (str(carpeta), tuple(firma))


def verificar(carpeta: Path) -> tuple[dict, list[str]]:
    """(manifiesto, problemas) de una carpeta `vc-runtime`. Sin problemas, cada DLL declarada es la del manifiesto, byte a byte."""
    try:
        manifiesto = json.loads((carpeta / NOMBRE_MANIFIESTO).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return {}, [f"manifiesto ilegible: {type(exc).__name__}"]
    if not isinstance(manifiesto, dict):
        return {}, ["manifiesto ilegible"]
    problemas: list[str] = []
    if manifiesto.get("architecture") != "x64" or manifiesto.get("deployment") != "app-local":
        problemas.append("el manifiesto no declara x64/app-local")
    declarados = manifiesto.get("files")
    if not isinstance(declarados, dict) or not declarados:
        return manifiesto, problemas + ["el manifiesto no declara archivos"]
    for nombre, datos in sorted(declarados.items()):
        ruta = carpeta / "x64" / nombre
        try:
            if ruta.stat().st_size != int(datos["bytes"]) or _sha256(ruta) != str(datos["sha256"]).lower():
                problemas.append(f"{nombre}: no coincide con su manifiesto")
        except OSError:
            problemas.append(f"{nombre}: falta")
        except (KeyError, TypeError, ValueError):
            problemas.append(f"{nombre}: entrada del manifiesto incompleta")
    return manifiesto, problemas


def runtime_verificado() -> tuple[Path | None, dict, list[str]]:
    """(carpeta x64, manifiesto, problemas). La carpeta sólo se devuelve si todo coincide; la verificación se recuerda por firma."""
    carpeta = directorio_incluido()
    if carpeta is None:
        return None, {}, ["MolDesign no encuentra su runtime de Visual C++ (tools/vc-runtime)"]
    firma = _firma(carpeta)
    if _cache.get("firma") != firma:
        manifiesto, problemas = verificar(carpeta)
        _cache.clear()
        _cache.update(firma=firma, manifiesto=manifiesto, problemas=problemas)
    problemas = list(_cache["problemas"])  # type: ignore[arg-type]
    manifiesto = dict(_cache["manifiesto"])  # type: ignore[arg-type]
    return (None if problemas else carpeta / "x64"), manifiesto, problemas


def python_de_blender(blender: Path) -> Path | None:
    """El `python.exe` que Blender lanza por subproceso (`<X.Y>/python/bin/python.exe`); el de la versión más alta si hay varios."""
    # Sólo las carpetas con nombre de versión, y sin `glob`: un Blender del usuario puede vivir en la raíz de una unidad, donde
    # hay carpetas que ni se pueden mirar (medido: `E:\WpSystem` lanza WinError 1337 al recorrer `E:\*`).
    candidatos = []
    try:
        hijos = [h for h in blender.parent.iterdir() if re.fullmatch(r"\d+\.\d+", h.name)]
    except OSError:
        return None
    for carpeta in hijos:
        python = carpeta / "python" / "bin" / "python.exe"
        try:
            if python.is_file():
                candidatos.append((tuple(int(p) for p in carpeta.name.split(".")), python))
        except OSError:
            continue
    return max(candidatos)[1] if candidatos else None


def desplegar_junto_a_python(python: Path) -> list[str]:
    """Copia las DLL verificadas que falten junto a `python`; devuelve las que copió. No pisa una DLL que no puso MolDesign.

    Sólo para el Blender administrado (lo decide quien llama). Una DLL que MolDesign copió antes y ya no coincide con el
    manifiesto (dañada, o de un runtime anterior) se reemplaza; cualquier otra que ya estuviera se respeta.
    """
    origen, manifiesto, problemas = runtime_verificado()
    if origen is None:
        log.warning("Runtime de Visual C++ no verificado; no se aplica a Blender: %s", "; ".join(problemas))
        return []
    destino = python.parent
    registro_path = destino / NOMBRE_REGISTRO
    try:
        registro = json.loads(registro_path.read_text(encoding="utf-8"))
        nuestras = set(registro.get("archivos") or {}) if isinstance(registro, dict) else set()
    except (OSError, ValueError):
        nuestras = set()
    copiadas: list[str] = []
    for nombre, datos in sorted(manifiesto["files"].items()):
        ruta = destino / nombre
        if ruta.exists():
            if nombre not in nuestras:
                continue  # la trajo Blender: es suya
            try:
                if _sha256(ruta) == str(datos["sha256"]).lower():
                    continue
            except OSError:
                pass
        temporal = destino / f".{nombre}.{uuid.uuid4().hex}.tmp"
        try:
            temporal.write_bytes((origen / nombre).read_bytes())
            if _sha256(temporal) != str(datos["sha256"]).lower():
                raise OSError("la copia no coincide con el manifiesto")
            os.replace(temporal, ruta)
            copiadas.append(nombre)
        except OSError as exc:
            # En uso por un Blender que está corriendo, o sin permiso: se queda el PATH del subproceso como respaldo.
            log.warning("No se pudo copiar %s junto a %s: %s", nombre, python, exc)
        finally:
            temporal.unlink(missing_ok=True)
    if copiadas:
        nuestras |= set(copiadas)
        try:
            registro_path.write_text(json.dumps({
                "componente": manifiesto.get("component"), "version": manifiesto.get("version"),
                "arquitectura": manifiesto.get("architecture"), "origen": "tools/vc-runtime de MolDesign",
                "archivos": {n: manifiesto["files"][n]["sha256"] for n in sorted(nuestras) if n in manifiesto["files"]},
            }, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError as exc:
            log.warning("No se pudo registrar el runtime copiado junto a %s: %s", python, exc)
        log.info("Runtime de Visual C++ %s copiado junto a %s: %s", manifiesto.get("version"), python, ", ".join(copiadas))
    return copiadas


def con_runtime_en_path(env: dict[str, str]) -> dict[str, str]:
    """El mismo entorno con la carpeta verificada delante del PATH (sólo para el subproceso; si no verifica, sin cambios)."""
    origen, _, _ = runtime_verificado()
    if origen is None:
        return env
    clave = next((k for k in env if k.upper() == "PATH"), "PATH")
    actual = env.get(clave, "")
    partes = [p for p in actual.split(os.pathsep) if p and os.path.normcase(p) != os.path.normcase(str(origen))]
    return {**env, clave: os.pathsep.join([str(origen), *partes])}


def codigo_windows(returncode: int) -> int:
    """El código de salida como lo escribe Windows (0xC0000135), venga con signo o sin él."""
    return returncode & 0xFFFFFFFF


def probar_python(blender: Path, env: dict[str, str], *, timeout: int = 60) -> dict:
    """Arranca el Python auxiliar de Blender con el entorno que recibirá de verdad y comprueba lo que el gestor de extensiones usa.

    Devuelve {"ok", "python", "returncode", "codigo", "stdout", "stderr"}. `ok` sólo si terminó con 0 y dijo MOLCY_PY_OK.
    Si este Blender no trae Python propio («python» None), no hay nada que probar y `ok` es True.
    """
    python = python_de_blender(blender)
    if python is None:
        return {"ok": True, "python": None, "returncode": None, "codigo": None, "stdout": "", "stderr": ""}
    # Diferido: la verificación del bundle carga este módulo sin process.py (scripts/tests/test_verify_vc_runtime.py).
    from .process import carpeta_de_proceso
    try:
        resultado = subprocess.run([str(python), "-I", "-c", SONDA_PYTHON], capture_output=True, text=True,
                                   timeout=timeout, check=False, env=env, creationflags=BANDERAS_SIN_VENTANA,
                                   cwd=carpeta_de_proceso())
    except subprocess.TimeoutExpired as exc:
        return {"ok": False, "python": str(python), "returncode": None, "codigo": "timeout",
                "stdout": str(exc.stdout or ""), "stderr": str(exc.stderr or "")}
    except OSError as exc:
        return {"ok": False, "python": str(python), "returncode": None, "codigo": type(exc).__name__,
                "stdout": "", "stderr": str(exc)}
    ok = resultado.returncode == 0 and "MOLCY_PY_OK" in resultado.stdout
    return {"ok": ok, "python": str(python), "returncode": resultado.returncode,
            "codigo": f"0x{codigo_windows(resultado.returncode):08X}", "stdout": resultado.stdout, "stderr": resultado.stderr}
