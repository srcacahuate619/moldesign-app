"""Códigos CCD de cinco caracteres, con mmCIF REALES del RCSB (8XVK: ambrisentán A1D5J; 8YUT: A1D67).

Los fixtures son recortes de ±10 Å alrededor del ligando de los archivos descargados de files.rcsb.org (dominio
público); el archivo completo y su SHA-256 están en el expediente de la entrega. Medido el 2026-10-09 sobre los
archivos enteros: 8XVK trae A1D5J (R:1201), 8ZP2 trae A1LX4 (A:701) y 8YUT trae A1D67 (R:401).

Control negativo: la conversión ingenua de gemmi (`make_pdb_string`) escribe el HETATM como «A1D» en los dos, que es
exactamente la colisión que la memoria `codigos-ccd-de-cinco-caracteres` documentó.
"""

from __future__ import annotations

import json
from pathlib import Path

import gemmi
import pytest
import pytest_asyncio

from services.targets.conversion_mmcif import mmcif_a_pdb
from tests.receptores_propios_ayudas import aislar_almacen
from tests.test_target_authorization import _Environment

DATOS = Path(__file__).parent / "data" / "receptores_propios"
CASOS = {
    "8xvk": ("A1D5J", "R", "1201"),
    "8yut": ("A1D67", "R", "401"),
}


def _texto(id_: str) -> str:
    ccd = CASOS[id_][0].lower()
    return (DATOS / f"{id_}_{ccd}_recortado.cif").read_text(encoding="utf-8")


@pytest.mark.parametrize("id_", sorted(CASOS))
def test_el_ligando_de_cinco_caracteres_se_escribe_con_un_sustituto_y_queda_la_correspondencia(id_):
    ccd, cadena, numero = CASOS[id_]

    conversion = mmcif_a_pdb(_texto(id_), f"{id_}.cif")

    renombrados = conversion.informe["residuos_renombrados"]
    assert [(r["original"], r["cadena"], str(r["numero"])) for r in renombrados] == [(ccd, cadena, numero)]
    sustituto = renombrados[0]["pdb"]
    assert len(sustituto) == 3 and sustituto != ccd[:3]
    hetero = {l[17:20].strip() for l in conversion.pdb.splitlines() if l.startswith("HETATM")}
    assert sustituto in hetero and ccd[:3] not in hetero and ccd not in hetero
    assert renombrados[0]["atomos"] == sum(
        1 for l in conversion.pdb.splitlines() if l.startswith("HETATM") and l[17:20].strip() == sustituto)
    assert "MMCIF_RESIDUOS_RENOMBRADOS" in conversion.informe["avisos"]
    assert conversion.informe["ensamblaje"]["estado"] == "aplicado"


@pytest.mark.parametrize("id_", sorted(CASOS))
def test_control_la_conversion_ingenua_de_gemmi_trunca_el_codigo_a_tres_caracteres(id_):
    ccd = CASOS[id_][0]
    st = gemmi.read_structure(str(DATOS / f"{id_}_{ccd.lower()}_recortado.cif"))
    st.setup_entities()

    ingenuo = {l[17:20].strip() for l in st.make_pdb_string().splitlines() if l.startswith("HETATM")}

    assert ccd[:3] in ingenuo and ccd not in ingenuo          # el defecto que la conversión propia evita
    # y los dos ligandos distintos de estas dos entradas serían el mismo «A1D» en un PDB clásico
    assert CASOS["8xvk"][0][:3] == CASOS["8yut"][0][:3] and CASOS["8xvk"][0] != CASOS["8yut"][0]


def test_dos_ligandos_con_el_mismo_prefijo_en_un_mismo_archivo_no_se_funden_con_los_codigos_reales():
    """8YUT con A1D5J añadido en otra posición: A1D67 y A1D5J deben seguir siendo dos residuos distintos."""
    texto = _texto("8yut")
    linea = next(l for l in texto.splitlines() if l.startswith("HETATM") and " A1D67 " in l)
    copia = [l.replace(" A1D67 ", " A1D5J ").replace(" 401 ", " 402 ") for l in texto.splitlines()
             if l.startswith("HETATM") and " A1D67 " in l]
    assert linea and copia
    cuerpo = texto.replace(linea, linea + "\n" + "\n".join(copia), 1)

    conversion = mmcif_a_pdb(cuerpo, "8yut_doble.cif")

    renombrados = {r["original"]: r["pdb"] for r in conversion.informe["residuos_renombrados"]}
    assert set(renombrados) == {"A1D67", "A1D5J"} and len(set(renombrados.values())) == 2


@pytest_asyncio.fixture
async def entorno(tmp_path, monkeypatch):
    aislar_almacen(monkeypatch, tmp_path / "almacen")
    env = _Environment(tmp_path / "targets.db")
    await env.start()
    try:
        yield env
    finally:
        await env.close()


@pytest.mark.asyncio
async def test_8xvk_pasa_por_la_subida_y_preparacion_enseña_el_codigo_original(entorno):
    import copy

    from services.dossier.localization import traducir_dossier
    from tests.fixtures_dossier import caso_completo
    from tests.test_preparacion_auditoria import _PROCEDENCIA, _auditar
    from utils.local_storage import path_for

    cliente = entorno.client(await entorno.user("ana"))
    respuesta = cliente.post("/targets/upload", data={
        "name": "8XVK", "is_curated": "false", "chain_id": "R", "grid_center_x": "155.03",
        "grid_center_y": "150.12", "grid_center_z": "167.72", "grid_size_x": "25", "grid_size_y": "25",
        "grid_size_z": "25"}, files={"file": ("8XVK.CIF", _texto("8xvk").encode())})

    assert respuesta.status_code == 201, respuesta.text
    destino = respuesta.json()["target"]
    informe = json.loads(path_for(destino["prepared_file_path"][:-6] + ".report.json").read_text(encoding="utf-8"))
    assert informe["entrada"]["conversion"]["residuos_renombrados"][0]["original"] == "A1D5J"
    caso = caso_completo()
    procedencia = copy.deepcopy(_PROCEDENCIA)
    procedencia["receptor_prep"] = {**informe, "chain": "R", "site_chains": ["R"]}
    caso["eval_result"].docking_protocol = {**caso["eval_result"].docking_protocol, "execution_provenance": procedencia}
    auditoria = _auditar(caso)

    def valor(a, clave):
        return next(r for b in a["bloques"] for r in b["requisitos"] if r["clave"] == clave)["valor"]

    assert "códigos largos sustituidos: A1D5J → " in valor(auditoria, "receptor.entrada")
    assert "(R:1201)" in valor(auditoria, "receptor.entrada")
    assert "[A1D5J] R:1201" in valor(auditoria, "entorno.otras_especies")      # el ligando del cristal, con su nombre real
    assert "long codes replaced: A1D5J → " in valor(traducir_dossier(auditoria, "en"), "receptor.entrada")
