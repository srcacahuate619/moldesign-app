"""
Superficie HTTP de la cohorte: comprobar, congelar, consultar.

# Las dos cosas que hace esta ruta, y por qué son dos

    POST /evaluation/cohorts/preflight   un DICTAMEN. Se calcula y se tira.
    POST /evaluation/cohorts             un REGISTRO. Se congela y sobrevive.

El dictamen es una función pura del archivo y del estudio: repítelo mañana y da
lo mismo, siempre que no cambie la versión del validador. El registro tiene que
seguir diciendo lo mismo **aunque esa versión cambie**, porque es lo que alguien
aceptó. De ahí que crear una cohorte guarde el veredicto entero y no sólo la
receta para recalcularlo.

# Por qué una ruta nueva y no `POST /evaluation/batch`

`/evaluation/batch` **arranca un cribado**: parsea, filtra, crea un registro en
memoria y lanza `asyncio.create_task`. No hay forma de preguntarle «¿qué
entraría?» sin que entre, ni de guardar la respuesta.

Ninguna ruta de este archivo ejecuta docking, llama a ML, lanza tareas de fondo
ni devuelve ningún score. Las rutas históricas de Batch siguen intactas: esta
superficie no las sustituye todavía.

# Por qué multipart y no JSON

Las moléculas llegan como archivo —CSV, Excel, SDF, SMILES— y la definición
científica como JSON en un campo de formulario. Meter el archivo dentro del JSON
obligaría a codificarlo en base64 y a duplicar en memoria un contenido que ya
viene por streaming.

# El resultado NUNCA llega del cliente

Crear una cohorte recalcula el preflight desde el archivo y el estudio. El
cliente manda `expected_fingerprint` —lo que él cree haber aceptado— y el
servidor compara. Si aceptáramos un `CohortPreflightResult` enviado por el
cliente, cualquiera podría congelar una cohorte que declara 500 moléculas
elegibles a partir de un archivo vacío, y el registro dejaría de ser evidencia
de nada.

# Qué se rechaza en la puerta y qué se declara en el resultado

    422  lo que impide siquiera formular la cohorte: `study` que no es JSON,
         receptor `ALL`, campo desconocido, flotante no finito, tamaño fuera de
         los límites del producto, `expected_fingerprint` con otra forma.
    409  el fingerprint recalculado no es el que el cliente aceptó.
    404  la cohorte no existe **o no es tuya**. No se distinguen: ver
         `services/cohort/repository.py`.

`/preflight` DECLARA todo lo demás con 200 —un archivo ilegible, una columna
ausente, cero elegibles—: eso sí es una cohorte, una que no se puede ejecutar, y
el cliente necesita verla entera para arreglarla. `POST /cohorts` no la congela:
una cohorte bloqueada no es una entrada ejecutable y guardarla sólo produciría un
registro que nadie puede usar.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user_optional
from services.targets.access import get_target_for_user
from core.database import get_db
from core.models import UserORM
from db.repository import Repository
from services.cohort import repository as cohort_repo
from services.cohort.parser import ParsedFile, read_cohort_file
from services.cohort.preflight import build_cohort_preflight
from services.cohort.schemas import (
    FINGERPRINT_PATTERN,
    MAX_COHORT_FILE_BYTES,
    MAX_COHORT_ROWS,
    CohortListItem,
    CohortPreflightResult,
    CohortProvenance,
    CohortRecord,
    CohortSourceFile,
    CohortStudy,
)
from services.cohort.taxonomy import READY
from utils.logger import get_logger

log = get_logger(__name__)
router = APIRouter(prefix="/cohorts", tags=["Cohortes"])


def _rechazar_constante(nombre: str) -> float:
    """
    `json.loads` acepta `NaN`, `Infinity` y `-Infinity` por defecto.

    Ninguno es JSON válido y ninguno describe una caja, una exhaustividad ni
    una semilla. Se cortan aquí, antes de que pydantic los vea, para poder
    decir exactamente cuál llegó.
    """
    raise ValueError(
        f"`{nombre}` no es un número JSON válido. La configuración de una cohorte no "
        "admite valores no finitos."
    )


def _detalle(error: ValidationError) -> list[dict]:
    """Errores de validación en la forma que FastAPI ya devuelve en otras rutas."""
    return [
        {
            "loc": ["body", "study", *[str(parte) for parte in fallo.get("loc", ())]],
            "msg": fallo.get("msg", ""),
            "type": fallo.get("type", ""),
        }
        for fallo in error.errors()
    ]


def _leer_estudio(study: str) -> CohortStudy:
    try:
        crudo = json.loads(study, parse_constant=_rechazar_constante)
    except ValueError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"`study` no es un JSON válido: {exc}",
        ) from exc
    try:
        return CohortStudy.model_validate(crudo)
    except ValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, _detalle(exc)) from exc


async def _leer_archivo(file: UploadFile) -> tuple[bytes, ParsedFile]:
    """
    Bytes y lectura, con los límites aplicados ANTES de tocar química.

    El orden importa: parsear es barato y canonicalizar 20 000 moléculas no lo
    es. El tope de filas se comprueba sobre la lectura cruda para no pagar el
    trabajo de una cohorte que se va a rechazar igual.
    """
    contenido = await file.read()
    if len(contenido) > MAX_COHORT_FILE_BYTES:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"El archivo supera el límite de {MAX_COHORT_FILE_BYTES // (1024 * 1024)} MB.",
        )

    lectura = read_cohort_file(file.filename or "", contenido)
    if len(lectura.rows) > MAX_COHORT_ROWS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            (
                f"La cohorte declara {len(lectura.rows)} filas y el límite del producto es "
                f"{MAX_COHORT_ROWS}. Divídela en cohortes comparables en lugar de recortarla "
                "en silencio."
            ),
        )
    return contenido, lectura


def _fuente(fila: Any) -> CohortSourceFile:
    return CohortSourceFile(
        filename=fila.source_filename,
        content_type=fila.source_content_type,
        sha256=fila.source_sha256,
        size_bytes=fila.source_size_bytes,
    )


def _instante(valor: datetime | None) -> str:
    """
    ISO 8601 en UTC. SQLite devuelve el `datetime` sin zona: se le repone.

    No es cosmética. Un `created_at` sin zona se lee como hora local en la mitad
    de los clientes, y una cohorte congelada a las 23:30 UTC aparecería creada
    «mañana» o «ayer» según quién la mire.
    """
    if valor is None:
        return ""
    if valor.tzinfo is None:
        return valor.replace(tzinfo=timezone.utc).isoformat()
    return valor.astimezone(timezone.utc).isoformat()


def _snapshot(fila: Any) -> CohortPreflightResult:
    """
    El veredicto congelado, revalidado contra el contrato de HOY.

    Si un snapshot guardado ya no encaja, se dice —409— en vez de devolverlo a
    medias. Una cohorte que se congeló con un contrato que este build no sabe
    leer no se puede seguir presentando como si la entendiéramos.
    """
    try:
        return CohortPreflightResult.model_validate(fila.preflight_snapshot_json)
    except ValidationError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            (
                "Esta cohorte se congeló con una versión del contrato de comprobación "
                "previa que este build ya no sabe leer. No se devuelve a medias."
            ),
        ) from exc


@router.post(
    "/preflight",
    summary="Comprobación previa de una cohorte (no ejecuta docking ni la persiste)",
    response_model=CohortPreflightResult,
)
async def cohort_preflight(
    file: UploadFile = File(..., description="CSV, Excel, SDF o SMILES/TXT con las moléculas."),
    study: str = Form(..., description="`CohortStudy` v1 serializado como JSON."),
    current_user: UserORM | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> CohortPreflightResult:
    """
    Analiza y normaliza una cohorte sin ejecutarla y sin guardarla.

    Superar esta comprobación **no predice unión ni calidad farmacológica**: no
    se ha calculado nada todavía. Sólo dice que estas entradas se pueden leer y
    que esta configuración se puede aplicar a todas por igual.
    """
    definicion = _leer_estudio(study)
    if definicion.receptor.pdb_id.startswith("USR_"):
        await get_target_for_user(
            Repository(db), definicion.receptor.pdb_id, current_user, allow_missing=True
        )
    contenido, lectura = await _leer_archivo(file)

    resultado = build_cohort_preflight(
        study=definicion,
        filename=file.filename or "",
        content=contenido,
        generated_at=datetime.now(timezone.utc),
        parsed=lectura,
    )

    log.info(
        "cohort_preflight",
        receptor=definicion.receptor.pdb_id,
        formato=lectura.format,
        decision=resultado.decision,
        total_rows=resultado.summary.total_rows,
        eligible_rows=resultado.summary.eligible_rows,
        fingerprint=resultado.cohort_fingerprint,
    )
    return resultado


@router.post(
    "",
    summary="Congelar una cohorte comprobada (no ejecuta nada)",
    response_model=CohortRecord,
    status_code=status.HTTP_201_CREATED,
)
async def create_cohort(
    file: UploadFile = File(..., description="El MISMO archivo que se comprobó."),
    study: str = Form(..., description="El MISMO `CohortStudy` v1 que se comprobó."),
    expected_fingerprint: str = Form(
        ..., description="El `cohort_fingerprint` que devolvió la comprobación previa."
    ),
    current_user: UserORM | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> CohortRecord:
    """
    Acepta una comprobación previa y la congela como cohorte durable.

    Lo que queda congelado: la definición normalizada, el veredicto entero —con
    sus filas inválidas y duplicadas—, el archivo original y su SHA-256. Lo que
    NO ocurre: ningún cálculo científico. `ready` sigue significando lo mismo
    que en la comprobación previa —entrada ejecutable— y no hay todavía ninguna
    evidencia de docking.
    """
    # La forma de la huella se comprueba primero: es lo más barato y una huella
    # con otra forma no puede coincidir con ninguna que este producto emita.
    esperada = (expected_fingerprint or "").strip()
    if not FINGERPRINT_PATTERN.match(esperada):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            (
                "`expected_fingerprint` tiene que ser el `cohort_fingerprint` que devolvió "
                "la comprobación previa, con la forma `sha256:<64 hexadecimales>`."
            ),
        )

    definicion = _leer_estudio(study)
    if definicion.receptor.pdb_id.startswith("USR_"):
        await get_target_for_user(
            Repository(db), definicion.receptor.pdb_id, current_user, allow_missing=True
        )
    contenido, lectura = await _leer_archivo(file)
    ahora = cohort_repo.utc_now()

    # SIEMPRE se recalcula. Nunca se acepta un resultado del cliente.
    resultado = build_cohort_preflight(
        study=definicion,
        filename=file.filename or "",
        content=contenido,
        generated_at=ahora,
        parsed=lectura,
    )

    # La identidad se comprueba antes que el veredicto: si el archivo o el
    # estudio no son los que se enseñaron, decirlo es más útil que explicar por
    # qué está bloqueada una cohorte que el usuario nunca vio.
    if resultado.cohort_fingerprint != esperada:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {
                "message": (
                    "El archivo o el estudio no son los que produjeron la comprobación "
                    "previa que aceptaste. No se congela una cohorte distinta de la que "
                    "se te enseñó: vuelve a comprobarla."
                ),
                "expected_fingerprint": esperada,
                "computed_fingerprint": resultado.cohort_fingerprint,
            },
        )

    if resultado.decision != READY:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            {
                "message": (
                    "La cohorte está bloqueada y no se guarda: no es una entrada "
                    "ejecutable. Corrige los bloqueantes y vuelve a comprobarla."
                ),
                "decision": resultado.decision,
                "blockers": resultado.blockers,
            },
        )

    owner_id = await cohort_repo.resolve_owner_id(db, current_user)
    cohorte = await cohort_repo.create_cohort(
        db,
        study=definicion,
        preflight=resultado,
        source_filename=file.filename,
        source_content_type=file.content_type,
        source_bytes=contenido,
        owner_id=owner_id,
        created_at=ahora,
    )

    # Se registra la IDENTIDAD, nunca el contenido molecular: un log con 500
    # SMILES es una copia del archivo en un sitio que nadie audita.
    log.info(
        "cohort_created",
        cohort_id=str(cohorte.id),
        receptor=definicion.receptor.pdb_id,
        fingerprint=resultado.cohort_fingerprint,
        source_sha256=cohorte.source_sha256,
        total_rows=resultado.summary.total_rows,
        eligible_rows=resultado.summary.eligible_rows,
    )

    return CohortRecord(
        id=cohorte.id,
        schema_version=cohorte.schema_version,
        name=cohorte.name,
        status=cohorte.status,
        cohort_fingerprint=cohorte.cohort_fingerprint,
        created_at=_instante(ahora),
        source=CohortSourceFile(
            filename=cohorte.source_filename,
            content_type=cohorte.source_content_type,
            sha256=cohorte.source_sha256,
            size_bytes=cohorte.source_size_bytes,
        ),
        provenance=CohortProvenance.model_validate(cohorte.provenance_json),
        preflight=resultado,
    )


@router.get(
    "",
    summary="Cohortes congeladas (resumen: sin filas y sin archivo)",
    response_model=list[CohortListItem],
)
async def list_cohorts(
    limit: int = Query(50, ge=1, le=200),
    current_user: UserORM | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> list[CohortListItem]:
    """
    Las cohortes de quien pregunta, de la más reciente a la más antigua.

    Sin filas y sin bytes: este listado contesta «¿qué cohortes tengo?», y
    contestarlo con 500 filas por cohorte lo convertiría en una descarga.
    """
    owner_id = await cohort_repo.resolve_owner_id(db, current_user)
    filas = await cohort_repo.list_cohorts(db, owner_id=owner_id, limit=limit)

    listado: list[CohortListItem] = []
    for fila in filas:
        estudio = fila.normalized_study_json or {}
        receptor = (estudio.get("receptor") or {}).get("pdb_id", "")
        motor = (estudio.get("config") or {}).get("docking_engine", "")
        # Sólo el resumen del snapshot. Las filas se quedan en la base.
        resumen = _snapshot(fila).summary
        listado.append(
            CohortListItem(
                id=fila.id,
                name=fila.name,
                status=fila.status,
                cohort_fingerprint=fila.cohort_fingerprint,
                receptor_pdb_id=receptor,
                docking_engine=motor,
                created_at=_instante(fila.created_at),
                source=_fuente(fila),
                summary=resumen,
            )
        )
    return listado


@router.get(
    "/{cohort_id}",
    summary="Una cohorte congelada: definición, snapshot, resumen y filas",
    response_model=CohortRecord,
)
async def get_cohort(
    cohort_id: uuid.UUID,
    current_user: UserORM | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> CohortRecord:
    """
    Devuelve la cohorte entera menos los bytes del archivo.

    Se publica su SHA-256 para poder cotejarla contra el archivo que uno tenga;
    entregar el contenido es otra operación y no un efecto secundario de mirar.
    """
    owner_id = await cohort_repo.resolve_owner_id(db, current_user)
    fila = await cohort_repo.get_cohort(db, cohort_id=cohort_id, owner_id=owner_id)
    if fila is None:
        # Inexistente y ajena contestan lo MISMO. Un 403 confirmaría que ese
        # identificador existe en esta máquina.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No existe la cohorte solicitada.")

    return CohortRecord(
        id=fila.id,
        schema_version=fila.schema_version,
        name=fila.name,
        status=fila.status,
        cohort_fingerprint=fila.cohort_fingerprint,
        created_at=_instante(fila.created_at),
        source=_fuente(fila),
        provenance=CohortProvenance.model_validate(fila.provenance_json),
        preflight=_snapshot(fila),
    )
