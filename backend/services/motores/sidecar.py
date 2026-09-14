"""Supervisor de los motores que viven en un proceso aparte.

Sigue el patrón que ya está probado en `services/ai/local_llm.py` para
`llama-server.exe`, porque los modos de fallo son los mismos y ya se pagaron una
vez: el proceso se lanza sin ventana, se drena su salida para que no se bloquee
al llenarse la tubería, se espera a que `/health` responda en vez de suponer que
arrancó, y se apaga al salir la aplicación.

Tres reglas propias de esta capa:

1. **Encender es explícito.** Nadie levanta un motor de 8 GB porque una pantalla
   se abrió. Se enciende cuando el investigador lo pide o cuando una corrida que
   ya lo eligió va a usarlo.
2. **Los pesos se pasan por entorno.** El sidecar carga del directorio que se le
   indica y con `local_files_only`: un servicio de plegamiento que resuelve el
   modelo «por su nombre» acaba saliendo a la red en una aplicación que promete
   no hacerlo.
3. **Un arranque fallido se recuerda con su motivo.** El siguiente que pregunte
   tiene que leer qué pasó, no un «no disponible» sin causa.
"""

from __future__ import annotations

import atexit
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Optional

import urllib.error
import urllib.request

from utils.logger import get_logger
from utils.procesos import BANDERAS_SIN_VENTANA

from services.motores.catalogo import (
    CATALOGO,
    POR_ID,
    EstadoMotor,
    MotorDescargable,
    RAIZ,
    archivos_que_faltan,
    dependencias_que_faltan,
    directorio_del_modelo,
    estado_de,
)

log = get_logger(__name__)

#: Cuánto se espera a que el proceso conteste `/health` antes de darlo por muerto.
#: Cargar 8.4 GB desde disco no es instantáneo, y menos en un disco mecánico.
ESPERA_ARRANQUE_S = 180.0
INTERVALO_SONDA_S = 1.0
TIMEOUT_SONDA_S = 2.0

#: Cuánto se espera a que el puerto ACEPTE, antes de gastar la sonda HTTP.
#:
#: Un `accept` en loopback lo resuelve el sistema operativo y es inmediato
#: aunque el proceso esté ocupado. Medio segundo es holgadísimo incluso en
#: una máquina virtual, y si se agota es que no hay nadie al otro lado.
TIMEOUT_CONEXION_S = 0.5


class MotorSidecar:
    """Un motor en su propio proceso. Idempotente en encender y apagar."""

    def __init__(self, motor: MotorDescargable):
        if motor.sidecar is None:
            raise ValueError(f"{motor.id} no declara sidecar")
        self.motor = motor
        self.spec = motor.sidecar
        self._proceso: Optional[subprocess.Popen] = None
        self._error: str | None = None
        self._drenaje: threading.Thread | None = None

    # ── Estado ────────────────────────────────────────────────────────────

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.spec.puerto}"

    @property
    def error(self) -> str | None:
        return self._error

    def esta_vivo(self) -> bool:
        """El proceso existe y no ha terminado. No dice que ya sirva."""
        return self._proceso is not None and self._proceso.poll() is None

    def _puerto_acepta(self) -> bool:
        """¿Hay alguien escuchando? Pregunta barata antes de la cara.

        MEDIDO en Windows contra el puerto del sidecar apagado: el puerto no
        RECHAZA la conexión, la traga en silencio —lo hace el cortafuegos—, así
        que `connect` agota el tiempo que se le dé, sea el que sea:

            urlopen, timeout 2 s      2 013 ms
            socket.connect, 250 ms      264 ms

        Un `accept` de TCP en loopback lo hace el sistema operativo, no la
        aplicación: un sidecar ocupado cargando 8 GB de pesos sigue aceptando la
        conexión al instante, y entonces se cae a la sonda HTTP de siempre. Por
        eso este atajo no puede declarar apagado un motor que esté encendido.
        """
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(TIMEOUT_CONEXION_S)
        try:
            s.connect(("127.0.0.1", self.motor.sidecar.puerto))
            return True
        except OSError:
            return False
        finally:
            s.close()

    def responde(self) -> bool:
        """`/health` contesta. Es lo único que autoriza a decir «listo»."""
        if not self._puerto_acepta():
            return False
        try:
            peticion = urllib.request.Request(f"{self.url}/health", method="GET")
            with urllib.request.urlopen(peticion, timeout=TIMEOUT_SONDA_S) as r:
                return 200 <= r.status < 300
        except (urllib.error.URLError, OSError, ValueError):
            return False

    def _puede_estar_vivo(self) -> bool:
        """¿Tiene sentido siquiera preguntarle?

        Un motor cuyos pesos NO están descargados no puede estar sirviendo: el
        sidecar no arranca sin checkpoint. Preguntárselo igual es gastar el
        presupuesto entero de la sonda contra un puerto donde no hay nadie.
        """
        if self.esta_vivo():
            return True
        return not archivos_que_faltan(self.motor)

    def estado(self) -> EstadoMotor:
        # ── POR QUÉ NO SE SONDEA SIEMPRE ───────────────────────────────────
        #
        # Esto era `estado_de(self.motor, encendido=self.responde(), ...)`, y
        # Python evalúa los argumentos ANTES de llamar: la sonda corría en todas
        # las llamadas, incluso cuando el propio `estado_de` iba a devolver
        # «no instalado» sin mirarla.
        #
        # MEDIDO sobre el runtime empaquetado, con ESMFold sin descargar:
        #
        #     inventario_de_motores()            2 022 ms
        #       estados_de_motores_descargables()  2 012 ms   <- la sonda
        #       archivos_que_faltan(esmfold)           0.8 ms
        #       dependencias_que_faltan(esmfold)       1.0 ms
        #
        # Dos segundos exactos, que es el timeout, en CADA apertura del panel de
        # opciones y en cada arranque de la interfaz. Y se pagan justamente en
        # la máquina donde más duele: una instalación recién hecha, que es la
        # que nunca ha descargado los pesos. En la máquina del revisor de la
        # Store, siempre.
        #
        # Con esta guarda, quien no ha descargado el motor no espera nada; quien
        # sí lo ha descargado sigue recibiendo la respuesta honesta de la sonda,
        # que es la única que autoriza a decir «listo».
        encendido = self.responde() if self._puede_estar_vivo() else False
        return estado_de(self.motor, encendido=encendido, error=self._error)

    # ── Ciclo de vida ─────────────────────────────────────────────────────

    def encender(self, *, modo: str | None = None) -> bool:
        """Lanza el proceso y espera a que sirva. Idempotente."""
        if self.responde():
            return True

        self._error = None

        faltan = archivos_que_faltan(self.motor)
        if faltan:
            self._error = (
                f"faltan {len(faltan)} archivo(s) del modelo; descárgalo desde el "
                "gestor de modelos"
            )
            return False

        faltan_deps = dependencias_que_faltan(self.motor)
        if faltan_deps:
            self._error = f"este runtime no trae {', '.join(faltan_deps)}"
            return False

        directorio_servicio = RAIZ / "backend" / "sidecars" / self.spec.paquete
        if not (directorio_servicio / "app.py").exists():
            self._error = f"no se encontró el servicio en {directorio_servicio}"
            return False

        modelo = directorio_del_modelo(self.motor)
        entorno = os.environ.copy()
        entorno[self.spec.variable_modelo] = str(modelo) if modelo else ""
        entorno["ESMFOLD_PORT"] = str(self.spec.puerto)
        # El host es 127.0.0.1 y no 0.0.0.0: este proceso sirve a la aplicación
        # de esta máquina. Escuchar en todas las interfaces expondría un motor
        # sin autenticación a la red local.
        entorno["ESMFOLD_HOST"] = "127.0.0.1"
        if modo:
            entorno["ESMFOLD_MODE"] = modo

        argumentos = [
            sys.executable,
            "-m",
            "uvicorn",
            self.spec.app,
            "--host",
            "127.0.0.1",
            "--port",
            str(self.spec.puerto),
            "--log-level",
            "warning",
        ]

        try:
            flags = BANDERAS_SIN_VENTANA
            self._proceso = subprocess.Popen(
                argumentos,
                cwd=str(directorio_servicio),
                env=entorno,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                creationflags=flags,
            )
        except Exception as exc:  # noqa: BLE001 — el motivo va al estado
            self._error = f"no se pudo lanzar el proceso: {exc}"
            self._proceso = None
            return False

        # Drenar la salida ANTES de sondear: el servicio escribe el progreso de
        # carga del checkpoint, y una tubería de 64 KB llena bloquea al proceso.
        # Es el mismo fallo que ya mordió con `llama-server`.
        self._iniciar_drenaje()
        log.info("motor_sidecar_lanzado", motor=self.motor.id, pid=self._proceso.pid,
                 puerto=self.spec.puerto)

        limite = time.monotonic() + ESPERA_ARRANQUE_S
        while time.monotonic() < limite:
            if not self.esta_vivo():
                codigo = self._proceso.returncode if self._proceso else "?"
                self._error = f"el proceso terminó al arrancar (código {codigo})"
                self._proceso = None
                return False
            if self.responde():
                log.info("motor_sidecar_listo", motor=self.motor.id)
                return True
            time.sleep(INTERVALO_SONDA_S)

        self._error = (
            f"no respondió en {int(ESPERA_ARRANQUE_S)} s. Cargar el checkpoint puede "
            "tardar más en un disco lento; vuelve a intentarlo."
        )
        self.apagar()
        return False

    def apagar(self) -> None:
        proceso, self._proceso = self._proceso, None
        if proceso is None or proceso.poll() is not None:
            return
        try:
            proceso.terminate()
            try:
                proceso.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proceso.kill()
                proceso.wait(timeout=5)
        except Exception as exc:  # noqa: BLE001
            log.warning("motor_sidecar_apagado_sucio", motor=self.motor.id, error=str(exc))
        else:
            log.info("motor_sidecar_apagado", motor=self.motor.id)

    def _iniciar_drenaje(self) -> None:
        proceso = self._proceso
        if proceso is None or proceso.stdout is None:
            return

        def _drenar() -> None:
            try:
                for linea in proceso.stdout:  # type: ignore[union-attr]
                    texto = linea.decode("utf-8", "replace").strip()
                    if texto:
                        log.debug("motor_sidecar_salida", motor=self.motor.id, linea=texto[:300])
            except Exception:  # noqa: BLE001 — el drenaje nunca puede tumbar el backend
                pass

        self._drenaje = threading.Thread(target=_drenar, daemon=True,
                                         name=f"drenaje-{self.motor.id}")
        self._drenaje.start()


# ── Registro por proceso ─────────────────────────────────────────────────────

_SIDECARS: dict[str, MotorSidecar] = {}


def sidecar_de(motor_id: str) -> MotorSidecar | None:
    motor = POR_ID.get(motor_id)
    if motor is None or motor.sidecar is None:
        return None
    if motor_id not in _SIDECARS:
        _SIDECARS[motor_id] = MotorSidecar(motor)
    return _SIDECARS[motor_id]


def estados_de_motores_descargables() -> list[dict]:
    """El estado de cada motor descargable, para el contrato de la interfaz."""
    salida: list[dict] = []
    for motor in CATALOGO:
        sc = sidecar_de(motor.id)
        estado = sc.estado() if sc else estado_de(motor)
        salida.append(estado.como_dict())
    return salida


def _apagar_todos() -> None:
    for sc in list(_SIDECARS.values()):
        try:
            sc.apagar()
        except Exception:  # noqa: BLE001
            pass


atexit.register(_apagar_todos)
