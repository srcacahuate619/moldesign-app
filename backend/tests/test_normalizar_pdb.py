"""Lo que se le hace a un PDB para que Meeko lo lea: el primer modelo y el elemento que falta.

Cada arreglo trae su control negativo: un PDB que no lo necesita sale byte a byte igual.
"""

from __future__ import annotations

from pathlib import Path

from services.targets.normalizar_pdb import elemento_desde_el_nombre, normalizar_pdb
from tests.receptores_propios_ayudas import linea_pdb, pdb_sintetico

PDB_REAL = (Path(__file__).parent / "data" / "receptores_propios" / "8hfi_recortado.pdb").read_text(encoding="utf-8")
NL = chr(10)


def _sin_elemento(pdb: str) -> str:
    return NL.join(l[:76] + "  " if l.startswith(("ATOM", "HETATM")) else l for l in pdb.splitlines()) + NL


class TestSinCambios:
    def test_un_pdb_bien_formado_sale_identico(self):
        for pdb in (PDB_REAL, pdb_sintetico(residuos=12)):
            texto, informe = normalizar_pdb(pdb)
            assert texto is pdb or texto == pdb
            assert informe == {}

    def test_un_solo_model_no_es_un_conjunto(self):
        uno = "MODEL        1" + NL + pdb_sintetico(residuos=3) + "ENDMDL" + NL

        assert normalizar_pdb(uno) == (uno, {})


class TestVariosModelos:
    def _rmn(self, n: int) -> str:
        cuerpo = [f"MODEL     {i:>4}{NL}{pdb_sintetico(residuos=3).replace('END' + NL, '')}ENDMDL{NL}" for i in range(1, n + 1)]
        return "REMARK   2 RESOLUTION. NOT APPLICABLE." + NL + "".join(cuerpo) + "END" + NL

    def test_se_conserva_solo_el_modelo_uno_y_se_declara(self):
        texto, informe = normalizar_pdb(self._rmn(4))

        assert informe == {"modelos": {"en_el_archivo": 4, "usado": 1}}
        assert sum(l.startswith("ATOM") for l in texto.splitlines()) == 15
        assert not any(l.startswith(("MODEL", "ENDMDL")) for l in texto.splitlines())
        assert texto.startswith("REMARK   2") and texto.rstrip().endswith("END")

    def test_el_modelo_uno_es_el_primero_aunque_el_archivo_no_empiece_por_el(self):
        texto, _ = normalizar_pdb(self._rmn(2).replace("MODEL        1", "MODEL        7", 1))

        assert sum(l.startswith("ATOM") for l in texto.splitlines()) == 15


class TestElementoAusente:
    def test_el_elemento_se_infiere_del_nombre_y_se_cuenta(self):
        pdb = _sin_elemento(PDB_REAL)

        texto, informe = normalizar_pdb(pdb)

        esperado = sum(1 for l in PDB_REAL.splitlines() if l.startswith(("ATOM", "HETATM")))
        assert informe == {"elementos_inferidos": esperado}
        # Recupera exactamente el elemento original en todos los átomos del recorte real de 8HFI
        original = [l[76:78].strip() for l in PDB_REAL.splitlines() if l.startswith(("ATOM", "HETATM"))]
        inferido = [l[76:78].strip() for l in texto.splitlines() if l.startswith(("ATOM", "HETATM"))]
        assert inferido == original

    def test_solo_se_rellenan_las_lineas_que_lo_necesitan(self):
        lineas = PDB_REAL.splitlines()
        i = next(k for k, l in enumerate(lineas) if l.startswith("ATOM"))
        lineas[i] = lineas[i][:76] + "  "

        texto, informe = normalizar_pdb(NL.join(lineas) + NL)

        assert informe == {"elementos_inferidos": 1}
        assert texto.splitlines()[i].rstrip() == PDB_REAL.splitlines()[i].rstrip()

    def test_calcio_ion_frente_a_carbono_alfa_y_cloro_de_un_ligando(self):
        assert elemento_desde_el_nombre("ATOM      2  CA  GLY A  60      75.008 105.246  90.531") == "C"
        assert elemento_desde_el_nombre("HETATM  900 CA    CA A 801      10.000  10.000  10.000") == "CA"
        assert elemento_desde_el_nombre("HETATM  901 ZN    ZN A 802      10.000  10.000  10.000") == "ZN"
        assert elemento_desde_el_nombre("HETATM  902 CL1  LIG A 803      10.000  10.000  10.000") == "CL"
        assert elemento_desde_el_nombre("HETATM  903  C1  LIG A 803      10.000  10.000  10.000") == "C"
        assert elemento_desde_el_nombre("ATOM    904 1HG1 LEU A  10      10.000  10.000  10.000") == "H"
        assert elemento_desde_el_nombre("ATOM    905 HG21 THR A  11      10.000  10.000  10.000") == "H"

    def test_una_linea_sin_columna_de_elemento_mas_corta_que_78_se_completa(self):
        corta = linea_pdb(1, "CA", "ALA", "A", 1, (0.0, 0.0, 0.0), "C")[:66]

        texto, informe = normalizar_pdb(corta + NL)

        assert informe == {"elementos_inferidos": 1} and texto.splitlines()[0][76:78] == " C"
