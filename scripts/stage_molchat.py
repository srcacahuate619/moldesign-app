#!/usr/bin/env python3
r"""Materializa el sidecar MolChat como PROGRAMA INDEPENDIENTE en `tools/molchat/`.

# Qué es y por qué se copia así

MolChat es el asistente de laboratorio: un servicio Python en loopback con su
UI estática, publicado bajo **GPL-3.0-or-later** en su propio repositorio
público (https://github.com/srcacahuate619/moldesign-molchat).

MolDesign (PolyForm Noncommercial) lo distribuye en el mismo instalador pero
NO lo importa ni lo enlaza: lo ejecuta por subproceso
(bootstrap del paquete `src` en puerto loopback efímero) y se comunican
por HTTP versionado (`moldesign.molchat/1`). Es el mismo patrón que el motor
Molcy (ADR 92 → 95) y que Open Babel (ADR 79). Ver
`docs/100_ADR_MOLCHAT_EXTERNO.md`.

# De dónde sale y quién decide qué viaja

Lo que viaja lo decide el PRODUCTO, no este script: `scripts/make_manifest.py`
del repositorio fuente genera la copia vendorizable (paquete, build de UI,
`LICENSE`, `NOTICE.md`, `pyproject.toml`) y su manifiesto desde un commit
limpio. Este script lo invoca por subproceso y después verifica el resultado
con el verificador local (`services/molchat_host/manifest.py`, espejo de
`services/molcy/motor.py`). Una sola implementación de "qué viaja" (allí);
una sola de "qué es íntegro" (aquí, la que el lanzador usa antes de arrancar).

El manifiesto registra la URL pública (sin credenciales), la rama y el
commit. El repositorio marca `tools/molchat/**` como `-text`
(`.gitattributes`) para que git no toque sus bytes.

# Qué se comprueba

- el manifiesto describe EXACTAMENTE los ficheros de `tools/molchat/`
  (ninguno de más, ninguno de menos, cada SHA-256 y el conjunto);
- el manifiesto declara el esquema y el contrato que este host habla;
- `LICENSE` es el texto de la GPL-3.0-or-later (hash del texto con saltos LF);
- ningún fichero de código lleva una ruta absoluta de una máquina concreta;
- están los ficheros que el lanzador exige (entrada del sidecar, UI, licencia).

# La fijación

Vendorizar en `tools/molchat/` también escribe `backend/data/molchat_fijacion.json`:
el commit, el origen (`repositorio`, `oficial`) y el SHA-256 del manifiesto que
el host espera. El lanzador no arranca una copia incluida que no coincida con
esa fijación (ver `services/molchat_host/manifest.py`). Una versión propia de
MolChat se fija igual: su origen queda como `oficial: false`.

`--destino <carpeta>` vendoriza a una carpeta de prueba y NO toca ni la copia
incluida ni la fijación: para probar un cambio de MolChat sin cambiar lo que
MolDesign publica.

# Uso

    git clone https://github.com/srcacahuate619/moldesign-molchat.git ..\moldesign-molchat  # (una vez) y `git pull` para actualizar
    python scripts/stage_molchat.py --fuente ..\moldesign-molchat --write                  # vendoriza el HEAD de ese clon y fija la llave
    python scripts/stage_molchat.py --check                                                # verifica tools/molchat/ y su fijación
    python scripts/stage_molchat.py --fuente <clon> --write --destino <carpeta>            # prueba: no toca tools/molchat/ ni la fijación
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESTINO = ROOT / "tools" / "molchat"


def _cargar_manifiesto():
    """`backend/services/molchat_host/manifest.py` por ruta, sin importar el
    paquete `services` (que arrastraría medio backend).

    Es la ÚNICA implementación de «qué es una copia íntegra»: el lanzador la
    usa antes de arrancar el sidecar, la verificación del bundle la usa sobre
    el runtime staged y este script la usa al vendorizar. Dos copias se
    desincronizarían.
    """
    ruta = ROOT / "backend" / "services" / "molchat_host" / "manifest.py"
    spec = importlib.util.spec_from_file_location("moldesign_molchat_manifest", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


_manifiesto = _cargar_manifiesto()
NOMBRE_MANIFIESTO = _manifiesto.NOMBRE_MANIFIESTO
ESQUEMA = _manifiesto.ESQUEMA
CONTRATO_SIDECAR = _manifiesto.CONTRATO_SIDECAR
LICENCIA_SPDX = "GPL-3.0-or-later"
#: SHA-256 del texto oficial de la GPL-3.0-or-later con saltos LF (el mismo
#: texto que clava `stage_molcy_motor.py`: un hecho sobre la licencia).
SHA256_GPL3_LF = "8ceb4b9ee5adedde47b31e975c1d90c73ad27b6b165a1dcd80c7c545eb65b903"

#: Lo que el lanzador (`services/molchat_host/launcher.py`) exige para dar la
#: copia por válida: cadena de entrada, servidor del sidecar, UI y licencia.
#: El productor (`make_manifest.py` en el repo fuente) ya lo exige al escribir;
#: aquí se re-exige para que un directorio armado a mano no pase el `--check`.
INDISPENSABLES = (
    "LICENSE", "NOTICE.md", "pyproject.toml",
    "src/molchat_agent/__init__.py",
    "src/molchat_agent/__main__.py",
    "src/molchat_agent/cli.py",
    "src/molchat_agent/server/serve.py",
    "src/molchat_agent/server/app.py",
    "ui/dist/index.html",
)
SUFIJOS_DE_CODIGO = {".py", ".ps1", ".sh", ".js", ".html", ".css", ".json", ".toml", ".md"}

#: Ruta absoluta de una máquina concreta. Espejo del detector de
#: `scripts/check_secrets.py` del repositorio MolChat, incluidas sus dos
#: exclusiones de precisión: un `\\u`+cuatro hexadecimales es un escape
#: unicode JS (los bundles minificados están llenos) y un servidor UNC real
#: empieza por alfanumérico. Duplicado a propósito: en un clon de MolDesign
#: no está el repo fuente y el `--check` debe bastarse solo.
RUTA_DE_MAQUINA = re.compile(
    r"(?<![A-Za-z])[A-Za-z]:[/\\]|\\{2,4}(?!u[0-9a-fA-F]{4})[A-Za-z0-9][\w.$-]*\\+[\w.$-]+|/(?:home|Users)/[\w.~-]+"
)


def rutas_de_maquina(texto: str) -> list[tuple[int, str]]:
    """(línea, fragmento) de cada ruta absoluta de una máquina en un texto de código."""
    halladas = []
    for numero, linea in enumerate(texto.splitlines(), 1):
        for m in RUTA_DE_MAQUINA.finditer(linea):
            halladas.append((numero, linea[m.start(): m.start() + 40].strip()))
    return halladas


def problemas_de_contenido(contenido: dict[str, bytes]) -> list[str]:
    """Licencia equivocada, rutas de máquina o ficheros que faltan; vacío si todo está bien."""
    problemas = []
    for ruta in INDISPENSABLES:
        if ruta not in contenido:
            problemas.append(f"falta {ruta}")
    licencia = contenido.get("LICENSE")
    if licencia is not None and _manifiesto.sha256_bytes(licencia.replace(b"\r\n", b"\n")) != SHA256_GPL3_LF:
        problemas.append("LICENSE no es el texto de la GPL-3.0-or-later")
    for ruta, datos in sorted(contenido.items()):
        if Path(ruta).suffix not in SUFIJOS_DE_CODIGO:
            continue
        try:
            texto = datos.decode("utf-8")
        except UnicodeDecodeError:
            continue
        for linea, fragmento in rutas_de_maquina(texto):
            problemas.append(f"{ruta}:{linea}: ruta de una máquina concreta: {fragmento!r}")
    return problemas


def problemas_de_forma(manifiesto: dict) -> list[str]:
    """El manifiesto declara lo que este host necesita: esquema, contrato, versión y origen."""
    problemas = []
    for clave in ("schema", "programa", "version", "licencia_spdx", "fuente",
                  "invocacion", "no_se_enlaza", "contrato", "archivos", "sha256_conjunto"):
        if clave not in manifiesto:
            problemas.append(f"el manifiesto no trae {clave}")
    if problemas:
        return problemas
    if manifiesto["schema"] != ESQUEMA:
        problemas.append(f"schema {manifiesto['schema']!r}: este host sólo conoce {ESQUEMA}")
    contrato = manifiesto["contrato"]
    if not isinstance(contrato, dict) or contrato.get("agente_plataforma") != CONTRATO_SIDECAR:
        problemas.append("contrato.agente_plataforma desconocido: este sidecar no arranca aquí")
    fuente = manifiesto["fuente"]
    if not isinstance(fuente, dict) or not re.fullmatch(r"[0-9a-f]{40}", str(fuente.get("commit", ""))):
        problemas.append("fuente.commit no es un commit (40 hex)")
    return problemas


def _es_la_copia_incluida(destino: Path) -> bool:
    """¿Es `destino` la copia que MolDesign publica? Compara rutas resueltas: una ruta
    escrita de otra forma en la línea de órdenes no puede saltarse la fijación."""
    return destino.resolve() == DESTINO.resolve()


def verificar(destino: Path | None = None) -> list[str]:
    """Problemas de `destino` (lista vacía = íntegro y apto): primero lo que
    dice el manifiesto —la misma comprobación que hace el lanzador antes de
    arrancar—, después lo que sólo importa al distribuir (forma del manifiesto,
    licencia, rutas de máquina, ficheros indispensables) y, si `destino` es la
    copia incluida, que encaje con su fijación."""
    destino = DESTINO if destino is None else destino
    problemas = _manifiesto.verificar_integridad(destino)
    if problemas:
        return problemas
    manifiesto = _manifiesto.manifiesto_de(destino)
    problemas = problemas_de_forma(manifiesto)
    if problemas:
        return problemas
    declarados = manifiesto["archivos"]
    problemas = problemas_de_contenido({ruta: (destino / ruta).read_bytes() for ruta in declarados})
    if problemas or not _es_la_copia_incluida(destino):
        return problemas
    return _manifiesto.verificar_fijacion(destino)


def _escribir_fijacion(carpeta: Path) -> dict:
    """Escribe la fijación de la copia `carpeta` (commit, origen y SHA-256 del manifiesto).

    Reemplazo atómico: un fallo a mitad no deja una fijación a medias.
    """
    fijacion = _manifiesto.fijacion_para(carpeta)
    ruta = _manifiesto.FIJACION
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.parent / (ruta.name + ".tmp")
    temporal.write_text(json.dumps(fijacion, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporal, ruta)
    return fijacion


def escribir(fuente: Path, min_moldesign: str = "", destino: Path | None = None) -> None:
    """Vendoriza el HEAD de `fuente` en `destino` (por defecto `tools/molchat/`) vía su
    productor. Sólo la copia incluida actualiza la fijación de la llave."""
    destino = DESTINO if destino is None else destino
    incluida = _es_la_copia_incluida(destino)
    if not (fuente / ".git").exists():
        raise SystemExit(f"{fuente} no es un repositorio git")
    productor = fuente / "scripts" / "make_manifest.py"
    if not productor.is_file():
        raise SystemExit(
            f"{fuente} no trae scripts/make_manifest.py: ese commit es anterior "
            "al productor del manifiesto (Fase 6.1); actualiza la fuente.")
    if destino.exists() and not (destino / NOMBRE_MANIFIESTO).is_file():
        raise SystemExit(f"{destino} existe y no es un MolChat vendorizado; no lo borro.")
    # Nunca pedir al productor que borre la copia activa: si Tauri mantiene el
    # directorio abierto, Windows puede detener rmtree después de borrar archivos.
    temporal = Path(tempfile.mkdtemp(prefix=".molchat-stage-", dir=destino.parent))
    preparado, anterior = temporal / "nuevo", temporal / "anterior"
    instalado = False
    try:
        cmd = [sys.executable, str(productor), "--write",
               "--fuente", str(fuente), "--out", str(preparado)]
        if min_moldesign:
            cmd += ["--min-moldesign", min_moldesign]
        hecho = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if hecho.returncode != 0:
            raise SystemExit(f"el productor rechazó la fuente:\n{hecho.stderr.strip() or hecho.stdout.strip()}")
        problemas = verificar(preparado)
        if problemas:
            raise SystemExit("lo producido no verifica:\n  " + "\n  ".join(problemas))
        if destino.exists():
            try:
                destino.rename(anterior)
            except OSError as exc:
                raise SystemExit(f"no se pudo apartar la copia activa; cierra MolChat y vuelve a intentar: {exc}") from exc
        try:
            preparado.rename(destino)
            instalado = True
        except OSError:
            if anterior.exists():
                anterior.rename(destino)
            raise
    finally:
        # Si falló la restauración, el respaldo se conserva para recuperación.
        if not anterior.exists() or instalado:
            shutil.rmtree(temporal, ignore_errors=True)
    manifiesto = json.loads((destino / NOMBRE_MANIFIESTO).read_text(encoding="utf-8"))
    if not incluida:
        print(f"{destino}: v{manifiesto['version']}, "
              f"{manifiesto['fuente']['rama']}@{manifiesto['fuente']['commit'][:8]}, "
              f"{len(manifiesto['archivos'])} ficheros (prueba: tools/molchat/ y la fijación no cambian)")
        return
    fijacion = _escribir_fijacion(destino)
    print(f"tools/molchat/: v{manifiesto['version']}, "
          f"{manifiesto['fuente']['rama']}@{manifiesto['fuente']['commit'][:8]}, "
          f"{len(manifiesto['archivos'])} ficheros; fijación "
          f"{'oficial' if fijacion['oficial'] else 'no oficial'}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--fuente", type=Path, help="clon de moldesign-molchat del que vendorizar (con --write)")
    parser.add_argument("--write", action="store_true", help="vendoriza el HEAD de --fuente en tools/molchat/")
    parser.add_argument("--check", action="store_true", help="verifica tools/molchat/ contra su manifiesto")
    parser.add_argument("--min-moldesign", default="",
                        help="MolDesign mínimo con superficie de host (al manifiesto)")
    parser.add_argument("--destino", type=Path, default=None,
                        help="carpeta de prueba: vendoriza o verifica allí sin tocar tools/molchat/ ni la fijación")
    args = parser.parse_args(argv)
    if args.write:
        if not args.fuente:
            parser.error("--write necesita --fuente")
        escribir(args.fuente, args.min_moldesign, args.destino)
        return 0
    if args.check or not args.write:
        destino = args.destino or DESTINO
        problemas = verificar(args.destino)
        if problemas:
            print(f"{destino} NO es íntegro:\n  " + "\n  ".join(problemas), file=sys.stderr)
            return 1
        manifiesto = json.loads((destino / NOMBRE_MANIFIESTO).read_text(encoding="utf-8"))
        print(f"{destino} íntegro: v{manifiesto['version']}, "
              f"{manifiesto['fuente']['rama']}@{manifiesto['fuente']['commit'][:8]}, "
              f"{manifiesto['licencia_spdx']}, {len(manifiesto['archivos'])} ficheros")
    return 0


if __name__ == "__main__":
    sys.exit(main())
