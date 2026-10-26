"""
Los avisos científicos, con su severidad DECLARADA.

# El fallo que arregla

`scientific_warnings` viajaba como una lista de cadenas sueltas, y la pestaña
de alertas decidía el color buscando subcadenas en el texto
(`ProAlertsTab.tsx::getAlertStyle`):

    const isPositive = lower.includes("buen") || lower.includes("seguro")
                    || lower.includes("cumple") || ...;
    if (isPositive) return VERDE;

Dos problemas, y el que de verdad ocurre no es el que parece:

**No es alarma falsa — todavía.** Se pasaron los 184 literales de aviso que
emite hoy el backend por esa misma función: cero falsos verdes. Los ejemplos
del tipo «No cumple la regla de Lipinski» —que contendría «cumple» y saldría en
verde— no existen en el código.

**Es aplanamiento.** 159 de esos 184 (el 86 %) no coinciden con ninguna lista y
caen todos en el mismo azul «NOTA CIENTÍFICA». Entre ellos:

    MOTOR SUSTITUIDO: … La pose NO viene de un modelo de plegamiento
    Afinidad débil en la escala de Vina (…): por encima de -6 el score deja
      de discriminar bien entre unir y no unir
    ⚠️ Metales de transición detectados: …
    La semilla reportada por Vina difiere de la configurada

Un sustituto de motor no declarado, una afinidad fuera del rango en que el
score discrimina y una semilla que no coincide no son notas: son las tres cosas
que más deberían cambiar la lectura de la corrida, y se enseñaban con el mismo
peso visual que «Las afinidades se extrajeron de la tabla de stdout».

Y la segunda mitad sigue siendo cierta aunque hoy no dispare: mientras la
severidad se deduzca de la redacción, **un aviso nuevo puede cambiar de color
al reescribir su frase**. Eso no es un fallo que se arregle una vez.

# La regla

Quien emite el aviso declara su severidad. Nadie la adivina después.

# Compatibilidad

La columna `scientific_warnings` es JSON y ya está en la base: no hace falta
migrar nada. Las corridas antiguas guardaron cadenas y siguen leyéndose; se
normalizan a `severidad="heredada"`, que significa exactamente lo que dice —no
se declaró— y NO se convierte en `info`, porque eso sería volver a inventar el
dato por otra vía.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

#: **Contrato con la interfaz (B-5).** Todos los códigos que el backend emite
#: con `aviso(...)` o como `"codigo"` literal. La interfaz enseña un título
#: traducido por código, porque el `mensaje` es castellano y dinámico. Añadir,
#: renombrar o retirar un código se anuncia antes en el canal entre sesiones
#: (F→B-004). `tests/test_codigos_de_aviso.py` falla si un código emitido falta
#: aquí o si uno de aquí ya no se emite.
CODIGOS_DE_AVISO = frozenset({
    "AFINIDAD_DEBIL",
    # CLAVE-09: la enumeración de microestados llegó al tope de dimorphite.
    "MICROESTADOS_RECORTADOS",
    # El receptor acoplado trae aguas en la caja (camino B o C): no se retiraron.
    "AGUAS_DEL_SITIO_CONSERVADAS",
    "BIGUANIDA_ESTADO_EN_REVISION",
    "CADENAS_LATERALES_TRUNCADAS",
    "CAJA_BUSQUEDA_AMPLIA",
    "COFACTORES_SIN_PLANTILLA_FUERA_DEL_SITIO",
    # Avisos de la subida de un receptor propio (`entrada_receptor`, `conversion_mmcif`, `pdbqt_propio`): se
    # registran en `entrada.avisos` del perfil y en el informe de preparación, con su mensaje en castellano.
    "DECODIFICADO_LATIN1",
    "ESPECIE_ACOPLADA_DISTINTA",
    "ESTEREOQUIMICA_NO_DECLARADA",
    "ESTEREOQUIMICA_PERDIDA_AL_NORMALIZAR",
    "HOTSPOTS_ERROR",
    "LIGANDO_EXCEDE_CAJA",
    "METALES_SIN_MOTOR_ADECUADO",
    "METAL_FEATURES_NO_EVALUADO",
    "MICROESTADO_PKA_NO_VERIFICADO",
    "MICROESTADO_SIN_CRITERIO_QUIMICO",
    "ML_FUERA_DE_DOMINIO",
    "MMCIF_CADENAS_RENOMBRADAS",
    "MMCIF_RESIDUOS_RENOMBRADOS",
    "MMCIF_SERIE_RENUMERADA",
    "MMCIF_VARIOS_MODELOS",
    "MMGBSA_FAILED",
    "MMGBSA_TIMEOUT",
    "MOLECULA_FLEXIBLE",
    "MOLECULA_GRANDE",
    "MOTOR_AD4_XTB",
    "MOTOR_SUSTITUIDO",
    "PDBQT_CADENA_EN_BLANCO",
    "PDBQT_POCOS_ATOMOS",
    "PDBQT_SIN_HIDROGENOS_POLARES",
    "PEPTIDE_REFINEMENT_NO_VALIDADO",
    "PEPTIDO_LINEAL_DETECTADO",
    "PEPTIDO_PLEGADO_Y_ACOPLADO",
    "PEPTIDO_POSES_PARCIALES",
    "PEPTIDO_SIN_ACOPLAMIENTO",
    "QUANTUM_NO_EVALUADO",
    "RECEPTOR_PROTONACION_DECLARADA",
    "RESCORING_SIDECAR",
    "RESIDUOS_ELIMINADOS_FUERA_DEL_SITIO",
    "SA_ALTO",
    "SEMILLA_DISCREPANTE",
    "SIN_CORRECCION_DE_PROTONACION",
    "SIN_HOTSPOTS",
    "SITIO_DESOLVATADO",
})

#: Marcas del normalizador para avisos que no traen código. No se emiten.
CODIGOS_DE_NORMALIZACION = frozenset({"HEREDADO", "SIN_CODIGO"})


class Severidad(str, Enum):
    """Cuánto debería cambiar este aviso la lectura de la corrida."""

    #: Un resultado favorable que merece señalarse.
    POSITIVA = "positiva"
    #: Contexto o procedencia. No cambia lo que se puede concluir.
    INFO = "info"
    #: Cambia lo que se puede concluir, pero la corrida sigue siendo utilizable.
    PRECAUCION = "precaucion"
    #: Invalida o compromete la lectura de la corrida.
    CRITICA = "critica"
    #: Corrida anterior a esta etapa: la severidad no se declaró y no se deduce.
    HEREDADA = "heredada"


@dataclass(frozen=True)
class Aviso:
    """Un aviso científico con identidad estable.

    `codigo` es lo que permite reconocer el mismo aviso entre versiones aunque
    cambie su redacción: es lo que hacía falta y no existía.
    """

    codigo: str
    severidad: Severidad
    mensaje: str

    def a_dict(self) -> dict[str, str]:
        return {
            "codigo": self.codigo,
            "severidad": self.severidad.value,
            "mensaje": self.mensaje,
        }


def aviso(codigo: str, severidad: Severidad, mensaje: str) -> dict[str, str]:
    """Atajo para los sitios de emisión, que sólo necesitan el diccionario."""
    return Aviso(codigo=codigo, severidad=severidad, mensaje=mensaje).a_dict()


_SEVERIDADES = {s.value for s in Severidad}


def normalizar_aviso(valor: Any) -> dict[str, str]:
    """Un aviso —nuevo o heredado— en la forma canónica.

    Acepta la cadena suelta de las corridas antiguas y el diccionario de las
    nuevas. Nunca deduce la severidad del texto.
    """
    if isinstance(valor, dict):
        severidad = str(valor.get("severidad") or "").strip().lower()
        if severidad not in _SEVERIDADES:
            severidad = Severidad.HEREDADA.value
        mensaje = str(valor.get("mensaje") or valor.get("message") or "").strip()
        codigo = str(valor.get("codigo") or valor.get("code") or "").strip() or "SIN_CODIGO"
        return {"codigo": codigo, "severidad": severidad, "mensaje": mensaje}

    # `str(None)` es `"None"`, que se colaba como un aviso con ese texto. Un
    # hueco en la lista es ruido, no un aviso: se convierte en cadena vacía y
    # `normalizar_avisos` lo descarta.
    return {
        "codigo": "HEREDADO",
        "severidad": Severidad.HEREDADA.value,
        "mensaje": "" if valor is None else str(valor).strip(),
    }


def normalizar_avisos(valores: Any) -> list[dict[str, str]]:
    """La lista completa, saneada. Los avisos vacíos se descartan."""
    if not valores:
        return []
    if isinstance(valores, (str, dict)):
        valores = [valores]
    salida = []
    for valor in valores:
        normalizado = normalizar_aviso(valor)
        if normalizado["mensaje"]:
            salida.append(normalizado)
    return salida


def textos(valores: Any) -> list[str]:
    """Sólo los mensajes.

    Lo usan el dossier y el PDF, que llevan los avisos como prosa y no pintan
    colores. Existe para que ningún lector acabe imprimiendo `str(dict)`.
    """
    return [item["mensaje"] for item in normalizar_avisos(valores)]
