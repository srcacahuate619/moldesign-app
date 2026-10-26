"""Dos arreglos que un PDB real necesita antes de entrar en el pipeline, siempre declarados.

* **Varios modelos** (un conjunto de RMN, o un PDB con ``MODEL`` repetido): el filtro de cadenas conservaba
  los átomos de TODOS los modelos y Meeko recibía cada residuo varias veces y fallaba. Se usa el modelo 1 y se
  declara, igual que hace la conversión de mmCIF.
* **Sin columna de elemento** (cols. 77–78 en blanco): Meeko lee el elemento de esa columna y falla sin ella.
  El elemento se infiere del nombre del átomo con la convención del PDB (la posición del nombre en las columnas
  13–16 distingue ``CA`` calcio de `` CA `` carbono alfa) y se cuenta cuántos se infirieron.

Un PDB que no necesita ninguno de los dos sale **byte a byte igual** (el receptor preparado de un PDB bien
formado no cambia: es la paridad con el catálogo y con el mmCIF).
"""

from __future__ import annotations

from typing import Any

#: Elementos de dos letras que aparecen como iones o heteroátomos; ``HG`` se omite a propósito: en un
#: HETATM suele ser el hidrógeno gamma de un residuo modificado, no un mercurio.
_DOS_LETRAS = frozenset({
    "CL", "BR", "FE", "ZN", "MG", "MN", "CU", "NA", "CA", "CO", "NI", "CD", "SE", "SR", "AU", "PT", "PB",
    "AL", "SI", "LI", "BE", "KR", "XE", "IR", "OS", "GD", "CS", "RB", "BA", "TL", "AG", "PD", "SN", "SB",
    "TE", "AS", "CR", "MO", "TI", "ZR", "LA", "CE", "EU", "YB", "LU", "RU", "RH", "RE", "W ", "HF",
})


def elemento_desde_el_nombre(linea: str) -> str:
    """El elemento de un registro ATOM/HETATM según su nombre, o ``""`` si no se puede decidir."""
    nombre = linea[12:16]
    letras = "".join(c for c in nombre if c.isalpha()).upper()
    if not letras:
        return ""
    if linea.startswith("HETATM") and nombre[0] != " " and letras[:2] in _DOS_LETRAS:
        return letras[:2]
    return letras[0]


def _modelos(lineas: list[str]) -> int:
    return sum(1 for l in lineas if l.startswith("MODEL"))


#: Nombres de CHARMM que Meeko no conoce. En modo automático MolDesign vuelve a protonar con la receta,
#: así que la histidina pasa a ``HIS`` (Meeko elige el tautómero) y ``WAT`` a ``HOH`` (un agua, que la
#: receta retira). Sin esto, la receta borraba las histidinas ``HSD``. El modo «respetar» tiene su propia
#: traducción, a ``HID``/``HIE``/``HIP``, porque ahí la protonación es la del equipo.
CHARMM_A_PDB = {"HSD": "HIS", "HSE": "HIS", "HSP": "HIS", "WAT": "HOH"}


def nombres_charmm_a_pdb(texto: str) -> tuple[str, list[dict[str, Any]]]:
    """``HSD``/``HSE``/``HSP``/``WAT`` → ``HIS``/``HOH``, con el número de residuos de cada traducción."""
    vistos: dict[str, set[tuple[str, str, str]]] = {}
    salida: list[str] = []
    for linea in texto.split("\n"):
        if linea.startswith(("ATOM", "HETATM")) and len(linea) >= 27:
            nombre = linea[17:20].strip()
            if nombre in CHARMM_A_PDB:
                vistos.setdefault(nombre, set()).add((linea[21:22], linea[22:26], linea[26:27]))
                linea = linea[:17] + f"{CHARMM_A_PDB[nombre]:>3}" + linea[20:]
        salida.append(linea)
    if not vistos:
        return texto, []
    traducciones = [{"original": n, "pdb": CHARMM_A_PDB[n], "residuos": len(claves)}
                    for n, claves in sorted(vistos.items())]
    return "\n".join(salida), traducciones


def normalizar_pdb(texto: str) -> tuple[str, dict[str, Any]]:
    """Devuelve el PDB listo y un informe de lo que se hizo (vacío si no hubo que tocar nada)."""
    lineas = texto.split("\n")
    informe: dict[str, Any] = {}

    modelos = _modelos(lineas)
    if modelos > 1:
        salida: list[str] = []
        vistos = 0
        for linea in lineas:
            if linea.startswith("MODEL"):
                vistos += 1
                continue
            if linea.startswith("ENDMDL"):
                if vistos >= 1:
                    # lo que venga después del primer modelo son los demás; las líneas finales (CONECT,
                    # MASTER, END) se conservan al final
                    break
                continue
            salida.append(linea)
        lineas = [*salida, "END", ""]
        informe["modelos"] = {"en_el_archivo": modelos, "usado": 1}

    inferidos = 0
    resultado: list[str] = []
    for linea in lineas:
        if linea.startswith(("ATOM", "HETATM")) and len(linea) >= 54 and not linea[76:78].strip():
            elemento = elemento_desde_el_nombre(linea)
            if elemento:
                linea = linea[:76].ljust(76) + f"{elemento:>2}" + linea[78:]
                inferidos += 1
        resultado.append(linea)
    if inferidos:
        informe["elementos_inferidos"] = inferidos

    if not informe:
        return texto, {}
    return "\n".join(resultado), informe
