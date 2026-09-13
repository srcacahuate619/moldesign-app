"""Valida que el runtime staged sea seguro y ejecutable antes de Tauri/NSIS."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "root",
        nargs="?",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Raíz del repositorio MolDesign.",
    )
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_manifest(resources: Path) -> list[str]:
    errors: list[str] = []
    manifest_path = resources / "runtime-manifest.json"
    if not manifest_path.is_file():
        return [f"Falta {manifest_path}"]
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"Manifiesto ilegible: {exc}"]
    if manifest.get("schema_version") != 1 or manifest.get("profile") != "desktop-mvp":
        errors.append("El manifiesto no declara schema_version=1 y profile=desktop-mvp.")
    if manifest.get("total_excludes_runtime_manifest") is not True:
        errors.append("El manifiesto no declara que su total describe sólo el payload.")
    for relative, expected in manifest.get("critical_assets", {}).items():
        path = resources / relative
        if not path.is_file():
            errors.append(f"Asset crítico ausente: {relative}")
            continue
        if path.stat().st_size != expected.get("bytes"):
            errors.append(f"Tamaño inesperado: {relative}")
        if sha256(path) != expected.get("sha256"):
            errors.append(f"Hash inesperado: {relative}")
    return errors


def find_forbidden_files(resources: Path) -> list[str]:
    forbidden: list[str] = []
    allowed_database = (resources / "data" / "molgraph_seed.db").resolve()
    for path in resources.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(resources).as_posix()
        lower_name = path.name.lower()
        parts = {part.lower() for part in path.parts}
        if path.resolve() == allowed_database:
            continue
        if lower_name.startswith(".env"):
            forbidden.append(relative)
        elif lower_name == "provider_config.json":
            forbidden.append(relative)
        elif lower_name.endswith((".log", ".err", ".out", ".sqlite", ".sqlite3", ".db")):
            forbidden.append(relative)
        elif lower_name.endswith((".key", ".pfx", ".p12")):
            forbidden.append(relative)
        elif "invalid_due_to_data_leakage" in lower_name:
            forbidden.append(relative)
        elif "backend" in parts and lower_name == "secret_key":
            forbidden.append(relative)
    return forbidden


def run_checked(command: list[str], *, cwd: Path, env: dict[str, str] | None = None, timeout: int = 120) -> None:
    result = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    if result.returncode != 0:
        output = "\n".join(item for item in (result.stdout.strip(), result.stderr.strip()) if item)
        raise RuntimeError(f"Falló {' '.join(command[:2])}:\n{output[-4000:]}")


def tree_state(root: Path) -> dict[str, tuple[int, int]]:
    return {
        path.relative_to(root).as_posix(): (path.stat().st_size, path.stat().st_mtime_ns)
        for path in root.rglob("*")
        if path.is_file()
    }


# DLLs presentes en cualquier Windows 10/11. Lista conservadora a proposito: lo
# que no este aqui se reporta y se revisa a mano. Preferimos un falso positivo
# que cuesta una revision, a un falso negativo que llega al investigador.
_DLLS_DE_WINDOWS = {
    "kernel32", "kernelbase", "ntdll", "user32", "gdi32", "gdi32full", "advapi32",
    "shell32", "shlwapi", "ole32", "oleaut32", "combase", "comctl32", "comdlg32",
    "ws2_32", "wsock32", "mswsock", "crypt32", "cryptbase", "bcrypt",
    "bcryptprimitives", "ncrypt", "secur32", "sspicli", "rpcrt4", "psapi",
    "version", "winmm", "wintrust", "iphlpapi", "dbghelp", "dbgcore", "imagehlp",
    "setupapi", "cfgmgr32", "powrprof", "userenv", "netapi32", "profapi",
    "msvcrt", "ucrtbase", "imm32", "uxtheme", "dwmapi", "propsys", "winhttp",
    "wininet", "urlmon", "dnsapi", "normaliz", "nsi", "opengl32", "glu32",
    "dxgi", "d3d11", "d3d12", "d3dcompiler_47", "windowscodecs", "mfplat",
    "avrt", "wtsapi32", "usp10", "oleacc", "msimg32", "pdh", "cabinet", "msi",
    "rstrtmgr", "authz", "sechost", "win32u", "gdiplus", "shcore", "credui",
    "httpapi", "wldap32", "mpr", "msasn1", "cryptsp", "cryptnet", "xmllite",
    "winspool", "winspool.drv", "dhcpcsvc", "dsound", "winusb", "hid",
}
_PREFIJOS_DE_WINDOWS = ("api-ms-win-", "ext-ms-win-")

# Dependencias que faltan A PROPOSITO, cada una con su motivo y su consecuencia.
# Entrar aqui exige haber comprobado que su ausencia DEGRADA y no rompe.
_AUSENCIAS_ACEPTADAS = {
    "opencl.dll": (
        "la provee el driver de la GPU. Sin ella el plugin OpenCL de OpenMM no "
        "carga y OpenMM usa CPU, que es la ruta soportada; y AutoDock-Vina-GPU "
        "no se usa (ver core/config.py: retirado por divergencia FP32/FP64)."
    ),
    "tbb12.dll": (
        "capa de hilos TBB de numba, opcional. Sin ella numba usa workqueue."
    ),
    "libboost_program_options-mt.dll": "solo AutoDock-Vina-GPU, que no se usa.",
    "libboost_thread-mt.dll": "solo AutoDock-Vina-GPU, que no se usa.",
    "libboost_filesystem-mt.dll": "solo AutoDock-Vina-GPU, que no se usa.",
    "libcrypto-3-x64.dll": (
        "carga diferida de llama.cpp para descargas HTTPS de modelos, que "
        "MolDesign no usa. Comprobado que `llama-common.dll` carga en una "
        "maquina sin esta DLL en System32 ni en el PATH."
    ),
    "libssl-3-x64.dll": "igual que libcrypto-3-x64.dll.",
}


def _es_de_windows(nombre: str) -> bool:
    base = nombre[:-4] if nombre.endswith(".dll") else nombre
    if base in _DLLS_DE_WINDOWS:
        return True
    return any(base.startswith(p) for p in _PREFIJOS_DE_WINDOWS)


def validate_native_dependencies(resources: Path) -> None:
    """Ninguna DLL que el bundle importe puede faltar en una maquina limpia.

    POR QUE ESTA COMPROBACION Y NO EL IMPORT DE PRUEBA. `validate_runtime`
    ejecuta un import real, y da verde... en la maquina de construccion, que
    tiene Visual Studio y por tanto `msvcp140.dll` y compania en System32. El
    primer instalador salio asi: gate en verde, y en una VM con Windows limpio
    el backend moria porque `_greenlet.pyd` no cargaba, con SQLAlchemy asincrono
    detras y uvicorn apagandose antes de contestar /health.

    Una comprobacion que depende del entorno donde corre no puede detectar una
    dependencia del entorno. Esta lee las tablas de importacion de los PE del
    bundle y clasifica cada dependencia en: esta dentro del paquete, es parte de
    Windows, es una ausencia aceptada y documentada, o es un RIESGO. Da el mismo
    resultado se ejecute donde se ejecute.
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from pe_imports import imports_de

    binarios = [
        f for f in resources.rglob("*")
        if f.is_file() and f.suffix.lower() in (".dll", ".pyd", ".exe")
    ]
    if not binarios:
        raise FileNotFoundError(f"no hay binarios que analizar en {resources}")

    # El ORDEN DE BUSQUEDA DE WINDOWS, y no "esta en algun sitio del paquete".
    #
    # La primera version de esta guardia daba por resuelta una DLL si existia
    # en cualquier carpeta del bundle. Al probarla apartando `msvcp140.dll` de
    # `python/` NO fallo: quedaba otra copia dentro de
    # `site-packages/openbabel_wheel.libs/`, un directorio PRIVADO de esa rueda
    # que ningun otro modulo tiene en su ruta de busqueda.
    #
    # Es literalmente el bug original: `msvcp140.dll` existia ahi dentro y
    # `_greenlet.pyd` seguia sin encontrarla. Una guardia que lo hubiera dado
    # por bueno habria firmado el mismo instalador roto.
    #
    # Lo que Windows mira de verdad, en orden: el directorio del propio binario,
    # el del proceso que carga -para todo lo que cuelga de `python/` eso es
    # `python/`, donde vive python.exe- y despues el sistema.
    raiz_python = resources / "python"
    site_packages = raiz_python / "Lib" / "site-packages"

    # `delvewheel` renombra las DLLs privadas de cada rueda con un hash de 32
    # hex y las deja en `<paquete>.libs/`, registrando ese directorio con
    # `os.add_dll_directory()` al importar el paquete. Un nombre ASI solo lo
    # pide un binario parcheado por delvewheel, que por construccion tiene su
    # directorio registrado: basta con que exista en alguna carpeta `.libs`.
    #
    # Un nombre SIN hash es otra cosa. `msvcp140.dll` tal cual, escondida en
    # `openbabel_wheel.libs/`, no la encuentra `_greenlet.pyd`: ese directorio
    # solo se registra al importar openbabel, y greenlet no lo importa. Ese es
    # exactamente el bug que dejo el instalador roto, asi que para los nombres
    # de sistema se exige el orden de busqueda real de Windows.
    _MANGLED = re.compile(r"-[0-9a-f]{32}\.dll$")
    _en_libs = {
        f.name.lower()
        for f in site_packages.glob("*.libs/*.dll")
    } if site_packages.is_dir() else set()

    def _paquete_de(binario: Path) -> Path | None:
        """El paquete de site-packages al que pertenece, si es que pertenece."""
        try:
            partes = binario.relative_to(site_packages).parts
        except ValueError:
            return None
        return site_packages / partes[0] if partes else None

    def resuelta(dll: str, binario: Path) -> bool:
        # 1. Junto al propio binario: lo primero que mira Windows.
        if (binario.parent / dll).exists():
            return True
        # 2. Nombre con hash de delvewheel: solo lo pide un binario parcheado,
        #    cuyo directorio `.libs` esta registrado por construccion.
        if _MANGLED.search(dll) and dll in _en_libs:
            return True
        # 3. Dentro del arbol de bibliotecas del propio paquete. Las ruedas
        #    cientificas registran su carpeta con `os.add_dll_directory()` al
        #    importarse: OpenMM pone sus plugins en `OpenMM.libs/lib/plugins/`
        #    y la biblioteca un nivel mas arriba; torch pide `torch_python.dll`
        #    desde `torch/lib/`. Son resolubles, y marcarlas seria un falso
        #    positivo que acabaria con la guardia desactivada.
        paquete = _paquete_de(binario)
        if paquete is not None:
            nombre = paquete.name
            for arbol in (paquete, site_packages / f"{nombre}.libs"):
                if arbol.is_dir() and any(arbol.rglob(dll)):
                    return True
        # 4. Junto al interprete: es el directorio del proceso para todo lo que
        #    cuelga de python/.
        try:
            binario.relative_to(raiz_python)
        except ValueError:
            return False  # fuera de python/ solo cuenta su propia carpeta
        return (raiz_python / dll).exists()

    riesgos: dict[str, set[str]] = {}
    aceptadas_vistas: set[str] = set()
    total_dependencias = 0

    for binario in binarios:
        for dll in set(imports_de(binario)):
            total_dependencias += 1
            if _es_de_windows(dll) or resuelta(dll, binario):
                continue
            if dll in _AUSENCIAS_ACEPTADAS:
                aceptadas_vistas.add(dll)
                continue
            riesgos.setdefault(dll, set()).add(
                binario.relative_to(resources).as_posix()
            )

    if riesgos:
        detalle = []
        for nombre, quien in sorted(riesgos.items(), key=lambda kv: -len(kv[1])):
            ejemplos = ", ".join(sorted(quien)[:3])
            detalle.append(f"  {nombre}  ({len(quien)} binario(s): {ejemplos} ...)")
        raise RuntimeError(
            "hay dependencias nativas que una maquina Windows limpia no tendra:\n"
            + "\n".join(detalle)
            + "\n\nEn ESTA maquina puede que la aplicacion funcione igual, porque "
            "el sistema las tenga por otras instalaciones. Empaqueta la DLL junto "
            "al binario que la pide, o -si su ausencia solo DEGRADA y no rompe- "
            "declarala en _AUSENCIAS_ACEPTADAS con el motivo comprobado."
        )

    print(
        f"      dependencias nativas: {len(binarios)} binarios, "
        f"{total_dependencias} importaciones, 0 sin resolver "
        f"({len(aceptadas_vistas)} ausencias declaradas)"
    )


def validate_runtime(resources: Path) -> None:
    python = resources / "python" / "python.exe"
    backend = resources / "backend"
    vina = resources / "tools" / "vina" / "vina.exe"
    if not python.is_file() or not backend.is_dir() or not vina.is_file():
        raise FileNotFoundError("Falta Python, backend o Vina en el runtime staged.")

    # ── EL ORDEN DE IMPORTACION ES PARTE DE LA PRUEBA ────────────────────
    #
    # Auditoria del 2026-09-04. Esta sonda importaba
    #
    #     ...,sklearn,xgboost,torch,openmm;  ...  from api.main import app
    #
    # es decir, `xgboost` ANTES que `torch`. Ese orden no existe en produccion:
    # el backend arranca por `api.main`, que acaba llegando a ADMET y desde ahi
    # a torch. Y la diferencia importa, porque xgboost carga su propio runtime
    # de Visual C++ al importarse: si el paquete lleva un `msvcp140.dll` viejo,
    # importar xgboost primero deja cargada una version que torch luego acepta,
    # mientras que en el orden real torch la pide y falla con `WinError 1114`.
    #
    # O sea: la sonda pasaba por hacer algo que el producto no hace, y el
    # `WinError 1114` de una instalacion limpia no aparecia aqui. Un
    # verificador que reordena para que le salga bien no verifica nada.
    #
    # Ahora se comprueba en DOS pasos y en el orden de verdad:
    #
    #   1. `api.main` primero, tal como arranca el backend, y con torch
    #      importado DESPUES de las dependencias cientificas pesadas.
    #   2. La prediccion de ADMET de verdad sobre una molecula, porque el
    #      sintoma de la DLL incompatible no es una excepcion en el import
    #      sino que ADMET devuelve None en todo. Un import que carga y un
    #      modelo que predice no son la misma comprobacion.
    import_probe = (
        "import os,sys;"
        "sys.path.insert(0,os.environ['MOLDESIGN_BUNDLE_BACKEND']);"
        "from api.main import app;"
        "assert app is not None;"
        "import torch;"
        "import fastapi,uvicorn,numpy,scipy,sklearn,xgboost,openmm;"
        "from rdkit import Chem;"
        "import meeko;"
        "from chem.blood_viability import predict_admet_ai;"
        "_p=predict_admet_ai('CC(=O)Oc1ccccc1C(=O)O');"
        "_vivos=[k for k,v in _p.items() if v is not None];"
        "assert _vivos, "
        "  'ADMET devolvio None en TODOS los campos: el modelo carga pero no predice. "
        "Suele ser el runtime de Visual C++ del paquete (ver bundle_helper, [6a2/7]).';"
        "print('imports: ok (api.main -> torch -> admet: %d campos)' % len(_vivos))"
    )
    with tempfile.TemporaryDirectory(prefix="moldesign-bundle-verify-") as temp_dir:
        env = runtime_environment(backend, vina, Path(temp_dir))
        # 120 s bastaban en caliente y fallaban en frio. Importar torch, openmm,
        # rdkit y sklearn desde un runtime de 1.9 GB recien copiado tarda ~30 s
        # con la cache del sistema llena y varios minutos sin ella: es
        # exactamente la situacion del PRIMER arranque en la maquina de un
        # investigador, que es el caso que esta comprobacion existe para cubrir.
        # Un timeout apretado no detecta una dependencia global; solo convierte
        # un disco lento en un fallo de empaquetado.
        run_checked([str(python), "-B", "-c", import_probe], cwd=backend, env=env, timeout=600)
    run_checked([str(vina), "--version"], cwd=vina.parent, timeout=30)


def validate_lightweight_models(resources: Path) -> None:
    """Carga los modelos ligeros exactos con el Python que se instalará.

    Presencia y hash no bastan: un checkpoint puede estar intacto y no ser
    compatible con la arquitectura o las DLL del runtime. Esta sonda carga
    XGBoost y CL-GNN estrictamente desde el bundle staged.
    """
    python = resources / "python" / "python.exe"
    backend = resources / "backend"
    rescoring = resources / "rescoring"
    vina = resources / "tools" / "vina" / "vina.exe"
    model_manifest_path = rescoring / "artifacts" / "model-manifest.json"
    manifest = json.loads(model_manifest_path.read_text(encoding="utf-8"))
    clgnn = manifest["models"]["gnn_v2_cl"]

    for field in ("file", "metadata_file"):
        relative = clgnn[field]
        artifact = rescoring / "artifacts" / relative
        if not artifact.is_file():
            raise FileNotFoundError(f"Modelo ligero ausente del bundle: {relative}")
        expected = clgnn["sha256" if field == "file" else "metadata_sha256"]
        actual = sha256(artifact)
        if actual != expected:
            raise RuntimeError(
                f"Hash de modelo ligero incorrecto: {relative}; "
                f"esperado={expected}, actual={actual}"
            )

    probe = (
        "import os,sys;"
        "sys.path.insert(0,os.environ['MOLDESIGN_BUNDLE_BACKEND']);"
        "sys.path.insert(0,os.environ['MOLDESIGN_BUNDLE_RESCORING']);"
        "import xgboost as xgb;"
        "b=xgb.Booster();"
        "b.load_model(os.path.join(os.environ['MOLDESIGN_BUNDLE_RESCORING'],'artifacts','model_a_universal.json'));"
        "assert len(b.feature_names or [])==167, 'contrato XGBoost inesperado';"
        "from services.ai.clgnn_inference import _load_model;"
        "m,d=_load_model();"
        "assert m is not None, 'CL-GNN no cargo desde el bundle';"
        "n=sum(p.numel() for p in m.parameters() if p.requires_grad);"
        "assert n==677657, 'arquitectura CL-GNN inesperada: %d' % n;"
        "print('modelos ligeros: XGBoost 167 features; CL-GNN %d parametros en %s' % (n,d))"
    )
    with tempfile.TemporaryDirectory(prefix="moldesign-models-verify-") as temp_dir:
        env = runtime_environment(backend, vina, Path(temp_dir))
        env["MOLDESIGN_BUNDLE_RESCORING"] = str(rescoring)
        run_checked([str(python), "-B", "-c", probe], cwd=backend, env=env, timeout=300)


def validate_open_babel(resources: Path) -> None:
    r"""Open Babel, comprobado como se usa: desde el BACKEND EMPAQUETADO.

    `check_openbabel_boundary.py` ya ejecuta el binario y comprueba su hash.
    Esto comprueba otra cosa, y por eso no sobra: que el **adaptador del backend
    que viaja en el instalador** localiza el programa, verifica su hash y lo
    ejecuta, corriendo bajo el intérprete empaquetado y con el entorno exacto de
    producción.

    Es la diferencia entre «el archivo está y funciona» y «el código instalado
    lo encuentra». Aquí ya se pagó esa distinción: `_obabel_del_bundle()`
    resolvía a un lanzador de pip con la ruta del intérprete de la máquina de
    construcción incrustada, y en el equipo del usuario no existía.

    Se ejecuta con `MOLDESIGN_OPENBABEL_DIR` SIN definir, a propósito: así se
    comprueba la resolución por defecto —la que usará el backend si el
    contenedor Tauri no pasara la variable— y no una que le damos hecha.
    """
    python = resources / "python" / "python.exe"
    backend = resources / "backend"
    vina = resources / "tools" / "vina" / "vina.exe"
    herramienta = resources / "tools" / "openbabel"
    if not (herramienta / "bin" / "obabel.exe").is_file():
        raise FileNotFoundError(
            f"Open Babel no está en el runtime staged: {herramienta}. "
            "Viaja en el instalador; su ausencia es un empaquetado incompleto."
        )

    sonda = (
        "import asyncio,os,sys;"
        "sys.path.insert(0,os.environ['MOLDESIGN_BUNDLE_BACKEND']);"
        "from services.external_tools import open_babel as ob;"
        "e=ob.estado_actual(verificar_version=True);"
        "assert e.estado is ob.EstadoOpenBabel.AVAILABLE, e.detalle;"
        "assert e.licencia_spdx=='GPL-2.0-only', e.licencia_spdx;"
        "assert e.ruta_relativa=='tools/openbabel/bin/obabel.exe', e.ruta_relativa;"
        "p='\\n'.join(['ROOT',"
        "'ATOM      1  C   UNL     1       0.000   0.000   0.000  1.00  0.00     0.000 C ',"
        "'ATOM      2  C   UNL     1       1.520   0.000   0.000  1.00  0.00     0.000 C ',"
        "'ATOM      3  O   UNL     1       2.100   1.080   0.000  1.00  0.00    -0.270 OA',"
        "'ENDROOT','TORSDOF 0','']);"
        "c=asyncio.run(ob.convertir_pdbqt_a_sdf(p));"
        "assert ob.sdf_es_valido(c.contenido), 'el SDF convertido no es utilizable';"
        "n=next(int(l[:3]) for l in c.contenido.splitlines() if 'V2000' in l);"
        "assert n==3, 'entraron 3 atomos y salieron %d' % n;"
        "print('open babel: ok (%s, %s, sha256 %s)' % "
        "(e.version_declarada, e.licencia_spdx, (e.sha256 or '')[:12]))"
    )
    with tempfile.TemporaryDirectory(prefix="moldesign-obabel-verify-") as temp_dir:
        env = runtime_environment(backend, vina, Path(temp_dir))
        env.pop("MOLDESIGN_OPENBABEL_DIR", None)
        run_checked([str(python), "-B", "-c", sonda], cwd=backend, env=env, timeout=180)


def runtime_environment(backend: Path, vina: Path, temp_dir: Path) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "APP_MODE": "DESKTOP",
            "ENVIRONMENT": "production",
            "LOCAL_DATA_DIR": str(temp_dir / "data"),
            "MOLDESIGN_BUNDLE_BACKEND": str(backend),
            "PYTHONPATH": str(backend),
            "PYTHONDONTWRITEBYTECODE": "1",
            # El mismo que pone `spawn_backend` en produccion (doc 73 §1). Sin
            # el, este arranque comprueba un entorno que ningun usuario tiene:
            # el Python embebido abre en cp1252 y corrompe lecturas en silencio.
            "PYTHONUTF8": "1",
            "SECRET_KEY": "bundle-verification-only-" + ("x" * 40),
            "VINA_EXECUTABLE_PATH": str(vina),
            "TABPFN_NO_BROWSER": "true",
        }
    )
    return env


def reserve_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.bind(("127.0.0.1", 0))
        return int(server.getsockname()[1])


def validate_backend_health(resources: Path) -> None:
    python = resources / "python" / "python.exe"
    backend = resources / "backend"
    vina = resources / "tools" / "vina" / "vina.exe"
    port = reserve_port()

    with tempfile.TemporaryDirectory(prefix="moldesign-health-verify-") as temp_dir:
        temp_path = Path(temp_dir)
        env = runtime_environment(backend, vina, temp_path)
        log_path = temp_path / "backend.log"
        creation_flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        with log_path.open("w", encoding="utf-8") as log_handle:
            process = subprocess.Popen(
                [
                    str(python),
                    "-B",
                    "-m",
                    "uvicorn",
                    "api.main:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                    "--loop",
                    "asyncio",
                    "--app-dir",
                    str(backend),
                ],
                cwd=backend,
                env=env,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                creationflags=creation_flags,
            )
        try:
            deadline = time.monotonic() + 120
            last_error = "sin respuesta"
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    last_error = f"el backend terminó con código {process.returncode}"
                    break
                try:
                    with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as response:
                        body = json.loads(response.read().decode("utf-8"))
                    if (
                        body.get("app") == "mol-design"
                        and body.get("app_mode") == "DESKTOP"
                        and body.get("version")
                        and body.get("components", {}).get("database", {}).get("status") == "healthy"
                    ):
                        return
                    last_error = f"contrato de salud incompleto: {body}"
                except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
                    last_error = str(exc)
                time.sleep(0.5)
            tail = log_path.read_text(encoding="utf-8", errors="replace")[-5000:]
            raise RuntimeError(f"El backend staged no pasó /health: {last_error}\n{tail}")
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)


def validate_backend_freshness(root: Path, resources: Path) -> list[str]:
    """
    El backend staged tiene que ser EL del repositorio, archivo por archivo.

    Por qué existe esta comprobación
    --------------------------------
    `resources/` es artefacto de build: `bundle_helper` lo borra y lo recopia.
    Pero nada obligaba a re-stagear antes de empaquetar, y un staging viejo
    producía un instalador con un backend atrasado.

    Y el fallo era INVISIBLE. Las etapas nuevas del pipeline se importan dentro
    de un `try/except` para que un fallo suyo no tumbe un docking terminado; un
    módulo ausente se degrada a `None` en silencio. El runtime arrancaba, pasaba
    `/health`, y producía evaluaciones sin validación física ni selector de pose
    — con la interfaz diciendo «no evaluada» y el dossier declarándolo, todo
    formalmente correcto, describiendo un producto sin sus funciones.

    `critical_assets` no lo cubría: sella 7 archivos, y del backend sólo
    `api/main.py`. Aquí se compara el árbol entero.
    """
    import hashlib

    vivo = root.resolve() / "backend"
    staged = resources / "backend"
    if not vivo.is_dir():
        return [f"No se encuentra el backend fuente: {vivo}"]

    def digest(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    # Las mismas exclusiones que aplica `bundle_helper` al copiar: comparar
    # contra lo que NO se copia produciría un falso positivo permanente.
    def excluido(relativo: Path) -> bool:
        partes = {parte.lower() for parte in relativo.parts}
        if partes & {"__pycache__", "tests", "logs", "crash_dumps", "magicmock"}:
            return True
        nombre = relativo.name
        return (
            nombre.startswith("test_")
            or nombre.endswith(("_test.py", ".pyc", ".pyo"))
        )

    faltantes: list[str] = []
    distintos: list[str] = []
    for archivo in sorted(vivo.rglob("*.py")):
        relativo = archivo.relative_to(vivo)
        if excluido(relativo):
            continue
        destino = staged / relativo
        if not destino.is_file():
            faltantes.append(relativo.as_posix())
        elif digest(archivo) != digest(destino):
            distintos.append(relativo.as_posix())

    errores: list[str] = []
    if faltantes:
        errores.append(
            "El backend staged NO tiene módulos que sí están en el repositorio "
            "(el instalador saldría sin ellos, y degradarían en silencio):\n- "
            + "\n- ".join(faltantes[:40])
        )
    if distintos:
        errores.append(
            "El backend staged está desfasado respecto al repositorio:\n- "
            + "\n- ".join(distintos[:40])
        )
    if errores:
        errores.append("Vuelve a ejecutar `npm run stage:desktop` antes de empaquetar.")
    return errores


def validate_declared_dependencies(root: Path, resources: Path) -> list[str]:
    """
    Lo que `requirements.txt` declara tiene que estar en el Python empaquetado.

    `posebusters` estaba declarado y ausente del bundle: el validador físico no
    habría podido ejecutarse en el producto instalado, y la etapa se habría
    declarado `not_evaluated` en cada corrida sin que nada fallara.
    """
    requisitos = root.resolve() / "backend" / "requirements.txt"
    site = resources / "python" / "Lib" / "site-packages"
    if not requisitos.is_file() or not site.is_dir():
        return []

    # Sólo las que el camino científico necesita de verdad. La lista es corta a
    # propósito: comprobar las ~200 de `requirements.txt` produciría ruido por
    # los nombres de distribución que no coinciden con el del paquete.
    criticas = {
        "posebusters": "posebusters",
        "xgboost": "xgboost",
        "rdkit": "rdkit",
        "scipy": "scipy",
        "numpy": "numpy",
    }
    declarado = requisitos.read_text(encoding="utf-8", errors="replace").lower()
    presentes = {entrada.name.lower() for entrada in site.iterdir()}

    ausentes = [
        nombre for nombre, modulo in criticas.items()
        if nombre in declarado and modulo not in presentes
    ]
    if ausentes:
        return [
            "Dependencias declaradas en requirements.txt que NO están en el runtime "
            "empaquetado: " + ", ".join(sorted(ausentes))
            + ". Instálalas en `python-embed` y vuelve a ejecutar `npm run stage:desktop`."
        ]
    return []


def validate_catalog_structures(resources: Path) -> list[str]:
    """Cada objetivo del catalogo viaja con su estructura.

    Sin esto, un objetivo del catalogo sin `.pdb.gz` en el bundle solo se nota
    en la maquina del investigador: aqui `data/targets` esta lleno, y ademas
    `data/target_library` -que NO se empaqueta- adelanta estructuras que el
    usuario nunca tendra. Lo que le pasaria a el es que el receptor exige RED
    para descargarse del RCSB, en un producto que se vende como offline.
    """
    catalogo = resources / "curated_targets.json"
    estructuras = resources / "data" / "targets"
    if not catalogo.is_file() or not estructuras.is_dir():
        return [f"El bundle no trae catalogo o estructuras: {catalogo}, {estructuras}"]

    disponibles = {ruta.name[:-7].upper() for ruta in estructuras.glob("*.pdb.gz")}
    disponibles |= {ruta.stem.upper() for ruta in estructuras.glob("*.pdb")}
    objetivos = json.loads(catalogo.read_text(encoding="utf-8"))
    faltan = sorted(
        objetivo["pdb_id"].upper()
        for objetivo in objetivos
        if objetivo["pdb_id"].upper() not in disponibles
    )
    if faltan:
        return [
            f"{len(faltan)} objetivos del catalogo no traen estructura empaquetada "
            f"y exigirian red para acoplar: {faltan[:20]}"
        ]
    return []


def validate_peptide_abstention(resources: Path) -> None:
    """El runtime embebido reproduce la abstención peptídica.

    `docs/76_DECISION_TRANSFERENCIA_ESMFOLD_A_LIGANDO_V1.md` §8 y §9.8: la
    abstención de la frontera estructura→ligando es un resultado científico
    válido y tiene que viajar igual por el backend empaquetado.

    NO se carga ESMFold: son 8.44 GB y minutos de CPU, y un gate de build no es
    el sitio. Lo que sí se ejerce, dentro del runtime staged y con su intérprete,
    es la primitiva de la abstención:

      - `_fallback_poses` marca `folded_structure_only` y deja la afinidad en
        `None` — es la función que devuelve la estructura plegada cuando el
        acoplamiento no se pudo hacer;
      - `DockingResult.best_affinity` sigue siendo obligatorio, que es lo que
        impide rellenar el contrato con un número inventado;
      - el código peptídico empaquetado no contiene la aritmética que derivaba
        una afinidad de una confianza.

    Antes de las correcciones del 2026-09-04 ese camino reportaba −4.0 kcal/mol
    para cualquier resultado real de Vina. Esta comprobación existe para que no
    vuelva por la puerta del instalador.
    """
    python = resources / "python" / "python.exe"
    backend = resources / "backend"

    probe = (
        "import os,sys;"
        "sys.path.insert(0,os.environ['MOLDESIGN_BUNDLE_BACKEND']);"
        "sys.path.insert(0,os.path.join(os.environ['MOLDESIGN_BUNDLE_BACKEND'],'sidecars','esmfold'));"
        "from predictor import ESMFoldFastPredictor, ORIGEN_SOLO_PLEGADO;"
        "p=ESMFoldFastPredictor._fallback_poses('no_existe.pdb')[0];"
        "assert p.origen==ORIGEN_SOLO_PLEGADO, 'la pose sin acoplar no se marca';"
        "assert p.vina_affinity_kcal_mol is None, 'se fabrico una afinidad sin acoplamiento';"
        "from core.models import DockingResult;"
        "assert DockingResult.model_fields['best_affinity'].is_required(), "
        "  'best_affinity dejo de ser obligatorio: el contrato se podria rellenar con -4.0';"
        "import pathlib;"
        "peptido=pathlib.Path(os.environ['MOLDESIGN_BUNDLE_BACKEND'])/'services'/'docking'/'peptide_docking.py';"
        "codigo=[l for l in peptido.read_text(encoding='utf-8').splitlines() "
        "  if not l.strip().startswith('#')];"
        "malas=[l for l in codigo if 'min(-4.0' in l.replace(' ','')];"
        "assert not malas, 'volvio el clamp que devolvia -4.0: %r' % malas;"
        "print('abstencion peptidica: ok')"
    )

    with tempfile.TemporaryDirectory(prefix="moldesign-abstencion-") as temp_dir:
        env = runtime_environment(backend, resources / "tools" / "vina" / "vina.exe", Path(temp_dir))
        result = subprocess.run(
            [str(python), "-c", probe],
            capture_output=True, text=True, timeout=300, env=env,
            cwd=str(backend),
        )
    if result.returncode != 0:
        raise RuntimeError(
            "El runtime embebido no reproduce la abstencion peptidica:\n"
            + (result.stderr or result.stdout)[-2000:]
        )


def validate_m5_manifest(root: Path, resources: Path) -> list[str]:
    """El manifiesto de M5-Zn, idéntico byte a byte en el runtime embebido.

    Gate §10.8 de `docs/75_DECISION_CIENTIFICA_M5_ZN_V1.md`: el backend
    empaquetado tiene que ejecutar los mismos perfiles y manifiestos que los
    tests. Si el bundle lleva una copia distinta —o no lleva ninguna— el
    producto instalado puntúa con otros pesos que los validados, y nada lo
    dice.

    Se comparan los BYTES, no el contenido parseado: el manifiesto es un
    artefacto determinista y una diferencia de formato ya significa que salió
    de otro sitio.
    """
    relativa = Path("services/pipeline/protocols/m5/m5_zn_manifest.json")
    origen = root / "backend" / relativa
    copia = resources / "backend" / relativa

    if not origen.is_file():
        return [f"Falta el manifiesto de M5-Zn en el repositorio: {origen}"]
    if not copia.is_file():
        return [
            f"El runtime staged no lleva el manifiesto de M5-Zn ({relativa}). "
            "Sin él, el backend empaquetado no puede aplicar los perfiles."
        ]

    if origen.read_bytes() != copia.read_bytes():
        return [
            f"El manifiesto de M5-Zn del bundle difiere del repositorio "
            f"({relativa}). El producto instalado puntuaría con otros pesos."
        ]
    return []


def main(root: Path) -> None:
    resources = root.resolve() / "frontend" / "src-tauri" / "resources"
    if not resources.is_dir():
        raise FileNotFoundError(f"Runtime staged ausente: {resources}")

    errors = validate_manifest(resources)
    errors += validate_catalog_structures(resources)
    errors += validate_backend_freshness(root, resources)
    errors += validate_declared_dependencies(root, resources)
    errors += validate_m5_manifest(root, resources)
    forbidden = find_forbidden_files(resources)
    if forbidden:
        errors.append("Archivos prohibidos en el bundle:\n- " + "\n- ".join(forbidden[:100]))
    if errors:
        raise RuntimeError("\n".join(errors))

    before = tree_state(resources)
    validate_native_dependencies(resources)
    validate_runtime(resources)
    validate_lightweight_models(resources)
    validate_open_babel(resources)
    validate_backend_health(resources)
    validate_peptide_abstention(resources)
    after = tree_state(resources)
    if before != after:
        added = sorted(set(after) - set(before))
        removed = sorted(set(before) - set(after))
        changed = sorted(path for path in set(before) & set(after) if before[path] != after[path])
        raise RuntimeError(
            "La verificación mutó el runtime staged. "
            f"added={added[:20]} removed={removed[:20]} changed={changed[:20]}"
        )
    manifest = json.loads((resources / "runtime-manifest.json").read_text(encoding="utf-8"))
    print(
        "Runtime desktop verificado: "
        f"{manifest['total']['files']} archivos, {manifest['total']['mib']} MiB; "
        "sin secretos/estado local; backend al día con el repositorio; "
        "dependencias y modelos ligeros presentes y cargables; imports, Vina y /health correctos; "
        "Open Babel localizado por el backend empaquetado y convirtiendo."
    )


if __name__ == "__main__":
    main(parse_args().root)
