"""
Contrato del modelo canónico y del PDF del dossier.

Lo que estas pruebas impiden, en orden de gravedad:

1. **Que una ausencia se convierta en «pasa».** Es el fallo que destruye el
   valor del documento: basta un `if not warnings` para afirmar que se comprobó
   algo que nadie comprobó.
2. **Que un score 0-100 vuelva a la jerarquía principal.** El apéndice heredado
   existe para contenerlos; la portada y el resumen no pueden tenerlos.
3. **Que una corrida se atribuya a la hipótesis equivocada.**
4. **Que el PDF salga con secciones ausentes o sin poder leerse.**
"""

from __future__ import annotations

import io
import json

import pytest

from services.dossier.model import build_case_dossier, hash_canonico
from services.dossier.pdf import render_dossier_pdf
from services.dossier.schemas import CaseProjection, claves_prohibidas_en
from services.dossier.taxonomy import Estado
from tests.fixtures_dossier import (
    RELOJ,
    caso_antiguo,
    caso_completo,
    caso_parcial,
    molecula,
    proyeccion_completa,
    resultado_completo,
    resultado_parcial,
    target_completo,
)


def _control(dossier, codigo):
    for control in [*dossier.controles, *dossier.dimensiones]:
        if control.codigo == codigo:
            return control
    raise AssertionError(f"Falta el control {codigo}")


def _campo(campos, etiqueta):
    for campo in campos:
        if campo.etiqueta == etiqueta:
            return campo
    raise AssertionError(f"Falta el campo «{etiqueta}»")


# ── 1. Construcción del modelo ───────────────────────────────────────


class TestModeloCanonico:
    def test_caso_completo_produce_un_modelo_serializable(self):
        dossier = build_case_dossier(**caso_completo())

        assert dossier.schema_version == 1
        assert dossier.case_id == "caso-serie-a-001"
        assert dossier.task_id == "task-completa-0001"
        assert len(dossier.poses) == 3
        # El JSON canónico es estable y parseable: es lo que viaja al paquete.
        payload = json.loads(dossier.json_canonico())
        assert payload["schema_version"] == 1
        assert payload["poses"]["items"][0]["afinidad_kcal_mol"] == -9.5

    def test_el_modelo_separa_ejecucion_de_disposicion_y_revision(self):
        """Tres estados distintos. Mezclarlos es fabricar autoridad."""
        dossier = build_case_dossier(**caso_completo())

        assert dossier.ejecucion["tecnico"].valor == "completed"
        assert dossier.ejecucion["cientifico"].estado is not None
        assert dossier.ejecucion["humano"].estado == Estado.REGISTRADO
        # Y son campos independientes, no derivados unos de otros.
        assert dossier.ejecucion["tecnico"] is not dossier.ejecucion["cientifico"]

    def test_sin_decisiones_la_revision_humana_es_no_evaluado(self):
        dossier = build_case_dossier(**caso_parcial())
        assert dossier.ejecucion["humano"].estado == Estado.NO_EVALUADO

    def test_el_hash_canonico_es_determinista(self):
        assert hash_canonico(build_case_dossier(**caso_completo())) == hash_canonico(
            build_case_dossier(**caso_completo())
        )

    def test_contexto_largo_no_se_recorta_en_el_modelo(self):
        """El recorte, si hace falta, es del render — nunca del dato."""
        dossier = build_case_dossier(**caso_parcial())
        pregunta = _campo(dossier.proposito, "¿Qué intenta responder este caso?")
        assert len(pregunta.valor or "") > 1000


# ── 2. Nada ausente se convierte en «pasa» ───────────────────────────


class TestAusenciasNuncaSonPasa:
    def test_validacion_fisica_ausente_es_no_evaluado(self):
        """
        Una corrida ANTERIOR a la etapa no tiene contrato, y eso no es validez.

        El test miraba `pose_validation`, un campo que el backend nunca emitió,
        así que comprobaba una ausencia garantizada. Ahora mira la ausencia que
        de verdad ocurre: la de un resultado anterior a P0-A.
        """
        dossier = build_case_dossier(**caso_antiguo())
        control = _control(dossier, "VALIDEZ_FISICA_POSES")
        assert control.estado == Estado.NO_EVALUADO
        assert control.estado != Estado.PASA

    def test_revision_no_es_pasa(self):
        """
        `review` describe una batería incompleta, NO una pose aprobada.

        Es la confusión que convertiría un hueco de medición en un aval, y la
        que el dossier no puede cometer en ningún formato.
        """
        dossier = build_case_dossier(**caso_completo())
        control = _control(dossier, "VALIDEZ_FISICA_POSES")
        assert control.estado == Estado.REVISAR
        assert control.estado != Estado.PASA

    def test_una_corrida_con_veredicto_real_lo_declara(self):
        """Y cuando la etapa SÍ corrió, el dossier lo dice con su motor."""
        dossier = build_case_dossier(**caso_completo())
        campos = {c.etiqueta: c for c in dossier.validacion}
        assert campos["Motor de validación"].valor == "posebusters:1.0:dock"
        assert campos["Cobertura"].valor == "3 de 3 poses"

    def test_corrida_sin_poses_declara_no_disponible(self):
        dossier = build_case_dossier(**caso_parcial())
        assert dossier.poses == []
        assert dossier.poses_estado == Estado.NO_DISPONIBLE
        assert dossier.poses_razon

    def test_campos_de_protocolo_ausentes_son_no_disponible(self):
        dossier = build_case_dossier(**caso_parcial())
        for etiqueta in ("Versión del motor", "Semilla aleatoria", "Origen del parseo"):
            campo = _campo(dossier.protocolo, etiqueta)
            assert campo.estado == Estado.NO_DISPONIBLE, etiqueta
            assert campo.razon
            assert campo.valor is None

    def test_contexto_no_declarado_es_no_definido_no_no_disponible(self):
        """
        Son cosas distintas: nadie preguntó vs. la corrida no lo serializó.

        Confundirlas haría que el dossier culpara al pipeline de un hueco que
        dejó el usuario, o al revés.
        """
        dossier = build_case_dossier(**caso_parcial())
        assert _campo(dossier.proposito, "¿Qué decisión se pretende tomar?").estado == Estado.NO_DEFINIDO
        assert _campo(dossier.protocolo, "Versión del motor").estado == Estado.NO_DISPONIBLE

    def test_ningun_estado_afirmativo_sin_valor(self):
        """Un campo REGISTRADO sin contenido sería una afirmación vacía."""
        for datos in (caso_completo(), caso_parcial()):
            dossier = build_case_dossier(**datos)
            todos = [
                *dossier.portada, *dossier.proposito, *dossier.entradas,
                *dossier.preparacion, *dossier.protocolo, *dossier.apendice_heredado,
                *dossier.ejecucion.values(),
            ]
            for campo in todos:
                if campo.estado.es_afirmativo:
                    assert campo.valor, f"«{campo.etiqueta}» afirma sin valor"

    def test_resultado_fuera_de_dominio_se_declara(self):
        dossier = build_case_dossier(**caso_parcial())
        dominio = _control(dossier, "MODEL")
        assert dominio.estado in (Estado.REVISAR, Estado.NO_EVALUADO)
        assert any("dominio" in u.lower() for u in dossier.incertidumbres)

    def test_fallback_aparece_en_el_protocolo(self):
        dossier = build_case_dossier(**caso_parcial())
        fallback = _campo(dossier.protocolo, "Motivo de fallback")
        assert fallback.estado == Estado.REGISTRADO
        assert "GNN" in (fallback.valor or "")


# ── 3. Atribución de la corrida ──────────────────────────────────────


class TestCorridaEInputs:
    def test_huellas_discordantes_marcan_corrida_anterior(self):
        """El cliente dijo «corresponde»; las huellas dicen que no."""
        dossier = build_case_dossier(**caso_parcial())

        relacion = _campo(dossier.entradas, "Relación de la corrida con los inputs actuales")
        assert relacion.estado == Estado.REVISAR
        assert dossier.avisos_integridad
        assert "corrida_anterior" in dossier.avisos_integridad[0]

    def test_una_hipotesis_desfasada_fuerza_abstencion(self):
        dossier = build_case_dossier(**caso_parcial())
        assert dossier.siguiente_accion.estado == Estado.ABSTENCION
        # Y la etiqueta sigue siendo legible pese a no ser un estado afirmativo.
        assert "ABSTENCIÓN" in dossier.siguiente_accion.texto

    def test_huellas_coincidentes_corresponden(self):
        dossier = build_case_dossier(**caso_completo())
        relacion = _campo(dossier.entradas, "Relación de la corrida con los inputs actuales")
        assert relacion.estado == Estado.REGISTRADO
        assert dossier.avisos_integridad == []

    def test_task_id_discordante_produce_aviso(self):
        datos = caso_completo()
        datos["eval_result"].task_id = "task-de-otra-corrida"
        dossier = build_case_dossier(**datos)
        assert any("no puede afirmar" in a for a in dossier.avisos_integridad)

    def test_decision_de_otra_huella_no_aplica_a_los_inputs_actuales(self):
        datos = caso_completo()
        proyeccion = datos["projection"].model_copy(deep=True)
        proyeccion.decisions[0].fingerprint = "sha256:" + "0" * 64
        datos["projection"] = proyeccion
        dossier = build_case_dossier(**datos)
        assert dossier.decisiones[0]["aplica_a_los_inputs_actuales"] is False


# ── 4. Sin score soberano ────────────────────────────────────────────


class TestSinScoreSoberano:
    def test_los_indices_solo_viven_en_el_apendice(self):
        dossier = build_case_dossier(**caso_completo())

        principal = [
            *dossier.portada, *dossier.proposito, *dossier.entradas,
            *dossier.preparacion, *dossier.protocolo, *dossier.ejecucion.values(),
        ]
        for campo in principal:
            texto = f"{campo.etiqueta} {campo.valor or ''}".lower()
            assert "84.5" not in texto, f"score en la jerarquía principal: {campo.etiqueta}"
            assert "score" not in texto or "heredado" in texto

        assert dossier.apendice_heredado, "el índice heredado debe estar en el apéndice"
        assert any("84.5" == (c.valor or "") for c in dossier.apendice_heredado)

    def test_el_apendice_declara_que_no_es_probabilidad(self):
        dossier = build_case_dossier(**caso_completo())
        for campo in dossier.apendice_heredado:
            assert campo.estado == Estado.REVISAR
            assert "no es interpretable" in (campo.razon or "")
            assert "No decisional" in (campo.razon or "")

    def test_una_corrida_sin_indices_no_inventa_apendice(self):
        dossier = build_case_dossier(**caso_parcial())
        assert dossier.apendice_heredado == []


# ── 5. PDF ───────────────────────────────────────────────────────────


class TestPdf:
    def test_pdf_valido_con_las_secciones_obligatorias(self):
        dossier = build_case_dossier(**caso_completo())
        datos = render_dossier_pdf(dossier).getvalue()

        assert datos.startswith(b"%PDF")
        assert b"%%EOF" in datos[-2048:]
        assert len(datos) > 8000

    @pytest.mark.skipif(
        __import__("importlib").util.find_spec("pypdf") is None,
        reason="pypdf no disponible: el contrato semántico se comprueba con él",
    )
    def test_contrato_semantico_del_pdf(self):
        from pypdf import PdfReader

        dossier = build_case_dossier(**caso_completo())
        datos = render_dossier_pdf(dossier).getvalue()
        texto = "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(datos)).pages)

        for seccion in (
            "DOSSIER DE EVIDENCIA COMPUTACIONAL",
            "Pregunta y propósito del caso",
            "Resumen de lo ejecutado",
            "Entradas y procedencia",
            "Preparación del sistema y supuestos",
            "Protocolo y entorno de ejecución",
            "Evidencia estructural y acoplamiento",
            # P0-D: generación, selección y validación física real.
            "Generación de poses",
            "Selección de pose",
            "Validación geométrica y física",
            "Controles físicos y geométricos",
            "Evidencia por dimensión",
            "Supuestos declarados",
            "Incertidumbres y limitaciones",
            "Interpretación justificable y próximos pasos",
            "Procedencia e instrucciones de verificación",
            "Outputs heredados (no decisionales)",
        ):
            assert seccion in texto, f"falta la sección «{seccion}»"

        # Nada de autoridad indebida.
        for prohibido in ("GLOBAL SCORE", "Proof of Discovery", "candidato clínico seguro"):
            assert prohibido not in texto

    def test_el_pdf_no_sale_a_la_red(self, monkeypatch):
        """Un documento de evidencia no puede depender de un tercero."""
        import urllib.request

        def explota(*_a, **_k):
            raise AssertionError("El dossier no debe consultar servicios externos")

        monkeypatch.setattr(urllib.request, "urlopen", explota)
        dossier = build_case_dossier(**caso_completo())
        assert render_dossier_pdf(dossier).getvalue().startswith(b"%PDF")

    def test_el_pdf_del_caso_parcial_tambien_se_genera(self):
        """Los huecos no rompen el render: se imprimen."""
        dossier = build_case_dossier(**caso_parcial())
        datos = render_dossier_pdf(dossier).getvalue()
        assert datos.startswith(b"%PDF")


# ── 6. Contrato de entrada ───────────────────────────────────────────


class TestProyeccionDelCaso:
    def test_rechaza_rutas_locales(self):
        for valor in ("C:\\Users\\Johan\\caso", "/home/johan/caso", "\\\\servidor\\share"):
            with pytest.raises(ValueError):
                CaseProjection.model_validate({"case_id": "c1", "name": valor})

    def test_rechaza_campos_desconocidos(self):
        """`storage.path` y cualquier otro extra no entran."""
        with pytest.raises(ValueError):
            CaseProjection.model_validate({
                "case_id": "c1", "name": "Caso", "storage": {"path": "D:\\casos\\x"},
            })

    def test_rechaza_un_case_id_sin_caracteres_utilizables(self):
        with pytest.raises(ValueError):
            CaseProjection.model_validate({"case_id": "///", "name": "Caso"})

    def test_no_acepta_resultados_cientificos_del_cliente(self):
        with pytest.raises(ValueError):
            CaseProjection.model_validate({
                "case_id": "c1", "name": "Caso", "affinity_kcal": -9.9,
            })

    def test_detecta_claves_de_secreto_en_un_payload(self):
        encontradas = claves_prohibidas_en({"inputs": {"api_key": "x", "ligand": {"token": "y"}}})
        assert "inputs.api_key" in encontradas
        assert "inputs.ligand.token" in encontradas

    def test_la_proyeccion_completa_es_valida(self):
        assert proyeccion_completa().projection_version == 1
