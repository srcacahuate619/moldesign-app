"""
services/ai/tools/evaluation_tools.py

MolChat tools para consultar evaluaciones REALES persistidas (F10).

Problema resuelto
-----------------
El usuario pregunta "desglosa el Score ADME de la última evaluación",
"listame las poses de docking con RMSD", "qué comando Vina se usó" — y el
LLM responde "no tengo la capacidad" porque NINGUNA tool consulta la DB de
evaluaciones. Pero `evaluation_results` tiene TODO eso (adme_score,
docking_poses con rmsd, vina_version, vina_random_seed, hotspots_hit,
evaluated_at, ...).

Esta tool da al chat acceso a los datos reales de la última evaluación del
usuario (o de una molécula concreta), con el MISMO principio del resto del
sistema: el código decide lo factual, el modelo explica lo conceptual.
"""

from __future__ import annotations

import json
import uuid

from services.ai.tool_registry import ToolDef, get_tool_registry


class SinIdentidad(Exception):
    """La herramienta se llamó sin saber de quién es el historial."""


def _resolve_user_id(user_id: str) -> uuid.UUID:
    """Resolver el user_id de la cuenta que pregunta.

    D-05: antes, sin `user_id`, esto caía a la cuenta de prueba del repositorio.
    La herramienta contestaba igual, pero el historial que leía era el de una
    cuenta sintética compartida, no el de quien preguntaba. Devolver datos de
    otra cuenta como si fueran tuyos es peor que no contestar.

    Desde MOLCHAT-BE-002 el chat siempre tiene sesión, así que este camino no
    debería alcanzarse; si se alcanza es un error de programación y se declara
    como tal en vez de resolverse a un usuario cualquiera.
    """
    if not user_id:
        raise SinIdentidad("la herramienta se llamó sin identidad de cuenta")
    try:
        return uuid.UUID(user_id)
    except (ValueError, TypeError) as exc:
        raise SinIdentidad(f"identidad de cuenta ilegible: {user_id!r}") from exc


async def query_evaluation_details(
    user_id: str = "",
    which: str = "last",
    target: str = "",
    smiles: str = "",
    limit: str = "1",
) -> str:
    """Consultar los datos REALES de una evaluación persistida.

    which:
      - "last"   → la evaluación más reciente del usuario (default)
      - "first"  → la más antigua
      - "target" → la más reciente contra un target concreto
      - "smiles" → la evaluación de una molécula concreta (SMILES o nombre)
    limit: cuántas evaluaciones devolver (default 1).

    Devuelve los campos clave del evaluation_result: score total, afinidad,
    ADME score, subcomponentes sanguíneos, poses de docking (rank/afinidad/
    RMSD), versión y semilla de Vina, hotspots, timestamp. Los datos vienen
    de la DB real — NO del modelo.
    """
    try:
        uid = _resolve_user_id(user_id)
    except SinIdentidad:
        return (
            "No puedo consultar el historial: esta petición no trae identidad "
            "de cuenta, y no voy a leer el de otra."
        )

    try:
        from core.database import get_db_session
        from db.repository import Repository
        from services.ai.known_molecules import get_smiles_by_name
    except Exception as e:
        return f"Error: no se pudo consultar el historial ({str(e)[:100]})"

    # Resolver SMILES por nombre si hace falta (para filtro smiles)
    resolved_smiles = ""
    if smiles:
        resolved_smiles = smiles
        try:
            named = get_smiles_by_name(smiles)
            if named:
                resolved_smiles = named
        except Exception:
            pass

    try:
        async with get_db_session() as db:
            repo = Repository(db)
            mols = await repo.list_user_molecules(uid, limit=500)
    except Exception as e:
        return f"Error consultando evaluaciones: {str(e)[:150]}"

    if not mols:
        return (
            "No hay evaluaciones en el historial todavía. Evaluá una molécula "
            "contra un receptor para que se registre automáticamente."
        )

    # ── Filtrar ──
    if target:
        t = target.strip().lower()
        mols = [
            m for m in mols
            if m.target and t in m.target.pdb_id.lower()
        ]
    if resolved_smiles:
        mols = [m for m in mols if m.smiles == resolved_smiles]

    # Solo las que tienen evaluación
    mols = [m for m in mols if m.evaluation_result]
    if not mols:
        return "No encontré evaluaciones que coincidan con los filtros."

    # ── Seleccionar ──
    # list_user_molecules ya ordena por created_at desc → [0] es la última.
    if which == "first":
        mols = [mols[-1]]
    elif which in ("target", "smiles"):
        mols = [mols[0]]
    else:  # last
        mols = [mols[0]]

    try:
        lim = max(1, min(int(limit), 5))
    except (TypeError, ValueError):
        lim = 1
    mols = mols[:lim]

    lines: list[str] = []
    for mol in mols:
        ev = mol.evaluation_result
        target_name = mol.target.name if mol.target else "?"
        target_pdb = mol.target.pdb_id if mol.target else "?"
        name = mol.name or mol.smiles[:25]

        header = f"[Evaluación de {name} contra {target_name} ({target_pdb})]"
        lines.append(header)

        # Score compuesto
        parts = []
        if ev.total_score is not None:
            parts.append(f"score_total={ev.total_score:.1f}/100")
        if ev.affinity_kcal is not None:
            parts.append(f"afinidad={ev.affinity_kcal:.2f} kcal/mol")
        if ev.affinity_score is not None:
            parts.append(f"score_afinidad={ev.affinity_score:.1f}")
        lines.append("  " + " | ".join(parts))

        # ADME + subcomponentes
        adme_parts = []
        if ev.adme_score is not None:
            adme_parts.append(f"ADME_score={ev.adme_score:.1f}")
        if ev.druglikeness_score is not None:
            adme_parts.append(f"druglikeness={ev.druglikeness_score:.1f}")
        if ev.blood_solubility_logs is not None:
            adme_parts.append(f"LogS={ev.blood_solubility_logs:.2f}")
        if ev.blood_ppb_category:
            adme_parts.append(f"PPB={ev.blood_ppb_category}")
        if ev.blood_bbb_permeable is not None:
            adme_parts.append(f"BBB={'sí' if ev.blood_bbb_permeable else 'no'}")
        if ev.blood_hia_permeable is not None:
            adme_parts.append(f"HIA={'sí' if ev.blood_hia_permeable else 'no'}")
        if ev.lipinski_pass is not None:
            adme_parts.append(f"Lipinski={'OK' if ev.lipinski_pass else 'FAIL'}")
        if ev.qed is not None:
            adme_parts.append(f"QED={ev.qed:.3f}")
        if ev.sa_score is not None:
            adme_parts.append(f"SA={ev.sa_score:.2f}")
        if adme_parts:
            lines.append("  ADME: " + " | ".join(adme_parts))

        # Poses de docking
        poses = []
        try:
            raw_poses = ev.docking_poses
            if isinstance(raw_poses, str):
                raw_poses = json.loads(raw_poses)
            if raw_poses:
                poses = raw_poses
        except (json.JSONDecodeError, TypeError):
            poses = []
        if poses:
            pose_lines = []
            for p in poses[:5]:
                rank = p.get("rank", "?")
                aff = p.get("affinity", p.get("affinity_kcal", "?"))
                rmsd_lb = p.get("rmsd_lb", "?")
                rmsd_ub = p.get("rmsd_ub", "?")
                pose_lines.append(
                    f"pose {rank}: aff={aff}, RMSD_lb={rmsd_lb}, RMSD_ub={rmsd_ub}"
                )
            lines.append("  Poses: " + "; ".join(pose_lines))

        # Metadatos de reproducibilidad (Vina)
        meta = []
        if ev.vina_version:
            meta.append(f"Vina {ev.vina_version}")
        if ev.vina_random_seed is not None:
            meta.append(f"seed={ev.vina_random_seed}")
        if ev.parsing_source:
            meta.append(f"source={ev.parsing_source}")
        if meta:
            lines.append("  Repro: " + " | ".join(meta))

        # Hotspots / residuos
        if ev.hotspots_hit:
            try:
                hs = ev.hotspots_hit
                if isinstance(hs, str):
                    hs = json.loads(hs)
                lines.append("  Hotspots: " + ", ".join(str(h) for h in hs[:10]))
            except (json.JSONDecodeError, TypeError):
                lines.append(f"  Hotspots: {str(ev.hotspots_hit)[:80]}")

        if ev.evaluated_at:
            lines.append(f"  Evaluada: {ev.evaluated_at}")

        lines.append("")

    return "\n".join(lines).strip()


def register_evaluation_tools():
    registry = get_tool_registry()
    registry.register(ToolDef(
        name="query_evaluation_details",
        clase="dato_persistido",
        procedencia="evaluaciones persistidas de esta cuenta",
        description=(
            "Consulta los datos REALES de una evaluación persistida del usuario: "
            "score total, afinidad, ADME score con subcomponentes (LogS, PPB, "
            "BBB, HIA, Lipinski, QED, SA), poses de docking con RMSD, versión y "
            "semilla de Vina, hotspots y timestamp. Usala para responder preguntas "
            "sobre 'la última evaluación', 'el score ADME', 'las poses', 'qué "
            "comando Vina se usó'. which='last' (default) | 'first' | 'target' | "
            "'smiles'; target/smiles para filtrar."
        ),
        parameters={
            "user_id": {"type": "string", "required": False},
            "which": {"type": "string", "required": False},
            "target": {"type": "string", "required": False},
            "smiles": {"type": "string", "required": False},
            "limit": {"type": "string", "required": False},
        },
        offline=True,
        fn=query_evaluation_details,
    ))
