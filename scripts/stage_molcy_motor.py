#!/usr/bin/env python3
r"""Materializa el motor Molcy como PROGRAMA INDEPENDIENTE en `tools/molcy/`.

# Qué es y por qué se copia así

Molcy es el motor que dibuja los vídeos: un conjunto de scripts que se ejecutan DENTRO de Blender
(`blender -b --python scripts/maestro.py`), usan su API de Python (`bpy`) y activan Molecular Nodes. Blender y Molecular Nodes
son GPL-3.0-or-later, así que el motor se publica bajo **GPL-3.0-or-later** (decisión del propietario, 2026-10-04; el texto está en
su `LICENSE` y las razones en su `NOTICE.md`).

MolDesign (PolyForm Noncommercial) lo distribuye en el mismo instalador pero NO lo importa ni lo enlaza: lo ejecuta por subproceso
(`powershell -File correr_caso.ps1` → `blender -b ... maestro.py`) con rutas absolutas, y se comunican por ficheros (`scene.json`, la
geometría, el acta y el MP4). Es el mismo patrón que Open Babel (ADR 79). Ver `docs/95_ADR_MOTOR_MOLCY_EN_EL_INSTALADOR.md`.

# De dónde sale y por qué desde un COMMIT

El motor tiene su propio repositorio PÚBLICO (https://github.com/srcacahuate619/moldesign-molcy, GPL-3.0-or-later): es la fuente de verdad y la
oferta de código fuente que pide la GPL. Aquí se vendoriza desde un commit concreto de un clon suyo, leyendo los BLOBS de git (`git show
<commit>:<ruta>`), no el árbol de trabajo: el árbol cambia de saltos de línea según `core.autocrlf` de cada máquina y los bytes del manifiesto no
pueden depender de eso. El manifiesto registra la URL pública (sin credenciales), la rama y el commit. El repositorio de MolDesign marca
`tools/molcy/**` como `-text` (`.gitattributes`) para que git no los toque.

Se exige que el árbol de origen esté limpio en lo que se copia: copiar el commit sin avisar de que el árbol de trabajo tiene cambios
sin commitear habría vendorizado algo distinto de lo que el propietario ve en disco.

# Qué se copia y qué no

SÍ: lo que el producto ejecuta —`maestro.py`, `correr_caso.ps1` y los paquetes `formatos`, `guiones`, `marca`, `nucleo`, `salida`,
`sujetos`, `variables`—, la plantilla de arte, el emblema, `LICENSE` y `NOTICE.md`.
NO: las pruebas del motor (`scripts/pruebas/`), el README y los ficheros de git del repositorio público, y —si se vendoriza desde el repositorio
privado del autor— su interfaz Flask, sus herramientas de desarrollo y los casos y vídeos ya generados. Todo el conjunto pesa ~3 MB.

# Qué se comprueba

- el manifiesto describe EXACTAMENTE los ficheros de `tools/molcy/` (ninguno de más, ninguno de menos, cada SHA-256);
- `LICENSE` es el texto de la GPL-3.0-or-later (hash del texto con saltos LF);
- ningún .py/.ps1/.sh lleva una ruta absoluta de una máquina (`E:\blender.exe`, `D:\moldesign-build\...`): el motor que viaja no
  puede apuntar a la máquina del que lo escribió;
- están los ficheros que el detector de MolDesign exige.

# Uso

    git clone https://github.com/srcacahuate619/moldesign-molcy.git ..\moldesign-molcy        # (una vez) y `git pull` para actualizar
    python scripts/stage_molcy_motor.py --fuente ..\moldesign-molcy --write                   # vendoriza desde el HEAD de ese clon
    python scripts/stage_molcy_motor.py --check                                               # verifica tools/molcy/ contra su manifiesto
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import urllib.parse
from pathlib import Path

ROOT =Path(__file__).resolve().parents[1]
DESTINO = ROOT / "tools" / "molcy"


def _cargar_motor():
    """`backend/services/molcy/motor.py` por ruta, sin importar el paquete `services` (que arrastraría medio backend).

    Es la ÚNICA implementación de «qué es un motor íntegro»: el backend la usa antes de ejecutarlo, el verificador del bundle la usa
    sobre el runtime staged y este script la usa al vendorizar. Dos copias se desincronizarían.
    """
    ruta = ROOT / "backend" / "services" / "molcy" / "motor.py"
    spec = importlib.util.spec_from_file_location("moldesign_molcy_motor", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


_motor = _cargar_motor()
NOMBRE_MANIFIESTO = _motor.NOMBRE_MANIFIESTO
ESQUEMA = _motor.ESQUEMA
sha256_bytes = _motor.sha256_bytes
sha256_conjunto = _motor.sha256_conjunto
LICENCIA_SPDX = "GPL-3.0-or-later"
#: SHA-256 del texto oficial de la GPL-3.0-or-later con saltos LF (el de la distribución de Blender 5.2.2,
#: `license/spdx/GPL-3.0-or-later.txt`, normalizado).
SHA256_GPL3_LF = "8ceb4b9ee5adedde47b31e975c1d90c73ad27b6b165a1dcd80c7c545eb65b903"

INCLUIR_ARCHIVOS = (
    "LICENSE", "NOTICE.md", "scripts/maestro.py", "scripts/correr_caso.ps1",
    # Las fotos (2026-10-08): el lanzador, fuera de Blender, y el script que rinde un fotograma dentro de Blender.
    "scripts/correr_foto.py", "scripts/foto.py",
    "moldesign/assets/blender/plantilla_arte.blend",
)
INCLUIR_CARPETAS = (
    "scripts/formatos/", "scripts/guiones/", "scripts/marca/", "scripts/nucleo/", "scripts/salida/",
    "scripts/sujetos/", "scripts/variables/", "moldesign/assets/marca/",
)
#: Lo que el detector de MolDesign (`services/molcy/renderer.py`) exige para dar el motor por válido.
INDISPENSABLES = (
    "LICENSE", "scripts/maestro.py", "scripts/correr_caso.ps1", "moldesign/assets/blender/plantilla_arte.blend",
    "scripts/formatos/previsualizacion.py", "scripts/formatos/social_vertical.py", "scripts/formatos/biblioteca.py",
    "scripts/variables/cpu.py", "scripts/salida/render.py", "scripts/marca/cierre.py",
    "scripts/correr_foto.py", "scripts/foto.py", "scripts/variables/momentos.py", "scripts/salida/foto_final.py",
)
#: Dentro de una carpeta que sí viaja, lo que no: `preparar_emblema.py` genera el emblema (necesita un modelo de profundidad y un
#: recurso del repositorio de MolDesign, con una ruta de su máquina); no se ejecuta al renderizar, sólo se usó una vez.
EXCLUIR_ARCHIVOS = ("scripts/marca/preparar_emblema.py",)
EXCLUIDOS_DOCUMENTADOS = (
    "scripts/marca/preparar_emblema.py (herramienta de una sola vez)",
    "scripts/pruebas/ (pruebas del motor, en su repositorio)", "README.md, .gitignore y .gitattributes del repositorio público",
    "scripts/interfaz/, scripts/herramientas/, moldesign/scripts/, moldesign/cases/ (sólo existen en el repositorio privado del autor)",
)
SUFIJOS_DE_CODIGO = {".py", ".ps1", ".sh"}

#: Ruta absoluta de una máquina concreta: `E:\blender.exe`, `"E:\\proyect3d"`, `D:/moldesign-build`, `C:\Users\...`. La letra de
#: unidad va sola (no precedida de letra, dígito, guion bajo o barra invertida) y seguida de `:` y una barra: así no confunde
#: `http://` (la `p` va precedida de `t`) ni el `d:\d` de una expresión regular (la `d` va precedida de `\`).
RUTA_DE_MAQUINA = re.compile(r"(?<![A-Za-z0-9_\\])[A-Za-z]:[\\/]")


def rutas_de_maquina(texto: str) -> list[tuple[int, str]]:
    """(línea, fragmento) de cada ruta absoluta de una máquina en un texto de código."""
    halladas = []
    for numero, linea in enumerate(texto.splitlines(), 1):
        for m in RUTA_DE_MAQUINA.finditer(linea):
            halladas.append((numero, linea[m.start(): m.start() + 40].strip()))
    return halladas


def _git(fuente: Path, *args: str, texto: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(fuente), *args], capture_output=True, text=texto, check=False)


def _es_del_motor(ruta: str) -> bool:
    return ruta not in EXCLUIR_ARCHIVOS and (ruta in INCLUIR_ARCHIVOS or ruta.startswith(INCLUIR_CARPETAS))


def leer_del_commit(fuente: Path) -> tuple[dict[str, bytes], dict[str, str]]:
    """Blobs del HEAD de `fuente` (sólo lo que viaja) y de dónde salen. Aborta si el árbol tiene cambios en esas rutas."""
    commit = _git(fuente, "rev-parse", "HEAD")
    if commit.returncode != 0:
        raise SystemExit(f"{fuente} no es un repositorio git: {commit.stderr.strip()}")
    rama = _git(fuente, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    listado = _git(fuente, "ls-tree", "-r", "-z", "--name-only", "HEAD", texto=False).stdout.decode("utf-8")
    rutas = sorted(r for r in listado.split("\0") if r and _es_del_motor(r))
    faltan = [r for r in INDISPENSABLES if r not in rutas]
    if faltan:
        raise SystemExit(f"El commit no trae lo indispensable: {faltan}")
    sucio = _git(fuente, "status", "--porcelain", "--", *INCLUIR_ARCHIVOS, *INCLUIR_CARPETAS).stdout.strip()
    if sucio:
        raise SystemExit(
            "El árbol de origen tiene cambios sin commitear en lo que se copia; se vendoriza el COMMIT, no el árbol de trabajo. "
            f"Commitea o descarta:\n{sucio}"
        )
    contenido = {}
    for ruta in rutas:
        blob = _git(fuente, "show", f"HEAD:{ruta}", texto=False)
        if blob.returncode != 0:
            raise SystemExit(f"No se pudo leer {ruta} del commit: {blob.stderr.decode('utf-8', 'replace')}")
        contenido[ruta] = blob.stdout
    origen = {"commit": commit.stdout.strip(), "rama": rama}
    url = repositorio_publico(fuente)
    if url:
        origen["repositorio"] = url
    return contenido, origen


def repositorio_publico(fuente: Path) -> str | None:
    """URL del remoto `origin` SIN credenciales (la GPL pide poder obtener el código fuente: el manifiesto dice dónde está)."""
    salida = _git(fuente, "remote", "get-url", "origin")
    if salida.returncode != 0 or not salida.stdout.strip():
        return None
    partes = urllib.parse.urlsplit(salida.stdout.strip())
    if partes.scheme not in {"http", "https"} or not partes.hostname:
        return None  # una ruta local o un remoto ssh no sirve como oferta pública de código fuente
    anfitrion = partes.hostname + (f":{partes.port}" if partes.port else "")
    return urllib.parse.urlunsplit((partes.scheme, anfitrion, partes.path.removesuffix(".git"), "", ""))


def problemas_de_contenido(contenido: dict[str, bytes]) -> list[str]:
    """Rutas de máquina en el código, licencia equivocada o ficheros que faltan; vacío si todo está bien."""
    problemas = []
    for ruta in INDISPENSABLES:
        if ruta not in contenido:
            problemas.append(f"falta {ruta}")
    licencia = contenido.get("LICENSE")
    if licencia is not None and sha256_bytes(licencia.replace(b"\r\n", b"\n")) != SHA256_GPL3_LF:
        problemas.append("LICENSE no es el texto de la GPL-3.0-or-later")
    for ruta, datos in sorted(contenido.items()):
        if Path(ruta).suffix in SUFIJOS_DE_CODIGO:
            for linea, fragmento in rutas_de_maquina(datos.decode("utf-8", "replace")):
                problemas.append(f"{ruta}:{linea}: ruta de una máquina concreta: {fragmento!r}")
    return problemas


def construir_manifiesto(contenido: dict[str, bytes], origen: dict[str, str]) -> dict:
    archivos = {ruta: {"bytes": len(datos), "sha256": sha256_bytes(datos)} for ruta, datos in sorted(contenido.items())}
    return {
        "schema": ESQUEMA,
        "programa": "Molcy (motor de vídeo de MolDesign)",
        "licencia_spdx": LICENCIA_SPDX,
        "licencia_texto": "LICENSE",
        "fuente": {"proyecto": "moldesign-molcy", **origen},
        "invocacion": ("subproceso: vídeo, powershell -File scripts/correr_caso.ps1 → blender -b --python scripts/maestro.py; "
                       "fotos, python scripts/correr_foto.py → blender -b --python scripts/maestro.py --fotos y scripts/foto.py"),
        "no_se_enlaza": ("MolDesign no importa ningún módulo del motor ni el motor importa MolDesign; se comunican por "
                         "ficheros (scene.json, geometría, actas, MP4 y PNG)."),
        "requisitos": {"blender_minimo": "5.2", "molecular_nodes": "extensión de Blender Extensions, instalada por el usuario"},
        "excluidos": list(EXCLUIDOS_DOCUMENTADOS),
        "archivos": archivos,
        "sha256_conjunto": sha256_conjunto(archivos),
    }


def escribir(fuente: Path) -> None:
    contenido, origen = leer_del_commit(fuente)
    problemas = problemas_de_contenido(contenido)
    if problemas:
        raise SystemExit("El commit de origen no se puede distribuir:\n  " + "\n  ".join(problemas))
    if DESTINO.exists():
        if not (DESTINO / NOMBRE_MANIFIESTO).is_file():
            raise SystemExit(f"{DESTINO} existe y no es un motor Molcy vendorizado; no lo borro.")
        shutil.rmtree(DESTINO)
    for ruta, datos in contenido.items():
        destino = DESTINO / ruta
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(datos)
    manifiesto = construir_manifiesto(contenido, origen)
    (DESTINO / NOMBRE_MANIFIESTO).write_bytes((json.dumps(manifiesto, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(f"tools/molcy/: {len(contenido)} ficheros de {origen['rama']}@{origen['commit'][:8]} "
          f"({sum(len(d) for d in contenido.values()) / 1e6:.1f} MB)")


def verificar(destino: Path = DESTINO) -> list[str]:
    """Problemas de `destino` (lista vacía = íntegro): primero lo que dice el manifiesto —la misma comprobación que hace el backend
    antes de usar el motor— y, si cuadra, lo que sólo importa al distribuir: licencia, rutas de máquina, ficheros indispensables."""
    problemas = _motor.verificar_integridad(destino)
    if problemas:
        return problemas
    declarados = _motor.manifiesto_de(destino)["archivos"]
    return problemas_de_contenido({ruta: (destino / ruta).read_bytes() for ruta in declarados})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--fuente", type=Path, help="árbol git del motor del que vendorizar (con --write)")
    parser.add_argument("--write", action="store_true", help="vendoriza el HEAD de --fuente en tools/molcy/")
    parser.add_argument("--check", action="store_true", help="verifica tools/molcy/ contra su manifiesto")
    args = parser.parse_args(argv)
    if args.write:
        if not args.fuente:
            parser.error("--write necesita --fuente")
        escribir(args.fuente)
        return 0
    if args.check or not args.write:
        problemas = verificar()
        if problemas:
            print("tools/molcy/ NO es íntegro:\n  " + "\n  ".join(problemas), file=sys.stderr)
            return 1
        manifiesto = json.loads((DESTINO / NOMBRE_MANIFIESTO).read_text(encoding="utf-8"))
        print(f"tools/molcy/ íntegro: {len(manifiesto['archivos'])} ficheros, "
              f"{manifiesto['fuente']['rama']}@{manifiesto['fuente']['commit'][:8]}, {manifiesto['licencia_spdx']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
