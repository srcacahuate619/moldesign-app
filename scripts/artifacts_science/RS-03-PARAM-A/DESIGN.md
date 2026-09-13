# RS-03-PARAM-A — Parametrización OpenFF Sage + NAGL nativo (116 ligandos train)

## Contexto

- **Prerregistro**: RS-03-PARAM-A-PRE sellado GO (`147abb1`), que refina el PRE maestro RS-03-PARAM-PRE sellado (`7dfa3b8`, IT1 QA-2).
- **Hipótesis**: la parametrización OpenFF Sage 2.2.1 + NAGL `openff-gnn-am1bcc-1.0.0.pt` (producción) sobre los 116 ligandos train es una base física correcta (cobertura, determinismo, conservación de carga, cero fallback silencioso) que reemplaza el tipado heurístico de `molchamb_v2.py:65`.

## Protocolo ejecutado

- **Cohorte**: 116 ligandos train (lista canónica `data/pose_selector_dataset/poses_train.jsonl`, assert n=116). Cero val40/test/D-RC-CONFIRM.
- **Entorno**: contenedor Ubuntu `moldesign-science:latest` en `192.168.1.64` (cliente `scripts/moldesign_client.py` / `remote_docker_runner.py`); openff-toolkit 0.18.0, openff-nagl 0.5.5, openff-nagl-models 2025.9.0, openff-interchange 0.5.2, RDKit 2026.03.1, OpenMM 8.5.2, Python 3.11.
- **Runner**: `scripts/run_rs03_param_a.py` (dual-mode: Windows delega al contenedor; `--inside-container` ejecuta la química).
- **Assets**: SDF por ligando `data/pdbbind/{pid}/{pid}_ligand.sdf` (sha256 registrado por ligando en per_complex), RDKit `SDMolSupplier(removeHs=False, sanitize=True)` para sanitización, NAGL congelado.
- **Fuerza/cargas**: Sage `openff-2.2.1.offxml` (primario), modelo NAGL `openff-gnn-am1bcc-1.0.0.pt` SHA-256 `7981e7f5b0b1e424c9e10a40d9e7606d96dcd3dd2b095cb4eeff6829f92238ee` (NO RC).
- **Chequeos por ligando**: carga formal del ligando sanitizado; Σq normalizada a la carga formal (delta_q_e); mapeo heavy-atom biyectivo + `atom_order_hash`; energía finita + sistema serializable; clasificación de fallos por química.
- **Determinismo**: dos ejecuciones en el contenedor; diferencia máxima de carga registrada.
- **Transferencia**: SDF ida/vuelta al workspace del contenedor (`/home/srcacahuate619/moldesign-env`), resultados descargados; transferencia binaria sin normalización EOL para preservar SHA-256 reproducibles Windows/Ubuntu.

## Resultados

- **decision: GO** · duración 379.5 s · n_total 116, n_passed 116, n_failed 0.
- **global_coverage: 1.0** (≥0.95 requerido).
- **max_charge_drift_e: 2.7755575615628914e-17** (≤1×10⁻⁶ requerido; determinismo excelente).
- **Los 11 gates G1–G11: true**:
  - G1 modelo NAGL 1.0.0 congelado con SHA-256 registrado ✓
  - G2 cero descargas de modelos durante ejecución ✓
  - G3 carga formal derivada del ligando sanitizado ✓
  - G4 |Σq − formal| ≤ 1×10⁻⁴ e (máx delta_q_e ~1e−15) ✓
  - G5 mapeo atómico biyectivo + atom_order_hash ✓
  - G6 cero fallback silencioso ✓
  - G7 cobertura global ≥95% (100%) ✓
  - G8 cobertura ≥90% por estrato (100% en todos) ✓
  - G9 energía finita + serializable 100% ✓
  - G10 determinismo ≤1×10⁻⁶ e (2.78e−17) ✓
  - G11 fallos clasificados por química (0 fallos) ✓
- **Estratos (cobertura 100% en todos)**: neutral 86/86, ionized 30/30, halogenated 18/18, sulfur_phosphorus 46/46, MW bajo (<300) 41/41, medio (300–500) 56/56, alto (>500) 19/19, rotatable bajo (<5) 37/37, medio (5–10) 41/41, alto (>10) 38/38, drug_like 81/81.

## Conclusión

La base física NAGL nativa (Sage 2.2.1 + `openff-gnn-am1bcc-1.0.0`) parametriza los 116 ligandos train con cobertura 100%, determinismo 2.78e−17 y cero fallos. **RS-03-PARAM-A cumple su gate.**

Esto reemplaza el tipado heurístico de `molchamb_v2.py:65` como fundamento de cargas para el futuro RS-03. El siguiente paso es **RS-03-PARAM-B** (referencia AM1-BCC estratificada; no selector; prohibido seleccionar NAGL por RMSD ni Top-1), tras lo cual **RS-03-PARAM** agrega A+B.

Nota de gobernanza: RS-03-PARAM-A no reclama mejora científica (es QC de base física). El claim de "rescoring MM/GBSA-like" solo se evalúa en RS-03 con la cascada v0.6 → margin-only → MM/GBSA-like, tras completar B.

## Archivos

- `scripts/run_rs03_param_a.py` — runner dual-mode (Windows↔contenedor).
- `scripts/remote_docker_runner.py` — helper de ejecución remota (usado por el runner).
- `metrics.json` — decisión GO, gates G1–G11, estratos, determinismo, modelo/fuerza.
- `per_complex.jsonl` (116) — por ligando: sdf_sha256, n_atoms/heavy, mw, rotatable_bonds, formal_charge, charge_sum_raw/normalized, delta_q_e, atom_order_hash, charges (por átomo), strata.
- `failures.jsonl` — vacío (0 fallos).
- `manifest.json` — RS-03-PARAM-A (init 42; a sellar con runner + resultados + DESIGN).