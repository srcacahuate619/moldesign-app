#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_build_confirm_cohort.py — tests de regresión del pipeline D-RC-CONFIRM.

Cubre los fixes de las iteraciones 2 y 3:

  (a) cuotas_proporcionales: casos de referencia del resto mayor calculados a
      mano (el bug B2 repartía el remanente repetidamente al mismo bin y podía
      exceder el total).
  (b) similitud de receptores por CADENA: dos complejos sintéticos multicadena
      donde una cadena es idéntica y las otras no; la métrica por cadena debe
      dar >= 0.90 y la vieja concatenación de cadenas no lo daba (B1).
  (c) metales del pocket: PDB sintético con Zn a 3 Å (pocket), Zn a 6 Å (near)
      y Zn a 60 Å (remote) del ligando (B6).
  (d) clases químicas: oligo (>= 3 anillos con O), acíclico por InChIKey y
      Tanimoto de conteo con valores conocidos (B5/B7).
  (e) clusters de cadena con union-find COMPLETO (B1 intra-cohorte, iteración
      3): cadena de transición entre 6 complejos (pares consecutivos comparten
      cadena IDÉNTICA, ningún par no consecutivo supera 0.90) debe dar UNA
      componente; el viejo "primer dueño" los dividía en 6. Además, cadena
      idéntica exacta (sim = 1.0) entre dos complejos con otra cadena
      diferente debe unirlos.

Uso: python scripts/test_build_confirm_cohort.py   → imprime "OK" y sale 0.

Solo biblioteca estándar; importa las funciones puras de build_confirm_cohort
(RDKit solo se usa donde el propio módulo lo usa, p. ej. en (c) vía SDF).
"""

from __future__ import annotations

import os
import random
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import build_confirm_cohort as bcc  # noqa: E402

FALLOS: list[str] = []


def comprobar(condicion: bool, nombre: str, detalle: str = "") -> None:
    if not condicion:
        FALLOS.append(f"{nombre}: {detalle}")
        print(f"  FAIL {nombre}: {detalle}")
    else:
        print(f"  ok   {nombre}")


# ─────────────────────────── (a) cuotas de resto mayor ────────────────────────


def test_cuotas() -> None:
    print("(a) cuotas_proporcionales (resto mayor canónico)")
    casos = [
        # (disponibles, total, esperado)
        ({"a": 2, "b": 1, "c": 1}, 3, {"a": 1, "b": 1, "c": 1}),
        ({"a": 100, "b": 10}, 3, {"a": 2, "b": 1}),
        ({"a": 1, "b": 1, "c": 1}, 2, {"a": 1, "b": 1, "c": 0}),
        # total > inventario: el algoritmo puro reparte hasta total (el muestreo
        # acota después); empate de fracciones resuelto por nombre.
        ({"a": 1, "b": 1, "c": 1}, 5, {"a": 2, "b": 2, "c": 1}),
        ({"a": 57, "b": 7, "c": 3, "d": 2}, 10, {"a": 8, "b": 1, "c": 1, "d": 0}),
        ({"a": 3, "b": 2}, 100, {"a": 60, "b": 40}),
    ]
    for i, (disp, total, esperado) in enumerate(casos, start=1):
        got = bcc.cuotas_proporcionales(disp, total)
        nombre = f"caso {i} {disp} total={total}"
        comprobar(got == esperado, nombre, f"esperado {esperado}, obtenido {got}")
        comprobar(sum(got.values()) == total, nombre + " (suma exacta)",
                  f"suma={sum(got.values())}")
        if total <= sum(disp.values()):
            for b, v in got.items():
                comprobar(v <= disp[b], nombre + f" (no excede inventario {b})",
                          f"{b}={v} > {disp[b]}")


# ─────────────────────── (b) similitud por cadena (B1) ────────────────────────


def _seq_aleatoria(rng: random.Random, largo: int) -> str:
    aa = "ACDEFGHIKLMNPQRSTVWY"
    return "".join(rng.choice(aa) for _ in range(largo))


def _metrica_vieja_concatenacion(cads: dict[str, str]) -> str:
    """Reproduce la métrica de la iteración 1 (concatenación de cadenas)."""
    return "|".join(f"{c}:{s}" for c, s in sorted(cads.items()))


def test_cadenas() -> None:
    print("(b) similitud de receptor por cadena (B1)")
    rng = random.Random(7)
    x = _seq_aleatoria(rng, 150)
    y = _seq_aleatoria(rng, 150)
    z = _seq_aleatoria(rng, 150)
    comp_a = {"A": x, "B": y}
    comp_b = {"A": x, "B": z}
    sim, par = bcc.mejor_par_cadenas(comp_a, comp_b)
    comprobar(sim >= 0.90, "cadena idéntica entre complejos multicadena", f"sim={sim:.4f}")
    comprobar(par == ("A", "A"), "par correcto (A, A)", f"par={par}")
    # La métrica vieja (concatenación) NO alcanzaba 0.90: era el bug B1.
    s1 = _metrica_vieja_concatenacion(comp_a)
    s2 = _metrica_vieja_concatenacion(comp_b)
    vieja = bcc.solapamiento_kmers(bcc.kmers(s1), bcc.kmers(s2))
    comprobar(vieja < 0.90,
              "la concatenación vieja NO alcanza 0.90 (regresión B1)",
              f"vieja={vieja:.4f}")
    # Complejos sin cadenas relacionadas deben quedar por debajo del umbral.
    w = _seq_aleatoria(rng, 150)
    comp_c = {"A": z, "B": w}
    sim2, _ = bcc.mejor_par_cadenas(comp_a, comp_c)
    comprobar(sim2 < 0.90, "cadenas no relacionadas < 0.90", f"sim={sim2:.4f}")


# ─────────────────────────── (c) metales del pocket ───────────────────────────


def _linea_hetatm(serial: int, res: str, cad: str, resseq: int,
                  x: float, y: float, z: float, el: str, occ: float = 1.0) -> str:
    """Línea HETATM con columnas PDB exactas (elemento en 77:78)."""
    nombre = f" {el:<3s}"
    return (f"HETATM{serial:5d} {nombre:>4s} {res:>3s} {cad:1s}{resseq:4d}    "
            f"{x:8.3f}{y:8.3f}{z:8.3f}{occ:6.2f}{20.0:6.2f}          {el:>2s}")


def test_metales() -> None:
    print("(c) metales_pocket (B6)")
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        d = base / "0abc"
        d.mkdir()
        lineas = [
            _linea_hetatm(1, "ZN", "A", 500, 3.0, 0.0, 0.0, "ZN"),
            _linea_hetatm(2, "ZN", "A", 501, 6.0, 0.0, 0.0, "ZN"),
            _linea_hetatm(3, "ZN", "A", 502, 60.0, 0.0, 0.0, "ZN"),
        ]
        (d / "0abc_protein.pdb").write_text("\n".join(lineas) + "\n",
                                            encoding="utf-8")
        sdf = (
            "0abc_ligand\n  test\n\n  5  4  0  0  0  0  0  0  0  0999 V2000\n"
            "    0.0000    0.0000    0.0000 C   0  0  0  0  0\n"
            "    1.0900    0.0000    0.0000 H   0  0  0  0  0\n"
            "   -0.3633    1.0275    0.0000 H   0  0  0  0  0\n"
            "   -0.3633   -0.5138   -0.8896 H   0  0  0  0  0\n"
            "   -0.3633   -0.5138    0.8896 H   0  0  0  0  0\n"
            "  1  2  1  0\n  1  3  1  0\n  1  4  1  0\n  1  5  1  0\n"
            "M  END\n$$$$\n"
        )
        (d / "0abc_ligand.sdf").write_text(sdf, encoding="utf-8")
        res = bcc.metales_pocket(base, "0abc")
        comprobar(res["metales_pocket"] == ["ZN"],
                  "Zn a 3 Å cuenta como pocket", f"pocket={res['metales_pocket']}")
        comprobar(res["near"] == ["ZN"], "Zn a 6 Å es near", f"near={res['near']}")
        comprobar(res["remote"] == ["ZN"], "Zn a 60 Å es remote",
                  f"remote={res['remote']}")
        clases = {m["clase"] for m in res["detalle"]}
        comprobar(clases == {"pocket", "near", "remote"},
                  "tres clases distintas reportadas", f"clases={clases}")
        dists = {m["clase"]: m["distancia_min"] for m in res["detalle"]}
        comprobar(abs(dists.get("pocket", -1) - 3.0) < 1e-6, "distancia pocket = 3.0 Å",
                  f"d={dists.get('pocket')}")
        comprobar(abs(dists.get("remote", -1) - 60.0) < 1e-6, "distancia remote = 60.0 Å",
                  f"d={dists.get('remote')}")


# ─────────────────────── (d) química y Tanimoto de conteo ─────────────────────


def test_quimica() -> None:
    print("(d) clases químicas y Tanimoto de conteo (B5/B7)")
    if not bcc.RDKIT_OK:
        print("  skip (RDKit no disponible)")
        return
    from rdkit import Chem

    # Oligo heurístico: celobiosa extendida (3 anillos con O en el anillo).
    celo = Chem.MolFromSmiles("OCC1OC(O)C(O)C(O)C1OC1OC(CO)C(O)C(O)C1OC1OC(CO)C(O)C(O)C1O")
    if celo is not None:
        q = bcc.quimica_ligando(celo)
        comprobar(q["rings_with_o"] >= 3, "3 anillos con O detectados",
                  f"rings_with_o={q['rings_with_o']}")
        comprobar(q["scaffold_class"].startswith("oligo:"),
                  "clase oligo:<n>:<n> para oligosacárido",
                  f"clase={q['scaffold_class']}")
        comprobar(q["stratum"] == "oligo", "estrato oligo", f"stratum={q['stratum']}")

    # Acíclico: clase por connectivity InChIKey, estrato lipid si MW > 150.
    acic = Chem.MolFromSmiles("CCCCCCCCCCCCCCCCCC(=O)O")
    q = bcc.quimica_ligando(acic)
    comprobar(q["scaffold_class"].startswith("acyclic:"),
              "acíclico usa clase acyclic:<ik14>", f"clase={q['scaffold_class']}")
    comprobar(q["stratum"] in ("lipid", "fragment"), "estrato acíclico válido",
              f"stratum={q['stratum']}")

    # Péptido: >= 3 amidas.
    pep = Chem.MolFromSmiles("NCC(=O)NCC(=O)NCC(=O)NCC(=O)O")
    q = bcc.quimica_ligando(pep)
    comprobar(q["n_amide"] >= 3, "péptido con >= 3 amidas", f"n_amide={q['n_amide']}")
    comprobar(q["stratum"] == "peptide", "estrato peptide", f"stratum={q['stratum']}")

    # Tanimoto de conteo con valores conocidos.
    t = bcc.tanimoto_conteo({1: 2, 2: 1}, {1: 1, 2: 3})
    comprobar(abs(t - 0.4) < 1e-9, "tanimoto conteo {2,1} vs {1,3} = 0.4", f"t={t}")
    t2 = bcc.tanimoto_conteo({1: 5}, {1: 5})
    comprobar(abs(t2 - 1.0) < 1e-9, "tanimoto idénticos = 1.0", f"t={t2}")
    t3 = bcc.tanimoto_conteo({1: 5}, {2: 5})
    comprobar(t3 == 0.0, "tanimoto disjuntos = 0.0", f"t={t3}")


# ─────────────────── (e) clusters de cadena: union-find completo ───────────────


def test_clusters_cadenas() -> None:
    print("(e) clusters de cadena: union-find completo con cierre transitivo")
    rng = random.Random(11)
    base = _seq_aleatoria(rng, 260)
    # Cadena de transición: 6 complejos; cada par consecutivo comparte una
    # cadena IDÉNTICA (sim = 1.0); ningún par de ventanas distintas supera
    # 0.90, así que ningún par directo no-consecutivo tiene arista. El
    # "primer dueño" de la iteración 2 dejaba los 6 como singletons.
    ventanas = [base[i * 18:i * 18 + 130] for i in range(6)]
    for i in range(6):
        for j in range(i + 1, 6):
            o = bcc.solapamiento_kmers(bcc.kmers(ventanas[i]),
                                       bcc.kmers(ventanas[j]))
            comprobar(o < 0.90, f"ventanas {i}/{j} sin par directo >= 0.90",
                      f"o={o:.4f}")
    unidades = []
    for i in range(6):
        cads = {"A": ventanas[i], "B": _seq_aleatoria(rng, 130)}
        if i > 0:
            # Cadena idéntica compartida con el complejo anterior.
            cads["T"] = ventanas[i - 1]
        unidades.append((f"c{i}", cads))
    cl, tamanos, vecinos = bcc.clusters_cadenas(unidades)
    comprobar(len(tamanos) == 1, "6 complejos en UNA componente (transitiva)",
              f"tamanos={tamanos}")
    comprobar(tamanos == [6], "tamaño de componente = 6 (cap 3 aplicable)",
              f"tamanos={tamanos}")
    comprobar(1 in vecinos[0] and 0 not in vecinos[2] and 0 not in vecinos[3],
              "adyacencia: A~B sí, A~C/A~D no", f"vecinos[0]={sorted(vecinos[0])}")

    # Cadena idéntica exacta (sim = 1.0) entre dos complejos con otra cadena
    # distinta: deben unirse en una componente.
    x = _seq_aleatoria(rng, 150)
    p1 = _seq_aleatoria(rng, 150)
    p2 = _seq_aleatoria(rng, 150)
    cl2, tamanos2, vecinos2 = bcc.clusters_cadenas(
        [("a", {"A": x, "B": p1}), ("b", {"A": x, "B": p2})])
    comprobar(len(tamanos2) == 1 and tamanos2 == [2],
              "cadena idéntica (sim=1.0) une dos complejos",
              f"tamanos={tamanos2}")
    comprobar(1 in vecinos2[0] and 0 in vecinos2[1],
              "par directo 1.0 registrado como vecinos",
              f"vecinos2={vecinos2}")

    # Control: complejos sin relación quedan separados.
    y = _seq_aleatoria(rng, 150)
    z = _seq_aleatoria(rng, 150)
    cl3, tamanos3, vecinos3 = bcc.clusters_cadenas(
        [("a", {"A": x, "B": p1}), ("c", {"A": y, "B": z})])
    comprobar(tamanos3 == [1, 1], "sin relación → 2 componentes",
              f"tamanos={tamanos3}")
    comprobar(vecinos3[0] == set() and vecinos3[1] == set(),
              "sin relación → sin vecinos directos", f"vecinos3={vecinos3}")


def main() -> int:
    test_cuotas()
    test_cadenas()
    test_metales()
    test_quimica()
    test_clusters_cadenas()
    if FALLOS:
        print(f"\nFALLARON {len(FALLOS)} tests")
        return 1
    print("\nOK — todos los tests de build_confirm_cohort pasan")
    return 0


if __name__ == "__main__":
    sys.exit(main())
