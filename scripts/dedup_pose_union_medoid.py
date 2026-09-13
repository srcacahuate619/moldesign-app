# -*- coding: utf-8 -*-
"""dedup_pose_union_medoid.py — MF-11-R1 (docs/49 §15, entregable 9):
deduplicación LABEL-BLIND de la unión MF-01-UNION (SOLO train) por clustering
greedy de RMSD pocket-frame con DIÁMETRO controlado, representante primario =
MEDOID GEOMÉTRICO. Recupera el contrato original autorizado por el maintainer
que MF-11 desvió (D2: identity-first).

REGLAS DURAS (preregistradas en DESIGN.md ANTES de evaluar):

1. Inputs: SOLO train. union_candidates_train.jsonl + union_labels_train.jsonl
   (116 complejos / 2739 poses). Este script NUNCA abre los archivos val de
   la unión, ni poses_test.jsonl, ni la cohorte de denylist.

2. Métrica pose-vs-pose: átomos pesados (elemento PDBQT no H), matching 1:1
   por serial, SIN alineamiento — extensión por pares de molflex.rmsd_pose_pocket
   (misma definición de marco: coordenadas absolutas del receptor fijo;
   traslación/rotación de la pose NO se compensan). Caveat heredado: matching
   1:1 sin simetría química.

3. Clustering con DIÁMETRO controlado (regla de admisión exacta): greedy
   determinista por identidad ascendente. Una pose entra al PRIMER cluster
   existente (en orden de creación) si su RMSD a TODOS los miembros del
   cluster es <= U (garantía: todo par de miembros del cluster está a <= U).
   Si ningún cluster es compatible, abre cluster nuevo. Umbrales
   preregistrados: 0.5, 0.75, 1.0, 1.5, 2.0 Å (los 5 en una sola pasada).

4. Representante primario = MEDOID GEOMÉTRICO: miembro del cluster que
   minimiza la suma de RMSDs a los demás miembros; empate por identidad
   ascendente. Label-blind (solo geometría; nunca usa labels).

5. Selección del umbral (preregistrada): el MAYOR umbral que cumpla las tres
   condiciones: (a) CERO pérdidas de cobertura de oráculo (todo complejo
   cubierto antes — min rmsd <= 2.0 Å — sigue cubierto con el medoid como
   representante), (b) degradación mediana de min-RMSD <= 0.1 Å (mediana
   sobre los 116 complejos de (min rmsd de medoids − mejor rmsd antes)),
   (c) reducción de candidatos >= 10%. Si ninguno cumple: NO_GO con la tabla
   completa (sin elegir a dedo).

6. Ablation SECUNDARIA (NO primaria): representante = mejor vina_score
   (label-blind). Solo se reporta en metrics.json, marcada explícitamente
   como no primaria y con la nota de que mezcla deduplicación con una señal
   que RS-01 evaluará después (puede favorecer fuentes/configuraciones de
   Vina). El clustering NO cambia.

7. Separación de oráculo: union_labels_train.jsonl se lee EXCLUSIVAMENTE en
   la fase de evaluación (evaluar_umbral); la admisión de poses y la elección
   del representante NUNCA usan labels.

8. Sidecar de membresía del umbral elegido: cluster_members_train_{U}.jsonl,
   un registro por cluster (cluster_key, representative_identity = medoid,
   member_identities/member_sources/member_provenance_keys por identidad
   ascendente, cluster_size, max_pairwise_rmsd), para auditar qué poses
   fueron descartadas sin reejecutar el algoritmo. Además cuantifica los
   empates del medoid (bloque empates_medoid de metrics.json).

Determinismo: sin timestamps ni aleatoriedad en las salidas; dos corridas
producen bytes idénticos. Solo biblioteca estándar (RDKit no requerido: la
métrica es matching 1:1 por serial, sin operaciones químicas).

Uso:
  python scripts/dedup_pose_union_medoid.py --union-dir <dir> --out-dir <dir>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

UNION_DIR_DEFAULT = PROJECT_ROOT / "scripts" / "artifacts_science" / "MF-01-UNION"
OUT_DIR_DEFAULT = PROJECT_ROOT / "scripts" / "artifacts_science" / "MF-11-R1"
MANIFEST_DATASET = PROJECT_ROOT / "data" / "pose_selector_dataset" / "manifest.json"
DENYLIST_JSON = (
    PROJECT_ROOT / "scripts" / "artifacts_science" / "FND-05" / "denylist_pids.json"
)

UMBRALES = (0.5, 0.75, 1.0, 1.5, 2.0)  # Å — preregistrados en DESIGN.md
UMBRAL_COBERTURA = 2.0  # Å — cobertura de oráculo (min rmsd <= umbral)
SPLIT_UNICO = "train"  # MF-11-R1 es SOLO train (excluye la val de MF-11, D1)

ETIQUETA_UMBRAL = {u: str(u) for u in UMBRALES}  # "0.5" ... "2.0"


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


def matriz_distancias(identidades: list, coords_por_identidad: dict) -> dict:
    """Distancia pose-vs-pose para todo par (i < j) del complejo, keyed por
    (identidad_menor, identidad_mayor). Pares sin átomos comunes = inf."""
    dmat: dict = {}
    for i, a in enumerate(identidades):
        ca = coords_por_identidad.get(a, {})
        for b in identidades[i + 1:]:
            r = rmsd_pocket_pose_vs_pose(ca, coords_por_identidad.get(b, {}))
            dmat[(a, b)] = float("inf") if r is None else r
    return dmat


def clustering_diametro(identidades: list, dmat: dict, umbral: float) -> list:
    """Regla de admisión por DIÁMETRO (preregistrada): greedy determinista por
    identidad ascendente; la pose entra al PRIMER cluster existente (orden de
    creación) cuya distancia a TODOS los miembros es <= umbral; si ninguno es
    compatible, abre cluster nuevo.

    Garantía del diámetro: como cada miembro fue admitido siendo <= umbral de
    todos los previos, todo par de miembros de un cluster está a <= umbral.
    """
    clusters: list = []
    for ident in identidades:
        destino = None
        for cluster in clusters:
            if all(dmat[(min(ident, m), max(ident, m))] <= umbral for m in cluster):
                destino = cluster
                break
        if destino is None:
            clusters.append([ident])
        else:
            destino.append(ident)
    return clusters


def medoid_detalle(cluster: list, dmat: dict):
    """(medoid, empatados): medoid = miembro del cluster que minimiza la suma
    de RMSDs a los demás; empatados = miembros con ESA suma mínima exacta
    (>= 1 miembro). El desempate por identidad ascendente elige el primero de
    la lista ordenada. Label-blind (solo geometría; nunca usa labels)."""
    sumas: dict = {}
    for m in cluster:
        sumas[m] = sum(dmat[(min(m, o), max(m, o))] for o in cluster if o != m)
    suma_min = min(sumas.values())
    empatados = sorted(m for m, s in sumas.items() if s == suma_min)
    return empatados[0], empatados


def medoid_geometrico(cluster: list, dmat: dict) -> str:
    """MEDOID GEOMÉTRICO: miembro que minimiza la suma de RMSDs a los demás;
    empate por identidad ascendente. Label-blind (solo geometría)."""
    return medoid_detalle(cluster, dmat)[0]


def construir_sidecar_y_empates(pid_orden: list, clusters_por_pid: dict,
                                candidatos_por_identidad: dict,
                                dmat_por_pid: dict, umbral: float):
    """Sidecar de membresía del umbral elegido + cuantificación de empates.

    Un registro por cluster (orden: pid ascendente, cluster en orden de
    creación): cluster_key, representante (medoid), miembros por identidad
    ascendente con fuentes y provenance_keys, tamaño y diámetro máximo.
    Cuantifica además: clusters no-singleton, empates de medoid (2+ miembros
    con la MISMA suma exacta, resueltos por identidad), empates cross-source
    (los empatados mezclan fuentes) y fuente ganadora en esos empates.
    """
    filas: list = []
    n_no_singleton = 0
    n_empates = 0
    n_empates_cross = 0
    fuente_elegida: dict = {}
    for pid in pid_orden:
        dmat = dmat_por_pid[pid]
        for idx, cluster in enumerate(clusters_por_pid[pid]):
            medoid, empatados = medoid_detalle(cluster, dmat)
            miembros = sorted(cluster)
            pares = [
                dmat[(min(a, b), max(a, b))]
                for i, a in enumerate(miembros) for b in miembros[i + 1:]
            ]
            filas.append({
                "cluster_key": f"{SPLIT_UNICO}|{pid}|{umbral}|{idx}",
                "representative_identity": medoid,
                "member_identities": miembros,
                "member_sources": [candidatos_por_identidad[m]["source"] for m in miembros],
                "member_provenance_keys": [
                    candidatos_por_identidad[m].get("provenance_key", "") for m in miembros
                ],
                "cluster_size": len(miembros),
                "max_pairwise_rmsd": round(max(pares), 4) if pares else 0.0,
            })
            if len(miembros) >= 2:
                n_no_singleton += 1
            if len(empatados) >= 2:
                n_empates += 1
                fuentes_empatados = {candidatos_por_identidad[m]["source"] for m in empatados}
                if len(fuentes_empatados) > 1:
                    n_empates_cross += 1
                    fuente_ganadora = candidatos_por_identidad[medoid]["source"]
                    fuente_elegida[fuente_ganadora] = fuente_elegida.get(fuente_ganadora, 0) + 1
    empates_resumen = {
        "umbral": umbral,
        "definicion_empate": "2+ miembros con la MISMA suma exacta de distancias "
                             "a los demas; el desempate por identidad ascendente "
                             "decidio al representante",
        "n_clusters_no_singleton": n_no_singleton,
        "n_empates_medoid": n_empates,
        "n_empates_cross_source": n_empates_cross,
        "fuente_elegida_en_empates": dict(sorted(fuente_elegida.items())),
        "nota": "los empates cross-source son la unica via por la que el desempate "
                "por identidad puede introducir preferencia de fuente (caveat "
                "cuantificado para RS-01)",
    }
    return filas, empates_resumen


def rep_mejor_vina(cluster: list, candidatos_por_identidad: dict) -> str:
    """Ablation SECUNDARIA: representante = mejor (menor) vina_score; empate
    por identidad ascendente. Label-blind (vina_score vive en el candidato,
    no es un label cristalográfico)."""
    return min(cluster, key=lambda i: (candidatos_por_identidad[i]["vina_score"], i))


def mediana(valores: list):
    """Mediana clásica (promedio de los dos centrales si n par)."""
    ordenados = sorted(valores)
    n = len(ordenados)
    if n == 0:
        return None
    mitad = n // 2
    if n % 2:
        return ordenados[mitad]
    return (ordenados[mitad - 1] + ordenados[mitad]) / 2


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
    """Verifica que los pids train de la unión no intersectan test histórico ni
    la denylist D-RC-CONFIRM. Lee SOLO metadatos sellados (manifest del dataset,
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


def cargar_union_train(union_dir: Path):
    """Carga SOLO train: candidatos y labels; valida identidades 1:1 (duro)."""
    cand_path = union_dir / "union_candidates_train.jsonl"
    lab_path = union_dir / "union_labels_train.jsonl"

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
                    f"ERROR: identidad duplicada en union_labels_train: {ident}"
                )
            labels[ident] = reg

    ids_cand = [c["identity"] for c in candidatos]
    if len(set(ids_cand)) != len(ids_cand):
        raise SystemExit("ERROR: identidad duplicada en union_candidates_train")
    if set(ids_cand) != set(labels):
        raise SystemExit(
            "ERROR: identidades de candidatos y labels no coinciden 1:1"
        )
    return candidatos, labels


def agrupar_por_complejo(candidatos: list, failures: list):
    """Parsea geometría, arma la matriz de distancias por complejo y corre el
    clustering de diámetro para los 5 umbrales en una sola pasada. NO recibe
    labels.

    Devuelve (por_pid, coords_por_identidad, dmat_por_pid, clusters_por_pid)
    donde clusters_por_pid = {umbral: {pid: [clusters]}}.
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
                "split": SPLIT_UNICO,
                "pid": pid,
                "identity": ident,
                "tipo": "sin_coordenadas_parseables",
                "detalle": "PDBQT sin ATOM/HETATM parseables",
            })

    dmat_por_pid: dict = {}
    clusters_por_pid: dict = {u: {} for u in UMBRALES}
    for pid in sorted(por_pid):
        identidades = sorted(por_pid[pid])
        firmas = {tuple(firma_por_identidad[i]) for i in identidades}
        if len(firmas) > 1:
            for ident in identidades:
                failures.append({
                    "split": SPLIT_UNICO,
                    "pid": pid,
                    "identity": ident,
                    "tipo": "firma_atomica_heterogenea",
                    "detalle": "el complejo tiene poses con distinta secuencia "
                               "serial/elemento; el RMSD usa la intersección de seriales",
                })
        dmat = matriz_distancias(identidades, coords_por_identidad)
        dmat_por_pid[pid] = dmat
        for u in UMBRALES:
            clusters_por_pid[u][pid] = clustering_diametro(identidades, dmat, u)
    return por_pid, coords_por_identidad, dmat_por_pid, clusters_por_pid


def evaluar_umbral(pid_orden: list, clusters_por_pid: dict,
                   candidatos_por_identidad: dict, labels: dict,
                   dmat_por_pid: dict, umbral: float):
    """Fase de EVALUACIÓN (única que lee labels). NO participa en admisión ni
    en elección de representante.

    Por complejo: cobertura de oráculo antes/después (representante = medoid),
    degradación de min-RMSD (min rmsd de medoids − mejor rmsd antes, >= 0) y
    ablation mejor-Vina (representante alternativo, secundaria). Genera además
    las filas de labels dedup (con cluster_best_* como dato de evaluación).
    """
    filas_labels: list = []
    filas_per_complex: list = []
    perdidos: list = []
    perdidos_vina: list = []
    degradaciones: list = []
    degradaciones_vina: list = []
    n_antes = 0
    n_despues = 0
    cubiertos_antes = 0
    cubiertos_despues = 0
    cubiertos_despues_vina = 0
    por_fuente_antes: dict = {}
    por_fuente_despues: dict = {}
    tamanos: list = []

    for pid in pid_orden:
        clusters = clusters_por_pid[pid]
        dmat = dmat_por_pid[pid]
        ids_complejo = [ident for cl in clusters for ident in cl]
        rmsds = [float(labels[i]["rmsd"]) for i in ids_complejo]
        mejor_antes = min(rmsds)
        n_antes += len(ids_complejo)
        n_despues += len(clusters)

        reps = [medoid_geometrico(cl, dmat) for cl in clusters]
        min_rep = min(float(labels[r]["rmsd"]) for r in reps)
        reps_vina = [rep_mejor_vina(cl, candidatos_por_identidad) for cl in clusters]
        min_rep_vina = min(float(labels[r]["rmsd"]) for r in reps_vina)

        cubierto_antes = mejor_antes <= UMBRAL_COBERTURA
        cubierto_despues = min_rep <= UMBRAL_COBERTURA
        cubierto_despues_vina = min_rep_vina <= UMBRAL_COBERTURA
        cubiertos_antes += 1 if cubierto_antes else 0
        cubiertos_despues += 1 if cubierto_despues else 0
        cubiertos_despues_vina += 1 if cubierto_despues_vina else 0

        degradaciones.append(min_rep - mejor_antes)
        degradaciones_vina.append(min_rep_vina - mejor_antes)

        if cubierto_antes and not cubierto_despues:
            perdidos.append(f"{SPLIT_UNICO}|{pid}")
        if cubierto_antes and not cubierto_despues_vina:
            perdidos_vina.append(f"{SPLIT_UNICO}|{pid}")

        for ident in ids_complejo:
            fuente = candidatos_por_identidad[ident]["source"]
            por_fuente_antes[fuente] = por_fuente_antes.get(fuente, 0) + 1
        for ident in reps:
            fuente = candidatos_por_identidad[ident]["source"]
            por_fuente_despues[fuente] = por_fuente_despues.get(fuente, 0) + 1

        for idx, cluster in enumerate(clusters):
            tamanos.append(len(cluster))
            rep = reps[idx]
            fila = dict(labels[rep])
            fila["pid"] = pid
            fila["cluster_id"] = idx
            fila["cluster_size"] = len(cluster)
            mejor = min(cluster, key=lambda i: (float(labels[i]["rmsd"]), i))
            if mejor != rep and float(labels[mejor]["rmsd"]) < float(labels[rep]["rmsd"]):
                fila["cluster_best_rmsd"] = labels[mejor]["rmsd"]
                fila["cluster_best_identity"] = mejor
            filas_labels.append(fila)

        filas_per_complex.append({
            "pid": pid,
            "umbral": umbral,
            "n_antes": len(ids_complejo),
            "n_despues": len(clusters),
            "cluster_count": len(clusters),
            "coverage_antes": bool(cubierto_antes),
            "coverage_despues": bool(cubierto_despues),
            "mejor_rmsd_antes": round(mejor_antes, 4),
            "min_rmsd_medoids": round(min_rep, 4),
            "degradacion": round(min_rep - mejor_antes, 4),
        })

    tamanos_ordenados = sorted(tamanos)
    degradacion_mediana = mediana(degradaciones)
    degradacion_mediana_vina = mediana(degradaciones_vina)
    n_complejos = len(pid_orden)
    reduccion_fraccion = (1 - n_despues / n_antes) if n_antes else 0.0
    resumen = {
        "umbral": umbral,
        "n_antes": n_antes,
        "n_despues": n_despues,
        "reduccion_pct": round(100.0 * reduccion_fraccion, 2),
        "n_complejos": n_complejos,
        "cubiertos_antes": cubiertos_antes,
        "cubiertos_despues": cubiertos_despues,
        "cobertura_antes": round(cubiertos_antes / n_complejos, 4) if n_complejos else 0.0,
        "cobertura_despues": round(cubiertos_despues / n_complejos, 4) if n_complejos else 0.0,
        "n_perdidos": len(perdidos),
        "complejos_perdidos": perdidos,
        "degradacion_mediana": round(degradacion_mediana, 4)
        if degradacion_mediana is not None else None,
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
        "cumple": {
            "a_cero_perdidas": len(perdidos) == 0,
            "b_degradacion_mediana": degradacion_mediana is not None
            and degradacion_mediana <= 0.1,
            "c_reduccion": reduccion_fraccion >= 0.10,
        },
        "ablation_mejor_vina": {
            "nota": "SECUNDARIA, NO primaria: mezcla deduplicacion con senal de "
                    "Vina (RS-01 la evaluara; puede favorecer fuentes/configuraciones "
                    "de Vina). El clustering es el mismo; solo cambia el representante.",
            "cubiertos_despues": cubiertos_despues_vina,
            "cobertura_despues": round(cubiertos_despues_vina / n_complejos, 4)
            if n_complejos else 0.0,
            "n_perdidos": len(perdidos_vina),
            "complejos_perdidos": perdidos_vina,
            "degradacion_mediana": round(degradacion_mediana_vina, 4)
            if degradacion_mediana_vina is not None else None,
        },
    }
    return filas_labels, filas_per_complex, resumen


def seleccionar_umbral(resumenes: dict):
    """Regla preregistrada: el MAYOR umbral que cumple (a)+(b)+(c).
    Devuelve (elegido, motivo); elegido = None si ninguno cumple (NO_GO)."""
    validos = [u for u in UMBRALES if all(resumenes[str(u)]["cumple"].values())]
    if not validos:
        return None, (
            "ningun umbral cumple (a) 0 perdidas + (b) degradacion mediana <= 0.1 + "
            "(c) reduccion >= 10%: NO_GO con la tabla completa (sin elegir a dedo)"
        )
    elegido = max(validos)
    r = resumenes[str(elegido)]
    motivo = (
        f"{elegido} es el MAYOR umbral que cumple (a) 0 perdidas, "
        f"(b) degradacion mediana {r['degradacion_mediana']} <= 0.1, "
        f"(c) reduccion {r['reduccion_pct']}% >= 10%"
    )
    return elegido, motivo


def umbral_per_complex(elegido, resumenes: dict):
    """Umbral para per_complex.jsonl: el elegido por la regla; si ninguno
    cumple, fallback preregistrado: umbral con 0 perdidas y MENOR degradación
    mediana (empate: mayor U); si ninguno tiene 0 perdidas, el mayor U."""
    if elegido is not None:
        return elegido
    cero = [u for u in UMBRALES if resumenes[str(u)]["n_perdidos"] == 0]
    if cero:
        return min(cero, key=lambda u: (resumenes[str(u)]["degradacion_mediana"], -u))
    return max(UMBRALES)


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

    candidatos, labels = cargar_union_train(union_dir)
    union_pids = {str(c["pid"]) for c in candidatos}

    _por_pid, _coords, dmat_por_pid, clusters_por_pid = agrupar_por_complejo(
        candidatos, failures
    )
    candidatos_por_identidad = {c["identity"]: c for c in candidatos}
    pid_orden = sorted({c["pid"] for c in candidatos})

    filas_labels_por_umbral: dict = {}
    filas_cand_por_umbral: dict = {}
    filas_pc_por_umbral: dict = {}
    resumenes: dict = {}
    for u in UMBRALES:
        filas_labels, filas_pc, resumen = evaluar_umbral(
            pid_orden, clusters_por_pid[u], candidatos_por_identidad,
            labels, dmat_por_pid, u,
        )
        reps_ordenados = sorted(
            medoid_geometrico(cl, dmat_por_pid[pid])
            for pid in pid_orden
            for cl in clusters_por_pid[u][pid]
        )
        filas_cand_por_umbral[u] = [dict(candidatos_por_identidad[i]) for i in reps_ordenados]
        filas_labels_por_umbral[u] = sorted(filas_labels, key=lambda f: f["identity"])
        filas_pc_por_umbral[u] = filas_pc
        resumenes[str(u)] = resumen

    exclusiones = verificar_exclusiones(union_pids, errores)
    if errores:
        for err in errores:
            print(f"ERROR: {err}", file=sys.stderr)
        return 1
    if union_pids & set(exclusiones["test_historico"]["interseccion"]):
        print("ERROR: intersección con test histórico", file=sys.stderr)
        return 1
    if union_pids & set(exclusiones["denylist_fnd05"]["interseccion"]):
        print("ERROR: intersección con denylist D-RC-CONFIRM", file=sys.stderr)
        return 1

    elegido, motivo = seleccionar_umbral(resumenes)
    u_pc = umbral_per_complex(elegido, resumenes)

    filas_sidecar, empates_resumen = construir_sidecar_y_empates(
        pid_orden, clusters_por_pid[u_pc], candidatos_por_identidad,
        dmat_por_pid, u_pc,
    )
    escribir_jsonl(out_dir / f"cluster_members_train_{ETIQUETA_UMBRAL[u_pc]}.jsonl",
                   filas_sidecar)

    for u in UMBRALES:
        et = ETIQUETA_UMBRAL[u]
        escribir_jsonl(out_dir / f"dedup_candidates_train_{et}.jsonl",
                       filas_cand_por_umbral[u])
        escribir_jsonl(out_dir / f"dedup_labels_train_{et}.jsonl",
                       filas_labels_por_umbral[u])
    escribir_jsonl(out_dir / "per_complex.jsonl",
                   sorted(filas_pc_por_umbral[u_pc], key=lambda f: f["pid"]))
    escribir_jsonl(out_dir / "failures.jsonl", failures)

    metrics = {
        "experimento": "MF-11-R1",
        "insumos": {
            "union": "scripts/artifacts_science/MF-01-UNION (solo lectura, sellado)",
            "splits": [SPLIT_UNICO],
            "n_complejos_train": len(pid_orden),
            "n_antes_train": len(candidatos),
            "nota": "SOLO train (desviacion D1 de MF-11: la val actual queda excluida "
                    "por completo; la regla se evalua unicamente sobre train)",
        },
        "contrato": {
            "metrica": "RMSD pocket-frame pose-vs-pose (heavy atoms, matching 1:1 "
                       "por serial, sin alineamiento; misma definicion de marco que "
                       "molflex.rmsd_pose_pocket extendida por pares)",
            "regla_admision": "diametro controlado: la pose entra al PRIMER cluster "
                              "(orden de creacion) cuya distancia a TODOS los miembros "
                              "es <= U (garantia: todo par de miembros a <= U); greedy "
                              "por identidad ascendente; si no, cluster nuevo",
            "representante_primario": "medoid geometrico (minimiza suma de RMSDs a los "
                                      "demas; empate por identidad ascendente; label-blind)",
            "umbrales_preregistrados": list(UMBRALES),
            "seleccion": "MAYOR umbral con (a) 0 perdidas de cobertura (<= 2.0 A con el "
                         "medoid), (b) degradacion mediana <= 0.1 A, (c) reduccion >= 10%; "
                         "si ninguno cumple, NO_GO con tabla completa (sin elegir a dedo)",
            "ablation": "SECUNDARIA, NO primaria: representante = mejor vina_score "
                        "(label-blind); mezcla dedup con senal Vina (RS-01 la evaluara)",
            "separacion_oraculo": "union_labels_train se lee SOLO en la fase de "
                                  "evaluacion (evaluar_umbral); admision y eleccion de "
                                  "representante NUNCA usan labels",
            "sidecar": "cluster_members_train_{U}.jsonl del umbral elegido: audita "
                       "la membresia de cada cluster (representante medoid, miembros, "
                       "fuentes, provenance_keys, diametro maximo) sin reejecutar",
        },
        "por_umbral": resumenes,
        "seleccion_umbral": {
            "umbral_elegido": elegido,
            "motivo": motivo,
            "umbral_per_complex": u_pc,
            "nota_per_complex": "per_complex.jsonl usa el umbral elegido; si ninguno "
                                "cumple, el fallback preregistrado (ver DESIGN.md)",
        },
        "empates_medoid": empates_resumen,
        "exclusiones": exclusiones,
        "label_blind": {
            "clustering": "no lee labels (verificado por contrato y por test sintetico "
                          "scripts/test_dedup_pose_union_medoid.py)",
            "cobertura": "el oraculo (rmsd cristalografico de union_labels_train) se usa "
                         "EXCLUSIVAMENTE para evaluar la preservacion DESPUES de deduplicar",
        },
        "determinismo": "salidas sin timestamps ni aleatoriedad; dos corridas producen "
                        "bytes identicos (verificacion en DESIGN.md)",
    }
    escribir_json(out_dir / "metrics.json", metrics)

    for u in UMBRALES:
        r = resumenes[str(u)]
        print(f"[U={u}] n={r['n_antes']}->{r['n_despues']} reduccion={r['reduccion_pct']}% "
              f"cobertura {r['cubiertos_antes']}->{r['cubiertos_despues']}/{r['n_complejos']} "
              f"perdidos={r['n_perdidos']} degradacion_mediana={r['degradacion_mediana']} "
              f"cumple={all(r['cumple'].values())}")
    print(f"[seleccion] umbral_elegido={elegido} — {motivo}")
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
        description="MF-11-R1: deduplicación label-blind de la unión MF-01-UNION "
                    "(SOLO train) con diámetro controlado y medoid geométrico; "
                    "5 umbrales preregistrados en una pasada.")
    parser.add_argument("--union-dir", type=Path, default=UNION_DIR_DEFAULT,
                        help="directorio de la unión materializada (default: %(default)s)")
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR_DEFAULT,
                        help="directorio de salida del experimento MF-11-R1 (default: %(default)s)")
    args = parser.parse_args(argv)
    return correr(Path(args.union_dir), Path(args.out_dir))


if __name__ == "__main__":
    sys.exit(main())
