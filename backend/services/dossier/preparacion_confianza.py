"""La confianza de una estructura predicha, en las frases que Preparación imprime.

Para un receptor propio ``receptor_prep.prediccion`` dice si el archivo es una predicción, con qué convención se leyó
su pLDDT y cómo es el sitio de unión. Preparación lo traduce a un requisito que **pide revisión y no bloquea**: un
pLDDT bajo junto al sitio es una decisión científica abierta, no evidencia que falte.

Estados:

* ``NO_APLICA`` — el archivo no tiene indicios de ser una predicción (el método declarado, si lo hay, se imprime);
* ``REGISTRADO`` — predicción con el pLDDT leído y ningún residuo del sitio por debajo de 70;
* ``REVISAR`` — predicción con residuos del sitio por debajo de 70 (se listan);
* ``NO_DISPONIBLE`` — no se puede saber o no se puede leer, con el motivo (formato sin factor B, convención sin
  verificar, escala ambigua, un archivo que no dice de dónde viene y del que no consta la fuente…). Nunca se
  rellena con un supuesto.

Cuando el archivo no dice de dónde viene, lo que declaró quien lo subió se nombra como declaración suya («fuente
declarada por quien subió el archivo»), para que quien reciba el dossier no lo confunda con algo detectado.

Los textos son frases fijas y los datos (residuos, valores) se copian sin traducir: ``core/i18n_receptores_propios.py``
lleva cada frase al inglés.
"""

from __future__ import annotations

from typing import Any

from services.dossier.model import Campo
from services.dossier.taxonomy import Estado
from services.targets import prediccion as P

ETIQUETA = "Confianza de la estructura (pLDDT)"
SEPARADOR = " · "

_RAZONES = {
    P.SIN_PLDDT_DECLARADO: (
        "El archivo es un modelo predicho (ModelCIF) pero no declara el pLDDT por residuo: no se lee la confianza "
        "del sitio."
    ),
    P.CONVENCION_SIN_VERIFICAR: (
        "El archivo se declara un modelo (método teórico), pero no es de AlphaFold DB ni declara el pLDDT en "
        "_ma_qa_metric_local (ModelCIF). Sólo en AlphaFold DB está verificado que el factor B sea el pLDDT; en otro "
        "archivo podría ser otra cosa, así que no se lee."
    ),
    P.ESCALA_AMBIGUA: (
        "Todos los valores de pLDDT del archivo son ≤ 1: podrían estar en escala 0–1 o ser una confianza ínfima. No "
        "se interpreta sin verificar la convención de esa fuente."
    ),
    P.B_NO_COINCIDE: (
        "El factor B del archivo no coincide con el pLDDT que declara _ma_qa_metric_local: no se sabe cuál es el "
        "correcto y no se usa ninguno."
    ),
    P.FORMATO_SIN_FACTOR_B: (
        "Un PQR no conserva el factor B ni el método del archivo original: no se puede saber si la estructura es una "
        "predicción ni leer su confianza."
    ),
    P.PDBQT_SIN_ORIGEN: (
        "Un PDBQT no conserva el factor B ni el método: sin la estructura de origen no se puede saber si es una "
        "predicción ni leer su confianza."
    ),
    P.FUENTE_SIN_DECLARAR: (
        "El archivo no declara su método ni trae marcas de predicción, y no consta de dónde viene: no se sabe si es "
        "experimental o una predicción. Si es una predicción, su confianza (pLDDT) no se lee; para leerla, vuelve a "
        "subirlo indicando qué herramienta lo generó."
    ),
    P.HERRAMIENTA_SIN_VERIFICAR: (
        "Quien subió el archivo declaró que es una predicción, pero MolDesign no ha comprobado con un archivo real "
        "dónde guarda esa herramienta el pLDDT: su factor B podría ser otra cosa, así que no se lee. Están "
        "comprobadas AlphaFold DB y Boltz 2.2.1."
    ),
    P.DECLARACION_NO_COINCIDE: (
        "Quien subió el archivo declaró que es de Boltz-2, pero no es como los PDB que escribe Boltz 2.2.1 (el mismo "
        "pLDDT, entre 0 y 100, en todos los átomos de cada residuo). No se sabe qué guarda su factor B, así que no se "
        "lee."
    ),
}
#: El motivo cuando quien subió el archivo nombró la herramienta (``otra``). Va en el motivo y no en el valor, porque un
#: campo «no disponible» no enseña valor (``Campo.as_dict``). El nombre se copia sin traducir.
RAZON_HERRAMIENTA = (
    "Quien subió el archivo declaró que es una predicción de {herramienta}, pero MolDesign no ha comprobado con un "
    "archivo real dónde guarda esa herramienta el pLDDT: su factor B podría ser otra cosa, así que no se lee. Están "
    "comprobadas AlphaFold DB y Boltz 2.2.1."
)
NO_APLICA_DECLARADA = (
    "Sin indicios de estructura predicha: el archivo no declara método y quien lo subió declaró que es experimental."
)

ACCION_REVISAR = (
    "Confirma la cavidad con una estructura experimental del mismo receptor, o decide con tu criterio si el modelo "
    "basta para el sitio. Preparación no bloquea por esto."
)

_FUENTES = {
    "alphafold_db": "estructura predicha por AlphaFold DB",
    "modelcif": "estructura predicha (ModelCIF)",
    P.FUENTE_BOLTZ: "estructura predicha por Boltz-2 (fuente declarada por quien subió el archivo)",
    P.FUENTE_ARCHIVO_CHAI1: "estructura predicha por Chai-1 (declarado por el archivo en _struct.title)",
}
#: Cuando la fuente tiene su propia convención comprobada, se dice cuál; las demás usan ``_LEIDO``.
_LEIDO_POR_FUENTE = {
    P.FUENTE_BOLTZ: "pLDDT leído del factor B (convención comprobada con un archivo real de Boltz 2.2.1)",
}
#: Lo que se comprobó en el propio archivo. Con la firma de Chai-1 y el valor local igual al factor B del Cα en cada
#: residuo, se dice que es el Cα; con la firma sola, no (el texto genérico de ``_LEIDO`` lo deja sin verificar).
_LEIDO_POR_LECTURA = {
    "calfa": (
        "pLDDT leído de _ma_qa_metric_local; los valores leídos coinciden con el factor B de los Cα correspondientes. "
        "El archivo declara Chai-1 y no acredita su versión"
    ),
}
#: El texto que escribieron las corridas anteriores a la revisión final de 1.0.4. Decía «que no es la media del residuo»,
#: y un factor B que varía dentro del residuo no lo demuestra: valores por encima y por debajo pueden compensarse y dar
#: la misma media (contraejemplo de 90 residuos, `docs/auditorias/revision-final-1.0.4/comprobar_d01.py`). Los dossiers
#: ya escritos no se reescriben: el texto se conserva entero para que siga traduciéndose.
TEXTO_ANTERIOR_DE_LECTURA_CALFA = (
    "pLDDT leído de _ma_qa_metric_local: en este archivo coincide con el factor B del Cα de cada residuo, que no "
    "es la media del residuo que da el modelo (así lo escribe Chai-1 0.6.1; el archivo no declara su versión)"
)
#: Cómo se leyó el pLDDT, según dónde estaba y si la convención de esa fuente está verificada. Frases enteras, para
#: que cada una tenga su inglés exacto (`core/i18n_receptores_propios.py`).
_LEIDO = {
    ("factor_b", True): "pLDDT leído del factor B (convención verificada con un archivo real de AlphaFold DB)",
    ("ma_qa_metric_local", True):
        "pLDDT leído de _ma_qa_metric_local (convención verificada con un archivo real de AlphaFold DB)",
    ("ma_qa_metric_local", False):
        "pLDDT leído de _ma_qa_metric_local (declarado por el archivo; convención de esta fuente sin verificar "
        "con un archivo real)",
}
_LEIDO_SIN_CONVENCION = "pLDDT leído del archivo (convención sin verificar con un archivo real)"


def _numero(valor: Any) -> str:
    return f"{float(valor):g}"


def _partes(prediccion: dict[str, Any]) -> list[str]:
    fuente = prediccion.get("fuente") or ""
    partes = [_FUENTES.get(fuente, "estructura predicha")]
    convencion = prediccion.get("convencion") or {}
    partes.append(
        _LEIDO_POR_LECTURA.get(convencion.get("lectura") or "")
        or _LEIDO_POR_FUENTE.get(fuente)
        or _LEIDO.get((convencion.get("plddt_en"), bool(convencion.get("verificada"))), _LEIDO_SIN_CONVENCION))
    plddt = prediccion.get("plddt") or {}
    if plddt:
        partes.append(f"pLDDT medio {_numero(plddt['media'])} en {plddt['residuos']} residuos "
                      f"({plddt['bajo_70']} por debajo de 70)")
    sitio = prediccion.get("sitio")
    if sitio is None:
        partes.append("el pLDDT del sitio no se midió")
    elif not sitio["con_plddt"]:
        partes.append(f"sin residuos con pLDDT a {_numero(sitio['margen_A'])} Å o menos de la caja")
    else:
        partes.append(f"sitio (a {_numero(sitio['margen_A'])} Å o menos de la caja): {sitio['con_plddt']} residuos, "
                      f"pLDDT mínimo {_numero(sitio['minimo'])}, medio {_numero(sitio['media'])}")
        if sitio["n_bajo_70"]:
            listado = ", ".join(f"{r['residuo']} {r['nombre']} ({_numero(r['plddt'])})" for r in sitio["bajo_70"])
            resto = sitio["n_bajo_70"] - len(sitio["bajo_70"])
            partes.append(f"{len(sitio['bajo_70'])} por debajo de 70: {listado}")
            if resto > 0:
                partes.append(f"otros {resto} por debajo de 70 sin listar")
        if sitio["sin_plddt"]:
            partes.append(f"{sitio['sin_plddt']} residuos del sitio sin pLDDT")
    return partes


def campo_de_confianza(prediccion: dict[str, Any]) -> tuple[Campo, str | None]:
    """El campo de Preparación y, si pide revisión, la acción recomendada."""
    codigo = prediccion.get("no_disponible")
    declaracion = prediccion.get("declaracion") or {}
    usada = declaracion if declaracion.get("usada") else {}
    if codigo:
        herramienta = usada.get("herramienta")
        razon = (RAZON_HERRAMIENTA.format(herramienta=herramienta)
                 if codigo == P.HERRAMIENTA_SIN_VERIFICAR and herramienta else _RAZONES.get(codigo, codigo))
        return Campo(ETIQUETA, None, Estado.NO_DISPONIBLE, razon), None
    if not prediccion.get("es_predicha"):
        metodo = prediccion.get("metodo_declarado")
        if usada.get("fuente") == P.FUENTE_EXPERIMENTAL:
            return Campo(ETIQUETA, None, Estado.NO_APLICA, NO_APLICA_DECLARADA), None
        return Campo(
            ETIQUETA, None, Estado.NO_APLICA,
            "Sin indicios de estructura predicha en el archivo"
            + (f" (método declarado: {metodo})." if metodo else " (no declara método)."),
        ), None
    sitio = prediccion.get("sitio")
    if sitio is None:
        return Campo(ETIQUETA, SEPARADOR.join(_partes(prediccion)), Estado.NO_EVALUADO,
                     "La corrida no midió el pLDDT de los residuos junto al sitio.",
                     valor_es_clasificacion=True), None
    if not sitio["con_plddt"]:
        return Campo(ETIQUETA, SEPARADOR.join(_partes(prediccion)), Estado.NO_DISPONIBLE,
                     "Ningún residuo con pLDDT junto a la caja: no se puede juzgar la confianza del sitio.",
                     valor_es_clasificacion=True), None
    bajo = sitio["n_bajo_70"] > 0
    return Campo(
        ETIQUETA, SEPARADOR.join(_partes(prediccion)),
        Estado.REVISAR if bajo else Estado.REGISTRADO,
        ("Hay residuos junto al sitio con pLDDT por debajo de 70: su posición es una conjetura del modelo y la "
         "cavidad acoplada podría no ser así. No bloquea: es una decisión científica abierta.") if bajo else None,
        valor_es_clasificacion=bajo,
    ), (ACCION_REVISAR if bajo else None)
