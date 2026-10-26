"""El motor Molcy que viaja en el instalador: dónde está y si es el que se distribuyó.

Molcy es un programa independiente (GPL-3.0-or-later) que se ejecuta dentro de Blender; MolDesign no lo importa, lo ejecuta por
subproceso (ver `renderer._ejecutar`). Va en `tools/molcy/` con su manifiesto (`molcy-manifest.json`: SHA-256 de cada fichero, el
commit del que sale y su licencia), igual que Open Babel (ADR 79). Aquí sólo hay biblioteca estándar: lo usan el backend, la
verificación del bundle (`verify_desktop_bundle.py`, bajo el intérprete empaquetado) y el script que lo vendoriza.

Qué NO hace: no decide si Blender puede usarlo (eso es `renderer._detectar`) ni lo repara. Si un fichero no coincide con su manifiesto,
el detector se abstiene: un motor alterado produciría un vídeo cuya procedencia no sería la declarada.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

NOMBRE_MANIFIESTO = "molcy-manifest.json"
ESQUEMA = "moldesign.molcy-motor/1"


def sha256_bytes(datos: bytes) -> str:
    return hashlib.sha256(datos).hexdigest()


def sha256_conjunto(archivos: dict[str, dict]) -> str:
    """Huella del conjunto: rutas y hashes ordenados. Cambia si cambia un byte, un nombre o la lista."""
    cuerpo = "".join(f"{ruta}\0{archivos[ruta]['sha256']}\n" for ruta in sorted(archivos))
    return sha256_bytes(cuerpo.encode("utf-8"))


def directorio_incluido() -> Path | None:
    """Carpeta del motor que viaja con MolDesign, o None si este arranque no la tiene.

    Orden: `MOLDESIGN_MOLCY_DIR` (la que pasa Rust), la hermana de la carpeta de Open Babel (`tools/molcy` junto a
    `tools/openbabel`: así se resuelve aunque el contenedor no pase la variable) y, en un árbol de desarrollo, `tools/molcy` del
    repositorio. Cuenta como incluido sólo si trae su manifiesto.
    """
    candidatas: list[Path] = []
    if os.environ.get("MOLDESIGN_MOLCY_DIR"):
        candidatas.append(Path(os.environ["MOLDESIGN_MOLCY_DIR"]))
    if os.environ.get("MOLDESIGN_OPENBABEL_DIR"):
        candidatas.append(Path(os.environ["MOLDESIGN_OPENBABEL_DIR"]).parent / "molcy")
    candidatas.append(Path(__file__).resolve().parents[3] / "tools" / "molcy")
    for carpeta in candidatas:
        if carpeta.is_absolute() and (carpeta / NOMBRE_MANIFIESTO).is_file():
            return carpeta.resolve()
    return None


def motor_propio_permitido() -> bool:
    """¿Se acepta un motor distinto del incluido? Sólo para quien desarrolla el motor, con `MOLCY_PERMITIR_MOTOR_PROPIO=1` en el entorno.

    Ni la pantalla ni el instalador lo activan: el cierre de MolDesign (la firma al final de todo video) lo pone el motor, y un motor
    cualquiera podría no ponerlo. El motor es GPL: quien quiera ejecutar una versión modificada puede hacerlo con esta variable y sin tocar el
    instalador; lo que no existe es una vía en la aplicación.
    """
    return os.environ.get("MOLCY_PERMITIR_MOTOR_PROPIO") == "1"


def es_bytecode(ruta: Path, carpeta: Path) -> bool:
    """`__pycache__/*.pyc`: lo que el Python de Blender escribe junto al motor la primera vez que lo ejecuta.

    Es un derivado de los `.py` (que sí se verifican), no un fichero del motor. Medido (2026-10-04): tras el primer vídeo, 36 ficheros
    `.cpython-313.pyc` aparecieron en `tools/molcy/` y la comprobación declaraba el motor «alterado» (`sobra ...`). Blender no
    obedece `PYTHONDONTWRITEBYTECODE`, así que no se puede evitar que los escriba; en una instalación de sólo lectura (Store, Program Files) ni
    siquiera puede. Sólo se ignora el `.pyc` dentro de un `__pycache__`: un `.py`, o un `.pyc` fuera de él, siguen contando.
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
    """El manifiesto ya leído (para registrar procedencia: commit, licencia). Vacío si no se puede leer."""
    try:
        return json.loads((carpeta / NOMBRE_MANIFIESTO).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
