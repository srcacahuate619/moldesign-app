"""Camino B: un receptor que el equipo YA preparó se respeta (protonación, aguas, metales, cofactores).

El fixture es un recorte REAL de 8HFI protonado con PDBFixer (OpenMM) con 8 aguas del cristal y el cloruro
(ver `8hfi_protonado_origen.json`). Las pruebas pasan por la API con Meeko real: lo que se verifica es lo que se
entrega, no sólo el código.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import pytest_asyncio

from tests.receptores_propios_ayudas import aislar_almacen, linea_pdb
from tests.test_target_authorization import _Environment

DATOS = Path(__file__).parent / "data" / "receptores_propios"
PROTONADO = (DATOS / "8hfi_protonado.pdb").read_text(encoding="utf-8")
CAJA_8HFI = {"grid_center_x": "100.281", "grid_center_y": "100.843", "grid_center_z": "101.442",
             "grid_size_x": "30", "grid_size_y": "30", "grid_size_z": "30"}


@pytest_asyncio.fixture
async def entorno(tmp_path, monkeypatch):
    aislar_almacen(monkeypatch, tmp_path / "almacen")
    env = _Environment(tmp_path / "targets.db")
    await env.start()
    try:
        yield env
    finally:
        await env.close()


def _subir(cliente, contenido: str, nombre: str = "equipo.pdb", modo: str = "respetar", **campos):
    datos = {"name": "preparado por el equipo", "is_curated": "false", "modo_preparacion": modo,
             "chain_id": "A", **CAJA_8HFI, **campos}
    return cliente.post("/targets/upload", data=datos, files={"file": (nombre, contenido.encode())})


def _informe(respuesta) -> tuple[str, dict, str]:
    from utils.local_storage import path_for

    destino = respuesta.json()["target"]
    ruta = destino["prepared_file_path"]
    informe = json.loads(path_for(ruta[:-6] + ".report.json").read_text(encoding="utf-8"))
    return destino["pdb_id"], informe, path_for(ruta).read_text(encoding="utf-8")


def _residuos(pdbqt: str) -> set[str]:
    return {l[17:20].strip() for l in pdbqt.splitlines() if l.startswith(("ATOM", "HETATM"))}


def _charmm(texto: str) -> str:
    return (texto.replace(" HID ", " HSD ").replace(" HIE ", " HSE ").replace(" HIP ", " HSP ")
            .replace(" HOH ", " WAT "))


@pytest.mark.asyncio
async def test_se_conserva_lo_que_el_equipo_decidio_y_la_protonacion_declarada_se_comprueba(entorno):
    cliente = entorno.client(await entorno.user("ana"))

    respeta = _subir(cliente, PROTONADO)
    automatico = _subir(cliente, PROTONADO, modo="automatico")

    assert respeta.status_code == 201, respeta.text
    assert automatico.status_code == 201, automatico.text
    _, informe, pdbqt = _informe(respeta)
    _, informe_auto, pdbqt_auto = _informe(automatico)
    # Las aguas y el cloruro que el equipo dejó siguen en el receptor; la receta automática los retira.
    assert {"HOH", "CL"} <= _residuos(pdbqt)
    assert not ({"HOH", "CL"} & _residuos(pdbqt_auto))
    assert informe["modo_de_preparacion"] == "respetar"
    declarada = informe["protonacion_declarada"]
    assert declarada["origen"] == "usuario" and declarada["plantillas_coinciden"] is True
    assert declarada["plantillas_declaradas"] == 4                       # las cuatro histidinas HID
    assert {f["template"] for f in informe["protonation_templates"].values() if f["input_resname"] == "HID"} == {"HID"}
    diff = informe["species_diff"]
    assert diff["state"] == "evaluado" and diff["removed"]["waters"] == 0 and diff["removed"]["metals"] == 0
    assert informe_auto["species_diff"]["removed"]["waters"] > 0       # lo que el modo automático sí tira
    assert informe["traducciones"] == [] and informe["cofactors_outside_site"] == []


@pytest.mark.asyncio
async def test_los_nombres_de_charmm_y_wat_se_traducen_y_se_declaran_con_el_mismo_receptor(entorno):
    cliente = entorno.client(await entorno.user("ana"))

    amber = _subir(cliente, PROTONADO)
    charmm = _subir(cliente, _charmm(PROTONADO))

    assert charmm.status_code == 201, charmm.text
    _, informe_amber, pdbqt_amber = _informe(amber)
    _, informe, pdbqt = _informe(charmm)
    assert pdbqt == pdbqt_amber                                         # el mismo receptor, byte a byte
    assert informe["receptor_sha256"] == informe_amber["receptor_sha256"]
    assert informe["traducciones"] == [
        {"original": "HSD", "pdb": "HID", "residuos": 4},
        {"original": "WAT", "pdb": "HOH", "residuos": 8},
    ]
    assert informe["protonacion_declarada"]["traducciones"] == informe["traducciones"]


def _his(texto: str) -> str:
    return texto.replace(" HID ", " HIS ").replace(" HIE ", " HIS ").replace(" HIP ", " HIS ")


@pytest.mark.asyncio
async def test_el_modo_automatico_conserva_las_histidinas_hsd_como_his_y_lo_declara(entorno):
    """La receta automática borraba las histidinas de un archivo con nombres de CHARMM (Meeko no conoce HSD).

    Ahora la subida traduce HSD/HSE/HSP → HIS y WAT → HOH antes de prepararlo: el receptor es, byte a byte, el
    del mismo archivo con nombres estándar, y la traducción queda declarada en «Archivo del receptor».
    """
    cliente = entorno.client(await entorno.user("ana"))

    charmm = _subir(cliente, _charmm(PROTONADO), modo="automatico")
    estandar = _subir(cliente, _his(PROTONADO), modo="automatico")

    assert charmm.status_code == 201, charmm.text
    assert estandar.status_code == 201, estandar.text
    pdb_id, informe, pdbqt = _informe(charmm)
    _, informe_estandar, pdbqt_estandar = _informe(estandar)
    assert not [r for r in informe["removed_residues"] if r["name"] in {"HSD", "HSE", "HSP"}]
    assert pdbqt == pdbqt_estandar and informe["receptor_sha256"] == informe_estandar["receptor_sha256"]
    assert informe["entrada"]["normalizacion"]["nombres_charmm"] == [
        {"original": "HSD", "pdb": "HIS", "residuos": 4},
        {"original": "WAT", "pdb": "HOH", "residuos": 8},
    ]
    from services.dossier.preparacion_entrada import partes_de_entrada
    assert "nombres de residuo traducidos: HSD → HIS (4), WAT → HOH (8)" in partes_de_entrada(informe)


def test_la_traduccion_de_charmm_no_toca_un_pdb_estandar():
    from services.targets.normalizar_pdb import nombres_charmm_a_pdb

    assert nombres_charmm_a_pdb(_his(PROTONADO)) == (_his(PROTONADO), [])


def _con_hetero(base: str, linea: str) -> str:
    return base.replace("\nEND\n", "\n" + linea + "\nEND\n")


@pytest.mark.asyncio
async def test_un_sodio_junto_al_sitio_se_abstiene_con_su_motivo_y_lejos_se_retira_y_se_declara(entorno):
    cliente = entorno.client(await entorno.user("ana"))
    cerca = linea_pdb(9001, "NA", "NA", "A", 901, (100.0, 100.0, 101.0), "NA", registro="HETATM")
    lejos = linea_pdb(9002, "NA", "NA", "A", 902, (160.0, 160.0, 160.0), "NA", registro="HETATM")

    junto = _subir(cliente, _con_hetero(PROTONADO, cerca))
    aparte = _subir(cliente, _con_hetero(PROTONADO, lejos))

    assert junto.status_code == 400
    cuerpo = junto.json()
    assert cuerpo["codigo"] == "ESPECIE_NO_REPRESENTABLE" and "NA A:901" in cuerpo["detail"]
    assert "nitrógeno aceptor" in cuerpo["detail"] + json.dumps(cuerpo["datos"], ensure_ascii=False)
    assert aparte.status_code == 201, aparte.text
    _, informe, pdbqt = _informe(aparte)
    assert "NA" not in _residuos(pdbqt)
    fuera = informe["cofactors_outside_site"]
    assert [(f["name"], f["chain"], f["residue_number"], f["action"]) for f in fuera] == [("NA", "A", "902", "retirado")]


@pytest.mark.asyncio
async def test_un_residuo_sin_plantilla_junto_al_sitio_tampoco_se_adivina(entorno):
    cliente = entorno.client(await entorno.user("ana"))
    raro = linea_pdb(9003, "C1", "LIG", "A", 903, (100.0, 100.0, 101.0), "C", registro="HETATM")

    respuesta = _subir(cliente, _con_hetero(PROTONADO, raro))

    assert respuesta.status_code == 400 and respuesta.json()["codigo"] == "ESPECIE_NO_REPRESENTABLE"
    assert "LIG A:903" in respuesta.json()["detail"]


@pytest.mark.asyncio
async def test_el_catalogo_y_el_modo_automatico_siguen_retirando_las_aguas(entorno):
    """Control negativo del arreglo: el modo nuevo no cambió la receta de siempre."""
    cliente = entorno.client(await entorno.user("ana"))

    automatico = _subir(cliente, PROTONADO, modo="automatico")

    _, informe, pdbqt = _informe(automatico)
    assert informe["modo_de_preparacion"] == "automatico" and "protonacion_declarada" not in informe
    assert "HOH" not in _residuos(pdbqt)


@pytest.mark.asyncio
async def test_un_modo_que_no_existe_o_que_no_cuadra_con_la_subida_se_explica(entorno):
    cliente = entorno.client(await entorno.user("ana"))

    raro = _subir(cliente, PROTONADO, modo="magico")
    pdbqt_como_crudo = _subir(cliente, PROTONADO, modo="pdbqt")

    for respuesta in (raro, pdbqt_como_crudo):
        assert respuesta.status_code == 400 and respuesta.json()["codigo"] == "MODO_INCOHERENTE"


@pytest.mark.asyncio
async def test_cym_es_el_tiolato_y_meeko_lo_llama_cyx_menos_se_declara_y_se_comprueba(entorno):
    """El encargo suponía que Meeko no tenía CYM; en 0.7.1 existe como alias de la plantilla del tiolato (CYX-)."""
    cliente = entorno.client(await entorno.user("ana"))
    lineas = []
    for l in PROTONADO.splitlines():
        if l.startswith("ATOM") and l[22:26].strip() == "86" and l[17:20] == "CYS":
            if l[12:16].strip() == "HG":
                continue
            l = l[:17] + "CYM" + l[20:]
        lineas.append(l)

    respuesta = _subir(cliente, "\n".join(lineas) + "\n")

    assert respuesta.status_code == 201, respuesta.text
    _, informe, _ = _informe(respuesta)
    assert informe["protonation_templates"]["A:86"] == {"input_resname": "CYM", "template": "CYX-"}
    assert informe["protonacion_declarada"]["plantillas_declaradas"] == 5       # 4 HID + 1 CYM


# ── Las piezas, una a una: cada una con lo que debe detectar y lo que no ──


class TestPiezas:
    def test_traducir_residuos_cuenta_residuos_no_atomos_y_no_toca_lo_demas(self):
        from services.docking.preparer_respetando import traducir_residuos

        texto, traducciones = traducir_residuos(_charmm(PROTONADO))

        assert traducciones == [{"original": "HSD", "pdb": "HID", "residuos": 4},
                                {"original": "WAT", "pdb": "HOH", "residuos": 8}]
        assert texto == PROTONADO.replace("\r", "")
        assert traducir_residuos(PROTONADO) == (PROTONADO, [])

    def test_el_filtro_conserva_aguas_y_metales_y_deja_fuera_otras_cadenas_y_ligandos_de_otras_cadenas(self):
        from services.docking.preparer_respetando import filtrar_respetando

        extra = "\n".join([
            linea_pdb(9100, "CA", "ALA", "B", 1, (0.0, 0.0, 0.0), "C"),                          # otra cadena
            linea_pdb(9101, "ZN", "ZN", "B", 2, (100.0, 100.0, 101.0), "ZN", registro="HETATM"),  # ion de esa cadena
            linea_pdb(9102, "O", "HOH", "W", 3, (101.0, 100.0, 101.0), "O", registro="HETATM"),   # agua en su cadena, cerca
            linea_pdb(9103, "O", "HOH", "W", 4, (190.0, 190.0, 190.0), "O", registro="HETATM"),   # agua en su cadena, lejos
        ])
        texto = _con_hetero(PROTONADO, extra)

        filtrado, info = filtrar_respetando(texto, {"A"}, (100.281, 100.843, 101.442), (30.0, 30.0, 30.0))

        nombres = {(l[21], l[17:20].strip()) for l in filtrado.splitlines() if l.startswith(("ATOM", "HETATM"))}
        assert ("A", "HOH") in nombres and ("A", "CL") in nombres
        assert ("W", "HOH") in nombres                   # la cadena W no tiene proteína: entra lo que está junto al sitio
        assert ("B", "ALA") not in nombres and ("B", "ZN") not in nombres
        assert info["hetero_de_cadenas_sin_proteina"] == 1
        assert sum(1 for l in filtrado.splitlines() if l[21:22] == "W") == 1       # la lejana no

    def test_el_filtro_resuelve_los_altlocs_como_el_catalogo(self):
        from services.docking.preparer_respetando import filtrar_respetando

        base = [l for l in PROTONADO.splitlines() if l.startswith("ATOM")][:5]
        a = [l[:16] + "A" + l[17:54] + "  0.60" + l[60:] for l in base]
        b = [l[:16] + "B" + l[17:54] + "  0.40" + l[60:] for l in base]

        filtrado, _ = filtrar_respetando("\n".join(a + b) + "\n", {"A"}, (0.0, 0.0, 0.0), (20.0, 20.0, 20.0))

        assert len([l for l in filtrado.splitlines() if l.startswith("ATOM")]) == 5
        assert all(l[16] == " " and l[54:60] == "  0.60" for l in filtrado.splitlines() if l.startswith("ATOM"))

    def test_clasifica_lo_que_no_se_puede_representar(self):
        from services.docking.preparer_respetando import especies_sin_representacion

        texto = "\n".join([
            linea_pdb(1, "NA", "NA", "A", 1, (0.0, 0.0, 0.0), "NA", registro="HETATM"),     # sodio
            linea_pdb(2, "K", "K", "A", 2, (0.0, 0.0, 0.0), "K", registro="HETATM"),         # potasio: sin radio covalente
            linea_pdb(3, "C1", "LIG", "A", 3, (50.0, 0.0, 0.0), "C", registro="HETATM"),     # sin plantilla, lejos
            linea_pdb(4, "ZN", "ZN", "A", 4, (0.0, 0.0, 0.0), "ZN", registro="HETATM"),      # con plantilla
            linea_pdb(5, "O", "HOH", "A", 5, (0.0, 0.0, 0.0), "O", registro="HETATM"),       # con plantilla
            linea_pdb(6, "CA", "CYM", "A", 6, (0.0, 0.0, 0.0), "C"),                          # con plantilla (alias)
        ])

        filas = especies_sin_representacion(texto, (0.0, 0.0, 0.0), (10.0, 10.0, 10.0))

        assert [(f["name"], f["motivo"]) for f in filas] == [("NA", "sodio"), ("K", "sin_radio"), ("LIG", "sin_plantilla")]
        assert [f["distance_to_box_A"] for f in filas if f["name"] == "LIG"] == [45.0]

    def test_la_comprobacion_de_protonacion_ve_el_cambio_y_acepta_variantes_terminales_y_el_alias_de_cym(self):
        from services.docking.preparer_respetando import _comprobar_protonacion

        _, cambiadas = _comprobar_protonacion({
            "A:1": {"input_resname": "HID", "residue_template_key": "HIE"},        # lo que Meeko no puede hacer
            "A:2": {"input_resname": "ASH", "residue_template_key": "ASP"},
        })
        _, bien = _comprobar_protonacion({
            "A:1": {"input_resname": "HID", "residue_template_key": "HID"},
            "A:2": {"input_resname": "HIE", "residue_template_key": "NHIE"},       # N-terminal
            "A:3": {"input_resname": "CYM", "residue_template_key": "CYX-"},        # alias
            "A:4": {"input_resname": "HIS", "residue_template_key": "HID"},         # sin declarar: lo decide Meeko
            "A:5": {"input_resname": "LYN", "residue_template_key": "CLYN"},
        })

        assert cambiadas == ["A:1 HID → HIE", "A:2 ASH → ASP"] and bien == []

    def test_un_residuo_con_protonacion_declarada_e_incompleto_se_trunca_en_vez_de_perderse(self):
        from services.docking.preparer_respetando import truncar_respetando

        lineas = [l for l in PROTONADO.splitlines() if l.startswith("ATOM") and l[22:26].strip() == "178"]
        quitar = {"NE2", "CD2", "CE1", "ND1", "HD1", "HD2", "HE1"}
        incompleto = [l for l in lineas if l[12:16].strip() not in quitar]

        texto, filas = truncar_respetando("\n".join(incompleto) + "\n", (100.0, 100.0, 101.0), (30.0, 30.0, 30.0))

        assert [(f["name"], f["action"]) for f in filas] == [("HID", "truncado a ALA")]
        assert {l[17:20] for l in texto.splitlines()} == {"ALA"}
        completo, sin_filas = truncar_respetando("\n".join(lineas) + "\n", (100.0, 100.0, 101.0), (30.0, 30.0, 30.0))
        assert sin_filas == [] and {l[17:20] for l in completo.splitlines()} == {"HID"}   # lo completo conserva su variante

    def test_la_receta_depende_de_la_caja_las_cadenas_y_el_archivo(self):
        from services.docking.preparer_respetando import receta_respetando

        caja = ((1.0, 2.0, 3.0), (20.0, 20.0, 20.0))
        base = receta_respetando(PROTONADO, {"A"}, *caja)

        assert base == receta_respetando(PROTONADO, {"A"}, *caja)
        assert base != receta_respetando(PROTONADO + " ", {"A"}, *caja)
        assert base != receta_respetando(PROTONADO, {"B"}, *caja)
        assert base != receta_respetando(PROTONADO, {"A"}, (1.0, 2.0, 4.0), caja[1])


# ── La comprobación previa y Preparación de un receptor respetado ─────────


def _preflight_de(pdb_id: str, destino: dict):
    from services.docking.preflight import build_preflight

    return build_preflight(
        smiles="CNCCCN1c2ccccc2CCc2ccccc21", target_pdb_id=pdb_id, chain=destino["chain"],
        target_origin="privado", target_reference=None, grid_center=None, grid_size=None,
        custom_hotspots=None,
        catalog_grid_center=(destino["grid_center_x"], destino["grid_center_y"], destino["grid_center_z"]),
        catalog_grid_size=(destino["grid_size_x"], destino["grid_size_y"], destino["grid_size_z"]),
        catalog_hotspots=[], cofactors_whitelist=[], site_chains=destino.get("site_chains"),
        site_ligand=destino.get("site_ligand"), calibracion=None,
    )


def _controles(informe: dict) -> dict:
    return {c["code"]: c for c in informe["controls"]}


@pytest.mark.asyncio
async def test_la_comprobacion_previa_describe_la_ruta_que_se_ejecuta_y_la_protonacion_declarada(entorno):
    cliente = entorno.client(await entorno.user("ana"))
    respuesta = _subir(cliente, PROTONADO)
    destino = respuesta.json()["target"]

    informe = _preflight_de(destino["pdb_id"], destino)

    controles = _controles(informe)
    # (el motor de docking no está configurado en la suite: ése es el único bloqueante, y no es del receptor)
    assert set(informe["technical_blockers"]) <= {"MOTOR_DOCKING_DISPONIBLE"}
    assert informe["receptor"]["modo_de_preparacion"] == "respetar"
    assert "ya preparado por el usuario" in controles["POLITICA_HETEROATOMOS"]["observation"]
    assert "sin lista blanca" in controles["POLITICA_HETEROATOMOS"]["observation"]
    assert controles["RECEPTOR_PREPARADO_DISPONIBLE"]["state"] == "pasa"       # el mismo hash de receta que se ejecutó
    protonacion = controles["RECEPTOR_PROTONACION_DECLARADA"]
    assert protonacion["state"] == "advertencia" and "4 residuo(s)" in protonacion["observation"]
    assert "Meeko aplicó exactamente esas plantillas" in protonacion["observation"]
    # El diff es el del archivo traducido: no cuenta WAT→HOH como especie retirada.
    assert controles["ESPECIES_DEL_SITIO_RETIRADAS"]["state"] == "pasa"


@pytest.mark.asyncio
async def test_la_comprobacion_previa_bloquea_una_especie_sin_representacion_junto_al_sitio(entorno):
    from utils.local_storage import path_for

    cliente = entorno.client(await entorno.user("ana"))
    destino = _subir(cliente, PROTONADO).json()["target"]
    raw = path_for(f"targets/{destino['pdb_id']}/raw.pdb")
    sodio = linea_pdb(9001, "NA", "NA", "A", 901, (100.0, 100.0, 101.0), "NA", registro="HETATM")
    raw.write_text(_con_hetero(raw.read_text(encoding="utf-8"), sodio), encoding="utf-8")

    informe = _preflight_de(destino["pdb_id"], destino)

    control = _controles(informe)["ESPECIES_SIN_REPRESENTACION"]
    assert control["state"] == "bloquea" and "NA A:901" in control["observation"]
    assert "ESPECIES_SIN_REPRESENTACION" in informe["technical_blockers"]
    assert "COFACTOR_TEMPLATE_NO_DISPONIBLE" not in _controles(informe)


@pytest.mark.asyncio
async def test_preparacion_dice_de_quien_es_la_protonacion_y_las_aguas_en_los_dos_idiomas(entorno):
    import copy

    from services.dossier.localization import traducir_dossier
    from tests.fixtures_dossier import caso_completo
    from tests.test_dossier_en_ingles_completo import _parece_espanol
    from tests.test_preparacion_auditoria import _PROCEDENCIA, _auditar

    cliente = entorno.client(await entorno.user("ana"))
    _, informe, _ = _informe(_subir(cliente, _charmm(PROTONADO)))
    caso = caso_completo()
    procedencia = copy.deepcopy(_PROCEDENCIA)
    procedencia["receptor_prep"] = {**informe, "chain": "A", "site_chains": ["A"]}
    caso["eval_result"].docking_protocol = {**caso["eval_result"].docking_protocol, "execution_provenance": procedencia}

    auditoria = _auditar(caso)
    en = traducir_dossier(auditoria, "en")

    def req(a, clave):
        return next(r for b in a["bloques"] for r in b["requisitos"] if r["clave"] == clave)

    assert req(auditoria, "receptor.protonacion")["valor"] == "Declarada por el usuario (origen: usuario)"
    assert "nombres de residuo traducidos: HSD → HID (4), WAT → HOH (8)" in req(auditoria, "receptor.entrada")["valor"]
    assert req(auditoria, "entorno.aguas")["estado"] == "REGISTRADO" and "8 conservada(s)" in req(auditoria, "entorno.aguas")["valor"]
    for clave in ("receptor.protonacion", "receptor.entrada", "entorno.aguas", "entorno.metales_cofactores"):
        for campo in ("valor", "razon"):
            texto = req(en, clave).get(campo)
            assert not texto or not _parece_espanol(texto), (clave, campo, texto)
    assert "residue names translated: HSD → HID (4), WAT → HOH (8)" in req(en, "receptor.entrada")["valor"]
    assert req(en, "entorno.aguas")["valor"].endswith("8 kept")


@pytest.mark.asyncio
async def test_una_variante_de_un_receptor_respetado_se_prepara_igual_respetandolo(entorno):
    from services.targets import perfil_receptor

    cliente = entorno.client(await entorno.user("ana"))
    padre = _subir(cliente, PROTONADO).json()["target"]

    variante = cliente.post(f"/targets/{padre['pdb_id']}/variants", json={
        "name": "otra caja", "grid_size": [28.0, 28.0, 28.0]})

    assert variante.status_code == 201, variante.text
    hijo = variante.json()
    assert hijo["pdb_id"] != padre["pdb_id"]
    assert perfil_receptor.cargar(hijo["pdb_id"])["modo"] == "respetar"
    assert hijo["preparation_recipe"]["mode"] == "respect_user_preparation"
    from utils.local_storage import path_for

    preparados = sorted(path_for(f"targets/{hijo['pdb_id']}").glob("prepared-*.pdbqt"))
    assert len(preparados) == 1
    assert {"HOH", "CL"} <= _residuos(preparados[0].read_text(encoding="utf-8"))   # las aguas del equipo viajan


@pytest.mark.asyncio
async def test_un_pqr_da_el_mismo_receptor_que_su_pdb_y_declara_que_las_cargas_no_se_usan(entorno):
    import copy

    from services.dossier.localization import traducir_dossier
    from tests.fixtures_dossier import caso_completo
    from tests.test_dossier_en_ingles_completo import _parece_espanol
    from tests.test_lector_pqr import a_pqr
    from tests.test_preparacion_auditoria import _PROCEDENCIA, _auditar

    cliente = entorno.client(await entorno.user("ana"))

    desde_pdb = _subir(cliente, PROTONADO)
    desde_pqr = _subir(cliente, a_pqr(PROTONADO, estilo="campos"), nombre="equipo.PQR")

    assert desde_pqr.status_code == 201, desde_pqr.text
    _, informe_pdb, pdbqt_pdb = _informe(desde_pdb)
    _, informe, pdbqt = _informe(desde_pqr)
    assert pdbqt == pdbqt_pdb and informe["receptor_sha256"] == informe_pdb["receptor_sha256"]
    pqr = informe["entrada"]["pqr"]
    assert informe["entrada"]["formato"] == "pqr" and pqr["cargas_y_radios_descartados"] == pqr["atomos"] > 0
    assert informe["protonacion_declarada"]["formato_del_archivo"] == "pqr"

    caso = caso_completo()
    procedencia = copy.deepcopy(_PROCEDENCIA)
    procedencia["receptor_prep"] = {**informe, "chain": "A", "site_chains": ["A"]}
    caso["eval_result"].docking_protocol = {**caso["eval_result"].docking_protocol, "execution_provenance": procedencia}
    auditoria = _auditar(caso)
    valor = next(r for b in auditoria["bloques"] for r in b["requisitos"] if r["clave"] == "receptor.entrada")["valor"]
    en = next(r for b in traducir_dossier(auditoria, "en")["bloques"] for r in b["requisitos"]
              if r["clave"] == "receptor.entrada")["valor"]
    assert "convertido de PQR a PDB clásico" in valor and "(Vina no los usa)" in valor
    assert "PQR charges and radii discarded" in en and "(Vina does not use them)" in en
    assert not _parece_espanol(en), en


@pytest.mark.asyncio
async def test_un_pdb_con_extension_pqr_o_al_reves_se_rechaza_con_motivo(entorno):
    cliente = entorno.client(await entorno.user("ana"))

    pdb_como_pqr = _subir(cliente, PROTONADO, nombre="equipo.pqr")

    assert pdb_como_pqr.status_code == 400 and pdb_como_pqr.json()["codigo"] == "PQR_LINEA_ILEGIBLE"


@pytest.mark.asyncio
async def test_un_pqr_real_de_pdb2pqr_amber_se_prepara_respetando_y_declara_lo_que_no_trae(entorno):
    """Salida real de PDB2PQR 3.7.1 (AMBER, PROPKA a pH 7,4) sobre el recorte de 8HFI: ver pdb2pqr_procedencia.json."""
    cliente = entorno.client(await entorno.user("ana"))
    texto = (DATOS / "8hfi_recortado_amber.pqr").read_text(encoding="utf-8")

    respuesta = _subir(cliente, texto, nombre="8hfi_amber.pqr")

    assert respuesta.status_code == 201, respuesta.text
    _, informe, pdbqt = _informe(respuesta)
    pqr = informe["entrada"]["pqr"]
    assert informe["entrada"]["formato"] == "pqr" and informe["modo_de_preparacion"] == "respetar"
    assert pqr["atomos"] == 744 == pqr["cargas_y_radios_descartados"]
    assert informe["protonacion_declarada"]["origen"] == "usuario"
    assert informe["protonacion_declarada"]["plantillas_coinciden"] is True
    assert "ATOM" in pdbqt                                                # Meeko escribió un receptor, no un vacío


@pytest.mark.asyncio
async def test_un_pqr_real_de_charmm_se_rechaza_con_el_motivo_la_accion_y_los_sitios(entorno):
    cliente = entorno.client(await entorno.user("ana"))
    texto = (DATOS / "8hfi_recortado_charmm.pqr").read_text(encoding="utf-8")

    respuesta = cliente.post("/targets/upload", data={
        "name": "charmm", "is_curated": "false", "modo_preparacion": "respetar", "chain_id": "A", **CAJA_8HFI},
        files={"file": ("8hfi_charmm.pqr", texto.encode())})

    cuerpo = respuesta.json()
    assert respuesta.status_code == 400 and cuerpo["codigo"] == "PQR_PARCHES_CHARMM"
    assert cuerpo["datos"]["parches"] == {"TER": ["A:105"]}
    assert "--ffout=AMBER" in cuerpo["detail"] and "«TER»" in cuerpo["detail"]
    assert "\\" not in cuerpo["detail"] and ":/" not in cuerpo["detail"]            # sin rutas del disco
    # El inglés sale del mismo error: el router lo elige por el idioma de la petición (lo cubre el arnés de la API).
    from services.targets.lector_pqr import pqr_a_pdb
    from services.targets.errores_subida import ErrorDeSubida
    with pytest.raises(ErrorDeSubida) as error:
        pqr_a_pdb(texto, "8hfi_charmm.pqr")
    assert "CHARMM patches" in error.value.mensaje("en") and "--ffout=AMBER" in error.value.mensaje("en")
