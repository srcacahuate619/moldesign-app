"""
Códigos estables de la comprobación previa de cohortes.

# Por qué códigos y no frases

La interfaz, el dossier de cohorte (5C) y cualquier análisis posterior van a
tener que **decidir** sobre estos valores: agrupar filas por causa, contar
excepciones, filtrar. Si la lógica dependiera del texto en castellano, cambiar
una tilde rompería un recuento, y traducir el producto lo rompería entero.

Aquí vive el identificador; el texto explicativo vive en la interfaz y en
`docs/57_COHORT_PREFLIGHT_V1.md`. El código es el contrato, la frase no.

# Regla de compatibilidad

Un código **no se renombra ni se reutiliza**. Añadir uno nuevo es aditivo;
cambiar el significado de uno existente rompe en silencio a quien ya contaba
con él. Si un código deja de emitirse, se documenta como retirado y su nombre
queda quemado.
"""

from __future__ import annotations

from typing import Final, Literal

# ── Estado de una fila ───────────────────────────────────────────────
#
# DOS estados y sólo dos. `eligible` no significa «buena molécula»: significa
# que la fila puede entrar en la corrida común de la cohorte. La calidad
# farmacológica no se afirma aquí —ni aquí ni después del docking.

Eligibility = Literal["eligible", "invalid_input"]

ELIGIBLE: Final = "eligible"
INVALID_INPUT: Final = "invalid_input"


# ── Papel de control declarado ───────────────────────────────────────
#
# EXPLÍCITO SIEMPRE. No se infiere de nombres («ref», «control_1»), ni de
# afinidades, ni de la posición en el archivo. Un control inferido es una
# afirmación que nadie hizo, y el día que se calcule enriquecimiento sería la
# afirmación que decide si la cohorte «funcionó».

ControlRole = Literal["reference", "positive", "negative", "none"]

CONTROL_ROLES: Final[frozenset[str]] = frozenset({"reference", "positive", "negative", "none"})

ROLE_NONE: Final = "none"


# ── Razones por las que una fila NO es elegible ──────────────────────

#: La celda de SMILES está vacía o la fila entera lo está.
SMILES_AUSENTE: Final = "SMILES_AUSENTE"

#: RDKit no puede leer la estructura. Es un fallo de LECTURA, no de calidad.
SMILES_ILEGIBLE: Final = "SMILES_ILEGIBLE"

#: La estructura se lee, pero el validador del producto la rechaza para
#: evaluación (política química vigente: átomos pesados mínimos, etc.). Se
#: separa de `SMILES_ILEGIBLE` a propósito: «no te entiendo» y «te entiendo y
#: este producto no te evalúa» son diagnósticos distintos y se actúa distinto.
SMILES_NO_ADMISIBLE: Final = "SMILES_NO_ADMISIBLE"

#: El registro del archivo no se pudo interpretar como una molécula (p. ej. un
#: bloque SDF corrupto). Se conserva la fila para que el recuento no mienta.
REGISTRO_ILEGIBLE: Final = "REGISTRO_ILEGIBLE"

ROW_REASONS: Final[frozenset[str]] = frozenset(
    {SMILES_AUSENTE, SMILES_ILEGIBLE, SMILES_NO_ADMISIBLE, REGISTRO_ILEGIBLE}
)


# ── Avisos de fila ───────────────────────────────────────────────────
#
# Un aviso NO invalida la fila ni bloquea la cohorte. Declara algo que el
# lector tiene que saber para interpretar el resultado.

#: Otra fila anterior tiene el mismo SMILES canónico. `duplicate_of_row` dice
#: cuál. NO se excluye: si se excluyera aquí, el recuento de la cohorte dejaría
#: de corresponder al archivo que la persona subió.
SMILES_DUPLICADO: Final = "SMILES_DUPLICADO"

#: Había una celda `active` y no se pudo interpretar como etiqueta binaria. La
#: etiqueta queda ausente; la fila sigue siendo evaluable.
ETIQUETA_ACTIVE_INVALIDA: Final = "ETIQUETA_ACTIVE_INVALIDA"

#: Había una celda `control_role` con un valor fuera del vocabulario. El papel
#: queda en `none`: inventar el que «parecía» sería inferir un control.
ROL_CONTROL_INVALIDO: Final = "ROL_CONTROL_INVALIDO"

#: La fila tiene menos o más celdas que la cabecera.
FILA_COLUMNAS_INCONSISTENTES: Final = "FILA_COLUMNAS_INCONSISTENTES"

#: El validador del producto aceptó la molécula pero dejó avisos químicos.
MOLECULA_CON_AVISOS_QUIMICOS: Final = "MOLECULA_CON_AVISOS_QUIMICOS"

#: La fila no declara nombre. No se fabrica uno a partir del SMILES.
NOMBRE_AUSENTE: Final = "NOMBRE_AUSENTE"

ROW_WARNINGS: Final[frozenset[str]] = frozenset(
    {
        SMILES_DUPLICADO,
        ETIQUETA_ACTIVE_INVALIDA,
        ROL_CONTROL_INVALIDO,
        FILA_COLUMNAS_INCONSISTENTES,
        MOLECULA_CON_AVISOS_QUIMICOS,
        NOMBRE_AUSENTE,
    }
)


# ── Bloqueantes de la cohorte ────────────────────────────────────────
#
# Un bloqueante dice que la cohorte NO se puede ejecutar tal como está. No es
# una opinión sobre la ciencia: es un hecho verificable sobre la entrada.

#: El archivo no se pudo decodificar o su contenido no se pudo recorrer.
ARCHIVO_ILEGIBLE: Final = "ARCHIVO_ILEGIBLE"

#: La extensión no corresponde a ningún formato que la ingesta sepa leer.
FORMATO_NO_SOPORTADO: Final = "FORMATO_NO_SOPORTADO"

#: El archivo no declara ninguna columna de estructura.
COLUMNA_SMILES_AUSENTE: Final = "COLUMNA_SMILES_AUSENTE"

#: El archivo no contiene ninguna fila de datos.
COHORTE_VACIA: Final = "COHORTE_VACIA"

#: Hay filas, pero ninguna puede entrar en la corrida. Ejecutar produciría una
#: cohorte de cero moléculas presentada como si fuera un cribado.
SIN_MOLECULAS_ELEGIBLES: Final = "SIN_MOLECULAS_ELEGIBLES"

#: El runtime no trae el lector que ese formato necesita (openpyxl para Excel,
#: RDKit para SDF). NO es `ARCHIVO_ILEGIBLE`: el archivo puede estar
#: perfectamente, y decir que está corrupto mandaría a la persona a rehacer un
#: archivo que no tiene nada malo.
LECTOR_NO_DISPONIBLE: Final = "LECTOR_NO_DISPONIBLE"

#: RDKit no está disponible en este runtime. NO se marca cada molécula como
#: ilegible: eso sería culpar a la entrada de una carencia del entorno.
VALIDADOR_NO_DISPONIBLE: Final = "VALIDADOR_NO_DISPONIBLE"

COHORT_BLOCKERS: Final[frozenset[str]] = frozenset(
    {
        ARCHIVO_ILEGIBLE,
        FORMATO_NO_SOPORTADO,
        COLUMNA_SMILES_AUSENTE,
        COHORTE_VACIA,
        SIN_MOLECULAS_ELEGIBLES,
        LECTOR_NO_DISPONIBLE,
        VALIDADOR_NO_DISPONIBLE,
    }
)


# ── Avisos de la cohorte ─────────────────────────────────────────────
#
# NINGUNO bloquea. Un aviso que bloqueara sería un bloqueante mal nombrado.

#: Ninguna fila declara papel de control. La cohorte se puede ejecutar; lo que
#: no se podrá es interpretar su resultado contra una referencia.
SIN_CONTROLES_DECLARADOS: Final = "SIN_CONTROLES_DECLARADOS"

#: Ninguna fila declara etiqueta `active`. No bloquea: una cohorte prospectiva
#: no tiene por qué conocer la respuesta.
SIN_ETIQUETAS_ACTIVE: Final = "SIN_ETIQUETAS_ACTIVE"

#: Hay SMILES repetidos canónicamente. Se declaran, no se ocultan; qué hacer
#: con ellos en las métricas se decide en 5B, no aquí.
DUPLICADOS_CANONICOS: Final = "DUPLICADOS_CANONICOS"

#: Hay filas que no entran en la corrida. La cobertura lo cuantifica.
FILAS_INVALIDAS: Final = "FILAS_INVALIDAS"

#: La configuración no declara caja. En ejecución se derivará del receptor, y
#: hasta que eso ocurra no se puede afirmar qué región se va a explorar.
CAJA_NO_DECLARADA: Final = "CAJA_NO_DECLARADA"

#: La configuración no fija semilla. Dos corridas de la misma cohorte podrán
#: diferir dentro del ruido estocástico del motor.
SEMILLA_NO_DECLARADA: Final = "SEMILLA_NO_DECLARADA"

COHORT_WARNINGS: Final[frozenset[str]] = frozenset(
    {
        SIN_CONTROLES_DECLARADOS,
        SIN_ETIQUETAS_ACTIVE,
        DUPLICADOS_CANONICOS,
        FILAS_INVALIDAS,
        CAJA_NO_DECLARADA,
        SEMILLA_NO_DECLARADA,
    }
)


# ── Decisión ─────────────────────────────────────────────────────────

Decision = Literal["ready", "blocked"]

READY: Final = "ready"
BLOCKED: Final = "blocked"


def decide(blockers: list[str]) -> Decision:
    """
    `ready` si no hay bloqueantes. Los avisos NO deciden.

    Está aquí, en una función de una línea, para que exista UN sitio donde se
    toma la decisión. Repetir `if blockers` en tres módulos es cómo un aviso
    acaba bloqueando en uno de ellos.
    """
    return BLOCKED if blockers else READY
