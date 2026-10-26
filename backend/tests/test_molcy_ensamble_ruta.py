"""La ruta de Molcy ofrece y lanza la escena Ensamble sólo cuando la corrida la respalda.

Se prueba el router con el mismo arnés que las demás escenas: la corrida guardada, el
motor y el renderizador son dobles; lo que se comprueba es qué se ofrece, qué se
abstiene y qué llega al paquete y al lanzador.
"""
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.dependencies import get_current_user
from api.routers import molcy
from core.database import get_db
from services.molcy import cpu, renderer
from services.molcy import ensamble as evidencia
from services.molcy.package import sha256


_RECOGER_REAL = evidencia.recoger


def _snap(generadas=30, por_conformacion=True, con_receptor=True):
    receptor = b"receptor guardado con la corrida"
    prov = {"box_center": [1, 2, 3], "box_size": [20, 20, 20]}
    if por_conformacion:
        prov["por_conformacion"] = [{"indice": 4, "num_poses": 9}]
    return receptor, {
        "receptor_path": "receptor-run", "receptor_sha256": sha256(receptor),
        "vina_random_seed": 42,
        "docking_protocol": {"conformers_generated": generadas, "execution_provenance": prov},
        "docking_poses": [{"rank": 1, "affinity": -7.0, "conformer_index": 4,
                           "source_provenance": {"rank": 1}}],
    } if con_receptor else {}


@pytest.fixture
def cliente(monkeypatch, tmp_path):
    user = SimpleNamespace(id=uuid.uuid4())
    mol = SimpleNamespace(id=uuid.uuid4(), target=SimpleNamespace(
        id=uuid.uuid4(), pdb_id="TEST", name="Receptor", chain="A"))
    receptor, snap = _snap()
    run = SimpleNamespace(status="SUCCESS", saved_at="guardado", snapshot_json=snap,
                          molecule_id=mol.id, task_id="run")
    repo = SimpleNamespace(get_evaluation_run=AsyncMock(return_value=run),
                           materialize_run_snapshot=AsyncMock(return_value=snap),
                           get_all_targets=AsyncMock(return_value=[]))
    db = AsyncMock()
    db.scalar.return_value = mol
    db.execute.return_value = SimpleNamespace(all=lambda: [(run, "Molecula", "TEST")])
    app = FastAPI()
    app.include_router(molcy.router)

    async def database():
        yield db

    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_current_user] = lambda: user
    monkeypatch.setattr(molcy, "Repository", lambda _: repo)
    monkeypatch.setattr(molcy, "_instalacion_estable", lambda: None)
    monkeypatch.setattr(cpu, "recursos", lambda: {"cpu_hilos": 2, "cpu_logicos": 8,
                                                  "cpu_hilos_disponibles": 8, "cpu_hilos_maximos": 6})
    monkeypatch.setattr(renderer, "detectar", lambda: {"disponible": True, "gpu_disponible": True,
                                                       "cpu_hilos_configurables": True})
    monkeypatch.setattr(renderer, "ensamble_disponible", lambda: True)
    monkeypatch.setattr(renderer, "busqueda_disponible", lambda: False)
    monkeypatch.setattr(molcy.disk, "assert_budget", lambda *_: None)
    monkeypatch.setattr(renderer, "raiz_trabajo", lambda *_: tmp_path)
    monkeypatch.setattr(molcy.storage, "crear_raiz", lambda *a, **k: tmp_path)  # sin esto escribía en los datos reales
    monkeypatch.setattr(molcy, "read_bytes", AsyncMock(return_value=receptor))
    entregado = {"contrato": {"schema": "moldesign.ensamble/1"}, "archivos": {}}
    recoger = AsyncMock(return_value=entregado)
    monkeypatch.setattr(evidencia, "recoger", recoger)
    paquetes, lanzados = [], []
    monkeypatch.setattr(molcy, "construir_paquete", lambda _, **kw: paquetes.append(kw))
    monkeypatch.setattr(renderer, "iniciar", lambda *_, **kw: lanzados.append(kw))
    with TestClient(app) as client:
        yield SimpleNamespace(client=client, db=db, mol=mol, snap=snap, run=run, recoger=recoger,
                              entregado=entregado, paquetes=paquetes, lanzados=lanzados)


def _lanzar(c, escena="ensamble"):
    return c.client.post("/molcy/trabajos", json={
        "origen": "moldex", "id": str(c.mol.id), "task_id": "run", "escena": escena,
        "formato": "previsualizacion", "dispositivo": "gpu"})


# ── qué se ofrece ─────────────────────────────────────────────────────────────
def test_una_corrida_de_ensamble_ofrece_la_escena(cliente):
    fuente = cliente.client.get("/molcy/fuentes").json()["moldex"][0]
    assert "ensamble" in fuente["escenas_disponibles"]
    # La piscina no tiene un SDF único: «resultado» no se ofrece (sólo el receptor y la caja).
    assert "resultado" not in fuente["escenas_disponibles"]


@pytest.mark.parametrize("cambio", [
    "motor_viejo", "una_conformacion", "sin_por_conformacion", "sin_caja",
])
def test_no_se_ofrece_si_algo_de_lo_necesario_falta(cliente, monkeypatch, cambio):
    prov = cliente.snap["docking_protocol"]["execution_provenance"]
    if cambio == "motor_viejo":
        monkeypatch.setattr(renderer, "ensamble_disponible", lambda: False)
    elif cambio == "una_conformacion":
        cliente.snap["docking_protocol"]["conformers_generated"] = 1
    elif cambio == "sin_por_conformacion":
        prov.pop("por_conformacion")
    else:
        prov.pop("box_center")
    fuente = cliente.client.get("/molcy/fuentes").json()["moldex"][0]
    assert "ensamble" not in fuente["escenas_disponibles"]


# ── qué se lanza ──────────────────────────────────────────────────────────────
def test_lanzar_el_ensamble_demuestra_la_evidencia_y_la_pone_en_el_paquete(cliente):
    r = _lanzar(cliente)

    assert r.status_code == 202, r.text
    cliente.recoger.assert_awaited_once_with(cliente.snap)
    assert cliente.paquetes[0]["ensamble"] is cliente.entregado
    # El ensamble no tiene un archivo de poses único: no se le pasa uno.
    assert cliente.paquetes[0]["poses_sdf"] is None
    assert cliente.lanzados[0]["sujeto"] == "ensamble_conformacional"
    assert cliente.lanzados[0]["fuente"]["task_id"] == "run"
    assert cliente.lanzados[0]["fuente"]["escena"] == "ensamble"


def test_si_la_evidencia_no_se_demuestra_no_se_lanza_nada_y_se_dice_por_que(cliente):
    cliente.recoger.side_effect = evidencia.EnsambleNoDisponible(
        "No se puede demostrar la pose 3 de la piscina: el archivo cambió")
    r = _lanzar(cliente)

    assert r.status_code == 409
    assert "pose 3" in r.json()["detail"]
    assert cliente.lanzados == [] and cliente.paquetes == []


def test_con_un_motor_sin_la_escena_se_rechaza_antes_de_demostrar_nada(cliente, monkeypatch):
    monkeypatch.setattr(renderer, "ensamble_disponible", lambda: False)
    r = _lanzar(cliente)

    assert r.status_code == 409 and "Ensamble" in r.json()["detail"]
    cliente.recoger.assert_not_awaited()
    assert cliente.lanzados == []


def test_una_corrida_que_no_es_ensamble_se_abstiene_con_el_motivo_real(cliente, monkeypatch):
    monkeypatch.setattr(evidencia, "recoger", _RECOGER_REAL)       # no el doble del arnés
    cliente.snap["docking_protocol"]["conformers_generated"] = 1
    r = _lanzar(cliente)

    assert r.status_code == 409
    assert "no es un ensamble" in r.json()["detail"]
    assert cliente.lanzados == [] and cliente.paquetes == []


@pytest.mark.parametrize("escena", ["resultado", "receptor", "busqueda"])
def test_las_demas_escenas_no_cambian_de_sujeto(cliente, escena):
    r = _lanzar(cliente, escena)
    # `resultado` y `busqueda` piden poses y traza que este arnés no tiene: 409, no 500.
    assert r.status_code in (202, 409), r.text
    if r.status_code == 202:
        assert cliente.lanzados[0]["sujeto"] == "receptor_solo"
    cliente.recoger.assert_not_awaited()


def test_una_sesion_de_fotos_acepta_la_escena_ensamble():
    modelo = molcy.NuevasFotos(origen="moldex", id="x", task_id="run", escena="ensamble",
                               orientacion="vertical", dispositivo="cpu", cpu_hilos=2)
    assert modelo.escena == "ensamble"


def test_el_ensamble_se_lanza_con_su_guion_y_las_demas_escenas_no_cambian():
    assert renderer.GUION_DE_SUJETO["ensamble_conformacional"] == "y"
    assert renderer.GUION_DE_SUJETO["busqueda_montecarlo"] == "x"
    for sujeto in ("pose_evaluada", "receptor_solo", "ligando_cocristal"):
        assert renderer.GUION_DE_SUJETO.get(sujeto, "sitio_activo") == "sitio_activo"


def _filas(cliente, n):
    otra = SimpleNamespace(status="SUCCESS", saved_at="guardado", snapshot_json=cliente.snap,
                           molecule_id=uuid.uuid4(), task_id=str(uuid.uuid4()))
    cliente.db.execute.return_value = SimpleNamespace(
        all=lambda: [(otra if i else cliente.run, f"Molecula {i}", "TEST") for i in range(n)])


def test_el_motor_se_comprueba_una_sola_vez_por_listado(cliente, monkeypatch):
    """Comprobar el motor relee y hashea sus ficheros: no se repite por cada corrida."""
    llamadas = []
    monkeypatch.setattr(renderer, "ensamble_disponible", lambda: llamadas.append(1) or True)
    _filas(cliente, 6)
    filas = cliente.client.get("/molcy/fuentes").json()["moldex"]

    assert len(filas) == 6 and all("ensamble" in f["escenas_disponibles"] for f in filas)
    assert len(llamadas) == 1


def test_una_corrida_que_no_es_ensamble_no_cuesta_una_comprobacion_del_motor(cliente, monkeypatch):
    llamadas = []
    monkeypatch.setattr(renderer, "ensamble_disponible", lambda: llamadas.append(1) or True)
    cliente.snap["docking_protocol"]["conformers_generated"] = 1
    _filas(cliente, 6)
    filas = cliente.client.get("/molcy/fuentes").json()["moldex"]

    assert all("ensamble" not in f["escenas_disponibles"] for f in filas)
    assert llamadas == []


def _rig_disponible(cliente, indice=4, ejes=True, hash_correcto=True):
    cliente.entregado["contrato"]["conformeros"] = [
        {"indice": indice, "sdf_sha256": "a" * 64, "rig_torsional": {
            "schema": "moldesign.rig-torsional/1", "sdf_sha256": ("a" if hash_correcto else "b") * 64,
            "ejes": [{"atomos": ["C1", "C2", "C3", "C4"]}] if ejes else []}}]


def _lanzar_con_receta(cliente, **extra):
    return cliente.client.post("/molcy/trabajos", json={
        "origen": "moldex", "id": str(cliente.mol.id), "task_id": "run", "escena": "ensamble",
        "formato": "previsualizacion", "dispositivo": "gpu", **extra})


def test_la_creacion_devuelve_la_receta_normalizada_que_recibe_el_lanzador(cliente):
    _rig_disponible(cliente)
    r = _lanzar_con_receta(cliente, presentacion={"titulo": "Mi ensamble", "color_receptor": "#aabbcc"},
                          ensamble_fluido={"variante": "lenta"})
    assert r.status_code == 202, r.text
    ajustes = r.json()["ajustes"]
    assert ajustes["ensamble_fluido"] == {"variante": "lenta", "conformero": 4}
    assert ajustes["presentacion"]["color_receptor"] == "#AABBCC"
    assert cliente.lanzados[0]["ensamble_fluido"] == ajustes["ensamble_fluido"]
    assert cliente.lanzados[0]["presentacion"] == ajustes["presentacion"]


@pytest.mark.parametrize("fallo", ["sin_rig", "sin_ejes", "hash", "indice"])
def test_fluido_explicito_sin_fuente_verificable_se_abstiene_antes_del_paquete(cliente, fallo):
    if fallo != "sin_rig":
        _rig_disponible(cliente, ejes=fallo != "sin_ejes", hash_correcto=fallo != "hash")
    r = _lanzar_con_receta(cliente, ensamble_fluido={"variante": "detallada", "conformero": 99 if fallo == "indice" else 4})
    assert r.status_code == 409 and "rig torsional" in r.json()["detail"]
    assert cliente.paquetes == [] and cliente.lanzados == []


def test_referencia_actual_sigue_disponible_sin_rig_y_rechaza_parametro_cientifico(cliente):
    r = _lanzar_con_receta(cliente)
    assert r.status_code == 202, r.text
    assert "ensamble_fluido" not in r.json()["ajustes"]
    assert cliente.lanzados[0]["ensamble_fluido"] is None
    bad = _lanzar_con_receta(cliente, presentacion={"vina_random_seed": 1})
    assert bad.status_code == 422


def test_no_aplica_torsiones_a_una_escena_sin_ensamble(cliente):
    r = _lanzar_con_receta(cliente, escena="receptor", ensamble_fluido={"variante": "lenta"})
    assert r.status_code == 422
    assert cliente.paquetes == [] and cliente.lanzados == []
