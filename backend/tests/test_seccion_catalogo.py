"""El catálogo no promociona evidencia incompleta ni de otra receta."""
import json
from types import SimpleNamespace

import pytest

from services.targets import seccion_catalogo as sc
from services.docking.preparer import RECEPTOR_RECIPE_VERSION


@pytest.fixture(autouse=True)
def limpiar_cache():
    sc._leer.cache_clear()
    yield
    sc._leer.cache_clear()


def target(**extra):
    return SimpleNamespace(pdb_id="8HFI", is_private=False, is_community=False, **extra)


def entrada():
    return {
        "receta_receptor": RECEPTOR_RECIPE_VERSION,
        "receptor_sha256": "0" * 64,
        "pose": {"semillas": 5, "semillas_rmsd_ok": 4, "posebusters_valida": True},
        "calibracion": {"rho": 0.41, "ic95": [0.17, 0.61], "n": 55, "endpoint": "Ki",
                        "panel": "prueba"},
        "protocolo": {"exhaustiveness": 8, "num_poses": 9, "semilla": 42},
        "condiciones": ["RECEPTOR_SIN_IONES", "SERIE_CONGENERICA"],
    }


def inyectar(monkeypatch, tmp_path, datos):
    ruta = tmp_path / "verificados.json"
    ruta.write_text(json.dumps({"verificados": {"8HFI": datos}}), encoding="utf-8")
    monkeypatch.setattr(sc, "RUTA_VERIFICADOS", ruta)


def _sin_respaldo(pdb_id: str, verificado: dict) -> list[str]:
    """Campos de un verificado real que no repite su intento GO publicado (que a su vez coincide con su sello)."""
    intentos = json.loads(sc.RUTA_INTENTOS.read_text(encoding="utf-8"))["intentos"]
    go = [i for i in intentos if i.get("pdb_id") == pdb_id and i.get("decision") == "GO"
          and i.get("experimento") == verificado.get("experimento")]
    if len(go) != 1:
        return ["intento_GO"]
    intento = go[0]
    campos = [("receta_receptor",), ("receptor_sha256",), ("protocolo",), ("condiciones",)]
    campos += [("pose", k) for k in ("semillas", "semillas_rmsd_ok", "posebusters_valida", "rmsd_top1_A")]
    campos += [("calibracion", k) for k in ("rho", "ic95", "n", "endpoint", "panel", "rho_peor", "ic95_rho_peor")]

    def valor(d, ruta):
        for clave in ruta:
            d = d.get(clave) if isinstance(d, dict) else None
        return d
    return [".".join(c) for c in campos if valor(verificado, c) != valor(intento, c)]


def test_guardian_cada_verificado_real_tiene_su_intento_go_sellado():
    """Promocionar a mano falla: cada verificado repite las cifras de un intento GO, y
    `test_intentos_de_verificacion` comprueba ese intento contra su experimento sellado."""
    datos = json.loads(sc.RUTA_VERIFICADOS.read_text(encoding="utf-8"))["verificados"]
    assert set(datos) == {"8T69"}
    for pdb_id, verificado in datos.items():
        assert sc.supera_el_protocolo(verificado), pdb_id
        assert _sin_respaldo(pdb_id, verificado) == [], pdb_id


@pytest.mark.parametrize("ruta, valor", [
    (("calibracion", "rho"), 0.45), (("calibracion", "ic95"), [0.3, 0.6]), (("pose", "semillas_rmsd_ok"), 4),
    (("receptor_sha256",), "0" * 64), (("experimento",), "CAL-D-01-R4-VMAT2-8T69"),
])
def test_el_guardian_ve_un_verificado_sin_respaldo(ruta, valor):
    """Control negativo: mejorar una cifra o apoyarse en un intento que no es GO tiene que fallar."""
    import copy

    verificado = copy.deepcopy(json.loads(sc.RUTA_VERIFICADOS.read_text(encoding="utf-8"))["verificados"]["8T69"])
    destino = verificado
    for clave in ruta[:-1]:
        destino = destino[clave]
    destino[ruta[-1]] = valor
    assert _sin_respaldo("8T69", verificado) != []


def test_8t69_real_es_verificado():
    assert sc.seccion_del_receptor(SimpleNamespace(pdb_id="8T69", is_private=False, is_community=False)) == "verificado"


@pytest.mark.parametrize("pdb_id", ["8HFI", "1UZJ", "DESCONOCIDO"])
def test_catalogo_real_es_demostracion(pdb_id):
    receptor = target()
    receptor.pdb_id = pdb_id
    assert sc.seccion_del_receptor(receptor) == "demostracion"
    assert sc.verificacion_del_receptor(pdb_id) is None


@pytest.mark.parametrize("campo", ["is_private", "is_community"])
def test_propios_y_comunidad_no_son_catalogo(campo):
    receptor = target()
    setattr(receptor, campo, True)
    assert sc.seccion_del_receptor(receptor) is None


def test_entrada_completa_receta_actual(monkeypatch, tmp_path):
    datos = entrada()
    inyectar(monkeypatch, tmp_path, datos)
    assert sc.seccion_del_receptor(target()) == "verificado"
    assert sc.verificacion_del_receptor("8hfi") == datos


@pytest.mark.parametrize("defecto", ["sin_pose", "sin_calibracion", "otra_receta", "pose_vacia", "calibracion_vacia"])
def test_evidencia_incompleta_no_promociona(monkeypatch, tmp_path, defecto):
    datos = entrada()
    if defecto.startswith("sin_"):
        datos.pop(defecto[4:])
    elif defecto == "otra_receta":
        datos["receta_receptor"] = RECEPTOR_RECIPE_VERSION + 1
    else:
        datos[defecto.split("_")[0]] = {}
    inyectar(monkeypatch, tmp_path, datos)
    assert sc.seccion_del_receptor(target()) == "demostracion"
    assert sc.verificacion_del_receptor("8HFI") is None


def _sin_hash(d):
    d.pop("receptor_sha256")


def _ic_cruza_cero(d):
    d["calibracion"]["ic95"] = [-0.05, 0.48]


def _ic_toca_cero(d):
    d["calibracion"]["ic95"] = [0, 0.48]


def _dos_de_cinco(d):
    d["pose"]["semillas_rmsd_ok"] = 2


def _cuatro_semillas(d):
    d["pose"].update(semillas=4, semillas_rmsd_ok=4)


def _mas_ok_que_semillas(d):
    d["pose"]["semillas_rmsd_ok"] = 6


def _posebusters_falla(d):
    d["pose"]["posebusters_valida"] = False


def _posebusters_ausente(d):
    d["pose"].pop("posebusters_valida")


def _sin_endpoint(d):
    d["calibracion"].pop("endpoint")


def _ic_texto(d):
    d["calibracion"]["ic95"] = ["0.17", "0.61"]


def _sin_protocolo(d):
    d.pop("protocolo")


def _protocolo_sin_semilla(d):
    d["protocolo"].pop("semilla")


def _sin_condiciones(d):
    d.pop("condiciones")


def _condicion_vacia(d):
    d["condiciones"] = [""]


@pytest.mark.parametrize("romper", [
    _sin_hash, _ic_cruza_cero, _ic_toca_cero, _dos_de_cinco, _cuatro_semillas,
    _mas_ok_que_semillas, _posebusters_falla, _posebusters_ausente, _sin_endpoint, _ic_texto,
    _sin_protocolo, _protocolo_sin_semilla, _sin_condiciones, _condicion_vacia,
])
def test_resultado_que_no_supera_el_protocolo_sigue_en_demostracion(monkeypatch, tmp_path, romper):
    """Un resultado desfavorable se publica, pero no gana el sello aunque se escriba."""
    datos = entrada()
    romper(datos)
    inyectar(monkeypatch, tmp_path, datos)
    assert sc.seccion_del_receptor(target()) == "demostracion"
    assert sc.verificacion_del_receptor("8HFI") is None


def test_el_limite_del_protocolo_si_supera(monkeypatch, tmp_path):
    datos = entrada()
    datos["pose"]["semillas_rmsd_ok"] = 3
    datos["calibracion"]["ic95"] = [0.01, 0.5]
    datos["condiciones"] = []  # declarar «ninguna» también es declarar
    inyectar(monkeypatch, tmp_path, datos)
    assert sc.seccion_del_receptor(target()) == "verificado"


def test_avisos_medidos():
    esperados = "1UZJ 1W22 2B2A 3KD2 3KDA 3V94 4DLN 4DM7 4DMF 4I04 4LMO 4YNQ 5DIY 5YWV 7JVU 7JVW".split()
    assert set(sc._leer(sc.RUTA_AVISOS)["avisos"]) == set(esperados)
    for pdb in esperados:
        assert sc.avisos_del_receptor(pdb.lower()) == ["SITIO_FUERA_DE_LA_UNIDAD_BIOLOGICA"]
    assert sc.avisos_del_receptor("8HFI") == []


@pytest.mark.parametrize("contenido", [None, "{", "[]", '{"verificados": []}', '{"verificados": {"8HFI": 7}}'])
def test_archivo_ausente_o_corrupto(monkeypatch, tmp_path, contenido):
    ruta = tmp_path / "faltante.json"
    if contenido is not None:
        ruta.write_text(contenido, encoding="utf-8")
    monkeypatch.setattr(sc, "RUTA_VERIFICADOS", ruta)
    monkeypatch.setattr(sc, "RUTA_AVISOS", ruta)
    assert sc.seccion_del_receptor(target()) == "demostracion"
    assert sc.verificacion_del_receptor("8HFI") is None
    assert sc.avisos_del_receptor("1UZJ") == []


@pytest.mark.asyncio
async def test_listado_transporta_seccion_y_avisos_sin_cambiar_disponibilidad(monkeypatch):
    import uuid
    from unittest.mock import AsyncMock
    from api.routers import targets

    receptor = SimpleNamespace(
        id=uuid.uuid4(), pdb_id="1UZJ", name="prueba", chain="A",
        description=None, is_prepared=False, requires_cns=False,
        structural_family="protease", organism=None, resolution=None,
        is_private=False, is_community=False, retired_reason=None, hotspots=None,
    )
    monkeypatch.setattr(targets.Repository, "get_all_targets", AsyncMock(return_value=[receptor]))
    monkeypatch.setattr(targets, "estado_de_calibracion", lambda _: SimpleNamespace(to_dict=lambda: {}))
    monkeypatch.setattr(targets, "motivo_no_disponible", lambda _: None)
    monkeypatch.setattr(targets, "cadenas_truncadas_en_sitio", lambda _: ["A:1 LYS→ALA"])
    resultado = (await targets.list_targets(current_user=None, db=None))[0]
    assert resultado.seccion_catalogo == "demostracion"
    assert resultado.verificacion is None
    assert resultado.avisos_catalogo == ["SITIO_FUERA_DE_LA_UNIDAD_BIOLOGICA"]
    assert resultado.disponible is True
    assert resultado.cadenas_truncadas_en_sitio == ["A:1 LYS→ALA"]


# SCI-D-002: resúmenes que tienen todos los campos y aun así no describen el
# protocolo declarado, o no describen ninguna correlación posible.

def _tres_de_cien_semillas(d):
    d["pose"].update(semillas=100, semillas_rmsd_ok=3)


def _rho_negativa_con_ic_positivo(d):
    d["calibracion"].update(rho=-0.8, ic95=[0.1, 0.5])


def _rho_cero_con_ic_positivo(d):
    d["calibracion"].update(rho=0.0, ic95=[0.1, 0.5])


def _ic_fuera_del_dominio(d):
    d["calibracion"]["ic95"] = [1.1, 1.3]


def _ic_infinito(d):
    d["calibracion"]["ic95"] = [0.1, float("inf")]


def _rho_no_numero(d):
    d["calibracion"]["rho"] = float("nan")


def _rho_fuera_del_dominio(d):
    d["calibracion"].update(rho=1.4, ic95=[0.2, 0.6])


def _n_booleano(d):
    d["calibracion"]["n"] = True


def _semillas_ok_booleano(d):
    d["pose"]["semillas_rmsd_ok"] = True


@pytest.mark.parametrize("romper", [
    _tres_de_cien_semillas, _rho_negativa_con_ic_positivo, _rho_cero_con_ic_positivo,
    _ic_fuera_del_dominio, _ic_infinito, _rho_no_numero, _rho_fuera_del_dominio,
    _n_booleano, _semillas_ok_booleano,
])
def test_resumen_incoherente_con_el_protocolo_no_promociona(monkeypatch, tmp_path, romper):
    datos = entrada()
    romper(datos)
    inyectar(monkeypatch, tmp_path, datos)
    assert sc.supera_el_protocolo(datos) is False
    assert sc.seccion_del_receptor(target()) == "demostracion"


def test_ic_que_no_contiene_la_rho_puntual_no_se_rechaza_por_eso(monkeypatch, tmp_path):
    """Un bootstrap percentil no garantiza contener la estimación: no se exige."""
    datos = entrada()
    datos["calibracion"].update(rho=0.12, ic95=[0.15, 0.6])
    inyectar(monkeypatch, tmp_path, datos)
    assert sc.supera_el_protocolo(datos) is True
