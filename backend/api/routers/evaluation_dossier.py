"""
Superficie HTTP del dossier de caso.

# Por qué no cuelga de /blockchain

`/blockchain/certificate/{id}` nació como certificado: un documento que sella
*cuándo* se emitió algo. El dossier responde otra pregunta —*qué evidencia
produjo esta corrida y qué queda sin evaluar*— y depende del CASO, que la ruta
de blockchain no conoce.

Las rutas antiguas se conservan intactas para no romper a quien las use hoy. La
superficie nueva vive bajo `/evaluation/dossier`, junto al resto del ciclo de
evaluación, y recibe la proyección del caso por POST porque el caso vive en el
cliente y no cabe en una URL.

# Autorización

La misma que el resto de `/evaluation`: `require_owned_molecule`. Un dossier
lleva SMILES, poses y procedencia; que su ruta sea nueva no la exime.

# Errores distinguibles

    404  la molécula no existe, o no tiene resultado que documentar
    403  la molécula no es de quien la pide
    409  el caso pide una corrida y el resultado guardado es de otra

El 409 es el que importa: empaquetar en silencio un resultado que pertenece a
otra corrida produciría un dossier que afirma describir algo que no describe, y
eso es peor que no entregar nada.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.dependencies import get_current_user_optional
from api.routers.evaluation_access import require_owned_molecule
from core.database import get_db
from core.models import EvaluationResultORM, EvaluationRunORM, MoleculeORM, UserORM
from db.repository import Repository
from services.dossier.model import Artefacto, build_case_dossier
from services.dossier.package import construir_paquete, raiz_paquete, sanitizar
from services.dossier.pdf import render_dossier_pdf
from services.dossier.schemas import CaseProjection
from services.dossier.taxonomy import Estado
from utils.logger import get_logger

log = get_logger(__name__)
router = APIRouter(prefix="/dossier", tags=["Dossier de caso"])


async def _reunir(
    molecule_id: uuid.UUID,
    projection: CaseProjection,
    current_user: UserORM | None,
    db: AsyncSession,
):
    """
    Recupera molécula, resultado y target, y contrasta la identidad de la corrida.

    Todo lo científico sale de aquí, nunca de la petición: es lo que permite que
    el dossier afirme describir lo que se ejecutó.
    """
    repository = Repository(db)

    await require_owned_molecule(
        repository=repository,
        db=db,
        molecule_id=molecule_id,
        current_user=current_user,
        forbidden_detail="No tienes permiso para exportar el dossier de esta molécula.",
        missing_detail="No existe la molécula solicitada.",
    )

    molecule = await db.scalar(
        select(MoleculeORM).options(selectinload(MoleculeORM.target)).where(MoleculeORM.id == molecule_id)
    )
    if molecule is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No existe la molécula solicitada.")

    declarado = projection.run.task_id if projection.run else None
    corrida = None
    if declarado:
        corrida = await db.scalar(
            select(EvaluationRunORM).where(
                EvaluationRunORM.task_id == str(declarado),
                EvaluationRunORM.molecule_id == molecule_id,
            )
        )
    eval_result = (
        SimpleNamespace(**dict(corrida.snapshot_json or {})) if corrida is not None
        else await db.scalar(
            select(EvaluationResultORM).where(EvaluationResultORM.molecule_id == molecule_id)
        )
    )
    if eval_result is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "La molécula no tiene un resultado de evaluación que documentar.",
        )

    # Identidad de la corrida: se comprueba, no se supone.
    registrado = getattr(eval_result, "celery_task_id", None) or getattr(eval_result, "task_id", None)
    if declarado and registrado and str(declarado) != str(registrado):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            (
                "El caso pide la corrida solicitada y el resultado almacenado pertenece a otra. "
                "No se empaqueta un resultado que no corresponde a la corrida del caso."
            ),
        )

    return molecule, eval_result, getattr(molecule, "target", None)


async def _artefactos(eval_result, target, molecule) -> list[Artefacto]:
    """
    Artefactos reales. Los ausentes se DECLARAN, no se fabrican.

    Se leen sólo por las rutas lógicas del almacenamiento del producto; nunca
    por una ruta que venga de la petición.
    """
    from utils.local_storage import read_text

    artefactos: list[Artefacto] = []

    # ── Poses ────────────────────────────────────────────────────────
    poses_path = getattr(eval_result, "poses_file_path", None)
    contenido_poses = None
    if poses_path:
        try:
            contenido_poses = await read_text(poses_path)
        except Exception as exc:  # archivo borrado, permisos, disco
            log.warning("dossier_poses_no_legibles", error=str(exc))
    artefactos.append(Artefacto(
        rol="outputs",
        nombre="poses.sdf",
        media_type="chemical/x-mdl-sdfile",
        fuente="eval_result.poses_file_path",
        estado=Estado.REGISTRADO if contenido_poses else Estado.NO_DISPONIBLE,
        contenido=contenido_poses.encode("utf-8") if contenido_poses else None,
        razon=None if contenido_poses else (
            "La corrida no conserva el archivo de poses en el almacenamiento local."
        ),
    ))

    # Cada pose conserva su bloque PDBQT exacto. Es especialmente importante
    # para ensemble: el top-K puede mezclar K archivos SDF distintos y, por
    # tanto, no existe un único ``poses.sdf`` que represente la piscina.
    poses_crudas = getattr(eval_result, "docking_poses", None) or []
    archivos_pdbqt: dict[int, str] = {}
    for posicion, pose in enumerate(poses_crudas, start=1):
        rank = (
            pose.get("rank") if isinstance(pose, dict)
            else getattr(pose, "rank", None)
        )
        try:
            rank_entero = int(rank if rank is not None else posicion)
        except (TypeError, ValueError):
            rank_entero = posicion
        bloque = (
            pose.get("pdbqt_block") if isinstance(pose, dict)
            else getattr(pose, "pdbqt_block", None)
        )
        nombre_pose = f"pose_rank_{rank_entero:03d}.pdbqt"
        archivos_pdbqt[rank_entero] = f"outputs/{nombre_pose}"
        artefactos.append(Artefacto(
            rol="outputs",
            nombre=nombre_pose,
            media_type="chemical/x-pdbqt",
            fuente=f"evaluation_results.docking_poses[rank={rank_entero}].pdbqt_block",
            estado=Estado.REGISTRADO if bloque else Estado.NO_DISPONIBLE,
            contenido=(str(bloque).encode("utf-8") if bloque else None),
            razon=None if bloque else (
                "La corrida no conservó el bloque PDBQT exacto de esta pose."
            ),
        ))

    # ── Receptor preparado ───────────────────────────────────────────
    # El almacenamiento por PDB ID es mutable: puede contener una preparacion
    # posterior a la corrida. Incluirla como si fuera el input ejecutado haria
    # el paquete aparentemente reproducible con el receptor equivocado. Solo
    # se incluye una ruta ligada al resultado; mientras el ORM no la persista,
    # la ausencia se declara de forma honesta.
    pdb_id = getattr(target, "pdb_id", None) if target else None
    preparado = None
    receptor_path = getattr(eval_result, "receptor_path", None)
    if receptor_path:
        try:
            preparado = (await read_text(receptor_path)).encode("utf-8")
        except Exception as exc:
            log.warning("dossier_receptor_preparado_no_legible", error=str(exc))
    artefactos.append(Artefacto(
        rol="inputs",
        nombre=f"{sanitizar(pdb_id or 'receptor')}_prepared.pdbqt",
        media_type="chemical/x-pdbqt",
        fuente="eval_result.receptor_path",
        estado=Estado.REGISTRADO if preparado else Estado.NO_DISPONIBLE,
        contenido=preparado,
        razon=None if preparado else (
            "La corrida no conserva una copia inmutable del receptor preparado que utilizó."
        ),
    ))

    # ── Ligando: el SMILES canónico como archivo ─────────────────────
    smiles = getattr(molecule, "smiles", None)
    artefactos.append(Artefacto(
        rol="inputs",
        nombre="ligand.smi",
        media_type="chemical/x-daylight-smiles",
        fuente="molecule.smiles",
        estado=Estado.REGISTRADO if smiles else Estado.NO_DISPONIBLE,
        contenido=f"{smiles}\n".encode("utf-8") if smiles else None,
        razon=None if smiles else "La molécula no tiene SMILES serializado.",
    ))

    # ── Contratos estructurales: la evidencia, en su forma exacta ────
    #
    # Se guardan TAL CUAL los persistió el backend. El PDF es una lectura de
    # estos dos objetos; incluirlos crudos permite a un tercero comprobar que
    # el documento no añadió, quitó ni suavizó nada. Si faltan, se declaran
    # ausentes con su razón en vez de omitirse.
    import json as _json

    evidencia_fisica = getattr(eval_result, "structural_evidence", None)
    artefactos.append(Artefacto(
        rol="evidencia",
        nombre="structural_evidence.json",
        media_type="application/json",
        fuente="evaluation_results.structural_evidence",
        estado=Estado.REGISTRADO if evidencia_fisica else Estado.NO_EVALUADO,
        contenido=(
            _json.dumps(evidencia_fisica, ensure_ascii=False, sort_keys=True, indent=2,
                        default=str).encode("utf-8") + b"\n"
        ) if evidencia_fisica else None,
        razon=None if evidencia_fisica else (
            "Esta corrida es anterior a la etapa de validación física, o la etapa no llegó a "
            "emitir veredicto. Que no se midiera no dice nada sobre las poses."
        ),
    ))

    seleccion = getattr(eval_result, "pose_selection", None)
    artefactos.append(Artefacto(
        rol="evidencia",
        nombre="pose_selection.json",
        media_type="application/json",
        fuente="evaluation_results.pose_selection",
        estado=Estado.REGISTRADO if seleccion else Estado.NO_EVALUADO,
        contenido=(
            _json.dumps(seleccion, ensure_ascii=False, sort_keys=True, indent=2,
                        default=str).encode("utf-8") + b"\n"
        ) if seleccion else None,
        razon=None if seleccion else (
            "Esta corrida es anterior a la etapa de selección de pose. La referencia sigue "
            "siendo Vina top-1, declarada como fallback."
        ),
    ))

    # ── Metadatos del selector: modelo, versión y hashes ─────────────
    # Van aparte del contrato para que un verificador pueda comprobar QUÉ
    # modelo opinó sin leerse el JSON entero, y para que el hash del modelo
    # quede junto a los del resto de artefactos del manifiesto.
    modelo_sel = (seleccion or {}).get("model") if isinstance(seleccion, dict) else None
    artefactos.append(Artefacto(
        rol="evidencia",
        nombre="pose_selector_model.json",
        media_type="application/json",
        fuente="evaluation_results.pose_selection.model",
        estado=Estado.REGISTRADO if modelo_sel else Estado.NO_DISPONIBLE,
        contenido=(
            _json.dumps(modelo_sel, ensure_ascii=False, sort_keys=True, indent=2,
                        default=str).encode("utf-8") + b"\n"
        ) if modelo_sel else None,
        razon=None if modelo_sel else (
            "El selector no llegó a cargar su modelo, así que no hay artefacto que sellar."
        ),
    ))

    # ── Las poses que el dossier nombra ──────────────────────────────
    #
    # NO se duplica el `.sdf` completo: ya viaja como `poses.sdf` y el manifiesto
    # lo declara. Aquí va un índice pequeño que dice QUÉ pose es la top-1 de
    # Vina, cuál recomendó el selector y cuáles son alternativas físicamente
    # válidas, apuntando al archivo grande por su nombre. Copiar los bloques
    # otra vez engordaría el paquete sin añadir una sola comprobación.
    if poses_crudas or seleccion or evidencia_fisica:
        estados_fisicos = {}
        if isinstance(evidencia_fisica, dict):
            for entrada in evidencia_fisica.get("poses") or []:
                if entrada.get("rank") is not None:
                    estados_fisicos[entrada["rank"]] = entrada.get("status")
        sel = seleccion if isinstance(seleccion, dict) else {}
        top1 = sel.get("vina_top1_rank")
        sugerida = sel.get("selected_pose_rank")
        alternativas = [
            a.get("rank") for a in (sel.get("physically_valid_alternatives") or [])
            if isinstance(a, dict) and a.get("rank") is not None
        ]
        indice = {
            "contrato": "pose_index/v2",
            "nota": (
                "Índice de referencia. Cada pose apunta a su bloque PDBQT exacto; "
                "`outputs/poses.sdf` se declara además cuando la corrida produjo un "
                "archivo único que representa la colección."
            ),
            "archivo_sdf_de_coleccion": (
                "outputs/poses.sdf" if contenido_poses else None
            ),
            "vina_top1_rank": top1,
            "pose_sugerida_rank": sugerida,
            "alternativas_fisicamente_validas": alternativas,
            "poses": [
                {
                    "rank": getattr(pose, "rank", None) if not isinstance(pose, dict) else pose.get("rank"),
                    "affinity_kcal_mol": (
                        getattr(pose, "affinity", None) if not isinstance(pose, dict)
                        else pose.get("affinity")
                    ),
                    "physical_status": estados_fisicos.get(
                        getattr(pose, "rank", None) if not isinstance(pose, dict) else pose.get("rank"),
                        "not_evaluated",
                    ),
                    "archivo_pdbqt": archivos_pdbqt.get(
                        getattr(pose, "rank", None) if not isinstance(pose, dict)
                        else pose.get("rank")
                    ),
                    "es_vina_top1": (
                        (getattr(pose, "rank", None) if not isinstance(pose, dict) else pose.get("rank"))
                        == top1
                    ),
                    "es_sugerida": (
                        (getattr(pose, "rank", None) if not isinstance(pose, dict) else pose.get("rank"))
                        == sugerida
                    ),
                    "es_alternativa": (
                        (getattr(pose, "rank", None) if not isinstance(pose, dict) else pose.get("rank"))
                        in alternativas
                    ),
                }
                for pose in poses_crudas
            ],
        }
        artefactos.append(Artefacto(
            rol="evidencia",
            nombre="pose_index.json",
            media_type="application/json",
            fuente="eval_result.docking_poses + structural_evidence + pose_selection",
            estado=Estado.REGISTRADO,
            contenido=_json.dumps(indice, ensure_ascii=False, sort_keys=True,
                                  indent=2, default=str).encode("utf-8") + b"\n",
        ))
    else:
        artefactos.append(Artefacto(
            rol="evidencia", nombre="pose_index.json", media_type="application/json",
            fuente="eval_result.docking_poses + structural_evidence + pose_selection",
            estado=Estado.NO_DISPONIBLE,
            razon="La corrida no serializó poses ni contratos estructurales.",
        ))

    # ── Logs de ESTA corrida ─────────────────────────────────────────
    avisos = getattr(eval_result, "scientific_warnings", None) or []
    error = getattr(eval_result, "error_message", None)
    if avisos or error:
        cuerpo = "\n".join([*(str(a) for a in avisos), *( [f"ERROR: {error}"] if error else [])])
        artefactos.append(Artefacto(
            rol="logs", nombre="run_warnings.log", media_type="text/plain",
            fuente="eval_result.scientific_warnings / error_message",
            estado=Estado.REGISTRADO, contenido=(cuerpo + "\n").encode("utf-8"),
        ))
    else:
        artefactos.append(Artefacto(
            rol="logs", nombre="run_warnings.log", media_type="text/plain",
            fuente="eval_result.scientific_warnings / error_message",
            estado=Estado.NO_DISPONIBLE,
            razon="La corrida no registró advertencias ni errores.",
        ))

    return artefactos


def _content_disposition(disposicion: str, nombre: str) -> str:
    """
    Cabecera segura.

    El nombre va saneado a `[A-Za-z0-9._-]`: un nombre de caso con comillas o
    saltos de línea podría inyectar cabeceras, y uno con acentos rompe clientes
    que no leen `filename*`.
    """
    return f'{disposicion}; filename="{sanitizar(nombre, maximo=120)}"'


@router.post(
    "/{molecule_id}/preview",
    summary="Dossier del caso en PDF (inline)",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
)
async def dossier_preview(
    molecule_id: uuid.UUID,
    projection: CaseProjection,
    current_user: UserORM | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """Genera el dossier y lo devuelve para leer en pantalla."""
    molecule, eval_result, target = await _reunir(molecule_id, projection, current_user, db)
    dossier = build_case_dossier(
        projection=projection, molecule=molecule, eval_result=eval_result, target=target,
        generated_at=datetime.now(timezone.utc),
    )
    pdf = render_dossier_pdf(dossier)
    nombre = f"dossier_{sanitizar(projection.name, maximo=60)}.pdf"
    log.info("dossier_preview", molecule_id=str(molecule_id), case_id=projection.case_id)
    return StreamingResponse(
        pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": _content_disposition("inline", nombre),
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )


@router.post(
    "/{molecule_id}/package",
    summary="Paquete reproducible del caso (ZIP con manifiesto y hashes)",
    response_class=Response,
    responses={200: {"content": {"application/zip": {}}}},
)
async def dossier_package(
    molecule_id: uuid.UUID,
    projection: CaseProjection,
    current_user: UserORM | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """Genera el paquete verificable: PDF, manifiesto, hashes y artefactos reales."""
    molecule, eval_result, target = await _reunir(molecule_id, projection, current_user, db)
    ahora = datetime.now(timezone.utc)
    dossier = build_case_dossier(
        projection=projection, molecule=molecule, eval_result=eval_result, target=target,
        generated_at=ahora,
    )
    pdf = render_dossier_pdf(dossier).getvalue()
    artefactos = await _artefactos(eval_result, target, molecule)
    datos, entradas, raiz = construir_paquete(
        dossier=dossier,
        pdf_bytes=pdf,
        projection_json=projection.model_dump_json(indent=2),
        artefactos=artefactos,
    )
    log.info(
        "dossier_package",
        molecule_id=str(molecule_id),
        case_id=projection.case_id,
        archivos=len(entradas),
        bytes=len(datos),
    )
    return Response(
        content=datos,
        media_type="application/zip",
        headers={
            "Content-Disposition": _content_disposition("attachment", f"{raiz}.zip"),
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )
