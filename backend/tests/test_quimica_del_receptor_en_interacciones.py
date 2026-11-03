"""El receptor que se le da a ProLIF trae la química de sus residuos, y los hidrógenos añadidos siguen en su residuo.

Una corrida real de 8T69 (VMAT2 con un fármaco de ProLIF) daba CERO contactos en las poses 1 y 2. Medido el 2026-11-02:
RDKit lee el PDB derivado del PDBQT sólo con enlaces sencillos por distancia (ni aromaticidad, ni el C=O del esqueleto,
ni cargas) y los hidrógenos que añade `AddHs` quedan sin residuo, así que ProLIF los deja fuera de cada fragmento. Con
la química de los residuos estándar la misma corrida da 5, 7 y 9 contactos (poses 1, 2 y 3). Estas pruebas fijan la
causa con receptores sintéticos de unos pocos átomos y llevan su control negativo: sin la química, no hay contacto.
"""
from __future__ import annotations

import math

import pytest
from rdkit import Chem
from rdkit.Chem import AllChem

from services.interactions.analyzer import (
    _aplicar_quimica_estandar,
    _hidrogenos_en_su_residuo,
    _leer_receptor,
    analyze_complex,
)


def _linea(serial: int, nombre: str, residuo: str, numero: int, x: float, y: float, z: float) -> str:
    elemento = "H" if nombre.startswith("H") else nombre[0]
    return f"ATOM  {serial:5d} {nombre.rjust(3) if len(nombre) < 4 else nombre:<4s} {residuo:>3s} A{numero:4d}    {x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00           {elemento}"


def _pdb(atomos: list[tuple[str, str, int, float, float, float]]) -> str:
    return "\n".join(_linea(i + 1, *a) for i, a in enumerate(atomos)) + "\nEND\n"


def _fenilalanina(numero: int = 1, residuo: str = "PHE", z: float = 0.0, centro: tuple[float, float] = (0.0, 0.0)):
    """Una Phe plana: esqueleto, CB y anillo de radio 1,40 Å centrado en `centro`."""
    cx, cy = centro
    atomos = [("N", residuo, numero, cx - 1.2, cy - 3.3, z), ("CA", residuo, numero, cx, cy - 2.8, z),
              ("C", residuo, numero, cx + 1.2, cy - 3.6, z), ("O", residuo, numero, cx + 1.3, cy - 4.8, z),
              ("CB", residuo, numero, cx, cy - 1.3, z)]
    for k, nombre in enumerate(("CG", "CD1", "CE1", "CZ", "CE2", "CD2")):
        angulo = math.radians(90 + 60 * k)
        atomos.append((nombre, residuo, numero, cx + 1.4 * math.cos(angulo), cy + 1.4 * math.sin(angulo), z))
    return atomos


def _bencenos_encima(tmp_path, z: float = 3.8):
    """Benceno plano paralelo al anillo de la Phe, a `z` Å."""
    mol = Chem.AddHs(Chem.MolFromSmiles("c1ccccc1"))
    assert AllChem.EmbedMolecule(mol, randomSeed=7) == 0
    conformador = mol.GetConformer()
    for k in range(6):
        angulo = math.radians(60 * k)
        conformador.SetAtomPosition(k, (1.39 * math.cos(angulo), 1.39 * math.sin(angulo), z))
        conformador.SetAtomPosition(6 + k, (2.47 * math.cos(angulo), 2.47 * math.sin(angulo), z))
    ruta = tmp_path / "ligando.sdf"
    ruta.write_text(Chem.MolToMolBlock(mol) + "\n$$$$\n", encoding="utf-8")
    return ruta


def _residuo(mol, nombre_atomo: str):
    return next(a for a in mol.GetAtoms() if a.GetPDBResidueInfo().GetName().strip() == nombre_atomo)


# ── 1. Qué percibe RDKit del receptor ────────────────────────────────

def test_sin_plantillas_un_pdb_sale_solo_con_enlaces_sencillos():
    """La causa: RDKit no pone aromaticidad ni el C=O del esqueleto a un residuo leído de un PDB."""
    crudo = Chem.MolFromPDBBlock(_pdb(_fenilalanina()), removeHs=False, sanitize=True)
    assert not any(a.GetIsAromatic() for a in crudo.GetAtoms())
    assert {str(b.GetBondType()) for b in crudo.GetBonds()} == {"SINGLE"}


def test_la_fenilalanina_queda_aromatica_y_su_carbonilo_doble():
    mol, quimica = _leer_receptor(_pdb(_fenilalanina()))
    assert quimica == "standard_residue_templates"
    anillo = [a for a in mol.GetAtoms() if a.GetPDBResidueInfo().GetName().strip() in ("CG", "CD1", "CE1", "CZ", "CE2", "CD2")]
    assert len(anillo) == 6 and all(a.GetIsAromatic() for a in anillo)
    assert not _residuo(mol, "CB").GetIsAromatic()
    carbonilo = mol.GetBondBetweenAtoms(_residuo(mol, "C").GetIdx(), _residuo(mol, "O").GetIdx())
    assert carbonilo.GetBondType() == Chem.BondType.DOUBLE


def test_un_residuo_sin_plantilla_se_declara_y_no_se_inventa_su_quimica():
    """Control negativo: un residuo que no es estándar se lee como antes y el informe lo dice."""
    mol, quimica = _leer_receptor(_pdb(_fenilalanina(residuo="XYZ")))
    assert quimica == "bonds_by_distance_only"
    assert not any(a.GetIsAromatic() for a in mol.GetAtoms())


def _lisina(hidrogenos: int):
    atomos = [("N", "LYS", 1, 0.0, 0.0, 0.0), ("CA", "LYS", 1, 1.4, 0.0, 0.0), ("C", "LYS", 1, 2.0, 1.4, 0.0),
              ("O", "LYS", 1, 3.2, 1.5, 0.0), ("CB", "LYS", 1, 2.0, -0.8, 1.2), ("CG", "LYS", 1, 3.4, -0.6, 1.8),
              ("CD", "LYS", 1, 3.5, -1.4, 3.1), ("CE", "LYS", 1, 4.9, -1.2, 3.7), ("NZ", "LYS", 1, 5.0, -2.0, 4.9)]
    posiciones = [(5.9, -1.7, 5.4), (4.3, -1.8, 5.6), (5.0, -3.0, 4.7)]
    atomos += [(f"HZ{k + 1}", "LYS", 1, *posiciones[k]) for k in range(hidrogenos)]
    return atomos


@pytest.mark.parametrize("hidrogenos,carga", [(3, 1), (2, 0), (0, 0)])
def test_la_carga_de_la_lisina_sale_de_sus_hidrogenos_y_sin_ellos_no_se_supone(hidrogenos, carga):
    mol, _ = _leer_receptor(_pdb(_lisina(hidrogenos)))
    assert _residuo(mol, "NZ").GetFormalCharge() == carga


def _aspartato(hidrogeno_en: str | None):
    atomos = [("N", "ASP", 1, 0.0, 0.0, 0.0), ("CA", "ASP", 1, 1.4, 0.0, 0.0), ("C", "ASP", 1, 2.0, 1.4, 0.0),
              ("O", "ASP", 1, 3.2, 1.5, 0.0), ("CB", "ASP", 1, 2.0, -0.8, 1.2), ("CG", "ASP", 1, 3.4, -0.6, 1.8),
              ("OD1", "ASP", 1, 4.4, -1.3, 1.7), ("OD2", "ASP", 1, 3.5, 0.5, 2.5)]
    if hidrogeno_en:
        base = {"OD1": (5.2, -0.8, 1.9), "OD2": (4.3, 0.9, 3.0)}[hidrogeno_en]
        atomos.append(("HD1" if hidrogeno_en == "OD1" else "HD2", "ASP", 1, *base))
    return atomos


@pytest.mark.parametrize("hidrogeno_en,carga_total", [(None, -1), ("OD2", 0)])
def test_el_aspartato_es_carboxilato_solo_si_ninguno_de_sus_oxigenos_lleva_hidrogeno(hidrogeno_en, carga_total):
    mol, _ = _leer_receptor(_pdb(_aspartato(hidrogeno_en)))
    assert _residuo(mol, "OD1").GetFormalCharge() + _residuo(mol, "OD2").GetFormalCharge() == carga_total


def _histidina(hidrogenos_en: tuple[str, ...]):
    """Imidazol plano (pentágono de lado 1,36 Å) con CB, CA y el esqueleto saliendo del CG."""
    radio, centro = 1.157, (0.0, 0.0)
    nombres = ("CG", "ND1", "CE1", "NE2", "CD2")
    vertices = {n: (centro[0] + radio * math.cos(math.radians(90 + 72 * k)),
                    centro[1] + radio * math.sin(math.radians(90 + 72 * k))) for k, n in enumerate(nombres)}

    def hacia_afuera(nombre: str, distancia: float) -> tuple[float, float, float]:
        x, y = vertices[nombre]
        return (x + distancia * (x - centro[0]) / radio, y + distancia * (y - centro[1]) / radio, 0.0)

    atomos = [(n, "HIS", 1, *vertices[n], 0.0) for n in nombres]
    atomos += [("CB", "HIS", 1, *hacia_afuera("CG", 1.5)), ("CA", "HIS", 1, *hacia_afuera("CG", 3.0)),
               ("N", "HIS", 1, 1.3, 4.4, 0.0), ("C", "HIS", 1, -1.3, 4.4, 0.0), ("O", "HIS", 1, -2.4, 5.0, 0.0)]
    atomos += [("HD1" if n == "ND1" else "HE2", "HIS", 1, *hacia_afuera(n, 1.0)) for n in hidrogenos_en]
    return atomos


@pytest.mark.parametrize("hidrogenos_en,aromatica,carga", [
    (("NE2",), True, 0),            # HIE
    (("ND1",), True, 0),            # HID
    (("ND1", "NE2"), True, 1),      # HIP
    ((), False, 0),                 # sin el H que decide el tautómero no se elige uno
])
def test_la_histidina_toma_su_tautomero_del_hidrogeno_que_trae(hidrogenos_en, aromatica, carga):
    mol, _ = _leer_receptor(_pdb(_histidina(hidrogenos_en)))
    anillo = [_residuo(mol, n) for n in ("CG", "ND1", "CE1", "NE2", "CD2")]
    assert all(a.GetIsAromatic() for a in anillo) is aromatica
    assert sum(a.GetFormalCharge() for a in anillo) == carga


def test_una_plantilla_que_falla_no_tumba_el_analisis_y_se_declara(monkeypatch):
    """Si aplicar la química estándar lanza (valencias imposibles tras las plantillas), el receptor se lee como antes."""
    from services.interactions import analyzer

    def fallar(_mol):
        raise ValueError("Explicit valence for atom # 7 C, 5, is greater than permitted")

    monkeypatch.setattr(analyzer, "_aplicar_quimica_estandar", fallar)
    mol, quimica = _leer_receptor(_pdb(_fenilalanina()))
    assert mol is not None and quimica == "bonds_by_distance_only"
    assert not any(a.GetIsAromatic() for a in mol.GetAtoms())


def test_no_modifica_la_molecula_de_entrada():
    crudo = Chem.MolFromPDBBlock(_pdb(_fenilalanina()), removeHs=False, sanitize=False)
    copia, tipados = _aplicar_quimica_estandar(crudo)
    assert tipados == 1
    assert {str(b.GetBondType()) for b in crudo.GetBonds()} == {"SINGLE"}
    assert any(a.GetIsAromatic() for a in copia.GetAtoms())


# ── 2. Los hidrógenos añadidos siguen en su residuo ─────────────────

def test_los_hidrogenos_que_anade_rdkit_quedan_en_el_residuo_de_su_atomo_pesado():
    mol, _ = _leer_receptor(_pdb(_fenilalanina()))
    con_h = _hidrogenos_en_su_residuo(Chem.AddHs(mol, addCoords=True))
    assert sum(1 for a in con_h.GetAtoms() if a.GetAtomicNum() == 1) > 0
    assert all(a.GetPDBResidueInfo() is not None for a in con_h.GetAtoms())
    for atomo in con_h.GetAtoms():
        if atomo.GetAtomicNum() == 1:
            padre = atomo.GetNeighbors()[0].GetPDBResidueInfo()
            propio = atomo.GetPDBResidueInfo()
            assert (propio.GetResidueName(), propio.GetResidueNumber(), propio.GetChainId()) == \
                   (padre.GetResidueName(), padre.GetResidueNumber(), padre.GetChainId())


# ── 3. De punta a punta con ProLIF: la química es lo que habilita el contacto ────────

def _analizar(tmp_path, pdb_texto: str):
    receptor = tmp_path / "receptor.pdb"
    receptor.write_text(pdb_texto, encoding="utf-8")
    return analyze_complex(receptor, _bencenos_encima(tmp_path), molecule_id="m", target_pdb_id="X", pose_rank=1)


def test_un_benceno_apilado_sobre_una_fenilalanina_da_apilamiento_pi(tmp_path):
    informe = _analizar(tmp_path, _pdb(_fenilalanina()))
    assert informe.engine.startswith("prolif:") and informe.receptor_chemistry == "standard_residue_templates"
    apilamientos = [i for i in informe.interactions if i.type == "pi_stacking"]
    assert len(apilamientos) == 1 and apilamientos[0].residue_name == "PHE"
    assert apilamientos[0].distance < 4.5


def test_sin_la_quimica_del_residuo_el_mismo_apilamiento_no_se_ve(tmp_path):
    """Control negativo: el mismo anillo con un nombre de residuo sin plantilla no tiene aromaticidad, y no hay contacto."""
    informe = _analizar(tmp_path, _pdb(_fenilalanina(residuo="XYZ")))
    assert informe.receptor_chemistry == "bonds_by_distance_only"
    assert not [i for i in informe.interactions if i.type == "pi_stacking"]


def _valina():
    """El CB de una Val (un C con un H y tres vecinos pesados) sólo es hidrofóbico para ProLIF si su H está en el residuo."""
    return [("N", "VAL", 1, -0.8, 1.2, 0.5), ("CA", "VAL", 1, 0.0, 0.0, 0.0), ("C", "VAL", 1, 1.4, 0.6, 0.5),
            ("O", "VAL", 1, 2.4, -0.2, 1.0), ("CB", "VAL", 1, -0.5, -1.3, 0.6), ("CG1", "VAL", 1, -1.9, -1.4, 1.2),
            ("CG2", "VAL", 1, 0.1, -2.5, 0.0)]


def _benceno_a(tmp_path, centro: tuple[float, float, float]):
    mol = Chem.AddHs(Chem.MolFromSmiles("c1ccccc1"))
    assert AllChem.EmbedMolecule(mol, randomSeed=7) == 0
    conformador = mol.GetConformer()
    for k in range(6):
        angulo = math.radians(60 * k)
        conformador.SetAtomPosition(k, (centro[0] + 1.39 * math.cos(angulo), centro[1] + 1.39 * math.sin(angulo), centro[2]))
        conformador.SetAtomPosition(6 + k, (centro[0] + 2.47 * math.cos(angulo), centro[1] + 2.47 * math.sin(angulo), centro[2]))
    ruta = tmp_path / "benceno.sdf"
    ruta.write_text(Chem.MolToMolBlock(mol) + "\n$$$$\n", encoding="utf-8")
    return ruta


def test_el_hidrogeno_dentro_del_residuo_es_lo_que_habilita_el_contacto_hidrofobico_del_cb(tmp_path, monkeypatch):
    """Con el H de RDKit en su residuo el CB de la Val es hidrofóbico; sin él (como antes del 2026-11-02) no se ve."""
    from services.interactions import analyzer

    receptor = tmp_path / "receptor.pdb"
    receptor.write_text(_pdb(_valina()), encoding="utf-8")
    ligando = _benceno_a(tmp_path, (-0.5, -1.3, 4.6))

    con = analyze_complex(receptor, ligando, molecule_id="m", target_pdb_id="X", pose_rank=1)
    assert [(i.residue_name, i.protein_atom[0]) for i in con.interactions if i.type == "hydrophobic"], con.summary

    monkeypatch.setattr(analyzer, "_hidrogenos_en_su_residuo", lambda mol: mol)
    sin = analyze_complex(receptor, ligando, molecule_id="m", target_pdb_id="X", pose_rank=1)
    assert sin.engine.startswith("prolif:")
    assert not [i for i in sin.interactions if i.type == "hydrophobic"]


def test_un_benceno_lejos_de_la_fenilalanina_no_da_apilamiento(tmp_path):
    """Control negativo geométrico: el detector no inventa contactos porque haya química."""
    receptor = tmp_path / "receptor.pdb"
    receptor.write_text(_pdb(_fenilalanina()), encoding="utf-8")
    informe = analyze_complex(receptor, _bencenos_encima(tmp_path, z=12.0), molecule_id="m", target_pdb_id="X", pose_rank=1)
    assert informe.engine.startswith("prolif:")
    assert not [i for i in informe.interactions if i.type == "pi_stacking"]


def test_un_carboxilato_junto_a_una_lisina_cargada_da_puente_salino_y_sin_ella_no(tmp_path):
    ligando = Chem.AddHs(Chem.MolFromSmiles("CC(=O)[O-]"))
    assert AllChem.EmbedMolecule(ligando, randomSeed=5) == 0
    # El carboxilato a ~3 Å del NZ de la lisina (5,0 / -2,0 / 4,9): se coloca el ligando en esa vecindad.
    conformador = ligando.GetConformer()
    centro = conformador.GetAtomPosition(3)  # el O con carga
    desplazamiento = (5.0 - centro.x + 3.0, -2.0 - centro.y, 4.9 - centro.z)
    for i in range(ligando.GetNumAtoms()):
        p = conformador.GetAtomPosition(i)
        conformador.SetAtomPosition(i, (p.x + desplazamiento[0], p.y + desplazamiento[1], p.z + desplazamiento[2]))
    sdf = tmp_path / "acetato.sdf"
    sdf.write_text(Chem.MolToMolBlock(ligando) + "\n$$$$\n", encoding="utf-8")

    def contactos(hidrogenos: int):
        pdb = tmp_path / f"lys{hidrogenos}.pdb"
        pdb.write_text(_pdb(_lisina(hidrogenos)), encoding="utf-8")
        return analyze_complex(pdb, sdf, molecule_id="m", target_pdb_id="X", pose_rank=1)

    cargada, neutra = contactos(3), contactos(2)
    assert [i.type for i in cargada.interactions if i.type == "salt_bridge"], cargada.summary
    assert not [i for i in neutra.interactions if i.type == "salt_bridge"]
