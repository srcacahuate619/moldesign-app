# 24 — OSS Readiness Checklist (Fase 2 roadmap)

> **⚠️ ESTADO DOCUMENTAL: Histórico (snapshot 2026-07-25).** Varias casillas de este checklist ya no reflejan el repositorio actual: `README.md`, `LICENSE`, `CONTRIBUTING.md`, `ci.yml` y `docs/INDEX.md` existen hoy y fueron creados en Fase 2 (commit `40666c0`). Consérvese como registro histórico; para el estado vigente ver README raíz y CI.
> **Fecha**: 2026-07-25
> **Estado**: Checklist accionable derivado de `docs/18_OSS_ROADMAP.md` Fase 2.
> **Objetivo**: llevar el repo a estado clonable → CI verde → reproducible en <1 hr.
> **Pre-requisitos**: Fase 1 (re-corrida + metricas) completa. Fase 0 (5HT1A focused box) completa.

---

## TL;DR — estado actual (2026-07-25)

| # | Item Fase 2 | Status | Notas |
|---|-------------|--------|-------|
| 1 | `README.md` root | ❌ MISSING | crítico — el docs/README no cuenta |
| 2 | `LICENSE` (AGPL-3.0) | ❌ MISSING | bloqueante — sin licence el repo no es OSS |
| 3 | `LICENSE-MODELS` (MolDesign Model License v1.1) | ✅ EXISTE (actualizado) | crítico para assets |
| 4 | `CONTRIBUTING.md` | ❌ MISSING | recomendado por GitHub |
| 5 | `.gitignore` agresivo | ✅ EXISTS (7328 bytes) | ya excluye todo lo necesario |
| 6 | `scripts/download_binaries.ps1` | ❌ MISSING | crítico para reproducibilidad |
| 7 | `scripts/run_5targets_2500.ps1` portable | ⚠️ PARTIAL | existe pero hardcodea paths |
| 8 | `.github/workflows/ci.yml` | ❌ MISSING | crítico — CI verde badge |
| 9 | `.github/ISSUE_TEMPLATE/` (bug + feature) | ❌ MISSING | recomendado |
| 10 | `.github/PULL_REQUEST_TEMPLATE.md` | ❌ MISSING | recomendado |
| 11 | Root `docs/INDEX.md` (o redirect a docs/README) | ❌ MISSING | navegación |

**Coverage**: 1.5/11 items (≈14%). Esta sesión genera una checklist actionsle sin
crear todos los archivos (no-build; el usuario los creará/decidira en sesión
dedicada de escritura Fase 2 proper).

---

## 1. `README.md` (root) — TEMPLATE SUGERIDO

```markdown
# MolDesign

[![CI Status](https://github.com/<user>/moldesign-build/actions/workflows/ci.yml/badge.svg)](https://github.com/<user>/moldesign-build/actions/workflows/ci.yml)
[![License: AGPL-3.0](https://img.shields.io/badge/license-AGPL--3.0-blue.svg)](LICENSE)
[![Models: Source-Available](https://img.shields.io/badge/models-source--available-lightgrey.svg)](LICENSE-MODELS)
[![Paper: JCIM in prep](https://img.shields.io/badge/paper-JCIM--prep-orange.svg)](docs/24_OSS_READINESS_CHECKLIST.md)

**MolDesign** es un pipeline de **drug discovery** open source que combina
docking convencional (AutoDock Vina), rescoring de machine learning (XGBoost
+ GNN-v2 + CL-GNN), y quantum features (xTB) para priorizar ligandos
candidatos sobre blancos proteicos. Diseñado para correr on-premises sin
 GPU obligatoria, ideal para labs académicos con hardware modesto.

## Quickstart

```bash
# 1. Clone + setup (10 min)
git clone https://github.com/<user>/moldesign-build.git
cd moldesign-build
python -m venv .venv && .venv\Scripts\activate  # Windows
pip install -r requirements.txt

# 2. Download binaries (Vina + xTB, ~200 MB)
powershell -File scripts/download_binaries.ps1

# 3. Run the paper benchmark (~8 hr compute on Ryzen 5 / 32 GB)
powershell -File scripts/run_5targets_2500.ps1

# 4. Inspect results
type data\gnn_fixed\ef_report_*_gs.json
```

## What you get

5 standard drug-discovery targets × 4 rescoring methods:

| Target | Family | EF@1% (Vina+XGB) | AUC | N mols |
|--------|--------|-------------------|------|--------|
| 5HT1A | GPCR | 36.85x | 0.8288 | 2547 |
| CDK2 (3pp0) | kinase | 3.98x | 0.9860 | 199 |
| HIV-PR (1HSG) | protease | ... | ... | ... |
| ERα (3ert) | nuclear receptor | ... | ... | ... |
| Factor Xa (1f0r) | protease | ... | ... | ... |

**Primary paper claim**: Vina + XGB stacking. See `docs/metricas_experimentales.md`.

## Documentation

- [`07_SPEARMAN_BENCHMARK_LOG.md`](07_SPEARMAN_BENCHMARK_LOG.md) — iterative benchmark history
- [`08_SCIENTIFIC_VALIDATION.md`](08_SCIENTIFIC_VALIDATION.md) — formal validation
- [`18_OSS_ROADMAP.md`](18_OSS_ROADMAP.md) — project roadmap
- [`19_LIMITATIONS.md`](19_LIMITATIONS.md) — honest limitations (read first!)
- [`21_ABLATION_MOLCHAMB_5HT1A.md`](21_ABLATION_MOLCHAMB_5HT1A.md) — MolChamb ablation
- [`23_BUCKET_C_RESEARCH_TRACK.md`](23_BUCKET_C_RESEARCH_TRACK.md) — GNN-v3 research plan
- [`24_OSS_READINESS_CHECKLIST.md`](24_OSS_READINESS_CHECKLIST.md) — this doc

## License

- **Code**: AGPL-3.0 — see [`LICENSE`](../LICENSE).
- **Models** (`.pth`, `.db` seeds): MolDesign Model License v1.1 (source-available) — see [`LICENSE-MODELS`](../LICENSE-MODELS).
- **Binaries** (Vina, xTB): sus propias licencias (Apache-2.0, GPL/LGPL).

## Contributing

See [`CONTRIBUTING.md`](../CONTRIBUTING.md). Conventional commits requeridos.

## Citation

```bibtex
@unpublished{moldesign2026,
  title={MolDesign: an open-source Vina+XGB+GNN stacking pipeline for docking rescoring},
  author={...},
  year={2026},
  note={JCIM submission in preparation}
}
```
```

---

## 2. `LICENSE` (root, AGPL-3.0 full text)

- Source: https://www.gnu.org/licenses/agpl-3.0.txt
- Copy paste verbatim. 35 KB aprox.
- Sin cambios. AGPL-3.0 es la licence standard del codebase (ya está en `Cargo.toml`/`package.json`).

---

## 3. `LICENSE-MODELS` (root, MolDesign Model License v1.1 — source-available)

```text
MolDesign Model License v1.1 — Source-Available (opción C)

The model weights, checkpoint files (.pth), embeddings databases (.db seeds),
and any configuration metadata that encodes learned parameters distributed as
part of MolDesign are licensed under the MolDesign Model License v1.1
(source-available). This replaces the previous CC-BY-NC-SA 4.0 because the
NonCommercial clause blocked academic labs with industrial funding — the
majority of real-world research use.

Human-readable summary:
  - Research Use (investigación, benchmarking, publicación — incl. empresa
    con fines de investigación): FREE
  - Commercial Product Development (integrar los modelos en un pipeline/
    producto comercial): requires Enterprise license
  - Redistribution of weights/models to third parties: requires Enterprise
  - Offering the Models as a Service / API / SaaS: requires Enterprise
  - Attribution: required in any publication using the Models

Full legal code: see the LICENSE-MODELS file at the repository root.
```

Assets cubiertos:
- `rescoring/artifacts/*.pth` (`gnn_v2_best.pt`, `clgnn_*.pt`, `propagation_gnn.pt`, `deltapki_model.pt`)
- `data/quantum_cache.db` (4522 mols SMILES → quantum features pre-computed)
- `frontend/src-tauri/resources/rescoring/artifacts/*.pt` (bundled en el `.exe`)

---

## 4. `CONTRIBUTING.md` — TEMPLATE SUGERIDO

```markdown
# Contributing to MolDesign

Thanks for considering a contribution! Please read this file first.

## Setup (dev)

```bash
git clone https://github.com/<user>/moldesign-build.git
cd moldesign-build
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
pip install pytest pytest-cov  # dev tools
```

## Run the test suite

```bash
pytest rescoring/tests/ -v            # 36 tests (Bucket A.4 + B.4)
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
- `silence-fail` — silent failure mode (like Bucket A.1)
- `paper claim` — affects what the JCIM paper claims
- `bucket-c` — related to GNN-v3 research track (see docs/23)

## License contributions

By contributing, you agree your contributions are licensed under AGPL-3.0.
Model contributions (weights, learned data) fall under the MolDesign Model
License v1.0 (source-available). Mention in PR if you intend either different
licence.
```

---

## 5. `.github/workflows/ci.yml` — CI Workflow

```yaml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: windows-latest  # primary dev platform is Windows
    steps:
      - uses: actions/checkout@v4
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.14'
      - name: Install deps
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install pytest pytest-cov
      - name: Run tests
        run: pytest rescoring/tests/ -v --cov=rescoring --cov=backend
      - name: Upload coverage
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: coverage
          path: .coverage
```

---

## 6. `.github/ISSUE_TEMPLATE/bug_report.md` + `feature_request.md`

### bug_report.md
```markdown
---
name: Bug report
about: Report a broken behavior
title: "[BUG] <one-line summary>"
labels: bug
assignees: ''
---

## Describe the bug
A clear description of what's wrong.

## To reproduce
Steps to trigger:
1. ...
2. ...

Expected: ...
Actual: ...

## Environment
- OS: [Windows 11 / Linux / macOS]
- Python: [e.g. 3.14.0]
- MolDesign commit: [`git rev-parse --short HEAD`]

## Logs and artefacts
```
<paste relevant log tail or error>
```
```

### feature_request.md
```markdown
---
name: Feature request
about: Suggest a new feature or improvement
title: "[FEAT] <one-line summary>"
labels: enhancement
assignees: ''
---

## Is your feature request related to a problem?
A clear description of what the problem is.

## Proposed solution
What you'd like to see happen.

## Bucket tag
- [ ] bucket-c (GNN-v3 research track)
- [ ] paper claim (affects JCIM paper)
- [ ] reproducibility
- [ ] other

## Alternatives considered
Any alternative approaches you've considered.
```

---

## 7. `.github/PULL_REQUEST_TEMPLATE.md`

```markdown
## What does this PR do?

Brief summary.

## Related issues
- Closes #123
- Refs #456

## Type of change
- [ ] Bug fix (non-breaking)
- [ ] New feature (non-breaking)
- [ ] Breaking change (please describe impact)
- [ ] Documentation only
- [ ] Test only

## Checklist
- [ ] Tests added/updated
- [ ] `pytest rescoring/tests/ -v` passes locally
- [ ] Commit messages follow Conventional Commits
- [ ] No secrets / API keys in diff
- [ ] `docs/` updated if behavior changed

## Bucket tag (if applicable)
- [ ] bucket-c
- [ ] paper claim
- [ ] reproducibility

## Notes for reviewers
Anything specific reviewers should focus on.
```

---

## 8. `scripts/download_binaries.ps1` — binary downloader

```powershell
<#
.SYNOPSIS
  Downloads Vina + xTB binaries from their official sources.
.DESCRIPTION
  Required once after `git clone` before running `run_5targets_2500.ps1`.
  Downloads go to: tools/vina/vina.exe, tools/xtb/xtb-6.7.1/bin/xtb.exe.
#>

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$toolsDir = Join-Path $root 'tools'

# --- Vina (Apache-2.0, Scripps) ---
$vinaDir = Join-Path $toolsDir 'vina'
if (-not (Test-Path $vinaDir)) {
    New-Item -ItemType Directory -Force -Path $vinaDir | Out-Null
}
$vinaExe = Join-Path $vinaDir 'vina.exe'
if (-not (Test-Path $vinaExe)) {
    Write-Host "Downloading Vina..."
    # The URL changes; current known-good: https://github.com/ccsdysb/vina/releases
    # Keep a pinned version in source control (see LICENSE-vina.txt)
    Invoke-WebRequest -Uri 'https://github.com/ccsdysb/vina/releases/download/v1.2.5/vina_1.2.5_windows.exe' -OutFile $vinaExe
    Write-Host "Vina downloaded: $vinaExe"
} else {
    Write-Host "Vina already present: $vinaExe"
}

# --- xTB (GPL/LGPL, grimme-lab) ---
$xtbDir = Join-Path $toolsDir 'xtb\xtb-6.7.1\bin'
if (-not (Test-Path $xtbDir)) {
    New-Item -ItemType Directory -Force -Path $xtbDir | Out-Null
}
$xtbExe = Join-Path $xtbDir 'xtb.exe'
if (-not (Test-Path $xtbExe)) {
    Write-Host "Downloading xTB..."
    Invoke-WebRequest -Uri 'https://github.com/grimme-lab/xtb/releases/download/v6.7.1/xtb-6.7.1-windows.zip' -OutFile "$xtbDir\xtb.zip"
    Expand-Archive -Path "$xtbDir\xtb.zip" -DestinationPath (Join-Path $toolsDir 'xtb') -Force
    Remove-Item "$xtbDir\xtb.zip"
    Write-Host "xTB extracted: $xtbExe"
} else {
    Write-Host "xTB already present: $xtbExe"
}

Write-Host ""
Write-Host "Binaries ready. Now: scripts\run_5targets_2500.ps1"
```

---

## 9. `scripts/run_5targets_2500.ps1` — ports fixes

Cambios needed sobre el script actual (7578 bytes):

1. Reemplazar `C:\Python314\python.exe` con detección automática:
   ```powershell
   $py = if ($env:PYTHON) { $env:PYTHON } elseif (Get-Command python -ErrorAction SilentlyContinue) { (Get-Command python).Source } else { 'python' }
   ```

2. Reemplazar paths absolutos `D:\moldesign-build\...` con `$PSScriptRoot\..`:
   ```powershell
   $repo = Split-Path -Parent $PSScriptRoot
   Set-Location $repo
   ```

3. Deteksi missing binaries y sugerir `download_binaries.ps1`:
   ```powershell
   if (-not (Test-Path "$repo\tools\vina\vina.exe")) {
       Write-Error "Missing Vina. Run scripts\download_binaries.ps1 first."
       exit 1
   }
   ```

4. Mensaje final claro con ruta del log:
   ```powershell
   Write-Host "Done. Reports: $repo\data\gnn_fixed\ef_report_*_gs.json"
   ```

El resto del flow (5 targets, --focused-box para 5HT1A, re-score-gnn, ablation)
se mantiene. Solo se cambia la portabilidad.

---

## 10. Métricas de aceptación Fase 2 (definition of done)

- [ ] Root `README.md` con quickstart reproducible en <1 hr wallclock.
- [ ] Root `LICENSE` (AGPL-3.0) y `LICENSE-MODELS` (MolDesign Model License v1.1, source-available).
- [ ] `CONTRIBUTING.md` con setup dev + commit style + PR checklist.
- [ ] `.github/workflows/ci.yml` corriendo `pytest` en push/PR.
- [ ] `.github/ISSUE_TEMPLATE/` con bug_report + feature_request.
- [ ] `.github/PULL_REQUEST_TEMPLATE.md`.
- [ ] `scripts/download_binaries.ps1` que descarga Vina + xTB.
- [ ] `scripts/run_5targets_2500.ps1` sin paths hardcodeados (corre desde cualquier clone).
- [ ] CI badge verde en `main`.
- [ ] Cualquiera puede `git clone ... && cd moldesign-build && scripts\download_binaries.ps1 && scripts\run_5targets_2500.ps1` y reproducir la tabla del paper en <10 hr wallclock.

---

## 11. Out-of-scope para Fase 2 (declarado)

- **Frontend**: post-Fase 4 paper draft. El dashboard Tauri está roto (`frontend/src/app/` vacío), postpuesto.
- **EULA del `.exe`**: Fase 3 (legal HD). Requiere asesoría externa.
- **NSIS installer**: Fase 5 (post-frontend).
- **GitHub Release public**: Fase 6 (post-paper).
- **Scripts de scopo científico nuevo** (Bucket C, EquiBind): track separado.

---

## 12. Tiempo estimado

- **Set-up**: 1 sesión (escritura de los 8 archivos faltantes).
- **CI dry-run**: 1 sesión (debugar workflow en GitHub Actions, ajustar deps).
- **Total Fase 2**: 1-2 sesiones (sin cómputo pesado).

El blocker más fuerte es el `LICENSE` (legal verify) y los binarios (`download_binaries.ps1` URLs oficiales). Con esos resueltos, el resto es escritura directa.

---

## 13. Decisión pendiente del usuario

Antes de abrir el repo público:

- [ ] Handle GitHub (`@<user>` o `@moldesign-org` ?).
- [ ] Repo name (`moldesign-build` vs `moldesign` vs `moldesign-v1`).
- [ ] Default branch (`main` confirmado).
- [ ] Owner del copyright en LICENSE (`Copyright (c) 2026 <name>`).
- [ ] Email de contacto para commercial licensing inquiries.

Cuando el usuario defina estos, los templates con `<...>` placeholders se
rellenan.

---

*Documento generado en la sesión 2026-07-25 (stopping point). Las plantillas
sugeridas en Secciones 1-9 son para copiar a archivos durante la sesión
proper de Fase 2.*
