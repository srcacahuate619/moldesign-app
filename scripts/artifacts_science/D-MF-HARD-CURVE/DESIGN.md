# D-MF-HARD-CURVE — Curva MolFlex 5/15/30 (entregable 7) — DESIGN

**Fecha:** 2026-08-16
**Rama:** experimentos/ruta-c-molflex
**Referencia:** docs/49 §15 entregable 7 (MF-02) + FORECAST.md (preregistro) +
D-MF-HARD/DESIGN.md (cohorte sellada). **NO sellado, NO finish** (instruccion
del maintainer: entregable ejecutado y documentado, sellado diferido).

## 1. Protocolo ejecutado

- Curva anidada: 30 conformeros ETKDG UNA vez por complejo (seed 42,
  pruneRmsThresh 0.4), docks por conformero (1 invocacion Vina = 9 modos).
  Prefijos {0..4} = K5, {0..14} = K15, {0..29} = K30 (anidamiento
  byte-idempotente verificado en FORECAST/prefix_smoke.json).
- Config: seed ETKDG=42, --seed 42 explicito en TODAS las invocaciones de
  Vina (SEMILLA_VINA de molflex.py, preregistro FND-06), box 25 A centrado en
  ligando cristalografico, exh=8, 9 modos, CPU=1 por Vina, 6 workers,
  Vina 1.2.7, timeout 240 s/dock, sin relax.
- Alcance: SOLO train (17 hard + 17 controles). Los 10 pids de val NO se
  dockearon ni evaluaron (cero val tocado; guardia dura en el runner +
  verificacion final).
- Generacion reusada de scripts/molflex.py (construir_ensemble,
  preparar_complejo, dock_rigido_archivo): cero reimplementacion manual de
  la config. La unica transformacion es el RENOMBRADO de la salida a
  curve30_conf{cid}.out.pdbqt (identidad de la curva; colision con
  historicos verificada = 0 en FND-06 y MF-01-UNION).

## 2. Decisiones de implementacion

- Identidad canonica por pose: train|pid|molflex|curve30_conf{cid}.out|model_idx
  — model_idx SOLO sobre modelos REALMENTE emitidos (gate corregido: Vina
  1.2.7 puede emitir 1..9 modelos por clustering de poses de salida; si
  emite 4, existen 4 identidades, nada de model_idx fantasma).
- GATE CORREGIDO (enmienda auditada 2026-08-16): validez = rc=0 + archivo no
  vacio + 1 <= n_models_emitted <= 9 + todos los modelos con score FINITO de
  REMARK VINA RESULT + geometria parseable. Scores EXCLUSIVAMENTE del
  archivo (nunca de la tabla stdout, que puede listar mas modos que el
  archivo). Por corrida: num_modes_requested=9 + n_models_emitted (en
  provenance.json y curve_provenance.jsonl).
- Resume idempotente por identidad: salida valida bajo el gate corregido ->
  salta; fallo -> ITT registrado en failures.jsonl, NO reintentado (reintento
  manual unico via --retry PID: retry TECNICO documentado en
  retry_log.jsonl / technical_retries.jsonl, contado en metrics; si pasa no
  cuenta como fracaso cientifico).
- Desviaciones: los falsos fallos del gate anterior del pilot
  (mode_count_mismatch, hoy validos) se reclasifican a deviations.jsonl
  FUERA del ITT, recuperando sus tiempos medidos.
- Mapas de grid transient (FORECAST §3.6): primer dock escribe mapas
  (--write_maps + --force_even_voxels, ES el dock del conf 0); el resto
  reutiliza (--maps); se borran al completar el complejo. Resume parcial sin
  mapas -> docks fresh (misma config nominal).
- Lotes con resume: --wall-budget 300 s por invocacion bash (<=10 min),
  progress.json con completados/pendientes/fallos entre lotes.
- DETENCION (enmienda 7) -> STOP.json + reporte, sin continuar: cero modelos
  emitidos, >9 modelos, score/geometria invalidos, provenance incorrecto
  (14 campos/semillas/experiment_id/file_stem), o fallos SISTEMATICOS
  (todos los conformeros de un complejo fallan con el mismo motivo, o el
  mismo motivo en >=3 complejos).
- Consolidacion separada del docking (--consolidate): los artefactos finales
  se reconstruyen desde el work dir; el docking nunca escribe en
  scripts/artifacts_science.

## 3. Metrica de pose y caveats

- rmsd_pose_pocket (molflex.py) sobre los modelos EMITIDOS de cada dock
  contra el ligando cristalografico data/pdbbind/{pid}/{pid}_ligand.sdf:
  compara coordenadas 1:1 EN EL MARCO DEL POCKET (sin alineamiento; el
  receptor es fijo). Caveat documentado: traslacion/rotacion de la pose no
  se compensan (esa es la intencion — mide si la pose esta en el sitio
  bioactivo, no solo si su geometria interna coincide). GetBestRMS queda
  excluido de esta metrica.
- Degeneracion por yield: controles poco flexibles rinden <30 confs (pruning
  RMSD 0.4); los prefijos 15/30 degeneran al ensemble completo. Documentado
  por complejo en per_complex.jsonl (n_conf_5/15/30 reales).
- Grid del dock que escribe mapas usa voxels pares (span 25.5 vs 25.125 A),
  side effect documentado en molflex.py (fix E2); el resto del complejo
  reutiliza ese grid. Config nominal box 25 identica en todos.
- Bootstrap BCa (n=2000, seed 42) es INFORMATIVO: no decide (FORECAST §6).

## 4. Resultados

- Poses train consolidadas: 4329; fallos ITT: 0.
- Regla de decision corregida (FORECAST.md, preregistrada): el menor
  K en {5,15} que frente a 30 en train pierda <=1/17 hard cubiertos, degrade
  la mediana min-RMSD hard <=0.1 A, no pierda >1 control cubierto ni degrade
  su mediana >0.1 A; si ninguno cumple -> 30.
- **K ELEGIDO: 15**
- Numeros de soporte:
- K5: hard cubiertos 1/4 (pierde 3), mediana 5.278 vs 4.011 (deg 1.267); control cubiertos 14/15 (pierde 1), mediana 1.08 vs 1.041 (deg 0.039)
- K15: hard cubiertos 3/4 (pierde 1), mediana 4.024 vs 4.011 (deg 0.013); control cubiertos 15/15 (pierde 0), mediana 1.041 vs 1.041 (deg 0.000)
- Metricas completas: metrics.json (incluye gate: desviaciones y retries
  tecnicos, distribucion de n_models_emitted).

### 4.1 CAVEAT DE NO-SATURACION (correccion previa al sello, autorizada)

- **NO se declara saturacion completa.** K30 mejoro varios hard: 1aaq
  (6.855 -> 3.484), 1b46 (1.449 -> 1.134), 1hmr (5.730 -> 4.353), 1jn4
  (5.278 -> 4.058), 1njs (7.360 -> 2.043) y AÑADIO 1b2h como cuarto
  complejo cubierto (min-RMSD 1.706 a K30, no cubierto a K15). K15 es la
  politica COSTO/COBERTURA elegida por la regla corregida, NO equivalencia
  cientifica con K30.
- **Cobertura hard sigue siendo NO_GO: 3/17 (17.6%) a K15.** La cohorte
  D-MF-HARD es por construccion el estrato dificil (rot>=15); este resultado
  no rehabilita MolFlex en D-MF-HARD. El scope de K15 es validacion piloto.
- **Distincion mediana vs media en la ganancia pareada 15->30:** la MEDIANA
  pareada de delta min-RMSD es 0.000 A (la mayoria de los complejos no
  cambia); la MEDIA pareada es -0.289 A, impulsada por mejoras concentradas
  en unos pocos hard (listados arriba). Ambas estan en metrics.json
  (ganancias_pareadas.15_30: delta_mediana y delta_media); ninguna decide
  (bootstrap informativo).

## 5. Provenance Git de esta carpeta

Cadena de commits (rama experimentos/ruta-c-molflex):

| Commit | Contenido |
|---|---|
| `c30701b` | docs: regla de decision corregida (FORECAST) |
| `47f9efd` | CODIGO de ejecucion: gate enmendado (REMARK-only, emitted-only, desviaciones, retries tecnicos) + 11 tests |
| `6a208e0` | CONSOLIDACION/RESULTADOS: curva 5/15/30 train completada (689 docks, 0 ITT, K=15) |

`manifest.json` apunta a `git_state.commit = 6a208e0a5ae8beefb058540d5555f48332226221`
(el commit que contiene codigo final + resultados; c30701b y 47f9efd son sus
ancestros directos).

## 6. Archivos

| Archivo | Contenido |
|---|---|
| curve_poses_train.jsonl | una linea por pose (solo modelos emitidos), train |
| curve_provenance.jsonl | sidecar FND-06 canonico (14 campos + num_modes_requested/n_models_emitted) por corrida |
| curve_candidates_train.jsonl | artefacto candidato: geometrias PDBQT crudas por pose emitida (4329) |
| policy.json | politica fijada K=15 + regla + config + hashes sha256 de train |
| metrics.json | cobertura/medianas/tiempos/fallos/ganancias/decision/gate/caveats |
| per_complex.jsonl | una linea por complejo con prefijos y degeneracion |
| failures.jsonl | fallos ITT (sin reintentos; reclasificados fuera) |
| deviations.jsonl | falsos fallos del gate anterior del pilot (fuera de ITT) |
| technical_retries.jsonl | retries tecnicos documentados |
| FORECAST.md / prefix_smoke.json | preregistro y smoke de prefijo (previos) |
