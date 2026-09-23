"""
services/ai/tools/rdkit_tools.py

Herramientas offline basadas en RDKit con cache local por SMILES.
"""

from __future__ import annotations

import sqlite3
import time

from core.config import directorio_de_datos
from services.ai.tool_registry import ToolDef, get_tool_registry

_TOOL_CACHE = directorio_de_datos("cache") / "tool_cache.db"


def _tool_cache_conn():
    _TOOL_CACHE.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(_TOOL_CACHE))
    c.execute("CREATE TABLE IF NOT EXISTS results (key TEXT PRIMARY KEY, result TEXT, fetched REAL)")
    c.commit()
    return c


def _cache_get(key: str) -> str | None:
    c = _tool_cache_conn()
    row = c.execute("SELECT result FROM results WHERE key=?", (key,)).fetchone()
    c.close()
    return row[0] if row else None


def _cache_set(key: str, result: str):
    c = _tool_cache_conn()
    c.execute("INSERT OR REPLACE INTO results VALUES(?,?,?)", (key, result, time.time()))
    c.commit(); c.close()


async def compute_properties(smiles: str) -> str:
    cache_key = f"props_{smiles}"
    cached = _cache_get(cache_key)
    if cached:
        return cached
    """Calcular propiedades fisicoquímicas de una molécula."""
    try:
        from rdkit import Chem
        from rdkit.Chem import Descriptors, rdMolDescriptors

        mol = Chem.MolFromSmiles(smiles)
        if not mol:
            return "Error: SMILES inválido."

        mw = round(Descriptors.MolWt(mol), 1)
        logp = round(Descriptors.MolLogP(mol), 2)
        tpsa = round(rdMolDescriptors.CalcTPSA(mol), 1)
        hbd = rdMolDescriptors.CalcNumHBD(mol)
        hba = rdMolDescriptors.CalcNumHBA(mol)
        rot_bonds = rdMolDescriptors.CalcNumRotatableBonds(mol)
        heavy = mol.GetNumHeavyAtoms()
        rings = rdMolDescriptors.CalcNumRings(mol)

        result = (
            f"MW: {mw} Da, LogP: {logp}, TPSA: {tpsa} A^2, "
            f"H-Bond Donors: {hbd}, H-Bond Acceptors: {hba}, "
            f"Rotatable Bonds: {rot_bonds}, Heavy Atoms: {heavy}, Rings: {rings}"
        )
        _cache_set(cache_key, result)
        return result
    except ImportError:
        return "Error: RDKit no disponible."
    except Exception as e:
        return f"Error calculando propiedades: {str(e)[:100]}"


async def validate_smiles(smiles: str) -> str:
    """Validar si un SMILES es sintácticamente correcto."""
    try:
        from rdkit import Chem
        mol = Chem.MolFromSmiles(smiles)
        if not mol:
            return f"SMILES inválido: '{smiles}' no es reconocible por RDKit."
        canonical = Chem.MolToSmiles(mol, canonical=True)
        mw = Chem.Descriptors.MolWt(mol)
        return f"Válido. SMILES canónico: {canonical}. Peso molecular: {mw:.1f} Da."
    except ImportError:
        return "Error: RDKit no disponible."
    except Exception as e:
        return f"Error validando: {str(e)[:100]}"


async def check_druglikeness(smiles: str) -> str:
    """Evaluar reglas de drug-likeness: Lipinski, Veber, Ghose, PAINS."""
    try:
        from rdkit import Chem
        from rdkit.Chem import Descriptors, rdMolDescriptors
        from chem.pains import _get_pains_catalog

        mol = Chem.MolFromSmiles(smiles)
        if not mol:
            return "Error: SMILES inválido."

        mw = Descriptors.MolWt(mol)
        logp = Descriptors.MolLogP(mol)
        hbd = rdMolDescriptors.CalcNumHBD(mol)
        hba = rdMolDescriptors.CalcNumHBA(mol)
        tpsa = rdMolDescriptors.CalcTPSA(mol)
        rot = rdMolDescriptors.CalcNumRotatableBonds(mol)

        lipinski = mw <= 500 and logp <= 5 and hbd <= 5 and hba <= 10
        veber = rot <= 10 and tpsa <= 140

        # MOLCHAT-AUD-01 (SCI): aquí el fallo del catálogo se tragaba y la
        # herramienta contestaba «Sin alertas PAINS». Fabricar un negativo es
        # tan prohibido como fabricar un positivo, y es peor de detectar: nadie
        # sospecha de una buena noticia. «No hay alertas» y «no pude mirar» son
        # respuestas distintas.
        pains_entries: list[str] = []
        pains_evaluado = True
        pains_error = ""
        try:
            catalog = _get_pains_catalog()
            matches = catalog.GetMatches(mol)
            pains_entries = [m.GetDescription() for m in matches[:5]]
        except Exception as exc:
            pains_evaluado = False
            pains_error = str(exc)[:80]

        result = (
            f"Lipinski: {'APROBADO' if lipinski else 'FALLIDO'} "
            f"(MW={mw:.0f}, LogP={logp:.1f}, HBD={hbd}, HBA={hba}). "
            f"Veber: {'APROBADO' if veber else 'FALLIDO'} "
            f"(RotB={rot}, TPSA={tpsa:.0f})."
        )
        if not pains_evaluado:
            result += (
                " PAINS: no se pudo evaluar el catálogo"
                f"{f' ({pains_error})' if pains_error else ''} — "
                "no afirmes que no hay alertas."
            )
        elif pains_entries:
            result += f" ⚠️ PAINS ALERTS: {', '.join(pains_entries[:3])}."
        else:
            result += " Sin alertas PAINS."
        return result
    except ImportError:
        return "Error: RDKit no disponible."
    except Exception as e:
        return f"Error en drug-likeness: {str(e)[:100]}"


async def compare_molecules(smiles_a: str, smiles_b: str) -> str:
    """Comparar dos moléculas lado a lado."""
    try:
        from rdkit import Chem
        from rdkit.Chem import Descriptors, rdMolDescriptors

        mol_a = Chem.MolFromSmiles(smiles_a)
        mol_b = Chem.MolFromSmiles(smiles_b)

        if not mol_a:
            return f"Error: SMILES A inválido: {smiles_a[:30]}"
        if not mol_b:
            return f"Error: SMILES B inválido: {smiles_b[:30]}"

        def props(mol):
            return {
                "MW": round(Descriptors.MolWt(mol), 1),
                "LogP": round(Descriptors.MolLogP(mol), 2),
                "HBD": rdMolDescriptors.CalcNumHBD(mol),
                "HBA": rdMolDescriptors.CalcNumHBA(mol),
                "TPSA": round(rdMolDescriptors.CalcTPSA(mol), 1),
                "RotB": rdMolDescriptors.CalcNumRotatableBonds(mol),
            }

        pa = props(mol_a)
        pb = props(mol_b)
        lines = ["Comparación:"]
        for key in ["MW", "LogP", "HBD", "HBA", "TPSA", "RotB"]:
            delta = round(pb[key] - pa[key], 2) if isinstance(pa[key], (int, float)) else "?"
            sign = "+" if isinstance(delta, (int, float)) and delta > 0 else ""
            lines.append(f"  {key}: A={pa[key]} | B={pb[key]} (Δ={sign}{delta})")
        return "\n".join(lines)
    except ImportError:
        return "Error: RDKit no disponible."
    except Exception as e:
        return f"Error comparando: {str(e)[:100]}"


def register_rdkit_tools():
    registry = get_tool_registry()
    registry.register(ToolDef(
        name="compute_properties",
        clase="calculo",
        procedencia="RDKit (descriptores sobre el SMILES dado)",
        description="Calcula MW, LogP, TPSA, HBD, HBA, rotatable bonds, rings de un SMILES.",
        parameters={"smiles": {"type": "string", "required": True}},
        offline=True,
        fn=compute_properties,
    ))
    registry.register(ToolDef(
        name="validate_smiles",
        clase="calculo",
        procedencia="RDKit (parseo y canonicalización)",
        description="Verifica si un SMILES es válido y devuelve su forma canónica.",
        parameters={"smiles": {"type": "string", "required": True}},
        offline=True,
        fn=validate_smiles,
    ))
    registry.register(ToolDef(
        name="check_druglikeness",
        clase="calculo",
        procedencia="RDKit + catálogo PAINS de RDKit",
        description="Evalúa Lipinski, Veber y alertas PAINS de un SMILES.",
        parameters={"smiles": {"type": "string", "required": True}},
        offline=True,
        fn=check_druglikeness,
    ))
    registry.register(ToolDef(
        name="compare_molecules",
        clase="calculo",
        procedencia="RDKit (descriptores de ambos SMILES)",
        description="Compara propiedades de dos moléculas (MW, LogP, HBD, HBA, TPSA).",
        parameters={
            "smiles_a": {"type": "string", "required": True},
            "smiles_b": {"type": "string", "required": True},
        },
        offline=True,
        fn=compare_molecules,
    ))
