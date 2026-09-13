"""
Tests del motor MolPocket (utils/pocket_detector.py) — R1/R2/R6 del spec.

Estrategia (sin RDKit, sin DB):
- PDBs sintéticos generados con helpers locales `_shell_pdb` y `_tetra_pdb`
  (patrón del repo: conftest no toca la DB).
- Los helpers internos (_parse_heavy_atoms, _circumspheres, _filter_spheres,
  _cluster_spheres) se ejercitan directamente para los casos unitarios;
  `detect_pockets` cubre el contrato público (nunca lanza, devuelve []).
- El scoring es logístico estilo fpocket (nas_norm intra-proteína, as_density,
  volumen, superficies enterradas); no usa Kyte-Doolittle como antes.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from utils.pocket_detector import (
    _circumspheres,
    _cluster_spheres,
    _filter_spheres,
    _parse_heavy_atoms,
    detect_pockets,
)


# ═════════════════════════════════════════════════════════════════════════════
# Helpers de PDB sintético
# ═════════════════════════════════════════════════════════════════════════════


def _atom_line(serial, atom_name, res_name, chain, res_seq, x, y, z, element):
    """Línea ATOM en formato PDB estándar (elemento en columnas 76-78)."""
    return (
        f"ATOM  {serial:5d} {atom_name:>4s} {res_name:>3s} {chain}{res_seq:4d}    "
        f"{x:8.3f}{y:8.3f}{z:8.3f}{1.00:6.2f}{52.27:6.2f}          {element:>2s}"
    )


def _shell_pdb(radius=6.5, n=60, thickness=3.0, center=(0.0, 0.0, 0.0),
               res_name="LEU", seed=0):
    """Cáscara esférica de átomos pesados (todos carbono).

    La pared tiene grosor `thickness` Å entre `radius - thickness` y `radius`;
    la cavidad interior (sin átomos) tiene radio ~`radius - thickness` y su
    centro es `center`. Residuo configurable (default LEU, hidrofóbico).
    """
    rng = np.random.default_rng(seed)
    r_inner = radius - thickness
    center_arr = np.asarray(center, dtype=float)

    pts: list[list[float]] = []
    while len(pts) < n:
        cand = rng.normal(size=(n * 2, 3))
        cand = cand / np.linalg.norm(cand, axis=1, keepdims=True)  # direcciones
        rad = rng.uniform(r_inner, radius, size=(n * 2, 1))
        cand = cand * rad + center_arr
        dist = np.linalg.norm(cand - center_arr, axis=1)
        ok = (dist >= r_inner) & (dist <= radius)
        pts.extend(cand[ok].tolist())

    lines = []
    for i, (x, y, z) in enumerate(np.asarray(pts[:n])):
        lines.append(_atom_line(i + 1, f"C{i % 10 + 1}", res_name, "A", i + 1,
                                x, y, z, "C"))
    return "\n".join(lines)


def _plate_pdb(n=60, center=(0.0, 0.0, 0.0), seed=0):
    """Monocapa plana de átomos (z = 0): superficie expuesta sin cavidad."""
    rng = np.random.default_rng(seed)
    pts2 = rng.uniform(-10.0, 10.0, size=(n, 2))
    pts = np.hstack([pts2, np.zeros((n, 1))]) + np.asarray(center)
    lines = []
    for i, (x, y, z) in enumerate(pts):
        lines.append(_atom_line(i + 1, f"C{i % 10 + 1}", "LEU", "A", i + 1,
                                x, y, z, "C"))
    return "\n".join(lines)


def _tetra_pdb(side=4.0, center=(0.0, 0.0, 0.0)):
    """Tetraedro regular de lado `side` Å centrado en `center` (4 átomos)."""
    s = side
    v = np.array([
        [0.0, 0.0, 0.0],
        [s, 0.0, 0.0],
        [s / 2, s * math.sqrt(3) / 2, 0.0],
        [s / 2, s * math.sqrt(3) / 6, s * math.sqrt(2.0 / 3.0)],
    ], dtype=float)
    v = v - v.mean(axis=0) + np.asarray(center, dtype=float)
    lines = []
    for i, (x, y, z) in enumerate(v):
        lines.append(_atom_line(i + 1, f"C{i + 1}", "LEU", "A", i + 1, x, y, z, "C"))
    return "\n".join(lines)


def _coords_of(pdb_text):
    """Coordenadas parseadas (primer retorno de _parse_heavy_atoms)."""
    return _parse_heavy_atoms(pdb_text)[0]


# ═════════════════════════════════════════════════════════════════════════════
# 1) Parseo: solo ATOM pesados
# ═════════════════════════════════════════════════════════════════════════════


class TestParseo:
    def test_solo_atom_pesados_excluye_h_y_hetatm(self):
        pdb = "\n".join([
            _atom_line(1, "N", "VAL", "A", 12, 69.243, 6.720, 25.322, "N"),
            _atom_line(2, "CA", "VAL", "A", 12, 70.588, 7.288, 25.258, "C"),
            _atom_line(3, "H", "VAL", "A", 12, 69.500, 6.900, 25.100, "H"),   # H → excluido
            _atom_line(4, "CB", "VAL", "A", 12, 70.860, 8.091, 23.920, "C"),
            "HETATM    5  O   HOH A  13      68.000   5.000  24.000  1.00 30.00           O",
        ])
        coords, res_names, res_ids, elements = _parse_heavy_atoms(pdb)
        assert coords.shape == (3, 3)
        assert res_names == ["VAL", "VAL", "VAL"]
        assert res_ids == ["A:VAL12", "A:VAL12", "A:VAL12"]
        assert elements == ["N", "C", "C"]
        np.testing.assert_allclose(coords[1], [70.588, 7.288, 25.258], atol=1e-3)

    def test_elemento_derivado_del_nombre_sin_columna_76_78(self):
        # PDB viejo sin columna de elemento: '1HG' → H (excluido), 'CA' → C
        pdb = "\n".join([
            _atom_line(1, "CA", "VAL", "A", 1, 1.0, 2.0, 3.0, ""),
            _atom_line(2, "1HG", "VAL", "A", 1, 1.1, 2.1, 3.1, ""),
        ])
        coords, _rn, _ri, elements = _parse_heavy_atoms(pdb)
        assert coords.shape == (1, 3)
        assert elements == ["C"]

    def test_coords_invalidas_se_descartan(self):
        pdb = "\n".join([
            _atom_line(1, "CA", "VAL", "A", 1, 1.0, 2.0, 3.0, "C"),
            "ATOM      2  CA  VAL A   1      INVALIDO          1.00 30.00           C",
        ])
        coords, _rn, _ri, _el = _parse_heavy_atoms(pdb)
        assert coords.shape == (1, 3)


# ═════════════════════════════════════════════════════════════════════════════
# 2) Circumspheres: tetraedro regular y degenerados
# ═════════════════════════════════════════════════════════════════════════════


class TestCircumspheres:
    def test_tetraedro_regular_radio_s_sqrt6_4(self):
        side = 4.0
        coords = _coords_of(_tetra_pdb(side=side, center=(5.0, -3.0, 2.0)))
        centers, radii, simplices = _circumspheres(coords)
        assert simplices.shape[0] == 1
        r_esperado = side * math.sqrt(6) / 4.0
        # Tolerancia 1e-3: el PDB sintético redondea coords a 3 decimales
        assert radii[0] == pytest.approx(r_esperado, rel=1e-3)
        np.testing.assert_allclose(centers[0], [5.0, -3.0, 2.0], atol=1e-3)

    def test_tetraedro_coplanar_sin_esferas(self):
        # 4 puntos exactamente coplanares (z = 0) → sin tetraedros válidos
        pdb = "\n".join([
            _atom_line(1, "C1", "LEU", "A", 1, 0.0, 0.0, 0.0, "C"),
            _atom_line(2, "C2", "LEU", "A", 2, 4.0, 0.0, 0.0, "C"),
            _atom_line(3, "C3", "LEU", "A", 3, 2.0, 3.5, 0.0, "C"),
            _atom_line(4, "C4", "LEU", "A", 4, 1.0, 2.0, 0.0, "C"),
        ])
        coords = _coords_of(pdb)
        centers, radii, simplices = _circumspheres(coords)
        assert centers.shape[0] == 0
        assert radii.shape[0] == 0


# ═════════════════════════════════════════════════════════════════════════════
# 3) Filtros: radio y exposición al solvente (hull)
# ═════════════════════════════════════════════════════════════════════════════


class TestFiltros:
    def test_filtro_radio_respeta_rango_min_max(self):
        """Unit: la máscara de _filter_spheres excluye radios fuera de [3.4, 6.2]."""
        coords = _coords_of(_shell_pdb(radius=6.5, thickness=3.0, n=60, seed=0))
        centers, radii, simplices = _circumspheres(coords)
        assert radii.size > 0
        mask = _filter_spheres(centers, radii, simplices, coords)
        assert mask.shape == radii.shape
        assert radii[mask].min() >= 3.4
        assert radii[mask].max() <= 6.2

    def test_cavidad_chica_no_genera_pocket(self):
        """Cavidad interior radio 1.5 Å < min_radius 3.4: sus esferas se filtran.

        Un cluster de cavidad real tiene ~50+ esferas (ver shell normal); los
        pockets espurios de tetraedros intra-pared del shell sintético tienen
        n_spheres <= 3. Ningún pocket grande ⇒ la cavidad no se detectó.
        """
        for seed in range(8):
            pdb = _shell_pdb(radius=4.5, thickness=3.0, n=60, seed=seed)
            pockets = detect_pockets(pdb, top_n=5)
            assert all(p.n_spheres < 15 for p in pockets)

    def test_cavidad_grande_no_genera_pocket(self):
        """Cavidad interior radio 7.5 Å > max_radius 6.2: sus esferas se filtran.

        Espurios del shell sintético: n_spheres <= 12. Ningún pocket grande
        ⇒ la cavidad grande no se detectó.
        """
        for seed in range(8):
            pdb = _shell_pdb(radius=10.5, thickness=3.0, n=60, seed=seed)
            pockets = detect_pockets(pdb, top_n=5)
            assert all(p.n_spheres < 15 for p in pockets)

    def test_monocapa_plana_sin_pockets(self):
        # Superficie plana expuesta: todos los tetraedros degenerados o expuestos
        assert detect_pockets(_plate_pdb(n=60)) == []

    def test_shell_esferico_detecta_pocket(self):
        pockets = detect_pockets(_shell_pdb(radius=6.5, thickness=3.0, n=60))
        assert len(pockets) >= 1


class TestClustering:
    def test_dos_cavidades_separadas_dos_clusters(self):
        pdb = "\n".join([
            _shell_pdb(radius=6.5, thickness=3.0, n=150, center=(0.0, 0.0, 0.0), seed=1),
            _shell_pdb(radius=6.5, thickness=3.0, n=150, center=(30.0, 0.0, 0.0), seed=2),
        ])
        pockets = detect_pockets(pdb, top_n=5)
        # Los clusters de cavidad real tienen ~15+ esferas; los artefactos del
        # shell (tetraedros intra-pared) forman clusters de 1-2 esferas.
        reales = [p for p in pockets if p.n_spheres >= 15]
        assert len(reales) == 2
        xs = sorted(p.center[0] for p in reales)
        assert xs[0] == pytest.approx(0.0, abs=2.0)
        assert xs[1] == pytest.approx(30.0, abs=2.0)

    def test_cluster_spheres_agrupa_por_solapamiento(self):
        # 2 esferas solapadas + 1 lejana → 2 clusters
        centers = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [50.0, 0.0, 0.0]])
        radii = np.array([4.0, 4.0, 4.0])
        clusters = _cluster_spheres(centers, radii)
        assert len(clusters) == 2
        sizes = sorted(len(c) for c in clusters)
        assert sizes == [1, 2]


# ═════════════════════════════════════════════════════════════════════════════
# 4) Scoring: logístico estilo fpocket (nas_norm intra-proteína)
# ═════════════════════════════════════════════════════════════════════════════


class TestScoring:
    def test_pocket_mas_grande_gana_por_nas_norm(self):
        """El score de fpocket premia al pocket más grande de la proteína.

        Dos cáscaras de distinto tamaño en la misma proteína: la cavidad más
        grande (más esferas → nas_norm mayor) debe obtener el mayor score.
        """
        pdb = "\n".join([
            _shell_pdb(radius=6.5, thickness=3.0, n=150, center=(0.0, 0.0, 0.0), seed=1),
            _shell_pdb(radius=8.5, thickness=3.0, n=220, center=(30.0, 0.0, 0.0), seed=2),
        ])
        pockets = detect_pockets(pdb, top_n=5)
        reales = [p for p in pockets if p.n_spheres >= 15]
        assert len(reales) >= 1
        # El de la derecha (30, 0, 0) es la cavidad más grande → score mayor
        xs = sorted((p.center[0], p.score) for p in reales)
        assert xs[-1][0] == pytest.approx(30.0, abs=2.0)
        assert xs[-1][1] == max(p.score for p in reales)

    def test_score_druggability_en_rango(self):
        pdb = _shell_pdb(radius=6.5, thickness=3.0, n=60, seed=7)
        p = detect_pockets(pdb, top_n=1)[0]
        assert 0.0 <= p.druggability <= 1.0


# ═════════════════════════════════════════════════════════════════════════════
# 5) Robustez y contrato público
# ═════════════════════════════════════════════════════════════════════════════


class TestRobustez:
    def test_pdb_vacio_devuelve_lista_vacia(self):
        assert detect_pockets("") == []
        assert detect_pockets("\n\n") == []

    def test_pdb_basura_no_lanza(self):
        assert detect_pockets("esto no es un pdb\nATOM garbage\nHETATM xyz") == []

    def test_menos_de_20_atomos_devuelve_vacio(self):
        # 4 átomos: por debajo del guard MIN_ATOMS_FOR_POCKET
        assert detect_pockets(_tetra_pdb(side=4.0)) == []

    def test_determinismo_dos_llamadas_identicas(self):
        pdb = _shell_pdb(radius=6.5, thickness=3.0, n=60, seed=3)
        assert detect_pockets(pdb) == detect_pockets(pdb)

    def test_top_n_respeta_orden_por_score(self):
        pdb = _shell_pdb(radius=6.5, thickness=3.0, n=60, seed=5)
        pockets = detect_pockets(pdb, top_n=2)
        assert len(pockets) <= 2
        scores = [p.score for p in pockets]
        assert scores == sorted(scores, reverse=True)


# ═════════════════════════════════════════════════════════════════════════════
# 6) E2E: shell de ~60 átomos
# ═════════════════════════════════════════════════════════════════════════════


class TestE2E:
    def test_shell_60_atomos_pocket_completo(self):
        pdb = _shell_pdb(radius=6.5, thickness=3.0, n=60, seed=11)
        pockets = detect_pockets(pdb, top_n=1)
        assert len(pockets) == 1
        p = pockets[0]

        # Centro ≈ centroide de la cavidad (±2 Å)
        assert abs(p.center[0]) <= 2.0
        assert abs(p.center[1]) <= 2.0
        assert abs(p.center[2]) <= 2.0

        # Campos poblados y en rango
        assert p.radius > 0.0
        assert p.volume > 0.0
        assert 0.0 <= p.score <= 1.0
        assert 0.0 <= p.druggability <= 1.0
        assert p.n_spheres >= 1

        # Hotspots: top 15, formato {name, importance}
        assert len(p.hotspots) <= 15
        for h in p.hotspots:
            assert set(h.keys()) == {"name", "importance"}
            assert 0.5 <= h["importance"] <= 1.0
            assert isinstance(h["name"], str)


# ═════════════════════════════════════════════════════════════════════════════
# 7) Re-ranking empírico (druggability + nas_norm + 0.3*hyd_norm)
# ═════════════════════════════════════════════════════════════════════════════


class TestReranking:
    def test_rank_score_atributo_interno(self):
        """El atributo rank_score (usado para ordenar) existe en cada pocket."""
        pdb = _shell_pdb(radius=6.5, thickness=3.0, n=60, seed=11)
        pockets = detect_pockets(pdb, top_n=3)
        assert len(pockets) >= 1
        for p in pockets:
            assert hasattr(p, "rank_score")
            assert isinstance(p.rank_score, float)

    def test_orden_descendente_por_rank_score(self):
        """Los pockets retornados están ordenados por rank_score desc."""
        pdb = _shell_pdb(radius=6.5, thickness=3.0, n=80, seed=5)
        pockets = detect_pockets(pdb, top_n=5)
        ranks = [p.rank_score for p in pockets]
        assert ranks == sorted(ranks, reverse=True)

    def test_druggability_en_rango(self):
        """druggability se conserva en [0,1] tras el re-rank."""
        pdb = _shell_pdb(radius=6.5, thickness=3.0, n=60, seed=11)
        pockets = detect_pockets(pdb, top_n=1)
        assert 0.0 <= pockets[0].druggability <= 1.0


# ═════════════════════════════════════════════════════════════════════════════
# 8) Fallback APO en discover_pocket_from_pdb (utils/structural.py)
# ═════════════════════════════════════════════════════════════════════════════


class TestApoFallback:
    def _apo_pdb(self) -> str:
        """Shell sin ligandos HETATM — estructura APO pura."""
        return _shell_pdb(radius=6.5, thickness=3.0, n=60, seed=11)

    def test_apo_sin_ligando_usa_molpocket(self):
        from utils.structural import discover_pocket_from_pdb
        res = discover_pocket_from_pdb(self._apo_pdb())
        assert res["success"] is True
        assert res.get("apo_molpocket") is True
        assert res["ligand_name"] == "APO"
        # Grid center poblado y grid size en rango físico
        cx, cy, cz = res["grid_center"]
        assert all(isinstance(v, (int, float)) for v in (cx, cy, cz))
        gx, gy, gz = res["grid_size"]
        assert 20.0 <= gx <= 50.0
        assert 20.0 <= gy <= 50.0
        assert 20.0 <= gz <= 50.0

    def test_apo_warning_informativo(self):
        from utils.structural import discover_pocket_from_pdb
        res = discover_pocket_from_pdb(self._apo_pdb())
        assert any("MolPocket" in w for w in res.get("warnings", []))

    def test_holo_con_ligando_no_usa_fallback(self):
        """PDB con HETATM drug-like sigue la rama normal (sin fallback APO)."""
        from utils.structural import discover_pocket_from_pdb
        # Shell + un HETATM "ligando" de 12 átomos (drug-like)
        lig_lines = []
        for i in range(12):
            lig_lines.append(
                f"HETATM{i + 1:5d}  L{i:2d} LIG A 100    "
                f"{i * 0.5:8.3f}{0.0:8.3f}{0.0:8.3f}  1.00 20.00          "
            )
        pdb = self._apo_pdb() + "\n" + "\n".join(lig_lines)
        res = discover_pocket_from_pdb(pdb)
        assert res["success"] is True
        assert not res.get("apo_molpocket")   # None → rama normal
        assert res.get("ligand_name") == "LIG"
