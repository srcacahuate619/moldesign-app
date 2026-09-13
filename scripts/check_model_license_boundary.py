#!/usr/bin/env python3
"""Verifica la licencia y el inventario de artefactos aprendidos.

El código y los modelos propios comparten PolyForm Noncommercial 1.0.0, pero
los pesos siguen necesitando un marcador local: enumera exactamente qué archivos
son artefactos aprendidos y evita confundirlos con pesos de terceros. El gate
también rechaza documentación que afirme que el repositorio no contiene pesos.

Uso:
    python scripts/check_model_license_boundary.py --write
    python scripts/check_model_license_boundary.py --check
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

# La consola de Windows usa cp1252: un carácter fuera de esa tabla convierte un
# informe en un traceback DESPUÉS de haber hecho el trabajo. Ver salida_consola.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from salida_consola import consola_utf8  # noqa: E402

consola_utf8()


RAIZ = Path(__file__).resolve().parents[1]
MARCADOR = "MODELS-LICENSE.md"

#: Extensiones que, versionadas, son artefactos APRENDIDOS por definición de
#: `LICENSE-MODELS` §1: «trained neural network weights (e.g. .pth, .pt, .onnx,
#: .safetensors files), database artifacts (e.g. .db, .sqlite files), learned
#: embeddings, fingerprint caches, calibration data, and any other learned or
#: derived data».
EXTENSIONES_APRENDIDAS = (
    ".pt", ".pth", ".ckpt", ".safetensors", ".onnx", ".h5", ".gguf",
    ".xgb", ".pkl", ".joblib",
)

#: Artefactos de TERCEROS: `LICENSE-MODELS` los excluye expresamente («THIRD-PARTY
#: EXCLUSION»), así que declararlos como Modelos propios sería reclamar autoría
#: ajena — el error opuesto y peor.
DE_TERCEROS = ("rescoring/RTMScore/",)

#: ÁRBOLES QUE NO SE MARCAN EN SITIO, y por qué.
#:
#: `scripts/artifacts_science/` son artefactos SELLADOS: cada experimento lleva
#: su manifiesto con `assets_hashes`, y la regla 5 de `AGENTS.md` prohíbe
#: tocarlos. Escribir un marcador dentro no rompería ningún hash —el sellado es
#: por archivo y los `fold_models/` no están en él— pero sí rompería la regla, y
#: una regla que se salta «sólo esta vez» deja de proteger.
#:
#: Tampoco está claro que deban tratarse como Modelos restringidos: son la
#: EVIDENCIA de un experimento sellado, y publicarlos es justamente lo que hace
#: reproducible el resultado. Restringir su redistribución iría contra el motivo
#: por el que existen.
#:
#: Así que no se marcan y tampoco se dan por resueltos: el gate los ENUMERA en
#: cada ejecución, para que la decisión esté a la vista de quien puede tomarla.
SIN_MARCADOR_EN_SITIO: dict[str, str] = {
    "scripts/artifacts_science/": (
        "árbol sellado (AGENTS.md regla 5); además es evidencia científica "
        "publicada a propósito, no pesos de producto"
    ),
}


def _motivo_sin_marcador(directorio: str) -> str:
    for prefijo, motivo in SIN_MARCADOR_EN_SITIO.items():
        if directorio.startswith(prefijo.rstrip("/")):
            return motivo
    return "sin motivo declarado"

#: Documentos normativos que no pueden afirmar lo contrario de lo que hay.
DOCUMENTOS_NORMATIVOS = (
    "docs/78_DECISION_DISTRIBUCION_DE_PESOS_Y_RUNTIME.md",
    "README.md",
    "AGENTS.md",
)

#: Formas de afirmar «aquí no hay pesos». Se comprueban sólo si SÍ los hay.
NEGACIONES = (
    re.compile(r"ning[úu]n peso entrenado", re.IGNORECASE),
    re.compile(r"sin pesos entrenados", re.IGNORECASE),
    re.compile(r"no (?:se )?(?:incluyen|lleva|contiene) pesos", re.IGNORECASE),
)


def versionados() -> list[str]:
    salida = subprocess.run(
        ["git", "ls-files"], cwd=RAIZ, capture_output=True, text=True, check=True
    ).stdout
    return [linea.strip().replace("\\", "/") for linea in salida.splitlines() if linea.strip()]


def es_aprendido(ruta: str) -> bool:
    if any(ruta.startswith(prefijo) for prefijo in DE_TERCEROS):
        return False
    return ruta.lower().endswith(EXTENSIONES_APRENDIDAS)


def por_directorio(rutas: list[str]) -> dict[str, list[str]]:
    grupos: dict[str, list[str]] = {}
    for ruta in rutas:
        if es_aprendido(ruta):
            grupos.setdefault(ruta.rsplit("/", 1)[0], []).append(ruta.rsplit("/", 1)[1])
    return {d: sorted(f) for d, f in sorted(grupos.items())}


def texto_marcador(directorio: str, archivos: list[str]) -> str:
    """Marcador generado: enumera los artefactos y su licencia efectiva."""
    profundidad = directorio.count("/") + 1
    subir = "../" * profundidad
    lista = "\n".join(f"- `{nombre}`" for nombre in archivos)
    return f"""<!-- GENERADO por scripts/check_model_license_boundary.py. No editar a mano. -->

# Artefactos aprendidos de MolDesign

Este directorio contiene **{len(archivos)} artefacto(s) aprendido(s)** propio(s):

{lista}

Se rigen por [`{subir}LICENSE-MODELS`]({subir}LICENSE-MODELS), que aplica la
licencia **PolyForm Noncommercial 1.0.0**: uso, estudio, modificación y
redistribución no comerciales están permitidos; cualquier uso comercial exige
un acuerdo escrito separado con MolDesign.

Los pesos de terceros —Qwen, ESMFold, TabPFN, RTMScore— conservan su propia
licencia y no quedan relicenciados por este marcador. Consulte
[`{subir}frontend/public/legal/THIRD_PARTY_NOTICES.md`]({subir}frontend/public/legal/THIRD_PARTY_NOTICES.md).
"""


def comprobar_documentos(hay_pesos: bool) -> list[str]:
    if not hay_pesos:
        return []
    problemas: list[str] = []
    for relativa in DOCUMENTOS_NORMATIVOS:
        ruta = RAIZ / relativa
        if not ruta.is_file():
            continue
        for numero, linea in enumerate(
            ruta.read_text(encoding="utf-8", errors="replace").splitlines(), 1
        ):
            if any(patron.search(linea) for patron in NEGACIONES):
                problemas.append(f"{relativa}:{numero}: {linea.strip()[:110]}")
    return problemas


# ── AUTOTEST: un guardián que no demuestra que ve no sirve ───────────────

_DEBE_VER_APRENDIDO = (
    "rescoring/artifacts/pose_selector_v06.xgb",
    "rescoring/artifacts/gpu/model_a.joblib",
    "a/b/gnn_v2_cl_best.pt",
    "x/y.safetensors",
)
_NO_DEBE_VER_APRENDIDO = (
    "rescoring/artifacts/model-manifest.json",
    "backend/api/main.py",
    "rescoring/RTMScore/model/pesos.pt",   # terceros, MIT
    "docs/PAPER_UMS.pdf",
)
_DEBE_VER_NEGACION = (
    "el repositorio público no lleva ningún peso entrenado",
    "Código y manifiestos, sin pesos entrenados",
)
_NO_DEBE_VER_NEGACION = (
    "los pesos entrenados se distribuyen bajo LICENSE-MODELS",
    "ningún peso de terceros se relicencia",
)


def autotest() -> None:
    for muestra in _DEBE_VER_APRENDIDO:
        if not es_aprendido(muestra):
            raise SystemExit(
                f"AUTOTEST FALLIDO: no reconoce `{muestra}` como artefacto aprendido."
            )
    for muestra in _NO_DEBE_VER_APRENDIDO:
        if es_aprendido(muestra):
            raise SystemExit(f"AUTOTEST FALLIDO: marca de más `{muestra}`.")
    for muestra in _DEBE_VER_NEGACION:
        if not any(p.search(muestra) for p in NEGACIONES):
            raise SystemExit(f"AUTOTEST FALLIDO: no ve la negación en `{muestra}`.")
    for muestra in _NO_DEBE_VER_NEGACION:
        if any(p.search(muestra) for p in NEGACIONES):
            raise SystemExit(f"AUTOTEST FALLIDO: negación falsa en `{muestra}`.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    grupo = parser.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--write", action="store_true")
    grupo.add_argument("--check", action="store_true")
    args = parser.parse_args()

    autotest()
    todos = por_directorio(versionados())
    grupos = {
        d: f for d, f in todos.items()
        if _motivo_sin_marcador(d) == "sin motivo declarado"
    }
    enumerados = {d: f for d, f in todos.items() if d not in grupos}
    total = sum(len(v) for v in grupos.values())
    total_enumerado = sum(len(v) for v in enumerados.values())

    if args.write:
        for directorio, archivos in grupos.items():
            destino = RAIZ / directorio / MARCADOR
            destino.write_text(texto_marcador(directorio, archivos), encoding="utf-8", newline="\n")
            print(f"  {directorio}/{MARCADOR}  ({len(archivos)} artefactos)")
        print(f"\n{total} artefactos aprendidos marcados en {len(grupos)} directorios.")
        for directorio, archivos in enumerados.items():
            motivo = _motivo_sin_marcador(directorio)
            print(f"  SIN MARCAR  {directorio}  ({len(archivos)} artefactos)")
            print(f"              {motivo}")
        problemas = comprobar_documentos(total > 0)
        if problemas:
            print(
                "\nAVISO: hay documentos que afirman lo contrario de lo que hay.\n  - "
                + "\n  - ".join(problemas)
            )
        return 0

    fallos: list[str] = []
    for directorio, archivos in grupos.items():
        marcador = RAIZ / directorio / MARCADOR
        if not marcador.is_file():
            fallos.append(
                f"F1 `{directorio}/` tiene {len(archivos)} artefacto(s) aprendido(s) "
                f"y ningún `{MARCADOR}`. Quien clone no podría conocer sus términos ni procedencia."
            )
            continue
        esperado = texto_marcador(directorio, archivos)
        if marcador.read_text(encoding="utf-8") != esperado:
            fallos.append(
                f"F2 `{directorio}/{MARCADOR}` no enumera los artefactos que hay. "
                "Regenera con --write y revisa el diff."
            )

    problemas = comprobar_documentos(total > 0)
    if problemas:
        fallos.append(
            f"F3 hay {total} artefactos aprendidos versionados, y estos documentos "
            "afirman que no los hay:\n    - " + "\n    - ".join(problemas)
        )

    if fallos:
        print("Frontera de licencia de los artefactos aprendidos ROTA:", file=sys.stderr)
        for fallo in fallos:
            print(f"  {fallo}", file=sys.stderr)
        print(
            "\nContexto: docs/78_DECISION_DISTRIBUCION_DE_PESOS_Y_RUNTIME.md",
            file=sys.stderr,
        )
        return 1

    print(
        f"Frontera de licencia verificada: {total} artefactos aprendidos en "
        f"{len(grupos)} directorios, todos con `{MARCADOR}`; "
        "ningún documento normativo los niega."
    )
    if enumerados:
        print(
            f"\n{total_enumerado} artefactos más viven en árboles que NO se marcan "
            "en sitio. No es un olvido: es una decisión abierta, y se enumera "
            "para que esté a la vista de quien tiene que tomarla."
        )
        for directorio, archivos in enumerados.items():
            print(f"  {directorio}  ({len(archivos)})  — {_motivo_sin_marcador(directorio)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
