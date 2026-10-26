"""PQR: se lee conservando nombres y coordenadas, y se declara que Vina no usa sus cargas.

Dos familias de pruebas, y conviene no confundirlas:

* ``TestLecturaFiel``, ``TestDeclaraciones`` y ``TestRechazos`` usan PQR *derivados* del recorte REAL de 8HFI
  protonado (cargas y radios de relleno, escritos por ``a_pqr``): comprueban la lógica del lector con variantes de
  formato que PDB2PQR no produce (sin cadena, separados por espacios).
* ``TestSalidaRealDePdb2pqr`` usa salidas REALES de PDB2PQR 3.7.1 con PROPKA 3.5.1 (venv aparte; órdenes, versiones
  y hashes en ``data/receptores_propios/pdb2pqr_procedencia.json``). Fue la que encontró el defecto de los nombres
  pegados (``1CBDISU``): el lector de campos lo leía como un átomo sin cadena y escribía una línea corrupta sin avisar.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from services.targets.errores_subida import ErrorDeSubida
from services.targets.lector_pqr import _por_campos, pqr_a_pdb

DATOS = Path(__file__).parent / "data" / "receptores_propios"
PDB = (DATOS / "8hfi_protonado.pdb").read_text(encoding="utf-8")


def a_pqr(pdb: str, *, con_cadena: bool = True, estilo: str = "columnas") -> str:
    """El mismo PDB escrito como PQR: carga y radio de relleno en lugar de ocupación, factor B y elemento."""
    lineas = []
    for l in pdb.splitlines():
        if not l.startswith(("ATOM", "HETATM")):
            lineas.append(l)
            continue
        carga, radio = (-0.3 if l[12:16].strip() == "N" else 0.1), 1.85
        x, y, z = l[30:38], l[38:46], l[46:54]
        if estilo == "columnas":
            # Como PDB2PQR: columnas del PDB hasta las coordenadas, luego carga y radio.
            lineas.append(f"{l[:6]}{l[6:11]} {l[12:16]}{l[16]}{l[17:20]} {l[21]}{l[22:27]}   {x}{y}{z} {carga:7.4f} {radio:6.4f}")
        else:
            # PQR estricto: todo separado por espacios (la cadena es opcional).
            cadena = f" {l[21]}" if con_cadena else ""
            lineas.append(f"{l[:6].strip():<6} {int(l[6:11]):>5}  {l[12:16].strip():<4} {l[17:20]}{cadena} {l[22:26].strip():>4}"
                          f"   {float(x):8.3f} {float(y):8.3f} {float(z):8.3f} {carga:7.4f} {radio:6.4f}")
    return "\n".join(lineas) + "\n"


def _atomos(pdb: str):
    return [(l[:6].strip(), l[12:16].strip(), l[17:20].strip(), l[21], l[22:26].strip(), l[30:54])
            for l in pdb.splitlines() if l.startswith(("ATOM", "HETATM"))]


class TestLecturaFiel:
    @pytest.mark.parametrize("estilo", ["columnas", "campos"])
    def test_nombres_residuos_cadenas_y_coordenadas_se_conservan(self, estilo):
        texto, informe = pqr_a_pdb(a_pqr(PDB, estilo=estilo))

        assert _atomos(texto) == _atomos(PDB)
        assert informe["atomos"] == len(_atomos(PDB))

    def test_el_elemento_se_infiere_y_coincide_con_el_del_pdb(self):
        texto, _ = pqr_a_pdb(a_pqr(PDB))

        original = [l[76:78].strip() for l in PDB.splitlines() if l.startswith(("ATOM", "HETATM"))]
        leido = [l[76:78].strip() for l in texto.splitlines() if l.startswith(("ATOM", "HETATM"))]
        assert leido == original

    def test_los_nombres_de_protonacion_y_las_aguas_pasan_tal_cual(self):
        texto, _ = pqr_a_pdb(a_pqr(PDB.replace(" HID ", " HSD ").replace(" HOH ", " WAT ")))

        nombres = {l[17:20].strip() for l in texto.splitlines() if l.startswith(("ATOM", "HETATM"))}
        assert {"HSD", "WAT", "CL"} <= nombres and "HID" not in nombres


class TestDeclaraciones:
    def test_las_cargas_y_los_radios_se_descartan_y_se_cuentan(self):
        _, informe = pqr_a_pdb(a_pqr(PDB))

        assert informe["cargas_y_radios_descartados"] == informe["atomos"]
        assert "Vina no usa las cargas" in informe["motivo_del_descarte"]
        assert isinstance(informe["carga_neta_del_pqr"], float)

    def test_sin_cadena_se_asigna_a_y_se_declara(self):
        pqr = a_pqr(PDB, con_cadena=False, estilo="campos")

        texto, informe = pqr_a_pdb(pqr)

        assert informe["atomos_sin_cadena"] == informe["atomos"]
        assert {l[21] for l in texto.splitlines() if l.startswith(("ATOM", "HETATM"))} == {"A"}

    def test_un_residuo_terminal_de_amber_se_reduce_a_su_base_y_se_declara(self):
        pqr = a_pqr(PDB, estilo="campos")
        lineas = pqr.splitlines()
        i = next(k for k, l in enumerate(lineas) if l.startswith("ATOM") and " LEU " in l)
        lineas[i] = lineas[i].replace(" LEU ", " NLEU ", 1)

        texto, informe = pqr_a_pdb("\n".join(lineas) + "\n")

        assert informe["residuos_terminales_reducidos"] == {"NLEU": "LEU"}
        assert _atomos(texto) == _atomos(PDB)


class TestRechazos:
    def test_una_linea_ilegible_se_rechaza_con_su_numero(self):
        roto = a_pqr(PDB, estilo="campos").splitlines()
        roto.insert(3, "ATOM      9  CA  ALA A   9   esto no son coordenadas  0.1000 1.8500")

        with pytest.raises(ErrorDeSubida) as error:
            pqr_a_pdb("\n".join(roto) + "\n", "mi.pqr")

        assert error.value.codigo == "PQR_LINEA_ILEGIBLE" and "línea 4" in error.value.mensaje("es")
        assert "mi.pqr" in error.value.mensaje("es") and "Line 4" in error.value.mensaje("en")

    def test_un_pdb_con_extension_pqr_se_detecta_porque_le_faltan_carga_y_radio(self):
        # Un PDB tiene ocupación y factor B (y elemento) donde un PQR tiene carga y radio: la lectura falla con motivo.
        with pytest.raises(ErrorDeSubida) as error:
            pqr_a_pdb(PDB)

        assert error.value.codigo == "PQR_LINEA_ILEGIBLE"

    def test_un_nombre_de_residuo_largo_que_no_es_terminal_se_rechaza(self):
        pqr = "ATOM      1  C1  XYZW A   1      1.000   2.000   3.000 0.1000 1.8500\n"

        with pytest.raises(ErrorDeSubida) as error:
            pqr_a_pdb(pqr)

        assert error.value.codigo == "PQR_RESIDUO_NO_REPRESENTABLE" and "XYZW" in error.value.mensaje("es")

    def test_un_archivo_sin_atomos_se_rechaza(self):
        with pytest.raises(ErrorDeSubida) as error:
            pqr_a_pdb("REMARK nada\nEND\n")

        assert error.value.codigo == "PQR_SIN_ATOMOS"


def _real(nombre: str) -> str:
    return (DATOS / nombre).read_text(encoding="utf-8")


def _por_clave(pdb: str) -> dict[tuple[str, str, str], tuple[str, str]]:
    return {(l[21], l[22:26].strip(), l[12:16].strip()): (l[17:20].strip(), l[30:54])
            for l in pdb.splitlines() if l.startswith(("ATOM", "HETATM"))}


class TestSalidaRealDePdb2pqr:
    def test_el_pqr_amber_real_se_lee_entero_con_los_mismos_residuos_y_coordenadas_que_su_pdb(self):
        origen = _por_clave((DATOS / "8hfi_recortado.pdb").read_text(encoding="utf-8"))

        texto, informe = pqr_a_pdb(_real("8hfi_recortado_amber.pqr"), "8hfi_recortado_amber.pqr")

        leido = _por_clave(texto)
        comunes = [k for k in origen if k in leido]
        assert informe["atomos"] == 744 and informe["atomos_sin_cadena"] == 0
        assert informe["cargas_y_radios_descartados"] == 744
        assert len(comunes) == 364                       # los 29 HETATM (ligando, aguas, cloruro) no los escribe PDB2PQR
        assert all(origen[k][0] == leido[k][0] for k in comunes)      # ningún nombre de residuo cambia
        # PDB2PQR movió 2 átomos pesados al optimizar la red de enlaces de hidrógeno (medido); el lector no mueve ninguno.
        assert sum(1 for k in comunes if origen[k][1] != leido[k][1]) == 2
        assert {l[76:78].strip() for l in texto.splitlines() if l.startswith("ATOM")} == {"C", "H", "N", "O", "S"}

    def test_el_pqr_charmm_real_se_rechaza_por_el_carboxilo_escrito_como_residuo_aparte(self):
        with pytest.raises(ErrorDeSubida) as error:
            pqr_a_pdb(_real("8hfi_recortado_charmm.pqr"), "8hfi_recortado_charmm.pqr")

        assert error.value.codigo == "PQR_PARCHES_CHARMM"
        assert error.value.datos["parches"] == {"TER": ["A:105"]}
        es, en = error.value.mensaje("es"), error.value.mensaje("en")
        assert "«TER»" in es and "A:105" in es and "--ffout=AMBER" in es
        assert "CHARMM patches" in en and "upload the protonated PDB" in en

    def test_el_extracto_real_con_disu_se_rechaza_en_vez_de_escribir_una_linea_corrupta(self):
        with pytest.raises(ErrorDeSubida) as error:
            pqr_a_pdb(_real("charmm_disu_extracto.pqr"), "charmm_disu_extracto.pqr")

        assert error.value.codigo == "PQR_PARCHES_CHARMM" and error.value.datos["parches"] == {"DISU": ["A:176"]}

    def test_control_la_lectura_por_campos_sola_confunde_1cbdisu_con_un_atomo_sin_cadena(self):
        # El defecto que esta salida real destapó: el nombre del átomo y el del residuo, pegados, dejan 10 campos
        # —los mismos que una línea sin cadena— y la lectura por campos devuelve basura sin fallar.
        linea = next(l for l in _real("charmm_disu_extracto.pqr").splitlines() if "DISU" in l)

        fila = _por_campos(linea)

        assert fila is not None and fila["nombre"] == "1CBDISU" and fila["residuo"] == "A" and fila["cadena"] == ""

    def test_el_mismo_extracto_sin_parche_se_lee_bien_por_columnas(self):
        # Caso que NO debe detectar: las mismas líneas con la cistina escrita como residuo normal.
        sano = "\n".join(l.replace("1CBDISU", " CB CYS").replace("1SGDISU", " SG CYS")
                         for l in _real("charmm_disu_extracto.pqr").splitlines()) + "\n"
        assert "DISU" not in sano

        texto, informe = pqr_a_pdb(sano, "sano.pqr")

        nombres = [(l[12:16].strip(), l[17:20].strip(), l[21]) for l in texto.splitlines() if l.startswith("ATOM")]
        assert ("CB", "CYS", "A") in nombres and ("SG", "CYS", "A") in nombres
        assert informe["atomos_sin_cadena"] == 0

    def test_una_linea_sin_columnas_con_el_residuo_de_una_letra_se_rechaza_por_ambigua(self):
        pegada = "ATOM 1887 1CBDISU A 176 97.296 102.569 138.561 -0.1000 2.1750\n"

        with pytest.raises(ErrorDeSubida) as error:
            pqr_a_pdb(pegada, "pegada.pqr")

        assert error.value.codigo == "PQR_LINEA_AMBIGUA" and "línea 1" in error.value.mensaje("es")
        assert "Line 1" in error.value.mensaje("en")

    def test_un_residuo_de_una_letra_con_cadena_no_es_ambiguo(self):
        # Caso que NO debe detectar: con la cadena presente (11 campos) un nombre de una letra se respeta.
        linea = "ATOM 1 CA A A 1 1.000 2.000 3.000 0.1000 1.8500\n"

        texto, informe = pqr_a_pdb(linea, "rna.pqr")

        assert informe["atomos"] == 1 and informe["atomos_sin_cadena"] == 0
        assert texto.splitlines()[0][17:20].strip() == "A" and texto.splitlines()[0][21] == "A"
