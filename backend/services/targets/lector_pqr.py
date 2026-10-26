"""PQR (salida de PDB2PQR/PROPKA) → PDB clásico.

Un PQR es un PDB con la carga parcial y el radio de cada átomo en lugar de la ocupación y el factor B. Para un
equipo que protonó su receptor con PDB2PQR es el formato natural, así que se lee:

* **conservando nombres y coordenadas** tal como vienen (incluidos los hidrógenos y los nombres de protonación:
  ``HID``/``HIE``/``HIP``, ``CYX``, ``HSD``…, que después trata el modo «respetar»);
* **declarando que Vina no usa sus cargas**: las cargas y los radios se descartan, se cuentan y quedan en el
  informe. La carga parcial de un PDBQT sale de Meeko, no del PQR.

Lo que un PQR no trae se declara en vez de inventarse: sin cadena (se asigna ``A``), sin ocupación ni factor B
(1,00 y 0,00). Un nombre de residuo de cuatro caracteres (``NALA``, ``CALA``: residuos terminales de AMBER en
PDB2PQR) se reduce al residuo base si lo es; cualquier otro se rechaza con su motivo.
"""

from __future__ import annotations

import math
from typing import Any

from services.targets.errores_subida import ErrorDeSubida
from services.targets.normalizar_pdb import elemento_desde_el_nombre

_AMINOACIDOS = frozenset({
    "ALA", "ARG", "ASN", "ASP", "CYS", "GLN", "GLU", "GLY", "HIS", "ILE", "LEU", "LYS", "MET", "PHE", "PRO",
    "SER", "THR", "TRP", "TYR", "VAL", "HID", "HIE", "HIP", "HSD", "HSE", "HSP", "CYX", "CYM", "ASH", "GLH",
    "LYN",
})
#: Parches de CHARMM que PDB2PQR 3.7.1 escribe como residuos aparte, con el número del aminoácido al que parchean
#: (medido con 8HFI: ``TER`` = carboxilo C-terminal C/OT1/OT2; ``DISU`` = CB/SG de una cistina como «1CB», «1SG»).
_PARCHES_CHARMM = frozenset({"TER", "DISU"})
_IONES_DE_DOS_LETRAS = frozenset({"CL", "BR", "FE", "ZN", "MG", "MN", "CU", "NA", "CA", "CO", "NI", "CD", "SE"})


def _flotantes(trozos: list[str]) -> list[float] | None:
    try:
        valores = [float(t) for t in trozos]
    except ValueError:
        return None
    return valores if all(math.isfinite(v) for v in valores) else None


def _por_columnas(linea: str) -> dict[str, Any] | None:
    """Las columnas de un PDB (nombre 13–16, residuo 17–20, x, y, z en 31–54) seguidas de carga y radio.

    Así escribe PDB2PQR, y es la lectura que no se equivoca cuando el nombre del átomo y el del residuo quedan
    pegados (``1CBDISU``, el parche de disulfuro de CHARMM): partir por espacios los confundiría con un átomo sin
    cadena. Se exige que las columnas en blanco lo estén y que el número de residuo sea entero; si no, no es esta
    disposición y se prueba la lectura por campos.
    """
    if len(linea) < 56 or linea[11:12].strip() or linea[20:21].strip():
        return None
    numero, nombre, residuo = linea[22:26].strip(), linea[12:16].strip(), linea[16:20].strip()
    if not linea[6:11].strip().isdigit() or not numero.lstrip("-").isdigit() or not nombre or not residuo:
        return None
    coordenadas = _flotantes([linea[30:38], linea[38:46], linea[46:54]])
    resto = _flotantes(linea[54:].split())
    if coordenadas is None or resto is None or len(resto) != 2:
        return None
    return {
        "nombre": nombre, "residuo": residuo, "cadena": linea[21:22].strip(), "numero": numero,
        "insercion": linea[26:27].strip(), "xyz": coordenadas, "carga": resto[0], "radio": resto[1],
    }


def _por_campos(linea: str) -> dict[str, Any] | None:
    """El PQR estricto: campos separados por espacios, con la cadena opcional."""
    campos = linea.split()
    if len(campos) not in (10, 11):
        return None
    numeros = _flotantes(campos[-5:])
    if numeros is None:
        return None
    sin_cadena = len(campos) == 10
    residuo = campos[3]
    cadena = "" if sin_cadena else campos[4]
    numero = campos[4] if sin_cadena else campos[5]
    insercion = ""
    if numero and numero[-1].isalpha():
        numero, insercion = numero[:-1], numero[-1]
    if not numero.lstrip("-").isdigit():
        return None
    return {"nombre": campos[2], "residuo": residuo, "cadena": cadena, "numero": numero, "insercion": insercion,
            "xyz": numeros[:3], "carga": numeros[3], "radio": numeros[4]}


def _ambigua_por_campos(fila: dict[str, Any]) -> bool:
    """Sin cadena y con un «residuo» de una letra: lo más probable es que el nombre del átomo y el del residuo vengan
    pegados y la línea tenga la cadena. Es indecidible por campos, así que no se adivina."""
    return not fila["cadena"] and len(fila["residuo"]) == 1


def _campo_nombre(nombre: str, registro: str, residuo: str) -> str:
    if len(nombre) >= 4:
        return nombre[:4]
    if registro == "HETATM" and nombre.upper() in _IONES_DE_DOS_LETRAS and residuo.upper() == nombre.upper():
        return nombre.ljust(4)
    return (" " + nombre).ljust(4)


def pqr_a_pdb(texto: str, nombre_archivo: str = "archivo") -> tuple[str, dict[str, Any]]:
    """El PDB resultante y el informe de lo que se descartó y de lo que el PQR no traía."""
    salida: list[str] = []
    atomos = 0
    sin_cadena = 0
    terminales: dict[str, str] = {}
    parches: dict[str, set[tuple[str, str]]] = {}
    cargas_netas = 0.0
    serial = 0
    for numero_linea, linea in enumerate(texto.split("\n"), start=1):
        # «ATOM 1887 …» (un solo espacio, de herramientas que no respetan las columnas) también es un átomo.
        registro = "HETATM" if linea.startswith("HETATM") else "ATOM" if linea.startswith("ATOM") else linea[:6].strip()
        if registro == "TER":
            salida.append("TER")
            continue
        if registro not in ("ATOM", "HETATM"):
            continue
        # Primero las columnas de un PDB (la disposición de PDB2PQR, que admite residuos de cuatro caracteres y
        # nombres pegados); si la línea no las respeta, los campos separados por espacios del PQR estricto.
        fila = _por_columnas(linea)
        if fila is None:
            fila = _por_campos(linea)
            if fila is not None and _ambigua_por_campos(fila):
                raise ErrorDeSubida(
                    "PQR_LINEA_AMBIGUA",
                    f"La línea {numero_linea} de «{nombre_archivo}» es ambigua: no trae cadena y el residuo "
                    f"«{fila['residuo']}» tiene una sola letra, lo que suele ser un nombre de átomo pegado al del "
                    "residuo. Vuelve a generar el PQR con PDB2PQR (que escribe cadena y columnas) y súbelo de nuevo.",
                    f"Line {numero_linea} of «{nombre_archivo}» is ambiguous: it has no chain and residue "
                    f"«{fila['residuo']}» is a single letter, which usually means an atom name glued to the residue "
                    "name. Regenerate the PQR with PDB2PQR (which writes the chain and fixed columns) and upload it "
                    "again.",
                )
        if fila is None:
            raise ErrorDeSubida(
                "PQR_LINEA_ILEGIBLE",
                f"La línea {numero_linea} de «{nombre_archivo}» no se puede leer como PQR: se esperan nombre, "
                "residuo, cadena, número, x, y, z, carga y radio. Comprueba que el archivo es la salida de "
                "PDB2PQR y no un PDB con otra extensión.",
                f"Line {numero_linea} of «{nombre_archivo}» cannot be read as PQR: name, residue, chain, number, "
                "x, y, z, charge and radius are expected. Check that the file is PDB2PQR output and not a PDB "
                "with another extension.",
            )
        residuo = fila["residuo"]
        if residuo.upper() in _PARCHES_CHARMM:
            parches.setdefault(residuo.upper(), set()).add((fila["cadena"] or "A", fila["numero"]))
            continue
        if len(residuo) > 3:
            base = residuo[1:] if residuo[0] in "NC" else ""
            if base not in _AMINOACIDOS:
                raise ErrorDeSubida(
                    "PQR_RESIDUO_NO_REPRESENTABLE",
                    f"El residuo «{residuo}» (línea {numero_linea}) tiene más de tres caracteres y el PDB clásico "
                    "no puede escribirlo. Renómbralo con su código de tres letras y vuelve a subirlo.",
                    f"Residue «{residuo}» (line {numero_linea}) has more than three characters and classic PDB "
                    "cannot write it. Rename it with its three-letter code and upload it again.",
                )
            terminales[residuo] = base
            residuo = base
        if not fila["cadena"]:
            sin_cadena += 1
        x, y, z = fila["xyz"]
        if max(abs(x), abs(y), abs(z)) > 9999.999:
            raise ErrorDeSubida(
                "PQR_COORDENADA_NO_REPRESENTABLE",
                f"Una coordenada de la línea {numero_linea} está fuera del rango del formato PDB (±9999,999 Å).",
                f"A coordinate on line {numero_linea} is outside the PDB format range (±9999.999 Å).",
            )
        serial = serial % 99999 + 1
        cadena = fila["cadena"] or "A"
        parcial = (f"{registro:<6}{serial:>5} {_campo_nombre(fila['nombre'], registro, residuo)} {residuo:>3} "
                   f"{cadena}{int(fila['numero']):>4}{fila['insercion'] or ' '}   {x:8.3f}{y:8.3f}{z:8.3f}"
                   f"{1.0:6.2f}{0.0:6.2f}")
        elemento = elemento_desde_el_nombre(parcial)
        salida.append(parcial + f"          {elemento:>2}")
        atomos += 1
        cargas_netas += fila["carga"]
    if parches:
        resumen = "; ".join(f"«{nombre}» en {len(sitios)} sitio(s)" for nombre, sitios in sorted(parches.items()))
        resumen_en = "; ".join(f"«{nombre}» at {len(sitios)} site(s)" for nombre, sitios in sorted(parches.items()))
        ejemplos = sorted({f"{c}:{n}" for sitios in parches.values() for c, n in sitios})[:5]
        raise ErrorDeSubida(
            "PQR_PARCHES_CHARMM",
            f"«{nombre_archivo}» trae parches de CHARMM escritos como residuos aparte ({resumen}; por ejemplo "
            f"{', '.join(ejemplos)}). Sus átomos (OT1, OT2, 1CB…) no coinciden con los nombres estándar y el PDB "
            "clásico no los representa, así que MolDesign no los reordena ni los adivina. Genera el PQR con otro "
            "campo de fuerzas (por ejemplo --ffout=AMBER en PDB2PQR) o sube el PDB protonado con nombres estándar.",
            f"«{nombre_archivo}» has CHARMM patches written as separate residues ({resumen_en}; for example "
            f"{', '.join(ejemplos)}). Their atoms (OT1, OT2, 1CB…) do not match the standard names and classic PDB "
            "cannot represent them, so MolDesign neither reorders nor guesses them. Generate the PQR with another "
            "force field (for example --ffout=AMBER in PDB2PQR) or upload the protonated PDB with standard names.",
            parches={nombre: sorted(f"{c}:{n}" for c, n in sitios) for nombre, sitios in parches.items()},
        )
    if atomos == 0:
        raise ErrorDeSubida(
            "PQR_SIN_ATOMOS",
            f"«{nombre_archivo}» no contiene ningún átomo (líneas ATOM o HETATM).",
            f"«{nombre_archivo}» contains no atoms (ATOM or HETATM lines).",
        )
    salida.append("END")
    informe = {
        "origen_formato": "pqr",
        "atomos": atomos,
        "cargas_y_radios_descartados": atomos,
        "carga_neta_del_pqr": round(cargas_netas, 3),
        "motivo_del_descarte": "Vina no usa las cargas del PQR: la carga parcial del PDBQT la calcula Meeko.",
        "atomos_sin_cadena": sin_cadena,
        "ocupacion_y_factor_b": "el PQR no los trae: se escriben 1,00 y 0,00",
        "residuos_terminales_reducidos": terminales,
    }
    return "\n".join(salida) + "\n", informe
