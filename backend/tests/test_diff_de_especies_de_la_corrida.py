"""El diff de heteroátomos que la corrida guarda, y lo que el dossier dice de él.

Hasta el 2026-09-27 sólo lo calculaba el preflight y no quedaba archivado con
el resultado, así que el dossier decía siempre NO_EVALUADO en «Aguas, metales y
cofactores». Para la pestaña Preparación eso deja sin evaluar el bloque del
entorno del sitio en todas las corridas, incluidas las que pierden un zinc
catalítico: la ruta de docking lo retira porque ningún receptor declara metales.

Lo que estas pruebas fijan:

1. El diff distingue lo retirado JUNTO AL SITIO de lo retirado en toda la
   estructura. Un recuento global no separa el zinc catalítico de un sulfato
   a 40 Å.
2. La corrida real (Meeko de verdad, disco vacío) lo escribe en el informe.
3. El dossier no reconstruye el diff cuando falta: un receptor en caché de
   antes de este campo se declara NO_EVALUADO.
"""

from __future__ import annotations

import json

import pytest

from services.docking import preflight, preparer
from services.dossier.model import build_case_dossier
from services.dossier.taxonomy import Estado
from tests.fixtures_dossier import caso_completo, resultado_completo


def _atomo(registro: str, serie: int, nombre: str, residuo: str, cadena: str,
           numero: int, x: float, y: float, z: float, elemento: str) -> str:
    return (
        f"{registro:<6}{serie:>5} {nombre:<4} {residuo:>3} {cadena}{numero:>4}    "
        f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00 20.00          {elemento:>2}"
    )


#: Caja de 10 Å centrada en el origen. MARGEN_SITIO_A = 6 Å, así que todo lo
#: que esté a 11 Å o menos del centro en un eje cuenta como junto al sitio.
CENTRO = (0.0, 0.0, 0.0)
CAJA = (10.0, 10.0, 10.0)

ESTRUCTURA = "\n".join([
    # Proteína de la cadena A, dentro de la caja.
    _atomo("ATOM", 1, "N", "ALA", "A", 1, 1.0, 0.0, 0.0, "N"),
    _atomo("ATOM", 2, "CA", "ALA", "A", 1, 2.0, 0.0, 0.0, "C"),
    # Selenometionina junto al sitio: entra en Meeko como MET.
    _atomo("HETATM", 3, "N", "MSE", "A", 2, 3.0, 1.0, 0.0, "N"),
    _atomo("HETATM", 4, "SE", "MSE", "A", 2, 3.5, 1.5, 0.0, "SE"),
    # Zinc catalítico a 2 Å del centro: la ruta de docking lo retira.
    _atomo("HETATM", 5, "ZN", "ZN", "A", 301, 2.0, 0.0, 0.0, "ZN"),
    # Un agua dentro y otra a 40 Å.
    _atomo("HETATM", 6, "O", "HOH", "A", 401, 0.0, 3.0, 0.0, "O"),
    _atomo("HETATM", 7, "O", "HOH", "A", 402, 45.0, 0.0, 0.0, "O"),
    # Sulfato lejano: retirado, pero NO junto al sitio.
    _atomo("HETATM", 8, "S", "SO4", "A", 501, 0.0, 45.0, 0.0, "S"),
    # El ligando del cristal, en el centro.
    _atomo("HETATM", 9, "C1", "LIG", "A", 601, 0.0, 0.0, 1.0, "C"),
    # Un HEM de OTRA cadena a 5 Å de la caja: la cadena B no entra.
    _atomo("ATOM", 10, "CA", "GLY", "B", 1, 30.0, 30.0, 30.0, "C"),
    _atomo("HETATM", 11, "FE", "HEM", "B", 701, 0.0, 0.0, 10.0, "FE"),
    # Dos residuos de la cadena B tocan la caja (dos átomos del mismo cuentan uno).
    _atomo("ATOM", 12, "N", "VAL", "B", 2, 0.0, 8.0, 0.0, "N"),
    _atomo("ATOM", 13, "CA", "VAL", "B", 2, 0.0, 9.0, 0.0, "C"),
    _atomo("ATOM", 14, "CA", "LEU", "B", 3, 0.0, 10.5, 0.0, "C"),
    "END",
]) + "\n"


def _diff() -> dict:
    entrada = preparer.filter_pdb_content(
        ESTRUCTURA, chain_id={"A"}, keep_hetatm=True, cofactors_whitelist=[],
        site_ligand="LIG",
    )
    return preflight.diff_de_especies_de_la_corrida(
        ESTRUCTURA, entrada, cadenas="A", center=CENTRO, size=CAJA, site_ligand="lig",
    )


def _por_nombre(filas: list[dict]) -> dict[str, dict]:
    return {f"{f['name']}{f['residue_number']}": f for f in filas}


class TestElDiff:
    def test_los_recuentos_son_los_del_preflight(self):
        """La misma semántica que enseña la comprobación previa, no otra."""
        diff = _diff()
        entrada = preparer.filter_pdb_content(
            ESTRUCTURA, chain_id={"A"}, keep_hetatm=True, cofactors_whitelist=[],
            site_ligand="LIG",
        )
        esperado = preflight._build_diff(
            preflight.count_species(ESTRUCTURA), preflight.count_species(entrada), "A",
        )
        for clave, valor in esperado.items():
            assert diff[clave] == valor, clave

    def test_separa_lo_retirado_junto_al_sitio(self):
        cerca = _diff()["near_site"]
        retiradas = _por_nombre(cerca["removed"])

        assert cerca["margin_A"] == preparer.MARGEN_SITIO_A
        assert retiradas["ZN301"]["category"] == "metal"
        assert retiradas["HOH401"]["category"] == "water"
        assert retiradas["LIG601"]["category"] == "site_ligand"
        # La cadena B no entra en el receptor aunque su HEM toque la caja.
        assert retiradas["HEM701"]["category"] == "organic_cofactor"
        assert retiradas["HEM701"]["distance_to_box_A"] == pytest.approx(5.0)

    def test_lo_lejano_no_cuenta_como_sitio(self):
        cerca = _diff()["near_site"]
        nombres = set(_por_nombre([*cerca["removed"], *cerca["preserved"]]))
        assert "HOH402" not in nombres
        assert "SO4501" not in nombres
        # Pero sigue en los recuentos globales: no se esconde, se sitúa.
        assert _diff()["removed"]["waters"] == 2

    def test_la_selenometionina_se_conserva_como_met(self):
        conservadas = _por_nombre(_diff()["near_site"]["preserved"])
        assert conservadas["MSE2"]["converted_to"] == "MET"

    def test_declara_el_ligando_normalizado(self):
        assert _diff()["site_ligand"] == "LIG"

    def test_cuenta_la_proteina_de_cadenas_excluidas_junto_al_sitio(self):
        """La GLY B1 está a 40 Å y no cuenta; VAL B2 y LEU B3 tocan la caja."""
        assert _diff()["near_site"]["protein_residues_removed"] == {"B": 2}


# ── La corrida real ──────────────────────────────────────────────────

RECEPTOR_CON_ZINC = "1C3R"


@pytest.mark.asyncio
async def test_prepare_target_guarda_el_diff_con_el_zinc_del_sitio(tmp_path, monkeypatch):
    """Meeko de verdad sobre un disco vacío, con un zinc catalítico en la caja.

    1C3R es la HDLP de *Aquifex aeolicus*, con el zinc a 0 Å de la caja. La
    ruta de docking lo retira porque el catálogo no declara metales para
    ningún receptor, y hasta hoy el expediente no podía decirlo. No se usa
    1BN1, el caso de la anhidrasa: Meeko pierde residuos de su sitio y la
    preparación se abstiene antes de escribir el informe.
    """
    from tests.test_preparacion_en_instalacion_limpia import (
        _catalogo,
        _sembrar_como_el_instalador,
    )
    from utils import local_storage

    datos = tmp_path / "MolDesign" / "data"
    datos.mkdir(parents=True)
    temporal = tmp_path / "vina"
    temporal.mkdir()
    for ajustes in (preparer.settings, local_storage.settings):
        monkeypatch.setattr(ajustes, "local_data_dir", str(datos))
        monkeypatch.setattr(ajustes, "vina_temp_dir", str(temporal))
    assert local_storage.data_dir() == datos

    objetivo = _catalogo(RECEPTOR_CON_ZINC)
    _sembrar_como_el_instalador(RECEPTOR_CON_ZINC, datos)
    ruta = await preparer.prepare_target(
        pdb_id=RECEPTOR_CON_ZINC,
        chain_id=objetivo["chain"],
        center=(objetivo["grid_center_x"], objetivo["grid_center_y"], objetivo["grid_center_z"]),
        size=(objetivo["grid_size_x"], objetivo["grid_size_y"], objetivo["grid_size_z"]),
        site_chains=objetivo["site_chains"],
    )

    informe = json.loads((datos / preparer._meeko_report_path(ruta)).read_text(encoding="utf-8"))
    diff = informe["species_diff"]
    assert diff["state"] == "evaluado"
    metales = {
        (f["chain"], f["residue_number"]): f
        for f in diff["near_site"]["removed"] if f["category"] == "metal"
    }
    # El de A es el catalítico del receptor acoplado. El de B también toca la
    # caja de 30 Å, aunque la cadena B no entra en el receptor.
    assert set(metales) == {("A", "501"), ("B", "503")}, diff["near_site"]["removed"]
    assert metales[("A", "501")]["name"] == "ZN"
    assert metales[("A", "501")]["distance_to_box_A"] == 0.0
    assert any(f["category"] == "site_ligand" for f in diff["near_site"]["removed"])
    # Y la cadena B entera que la caja toca sin entrar en el receptor.
    assert diff["near_site"]["protein_residues_removed"] == {"B": 131}


# ── Lo que dice el dossier ───────────────────────────────────────────


def _dossier_con(receptor_prep: dict | None):
    caso = caso_completo()
    resultado = resultado_completo()
    protocolo = dict(resultado.docking_protocol)
    if receptor_prep is not None:
        protocolo["execution_provenance"] = {"receptor_prep": receptor_prep}
    resultado.docking_protocol = protocolo
    caso["eval_result"] = resultado
    dossier = build_case_dossier(**caso)
    return next(c for c in dossier.preparacion if c.etiqueta == "Aguas, metales y cofactores")


class TestElDossier:
    def test_sin_diff_es_no_evaluado(self):
        campo = _dossier_con({"source": "meeko_report", "recipe_hash": "a" * 64})
        assert campo.estado == Estado.NO_EVALUADO
        assert "no se reconstruye" in campo.razon.lower()

    def test_un_receptor_congelado_lo_dice(self):
        campo = _dossier_con({"source": "durable_receptor_snapshot"})
        assert campo.estado == Estado.NO_EVALUADO
        assert "congelado" in campo.razon

    def test_un_metal_retirado_junto_al_sitio_pide_revision_y_se_ve(self):
        campo = _dossier_con({"source": "meeko_report", "species_diff": _diff()})
        assert campo.estado == Estado.REVISAR
        # El qué es el motivo de revisar: no puede quedar escondido.
        assert "ZN A:301" in campo.texto
        assert "HEM B:701" in campo.texto
        assert "ligando del cristal (LIG A:601)" in campo.texto

    def test_solo_aguas_y_ligando_es_registrado(self):
        diff = _diff()
        diff["near_site"] = {
            **diff["near_site"],
            "removed": [f for f in diff["near_site"]["removed"]
                        if f["category"] in ("water", "site_ligand")],
        }
        campo = _dossier_con({"source": "meeko_report", "species_diff": diff})
        assert campo.estado == Estado.REGISTRADO
        assert "retirado 1 agua(s)" in campo.texto

    def test_los_recuentos_se_llaman_registros(self):
        """`count_species` cuenta registros HETATM: un HEM son 43, no uno."""
        campo = _dossier_con({"source": "meeko_report", "species_diff": _diff()})
        assert campo.texto.startswith("Registros HETATM retirados del ensamblaje")


# ── QA-027: un cloruro no es un metal ─────────────────────────────────────


class TestRotuloDeMetal:
    """`preparer.METAL_COFACTORS` es la lista de RETENCIÓN y mete CL, XE y KR.

    Rotular con ella decía «2 metales» en 3F75 (dos Cl⁻) y Preparación bloqueaba
    cualquier corrida con un cloruro junto a la caja.
    """

    @pytest.mark.parametrize("residuo", ["CL", "XE", "KR"])
    def test_haluro_y_gases_nobles_no_son_metales(self, residuo):
        assert residuo in preparer.METAL_COFACTORS  # la retención no cambia
        assert preflight._species_category(residuo) == "other_heteroatom"

    @pytest.mark.parametrize("residuo", ["ZN", "MG", "FE", "NA", "K"])
    def test_los_metales_siguen_siendo_metales(self, residuo):
        assert preflight._species_category(residuo) == "metal"

    def test_el_recuento_no_cuenta_el_cloruro_como_metal(self):
        pdb = (
            "HETATM    1 CL    CL A 301      10.000  10.000  10.000  1.00 20.00          CL\n"
            "HETATM    2 ZN    ZN A 302      12.000  12.000  12.000  1.00 20.00          ZN\n"
        )
        cuenta = preflight.count_species(pdb)
        assert cuenta.metals == 1
        assert cuenta.other_hetatm == 1
