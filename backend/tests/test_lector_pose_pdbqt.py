"""Contrato del lector de poses: el PDBQT aporta coordenadas, nunca quimica.

EXISTE POR UN DEFECTO MEDIDO. El lector anterior hacia `MolFromPDBBlock` sobre las lineas
del PDBQT y despues parcheaba con `AssignBondOrdersFromTemplate`. Sobre las 232 poses top-1
del protocolo rigido eso cubria **40 (17.2%)**: 178 morian en la lectura porque el tipo
AutoDock `A` -carbono aromatico- ocupa las columnas 77-78 donde un PDB lleva el simbolo
quimico, y RDKit aborta con `anum > -1`; otras 14 morian en la valencia de la plantilla.
El fallo estaba CORRELACIONADO CON LA AROMATICIDAD, que es la peor forma de perder datos.

La ruta nueva no infiere nada: plantilla quimica + `index_map` serial->indice + coordenadas
leidas por columnas fijas. Estas pruebas fijan el contrato, incluido el de abstenerse.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.chemistry.pose_physical_validity import (  # noqa: E402
    _coords_de_pdbqt,
    leer_pose_pdbqt,
)

Chem = pytest.importorskip("rdkit.Chem")
from rdkit import RDLogger  # noqa: E402

RDLogger.DisableLog("rdApp.*")


def _linea(serial: int, nombre: str, x: float, y: float, z: float, tipo: str) -> str:
    """Una linea ATOM de PDBQT, colocada por COLUMNAS y no por concatenacion.

    Las columnas importan: el nombre de atomo vive en 13-16, las coordenadas en 31-54 y el
    tipo AutoDock en 77-78, justo donde un PDB lleva el simbolo quimico. Construir la linea
    a ojo desplaza los campos y la prueba deja de probar lo que dice.
    """
    buf = [" "] * 79
    def _poner(desde_1: int, texto: str):
        buf[desde_1 - 1: desde_1 - 1 + len(texto)] = list(texto)
    _poner(1, "ATOM")
    _poner(12 - len(str(serial)), str(serial))              # 7-11, a la derecha
    _poner(14, nombre)                                       # 13-16
    _poner(18, "UNL")
    _poner(23, "1")
    _poner(31, f"{x:8.3f}")
    _poner(39, f"{y:8.3f}")
    _poner(47, f"{z:8.3f}")
    _poner(55, "  1.00  0.00     0.000")
    _poner(78 - len(tipo) + 1, tipo)                         # 77-78
    return "".join(buf).rstrip() + (" " if len(tipo) == 1 else "")


def _molecula_y_mapa(smiles: str):
    """Plantilla con H explicitos y un mapa serial->indice para los atomos con coordenada."""
    mol = Chem.AddHs(Chem.MolFromSmiles(smiles))
    from rdkit.Chem import AllChem
    AllChem.EmbedMolecule(mol, randomSeed=42)
    return mol


class TestLecturaDeColumnas:
    def test_no_lee_el_tipo_autodock_como_elemento(self):
        """`A` es carbono aromatico; `NA`, nitrogeno aceptor. Ninguno es un elemento."""
        texto = "\n".join([
            _linea(1, "C", 1.0, 2.0, 3.0, "A"),      # el que rompia el lector viejo
            _linea(2, "N", 4.0, 5.0, 6.0, "NA"),     # NO es sodio
            _linea(3, "H", 7.0, 8.0, 9.0, "HD"),
        ])
        atomos = _coords_de_pdbqt(texto)
        assert [a[0] for a in atomos] == [1, 2, 3]
        assert atomos[0][1:4] == (1.0, 2.0, 3.0)
        assert atomos[1][1:4] == (4.0, 5.0, 6.0)
        # el tipo se lee, pero solo para reconocer pseudo-atomos: nunca como elemento
        assert [a[4] for a in atomos] == ["A", "NA", "HD"]

    def test_el_lector_viejo_moriria_con_el_tipo_A(self):
        """Deja constancia del defecto: no es una hipotesis, es reproducible."""
        bloque = _linea(1, "C", 1.0, 2.0, 3.0, "A") + "\nEND\n"
        assert Chem.MolFromPDBBlock(bloque, removeHs=False, sanitize=False) is None

    def test_pdbqt_truncado_no_produce_atomos_a_medias(self):
        atomos = _coords_de_pdbqt("ATOM      1  C   UNL     1       1.0")
        assert atomos == []


class TestRutaDelMapa:
    def _caso(self, smiles="CCO"):
        mol = _molecula_y_mapa(smiles)
        conf = mol.GetConformer()
        lineas, mapa = [], []
        serial = 1
        for a in mol.GetAtoms():
            # solo pesados y polares llevan coordenada en un PDBQT de Vina
            polar = (a.GetAtomicNum() == 1 and a.GetDegree() == 1
                     and a.GetNeighbors()[0].GetAtomicNum() in (7, 8, 16))
            if a.GetAtomicNum() == 1 and not polar:
                continue
            p = conf.GetAtomPosition(a.GetIdx())
            lineas.append(_linea(serial, a.GetSymbol(), p.x, p.y, p.z,
                                 "A" if a.GetIsAromatic() else a.GetSymbol()))
            mapa.append([serial, a.GetIdx()])
            serial += 1
        return mol, "\n".join(lineas), mapa

    def test_lee_y_conserva_la_identidad_quimica(self):
        plantilla, texto, mapa = self._caso()
        r = leer_pose_pdbqt(texto, plantilla=plantilla, index_map=mapa)
        assert r.mol is not None, r.motivo
        assert r.ruta == "mapa_atomico"
        assert r.diagnostico["carga_formal_identica"]
        assert r.diagnostico["n_enlaces_pesados_identico"]
        assert r.diagnostico["smiles_isomerico_identico"]

    def test_los_h_sin_coordenada_se_eliminan_no_se_heredan(self):
        """La leccion de MF-33-H-COR: un H sin coordenada NO conserva la de la plantilla."""
        plantilla, texto, mapa = self._caso()
        r = leer_pose_pdbqt(texto, plantilla=plantilla, index_map=mapa)
        assert r.diagnostico["h_sin_coordenada_eliminados"] > 0
        assert r.mol.GetNumAtoms() == len(mapa)

    def test_smiles_cargado_como_el_de_10gs(self):
        plantilla, texto, mapa = self._caso("[NH3+]CC(=O)[O-]")
        r = leer_pose_pdbqt(texto, plantilla=plantilla, index_map=mapa)
        assert r.mol is not None, r.motivo
        assert Chem.GetFormalCharge(r.mol) == Chem.GetFormalCharge(plantilla)

    def test_ligando_aromatico(self):
        plantilla, texto, mapa = self._caso("c1ccccc1O")
        r = leer_pose_pdbqt(texto, plantilla=plantilla, index_map=mapa)
        assert r.mol is not None, r.motivo

    def test_ligando_sin_h_polares(self):
        plantilla, texto, mapa = self._caso("CC(F)(F)F")
        r = leer_pose_pdbqt(texto, plantilla=plantilla, index_map=mapa)
        assert r.mol is not None, r.motivo


class TestMacrociclos:
    """Meeko abre los macrociclos e inserta pseudo-atomos de pegado tipo `G`.

    No son atomos de la molecula y por eso `index_map.json` no los lista. Medido: los tres
    macrociclos de la cohorte -`1mmq`, `1mmr`, `1nm6`- traen exactamente 2 cada uno, y sin
    esta regla las 6 poses quedaban fuera. Ninguno de sus atomos PESADOS estaba sin mapear.
    """

    def test_los_pseudoatomos_de_pegado_se_descartan(self):
        plantilla, texto, mapa = TestRutaDelMapa()._caso()
        siguiente = max(s for s, _i in mapa) + 1
        texto += "\n" + _linea(siguiente, "G", 99.0, 99.0, 99.0, "G")
        r = leer_pose_pdbqt(texto, plantilla=plantilla, index_map=mapa)
        assert r.mol is not None, r.motivo
        assert r.diagnostico["pseudoatomos_de_pegado_descartados"] == 1

    def test_un_serial_no_mapeado_que_NO_es_pegado_sigue_abortando(self):
        """La regla es estrecha a proposito: no se traga cualquier serial sobrante."""
        plantilla, texto, mapa = TestRutaDelMapa()._caso()
        siguiente = max(s for s, _i in mapa) + 1
        texto += "\n" + _linea(siguiente, "C", 99.0, 99.0, 99.0, "C")
        r = leer_pose_pdbqt(texto, plantilla=plantilla, index_map=mapa)
        assert r.mol is None
        assert r.motivo == "serial_ausente_o_indice_fuera_de_rango"


class TestSeAbstieneEnVezDeAdivinar:
    def _base(self):
        return TestRutaDelMapa()._caso()

    def test_mapa_no_biyectivo(self):
        plantilla, texto, mapa = self._base()
        mapa[1][1] = mapa[0][1]                    # dos seriales al mismo indice
        r = leer_pose_pdbqt(texto, plantilla=plantilla, index_map=mapa)
        assert r.mol is None
        assert r.motivo == "index_map_no_biyectivo"

    def test_serial_ausente_en_el_mapa(self):
        plantilla, texto, mapa = self._base()
        mapa = mapa[:-1]                            # falta la entrada del ultimo atomo
        r = leer_pose_pdbqt(texto, plantilla=plantilla, index_map=mapa)
        assert r.mol is None
        assert r.motivo == "serial_ausente_o_indice_fuera_de_rango"

    def test_serial_duplicado_en_el_pdbqt(self):
        plantilla, texto, mapa = self._base()
        lineas = texto.splitlines()
        lineas.append(lineas[0])                    # mismo serial dos veces
        r = leer_pose_pdbqt("\n".join(lineas), plantilla=plantilla, index_map=mapa)
        assert r.mol is None
        assert r.motivo == "seriales_duplicados_en_pdbqt"

    def test_atomo_pesado_sin_coordenada(self):
        """Si a un pesado le falta coordenada, la pose NO se completa con la plantilla."""
        plantilla, texto, mapa = self._base()
        pesado = next(i for i, (_s, i2) in enumerate(mapa)
                      if plantilla.GetAtomWithIdx(i2).GetAtomicNum() > 1)
        serial_fuera = mapa[pesado][0]
        lineas = [l for l in texto.splitlines() if int(l[6:11]) != serial_fuera]
        mapa2 = [m for m in mapa if m[0] != serial_fuera]
        r = leer_pose_pdbqt("\n".join(lineas), plantilla=plantilla, index_map=mapa2)
        assert r.mol is None
        assert r.motivo == "atomo_pesado_sin_coordenada"

    def test_indice_fuera_de_rango(self):
        plantilla, texto, mapa = self._base()
        mapa[0][1] = 10_000
        r = leer_pose_pdbqt(texto, plantilla=plantilla, index_map=mapa)
        assert r.mol is None
        assert r.motivo == "serial_ausente_o_indice_fuera_de_rango"

    def test_pdbqt_sin_atomos(self):
        r = leer_pose_pdbqt("REMARK nada\n", plantilla=Chem.MolFromSmiles("CCO"),
                            index_map=[[1, 0]])
        assert r.mol is None
        assert r.motivo == "pdbqt_sin_atomos"

    def test_sin_mapa_ni_smiles_no_inventa(self):
        r = leer_pose_pdbqt(_linea(1, "C", 1.0, 2.0, 3.0, "C"))
        assert r.mol is None
        assert r.motivo == "sin_mapa_ni_smiles"


class TestRutaDeRespaldo:
    def test_sin_mapa_usa_la_heuristica_y_lo_declara(self):
        """Para un PDBQT externo sin mapa. Queda etiquetada, no escondida."""
        mol = _molecula_y_mapa("CCO")
        conf = mol.GetConformer()
        lineas = [_linea(i + 1, a.GetSymbol(), conf.GetAtomPosition(a.GetIdx()).x,
                         conf.GetAtomPosition(a.GetIdx()).y,
                         conf.GetAtomPosition(a.GetIdx()).z, a.GetSymbol())
                  for i, a in enumerate(mol.GetAtoms())]
        r = leer_pose_pdbqt("\n".join(lineas), smiles="CCO")
        assert r.ruta == "plantilla_heuristica"
        assert "aviso" in r.diagnostico
