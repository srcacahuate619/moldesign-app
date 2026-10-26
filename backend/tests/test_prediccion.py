"""Estructuras predichas: detección, convención verificada del pLDDT y confianza del sitio.

Los fixtures son recortes (residuos 1-90) de los archivos REALES de AlphaFold DB para P23975 (NET humano), versión 6,
descargados del EBI el 2026-10-09: ``af_p23975_recortado.pdb`` y ``.cif`` conservan la cabecera y las métricas
``_ma_qa_metric_local`` tal cual (hashes en ``alphafold_procedencia.json``).

Lo que se verificó en esos archivos, y sólo eso: el factor B del PDB y ``B_iso_or_equiv`` del mmCIF son el pLDDT por
residuo, escala 0–100, y coinciden con ``_ma_qa_metric_local``. De Boltz, Chai-1 y AlphaFold 3 no hay un archivo
real de salida en sus repositorios oficiales: su convención NO está verificada y estas pruebas comprueban que no se
afirma (``no_disponible``), no que se lea.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path

import pytest
import pytest_asyncio

from services.dossier.localization import traducir_dossier
from services.dossier.preparacion_confianza import campo_de_confianza
from services.dossier.taxonomy import Estado
from services.targets import prediccion as P
from services.targets.conversion_mmcif import mmcif_a_pdb
from services.targets.normalizar_pdb import normalizar_pdb
from tests.receptores_propios_ayudas import aislar_almacen, linea_pdbqt
from tests.test_target_authorization import _Environment

DATOS = Path(__file__).parent / "data" / "receptores_propios"
PDB_AF = (DATOS / "af_p23975_recortado.pdb").read_text(encoding="utf-8")
CIF_AF = (DATOS / "af_p23975_recortado.cif").read_text(encoding="utf-8")
CA_BAJO = (-51.005, -23.775, 29.204)     # Cα del residuo 1: pLDDT 33,75 (el extremo N de AlphaFold DB)
CA_ALTO = (3.777, -13.874, 10.071)       # Cα del residuo 64: pLDDT 95,38


def _analizar_pdb(texto: str = PDB_AF):
    return P.analizar("pdb", texto, normalizar_pdb(texto)[0])


def _analizar_cif(texto: str = CIF_AF):
    conversion = mmcif_a_pdb(texto, "af.cif")
    return P.analizar("mmcif", texto, conversion.pdb, {c["original"]: c["pdb"] for c in conversion.informe["cadenas"]})


class TestConvencionVerificada:
    def test_alphafold_db_pdb_real_el_factor_b_es_el_plddt(self):
        info, mapa = _analizar_pdb()

        assert info["es_predicha"] and info["fuente"] == "alphafold_db" and info["no_disponible"] is None
        assert info["convencion"]["verificada"] is True
        assert (info["convencion"]["plddt_en"], info["convencion"]["escala"]) == ("factor_b", "0-100")
        assert info["plddt"]["residuos"] == 90 == len(mapa)
        assert mapa["A:1"] == 33.75 and mapa["A:64"] == 95.38      # los valores del archivo real, residuo a residuo

    def test_alphafold_db_mmcif_real_da_el_mismo_mapa_que_su_pdb(self):
        info_cif, mapa_cif = _analizar_cif()
        _, mapa_pdb = _analizar_pdb()

        assert info_cif["fuente"] == "alphafold_db" and info_cif["convencion"]["plddt_en"] == "ma_qa_metric_local"
        assert info_cif["convencion"]["verificada"] is True
        assert mapa_cif == mapa_pdb                               # paridad PDB ↔ mmCIF, residuo a residuo

    def test_el_resumen_global_coincide_con_los_valores(self):
        info, mapa = _analizar_pdb()

        valores = list(mapa.values())
        assert info["plddt"]["minimo"] == min(valores) and info["plddt"]["maximo"] == max(valores)
        assert info["plddt"]["bajo_70"] == sum(v < 70 for v in valores) > 0
        assert info["plddt"]["bajo_50"] == sum(v < 50 for v in valores)

    @pytest.mark.parametrize("nombre, formato", [("8hfi_recortado.cif", "mmcif"), ("8hfi_recortado.pdb", "pdb")])
    def test_una_estructura_experimental_no_es_predicha_y_no_se_lee_confianza(self, nombre, formato):
        texto = (DATOS / nombre).read_text(encoding="utf-8")
        if formato == "mmcif":
            conversion = mmcif_a_pdb(texto, nombre)
            info, mapa = P.analizar("mmcif", texto, conversion.pdb)
        else:
            info, mapa = P.analizar("pdb", texto, texto)

        assert info["es_predicha"] is False and info["plddt"] is None and mapa is None
        assert info["no_disponible"] is None and info["fuente"] is None
        if formato == "mmcif":
            assert info["metodo_declarado"] == "ELECTRON MICROSCOPY"       # 8HFI es una estructura de crio-EM


class TestLoQueNoSeAfirma:
    """Controles: cada uno debe terminar en «no disponible» con su código, nunca en una cifra."""

    def test_el_factor_b_distinto_del_plddt_declarado_no_se_usa(self):
        # Se cambian los pLDDT locales y no el factor B: el archivo se contradice.
        roto = re.sub(r"^(A [A-Z]{3} \d+\s+2 )(\d+\.\d+)", lambda m: m.group(1) + "11.11", CIF_AF, flags=re.M)
        assert roto != CIF_AF

        info, mapa = _analizar_cif(roto)

        assert info["fuente"] == "alphafold_db" and info["no_disponible"] == P.B_NO_COINCIDE
        assert info["plddt"] is None and mapa is None

    def test_un_modelcif_sin_plddt_local_no_se_lee(self):
        sin_local = CIF_AF.replace("_ma_qa_metric_local.", "_ma_qa_metric_localx.")

        info, mapa = _analizar_cif(sin_local)

        assert info["es_predicha"] and info["fuente"] == "desconocida"
        assert info["no_disponible"] == P.SIN_PLDDT_DECLARADO and mapa is None

    def test_un_modelcif_de_otra_fuente_se_lee_pero_su_convencion_queda_sin_verificar(self):
        otra = CIF_AF.replace("_entry.id AF-P23975-F1", "_entry.id OTRA-FUENTE-1")
        assert otra != CIF_AF

        info, mapa = _analizar_cif(otra)

        assert info["fuente"] == "modelcif" and info["convencion"]["verificada"] is False
        assert info["no_disponible"] is None and mapa["A:64"] == 95.38

    def test_valores_de_plddt_en_0_1_son_ambiguos_y_no_se_interpretan(self):
        otra = CIF_AF.replace("_entry.id AF-P23975-F1", "_entry.id OTRA-FUENTE-1")
        en_unidad = re.sub(r"^(A [A-Z]{3} \d+\s+2 )(\d+\.\d+)",
                           lambda m: m.group(1) + f"{float(m.group(2)) / 100:.4f}", otra, flags=re.M)

        info, mapa = _analizar_cif(en_unidad)

        assert info["no_disponible"] == P.ESCALA_AMBIGUA and mapa is None

    def test_un_pdb_teorico_que_no_es_alphafold_db_no_afirma_ninguna_convencion(self):
        # La misma estructura sin la cabecera de AlphaFold DB y con el método de un modelo: Boltz, Chai y AF3 caen aquí.
        otro = PDB_AF.replace("ALPHAFOLD MONOMER V2.0 PREDICTION FOR", "UN MODELO DE").replace(
            "TITLE", "EXPDTA    THEORETICAL MODEL\nTITLE", 1)

        info, mapa = _analizar_pdb(otro)

        assert info["es_predicha"] and info["fuente"] == "desconocida"
        assert info["no_disponible"] == P.CONVENCION_SIN_VERIFICAR and mapa is None

    def test_un_pqr_y_un_pdbqt_sin_origen_no_dicen_si_son_predicciones(self):
        info_pqr, mapa = P.analizar("pqr", PDB_AF, PDB_AF)
        info_pdbqt = P.sin_estructura_de_origen()

        assert info_pqr["es_predicha"] is None and info_pqr["no_disponible"] == P.FORMATO_SIN_FACTOR_B and mapa is None
        assert info_pdbqt["es_predicha"] is None and info_pdbqt["no_disponible"] == P.PDBQT_SIN_ORIGEN


class TestSitio:
    def test_el_margen_y_la_distancia_son_los_de_la_preparacion(self):
        from services.docking import preparer

        assert P.MARGEN_SITIO_A == preparer.MARGEN_SITIO_A
        for punto in [(0.0, 0.0, 0.0), (14.0, -3.0, 5.5), (-30.0, 22.0, 9.0)]:
            assert P._distancia_a_caja(punto, (1.0, 2.0, 3.0), (10.0, 12.0, 14.0)) == pytest.approx(
                preparer._distancia_a_caja(punto, (1.0, 2.0, 3.0), (10.0, 12.0, 14.0)))

    def test_un_sitio_de_alta_confianza_no_pide_revision(self):
        _, mapa = _analizar_pdb()

        sitio = P.confianza_del_sitio(mapa, PDB_AF, CA_ALTO, (10.0, 10.0, 10.0))

        assert sitio["con_plddt"] > 5 and sitio["n_bajo_70"] == 0 and sitio["minimo"] >= 70
        assert sitio["sin_plddt"] == 0 and sitio["bajo_70"] == []

    def test_un_sitio_en_el_extremo_n_lista_los_residuos_por_debajo_de_70(self):
        _, mapa = _analizar_pdb()

        sitio = P.confianza_del_sitio(mapa, PDB_AF, CA_BAJO, (10.0, 10.0, 10.0))

        assert sitio["n_bajo_70"] >= 3 and sitio["minimo"] < 50
        assert all(r["plddt"] < 70 for r in sitio["bajo_70"])
        assert [r["plddt"] for r in sitio["bajo_70"]] == sorted(r["plddt"] for r in sitio["bajo_70"])
        assert {r["residuo"] for r in sitio["bajo_70"]} <= {f"A:{n}" for n in range(1, 91)}

    def test_los_residuos_sin_plddt_se_cuentan_en_vez_de_ignorarse(self):
        _, mapa = _analizar_pdb()
        parcial = {k: v for k, v in mapa.items() if k != "A:64"}

        sitio = P.confianza_del_sitio(parcial, PDB_AF, CA_ALTO, (10.0, 10.0, 10.0))

        assert sitio["sin_plddt"] == 1 and sitio["con_plddt"] == sitio["residuos"] - 1

    def test_acepta_un_pdbqt_porque_lee_las_mismas_columnas(self):
        _, mapa = _analizar_pdb()
        pdbqt = linea_pdbqt(1, "CA", "LEU", "A", 64, (3.777, -13.874, 10.071), "C") + "\n"

        sitio = P.confianza_del_sitio(mapa, pdbqt, CA_ALTO, (10.0, 10.0, 10.0))

        assert sitio["residuos"] == 1 and sitio["minimo"] == 95.38

    def test_una_caja_lejos_de_la_proteina_no_inventa_residuos(self):
        _, mapa = _analizar_pdb()

        sitio = P.confianza_del_sitio(mapa, PDB_AF, (500.0, 500.0, 500.0), (10.0, 10.0, 10.0))

        assert sitio["residuos"] == 0 and sitio["minimo"] is None and sitio["media"] is None


def _prediccion_con_sitio(bajos: int, *, residuos: int = 40) -> dict:
    info, mapa = _analizar_pdb()
    sitio = {"margen_A": 6.0, "residuos": residuos, "con_plddt": residuos, "sin_plddt": 0,
             "minimo": 41.2 if bajos else 82.5, "media": 90.1, "n_bajo_70": bajos, "n_bajo_50": 1 if bajos else 0,
             "bajo_70": [{"residuo": f"A:{i}", "nombre": "LEU", "plddt": 41.2 + i, "distancia_A": 1.5}
                         for i in range(min(bajos, 12))]}
    return {**copy.deepcopy(info), "sitio": sitio}


class TestPreparacion:
    def test_un_sitio_fiable_queda_registrado(self):
        campo, accion = campo_de_confianza(_prediccion_con_sitio(0))

        assert campo.estado == Estado.REGISTRADO and accion is None
        assert "estructura predicha por AlphaFold DB" in campo.valor and "convención verificada" in campo.valor

    def test_un_sitio_con_residuos_bajos_pide_revision_los_lista_y_no_bloquea(self):
        from services.dossier.preparacion import Requisito

        campo, accion = campo_de_confianza(_prediccion_con_sitio(15))
        requisito = Requisito("receptor.confianza_estructural", campo, "receptor_prep.prediccion", False,
                              accion_recomendada=accion)

        assert campo.estado == Estado.REVISAR and requisito.pide_revision and not requisito.bloquea
        assert campo.valor_es_clasificacion and "15 por debajo de 70" not in campo.valor.replace("12 por debajo", "")
        assert "12 por debajo de 70: A:0 LEU" in campo.valor and "otros 3 por debajo de 70 sin listar" in campo.valor
        assert accion and "no bloquea" in campo.razon.lower()

    def test_cada_codigo_de_no_disponible_se_explica_y_ninguno_trae_cifras(self):
        for codigo in (P.SIN_PLDDT_DECLARADO, P.CONVENCION_SIN_VERIFICAR, P.ESCALA_AMBIGUA, P.B_NO_COINCIDE,
                       P.FORMATO_SIN_FACTOR_B, P.PDBQT_SIN_ORIGEN):
            campo, _ = campo_de_confianza({"es_predicha": True, "no_disponible": codigo})

            assert campo.estado == Estado.NO_DISPONIBLE and campo.razon and campo.razon != codigo
            assert campo.as_dict()["valor"] is None

    def test_lo_experimental_es_no_aplica_y_lleva_su_metodo(self):
        campo, _ = campo_de_confianza({"es_predicha": False, "metodo_declarado": "X-RAY DIFFRACTION"})

        assert campo.estado == Estado.NO_APLICA and "X-RAY DIFFRACTION" in campo.razon

    def test_sin_haber_medido_el_sitio_no_se_da_por_bueno(self):
        info, _ = _analizar_pdb()

        campo, _ = campo_de_confianza(info)               # sin «sitio»

        assert campo.estado == Estado.NO_EVALUADO

    def test_todas_las_frases_pasan_al_ingles_sin_dejar_castellano(self):
        from tests.test_dossier_en_ingles_completo import _parece_espanol

        for prediccion in (_prediccion_con_sitio(0), _prediccion_con_sitio(15),
                           {"es_predicha": False, "metodo_declarado": None},
                           {"es_predicha": False, "metodo_declarado": "X-RAY DIFFRACTION"},
                           *({"es_predicha": True, "no_disponible": c} for c in (
                               P.SIN_PLDDT_DECLARADO, P.CONVENCION_SIN_VERIFICAR, P.ESCALA_AMBIGUA, P.B_NO_COINCIDE,
                               P.FORMATO_SIN_FACTOR_B, P.PDBQT_SIN_ORIGEN))):
            campo, accion = campo_de_confianza(prediccion)
            auditoria = {"bloques": [{"id": "receptor", "requisitos": [
                {**campo.as_dict(), "clave": "receptor.confianza_estructural",
                 **({"accion_recomendada": accion} if accion else {})}]}]}

            en = traducir_dossier(auditoria, "en")["bloques"][0]["requisitos"][0]

            textos = [en["etiqueta"], en["valor"], en["razon"], en.get("accion_recomendada")]
            for t in filter(None, textos):
                assert not _parece_espanol(t), (prediccion, t)


@pytest_asyncio.fixture
async def entorno(tmp_path, monkeypatch):
    aislar_almacen(monkeypatch, tmp_path / "almacen")
    env = _Environment(tmp_path / "targets.db")
    await env.start()
    try:
        yield env
    finally:
        await env.close()


def _subir(cliente, nombre: str, contenido: str, centro, *, modo: str = "automatico", cadena: str = "A", tamano="20"):
    return cliente.post("/targets/upload", data={
        "name": "predicha", "is_curated": "false", "chain_id": cadena, "modo_preparacion": modo,
        "grid_center_x": str(centro[0]), "grid_center_y": str(centro[1]), "grid_center_z": str(centro[2]),
        "grid_size_x": tamano, "grid_size_y": tamano, "grid_size_z": tamano},
        files={"file": (nombre, contenido.encode())})


def _auditoria_de(respuesta):
    from tests.fixtures_dossier import caso_completo
    from tests.test_preparacion_auditoria import _PROCEDENCIA, _auditar
    from utils.local_storage import path_for

    destino = respuesta.json()["target"]
    informe = json.loads(path_for(destino["prepared_file_path"][:-6] + ".report.json").read_text(encoding="utf-8"))
    caso = caso_completo()
    procedencia = copy.deepcopy(_PROCEDENCIA)
    procedencia["receptor_prep"] = {**informe, "chain": "A", "site_chains": ["A"]}
    caso["eval_result"].docking_protocol = {**caso["eval_result"].docking_protocol, "execution_provenance": procedencia}
    return informe, _auditar(caso)


def _requisito(auditoria: dict, clave: str) -> dict:
    return next(r for b in auditoria["bloques"] for r in b["requisitos"] if r["clave"] == clave)


@pytest.mark.asyncio
@pytest.mark.parametrize("nombre, contenido", [("AF-P23975-F1-model_v6.pdb", PDB_AF), ("AF-P23975-F1-model_v6.CIF", CIF_AF)],
                         ids=["pdb", "mmcif"])      # sin ids, el contenido entero del archivo sería el nombre de la prueba
async def test_alphafold_db_con_el_sitio_fiable_queda_registrado_en_pdb_y_en_mmcif(entorno, nombre, contenido):
    cliente = entorno.client(await entorno.user("ana"))

    respuesta = _subir(cliente, nombre, contenido, CA_ALTO)

    assert respuesta.status_code == 201, respuesta.text
    informe, auditoria = _auditoria_de(respuesta)
    sitio = informe["prediccion"]["sitio"]
    assert informe["prediccion"]["fuente"] == "alphafold_db" and sitio["n_bajo_70"] == 0 and sitio["con_plddt"] > 5
    requisito = _requisito(auditoria, "receptor.confianza_estructural")
    assert requisito["estado"] == "REGISTRADO" and "estructura predicha por AlphaFold DB" in requisito["valor"]
    assert "receptor.confianza_estructural" not in auditoria["bloqueantes"]


@pytest.mark.asyncio
async def test_alphafold_db_con_el_sitio_en_el_extremo_n_pide_revision_y_no_bloquea(entorno):
    cliente = entorno.client(await entorno.user("ana"))

    respuesta = _subir(cliente, "AF-P23975-F1-model_v6.pdb", PDB_AF, CA_BAJO)

    assert respuesta.status_code == 201, respuesta.text
    informe, auditoria = _auditoria_de(respuesta)
    assert informe["prediccion"]["sitio"]["n_bajo_70"] >= 3
    requisito = _requisito(auditoria, "receptor.confianza_estructural")
    assert requisito["estado"] == "REVISAR" and requisito["accion_recomendada"]
    assert "receptor.confianza_estructural" in auditoria["en_revision"]
    assert "receptor.confianza_estructural" not in auditoria["bloqueantes"]


@pytest.mark.asyncio
async def test_una_estructura_experimental_del_usuario_es_no_aplica(entorno):
    cliente = entorno.client(await entorno.user("ana"))
    texto = (DATOS / "8hfi_recortado.cif").read_text(encoding="utf-8")

    respuesta = _subir(cliente, "8hfi.cif", texto, (100.281, 100.843, 101.442), tamano="25")

    assert respuesta.status_code == 201, respuesta.text
    informe, auditoria = _auditoria_de(respuesta)
    assert informe["prediccion"]["es_predicha"] is False
    requisito = _requisito(auditoria, "receptor.confianza_estructural")
    assert requisito["estado"] == "NO_APLICA" and "ELECTRON MICROSCOPY" in requisito["razon"]


@pytest.mark.asyncio
async def test_el_catalogo_no_lleva_el_requisito_porque_su_informe_no_cambia():
    from services.dossier.preparacion import _requisito_de_confianza

    assert _requisito_de_confianza({"chain": "A", "recipe_hash": "x"}) == []
    assert _requisito_de_confianza(None) == []


def test_la_busqueda_en_alphafold_db_y_la_subida_leen_el_mismo_plddt(tmp_path):
    """Los dos caminos usan la misma convención (factor B = pLDDT): el cliente de la búsqueda lee el Cα de cada residuo."""
    from services.alphafold.client import _parse_plddt_from_pdb

    archivo = tmp_path / "af.pdb"
    archivo.write_text(PDB_AF, encoding="utf-8")

    por_el_cliente = _parse_plddt_from_pdb(str(archivo))
    _, mapa = _analizar_pdb()

    assert por_el_cliente == [mapa[f"A:{n}"] for n in range(1, 91)]


def test_el_operador_del_ensamblaje_va_en_singular_cuando_es_uno():
    from core.i18n_plantillas import traducir
    from services.dossier.preparacion_entrada import partes_de_conversion

    uno = partes_de_conversion({"ensamblaje": {"estado": "aplicado", "usado": "1", "operadores_aplicados": 1}})
    dos = partes_de_conversion({"ensamblaje": {"estado": "aplicado", "usado": "1", "operadores_aplicados": 2}})

    assert "ensamblaje 1 aplicado (1 operador)" in uno and "ensamblaje 1 aplicado (2 operadores)" in dos
    assert traducir("ensamblaje 1 aplicado (1 operador)", "en") == "assembly 1 applied (1 operator)"
    assert traducir("ensamblaje 1 aplicado (2 operadores)", "en") == "assembly 1 applied (2 operators)"


@pytest.mark.asyncio
async def test_un_pdbqt_con_su_origen_alphafold_hereda_la_confianza_del_sitio_y_sin_origen_no_la_inventa(entorno):
    """El PDBQT lo prepara la propia subida (modo automático) a partir del modelo; después se sube como camino C."""
    from utils.local_storage import path_for

    cliente = entorno.client(await entorno.user("ana"))
    primera = _subir(cliente, "AF-P23975-F1-model_v6.pdb", PDB_AF, CA_BAJO)
    assert primera.status_code == 201, primera.text
    pdbqt = path_for(primera.json()["target"]["prepared_file_path"]).read_bytes()
    campos = {"name": "pdbqt de AlphaFold", "is_curated": "true", "modo_preparacion": "pdbqt", "chain_id": "A",
              "grid_center_x": str(CA_BAJO[0]), "grid_center_y": str(CA_BAJO[1]), "grid_center_z": str(CA_BAJO[2]),
              "grid_size_x": "20", "grid_size_y": "20", "grid_size_z": "20"}

    con_origen = cliente.post("/targets/upload", data=campos, files={
        "file": ("receptor.pdbqt", pdbqt), "source_file": ("AF-P23975-F1-model_v6.pdb", PDB_AF.encode())})
    sin_origen = cliente.post("/targets/upload", data=campos, files={"file": ("receptor.pdbqt", pdbqt)})

    assert con_origen.status_code == 201, con_origen.text
    informe_con, auditoria_con = _auditoria_de(con_origen)
    assert informe_con["prediccion"]["fuente"] == "alphafold_db" and informe_con["prediccion"]["sitio"]["n_bajo_70"] >= 3
    assert _requisito(auditoria_con, "receptor.confianza_estructural")["estado"] == "REVISAR"

    assert sin_origen.status_code == 201, sin_origen.text
    informe_sin, auditoria_sin = _auditoria_de(sin_origen)
    assert informe_sin["prediccion"]["es_predicha"] is None and "sitio" not in informe_sin["prediccion"]
    requisito = _requisito(auditoria_sin, "receptor.confianza_estructural")
    assert requisito["estado"] == "NO_DISPONIBLE" and requisito["valor"] is None
