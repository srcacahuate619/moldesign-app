"""Comprueba que ningún build Tauri pueda saltarse el runtime gate."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    package = json.loads((ROOT / "frontend" / "package.json").read_text(encoding="utf-8"))
    tauri = json.loads(
        (ROOT / "frontend" / "src-tauri" / "tauri.conf.json").read_text(encoding="utf-8")
    )

    before_build = tauri.get("build", {}).get("beforeBuildCommand", "")
    commands = [part.strip() for part in before_build.split("&&")]
    required = [
        "npm run check:csp",
        "npm run check:rescoring-manifest",
        # Gates §10.1-10.2 del ADR 75 y punto 6 de la Fase 0 del doc 74. Van
        # ANTES del staging a propósito: si un peso cambió sin regenerar el
        # manifiesto, o una corrida dorada cambió de significado, el build no
        # debe llegar siquiera a copiar el runtime.
        "npm run check:m5-manifest",
        "npm run check:goldens",
        # Los pesos que la interfaz muestra tienen que ser los que el backend
        # aplica. Las siete familias divergian el 2026-09-04, incluida una que
        # atribuia a CL-GNN el peso de la GNN legacy.
        "npm run check:pesos-stacking",
        "npm run stage:desktop",
        "npm run verify:desktop-runtime",
        # Paso 4 de la Fase 0 del doc 74: el dossier del backend EMPAQUETADO,
        # pedido por su API pública, contra las corridas doradas y contra el que
        # emite el backend de desarrollo. Va DESPUÉS del staging porque verifica
        # lo que se copió, y antes del build porque un instalador cuyo dossier
        # difiere del que se probó no debería llegar a existir.
        "npm run check:dossier-embebido",
        "npm run build:desktop",
    ]
    positions = []
    for command in required:
        if command not in commands:
            raise RuntimeError(f"beforeBuildCommand no ejecuta `{command}`.")
        positions.append(commands.index(command))
    if positions != sorted(positions):
        raise RuntimeError("El release gate está desordenado: staging y verificación deben preceder al build.")

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
    main()
