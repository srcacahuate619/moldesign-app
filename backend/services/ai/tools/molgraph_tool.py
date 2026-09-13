"""
services/ai/tools/molgraph_tool.py

Herramienta MolGraph para MolChat: knowledge graph quimico en SQLite.
Reemplaza el DENSE format (2000 tokens) por queries de ~60 tokens.
Tecnologia propia de MolDesign.
"""

from __future__ import annotations

import asyncio

from services.ai.tool_registry import ToolDef, get_tool_registry


async def _run_sync(fn, *args, **kwargs):
    """Ejecutar funcion sincrona en thread pool para no bloquear el event loop."""
    return await asyncio.get_running_loop().run_in_executor(
        None, lambda: fn(*args, **kwargs)
    )


async def query_molgraph(query: str = "", target: str = "", min_score: str = "",
                          min_affinity: str = "", limit: str = "8",
                          randomize: str = "false",
                          user_id: str | None = None) -> str:
    """
    Consultar el knowledge graph quimico de MolDesign.
    Encuentra moleculas evaluadas, por target, score o afinidad.

    randomize=true → factor X SOLO cuando el usuario pidió exploración sin
    orden explícito (ej. "dame moléculas contra 5-HT1A"). Cuando el usuario
    pide "top/mejores" el chat_service pasa randomize=false (ranking real).
    """
    import random as _random
    from services.ai.molgraph import query_graph, query_fts

    # Detectar si es busqueda FTS5
    if query and not target and not min_score:
        results = query_fts(query, limit=int(limit), user_id=user_id)
        if results:
            if randomize.lower() in ("1", "true", "yes", "si") and len(results) > 1:
                _random.shuffle(results)
                results = results[: int(limit)]
            lines = ["[MolGraph FTS5]"]
            for r in results:
                lines.append(f"  {r['type']}: {r['name']}")
            return "\n".join(lines)
        return "[MolGraph] No se encontraron resultados."

    if target and "smiles" not in target.lower():
        # Buscar moleculas contra un target
        # Pool amplio para poder elegir subset aleatorio si hace falta.
        pool_limit = max(int(limit) * 5, 40)
        results = query_graph(
            target_pdb=target,
            min_score=float(min_score) if min_score else 0,
            min_affinity=float(min_affinity) if min_affinity else -999,
            limit=pool_limit,
        )
        if randomize.lower() in ("1", "true", "yes", "si") and len(results) > int(limit):
            results = _random.sample(results, k=int(limit))
        elif len(results) > int(limit):
            results = results[: int(limit)]
        if results:
            lines = [f"[MolGraph - Evaluaciones contra {target}]"]
            for r in results:
                lines.append(
                    f"  {r['name']}: score={r['score']}/100, "
                    f"afinidad={r['affinity']} kcal/mol, "
                    f"MW={r['mw']}"
                )
            return "\n".join(lines)
        return f"[MolGraph] No hay evaluaciones contra '{target}'."

    # Top global
    from services.ai.molgraph import get_top_molecules
    results = get_top_molecules(by="score", limit=int(limit), user_id=user_id)
    if results:
        if randomize.lower() in ("1", "true", "yes", "si") and len(results) > 1:
            _random.shuffle(results)
        lines = ["[MolGraph - Top scores]"]
        for r in results:
            lines.append(
                f"  {r['smiles'][:30]}: score={r['score']}/100, "
                f"afinidad={r['affinity']} kcal/mol"
            )
        return "\n".join(lines)
    return "[MolGraph] No hay evaluaciones registradas aun."


async def molgraph_neighbors(smiles: str, limit: str = "5",
                             randomize: str = "false",
                             user_id: str | None = None) -> str:
    """Encontrar moleculas relacionadas (mismo target, similares).

    randomize=true → varía el ORDEN de presentación (factor X): cuando hay
    más vecinos que `limit`, los resultados se muestran en orden aleatorio
    para que MolChat nunca repita la misma lista. Los datos son reales.
    """
    import random as _random
    from services.ai.molgraph import query_neighbors
    results = query_neighbors(smiles, limit=max(int(limit) * 4, 20), user_id=user_id)
    if results:
        if randomize.lower() in ("1", "true", "yes", "si"):
            _random.shuffle(results)
            results = results[: int(limit)]
        lines = [f"[MolGraph - Relacionadas con {smiles[:30]}]"]
        for r in results:
            lines.append(
                f"  {r['smiles'][:30]}: {r.get('relation','?')} "
                f"(score={r.get('score','?')}, aff={r.get('affinity','?')})"
            )
        return "\n".join(lines)
    return "[MolGraph] No hay moleculas relacionadas."


async def molgraph_similar(smiles: str, threshold: str = "0.6", limit: str = "5",
                           randomize: str = "false",
                           user_id: str | None = None) -> str:
    """Encuentra moleculas quimicamente similares via fingerprints (Tanimoto).

    randomize=true → factor X: si hay MÁS similares que `limit`, se elige el
    subset al azar entre los que pasan el umbral (todos reales, misma
    calidad química). MolChat nunca repite la misma lista.
    """
    import random as _random
    from services.ai.molgraph import query_molgraph_similar
    # Pedir un pool amplio; si randomize, elegir subset aleatorio.
    pool = await _run_sync(
        query_molgraph_similar, smiles, float(threshold),
        max(int(limit) * 5, 25), user_id,
    )
    results = pool
    if pool and randomize.lower() in ("1", "true", "yes", "si"):
        results = _random.sample(pool, k=min(int(limit), len(pool)))
    if results:
        lines = [f"[MolGraph - Similares a {smiles[:30]} (Tanimoto >= {threshold})]"]
        for r in results:
            lines.append(
                f"  {r['smiles'][:30]}: sim={r['similarity']}, "
                f"score={r.get('score','?')}, aff={r.get('affinity','?')}"
            )
        return "\n".join(lines)
    return "[MolGraph] No se encontraron moleculas quimicamente similares."


async def molgraph_impact(substructure: str = "", min_delta: str = "-99.0",
                          user_id: str | None = None) -> str:
    """Analizar que modificaciones quimicas mejoraron la afinidad."""
    from services.ai.molgraph import query_modification_impact
    results = query_modification_impact(substructure, float(min_delta), user_id=user_id)
    if results:
        lines = [f"[MolGraph - Impacto de modificaciones: {substructure or 'todas'}]"]
        improvements = [r for r in results if r["delta_affinity"] < 0]
        lines.append(f"  Mejoras: {len(improvements)}/{len(results)} casos")
        for r in results[:6]:
            icon = "+" if r["delta_affinity"] < 0 else "-" if r["delta_affinity"] > 0 else "="
            lines.append(
                f"  {icon} {r['modification']}: delta_aff={r['delta_affinity']:.1f}, "
                f"score: {r['parent_score']}→{r['child_score']}"
            )
        return "\n".join(lines)
    return "[MolGraph] No hay modificaciones registradas aun."


async def molgraph_scaffolds(threshold: str = "0.5", user_id: str | None = None,
                             randomize: str = "false") -> str:
    """Agrupar moleculas en series quimicas (scaffolds).

    randomize=true → factor X: varía el orden de presentación de las series
    (los datos son reales, solo cambia qué serie se muestra primero).
    """
    import random as _random
    from services.ai.molgraph import query_scaffold_groups
    groups = await _run_sync(query_scaffold_groups, float(threshold), user_id)
    if groups:
        if randomize.lower() in ("1", "true", "yes", "si") and len(groups) > 1:
            _random.shuffle(groups)
        lines = [f"[MolGraph - Series quimicas (Tanimoto >= {threshold})]"]
        for g in groups[:5]:
            lines.append(
                f"  Serie {g['series_leader']}: {g['members']} miembros, "
                f"mejor score={g['best_score']}, aff={g['best_affinity']}"
            )
        return "\n".join(lines)
    return "[MolGraph] No se detectaron series quimicas."


async def molgraph_druglikeness(user_id: str | None = None) -> str:
    """Estadisticas de drug-likeness sobre todas las evaluaciones."""
    from services.ai.molgraph import query_druglikeness_stats
    s = query_druglikeness_stats(user_id=user_id)
    if s["total"] == 0:
        return "[MolGraph] Sin evaluaciones."
    t = s["total"]
    return (
        f"[MolGraph - Drug-Likeness ({t} moleculas)]\n"
        f"  MW>500: {s['mw_gt_500']}/{t} ({round(s['mw_gt_500']/t*100)}%)\n"
        f"  LogP>5: {s['logp_gt_5']}/{t} ({round(s['logp_gt_5']/t*100)}%)\n"
        f"  HBD>5: {s['hbd_gt_5']}/{t} ({round(s['hbd_gt_5']/t*100)}%)\n"
        f"  HBA>10: {s['hba_gt_10']}/{t} ({round(s['hba_gt_10']/t*100)}%)\n"
        f"  TPSA>140: {s['tpsa_gt_140']}/{t} ({round(s['tpsa_gt_140']/t*100)}%)\n"
        f"  Rot>10: {s['rot_gt_10']}/{t} ({round(s['rot_gt_10']/t*100)}%)"
    )


async def molgraph_admet(user_id: str | None = None) -> str:
    """Correlacion entre LogP y predicciones ADMET."""
    from services.ai.molgraph import query_admet_correlation
    r = query_admet_correlation(user_id=user_id)
    if not r:
        return "[MolGraph] Sin datos ADMET."
    lines = ["[MolGraph - Correlacion LogP vs ADMET]"]
    for group in ["low_logp", "mid_logp", "high_logp"]:
        if group in r:
            d = r[group]
            label = f"  LogP {'<1.5' if group=='low_logp' else '1.5-3.5' if group=='mid_logp' else '>3.5'}: "
            label += f"{d['count']} mols, BBB+={d['bbb_permeable_pct']}%, "
            label += f"HIA+={d['hia_permeable_pct']}%, avgMW={d['avg_mw']}"
            lines.append(label)
    return "\n".join(lines)


def register_molgraph_tools():
    registry = get_tool_registry()
    registry.register(ToolDef(
        name="query_molgraph",
        clase="dato_persistido",
        procedencia="knowledge graph local de MolDesign",
        description=(
            "Consulta el knowledge graph quimico de MolDesign. "
            "Usa query para busqueda por texto, target para buscar por "
            "target PDB, min_score/min_affinity para filtrar. "
            "Ej: 'moleculas contra 5-HT1A con score > 50'."
        ),
        parameters={
            "query": {"type": "string", "required": False},
            "target": {"type": "string", "required": False},
            "min_score": {"type": "string", "required": False},
            "min_affinity": {"type": "string", "required": False},
            "limit": {"type": "string", "required": False},
            "randomize": {"type": "string", "required": False},
        },
        offline=True,
        fn=query_molgraph,
    ))
    registry.register(ToolDef(
        name="molgraph_neighbors",
        clase="dato_persistido",
        procedencia="knowledge graph local de MolDesign",
        description="Encuentra moleculas relacionadas (mismo target, similares).",
        parameters={
            "smiles": {"type": "string", "required": True},
            "limit": {"type": "string", "required": False},
            "randomize": {"type": "string", "required": False},
        },
        offline=True,
        fn=molgraph_neighbors,
    ))
    registry.register(ToolDef(
        name="molgraph_similar",
        clase="calculo",
        procedencia="similitud Tanimoto sobre fingerprints RDKit del grafo local",
        description="Encuentra moleculas quimicamente similares via fingerprints RDKit (Tanimoto).",
        parameters={
            "smiles": {"type": "string", "required": True},
            "threshold": {"type": "string", "required": False},
            "limit": {"type": "string", "required": False},
            "randomize": {"type": "string", "required": False},
        },
        offline=True,
        fn=molgraph_similar,
    ))
    registry.register(ToolDef(
        name="molgraph_impact",
        clase="dato_persistido",
        procedencia="knowledge graph local de MolDesign",
        description="Analiza que modificaciones quimicas mejoraron/empeoraron la afinidad en evaluaciones pasadas.",
        parameters={"substructure": {"type": "string", "required": False}},
        offline=True,
        fn=molgraph_impact,
    ))
    registry.register(ToolDef(
        name="molgraph_scaffolds",
        clase="calculo",
        procedencia="agrupamiento por fingerprints RDKit del grafo local",
        description="Agrupa moleculas en series quimicas por similitud (fingerprints).",
        parameters={"threshold": {"type": "string", "required": False}},
        offline=True,
        fn=molgraph_scaffolds,
    ))
    registry.register(ToolDef(
        name="molgraph_druglikeness",
        clase="dato_persistido",
        procedencia="estadística sobre las evaluaciones del grafo local",
        description="Estadisticas de drug-likeness (Lipinski, Veber) sobre todas las evaluaciones.",
        offline=True,
        fn=molgraph_druglikeness,
    ))
    registry.register(ToolDef(
        name="molgraph_admet",
        clase="dato_persistido",
        procedencia="estadística sobre las evaluaciones del grafo local",
        description="Correlacion entre LogP y predicciones ADMET (BBB, HIA) en todas las evaluaciones.",
        offline=True,
        fn=molgraph_admet,
    ))
