"""
services/ai/tools/session_tools.py

Tools que operan sobre la CONVERSACIÓN ACTUAL de MolChat (no sobre la DB).

rank_session_molecules: ranking determinista de las moléculas que se vieron
en esta conversación (por peso molecular, score, afinidad, etc.).

Resolver el razonamiento comparativo N>2 de forma DETERMINISTA: el modelo
Qwen 1.5B falla "cuál tiene menor peso molecular?" entre 3+ moléculas del
historial — esta tool le da la tabla ya ordenada, el modelo solo redacta.
"""

from __future__ import annotations


from services.ai.tool_registry import ToolDef, get_tool_registry


def _extract_session_molecules() -> list[dict]:
    """Extraer las moléculas (nombre/SMILES + tool results) de la conversación
    actual. Fuente: system messages con tool results (formato:
    'compute_properties (aspirina): MW: 180.2 Da, LogP: 1.31, ...').
    """
    from services.ai.chat_service import get_chat_service, ChatService

    cs = get_chat_service()
    conv = cs.get_conversation()
    if not conv:
        return []

    # Recolectar tool results con nombre
    named_text = " ".join(
        m.get("content", "")
        for m in conv.messages
        if m.get("role") == "system"
        and "Sistema: resultados de herramientas ejecutadas" in m.get("content", "")
    )
    named = ChatService._parse_named_tool_values(named_text)

    molecules: list[dict] = []
    for name, values_by_key in named.items():
        flat = {k: v[0] if isinstance(v, list) and v else v for k, v in values_by_key.items()}
        # Asegurar un "name" legible: usar el nombre del tool result si es
        # corto, o truncar el SMILES
        display = name if len(name) <= 40 else name[:40]
        molecules.append({
            "name": display,
            "smiles": display if display.startswith(("C", "N", "O", "c", "n", "o")) else "",
            "molecular_weight": flat.get("molecular_weight"),
            "log_p": flat.get("log_p"),
            "tpsa": flat.get("tpsa"),
            "hbd": flat.get("hbd"),
            "hba": flat.get("hba"),
            "rotatable_bonds": flat.get("rotatable_bonds"),
            "heavy_atoms": flat.get("heavy_atoms"),
            "rings": flat.get("rings"),
            "affinity_kcal": flat.get("affinity_kcal"),
            "total_score": flat.get("total_score"),
        })

    # Deduplicar por nombre
    seen = set()
    uniq = []
    for mol in molecules:
        key = mol["name"]
        if key not in seen:
            seen.add(key)
            uniq.append(mol)
    return uniq


def _safe_float(v) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


async def rank_session_molecules(
    metric: str = "molecular_weight",
    order: str = "asc",
    limit: str = "10",
) -> str:
    """Ranking determinista de las moléculas vistas en esta conversación.

    metric: molecular_weight | log_p | tpsa | hbd | hba | rotatable_bonds |
            heavy_atoms | rings | affinity_kcal | total_score
    order:  asc (menor a mayor) | desc (mayor a menor)
    """
    molecules = _extract_session_molecules()
    if not molecules:
        return (
            "No hay moléculas registradas en esta conversación. "
            "Calculá propiedades de alguna molécula primero (ej. "
            "'calcula propiedades de la aspirina')."
        )

    valid_metrics = {
        "molecular_weight", "log_p", "tpsa", "hbd", "hba",
        "rotatable_bonds", "heavy_atoms", "rings",
        "affinity_kcal", "total_score",
    }
    if metric not in valid_metrics:
        metric = "molecular_weight"

    # Filtrar las que tienen el campo
    ranked = []
    for mol in molecules:
        val = _safe_float(mol.get(metric))
        if val is not None:
            mol["_val"] = val
            ranked.append(mol)

    if not ranked:
        return f"Ninguna molécula de la conversación tiene datos de '{metric}'."

    ranked.sort(key=lambda m: m["_val"], reverse=(order.lower() == "desc"))

    try:
        lim = max(1, min(int(limit), 20))
    except (TypeError, ValueError):
        lim = 10
    ranked = ranked[:lim]

    # Unidad según métrica
    unit = ""
    if metric == "molecular_weight":
        unit = " Da"
    elif metric == "tpsa":
        unit = " A²"
    elif metric == "affinity_kcal":
        unit = " kcal/mol"
    elif metric == "total_score":
        unit = "/100"

    lines = [f"[Ranking de {len(ranked)} moléculas por {metric} ({order})]"]
    for i, mol in enumerate(ranked, 1):
        val = mol["_val"]
        # Precisión por métrica: LogP y afinidad con 2 decimales, MW/TPSA/score 1
        if metric in ("log_p", "affinity_kcal"):
            val_str = f"{val:.2f}"
        else:
            val_str = f"{val:.1f}"
        extra = []
        if mol.get("molecular_weight") is not None and metric != "molecular_weight":
            extra.append(f"MW={mol['molecular_weight']:.1f}")
        if mol.get("affinity_kcal") is not None and metric != "affinity_kcal":
            extra.append(f"aff={mol['affinity_kcal']:.1f}")
        if mol.get("total_score") is not None and metric != "total_score":
            extra.append(f"score={mol['total_score']:.0f}")
        suffix = f" ({', '.join(extra)})" if extra else ""
        lines.append(f"  {i}. {mol['name']}: {val_str}{unit}{suffix}")

    return "\n".join(lines)


async def query_history(
    target: str = "",
    sort_by: str = "total_score",
    order: str = "desc",
    min_score: str = "",
    max_score: str = "",
    min_affinity: str = "",
    min_mw: str = "",
    max_mw: str = "",
    limit: str = "10",
    user_id: str = "",
) -> str:
    """Consultar el historial persistido de evaluaciones del usuario.

    Fuente: la DB (molecules + evaluation_results). Todas las evaluaciones
    se registran automáticamente (política: sin botón de guardar).

    user_id: la cuenta cuyo historial se consulta. Es obligatorio de hecho:
    sin él la herramienta se abstiene en vez de leer el de otra cuenta (D-05).
    `/ai/chat` exige sesión desde MOLCHAT-BE-002, así que siempre lo hay.

    Filtros combinables:
      target      — receptor (ej. 5HT1A, 7E2Y, CDK2)
      sort_by     — total_score | affinity_kcal | molecular_weight | log_p |
                    tpsa | qed | adme_score | druglikeness_score | created_at
      order       — desc | asc
      min/max_score    — rango de total_score (0-100)
      min_affinity     — afinidad mínima (kcal/mol, más negativo = mejor)
      min/max_mw       — rango de peso molecular (Da)
    """
    try:
        import uuid as _uuid
        from core.database import get_db_session
        from db.repository import Repository
    except ImportError as e:
        return f"Error: historial no disponible ({e})"

    # D-05: sin identidad no se lee el historial de nadie. Antes caía al usuario
    # de prueba y devolvía sus moléculas como si fueran las de quien preguntaba.
    if not user_id:
        return (
            "No puedo consultar el historial: esta petición no trae identidad "
            "de cuenta, y no voy a leer el de otra."
        )

    try:
        async with get_db_session() as db:
            repo = Repository(db)
            uid = _uuid.UUID(user_id)
            mols = await repo.list_user_molecules(uid, limit=500)
    except Exception as e:
        return f"Error consultando historial: {str(e)[:150]}"

    if not mols:
        return (
            "No hay evaluaciones en el historial todavía. Evaluá una molécula "
            "contra un receptor para que se registre automáticamente."
        )

    def _f(v) -> float | None:
        if v is None:
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    # Construir registros con todos los campos indexables
    records = []
    for mol in mols:
        ev = mol.evaluation_result
        target_pdb = mol.target.pdb_id if mol.target else "unknown"
        rec = {
            "name": mol.name or mol.smiles[:25],
            "smiles": mol.smiles,
            "target": target_pdb,
            "status": mol.status.value if hasattr(mol.status, "value") else str(mol.status),
            "total_score": _f(ev.total_score if ev else None),
            "affinity_kcal": _f(ev.affinity_kcal if ev else None),
            "affinity_score": _f(ev.affinity_score if ev else None),
            "molecular_weight": _f(ev.molecular_weight if ev else None),
            "log_p": _f(ev.log_p if ev else None),
            "tpsa": _f(ev.tpsa if ev else None),
            "qed": _f(ev.qed if ev else None),
            "adme_score": _f(ev.adme_score if ev else None),
            "druglikeness_score": _f(ev.druglikeness_score if ev else None),
            "gnn_score": _f(ev.gnn_score if ev else None),
            "lipinski_pass": bool(ev.lipinski_pass) if ev and ev.lipinski_pass is not None else None,
        }
        records.append(rec)

    # ── Filtros ──
    if target:
        t = target.strip().lower()
        records = [r for r in records if t in r["target"].lower()]

    if min_score:
        v = _f(min_score)
        if v is not None:
            records = [r for r in records if r["total_score"] is not None and r["total_score"] >= v]
    if max_score:
        v = _f(max_score)
        if v is not None:
            records = [r for r in records if r["total_score"] is not None and r["total_score"] <= v]
    if min_affinity:
        v = _f(min_affinity)
        if v is not None:
            records = [r for r in records if r["affinity_kcal"] is not None and r["affinity_kcal"] <= v]
    if min_mw:
        v = _f(min_mw)
        if v is not None:
            records = [r for r in records if r["molecular_weight"] is not None and r["molecular_weight"] >= v]
    if max_mw:
        v = _f(max_mw)
        if v is not None:
            records = [r for r in records if r["molecular_weight"] is not None and r["molecular_weight"] <= v]

    if not records:
        return "No hay evaluaciones que coincidan con los filtros indicados."

    # ── Orden ──
    valid_sort = {
        "total_score", "affinity_kcal", "affinity_score", "molecular_weight",
        "log_p", "tpsa", "qed", "adme_score", "druglikeness_score",
        "gnn_score", "created_at",
    }
    if sort_by not in valid_sort:
        sort_by = "total_score"

    def _sort_key(r):
        v = r.get(sort_by)
        return v if v is not None else -999999 if order.lower() == "asc" else 999999

    records.sort(key=_sort_key, reverse=(order.lower() != "asc"))

    try:
        lim = max(1, min(int(limit), 25))
    except (TypeError, ValueError):
        lim = 10
    records = records[:lim]

    lines = [f"[Historial - {len(records)} evaluaciones ordenadas por {sort_by} ({order})]"]
    for i, r in enumerate(records, 1):
        parts = [r["name"]]
        if r["target"] != "unknown":
            parts.append(r["target"])
        if r["total_score"] is not None:
            parts.append(f"score={r['total_score']:.1f}")
        if r["affinity_kcal"] is not None:
            parts.append(f"aff={r['affinity_kcal']:.1f}")
        if r["molecular_weight"] is not None:
            parts.append(f"MW={r['molecular_weight']:.1f}")
        if r["log_p"] is not None:
            parts.append(f"LogP={r['log_p']:.2f}")
        if r["lipinski_pass"] is not None:
            parts.append("Lipinski=OK" if r["lipinski_pass"] else "Lipinski=FAIL")
        lines.append(f"  {i}. {' | '.join(parts)}")

    return "\n".join(lines)


def register_session_tools():
    registry = get_tool_registry()
    registry.register(ToolDef(
        name="rank_session_molecules",
        clase="dato_persistido",
        procedencia="moléculas de la sesión en curso, con sus valores ya calculados",
        description=(
            "Rankea las moléculas ya calculadas en ESTA conversación por una "
            "métrica: molecular_weight, log_p, tpsa, hbd, hba, affinity_kcal, "
            "total_score. Devuelve una tabla ordenada. Usala para responder "
            "'cuál tiene menor/mayor peso molecular', 'cuál es la más lipofílica', "
            "etc. entre las moléculas que ya vimos en el chat."
        ),
        parameters={
            "metric": {"type": "string", "required": False},
            "order": {"type": "string", "required": False},
            "limit": {"type": "string", "required": False},
        },
        offline=True,
        category="general",
        fn=rank_session_molecules,
    ))
    registry.register(ToolDef(
        name="query_history",
        clase="dato_persistido",
        procedencia="historial de evaluaciones de esta cuenta",
        description=(
            "Consulta el historial PERSISTIDO de evaluaciones del usuario. "
            "Todas las evaluaciones se guardan automáticamente. Filtros: "
            "target (receptor ej. 5HT1A), sort_by (total_score, affinity_kcal, "
            "molecular_weight, log_p, tpsa, qed), min/max_score, min_affinity, "
            "min/max_mw. Usala para 'qué evalué contra X', 'mejores scores', "
            "'qué moleculas pasan Lipinski'."
        ),
        parameters={
            "target": {"type": "string", "required": False},
            "sort_by": {"type": "string", "required": False},
            "order": {"type": "string", "required": False},
            "min_score": {"type": "string", "required": False},
            "max_score": {"type": "string", "required": False},
            "min_affinity": {"type": "string", "required": False},
            "min_mw": {"type": "string", "required": False},
            "max_mw": {"type": "string", "required": False},
            "limit": {"type": "string", "required": False},
        },
        offline=True,
        category="general",
        fn=query_history,
    ))
