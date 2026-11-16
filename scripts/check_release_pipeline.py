"""Comprueba que ningún build Tauri pueda saltarse el runtime gate."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


#: Las dieciséis puertas de `beforeBuildCommand`, en su orden. Sale de `frontend/src-tauri/tauri.conf.json` y de
#: AGENTS.md («Construir»): antes este comprobador exigía sólo nueve y una pasada en verde no decía nada de las otras
#: siete (`check:runtime-arbol`, `check:openbabel-fuente`, `check:molcy-motor`, `check:openbabel`,
#: `check:evaluation-runtime`, `check:exported-api-url`, `check:no-remote-assets`). La revisión final de 1.0.4 (B-11)
#: las quitó una a una en memoria y el comprobador seguía pasando. Que el orden importa, y por qué:
#: - las que miran fuentes y manifiestos van ANTES del staging: si un peso o una corrida dorada cambió, el build no
#:   debe llegar siquiera a copiar el runtime;
#: - `check:openbabel`, `verify:desktop-runtime`, `check:evaluation-runtime` y `check:dossier-embebido` miran el
#:   ARTEFACTO, así que sólo pueden correr DESPUÉS de `stage:desktop` (restricción 1 de AGENTS.md);
#: - las dos últimas miran el export estático, así que van después de `build:desktop`.
REQUERIDAS = [
    "npm run check:runtime-arbol",
    "npm run check:csp",
    "npm run check:rescoring-manifest",
    "npm run check:m5-manifest",
    "npm run check:goldens",
    "npm run check:pesos-stacking",
    "npm run check:openbabel-fuente",
    "npm run check:molcy-motor",
    "npm run stage:desktop",
    "npm run check:openbabel",
    "npm run verify:desktop-runtime",
    "npm run check:evaluation-runtime",
    "npm run check:dossier-embebido",
    "npm run build:desktop",
    "npm run check:exported-api-url",
    "npm run check:no-remote-assets",
]


def verificar_comandos(commands: list[str]) -> None:
    """Falla si falta una de las dieciséis puertas o si alguna cambió de orden. Pura: se puede atacar en memoria."""
    positions = []
    for command in REQUERIDAS:
        if command not in commands:
            raise RuntimeError(f"beforeBuildCommand no ejecuta `{command}`.")
        positions.append(commands.index(command))
    if positions != sorted(positions):
        raise RuntimeError("El release gate está desordenado: staging y verificación deben preceder al build.")


def autotest() -> None:
    """El guardián tiene que demostrar que ve (restricción 2 de AGENTS.md): sin una puerta, o con dos cambiadas de sitio, falla."""
    verificar_comandos(list(REQUERIDAS))
    for i, quitada in enumerate(REQUERIDAS):
        try:
            verificar_comandos(REQUERIDAS[:i] + REQUERIDAS[i + 1:])
        except RuntimeError:
            continue
        raise SystemExit(f"autotest: el comprobador no ve que falta `{quitada}`.")
    for a, b in ((0, 1), (7, 8), (8, 9), (13, 14), (14, 15)):
        cambiada = list(REQUERIDAS)
        cambiada[a], cambiada[b] = cambiada[b], cambiada[a]
        try:
            verificar_comandos(cambiada)
        except RuntimeError:
            continue
        raise SystemExit(f"autotest: el comprobador no ve que `{REQUERIDAS[a]}` y `{REQUERIDAS[b]}` cambiaron de orden.")
    print(f"autotest: ve la falta de cada una de las {len(REQUERIDAS)} puertas y los cambios de orden.")


def main() -> None:
    package = json.loads((ROOT / "frontend" / "package.json").read_text(encoding="utf-8"))
    tauri = json.loads(
        (ROOT / "frontend" / "src-tauri" / "tauri.conf.json").read_text(encoding="utf-8")
    )

    before_build = tauri.get("build", {}).get("beforeBuildCommand", "")
    commands = [part.strip() for part in before_build.split("&&")]
    verificar_comandos(commands)
    extra = [c for c in commands if c not in REQUERIDAS]
    if extra:
        raise RuntimeError(
            "beforeBuildCommand tiene comandos que este comprobador no conoce: "
            + ", ".join(f"`{c}`" for c in extra)
            + ". Añádelos a REQUERIDAS con su lugar en el orden."
        )

    resources = tauri.get("bundle", {}).get("resources", {})
    if resources.get("resources/") != "":
        raise RuntimeError("Tauri no empaqueta `src-tauri/resources/` en la raíz de recursos.")

    scripts = package.get("scripts", {})
    if "bundle_helper.py" not in scripts.get("stage:desktop", ""):
        raise RuntimeError("`stage:desktop` ya no usa el constructor allow-list del runtime.")
    if "verify_desktop_bundle.py" not in scripts.get("verify:desktop-runtime", ""):
        raise RuntimeError("`verify:desktop-runtime` ya no ejecuta la verificación integral.")
    if "check_stacking_weights_ui.py" not in scripts.get("check:pesos-stacking", ""):
        raise RuntimeError(
            "`check:pesos-stacking` ya no compara la interfaz con los pesos efectivos."
        )
    if "verify_embedded_dossier.py" not in scripts.get("check:dossier-embebido", ""):
        raise RuntimeError(
            "`check:dossier-embebido` ya no pide el dossier al runtime empaquetado."
        )
    tauri_build = scripts.get("tauri:build", "")
    if "tauri build" not in tauri_build or "tauri.conf.prod.json" not in tauri_build:
        raise RuntimeError("`tauri:build` no apunta al build de producción Tauri.")

    print("Release pipeline verificado: stage -> runtime gate -> frontend -> Tauri/NSIS.")


if __name__ == "__main__":
    import sys

    if "--autotest" in sys.argv[1:]:
        autotest()
    main()
