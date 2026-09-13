#!/usr/bin/env python3
"""Comprueba que la publicación cumple la oferta de fuente de la GPLv2.

# Qué obligación cubre

Open Babel viaja en el instalador bajo **GPL-2.0-only**. La GPLv2 §3 obliga a
acompañar el binario del **código fuente correspondiente** —el de la versión
exacta distribuida— o de una oferta escrita válida para obtenerlo.

Enlazar a un repositorio de GitHub no basta por sí solo: el enlace apunta a lo
que haya hoy en esa rama, no a los bytes que se compilaron. Si mañana el
repositorio desaparece, o el commit se reescribe, la publicación ya distribuida
se queda sin su fuente correspondiente y la obligación sigue viva.

Por eso cada publicación adjunta los archivos, y esto comprueba que están.

# Qué NO hace

No descarga nada. Un comprobador que se va a la red no puede correr en el
momento del sellado ni sobre una máquina sin conexión, que son justo los dos
sitios donde tiene que correr. Prepara los artefactos quien publica; esto
verifica que los preparó y que sus hashes son los declarados.

Tampoco es asesoría jurídica. Es la comprobación de ingeniería que hace
verificable un requisito que, si no, se cumpliría de memoria.

# Uso

    python scripts/verify_release_source_offer.py --plantilla
        escribe `dist/source-offer/openbabel-source-offer.json` con los datos
        que ya se conocen y los hashes vacíos, para rellenarlos al preparar los
        archivos de fuente.

    python scripts/verify_release_source_offer.py --check
        falla si falta un artefacto o si un hash no coincide.

Exit code: 0 = la oferta está completa, 1 = no lo está.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

# La consola de Windows usa cp1252: un carácter fuera de esa tabla convierte un
# informe en un traceback DESPUÉS de haber hecho el trabajo. Ver salida_consola.
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:  # noqa: E402
    from salida_consola import consola_utf8
except ImportError:  # pragma: no cover - un clon puede no traer el ayudante
    # Se degrada en vez de morir: esto es presentación, no resultado. Un script
    # de aprovisionamiento que no arranca porque falta una comodidad de consola
    # deja al que clona sin la única herramienta que tenía para desbloquearse.
    def consola_utf8() -> None:
        import sys as _sys
        for _flujo in (_sys.stdout, _sys.stderr):
            _reconfigurar = getattr(_flujo, "reconfigure", None)
            if _reconfigurar is not None:
                try:
                    _reconfigurar(encoding="utf-8", errors="replace")
                except (ValueError, OSError):
                    pass

consola_utf8()


RAIZ = Path(__file__).resolve().parents[1]
DIRECTORIO = RAIZ / "dist" / "source-offer"

#: La DECLARACION vive en el repositorio; los TARBALLS, no.
#:
#: Medido el 2026-09-06: `dist/` esta en `.gitignore`, asi que la oferta
#: entera existia solo en la maquina del mantenedor. Un clon limpio corria
#: este gate y obtenia codigo 1 —correctamente, pero sin saber siquiera que
#: se ofrece ni de que commit—. Ahora la declaracion (URLs, commits y
#: SHA-256) esta versionada y cualquiera puede leerla; los dos .tar.gz
#: siguen fuera porque son artefactos de publicacion de 35 MB, no fuente
#: del proyecto.
OFERTA_VERSIONADA = RAIZ / "tools" / "openbabel" / "SOURCE-OFFER.json"
OFERTA_EN_DIST = DIRECTORIO / "openbabel-source-offer.json"
OFERTA = OFERTA_VERSIONADA if OFERTA_VERSIONADA.is_file() else OFERTA_EN_DIST
MANIFIESTO_HERRAMIENTA = RAIZ / "tools" / "openbabel" / "openbabel-manifest.json"

#: Los dos archivos que hacen falta para reconstruir el binario distribuido.
#: El primero son las fuentes de Open Babel; el segundo, las recetas que las
#: compilaron. Con uno solo no se puede reproducir nada.
ARTEFACTOS = (
    "openbabel-src-77993b9a.tar.gz",
    "openbabel-wheel-recipe-c6b2731d.tar.gz",
)


def sha256(ruta: Path) -> str:
    digest = hashlib.sha256()
    with ruta.open("rb") as handle:
        for bloque in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(bloque)
    return digest.hexdigest()


def _datos_de_la_herramienta() -> dict:
    if not MANIFIESTO_HERRAMIENTA.is_file():
        raise SystemExit(
            f"No existe {MANIFIESTO_HERRAMIENTA.relative_to(RAIZ).as_posix()}. "
            "Ejecuta `python scripts/stage_openbabel_tool.py` antes: la oferta "
            "describe el binario que de verdad se distribuye."
        )
    return json.loads(MANIFIESTO_HERRAMIENTA.read_text(encoding="utf-8"))


def plantilla() -> int:
    manifiesto = _datos_de_la_herramienta()
    procedencia = manifiesto["procedencia"]
    ejecutable = manifiesto["ejecutable"]
    DIRECTORIO.mkdir(parents=True, exist_ok=True)
    documento = {
        "schema_version": 1,
        "obligacion": (
            "GPL-2.0-only §3: acompañar el binario distribuido del código fuente "
            "correspondiente de la versión exacta, o de una oferta escrita válida."
        ),
        "programa": manifiesto["programa"],
        "version": manifiesto["version_paquete"],
        "licencia_spdx": manifiesto["licencia_spdx"],
        "binario_distribuido": {
            "ruta": f"tools/openbabel/{ejecutable}",
            "sha256": manifiesto["archivos"][ejecutable]["sha256"],
        },
        "wheel_de_origen": {
            "nombre": procedencia["wheel"],
            "sha256": procedencia["wheel_sha256"],
        },
        "procedencia": procedencia,
        "artefactos": {
            nombre: {
                "sha256": "",
                "descripcion": (
                    "fuentes de Open Babel en el commit "
                    f"{procedencia['fuentes_incorporadas_commit']}"
                    if "src" in nombre
                    else "recetas de compilación del wheel en el commit "
                    f"{procedencia['empaquetador_commit']}"
                ),
            }
            for nombre in ARTEFACTOS
        },
        "como_rellenar": (
            "Prepara los dos .tar.gz en este mismo directorio, calcula su SHA-256 "
            "y escríbelo en `artefactos`. Después `--check` debe pasar."
        ),
    }
    OFERTA.write_text(
        json.dumps(documento, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Plantilla escrita: {OFERTA.relative_to(RAIZ).as_posix()}")
    print("Rellena los SHA-256 de los artefactos cuando los prepares.")
    return 0


def comprobar(permitir_ausentes: bool = False) -> int:
    problemas: list[str] = []
    ausentes: list[str] = []
    if not OFERTA.is_file():
        print(
            "La oferta de código fuente correspondiente NO está preparada: falta "
            f"{OFERTA.relative_to(RAIZ).as_posix()}.\n"
            "Open Babel se distribuye bajo GPL-2.0-only y la GPLv2 §3 exige "
            "acompañar el binario de la fuente de la versión exacta. Un enlace a "
            "una web no cumple por sí solo.\n"
            "Ejecuta `python scripts/verify_release_source_offer.py --plantilla` "
            "y prepara los artefactos.",
            file=sys.stderr,
        )
        return 1

    # `utf-8-sig`: en Windows es facil que un editor deje BOM en este JSON,
    # y un gate de cumplimiento no puede caerse por un byte invisible.
    documento = json.loads(OFERTA.read_text(encoding="utf-8-sig"))
    manifiesto = _datos_de_la_herramienta()
    ejecutable = manifiesto["ejecutable"]

    # El binario que se ofrece reconstruir tiene que ser el que se distribuye.
    esperado = manifiesto["archivos"][ejecutable]["sha256"]
    declarado = documento.get("binario_distribuido", {}).get("sha256")
    if declarado != esperado:
        problemas.append(
            "la oferta describe otro binario: declara "
            f"{str(declarado)[:12]}… y se distribuye {esperado[:12]}…"
        )
    if documento.get("licencia_spdx") != "GPL-2.0-only":
        problemas.append(
            f"la oferta declara la licencia {documento.get('licencia_spdx')!r} "
            "en vez de GPL-2.0-only"
        )
    if documento.get("wheel_de_origen", {}).get("sha256") != (
        manifiesto["procedencia"]["wheel_sha256"]
    ):
        problemas.append("el SHA-256 del wheel de origen no coincide con el manifiesto")

    for nombre in ARTEFACTOS:
        entrada = documento.get("artefactos", {}).get(nombre)
        if entrada is None:
            problemas.append(f"la oferta no declara el artefacto {nombre}")
            continue
        ruta = DIRECTORIO / nombre
        if not ruta.is_file():
            if permitir_ausentes:
                ausentes.append(nombre)
                continue
            problemas.append(
                f"falta el archivo de fuente {nombre}: sin él la publicación "
                "no ofrece acceso equivalente al código correspondiente"
            )
            continue
        if not entrada.get("sha256"):
            problemas.append(f"el SHA-256 de {nombre} está sin rellenar")
        elif sha256(ruta) != entrada["sha256"]:
            problemas.append(f"el SHA-256 de {nombre} no coincide con el declarado")

    if ausentes and not problemas:
        faltantes = ", ".join(ausentes)
        print(
            "Oferta de fuente DECLARADA y coherente con el binario "
            f"distribuido, pero {len(ausentes)} artefacto(s) NO están en "
            f"este árbol: {faltantes}.\n"
            "  No se ha verificado su contenido. Saltar no es aprobar: "
            "antes de publicar, prepáralos y corre este gate SIN "
            "--permitir-artefactos-ausentes."
        )
        return 0

    if problemas:
        print(
            "La oferta de código fuente correspondiente NO está completa:",
            file=sys.stderr,
        )
        for problema in problemas:
            print(f"  - {problema}", file=sys.stderr)
        return 1

    print(
        f"Oferta de fuente verificada: {len(ARTEFACTOS)} artefactos presentes con "
        f"su SHA-256, para {documento['programa']} {documento['version']} "
        f"({documento['licencia_spdx']})."
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    grupo = parser.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--plantilla", action="store_true")
    grupo.add_argument("--check", action="store_true")
    parser.add_argument(
        "--permitir-artefactos-ausentes", action="store_true",
        help=("comprueba la DECLARACIÓN aunque los .tar.gz no estén; "
              "lo dice en vez de imprimir «verificado»"),
    )
    args = parser.parse_args()
    if args.plantilla:
        return plantilla()
    return comprobar(args.permitir_artefactos_ausentes)


if __name__ == "__main__":
    raise SystemExit(main())
