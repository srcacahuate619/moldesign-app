"""
Fragment Library — BRICS-based fragment database for analog generation.

Builds a library of BRICS fragments from ChEMBL actives and benchmark decoys.
Classifies fragments into CORES (>=2 attachment points) and SUBSTITUENTS (1 attachment).
Fragments are deduplicated by SMILES and sorted by drug-likeness frequency.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from rdkit import Chem, RDLogger
from rdkit.Chem import BRICS, Descriptors, rdMolDescriptors

RDLogger.logger().setLevel(RDLogger.ERROR)


@dataclass
class Fragment:
    smiles: str
    mol: Chem.Mol
    frequency: int = 0
    is_core: bool = False       # >=2 attachment points
    n_attach: int = 0            # number of dummy atoms ([*])
    sources: list[str] = field(default_factory=list)  # which datasets it came from
    mw: float = 0.0
    rot_bonds: int = 0
    ring_count: int = 0

    def __hash__(self):
        return hash(self.smiles)


class FragmentLibrary:
    """Pre-built library of drug-like BRICS fragments."""

    def __init__(self):
        self.cores: dict[str, Fragment] = {}          # scaffolds
        self.substituents: dict[str, Fragment] = {}   # side chains
        self._built = False

    def build(
        self,
        chembl_files: list[str] | None = None,
        decoy_files: list[str] | None = None,
        max_fragments: int = 5000,
    ) -> "FragmentLibrary":
        """
        Build fragment library from ChEMBL actives and DUD-E decoys.

        Args:
            chembl_files: Paths to ChEMBL active molecule files (SMILES per line)
            decoy_files: Paths to decoy molecule files (SMILES per line)
            max_fragments: Maximum unique fragments to keep (per category)
        """
        if self._built:
            return self

        all_smiles: list[str] = []
        source_map: dict[str, str] = {}

        # Load ChEMBL actives
        for fpath in (chembl_files or []):
            try:
                with open(fpath) as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        # Skip headers, comments, and empty lines
                        if line.startswith("#") or line.startswith("SMILES") or line.startswith("//"):
                            continue
                        smi = line.split()[0] if line.split() else line
                        # Validate SMILES
                        if smi and len(smi) > 1:
                            try:
                                mol = Chem.MolFromSmiles(smi)
                                if mol:
                                    all_smiles.append(smi)
                                    source_map[smi] = Path(fpath).stem
                            except Exception:
                                pass
            except Exception:
                pass

        # Load decoys
        for fpath in (decoy_files or []):
            try:
                with open(fpath) as f:
                    for line in f:
                        smi = line.strip().split()[0]
                        if smi and smi not in source_map:
                            all_smiles.append(smi)
                            source_map[smi] = Path(fpath).stem
            except Exception:
                pass

        # Remove duplicates while preserving order
        seen = set()
        unique_smiles = []
        for smi in all_smiles:
            if smi not in seen:
                seen.add(smi)
                unique_smiles.append(smi)

        # BRICS fragment all molecules
        frag_counter: Counter = Counter()
        frag_info: dict[str, tuple[Chem.Mol, int]] = {}  # smiles -> (mol, n_attach)

        for smi in unique_smiles:
            try:
                mol = Chem.MolFromSmiles(smi)
                if mol is None or mol.GetNumHeavyAtoms() < 5:
                    continue

                # BRICS fragmentation (2D — no 3D embedding needed)
                fragments = list(BRICS.BRICSDecompose(mol, minFragmentSize=3))
                for frag_smi in fragments:
                    frag_mol = Chem.MolFromSmiles(frag_smi)
                    if frag_mol is None:
                        continue

                    n_dummy = frag_smi.count("*")
                    if n_dummy == 0:
                        continue  # not a real fragment (BRICS gave back full mol)

                    # Clean version without attachment points for display
                    clean_smi = Chem.MolToSmiles(frag_mol, isomericSmiles=True)
                    n_heavy = frag_mol.GetNumHeavyAtoms()

                    if n_heavy < 2:
                        continue  # skip tiny fragments

                    frag_counter[clean_smi] += 1
                    if clean_smi not in frag_info:
                        frag_info[clean_smi] = (frag_mol, n_dummy)

            except Exception:
                continue

        # Classify and build
        for frag_smi, count in frag_counter.most_common():
            if frag_smi not in frag_info:
                continue

            frag_mol, n_attach = frag_info[frag_smi]

            try:
                mw = Descriptors.MolWt(frag_mol)
                rot_bonds = rdMolDescriptors.CalcNumRotatableBonds(frag_mol)
                rings = rdMolDescriptors.CalcNumRings(frag_mol)
            except Exception:
                mw, rot_bonds, rings = 0.0, 0, 0

            is_core = n_attach >= 2
            target_dict = self.cores if is_core else self.substituents

            if len(target_dict) >= max_fragments:
                continue

            target_dict[frag_smi] = Fragment(
                smiles=frag_smi,
                mol=frag_mol,
                frequency=count,
                is_core=is_core,
                n_attach=n_attach,
                mw=mw,
                rot_bonds=rot_bonds,
                ring_count=rings,
            )

        self._built = True
        return self

    def get_cores(self, exclude: set[str] | None = None, max_n: int = 50) -> list[Fragment]:
        """Get most frequent core fragments, optionally excluding some."""
        cores = sorted(self.cores.values(), key=lambda f: f.frequency, reverse=True)
        if exclude:
            cores = [c for c in cores if c.smiles not in exclude]
        return cores[:max_n]

    def get_substituents(self, exclude: set[str] | None = None, max_n: int = 200) -> list[Fragment]:
        """Get most frequent substituent fragments, optionally excluding some."""
        subs = sorted(self.substituents.values(), key=lambda f: f.frequency, reverse=True)
        if exclude:
            subs = [s for s in subs if s.smiles not in exclude]
        return subs[:max_n]

    def search_cores(self, min_atoms: int = 5, max_atoms: int = 40, min_rings: int = 1) -> list[Fragment]:
        """Search core fragments by size/ring constraints."""
        results = []
        for f in self.cores.values():
            n_heavy = f.mol.GetNumHeavyAtoms() if f.mol else 0
            if min_atoms <= n_heavy <= max_atoms and f.ring_count >= min_rings:
                results.append(f)
        return sorted(results, key=lambda f: f.frequency, reverse=True)

    def search_substituents(self, min_atoms: int = 1, max_atoms: int = 30) -> list[Fragment]:
        """Search substituent fragments by size."""
        results = []
        for f in self.substituents.values():
            n_heavy = f.mol.GetNumHeavyAtoms() if f.mol else 0
            if min_atoms <= n_heavy <= max_atoms:
                results.append(f)
        return sorted(results, key=lambda f: f.frequency, reverse=True)

    @property
    def n_cores(self) -> int:
        return len(self.cores)

    @property
    def n_substituents(self) -> int:
        return len(self.substituents)

    @property
    def n_total(self) -> int:
        return self.n_cores + self.n_substituents


# Singleton instance
_library: FragmentLibrary | None = None


def get_fragment_library(
    chembl_files: list[str] | None = None,
    decoy_files: list[str] | None = None,
    force_rebuild: bool = False,
) -> FragmentLibrary:
    """Get or build the singleton FragmentLibrary."""
    global _library
    if _library is None or force_rebuild:
        _library = FragmentLibrary()
        _library.build(chembl_files=chembl_files, decoy_files=decoy_files)
    return _library
