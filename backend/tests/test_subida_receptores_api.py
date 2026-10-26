"""La subida de receptores propios por la API: qué se acepta y cómo se rechaza lo demás.

Las pruebas con Vina real viven en `docs/encargos/receptores-propios-1-0-2/qa_subida_receptores.py`
(el arnés levanta el backend y evalúa); aquí se fija el contrato de la ruta con una base
desechable y sin ejecutar ningún motor.
"""

from __future__ import annotations

import json

import pytest
import pytest_asyncio

from tests.receptores_propios_ayudas import aislar_almacen, linea_pdbqt, pdbqt_sintetico
from tests.test_target_authorization import _Environment

CAJA = {"grid_center_x": "10", "grid_center_y": "0", "grid_center_z": "0",
        "grid_size_x": "20", "grid_size_y": "20", "grid_size_z": "20"}


@pytest_asyncio.fixture
async def entorno(tmp_path, monkeypatch):
    aislar_almacen(monkeypatch, tmp_path / "almacen")
    env = _Environment(tmp_path / "targets.db")
    await env.start()
    try:
        yield env
    finally:
        await env.close()


def _subir(cliente, contenido: bytes, nombre: str, **campos):
    datos = {"name": "mi receptor", "is_curated": "true", "chain_id": "A", **CAJA, **campos}
    return cliente.post("/targets/upload", data=datos, files={"file": (nombre, contenido)})


@pytest.mark.asyncio
async def test_un_pdbqt_sin_origen_se_acepta_y_deja_perfil_e_informe(entorno):
    from services.targets import perfil_receptor
    from utils.local_storage import path_for

    usuario = await entorno.user("ana")
    respuesta = _subir(entorno.client(usuario), pdbqt_sintetico(residuos=30).encode(), "mi_receptor.pdbqt")

    assert respuesta.status_code == 201, respuesta.text
    cuerpo = respuesta.json()
    pdb_id = cuerpo["target"]["pdb_id"]
    assert pdb_id.startswith("USR_") and "sin la estructura de origen" in cuerpo["aviso_sin_origen"].lower()
    perfil = perfil_receptor.cargar(pdb_id)
    assert perfil["modo"] == "pdbqt" and perfil["origen"] is None
    assert perfil["entrada"]["archivo"] == "mi_receptor.pdbqt"
    preparado = path_for(cuerpo["target"]["prepared_file_path"])
    assert preparado.is_file() and preparado.with_suffix(".report.json").is_file()
    # Nada de esto toca el crudo: no hay origen que descargar ni inventar.
    assert not path_for(f"targets/{pdb_id}/raw.pdb").exists()


@pytest.mark.asyncio
async def test_un_pdbqt_con_registros_de_ligando_se_rechaza_con_codigo_y_sin_rutas(entorno):
    usuario = await entorno.user("ana")
    texto = pdbqt_sintetico(residuos=30) + "ROOT\nENDROOT\nTORSDOF 0\n"

    respuesta = _subir(entorno.client(usuario), texto.encode(), "ligando.pdbqt")

    assert respuesta.status_code == 400
    cuerpo = respuesta.json()
    assert cuerpo["codigo"] == "PDBQT_NO_ES_RIGIDO"
    assert "ROOT" in cuerpo["detail"] and ":\\" not in cuerpo["detail"]


@pytest.mark.asyncio
async def test_un_tipo_de_atomo_que_vina_no_admite_se_rechaza_con_su_linea(entorno):
    usuario = await entorno.user("ana")
    texto = pdbqt_sintetico(residuos=30) + linea_pdbqt(9000, "ZN", "ZN", "A", 301, (0, 0, 0), "ZN",
                                                       registro="HETATM") + "\n"

    respuesta = _subir(entorno.client(usuario), texto.encode(), "zinc.pdbqt")

    assert respuesta.status_code == 400
    assert respuesta.json()["codigo"] == "PDBQT_TIPO_NO_SOPORTADO"
    assert "ZN" in respuesta.json()["detail"]


@pytest.mark.asyncio
async def test_el_modo_pdbqt_sin_caja_pide_la_caja(entorno):
    usuario = await entorno.user("ana")
    cliente = entorno.client(usuario)
    datos = {"name": "x", "is_curated": "true", "chain_id": "A"}

    respuesta = cliente.post("/targets/upload", data=datos,
                             files={"file": ("r.pdbqt", pdbqt_sintetico(residuos=30).encode())})

    assert respuesta.status_code == 400
    assert respuesta.json()["codigo"] == "PDBQT_SIN_CAJA"


@pytest.mark.asyncio
async def test_el_modo_pdbqt_con_otra_extension_dice_que_hacer(entorno):
    usuario = await entorno.user("ana")

    respuesta = _subir(entorno.client(usuario), b"HEADER x\nATOM x\n", "estructura.pdb")

    assert respuesta.status_code == 400
    assert respuesta.json()["codigo"] == "PDBQT_EXTENSION"
    assert json.dumps(respuesta.json(), ensure_ascii=False).count("SDF") == 0


# ── Una estructura cruda, con Meeko real ──────────────────────────────────

import gzip
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
HSG = RAIZ / "data" / "targets" / "1HSG.pdb.gz"
CAJA_1HSG = {"grid_center_x": "13.073", "grid_center_y": "22.467", "grid_center_z": "5.557",
             "grid_size_x": "25", "grid_size_y": "25", "grid_size_z": "25"}


@pytest.mark.asyncio
async def test_un_pdb_gz_con_extension_en_mayusculas_se_prepara_y_registra_como_llego(entorno):
    from services.targets import perfil_receptor
    from utils.local_storage import path_for

    usuario = await entorno.user("ana")
    comprimido = HSG.read_bytes()
    respuesta = _subir(entorno.client(usuario), comprimido, "1HSG.PDB.GZ", is_curated="false", **CAJA_1HSG)

    assert respuesta.status_code == 201, respuesta.text
    pdb_id = respuesta.json()["target"]["pdb_id"]
    perfil = perfil_receptor.cargar(pdb_id)
    assert perfil["modo"] == "automatico" and perfil["camino"] == "A"
    entrada = perfil["entrada"]
    assert entrada["archivo"] == "1HSG.PDB.GZ" and entrada["comprimido"] is True and entrada["formato"] == "pdb"
    assert entrada["sha256"] != entrada["sha256_contenido"]
    # El original comprimido se conserva para poder comprobar su hash; el crudo es el descomprimido.
    assert path_for(f"targets/{pdb_id}/subida/original.pdb.gz").read_bytes() == comprimido
    assert path_for(f"targets/{pdb_id}/raw.pdb").read_text(encoding="utf-8") == \
        gzip.decompress(comprimido).decode("utf-8").replace("\r\n", "\n")
    informe = json.loads(path_for(respuesta.json()["target"]["prepared_file_path"][:-6] + ".report.json")
                         .read_text(encoding="utf-8"))
    assert informe["modo_de_preparacion"] == "automatico"
    assert informe["entrada"]["sha256"] == entrada["sha256"]
    assert informe["species_diff"]["state"] == "evaluado"


@pytest.mark.asyncio
async def test_una_cadena_que_no_existe_dice_cuales_hay_y_no_enseña_rutas(entorno):
    usuario = await entorno.user("ana")

    respuesta = _subir(entorno.client(usuario), HSG.read_bytes(), "1hsg.pdb.gz", is_curated="false",
                       **{**CAJA_1HSG}, **{"chain_id": "Z"})

    assert respuesta.status_code == 400, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["codigo"] == "CADENA_SIN_PROTEINA" and cuerpo["datos"]["cadenas"] == ["A", "B"]
    assert "«Z»" in cuerpo["detail"] and "A, B" in cuerpo["detail"]
    for fuga in ("\\", "vina", "mk_prepare", "Traceback", "STDERR"):
        assert fuga not in cuerpo["detail"], fuga


@pytest.mark.asyncio
async def test_solo_adn_no_es_un_receptor(entorno):
    from tests.receptores_propios_ayudas import linea_pdb

    usuario = await entorno.user("ana")
    adn = "\n".join(linea_pdb(i, "P", r, "A", i, (float(i), 0.0, 0.0), "P")
                    for i, r in enumerate(("DA", "DC", "DG", "DT"), start=1)) + "\nEND\n"

    respuesta = _subir(entorno.client(usuario), adn.encode(), "adn.pdb", is_curated="false", **CAJA_1HSG)

    assert respuesta.status_code == 400 and respuesta.json()["codigo"] == "SIN_PROTEINA"


@pytest.mark.asyncio
async def test_un_sdf_o_un_binario_o_un_mmcif_con_nombre_de_pdb_se_rechazan_con_motivo(entorno):
    usuario = await entorno.user("ana")
    cliente = entorno.client(usuario)
    caja = {"is_curated": "false", **CAJA_1HSG}

    sdf = _subir(cliente, b"x\n\n\n  0  0  0  0  0  0  0  0  0  0999 V2000\nM  END\n$$$$\n", "lig.sdf", **caja)
    binario = _subir(cliente, b"\x00\x01\x02" * 50, "x.pdb", **caja)
    mayusculas = _subir(cliente, b"HEADER x\n", "X.PDB", **caja)

    assert sdf.json()["codigo"] == "EXTENSION_ES_LIGANDO"
    assert binario.json()["codigo"] == "CONTENIDO_BINARIO"
    assert mayusculas.json()["codigo"] == "CONTENIDO_ILEGIBLE"   # la extensión en mayúsculas YA no es el motivo
    assert all(r.status_code == 400 for r in (sdf, binario, mayusculas))


# ── La paridad PDB ↔ mmCIF, con Meeko real ────────────────────────────────

DATOS_PROPIOS = Path(__file__).parent / "data" / "receptores_propios"
CAJA_8HFI = {"grid_center_x": "100.281", "grid_center_y": "100.843", "grid_center_z": "101.442",
             "grid_size_x": "30", "grid_size_y": "30", "grid_size_z": "30"}


@pytest.mark.asyncio
async def test_el_mismo_receptor_por_pdb_y_por_mmcif_da_el_mismo_receptor_preparado(entorno):
    """8HFI (recorte real del RCSB): los bytes del PDBQT que se acopla no dependen del formato de entrada."""
    from services.targets import perfil_receptor
    from utils.local_storage import path_for

    usuario = await entorno.user("ana")
    cliente = entorno.client(usuario)
    preparados, informes = {}, {}
    for nombre in ("8hfi_recortado.pdb", "8HFI_RECORTADO.CIF"):
        origen = DATOS_PROPIOS / nombre.lower()
        respuesta = _subir(cliente, origen.read_bytes(), nombre, is_curated="false", **CAJA_8HFI)
        assert respuesta.status_code == 201, respuesta.text
        destino = respuesta.json()["target"]
        ruta = destino["prepared_file_path"]
        preparados[nombre] = path_for(ruta).read_bytes()
        informes[nombre] = (destino["pdb_id"], json.loads(path_for(ruta[:-6] + ".report.json").read_text(encoding="utf-8")))

    assert preparados["8hfi_recortado.pdb"] == preparados["8HFI_RECORTADO.CIF"]
    (id_pdb, informe_pdb), (id_cif, informe_cif) = informes["8hfi_recortado.pdb"], informes["8HFI_RECORTADO.CIF"]
    assert informe_pdb["receptor_sha256"] == informe_cif["receptor_sha256"]
    for clave in ("removed_residues", "truncated_sidechains", "backbone_gaps", "protonation_templates"):
        assert informe_pdb[clave] == informe_cif[clave], clave
    # Lo único que distingue los dos informes es cómo llegó cada archivo.
    assert informe_pdb["entrada"]["formato"] == "pdb" and "conversion" not in informe_pdb["entrada"]
    conversion = informe_cif["entrada"]["conversion"]
    assert informe_cif["entrada"]["formato"] == "mmcif" and conversion["origen_formato"] == "mmcif"
    assert conversion["ensamblaje"]["estado"] == "aplicado" and conversion["cadenas"][0]["pdb"] == "A"
    assert perfil_receptor.cargar(id_cif)["entrada"]["conversion"] == conversion
    # El mmCIF conserva, aparte, su propio hash: la procedencia es la del archivo que subió la persona.
    assert path_for(f"targets/{id_cif}/raw.pdb").read_text(encoding="utf-8").startswith("EXPDTA")


@pytest.mark.asyncio
async def test_un_mmcif_vacio_o_roto_se_explica_con_su_codigo(entorno):
    usuario = await entorno.user("ana")
    cliente = entorno.client(usuario)
    vacio = _subir(cliente, b"data_X\n_entry.id X\n", "x.cif", is_curated="false", **CAJA_8HFI)
    roto = _subir(cliente, b"data_X\nloop_\n_atom_site.Cartn_x\n'sin cerrar\n", "x.mmcif", is_curated="false",
                  **CAJA_8HFI)

    assert vacio.status_code == roto.status_code == 400
    assert vacio.json()["codigo"] == "CONTENIDO_ILEGIBLE"
    assert roto.json()["codigo"] == "MMCIF_ILEGIBLE" and "x.mmcif" in roto.json()["detail"]


# ── Un PDBQT con su estructura de origen ──────────────────────────────────


def _subir_con_origen(cliente, pdbqt: bytes, nombre: str, origen: bytes, nombre_origen: str, **campos):
    datos = {"name": "con origen", "is_curated": "true", "chain_id": "A", **CAJA_8HFI, **campos}
    return cliente.post("/targets/upload", data=datos,
                        files={"file": (nombre, pdbqt), "source_file": (nombre_origen, origen)})


def _desplazar_x(pdb: str, delta: float) -> str:
    """El mismo PDB con todos los átomos movidos `delta` Å en x: la misma proteína en otro sitio."""
    lineas = []
    for l in pdb.splitlines():
        if l.startswith(("ATOM", "HETATM")):
            l = l[:30] + f"{float(l[30:38]) + delta:8.3f}" + l[38:]
        lineas.append(l)
    return "\n".join(lineas) + "\n"


def _pdbqt_de_8hfi_recortado(cliente) -> bytes:
    """El PDBQT que sacaría la preparación automática de MolDesign: lo que 'trae' un equipo."""
    from utils.local_storage import path_for

    origen = (DATOS_PROPIOS / "8hfi_recortado.pdb").read_bytes()
    respuesta = _subir(cliente, origen, "crudo.pdb", is_curated="false", **CAJA_8HFI)
    assert respuesta.status_code == 201, respuesta.text
    return path_for(respuesta.json()["target"]["prepared_file_path"]).read_bytes()


@pytest.mark.asyncio
async def test_con_origen_el_pdbqt_se_audita_hacia_el_pdb(entorno):
    from services.targets import perfil_receptor
    from utils.local_storage import path_for

    cliente = entorno.client(await entorno.user("ana"))
    pdbqt = _pdbqt_de_8hfi_recortado(cliente)
    origen = (DATOS_PROPIOS / "8hfi_recortado.pdb").read_bytes()

    respuesta = _subir_con_origen(cliente, pdbqt, "mi_receptor.pdbqt", origen, "8HFI_Origen.PDB")

    assert respuesta.status_code == 201, respuesta.text
    cuerpo = respuesta.json()
    assert "aviso_sin_origen" not in cuerpo
    pdb_id = cuerpo["target"]["pdb_id"]
    perfil = perfil_receptor.cargar(pdb_id)
    assert perfil["modo"] == "pdbqt" and perfil["origen"]["archivo"] == "8HFI_Origen.PDB"
    assert perfil["correspondencia"]["corresponde"] and perfil["correspondencia"]["cobertura"] == 1.0
    assert path_for(f"targets/{pdb_id}/raw.pdb").is_file()          # el origen es la fuente de la auditoría
    informe = json.loads(path_for(cuerpo["target"]["prepared_file_path"][:-6] + ".report.json")
                         .read_text(encoding="utf-8"))
    assert informe["modo_de_preparacion"] == "pdbqt_con_origen"
    # La auditoría completa, calculada del origen hacia el PDBQT.
    diff = informe["species_diff"]
    assert diff["state"] == "evaluado"
    retiradas = {f["name"] for f in diff["near_site"]["removed"]}
    assert "DSM" in retiradas and "HOH" in retiradas             # el ligando del cristal y las aguas del origen
    assert informe["removed_residues"] == [] and isinstance(informe["backbone_gaps"], list)
    assert informe["correspondencia_con_el_origen"]["corresponde"] is True
    assert "no_disponible" in informe and "species_diff" not in informe["no_disponible"]
    assert informe["origen"]["formato"] == "pdb"


@pytest.mark.asyncio
async def test_el_origen_en_mmcif_se_convierte_y_deja_su_conversion(entorno):
    from services.targets import perfil_receptor

    cliente = entorno.client(await entorno.user("ana"))
    pdbqt = _pdbqt_de_8hfi_recortado(cliente)

    respuesta = _subir_con_origen(cliente, pdbqt, "m.pdbqt", (DATOS_PROPIOS / "8hfi_recortado.cif").read_bytes(),
                                  "8hfi.cif")

    assert respuesta.status_code == 201, respuesta.text
    perfil = perfil_receptor.cargar(respuesta.json()["target"]["pdb_id"])
    assert perfil["origen"]["formato"] == "mmcif" and perfil["origen"]["conversion"]["ensamblaje"]["usado"] == "1"


@pytest.mark.asyncio
async def test_un_origen_que_no_es_el_del_pdbqt_se_rechaza_con_la_medida_y_sin_dejar_rastro(entorno):
    from tests.receptores_propios_ayudas import pdb_sintetico
    from utils.local_storage import data_dir

    cliente = entorno.client(await entorno.user("ana"))
    pdbqt = _pdbqt_de_8hfi_recortado(cliente)
    antes = {p.name for p in (data_dir() / "targets").iterdir()}

    otro = _subir_con_origen(cliente, pdbqt, "m.pdbqt", pdb_sintetico(residuos=40).encode(), "otra.pdb")
    movido = _subir_con_origen(cliente, pdbqt, "m.pdbqt", _desplazar_x((DATOS_PROPIOS / "8hfi_recortado.pdb")
                                                                      .read_text(encoding="utf-8"), 8.0).encode(),
                               "movido.pdb")

    for respuesta in (otro, movido):
        assert respuesta.status_code == 400 and respuesta.json()["codigo"] == "PDBQT_NO_CORRESPONDE_AL_ORIGEN"
        assert "correspondencia" in respuesta.json()["datos"]
    assert {p.name for p in (data_dir() / "targets").iterdir()} == antes          # nada a medias


@pytest.mark.asyncio
async def test_el_origen_solo_vale_con_pdbqt_y_no_puede_ser_otro_pdbqt(entorno):
    cliente = entorno.client(await entorno.user("ana"))
    pdbqt = _pdbqt_de_8hfi_recortado(cliente)
    origen_pdb = (DATOS_PROPIOS / "8hfi_recortado.pdb").read_bytes()

    otro_pdbqt = _subir_con_origen(cliente, pdbqt, "m.pdbqt", pdbqt, "origen.pdbqt")
    en_crudo = _subir_con_origen(cliente, origen_pdb, "crudo.pdb", origen_pdb, "origen.pdb", is_curated="false")

    assert otro_pdbqt.json()["codigo"] == "ORIGEN_ES_PDBQT"
    assert en_crudo.status_code == 400 and en_crudo.json()["codigo"] == "ORIGEN_SOLO_CON_PDBQT"


# ── Cadenas de varias letras y códigos CCD de cinco caracteres, por la API ──


def _cif_cadenas_largas() -> bytes:
    from tests.receptores_propios_ayudas import mmcif_sintetico, residuo_ala, residuo_hetero

    def apilar(n, dy):
        nombre, num, het, ats = residuo_ala(n)
        return (nombre, num, het, [(a, e, (x, y + dy, z), alt, occ) for a, e, (x, y, z), alt, occ in ats])

    cadenas = [
        {"auth": "AAA", "label": "A", "residuos": [apilar(n, 0.0) for n in range(1, 40)]},
        {"auth": "B1", "label": "B", "residuos": [apilar(n, 40.0) for n in range(1, 40)]},
        {"auth": "AAA", "label": "L1", "polimero": False, "residuos": [residuo_hetero("A1D5J", 401, (50.0, 0.0, 0.0))]},
        {"auth": "AAA", "label": "L2", "polimero": False, "residuos": [residuo_hetero("A1D67", 402, (60.0, 0.0, 0.0))]},
    ]
    return mmcif_sintetico(cadenas).encode()


@pytest.mark.asyncio
async def test_se_pide_la_cadena_del_archivo_y_el_receptor_usa_la_letra_con_la_correspondencia_declarada(entorno):
    from services.targets import perfil_receptor

    cliente = entorno.client(await entorno.user("ana"))
    caja = {"grid_center_x": "60", "grid_center_y": "0", "grid_center_z": "0",
            "grid_size_x": "30", "grid_size_y": "30", "grid_size_z": "30"}

    respuesta = _subir(cliente, _cif_cadenas_largas(), "sintetico.cif", is_curated="false", chain_id="AAA", **caja)

    assert respuesta.status_code == 201, respuesta.text
    destino = respuesta.json()["target"]
    assert destino["chain"] == "A"                                     # la letra con la que se prepara
    conversion = perfil_receptor.cargar(destino["pdb_id"])["entrada"]["conversion"]
    assert [(c["original"], c["pdb"]) for c in conversion["cadenas"]] == [("AAA", "A"), ("B1", "B")]
    assert {r["original"] for r in conversion["residuos_renombrados"]} == {"A1D5J", "A1D67"}
    assert len({r["pdb"] for r in conversion["residuos_renombrados"]}) == 2     # no se fundieron


@pytest.mark.asyncio
async def test_una_cadena_que_no_esta_lista_los_nombres_originales_no_las_letras_internas(entorno):
    cliente = entorno.client(await entorno.user("ana"))
    caja = {"grid_center_x": "60", "grid_center_y": "0", "grid_center_z": "0"}

    respuesta = _subir(cliente, _cif_cadenas_largas(), "sintetico.cif", is_curated="false", chain_id="ZZZ", **caja)

    assert respuesta.status_code == 400
    cuerpo = respuesta.json()
    assert cuerpo["codigo"] == "CADENA_SIN_PROTEINA" and cuerpo["datos"]["cadenas"] == ["AAA", "B1"]
    assert "AAA, B1" in cuerpo["detail"]
