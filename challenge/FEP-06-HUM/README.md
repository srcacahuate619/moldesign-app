# FEP-06-HUM — Blind audit challenge: can you set up FEP from this package alone?

MolDesign exports each docking run as a **run package**: the source structure, the prepared receptor, ligand inputs and poses,
the exact parameters and software versions, a preparation audit (`preparacion/audit.json`) with every decision and its reason,
SHA-256 checksums, and a readable dossier (`dossier.pdf`) that also states what was **not** evaluated.

The product claims that a colleague can pick up such a package without asking the sender anything. So far that claim has
only been tested by LLM reviewers. This challenge asks **people who prepare free-energy or MD calculations** to try to break it.

## What you do (we expect about 30–60 min per package)

1. **Sign up** by Reddit private message to [u/MolDesign](https://www.reddit.com/user/MolDesign/) or by email to [moldesign619@gmail.com](mailto:moldesign619@gmail.com), or open an issue with the
   [**"FEP-06-HUM sign-up"** template](https://github.com/srcacahuate619/moldesign-app/issues/new?template=fep06-hum-signup.yml).
   Your name, your background and how to reach you are enough. We assign you **two packages** from `packages/`,
   first come first served, and reply privately. You can review more if you like. If you can't finish, tell us so we can
   offer your packages to the next person; we also do that after 14 days without a review, and your review still counts if
   it arrives before the round closes.
2. Treat each package as if a colleague handed it to you for an FEP setup. Use **only the package**, plus public sources
   such as the PDB entry or the literature. Do not contact us about the content.
3. Fill in [`REVIEW_FORM.md`](REVIEW_FORM.md), one per package, and **send it privately**, by Reddit message to [u/MolDesign](https://www.reddit.com/user/MolDesign/) or email to [moldesign619@gmail.com](mailto:moldesign619@gmail.com):
   - your verdict:
     - `READY_TO_PREPARE`: you could set up the calculation without asking anything that changes the result (a silent
       loss rules this out);
     - `PREPARABLE_WITH_QUESTIONS`: workable, but with open scientific questions for the sender;
     - `NOT_PREPARABLE`: something critical is missing or hidden;
   - the **14 handoff needs** below, each marked:
     - `RECONSTRUCTIBLE`: it is in the package, or follows from its files without ambiguity;
     - `AMBIGUOUS`: it is there, but allows more than one reading, or the decision that settles it is missing;
     - `MISSING`: it is not there (say where you looked);
     - `NOT_APPLICABLE`: it does not apply to this package, such as atom mapping when there is only one ligand;
   - **anything the package dropped or changed from the source structure without saying so**, with the file and the line.

**Please keep your findings private until the round closes.** Each review has to be independent: don't post them in issues,
comments or social media, and don't read anyone else's. The form asks whether you saw another review; that doesn't
disqualify you, but it is reported separately. Every review is published, with credit, when the round closes.

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
| P03 | VMAT2 (8T69), the system shown in [the video](https://youtu.be/g6BiVi3rCKI) | A: from the catalog |
| P04 | Proteasome (6HW5) | A: from the catalog |
| P05 | Carbonic anhydrase II (2AW1) | A: from the catalog |
| P06 | BRAF V600E (4FK3) | A: from the catalog |
| P07 | EGFR (1M17) | A: from the catalog |
| P08 | EGFR (1M17) | C: PDBQT only, no source structure |
| P09 | p38α (OpenFF protein-ligand-benchmark, PDB 3FLY) | B: structure prepared by the user |
| P10 | HIV-1 protease (1HSG) | A: from the catalog |

Every package was exported unchanged by the product. To check that yours arrived intact, either of these is enough:

- `sha256sum -c SHA256SUMS` inside `packages/` (on Windows: `Get-FileHash P0X.zip`, and compare with `SHA256SUMS`);
- the package verifier, which also checks every file inside the zip against the package's own manifest. It needs only
  Python 3 and its standard library (tested with 3.11, 3.12 and 3.14), nothing to install. Clone or download the repository
  and run, from its root (`python3` on Linux):

      python scripts/verify_dossier_package.py challenge/FEP-06-HUM/packages/P0X.zip --lang en

  It prints `VALID` or `INVALID`. When a package says `29 present / 30 declared`, the missing file is declared as not
  available in its manifest, with the reason.

The ten packages were generated on 2026-10-26 (UTC) through the product's own API, in English, from one build whose
`backend/` and `tools/` are identical to commit [`b361d730`](https://github.com/srcacahuate619/moldesign-app/tree/b361d730)
of this repository. `main` has moved on since then: to read the code that made the packages, use that commit. The packages
themselves do not declare it (`Code commit` says `NO_DISPONIBLE`, not available), so this paragraph is our statement, not
something the package proves. Each run started from the public PDB entry or the user's file and went through the same steps a
user would take: upload or pick the receptor, evaluate the ligand with Vina, export the run package.

## What you get

- Every admitted reviewer is **credited by name** (or the name you choose) as a collaborator in the app's
  *About MolDesign* page and in the public write-up of FEP-06-HUM.
- If you go further and rebuild a package for FEP or MD, documenting what you had to guess, you are listed as a
  **contributor** to the write-up.
- The results are published **whatever they show**, including a NO_GO.

## How it is decided (pre-registered)

The rules were committed before any package was generated: [`REGISTRO_PREVIO.md`](REGISTRO_PREVIO.md) (in Spanish). That file
stays as it was; what has changed since then is in [`DEVIATIONS.md`](DEVIATIONS.md).

- **Admitted review:** it arrives privately before the round closes, with the verdict, the 14 needs and any silent losses
  with file and line. A person counts once per package: the first review they send.
- **Silent loss:** something from the source structure that the package neither carries nor declares as removed, changed or
  not measured. If the package declares it, even poorly, it is not a silent loss.
- **False alarm:** a need marked AMBIGUOUS or MISSING as undeclared, about something the package does carry or declare. One of
  the ten is the **clean package** used to count them; the sealed key says which.
- **NO_GO:** at least one confirmed silent loss outside the control package, or the product claiming a transfer state that
  does not hold. A finding is confirmed if one admitted reviewer reports it and we verify it against the source and the
  audit.
- **GO:** none of the above, the known problem is found by at least half of the reviews of its package, and the clean
  package gets a median of at most one false alarm per review.
- **INCONCLUSIVE:** the known problem goes unnoticed, there are fewer than 3 reviewers, the control package gets fewer than 2
  reviews, or any other case that is neither GO nor NO_GO.
- The round closes on **2026-12-06** or after 20 admitted reviews, whichever comes first.

**The answer key** (which system is the control, which facts each package should let you find, and the assignment list) is sealed.
Its SHA-256 is:

    332d187d8c75add85212ebf6482709bd272cecfdc492b90124d45d4c6aa6dabc

It is published in full when the round closes, so anyone can check that it was not changed after the reviews came in.

## Fine print

- **Allowed:** the package, the PDB, the OpenFF benchmark and the literature.
- **Not allowed:** the answer key and anything from the earlier LLM rounds (FEP-06-PRE). This repository summarises some of
  it (`AGENTS.md`, `docs/`) and you only need the repository to run the verifier, so please review from the package. If you
  did read those documents, say so in the form.
- **Please declare** if you used a language model. A review written by a model does not count; an assisted one does, and is
  reported separately.
- Reviews arrive by private message or email and are kept unpublished until the round closes. Then they are published
  together with the answer key, under the name you chose or anonymously if you prefer; the form asks which.
- The packages come from a **development build of 1.0.4, not yet released**. The source code is in this repository.
- Some JSON keys and values are still in Spanish. The translation is in progress and is not one of the problems you are asked
  to find:
  - keys: `corrida` = run, `decididos` = decided, `bloqueantes` = blockers, `en_revision` = under review, `estado` = status,
    `fuente` = source, `valor` = value, `razon` and `motivo` = reason;
  - package states: `TRANSFERIBLE` = ready, `REVISION` = needs review, `BLOQUEADO` = blocked;
  - field states: `REGISTRADO` = recorded, `PASA` = passes, `REVISAR` = to review, `ABSTENCION` = abstained,
    `NO_EVALUADO` = not evaluated, `NO_DISPONIBLE` = not available, `NO_APLICA` = not applicable.
- MolDesign runs AutoDock Vina 1.2.7. It **does not run FEP or MD**: it prepares and audits the system that an external
  calculation would use. Nothing here certifies compatibility with FEP+, OpenFE or any other protocol.
- Licences: MolDesign is PolyForm Noncommercial 1.0.0 (source-available). PDB structures are public domain. The p38α structure
  comes from the [OpenFF protein-ligand-benchmark](https://github.com/openforcefield/protein-ligand-benchmark) (CC BY 4.0).
