"""La única puerta por la que las herramientas salen a internet.

MOLCHAT-NET-005 puso consentimiento por cuenta y por destino para el **proveedor
de chat**. Las herramientas quedaron detrás de `allow_web`, que es un
interruptor: autorizar «buscar en internet» autorizaba a la vez PubChem, ChEMBL,
RCSB y UniProt, sin decir cuáles, ni hacia qué hosts, ni qué dato sale. Un
interruptor no es un permiso.

Este módulo lo convierte en uno, reutilizando exactamente el mismo mecanismo que
ya usa el proveedor —huella `servicio@host`, almacén por cuenta— para que haya
**una** política de salida y no dos que se desincronizan.

Tres reglas:

* **el destino se declara, no se supone.** Cada servicio dice su host, su
  finalidad y qué datos salen hacia él. Un host que no está en el catálogo no se
  resuelve a favor de enviar: se rechaza;
* **el permiso se ata al host que se mostró.** Si el destino cambia de host, el
  permiso no lo hereda: el destino nuevo es otro destino;
* **hay un modo completamente offline**, y es consultable. `MOLDESIGN_OFFLINE=1`
  niega toda salida aunque haya permiso, para que «este equipo no habla con
  nadie» sea una afirmación comprobable y no una intención.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlparse

from utils.logger import get_logger

log = get_logger(__name__)


class SalidaNoAutorizada(RuntimeError):
    """Se intentó salir a la red sin permiso de esa cuenta para ese destino."""


@dataclass(frozen=True)
class Destino:
    """Un servicio externo, con todo lo que hay que poder enseñar antes de ir."""

    servicio: str
    host: str
    #: Para qué se consulta. Lo lee el investigador antes de autorizar.
    finalidad: str
    #: Qué sale de la máquina hacia allí. Nunca «datos»: qué datos.
    que_sale: str

    @property
    def huella(self) -> str:
        """`servicio@host`. Mover el host cambia la huella, y eso revoca."""
        return f"{self.servicio}@{self.host}"

    def to_dict(self) -> dict[str, str]:
        return {
            "servicio": self.servicio,
            "host": self.host,
            "finalidad": self.finalidad,
            "que_sale": self.que_sale,
            "huella": self.huella,
        }


#: Catálogo de destinos. Añadir uno exige declarar qué sale hacia él, que es
#: justo la pregunta que un interruptor global permite no contestar.
DESTINOS: tuple[Destino, ...] = (
    Destino(
        servicio="pubchem",
        host="pubchem.ncbi.nlm.nih.gov",
        finalidad="propiedades y descripciones de compuestos conocidos",
        que_sale="el nombre o el SMILES del compuesto que se consulta",
    ),
    Destino(
        servicio="chembl",
        host="www.ebi.ac.uk",
        finalidad="bioactividad medida publicada",
        que_sale="el nombre o el SMILES del compuesto que se consulta",
    ),
    Destino(
        servicio="rcsb",
        host="search.rcsb.org",
        finalidad="búsqueda de estructuras de receptores",
        que_sale="el texto de búsqueda o el PDB ID",
    ),
    Destino(
        servicio="rcsb-datos",
        host="data.rcsb.org",
        finalidad="metadatos de una estructura PDB concreta",
        que_sale="el PDB ID del receptor",
    ),
    Destino(
        servicio="huggingface",
        host="huggingface.co",
        finalidad="buscar y descargar modelos de lenguaje locales",
        que_sale="el texto de búsqueda del modelo, o el identificador del modelo a descargar",
    ),
    Destino(
        servicio="uniprot",
        host="rest.uniprot.org",
        finalidad="identidad y anotación de la proteína",
        que_sale="el identificador o el nombre de la proteína",
    ),
)


def modo_offline() -> bool:
    """¿Está el equipo declarado como incomunicado?

    Es una función y no una constante a propósito: tiene que poder comprobarse
    en el momento, y cambiar sin reiniciar el proceso.
    """
    return os.environ.get("MOLDESIGN_OFFLINE", "").strip() in {"1", "true", "yes"}


def _host_de(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except ValueError:
        return ""


def destino_de_url(url: str) -> Destino | None:
    """El destino declarado para esa URL, o `None` si no está en el catálogo."""
    host = _host_de(url)
    if not host:
        return None
    for destino in DESTINOS:
        if destino.host.lower() == host:
            return destino
    return None


def destino_de_servicio(servicio: str) -> Destino | None:
    for destino in DESTINOS:
        if destino.servicio == servicio:
            return destino
    return None


def permisos_de(user_id: str | None) -> dict[str, dict]:
    """Destinos que esta cuenta autorizó. Nunca hereda: sin cuenta, ninguno."""
    if not user_id:
        return {}
    from services.ai.provider_config_store import cargar_consentimientos

    return cargar_consentimientos(user_id)


def hay_permiso(destino: Destino, user_id: str | None) -> bool:
    return destino.huella in permisos_de(user_id)


def otorgar(servicio: str, user_id: str) -> dict:
    """Registra el permiso de una cuenta para un destino concreto."""
    destino = destino_de_servicio(servicio)
    if destino is None:
        raise SalidaNoAutorizada(
            f"'{servicio}' no es un destino declarado: no se puede autorizar lo "
            "que no dice a dónde va ni qué manda."
        )
    from services.ai.provider_config_store import guardar_consentimiento

    registro = {
        **destino.to_dict(),
        "otorgado_en": datetime.now(timezone.utc).isoformat(),
    }
    guardar_consentimiento(user_id, destino.huella, registro)
    log.info("salida_autorizada", servicio=servicio, host=destino.host)
    return registro


def revocar(servicio: str, user_id: str) -> bool:
    destino = destino_de_servicio(servicio)
    if destino is None:
        return False
    from services.ai.provider_config_store import borrar_consentimientos_de

    # Es por servicio y no por huella a propósito: si el destino cambió de host
    # desde que se autorizó, el permiso viejo tiene que irse igual.
    return bool(borrar_consentimientos_de(user_id, destino.servicio))


def exigir_permiso(url: str, user_id: str | None) -> Destino:
    """Puerta única de salida. Lanza `SalidaNoAutorizada` si no se puede ir.

    El orden importa: primero el modo offline —que manda sobre cualquier
    permiso—, luego que el destino esté declarado, y sólo al final el permiso de
    la cuenta.
    """
    if modo_offline():
        raise SalidaNoAutorizada(
            "El equipo está en modo offline: ninguna herramienta sale a la red, "
            "aunque tenga permiso."
        )

    destino = destino_de_url(url)
    if destino is None:
        raise SalidaNoAutorizada(
            f"El host '{_host_de(url) or url}' no es un destino declarado. La "
            "duda no se resuelve a favor de enviar."
        )

    if not user_id:
        raise SalidaNoAutorizada(
            f"Sin identidad de cuenta no se sale hacia {destino.host}: el "
            "permiso es de alguien, no del proceso."
        )

    if not hay_permiso(destino, user_id):
        raise SalidaNoAutorizada(
            f"Esta cuenta no autorizó {destino.servicio} ({destino.host}). "
            f"Hacia allí saldría: {destino.que_sale}. Finalidad: {destino.finalidad}."
        )

    return destino


def estado_de_destinos(user_id: str | None) -> list[dict]:
    """Lo que la interfaz necesita para preguntar: destino, finalidad y estado."""
    autorizados = permisos_de(user_id)
    return [
        {
            **destino.to_dict(),
            "consentido": destino.huella in autorizados,
            "otorgado_en": autorizados.get(destino.huella, {}).get("otorgado_en"),
        }
        for destino in DESTINOS
    ]
