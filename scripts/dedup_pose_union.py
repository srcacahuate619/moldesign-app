# -*- coding: utf-8 -*-
"""dedup_pose_union.py — MF-11 (docs/49 §15, entregable 9): deduplicación
LABEL-BLIND de la unión MF-01-UNION por clustering greedy de RMSD
pocket-frame pose-vs-pose.

REGLAS DURAS (preregistradas en DESIGN.md ANTES de evaluar):

1. Clustering LABEL-BLIND. La deduplicación usa SOLO geometría pose-vs-pose:
   coordenadas absolutas de los PDBQT embebidos en el marco del receptor
   fijo (la MISMA definición de marco que molflex.rmsd_pose_pocket, extendida
   por pares). Los labels (union_labels_*.jsonl) se leen EXCLUSIVAMENTE en la
   fase de evaluación (función evaluar_preservacion), NUNCA dentro del
   clustering. Las funciones de clustering no reciben labels por contrato.

2. Regla única: clustering greedy por identidad ascendente; cada pose se une
   al PRIMER cluster existente (en orden de creación) cuyo REPRESENTANTE esté
   a RMSD pose-vs-pose <= 2.0 Å; si no, abre cluster nuevo. El representante
   de cada cluster = la PRIMERA pose en orden de identidad (label-blind).

3. Métrica pose-vs-pose: átomos pesados (elemento PDBQT no H), matching 1:1
   por serial, SIN alineamiento (traslación/rotación de la pose NO se
   compensan). Caveat heredado de rmsd_pose_pocket: matching 1:1 sin simetría
   química; la métrica simétrica es trabajo futuro.

4. Cero test histórico y cero D-RC-CONFIRM: este script NUNCA abre
   poses_test.jsonl. La verificación de no intersección usa solo metadatos
   sellados de split (manifest del dataset) y la denylist FND-05, ambos con
   verificación de integridad SHA-256.

Determinismo: sin timestamps ni aleatoriedad en las salidas; dos corridas
producen bytes idénticos. Solo biblioteca estándar.

Uso:
  python scripts/dedup_pose_union.py --union-dir <dir> --out-dir <dir>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

UNION_DIR_DEFAULT = PROJECT_ROOT / "scripts" / "artifacts_science" / "MF-01-UNION"
OUT_DIR_DEFAULT = PROJECT_ROOT / "scripts" / "artifacts_science" / "MF-11"
MANIFEST_DATASET = PROJECT_ROOT / "data" / "pose_selector_dataset" / "manifest.json"
DENYLIST_JSON = (
    PROJECT_ROOT / "scripts" / "artifacts_science" / "FND-05" / "denylist_pids.json"
)

UMBRAL_RMSD = 2.0  # Å — preregistrado en DESIGN.md
UMBRAL_COBERTURA = 2.0  # Å — cobertura de oráculo (min rmsd <= umbral)

SPLITS = ("train", "val")


def parsear_atomos_pesados(pdbqt_texto: str):
    """Parsea ATOM/HETATM de un PDBQT embebido.

    Devuelve (coords, firma) donde coords = {serial: (x, y, z)} de átomos
    pesados (elemento no hidrógeno, columnas PDBQT 77-78) y firma = lista de
    (serial, elemento) pesados en orden de aparición.
    """
    coords: dict = {}
    firma: list = []
    for linea in pdbqt_texto.splitlines():
        if not (linea.startswith("ATOM") or linea.startswith("HETATM")):
            continue
        try:
            serial = int(linea[6:11])
            x = float(linea[30:38])
            y = float(linea[38:46])
            z = float(linea[46:54])
        except (ValueError, IndexError):
            continue
        elemento = linea[76:78].strip()
        if elemento.startswith("H"):
            continue
        coords[serial] = (x, y, z)
        firma.append((serial, elemento))
    return coords, firma


def rmsd_pocket_pose_vs_pose(coords_a: dict, coords_b: dict):
    """Extensión pairwise de molflex.rmsd_pose_pocket.

    RMSD de átomos pesados EN EL MARCO DEL POCKET (coordenadas absolutas del
    receptor fijo), SIN alineamiento: compara las coords de dos poses 1:1 por
    serial sobre los átomos comunes. None si no hay átomos comparables.
    """
    comunes = [s for s in coords_a if s in coords_b]
    if not comunes:
        return None
    suma = 0.0
    for serial in comunes:
        xa, ya, za = coords_a[serial]
        xb, yb, zb = coords_b[serial]
        suma += (xa - xb) ** 2 + (ya - yb) ** 2 + (za - zb) ** 2
    return (suma / len(comunes)) ** 0.5


def clustering_greedy(identidades: list, coords_por_identidad: dict) -> list:
    """Regla preregistrada (label-blind): greedy, identidad ascendente,
    umbral 2.0 Å contra el REPRESENTANTE de cada cluster; representante =
    primera pose. Devuelve lista de clusters (listas de identidades).
    """
    clusters: list = []
    for ident in identidades:
        coords = coords_por_identidad.get(ident, {})
        destino = None
        for cluster in clusters:
            r = rmsd_pocket_pose_vs_pose(coords_por_identidad.get(cluster[0], {}), coords)
            if r is not None and r <= UMBRAL_RMSD:
                destino = cluster
                break
        if destino is None:
            clusters.append([ident])
        else:
            destino.append(ident)
    return clusters


def percentil_ordenado(valores: list, p: int):
    """Percentil por rango más cercano (ceil(p*n/100)-1) sobre lista ordenada."""
    n = len(valores)
    if n == 0:
        return None
    idx = -(-p * n // 100) - 1
    return valores[max(0, min(n - 1, idx))]


def sha256_archivo(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for bloque in iter(lambda: fh.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def sha256_texto(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def verificar_exclusiones(union_pids: set, errores: list) -> dict:
    """Verifica que los pids de la unión no intersectan test histórico ni la
    denylist D-RC-CONFIRM. Lee SOLO metadatos sellados (manifest del dataset,
    denylist FND-05); nunca abre poses_test.jsonl ni candidates de cohorte."""
    detalle = {
        "test_historico": {},
        "denylist_fnd05": {},
    }

    man = json.loads(MANIFEST_DATASET.read_text(encoding="utf-8"))
    test_pids = [str(p) for p in man.get("test_pids", [])]
    integro_test = sha256_texto(json.dumps(test_pids)) == str(
        man.get("test_pids_sha256", "")
    ).strip()
    if not integro_test:
        errores.append(
            "test_pids del manifest del dataset NO coincide con su sha256 sellado"
        )
    detalle["test_historico"] = {
        "n_test_manifest": len(test_pids),
        "n_union": len(union_pids),
        "interseccion": sorted(union_pids & set(test_pids)),
        "test_pids_sha256_ok": integro_test,
        "fuente": "data/pose_selector_dataset/manifest.json (metadatos de split; "
                  "poses_test.jsonl NUNCA se abre)",
    }

    deny = json.loads(DENYLIST_JSON.read_text(encoding="utf-8"))
    candidatos = DENYLIST_JSON.parent / "candidates.jsonl"
    integro_deny = (
        candidatos.is_file()
        and sha256_archivo(candidatos).upper()
        == str(deny.get("sha256_candidates", "")).strip().upper()
    )
    if not integro_deny:
        errores.append("cohorte cambiada, denylist obsoleto (FND-05)")
    denylist_pids = {str(p) for p in deny.get("pids", [])}
    detalle["denylist_fnd05"] = {
        "n_denylist": len(denylist_pids),
        "n_union": len(union_pids),
        "interseccion": sorted(union_pids & denylist_pids),
        "candidates_sha256_ok": integro_deny,
        "fuente": "scripts/artifacts_science/FND-05/denylist_pids.json "
                  "(cuarentena D-RC-CONFIRM)",
    }
    return detalle


def cargar_union(union_dir: Path, split: str):
    """Carga candidatos y labels del split; valida identidades 1:1 (duros)."""
    cand_path = union_dir / f"union_candidates_{split}.jsonl"
    lab_path = union_dir / f"union_labels_{split}.jsonl"

    candidatos: list = []
    for linea in cand_path.read_text(encoding="utf-8").splitlines():
        if linea.strip():
            candidatos.append(json.loads(linea))
    labels: dict = {}
    for linea in lab_path.read_text(encoding="utf-8").splitlines():
        if linea.strip():
            reg = json.loads(linea)
            ident = reg["identity"]
            if ident in labels:
                raise SystemExit(
                    f"ERROR: identidad duplicada en union_labels_{split}: {ident}"
                )
            labels[ident] = reg

    ids_cand = [c["identity"] for c in candidatos]
    if len(set(ids_cand)) != len(ids_cand):
        raise SystemExit(f"ERROR: identidad duplicada en union_candidates_{split}")
    if set(ids_cand) != set(labels):
        raise SystemExit(
            f"ERROR: identidades de candidatos y labels no coinciden 1:1 en {split}"
        )
    return candidatos, labels


def deduplicar_split(candidatos: list, failures: list, split: str):
    """Clustering label-blind por complejo. NO recibe labels.

    Devuelve (clusters_por_pid, reps_por_pid, fallos_pid).
    """
    por_pid: dict = {}
    coords_por_identidad: dict = {}
    firma_por_identidad: dict = {}
    for cand in candidatos:
        ident = cand["identity"]
        pid = cand["pid"]
        por_pid.setdefault(pid, []).append(ident)
        coords, firma = parsear_atomos_pesados(cand.get("pdbqt", ""))
        coords_por_identidad[ident] = coords
        firma_por_identidad[ident] = firma
        if not coords:
            failures.append({
                "split": split,
                "pid": pid,
                "identity": ident,
                "tipo": "sin_coordenadas_parseables",
                "detalle": "PDBQT sin ATOM/HETATM parseables",
            })

    clusters_por_pid: dict = {}
    fallos_pid: dict = {}
    for pid in sorted(por_pid):
        identidades = sorted(por_pid[pid])
        firmas = {tuple(firma_por_identidad[i]) for i in identidades}
        if len(firmas) > 1:
            fallos_pid[pid] = {
                "n_identidades": len(identidades),
                "n_firmas": len(firmas),
            }
            for ident in identidades:
                failures.append({
                    "split": split,
                    "pid": pid,
                    "identity": ident,
                    "tipo": "firma_atomica_heterogenea",
                    "detalle": "el complejo tiene poses con distinta secuencia "
                               "serial/elemento; el RMSD usa la intersección de seriales",
                })
        clusters_por_pid[pid] = clustering_greedy(identidades, coords_por_identidad)
    reps_por_pid = {pid: [cl[0] for cl in clus] for pid, clus in clusters_por_pid.items()}
    return clusters_por_pid, reps_por_pid, fallos_pid


def evaluar_preservacion(clusters_por_pid: dict, candidatos_por_identidad: dict,
                         labels: dict, split: str):
    """Fase de EVALUACIÓN (única que lee labels). NO participa en membresía.

    Devuelve filas de labels dedup y métricas de cobertura.
    """
    filas_labels: list = []
    perdidos: list = []
    detalle_perdidos: dict = {}
    n_antes = 0
    n_despues = 0
    cubiertos_antes = 0
    cubiertos_despues = 0
    n_complejos = 0
    por_fuente_antes: dict = {}
    por_fuente_despues: dict = {}
    tamanos: list = []

    for pid in sorted(clusters_por_pid):
        n_complejos += 1
        clusters = clusters_por_pid[pid]
        ids_complejo = [ident for cl in clusters for ident in cl]
        rmsds_complejo = [float(labels[i]["rmsd"]) for i in ids_complejo]
        n_antes += len(ids_complejo)
        n_despues += len(clusters)
        cubierto_antes = min(rmsds_complejo) <= UMBRAL_COBERTURA
        reps = [cl[0] for cl in clusters]
        cubierto_despues = min(float(labels[r]["rmsd"]) for r in reps) <= UMBRAL_COBERTURA
        cubiertos_antes += 1 if cubierto_antes else 0
        cubiertos_despues += 1 if cubierto_despues else 0
        if cubierto_antes and not cubierto_despues:
            clave = f"{split}|{pid}"
            perdidos.append(clave)
            mejor = min(ids_complejo, key=lambda i: (float(labels[i]["rmsd"]), i))
            detalle_perdidos[clave] = {
                "mejor_pose": mejor,
                "mejor_pose_rmsd": labels[mejor]["rmsd"],
                "mejor_pose_es_representante": mejor in reps,
                "min_rmsd_representantes": round(
                    min(float(labels[r]["rmsd"]) for r in reps), 3),
                "n_antes": len(ids_complejo),
                "n_despues": len(clusters),
            }

        for ident in ids_complejo:
            fuente = candidatos_por_identidad[ident]["source"]
            por_fuente_antes[fuente] = por_fuente_antes.get(fuente, 0) + 1
        for ident in reps:
            fuente = candidatos_por_identidad[ident]["source"]
            por_fuente_despues[fuente] = por_fuente_despues.get(fuente, 0) + 1

        for idx, cluster in enumerate(clusters):
            tamanos.append(len(cluster))
            rep = cluster[0]
            fila = dict(labels[rep])
            fila["pid"] = pid
            fila["cluster_id"] = idx
            fila["cluster_size"] = len(cluster)
            mejor = min(cluster, key=lambda i: (float(labels[i]["rmsd"]), i))
            if mejor != rep and float(labels[mejor]["rmsd"]) < float(labels[rep]["rmsd"]):
                fila["cluster_best_rmsd"] = labels[mejor]["rmsd"]
                fila["cluster_best_identity"] = mejor
            filas_labels.append(fila)

    tamanos_ordenados = sorted(tamanos)
    resumen = {
        "n_antes": n_antes,
        "n_despues": n_despues,
        "reduccion_pct": round(100.0 * (1 - n_despues / n_antes), 2) if n_antes else 0.0,
        "n_complejos": n_complejos,
        "cubiertos_antes": cubiertos_antes,
        "cubiertos_despues": cubiertos_despues,
        "cobertura_antes": round(cubiertos_antes / n_complejos, 4) if n_complejos else 0.0,
        "cobertura_despues": round(cubiertos_despues / n_complejos, 4) if n_complejos else 0.0,
        "complejos_perdidos": perdidos,
        "n_complejos_perdidos": len(perdidos),
        "detalle_complejos_perdidos": detalle_perdidos,
        "por_fuente": {
            fuente: {
                "n_antes": por_fuente_antes.get(fuente, 0),
                "n_despues": por_fuente_despues.get(fuente, 0),
                "pct_supervivencia": round(
                    100.0 * por_fuente_despues.get(fuente, 0) / por_fuente_antes[fuente], 2
                )
                if por_fuente_antes.get(fuente) else 0.0,
            }
            for fuente in sorted(por_fuente_antes)
        },
        "tamanos_cluster": {
            "P50": percentil_ordenado(tamanos_ordenados, 50),
            "P90": percentil_ordenado(tamanos_ordenados, 90),
            "max": tamanos_ordenados[-1] if tamanos_ordenados else 0,
            "media": round(sum(tamanos_ordenados) / len(tamanos_ordenados), 2)
            if tamanos_ordenados else 0.0,
        },
    }
    return filas_labels, resumen


def escribir_jsonl(path: Path, filas: list):
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        for fila in filas:
            fh.write(json.dumps(fila, ensure_ascii=False) + "\n")


def escribir_json(path: Path, obj):
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(obj, ensure_ascii=False, indent=2) + "\n")


def correr(union_dir: Path, out_dir: Path) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    failures: list = []
    errores: list = []

    union_pids: set = set()
    filas_cand_dedup: dict = {}
    filas_labels_dedup: dict = {}
    resumenes: dict = {}
    filas_per_complex: list = []
    clusters_por_split: dict = {}

    for split in SPLITS:
        candidatos, labels = cargar_union(union_dir, split)
        for cand in candidatos:
            union_pids.add(str(cand["pid"]))

        clusters_por_pid, reps_por_pid, _fallos_pid = deduplicar_split(
            candidatos, failures, split
        )
        clusters_por_split[split] = clusters_por_pid
        candidatos_por_identidad = {c["identity"]: c for c in candidatos}

        reps_ordenados = sorted(
            (ident for ident in candidatos_por_identidad
             if ident in {r for reps in reps_por_pid.values() for r in reps})
        )
        filas_cand_dedup[split] = [dict(candidatos_por_identidad[i]) for i in reps_ordenados]

        filas_labels, resumen = evaluar_preservacion(
            clusters_por_pid, candidatos_por_identidad, labels, split
        )
        filas_labels_dedup[split] = sorted(filas_labels, key=lambda f: f["identity"])
        resumenes[split] = resumen

        for pid in sorted(clusters_por_pid):
            clusters = clusters_por_pid[pid]
            ids_complejo = [ident for cl in clusters for ident in cl]
            cubierto_antes = min(float(labels[i]["rmsd"]) for i in ids_complejo) <= UMBRAL_COBERTURA
            reps = [cl[0] for cl in clusters]
            cubierto_despues = min(float(labels[r]["rmsd"]) for r in reps) <= UMBRAL_COBERTURA
            filas_per_complex.append({
                "split": split,
                "pid": pid,
                "n_antes": len(ids_complejo),
                "n_despues": len(clusters),
                "coverage_antes": cubierto_antes,
                "coverage_despues": cubierto_despues,
                "cluster_count": len(clusters),
            })

    exclusiones = verificar_exclusiones(union_pids, errores)
    if errores:
        for err in errores:
            print(f"ERROR: {err}", file=sys.stderr)
        return 1
    if any(union_pids & set(exclusiones["test_historico"]["interseccion"])):
        print("ERROR: intersección con test histórico", file=sys.stderr)
        return 1
    if any(union_pids & set(exclusiones["denylist_fnd05"]["interseccion"])):
        print("ERROR: intersección con denylist D-RC-CONFIRM", file=sys.stderr)
        return 1

    def fusionar(clave):
        acc: dict = {}
        for split in SPLITS:
            for fuente, detalle in resumenes[split][clave].items():
                sub = acc.setdefault(fuente, {"n_antes": 0, "n_despues": 0})
                sub["n_antes"] += detalle["n_antes"]
                sub["n_despues"] += detalle["n_despues"]
        for fuente, sub in acc.items():
            sub["pct_supervivencia"] = round(100.0 * sub["n_despues"] / sub["n_antes"], 2) \
                if sub["n_antes"] else 0.0
        return acc

    global_n_antes = sum(r["n_antes"] for r in resumenes.values())
    global_n_despues = sum(r["n_despues"] for r in resumenes.values())
    global_complejos = sum(r["n_complejos"] for r in resumenes.values())
    global_cub_antes = sum(r["cubiertos_antes"] for r in resumenes.values())
    global_cub_despues = sum(r["cubiertos_despues"] for r in resumenes.values())
    global_tamanos: list = []
    for split in SPLITS:
        for cl in clusters_por_split[split].values():
            global_tamanos.extend(len(c) for c in cl)
    global_tamanos.sort()

    metrics = {
        "experimento": "MF-11",
        "insumos": {
            "union": "scripts/artifacts_science/MF-01-UNION (solo lectura, sellado)",
            "regla_predefinida": {
                "metrica": "RMSD pocket-frame pose-vs-pose (heavy atoms, matching 1:1 "
                           "por serial, sin alineamiento; misma definición de marco que "
                           "molflex.rmsd_pose_pocket extendida por pares)",
                "umbral": UMBRAL_RMSD,
                "algoritmo": "clustering greedy por identidad ascendente; la pose se une "
                             "al primer cluster cuyo representante está a RMSD <= umbral",
                "representante": "primera pose del cluster en orden de identidad (label-blind)",
                "caveat": "matching 1:1 sin simetría química (heredado de rmsd_pose_pocket); "
                          "la métrica simétrica es trabajo futuro",
            },
            "separacion_oraculo": "los labels solo se leen en la fase de evaluación "
                                  "(evaluar_preservacion); el clustering no los recibe",
        },
        "por_split": resumenes,
        "global": {
            "n_antes": global_n_antes,
            "n_despues": global_n_despues,
            "reduccion_pct": round(100.0 * (1 - global_n_despues / global_n_antes), 2)
            if global_n_antes else 0.0,
            "n_complejos": global_complejos,
            "cubiertos_antes": global_cub_antes,
            "cubiertos_despues": global_cub_despues,
            "cobertura_antes": round(global_cub_antes / global_complejos, 4)
            if global_complejos else 0.0,
            "cobertura_despues": round(global_cub_despues / global_complejos, 4)
            if global_complejos else 0.0,
            "complejos_perdidos": [
                p for split in SPLITS for p in resumenes[split]["complejos_perdidos"]
            ],
            "n_complejos_perdidos": sum(
                r["n_complejos_perdidos"] for r in resumenes.values()
            ),
            "detalle_complejos_perdidos": {
                k: v for split in SPLITS
                for k, v in resumenes[split]["detalle_complejos_perdidos"].items()
            },
            "por_fuente": fusionar("por_fuente"),
            "tamanos_cluster": {
                "P50": percentil_ordenado(global_tamanos, 50),
                "P90": percentil_ordenado(global_tamanos, 90),
                "max": global_tamanos[-1] if global_tamanos else 0,
                "media": round(sum(global_tamanos) / len(global_tamanos), 2)
                if global_tamanos else 0.0,
            },
        },
        "exclusiones": exclusiones,
        "label_blind": {
            "clustering": "no lee labels (verificado por contrato y por test sintético "
                          "scripts/test_dedup_pose_union.py)",
            "cobertura": "el oráculo (rmsd cristalográfico de union_labels_*) se usa "
                         "EXCLUSIVAMENTE para evaluar la preservación DESPUÉS de deduplicar",
        },
        "determinismo": "salidas sin timestamps ni aleatoriedad; dos corridas producen "
                        "bytes idénticos (verificación en DESIGN.md)",
    }

    for split in SPLITS:
        escribir_jsonl(out_dir / f"dedup_candidates_{split}.jsonl", filas_cand_dedup[split])
        escribir_jsonl(out_dir / f"dedup_labels_{split}.jsonl", filas_labels_dedup[split])
    escribir_jsonl(out_dir / "per_complex.jsonl", sorted(
        filas_per_complex, key=lambda f: (f["split"], f["pid"])))
    escribir_jsonl(out_dir / "failures.jsonl", failures)
    escribir_json(out_dir / "metrics.json", metrics)

    for split in SPLITS:
        r = resumenes[split]
        print(f"[{split}] n_antes={r['n_antes']} n_despues={r['n_despues']} "
              f"reduccion={r['reduccion_pct']}% cubiertos {r['cubiertos_antes']}->"
              f"{r['cubiertos_despues']}/{r['n_complejos']} perdidos={r['n_complejos_perdidos']}")
    print(f"[global] n_antes={global_n_antes} n_despues={global_n_despues} "
          f"reduccion={metrics['global']['reduccion_pct']}% perdidos="
          f"{metrics['global']['n_complejos_perdidos']}")
    print(f"[exclusiones] test={len(exclusiones['test_historico']['interseccion'])} "
          f"denylist={len(exclusiones['denylist_fnd05']['interseccion'])}")
    print(f"[failures] {len(failures)}")
    return 0


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    parser = argparse.ArgumentParser(
        description="MF-11: deduplicación label-blind de la unión MF-01-UNION "
                    "por clustering greedy de RMSD pocket-frame pose-vs-pose.")
    parser.add_argument("--union-dir", type=Path, default=UNION_DIR_DEFAULT,
                        help="directorio de la unión materializada (default: %(default)s)")
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR_DEFAULT,
                        help="directorio de salida del experimento MF-11 (default: %(default)s)")
    args = parser.parse_args(argv)
    return correr(Path(args.union_dir), Path(args.out_dir))


if __name__ == "__main__":
    sys.exit(main())
