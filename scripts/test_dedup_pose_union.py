# -*- coding: utf-8 -*-
"""test_dedup_pose_union.py — tests sintéticos de MF-11 (entregable 9).

Verifica:
1. Fixture con 3 poses donde 2 son casi idénticas (RMSD < 2.0) → 2 clusters.
2. LABEL-BLIND: alterar los labels NO cambia el clustering (los candidatos
   dedup son byte-idénticos entre dos conjuntos de labels distintos).
3. Greedy: la pose se une al PRIMER cluster cuyo representante cumple el
   umbral (determinismo de la regla).
4. RMSD pose-vs-pose: None sin átomos comunes; métrica en marco fijo.
5. End-to-end con tempdirs: salidas correctas y determinismo byte a byte.
Solo biblioteca estándar.
"""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
import dedup_pose_union as du  # noqa: E402


def pdbqt_sintetico(atomos):
    """Construye un PDBQT sintético con columnas PDB fijas. atomos: [(serial,
    elem, x, y, z)]."""
    lineas = ["MODEL 1", "REMARK VINA RESULT:      -8.0      0.000      0.000",
              "ROOT"]
    for serial, elem, x, y, z in atomos:
        l = [" "] * 80
        l[0:6] = list("HETATM")
        l[6:11] = list(f"{serial:5d}")
        l[12:16] = list(f"{elem:<4s}")
        l[17:20] = list("UNL")
        l[22:26] = list(f"{1:4d}")
        l[30:38] = list(f"{x:8.3f}")
        l[38:46] = list(f"{y:8.3f}")
        l[46:54] = list(f"{z:8.3f}")
        l[54:60] = list("  1.00")
        l[60:66] = list("  0.00")
        l[66:76] = list("     0.000")
        l[76:78] = list(f"{elem:>2s}")
        lineas.append("".join(l).rstrip())
    lineas.append("ENDMDL")
    return "\n".join(lineas) + "\n"


def candidato(ident, pid, split, fuente, pdbqt_texto, score=-8.0):
    return {
        "identity": ident,
        "split": split,
        "pid": pid,
        "source": fuente,
        "file_stem": f"conf_{ident.split('|')[-2]}.out",
        "model_idx": int(ident.split("|")[-1]),
        "vina_score": score,
        "provenance_key": f"{pid}|{fuente}|stem",
        "geometry_source": "pdbqt",
        "pdbqt": pdbqt_texto,
    }


def label(ident, rmsd):
    return {"identity": ident, "rmsd": rmsd, "n_heavy": 6, "n_contacts_4": 3,
            "n_contacts_6": 4, "n_clashes": 0, "pose_score_variance": 0.1,
            "pose_score_range": 0.5}


ATOMOS_A = [(1, "C", 0.0, 0.0, 0.0), (2, "N", 1.0, 0.0, 0.0),
            (3, "O", 0.0, 1.0, 0.0), (4, "C", 0.0, 0.0, 1.0),
            (5, "H", 1.0, 1.0, 0.0), (6, "H", 0.0, 1.0, 1.0)]
ATOMOS_B = [(s, e, x + 0.05, y + 0.05, z + 0.05) for s, e, x, y, z in ATOMOS_A]
ATOMOS_C = [(s, e, x + 10.0, y + 10.0, z + 10.0) for s, e, x, y, z in ATOMOS_A]


class TestParseo(unittest.TestCase):
    def test_pesados_excluye_hidrogenos(self):
        coords, firma = du.parsear_atomos_pesados(pdbqt_sintetico(ATOMOS_A))
        self.assertEqual(len(coords), 4)  # 4 pesados, 2 H excluidos
        self.assertEqual(sorted(coords), [1, 2, 3, 4])

    def test_sin_coordenadas(self):
        coords, firma = du.parsear_atomos_pesados("MODEL 1\nENDMDL\n")
        self.assertEqual(coords, {})


class TestRmsdPocket(unittest.TestCase):
    def test_rmsd_casi_identico_menor_a_umbral(self):
        ca, _ = du.parsear_atomos_pesados(pdbqt_sintetico(ATOMOS_A))
        cb, _ = du.parsear_atomos_pesados(pdbqt_sintetico(ATOMOS_B))
        r = du.rmsd_pocket_pose_vs_pose(ca, cb)
        self.assertIsNotNone(r)
        self.assertLess(r, 0.2)
        self.assertLess(r, du.UMBRAL_RMSD)

    def test_rmsd_lejano_mayor_a_umbral(self):
        ca, _ = du.parsear_atomos_pesados(pdbqt_sintetico(ATOMOS_A))
        cc, _ = du.parsear_atomos_pesados(pdbqt_sintetico(ATOMOS_C))
        r = du.rmsd_pocket_pose_vs_pose(ca, cc)
        self.assertIsNotNone(r)
        self.assertGreater(r, du.UMBRAL_RMSD)

    def test_rmsd_none_sin_comunes(self):
        ca, _ = du.parsear_atomos_pesados(pdbqt_sintetico(ATOMOS_A))
        cd = {99: (1.0, 2.0, 3.0)}
        self.assertIsNone(du.rmsd_pocket_pose_vs_pose(ca, cd))


class TestClustering(unittest.TestCase):
    def _clusters_fixture(self):
        coords = {}
        for ident, atomos in [("train|x1|molflex|f0.out|0", ATOMOS_A),
                              ("train|x1|molflex|f1.out|0", ATOMOS_B),
                              ("train|x1|molflex|f2.out|0", ATOMOS_C)]:
            c, _ = du.parsear_atomos_pesados(pdbqt_sintetico(atomos))
            coords[ident] = c
        ids = sorted(coords)
        return ids, coords

    def test_dos_clusters_para_tres_poses(self):
        ids, coords = self._clusters_fixture()
        clusters = du.clustering_greedy(ids, coords)
        self.assertEqual(len(clusters), 2)
        self.assertEqual(clusters[0], ids[:2])  # A y B juntas
        self.assertEqual(clusters[1], [ids[2]])  # C sola

    def test_representante_es_primera_pose(self):
        ids, coords = self._clusters_fixture()
        clusters = du.clustering_greedy(ids, coords)
        self.assertEqual(clusters[0][0], ids[0])

    def test_greedy_une_al_primer_cluster(self):
        # A y B quedan en clusters distintos (RMSD 2.5 > umbral); D está a
        # <=2.0 de AMBOS representantes y debe unirse al PRIMER cluster (A).
        def un_atomo(x, y, z):
            return pdbqt_sintetico([(1, "C", x, y, z), (2, "H", x + 1.0, y, z)])

        coords = {}
        for ident, texto in [
            ("a|0", un_atomo(0.0, 0.0, 0.0)),
            ("b|0", un_atomo(2.5, 0.0, 0.0)),
            ("d|0", un_atomo(1.25, 0.0, 0.0)),
        ]:
            c, _ = du.parsear_atomos_pesados(texto)
            coords[ident] = c
        ids = sorted(coords)
        clusters = du.clustering_greedy(ids, coords)
        self.assertEqual(len(clusters), 2)
        self.assertEqual(clusters[0], ["a|0", "d|0"])
        self.assertEqual(clusters[1], ["b|0"])


class TestPipelineLabelBlind(unittest.TestCase):
    def _escribir_union(self, raiz: Path, labels_rmsd: dict):
        union = raiz / "union"
        union.mkdir(parents=True)
        ids_fuente = [
            ("train|x1|molflex|f0.out|0", ATOMOS_A),
            ("train|x1|molflex|f1.out|0", ATOMOS_B),
            ("train|x1|molflex|f2.out|0", ATOMOS_C),
        ]
        cands = [candidato(ident, "x1", "train", "molflex", pdbqt_sintetico(atomos))
                 for ident, atomos in ids_fuente]
        labels = [label(ident, labels_rmsd.get(ident, 5.0)) for ident, _ in ids_fuente]
        with open(union / "union_candidates_train.jsonl", "w",
                  encoding="utf-8", newline="\n") as fh:
            for c in cands:
                fh.write(json.dumps(c, ensure_ascii=False) + "\n")
        with open(union / "union_labels_train.jsonl", "w",
                  encoding="utf-8", newline="\n") as fh:
            for l in labels:
                fh.write(json.dumps(l, ensure_ascii=False) + "\n")
        for split in ("val",):
            for nombre in (f"union_candidates_{split}.jsonl",
                           f"union_labels_{split}.jsonl"):
                with open(union / nombre, "w", encoding="utf-8", newline="\n") as fh:
                    fh.write("")
        return union

    def _sha256(self, path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def test_label_blind_y_determinismo(self):
        labels_v1 = {
            "train|x1|molflex|f0.out|0": 1.0,   # A buena
            "train|x1|molflex|f1.out|0": 9.0,   # B mala
            "train|x1|molflex|f2.out|0": 5.0,   # C media
        }
        labels_v2 = {
            "train|x1|molflex|f0.out|0": 9.0,   # A ahora mala
            "train|x1|molflex|f1.out|0": 1.0,   # B ahora buena
            "train|x1|molflex|f2.out|0": 9.0,   # C mala
        }
        hashes_v1 = self._ejecutar(labels_v1)
        hashes_v2 = self._ejecutar(labels_v2)
        # LABEL-BLIND: los candidatos dedup deben ser byte-idénticos aunque
        # los labels (oráculo) cambien.
        self.assertEqual(hashes_v1["dedup_candidates_train.jsonl"],
                         hashes_v2["dedup_candidates_train.jsonl"])
        # Los labels y métricas SÍ pueden cambiar (evaluación del oráculo).
        self.assertNotEqual(hashes_v1["dedup_labels_train.jsonl"],
                            hashes_v2["dedup_labels_train.jsonl"])

    def _ejecutar(self, labels_rmsd: dict) -> dict:
        salidas: dict = {}
        with tempfile.TemporaryDirectory() as td:
            raiz = Path(td)
            union = self._escribir_union(raiz, labels_rmsd)
            out = raiz / "out"
            rc = du.correr(union, out)
            self.assertEqual(rc, 0, msg="correr() devolvió error")
            for nombre in ("dedup_candidates_train.jsonl", "dedup_labels_train.jsonl",
                           "per_complex.jsonl", "failures.jsonl", "metrics.json"):
                salidas[nombre] = self._sha256(out / nombre)
        return salidas

    def test_end_to_end_contenido(self):
        with tempfile.TemporaryDirectory() as td:
            raiz = Path(td)
            union = self._escribir_union(raiz, {
                "train|x1|molflex|f0.out|0": 1.0,
                "train|x1|molflex|f1.out|0": 9.0,
                "train|x1|molflex|f2.out|0": 5.0,
            })
            out = raiz / "out"
            rc = du.correr(union, out)
            self.assertEqual(rc, 0)
            cands = [json.loads(l) for l in
                     (out / "dedup_candidates_train.jsonl").read_text(
                         encoding="utf-8").splitlines()]
            self.assertEqual(len(cands), 2)  # 2 clusters
            self.assertEqual(cands[0]["identity"], "train|x1|molflex|f0.out|0")
            self.assertNotIn("rmsd", cands[0])
            labs = [json.loads(l) for l in
                    (out / "dedup_labels_train.jsonl").read_text(
                        encoding="utf-8").splitlines()]
            self.assertEqual(len(labs), 2)
            # El cluster de A+B: representante A (rmsd 1.0); cluster_best = A
            self.assertEqual(labs[0]["cluster_size"], 2)
            self.assertNotIn("cluster_best_rmsd", labs[0])
            metrics = json.loads((out / "metrics.json").read_text(encoding="utf-8"))
            self.assertEqual(metrics["global"]["n_antes"], 3)
            self.assertEqual(metrics["global"]["n_despues"], 2)
            self.assertEqual(metrics["global"]["n_complejos_perdidos"], 0)
            pc = [json.loads(l) for l in
                  (out / "per_complex.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual(pc[0]["n_antes"], 3)
            self.assertEqual(pc[0]["n_despues"], 2)
            self.assertTrue(pc[0]["coverage_antes"])
            self.assertTrue(pc[0]["coverage_despues"])

    def test_cluster_best_se_registra_si_el_mejor_no_es_representante(self):
        # B (miembro del cluster de A) es mejor que A → cluster_best en labels.
        with tempfile.TemporaryDirectory() as td:
            raiz = Path(td)
            union = self._escribir_union(raiz, {
                "train|x1|molflex|f0.out|0": 1.5,   # A rep, peor
                "train|x1|molflex|f1.out|0": 0.3,   # B mejor
                "train|x1|molflex|f2.out|0": 5.0,
            })
            out = raiz / "out"
            rc = du.correr(union, out)
            self.assertEqual(rc, 0)
            labs = [json.loads(l) for l in
                    (out / "dedup_labels_train.jsonl").read_text(
                        encoding="utf-8").splitlines()]
            primero = labs[0]
            self.assertEqual(primero["identity"], "train|x1|molflex|f0.out|0")
            self.assertEqual(primero["cluster_best_rmsd"], 0.3)
            self.assertEqual(primero["cluster_best_identity"],
                             "train|x1|molflex|f1.out|0")


if __name__ == "__main__":
    unittest.main(verbosity=2)
