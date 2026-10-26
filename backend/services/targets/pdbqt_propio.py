"""Un PDBQT listo para Vina que sube la persona: se evalúa tal cual, y se audita si trae su origen.

# Qué hace y qué no

La ejecución usa el PDBQT **sin tocarlo**: ni lo vuelve a protonar ni lo pasa por
Meeko. Eso es lo que el investigador pidió al subir un receptor ya preparado. A
cambio, MolDesign sólo puede afirmar lo que está en el archivo:

* sin la estructura de origen sólo se registran el hash, las cadenas, los
  residuos y los tipos de átomo. Lo que se retiró, los huecos y las cadenas
  laterales truncadas **no se pueden saber** y quedan en ``null`` con su motivo;
* con la estructura de origen se compara el PDBQT contra ella y la auditoría es la
  misma de siempre (diff de especies, huecos, truncadas, residuos ausentes). Antes
  se comprueba que los dos archivos describen el mismo receptor.

# Tipos de átomo

La lista de tipos admitidos sale de una prueba con el Vina 1.2.7 que viaja en el
instalador (``docs/versions/1.0.2_cambios.md``): acepta ``Zn``, ``Fe``, ``Mg``…
en esa grafía y **rechaza** ``ZN``, ``CL``, ``NS`` u ``OS``. Un tipo desconocido se
rechaza aquí, con su línea, en vez de dejar que Vina falle durante la corrida.
"""

from __future__ import annotations

import hashlib
import math
import statistics
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from services.targets.errores_subida import ErrorDeSubida

#: Medido con Vina 1.2.7 (tools/vina/vina.exe): aceptados tal cual, sensibles a mayúsculas.
TIPOS_ACEPTADOS = frozenset({
    "C", "A", "N", "NA", "OA", "SA", "S", "HD", "H", "P", "F", "I", "Cl", "Br",
    "Zn", "Fe", "Mg", "Ca", "Mn", "Cu", "Na", "K", "Ni", "Co", "Cd", "Hg", "Si", "At",
    "G0", "W",
})

#: Registros que sólo aparecen en un ligando o en residuos flexibles, nunca en un receptor rígido.
_REGISTROS_FLEXIBLES = ("ROOT", "ENDROOT", "BRANCH", "ENDBRANCH", "TORSDOF", "BEGIN_RES", "END_RES")

_AGUAS = frozenset({"HOH", "WAT", "DOD", "TIP", "SOL"})

#: Nombre de residuo → clase de aminoácido, para comparar un PDBQT con su origen aunque
#: la protonación cambie el nombre (HIS ↔ HID/HIE/HIP, CYS ↔ CYX…).
_CLASE_DE_RESIDUO = {
    "HID": "HIS", "HIE": "HIS", "HIP": "HIS", "HSD": "HIS", "HSE": "HIS", "HSP": "HIS", "HIS": "HIS",
    "CYX": "CYS", "CYM": "CYS", "CYS": "CYS",
    "ASH": "ASP", "ASP": "ASP", "GLH": "GLU", "GLU": "GLU", "LYN": "LYS", "LYS": "LYS",
    "MSE": "MET", "MET": "MET",
}

#: Un PDBQT y su origen "corresponden" si casi todos los residuos casan y las
#: coordenadas pesadas apenas se han movido. Medido sobre 8HFI: 0 Å.
COBERTURA_MINIMA = 0.90
DESPLAZAMIENTO_MEDIANO_MAXIMO_A = 0.5


@dataclass
class ResumenPdbqt:
    """Lo que se puede saber de un PDBQT sin su estructura de origen."""

    atomos: int = 0
    pesados: int = 0
    hidrogenos: int = 0
    cadenas: list[str] = field(default_factory=list)
    residuos: int = 0
    tipos: dict[str, int] = field(default_factory=dict)
    hetero: dict[str, int] = field(default_factory=dict)
    cadenas_en_blanco: bool = False
    avisos: list[dict[str, Any]] = field(default_factory=list)

    def como_dict(self) -> dict[str, Any]:
        return {
            "atomos": self.atomos, "pesados": self.pesados, "hidrogenos_polares": self.hidrogenos,
            "cadenas": self.cadenas, "cadenas_en_blanco": self.cadenas_en_blanco,
            "residuos": self.residuos, "tipos_de_atomo": dict(sorted(self.tipos.items())),
            "hetero": dict(sorted(self.hetero.items())), "avisos": self.avisos,
        }


def sha256_de(datos: bytes) -> str:
    return hashlib.sha256(datos).hexdigest()


def _tipo(linea: str) -> str:
    """El tipo de átomo AutoDock: columnas 78-79, o el último campo si la línea se desalineó."""
    if len(linea) >= 79 and linea[77:79].strip():
        return linea[77:79].strip()
    partes = linea.split()
    return partes[-1] if len(partes) >= 11 else ""


def analizar_pdbqt(texto: str) -> ResumenPdbqt:
    """Valida un PDBQT de receptor y resume lo que contiene. Lanza ``ErrorDeSubida`` si no sirve."""
    resumen = ResumenPdbqt()
    tipos: Counter[str] = Counter()
    hetero: Counter[str] = Counter()
    cadenas: set[str] = set()
    residuos: set[tuple[str, str, str]] = set()
    desconocidos: dict[str, int] = {}
    cortas: list[int] = []
    sin_coordenadas: list[int] = []
    sodios: list[str] = []
    modelos = 0
    for numero, linea in enumerate(texto.splitlines(), start=1):
        registro = linea[:6].strip()
        if registro == "MODEL":
            modelos += 1
            continue
        if linea.startswith(_REGISTROS_FLEXIBLES):
            raise ErrorDeSubida(
                "PDBQT_NO_ES_RIGIDO",
                f"La línea {numero} del PDBQT es «{linea.split()[0]}»: eso es propio de un ligando o de residuos "
                "flexibles, no de un receptor rígido. Exporta el receptor rígido (sin ROOT, BRANCH ni TORSDOF) "
                "con tu herramienta de preparación.",
                f"Line {numero} of the PDBQT is «{linea.split()[0]}», which belongs to a ligand or to flexible "
                "residues, not to a rigid receptor. Export the rigid receptor (no ROOT, BRANCH or TORSDOF) "
                "from your preparation tool.",
            )
        if registro not in ("ATOM", "HETATM"):
            continue
        if len(linea) < 66:
            cortas.append(numero)
            continue
        try:
            xyz = tuple(float(linea[i:i + 8]) for i in (30, 38, 46))
        except ValueError:
            sin_coordenadas.append(numero)
            continue
        if not all(math.isfinite(v) for v in xyz):
            sin_coordenadas.append(numero)
            continue
        tipo = _tipo(linea)
        if tipo not in TIPOS_ACEPTADOS:
            desconocidos.setdefault(tipo or "(vacío)", numero)
            continue
        resumen.atomos += 1
        tipos[tipo] += 1
        if tipo in ("H", "HD"):
            resumen.hidrogenos += 1
        else:
            resumen.pesados += 1
        nombre_residuo = linea[17:20].strip()
        cadena = linea[21:22].strip()
        if cadena:
            cadenas.add(cadena)
        else:
            resumen.cadenas_en_blanco = True
        residuos.add((cadena, linea[22:26].strip(), linea[26:27].strip()))
        if registro == "HETATM" or nombre_residuo in _AGUAS:
            hetero[nombre_residuo] += 1
        if nombre_residuo == "NA" and linea[12:16].strip() == "NA" and tipo == "NA":
            sodios.append(f"{cadena or '-'}:{linea[22:26].strip()}")
    if modelos > 1:
        raise ErrorDeSubida(
            "PDBQT_VARIOS_MODELOS",
            f"El PDBQT trae {modelos} registros MODEL. Un receptor tiene un solo modelo: deja el que quieras "
            "acoplar y vuelve a subirlo.",
            f"The PDBQT has {modelos} MODEL records. A receptor has a single model: keep the one you want to "
            "dock and upload it again.",
        )
    if cortas or sin_coordenadas:
        primera = (cortas or sin_coordenadas)[0]
        raise ErrorDeSubida(
            "PDBQT_LINEA_ILEGIBLE",
            f"{len(cortas) + len(sin_coordenadas)} línea(s) ATOM/HETATM del PDBQT no se pueden leer "
            f"(la primera es la {primera}): faltan columnas o las coordenadas no son números. "
            "Vuelve a exportar el receptor desde tu herramienta de preparación.",
            f"{len(cortas) + len(sin_coordenadas)} ATOM/HETATM line(s) of the PDBQT cannot be read "
            f"(the first is line {primera}): columns are missing or the coordinates are not numbers. "
            "Export the receptor again from your preparation tool.",
        )
    if desconocidos:
        lista = ", ".join(f"{t} (línea {n})" for t, n in sorted(desconocidos.items()))
        lista_en = ", ".join(f"{t} (line {n})" for t, n in sorted(desconocidos.items()))
        raise ErrorDeSubida(
            "PDBQT_TIPO_NO_SOPORTADO",
            f"El PDBQT usa tipos de átomo que AutoDock Vina 1.2.7 no admite: {lista}. "
            "Vina distingue mayúsculas (Zn, no ZN; Cl, no CL) y no tiene NS, OS ni HS. "
            "Corrige los tipos o vuelve a exportar el receptor.",
            f"The PDBQT uses atom types that AutoDock Vina 1.2.7 does not accept: {lista_en}. "
            "Vina is case sensitive (Zn, not ZN; Cl, not CL) and has no NS, OS or HS. "
            "Fix the types or export the receptor again.",
        )
    if resumen.atomos == 0:
        raise ErrorDeSubida(
            "PDBQT_SIN_ATOMOS",
            "El PDBQT no contiene ningún átomo (líneas ATOM o HETATM). Comprueba que subiste el receptor y "
            "no un archivo vacío o de otro formato.",
            "The PDBQT has no atoms (ATOM or HETATM lines). Check that you uploaded the receptor and not an "
            "empty file or one in another format.",
        )
    if sodios:
        raise ErrorDeSubida(
            "PDBQT_SODIO_COMO_NITROGENO",
            f"El PDBQT trae un residuo NA con átomo NA y tipo NA ({', '.join(sodios[:5])}): en PDBQT el tipo NA "
            "es un nitrógeno aceptor, no un sodio. Vina lo trataría como un nitrógeno fantasma. Retira el ion "
            "o cámbiale el tipo a «Na» (sodio) y vuelve a subirlo.",
            f"The PDBQT has an NA residue with an NA atom of type NA ({', '.join(sodios[:5])}): in PDBQT the NA "
            "type is an acceptor nitrogen, not sodium. Vina would treat it as a phantom nitrogen. Remove the "
            "ion or change its type to «Na» (sodium) and upload it again.",
        )
    resumen.tipos = dict(tipos)
    resumen.hetero = dict(hetero)
    resumen.cadenas = sorted(cadenas)
    resumen.residuos = len(residuos)
    if resumen.pesados < 100:
        resumen.avisos.append({
            "codigo": "PDBQT_POCOS_ATOMOS",
            "es": f"El PDBQT sólo tiene {resumen.pesados} átomos pesados: parece un fragmento, no un receptor.",
            "en": f"The PDBQT only has {resumen.pesados} heavy atoms: it looks like a fragment, not a receptor.",
        })
    if resumen.hidrogenos == 0:
        resumen.avisos.append({
            "codigo": "PDBQT_SIN_HIDROGENOS_POLARES",
            "es": "El PDBQT no tiene hidrógenos polares (HD): Vina no verá donadores de puente de hidrógeno.",
            "en": "The PDBQT has no polar hydrogens (HD): Vina will not see hydrogen bond donors.",
        })
    if resumen.cadenas_en_blanco:
        resumen.avisos.append({
            "codigo": "PDBQT_CADENA_EN_BLANCO",
            "es": "Hay átomos sin identificador de cadena; la cadena que declares es la que se registra.",
            "en": "Some atoms have no chain identifier; the chain you declare is the one that is recorded.",
        })
    return resumen


# ── Correspondencia con la estructura de origen ───────────────────────────


def _es_hidrogeno(linea: str, *, pdbqt: bool) -> bool:
    if pdbqt:
        return _tipo(linea) in ("H", "HD")
    elemento = linea[76:78].strip().upper() if len(linea) >= 78 else ""
    if elemento:
        return elemento in ("H", "D")
    return linea[12:16].strip().lstrip("0123456789")[:1] == "H"


def _residuos(texto: str, *, pdbqt: bool) -> dict[tuple[str, str, str], dict[str, Any]]:
    """Residuos de PROTEÍNA (registros ATOM) con sus átomos pesados, por (cadena, número, inserción)."""
    filas: dict[tuple[str, str, str], dict[str, Any]] = {}
    for linea in texto.splitlines():
        if not linea.startswith("ATOM") or len(linea) < 54:
            continue
        if linea[16:17] not in (" ", "A", ""):
            continue
        if _es_hidrogeno(linea, pdbqt=pdbqt):
            continue
        clave = (linea[21:22].strip() or "A", linea[22:26].strip(), linea[26:27].strip())
        try:
            xyz = tuple(float(linea[i:i + 8]) for i in (30, 38, 46))
        except ValueError:
            continue
        nombre = linea[17:20].strip()
        fila = filas.setdefault(clave, {"nombre": nombre, "atomos": {}})
        fila["atomos"].setdefault(linea[12:16].strip(), xyz)
    return filas


def _clase(nombre: str) -> str:
    return _CLASE_DE_RESIDUO.get(nombre, nombre)


def correspondencia(origen: str, pdbqt: str) -> dict[str, Any]:
    """Mide si ``pdbqt`` describe el mismo receptor que ``origen``. No lanza: devuelve la medida."""
    del_pdbqt = _residuos(pdbqt, pdbqt=True)
    del_origen = _residuos(origen, pdbqt=False)
    coinciden = 0
    desplazamientos: list[float] = []
    for clave, fila in del_pdbqt.items():
        otro = del_origen.get(clave)
        if otro is None or _clase(otro["nombre"]) != _clase(fila["nombre"]):
            continue
        coinciden += 1
        for nombre_atomo, xyz in fila["atomos"].items():
            par = otro["atomos"].get(nombre_atomo)
            if par is not None:
                desplazamientos.append(math.dist(xyz, par))
    total = len(del_pdbqt)
    cobertura = coinciden / total if total else 0.0
    mediano = statistics.median(desplazamientos) if desplazamientos else None
    return {
        "residuos_del_pdbqt": total,
        "residuos_que_coinciden": coinciden,
        "cobertura": round(cobertura, 4),
        "atomos_comparados": len(desplazamientos),
        "desplazamiento_mediano_A": round(mediano, 4) if mediano is not None else None,
        "corresponde": bool(
            total and cobertura >= COBERTURA_MINIMA and mediano is not None
            and mediano <= DESPLAZAMIENTO_MEDIANO_MAXIMO_A
        ),
    }


def exigir_correspondencia(origen: str, pdbqt: str) -> dict[str, Any]:
    medida = correspondencia(origen, pdbqt)
    if medida["corresponde"]:
        return medida
    if medida["residuos_del_pdbqt"] == 0:
        detalle_es = "el PDBQT no tiene residuos de proteína que comparar"
        detalle_en = "the PDBQT has no protein residues to compare"
    elif medida["cobertura"] < COBERTURA_MINIMA:
        detalle_es = (f"sólo {medida['residuos_que_coinciden']} de {medida['residuos_del_pdbqt']} residuos del PDBQT "
                      "casan con el origen por cadena, número y nombre (se exige el "
                      f"{int(COBERTURA_MINIMA * 100)} %)")
        detalle_en = (f"only {medida['residuos_que_coinciden']} of {medida['residuos_del_pdbqt']} PDBQT residues "
                      "match the source by chain, number and name (at least "
                      f"{int(COBERTURA_MINIMA * 100)} % is required)")
    else:
        detalle_es = (f"los átomos pesados están a {medida['desplazamiento_mediano_A']} Å de mediana de sus "
                      f"posiciones en el origen (el máximo es {DESPLAZAMIENTO_MEDIANO_MAXIMO_A} Å)")
        detalle_en = (f"heavy atoms sit a median {medida['desplazamiento_mediano_A']} Å from their positions in the "
                      f"source (the maximum is {DESPLAZAMIENTO_MEDIANO_MAXIMO_A} Å)")
    raise ErrorDeSubida(
        "PDBQT_NO_CORRESPONDE_AL_ORIGEN",
        f"El PDBQT y la estructura de origen no parecen el mismo receptor: {detalle_es}. "
        "Sube el origen del que salió este PDBQT, o súbelo sin origen para evaluarlo sin auditoría.",
        f"The PDBQT and the source structure do not look like the same receptor: {detalle_en}. "
        "Upload the source this PDBQT came from, or upload it without a source to evaluate it without an audit.",
        correspondencia=medida,
    )
