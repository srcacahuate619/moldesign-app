"""MOLCHAT-NET-005 — consentimiento por cuenta antes de salir de la máquina.

Hasta aquí no existía ninguna puerta: si había un proveedor remoto configurado,
el turno se enviaba. Con él iba el contexto de caso y molécula, que es el trabajo
del investigador, no sólo el texto del chat.

Dos ideas sostienen este módulo:

**El destino se calcula, no se supone.** Un proveedor no es remoto por su nombre:
`ollama` apuntado al servidor de otra persona sale de la máquina, y un
`openai` apuntado a un `llama.cpp` en `localhost` no. Lo que decide es el host
del destino resuelto **para esa cuenta** (D-09). Un host desconocido se trata
como remoto: la duda no se resuelve a favor de enviar.

**El consentimiento es de una cuenta para un destino concreto.** Se otorga a la
huella `proveedor@host`, así que cambiar el `base_url` no lo hereda: el destino
nuevo es otro destino y hay que volver a autorizarlo. Eso es lo que cierra la
mitad que MOLCHAT-BE-003 dejó abierta —el cambio de destino dejaba de ser
invisible— sin depender de que la interfaz se acuerde de avisar.

Y por la misma razón por la que las conversaciones heredadas no reciben dueño
(D-07), **el consentimiento no se hereda nunca**: darlo por otorgado sería
afirmar que alguien aceptó algo que nadie comprobó.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from utils.logger import get_logger

log = get_logger(__name__)

#: Proveedores cuyo destino no depende de `base_url`: hablan siempre con su API.
_HOSTS_FIJOS = {
    "claude": "api.anthropic.com",
    "gemini": "generativelanguage.googleapis.com",
}

#: El motor que corre dentro de esta máquina. No hay red que consentir.
_PROVEEDOR_LOCAL = "local"

#: Sólo estos hosts son «esta máquina». Una IP de la red local **no** lo es:
#: es otra computadora, y los datos salen igual.
_HOSTS_DE_ESTA_MAQUINA = {"localhost", "127.0.0.1", "::1", "[::1]", "0.0.0.0"}


@dataclass(frozen=True)
class Destino:
    """A dónde van los datos de un turno, y si eso sale de la máquina."""

    provider_id: str
    host: str
    url: str
    es_remoto: bool

    @property
    def huella(self) -> str:
        """Identidad del destino. El consentimiento se otorga a esto."""
        return f"{self.provider_id}@{self.host}"

    def como_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "host": self.host,
            "url": self.url,
            "es_remoto": self.es_remoto,
            "huella": self.huella,
        }


def es_host_de_esta_maquina(host: str) -> bool:
    return host.strip().lower() in _HOSTS_DE_ESTA_MAQUINA


def destino_de(provider: Any) -> Destino:
    """Calcula el destino real de un proveedor ya resuelto para una cuenta."""
    pid = getattr(provider, "id", "") or ""

    if pid == _PROVEEDOR_LOCAL:
        return Destino(
            provider_id=pid,
            host="",
            url="en esta máquina",
            es_remoto=False,
        )

    if pid in _HOSTS_FIJOS:
        host = _HOSTS_FIJOS[pid]
        return Destino(provider_id=pid, host=host, url=f"https://{host}", es_remoto=True)

    url = (getattr(getattr(provider, "config", None), "base_url", "") or "").strip()
    if not url:
        # Sin destino declarado no se puede afirmar que sea local.
        return Destino(provider_id=pid, host="(sin declarar)", url="", es_remoto=True)

    host = urlparse(url).hostname or "(sin declarar)"
    return Destino(
        provider_id=pid,
        host=host,
        url=url,
        es_remoto=not es_host_de_esta_maquina(host),
    )


def destino_propuesto(provider_id: str, base_url: str | None) -> Destino:
    """El destino que tendría un proveedor si se le aplicara ese `base_url`.

    Se calcula sin construir el proveedor porque hace falta **antes** de guardar
    nada: es lo que permite rechazar un cambio de destino no confirmado
    (MOLCHAT-BE-003) en vez de detectarlo después.
    """

    class _Propuesta:
        id = provider_id

        class config:  # noqa: D106 - sólo transporta el base_url
            pass

    propuesta = _Propuesta()
    propuesta.config.base_url = (base_url or "").strip()
    return destino_de(propuesta)


# ── Otorgar, comprobar y revocar ─────────────────────────────────────────


def hay_consentimiento(destino: Destino, user_id: str | None) -> bool:
    """¿Esta cuenta autorizó **este** destino?

    Un destino que no sale de la máquina no necesita autorización: el camino
    local tiene que ser inequívoco y sin fricción, que es lo que pide el §8.
    """
    if not destino.es_remoto:
        return True
    if not user_id:
        return False

    from services.ai.provider_config_store import cargar_consentimientos

    return destino.huella in cargar_consentimientos(user_id)


def otorgar(destino: Destino, user_id: str) -> dict[str, Any]:
    """Registra el consentimiento de una cuenta para un destino."""
    from services.ai.provider_config_store import guardar_consentimiento

    registro = {
        "provider_id": destino.provider_id,
        "host": destino.host,
        "url": destino.url,
        "otorgado_en": datetime.now(timezone.utc).isoformat(),
    }
    guardar_consentimiento(user_id, destino.huella, registro)
    log.info("consentimiento_otorgado", provider_id=destino.provider_id, host=destino.host)
    return registro


def revocar(provider_id: str, user_id: str) -> bool:
    """Retira el consentimiento de una cuenta para un proveedor.

    Revocar es por proveedor, no por huella: si el destino cambió, lo que el
    investigador quiere retirar es «no mandes nada más por ahí».
    """
    from services.ai.provider_config_store import borrar_consentimientos_de

    retirados = borrar_consentimientos_de(user_id, provider_id)
    if retirados:
        log.info("consentimiento_revocado", provider_id=provider_id, huellas=retirados)
    return bool(retirados)


def mensaje_de_falta(destino: Destino) -> str:
    """Lo que se le dice al investigador en vez de enviar el turno.

    Tiene que decir a dónde iba, qué iba y cómo seguir: un error accionable, no
    un «no disponible».
    """
    return (
        f"Este turno saldría de tu máquina hacia {destino.host}, y con él el "
        "contexto de caso y molécula de la conversación. No lo envié: esta "
        "cuenta todavía no autorizó ese destino. Autorizalo en Opciones > "
        "Intérprete IA, o elegí el motor local, que no sale de la máquina."
    )


def motivo_de_bloqueo(destino: Destino, user_id: str | None) -> str:
    """Por qué **no** se puede salir hacia ese destino ahora, o `""` si se puede.

    Es la puerta; `hay_consentimiento` es sólo una de las dos preguntas que la
    componen. La otra es el modo offline, y el orden entre ellas importa: el
    equipo declarado incomunicado manda sobre cualquier autorización, igual que
    en `red.exigir_permiso`.

    Estaba sin cerrar. `red.py` documenta `MOLDESIGN_OFFLINE=1` como «niega toda
    salida aunque haya permiso, para que 'este equipo no habla con nadie' sea
    una afirmación comprobable», y `/ai/consent/red` lo publica — pero la puerta
    del proveedor de chat nunca lo miraba. Con el modo activado y un proveedor
    remoto ya consentido, el turno salía igual: la afirmación valía para las
    herramientas y no para MolChat, que es justo el camino por el que sale el
    trabajo del investigador.
    """
    if not destino.es_remoto:
        return ""

    from services.ai.red import modo_offline

    if modo_offline():
        return (
            f"Este equipo está en modo offline y esto saldría hacia {destino.host}. "
            "No lo envié, aunque el destino esté autorizado: el modo offline manda "
            "sobre el permiso. Usá el motor local, que no sale de la máquina."
        )

    if hay_consentimiento(destino, user_id):
        return ""
    return mensaje_de_falta(destino)


def estado_de_destinos(
    registry: Any, user_id: str, incluir_heredadas: bool = False
) -> list[dict[str, Any]]:
    """Para cada proveedor del catálogo: a dónde iría y si esta cuenta lo autorizó."""
    from services.ai.provider_config_store import cargar_consentimientos

    otorgados = cargar_consentimientos(user_id)
    activo = registry.active_provider_id_for_user(user_id, incluir_heredadas)

    filas = []
    for fila in registry.list_providers(user_id, incluir_heredadas):
        pid = fila["id"]
        provider = registry.resolve_for_user(pid, user_id, incluir_heredadas)
        if provider is None:
            continue
        destino = destino_de(provider)
        registro = otorgados.get(destino.huella)
        filas.append({
            **destino.como_dict(),
            "name": fila["name"],
            "activo": pid == activo,
            "consentido": (not destino.es_remoto) or registro is not None,
            "otorgado_en": (registro or {}).get("otorgado_en"),
        })
    return filas
