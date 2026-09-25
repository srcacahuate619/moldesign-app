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
    """Ertl-Schuffenhauer SA score as implemented by RDKit Contrib."""
    from rdkit.Contrib.SA_Score import sascorer

    return round(float(sascorer.calculateScore(mol)), 2)


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


def _passes_filters(props: dict, mol: Chem.Mol) -> bool:
    """Check if molecule passes drug-likeness filters."""
    from services.chemistry.structural_alerts import alertas_estructurales

    return (
        not alertas_estructurales(mol)
        and props["qed"] >= 0.2
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
    if props is None or not _passes_filters(props, mol):
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


def _single_dummy(mol: Chem.Mol) -> tuple[int, int] | None:
    dummies = [atom for atom in mol.GetAtoms() if atom.GetAtomicNum() == 0]
    if len(dummies) != 1 or len(dummies[0].GetNeighbors()) != 1:
        return None
    return dummies[0].GetIdx(), dummies[0].GetNeighbors()[0].GetIdx()


def _remove_dummy(mol: Chem.Mol) -> tuple[Chem.Mol, int] | None:
    attachment = _single_dummy(mol)
    if attachment is None:
        return None
    dummy, anchor = attachment
    rw = Chem.RWMol(mol)
    rw.RemoveAtom(dummy)
    if anchor > dummy:
        anchor -= 1
    result = rw.GetMol()
    Chem.SanitizeMol(result)
    return result, anchor


def _join_on_dummies(left: Chem.Mol, right: Chem.Mol) -> str | None:
    """Connect the two declared attachment atoms without choosing an index."""
    lhs, rhs = _single_dummy(left), _single_dummy(right)
    if lhs is None or rhs is None:
        return None
    offset = left.GetNumAtoms()
    rw = Chem.RWMol(Chem.CombineMols(left, right))
    rw.AddBond(lhs[1], offset + rhs[1], Chem.BondType.SINGLE)
    for dummy in sorted((lhs[0], offset + rhs[0]), reverse=True):
        rw.RemoveAtom(dummy)
    mol = rw.GetMol()
    Chem.SanitizeMol(mol)
    if len(Chem.GetMolFrags(mol)) != 1:
        return None
    return Chem.MolToSmiles(mol, isomericSmiles=True)


def _hop_scaffold(parent_smi: str, old_core_smi: str, new_core_smi: str) -> str | None:
    """Transfer one identified parent R group to a core with one explicit site.

    Multi-substituted parents and cores without an attachment marker abstain.
    Returning a bare replacement core would mislabel it as an analog.
    """
    try:
        parent = Chem.MolFromSmiles(parent_smi)
        old_core = Chem.MolFromSmiles(old_core_smi)
        new_core = Chem.MolFromSmiles(new_core_smi)
        if any(x is None for x in (parent, old_core, new_core)):
            return None
        residual = Chem.ReplaceCore(parent, old_core, labelByIndex=True)
        if residual is None or _single_dummy(residual) is None:
            return None
        return _join_on_dummies(new_core, residual)
    except (ValueError, RuntimeError):
        return None


def _swap_substituents(parent_smi: str, new_sub_smi: str) -> str | None:
    """Replace one R group at its original Murcko attachment atom."""
    try:
        parent = Chem.MolFromSmiles(parent_smi)
        new_sub = Chem.MolFromSmiles(new_sub_smi)
        if parent is None or new_sub is None or _single_dummy(new_sub) is None:
            return None
        scaffold = MurckoScaffold.GetScaffoldForMol(parent)
        if scaffold is None or scaffold.GetNumHeavyAtoms() < 2:
            return None
        old_sub = Chem.ReplaceCore(parent, scaffold, labelByIndex=True)
        attachment = _single_dummy(old_sub) if old_sub is not None else None
        if attachment is None:
            return None
        scaffold_index = old_sub.GetAtomWithIdx(attachment[0]).GetIsotope()
        if scaffold_index >= scaffold.GetNumAtoms():
            return None
        core = Chem.RWMol(scaffold)
        dummy = core.AddAtom(Chem.Atom(0))
        core.AddBond(scaffold_index, dummy, Chem.BondType.SINGLE)
        return _join_on_dummies(core.GetMol(), new_sub)
    except (ValueError, RuntimeError):
        return None


def _replace_fragment(parent_smi: str, old_frag: str, new_frag: str) -> str | None:
    """Replace a BRICS fragment only with unique one-bond graph mapping."""
    try:
        parent = Chem.MolFromSmiles(parent_smi)
        old = Chem.MolFromSmiles(old_frag)
        new = Chem.MolFromSmiles(new_frag)
        if any(x is None for x in (parent, old, new)):
            return None
        old_clean = _remove_dummy(old)
        new_clean = _remove_dummy(new)
        if old_clean is None or new_clean is None:
            return None
        query, _ = old_clean
        matches = parent.GetSubstructMatches(query, uniquify=True)
        if len(matches) != 1:
            return None
        matched = set(matches[0])
        external = sum(
            neighbor.GetIdx() not in matched
            for idx in matched
            for neighbor in parent.GetAtomWithIdx(idx).GetNeighbors()
        )
        if external != 1:
            return None
        products = Chem.ReplaceSubstructs(
            parent, query, new_clean[0],
            replaceAll=False, replacementConnectionPoint=new_clean[1],
        )
        if len(products) != 1:
            return None
        product = products[0]
        Chem.SanitizeMol(product)
        if len(Chem.GetMolFrags(product)) != 1:
            return None
        return Chem.MolToSmiles(product, isomericSmiles=True)
    except (ValueError, RuntimeError):
        return None
