# Reproducible dossier · QA cierre 8HFI

Package: `moldesign_case_350e8d04-4273-41f5-b818-72ab44f3c95e_run_27c62c96-a89`
Case: `350e8d04-4273-41f5-b818-72ab44f3c95e`
Run: `27c62c96-a890-47f6-b0c1-095dc6801edb`
Receptor: 8HFI · CRYO-EM STRUCTURE OF HUMAN NOREPINEPHRINE TRANSPORTER NET IN THE
Generated: 2026-10-10T00:56:56+00:00
Dossier model: v1 · manifest v1

## What this is

The verifiable counterpart to `dossier.pdf`. The PDF is the human-readable view of the case; this package lets you check that the view was based on the files it declares and detect whether any are missing or changed.

**Neither replaces the other.**

## What this is NOT

This is not a recommendation. It does not claim that the molecule is a drug, clinical candidate, or safe compound. The 0–100 indices in the PDF appendix are not probability, confidence, or quality measures, and they are not decision criteria.

## Contents

```
moldesign_case_350e8d04-4273-41f5-b818-72ab44f3c95e_run_27c62c96-a89/
├── README.md              this file
├── dossier.pdf            human-readable view of the case
├── manifest.json          role, size, SHA-256, and status of each file
├── checksums.sha256       sorted hash index
├── case/                  case projection and canonical model
├── run/                   protocol and reproduction instructions
├── inputs/                receptor and ligand, when available
├── outputs/               serialized poses and results
├── evidencia/             structural evidence, selection, and checks
└── logs/                  warnings and errors for THIS run
```

## Integrity

To verify:

```
python scripts/verify_dossier_package.py <este-archivo>.zip
```

Without extracting or running anything, the verifier checks that no entry escapes the root directory, the manifest version is supported, all declared files exist, their SHA-256 hashes and sizes match, and there are no duplicates or undeclared files.

### Three deliberate exclusions

1. **The ZIP does not contain itself.** A package containing its own copy could not be finalized: its hash would change when included.
2. **`checksums.sha256` does not include its own hash.** Writing its hash into the file is impossible for the same reason.
3. **`manifest.json` does not declare itself** in `files`, for the same reason. Its integrity **is** covered: `checksums.sha256` is calculated afterward and includes the manifest, so any change to the manifest is detected.

The verifier knows about all three and does not report them as undeclared files.

### What a checksum proves, and what it does not

A correct checksum demonstrates **integrity, not validity**: the bytes have not changed since the package was created. It does not prove that the method was suitable, the preparation was correct, the poses are physically reasonable, or the conclusion is true. `VALID` is a statement about the FILES, never the science, and this package does not claim that the compound is active, effective, or safe.

## Missing artifacts

A missing file is declared; it is not replaced with a marker that looks like the artifact.

- None: all declared artifacts are present.

## Status glossary

- **NOT DEFINED** — The case did not declare this context.
- **NOT EVALUATED** — The control was not evaluated in this run.
- **NOT AVAILABLE** — The expected result or artifact is unavailable.
- **NOT APPLICABLE** — The control does not apply to this case.
- **REVIEW** — Evidence is available, but it does not support a conclusion on its own.
- **ABSTENTION** — Required evidence is missing or a declared blocker exists.
- **RECORDED** — The data exists and was serialized by the run.
- **PASSED** — The control ran and passed.
