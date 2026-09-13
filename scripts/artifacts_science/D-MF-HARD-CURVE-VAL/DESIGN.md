# D-MF-HARD-CURVE-VAL — Validacion unica de val con K=15 — DESIGN

**Fecha:** 2026-08-16
**Rama:** experimentos/ruta-c-molflex
**Referencia:** sello train D-MF-HARD-CURVE (commit f31bfeb, K=15 GO) +
FORECAST.md. **NO sellado, NO finish.**

## 1. Alcance y autorizacion

- Autorizacion del maintainer: SOLO K=15 (15 conformeros, NO 30), SOLO los
  5 hard + 5 controles de val del cohort D-MF-HARD sellado, config identica
  al train sellado (seed ETKDG=42, --seed 42 Vina, box 25 A, exh=8,
  num_modes_requested=9, vina 1.2.7, cpu=1, 6 workers, sin relax, gate
  enmendado), reporte descriptivo.
- **K NO cambia y K30 NO se abre pase lo que pase.** K=15 quedo fijado por la
  regla corregida sobre train ANTES de tocar val; esta corrida es
  verificacion piloto descriptiva (n=5 sin potencia, D-MF-HARD DESIGN §5).

## 2. Implementacion

- Runner: scripts/run_molflex_curve_val.py — REUSA las funciones del runner
  train SIN tocar el archivo sellado (scripts/run_molflex_curve.py es asset
  del sello f31bfeb con hash 46fd2d35...): importa el modulo y monkeypatchea
  (constantes N_CONF=15/PREFIJOS=[15]/WORK/ARTIFACTS/EXPERIMENT_ID +
  wrappers de las funciones con strings train-hardcodeados: file_stem
  curve30 -> curve15, split train -> val). El gate corregido
  (parse_vina_output), el docking por conformero (dock_rigido_archivo via
  _dock_worker/_dock_writemaps) y el flujo de lotes con resume se reusan sin
  modificacion.
- WORK dir: data/dmfhard_curve_work/val/ (dentro del work dir train ya
  gitignored; .gitignore NO modificado).
- El ensemble de 15 es el prefijo exacto del ensemble de 30 (propiedad
  verificada en FORECAST/prefix_smoke.json).
- Consolidacion val PROPIA (sin regla de decision, sin bootstrap decisorio):
  cobertura n/5 por estrato con Wilson CI 95% (descriptivo), mediana
  min-RMSD, ITT, tiempos P50/P90, degeneracion por yield.

## 3. Resultados

- Poses val: 949; fallos ITT: 0.
- Hard (n=5): cobertura 2/5, mediana
  min-RMSD 2.912.
- Control (n=5): cobertura 4/5, mediana
  min-RMSD 1.367.
- Detalle: metrics.json.

## 4. Declaraciones

- **K permanece 15.** Ningun numero de esta corrida cambia K ni abre K30.
- n=5 por estrato: SIN inferencia fuerte contra train (solo descripcion).

## 5. Archivos

| Archivo | Contenido |
|---|---|
| curve_poses_val.jsonl | una linea por pose emitida (identidades val|pid|molflex|curve15_...) |
| curve_provenance.jsonl | sidecar FND-06 canonico por corrida |
| curve_candidates_val.jsonl | bloques PDBQT crudos por pose emitida |
| metrics.json | metricas descriptivas por estrato + Wilson CI |
| per_complex.jsonl | una linea por complejo val |
| failures.jsonl | fallos ITT |
| deviations.jsonl | esperado vacio (gate corregido desde el inicio) |
