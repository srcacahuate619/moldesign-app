# -*- coding: utf-8 -*-
"""build_pose_union.py — MF-01-UNION: unión materializada de poses existentes.

Entregable 4 de la primera tanda de docs/49 (sección 15): materializar la
unión de las poses EXISTENTES de Ruta C sobre train+val (156 complejos /
3469 poses), SIN re-docking, SIN scoring v0.6 y SIN deduplicar (eso es
MF-11, posterior).

Por cada pose de data/pose_selector_dataset/poses_{train,val}.jsonl se emite:

  - candidato: identidad canónica + vina_score + enlace a provenance
    (provenance_key = clave pid|source|file_stem del sidecar FND-06) +
    geometría materializada:
      * `pdbqt` (bloque MODEL/ENDMDL textual recuperado de la salida del
        generador) con geometry_source="pdbqt", o
      * `geometry` (coordenadas de átomos pesados desde records) con
        geometry_source="_coords", o
      * geometry_source="missing" (pose válida sin geometría recuperable:
        se registra en failures.jsonl y el build continúa).
    Los candidatos NO contienen rmsd ni ningún label de calidad: los labels
    viven en archivos separados (union_labels_*.jsonl) keyed por identidad,
    para que el orden/inclusión de candidatos no pueda depender del rmsd.

  - label: identity + rmsd + campos de calidad históricos (n_heavy,
    n_contacts_4, n_contacts_6, n_clashes, pose_score_variance,
    pose_score_range), en el MISMO orden por identidad.

Identidad canónica: split|pid|source|file_stem|model_idx. Orden de salida:
identidad ascendente (determinista, independiente de rmsd).

Validaciones con FAIL duro (exit 1, nada parcial): colisión de identidad y
pose sin provenance (el sidecar FND-06 es el único enlace autorizado).
La geometría faltante NO falla el build si la pose es válida.

Fuentes de geometría (por source, en orden de preferencia):
  flexible_redock: <repo>/data/pdbbind/vina_redock_work/{pid}/{pid}_out.pdbqt
  molflex:         <repo>/scripts/.work_molflex_v3/{pid}/{file_stem}.pdbqt
  ruta_a:          <repo>/tmp/ruta_a/{pid}/{file_stem}/out.pdbqt
Con --geometry-root DIR se añade un candidato alternativo por source
(árboles reubicados): DIR/{work_molflex_v3|data/pdbbind/vina_redock_work|
tmp/ruta_a}/... (el workdir de molflex vive hoy fuera del repo, en el
backup moldesign-backups/work_molflex_v3).
Fallback final: _coords en <poses>/records/{pid}.json.

El builder SOLO abre poses_train.jsonl y poses_val.jsonl; nunca
poses_test.jsonl (test histórico fuera de alcance, docs/49 §4).

Determinismo: sin marcas de tiempo, orden canónico por identidad, escritura
atómica (temp + os.replace). Dos corridas sobre los mismos insumos
producen bytes idénticos.

Uso:
    python scripts/build_pose_union.py \
        --poses data/pose_selector_dataset \
        --provenance scripts/artifacts_science/FND-06/poses_provenance.jsonl \
        --out-dir scripts/artifacts_science/MF-01-UNION \
        [--geometry-root DIR]
"""

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

POSES_DIR_DEFAULT = PROJECT_ROOT / "data" / "pose_selector_dataset"
PROVENANCE_DEFAULT = (
    PROJECT_ROOT
    / "scripts"
    / "artifacts_science"
    / "FND-06"
    / "poses_provenance.jsonl"
)
OUT_DIR_DEFAULT = (
    PROJECT_ROOT / "scripts" / "artifacts_science" / "MF-01-UNION"
)

SPLITS = ("train", "val")
FUENTES_CANONICAS = ("flexible_redock", "molflex", "ruta_a")

CLAVES_CANDIDATO = [
    "identity",
    "split",
    "pid",
    "source",
    "file_stem",
    "model_idx",
    "vina_score",
    "provenance_key",
    "geometry_source",
    "pdbqt",
    "geometry",
]
CLAVES_LABEL = [
    "identity",
    "rmsd",
    "n_heavy",
    "n_contacts_4",
    "n_contacts_6",
    "n_clashes",
    "pose_score_variance",
    "pose_score_range",
]
CLAVES_FALLA = [
    "identity",
    "split",
    "pid",
    "source",
    "file_stem",
    "model_idx",
    "tipo",
    "detalle",
]


# ───────────────────────── utilidades ───────────────────────────────────────

def _atomic_write(path: Path, texto: str) -> None:
    """Escritura atómica (temp + os.replace), igual que la convención FND-06."""
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(texto)
    os.replace(tmp, path)


def _leer_poses(split: str, poses_dir: Path) -> list[dict]:
    """Lee poses_{split}.jsonl completo (solo train/val; test nunca se abre)."""
    path = poses_dir / f"poses_{split}.jsonl"
    poses: list[dict] = []
    with open(path, encoding="utf-8") as fh:
        for linea in fh:
            linea = linea.strip()
            if not linea:
                continue
            try:
                poses.append(json.loads(linea))
            except json.JSONDecodeError as exc:
                print(f"ERROR: JSON inválido en {path}: {exc}", file=sys.stderr)
                sys.exit(1)
    return poses


def _cargar_sidecar(path: Path) -> dict[str, dict]:
    """Sidecar FND-06 indexado por su clave `key` (pid|source|file_stem).

    FAIL duro si hay claves duplicadas (sidecar inconsistente) o si la clave
    no coincide con pid|source|file_stem del registro.
    """
    sidecar: dict[str, dict] = {}
    with open(path, encoding="utf-8") as fh:
        for linea in fh:
            linea = linea.strip()
            if not linea:
                continue
            try:
                r = json.loads(linea)
            except json.JSONDecodeError as exc:
                print(f"ERROR: JSON inválido en sidecar {path}: {exc}",
                      file=sys.stderr)
                sys.exit(1)
            clave = r.get("key")
            compuesta = f"{r.get('pid')}|{r.get('source')}|{r.get('file_stem')}"
            if clave != compuesta:
                print(
                    f"ERROR: sidecar inconsistente: key={clave!r} != "
                    f"{compuesta!r}",
                    file=sys.stderr,
                )
                sys.exit(1)
            if clave in sidecar:
                print(
                    f"ERROR: sidecar con clave duplicada: {clave}",
                    file=sys.stderr,
                )
                sys.exit(1)
            sidecar[clave] = r
    return sidecar


# ───────────────────────── geometría ────────────────────────────────────────

def _rutas_out(pid: str, source: str, file_stem: str,
               geometry_root: Path | None) -> list[Path]:
    """Candidatos de archivo de salida del generador, en orden de preferencia.

    Primero la ubicación histórica dentro del repo y, si se pasó
    --geometry-root, la ubicación reubicada correspondiente. El layout
    reubicado NO replica el prefijo repo para molflex: el workdir se movió
    como <root>/work_molflex_v3 (backup moldesign-backups), no
    <root>/scripts/.work_molflex_v3.
    """
    if source == "flexible_redock":
        rel_repo = Path("data") / "pdbbind" / "vina_redock_work" / pid / f"{pid}_out.pdbqt"
        rel_mov = rel_repo
    elif source == "molflex":
        rel_repo = Path("scripts") / ".work_molflex_v3" / pid / f"{file_stem}.pdbqt"
        rel_mov = Path("work_molflex_v3") / pid / f"{file_stem}.pdbqt"
    elif source == "ruta_a":
        rel_repo = Path("tmp") / "ruta_a" / pid / file_stem / "out.pdbqt"
        rel_mov = rel_repo
    else:
        return []
    rutas = [PROJECT_ROOT / rel_repo]
    if geometry_root is not None:
        rutas.append(geometry_root / rel_mov)
    return rutas


def _extraer_bloques(texto: str) -> list[str]:
    """Divide un PDBQT de salida en bloques MODEL..ENDMDL (texto verbatim).

    Índice del bloque == model_idx del dataset (misma convención que
    mf.parsear_out_vina: se emite un modelo por ENDMDL con átomos). Si el
    archivo no usa marcadores MODEL/ENDMDL (caso Vina sin multi-modelo), el
    archivo entero se trata como un único bloque (model_idx 0).
    """
    bloques: list[str] = []
    actual: list[str] | None = None
    for linea in texto.splitlines():
        if linea.startswith("MODEL"):
            actual = [linea]
        elif actual is not None:
            actual.append(linea)
            if linea.startswith("ENDMDL"):
                bloques.append("\n".join(actual))
                actual = None
    if actual is not None and any(
        l.startswith(("ATOM", "HETATM")) for l in actual
    ):
        # Archivo truncado sin ENDMDL final: conservamos el texto real tal
        # cual (no se fabrica nada). parsear_out_vina no lo habría contado,
        # así que ningún model_idx del dataset apunta aquí.
        bloques.append("\n".join(actual))
    return bloques


def _coords_desde_record(records_dir: Path, pid: str, source: str,
                         file_stem: str, model_idx: int) -> dict | None:
    """_coords de la pose en records/{pid}.json (fallback de geometría)."""
    rec = records_dir / f"{pid}.json"
    if not rec.is_file():
        return None
    try:
        datos = json.loads(rec.read_text(encoding="utf-8"))
    except Exception:
        return None
    registros = datos.get("registros", {})
    for r in registros.get(f"{pid}|{source}|{file_stem}", []):
        if r.get("model_idx") == model_idx and isinstance(
            r.get("_coords"), dict
        ):
            return r["_coords"]
    return None


def _geometria_de_pose(pose: dict, geometry_root: Path | None,
                       records_dir: Path,
                       cache_bloques: dict) -> tuple[str, dict]:
    """Resuelve la geometría de una pose.

    Devuelve (geometry_source, contenido) donde contenido es:
      - {"pdbqt": <texto del bloque>} si geometry_source == "pdbqt";
      - {"geometry": <dict _coords>} si geometry_source == "_coords";
      - {} si geometry_source == "missing".
    """
    pid = pose["pid"]
    source = pose["source"]
    file_stem = pose["file_stem"]
    model_idx = pose["model_idx"]
    clave_run = (pid, source, file_stem)
    if clave_run not in cache_bloques:
        bloques: list[str] | None = None
        for ruta in _rutas_out(pid, source, file_stem, geometry_root):
            if not ruta.is_file():
                continue
            try:
                texto = ruta.read_text(encoding="utf-8")
            except Exception:
                continue
            bloques = _extraer_bloques(texto)
            break
        cache_bloques[clave_run] = bloques
    bloques = cache_bloques[clave_run]
    if bloques is not None and 0 <= model_idx < len(bloques):
        return "pdbqt", {"pdbqt": bloques[model_idx]}
    coords = _coords_desde_record(
        records_dir, pid, source, file_stem, model_idx
    )
    if coords is not None:
        return "_coords", {"geometry": coords}
    return "missing", {}


# ───────────────────────── validaciones duras ───────────────────────────────

def _validar_identidades(poses: list[dict]) -> None:
    """FAIL duro ante colisiones de identidad o identidad incompleta."""
    colisiones: dict[str, int] = Counter()
    for split, pose in poses:
        try:
            ident = f"{split}|{pose['pid']}|{pose['source']}|" \
                    f"{pose['file_stem']}|{pose['model_idx']}"
        except KeyError as exc:
            print(
                f"ERROR: identidad incompleta (falta {exc.args[0]}) en "
                f"{split}: {pose}",
                file=sys.stderr,
            )
            sys.exit(1)
        colisiones[ident] += 1
    duplicadas = sorted(k for k, v in colisiones.items() if v > 1)
    if duplicadas:
        for ident in duplicadas:
            print(f"ERROR: colisión de identidad: {ident} "
                  f"({colisiones[ident]} poses)", file=sys.stderr)
        print(f"ERROR: {len(duplicadas)} identidades colisionadas. "
              "FAIL duro del build (nada parcial).", file=sys.stderr)
        sys.exit(1)


# ───────────────────────── emisión ──────────────────────────────────────────

def _fila_candidato(ident: str, pose: dict, provenance_key: str,
                    geometry_source: str, contenido: dict) -> dict:
    fila = {
        "identity": ident,
        "split": pose["split"],
        "pid": pose["pid"],
        "source": pose["source"],
        "file_stem": pose["file_stem"],
        "model_idx": pose["model_idx"],
        "vina_score": pose.get("vina_score"),
        "provenance_key": provenance_key,
        "geometry_source": geometry_source,
    }
    if "pdbqt" in contenido:
        fila["pdbqt"] = contenido["pdbqt"]
    elif "geometry" in contenido:
        fila["geometry"] = contenido["geometry"]
    return {k: fila[k] for k in CLAVES_CANDIDATO if k in fila}


def _fila_label(ident: str, pose: dict) -> dict:
    fila = {
        "identity": ident,
        "rmsd": pose.get("rmsd"),
        "n_heavy": pose.get("n_heavy"),
        "n_contacts_4": pose.get("n_contacts_4"),
        "n_contacts_6": pose.get("n_contacts_6"),
        "n_clashes": pose.get("n_clashes"),
        "pose_score_variance": pose.get("pose_score_variance"),
        "pose_score_range": pose.get("pose_score_range"),
    }
    return {k: fila[k] for k in CLAVES_LABEL}


# ───────────────────────── flujo principal ──────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="MF-01-UNION: unión materializada de poses existentes "
        "sobre train/val (entregable 4, docs/49 §15)."
    )
    parser.add_argument("--poses", type=Path, default=POSES_DIR_DEFAULT,
                        help="directorio del dataset pose_selector")
    parser.add_argument("--provenance", type=Path, default=PROVENANCE_DEFAULT,
                        help="sidecar FND-06 poses_provenance.jsonl")
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR_DEFAULT,
                        help="directorio de salida")
    parser.add_argument("--geometry-root", type=Path, default=None,
                        help="raíz opcional con salidas reubicadas de los "
                        "generadores (work_molflex_v3, etc.)")
    args = parser.parse_args(argv)

    # 1) lectura (SOLO train/val; poses_test.jsonl nunca se abre).
    poses: list[tuple[str, dict]] = []
    for split in SPLITS:
        for pose in _leer_poses(split, args.poses):
            pose = dict(pose)
            pose["split"] = split
            poses.append((split, pose))

    # 2) validaciones duras ANTES de escribir nada.
    _validar_identidades(poses)
    sidecar = _cargar_sidecar(args.provenance)

    # 3) join de provenance (FAIL duro si falta) + coherencia de clave.
    sin_provenance: list[dict] = []
    for split, pose in poses:
        clave = f"{pose['pid']}|{pose['source']}|{pose['file_stem']}"
        if clave not in sidecar:
            sin_provenance.append(pose)
    if sin_provenance:
        for pose in sorted(sin_provenance, key=lambda p: (
                p["split"], p["pid"], p["source"], p["file_stem"])):
            print(f"ERROR: pose sin provenance: {pose['split']}|"
                  f"{pose['pid']}|{pose['source']}|{pose['file_stem']}",
                  file=sys.stderr)
        print(f"ERROR: {len(sin_provenance)} poses sin provenance. "
              "FAIL duro del build (nada parcial).", file=sys.stderr)
        sys.exit(1)

    # 4) geometría por pose (la faltante es no-fatal: failures + continue).
    cache_bloques: dict = {}
    fallas: list[dict] = []
    filas_por_split: dict[str, list[dict]] = {s: [] for s in SPLITS}
    labels_por_split: dict[str, list[dict]] = {s: [] for s in SPLITS}
    geo_por_fuente: dict[str, dict[str, int]] = {}
    for split, pose in poses:
        ident = f"{split}|{pose['pid']}|{pose['source']}|" \
                f"{pose['file_stem']}|{pose['model_idx']}"
        clave = f"{pose['pid']}|{pose['source']}|{pose['file_stem']}"
        fuente = pose["source"]
        geo = geo_por_fuente.setdefault(
            fuente, {"pdbqt": 0, "_coords": 0, "missing": 0}
        )
        if not isinstance(pose.get("model_idx"), int) or pose["model_idx"] < 0:
            fallas.append({
                "identity": ident, "split": split, "pid": pose["pid"],
                "source": fuente, "file_stem": pose["file_stem"],
                "model_idx": pose["model_idx"], "tipo": "model_idx_invalido",
                "detalle": "model_idx no es un entero >= 0",
            })
            geo["missing"] += 1
            geometry_source, contenido = "missing", {}
        else:
            geometry_source, contenido = _geometria_de_pose(
                pose, args.geometry_root, args.poses / "records",
                cache_bloques,
            )
            geo[geometry_source] += 1
            if geometry_source == "missing":
                fallas.append({
                    "identity": ident, "split": split, "pid": pose["pid"],
                    "source": fuente, "file_stem": pose["file_stem"],
                    "model_idx": pose["model_idx"],
                    "tipo": "geometria_no_recuperable",
                    "detalle": "sin bloque PDBQT del generador y sin _coords "
                    "en records",
                })
        filas_por_split[split].append(
            _fila_candidato(ident, pose, clave, geometry_source, contenido)
        )
        labels_por_split[split].append(_fila_label(ident, pose))

    # 5) orden canónico: identidad ascendente en candidatos y labels.
    for split in SPLITS:
        filas_por_split[split].sort(key=lambda f: f["identity"])
        labels_por_split[split].sort(key=lambda f: f["identity"])

    # 6) conteos para metrics.
    n_poses = {s: len(filas_por_split[s]) for s in SPLITS}
    n_pids = {s: len({f["pid"] for f in filas_por_split[s]}) for s in SPLITS}
    pids_compartidos = sorted(
        {f["pid"] for f in filas_por_split["train"]}
        & {f["pid"] for f in filas_por_split["val"]}
    )
    runs_usadas = sorted({f["provenance_key"] for s in SPLITS
                          for f in filas_por_split[s]})
    runs_por_fuente: dict[str, int] = Counter()
    vistos: set = set()
    for f in (x for s in SPLITS for x in filas_por_split[s]):
        clave_run = (f["source"], f["provenance_key"])
        if clave_run not in vistos:
            vistos.add(clave_run)
            runs_por_fuente[f["source"]] += 1
    runs_por_fuente = dict(sorted(runs_por_fuente.items()))
    total_geo = {k: sum(f.get(k, 0) for f in geo_por_fuente.values())
                 for k in ("pdbqt", "_coords", "missing")}

    metrics = {
        "experiment_id": "MF-01-UNION",
        "alcance": {
            "splits": "train+val (test histórico fuera de alcance: "
                      "poses_test.jsonl nunca se abre)",
            "n_complejos": sum(n_pids.values()),
            "n_complejos_train": n_pids["train"],
            "n_complejos_val": n_pids["val"],
            "n_poses": sum(n_poses.values()),
            "n_poses_train": n_poses["train"],
            "n_poses_val": n_poses["val"],
            "pids_compartidos_entre_splits": pids_compartidos,
        },
        "identidad": {
            "formato": "split|pid|source|file_stem|model_idx",
            "colisiones": 0,
            "orden_salida": "identity ascendente (independiente de rmsd)",
        },
        "provenance": {
            "sidecar": "scripts/artifacts_science/FND-06/poses_provenance.jsonl",
            "clave": "pid|source|file_stem",
            "runs_en_sidecar": len(sidecar),
            "runs_usadas": len(runs_usadas),
            "runs_esperadas": 447,
            "runs_por_fuente": runs_por_fuente,
            "runs_solo_test": len(sidecar) - len(runs_usadas),
            "poses_sin_provenance": 0,
        },
        "geometria": {
            "resolucion": {
                "flexible_redock": "data/pdbbind/vina_redock_work/{pid}/{pid}_out.pdbqt",
                "molflex": "work_molflex_v3/{pid}/{file_stem}.pdbqt "
                           "(reubicado: moldesign-backups/work_molflex_v3)",
                "ruta_a": "tmp/ruta_a/{pid}/{file_stem}/out.pdbqt",
                "fallback": "records/{pid}.json → _coords",
            },
            "por_pose": {
                "pdbqt": total_geo["pdbqt"],
                "_coords": total_geo["_coords"],
                "missing": total_geo["missing"],
            },
            "por_fuente": {
                f: {
                    "n_poses": sum(v for v in geo_por_fuente[f].values()),
                    **geo_por_fuente[f],
                }
                for f in sorted(geo_por_fuente)
            },
        },
        "separacion_candidatos_labels": (
            "union_candidates_*.jsonl NO contienen rmsd ni labels de "
            "calidad; union_labels_*.jsonl llevan las etiquetas keyed por "
            "identidad, en el mismo orden"
        ),
        "notas": [
            "Sin re-docking, sin scoring v0.6, sin deduplicación (MF-11).",
            "Determinista: dos corridas sobre los mismos insumos producen "
            "bytes idénticos.",
            "PASS OPERACIONAL de este artefacto != gate científico de "
            "MF-01 (permanece NO_GO: MolFlex aportó 0 complejos en "
            "D-MF-HARD; decisión en RS-01).",
        ],
    }

    # 7) escritura atómica de todas las salidas.
    args.out_dir.mkdir(parents=True, exist_ok=True)
    for split in SPLITS:
        _atomic_write(
            args.out_dir / f"union_candidates_{split}.jsonl",
            "\n".join(json.dumps(f, ensure_ascii=False)
                      for f in filas_por_split[split]) + "\n",
        )
        _atomic_write(
            args.out_dir / f"union_labels_{split}.jsonl",
            "\n".join(json.dumps(f, ensure_ascii=False)
                      for f in labels_por_split[split]) + "\n",
        )
    fallas.sort(key=lambda f: (f["identity"], f["tipo"], str(f["detalle"])))
    lineas_fallas = (
        "\n".join(json.dumps(
            {k: f[k] for k in CLAVES_FALLA if k in f},
            ensure_ascii=False,
        ) for f in fallas) + "\n"
        if fallas
        else ""
    )
    _atomic_write(args.out_dir / "failures.jsonl", lineas_fallas)
    _atomic_write(
        args.out_dir / "metrics.json",
        json.dumps(metrics, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
    )

    print(f"MF-01-UNION: {sum(n_poses.values())} poses "
          f"({n_poses['train']} train / {n_poses['val']} val), "
          f"{sum(n_pids.values())} complejos "
          f"({n_pids['train']} train / {n_pids['val']} val)")
    print(f"provenance: {len(runs_usadas)}/447 corridas usadas, "
          f"0 poses sin provenance, 0 colisiones")
    print(f"geometría: pdbqt={total_geo['pdbqt']} "
          f"_coords={total_geo['_coords']} missing={total_geo['missing']}")
    print(f"fallas no fatales: {len(fallas)}")
    print(f"artefactos: {args.out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
