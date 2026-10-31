# FEP-06-HUM review form

One form per package. Copy it into a Reddit private message to [u/MolDesign](https://www.reddit.com/user/MolDesign/) or an email to [moldesign619@gmail.com](mailto:moldesign619@gmail.com).
Please **don't post it publicly** until the round closes: every review has to be independent.

---

**Name for the credits** (a handle is fine; or "anonymous"):

**Background** (for example FEP with FEP+, OpenFE or Amber; MD; docking; structural biology; years of experience, optional):

**Package** (P01–P10):

**Verdict** (`READY_TO_PREPARE` / `PREPARABLE_WITH_QUESTIONS` / `NOT_PREPARABLE`):

## The 14 handoff needs

One line each: RECONSTRUCTIBLE / AMBIGUOUS / MISSING / NOT_APPLICABLE, and the file or field that supports it. For MISSING, say
where you looked.

- N01 source and biological assembly:
- N02 prepared receptor (kept / removed / why):
- N03 receptor protonation in the site:
- N04 ligand identity:
- N05 ligand protonation and tautomer:
- N06 starting pose and provenance:
- N07 waters:
- N08 metals, cofactors, coordination:
- N09 missing atoms or residues in the site:
- N10 altlocs:
- N11 covalent binding or membrane:
- N12 versions, seeds, parameters, hashes:
- N13 decision log:
- N14 experimental reference / atom mapping:

## Silent losses or changes

Anything dropped or altered from the source structure without being declared. Give the file and the line or field. A silent
loss rules out `READY_TO_PREPARE`.

## Questions you would ask the sender before running FEP

## Time spent (minutes)

## What else did you consult?

The PDB entry, the literature, the OpenFF benchmark, tools, this repository's own documents... and whether a language model
helped, and how.

## Independence

Did you read or hear about anyone else's review of this challenge before sending yours? (yes / no; if yes, which)
