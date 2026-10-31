"""Host mínimo del sidecar MolChat: estado y sesiones.

La UI no habla con el sidecar a ciegas: pregunta aquí si hay sidecar y pide
una sesión (token mh1 con scopes y caducidad corta) atada a SU cuenta. El
primer `/session` levanta el sidecar bajo demanda; un sidecar roto responde
503 con motivo y MolDesign sigue funcionando.
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from api.dependencies import get_current_user
from core.config import get_settings
from core.models import UserORM
from services.molchat_host import launcher, proveedores, sesion

router = APIRouter(prefix="/molchat-host", tags=["MolChatHost"])

#: La UI de escritorio es el cliente completo del panel: necesita los seis.
PERMISOS_DE_UI = frozenset({"read", "chat", "plan", "approve", "cancel", "transcribe"})
CONTRATO = "moldesign.molchat/1"


def _url_backend(request: Request) -> str:
    # ASGI expone el puerto del socket, no la cabecera Host que controla el cliente.
    server = request.scope.get("server")
    if server and isinstance(server[1], int) and 0 < server[1] < 65536:
        return f"http://127.0.0.1:{server[1]}"
    return get_settings().molchat_moldesign_url


class PropiedadesSolicitud(BaseModel):
    model_config = ConfigDict(extra="forbid")
    smiles: str = Field(min_length=1, max_length=2000)


@router.get("/contract")
def contrato(user: UserORM = Depends(get_current_user)) -> dict:
    """Versión y capacidades explícitas; no implica paridad de todo el catálogo."""
    return {"contract": CONTRATO, "capabilities": ["properties/1", "platform-actions/1"]}


@router.post("/properties")
async def propiedades(payload: PropiedadesSolicitud,
                       user: UserORM = Depends(get_current_user)) -> dict:
    """Descriptores reales del producto; se abstiene si la validación falla."""
    def calcular() -> dict:
        from chem.validator import validate_smiles
        from chem.properties import calculate_properties

        validacion = validate_smiles(payload.smiles)
        if not validacion.is_valid or not validacion.canonical_smiles:
            raise HTTPException(422, detail={"errors": validacion.errors})
        props = calculate_properties(validacion.canonical_smiles, run_admet_ai=False)
        return {
            "contract": "properties/1",
            "canonical_smiles": validacion.canonical_smiles,
            "source": f"MolDesign / {validacion.motor_canonico}",
            "warnings": validacion.warnings,
            "methods": {
                "mw": "RDKit Descriptors.MolWt (masa molecular promedio)",
                "logp": "RDKit Crippen.MolLogP (contribuciones atómicas)",
                "tpsa": "RDKit rdMolDescriptors.CalcTPSA (Ertl)",
                "hbd": "RDKit Lipinski.NHOHCount (enlaces N-H y O-H)",
                "hba": "RDKit Lipinski.NOCount (número de átomos de N y O)",
            },
            "properties": {
                "mw": props.molecular_weight, "logp": props.log_p,
                "tpsa": props.tpsa, "hbd": props.hbd, "hba": props.hba,
                "rot_bonds": props.rotatable_bonds,
                "heavy_atoms": props.heavy_atom_count, "rings": props.ring_count,
            },
        }
    return await asyncio.to_thread(calcular)


class SesionRespuesta(BaseModel):
    model_config = {"extra": "forbid"}

    token: str = Field(description="Sesión mh1 para el sidecar (Bearer, corta vida)")
    url: str = Field(description="URL loopback del sidecar (el puerto varía)")
    expira_en_s: int = Field(description="Segundos de vida del token")
    scopes: list[str] = Field(description="Permisos concedidos")


@router.get("/status")
def estado(request: Request) -> dict:
    """¿Hay sidecar? ¿Cuál? ¿En marcha? Sin autenticar: no expone datos."""
    return launcher.obtener_lanzador(_url_backend(request)).estado()


@router.post("/session", response_model=SesionRespuesta)
def sesion_nueva(request: Request, user: UserORM = Depends(get_current_user)) -> SesionRespuesta:
    """Levanta el sidecar si duerme y acuña una sesión para esta cuenta."""
    ajustes = get_settings()
    lanzador = launcher.obtener_lanzador(_url_backend(request))
    try:
        url = lanzador.arrancar()
    except launcher.LanzadorError as exc:
        raise HTTPException(503, str(exc)) from exc
    try:
        token = sesion.acunar(str(user.id), PERMISOS_DE_UI, ajustes.molchat_ttl_s)
    except sesion.SesionMolChatError as exc:
        raise HTTPException(503, str(exc)) from exc
    return SesionRespuesta(token=token, url=url,
                           expira_en_s=ajustes.molchat_ttl_s,
                           scopes=sorted(PERMISOS_DE_UI))


# ── Proveedores de IA por cuenta ─────────────────────────────────────────
# La clave la introduce la interfaz de MolDesign y se guarda por cuenta. Ninguna
# respuesta devuelve una clave completa; sólo `credencial` la entrega, y sólo al
# sidecar (sesión mh1), y sólo si la cuenta autorizó el host del catálogo.


class ClaveSolicitud(BaseModel):
    model_config = ConfigDict(extra="forbid")
    api_key: str = Field(min_length=8, max_length=512)
    host_visto: str = Field(min_length=1, max_length=255,
                            description="Host que la interfaz mostró antes de pedir la clave")
    modelo: str | None = Field(default=None, max_length=120)


class ActivoSolicitud(BaseModel):
    model_config = ConfigDict(extra="forbid")
    proveedor: str | None = Field(default=None, max_length=32)
    modelo: str | None = Field(default=None, max_length=120)


class CredencialSolicitud(BaseModel):
    model_config = ConfigDict(extra="forbid")
    proveedor: str | None = Field(default=None, max_length=32)
    host: str = Field(min_length=1, max_length=255)


def _responder(operacion):
    try:
        return operacion()
    except proveedores.ProveedorError as exc:
        raise HTTPException(exc.estado, exc.detalle) from exc


def _sesion_de_sidecar(request: Request) -> bool:
    return request.headers.get("authorization", "").startswith("Bearer mh1.")


@router.get("/proveedores")
def proveedores_de_cuenta(user: UserORM = Depends(get_current_user)) -> dict:
    """Catálogo verificado de MolChat y el estado de esta cuenta. Sin claves."""
    return proveedores.estado(str(user.id))


@router.put("/proveedores/{proveedor}/clave")
def guardar_clave(proveedor: str, payload: ClaveSolicitud,
                  user: UserORM = Depends(get_current_user)) -> dict:
    """«Guardar y autorizar envío a <host>»: clave cifrada por cuenta y autorización del destino."""
    return _responder(lambda: proveedores.guardar_y_autorizar(
        str(user.id), proveedor, payload.api_key, payload.host_visto, payload.modelo))


@router.delete("/proveedores/{proveedor}/clave")
def retirar_clave(proveedor: str, user: UserORM = Depends(get_current_user)) -> dict:
    return _responder(lambda: proveedores.retirar_clave(str(user.id), proveedor))


@router.put("/proveedores/activo")
def elegir_activo(payload: ActivoSolicitud, user: UserORM = Depends(get_current_user)) -> dict:
    return _responder(lambda: proveedores.elegir_activo(str(user.id), payload.proveedor, payload.modelo))


@router.post("/credencial")
def credencial(payload: CredencialSolicitud, request: Request,
               user: UserORM = Depends(get_current_user)) -> dict:
    """Clave y modelo para una llamada del sidecar. Sólo con sesión mh1; nunca desde la interfaz."""
    if not _sesion_de_sidecar(request):
        raise HTTPException(403, "las credenciales sólo se entregan al sidecar")
    return _responder(lambda: proveedores.credencial(str(user.id), payload.proveedor, payload.host))
