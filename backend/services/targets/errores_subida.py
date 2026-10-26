"""Errores de la subida de receptores propios: qué falló y qué hacer, en los dos idiomas.

La subida convertía cualquier ``ValueError`` en un 400 genérico («Error de
validación…») y el motivo real se perdía: una extensión en mayúsculas, un mmCIF o
un PDBQT sin estructura de origen eran indistinguibles para quien subía el
archivo. Estos errores llevan un código estable, el texto en castellano y en
inglés, y nunca una ruta del disco ni el contenido del archivo.

Heredan de ``ValueError`` a propósito: los llamadores antiguos que capturan
``ValueError`` siguen funcionando, aunque el router los trate aparte para
conservar el mensaje.
"""

from __future__ import annotations

import re
from typing import Any

#: Una ruta de Windows o de POSIX dentro de un mensaje. Un error de subida no la lleva.
_RUTA = re.compile(r"(?:[A-Za-z]:[\\/]|/(?:home|Users|tmp|var|usr)/)[^\s'\"]+")


class ErrorDeSubida(ValueError):
    """Un fallo de la subida que la persona puede corregir."""

    def __init__(self, codigo: str, es: str, en: str, *, estado: int = 400, **datos: Any) -> None:
        super().__init__(es)
        self.codigo = codigo
        self.es = es
        self.en = en
        self.estado = estado
        self.datos = datos

    def mensaje(self, idioma: str = "es") -> str:
        texto = self.en if (idioma or "es").lower().startswith("en") else self.es
        return _RUTA.sub("<ruta omitida>", texto)

    def como_json(self, idioma: str = "es") -> dict[str, Any]:
        return {"detail": self.mensaje(idioma), "codigo": self.codigo, "datos": self.datos}


def formatos_aceptados() -> str:
    """La lista que se enseña cuando la extensión no es ninguna de las admitidas."""
    return ".pdb, .ent, .cif, .mmcif, .pqr, .pdbqt (" + ", ".join(
        f"{e}.gz" for e in (".pdb", ".cif", ".pqr", ".pdbqt")) + "…)"


def _etiquetas_de_residuos(detalle: str) -> str:
    """Los residuos que cita un error de preparación (JSON dentro del texto), sin rutas ni stderr."""
    import json

    inicio, fin = detalle.find("["), detalle.rfind("]")
    if inicio == -1 or fin == -1:
        return ""
    try:
        filas = json.loads(detalle[inicio:fin + 1])
    except ValueError:
        return ""
    etiquetas = [
        f"{f.get('name')} {f.get('chain')}:{f.get('residue_number')}" for f in filas if isinstance(f, dict)
    ]
    return ", ".join(etiquetas[:8]) + ("…" if len(etiquetas) > 8 else "")


#: Meeko cita el residuo que no pudo construir así: «interrupted residues in PDB: {'A:438'}».
_RESIDUOS_INTERRUMPIDOS = re.compile(r"interrupted residues in PDB:\s*\{([^}]*)\}")
_ETIQUETA_DE_RESIDUO = re.compile(r"[A-Za-z0-9]{1,4}:-?\d+[A-Za-z]?")


def _residuos_interrumpidos(detalle: str) -> list[str]:
    """Las etiquetas «A:438» que Meeko cita al no poder construir un residuo, sin rutas ni salida de error."""
    cita = _RESIDUOS_INTERRUMPIDOS.search(detalle or "")
    if cita is None:
        return []
    etiquetas = [e for e in re.findall(r"'([^']+)'", cita.group(1)) if _ETIQUETA_DE_RESIDUO.fullmatch(e)]
    return etiquetas[:8]


def cadenas_con_proteina(texto_pdb: str) -> list[str]:
    """Las cadenas que tienen al menos un registro ATOM (proteína), en orden alfabético."""
    return sorted({
        (l[21:22].strip() or "A") for l in (texto_pdb or "").split("\n") if l.startswith("ATOM") and len(l) > 21
    })


def error_de_cadena(cadena: str | None, cadenas: list[str]) -> ErrorDeSubida:
    """La cadena pedida no tiene proteína en el archivo: se dice cuáles sí."""
    con = ", ".join(cadenas)
    return ErrorDeSubida(
        "CADENA_SIN_PROTEINA",
        f"La cadena «{cadena or '?'}» no tiene átomos de proteína en el archivo. "
        + (f"Cadenas con proteína: {con}. " if con else "")
        + "Indica una de ellas en «Cadena» y vuelve a subirlo.",
        f"Chain «{cadena or '?'}» has no protein atoms in the file. "
        + (f"Chains with protein: {con}. " if con else "")
        + "Enter one of them in «Chain» and upload again.",
        cadenas=cadenas,
    )


def desde_preparacion(
    exc: Exception, *, cadena: str | None = None, texto_pdb: str | None = None, modo: str | None = None,
) -> ErrorDeSubida:
    """Convierte un fallo de la preparación en un error de subida con motivo y acción.

    ``ProteinPreparationError.detail`` puede traer la línea de comandos de Meeko, con rutas
    temporales, y la salida de error del programa: nada de eso llega a quien sube el archivo
    (queda en el registro). Sólo se cita lo que la persona puede actuar: cadena, residuos, cofactores.
    """
    if isinstance(exc, ErrorDeSubida):
        return exc
    paso = str(getattr(exc, "step", "") or "")
    detalle = str(getattr(exc, "detail", "") or "")
    cadenas = cadenas_con_proteina(texto_pdb or "")
    if paso == "chain_filtering":
        return error_de_cadena(cadena, cadenas)
    if paso == "cofactor_template_missing":
        lista = detalle.split("caja: ", 1)[-1].split(". Se detiene", 1)[0] if "caja: " in detalle else ""
        return ErrorDeSubida(
            "COFACTOR_SIN_PLANTILLA",
            "Hay cofactores o residuos modificados junto al sitio sin una plantilla local de Meeko"
            + (f" ({lista})" if lista else "")
            + ". MolDesign no los descarga de la red ni los retira en silencio porque cambiarían la "
              "química de la cavidad. Retíralos del archivo y vuelve a subirlo, o sube un PDBQT que "
              "ya los incluya.",
            "There are cofactors or modified residues next to the site without a local Meeko template"
            + (f" ({lista})" if lista else "")
            + ". MolDesign neither downloads them nor removes them silently because that would change "
              "the chemistry of the cavity. Remove them from the file and upload again, or upload a "
              "PDBQT that already includes them.",
        )
    if paso == "receptor_site_residues_missing":
        perdidos = _etiquetas_de_residuos(detalle)
        respetando = modo == "respetar"
        return ErrorDeSubida(
            "RESIDUOS_DEL_SITIO_PERDIDOS",
            "La preparación habría perdido residuos del sitio"
            + (f" ({perdidos})" if perdidos else "")
            + " y MolDesign no acopla contra un sitio incompleto. Suele deberse a átomos pesados que "
              "faltan en esos residuos"
            + (" o a hidrógenos cuyos nombres no siguen la convención de las plantillas de Meeko "
               "(HB2/HB3, HE2…)" if respetando else "")
            + "; repara la estructura o usa otra del mismo receptor.",
            "Preparation would have lost residues of the site"
            + (f" ({perdidos})" if perdidos else "")
            + " and MolDesign does not dock against an incomplete site. This is usually due to heavy "
              "atoms missing from those residues"
            + (" or to hydrogens whose names do not follow Meeko's template convention (HB2/HB3, HE2…)"
               if respetando else "")
            + "; repair the structure or use another one of the same receptor.",
        )
    if paso == "especie_no_representable":
        try:
            import json as _json

            filas = _json.loads(detalle)
        except ValueError:
            filas = []
        etiquetas = ", ".join(f"{f.get('name')} {f.get('chain')}:{f.get('residue_number')}" for f in filas[:6])
        motivos_es = "; ".join(sorted({str(f.get("motivo_texto")) for f in filas if f.get("motivo_texto")}))
        return ErrorDeSubida(
            "ESPECIE_NO_REPRESENTABLE",
            "El archivo trae especies junto al sitio que MolDesign no puede representar para Vina"
            + (f" ({etiquetas})" if etiquetas else "")
            + (f": {motivos_es}" if motivos_es else "")
            + ". No se adivinan ni se retiran en silencio: quítalas del archivo, o sube el receptor ya "
              "preparado como PDBQT (donde tu herramienta las haya tipado).",
            "The file has species next to the site that MolDesign cannot represent for Vina"
            + (f" ({etiquetas})" if etiquetas else "")
            + ". They are neither guessed nor silently removed: remove them from the file, or upload the "
              "already-prepared receptor as PDBQT (where your tool has typed them).",
            especies=filas[:20],
        )
    if paso == "protonacion_cambiada":
        try:
            import json as _json

            cambios = _json.loads(detalle)
        except ValueError:
            cambios = []
        lista = ", ".join(cambios[:6])
        return ErrorDeSubida(
            "PROTONACION_CAMBIADA",
            "Meeko aplicó una plantilla distinta de la protonación que declara el archivo"
            + (f" ({lista})" if lista else "")
            + ". MolDesign no deja pasar ese cambio: revisa los átomos de hidrógeno de esos residuos o "
              "sube el receptor ya preparado como PDBQT.",
            "Meeko applied a template different from the protonation the file declares"
            + (f" ({lista})" if lista else "")
            + ". MolDesign does not let that change through: check the hydrogen atoms of those residues or "
              "upload the already-prepared receptor as PDBQT.",
            cambios=cambios[:20],
        )
    if paso == "site_chains_missing":
        return ErrorDeSubida(
            "CADENAS_DEL_SITIO_PERDIDAS",
            "El sitio se forma entre varias cadenas y el receptor preparado no las contendría todas, "
            "así que se acoplaría contra media cavidad. Comprueba que el archivo trae todas las "
            "cadenas del sitio.",
            "The site is formed between several chains and the prepared receptor would not contain "
            "all of them, so docking would run against half a cavity. Check that the file has all "
            "the chains of the site.",
        )
    if paso.startswith("dynamic_box"):
        return ErrorDeSubida(
            "CAJA_NO_DERIVABLE",
            "No se pudo derivar la caja de búsqueda del archivo. Indica el centro (x, y, z, en Å) y "
            "vuelve a subirlo.",
            "The search box could not be derived from the file. Give the center (x, y, z, in Å) "
            "and upload again.",
        )
    if paso.startswith(("mk_prepare", "meeko", "validate_pdbqt")):
        interrumpidos = _residuos_interrumpidos(detalle)
        if interrumpidos:
            # Meeko dice el residuo exacto: decirlo es más útil que la lista genérica de causas.
            lista = ", ".join(interrumpidos)
            return ErrorDeSubida(
                "MEEKO_NO_PUDO",
                f"Meeko no pudo preparar este receptor: en el archivo, los átomos de {lista} no van "
                "seguidos. Ordénalos en el archivo y vuelve a subirlo, o sube el receptor ya preparado como PDBQT.",
                f"Meeko could not prepare this receptor: in the file, the atoms of {lista} are not "
                "contiguous. Reorder them in the file and upload again, or upload the already-prepared "
                "receptor as PDBQT.",
                paso=paso, residuos=interrumpidos,
            )
        return ErrorDeSubida(
            "MEEKO_NO_PUDO",
            "Meeko no pudo preparar este receptor. Suele deberse a residuos no estándar, a átomos con "
            "nombres que no reconoce o a hidrógenos que no casan con sus plantillas. Revisa el archivo "
            "o sube el receptor ya preparado como PDBQT.",
            "Meeko could not prepare this receptor. This is usually due to non-standard residues, atom "
            "names it does not recognize or hydrogens that do not match its templates. Check the file "
            "or upload the already-prepared receptor as PDBQT.",
            paso=paso,
        )
    return ErrorDeSubida(
        "PREPARACION_FALLIDA",
        "La preparación del receptor falló"
        + (f" en el paso «{paso}»" if paso else "")
        + ". Revisa que el archivo sea la estructura completa de una proteína; el detalle técnico queda "
          "en el registro de MolDesign.",
        "Receptor preparation failed"
        + (f" at step «{paso}»" if paso else "")
        + ". Check that the file is the complete structure of a protein; the technical detail is kept "
          "in the MolDesign log.",
        paso=paso,
    )
