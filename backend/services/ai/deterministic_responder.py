"""
services/ai/deterministic_responder.py

RESPUESTAS DETERMINISTAS (Opción A): el código construye la respuesta final
para consultas factuales/comparativas — el modelo NO redacta, así no hay nada
que pueda alucinar ni invertir.

Filosofía: "the model proposes, the system disposes". Para queries de ranking,
comparación e historial, los datos vienen de las tools (verificados); el código
Python decide la relación (mayor/menor) con un `if` — que nunca se equivoca.

Detecta SINÓNIMOS y FORMAS INVERTIDAS de forma semántica:
  - "cuál es mayor?" / "cuál es menor?" / "más pesada" / "más liviana"
  - "más lipofílica" / "menos lipofílica" / "mayor logP" / "menor logP"
  - "mejor afinidad" / "peor afinidad" (afinidad: más negativo = mejor)
  - "más grande" / "más chica" / "top N" / "ranking" / "ordenar"
"""

from __future__ import annotations

import re
from typing import Optional

# ── Semántica de métricas ────────────────────────────────────────────
# Cada métrica sabe:
#   - sus palabras clave (sinónimos de la pregunta del usuario)
#   - la dirección NATURAL para mostrar el ranking (lo "mejor" primero)
#   - la unidad
#   - si "mejor" significa mayor o menor valor
_METRICS: dict[str, dict] = {
    "molecular_weight": {
        "keywords": ["peso molecular", "masa molecular", "pesada", "liviana",
                     "grande", "chica", "peso", "mw", "masa", "pesado"],
        "unit": " Da",
        "precision": 1,
        "natural_order": "asc",   # se muestra de menor a mayor
        "better_is": "lower",     # el menor peso suele ser "mejor" para fármacos
    },
    "log_p": {
        "keywords": ["lipofil", "logp", "log p", "hidrofil"],
        "unit": "",
        "precision": 2,
        "natural_order": "desc",  # más lipofílica primero
        "better_is": "higher",    # más lipofílica
    },
    "tpsa": {
        "keywords": ["tpsa", "superficie polar", "polar surface"],
        "unit": " A²",
        "precision": 1,
        "natural_order": "desc",
        "better_is": "lower",
    },
    "affinity_kcal": {
        "keywords": ["afinidad", "affinity", "binding", "union", "kcal"],
        "unit": " kcal/mol",
        "precision": 2,
        "natural_order": "asc",   # más negativo = mejor → primero
        "better_is": "lower",     # más negativo es mejor
    },
    "total_score": {
        "keywords": ["score", "puntaje", "puntuacion", "mejor evaluad"],
        "unit": "/100",
        "precision": 1,
        "natural_order": "desc",
        "better_is": "higher",
    },
    "hbd": {
        "keywords": ["h-bon donor", "h-bond donor", "donadores", "donors", "hbd"],
        "unit": "",
        "precision": 0,
        "natural_order": "desc",
        "better_is": "lower",
    },
    "hba": {
        "keywords": ["h-bon acceptor", "h-bond acceptor", "aceptores", "acceptors", "hba"],
        "unit": "",
        "precision": 0,
        "natural_order": "desc",
        "better_is": "lower",
    },
    "rotatable_bonds": {
        "keywords": ["rotatable", "enlaces rot", "rot bonds"],
        "unit": "",
        "precision": 0,
        "natural_order": "desc",
        "better_is": "lower",
    },
    "heavy_atoms": {
        "keywords": ["atomos pesados", "heavy atom", "atomos"],
        "unit": "",
        "precision": 0,
        "natural_order": "desc",
        "better_is": "lower",
    },
    "rings": {
        "keywords": ["anillos", "rings", "anillo"],
        "unit": "",
        "precision": 0,
        "natural_order": "desc",
        "better_is": "lower",
    },
}

# Palabras que indican "extremo mayor" (max) en la pregunta
_WORDS_MAX = {
    "mayor", "mas grande", "mas pesada", "mas lipofilica", "mas alta",
    "mas", "mayor valor", "mejor", "mas lipofilico", "grande",
    "pesada", "mas pesado",
}
# Palabras que indican "extremo menor" (min)
_WORDS_MIN = {
    "menor", "mas chica", "mas liviana", "mas pequena", "menos lipofilica",
    "menos lipofilico", "mas baja", "menor valor", "peor", "menos",
    "mas hidrofilica", "mas hidrofilico", "chica", "liviana", "pequena",
    "mas liviano", "mas chico", "mas pequeno",
}


def _norm(text: str) -> str:
    """Normalizar tildes: 'pequeña' → 'pequena', 'más' → 'mas', etc."""
    table = {
        "á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u",
        "ü": "u", "ñ": "n",
    }
    return "".join(table.get(c, c) for c in text.lower())

# Nombres de moléculas conocidas (para respuestas legibles)
_KNOWN_NAMES = [
    "aspirina", "ibuprofeno", "paracetamol", "cafeina", "morfina",
    "etanol", "dopamina", "glucosa", "testosterona", "taxol",
    "penicilina", "amoxicilina", "diazepam", "fluoxetina",
    "sertralina", "omeprazol", "serotonina", "adrenalina",
]


def _detect_metric(message: str) -> Optional[str]:
    """Detectar qué métrica pide la pregunta. None si ninguna es clara."""
    lo = _norm(message)
    for metric, spec in _METRICS.items():
        for kw in spec["keywords"]:
            if kw in lo:
                return metric
    # "pesa menos/más" → peso molecular (sin decir 'peso molecular')
    if "pesa" in lo or "pesado" in lo or "pesada" in lo:
        return "molecular_weight"
    return None


def _detect_direction(message: str, metric: str) -> str:
    """Detectar si la pregunta pide el MAYOR (max) o el MENOR (min) valor.

    Usa semántica de la métrica: para afinidad "mejor" = más negativo = min.
    """
    lo = _norm(message)
    spec = _METRICS[metric]

    # Palabras de dirección explícitas
    has_max = any(w in lo for w in _WORDS_MAX)
    has_min = any(w in lo for w in _WORDS_MIN)

    if has_max and not has_min:
        return "max"
    if has_min and not has_max:
        return "min"
    if has_max and has_min:
        # Ambos (ej. "mayor o menor") → devolver el natural de la métrica
        return spec["natural_order"]

    # Sin palabra explícita de dirección → usar la pregunta general:
    # "cuál es el mejor score?" → mejor = según la métrica
    if any(w in lo for w in ("mejor", "top", "mejores")):
        return "max" if spec["better_is"] == "higher" else "min"

    # Default: el orden natural de la métrica (lo "mejor" primero)
    return spec["natural_order"]


def _direction_to_order(direction: str) -> str:
    """'max' → ranking desc, 'min' → ranking asc."""
    return "desc" if direction == "max" else "asc"


def parse_ranking_table(tool_text: str) -> list[dict]:
    """Parsear la tabla del ranking de rank_session_molecules.

    Formato:
      [Ranking de 3 moléculas por molecular_weight (asc)]
        1. paracetamol: 151.2 Da
        2. aspirina: 180.2 Da
    Devuelve lista de {name, value} en el orden del ranking.
    """
    rows: list[dict] = []
    for line in tool_text.splitlines():
        line = line.strip()
        m = re.match(r"^(\d+)\.\s+(.+?):\s*(-?\d+\.?\d*)", line)
        if m:
            rows.append({"name": m.group(2).strip(), "value": float(m.group(3))})
    return rows


def _fmt(value: float, precision: int) -> str:
    if precision <= 0:
        return f"{int(round(value))}"
    return f"{value:.{precision}f}"


def _human_metric(metric: str, direction: str) -> str:
    """Nombre legible de la métrica según la dirección de la pregunta."""
    labels = {
        "molecular_weight": "peso molecular",
        "log_p": "lipofilicidad (LogP)",
        "tpsa": "TPSA",
        "affinity_kcal": "afinidad",
        "total_score": "score",
        "hbd": "H-bond donors",
        "hba": "H-bond acceptors",
        "rotatable_bonds": "enlaces rotables",
        "heavy_atoms": "átomos pesados",
        "rings": "anillos",
    }
    return labels.get(metric, metric)


def _describe_winner(metric: str, direction: str) -> str:
    """Frase natural para el ganador según métrica y dirección."""
    spec = _METRICS[metric]
    if direction == "max":
        if metric == "log_p":
            return "la más lipofílica"
        if metric == "affinity_kcal":
            return "la de peor afinidad (menos negativa)"
        if metric == "molecular_weight":
            return "la más pesada"
        return f"la de mayor {_human_metric(metric, direction)}"
    else:
        if metric == "log_p":
            return "la menos lipofílica (más hidrofílica)"
        if metric == "affinity_kcal":
            return "la de mejor afinidad (más negativa)"
        if metric == "molecular_weight":
            return "la más liviana"
        return f"la de menor {_human_metric(metric, direction)}"


# ── Respuesta para ranking de sesión ─────────────────────────────────

def build_rank_response(message: str, tool_text: str) -> Optional[str]:
    """Construir la respuesta determinista para un ranking de sesión.

    Devuelve la respuesta final (str) o None si no se puede responder
    de forma determinista (el caller cae al modelo).
    """
    metric = _detect_metric(message)
    if metric is None:
        # Sin métrica clara pero con "mayor/menor" → default peso molecular
        lo = _norm(message)
        if any(w in lo for w in ("mayor", "menor", "mas")):
            metric = "molecular_weight"
        else:
            return None

    direction = _detect_direction(message, metric)
    rows = parse_ranking_table(tool_text)
    if len(rows) < 1:
        return None

    spec = _METRICS[metric]
    unit = spec["unit"]
    prec = spec["precision"]

    # El ranking de la tool ya viene ordenado por natural_order.
    # Para el extremo pedido: si el ranking está en el orden pedido, el
    # primero es el extremo; si no, hay que invertir.
    order = _direction_to_order(direction)
    # Reordenar según la dirección pedida
    sorted_rows = sorted(
        rows, key=lambda r: r["value"],
        reverse=(direction == "max"),
    )
    winner = sorted_rows[0]
    others = sorted_rows[1:]

    winner_desc = _describe_winner(metric, direction)
    parts = [
        f"Entre las {len(rows)} moléculas de esta conversación, "
        f"{winner_desc} es **{winner['name']}** con "
        f"{_fmt(winner['value'], prec)}{unit}."
    ]

    # Añadir el ranking completo (compacto) si hay más de una
    if len(sorted_rows) > 1:
        ranking_str = ", ".join(
            f"{i}. {r['name']} ({_fmt(r['value'], prec)}{unit})"
            for i, r in enumerate(sorted_rows, 1)
        )
        parts.append(f"Ranking: {ranking_str}.")

    return " ".join(parts)


# ── Respuesta para comparación par a par (compare_molecules) ─────────

def build_compare_response(message: str, tool_text: str) -> Optional[str]:
    """Construir la respuesta determinista para compare_molecules.

    El tool result de compare_molecules tiene formato:
      Comparación:
        MW: A=180.2 | B=206.3 (Δ=+26.1)
        LogP: A=1.31 | B=3.07 (Δ=+1.76)
    La respuesta indica qué molécula es mayor/menor en cada métrica.
    """
    # Detectar los nombres A y B del tool result (el chat_service los
    # inyecta como "compare_molecules (A=aspirina | B=ibuprofeno): ...")
    header_m = re.search(r"\(A=([^ |]+)\s*\|\s*B=([^ )]+)\)", tool_text)
    if not header_m:
        return None
    name_a, name_b = header_m.group(1), header_m.group(2)

    # Extraer las filas de comparación: "MW: A=180.2 | B=206.3"
    lines: list[str] = []
    for line in tool_text.splitlines():
        m = re.match(r"^\s*([A-Za-z]+):\s*A=(-?\d+\.?\d*)\s*\|\s*B=(-?\d+\.?\d*)", line)
        if m:
            metric_label, va, vb = m.group(1), float(m.group(2)), float(m.group(3))
            lines.append((metric_label, va, vb))

    if not lines:
        return None

    # Construir la comparación por métrica
    parts = [f"Comparación entre {name_a} y {name_b}:"]
    for metric_label, va, vb in lines:
        if abs(va - vb) < 0.001:
            cmp_str = "iguales"
        elif va > vb:
            cmp_str = f"mayor en {name_a} ({va:g} vs {vb:g})"
        else:
            cmp_str = f"mayor en {name_b} ({vb:g} vs {va:g})"
        parts.append(f"- {metric_label}: {cmp_str}")

    return "\n".join(parts)


# ── Respuesta para comparación N-moléculas (3+) ─────────────────────

_MULTI_METRICS = [
    ("MW", "MW"),
    ("LogP", "LogP"),
    ("TPSA", "TPSA"),
    ("H-Bond Donors", "HBD"),
    ("H-Bond Acceptors", "HBA"),
    ("Rotatable Bonds", "RotBonds"),
    ("Heavy Atoms", "HeavyAtoms"),
    ("Rings", "Rings"),
]


def build_multi_compare_response(message: str, rows: list[dict]) -> Optional[str]:
    """Construir la tabla comparativa determinista para N moléculas (3+).

    `rows` es la lista de dicts que el chat_service armó ejecutando
    compute_properties por cada molécula:
        [{"name": "amlodipino", "smiles": "...", "result": "MW: 422.9 Da, ..."}]

    Cada `result` tiene el formato de compute_properties:
        "MW: 422.9 Da, LogP: 2.66, TPSA: 99.9 A^2, H-Bond Donors: 2, ..."

    Devuelve una tabla Markdown-alineada con los valores reales. Devuelve
    None si no puede parsear al menos 1 métrica (el caller cae al LLM).
    """
    if not rows or len(rows) < 2:
        return None

    # Parsear cada fila: métrica -> valor
    parsed: list[dict] = []
    for row in rows:
        result = row.get("result") or ""
        if "Error" in result:
            return None  # alguna molécula falló → no construir tabla parcial
        values: dict[str, float] = {}
        ok = False
        for metric_label, _key in _MULTI_METRICS:
            m = re.search(
                re.escape(metric_label) + r"\s*:\s*([-\d]+\.?\d*)", result
            )
            if m:
                values[metric_label] = float(m.group(1))
                ok = True
        if not ok:
            return None
        parsed.append({"name": row.get("name") or row.get("smiles", "")[:20],
                       "values": values})

    # Encabezado + filas
    names = [p["name"] for p in parsed]
    header = " | ".join(["Métrica"] + names)
    sep = " | ".join(["---"] * (len(names) + 1))
    lines = [header, sep]

    for metric_label, _key in _MULTI_METRICS:
        # Solo incluir métricas que TODAS las moléculas tienen.
        if all(metric_label in p["values"] for p in parsed):
            cells = [
                f"{p['values'][metric_label]:g}" for p in parsed
            ]
            lines.append(f"{metric_label} | " + " | ".join(cells))

    return "\n".join(lines)


# ── Respuesta para historial (query_history) ─────────────────────────

def build_history_response(message: str, tool_text: str) -> Optional[str]:
    """Construir la respuesta determinista para query_history.

    El tool result de query_history tiene formato:
      [Historial - N evaluaciones ordenadas por total_score (desc)]
        1. nombre | target | score=87.5 | aff=-8.2 | MW=180.2 | Lipinski=OK

    Caso especial: si el usuario preguntó por la "última" evaluación
    (sort_by=created_at, limit=1), responde directo: "La última evaluación
    fue ... score=..." en vez de listar todo el historial.
    """
    if "[Historial" not in tool_text:
        return None

    # Extraer el header de orden
    header_m = re.search(r"ordenadas por (\w+)\s*\((\w+)\)", tool_text)
    sort_field = header_m.group(1) if header_m else "score"
    order = header_m.group(2) if header_m else "desc"

    rows = []
    for line in tool_text.splitlines():
        line = line.strip()
        m = re.match(r"^(\d+)\.\s+(.+)$", line)
        if m and "|" in line:
            rows.append(m.group(2))

    if not rows:
        return None

    # Caso "última evaluación": 1 fila ordenada por created_at
    if sort_field == "created_at" and len(rows) == 1:
        row = rows[0]
        return f"La última evaluación fue: {row}"
    if sort_field == "created_at":
        # Ordenado por fecha pero varias filas → mostrar con énfasis en la 1ª
        parts = [
            f"Evaluaciones más recientes ({order}):"
        ]
        for i, row in enumerate(rows, 1):
            prefix = "→ " if i == 1 else f"{i}. "
            parts.append(f"{prefix}{row}")
        return "\n".join(parts)

    parts = [
        f"Tu historial tiene {len(rows)} evaluaciones, "
        f"ordenadas por {sort_field} ({order}):"
    ]
    for i, row in enumerate(rows, 1):
        parts.append(f"{i}. {row}")
    return "\n".join(parts)


# ── Respuesta para propiedades de una molécula (compute_properties) ──

def build_properties_response(tool_text: str) -> Optional[str]:
    """Construir la respuesta determinista para compute_properties.

    Tool result: "compute_properties (aspirina): MW: 180.2 Da, LogP: 1.31,
    TPSA: 63.6 A^2, H-Bond Donors: 1, ..."
    Devuelve una tabla limpia en texto plano (sin redacción del modelo).
    """
    m = re.search(r"compute_properties \(([^)]+)\):\s*(.+)", tool_text)
    if not m:
        return None
    name, body = m.group(1), m.group(2)

    props = []
    for key in ("MW", "LogP", "TPSA"):
        pm = re.search(rf"{key}:\s*(-?\d+\.?\d*)", body)
        if pm:
            props.append(f"{key}: {pm.group(1)}")
    for key in ("H-Bond Donors", "H-Bond Acceptors", "Rotatable Bonds",
                "Heavy Atoms", "Rings"):
        pm = re.search(rf"{key}:\s*(\d+)", body)
        if pm:
            props.append(f"{key}: {pm.group(1)}")

    if not props:
        return None

    return f"Propiedades de {name}:\n" + "\n".join(f"- {p}" for p in props)
