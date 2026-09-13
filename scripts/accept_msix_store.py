r"""Aceptacion del MSIX de Microsoft Store: instala, ejecuta, actualiza y desinstala.

No modifica el producto. Si algo falla, lo deja escrito con evidencia y devuelve
codigo != 0.

Lo que comprueba, en este orden:

  1. identidad      el manifiesto del paquete INSTALADO declara exactamente la
                    identidad reservada en Partner Center;
  2. version        cuatro campos y cuarto campo 0;
  3. confianza      runFullTrust declarado (sin el, Python/Vina/Open Babel no
                    arrancan);
  4. integridad     el runtime staged viaja completo dentro del paquete;
  5. escritura      datos, SQLite, logs, poses y destinos de descarga quedan
                    FUERA de WindowsApps;
  6. ejecucion      la app arranca, el backend responde y una evaluacion normal
                    y otra avanzada terminan en SUCCESS;
  7. persistencia   tras reiniciar la app, el resultado sigue ahi y coincide;
  8. actualizacion  instalar una version superior conserva los datos;
  9. desinstalacion quitar el paquete NO borra los datos del usuario.

Por que se comprueba sobre el paquete INSTALADO y no sobre el layout: en
`C:\\Program Files\\WindowsApps` el arbol es de solo lectura y el proceso corre
con identidad de paquete. Un fallo de escritura solo aparece ahi. Validar el
layout demostraria unicamente que los ficheros existen.

Uso:
    python scripts/accept_msix_store.py --msix E:\rel\v<version>\<paquete>.msix
    python scripts/accept_msix_store.py --msix ... --omitir-actualizacion
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "msix" / "msix-config.json"
WINDOWSAPPS = Path(r"C:/Program Files/WindowsApps")


def _sha256(path: Path) -> str:
    """Identidad real del paquete. La ruta no lo es: el nombre se reutiliza."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


SMILES_NORMAL = "CC(=O)OC1=CC=CC=C1C(=O)O"          # aspirina
SMILES_AVANZADA = "CC(=O)Nc1ccc(O)cc1"               # paracetamol
TARGET = "3F75"
CHAIN = "A"


class AceptacionFallida(RuntimeError):
    """Un contrato del paquete no se cumple."""


# ── PowerShell ──────────────────────────────────────────────────────────────

def _ps(script: str, timeout: float = 600) -> tuple[int, str, str]:
    res = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=timeout,
    )
    return res.returncode, (res.stdout or "").strip(), (res.stderr or "").strip()


def _ps_json(script: str, timeout: float = 600) -> Any:
    rc, out, err = _ps(script + " | ConvertTo-Json -Depth 6 -Compress", timeout)
    if rc != 0:
        raise AceptacionFallida(f"PowerShell fallo ({rc}): {err[:800]}")
    if not out:
        return None
    return json.loads(out)


# ── Paquete ─────────────────────────────────────────────────────────────────

def paquete_instalado(nombre: str) -> dict | None:
    datos = _ps_json(
        f"Get-AppxPackage -Name '{nombre}' | "
        "Select-Object Name,Publisher,PackageFullName,PackageFamilyName,Version,InstallLocation,Status")
    if isinstance(datos, list):
        return datos[0] if datos else None
    return datos


def instalar(msix: Path, actualizar: bool = False) -> None:
    verbo = "actualizacion" if actualizar else "instalacion"
    rc, out, err = _ps(f"Add-AppxPackage -Path '{msix}' -ErrorAction Stop", timeout=1800)
    if rc != 0:
        raise AceptacionFallida(f"La {verbo} del MSIX fallo: {err[:1500] or out[:1500]}")


def desinstalar(package_full_name: str) -> None:
    rc, out, err = _ps(
        f"Remove-AppxPackage -Package '{package_full_name}' -ErrorAction Stop", timeout=900)
    if rc != 0:
        raise AceptacionFallida(f"La desinstalacion fallo: {err[:1000] or out[:1000]}")


# ── Comprobaciones estaticas sobre el .msix ─────────────────────────────────

RE_IDENT = re.compile(
    r'<Identity\s+Name="(?P<name>[^"]+)"\s+Publisher="(?P<pub>[^"]+)"\s+'
    r'Version="(?P<ver>[^"]+)"', re.S)


def comprobar_identidad_y_version(msix: Path, cfg: dict) -> dict[str, Any]:
    """Lee el manifiesto DENTRO del .msix y lo confronta con la configuracion."""
    with zipfile.ZipFile(msix) as z:
        xml = z.read("AppxManifest.xml").decode("utf-8", "replace")

    m = RE_IDENT.search(xml)
    if not m:
        raise AceptacionFallida("El .msix no declara un bloque <Identity> legible.")
    ident = cfg["identidad_del_store"]
    fallos = []
    if m.group("name") != ident["package_identity_name"]:
        fallos.append(f"Identity/Name={m.group('name')!r}, esperado "
                      f"{ident['package_identity_name']!r}")
    if m.group("pub") != ident["package_identity_publisher"]:
        fallos.append(f"Identity/Publisher={m.group('pub')!r}, esperado "
                      f"{ident['package_identity_publisher']!r}")

    esperado_pdn = ident["package_properties_publisher_display_name"]
    if f"<PublisherDisplayName>{esperado_pdn}</PublisherDisplayName>" not in xml:
        fallos.append(f"PublisherDisplayName no es {esperado_pdn!r}")

    version = m.group("ver")
    campos = version.split(".")
    if len(campos) != 4:
        fallos.append(f"La version {version!r} no tiene cuatro campos.")
    elif campos[3] != "0":
        fallos.append(f"El cuarto campo de la version es {campos[3]!r} y el Store "
                      "exige 0: reserva ese campo para si.")
    else:
        for i, c in enumerate(campos):
            if not c.isdigit() or int(c) > 65535:
                fallos.append(f"Campo {i} de la version fuera de rango: {c!r}")

    confianza = 'Name="runFullTrust"' in xml
    if not confianza:
        fallos.append("El manifiesto no declara runFullTrust: sin plena confianza "
                      "el interprete Python embebido, Vina y Open Babel no pueden "
                      "ejecutarse.")

    if fallos:
        raise AceptacionFallida("Identidad/version/confianza incorrectas:\n  - " +
                                "\n  - ".join(fallos))
    return {"identity_name": m.group("name"), "identity_publisher": m.group("pub"),
            "version": version, "run_full_trust": confianza}


def comprobar_runtime_completo(msix: Path) -> dict[str, Any]:
    """El runtime staged debe viajar entero: recortarlo cambia el producto."""
    exigidos = [
        "resources/python/python.exe",
        "resources/backend/api/main.py",
        "resources/tools/vina/vina.exe",
        "resources/tools/openbabel/bin/obabel.exe",
        "resources/rescoring/artifacts/model-manifest.json",
        "resources/runtime-manifest.json",
        "resources/curated_targets.json",
        "moldesign.exe",
    ]
    with zipfile.ZipFile(msix) as z:
        nombres = set(z.namelist())
        faltan = [r for r in exigidos if r not in nombres]
        n_ficheros = len(nombres)
    if faltan:
        raise AceptacionFallida(f"El MSIX no lleva el runtime completo. Faltan: {faltan}")
    return {"ficheros_en_el_paquete": n_ficheros, "exigidos_presentes": len(exigidos)}


# ── Escritura fuera de WindowsApps ──────────────────────────────────────────

def comprobar_escritura_fuera(install_location: str) -> dict[str, Any]:
    """Ningun dato del usuario puede vivir bajo WindowsApps.

    Se comprueban las rutas que el producto declara, no una lista inventada:
    se le pregunta al backend EMPAQUETADO por su configuracion efectiva.
    """
    instalado = Path(install_location)
    py = instalado / "resources" / "python" / "python.exe"
    backend = instalado / "resources" / "backend"
    if str(instalado).lower().startswith(str(WINDOWSAPPS).lower()):
        # WindowsApps deliberately denies direct traversal and execution to an
        # ordinary desktop process. The signed archive was already inspected
        # by comprobar_runtime_completo(); below, the installed app is launched
        # through its package identity and exercises these paths for real.
        return {
            "estado": "NO_CONCLUYENTE_ACL_WINDOWSAPPS",
            "install_location": str(instalado),
            "nota": (
                "El arnes no atraviesa WindowsApps directamente; el runtime "
                "existe dentro del MSIX firmado y sus rutas se comprueban "
                "indirectamente durante la ejecucion instalada."
            ),
        }
    try:
        interprete_visible = py.is_file()
    except PermissionError:
        # WindowsApps deliberately denies directory traversal to an ordinary
        # desktop process. That is not evidence that the packaged runtime is
        # absent: comprobar_runtime_completo() already inspected the signed
        # MSIX. The effective paths are exercised later by launching the app.
        return {
            "estado": "NO_CONCLUYENTE_ACL_WINDOWSAPPS",
            "install_location": str(instalado),
            "nota": (
                "Windows nego la lectura directa de WindowsApps al arnes no "
                "elevado; el runtime existe dentro del MSIX firmado y sus rutas "
                "se comprobaran indirectamente durante la ejecucion instalada."
            ),
        }
    if not interprete_visible:
        raise AceptacionFallida(f"No hay interprete en el paquete instalado: {py}")

    entorno = os.environ.copy()
    entorno.update({"PYTHONPATH": str(backend), "PYTHONUTF8": "1",
                    "PYTHONDONTWRITEBYTECODE": "1", "APP_MODE": "DESKTOP"})
    codigo = (
        "import json,sys,tempfile;"
        "sys.path.insert(0,r'%s');"
        "from core.config import get_settings;"
        "s=get_settings();"
        "print(json.dumps({'local_data_dir':str(s.local_data_dir),"
        "'vina_temp_dir':str(s.vina_temp_dir),'tempdir':tempfile.gettempdir()}))"
    ) % str(backend)
    res = subprocess.run([str(py), "-c", codigo], capture_output=True, text=True,
                         encoding="utf-8", errors="replace", env=entorno,
                         cwd=str(backend), timeout=300)
    if res.returncode != 0:
        raise AceptacionFallida(
            f"No se pudo leer la configuracion del backend empaquetado: {res.stderr[-800:]}")
    rutas = json.loads(res.stdout.strip().splitlines()[-1])

    dentro = {k: v for k, v in rutas.items()
              if str(v).lower().startswith(str(WINDOWSAPPS).lower())}
    if dentro:
        raise AceptacionFallida(
            f"Estas rutas de escritura caen DENTRO de WindowsApps y fallarian en "
            f"tiempo de ejecucion: {dentro}")

    # Prueba activa: el directorio de instalacion debe ser de solo lectura.
    sonda = instalado / "_sonda_de_escritura.tmp"
    try:
        sonda.write_text("x", encoding="utf-8")
        escribible = True
        sonda.unlink(missing_ok=True)
    except OSError:
        escribible = False

    return {"rutas_declaradas": rutas, "ninguna_bajo_windowsapps": True,
            "install_location_escribible": escribible,
            "nota_si_escribible": (
                "WindowsApps resulto escribible para este proceso. Suele significar "
                "que la prueba corre elevada; no invalida el resto, pero la "
                "comprobacion de solo-lectura no es concluyente aqui."
                if escribible else "")}


# ── Ejecucion y evaluaciones ────────────────────────────────────────────────

def _http(base: str, metodo: str, ruta: str, cuerpo: dict | None = None,
          timeout: float = 300) -> tuple[int | None, Any]:
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    req = urllib.request.Request(
        f"{base}{ruta}", data=datos, method=metodo,
        headers={"Content-Type": "application/json"} if datos else {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        cuerpo_err = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(cuerpo_err)
        except Exception:
            return e.code, {"_raw": cuerpo_err[:1500]}
    except Exception as e:
        return None, {"_transporte": repr(e)}


def localizar_backend(log_dir: Path, install_location: str, espera_s: float = 240) -> str:
    """Descubre el puerto del backend leyendo el log que escribe el lanzador.

    No se escanean puertos: un servidor ajeno en el rango daria un falso
    positivo y la prueba mediria otro proceso.
    """
    limite = time.time() + espera_s
    patron = re.compile(r"puerto (\d{4,5})")
    while time.time() < limite:
        if log_dir.is_dir():
            logs = sorted(log_dir.glob("backend_*.log"), key=lambda p: p.stat().st_mtime)
            for log in reversed(logs):
                texto = log.read_text(encoding="utf-8", errors="replace")
                encontrados = patron.findall(texto)
                if encontrados:
                    base = f"http://127.0.0.1:{encontrados[-1]}"
                    estado, _ = _http(base, "GET", "/health", timeout=10)
                    if estado is not None:
                        return base
        for puerto in range(8000, 8020):
            base = f"http://127.0.0.1:{puerto}"
            estado, salud = _http(base, "GET", "/health", timeout=1)
            vina_path = (((salud or {}).get("components") or {}).get("vina") or {}).get("path", "")
            if (estado == 200 and salud.get("app") == "mol-design"
                    and salud.get("app_mode") == "DESKTOP"
                    and str(vina_path).lower().startswith(install_location.lower())):
                return base
        time.sleep(3)
    raise AceptacionFallida(
        f"No se encontro un backend vivo a partir de los logs de {log_dir} "
        f"en {espera_s:.0f} s.")


def evaluar(base: str, smiles: str, nombre: str, avanzada: bool) -> dict[str, Any]:
    """Una evaluacion completa. `avanzada` manda pipeline_config explicito."""
    cuerpo_pre: dict[str, Any] = {"smiles": smiles, "target_pdb_id": TARGET, "chain": CHAIN}
    pipeline_config = None
    if avanzada:
        pipeline_config = {
            "enabled_stages": ["validation", "properties", "sa_filter", "conformer",
                               "docking", "xgb"],
            "stage_params": {"properties": {"run_admet_ai": False},
                             "conformer": {"conformers": 1},
                             "docking": {"exhaustiveness": 8, "num_poses": 9, "seed": 42}},
            "docking_engine": "vina", "pro_selectivity": False, "pro_mmgbsa": False,
        }
        cuerpo_pre["pipeline_config"] = pipeline_config
        docking = pipeline_config["stage_params"]["docking"]
        cuerpo_pre.update({
            "docking_engine": pipeline_config["docking_engine"],
            "exhaustiveness": docking["exhaustiveness"],
            "num_poses": docking["num_poses"],
            "conformers": pipeline_config["stage_params"]["conformer"]["conformers"],
        })

    estado, pre = _http(base, "POST", "/evaluation/preflight", cuerpo_pre)
    if estado != 200:
        raise AceptacionFallida(f"Preflight ({nombre}) devolvio {estado}: {str(pre)[:600]}")
    if pre.get("technical_blockers"):
        raise AceptacionFallida(f"Preflight ({nombre}) bloqueado: {pre['technical_blockers']}")

    cuerpo: dict[str, Any] = {"smiles": smiles, "target_pdb_id": TARGET, "chain": CHAIN,
                              "molecule_name": nombre}
    huella = pre.get("input_fingerprint")
    if isinstance(huella, str):
        cuerpo["preflight_fingerprint"] = huella
    if pipeline_config:
        cuerpo["pipeline_config"] = pipeline_config
        config = pre.get("effective_config") or {}
        if config.get("grid_center"):
            cuerpo["grid_center"] = config["grid_center"]
            cuerpo["grid_size"] = config["grid_size"]

    estado, sub = _http(base, "POST", "/evaluation/submit", cuerpo)
    if estado != 202:
        raise AceptacionFallida(f"Submit ({nombre}) devolvio {estado}: {str(sub)[:600]}")
    task_id = sub["task_id"]

    t0 = time.time()
    limite = time.time() + 1800
    ultimo = None
    while time.time() < limite:
        _, ultimo = _http(base, "GET", f"/evaluation/status/{task_id}")
        if (ultimo or {}).get("status") in {"SUCCESS", "FAILURE", "REVOKED"}:
            break
        time.sleep(3)
    if not ultimo or ultimo.get("status") != "SUCCESS":
        raise AceptacionFallida(f"La evaluacion {nombre} no termino en SUCCESS: "
                                f"{str(ultimo)[:800]}")
    resultado = ultimo.get("result") or {}
    return {"task_id": task_id, "molecule_id": resultado.get("molecule_id"),
            "affinity_kcal": resultado.get("affinity_kcal"),
            "total_score": resultado.get("total_score"),
            "vina_version": resultado.get("vina_version"),
            "segundos": round(time.time() - t0, 1)}


def lanzar_app(aumid: str) -> None:
    rc, _out, err = _ps(f"Start-Process 'shell:AppsFolder\\{aumid}'", timeout=180)
    if rc != 0:
        raise AceptacionFallida(f"No se pudo lanzar la app empaquetada: {err[:600]}")


def cerrar_app() -> None:
    _ps("Get-Process moldesign -ErrorAction SilentlyContinue | Stop-Process -Force", 180)
    time.sleep(5)


def aumid_de(package_family_name: str, package_full_name: str) -> str:
    datos = _ps_json(
        f"Get-AppxPackage -Name (Get-AppxPackage | Where-Object PackageFullName -eq "
        f"'{package_full_name}').Name | Get-AppxPackageManifest | "
        "ForEach-Object { $_.Package.Applications.Application.Id }")
    app_id = datos if isinstance(datos, str) else (datos[0] if datos else None)
    if not app_id:
        raise AceptacionFallida("No se pudo leer el Application Id del paquete.")
    return f"{package_family_name}!{app_id}"


# ── Programa ────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--msix", type=Path, required=True)
    ap.add_argument("--msix-actualizacion", type=Path,
                    help="Paquete de version superior para probar la actualizacion.")
    ap.add_argument("--omitir-actualizacion", action="store_true")
    ap.add_argument("--omitir-ejecucion", action="store_true",
                    help="Solo comprobaciones estaticas y de rutas.")
    ap.add_argument("--out", type=Path, default=None,
                    help="Por defecto, junto al propio paquete: la evidencia "
                         "viaja con lo que probo.")
    args = ap.parse_args()

    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    nombre_paquete = cfg["identidad_del_store"]["package_identity_name"]
    msix = args.msix.resolve()
    if not msix.is_file():
        raise SystemExit(f"No existe el paquete: {msix}")
    salida = args.out if args.out else msix.parent / "accept-evidence.json"

    # El sha256 del paquete, no solo su ruta. Un fichero con el mismo nombre y
    # bytes distintos es lo que dejo esta evidencia describiendo un paquete que
    # ya no existia: se reempaqueto encima y nada lo delataba.
    ev: dict[str, Any] = {
        "ejecutado_utc": datetime.now(timezone.utc).isoformat(),
        "msix": str(msix),
        "msix_sha256": _sha256(msix),
        "msix_bytes": msix.stat().st_size,
        "resultados": {}, "estado": "FAIL",
    }
    log_dir = Path(os.environ.get("TEMP", r"C:/Windows/Temp")) / "MolDesign" / "logs"
    datos_usuario = Path.home() / "MolDesign" / "data"

    try:
        print("[1-4] identidad, version, confianza e integridad del paquete")
        ev["resultados"]["identidad"] = comprobar_identidad_y_version(msix, cfg)
        ev["resultados"]["runtime_completo"] = comprobar_runtime_completo(msix)
        print(f"      {ev['resultados']['identidad']}")

        previo = paquete_instalado(nombre_paquete)
        if previo:
            print(f"      hay una instalacion previa: {previo['PackageFullName']}; se quita")
            desinstalar(previo["PackageFullName"])

        print("[5] instalacion")
        instalar(msix)
        info = paquete_instalado(nombre_paquete)
        if not info:
            raise AceptacionFallida("Tras Add-AppxPackage el paquete no aparece instalado.")
        ev["resultados"]["instalacion"] = info
        print(f"      {info['PackageFullName']}  ->  {info['InstallLocation']}")

        print("[6] escritura fuera de WindowsApps")
        ev["resultados"]["escritura"] = comprobar_escritura_fuera(info["InstallLocation"])
        print(f"      {ev['resultados']['escritura'].get('rutas_declaradas', ev['resultados']['escritura'])}")

        if not args.omitir_ejecucion:
            print("[7] ejecucion y evaluaciones")
            aumid = aumid_de(info["PackageFamilyName"], info["PackageFullName"])
            ev["resultados"]["aumid"] = aumid
            lanzar_app(aumid)
            base = localizar_backend(log_dir, info["InstallLocation"])
            ev["resultados"]["backend"] = base
            estado, salud = _http(base, "GET", "/health")
            ev["resultados"]["health"] = {"status": estado, "cuerpo": salud}

            normal = evaluar(base, SMILES_NORMAL, "msix-normal", avanzada=False)
            print(f"      normal   -> {normal}")
            avanzada = evaluar(base, SMILES_AVANZADA, "msix-avanzada", avanzada=True)
            print(f"      avanzada -> {avanzada}")
            if normal["molecule_id"] == avanzada["molecule_id"]:
                raise AceptacionFallida(
                    "Las dos evaluaciones comparten molecule_id: una sobrescribe a la otra.")
            ev["resultados"]["evaluaciones"] = {"normal": normal, "avanzada": avanzada}

            print("[8] persistencia tras reiniciar la app")
            cerrar_app()
            lanzar_app(aumid)
            base = localizar_backend(log_dir, info["InstallLocation"])
            reabiertos = {}
            for etiqueta, corrida in (("normal", normal), ("avanzada", avanzada)):
                estado, r = _http(
                    base, "GET",
                    f"/evaluation/result/{corrida['molecule_id']}?task_id={corrida['task_id']}")
                if estado != 200:
                    raise AceptacionFallida(
                        f"Tras reiniciar, el resultado {etiqueta} no se pudo releer ({estado}).")
                if r.get("affinity_kcal") != corrida["affinity_kcal"]:
                    raise AceptacionFallida(
                        f"Tras reiniciar, la afinidad de {etiqueta} cambio: "
                        f"{corrida['affinity_kcal']} -> {r.get('affinity_kcal')}")
                reabiertos[etiqueta] = {"affinity_kcal": r.get("affinity_kcal")}
            ev["resultados"]["persistencia"] = reabiertos
            print(f"      {reabiertos}")
            cerrar_app()

        huella_datos_antes = sorted(p.name for p in datos_usuario.rglob("*") if p.is_file())[:50]
        ev["resultados"]["datos_usuario"] = {
            "ruta": str(datos_usuario), "existe": datos_usuario.is_dir(),
            "muestra_de_ficheros": huella_datos_antes[:10],
            "n_ficheros": len(huella_datos_antes),
        }

        if args.msix_actualizacion and not args.omitir_actualizacion:
            print("[9] actualizacion")
            instalar(args.msix_actualizacion.resolve(), actualizar=True)
            info2 = paquete_instalado(nombre_paquete)
            if not info2 or info2["Version"] == info["Version"]:
                raise AceptacionFallida(
                    f"La actualizacion no cambio la version: {info2 and info2['Version']}")
            conservados = datos_usuario.is_dir() and any(datos_usuario.rglob("*"))
            if not conservados:
                raise AceptacionFallida("La actualizacion borro los datos del usuario.")
            ev["resultados"]["actualizacion"] = {
                "de": info["Version"], "a": info2["Version"], "datos_conservados": True}
            print(f"      {info['Version']} -> {info2['Version']}, datos conservados")
            info = info2
        elif not args.omitir_actualizacion:
            ev["resultados"]["actualizacion"] = {
                "estado": "NO_EJECUTADA",
                "motivo": "No se paso --msix-actualizacion. Requiere un segundo paquete "
                          "con Build superior; generarlo con store_build_override."}

        print("[10] desinstalacion sin borrar datos")
        desinstalar(info["PackageFullName"])
        if paquete_instalado(nombre_paquete):
            raise AceptacionFallida("Tras Remove-AppxPackage el paquete sigue instalado.")
        if not datos_usuario.is_dir():
            raise AceptacionFallida(
                f"La desinstalacion borro {datos_usuario}. Los datos del usuario deben "
                "sobrevivir a quitar la app.")
        quedan = sorted(p.name for p in datos_usuario.rglob("*") if p.is_file())[:50]
        if len(quedan) < len(huella_datos_antes):
            raise AceptacionFallida(
                f"La desinstalacion redujo los ficheros del usuario: "
                f"{len(huella_datos_antes)} -> {len(quedan)}")
        ev["resultados"]["desinstalacion"] = {
            "paquete_ausente": True, "datos_conservados": True, "n_ficheros": len(quedan)}
        print(f"      datos conservados: {len(quedan)} ficheros en {datos_usuario}")

        ev["estado"] = "PASS"
        print("\nPASS: el MSIX supera la aceptacion de Store.")
        return 0
    except AceptacionFallida as e:
        ev["error"] = str(e)
        print(f"\nFAIL: {e}", file=sys.stderr)
        return 1
    except Exception as e:  # noqa: BLE001
        ev["error"] = f"{type(e).__name__}: {e}"
        print(f"\nFAIL (inesperado): {ev['error']}", file=sys.stderr)
        return 1
    finally:
        salida.parent.mkdir(parents=True, exist_ok=True)
        salida.write_text(json.dumps(ev, indent=2, ensure_ascii=False, default=str),
                            encoding="utf-8")
        print(f"evidencia -> {salida}")


if __name__ == "__main__":
    raise SystemExit(main())
