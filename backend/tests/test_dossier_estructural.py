"""
La evidencia estructural llega íntegra al PDF, al JSON y al manifiesto.

Lo que protegen, en orden de gravedad:

1. **Coherencia entre formatos.** El PDF, `case_snapshot.json` y el manifiesto
   describen la MISMA corrida. Si cada uno la interpretara por su cuenta, una
   discrepancia entre el documento legible y el paquete verificable destruiría
   el valor de los dos: el lector no sabría cuál creer.

2. **`review` y `not_evaluated` NUNCA son validez.** Uno describe una batería
   que no corrió entera; el otro, un validador que no corrió. Ninguno dice nada
   sobre la molécula, y ninguno autoriza la palabra «válida».

3. **La pose sugerida que falla NO se sustituye.** El dossier declara revisión
   y lista las alternativas, sin elegir ninguna.

4. **Integridad no es validez científica.** Un checksum correcto prueba que los
   bytes no cambiaron. El paquete tiene que decirlo con esas palabras.

5. **Nada se esconde.** Abstenciones, fallos, exclusiones y moléculas no
   evaluadas aparecen con su causa, o el informe no es una cobertura.
"""

from __future__ import annotations

import io
import json
import zipfile

import pytest

from services.dossier.model import build_case_dossier, hash_canonico
from services.dossier.package import construir_paquete
from services.dossier.pdf import render_dossier_pdf
from services.dossier.taxonomy import Estado
from tests.fixtures_dossier import (
    caso_antiguo,
    caso_completo,
    caso_parcial,
    caso_selector_abstenido,
    caso_validacion_parcial,
)

pypdf = pytest.importorskip("pypdf", reason="el contrato del PDF se lee con pypdf")


def _texto_pdf(dossier) -> str:
    datos = render_dossier_pdf(dossier).getvalue()
    return "\n".join(p.extract_text() or "" for p in pypdf.PdfReader(io.BytesIO(datos)).pages)


def _campos(bloque) -> dict[str, object]:
    return {c.etiqueta: c for c in bloque}


# ── 1. Coherencia API → PDF → JSON → manifiesto ──────────────────────


class TestCoherenciaEntreFormatos:
    def test_los_tres_formatos_dicen_lo_mismo_de_la_seleccion(self):
        dossier = build_case_dossier(**caso_completo())
        texto = _texto_pdf(dossier)
        datos = dossier.as_dict()

        # El modelo canónico.
        seleccion = _campos(dossier.seleccion)
        assert seleccion["Pose principal del producto (Vina top-1)"].valor == "#1"
        assert seleccion["Pose recomendada por el selector"].valor == "#2"

        # El JSON que viaja al paquete.
        por_etiqueta = {c["etiqueta"]: c for c in datos["seleccion"]}
        assert por_etiqueta["Pose principal del producto (Vina top-1)"]["valor"] == "#1"
        assert por_etiqueta["Pose recomendada por el selector"]["valor"] == "#2"

        # Y el PDF.
        assert "Selección de pose" in texto
        assert "Vina top-1" in texto

    def test_el_paquete_ancla_pdf_json_y_manifiesto_al_mismo_objeto(self):
        dossier = build_case_dossier(**caso_completo())
        pdf = render_dossier_pdf(dossier).getvalue()
        datos, entradas, _ = construir_paquete(
            dossier=dossier, pdf_bytes=pdf, projection_json="{}", artefactos=(),
        )

        with zipfile.ZipFile(io.BytesIO(datos)) as z:
            raiz = z.namelist()[0].split("/")[0]
            manifiesto = json.loads(z.read(f"{raiz}/manifest.json"))
            modelo = json.loads(z.read(f"{raiz}/case/dossier_model.json"))
            resumen = json.loads(z.read(f"{raiz}/evidencia/evidence_summary.json"))

        # El manifiesto sella el modelo canónico, y el JSON ES ese modelo.
        assert manifiesto["dossier_model_sha256"] == hash_canonico(dossier)
        assert modelo["seleccion"] == dossier.as_dict()["seleccion"]
        assert modelo["validacion_fisica"] == dossier.as_dict()["validacion_fisica"]
        # Y el resumen de evidencia del paquete no contradice al modelo.
        assert resumen["controles"] == dossier.as_dict()["controles"]

    def test_la_evidencia_por_pose_es_la_misma_en_json_y_en_pdf(self):
        dossier = build_case_dossier(**caso_completo())
        texto = _texto_pdf(dossier)
        por_pose = dossier.as_dict()["validacion_fisica"]["por_pose"]

        assert [p["rango"] for p in por_pose] == [1, 2, 3]
        assert [p["estado_fisico_codigo"] for p in por_pose] == ["passed", "failed", "passed"]
        # La pose que falla nombra SU control, no un recuento anónimo.
        assert por_pose[1]["checks_que_fallan"] == ["internal_energy"]
        assert "internal_energy" in texto


# ── 2. `review` y `not_evaluated` nunca son validez ──────────────────


class TestNadaAusenteEsValidez:
    def test_solo_passed_marca_una_pose_como_fisicamente_valida(self):
        dossier = build_case_dossier(**caso_completo())
        por_pose = {p.rango: p for p in dossier.evidencia_poses}

        assert por_pose[1].fisicamente_valida is True
        assert por_pose[2].fisicamente_valida is False   # failed
        assert por_pose[3].fisicamente_valida is True

    def test_una_validacion_parcial_no_se_redondea_a_completa(self):
        dossier = build_case_dossier(**caso_validacion_parcial())
        campos = _campos(dossier.validacion)

        assert campos["Cobertura"].valor == "1 de 3 poses"
        no_evaluadas = [p for p in dossier.evidencia_poses if p.estado_fisico_codigo == "not_evaluated"]
        assert len(no_evaluadas) == 2
        assert all(p.fisicamente_valida is False for p in no_evaluadas)
        # Y la razón viaja, no se pierde.
        assert campos["Código de razón"].valor == "MAPA_SIN_HIDROGENOS_POLARES"

    def test_el_pdf_dice_que_revision_no_es_pose_aprobada(self):
        texto = _texto_pdf(build_case_dossier(**caso_completo()))
        assert "no corrió entera" in texto or "no es una pose aprobada" in texto.lower()

    def test_una_corrida_antigua_no_es_un_fallo_de_las_poses(self):
        dossier = build_case_dossier(**caso_antiguo())
        campos = _campos(dossier.validacion)

        assert campos["Veredicto de la etapa"].estado == Estado.NO_EVALUADO
        assert dossier.evidencia_poses == []
        assert "anterior a la etapa" in campos["Veredicto de la etapa"].razon
        # Y el selector se lee como no ejecutado, no como abstenido.
        seleccion = _campos(dossier.seleccion)
        assert seleccion["Estado de la etapa de selección"].estado == Estado.NO_EVALUADO


# ── 3. La pose sugerida que falla no se sustituye ────────────────────


class TestLaSugeridaQueFallaNoSeSustituye:
    def test_se_declara_revision_y_se_listan_las_alternativas(self):
        dossier = build_case_dossier(**caso_completo())
        campos = _campos(dossier.validacion)
        seleccion = _campos(dossier.seleccion)

        # La sugerida sigue siendo la 2, y falla.
        assert seleccion["Pose recomendada por el selector"].valor == "#2"
        assert campos["Estado físico de la pose recomendada"].valor == "failed"
        # No se cambia por otra…
        assert "NO SE SUSTITUYE" in campos["Sustitución automática"].valor
        # …y las que pasan se listan sin quedar elegidas.
        assert seleccion["Alternativas físicamente válidas"].valor == "#1, #3"
        sugeridas = [p for p in dossier.evidencia_poses if p.es_sugerida]
        assert [p.rango for p in sugeridas] == [2]

    def test_el_pdf_lo_dice_con_todas_las_letras(self):
        texto = _texto_pdf(build_case_dossier(**caso_completo()))
        assert "NO SE SUSTITUYE" in texto
        assert "nadie tomó" in texto

    def test_la_discordancia_con_vina_top1_se_declara(self):
        dossier = build_case_dossier(**caso_completo())
        campos = _campos(dossier.seleccion)
        assert "NO es la top-1 de Vina" in campos["Discordancia entre la sugerida y Vina top-1"].valor
        assert any("no son la misma" in u for u in dossier.incertidumbres)


# ── 4. Selector ausente y abstenido ──────────────────────────────────


class TestSelector:
    def test_la_abstencion_se_declara_y_la_referencia_es_fallback(self):
        dossier = build_case_dossier(**caso_selector_abstenido())
        campos = _campos(dossier.seleccion)

        assert campos["Estado de la etapa de selección"].estado == Estado.ABSTENCION
        assert campos["Pose recomendada por el selector"].estado != Estado.REGISTRADO
        assert "FALLBACK" in campos["Referencia declarada"].valor
        assert campos["Razón de abstención"].valor == "MARGEN_BAJO_UMBRAL"
        # Lo medido se conserva: se puede auditar por qué se abstuvo.
        assert campos["Pose que habría recomendado (abstención)"].valor == "#2"
        assert "0.021" in campos["Margen de confianza y umbral"].valor
        # Y Vina top-1 sigue declarada.
        assert campos["Pose principal del producto (Vina top-1)"].valor == "#1"

    def test_el_selector_ausente_no_se_presenta_como_acierto(self):
        dossier = build_case_dossier(**caso_antiguo())
        campos = _campos(dossier.seleccion)
        assert "FALLBACK" in campos["Referencia declarada"].valor
        assert any("no se ejecutó" in u for u in dossier.incertidumbres)

    def test_el_modelo_y_su_hash_viajan_al_dossier(self):
        dossier = build_case_dossier(**caso_completo())
        campos = _campos(dossier.seleccion)
        assert campos["Modelo del selector"].valor == "pose_selector_v06"
        assert campos["SHA-256 del modelo"].valor == "b" * 64
        assert campos["SHA-256 de la metadata del modelo"].valor == "c" * 64


# ── 5. El ZIP: contenido, checksums y detección de alteración ────────


class TestPaquete:
    def _paquete(self, caso, artefactos=()):
        dossier = build_case_dossier(**caso)
        pdf = render_dossier_pdf(dossier).getvalue()
        return construir_paquete(
            dossier=dossier, pdf_bytes=pdf, projection_json="{}", artefactos=artefactos,
        )

    def test_los_checksums_cubren_todo_lo_presente_y_son_correctos(self):
        import hashlib

        datos, _, _ = self._paquete(caso_completo())
        with zipfile.ZipFile(io.BytesIO(datos)) as z:
            raiz = z.namelist()[0].split("/")[0]
            checksums = z.read(f"{raiz}/checksums.sha256").decode("utf-8")
            declarados = {
                linea.split("  ", 1)[1]: linea.split("  ", 1)[0]
                for linea in checksums.strip().splitlines() if "  " in linea
            }
            for path, esperado in declarados.items():
                real = hashlib.sha256(z.read(f"{raiz}/{path}")).hexdigest()
                assert real == esperado, path

        # Los tres ciclos de hash quedan fuera, y sólo esos.
        assert "checksums.sha256" not in declarados
        assert "manifest.json" in declarados

    def test_una_alteracion_de_un_byte_se_detecta(self):
        import hashlib

        datos, _, _ = self._paquete(caso_completo())
        with zipfile.ZipFile(io.BytesIO(datos)) as z:
            raiz = z.namelist()[0].split("/")[0]
            original = z.read(f"{raiz}/case/dossier_model.json")
            declarado = next(
                linea.split("  ", 1)[0]
                for linea in z.read(f"{raiz}/checksums.sha256").decode("utf-8").splitlines()
                if linea.endswith("case/dossier_model.json")
            )

        alterado = original.replace(b"passed", b"PASSED", 1)
        assert alterado != original
        assert hashlib.sha256(alterado).hexdigest() != declarado

    def test_el_paquete_es_determinista_bajo_el_mismo_reloj(self):
        primero, _, _ = self._paquete(caso_completo())
        segundo, _, _ = self._paquete(caso_completo())
        assert primero == segundo

    def test_el_readme_separa_integridad_de_validez_cientifica(self):
        datos, _, _ = self._paquete(caso_completo())
        with zipfile.ZipFile(io.BytesIO(datos)) as z:
            raiz = z.namelist()[0].split("/")[0]
            readme = z.read(f"{raiz}/README.md").decode("utf-8")
            receta = z.read(f"{raiz}/run/reproduce.md").decode("utf-8")

        # Lo primero que lee un verificador.
        assert "integridad, no validez" in readme
        assert "nunca sobre la ciencia" in readme
        assert "no prueba que el método fuera" in readme.lower()
        # Y la receta lo repite donde se explica cómo reproducir.
        assert "integridad, no validez" in receta
        assert "No afirma que el compuesto sea activo" in receta

    def test_la_receta_nombra_los_artefactos_estructurales(self):
        datos, _, _ = self._paquete(caso_completo())
        with zipfile.ZipFile(io.BytesIO(datos)) as z:
            raiz = z.namelist()[0].split("/")[0]
            receta = z.read(f"{raiz}/run/reproduce.md").decode("utf-8")

        for archivo in ("structural_evidence.json", "pose_selection.json",
                        "pose_index.json", "pose_selector_model.json"):
            assert archivo in receta, archivo
        # Y declara la garantía más fuerte: el SDF sólo aparece cuando
        # representa de verdad la colección. Con ensemble las poses salen de
        # una piscina de K corridas, así que el SDF de UNA conformación no es
        # la piscina — y el paquete no finge que lo sea.
        #
        # Se normalizan los espacios: la frase cruza saltos de línea y una
        # prueba que dependa del reflujo del párrafo se rompe al reescribirlo
        # sin que la garantía haya cambiado.
        plano = " ".join(receta.split())
        assert "outputs/poses.sdf" in plano
        assert "sólo cuando representa de verdad la colección" in plano
        assert "en un ensemble no se finge" in plano

    def test_los_artefactos_ausentes_se_declaran_en_vez_de_omitirse(self):
        from services.dossier.model import Artefacto

        ausente = Artefacto(
            rol="evidencia", nombre="structural_evidence.json",
            media_type="application/json", fuente="evaluation_results.structural_evidence",
            estado=Estado.NO_EVALUADO, contenido=None,
            razon="Esta corrida es anterior a la etapa de validación física.",
        )
        datos, entradas, _ = self._paquete(caso_antiguo(), artefactos=[ausente])

        declarado = next(e for e in entradas if e.path.endswith("structural_evidence.json"))
        assert declarado.estado == Estado.NO_EVALUADO.value
        assert declarado.razon
        # Se declara en el manifiesto aunque no exista dentro del ZIP.
        with zipfile.ZipFile(io.BytesIO(datos)) as z:
            raiz = z.namelist()[0].split("/")[0]
            manifiesto = json.loads(z.read(f"{raiz}/manifest.json"))
            nombres = z.namelist()
        paths = {f["path"] for f in manifiesto["files"]}
        assert "evidencia/structural_evidence.json" in paths
        assert f"{raiz}/evidencia/structural_evidence.json" not in nombres


# ── 6. Unicode, PDF renderizable y frases prohibidas ─────────────────


class TestRobustez:
    def test_unicode_sobrevive_al_pdf_y_al_json(self):
        caso = caso_completo()
        caso["eval_result"].structural_evidence = {
            **caso["eval_result"].structural_evidence,
            "poses": [
                {**caso["eval_result"].structural_evidence["poses"][0],
                 "detail": "Ångström · β-lámina · 甲基 · émétine — sin choques",
                 "checks_que_fallan": []},
            ],
            "poses_evaluated": 1,
            "poses_produced": 1,
        }
        dossier = build_case_dossier(**caso)

        crudo = dossier.json_canonico()
        assert "Ångström" in crudo and "甲基" in crudo
        # El JSON canónico se relee sin pérdida.
        assert json.loads(crudo)["validacion_fisica"]["por_pose"][0]["detalle"].startswith("Ångström")
        # Y el PDF se genera igual (reportlab puede no tener glifo CJK; lo que
        # se exige es que NO reviente el documento).
        datos = render_dossier_pdf(dossier).getvalue()
        assert datos.startswith(b"%PDF") and b"%%EOF" in datos[-2048:]

    @pytest.mark.parametrize(
        "caso",
        [caso_completo, caso_parcial, caso_antiguo, caso_selector_abstenido, caso_validacion_parcial],
        ids=["completo", "parcial", "antiguo", "abstenido", "validacion_parcial"],
    )
    def test_el_pdf_se_renderiza_en_todos_los_escenarios(self, caso):
        datos = render_dossier_pdf(build_case_dossier(**caso())).getvalue()
        assert datos.startswith(b"%PDF")
        assert b"%%EOF" in datos[-2048:]
        assert len(pypdf.PdfReader(io.BytesIO(datos)).pages) >= 4

    @pytest.mark.parametrize(
        "caso",
        [caso_completo, caso_parcial, caso_antiguo, caso_selector_abstenido, caso_validacion_parcial],
        ids=["completo", "parcial", "antiguo", "abstenido", "validacion_parcial"],
    )
    def test_ninguna_afirmacion_prohibida_en_ningun_escenario(self, caso):
        dossier = build_case_dossier(**caso())
        texto = _texto_pdf(dossier)
        crudo = dossier.json_canonico()

        # Frases que sólo pueden leerse como afirmación. Las que el dossier sí
        # usa —«no afirma que sea un candidato clínico»— son DESMENTIDOS, y
        # vetarlas por substring prohibiría al documento negar lo que no
        # sostiene, que es justo lo contrario de lo que pide el sprint.
        for prohibido in (
            "el compuesto es activo", "es un fármaco", "eficacia demostrada",
            "probabilidad de éxito del", "alta calidad farmacológica",
            "resultado prometedor", "GLOBAL SCORE", "Proof of Discovery",
            "validado experimentalmente",
        ):
            assert prohibido not in texto, prohibido
            assert prohibido not in crudo, prohibido

        # Y los desmentidos SÍ tienen que estar: un documento que no dijera qué
        # NO afirma dejaría al lector rellenando el hueco.
        assert "no es una recomendación clínica" in texto.lower()

    def test_los_indices_0_100_viven_solo_en_el_apendice_no_decisional(self):
        dossier = build_case_dossier(**caso_completo())
        etiquetas_apendice = {c.etiqueta for c in dossier.apendice_heredado}

        assert any("total_score" in e for e in etiquetas_apendice)
        for campo in dossier.apendice_heredado:
            assert campo.estado == Estado.REVISAR
            assert "no decisional" in (campo.razon or "").lower()

        # Y ninguna de las secciones nuevas los reintroduce.
        for bloque in (dossier.generacion, dossier.seleccion, dossier.validacion):
            for campo in bloque:
                assert "score" not in campo.etiqueta.lower()


# ── 7. El protocolo de generación 3D, declarado ──────────────────────


class TestProtocoloDeGeneracion:
    """
    El dossier decía siempre «no evaluado» porque el resultado no persistía el
    parámetro. Ahora se sella con la corrida, y las dos cifras —pedidas y
    conseguidas— se dicen por separado: contar sólo lo conseguido escondería si
    el ensemble hizo lo que se le pidió.
    """

    def _campo(self, protocolo):
        caso = caso_completo()
        caso["eval_result"].docking_protocol = protocolo
        dossier = build_case_dossier(**caso)
        return {c.etiqueta: c for c in dossier.generacion}["Generación conformacional"]

    def test_una_corrida_anterior_no_se_lee_como_conformero_unico(self):
        """`None` es «no se selló», no «se confirmó que fue una sola»."""
        campo = self._campo(None)
        assert campo.estado == Estado.NO_EVALUADO
        assert campo.valor is None
        assert "anterior al sellado" in campo.razon

    def test_conformero_unico_se_declara_como_tal(self):
        campo = self._campo({
            "contract": "docking_protocol/v1",
            "conformers_requested": 1, "conformers_generated": 1,
        })
        assert campo.estado == Estado.REGISTRADO
        assert "Confórmero único" in campo.valor

    def test_un_ensemble_completo_se_declara_con_su_recuento(self):
        campo = self._campo({
            "contract": "docking_protocol/v1",
            "conformers_requested": 30, "conformers_generated": 30,
        })
        assert campo.estado == Estado.REGISTRADO
        assert campo.valor == "Ensemble · 30 de 30 conformaciones"

    def test_un_ensemble_incompleto_exige_revision_y_dice_cuanto_falta(self):
        campo = self._campo({
            "contract": "docking_protocol/v1",
            "conformers_requested": 30, "conformers_generated": 22,
        })
        assert campo.estado == Estado.REVISAR
        assert campo.valor == "Ensemble · 22 de 30 conformaciones"
        assert "menor que la solicitada" in campo.razon
        # Y no promete lo que la medición no dice.
        assert "no mejora" in campo.razon and "top-1" in campo.razon

    def test_el_pdf_imprime_el_protocolo(self):
        caso = caso_completo()
        caso["eval_result"].docking_protocol = {
            "contract": "docking_protocol/v1",
            "conformers_requested": 30, "conformers_generated": 22,
        }
        texto = _texto_pdf(build_case_dossier(**caso))
        assert "Ensemble" in texto
        assert "22 de 30" in texto
