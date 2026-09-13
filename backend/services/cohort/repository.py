"""
Persistencia de cohortes congeladas.

# Una escritura, una tabla, una transacción

Crear una cohorte es UN `INSERT` en `cohorts`. No hay tabla de filas, no hay
archivo en disco al lado, no hay segundo paso. Esa es la razón de que no pueda
quedar una cohorte a medias: no existe un estado intermedio en el que la fila ya
esté y el archivo todavía no, ni al revés.

Una tabla por fila llegará cuando las filas tengan estado propio —que es lo que
introduce la ejecución en 5C—. Mientras no lo tengan, partirlas en dos tablas
sólo añade una forma de que la mitad se guarde.

# El archivo NO se lee salvo que se pida

`source_bytes` puede ocupar 8 MB. `list_cohorts` y `get_cohort` seleccionan
columnas EXPLÍCITAS y el BLOB no está entre ellas: nunca sale de SQLite para
pintar un listado. Quien de verdad necesita los bytes —la ejecución de 5C— los
pide por su nombre con `load_cohort_source`.

# Propiedad

Se sigue la convención del producto (`api/routers/evaluation_access.py`): sin
usuario autenticado, el dueño es el usuario `demo`, que es como el escritorio
opera de forma anónima.

Lo que NO se sigue es su respuesta de error. `require_owned_molecule` contesta
403 cuando la molécula es de otro, y un 403 confirma que ese identificador
existe. Aquí una cohorte ajena es indistinguible de una inexistente: las dos
devuelven `None` y el router contesta 404. La diferencia es deliberada y la
paga quien pruebe identificadores al azar.
"""

from __future__ import annotations

import hashlib
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import CohortORM, UserORM
from services.cohort.fingerprint import COHORT_FINGERPRINT_CONTRACT
from services.cohort.schemas import (
    COHORT_PREFLIGHT_SCHEMA_VERSION,
    COHORT_STATUS_READY,
    CohortPreflightResult,
    CohortProvenance,
    CohortStudy,
)

#: Caracteres que sobreviven en el nombre del archivo. Lista blanca, no negra:
#: una lista negra siempre olvida uno, y aquí un olvido acaba imprimiendo el
#: nombre de usuario de alguien dentro de una respuesta que circula.
_NOMBRE_SEGURO = re.compile(r"[^A-Za-z0-9._-]+")


def sanitize_source_filename(nombre: str | None, *, maximo: int = 120) -> str:
    """
    Deja el nombre BASE, saneado. Nunca una ruta.

    Se cortan los separadores de los DOS sistemas (`/` y `\\`) antes de sanear:
    un navegador puede mandar `C:\\Users\\ana\\cohorte.csv`, y guardar eso
    publicaría el nombre de usuario de Ana en cada respuesta que enseñe la
    cohorte. El `..` se disuelve en el mismo paso porque no sobrevive a la lista
    blanca como componente de ruta.
    """
    crudo = (nombre or "").replace("\\", "/").split("/")[-1].strip()
    limpio = _NOMBRE_SEGURO.sub("-", crudo)
    limpio = re.sub(r"\.{2,}", ".", limpio)
    limpio = re.sub(r"-{2,}", "-", limpio).strip("-._")
    return (limpio or "cohorte")[:maximo]


def sha256_of(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def build_provenance(created_at: datetime) -> CohortProvenance:
    """
    Con qué se congeló. **Lo que no se puede leer, no se escribe.**

    Las versiones se leen del runtime en este instante, no de una constante
    copiada a mano. Si una no está disponible el campo se omite: un
    `"desconocida"` se leería después como si fuera un dato.
    """
    version_producto: str | None
    try:
        # Import tardío: `api.main` importa los routers, que importan esto. En
        # tiempo de petición el módulo ya está cargado y esto es un acceso al
        # caché de módulos, no una importación real.
        from api.main import APP_VERSION

        version_producto = str(APP_VERSION)
    except Exception:
        version_producto = None

    version_rdkit: str | None
    try:
        import rdkit

        version_rdkit = str(rdkit.__version__)
    except Exception:
        version_rdkit = None

    return CohortProvenance(
        preflight_contract_version=COHORT_PREFLIGHT_SCHEMA_VERSION,
        fingerprint_contract=COHORT_FINGERPRINT_CONTRACT,
        moldesign_version=version_producto,
        rdkit_version=version_rdkit,
        created_at=created_at.isoformat(),
    )


async def resolve_owner_id(db: AsyncSession, current_user: UserORM | None) -> uuid.UUID:
    """Dueño efectivo. Sin sesión autenticada, el usuario `demo` del escritorio."""
    if current_user is not None:
        return current_user.id
    from db.repository import Repository

    demo = await Repository(db).get_or_create_test_user()
    return demo.id


async def create_cohort(
    db: AsyncSession,
    *,
    study: CohortStudy,
    preflight: CohortPreflightResult,
    source_filename: str | None,
    source_content_type: str | None,
    source_bytes: bytes,
    owner_id: uuid.UUID,
    created_at: datetime,
) -> CohortORM:
    """
    Congela la cohorte. El llamador ya comprobó que el preflight está `ready`.

    No hace `commit`: la transacción la cierra `get_db`, que es quien sabe si el
    resto de la petición terminó bien. Hacer commit aquí dejaría la cohorte
    guardada aunque el endpoint fallara al construir la respuesta.
    """
    from core.database import flush_with_retry

    cohorte = CohortORM(
        id=uuid.uuid4(),
        schema_version=preflight.schema_version,
        name=study.name,
        status=COHORT_STATUS_READY,
        cohort_fingerprint=preflight.cohort_fingerprint,
        source_filename=sanitize_source_filename(source_filename),
        source_content_type=(source_content_type or None),
        source_sha256=sha256_of(source_bytes),
        source_bytes=source_bytes,
        source_size_bytes=len(source_bytes),
        normalized_study_json=study.model_dump(mode="json"),
        preflight_snapshot_json=preflight.model_dump(mode="json"),
        provenance_json=build_provenance(created_at).model_dump(mode="json"),
        user_id=owner_id,
        created_at=created_at,
    )
    db.add(cohorte)
    await flush_with_retry(db)
    return cohorte


#: Columnas del listado. El BLOB NO está: un listado no descarga archivos.
_COLUMNAS_LISTADO = (
    CohortORM.id,
    CohortORM.name,
    CohortORM.status,
    CohortORM.cohort_fingerprint,
    CohortORM.source_filename,
    CohortORM.source_content_type,
    CohortORM.source_sha256,
    CohortORM.source_size_bytes,
    CohortORM.normalized_study_json,
    CohortORM.preflight_snapshot_json,
    CohortORM.created_at,
)

#: Columnas del detalle. Tampoco lleva el BLOB: el detalle describe la cohorte,
#: no la entrega.
_COLUMNAS_DETALLE = (
    *_COLUMNAS_LISTADO,
    CohortORM.schema_version,
    CohortORM.provenance_json,
)


async def list_cohorts(
    db: AsyncSession, *, owner_id: uuid.UUID, limit: int = 50
) -> list[Any]:
    """Cohortes del dueño, de la más reciente a la más antigua. Sin bytes."""
    resultado = await db.execute(
        select(*_COLUMNAS_LISTADO)
        .where(CohortORM.user_id == owner_id)
        .order_by(CohortORM.created_at.desc(), CohortORM.id.desc())
        .limit(limit)
    )
    return list(resultado.all())


async def get_cohort(
    db: AsyncSession, *, cohort_id: uuid.UUID, owner_id: uuid.UUID
) -> Any | None:
    """
    Una cohorte del dueño, o `None`.

    `None` significa las dos cosas —no existe, o no es tuya— y el router no las
    distingue al contestar. Distinguirlas convertiría el endpoint en un oráculo
    de qué identificadores existen en la máquina.
    """
    resultado = await db.execute(
        select(*_COLUMNAS_DETALLE).where(
            CohortORM.id == cohort_id, CohortORM.user_id == owner_id
        )
    )
    return resultado.first()


async def load_cohort_source(
    db: AsyncSession, *, cohort_id: uuid.UUID, owner_id: uuid.UUID
) -> tuple[bytes, str, str] | None:
    """
    Los bytes del archivo original, su nombre saneado y su SHA-256.

    NO tiene endpoint. Existe para la ejecución de 5C, que necesitará el archivo
    tal como se subió, y para poder comprobar en pruebas que lo guardado es
    byte a byte lo que llegó.
    """
    resultado = await db.execute(
        select(
            CohortORM.source_bytes, CohortORM.source_filename, CohortORM.source_sha256
        ).where(CohortORM.id == cohort_id, CohortORM.user_id == owner_id)
    )
    fila = resultado.first()
    if fila is None:
        return None
    return (bytes(fila.source_bytes), fila.source_filename, fila.source_sha256)


def utc_now() -> datetime:
    """Instante de congelación. Un solo sitio, para que no haya dos relojes."""
    return datetime.now(timezone.utc)
