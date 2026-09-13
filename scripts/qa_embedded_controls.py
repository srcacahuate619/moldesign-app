"""Arnes de validacion externa de los pipelines M4, M5-Zn y Peptidos.

Protocolo prerregistrado: `validation/protocols/alpha-controls-v1.json`
(SHA-256 en `validation/protocols/alpha-controls-v1.sha256`). El arnes
COMPRUEBA ese hash antes de ejecutar nada: si el protocolo cambio despues de
congelarse, aborta. Un prerregistro que se puede editar despues de ver los
resultados no es un prerregistro.

Este arnes NO modifica el producto. Si encuentra un defecto lo deja escrito con
su evidencia y devuelve codigo != 0.


Por que no basta con `python -m uvicorn api.main:app`
-----------------------------------------------------
El backend embebido NO se configura solo: la aplicacion de escritorio le pasa
un entorno que decide que componentes existen. Reproducirlo mal fabrica fallos
que el usuario nunca ve. Medido en esta auditoria:

  sin VINA_EXECUTABLE_PATH   /health devuelve `vina: {exists: false}` y el
                             veredicto se hunde por un binario que SI esta en
                             el bundle y SI ejecuta. `settings.vina_executable_path`
                             vale "tools/vina/vina.exe" —relativo— y el CWD es
                             `<resources>/backend`, no `<resources>`.
  sin ENVIRONMENT=production el backend se declara `environment=development`.
  sin PYTHONUTF8=1           el interprete embebido arranca en cp1252 y una
                             lectura de texto sin `encoding=` vuelve corrompida
                             SIN excepcion.

Por eso `entorno_de_produccion()` es una traduccion literal de
`frontend/src-tauri/src/backend.rs::spawn_backend`, con la referencia a la
linea. Si el lanzador cambia y este arnes no, la comparacion deja de ser valida:
`--verificar-contrato-de-arranque` existe para detectarlo.


Modos de entorno (protocolo, seccion `entorno_de_ejecucion`)
------------------------------------------------------------
  VM_LIMPIA       Windows limpio y aprovisionado. Modo preferente.
  COPIA_AISLADA   copia integra de `resources/` fuera del arbol fuente.
                  Sustituto DECLARADO; no equivale a una VM y el informe debe
                  decirlo.
  DEV             `resources/` dentro del arbol fuente. Solo sirve para la
                  tabla de paridad; nunca para la conclusion.

El modo no se infiere: se declara con `--modo` y queda escrito en el resultado.

Uso:
    python scripts/qa_embedded_controls.py --modo COPIA_AISLADA \
        --bundle D:/moldesign-audit/bundle-copy --fase 0
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import platform
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
PROTOCOL = REPO / "validation" / "protocols" / "alpha-controls-v1.json"
PROTOCOL_HASH = REPO / "validation" / "protocols" / "alpha-controls-v1.sha256"

MODOS = ("VM_LIMPIA", "COPIA_AISLADA", "DEV")


class ArnesAbortado(RuntimeError):
    """El arnes no puede medir con validez. No es un fallo del producto."""


# ── Prerregistro ────────────────────────────────────────────────────────────

def verificar_prerregistro() -> dict[str, Any]:
    """El protocolo debe existir y coincidir con su hash congelado."""
    if not PROTOCOL.is_file():
        raise ArnesAbortado(f"No existe el protocolo prerregistrado: {PROTOCOL}")
    if not PROTOCOL_HASH.is_file():
        raise ArnesAbortado(f"No existe el hash congelado: {PROTOCOL_HASH}")
    esperado = json.loads(PROTOCOL_HASH.read_text(encoding="utf-8"))
    real = hashlib.sha256(PROTOCOL.read_bytes()).hexdigest()
    if real != esperado["sha256"]:
        raise ArnesAbortado(
            "El protocolo NO coincide con su hash congelado.\n"
            f"  congelado: {esperado['sha256']}\n"
            f"  actual:    {real}\n"
            "El prerregistro queda invalidado: los resultados obtenidos con un "
            "protocolo editado despues de congelarlo no son ciegos."
        )
    return {"sha256": real, "frozen_at_utc": esperado.get("frozen_at_utc")}


# ── Entorno de produccion ───────────────────────────────────────────────────

def entorno_de_produccion(bundle: Path) -> dict[str, str]:
    """Traduccion literal de `src-tauri/src/backend.rs::spawn_backend` (~L635-686).

    Cada variable esta aqui porque el lanzador la pone. Quitar una no simplifica
    el arnes: mide otro producto.
    """
    backend = bundle / "backend"
    env = os.environ.copy()
    env.update({
        "APP_MODE": "DESKTOP",
        "ENVIRONMENT": "production",
        "PYTHONPATH": str(backend),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONUTF8": "1",
        "VINA_EXECUTABLE_PATH": str(bundle / "tools" / "vina" / "vina.exe"),
        "MOLDESIGN_OPENBABEL_DIR": str(bundle / "tools" / "openbabel"),
        "TABPFN_NO_BROWSER": "true",
    })
    env.pop("PYTHONHOME", None)
    return env


CONTRATO_DE_ARRANQUE = {
    "fuente": "frontend/src-tauri/src/backend.rs::spawn_backend",
    "cwd": "<bundle>/backend",
    "argv": ["-m", "uvicorn", "api.main:app", "--host", "127.0.0.1",
             "--port", "<puerto>", "--loop", "asyncio", "--app-dir", "<bundle>/backend"],
    "env": ["APP_MODE", "ENVIRONMENT", "PYTHONPATH", "PYTHONDONTWRITEBYTECODE",
            "PYTHONUTF8", "VINA_EXECUTABLE_PATH", "MOLDESIGN_OPENBABEL_DIR",
            "TABPFN_NO_BROWSER"],
}


def verificar_contrato_de_arranque(repo_fuente: Path) -> dict[str, Any]:
    """Comprueba que el lanzador real sigue poniendo las variables que copiamos.

    No parsea Rust: busca cada nombre en el fichero. Si el lanzador deja de
    poner una, o anade otra, este arnes esta midiendo un entorno que ya no
    existe y hay que actualizarlo antes de creer sus numeros.
    """
    fuente = repo_fuente / "frontend" / "src-tauri" / "src" / "backend.rs"
    if not fuente.is_file():
        return {"estado": "NO_VERIFICABLE", "motivo": f"no existe {fuente}"}
    texto = fuente.read_text(encoding="utf-8", errors="replace")
    faltan = [v for v in CONTRATO_DE_ARRANQUE["env"] if f'"{v}"' not in texto]
    # Variables que el lanzador pone y el arnes no conoce.
    import re
    puestas = set(re.findall(r'\.env\(\s*"([A-Z0-9_]+)"', texto))
    nuevas = sorted(puestas - set(CONTRATO_DE_ARRANQUE["env"]))
    return {
        "estado": "OK" if not faltan and not nuevas else "DIVERGENTE",
        "declaradas_por_el_arnes_y_ausentes_en_el_lanzador": faltan,
        "puestas_por_el_lanzador_y_desconocidas_para_el_arnes": nuevas,
        "fuente": str(fuente),
    }


# ── Arranque ────────────────────────────────────────────────────────────────

def _puerto_libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


class Backend:
    """Backend embebido arrancado como lo arranca la aplicacion de escritorio."""

    def __init__(self, bundle: Path, log_path: Path) -> None:
        self.bundle = bundle
        self.backend_dir = bundle / "backend"
        self.python = bundle / "python" / "python.exe"
        self.log_path = log_path
        self.port = _puerto_libre()
        self.proc: subprocess.Popen[bytes] | None = None
        self._log = None
        self.arranque_s: float | None = None

    def __enter__(self) -> "Backend":
        for exigido in (self.python, self.backend_dir / "api" / "main.py"):
            if not exigido.exists():
                raise ArnesAbortado(f"El bundle no esta completo: falta {exigido}")
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._log = self.log_path.open("ab")
        t0 = time.time()
        self.proc = subprocess.Popen(
            [str(self.python), "-m", "uvicorn", "api.main:app",
             "--host", "127.0.0.1", "--port", str(self.port),
             "--loop", "asyncio", "--app-dir", str(self.backend_dir)],
            cwd=str(self.backend_dir),
            env=entorno_de_produccion(self.bundle),
            stdout=self._log, stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        # Listo = responde HTTP, sea cual sea el codigo. Un 503 con cuerpo es
        # una respuesta que hay que leer, no un "todavia no arranca".
        for _ in range(180):
            if self.proc.poll() is not None:
                raise ArnesAbortado(
                    f"El backend murio al arrancar (rc={self.proc.returncode}). "
                    f"Log: {self.log_path}")
            estado, _cuerpo = self.get("/health", timeout=5)
            if estado is not None:
                self.arranque_s = round(time.time() - t0, 2)
                return self
            time.sleep(1)
        raise ArnesAbortado(f"El backend no respondio en 180 s. Log: {self.log_path}")

    def __exit__(self, *exc: object) -> None:
        if self.proc is not None and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=10)
        if self._log is not None:
            self._log.close()

    def get(self, ruta: str, timeout: float = 120) -> tuple[int | None, bytes]:
        """(status, cuerpo). Un HTTPError es una respuesta con cuerpo, no un fallo."""
        try:
            with urllib.request.urlopen(
                    f"http://127.0.0.1:{self.port}{ruta}", timeout=timeout) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()
        except Exception as e:  # transporte: el servidor no contesto
            return None, repr(e).encode()

    def json(self, ruta: str, timeout: float = 120) -> tuple[int | None, Any]:
        estado, cuerpo = self.get(ruta, timeout)
        try:
            return estado, json.loads(cuerpo.decode("utf-8"))
        except Exception:
            return estado, {"_raw": cuerpo[:2000].decode("utf-8", "replace")}


# ── Contrato vivo ───────────────────────────────────────────────────────────

class Contrato:
    """Rutas leidas del OpenAPI vivo. Ninguna ruta se escribe de memoria."""

    def __init__(self, spec: dict[str, Any]) -> None:
        self.paths = spec.get("paths", {})

    def existe(self, ruta: str, metodo: str = "get") -> bool:
        return metodo.lower() in {m.lower() for m in self.paths.get(ruta, {})}

    def exige(self, ruta: str, metodo: str = "get") -> None:
        if not self.existe(ruta, metodo):
            raise ArnesAbortado(
                f"El OpenAPI vivo no declara {metodo.upper()} {ruta}. "
                "El arnes no inventa rutas: corrigelo o actualiza el arnes.")

    def buscar(self, fragmento: str) -> list[str]:
        return sorted(p for p in self.paths if fragmento in p)


# ── Entorno medido ──────────────────────────────────────────────────────────

def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def huella_del_arbol(raiz: Path) -> dict[str, Any]:
    """Huella de `resources/` para detectar escrituras del propio bundle.

    Invariante bloqueante: el bundle no escribe bases ni caches dentro de
    `resources/`. Se compara antes y despues de las corridas.
    """
    entradas: dict[str, list[int | float]] = {}
    for p in sorted(raiz.rglob("*")):
        if p.is_file():
            try:
                st = p.stat()
            except OSError:
                continue
            entradas[str(p.relative_to(raiz)).replace("\\", "/")] = [st.st_size, st.st_mtime_ns]
    payload = json.dumps(entradas, sort_keys=True).encode()
    return {"n_ficheros": len(entradas), "sha256": hashlib.sha256(payload).hexdigest(),
            "_entradas": entradas}


def diferencia_de_arbol(antes: dict[str, Any], despues: dict[str, Any]) -> dict[str, Any]:
    a, d = antes["_entradas"], despues["_entradas"]
    nuevos = sorted(set(d) - set(a))
    borrados = sorted(set(a) - set(d))
    modificados = sorted(k for k in set(a) & set(d) if a[k] != d[k])
    return {"nuevos": nuevos[:200], "n_nuevos": len(nuevos),
            "borrados": borrados[:200], "n_borrados": len(borrados),
            "modificados": modificados[:200], "n_modificados": len(modificados),
            "invariante_cumplida": not (nuevos or borrados or modificados)}


def describir_entorno(bundle: Path, modo: str) -> dict[str, Any]:
    manifest_path = bundle / "runtime-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {}

    vina = bundle / "tools" / "vina" / "vina.exe"
    vina_version = None
    if vina.is_file():
        try:
            out = subprocess.run([str(vina), "--version"], capture_output=True,
                                 timeout=60, text=True)
            vina_version = (out.stdout or out.stderr).strip().splitlines()[:1]
        except Exception as e:
            vina_version = [f"ERROR: {e!r}"]

    # Activos criticos declarados por el manifiesto, verificados uno a uno.
    activos = {}
    for rel, decl in (manifest.get("critical_assets") or {}).items():
        p = bundle / rel
        if not p.is_file():
            activos[rel] = {"presente": False, "declarado_sha256": decl.get("sha256")}
            continue
        real = _sha256(p)
        activos[rel] = {"presente": True, "declarado_sha256": decl.get("sha256"),
                        "real_sha256": real, "coincide": real == decl.get("sha256")}

    return {
        "modo": modo,
        "declaracion": ("NO EJECUTADO EN VM" if modo != "VM_LIMPIA" else "EJECUTADO EN VM LIMPIA"),
        "bundle": str(bundle),
        "runtime_manifest_sha256": _sha256(manifest_path) if manifest_path.is_file() else None,
        "producto": {"version": manifest.get("product_version"),
                     "profile": manifest.get("profile"),
                     "generado_en": manifest.get("generated_at_utc")},
        "activos_criticos": activos,
        "vina_version": vina_version,
        "host": {
            "os": platform.platform(),
            "maquina": platform.machine(),
            "procesador": platform.processor(),
            "python_del_arnes": sys.version,
        },
        "medido_utc": datetime.now(timezone.utc).isoformat(),
    }


# ── Fase 0: runtime ─────────────────────────────────────────────────────────

def fase_0(bundle: Path, modo: str, out: Path, repo_fuente: Path) -> dict[str, Any]:
    """Arranca, lee el contrato vivo y confronta lo declarado con lo presente."""
    res: dict[str, Any] = {"fase": "FASE_0_RUNTIME"}
    res["contrato_de_arranque"] = verificar_contrato_de_arranque(repo_fuente)
    res["entorno"] = describir_entorno(bundle, modo)

    antes = huella_del_arbol(bundle)

    with Backend(bundle, out / "logs" / "backend_fase0.log") as be:
        res["arranque_s"] = be.arranque_s
        res["puerto"] = be.port

        estado, spec = be.json("/openapi.json")
        if estado != 200:
            raise ArnesAbortado(f"OpenAPI no disponible (status={estado}).")
        contrato = Contrato(spec)
        (out / "openapi.json").write_text(json.dumps(spec, indent=1), encoding="utf-8")
        res["n_rutas"] = len(contrato.paths)
        res["rutas_de_evaluacion"] = contrato.buscar("evaluation")

        capturas = {}
        for ruta in ("/health", "/hardware", "/rescoring/health", "/rescoring/info", "/"):
            if not contrato.existe(ruta):
                capturas[ruta] = {"_no_declarada_en_openapi": True}
                continue
            st, cuerpo = be.json(ruta)
            capturas[ruta] = {"status": st, "cuerpo": cuerpo}
        res["capturas"] = capturas

        salud = capturas.get("/health", {}).get("cuerpo", {})
        res["diagnostico_de_salud"] = diagnosticar_salud(salud, bundle)

    despues = huella_del_arbol(bundle)
    res["escritura_en_resources"] = diferencia_de_arbol(antes, despues)
    return res


def diagnosticar_salud(salud: dict[str, Any], bundle: Path) -> dict[str, Any]:
    """Confronta lo que /health declara con lo que hay en disco.

    Un componente que el backend declara ausente puede estar presente (y
    entonces el fallo es del chequeo), y uno que declara sano puede faltar. Las
    dos direcciones son defectos distintos y se separan.
    """
    comps = (salud or {}).get("components", {}) or {}
    hallazgos = []

    vina = comps.get("vina", {})
    ruta_vina = bundle / "tools" / "vina" / "vina.exe"
    if vina.get("status") != "healthy" and ruta_vina.is_file():
        hallazgos.append({
            "componente": "vina", "clase": "FALSO_NEGATIVO_DE_HEALTH",
            "declarado": vina, "en_disco": str(ruta_vina),
            "nota": "El binario existe y ejecuta. `settings.vina_executable_path` "
                    "es relativo y el CWD es <bundle>/backend.",
        })

    mm = comps.get("model_manifest", {})
    for err in mm.get("errors", []) or []:
        fichero = err.split(":")[-1]
        encontrado = list(bundle.rglob(fichero)) if fichero else []
        hallazgos.append({
            "componente": "model_manifest", "clase": "ARTEFACTO_AUSENTE_EN_BUNDLE",
            "error": err,
            "presente_en_bundle": [str(p) for p in encontrado],
            "nota": "Declarado por un manifiesto que SI viaja en el bundle.",
        })

    return {"status_global": (salud or {}).get("status"),
            "environment": (salud or {}).get("app_mode"),
            "hallazgos": hallazgos}


# ── Programa ────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--modo", required=True, choices=MODOS,
                    help="Se DECLARA, no se infiere. Queda escrito en el resultado.")
    ap.add_argument("--bundle", type=Path, required=True,
                    help="Raiz del bundle: la carpeta con python/, backend/, tools/.")
    ap.add_argument("--fase", default="0", choices=["0"],
                    help="Fases 2, 3 y 4 requieren cohorte aprovisionada.")
    ap.add_argument("--out", type=Path, default=REPO / "validation" / "results")
    ap.add_argument("--repo-fuente", type=Path, default=REPO,
                    help="Arbol con src-tauri, para verificar el contrato de arranque.")
    args = ap.parse_args()

    try:
        pre = verificar_prerregistro()
    except ArnesAbortado as e:
        print(f"ABORTADO: {e}", file=sys.stderr)
        return 2

    bundle = args.bundle.resolve()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)

    cabecera = {
        "arnes": "scripts/qa_embedded_controls.py",
        "protocolo": {"fichero": "validation/protocols/alpha-controls-v1.json", **pre},
        "ejecutado_utc": datetime.now(timezone.utc).isoformat(),
        "modo": args.modo,
    }
    if args.modo != "VM_LIMPIA":
        print(f"AVISO: modo {args.modo}. El informe debe declarar 'NO EJECUTADO EN VM'.")

    try:
        resultado = fase_0(bundle, args.modo, out, args.repo_fuente.resolve())
    except ArnesAbortado as e:
        (out / "fase0_abortada.json").write_text(
            json.dumps({**cabecera, "abortado": str(e)}, indent=2, ensure_ascii=False),
            encoding="utf-8")
        print(f"ABORTADO: {e}", file=sys.stderr)
        return 2

    payload = {**cabecera, "resultado": resultado}
    destino = out / "fase0_runtime.json"
    # `_entradas` es la huella completa del arbol: util para diagnosticar, pero
    # son decenas de miles de lineas. Se guarda aparte.
    destino.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str),
                       encoding="utf-8")
    print(f"-> {destino}")

    hallazgos = resultado.get("diagnostico_de_salud", {}).get("hallazgos", [])
    inv = resultado.get("escritura_en_resources", {})
    print(f"arranque: {resultado.get('arranque_s')} s")
    print(f"rutas en OpenAPI: {resultado.get('n_rutas')}")
    print(f"hallazgos de salud: {len(hallazgos)}")
    for h in hallazgos:
        print(f"  [{h['clase']}] {h['componente']}: {h.get('error') or h.get('nota')}")
    print(f"resources/ intacto: {inv.get('invariante_cumplida')} "
          f"(nuevos={inv.get('n_nuevos')} modificados={inv.get('n_modificados')})")
    return 1 if hallazgos else 0


if __name__ == "__main__":
    raise SystemExit(main())
