"""El inventario de licencias, puesto a prueba contra defectos fabricados.

# Por qué esto existe

Auditoría Luna, bloque 1 (docs/86). `generate_sbom.py --check` salía 1 sobre el
árbol de desarrollo, y detrás había tres defectos de la misma familia —un
inventario que informa de lo que *él* sabe leer y calla lo demás—:

* `_binarios()` omitía en silencio lo que no estuviera en la máquina. El SBOM
  guardado decía 2 binarios; `bundle_helper` empaqueta 4. Nada distinguía «no
  viaja» de «no estaba en el árbol donde se generó».
* Las 575 crates Rust salían con licencia vacía, porque `cargo metadata
  --offline` falla si alguna crate de OTRA plataforma no está en la caché, y el
  respaldo (`Cargo.lock`) no trae licencias. El apartado `sin_licencia_declarada`
  ni siquiera tenía una lista Rust: «rust: 0» se leía como «sin riesgo» cuando
  era «sin mirar».
* El párrafo de licencias de AGENTS.md describía una clasificación que el SBOM ya
  no tiene, con un recuento que no cuadra.

Estas pruebas fabrican cada defecto y exigen que el inventario lo marque; y
comprueban también el caso sano, para que un detector que dijera «incompleto»
siempre tampoco pasara.
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "scripts" / "generate_sbom.py"
SBOM = RAIZ / "docs" / "api" / "sbom.json"
AGENTS = RAIZ / "AGENTS.md"


def _cargar():
    if not SCRIPT.is_file():
        pytest.skip("no está scripts/generate_sbom.py")
    spec = importlib.util.spec_from_file_location("_generate_sbom", SCRIPT)
    modulo = importlib.util.module_from_spec(spec)
    sys.modules["_generate_sbom"] = modulo
    assert spec.loader is not None
    spec.loader.exec_module(modulo)
    return modulo


sbom_mod = _cargar()


# ── cargo metadata fabricado ─────────────────────────────────────────────


def _crate(nombre: str, licencia: str | None = "MIT", version: str = "1.0.0") -> dict:
    return {
        "id": f"{nombre} {version}",
        "name": nombre,
        "version": version,
        "license": licencia,
        "repository": f"https://example.org/{nombre}",
        "source": "registry+https://github.com/rust-lang/crates.io-index",
        "manifest_path": f"/x/{nombre}/Cargo.toml",
    }


def _metadata(crates: list[dict], aristas: list[tuple], raiz: str = "app 1.0.0") -> dict:
    """`aristas`: (origen, destino, tipo) con tipo None | "build" | "dev"."""
    nodos: dict[str, list] = {c["id"]: [] for c in crates}
    for origen, destino, tipo in aristas:
        nodos[origen].append(
            {"pkg": destino, "dep_kinds": [{"kind": tipo, "target": None}]}
        )
    return {
        "packages": crates,
        "resolve": {
            "root": raiz,
            "nodes": [{"id": i, "deps": d} for i, d in nodos.items()],
        },
    }


@pytest.fixture
def grafo():
    """app → serde (normal) → itoa (normal); app → cc (build); app → mock (dev)."""
    return _metadata(
        [
            _crate("app", "PolyForm-Noncommercial-1.0.0", "1.0.0"),
            _crate("serde", "MIT OR Apache-2.0"),
            _crate("itoa", "MIT"),
            _crate("cc", "MIT"),
            _crate("mockall", "MIT"),
        ],
        [
            ("app 1.0.0", "serde 1.0.0", None),
            ("serde 1.0.0", "itoa 1.0.0", None),
            ("app 1.0.0", "cc 1.0.0", "build"),
            ("app 1.0.0", "mockall 1.0.0", "dev"),
        ],
    )


def test_las_crates_enlazadas_son_la_clausura_normal_sin_la_raiz(grafo):
    enlazadas, _ = sbom_mod._clasificar_crates(grafo)
    assert [c["nombre"] for c in enlazadas] == ["itoa", "serde"]
    assert "app" not in {c["nombre"] for c in enlazadas}, (
        "el producto no es una dependencia de terceros de sí mismo"
    )


def test_las_de_construccion_se_separan_y_las_de_desarrollo_no_entran(grafo):
    enlazadas, construccion = sbom_mod._clasificar_crates(grafo)
    assert [c["nombre"] for c in construccion] == ["cc"]
    todas = {c["nombre"] for c in enlazadas} | {c["nombre"] for c in construccion}
    assert "mockall" not in todas, "una dependencia de desarrollo no se distribuye"


def test_una_licencia_que_es_solo_adorno_no_cuenta_como_declarada():
    """MDAnalysis copia su LICENSE en la metadata y la primera línea es una fila de «=».

    El SBOM la registraba como su licencia, y un paquete LGPL-3.0-or-later quedaba
    fuera de toda clasificación (2026-10-11). Se resuelve con el archivo del paquete,
    y lo que sea sólo adorno y no tenga resolución queda sin licencia, a la vista.
    """
    adorno = "=" * 74
    resuelto = sbom_mod._resolver([{"nombre": "MDAnalysis", "version": "2.10.0", "licencia": adorno}])
    assert resuelto[0]["licencia"] == "LGPL-3.0-or-later"
    assert resuelto[0]["licencia_origen"] == "archivo del paquete"
    desconocido = [{"nombre": "otro", "version": "1", "licencia": adorno}]
    assert sbom_mod._sin_licencia(sbom_mod._resolver(desconocido)) == desconocido
    # Control: una licencia de verdad no se toca.
    assert sbom_mod._sin_licencia([{"nombre": "x", "version": "1", "licencia": "MIT"}]) == []


def test_una_crate_sin_licencia_queda_declarada_como_tal():
    datos = _metadata(
        [_crate("app", "MIT"), _crate("rara", None)],
        [("app 1.0.0", "rara 1.0.0", None)],
    )
    enlazadas, _ = sbom_mod._clasificar_crates(datos)
    assert enlazadas[0]["licencia"] == ""
    assert [c["nombre"] for c in sbom_mod._sin_licencia(enlazadas)] == ["rara"]


# ── el origen de la licencia Rust ────────────────────────────────────────


def _falso_subprocess(monkeypatch, *, salida: str = "", codigo: int = 0, capturar=None):
    def falso(argumentos, **_):
        if capturar is not None:
            capturar.append(list(argumentos))
        return subprocess.CompletedProcess(argumentos, codigo, stdout=salida, stderr="boom")

    monkeypatch.setattr(sbom_mod.subprocess, "run", falso)


def test_cargo_metadata_se_pide_filtrado_a_la_plataforma_del_instalador(monkeypatch, grafo):
    """Sin el filtro, cargo exige bajar crates de Android o Linux que el
    instalador de Windows no lleva, falla offline, y el inventario cae a un
    `Cargo.lock` sin licencias: así salieron las 575 en blanco."""
    llamadas: list[list[str]] = []
    _falso_subprocess(monkeypatch, salida=json.dumps(grafo), capturar=llamadas)
    resultado = sbom_mod._paquetes_rust()
    assert "--filter-platform" in llamadas[0]
    assert sbom_mod.PLATAFORMA_RUST in llamadas[0]
    assert sbom_mod.PLATAFORMA_RUST == "x86_64-pc-windows-msvc"
    assert resultado["licencias_verificadas"] is True
    assert resultado["plataforma"] == sbom_mod.PLATAFORMA_RUST


def test_si_cargo_no_resuelve_el_inventario_se_declara_no_verificado(monkeypatch, tmp_path):
    """El respaldo no puede hacerse pasar por inventario completo."""
    lock = tmp_path / "Cargo.lock"
    lock.write_text(
        '[[package]]\nname = "app"\nversion = "1.0.0"\n\n'
        '[[package]]\nname = "serde"\nversion = "1.0.0"\n'
        'source = "registry+https://github.com/rust-lang/crates.io-index"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(sbom_mod, "CARGO_LOCK", lock)
    _falso_subprocess(monkeypatch, codigo=101)
    resultado = sbom_mod._paquetes_rust()
    assert resultado["licencias_verificadas"] is False
    assert [c["nombre"] for c in resultado["enlazadas"]] == ["serde"], (
        "el respaldo conserva nombre y versión, sin el propio producto"
    )
    assert all(c["licencia"] == "" for c in resultado["enlazadas"])
    assert "Cargo.lock" in resultado["fuente"]


def test_cargo_ausente_tambien_es_no_verificado(monkeypatch, tmp_path):
    lock = tmp_path / "Cargo.lock"
    lock.write_text(
        '[[package]]\nname = "serde"\nversion = "1.0.0"\n'
        'source = "registry+https://github.com/rust-lang/crates.io-index"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(sbom_mod, "CARGO_LOCK", lock)

    def sin_cargo(*_a, **_k):
        raise FileNotFoundError("cargo")

    monkeypatch.setattr(sbom_mod.subprocess, "run", sin_cargo)
    assert sbom_mod._paquetes_rust()["licencias_verificadas"] is False


# ── los binarios que viajan ──────────────────────────────────────────────

AVISOS_FALSOS = (
    "| Componente | Versión | Función | Licencia / estado | Fuente |\n"
    "|---|---:|---|---|---|\n"
    "| AutoDock Vina | 1.2.7 | Docking | Apache-2.0 | https://x |\n"
    "| xTB | 6.7.1 | Semiempírico | LGPL-3.0-or-later | https://x |\n"
    "| llama.cpp | b10199 | Inferencia | MIT | https://x |\n"
)


def _arbol(tmp_path: Path, *, con: tuple[str, ...], avisos: str = AVISOS_FALSOS) -> Path:
    for herramienta in con:
        ruta = tmp_path / sbom_mod.BINARIOS[herramienta][0]
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_bytes(f"binario-{herramienta}".encode())
    manifiesto = tmp_path / "tools" / "openbabel" / "openbabel-manifest.json"
    if "openbabel" in con:
        manifiesto.write_text(
            json.dumps({
                "programa": "Open Babel", "version_paquete": "3.1.1.23",
                "licencia_spdx": "GPL-2.0-only", "procedencia": "wheel",
            }),
            encoding="utf-8",
        )
    if "molcy" in con:
        (tmp_path / "tools" / "molcy" / "molcy-manifest.json").write_text(
            json.dumps({
                "programa": "Molcy (motor de vídeo de MolDesign)", "licencia_spdx": "GPL-3.0-or-later",
                "fuente": {"proyecto": "proyect3d", "rama": "molcy/integracion", "commit": "63daa7953d925b562e9d29df08485202f19f221e"},
                "archivos": {"scripts/maestro.py": {"bytes": 1, "sha256": "0" * 64}}, "sha256_conjunto": "f" * 64,
            }),
            encoding="utf-8",
        )
    if "molchat" in con:
        (tmp_path / "tools" / "molchat" / "molchat-manifest.json").write_text(
            json.dumps({
                "programa": "MolChat (asistente de laboratorio de MolDesign)", "version": "0.1.0",
                "licencia_spdx": "GPL-3.0-or-later",
                "fuente": {"proyecto": "moldesign-molchat", "rama": "main", "commit": "b" * 40},
                "archivos": {"src/molchat_agent/__main__.py": {"bytes": 1, "sha256": "0" * 64}},
                "sha256_conjunto": "e" * 64,
            }),
            encoding="utf-8",
        )
    destino = tmp_path / "frontend" / "public" / "legal"
    destino.mkdir(parents=True, exist_ok=True)
    (destino / "THIRD_PARTY_NOTICES.md").write_text(avisos, encoding="utf-8")
    return tmp_path


def test_los_binarios_del_sbom_son_las_herramientas_que_empaqueta_bundle_helper():
    """Una sola fuente: si el instalador empieza a llevar otra herramienta, el
    SBOM tiene que enterarse sin que nadie se acuerde de actualizarlo."""
    sys.path.insert(0, str(RAIZ / "scripts"))
    import bundle_helper

    assert set(sbom_mod.BINARIOS) == set(bundle_helper.HERRAMIENTAS_EMPAQUETADAS)
    assert set(bundle_helper.HERRAMIENTAS_CRITICAS) <= set(bundle_helper.HERRAMIENTAS_EMPAQUETADAS)


def test_un_binario_opcional_ausente_se_declara_en_vez_de_callarse(tmp_path):
    raiz = _arbol(tmp_path, con=("vina", "openbabel", "molcy"))
    presentes, ausentes = sbom_mod._binarios(raiz)
    assert [b["nombre"] for b in presentes] == ["vina.exe", "obabel.exe", "maestro.py"]
    assert sorted(a["herramienta"] for a in ausentes) == ["llama", "molchat", "xtb"]
    assert all("no viaja" in a["consecuencia"] for a in ausentes)


def test_un_binario_critico_ausente_aborta(tmp_path):
    """`bundle_helper` aborta sin Vina u Open Babel; un SBOM sin ellos describiría
    un instalador que no se puede construir."""
    raiz = _arbol(tmp_path, con=("vina", "xtb", "llama"))
    with pytest.raises(SystemExit) as salida:
        sbom_mod._binarios(raiz)
    assert "openbabel" in str(salida.value).lower()


def test_el_motor_molcy_es_critico_y_su_licencia_sale_de_su_manifiesto(tmp_path):
    """El motor viaja en el instalador: sin él no hay vídeos, así que no se omite en silencio."""
    raiz = _arbol(tmp_path, con=("vina", "xtb", "llama", "openbabel"))
    with pytest.raises(SystemExit) as salida:
        sbom_mod._binarios(raiz)
    assert "molcy" in str(salida.value).lower()
    raiz = _arbol(tmp_path, con=("vina", "xtb", "llama", "openbabel", "molcy", "molchat"))
    presentes, ausentes = sbom_mod._binarios(raiz)
    motor = {b["nombre"]: b for b in presentes}["maestro.py"]
    assert not ausentes
    assert motor["licencia"] == "GPL-3.0-or-later"
    assert motor["licencia_origen"] == "tools/molcy/molcy-manifest.json"
    assert motor["version"] == "63daa7953d92"
    assert motor["procedencia"]["rama"] == "molcy/integracion"
    assert motor["ficheros"] == 1 and len(motor["sha256_conjunto"]) == 64


def test_el_sidecar_molchat_es_opcional_y_su_licencia_sale_de_su_manifiesto(tmp_path):
    """MolDesign funciona sin sidecar: su ausencia se declara, no aborta. Si
    está, programa, versión y licencia salen del manifiesto vendorizado."""
    raiz = _arbol(tmp_path, con=("vina", "xtb", "llama", "openbabel", "molcy"))
    presentes, ausentes = sbom_mod._binarios(raiz)
    assert [a["herramienta"] for a in ausentes] == ["molchat"]
    raiz = _arbol(tmp_path, con=("vina", "xtb", "llama", "openbabel", "molcy", "molchat"))
    presentes, ausentes = sbom_mod._binarios(raiz)
    assert not ausentes
    lado = {b["nombre"]: b for b in presentes}["__main__.py"]
    assert lado["licencia"] == "GPL-3.0-or-later"
    assert lado["licencia_origen"] == "tools/molchat/molchat-manifest.json"
    assert lado["version"] == "0.1.0"
    assert lado["procedencia"]["rama"] == "main"
    assert lado["ficheros"] == 1 and len(lado["sha256_conjunto"]) == 64


def test_los_binarios_toman_su_licencia_del_aviso_del_producto(tmp_path):
    raiz = _arbol(tmp_path, con=("vina", "xtb", "llama", "openbabel", "molcy", "molchat"))
    presentes, ausentes = sbom_mod._binarios(raiz)
    assert not ausentes
    por_nombre = {b["nombre"]: b for b in presentes}
    assert por_nombre["vina.exe"]["licencia"] == "Apache-2.0"
    assert por_nombre["xtb.exe"]["licencia"] == "LGPL-3.0-or-later"
    assert por_nombre["llama-server.exe"]["licencia"] == "MIT"
    assert por_nombre["obabel.exe"]["licencia"] == "GPL-2.0-only"
    # Una declaración del producto no es un archivo de licencia leído del binario:
    # el SBOM lo dice, en vez de dejar que parezca más de lo que es.
    for nombre in ("vina.exe", "xtb.exe", "llama-server.exe"):
        assert "THIRD_PARTY_NOTICES" in por_nombre[nombre]["licencia_origen"]
    assert all(len(b["sha256"]) == 64 for b in presentes)


def test_un_binario_sin_fila_en_los_avisos_queda_sin_licencia(tmp_path):
    sin_xtb = AVISOS_FALSOS.replace("| xTB | 6.7.1 | Semiempírico | LGPL-3.0-or-later | https://x |\n", "")
    raiz = _arbol(tmp_path, con=("vina", "xtb", "llama", "openbabel", "molcy"), avisos=sin_xtb)
    presentes, _ = sbom_mod._binarios(raiz)
    assert [b["nombre"] for b in sbom_mod._sin_licencia(presentes)] == ["xtb.exe"]


# ── la cobertura bloquea la afirmación global ────────────────────────────


def _sbom_falso(*, rust_sin_licencia: int = 0, binarios_sin_licencia: int = 0) -> dict:
    return {
        "python_embed": {"total": 0, "paquetes": []},
        "npm_produccion": {"total": 0, "paquetes": []},
        "rust_produccion": {"total": 0, "paquetes": [], "licencias_verificadas": True},
        "binarios": [],
        "dependencias_de_construccion": {"python": [], "rust": []},
        "sin_licencia_declarada": {
            "python": [], "npm": [],
            "rust": [{"nombre": "x"}] * rust_sin_licencia,
            "binarios": [{"nombre": "y"}] * binarios_sin_licencia,
        },
        "cobertura_de_licencias": sbom_mod._cobertura(
            python=[], npm=[],
            rust=[{"nombre": "x", "licencia": ""}] * rust_sin_licencia,
            binarios=[{"nombre": "y", "licencia": ""}] * binarios_sin_licencia,
            rust_verificado=True,
        ),
    }


def test_la_cobertura_es_completa_solo_si_nada_queda_sin_licencia():
    assert _sbom_falso()["cobertura_de_licencias"]["completa"] is True
    assert _sbom_falso(rust_sin_licencia=1)["cobertura_de_licencias"]["completa"] is False
    assert _sbom_falso(binarios_sin_licencia=1)["cobertura_de_licencias"]["completa"] is False


def test_un_rust_no_verificado_nunca_es_cobertura_completa():
    """Aunque ninguna crate tenga el campo vacío: si cargo no pudo resolver, el
    vacío no distingue nada y la afirmación global no se sostiene."""
    cobertura = sbom_mod._cobertura(python=[], npm=[], rust=[], binarios=[], rust_verificado=False)
    assert cobertura["completa"] is False
    assert "no verificad" in cobertura["rust"]["estado"]


@pytest.mark.parametrize("sin_licencia", [{"rust_sin_licencia": 3}, {"binarios_sin_licencia": 1}])
def test_check_falla_si_la_cobertura_es_incompleta_aunque_el_archivo_coincida(
    monkeypatch, tmp_path, capsys, sin_licencia
):
    """Que el SBOM guardado sea idéntico al generado no basta: un inventario
    idéntico y con huecos sigue teniendo huecos."""
    falso = _sbom_falso(**sin_licencia)
    texto = json.dumps(falso, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    guardado = tmp_path / "sbom.json"
    guardado.write_text(texto, encoding="utf-8")
    monkeypatch.setattr(sbom_mod, "SALIDA", guardado)
    monkeypatch.setattr(sbom_mod, "_construir", lambda: falso)
    monkeypatch.setattr(sbom_mod, "PYTHON_EMBED", Path(sys.executable))
    monkeypatch.setattr(sys, "argv", ["generate_sbom.py", "--check"])
    assert sbom_mod.main() == 1
    assert "sin licencia" in capsys.readouterr().err.lower()


def test_check_pasa_con_cobertura_completa_y_archivo_idempotente(monkeypatch, tmp_path):
    falso = _sbom_falso()
    guardado = tmp_path / "sbom.json"
    guardado.write_text(
        json.dumps(falso, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    monkeypatch.setattr(sbom_mod, "SALIDA", guardado)
    monkeypatch.setattr(sbom_mod, "_construir", lambda: falso)
    monkeypatch.setattr(sbom_mod, "PYTHON_EMBED", Path(sys.executable))
    monkeypatch.setattr(sys, "argv", ["generate_sbom.py", "--check"])
    assert sbom_mod.main() == 0


# ── las licencias resueltas por evidencia ────────────────────────────────


def test_las_licencias_resueltas_solo_listan_las_que_se_aplicaron(monkeypatch):
    """`busboy` y `streamsearch` seguían en el diccionario después de salir del
    lockfile, y el informe afirmaba haber resuelto paquetes que ya no se
    distribuyen."""
    monkeypatch.setattr(
        sbom_mod, "LICENCIAS_RESUELTAS",
        {"presente": ("MIT", "leída"), "fantasma": ("MIT", "leída hace meses")},
    )
    paquetes = sbom_mod._resolver([{"nombre": "presente", "version": "1", "licencia": ""}])
    resumen = sbom_mod._resueltas_por_evidencia(paquetes)
    assert list(resumen) == ["presente"]


# ── el SBOM guardado y la prosa que lo describe ──────────────────────────


@pytest.mark.skipif(not SBOM.is_file(), reason="no hay docs/api/sbom.json")
def test_el_sbom_guardado_tiene_cobertura_completa_y_ninguna_seccion_sin_licencia():
    sbom = json.loads(SBOM.read_text(encoding="utf-8"))
    assert sbom["cobertura_de_licencias"]["completa"] is True
    assert sbom["rust_produccion"]["licencias_verificadas"] is True
    sin = sbom["sin_licencia_declarada"]
    assert set(sin) >= {"python", "npm", "rust", "binarios"}, (
        "cada ecosistema tiene su lista: sin lista, «0» no distingue «sin riesgo» de «sin mirar»"
    )
    assert all(sin[k] == [] for k in ("python", "npm", "rust", "binarios"))
    assert sbom["rust_produccion"]["total"] == len(sbom["rust_produccion"]["paquetes"]) > 0
    assert all(c["licencia"] for c in sbom["rust_produccion"]["paquetes"])


@pytest.mark.skipif(not SBOM.is_file(), reason="no hay docs/api/sbom.json")
def test_agents_md_cuenta_lo_que_el_sbom_tiene():
    """El párrafo envejeció tres veces porque nada lo comparaba con el SBOM."""
    sbom = json.loads(SBOM.read_text(encoding="utf-8"))
    resueltas = set(sbom["licencias_resueltas_por_evidencia"]["paquetes"])
    python = {p["nombre"] for p in sbom["python_embed"]["paquetes"]}
    npm = {p["nombre"] for p in sbom["npm_produccion"]["paquetes"]}

    coincidencia = re.search(
        r"\*\*(\d+) paquetes Python y (\d+) npm\*\*", AGENTS.read_text(encoding="utf-8")
    )
    assert coincidencia, "AGENTS.md debe declarar «**N paquetes Python y M npm**» resueltos por evidencia"
    assert (int(coincidencia.group(1)), int(coincidencia.group(2))) == (
        len(resueltas & python), len(resueltas & npm),
    )
    # Y todo lo que el informe lista como resuelto es de verdad distribuido.
    assert resueltas <= python | npm


@pytest.mark.skipif(not SBOM.is_file(), reason="no hay docs/api/sbom.json")
def test_ningun_componente_inventariado_declara_agpl_ni_sspl():
    """La frase de AGENTS.md que lo afirma, convertida en algo que falla.

    Recorre los cuatro ecosistemas con el normalizador del propio generador (que
    ya sabe que «GNU AFFERO GENERAL PUBLIC LICENSE» es AGPL). Si mañana entra una
    dependencia AGPL, esto falla y la prosa tiene que cambiar con ella: lo que no
    puede es seguir diciendo «no hay» sobre un SBOM que dice lo contrario.
    """
    sbom = json.loads(SBOM.read_text(encoding="utf-8"))
    componentes = [
        *sbom["python_embed"]["paquetes"],
        *sbom["npm_produccion"]["paquetes"],
        *sbom["rust_produccion"]["paquetes"],
        *sbom["binarios"],
    ]
    assert len(componentes) > 1000, "el recorrido tiene que ver el inventario entero"
    culpables = [
        (c["nombre"], c["licencia"])
        for c in componentes
        if any(m in sbom_mod._normalizar_licencia(c.get("licencia", "")) for m in ("AGPL", "SSPL"))
    ]
    assert not culpables, culpables


def test_el_normalizador_ve_agpl_y_sspl_en_su_nombre_largo():
    """Un detector que no demuestra que ve no sirve: se prueba con muestras rotas."""
    for muestra in (
        "AGPL-3.0-or-later",
        "GNU Affero General Public License v3",
        "Server Side Public License",
        "SSPL-1.0",
    ):
        assert any(m in sbom_mod._normalizar_licencia(muestra) for m in ("AGPL", "SSPL")), muestra
    for muestra in ("MIT OR Apache-2.0", "LGPL-3.0-or-later", "GPL-2.0-only", "MPL-2.0"):
        assert not any(
            m in sbom_mod._normalizar_licencia(muestra) for m in ("AGPL", "SSPL")
        ), muestra


# ── el árbol real ────────────────────────────────────────────────────────


def _cargo_disponible() -> bool:
    try:
        return subprocess.run(["cargo", "--version"], capture_output=True).returncode == 0
    except OSError:
        return False


@pytest.mark.skipif(
    not (RAIZ / "python-embed" / "python.exe").is_file() or not _cargo_disponible(),
    reason="necesita python-embed y cargo: sobre un clon limpio el gate lo dice y no comprueba",
)
def test_el_check_del_sbom_pasa_sobre_este_arbol():
    proceso = subprocess.run(
        [str(RAIZ / "python-embed" / "python.exe"), str(SCRIPT), "--check"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=RAIZ,
        env={**__import__("os").environ, "PYTHONUTF8": "1"},
    )
    assert proceso.returncode == 0, proceso.stderr + proceso.stdout
