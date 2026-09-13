# -*- coding: utf-8 -*-
"""test_dedup_pose_union_medoid.py — tests sintéticos de MF-11-R1.

Verifica:
1. MEDOID geométrico ≠ representante identity-first: el medoid (mínima suma de
   distancias) se elige correctamente y la fila de labels apunta al medoid.
2. Admisión por DIÁMETRO: una pose a <= U del representante pero a > U de otro
   miembro NO entra al cluster (a diferencia de la regla rep-based de MF-11).
3. Empate del medoid → identidad ascendente.
4. Ablation mejor-Vina-score da OTRO representante (distinto del medoid).
5. LABEL-BLIND: alterar labels deja los candidatos byte-idénticos.
6. Determinismo: dos corridas → salidas byte-idénticas.
7. Solo train: los archivos val de la unión se ignoran (incluso envenenados);
   ninguna salida contiene identidades val y no se generan archivos val.
8. Selección del umbral por la regla preregistrada (mayor válido).
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
import dedup_pose_union_medoid as dm  # noqa: E402


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
    return {"identity": ident, "rmsd": rmsd, "n_heavy": 1, "n_contacts_4": 1,
            "n_contacts_6": 1, "n_clashes": 0, "pose_score_variance": 0.1,
            "pose_score_range": 0.5}


def ident(n):
    return f"train|x1|molflex|f{n}.out|0"


def un_atomo(x):
    return pdbqt_sintetico([(1, "C", x, 0.0, 0.0)])


def _escribir_union(raiz: Path, rmsd_por_ident: dict, vina_por_ident: dict):
    """Fixture 1 complejo (x1) con 3 poses sobre el eje X: A(x=0), B(x=1),
    C(x=2). Distancias: d(A,B)=1, d(B,C)=1, d(A,C)=2."""
    union = raiz / "union"
    union.mkdir(parents=True)
    coords = {"0": 0.0, "1": 1.0, "2": 2.0}
    cands = [candidato(ident(n), "x1", "train", "molflex", un_atomo(coords[str(n)]),
                       score=vina_por_ident.get(ident(n), -8.0))
             for n in (0, 1, 2)]
    labels = [label(ident(n), rmsd_por_ident[ident(n)]) for n in (0, 1, 2)]
    with open(union / "union_candidates_train.jsonl", "w",
              encoding="utf-8", newline="\n") as fh:
        for c in cands:
            fh.write(json.dumps(c, ensure_ascii=False) + "\n")
    with open(union / "union_labels_train.jsonl", "w",
              encoding="utf-8", newline="\n") as fh:
        for l in labels:
            fh.write(json.dumps(l, ensure_ascii=False) + "\n")
    for nombre in ("union_candidates_val.jsonl", "union_labels_val.jsonl"):
        with open(union / nombre, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("{JSON INVALIDO ENVENENADO: este archivo NUNCA debe leerse}\n")
    return union


def _rmsd_v1():
    # A buena (1.0), B mala (9.0), C media (5.0) → cobertura antes OK.
    return {ident(0): 1.0, ident(1): 9.0, ident(2): 5.0}


def _rmsd_v2():
    # Labels alterados: A mala, B buena. Los candidatos deben ser idénticos.
    return {ident(0): 9.0, ident(1): 1.0, ident(2): 9.0}


def _vina():
    return {ident(0): -9.0, ident(1): -8.0, ident(2): -7.0}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TestMedoid(unittest.TestCase):
    def test_medoid_difiere_de_identity_first(self):
        # U=2.0: los 3 en un solo cluster (todas las distancias <= 2).
        # Medoid = B (suma 2) vs identity-first = A (suma 3).
        identidades = [ident(n) for n in (0, 1, 2)]
        coords = {}
        for n in (0, 1, 2):
            c, _ = dm.parsear_atomos_pesados(un_atomo(float(n)))
            coords[ident(n)] = c
        dmat = dm.matriz_distancias(identidades, coords)
        clusters = dm.clustering_diametro(identidades, dmat, 2.0)
        self.assertEqual(len(clusters), 1)
        self.assertEqual(clusters[0], identidades)
        self.assertEqual(dm.medoid_geometrico(clusters[0], dmat), ident(1))
        self.assertNotEqual(dm.medoid_geometrico(clusters[0], dmat), identidades[0])

    def test_empate_medoid_identidad_ascendente(self):
        # A(0), B(1), C(1): B y C empatan en suma (1) → gana B (identidad menor).
        coords = {}
        for n, x in (("0", 0.0), ("1", 1.0), ("2", 1.0)):
            c, _ = dm.parsear_atomos_pesados(un_atomo(x))
            coords[ident(n)] = c
        identidades = [ident(n) for n in ("0", "1", "2")]
        dmat = dm.matriz_distancias(identidades, coords)
        clusters = dm.clustering_diametro(identidades, dmat, 2.0)
        self.assertEqual(len(clusters), 1)
        self.assertEqual(dm.medoid_geometrico(clusters[0], dmat), ident("1"))

    def test_admision_diametro_no_rep_based(self):
        # A(0), B(1.9), C(-1.9), U=2.0: C está a 1.9 <= U del representante A,
        # pero a 3.8 > U del miembro B → NO entra (regla de diámetro). La regla
        # rep-based de MF-11 habría fusionado las 3 en un cluster.
        coords = {}
        for n, x in (("0", 0.0), ("1", 1.9), ("2", -1.9)):
            c, _ = dm.parsear_atomos_pesados(un_atomo(x))
            coords[ident(n)] = c
        identidades = [ident(n) for n in ("0", "1", "2")]
        dmat = dm.matriz_distancias(identidades, coords)
        clusters = dm.clustering_diametro(identidades, dmat, 2.0)
        self.assertEqual(len(clusters), 2)
        self.assertEqual(clusters[0], [ident("0"), ident("1")])
        self.assertEqual(clusters[1], [ident("2")])

    def test_ablation_vina_da_otro_representante(self):
        # Fixture A/B/C con vina A=-9 (mejor). En U=2.0 el medoid es B;
        # el representante mejor-Vina debe ser A.
        coords = {}
        for n in (0, 1, 2):
            c, _ = dm.parsear_atomos_pesados(un_atomo(float(n)))
            coords[ident(n)] = c
        identidades = [ident(n) for n in (0, 1, 2)]
        dmat = dm.matriz_distancias(identidades, coords)
        clusters = dm.clustering_diametro(identidades, dmat, 2.0)
        cands = {ident(n): candidato(ident(n), "x1", "train", "molflex",
                                     un_atomo(float(n)), score=_vina()[ident(n)])
                 for n in (0, 1, 2)}
        self.assertEqual(dm.medoid_geometrico(clusters[0], dmat), ident(1))
        self.assertEqual(dm.rep_mejor_vina(clusters[0], cands), ident(0))
        self.assertNotEqual(dm.medoid_geometrico(clusters[0], dmat),
                            dm.rep_mejor_vina(clusters[0], cands))


class TestPipeline(unittest.TestCase):
    def _ejecutar(self, raiz: Path, rmsd_por_ident: dict) -> dict:
        union = _escribir_union(raiz, rmsd_por_ident, _vina())
        out = raiz / "out"
        rc = dm.correr(union, out)
        self.assertEqual(rc, 0, msg="correr() devolvió error")
        salidas = {}
        for nombre in sorted(p.name for p in out.iterdir()):
            salidas[nombre] = _sha256(out / nombre)
        return salidas

    def test_label_blind_candidatos_identicos(self):
        with tempfile.TemporaryDirectory() as td:
            raiz = Path(td)
            h1 = self._ejecutar(raiz / "v1", _rmsd_v1())
            h2 = self._ejecutar(raiz / "v2", _rmsd_v2())
            for nombre in h1:
                if nombre.startswith("dedup_candidates_train_"):
                    self.assertEqual(h1[nombre], h2[nombre],
                                     msg=f"candidatos {nombre} cambian con labels")
            self.assertNotEqual(h1["dedup_labels_train_2.0.jsonl"],
                                h2["dedup_labels_train_2.0.jsonl"])

    def test_determinismo_dos_corridas(self):
        with tempfile.TemporaryDirectory() as td:
            raiz = Path(td)
            union = _escribir_union(raiz, _rmsd_v1(), _vina())
            out1 = raiz / "out1"
            out2 = raiz / "out2"
            self.assertEqual(dm.correr(union, out1), 0)
            self.assertEqual(dm.correr(union, out2), 0)
            nombres = sorted(p.name for p in out1.iterdir())
            self.assertEqual(nombres, sorted(p.name for p in out2.iterdir()))
            for nombre in nombres:
                self.assertEqual(_sha256(out1 / nombre), _sha256(out2 / nombre),
                                 msg=f"hash distinto en {nombre}")

    def test_solo_train_sin_val(self):
        with tempfile.TemporaryDirectory() as td:
            raiz = Path(td)
            union = _escribir_union(raiz, _rmsd_v1(), _vina())
            out = raiz / "out"
            self.assertEqual(dm.correr(union, out), 0)
            nombres = sorted(p.name for p in out.iterdir())
            self.assertFalse(any("val" in n for n in nombres))
            for nombre in nombres:
                texto = (out / nombre).read_text(encoding="utf-8")
                self.assertNotIn("|val", texto, msg=f"val en {nombre}")
                self.assertNotIn('"split": "val"', texto, msg=f"val en {nombre}")

    def test_end_to_end_seleccion_umbral(self):
        with tempfile.TemporaryDirectory() as td:
            raiz = Path(td)
            union = _escribir_union(raiz, _rmsd_v1(), _vina())
            out = raiz / "out"
            self.assertEqual(dm.correr(union, out), 0)

            cands = [json.loads(l) for l in
                     (out / "dedup_candidates_train_2.0.jsonl").read_text(
                         encoding="utf-8").splitlines()]
            self.assertEqual(len(cands), 1)
            # U=2.0: un solo cluster [A,B,C]; medoid = B.
            self.assertEqual(cands[0]["identity"], ident(1))
            self.assertNotIn("rmsd", cands[0])

            labs = [json.loads(l) for l in
                    (out / "dedup_labels_train_2.0.jsonl").read_text(
                        encoding="utf-8").splitlines()]
            self.assertEqual(len(labs), 1)
            self.assertEqual(labs[0]["identity"], ident(1))
            self.assertEqual(labs[0]["cluster_size"], 3)
            self.assertEqual(labs[0]["cluster_best_identity"], ident(0))
            self.assertEqual(labs[0]["cluster_best_rmsd"], 1.0)

            cands_15 = [json.loads(l) for l in
                        (out / "dedup_candidates_train_1.5.jsonl").read_text(
                            encoding="utf-8").splitlines()]
            self.assertEqual([c["identity"] for c in cands_15],
                             [ident(0), ident(2)])  # medoid de [A,B] = A; y C

            metrics = json.loads((out / "metrics.json").read_text(encoding="utf-8"))
            # U=2.0: medoid B (rmsd 9.0) pierde cobertura; ablation Vina (A) la conserva.
            r20 = metrics["por_umbral"]["2.0"]
            self.assertEqual(r20["n_perdidos"], 1)
            self.assertEqual(r20["complejos_perdidos"], ["train|x1"])
            self.assertFalse(r20["cumple"]["a_cero_perdidas"])
            self.assertEqual(r20["ablation_mejor_vina"]["cubiertos_despues"], 1)
            self.assertEqual(r20["ablation_mejor_vina"]["n_perdidos"], 0)
            # U=1.5: clusters [A,B],[C]; medoid A (rmsd 1.0) → 0 perdidos, cumple.
            r15 = metrics["por_umbral"]["1.5"]
            self.assertTrue(r15["cumple"]["a_cero_perdidas"])
            self.assertTrue(r15["cumple"]["b_degradacion_mediana"])
            self.assertTrue(r15["cumple"]["c_reduccion"])
            # U=1.0 también cumple; la regla elige el MAYOR → 1.5.
            self.assertEqual(metrics["seleccion_umbral"]["umbral_elegido"], 1.5)
            self.assertEqual(metrics["seleccion_umbral"]["umbral_per_complex"], 1.5)

            pc = [json.loads(l) for l in
                  (out / "per_complex.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(pc), 1)
            self.assertEqual(pc[0]["umbral"], 1.5)
            self.assertTrue(pc[0]["coverage_antes"])
            self.assertTrue(pc[0]["coverage_despues"])

            self.assertEqual((out / "failures.jsonl").read_text(encoding="utf-8"), "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
