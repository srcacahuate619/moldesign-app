"""Chemical vocabulary for speech transcription (es/en).

faster-whisper accepts an ``initial_prompt`` that biases the decoder toward
domain words; the sidecar's own local backend uses it. The platform endpoint
takes no prompt parameter, so platform transcripts get no bias (documented,
not faked). The same lexicon feeds transcription evaluation: expected terms
that a good transcript must contain.
"""

from __future__ import annotations

LEXICON_ES: tuple[str, ...] = (
    "SMILES", "docking", "afinidad", "receptor", "ligando", "pose", "poses",
    "scoring", "rescoring", "ADMET", "Lipinski", "Veber", "farmacóforo",
    "andamiaje", "análogo", "análogos", "cribado", "diana", "proteína",
    "mutación", "solvatación", "hidrofóbico", "puente de hidrógeno",
    "kilocalorías", "nanomolar", "micromolar", "QED", "PAINS", "TPSA",
    "quinasa", "proteasa", "EGFR", "evaluación", "corrida", "expediente",
    "dossier", "propiedades", "toxicidad", "solubilidad",
)

LEXICON_EN: tuple[str, ...] = (
    "SMILES", "docking", "affinity", "receptor", "ligand", "pose", "poses",
    "scoring", "rescoring", "ADMET", "Lipinski", "Veber", "pharmacophore",
    "scaffold", "analog", "analogs", "screening", "target", "protein",
    "mutation", "solvation", "hydrophobic", "hydrogen bond",
    "kilocalories", "nanomolar", "micromolar", "QED", "PAINS", "TPSA",
    "kinase", "protease", "EGFR", "evaluation", "run", "dossier",
    "properties", "toxicity", "solubility",
)

LEXICONS = {"es": LEXICON_ES, "en": LEXICON_EN}


def lexicon(lang: str = "es") -> tuple[str, ...]:
    """Chemical terms for a language (defaults to Spanish)."""
    return LEXICONS.get(lang, LEXICON_ES)


def initial_prompt(lang: str = "es") -> str:
    """Decoder-bias prompt for faster-whisper (comma-joined lexicon)."""
    return "Chemistry vocabulary: " + ", ".join(lexicon(lang)) + "."
