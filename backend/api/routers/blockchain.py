"""
Blockchain certification router.

Provides endpoints for certifying molecular discoveries on Solana devnet.
"""

import hashlib
import uuid
from typing import Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from fastapi.responses import StreamingResponse

from core.config import get_settings, Settings
from core.database import get_db
from core.models import MoleculeORM, EvaluationResultORM, UserORM
from api.dependencies import get_current_user, get_current_user_optional
# Alias explícito: los endpoints /certify y /verify de este router se llaman
# igual que las funciones importadas de certifier.py. Un `def` de módulo
# rebindea el nombre global en cuanto el módulo se importa, así que sin el
# alias las llamadas internas (líneas más abajo) terminaban resolviendo al
# propio endpoint FastAPI en vez de a la implementación on-chain: certify
# fallaba por firma incompatible y verify se llamaba a sí mismo en bucle
# infinito (RecursionError). Ver auditoría 2026-08-16.
from services.blockchain.certifier import (
    is_solana_public_key,
    verify_certification as verify_certification_onchain,
)
from services.blockchain.pdf_generator import generate_certificate_pdf
from utils.logger import get_logger


router = APIRouter(prefix="/blockchain", tags=["blockchain"])
log = get_logger(__name__)


def _is_solana_wallet(value: Optional[str]) -> bool:
    """Validate a public key without importing a Solana Python SDK."""
    return is_solana_public_key(value)

def _public_author_reference(user: UserORM, requested_wallet: Optional[str]) -> str:
    """Return a public author reference without ever publishing an email."""
    if _is_solana_wallet(requested_wallet):
        return requested_wallet.strip()
    stored_wallet = getattr(user, "solana_wallet_address", None)
    if _is_solana_wallet(stored_wallet):
        return stored_wallet.strip()
    digest = hashlib.sha256(f"moldesign-user:{user.id}".encode("utf-8")).hexdigest()[:24]
    return f"account:{digest}"


def _require_certificate_owner(mol, current_user: Optional[UserORM]):
    """Exige que el certificado sea de quien lo pide. MOLDEX-BE-005.

    Antes esto autorizaba con `mol.user_id != current_user_id and mol.user_id
    != demo_user.id`, y `current_user_id` caía al usuario demo cuando no había
    sesión. Dos agujeros en una línea: cualquier molécula del espacio demo
    quedaba legible por **toda** cuenta y también sin autenticar, y el 403
    confirmaba que el recurso existía.

    El motivo histórico de esa laxitud —«en DESKTOP las moléculas se crean con
    el usuario demo»— ya no aplica: el escritorio inicia sesión solo como
    `Desktop User` (`/auth/desktop-login`), que es una cuenta con identidad
    propia. El espacio demo dejó de ser el invitado real.

    Se responde 404 y no 403, como en BATCH-BE-002: un 403 revela la existencia
    de un dossier ajeno, que ya es información.
    """
    if current_user is None or mol.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Molécula no encontrada")
    return mol


def _score_sellable(evaluation: EvaluationResultORM) -> float:
    """Devuelve el score que puede sellarse, o bloquea la certificación.

    MOLDEX-SCI-002. Ambas rutas escribían `evaluation.total_score or 0.0`. Ese
    idiom confunde dos cosas distintas: un score de `0.0` realmente medido —un
    valor válido del extremo inferior de la escala 0-100— y un score que no
    existe. `BlockchainRecord.total_score` es un `float` obligatorio, así que el
    esquema habría rechazado el `None`; el `or 0.0` lo convertía en un cero
    válido antes de que Pydantic pudiera verlo.

    A diferencia de BATCH-SCI-001 y EVAL-SCI-012, aquí el cero fabricado se
    escribe en una cadena pública con licencia CC0 y timestamp, y no se puede
    corregir después. Por eso se bloquea en vez de degradarse.
    """
    score = getattr(evaluation, "total_score", None)
    if score is None:
        raise HTTPException(
            status_code=400,
            detail=(
                "La corrida no tiene un score total calculado, y un certificado "
                "es irreversible: sellar un valor ausente lo convertiría en una "
                "medida que nadie hizo. Vuelve a evaluar la molécula antes de "
                "certificarla."
            ),
        )
    try:
        return float(score)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=400,
            detail=(
                "El score total de la corrida no es un número interpretable y no "
                "puede sellarse."
            ),
        )


def _valores_del_sello(
    signature: str,
    task_id: Optional[str],
    sealed_score: Optional[float],
) -> dict:
    """Lo que hay que persistir al certificar, no sólo la firma.

    MOLDEX-SCI-001. `blockchain_tx_id` vive en `evaluation_results`, que es la
    proyección mutable de la última evaluación de la molécula: al reevaluarla,
    `upsert_evaluation_result` reescribe score, afinidad, receptor y semilla, y
    el sello se queda pegado a cifras que no son las que atestiguó.

    Guardando junto a la firma **qué corrida** se certificó y **qué score** se
    selló, la divergencia deja de ser invisible: Moldex puede compararlo con la
    corrida vigente y decirlo.
    """
    return {
        "blockchain_tx_id": signature,
        "certified_task_id": task_id,
        "certified_total_score": sealed_score,
    }


class CertificationRequest(BaseModel):
    molecule_id: uuid.UUID
    user_wallet: Optional[str] = None


@router.get("/health")
async def blockchain_health(settings: Settings = Depends(get_settings)):
    """
    Returns Solana connection health status for the frontend.
    The frontend uses this to show indicator in CertificationModal.
    """
    from services.blockchain.certifier import get_certifier
    certifier = await get_certifier()
    status = await certifier.health()
    return {
        **status,
        "rpc_url": settings.solana_rpc_url,
        "network": status["network"],
    }



@router.post("/certify", status_code=409, deprecated=True)
async def certify_molecule(
    request: CertificationRequest,
    current_user: UserORM = Depends(get_current_user),
):
    """Legacy server-signing endpoint retained as an explicit, honest refusal.

    The alpha never stores an institutional private key. Transactions are
    prepared by /prepare and signed client-side by a wallet or by the
    desktop-only ephemeral devnet identity.
    """
    raise HTTPException(
        status_code=409,
        detail=(
            "La firma institucional fue retirada. Usa el registro experimental "
            "de Solana devnet desde la ventana de certificación."
        ),
    )

@router.get("/certify/{molecule_id}/prepare")
async def prepare_certification(
    molecule_id: uuid.UUID,
    user_wallet: str,
    current_user: UserORM = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Prepares the memo string for a client-side Web3 certification.
    """
    stmt = select(MoleculeORM).options(selectinload(MoleculeORM.target)).where(MoleculeORM.id == molecule_id)
    mol = (await db.execute(stmt)).scalar_one_or_none()
    if not mol:
        raise HTTPException(status_code=404, detail="Molécula no encontrada")

    if mol.user_id and mol.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="No tienes permiso")

    if not _is_solana_wallet(user_wallet):
        raise HTTPException(status_code=422, detail="La direccion de wallet de Solana no es valida")

    evaluation = await db.scalar(select(EvaluationResultORM).where(EvaluationResultORM.molecule_id == molecule_id))
    if not evaluation:
        raise HTTPException(status_code=400, detail="Molécula no evaluada")

    if evaluation.blockchain_tx_id:
        return {"already_certified": True, "signature": evaluation.blockchain_tx_id}

    # DOC 71, DEFECTO E3. Aqui decia `datetime.utcnow().isoformat()`, que
    # produce `2026-09-02T20:22:57.261446`: una marca SIN zona horaria. En un
    # certificado eso es peor que en cualquier otro sitio, porque el documento
    # existe para poder reconciliarse con otras fuentes, y una hora sin huso no
    # se puede comparar con nada sin adivinar. `utcnow()` ademas devuelve un
    # datetime NAIVE -esta deprecado en 3.12 justo por esto-.
    #
    # `datetime.now(timezone.utc)` da `...+00:00`. Los memos ya sellados no
    # cambian: quedan en la cadena tal como se emitieron, y este formato aplica
    # a las certificaciones nuevas.
    timestamp_iso = datetime.now(timezone.utc).isoformat()
    total_score = _score_sellable(evaluation)
    target_pdb_id = mol.target.pdb_id if mol.target else "7E2Y"

    memo = f"MolDesign-v1|CC0|{mol.smiles_hash}|{total_score:.2f}|{target_pdb_id}|{timestamp_iso}|{user_wallet}"

    return {
        "already_certified": False,
        "memo": memo
    }

class LinkRequest(BaseModel):
    molecule_id: uuid.UUID
    signature: str

@router.post("/certify/link")
async def link_certification(
    request: LinkRequest,
    current_user: UserORM = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Verifies a client-signed transaction and links it to the molecule.
    """
    stmt = select(MoleculeORM).options(selectinload(MoleculeORM.target)).where(MoleculeORM.id == request.molecule_id)
    mol = (await db.execute(stmt)).scalar_one_or_none()
    if not mol:
        raise HTTPException(status_code=404, detail="Molecula no encontrada")

    if mol.user_id and mol.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="No tienes permiso")

    # 1. Verify transaction on blockchain
    record = await verify_certification_onchain(request.signature)
    if not record:
        raise HTTPException(status_code=400, detail="Firma inválida o no encontrada en la blockchain")

    # 2. Ensure the memo matches the molecule's smiles hash
    if record.smiles_hash != mol.smiles_hash:
        raise HTTPException(status_code=400, detail="La transacción no corresponde a esta molécula")

    # A matching hash is not enough: the public memo must describe the exact
    # target and score that are about to be linked to this local evaluation.
    evaluation = await db.scalar(
        select(EvaluationResultORM).where(EvaluationResultORM.molecule_id == request.molecule_id)
    )
    if not evaluation:
        raise HTTPException(status_code=400, detail="Molécula no evaluada")
    expected_score = _score_sellable(evaluation)
    expected_target = mol.target.pdb_id if getattr(mol, "target", None) else "7E2Y"
    if abs(record.total_score - round(expected_score, 2)) > 1e-9 or record.target_pdb_id != expected_target:
        raise HTTPException(
            status_code=400,
            detail="La transacción no corresponde a la corrida y target actuales",
        )

    # A sovereign signature is the only event that links a public wallet to
    # an account. Institutional certifications use a pseudonymous account id.
    if _is_solana_wallet(record.user_wallet):
        current_user.solana_wallet_address = record.user_wallet

    # 3. Link ONLY to this molecule's evaluation
    #    Se ancla el sello a su corrida (MOLDEX-SCI-001). Aquí el score sellado
    #    se toma del memo verificado en la cadena, no de la fila local: el memo
    #    es lo que realmente quedó atestiguado, y la fila puede haber cambiado
    #    entre la firma y este enlace.
    evaluacion_sellada = await db.scalar(
        select(EvaluationResultORM).where(
            EvaluationResultORM.molecule_id == request.molecule_id
        )
    )
    stmt_update = (
        update(EvaluationResultORM)
        .where(EvaluationResultORM.molecule_id == request.molecule_id)
        .values(
            **_valores_del_sello(
                signature=request.signature,
                task_id=getattr(evaluacion_sellada, "task_id", None),
                sealed_score=record.total_score,
            )
        )
    )
    await db.execute(stmt_update)

    mol.is_saved = True
    if mol.user_id is None:
        mol.user_id = current_user.id

    await db.commit()

    return {"success": True, "signature": request.signature}


@router.get("/verify/{signature}")
async def verify_certification(signature: str):
    """
    Verify a certification transaction on the blockchain.

    Returns the certified record if found and valid.
    """
    record = await verify_certification_onchain(signature)

    if record is None:
        raise HTTPException(status_code=404, detail="Certification not found or invalid")

    return {
        "signature": signature,
        "record": record.dict(),
        "status": "verified",
        "message": "Certification verified on Solana blockchain"
    }

async def _generate_certificate_data(
    molecule_id: uuid.UUID,
    current_user: UserORM | None,
    db: AsyncSession
):
    stmt = select(MoleculeORM).options(selectinload(MoleculeORM.target)).where(MoleculeORM.id == molecule_id)
    result = await db.execute(stmt)
    mol = result.scalar_one_or_none()

    if not mol:
        raise HTTPException(status_code=404, detail="Molécula no encontrada")

    _require_certificate_owner(mol, current_user)

    evaluation = await db.scalar(
        select(EvaluationResultORM).where(EvaluationResultORM.molecule_id == molecule_id)
    )
    if not evaluation:
        raise HTTPException(status_code=400, detail="La molécula no ha sido evaluada")

    target_name = mol.target.name if mol.target else "7E2Y (5-HT1A)"

    # Download SDF poses and Receptor PDB content for advanced PDF generation
    pose_sdf_content = None
    if evaluation.poses_file_path:
        try:
            from utils.local_storage import read_text
            pose_sdf_content = await read_text(evaluation.poses_file_path)
        except Exception:
            pass

    receptor_pdb_content = None
    if mol.target:
        import os
        pdb_id = mol.target.pdb_id.upper()
        # Try local paths first
        from services.docking.preparer import get_target_pdb_path
        possible_paths = [
            get_target_pdb_path(pdb_id),
            f"/data/targets/{pdb_id}.pdb",
            f"data/targets/{pdb_id}.pdb",
            f"data/{pdb_id.lower()}/receptor.pdb",
            f"data/{pdb_id.upper()}/receptor.pdb",
        ]
        for path in possible_paths:
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8", errors="replace") as f:
                        receptor_pdb_content = f.read()
                    break
                except Exception:
                    pass
        # Fallback to local storage
        if not receptor_pdb_content:
            try:
                from utils.file_handlers import StoragePath
                from utils.local_storage import read_text
                raw_path = StoragePath.target_raw(pdb_id)
                receptor_pdb_content = await read_text(raw_path)
            except Exception:
                pass

    # ── El render NO puede bloquear el bucle de eventos ─────────────────────
    #
    # DOC 71, DEFECTO E1. `generate_certificate_pdf` es SINCRONA -ReportLab
    # componiendo un documento con tablas, imagenes SVG y un apendice- y se
    # llamaba directamente desde este `async def`. En un backend de escritorio
    # de un solo proceso eso congela TODO mientras dura: el sondeo del pipeline,
    # el catalogo, la propia peticion gemela del certificado.
    #
    # La vista previa lo notaba y la descarga no por una razon de forma: la
    # descarga la dispara un click y la vista previa se monta sola, y en
    # desarrollo React invoca el efecto dos veces, asi que salian DOS
    # generaciones simultaneas del mismo documento. Bloqueo doble, y el WebView
    # cortando la peticion en vuelo: `Failed to fetch`.
    #
    # `asyncio.to_thread` es lo que ya usa este repositorio para lo mismo -ver
    # `api/main.py` con el gestor de modelos y la siembra de estructuras-.
    import asyncio

    pdf_buf = await asyncio.to_thread(
        generate_certificate_pdf,
        mol,
        evaluation,
        target_name,
        pose_sdf_content=pose_sdf_content,
        receptor_pdb_content=receptor_pdb_content,
    )

    pdb_id = mol.target.pdb_id.upper() if mol.target else "UNKNOWN"
    mol_hash = mol.smiles_hash[:8] if mol.smiles_hash else "nohash"
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    dynamic_filename = f"MolDesign_Dossier_{pdb_id}_{mol_hash}_{date_str}.pdf"

    return pdf_buf, dynamic_filename


@router.get("/certificate/{molecule_id}")
async def get_certificate(
    molecule_id: uuid.UUID,
    current_user: UserORM | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db)
):
    """
    Generates and downloads a PDF certificate for the certified molecule.
    """
    pdf_buf, dynamic_filename = await _generate_certificate_data(molecule_id, current_user, db)
    return StreamingResponse(
        pdf_buf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename={dynamic_filename}",
            "Access-Control-Expose-Headers": "Content-Disposition"
        }
    )


@router.get("/certificate/{molecule_id}/preview")
async def get_certificate_preview(
    molecule_id: uuid.UUID,
    current_user: UserORM | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db)
):
    """
    Generates and returns a PDF certificate inline for the viewer.
    """
    pdf_buf, dynamic_filename = await _generate_certificate_data(molecule_id, current_user, db)
    return StreamingResponse(
        pdf_buf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename={dynamic_filename}",
            "Access-Control-Expose-Headers": "Content-Disposition"
        }
    )
