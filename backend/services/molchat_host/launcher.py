"""Supervisor del sidecar MolChat: localizar, verificar, arrancar, parar.

El sidecar arranca BAJO DEMANDA (la primera sesión lo levanta): el escritorio
no paga su coste si el usuario nunca abre el panel, y un sidecar roto no
impide arrancar MolDesign. Antes de cada arranque se verifica el manifiesto;
copia alterada, contrato desconocido o puerto esquivo ⇒ no arranca y el
motivo viaja en la excepción (el router lo convierte en 503).

Todo aquí es síncrono a propósito: el router expone endpoints `def` y
FastAPI los corre en su threadpool, sin bloquear el loop. El `Lanzador` de
producción es único por proceso (`obtener_lanzador`); las pruebas instancian
los suyos.
"""
from __future__ import annotations

import json
import os
import secrets
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

from services.molchat_host import manifest, sesion
from utils.procesos import BANDERAS_SIN_VENTANA

ARRANQUE_TIMEOUT_S = 60.0
PARADA_TIMEOUT_S = 10.0
SALUD_RUTA = "/v1/health"

#: El intérprete empaquetado del escritorio es un Python aislado (su `._pth`
#: fija sys.path): ignora `PYTHONPATH` y `-m` nunca añade el cwd, así que el
#: sidecar no se puede resolver desde el entorno. Lo resuelve el propio
#: proceso: `sys.argv[1]` es el `src/` vendorizado, el resto es la CLI, y el
#: código de salida de `main()` se propaga. `PYTHONPATH` se sigue fijando
#: abajo como cortesía para intérpretes no aislados y para depuración, pero
#: nada depende de ella.
ARRANQUE_CMD = (
    "import sys; sys.path.insert(0, sys.argv.pop(1)); "
    "from molchat_agent.cli import main; raise SystemExit(main())"
)


class LanzadorError(RuntimeError):
    """El sidecar no arrancó o no paró. El mensaje se puede mostrar."""


def localizar() -> tuple[Path | None, str]:
    """(carpeta, motivo): la copia a usar, o (None, por qué no hay)."""
    carpeta = manifest.directorio_incluido()
    if carpeta is None:
        return None, "sin sidecar incluido (tools/molchat/ ausente)"
    if os.environ.get("MOLDESIGN_MOLCHAT_DIR") \
            and carpeta != manifest.directorio_incluido(solo_incluido=True) \
            and not manifest.molchat_externo_permitido():
        return None, ("MOLDESIGN_MOLCHAT_DIR apunta fuera de lo incluido: "
                      "sólo con MOLCHAT_PERMITIR_EXTERNO=1")
    problemas = manifest.verificar_integridad(carpeta)
    if problemas:
        return None, "copia alterada: " + "; ".join(problemas[:3])
    manifiesto = manifest.manifiesto_de(carpeta)
    contrato = (manifiesto.get("contrato") or {}).get("agente_plataforma")
    if contrato != manifest.CONTRATO_SIDECAR:
        return None, (f"contrato {contrato!r}: este host habla "
                      f"{manifest.CONTRATO_SIDECAR}")
    if carpeta == manifest.directorio_incluido(solo_incluido=True):
        # La copia incluida debe ser la fijada. Una copia externa, con permiso
        # explícito para desarrollar, se acepta sin fijación: la elige quien la usa.
        problemas = manifest.verificar_fijacion(carpeta)
        if problemas:
            return None, "la llave no coincide con su fijación: " + "; ".join(problemas[:3])
    return carpeta, "ok"


def puerto_libre() -> int:
    """Un puerto loopback libre ahora mismo (el arranque confirma que sigue)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


class Lanzador:
    def __init__(self, *, python: Path | str | None = None,
                 host: str = "127.0.0.1", port: int | None = None,
                 moldesign_url: str = "http://127.0.0.1:18017",
                 arranque_timeout_s: float = ARRANQUE_TIMEOUT_S) -> None:
        self._python = str(python or sys.executable)
        self._host = host
        self._port = port
        self._moldesign_url = moldesign_url
        self._timeout = arranque_timeout_s
        self._proceso: subprocess.Popen | None = None
        self._url: str | None = None
        self._drenaje: threading.Thread | None = None
        self._salida: list[str] = []
        self._candado = threading.Lock()

    @property
    def url(self) -> str | None:
        return self._url

    def vivo(self) -> bool:
        return self._proceso is not None and self._proceso.poll() is None

    def estado(self) -> dict:
        """Lo que GET /molchat-host/status cuenta (sin secretos)."""
        carpeta, motivo = localizar()
        manifiesto = manifest.manifiesto_de(carpeta) if carpeta else {}
        fuente = manifiesto.get("fuente", {})
        incluida = carpeta is not None and carpeta == manifest.directorio_incluido(solo_incluido=True)
        fijada = manifest.fijacion_resumen() if incluida else {"repositorio": "", "oficial": False}
        return {
            "disponible": carpeta is not None,
            "motivo": motivo,
            "en_marcha": self.vivo(),
            "url": self._url,
            "version": manifiesto.get("version"),
            "commit": (fuente.get("commit") or "")[:12],
            "contrato": (manifiesto.get("contrato") or {}).get("agente_plataforma"),
            "externa": carpeta is not None and not incluida,
            "oficial": fijada["oficial"],
            "repositorio": fijada["repositorio"],
        }

    def arrancar(self) -> str:
        """Levanta el sidecar y espera su salud. Idempotente. Devuelve la URL."""
        with self._candado:
            if self.vivo() and self._saludable():
                assert self._url is not None
                return self._url
            if self.vivo():
                self._matar()
            carpeta, motivo = localizar()
            if carpeta is None:
                raise LanzadorError(motivo)
            puerto = self._port or puerto_libre()
            secreto = secrets.token_hex(32)
            sesion.fijar_secreto_host(secreto.encode("utf-8"))
            env = dict(os.environ)
            env["PYTHONPATH"] = str(carpeta / "src") + (
                os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
            env["MOLCHAT_HOST_SECRET"] = secreto
            env["MOLDESIGN_BASE_URL"] = self._moldesign_url
            argv = [self._python, "-c", ARRANQUE_CMD, str(carpeta / "src"),
                    "serve", "--host", self._host, "--port", str(puerto),
                    "--ui-dist", str(carpeta / "ui" / "dist")]
            try:
                self._proceso = subprocess.Popen(
                    argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    cwd=str(carpeta), creationflags=BANDERAS_SIN_VENTANA,
                    env=env)
            except OSError as exc:
                raise LanzadorError(f"no se pudo lanzar el intérprete: {exc}") from exc
            self._url = f"http://{self._host}:{puerto}"
            self._salida = []
            self._arrancar_drenaje()
            if not self._esperar_salud():
                cola = " ".join(self._salida[-5:])
                self._matar()
                raise LanzadorError(
                    f"el sidecar no respondió salud en {self._timeout:.0f}s"
                    + (f": {cola}" if cola else ""))
            return self._url

    def detener(self) -> str:
        """Para el sidecar; mata tras un periodo de gracia. Idempotente."""
        with self._candado:
            proceso, self._proceso = self._proceso, None
            self._url = None
            if proceso is None or proceso.poll() is not None:
                return "detenido"
            proceso.terminate()
            try:
                proceso.wait(timeout=PARADA_TIMEOUT_S)
            except subprocess.TimeoutExpired:
                proceso.kill()
                proceso.wait(timeout=PARADA_TIMEOUT_S)
            return "detenido"

    def _saludable(self) -> bool:
        if not self._url:
            return False
        try:
            with urllib.request.urlopen(
                    self._url + SALUD_RUTA, timeout=3) as respuesta:
                if not respuesta.status or respuesta.status >= 400:
                    return False
                cuerpo = json.loads(respuesta.read(4097))
                return (isinstance(cuerpo, dict) and cuerpo.get("status") == "ok"
                        and cuerpo.get("contract") == manifest.CONTRATO_SIDECAR)
        except (OSError, ValueError, TypeError):
            return False

    def _esperar_salud(self) -> bool:
        limite = time.monotonic() + self._timeout
        pausa = 0.2
        while time.monotonic() < limite:
            if not self.vivo():
                return False
            if self._saludable():
                return True
            time.sleep(pausa)
            pausa = min(pausa * 1.5, 2.0)
        return self.vivo() and self._saludable()

    def _arrancar_drenaje(self) -> None:
        assert self._proceso is not None and self._proceso.stdout is not None
        tuberia = self._proceso.stdout
        cola = self._salida

        def _drenar() -> None:
            try:
                for linea in tuberia:
                    texto = linea.decode("utf-8", "replace").strip()
                    if texto and len(cola) < 50:
                        cola.append(texto[-200:])
            except (OSError, ValueError):
                pass

        self._drenaje = threading.Thread(target=_drenar, daemon=True)
        self._drenaje.start()

    def _matar(self) -> None:
        proceso, self._proceso = self._proceso, None
        self._url = None
        if proceso is None:
            return
        try:
            proceso.kill()
            proceso.wait(timeout=PARADA_TIMEOUT_S)
        except (OSError, subprocess.TimeoutExpired):
            pass


_LANZADOR: Lanzador | None = None
_CANDADO_GLOBAL = threading.Lock()


def obtener_lanzador(moldesign_url: str = "http://127.0.0.1:18017") -> Lanzador:
    """El lanzador del proceso (la primera llamada fija la configuración)."""
    global _LANZADOR
    with _CANDADO_GLOBAL:
        if _LANZADOR is None:
            _LANZADOR = Lanzador(moldesign_url=moldesign_url)
        return _LANZADOR
