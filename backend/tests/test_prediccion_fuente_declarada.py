"""Boltz-2 y Chai-1 con sus archivos reales, y la fuente que declara quien sube un archivo que no dice de dónde viene.

Los fixtures son recortes (residuos 1-90 de la cadena A) de las salidas reales de Boltz 2.2.1 y chai_lab 0.6.1 que
generó el cuaderno de Colab el 2026-11-15. Sus hashes y los de sus originales están en ``boltz_chai_procedencia.json``,
y los originales, en el manifiesto del acta ``docs/auditorias/convencion-plddt-boltz-chai-2026-11-15/``. Los produce
``scripts/colab_plddt/recortar_fixtures.py``.

Lo que fijan:

* el PDB de Boltz no trae ninguna cabecera. Sin declaración no consta si es una predicción; declarado «Boltz-2», su
  factor B se lee como pLDDT, y sólo si el archivo es como los que escribe Boltz 2.2.1;
* el mmCIF de Boltz se lee como ModelCIF sin verificar, y ``_ma_qa_metric_local`` es su factor B (el pLDDT del modelo);
* con el mmCIF de Chai-1, el producto lee el pLDDT del Cα (``_ma_qa_metric_local``), no la media del residuo que da el
  modelo. Es la decisión abierta del acta: estas pruebas describen lo que hace hoy, no lo que debería hacer.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path

import pytest

from services.dossier.localization import traducir_dossier
from services.dossier.preparacion_confianza import NO_APLICA_DECLARADA, campo_de_confianza
from services.dossier.taxonomy import Estado
from services.targets import prediccion as P
from services.targets.conversion_mmcif import mmcif_a_pdb
from services.targets.normalizar_pdb import normalizar_pdb
from tests.test_prediccion import CIF_AF, PDB_AF, _auditoria_de, _requisito, entorno  # noqa: F401  (entorno es un fixture)

DATOS = Path(__file__).parent / "data" / "receptores_propios"
PROCEDENCIA = json.loads((DATOS / "boltz_chai_procedencia.json").read_text(encoding="utf-8"))
PDB_BOLTZ = (DATOS / "boltz_cdk2_lig_recortado.pdb").read_text(encoding="utf-8")
CIF_BOLTZ = (DATOS / "boltz_cdk2_apo_recortado.cif").read_text(encoding="utf-8")
CIF_CHAI = (DATOS / "chai_cdk2_apo_recortado.cif").read_text(encoding="utf-8")
PDB_8HFI = (DATOS / "8hfi_recortado.pdb").read_text(encoding="utf-8")
CIF_8HFI = (DATOS / "8hfi_recortado.cif").read_text(encoding="utf-8")
CA_39 = (0.298, -22.785, -0.518)      # Cα de THR 39: pLDDT 61,24, el mínimo de CDK2 en Boltz (bucle 37-41)
CA_83 = (8.532, -0.376, -12.851)      # Cα de LEU 83, la bisagra del sitio del ATP: pLDDT 98,88


def _pdb(texto: str = PDB_BOLTZ, **declaracion):
    return P.analizar("pdb", texto, normalizar_pdb(texto)[0], **declaracion)


def _cif(texto: str, nombre: str = "x.cif", **declaracion):
    conversion = mmcif_a_pdb(texto, nombre)
    return P.analizar("mmcif", texto, conversion.pdb, {c["original"]: c["pdb"] for c in conversion.informe["cadenas"]},
                      **declaracion)


def _factor_b(texto_pdb: str) -> tuple[dict[str, list[float]], dict[str, float]]:
    """El factor B de cada átomo por residuo, y el del Cα."""
    por_atomo: dict[str, list[float]] = defaultdict(list)
    ca: dict[str, float] = {}
    for linea in texto_pdb.splitlines():
        if linea.startswith("ATOM"):
            clave = f"{linea[21]}:{int(linea[22:26])}"
            por_atomo[clave].append(float(linea[60:66]))
            if linea[12:16].strip() == "CA":
                ca[clave] = float(linea[60:66])
    return por_atomo, ca


def _factor_b_cif(texto: str) -> tuple[dict[str, list[float]], dict[str, float]]:
    """Lo mismo, leído del mmCIF con sus 3 decimales (el PDB convertido sólo tiene 2)."""
    import gemmi

    estructura = gemmi.make_structure_from_block(gemmi.cif.read_string(texto)[0])
    proteina = [(f"{c.name}:{r.seqid.num}", r) for c in estructura[0] for r in c if r.het_flag == "A"]
    return ({k: [a.b_iso for a in r] for k, r in proteina},
            {k: r.find_atom("CA", "*").b_iso for k, r in proteina})


def test_los_recortes_son_los_que_declara_su_procedencia():
    for nombre, sha in PROCEDENCIA["recortes"].items():
        assert hashlib.sha256((DATOS / nombre).read_bytes()).hexdigest() == sha, nombre
    assert len(PROCEDENCIA["originales"]) == 3
    manifiesto = json.loads((Path(__file__).resolve().parents[2] / "docs" / "auditorias"
                             / "convencion-plddt-boltz-chai-2026-11-15" / "manifiesto.json").read_text(encoding="utf-8"))
    for ruta, sha in PROCEDENCIA["originales"].items():
        assert manifiesto["archivos"][ruta]["sha256"] == sha, ruta


class TestElPdbDeBoltz:
    def test_no_trae_cabecera_y_por_eso_hay_que_preguntar(self):
        assert PDB_BOLTZ.startswith("ATOM")
        assert P.hay_que_preguntar_la_fuente("pdb", PDB_BOLTZ)

    def test_sin_declaracion_no_consta_si_es_una_prediccion(self):
        info, mapa = _pdb()

        assert info["es_predicha"] is None and info["no_disponible"] == P.FUENTE_SIN_DECLARAR and mapa is None
        assert "declaracion" not in info

    def test_declarado_boltz_su_factor_b_se_lee_con_la_convencion_comprobada(self):
        info, mapa = _pdb(fuente_declarada="boltz")

        assert info["es_predicha"] and info["fuente"] == P.FUENTE_BOLTZ and info["no_disponible"] is None
        assert info["convencion"]["verificada"] is True and info["convencion"]["fuente_declarada"] is True
        assert info["convencion"]["plddt_en"] == "factor_b" and "Boltz 2.2.1" in info["convencion"]["referencia"]
        assert info["declaracion"] == {"fuente": "boltz", "herramienta": None, "usada": True}
        assert len(mapa) == 90 and mapa["A:39"] == 61.24 and mapa["A:83"] == 98.88   # los valores del archivo real
        assert info["plddt"]["bajo_70"] == 5                                         # 37-41, como en el modelo

    def test_el_mapa_es_el_factor_b_de_cada_residuo(self):
        _, mapa = _pdb(fuente_declarada="boltz")
        por_atomo, _ = _factor_b(normalizar_pdb(PDB_BOLTZ)[0])

        assert all(max(v) - min(v) <= 0.01 for v in por_atomo.values())              # uno por residuo
        assert mapa == {k: v[0] for k, v in por_atomo.items()}

    def test_declarado_experimental_no_aplica_y_lo_dice(self):
        info, mapa = _pdb(fuente_declarada="experimental")
        campo, _ = campo_de_confianza(info)

        assert info["es_predicha"] is False and mapa is None
        assert campo.estado == Estado.NO_APLICA and campo.razon == NO_APLICA_DECLARADA

    def test_otra_herramienta_se_registra_con_su_nombre_y_no_se_lee(self):
        info, mapa = _pdb(fuente_declarada="otra", herramienta_declarada="ColabFold 1.5")
        campo, _ = campo_de_confianza(info)

        assert info["es_predicha"] and info["no_disponible"] == P.HERRAMIENTA_SIN_VERIFICAR and mapa is None
        assert campo.estado == Estado.NO_DISPONIBLE and "predicción de ColabFold 1.5" in campo.razon
        assert campo.as_dict()["valor"] is None                                       # un «no disponible» no da valor

    def test_no_lo_se_queda_como_no_consta_y_registrado(self):
        info, mapa = _pdb(fuente_declarada="no_se")

        assert info["no_disponible"] == P.FUENTE_SIN_DECLARAR and mapa is None
        assert info["declaracion"] == {"fuente": "no_se", "herramienta": None, "usada": True}


class TestUnaDeclaracionQueNoCoincide:
    """Controles: declarar Boltz-2 no basta; el archivo tiene que ser como los que escribe Boltz 2.2.1."""

    def test_un_factor_b_distinto_dentro_de_un_residuo_no_se_lee(self):
        # El Cα de cada residuo con otro valor (columnas 61-66): ya no hay un pLDDT por residuo.
        roto = "".join(linea[:60] + " 50.00" + linea[66:] if linea.startswith("ATOM") and linea[12:16] == " CA "
                       else linea for linea in PDB_BOLTZ.splitlines(keepends=True))
        assert roto != PDB_BOLTZ and roto.count(" 50.00 ") >= 90

        info, mapa = _pdb(roto, fuente_declarada="boltz")

        assert info["no_disponible"] == P.DECLARACION_NO_COINCIDE and mapa is None

    def test_un_pdb_con_el_factor_b_en_0_1_no_se_lee(self):
        en_unidad = re.sub(r"^(ATOM.{56})(.{6})", lambda m: m.group(1) + f"{float(m.group(2)) / 100:6.4f}"[:6],
                           PDB_BOLTZ, flags=re.M)

        info, mapa = _pdb(en_unidad, fuente_declarada="boltz")

        assert info["no_disponible"] == P.DECLARACION_NO_COINCIDE and mapa is None

    def test_un_mmcif_que_no_es_modelcif_declarado_boltz_no_se_lee(self):
        # Boltz escribe sus mmCIF en ModelCIF; uno sin esas tablas no es lo que se comprobó.
        sin_modelcif = CIF_BOLTZ.replace("_ma_", "_xx_")
        assert P.hay_que_preguntar_la_fuente("mmcif", sin_modelcif)

        info, mapa = _cif(sin_modelcif, fuente_declarada="boltz")

        assert info["no_disponible"] == P.DECLARACION_NO_COINCIDE and mapa is None


class TestLaDeclaracionNoPisaAlArchivo:
    def test_un_archivo_de_alphafold_db_sigue_siendolo_aunque_se_declare_otra_cosa(self):
        info, mapa = P.analizar("pdb", PDB_AF, normalizar_pdb(PDB_AF)[0], fuente_declarada="experimental")

        assert info["fuente"] == "alphafold_db" and mapa
        assert info["declaracion"]["usada"] is False

    def test_un_cristal_que_declara_su_metodo_no_se_lee_como_boltz(self):
        info, mapa = P.analizar("pdb", PDB_8HFI, PDB_8HFI, fuente_declarada="boltz")

        assert info["es_predicha"] is False and info["metodo_declarado"] == "ELECTRON MICROSCOPY" and mapa is None
        assert info["declaracion"]["usada"] is False

    @pytest.mark.parametrize("formato, texto", [
        ("pdb", PDB_AF), ("mmcif", CIF_AF), ("pdb", PDB_8HFI), ("mmcif", CIF_8HFI), ("mmcif", CIF_BOLTZ),
        ("mmcif", CIF_CHAI), ("pqr", PDB_BOLTZ), ("pdb", PDB_BOLTZ),
    ], ids=["afdb-pdb", "afdb-cif", "8hfi-pdb", "8hfi-cif", "boltz-cif", "chai-cif", "pqr", "boltz-pdb"])
    def test_se_pregunta_exactamente_cuando_la_subida_usaria_la_declaracion(self, formato, texto):
        if formato == "mmcif":
            info, _ = _cif(texto)
        else:
            info, _ = P.analizar(formato, texto, normalizar_pdb(texto)[0])

        assert P.hay_que_preguntar_la_fuente(formato, texto) == (info["no_disponible"] == P.FUENTE_SIN_DECLARAR)

    def test_una_fuente_desconocida_es_un_error_y_el_nombre_se_limpia(self):
        with pytest.raises(ValueError):
            P.normalizar_declaracion("alphafold3")
        assert P.normalizar_declaracion(None) is None and P.normalizar_declaracion("  ") is None
        assert P.normalizar_declaracion("BOLTZ", "ignorado") == {"fuente": "boltz", "herramienta": None}
        limpio = P.normalizar_declaracion("otra", " Color\x00Fold\n" + "x" * 200)
        assert limpio["herramienta"].startswith("Color Fold x") and len(limpio["herramienta"]) == P.MAX_HERRAMIENTA


class TestLosMmcifDeBoltzYChai:
    def test_boltz_se_lee_como_modelcif_sin_verificar_y_es_su_factor_b(self):
        info, mapa = _cif(CIF_BOLTZ)
        por_atomo, _ = _factor_b_cif(CIF_BOLTZ)

        assert info["fuente"] == "modelcif" and info["convencion"]["verificada"] is False
        assert not P.hay_que_preguntar_la_fuente("mmcif", CIF_BOLTZ)
        assert all(max(v) - min(v) < 0.0006 for v in por_atomo.values())           # uno por residuo
        assert len(mapa) == 90 and all(abs(mapa[k] - v[0]) < 0.0006 for k, v in por_atomo.items())
        assert info["plddt"]["bajo_70"] == 13

    def test_chai_declara_su_fuente_pero_el_producto_lee_el_calfa_y_no_la_media(self):
        """Lo que hace hoy (acta del 2026-11-15): la media por residuo es el pLDDT del modelo; el Cα es más alto."""
        info, mapa = _cif(CIF_CHAI)
        por_atomo, ca = _factor_b_cif(CIF_CHAI)
        media = {k: sum(v) / len(v) for k, v in por_atomo.items()}

        assert "_struct.title 'Chai-1 predicted structure'" in CIF_CHAI
        assert info["fuente"] == P.FUENTE_ARCHIVO_CHAI1 and info["convencion"]["verificada"] is False
        assert all(abs(mapa[k] - ca[k]) < 0.0006 for k in mapa)                    # lee el Cα
        assert round(ca["A:36"] - media["A:36"], 1) == 14.7                           # que se aparta de la media
        assert sum(v < 70 for v in mapa.values()) == 5 and sum(v < 70 for v in media.values()) == 11


def _sin_firma(texto: str, titulo: str | None) -> str:
    """El mismo mmCIF de Chai-1 con otro ``_struct.title``, o sin él."""
    linea = f"_struct.title '{P.FIRMA_CHAI1}'"
    assert texto.count(linea) == 1
    return texto.replace(linea, "" if titulo is None else f"_struct.title '{titulo}'")


def _centro_del_ca(texto: str, clave: str) -> tuple[float, float, float]:
    import gemmi

    estructura = gemmi.make_structure_from_block(gemmi.cif.read_string(texto)[0])
    for cadena in estructura[0]:
        for residuo in cadena:
            if f"{cadena.name}:{residuo.seqid.num}" == clave:
                pos = residuo.find_atom("CA", "*").pos
                return (pos.x, pos.y, pos.z)
    raise KeyError(clave)


class TestLaFirmaDeChai:
    """D-01 de la investigación de 1.0.4: con la firma de Chai-1 se nombra la herramienta como declarada por el
    archivo, y se dice que el valor es el del Cα sólo si el propio archivo lo cumple; lo que se lee, y por tanto la
    regla del 70, no cambia."""

    def test_con_la_firma_nombra_chai_y_el_calfa_sin_darla_por_verificada(self):
        info, mapa = _cif(CIF_CHAI)

        assert info["fuente"] == P.FUENTE_ARCHIVO_CHAI1
        assert f"_struct.title: «{P.FIRMA_CHAI1}»" in info["evidencia"]
        assert info["convencion"] == {"plddt_en": "ma_qa_metric_local", "escala": "0-100", "verificada": False,
                                      "referencia": P.REFERENCIA_CHAI1, "lectura": "calfa"}
        assert info["plddt"]["bajo_70"] == 5 and len(mapa) == 90

    @pytest.mark.parametrize("titulo", [None, "Chai-2 predicted structure", "chai-1 predicted structure",
                                        "Chai-1 predicted structure (editado)"])
    def test_sin_la_firma_exacta_sigue_siendo_un_modelcif_y_lee_lo_mismo(self, titulo):
        """Control negativo: la firma es la cadena exacta del exportador, no algo que se le parezca."""
        con_firma, mapa_con = _cif(CIF_CHAI)
        info, mapa = _cif(_sin_firma(CIF_CHAI, titulo))

        assert info["fuente"] == "modelcif" and "lectura" not in info["convencion"]
        assert info["convencion"]["referencia"] is None
        assert not any("_struct.title" in e for e in info["evidencia"])
        assert mapa == mapa_con and info["plddt"] == con_firma["plddt"]

    def test_con_la_firma_pero_un_valor_que_no_es_el_calfa_no_se_dice_que_es_el_calfa(self):
        """Contraejemplo del seguimiento de la réplica (2026-11-15): la primera fila de la tabla local, de 91,387 a 51.

        La firma sigue nombrando a Chai-1, pero este archivo ya no guarda el Cα, así que no se afirma; el texto es el
        genérico «sin verificar» y lo que se lee (el valor local) es el del archivo.
        """
        fila = "1 1 A 1 MET 1 91.387"
        assert CIF_CHAI.count(fila) == 1
        info, mapa = _cif(CIF_CHAI.replace(fila, "1 1 A 1 MET 1 51"))

        assert info["fuente"] == P.FUENTE_ARCHIVO_CHAI1
        assert f"_struct.title: «{P.FIRMA_CHAI1}»" in info["evidencia"]
        assert "lectura" not in info["convencion"] and info["convencion"]["referencia"] is None
        assert info["convencion"]["verificada"] is False and mapa["A:1"] == 51.0

        campo, _ = campo_de_confianza(info)
        assert "Chai-1 (declarado por el archivo en _struct.title)" in campo.valor
        assert "Cα" not in campo.valor
        assert "convención de esta fuente sin verificar con un archivo real" in campo.valor

    def test_con_la_firma_y_un_b_uniforme_por_residuo_no_se_dice_que_no_es_la_media(self):
        """Segunda opinión (2026-11-15): si todos los átomos de cada residuo llevan el valor local, el Cα coincide,
        pero también la media, así que «no es la media del residuo» no estaría mostrado en ese archivo."""
        import gemmi

        # Sólo se reescribe la columna B_iso_or_equiv: cada átomo de proteína toma el B de su Cα. La firma y la tabla
        # ModelCIF quedan intactas.
        documento = gemmi.cif.read_string(CIF_CHAI)
        tabla = documento[0].find("_atom_site.", ["group_PDB", "label_asym_id", "label_seq_id", "label_atom_id",
                                                  "B_iso_or_equiv"])
        del_ca = {(f[1], f[2]): f[4] for f in tabla if f[0] == "ATOM" and f[3] == "CA"}
        cambiados = 0
        for fila in tabla:
            if fila[0] == "ATOM" and (fila[1], fila[2]) in del_ca and fila[4] != del_ca[(fila[1], fila[2])]:
                fila[4] = del_ca[(fila[1], fila[2])]
                cambiados += 1
        uniforme = documento.as_string()
        assert cambiados > 0 and f"_struct.title '{P.FIRMA_CHAI1}'" in uniforme
        assert all(max(v) - min(v) < 0.0006 for v in _factor_b_cif(uniforme)[0].values())

        info, mapa = _cif(uniforme)

        assert info["fuente"] == P.FUENTE_ARCHIVO_CHAI1
        assert "lectura" not in info["convencion"] and info["convencion"]["referencia"] is None
        assert mapa == _cif(CIF_CHAI)[1]
        campo, _ = campo_de_confianza(info)
        assert "Cα" not in campo.valor and "no es la media" not in campo.valor

    def test_la_firma_no_cambia_el_mmcif_de_boltz(self):
        info, _ = _cif(CIF_BOLTZ)
        assert info["fuente"] == "modelcif" and "lectura" not in info["convencion"]

    def test_preparacion_nombra_chai_y_el_calfa_y_el_estado_no_cambia(self):
        centro = _centro_del_ca(CIF_CHAI, "A:36")
        conversion = mmcif_a_pdb(CIF_CHAI, "x.cif")
        estados = []
        for texto in (CIF_CHAI, _sin_firma(CIF_CHAI, None)):
            info, mapa = _cif(texto)
            sitio = P.confianza_del_sitio(mapa, conversion.pdb, centro, (10.0, 10.0, 10.0))
            campo, accion = campo_de_confianza({**info, "sitio": sitio})
            estados.append((campo.estado, sitio["n_bajo_70"], accion))
            if texto is CIF_CHAI:
                assert "Chai-1 (declarado por el archivo en _struct.title)" in campo.valor
                assert "los valores leídos coinciden con el factor B de los Cα correspondientes" in campo.valor
                assert "El archivo declara Chai-1 y no acredita su versión" in campo.valor
                # Un B que varía no demuestra que el Cα sea distinto de la media: no se afirma (revisión final, D-01).
                assert "no es la media" not in campo.valor and "0.6.1" not in campo.valor
            else:
                assert "Chai-1" not in campo.valor and "estructura predicha (ModelCIF)" in campo.valor
        assert estados[0] == estados[1]

    def test_las_frases_de_chai_pasan_al_ingles_sin_dejar_castellano(self):
        from tests.test_dossier_en_ingles_completo import _parece_espanol

        info, mapa = _cif(CIF_CHAI)
        sitio = P.confianza_del_sitio(mapa, mmcif_a_pdb(CIF_CHAI, "x.cif").pdb, _centro_del_ca(CIF_CHAI, "A:36"),
                                      (10.0, 10.0, 10.0))
        campo, accion = campo_de_confianza({**info, "sitio": sitio})
        auditoria = {"bloques": [{"id": "receptor", "requisitos": [
            {**campo.as_dict(), "clave": "receptor.confianza_estructural",
             **({"accion_recomendada": accion} if accion else {})}]}]}

        en = traducir_dossier(auditoria, "en")["bloques"][0]["requisitos"][0]

        assert "structure predicted by Chai-1 (declared by the file in _struct.title)" in en["valor"]
        assert "the values read match the B-factor of the corresponding Cα atoms" in en["valor"]
        assert "The file declares Chai-1 and does not establish its version" in en["valor"]
        for texto in filter(None, [en["valor"], en["razon"], en.get("accion_recomendada")]):
            assert not _parece_espanol(texto), texto


class TestPreparacionConBoltz:
    def test_el_sitio_del_bucle_37_41_pide_revision_y_nombra_la_fuente_declarada(self):
        info, mapa = _pdb(fuente_declarada="boltz")
        sitio = P.confianza_del_sitio(mapa, normalizar_pdb(PDB_BOLTZ)[0], CA_39, (10.0, 10.0, 10.0))

        campo, accion = campo_de_confianza({**info, "sitio": sitio})

        assert campo.estado == Estado.REVISAR and accion
        assert "Boltz-2 (fuente declarada por quien subió el archivo)" in campo.valor
        assert "convención comprobada con un archivo real de Boltz 2.2.1" in campo.valor
        assert "A:39 THR (61.24)" in campo.valor

    def test_el_sitio_de_la_bisagra_queda_registrado(self):
        info, mapa = _pdb(fuente_declarada="boltz")
        sitio = P.confianza_del_sitio(mapa, normalizar_pdb(PDB_BOLTZ)[0], CA_83, (10.0, 10.0, 10.0))

        campo, _ = campo_de_confianza({**info, "sitio": sitio})

        assert campo.estado == Estado.REGISTRADO and sitio["n_bajo_70"] == 0 and sitio["con_plddt"] > 5

    def test_todas_las_frases_nuevas_pasan_al_ingles_sin_dejar_castellano(self):
        from tests.test_dossier_en_ingles_completo import _parece_espanol

        boltz, mapa = _pdb(fuente_declarada="boltz")
        sitio = P.confianza_del_sitio(mapa, normalizar_pdb(PDB_BOLTZ)[0], CA_39, (10.0, 10.0, 10.0))
        casos = [{**boltz, "sitio": sitio}, _pdb(fuente_declarada="experimental")[0], _pdb()[0],
                 _pdb(fuente_declarada="otra", herramienta_declarada="ColabFold")[0],
                 _pdb(fuente_declarada="no_se")[0],
                 _pdb(PDB_BOLTZ.replace(" 61.24 ", " 11.11 ", 1), fuente_declarada="boltz")[0]]   # un átomo distinto
        assert {c.get("no_disponible") for c in casos} == {None, P.FUENTE_SIN_DECLARAR, P.HERRAMIENTA_SIN_VERIFICAR,
                                                            P.DECLARACION_NO_COINCIDE}
        for prediccion in casos:
            campo, accion = campo_de_confianza(prediccion)
            auditoria = {"bloques": [{"id": "receptor", "requisitos": [
                {**campo.as_dict(), "clave": "receptor.confianza_estructural",
                 **({"accion_recomendada": accion} if accion else {})}]}]}

            en = traducir_dossier(auditoria, "en")["bloques"][0]["requisitos"][0]

            for texto in filter(None, [en["valor"], en["razon"], en.get("accion_recomendada")]):
                assert not _parece_espanol(texto), (prediccion.get("no_disponible"), texto)
        en = traducir_dossier({"bloques": [{"id": "receptor", "requisitos": [
            {**campo_de_confianza(casos[3])[0].as_dict(), "clave": "receptor.confianza_estructural"}]}]}, "en")
        assert en["bloques"][0]["requisitos"][0]["razon"].startswith(
            "Whoever uploaded the file declared it a prediction from ColabFold, but")


# ── Por la API ───────────────────────────────────────────────────────────────


def _subir(cliente, nombre: str, contenido: str | bytes, centro, *, camino: str = "automatico", **extra):
    datos = {"name": "boltz", "is_curated": "false", "chain_id": "A", "modo_preparacion": camino,
             "grid_center_x": str(centro[0]), "grid_center_y": str(centro[1]), "grid_center_z": str(centro[2]),
             "grid_size_x": "10", "grid_size_y": "10", "grid_size_z": "10", **extra}
    contenido = contenido.encode() if isinstance(contenido, str) else contenido
    return cliente.post("/targets/upload", data=datos, files={"file": (nombre, contenido)})


def _inspeccionar(cliente, nombre: str, contenido: str | bytes):
    contenido = contenido.encode() if isinstance(contenido, str) else contenido
    return cliente.post("/targets/upload/inspeccion", files={"file": (nombre, contenido)})


@pytest.mark.asyncio
async def test_la_inspeccion_dice_cuando_hay_que_preguntar(entorno):
    cliente = entorno.client(await entorno.user("ana"))

    boltz = _inspeccionar(cliente, "cdk2_lig_model_0.pdb", PDB_BOLTZ)
    comprimido = _inspeccionar(cliente, "cdk2_lig_model_0.pdb.gz", gzip.compress(PDB_BOLTZ.encode()))
    afdb = _inspeccionar(cliente, "AF-P23975-F1-model_v6.pdb", PDB_AF)
    chai = _inspeccionar(cliente, "pred.model_idx_0.cif", CIF_CHAI)
    mala = _inspeccionar(cliente, "ligando.sdf", "x")

    assert boltz.status_code == 200 and boltz.json() == {
        "formato": "pdb", "pregunta_fuente": True, "fuentes": ["experimental", "boltz", "otra", "no_se"]}
    assert comprimido.json()["pregunta_fuente"] is True
    assert afdb.json()["pregunta_fuente"] is False and chai.json()["pregunta_fuente"] is False
    assert mala.status_code >= 400 and mala.json()["codigo"]          # el mismo error que daría la subida


@pytest.mark.asyncio
async def test_un_pdb_de_boltz_declarado_pide_revision_junto_al_bucle_y_sin_declarar_no_consta(entorno):
    cliente = entorno.client(await entorno.user("ana"))

    declarado = _subir(cliente, "cdk2_lig_model_0.pdb", PDB_BOLTZ, CA_39, fuente_declarada="boltz")
    sin_declarar = _subir(cliente, "cdk2_lig_model_0.pdb", PDB_BOLTZ, CA_39)

    assert declarado.status_code == 201, declarado.text
    informe, auditoria = _auditoria_de(declarado)
    assert informe["prediccion"]["fuente"] == "boltz" and informe["prediccion"]["sitio"]["n_bajo_70"] >= 3
    requisito = _requisito(auditoria, "receptor.confianza_estructural")
    assert requisito["estado"] == "REVISAR" and "Boltz-2" in requisito["valor"]
    assert "receptor.confianza_estructural" in auditoria["en_revision"]
    assert "receptor.confianza_estructural" not in auditoria["bloqueantes"]

    assert sin_declarar.status_code == 201, sin_declarar.text
    informe, auditoria = _auditoria_de(sin_declarar)
    assert informe["prediccion"]["no_disponible"] == P.FUENTE_SIN_DECLARAR
    requisito = _requisito(auditoria, "receptor.confianza_estructural")
    assert requisito["estado"] == "NO_DISPONIBLE" and requisito["valor"] is None
    assert "receptor.confianza_estructural" not in auditoria["bloqueantes"]


@pytest.mark.asyncio
async def test_una_fuente_que_no_existe_se_rechaza_antes_de_preparar(entorno):
    cliente = entorno.client(await entorno.user("ana"))

    respuesta = _subir(cliente, "cdk2_lig_model_0.pdb", PDB_BOLTZ, CA_39, fuente_declarada="alphafold3")

    assert respuesta.status_code == 422 and respuesta.json()["codigo"] == "FUENTE_DECLARADA_INVALIDA"


@pytest.mark.asyncio
async def test_en_el_camino_c_la_declaracion_es_de_la_estructura_de_origen(entorno):
    from utils.local_storage import path_for

    cliente = entorno.client(await entorno.user("ana"))
    primera = _subir(cliente, "cdk2_lig_model_0.pdb", PDB_BOLTZ, CA_39, fuente_declarada="boltz")
    assert primera.status_code == 201, primera.text
    pdbqt = path_for(primera.json()["target"]["prepared_file_path"]).read_bytes()
    campos = {"name": "pdbqt de Boltz", "is_curated": "true", "modo_preparacion": "pdbqt", "chain_id": "A",
              "grid_center_x": str(CA_39[0]), "grid_center_y": str(CA_39[1]), "grid_center_z": str(CA_39[2]),
              "grid_size_x": "10", "grid_size_y": "10", "grid_size_z": "10", "fuente_declarada": "boltz"}

    respuesta = cliente.post("/targets/upload", data=campos, files={
        "file": ("receptor.pdbqt", pdbqt), "source_file": ("cdk2_lig_model_0.pdb", PDB_BOLTZ.encode())})

    assert respuesta.status_code == 201, respuesta.text
    informe, auditoria = _auditoria_de(respuesta)
    assert informe["prediccion"]["fuente"] == "boltz"
    assert _requisito(auditoria, "receptor.confianza_estructural")["estado"] == "REVISAR"


class _Respuesta:
    """Lo que espera ``_auditoria_de``: la variante devuelve el ``Target``, sin la ruta del receptor preparado."""

    def __init__(self, pdb_id: str):
        from utils.local_storage import path_for

        preparados = sorted(path_for(f"targets/{pdb_id}").glob("prepared-*.pdbqt"))
        assert len(preparados) == 1, preparados
        self._target = {"prepared_file_path": f"targets/{pdb_id}/{preparados[0].name}"}

    def json(self) -> dict:
        return {"target": self._target}


@pytest.mark.asyncio
@pytest.mark.parametrize("nombre, contenido, extra, fuente", [
    ("cdk2_lig_model_0.pdb", PDB_BOLTZ, {"fuente_declarada": "boltz"}, "boltz"),
    ("AF-P23975-F1-model_v6.cif", CIF_AF, {}, "alphafold_db"),
], ids=["boltz-declarado", "alphafold-mmcif"])
async def test_una_variante_hereda_el_analisis_de_su_padre(entorno, nombre, contenido, extra, fuente):
    """La variante lee el PDB ya convertido del padre, sin cabecera ni ModelCIF: antes perdía la predicción."""
    from services.targets import perfil_receptor

    cliente = entorno.client(await entorno.user("ana"))
    centro = CA_39 if fuente == "boltz" else (-51.005, -23.775, 29.204)
    padre = _subir(cliente, nombre, contenido, centro, **extra)
    assert padre.status_code == 201, padre.text
    id_padre = padre.json()["target"]["pdb_id"]

    variante = cliente.post(f"/targets/{id_padre}/variants", json={"name": "otra caja", "grid_size": [12.0, 12.0, 12.0]})

    assert variante.status_code == 201, variante.text
    hijo = variante.json()
    prediccion = perfil_receptor.cargar(hijo["pdb_id"])["prediccion"]
    assert prediccion["fuente"] == fuente and prediccion["heredada_de"] == id_padre
    informe, auditoria = _auditoria_de(_Respuesta(hijo["pdb_id"]))
    assert informe["prediccion"]["sitio"]["n_bajo_70"] >= 1
    assert _requisito(auditoria, "receptor.confianza_estructural")["estado"] == "REVISAR"
