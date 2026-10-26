"""Camino C: un PDBQT listo para Vina se evalúa tal cual, y se audita si trae su origen.

Cada prueba trae casos que el lector DEBE detectar y casos que NO debe tocar: un
guardián que sólo muestra que acepta lo bueno no demuestra que ve lo malo.
"""

from __future__ import annotations

import json

import pytest

from services.docking.preparer_propio import (
    construir_informe,
    pdbqt_como_pdb,
    preparar_pdbqt,
    receta_pdbqt,
)
from services.targets import perfil_receptor
from services.targets.errores_subida import ErrorDeSubida
from services.targets.pdbqt_propio import (
    TIPOS_ACEPTADOS,
    analizar_pdbqt,
    correspondencia,
    exigir_correspondencia,
    sha256_de,
)
from tests.receptores_propios_ayudas import (
    aislar_almacen,
    cadena_de_alaninas,
    linea_pdbqt,
    pdb_sintetico,
    pdbqt_sintetico,
)


# ── El lector del PDBQT ──────────────────────────────────────────────────


class TestAnalizarPdbqt:
    def test_un_pdbqt_de_receptor_valido_se_resume(self):
        resumen = analizar_pdbqt(pdbqt_sintetico(residuos=30))

        assert resumen.atomos == 180 and resumen.pesados == 150 and resumen.hidrogenos == 30
        assert resumen.cadenas == ["A"] and resumen.residuos == 30
        assert resumen.tipos == {"N": 30, "C": 90, "OA": 30, "HD": 30}
        assert resumen.avisos == []

    @pytest.mark.parametrize("registro", ["ROOT", "ENDROOT", "BRANCH   1   2", "TORSDOF 5", "BEGIN_RES ALA A   1"])
    def test_un_registro_de_ligando_o_de_residuos_flexibles_se_rechaza_con_su_linea(self, registro):
        texto = pdbqt_sintetico(residuos=30) + registro + "\n"

        with pytest.raises(ErrorDeSubida) as error:
            analizar_pdbqt(texto)

        assert error.value.codigo == "PDBQT_NO_ES_RIGIDO"
        assert "línea" in error.value.mensaje("es") and "Line" in error.value.mensaje("en")

    @pytest.mark.parametrize("tipo", ["ZN", "CL", "BR", "FE", "NS", "OS", "XX"])
    def test_los_tipos_que_vina_rechaza_se_detectan_antes_de_la_corrida(self, tipo):
        texto = pdbqt_sintetico(residuos=30) + linea_pdbqt(9000, "X", "LIG", "A", 99, (0, 0, 0), tipo) + "\n"

        with pytest.raises(ErrorDeSubida) as error:
            analizar_pdbqt(texto)

        assert error.value.codigo == "PDBQT_TIPO_NO_SOPORTADO"
        assert tipo in error.value.mensaje("es")

    @pytest.mark.parametrize("tipo", ["Zn", "Cl", "Br", "Fe", "Mg", "Ca", "Mn", "SA", "A", "HD"])
    def test_los_tipos_que_vina_acepta_pasan(self, tipo):
        assert tipo in TIPOS_ACEPTADOS
        texto = pdbqt_sintetico(residuos=30) + linea_pdbqt(9000, "X", "LIG", "A", 99, (0, 0, 0), tipo,
                                                           registro="HETATM") + "\n"

        assert analizar_pdbqt(texto).atomos == 181

    def test_el_sodio_escrito_como_nitrogeno_aceptor_se_rechaza(self):
        sodio = linea_pdbqt(9000, "NA", "NA", "A", 99, (0, 0, 0), "NA", registro="HETATM")

        with pytest.raises(ErrorDeSubida) as error:
            analizar_pdbqt(pdbqt_sintetico(residuos=30) + sodio + "\n")

        assert error.value.codigo == "PDBQT_SODIO_COMO_NITROGENO"
        assert "Na" in error.value.mensaje("es")

    def test_un_nitrogeno_aceptor_que_se_llama_na_dentro_de_un_residuo_normal_no_es_un_sodio(self):
        nitrogeno = linea_pdbqt(9000, "NA", "LIG", "A", 99, (0, 0, 0), "NA", registro="HETATM")

        assert analizar_pdbqt(pdbqt_sintetico(residuos=30) + nitrogeno + "\n").atomos == 181

    def test_un_archivo_sin_atomos_o_con_coordenadas_rotas_se_rechaza(self):
        with pytest.raises(ErrorDeSubida) as vacio:
            analizar_pdbqt("REMARK nada\nEND\n")
        with pytest.raises(ErrorDeSubida) as rota:
            analizar_pdbqt(pdbqt_sintetico(residuos=30).replace("   3.800", "   abcdef", 1))
        with pytest.raises(ErrorDeSubida) as corta:
            analizar_pdbqt(pdbqt_sintetico(residuos=30) + "ATOM      1  N   ALA A   1\n")

        assert vacio.value.codigo == "PDBQT_SIN_ATOMOS"
        assert rota.value.codigo == "PDBQT_LINEA_ILEGIBLE"
        assert corta.value.codigo == "PDBQT_LINEA_ILEGIBLE"

    def test_varios_modelos_se_rechazan(self):
        texto = "MODEL 1\n" + pdbqt_sintetico(residuos=30) + "ENDMDL\nMODEL 2\n" + pdbqt_sintetico(residuos=30)

        with pytest.raises(ErrorDeSubida) as error:
            analizar_pdbqt(texto)

        assert error.value.codigo == "PDBQT_VARIOS_MODELOS"

    def test_un_fragmento_o_sin_hidrogenos_polares_se_avisa_pero_no_se_rechaza(self):
        resumen = analizar_pdbqt(pdbqt_sintetico(residuos=5))

        assert {a["codigo"] for a in resumen.avisos} == {"PDBQT_POCOS_ATOMOS"}
        sin_h = "\n".join(l for l in pdbqt_sintetico(residuos=30).splitlines() if not l.rstrip().endswith("HD"))
        assert {a["codigo"] for a in analizar_pdbqt(sin_h).avisos} == {"PDBQT_SIN_HIDROGENOS_POLARES"}

    def test_los_mensajes_no_llevan_rutas_del_disco(self):
        with pytest.raises(ErrorDeSubida) as error:
            analizar_pdbqt("ROOT C:\\Users\\alguien\\receptor.pdbqt\n")

        assert "alguien" not in error.value.mensaje("es") + error.value.mensaje("en")


# ── Correspondencia con la estructura de origen ───────────────────────────


class TestCorrespondencia:
    def test_el_origen_del_que_salio_el_pdbqt_corresponde(self):
        medida = correspondencia(pdb_sintetico(residuos=30), pdbqt_sintetico(residuos=30))

        assert medida["corresponde"] and medida["cobertura"] == 1.0
        assert medida["desplazamiento_mediano_A"] == 0.0

    def test_la_protonacion_no_rompe_la_correspondencia(self):
        origen = pdb_sintetico(residuos=30)
        pdbqt = pdbqt_sintetico(residuos=30).replace("ALA", "HID")   # otro nombre de la misma clase

        assert correspondencia(origen, pdbqt)["corresponde"] is False        # ALA no es HIS
        origen_his = origen.replace("ALA", "HIS")
        assert correspondencia(origen_his, pdbqt)["corresponde"] is True      # HIS ~ HID

    def test_otra_proteina_no_corresponde(self):
        otro = pdb_sintetico(residuos=30).replace("ALA", "GLY")

        with pytest.raises(ErrorDeSubida) as error:
            exigir_correspondencia(otro, pdbqt_sintetico(residuos=30))

        assert error.value.codigo == "PDBQT_NO_CORRESPONDE_AL_ORIGEN"
        assert error.value.datos["correspondencia"]["residuos_que_coinciden"] == 0

    def test_las_mismas_secuencias_con_otra_geometria_tampoco(self):
        movida = pdb_sintetico(residuos=30, origen=(0.0, 8.0, 0.0))

        with pytest.raises(ErrorDeSubida) as error:
            exigir_correspondencia(movida, pdbqt_sintetico(residuos=30))

        assert error.value.datos["correspondencia"]["cobertura"] == 1.0
        assert error.value.datos["correspondencia"]["desplazamiento_mediano_A"] > 0.5

    def test_otra_cadena_no_corresponde(self):
        with pytest.raises(ErrorDeSubida):
            exigir_correspondencia(pdb_sintetico(cadena="B"), pdbqt_sintetico(cadena="A"))


# ── El PDB que se reconstruye desde el PDBQT ──────────────────────────────


class TestPdbqtComoPdb:
    def test_quita_hidrogenos_y_reescribe_el_elemento(self):
        pdb = pdbqt_como_pdb(pdbqt_sintetico(residuos=2))

        lineas = pdb.splitlines()
        assert len(lineas) == 10 and not any(l[12:16].strip() == "H" for l in lineas)
        assert {l[76:78].strip() for l in lineas} == {"N", "C", "O"}
        assert all(l.startswith("ATOM  ") for l in lineas)

    def test_un_hetero_con_tipo_metalico_conserva_su_elemento(self):
        texto = pdbqt_sintetico(residuos=2) + linea_pdbqt(99, "ZN", "ZN", "A", 301, (1, 2, 3), "Zn",
                                                          registro="HETATM") + "\n"

        zinc = [l for l in pdbqt_como_pdb(texto).splitlines() if l.startswith("HETATM")]
        assert len(zinc) == 1 and zinc[0][76:78] == "ZN"


# ── El perfil: el catálogo no tiene ───────────────────────────────────────


class TestPerfil:
    @pytest.mark.parametrize("pdb_id", ["8HFI", "1C3R", "3F75", "5VA1", "1HSG"])
    def test_el_catalogo_no_tiene_perfil_y_no_toca_el_disco(self, pdb_id, monkeypatch):
        def prohibido(*_a, **_k):
            raise AssertionError("el catálogo no puede leer un perfil del disco")

        monkeypatch.setattr(perfil_receptor, "path_for", prohibido)

        assert perfil_receptor.cargar(pdb_id) is None
        assert perfil_receptor.distinto_del_automatico(pdb_id) is None
        assert perfil_receptor.extras_del_informe(pdb_id) == {}

    def test_un_receptor_propio_sin_perfil_se_prepara_como_siempre(self, tmp_path, monkeypatch):
        aislar_almacen(monkeypatch, tmp_path)

        assert perfil_receptor.cargar("USR_ABC123") is None
        assert perfil_receptor.distinto_del_automatico("USR_ABC123") is None


# ── La preparación del PDBQT propio ───────────────────────────────────────


def _perfil(contenido: bytes, *, con_origen: bool) -> dict:
    sha = sha256_de(contenido)
    return {
        "schema": perfil_receptor.SCHEMA, "pdb_id": "USR_C0C0C0", "modo": perfil_receptor.MODO_PDBQT,
        "receptor_sha256": sha,
        "entrada": {"archivo": "mi_receptor.pdbqt", "formato": "pdbqt", "bytes": len(contenido), "sha256": sha},
        "origen": {"sha256_contenido": "a" * 64} if con_origen else None,
        "almacen": {"receptor": "targets/USR_C0C0C0/subida/receptor.pdbqt",
                    "origen": "targets/USR_C0C0C0/raw.pdb" if con_origen else None},
    }


@pytest.mark.asyncio
async def test_sin_origen_el_receptor_es_el_archivo_y_lo_que_no_se_sabe_queda_en_null_con_motivo(
    tmp_path, monkeypatch,
):
    from utils.local_storage import read_bytes, read_text, write_bytes

    datos = aislar_almacen(monkeypatch, tmp_path)
    contenido = pdbqt_sintetico(residuos=30).encode()
    perfil = _perfil(contenido, con_origen=False)
    await write_bytes(contenido, perfil["almacen"]["receptor"])

    ruta = await preparar_pdbqt("USR_C0C0C0", perfil, center=(10.0, 0.0, 0.0), size=(20.0, 20.0, 20.0))

    assert await read_bytes(ruta) == contenido            # ni un byte distinto del que subió
    informe = json.loads(await read_text(ruta[:-6] + ".report.json"))
    assert informe["receptor_sha256"] == sha256_de(contenido)
    assert informe["modo_de_preparacion"] == "pdbqt_sin_origen"
    assert informe["pdbqt"]["cadenas"] == ["A"] and informe["pdbqt"]["tipos_de_atomo"]["OA"] == 30
    for campo in ("species_diff", "removed_residues", "truncated_sidechains", "backbone_gaps"):
        assert informe[campo] is None, campo
        assert "estructura de origen" in informe["no_disponible"][campo]
    # Lo que `vina_service` exige de un informe de receptor existe, vacío y declarado.
    assert informe["protonation_templates"] == {} and informe["protonacion_declarada"]["verificada"] is False
    assert not any(datos.rglob("*.mol2"))


@pytest.mark.asyncio
async def test_un_pdbqt_alterado_en_disco_no_se_evalua(tmp_path, monkeypatch):
    from core.exceptions import ProteinPreparationError
    from utils.local_storage import write_bytes

    aislar_almacen(monkeypatch, tmp_path)
    contenido = pdbqt_sintetico(residuos=30).encode()
    perfil = _perfil(contenido, con_origen=False)
    await write_bytes(contenido + b"REMARK alterado\n", perfil["almacen"]["receptor"])

    with pytest.raises(ProteinPreparationError):
        await preparar_pdbqt("USR_C0C0C0", perfil, center=(10.0, 0.0, 0.0), size=(20.0, 20.0, 20.0))


def test_la_receta_depende_de_la_caja_y_del_origen():
    contenido = pdbqt_sintetico(residuos=30).encode()
    sin_origen = _perfil(contenido, con_origen=False)
    con_origen = _perfil(contenido, con_origen=True)
    caja = ((1.0, 2.0, 3.0), (20.0, 20.0, 20.0))

    assert receta_pdbqt(sin_origen, *caja) == receta_pdbqt(sin_origen, *caja)
    assert receta_pdbqt(sin_origen, *caja) != receta_pdbqt(con_origen, *caja)
    assert receta_pdbqt(sin_origen, *caja) != receta_pdbqt(sin_origen, (1.0, 2.0, 4.0), caja[1])


def test_con_origen_el_informe_audita_hacia_el_pdbqt():
    pdb, _ = cadena_de_alaninas(residuos=30, hetero=("HEM", "FE", 301, (10.0, 0.5, 0.0)))
    origen = "\n".join(pdb) + "\nEND\n"
    pdbqt = pdbqt_sintetico(residuos=30)
    perfil = {**_perfil(pdbqt.encode(), con_origen=True), "pdb_id": "USR_C0C0C0"}

    informe = construir_informe(perfil, pdbqt, recipe_hash="b" * 64, center=(10.0, 0.0, 0.0),
                                size=(20.0, 20.0, 20.0), origen_texto=origen)

    assert informe["modo_de_preparacion"] == "pdbqt_con_origen"
    diff = informe["species_diff"]
    assert diff["state"] == "evaluado"
    # El hemo estaba en el origen, junto a la caja, y el PDBQT no lo trae: se declara retirado.
    retiradas = {f["name"] for f in diff["near_site"]["removed"]}
    assert "HEM" in retiradas
    assert informe["removed_residues"] == [] and informe["backbone_gaps"] == []
    assert "species_diff" not in informe.get("no_disponible", {})


# ── Lo que dice Preparación ───────────────────────────────────────────────


def _auditar_pdbqt(receptor_prep: dict) -> dict:
    import copy

    from tests.fixtures_dossier import caso_completo
    from tests.test_preparacion_auditoria import _PROCEDENCIA, _auditar

    caso = caso_completo()
    procedencia = copy.deepcopy(_PROCEDENCIA)
    procedencia["receptor_prep"] = receptor_prep
    caso["eval_result"].docking_protocol = {
        **caso["eval_result"].docking_protocol, "execution_provenance": procedencia}
    return _auditar(caso)


def _requisito(auditoria: dict, clave: str) -> dict:
    return next(r for b in auditoria["bloques"] for r in b["requisitos"] if r["clave"] == clave)


def test_preparacion_bloquea_un_pdbqt_sin_origen_y_dice_que_hacer():
    pdbqt = pdbqt_sintetico(residuos=30)
    perfil = {**_perfil(pdbqt.encode(), con_origen=False), "pdb_id": "USR_C0C0C0"}
    informe = construir_informe(perfil, pdbqt, recipe_hash="b" * 64, center=(10.0, 0.0, 0.0),
                                size=(20.0, 20.0, 20.0), origen_texto=None)
    informe = {**informe, "chain": "A", "site_chains": ["A"],
               "entrada": perfil["entrada"]}

    auditoria = _auditar_pdbqt({"source": "meeko_report", **informe})

    assert auditoria["estado"] == "BLOQUEADO"
    metales = _requisito(auditoria, "entorno.metales_cofactores")
    assert metales["estado"] == "NO_EVALUADO"
    assert "Sin la estructura de origen" in metales["razon"] and "súbela" in metales["razon"]
    assert "estructura de origen del PDBQT" in metales["accion_recomendada"]
    assert "entorno.metales_cofactores" in auditoria["bloqueantes"]
    # Lo demás que no se pudo medir se explica igual, y la protonación es del usuario.
    assert "estructura de origen" in _requisito(auditoria, "receptor.residuos_retirados")["razon"]
    protonacion = _requisito(auditoria, "receptor.protonacion")
    assert protonacion["valor"].startswith("Declarada por el usuario")
    assert "validada" not in protonacion["razon"].lower()
    entrada = _requisito(auditoria, "receptor.entrada")
    assert entrada["estado"] == "REGISTRADO" and "PDBQT listo para Vina, sin estructura de origen" in entrada["valor"]


def test_un_receptor_del_catalogo_no_gana_requisitos_ni_razones_nuevas():
    auditoria = _auditar_pdbqt({"source": "meeko_report", "recipe_hash": "5" * 64, "chain": "A",
                                "site_chains": ["A"], "removed_residues": [], "cofactors_outside_site": []})

    claves = {r["clave"] for b in auditoria["bloques"] for r in b["requisitos"]}
    assert "receptor.entrada" not in claves
    assert "estructura de origen" not in json.dumps(auditoria, ensure_ascii=False)


def test_la_auditoria_de_un_pdbqt_sin_origen_se_lee_entera_en_ingles():
    from services.dossier.localization import traducir_dossier
    from tests.test_dossier_en_ingles_completo import _parece_espanol

    pdbqt = pdbqt_sintetico(residuos=30)
    perfil = {**_perfil(pdbqt.encode(), con_origen=False), "pdb_id": "USR_C0C0C0"}
    informe = construir_informe(perfil, pdbqt, recipe_hash="b" * 64, center=(10.0, 0.0, 0.0),
                                size=(20.0, 20.0, 20.0), origen_texto=None)
    auditoria = _auditar_pdbqt({"source": "meeko_report", **informe, "chain": "A", "site_chains": ["A"],
                                "entrada": perfil["entrada"]})

    en = traducir_dossier(auditoria, "en")

    requisitos = {r["clave"]: r for b in en["bloques"] for r in b["requisitos"]}
    for clave in ("receptor.protonacion", "receptor.entrada", "entorno.metales_cofactores",
                  "receptor.residuos_retirados", "receptor.huecos", "receptor.cadenas_truncadas"):
        for campo in ("razon", "valor", "accion_recomendada"):
            texto = requisitos[clave].get(campo)
            assert not texto or not _parece_espanol(texto), (clave, campo, texto)
    assert requisitos["receptor.protonacion"]["valor"] == "Declared by the user (origin: user)"
    assert "mode: PDBQT ready for Vina, without a source structure" in requisitos["receptor.entrada"]["valor"]
    assert "Upload the PDBQT's source structure" in requisitos["entorno.metales_cofactores"]["accion_recomendada"]
