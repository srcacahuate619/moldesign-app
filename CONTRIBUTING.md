# Contribuir a MolDesign (y auditarlo)

Esta guía sirve para dos cosas: que alguien que no conoce el proyecto pueda
**reproducirlo desde un fork** —pruebas, puertas, experimentos sellados y el
instalador— y que pueda **contribuir** sin romper lo que el proyecto promete.
Lo que MolDesign es y lo que no es está en [`AGENTS.md`](AGENTS.md); las reglas
que vienen de fallos reales, en su sección «Restricciones que no debes romper».

> *English summary.* Windows 10/11 x64. Python 3.11 and Node 24.20 (`.nvmrc`).
> Install `backend/requirements-embed.lock.txt` + `backend/requirements-test.txt`,
> run the commands in §2 (they are exactly what CI runs), then `npm ci` and the
> frontend checks. `python scripts/validar_sellos.py --check` verifies every sealed
> experiment from a clean clone. Full installer build: §3. Contributions need the
> CLA (§6).

## 1. Plataforma

| Qué | Dónde se ha comprobado |
|---|---|
| Pruebas de backend, rescoring y scripts; puertas de CI; sellos | Windows 11 x64, Python 3.11 (CI: `windows-latest`) |
| Frontend (`npm ci`, `typecheck`, `test:run`) | Windows 11 x64, Node 24.20.0, npm 11.19.0 |
| Instalador (`npm run tauri:build`) | Windows 11 x64 con Rust estable y MSVC Build Tools |
| Linux y macOS | **No comprobado.** El producto es una aplicación de escritorio de Windows. |

Git para Windows con su configuración por defecto (`core.autocrlf=true`) es
válido: los ficheros cuyos bytes están sellados llevan `-text` en
`.gitattributes` y git no los reescribe.

## 2. Verificación rápida: lo mismo que la CI

Desde un clon del fork, sin aprovisionar nada más. El entorno es la lista
**exacta** del intérprete que se distribuye, no una aproximación:

    py -3.11 -m venv .venv
    .venv\Scripts\activate
    python -m pip install -r backend/requirements-embed.lock.txt
    python -m pip install -r backend/requirements-test.txt

Backend y rescoring (`.github/workflows/ci.yml`, jobs `backend` y `rescoring`):

    cd backend
    python -m ruff check api core db services --select E9,F63,F7,F82
    python -m pytest tests -ra -p no:cacheprovider
    python -m pytest ../scripts/tests -ra -p no:cacheprovider
    python ../scripts/report_test_counts.py --check
    python ../scripts/generate_openapi_contract.py --check
    python ../scripts/check_docs_links.py --check
    python ../scripts/validar_sellos.py --check
    python ../scripts/generate_runtime_inventory.py --check
    python ../scripts/check_stacking_weights_ui.py --check
    python ../scripts/check_release_pipeline.py
    python ../scripts/check_openbabel_boundary.py
    python ../scripts/check_model_license_boundary.py --check
    python ../scripts/lock_embedded_runtime.py --check --permitir-runtime-ausente
    python ../scripts/generate_sbom.py --check --permitir-runtime-ausente
    cd ..
    python rescoring/scripts/generate_model_manifest.py --check
    python -m pytest rescoring/tests -ra -p no:cacheprovider
    python rescoring/scripts/check_vina_importance_gate.py
    python scripts/smoke_test_desktop.py

Frontend y Rust (jobs `frontend` y `tauri`):

    cd frontend
    npm ci
    npm run check:csp
    npm run typecheck
    npm run test:run
    cd src-tauri
    cargo fmt --check
    cargo clippy --all-targets -- -D warnings
    cargo test --all-targets

Las pruebas que necesitan binarios del runtime (Vina, Open Babel, xTB) o
checkpoints no distribuidos **se omiten diciéndolo**, con el motivo en la salida
de `pytest -ra`; no pasan en falso. Para ejecutarlas, aprovisiona el runtime (§3).

## 3. Aprovisionar el runtime y construir el instalador

`git clone` no trae el intérprete embebido, los motores nativos ni la base
sembrada: son unos 2,2 GB que se descargan de un archivo fijado por revisión y
SHA-256. Primero, qué falta (no escribe nada y no necesita red):

    python scripts/bootstrap_dev_tree.py --check

Después, aprovisionar (verifica el archivo antes de extraer y nunca escribe
sobre ficheros versionados):

    python scripts/bootstrap_dev_tree.py --fetch

El archivo se puede reconstruir desde el repositorio y comparar con el publicado:
`python scripts/build_base_archive.py --check`. Con el árbol aprovisionado:

    cd frontend
    npm ci
    npm run tauri:build

`tauri:build` encadena las puertas de `beforeBuildCommand`
(`frontend/src-tauri/tauri.conf.json`); están descritas en `AGENTS.md`, sección
«Construir». Si se cambia algo de empaquetado, CSP o estilos, ejecuta además
`npm run smoke:prod`.

Los pesos propios que usa el producto (clasificador XGBoost, `model_a_*`,
CL-GNN `gnn_v2_cl_best.pt`) **vienen con el clon**, en `rescoring/artifacts/`,
bajo [`LICENSE-MODELS`](LICENSE-MODELS). `generate_model_manifest.py --check`
comprueba sus hashes.

## 4. Reproducir la ciencia

Cada experimento vive en `scripts/artifacts_science/<ID>/`: `manifest.json`
(hipótesis, protocolo, gate, entorno, hashes, decisión y su razón),
`metrics.json`, `per_complex.jsonl`, `failures.jsonl` y `logs/`. El relato de
cada hallazgo o refutación está en `docs/papers/<ID>.md` y en la pestaña Ciencia
de la aplicación.

- **Comprobar que nada cambió desde el sello:**
  `python scripts/validar_sellos.py --check` (añade `--detalle` para ver cada
  fichero). Un hash distinto es un fallo. Un fichero ausente sólo se acepta si
  está declarado en [`scripts/sellos_no_distribuidos.json`](scripts/sellos_no_distribuidos.json),
  con el motivo y cómo conseguirlo.
- **Lo que no viaja:** PDBBind v2020, cuya licencia no permite redistribuirlo;
  quien quiera repetir un experimento que lo use tiene que obtenerlo con su
  licencia y extraerlo en `data/pdbbind/`. Los hashes sellados permiten
  comprobar que es la misma copia. El runtime (§3) y algunos datasets derivados
  de PDBBind están en la misma tabla.
- **Repetir un experimento:** el campo `protocol` del manifiesto nombra el
  script y sus parámetros. Los resultados se escriben en un directorio nuevo
  —nunca encima del artefacto sellado—, y se comparan con él.
- **Referencia externa del auditor:** `FEP-08-CONTROL-POSITIVO` aplica las
  auditorías FEP al protein-ligand-benchmark de OpenFF (datos CC BY 4.0), que
  cualquiera puede descargar.

## 5. Reglas del proyecto que afectan a una contribución

- No se edita nada dentro de `scripts/artifacts_science/`: son artefactos
  sellados. Un activo sellado que cambia se registra con
  `python scripts/experiment_manifest.py maintain`, que conserva el hash
  anterior y exige un motivo y un commit.
- Un experimento se prerregistra (`experiment_manifest.py init`) **antes** de
  medir, con su gate; el gate no cambia después de ver los datos.
- Una prueba de empaquetado mira el artefacto (`out/`, el bundle), no el código.
- Un guardián de `frontend/scripts/` o `scripts/` lleva autotest: muestras que
  debe detectar y muestras que no.
- Nada de `except Exception` silencioso: si se captura, se registra y se declara.
- No se importan `openbabel`, `pybel` ni `_openbabel` desde `backend/` o
  `rescoring/` (`docs/79_ADR_FRONTERA_OPEN_BABEL.md`).

## 6. Commits, pull requests y CLA

- **Conventional Commits** (`feat(ámbito): …`, `fix`, `docs`, `test`,
  `science`, `ci`, `chore`). El mensaje explica el porqué, con la medida si la
  hay.
- **CLA obligatorio antes de integrar la primera contribución**: una línea en
  [`CONTRIBUTORS.md`](CONTRIBUTORS.md) y el trailer `MolDesign-CLA: accepted v1.0`
  en el commit (ver [`CLA.md`](CLA.md)). Conservas el copyright; el CLA concede
  al proyecto una licencia amplia, incluido el derecho a distribuir con otras
  condiciones en el futuro.
- **Coautoría:** el historial declara con `Co-Authored-By` la asistencia de IA
  usada en el desarrollo. Si la usas, decláralo igual.
- **Checklist de la PR:**
  - [ ] Pruebas nuevas o actualizadas para el comportamiento que cambia.
  - [ ] Los comandos de §2 que afectan a lo que tocas pasan en local.
  - [ ] `python scripts/validar_sellos.py --check` pasa.
  - [ ] Sin secretos, claves ni correos personales en el diff.
  - [ ] `docs/` actualizado si cambia un comportamiento o una cifra.

## 7. Licencias

Código: **PolyForm Noncommercial 1.0.0** ([`LICENSE`](LICENSE)); modelos
propios: [`LICENSE-MODELS`](LICENSE-MODELS). Es *source-available*, no código
abierto según la OSI: el uso comercial requiere una licencia aparte
([`COMMERCIAL-LICENSE.md`](COMMERCIAL-LICENSE.md)). Las dependencias con copyleft
del runtime distribuido están declaradas en `AGENTS.md` («Licencia») y en el SBOM
(`scripts/generate_sbom.py`). Si tu contribución trae código o datos de terceros,
dilo en la PR con su licencia.

## 8. Issues

Etiquetas útiles: `bug`, `reproducibility` (algo de §2-§4 no se reproduce en tu
máquina: adjunta la salida), `silent-fail` (un fallo que el producto no
declara), `science` (una cifra o una afirmación que no puedes rastrear hasta una
medida: en este proyecto eso es un defecto).
