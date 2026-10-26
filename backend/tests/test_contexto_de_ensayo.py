"""El contexto de ensayo frente a la corrida (C-GAP-02, auditoría científica, Fase C).

Las condiciones del ensayo y el constructo sólo viajaban como texto libre: nada
contrastaba su pH, sus cadenas o sus cofactores con lo que la corrida preparó, y una
discrepancia no dejaba rastro. Lo que fijan estas pruebas, con la regla que la
auditoría escribió antes de que existiera el código:

1. **Matriz de metadatos completa.** El 100 % de las discrepancias declaradas se
   señala, y ningún campo omitido se rotula coincidente ni discrepante.
2. Sin contexto de ensayo no aparece ningún requisito nuevo: lo omitido es
   desconocido, no una alerta inventada.
3. Una discrepancia pide revisión y se resuelve con una decisión registrada, como el
   resto de Preparación.
4. El ZIP transmite valores, fuentes y decisiones, y el estado de cada comparación se
   recalcula desde el paquete sin el disco de quien lo generó.

Esto no valida ninguna afinidad: compara lo que el investigador declara del ensayo
con lo que la corrida registró.
"""

from __future__ import annotations

import io
import itertools
import json
import zipfile

import pytest
from pydantic import ValidationError

from core.i18n_plantillas import _PARECE_CASTELLANO
from services.dossier.contexto_ensayo import CONTRATO, TOLERANCIA_PH, clasificar
from services.dossier.localization import traducir_dossier
from services.dossier.model import build_case_dossier
from services.dossier.package import construir_paquete
from services.dossier.pdf import render_dossier_pdf
from services.dossier.preparacion import PREFIJO_DECISION, build_preparacion
from services.dossier.schemas import ContextoCientifico, ContextoDeEnsayo, DecisionHumana
from tests.test_diff_de_especies_de_la_corrida import _diff
from tests.test_preparacion_auditoria import _con_procedencia, _requisito

HUELLA = "tarea:task-completa-0001"
CLAVES = ("entorno.ensayo.ph", "entorno.ensayo.cadenas", "entorno.ensayo.cofactores")


def _caso(assay: dict | None, *, ph_corrida: float | None = 7.4,
          cofactores_corrida: list[str] | None | str = "ausente") -> dict:
    """La corrida del fixture (cadenas preparadas «R»), con el pH y los cofactores pedidos."""
    protonacion = ({"aplicada": True, "motor": "dimorphite-dl", "ph": ph_corrida}
                   if ph_corrida is not None else
                   {"aplicada": False, "motor": None, "ph": None, "motivo": "sin dimorphite"})
    caso = _con_procedencia(_diff(), protonacion=protonacion)
    prep = caso["eval_result"].docking_protocol["execution_provenance"]["receptor_prep"]
    prep["prepared_chains"] = ["R"]
    if cofactores_corrida != "ausente":
        prep["cofactors_whitelist"] = cofactores_corrida
    contexto = caso["projection"].context.model_copy(
        update={"assay": None if assay is None else ContextoDeEnsayo(**assay)})
    caso["projection"] = caso["projection"].model_copy(update={"context": contexto})
    return caso


def _auditar(caso: dict) -> dict:
    return build_preparacion(build_case_dossier(**caso), caso["eval_result"], caso["projection"])


def _requisitos_del_ensayo(auditoria: dict) -> dict[str, dict]:
    return {r["clave"]: r for b in auditoria["bloques"] for r in b["requisitos"]
            if r["clave"].startswith("entorno.ensayo")}


# ── El contrato ──────────────────────────────────────────────────────


def test_todo_el_contrato_es_opcional_y_versionado():
    vacio = ContextoDeEnsayo()
    assert vacio.version == 1
    assert all(getattr(vacio, c) is None for c in
               ("ph", "temperature_c", "endpoint", "protein_construct", "chains", "cofactors", "source"))
    assert ContextoCientifico().assay is None


@pytest.mark.parametrize("malo", [
    {"ph": 15}, {"ph": -1}, {"version": 2}, {"chains": ["A B"]}, {"cofactors": [""]},
    {"desconocido": 1}, {"source": "C:\\Users\\alguien\\ensayo.xlsx"},
])
def test_el_contrato_rechaza_lo_que_no_es_suyo(malo):
    with pytest.raises(ValidationError):
        ContextoDeEnsayo(**malo)


# ── 1 · La matriz de metadatos ───────────────────────────────────────


@pytest.mark.parametrize("ensayo,corrida,esperado", [
    (7.4, 7.4, "coincide"),
    (7.4, 7.4 + TOLERANCIA_PH, "coincide"),
    (7.4, 7.4 + TOLERANCIA_PH + 0.01, "discrepancia"),
    (5.5, 7.4, "discrepancia"),
    (None, 7.4, "desconocido"),
    (7.4, None, "desconocido"),
    (None, None, "desconocido"),
])
def test_ph(ensayo, corrida, esperado):
    assert clasificar("ph", ensayo, corrida) == esperado


@pytest.mark.parametrize("campo", ["cadenas", "cofactores"])
@pytest.mark.parametrize("ensayo,corrida,esperado", [
    (["A"], ["a"], "coincide"),
    (["B", "A"], ["A", "B", "A"], "coincide"),
    (["A"], ["A", "B"], "discrepancia"),
    (["ZN"], [], "discrepancia"),       # registrada vacía: no se conservó ninguno
    ([], [], "coincide"),
    (None, ["A"], "desconocido"),
    (["A"], None, "desconocido"),       # la corrida no lo registró
])
def test_listas(campo, ensayo, corrida, esperado):
    assert clasificar(campo, ensayo, corrida) == esperado


_PH = {"omitido": None, "igual": 7.4, "distinto": 5.5}
_CADENAS = {"omitido": None, "igual": ["R"], "distinto": ["A"]}
_COFACTORES = {"omitido": None, "igual": ["ZN"], "distinto": ["MG"]}


@pytest.mark.parametrize("ph,cadenas,cofactores", list(itertools.product(_PH, _CADENAS, _COFACTORES)))
def test_matriz_completa_sobre_la_auditoria(ph, cadenas, cofactores):
    """27 fichas: cada campo omitido, igual o distinto a lo que la corrida registró."""
    auditoria = _auditar(_caso({"ph": _PH[ph], "chains": _CADENAS[cadenas],
                                "cofactors": _COFACTORES[cofactores]},
                               cofactores_corrida=["ZN"]))
    requisitos = _requisitos_del_ensayo(auditoria)
    for clave, declarado in zip(CLAVES, (ph, cadenas, cofactores)):
        if declarado == "omitido":
            assert clave not in requisitos                       # ni coincide ni discrepa
        elif declarado == "igual":
            assert requisitos[clave]["estado"] == "REGISTRADO"
            assert clave not in auditoria["en_revision"]
        else:
            assert requisitos[clave]["estado"] == "REVISAR"
            assert clave in auditoria["en_revision"]
            assert requisitos[clave]["accion_recomendada"]
        if declarado != "omitido":
            assert requisitos[clave]["imprescindible"] is False  # revisión, no bloqueo


# ── 2 · Lo omitido es desconocido ────────────────────────────────────


def test_sin_contexto_de_ensayo_no_aparece_ningun_requisito():
    auditoria = _auditar(_caso(None))
    assert _requisitos_del_ensayo(auditoria) == {}
    assert not any(c.startswith("entorno.ensayo") for c in auditoria["en_revision"])


def test_ubicacion_sigue_describiendo_solo_huecos_aunque_haya_ensayo():
    """La interfaz exige a cada entrada de `ubicacion` la forma de un hueco del esqueleto.

    El contexto de ensayo se metió ahí una vez y un caso con `assay` declarado dejó de abrir Preparación
    (HTTP 200 convertido en «forma que esta versión no conoce»). Lo encontró la entrega de la interfaz.
    """
    huecos = {"chain", "after", "before", "c_n_distance_A", "distance_to_box_A", "missing_declared", "site_critical"}
    auditoria = _auditar(_caso({"ph": 5.5, "chains": ["A"], "cofactors": ["ZN"], "temperature_c": 25,
                                "endpoint": "Ki", "source": "CHEMBL853189"}))
    con_ensayo = [r for b in auditoria["bloques"] for r in b["requisitos"] if "ensayo" in r]
    assert len(con_ensayo) >= 4
    for requisito in (r for b in auditoria["bloques"] for r in b["requisitos"]):
        for entrada in requisito.get("ubicacion", []):
            assert huecos <= set(entrada), (requisito["clave"], sorted(entrada))
        if "ensayo" in requisito:
            assert "ubicacion" not in requisito, requisito["clave"]


def test_lo_que_no_tiene_contraparte_se_transmite_sin_compararse():
    auditoria = _auditar(_caso({"temperature_c": 25, "endpoint": "Ki", "protein_construct": "dominio quinasa",
                                "source": "CHEMBL853189"}))
    requisitos = _requisitos_del_ensayo(auditoria)
    assert list(requisitos) == ["entorno.ensayo"]
    resumen = requisitos["entorno.ensayo"]
    assert resumen["estado"] == "REGISTRADO"
    assert resumen["ensayo"] == {"contrato": CONTRATO, "declarados_sin_contraparte": {
        "temperature_c": 25.0, "endpoint": "Ki", "protein_construct": "dominio quinasa",
        "source": "CHEMBL853189"}}
    assert "ubicacion" not in resumen


def test_si_la_corrida_no_lo_registro_la_comparacion_no_se_hace():
    """El ensayo declara pH y cofactores; la corrida no registró ninguno de los dos."""
    auditoria = _auditar(_caso({"ph": 7.4, "cofactors": ["ZN"]}, ph_corrida=None))
    requisitos = _requisitos_del_ensayo(auditoria)
    for clave in ("entorno.ensayo.ph", "entorno.ensayo.cofactores"):
        assert requisitos[clave]["estado"] == "NO_DISPONIBLE"
        assert requisitos[clave]["valor"] is None
        assert "no se pudo hacer" in requisitos[clave]["razon"]
        assert requisitos[clave]["ensayo"]["estado"] == "desconocido"


def test_una_lista_vacia_registrada_si_se_compara():
    auditoria = _auditar(_caso({"cofactors": ["ZN"]}, cofactores_corrida=[]))
    cofactores = _requisitos_del_ensayo(auditoria)["entorno.ensayo.cofactores"]
    assert cofactores["estado"] == "REVISAR"
    assert cofactores["razon"] == "El ensayo declara ZN y la corrida conservó ∅."


# ── 3 · La discrepancia se decide ────────────────────────────────────


def test_una_decision_justificada_resuelve_la_discrepancia():
    caso = _caso({"ph": 5.5})
    motivo = "El ligando no tiene centros ionizables entre 5,5 y 7,4."
    caso["projection"] = caso["projection"].model_copy(update={"decisions": [DecisionHumana(
        control_code=PREFIJO_DECISION + "entorno.ensayo.ph", fingerprint=HUELLA,
        at="2026-10-20T22:00:00Z", note=motivo)]})
    auditoria = _auditar(caso)
    ph = _requisitos_del_ensayo(auditoria)["entorno.ensayo.ph"]
    assert ph["estado"] == "REVISAR"                              # el dato no cambia
    assert ph["razon"] == ("El ensayo declara pH 5.5 y el ligando se protonó a pH 7.4: "
                           "la especie acoplada puede no ser la del ensayo.")
    assert ph["decision"]["resuelve"] is True
    assert "entorno.ensayo.ph" in auditoria["decididos"]
    assert "entorno.ensayo.ph" not in auditoria["en_revision"]


def test_en_ingles_no_queda_castellano():
    en = traducir_dossier(_auditar(_caso(
        {"ph": 5.5, "chains": ["A"], "cofactors": ["ZN"], "temperature_c": 25},
        cofactores_corrida=[])), "en")
    for requisito in _requisitos_del_ensayo(en).values():
        for campo in ("etiqueta", "valor", "razon", "accion_recomendada"):
            texto = requisito.get(campo)
            if texto:
                assert not _PARECE_CASTELLANO.search(texto), (requisito["clave"], campo, texto)


# ── 4 · El paquete lo transmite y se reconstruye ─────────────────────


def test_el_zip_transmite_el_contexto_y_se_recalcula_sin_el_disco():
    caso = _caso({"ph": 5.5, "chains": ["R"], "cofactors": ["ZN"], "source": "doi:10.1000/x"},
                 cofactores_corrida=[])
    auditoria = _auditar(caso)
    dossier = build_case_dossier(**caso)
    datos, _, raiz = construir_paquete(
        dossier=dossier, pdf_bytes=render_dossier_pdf(dossier).getvalue(),
        projection_json=caso["projection"].model_dump_json(indent=2), preparacion=auditoria)
    with zipfile.ZipFile(io.BytesIO(datos)) as zf:
        snapshot = json.loads(zf.read(f"{raiz}/case/case_snapshot.json"))
        audit = json.loads(zf.read(f"{raiz}/preparacion/audit.json"))

    declarado = snapshot["context"]["assay"]
    assert declarado["ph"] == 5.5 and declarado["source"] == "doi:10.1000/x"
    comparaciones = [r["ensayo"] for b in audit["bloques"] for r in b["requisitos"]
                     if r["clave"] in CLAVES]
    assert {c["campo"] for c in comparaciones} == {"ph", "cadenas", "cofactores"}
    llave = {"ph": "ph", "cadenas": "chains", "cofactores": "cofactors"}
    for c in comparaciones:
        assert c["contrato"] == CONTRATO and c["fuente_ensayo"] and c["fuente_corrida"]
        ensayo = declarado[llave[c["campo"]]]
        assert c["ensayo"] == (ensayo if c["campo"] == "ph" else sorted(ensayo))
        # El estado se recalcula con los valores que lleva el paquete.
        assert clasificar(c["campo"], c["ensayo"], c["corrida"]) == c["estado"]
    assert {c["campo"]: c["estado"] for c in comparaciones} == {
        "ph": "discrepancia", "cadenas": "coincide", "cofactores": "discrepancia"}
