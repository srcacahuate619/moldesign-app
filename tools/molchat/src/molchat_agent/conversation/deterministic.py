"""Deterministic responders: code builds factual answers, the model never does.

Reimplemented from MolDesign's ``deterministic_responder.py`` (metric
semantics, direction words, answer shapes) without importing it. The
superación over the original: typed inputs instead of regex-parsing tool
text — values flow from tools to answers without a text round-trip where
names and numbers can cross.
"""

from __future__ import annotations

from dataclasses import dataclass

METRICS: dict[str, dict] = {
    "molecular_weight": {
        "keywords": ["peso molecular", "masa molecular", "pesada", "liviana",
                     "grande", "chica", "peso", "mw", "masa", "pesado"],
        "unit": " Da",
        "precision": 1,
        "natural_order": "asc",
        "better_is": "lower",
    },
    "log_p": {
        "keywords": ["lipofil", "logp", "log p", "hidrofil"],
        "unit": "",
        "precision": 2,
        "natural_order": "desc",
        "better_is": "higher",
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
        "natural_order": "asc",
        "better_is": "lower",
    },
    "total_score": {
        "keywords": ["score", "puntaje", "puntuacion", "mejor evaluad"],
        "unit": "/100",
        "precision": 1,
        "natural_order": "desc",
        "better_is": "higher",
    },
    "hbd": {
        "keywords": ["h-bond donor", "donadores", "donors", "hbd"],
        "unit": "",
        "precision": 0,
        "natural_order": "desc",
        "better_is": "lower",
    },
    "hba": {
        "keywords": ["h-bond acceptor", "aceptores", "acceptors", "hba"],
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

_WORDS_MAX = {
    "mayor", "mas grande", "mas pesada", "mas lipofilica", "mas alta",
    "mas", "mayor valor", "mejor", "mas lipofilico", "grande",
    "pesada", "mas pesado",
}
_WORDS_MIN = {
    "menor", "mas chica", "mas liviana", "mas pequena", "menos lipofilica",
    "menos lipofilico", "mas baja", "menor valor", "peor", "menos",
    "mas hidrofilica", "mas hidrofilico", "chica", "liviana", "pequena",
    "mas liviano", "mas chico", "mas pequeno",
}


@dataclass
class MoleculeProps:
    """Typed properties of one molecule. No text parsing downstream."""

    name: str
    smiles: str = ""
    molecular_weight: float | None = None
    log_p: float | None = None
    tpsa: float | None = None
    hbd: int | None = None
    hba: int | None = None
    rotatable_bonds: int | None = None
    heavy_atoms: int | None = None
    rings: int | None = None
    affinity_kcal: float | None = None
    total_score: float | None = None

    def value_of(self, metric: str) -> float | None:
        value = getattr(self, metric, None)
        return None if value is None else float(value)


def _norm(text: str) -> str:
    return text.lower().translate(str.maketrans("áéíóúüñ", "aeiouun"))


def detect_metric(message: str) -> str | None:
    lo = _norm(message)
    for metric, spec in METRICS.items():
        if any(kw in lo for kw in spec["keywords"]):
            return metric
    if "pesa" in lo or "pesado" in lo or "pesada" in lo:
        return "molecular_weight"
    return None


def detect_direction(message: str, metric: str) -> str:
    """Direction for the question: max, min, or the metric's natural order.

    Quality words ("mejor"/"peor"/"top") resolve through the metric's
    ``better_is`` FIRST: "mejor afinidad" is the most negative value (min).
    Fix vs internal, which answers "mejor afinidad" with the worst value
    ("mejor" sits in its max-word set); its own docstring asks for min.
    """
    lo = _norm(message)
    spec = METRICS[metric]
    better_end = "max" if spec["better_is"] == "higher" else "min"
    worse_end = "min" if better_end == "max" else "max"
    has_better = any(w in lo for w in ("mejor", "mejores", "top"))
    has_worse = "peor" in lo
    if has_better and not has_worse:
        return better_end
    if has_worse and not has_better:
        return worse_end
    has_max = any(w in lo for w in _WORDS_MAX)
    has_min = any(w in lo for w in _WORDS_MIN)
    if has_max and not has_min:
        return "max"
    if has_min and not has_max:
        return "min"
    return spec["natural_order"]


def fmt(value: float, precision: int) -> str:
    if precision <= 0:
        return f"{int(round(value))}"
    return f"{value:.{precision}f}"


_HUMAN_METRIC = {
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


def _describe_winner(metric: str, direction: str) -> str:
    label = _HUMAN_METRIC.get(metric, metric)
    if direction == "max":
        if metric == "log_p":
            return "la más lipofílica"
        if metric == "affinity_kcal":
            return "la de peor afinidad (menos negativa)"
        if metric == "molecular_weight":
            return "la más pesada"
        return f"la de mayor {label}"
    if metric == "log_p":
        return "la menos lipofílica (más hidrofílica)"
    if metric == "affinity_kcal":
        return "la de mejor afinidad (más negativa)"
    if metric == "molecular_weight":
        return "la más liviana"
    return f"la de menor {label}"


def build_rank_response(message: str, molecules: list[MoleculeProps]) -> str | None:
    """Deterministic session ranking. None when it cannot answer exactly."""
    metric = detect_metric(message)
    if metric is None:
        # Fix vs internal: bare "mas" ("mas puentes?") must not default to MW;
        # only true comparatives ("mayor"/"menor") earn the MW default.
        if any(w in _norm(message) for w in ("mayor", "menor")):
            metric = "molecular_weight"
        else:
            return None
    direction = detect_direction(message, metric)
    rows = [(m.name, m.value_of(metric)) for m in molecules]
    rows = [(name, value) for name, value in rows if value is not None]
    if not rows:
        return None
    rows.sort(key=lambda item: item[1], reverse=(direction == "max"))
    spec = METRICS[metric]
    unit, prec = spec["unit"], spec["precision"]
    winner_desc = _describe_winner(metric, direction)
    parts = [f"Entre las {len(rows)} moléculas de esta conversación, "
             f"{winner_desc} es **{rows[0][0]}** con "
             f"{fmt(rows[0][1], prec)}{unit}."]
    if len(rows) > 1:
        ranking = ", ".join(f"{i}. {name} ({fmt(value, prec)}{unit})"
                            for i, (name, value) in enumerate(rows, 1))
        parts.append(f"Ranking: {ranking}.")
    return " ".join(parts)


def build_compare_response(name_a: str, props_a: MoleculeProps,
                           name_b: str, props_b: MoleculeProps) -> str:
    """Deterministic pairwise comparison over typed values."""
    rows = [("MW", props_a.molecular_weight, props_b.molecular_weight),
            ("LogP", props_a.log_p, props_b.log_p),
            ("TPSA", props_a.tpsa, props_b.tpsa),
            ("HBD", props_a.hbd, props_b.hbd),
            ("HBA", props_a.hba, props_b.hba)]
    parts = [f"Comparación entre {name_a} y {name_b}:"]
    for label, val_a, val_b in rows:
        if val_a is None or val_b is None:
            continue
        if abs(val_a - val_b) < 0.001:
            parts.append(f"- {label}: iguales ({val_a:g})")
        elif val_a > val_b:
            parts.append(f"- {label}: mayor en {name_a} ({val_a:g} vs {val_b:g})")
        else:
            parts.append(f"- {label}: mayor en {name_b} ({val_b:g} vs {val_a:g})")
    return "\n".join(parts)


_MULTI_METRICS = [
    ("MW", "molecular_weight", 1),
    ("LogP", "log_p", 2),
    ("TPSA", "tpsa", 1),
    ("H-Bond Donors", "hbd", 0),
    ("H-Bond Acceptors", "hba", 0),
    ("Rotatable Bonds", "rotatable_bonds", 0),
    ("Heavy Atoms", "heavy_atoms", 0),
    ("Rings", "rings", 0),
]


def build_multi_compare_response(molecules: list[MoleculeProps]) -> str | None:
    """Markdown table for N molecules. None when a row has no data at all."""
    if len(molecules) < 2:
        return None
    if any(all(m.value_of(field) is None for _, field, _ in _MULTI_METRICS)
           for m in molecules):
        return None  # a molecule failed: no partial tables
    names = [m.name for m in molecules]
    lines = [" | ".join(["Métrica"] + names),
             " | ".join(["---"] * (len(names) + 1))]
    for label, field, precision in _MULTI_METRICS:
        values = [m.value_of(field) for m in molecules]
        if any(v is None for v in values):
            continue  # only metrics every molecule has
        lines.append(f"{label} | " + " | ".join(fmt(v, precision) for v in values))  # type: ignore[arg-type]
    return "\n".join(lines)


def build_properties_response(name: str, props: MoleculeProps) -> str | None:
    """Clean property table. None when there is nothing to show."""
    entries = [("MW", props.molecular_weight, 1),
               ("LogP", props.log_p, 2),
               ("TPSA", props.tpsa, 1),
               ("H-Bond Donors", props.hbd, 0),
               ("H-Bond Acceptors", props.hba, 0),
               ("Rotatable Bonds", props.rotatable_bonds, 0),
               ("Heavy Atoms", props.heavy_atoms, 0),
               ("Rings", props.rings, 0)]
    lines = [f"- {label}: {fmt(value, prec)}"
             for label, value, prec in entries if value is not None]
    if not lines:
        return None
    return f"Propiedades de {name}:\n" + "\n".join(lines)


def build_session_history_response(molecules: list[MoleculeProps]) -> str:
    """What this conversation computed. Persisted history is declared, not faked."""
    if not molecules:
        text = ("En esta conversación aún no calculaste propiedades de "
                "ninguna molécula.")
    else:
        rows = []
        for i, mol in enumerate(molecules, 1):
            detail = ""
            if mol.molecular_weight is not None:
                detail = f" (MW {fmt(mol.molecular_weight, 1)} Da)"
            rows.append(f"{i}. {mol.name}{detail}")
        text = (f"En esta conversación calculaste {len(molecules)} "
                f"moléculas:\n" + "\n".join(rows))
    return text + ("\nEl historial persistido de evaluaciones aún no está "
                   "conectado en este build.")


def build_druglikeness_response(name: str, props: MoleculeProps,
                                pains_recorded: list[str] | None) -> str | None:
    """Lipinski (1997) + Veber (2002) rules over typed values.

    PAINS needs a structural-alerts catalog (platform-side): without a
    recorded evaluation this responder abstains on PAINS instead of
    fabricating the good news ("sin alertas" unexamined).
    """
    mw, logp, hbd, hba = (props.molecular_weight, props.log_p, props.hbd, props.hba)
    rot, tpsa = props.rotatable_bonds, props.tpsa
    if None in (mw, logp, hbd, hba, rot, tpsa):
        return None
    assert mw is not None and logp is not None and tpsa is not None  # typed
    lipinski = mw <= 500 and logp <= 5 and hbd <= 5 and hba <= 10  # type: ignore[operator]
    veber = rot <= 10 and tpsa <= 140  # type: ignore[operator]
    parts = [
        f"Lipinski: {'CUMPLE' if lipinski else 'NO CUMPLE'} "
        f"(MW={mw:.0f}, LogP={logp:.1f}, HBD={hbd}, HBA={hba}).",
        f"Veber: {'CUMPLE' if veber else 'NO CUMPLE'} "
        f"(RotB={rot}, TPSA={tpsa:.0f}).",
    ]
    if pains_recorded is None:
        parts.append("PAINS: no evaluado en este build; "
                     "no afirmo que no haya alertas.")
    elif pains_recorded:
        parts.append(f"PAINS (dato registrado): alertas: "
                     f"{', '.join(pains_recorded)}.")
    else:
        parts.append("PAINS (dato registrado): sin alertas.")
    return f"Drug-likeness de {name}: " + " ".join(parts)
