"""Metales y cofactores junto al sitio, en dos niveles (2026-10-22).

Lo midió ABS-TR-01-VALIDEZ (`docs/100`): de los 3 falsos bloqueos de 18, dos (1RKP y 6KE5) eran un ion retirado a ≤ 6 Å que
el ligando no coordina, y en 1RKP la distancia la ponía la pose de Vina (5,17 Å) y no el cristal (6,52 Å), así que la decisión
dependía de la semilla. Y 4NY4, con el Fe del hemo coordinado por el ligando, pasaba sin aviso porque el hemo se conserva.

Ahora: un metal o cofactor retirado que el ligando del cristal coordina (N, O o S a ≤ 2,8 Å de un metal) sigue absteniendo; uno
sólo cercano pide revisión; la distancia de metales y cofactores se mide desde el cristal cuando lo hay; y un metal conservado
que el ligando coordina pide revisión. Sin ligando del cristal no se sabe si lo coordina, y se abstiene como antes.
"""

from __future__ import annotations

import copy

from core.i18n_plantillas import _PARECE_CASTELLANO
from services.dossier.contexto_estructural import _Atomo, _atomos, _coordinacion
from services.dossier.localization import traducir_dossier
from tests.test_preparacion_auditoria import _requisito
from tests.test_preparacion_desde_el_ligando import _auditar, _caso, _contexto

ZN = ("A", "301", "", "ZN")
HEM = ("B", "701", "", "HEM")


def _metales(caso: dict, **contexto) -> dict:
    auditoria = _auditar(caso, _contexto_con(**contexto))
    return auditoria, _requisito(auditoria, "entorno.metales_cofactores")


def _contexto_con(*, metal: float = 3.0, al_cristal: dict | None = None, coordinadas: dict | None = None):
    c = _contexto(metal=metal)
    c.especies_al_cristal = dict(al_cristal or {})
    c.coordinadas = coordinadas
    return c


class TestDosNiveles:
    def test_cerca_y_sin_coordinar_pide_revision(self):
        auditoria, metales = _metales(_caso(), coordinadas={})
        assert metales["estado"] == "REVISAR"
        assert "entorno.metales_cofactores" not in auditoria["bloqueantes"]
        assert "El ligando del cristal no toca ninguno" in metales["valor"]
        assert metales["accion_recomendada"].startswith("Si la especie es estructural o catalítica")

    def test_coordinado_por_el_ligando_sigue_absteniendo(self):
        auditoria, metales = _metales(_caso(), coordinadas={ZN: "N21–ZN 2.05 Å"})
        assert metales["estado"] == "ABSTENCION"
        assert "entorno.metales_cofactores" in auditoria["bloqueantes"]
        assert "En contacto con el ligando del cristal: ZN A:301 (N21–ZN 2.05 Å)." in metales["valor"]

    def test_un_cofactor_en_contacto_sigue_absteniendo(self):
        _, metales = _metales(_caso(), coordinadas={HEM: "contacto 3.40 Å"})
        assert metales["estado"] == "ABSTENCION"
        assert "HEM B:701 (contacto 3.40 Å)" in metales["valor"]

    def test_sin_ligando_del_cristal_no_se_sabe_y_se_abstiene(self):
        _, metales = _metales(_caso(), coordinadas=None)
        assert metales["estado"] == "ABSTENCION"

    def test_la_distancia_es_la_del_cristal_y_no_la_de_la_pose(self):
        """1RKP: la pose acercaba el Zn a 5,17 Å; el cristal lo deja a 6,52 Å."""
        _, metales = _metales(_caso(), metal=5.17, al_cristal={ZN: 6.52, HEM: 6.9}, coordinadas={})
        assert metales["estado"] == "REGISTRADO"
        assert "ZN A:301 (6.52 Å)" in metales["valor"]
        assert "5.17" not in metales["valor"]

    def test_sin_distancia_al_cristal_se_usa_la_de_la_pose(self):
        _, metales = _metales(_caso(), metal=5.17, al_cristal={}, coordinadas={})
        assert "ZN A:301 (5.17 Å)" in metales["valor"]

    def test_un_metal_conservado_y_coordinado_pide_revision(self):
        """4NY4: el ligando coordina el Fe del hemo que el receptor conserva."""
        caso = _caso()
        prov = copy.deepcopy(caso["eval_result"].docking_protocol["execution_provenance"])
        cerca = prov["receptor_prep"]["species_diff"]["near_site"]
        cerca["preserved"] = cerca.get("preserved", []) + [f for f in cerca["removed"] if f["name"] == "ZN"]
        cerca["removed"] = [f for f in cerca["removed"] if f["name"] != "ZN"]
        caso["eval_result"].docking_protocol = {**caso["eval_result"].docking_protocol, "execution_provenance": prov}
        auditoria, metales = _metales(caso, metal=9.0, coordinadas={ZN: "N32–FE 2.12 Å"})
        assert metales["estado"] == "REVISAR"
        assert "Conservados y coordinados por el ligando del cristal: ZN A:301 (N32–FE 2.12 Å)." in metales["valor"]
        assert metales["razon"].startswith("El ligando del cristal coordina un metal que el receptor conserva.")

    def test_sale_en_ingles(self):
        for coordinadas in ({}, {ZN: "N21–ZN 2.05 Å"}, None):
            ingles = traducir_dossier(_auditar(_caso(), _contexto_con(coordinadas=coordinadas)), "en")
            metales = _requisito(ingles, "entorno.metales_cofactores")
            for campo in ("valor", "razon", "accion_recomendada"):
                texto = metales.get(campo)
                if isinstance(texto, str):
                    assert not _PARECE_CASTELLANO.search(texto), (coordinadas, campo, texto)


def _atomo(nombre: str, residuo: str, xyz, elemento: str) -> _Atomo:
    return _Atomo("HETATM", "A", "1", "", residuo, nombre, "", 1.0, xyz, elemento)


class TestCoordinacion:
    def test_un_donador_a_2_8_o_menos_coordina(self):
        zn = [_atomo("ZN", "ZN", (0.0, 0.0, 0.0), "ZN")]
        assert _coordinacion(zn, [_atomo("N21", "AL5", (2.05, 0.0, 0.0), "N")]) == "N21–ZN 2.05 Å"

    def test_mas_lejos_no(self):
        zn = [_atomo("ZN", "ZN", (0.0, 0.0, 0.0), "ZN")]
        assert _coordinacion(zn, [_atomo("O1", "LIG", (2.95, 0.0, 0.0), "O")]) is None

    def test_el_hierro_dentro_del_hemo_cuenta(self):
        hemo = [_atomo("NA", "HEM", (1.0, 1.0, 0.0), "N"), _atomo("FE", "HEM", (0.0, 0.0, 0.0), "FE")]
        assert _coordinacion(hemo, [_atomo("N32", "2QH", (0.0, 0.0, 2.12), "N")]) == "N32–FE 2.12 Å"

    def test_un_cofactor_sin_metal_no_coordina(self):
        nad = [_atomo("O2N", "NAD", (0.0, 0.0, 0.0), "O")]
        assert _coordinacion(nad, [_atomo("N1", "LIG", (1.5, 0.0, 0.0), "N")]) is None


class TestElementoConCarga:
    """MET-02-SEMILLA: en 45 de los 446 depósitos la columna 79 trae la carga («MG2», «ZN0», «H0»)."""

    @staticmethod
    def _linea(registro: str, nombre: str, residuo: str, xyz, elemento_y_carga: str) -> str:
        return (f"{registro:<6}{1:>5} {nombre:<4} {residuo:>3} A 601    "
                f"{xyz[0]:8.3f}{xyz[1]:8.3f}{xyz[2]:8.3f}  1.00 20.00          {elemento_y_carga:<4}")

    def test_el_metal_con_carga_se_reconoce(self):
        texto = chr(10).join([self._linea("HETATM", "MG", "MG", (0, 0, 0), "MG2+"),
                           self._linea("HETATM", "O1G", "ANP", (1.94, 0, 0), "O0")])
        mg, o = _atomos(texto)
        assert (mg.elemento, o.elemento) == ("MG", "O")
        assert _coordinacion([mg], [o]) == "O1G–MG 1.94 Å"

    def test_un_hidrogeno_con_carga_no_cuenta_como_pesado(self):
        texto = chr(10).join([self._linea("HETATM", "C1", "SHH", (0, 0, 0), "C0"),
                           self._linea("HETATM", "H1", "SHH", (1, 0, 0), "H0")])
        assert [a.nombre for a in _atomos(texto)] == ["C1"]

    def test_el_tipo_de_autodock_no_cambia(self):
        texto = chr(10).join([self._linea("ATOM", "OD1", "ASP", (0, 0, 0), " OA"),
                           self._linea("ATOM", "HD1", "HIS", (1, 0, 0), " HD")])
        assert [a.elemento for a in _atomos(texto, pesados=False)] == ["OA", "HD"]
