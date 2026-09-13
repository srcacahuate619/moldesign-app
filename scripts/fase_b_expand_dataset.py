"""
fase_b_expand_dataset.py — Orquestador de expansión de dataset Fase B.

Amplía el pool de entrenamiento del modelo de rescoring (Fase A: 865 complejos
cacheados, 537 en train, holdout congelado de 328) hacia varios miles de
complejos, reentrena y compara contra el baseline de Fase A
(docs/38_FASE_B_BASELINE.md).

CADENA REAL REUTILIZADA (nada se reimplementa):
  Etapa 1  → rescoring/scripts/enrich_index_bindingdb.py (BindingDB TSV, real)
  Etapa 2  → rescoring/scripts/redock_pdbbind.py (run_vina_redocking, real)
  Etapa 3  → rescoring/feature_extractor.py extract_single_complex (v4, real)
             + merge de features Vina al cache (mismo formato que feature_cache_v4)
  Etapa 4  → rescoring/data_splitter.py create_frozen_test_set /
             scaffold_split_cv / verify_scaffold_disjoint (real)
  Etapa 5  → rescoring/train_families.py (subprocess, NO se modifica)
  Etapa 6  → rescoring/evaluate_test_set.py (funciones importadas + reporte propio)

SEGURIDAD (safe-by-default):
  * Sin flags → no ejecuta nada; imprime ayuda.
  * --dry-run imprime todos los pasos/comandos SIN ejecutar nada pesado.
  * Las etapas solo corren con --stage N (1..6) o --all.
  * model_a_universal.json NUNCA se sobreescribe en etapas 1-6: el training
    escribe a artifacts/ (nombre fijo de train_families), luego este script
    renombra los nuevos a model_a_*_faseb.* y RESTAURA los de Fase A desde
    backup. Solo --promote (flag explícito) hace el swap final tras backup.
  * Cada etapa registra SHA-256 de sus inputs (INDEX, split_config,
    family_map, manifest) en data/pdbbind/faseb_logs/faseb_pipeline_log.json.

INVARIANTE CIENTÍFICO (documentado también en el runbook 39):
  * Los 328 IDs del holdout de Fase A NUNCA entran al pool de entrenamiento
    de Fase B: la Etapa 4 los fuerza dentro del NUEVO holdout congelado y
    verifica disjunción por scaffold (verify_scaffold_disjoint == 0
    violaciones) antes de escribir split_config_faseb.json.

USO:
  python scripts/fase_b_expand_dataset.py --dry-run
  python scripts/fase_b_expand_dataset.py --stage 1 --limit 300
  python scripts/fase_b_expand_dataset.py --all --limit 300 --max-workers 6
  python scripts/fase_b_expand_dataset.py --stage 6
  python scripts/fase_b_expand_dataset.py --promote   (swap final, explícito)

REQUISITOS EN RUNTIME (no se instalan aquí):
  httpx, rdkit, numpy, scipy, xgboost, joblib, AutoDock Vina (binario),
  OpenBabel (obabel, para redock).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# ──────────────────────────────────────────────────────────────────────────
# Rutas del proyecto (absolutas, independientes del CWD)
# ──────────────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESCORING_DIR = PROJECT_ROOT / "rescoring"
SCRIPTS_DIR = RESCORING_DIR / "scripts"
ARTIFACTS_DIR = RESCORING_DIR / "artifacts"
DATA_DIR = PROJECT_ROOT / "data" / "pdbbind"
CACHE_DIR = DATA_DIR / "feature_cache_v4"
VINA_CACHE = DATA_DIR / "vina_redock_cache"
VINA_WORK = DATA_DIR / "vina_redock_work"
INDEX_PATH = DATA_DIR / "INDEX_refined_data.2020"
LOG_DIR = DATA_DIR / "faseb_logs"
MANIFEST_PATH = DATA_DIR / "faseb_selection_manifest.json"
SPLIT_CURRENT = ARTIFACTS_DIR / "split_config.json"
SPLIT_FASEB = ARTIFACTS_DIR / "split_config_faseb.json"
FAMILY_MAP_CURRENT = ARTIFACTS_DIR / "family_map.json"
FAMILY_MAP_FASEB = ARTIFACTS_DIR / "family_map_faseb.json"
BASELINE_DOC = PROJECT_ROOT / "docs" / "38_FASE_B_BASELINE.md"
BINDINGDB_ZIP = DATA_DIR / "downloads" / "BindingDB_All_202604_tsv.zip"

# Nombres que produce train_families.py (fijos, no se puede cambiar)
FAMILY_NAMES = ["universal", "kinase", "protease", "gpcr",
                "nuclear_receptor", "soluble_enzyme"]

# Baseline Fase A (docs/38) — valores de comparación inmutables
BASELINE_HOLDOUT_SPEARMAN = 0.6094
BASELINE_HOLDOUT_CI_LO = 0.5282
BASELINE_HOLDOUT_CI_HI = 0.6791
BASELINE_N_HOLDOUT = 328

VINA_TO_PKI = 1.36  # pKi = -vina_best_score / 1.36 (delta-learning)


# ──────────────────────────────────────────────────────────────────────────
# Helpers de logging / hashing
# ──────────────────────────────────────────────────────────────────────────

def ts() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def banner(msg: str) -> None:
    print(f"\n{'=' * 74}\n  {msg}\n{'=' * 74}")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_dir_listing(directory: Path, pattern: str = "*.json") -> str:
    """Hash liviano del contenido de un directorio de JSONs (nombre+bytes).

    No se usa para el cache completo de 865 archivos (muy pesado); se usa
    solo para directorios pequeños (backups). Para el feature_cache se
    registra el CONTEO + hash del manifest en su lugar.
    """
    h = hashlib.sha256()
    for p in sorted(directory.glob(pattern)):
        h.update(p.name.encode())
        h.update(str(p.stat().st_size).encode())
    return h.hexdigest()


def load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def append_pipeline_log(entry: dict) -> None:
    """Acumula entradas de auditoría (hashes) en faseb_pipeline_log.json."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / "faseb_pipeline_log.json"
    try:
        log_data = load_json(log_path)
    except Exception:
        log_data = {"entries": []}
    entry["timestamp"] = datetime.now().isoformat()
    log_data["entries"].append(entry)
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log_data, f, indent=2, ensure_ascii=False, default=str)


def run_cmd(cmd: list[str], cwd: Path, dry: bool, desc: str) -> int:
    """Imprime (dry) o ejecuta (real) un comando externo. Retorna exit code."""
    print(f"  $ {' '.join(str(c) for c in cmd)}")
    print(f"    [cwd={cwd}]  ({desc})")
    if dry:
        return 0
    t0 = time.time()
    # Los scripts hijos imprimen Unicode (╔═ banners) y con stdout redirigido
    # Python usa cp1252 → UnicodeEncodeError. Forzar UTF-8 en el hijo.
    import os
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run([str(c) for c in cmd], cwd=str(cwd), env=env)
    print(f"    [exit={result.returncode} en {time.time() - t0:.0f}s]")
    return result.returncode


def discover_local_complexes(data_dir: Path) -> set[str]:
    """PDB IDs locales con proteína + ligando (requisito mínimo estructural)."""
    ids = set()
    if not data_dir.exists():
        return ids
    for d in data_dir.iterdir():
        if not d.is_dir() or len(d.name) != 4 or not d.name.isalnum():
            continue
        pid = d.name.lower()
        if (d / f"{pid}_protein.pdb").exists() and (d / f"{pid}_ligand.sdf").exists():
            ids.add(pid)
    return ids


def parse_index_pki_map(index_path: Path) -> dict[str, float]:
    """Mismo parsing que train_families.parse_index: {pdb_id_upper: pKi}."""
    pki_map: dict[str, float] = {}
    if not index_path.exists():
        return pki_map
    with open(index_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) >= 6:
                pdb_id = parts[0].upper()
                try:
                    pki_map[pdb_id] = float(parts[-1])
                except ValueError:
                    pass
    return pki_map


# ──────────────────────────────────────────────────────────────────────────
# Etapa 1 — Datos: enriquecer el pool de etiquetas (BindingDB, real)
# ──────────────────────────────────────────────────────────────────────────

def stage_1_enrich(args, dry: bool) -> None:
    banner("ETAPA 1/6 — Enriquecer INDEX con etiquetas BindingDB (real)")

    local_ids = discover_local_complexes(DATA_DIR)
    current = parse_index_pki_map(INDEX_PATH)
    local_upper = {p.upper() for p in local_ids}
    candidates = local_upper - set(current)
    print(f"  Complejos locales con proteína+ligando: {len(local_ids)}")
    print(f"  Etiquetas actuales en INDEX:            {len(current)}")
    print(f"  Candidatos nuevos (sin etiqueta):       {len(candidates)}")
    print(f"  Límite de piloto (--limit):             {args.limit}")

    steps = [
        f"1. Backup INDEX actual → {INDEX_PATH.with_name('INDEX_refined_data.2020.faseA_' + ts())}",
        "2. Descargar/escanear BindingDB_All TSV (~525 MB) con enrich_index_bindingdb.py",
        "3. Reconstruir etiquetas de los candidatos (Ki > Kd > IC50 > EC50; exactos primero)",
        "4. Escribir INDEX por etapas: entradas Fase A + hasta --limit nuevos",
        "5. Guardar manifest de selección (IDs elegidos) + hashes SHA-256",
    ]
    for s in steps:
        print(f"    - {s}")

    if MANIFEST_PATH.exists() and not args.force:
        print("\n  [ABORT] Ya existe un manifest de selección previo.")
        print("  Re-ejecutar con --force borra el manifest y re-selecciona.")
        print("  (El INDEX por etapas ya contiene las entradas nuevas: no repetir.)")
        sys.exit(3)

    if dry:
        print("\n  [DRY-RUN] Comando real que se ejecutaría:")
        zip_args = ["--skip-download"] if BINDINGDB_ZIP.exists() else []
        run_cmd(
            [sys.executable, str(SCRIPTS_DIR / "enrich_index_bindingdb.py"),
             "--data-dir", str(DATA_DIR),
             "--output", str(DATA_DIR / f"INDEX_faseb_enriched_full_{ts()}.2020")]
            + zip_args,
            cwd=SCRIPTS_DIR, dry=True,
            desc="descarga+scan BindingDB para todos los PDB locales (2.6M filas)",
        )
        print("\n  [DRY-RUN] Finalizado. No se descargó ni escribió nada.")
        return

    # ── Ejecución real ──
    backup_index = DATA_DIR / f"INDEX_refined_data.2020.faseA_{ts()}"
    shutil.copy2(INDEX_PATH, backup_index)
    print(f"\n  [OK] Backup del INDEX Fase A: {backup_index.name}")

    enriched_full = DATA_DIR / f"INDEX_faseb_enriched_full_{ts()}.2020"
    zip_flag = ["--skip-download"] if BINDINGDB_ZIP.exists() else []
    rc = run_cmd(
        [sys.executable, str(SCRIPTS_DIR / "enrich_index_bindingdb.py"),
         "--data-dir", str(DATA_DIR),
         "--output", str(enriched_full)] + zip_flag,
        cwd=SCRIPTS_DIR, dry=False,
        desc="enrich_index_bindingdb.py (descarga 525MB + scan TSV + RCSB metadata)",
    )
    if rc != 0 or not enriched_full.exists():
        print("\n  [ABORT] El enriquecimiento falló. El INDEX Fase A sigue intacto.")
        sys.exit(1)

    # Selección determinística: prioriza Ki/Kd exactos, luego el resto;
    # orden alfabético como desempate. Nunca más de --limit IDs nuevos.
    orig_lines = {}
    with open(INDEX_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                parts = line.split()
                if parts:
                    orig_lines[parts[0].upper()] = line

    enriched_map: dict[str, str] = {}
    with open(enriched_full, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                parts = line.split()
                if len(parts) >= 6 and parts[0].upper() not in orig_lines:
                    enriched_map[parts[0].upper()] = line

    def selection_key(pid_line: tuple[str, str]):
        pid, line = pid_line
        parts = line.split()
        raw = " ".join(parts[3:parts.index("//")]) if "//" in parts else ""
        m = re.search(r"(Ki|Kd|IC50|EC50)\s*([=<>~])\s*[\d.]+", raw)
        btype = m.group(1) if m else "other"
        prec = m.group(2) if m else "~"
        type_rank = {"Ki": 0, "Kd": 0, "IC50": 1, "EC50": 1, "other": 2}.get(btype, 2)
        prec_rank = 0 if prec == "=" else 1
        return (type_rank, prec_rank, pid)

    selected = sorted(enriched_map.items(), key=selection_key)[: args.limit]
    selected_ids = [pid for pid, _ in selected]
    print(f"  [OK] Seleccionados {len(selected_ids)} complejos nuevos "
          f"({len(enriched_map)} disponibles en BindingDB).")

    # Escribir INDEX por etapas: Fase A (líneas originales) + seleccionados.
    header = ("# PDBbind v2020 — INDEX por etapas (Fase B, piloto)\n"
              "# Entradas Fase A (865) + selección BindingDB (ver manifest)\n")
    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        f.write(header)
        for pid in sorted(orig_lines):
            f.write(orig_lines[pid] + "\n")
        for pid, line in sorted(selected, key=lambda x: x[0]):
            f.write(line + "\n")

    manifest = {
        "created_at": datetime.now().isoformat(),
        "mode": "bindingdb_enrichment",
        "limit": args.limit,
        "n_local_complexes": len(local_ids),
        "n_candidates": len(candidates),
        "n_selected_new": len(selected_ids),
        "selected_new_ids": sorted(selected_ids),
        "original_index_sha256": sha256_file(backup_index),
        "enriched_full_sha256": sha256_file(enriched_full),
        "staged_index_sha256": sha256_file(INDEX_PATH),
        "selection_rule": "Ki/Kd exactos primero, orden alfabético; "
                          "data_curator filtra IC50/EC50 y precisión no exacta en Etapa 4",
    }
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    append_pipeline_log({
        "stage": 1,
        "action": "index_enriched",
        "n_new_labels": len(selected_ids),
        "backup_index": backup_index.name,
        "hashes": {
            "original_index": manifest["original_index_sha256"],
            "enriched_full": manifest["enriched_full_sha256"],
            "staged_index": manifest["staged_index_sha256"],
        },
    })
    print(f"  [OK] INDEX por etapas escrito: {INDEX_PATH}")
    print(f"  [OK] Manifest: {MANIFEST_PATH.name}")
    print(f"  Rollback manual: copiar {backup_index.name} sobre INDEX_refined_data.2020")


# ──────────────────────────────────────────────────────────────────────────
# Etapa 2 — Redock: poses Vina de los complejos nuevos (reutiliza script real)
# ──────────────────────────────────────────────────────────────────────────

def stage_2_redock(args, dry: bool) -> None:
    banner("ETAPA 2/6 — Redock Vina de complejos nuevos (redock_pdbbind.py real)")

    if not MANIFEST_PATH.exists() and not dry:
        print("  [ABORT] No hay manifest de selección. Ejecutar Etapa 1 primero.")
        sys.exit(3)
    if MANIFEST_PATH.exists():
        manifest = load_json(MANIFEST_PATH)
        new_ids = [i.lower() for i in manifest["selected_new_ids"]]
    else:
        new_ids = []
    pending = [i for i in new_ids if not (VINA_CACHE / f"{i}.json").exists()]
    print(f"  IDs nuevos seleccionados: {len(new_ids)}")
    print(f"  Ya redockeados (cache):   {len(new_ids) - len(pending)}")
    print(f"  Pendientes de redock:     {len(pending)}")
    print(f"  Estimación: ~5 min/complejo → {len(pending) * 5 / max(args.max_workers, 1) / 60:.1f} h "
          f"con {args.max_workers} workers")

    if dry:
        print("\n  [DRY-RUN] Se importaría run_vina_redocking de rescoring/scripts/redock_pdbbind.py")
        print("  [DRY-RUN] y se procesarían solo los IDs del manifest (el script original")
        print("  [DRY-RUN] no soporta --limit; por eso este orquestador llama su función real).")
        print(f"  [DRY-RUN] Salida: {VINA_CACHE}/{{pdb_id}}.json (4 features Grupo B)")
        return

    if not pending:
        print("\n  [OK] Nada pendiente.")
        return

    vina_path = args.vina_path
    if not Path(vina_path).exists() and "/" not in vina_path and "\\" not in vina_path:
        from shutil import which
        if not which(vina_path):
            print(f"  [ABORT] Binario Vina no encontrado: '{vina_path}'. "
                  f"Usar --vina-path <ruta al .exe>.")
            sys.exit(1)

    # Import REAL del script de redock (sin modificarlo)
    sys.path.insert(0, str(SCRIPTS_DIR))
    from redock_pdbbind import run_vina_redocking

    VINA_CACHE.mkdir(parents=True, exist_ok=True)
    VINA_WORK.mkdir(parents=True, exist_ok=True)

    jobs = []
    for pid in pending:
        d = DATA_DIR / pid
        prot = d / f"{pid}_protein.pdb"
        sdf = d / f"{pid}_ligand.sdf"
        if prot.exists() and sdf.exists():
            jobs.append((pid, str(prot), str(sdf)))

    n_ok, n_fail = 0, 0
    failures: dict[str, str] = {}
    t0 = time.time()
    from concurrent.futures import ProcessPoolExecutor, as_completed
    with ProcessPoolExecutor(max_workers=max(1, args.max_workers)) as ex:
        futures = {
            ex.submit(run_vina_redocking, pid, prot, sdf, vina_path,
                      str(VINA_WORK / pid)): pid
            for pid, prot, sdf in jobs
        }
        for fut in as_completed(futures):
            pid = futures[fut]
            try:
                result, reason = fut.result(timeout=900)
            except Exception as e:
                failures[pid] = f"worker_exception:{type(e).__name__}"
                n_fail += 1
                continue
            if result is None:
                failures[pid] = reason
                n_fail += 1
                print(f"    [FAIL] {pid}: {reason}")
                continue
            (VINA_CACHE / f"{pid}.json").write_text(json.dumps(result))
            n_ok += 1
            elapsed = max(time.time() - t0, 1e-9)
            print(f"    [{n_ok + n_fail}/{len(jobs)}] OK={n_ok} FAIL={n_fail} "
                  f"({(n_ok + n_fail) / elapsed:.2f} compl/min)")

    if failures:
        (VINA_CACHE / "redock_failures.json").write_text(
            json.dumps(failures, indent=2, sort_keys=True))

    append_pipeline_log({
        "stage": 2,
        "action": "vina_redock",
        "n_pending": len(jobs),
        "n_success": n_ok,
        "n_failed": n_fail,
        "failures_manifest": "vina_redock_cache/redock_failures.json" if failures else None,
        "hashes": {"manifest": sha256_file(MANIFEST_PATH)},
    })
    print(f"\n  [OK] Redock: {n_ok} exitosos, {n_fail} fallidos "
          f"(motivos en vina_redock_cache/redock_failures.json; "
          f"los fallidos usan imputación por media en training).")


# ──────────────────────────────────────────────────────────────────────────
# Etapa 3 — Features: cache v4 de los nuevos complejos (extractor REAL)
# ──────────────────────────────────────────────────────────────────────────

def stage_3_features(args, dry: bool) -> None:
    banner("ETAPA 3/6 — Precomputar features v4 (feature_extractor.extract_single_complex)")

    if not MANIFEST_PATH.exists() and not dry:
        print("  [ABORT] No hay manifest. Ejecutar Etapa 1 primero.")
        sys.exit(3)
    if MANIFEST_PATH.exists():
        manifest = load_json(MANIFEST_PATH)
        new_ids = [i.lower() for i in manifest["selected_new_ids"]]
    else:
        new_ids = []
    pending = [i for i in new_ids if not (CACHE_DIR / f"{i}.json").exists()]
    pending = [i for i in pending
               if (DATA_DIR / i / f"{i}_protein.pdb").exists()
               and (DATA_DIR / i / f"{i}_ligand.sdf").exists()]
    print(f"  IDs nuevos: {len(new_ids)} | pendientes de features 3D: {len(pending)}")
    print(f"  Formato de salida: {CACHE_DIR}/{{pdb_id}}.json = "
          "{\"version\": 4, \"features\": {...}} (mismo que feature_cache_v4)")
    print(f"  Estimación: 20s-2min/complejo → {len(pending) / max(args.max_workers, 1) / 30:.1f}-"
          f"{len(pending) * 2 / max(args.max_workers, 1) / 60:.1f} h con {args.max_workers} workers")

    if dry:
        print("\n  [DRY-RUN] Se importaría extract_single_complex de rescoring/feature_extractor.py")
        print("  [DRY-RUN] (mismo path que train_orchestrator._extract_features_for_all usa para")
        print("  [DRY-RUN]  producir feature_cache_v4) y se escribiría solo para los IDs pendientes.")
        print("  [DRY-RUN] Luego se haría merge de features Vina (vina_redock_cache) al cache.")
        return

    sys.path.insert(0, str(RESCORING_DIR))
    from feature_extractor import (CACHE_VERSION, INTERACTION_FEATURES,
                                   extract_single_complex, zero_all_3d_features)

    jobs = []
    for pid in pending:
        d = DATA_DIR / pid
        jobs.append((pid, str(d / f"{pid}_protein.pdb"), str(d / f"{pid}_ligand.sdf")))

    n_ok, n_fail = 0, 0
    t0 = time.time()
    from concurrent.futures import ProcessPoolExecutor, as_completed
    with ProcessPoolExecutor(max_workers=max(1, args.max_workers)) as ex:
        futures = {
            ex.submit(extract_single_complex, prot, lig): pid
            for pid, prot, lig in jobs
        }
        for fut in as_completed(futures):
            pid = futures[fut]
            try:
                feats = fut.result(timeout=300)
            except Exception as e:
                print(f"    [FAIL] {pid}: {e}")
                feats = zero_all_3d_features()
            if feats is None:
                feats = zero_all_3d_features()

            has_nonzero = any(feats.get(f, 0.0) > 0.0 for f in INTERACTION_FEATURES)
            if not has_nonzero:
                n_fail += 1
                print(f"    [WARN] {pid}: features 3D en cero (¿PDB ilegible?)")
            else:
                n_ok += 1

            # Merge de features Vina (Grupo B) desde el cache de redock
            vina_file = VINA_CACHE / f"{pid}.json"
            if vina_file.exists():
                try:
                    feats.update(json.loads(vina_file.read_text()))
                    feats["vina_enriched"] = True
                    feats["vina_exhaustiveness"] = 8
                except Exception:
                    pass

            cache_data = {"version": CACHE_VERSION, "features": feats}
            (CACHE_DIR / f"{pid}.json").write_text(json.dumps(cache_data))
            elapsed = max(time.time() - t0, 1e-9)
            print(f"    [{n_ok + n_fail}/{len(jobs)}] OK={n_ok} FAIL={n_fail} "
                  f"({(n_ok + n_fail) / elapsed:.2f} compl/min)")

    append_pipeline_log({
        "stage": 3,
        "action": "features_v4",
        "n_pending": len(jobs),
        "n_success": n_ok,
        "n_failed_3d": n_fail,
        "cache_version": CACHE_VERSION,
        "hashes": {"manifest": sha256_file(MANIFEST_PATH)},
    })
    print(f"\n  [OK] Features v4: {n_ok} con 3D real, {n_fail} en cero.")


# ──────────────────────────────────────────────────────────────────────────
# Etapa 4 — Split: NUEVO holdout scaffold-disjoint sobre el pool ampliado
# ──────────────────────────────────────────────────────────────────────────

def stage_4_split(args, dry: bool) -> None:
    banner("ETAPA 4/6 — Carve NUEVO holdout scaffold-disjoint (pool ampliado)")

    print("  INVARIANTE CIENTÍFICO (obligatorio):")
    print("    * Los 328 IDs del holdout Fase A se fuerzan dentro del NUEVO holdout.")
    print("    * El pool de entrenamiento Fase B nunca contiene esos 328 IDs.")
    print("    * verify_scaffold_disjoint() debe dar 0 violaciones antes de guardar.")
    print("    * Se reutiliza create_frozen_test_set / scaffold_split_cv / verify")
    print("      de data_splitter.py (mismo protocolo A1, seed 42, test_size 500).")

    steps = [
        "1. PDBBindParser.load() sobre el INDEX por etapas (865 + N nuevos)",
        "2. DataCurator.curate() (rechaza IC50/EC50 y precisión no exacta)",
        "3. VIPAuditor.audit_all() + clasificación estructural",
        "4. create_frozen_test_set(vip, fam, test_size=500, seed=42)",
        "5. Cierre del invariante: añadir holdout Fase A faltante + cierre por scaffold",
        "6. verify_scaffold_disjoint == 0 → guardar split_config_faseb.json",
        "7. family_map_faseb.json = family_map Fase A + clasificación de IDs nuevos",
    ]
    for s in steps:
        print(f"    - {s}")

    if dry:
        print(f"\n  [DRY-RUN] Salida real: {SPLIT_FASEB.name} y {FAMILY_MAP_FASEB.name}")
        print("  [DRY-RUN] split_config.json de Fase A NO se toca en esta etapa.")
        return

    sys.path.insert(0, str(RESCORING_DIR))
    from data_curator import DataCurator
    from data_splitter import (create_frozen_test_set, save_split_config,
                               scaffold_split_cv, verify_scaffold_disjoint)
    from pdbbind_parser import PDBBindParser
    from structural_family import StructuralFamilyClassifier
    from vip_audit import VIPAuditor, get_vip_complexes

    parser = PDBBindParser(str(DATA_DIR))
    n_loaded = parser.load(include_other=False)
    print(f"\n  Complejos cargados desde INDEX: {n_loaded}")
    if n_loaded == 0:
        print("  [ABORT] Parser no cargó complejos. Revisar INDEX por etapas.")
        sys.exit(1)

    curator = DataCurator()
    curated, curation_report = curator.curate(parser.complexes)
    print(f"  Tras curación: {len(curated)} "
          f"(removidos {curation_report.n_input_total - curation_report.n_output})")

    auditor = VIPAuditor(skip_structure_checks=args.skip_structure_checks)
    audit_report = auditor.audit_all(curated)
    vip_ids = set(get_vip_complexes(audit_report))
    vip = [c for c in curated if c.pdb_id in vip_ids]
    print(f"  Complejos VIP: {len(vip)}")

    classifier = StructuralFamilyClassifier()
    classifications = classifier.classify_all(vip)

    test_ids = create_frozen_test_set(
        vip, classifications, test_size=args.test_size, seed=args.seed,
    )
    print(f"  Holdout base (scaffold-disjoint, seed={args.seed}): {len(test_ids)}")

    # ── Invariante: el holdout Fase A nunca entra al train de Fase B ──
    old_split = load_json(SPLIT_CURRENT)
    old_frozen = {str(pid).lower() for pid in old_split.get("frozen_test_set", [])}
    added_old = old_frozen - {pid.lower() for pid in test_ids}
    test_set = {pid.lower() for pid in test_ids} | added_old
    print(f"  IDs del holdout Fase A añadidos por invariante: {len(added_old)}")

    # ── Cierre por scaffold: si un ID del holdout comparte scaffold con un
    #    complejo del train, TODO su grupo scaffold pasa al holdout. ──
    guard = 0
    while guard < 10:
        test_list = sorted(test_set)
        ok, violations = verify_scaffold_disjoint(test_list, vip)
        if ok:
            break
        n_viol = sum(len(v) for v in violations.values())
        print(f"    [cierre scaffold] añadiendo {n_viol} complejos al holdout...")
        for vids in violations.values():
            test_set.update(pid.lower() for pid in vids)
        guard += 1
    if guard >= 10:
        print("  [ABORT] Cierre por scaffold no convergió.")
        sys.exit(1)

    test_ids_final = sorted(test_set)
    n_train_pool = sum(1 for c in vip if c.pdb_id not in test_set)
    assert not (set(c.pdb_id for c in vip) - test_set) & old_frozen, \
        "INVARIANTE VIOLADO: un ID del holdout Fase A quedó en train"

    splits = scaffold_split_cv(vip, test_ids_final, n_folds=5, seed=args.seed)
    ok, violations = verify_scaffold_disjoint(test_ids_final, vip)
    if not ok:
        print("  [ABORT] Holdout NO scaffold-disjoint tras el cierre.")
        sys.exit(1)

    save_split_config(test_ids_final, splits, SPLIT_FASEB, seed=args.seed)
    print(f"  [OK] Holdout final: {len(test_ids_final)} IDs "
          f"(train pool: {n_train_pool}) — scaffold-disjoint verificado.")

    # ── family_map Fase B: preservar clasificación Fase A + añadir nuevos ──
    old_fam = load_json(FAMILY_MAP_CURRENT) if FAMILY_MAP_CURRENT.exists() else {}
    new_fam = {}
    for cpx in vip:
        pid = cpx.pdb_id
        if pid.lower() in {k.lower() for k in old_fam}:
            continue
        fc = classifications.get(pid)
        new_fam[pid] = fc.family if hasattr(fc, "family") else str(fc)
    merged_fam = dict(old_fam)
    merged_fam.update(new_fam)
    with open(FAMILY_MAP_FASEB, "w", encoding="utf-8") as f:
        json.dump(merged_fam, f, indent=2, ensure_ascii=False)
    print(f"  [OK] family_map_faseb.json: {len(merged_fam)} entradas "
          f"({len(new_fam)} nuevas)")

    append_pipeline_log({
        "stage": 4,
        "action": "split_faseb",
        "n_loaded": n_loaded,
        "n_curated": len(curated),
        "n_vip": len(vip),
        "n_holdout": len(test_ids_final),
        "n_old_frozen_added": len(added_old),
        "n_train_pool": n_train_pool,
        "scaffold_violations": 0,
        "hashes": {
            "old_split_config": sha256_file(SPLIT_CURRENT),
            "new_split_config": sha256_file(SPLIT_FASEB),
            "old_family_map": sha256_file(FAMILY_MAP_CURRENT)
            if FAMILY_MAP_CURRENT.exists() else None,
            "new_family_map": sha256_file(FAMILY_MAP_FASEB),
        },
    })
    print(f"  [OK] {SPLIT_FASEB.name} listo. split_config.json de Fase A intacto.")


# ──────────────────────────────────────────────────────────────────────────
# Etapa 5 — Train: train_families.py sobre el pool ampliado (con swap seguro)
# ──────────────────────────────────────────────────────────────────────────

def stage_5_train(args, dry: bool) -> None:
    banner("ETAPA 5/6 — Entrenar train_families.py sobre pool ampliado")

    if not SPLIT_FASEB.exists() and not dry:
        print("  [ABORT] No existe split_config_faseb.json. Ejecutar Etapa 4.")
        sys.exit(3)

    existing_faseb = [p for p in ARTIFACTS_DIR.glob("model_a_*_faseb.joblib")]
    if existing_faseb and not args.force:
        print("  [ABORT] Ya existen modelos *_faseb.joblib de un entrenamiento previo.")
        print("  Usar --force para respaldarlos y volver a entrenar.")
        sys.exit(3)

    backup_dir = ARTIFACTS_DIR / f"backup_{ts()}_faseB_pre"
    steps = [
        f"1. Backup de modelos activos + split_config + family_map → {backup_dir.name}",
        "2. Swap TEMPORAL: split_config_faseb.json → split_config.json",
        "3. Swap TEMPORAL: family_map_faseb.json → family_map.json",
        "4. python train_families.py (cwd=rescoring) — entrena universal + familias",
        "5. Renombrar nuevos model_a_*.joblib → model_a_*_faseb.joblib",
        "6. RESTAURAR split_config, family_map y model_a_* originales (Fase A activa)",
        "7. Registrar SHA-256 de split/family_map usados y de los nuevos joblibs",
    ]
    for s in steps:
        print(f"    - {s}")

    train_cmd = [sys.executable, "train_families.py"]
    if dry:
        run_cmd(train_cmd, cwd=RESCORING_DIR, dry=True,
                desc="train_families (escribe model_a_*.joblib en artifacts/)")
        print("\n  [DRY-RUN] Nota: train_families.py usa nombres fijos de salida.")
        print("  [DRY-RUN] El swap/rename/restore protege los artefactos Fase A.")
        return

    old_faseb_backup = None
    if existing_faseb and args.force:
        old_faseb_backup = ARTIFACTS_DIR / f"backup_{ts()}_faseB_prev"
        old_faseb_backup.mkdir(exist_ok=True)
        for p in existing_faseb:
            shutil.copy2(p, old_faseb_backup / p.name)
        print(f"  [force] Modelos *_faseb previos respaldados en {old_faseb_backup.name}")

    # ── Backup ──
    backup_dir.mkdir(exist_ok=True)
    for name in FAMILY_NAMES:
        for ext in [".joblib", ".json", ".metadata.json"]:
            src = ARTIFACTS_DIR / f"model_a_{name}{ext}"
            if src.exists():
                shutil.copy2(src, backup_dir / src.name)
    shutil.copy2(SPLIT_CURRENT, backup_dir / SPLIT_CURRENT.name)
    if FAMILY_MAP_CURRENT.exists():
        shutil.copy2(FAMILY_MAP_CURRENT, backup_dir / FAMILY_MAP_CURRENT.name)
    print(f"\n  [OK] Backup de Fase A: {backup_dir.name}")

    # ── Swap temporal de split y family_map ──
    shutil.copy2(SPLIT_FASEB, SPLIT_CURRENT)
    if FAMILY_MAP_FASEB.exists():
        shutil.copy2(FAMILY_MAP_FASEB, FAMILY_MAP_CURRENT)
    split_used_sha = sha256_file(SPLIT_CURRENT)
    fam_used_sha = sha256_file(FAMILY_MAP_CURRENT) if FAMILY_MAP_CURRENT.exists() else None
    index_used_sha = sha256_file(INDEX_PATH)
    print("  [OK] split_config_faseb instalado temporalmente en split_config.json")

    # ── Entrenar ──
    t0 = time.time()
    rc = run_cmd(train_cmd, cwd=RESCORING_DIR, dry=False, desc="train_families.py")
    elapsed_min = (time.time() - t0) / 60
    if rc != 0:
        print("  [ABORT] train_families falló. Restaurando split/family_map...")
        shutil.copy2(backup_dir / SPLIT_CURRENT.name, SPLIT_CURRENT)
        if (backup_dir / FAMILY_MAP_CURRENT.name).exists():
            shutil.copy2(backup_dir / FAMILY_MAP_CURRENT.name, FAMILY_MAP_CURRENT)
        sys.exit(1)
    print(f"  [OK] Entrenamiento finalizado en {elapsed_min:.1f} min")

    # ── Renombrar nuevos + restaurar originales ──
    new_hashes = {}
    for name in FAMILY_NAMES:
        new_joblib = ARTIFACTS_DIR / f"model_a_{name}.joblib"
        if new_joblib.exists():
            shutil.move(str(new_joblib), str(ARTIFACTS_DIR / f"model_a_{name}_faseb.joblib"))
            new_hashes[f"model_a_{name}_faseb.joblib"] = \
                sha256_file(ARTIFACTS_DIR / f"model_a_{name}_faseb.joblib")
    for p in backup_dir.glob("model_a_*"):
        shutil.copy2(p, ARTIFACTS_DIR / p.name)
    shutil.copy2(backup_dir / SPLIT_CURRENT.name, SPLIT_CURRENT)
    if (backup_dir / FAMILY_MAP_CURRENT.name).exists():
        shutil.copy2(backup_dir / FAMILY_MAP_CURRENT.name, FAMILY_MAP_CURRENT)

    append_pipeline_log({
        "stage": 5,
        "action": "train_faseb",
        "backup_dir": backup_dir.name,
        "hashes": {
            "split_used": split_used_sha,
            "family_map_used": fam_used_sha,
            "index_used": index_used_sha,
            "new_models": new_hashes,
        },
    })
    print(f"\n  [OK] Modelos Fase B: {', '.join(sorted(new_hashes))}")
    print("  [OK] Artefactos Fase A restaurados y activos (nada se perdió).")


# ──────────────────────────────────────────────────────────────────────────
# Etapa 6 — Evaluate: holdout nuevo + comparación contra baseline Fase A
# ──────────────────────────────────────────────────────────────────────────

def _convert_joblib_to_json(joblib_path: Path, json_path: Path,
                            meta_path: Path) -> None:
    """Convierte .joblib → .json + .metadata.json (espejo de
    model_manager.ModelManager._auto_convert_joblib, sin modificarlo)."""
    import joblib as _joblib

    data = _joblib.load(str(joblib_path))
    booster = data.get("booster") or data.get("model")
    if booster is None:
        raise ValueError(f"joblib sin booster: {joblib_path}")
    booster.save_model(str(json_path))
    metadata = {
        "feature_names": data.get("feature_names", []),
        "metrics": data.get("metrics", {}),
        "train_samples": data.get("train_samples", 0),
        "train_timestamp": data.get("train_timestamp", ""),
        "params": data.get("params", {}),
    }
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False, default=str)


def _evaluate_model_on_split(model_json: Path, split_cfg: Path,
                             label: str, quiet: bool = False) -> dict:
    """Evalúa un modelo sobre un split dado reutilizando evaluate_test_set.py.

    Importa las funciones REALES de evaluate_test_set y parchea sus
    constantes de módulo (no se modifica el archivo).
    """
    import numpy as np
    from scipy.stats import pearsonr, spearmanr

    sys.path.insert(0, str(RESCORING_DIR))
    import evaluate_test_set as ev

    ev.SPLIT_CONFIG = split_cfg
    ev.PDBBIND_DIR = DATA_DIR
    ev.INDEX_PATH = INDEX_PATH
    ev.FEATURE_CACHE = CACHE_DIR
    ev.MODEL_JSON = model_json
    ev.MODEL_META = model_json.with_suffix(".metadata.json")
    ev.FAMILY_MAP = FAMILY_MAP_CURRENT

    test_ids = ev.load_test_ids(split_cfg)
    labels = ev.parse_index(INDEX_PATH)
    features_3d = ev.load_3d_features(CACHE_DIR)
    test_ids_upper = [pid.upper() for pid in test_ids]
    valid_ids = [pid for pid in test_ids_upper
                 if pid in features_3d and pid in labels]
    if len(valid_ids) < 10:
        raise RuntimeError(f"[{label}] muy pocos complejos válidos: {len(valid_ids)}")
    features = ev.enrich_features(valid_ids, features_3d)
    model, model_feature_names, is_delta = ev.load_model(model_json)
    X = ev.build_matrix(valid_ids, features, model_feature_names)
    import xgboost as xgb
    delta_preds = model.predict(xgb.DMatrix(X, feature_names=model_feature_names))
    y_true, y_pred = [], []
    for i, pid in enumerate(valid_ids):
        y_true.append(labels[pid])
        if is_delta:
            vina_score = features[pid].get("vina_best_score", 0.0)
            y_pred.append((-vina_score / VINA_TO_PKI) + float(delta_preds[i]))
        else:
            y_pred.append(float(delta_preds[i]))
    yt = np.array(y_true)
    yp = np.array(y_pred)
    rho, pval = spearmanr(yt, yp)
    r_pearson, p_pearson = pearsonr(yt, yp)
    rmse = float(np.sqrt(np.mean((yt - yp) ** 2)))
    mae = float(np.mean(np.abs(yt - yp)))
    ci_lo, ci_hi = ev.bootstrap_ci(yt, yp, n_iter=10_000, statistic="spearman")
    ci_lo_p, ci_hi_p = ev.bootstrap_ci(yt, yp, n_iter=10_000, statistic="pearson")
    return {
        "label": label,
        "n": len(valid_ids),
        "spearman": round(float(rho), 4),
        "spearman_p": round(float(pval), 6),
        "ci95_spearman": [round(ci_lo, 4), round(ci_hi, 4)],
        "pearson": round(float(r_pearson), 4),
        "pearson_p": round(float(p_pearson), 6),
        "ci95_pearson": [round(ci_lo_p, 4), round(ci_hi_p, 4)],
        "rmse": round(rmse, 4),
        "mae": round(mae, 4),
        "y_true_range": [round(float(yt.min()), 2), round(float(yt.max()), 2)],
    }


def _extract_baseline_from_doc() -> dict:
    """Lee docs/38_FASE_B_BASELINE.md y extrae los números del baseline."""
    if not BASELINE_DOC.exists():
        return {
            "spearman": BASELINE_HOLDOUT_SPEARMAN,
            "ci_lo": BASELINE_HOLDOUT_CI_LO,
            "ci_hi": BASELINE_HOLDOUT_CI_HI,
            "n": BASELINE_N_HOLDOUT,
            "source": "constantes del script (doc38 no encontrado)",
        }
    text = BASELINE_DOC.read_text(encoding="utf-8")
    m_s = re.search(r"Spearman holdout \| \*\*([\d.]+)\*\*", text)
    m_ci = re.search(r"\[([\d.]+), ([\d.]+)\] \(bootstrap 10k\)", text)
    return {
        "spearman": float(m_s.group(1)) if m_s else BASELINE_HOLDOUT_SPEARMAN,
        "ci_lo": float(m_ci.group(1)) if m_ci else BASELINE_HOLDOUT_CI_LO,
        "ci_hi": float(m_ci.group(2)) if m_ci else BASELINE_HOLDOUT_CI_HI,
        "n": BASELINE_N_HOLDOUT,
        "source": "docs/38_FASE_B_BASELINE.md",
    }


def stage_6_evaluate(args, dry: bool) -> None:
    banner("ETAPA 6/6 — Evaluación en holdout nuevo + comparación con Fase A")

    faseb_joblib = ARTIFACTS_DIR / "model_a_universal_faseb.joblib"
    faseb_json = ARTIFACTS_DIR / "model_a_universal_faseb.json"
    faseb_meta = ARTIFACTS_DIR / "model_a_universal_faseb.metadata.json"
    fasea_json = ARTIFACTS_DIR / "model_a_universal.json"

    print(f"  Holdout de evaluación: {SPLIT_FASEB.name} (NUEVO, scaffold-disjoint)")
    print(f"  Modelo Fase B: {faseb_json.name}  (convertido desde {faseb_joblib.name})")
    print(f"  Modelo Fase A (activo): {fasea_json.name}")
    print("  Comparación: Spearman + CI95 bootstrap 10k, Fase A vs Fase B")
    print("  SOBRE EL MISMO holdout nuevo, más el baseline histórico (doc 38).")

    if dry:
        print("\n  [DRY-RUN] Se importarían las funciones de evaluate_test_set.py")
        print("  [DRY-RUN] y se escribiría faseb_comparison_report.json en artifacts/.")
        print("  [DRY-RUN] Ningún modelo se toca; solo lectura.")
        return

    if not faseb_joblib.exists() and not dry:
        print("  [ABORT] No existe model_a_universal_faseb.joblib. Ejecutar Etapa 5.")
        sys.exit(3)
    if not SPLIT_FASEB.exists() and not dry:
        print("  [ABORT] No existe split_config_faseb.json. Ejecutar Etapa 4.")
        sys.exit(3)

    # Convertir joblib → json (runtime, mismo formato que model_manager)
    _convert_joblib_to_json(faseb_joblib, faseb_json, faseb_meta)
    print(f"  [OK] Convertido: {faseb_json.name} + metadata")

    baseline = _extract_baseline_from_doc()
    print(f"\n  Baseline Fase A (doc 38, holdout 328 histórico): "
          f"Spearman {baseline['spearman']} [{baseline['ci_lo']}, {baseline['ci_hi']}]")

    # 1) Fase B sobre el holdout NUEVO
    print("\n  Evaluando model_a_universal_faseb en el holdout nuevo...")
    res_b = _evaluate_model_on_split(faseb_json, SPLIT_FASEB, "faseb_nuevo_holdout")

    # 2) Fase A sobre el MISMO holdout nuevo (comparación justa)
    print("  Evaluando model_a_universal (Fase A) en el MISMO holdout nuevo...")
    res_a = _evaluate_model_on_split(fasea_json, SPLIT_FASEB, "fasea_nuevo_holdout")

    # ── Go/No-Go ──
    rho_b = res_b["spearman"]
    ci_lo_b = res_b["ci95_spearman"][0]
    delta_vs_baseline = rho_b - baseline["spearman"]
    delta_vs_fasea = rho_b - res_a["spearman"]

    if rho_b >= baseline["spearman"] and ci_lo_b >= baseline["ci_lo"]:
        verdict = "GO"
    elif rho_b >= baseline["spearman"] and ci_lo_b < baseline["ci_lo"]:
        verdict = "WARN"
    else:
        verdict = "NO-GO"

    report = {
        "timestamp": datetime.now().isoformat(),
        "baseline_fase_a": baseline,
        "fase_a_en_holdout_nuevo": res_a,
        "fase_b_en_holdout_nuevo": res_b,
        "deltas": {
            "faseb_vs_baseline_historico": round(delta_vs_baseline, 4),
            "faseb_vs_fasea_mismo_holdout": round(delta_vs_fasea, 4),
        },
        "verdict": verdict,
        "go_no_go_criteria": {
            "go": "Spearman ≥ {b} Y CI95_lo ≥ {lo}".format(
                b=baseline["spearman"], lo=baseline["ci_lo"]),
            "warn": "Spearman ≥ baseline pero CI95 se solapa hacia abajo",
            "no_go": "Spearman < {b} (no mejora el baseline)".format(
                b=baseline["spearman"]),
        },
        "hashes": {
            "faseb_model_json": sha256_file(faseb_json),
            "fasea_model_json": sha256_file(fasea_json),
            "split_used": sha256_file(SPLIT_FASEB),
            "index_used": sha256_file(INDEX_PATH),
        },
    }
    report_path = ARTIFACTS_DIR / "faseb_comparison_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)

    append_pipeline_log({"stage": 6, "action": "evaluate", "report": report_path.name,
                         "verdict": verdict, "hashes": report["hashes"]})

    print("\n" + "-" * 74)
    print("  COMPARACIÓN (holdout nuevo, n={a} Fase A / n={b} Fase B)".format(
        a=res_a["n"], b=res_b["n"]))
    print("-" * 74)
    for r in (res_a, res_b):
        print(f"  {r['label']:22s} Spearman={r['spearman']:.4f} "
              f"[{r['ci95_spearman'][0]:.4f}, {r['ci95_spearman'][1]:.4f}] "
              f"Pearson={r['pearson']:.4f} RMSE={r['rmse']:.4f}")
    print(f"  baseline (doc38)        Spearman={baseline['spearman']} "
          f"[{baseline['ci_lo']}, {baseline['ci_hi']}]")
    print(f"\n  VEREDICTO: {verdict}  "
          f"(Δ vs baseline={delta_vs_baseline:+.4f}, Δ vs FaseA mismo holdout={delta_vs_fasea:+.4f})")
    print(f"  Reporte: {report_path.name}")
    if verdict == "GO":
        print("  Siguiente paso: --promote (requiere decisión explícita del usuario).")


# ──────────────────────────────────────────────────────────────────────────
# Promote — swap final EXPLÍCITO (solo con --promote)
# ──────────────────────────────────────────────────────────────────────────

def promote(args, dry: bool) -> None:
    banner("PROMOTE — Activación del modelo Fase B (swap final explícito)")

    steps = [
        "1. Backup de model_a_*.json/.metadata/.joblib activos → backup_*_faseB_promote/",
        "2. Convertir model_a_*_faseb.joblib → model_a_*.json + .metadata.json",
        "3. Copiar los Fase B sobre los nombres activos (model_a_universal.json, ...)",
        "4. Registrar SHA-256 antes/después en faseb_pipeline_log.json",
        "5. (Manual) regenerar manifest con scripts/generate_model_manifest.py",
    ]
    for s in steps:
        print(f"    - {s}")

    if dry:
        print("\n  [DRY-RUN] Nada se modifica. El modelo Fase A sigue activo.")
        return

    faseb_joblibs = sorted(ARTIFACTS_DIR.glob("model_a_*_faseb.joblib"))
    if not faseb_joblibs:
        print("  [ABORT] No hay modelos *_faseb.joblib. Ejecutar Etapa 5 primero.")
        sys.exit(3)

    backup_dir = ARTIFACTS_DIR / f"backup_{ts()}_faseB_promote"
    backup_dir.mkdir(exist_ok=True)
    before_hashes, after_hashes = {}, {}

    # Backup de activos
    for name in FAMILY_NAMES:
        for ext in [".json", ".metadata.json", ".joblib"]:
            src = ARTIFACTS_DIR / f"model_a_{name}{ext}"
            if src.exists():
                shutil.copy2(src, backup_dir / src.name)
                before_hashes[src.name] = sha256_file(src)

    # Convertir + copiar
    for joblib_path in faseb_joblibs:
        name = joblib_path.stem.replace("_faseb", "")
        json_path = ARTIFACTS_DIR / f"{name}.json"
        meta_path = ARTIFACTS_DIR / f"{name}.metadata.json"
        _convert_joblib_to_json(joblib_path, json_path, meta_path)
        after_hashes[json_path.name] = sha256_file(json_path)
        after_hashes[meta_path.name] = sha256_file(meta_path)
        print(f"  [OK] Activado: {json_path.name}")

    append_pipeline_log({
        "stage": "promote",
        "action": "model_activated",
        "backup_dir": backup_dir.name,
        "before_hashes": before_hashes,
        "after_hashes": after_hashes,
    })
    print(f"\n  [OK] Swap completo. Backup: {backup_dir.name}")
    print("  Recordatorio manual: actualizar training_report.json y "
          "docs/38_FASE_B_BASELINE.md con la comparación, y regenerar "
          "model-manifest.json (scripts/generate_model_manifest.py).")


# ──────────────────────────────────────────────────────────────────────────
# Dry-run global + main
# ──────────────────────────────────────────────────────────────────────────

def dry_run_all(args) -> None:
    banner("FASE B — DRY-RUN GLOBAL (nada se ejecuta)")
    print(f"  Pool actual: {len(discover_local_complexes(DATA_DIR))} complejos locales, "
          f"{len(parse_index_pki_map(INDEX_PATH))} etiquetas, "
          f"{len(list(CACHE_DIR.glob('*.json'))) if CACHE_DIR.exists() else 0} features cacheadas")
    print(f"  Límite piloto: {args.limit} | workers: {args.max_workers} | "
          f"test_size: {args.test_size} | seed: {args.seed}")
    for fn in (stage_1_enrich, stage_2_redock, stage_3_features,
               stage_4_split, stage_5_train, stage_6_evaluate):
        fn(args, dry=True)
    promote(args, dry=True)
    banner("DRY-RUN COMPLETO")


def main() -> int:
    # Consola Windows cp1252 no soporta flechas/unicode del banner:
    # forzar UTF-8 con reemplazo seguro.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    ap = argparse.ArgumentParser(
        description="Fase B — expansión de dataset y reentrenamiento honesto",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Etapas: 1=enriquecer etiquetas (BindingDB)  2=redock Vina\n"
            "        3=features v4  4=split scaffold-disjoint NUEVO  5=train  6=evaluate\n"
            "Promoción: --promote (swap final explícito tras backup).\n"
            "Sin flags no ejecuta nada. --dry-run imprime todo sin ejecutar."
        ),
    )
    ap.add_argument("--stage", type=int, choices=[1, 2, 3, 4, 5, 6],
                    help="Ejecutar SOLO esta etapa (1..6)")
    ap.add_argument("--all", action="store_true", help="Ejecutar etapas 1→6 en orden")
    ap.add_argument("--promote", action="store_true",
                    help="Swap final: activar modelos Fase B (requiere backup previo)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Imprimir todos los pasos sin ejecutar nada pesado")
    ap.add_argument("--limit", type=int, default=300,
                    help="Máximo de complejos NUEVOS en el piloto (default 300)")
    ap.add_argument("--max-workers", type=int, default=6,
                    help="Workers paralelos para redock/features (default 6)")
    ap.add_argument("--vina-path", type=str, default="vina",
                    help="Ruta al binario de AutoDock Vina (default: 'vina' en PATH)")
    ap.add_argument("--test-size", type=int, default=500,
                    help="Tamaño objetivo del NUEVO holdout (default 500)")
    ap.add_argument("--seed", type=int, default=42, help="Semilla de splits (default 42)")
    ap.add_argument("--skip-structure-checks", action="store_true",
                    help="VIP audit sin checks de estructura (más rápido, menos estricto)")
    ap.add_argument("--force", action="store_true",
                    help="Re-ejecutar etapa aunque ya exista manifest/modelos previos")
    args = ap.parse_args()

    if args.dry_run:
        if args.stage:
            {1: stage_1_enrich, 2: stage_2_redock, 3: stage_3_features,
             4: stage_4_split, 5: stage_5_train, 6: stage_6_evaluate}[args.stage](
                args, dry=True)
        else:
            dry_run_all(args)
        return 0

    if args.promote and not args.stage:
        promote(args, dry=False)
        return 0

    if not args.all and not args.stage:
        print("Nada que hacer: se requiere --stage N, --all, --promote o --dry-run.")
        ap.print_help()
        return 2

    stages = {
        1: stage_1_enrich, 2: stage_2_redock, 3: stage_3_features,
        4: stage_4_split, 5: stage_5_train, 6: stage_6_evaluate,
    }
    if args.all:
        for n in range(1, 7):
            stages[n](args, dry=False)
    else:
        stages[args.stage](args, dry=False)
        if args.promote:
            promote(args, dry=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
