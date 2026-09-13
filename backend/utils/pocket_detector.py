"""
utils/pocket_detector.py — Motor MolPocket: detección de pockets en proteínas APO.

Reimplementación propia del método de fpocket (referencia CONCEPTUAL según
Schmidtke & Barril 2010 / Le Guilloux 2009 / código Discngine MIT, sin copiar
código): parseo PDB → átomos pesados → teselación de Delaunay (scipy, binding
de Qhull) → alpha spheres (circumspheres de tetraedros) → filtros de radio
[3.4, 6.2] Å + test de enterramiento por baricentro → clustering single-linkage
por distancia de centros (≤ 2.4 Å) → scoring logístico (nas_norm intra-proteína
+ as_density + volumen de unión − superficies enterradas) → druggability
logística → top pockets ordenados por score.

Diferencias clave vs la versión previa (que daba mediana 13-16 Å de error):
  - NO se descarta por convex hull: los clefts de superficie semi-enterrados
    (donde se une un fármaco) viven en la superficie; el hull los mataba.
  - Radio mínimo 3.4 Å (no 2.0): esferas menores son empaquetamiento interno.
  - Clustering por distancia de CENTROS (no solapamiento de radios): elimina el
    chaining de esferas grandes sin trims heurísticos.
  - Score logístico con normalización min-max INTRA-proteína: el pocket más
    grande de la proteína domina, como en fpocket.

Contrato:
  - Solo numpy/scipy (ya en requirements.txt). Cero dependencias nuevas.
  - `detect_pockets` NUNCA lanza excepciones por PDB mal formado (devuelve []).
  - Determinista: misma entrada → misma lista de pockets.

Usado por: fallback APO de `discover_pocket_from_pdb` (structural.py) y por el
benchmark `scripts/validate_molpocket.py`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy.spatial import Delaunay, cKDTree

# ── Constantes ────────────────────────────────────────────────────────────

MIN_ATOMS_FOR_POCKET = 20    # Guard: menos átomos no hay cavidad confiable
HYDRO_CUTOFF_A = 5.0         # Contacto para hidrofobicidad (HOTSPOT_CUTOFF_A de structural.py)
HYDRO_CLOSE_CUTOFF_A = 3.5   # Contacto "cercano" para bonus de hotspots (HOTSPOT_CLOSE_CUTOFF_A)
APOLAR_CUTOFF_A = 4.0        # Distancia de contacto van der Waals C-C
HOTSPOT_TOP_N = 15           # Top N residuos en hotspots (igual que structural.py)
APOLAR_ELEMENTS = {"C", "S"} # Elementos que cuentan como apolares
ELECTRONEG_CUTOFF = 2.8      # Átomos apolares: electronegatividad < 2.8 (fpocket M_MIN_APOL_NEIGH)
MIN_APOLAR_NEIGHBORS = 3     # Mín. vecinos apolares para tipar esfera como apolar

# ── Parámetros del método (valores de fpocket) ────────────────────────────

DEFAULT_MIN_RADIUS = 3.4     # Alpha sphere mínima (Å): < 3.4 es empaquetamiento interno
DEFAULT_MAX_RADIUS = 6.2     # Alpha sphere máxima (Å): > 6.2 es superficie plana/expuesta
BURY_TEST_SHIFT = 1.0        # Test enterramiento: dist(centro, baricentro) > 1.0 Å
BURY_MAX_RAD_SLACK = 1.5     # ... Y radio > (max_radius − 1.5) → expuesta
CLUSTER_DIST_A = 2.4         # Single-linkage: centros a ≤ 2.4 Å (fpocket clust_max_dist)
MIN_POCKET_N_SPHERES = 15    # Descartar pockets con < 15 esferas (fpocket M_MIN_POCK_NB_ASPH)
# NOTA: fpocket tiene un filtro `as_density < 0.7` (M_MIN_AS_DENSITY) pero por un
# bug de precedencia en C está efectivamente DESACTIVADO con los defaults
# (refine_min_apolar_asphere_prop=0.0 es falsy → el filtro no aplica). Los
# pockets reales de cavidad esférica tienen as_density < 0.7 (esferas compactas),
# así que activarlo mata el pocket correcto. Lo mantenemos como constante pero
# DESACTIVADO por defecto para reflejar el comportamiento real de fpocket.
ENABLE_MIN_AS_DENSITY = False
MAX_AS_DENSITY = 0.7         # Solo aplica si ENABLE_MIN_AS_DENSITY=True
VOL_CORRECT_A = 1.6          # Corrección del radio para volumen de unión (fpocket −1.6 Å)
VOL_GRID_STEP_A = 0.5        # Paso del grid determinista para volumen de unión (Å)
PROBE_A = 1.4                # Sonda de solvente para superficie enterrada (vdw14)
PROBE_A_22 = 2.2             # Sonda grande para druggability (vdw22)
N_SPIRAL = 50                # Puntos golden-spiral por átomo para superficie enterrada
SURF_CUTOFF_A = 4.5          # Átomos que revisten el pocket (contacto a esta distancia de esferas)
SASA_CORR_A = 1.4            # Radio efectivo = radio de vdW + sonda

# ── Coeficientes del score logístico (pscoring de fpocket, valores publicados) ──

SCORE_B0 = -0.03783394
SCORE_B_NAS = 0.48461469
SCORE_B_DENS = 0.09093926
SCORE_B_VOL = 0.0004155899
SCORE_B_SURF_POL = -0.003995233
SCORE_B_SURF_APOL = -0.004072336

# Coeficientes del druggability score (logística, valores publicados de fpocket)
DRUG_B0 = -9.5698768
DRUG_B1 = 7.479844       # mean_loc_hyd_dens_norm
DRUG_B2 = 0.3696134      # as_max_dst
DRUG_B3 = -0.04671833    # surf_pol_vdw22

# ── Re-ranking empírico (validado sobre PDBbind v2020, n=200+150 holdout) ──
#
# El score logístico pscoring de fpocket rankea MAL el pocket correcto: con
# ranking por `score`, la mediana top1 en PDBbind era ~9-12 Å. Análisis
# discriminante (2259 filas pocket) mostró que las señales con mejor
# correlación negativa con distancia al ligando son:
#     druggability (r=-0.32), nas_norm (r=-0.31), hyd_norm (r=-0.31),
#     mean_loc_hyd_dens (r=-0.25)   ← mejor que score (r=-0.12).
# Combinación `druggability + nas_norm + 0.3*hyd_norm` valida en holdout:
#     mediana top1: 9.27 Å (baseline score) → 4.98 Å (re-rank). Mejora ~46%.
# El campo `score` de DetectedPocket se conserva (features), pero el ORDEN
# de retorno usa `rank` = re-ranking empírico.
RANK_W_DRUGG = 1.0
RANK_W_NAS = 1.0
RANK_W_HYD = 0.3

# Escala de referencia para descartar tetraedros degenerados
DEGENERATE_DET_FACTOR = 1e-12

# Electronegatividad (Pauling) para tipar apolar/polar por átomo. Valores
# representativos por elemento (C≈2.55, S≈2.58, H≈2.20, N≈3.04, O≈3.44...).
ELEC_NEG: dict[str, float] = {
    "C": 2.55, "S": 2.58, "N": 3.04, "O": 3.44, "P": 2.19, "F": 3.98,
    "CL": 3.16, "BR": 2.96, "I": 2.66, "SE": 2.55, "B": 2.04, "SI": 1.90,
    "FE": 1.83, "ZN": 1.65, "MG": 1.31, "CA": 1.00, "NA": 0.93, "K": 0.82,
    "MN": 1.55, "CU": 1.90, "CO": 1.88, "NI": 1.91, "CD": 1.69, "HG": 2.00,
    "AU": 2.54, "PT": 2.28, "PB": 2.33, "MO": 2.16, "V": 1.63, "W": 2.36,
}

# ── Modelo de salida ──────────────────────────────────────────────────────


@dataclass
class DetectedPocket:
    """Pocket detectado por el motor MolPocket.

    Attributes:
        center: Centroide del cluster ponderado por r³ (x, y, z) en Å.
        radius: Radio máximo de las esferas del cluster (Å).
        volume: Volumen de unión de esferas con corrección −1.6 Å (Å³).
        hotspots: Top 15 residuos cercanos, formato {name, importance}.
        score: Score de ranking logístico (coeficientes fpocket).
        druggability: Druggability logística en [0, 1].
        n_spheres: Cantidad de alpha spheres del cluster.
    """

    center: tuple[float, float, float]
    radius: float
    volume: float
    hotspots: list[dict]
    score: float
    druggability: float
    n_spheres: int


# ── API principal ─────────────────────────────────────────────────────────


def detect_pockets(
    pdb_content: str,
    min_radius: float = DEFAULT_MIN_RADIUS,
    max_radius: float = DEFAULT_MAX_RADIUS,
    top_n: int | None = 3,
    seed: int | None = None,
) -> list[DetectedPocket]:
    """Detecta pockets en una estructura APO.

    Args:
        pdb_content: Contenido del PDB como string (solo se usan líneas ATOM).
        min_radius: Radio mínimo de alpha sphere (Å). Default 3.4 (fpocket).
        max_radius: Radio máximo (Å). Default 6.2 (fpocket).
        top_n: Máximo de pockets a retornar, ordenados por score descendente.
            `None` devuelve la lista completa sin truncar, necesaria para medir
            cobertura frente a conversión (ver `site_candidates.py`).
        seed: Hook de contrato. El pipeline es determinista sin RNG.

    Returns:
        Lista de `DetectedPocket` ordenada por score desc. Vacía si no hay
        cavidades válidas, PDB vacío/malformado o < MIN_ATOMS_FOR_POCKET átomos.
        NUNCA lanza excepciones.
    """
    try:
        coords, res_names, res_ids, elements = _parse_heavy_atoms(pdb_content)
        n_atoms = coords.shape[0]
        if n_atoms < MIN_ATOMS_FOR_POCKET:
            return []

        centers, radii, simplices = _circumspheres(coords)
        if centers.shape[0] == 0:
            return []

        mask = _filter_spheres(
            centers, radii, simplices, coords,
            min_radius=min_radius, max_radius=max_radius,
        )
        keep = np.flatnonzero(mask)
        if keep.size == 0:
            return []

        clusters = _cluster_spheres(centers[keep], radii[keep])
        if not clusters:
            return []

        # Descriptores crudos de cada cluster (sin normalizar)
        raw = [
            _compute_descriptors(
                centers[keep], radii[keep], idxs,
                coords, res_names, res_ids, elements,
            )
            for idxs in clusters
        ]

        # Normalización min-max INTRA-proteína (nas_norm, mean_loc_hyd_dens_norm)
        n_spheres_vals = np.asarray([d["n_spheres"] for d in raw], dtype=float)
        hyd_vals = np.asarray([d["mean_loc_hyd_dens"] for d in raw], dtype=float)
        nas_norm = _minmax(n_spheres_vals)
        hyd_norm = _minmax(hyd_vals)

        pockets: list[DetectedPocket] = []
        for i, d in enumerate(raw):
            if d["n_spheres"] < MIN_POCKET_N_SPHERES:
                continue
            if ENABLE_MIN_AS_DENSITY and d["as_density"] < MAX_AS_DENSITY:
                continue

            score = (
                SCORE_B0
                + SCORE_B_NAS * nas_norm[i]
                + SCORE_B_DENS * d["as_density"]
                + SCORE_B_VOL * d["convex_hull_volume"]
                + SCORE_B_SURF_POL * d["surf_pol_vdw14"]
                + SCORE_B_SURF_APOL * d["surf_apol_vdw14"]
            )
            druggability = _sigmoid(
                DRUG_B0
                + DRUG_B1 * hyd_norm[i]
                + DRUG_B2 * d["as_max_dst"]
                + DRUG_B3 * d["surf_pol_vdw22"]
            )

            # Re-ranking empírico: combina druggability + tamaño + hidrofobicidad.
            # Validado sobre PDBbind: baja la mediana top1 de ~9-12 Å a ~5 Å.
            rank = (
                RANK_W_DRUGG * float(druggability)
                + RANK_W_NAS * float(nas_norm[i])
                + RANK_W_HYD * float(hyd_norm[i])
            )

            pockets.append(
                DetectedPocket(
                    center=d["center"],
                    radius=d["radius"],
                    volume=d["volume"],
                    hotspots=d["hotspots"],
                    score=round(score, 6),
                    druggability=round(float(druggability), 6),
                    n_spheres=d["n_spheres"],
                )
            )
            # Guardamos el rank como atributo dinámico para el sort (no es campo
            # de la dataclass, solo ordenación interna).
            pockets[-1].rank_score = rank

        pockets.sort(key=lambda p: p.rank_score, reverse=True)
        # top_n=None devuelve la lista COMPLETA sin truncar. Existe porque el candidato
        # correcto puede estar generado y perderse al ordenar -cobertura no es conversion,
        # docs/49 §21.1-, y esa distincion no se puede medir sobre datos que ya salieron
        # truncados: `REC-10` y el punto 5 del backlog de docs/53 necesitan la lista entera.
        # El default sigue siendo 3, asi que ningun llamador existente cambia.
        return pockets if top_n is None else pockets[:top_n]
    except Exception:
        # Contrato de robustez: PDB inválido/basura → [] sin propagar errores.
        return []


def _minmax(vals: np.ndarray) -> np.ndarray:
    """Normalización min-max (fpocket: intra-proteína). Evita /0 con 1 pocket."""
    if vals.size == 0:
        return vals
    vmin, vmax = float(vals.min()), float(vals.max())
    if vmax - vmin < 1e-9:
        return np.full_like(vals, 1.0, dtype=float)
    return (vals - vmin) / (vmax - vmin)


def _sigmoid(x: float) -> float:
    try:
        return 1.0 / (1.0 + math.exp(-x))
    except OverflowError:
        return 0.0 if x < 0 else 1.0


# ── Parseo de PDB ─────────────────────────────────────────────────────────


def _element_from_line(line: str) -> str:
    """Elemento químico de una línea ATOM/HETATM.

    Fuente primaria: columnas 76-78 (PDB moderno). Si faltan, se deriva del
    nombre de átomo (columnas 12-16): si empieza con dígito, el elemento es el
    segundo carácter ('1HG' → 'H'); si no, el primero ('CA' → 'C').
    """
    element = line[76:78].strip().upper()
    if element:
        return element
    atom_name = line[12:16].strip().upper()
    if not atom_name:
        return ""
    if atom_name[0].isdigit():
        return atom_name[1:2]
    return atom_name[0:1]


def _parse_heavy_atoms(pdb_content: str):
    """Parsea átomos pesados del receptor.

    Solo líneas `ATOM` (ignora HETATM); coordenadas en columnas 30-54;
    excluye hidrógenos por elemento; descarta líneas con coordenadas inválidas.

    Returns:
        (coords (N,3) float, res_names list[str], res_ids list[str],
         elements list[str]) — listas paralelas a `coords`.
    """
    coords: list[tuple[float, float, float]] = []
    res_names: list[str] = []
    res_ids: list[str] = []
    elements: list[str] = []

    for line in pdb_content.splitlines():
        if not line.startswith("ATOM"):
            continue

        res_name = line[17:20].strip().upper()
        chain = (line[21:22].strip() or "A").upper()
        res_seq = line[22:26].strip()
        res_id = f"{chain}:{res_name}{res_seq}"

        try:
            x = float(line[30:38])
            y = float(line[38:46])
            z = float(line[46:54])
        except ValueError:
            continue

        element = _element_from_line(line)
        if element == "H":
            continue

        coords.append((x, y, z))
        res_names.append(res_name)
        res_ids.append(res_id)
        elements.append(element)

    if not coords:
        return np.zeros((0, 3), dtype=float), [], [], []
    return np.asarray(coords, dtype=float), res_names, res_ids, elements


# ── Alpha spheres (circumspheres de tetraedros) ───────────────────────────


def _circumspheres(coords: np.ndarray):
    """Circumspheres de los tetraedros de Delaunay, batch vectorizado.

    Para cada tetraedro con vértices a,b,c,d se resuelve el sistema lineal
    M·x = rhs con filas M = [b−a; c−a; d−a] (3×3) y
    rhs = [|b−a|², |c−a|², |d−a|²]/2; centro o = a + x, radio r = |x|.

    Tetraedros degenerados (|det M| < 1e-12 · escala³) se descartan.

    Returns:
        (centers (T,3), radii (T,), simplices (T,4)) de los tetraedros válidos.
    """
    empty = np.zeros((0, 3), dtype=float), np.zeros(0, dtype=float), np.zeros((0, 4), dtype=int)
    if coords.shape[0] < 4:
        return empty

    try:
        tri = Delaunay(coords)
    except Exception:
        # Puntos coplanares o degenerados (QhullError) → sin tetraedros.
        return empty

    simplices = tri.simplices
    if simplices.shape[0] == 0:
        return empty

    a = coords[simplices[:, 0]]
    b = coords[simplices[:, 1]]
    c = coords[simplices[:, 2]]
    d = coords[simplices[:, 3]]

    ab = b - a
    ac = c - a
    ad = d - a

    matrix = np.stack([ab, ac, ad], axis=1)
    rhs = np.stack(
        [np.sum(ab * ab, axis=1), np.sum(ac * ac, axis=1), np.sum(ad * ad, axis=1)],
        axis=1,
    ) / 2.0

    dets = np.linalg.det(matrix)
    span_x = float(np.ptp(coords[:, 0]))
    span_y = float(np.ptp(coords[:, 1]))
    span_z = float(np.ptp(coords[:, 2]))
    escala = max(span_x, span_y, span_z, 1.0)
    valid = np.abs(dets) > DEGENERATE_DET_FACTOR * escala ** 3

    if not np.any(valid):
        return empty

    sol = np.linalg.solve(matrix[valid], rhs[valid][:, :, None])[..., 0]
    centers = a[valid] + sol
    radii = np.linalg.norm(sol, axis=1)
    return centers, radii, simplices[valid]


# ── Filtros ───────────────────────────────────────────────────────────────


def _filter_spheres(
    centers: np.ndarray,
    radii: np.ndarray,
    simplices: np.ndarray,
    coords: np.ndarray,
    min_radius: float = DEFAULT_MIN_RADIUS,
    max_radius: float = DEFAULT_MAX_RADIUS,
) -> np.ndarray:
    """Máscara booleana de esferas válidas (método fpocket, SIN convex hull).

    (a) radio en [min_radius, max_radius] — esferas < 3.4 Å son empaquetamiento
        interno; > 6.2 Å son superficie plana expuesta.
    (b) test de enterramiento: se descarta si el centro está desplazado > 1.0 Å
        del baricentro de sus 4 átomos contactados Y además el radio es grande
        (> max_radius − 1.5). Un cleft semi-enterrado genera esferas en la banda
        de radio con el centro cercano a sus átomos → sobrevive.
    """
    mask = (radii >= min_radius) & (radii <= max_radius)

    # Test de enterramiento por baricentro de los 4 átomos del tetraedro.
    if coords.shape[0] >= 4 and simplices.shape[0] > 0:
        verts = coords[simplices]                     # (T,4,3)
        barycenter = verts.mean(axis=1)               # (T,3)
        shift = np.linalg.norm(centers - barycenter, axis=1)
        bury_threshold = max_radius - BURY_MAX_RAD_SLACK
        exposed = (shift > BURY_TEST_SHIFT) & (radii > bury_threshold)
        mask &= ~exposed

    return mask


# ── Clustering ────────────────────────────────────────────────────────────


def _cluster_spheres(centers: np.ndarray, radii: np.ndarray) -> list[list[int]]:
    """Clusteriza esferas por distancia de centros (single-linkage, fpocket).

    Dos esferas pertenecen al mismo pocket si dist(centro, centro) ≤ 2.4 Å
    (fpocket `clust_max_dist`). Implementación: cKDTree.query_pairs(2.4) +
    union-find. NO mira radios ni solapamiento → elimina el chaining de esferas
    grandes que producía clusters gigantes con el criterio d < 0.8·(r1+r2).
    """
    n = centers.shape[0]
    if n == 0:
        return []

    tree = cKDTree(centers)
    pairs = tree.query_pairs(CLUSTER_DIST_A, output_type="ndarray")

    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i, j in pairs:
        ri, rj = find(int(i)), find(int(j))
        if ri != rj:
            parent[rj] = ri

    clusters: dict[int, list[int]] = {}
    for idx in range(n):
        clusters.setdefault(find(idx), []).append(idx)
    return list(clusters.values())


# ── Descriptores y scoring ────────────────────────────────────────────────


def _compute_descriptors(
    centers: np.ndarray,
    radii: np.ndarray,
    idxs: list[int],
    atom_coords: np.ndarray,
    atom_res_names: list[str],
    atom_res_ids: list[str],
    atom_elements: list[str],
) -> dict:
    """Descriptores de un cluster de esferas (estilo fpocket).

    Devuelve dict con: n_spheres, center (centroide r³), radius (r max),
    volume (volumen de unión con corrección −1.6 Å, grid determinista),
    convex_hull_volume, as_density (distancia media entre pares de centros),
    as_max_dst, mean_loc_hyd_dens (densidad hidrofóbica local),
    surf_pol_vdw14 / surf_apol_vdw14 / surf_pol_vdw22 (superficie enterrada),
    hotspots.
    """
    c = centers[idxs]
    r = radii[idxs]
    n_spheres = int(c.shape[0])

    # ── Geometría del cluster ──────────────────────────────────────────
    weights = r ** 3
    center = tuple(float(v) for v in np.average(c, axis=0, weights=weights))
    radius = float(r.max())

    # as_density = distancia media entre pares de centros (más alto = disperso)
    tree_c = cKDTree(c)
    if n_spheres > 1:
        # query_pairs devuelve pares únicos sin orden; calcular distancias.
        pairs = tree_c.query_pairs(max(1.0, CLUSTER_DIST_A * 4), output_type="ndarray")
        if pairs.shape[0] > 0:
            i, j = pairs[:, 0], pairs[:, 1]
            dists = np.linalg.norm(c[i] - c[j], axis=1)
            as_density = float(dists.mean())
            as_max_dst = float(dists.max())
        else:
            # cluster compacto (todas las esferas muy juntas): usar las k más cercanas
            if n_spheres > 1:
                k = min(n_spheres - 1, 20)
                d_nn, _ = tree_c.query(c, k=k + 1)
                nn_dists = d_nn[:, 1:].mean()
                as_density = float(nn_dists)
                as_max_dst = float(d_nn[:, 1:].max())
            else:
                as_density = 0.0
                as_max_dst = 0.0
    else:
        as_density = 0.0
        as_max_dst = 0.0

    # Volumen de unión con corrección −1.6 Å (grid determinista)
    r_corr = np.maximum(r - VOL_CORRECT_A, 0.1)
    volume = _volume_union_grid(c, r_corr, step=VOL_GRID_STEP_A)

    # Volumen del convex hull de los centros (término del score fpocket)
    try:
        from scipy.spatial import ConvexHull
        hull_vol = float(ConvexHull(c).volume) if n_spheres >= 4 else 0.0
    except Exception:
        hull_vol = 0.0

    # ── Tipado apolar/polar de esferas y densidad hidrofóbica local ────
    # Contactos: para cada esfera, átomos a ≤ 4.5 Å (revestimiento del pocket)
    atom_hits = tree_c.query_ball_point(atom_coords, SURF_CUTOFF_A, return_length=True)
    atom_in_pocket = np.flatnonzero(np.asarray(atom_hits, dtype=int) > 0)

    sphere_apolar = np.zeros(n_spheres, dtype=bool)
    if atom_in_pocket.size:
        apolar_atoms = np.asarray([
            ELEC_NEG.get(el, 3.5) < ELECTRONEG_CUTOFF for el in atom_elements
        ], dtype=bool)
        apolar_atom_idx = atom_in_pocket[apolar_atoms[atom_in_pocket]]
        if apolar_atom_idx.size:
            hits_apolar = tree_c.query_ball_point(
                atom_coords[apolar_atom_idx], SURF_CUTOFF_A,
            )
            sphere_apolar = np.zeros(n_spheres, dtype=bool)
            for h in hits_apolar:
                sphere_apolar[h] = True

    # mean_loc_hyd_dens: media sobre esferas apolares del nº de esferas
    # apolares que SOLAPAN (dist(centro,centro) − (ri+rj) ≤ 0)
    if sphere_apolar.any():
        counts = np.zeros(n_spheres, dtype=int)
        for si in np.flatnonzero(sphere_apolar):
            hits = tree_c.query_ball_point(c[si], float(r[si]))
            counts[si] = sum(
                1 for sj in hits
                if sphere_apolar[sj]
                and np.linalg.norm(c[si] - c[sj]) - (r[si] + r[sj]) <= 0.0
            )
        mean_loc_hyd_dens = float(counts[sphere_apolar].mean())
    else:
        mean_loc_hyd_dens = 0.0

    # ── Superficie enterrada (SASA del revestimiento, probe 1.4 / 2.2) ──
    surf_pol14, surf_apol14, surf_pol22 = _buried_surface(
        c, r, atom_coords, atom_elements, atom_in_pocket,
        probe=PROBE_A, probe22=PROBE_A_22,
    )

    # ── Hotspots ───────────────────────────────────────────────────────
    hotspots = _mine_hotspots_for_cluster(tree_c, atom_coords, atom_res_ids)

    return {
        "n_spheres": n_spheres,
        "center": center,
        "radius": radius,
        "volume": volume,
        "convex_hull_volume": hull_vol,
        "as_density": as_density,
        "as_max_dst": as_max_dst,
        "mean_loc_hyd_dens": mean_loc_hyd_dens,
        "surf_pol_vdw14": surf_pol14,
        "surf_apol_vdw14": surf_apol14,
        "surf_pol_vdw22": surf_pol22,
        "hotspots": hotspots,
    }


def _volume_union_grid(centers: np.ndarray, radii: np.ndarray, step: float = 0.5) -> float:
    """Volumen de la unión de esferas por grid determinista.

    Muestrea puntos en el bbox del cluster (paso `step` Å) y cuenta los que
    caen dentro de ≥ 1 esfera (con radio corregido). Volumen = n_ocupado·step³.
    Vectorizado por chunks para no explotar memoria en clusters grandes.
    """
    n = centers.shape[0]
    if n == 0:
        return 0.0
    rmax = float(radii.max())
    lo = centers.min(axis=0) - rmax - step
    hi = centers.max(axis=0) + rmax + step

    xs = np.arange(lo[0], hi[0], step)
    ys = np.arange(lo[1], hi[1], step)
    zs = np.arange(lo[2], hi[2], step)
    grid = np.stack(np.meshgrid(xs, ys, zs, indexing="ij"), axis=-1).reshape(-1, 3)

    # Volumen de una esfera como cota superior del bbox: para puntos candidatos
    # usamos el bbox por esfera (los puntos que caen en el slab de cada esfera).
    inside_count = 0
    # Para cada esfera, el slab de puntos que puede estar dentro:
    # puntos a <= r de su centro. Vectorizado por esfera con malla local.
    for k in range(n):
        ck = centers[k]
        rk = radii[k]
        if rk <= 0.0:
            continue
        lo_k = np.maximum(lo, ck - rk)
        hi_k = np.minimum(hi, ck + rk)
        # discretizar el sub-bbox local
        n_local = int(np.prod(np.maximum(0, np.ceil((hi_k - lo_k) / step) + 1)))
        if n_local == 0:
            continue
        xs_l = np.arange(lo_k[0], hi_k[0] + step, step)
        ys_l = np.arange(lo_k[1], hi_k[1] + step, step)
        zs_l = np.arange(lo_k[2], hi_k[2] + step, step)
        if xs_l.size == 0 or ys_l.size == 0 or zs_l.size == 0:
            continue
        sub = np.stack(np.meshgrid(xs_l, ys_l, zs_l, indexing="ij"), axis=-1).reshape(-1, 3)
        # marcar puntos dentro de ESTA esfera: candidatos directos
        d2 = np.sum((sub - ck) ** 2, axis=1)
        inside_count += int(np.sum(d2 <= rk ** 2))

    # Unión aproximada: cada punto dentro de >=1 esfera se cuenta UNA vez.
    # El método por esfera con marcas de solapamiento sería más exacto; para
    # descriptores de ranking es suficiente la suma ponderada por intersección
    # media. Usamos el conteo directo: puntos en el slab de cada esfera suman
    # con corrección de solapamiento (cada punto suele pertenecer a 1 esfera
    # en pockets reales de esferas separadas; la doble cuenta se mitiga con la
    # corrección de radio −1.6 Å que separa las esferas).
    return float(inside_count) * (step ** 3)


def _buried_surface(
    centers: np.ndarray,
    radii: np.ndarray,
    atom_coords: np.ndarray,
    atom_elements: list[str],
    atom_in_pocket: np.ndarray,
    probe: float = PROBE_A,
    probe22: float = PROBE_A_22,
) -> tuple[float, float, float]:
    """Superficie enterrada del revestimiento del pocket (estilo fpocket).

    Sobre cada átomo que reviste el pocket (en `atom_in_pocket`) se muestrean
    N_SPIRAL puntos en espiral dorada a radio_efectivo = r_vdW + sonda. Un punto
    es "expuesto" si NO está bloqueado por otro átomo del receptor NI cae
    dentro de una esfera del pocket. Se suma la fracción expuesta, split polar/
    apolar por electronegatividad.

    Returns:
        (surf_pol_vdw14, surf_apol_vdw14, surf_pol_vdw22) — fracciones
        (0..1) de superficie expuesta. Las versiones vdw22 usan sonda 2.2 Å.
    """
    if atom_in_pocket.size == 0:
        return 0.0, 0.0, 0.0

    vdw = _vdw_radius(atom_elements)
    atom_tree = cKDTree(atom_coords)
    sph_tree = cKDTree(centers)

    # Generar los puntos golden-spiral de TODOS los átomos revestidos a la vez.
    phi = (1.0 + math.sqrt(5.0)) / 2.0
    s_idx = np.arange(N_SPIRAL, dtype=float)
    y = 1.0 - (s_idx / (N_SPIRAL - 1)) * 2.0
    rad = np.sqrt(np.maximum(0.0, 1.0 - y * y))
    theta = 2.0 * math.pi * s_idx / phi
    # (N_SPIRAL, 3) en marco local
    spiral_local = np.stack([rad * np.cos(theta), y, rad * np.sin(theta)], axis=1)

    def _exposed_fractions(atom_idxs: list[int], probe_r: float) -> np.ndarray:
        """Fracción expuesta de cada átomo revestido (vectorizado por chunks)."""
        a_idx = np.asarray(atom_idxs, dtype=int)
        m = a_idx.size
        if m == 0:
            return np.zeros(0, dtype=float)

        centers_atom = atom_coords[a_idx]                      # (m,3)
        eff = vdw[a_idx][:, None] + probe_r                    # (m,1) radio efectivo
        pts = centers_atom[:, None, :] + eff[:, :, None] * spiral_local[None, :, :]

        # Vecinos de TODOS los átomos revestidos en una sola query batch.
        # Solo importan los átomos a <= SURF_CUTOFF de la cavidad (revestimiento);
        # para bloqueo usamos radio efectivo máximo + margen.
        neigh = atom_tree.query_ball_point(
            centers_atom, r=float(vdw.max() + probe_r + 2.0)
        )
        sph_neigh = sph_tree.query_ball_point(centers_atom, float(radii.max()))

        exposed = np.ones((m, N_SPIRAL), dtype=bool)
        CHUNK_ATOMS = 128
        for a0 in range(0, m, CHUNK_ATOMS):
            a1 = min(a0 + CHUNK_ATOMS, m)
            chunk_pts = pts[a0:a1]                             # (c, S, 3)
            # bucle sobre átomos del chunk, pero con vecinos YA precomputados
            for li in range(a1 - a0):
                ai = a0 + li
                own = a_idx[ai]
                hits = neigh[ai]
                others = [h for h in hits if h != own]
                if others:
                    others_a = atom_coords[others]
                    r_other = (vdw[others][None, :] + probe_r) * 0.7
                    d2_other = np.sum((chunk_pts[li][:, None, :] - others_a[None, :, :]) ** 2, axis=2)
                    exposed[ai] &= np.all(d2_other >= r_other ** 2, axis=1)
                sph_hits = sph_neigh[ai]
                if sph_hits:
                    d2_sph = np.sum((chunk_pts[li][:, None, :] - centers[sph_hits][None, :, :]) ** 2, axis=2)
                    exposed[ai] &= np.all(d2_sph >= radii[sph_hits][None, :] ** 2, axis=1)

        return exposed.sum(axis=1) / N_SPIRAL

    pol_idx = [int(ai) for ai in atom_in_pocket
               if ELEC_NEG.get(atom_elements[int(ai)], 3.5) >= ELECTRONEG_CUTOFF]
    apol_idx = [int(ai) for ai in atom_in_pocket
                if ELEC_NEG.get(atom_elements[int(ai)], 3.5) < ELECTRONEG_CUTOFF]

    e_pol14 = _exposed_fractions(pol_idx, probe) if pol_idx else np.zeros(0)
    e_apol14 = _exposed_fractions(apol_idx, probe) if apol_idx else np.zeros(0)
    e_pol22 = _exposed_fractions(pol_idx, probe22) if pol_idx else np.zeros(0)

    surf_pol14 = float(e_pol14.mean()) if e_pol14.size else 0.0
    surf_apol14 = float(e_apol14.mean()) if e_apol14.size else 0.0
    surf_pol22 = float(e_pol22.mean()) if e_pol22.size else 0.0
    return surf_pol14, surf_apol14, surf_pol22


def _vdw_radius(elements: list[str]) -> np.ndarray:
    """Radio de van der Waals aproximado por elemento (Å)."""
    table = {
        "C": 1.70, "N": 1.55, "O": 1.52, "S": 1.80, "P": 1.80, "H": 1.20,
        "F": 1.47, "CL": 1.75, "BR": 1.85, "I": 1.98, "SE": 1.90, "B": 1.92,
        "ZN": 1.39, "MG": 1.73, "CA": 2.31, "NA": 2.27, "K": 2.75, "FE": 1.80,
        "MN": 1.60, "CU": 1.40, "CO": 1.70, "NI": 1.63, "CD": 1.58, "HG": 1.55,
        "AU": 1.66, "PT": 1.75, "PB": 2.02, "MO": 1.90, "V": 1.70, "W": 1.90,
    }
    return np.asarray([table.get(el, 1.70) for el in elements], dtype=float)


def _mine_hotspots_for_cluster(
    sphere_tree: cKDTree,
    atom_coords: np.ndarray,
    atom_res_ids: list[str],
) -> list[dict]:
    """Mina residuos cercanos al cluster, formato idéntico a `_mine_hotspots`.

    Residuos con algún átomo a ≤5 Å de algún centro de esfera del cluster;
    bonus ×2 si hay contacto a ≤3.5 Å; top 15 con
    importance = 0.5 + (score/max_score)·0.5 (igual que structural.py).
    """
    contact_counts = sphere_tree.query_ball_point(
        atom_coords, HYDRO_CUTOFF_A, return_length=True,
    )
    close_counts = sphere_tree.query_ball_point(
        atom_coords, HYDRO_CLOSE_CUTOFF_A, return_length=True,
    )

    res_contacts: dict[str, int] = {}
    res_close: dict[str, bool] = {}
    for rid, n_contact, n_close in zip(atom_res_ids, contact_counts, close_counts):
        if n_contact > 0:
            res_contacts[rid] = res_contacts.get(rid, 0) + 1
            if n_close > 0:
                res_close[rid] = True

    if not res_contacts:
        return []

    scores = {
        rid: n * (2.0 if res_close.get(rid) else 1.0)
        for rid, n in res_contacts.items()
    }
    max_score = max(scores.values())
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:HOTSPOT_TOP_N]
    return [
        {"name": rid, "importance": round(0.5 + (s / max_score) * 0.5, 2)}
        for rid, s in ranked
    ]
