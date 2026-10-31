"""services/evaluation/proposals.py

LUNA-05 — MolChat PROPONE un docking; sólo el investigador, por otra puerta, lo lanza.

# El fallo

`run_docking` construía la petición y la registraba en el MISMO turno: del texto del
investigador a una corrida de Vina en cola sin que nadie viera qué se iba a ejecutar.
El criterio de la auditoría pide una confirmación explícita y separada: ver receptor,
motor y política efectiva antes, y que lo que se lance sea exactamente lo que se vio.
(El preflight del servidor valida bloqueantes; no es una aceptación humana.)

# Cómo funciona ahora

1. **Proponer** (`proponer`): el servidor construye la petición, corre el preflight
   REAL (el mismo informe que usa la pestaña Evaluación) y, si no hay bloqueantes,
   guarda la propuesta —petición completa más la huella del preflight que se va a
   mostrar— y la presenta en el chat: receptor y cadena, motor, protocolo efectivo,
   caja, política de heteroátomos, advertencias y coste aproximado. NADA se encola.
2. **Aprobar** (`aprobar`): sólo `POST /ai/proposals/{id}/approve`, con la sesión de
   la cuenta, envía la orden. Un «sí» escrito en el chat NO aprueba: es un mensaje de
   texto, y la aprobación tiene que ser un acto distinto del texto que se interpretó.
3. La petición que se lanza sale del servidor, **nunca del cliente**: el cuerpo de la
   aprobación sólo lleva el id y la huella que el investigador vio. Se comprueban
   cuenta, caducidad y huella; la propuesta se consume de forma atómica (una sola
   aprobación); y la puerta común (`registrar_corrida`) vuelve a correr el preflight y
   compara su huella con la mostrada: si la preparación cambió entre la propuesta y la
   aprobación, no se lanza.

# Lo que NO hace, a propósito

* **No persiste** la propuesta más allá de `TTL_PROPUESTA_S` ni de un reinicio del
  motor: vive en el almacén efímero local, como las tareas en curso. Una propuesta que
  caduca se vuelve a pedir; es preferible a una aprobación vieja sobre un receptor que
  quizá ya cambió.
* **No restituye** una propuesta cuya aprobación falló en la puerta común: se consumió,
  y el investigador tiene que pedirla de nuevo. Una propuesta que pudiera aprobarse dos
  veces es peor que una que hay que repetir.
* **No estima un número**: el coste es el rango del estimador del producto
  (`services.estimacion`), con su apoyo declarado («modelo medido en otra máquina» o
  «calibrado con N acoplamientos de este equipo»).
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import secrets
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException

from utils.logger import get_logger

log = get_logger(__name__)

#: Cuánto vive una propuesta sin aprobar. Pasado este tiempo el receptor, la caja o el
#: motor pueden no ser los que se mostraron: se vuelve a pedir.
TTL_PROPUESTA_S = 15 * 60

#: Marcador que el frontend convierte en la tarjeta con los botones. Va en un comentario
#: HTML para que, sin esa tarjeta (otro cliente, el historial en bruto), el texto siga
#: leyéndose entero.
MARCADOR = "__DOCKING_PROPOSAL__"

_PREFIJO = "molchat:propuesta_docking:"

_RE_MARCADOR = re.compile(rf"<!--{MARCADOR}\s+id=(\w+)\s+hash=(sha256:[0-9a-f]{{64}})-->")

#: Respuestas cortas que, tecleadas, suenan a «sí, lánzalo».
_AFIRMATIVOS = frozenset({
    "sí", "si", "s", "claro", "dale", "ok", "vale", "confirmo", "acepto", "lanza",
    "lánzala", "lanzala", "lánzalo", "lanzalo", "adelante", "aprobado", "apruebo",
    "aprobar", "hazlo", "envíalo", "envialo", "yes", "y",
})

NO_PENDIENTE = (
    "Esta propuesta ya no está pendiente: se aprobó, se rechazó o caducó. "
    "Pídela de nuevo en el chat."
)


class PropuestaNoAplicable(Exception):
    """Una propuesta que no se puede consultar, aprobar o rechazar, con su código HTTP."""

    def __init__(self, status_code: int, detalle: str) -> None:
        super().__init__(detalle)
        self.status_code = status_code
        self.detalle = detalle


class PropuestaBloqueada(Exception):
    """El preflight bloquea la corrida: no hay propuesta aprobable (CR-07).

    Lleva el informe completo para que la creación HTTP lo devuelva tal
    cual, sin propuesta que aprobar.
    """

    def __init__(self, informe: dict[str, Any]) -> None:
        super().__init__("El preflight del servidor bloquea esta evaluación.")
        self.informe = informe


def _clave(propuesta_id: str) -> str:
    return f"{_PREFIJO}{propuesta_id}"


def huella_de_propuesta(
    *,
    user_id: str,
    canonical_smiles: str,
    target_pdb_id: str,
    chain: str | None,
    pipeline_config: dict | None,
    input_fingerprint: str,
) -> str:
    """Huella de TODO lo que la aprobación autoriza: cuenta, ligando, receptor,
    protocolo y la preparación exacta que inspeccionó el preflight."""
    documento = {
        "user_id": user_id,
        "canonical_smiles": canonical_smiles,
        "target_pdb_id": target_pdb_id,
        "chain": chain,
        "pipeline_config": pipeline_config,
        "input_fingerprint": input_fingerprint,
    }
    canonico = json.dumps(documento, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(canonico.encode("utf-8")).hexdigest()


def _duracion(segundos: float) -> str:
    segundos = max(0, int(round(segundos)))
    minutos, resto = divmod(segundos, 60)
    if minutos == 0:
        return f"{resto} s"
    return f"{minutos} min {resto:02d} s" if resto else f"{minutos} min"


def _coste_aproximado(informe: dict[str, Any]) -> tuple[str, list[str]]:
    """(rango legible, avisos) del estimador del producto; nunca un número inventado."""
    try:
        # Las mismas piezas que `GET /evaluation/estimate` (api/main.py): el coste que
        # se muestra aquí es el que la pestaña Evaluación mostraría.
        from api.main import receptor_preparado_en_disco
        from core.config import get_settings
        # Sólo los núcleos: `detect_hardware()` importaba torch y openmm, y `proponer` (async) lo llamaba en el bucle
        # de eventos, que se congelaba (2026-10-10).
        from core.hardware import nucleos_logicos
        from services.docking.search_policy import VINA_PROCESS_LIMIT
        from services.estimacion import estimar_corrida

        config = informe["effective_config"]
        tamano = config["grid_size"]
        try:
            preparado = receptor_preparado_en_disco(informe["receptor"]["pdb_id"])
        except Exception:  # noqa: BLE001 - no saberlo se trata como «ya está»
            preparado = True
        e = estimar_corrida(
            cpu=int(getattr(get_settings(), "vina_cpu", 0) or nucleos_logicos()),
            exhaustiveness=int(config["exhaustiveness"]),
            conformers=int(config["conformers"]),
            volumen_caja=float(tamano[0]) * float(tamano[1]) * float(tamano[2]),
            receptor_preparado=preparado,
            docks_en_paralelo=VINA_PROCESS_LIMIT,
        )
        rango = f"{_duracion(e['segundos_min'])} – {_duracion(e['segundos_max'])}"
        return f"{rango} ({e['apoyo']}: {e['detalle_apoyo']})", list(e.get("avisos") or [])
    except Exception as exc:  # noqa: BLE001 - sin estimación se dice, no se rellena
        log.warning("propuesta_sin_estimacion", error=str(exc)[:160])
        return "no disponible (no se pudo estimar en este equipo; no se inventa un tiempo)", []


def _version_de_vina() -> str:
    try:
        from api.routers.evaluation import inventario_de_motores

        for motor in inventario_de_motores().get("docking", []):
            if motor.get("id") == "vina" and motor.get("version"):
                return f"AutoDock Vina {motor['version']}"
    except Exception:  # noqa: BLE001
        pass
    return "AutoDock Vina"


def _controles_a_leer(informe: dict[str, Any], estados: tuple[str, ...]) -> list[str]:
    lineas = []
    for control in informe.get("controls", []):
        if control.get("state") in estados:
            lineas.append(f"{control.get('title')}: {control.get('observation')}")
    return lineas


def _texto_de_la_propuesta(
    *, propuesta_id: str, huella: str, informe: dict[str, Any], coste: str
) -> str:
    receptor = informe["receptor"]
    config = informe["effective_config"]
    politica = config.get("heteroatom_policy", {})
    centro = ", ".join(f"{v:g}" for v in config["grid_center"])
    tamano = ", ".join(f"{v:g}" for v in config["grid_size"])
    advertencias = _controles_a_leer(informe, ("advertencia",))
    sin_evaluar = _controles_a_leer(informe, ("no_evaluado",))

    lineas = [
        "**Propuesta de evaluación — todavía NO lanzada.** Nada está en cola.",
        "",
        f"- **Ligando:** `{informe['ligand'].get('canonical_smiles') or informe['ligand'].get('input_smiles')}`",
        (
            f"- **Receptor:** {receptor['pdb_id']} · cadena {receptor['chain']} · "
            f"origen {receptor['origin']}"
        ),
        f"- **Motor:** {_version_de_vina()} (`{config['docking_engine']}`)",
        (
            f"- **Protocolo efectivo:** exhaustividad {config['exhaustiveness']} · "
            f"{config['num_poses']} poses · {config['conformers']} "
            f"conformación{'es' if int(config['conformers']) != 1 else ''} · semilla {config['seed']}"
        ),
        f"- **Caja:** centro ({centro}) Å · tamaño ({tamano}) Å",
        (
            f"- **Heteroátomos:** aguas {politica.get('waters', '?')} · metales "
            f"{politica.get('metals', '?')} · cofactores orgánicos "
            f"{politica.get('organic_cofactors', '?')}"
        ),
        f"- **Coste aproximado:** {coste}",
        f"- **Huella de la propuesta:** `{huella[:19]}…` · caduca en {TTL_PROPUESTA_S // 60} min",
    ]
    if advertencias:
        lineas += ["", "**Advertencias del preflight (léelas antes de aprobar):**"]
        lineas += [f"- {a}" for a in advertencias[:8]]
    if sin_evaluar:
        lineas += ["", "**No evaluado** (no se sabe, no se da por bueno):"]
        lineas += [f"- {a}" for a in sin_evaluar[:6]]
    lineas += [
        "",
        "Para lanzarla, aprueba esta propuesta con el botón **Aprobar y lanzar**. Escribir "
        "«sí» en el chat **no** la lanza: la aprobación se confirma con tu sesión y queda "
        "atada a esta huella.",
        "",
        f"<!--{MARCADOR} id={propuesta_id} hash={huella}-->",
    ]
    return "\n".join(lineas)


async def _crear_registro(
    *,
    peticion: Any,
    usuario: Any,
    db: Any,
    conversacion_id: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Núcleo de creación compartido por el chat y por HTTP (CR-07).

    Corre el preflight real, guarda la propuesta y devuelve
    ``(registro, informe)``. No encola nada. Si el preflight bloquea, lanza
    `PropuestaBloqueada` con el informe completo y no guarda propuesta.
    """
    from api.routers.evaluation import comprobar_preparacion
    from chem.validator import validate_smiles_or_raise
    from utils.cache import cache

    validacion = validate_smiles_or_raise(peticion.smiles)
    informe = await comprobar_preparacion(
        data=peticion,
        canonical_smiles=validacion.canonical_smiles,
        db=db,
        current_user=usuario,
    )

    if informe.get("technical_blockers"):
        raise PropuestaBloqueada(informe)

    firmada = peticion.model_copy(
        update={"preflight_fingerprint": informe["input_fingerprint"]}
    )
    cuerpo = firmada.model_dump(mode="json", exclude_none=True)
    huella = huella_de_propuesta(
        user_id=str(usuario.id),
        canonical_smiles=validacion.canonical_smiles,
        target_pdb_id=firmada.target_pdb_id,
        chain=firmada.chain,
        pipeline_config=cuerpo.get("pipeline_config"),
        input_fingerprint=informe["input_fingerprint"],
    )
    propuesta_id = uuid.uuid4().hex
    coste, _avisos = _coste_aproximado(informe)
    registro = {
        "id": propuesta_id,
        "user_id": str(usuario.id),
        "conversation_id": conversacion_id,
        "hash": huella,
        "request": cuerpo,
        "creada_en": time.time(),
        "resumen": {
            "receptor": informe["receptor"]["pdb_id"],
            "cadena": informe["receptor"]["chain"],
            "motor": informe["effective_config"]["docking_engine"],
            "coste": coste,
        },
    }
    await cache.set(_clave(propuesta_id), registro, ttl=TTL_PROPUESTA_S)
    log.info(
        "docking_propuesto",
        propuesta=propuesta_id, hash=huella[:19], receptor=firmada.target_pdb_id,
        cuenta=str(usuario.id),
    )
    return registro, informe


def _caduca_en(registro: dict[str, Any]) -> str:
    instante = datetime.fromtimestamp(
        registro["creada_en"] + TTL_PROPUESTA_S, tz=timezone.utc
    )
    return instante.isoformat()


def vista_estructurada(registro: dict[str, Any], informe: dict[str, Any]) -> dict[str, Any]:
    """La propuesta como recurso HTTP (CR-07), sin texto de chat.

    Lleva los dos nombres de cada identidad (`proposal_id`/`id`,
    `proposal_hash`/`hash`): el contrato nuevo de MolChat y el que la
    consulta existente ya devolvía designan la misma huella.
    """
    efectiva = informe["effective_config"]
    return {
        "proposal_id": registro["id"],
        "id": registro["id"],
        "proposal_hash": registro["hash"],
        "hash": registro["hash"],
        "estado": "pendiente",
        "parametros_efectivos": {
            "motor": efectiva.get("docking_engine"),
            "exhaustividad": efectiva.get("exhaustiveness"),
            "poses": efectiva.get("num_poses"),
            "semilla": efectiva.get("seed"),
            "conformaciones": efectiva.get("conformers"),
            "caja": {
                "centro": efectiva.get("grid_center"),
                "tamano": efectiva.get("grid_size"),
            },
        },
        "preflight": {
            "technical_blockers": list(informe.get("technical_blockers") or []),
            "warnings": list(informe.get("warnings") or []),
            "not_evaluated": list(informe.get("not_evaluated") or []),
        },
        "caduca_en": _caduca_en(registro),
        "expira_en_s": TTL_PROPUESTA_S,
    }


async def crear_estructurada(
    *,
    peticion: Any,
    usuario: Any,
    db: Any,
) -> dict[str, Any]:
    """Crea la propuesta revisable de CR-07. Nunca encola ni ejecuta nada."""
    registro, informe = await _crear_registro(peticion=peticion, usuario=usuario, db=db)
    return vista_estructurada(registro, informe)


async def proponer(
    *,
    peticion: Any,
    usuario: Any,
    db: Any,
    conversacion_id: str | None = None,
) -> str:
    """Corre el preflight, guarda la propuesta y devuelve el texto que la presenta.

    No encola nada. Si el preflight del servidor bloquea la corrida no hay propuesta
    que aprobar: se devuelve el motivo (y no se sustituye por una estimación).
    """
    try:
        registro, informe = await _crear_registro(
            peticion=peticion, usuario=usuario, db=db,
            conversacion_id=conversacion_id,
        )
    except PropuestaBloqueada as bloqueada:
        informe = bloqueada.informe
        motivos = _controles_a_leer(informe, ("bloquea",)) or list(
            informe.get("technical_blockers") or []
        )
        return (
            "No propongo lanzar la evaluación: el preflight del servidor la bloquea.\n"
            + "\n".join(f"- {m}" for m in motivos[:8])
            + "\n(No la sustituyo por una estimación.)"
        )
    return _texto_de_la_propuesta(
        propuesta_id=registro["id"], huella=registro["hash"],
        informe=informe, coste=registro["resumen"]["coste"],
    )


async def _propuesta_de(propuesta_id: str, usuario: Any) -> dict[str, Any]:
    """La propuesta vigente de ESTA cuenta, o el motivo exacto por el que no existe."""
    from utils.cache import cache

    registro = await cache.get(_clave(propuesta_id))
    if registro is None:
        raise PropuestaNoAplicable(410, NO_PENDIENTE)
    if registro.get("user_id") != str(usuario.id):
        # Mismo 404 que si no existiera: no se revela que la propuesta es de otra cuenta.
        raise PropuestaNoAplicable(404, "Propuesta no encontrada.")
    return registro


async def consultar(propuesta_id: str, usuario: Any) -> dict[str, Any]:
    registro = await _propuesta_de(propuesta_id, usuario)
    restante = max(0, math.ceil(TTL_PROPUESTA_S - (time.time() - registro["creada_en"])))
    return {
        "id": registro["id"],
        "proposal_id": registro["id"],
        "estado": "pendiente",
        "expira_en_s": restante,
        "caduca_en": _caduca_en(registro),
        "hash": registro["hash"],
        "proposal_hash": registro["hash"],
        "resumen": registro["resumen"],
    }


async def rechazar(propuesta_id: str, usuario: Any) -> None:
    from utils.cache import cache

    await _propuesta_de(propuesta_id, usuario)
    await cache.delete(_clave(propuesta_id))
    log.info("docking_propuesta_rechazada", propuesta=propuesta_id, cuenta=str(usuario.id))


async def aprobar(
    *,
    propuesta_id: str,
    huella: str,
    usuario: Any,
    db: Any,
    client_ip: str | None = None,
) -> tuple[Any, dict[str, Any]]:
    """Lanza la corrida que ESTA propuesta describe, y sólo esa.

    Devuelve `(CorridaRegistrada, registro de la propuesta)`. La petición sale del
    registro del servidor; del cliente sólo llegan el id y la huella que vio.
    """
    from api.routers.evaluation import EvaluationSubmitRequest
    from services import evaluation_submission
    from utils.cache import cache

    registro = await _propuesta_de(propuesta_id, usuario)
    if not secrets.compare_digest(registro["hash"], huella):
        raise PropuestaNoAplicable(
            409,
            "La huella que se aprueba no es la de esta propuesta: no se lanza nada. "
            "Pide la propuesta de nuevo.",
        )
    # Reclamo atómico: la primera aprobación se la lleva; una segunda ya no la encuentra.
    if not await cache.delete(_clave(propuesta_id)):
        raise PropuestaNoAplicable(410, NO_PENDIENTE)

    peticion = EvaluationSubmitRequest.model_validate(registro["request"])
    try:
        corrida = await evaluation_submission.registrar_corrida(
            data=peticion,
            db=db,
            current_user=usuario,
            client_ip=client_ip,
            # La puerta común recalcula el preflight y lo compara con la huella
            # que el investigador vio: si la preparación cambió, no se lanza.
            exigir_preflight=True,
        )
    except HTTPException as exc:
        log.warning(
            "docking_aprobacion_rechazada", propuesta=propuesta_id,
            status=exc.status_code, cuenta=str(usuario.id),
        )
        raise
    log.info(
        "docking_aprobado", propuesta=propuesta_id, hash=registro["hash"][:19],
        task_id=corrida.task_id, cuenta=str(usuario.id),
    )
    return corrida, registro


def mensaje_de_lanzamiento(corrida: Any) -> str:
    """El texto determinista que sigue a una aprobación: lanzada, y todavía sin número."""
    return (
        f"Evaluación lanzada en segundo plano contra {corrida.target_pdb_id}, "
        "tras tu aprobación.\n"
        f"  task_id={corrida.task_id}\n"
        f"  molécula={corrida.canonical_smiles}\n"
        f"{corrida.aviso_de_calibracion}"
        "Todavía no hay afinidad ni score: la corrida acaba de empezar y no los "
        "estimo. Consulta el estado con check_docking_status | "
        f"task_id={corrida.task_id}, y cita cualquier número por ese task_id."
    )


async def respuesta_a_un_si_escrito(
    *, mensajes: list[dict[str, Any]], mensaje_del_usuario: str, user_id: str | None
) -> str | None:
    """Qué contesta MolChat cuando alguien teclea «sí» ante una propuesta pendiente.

    La aprobación es el botón, no el texto: un «sí» es un mensaje más de la
    conversación, y la regla es que lo que lanza una corrida sea un acto distinto de
    lo que se escribió.

    `mensajes` es el historial SIN el «sí» recién escrito. Cuenta sólo si la propuesta
    es de lo último que se dijo —se recorre hacia atrás hasta el último mensaje del
    investigador— y sigue vigente y es de esta cuenta; en cualquier otro caso el «sí»
    es de otra cosa y devuelve `None`. El marcador puede estar en un mensaje del
    asistente (camino forzado) o en el del sistema que guarda el resultado de la
    herramienta (camino del clasificador determinista): el recorrido mira los dos. Esto
    lo encontró el gate runtime real, no una prueba: con sólo `assistant`, un «sí»
    generaba una SEGUNDA propuesta en vez de este aviso.
    """
    texto = (mensaje_del_usuario or "").lower().strip().strip(".,!?¿¡ ")
    if texto not in _AFIRMATIVOS:
        return None
    for mensaje in reversed(mensajes):
        if mensaje.get("role") == "user":
            return None
        hallazgo = _RE_MARCADOR.search(mensaje.get("content", "") or "")
        if not hallazgo:
            continue
        from utils.cache import cache

        registro = await cache.get(_clave(hallazgo.group(1)))
        if registro is None or registro.get("user_id") != str(user_id):
            return None
        return (
            "Escribir «sí» no lanza el docking. La aprobación se hace con el botón "
            "**Aprobar y lanzar** de la propuesta —confirma con tu sesión y queda atada "
            "a su huella—, y mientras no la apruebes no hay nada en cola."
        )
    return None
