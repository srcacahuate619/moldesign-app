# How to reproduce this run

Package: `moldesign_case_350e8d04-4273-41f5-b818-72ab44f3c95e_run_27c62c96-a89`
Dossier model: v1
Generated: 2026-10-10T00:56:56+00:00

## 1. What ran

- Receptor: 8HFI · CRYO-EM STRUCTURE OF HUMAN NOREPINEPHRINE TRANSPORTER NET IN THE
- Run: 27c62c96-a890-47f6-b0c1-095dc6801edb
- Molecule: e5655ee8-fa0b-4c1a-aebe-995548b0281b

The exact parameters are in `run/protocol.json`, under `parametros`. Each has a status: those marked `NO_DISPONIBLE` were not serialized by the run and **cannot be reproduced blindly**.

## 2. Check integrity first

```
python scripts/verify_dossier_package.py <este-archivo>.zip
```

If the result is not `VALID`, do not reproduce anything: the package does not describe what it claims to describe.

## 3. Repeat the docking run

With MolDesign: open the case, restore the inputs from `case/case_snapshot.json`, run the preflight check, and compare the resulting fingerprint with `input_fingerprint`. If they match, the new run starts from the same hypothesis.

Outside MolDesign: check the status of each field in `run/protocol.json`. Only `REGISTRADO` values come from the run; `NO_DISPONIBLE` values prevent you from claiming that the calculation can be reconstructed. Use `inputs/ligand_docked.smi` for the docked species and `inputs/ligand.smi` for the original input when both files are recorded. Also check the prepared receptor and effective search box before repeating Vina. The files `inputs/ligand_input.sdf`, `inputs/ligand_input.pdbqt`, and `logs/vina.log` contain the archived bytes when their SHA-256 hashes matched the run's provenance; their absence is stated in the manifest.

## 3.1. Raw structural evidence

- `evidencia/structural_evidence.json` — the per-pose physical verdict as persisted by the backend: engine, coverage, failed checks, and their reasons.
- `evidencia/pose_selection.json` — the selector's recommendation: Vina top-1, suggested pose, margin, threshold, abstention, and alternatives.
- `evidencia/pose_index.json` — which pose is which and the exact PDBQT block it points to. `outputs/poses.sdf` is included only when it truly represents the collection; for an ensemble, a single-conformation SDF is not presented as the full set.
- `evidencia/pose_selector_model.json` — selector model, version, and SHA-256.

The run configuration is NOT repeated here: it lives in `run/protocol.json`, where each parameter also has a status. A second file with the same plain values would create two places to look and no new check.

The protocol records requested and generated conformers when the stage reported them. It does not record a complete series of restarts; no missing field is filled from the configuration declared by the case.

The PDF is a readable view of these files. They are provided raw so you can check that the document did not add, remove, or soften anything.

These files do NOT say two things: `review` does not mean the pose was approved—the full check suite did not run—and `not_evaluated` describes what happened to the validator, never to the molecule. Neither is negative evidence about the compound.

## 4. What this package does NOT guarantee

- It does not guarantee bit-for-bit reproducibility; that depends on the engine version and hardware.
- It does not guarantee scientific validity. The dossier statuses say what was checked and what was not.
- **A correct checksum demonstrates integrity, not validity.** It proves that the bytes have not changed since the package was created. It does not prove that the method was suitable, the preparation was correct, or the conclusion is true. `VALID` means the files passed verification, not that the science is valid.
- It does not claim that the compound is active, effective, safe, or a drug candidate. Nothing in this package supports that kind of conclusion.
