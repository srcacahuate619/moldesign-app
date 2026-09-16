r"""Arma el MSIX de Microsoft Store a partir del build de Tauri y del runtime staged.

Ruta SEPARADA de NSIS. No toca `tauri.conf.json` ni `tauri.conf.prod.json`: el
instalador NSIS se sigue construyendo como siempre. Este script consume lo que
Tauri ya produjo y lo empaqueta.

Por que el MSIX no lo hace Tauri
--------------------------------
`tauri build --bundles` admite exactamente `msi` y `nsis` en la CLI 2.11. No hay
target MSIX. La guia oficial para Store con Tauri es la misma que aqui: compilar
la app con Tauri y empaquetar despues con el CLI `winapp` de Microsoft. Por eso
hay dos pasos y no uno.

Orden de las fases (cada una es idempotente y se puede saltar):

  1. stage     runtime staged completo en frontend/src-tauri/resources
  2. tauri     compila la app sin bundlear instalador (--no-bundle)
  3. assets    genera los iconos MSIX en msix/assets
  4. manifest  escribe msix/Package.appxmanifest desde msix-config.json
  5. layout    arma el arbol del paquete en <raiz de produccion>/v<version>/layout
  6. package   winapp package (o makeappx como respaldo) -> .msix
  7. sign      firma con certificado de DESARROLLO, solo para probar en local

Donde aterrizan los artefactos
------------------------------
En la RAIZ DE PRODUCCION, que por defecto es `E:\rel` y esta deliberadamente
fuera del arbol de desarrollo y en otro disco fisico. Cada envio estrena
`v<version del Store>`: el paquete, su evidencia de build, la de aceptacion y el
informe del WACK viajan juntos y nadie reescribe una carpeta ya sellada.
Se cambia con `--dist` o `MOLDESIGN_DIST_RAIZ`. La raiz debe ser CORTA: el
fichero mas hondo del runtime deja ~20 caracteres de margen frente al MAX_PATH
de Windows, y el script lo comprueba antes de copiar.

La version del Store se DERIVA de `version` de tauri.conf.json y se valida:
cuatro campos, cuarto campo 0, cada campo <= 65535. Ver `msix-config.json`
seccion `version_del_store` para el mapeo y su limitacion.

Uso:
    python scripts/build_msix.py --todo
    python scripts/build_msix.py --fases manifest,layout,package,sign
    python scripts/build_msix.py --todo --omitir-tauri   # reutiliza el exe
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
MSIX_DIR = ROOT / "msix"
CONFIG = MSIX_DIR / "msix-config.json"
TAURI_CONF = ROOT / "frontend" / "src-tauri" / "tauri.conf.json"
TAURI_CONF_MSIX = ROOT / "frontend" / "src-tauri" / "tauri.conf.msix.json"
RESOURCES = ROOT / "frontend" / "src-tauri" / "resources"
TARGET_RELEASE = ROOT / "frontend" / "src-tauri" / "target" / "release"
# ── Raiz de PRODUCCION ──────────────────────────────────────────────────────
# Los artefactos de release no viven en el arbol de desarrollo, ni siquiera en el
# mismo disco: E: es otra unidad fisica, distinta de la de desarrollo. Asi un
# fallo del disco de trabajo no se lleva el paquete sellado ni su evidencia, y
# ningun script de desarrollo puede pisarlos por accidente -- que es exactamente
# como se corrompio dist/base-v1.0.0.zip durante una auditoria.
#
# DIST se fija en main() porque depende de la version del Store: cada envio
# estrena carpeta y NUNCA se reutiliza una. Reutilizar el directorio de salida es
# lo que dejo evidencia de aceptacion apuntando a bytes que ya no existian.
DIST_RAIZ = Path(os.environ.get("MOLDESIGN_DIST_RAIZ", r"E:\rel"))
DIST = DIST_RAIZ / "sin-version"
LAYOUT = DIST / "layout"

# MAX_PATH de Windows. El fichero mas hondo del runtime real ronda los 238
# caracteres (torch -> third_party -> ... -> duktape/LICENSE.txt) con la raiz
# antigua, asi que el margen es de ~20: una raiz de produccion larga rompe el
# empaquetado. Se comprueba ANTES de copiar, no despues de fallar a medias.
MAX_PATH = 260

FASES = ("stage", "tauri", "assets", "manifest", "layout", "package", "sign")

# Artefactos derivados de PDBbind que NO se redistribuyen en el paquete.
# Son tablas de afinidades/features derivadas del dataset, no pesos ni código
# (que sí se distribuyen como obra del autor). Ver docs/86 y
# frontend/public/legal/RELEASE_BLOCKERS.md. Se excluyen del layout en
# fase_layout y un gate aborta si reaparecen.
ARTEFACTOS_PDBBIND_EXCLUIDOS = [
    "resources/backend/data/benchmark_pdbbind.json",
    "resources/backend/data/benchmark_pdbbind_200.json",
    "resources/backend/data/benchmark_pdbbind_200_rerank.json",
    "resources/backend/data/pocket_dataset_150_holdout.json",
    "resources/backend/data/pocket_dataset_200.json",
    "resources/rescoring/artifacts/pdbbind_audit_report.json",
]


class BuildAbortado(RuntimeError):
    """El build no puede continuar de forma valida."""


# ── Utilidades ──────────────────────────────────────────────────────────────

def _cargar(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _mostrar(path: Path) -> str:
    """Ruta legible: relativa al repo si cuelga de el, absoluta si no.

    Desde que produccion vive en otro disco, `relative_to(ROOT)` lanza
    ValueError para todo lo que hay bajo DIST. No es cosmetica: se usaba en
    cuatro sitios y cualquiera de ellos tumbaba el build entero.
    """
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _correr(argv: list[str], cwd: Path | None = None, env: dict[str, str] | None = None) -> str:
    print(f"    $ {' '.join(str(a) for a in argv)}")
    partes = [str(a) for a in argv]
    # En Windows `npm` y `npx` son .cmd: CreateProcess no los encuentra por
    # nombre pelado y subprocess falla con WinError 2. Se resuelven a su ruta
    # real en vez de usar shell=True, que haria pasar los argumentos por el
    # interprete de comandos.
    resuelto = shutil.which(partes[0], path=(env or os.environ).get("PATH"))
    if resuelto:
        partes[0] = resuelto
    res = subprocess.run(
        partes, cwd=str(cwd) if cwd else None,
        env=env, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if res.returncode != 0:
        raise BuildAbortado(
            f"Fallo ({res.returncode}): {' '.join(str(a) for a in argv)}\n"
            f"--- stdout ---\n{(res.stdout or '')[-3000:]}\n"
            f"--- stderr ---\n{(res.stderr or '')[-3000:]}"
        )
    return res.stdout or ""


def _buscar_winapp() -> Path | None:
    hallado = shutil.which("winapp")
    if hallado:
        return Path(hallado)
    # winget lo instala en WindowsApps del usuario, que puede no estar en el PATH
    # del proceso actual aunque si en el del usuario.
    candidato = (Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WindowsApps" / "winapp.exe")
    return candidato if candidato.is_file() else None


def _buscar_sdk(nombre: str) -> Path | None:
    """makeappx / signtool mas reciente del Windows SDK."""
    base = Path(r"C:/Program Files (x86)/Windows Kits/10/bin")
    if not base.is_dir():
        return None
    encontrados = sorted(
        (p for p in base.glob(f"*/x64/{nombre}") if p.is_file()),
        key=lambda p: p.parent.parent.name,
    )
    return encontrados[-1] if encontrados else None


# ── Version del Store ───────────────────────────────────────────────────────

RE_SEMVER = re.compile(
    r"^(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)"
    r"(?:-(?P<canal>alpha|beta|rc)\.(?P<n>\d+))?$"
)


def version_del_store(semver: str, override: int | None) -> tuple[str, dict[str, Any]]:
    """Traduce semver a `Major.Minor.Build.0` y valida los limites del Store."""
    m = RE_SEMVER.match(semver.strip())
    if not m:
        raise BuildAbortado(
            f"`version` de tauri.conf.json no es semver reconocible: {semver!r}. "
            "El mapeo a version de Store no puede inventarse."
        )
    major = int(m.group("major"))
    minor = int(m.group("minor"))
    patch = int(m.group("patch"))
    canal = m.group("canal")
    n = int(m.group("n")) if m.group("n") else None

    if override is not None:
        build = int(override)
        derivacion = f"override explicito ({build})"
    elif canal == "alpha":
        build, derivacion = n, f"alpha.{n} -> Build = {n}"
    elif canal == "beta":
        build, derivacion = 10000 + n, f"beta.{n} -> Build = 10000 + {n}"
    elif canal == "rc":
        build, derivacion = 20000 + n, f"rc.{n} -> Build = 20000 + {n}"
    else:
        build, derivacion = 30000 + patch, f"sin prerelease -> Build = 30000 + {patch}"

    for nombre, campo in (("Major", major), ("Minor", minor), ("Build", build)):
        if not 0 <= campo <= 65535:
            raise BuildAbortado(
                f"El campo {nombre} de la version del Store vale {campo} y debe estar "
                "entre 0 y 65535."
            )
    version = f"{major}.{minor}.{build}.0"
    # El cuarto campo lo reserva el Store: un paquete con Revision != 0 se rechaza.
    assert version.endswith(".0"), version
    return version, {
        "semver_origen": semver,
        "version_store": version,
        "derivacion": derivacion,
        "revision_es_cero": True,
    }


# ── Fase: manifiesto ────────────────────────────────────────────────────────

PLANTILLA_MANIFIESTO = """<?xml version="1.0" encoding="utf-8"?>
<!-- GENERADO por scripts/build_msix.py desde msix/msix-config.json.
     No editar a mano: el generador lo sobreescribe y la identidad dejaria de
     estar verificada contra la configuracion. -->
<Package
  xmlns="http://schemas.microsoft.com/appx/manifest/foundation/windows10"
  xmlns:uap="http://schemas.microsoft.com/appx/manifest/uap/windows10"
  xmlns:rescap="http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities"
  xmlns:win32dependencies="http://schemas.microsoft.com/appx/manifest/externaldependencies"
  IgnorableNamespaces="uap rescap win32dependencies">

  <Identity
    Name="{identity_name}"
    Publisher="{identity_publisher}"
    Version="{version}"
    ProcessorArchitecture="{arch}" />

  <Properties>
    <DisplayName>{display_name}</DisplayName>
    <PublisherDisplayName>{publisher_display_name}</PublisherDisplayName>
    <Logo>assets\\StoreLogo.png</Logo>
  </Properties>

  <Dependencies>
    <TargetDeviceFamily Name="Windows.Desktop" MinVersion="{min_version}" MaxVersionTested="{max_tested}" />
    <!-- Esquema documentado por Microsoft para declarar el runtime de WebView2
         como dependencia externa en MSIX: win32dependencies:ExternalDependency.
         Name y Publisher son los valores fijos que Microsoft permite para este
         elemento. MinVersion "1.1.1.1" es el valor del ejemplo del documento
         oficial del esquema y significa que CUALQUIER runtime Evergreen ya
         instalado lo satisface: la instalacion en cadena solo se dispara en una
         maquina donde el runtime falta. Optional="false" falla cerrado: una
         instalacion sin red en una maquina sin runtime falla de forma honesta
         en vez de producir una aplicacion que no puede arrancar. -->
    <win32dependencies:ExternalDependency
      Name="Microsoft.WebView2"
      Publisher="CN=Microsoft Windows, O=Microsoft Corporation, L=Redmond, S=Washington, C=US"
      MinVersion="1.1.1.1"
      Optional="false" />
  </Dependencies>

  <Resources>
    <Resource Language="es-ES" />
    <Resource Language="en-US" />
  </Resources>

  <Applications>
    <Application Id="MolDesign"
                 Executable="{executable}"
                 EntryPoint="Windows.FullTrustApplication">
      <uap:VisualElements
        DisplayName="{display_name}"
        Description="{description}"
        BackgroundColor="transparent"
        Square150x150Logo="assets\\Square150x150Logo.png"
        Square44x44Logo="assets\\Square44x44Logo.png">
        <uap:DefaultTile
          Wide310x150Logo="assets\\Wide310x150Logo.png"
          Square310x310Logo="assets\\Square310x310Logo.png"
          Square71x71Logo="assets\\Square71x71Logo.png" />
        <uap:SplashScreen Image="assets\\SplashScreen.png" />
      </uap:VisualElements>
    </Application>
  </Applications>

  <Capabilities>
    <!-- runFullTrust es la confianza que este producto necesita, y no es
         opcional: el backend es un interprete Python embebido que se lanza como
         subproceso, y AutoDock Vina y Open Babel se invocan como programas
         externos. Sin plena confianza no hay pipeline.
         Es una capacidad RESTRINGIDA: Partner Center exige justificacion
         escrita y la revisa una persona. -->
    <rescap:Capability Name="runFullTrust" />
  </Capabilities>
</Package>
"""


def fase_manifiesto(cfg: dict, version: str) -> Path:
    ident = cfg["identidad_del_store"]
    conf = _cargar(TAURI_CONF)
    destino = MSIX_DIR / "Package.appxmanifest"
    xml = PLANTILLA_MANIFIESTO.format(
        identity_name=ident["package_identity_name"],
        identity_publisher=ident["package_identity_publisher"],
        publisher_display_name=ident["package_properties_publisher_display_name"],
        arch=ident["processor_architecture"],
        version=version,
        display_name=conf.get("productName", "MolDesign"),
        description="Diseno molecular asistido con acoplamiento AutoDock Vina y "
                    "reescalado reproducible.",
        executable="moldesign.exe",
        min_version="10.0.17763.0",
        max_tested="10.0.26100.0",
    )
    destino.write_text(xml, encoding="utf-8")
    print(f"    -> {destino.relative_to(ROOT)}")
    return destino


# ── Fase: assets ────────────────────────────────────────────────────────────

def _recomprimir_assets_excedentes(cfg: dict) -> None:
    """Baja por debajo del límite de 204 800 bytes que exige el WACK.

    `winapp manifest update-assets` genera a veces PNG sobredimensionados (el
    WACK marcó `Square310x310Logo.scale-200.png`). Se cuantizan a paleta de 256
    colores preservando el canal alfa (FASTOCTREE), manteniendo dimensiones. Para
    logos de marca es visualmente neutro y baja el PNG muy por debajo del límite.
    No se tocan los iconos de NSIS (`frontend/src-tauri/icons`), sólo
    `msix/assets`.
    """
    from PIL import Image  # type: ignore

    assets = MSIX_DIR / "assets"
    max_bytes = 200 * 1024
    for png in sorted(assets.glob("*.png")):
        try:
            antes = png.stat().st_size
        except OSError:
            continue
        if antes <= max_bytes:
            continue
        with Image.open(png) as im:
            im.load()
            rgba = im.convert("RGBA")
        cuantizada = rgba.quantize(
            colors=256,
            method=Image.Quantize.FASTOCTREE,
            dither=Image.Dither.FLOYDSTEINBERG,
        )
        cuantizada.save(png, "PNG", optimize=True)
        despues = png.stat().st_size
        print(f"    recomprimido {png.name}: {antes} -> {despues} bytes")
        if despues > max_bytes:
            print(
                f"    ADVERTENCIA: {png.name} ({despues} bytes) sigue por encima "
                f"de {max_bytes}; revisar la imagen fuente."
            )


def fase_assets(cfg: dict, winapp: Path | None) -> None:
    """Genera los iconos MSIX en msix/assets.

    No sobreescribe `frontend/src-tauri/icons`: esos iconos sirven a la ruta
    NSIS y tocarlos cambiaria el instalador existente.
    """
    assets = MSIX_DIR / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    fuente = ROOT / cfg["assets"]["imagen_fuente"].replace("/", os.sep)
    if not fuente.is_file():
        raise BuildAbortado(f"No existe la imagen fuente de assets: {fuente}")

    manifiesto = MSIX_DIR / "Package.appxmanifest"
    usado_winapp = False
    if winapp and manifiesto.is_file():
        try:
            _correr([winapp, "manifest", "update-assets", str(fuente)], cwd=MSIX_DIR)
            print("    assets generados por winapp manifest update-assets")
            usado_winapp = True
        except BuildAbortado as e:
            print(f"    winapp update-assets no sirvio ({str(e)[:120]}...); se usa respaldo")

    if not usado_winapp:
        # Respaldo: reescalar con Pillow. Los nombres y tamanos son los que exige
        # el manifiesto; si falta uno, el paquete no valida.
        from PIL import Image  # type: ignore

        requeridos = {
            "StoreLogo.png": (50, 50),
            "Square44x44Logo.png": (44, 44),
            "Square71x71Logo.png": (71, 71),
            "Square150x150Logo.png": (150, 150),
            "Square310x310Logo.png": (310, 310),
            "Wide310x150Logo.png": (310, 150),
            "SplashScreen.png": (620, 300),
        }
        with Image.open(fuente) as img:
            base = img.convert("RGBA")
            for nombre, (w, h) in requeridos.items():
                lienzo = Image.new("RGBA", (w, h), (0, 0, 0, 0))
                lado = min(w, h)
                escalado = base.resize((lado, lado), Image.LANCZOS)
                lienzo.paste(escalado, ((w - lado) // 2, (h - lado) // 2), escalado)
                lienzo.save(assets / nombre, "PNG")
        print(f"    {len(requeridos)} assets reescalados con Pillow -> {assets.relative_to(ROOT)}")

    _recomprimir_assets_excedentes(cfg)


# ── Fase: layout ────────────────────────────────────────────────────────────

def resolver_dist(raiz: Path, version: str) -> tuple[Path, Path]:
    """Carpeta de produccion de ESTA version, y su layout.

    No hay repliegue silencioso al arbol de desarrollo: si la unidad de
    produccion no esta, el build para. Replegarse dejaria el paquete en el disco
    de trabajo con la evidencia diciendo otra cosa, que es peor que no construir.
    """
    unidad = Path(raiz.anchor) if raiz.anchor else None
    if unidad is not None and not unidad.exists():
        raise BuildAbortado(
            f"La unidad de produccion {unidad} no esta disponible. Conectala, o "
            f"indica otra raiz con --dist / MOLDESIGN_DIST_RAIZ."
        )
    dist = raiz / f"v{version}"
    return dist, dist / "layout"


def _verificar_max_path(layout: Path) -> int:
    """Aborta si la raiz elegida no deja sitio para el fichero mas hondo.

    Se mide sobre el runtime staged real, no sobre una estimacion: `resources`
    trae rutas de ~200 caracteres (torch y sus third_party anidados) y el margen
    frente al MAX_PATH de Windows es de decenas de caracteres, no de cientos.
    """
    if not RESOURCES.is_dir():
        return 0
    destino = layout / "resources"
    mas_largo, ejemplo = 0, ""
    for p in RESOURCES.rglob("*"):
        rel = str(p.relative_to(RESOURCES))
        if len(rel) > mas_largo:
            mas_largo, ejemplo = len(rel), rel
    proyectado = len(str(destino)) + 1 + mas_largo
    print(f"    path mas largo proyectado: {proyectado} de {MAX_PATH} "
          f"(margen {MAX_PATH - proyectado})")
    if proyectado >= MAX_PATH:
        raise BuildAbortado(
            f"La raiz de produccion es demasiado larga: el fichero mas hondo del "
            f"runtime quedaria en {proyectado} caracteres y Windows corta en "
            f"{MAX_PATH}.\n"
            f"  ejemplo: ...\\{ejemplo}\n"
            f"  Usa una raiz mas corta con --dist."
        )
    return proyectado


def fase_layout(cfg: dict) -> dict[str, Any]:
    """Arbol del paquete: exe + WebView2 + runtime staged + assets + manifiesto."""
    exe = TARGET_RELEASE / "moldesign.exe"
    if not exe.is_file():
        raise BuildAbortado(
            f"No existe {exe}. Ejecuta la fase `tauri` (o quita --omitir-tauri)."
        )
    if not (RESOURCES / "backend" / "api" / "main.py").is_file():
        raise BuildAbortado(
            f"No hay runtime staged en {RESOURCES}. Ejecuta la fase `stage`."
        )

    path_proyectado = _verificar_max_path(LAYOUT)

    if LAYOUT.exists():
        shutil.rmtree(LAYOUT)
    LAYOUT.mkdir(parents=True)

    shutil.copy2(exe, LAYOUT / "moldesign.exe")

    # DLL sueltas que Tauri deja junto al exe (WebView2Loader y similares).
    for dll in TARGET_RELEASE.glob("*.dll"):
        shutil.copy2(dll, LAYOUT / dll.name)

    # El runtime staged va INTEGRO. Recortarlo produciria un producto distinto
    # del que se valido.
    shutil.copytree(RESOURCES, LAYOUT / "resources", symlinks=False)

    # Los artefactos derivados de PDBbind no se redistribuyen. Se excluyen del
    # layout explícitamente y se verifica: un gate no puede quedarse mudo.
    for rel in ARTEFACTOS_PDBBIND_EXCLUIDOS:
        destino = LAYOUT / rel
        if destino.exists() or destino.is_symlink():
            destino.unlink()
    supervivientes = [rel for rel in ARTEFACTOS_PDBBIND_EXCLUIDOS if (LAYOUT / rel).exists()]
    if supervivientes:
        raise BuildAbortado(
            "Artefactos PDBbind-derivados siguen en el layout tras la exclusión: "
            f"{supervivientes}")

    shutil.copytree(MSIX_DIR / "assets", LAYOUT / "assets")
    shutil.copy2(MSIX_DIR / "Package.appxmanifest", LAYOUT / "AppxManifest.xml")

    n = sum(1 for p in LAYOUT.rglob("*") if p.is_file())
    total = sum(p.stat().st_size for p in LAYOUT.rglob("*") if p.is_file())
    print(f"    layout: {n} ficheros, {total / 1024 / 1024:.1f} MiB")
    return {"ficheros": n, "bytes": total, "ruta": str(LAYOUT),
            "path_mas_largo_proyectado": path_proyectado, "max_path": MAX_PATH}


# ── Fase: package ───────────────────────────────────────────────────────────

def fase_package(cfg: dict, version: str, winapp: Path | None) -> Path:
    ident = cfg["identidad_del_store"]
    nombre = f"{ident['package_identity_name']}_{version}_{ident['processor_architecture']}.msix"
    salida = DIST / nombre
    if salida.exists():
        salida.unlink()

    if winapp:
        _correr([winapp, "package", str(LAYOUT), "--manifest",
                 str(MSIX_DIR / "Package.appxmanifest"), "--output", str(salida)])
    else:
        makeappx = _buscar_sdk("makeappx.exe")
        if not makeappx:
            raise BuildAbortado("Ni winapp ni makeappx.exe disponibles.")
        _correr([makeappx, "pack", "/o", "/d", str(LAYOUT), "/p", str(salida)])

    if not salida.is_file():
        raise BuildAbortado(f"El empaquetado no produjo {salida}")
    print(f"    -> {_mostrar(salida)} ({salida.stat().st_size / 1024 / 1024:.1f} MiB)")
    return salida


# ── Fase: firma (solo pruebas locales) ──────────────────────────────────────

def fase_sign(cfg: dict, paquete: Path, winapp: Path | None) -> dict[str, Any]:
    """Firma con un certificado de DESARROLLO para poder instalar en local.

    El paquete que se envia a Partner Center NO se firma aqui: lo firma el
    Store. Este certificado no se distribuye ni se commitea.
    """
    publisher = cfg["identidad_del_store"]["package_identity_publisher"]
    # El certificado vive en la RAIZ de produccion, no en la carpeta de la
    # version: es el mismo para todas y regenerarlo por version obligaria a
    # confiar un certificado nuevo en cada prueba de instalacion.
    cert = DIST_RAIZ / "devcert.pfx"
    if not winapp:
        return {"firmado": False, "motivo": "winapp no disponible; se omite la firma"}
    if not cert.is_file():
        # El sujeto del certificado debe coincidir EXACTAMENTE con Publisher del
        # manifiesto o Windows rechaza la instalacion.
        cert.parent.mkdir(parents=True, exist_ok=True)
        _correr([winapp, "cert", "generate", "--publisher", publisher,
                 "--output", str(cert)], cwd=cert.parent)
    if not cert.is_file():
        return {"firmado": False, "motivo": f"no se genero {cert}"}
    # winapp 0.6.x recibe el certificado como segundo argumento posicional:
    # `winapp sign <paquete> <certificado>`. La sintaxis antigua `--cert`
    # genera el MSIX pero aborta justo antes de firmarlo.
    _correr([winapp, "sign", str(paquete), str(cert)])
    return {"firmado": True, "certificado": _mostrar(cert),
            "sujeto_esperado": publisher,
            "nota": "Certificado de desarrollo, solo para instalar y probar en esta maquina."}


# ── Programa ────────────────────────────────────────────────────────────────

def main() -> int:
    # Las tres son globales porque las fases las leen como constantes de modulo;
    # su valor real depende de --dist y de la version, que solo se conocen aqui.
    global DIST_RAIZ, DIST, LAYOUT

    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--todo", action="store_true", help="Ejecuta todas las fases.")
    ap.add_argument("--fases", help=f"Lista separada por comas de: {','.join(FASES)}")
    ap.add_argument("--omitir-tauri", action="store_true",
                    help="Reutiliza target/release/moldesign.exe tal como este.")
    ap.add_argument("--store-build", type=int, default=None,
                    help="Fija el tercer campo de la version del Store para ESTA "
                         "corrida, sin tocar msix-config.json. Existe para poder "
                         "generar el paquete de version superior con el que se "
                         "prueba la ACTUALIZACION: sin el habria que editar la "
                         "configuracion sellada y el arbol quedaria sucio. OJO: la "
                         "fase `manifest` deja msix/Package.appxmanifest con esta "
                         "version; restauralo (`git checkout --`) antes de construir "
                         "el paquete que se envia.")
    ap.add_argument("--dist", type=Path, default=DIST_RAIZ,
                    help=f"Raiz de produccion. Por defecto {DIST_RAIZ} "
                         f"(disco separado del de desarrollo). Dentro se crea "
                         f"una carpeta v<version> por envio.")
    args = ap.parse_args()

    if args.todo:
        fases = [f for f in FASES if not (args.omitir_tauri and f == "tauri")]
    elif args.fases:
        fases = [f.strip() for f in args.fases.split(",") if f.strip()]
        desconocidas = [f for f in fases if f not in FASES]
        if desconocidas:
            raise SystemExit(f"Fases desconocidas: {desconocidas}. Validas: {list(FASES)}")
    else:
        raise SystemExit("Indica --todo o --fases <lista>.")

    cfg = _cargar(CONFIG)
    conf = _cargar(TAURI_CONF)
    version, detalle_version = version_del_store(
        conf["version"],
        args.store_build if args.store_build is not None
        else cfg["version_del_store"].get("store_build_override"))

    DIST_RAIZ = args.dist.resolve() if args.dist.is_absolute() else (ROOT / args.dist)
    DIST, LAYOUT = resolver_dist(DIST_RAIZ, version)
    DIST.mkdir(parents=True, exist_ok=True)

    winapp = _buscar_winapp()
    print(f"winapp: {winapp or 'NO DISPONIBLE (se usara makeappx)'}")
    print(f"version del Store: {version}  [{detalle_version['derivacion']}]")
    print(f"produccion: {DIST}")

    # El arbol sucio no aborta el build -- hay motivos legitimos para empaquetar
    # con cambios locales -- pero queda ESCRITO en la evidencia. Un
    # `build-evidence.json` que declara un commit y se construyo sobre otra cosa
    # afirma una procedencia que no existe.
    sucio = _correr(["git", "status", "--porcelain"], cwd=ROOT).strip()
    if sucio:
        print(f"AVISO: arbol sucio, {len(sucio.splitlines())} ficheros sin "
              f"commitear. Queda registrado en la evidencia.")

    evidencia: dict[str, Any] = {
        "generado_utc": datetime.now(timezone.utc).isoformat(),
        "commit": _correr(["git", "rev-parse", "HEAD"], cwd=ROOT).strip(),
        "arbol_limpio": not sucio,
        "ficheros_sin_commitear": len(sucio.splitlines()) if sucio else 0,
        "dist_raiz": str(DIST_RAIZ),
        "dist_version": str(DIST),
        "identidad": cfg["identidad_del_store"],
        "version": detalle_version,
        "nivel_de_confianza": cfg["nivel_de_confianza"],
        "winapp": str(winapp) if winapp else None,
        "fases_ejecutadas": [],
    }
    paquete: Path | None = None

    for fase in fases:
        print(f"[{fase}]")
        if fase == "stage":
            _correr([ROOT / "python-embed" / "python.exe",
                     ROOT / "scripts" / "bundle_helper.py", str(ROOT)], cwd=ROOT)
        elif fase == "tauri":
            # --no-bundle: el instalador NSIS NO se toca desde aqui. Solo se
            # quiere el exe compilado; el empaquetado MSIX lo hace winapp.
            #
            # No se llama a `build:desktop` ni a `stage:desktop` por separado:
            # el `beforeBuildCommand` de tauri.conf.json ya encadena las puertas
            # del producto (manifiesto de rescoring, M5, goldens, pesos de
            # stacking, frontera de Open Babel, gate de evaluacion, dossier) y
            # termina con el build del frontend. Duplicarlas aqui alargaria el
            # build sin comprobar nada nuevo, y saltarselas produciria un MSIX
            # que no paso las mismas puertas que el instalador NSIS.
            entorno = os.environ.copy()
            entorno["BUILD_TARGET"] = "desktop"
            # Deliberadamente NO hay forma de saltarse una puerta desde aqui.
            # Si `beforeBuildCommand` falla, el MSIX no se construye: un paquete
            # que no paso las mismas puertas que el NSIS no deberia existir, y un
            # bypass que se commitea deja de ser temporal.
            _correr(["npx", "tauri", "build", "--no-bundle", "--config",
                     "src-tauri/tauri.conf.msix.json"], cwd=ROOT / "frontend", env=entorno)
        elif fase == "assets":
            fase_assets(cfg, winapp)
        elif fase == "manifest":
            fase_manifiesto(cfg, version)
        elif fase == "layout":
            evidencia["layout"] = fase_layout(cfg)
        elif fase == "package":
            paquete = fase_package(cfg, version, winapp)
            evidencia["paquete"] = {
                "ruta": _mostrar(paquete),
                "bytes": paquete.stat().st_size,
                "sha256": _sha256(paquete),
            }
        elif fase == "sign":
            if paquete is None:
                candidatos = sorted(DIST.glob("*.msix"))
                if not candidatos:
                    raise BuildAbortado("No hay .msix que firmar.")
                paquete = candidatos[-1]
            evidencia["firma"] = fase_sign(cfg, paquete, winapp)
            evidencia["paquete"] = {
                "ruta": _mostrar(paquete),
                "bytes": paquete.stat().st_size,
                "sha256": _sha256(paquete),
            }
        evidencia["fases_ejecutadas"].append(fase)

    destino = DIST / "build-evidence.json"
    destino.write_text(json.dumps(evidencia, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nevidencia -> {_mostrar(destino)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BuildAbortado as e:
        print(f"ABORTADO: {e}", file=sys.stderr)
        raise SystemExit(2)
