# Contributing to MolDesign

Thanks for considering a contribution! Please read this file first.

## Setup (dev)

MolDesign tiene dos superficies: el backend Python y el desktop Tauri. Para
el backend se usa Python 3.11; para el frontend se usa Node 24.20.x y npm
11.19.x, las versiones declaradas por el proyecto.

    git clone https://github.com/srcacahuate619/moldesign-app.git
    cd moldesign-app
    python -m venv .venv
    .venv\Scripts\activate
    python -m pip install -r backend/requirements-desktop.txt
    python -m pip install pytest pytest-cov
    cd frontend
    npm ci

El runtime embebido, Vina, Open Babel y los pesos no se descargan con npm ni
con pip. Comprueba su estado desde la raíz:

    python scripts/bootstrap_dev_tree.py --check

Si el runtime base está publicado y autorizado para tu entorno, el script puede
aprovisionar el árbol de desarrollo con --fetch. La aplicación instalada no
ejecuta ese script: su runtime viaja dentro del bundle. Qwen y ESMFold son
módulos opcionales del launcher.

## Run the test suite

```bash
pytest rescoring/tests/ -v            # rescoring tests
pytest backend/tests/ -v              # backend tests (API, models, app_mode, ...)\ncd frontend\nnpm run typecheck\nnpm run test:run
pytest rescoring/tests/ -v --cov=rescoring --cov=backend
```

## Commit style — Conventional Commits (mandatory)

Use the conventional commit format. Examples:

- `feat(gnn-v2): add contrastive pretraining on PDBbind refined`
- `fix(benchmark): correct EF@1% calculation when N < 100`
- `docs(roadmap): add Fase 7 section`
- `test(bucket-b): add regression test for dynamic box fallback`
- `chore: bump torch version to 2.4.1`

Avoid:
- "Co-Authored-By" tags (we keep commit history clean).
- Squash merges without descriptive message.

## Pull Request checklist

- [ ] Tests added or updated for changed behavior.
- [ ] `pytest rescoring/tests/ -v` passes locally.
- [ ] Commit messages follow Conventional Commits.
- [ ] No secrets / API keys / personal emails in the diff.
- [ ] `docs/` updated if behavior changed (link in PR description).

## Code style

- Python: 4-space indent, 100 char line limit, type hints on public APIs.
- Avoid emoji in commit messages or code (this codebase uses ASCII).
- Avoid silent-fail patterns. If you `except Exception`, log it.

## Issue triage

Issues tagged:
- `bug` — broken behavior
- `reproducibility` — can't reproduce benchmark
- `silent-fail` — silent failure mode (like Bucket A.1)
- `paper claim` — affects JCIM paper claims
- `bucket-c` — related to GNN-v3 research track (see docs/23)

## License contributions — CLA required

**Before your first pull request is merged you must accept the
[Contributor License Agreement](CLA.md).** It takes one line in `CONTRIBUTORS.md` and
one commit trailer; the CLA file explains how.

You keep the copyright on your work. The CLA grants the project a broad licence to it,
**including the right to distribute it under different terms in the future**. That right
is what allows MolDesign to change its public licence or offer commercial licences
without tracking down every past contributor. An "inbound = outbound" notice alone does
not grant it, and once a contribution lands without it the project's licence is frozen.

Code contributions are distributed under the project's current public licence
(PolyForm Noncommercial 1.0.0). MolDesign-owned model contributions fall under
the same noncommercial grant documented in LICENSE-MODELS. Mention in your PR if
third-party terms apply.

Background on why the licence is what it is, and what would have to change to move it:
[`docs/LICENSING.md`](docs/LICENSING.md).