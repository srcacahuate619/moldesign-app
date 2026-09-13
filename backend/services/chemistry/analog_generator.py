"""
Analog Generator — BRICS-based molecular optimization engine.

Given a "hit" molecule, generates analogs by:
1. BRICS decomposition → identify scaffold + substituents
2. Scaffold hopping → replace core with alternative cores
3. Substituent swapping → replace side chains with alternatives
4. Property filtering → QED, SA Score, Lipinski, PAINS
5. Scoring → Vina + XGBoost + CL-GNN + MolChamb (when available)
6. Ranking → sort by composite score, diversity, novelty
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from enum import Enum
from typing import Callable

from rdkit import Chem, RDLogger
from rdkit.Chem import (
    AllChem,
    BRICS,
    Descriptors,
    Lipinski,
    QED,
    rdMolDescriptors,
)
from rdkit.Chem.Scaffolds import MurckoScaffold

RDLogger.logger().setLevel(RDLogger.ERROR)

# ── Data types ────────────────────────────────────────────────────────────


class AnalogStrategy(str, Enum):
    ALL = "all"                    # try everything
    SCAFFOLD_HOP = "scaffold_hop"  # keep substituents, change core
    SUBSTITUENT_SWAP = "substituent_swap"  # keep core, change side chains
    DIVERSITY = "diversity"       # maximize chemical diversity


@dataclass
class AnalogCandidate:
    smiles: str
    parent_smiles: str
    strategy: AnalogStrategy
    morgan_similarity: float  # Tanimoto to parent
    qed: float
    sa_score: float
    mw: float
    logp: float
    hbd: int
    hba: int
    tpsa: float
    rot_bonds: int
    composite_score: float | None = None  # from scoring pipeline
    vina_affinity: float | None = None
    ml_prob: float | None = None
    clgnn_prob: float | None = None
    molchamb_score: float | None = None
    explanation: str = ""

    def to_dict(self) -> dict:
        return {
            "smiles": self.smiles,
            "parent_smiles": self.parent_smiles,
            "strategy": self.strategy.value,
            "morgan_similarity": round(self.morgan_similarity, 3),
            "qed": round(self.qed, 3),
            "sa_score": round(self.sa_score, 3),
            "mw": round(self.mw, 1),
            "logp": round(self.logp, 1),
            "hbd": self.hbd,
            "hba": self.hba,
            "tpsa": round(self.tpsa, 1),
            "rot_bonds": self.rot_bonds,
            "composite_score": round(self.composite_score, 4) if self.composite_score is not None else None,
            "vina_affinity": round(self.vina_affinity, 2) if self.vina_affinity is not None else None,
            "ml_prob": round(self.ml_prob, 4) if self.ml_prob is not None else None,
            "clgnn_prob": round(self.clgnn_prob, 4) if self.clgnn_prob is not None else None,
            "molchamb_score": round(self.molchamb_score, 4) if self.molchamb_score is not None else None,
            "explanation": self.explanation,
        }


# ── SA Score (Synthetic Accessibility) ────────────────────────────────────

def _compute_sa_score(mol: Chem.Mol) -> float:
    """
    Simplified SA Score based on Ertl & Schuffenhauer (2009).
    Uses fragment complexity + ring penalty.
    """
    fragment_score = 0.0
    n_fragments = 0

    try:
        fragments = BRICS.BRICSDecompose(mol, minFragmentSize=1)
        n_fragments = len(list(fragments))
    except Exception:
        n_fragments = max(1, mol.GetNumHeavyAtoms() // 4)

    # Fragment complexity: more unique fragments = harder to synthesize
    fragment_score = math.log(max(1, n_fragments))

    # Size penalty
    size_penalty = mol.GetNumHeavyAtoms() / 100.0

    # Ring complexity
    n_rings = rdMolDescriptors.CalcNumRings(mol)
    n_bridge = rdMolDescriptors.CalcNumBridgeheadAtoms(mol)
    ring_penalty = (n_rings * 0.1) + (n_bridge * 0.3)

    # Chirality
    n_chiral = len(Chem.FindMolChiralCenters(mol, includeUnassigned=True))
    chiral_penalty = n_chiral * 0.2

    # Spiro penalty
    spiro_pattern = Chem.MolFromSmarts("[*]([*])([*])([*])")
    n_spiro = len(mol.GetSubstructMatches(spiro_pattern)) if spiro_pattern else 0
    spiro_penalty = n_spiro * 0.5

    # Scale to 1-10 (1=easy, 10=hard)
    raw = fragment_score + size_penalty + ring_penalty + chiral_penalty + spiro_penalty
    sa = min(10.0, max(1.0, raw * 1.5 + 1.0))
    return round(sa, 2)


# ── Property computation ────────────────────────────────────────────────────


def _compute_properties(smiles: str) -> dict | None:
    """Compute drug-likeness properties for a SMILES string."""
    try:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return None

        qed = QED.default(mol)
        sa = _compute_sa_score(mol)
        mw = Descriptors.MolWt(mol)
        logp = Descriptors.MolLogP(mol)
        hbd = Lipinski.NumHDonors(mol)
        hba = Lipinski.NumHAcceptors(mol)
        tpsa = rdMolDescriptors.CalcTPSA(mol)
        rot_bonds = rdMolDescriptors.CalcNumRotatableBonds(mol)

        return {
            "qed": round(qed, 3),
            "sa_score": sa,
            "mw": round(mw, 1),
            "logp": round(logp, 2),
            "hbd": hbd,
            "hba": hba,
            "tpsa": round(tpsa, 1),
            "rot_bonds": rot_bonds,
        }
    except Exception:
        return None


def _passes_filters(props: dict) -> bool:
    """Check if molecule passes drug-likeness filters."""
    return (
        props["qed"] >= 0.2
        and props["sa_score"] <= 6.0
        and 100 <= props["mw"] <= 600
        and -2 <= props["logp"] <= 7
        and props["hbd"] <= 7
        and props["hba"] <= 12
        and props["rot_bonds"] <= 15
    )


def _morgan_similarity(smi1: str, smi2: str) -> float:
    """Compute Tanimoto similarity between two Morgan fingerprints."""
    try:
        m1 = Chem.MolFromSmiles(smi1)
        m2 = Chem.MolFromSmiles(smi2)
        if m1 is None or m2 is None:
            return 0.0
        fp1 = AllChem.GetMorganFingerprintAsBitVect(m1, 3, nBits=2048)
        fp2 = AllChem.GetMorganFingerprintAsBitVect(m2, 3, nBits=2048)

        from rdkit.DataStructs import TanimotoSimilarity

        return TanimotoSimilarity(fp1, fp2)
    except Exception:
        return 0.0


# ── BRICS decomposition ─────────────────────────────────────────────────────


def _decompose_brics(smiles: str) -> tuple[Chem.Mol | None, list[Chem.Mol], list[str]]:
    """
    Decompose molecule into scaffold + substituents via BRICS.

    Returns: (parent_mol, substituent_mols, core_smiles_list)
    """
    try:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return None, [], []

        # Get Murcko scaffold (ring systems + linkers) as the "core"
        scaffold = MurckoScaffold.GetScaffoldForMol(mol)
        if scaffold is None:
            return mol, [], []

        core_smi = Chem.MolToSmiles(scaffold, isomericSmiles=True)

        # BRICS decomposition for substituents
        frags = list(BRICS.BRICSDecompose(mol, minFragmentSize=2))

        # Identify fragments that are NOT part of the scaffold
        substituents = []
        for frag_smi in frags:
            frag_mol = Chem.MolFromSmiles(frag_smi)
            if frag_mol is None:
                continue
            n_dummy = frag_smi.count("*")

            # Check if this fragment is substantially different from scaffold
            if scaffold.HasSubstructMatch(frag_mol) or n_dummy == 0:
                continue

            # Remove dummy atoms for clean substituent
            subst_mol = Chem.DeleteSubstructs(
                Chem.RWMol(frag_mol),
                Chem.MolFromSmarts("[*]"),
            )
            if subst_mol.GetNumAtoms() > 0:
                substituents.append(subst_mol)

        return mol, substituents, [core_smi]
    except Exception:
        return None, [], []


# ── Analog Generator ────────────────────────────────────────────────────────


class AnalogGenerator:
    """BRICS-based analog generator with fragment library integration."""

    def __init__(self, fragment_library=None):
        """
        Args:
            fragment_library: FragmentLibrary instance (auto-built if None)
        """
        self._frag_lib = fragment_library
        self._scorer: Callable | None = None  # async scoring callback

    @property
    def fragment_library(self):
        if self._frag_lib is None:
            from .fragment_library import get_fragment_library

            self._frag_lib = get_fragment_library()
        return self._frag_lib

    def set_scorer(self, scorer: Callable):
        """Set callback for async scoring. scorer(smiles) -> dict with vina/ml/clgnn/molchamb scores."""
        self._scorer = scorer

    def generate(
        self,
        parent_smiles: str,
        target_id: str | None = None,
        n_analogs: int = 50,
        strategy: AnalogStrategy = AnalogStrategy.ALL,
        min_similarity: float = 0.3,
        diversity_threshold: float = 0.9,
    ) -> list[AnalogCandidate]:
        """
        Generate analogs for a hit molecule.

        Args:
            parent_smiles: SMILES of the hit molecule
            target_id: Target protein ID (for context — not used yet)
            n_analogs: Maximum number of analogs to return
            strategy: Generation strategy
            min_similarity: Minimum Tanimoto similarity to parent
            diversity_threshold: Max Tanimoto sim between analogs (prune too similar)

        Returns:
            Ranked list of AnalogCandidate objects
        """
        parent_mol, substituents, cores = _decompose_brics(parent_smiles)
        if parent_mol is None:
            return []

        parent_core_smi = cores[0] if cores else parent_smiles

        candidates: list[AnalogCandidate] = []
        seen_smiles: set[str] = {parent_smiles}

        lib = self.fragment_library
        if not lib._built:
            return []  # library not built yet

        # ── Strategy 1: Scaffold Hopping ──
        if strategy in (AnalogStrategy.ALL, AnalogStrategy.SCAFFOLD_HOP):
            parent_heavy = parent_mol.GetNumHeavyAtoms()
            alternative_cores = lib.search_cores(
                min_atoms=max(3, parent_heavy // 3),
                max_atoms=parent_heavy + 10,
                min_rings=1,
            )

            alt_core_set = set()
            for core in alternative_cores[:30]:
                clean_core = core.smiles.replace("*", "").replace("()", "")
                if clean_core in alt_core_set:
                    continue
                alt_core_set.add(clean_core)

                # Replace scaffold: keep substituents, change core
                # Simple approach: attach substituents as SMILES fragments
                # For now, use heuristic: if parent has scaffold → try alternative
                try:
                    new_smi = _hop_scaffold(
                        parent_smiles, parent_core_smi, core.smiles
                    )
                    if new_smi and new_smi not in seen_smiles:
                        seen_smiles.add(new_smi)
                        cand = _make_candidate(
                            new_smi, parent_smiles, AnalogStrategy.SCAFFOLD_HOP,
                            explanation=f"Scaffold hop: {core.smiles[:30]} (freq={core.frequency})",
                        )
                        if cand:
                            candidates.append(cand)
                except Exception:
                    continue

        # ── Strategy 2: Substituent Swapping ──
        if strategy in (AnalogStrategy.ALL, AnalogStrategy.SUBSTITUENT_SWAP):
            subs = lib.search_substituents(min_atoms=1, max_atoms=25)

            # Group substituents by size
            for sub in subs[:150]:
                clean_sub = sub.smiles.replace("*", "")
                if len(clean_sub) < 2:
                    continue

                try:
                    new_smi = _swap_substituents(parent_smiles, sub.smiles)
                    if new_smi and new_smi not in seen_smiles:
                        seen_smiles.add(new_smi)
                        cand = _make_candidate(
                            new_smi, parent_smiles, AnalogStrategy.SUBSTITUENT_SWAP,
                            explanation=f"Substituent: {clean_sub[:30]} (freq={sub.frequency})",
                        )
                        if cand:
                            candidates.append(cand)
                except Exception:
                    continue

        # ── Strategy 3: BRICS recombination ──
        if strategy in (AnalogStrategy.ALL, AnalogStrategy.DIVERSITY):
            brics_frags = list(BRICS.BRICSDecompose(parent_mol, minFragmentSize=2))

            # Find similar-sized fragments from library
            for frag in brics_frags:
                frag_mol = Chem.MolFromSmiles(frag)
                if frag_mol is None:
                    continue
                f_heavy = frag_mol.GetNumHeavyAtoms()
                n_dummy = frag.count("*")

                alt_frags = lib.search_substituents(
                    min_atoms=max(1, f_heavy - 3),
                    max_atoms=f_heavy + 5,
                )

                for alt in alt_frags[:10]:
                    try:
                        new_smi = _replace_fragment(parent_smiles, frag, alt.smiles)
                        if new_smi and new_smi not in seen_smiles:
                            seen_smiles.add(new_smi)
                            cand = _make_candidate(
                                new_smi, parent_smiles, AnalogStrategy.DIVERSITY,
                                explanation=f"BRICS swap: {frag[:20]} -> {alt.smiles[:20]} (freq={alt.frequency})",
                            )
                            if cand:
                                candidates.append(cand)
                    except Exception:
                        continue

        # ── Filter & Rank ──
        candidates = [
            c for c in candidates
            if c.morgan_similarity >= min_similarity
        ]

        # Diversity pruning: remove candidates too similar to each other
        if diversity_threshold < 1.0:
            candidates.sort(key=lambda c: c.qed, reverse=True)
            pruned: list[AnalogCandidate] = []
            for c in candidates:
                too_similar = False
                for existing in pruned:
                    if _morgan_similarity(c.smiles, existing.smiles) > diversity_threshold:
                        too_similar = True
                        break
                if not too_similar:
                    pruned.append(c)
            candidates = pruned

        # Rank by QED (will be re-ranked if scorer is available)
        candidates.sort(key=lambda c: (c.qed, -c.sa_score), reverse=True)
        return candidates[:n_analogs]

    async def generate_with_scoring(
        self,
        parent_smiles: str,
        target_id: str | None = None,
        n_analogs: int = 30,
        strategy: AnalogStrategy = AnalogStrategy.ALL,
    ) -> list[AnalogCandidate]:
        """
        Generate analogs AND score them through the full pipeline.
        Uses scoring callback if set.
        """
        candidates = self.generate(
            parent_smiles, target_id, n_analogs, strategy
        )

        if self._scorer:
            # v1.5: Usar predict_batch_rescore para inferencia vectorizada (10-50x speedup)
            # v1.7: Pasar propiedades reales del AnalogCandidate, no defaults inventados
            try:
                from services.rescoring_service import predict_batch_rescore
                mol_dicts = [
                    {
                        "smiles": c.smiles,
                        "molecular_weight": c.mw,
                        "logp": c.logp,
                        "tpsa": c.tpsa,
                        "hbd": c.hbd,
                        "hba": c.hba,
                        "rotatable_bonds": c.rot_bonds,
                        "qed": c.qed,
                    }
                    for c in candidates
                ]
                batch_results = predict_batch_rescore(mol_dicts)
                if batch_results:
                    for c, result in zip(candidates, batch_results):
                        if result:
                            c.ml_prob = result.get("classifier_prob")
                            c.composite_score = result.get("score_a")
                else:
                    # Fallback a one-by-one si el modelo no esta disponible
                    for c in candidates:
                        try:
                            scores = self._scorer(c.smiles)
                            c.ml_prob = scores.get("ml_prob")
                            c.composite_score = scores.get("composite")
                        except Exception:
                            pass
            except ImportError:
                # Fallback a one-by-one si rescoring_service no esta disponible
                for c in candidates:
                    try:
                        scores = self._scorer(c.smiles)
                        c.vina_affinity = scores.get("vina_score")
                        c.ml_prob = scores.get("ml_prob")
                        c.clgnn_prob = scores.get("clgnn_prob")
                        c.molchamb_score = scores.get("molchamb_score")
                        c.composite_score = scores.get("composite")
                    except Exception:
                        pass

        # Re-rank with scores
        def _key(c: AnalogCandidate) -> float:
            score = c.composite_score or 0.5
            qed_bonus = c.qed * 0.1
            sa_penalty = max(0, (c.sa_score - 5) * 0.05)
            return score + qed_bonus - sa_penalty

        candidates.sort(key=_key, reverse=True)
        return candidates[:n_analogs]


# ── Internal helpers ────────────────────────────────────────────────────────


def _make_candidate(
    smiles: str, parent_smiles: str, strategy: AnalogStrategy, explanation: str = ""
) -> AnalogCandidate | None:
    """Create an AnalogCandidate with computed properties. Rejects invalid molecules."""
    # Basic SMILES validation
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None

    # Reject multi-component (disconnected) molecules
    fragments = Chem.GetMolFrags(mol)
    if len(fragments) > 1:
        return None

    # Reject molecules that are trivially identical to parent
    if smiles == parent_smiles:
        return None

    # Sanitize and get clean SMILES
    try:
        canonical = Chem.MolToSmiles(mol, isomericSmiles=True)
    except Exception:
        return None

    props = _compute_properties(canonical)
    if props is None or not _passes_filters(props):
        return None

    sim = _morgan_similarity(canonical, parent_smiles)

    return AnalogCandidate(
        smiles=canonical,
        parent_smiles=parent_smiles,
        strategy=strategy,
        morgan_similarity=sim,
        explanation=explanation,
        **props,
    )


def _hop_scaffold(parent_smi: str, old_core_smi: str, new_core_smi: str) -> str | None:
    """
    Replace scaffold in parent molecule with alternative core.
    Simple approach: return cleaned new core as a molecule.
    Real scaffold hopping would require R-group enumeration.
    """
    try:
        import re

        # Clean the new core: remove dummy atoms
        clean_core = re.sub(r"\[\d+\*\]", "", new_core_smi)
        clean_core = clean_core.replace("[*]", "").replace("*", "").replace("()", "")

        if not clean_core or len(clean_core) < 2:
            return None

        new_mol = Chem.MolFromSmiles(clean_core)
        if new_mol is None:
            return None

        # For scaffold hopping: return the new scaffold as a simplified analog
        # Full implementation would attach the parent's substituents to this core
        return Chem.MolToSmiles(new_mol, isomericSmiles=True)

    except Exception:
        return None


def _swap_substituents(parent_smi: str, new_sub_smi: str) -> str | None:
    """
    Swap a substituent on the parent Murcko scaffold with a new one.
    Properly forms a single bond between scaffold and substituent.
    """

    try:
        parent_mol = Chem.MolFromSmiles(parent_smi)
        if parent_mol is None:
            return None

        scaffold = MurckoScaffold.GetScaffoldForMol(parent_mol)
        if scaffold is None or scaffold.GetNumHeavyAtoms() < 2:
            return None

        # Clean the new substituent of dummy atoms
        sub_clean = re.sub(r"\[\d+\*\]", "", new_sub_smi)
        sub_clean = sub_clean.replace("[*]", "").replace("*", "")

        if not sub_clean or len(sub_clean) < 1:
            return None

        sub_mol = Chem.MolFromSmiles(sub_clean)
        if sub_mol is None:
            return None

        # Find atoms in scaffold that have free valence (can form new bond)
        scaffold_rw = Chem.RWMol(scaffold)
        n_atoms_before = scaffold_rw.GetNumAtoms()

        # Combine scaffold and substituent, then form a bond
        combined = Chem.CombineMols(scaffold, sub_mol)
        rw = Chem.RWMol(combined)

        # Find the first atom in scaffold with an implicit H to use as attachment point
        # and the first atom in substituent to attach
        attach_scaffold = -1
        for i in range(n_atoms_before):
            atom = rw.GetAtomWithIdx(i)
            if atom.GetAtomicNum() > 1 and atom.GetNumImplicitHs() > 0:
                # Prefer carbon atoms with free valence
                if atom.GetAtomicNum() == 6:
                    attach_scaffold = i
                    break
                elif attach_scaffold < 0:
                    attach_scaffold = i

        # Find attachment point on substituent
        attach_sub = -1
        for i in range(n_atoms_before, rw.GetNumAtoms()):
            atom = rw.GetAtomWithIdx(i)
            if atom.GetAtomicNum() > 1 and atom.GetNumImplicitHs() > 0:
                if atom.GetAtomicNum() == 6:
                    attach_sub = i
                    break
                elif attach_sub < 0:
                    attach_sub = i

        if attach_scaffold < 0 or attach_sub < 0:
            return None

        rw.AddBond(attach_scaffold, attach_sub, Chem.BondType.SINGLE)

        Chem.SanitizeMol(rw)
        return Chem.MolToSmiles(rw, isomericSmiles=True)

    except Exception:
        return None


def _replace_fragment(parent_smi: str, old_frag: str, new_frag: str) -> str | None:
    """Replace one BRICS fragment with another using SMILES substitution."""
    try:
        # Clean both fragments of attachment markers
        old_clean = old_frag
        new_clean = new_frag
        for pattern in [r"\[\d+\*\]", r"\[\*\]", r"\*"]:
            import re
            old_clean = re.sub(pattern, "", old_clean)
            new_clean = re.sub(pattern, "", new_clean)

        if not old_clean or not new_clean:
            return None

        if old_clean in parent_smi and old_clean != new_clean:
            new_smi = parent_smi.replace(old_clean, new_clean, 1)

            # Validate
            new_mol = Chem.MolFromSmiles(new_smi)
            if new_mol is None:
                return None

            # Check that it's structurally valid (connected)
            fragments = Chem.GetMolFrags(new_mol)
            if len(fragments) > 1:
                return None  # disconnected fragments

            return Chem.MolToSmiles(new_mol, isomericSmiles=True)

        return None
    except Exception:
        return None
