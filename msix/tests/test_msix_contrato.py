"""Autotests del contrato MSIX: identidad, version, confianza y no-regresion de NSIS.

Son rapidos y no necesitan un paquete construido. Cubren lo que un error humano
rompe en silencio y el Store solo rechaza despues de subir:

  - la identidad debe ser EXACTA; un caracter distinto y el paquete deja de ser
    actualizable para quien ya lo tenga instalado;
  - la version debe tener cuatro campos y el cuarto en 0;
  - runFullTrust debe estar declarado, porque sin el no arrancan ni el Python
    embebido ni Vina ni Open Babel;
  - la ruta NSIS NO puede haberse alterado: el encargo era anadir MSIX, no
    sustituir el instalador existente.

La aceptacion sobre el paquete instalado vive en scripts/accept_msix_store.py;
esto es la red de seguridad barata que corre en cada cambio.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
MSIX = ROOT / "msix"
CONFIG = MSIX / "msix-config.json"
MANIFIESTO = MSIX / "Package.appxmanifest"
CONF_BASE = ROOT / "frontend" / "src-tauri" / "tauri.conf.json"
CONF_PROD = ROOT / "frontend" / "src-tauri" / "tauri.conf.prod.json"
CONF_MSIX = ROOT / "frontend" / "src-tauri" / "tauri.conf.msix.json"

sys.path.insert(0, str(ROOT / "scripts"))
from build_msix import BuildAbortado, fase_sign, version_del_store  # noqa: E402

# Valores reservados en Partner Center. Se escriben aqui a mano, a proposito:
# si alguien cambia msix-config.json, esta prueba debe fallar, no adaptarse.
IDENTITY_NAME = "amezcua-dev.com.MolDesign"
IDENTITY_PUBLISHER = "CN=6441FBBA-B77A-4619-9CEB-ACEDE74573C0"
PUBLISHER_DISPLAY_NAME = "amezcua-dev.com"


def _cargar(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


# ── Identidad ───────────────────────────────────────────────────────────────

def test_configuracion_declara_la_identidad_reservada():
    ident = _cargar(CONFIG)["identidad_del_store"]
    assert ident["package_identity_name"] == IDENTITY_NAME
    assert ident["package_identity_publisher"] == IDENTITY_PUBLISHER
    assert ident["package_properties_publisher_display_name"] == PUBLISHER_DISPLAY_NAME


@pytest.mark.skipif(not MANIFIESTO.is_file(),
                    reason="Package.appxmanifest aun no generado (fase `manifest`).")
def test_el_manifiesto_generado_repite_la_identidad_exacta():
    xml = MANIFIESTO.read_text(encoding="utf-8")
    m = re.search(r'<Identity\s+Name="([^"]+)"\s+Publisher="([^"]+)"\s+Version="([^"]+)"', xml)
    assert m, "El manifiesto no tiene un bloque <Identity> legible."
    assert m.group(1) == IDENTITY_NAME
    assert m.group(2) == IDENTITY_PUBLISHER
    assert f"<PublisherDisplayName>{PUBLISHER_DISPLAY_NAME}</PublisherDisplayName>" in xml


@pytest.mark.skipif(not MANIFIESTO.is_file(),
                    reason="Package.appxmanifest aun no generado (fase manifest).")
def test_el_manifiesto_declara_webview2_como_dependencia_externa():
    xml = MANIFIESTO.read_text(encoding="utf-8")
    assert 'xmlns:win32dependencies="http://schemas.microsoft.com/appx/manifest/externaldependencies"' in xml
    assert "IgnorableNamespaces=\"uap rescap win32dependencies\"" in xml
    assert '<win32dependencies:ExternalDependency' in xml
    assert 'Name="Microsoft.WebView2"' in xml
    assert ('Publisher="CN=Microsoft Windows, O=Microsoft Corporation, '
            'L=Redmond, S=Washington, C=US"') in xml
    assert 'MinVersion="1.1.1.1"' in xml
    assert 'Optional="false"' in xml
# ── Version ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("semver,esperado", [
    ("1.0.0-alpha.2", "1.0.2.0"),
    ("1.0.0-alpha.0", "1.0.0.0"),
    ("1.0.0-beta.1", "1.0.10001.0"),
    ("1.0.0-rc.3", "1.0.20003.0"),
    ("1.0.0", "1.0.30000.0"),
    ("1.0.7", "1.0.30007.0"),
    ("2.5.1", "2.5.30001.0"),
])
def test_mapeo_de_version_del_store(semver, esperado):
    version, _ = version_del_store(semver, None)
    assert version == esperado


def test_la_version_siempre_termina_en_cero():
    """El Store reserva el cuarto campo y rechaza un paquete que lo use."""
    for semver in ("1.0.0-alpha.2", "1.0.0-beta.9", "3.1.4"):
        version, detalle = version_del_store(semver, None)
        campos = version.split(".")
        assert len(campos) == 4, f"{version} no tiene cuatro campos"
        assert campos[3] == "0", f"{version} no termina en 0"
        assert detalle["revision_es_cero"] is True


def test_los_canales_de_prerelease_son_monotonos():
    """alpha < beta < rc < final dentro de un mismo Major.Minor.

    Si el mapeo dejara de ser monotono, un envio posterior podria llevar una
    version MENOR y el Store lo rechazaria sin explicar por que.
    """
    def build(s: str) -> int:
        return int(version_del_store(s, None)[0].split(".")[2])

    assert build("1.0.0-alpha.1") < build("1.0.0-alpha.2")
    assert build("1.0.0-alpha.999") < build("1.0.0-beta.1")
    assert build("1.0.0-beta.999") < build("1.0.0-rc.1")
    assert build("1.0.0-rc.999") < build("1.0.0")


def test_campos_fuera_de_rango_abortan():
    with pytest.raises(BuildAbortado, match="65535"):
        version_del_store("1.0.0", 70000)


def test_un_semver_irreconocible_aborta_en_vez_de_inventar():
    with pytest.raises(BuildAbortado, match="semver"):
        version_del_store("1.0", None)


def test_el_override_manda_sobre_el_mapeo():
    version, detalle = version_del_store("1.0.0-alpha.2", 4242)
    assert version == "1.0.4242.0"
    assert "override" in detalle["derivacion"]


# ── Nivel de confianza ──────────────────────────────────────────────────────

@pytest.mark.skipif(not MANIFIESTO.is_file(), reason="manifiesto aun no generado")
def test_el_manifiesto_declara_run_full_trust():
    xml = MANIFIESTO.read_text(encoding="utf-8")
    assert 'Name="runFullTrust"' in xml, (
        "Sin runFullTrust el interprete Python embebido, Vina y Open Babel no "
        "pueden ejecutarse: no habria pipeline.")
    assert 'EntryPoint="Windows.FullTrustApplication"' in xml


def test_la_configuracion_declara_que_run_full_trust_es_restringida():
    """Partner Center exige justificacion escrita y la revisa una persona.

    Se comprueba que la configuracion lo diga, para que nadie envie el paquete
    creyendo que es una capacidad ordinaria.
    """
    conf = _cargar(CONFIG)["nivel_de_confianza"]
    assert conf["capability"] == "runFullTrust"
    assert conf["es_restringida"] is True
    assert conf["por_que_es_necesario"], "Debe quedar escrito POR QUE se necesita."


def test_la_configuracion_declara_la_dependencia_webview2():
    conf = _cargar(CONFIG)["dependencia_webview2"]
    assert conf["name"] == "Microsoft.WebView2"
    assert conf["publisher"] == (
        "CN=Microsoft Windows, O=Microsoft Corporation, L=Redmond, "
        "S=Washington, C=US"
    )
    assert conf["min_version"] == "1.1.1.1"
    assert conf["optional"] is False
    assert conf["por_que"]
    assert "App Installer" in conf["caveat"]
    assert "Add-AppxPackage" in conf["caveat"]
# ── No-regresion de la ruta NSIS ────────────────────────────────────────────
def test_webview2_runtime_ausente_se_detecta_y_falla_con_guia(monkeypatch):
    import accept_msix_store
    monkeypatch.setattr(accept_msix_store, "_ps_json", lambda _script: None)
    estado = accept_msix_store.webview2_runtime()
    assert estado["installed"] is False
    with pytest.raises(accept_msix_store.AceptacionFallida, match="Microsoft.WebView2"):
        accept_msix_store.comprobar_webview2_runtime()
def test_webview2_runtime_presente_se_detecta_en_el_registro(monkeypatch):
    import accept_msix_store
    monkeypatch.setattr(accept_msix_store, "_ps_json", lambda _script: {
        "path": "HKLM:\\SOFTWARE\\...",
        "pv": "130.0.2849.68",
    })

def test_la_ruta_nsis_sigue_intacta():
    """El encargo era anadir MSIX, no sustituir el instalador existente."""
    base = _cargar(CONF_BASE)
    assert base["bundle"]["targets"] == ["nsis"], (
        "tauri.conf.json dejo de apuntar a NSIS: la ruta existente se ha alterado.")
    assert base["bundle"]["active"] is True
    assert "nsis" in base["bundle"]["windows"]


def test_la_config_msix_no_bundlea_instalador():
    msix = _cargar(CONF_MSIX)
    assert msix["bundle"]["active"] is False
    assert msix["bundle"]["targets"] == []


def test_la_csp_del_build_de_store_es_la_de_produccion():
    """Relajar la CSP en Store daria un binario distinto del validado."""
    prod = _cargar(CONF_PROD)["app"]["security"]["csp"]
    msix = _cargar(CONF_MSIX)["app"]["security"]["csp"]
    assert msix == prod, "La CSP del build MSIX difiere de la de produccion."


def test_la_config_msix_no_lleva_claves_de_comentario():
    """El esquema de Tauri las rechaza y el build falla con un error oscuro.

    Paso de verdad durante la implementacion: `_nota` y `_csp` tumbaron el build
    con «Additional properties are not allowed».
    """
    def sin_guion_bajo(d, ruta=""):
        for k, v in d.items():
            assert not k.startswith("_"), f"Clave de comentario en {ruta}/{k}"
            if isinstance(v, dict):
                sin_guion_bajo(v, f"{ruta}/{k}")

    sin_guion_bajo(_cargar(CONF_MSIX))


# ── Alcance: nada juridico ni cientifico ────────────────────────────────────

def test_el_alcance_excluye_licencias_y_artefactos_cientificos():
    fuera = _cargar(CONFIG)["fuera_de_alcance_de_este_trabajo"]
    texto = " ".join(fuera).lower()
    for termino in ("licencia", "checkpoint", "partner center"):
        assert termino in texto, f"El alcance no menciona {termino!r}."


def test_winapp_recibe_el_certificado_como_argumento_posicional(monkeypatch, tmp_path):
    """Fija la CLI de winapp 0.6.x que se usa en la maquina de release."""
    import build_msix

    paquete = tmp_path / "app.msix"
    paquete.write_bytes(b"msix")
    cert = tmp_path / "devcert.pfx"
    cert.write_bytes(b"pfx")
    llamadas = []

    # El certificado cuelga de la RAIZ de produccion, no de la carpeta de la
    # version: es el mismo para todos los envios.
    monkeypatch.setattr(build_msix, "DIST_RAIZ", tmp_path)
    monkeypatch.setattr(build_msix, "DIST", tmp_path / "v1.0.2.0")
    monkeypatch.setattr(build_msix, "ROOT", tmp_path)
    monkeypatch.setattr(build_msix, "_correr", lambda cmd, **_: llamadas.append(cmd) or "")

    fase_sign(_cargar(CONFIG), paquete, Path("winapp.exe"))

    assert llamadas == [[Path("winapp.exe"), "sign", str(paquete), str(cert)]]
    assert "--cert" not in llamadas[0]


def test_acl_de_windowsapps_no_se_clasifica_como_runtime_ausente(monkeypatch):
    """Una ACL del contenedor no demuestra que falte el runtime firmado."""
    import accept_msix_store

    def acceso_denegado(_self):
        raise PermissionError(5, "Acceso denegado")

    monkeypatch.setattr(Path, "is_file", acceso_denegado)
    resultado = accept_msix_store.comprobar_escritura_fuera(
        r"C:\Program Files\WindowsApps\amezcua-dev.com.MolDesign_test"
    )

    assert resultado["estado"] == "NO_CONCLUYENTE_ACL_WINDOWSAPPS"
    assert "runtime existe dentro del MSIX firmado" in resultado["nota"]

def test_aumid_usa_package_family_name_y_no_package_full_name(monkeypatch):
    """Windows lanza PackageFamilyName!ApplicationId, no PackageFullName!Id."""
    import accept_msix_store

    monkeypatch.setattr(accept_msix_store, "_ps_json", lambda _script: "MolDesign")
    aumid = accept_msix_store.aumid_de(
        "amezcua-dev.com.MolDesign_he54t0vnbfj1r",
        "amezcua-dev.com.MolDesign_1.0.2.0_x64__he54t0vnbfj1r",
    )

    assert aumid == "amezcua-dev.com.MolDesign_he54t0vnbfj1r!MolDesign"
    assert "_1.0.2.0_x64__" not in aumid

def test_descubrimiento_por_rango_exige_identidad_modo_y_vina_del_paquete(monkeypatch, tmp_path):
    import accept_msix_store

    install = r"C:\Program Files\WindowsApps\amezcua-dev.com.MolDesign_test"

    def health(base, metodo, ruta, timeout=300, cuerpo=None):
        port = int(base.rsplit(":", 1)[1])
        if port == 8002:
            return 200, {"app": "otro-producto", "app_mode": "DESKTOP", "components": {}}
        if port == 8003:
            return 200, {
                "app": "mol-design",
                "app_mode": "DESKTOP",
                "components": {"vina": {"path": install + r"\resources\tools\vina\vina.exe"}},
            }
        return None, {}

    monkeypatch.setattr(accept_msix_store, "_http", health)
    assert accept_msix_store.localizar_backend(tmp_path / "sin-logs", install, 1) == (
        "http://127.0.0.1:8003"
    )


def test_evaluacion_avanzada_sella_los_mismos_parametros_en_preflight_y_submit(monkeypatch):
    import accept_msix_store

    vistos = {}

    def api(base, metodo, ruta, cuerpo=None, timeout=300):
        if ruta == "/evaluation/preflight":
            vistos["preflight"] = cuerpo
            return 200, {
                "technical_blockers": [],
                "input_fingerprint": "sha256:" + "a" * 64,
                "effective_config": {"grid_center": [1, 2, 3], "grid_size": [20, 20, 20]},
}
        if ruta == "/evaluation/submit":
            vistos["submit"] = cuerpo
            return 202, {"task_id": "task-1"}
        if ruta == "/evaluation/status/task-1":
            return 200, {"status": "SUCCESS", "result": {"molecule_id": "mol-1"}}
        raise AssertionError(ruta)

    monkeypatch.setattr(accept_msix_store, "_http", api)
    accept_msix_store.evaluar("http://127.0.0.1:8001", "CC", "advanced", True)

    pre = vistos["preflight"]
    submit = vistos["submit"]
    docking = submit["pipeline_config"]["stage_params"]["docking"]
    assert pre["docking_engine"] == submit["pipeline_config"]["docking_engine"]
    assert pre["exhaustiveness"] == docking["exhaustiveness"]
    assert pre["num_poses"] == docking["num_poses"]
    assert pre["conformers"] == submit["pipeline_config"]["stage_params"]["conformer"]["conformers"]


# ── Exclusión de artefactos PDBbind-derivados ────────────────────────────────

def test_los_artefactos_pdbbind_derivados_se_excluyen_y_apuntan_a_archivos_reales():
    """La exclusión del canal de distribución debe ser una lista VIVA.

    Un guardián que apunta a archivos que ya no existen 'protege' algo que no
    viajaría de todos modos; y si un artefacto PDBbind-derivado entra de nuevo al
    runtime sin estar en la lista, volvería a distribuirse en silencio. Se
    comprueba que cada entrada apunta a un archivo real y que ninguna coincide
    con los 'exigidos' del runtime completo de la aceptación.
    """
    import build_msix

    excluidos = build_msix.ARTEFACTOS_PDBBIND_EXCLUIDOS
    assert excluidos, "la lista de exclusión PDBbind está vacía"
    for rel in excluidos:
        ruta = ROOT / "frontend" / "src-tauri" / rel
        assert ruta.is_file(), (
            f"la exclusión apunta a un archivo inexistente: {rel}; si ya no existe, "
            "quítalo de la lista o pierde su función de gate."
        )
    # Ninguno debe estar entre los exigidos del "runtime completo" (la aceptación
    # no puede exigir a la vez un artefacto que se excluye por motivos jurídicos).
    import accept_msix_store

    exigidos = [
        "resources/python/python.exe",
        "resources/backend/api/main.py",
        "resources/tools/vina/vina.exe",
        "resources/tools/openbabel/bin/obabel.exe",
        "resources/rescoring/artifacts/model-manifest.json",
        "resources/curated_targets.json",
        "resources/runtime-manifest.json",
        "moldesign.exe",
    ]
    for rel in excluidos:
        assert rel not in exigidos, f"{rel} está entre los exigidos pero debe excluirse"

# ── Distribucion: donde aterrizan los artefactos de release ─────────────────
#
# La raiz esta escrita A MANO aqui, igual que la identidad: si alguien cambia
# msix-config.json, esta prueba falla en vez de adaptarse al cambio.
RAIZ_DE_PRODUCCION = r"E:\rel"


def test_la_configuracion_y_el_script_declaran_la_misma_raiz_de_produccion():
    import build_msix

    cfg = _cargar(CONFIG)
    assert cfg["distribucion"]["raiz_de_produccion"] == RAIZ_DE_PRODUCCION
    assert str(build_msix.DIST_RAIZ) == RAIZ_DE_PRODUCCION


def test_la_raiz_de_produccion_no_cuelga_del_arbol_de_desarrollo():
    """El punto entero de la separacion: produccion fuera del repo y de su disco."""
    import build_msix

    with pytest.raises(ValueError):
        build_msix.DIST_RAIZ.relative_to(ROOT)
    assert build_msix.DIST_RAIZ.anchor.upper() != Path(ROOT).anchor.upper(), (
        "la raiz de produccion esta en el mismo disco que el desarrollo; "
        "un fallo de ese disco se llevaria el paquete sellado y su evidencia"
    )


def test_cada_version_estrena_carpeta():
    """Nunca se reutiliza un directorio ya sellado."""
    import build_msix

    dist, layout = build_msix.resolver_dist(Path(r"E:\rel"), "1.0.2.0")
    assert dist == Path(r"E:\rel\v1.0.2.0")
    assert layout == Path(r"E:\rel\v1.0.2.0\layout")

    otra, _ = build_msix.resolver_dist(Path(r"E:\rel"), "1.0.3.0")
    assert otra != dist, "dos versiones distintas no pueden compartir carpeta"


def test_sin_unidad_de_produccion_el_build_aborta_en_vez_de_replegarse():
    """Replegarse al disco de desarrollo dejaria la evidencia mintiendo."""
    import build_msix

    with pytest.raises(BuildAbortado) as e:
        build_msix.resolver_dist(Path(r"Z:\rel"), "1.0.2.0")
    assert "no esta disponible" in str(e.value)


def test_una_raiz_larga_aborta_antes_de_copiar(monkeypatch, tmp_path):
    """El margen frente a MAX_PATH es de decenas de caracteres, no de cientos."""
    import build_msix

    # Runtime de mentira con una ruta relativa honda, como las de torch.
    recursos = tmp_path / "resources"
    hondo = recursos.joinpath(*[f"nivel{i:02d}" for i in range(12)])
    hondo.mkdir(parents=True)
    (hondo / "LICENSE.txt").write_text("x", encoding="utf-8")
    monkeypatch.setattr(build_msix, "RESOURCES", recursos)

    corta = Path(r"E:\rel\v1.0.2.0\layout")
    assert build_msix._verificar_max_path(corta) < build_msix.MAX_PATH

    larga = Path("E:\\") / ("x" * 200) / "layout"
    with pytest.raises(BuildAbortado) as e:
        build_msix._verificar_max_path(larga)
    assert "demasiado larga" in str(e.value)


# ── Documentos legales que deben viajar en el paquete ───────────────────────
#
# `bundle_helper.py` copia frontend/public/legal -> resources/licenses. Lo que no
# esta en esa carpeta NO llega al usuario, por mucho que exista en la raiz del
# repositorio: es exactamente lo que pasaba con la politica de privacidad.

# Pares (copia que VIAJA -> original canonico en la raiz del repositorio). El
# staging copia frontend/public/legal a resources/licenses: la copia es lo que el
# usuario lee, el original es lo que el proyecto declara.
PARES_LEGALES = {
    "licenses/POLYFORM-NONCOMMERCIAL-1.0.0.txt": "LICENSE",
    "licenses/MOLDESIGN-MODELS.txt": "LICENSE-MODELS",
    "licenses/COMMERCIAL-LICENSE.md": "COMMERCIAL-LICENSE.md",
    "PRIVACY.md": "PRIVACY.md",
}

# Divergencias conocidas, pendientes de decision del autor. Se vacio el
# 2026-09-12: LICENSE-MODELS y COMMERCIAL-LICENSE.md se hicieron coherentes con
# la determinacion sobre PDBbind y sus copias se regeneraron del original. Debe
# seguir vacia: cualquier entrada nueva es un texto que el usuario lee distinto
# de lo que el proyecto declara.
DIVERGENCIAS_LEGALES_CONOCIDAS: set[str] = set()


def test_la_politica_de_privacidad_viaja_en_el_paquete():
    """El Store exige politica de privacidad y el usuario debe poder leerla."""
    enviada = ROOT / "frontend" / "public" / "legal" / "PRIVACY.md"
    assert enviada.is_file(), (
        "PRIVACY.md no esta en frontend/public/legal: no llegaria al paquete, "
        "porque el staging solo copia esa carpeta a resources/licenses."
    )


def test_la_politica_enviada_no_se_desincroniza_de_la_del_repositorio():
    """Dos copias del mismo documento se separan solas si nadie lo comprueba."""
    original = ROOT / "PRIVACY.md"
    enviada = ROOT / "frontend" / "public" / "legal" / "PRIVACY.md"
    assert original.read_bytes() == enviada.read_bytes(), (
        "PRIVACY.md de la raiz y la copia que viaja en el paquete difieren. "
        "El usuario estaria leyendo una politica distinta de la publicada."
    )


def test_los_textos_legales_exigidos_viajan():
    """Lo que no esta en frontend/public/legal NO llega al usuario."""
    legal = ROOT / "frontend" / "public" / "legal"
    for rel in PARES_LEGALES:
        assert (legal / rel).is_file(), f"{rel} no viaja en el paquete"


def test_las_copias_enviadas_no_se_desincronizan_del_original():
    """El usuario debe leer el MISMO texto que el proyecto declara.

    Hoy hay dos divergencias reales: el parrafo sobre PDBbind que `bf50af3`
    anadio a LICENSE-MODELS y a COMMERCIAL-LICENSE.md nunca llego a las copias
    que viajan. Son decision del autor -no se editan textos de licencia desde
    aqui-, asi que quedan registradas como lista VIVA: si aparece una tercera
    divergencia el gate avisa, y cuando el autor resuelva una, el gate obliga a
    quitarla de la lista en vez de dejarla enterrada.
    """
    legal = ROOT / "frontend" / "public" / "legal"
    divergen = set()
    for rel, canonico in PARES_LEGALES.items():
        enviada = legal / rel
        original = ROOT / canonico
        if not enviada.is_file() or not original.is_file():
            continue
        if enviada.read_bytes() != original.read_bytes():
            divergen.add(rel)

    nuevas = divergen - DIVERGENCIAS_LEGALES_CONOCIDAS
    resueltas = DIVERGENCIAS_LEGALES_CONOCIDAS - divergen
    assert not nuevas, (
        f"Texto legal enviado que ya no coincide con el original: {sorted(nuevas)}. "
        "El usuario leeria una version distinta de la que el proyecto declara."
    )
    assert not resueltas, (
        f"Estas divergencias ya estan resueltas: {sorted(resueltas)}. "
        "Quitalas de DIVERGENCIAS_LEGALES_CONOCIDAS o el gate deja de vigilar."
    )


# ── Coherencia de la version entre los cinco sitios que la declaran ─────────

# No hay fuente unica de version en el proyecto, y cada consumidor lee la suya:
#   tauri.conf.json  -> de aqui deriva la version del MSIX
#   Cargo.toml       -> recurso de version del exe
#   package.json     -> frontend
#   backend/api/main.py (APP_VERSION) -> lo que responde /health y lo que graba
#                       la evidencia de aceptacion
#   lib/softwareCatalog.ts (PRODUCT.version) -> lo que el usuario ve en «Acerca de»
#
# Estaban desalineados: cuatro decian 1.0.0-alpha.2 y la pantalla «Acerca de»
# decia 1.0.0. Un envio a Store donde el paquete y la propia app declaran
# versiones distintas es exactamente el detalle que delata un producto sin
# terminar.
FUENTES_DE_VERSION = {
    "frontend/src-tauri/tauri.conf.json": r'"version"\s*:\s*"([^"]+)"',
    "frontend/src-tauri/Cargo.toml": r'^version\s*=\s*"([^"]+)"',
    "frontend/package.json": r'"version"\s*:\s*"([^"]+)"',
    "backend/api/main.py": r'^APP_VERSION\s*=\s*"([^"]+)"',
    "frontend/lib/softwareCatalog.ts": r'version:\s*"([^"]+)"',
}


def test_los_cinco_sitios_declaran_la_misma_version():
    import re as _re

    encontradas = {}
    for rel, patron in FUENTES_DE_VERSION.items():
        texto = (ROOT / rel).read_text(encoding="utf-8")
        m = _re.search(patron, texto, _re.M)
        assert m, f"no se pudo leer la version en {rel}"
        encontradas[rel] = m.group(1)

    distintas = set(encontradas.values())
    assert len(distintas) == 1, (
        "La version no coincide entre los sitios que la declaran: "
        + ", ".join(f"{k}={v}" for k, v in encontradas.items())
    )


def test_la_version_del_store_sale_de_la_version_del_producto():
    """El numero que ve el usuario en la ficha debe derivar del producto."""
    import json as _json

    cfg = _cargar(CONFIG)
    conf = _cargar(CONF_BASE)
    version, detalle = version_del_store(
        conf["version"], cfg["version_del_store"].get("store_build_override"))

    assert version == "1.0.1.0", (
        f"La version del Store es {version}. Se decidio 1.0.1.0 para el segundo "
        "envio; cambiarlo es politica de publicacion y no admite retroceso una "
        "vez publicado."
    )
    assert detalle["revision_es_cero"] is True
    assert _json is not None


def test_la_interfaz_no_escribe_la_version_a_mano():
    """Una version literal en JSX no la ve el gate de las cinco fuentes.

    Paso de verdad: los cinco declarantes decian 1.0.0 y la aplicacion seguia
    mostrando «v1.0.0-alpha.2» en el pie, en el lanzador y en el menu de
    opciones, porque eran cadenas escritas a mano. Un producto que se envia como
    1.0.0.0 y se presenta como alpha.2 al usuario esta a medio terminar.
    """
    import re as _re

    patron = _re.compile(r"v?\d+\.\d+\.\d+(?:-[A-Za-z0-9.]+)?")
    sospechosas = []
    for carpeta in ("frontend/app", "frontend/components"):
        base = ROOT / carpeta
        if not base.is_dir():
            continue
        for f in base.rglob("*.tsx"):
            if "__tests__" in str(f) or ".test." in f.name:
                continue
            for n, linea in enumerate(
                f.read_text(encoding="utf-8", errors="replace").splitlines(), 1
            ):
                # Solo lo que el usuario ve: un nodo de texto JSX.
                if ">" not in linea or "<" not in linea:
                    continue
                if "PRODUCT.version" in linea:
                    continue
                # La version de una LICENCIA no es la del producto: «PolyForm
                # Noncommercial 1.0.0» es el nombre de la licencia.
                if any(x in linea for x in ("PolyForm", "GPL", "Apache", "MIT",
                                            "License", "Licencia", "licencia")):
                    continue
                for m in patron.finditer(linea):
                    if m.group(0).count(".") == 2:
                        sospechosas.append(
                            f"{f.relative_to(ROOT)}:{n}: {m.group(0)}"
                        )

    assert not sospechosas, (
        "Version escrita a mano en la interfaz; debe salir de PRODUCT.version:\n  "
        + "\n  ".join(sospechosas[:10])
    )
