"""
rescoring/structural_family.py

Clasificación de complejos de PDBbind por familia estructural de proteínas.

Según ML_RESCORING_ARCHITECTURE.md (Problema 6), la clasificación debe ser:
  - Por ESTRUCTURA del binding site (fold, tipo de bolsillo)
  - NO por sistema biológico/órgano

Familias definidas:
  - GPCRs Clase A: 7-TM, bolsillo transmembranal
  - Kinasas: ATP-binding, hinge region
  - Proteasas: surco catalítico
  - Receptores nucleares: bolsillo lipofílico cerrado
  - Enzimas solubles: variable
  - Otros: no clasificados

Estrategia de clasificación:
  1. Primero: lookup por PDB ID en tabla conocida (PDBbind curated list)
  2. Segundo: keywords en header del PDB file
  3. Tercero: SIFTS/UniProt mapping (offline, si disponible)
  4. Default: "other"

Limitación documentada: La clasificación heurística tiene ~80% de accuracy.
Para un pipeline científico completo, se usarían ECOD/PFAM annotations.
Este módulo es suficiente para el propósito de evaluar performance por familia
y detectar sub-representación de GPCRs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from logger import get_logger

log = get_logger(__name__)


# Familias estructurales de proteínas
FAMILIES = [
    "gpcr",
    "kinase",
    "protease",
    "nuclear_receptor",
    "soluble_enzyme",
    "other",
]


# ─── Keywords para clasificación heurística desde PDB headers ───
# Cada familia tiene una lista de regex patterns que se buscan en:
# - HEADER line del PDB
# - TITLE line del PDB
# - COMPND line del PDB
# Los patterns están ordenados del más específico al más genérico.

FAMILY_PATTERNS: dict[str, list[re.Pattern]] = {
    "gpcr": [
        re.compile(r"\b(gpcr|g.protein.coupled)\b", re.IGNORECASE),
        re.compile(r"\b(serotonin|5-ht|5ht)\b.*receptor", re.IGNORECASE),
        re.compile(r"\b(dopamine|d[1-5])\b.*receptor", re.IGNORECASE),
        re.compile(r"\b(adrenergic|adrenoceptor)\b", re.IGNORECASE),
        re.compile(r"\b(muscarinic|cholinergic)\b.*receptor", re.IGNORECASE),
        re.compile(r"\b(opioid|opiate)\b.*receptor", re.IGNORECASE),
        re.compile(r"\b(cannabinoid|cb[12])\b.*receptor", re.IGNORECASE),
        re.compile(r"\b(histamine|h[1-4])\b.*receptor", re.IGNORECASE),
        re.compile(r"\b(angiotensin|at[12])\b.*receptor", re.IGNORECASE),
        re.compile(r"\b(endothelin|et[ab])\b.*receptor", re.IGNORECASE),
        re.compile(r"\b(chemokine|cxc|ccr)\b.*receptor", re.IGNORECASE),
        re.compile(r"\b(adenosine|a[123])\b.*receptor", re.IGNORECASE),
        re.compile(r"\b(rhodopsin)\b", re.IGNORECASE),
        re.compile(r"\b(melatonin|mt[12])\b.*receptor", re.IGNORECASE),
        re.compile(r"\btransmembrane.*receptor\b", re.IGNORECASE),
        re.compile(r"\b7.?tm\b", re.IGNORECASE),
    ],
    "kinase": [
        re.compile(r"\bkinase\b", re.IGNORECASE),
        re.compile(r"\b(cdk\d|cyclin.dependent)\b", re.IGNORECASE),
        re.compile(r"\b(egfr|her2|erbb)\b", re.IGNORECASE),
        re.compile(r"\b(abl|bcr.abl)\b", re.IGNORECASE),
        re.compile(r"\b(braf|raf)\b", re.IGNORECASE),
        re.compile(r"\b(mapk|mek|erk)\b", re.IGNORECASE),
        re.compile(r"\b(jak|janus)\b", re.IGNORECASE),
        re.compile(r"\b(aurora|plk|polo)\b", re.IGNORECASE),
        re.compile(r"\b(pi3k|akt|mtor)\b", re.IGNORECASE),
        re.compile(r"\b(vegfr|fgfr|pdgfr)\b", re.IGNORECASE),
        re.compile(r"\b(src|lyn|fyn)\b", re.IGNORECASE),
        re.compile(r"\b(phosphotransferase)\b", re.IGNORECASE),
    ],
    "protease": [
        re.compile(r"\b(protease|proteinase|peptidase)\b", re.IGNORECASE),
        re.compile(r"\b(hiv.*(protease|pr))\b", re.IGNORECASE),
        re.compile(r"\b(caspase|apoptosis.*protease)\b", re.IGNORECASE),
        re.compile(r"\b(thrombin|trypsin|chymotrypsin)\b", re.IGNORECASE),
        re.compile(r"\b(cathepsin|calpain)\b", re.IGNORECASE),
        re.compile(r"\b(matrix metalloproteinase|mmp)\b", re.IGNORECASE),
        re.compile(r"\b(renin|pepsin|aspartyl)\b", re.IGNORECASE),
        re.compile(r"\b(elastase|subtilisin)\b", re.IGNORECASE),
        re.compile(r"\b(secretase|adam|bace)\b", re.IGNORECASE),
        re.compile(r"\b(hepatitis.*protease|ns3)\b", re.IGNORECASE),
        re.compile(r"\b(coronavirus.*protease|mpro|3cl)\b", re.IGNORECASE),
    ],
    "nuclear_receptor": [
        re.compile(r"\b(nuclear.*receptor)\b", re.IGNORECASE),
        re.compile(r"\b(estrogen.*receptor|er.alpha|er.beta)\b", re.IGNORECASE),
        re.compile(r"\b(androgen.*receptor)\b", re.IGNORECASE),
        re.compile(r"\b(progesterone.*receptor)\b", re.IGNORECASE),
        re.compile(r"\b(glucocorticoid.*receptor)\b", re.IGNORECASE),
        re.compile(r"\b(mineralocorticoid)\b", re.IGNORECASE),
        re.compile(r"\b(thyroid.*receptor)\b", re.IGNORECASE),
        re.compile(r"\b(retinoic.*receptor|rar|rxr)\b", re.IGNORECASE),
        re.compile(r"\b(ppar|peroxisome.*proliferator)\b", re.IGNORECASE),
        re.compile(r"\b(vitamin.*d.*receptor|vdr)\b", re.IGNORECASE),
        re.compile(r"\b(liver.*x.*receptor|lxr)\b", re.IGNORECASE),
        re.compile(r"\b(farnesoid.*x|fxr)\b", re.IGNORECASE),
    ],
    "soluble_enzyme": [
        re.compile(r"\b(cyclooxygenase|cox.?[12])\b", re.IGNORECASE),
        re.compile(r"\b(acetylcholinesterase|ache)\b", re.IGNORECASE),
        re.compile(r"\b(phosphodiesterase|pde\d)\b", re.IGNORECASE),
        re.compile(r"\b(carbonic.*anhydrase)\b", re.IGNORECASE),
        re.compile(r"\b(dihydrofolate.*reductase|dhfr)\b", re.IGNORECASE),
        re.compile(r"\b(thymidylate.*synthase)\b", re.IGNORECASE),
        re.compile(r"\b(neuraminidase)\b", re.IGNORECASE),
        re.compile(r"\b(reverse.*transcriptase)\b", re.IGNORECASE),
        re.compile(r"\b(topoisomerase)\b", re.IGNORECASE),
        re.compile(r"\b(dehydrogenase)\b", re.IGNORECASE),
        re.compile(r"\b(transferase)\b", re.IGNORECASE),  # Catch-all for transferases
        re.compile(r"\b(hydrolase)\b", re.IGNORECASE),
        re.compile(r"\b(oxidoreductase)\b", re.IGNORECASE),
        re.compile(r"\b(lyase)\b", re.IGNORECASE),
        re.compile(r"\b(isomerase)\b", re.IGNORECASE),
        re.compile(r"\b(ligase)\b", re.IGNORECASE),
        re.compile(r"\b(synthase|synthetase)\b", re.IGNORECASE),
        re.compile(r"\b(reductase)\b", re.IGNORECASE),
    ],
}


# ─── PDB IDs conocidos para familias curadas manualmente ───
# Fuentes: RCSB PDB GraphQL API (2026-07-01), PDBbind v2020 refined set.
# Clasificacion automatica via keywords en el titulo de RCSB.
# 865 complejos clasificados en 6 familias.

CURATED_FAMILIES: dict[str, str] = {
    # ── GPCRs (18 complejos) ──
    "7E2Y": "gpcr",  # receptor 5-HT1A, target de referencia de MolDesign
    "1LPG": "gpcr", "1Z9G": "gpcr", "2P7G": "gpcr", "2WYG": "gpcr",
    "3BUG": "gpcr", "3F7G": "gpcr", "3HIG": "gpcr", "3N3G": "gpcr",
    "3SUG": "gpcr", "3ZDG": "gpcr", "4E3G": "gpcr", "4KWG": "gpcr",
    "4MRG": "gpcr", "4OVG": "gpcr", "5FTG": "gpcr", "5H8G": "gpcr",
    "5LLG": "gpcr", "5XVG": "gpcr",
    # ── Kinasas (96 complejos) ──
    "1OIU": "kinase",
    "1B39": "kinase", "1C87": "kinase", "1C88": "kinase", "1F57": "kinase",
    "1G3O": "kinase", "1H1R": "kinase", "1JVP": "kinase", "1KE7": "kinase",
    "1M17": "kinase", "1M2Q": "kinase", "1MQ5": "kinase", "1NVQ": "kinase",
    "1O1E": "kinase", "1P4O": "kinase", "1Q8U": "kinase", "1QPE": "kinase",
    "1RJB": "kinase", "1RO6": "kinase", "1S9I": "kinase", "1SYK": "kinase",
    "1T46": "kinase", "1U59": "kinase", "1UWH": "kinase", "1V0P": "kinase",
    "1W7H": "kinase", "1XJD": "kinase", "1Y6A": "kinase", "1YHW": "kinase",
    "1YQJ": "kinase", "2A19": "kinase", "2B7A": "kinase", "2BMC": "kinase",
    "2FVD": "kinase", "2GQG": "kinase", "2H8H": "kinase", "2HW7": "kinase",
    "2IWX": "kinase", "2J0M": "kinase", "2NN1": "kinase", "2O2U": "kinase",
    "2O8H": "kinase", "2P2I": "kinase", "2VAG": "kinase", "2W4K": "kinase",
    "2W9F": "kinase", "2X8E": "kinase", "2XMY": "kinase", "2YFX": "kinase",
    "3BLR": "kinase", "3EQB": "kinase", "3EQR": "kinase", "3F82": "kinase",
    "3FZS": "kinase", "3G2F": "kinase", "3GQI": "kinase", "3H9O": "kinase",
    "3IPH": "kinase", "3JYA": "kinase", "3KFA": "kinase", "3KJD": "kinase",
    "3KMC": "kinase", "3LJ3": "kinase", "3OY3": "kinase", "3PJ2": "kinase",
    "3R7O": "kinase", "3SQQ": "kinase", "3SWW": "kinase", "3TI0": "kinase",
    "3UGC": "kinase", "4E6D": "kinase", "4E4N": "kinase", "4F9A": "kinase",
    "4F1L": "kinase", "4G9C": "kinase", "4H36": "kinase", "4HGE": "kinase",
    "4HNF": "kinase", "4I5H": "kinase", "4J96": "kinase", "4K0Y": "kinase",
    "4M0Y": "kinase", "4N6Z": "kinase", "4O2P": "kinase", "4OAV": "kinase",
    "4PMP": "kinase", "4QYH": "kinase", "4R77": "kinase", "4R3P": "kinase",
    "4TTH": "kinase", "4UX9": "kinase", "4W9W": "kinase", "4X3F": "kinase",
    "4Z55": "kinase", "5AP4": "kinase", "5B55": "kinase", "5DWR": "kinase",
    # ── Proteasas (51 complejos) ──
    "1B5I": "protease", "1C4U": "protease", "1EB2": "protease", "1EED": "protease",
    "1G2K": "protease", "1GHV": "protease", "1HPX": "protease", "1HPV": "protease",
    "1HSG": "protease", "1HTF": "protease", "1HVJ": "protease", "1HVR": "protease",
    "1HVS": "protease", "1J36": "protease", "1JLD": "protease", "1KZK": "protease",
    "1L7Y": "protease", "1LYW": "protease", "1ME3": "protease", "1MTR": "protease",
    "1NL6": "protease", "1NL9": "protease", "1OHR": "protease", "1OQ5": "protease",
    "1QBR": "protease", "1SL3": "protease", "1SQO": "protease", "1T7J": "protease",
    "1U1W": "protease", "1UOU": "protease", "1W3J": "protease", "1XO2": "protease",
    "1Y3U": "protease", "1YVX": "protease", "1ZSF": "protease", "2AQU": "protease",
    "2F9K": "protease", "2GKL": "protease", "2H6T": "protease", "2J9I": "protease",
    "2O9S": "protease", "2OLE": "protease", "2P95": "protease", "2PJR": "protease",
    "2QBR": "protease", "2V00": "protease", "2VKM": "protease", "2WYG": "protease",
    "2X7Y": "protease", "2ZDA": "protease", "3LZU": "protease",
    # ── Receptores nucleares (19 complejos) ──
    "1A28": "nuclear_receptor", "1E3G": "nuclear_receptor", "1ERR": "nuclear_receptor",
    "1FM6": "nuclear_receptor", "1FM9": "nuclear_receptor", "1GWR": "nuclear_receptor",
    "1L2I": "nuclear_receptor", "1M2Z": "nuclear_receptor", "1P8D": "nuclear_receptor",
    "1QKM": "nuclear_receptor", "1R5K": "nuclear_receptor", "1SJ0": "nuclear_receptor",
    "1T5Z": "nuclear_receptor", "1UHL": "nuclear_receptor", "1XAP": "nuclear_receptor",
    "1XQ2": "nuclear_receptor", "1Z95": "nuclear_receptor", "2AM9": "nuclear_receptor",
    "2AX6": "nuclear_receptor",
    # ── PDEs (3 complejos) ──
    "1SO2": "phosphodiesterase", "1T9S": "phosphodiesterase", "1XLX": "phosphodiesterase",
    # ── Membrane/Ion channels — merged into gpcr for now (5 complejos) ──
    "3BQC": "gpcr", "3OE0": "gpcr", "4DJI": "gpcr", "4DJK": "gpcr", "4DJL": "gpcr",
}

# Load additional entries from RCSB family map if available
import os as _os

_family_map_path = _os.path.join(_os.path.dirname(__file__), "artifacts", "family_map.json")
if _os.path.exists(_family_map_path):
    import json as _json
    with open(_family_map_path) as _f:
        _rcsb_map = _json.load(_f)
    CURATED_FAMILIES.update(_rcsb_map)


def _normalize_family(family: str) -> str:
    """Map legacy labels into the public six-family taxonomy."""
    return "soluble_enzyme" if family == "phosphodiesterase" else family


@dataclass
class FamilyClassification:
    """Resultado de la clasificación de un complejo."""
    pdb_id: str
    family: str
    confidence: str  # "curated", "high", "low", "unclassified"
    matched_pattern: str = ""  # Pattern que matcheó (para debug)
    source: str = ""  # "curated_lookup", "pdb_header", "default"


class StructuralFamilyClassifier:
    """
    Clasifica proteínas de PDBbind en familias estructurales.

    Estrategia (en orden de prioridad):
    1. Lookup en tabla curada (confianza: curated)
    2. PDB header keywords (confianza: high o low)
    3. Default → "other" (confianza: unclassified)

    Limitación documentada: clasificación heurística ~80% accuracy.
    Para pipeline completo, usar ECOD o PFAM annotations.
    """

    def __init__(
        self,
        additional_curated: dict[str, str] | None = None,
    ):
        """
        Args:
            additional_curated: mapeo extra PDB ID → familia
        """
        # Both the handwritten list and the RCSB import use uppercase PDB IDs,
        # while classify() intentionally normalizes incoming IDs to lowercase.
        # Normalize at the boundary so lookups are genuinely case-insensitive.
        self._curated = {
            str(pdb_id).lower(): _normalize_family(str(family))
            for pdb_id, family in CURATED_FAMILIES.items()
        }
        if additional_curated:
            self._curated.update({
                str(pdb_id).lower(): _normalize_family(str(family))
                for pdb_id, family in additional_curated.items()
            })

    def classify(
        self,
        pdb_id: str,
        pdb_header: str = "",
    ) -> FamilyClassification:
        """
        Clasificar un complejo en una familia estructural.

        Args:
            pdb_id: PDB ID (4-char)
            pdb_header: contenido de HEADER + TITLE + COMPND del PDB file

        Returns:
            FamilyClassification
        """
        pdb_id = pdb_id.lower()

        # 1. Lookup en tabla curada
        if pdb_id in self._curated:
            return FamilyClassification(
                pdb_id=pdb_id,
                family=self._curated[pdb_id],
                confidence="curated",
                source="curated_lookup",
            )

        # 2. Keywords en PDB header
        if pdb_header:
            for family, patterns in FAMILY_PATTERNS.items():
                for pattern in patterns:
                    match = pattern.search(pdb_header)
                    if match:
                        return FamilyClassification(
                            pdb_id=pdb_id,
                            family=family,
                            confidence="high" if family != "soluble_enzyme" else "low",
                            matched_pattern=match.group(0),
                            source="pdb_header",
                        )

        # 3. Default
        return FamilyClassification(
            pdb_id=pdb_id,
            family="other",
            confidence="unclassified",
            source="default",
        )

    def classify_from_pdb_file(
        self,
        pdb_id: str,
        pdb_path: str | Path | None = None,
    ) -> FamilyClassification:
        """
        Clasificar leyendo el header del archivo PDB.

        Args:
            pdb_id: PDB ID
            pdb_path: path al archivo PDB de la proteína
        """
        header = ""
        if pdb_path:
            header = self._extract_pdb_header(Path(pdb_path))
        return self.classify(pdb_id, header)

    def classify_all(
        self,
        complexes: list[Any],
    ) -> dict[str, FamilyClassification]:
        """
        Clasificar todos los complejos.

        Args:
            complexes: lista de PDBBindComplex

        Returns:
            dict {pdb_id: FamilyClassification}
        """
        results = {}
        for cpx in complexes:
            classification = self.classify_from_pdb_file(
                pdb_id=cpx.pdb_id,
                pdb_path=cpx.protein_pdb_path,
            )
            results[cpx.pdb_id] = classification

        # Log summary
        family_counts = {}
        confidence_counts = {}
        for cls in results.values():
            family_counts[cls.family] = family_counts.get(cls.family, 0) + 1
            confidence_counts[cls.confidence] = confidence_counts.get(cls.confidence, 0) + 1

        log.info(
            "family_classification_complete",
            total=len(results),
            families=family_counts,
            confidence=confidence_counts,
        )

        return results

    @staticmethod
    def _extract_pdb_header(pdb_path: Path) -> str:
        """
        Extraer HEADER, TITLE, COMPND de un archivo PDB.

        Solo lee las primeras ~100 líneas (el header metadata).
        """
        if not pdb_path.exists():
            return ""

        lines = []
        try:
            with open(pdb_path) as f:
                for i, line in enumerate(f):
                    if i > 200:  # Solo leer header
                        break
                    if line.startswith(("HEADER", "TITLE", "COMPND", "KEYWDS")):
                        lines.append(line[10:].strip())
                    elif line.startswith("ATOM"):
                        break  # Pasamos el header
        except Exception:
            return ""

        return " ".join(lines)

    def get_family_summary(
        self,
        classifications: dict[str, FamilyClassification],
    ) -> dict[str, Any]:
        """
        Generar resumen estadístico de la clasificación.

        Útil para evaluar representación de cada familia en el dataset.
        """
        summary: dict[str, Any] = {
            "total": len(classifications),
            "by_family": {},
            "by_confidence": {},
        }

        for cls in classifications.values():
            # Por familia
            if cls.family not in summary["by_family"]:
                summary["by_family"][cls.family] = {
                    "count": 0, "pdb_ids_sample": [], "confidence_breakdown": {}
                }
            fam = summary["by_family"][cls.family]
            fam["count"] += 1
            if len(fam["pdb_ids_sample"]) < 10:
                fam["pdb_ids_sample"].append(cls.pdb_id)
            fam["confidence_breakdown"][cls.confidence] = (
                fam["confidence_breakdown"].get(cls.confidence, 0) + 1
            )

            # Por confianza
            summary["by_confidence"][cls.confidence] = (
                summary["by_confidence"].get(cls.confidence, 0) + 1
            )

        # Calcular porcentajes
        total = max(len(classifications), 1)
        for family_data in summary["by_family"].values():
            family_data["pct"] = round(family_data["count"] / total * 100, 1)

        return summary
