"""El sitio de union de un receptor: que cadenas lo forman y con que evidencia.

# Por que vive en el backend y no en `scripts/`

Esta es la UNICA implementacion. La usan tres caminos que tienen que dar el mismo
resultado sobre la misma estructura:

  * el catalogo curado, via `scripts/revisar_cadena_por_receptor.py`, que importa
    de aqui en vez de tener su propia copia;
  * la ingesta automatica de un PDB ID que teclea el usuario;
  * la subida manual de un archivo.

Tenerla duplicada es como se llega a que el catalogo diga «interfaz B·A» y un
receptor subido por el usuario diga «cadena A» para la misma proteina. El doc 71
documenta a donde lleva eso.

# Que decide, y con que

`anotar_sitio` responde una pregunta: **que cadenas forman el sitio que hay
dentro de esta caja de docking**, y con que fuerza se sabe.

    cocrystal_ligand   las cadenas que contactan el ligando cristalizado a
                       <=4,5 A. Es lo que miraria un cristalografo.
    box_volume         las cadenas que ponen atomos dentro de la caja. No
                       distingue el bolsillo de la vecindad: una cadena puede
                       llenar la caja sin formar el sitio.

Presentar las dos como equivalentes seria afirmar de mas, y por eso la evidencia
viaja como campo hasta la tarjeta del receptor.

# Lo que NO decide

El modo de preparacion. Que un receptor se prepare con una cadena o con varias lo
DERIVA `prepare_target` de `site_chains`; aqui solo se mide el hecho.
"""

from __future__ import annotations

import collections
import math

#: Heteroatomos que NO son el ligando de interes: disolventes, crioprotectores,
#: tampones, iones sueltos y azucares de glicosilacion.
NO_SON_LIGANDO = {
    "HOH", "WAT", "DOD", "GOL", "EDO", "PEG", "PG4", "1PE", "2PE", "P6G", "PGE",
    "SO4", "PO4", "ACT", "ACY", "MES", "TRS", "EPE", "CIT", "FLC", "TLA", "MLI",
    "DMS", "IPA", "MPD", "BME", "FMT", "NO3", "CL", "BR", "IOD", "NA", "K", "MG",
    "CA", "ZN", "MN", "FE", "CU", "NI", "CD", "HG", "CO", "CS", "RB", "SR", "BA",
    "NAG", "MAN", "BMA", "FUC", "GAL", "GLC", "NDG", "XYP", "SIA",
    # A2G y NGA son los dos anomeros de la N-acetilgalactosamina: glicosilacion,
    # no ligando. Sin A2G, 6MEO se decidia por un azucar pegado a la superficie.
    "A2G", "NGA", "BGC", "FUL", "GLA", "NAN", "RAM", "XYS", "GCU", "IDS",
    "IMD", "AZI", "SCN", "OXY", "PER", "UNX", "UNL",
    # LIPIDOS Y DETERGENTES. Se excluyen porque un detergente pegado a la
    # superficie no dice donde esta el sitio de union: dice donde habia
    # membrana o donde cristalizo. La primera version de esta herramienta
    # eligio cadena por un C8E (eter de octilo) en 5O67, por COLESTEROL en
    # 7XW6 y por un fosfolipido en 3RVZ. Decidir la cadena del receptor por
    # ahi seria el mismo error que se esta intentando corregir.
    "CLR", "CHD", "CHS", "OLA", "OLB", "OLC", "PLM", "MYR", "STE", "PEE",
    "PGV", "PGW", "POV", "PCW", "PC1", "PX4", "LDA", "BOG", "LMT", "LMU",
    "DAO", "D10", "D12", "HEX", "HEZ", "LAP", "TRD", "UND", "DD9", "SOG",
    "PLC", "PSC", "DGA", "MC3", "Y01", "HP6", "12P", "15P", "P33", "7PE",
}

#: AMINOACIDOS MODIFICADOS. Aparecen como HETATM pero son parte de la CADENA
#: PROTEICA, no ligandos. La selenometionina (MSE) se usa para el faseado
#: cristalografico y esta por toda la proteina; elegir la cadena del receptor
#: por donde cae una MSE no significa nada. Paso en 5O65.
RESIDUOS_MODIFICADOS = {
    "MSE", "SEP", "TPO", "PTR", "CSO", "CME", "CSD", "CSS", "OCS", "KCX",
    "LLP", "PCA", "MLY", "M3L", "ALY", "HYP", "SEC", "PYL", "FME", "ABA",
    "AIB", "NLE", "ORN", "SAR", "DAL", "DAR", "DAS", "DCY", "DGL", "DHI",
    "DIL", "DLE", "DLY", "DPN", "DPR", "DSN", "DTH", "DTR", "DTY", "DVA",
    "TYS", "SEB", "NEP", "HIC", "MHO", "SNC", "TRQ", "CGU", "BMT", "MVA",
}

#: Los eteres de polioxietileno (C8E1..C8E9, y variantes) son detergentes.
PREFIJOS_DETERGENTE = ("C8E", "C10E", "C12E", "JEF", "PE4", "PE5", "PE8")

CORTE_CONTACTO = 4.5      # A. Distancia de contacto proteina-ligando.
MIN_ATOMOS_LIGANDO = 6    # menos que esto es un ion o un fragmento de disolvente
#: Residuos que tiene que tocar una copia para considerarse unida. El sitio
#: mediano del catalogo contacta 15-20; con menos de cinco no hay bolsillo.
MIN_CONTACTOS_PARA_ESTAR_UNIDO = 5
DOMINA = 0.90             # >=90% de los atomos de la caja: manda sola.
COMPARTE = 0.80           # <80%: el sitio se comparte de verdad.


def elegir_ligando(heteros: dict, proteina: list, centro, radio: float):
    """El ligando que ocupa la caja, eligiendo bien entre copias del mismo.

    Regla en dos pasos, y el orden importa:

      1. **Que ligando.** El mas cercano al centro de la caja. NO el que mas
         residuos toca: en un citocromo P450 el HEMO toca 30 residuos y el
         farmaco 15, y el HEMO es un cofactor, no lo que se quiere sondear.
         La caja codifica la intencion de quien curo el objetivo y manda.

      2. **Que COPIA de ese ligando.** Tambien la mas cercana, PERO descartando
         antes las copias que no estan unidas a nada. Una copia que toca uno o
         dos residuos esta pegada a la superficie o es un artefacto de
         cristalizacion: 4JZD tenia una copia de 1NJ tocando UN residuo al lado
         de otra tocando 24, y 6SXG una de OHT tocando dos frente a otra
         tocando seis.

         El filtro se queda ahi a proposito. Preferir siempre «la que mas toca»
         seria peor: en 4QA0 -HDAC8 con SAHA- las dos copias estan unidas de
         verdad, una por cadena, y esa regla habria movido el sitio a la cadena
         contraria a la que declaran la caja Y los doce hotspots. Entre copias
         legitimas manda la caja, que es la intencion de quien curo el objetivo.

    Devuelve `(clave, coords, distancia_al_centro)` o `None`.
    """
    candidatos = []
    for clave, coords in heteros.items():
        if len(coords) < MIN_ATOMOS_LIGANDO:
            continue
        mx = sum(p[0] for p in coords) / len(coords)
        my = sum(p[1] for p in coords) / len(coords)
        mz = sum(p[2] for p in coords) / len(coords)
        candidatos.append((math.dist((mx, my, mz), centro), clave, coords))
    if not candidatos:
        return None
    candidatos.sort(key=lambda c: c[0])
    nombre = candidatos[0][1][0]

    # Entre las copias del MISMO compuesto que caen en la caja, la que se une.
    copias = [c for c in candidatos if c[1][0] == nombre and c[0] <= radio]
    if len(copias) > 1:
        corte2 = CORTE_CONTACTO ** 2
        def contactos(coords):
            n = 0
            for _, x, y, z in proteina:
                if any((x - lx) ** 2 + (y - ly) ** 2 + (z - lz) ** 2 <= corte2
                       for lx, ly, lz in coords):
                    n += 1
            return n
        unidas = [c for c in copias if contactos(c[2]) >= MIN_CONTACTOS_PARA_ESTAR_UNIDO]
        if unidas:
            # Ya filtradas las no unidas, manda la cercania a la caja.
            mejor = min(unidas, key=lambda c: c[0])
            return mejor[1], mejor[2], mejor[0]
    d, clave, coords = candidatos[0]
    return clave, coords, d


#: Una cadena que aporta menos que esto al sitio no lo esta formando: lo roza.
#: Sin este suelo, un contacto de dos atomos convierte un monomero en interfaz.
APORTE_MINIMO = 0.15


def parsear_estructura(pdb_text: str):
    """Atomos de proteina y heteroatomos candidatos a ligando.

    Devuelve `(proteina, heteros)` con el mismo contrato que espera
    `elegir_ligando`: la proteina como `(cadena, x, y, z)` y los heteroatomos
    indexados por `(residuo, cadena, numero)`.
    """
    proteina: list[tuple[str, float, float, float]] = []
    heteros: dict[tuple[str, str, str], list[tuple[float, float, float]]] =         collections.defaultdict(list)
    for linea in pdb_text.splitlines():
        if not linea.startswith(("ATOM", "HETATM")):
            continue
        try:
            x, y, z = float(linea[30:38]), float(linea[38:46]), float(linea[46:54])
        except (ValueError, IndexError):
            continue
        cadena = linea[21].strip() or "?"
        if linea.startswith("ATOM"):
            proteina.append((cadena, x, y, z))
            continue
        residuo = linea[17:20].strip().upper()
        if (residuo in NO_SON_LIGANDO or residuo in RESIDUOS_MODIFICADOS
                or residuo.startswith(PREFIJOS_DETERGENTE)):
            continue
        heteros[(residuo, cadena, linea[22:27].strip())].append((x, y, z))
    return proteina, dict(heteros)


def anotar_sitio(
    pdb_text: str,
    centro: tuple[float, float, float],
    tamano: tuple[float, float, float],
) -> dict | None:
    """Los cuatro campos del sitio, o None si no hay con que medirlo.

    Args:
        pdb_text: el PDB COMPLETO, sin filtrar por cadena. Filtrarlo antes
            haria imposible ver que el sitio se forma entre varias.
        centro, tamano: la caja de docking.

    **Se mide sobre la UNIDAD BIOLOGICA, no sobre lo depositado.** Cuando el
    ensamblaje tiene simetria interna que coincide con la del cristal, el PDB
    trae solo una fraccion y el resto se genera con las matrices BIOMT. Medir
    sobre lo depositado veia media cavidad -o un cuarto, en un canal
    tetramerico- y anotaba un sitio que no existe asi. Ver
    `services/chemistry/ensamblaje_biologico.py` para las cifras.

    Returns:
        `{"site_chains", "site_chain_atoms", "site_evidence", "site_ligand"}`.
    """
    from services.chemistry.ensamblaje_biologico import generar_unidad_biologica

    proteina, heteros = parsear_estructura(generar_unidad_biologica(pdb_text).pdb)
    if not proteina:
        return None
    mitad = float(max(tamano)) / 2.0

    elegido = elegir_ligando(heteros, proteina, tuple(centro), mitad)
    contactos: collections.Counter = collections.Counter()
    ligando = None
    if elegido and elegido[2] <= mitad:
        (residuo, _, _), coords, _ = elegido
        corte2 = CORTE_CONTACTO ** 2
        for c, x, y, z in proteina:
            if any((x - lx) ** 2 + (y - ly) ** 2 + (z - lz) ** 2 <= corte2
                   for lx, ly, lz in coords):
                contactos[c] += 1
        if contactos:
            ligando = residuo

    if not contactos:
        for c, x, y, z in proteina:
            if all(abs(v - centro[i]) <= mitad for i, v in enumerate((x, y, z))):
                contactos[c] += 1
    total = sum(contactos.values())
    if not total:
        return None

    forman = [c for c, n in contactos.most_common() if n / total >= APORTE_MINIMO]
    if not forman:
        # Ninguna llega al suelo: sitio repartido de forma pareja entre muchas
        # -un anillo de diez subunidades con la caja sobre el eje-. Quedarse con
        # `[]` diria «no lo forma nadie», que es falso.
        forman = [c for c, _ in contactos.most_common()]

    return {
        "site_chains": forman,
        "site_chain_atoms": {c: contactos[c] for c in forman},
        "site_evidence": "cocrystal_ligand" if ligando else "box_volume",
        "site_ligand": ligando,
    }
