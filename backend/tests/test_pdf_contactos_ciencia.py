"""Caza 1 (2026-11-12), arreglos de ciencia, tanda 2: el mapa de contactos del informe dice lo que midió.

`compute_residue_interactions` llamaba «Salt Bridge» a cualquier ASP/GLU/ARG/LYS junto a un N u O del ligando (en 4NY4, dos ARG con un
ligando dicatión), no evaluaba el puente salino si ya había un enlace de hidrógeno (el GLU312 de VMAT2 con la amina catiónica salía
sólo como «H-Bond»), llamaba enlace de hidrógeno a cualquier par N/O/F a menos de 3,2 Å (aceptor con aceptor incluido) y rotulaba la
distancia mínima de TODO el residuo, hidrógenos del receptor incluidos (2,02 Å en E12 frente a 3,2 Å para el mismo ligando sin ellos).
Cada prueba construye un ligando y un receptor de coordenadas conocidas y lee lo que sale impreso.
"""
from __future__ import annotations

import re

import pytest
from rdkit import Chem
from rdkit.Chem import AllChem

from services.blockchain.pdf_generator import compute_residue_interactions


def _ligando(smiles: str):
    m = Chem.AddHs(Chem.MolFromSmiles(smiles))
    AllChem.EmbedMolecule(m, randomSeed=11)
    AllChem.MMFFOptimizeMolecule(m)
    return m


def _sdf(m) -> str:
    return Chem.MolToMolBlock(m) + "$$$$\n"


def _pos(m, idx):
    p = m.GetConformer().GetAtomPosition(idx)
    return p.x, p.y, p.z


def _linea(serie, nombre, res, num, xyz, elemento, cadena="A", registro="ATOM  "):
    x, y, z = xyz
    return f"{registro}{serie:5d} {nombre:<4s} {res:>3s} {cadena}{num:4d}    {x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00          {elemento:>2s}\n"


def _receptor(*atomos) -> str:
    """Cada átomo: (nombre, residuo, número, xyz, elemento)."""
    return "".join(_linea(i + 1, *a) for i, a in enumerate(atomos))


def _tipos(contactos):
    return {c["residue"]: c["type"] for c in contactos}


def _distancia(contactos, residuo) -> float:
    return float(next(c for c in contactos if c["residue"] == residuo)["distance"].split()[0])


def _a(m, idx, distancia, direccion=(1.0, 0.0, 0.0)):
    x, y, z = _pos(m, idx)
    return x + distancia * direccion[0], y + distancia * direccion[1], z + distancia * direccion[2]


# ── B01 / B02: puente salino sólo entre cargas de signo contrario, y sin quitárselo al enlace de hidrógeno ────────


def test_arg_no_forma_puente_salino_con_un_cation_y_asp_si():
    amonio = _ligando("C[NH3+]")
    n = next(a.GetIdx() for a in amonio.GetAtoms() if a.GetSymbol() == "N")
    receptor = _receptor(
        ("NH1", "ARG", 10, _a(amonio, n, 3.3, (0, 1, 0)), "N"),     # catión junto a catión: no es un puente salino
        ("OD1", "ASP", 20, _a(amonio, n, 2.8, (-1, 0, 0)), "O"),    # carboxilato junto al catión: sí, y además acepta el H
    )
    tipos = _tipos(compute_residue_interactions(receptor, _sdf(amonio)))
    assert "Salt Bridge" not in tipos["ARG10 (A)"] and "H-Bond" not in tipos["ARG10 (A)"], tipos
    assert set(tipos["ASP20 (A)"].split("/")) == {"H-Bond", "Salt Bridge"}, tipos   # B02: los dos, no uno solo


def test_un_anion_forma_puente_salino_con_arg_y_lys():
    acetato = _ligando("CC(=O)[O-]")
    o = next(a.GetIdx() for a in acetato.GetAtoms() if a.GetSymbol() == "O")
    receptor = _receptor(("NH2", "ARG", 5, _a(acetato, o, 3.4), "N"),
                         ("NZ", "LYS", 6, _a(acetato, o, 3.6, (0, 1, 0)), "N"))
    tipos = _tipos(compute_residue_interactions(receptor, _sdf(acetato)))
    assert "Salt Bridge" in tipos["ARG5 (A)"] and "Salt Bridge" in tipos["LYS6 (A)"], tipos


def test_un_ligando_neutro_no_forma_puentes_salinos():
    amida = _ligando("CC(=O)NC")
    o = next(a.GetIdx() for a in amida.GetAtoms() if a.GetSymbol() == "O")
    receptor = _receptor(("OD1", "ASP", 7, _a(amida, o, 3.5), "O"), ("NH1", "ARG", 8, _a(amida, o, 3.5, (0, 1, 0)), "N"))
    assert all("Salt Bridge" not in t for t in _tipos(compute_residue_interactions(receptor, _sdf(amida))).values())


# ── B03: enlace de hidrógeno = un donante y un aceptor ─────────────────────────────────────────────────────────


def test_dos_aceptores_no_son_un_enlace_de_hidrogeno():
    acetona = _ligando("CC(=O)C")
    o = next(a.GetIdx() for a in acetona.GetAtoms() if a.GetSymbol() == "O")
    receptor = _receptor(("O", "GLY", 3, _a(acetona, o, 2.9), "O"))      # O de la cadena principal: aceptor
    assert "H-Bond" not in _tipos(compute_residue_interactions(receptor, _sdf(acetona)))["GLY3 (A)"]


def test_un_donante_del_ligando_con_un_aceptor_del_receptor_si_lo_es():
    metanol = _ligando("CO")
    o = next(a.GetIdx() for a in metanol.GetAtoms() if a.GetSymbol() == "O")
    receptor = _receptor(("O", "GLY", 3, _a(metanol, o, 2.8), "O"))
    contactos = compute_residue_interactions(receptor, _sdf(metanol))
    assert "H-Bond" in _tipos(contactos)["GLY3 (A)"]
    assert next(c for c in contactos if c["residue"] == "GLY3 (A)")["ligand_atoms"] == [o]


# ── B04: la distancia rotulada es la del par que se rotula, y sin hidrógenos ───────────────────────────────────


def test_la_distancia_no_cuenta_los_hidrogenos_del_receptor():
    metanol = _ligando("CO")
    o = next(a.GetIdx() for a in metanol.GetAtoms() if a.GetSymbol() == "O")
    receptor = _receptor(("OD1", "ASP", 20, _a(metanol, o, 2.8), "O"),
                         ("HD2", "ASP", 20, _a(metanol, o, 1.9, (0, 1, 0)), "H"))
    d = _distancia(compute_residue_interactions(receptor, _sdf(metanol)), "ASP20 (A)")
    assert d == pytest.approx(2.8, abs=0.02), f"la distancia impresa es {d}: contó el hidrógeno"


def test_la_distancia_de_un_enlace_de_hidrogeno_es_la_de_su_par_donante_aceptor():
    etanol = _ligando("CCO")
    o = next(a.GetIdx() for a in etanol.GetAtoms() if a.GetSymbol() == "O")
    c = next(a.GetIdx() for a in etanol.GetAtoms() if a.GetSymbol() == "C" and a.GetNeighbors()[0].GetSymbol() != "O"
             and all(v.GetSymbol() != "O" for v in a.GetNeighbors()))
    receptor = _receptor(("OG", "SER", 4, _a(etanol, o, 3.0), "O"),
                         ("CB", "SER", 4, _a(etanol, c, 2.9, (0, 0, 1)), "C"))   # un carbono más cerca que el O
    d = _distancia(compute_residue_interactions(receptor, _sdf(etanol)), "SER4 (A)")
    assert d == pytest.approx(3.0, abs=0.02), f"rotula {d}: es el mínimo del residuo, no el del enlace de hidrógeno"


# ── B15 (hallado al arreglar B01–B05): «Pi-Stacking» sin medir anillos ──────────────────────────────────────────


def _anillo_de_fenilalanina(ligando, altura, desplazamiento=0.0):
    """Los seis átomos del anillo de una PHE, paralelo al bencenilo y a `altura` Å de su plano (en su normal)."""
    import numpy as np

    anillo = [a.GetIdx() for a in ligando.GetAtoms() if a.GetIsAromatic()]
    puntos = np.array([_pos(ligando, i) for i in anillo])
    c = puntos.mean(axis=0)
    u = (puntos[0] - c) / np.linalg.norm(puntos[0] - c)
    n = np.cross(puntos[0] - c, puntos[1] - c)
    n /= np.linalg.norm(n)
    v = np.cross(n, u)
    nombres = ("CG", "CD1", "CE1", "CZ", "CE2", "CD2")
    return {nombre: tuple(c + altura * n + desplazamiento * u + 1.4 * (np.cos(k * np.pi / 3) * u + np.sin(k * np.pi / 3) * v))
            for k, nombre in enumerate(nombres)}, tuple(puntos[0] + 4.0 * n), tuple(c)


def test_un_carbono_cercano_de_una_phe_no_es_apilamiento_si_los_anillos_estan_lejos():
    benceno = _ligando("c1ccccc1")
    anillo, sobre_un_atomo, _ = _anillo_de_fenilalanina(benceno, 7.0)
    receptor = _receptor(*[(n, "PHE", 9, xyz, "C") for n, xyz in anillo.items()], ("CA", "PHE", 9, sobre_un_atomo, "C"))
    tipo = _tipos(compute_residue_interactions(receptor, _sdf(benceno)))["PHE9 (A)"]
    assert "Pi-Stacking" not in tipo, f"el CA de la cadena principal a 4 Å, con los anillos a 7 Å, salió como {tipo}"


def test_dos_anillos_a_4_angstroms_de_centroide_si_son_apilamiento():
    benceno = _ligando("c1ccccc1")
    anillo, _, _ = _anillo_de_fenilalanina(benceno, 3.9)
    receptor = _receptor(*[(n, "PHE", 9, xyz, "C") for n, xyz in anillo.items()])
    contactos = compute_residue_interactions(receptor, _sdf(benceno))
    assert "Pi-Stacking" in _tipos(contactos)["PHE9 (A)"]
    assert _distancia(contactos, "PHE9 (A)") == pytest.approx(3.9, abs=0.05)     # la de los centroides


# ── B05: el informe dice sobre qué estructura midió ────────────────────────────────────────────────────────────


def test_el_informe_dice_sobre_que_estructura_midio_los_contactos():
    pytest.importorskip("pypdf")
    from tests.test_pdf_informe_figuras_y_cuadros import _informe, _texto

    amonio = _ligando("C[NH3+]")
    n = next(a.GetIdx() for a in amonio.GetAtoms() if a.GetSymbol() == "N")
    receptor = _receptor(("OD1", "ASP", 20, _a(amonio, n, 2.8, (-1, 0, 0)), "O"))
    texto = re.sub(r"\s+", " ", _texto(_informe(smiles="C[NH3+]", pose_sdf=_sdf(amonio), receptor_pdb=receptor)))
    assert "ASP20 (A)" in texto
    assert "Contactos medidos sobre la estructura del receptor del caso, no sobre el PDBQT acoplado" in texto
