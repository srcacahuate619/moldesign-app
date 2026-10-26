"""Selección de fuentes propias y trabajos Molcy con identidad de corrida."""
from __future__ import annotations

import uuid
import asyncio
import secrets
import time
import threading
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi import Path as Path_
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import and_, exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.dependencies import get_current_user
from core.database import get_db
from core.exceptions import LocalStorageError
from core.models import EvaluationRunORM, MoleculeORM, TargetORM, UserORM
from db.repository import Repository
from services.molcy.package import construir_paquete, sha256
from services.docking import search_trace
from services.molcy import addon, cpu, disk, fotos, gpu, renderer, installation, salidas, storage
from services.molcy import ensamble as evidencia_ensamble
from services.molcy.presentacion import PresentacionMolcy, EnsambleFluido, normalizar as normalizar_ajustes
from services.targets.access import get_target_for_user, target_is_accessible
from services.targets.disponibilidad import motivo_no_disponible
from services.targets.seccion_catalogo import seccion_del_receptor
from services.semilla_estructuras import _directorio_empaquetado
from utils.file_handlers import StoragePath
from utils.local_storage import path_for, read_bytes

def _molecula_con_fichas():
    """¿La molécula tiene al menos una evaluación guardada como ficha propia?"""
    return exists(select(EvaluationRunORM.id).where(
        EvaluationRunORM.molecule_id == MoleculeORM.id,
        EvaluationRunORM.saved_at.isnot(None),
    )).correlate(MoleculeORM)


async def _corrida_en_moldex(db: AsyncSession, molecula: MoleculeORM,
                             corrida: EvaluationRunORM) -> bool:
    """Una corrida sólo es fuente si el investigador la guardó en Moldex."""
    if corrida.saved_at is not None:
        return True
    if not molecula.is_saved:
        return False
    return not await db.scalar(select(_molecula_con_fichas()).select_from(MoleculeORM).where(
        MoleculeORM.id == molecula.id))


def _instalacion_estable() -> None:
    if installation.status().get("estado") == "instalando" or addon.estado().get("estado") == "instalando":
        raise HTTPException(409, "Espera a que termine la instalación de Blender o Molecular Nodes.")


router = APIRouter(prefix="/molcy", tags=["Molcy"])
_media: dict[str, tuple[float, str, str]] = {}
_media_lock = threading.Lock()


class NuevoTrabajo(BaseModel):
    origen: Literal["moldex", "receptor"]
    id: str
    task_id: str | None = None
    escena: Literal["resultado", "receptor", "busqueda", "ensamble"]
    formato: Literal["horizontal", "vertical", "previsualizacion"]
    dispositivo: Literal["cpu", "gpu"] = "gpu"
    cpu_hilos: int | None = Field(default=None, strict=True, ge=1, le=1024)
    #: Carpeta de salida elegida SÓLO para este vídeo (id que dio el selector nativo), o
    #: «predeterminada» para ignorar la preferencia global. Sin valor: la preferencia global o el caso.
    salida_id: str | None = Field(default=None, max_length=64)
    presentacion: PresentacionMolcy = Field(default_factory=PresentacionMolcy)
    ensamble_fluido: EnsambleFluido | None = None
    # Compatibility with clients that explicitly selected a budget. The app
    # omits this field: Blender manages VRAM automatically.
    gpu_vram_mib: int | None = Field(default=None, strict=True, ge=128, le=1048576, deprecated=True)


def _datos_caja(prov: dict) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    try:
        return (tuple(float(x) for x in prov["box_center"]),
                tuple(float(x) for x in prov["box_size"]))  # type: ignore[return-value]
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(409, "La corrida no conserva su caja de docking exacta.") from exc


def _fuente_receptor_disponible(target: TargetORM) -> bool:
    if target.prepared_file_path:
        try:
            if path_for(target.prepared_file_path).is_file():
                return True
        except (OSError, ValueError):
            pass
    if path_for(StoragePath.target_raw(target.pdb_id)).is_file():
        return True
    bundle = _directorio_empaquetado()
    return bool(bundle and any((bundle / f"{name}.pdb.gz").is_file()
                               for name in (target.pdb_id, target.pdb_id.lower())))


@router.get("/fuentes")
async def fuentes(user: UserORM = Depends(get_current_user),
                  db: AsyncSession = Depends(get_db)):
    repo = Repository(db)
    corridas = (await db.execute(
        select(EvaluationRunORM, MoleculeORM.name, TargetORM.pdb_id)
        .join(MoleculeORM, EvaluationRunORM.molecule_id == MoleculeORM.id)
        .join(TargetORM, MoleculeORM.target_id == TargetORM.id)
        .where(MoleculeORM.user_id == user.id, EvaluationRunORM.status == "SUCCESS",
               or_(
                   EvaluationRunORM.saved_at.isnot(None),
                   # Vía heredada: molécula guardada entera, sin fichas por corrida.
                   and_(MoleculeORM.is_saved.is_(True), ~_molecula_con_fichas()),
               ))
        .order_by(EvaluationRunORM.created_at.desc())
    )).all()
    try:
        casos = storage.casos(str(user.id))
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    moldex = []
    motor_con_ensamble: bool | None = None
    for run, nombre, receptor in corridas:
        snap = run.snapshot_json or {}
        prov = (snap.get("docking_protocol") or {}).get("execution_provenance") or {}
        receptor_disponible = all((snap.get("receptor_path"), snap.get("receptor_sha256"),
                                   prov.get("box_center"), prov.get("box_size")))
        escenas = ["receptor"] if receptor_disponible else []
        if receptor_disponible and snap.get("poses_file_path") and prov.get("poses_sha256"):
            escenas.insert(0, "resultado")
            trace = prov.get("search_trace")
            if trace and renderer.busqueda_disponible():
                try:
                    metadata, _ = await search_trace.recover(trace)
                    if (metadata["receptor_sha256"] == snap["receptor_sha256"]
                            and metadata["ligand_pdbqt_sha256"] == prov.get("ligand_pdbqt_sha256")
                            and metadata.get("poses_sdf_sha256") == prov["poses_sha256"]
                            and metadata["box_center"] == prov["box_center"]
                            and metadata["box_size"] == prov["box_size"]
                            and metadata["seed"] == snap.get("vina_random_seed")):
                        escenas.append("busqueda")
                except (OSError, ValueError, KeyError):
                    pass
        # El ensamble necesita la caja y el receptor verificables, el linaje de cada pose
        # y un motor que traiga la escena. La demostración exacta (hashes, seis puertas
        # de recuperación) ocurre al lanzarla y se abstiene diciendo qué falta. Lo barato
        # va primero: comprobar el motor relee y hashea sus ficheros, y se hace una vez.
        if receptor_disponible and evidencia_ensamble.es_ensamble(snap)[0]:
            if motor_con_ensamble is None:
                motor_con_ensamble = renderer.ensamble_disponible()
            if motor_con_ensamble:
                escenas.append("ensamble")
        disponible = bool(escenas)
        try:
            caso = storage.caso_de_corrida(str(user.id), run.task_id, registrados=casos)
            motivo_caso = None
        except ValueError as exc:
            caso, motivo_caso, disponible = None, str(exc), False
        moldex.append({"id": str(run.molecule_id), "nombre": nombre or f"MOL-{str(run.molecule_id)[:8]}",
                       "receptor": receptor, "task_id": run.task_id,
                       "caso": {"id": caso["id"], "nombre": caso["nombre"]} if caso else None,
                       "disponible": bool(disponible),
                       "escenas_disponibles": escenas,
                       "motivo": motivo_caso or (None if disponible else "Esta corrida no conserva receptor, poses o caja verificables.")})
    targets = await repo.get_all_targets()
    receptores = []
    for t in targets:
        if not target_is_accessible(t, user) or t.retired_reason:
            continue
        bloqueo = motivo_no_disponible(t.pdb_id)
        disponible = bloqueo is None and _fuente_receptor_disponible(t)
        receptores.append({"id": t.pdb_id, "nombre": t.name,
                           "propio": bool(t.creator_id == user.id),
                           "disponible": disponible,
                           "motivo": None if disponible else bloqueo or "No hay estructura local para este receptor."})
    return {"moldex": moldex, "receptores": receptores}


@router.get("/renderizador")
def renderizador(recomprobar: bool = False, _user: UserORM = Depends(get_current_user)):
    result = {**renderer.detectar(forzar=recomprobar), **cpu.recursos()}
    result["gpu_memoria"] = "automatica"
    result.update(gpu.recursos(result))
    result.update(_espacio(str(_user.id), None))
    return result


def _espacio(user_id: str, task_id: uuid.UUID | None, salida_id: str | None = None) -> dict:
    echo = {"espacio_task_id": str(task_id) if task_id else None, "espacio_salida_id": salida_id}
    try:
        salida = salidas.elegir(user_id, salida_id)
        case = storage.caso_de_corrida(user_id, str(task_id)) if task_id and salida is None else None
        destination = (salida["ruta"] if salida else case["ruta"] / "molcy" if case else renderer.raiz_salida())
        def budget(name):
            result = disk.budget(destination, name)
            try:
                disk.assert_brand_budget(renderer.raiz_salida(), name)
            except OSError as exc:
                result["disponible"] = False
                result["motivo"] = str(exc)
            return result
        return {**echo,
                "espacio": {name: budget(name) for name in disk.FORMATS},
                "espacio_fotos": {name: disk.photo_budget(destination, name) for name in disk.PHOTO_SHORT_SIDE}}
    except (OSError, ValueError) as exc:
        return {**echo, "espacio": None, "espacio_fotos": None, "espacio_motivo": str(exc)}


@router.get("/recursos")
def recursos(task_id: uuid.UUID | None = None, salida_id: str | None = Query(default=None, max_length=64),
             _user: UserORM = Depends(get_current_user)):
    # Actualiza carga/memoria sin arrancar Blender ni repetir el sondeo gráfico.
    return {**cpu.recursos(), **gpu.recursos(renderer.capacidad_estimada()),
            **_espacio(str(_user.id), task_id, salida_id)}


class PreferenciaSalida(BaseModel):
    salida_id: str | None = Field(default=None, max_length=64)


def _vista_salida(user_id: str) -> dict:
    """Preferencia global actual y si esta instalación puede autorizar carpetas."""
    actual = None
    problema = None
    ident = salidas.preferencia(user_id)
    if ident:
        try:
            actual = {"id": ident, "ruta": str(salidas.carpeta(ident)["ruta"])}
        except ValueError as exc:
            problema = str(exc)  # se declara: la preferencia existe pero ya no se puede usar
    return {"disponible": salidas.disponible(), "global": actual, "problema": problema,
            "predeterminada": str(renderer.raiz_salida())}


@router.get("/salida")
def salida_actual(user: UserORM = Depends(get_current_user)):
    return _vista_salida(str(user.id))


@router.put("/salida")
def fijar_salida(req: PreferenciaSalida, user: UserORM = Depends(get_current_user)):
    """«Para todos los vídeos»: recuerda la carpeta (o la quita con `null`)."""
    try:
        salidas.fijar_preferencia(str(user.id), req.salida_id)
    except (OSError, ValueError) as exc:
        raise HTTPException(409, str(exc)) from exc
    return _vista_salida(str(user.id))


class EstimacionFoto(BaseModel):
    orientacion: Literal["horizontal", "vertical"]
    resolucion: Literal["720p", "1080p", "1440p", "4k"]
    dispositivo: Literal["cpu", "gpu"]
    cpu_hilos: int | None = Field(default=None, strict=True, ge=1, le=1024)


@router.post("/fotos/estimacion")
async def estimacion_foto(req: EstimacionFoto, user: UserORM = Depends(get_current_user)):
    """Cuánto tardará una foto, medido con las fotos anteriores de este equipo. Sin medidas no hay número."""
    hilos = None
    if req.dispositivo == "cpu":
        try:
            hilos = cpu.validar_hilos(req.cpu_hilos)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
    elif req.cpu_hilos is not None:
        raise HTTPException(422, "La cantidad de hilos sólo se configura con la CPU.")
    jobs = await asyncio.to_thread(renderer.listar, str(user.id))
    return {**fotos.estimar(jobs, orientacion=req.orientacion, resolucion=req.resolucion, dispositivo=req.dispositivo,
                            capacidad=renderer.capacidad_estimada(), cpu_hilos=hilos),
            "dispositivo": req.dispositivo, "resolucion": req.resolucion}


@router.get("/addon")
def estado_addon(_user: UserORM = Depends(get_current_user)):
    return addon.estado()


@router.post("/addon", status_code=202)
def instalar_addon(_user: UserORM = Depends(get_current_user)):
    with renderer._lock:
        if renderer._reserved:
            raise HTTPException(409, "Espera a que termine el render antes de instalar Molecular Nodes.")
        if installation.status().get("estado") == "instalando":
            raise HTTPException(409, "Espera a que termine la instalación de Blender.")
        try:
            return addon.iniciar()
        except (ValueError, OSError) as exc:
            raise HTTPException(409, str(exc)) from exc


#: Qué escena admite cada origen: un receptor solo no tiene pose ni búsqueda.
_ESCENAS_DE_ORIGEN = {("moldex", "resultado"), ("moldex", "busqueda"), ("moldex", "receptor"),
                      ("moldex", "ensamble"), ("receptor", "receptor")}


async def _evidencia(req, user: UserORM, db: AsyncSession) -> dict:
    """Lo que el paquete de escena necesita, verificado por SHA-256. Lo mismo para un vídeo que para una sesión de fotos."""
    repo = Repository(db)
    fuente: dict = {"origen": req.origen, "id": req.id, "escena": req.escena}
    caso = None
    poses = None
    poses_hash = None
    afinidad = None
    vina_version = None
    semilla = None
    search_metadata = search_files = None
    ensamble = None
    if req.origen == "moldex":
        try:
            molecule_id = uuid.UUID(req.id)
        except ValueError as exc:
            raise HTTPException(404, "Evaluación no encontrada.") from exc
        mol = await db.scalar(select(MoleculeORM).options(selectinload(MoleculeORM.target)).where(
            MoleculeORM.id == molecule_id, MoleculeORM.user_id == user.id))
        if mol is None or not req.task_id:
            raise HTTPException(404, "Evaluación no encontrada en Moldex.")
        corrida = await repo.get_evaluation_run(req.task_id, molecule_id)
        if corrida is None or corrida.status != "SUCCESS":
            raise HTTPException(404, "Corrida terminada no encontrada.")
        if not await _corrida_en_moldex(db, mol, corrida):
            raise HTTPException(404, "Evaluación no encontrada en Moldex.")
        caso = storage.caso_de_corrida(str(user.id), req.task_id)
        if caso:
            fuente.update(case_id=caso["id"], case_name=caso["nombre"])
        snap = await repo.materialize_run_snapshot(corrida)
        prov = (snap.get("docking_protocol") or {}).get("execution_provenance") or {}
        centro, tamano = _datos_caja(prov)
        receptor_path = snap.get("receptor_path")
        receptor_hash = snap.get("receptor_sha256")
        if not all((receptor_path, receptor_hash)):
            raise HTTPException(409, "La corrida no conserva su receptor con un hash verificable.")
        try:
            receptor = await read_bytes(receptor_path)
            if req.escena in {"resultado", "busqueda"}:
                poses_path = snap.get("poses_file_path")
                poses_hash = prov.get("poses_sha256")
                if not all((poses_path, poses_hash)):
                    raise HTTPException(409, "La corrida no conserva receptor y poses con hashes verificables.")
                poses = await read_bytes(poses_path)
            if req.escena == "busqueda":
                if not renderer.busqueda_disponible() or not prov.get("search_trace"):
                    raise HTTPException(409, "Esta corrida no conserva una búsqueda interna compatible con Molcy.")
                search_metadata, search_files = await search_trace.recover(prov["search_trace"])
                if search_metadata["ligand_pdbqt_sha256"] != prov.get("ligand_pdbqt_sha256"):
                    raise HTTPException(409, "La traza no pertenece al ligando de esta corrida.")
            if req.escena == "ensamble":
                if not renderer.ensamble_disponible():
                    raise HTTPException(409, "El motor Molcy instalado no trae la escena Ensamble; actualízalo.")
                try:
                    ensamble = await evidencia_ensamble.recoger(snap)
                except evidencia_ensamble.EnsambleNoDisponible as exc:
                    raise HTTPException(409, str(exc)) from exc
        except (OSError, ValueError, LocalStorageError) as exc:
            raise HTTPException(409, "Falta un archivo persistido de la corrida.") from exc
        if sha256(receptor) != receptor_hash or (poses is not None and sha256(poses) != poses_hash):
            raise HTTPException(409, "Un archivo de la corrida ya no coincide con su SHA-256.")
        target = mol.target
        fuente.update({"molecule_id": req.id, "task_id": req.task_id})
        if poses_hash:
            fuente["poses_sha256"] = poses_hash
        afinidad = snap.get("affinity_kcal")
        vina_version = snap.get("vina_version")
        semilla = snap.get("vina_random_seed")
        sujeto = {"resultado": "pose_evaluada", "busqueda": "busqueda_montecarlo",
                  "receptor": "receptor_solo", "ensamble": "ensamble_conformacional"}[req.escena]
    else:
        target = await get_target_for_user(repo, req.id, user)
        bloqueo = motivo_no_disponible(target.pdb_id)
        if bloqueo:
            raise HTTPException(409, bloqueo)
        receptor_path = target.prepared_file_path
        if receptor_path and not path_for(receptor_path).is_file() and target.prepared_receptor_sha256:
            raise HTTPException(409, "Falta la preparación registrada de este receptor.")
        if not receptor_path or not path_for(receptor_path).is_file():
            if not _fuente_receptor_disponible(target):
                raise HTTPException(409, "No hay estructura local; añade un PDB antes de renderizar.")
            from services.docking.preparer import prepare_target
            receptor_path = await prepare_target(
                pdb_id=target.pdb_id, chain_id=target.chain,
                center=(target.grid_center_x, target.grid_center_y, target.grid_center_z),
                size=(target.grid_size_x, target.grid_size_y, target.grid_size_z),
                cofactors_whitelist=target.cofactors_whitelist or [],
                site_chains=target.site_chains, site_ligand=target.site_ligand,
            )
        try:
            receptor = await read_bytes(receptor_path)
        except (OSError, ValueError, LocalStorageError) as exc:
            raise HTTPException(409, "No se encontró el PDBQT preparado de este receptor.") from exc
        receptor_hash = target.prepared_receptor_sha256 or sha256(receptor)
        if sha256(receptor) != receptor_hash:
            raise HTTPException(409, "El receptor ya no coincide con su SHA-256 registrado.")
        centro = (target.grid_center_x, target.grid_center_y, target.grid_center_z)
        tamano = (target.grid_size_x, target.grid_size_y, target.grid_size_z)
        fuente.update({"target_id": str(target.id), "receptor_sha256": receptor_hash,
                       "hash_registrado": bool(target.prepared_receptor_sha256)})
        sujeto = "receptor_solo"
    # El historial identifica el receptor concreto de Moldex además de
    # conservar el origen de la molécula o la corrida.
    fuente.update({"target_id": str(target.id), "pdb_id": target.pdb_id,
                   "target_name": target.name, "chain": target.chain})
    fuente["receptor_sha256"] = receptor_hash
    return {"target": target, "fuente": fuente, "caso": caso, "receptor": receptor, "receptor_hash": receptor_hash,
            "centro": centro, "tamano": tamano, "poses": poses, "poses_hash": poses_hash, "afinidad": afinidad,
            "vina_version": vina_version, "semilla": semilla, "search_metadata": search_metadata,
            "search_files": search_files, "ensamble": ensamble, "sujeto": sujeto}


def _destino(user_id: str, salida_id: str | None, caso: dict | None) -> tuple[dict | None, Path]:
    salida = salidas.elegir(user_id, salida_id)
    return salida, (salida["ruta"] if salida else caso["ruta"] / "molcy" if caso else renderer.raiz_salida())


def _escribir_paquete(root: Path, ev: dict) -> None:
    target = ev["target"]
    paquete = root / "escenas" / target.pdb_id
    paquete.mkdir(parents=True, exist_ok=False)
    construir_paquete(paquete, receptor_pdbqt=ev["receptor"], receptor_sha256=ev["receptor_hash"],
                      pdb_id=target.pdb_id, nombre=target.name, cadena=target.chain,
                      seccion=seccion_del_receptor(target),
                      centro=ev["centro"], tamano=ev["tamano"], fuente=ev["fuente"], poses_sdf=ev["poses"],
                      poses_sha256=ev["poses_hash"], afinidad=ev["afinidad"],
                      version_vina=ev["vina_version"], semilla=ev["semilla"],
                      search_metadata=ev["search_metadata"], search_files=ev["search_files"],
                      ensamble=ev["ensamble"])


def _fallo_al_construir(root: Path, job_id: str, fuente: dict, exc: Exception, tipo: str | None = None) -> HTTPException:
    try:
        renderer.guardar_estado(root, {"id": job_id, "estado": "fallido", "fuente": fuente,
                                       "creado_s": time.time(), "motivo": str(exc), **({"tipo": tipo} if tipo else {})})
    except OSError:
        pass
    return HTTPException(409, f"No se pudo construir un paquete fiel: {exc}")


@router.post("/trabajos", status_code=202)
async def crear_trabajo(req: NuevoTrabajo, user: UserORM = Depends(get_current_user),
                        db: AsyncSession = Depends(get_db)):
    """Un VÍDEO, sólo con GPU. Las fotos (CPU o GPU) se piden en `/molcy/fotos`."""
    if (req.origen, req.escena) not in _ESCENAS_DE_ORIGEN:
        raise HTTPException(422, "La escena elegida no corresponde al origen seleccionado.")
    if req.dispositivo != "gpu" or req.cpu_hilos is not None:
        raise HTTPException(422, renderer.MENSAJE_VIDEO_SOLO_GPU)
    job_id = str(uuid.uuid4())
    try:
        with renderer.reservar(job_id):
            _instalacion_estable()
            capacidad = await asyncio.to_thread(renderer.detectar)
            if not capacidad["disponible"]:
                raise HTTPException(409, capacidad["motivo"])
            if not capacidad.get("gpu_disponible", False):
                raise HTTPException(409, capacidad.get("motivo_gpu") or "GPU no disponible para Molcy.")
            gpu_presupuesto = None
            if req.gpu_vram_mib is not None:
                try:
                    gpu_presupuesto = gpu.validar_presupuesto(req.gpu_vram_mib, gpu.recursos(capacidad))
                except ValueError as exc:
                    raise HTTPException(409, str(exc)) from exc
            formato = {"horizontal": "biblioteca", "vertical": "social_vertical",
                       "previsualizacion": "previsualizacion"}[req.formato]
            ev = await _evidencia(req, user, db)
            fluido = _fluido_efectivo(req, ev)
            target = ev["target"]
            try:
                salida, destino = _destino(str(user.id), req.salida_id, ev["caso"])
                disk.assert_budget(destino, formato)
                disk.assert_brand_budget(renderer.raiz_salida(), formato)
                root = storage.crear_raiz(str(user.id), job_id, ev["caso"], target.name, target.pdb_id, req.task_id,
                                          salida=salida)
            except (OSError, ValueError) as exc:
                raise HTTPException(409, str(exc)) from exc
            try:
                _escribir_paquete(root, ev)
                renderer.iniciar(root, job_id=job_id, pdb_id=target.pdb_id, sujeto=ev["sujeto"],
                                 formato=formato, dispositivo="gpu",
                                 capacidad=capacidad, fuente=ev["fuente"], gpu_presupuesto=gpu_presupuesto,
                                 presentacion=req.presentacion.model_dump(by_alias=True), ensamble_fluido=fluido)
            except (OSError, ValueError) as exc:
                raise _fallo_al_construir(root, job_id, ev["fuente"], exc) from exc
            return {"id": job_id, "estado": "en_cola",
                    "ajustes": normalizar_ajustes(req.presentacion.model_dump(by_alias=True), fluido)}
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


def _fluido_efectivo(req, ev: dict) -> dict | None:
    if req.ensamble_fluido is None:
        return None
    if req.escena != "ensamble":
        raise HTTPException(422, "La ilustración fluida sólo corresponde a la escena Ensamble.")
    conformeros = ((ev.get("ensamble") or {}).get("contrato") or {}).get("conformeros") or []
    candidates = [item for item in conformeros if req.ensamble_fluido.conformero is None
                  or item.get("indice") == req.ensamble_fluido.conformero]
    for item in candidates:
        rig = item.get("rig_torsional") or {}
        if (rig.get("schema") == "moldesign.rig-torsional/1" and rig.get("ejes")
                and rig.get("sdf_sha256") == item.get("sdf_sha256")):
            return {"variante": req.ensamble_fluido.variante, "conformero": item["indice"]}
    raise HTTPException(409, "La conformación elegida no conserva un rig torsional verificable con ejes elegibles.")


class NuevasFotos(BaseModel):
    origen: Literal["moldex", "receptor"]
    id: str
    task_id: str | None = None
    escena: Literal["resultado", "receptor", "busqueda", "ensamble"]
    orientacion: Literal["horizontal", "vertical"]
    presentacion: PresentacionMolcy = Field(default_factory=PresentacionMolcy)
    ensamble_fluido: EnsambleFluido | None = None
    dispositivo: Literal["cpu", "gpu"]
    cpu_hilos: int | None = Field(default=None, strict=True, ge=1, le=1024)
    salida_id: str | None = Field(default=None, max_length=64)


def _hilos_pedidos(dispositivo: str, cpu_hilos: int | None, capacidad: dict | None = None) -> None:
    if dispositivo == "gpu" and cpu_hilos is not None:
        raise HTTPException(422, "La cantidad de hilos sólo se configura con la CPU.")
    if dispositivo == "cpu":
        try:
            cpu.validar_hilos(cpu_hilos)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        if capacidad is not None and cpu_hilos is not None and not capacidad.get("cpu_hilos_configurables"):
            raise HTTPException(409, "Actualiza el motor Molcy para poder elegir los hilos de CPU.")


def _capacidad_de_fotos(capacidad: dict, dispositivo: str) -> None:
    if not capacidad.get("foto_disponible"):
        raise HTTPException(409, capacidad.get("motivo_foto") or capacidad.get("motivo") or "Molcy no puede tomar fotos.")
    if dispositivo == "gpu" and not capacidad.get("foto_gpu_disponible"):
        raise HTTPException(409, capacidad.get("motivo_foto_gpu") or "Cycles no encontró una GPU en este equipo.")


@router.post("/fotos", status_code=202)
async def crear_fotos(req: NuevasFotos, user: UserORM = Depends(get_current_user),
                      db: AsyncSession = Depends(get_db)):
    """Una sesión de FOTOS: prepara la escena una vez y rinde una miniatura de cada momento sugerido."""
    if (req.origen, req.escena) not in _ESCENAS_DE_ORIGEN:
        raise HTTPException(422, "La escena elegida no corresponde al origen seleccionado.")
    _hilos_pedidos(req.dispositivo, req.cpu_hilos)
    job_id = str(uuid.uuid4())
    try:
        with renderer.reservar(job_id):
            _instalacion_estable()
            capacidad = await asyncio.to_thread(renderer.detectar)
            _capacidad_de_fotos(capacidad, req.dispositivo)
            _hilos_pedidos(req.dispositivo, req.cpu_hilos, capacidad)
            ev = await _evidencia(req, user, db)
            fluido = _fluido_efectivo(req, ev)
            target = ev["target"]
            try:
                salida, destino = _destino(str(user.id), req.salida_id, ev["caso"])
                disk.assert_photo_budget(destino, "4k")
                root = storage.crear_raiz(str(user.id), job_id, ev["caso"], target.name, target.pdb_id, req.task_id,
                                          salida=salida)
            except (OSError, ValueError) as exc:
                raise HTTPException(409, str(exc)) from exc
            try:
                _escribir_paquete(root, ev)
                fotos.iniciar(root, job_id=job_id, pdb_id=target.pdb_id, sujeto=ev["sujeto"], escena=req.escena,
                              orientacion=req.orientacion, dispositivo=req.dispositivo, capacidad=capacidad,
                              fuente=ev["fuente"], cpu_hilos=req.cpu_hilos,
                              presentacion=req.presentacion.model_dump(by_alias=True), ensamble_fluido=fluido)
            except (OSError, ValueError) as exc:
                raise _fallo_al_construir(root, job_id, ev["fuente"], exc, tipo="fotos") from exc
            return {"id": job_id, "estado": "en_cola", "tipo": "fotos",
                    "ajustes": normalizar_ajustes(req.presentacion.model_dump(by_alias=True), fluido)}
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


class NuevaFoto(BaseModel):
    fotograma: int = Field(strict=True, ge=1, le=1_000_000)
    resolucion: Literal["720p", "1080p", "1440p", "4k"]
    dispositivo: Literal["cpu", "gpu"]
    cpu_hilos: int | None = Field(default=None, strict=True, ge=1, le=1024)


class NuevaVista(BaseModel):
    fotograma: int = Field(strict=True, ge=1, le=1_000_000)
    dispositivo: Literal["cpu", "gpu"]
    cpu_hilos: int | None = Field(default=None, strict=True, ge=1, le=1024)


async def _pedir_en_sesion(job_id: uuid.UUID, user: UserORM, operacion: str, fotograma: int, dispositivo: str,
                           cpu_hilos: int | None, resolucion: str | None = None) -> dict:
    _hilos_pedidos(dispositivo, cpu_hilos)
    try:
        with renderer.reservar(str(job_id)):
            _instalacion_estable()
            capacidad = await asyncio.to_thread(renderer.detectar)
            _capacidad_de_fotos(capacidad, dispositivo)
            _hilos_pedidos(dispositivo, cpu_hilos, capacidad)
            return fotos.pedir(str(user.id), str(job_id), operacion=operacion, fotograma=fotograma,
                               dispositivo=dispositivo, capacidad=capacidad, resolucion=resolucion,
                               cpu_hilos=cpu_hilos)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/trabajos/{job_id}/fotos", status_code=202)
async def tomar_foto(job_id: uuid.UUID, req: NuevaFoto, user: UserORM = Depends(get_current_user)):
    """Una foto de la escena preparada: un fotograma (sugerido o libre) a la resolución pedida, con marca y procedencia."""
    return await _pedir_en_sesion(job_id, user, "foto", req.fotograma, req.dispositivo, req.cpu_hilos, req.resolucion)


@router.post("/trabajos/{job_id}/vista", status_code=202)
async def vista_previa(job_id: uuid.UUID, req: NuevaVista, user: UserORM = Depends(get_current_user)):
    """Un fotograma libre al tamaño de una miniatura, para elegirlo viendo antes de pedir la foto."""
    return await _pedir_en_sesion(job_id, user, "vista", req.fotograma, req.dispositivo, req.cpu_hilos)


def _imagen(user: UserORM, job_id: uuid.UUID, clase: str, clave: str, nombre: bool = False) -> Response:
    try:
        datos = fotos.leer_png(str(user.id), str(job_id), clase, clave)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(409, "La imagen ya no coincide con su SHA-256.") from exc
    headers = {"Cache-Control": "private, no-store"}
    if nombre:
        path, _ = fotos.ruta_de(str(user.id), str(job_id), clase, clave)
        headers["Content-Disposition"] = f'inline; filename="{path.name}"'
    return Response(datos, media_type="image/png", headers=headers)


@router.get("/trabajos/{job_id}/tomas/{fotograma}")
def toma(job_id: uuid.UUID, fotograma: int, user: UserORM = Depends(get_current_user)):
    return _imagen(user, job_id, "toma", str(fotograma))


@router.get("/trabajos/{job_id}/vistas/{fotograma}")
def vista(job_id: uuid.UUID, fotograma: int, user: UserORM = Depends(get_current_user)):
    return _imagen(user, job_id, "vista", str(fotograma))


@router.get("/trabajos/{job_id}/fotos/{foto_id}")
def foto(job_id: uuid.UUID, foto_id: str = Path_(pattern=r"^[0-9]{2,4}$"), user: UserORM = Depends(get_current_user)):
    return _imagen(user, job_id, "foto", foto_id, nombre=True)


@router.get("/trabajos/{job_id}")
def estado(job_id: uuid.UUID, user: UserORM = Depends(get_current_user)):
    value = renderer.leer_estado(str(user.id), str(job_id))
    if value is None:
        raise HTTPException(404, "Trabajo no encontrado.")
    return value


@router.get("/trabajos/{job_id}/fotograma")
def fotograma(job_id: uuid.UUID, despues: int | None = Query(default=None, ge=0),
              user: UserORM = Depends(get_current_user)):
    """El fotograma más reciente del render en curso, para enseñarlo mientras se forma el vídeo.

    200 con el PNG, o 204 si todavía no hay ninguno o no hay uno más nuevo que `despues`. `X-Molcy-Fotograma` es su número
    en el guion (el cursor de `despues`); `X-Molcy-Orden`, su posición entre los rendidos, que es lo que va sobre
    `X-Molcy-Total` (ver `renderer.fotograma_reciente`).
    404 si el trabajo no existe o ya no está renderizando: entonces el vídeo (o el fallo) se pide por su ruta.
    """
    value = renderer.leer_estado(str(user.id), str(job_id))
    if value is None:
        raise HTTPException(404, "Trabajo no encontrado.")
    if value.get("estado") != "renderizando":
        raise HTTPException(404, "Este trabajo no está renderizando.")
    nuevo = {"Cache-Control": "no-store"}
    hallado = renderer.fotograma_reciente(str(user.id), str(job_id), value)
    if hallado is None or (despues is not None and hallado["indice"] <= despues):
        return Response(status_code=204, headers=nuevo)
    try:
        datos = hallado["ruta"].read_bytes()
    except OSError:
        return Response(status_code=204, headers=nuevo)
    return Response(datos, media_type="image/png", headers={
        **nuevo, "X-Molcy-Fotograma": str(hallado["indice"]), "X-Molcy-Orden": str(hallado["orden"]),
        "X-Molcy-Total": str(hallado["total"] or 0)})


@router.get("/trabajos/{job_id}/video")
def video(job_id: uuid.UUID, user: UserORM = Depends(get_current_user)):
    value = renderer.leer_estado(str(user.id), str(job_id))
    if value is None or value.get("estado") != "completo":
        raise HTTPException(404, "Vídeo no encontrado.")
    root = renderer.raiz_trabajo(str(user.id), str(job_id)) / "salida"
    path = root / Path(value["video"]).name
    if not path.is_file() or renderer.sha256_archivo(path) != value["video_sha256"]:
        raise HTTPException(409, "El vídeo ya no coincide con su SHA-256.")
    return FileResponse(path, media_type="video/mp4", filename=path.name)


class ConfiguracionRenderizador(BaseModel):
    modo: Literal["administrado", "existente"]
    blender: str | None = None
    motor: str | None = None


@router.put("/configuracion")
def configurar(req: ConfiguracionRenderizador, _user: UserORM = Depends(get_current_user)):
    with renderer._lock:
        _instalacion_estable()
        if renderer._reserved:
            raise HTTPException(409, "Espera a que termine el render antes de cambiar su instalación.")
        try:
            installation.configure(req.modo, req.blender, req.motor)
            renderer._ultima_capacidad.clear()
        except (ValueError, OSError) as exc:
            raise HTTPException(409, str(exc)) from exc
    # Fuera del cerrojo del renderizador: si hay un sondeo en curso, esperar aquí no debe bloquear a los demás.
    renderer.invalidar()
    return installation.status()


@router.get("/blender")
def estado_blender(_user: UserORM = Depends(get_current_user)):
    return installation.status()


@router.post("/blender", status_code=202)
def instalar_blender(_user: UserORM = Depends(get_current_user)):
    with renderer._lock:
        if addon.estado().get("estado") == "instalando":
            raise HTTPException(409, "Espera a que termine la instalación de Molecular Nodes.")
        if renderer._reserved:
            raise HTTPException(409, "Espera a que termine el render antes de instalar Blender.")
        try:
            return installation.start()
        except (ValueError, OSError) as exc:
            raise HTTPException(409, str(exc)) from exc


@router.post("/blender/cancelar")
def cancelar_blender(_user: UserORM = Depends(get_current_user)):
    try:
        return installation.cancel()
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("/trabajos")
def trabajos(user: UserORM = Depends(get_current_user)):
    return {"trabajos": renderer.listar(str(user.id))}


@router.post("/trabajos/{job_id}/cancelar")
def cancelar(job_id: uuid.UUID, user: UserORM = Depends(get_current_user)):
    value = renderer.cancelar(str(user.id), str(job_id))
    if value is None:
        raise HTTPException(404, "Trabajo no encontrado.")
    return value


@router.post("/trabajos/{job_id}/revelar")
def revelar(job_id: uuid.UUID, user: UserORM = Depends(get_current_user)):
    """Muestra el MP4 verificado o la carpeta del trabajo en el explorador local."""
    try:
        value = renderer.revelar(str(user.id), str(job_id))
    except (OSError, ValueError) as exc:
        raise HTTPException(409, str(exc)) from exc
    if value is None:
        raise HTTPException(404, "Trabajo no encontrado.")
    return value


@router.delete("/trabajos/{job_id}")
def eliminar(job_id: uuid.UUID, user: UserORM = Depends(get_current_user)):
    try:
        removed = renderer.eliminar(str(user.id), str(job_id))
    except (ValueError, OSError) as exc:
        raise HTTPException(409, str(exc)) from exc
    if not removed:
        raise HTTPException(404, "Trabajo no encontrado.")
    return {"eliminado": True}


@router.get("/trabajos/{job_id}/procedencia")
def procedencia(job_id: uuid.UUID, user: UserORM = Depends(get_current_user)):
    value = renderer.leer_estado(str(user.id), str(job_id))
    if value is not None and value.get("tipo") == "fotos":
        return _procedencia_de_fotos(user, job_id, value)
    if value is None or value.get("estado") != "completo":
        raise HTTPException(404, "Procedencia no encontrada.")
    video(job_id, user)  # Verifica también el hash del MP4 asociado.
    root = renderer.raiz_trabajo(str(user.id), str(job_id))
    import json
    try:
        build = json.loads((root / "salida" / Path(value["acta"]).name).read_text(encoding="utf-8"))
        manifests = {str(p.relative_to(root)): p.read_text(encoding="utf-8")
                     for p in (root / "escenas").rglob("MANIFEST.sha256")}
    except (OSError, ValueError) as exc:
        raise HTTPException(409, "La procedencia del vídeo no se pudo leer.") from exc
    return {"schema": "molcy.procedencia/1", "trabajo": value, "build": build, "manifiestos": manifests}


def _procedencia_de_fotos(user: UserORM, job_id: uuid.UUID, value: dict) -> dict:
    import json
    escena = value.get("escena_fotos")
    if value.get("estado") not in {"completo", "renderizando", "en_cola"} or not escena:
        raise HTTPException(404, "Procedencia no encontrada.")
    root = renderer.raiz_trabajo(str(user.id), str(job_id))
    salida = root / "salida"
    try:
        acta = salida / Path(escena["archivo"]).name
        if renderer.sha256_archivo(acta) != escena["sha256"]:
            raise HTTPException(409, "El acta de la escena ya no coincide con su SHA-256.")
        build = json.loads(acta.read_text(encoding="utf-8"))
        actas = {}
        for entrada in value.get("fotos") or []:
            fotos.leer_png(str(user.id), str(job_id), "foto", entrada["id"])   # verifica el SHA-256 de la foto entregada
            actas[entrada["id"]] = json.loads((salida / Path(entrada["acta"]).name).read_text(encoding="utf-8"))
        manifests = {str(p.relative_to(root)): p.read_text(encoding="utf-8")
                     for p in (root / "escenas").rglob("MANIFEST.sha256")}
    except (OSError, ValueError, KeyError, LookupError) as exc:
        raise HTTPException(409, "La procedencia de las fotos no se pudo leer.") from exc
    return {"schema": "molcy.procedencia/1", "trabajo": value, "build": build, "fotos": actas, "manifiestos": manifests}


@router.post("/trabajos/{job_id}/acceso")
def acceso_video(job_id: uuid.UUID, user: UserORM = Depends(get_current_user)):
    video(job_id, user)  # Sólo su dueño puede emitir un acceso temporal.
    token = secrets.token_urlsafe(32)
    now = time.monotonic()
    with _media_lock:
        for key, (expiry, _, _) in list(_media.items()):
            if expiry < now:
                _media.pop(key, None)
        if len(_media) >= 256:
            _media.pop(next(iter(_media)))
        _media[token] = (now + 3600, str(user.id), str(job_id))
    return {"ruta": f"/molcy/medios/{token}", "caduca_s": 3600}


@router.get("/medios/{token}", include_in_schema=False)
def medio(token: str):
    with _media_lock:
        grant = _media.get(token)
    if grant is None or grant[0] < time.monotonic():
        raise HTTPException(404, "Acceso al vídeo caducado.")
    _, user_id, job_id = grant
    value = renderer.leer_estado(user_id, job_id)
    if value is None or value.get("estado") != "completo":
        raise HTTPException(404, "Vídeo no encontrado.")
    path = renderer.raiz_trabajo(user_id, job_id) / "salida" / Path(value["video"]).name
    if not path.is_file() or renderer.sha256_archivo(path) != value["video_sha256"]:
        raise HTTPException(409, "El vídeo ya no coincide con su SHA-256.")
    return FileResponse(path, media_type="video/mp4", filename=path.name,
                        headers={"Cache-Control": "private, no-store"})
