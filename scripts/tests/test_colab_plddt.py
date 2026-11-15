"""El análisis del cuaderno de Colab (convención del pLDDT de Boltz y Chai-1) ve lo que tiene que ver.

Sobre el fixture REAL de AlphaFold DB del producto (residuos 1-90 de P23975) se fabrica una «salida del modelo» igual
a su pLDDT dividido entre 100. El análisis tiene que encontrar la escala ×100 y dar la coincidencia; con un solo
valor movido, con el orden barajado o con otra longitud, no. Ninguna de estas pruebas dice nada sobre Boltz ni Chai-1:
sólo que el instrumento que los va a medir distingue un acierto de un fallo.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys

import numpy as np
import pytest

from colab_plddt import analisis_plddt as A
from colab_plddt import construir_cuaderno as C
from colab_plddt import manifiesto_evidencia as M
from colab_plddt import recortar_fixtures as R


@pytest.fixture(scope="module")
def af(raiz_del_repositorio):
    datos = raiz_del_repositorio / "backend" / "tests" / "data" / "receptores_propios"
    return {"cif": datos / "af_p23975_recortado.cif", "pdb": datos / "af_p23975_recortado.pdb"}


def _plddt_local(lectura):
    """El pLDDT de AlphaFold DB del propio archivo, en el orden de los residuos (0–100)."""
    serie = next(v for k, v in A.series_del_archivo(lectura).items() if k.startswith("ma_qa_metric_local["))
    return np.asarray(serie[0], dtype=float)


def _coincidencias(comparaciones, prefijo=""):
    return {c["serie_archivo"] for c in comparaciones if c["coincide"] and c["serie_archivo"].startswith(prefijo)}


PDB_CON_LIGANDO = "\n".join([
    "ATOM      1  N   ALA A   1      0.000   0.000   0.000  1.00 91.20           N",
    "ATOM      2  CA  ALA A   1      1.000   0.000   0.000  1.00 91.20           C",
    "ATOM      3  N   GLY A   2      2.000   0.000   0.000  1.00 45.50           N",
    "ATOM      4  CA  GLY A   2      3.000   0.000   0.000  1.00 45.50           C",
    "HETATM    5  C1  LIG B   1      4.000   0.000   0.000  1.00 80.10           C",
    "HETATM    6  N1  LIG B   1      5.000   0.000   0.000  1.00 70.30           N",
    "HETATM    7  O1  LIG B   1      6.000   0.000   0.000  1.00 60.70           O",
    "END",
]) + "\n"


class TestComparacion:
    def test_la_salida_en_0_1_del_modelo_coincide_con_el_archivo_en_0_100(self, af):
        lectura = A.leer_mmcif(af["cif"])
        modelo = (_plddt_local(lectura) / 100).astype(np.float32)

        comparaciones = A.comparar_estructura(lectura, modelo)

        assert _coincidencias(comparaciones) >= {"b_media_por_residuo_proteina", "b_ca_por_residuo_proteina"}
        assert _coincidencias(comparaciones, "ma_qa_metric_local[")
        assert {c["escala"] for c in comparaciones if c["coincide"]} == {100.0}
        assert lectura["decimales_b"] == 2

    def test_un_solo_residuo_movido_un_punto_no_coincide(self, af):
        lectura = A.leer_mmcif(af["cif"])
        modelo = _plddt_local(lectura) / 100
        modelo[40] += 0.01                      # 1 punto de pLDDT: el doble del redondeo del archivo

        assert not _coincidencias(A.comparar_estructura(lectura, modelo))

    def test_el_orden_barajado_no_coincide(self, af):
        lectura = A.leer_mmcif(af["cif"])
        modelo = np.random.default_rng(0).permutation(_plddt_local(lectura) / 100)

        assert not _coincidencias(A.comparar_estructura(lectura, modelo))

    def test_otra_longitud_no_se_compara(self, af):
        lectura = A.leer_mmcif(af["cif"])

        assert A.comparar_estructura(lectura, _plddt_local(lectura)[:-1] / 100) == []
        assert A.comparar([1.0, 2.0], [1.0], 2) == {"coincide": False, "motivo": "longitud", "n_archivo": 2,
                                                     "n_modelo": 1}

    def test_el_pdb_y_el_mmcif_de_alphafold_db_dan_la_misma_serie(self, af):
        cif, pdb = A.leer_mmcif(af["cif"]), A.leer_pdb(af["pdb"])

        media_cif = A.series_del_archivo(cif)["b_media_por_residuo_proteina"][0]
        media_pdb = A.series_del_archivo(pdb)["b_media_por_residuo_proteina"][0]
        assert media_pdb == pytest.approx(media_cif) and len(media_pdb) == 90
        assert A.dispersion_dentro_del_residuo(pdb)["uno_por_residuo"] is True

    def test_con_ligando_cada_atomo_del_ligando_es_un_token(self, tmp_path):
        ruta = tmp_path / "x_model_0.pdb"
        ruta.write_text(PDB_CON_LIGANDO, encoding="utf-8")
        lectura = A.leer_pdb(ruta)
        modelo = np.array([91.2, 45.5, 80.1, 70.3, 60.7]) / 100

        comparaciones = A.comparar_estructura(lectura, modelo)

        assert "b_por_token" in _coincidencias(comparaciones)
        assert any(c["coincide"] and c["serie_modelo"] == "modelo_primeros_n_residuos"
                   and c["serie_archivo"] == "b_media_por_residuo_proteina" for c in comparaciones)
        assert [r["nombre"] for r in A.resumen_de_la_estructura(lectura)["residuos_no_proteina"]] == ["LIG"]

    def test_un_factor_b_distinto_por_atomo_se_ve(self, tmp_path):
        ruta = tmp_path / "x.pdb"
        ruta.write_text(PDB_CON_LIGANDO.replace("1.00 91.20           C", "1.00 88.00           C"), encoding="utf-8")

        dentro = A.dispersion_dentro_del_residuo(A.leer_pdb(ruta))

        assert dentro["uno_por_residuo"] is False and dentro["residuos_con_dispersion"] == 1


class TestVeredicto:
    @staticmethod
    def _estructura(lectura, modelo):
        return {"comparaciones": A.comparar_estructura(lectura, modelo), "max_modelo": float(np.max(modelo))}

    def test_dos_estructuras_que_coinciden_verifican_la_serie_con_su_escala(self, af):
        lectura = A.leer_mmcif(af["cif"])
        modelo = _plddt_local(lectura) / 100

        v = A.veredicto([self._estructura(lectura, modelo), self._estructura(lectura, modelo)])

        assert "b_media_por_residuo_proteina" in v["series_verificadas"] and v["motivo_si_no"] is None
        assert v["por_serie"]["b_media_por_residuo_proteina"]["escala_en_el_archivo"] == ["0-100"]

    def test_una_sola_estructura_no_basta(self, af):
        lectura = A.leer_mmcif(af["cif"])

        v = A.veredicto([self._estructura(lectura, _plddt_local(lectura) / 100)])

        assert v["series_verificadas"] == [] and "2" in v["motivo_si_no"]

    def test_basta_que_una_falle_para_no_verificar(self, af):
        lectura = A.leer_mmcif(af["cif"])
        bueno = _plddt_local(lectura) / 100
        malo = bueno.copy()
        malo[3] += 0.02

        v = A.veredicto([self._estructura(lectura, bueno), self._estructura(lectura, malo)])

        assert v["series_verificadas"] == []

    @pytest.mark.parametrize("escala, max_modelo, esperado", [
        (100.0, 0.97, "0-100"), (1.0, 0.97, "0-1"), (1.0, 97.0, "0-100"), (0.01, 97.0, "0-1"),
    ])
    def test_la_escala_del_archivo_sale_de_la_del_modelo(self, escala, max_modelo, esperado):
        assert A.escala_del_archivo(escala, max_modelo) == esperado


class TestRecorrido:
    def test_un_arbol_como_el_del_cuaderno_da_un_veredicto_por_grupo(self, af, tmp_path):
        lectura = A.leer_mmcif(af["cif"])
        modelo = (_plddt_local(lectura) / 100).astype(np.float32)
        for caso in ("cdk2_apo", "net_apo"):
            carpeta = tmp_path / "boltz" / f"{caso}__mmcif" / f"boltz_results_{caso}" / "predictions" / caso
            carpeta.mkdir(parents=True)
            shutil.copy(af["cif"], carpeta / f"{caso}_model_0.cif")
            np.savez(carpeta / f"plddt_{caso}_model_0.npz", plddt=modelo)
        chai = tmp_path / "chai" / "cdk2_apo__mmcif"
        chai.mkdir(parents=True)
        shutil.copy(af["cif"], chai / "pred.model_idx_0.cif")
        np.savez(chai / "salida_del_modelo.npz", plddt=modelo[None, :])
        (chai / "resumen_chai.json").write_text(json.dumps({"cif_paths": [str(chai / "pred.model_idx_0.cif")]}),
                                                encoding="utf-8")
        (tmp_path / "chai" / "net_apo__mmcif__fallido_1").mkdir()         # una corrida apartada no cuenta
        (tmp_path / "referencias").mkdir()
        shutil.copy(af["cif"], tmp_path / "referencias" / "AF-P23975-F1-model_v6.cif")

        analisis = A.analizar_resultados(tmp_path)

        assert analisis["grupos"]["boltz/mmcif"]["series_verificadas"]
        assert analisis["grupos"]["chai/mmcif"]["series_verificadas"] == []      # una estructura: no basta
        assert [c["spearman_b_media_vs_afdb"] for c in analisis["control_alphafold_db"]] == [pytest.approx(1.0)]
        json.dumps(analisis)                                                    # el cuaderno lo escribe tal cual
        assert "boltz/mmcif" in A.informe_markdown(analisis)

    def test_las_puntuaciones_de_chai_con_booleanos_se_leen(self, af, tmp_path):
        # Chai-1 0.6.1 guarda en scores.model_idx_N.npz enteros, reales y booleanos (has_inter_chain_clashes). El
        # análisis los redondeaba todos y numpy no redondea un booleano: la celda de análisis se cayó en Colab
        # (2026-11-15) con las tres corridas de Chai-1 terminadas.
        lectura = A.leer_mmcif(af["cif"])
        chai = tmp_path / "chai" / "cdk2_apo__mmcif"
        chai.mkdir(parents=True)
        shutil.copy(af["cif"], chai / "pred.model_idx_0.cif")
        np.savez(chai / "salida_del_modelo.npz", plddt=(_plddt_local(lectura) / 100)[None, :])
        np.savez(chai / "scores.model_idx_0.npz", aggregate_score=np.array([0.1921]), ptm=np.array([0.96]),
                 has_inter_chain_clashes=np.array([False]), chain_chain_clashes=np.zeros((1, 1), dtype=np.int64))
        (chai / "resumen_chai.json").write_text(json.dumps({"cif_paths": [str(chai / "pred.model_idx_0.cif")]}),
                                                encoding="utf-8")

        analisis = A.analizar_resultados(tmp_path)

        puntuaciones = analisis["estructuras"][0]["confianza_declarada_por_el_modelo"]
        assert puntuaciones["has_inter_chain_clashes"] == [False] and puntuaciones["aggregate_score"] == [0.1921]
        assert puntuaciones["chain_chain_clashes"] == [[0]]
        json.dumps(analisis)


class TestCuaderno:
    def test_el_cuaderno_versionado_es_el_que_sale_de_sus_fuentes(self):
        r = subprocess.run([sys.executable, str(C.AQUI / "construir_cuaderno.py"), "--check"],
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr

    def test_cada_celda_de_codigo_compila(self):
        cuaderno = json.loads(C.CUADERNO.read_text(encoding="utf-8"))
        codigo = [c for c in cuaderno["cells"] if c["cell_type"] == "code"]
        assert len(codigo) == sum(1 for tipo, _ in C.CELDAS if tipo != "markdown")
        for i, celda in enumerate(codigo):
            fuente = "".join(l for l in celda["source"] if not l.startswith("%%"))
            compile(fuente, f"celda_{i}", "exec")

    def test_los_modulos_que_escribe_son_los_del_repositorio(self):
        cuaderno = json.loads(C.CUADERNO.read_text(encoding="utf-8"))
        escritas = {c["source"][0].split("/")[-1].strip(): "".join(c["source"][1:])
                    for c in cuaderno["cells"] if c["source"] and c["source"][0].startswith("%%writefile")}
        for nombre in ("analisis_plddt.py", "ejecutar_chai.py"):
            assert escritas[nombre] == (C.AQUI / nombre).read_text(encoding="utf-8").rstrip("\n")


class TestManifiestoDeEvidencia:
    """El manifiesto es lo que se cita en lugar del archivo: tiene que ver un byte cambiado, un archivo de menos y uno de más."""

    @staticmethod
    def _arbol(raiz):
        (raiz / "chai" / "c").mkdir(parents=True)
        (raiz / "procedencia.json").write_text('{"a": 1}', encoding="utf-8")
        (raiz / "chai" / "c" / "pred.model_idx_0.cif").write_bytes(b"data_model\n")
        return raiz

    def test_un_arbol_intacto_coincide(self, tmp_path):
        raiz = self._arbol(tmp_path / "r")
        manifiesto = M.construir(raiz, archivado_en="F:/archivo", origen="prueba")

        assert manifiesto["archivos_totales"] == 2 and manifiesto["bytes_totales"] == 8 + 11
        assert M.verificar(raiz, manifiesto) == {"coincide": True, "faltan": [], "sobran": [], "distintos": [],
                                                  "comprobados": 2}

    def test_ve_un_byte_cambiado_un_archivo_de_menos_y_uno_de_mas(self, tmp_path):
        raiz = self._arbol(tmp_path / "r")
        manifiesto = M.construir(raiz)
        (raiz / "chai" / "c" / "pred.model_idx_0.cif").write_bytes(b"data_modeL\n")      # mismo tamaño, otro byte
        (raiz / "procedencia.json").unlink()
        (raiz / "extra.log").write_text("x", encoding="utf-8")

        resultado = M.verificar(raiz, manifiesto)

        assert resultado["coincide"] is False
        assert resultado["distintos"] == ["chai/c/pred.model_idx_0.cif"]
        assert resultado["faltan"] == ["procedencia.json"] and resultado["sobran"] == ["extra.log"]


class TestRecortarFixtures:
    """El recorte de los fixtures: residuos 1-90 de la cadena A, y todo lo demás tal cual."""

    def test_el_pdb_conserva_el_ligando_y_sus_conect_y_quita_lo_demas(self):
        def atomo(serie, registro, nombre, residuo, cadena, numero):
            return f"{registro:<6}{serie:>5} {nombre:<4} {residuo:>3} {cadena}{numero:>4}    " + " " * 26 + "80.00"

        pdb = "\n".join([
            atomo(1, "ATOM", "CA", "MET", "A", 1), atomo(2, "ATOM", "CA", "GLY", "A", 91),
            atomo(3, "HETATM", "C1", "LIG", "B", 1), atomo(4, "HETATM", "C2", "LIG", "B", 1),
            "CONECT    3    4", "CONECT    2    3", "END", "",
        ])

        recortado = R.recortar_pdb(pdb)

        assert " GLY A  91" not in recortado and " MET A   1" in recortado        # control: el 91 se va
        assert recortado.count("HETATM") == 2 and "CONECT    3    4" in recortado
        assert "CONECT    2    3" not in recortado and recortado.endswith("END\n")

    def test_el_mmcif_recorta_sus_dos_tablas_y_aborta_ante_una_fila_rara(self):
        cif = "\n".join([
            "data_x", "_struct.title 'Chai-1 predicted structure'", "#",
            "loop_", "_atom_site.label_asym_id", "_atom_site.label_seq_id", "_atom_site.B_iso_or_equiv",
            "A 90 70.1", "A 91 80.2", "B . 50.0", "#",
            "loop_", "_entity_poly_seq.num", "_entity_poly_seq.mon_id", "91 GLY", "#", "",
        ])

        recortado = R.recortar_mmcif(cif)

        assert "A 90 70.1" in recortado and "A 91 80.2" not in recortado and "B . 50.0" in recortado
        assert "91 GLY" in recortado and "'Chai-1 predicted structure'" in recortado   # el resto, tal cual
        with pytest.raises(ValueError):
            R.recortar_mmcif(cif.replace("A 91 80.2", "A 91"))
