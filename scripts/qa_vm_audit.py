"""Auditoría de una instalación de MolDesign en una máquina virtual limpia.

Produce `qa_comprehensive_report.json` y `qa_exec.log`. Sustituye al arnés
ad-hoc que corrió en la VM y que devolvió fallos falsos por cuatro razones
distintas, todas corregidas aquí:

1. **Llamaba a `POST /evaluation/dock`, que no existe.** El flujo canónico es
   `POST /evaluation/preflight` → `POST /evaluation/submit` →
   `GET /evaluation/status/{task_id}`. Para que no vuelva a ocurrir, el arnés
   **no escribe rutas de memoria**: exige que cada una exista en el OpenAPI
   vivo antes de llamarla (`Contrato.exige_rutas`). Una ruta inventada aborta
   la auditoría con `ContratoRoto` en vez de producir un 404 disfrazado de
   fallo del producto.

2. **Mandaba `target` en vez de `target_pdb_id`.** El cuerpo ya no se escribe a
   mano: se deriva del esquema que el propio OpenAPI asocia a cada ruta
   (`Contrato.payload_de`). Un campo que el esquema no declara, o un requerido
   que falta, es un error del arnés y se dice así.

3. **No esperaba al arranque en frío.** En una VM de 3 núcleos con disco
   emulado el backend tarda; el arnés preguntaba una vez y anotaba «caído».
   Ahora hay una fase de readiness explícita, con `/health` y `/targets` en
   **dos medidas separadas** y dos presupuestos configurables. Un timeout real
   se reporta como `TIMEOUT` —nunca como SKIP— y hunde el veredicto.

4. **Contaba como FAIL lo que falta por diseño.** ESMFold sin pesos y los
   motores «Próximamente» son ausencias esperadas. Se clasifican por el campo
   `requiere` que declara el backend, no por una lista escrita aquí; sólo
   `binario_empaquetado` —Vina— es un fallo real si no está.

5. **Levantaba el backend sin declarar el Vina que estaba auditando.** El
   instalador no depende de `PATH`: Rust fija `VINA_EXECUTABLE_PATH` al binario
   empaquetado. El arnés reproduce esa frontera tanto en el árbol fuente como
   en `resources` staged; si el binario no existe, aborta como defecto del
   arnés en vez de publicar que una build sana no trae Vina.

Por qué `/evaluation/submit` y no `/evaluation/evaluate`: los dos ejecutan el
mismo pipeline y pasan por las mismas puertas (`_enforce_submission_gates`),
pero `evaluate` es un `StreamingResponse` de SSE que sólo emite `task_id[:8]`
—ocho caracteres, inservibles para `/evaluation/status/{task_id}`—. Sin el
`task_id` completo no se puede correlacionar la evidencia que pide el punto 6,
ni sobrevivir a una VM lenta sin mantener un stream abierto media hora.

Este arnés NO modifica el producto. Si encuentra un defecto real, lo deja
escrito con su evidencia y devuelve 1.

Uso:
    # contra el backend que ya levantó la aplicación de escritorio
    python scripts/qa_vm_audit.py --base-url http://127.0.0.1:53017

    # levantando el backend desde el árbol (repo o `resources` staged)
    python scripts/qa_vm_audit.py --out-dir tmp/qa-vm-manual
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

ROOT = Path(__file__).resolve().parent.parent

SCHEMA_VERSION = 1

# Estados de una fase. `EXPECTED` y `SKIP` no hunden el veredicto; `FAIL` y
# `TIMEOUT` sí. Están separados a propósito: un timeout que se anota como SKIP
# es exactamente el fallo que esta auditoría existe para no repetir.
PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP"
EXPECTED = "EXPECTED"
TIMEOUT = "TIMEOUT"

ESTADOS_QUE_HUNDEN = (FAIL, TIMEOUT)

# Ligando de referencia: pequeño pero por encima del umbral del validador.
SMILES_POR_DEFECTO = "CC(=O)OC1=CC=CC=C1C(=O)O"
TARGET_POR_DEFECTO = "7E2Y"

# Las rutas que este arnés usa. Se comprueban contra el OpenAPI vivo ANTES de
# llamar a ninguna. `/evaluation/dock` no está aquí porque no existe.
RUTAS_REQUERIDAS: tuple[tuple[str, str], ...] = (
    ("/health", "get"),
    ("/targets/", "get"),
    ("/evaluation/engines", "get"),
    ("/evaluation/preflight", "post"),
    ("/evaluation/submit", "post"),
    ("/evaluation/status/{task_id}", "get"),
)

# Cómo se lee el campo `requiere` del inventario de motores. Sólo lo que el
# instalador empaqueta es un fallo si no está.
REQUISITOS_EMPAQUETADOS = frozenset({"binario_empaquetado"})
REQUISITOS_AUSENCIA_ESPERADA = frozenset({
    "binario_externo",        # QuickVina 2: no viaja en esta versión
    "servicio_externo",       # los «Próximamente»: viven en otro proceso
    "descarga_bajo_demanda",  # ESMFold y compañía: pesos que se bajan aparte
})

ESTADOS_TERMINALES = frozenset({"SUCCESS", "FAILURE", "REVOKED"})

# Las fases posteriores a readiness, para poder marcarlas SKIP de una vez si
# el backend nunca llegó a estar sano.
FASES_POSTERIORES: tuple[tuple[str, str], ...] = (
    ("readiness.targets", "GET /targets/"),
    ("contrato", "Rutas del contrato"),
    ("motores", "Inventario de motores"),
    ("evaluation.preflight", "POST /evaluation/preflight"),
    ("evaluation.submit", "POST /evaluation/submit"),
    ("evaluation.poll", "GET /evaluation/status/{task_id}"),
)


class ContratoRoto(RuntimeError):
    """El arnés pidió algo que el OpenAPI no declara. Es un bug del arnés."""


class ArnesAbortado(RuntimeError):
    """Condición que impide seguir auditando (no es un fallo del producto)."""


# ── Bitácora ────────────────────────────────────────────────────────────────

class Bitacora:
    """`qa_exec.log`: una línea por hecho, con marca de tiempo y a stdout."""

    def __init__(self, destino: Path) -> None:
        destino.parent.mkdir(parents=True, exist_ok=True)
        self._handle = destino.open("w", encoding="utf-8", newline="\n")
        self.destino = destino

    def linea(self, mensaje: str) -> None:
        marca = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        texto = f"{marca} {mensaje}"
        self._handle.write(texto + "\n")
        self._handle.flush()
        print(texto, flush=True)

    def cerrar(self) -> None:
        if not self._handle.closed:
            self._handle.close()


# ── HTTP ────────────────────────────────────────────────────────────────────

class Respuesta:
    """Una respuesta HTTP que nunca se pierde: el cuerpo se conserva siempre.

    `urllib` lanza en 4xx/5xx y el cuerpo se va con la excepción si nadie lo
    lee. El arnés anterior perdía justamente ahí el detalle del 422.
    """

    def __init__(
        self,
        *,
        status: int | None,
        cuerpo: bytes = b"",
        cabeceras: dict[str, str] | None = None,
        error: str | None = None,
        elapsed_s: float = 0.0,
    ) -> None:
        self.status = status
        self.cuerpo = cuerpo
        self.cabeceras = cabeceras or {}
        self.error = error
        self.elapsed_s = elapsed_s

    @property
    def texto(self) -> str:
        return self.cuerpo.decode("utf-8", errors="replace")

    def json(self) -> Any:
        return json.loads(self.texto)

    def como_evidencia(self, limite: int = 8000) -> dict[str, Any]:
        return {
            "status": self.status,
            "elapsed_s": round(self.elapsed_s, 3),
            "content_type": self.cabeceras.get("Content-Type"),
            "body": self.texto[:limite],
            "body_truncated": len(self.texto) > limite,
            "transport_error": self.error,
        }


def peticion(
    base: str,
    metodo: str,
    ruta: str,
    *,
    cuerpo: dict[str, Any] | None = None,
    token: str | None = None,
    timeout: float = 120.0,
) -> Respuesta:
    datos = None if cuerpo is None else json.dumps(cuerpo).encode("utf-8")
    cabeceras = {"Accept": "application/json"}
    if cuerpo is not None:
        cabeceras["Content-Type"] = "application/json"
    if token:
        cabeceras["Authorization"] = f"Bearer {token}"
    solicitud = urllib.request.Request(
        base.rstrip("/") + ruta, data=datos, headers=cabeceras, method=metodo
    )
    inicio = time.monotonic()
    try:
        with urllib.request.urlopen(solicitud, timeout=timeout) as respuesta:
            return Respuesta(
                status=int(respuesta.status),
                cuerpo=respuesta.read(),
                cabeceras=dict(respuesta.headers.items()),
                elapsed_s=time.monotonic() - inicio,
            )
    except urllib.error.HTTPError as exc:
        return Respuesta(
            status=int(exc.code),
            cuerpo=exc.read(),
            cabeceras=dict(exc.headers.items()) if exc.headers else {},
            elapsed_s=time.monotonic() - inicio,
        )
    except Exception as exc:  # URLError, timeout de socket, conexión rechazada
        return Respuesta(
            status=None,
            error=f"{type(exc).__name__}: {exc}",
            elapsed_s=time.monotonic() - inicio,
        )


def peticion_como_evidencia(
    metodo: str, ruta: str, cuerpo: dict[str, Any] | None
) -> dict[str, Any]:
    return {"method": metodo.upper(), "path": ruta, "body": cuerpo}


# ── El contrato: el OpenAPI manda ───────────────────────────────────────────

class Contrato:
    """El OpenAPI vivo del backend auditado. Nadie escribe rutas de memoria."""

    def __init__(self, spec: dict[str, Any], origen: str) -> None:
        self.spec = spec
        self.origen = origen

    @classmethod
    def cargar(
        cls, base: str, respaldo: Path | None, *, timeout: float = 60.0
    ) -> "Contrato":
        respuesta = peticion(base, "GET", "/openapi.json", timeout=timeout)
        if respuesta.status == 200:
            return cls(respuesta.json(), f"{base}/openapi.json")
        if respaldo is not None and respaldo.is_file():
            return cls(
                json.loads(respaldo.read_text(encoding="utf-8")), str(respaldo)
            )
        raise ArnesAbortado(
            "No se pudo leer el contrato: /openapi.json respondió "
            f"{respuesta.status or respuesta.error} y no hay respaldo legible."
        )

    def rutas_ausentes(self, rutas: Iterable[tuple[str, str]]) -> list[str]:
        paths = self.spec.get("paths", {})
        ausentes = []
        for ruta, metodo in rutas:
            declarados = {m.lower() for m in paths.get(ruta, {})}
            if metodo.lower() not in declarados:
                ausentes.append(f"{metodo.upper()} {ruta}")
        return ausentes

    def exige_rutas(self, rutas: Iterable[tuple[str, str]]) -> None:
        ausentes = self.rutas_ausentes(rutas)
        if ausentes:
            raise ContratoRoto(
                "El arnés pide rutas que el contrato no declara: "
                + ", ".join(ausentes)
                + f" (contrato: {self.origen})."
            )

    def _resolver(self, ref: str) -> dict[str, Any]:
        if not ref.startswith("#/"):
            raise ContratoRoto(f"Referencia no local en el contrato: {ref}")
        nodo: Any = self.spec
        for parte in ref[2:].split("/"):
            if not isinstance(nodo, dict) or parte not in nodo:
                raise ContratoRoto(f"El contrato no resuelve {ref}.")
            nodo = nodo[parte]
        return nodo

    def esquema_del_cuerpo(self, ruta: str, metodo: str) -> tuple[str, dict[str, Any]]:
        try:
            operacion = self.spec["paths"][ruta][metodo.lower()]
            esquema = operacion["requestBody"]["content"]["application/json"]["schema"]
        except KeyError as exc:
            raise ContratoRoto(
                f"{metodo.upper()} {ruta} no declara cuerpo JSON en el contrato "
                f"(falta {exc})."
            ) from exc
        ref = esquema.get("$ref")
        if ref is None:
            return (ruta, esquema)
        return (ref.rsplit("/", 1)[-1], self._resolver(ref))

    def payload_de(
        self, ruta: str, metodo: str, valores: dict[str, Any]
    ) -> tuple[str, dict[str, Any]]:
        """Deriva el cuerpo desde el esquema, en vez de escribirlo a mano.

        Aquí es donde `target` habría muerto: no es una propiedad de
        `PreflightRequest`, así que el arnés falla nombrándolo en vez de
        mandar un 422 y culpar al backend.
        """
        nombre, esquema = self.esquema_del_cuerpo(ruta, metodo)
        propiedades = esquema.get("properties", {})
        desconocidos = sorted(set(valores) - set(propiedades))
        if desconocidos:
            raise ContratoRoto(
                f"{metodo.upper()} {ruta}: el esquema {nombre} no declara "
                f"{desconocidos}. Propiedades válidas: {sorted(propiedades)}."
            )
        faltan = [c for c in esquema.get("required", []) if c not in valores]
        if faltan:
            raise ContratoRoto(
                f"{metodo.upper()} {ruta}: el esquema {nombre} exige {faltan} "
                "y el arnés no los envía."
            )
        # Un `None` en un campo opcional no es lo mismo que no enviarlo: el
        # backend distingue «sin override» de «override nulo» al recalcular la
        # huella del preflight.
        return nombre, {k: v for k, v in valores.items() if v is not None}


# ── El log del backend ──────────────────────────────────────────────────────

def directorios_de_log(explicito: Path | None) -> list[Path]:
    """Dónde puede estar el log del backend, en orden de preferencia.

    `backend.rs` escribe en `MOLDESIGN_LOG_DIR`, en `<repo>/logs` cuando corre
    sobre el árbol, y en `%TEMP%/MolDesign/logs` cuando está instalado.
    """
    candidatos: list[Path] = []
    if explicito is not None:
        candidatos.append(explicito)
    desde_entorno = os.environ.get("MOLDESIGN_LOG_DIR")
    if desde_entorno:
        candidatos.append(Path(desde_entorno))
    candidatos.append(ROOT / "logs")
    candidatos.append(Path(tempfile.gettempdir()) / "MolDesign" / "logs")
    return [c for c in candidatos if c.is_dir()]


def log_del_backend(directorios: Sequence[Path]) -> Path | None:
    """El archivo vivo. `backend.latest.log` guarda el NOMBRE del actual."""
    for directorio in directorios:
        puntero = directorio / "backend.latest.log"
        if puntero.is_file():
            try:
                nombre = puntero.read_text(encoding="utf-8", errors="replace").strip()
            except OSError:
                nombre = ""
            if nombre:
                candidato = directorio / nombre
                if candidato.is_file():
                    return candidato
        registros = sorted(
            directorio.glob("backend_*.log"), key=lambda p: p.stat().st_mtime
        )
        if registros:
            return registros[-1]
    return None


def cola_de_log(ruta: Path | None, lineas: int = 200) -> dict[str, Any]:
    if ruta is None:
        return {"path": None, "tail": [], "note": "no se encontró log del backend"}
    try:
        contenido = ruta.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        return {"path": str(ruta), "tail": [], "note": f"ilegible: {exc}"}
    return {
        "path": str(ruta),
        "lines_total": len(contenido),
        "tail": contenido[-lineas:],
    }


# ── La auditoría ────────────────────────────────────────────────────────────

class Auditoria:
    def __init__(self, bitacora: Bitacora, salida: Path) -> None:
        self.bitacora = bitacora
        self.salida = salida
        self.fases: list[dict[str, Any]] = []

    def anota(
        self,
        identificador: str,
        titulo: str,
        estado: str,
        *,
        detalle: dict[str, Any] | None = None,
        evidencia: dict[str, Any] | None = None,
        elapsed_s: float | None = None,
        timeout_s: float | None = None,
    ) -> dict[str, Any]:
        fase: dict[str, Any] = {
            "id": identificador,
            "titulo": titulo,
            "estado": estado,
            "elapsed_s": None if elapsed_s is None else round(elapsed_s, 3),
            "timeout_s": timeout_s,
            "detalle": detalle or {},
        }
        if evidencia:
            fase["evidencia"] = evidencia
        self.fases.append(fase)
        sufijo = "" if elapsed_s is None else f" ({elapsed_s:.1f} s)"
        self.bitacora.linea(f"[{estado:8}] {identificador}: {titulo}{sufijo}")
        return fase

    def fase(self, identificador: str) -> dict[str, Any] | None:
        for registro in self.fases:
            if registro["id"] == identificador:
                return registro
        return None

    @property
    def hundido(self) -> bool:
        return any(f["estado"] in ESTADOS_QUE_HUNDEN for f in self.fases)

    def resumen(self) -> dict[str, Any]:
        cuenta: dict[str, int] = {}
        for registro in self.fases:
            cuenta[registro["estado"]] = cuenta.get(registro["estado"], 0) + 1
        return {"por_estado": cuenta, "veredicto": FAIL if self.hundido else PASS}


def esperar_disponible(
    base: str,
    ruta: str,
    *,
    timeout_s: float,
    request_timeout_s: float,
    token: str | None,
    intervalo_s: float = 1.0,
    proceso: "subprocess.Popen[bytes] | None" = None,
) -> dict[str, Any]:
    """Sondea hasta un 200 o hasta agotar el presupuesto.

    Devuelve la medida completa: cuánto tardó, cuántos intentos y cuál fue la
    última respuesta. Nada de esto se redondea a un booleano — un `/health` que
    contesta 503 durante diez minutos no es «el backend no arrancó», y hay que
    poder leer la diferencia en el informe.
    """
    inicio = time.monotonic()
    limite = inicio + timeout_s
    intentos = 0
    ultima: Respuesta | None = None
    vistos: dict[str, int] = {}
    while True:
        if proceso is not None and proceso.poll() is not None:
            return {
                "listo": False,
                "motivo": "proceso_muerto",
                "exit_code": proceso.returncode,
                "attempts": intentos,
                "elapsed_s": time.monotonic() - inicio,
                "status_histogram": vistos,
                "ultima": ultima.como_evidencia() if ultima else None,
                "respuesta": ultima,
            }
        intentos += 1
        ultima = peticion(base, "GET", ruta, token=token, timeout=request_timeout_s)
        if ultima.status is not None:
            clave = str(ultima.status)
        else:
            clave = (ultima.error or "sin-respuesta").split(":")[0]
        vistos[clave] = vistos.get(clave, 0) + 1
        if ultima.status == 200:
            return {
                "listo": True,
                "attempts": intentos,
                "elapsed_s": time.monotonic() - inicio,
                "status_histogram": vistos,
                "ultima": ultima.como_evidencia(),
                # El objeto entero, sin truncar: quien llame puede necesitar
                # leer el cuerpo completo (el catálogo pasa de 200 KB) y la
                # evidencia se recorta a propósito para que quepa en el informe.
                "respuesta": ultima,
            }
        if time.monotonic() >= limite:
            return {
                "listo": False,
                "motivo": "timeout",
                "attempts": intentos,
                "elapsed_s": time.monotonic() - inicio,
                "status_histogram": vistos,
                "ultima": ultima.como_evidencia(),
                "respuesta": ultima,
            }
        time.sleep(intervalo_s)


def clasificar_motor(entrada: dict[str, Any]) -> tuple[str, str]:
    """(estado, motivo) de un motor del inventario.

    La regla se lee del campo `requiere`, que lo declara el backend. No hay
    lista de nombres aquí: si mañana ESMFold se empaquetara, su ausencia
    pasaría a ser un fallo sin tocar este arnés.
    """
    identificador = entrada.get("id", "?")
    requiere = entrada.get("requiere")
    disponible = bool(entrada.get("disponible"))
    if disponible:
        return PASS, f"{identificador}: disponible ({entrada.get('estado')})."
    if requiere in REQUISITOS_EMPAQUETADOS:
        return FAIL, (
            f"{identificador}: el instalador lo empaqueta ({requiere}) y no está "
            f"disponible. estado={entrada.get('estado')} "
            f"motivo={entrada.get('motivo')}"
        )
    if requiere in REQUISITOS_AUSENCIA_ESPERADA:
        return EXPECTED, (
            f"{identificador}: ausencia esperada ({requiere}, "
            f"estado={entrada.get('estado')})."
        )
    # Un `requiere` que no se sabe leer NO se excusa: la clasificación no puede
    # convertirse en una amnistía general.
    return FAIL, (
        f"{identificador}: `requiere`={requiere!r} no es un requisito conocido; "
        "el arnés no puede decidir si su ausencia es esperada."
    )


# ── Arranque del backend (modo no-attach) ───────────────────────────────────

def _puerto_libre() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _arbol_servido() -> tuple[Path, Path, Path]:
    """(árbol, backend, python) — el repositorio o el runtime staged."""
    staged = ROOT / "frontend" / "src-tauri" / "resources"
    if os.environ.get("MOLDESIGN_GATE_BUNDLE") == "1":
        if not (staged / "backend" / "api" / "main.py").is_file():
            raise ArnesAbortado(
                f"MOLDESIGN_GATE_BUNDLE=1 pero no hay runtime staged en {staged}."
            )
        return staged, staged / "backend", staged / "python" / "python.exe"
    return ROOT, ROOT / "backend", ROOT / "python-embed" / "python.exe"


def entorno_backend(arbol: Path, backend: Path) -> dict[str, str]:
    """Entorno mínimo que el supervisor de escritorio entrega al backend."""
    vina = arbol / "tools" / "vina" / "vina.exe"
    if not vina.is_file():
        raise ArnesAbortado(
            f"El arnés no puede declarar Vina: no existe el binario esperado en {vina}."
        )
    entorno = os.environ.copy()
    entorno.update({
        "PYTHONPATH": str(backend),
        "VINA_EXECUTABLE_PATH": str(vina),
        # Doc 73 §1: sin PYTHONUTF8 el intérprete embebido arranca en cp1252 y
        # una lectura de texto sin `encoding=` vuelve corrompida SIN excepción.
        # Un arnés que no lo ponga mide un entorno que ningún usuario tiene.
        "PYTHONUTF8": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
    })
    return entorno


def arrancar_backend(log_path: Path, puerto: int) -> tuple["subprocess.Popen[bytes]", Any]:
    arbol, backend, python = _arbol_servido()
    if not python.is_file():
        raise ArnesAbortado(f"No existe el intérprete del runtime: {python}")
    entorno = entorno_backend(arbol, backend)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handle = log_path.open("ab")
    proceso = subprocess.Popen(
        [
            str(python), "-m", "uvicorn", "api.main:app",
            "--host", "127.0.0.1", "--port", str(puerto),
            "--app-dir", str(backend),
        ],
        cwd=str(backend),
        env=entorno,
        stdout=handle,
        stderr=subprocess.STDOUT,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    return proceso, handle


def parar_backend(proceso: "subprocess.Popen[bytes] | None", handle: Any) -> None:
    if proceso is not None and proceso.poll() is None:
        proceso.terminate()
        try:
            proceso.wait(timeout=20)
        except subprocess.TimeoutExpired:
            proceso.kill()
            proceso.wait(timeout=10)
    if handle is not None:
        handle.close()


# ── Programa ────────────────────────────────────────────────────────────────

def _numero_de_entorno(nombre: str, defecto: float) -> float:
    valor = os.environ.get(nombre)
    if not valor:
        return defecto
    try:
        return float(valor)
    except ValueError:
        return defecto


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Auditoría de MolDesign en una VM limpia.",
    )
    parser.add_argument(
        "--base-url",
        help="Backend ya en marcha. Sin esto, el arnés levanta uno del árbol.",
    )
    parser.add_argument("--out-dir", type=Path, help="Directorio de evidencia.")
    parser.add_argument("--report", type=Path, help="Ruta de qa_comprehensive_report.json")
    parser.add_argument("--log", type=Path, help="Ruta de qa_exec.log")
    parser.add_argument("--token", help="Bearer opcional.")
    parser.add_argument("--smiles", default=SMILES_POR_DEFECTO)
    parser.add_argument("--target-pdb-id", default=TARGET_POR_DEFECTO)
    parser.add_argument("--chain", default=None)
    parser.add_argument(
        "--cold-start-timeout",
        type=float,
        default=_numero_de_entorno("MOLDESIGN_QA_COLD_START_TIMEOUT_S", 600.0),
        help=(
            "Presupuesto para que /health conteste 200. En una VM de 3 núcleos "
            "con disco emulado el arranque en frío es lento; medirlo con el "
            "presupuesto de una máquina de desarrollo produce fallos falsos."
        ),
    )
    parser.add_argument(
        "--targets-timeout",
        type=float,
        default=_numero_de_entorno("MOLDESIGN_QA_TARGETS_TIMEOUT_S", 300.0),
        help=(
            "Presupuesto propio para /targets, que se mide APARTE de /health: "
            "la primera llamada siembra el catálogo y es la primera consulta "
            "cara del proceso."
        ),
    )
    parser.add_argument(
        "--eval-timeout",
        type=float,
        default=_numero_de_entorno("MOLDESIGN_QA_EVAL_TIMEOUT_S", 1800.0),
    )
    parser.add_argument("--request-timeout", type=float, default=120.0)
    parser.add_argument("--poll-interval", type=float, default=2.0)
    parser.add_argument("--readiness-interval", type=float, default=1.0)
    parser.add_argument(
        "--backend-log-dir", type=Path, help="Dónde viven los backend_*.log."
    )
    parser.add_argument(
        "--openapi-fallback",
        type=Path,
        default=ROOT / "docs" / "api" / "openapi-current.json",
        help="Contrato de respaldo si el backend no sirve /openapi.json.",
    )
    parser.add_argument(
        "--skip-evaluation",
        action="store_true",
        help="Sólo readiness, contrato, motores y preflight.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Sobrescribir un informe anterior en el mismo --out-dir.",
    )
    return parser


class _Contexto:
    """Lo que `_cerrar` necesita saber; evita pasar ocho argumentos sueltos."""

    def __init__(self, args: argparse.Namespace, reporte: Path) -> None:
        self.args = args
        self.reporte = reporte
        self.modo = "?"
        self.base = "?"
        self.inicio = time.monotonic()
        self.aborto: str | None = None


def _cerrar(
    auditoria: Auditoria,
    ctx: _Contexto,
    *,
    codigo_forzado: int | None = None,
) -> int:
    resumen = auditoria.resumen()
    reporte = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "harness": "scripts/qa_vm_audit.py",
        "modo": ctx.modo,
        "base_url": ctx.base,
        "elapsed_total_s": round(time.monotonic() - ctx.inicio, 3),
        "parametros": {
            "smiles": ctx.args.smiles,
            "target_pdb_id": ctx.args.target_pdb_id,
            "cold_start_timeout_s": ctx.args.cold_start_timeout,
            "targets_timeout_s": ctx.args.targets_timeout,
            "eval_timeout_s": ctx.args.eval_timeout,
            "request_timeout_s": ctx.args.request_timeout,
            "skip_evaluation": ctx.args.skip_evaluation,
        },
        "aborto": ctx.aborto,
        "resumen": resumen,
        "fases": auditoria.fases,
    }
    ctx.reporte.parent.mkdir(parents=True, exist_ok=True)
    ctx.reporte.write_text(
        json.dumps(reporte, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    auditoria.bitacora.linea(
        f"VEREDICTO {resumen['veredicto']} · {resumen['por_estado']} · "
        f"reporte={ctx.reporte}"
    )
    if codigo_forzado is not None:
        return codigo_forzado
    return 1 if auditoria.hundido else 0


def ejecutar(args: argparse.Namespace) -> int:
    marca = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    # Un directorio por corrida, jamás reutilizado: reusar el directorio de
    # salida ya destruyó 102 resultados en este proyecto. Con `--out-dir`
    # explícito el arnés se niega a pisar un informe anterior salvo que se lo
    # pidan con `--force`; una auditoría que borra la auditoría de ayer es la
    # misma clase de error con otro sombrero.
    salida = args.out_dir or (ROOT / "tmp" / f"qa-vm-{marca}")
    reporte_previo = args.report or (salida / "qa_comprehensive_report.json")
    if reporte_previo.exists() and not args.force:
        raise SystemExit(
            f"Ya hay un informe en {reporte_previo}. Elige otro --out-dir "
            "(lo normal) o pasa --force si de verdad quieres sobrescribirlo."
        )
    salida.mkdir(parents=True, exist_ok=True)
    ctx = _Contexto(args, reporte_previo)
    bitacora = Bitacora(args.log or (salida / "qa_exec.log"))
    auditoria = Auditoria(bitacora, salida)

    proceso: "subprocess.Popen[bytes] | None" = None
    handle: Any = None
    log_propio: Path | None = None

    try:
        if args.base_url:
            ctx.base = args.base_url.rstrip("/")
            ctx.modo = "attach"
            bitacora.linea(f"Auditando un backend ya en marcha: {ctx.base}")
        else:
            ctx.modo = "spawn"
            puerto = _puerto_libre()
            ctx.base = f"http://127.0.0.1:{puerto}"
            log_propio = salida / f"backend_{marca}.log"
            proceso, handle = arrancar_backend(log_propio, puerto)
            bitacora.linea(
                f"Backend arrancado por el arnés en {ctx.base} "
                f"(pid={proceso.pid}), log={log_propio}"
            )

        directorios = directorios_de_log(args.backend_log_dir)

        def evidencia_backend() -> dict[str, Any]:
            if log_propio is not None:
                return cola_de_log(log_propio)
            return cola_de_log(log_del_backend(directorios))

        # ── Fase 1: readiness, en dos medidas separadas ──────────────────
        salud = esperar_disponible(
            ctx.base, "/health",
            timeout_s=args.cold_start_timeout,
            request_timeout_s=args.request_timeout,
            token=args.token,
            intervalo_s=args.readiness_interval,
            proceso=proceso,
        )
        if not salud["listo"]:
            estado = TIMEOUT if salud.get("motivo") == "timeout" else FAIL
            auditoria.anota(
                "readiness.health",
                "GET /health nunca contestó 200",
                estado,
                detalle={
                    "motivo": salud.get("motivo"),
                    "attempts": salud["attempts"],
                    "status_histogram": salud["status_histogram"],
                    "exit_code": salud.get("exit_code"),
                },
                evidencia={
                    "request": peticion_como_evidencia("GET", "/health", None),
                    "response": salud.get("ultima"),
                    "task_id": None,
                    "backend_log": evidencia_backend(),
                },
                elapsed_s=salud["elapsed_s"],
                timeout_s=args.cold_start_timeout,
            )
            for identificador, titulo in FASES_POSTERIORES:
                auditoria.anota(
                    identificador, f"{titulo} — no se intentó", SKIP,
                    detalle={"motivo": "readiness.health no pasó"},
                )
            return _cerrar(auditoria, ctx)

        auditoria.anota(
            "readiness.health", "GET /health contesta 200", PASS,
            detalle={
                "attempts": salud["attempts"],
                "status_histogram": salud["status_histogram"],
            },
            elapsed_s=salud["elapsed_s"],
            timeout_s=args.cold_start_timeout,
        )

        objetivos = esperar_disponible(
            ctx.base, "/targets/",
            timeout_s=args.targets_timeout,
            request_timeout_s=args.request_timeout,
            token=args.token,
            intervalo_s=args.readiness_interval,
            proceso=proceso,
        )
        if objetivos["listo"]:
            try:
                catalogo = objetivos["respuesta"].json()
                visibles = len(catalogo) if isinstance(catalogo, list) else None
            except (ValueError, AttributeError):
                visibles = None
            auditoria.anota(
                "readiness.targets", "GET /targets/ contesta 200", PASS,
                detalle={
                    "attempts": objetivos["attempts"],
                    "status_histogram": objetivos["status_histogram"],
                    "targets_visibles": visibles,
                },
                elapsed_s=objetivos["elapsed_s"],
                timeout_s=args.targets_timeout,
            )
        else:
            estado = TIMEOUT if objetivos.get("motivo") == "timeout" else FAIL
            auditoria.anota(
                "readiness.targets", "GET /targets/ nunca contestó 200", estado,
                detalle={
                    "motivo": objetivos.get("motivo"),
                    "attempts": objetivos["attempts"],
                    "status_histogram": objetivos["status_histogram"],
                },
                evidencia={
                    "request": peticion_como_evidencia("GET", "/targets/", None),
                    "response": objetivos.get("ultima"),
                    "task_id": None,
                    "backend_log": evidencia_backend(),
                },
                elapsed_s=objetivos["elapsed_s"],
                timeout_s=args.targets_timeout,
            )

        # ── Fase 2: el contrato ──────────────────────────────────────────
        contrato = Contrato.cargar(
            ctx.base, args.openapi_fallback, timeout=args.request_timeout
        )
        ausentes = contrato.rutas_ausentes(RUTAS_REQUERIDAS)
        if ausentes:
            auditoria.anota(
                "contrato", "El contrato no declara las rutas que el arnés usa",
                FAIL,
                detalle={"origen": contrato.origen, "rutas_ausentes": ausentes},
                evidencia={"backend_log": evidencia_backend()},
            )
            raise ContratoRoto("Rutas ausentes en el contrato: " + ", ".join(ausentes))
        auditoria.anota(
            "contrato", "Las rutas del flujo canónico existen en el contrato", PASS,
            detalle={
                "origen": contrato.origen,
                "rutas": [f"{m.upper()} {r}" for r, m in RUTAS_REQUERIDAS],
            },
        )

        # ── Fase 3: motores ──────────────────────────────────────────────
        respuesta = peticion(
            ctx.base, "GET", "/evaluation/engines",
            token=args.token, timeout=args.request_timeout,
        )
        if respuesta.status != 200:
            auditoria.anota(
                "motores", "GET /evaluation/engines no contestó 200", FAIL,
                detalle={"status": respuesta.status},
                evidencia={
                    "request": peticion_como_evidencia(
                        "GET", "/evaluation/engines", None
                    ),
                    "response": respuesta.como_evidencia(),
                    "task_id": None,
                    "backend_log": evidencia_backend(),
                },
                elapsed_s=respuesta.elapsed_s,
            )
        else:
            inventario = respuesta.json()
            entradas = [
                e
                for familia in ("docking", "peptido")
                for e in inventario.get(familia, [])
            ]
            clasificado = []
            for entrada in entradas:
                estado, motivo = clasificar_motor(entrada)
                clasificado.append({
                    "id": entrada.get("id"),
                    "familia": entrada.get("familia"),
                    "requiere": entrada.get("requiere"),
                    "estado_backend": entrada.get("estado"),
                    "disponible": entrada.get("disponible"),
                    "clasificacion": estado,
                    "motivo": motivo,
                })
                auditoria.anota(
                    f"motores.{entrada.get('id')}", motivo, estado,
                    detalle={
                        "requiere": entrada.get("requiere"),
                        "estado_backend": entrada.get("estado"),
                        "disponible": entrada.get("disponible"),
                    },
                )
            (salida / "motores.json").write_text(
                json.dumps(clasificado, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            auditoria.anota(
                "motores", "Inventario de motores clasificado por `requiere`", PASS,
                detalle={
                    "total": len(clasificado),
                    "ausencias_esperadas": sum(
                        1 for c in clasificado if c["clasificacion"] == EXPECTED
                    ),
                },
                elapsed_s=respuesta.elapsed_s,
            )

        # ── Fase 4: preflight, el flujo canónico ─────────────────────────
        _, cuerpo_preflight = contrato.payload_de(
            "/evaluation/preflight", "post",
            {
                "smiles": args.smiles,
                "target_pdb_id": args.target_pdb_id,
                "chain": args.chain,
                "docking_engine": "vina",
            },
        )
        respuesta = peticion(
            ctx.base, "POST", "/evaluation/preflight",
            cuerpo=cuerpo_preflight, token=args.token, timeout=args.request_timeout,
        )
        evidencia_preflight = {
            "request": peticion_como_evidencia(
                "POST", "/evaluation/preflight", cuerpo_preflight
            ),
            "response": respuesta.como_evidencia(),
            "task_id": None,
            "backend_log": evidencia_backend(),
        }
        if respuesta.status != 200:
            auditoria.anota(
                "evaluation.preflight",
                f"POST /evaluation/preflight devolvió {respuesta.status}", FAIL,
                detalle={"status": respuesta.status},
                evidencia=evidencia_preflight,
                elapsed_s=respuesta.elapsed_s,
            )
            for identificador, titulo in (
                ("evaluation.submit", "POST /evaluation/submit"),
                ("evaluation.poll", "GET /evaluation/status/{task_id}"),
            ):
                auditoria.anota(
                    identificador, f"{titulo} — no se intentó", SKIP,
                    detalle={"motivo": "el preflight no dio una huella"},
                )
            return _cerrar(auditoria, ctx)

        informe = respuesta.json()
        (salida / "preflight.json").write_text(
            json.dumps(informe, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        bloqueantes = informe.get("technical_blockers") or []
        huella = informe.get("input_fingerprint")
        if bloqueantes:
            auditoria.anota(
                "evaluation.preflight", "El preflight declara bloqueantes técnicos",
                FAIL,
                detalle={
                    "technical_blockers": bloqueantes,
                    "warnings": informe.get("warnings"),
                    "not_evaluated": informe.get("not_evaluated"),
                },
                evidencia=evidencia_preflight,
                elapsed_s=respuesta.elapsed_s,
            )
            for identificador, titulo in (
                ("evaluation.submit", "POST /evaluation/submit"),
                ("evaluation.poll", "GET /evaluation/status/{task_id}"),
            ):
                auditoria.anota(
                    identificador, f"{titulo} — no se intentó", SKIP,
                    detalle={"motivo": "el preflight bloquea la corrida"},
                )
            return _cerrar(auditoria, ctx)

        auditoria.anota(
            "evaluation.preflight", "POST /evaluation/preflight sin bloqueantes", PASS,
            detalle={
                "input_fingerprint": huella,
                "warnings": informe.get("warnings"),
                "not_evaluated": informe.get("not_evaluated"),
                "receptor": (informe.get("receptor") or {}).get("pdb_id"),
                "chain": (informe.get("receptor") or {}).get("chain"),
            },
            elapsed_s=respuesta.elapsed_s,
        )

        if args.skip_evaluation:
            for identificador, titulo in (
                ("evaluation.submit", "POST /evaluation/submit"),
                ("evaluation.poll", "GET /evaluation/status/{task_id}"),
            ):
                auditoria.anota(
                    identificador, f"{titulo} — omitido por --skip-evaluation", SKIP,
                )
            return _cerrar(auditoria, ctx)

        # ── Fase 5: submit ───────────────────────────────────────────────
        efectiva = informe.get("effective_config") or {}
        _, cuerpo_submit = contrato.payload_de(
            "/evaluation/submit", "post",
            {
                "smiles": args.smiles,
                "target_pdb_id": args.target_pdb_id,
                "chain": (informe.get("receptor") or {}).get("chain"),
                "molecule_name": "qa-vm-audit",
                "grid_center": efectiva.get("grid_center"),
                "grid_size": efectiva.get("grid_size"),
                "preflight_fingerprint": huella,
            },
        )
        respuesta = peticion(
            ctx.base, "POST", "/evaluation/submit",
            cuerpo=cuerpo_submit, token=args.token, timeout=args.request_timeout,
        )
        evidencia_submit: dict[str, Any] = {
            "request": peticion_como_evidencia(
                "POST", "/evaluation/submit", cuerpo_submit
            ),
            "response": respuesta.como_evidencia(),
            "task_id": None,
            "backend_log": evidencia_backend(),
        }
        aceptada = respuesta.json() if respuesta.status == 202 else {}
        task_id = aceptada.get("task_id") if isinstance(aceptada, dict) else None
        evidencia_submit["task_id"] = task_id
        if respuesta.status != 202 or not isinstance(task_id, str) or not task_id:
            titulo = (
                f"POST /evaluation/submit devolvió {respuesta.status}, se esperaba 202"
                if respuesta.status != 202
                else "202 sin task_id utilizable"
            )
            auditoria.anota(
                "evaluation.submit", titulo, FAIL,
                detalle={"status": respuesta.status},
                evidencia=evidencia_submit,
                elapsed_s=respuesta.elapsed_s,
            )
            auditoria.anota(
                "evaluation.poll",
                "GET /evaluation/status/{task_id} — no hubo task_id", SKIP,
                detalle={"motivo": "el submit no devolvió un task_id"},
            )
            return _cerrar(auditoria, ctx)

        auditoria.anota(
            "evaluation.submit", "POST /evaluation/submit aceptado (202)", PASS,
            detalle={
                "task_id": task_id,
                "smiles_hash": aceptada.get("smiles_hash"),
                "target_pdb_id": aceptada.get("target_pdb_id"),
            },
            elapsed_s=respuesta.elapsed_s,
        )

        # ── Fase 6: polling hasta estado terminal ────────────────────────
        ruta_estado = f"/evaluation/status/{task_id}"
        inicio_poll = time.monotonic()
        limite = inicio_poll + args.eval_timeout
        ultimo: Respuesta | None = None
        terminal: dict[str, Any] | None = None
        sondeos = 0
        while True:
            sondeos += 1
            ultimo = peticion(
                ctx.base, "GET", ruta_estado,
                token=args.token, timeout=args.request_timeout,
            )
            if ultimo.status == 200:
                try:
                    cuerpo = ultimo.json()
                except ValueError:
                    cuerpo = None
                if isinstance(cuerpo, dict) and cuerpo.get("status") in ESTADOS_TERMINALES:
                    terminal = cuerpo
                    break
            elif ultimo.status is not None and ultimo.status >= 400:
                break
            if time.monotonic() >= limite:
                break
            time.sleep(args.poll_interval)

        elapsed_poll = time.monotonic() - inicio_poll
        evidencia_poll = {
            "request": peticion_como_evidencia("GET", ruta_estado, None),
            "response": ultimo.como_evidencia() if ultimo else None,
            "task_id": task_id,
            "submit_request": evidencia_submit["request"],
            "polls": sondeos,
            "backend_log": evidencia_backend(),
        }
        if terminal is None:
            # Un 4xx/5xx en el polling es un fallo del contrato; agotar el
            # presupuesto sin estado terminal es un timeout. No son lo mismo y
            # no se anotan igual.
            hubo_error_http = (
                ultimo is not None
                and ultimo.status is not None
                and ultimo.status >= 400
            )
            auditoria.anota(
                "evaluation.poll",
                (
                    f"El polling devolvió {ultimo.status}"
                    if hubo_error_http
                    else "La corrida no alcanzó un estado terminal"
                ),
                FAIL if hubo_error_http else TIMEOUT,
                detalle={
                    "polls": sondeos,
                    "ultimo_status_http": ultimo.status if ultimo else None,
                },
                evidencia=evidencia_poll,
                elapsed_s=elapsed_poll,
                timeout_s=args.eval_timeout,
            )
        elif terminal.get("status") == "SUCCESS":
            resultado = terminal.get("result") or {}
            (salida / "resultado.json").write_text(
                json.dumps(terminal, indent=2, ensure_ascii=False, default=str),
                encoding="utf-8",
            )
            auditoria.anota(
                "evaluation.poll", "La corrida terminó en SUCCESS", PASS,
                detalle={
                    "task_id": task_id,
                    "polls": sondeos,
                    "molecule_id": resultado.get("molecule_id"),
                    "affinity_kcal": resultado.get("affinity_kcal"),
                    "total_score": resultado.get("total_score"),
                },
                elapsed_s=elapsed_poll,
                timeout_s=args.eval_timeout,
            )
        else:
            auditoria.anota(
                "evaluation.poll",
                f"La corrida terminó en {terminal.get('status')}", FAIL,
                detalle={
                    "task_id": task_id,
                    "polls": sondeos,
                    "status": terminal.get("status"),
                    "error": terminal.get("error"),
                },
                evidencia=evidencia_poll,
                elapsed_s=elapsed_poll,
                timeout_s=args.eval_timeout,
            )

        return _cerrar(auditoria, ctx)

    except (ContratoRoto, ArnesAbortado) as exc:
        ctx.aborto = f"{type(exc).__name__}: {exc}"
        bitacora.linea(f"ABORTA: {ctx.aborto}")
        # Código 2: el arnés no pudo auditar. NO es un veredicto sobre el
        # producto, y no debe leerse como uno.
        return _cerrar(auditoria, ctx, codigo_forzado=2)
    finally:
        parar_backend(proceso, handle)
        bitacora.cerrar()


def main(argv: Sequence[str] | None = None) -> int:
    return ejecutar(construir_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
