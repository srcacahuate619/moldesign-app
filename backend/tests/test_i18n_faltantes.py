"""El reporte opt-in registra texto español sin alterar respuestas localizadas."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core import i18n


class _ImmediateAsyncIterator:
    def __init__(self, items):
        self._items = iter(items)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self._items)
        except StopIteration:
            raise StopAsyncIteration from None


class _StreamingJSONResponse:
    def __init__(self, body: bytes):
        self.headers = {"content-type": "application/json"}
        self.body_iterator = _ImmediateAsyncIterator([body])


def _response(payload: dict) -> _StreamingJSONResponse:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    return _StreamingJSONResponse(body)


def _drive_immediate(coroutine):
    try:
        return coroutine.send(None)
    except StopIteration as result:
        return result.value
    coroutine.close()
    raise AssertionError("La prueba esperaba una corrutina sin operaciones de E/S")


def _install_inline_threadpool(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(i18n, "iterate_in_threadpool", _ImmediateAsyncIterator)


def _body(response: _StreamingJSONResponse, *, endpoint: str, openapi: bool = False) -> bytes:
    async def collect() -> bytes:
        localized = await i18n.localize_json_response(
            response,
            endpoint=endpoint,
            openapi=openapi,
        )
        return b"".join([chunk async for chunk in localized.body_iterator])

    return _drive_immediate(collect())


def test_reporte_opt_in_deduplica_y_no_cambia_la_respuesta(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _install_inline_threadpool(monkeypatch)
    texto = "El receptor conserva una geometría específica sin ficha previa."
    payload = {
        "detail": texto,
        "errors": [texto, texto],
        "nested": {"reason": texto},
        "name": texto,
        "description": texto,
        "reason": "No existe la corrida solicitada.",
    }
    monkeypatch.setenv("LOCAL_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("MOLDESIGN_I18N_REPORT", raising=False)
    token = i18n.set_request_locale("en")
    try:
        baseline = _body(_response(payload), endpoint="/evaluation/example")
        assert not (tmp_path / "i18n_faltantes.jsonl").exists()

        monkeypatch.setenv("MOLDESIGN_I18N_REPORT", "1")
        actual = _body(_response(payload), endpoint="/evaluation/example")
        _body(_response(payload), endpoint="/evaluation/example")
        i18n._I18N_REPORTED_BY_PATH.pop(tmp_path / "i18n_faltantes.jsonl", None)
        _body(_response(payload), endpoint="/evaluation/example")
    finally:
        i18n.reset_request_locale(token)

    assert actual == baseline
    localized = json.loads(actual)
    assert localized["detail"] == texto
    assert localized["errors"] == [texto, texto]
    assert localized["nested"]["reason"] == texto
    assert localized["name"] == texto
    assert localized["description"] == texto
    assert localized["reason"] == "The requested run does not exist."

    rows = [json.loads(line) for line in (tmp_path / "i18n_faltantes.jsonl").read_text(encoding="utf-8").splitlines()]
    assert rows == [{"endpoint": "/evaluation/example", "text": texto}]


def test_reporte_no_se_activa_en_espanol(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _install_inline_threadpool(monkeypatch)
    monkeypatch.setenv("LOCAL_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("MOLDESIGN_I18N_REPORT", "1")
    token = i18n.set_request_locale("es-MX")
    try:
        body = _body(
            _response({"detail": "No existe la corrida solicitada."}),
            endpoint="/evaluation/example",
        )
    finally:
        i18n.reset_request_locale(token)

    assert json.loads(body) == {"detail": "No existe la corrida solicitada."}
    assert not (tmp_path / "i18n_faltantes.jsonl").exists()


def test_openapi_reporta_solo_prosa_del_esquema(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _install_inline_threadpool(monkeypatch)
    texto = "El esquema incluye una descripción sin traducir."
    monkeypatch.setenv("LOCAL_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("MOLDESIGN_I18N_REPORT", "1")
    token = i18n.set_request_locale("en")
    try:
        body = _body(
            _response({
                "paths": {
                    "/example": {
                        "get": {
                            "summary": texto,
                            "tags": [texto],
                            "operationId": texto,
                        },
                    },
                },
            }),
            endpoint="/openapi.json",
            openapi=True,
        )
    finally:
        i18n.reset_request_locale(token)

    assert json.loads(body)["paths"]["/example"]["get"]["operationId"] == texto
    rows = [json.loads(line) for line in (tmp_path / "i18n_faltantes.jsonl").read_text(encoding="utf-8").splitlines()]
    assert rows == [{"endpoint": "/openapi.json", "text": texto}]


def test_estimacion_localiza_y_reporta_todos_los_campos_visibles(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _install_inline_threadpool(monkeypatch)
    monkeypatch.setenv("LOCAL_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("MOLDESIGN_I18N_REPORT", "1")
    token = i18n.set_request_locale("en")
    try:
        body = _body(
            _response({
                "detalle_apoyo": (
                    "Todavía no hay corridas terminadas en este equipo, así que esto sale de un modelo "
                    "medido en otra máquina. Se calibrará solo a partir del acoplamiento número 3."
                ),
                "etapas": [{
                    "etapa": "Preparación del ligando y análisis",
                    "nota": "Validación, propiedades, confórmeros y rescoring.",
                }],
                "una_vez": {
                    "etapa": "Preparar el receptor",
                    "nota": (
                        "Este receptor aún no está preparado en este equipo. Se hace una sola vez: "
                        "las siguientes corridas contra él se lo saltan."
                    ),
                },
                "avisos": [
                    "Tu equipo tiene 4 núcleos y la exhaustividad es 8: las búsquedas van en 2 tandas. "
                    "Bajarla a 4 haría la corrida más rápida sin cambiar el receptor ni la caja."
                ],
            }),
            endpoint="/evaluation/estimate",
        )
    finally:
        i18n.reset_request_locale(token)

    translated = json.loads(body)
    assert translated["detalle_apoyo"] == (
        "No runs have finished on this computer yet, so this estimate comes from a model measured "
        "on another computer. It will be calibrated only after docking run 3."
    )
    assert translated["etapas"] == [{
        "etapa": "Ligand preparation and analysis",
        "nota": "Validation, properties, conformers, and rescoring.",
    }]
    assert translated["una_vez"] == {
        "etapa": "Prepare receptor",
        "nota": (
            "This receptor has not been prepared on this computer yet. This happens once: "
            "later runs against it skip it."
        ),
    }
    assert translated["avisos"] == [
        "Your computer has 4 cores and exhaustiveness is 8: the searches run in 2 batches. "
        "Lowering it to 4 would make the run faster without changing the receptor or search box."
    ]
    assert not (tmp_path / "i18n_faltantes.jsonl").exists()


def test_evaluacion_real_localiza_mensajes_de_estado_motores_y_receptor(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _install_inline_threadpool(monkeypatch)
    monkeypatch.setenv("LOCAL_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("MOLDESIGN_I18N_REPORT", "1")
    motivo_no_disponible = (
        "Meeko elimina 7 residuo(s) a 6 Å o menos de la caja, del sitio: "
        "GLY A24 (3.027 Å), GLY A25 (2.577 Å), GLY A26 (3.996 Å), "
        "GLY A27 (4.622 Å), GLY A28 (2.263 Å), GLY A29 (1.864 Å), "
        "GLY A30 (5.681 Å). No se acopla contra un sitio incompleto."
    )
    payload = {
        "result": {
            "pose_selection": {
                "detail": (
                    "El selector recomienda la pose 2 con un margen de 0.122583. "
                    "Es una RECOMENDACIÓN: la pose principal del producto sigue siendo la 1 de Vina."
                ),
                "abstention": {"detail": (
                    "El margen entre la primera y la segunda (0.059321) no llega al umbral de "
                    "abstención (0.097663). El selector no recomienda."
                )},
            },
            "structural_evidence": {"poses": [{
                "detail": (
                    "PoseBusters en configuracion `dock` -sin verdad de terreno, que en produccion "
                    "no existe-. Ningun control de quimica o geometria falla. Ausencia de alertas "
                    "no significa ausencia de choques, enlaces imposibles o artefactos de preparacion."
                ),
            }]},
            "ligand_state": {
                "protonacion": {"seleccion": {"motivo": (
                    "Se comparan los recuentos de carga formal de cada microestado con los centros "
                    "que Henderson-Hasselbalch predice ionizados a pH 7.4, usando los pKa por clase "
                    "de este módulo. Los empates se rompen por orden alfabético del SMILES, no por "
                    "el orden de dimorphite-dl, que no es reproducible entre corridas."
                )}},
                "tautomeria": {"declaracion": {"motivo": (
                    "6 tautómeros enumerados y ninguno descartado con evidencia; "
                    "la especie acoplada se identifica aparte"
                )}},
            },
            "target_calibracion": {"motivo": (
                "faltan Spearman ρ del receptor y stacking calibrado para su familia"
            )},
            "calibracion": {
                "resumen": "Curado estructuralmente; sin calibrar y sin pipeline de familia",
                "advertencia": (
                    "Este receptor no tiene Spearman ρ medido y su familia estructural no tiene "
                    "stacking calibrado: se ejecuta con el contrato alpha conservador común. "
                    "No hay evidencia de que el ranking correlacione con afinidad real aquí. "
                    "Trata el resultado como una hipótesis a comprobar, no como una medida."
                ),
            },
        },
        "engine_reasons": [
            {"motivo": (
                "ColabFold se ejecuta en un servicio aparte que esta versión no instala. "
                "La aplicación sabe hablar con él, pero hay que levantarlo y todavía no hay "
                "ninguna dirección configurada."
            )},
            {"motivo": (
                "ESMFold Pro se ejecuta en un servicio aparte que esta versión no instala. "
                "La aplicación sabe hablar con él, pero hay que levantarlo y ahora mismo "
                "apunta a http://localhost:8300."
            )},
            {"motivo": (
                "ESMFold está instalado y apagado. Se enciende cuando lo pidas y ocupa memoria "
                "sólo mientras esté encendido."
            )},
        ],
        "histidinas": {"nota": "Plantillas de histidina de Meeko: A:69=HIE, B:69=HIE."},
        "avisos": [
            "La preparación retira 127 átomos de agua, 45 otros heteroátomos "
            "(ligandos, lípidos, aditivos).",
            (
                "Más allá de Ro5 (bRo5) (795 Da). Beyond Rule of Five (Doak, Over, Giordanetto, "
                "Kihlberg, Chem. Biol. 21:1115, 2014): 500 < MW ≤ 1000 Da. Espacio con fármacos "
                "orales reales —macrociclos, péptidos cíclicos, inhibidores de interacción "
                "proteína-proteína— que la regla de los cinco excluye por construcción. La corrida "
                "se ejecuta; lo que deja de aplicar son los filtros de Ro5 y los umbrales de "
                "eficiencia de ligando, que no están calibrados a este tamaño."
            ),
            (
                "Este receptor no tiene Spearman ρ medido y su familia estructural no tiene "
                "stacking calibrado: se ejecuta con el contrato alpha conservador común. No hay "
                "evidencia de que el ranking correlacione con afinidad real aquí. Trata el resultado "
                "como una hipótesis a comprobar, no como una medida."
            ),
        ],
        "motivo_no_disponible": motivo_no_disponible,
        "detalle_tecnico": {
            "motivo_no_disponible": (
                "Meeko no puede construir el receptor (RuntimeError: Expected 2 paddings "
                "for (A:1633, A:1646), but got 0)."
            ),
        },
        "scientific_warnings": [{
            "code": "RECEPTOR_PROTONACION_DECLARADA",
            "mensaje": (
                "Plantillas de histidina asignadas por Meeko: A:69=HIE, B:69=HIE. "
                "La asignación procede de plantillas y no valida el microestado experimental "
                "ni un pH concreto."
            ),
        }],
        "muegge_violations": ["más de 15 enlaces rotables", "MW fuera de 200-600"],
        "fallback_reason": (
            "Familia 'protease' sin modelo validado (quality gate: p 0.266 >= 0.05) — "
            "modelo universal usado."
        ),
        "protonation_method": "Meeko 0.7.1; asignación por plantilla, sin pH experimental declarado",
        "poblaciones_motivo": (
            "Sin modelo de poblaciones validado: no se descarta ningún candidato. "
            "El canónico de RDKit es una representación reproducible, no el estado dominante."
        ),
        "user_note": {
            "mensaje": "La persona escribió esta nota en español y se conserva como dato.",
        },
    }

    token = i18n.set_request_locale("en")
    try:
        body = _body(_response(payload), endpoint="/evaluation/status/example")
    finally:
        i18n.reset_request_locale(token)

    translated = json.loads(body)
    assert translated["result"]["pose_selection"]["detail"] == (
        "The selector recommends pose 2 with a margin of 0.122583. This is a RECOMMENDATION: "
        "the product's primary pose remains Vina pose 1."
    )
    assert translated["result"]["pose_selection"]["abstention"]["detail"] == (
        "The margin between the top two poses (0.059321) is below the abstention threshold "
        "(0.097663). The selector makes no recommendation."
    )
    assert translated["result"]["structural_evidence"]["poses"][0]["detail"] == (
        "PoseBusters in `dock` mode—without ground truth, which is not available in production. "
        "No chemistry or geometry checks fail. The absence of alerts does not mean there are no "
        "clashes, impossible bonds, or preparation artifacts."
    )
    assert translated["result"]["ligand_state"]["protonacion"]["seleccion"]["motivo"] == (
        "The formal-charge counts for each microstate are compared with the centers "
        "Henderson–Hasselbalch predicts to be ionized at pH 7.4, using this module's class-based "
        "pKa values. Ties are broken by alphabetical SMILES order, not by dimorphite-dl order, "
        "which is not reproducible across runs."
    )
    assert translated["result"]["ligand_state"]["tautomeria"]["declaracion"]["motivo"] == (
        "6 tautomers enumerated, and none were excluded based on evidence; "
        "the docked species is identified separately"
    )
    assert translated["result"]["calibracion"]["resumen"] == (
        "Structurally curated; calibration and a family pipeline are missing"
    )
    assert translated["result"]["calibracion"]["advertencia"] == (
        "This receptor has no measured Spearman ρ, and its structural family has no calibrated "
        "stacking, so it runs under the shared conservative alpha contract. There is no evidence "
        "that the ranking correlates with actual affinity here. Treat the result as a hypothesis "
        "to test, not as a measurement."
    )
    assert translated["engine_reasons"][0]["motivo"] == (
        "ColabFold runs as a separate service that this version does not install. The application "
        "can communicate with it, but the service must be started and no address is configured yet."
    )
    assert translated["engine_reasons"][1]["motivo"] == (
        "ESMFold Pro runs as a separate service that this version does not install. The application "
        "can communicate with it, but the service must be started; it currently points to "
        "http://localhost:8300."
    )
    assert translated["engine_reasons"][2]["motivo"] == (
        "ESMFold is installed and off. It starts when requested and uses memory only while running."
    )
    assert translated["histidinas"]["nota"] == "Meeko histidine templates: A:69=HIE, B:69=HIE."
    assert translated["avisos"] == [
        "Preparation removes 127 water atoms and 45 other heteroatoms (ligands, lipids, and additives).",
        (
            "Beyond Ro5 (bRo5) (795 Da). Beyond the Rule of Five (Doak, Over, Giordanetto, "
            "Kihlberg, Chem. Biol. 21:1115, 2014): 500 < MW ≤ 1000 Da. This is a space occupied "
            "by real oral drugs—macrocycles, cyclic peptides, and protein–protein interaction "
            "inhibitors—that the Rule of Five excludes by construction. The run proceeds; Ro5 "
            "filters and ligand-efficiency thresholds do not apply because they are not calibrated "
            "for this size."
        ),
        (
            "This receptor has no measured Spearman ρ, and its structural family has no calibrated "
            "stacking, so it runs under the shared conservative alpha contract. There is no evidence "
            "that the ranking correlates with actual affinity here. Treat the result as a hypothesis "
            "to test, not as a measurement."
        ),
    ]
    assert translated["motivo_no_disponible"] == (
        "Meeko removes 7 residue(s) within 6 Å of the box or binding site: "
        "GLY A24 (3.027 Å), GLY A25 (2.577 Å), GLY A26 (3.996 Å), "
        "GLY A27 (4.622 Å), GLY A28 (2.263 Å), GLY A29 (1.864 Å), "
        "GLY A30 (5.681 Å). Docking will not use an incomplete site."
    )
    assert translated["detalle_tecnico"]["motivo_no_disponible"] == (
        "Meeko could not build the receptor (RuntimeError: Expected 2 paddings "
        "for (A:1633, A:1646), but got 0)."
    )
    assert translated["scientific_warnings"][0]["mensaje"] == (
        "Meeko-assigned histidine templates: A:69=HIE, B:69=HIE. The assignment is "
        "template-based and does not validate the experimental microstate or a specific pH."
    )
    assert translated["user_note"]["mensaje"] == (
        "La persona escribió esta nota en español y se conserva como dato."
    )
    assert translated["muegge_violations"] == [
        "more than 15 rotatable bonds",
        "MW outside 200-600",
    ]
    assert translated["fallback_reason"] == (
        "Family 'protease' has no validated model (quality gate: p 0.266 >= 0.05) — "
        "the universal model was used."
    )
    assert translated["protonation_method"] == (
        "Meeko 0.7.1; template-based assignment, with no experimental pH declared"
    )
    assert translated["poblaciones_motivo"] == (
        "No validated population model is available, so no candidate is excluded. "
        "The RDKit canonical form is a reproducible representation, not the dominant state."
    )
    assert not (tmp_path / "i18n_faltantes.jsonl").exists()


def test_advertencias_cientificas_se_traducen_y_el_reporte_ignora_negacion_inglesa(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _install_inline_threadpool(monkeypatch)
    monkeypatch.setenv("LOCAL_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("MOLDESIGN_I18N_REPORT", "1")
    advertencia_es = (
        "⚠️ Molécula grande (58 átomos pesados, 19 enlaces rotables) — el docking será lento "
        "(búsqueda conformacional extensa). Si el tiempo es un límite, revisa el tamaño de la caja "
        "y la exhaustividad de Vina; reducirlos limita la búsqueda y puede cambiar las poses."
    )
    aviso_en = (
        "PoseBusters in `dock` mode—without ground truth, which is not available in production. "
        "No chemistry or geometry checks fail."
    )
    assert i18n._SPANISH_MARKERS.search("No hay evidencia registrada.")
    assert not i18n._SPANISH_MARKERS.search(aviso_en)
    token = i18n.set_request_locale("en")
    try:
        body = _body(
            _response({"scientific_warnings": [advertencia_es, aviso_en]}),
            endpoint="/evaluation/result/example",
        )
    finally:
        i18n.reset_request_locale(token)

    traducido = json.loads(body)["scientific_warnings"]
    assert traducido[0].startswith("Large molecule (58 heavy atoms, 19 rotatable bonds)")
    assert traducido[1] == aviso_en
    assert not (tmp_path / "i18n_faltantes.jsonl").exists()
