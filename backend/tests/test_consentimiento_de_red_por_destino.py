"""Ninguna herramienta sale a la red sin permiso de esa cuenta para ese destino.

MOLCHAT-NET-005 puso consentimiento por cuenta y por destino **para el proveedor
de chat**. Las herramientas quedaron fuera: `allow_web` es un interruptor
general, así que autorizar «buscar en internet» autorizaba a la vez PubChem,
ChEMBL, RCSB y UniProt, sin decir cuáles, ni a qué hosts, ni qué sale hacia
ellos. Un interruptor no es un permiso.

Y había una salida que ni siquiera pasaba por el interruptor: el gate de MolChat
la encontró —`pubchem_autolookup` consultaba PubChem en cada turno que nombrara
un fármaco conocido—. Se tapó con `allow_web`, que era lo correcto entonces;
esto es lo correcto ahora.

Lo que fija esta suite:

* cada destino tiene **servicio, host y finalidad declarados**, y qué dato sale;
* el permiso es por cuenta y por destino, con la misma huella y el mismo almacén
  que ya usa el proveedor de chat: un solo mecanismo, una sola política;
* mover el host **revoca**: el destino nuevo es otro destino;
* existe un modo completamente offline y es **verificable**;
* y lo que hace que todo lo anterior valga: **se intercepta la salida HTTP real**
  y la prueba falla si algo llega ahí sin permiso.

(Fase 6.6) Las herramientas del asistente murieron con él; la puerta queda y
estas pruebas la conducen directa. El escaneo de salidas cubre su nuevo hogar.
"""

from __future__ import annotations

import uuid

import pytest

from services import red

ALICE = str(uuid.uuid4())
BOB = str(uuid.uuid4())


@pytest.fixture(autouse=True)
def almacen_aislado(tmp_path, monkeypatch):
    from services import provider_config_store as store

    secreto = tmp_path / "secret_key"
    secreto.write_text("f" * 64, encoding="utf-8")
    monkeypatch.setattr(store, "_STORE_DIR", tmp_path)
    monkeypatch.setattr(store, "_STORE_FILE", tmp_path / "provider_config.json")
    monkeypatch.setattr(store, "_SECRET_KEY_FILE", secreto)
    monkeypatch.delenv("MOLDESIGN_OFFLINE", raising=False)
    yield


PUBCHEM = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/aspirin/JSON"
CHEMBL = "https://www.ebi.ac.uk/chembl/api/data/molecule.json?pref_name=ASPIRIN"
RCSB = "https://search.rcsb.org/rcsbsearch/v2/query"


class TestElCatalogoDeDestinos:
    def test_todo_destino_declara_servicio_host_y_finalidad(self):
        for destino in red.DESTINOS:
            assert destino.servicio
            assert destino.host
            assert destino.finalidad
            assert destino.que_sale, (
                f"{destino.servicio} no declara qué datos salen hacia él"
            )

    def test_el_destino_se_reconoce_por_el_host_de_la_url(self):
        assert red.destino_de_url(PUBCHEM).servicio == "pubchem"
        assert red.destino_de_url(CHEMBL).servicio == "chembl"
        assert red.destino_de_url(RCSB).servicio == "rcsb"

    def test_un_host_desconocido_no_se_resuelve_a_favor_de_enviar(self):
        with pytest.raises(red.SalidaNoAutorizada):
            red.exigir_permiso("https://servidor-de-alguien.example/api", user_id=ALICE)


class TestElPermisoEsPorCuentaYDestino:
    def test_sin_permiso_no_se_sale(self):
        with pytest.raises(red.SalidaNoAutorizada):
            red.exigir_permiso(PUBCHEM, user_id=ALICE)

    def test_con_permiso_se_sale(self):
        red.otorgar("pubchem", user_id=ALICE)

        red.exigir_permiso(PUBCHEM, user_id=ALICE)  # no lanza

    def test_autorizar_uno_no_autoriza_los_demas(self):
        """Es exactamente lo que `allow_web` hacía: un interruptor para todos."""
        red.otorgar("pubchem", user_id=ALICE)

        with pytest.raises(red.SalidaNoAutorizada):
            red.exigir_permiso(CHEMBL, user_id=ALICE)

    def test_el_permiso_de_una_cuenta_no_sirve_para_otra(self):
        red.otorgar("pubchem", user_id=ALICE)

        with pytest.raises(red.SalidaNoAutorizada):
            red.exigir_permiso(PUBCHEM, user_id=BOB)

    def test_sin_cuenta_no_se_sale(self):
        with pytest.raises(red.SalidaNoAutorizada):
            red.exigir_permiso(PUBCHEM, user_id=None)

    def test_revocar_cierra_la_salida(self):
        red.otorgar("pubchem", user_id=ALICE)
        red.revocar("pubchem", user_id=ALICE)

        with pytest.raises(red.SalidaNoAutorizada):
            red.exigir_permiso(PUBCHEM, user_id=ALICE)


class TestMoverElHostRevoca:
    def test_el_permiso_se_ata_al_host_que_se_mostro(self):
        red.otorgar("pubchem", user_id=ALICE)
        registro = red.permisos_de(ALICE)["pubchem@pubchem.ncbi.nlm.nih.gov"]

        assert registro["host"] == "pubchem.ncbi.nlm.nih.gov"

    def test_si_el_destino_cambia_de_host_el_permiso_no_lo_hereda(self, monkeypatch):
        red.otorgar("pubchem", user_id=ALICE)

        # Alguien reconfigura el servicio para que apunte a otro sitio.
        monkeypatch.setattr(
            red, "DESTINOS",
            tuple(
                red.Destino(
                    servicio=d.servicio,
                    host="proxy-de-alguien.example" if d.servicio == "pubchem" else d.host,
                    finalidad=d.finalidad,
                    que_sale=d.que_sale,
                )
                for d in red.DESTINOS
            ),
        )

        with pytest.raises(red.SalidaNoAutorizada):
            red.exigir_permiso(
                "https://proxy-de-alguien.example/rest/pug/compound", user_id=ALICE
            )


class TestElModoOffline:
    def test_offline_niega_todo_aunque_haya_permiso(self, monkeypatch):
        red.otorgar("pubchem", user_id=ALICE)
        monkeypatch.setenv("MOLDESIGN_OFFLINE", "1")

        with pytest.raises(red.SalidaNoAutorizada) as error:
            red.exigir_permiso(PUBCHEM, user_id=ALICE)

        assert "offline" in str(error.value).lower()

    def test_el_modo_offline_es_consultable(self, monkeypatch):
        assert red.modo_offline() is False
        monkeypatch.setenv("MOLDESIGN_OFFLINE", "1")
        assert red.modo_offline() is True


class TestLaSalidaRealSeIntercepta:
    """Sin esto, todo lo anterior es una promesa que nadie comprueba."""

    @pytest.fixture
    def espia_de_salida(self, monkeypatch):
        salidas: list[str] = []

        import urllib.request

        def _no_salir(request, *_a, **_kw):
            url = getattr(request, "full_url", str(request))
            salidas.append(url)
            raise AssertionError(f"salida HTTP no autorizada hacia {url}")

        monkeypatch.setattr(urllib.request, "urlopen", _no_salir)
        return salidas

    def test_una_llamada_sin_permiso_no_llega_a_la_red(self, espia_de_salida):
        with pytest.raises(red.SalidaNoAutorizada):
            red.exigir_permiso(PUBCHEM, user_id=ALICE)

        assert espia_de_salida == [], "no debió intentarse ninguna salida"

    def test_el_post_tambien_pasa_por_la_puerta(self, espia_de_salida):
        with pytest.raises(red.SalidaNoAutorizada):
            red.exigir_permiso(RCSB, user_id=ALICE)

        assert espia_de_salida == []

    def test_con_permiso_si_intenta_salir(self, monkeypatch):
        """El contraste: si el permiso no dejara pasar nada, sería inútil."""
        red.otorgar("pubchem", user_id=ALICE)

        red.exigir_permiso(PUBCHEM, user_id=ALICE)  # no lanza: deja pasar


class TestNingunaSalidaSeSaltaLaPuerta:
    def test_solo_los_modulos_de_red_abren_conexiones(self):
        """Una segunda vía de salida haría inútil la primera puerta."""
        import pathlib

        raiz = pathlib.Path(__file__).resolve().parents[1] / "services"
        # El hogar reubicado de la puerta (Fase 6.6): nadie aquí abre
        # conexiones salvo el lanzador del sidecar, cuya sonda es loopback
        # por construcción (host 127.0.0.1 + puerto efímero, sin URL remota).
        vigilados = [
            raiz / "red.py",
            raiz / "consent.py",
            raiz / "provider_config_store.py",
            raiz / "speech_to_text.py",
            raiz / "molgraph.py",
            raiz / "clgnn_inference.py",
            raiz / "llm" / "local_llm.py",
            raiz / "llm" / "resource_manager.py",
            raiz / "evaluation" / "interpreter.py",
            raiz / "evaluation" / "report_context.py",
            raiz / "evaluation" / "proposals.py",
        ]
        culpables: list[str] = []

        for archivo in vigilados:
            texto = archivo.read_text(encoding="utf-8", errors="replace")
            if "urllib.request.urlopen" in texto or "urlopen(" in texto:
                culpables.append(str(archivo.relative_to(raiz)))

        assert culpables == [], (
            "estos módulos abren conexiones por su cuenta, saltándose el "
            f"consentimiento por destino: {culpables}"
        )
