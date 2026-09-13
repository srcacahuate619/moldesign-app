"""
Vocabulario de estados del dossier.

# Por qué una taxonomía cerrada

Un dossier existe para que un tercero pueda distinguir **lo que se midió** de
**lo que no se miró**. En cuanto esa frontera se difumina, el documento deja de
ser evidencia y pasa a ser una opinión con tipografía.

El modo de fallo concreto que estos estados impiden: convertir un `None`, un
campo ausente o un error de lectura en «pasa». Es el error más barato de
cometer —basta un `if not warnings:`— y el más caro de descubrir, porque
produce un documento que afirma haber comprobado algo que nadie comprobó.

# Los seis estados de ausencia o reserva

    NO_DEFINIDO    el usuario no declaró ese contexto
    NO_EVALUADO    el control no se ejecutó
    NO_DISPONIBLE  el resultado o artefacto esperado no está
    NO_APLICA      el control no corresponde a este caso
    REVISAR        hay evidencia, pero no autoriza una conclusión
    ABSTENCION     falta evidencia indispensable, o hay un bloqueo declarado

Y dos afirmativos, que sólo se emiten con un dato detrás:

    REGISTRADO     el dato existe y está serializado
    PASA           el control se ejecutó y lo superó

`PASA` es el único estado que afirma algo sobre el mundo. Por eso no tiene
constructor por defecto en ninguna parte de este paquete: hay que pedirlo
explícitamente, con la observación que lo sostiene.
"""

from __future__ import annotations

from enum import Enum


class Estado(str, Enum):
    """Estado de un campo o control del dossier. Serializa como su valor."""

    NO_DEFINIDO = "NO_DEFINIDO"
    NO_EVALUADO = "NO_EVALUADO"
    NO_DISPONIBLE = "NO_DISPONIBLE"
    NO_APLICA = "NO_APLICA"
    REVISAR = "REVISAR"
    ABSTENCION = "ABSTENCION"
    REGISTRADO = "REGISTRADO"
    PASA = "PASA"

    @property
    def es_afirmativo(self) -> bool:
        """`True` sólo si el estado afirma que algo se comprobó o se registró."""
        return self in (Estado.REGISTRADO, Estado.PASA)

    @property
    def es_ausencia(self) -> bool:
        """`True` si el estado declara que NO hay dato con el que concluir."""
        return self in (
            Estado.NO_DEFINIDO,
            Estado.NO_EVALUADO,
            Estado.NO_DISPONIBLE,
            Estado.NO_APLICA,
        )


#: Texto que se imprime en el PDF para cada estado. Se mantiene aquí y no en el
#: renderizador para que el PDF, el manifiesto y el README digan exactamente lo
#: mismo — tres interpretaciones del mismo estado es justo lo que este paquete
#: existe para evitar.
ETIQUETA: dict[Estado, str] = {
    Estado.NO_DEFINIDO: "NO DEFINIDO",
    Estado.NO_EVALUADO: "NO EVALUADO",
    Estado.NO_DISPONIBLE: "NO DISPONIBLE",
    Estado.NO_APLICA: "NO APLICA",
    Estado.REVISAR: "REVISAR",
    Estado.ABSTENCION: "ABSTENCIÓN",
    Estado.REGISTRADO: "REGISTRADO",
    Estado.PASA: "PASA",
}

#: Qué significa cada estado, en una frase. Se imprime en la leyenda del PDF y
#: en el README del paquete: un lector externo no tiene por qué conocer el
#: vocabulario interno del producto.
GLOSARIO: dict[Estado, str] = {
    Estado.NO_DEFINIDO: "El caso no declaró este contexto.",
    Estado.NO_EVALUADO: "El control no se ejecutó en esta corrida.",
    Estado.NO_DISPONIBLE: "El resultado o artefacto esperado no está disponible.",
    Estado.NO_APLICA: "El control no corresponde a este caso.",
    Estado.REVISAR: "Hay evidencia, pero no autoriza una conclusión por sí sola.",
    Estado.ABSTENCION: "Falta evidencia indispensable o existe un bloqueo declarado.",
    Estado.REGISTRADO: "El dato existe y quedó serializado por la corrida.",
    Estado.PASA: "El control se ejecutó y lo superó.",
}


def estado_de_texto(valor: str | None) -> Estado:
    """
    Convierte un texto libre del usuario en `REGISTRADO` o `NO_DEFINIDO`.

    Una cadena en blanco es ausencia, no contenido: si se dejara pasar, el
    dossier imprimiría un apartado vacío como si estuviera respondido.
    """
    if valor is None:
        return Estado.NO_DEFINIDO
    return Estado.REGISTRADO if valor.strip() else Estado.NO_DEFINIDO


def estado_de_valor(valor: object) -> Estado:
    """
    Estado de un dato que la corrida debía serializar.

    `None` es `NO_DISPONIBLE` —se esperaba y no está—, nunca un afirmativo.
    Para el contexto que el usuario podía dejar en blanco, usa
    `estado_de_texto`: la ausencia significa otra cosa.
    """
    if valor is None:
        return Estado.NO_DISPONIBLE
    if isinstance(valor, str) and not valor.strip():
        return Estado.NO_DISPONIBLE
    if isinstance(valor, (list, tuple, dict)) and len(valor) == 0:
        return Estado.NO_DISPONIBLE
    return Estado.REGISTRADO
