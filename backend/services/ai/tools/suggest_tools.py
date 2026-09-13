"""
services/ai/tools/suggest_tools.py

MolChat tool: suggest_smiles — sugerir moléculas CRUZANDO con MolGraph.

Filosofía (F7)
--------------
Cuando el usuario pide "dame un SMILES interesante", "dame un SMILES para el
receptor X" o "dame una variante de la molécula Y", el sistema NO debe dejar
que el LLM invente un SMILES de memoria (alucina). En su lugar:

  1. MolGraph es la fuente de verdad: miles de moléculas YA evaluadas con
     propiedades reales (score, afinidad, MW, LogP).
  2. La selección es ALEATORIA dentro del subconjunto relevante — de esta
     forma MolChat NUNCA devuelve el mismo SMILES dos veces (ilusión de
     variedad sin hardcodear nada).
  3. "Variante": primero busca en el grafo si ya existe una derivada
     (relation='modified_from' o similar); si existe, la sugiere (con su
     afinidad medida). Si no, genera análogos BRICS y elige uno al azar.

Principio rector: el código decide lo factual, el modelo explica lo conceptual.
"""

from __future__ import annotations

import asyncio
import json
import random

from services.ai.tool_registry import ToolDef, get_tool_registry


async def _run_sync(fn, *args, **kwargs):
    """Ejecutar funcion sincrona en thread pool para no bloquear el event loop."""
    return await asyncio.get_running_loop().run_in_executor(
        None, lambda: fn(*args, **kwargs)
    )


def _format_molecule(name: str, smiles: str, props: dict) -> str:
    """Formatear una molécula del grafo con sus propiedades reales."""
    lines = [f"[MolGraph] {name or smiles[:40]}: {smiles}"]
    if props.get("score") is not None:
        lines.append(f"  score: {props['score']}/100")
    if props.get("affinity_kcal") is not None:
        lines.append(f"  afinidad: {props['affinity_kcal']} kcal/mol")
    if props.get("molecular_weight") is not None:
        lines.append(f"  MW: {props['molecular_weight']} Da")
    if props.get("log_p") is not None:
        lines.append(f"  LogP: {props['log_p']}")
    if props.get("target_name"):
        lines.append(f"  target: {props['target_name']}")
    return "\n".join(lines)


def _load_graph_molecules(user_id: str | None = None,
                          incluir_heredadas: bool = False) -> list[dict]:
    """Cargar moléculas del grafo con score (para selección aleatoria).

    IMPORTANTE (hallazgo de verificación): MolGraph tiene ~8000 NODOS pero
    solo ~2637 SMILES ÚNICOS. Un nodo 'evaluation' se crea por cada
    (molécula × target) — cada evaluación duplica el SMILES con su propio
    score. Para sugerencias, queremos las moléculas QUÍMICAMENTE DISTINTAS
    (DISTINCT smiles) de TODOS los nodos, tomando el mejor score por SMILES.
    Así la selección cubre las ~2637 moléculas reales (moléculas que solo
    existen como evaluación incluidas), no solo las 2633 de type='molecule'.

    Retorna lista de dicts con name, smiles, properties. Vacía si la DB
    no existe o no tiene moléculas.
    """
    # MOLCHAT-BE-009: esto abría `molgraph.db` a mano, saltándose la capa que
    # separa el corpus público del almacén de cada cuenta — y por tanto sugería
    # a un investigador las moléculas que había evaluado otro. Ahora pasa por
    # `_grafo`, que compone corpus + cuenta y no deja escribir.
    from services.ai.molgraph import _grafo

    try:
        with _grafo(user_id, incluir_heredadas) as conn:
            # SMILES únicos de TODOS los nodos con propiedades de score.
            # Por cada SMILES, tomamos la fila con el score más alto (el
            # mejor resultado de actividad conocido para esa molécula).
            rows = conn.execute(
                "SELECT name, smiles, properties_json FROM mol_nodes "
                "WHERE smiles IS NOT NULL AND smiles != '' "
                "AND properties_json IS NOT NULL AND properties_json != '{}' "
                "AND properties_json LIKE '%score%' "
                "ORDER BY "
                "  CAST(json_extract(properties_json, '$.score') AS REAL) DESC"
            ).fetchall()

        results = []
        seen: set[str] = set()
        for name, smiles, props_json in rows:
            if smiles in seen:
                continue  # ya tomamos el mejor score de este SMILES
            seen.add(smiles)
            try:
                props = json.loads(props_json)
            except Exception:
                props = {}
            if props.get("score") is None:
                continue  # solo moléculas evaluadas
            results.append({
                "name": name,
                "smiles": smiles,
                "properties": props,
            })
        return results
    except Exception:
        return []


def _random_interesting(limit: int = 1, user_id: str | None = None) -> str:
    """Modo 1: SMILES aleatorio entre las evaluadas del grafo.

    Aleatoriedad intencional: el usuario pidió "interesante" — devolvemos una
    molécula REAL del grafo al azar con sus propiedades, nunca hardcodeada.
    """
    mols = _load_graph_molecules(user_id=user_id)
    if not mols:
        return "[MolGraph] No hay moléculas evaluadas aún — evalúa una primero."
    sample = random.sample(mols, k=min(limit, len(mols)))
    return "\n\n".join(
        _format_molecule(m["name"], m["smiles"], m["properties"]) for m in sample
    )


def _random_for_target(target_pdb: str, limit: int = 1,
                       user_id: str | None = None) -> str:
    """Modo 2: SMILES aleatorio entre las evaluadas contra un target."""
    from services.ai.molgraph import query_graph

    results = query_graph(target_pdb=target_pdb, limit=50, user_id=user_id)
    # Filtrar las que tienen score y afinidad real
    scored = [r for r in results if r.get("score") is not None]
    if not scored:
        return f"[MolGraph] No hay moléculas evaluadas contra '{target_pdb}' aún."
    sample = random.sample(scored, k=min(limit, len(scored)))
    lines = []
    for r in sample:
        mw = r.get("mw")
        logp = r.get("logp")
        mw_str = f"{mw} Da" if isinstance(mw, (int, float)) else "N/D"
        logp_str = f"{logp}" if isinstance(logp, (int, float)) else "N/D"
        lines.append(
            f"[MolGraph - {target_pdb}] {r['smiles']}: score={r['score']}/100, "
            f"afinidad={r['affinity']} kcal/mol, MW={mw_str}, LogP={logp_str}"
        )
    return "\n".join(lines)


def _find_existing_variant(smiles: str, user_id: str | None = None) -> dict | None:
    """Buscar en el grafo si ya existe una variante de esta molécula.

    Prioriza derivadas directas (modified_from) y luego similares EVALUADAS
    (con score/afinidad medidos). Devuelve la primera variante existente con
    evidencia, o None. Una "similar" sin score no cuenta: mejor generar una
    nueva que sugerir algo sin datos de actividad.
    """
    from services.ai.molgraph import query_neighbors, query_molgraph_similar

    # 1. Vecinos con relación modified_from (derivadas directas)
    try:
        neighbors = query_neighbors(smiles, limit=20, user_id=user_id)
        for nb in neighbors:
            if nb.get("relation") == "modified_from":
                return {
                    "name": nb.get("name"),
                    "smiles": nb.get("smiles"),
                    "properties": {
                        "score": nb.get("score"),
                        "affinity_kcal": nb.get("affinity"),
                        "relation": "modified_from",
                    },
                }
    except Exception:
        pass

    # 2. Similares EVALUADAS (con score real medido) — variantes con evidencia
    try:
        sims = query_molgraph_similar(smiles, threshold=0.5, limit=20, user_id=user_id)
        for s in sims:
            score = s.get("score")
            aff = s.get("affinity")
            if score is not None or aff is not None:
                return {
                    "name": s.get("name"),
                    "smiles": s.get("smiles"),
                    "properties": {
                        "score": score,
                        "affinity_kcal": aff,
                        "similarity": s.get("similarity"),
                        "relation": "similar",
                    },
                }
    except Exception:
        pass

    return None


def _generate_random_variant(smiles: str) -> str:
    """Modo 3a: generar variante BRICS con aleatoriedad (nunca igual)."""
    # Guard rápido: BRICS necesita una molécula con suficientes átomos pesados.
    # Para moléculas diminutas (etanol, metano) el generador puede colgarse —
    # respondemos honestamente sin ejecutarlo.
    try:
        from rdkit import Chem
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return f"No reconozco {smiles[:30]} como SMILES válido."
        heavy = mol.GetNumHeavyAtoms()
        if heavy < 5:
            return (
                f"La molécula {smiles[:30]} es demasiado pequeña "
                f"({heavy} átomos pesados) para generar variantes BRICS "
                "con sentido. Prueba con una molécula de 5+ átomos."
            )
    except ImportError:
        pass

    strategies = ["all", "scaffold_hop", "substituent_swap", "diversity"]
    strategy = random.choice(strategies)
    try:
        from services.chemistry.analog_generator import AnalogGenerator, AnalogStrategy
        gen = AnalogGenerator()
        # Asegurar biblioteca de fragmentos (reutiliza la lógica de analog_tools)
        from services.ai.tools.analog_tools import _ensure_library_built
        _ensure_library_built(gen)
        candidates = gen.generate(
            smiles, n_analogs=30, strategy=AnalogStrategy(strategy)
        )
        if not candidates:
            return (
                f"No pude generar una variante de {smiles[:30]} con BRICS "
                "(molécula muy pequeña o biblioteca vacía)."
            )
        # Aleatorio entre los candidatos generados — nunca el mismo dos veces
        pick = random.choice(candidates)
        smi = getattr(pick, "smiles", None) or str(pick)
        sim = getattr(pick, "morgan_similarity", None)
        sim_str = f", sim={sim:.2f}" if isinstance(sim, (int, float)) else ""
        return (
            f"[BRICS {strategy}] Variante generada de {smiles[:30]}:\n"
            f"  {smi}\n"
            f"  similitud Morgan={sim_str}, estrategia={strategy}"
        )
    except ImportError:
        return "Generador BRICS no disponible en este modo."
    except Exception as e:
        return f"Error generando variante: {str(e)[:150]}"


async def suggest_smiles(
    mode: str = "interesting",
    target: str = "",
    smiles: str = "",
    limit: str = "1",
    user_id: str | None = None,
) -> str:
    """Sugerir moléculas cruzando con MolGraph (F7).

    mode:
      - interesting  → SMILES aleatorio entre las evaluadas del grafo
                       ("dame un smiles interesante", "alguna molécula buena")
      - for_target   → SMILES aleatorio entre las evaluadas contra un target
                       ("dame un smiles para el receptor de serotonina")
      - variant      → variante de una molécula: primero busca en el grafo
                       (modified_from/similar); si no hay, genera BRICS con
                       aleatoriedad ("dame una variante de la aspirina")
    """
    n = 1
    try:
        n = max(1, min(int(limit), 5))
    except ValueError:
        n = 1

    if mode == "for_target":
        if not target:
            return "Necesito saber contra qué receptor: ej. 'dame un SMILES para el receptor de serotonina'."
        return _random_for_target(target, limit=n, user_id=user_id)

    if mode == "variant":
        if not smiles:
            return "Necesito la molécula base: ej. 'dame una variante de la aspirina'."
        existing = await _run_sync(_find_existing_variant, smiles, user_id)
        if existing:
            # Ya existe una variante en el grafo — sugerirla con evidencia real
            props = existing["properties"]
            rel = props.get("relation", "?")
            score_s = f"score: {props.get('score')}" if props.get("score") is not None else ""
            aff_s = f"afinidad: {props.get('affinity_kcal')} kcal/mol" if props.get("affinity_kcal") is not None else ""
            evidence = ", ".join(s for s in (score_s, aff_s) if s)
            return (
                f"[MolGraph] Ya existe una variante de esta molécula "
                f"(relación '{rel}'):\n"
                f"  {existing['smiles']}\n"
                f"  {evidence if evidence else 'sin métricas registradas'}"
            )
        # No hay variante en el grafo → generar BRICS con límite de tiempo.
        # BRICS en moléculas muy pequeñas (etanol, metano) puede tardar o
        # colgarse construyendo la biblioteca — no bloqueamos el chat.
        try:
            return await asyncio.wait_for(
                _run_sync(_generate_random_variant, smiles),
                timeout=15.0,
            )
        except asyncio.TimeoutError:
            return (
                f"No encontré una variante de {smiles[:30]} en el grafo y el "
                "generador BRICS tardó demasiado para esta molécula. "
                "Prueba con una molécula más grande."
            )

    # default: interesting
    return _random_interesting(limit=n, user_id=user_id)


def register_suggest_tools():
    registry = get_tool_registry()
    registry.register(ToolDef(
        name="suggest_smiles",
        clase="dato_persistido",
        procedencia="moléculas ya evaluadas del grafo local; nunca un SMILES inventado",
        description=(
            "Sugiere moléculas CRUZANDO con MolGraph (knowledge graph químico). "
            "mode='interesting' → SMILES aleatorio entre las evaluadas del grafo "
            "('dame un smiles interesante'). mode='for_target' → SMILES aleatorio "
            "contra un receptor ('dame un smiles para el receptor de serotonina'; "
            "target puede ser nombre común o PDB ID). mode='variant' → variante de "
            "una molécula ('dame una variante de la aspirina'; busca primero en el "
            "grafo, si no hay genera con BRICS). Las selecciones son ALEATORIAS "
            "para nunca repetir el mismo SMILES."
        ),
        parameters={
            "mode": {
                "type": "string", "required": False,
                "description": "interesting | for_target | variant",
            },
            "target": {
                "type": "string", "required": False,
                "description": "Receptor (nombre común o PDB ID) para mode='for_target'",
            },
            "smiles": {
                "type": "string", "required": False,
                "description": "Molécula base para mode='variant'",
            },
            "limit": {"type": "string", "required": False},
        },
        offline=True,
        fn=suggest_smiles,
    ))
