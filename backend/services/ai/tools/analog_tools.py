"""
services/ai/tools/analog_tools.py

MolChat tools for analog generation via BRICS fragmentation.
generate_analogs — genera análogos de una molécula
explain_fragments — explica la fragmentación BRICS de una molécula
"""

from __future__ import annotations

import json

from services.ai.tool_registry import ToolDef, get_tool_registry


async def generate_analogs(smiles: str, n: str = "20", strategy: str = "all") -> str:
    """
    Genera análogos de una molécula hit usando fragmentación BRICS.
    
    Args:
        smiles: SMILES de la molécula padre
        n: Cantidad de análogos a generar (max 50)
        strategy: Estrategia: all, scaffold_hop, substituent_swap, diversity
    """
    try:
        n_analogs = min(int(n), 50)
    except ValueError:
        n_analogs = 20

    valid_strategies = {"all", "scaffold_hop", "substituent_swap", "diversity"}
    strategy = strategy if strategy in valid_strategies else "all"

    try:
        from services.chemistry.analog_generator import AnalogGenerator, AnalogStrategy

        gen = AnalogGenerator()
        gen_strategy = AnalogStrategy(strategy)

        # Build fragment library
        _ensure_library_built(gen)

        candidates = gen.generate(smiles, n_analogs=n_analogs, strategy=gen_strategy)

        if not candidates:
            return json.dumps({
                "ok": True,
                "parent": smiles,
                "n_analogs": 0,
                "message": (
                    "No se generaron análogos válidos. "
                    "Posibles causas: molécula muy pequeña (<5 átomos pesados), "
                    "biblioteca de fragmentos vacía, o filtros muy estrictos."
                ),
                "analogs": [],
            })

        data = {
            "ok": True,
            "parent": smiles,
            "strategy": strategy,
            "n_analogs": len(candidates),
            "library_stats": {
                "cores": gen.fragment_library.n_cores,
                "substituents": gen.fragment_library.n_substituents,
                "total": gen.fragment_library.n_total,
            },
            "analogs": [c.to_dict() for c in candidates],
        }

        top = candidates[0]
        result = json.dumps(data)
        return (
            f"[ANALOGS] Generated {len(candidates)} analogs from '{smiles}' "
            f"(strategy: {strategy}).\n\n"
            f"Top 3:\n"
            + "\n".join(
                f"  {i+1}. {c.smiles} "
                f"(QED={c.qed:.2f} SA={c.sa_score:.1f} "
                f"sim={c.morgan_similarity:.2f})"
                for i, c in enumerate(candidates[:3])
            )
            + f"\n\n📊 Biblioteca: {gen.fragment_library.n_total} fragments "
            f"({gen.fragment_library.n_cores} cores, "
            f"{gen.fragment_library.n_substituents} substit.)\n\n"
            + f"{result}"
        )

    except Exception as e:
        return json.dumps({"ok": False, "error": f"Analog generation failed: {e}"})


async def explain_fragments(smiles: str) -> str:
    """
    Explica la estructura de una molécula: scaffold Murcko,
    fragmentación BRICS, y propiedades drug-likeness clave.
    """
    try:
        from rdkit import Chem
        from rdkit.Chem import BRICS, Descriptors, Lipinski, QED, rdMolDescriptors
        from rdkit.Chem.Scaffolds import MurckoScaffold

        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return json.dumps({"ok": False, "error": f"SMILES inválido: {smiles}"})

        scaffold = MurckoScaffold.GetScaffoldForMol(mol)
        scaffold_smi = Chem.MolToSmiles(scaffold) if scaffold else "N/A"

        # MOLCHAT-AUD-01 (SCI): un fallo de BRICS se tragaba y la molécula
        # quedaba reportada con «Fragmentos BRICS: 0», que es un hecho químico
        # distinto de «no se pudo fragmentar». Cero es un resultado; el fallo
        # no lo es.
        brics_frags = []
        brics_evaluado = True
        try:
            brics_frags = list(BRICS.BRICSDecompose(mol, minFragmentSize=2))
        except Exception:
            brics_frags = []
            brics_evaluado = False

        props = {
            "smiles": smiles,
            "scaffold": scaffold_smi,
            "n_heavy_atoms": mol.GetNumHeavyAtoms(),
            "n_brics_fragments": len(brics_frags) if brics_evaluado else None,
            "brics_evaluado": brics_evaluado,
            "brics_fragments": [f.replace("*", "[*]") for f in brics_frags[:8]],
            "mw": round(Descriptors.MolWt(mol), 1),
            "logp": round(Descriptors.MolLogP(mol), 2),
            "qed": round(QED.default(mol), 3),
            "hbd": Lipinski.NumHDonors(mol),
            "hba": Lipinski.NumHAcceptors(mol),
            "tpsa": round(rdMolDescriptors.CalcTPSA(mol), 1),
            "rot_bonds": rdMolDescriptors.CalcNumRotatableBonds(mol),
            "n_rings": rdMolDescriptors.CalcNumRings(mol),
            "n_aromatic_rings": rdMolDescriptors.CalcNumAromaticRings(mol),
        }

        result = json.dumps({"ok": True, **props})
        return (
            f"[STRUCTURE] Analisis de '{smiles}':\n"
            f"  Scaffold: {scaffold_smi}\n"
            f"  Átomos pesados: {props['n_heavy_atoms']}\n"
            + (
                f"  Fragmentos BRICS: {props['n_brics_fragments']}\n"
                if brics_evaluado
                else "  Fragmentos BRICS: no se pudo fragmentar la molécula "
                     "(no lo leas como cero fragmentos)\n"
            )
            + f"  MW: {props['mw']} | logP: {props['logp']} | QED: {props['qed']}\n"
            f"  HBD: {props['hbd']} | HBA: {props['hba']} | TPSA: {props['tpsa']}\n"
            f"  Enlaces rotables: {props['rot_bonds']} | Anillos: {props['n_rings']}\n\n"
            + result
        )

    except Exception as e:
        return json.dumps({"ok": False, "error": f"Molecule explanation failed: {e}"})


def _ensure_library_built(gen) -> None:
    """Build fragment library from available data if not already built."""
    if gen._frag_lib and gen._frag_lib._built:
        return

    from pathlib import Path
    from services.chemistry.fragment_library import FragmentLibrary

    data_dir = Path(__file__).parent.parent.parent.parent.parent / "data"

    chembl_files = []
    decoy_files = []

    for pattern in ["chembl_*_actives.txt", "multitarget/*/actives.txt"]:
        for f in data_dir.glob(pattern):
            chembl_files.append(str(f))

    for pattern in ["multitarget/*/decoys.smi", "*_decoys.smi"]:
        for f in data_dir.glob(pattern):
            decoy_files.append(str(f))

    lib = FragmentLibrary()
    lib.build(chembl_files=chembl_files, decoy_files=decoy_files)
    gen._frag_lib = lib


def register_analog_tools(verbose: bool = False):
    """Registrar herramientas de generacion de analogos en MolChat.
    
    Args:
        verbose: Si True, descripciones largas (mas tokens). Si False, minimalistas.
    """
    registry = get_tool_registry()

    gen_desc = (
        "Genera analogos (derivados) de una molecula usando fragmentacion "
        "BRICS y una biblioteca de fragmentos drug-like. Soporta scaffold "
        "hopping, intercambio de sustituyentes y diversidad quimica. "
        "Devuelve analogos rankeados por QED y synthetic accessibility."
    ) if verbose else (
        "Genera analogos por scaffold hopping o intercambio de sustituyentes."
    )

    explain_desc = (
        "Explica la estructura de una molecula: scaffold Murcko, "
        "fragmentacion BRICS, y propiedades drug-likeness (MW, logP, QED, "
        "TPSA, etc). Util para entender POR QUE un analogo fue sugerido."
    ) if verbose else (
        "Explica scaffold, fragmentacion BRICS y propiedades drug-likeness."
    )

    registry.register(ToolDef(
        name="generate_analogs",
        clase="inferencia",
        procedencia="fragmentación BRICS + biblioteca local; el ranking QED/SA es estimado",
        description=gen_desc,
        parameters={
            "smiles": {"type": "str", "required": True, "description": "SMILES de la molecula padre"},
            "n": {"type": "int", "required": False, "description": "Cantidad de analogos (default 20, max 50)"},
            "strategy": {"type": "str", "required": False, "description": "all, scaffold_hop, substituent_swap, diversity"},
        },
        offline=True,
        category="analog",
        fn=generate_analogs,
    ))

    registry.register(ToolDef(
        name="explain_fragments",
        clase="calculo",
        procedencia="RDKit (scaffold Murcko y BRICS)",
        description=explain_desc,
        parameters={
            "smiles": {"type": "str", "required": True, "description": "SMILES de la molecula a explicar"},
        },
        offline=True,
        category="analog",
        fn=explain_fragments,
    ))
