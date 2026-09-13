"""Inventario de exposicion previa: que PDB / dianas ya vio el producto.

No juzga: enumera. Lee solo artefactos versionados del bundle y del arbol de
ciencia, y emite `validation/leakage/seen_inventory.json` con tres conjuntos:

  SEEN      el identificador exacto participo en entrenamiento, curacion,
            holdout congelado, seleccion de pesos o goldens;
  RELATED   la DIANA (no el complejo) aparece en alguno de esos usos, de modo
            que un PDB distinto de la misma proteina hereda homologia ~100%;
  EXTERNAL  ni el complejo ni su diana aparecen en ningun artefacto leido.

La clasificacion EXTERNAL es una afirmacion de ausencia y por eso se emite
junto a `sources_read`: si una fuente de exposicion no esta en esa lista, la
ausencia no la cubre.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from datetime import datetime, timezone
from pathlib import Path

# Raiz de salida: este worktree de validacion (solo escribe bajo validation/).
ROOT = Path(__file__).resolve().parent.parent
# Raiz de entrada: el arbol del producto, donde viven el bundle staged y data/.
# Estan gitignorados, asi que no aparecen en un worktree limpio.
PRODUCT_ROOT = Path(
    os.environ.get("MOLDESIGN_PRODUCT_ROOT", r"D:/moldesign-build")
).resolve()


def _load(path: Path):
    with io.open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--product-root", type=Path, default=PRODUCT_ROOT)
    args = ap.parse_args()
    src = args.product_root.resolve()
    art = src / "frontend" / "src-tauri" / "resources" / "rescoring" / "artifacts"
    data = src / "data"
    goldens = src / "backend" / "tests" / "goldens"
    m5_manifest = src / "backend/services/pipeline/protocols/m5/m5_zn_manifest.json"

    def rel(path: Path) -> str:
        try:
            return str(path.relative_to(src)).replace("\\", "/")
        except ValueError:
            return str(path).replace("\\", "/")

    sources: list[dict] = []
    seen: dict[str, list[str]] = {}

    def mark(pdb: str, why: str) -> None:
        key = pdb.strip().lower()
        if not key or len(key) != 4:
            return
        seen.setdefault(key, [])
        if why not in seen[key]:
            seen[key].append(why)

    def source(path: Path, role: str, n: int) -> None:
        sources.append({
            "path": rel(path),
            "role": role,
            "sha256": _sha256(path),
            "n_ids": n,
        })

    # 1. Split congelado: CV pool + holdout.
    p = art / "split_config.json"
    sc = _load(p)
    n = 0
    for pdb in sc["frozen_test_set"]:
        mark(pdb, "pdbbind_frozen_holdout")
        n += 1
    for fold in sc["folds"]:
        for pdb in fold.get("train_ids", []):
            mark(pdb, "pdbbind_cv_train")
            n += 1
        for pdb in fold.get("val_ids", []):
            mark(pdb, "pdbbind_cv_val")
            n += 1
    source(p, "split congelado XGBoost (train/val/holdout)", n)

    # 2. Auditoria de curacion: todo lo que se evaluo, aceptado o no.
    p = art / "pdbbind_audit_report.json"
    au = _load(p)
    n = 0
    for row in au.get("individual_results", []):
        pid = row.get("pdb_id")
        if pid:
            mark(pid, "pdbbind_curation_evaluated")
            n += 1
    source(p, "curacion PDBBind (752 evaluados)", n)

    # 3. Perfiles M5-Zn y sus checkpoints de benchmark.
    p = m5_manifest
    m5 = _load(p)
    n = 0
    for pid, prof in m5.get("profiles", {}).items():
        mark(pid, "m5_zn_profile_benchmark")
        n += 1
    source(p, "perfiles M5-Zn (seleccion de pesos por diana)", n)

    # 4. Checkpoints de benchmark en data/: seleccionaron pesos y umbrales.
    n = 0
    for cp in sorted(data.glob("benchmark_checkpoint_*.json")):
        stem = cp.stem.replace("benchmark_checkpoint_", "")
        if len(stem) == 4 and stem[0].isdigit():
            mark(stem, "benchmark_checkpoint")
            n += 1
        sources.append({
            "path": rel(cp),
            "role": f"checkpoint de benchmark (diana={stem})",
            "sha256": _sha256(cp),
            "n_ids": 1,
        })

    # 4b. model-manifest.json: sus metricas nombran las dianas held-out con las
    # que se evaluo cada modelo. Una diana usada para REPORTAR una AUC esta
    # expuesta aunque no se entrenara sobre ella. PILOT-0 no leyo esta fuente y
    # por eso dio 3PP0 por EXTERNAL: aparece como `kinase_CDK2_3PP0`.
    p = art / "model-manifest.json"
    if p.is_file():
        mm = _load(p)
        n = 0
        for nombre, mod in (mm.get("models") or {}).items():
            for clave, valor in (mod.get("metrics") or {}).items():
                if not isinstance(valor, dict):
                    continue
                for etiqueta in valor:
                    # etiquetas del tipo `kinase_CDK2_3PP0`, `protease_HIV_1HSG`
                    for trozo in str(etiqueta).split("_"):
                        if len(trozo) == 4 and trozo[0].isdigit():
                            mark(trozo, f"model_manifest_holdout:{nombre}.{clave}")
                            n += 1
        source(p, "model-manifest.json (dianas held-out nombradas en metrics)", n)

    # 5. Goldens: fijan salida esperada, luego son memorizables.
    n = 0
    if goldens.is_dir():
        for g in sorted(goldens.glob("*.json")):
            try:
                blob = io.open(g, encoding="utf-8").read()
            except OSError:
                continue
            for token in ("3dc3", "1gkc", "1o86", "1hsg", "7e2y"):
                if token in blob.lower():
                    mark(token, f"golden:{g.name}")
                    n += 1
    sources.append({"path": "backend/tests/goldens/*.json", "role": "goldens", "sha256": None, "n_ids": n})

    # Dianas cuyo NOMBRE quedo expuesto: cualquier PDB suyo es RELATED.
    related_targets = {
        "CA2": "carbonic anhydrase II - perfil M5-Zn + checkpoint",
        "MMP9": "matrix metalloproteinase 9 - perfil M5-Zn + checkpoint",
        "ACE": "angiotensin converting enzyme - perfil M5-Zn + checkpoint",
        "5HT1A": "calibracion externa BindingDB (7E2Y)",
        "CDK2": "checkpoint de benchmark",
        "ER_ALPHA": "checkpoint de benchmark",
        "FACTOR_XA": "checkpoint de benchmark",
        "HIV_PROTEASE": "checkpoint de benchmark + molchamb LOTO",
        "THROMBIN": "checkpoint de benchmark",
    }

    out = {
        "schema_version": 1,
        "product_root": str(src).replace("\\", "/"),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": "Marcar SEEN/RELATED/EXTERNAL antes de conocer resultados.",
        "seen_pdb_ids": {k: sorted(v) for k, v in sorted(seen.items())},
        "n_seen_pdb_ids": len(seen),
        "related_targets": related_targets,
        "sources_read": sources,
        "caveat": (
            "EXTERNAL significa 'ausente de sources_read'. No cubre exposicion "
            "por preentrenamiento de ESM/ESMFold, ni por PDBBind general fuera "
            "de los 865 refinados, ni similitud de scaffold, que se mide aparte."
        ),
    }
    dest = ROOT / "validation" / "leakage" / "seen_inventory.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    with io.open(dest, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, ensure_ascii=False)
    print(f"SEEN pdb ids: {len(seen)}")
    print(f"fuentes leidas: {len(sources)}")
    print(f"-> {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
