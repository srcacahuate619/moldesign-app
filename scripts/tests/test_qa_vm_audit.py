"""Autotests de `scripts/qa_vm_audit.py` — el arnés se audita a sí mismo.

Regla de la casa (doc 70 §2): **todo guardián lleva autotest**, con muestras
que debe detectar y muestras que no debe marcar. Un guardián con falsos
positivos acaba desactivado, y este arnés nació precisamente de una auditoría
que produjo cuatro clases de falso fallo.

Lo que se comprueba, una por una:

* 404 en `/evaluation/submit` → FAIL con el cuerpo del 404 conservado.
* 422 en `/evaluation/preflight` → FAIL con el detalle de validación conservado.
* timeout de arranque en frío → `TIMEOUT`, **nunca** SKIP, y el veredicto cae.
* timeout de la corrida → `TIMEOUT`, separado del 4xx del polling.
* `SUCCESS` → PASS y salida 0.
* `FAILURE` → FAIL con `task_id`, petición, respuesta y log del backend.

El backend es un `ThreadingHTTPServer` de verdad, no un monkeypatch: así se
ejercita el camino real de `urllib` —incluida la lectura del cuerpo de un
`HTTPError`, que es justo donde el arnés anterior perdía el detalle del 422—.
"""

from __future__ import annotations

import ast
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable

import pytest

import qa_vm_audit as qa


# ── Un OpenAPI mínimo pero fiel ─────────────────────────────────────────────
#
# Refleja el contrato real (`docs/api/openapi-current.json`) en lo que este
# arnés usa: los nombres de esquema, `required`, y —lo importante—
# `target_pdb_id`, que es el campo que la auditoría de la VM escribía mal.

def spec_base() -> dict[str, Any]:
    return {
        "openapi": "3.1.0",
        "info": {"title": "MolDesign API", "version": "1.0.0-alpha.2"},
        "paths": {
            "/health": {"get": {"responses": {"200": {"description": "ok"}}}},
            "/targets/": {"get": {"responses": {"200": {"description": "ok"}}}},
            "/evaluation/engines": {"get": {"responses": {"200": {"description": "ok"}}}},
            "/evaluation/preflight": {
                "post": {
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/PreflightRequest"}
                            }
                        },
                    },
                    "responses": {"200": {"description": "ok"}, "422": {"description": "no"}},
                }
            },
            "/evaluation/submit": {
                "post": {
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/EvaluationSubmitRequest"
                                }
                            }
                        },
                    },
                    "responses": {"202": {"description": "ok"}, "422": {"description": "no"}},
                }
            },
            "/evaluation/status/{task_id}": {
                "get": {"responses": {"200": {"description": "ok"}}}
            },
        },
        "components": {
            "schemas": {
                "PreflightRequest": {
                    "type": "object",
                    "title": "PreflightRequest",
                    "required": ["smiles", "target_pdb_id"],
                    "properties": {
                        "smiles": {"type": "string"},
                        "target_pdb_id": {"type": "string"},
                        "chain": {"type": "string"},
                        "docking_engine": {"type": "string", "default": "vina"},
                        "grid_center": {"type": "array"},
                        "grid_size": {"type": "array"},
                        "custom_hotspots": {"type": "array"},
                        "exhaustiveness": {"type": "integer"},
                        "num_poses": {"type": "integer"},
                        "conformers": {"type": "integer"},
                        "pipeline_config": {"type": "object"},
                    },
                },
                "EvaluationSubmitRequest": {
                    "type": "object",
                    "title": "EvaluationSubmitRequest",
                    "required": ["smiles"],
                    "properties": {
                        "smiles": {"type": "string"},
                        "target_pdb_id": {"type": "string", "default": "7E2Y"},
                        "chain": {"type": "string"},
                        "molecule_name": {"type": "string"},
                        "grid_center": {"type": "array"},
                        "grid_size": {"type": "array"},
                        "custom_hotspots": {"type": "array"},
                        "is_control": {"type": "boolean", "default": False},
                        "preflight_fingerprint": {"type": "string"},
                        "pipeline_config": {"type": "object"},
                        "patient_profile": {"type": "object"},
                        "peptide_docking_engine": {"type": "string"},
                    },
                },
            }
        },
    }


HUELLA = "sha256:" + "a" * 64

MOTORES_REALES = {
    "docking": [
        {
            "id": "vina", "familia": "docking", "estado": "listo",
            "disponible": True, "requiere": "binario_empaquetado", "motivo": None,
        },
        {
            "id": "qvina2", "familia": "docking", "estado": "no_instalado",
            "disponible": False, "requiere": "binario_externo",
            "motivo": "QuickVina 2 no viene con esta versión.",
        },
        {
            "id": "diffdock", "familia": "docking", "estado": "servicio_no_instalado",
            "disponible": False, "requiere": "servicio_externo",
            "motivo": "Se ejecuta en un servicio aparte que esta versión no instala.",
        },
    ],
    "peptido": [
        {
            "id": "esmfold", "familia": "peptido", "estado": "no_instalado",
            "disponible": False, "requiere": "descarga_bajo_demanda",
            "motivo": "Faltan los pesos; se descargan bajo demanda.",
            "archivos_faltantes": ["esmfold_v1.pt"],
        },
    ],
}


def preflight_ok() -> dict[str, Any]:
    return {
        "schema_version": 3,
        "input_fingerprint": HUELLA,
        "receptor": {"pdb_id": "7E2Y", "chain": "R"},
        "ligand": {"canonical_smiles": qa.SMILES_POR_DEFECTO},
        "effective_config": {
            "grid_center": [1.0, 2.0, 3.0],
            "grid_size": [20.0, 20.0, 20.0],
            "docking_engine": "vina",
            "exhaustiveness": 8,
            "num_poses": 9,
            "seed": 42,
        },
        "technical_blockers": [],
        "warnings": ["RECEPTOR_SIN_CALIBRAR"],
        "not_evaluated": [],
    }


# ── El backend falso ────────────────────────────────────────────────────────

Manejador = Callable[[dict[str, Any] | None, int], "tuple[int, Any]"]


class BackendFalso:
    """Servidor HTTP real y programable. Anota cada petición que recibe."""

    def __init__(self, rutas: dict[tuple[str, str], Manejador]) -> None:
        self.rutas = rutas
        self.peticiones: list[dict[str, Any]] = []
        self._contadores: dict[tuple[str, str], int] = {}
        self._lock = threading.Lock()
        servidor_falso = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *_args: Any) -> None:  # silencio en la suite
                pass

            def _atender(self, metodo: str) -> None:
                longitud = int(self.headers.get("Content-Length") or 0)
                crudo = self.rfile.read(longitud) if longitud else b""
                try:
                    cuerpo = json.loads(crudo) if crudo else None
                except ValueError:
                    cuerpo = {"__no_json__": crudo.decode("utf-8", "replace")}
                ruta = self.path.split("?", 1)[0]
                with servidor_falso._lock:
                    servidor_falso.peticiones.append(
                        {"method": metodo, "path": ruta, "body": cuerpo}
                    )
                    manejador, clave = servidor_falso._buscar(metodo, ruta)
                    if manejador is None:
                        status, carga = 404, {"detail": f"Not Found: {ruta}"}
                    else:
                        n = servidor_falso._contadores.get(clave, 0)
                        servidor_falso._contadores[clave] = n + 1
                        status, carga = manejador(cuerpo, n)
                # `ensure_ascii=False`, como FastAPI: si el falso escapara los
                # acentos, la prueba mediría el falso y no el arnés.
                datos = json.dumps(carga, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(datos)))
                self.end_headers()
                self.wfile.write(datos)

            def do_GET(self) -> None:  # noqa: N802
                self._atender("GET")

            def do_POST(self) -> None:  # noqa: N802
                self._atender("POST")

        self._servidor = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._hilo = threading.Thread(target=self._servidor.serve_forever, daemon=True)

    def _buscar(
        self, metodo: str, ruta: str
    ) -> "tuple[Manejador | None, tuple[str, str]]":
        clave = (metodo, ruta)
        if clave in self.rutas:
            return self.rutas[clave], clave
        # Prefijos: `/evaluation/status/<uuid>` se registra como `.../status/`.
        for (m, patron), manejador in self.rutas.items():
            if m == metodo and patron.endswith("/") and ruta.startswith(patron):
                return manejador, (m, patron)
        return None, clave

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self._servidor.server_address[1]}"

    def rutas_pedidas(self) -> list[str]:
        return [f"{p['method']} {p['path']}" for p in self.peticiones]

    def cuerpo_de(self, metodo: str, ruta: str) -> dict[str, Any] | None:
        for registro in self.peticiones:
            if registro["method"] == metodo and registro["path"] == ruta:
                return registro["body"]
        return None

    def __enter__(self) -> "BackendFalso":
        self._hilo.start()
        return self

    def __exit__(self, *_exc: Any) -> None:
        self._servidor.shutdown()
        self._servidor.server_close()
        self._hilo.join(timeout=5)


def constante(status: int, carga: Any) -> Manejador:
    return lambda _cuerpo, _n: (status, carga)


def rutas_felices(
    *,
    spec: dict[str, Any] | None = None,
    motores: dict[str, Any] | None = None,
    estados: list[dict[str, Any]] | None = None,
) -> dict[tuple[str, str], Manejador]:
    """El camino en el que todo va bien; cada test tuerce sólo lo suyo."""
    secuencia = estados or [
        {"task_id": "t-1", "status": "PENDING", "progress": 0},
        {
            "task_id": "t-1", "status": "SUCCESS", "progress": 100,
            "result": {
                "molecule_id": "11111111-1111-1111-1111-111111111111",
                "affinity_kcal": -8.1, "total_score": 74.2,
            },
        },
    ]

    def estado(_cuerpo: dict[str, Any] | None, n: int) -> tuple[int, Any]:
        return 200, secuencia[min(n, len(secuencia) - 1)]

    return {
        ("GET", "/openapi.json"): constante(200, spec if spec is not None else spec_base()),
        ("GET", "/health"): constante(200, {"status": "healthy"}),
        ("GET", "/targets/"): constante(200, [{"pdb_id": "7E2Y"}, {"pdb_id": "5VA1"}]),
        ("GET", "/evaluation/engines"): constante(
            200, motores if motores is not None else MOTORES_REALES
        ),
        ("POST", "/evaluation/preflight"): constante(200, preflight_ok()),
        ("POST", "/evaluation/submit"): constante(
            202,
            {
                "task_id": "t-1", "status": "submitted",
                "target_pdb_id": "7E2Y", "smiles_hash": "b" * 64,
            },
        ),
        ("GET", "/evaluation/status/"): estado,
    }


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def log_backend(tmp_path: Path) -> Path:
    """Un directorio de logs como el que deja `backend.rs`, con su puntero."""
    directorio = tmp_path / "logs"
    directorio.mkdir()
    (directorio / "backend_20260907_120000.log").write_text(
        "INFO uvicorn arrancado\nERROR docking: Vina devolvió 1\n",
        encoding="utf-8",
    )
    (directorio / "backend.latest.log").write_text(
        "backend_20260907_120000.log", encoding="utf-8"
    )
    return directorio


def correr(
    backend: BackendFalso, tmp_path: Path, log_backend: Path, *extra: str
) -> "tuple[int, dict[str, Any], str]":
    salida = tmp_path / "evidencia"
    codigo = qa.main([
        "--base-url", backend.base_url,
        "--out-dir", str(salida),
        "--backend-log-dir", str(log_backend),
        "--readiness-interval", "0.05",
        "--poll-interval", "0.05",
        "--request-timeout", "10",
        *extra,
    ])
    reporte = json.loads(
        (salida / "qa_comprehensive_report.json").read_text(encoding="utf-8")
    )
    bitacora = (salida / "qa_exec.log").read_text(encoding="utf-8")
    return codigo, reporte, bitacora


def fase(reporte: dict[str, Any], identificador: str) -> dict[str, Any]:
    for registro in reporte["fases"]:
        if registro["id"] == identificador:
            return registro
    raise AssertionError(
        f"El informe no trae la fase {identificador}: "
        f"{[f['id'] for f in reporte['fases']]}"
    )


# ── El contrato: lo que mató a `/evaluation/dock` y a `target` ──────────────

def test_el_arnes_no_conoce_evaluation_dock() -> None:
    """La regresión directa: el endpoint inventado no está en ningún sitio.

    Se recorre el AST en vez del texto porque `/evaluation/dock` **sí** aparece
    en el docstring del módulo —explicando por qué no existe—, y una búsqueda
    literal daría un falso positivo. Lo que no puede existir es una cadena
    *ejecutable* que lo nombre.
    """
    assert "/evaluation/dock" not in {ruta for ruta, _ in qa.RUTAS_REQUERIDAS}

    arbol = ast.parse(Path(qa.__file__).read_text(encoding="utf-8"))
    docstrings = {
        nodo.body[0].value
        for nodo in ast.walk(arbol)
        if isinstance(nodo, (ast.Module, ast.ClassDef, ast.FunctionDef))
        and nodo.body
        and isinstance(nodo.body[0], ast.Expr)
        and isinstance(nodo.body[0].value, ast.Constant)
        and isinstance(nodo.body[0].value.value, str)
    }
    ejecutables = [
        nodo.value
        for nodo in ast.walk(arbol)
        if isinstance(nodo, ast.Constant)
        and isinstance(nodo.value, str)
        and nodo not in docstrings
    ]
    assert not [c for c in ejecutables if "/evaluation/dock" in c]


def test_el_contrato_real_del_repositorio_sostiene_el_flujo() -> None:
    """El payload se deriva del OpenAPI vigente, no de la maqueta de arriba.

    Si el contrato cambia —un campo renombrado, un requerido nuevo— esta
    prueba cae aquí, en la suite, y no en la VM disfrazada de fallo del
    producto.
    """
    ruta_spec = Path(qa.__file__).parent.parent / "docs" / "api" / "openapi-current.json"
    if not ruta_spec.is_file():
        pytest.skip("no hay openapi-current.json en este árbol")
    contrato = qa.Contrato(
        json.loads(ruta_spec.read_text(encoding="utf-8")), str(ruta_spec)
    )
    contrato.exige_rutas(qa.RUTAS_REQUERIDAS)

    nombre, cuerpo = contrato.payload_de(
        "/evaluation/preflight", "post",
        {"smiles": "CCO", "target_pdb_id": "7E2Y", "chain": None,
         "docking_engine": "vina"},
    )
    assert nombre == "PreflightRequest"
    assert cuerpo == {"smiles": "CCO", "target_pdb_id": "7E2Y", "docking_engine": "vina"}

    nombre, cuerpo = contrato.payload_de(
        "/evaluation/submit", "post",
        {"smiles": "CCO", "target_pdb_id": "7E2Y", "molecule_name": "qa",
         "grid_center": [1.0, 2.0, 3.0], "grid_size": [20.0, 20.0, 20.0],
         "preflight_fingerprint": HUELLA, "chain": "R"},
    )
    assert nombre == "EvaluationSubmitRequest"
    assert cuerpo["target_pdb_id"] == "7E2Y"
    assert cuerpo["preflight_fingerprint"] == HUELLA


def test_payload_rechaza_un_campo_que_el_esquema_no_declara() -> None:
    """`target` en vez de `target_pdb_id`: muere aquí, con nombre y apellido."""
    contrato = qa.Contrato(spec_base(), "prueba")
    with pytest.raises(qa.ContratoRoto) as excinfo:
        contrato.payload_de(
            "/evaluation/preflight", "post",
            {"smiles": "CCO", "target": "7E2Y"},
        )
    mensaje = str(excinfo.value)
    assert "target" in mensaje
    assert "target_pdb_id" in mensaje  # dice cuál era el campo bueno


def test_payload_exige_los_requeridos() -> None:
    contrato = qa.Contrato(spec_base(), "prueba")
    with pytest.raises(qa.ContratoRoto, match="target_pdb_id"):
        contrato.payload_de("/evaluation/preflight", "post", {"smiles": "CCO"})


def test_una_ruta_ausente_del_contrato_aborta_sin_llamarla(
    tmp_path: Path, log_backend: Path
) -> None:
    """Si el contrato no declara `/evaluation/submit`, el arnés no la inventa."""
    spec = spec_base()
    del spec["paths"]["/evaluation/submit"]
    with BackendFalso(rutas_felices(spec=spec)) as backend:
        codigo, reporte, _ = correr(backend, tmp_path, log_backend)
    # Código 2: el arnés no pudo auditar. No es un veredicto sobre el producto.
    assert codigo == 2
    assert "POST /evaluation/submit" in reporte["aborto"]
    assert fase(reporte, "contrato")["estado"] == qa.FAIL
    assert "POST /evaluation/submit" not in backend.rutas_pedidas()


# ── El camino feliz ─────────────────────────────────────────────────────────

def test_success_recorre_el_flujo_canonico(
    tmp_path: Path, log_backend: Path
) -> None:
    with BackendFalso(rutas_felices()) as backend:
        codigo, reporte, bitacora = correr(backend, tmp_path, log_backend)

    assert codigo == 0
    assert reporte["resumen"]["veredicto"] == qa.PASS
    for identificador in (
        "readiness.health", "readiness.targets", "contrato", "motores",
        "evaluation.preflight", "evaluation.submit", "evaluation.poll",
    ):
        assert fase(reporte, identificador)["estado"] == qa.PASS

    pedidas = backend.rutas_pedidas()
    assert "POST /evaluation/preflight" in pedidas
    assert "POST /evaluation/submit" in pedidas
    assert "GET /evaluation/status/t-1" in pedidas
    assert not any("/evaluation/dock" in r for r in pedidas)

    assert fase(reporte, "evaluation.poll")["detalle"]["affinity_kcal"] == -8.1
    assert "VEREDICTO PASS" in bitacora


def test_el_cuerpo_lleva_target_pdb_id_y_la_huella_del_preflight(
    tmp_path: Path, log_backend: Path
) -> None:
    with BackendFalso(rutas_felices()) as backend:
        codigo, _, _ = correr(backend, tmp_path, log_backend)

    assert codigo == 0
    for ruta in ("/evaluation/preflight", "/evaluation/submit"):
        cuerpo = backend.cuerpo_de("POST", ruta)
        assert cuerpo is not None
        assert cuerpo["target_pdb_id"] == "7E2Y"
        assert "target" not in cuerpo
    # La huella viaja: sin ella `/evaluation/submit` no recalcula el preflight.
    assert backend.cuerpo_de("POST", "/evaluation/submit")["preflight_fingerprint"] == HUELLA


# ── 404 y 422 ───────────────────────────────────────────────────────────────

def test_submit_404_falla_conservando_la_evidencia(
    tmp_path: Path, log_backend: Path
) -> None:
    rutas = rutas_felices()
    rutas[("POST", "/evaluation/submit")] = constante(
        404, {"detail": "Not Found"}
    )
    with BackendFalso(rutas) as backend:
        codigo, reporte, _ = correr(backend, tmp_path, log_backend)

    assert codigo == 1
    registro = fase(reporte, "evaluation.submit")
    assert registro["estado"] == qa.FAIL
    assert registro["detalle"]["status"] == 404
    evidencia = registro["evidencia"]
    assert evidencia["request"]["path"] == "/evaluation/submit"
    assert evidencia["request"]["body"]["target_pdb_id"] == "7E2Y"
    assert evidencia["response"]["status"] == 404
    assert "Not Found" in evidencia["response"]["body"]
    assert "Vina devolvió 1" in "\n".join(evidencia["backend_log"]["tail"])
    # Sin task_id no se sondea: el polling queda SKIP, no FAIL inventado.
    assert fase(reporte, "evaluation.poll")["estado"] == qa.SKIP


def test_preflight_422_conserva_el_detalle_de_validacion(
    tmp_path: Path, log_backend: Path
) -> None:
    detalle_422 = {
        "detail": [
            {
                "type": "missing",
                "loc": ["body", "target_pdb_id"],
                "msg": "Field required",
            }
        ]
    }
    rutas = rutas_felices()
    rutas[("POST", "/evaluation/preflight")] = constante(422, detalle_422)
    with BackendFalso(rutas) as backend:
        codigo, reporte, _ = correr(backend, tmp_path, log_backend)

    assert codigo == 1
    registro = fase(reporte, "evaluation.preflight")
    assert registro["estado"] == qa.FAIL
    assert registro["detalle"]["status"] == 422
    cuerpo = registro["evidencia"]["response"]["body"]
    # El cuerpo del 422 viaja íntegro: es lo que dice QUÉ campo sobra o falta,
    # y es exactamente lo que el arnés anterior tiraba con la excepción.
    assert "target_pdb_id" in cuerpo
    assert "Field required" in cuerpo
    for identificador in ("evaluation.submit", "evaluation.poll"):
        assert fase(reporte, identificador)["estado"] == qa.SKIP


def test_preflight_con_bloqueantes_no_lanza_la_corrida(
    tmp_path: Path, log_backend: Path
) -> None:
    informe = preflight_ok()
    informe["technical_blockers"] = ["RECEPTOR_SIN_PREPARAR"]
    rutas = rutas_felices()
    rutas[("POST", "/evaluation/preflight")] = constante(200, informe)
    with BackendFalso(rutas) as backend:
        codigo, reporte, _ = correr(backend, tmp_path, log_backend)

    assert codigo == 1
    registro = fase(reporte, "evaluation.preflight")
    assert registro["estado"] == qa.FAIL
    assert registro["detalle"]["technical_blockers"] == ["RECEPTOR_SIN_PREPARAR"]
    assert "POST /evaluation/submit" not in backend.rutas_pedidas()


# ── FAILURE terminal ────────────────────────────────────────────────────────

def test_failure_conserva_task_id_peticion_respuesta_y_log(
    tmp_path: Path, log_backend: Path
) -> None:
    rutas = rutas_felices(estados=[
        {"task_id": "t-1", "status": "PENDING", "progress": 10},
        {
            "task_id": "t-1", "status": "FAILURE", "progress": 100,
            "error": "docking_failed: Vina devolvió código 1",
        },
    ])
    with BackendFalso(rutas) as backend:
        codigo, reporte, _ = correr(backend, tmp_path, log_backend)

    assert codigo == 1
    registro = fase(reporte, "evaluation.poll")
    assert registro["estado"] == qa.FAIL
    assert registro["detalle"]["status"] == "FAILURE"
    assert "Vina devolvió código 1" in registro["detalle"]["error"]

    evidencia = registro["evidencia"]
    assert evidencia["task_id"] == "t-1"
    assert evidencia["request"]["path"] == "/evaluation/status/t-1"
    # La petición que lanzó la corrida también se conserva: sin ella no se
    # puede reproducir el fallo.
    assert evidencia["submit_request"]["body"]["smiles"] == qa.SMILES_POR_DEFECTO
    assert evidencia["response"]["status"] == 200
    assert "FAILURE" in evidencia["response"]["body"]
    assert evidencia["backend_log"]["path"].endswith("backend_20260907_120000.log")
    assert "Vina devolvió 1" in "\n".join(evidencia["backend_log"]["tail"])


# ── Timeouts: nunca disfrazados ─────────────────────────────────────────────

def test_arranque_en_frio_agotado_es_timeout_y_no_skip(
    tmp_path: Path, log_backend: Path
) -> None:
    rutas = rutas_felices()
    rutas[("GET", "/health")] = constante(503, {"status": "degraded"})
    with BackendFalso(rutas) as backend:
        codigo, reporte, bitacora = correr(
            backend, tmp_path, log_backend, "--cold-start-timeout", "1"
        )

    assert codigo == 1
    registro = fase(reporte, "readiness.health")
    assert registro["estado"] == qa.TIMEOUT, "un timeout real no se anota como SKIP"
    assert registro["timeout_s"] == 1.0
    assert registro["elapsed_s"] >= 1.0
    assert registro["detalle"]["status_histogram"]["503"] >= 1
    # El 503 se conserva: dice QUÉ componente está degradado.
    assert "degraded" in registro["evidencia"]["response"]["body"]
    # Las fases que no se intentaron sí son SKIP, y no hunden nada por su cuenta.
    for identificador, _ in qa.FASES_POSTERIORES:
        assert fase(reporte, identificador)["estado"] == qa.SKIP
    assert reporte["resumen"]["veredicto"] == qa.FAIL
    assert "TIMEOUT" in bitacora


def test_un_arranque_lento_pero_bueno_no_es_un_fallo(
    tmp_path: Path, log_backend: Path
) -> None:
    """El falso fallo original: la VM tarda, el arnés no esperaba.

    `/health` contesta 503 tres veces y `/targets` dos: exactamente lo que hace
    una VM de 3 núcleos con disco emulado. El veredicto tiene que ser PASS.
    """
    def lento(codigo_ok: int, carga_ok: Any, veces: int) -> qa.Any:
        def manejador(_cuerpo: Any, n: int) -> tuple[int, Any]:
            if n < veces:
                return 503, {"status": "starting"}
            return codigo_ok, carga_ok
        return manejador

    rutas = rutas_felices()
    rutas[("GET", "/health")] = lento(200, {"status": "healthy"}, 3)
    rutas[("GET", "/targets/")] = lento(200, [{"pdb_id": "7E2Y"}], 2)
    with BackendFalso(rutas) as backend:
        codigo, reporte, _ = correr(
            backend, tmp_path, log_backend,
            "--cold-start-timeout", "20", "--targets-timeout", "20",
        )

    assert codigo == 0
    salud = fase(reporte, "readiness.health")
    objetivos = fase(reporte, "readiness.targets")
    assert salud["estado"] == qa.PASS and objetivos["estado"] == qa.PASS
    assert salud["detalle"]["attempts"] == 4
    assert objetivos["detalle"]["attempts"] == 3
    assert objetivos["detalle"]["targets_visibles"] == 1
    # Medición separada: dos presupuestos y dos relojes distintos.
    assert salud["timeout_s"] == 20.0 and objetivos["timeout_s"] == 20.0
    assert salud["elapsed_s"] != objetivos["elapsed_s"]


def test_el_catalogo_grande_se_cuenta_entero(
    tmp_path: Path, log_backend: Path
) -> None:
    """El catálogo real pasa de 200 KB y la evidencia se recorta a propósito.

    Contarlo sobre el cuerpo recortado daba `targets_visibles: null` en una
    corrida sana — un dato perdido por un límite pensado para otra cosa.
    """
    catalogo = [
        {"pdb_id": f"T{n:03d}", "relleno": "x" * 200} for n in range(300)
    ]
    rutas = rutas_felices()
    rutas[("GET", "/targets/")] = constante(200, catalogo)
    with BackendFalso(rutas) as backend:
        codigo, reporte, _ = correr(backend, tmp_path, log_backend)

    assert codigo == 0
    assert fase(reporte, "readiness.targets")["detalle"]["targets_visibles"] == 300


def test_targets_agotado_es_timeout_propio(
    tmp_path: Path, log_backend: Path
) -> None:
    """`/health` sano y `/targets` colgado no es «el backend no arrancó»."""
    rutas = rutas_felices()
    rutas[("GET", "/targets/")] = constante(503, {"detail": "seeding"})
    with BackendFalso(rutas) as backend:
        codigo, reporte, _ = correr(
            backend, tmp_path, log_backend, "--targets-timeout", "1"
        )

    assert codigo == 1
    assert fase(reporte, "readiness.health")["estado"] == qa.PASS
    registro = fase(reporte, "readiness.targets")
    assert registro["estado"] == qa.TIMEOUT
    assert registro["timeout_s"] == 1.0
    # El resto de la auditoría sigue: un catálogo lento no impide leer motores.
    assert fase(reporte, "motores")["estado"] == qa.PASS


def test_la_corrida_que_no_termina_es_timeout_no_failure(
    tmp_path: Path, log_backend: Path
) -> None:
    rutas = rutas_felices(estados=[{"task_id": "t-1", "status": "STARTED", "progress": 40}])
    with BackendFalso(rutas) as backend:
        codigo, reporte, _ = correr(
            backend, tmp_path, log_backend, "--eval-timeout", "1"
        )

    assert codigo == 1
    registro = fase(reporte, "evaluation.poll")
    assert registro["estado"] == qa.TIMEOUT
    assert registro["timeout_s"] == 1.0
    assert registro["evidencia"]["task_id"] == "t-1"
    assert registro["detalle"]["polls"] >= 2


def test_un_4xx_en_el_polling_es_fail_no_timeout(
    tmp_path: Path, log_backend: Path
) -> None:
    """404 en `/status` es un fallo del contrato, no una corrida lenta."""
    rutas = rutas_felices()
    rutas[("GET", "/evaluation/status/")] = constante(
        404, {"detail": "La evaluación ya no está disponible."}
    )
    with BackendFalso(rutas) as backend:
        codigo, reporte, _ = correr(
            backend, tmp_path, log_backend, "--eval-timeout", "30"
        )

    assert codigo == 1
    registro = fase(reporte, "evaluation.poll")
    assert registro["estado"] == qa.FAIL
    assert registro["detalle"]["ultimo_status_http"] == 404
    assert registro["elapsed_s"] < 30
    assert "ya no está disponible" in registro["evidencia"]["response"]["body"]


# ── Motores: ausencias esperadas ────────────────────────────────────────────

def test_los_motores_ausentes_por_diseno_no_hunden_el_veredicto(
    tmp_path: Path, log_backend: Path
) -> None:
    """ESMFold sin pesos y los «Próximamente» son EXPECTED, no FAIL."""
    with BackendFalso(rutas_felices()) as backend:
        codigo, reporte, _ = correr(backend, tmp_path, log_backend)

    assert codigo == 0
    assert fase(reporte, "motores.vina")["estado"] == qa.PASS
    for identificador in ("motores.qvina2", "motores.diffdock", "motores.esmfold"):
        assert fase(reporte, identificador)["estado"] == qa.EXPECTED
    assert fase(reporte, "motores")["detalle"]["ausencias_esperadas"] == 3
    assert reporte["resumen"]["por_estado"].get(qa.EXPECTED) == 3


def test_vina_ausente_si_es_un_fallo_real(
    tmp_path: Path, log_backend: Path
) -> None:
    """La contrapartida: lo que el instalador empaqueta no se excusa."""
    motores = json.loads(json.dumps(MOTORES_REALES))
    motores["docking"][0].update({
        "disponible": False, "estado": "error",
        "motivo": "No se encontró el ejecutable de AutoDock Vina.",
    })
    with BackendFalso(rutas_felices(motores=motores)) as backend:
        codigo, reporte, _ = correr(backend, tmp_path, log_backend)

    assert codigo == 1
    registro = fase(reporte, "motores.vina")
    assert registro["estado"] == qa.FAIL
    assert "binario_empaquetado" in registro["titulo"]


def test_un_requisito_desconocido_no_se_excusa() -> None:
    """La clasificación no puede volverse una amnistía general."""
    estado, motivo = qa.clasificar_motor(
        {"id": "motor_nuevo", "disponible": False, "requiere": "algo_que_no_existe"}
    )
    assert estado == qa.FAIL
    assert "no es un requisito conocido" in motivo


def test_un_motor_disponible_es_pass_sea_cual_sea_su_requisito() -> None:
    estado, _ = qa.clasificar_motor(
        {"id": "esmfold", "disponible": True, "estado": "listo",
         "requiere": "descarga_bajo_demanda"}
    )
    assert estado == qa.PASS


# ── El informe ──────────────────────────────────────────────────────────────

def test_el_informe_declara_sus_presupuestos(
    tmp_path: Path, log_backend: Path
) -> None:
    """Sin los timeouts escritos, un PASS no se puede interpretar."""
    with BackendFalso(rutas_felices()) as backend:
        _, reporte, _ = correr(
            backend, tmp_path, log_backend,
            "--cold-start-timeout", "42", "--targets-timeout", "17",
        )
    parametros = reporte["parametros"]
    assert parametros["cold_start_timeout_s"] == 42.0
    assert parametros["targets_timeout_s"] == 17.0
    assert reporte["harness"] == "scripts/qa_vm_audit.py"
    assert reporte["modo"] == "attach"


def test_no_pisa_el_informe_de_una_auditoria_anterior(
    tmp_path: Path, log_backend: Path
) -> None:
    """Reusar el directorio de salida ya destruyó 102 resultados aquí."""
    salida = tmp_path / "evidencia"
    with BackendFalso(rutas_felices()) as backend:
        correr(backend, tmp_path, log_backend)
        anterior = (salida / "qa_comprehensive_report.json").read_text(
            encoding="utf-8"
        )
        with pytest.raises(SystemExit, match="Ya hay un informe"):
            correr(backend, tmp_path, log_backend)
        # El informe de ayer sigue intacto.
        assert (salida / "qa_comprehensive_report.json").read_text(
            encoding="utf-8"
        ) == anterior
        # Y con `--force` se sobrescribe a propósito, no por descuido.
        codigo, reporte, _ = correr(backend, tmp_path, log_backend, "--force")
    assert codigo == 0
    assert reporte["resumen"]["veredicto"] == qa.PASS


def test_los_artefactos_llevan_los_nombres_de_la_auditoria(
    tmp_path: Path, log_backend: Path
) -> None:
    salida = tmp_path / "evidencia"
    with BackendFalso(rutas_felices()) as backend:
        qa.main([
            "--base-url", backend.base_url,
            "--out-dir", str(salida),
            "--backend-log-dir", str(log_backend),
            "--readiness-interval", "0.05",
            "--poll-interval", "0.05",
        ])
    assert (salida / "qa_comprehensive_report.json").is_file()
    assert (salida / "qa_exec.log").is_file()
    assert (salida / "preflight.json").is_file()
    assert (salida / "motores.json").is_file()
    assert (salida / "resultado.json").is_file()


def test_entorno_backend_declara_el_vina_del_artefacto(tmp_path, monkeypatch):
    """El arnés no depende de PATH ni publica un falso «Vina ausente»."""
    arbol = tmp_path / "resources"
    backend = arbol / "backend"
    vina = arbol / "tools" / "vina" / "vina.exe"
    backend.mkdir(parents=True)
    vina.parent.mkdir(parents=True)
    vina.write_bytes(b"vina")
    monkeypatch.setenv("VINA_EXECUTABLE_PATH", "C:/otro/vina.exe")

    entorno = qa.entorno_backend(arbol, backend)

    assert entorno["VINA_EXECUTABLE_PATH"] == str(vina)
    assert entorno["PYTHONPATH"] == str(backend)


def test_entorno_backend_aborta_si_el_arnes_no_encuentra_vina(tmp_path):
    """Una ruta inventada es un fallo del arnés, no una ausencia del producto."""
    with pytest.raises(qa.ArnesAbortado, match="no existe el binario esperado"):
        qa.entorno_backend(tmp_path, tmp_path / "backend")
