# Reubicaciones de archivos (2026-10-10 y 2026-10-11)

Registro de lo que se movió, borró o retiró para liberar espacio en D:. Los documentos del repositorio citan la ruta nueva en línea (`ahora: …`). Esta tabla es la referencia completa.

**Regla:** los logs, las medidas en JSON y las evidencias selladas **no se reescriben**. Si citan una ruta antigua, aquí está la nueva.

Espacio libre: D: pasó de 29,6 GB a 77,2 GB. F: pasó de 41,1 GB a 24,4 GB.

## 1. Movido a F: (`F:\Backups\moldesign-evidencia\`)

Todos los movimientos son robocopy `/MOVE` con recuento y bytes verificados.

| Origen (D:) | Destino (F:) | Tamaño | Notas |
|---|---|---|---|
| `moldesign-egfr-archive\` | `moldesign-evidencia\moldesign-egfr-archive\` | 6,05 GB | 40.737 ficheros. Campaña EGFR retirada del repo el 2026-10-01 |
| `moldesign-dev-data\molchat-lab\` | `2026-10-10-limpieza-D\dev-data\molchat-lab\` | 4,94 GB | 36.822 ficheros: pesos descargados con `procedencia.json`, MolScribe y su venv |
| `moldesign-qa\molcy-datos\` | `2026-10-10-limpieza-D\qa\molcy-datos\` | 1,16 GB | Blender 5.2.2 portátil con Molecular Nodes (software de terceros) |
| `moldesign-audits\frontend\` (sin `clon\`) | `2026-10-10-limpieza-D\audits\frontend\` | 0,9 MB | Informes de la auditoría de frontend de 2026-09-23, medidas JSON y sondas `.mjs` |
| `moldesign-build\dist\installers-anteriores\` | `2026-10-10-limpieza-D\dist\installers-anteriores\` | 0,6 GB | Instaladores archivados |
| `moldesign-build\dist\molcy-*` (11 carpetas) | `2026-10-10-limpieza-D\dist\molcy-*\` | ~1,45 GB | Vídeos, actas y salidas de QA de Molcy |
| `moldesign-build\tmp\{evaluation,batch,moldex,molchat}-runtime-*` anteriores a 2026-10-01, y `english-diagnosis-*` (35 carpetas) | `2026-10-10-limpieza-D\tmp\` | ~1,8 GB | Evidencia de puertas de los gates |
| Evidencia suelta de los worktrees retirados (`.tmp*`, `data\`, logs) | `2026-10-10-limpieza-D\worktrees\<nombre>\` | ~1 GB | Incluye `molgraph_seed.db`, del mismo tamaño que la copia de la rama principal |
| `moldesign-ci\sol-1-0-2\frontend\bundle-evidence.log` | `2026-10-10-limpieza-D\clones\sol-1-0-2\` | pequeño | Evidencia de empaquetado del clon |
| Cambios sin commitear de `moldesign-worktrees\clon-ci-frontend` | `2026-10-10-limpieza-D\clones\clon-ci-frontend\sin-commit.patch` | pequeño | Dos ficheros E2E; las mismas correcciones ya están en desarrollo |
| `tools\vina\vina_trace.exe` y su manifiesto en `cal-8hfi` y `receptores-propios` | `2026-10-10-limpieza-D\worktrees-binarios-historicos\` | pequeño | Versiones anteriores a las de la rama principal. Por si las usaron corridas selladas |

Dato técnico: `dist\molcy-mesa-20261007` tenía tres junctions a `E:\` (Blender). Se quitaron con `rmdir`, sin `/s`. `E:\` quedó intacto.

## 2. Borrado (regenerable o redundante)

| Elemento | Motivo | Qué queda |
|---|---|---|
| `frontend\src-tauri\target\debug` (11,1 GiB) | `cargo clean --profile dev` | `target\release` (necesario para recompilar rápido) |
| `frontend\.next`, `.next-dev`, `.next-molcy-verify` (~2,2 GB) | Caché de Next | Se regenera al compilar |
| `MagicMock\` en la raíz | Carpetas creadas por mocks de tests, sin versionar | Nada |
| `moldesign-worktrees\clon-ci-target` (4,9 GB) | Caché de compilación Rust de un clon de CI | Nada |
| `moldesign-audit\bundle-copy` (1,8 GB) | Copia del runtime; su código está en git | Se regenera con `stage:desktop` |
| `moldesign-ci\sol-1-0-2` (clon) | 0 commits fuera de desarrollo y 0 cambios | Commit `112a8476` en `codex/release-hygiene` |
| `moldesign-worktrees\clon-ci-frontend` (clon) | Todo está en desarrollo | Parche en `clones\clon-ci-frontend\` |
| `moldesign-audits\frontend\clon` (clon) | HEAD `c3415b6` está en desarrollo | Nada |

## 3. Worktrees retirados (las ramas se conservan)

Se retiraron con `git worktree remove --force` tras comprobar que no había modificaciones ni ficheros sin seguimiento. Los datos y ficheros ignorados valiosos ya estaban en F:.

| Worktree | Rama | Estado |
|---|---|---|
| `.worktrees\cal-8hfi` | `claude/cal-8hfi` | Integrada |
| `.worktrees\catalogo-demostracion` | `sol/cierre-qa` (con la rama `sol/catalogo-demostracion` para las entregas) | Integrada |
| `.worktrees\dossier-demo` | `claude/agents-1-0-2` | Integrada |
| `.worktrees\traduccion` | `codex/traduccion-entregable` | Integrada |
| `.worktrees\receptores-propios` | `claude/receptores-propios` | Integrada |
| `moldesign-worktrees\integ-qa-prueba` | Desacoplado en `6eef2ce9` | Integrada |
| `moldesign-worktrees\sandbox-agente1` | `qa/agente1-evaluacion` | Integrada |
| `moldesign-worktrees\sandbox-agente2` | `qa/agente2-resto` | Integrada |
| `moldesign-worktrees\sol-cierre-1-0-2` | `sol/cierre-1-0-2` | Integrada |
| `moldesign-worktrees\molcy` | `molcy/integracion-1.0.2` | Integrada |

Para leer el código de un worktree retirado: `git show <rama>:<ruta>`, o crear un worktree nuevo con `git worktree add <ruta> <rama>`.

## 4. Conservado sin tocar, a propósito

- **`scripts\artifacts_science\`** (artefactos sellados). `CAL-8HFI-01/entrada/PROTOCOLO_8HFI_BORRADOR.md` cita rutas de worktree y de `tmp/`. No se edita: cambiar bytes invalida el sello.
- **`docs\verificacion\`** (registros de verificación). Son logs y medidas tomados en su momento. Citan rutas antiguas, por ejemplo `D:/moldesign-ci/sol-1-0-2`. Se dejan como registro; esta tabla da la correspondencia.
- **`docs\versions\1.0.2_cambios.md`**. El registro se edita solo al commitear, por el protocolo del canal entre sesiones. Cita `D:\moldesign-audits\frontend\audit_frontend.md`, ahora en `F:\…\audits\frontend\audit_frontend.md`. Ese cambio queda pendiente para el próximo commit.
- **Vivos y no integrados:** `.worktrees\receptores-20261008` (rama `codex/receptores-curacion-20261008`) y `moldesign-worktrees\molchat-lab` (rama `claude/molchat-lab`). No se tocaron.

## 5. No localizado

- `tmp/evaluation-runtime-20260901T061702Z`, citado en `docs/61_PLAN_CIERRE_APP_ORQUESTACION_CLAUDE.md`. No está en D: ni en F:. Probablemente se purgó antes del archivo de 2026-09-28. No se ha podido recuperar.
