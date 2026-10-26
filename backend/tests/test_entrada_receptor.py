"""Lo básico de la subida: extensión, .gz con tope, contenido que corresponde y mensajes útiles.

Cada familia trae casos que el lector DEBE rechazar y casos que NO debe tocar.
"""

from __future__ import annotations

import gzip
import io

import pytest

from services.targets import entrada_receptor as er
from services.targets.entrada_receptor import (
    ArchivoSubido,
    clase_de_contenido,
    leer_subida,
    nombre_seguro,
    sin_proteina,
)
from services.targets.errores_subida import ErrorDeSubida
from tests.receptores_propios_ayudas import linea_pdb, pdb_sintetico, pdbqt_sintetico

PDB = pdb_sintetico(residuos=12).encode()
PDBQT = pdbqt_sintetico(residuos=12).encode()
MMCIF = (
    b"data_TEST\n#\nloop_\n_atom_site.group_PDB\n_atom_site.id\n_atom_site.type_symbol\n"
    b"_atom_site.label_atom_id\n_atom_site.label_comp_id\n_atom_site.auth_asym_id\n"
    b"_atom_site.auth_seq_id\n_atom_site.Cartn_x\n_atom_site.Cartn_y\n_atom_site.Cartn_z\n"
    b"ATOM 1 N N ALA A 1 1.000 2.000 3.000\n"
)
SDF = b"ethanol\n  rdkit\n\n  3  2  0  0  0  0  0  0  0  0999 V2000\n    0.0 0.0 0.0 C   0  0\nM  END\n$$$$\n"


def _gz(datos: bytes) -> bytes:
    salida = io.BytesIO()
    with gzip.GzipFile(fileobj=salida, mode="wb") as f:
        f.write(datos)
    return salida.getvalue()


def _error(nombre: str, contenido: bytes) -> ErrorDeSubida:
    with pytest.raises(ErrorDeSubida) as error:
        leer_subida(nombre, contenido)
    return error.value


# ── La extensión, sin distinguir mayúsculas ───────────────────────────────


class TestExtension:
    @pytest.mark.parametrize("nombre,formato", [
        ("8hfi.pdb", "pdb"), ("8HFI_CRUDO.PDB", "pdb"), ("pdb8hfi.ent", "pdb"), ("PDB8HFI.ENT", "pdb"),
        ("8hfi.cif", "mmcif"), ("8HFI.CIF", "mmcif"), ("8hfi.mmcif", "mmcif"), ("8HFI.MmCIF", "mmcif"),
        ("8hfi.pqr", "pqr"), ("8HFI.PQR", "pqr"), ("8hfi.pdbqt", "pdbqt"), ("8HFI.PdbQT", "pdbqt"),
    ])
    def test_cada_extension_admitida_se_reconoce_en_cualquier_grafia(self, nombre, formato):
        contenido = {"pdb": PDB, "mmcif": MMCIF, "pqr": PDB, "pdbqt": PDBQT}[formato]

        archivo = leer_subida(nombre, contenido)

        assert archivo.formato == formato and not archivo.comprimido

    @pytest.mark.parametrize("nombre", ["8hfi.pdb.gz", "8HFI.PDB.GZ", "x.Pdb.Gz"])
    def test_el_gz_se_reconoce_en_cualquier_grafia(self, nombre):
        archivo = leer_subida(nombre, _gz(PDB))

        assert archivo.formato == "pdb" and archivo.comprimido and archivo.contenido == PDB
        assert archivo.nombre_almacenado == "original.pdb.gz"

    @pytest.mark.parametrize("nombre", ["x.txt", "x", "x.pdb2", "x.zip", "x.tar.gz", ".gz", "x.PDBQT.bak"])
    def test_lo_que_no_es_un_receptor_se_rechaza_listando_lo_admitido(self, nombre):
        error = _error(nombre, PDB)

        assert error.codigo == "EXTENSION_NO_ADMITIDA"
        for ext in (".pdb", ".cif", ".pqr", ".pdbqt", ".gz"):
            assert ext in error.mensaje("es") and ext in error.mensaje("en")

    @pytest.mark.parametrize("nombre", ["lig.sdf", "LIG.SDF", "lig.mol2", "lig.mol", "lig.smi"])
    def test_un_formato_de_ligando_se_explica_y_no_se_ofrece_como_receptor(self, nombre):
        error = _error(nombre, SDF)

        assert error.codigo == "EXTENSION_ES_LIGANDO"
        assert "moléculas pequeñas" in error.mensaje("es") and "small-molecule" in error.mensaje("en")
        assert "PDB o mmCIF" in error.mensaje("es") and "PDB or mmCIF" in error.mensaje("en")

    def test_los_formatos_propietarios_dicen_a_que_se_exportan(self):
        error = _error("receptor.mae", b"x")

        assert error.codigo == "EXTENSION_PROPIETARIA" and "Maestro" in error.mensaje("es")
        assert "PDB o mmCIF" in error.mensaje("es")

    def test_ningun_mensaje_ofrece_sdf_como_formato_de_receptor(self):
        # La lista de lo admitido no menciona SDF (hoy el router decía «PDB, PDBQT o SDF»)…
        for idioma in ("es", "en"):
            assert "sdf" not in _error("x.txt", PDB).mensaje(idioma).lower()
        # …y cuando llega un SDF, el mensaje dice que NO es un receptor y qué subir en su lugar.
        for nombre in ("x.sdf", "x.pdb", "x.pdbqt"):
            for idioma, no_es in (("es", "no de receptores"), ("en", "not a receptor")):
                texto = _error(nombre, SDF).mensaje(idioma)
                assert "PDB" in texto and ("mmCIF" in texto)
                assert no_es in texto or "molécula pequeña" in texto or "small molecule" in texto, texto


# ── El .gz, con tope ──────────────────────────────────────────────────────


class TestGz:
    def test_el_tope_es_de_128_mib_descomprimidos(self):
        assert er.MAX_DESCOMPRIMIDO_BYTES == 128 * 1024 * 1024

    def test_una_bomba_gzip_se_corta_sin_materializarla(self, monkeypatch):
        monkeypatch.setattr(er, "MAX_DESCOMPRIMIDO_BYTES", 64 * 1024)
        bomba = _gz(b"ATOM  " + b"0" * (2 * 1024 * 1024))         # 2 MiB de ceros caben en ~2 KiB

        assert len(bomba) < 4096
        error = _error("bomba.pdb.gz", bomba)

        assert error.codigo == "GZ_DEMASIADO_GRANDE" and error.estado == 413
        assert "descomprimido" in error.mensaje("es") and "decompressed" in error.mensaje("en")

    def test_justo_en_el_tope_se_acepta_y_un_byte_mas_no(self, monkeypatch):
        cuerpo = PDB + b"REMARK " + b"x" * 500 + b"\n"
        monkeypatch.setattr(er, "MAX_DESCOMPRIMIDO_BYTES", len(cuerpo))

        assert leer_subida("a.pdb.gz", _gz(cuerpo)).bytes_contenido == len(cuerpo)
        assert _error("a.pdb.gz", _gz(cuerpo + b"x")).codigo == "GZ_DEMASIADO_GRANDE"

    def test_un_gz_que_no_lo_es_o_esta_truncado_se_rechaza(self):
        assert _error("a.pdb.gz", PDB).codigo == "GZ_INVALIDO"
        assert _error("a.pdb.gz", _gz(PDB)[:-12]).codigo == "GZ_INVALIDO"
        assert _error("a.pdb.gz", b"\x1f\x8b" + b"basura" * 20).codigo == "GZ_INVALIDO"

    def test_un_gzip_sin_la_extension_gz_dice_que_la_añada(self):
        error = _error("a.pdb", _gz(PDB))

        assert error.codigo == "GZ_SIN_EXTENSION" and "a.pdb.gz" in error.mensaje("es")

    def test_un_archivo_vacio_o_vacio_al_descomprimir_se_rechaza(self):
        assert _error("a.pdb", b"").codigo == "ARCHIVO_VACIO"
        assert _error("a.pdb.gz", _gz(b"")).codigo == "ARCHIVO_VACIO"


# ── El contenido tiene que corresponder a la extensión ────────────────────


class TestContenido:
    def test_un_mmcif_con_nombre_de_pdb_dice_que_es_mmcif(self):
        error = _error("x.pdb", MMCIF)

        assert error.codigo == "CONTENIDO_ES_MMCIF" and ".cif" in error.mensaje("es")

    def test_un_pdbqt_con_nombre_de_pdb_o_un_pdb_con_nombre_de_pdbqt(self):
        assert _error("x.pdb", PDBQT).codigo == "CONTENIDO_ES_PDBQT"
        assert _error("x.pdbqt", PDB).codigo == "CONTENIDO_ES_PDB"

    def test_un_sdf_con_nombre_de_receptor_dice_que_es_una_molecula(self):
        for nombre in ("x.pdb", "x.cif", "x.pdbqt", "x.pqr"):
            error = _error(nombre, SDF)
            assert error.codigo == "CONTENIDO_ES_SDF", nombre
            assert "molécula pequeña" in error.mensaje("es") and "small molecule" in error.mensaje("en")

    def test_un_archivo_sin_atomos_no_se_toma_por_receptor(self):
        for nombre in ("x.pdb", "x.cif", "x.pdbqt", "x.pqr"):
            assert _error(nombre, b"HEADER   nada\nREMARK   2 RESOLUTION. 2.0\nEND\n").codigo == "CONTENIDO_ILEGIBLE"

    def test_un_binario_se_rechaza(self):
        assert _error("x.pdb", b"\x00\x01\x02ATOM" * 100).codigo == "CONTENIDO_BINARIO"

    @pytest.mark.parametrize("contenido", [PDB, b"\xef\xbb\xbf" + PDB, PDB.replace(b"\n", b"\r\n"), PDB.replace(b"\n", b"\r")])
    def test_los_pdb_buenos_pasan_con_bom_y_con_cualquier_salto_de_linea(self, contenido):
        archivo = leer_subida("x.pdb", contenido)

        assert archivo.formato == "pdb" and "\r" not in archivo.texto and archivo.texto.startswith("ATOM")
        assert clase_de_contenido(archivo.texto) == "pdb"

    def test_el_contenido_se_conserva_sin_normalizar_y_el_texto_si(self):
        crlf = PDB.replace(b"\n", b"\r\n")

        archivo = leer_subida("x.pdb", crlf)

        assert archivo.contenido == crlf and archivo.texto == PDB.decode()
        assert archivo.sha256_contenido != leer_subida("x.pdb", PDB).sha256_contenido

    def test_un_pdb_en_latin1_se_lee_y_se_avisa(self):
        archivo = leer_subida("x.pdb", b"REMARK  an\xe1lisis\n" + PDB)

        assert archivo.formato == "pdb"
        assert [a["codigo"] for a in archivo.avisos] == ["DECODIFICADO_LATIN1"]
        assert archivo.identidad()["avisos"] == ["DECODIFICADO_LATIN1"]

    def test_un_pdbqt_de_ligando_no_se_confunde_con_pdb(self):
        ligando = (PDBQT.decode() + "ROOT\nENDROOT\nTORSDOF 0\n").encode()

        assert clase_de_contenido(ligando.decode()) == "pdbqt"


# ── Nada de rutas, nada de nombres peligrosos ─────────────────────────────


class TestNombres:
    @pytest.mark.parametrize("entrada,esperado", [
        ("../../etc/passwd", "passwd"), ("C:\\Users\\ana\\8hfi.pdb", "8hfi.pdb"), ("..", "archivo"),
        ("", "archivo"), ("mi receptor (1).pdb", "mi_receptor__1_.pdb"), ("a" * 200 + ".pdb", "a" * 80),
    ])
    def test_el_nombre_seguro_no_lleva_carpetas_ni_puntos_iniciales(self, entrada, esperado):
        assert nombre_seguro(entrada) == esperado

    def test_los_mensajes_no_llevan_la_ruta_del_nombre_subido(self):
        error = _error("C:\\Users\\ana\\secreto\\x.txt", PDB)

        assert "ana" not in error.mensaje("es") + error.mensaje("en")
        assert "x.txt" in error.mensaje("es")

    def test_la_identidad_registra_hashes_y_nunca_el_contenido(self):
        archivo = leer_subida("8HFI.PDB.GZ", _gz(PDB))

        identidad = archivo.identidad()
        assert identidad["archivo"] == "8HFI.PDB.GZ" and identidad["comprimido"] is True
        assert len(identidad["sha256"]) == 64 and identidad["sha256"] != identidad["sha256_contenido"]
        assert not any(isinstance(v, (bytes, bytearray)) for v in identidad.values())


# ── Sólo ADN no es un receptor ────────────────────────────────────────────


class TestSinProteina:
    def test_un_pdb_solo_de_adn_se_detecta(self):
        adn = "\n".join(
            linea_pdb(i, "P", residuo, "A", i, (float(i), 0.0, 0.0), "P")
            for i, residuo in enumerate(("DA", "DC", "DG", "DT"), start=1)
        ) + "\n"

        assert sin_proteina(adn)

    def test_una_proteina_o_un_peptido_pequeno_no(self):
        assert not sin_proteina(pdb_sintetico(residuos=3))
        assert not sin_proteina(pdb_sintetico(residuos=12).replace("ALA", "MSE"))
