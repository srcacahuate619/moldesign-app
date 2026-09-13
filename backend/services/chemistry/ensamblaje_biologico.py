"""Genera la unidad biologica a partir de las matrices BIOMT del PDB.

# Que problema resuelve

Un PDB deposita la **unidad asimetrica**: lo que hizo falta para describir el
cristal. La **unidad biologica** es la forma funcional de la molecula. Casi
siempre coinciden, pero cuando el ensamblaje tiene simetria interna que coincide
con la del cristal basta depositar una fraccion, y el resto se reconstruye
aplicando las matrices `BIOMT` del `REMARK 350`.

NavAb (5VB8) es el caso claro: homotetramero con eje de orden 4 que coincide con
el del cristal, asi que el archivo trae UNA subunidad y declara::

    AUTHOR DETERMINED BIOLOGICAL UNIT: TETRAMERIC

El poro del canal lo forman las cuatro subunidades. Con una, el poro no existe:
la caja de docking apunta al eje y encuentra vacio.

# Cuanto pesaba, medido sobre el catalogo

39 de los 385 declaraban mas de una matriz en `BIOMOLECULE: 1`. Generando el
ensamblaje y contando cuantos atomos aparecen DENTRO de la caja que no estaban
en el archivo:

    5VB8  80,5%      6SXG  56,9%      5E4G  44,1%
    5YUA  68,0%      6MWA  50,8%      6OGV  40,4%
    6SX5  64,8%      6SXE  50,4%      ...
    6SX7  61,3%      6P6X  45,6%      6LU7  12,6%
    6SXC  57,0%

**31 de los 39 tenian atomos que faltaban dentro de su caja de docking. Diez
superaban el 40%.**

Es el mismo defecto que el modo C del doc 71 -el sitio se forma entre copias y
solo se conserva una- pero generado por la SIMETRIA CRISTALOGRAFICA en vez de
por el filtrado de cadena. Era invisible a todas las comprobaciones anteriores
porque todas leian las coordenadas depositadas.

# Por que se puede aplicar siempre

Cuando solo hay la identidad -341 de los 385- la funcion devuelve la entrada sin
tocarla. Y cuando el sitio esta contenido en una subunidad, las copias generadas
caen lejos de la caja y el recorte al sitio las descarta: el resultado no cambia,
solo se hace algo de trabajo de mas. No hace falta decidir caso por caso, que es
justo donde se cuelan los errores.

# Determinismo

Las cadenas nuevas se nombran en un orden fijo -operador por operador, cadena por
cadena, alfabeto fijo-, asi que la misma entrada da siempre la misma salida. De
eso depende que la cache del receptor preparado siga siendo valida: si los
nombres cambiaran entre corridas, `prepared_receptor_matches_chain` invalidaria
el `.pdbqt` en cada arranque.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from utils.logger import get_logger

log = get_logger(__name__)

#: De donde salen los identificadores de las cadenas generadas. El formato PDB
#: clasico usa UN caracter, asi que hay 62 disponibles: de sobra para el peor
#: caso del catalogo (2 cadenas x 12 operadores = 24).
ALFABETO_DE_CADENAS = (
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "abcdefghijklmnopqrstuvwxyz"
    "0123456789"
)

_BIOMT = re.compile(r"^REMARK 350\s+BIOMT([123])\s+(\d+)\s+(.+)$")
_BIOMOLECULE = re.compile(r"^REMARK 350\s+BIOMOLECULE:\s*(\d+)")

Matriz = tuple[tuple[float, float, float, float], ...]


@dataclass(frozen=True)
class Ensamblaje:
    """Lo que se genero, para poder declararlo."""

    pdb: str
    #: Operadores aplicados, incluida la identidad.
    operadores: int
    #: Cadenas del archivo original.
    cadenas_originales: tuple[str, ...]
    #: Cadenas que existen tras generar, originales incluidas.
    cadenas_finales: tuple[str, ...]
    #: `True` si hubo algo que generar. `False` deja la entrada intacta.
    generado: bool


def _es_identidad(m: Matriz, tol: float = 1e-6) -> bool:
    esperado = ((1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0))
    return all(abs(m[i][j] - esperado[i][j]) < tol for i in range(3) for j in range(4))


def leer_matrices(pdb_text: str) -> list[Matriz]:
    """Las matrices de `BIOMOLECULE: 1`, en el orden en que aparecen.

    Solo el ensamblaje PRINCIPAL. Varias entradas declaran mas de uno -formas
    alternativas, o el contenido de la unidad asimetrica frente al biologico- y
    mezclarlos generaria copias que nadie pidio.
    """
    matrices: list[Matriz] = []
    filas: list[tuple[float, float, float, float]] = []
    en_principal = False
    for linea in pdb_text.splitlines():
        if not linea.startswith("REMARK 350"):
            if linea.startswith(("ATOM", "HETATM")):
                break          # los REMARK van antes; no hay que seguir leyendo
            continue
        cabecera = _BIOMOLECULE.match(linea)
        if cabecera:
            en_principal = cabecera.group(1) == "1"
            continue
        if not en_principal:
            continue
        m = _BIOMT.match(linea)
        if not m:
            continue
        try:
            valores = tuple(float(x) for x in m.group(3).split()[:4])
        except ValueError:
            continue
        if len(valores) != 4:
            continue
        filas.append(valores)  # type: ignore[arg-type]
        if m.group(1) == "3" and len(filas) == 3:
            matrices.append(tuple(filas))  # type: ignore[arg-type]
            filas = []
    return matrices


def generar_unidad_biologica(pdb_text: str, *, pdb_id: str = "") -> Ensamblaje:
    """Aplica los operadores BIOMT y devuelve el ensamblaje completo.

    Si solo hay la identidad -o ninguna matriz- devuelve la entrada intacta y
    `generado=False`. Es el caso de 341 de los 385 objetivos del catalogo.
    """
    lineas = pdb_text.splitlines()
    originales = []
    for l in lineas:
        if l.startswith(("ATOM", "HETATM")) and len(l) > 21:
            c = l[21]
            if c not in originales:
                originales.append(c)

    matrices = leer_matrices(pdb_text)
    a_aplicar = [m for m in matrices if not _es_identidad(m)]
    if not a_aplicar:
        return Ensamblaje(
            pdb=pdb_text, operadores=max(len(matrices), 1),
            cadenas_originales=tuple(originales),
            cadenas_finales=tuple(originales), generado=False,
        )

    libres = [c for c in ALFABETO_DE_CADENAS if c not in originales]
    if len(libres) < len(a_aplicar) * len(originales):
        # Sin identificadores no se puede generar sin colisionar, y una colision
        # fundiria dos cadenas distintas en una: `trim_to_pocket` indexa por
        # (cadena, numero) y perderia residuos en silencio. Antes que eso, se
        # devuelve el archivo tal cual y se declara.
        log.warning(
            "ensamblaje_no_generado_sin_identificadores",
            pdb_id=pdb_id, cadenas=len(originales), operadores=len(a_aplicar),
        )
        return Ensamblaje(
            pdb=pdb_text, operadores=len(matrices),
            cadenas_originales=tuple(originales),
            cadenas_finales=tuple(originales), generado=False,
        )

    salida = list(lineas)
    siguiente = 0
    finales = list(originales)
    for matriz in a_aplicar:
        renombre = {}
        for c in originales:
            renombre[c] = libres[siguiente]
            finales.append(libres[siguiente])
            siguiente += 1
        for l in lineas:
            if not l.startswith(("ATOM", "HETATM")) or len(l) < 54:
                continue
            try:
                x, y, z = float(l[30:38]), float(l[38:46]), float(l[46:54])
            except ValueError:
                continue
            nx = matriz[0][0] * x + matriz[0][1] * y + matriz[0][2] * z + matriz[0][3]
            ny = matriz[1][0] * x + matriz[1][1] * y + matriz[1][2] * z + matriz[1][3]
            nz = matriz[2][0] * x + matriz[2][1] * y + matriz[2][2] * z + matriz[2][3]
            nueva = (
                l[:21]
                + renombre.get(l[21], l[21])
                + l[22:30]
                + f"{nx:8.3f}{ny:8.3f}{nz:8.3f}"
                + l[54:]
            )
            salida.append(nueva)
    salida.append("END")

    log.info(
        "unidad_biologica_generada",
        pdb_id=pdb_id, operadores=len(matrices),
        cadenas_originales=len(originales), cadenas_finales=len(finales),
    )
    return Ensamblaje(
        pdb="\n".join(salida) + "\n", operadores=len(matrices),
        cadenas_originales=tuple(originales), cadenas_finales=tuple(finales),
        generado=True,
    )
