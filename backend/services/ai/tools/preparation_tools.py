"""
services/ai/tools/preparation_tools.py

MolChat lee la comprobación previa de Evaluación.

Problema resuelto
-----------------
A «¿por qué está bloqueado el receptor 8HFI?» o «¿está listo 7E2Y para
acoplar?» MolChat contestaba de memoria, cuando el producto ya calcula la
respuesta exacta: la comprobación previa del servidor
(`POST /evaluation/preflight`, el panel «Comprobación previa» de Evaluación),
con cada control —huecos junto al sitio, metales retirados, cadenas,
protonación, caja, calibración del receptor…— en uno de cuatro estados
(bloquea, advertencia, no evaluado, pasa) y con su motivo.

Esta herramienta devuelve ESE informe, el mismo que pinta el panel, sin
ejecutar docking. El código decide lo factual; el modelo sólo lo explica.

No es la pestaña Preparación. Esa pestaña audita una corrida ya guardada con su
propio informe (`POST /evaluation/dossier/{id}/preparacion`: tautómero, unión
covalente, membrana, decisiones…), y la respuesta lo dice para no mandar al
investigador a buscar ahí lo que contestó.

Sin ligando se piden los controles con un ligando de sondeo (fenol) y se
quitan los del ligando: describir un SMILES que nadie escribió sería inventar.
"""

from __future__ import annotations

import re
import uuid

from services.ai.tool_registry import ToolDef, get_tool_registry

#: Ligando para pedir los controles del receptor y del protocolo cuando la
#: pregunta no trae molécula. Sus controles no se devuelven. Fenol y no metano:
#: el validador rechaza el metano, y un ligando inválido podía dejar sin evaluar
#: controles que en una corrida real sí se evalúan.
_LIGANDO_DE_SONDEO = "Oc1ccccc1"

_TITULOS = (
    ("bloquea", "Bloquean la corrida"),
    ("advertencia", "Advertencias"),
    ("no_evaluado", "No se pudieron evaluar"),
)

#: Un identificador de receptor: código PDB o receptor propio (`USR_…`).
_RECEPTOR = re.compile(r"^(?:[0-9][A-Za-z0-9]{3}|USR_[A-Za-z0-9_]{1,6})$")


def _recortar(texto: str, n: int = 240) -> str:
    texto = " ".join(str(texto or "").split())
    return texto if len(texto) <= n else texto[: n - 1] + "…"


def resumir_informe(informe: dict, con_ligando: bool) -> str:
    """El informe de preflight en texto, sin interpretar nada."""
    receptor = informe.get("receptor") or {}
    ligando = informe.get("ligand") or {}
    controles = [
        c for c in informe.get("controls") or []
        if con_ligando or not str(c.get("code", "")).startswith("LIGANDO_")
    ]
    cabecera = (
        f"Comprobación previa de {receptor.get('pdb_id', '?')} (cadena {receptor.get('chain') or '?'}, "
        f"origen {receptor.get('origin') or 'desconocido'})"
    )
    if con_ligando:
        cabecera += f" con el ligando {ligando.get('canonical_smiles') or ligando.get('input_smiles')}"
    else:
        cabecera += " — sin ligando: sólo los controles del receptor y del protocolo"
    lineas = [cabecera + "."]
    for estado, titulo in _TITULOS:
        del_estado = [c for c in controles if c.get("state") == estado]
        if not del_estado:
            continue
        lineas.append(f"{titulo} ({len(del_estado)}):")
        for c in del_estado:
            lineas.append(
                f"- {c.get('title')} [{c.get('code')}]: {_recortar(c.get('observation'))} "
                f"Motivo: {_recortar(c.get('reason'), 180)}"
            )
    pasan = sum(1 for c in controles if c.get("state") == "pasa")
    lineas.append(f"Pasan {pasan} controles.")
    huella = str(informe.get("input_fingerprint") or "").replace("sha256:", "")[:12]
    if huella:
        lineas.append(f"Es el mismo informe que la comprobación previa de Evaluación (huella {huella}…).")
    return "\n".join(lineas)


def respuesta_breve(informe: dict, con_ligando: bool) -> str:
    """La respuesta al investigador, escrita por el código y no por el modelo.

    Medido en la cápsula el 2026-10-10: con el informe delante, Qwen2.5-1.5B
    contestó «El receptor 8HFI está bloqueado debido a varias advertencias»
    cuando ningún control bloqueaba. Aceptaba la premisa de la pregunta. Aquí la
    primera frase dice si hay bloqueo o no, y la premisa falsa queda desmentida.
    """
    receptor = (informe.get("receptor") or {}).get("pdb_id", "?")
    controles = [
        c for c in informe.get("controls") or []
        if con_ligando or not str(c.get("code", "")).startswith("LIGANDO_")
    ]
    bloquean = [c for c in controles if c.get("state") == "bloquea"]
    avisan = sum(1 for c in controles if c.get("state") == "advertencia")
    sin_evaluar = sum(1 for c in controles if c.get("state") == "no_evaluado")
    alcance = "" if con_ligando else " por el receptor ni por el protocolo"
    if bloquean:
        titulos = "; ".join(str(c.get("title")) for c in bloquean)
        frase = (
            f"Sí: según la comprobación previa de Evaluación, {len(bloquean)} control(es) "
            f"bloquean la corrida contra {receptor}: {titulos}. El motivo de cada uno está en el "
            "informe."
        )
    else:
        frase = (
            f"Según la comprobación previa de Evaluación, {receptor} no está bloqueado{alcance}: "
            "ningún control bloquea la corrida."
        )
    frase += (
        f" Tiene {avisan} advertencia(s) y {sin_evaluar} control(es) sin evaluar; el informe "
        "dice el motivo de cada uno. Las advertencias no impiden lanzar: la decisión es tuya."
    )
    if not con_ligando:
        frase += " Con el SMILES de un ligando concreto compruebo también los controles del ligando."
    frase += (
        " La pestaña Preparación es otra cosa: audita una corrida ya guardada con sus "
        "propios requisitos."
    )
    return frase


async def consultar_preparacion(
    target_pdb: str, smiles: str = "", chain: str = "", user_id: str = ""
) -> tuple[str, str] | None:
    """`(texto del informe, respuesta breve)`, o None si el receptor no es un identificador.

    Llama a la misma función que atiende `POST /evaluation/preflight`.
    """
    receptor = (target_pdb or "").strip()
    receptor = receptor if receptor.upper().startswith("USR_") else receptor.upper()
    if not _RECEPTOR.match(receptor):
        return None
    from api.routers.evaluation import PreflightRequest, evaluation_preflight
    from core.database import get_db_session
    from core.models import UserORM

    smiles = (smiles or "").strip()
    async with get_db_session() as db:
        usuario = None
        if user_id:
            try:
                usuario = await db.get(UserORM, uuid.UUID(user_id))
            except (ValueError, TypeError):
                usuario = None
        informe = await evaluation_preflight(
            data=PreflightRequest(
                smiles=smiles or _LIGANDO_DE_SONDEO,
                target_pdb_id=receptor,
                chain=(chain or "").strip() or None,
            ),
            db=db,
            current_user=usuario,
        )
    con_ligando = bool(smiles)
    return resumir_informe(informe, con_ligando), respuesta_breve(informe, con_ligando)


_SIN_RECEPTOR = (
    "Necesito el identificador del receptor (un código PDB como 7E2Y, o el de un "
    "receptor propio) para leer su comprobación previa."
)


async def check_preparation(
    target_pdb: str = "",
    smiles: str = "",
    chain: str = "",
    user_id: str = "",
) -> str:
    resultado = await consultar_preparacion(target_pdb, smiles, chain, user_id)
    if resultado is None:
        return _SIN_RECEPTOR
    texto, breve = resultado
    return f"{texto}\n{breve}"


def register_preparation_tools():
    registry = get_tool_registry()
    registry.register(ToolDef(
        name="check_preparation",
        clase="calculo",
        procedencia="comprobación previa del servidor (la misma que el panel de Evaluación)",
        description=(
            "Lee la comprobación previa de Evaluación: los controles REALES de un receptor "
            "(PDB ID) y, si se da, de un ligando (SMILES), sin ejecutar docking. Devuelve qué "
            "controles bloquean la corrida, cuáles avisan y cuáles no se pudieron evaluar "
            "(huecos junto al sitio, metales retirados, cadenas, protonación, caja, "
            "calibración), con su motivo. Úsala para '¿por qué está bloqueado el receptor X?', "
            "'¿está listo X para acoplar?', '¿qué falta para lanzar la evaluación?'."
        ),
        parameters={
            "target_pdb": {"type": "string", "required": True},
            "smiles": {"type": "string", "required": False},
            "chain": {"type": "string", "required": False},
            "user_id": {"type": "string", "required": False},
        },
        offline=True,
        category="docking",
        fn=check_preparation,
    ))
