"""El sidecar MolChat que viaja con MolDesign: dónde está y si es el distribuido.

MolChat es un programa independiente (GPL-3.0-or-later) que MolDesign no
importa: lo ejecuta como subproceso en loopback y se comunica por HTTP
versionado (`moldesign.molchat/1`). Va en `tools/molchat/` con su manifiesto
(`molchat-manifest.json`: SHA-256 por fichero, commit del que sale, contrato
que habla y su licencia), igual que el motor Molcy (ADR 95). Aquí sólo hay
biblioteca estándar: lo usan el lanzador del host, la verificación del
bundle y el script que lo vendoriza.

Qué NO hace: no decide si el contrato del sidecar es compatible (eso lo
exige el lanzador antes de arrancar) ni lo repara. Si un fichero no coincide
con su manifiesto, el host se abstiene: un sidecar alterado no se ejecuta.

La copia incluida además debe ser la FIJADA: `backend/data/molchat_fijacion.json`
guarda el commit y el SHA-256 del manifiesto que MolDesign espera. Esa fijación
vive en el backend, fuera de `tools/molchat/`, así que reemplazar la copia sin
actualizarla deja al host sin llave hasta que se fije de nuevo (ADR 100).
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

NOMBRE_MANIFIESTO = "molchat-manifest.json"
ESQUEMA = "moldesign.molchat/1"
#: Contrato sidecar↔plataforma que este host sabe hablar. Un sidecar que
#: declare otro `contrato.agente_plataforma` no arranca (el lanzador lo dice).
CONTRATO_SIDECAR = "moldesign.molchat/1"
ESQUEMA_FIJACION = "moldesign.molchat-fijacion/1"
#: Repositorio público de la llave. Una fijación que lo declara es la oficial;
#: cualquier otro origen es una versión propia (ver docs de MolChat).
REPOSITORIO_OFICIAL = "https://github.com/srcacahuate619/moldesign-molchat"
#: Dónde está la fijación de la llave. Va en el backend, no en la copia.
FIJACION = Path(__file__).resolve().parents[2] / "data" / "molchat_fijacion.json"


def sha256_bytes(datos: bytes) -> str:
    return hashlib.sha256(datos).hexdigest()


def sha256_conjunto(archivos: dict[str, dict]) -> str:
    """Huella del conjunto: rutas y hashes ordenados. Cambia si cambia un byte, un nombre o la lista."""
    cuerpo = "".join(f"{ruta}\0{archivos[ruta]['sha256']}\n" for ruta in sorted(archivos))
    return sha256_bytes(cuerpo.encode("utf-8"))


def directorio_incluido(raiz: Path | None = None,
                        solo_incluido: bool = False) -> Path | None:
    """Carpeta del sidecar que viaja con MolDesign, o None si este arranque no la tiene.

    Orden: `MOLDESIGN_MOLCHAT_DIR` (la que configura el desarrollador del
    sidecar), la hermana de la carpeta de Open Babel (`tools/molchat` junto a
    `tools/openbabel`: así se resuelve en el instalador) y, en un árbol de
    desarrollo, `tools/molchat` del repositorio. Cuenta como incluida sólo si
    trae su manifiesto. `raiz` existe para las pruebas; en producción es None.
    Con `solo_incluido`, se ignora la variable de entorno: así el lanzador
    distingue "el incluido, dicho por su nombre" de "uno externo".
    """
    repo = raiz or Path(__file__).resolve().parents[3]
    candidatas: list[Path] = []
    if os.environ.get("MOLDESIGN_MOLCHAT_DIR") and not solo_incluido:
        candidatas.append(Path(os.environ["MOLDESIGN_MOLCHAT_DIR"]))
    if os.environ.get("MOLDESIGN_OPENBABEL_DIR"):
        candidatas.append(Path(os.environ["MOLDESIGN_OPENBABEL_DIR"]).parent / "molchat")
    candidatas.append(repo / "tools" / "molchat")
    for carpeta in candidatas:
        if carpeta.is_absolute() and (carpeta / NOMBRE_MANIFIESTO).is_file():
            return carpeta.resolve()
    return None


def molchat_externo_permitido() -> bool:
    """¿Se acepta un sidecar distinto del incluido? Sólo para quien desarrolla
    el sidecar, con `MOLCHAT_PERMITIR_EXTERNO=1` en el entorno.

    Ni la pantalla ni el instalador lo activan. El sidecar es GPL: quien quiera
    ejecutar una versión modificada puede hacerlo con esta variable y sin tocar
    el instalador; lo que no existe es una vía en la aplicación.
    """
    return os.environ.get("MOLCHAT_PERMITIR_EXTERNO") == "1"


def es_bytecode(ruta: Path, carpeta: Path) -> bool:
    """`__pycache__/*.pyc`: lo que el intérprete escribe junto a la copia
    vendorizada la primera vez que la ejecuta.

    Es un derivado de los `.py` (que sí se verifican), no un fichero del
    sidecar. Sólo se ignora el `.pyc` dentro de un `__pycache__`: un `.py`, o
    un `.pyc` fuera de él, siguen contando.
    """
    relativa = ruta.relative_to(carpeta)
    return ruta.suffix == ".pyc" and "__pycache__" in relativa.parts[:-1]


def verificar_integridad(carpeta: Path) -> list[str]:
    """Problemas de `carpeta` frente a su manifiesto: ficheros que faltan, que sobran o que difieren. Vacío = íntegro."""
    ruta_manifiesto = carpeta / NOMBRE_MANIFIESTO
    try:
        manifiesto = json.loads(ruta_manifiesto.read_text(encoding="utf-8"))
        declarados = manifiesto["archivos"]
    except OSError:
        return [f"falta {NOMBRE_MANIFIESTO}"]
    except (ValueError, KeyError):
        return [f"{NOMBRE_MANIFIESTO} ilegible"]
    if manifiesto.get("schema") != ESQUEMA:
        return [f"esquema desconocido: {manifiesto.get('schema')!r}"]
    problemas: list[str] = []
    presentes = {p.relative_to(carpeta).as_posix(): p for p in carpeta.rglob("*")
                 if p.is_file() and p.name != NOMBRE_MANIFIESTO and not es_bytecode(p, carpeta)}
    for ruta in sorted(set(declarados) - set(presentes)):
        problemas.append(f"falta {ruta}")
    for ruta in sorted(set(presentes) - set(declarados)):
        problemas.append(f"sobra {ruta}: no está en el manifiesto")
    for ruta in sorted(set(declarados) & set(presentes)):
        datos = presentes[ruta].read_bytes()
        if sha256_bytes(datos) != declarados[ruta]["sha256"] or len(datos) != declarados[ruta]["bytes"]:
            problemas.append(f"{ruta} difiere del manifiesto")
    if manifiesto.get("sha256_conjunto") != sha256_conjunto(declarados):
        problemas.append("sha256_conjunto no corresponde a la lista de archivos")
    return problemas


def manifiesto_de(carpeta: Path) -> dict:
    """El manifiesto ya leído (para registrar procedencia: commit, contrato, licencia). Vacío si no se puede leer."""
    try:
        return json.loads((carpeta / NOMBRE_MANIFIESTO).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def normalizar_url(url: str | None) -> str:
    """La URL sin espacios, sin barra final ni sufijo `.git`, para comparar repositorios."""
    limpia = (url or "").strip().rstrip("/")
    return limpia[:-4] if limpia.endswith(".git") else limpia


def es_oficial(repositorio: str | None) -> bool:
    """¿Sale la copia del repositorio público oficial de MolChat?"""
    return bool(repositorio) and normalizar_url(repositorio) == normalizar_url(REPOSITORIO_OFICIAL)


def cargar_fijacion(ruta: Path | None = None) -> dict | None:
    """La fijación de la llave tal como está escrita, o None si falta o no se lee."""
    try:
        return json.loads((ruta or FIJACION).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def fijacion_para(carpeta: Path) -> dict:
    """La fijación que describe la copia `carpeta`. La escribe `scripts/stage_molchat.py` al vendorizar."""
    manifiesto = manifiesto_de(carpeta)
    fuente = manifiesto.get("fuente") or {}
    repositorio = str(fuente.get("repositorio") or "")
    return {
        "schema": ESQUEMA_FIJACION,
        "repositorio": repositorio,
        "oficial": es_oficial(repositorio),
        "commit": fuente.get("commit", ""),
        "rama": fuente.get("rama", ""),
        "version": manifiesto.get("version", ""),
        "sha256_manifiesto": sha256_bytes((carpeta / NOMBRE_MANIFIESTO).read_bytes()),
    }


def verificar_fijacion(carpeta: Path, ruta: Path | None = None) -> list[str]:
    """Problemas de la copia `carpeta` frente a la fijación del host. Vacío = la llave encaja."""
    fijacion = cargar_fijacion(ruta)
    if fijacion is None:
        return ["sin fijación de la llave (backend/data/molchat_fijacion.json)"]
    if fijacion.get("schema") != ESQUEMA_FIJACION:
        return [f"fijación de esquema desconocido: {fijacion.get('schema')!r}"]
    try:
        datos = (carpeta / NOMBRE_MANIFIESTO).read_bytes()
    except OSError:
        return [f"falta {NOMBRE_MANIFIESTO}"]
    problemas: list[str] = []
    if sha256_bytes(datos) != fijacion.get("sha256_manifiesto"):
        problemas.append("el manifiesto no es el fijado")
    commit = str((manifiesto_de(carpeta).get("fuente") or {}).get("commit") or "")
    if commit != fijacion.get("commit"):
        problemas.append(f"el commit {commit[:12]} no es el fijado {str(fijacion.get('commit'))[:12]}")
    return problemas


def fijacion_resumen() -> dict:
    """Lo que `GET /molchat-host/status` cuenta de la fijación: origen y si es el oficial. Sin rutas."""
    fijacion = cargar_fijacion() or {}
    repositorio = str(fijacion.get("repositorio") or "")
    return {"repositorio": repositorio, "oficial": es_oficial(repositorio)}
