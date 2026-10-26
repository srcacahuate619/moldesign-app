"""Lo que entra por la subida de un receptor: extensión, compresión y contenido.

# Qué garantiza

* La extensión se lee **sin distinguir mayúsculas** (`.PDB`, `.Cif`, `.PDBQT.GZ`):
  antes `endswith(".pdb")` rechazaba `8HFI_CRUDO.PDB` con un mensaje que escondía el motivo.
* Un `.gz` se descomprime con un **límite de tamaño descomprimido**: un archivo de
  31 MiB puede inflarse a decenas de GiB (bomba gzip) y tumbar el equipo del investigador.
* El contenido tiene que **corresponder a la extensión**: un `.pdb` que es un mmCIF, un
  `.pdbqt` que es un PDB o un SDF con nombre de receptor se rechazan diciendo qué es y qué hacer.
* Los mensajes **no ofrecen lo que no existe**: SDF y MOL2 son moléculas pequeñas, no receptores.

No interpreta la estructura (eso lo hacen la conversión de mmCIF, el lector de PQR y
la preparación); sólo decide si lo que llegó es un receptor legible y de qué clase.
"""

from __future__ import annotations

import gzip
import hashlib
import io
import zlib
from dataclasses import dataclass, field
from typing import Any

from services.targets.errores_subida import ErrorDeSubida

#: Tope del archivo DESCOMPRIMIDO. Un depósito grande (un ribosoma en mmCIF) ronda los 150 MiB;
#: por encima de este límite el investigador debe recortar las cadenas que no usa.
MAX_DESCOMPRIMIDO_BYTES = 128 * 1024 * 1024

FORMATO_PDB = "pdb"
FORMATO_MMCIF = "mmcif"
FORMATO_PQR = "pqr"
FORMATO_PDBQT = "pdbqt"

EXTENSIONES: dict[str, str] = {
    ".pdb": FORMATO_PDB, ".ent": FORMATO_PDB,
    ".cif": FORMATO_MMCIF, ".mmcif": FORMATO_MMCIF,
    ".pqr": FORMATO_PQR,
    ".pdbqt": FORMATO_PDBQT,
}

#: Formatos de moléculas pequeñas: existen, pero no son receptores.
_FORMATOS_DE_LIGANDO = (".sdf", ".mol", ".mol2", ".smi", ".smiles", ".xyz")
#: Formatos propietarios de otras herramientas: se exportan a PDB o mmCIF.
_FORMATOS_PROPIETARIOS = {
    ".mae": "Maestro", ".maegz": "Maestro", ".moe": "MOE", ".oeb": "OpenEye", ".cdx": "ChemDraw",
}

_AMINOACIDOS = frozenset({
    "ALA", "ARG", "ASN", "ASP", "CYS", "GLN", "GLU", "GLY", "HIS", "ILE", "LEU", "LYS", "MET", "PHE",
    "PRO", "SER", "THR", "TRP", "TYR", "VAL", "HID", "HIE", "HIP", "HSD", "HSE", "HSP", "CYX", "CYM",
    "ASH", "GLH", "LYN", "MSE", "SEP", "TPO", "PTR", "SEC", "PYL", "UNK", "ACE", "NME",
})


@dataclass(frozen=True)
class ArchivoSubido:
    """Un archivo ya leído: su identidad, su formato y su texto."""

    nombre: str                 # nombre seguro, sin carpetas
    extension: str              # la que se almacena: ".pdb", ".cif"… (minúsculas, sin .gz)
    formato: str                # pdb | mmcif | pqr | pdbqt
    comprimido: bool
    bytes_subidos: int
    sha256_subido: str          # del archivo tal como llegó (con .gz si lo traía)
    bytes_contenido: int
    sha256_contenido: str       # del contenido descomprimido
    contenido: bytes            # descomprimido, sin normalizar
    original: bytes             # tal como llegó (con .gz si lo traía)
    texto: str                  # decodificado, con \n como único salto de línea
    avisos: list[dict[str, Any]] = field(default_factory=list)

    @property
    def nombre_almacenado(self) -> str:
        """Dónde se guarda el original: un nombre fijo, nunca el del investigador."""
        return f"original{self.extension}" + (".gz" if self.comprimido else "")

    def identidad(self) -> dict[str, Any]:
        """Lo que se registra de la subida: nunca el contenido ni una ruta."""
        datos = {
            "archivo": self.nombre, "formato": self.formato, "comprimido": self.comprimido,
            "bytes": self.bytes_subidos, "sha256": self.sha256_subido,
            "bytes_descomprimidos": self.bytes_contenido, "sha256_contenido": self.sha256_contenido,
        }
        if self.avisos:
            datos["avisos"] = [a["codigo"] for a in self.avisos]
        return datos


def nombre_seguro(nombre: str | None) -> str:
    """El nombre sin carpetas ni caracteres raros; es lo único del nombre que se registra."""
    base = (nombre or "").replace("\\", "/").rsplit("/", 1)[-1]
    limpio = "".join(c if (c.isalnum() or c in "._-") else "_" for c in base).lstrip(".")
    return limpio[:80] or "archivo"


def _separar_extension(nombre: str) -> tuple[str, bool]:
    """(extensión en minúsculas sin el .gz, si traía .gz)."""
    minusculas = nombre.lower()
    comprimido = minusculas.endswith(".gz")
    if comprimido:
        minusculas = minusculas[:-3]
    punto = minusculas.rfind(".")
    return (minusculas[punto:] if punto > 0 else ""), comprimido


def _extension_invalida(nombre: str, extension: str, comprimido: bool) -> ErrorDeSubida:
    completo = extension + (".gz" if comprimido else "")
    if extension in _FORMATOS_DE_LIGANDO:
        return ErrorDeSubida(
            "EXTENSION_ES_LIGANDO",
            f"«{nombre}» es un formato de moléculas pequeñas ({completo}), no de receptores. "
            "Para un receptor sube la proteína en PDB o mmCIF (.pdb, .cif); los ligandos se "
            "introducen como SMILES al evaluar.",
            f"«{nombre}» is a small-molecule format ({completo}), not a receptor format. "
            "For a receptor upload the protein as PDB or mmCIF (.pdb, .cif); ligands are "
            "entered as SMILES when you evaluate.",
        )
    if extension in _FORMATOS_PROPIETARIOS:
        herramienta = _FORMATOS_PROPIETARIOS[extension]
        return ErrorDeSubida(
            "EXTENSION_PROPIETARIA",
            f"«{nombre}» es un archivo de {herramienta} ({completo}) y MolDesign no lo lee. "
            f"Expórtalo desde {herramienta} a PDB o mmCIF y súbelo de nuevo.",
            f"«{nombre}» is a {herramienta} file ({completo}) and MolDesign does not read it. "
            f"Export it from {herramienta} to PDB or mmCIF and upload it again.",
        )
    return ErrorDeSubida(
        "EXTENSION_NO_ADMITIDA",
        f"«{nombre}» tiene la extensión {completo or 'ninguna'}, que no es de un receptor admitido. "
        "Se admiten .pdb, .ent, .cif, .mmcif, .pqr y .pdbqt, y cada uno también comprimido (.gz). "
        "No distingue mayúsculas.",
        f"«{nombre}» has extension {completo or 'none'}, which is not a supported receptor format. "
        "Supported: .pdb, .ent, .cif, .mmcif, .pqr and .pdbqt, each also gzip-compressed (.gz). "
        "Case does not matter.",
    )


def _descomprimir(contenido: bytes, nombre: str) -> bytes:
    """gzip con tope: nunca se materializa más de ``MAX_DESCOMPRIMIDO_BYTES``."""
    if contenido[:2] != b"\x1f\x8b":
        raise ErrorDeSubida(
            "GZ_INVALIDO",
            f"«{nombre}» se llama .gz pero no es un archivo gzip válido (le falta la cabecera). "
            "Comprímelo de nuevo con gzip o súbelo sin la extensión .gz.",
            f"«{nombre}» is named .gz but is not a valid gzip file (the header is missing). "
            "Compress it again with gzip or upload it without the .gz extension.",
        )
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(contenido), mode="rb") as flujo:
            salida = flujo.read(MAX_DESCOMPRIMIDO_BYTES + 1)
    except (OSError, EOFError, zlib.error) as exc:
        raise ErrorDeSubida(
            "GZ_INVALIDO",
            f"«{nombre}» no se pudo descomprimir: el archivo gzip está dañado o truncado. "
            "Vuelve a comprimirlo o súbelo sin comprimir.",
            f"«{nombre}» could not be decompressed: the gzip file is damaged or truncated. "
            "Compress it again or upload it uncompressed.",
        ) from exc
    if len(salida) > MAX_DESCOMPRIMIDO_BYTES:
        limite = MAX_DESCOMPRIMIDO_BYTES // (1024 * 1024)
        raise ErrorDeSubida(
            "GZ_DEMASIADO_GRANDE",
            f"«{nombre}» ocupa más de {limite} MiB una vez descomprimido; MolDesign no lo abre por "
            "seguridad. Recorta del archivo las cadenas que no vas a usar y vuelve a subirlo.",
            f"«{nombre}» is larger than {limite} MiB once decompressed; MolDesign does not open it "
            "for safety. Remove the chains you will not use from the file and upload it again.",
            estado=413,
        )
    return salida


def _decodificar(contenido: bytes, nombre: str, avisos: list[dict[str, Any]]) -> str:
    if b"\x00" in contenido[:4096]:
        raise ErrorDeSubida(
            "CONTENIDO_BINARIO",
            f"«{nombre}» no es un archivo de texto (contiene bytes nulos). Comprueba que subiste la "
            "estructura y no un archivo binario o comprimido con otra extensión.",
            f"«{nombre}» is not a text file (it contains null bytes). Check that you uploaded the "
            "structure and not a binary or a compressed file with another extension.",
        )
    try:
        texto = contenido.decode("utf-8-sig")
    except UnicodeDecodeError:
        texto = contenido.decode("latin-1")
        avisos.append({
            "codigo": "DECODIFICADO_LATIN1",
            "es": "El archivo no es UTF-8; se leyó como Latin-1. Las columnas de átomos son ASCII, "
                  "pero revisa los comentarios si traen acentos.",
            "en": "The file is not UTF-8; it was read as Latin-1. Atom columns are ASCII, "
                  "but check the comments if they contain accents.",
        })
    if "\r" in texto:
        texto = texto.replace("\r\n", "\n").replace("\r", "\n")
    return texto


# ── Qué clase de archivo es, por su contenido ─────────────────────────────


def _lineas_de_atomo(texto: str, limite: int = 2000) -> list[str]:
    salida: list[str] = []
    for linea in texto.split("\n"):
        if linea.startswith(("ATOM", "HETATM")):
            salida.append(linea)
            if len(salida) >= limite:
                break
    return salida


def _tiene_tipo_autodock(linea: str) -> bool:
    """Una línea ATOM de PDBQT: carga parcial en 67-76 y tipo AutoDock en 78-79."""
    if len(linea) < 79:
        return False
    carga, tipo = linea[66:76].strip(), linea[77:79].strip()
    if not tipo or not carga:
        return False
    try:
        float(carga)
    except ValueError:
        return False
    return tipo[0].isalpha() and not tipo.replace(".", "").isdigit()


def clase_de_contenido(texto: str) -> str | None:
    """``mmcif`` · ``sdf`` · ``pdbqt`` · ``pdb`` (columnas PDB) · ``None`` si no se reconoce."""
    cabeza = texto[:200_000]
    primeras = [l.strip() for l in cabeza.split("\n", 400) if l.strip() and not l.lstrip().startswith("#")]
    if primeras and primeras[0].startswith("data_") and ("_atom_site." in cabeza or "loop_" in cabeza):
        return FORMATO_MMCIF
    if "\n$$$$" in cabeza or "M  END" in cabeza or "V2000" in cabeza or "V3000" in cabeza:
        return "sdf"
    atomos = _lineas_de_atomo(texto)
    if any(l.startswith(("ROOT", "ENDROOT", "TORSDOF", "BRANCH")) for l in primeras):
        return FORMATO_PDBQT
    if atomos:
        tipados = sum(_tiene_tipo_autodock(l) for l in atomos)
        return FORMATO_PDBQT if tipados > len(atomos) / 2 else FORMATO_PDB
    return None


_NOMBRES = {FORMATO_PDB: "PDB", FORMATO_MMCIF: "mmCIF", FORMATO_PQR: "PQR", FORMATO_PDBQT: "PDBQT", "sdf": "SDF"}
_PISTA = {
    FORMATO_MMCIF: ("súbelo con extensión .cif o .mmcif", "upload it with a .cif or .mmcif extension"),
    FORMATO_PDB: ("súbelo con extensión .pdb, o elige «Ya preparada por tu equipo» si es una estructura que ya protonaste",
                  "upload it with a .pdb extension, or choose «Already prepared by your team» if you already protonated it"),
    FORMATO_PDBQT: ("súbelo con extensión .pdbqt en el modo «PDBQT listo para Vina»",
                    "upload it with a .pdbqt extension in the «PDBQT ready for Vina» mode"),
    "sdf": ("un SDF es una molécula pequeña: para un receptor sube la proteína en PDB o mmCIF",
            "an SDF is a small molecule: for a receptor upload the protein as PDB or mmCIF"),
}


def _contenido_no_corresponde(nombre: str, esperado: str, real: str | None) -> ErrorDeSubida:
    if real is None:
        return ErrorDeSubida(
            "CONTENIDO_ILEGIBLE",
            f"«{nombre}» se llama como un archivo {_NOMBRES[esperado]}, pero no se reconoce ninguna "
            "línea de átomos (ATOM/HETATM o una tabla _atom_site). Comprueba que subiste la estructura "
            "del receptor y no un archivo vacío o de otra clase.",
            f"«{nombre}» is named like a {_NOMBRES[esperado]} file, but no atom line (ATOM/HETATM or an "
            "_atom_site table) was recognized. Check that you uploaded the receptor structure and not an "
            "empty file or another kind of file.",
        )
    es_pista, en_pista = _PISTA.get(real, ("revisa el formato", "check the format"))
    return ErrorDeSubida(
        f"CONTENIDO_ES_{real.upper()}",
        f"«{nombre}» tiene extensión de {_NOMBRES[esperado]} pero su contenido es {_NOMBRES[real]}: {es_pista}.",
        f"«{nombre}» has a {_NOMBRES[esperado]} extension but its content is {_NOMBRES[real]}: {en_pista}.",
    )


def _comprobar_contenido(nombre: str, formato: str, texto: str) -> None:
    real = clase_de_contenido(texto)
    if formato == FORMATO_MMCIF:
        if real != FORMATO_MMCIF:
            raise _contenido_no_corresponde(nombre, formato, real)
        return
    if formato == FORMATO_PQR:
        if real in (FORMATO_MMCIF, "sdf", FORMATO_PDBQT, None):
            raise _contenido_no_corresponde(nombre, formato, real)
        return
    if formato == FORMATO_PDB:
        if real != FORMATO_PDB:
            raise _contenido_no_corresponde(nombre, formato, real)
        return
    if formato == FORMATO_PDBQT and real != FORMATO_PDBQT:
        raise _contenido_no_corresponde(nombre, formato, real)


def leer_subida(nombre: str | None, contenido: bytes) -> ArchivoSubido:
    """Lee lo que subió la persona. Lanza ``ErrorDeSubida`` con qué falló y qué hacer."""
    seguro = nombre_seguro(nombre)
    extension, comprimido = _separar_extension(seguro)
    formato = EXTENSIONES.get(extension)
    if formato is None:
        raise _extension_invalida(seguro, extension, comprimido)
    if not contenido:
        raise ErrorDeSubida(
            "ARCHIVO_VACIO", f"«{seguro}» está vacío.", f"«{seguro}» is empty.")
    avisos: list[dict[str, Any]] = []
    descomprimido = _descomprimir(contenido, seguro) if comprimido else contenido
    if not comprimido and contenido[:2] == b"\x1f\x8b":
        raise ErrorDeSubida(
            "GZ_SIN_EXTENSION",
            f"«{seguro}» está comprimido con gzip pero no se llama .gz. Añade .gz al nombre "
            f"({seguro}.gz) o súbelo sin comprimir.",
            f"«{seguro}» is gzip-compressed but is not named .gz. Add .gz to the name "
            f"({seguro}.gz) or upload it uncompressed.",
        )
    if not descomprimido:
        raise ErrorDeSubida(
            "ARCHIVO_VACIO", f"«{seguro}» está vacío una vez descomprimido.",
            f"«{seguro}» is empty once decompressed.")
    texto = _decodificar(descomprimido, seguro, avisos)
    _comprobar_contenido(seguro, formato, texto)
    return ArchivoSubido(
        nombre=seguro, extension=extension, formato=formato, comprimido=comprimido,
        bytes_subidos=len(contenido), sha256_subido=hashlib.sha256(contenido).hexdigest(),
        bytes_contenido=len(descomprimido), sha256_contenido=hashlib.sha256(descomprimido).hexdigest(),
        contenido=descomprimido, original=contenido, texto=texto, avisos=avisos,
    )


def sin_proteina(texto_pdb: str) -> bool:
    """``True`` si el PDB no tiene ni un residuo de aminoácido (p. ej. sólo ADN)."""
    for linea in texto_pdb.split("\n"):
        if linea.startswith(("ATOM", "HETATM")) and len(linea) >= 20 and linea[17:20].strip() in _AMINOACIDOS:
            return False
    return True
