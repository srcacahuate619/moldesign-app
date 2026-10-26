"""Distancias al ligando y decisiones del receptor que la corrida no serializó.

# Por qué existe

La preparación mide «junto al sitio» como 6 Å desde la SUPERFICIE de la caja.
Con un lado mediano de 28,7 Å eso abarca casi toda la proteína: en 4NC3 bloqueaba
un hueco a 20 Å de la serotonina acoplada, y de 70 a 347 aguas listadas por
corrida sólo 1 a 10 estaban a ≤ 4 Å del ligando (auditoría del 2026-10-10). Para
un cálculo de energía libre lo que cuenta es la distancia al LIGANDO.

# De dónde sale cada coordenada, sin reconstruir nada

- La pose principal: el bloque PDBQT del rango 1 que la corrida guardó.
- El ligando del cristal y las especies retiradas: el crudo depositado, con la
  MISMA unidad biológica que generó la preparación. Antes de usarlo se
  recalcula el hash de la receta del receptor con ese crudo, con la receta del
  camino por el que se preparó (ver `origen_comprobado`); si no coincide con
  el de la corrida, no es el archivo con el que se preparó y no se mide nada.
- Qué residuos llegaron al receptor: el PDBQT de la corrida, por su SHA-256.
- Qué plantilla aplicó Meeko a cada His y Cys: el informe de la preparación,
  sólo si su `receptor_sha256` es el de la corrida.
- Si el receptor es de membrana y si el ligando del cristal está unido a la
  proteína: la secuencia de las cadenas del receptor y los registros HEADER y
  LINK del mismo crudo comprobado.
- Qué residuos no estándar lleva el receptor (metales, cofactores,
  fosforresiduos): el PDBQT de la corrida. No necesita el crudo, así que se
  mide aunque lo demás no se pueda.

Si falta cualquiera de esas piezas, `medido` es falso y `razon` dice cuál: la
auditoría sigue midiendo desde la caja y lo declara. Nunca se mezcla un criterio
con el otro.

Es trabajo de disco y CPU: el router lo llama con `asyncio.to_thread`.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

#: Metales, cofactores, otras especies y proteína fuera del receptor: primera y
#: segunda esfera del ligando.
UMBRAL_ESPECIE_A = 6.0
#: Aguas que pueden puentear al ligando (enlace de hidrógeno ≤ 3,5 Å, con margen).
UMBRAL_AGUA_A = 4.0
#: Enlace de hidrógeno entre átomos pesados (donador–aceptor). Un agua a esta distancia
#: del ligando y de la proteína puede puentearlos; un nitrógeno de una His, donarle o
#: aceptarle un hidrógeno al ligando.
UMBRAL_PUENTE_H_A = 3.5
#: Más cerca de un átomo del ligando, el agua ocupa su sitio: la pose la desplaza.
UMBRAL_SOLAPAMIENTO_A = 2.5
#: Un N, O o S del ligando del cristal a esta distancia de un metal lo coordina (la medida de
#: `scripts/medir_metales_del_sitio.py`: 43 de los 52 iones a ≤ 6 Å en el catálogo).
UMBRAL_LIGANDO_METAL_A = 2.8
#: Un cofactor sin metal no se coordina: cuenta como en contacto si un átomo suyo está a esta distancia del ligando del cristal.
UMBRAL_CONTACTO_COFACTOR_A = 4.0
#: Elementos (columnas 77-78 del PDB) que cuentan como metal, también dentro de un cofactor (el Fe del hemo).
METALES_PDB = frozenset({"ZN", "MG", "CA", "K", "NA", "MN", "FE", "CU", "CO", "NI", "CD", "HG"})
#: Residuos: un extremo de hueco o una cadena lateral truncada a esta distancia
#: puede alcanzar al ligando (una Arg mide unos 7 Å desde el Cα).
UMBRAL_RESIDUO_A = 8.0
#: S–S de un puente disulfuro (≈ 2,05 Å) con margen de resolución.
_DISULFURO_A = 2.5
#: Enlace peptídico C–N; por encima, la cadena está cortada (como `preparer`).
_ENLACE_PEPTIDICO_A = 2.0

Xyz = tuple[float, float, float]
_SIN_CARGA = re.compile(r"[0-9+-]+$")
_HIDROGENOS = {"H", "D", "HD", "HS"}


@dataclass
class ContextoEstructural:
    medido: bool
    razon: str | None = None
    #: «Pose top-1 y ligando del cristal TSN A:401», o sólo la pose.
    referencia: str | None = None
    #: (cadena, número, inserción, nombre) → Å al ligando, de cada especie de `near_site`.
    especies: dict[tuple[str, str, str, str], float] = field(default_factory=dict)
    #: Las mismas especies → Å al ligando del cristal sólo, sin la pose. Los metales y cofactores se juzgan con
    #: ésta cuando existe: el mínimo con la pose cambiaba con la semilla (1RKP: 5,17 Å por la pose, 6,52 Å el cristal).
    especies_al_cristal: dict[tuple[str, str, str, str], float] = field(default_factory=dict)
    #: Metales y cofactores en contacto con el ligando del cristal: un metal coordinado → «N21–ZN 2.05 Å»; un cofactor sin metal
    #: a ≤ UMBRAL_CONTACTO_COFACTOR_A → «contacto 3.40 Å». None si no
    #: hay ligando del cristal con el que mirarlo (receptor propio, ligando ausente del depósito): no se sabe.
    coordinadas: dict[tuple[str, str, str, str], str] | None = None
    #: (cadena, «RES n» anterior, «RES n» siguiente) → Å al ligando del extremo más cercano.
    huecos: dict[tuple[str, str, str], float] = field(default_factory=dict)
    #: El mismo hueco → rangos de las poses guardadas a ≤ UMBRAL_RESIDUO_A de un extremo. La pose 1
    #: ya cuenta en `huecos`; esto mira también las demás, que la corrida ofrece al investigador.
    huecos_poses: dict[tuple[str, str, str], list[int]] = field(default_factory=dict)
    #: Cuántas poses con coordenadas guardó la corrida (las que mira `huecos_poses`).
    poses_medidas: int = 0
    #: (cadena, número, inserción) → Å al ligando de cada cadena lateral truncada.
    truncadas: dict[tuple[str, str, str], float] = field(default_factory=dict)
    #: cadena → residuos de proteína fuera del receptor a ≤ UMBRAL_ESPECIE_A del ligando.
    excluidas: dict[str, int] | None = None
    #: [(«A:131», entrada, plantilla, Å)] de His, y de estados no estándar, a ≤ UMBRAL_RESIDUO_A.
    plantillas: list[tuple[str, str, str, float]] | None = None
    #: «A:131» → Å de ND1 o NE2 (el más cercano) al ligando, de cada His de `plantillas`.
    anillos_his: dict[str, float] = field(default_factory=dict)
    #: (cadena, número, inserción, nombre) → Å al N u O más cercano de la proteína del receptor,
    #: de cada agua de `near_site` a ≤ UMBRAL_AGUA_A del ligando.
    aguas_a_la_proteina: dict[tuple[str, str, str, str], float] = field(default_factory=dict)
    #: Las mismas aguas → Å al N u O más cercano del ligando (pose top-1 o ligando del cristal).
    aguas_al_ligando_polar: dict[tuple[str, str, str, str], float] = field(default_factory=dict)
    #: [«A:18–A:45»] puentes S–S de la estructura que el receptor no conserva como CYX.
    disulfuros_rotos: list[str] | None = None
    disulfuros_totales: int | None = None
    #: [«A:18–A:45»] puentes candidatos por geometría cuyo estado químico en el receptor no
    #: se pudo leer: falta la plantilla de una o de las dos cisteínas (SCI-C-001).
    disulfuros_sin_evaluar: list[str] | None = None
    #: [(«A:45 LYS», «A 0.60/B 0.40 → A», Å)] conformaciones alternativas cerca del ligando.
    altlocs: list[tuple[str, str, float]] = field(default_factory=list)
    #: Recorte multicadena: radio, residuos y cortes que crea. None si no hubo recorte.
    recorte: dict[str, Any] | None = None
    #: cadena del receptor → segmentos transmembrana probables (hidropatía de Kyte-Doolittle).
    segmentos_tm: dict[str, int] | None = None
    #: Clasificación del registro HEADER del depósito («MEMBRANE PROTEIN», «HYDROLASE»…).
    clasificacion: str | None = None
    #: Lípidos y detergentes de cristalización de membrana presentes en el depósito.
    lipidos: list[str] = field(default_factory=list)
    #: [«TSN A:401 C12–CYS A:481 SG (1.8 Å)»] enlaces LINK del ligando del cristal con la
    #: proteína; None si la corrida no declaró ligando del cristal.
    enlaces_covalentes: list[str] | None = None
    #: residuo → número de residuos del receptor fuera de los aminoácidos estándar; None
    #: si el PDBQT de la corrida no se pudo leer por su SHA-256.
    no_estandar: dict[str, int] | None = None
    #: [(«A:388», «NE2», «FE HEM A:601», Å, lleva H)] His del receptor preparado con un N del anillo a
    #: ≤ UMBRAL_COORDINACION_A de un metal conservado; None si el PDBQT no se pudo leer.
    his_al_metal: list[tuple[str, str, str, float, bool]] | None = None
    #: [(«A:442», «SG», «FE HEM A:601», Å, lleva HG)] Cys del receptor preparado cuyo SG está a
    #: ≤ UMBRAL_COORDINACION_A de un metal conservado; None si el PDBQT no se pudo leer.
    cys_al_metal: list[tuple[str, str, str, float, bool]] | None = None
    #: «B49 A:9000» si el ligando del cristal que sirve de referencia figura en el REMARK 610 (le faltan átomos).
    cristal_incompleto: str | None = None
    #: [(«A:694 THR», «SEE REMARK 999», Å o None)] diferencias que el depósito declara con su secuencia de referencia
    #: (SEQADV), sin etiquetas de expresión ni artefactos de clonación; None si no se midió.
    secuencia_modificada: list[tuple[str, str, float | None]] | None = None
    #: El texto del REMARK 999 (secuencia), si lo hay: «RESIDUES 694-753 DELETED, REPLACED WITH TS».
    remark_999: str | None = None
    #: [(«A:725 GLU», «» si es el residuo entero (REMARK 475) o «CG CD CE NZ» (REMARK 480), Å o None)] ocupación cero.
    ocupacion_cero: list[tuple[str, str, float | None]] | None = None


def no_medido(razon: str) -> ContextoEstructural:
    return ContextoEstructural(medido=False, razon=razon)


# ── Lectura de coordenadas ───────────────────────────────────────────


@dataclass(frozen=True)
class _Atomo:
    registro: str
    cadena: str
    numero: str
    insercion: str
    residuo: str
    nombre: str
    altloc: str
    ocupacion: float
    xyz: Xyz
    #: Columnas 77-79: el elemento en un PDB, el tipo de AutoDock en un PDBQT («OA», «NA», «C»).
    elemento: str = ""

    @property
    def polar(self) -> bool:
        """N u O: lo que puede dar o aceptar un puente de hidrógeno. Sin columna, por el nombre."""
        return (self.elemento or self.nombre)[:1] in ("N", "O")

    @property
    def clave(self) -> tuple[str, str, str]:
        return self.cadena, self.numero, self.insercion

    @property
    def clave_con_nombre(self) -> tuple[str, str, str, str]:
        """Un agua y un ligando pueden compartir cadena y número (3GEN: B43 y HOH A:1)."""
        return self.cadena, self.numero, self.insercion, self.residuo


def _atomos(texto: str, *, pesados: bool = True) -> list[_Atomo]:
    salida = []
    for linea in texto.splitlines():
        if not linea.startswith(("ATOM", "HETATM")) or len(linea) < 54:
            continue
        nombre = linea[12:16].strip()
        # Columnas 77-78 son el elemento en un PDB y la 79-80 su carga («MG2+», «ZN0» en 5E92 y 9GKV, «H0» en los H); en un
        # PDBQT, 78-79 son el tipo de AutoDock («OA», «HD»). Se leen 77-79 y se quita la carga: sin eso el Mg y el Zn no
        # contaban como metal y los H «H0» como átomos pesados (MET-02-SEMILLA).
        elemento = _SIN_CARGA.sub("", linea[76:79].strip().upper()) if len(linea) >= 77 else ""
        if pesados and (elemento in _HIDROGENOS or (not elemento and nombre[:1] in ("H", "D"))):
            continue
        try:
            xyz = (float(linea[30:38]), float(linea[38:46]), float(linea[46:54]))
            ocupacion = float(linea[54:60]) if len(linea) >= 60 and linea[54:60].strip() else 1.0
        except ValueError:
            continue
        salida.append(_Atomo(linea[:6].strip(), linea[21:22].strip() or "A", linea[22:26].strip(),
                             linea[26:27].strip(), linea[17:20].strip(), nombre, linea[16:17].strip(),
                             ocupacion, xyz, elemento))
    return salida


def _distancia(a: list[Xyz], referencias: list[list[Xyz]]) -> float | None:
    mejores = [min(math.dist(p, q) for p in a for q in ref) for ref in referencias if ref and a]
    return round(min(mejores), 2) if mejores else None


def _coordinacion(especie: list[_Atomo], donadores: list[_Atomo]) -> str | None:
    """«N21–ZN 2.05 Å» si un N, O o S del ligando del cristal coordina un metal de la especie; si no, None."""
    mejor = None
    for m in especie:
        # Sin columna de elemento sólo cuenta un ion suelto (ZN ZN): el NA del hemo es un nitrógeno, no sodio.
        if (m.elemento or (m.nombre.upper() if m.nombre == m.residuo else "")) not in METALES_PDB:
            continue
        for d in donadores:
            r = math.dist(m.xyz, d.xyz)
            if r <= UMBRAL_LIGANDO_METAL_A and (mejor is None or r < mejor[0]):
                mejor = (r, d.nombre, m.nombre)
    return f"{mejor[1]}–{mejor[2]} {mejor[0]:.2f} Å" if mejor else None


def _numero(texto: str) -> tuple[str, str]:
    """«ALA 197» o «ALA 197A» → («197», «A»)."""
    final = texto.split()[-1]
    cuerpo = final.rstrip("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    return cuerpo, final[len(cuerpo):]


# ── La medida ────────────────────────────────────────────────────────


def _poses(eval_result: Any) -> dict[int, list[_Atomo]]:
    """Rango → átomos pesados de cada pose guardada con su bloque PDBQT."""
    salida: dict[int, list[_Atomo]] = {}
    for pose in getattr(eval_result, "docking_poses", None) or []:
        rango = pose.get("rank") if isinstance(pose, dict) else getattr(pose, "rank", None)
        bloque = pose.get("pdbqt_block") if isinstance(pose, dict) else getattr(pose, "pdbqt_block", None)
        try:
            rango = int(rango)
        except (TypeError, ValueError):
            continue
        if isinstance(bloque, str) and (atomos := _atomos(bloque)):
            salida[rango] = atomos
    return salida


def _pose_principal(eval_result: Any) -> list[_Atomo]:
    poses = getattr(eval_result, "docking_poses", None) or []
    for pose in poses:
        rango = pose.get("rank") if isinstance(pose, dict) else getattr(pose, "rank", None)
        bloque = pose.get("pdbqt_block") if isinstance(pose, dict) else getattr(pose, "pdbqt_block", None)
        if str(rango) == "1" and isinstance(bloque, str):
            return _atomos(bloque)
    return []


def _leer_sellado(logico: str | None, sha256: str | None) -> bytes | None:
    from utils.local_storage import path_for

    if not isinstance(logico, str) or not isinstance(sha256, str) or len(sha256) != 64:
        return None
    try:
        datos = path_for(logico).read_bytes()
    except (OSError, ValueError):
        return None
    return datos if hashlib.sha256(datos).hexdigest() == sha256 else None


#: Escala de hidropatía de Kyte y Doolittle (1982, J. Mol. Biol. 157:105).
_HIDROPATIA = {
    "ALA": 1.8, "ARG": -4.5, "ASN": -3.5, "ASP": -3.5, "CYS": 2.5, "GLN": -3.5, "GLU": -3.5, "GLY": -0.4,
    "HIS": -3.2, "ILE": 4.5, "LEU": 3.8, "LYS": -3.9, "MET": 1.9, "PHE": 2.8, "PRO": -1.6, "SER": -0.8,
    "THR": -0.7, "TRP": -0.9, "TYR": -1.3, "VAL": 4.2, "MSE": 1.9,
}
#: Ventana y umbral del criterio de Kyte-Doolittle para hélices transmembrana.
VENTANA_TM, UMBRAL_TM = 19, 1.6
#: Lípidos y detergentes típicos de proteínas de membrana cristalizadas (LCP, micelas).
#: No entra el palmitato (PLM): en la albúmina o en un CYP es un ligando de una proteína soluble.
_LIPIDOS_DE_MEMBRANA = frozenset({
    "OLC", "OLA", "OLB", "MPG", "CLR", "Y01", "LDA", "BOG", "LMT", "DMU", "LMN", "UND",
    "PCW", "POV", "PEE", "PLC", "CDL", "LHG", "PGV", "PTY", "SOG", "D10", "D12",
})
#: Un enlace LINK más largo no es covalente (coordinación o puente de hidrógeno).
_ENLACE_COVALENTE_A = 2.3
_AMINOACIDOS = frozenset(_HIDROPATIA) | {"HID", "HIE", "HIP", "CYX", "CYM", "ASH", "GLH", "LYN"}


def segmentos_transmembrana(secuencia: list[str]) -> int:
    """Tramos con hidropatía media ≥ 1,6 en ventanas de 19 residuos: hélices transmembrana probables."""
    if len(secuencia) < VENTANA_TM:
        return 0
    valores = [_HIDROPATIA.get(r, 0.0) for r in secuencia]
    segmentos, dentro = 0, False
    for i in range(len(valores) - VENTANA_TM + 1):
        alta = sum(valores[i:i + VENTANA_TM]) / VENTANA_TM >= UMBRAL_TM
        segmentos += alta and not dentro
        dentro = alta
    return segmentos


def _secuencias(origen: str, cadenas: set[str]) -> dict[str, list[str]]:
    """Residuos observados de cada cadena, en el orden del archivo (sólo el primer modelo)."""
    vistos: set[tuple[str, str, str]] = set()
    salida: dict[str, list[str]] = defaultdict(list)
    for linea in origen.splitlines():
        if linea.startswith("ENDMDL"):
            break
        if not linea.startswith(("ATOM", "HETATM")) or len(linea) < 27:
            continue
        cadena, residuo = linea[21:22].strip() or "A", linea[17:20].strip()
        clave = (cadena, linea[22:26].strip(), linea[26:27].strip())
        if cadena in cadenas and residuo in _HIDROPATIA and clave not in vistos:
            vistos.add(clave)
            salida[cadena].append(residuo)
    return salida


def _enlaces_covalentes(origen: str, ligando: str, cadenas: set[str] | None = None) -> list[str]:
    """Registros LINK entre el ligando del cristal y un aminoácido del receptor, sin metales y a ≤ 2,3 Å.

    El aminoácido tiene que ser de las cadenas del receptor: un inhibidor peptídico lleva sus
    propios enlaces peptídicos en LINK (6LU7: PJE–LEU C:4) y no por eso está unido a la proteína.
    """
    from services.docking.preflight import _es_metal

    enlaces = []
    for linea in origen.splitlines():
        if not linea.startswith("LINK") or len(linea) < 57:
            continue
        lados = [(linea[12:16].strip(), linea[17:20].strip(), linea[21:22].strip(),
                  (linea[22:26] + linea[26:27]).strip()),
                 (linea[42:46].strip(), linea[47:50].strip(), linea[51:52].strip(),
                  (linea[52:56] + linea[56:57]).strip())]
        try:
            distancia = float(linea[73:78]) if len(linea) >= 78 and linea[73:78].strip() else None
        except ValueError:
            distancia = None
        nombres = {lado[1] for lado in lados}
        if ligando not in nombres or not (nombres & _AMINOACIDOS) or any(_es_metal(n) for n in nombres):
            continue
        if distancia is not None and distancia > _ENLACE_COVALENTE_A:
            continue
        lig, prot = sorted(lados, key=lambda lado: lado[1] != ligando)
        if cadenas is not None and (prot[2] or "A") not in cadenas:
            continue
        enlace = f"{lig[1]} {lig[2]}:{lig[3]} {lig[0]}–{prot[1]} {prot[2]}:{prot[3]} {prot[0]}"
        enlaces.append(enlace + (f" ({distancia:.1f} Å)" if distancia is not None else ""))
    return list(dict.fromkeys(enlaces))


#: SEQADV que no cambian la proteína que se cristalizó junto al sitio: colas de purificación y restos de la clonación.
_SEQADV_SIN_IMPORTANCIA = ("EXPRESSION TAG", "CLONING ARTIFACT", "INITIATING METHIONINE", "LEADER SEQUENCE")


def _filas_de_remark(origen: str, numero: str) -> list[tuple[str, str, str, str, list[str]]]:
    """(residuo, cadena, número, inserción, átomos) de las filas de datos de un REMARK 475/480/610.

    Las cabeceras de esos REMARK son frases en mayúsculas; una fila de datos es «[modelo] RES C NÚMERO[I] [átomos…]».
    """
    filas = []
    for linea in origen.splitlines():
        if not linea.startswith(f"REMARK {numero}"):
            continue
        partes = linea[10:].split()
        if partes and partes[0].isdigit() and len(partes) >= 4:
            partes = partes[1:]
        if len(partes) < 3 or len(partes[1]) != 1:
            continue
        m = re.fullmatch(r"(-?\d+)([A-Za-z]?)", partes[2])
        if not m or not re.fullmatch(r"[A-Z0-9]{1,3}", partes[0]):
            continue
        filas.append((partes[0], partes[1], m.group(1), m.group(2), partes[3:]))
    return filas


def _cabeceras_del_deposito(origen: str, cadenas: set[str], ligando_cristal: str | None, cristal: list[_Atomo] | None,
                            por_residuo: dict[tuple[str, str, str, str], list[_Atomo]], al_ligando) -> dict[str, Any]:
    """Lo que el depósito declara de sí mismo y que la preparación no lleva a ningún sitio (FEP-06-PRE, 2026-10-24).

    Ligando del cristal incompleto (REMARK 610), constructo modificado (SEQADV y REMARK 999) y ocupación cero
    (REMARK 475/480). Se leen las cabeceras tal cual; la distancia al ligando se mide sobre el ensamblaje.
    """
    salida: dict[str, Any] = {}
    if ligando_cristal and cristal:
        copia = (cristal[0].residuo, cristal[0].cadena, cristal[0].numero, cristal[0].insercion)
        if any((res, c, n, i) == copia for res, c, n, i, _ in _filas_de_remark(origen, "610")):
            salida["cristal_incompleto"] = f"{copia[0]} {copia[1]}:{copia[2]}{copia[3]}"

    modificadas: list[tuple[str, str, float | None]] = []
    for linea in origen.splitlines():
        if not linea.startswith("SEQADV") or len(linea) < 50:
            continue
        cadena, residuo = linea[16:17], linea[12:15].strip()
        if cadena not in cadenas:
            continue
        conflicto = linea[49:70].strip()
        if not conflicto or any(conflicto.startswith(s) for s in _SEQADV_SIN_IMPORTANCIA):
            continue
        numero, insercion = linea[18:22].strip(), linea[22:23].strip()
        distancia = al_ligando(por_residuo.get((cadena, numero, insercion, residuo), []))
        modificadas.append((f"{cadena}:{numero}{insercion} {residuo}", conflicto, distancia))
    salida["secuencia_modificada"] = modificadas
    texto_999 = " ".join(l[10:].strip() for l in origen.splitlines()
                         if l.startswith("REMARK 999") and l[10:].strip() and l[10:].strip() != "SEQUENCE")
    salida["remark_999"] = texto_999 or None

    ocupacion: list[tuple[str, str, float | None]] = []
    for numero_remark, entero in (("475", True), ("480", False)):
        for residuo, cadena, numero, insercion, atomos in _filas_de_remark(origen, numero_remark):
            if cadena not in cadenas:
                continue
            todos = por_residuo.get((cadena, numero, insercion, residuo), [])
            medidos = todos if entero else [a for a in todos if a.nombre in set(atomos)]
            ocupacion.append((f"{cadena}:{numero}{insercion} {residuo}",
                              "" if entero else " ".join(atomos), al_ligando(medidos)))
    salida["ocupacion_cero"] = ocupacion
    return salida


def _no_estandar(eval_result: Any, prov: dict[str, Any]) -> dict[str, int] | None:
    receptor = _leer_sellado(getattr(eval_result, "receptor_path", None), prov.get("receptor_sha256"))
    if receptor is None:
        return None
    residuos: dict[str, set[tuple[str, str, str]]] = defaultdict(set)
    for atomo in _atomos(receptor.decode("utf-8", errors="replace"), pesados=False):
        if atomo.residuo not in _AMINOACIDOS:
            residuos[atomo.residuo].add(atomo.clave)
    return {nombre: len(claves) for nombre, claves in sorted(residuos.items())}


#: Tipos de AutoDock de los metales que la preparación puede conservar. «NA» no entra: en un
#: PDBQT es el nitrógeno aceptor, no el sodio.
_METALES_AD = frozenset({"FE", "ZN", "MG", "MN", "CA", "CU", "CO", "NI", "CD"})
#: Metal–N de una His que lo coordina: Fe–N ≈ 2,0–2,2 Å y Zn–N ≈ 2,0–2,1 Å en los cristales.
UMBRAL_COORDINACION_A = 2.6
#: Un H unido a su N: N–H ≈ 1,0 Å.
_ENLACE_N_H_A = 1.15


def his_al_metal(pdbqt: str) -> list[tuple[str, str, str, float, bool]]:
    """Las His con un N del anillo que coordina un metal conservado, y si ese N lleva H.

    Un N unido al metal no puede llevar hidrógeno. La plantilla de Meeko no mira el metal: en
    las COX del catálogo, la His388 proximal coordina por NE2 el hierro del hemo conservado y
    recibe HIE, con el H justo en ese NE2 (8 de las 9 His que coordinan un metal en los 368
    receptores preparados por el barrido del 2026-10-11).
    """
    atomos = _atomos(pdbqt, pesados=False)
    metales = [a for a in atomos if a.elemento in _METALES_AD]
    if not metales:
        return []
    hidrogenos = [a for a in atomos if a.elemento == "HD"]
    filas = []
    for a in atomos:
        if a.residuo not in ("HIS", "HID", "HIE", "HIP") or a.nombre not in ("ND1", "NE2"):
            continue
        for m in metales:
            d = math.dist(a.xyz, m.xyz)
            if d <= UMBRAL_COORDINACION_A:
                con_h = any(h.clave == a.clave and math.dist(h.xyz, a.xyz) <= _ENLACE_N_H_A for h in hidrogenos)
                filas.append((f"{a.cadena}:{a.numero}{a.insercion}", a.nombre,
                              f"{m.nombre} {m.residuo} {m.cadena}:{m.numero}{m.insercion}", round(d, 2), con_h))
    return filas


#: Un H unido a su S: S–H ≈ 1,34 Å.
_ENLACE_S_H_A = 1.5


def cys_al_metal(pdbqt: str) -> list[tuple[str, str, str, float, bool]]:
    """Las Cys cuyo SG coordina un metal conservado, y si ese SG lleva HG.

    Una Cys que coordina un metal es un tiolato. La plantilla de Meeko no mira el metal y la deja
    como tiol neutro: en 4NY4 (CYP3A4), la Cys442 axial del hemo recibe HG a 2,54 Å del Fe
    (FEP-06-PRE, 2026-10-24). Fe–S ≈ 2,3 Å y Zn–S ≈ 2,3 Å en los cristales.
    """
    atomos = _atomos(pdbqt, pesados=False)
    metales = [a for a in atomos if a.elemento in _METALES_AD]
    if not metales:
        return []
    hidrogenos = [a for a in atomos if a.elemento == "HD"]
    filas = []
    for a in atomos:
        if a.residuo not in ("CYS", "CYX", "CYM") or a.nombre != "SG":
            continue
        for m in metales:
            d = math.dist(a.xyz, m.xyz)
            if d <= UMBRAL_COORDINACION_A:
                con_h = any(h.clave == a.clave and math.dist(h.xyz, a.xyz) <= _ENLACE_S_H_A for h in hidrogenos)
                filas.append((f"{a.cadena}:{a.numero}{a.insercion}", a.nombre,
                              f"{m.nombre} {m.residuo} {m.cadena}:{m.numero}{m.insercion}", round(d, 2), con_h))
    return filas


def medir(eval_result: Any, pdb_id: str | None) -> ContextoEstructural:
    """El contexto estructural de la corrida, o por qué no se pudo medir."""
    protocolo = getattr(eval_result, "docking_protocol", None) or {}
    prov = protocolo.get("execution_provenance") or {}
    contexto = _medir(eval_result, pdb_id)
    contexto.no_estandar = _no_estandar(eval_result, prov)
    receptor = _leer_sellado(getattr(eval_result, "receptor_path", None), prov.get("receptor_sha256"))
    texto = None if receptor is None else receptor.decode("utf-8", errors="replace")
    contexto.his_al_metal = None if texto is None else his_al_metal(texto)
    contexto.cys_al_metal = None if texto is None else cys_al_metal(texto)
    return contexto


@dataclass(frozen=True)
class OrigenComprobado:
    """El archivo depositado que preparó ESTE receptor, con lo que se derivó de la corrida.

    `datos` son los bytes del archivo tal cual (los que viajan en el paquete); `texto` es lo
    que leyó la preparación y lo que se mide. Sólo difieren en el camino B, que traduce los
    nombres que Meeko no conoce (WAT → HOH, HSD → HID) antes de preparar.
    """

    datos: bytes
    texto: str
    nombre: str
    sha256: str
    cadenas: set[str]
    ligando_cristal: str | None
    centro: tuple[float, float, float]
    lado: tuple[float, float, float]


#: `receptor_prep.modo_de_preparacion` de los caminos que no usan la receta automática.
#: El catálogo y el camino A no lo registran (o registran «automatico»).
_MODO_RESPETAR = "respetar"
_MODO_PDBQT_CON_ORIGEN = "pdbqt_con_origen"
_RECETA_DISTINTA = "El archivo de origen no es el que preparó el receptor de esta corrida (la receta no coincide)"


def origen_comprobado(eval_result: Any, pdb_id: str | None) -> OrigenComprobado | str:
    """El crudo depositado, o la razón por la que no se puede afirmar que sea el de la corrida.

    La comprobación es la receta: recalcularla con ese archivo y los parámetros de la corrida
    tiene que dar la que la corrida registró. Un archivo que no la da no es el que preparó este
    receptor, por mucho que se llame igual. Cada camino de preparación tiene SU receta, y se
    recalcula la del camino que registró la corrida:

    - catálogo y camino A: `preparer.receptor_recipe_hash`;
    - camino B (respetar el archivo): `preparer_respetando.receta_respetando`;
    - camino C con origen: `preparer_propio.receta_pdbqt`, que liga la corrida al PDBQT y al
      hash del origen subido. El crudo es la conversión de ese origen a PDB, y no tiene hash
      propio en el perfil: se exige además que siga correspondiendo al PDBQT de la corrida,
      con la misma medida que la subida.

    Hasta el 2026-10-11 se recalculaba siempre la automática, así que ningún receptor de los
    caminos B y C pasaba: FEP-09 lo midió en 127 de 127 auditorías del camino B (defecto P01),
    que medían desde la caja y decían que el archivo no era el de la corrida.
    """
    from services.docking import preparer

    protocolo = getattr(eval_result, "docking_protocol", None) or {}
    prov = protocolo.get("execution_provenance") or {}
    prep = prov.get("receptor_prep") or {}
    centro, lado = prov.get("box_center"), prov.get("box_size")
    receta = prep.get("recipe_hash")
    if not (pdb_id and receta and isinstance(centro, list) and isinstance(lado, list)):
        return "La corrida no registró la receta del receptor o la caja"
    fuente = preparer.receptor_source_path_no_network(pdb_id)
    if fuente is None or not fuente.is_file():
        return "No se encontró el archivo de origen del receptor"
    datos = fuente.read_bytes()
    texto = datos.decode("utf-8", errors="replace")
    texto_medido = texto

    sitio = [c for c in prep.get("site_chains") or [] if c]
    cadenas = set(sitio) if len(set(sitio)) > 1 else {str(prep.get("chain") or "").strip()}
    diff = prep.get("species_diff") if isinstance(prep.get("species_diff"), dict) else {}
    ligando_cristal = diff.get("site_ligand")
    modo = str(prep.get("modo_de_preparacion") or "")
    try:
        caja = (tuple(float(v) for v in centro), tuple(float(v) for v in lado))
        if modo == _MODO_RESPETAR:
            from services.docking.preparer_respetando import receta_respetando, traducir_residuos

            recalculada = receta_respetando(texto, cadenas, *caja)
            # La preparación filtró y midió el texto traducido: las especies del diff se llaman
            # HOH o HID, y medir el crudo con WAT o HSD las dejaría sin distancia.
            texto_medido = traducir_residuos(texto)[0]
        elif modo == _MODO_PDBQT_CON_ORIGEN:
            razon = _origen_del_pdbqt(eval_result, prov, pdb_id, texto, receta, caja)
            if razon:
                return razon
            recalculada = receta
        else:
            recalculada = preparer.receptor_recipe_hash(
                texto, chains=cadenas, cofactors_whitelist=prep.get("cofactors_whitelist"),
                center=caja[0], size=caja[1], site_ligand=ligando_cristal,
            )
    except (TypeError, ValueError):
        recalculada = None
    if recalculada != receta:
        return _RECETA_DISTINTA
    return OrigenComprobado(
        datos=datos, texto=texto_medido, nombre=fuente.name,
        sha256=hashlib.sha256(datos).hexdigest(), cadenas=cadenas,
        ligando_cristal=ligando_cristal,
        centro=caja[0],  # type: ignore[arg-type]
        lado=caja[1],  # type: ignore[arg-type]
    )


def _origen_del_pdbqt(eval_result: Any, prov: dict, pdb_id: str, texto: str, receta: str,
                      caja: tuple[tuple[float, ...], tuple[float, ...]]) -> str | None:
    """Camino C: `None` si el crudo es el origen del PDBQT de esta corrida; si no, por qué."""
    from services.docking.preparer_propio import receta_pdbqt
    from services.targets import perfil_receptor
    from services.targets.pdbqt_propio import correspondencia

    perfil = perfil_receptor.cargar(pdb_id)
    if not perfil or perfil.get("modo") != perfil_receptor.MODO_PDBQT or not perfil.get("origen"):
        return "No se encontró el perfil del receptor propio con el que se preparó esta corrida"
    try:
        recalculada = receta_pdbqt(perfil, *caja)
    except (KeyError, TypeError, ValueError):
        recalculada = None
    if recalculada != receta:
        return _RECETA_DISTINTA
    pdbqt = _leer_sellado(getattr(eval_result, "receptor_path", None), prov.get("receptor_sha256"))
    if pdbqt is None:
        return "No se pudo comprobar la estructura de origen del receptor"
    if not correspondencia(texto, pdbqt.decode("utf-8", errors="replace"))["corresponde"]:
        return "La estructura de origen ya no corresponde al PDBQT de esta corrida"
    return None


def _medir(eval_result: Any, pdb_id: str | None) -> ContextoEstructural:
    from services.docking import preparer
    from utils.file_handlers import StoragePath
    from utils.local_storage import path_for

    protocolo = getattr(eval_result, "docking_protocol", None) or {}
    prov = protocolo.get("execution_provenance") or {}
    prep = prov.get("receptor_prep") or {}
    pose = _pose_principal(eval_result)
    if not pose:
        return no_medido("La corrida no conserva la pose principal: las distancias se miden desde la caja.")
    comprobado = origen_comprobado(eval_result, pdb_id)
    if isinstance(comprobado, str):
        return no_medido(f"{comprobado}: las distancias se miden desde la caja.")
    receta = prep.get("recipe_hash")
    # Sin esta línea (54c5ba44 la movió a `origen_comprobado`), `_medir` lanzaba NameError,
    # la ruta lo capturaba y TODA auditoría medía desde la caja sin decir por qué.
    diff = prep.get("species_diff") if isinstance(prep.get("species_diff"), dict) else {}
    origen, cadenas = comprobado.texto, comprobado.cadenas
    ligando_cristal, centro, lado = comprobado.ligando_cristal, comprobado.centro, comprobado.lado

    from services.chemistry.ensamblaje_biologico import generar_unidad_biologica

    ensamblaje = _atomos(generar_unidad_biologica(origen, pdb_id=pdb_id).pdb)
    por_residuo: dict[tuple[str, str, str, str], list[_Atomo]] = defaultdict(list)
    for atomo in ensamblaje:
        por_residuo[atomo.clave_con_nombre].append(atomo)

    def _de(cadena: str, numero: str, insercion: str) -> list[_Atomo]:
        return [a for clave, atomos in por_residuo.items() if clave[:3] == (cadena, numero, insercion)
                for a in atomos]

    # El ligando del cristal: la copia más cercana al centro de la caja.
    referencias = [[a.xyz for a in pose]]
    # Los N y O del ligando: un agua sólo lo puentea si puede darle o aceptarle un hidrógeno.
    polares_del_ligando = [[a.xyz for a in pose if a.polar]]
    referencia = "Pose top-1"
    cristal: list[_Atomo] | None = None
    if ligando_cristal:
        copias = [atomos for atomos in por_residuo.values()
                  if atomos[0].registro == "HETATM" and atomos[0].residuo == ligando_cristal]
        if copias:
            def _al_centro(atomos: list[_Atomo]) -> float:
                return min(math.dist(a.xyz, centro) for a in atomos)
            copia = min(copias, key=_al_centro)
            referencias.append([a.xyz for a in copia])
            polares_del_ligando.append([a.xyz for a in copia if a.polar])
            cristal = copia
            referencia = (f"Pose top-1 y ligando del cristal {ligando_cristal} "
                          f"{copia[0].cadena}:{copia[0].numero}{copia[0].insercion}")

    def _al_ligando(atomos: list[_Atomo]) -> float | None:
        return _distancia([a.xyz for a in atomos], referencias)

    contexto = ContextoEstructural(medido=True, referencia=referencia, coordinadas={} if cristal else None)
    donadores = [a for a in cristal or [] if (a.elemento or a.nombre)[:1] in ("N", "O", "S")]
    poses = _poses(eval_result)
    contexto.poses_medidas = len(poses)

    contexto.segmentos_tm = {cadena: segmentos_transmembrana(secuencia)
                             for cadena, secuencia in sorted(_secuencias(origen, cadenas).items())}
    cabecera = next((linea for linea in origen.splitlines() if linea.startswith("HEADER")), "")
    contexto.clasificacion = cabecera[10:50].strip() or None
    contexto.lipidos = sorted({clave[3] for clave, atomos in por_residuo.items()
                               if atomos[0].registro == "HETATM" and clave[3] in _LIPIDOS_DE_MEMBRANA})
    if ligando_cristal:
        contexto.enlaces_covalentes = _enlaces_covalentes(origen, str(ligando_cristal).upper(), cadenas)
    cabeceras = _cabeceras_del_deposito(origen, cadenas, ligando_cristal, cristal, por_residuo, _al_ligando)
    contexto.cristal_incompleto = cabeceras.get("cristal_incompleto")
    contexto.secuencia_modificada = cabeceras["secuencia_modificada"]
    contexto.remark_999 = cabeceras["remark_999"]
    contexto.ocupacion_cero = cabeceras["ocupacion_cero"]

    # Los N y O de la proteína del receptor: con ellos se ve qué agua puede puentear al ligando.
    polares = [a.xyz for a in ensamblaje
               if a.registro == "ATOM" and a.cadena in cadenas and a.nombre[:1] in ("N", "O")]
    cerca = diff.get("near_site") if isinstance(diff.get("near_site"), dict) else {}
    for fila in list(cerca.get("removed") or []) + list(cerca.get("preserved") or []):
        clave = (str(fila.get("chain")), str(fila.get("residue_number")), str(fila.get("insertion_code") or ""))
        atomos = por_residuo.get((*clave, str(fila.get("name"))), [])
        distancia = _al_ligando(atomos)
        if distancia is not None:
            contexto.especies[(*clave, str(fila.get("name")))] = distancia
            # Otra copia del ligando del cristal también se mide sólo contra el cristal: el mínimo con la pose dice dónde
            # cayó la pose (7JVU: SHH A:404 a 0,31 Å de la pose y a 3,21 Å de SHH B:404), no a qué distancia está la copia.
            if cristal and fila.get("site_ligand_copy"):
                al_cristal = _distancia([a.xyz for a in atomos], [[a.xyz for a in cristal]])
                if al_cristal is not None:
                    contexto.especies_al_cristal[(*clave, str(fila.get("name")))] = al_cristal
            if cristal and fila.get("category") in ("metal", "organic_cofactor"):
                al_cristal = _distancia([a.xyz for a in atomos], [[a.xyz for a in cristal]])
                if al_cristal is not None:
                    contexto.especies_al_cristal[(*clave, str(fila.get("name")))] = al_cristal
                contacto = _coordinacion(atomos, donadores)
                if (contacto is None and al_cristal is not None and al_cristal <= UMBRAL_CONTACTO_COFACTOR_A
                        and fila.get("category") == "organic_cofactor"
                        and not any((a.elemento or "") in METALES_PDB for a in atomos)):
                    contacto = f"contacto {al_cristal:.2f} Å"
                if contacto and contexto.coordinadas is not None:
                    contexto.coordinadas[(*clave, str(fila.get("name")))] = contacto
            if fila.get("category") == "water" and distancia <= UMBRAL_AGUA_A:
                a_la_proteina = _distancia([a.xyz for a in atomos], [polares])
                if a_la_proteina is not None:
                    contexto.aguas_a_la_proteina[(*clave, str(fila.get("name")))] = a_la_proteina
                al_polar = _distancia([a.xyz for a in atomos], polares_del_ligando)
                if al_polar is not None:
                    contexto.aguas_al_ligando_polar[(*clave, str(fila.get("name")))] = al_polar

    for hueco in prep.get("backbone_gaps") or []:
        cadena = str(hueco.get("chain"))
        atomos = []
        for extremo in (str(hueco.get("after")), str(hueco.get("before"))):
            numero, insercion = _numero(extremo)
            atomos += por_residuo.get((cadena, numero, insercion, extremo.split()[0]), [])
        distancia = _al_ligando(atomos)
        if distancia is not None:
            contexto.huecos[(cadena, str(hueco.get("after")), str(hueco.get("before")))] = distancia
            extremos = [a.xyz for a in atomos]
            contexto.huecos_poses[(cadena, str(hueco.get("after")), str(hueco.get("before")))] = sorted(
                rango for rango, pose_k in poses.items()
                if (d := _distancia(extremos, [[a.xyz for a in pose_k]])) is not None and d <= UMBRAL_RESIDUO_A)

    for truncada in prep.get("truncated_sidechains") or []:
        clave = (str(truncada.get("chain")), str(truncada.get("residue_number")),
                 str(truncada.get("insertion_code") or ""))
        distancia = _al_ligando(por_residuo.get((*clave, str(truncada.get("name"))), []))
        if distancia is not None:
            contexto.truncadas[clave] = distancia

    # Conformaciones alternativas de las cadenas del receptor cerca del ligando,
    # con la regla de `preparer._filter_pdb_content`: la de mayor ocupación (A si empatan).
    for clave, atomos in sorted(por_residuo.items()):
        variantes: dict[str, float] = defaultdict(float)
        for atomo in atomos:
            if atomo.altloc and atomo.cadena in cadenas:
                variantes[atomo.altloc] += atomo.ocupacion
        if len(variantes) < 2:
            continue
        distancia = _al_ligando(atomos)
        if distancia is None or distancia > UMBRAL_RESIDUO_A:
            continue
        elegida = min(variantes, key=lambda v: (-variantes[v], v))
        reparto = "/".join(f"{v} {variantes[v] / max(1, sum(1 for a in atomos if a.altloc == v)):.2f}"
                           for v in sorted(variantes))
        contexto.altlocs.append((f"{clave[0]}:{clave[1]}{clave[2]} {atomos[0].residuo}",
                                 f"{reparto} → {elegida}", distancia))

    receptor = _leer_sellado(getattr(eval_result, "receptor_path", None), prov.get("receptor_sha256"))
    en_receptor: set[tuple[str, str, str]] | None = None
    if receptor is not None:
        en_receptor = {a.clave for a in _atomos(receptor.decode("utf-8", errors="replace"), pesados=False)}
        excluidas: dict[str, int] = defaultdict(int)
        for clave, atomos in por_residuo.items():
            if clave[:3] in en_receptor or atomos[0].registro != "ATOM":
                continue
            distancia = _al_ligando(atomos)
            if distancia is not None and distancia <= UMBRAL_ESPECIE_A:
                excluidas[clave[0]] += 1
        contexto.excluidas = dict(sorted(excluidas.items()))
        if len(cadenas) > 1:
            contexto.recorte = _recorte(receptor.decode("utf-8", errors="replace"), por_residuo, cadenas, lado)

    informe = path_for(preparer._meeko_report_path(StoragePath.target_prepared(pdb_id, receta)))
    try:
        datos = json.loads(informe.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        datos = None
    if isinstance(datos, dict) and datos.get("receptor_sha256") == prov.get("receptor_sha256"):
        # Un PDBQT sin origen declara aquí un motivo en texto, no un diccionario.
        plantillas = datos.get("protonation_templates")
        plantillas = plantillas if isinstance(plantillas, dict) else {}
        contexto.plantillas = []
        for residuo, fila in sorted(plantillas.items()):
            cadena, _, numero = str(residuo).partition(":")
            plantilla, entrada = str(fila.get("template")), str(fila.get("input_resname"))
            # Las variantes terminales («NMET», «CGLU») son el mismo estado de protonación.
            base = plantilla[1:] if len(plantilla) == 4 and plantilla[0] in "NC" else plantilla
            relevante = entrada.startswith("HI") or base not in {
                "ASP", "GLU", "LYS", "TYR", "ARG", "CYS", "CYX"}
            if not relevante:
                continue
            atomos = _de(cadena, numero, "")
            distancia = _al_ligando(atomos)
            if distancia is not None and distancia <= UMBRAL_RESIDUO_A:
                contexto.plantillas.append((residuo, entrada, plantilla, distancia))
                # Lo que la plantilla decide de una His es qué nitrógeno lleva el hidrógeno:
                # importa si uno de los dos toca al ligando, no si lo toca el esqueleto.
                anillo = _distancia([a.xyz for a in atomos if a.residuo.startswith("HI")
                                     and a.nombre in ("ND1", "NE2")], referencias)
                if entrada.startswith("HI") and anillo is not None:
                    contexto.anillos_his[residuo] = anillo
        contexto.plantillas.sort(key=lambda fila: fila[3])
        (contexto.disulfuros_rotos, contexto.disulfuros_totales,
         contexto.disulfuros_sin_evaluar) = _disulfuros(por_residuo, cadenas, plantillas, en_receptor)
    return contexto


def _recorte(receptor: str, por_residuo: dict[tuple[str, str, str, str], list[_Atomo]], cadenas: set[str],
             lado: tuple[float, float, float]) -> dict[str, Any]:
    from services.docking.preparer_multichain import radio_para_caja

    residuos: dict[tuple[str, str, str], dict[str, Xyz]] = defaultdict(dict)
    for atomo in _atomos(receptor, pesados=False):
        if atomo.registro == "ATOM":
            residuos[atomo.clave][atomo.nombre] = atomo.xyz
    cortes = 0
    ordenadas = sorted(residuos, key=lambda c: (c[0], int(c[1]) if c[1].lstrip("-").isdigit() else 0, c[2]))
    for a, b in zip(ordenadas, ordenadas[1:]):
        if a[0] == b[0] and "C" in residuos[a] and "N" in residuos[b] \
                and math.dist(residuos[a]["C"], residuos[b]["N"]) > _ENLACE_PEPTIDICO_A:
            cortes += 1
    de_las_cadenas = sum(1 for clave, atomos in por_residuo.items()
                         if clave[0] in cadenas and atomos[0].registro == "ATOM")
    return {"radio_A": round(float(radio_para_caja(lado)), 1), "residuos_receptor": len(residuos),
            "residuos_cadenas": de_las_cadenas, "cortes": cortes, "cadenas": sorted(cadenas)}


def _plantilla_de_cisteina(plantillas: dict[str, Any], residuo: str) -> str | None:
    """«CYS», «CYX» (también sus variantes terminales) o ``None`` si no consta."""
    fila = plantillas.get(residuo)
    plantilla = str(fila.get("template") or "") if isinstance(fila, dict) else ""
    base = plantilla[1:] if len(plantilla) == 4 and plantilla[0] in "NC" else plantilla
    return base if base in ("CYS", "CYX") else None


def _disulfuros(por_residuo: dict[tuple[str, str, str, str], list[_Atomo]], cadenas: set[str],
                plantillas: dict[str, Any],
                en_receptor: set[tuple[str, str, str]] | None = None,
                ) -> tuple[list[str], int, list[str]]:
    """Puentes S–S de la estructura: los rotos (CYS), el total y los que no se evaluaron.

    SCI-C-001. Antes, una cisteína sin plantilla daba el mismo «no roto» que una
    CYX, así que un receptor sin plantillas (el camino C con origen escribe
    ``{}``) salía con «ninguno queda como tiol libre» sin que nada lo
    comprobara. Ahora un puente sólo se da por conservado si sus **dos**
    cisteínas tienen plantilla CYX; roto si alguna es CYS; y si no, queda sin
    evaluar.

    Un puente cuyas dos cisteínas quedaron fuera del receptor (comprobado sobre
    el PDBQT, ``en_receptor``) no se cuenta como roto ni como sin evaluar: no
    deja un SH en la cavidad, y el recorte ya se declara aparte. De cada residuo
    se usa el azufre sin conformación alternativa o el de la primera.
    """
    azufres: dict[tuple[str, str, str, str], Xyz] = {}
    for clave, atomos in por_residuo.items():
        if clave[0] in cadenas and clave[3] in ("CYS", "CYX"):
            sg = sorted((a for a in atomos if a.nombre == "SG"), key=lambda a: a.altloc)
            if sg:
                azufres[clave] = sg[0].xyz
    rotos, total, sin_evaluar = [], 0, []
    claves = sorted(azufres)
    for i, clave_a in enumerate(claves):
        for clave_b in claves[i + 1:]:
            if math.dist(azufres[clave_a], azufres[clave_b]) > _DISULFURO_A:
                continue
            total += 1
            nombres = [f"{c[0]}:{c[1]}{c[2]}" for c in (clave_a, clave_b)]
            estados = [_plantilla_de_cisteina(plantillas, n) for n in nombres]
            if "CYS" in estados:
                rotos.append("–".join(nombres))
            elif estados == ["CYX", "CYX"]:
                continue
            elif en_receptor is not None and not any(c[:3] in en_receptor for c in (clave_a, clave_b)):
                continue
            else:
                sin_evaluar.append("–".join(nombres))
    return rotos, total, sin_evaluar
