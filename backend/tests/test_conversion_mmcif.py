"""mmCIF → PDB clásico: paridad con el PDB del RCSB y casos que el conversor DEBE declarar o rechazar.

La paridad usa un recorte REAL de 8HFI (RCSB, dominio público): el mmCIF y el PDB de los mismos
residuos. Los casos adversos son mmCIF sintéticos mínimos pero completos.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from services.chemistry.ensamblaje_biologico import generar_unidad_biologica, leer_matrices
from services.targets.conversion_mmcif import mmcif_a_pdb
from services.targets.errores_subida import ErrorDeSubida
from tests.receptores_propios_ayudas import mmcif_sintetico, residuo_ala, residuo_hetero

DATOS = Path(__file__).parent / "data" / "receptores_propios"


def _atomos(pdb: str) -> list[tuple]:
    return [
        (l[:6].strip(), l[12:16].strip(), l[16:17].strip(), l[17:20].strip(), l[21:22], l[22:26].strip(),
         l[26:27].strip(), l[30:38], l[38:46], l[46:54], l[54:60], l[60:66], l[76:78].strip())
        for l in pdb.splitlines() if l.startswith(("ATOM", "HETATM"))
    ]


def _cadenas_de(pdb: str) -> set[str]:
    return {l[21:22] for l in pdb.splitlines() if l.startswith(("ATOM", "HETATM"))}


# ── Paridad con el PDB del RCSB ───────────────────────────────────────────


@pytest.fixture(scope="module")
def conversion():
    return mmcif_a_pdb((DATOS / "8hfi_recortado.cif").read_text(encoding="utf-8"), "8hfi_recortado.cif")


@pytest.fixture(scope="module")
def pdb_rcsb():
    return (DATOS / "8hfi_recortado.pdb").read_text(encoding="utf-8")


class TestParidadConElPdbDelRcsb:
    def test_los_atomos_coinciden_uno_a_uno_y_en_el_mismo_orden(self, conversion, pdb_rcsb):
        convertidos, esperados = _atomos(conversion.pdb), _atomos(pdb_rcsb)

        assert len(convertidos) == len(esperados) == 393
        assert convertidos == esperados

    def test_la_cabecera_que_leen_las_funciones_del_producto_coincide(self, conversion, pdb_rcsb):
        from services.targets.ingestion_manager import extract_pdb_metadata

        assert extract_pdb_metadata(conversion.pdb) == extract_pdb_metadata(pdb_rcsb) == {
            "organism": "Homo Sapiens", "resolution": 2.5}
        assert conversion.metodo == "ELECTRON MICROSCOPY" and conversion.resolucion == 2.5

    def test_los_residuos_no_observados_coinciden_con_el_remark_465(self, conversion, pdb_rcsb):
        from services.docking.preparer import _residuos_no_observados

        assert _residuos_no_observados(conversion.pdb) == _residuos_no_observados(pdb_rcsb)
        assert len(_residuos_no_observados(conversion.pdb)["A"]) == 69

    def test_el_ensamblaje_declarado_es_la_identidad_y_no_inventa_copias(self, conversion, pdb_rcsb):
        assert conversion.informe["ensamblaje"]["estado"] == "aplicado"
        assert conversion.informe["ensamblaje"]["usado"] == "1"
        assert len(leer_matrices(conversion.pdb)) == len(leer_matrices(pdb_rcsb)) == 1
        assert generar_unidad_biologica(conversion.pdb).pdb == conversion.pdb

    def test_el_informe_no_declara_cambios_que_no_hubo(self, conversion):
        informe = conversion.informe
        assert informe["cadenas"] == [{"original": "A", "pdb": "A", "renombrada": False}]
        assert informe["residuos_renombrados"] == [] and informe["avisos"] == []
        assert informe["modelos"] == {"en_el_archivo": 1, "usado": 1} and not informe["serie_renumerada"]


# ── Cadenas de varias letras ──────────────────────────────────────────────


def _proteina(auth: str, label: str, residuos: int = 3):
    return {"auth": auth, "label": label, "residuos": [residuo_ala(n) for n in range(1, residuos + 1)]}


class TestCadenas:
    def test_las_cadenas_de_una_letra_se_conservan(self):
        conversion = mmcif_a_pdb(mmcif_sintetico([_proteina("A", "A"), _proteina("B", "B")]))

        assert _cadenas_de(conversion.pdb) == {"A", "B"}
        assert all(not c["renombrada"] for c in conversion.informe["cadenas"])

    def test_una_cadena_de_varias_letras_recibe_una_letra_libre_y_queda_declarada(self):
        conversion = mmcif_a_pdb(mmcif_sintetico([_proteina("AAA", "A"), _proteina("A", "B"), _proteina("B1", "C")]))

        correspondencia = {c["original"]: c["pdb"] for c in conversion.informe["cadenas"]}
        assert correspondencia["A"] == "A"                          # la de una letra no se mueve
        assert len({correspondencia["AAA"], correspondencia["B1"], "A"}) == 3   # y ninguna se funde
        assert _cadenas_de(conversion.pdb) == set(correspondencia.values())
        assert [c["renombrada"] for c in conversion.informe["cadenas"]] == [True, False, True]
        assert "MMCIF_CADENAS_RENOMBRADAS" in conversion.informe["avisos"]

    def test_la_asignacion_es_determinista(self):
        texto = mmcif_sintetico([_proteina("XYZ", "A"), _proteina("Q9", "B"), _proteina("C", "C")])

        assert mmcif_a_pdb(texto).informe["cadenas"] == mmcif_a_pdb(texto).informe["cadenas"]
        assert mmcif_a_pdb(texto).pdb == mmcif_a_pdb(texto).pdb

    def test_mas_de_62_cadenas_se_rechaza_con_su_motivo(self):
        cadenas = [_proteina(f"C{i:02d}", f"L{i:02d}", residuos=1) for i in range(70)]

        with pytest.raises(ErrorDeSubida) as error:
            mmcif_a_pdb(mmcif_sintetico(cadenas))

        assert error.value.codigo == "MMCIF_DEMASIADAS_CADENAS"
        assert "62" in error.value.mensaje("es") and "62" in error.value.mensaje("en")


# ── Códigos CCD de cinco caracteres ───────────────────────────────────────


class TestResiduosConNombreLargo:
    def _con_ligandos(self, *nombres):
        cadenas = [_proteina("A", "A")]
        for i, nombre in enumerate(nombres):
            cadenas.append({"auth": "A", "label": f"L{i}", "polimero": False,
                            "residuos": [residuo_hetero(nombre, 401 + i, (5.0 + 3 * i, 5.0, 5.0))]})
        return mmcif_sintetico(cadenas)

    def test_dos_ligandos_distintos_con_el_mismo_prefijo_no_se_funden(self):
        # El caso real de 8YUT: A1D67 y A1D5J colapsarían en «A1D» si se truncara el nombre.
        conversion = mmcif_a_pdb(self._con_ligandos("A1D67", "A1D5J"))

        renombrados = {r["original"]: r["pdb"] for r in conversion.informe["residuos_renombrados"]}
        assert set(renombrados) == {"A1D67", "A1D5J"} and len(set(renombrados.values())) == 2
        assert all(len(v) == 3 for v in renombrados.values())
        hetero = {l[17:20].strip() for l in conversion.pdb.splitlines() if l.startswith("HETATM")}
        assert hetero == set(renombrados.values()) and "A1D" not in hetero

    def test_el_sustituto_no_choca_con_un_residuo_que_ya_esta_en_el_archivo(self):
        conversion = mmcif_a_pdb(self._con_ligandos("A1D5J", "Z00"))

        sustituto = conversion.informe["residuos_renombrados"][0]["pdb"]
        assert sustituto != "Z00" and len(sustituto) == 3
        assert {l[17:20].strip() for l in conversion.pdb.splitlines() if l.startswith("HETATM")} == {sustituto, "Z00"}

    def test_la_correspondencia_lleva_cadena_numero_y_atomos(self):
        conversion = mmcif_a_pdb(self._con_ligandos("A1LX4"))

        fila = conversion.informe["residuos_renombrados"][0]
        assert (fila["original"], fila["cadena"], fila["numero"], fila["atomos"]) == ("A1LX4", "A", 401, 2)
        assert "MMCIF_RESIDUOS_RENOMBRADOS" in conversion.informe["avisos"]

    def test_los_nombres_de_tres_caracteres_no_se_tocan(self):
        conversion = mmcif_a_pdb(self._con_ligandos("HEM", "ZN"))

        assert conversion.informe["residuos_renombrados"] == []


# ── Lo que el PDB clásico no puede representar se abstiene ────────────────


class TestLimitesDelFormato:
    def test_un_numero_de_residuo_que_no_cabe_se_rechaza_con_cadena_y_numero(self):
        cadena = {"auth": "A", "label": "A", "residuos": [residuo_ala(1), residuo_ala(10234)]}

        with pytest.raises(ErrorDeSubida) as error:
            mmcif_a_pdb(mmcif_sintetico([cadena]))

        assert error.value.codigo == "MMCIF_NUMERACION_NO_REPRESENTABLE"
        assert "A:10234" in error.value.mensaje("es") and "A:10234" in error.value.mensaje("en")

    def test_los_numeros_negativos_y_el_limite_exacto_pasan(self):
        cadena = {"auth": "A", "label": "A", "residuos": [residuo_ala(-5), residuo_ala(9999, x0=-37900.0)]}

        conversion = mmcif_a_pdb(mmcif_sintetico([cadena]))

        assert {int(l[22:26]) for l in conversion.pdb.splitlines() if l.startswith("ATOM")} == {-5, 9999}

    def test_mas_de_99999_atomos_repiten_el_serial_y_lo_declaran_sin_romper_columnas(self):
        cadena = {"auth": "A", "label": "A", "residuos": [residuo_ala(n % 2500 + 1) for n in range(20_001)]}

        conversion = mmcif_a_pdb(mmcif_sintetico([cadena]))

        lineas = [l for l in conversion.pdb.splitlines() if l.startswith("ATOM")]
        assert len(lineas) == 100_005 and conversion.informe["serie_renumerada"]
        assert "MMCIF_SERIE_RENUMERADA" in conversion.informe["avisos"]
        assert {len(l) for l in lineas} == {78}
        assert int(lineas[99_999][6:11]) == 1 and int(lineas[99_998][6:11]) == 99_999

    def test_una_coordenada_fuera_de_rango_se_rechaza(self):
        atomos = [("CA", "C", (123456.0, 0.0, 0.0), None, 1.0)]
        cadena = {"auth": "A", "label": "A", "residuos": [("ALA", 1, False, atomos)]}

        with pytest.raises(ErrorDeSubida) as error:
            mmcif_a_pdb(mmcif_sintetico([cadena]))

        assert error.value.codigo == "MMCIF_COORDENADA_NO_REPRESENTABLE"


# ── Modelos, altlocs, hidrógenos ──────────────────────────────────────────


class TestContenido:
    def test_un_conjunto_de_rmn_usa_el_modelo_uno_y_lo_declara(self):
        conversion = mmcif_a_pdb(mmcif_sintetico([_proteina("A", "A")], modelos=4))

        assert conversion.informe["modelos"] == {"en_el_archivo": 4, "usado": 1}
        assert "MMCIF_VARIOS_MODELOS" in conversion.informe["avisos"]
        assert len(_atomos(conversion.pdb)) == 15            # 3 residuos × 5 átomos, una sola vez
        assert conversion.avisos[0]["es"].startswith("El archivo trae 4 modelos")

    def test_los_altlocs_y_las_ocupaciones_se_conservan_para_que_el_filtro_decida(self):
        a = residuo_ala(1, altloc="A", ocupacion=0.6)
        b = residuo_ala(1, altloc="B", ocupacion=0.4)
        cadena = {"auth": "A", "label": "A", "residuos": [(a[0], 1, False, a[3] + b[3])]}

        conversion = mmcif_a_pdb(mmcif_sintetico([cadena]))

        atomos = _atomos(conversion.pdb)
        assert {x[2] for x in atomos} == {"A", "B"} and {x[10].strip() for x in atomos} == {"0.60", "0.40"}
        assert conversion.informe["atomos_con_altloc"] == 10

    def test_los_hidrogenos_y_la_numeracion_negativa_se_conservan(self):
        atomos = [("N", "N", (0.0, 0.0, 0.0), None, 1.0), ("H", "H", (0.0, 1.0, 0.0), None, 1.0)]
        cadena = {"auth": "A", "label": "A", "residuos": [("ALA", -2, False, atomos)]}

        conversion = mmcif_a_pdb(mmcif_sintetico([cadena]))

        assert conversion.informe["hidrogenos"] == 1
        assert [l[76:78].strip() for l in conversion.pdb.splitlines() if l.startswith("ATOM")] == ["N", "H"]

    def test_las_lineas_de_atomo_tienen_el_ancho_del_formato_pdb(self):
        conversion = mmcif_a_pdb(mmcif_sintetico([_proteina("A", "A"), {
            "auth": "A", "label": "L", "polimero": False, "residuos": [residuo_hetero("HEM", 401)]}]))

        assert {len(l) for l in conversion.pdb.splitlines() if l.startswith(("ATOM", "HETATM"))} == {78}
        assert [l[:6] for l in conversion.pdb.splitlines() if l.startswith(("ATOM", "HETATM"))][-2:] == ["HETATM"] * 2


# ── Ensamblajes ───────────────────────────────────────────────────────────


class TestEnsamblaje:
    def _dos_cadenas(self, ensamblajes):
        return mmcif_sintetico([_proteina("A", "A", 4), _proteina("B", "B", 4)], ensamblajes=ensamblajes)

    def test_sin_ensamblajes_se_usa_lo_depositado(self):
        conversion = mmcif_a_pdb(self._dos_cadenas(None))

        assert conversion.informe["ensamblaje"]["estado"] == "unidad_asimetrica"
        assert conversion.informe["ensamblaje"]["declarados"] == [] and not leer_matrices(conversion.pdb)

    def test_un_ensamblaje_con_dos_operadores_que_cubre_todo_se_aplica_y_se_declara(self):
        conversion = mmcif_a_pdb(self._dos_cadenas([("1", [("1,2", ["A", "B"])])]))

        ensamblaje = conversion.informe["ensamblaje"]
        assert ensamblaje["estado"] == "aplicado" and ensamblaje["operadores_aplicados"] == 2
        assert ensamblaje["declarados"][0]["id"] == "1" and ensamblaje["declarados"][0]["detalle"] == "dimeric"
        generado = generar_unidad_biologica(conversion.pdb)
        assert generado.generado and generado.operadores == 2
        assert len(generado.cadenas_finales) == 4

    def test_un_ensamblaje_que_deja_un_polimero_fuera_no_inventa_copias(self):
        conversion = mmcif_a_pdb(self._dos_cadenas([("1", [("1,2", ["A"])])]))

        ensamblaje = conversion.informe["ensamblaje"]
        assert ensamblaje["estado"] == "unidad_asimetrica" and ensamblaje["usado"] is None
        assert "B" in ensamblaje["motivo"] and not leer_matrices(conversion.pdb)
        assert not generar_unidad_biologica(conversion.pdb).generado

    def test_operadores_distintos_para_cadenas_distintas_no_se_pueden_expresar(self):
        conversion = mmcif_a_pdb(self._dos_cadenas([("1", [("1,2", ["A"]), ("1,3", ["B"])])]))

        assert conversion.informe["ensamblaje"]["estado"] == "unidad_asimetrica"
        assert "operadores distintos" in conversion.informe["ensamblaje"]["motivo"]

    def test_se_usa_el_ensamblaje_1_aunque_no_sea_el_primero_declarado(self):
        conversion = mmcif_a_pdb(self._dos_cadenas([("2", [("1", ["A", "B"])]), ("1", [("1,2", ["A", "B"])])]))

        assert conversion.informe["ensamblaje"]["usado"] == "1"
        assert [d["id"] for d in conversion.informe["ensamblaje"]["declarados"]] == ["2", "1"]


# ── Archivos que no son un mmCIF de coordenadas ───────────────────────────


class TestIlegibles:
    def test_un_mmcif_truncado_o_sin_tabla_de_atomos_se_rechaza_sin_rutas(self):
        completo = mmcif_sintetico([_proteina("A", "A")])
        sin_atomos = "data_X\n_entry.id X\nloop_\n_entity.id\n_entity.type\n1 polymer\n"

        with pytest.raises(ErrorDeSubida) as sin_tabla:
            mmcif_a_pdb(sin_atomos, "x.cif")
        with pytest.raises(ErrorDeSubida) as roto:
            mmcif_a_pdb(completo.replace("loop_", "loop_\n'comilla sin cerrar", 1), "x.cif")

        assert sin_tabla.value.codigo == "MMCIF_SIN_ATOMOS"
        assert roto.value.codigo == "MMCIF_ILEGIBLE"
        for error in (sin_tabla.value, roto.value):
            assert "\\" not in error.mensaje("es") and "x.cif" in error.mensaje("es")
