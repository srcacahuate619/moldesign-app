"""
Ingesta de cohortes: leer sin descartar.

# La diferencia con `api/routers/batch.py`

Los extractores del Batch histórico son **con pérdida por contrato**: filtran
`if smiles and len(smiles) > 1`, saltan la fila si RDKit falla, indexan las
etiquetas por NOMBRE (dos moléculas homónimas comparten etiqueta) y fabrican un
nombre a partir del SMILES cuando falta. Para lo que hacen —arrancar un cribado
y ordenar la tabla— basta.

Aquí no basta. La cobertura de una cohorte es `elegibles / total`, y ese total
tiene que ser el del archivo que la persona subió. Un parser que descarta filas
reduce el denominador y convierte una cohorte del 60 % en una del 100 %, que es
exactamente la afirmación que este producto existe para no hacer.

Por eso **no se reutilizan** aquellos extractores ni se refactorizan para
compartir cuerpo: no son la misma función con otro llamador, son dos contratos
opuestos, y fundirlos obligaría a cambiar uno de los dos. El Batch histórico
sigue intacto hasta que 5B lo retire; entonces desaparece, no se unifica.

Consecuencia concreta: el CSV se lee con `csv.reader`, no con `DictReader`.
`DictReader` SALTA las líneas en blanco, así que una fila vacía dejaría de
existir y el total mentiría.

# Formatos y columnas

    .csv            cabecera en la primera fila
    .xlsx / .xls    cabecera en la primera fila
    .sdf            un registro por molécula; propiedades del bloque
    .smi / .txt     `smiles [nombre] [active] [control_role]`, separados por
                    espacios; `#` es comentario

Columnas reconocidas (insensible a mayúsculas, primera coincidencia):

    smiles          smiles · canonical_smiles · structure
    name            name · id · identifier · molecule_name
    active          active
    control_role    control_role

`control_role` se lee TAL CUAL. No se deduce de un nombre que empiece por
«ref», ni de la posición en el archivo, ni de nada más.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field

from services.cohort.taxonomy import (
    ARCHIVO_ILEGIBLE,
    COLUMNA_SMILES_AUSENTE,
    FILA_COLUMNAS_INCONSISTENTES,
    FORMATO_NO_SOPORTADO,
    LECTOR_NO_DISPONIBLE,
    REGISTRO_ILEGIBLE,
)

SMILES_COLUMNS = ("smiles", "canonical_smiles", "structure")
NAME_COLUMNS = ("name", "id", "identifier", "molecule_name")
ACTIVE_COLUMNS = ("active",)
CONTROL_ROLE_COLUMNS = ("control_role",)

#: Terminador de registro del formato SDF (MDL).
SDF_TERMINATOR = "$$$$"


@dataclass(frozen=True)
class RawRow:
    """
    Una fila del archivo antes de interpretar nada.

    Los campos son CRUDOS a propósito: `active_raw` y `control_role_raw` viajan
    como texto porque interpretarlos es una decisión con taxonomía —una etiqueta
    ilegible produce un aviso, no un valor inventado— y esa decisión pertenece a
    `preflight.py`, no al lector de archivos.
    """

    row_index: int
    source_name: str | None
    input_smiles: str
    active_raw: str | None = None
    control_role_raw: str | None = None
    #: Razones de ingesta que YA invalidan la fila (un registro SDF corrupto).
    reasons: tuple[str, ...] = ()
    #: Avisos de ingesta (forma de la fila).
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ParsedFile:
    """Lo que la ingesta pudo leer, y lo que impidió leer el resto."""

    format: str
    rows: tuple[RawRow, ...] = ()
    blockers: tuple[str, ...] = ()
    fields: frozenset[str] = field(default_factory=frozenset)


def _decode(content: bytes) -> str | None:
    """
    UTF-8 estricto (con BOM opcional). `None` si no es texto UTF-8.

    NO se usa `errors="replace"`. Sustituir bytes ilegibles por `U+FFFD`
    convertiría un archivo corrupto en un archivo aparentemente legible lleno de
    moléculas ilegibles, y el diagnóstico apuntaría a la química en vez de al
    archivo.
    """
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return None


def _column_index(headers: list[str], candidates: tuple[str, ...]) -> int | None:
    """Primera coincidencia. Determinista: el orden de `candidates` manda."""
    for candidate in candidates:
        for index, header in enumerate(headers):
            if header == candidate:
                return index
    return None


def _cell(row: list[str], index: int | None) -> str | None:
    if index is None or index >= len(row):
        return None
    value = (row[index] or "").strip()
    return value or None


def _rows_from_table(
    table: list[list[str]],
    formato: str,
) -> ParsedFile:
    """
    Cabecera + filas, para CSV y Excel por igual.

    Sin cabecera no hay tabla: se declara la cohorte vacía con el bloqueante de
    columna ausente, en lugar de adivinar que la primera columna son SMILES.
    """
    if not table:
        return ParsedFile(format=formato, blockers=(COLUMNA_SMILES_AUSENTE,))

    headers = [(cell or "").strip().lower() for cell in table[0]]
    smiles_at = _column_index(headers, SMILES_COLUMNS)
    name_at = _column_index(headers, NAME_COLUMNS)
    active_at = _column_index(headers, ACTIVE_COLUMNS)
    role_at = _column_index(headers, CONTROL_ROLE_COLUMNS)

    campos = {
        nombre
        for nombre, indice in (
            ("smiles", smiles_at),
            ("name", name_at),
            ("active", active_at),
            ("control_role", role_at),
        )
        if indice is not None
    }

    rows: list[RawRow] = []
    for index, raw in enumerate(table[1:]):
        avisos: tuple[str, ...] = ()
        # Una fila en blanco llega como `[]` desde `csv.reader`. Se conserva:
        # es una fila del archivo y cuenta en el denominador.
        if raw and len(raw) != len(headers):
            avisos = (FILA_COLUMNAS_INCONSISTENTES,)
        rows.append(
            RawRow(
                row_index=index,
                source_name=_cell(raw, name_at),
                input_smiles=_cell(raw, smiles_at) or "",
                active_raw=_cell(raw, active_at),
                control_role_raw=_cell(raw, role_at),
                warnings=avisos,
            )
        )

    blockers = () if smiles_at is not None else (COLUMNA_SMILES_AUSENTE,)
    return ParsedFile(
        format=formato, rows=tuple(rows), blockers=blockers, fields=frozenset(campos)
    )


def _parse_csv(content: bytes) -> ParsedFile:
    texto = _decode(content)
    if texto is None:
        return ParsedFile(format="csv", blockers=(ARCHIVO_ILEGIBLE,))
    try:
        tabla = [list(fila) for fila in csv.reader(io.StringIO(texto, newline=""))]
    except csv.Error:
        return ParsedFile(format="csv", blockers=(ARCHIVO_ILEGIBLE,))
    # Un salto de línea final produce una última fila vacía que NO es una fila
    # del archivo: es el terminador. Se retira sólo esa.
    if tabla and tabla[-1] == []:
        tabla.pop()
    return _rows_from_table(tabla, "csv")


def _parse_excel(content: bytes) -> ParsedFile:
    try:
        import openpyxl
    except ImportError:
        return ParsedFile(format="excel", blockers=(LECTOR_NO_DISPONIBLE,))

    try:
        libro = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        hoja = libro.active
        filas = [
            ["" if celda is None else str(celda) for celda in fila]
            for fila in hoja.iter_rows(values_only=True)
        ]
        libro.close()
    except Exception:
        return ParsedFile(format="excel", blockers=(ARCHIVO_ILEGIBLE,))

    # Excel declara una dimensión que suele exceder los datos: openpyxl fabrica
    # filas completamente vacías al final. Se recortan SÓLO las del final —una
    # fila vacía intercalada sí es una fila que alguien dejó en blanco y se
    # conserva—, porque contar el relleno de la hoja como moléculas ausentes
    # hundiría la cobertura por un artefacto del formato.
    while filas and all(celda.strip() == "" for celda in filas[-1]):
        filas.pop()

    return _rows_from_table(filas, "excel")


def _sdf_records(texto: str) -> list[str]:
    """
    Trocea el SDF por su terminador `$$$$`, ANTES de que RDKit lo vea.

    `SDMolSupplier` no es un contador fiable de registros: ante un bloque que no
    empieza por una cabecera válida deja de emitir en vez de emitir `None`, y el
    registro corrupto desaparece sin dejar rastro. Para un cribado eso es una
    molécula menos; para una cohorte es el denominador de la cobertura.

    Aquí el troceo lo hace el formato —el terminador está definido en la
    especificación de MDL— y RDKit sólo opina sobre cada bloque por separado.
    """
    registros: list[str] = []
    actual: list[str] = []
    for linea in texto.splitlines():
        if linea.strip() == SDF_TERMINATOR:
            registros.append("\n".join(actual))
            actual = []
            continue
        actual.append(linea)
    # Un último bloque sin terminador sigue siendo un registro declarado.
    if any(linea.strip() for linea in actual):
        registros.append("\n".join(actual))
    return [registro for registro in registros if registro.strip()]


def _parse_sdf(content: bytes) -> ParsedFile:
    texto = _decode(content)
    if texto is None:
        return ParsedFile(format="sdf", blockers=(ARCHIVO_ILEGIBLE,))
    try:
        from rdkit import Chem
        from rdkit import RDLogger
    except ImportError:
        return ParsedFile(format="sdf", blockers=(LECTOR_NO_DISPONIBLE,))

    RDLogger.DisableLog("rdApp.*")
    try:
        rows: list[RawRow] = []
        campos: set[str] = {"smiles"}
        for index, registro in enumerate(_sdf_records(texto)):
            supplier = Chem.SDMolSupplier()
            supplier.SetData(
                f"{registro}\n{SDF_TERMINATOR}\n", sanitize=True, removeHs=False
            )
            mol = next(iter(supplier), None)
            if mol is None:
                # El registro existe y no se pudo leer. Se conserva: saltarlo
                # dejaría una cohorte que dice tener menos moléculas de las que
                # el archivo declara.
                rows.append(
                    RawRow(
                        row_index=index,
                        source_name=None,
                        input_smiles="",
                        reasons=(REGISTRO_ILEGIBLE,),
                    )
                )
                continue
            nombre = mol.GetProp("_Name").strip() if mol.HasProp("_Name") else ""
            activo = mol.GetProp("active").strip() if mol.HasProp("active") else None
            rol = mol.GetProp("control_role").strip() if mol.HasProp("control_role") else None
            if nombre:
                campos.add("name")
            if activo is not None:
                campos.add("active")
            if rol is not None:
                campos.add("control_role")
            rows.append(
                RawRow(
                    row_index=index,
                    source_name=nombre or None,
                    input_smiles=Chem.MolToSmiles(mol),
                    active_raw=activo or None,
                    control_role_raw=rol or None,
                )
            )
    except Exception:
        return ParsedFile(format="sdf", blockers=(ARCHIVO_ILEGIBLE,))
    finally:
        RDLogger.EnableLog("rdApp.*")

    return ParsedFile(format="sdf", rows=tuple(rows), fields=frozenset(campos))


def _parse_smiles_text(content: bytes) -> ParsedFile:
    texto = _decode(content)
    if texto is None:
        return ParsedFile(format="smiles", blockers=(ARCHIVO_ILEGIBLE,))

    rows: list[RawRow] = []
    campos: set[str] = {"smiles"}
    for linea in texto.splitlines():
        limpia = linea.strip()
        # En un formato orientado a líneas, una línea en blanco y un comentario
        # no son registros: son separadores. No se cuentan como moléculas
        # ausentes porque nadie declaró una molécula ahí.
        if not limpia or limpia.startswith("#"):
            continue
        partes = limpia.split()
        rows.append(
            RawRow(
                row_index=len(rows),
                source_name=partes[1] if len(partes) > 1 else None,
                input_smiles=partes[0],
                active_raw=partes[2] if len(partes) > 2 else None,
                control_role_raw=partes[3] if len(partes) > 3 else None,
            )
        )
        if len(partes) > 1:
            campos.add("name")
        if len(partes) > 2:
            campos.add("active")
        if len(partes) > 3:
            campos.add("control_role")

    return ParsedFile(format="smiles", rows=tuple(rows), fields=frozenset(campos))


def read_cohort_file(filename: str, content: bytes) -> ParsedFile:
    """
    Lee el archivo conservando TODAS sus filas de datos.

    El formato se decide por extensión, igual que en el Batch histórico: no se
    olfatea el contenido, porque adivinar produce un formato distinto del que la
    persona cree haber subido y el fallo aparece lejos de su causa.
    """
    nombre = (filename or "").lower()
    if nombre.endswith(".csv"):
        return _parse_csv(content)
    if nombre.endswith((".xlsx", ".xls")):
        return _parse_excel(content)
    if nombre.endswith(".sdf"):
        return _parse_sdf(content)
    if nombre.endswith((".smi", ".txt")):
        return _parse_smiles_text(content)
    return ParsedFile(format="desconocido", blockers=(FORMATO_NO_SOPORTADO,))
