r"""Gate instalado del registro de casos: el caso creado reaparece tras cerrar y abrir.

`accept_msix_store.py` ejercia SQLite y las evaluaciones, pero NO el ciclo
Tauri `case_pick_parent_directory -> case_create -> persistir`. Este gate cubre
exactamente ese hueco, sobre el paquete INSTALADO y activado con identidad de
paquete (que es la unica forma de que `app_data_dir` caiga en la virtualizacion
de carpetas del MSIX y reproduzca el fallo de escritura atómica).

Como se dispara el autotest
---------------------------
La activacion de un paquete MSIX (`shell:AppsFolder\\<AUMID>`) no propaga
variables de entorno de forma fiable. El gate escribe, ANTES de lanzar, un
centinela JSON en el perfil del usuario (`~/.moldesign-case-self-test.json`).
El binario instalado lo lee en su `setup`, ejecuta el MISMO núcleo que
`case_create`/`case_read` contra el `app_data_dir` real, escribe la evidencia
donde indique el centinela y se consume (lo borra) antes de salir. En operación
normal no hay centinela y la app arranca como siempre.

No se prueba solo SQLite/backend: se persiste el registro de casos autorizados
(`authorized_cases.json`) y se comprueba que el caso reaparece en una SEGUNDA
ejecución, con carpetas de caso en C: y en D:.

Uso:
    python scripts/accept_msix_cases.py --msix E:\rel\v<version>\<paquete>.msix
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from accept_msix_store import (  # noqa: E402
    _sha256,
    aumid_de,
    cerrar_app,
    desinstalar,
    instalar,
    lanzar_app,
    paquete_instalado,
    _ps,
)

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "msix" / "msix-config.json"

SENTINEL = Path.home() / ".moldesign-case-self-test.json"
OWNER = "acceptance-gate-owner"


class GateFallido(RuntimeError):
    """El registro de casos no supero el gate instalado."""


def _escribir_centinela(mode: str, evidence: Path, **campos) -> None:
    SENTINEL.parent.mkdir(parents=True, exist_ok=True)
    SENTINEL.unlink(missing_ok=True)
    cuerpo = {"mode": mode, "evidence": str(evidence), **campos}
    SENTINEL.write_text(json.dumps(cuerpo, ensure_ascii=False), encoding="utf-8")


def _esperar_evidencia(evidence: Path, espera_s: float) -> dict:
    limite = time.time() + espera_s
    while time.time() < limite:
        if evidence.is_file():
            try:
                datos = json.loads(evidence.read_text(encoding="utf-8"))
                return datos
            except json.JSONDecodeError:
                pass  # aun escribiendo; reintentar
        if not SENTINEL.exists() and evidence.is_file():
            pass
        time.sleep(1)
    # Un ultimo intento antes de rendirse.
    if evidence.is_file():
        try:
            return json.loads(evidence.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    raise GateFallido(
        f"No aparecio evidencia en {evidence} en {espera_s:.0f} s. "
        f"centinela_presente={SENTINEL.exists()}"
    )


def _ejecutar(aumid: str, evidence: Path, req: dict, espera_s: float) -> dict:
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.unlink(missing_ok=True)
    _escribir_centinela(req["mode"], evidence, **{k: v for k, v in req.items() if k != "mode"})
    cerrar_app()  # no debe quedar una instancia previa con el centinela
    lanzar_app(aumid)
    try:
        return _esperar_evidencia(evidence, espera_s)
    finally:
        cerrar_app()


def _padre_fresco(volumen: str) -> Path:
    raiz = Path(f"{volumen}:\\")
    if not raiz.exists():
        raise GateFallido(f"El volumen {volumen}: no existe en esta maquina.")
    padre = raiz / "moldesign-accept-cases" / f"run-{uuid.uuid4().hex[:8]}"
    padre.mkdir(parents=True, exist_ok=True)
    return padre


def _evaluar_volumen(aumid: str, volumen: str, out: Path) -> dict:
    padre = _padre_fresco(volumen)
    evidencia_create = out / f"{volumen}-create.json"
    evidencia_verify = out / f"{volumen}-verify.json"

    creado = _ejecutar(
        aumid,
        evidencia_create,
        {"mode": "create", "parent": str(padre), "folder": "acceptance-case", "owner": OWNER},
        espera_s=120,
    )
    if not creado.get("ok"):
        raise GateFallido(
            f"La creacion del caso en {volumen}: fallo dentro del paquete instalado: {creado}"
        )
    case_id = creado.get("case_id")
    case_dir = creado.get("case_dir")
    if not case_id or not case_dir:
        raise GateFallido(f"La evidencia de creacion en {volumen}: no trae case_id/case_dir: {creado}")

    reabierto = _ejecutar(
        aumid,
        evidencia_verify,
        {"mode": "verify", "case_id": case_id, "case_dir": case_dir},
        espera_s=120,
    )
    if not reabierto.get("ok"):
        raise GateFallido(
            f"El caso {case_id} en {volumen}: no reaparecio tras cerrar y abrir: {reabierto}"
        )

    return {
        "volumen": f"{volumen}:",
        "padre": str(padre),
        "case_id": case_id,
        "case_dir": case_dir,
        "registry_path": creado.get("registry_path"),
        "health": creado.get("health"),
        "reaparecio": True,
        "resolved_dir": reabierto.get("resolved_dir"),
        "manifest_readable": reabierto.get("manifest_readable"),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--msix", type=Path, required=True)
    ap.add_argument("--volumenes", default="C,D", help="Letras separadas por coma (default C,D).")
    ap.add_argument("--out", type=Path, default=None,
                    help="Por defecto, junto al propio paquete: la evidencia "
                         "viaja con lo que probo.")
    ap.add_argument("--conservar-instalado", action="store_true",
                    help="No desinstala el paquete al terminar.")
    args = ap.parse_args()

    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    nombre_paquete = cfg["identidad_del_store"]["package_identity_name"]
    msix = args.msix.resolve()
    if not msix.is_file():
        raise SystemExit(f"No existe el paquete: {msix}")
    salida = args.out if args.out else msix.parent / "accept-cases-evidence.json"

    volumenes = [v.strip().upper() for v in args.volumenes.split(",") if v.strip()]
    ev: dict = {
        "ejecutado_utc": datetime.now(timezone.utc).isoformat(),
        "msix": str(msix),
        # El sha256, no solo la ruta: el nombre del paquete se reutiliza entre
        # builds y una evidencia que solo guarda la ruta deja de corresponder
        # a nada en cuanto se reempaqueta encima.
        "msix_sha256": _sha256(msix),
        "volumenes": volumenes,
        "resultados": {},
        "estado": "FAIL",
    }

    try:
        print("[1] instalacion")
        previo = paquete_instalado(nombre_paquete)
        if previo:
            print(f"      hay una instalacion previa: {previo['PackageFullName']}; se quita")
            desinstalar(previo["PackageFullName"])
        instalar(msix)
        info = paquete_instalado(nombre_paquete)
        if not info:
            raise GateFallido("Tras Add-AppxPackage el paquete no aparece instalado.")
        ev["resultados"]["instalacion"] = {
            "PackageFullName": info["PackageFullName"],
            "Version": info["Version"],
        }
        aumid = aumid_de(info["PackageFamilyName"], info["PackageFullName"])
        ev["resultados"]["aumid"] = aumid
        print(f"      {info['PackageFullName']}  AUMID={aumid}")

        out_dir = salida.parent
        for volumen in volumenes:
            print(f"[2] caso en {volumen}: (crear -> cerrar -> abrir)")
            r = _evaluar_volumen(aumid, volumen, out_dir)
            ev["resultados"][f"volumen_{volumen}"] = r
            print(f"      {r}")

        ev["estado"] = "PASS"
        print("\nPASS: el registro de casos persiste dentro del MSIX instalado.")
        return 0
    except GateFallido as e:
        ev["error"] = str(e)
        print(f"\nFAIL: {e}", file=sys.stderr)
        return 1
    except Exception as e:  # noqa: BLE001
        ev["error"] = f"{type(e).__name__}: {e}"
        print(f"\nFAIL (inesperado): {ev['error']}", file=sys.stderr)
        return 1
    finally:
        # Limpieza del centinela: nunca debe quedar basura que dispare el
        # autotest en un arranque normal posterior.
        SENTINEL.unlink(missing_ok=True)
        info_final = paquete_instalado(nombre_paquete)
        if info_final and not args.conservar_instalado:
            try:
                desinstalar(info_final["PackageFullName"])
            except GateFallido as e:
                print(f"      (aviso) no se pudo desinstalar: {e}", file=sys.stderr)
        salida.parent.mkdir(parents=True, exist_ok=True)
        salida.write_text(json.dumps(ev, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"evidencia -> {salida}")


if __name__ == "__main__":
    raise SystemExit(main())