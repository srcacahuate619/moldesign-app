# FEP-06-HUM — Blind audit challenge: can you set up FEP from this package alone?

MolDesign exports each docking run as a **run package**: the source structure, the prepared receptor, ligand inputs and poses,
the exact parameters and software versions, a preparation audit (`preparacion/audit.json`) with every decision and its reason,
SHA-256 checksums, and a readable dossier (`dossier.pdf`) that also states what was **not** evaluated.

The product claims that a colleague can pick up such a package without asking the sender anything. So far that claim has
only been tested by LLM reviewers. This challenge asks **people who prepare free-energy or MD calculations** to try to break it.

## What you do (about 30–60 min per package)

1. Open an issue with the **"FEP-06-HUM review"** template saying you want to take part. We assign you **two packages** from
   `packages/`, first come first served. You can review more if you like.
2. Treat each package as if a colleague handed it to you for an FEP setup. Use **only the package**, plus public sources
   such as the PDB entry or the literature. Do not contact us about the content.
3. Fill in the template:
   - your verdict:
     - `READY_TO_PREPARE`: you could set up the calculation without asking anything that changes the result;
     - `PREPARABLE_WITH_QUESTIONS`: workable, but with open scientific questions for the sender;
     - `NOT_PREPARABLE`: something critical is missing or hidden;
   - the **14 handoff needs** below, each marked RECONSTRUCTIBLE / AMBIGUOUS / MISSING / NOT_APPLICABLE;
   - **anything the package dropped or changed from the source structure without saying so**, with the file and the line.

**Good to know:** some packages were built to be hard, and **at least one has a known problem that the product does not
declare**. We don't say which one. Abstaining is a valid answer for the product: a package that says "blocked" because of a
real problem is doing its job.

## The 14 handoff needs

| | Need |
|---|---|
| N01 | Source structure and biological assembly |
| N02 | Prepared receptor: what was kept, what was removed, and why |
| N03 | Receptor protonation in the site, and who decided it |
| N04 | Ligand identity |
| N05 | Ligand protonation state and tautomer |
| N06 | Starting pose and where it came from |
| N07 | Waters |
| N08 | Metals and cofactors, and coordination that is not modelled |
| N09 | Missing atoms or residues in the site |
| N10 | Alternate locations (altlocs) |
| N11 | Covalent binding or membrane environment |
| N12 | Versions, seeds, parameters and hashes |
| N13 | Decision log |
| N14 | Experimental reference and atom mapping for a series |

## The packages

| Package | System | Receptor route |
|---|---|---|
| P01 | EGFR (1M17) | B: structure prepared by the user (PDBFixer) |
| P02 | KIT kinase (3G0E) | A: from the catalog |
| P03 | VMAT2 (8T69), the system shown in the video | A: from the catalog |
| P04 | Proteasome (6HW5) | A: from the catalog |
| P05 | Carbonic anhydrase II (2AW1) | A: from the catalog |
| P06 | BRAF V600E (4FK3) | A: from the catalog |
| P07 | EGFR (1M17) | A: from the catalog |
| P08 | EGFR (1M17) | C: PDBQT only, no source structure |
| P09 | p38α (OpenFF protein-ligand-benchmark, PDB 3FLY) | B: structure prepared by the user |
| P10 | HIV-1 protease (1HSG) | A: from the catalog |

Every package was exported unchanged by the product. `packages/SHA256SUMS` lists their hashes. Each package also verifies itself:
`python scripts/verify_dossier_package.py challenge/FEP-06-HUM/packages/P0X.zip` from the repository root.

The ten packages were generated on 2026-10-26 (UTC) through the product's own API, in English, from one build whose
`backend/` and `tools/` are identical to commit `b361d730` of this repository. Each run started from the public PDB entry or
the user's file and went through the same steps a user would take: upload or pick the receptor, evaluate the ligand with Vina,
export the run package.

## What you get

- Every admitted reviewer is **credited by name** (or the name you choose) as a collaborator in the app's
  *About MolDesign* page and in the public write-up of FEP-06-HUM.
- If you go further and rebuild a package for FEP or MD, documenting what you had to guess, you are listed as a
  **contributor** to the write-up.
- The results are published **whatever they show**, including a NO_GO.

## How it is decided (pre-registered)

The rules were committed before any package was generated: [`REGISTRO_PREVIO.md`](REGISTRO_PREVIO.md) (in Spanish).

- **NO_GO:** at least one confirmed silent loss outside the control package, or the product claiming a transfer state that
  does not hold. A finding is confirmed if one admitted reviewer reports it and we verify it against the source and the
  audit.
- **GO:** none of the above, the known problem is found by at least half of the reviews of its package, and the clean
  package gets a median of at most one false alarm per review.
- **INCONCLUSIVE:** the known problem goes unnoticed, or there are fewer than 3 reviewers.
- The round closes on **2026-12-06** or after 20 admitted reviews, whichever comes first.

**The answer key** (which system is the control, which facts each package should let you find, and the assignment list) is sealed.
Its SHA-256 is:

    332d187d8c75add85212ebf6482709bd272cecfdc492b90124d45d4c6aa6dabc

It is published in full when the round closes, so anyone can check that it was not changed after the reviews came in.

## Fine print

- **Allowed:** the package, the PDB, the OpenFF benchmark and the literature.
- **Please declare** if you used a language model. A review written by a model does not count; an assisted one does, and is
  reported separately.
- The packages come from the current **development build (1.0.4, not yet released)**. The source code is in this repository.
- Some JSON keys and a few strings are still in Spanish (`corrida` = run, `decididos` = decided). The translation is in progress
  and is not one of the problems you are asked to find.
- MolDesign runs AutoDock Vina 1.2.7. It **does not run FEP or MD**: it prepares and audits the system that an external
  calculation would use. Nothing here certifies compatibility with FEP+, OpenFE or any other protocol.
- Licences: MolDesign is PolyForm Noncommercial 1.0.0 (source-available). PDB structures are public domain. The p38α structure
  comes from the [OpenFF protein-ligand-benchmark](https://github.com/openforcefield/protein-ligand-benchmark) (CC BY 4.0).
