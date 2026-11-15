"""Controles con respuesta conocida del extractor de features que alimenta el SHAP.

La pestaña Explicabilidad dice qué contribuyó cada característica; si la
característica se calcula mal para un elemento concreto, el SHAP explica un
número equivocado con toda normalidad. Estos controles construyen entradas cuya
respuesta se conoce SIN usar el código bajo prueba:

  - la química de los 20 aminoácidos (tipado de la proteína);
  - geometría armada a mano con distancias exactas (capas, cortes, pares);
  - moléculas con SMILES conocido, preparadas con el mismo `mk_prepare_ligand`
    de producción, comparando el camino de entrenamiento (SDF) con el de
    inferencia (PDBQT) a igualdad de coordenadas;
  - salidas REALES de Vina (`backend/tests/fixtures/meeko_export`).

Qué detectó cada uno antes de corregir (medido el 2026-11-08):
  X09/X11  el boro y el silicio entraban como carbono (`shell_C_C_4_8` 175 → 199);
  X10      el exaltólido (C15H28O2, 17 átomos pesados) daba 19: dos pseudoátomos
           `G0` de cierre de macrociclo contados como carbono;
  X12      una línea PDBQT sin su espacio final perdía el átomo entero.

X08 documenta un límite que NO se corrige aquí (cambiaría la distribución con la
que se entrenó el modelo): `close_contacts_*` y `contacts_per_ha_*` cuentan
hidrógenos, así que dependen de cuántos traiga cada archivo.
"""

from __future__ import annotations

import random
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from feature_extractor import (  # noqa: E402
    ECIF_FEATURES,
    LIG_ECIF_TYPES,
    PROT_ECIF_TYPES,
    SHELL_FEATURES,
    _ad4_a_elemento,
    _assign_prot_ecif_type,
    _compute_ecif_features,
    _compute_shell_atom_counts,
    _get_conformer_coords,
    _load_protein_pdb,
)

Chem = pytest.importorskip("rdkit.Chem")
from rdkit.Geometry import Point3D  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _controles_xai import (  # noqa: E402
    colocar,
    construir_peptidos,
    escribir_sdf,
    extractor_geometrico,
    ligando_3d,
    modelos_pdbqt,
)

RAIZ = Path(__file__).resolve().parents[2]
FIXTURES = RAIZ / "backend" / "tests" / "fixtures" / "meeko_export"
HEAVY_KEYS = SHELL_FEATURES + ECIF_FEATURES + ["heavy_atom_count"]


# ─────────────────────────────────────────────────────────────────────────────
# Armado de entradas de control
# ─────────────────────────────────────────────────────────────────────────────


def _pdb_de_atomos_aislados(ruta: Path, atomos: list[tuple[str, tuple[float, float, float]]]) -> str:
    """Una «proteína» de átomos sueltos, cada uno en su residuo: la geometría es exacta
    y el tipo de cada átomo sólo depende de su elemento (sin vecinos, el N lleva H y es
    donador, el O también, el C es alifático)."""
    lineas = []
    for i, (el, (x, y, z)) in enumerate(atomos, 1):
        nombre = f" {el:<3s}" if len(el) == 1 else f"{el:<4s}"
        lineas.append(f"ATOM  {i:5d} {nombre[:4]} GLY A{i:4d}    {x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00          {el:>2s}")
    lineas.append("END")
    ruta.write_text("\n".join(lineas) + "\n")
    return str(ruta)


def _ligando_de_atomos(atomos: list[tuple[str, tuple[float, float, float]]]):
    m = Chem.RWMol()
    for el, _ in atomos:
        m.AddAtom(Chem.Atom(el))
    conf = Chem.Conformer(len(atomos))
    for i, (_, (x, y, z)) in enumerate(atomos):
        conf.SetAtomPosition(i, Point3D(x, y, z))
    m.AddConformer(conf)
    mol = m.GetMol()
    mol.UpdatePropertyCache(strict=False)
    return mol


def _geometricas(tmp_path: Path, prot_atomos, lig_atomos, nombre: str) -> dict[str, float]:
    """ECIF + capas, no nulas, de un ligando de átomos sueltos frente a una proteína de átomos sueltos."""
    pdb = _pdb_de_atomos_aislados(tmp_path / f"{nombre}.pdb", prot_atomos)
    prot = _load_protein_pdb(pdb)
    lig = _ligando_de_atomos(lig_atomos)
    pc, lc = _get_conformer_coords(prot), _get_conformer_coords(lig)
    f = {}
    f.update(_compute_shell_atom_counts(prot, lig, pc, lc))
    f.update(_compute_ecif_features(prot, lig, pc, lc))
    return {k: v for k, v in f.items() if v}


@pytest.fixture(scope="module")
def peptidos(tmp_path_factory):
    """Dos péptidos que juntos tienen los 20 aminoácidos, con y sin hidrógenos explícitos."""
    return construir_peptidos(tmp_path_factory)


# ─────────────────────────────────────────────────────────────────────────────
# X01 — el tipado de la proteína coincide con la química de los 20 aminoácidos
# ─────────────────────────────────────────────────────────────────────────────

# Tabla independiente del código: química de las cadenas laterales de un péptido NEUTRO
# (`MolFromSequence` deja COOH en Asp, Glu y el C-terminal, y NH2 en el N-terminal).
_LATERAL = {
    "ALA": {"CB": "C_ali"},
    "CYS": {"CB": "C_ali", "SG": "S"},
    "ASP": {"CB": "C_ali", "CG": "C_ali", "OD1": "O_acc", "OD2": "O_don"},
    "GLU": {"CB": "C_ali", "CG": "C_ali", "CD": "C_ali", "OE1": "O_acc", "OE2": "O_don"},
    "PHE": {"CB": "C_ali", **{a: "C_aro" for a in ("CG", "CD1", "CD2", "CE1", "CE2", "CZ")}},
    "GLY": {},
    "HIS": {"CB": "C_ali", "CG": "C_aro", "CD2": "C_aro", "CE1": "C_aro", "ND1": "N_acc", "NE2": "N_don"},
    "ILE": {"CB": "C_ali", "CG1": "C_ali", "CG2": "C_ali", "CD1": "C_ali"},
    "LYS": {"CB": "C_ali", "CG": "C_ali", "CD": "C_ali", "CE": "C_ali", "NZ": "N_don"},
    "LEU": {"CB": "C_ali", "CG": "C_ali", "CD1": "C_ali", "CD2": "C_ali"},
    "MET": {"CB": "C_ali", "CG": "C_ali", "SD": "S", "CE": "C_ali"},
    "ASN": {"CB": "C_ali", "CG": "C_ali", "OD1": "O_acc", "ND2": "N_don"},
    "PRO": {"CB": "C_ali", "CG": "C_ali", "CD": "C_ali"},
    "GLN": {"CB": "C_ali", "CG": "C_ali", "CD": "C_ali", "OE1": "O_acc", "NE2": "N_don"},
    "ARG": {"CB": "C_ali", "CG": "C_ali", "CD": "C_ali", "NE": "N_don", "CZ": "C_ali", "NH1": "N_don", "NH2": "N_don"},
    "SER": {"CB": "C_ali", "OG": "O_don"},
    "THR": {"CB": "C_ali", "OG1": "O_don", "CG2": "C_ali"},
    "VAL": {"CB": "C_ali", "CG1": "C_ali", "CG2": "C_ali"},
    "TRP": {"CB": "C_ali", **{a: "C_aro" for a in ("CG", "CD1", "CD2", "CE2", "CE3", "CZ2", "CZ3", "CH2")}, "NE1": "N_don"},
    "TYR": {"CB": "C_ali", **{a: "C_aro" for a in ("CG", "CD1", "CD2", "CE1", "CE2", "CZ")}, "OH": "O_don"},
}


def _tipo_esperado(resname: str, atomo: str) -> str:
    if atomo == "N":
        return "N_acc" if resname == "PRO" else "N_don"
    if atomo in ("CA", "C"):
        return "C_ali"
    if atomo == "O":
        return "O_acc"
    if atomo == "OXT":  # C-terminal neutro: COOH
        return "O_don"
    return _LATERAL[resname][atomo]


@pytest.mark.parametrize("hidrogenos", ["h", "noh"], ids=["con_H_explicitos", "sin_H"])
def test_x01_tipado_de_proteina_coincide_con_la_quimica_de_los_20_aminoacidos(peptidos, hidrogenos):
    revisados, fallos, residuos = 0, [], set()
    for pep in peptidos.values():
        prot = _load_protein_pdb(pep[hidrogenos])
        for a in prot.GetAtoms():
            if a.GetAtomicNum() <= 1:
                continue
            ri = a.GetPDBResidueInfo()
            rn, an = ri.GetResidueName(), ri.GetName().strip()
            residuos.add(rn)
            revisados += 1
            obtenido, esperado = _assign_prot_ecif_type(a), _tipo_esperado(rn, an)
            if obtenido != esperado:
                fallos.append((rn, ri.GetResidueNumber(), an, obtenido, esperado))
    assert len(residuos) == 20, f"el control debe cubrir los 20 aminoácidos, cubre {sorted(residuos)}"
    assert revisados > 150
    assert fallos == [], f"átomos mal tipados: {fallos}"


def test_x01_el_mismo_receptor_con_y_sin_hidrogenos_da_las_mismas_ecif_y_capas(peptidos):
    """Un receptor protonado y el mismo sin hidrógenos describen la MISMA proteína: sus ECIF y sus
    capas deben coincidir. Antes, con los hidrógenos escritos como átomos, todo N y todo O salía
    «aceptor» y las `ecif_N_don_*` y `ecif_O_don_*` valían cero (medido en 5TBO, 8ZP2 y 1BN1)."""
    for nombre, pep in peptidos.items():
        con_h, sin_h = _load_protein_pdb(pep["h"]), _load_protein_pdb(pep["noh"])
        pesados = pep["mol"].GetConformer().GetPositions()[[a.GetIdx() for a in pep["mol"].GetAtoms() if a.GetAtomicNum() > 1]]
        lig = colocar(ligando_3d("CC(=O)NC"), pesados.mean(axis=0), (0.0, 0.0, 0.0))
        lc = _get_conformer_coords(lig)
        resultados = []
        for prot in (con_h, sin_h):
            f = {}
            f.update(_compute_shell_atom_counts(prot, lig, _get_conformer_coords(prot), lc))
            f.update(_compute_ecif_features(prot, lig, _get_conformer_coords(prot), lc))
            resultados.append({k: v for k, v in f.items() if v})
        distintos = {k: (resultados[0].get(k, 0), resultados[1].get(k, 0)) for k in set(resultados[0]) | set(resultados[1])
                     if resultados[0].get(k, 0) != resultados[1].get(k, 0)}
        assert distintos == {}, f"péptido {nombre}: con H explícitos / sin H difieren en {distintos}"
        donadores = sum(v for k, v in resultados[1].items() if k.startswith(("ecif_N_don_", "ecif_O_don_")))
        assert donadores > 0, "el control sería vacuo: el ligando no toca ningún donador de la proteína"


# ─────────────────────────────────────────────────────────────────────────────
# X02 — en ecif_{proteína}_{ligando} y shell_{proteína}_{ligando}_… manda la proteína primero
# ─────────────────────────────────────────────────────────────────────────────

_PROT = [("N", (0.0, 0.0, 0.0)), ("O", (30.0, 0.0, 0.0)), ("C", (60.0, 0.0, 0.0)), ("S", (90.0, 0.0, 0.0))]


@pytest.mark.parametrize(
    "lig_el,x,ecif_esperado,shell_esperado",
    [
        ("O", 3.0, "ecif_N_don_O", "shell_N_O_0_4"),      # N con H de la proteína · O del ligando
        ("N", 33.0, "ecif_O_don_N", "shell_O_N_0_4"),     # O con H de la proteína · N del ligando
        ("O", 63.0, "ecif_C_ali_O", "shell_C_O_0_4"),     # C alifático de la proteína · O del ligando
        ("F", 63.0, "ecif_C_ali_F", "shell_C_F_0_4"),
        ("Cl", 93.0, "ecif_S_Hal", "shell_S_Cl_0_4"),     # Cl, Br e I se agrupan como «Hal» en ECIF
        ("P", 3.0, "ecif_N_don_other", "shell_N_P_0_4"),  # P del ligando: «other» en ECIF, propio en capas
    ],
)
def test_x02_el_primer_elemento_del_nombre_es_el_de_la_proteina(tmp_path, lig_el, x, ecif_esperado, shell_esperado):
    f = _geometricas(tmp_path, _PROT, [(lig_el, (x, 0.0, 0.0))], f"x02_{lig_el}_{int(x)}")
    assert f == {ecif_esperado: 1.0, shell_esperado: 1.0}, f


def test_x02_ningun_nombre_ecif_empieza_por_un_tipo_que_solo_exista_en_el_ligando():
    protein_types, ligand_types = set(PROT_ECIF_TYPES), set(LIG_ECIF_TYPES)
    for nombre in ECIF_FEATURES:
        m = re.fullmatch(r"ecif_(C_ali|C_aro|N_don|N_acc|O_don|O_acc|S|other)_(C|N|O|S|F|Hal|other)", nombre)
        assert m, nombre
        assert m.group(1) in protein_types and m.group(2) in ligand_types
    # `Hal` y `F` son tipos de ligando: ninguna clave puede empezar por ellos.
    assert not [n for n in ECIF_FEATURES if n.startswith(("ecif_Hal_", "ecif_F_"))]


# ─────────────────────────────────────────────────────────────────────────────
# X03 — las capas de distancia son [desde, hasta), con distancias exactas
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "d,capa",
    [(3.9, "shell_C_C_0_4"), (4.0, "shell_C_C_4_8"), (7.9, "shell_C_C_4_8"),
     (8.0, "shell_C_C_8_12"), (11.9, "shell_C_C_8_12"), (12.0, None)],
)
def test_x03_capas_de_distancia_son_semiabiertas(tmp_path, d, capa):
    f = _geometricas(tmp_path, [("C", (0.0, 0.0, 0.0))], [("C", (d, 0.0, 0.0))], f"x03_{d}")
    esperado = {capa: 1.0} if capa else {}
    assert {k: v for k, v in f.items() if k.startswith("shell_")} == esperado


# ─────────────────────────────────────────────────────────────────────────────
# X04/X05 — son conteos de PARES (no densidades) y ECIF corta a 6 Å, las capas no
# ─────────────────────────────────────────────────────────────────────────────


def test_x04_las_capas_cuentan_pares_no_una_densidad(tmp_path):
    prot = [("C", (0.0, 0.0, 0.0)), ("C", (0.0, 0.0, 1.0))]
    lig = [("C", (5.0, 0.0, 0.0)), ("C", (5.0, 1.0, 0.0)), ("C", (5.0, -1.0, 0.0))]
    f = _geometricas(tmp_path, prot, lig, "x04")
    assert f["shell_C_C_4_8"] == 6.0  # 2 átomos de proteína × 3 del ligando
    assert f["ecif_C_ali_C"] == 6.0


def test_x05_ecif_corta_a_6_angstrom_y_las_capas_llegan_a_12(tmp_path):
    f = _geometricas(tmp_path, [("N", (0.0, 0.0, 0.0))], [("C", (5.9, 0.0, 0.0)), ("C", (6.1, 0.0, 0.0))], "x05")
    assert f["ecif_N_don_C"] == 1.0           # sólo el de 5,9 Å
    assert f["shell_N_C_4_8"] == 2.0          # los dos caen en la capa 4–8 Å


# ─────────────────────────────────────────────────────────────────────────────
# X06 — los hidrógenos no entran en ECIF ni en las capas
# ─────────────────────────────────────────────────────────────────────────────


def test_x06_los_hidrogenos_del_ligando_no_cuentan_en_ecif_ni_en_capas(tmp_path):
    prot = [("O", (0.0, 0.0, 0.0))]
    sin_h = _geometricas(tmp_path, prot, [("C", (3.0, 0.0, 0.0))], "x06a")
    con_h = _geometricas(tmp_path, prot, [("C", (3.0, 0.0, 0.0)), ("H", (2.0, 0.0, 0.0))], "x06b")
    assert sin_h == con_h == {"ecif_O_don_C": 1.0, "shell_O_C_0_4": 1.0}


# ─────────────────────────────────────────────────────────────────────────────
# X07/X08 — close_contacts: átomos de proteína (no pares); y su dependencia de los H
# ─────────────────────────────────────────────────────────────────────────────


def test_x07_close_contacts_cuenta_atomos_de_proteina_y_contacts_per_ha_divide_entre_pesados(tmp_path):
    # Etanol: 3 átomos pesados + 6 H. Dos átomos de proteína cerca de varios átomos del ligando.
    lig = ligando_3d("CCO", semilla=3)
    pos = np.round(lig.GetConformer().GetPositions() - lig.GetConformer().GetPositions().mean(axis=0), 3)
    for i, p in enumerate(pos):
        lig.GetConformer().SetAtomPosition(i, p.tolist())
    sdf = escribir_sdf(lig, tmp_path / "etanol.sdf")
    prot_atomos = [("C", (2.0, 0.0, 0.0)), ("N", (-2.0, 0.0, 0.0)), ("O", (60.0, 0.0, 0.0))]
    pdb = _pdb_de_atomos_aislados(tmp_path / "x07.pdb", prot_atomos)
    f = extractor_geometrico()._extract_pdb_sdf(pdb, sdf)
    assert f["close_contacts_4A"] == 2.0     # átomos de proteína, no pares ni átomos de ligando
    assert f["heavy_atom_count"] == 3.0      # sin los 6 H
    assert f["contacts_per_ha_4A"] == pytest.approx(2.0 / 3.0)


def test_x08_limite_medido_close_contacts_dependen_de_los_hidrogenos_y_ecif_y_capas_no(peptidos, tmp_path):
    """No es un fallo que se corrija aquí: cambiaría la distribución de entrenamiento. Se fija
    para que la descripción de `contacts_per_ha_*` no afirme una química que no mide."""
    mol = ligando_3d("CC(=O)Oc1ccccc1C(=O)O")
    colocar(mol, peptidos["A"]["mol"].GetConformer().GetPositions().mean(axis=0))
    con_h = escribir_sdf(mol, tmp_path / "con_h.sdf")
    sin_h = escribir_sdf(Chem.RemoveHs(mol), tmp_path / "sin_h.sdf")
    ex = extractor_geometrico()
    a, b = ex._extract_pdb_sdf(peptidos["A"]["h"], con_h), ex._extract_pdb_sdf(peptidos["A"]["h"], sin_h)
    assert a["close_contacts_4A"] > b["close_contacts_4A"]
    assert a["contacts_per_ha_4A"] > b["contacts_per_ha_4A"]
    assert {k: a[k] for k in HEAVY_KEYS} == {k: b[k] for k in HEAVY_KEYS}


# ─────────────────────────────────────────────────────────────────────────────
# X09 — paridad entrenamiento (SDF) ↔ inferencia (PDBQT de Meeko) por elemento
# ─────────────────────────────────────────────────────────────────────────────

_PANEL = {
    "aspirina_C_O": "CC(=O)Oc1ccccc1C(=O)O",
    "nicotinamida_N": "NC(=O)c1cccnc1",
    "tiofeno_S": "Cc1ccsc1",
    "fluorobenceno_F": "Fc1ccccc1",
    "clorobenceno_Cl": "Clc1ccccc1",
    "bromobenceno_Br": "Brc1ccccc1",
    "yodobenceno_I": "Ic1ccccc1",
    "fosfonato_P": "COP(=O)(O)C",
    "boronico_B": "OB(O)c1ccccc1",
    "silano_Si": "C[Si](C)(C)c1ccccc1",
}


def _preparar_con_meeko(sdf: str, salida: Path) -> str:
    """Exactamente el comando de `vina_service._preparar_ligando`."""
    r = subprocess.run(
        [sys.executable, "-m", "meeko.cli.mk_prepare_ligand", "-i", sdf, "-o", str(salida)],
        capture_output=True, text=True, timeout=120,
    )
    assert r.returncode == 0 and salida.exists(), (r.stderr or r.stdout)[-300:]
    return salida.read_text(encoding="utf-8")


@pytest.mark.parametrize("nombre", sorted(_PANEL))
def test_x09_ecif_capas_y_atomos_pesados_son_iguales_en_entrenamiento_e_inferencia(peptidos, tmp_path, nombre):
    pytest.importorskip("meeko")
    mol = ligando_3d(_PANEL[nombre])
    colocar(mol, peptidos["A"]["mol"].GetConformer().GetPositions().mean(axis=0))
    sdf = escribir_sdf(mol, tmp_path / f"{nombre}.sdf")
    pdbqt = _preparar_con_meeko(sdf, tmp_path / f"{nombre}.pdbqt")
    ex = extractor_geometrico()
    entrenamiento = ex._extract_pdb_sdf(peptidos["A"]["h"], sdf)
    inferencia = ex._extract_pdbqt(pdbqt, peptidos["A"]["h"], skip_prolif=True)
    assert inferencia is not None
    reales = sum(1 for a in mol.GetAtoms() if a.GetAtomicNum() > 1)
    assert entrenamiento["heavy_atom_count"] == inferencia["heavy_atom_count"] == reales
    distintos = {k: (entrenamiento[k], inferencia[k]) for k in HEAVY_KEYS if entrenamiento[k] != inferencia[k]}
    assert distintos == {}, f"{nombre}: difieren (SDF, PDBQT) {distintos}"


# ─────────────────────────────────────────────────────────────────────────────
# X10 — un macrociclo REAL de Vina: los pseudoátomos de cierre no son ligando
# ─────────────────────────────────────────────────────────────────────────────

needs_fixtures = pytest.mark.skipif(not FIXTURES.exists(), reason="faltan las salidas reales de Vina del backend")


@needs_fixtures
def test_x10_el_exaltolido_de_vina_tiene_17_atomos_pesados_y_no_19(peptidos):
    bloque = modelos_pdbqt(FIXTURES / "exaltolida_macrociclo.pdbqt")[0]
    tipos = [ln.split()[-1] for ln in bloque.splitlines() if ln.startswith("ATOM")]
    assert tipos.count("G0") == 2 and tipos.count("CG0") == 2, "la salida real trae pseudoátomos G0 y carbonos CG0"
    verdad = Chem.SDMolSupplier(str(FIXTURES / "exaltolida_conformero_de_entrada.sdf"), removeHs=False)[0]
    reales = sum(1 for a in verdad.GetAtoms() if a.GetAtomicNum() > 1)
    assert reales == 17  # C15H28O2
    f = extractor_geometrico()._extract_pdbqt(bloque, peptidos["A"]["h"], skip_prolif=True)
    assert f["heavy_atom_count"] == float(reales)


@needs_fixtures
def test_x10_quitar_los_pseudoatomos_no_cambia_ninguna_feature(peptidos):
    bloque = modelos_pdbqt(FIXTURES / "exaltolida_macrociclo.pdbqt")[0]
    sin_g0 = "\n".join(l for l in bloque.splitlines() if not (l.startswith("ATOM") and re.fullmatch(r"G\d?", l.split()[-1])))
    ex = extractor_geometrico()
    a = ex._extract_pdbqt(bloque, peptidos["A"]["h"], skip_prolif=True)
    b = ex._extract_pdbqt(sin_g0, peptidos["A"]["h"], skip_prolif=True)
    assert {k: a[k] for k in HEAVY_KEYS} == {k: b[k] for k in HEAVY_KEYS}
    assert a["close_contacts_4A"] == b["close_contacts_4A"]


# ─────────────────────────────────────────────────────────────────────────────
# X11 — tipos AutoDock → elemento: nada desconocido se vuelve carbono
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "tipo,esperado",
    [("A", "C"), ("C", "C"), ("OA", "O"), ("NA", "N"), ("SA", "S"), ("HD", "H"), ("Cl", "Cl"), ("I", "I"),
     ("CG0", "C"),        # carbono REAL de un macrociclo abierto
     ("G0", None), ("G", None), ("G3", None),   # pseudoátomos de pegado
     ("B", "B"), ("Si", "Si"),                  # antes caían en «C»
     ("Xx", None), ("", None)],
)
def test_x11_tipos_ad4_a_elemento(tipo, esperado):
    assert _ad4_a_elemento(tipo) == esperado


# ─────────────────────────────────────────────────────────────────────────────
# X12 — una línea PDBQT sin su espacio final no pierde el átomo
# ─────────────────────────────────────────────────────────────────────────────


@needs_fixtures
def test_x12_pdbqt_con_espacios_finales_recortados_da_las_mismas_features(peptidos):
    bloque = modelos_pdbqt(FIXTURES / "paracetamol_9_poses.pdbqt")[0]
    recortado = "\n".join(l.rstrip() for l in bloque.splitlines())
    assert any(len(l) < 79 for l in recortado.splitlines() if l.startswith("ATOM")), "el control debe recortar líneas"
    ex = extractor_geometrico()
    a = ex._extract_pdbqt(bloque, peptidos["A"]["h"], skip_prolif=True)
    b = ex._extract_pdbqt(recortado, peptidos["A"]["h"], skip_prolif=True)
    assert a["heavy_atom_count"] == b["heavy_atom_count"] == 11.0  # paracetamol C8H9NO2
    assert a == b


# ─────────────────────────────────────────────────────────────────────────────
# X13/X14 — invariancias: movimiento rígido y orden de los átomos
# ─────────────────────────────────────────────────────────────────────────────


def _rotacion(semilla: int) -> np.ndarray:
    q, r = np.linalg.qr(np.random.default_rng(semilla).normal(size=(3, 3)))
    q = q * np.sign(np.diag(r))
    return q if np.linalg.det(q) > 0 else -q


def test_x13_un_movimiento_rigido_de_proteina_y_ligando_no_cambia_nada(peptidos, tmp_path):
    """En memoria, sin pasar por un PDB: escribir coordenadas rotadas a 3 decimales redondearía cada
    una por separado y movería pares de átomos que están a ~0,001 Å de un corte."""
    from feature_extractor import _compute_close_contacts

    mol = ligando_3d("CC(=O)Oc1ccccc1C(=O)O")
    colocar(mol, peptidos["A"]["mol"].GetConformer().GetPositions().mean(axis=0))
    prot = _load_protein_pdb(peptidos["A"]["h"])
    pc, lc = _get_conformer_coords(prot), _get_conformer_coords(mol)
    R, t = _rotacion(5), np.array([13.0, -7.0, 21.0], dtype=np.float32)

    def calcular(p, l):
        f = {}
        f.update(_compute_shell_atom_counts(prot, mol, p, l))
        f.update(_compute_ecif_features(prot, mol, p, l))
        f["cc4"], f["cc6"] = _compute_close_contacts(p, l)
        return f

    antes = calcular(pc, lc)
    despues = calcular((pc @ R.T + t).astype(np.float32), (lc @ R.T + t).astype(np.float32))
    assert sum(antes[k] for k in ECIF_FEATURES) > 0, "el control debe tener contactos que contar"
    assert antes == despues


def test_x14_reordenar_los_atomos_del_ligando_no_cambia_nada(peptidos, tmp_path):
    mol = ligando_3d("CC(=O)Oc1ccccc1C(=O)O")
    colocar(mol, peptidos["A"]["mol"].GetConformer().GetPositions().mean(axis=0))
    orden = list(range(mol.GetNumAtoms()))
    random.Random(3).shuffle(orden)
    assert orden != sorted(orden)
    ex = extractor_geometrico()
    a = ex._extract_pdb_sdf(peptidos["A"]["h"], escribir_sdf(mol, tmp_path / "a.sdf"))
    b = ex._extract_pdb_sdf(peptidos["A"]["h"], escribir_sdf(Chem.RenumberAtoms(mol, orden), tmp_path / "b.sdf"))
    assert a == b
