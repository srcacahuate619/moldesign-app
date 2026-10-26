"""Texto de contexto fisiológico para los certificados de MolDesign.

Este módulo no interpreta resultados ni modifica la evaluación.

SCI-A-020, 043, 046, 047 y 048. Aquí vivía una clasificación por subcadenas sobre
el PDB **entero** —encabezado, REMARKs y condiciones de cristalización—, y cada
regla acertaba por casualidad o fallaba con naturalidad:

* «RECEPTOR» llamaba GPCR o transmembranal a un receptor nuclear (3ERT);
* «KINASE» en ``COMPND FRAGMENT: KINASE DOMAIN`` llamaba quinasa a BACE1, una
  aspartil proteasa (5TOL);
* «MPRO» dentro de ``REMARK 3 IMPROPER ANGLES`` llamaba proteasa a la anhidrasa
  carbónica II (1BN1);
* «POTASSIUM» en ``REMARK 280 POTASSIUM CHLORIDE`` llamaba canal iónico a la
  transcriptasa inversa de la telomerasa (6E53);
* y lo que no casaba con nada se describía como «catalizador o transductor de
  señal intracelular» (1SM3, un anticuerpo con su epítopo).

Una función biológica no se deduce de una palabra del archivo. Sin una anotación
funcional curada (la descripción del catálogo, que el PDF prefiere cuando existe)
se dice que el contexto no está disponible, y lo que el depósito sí declara —su
clasificación y su título— se conserva como dato, sin convertirlo en función.
"""

from __future__ import annotations

#: Lo más largo que se copia del título del depósito: es un dato, no un párrafo.
MAX_TITULO = 160

SIN_CONTEXTO = (
    "Contexto fisiológico no disponible: el receptor no tiene una anotación funcional curada."
)


def _registro(texto: str, nombre: str) -> str | None:
    """El contenido de un registro PDB (HEADER, TITLE…), uniendo sus continuaciones."""
    partes = []
    for linea in texto.splitlines():
        if linea[:6].rstrip() != nombre:
            continue
        if nombre == "HEADER":
            # Columnas 11-50: la clasificación. Lo que sigue es la fecha y el código.
            partes.append(linea[10:50].strip())
        else:
            partes.append(linea[10:80].strip())
    contenido = " ".join(p for p in partes if p).strip()
    return contenido or None


def generate_physiological_context(pdb_id: str, header_lines: str | None) -> str:
    """El contexto fisiológico que se puede afirmar sin anotación curada: ninguno.

    ``pdb_id`` se conserva en el contrato público porque los certificados lo
    proporcionan. ``header_lines`` puede ser el PDB entero: sólo se leen sus
    registros HEADER y TITLE, nunca los REMARK ni las condiciones de cristalización.
    """
    del pdb_id
    if not header_lines:
        return SIN_CONTEXTO

    clasificacion = _registro(header_lines, "HEADER")
    titulo = _registro(header_lines, "TITLE")
    if titulo and len(titulo) > MAX_TITULO:
        titulo = titulo[:MAX_TITULO - 1].rstrip() + "…"
    if clasificacion and titulo:
        return (f"{SIN_CONTEXTO} Clasificación del depósito: {clasificacion}; "
                f"título del depósito: {titulo}.")
    if clasificacion:
        return f"{SIN_CONTEXTO} Clasificación del depósito: {clasificacion}."
    if titulo:
        return f"{SIN_CONTEXTO} Título del depósito: {titulo}."
    return SIN_CONTEXTO
