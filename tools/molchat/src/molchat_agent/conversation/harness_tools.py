"""MolChat-owned tools, with product operations delegated through typed ports."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
import asyncio
import re
import secrets
import unicodedata
from typing import Any
import httpx

from ..bridge import BridgeError, MolDesignBridge
from .pubchem import PubChemError, search_compounds
from .tool_loop import Tool
from .intents import KNOWN_SMILES, find_name
from .tools import ToolBackend, ToolError


def _named_input(maximum: int) -> dict[str, Any]:
    return {"type": "object", "properties": {"name": {"type": "string", "maxLength": maximum}},
            "required": ["name"], "additionalProperties": False}


def pubchem_tool(bridge: MolDesignBridge, client: httpx.AsyncClient) -> Tool:
    async def lookup(args: dict[str, Any]) -> dict[str, Any]:
        try:
            result = await search_compounds(args["name"], client=client, authorize=bridge.authorize_pubchem)
        except PermissionError:
            return {"status": "permission_denied", "message": "PubChem está desautorizado o sin red."}
        except (PubChemError, BridgeError):
            return {"status": "unavailable", "message": "No se pudo consultar PubChem o verificar el permiso."}
        return {"status": "ok" if result.matches else "not_found", "truncated": result.truncated,
                "methodology": {"source": "https://pubchem.ncbi.nlm.nih.gov/docs/glossary",
                    "hba": "PubChem refiere una clasificación de 1997; las reglas detalladas y su aplicación a esta molécula no se han comprobado aquí.",
                    "xlogp": "XLogP de PubChem; no es necesariamente el LogP de RDKit."},
                "matches": [{"cid": item.cid, "name": item.name, "source": item.source,
                             "properties": item.properties, "properties_available": item.properties_available}
                            for item in result.matches]}

    return Tool("pubchem_lookup", "Consulta identidad y propiedades públicas de un compuesto por nombre en PubChem. "
                "Devuelve la fuente y los datos disponibles; no modifica el editor.",
                _named_input(120), lookup)


def receptor_catalog_tool(bridge: MolDesignBridge) -> Tool:
    """Read only the account-scoped catalog; never change a case or receptor."""
    cached: list[dict[str, Any]] | None = None
    async def search(args: dict[str, Any]) -> dict[str, Any]:
        nonlocal cached
        page_text = args.get("page", "1")
        if not page_text.isascii() or not page_text.isdigit() or not 1 <= int(page_text) <= 1000:
            return {"status": "invalid", "message": "La página debe ser un entero positivo."}
        section = args.get("section", "all")
        availability = args.get("availability", "all")
        if section not in {"all", "verificado", "demostracion"} or availability not in {"all", "available", "unavailable"}:
            return {"status": "invalid", "message": "Filtro de catálogo no válido."}
        if not getattr(bridge, "token", None):
            return {"status": "unavailable", "message": "Se necesita una sesión de MolDesign."}
        if cached is None:
            try:
                response = await bridge.client.get("/targets/", headers={"Authorization": f"Bearer {bridge.token}"},
                                                   timeout=60, follow_redirects=False)
                if response.status_code != 200 or len(response.content) > 5_000_000:
                    return {"status": "unavailable", "message": "No se pudo consultar el catálogo de MolDesign."}
                data = response.json()
                if not isinstance(data, list) or not all(isinstance(row, dict) for row in data):
                    return {"status": "unavailable", "message": "El catálogo devolvió datos incompatibles."}
                cached = data
            except (httpx.RequestError, ValueError):
                return {"status": "unavailable", "message": "No se pudo consultar el catálogo de MolDesign."}
        def normalize(value: str) -> str:
            return "".join(c for c in unicodedata.normalize("NFKD", value.casefold()) if not unicodedata.combining(c))
        query = normalize(args["query"].strip())
        fields = ("pdb_id", "name", "organism", "structural_family", "therapeutic_family")
        matched = [row for row in cached if query == "*" or any(query in normalize(str(row.get(k) or "")) for k in fields)]
        if section != "all":
            matched = [row for row in matched if row.get("seccion_catalogo") == section]
        if availability != "all":
            expected = availability == "available"
            matched = [row for row in matched if row.get("disponible") is expected]
        page, size = int(page_text), 10
        selected = matched[(page - 1) * size:page * size]
        keys = ("id", "pdb_id", "name", "organism", "chain", "structural_family", "therapeutic_family",
                "is_private", "disponible", "motivo_no_disponible", "seccion_catalogo", "calibracion", "avisos_catalogo")
        return {"status": "ok", "source": "Catálogo de receptores de MolDesign", "query": args["query"],
                "page": page, "total": len(matched), "has_next": page * size < len(matched),
                "section": section, "availability": availability,
                "receptors": [{key: row.get(key) for key in keys} for row in selected]}
    schema = {"type": "object", "properties": {"query": {"type": "string", "maxLength": 120},
               "page": {"type": "string", "maxLength": 4}, "section": {"type": "string", "maxLength": 20},
               "availability": {"type": "string", "maxLength": 20}}, "required": ["query"], "additionalProperties": False}
    return Tool("search_receptors", "Consulta el catálogo de receptores accesible para la cuenta de MolDesign. "
                "Busca por nombre, PDB, organismo o familia; usa query='*' para listar y page para navegar. "
                "Filtros opcionales: section=verificado/demostracion y availability=available/unavailable. "
                "Disponible no equivale a verificado ni calibrado. No modifica el caso ni inicia cálculos.", schema, search)


def random_receptor_tool(catalog: Tool) -> Tool:
    """Sample the complete account-scoped catalog without modifying a case."""
    async def pick(args: dict[str, Any]) -> dict[str, Any]:
        section = args.get("section", "all")
        if section not in {"all", "verificado", "demostracion"}:
            return {"status": "invalid", "message": "Sección de catálogo no válida."}
        first = await catalog.execute({"query": "*", "page": "1"})
        if first.get("status") != "ok":
            return {"status": "unavailable", "message": "No se pudo consultar el catálogo."}
        total = first.get("total")
        if type(total) is not int or total < 0 or total > 10000:
            return {"status": "unavailable", "message": "No se pudo leer el catálogo completo."}
        rows = list(first.get("receptors", []))
        for page in range(2, (total + 9) // 10 + 1):
            result = await catalog.execute({"query": "*", "page": str(page)})
            if result.get("status") != "ok" or result.get("total") != total:
                return {"status": "unavailable", "message": "No se pudo leer el catálogo completo."}
            rows.extend(result.get("receptors", []))
        if len(rows) != total:
            return {"status": "unavailable", "message": "El catálogo está incompleto."}
        counts: dict[str, int] = {}
        for row in rows:
            value = row.get("pdb_id")
            if isinstance(value, str):
                key = value.upper()
                counts[key] = counts.get(key, 0) + 1
        candidates = [row for row in rows if isinstance(row.get("pdb_id"), str)
                      and re.fullmatch(r"[A-Za-z0-9_-]{1,64}", row["pdb_id"])
                      and counts[row["pdb_id"].upper()] == 1 and row.get("disponible") is not False
                      and (section == "all" or row.get("seccion_catalogo") == section)]
        if not candidates:
            return {"status": "not_found", "message": "No hay receptores seleccionables para ese filtro."}
        selected = secrets.choice(candidates)
        return {"status": "ok", "source": first["source"], "selection": "aleatoria",
                "eligible_count": len(candidates), "receptor": selected}

    schema = {"type": "object", "properties": {"section": {"type": "string", "maxLength": 20}},
              "required": [], "additionalProperties": False}
    return Tool("pick_random_receptor", "Elige al azar un receptor seleccionable del catálogo completo accesible a la cuenta. "
                "Úsala solo si el usuario pidió una elección aleatoria; filtra section=verificado o demostracion solo si lo pidió. "
                "Informa el receptor elegido y su sección real; no modifica un caso ni inicia docking. "
                "Para asignarlo después usa assign_case_receptor con el PDB devuelto.", schema, pick)


def create_case_tool(request_case: Callable[[str], Awaitable[dict[str, Any]]]) -> Tool:
    """MolChat requests a product action; only the host can confirm its result."""
    async def create(args: dict[str, Any]) -> dict[str, Any]:
        result = await request_case(args["name"])
        if not isinstance(result, dict) or result.get("status") not in {"created", "exists", "failed", "unknown"}:
            return {"status": "unknown", "message": "No se confirmó el resultado en MolDesign."}
        return {"status": result["status"], "name": args["name"]}

    return Tool("create_case", "Solicita a MolDesign crear un caso nuevo solo si el usuario pidió crearlo explícitamente. "
                "Cuando el usuario pide usar un caso nombrado, no lo crees: usa la herramienta de la acción solicitada. "
                "Informa éxito solo cuando el resultado del host sea created.", _named_input(100), create)


def load_case_smiles_tool(request_load: Callable[[str, str], Awaitable[dict[str, Any]]]) -> Tool:
    """Validate a structure, then ask the host to apply it to one named case."""
    async def load(args: dict[str, Any]) -> dict[str, Any]:
        case_name, smiles = args["case_name"].strip(), args["smiles"].strip()
        try:
            from rdkit import Chem
            molecule = await asyncio.to_thread(Chem.MolFromSmiles, smiles)
        except ImportError:
            return {"status": "unavailable", "message": "No está disponible la validación de SMILES."}
        except Exception:
            return {"status": "invalid_smiles", "message": "No se pudo interpretar el SMILES."}
        if molecule is None:
            return {"status": "invalid_smiles", "message": "El SMILES no es válido; no se modificó el caso."}
        result = await request_load(case_name, smiles)
        valid = {"applied", "not_found", "ambiguous", "busy", "failed", "unknown"}
        status = result.get("status") if isinstance(result, dict) else "unknown"
        if status not in valid:
            status = "unknown"
        return {"status": status, "case_name": case_name, "smiles": smiles}

    schema = {"type": "object", "properties": {
        "case_name": {"type": "string", "maxLength": 100},
        "smiles": {"type": "string", "maxLength": 2000}},
        "required": ["case_name", "smiles"], "additionalProperties": False}
    return Tool("load_case_smiles", "Carga un SMILES explícito en el campo del caso indicado en MolDesign. "
                "Úsala solo si el usuario pide cargarlo y se conocen el caso y el SMILES exactos. "
                "Si no son inequívocos pregunta. Confirma únicamente status=applied; no afirma que Ketcher "
                "dibujó o que se guardó en disco sin confirmación adicional.", schema, load)


def assign_case_receptor_tool(request_assign: Callable[[str, str], Awaitable[dict[str, Any]]]) -> Tool:
    async def assign(args: dict[str, Any]) -> dict[str, Any]:
        case_name, pdb_id = args["case_name"].strip(), args["pdb_id"].strip().upper()
        import re
        if not re.fullmatch(r"[A-Z0-9_-]{1,64}", pdb_id):
            return {"status": "invalid", "message": "Identificador de receptor no válido."}
        result = await request_assign(case_name, pdb_id)
        statuses = {"applied", "already_selected", "case_not_found", "case_ambiguous", "receptor_not_found",
                    "receptor_ambiguous", "unavailable", "locked", "busy", "save_failed", "failed", "unknown", "needs_selection"}
        status = result.get("status") if isinstance(result, dict) else "unknown"
        if status not in statuses:
            status = "unknown"
        return {"status": status, "case_name": case_name, "pdb_id": pdb_id}
    schema = {"type": "object", "properties": {"case_name": {"type": "string", "maxLength": 100},
              "pdb_id": {"type": "string", "maxLength": 64}}, "required": ["case_name", "pdb_id"],
              "additionalProperties": False}
    return Tool("assign_case_receptor", "Asigna al caso indicado un receptor del catálogo por su PDB ID exacto. "
                "Úsala solo si el usuario pidió asignarlo y la identidad es inequívoca. Para 'único receptor verificado' "
                "consulta primero search_receptors y comprueba total=1. No ejecuta docking. Solo confirma si el host responde applied o already_selected.", schema, assign)


def evaluation_status_tool(bridge: MolDesignBridge) -> Tool:
    """Read-only: report what MolDesign says about a task it already accepted."""
    async def status(args: dict[str, Any]) -> dict[str, Any]:
        task_id = args["task_id"].strip()
        if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", task_id):
            return {"status": "invalid", "message": "Identificador de tarea no válido."}
        if not getattr(bridge, "token", None):
            return {"status": "unavailable", "message": "Se necesita una sesión de MolDesign."}
        try:
            response = await bridge.client.get(f"/evaluation/status/{task_id}", timeout=30, follow_redirects=False,
                                               headers={"Authorization": f"Bearer {bridge.token}"})
            if response.status_code in (403, 404):
                return {"status": "not_found", "task_id": task_id}
            if response.status_code != 200 or len(response.content) > 5_000_000:
                return {"status": "unavailable", "message": "No se pudo consultar el estado en MolDesign."}
            data = response.json()
        except (httpx.RequestError, ValueError):
            return {"status": "unavailable", "message": "No se pudo consultar el estado en MolDesign."}
        if not isinstance(data, dict) or data.get("task_id") != task_id or not isinstance(data.get("status"), str):
            return {"status": "unavailable", "message": "MolDesign devolvió un estado incompatible."}
        safe: dict[str, Any] = {"status": "ok", "task_id": task_id, "task_status": data["status"],
                                "progress": data.get("progress") if type(data.get("progress")) is int else None,
                                "source": "MolDesign GET /evaluation/status"}
        if isinstance(data.get("error"), str):
            safe["error"] = data["error"][:300]
        result = data.get("result")
        if data["status"] == "SUCCESS" and isinstance(result, dict):
            keep = ("molecule_id", "affinity_kcal", "target_name", "vina_version", "vina_random_seed")
            safe["result"] = {key: result.get(key) for key in keep if result.get(key) is not None}
            calibration = result.get("target_calibracion")
            if isinstance(calibration, dict):
                safe["result"]["target_calibracion"] = calibration
            warnings = result.get("scientific_warnings")
            safe["result"]["scientific_warnings"] = len(warnings) if isinstance(warnings, list) else None
            safe["note"] = ("affinity_kcal es la energía de Vina de la mejor pose, no una energía libre ni un Ki. "
                            "Conserva la calibración del receptor tal como llega; ausente no significa calibrado.")
        return safe
    schema = {"type": "object", "properties": {"task_id": {"type": "string", "maxLength": 128}},
              "required": ["task_id"], "additionalProperties": False}
    return Tool("get_evaluation_status", "Consulta en MolDesign el estado de una tarea de evaluación que el host ya aceptó "
                "(task_id de evaluate_case). Solo lectura: no inicia, cancela ni reintenta. Informa task_status y progreso; "
                "si es SUCCESS, la afinidad de Vina y la calibración del receptor. No interpretes la afinidad como actividad.",
                schema, status)


def evaluate_case_tool(request_evaluation: Callable[[str], Awaitable[dict[str, Any]]]) -> Tool:
    async def evaluate(args: dict[str, Any]) -> dict[str, Any]:
        name = args["case_name"].strip()
        result = await request_evaluation(name)
        statuses = {"started", "started_unregistered", "case_not_found", "case_ambiguous", "busy", "blocked", "needs_review", "failed", "unknown"}
        if not isinstance(result, dict) or result.get("status") not in statuses:
            return {"status": "unknown", "case_name": name}
        safe = {"status": result["status"], "case_name": name}
        if isinstance(result.get("task_id"), str):
            safe["task_id"] = result["task_id"]
        if isinstance(result.get("reason"), str):
            safe["reason"] = result["reason"]
        return safe
    schema = {"type": "object", "properties": {"case_name": {"type": "string", "maxLength": 100}},
              "required": ["case_name"], "additionalProperties": False}
    return Tool("evaluate_case", "Solicita iniciar la evaluación del caso nombrado solo si el usuario pidió ejecutarla. "
                "Usa los inputs y comprobaciones de MolDesign. No modifica parámetros ni inicia tareas por iniciativa propia. "
                "'started' confirma aceptación y registro, no resultados; 'started_unregistered' confirma aceptación sin registro. "
                "Si el resultado es desconocido no reintentes sin revisar el caso.", schema, evaluate)


def properties_tool(backend: ToolBackend) -> Tool:
    """Use MolDesign's existing calculation, with no invented property values."""
    async def calculate(args: dict[str, Any]) -> dict[str, Any]:
        name = args["name"]
        known = find_name(name)
        smiles = KNOWN_SMILES.get(known, name) if known else name
        try:
            record = await backend.properties(smiles)
        except ToolError:
            return {"status": "unavailable", "message": "No se pudieron calcular propiedades para esa entrada."}
        identity = "unverified"
        verifier = None
        if smiles == record.smiles:
            identity = "same"
            verifier = "SMILES idéntico"
        else:
            try:
                from rdkit import Chem, rdBase
                left, right = Chem.MolFromSmiles(smiles), Chem.MolFromSmiles(record.smiles)
                if left is not None and right is not None:
                    a = Chem.MolToSmiles(left, canonical=True, isomericSmiles=True)
                    b = Chem.MolToSmiles(right, canonical=True, isomericSmiles=True)
                    identity = "same" if a == b else "changed"
                    verifier = f"SMILES canónico isomérico RDKit {rdBase.rdkitVersion}"
            except ImportError:
                pass
        return {"status": "ok", "name": name, "properties": record.props, "source": record.source,
                "methods": record.methods, "structure": {"input_smiles": smiles,
                    "canonical_smiles": record.smiles, "identity": identity,
                    "verifier": verifier, "warnings": record.warnings}}

    return Tool("compute_properties", "Calcula propiedades con MolDesign para un SMILES o un nombre "
                "reconocido. Para comparar con PubChem usa exactamente su SMILES devuelto, no el nombre. "
                "Devuelve identidad y transformaciones comprobables.", _named_input(2000), calculate)
