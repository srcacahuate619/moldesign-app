"""Localization of dossier display text at export time."""

from __future__ import annotations

from functools import lru_cache
from dataclasses import fields, is_dataclass, replace
from typing import Any

from core.i18n_plantillas import traducir
from services.dossier.model import Artefacto, Campo, CaseDossier, Control, PoseEvidencia

_CAMPOS_DE_TEXTO = frozenset({
    "message", "msg", "detail", "motivo", "observation", "reason", "error",
    "errors", "warning", "warnings", "etiqueta", "razon", "observacion",
    "nota", "titulo", "label", "summary", "limits", "assumptions",
    "uncertainties", "title", "hint", "hints", "reasons", "description",
    "descriptions", "aviso", "rotulo", "note", "interpretation_limit",
    "alcance", "accion_recomendada",
})
_CAMPOS_CON_DATO_DE_PERSONA = frozenset({
    "Caso", "Molécula", "Receptor", "Corrida", "Estado",
    "Tipo de estudio", "¿Qué intenta responder este caso?",
    "¿Qué decisión se pretende tomar?", "¿Qué justifica la elección del sistema?",
    "¿Qué controles o referencias existen?",
    "Notas del caso (contexto libre; no entra en ningún cálculo)",
    # «Origen del receptor» no está: es uno de cinco valores del sistema (curado,
    # privado, comunidad, subido, desconocido), y en inglés salía «curado».
    "Ligando introducido",
    "Ligando canónico (el que se acopla)", "Residuos de referencia",
})
#: Los orígenes del receptor que escribe el caso (RECEPTOR_ORIGINS en
#: `frontend/lib/cases/types.ts`). Son valores del sistema y se traducen.
ORIGENES_DEL_RECEPTOR = ("curado", "privado", "comunidad", "subido", "desconocido")
_CAMPOS_DE_IDENTIDAD = frozenset({
    "name", "source_name", "molecule_name", "case_name", "cohort_name",
    "target_label", "receptor_name", "smiles", "canonical_smiles", "input_smiles",
    "source_filename", "filename", "path", "ruta", "case_id", "molecule_id",
    "task_id", "run_id", "result_id", "id", "pdb_id", "chain", "sha256",
    "fingerprint", "contract", "status", "code", "reason_code", "error_code",
    "control_role", "active_label",
})
_LISTAS_DE_TEXTO_DEL_MODELO = frozenset({"supuestos", "incertidumbres", "avisos_integridad"})


def _texto(valor: Any, idioma: str) -> Any:
    return traducir(valor, idioma) if isinstance(valor, str) else valor


@lru_cache(maxsize=1)
def _campos_de_persona_en() -> frozenset[str]:
    """Las mismas etiquetas ya traducidas.

    El modelo puede localizarse más de una vez (la vista del PDF parte de una ya traducida): tras la primera pasada
    «Caso» es «Case», que no está en el conjunto español, y el nombre que escribió la persona —«2 elegidos de 8 del
    catálogo: …»— se traducía como si fuera texto del sistema.
    """
    return frozenset(traducir(etiqueta, "en") for etiqueta in _CAMPOS_CON_DATO_DE_PERSONA)


def _valor_de_campo(valor: Any, etiqueta: str, idioma: str, *, es_clasificacion: bool) -> Any:
    """Translate fixed explanatory values while preserving case and input data."""
    if not es_clasificacion and (etiqueta in _CAMPOS_CON_DATO_DE_PERSONA or etiqueta in _campos_de_persona_en()):
        return valor
    if es_clasificacion or isinstance(valor, str):
        if isinstance(valor, str) and etiqueta == "Huecos del esqueleto" and idioma == "en":
            return _localizar_huecos(valor)
        if (
            isinstance(valor, str)
            and etiqueta in ("Archivo del receptor", "Confianza de la estructura (pLDDT)")
            and idioma == "en"
        ):
            return _localizar_entrada_del_receptor(valor)
        return _contenido_de_texto(valor, idioma)
    return valor


def _localizar_entrada_del_receptor(texto: str) -> str:
    """«pdbqt · modo: <etiqueta> · SHA-256 …»: se traduce la etiqueta del modo y se copia el resto."""
    partes = []
    for parte in texto.split(" · "):
        if parte.startswith("unidad asimétrica: "):
            parte = "asymmetric unit: " + traducir(parte[len("unidad asimétrica: "):], "en")
        else:
            parte = traducir(parte, "en")
        partes.append(parte)
    return " · ".join(partes)


def _localizar_huecos(texto: str) -> str:
    """Localiza cada corte completo, conservando cadena/residuos/distancias."""
    translated = traducir(texto, "en")
    _, separator, gaps = texto.partition(": ")
    if separator and gaps and translated.endswith(gaps):
        return translated[:-len(gaps)] + ", ".join(traducir(gap, "en") for gap in gaps.split(", "))
    return translated


def _contenido_de_texto(valor: Any, idioma: str) -> Any:
    if isinstance(valor, str):
        return _texto(valor, idioma)
    if isinstance(valor, list):
        return [_contenido_de_texto(item, idioma) for item in valor]
    if isinstance(valor, dict):
        return _diccionario(valor, idioma)
    return _visitar(valor, idioma)


def _diccionario(valor: dict[str, Any], idioma: str) -> dict[str, Any]:
    resultado: dict[str, Any] = {}
    for clave, contenido in valor.items():
        if clave in _CAMPOS_DE_IDENTIDAD:
            resultado[clave] = contenido
        elif clave == "valor" and "etiqueta" in valor and "estado" in valor:
            resultado[clave] = _valor_de_campo(
                contenido,
                str(valor.get("etiqueta") or ""),
                idioma,
                es_clasificacion=valor.get("valor_es_clasificacion") is True,
            )
        elif clave == "glosario" and isinstance(contenido, dict):
            resultado[clave] = {
                estado: _contenido_de_texto(texto, idioma)
                for estado, texto in contenido.items()
            }
        elif clave == "valor" and valor.get("valor_es_clasificacion") is True:
            resultado[clave] = _contenido_de_texto(contenido, idioma)
        elif clave == "fuente" and "clave" in valor and "imprescindible" in valor:
            # La fuente de un requisito de Preparación: un campo del código o una descripción del sistema. Sólo aquí:
            # en otros diccionarios «fuente» puede ser lo que declaró el caso (la fuente de un Ki) y no se toca.
            resultado[clave] = _texto(contenido, idioma)
        elif clave in _CAMPOS_DE_TEXTO:
            resultado[clave] = _contenido_de_texto(contenido, idioma)
        else:
            resultado[clave] = _visitar(contenido, idioma)
    return resultado


def _visitar(valor: Any, idioma: str) -> Any:
    if isinstance(valor, Campo):
        return replace(
            valor,
            etiqueta=_texto(valor.etiqueta, idioma),
            valor=_valor_de_campo(
                valor.valor,
                valor.etiqueta,
                idioma,
                es_clasificacion=valor.valor_es_clasificacion,
            ),
            razon=_texto(valor.razon, idioma),
        )
    if isinstance(valor, Control):
        return replace(
            valor,
            titulo=_texto(valor.titulo, idioma),
            observacion=_texto(valor.observacion, idioma),
            protocolo=_texto(valor.protocolo, idioma),
        )
    if isinstance(valor, PoseEvidencia):
        return replace(
            valor,
            detalle=_texto(valor.detalle, idioma),
            razon=_texto(valor.razon, idioma),
        )
    if isinstance(valor, Artefacto):
        return replace(valor, razon=_texto(valor.razon, idioma))
    if isinstance(valor, CaseDossier):
        cambios: dict[str, Any] = {}
        for campo in fields(valor):
            actual = getattr(valor, campo.name)
            if campo.name in _LISTAS_DE_TEXTO_DEL_MODELO and isinstance(actual, list):
                cambios[campo.name] = [_contenido_de_texto(item, idioma) for item in actual]
            elif campo.name == "poses_razon":
                # El único texto del sistema que el modelo guarda como cadena suelta (el resto son Campo, Control…): sin esto, un caso sin
                # poses —el de una corrida fallida— salía en inglés con «NOT AVAILABLE — La corrida no serializó poses…».
                cambios[campo.name] = _texto(actual, idioma)
            else:
                cambios[campo.name] = _visitar(actual, idioma)
        return replace(valor, **cambios)
    if isinstance(valor, dict):
        return _diccionario(valor, idioma)
    if isinstance(valor, list):
        return [_visitar(item, idioma) for item in valor]
    if isinstance(valor, tuple):
        return tuple(_visitar(item, idioma) for item in valor)
    if is_dataclass(valor) and not isinstance(valor, type):
        return valor
    return valor


def traducir_dossier(dossier: Any, idioma: str) -> Any:
    """Return a localized export view while preserving stored evidence and identifiers."""
    if not isinstance(idioma, str) or idioma.lower().split("-", 1)[0] != "en":
        return dossier
    return _visitar(dossier, idioma)


def dossier_dict_localizado(dossier: CaseDossier, idioma: str) -> dict[str, Any]:
    """Serialize the export view, including taxonomy text derived by `as_dict`."""
    vista = traducir_dossier(dossier, idioma)
    resultado = vista.as_dict()
    if isinstance(idioma, str) and idioma.lower().split("-", 1)[0] == "en":
        resultado["glosario"] = {
            estado: _texto(texto, idioma)
            for estado, texto in resultado["glosario"].items()
        }
    return resultado
