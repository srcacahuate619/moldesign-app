"""mmCIF/PDBx → PDB clásico, con una correspondencia explícita de todo lo que el PDB no puede representar.

# Por qué hace falta

Las entradas recientes del PDB sólo se publican en mmCIF, y el resto del pipeline
(filtro de cadenas, huecos, Meeko, dossier) lee columnas de PDB clásico. Convertir
con ``gemmi.make_pdb_string`` es corto y **destruye información en silencio**:

* ``resName`` tiene tres columnas: un código CCD de cinco caracteres (``A1D5J``,
  ambrisentán en 8XVK) se trunca a ``A1D`` y en 8YUT ``A1D67`` y ``A1D5J`` se
  fundirían en el mismo residuo (memoria ``codigos-ccd-de-cinco-caracteres``);
* la cadena es **una** columna: ``AAA`` o ``H1`` no caben;
* el número de serie son cinco dígitos y el de residuo cuatro.

Aquí nada se trunca ni se renombra sin dejar la correspondencia en el informe, que
viaja con el receptor hasta el dossier. Lo que no se puede representar se abstiene
con un motivo (:class:`ErrorDeSubida`), nunca se adivina.

# Qué se conserva y qué se decide

* Cadenas por ``auth_asym_id``; **primer modelo** (un RMN con 20 se declara).
* Altlocs y ocupaciones tal cual: la política de elegir la conformación mayoritaria
  la aplica ``_filter_pdb_content`` igual que con un PDB.
* Ensamblaje biológico: se usa el ``1`` (o el primero) **sólo si** se puede aplicar
  sin inventar copias (ver :func:`_decidir_ensamblaje`); si no, se usa la unidad
  asimétrica y se declara por qué.
* ``REMARK 465`` (residuos no observados), resolución, método y organismo se
  reescriben con el formato que ya leen las funciones del producto.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import gemmi

from services.targets.errores_subida import ErrorDeSubida

#: Caracteres que el PDB clásico admite como identificador de cadena, en el orden en que se reparten.
ALFABETO_DE_CADENAS = (
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "abcdefghijklmnopqrstuvwxyz"
    "0123456789"
)
#: Prefijos de los códigos sustitutos de residuos con nombre largo: Z00…Z99, luego Y00…
_PREFIJOS_SUSTITUTO = "ZYXWV"

MAX_SERIAL = 99999
MAX_RESIDUO = 9999
MIN_RESIDUO = -999
LIMITE_COORDENADA = 9999.999


@dataclass
class ConversionMmcif:
    """El PDB resultante y todo lo que hubo que decidir para escribirlo."""

    pdb: str
    informe: dict[str, Any]
    organismo: str | None = None
    resolucion: float | None = None
    metodo: str | None = None
    avisos: list[dict[str, Any]] = field(default_factory=list)


def _leer_bloque(texto: str, nombre: str) -> gemmi.cif.Block:
    try:
        documento = gemmi.cif.read_string(texto)
    except Exception as exc:  # gemmi lanza RuntimeError con la línea del fallo
        raise ErrorDeSubida(
            "MMCIF_ILEGIBLE",
            f"«{nombre}» no se pudo leer como mmCIF ({_sin_ruta(str(exc))}). Comprueba que el archivo no "
            "está truncado y que es el mmCIF completo, no un fragmento.",
            f"«{nombre}» could not be read as mmCIF ({_sin_ruta(str(exc))}). Check that the file is not "
            "truncated and that it is the complete mmCIF, not a fragment.",
        ) from exc
    for bloque in documento:
        if bloque.find_values("_atom_site.Cartn_x"):
            return bloque
    raise ErrorDeSubida(
        "MMCIF_SIN_ATOMOS",
        f"«{nombre}» es un mmCIF válido pero no tiene la tabla de átomos (_atom_site). Sube el mmCIF "
        "de coordenadas, no un archivo de factores de estructura o de validación.",
        f"«{nombre}» is a valid mmCIF but has no atom table (_atom_site). Upload the coordinates "
        "mmCIF, not a structure-factor or validation file.",
    )


def _sin_ruta(texto: str) -> str:
    import re

    return re.sub(r"(?:[A-Za-z]:)?[\\/][^\s:]+", "<archivo>", texto)[:160]


# ── Cadenas ───────────────────────────────────────────────────────────────


def _correspondencia_de_cadenas(nombres: list[str]) -> dict[str, str]:
    """Una letra de PDB por cadena. Las de un carácter se conservan; las demás se reparten."""
    usadas: set[str] = set()
    resultado: dict[str, str] = {}
    for nombre in nombres:
        if len(nombre) == 1 and not nombre.isspace():
            resultado[nombre] = nombre
            usadas.add(nombre)
    libres = iter(c for c in ALFABETO_DE_CADENAS if c not in usadas)
    for nombre in nombres:
        if nombre in resultado:
            continue
        try:
            resultado[nombre] = next(libres)
        except StopIteration:
            raise ErrorDeSubida(
                "MMCIF_DEMASIADAS_CADENAS",
                f"El mmCIF tiene {len(nombres)} cadenas con identificadores que el PDB clásico no puede "
                "representar y no quedan letras libres (62 en total). Recorta del archivo las cadenas que "
                "no vas a usar y vuelve a subirlo.",
                f"The mmCIF has {len(nombres)} chains with identifiers that classic PDB cannot represent "
                "and no free letters remain (62 in total). Remove the chains you will not use from the "
                "file and upload it again.",
            ) from None
    return resultado


# ── Residuos con nombre largo ─────────────────────────────────────────────


def _sustitutos_de_residuos(nombres: set[str], existentes: set[str]) -> dict[str, str]:
    """Un código de tres caracteres por cada nombre CCD largo, que no choque con ninguno del archivo."""
    ocupados = set(existentes)
    pool = (f"{p}{n:02d}" for p in _PREFIJOS_SUSTITUTO for n in range(100))
    resultado: dict[str, str] = {}
    for largo in sorted(nombres):
        sustituto = next(c for c in pool if c not in ocupados)
        resultado[largo] = sustituto
        ocupados.add(sustituto)
    return resultado


# ── Ensamblaje ────────────────────────────────────────────────────────────


def _decidir_ensamblaje(
    st: gemmi.Structure, bloque: gemmi.cif.Block | None = None,
) -> tuple[dict[str, Any], list[list[float]] | None]:
    """Qué ensamblaje se usa y si se puede escribir como matrices ``BIOMT``.

    El generador del producto (``ensamblaje_biologico``) aplica los operadores de
    ``BIOMOLECULE: 1`` a **todas** las cadenas del archivo. Eso sólo equivale a lo que declara
    el depósito cuando las generadoras del ensamblaje cubren todos los polímeros y comparten
    los mismos operadores. En cualquier otro caso aplicarlos inventaría copias: se usa la
    unidad asimétrica y se declara.
    """
    declarados = [
        {"id": a.name, "detalle": a.oligomeric_details or None, "operadores": sorted({
            o.name for g in a.generators for o in g.operators}),
         "generadoras": len(a.generators)}
        for a in st.assemblies
    ]
    if not st.assemblies:
        if bloque is not None and bloque.find_values("_pdbx_struct_assembly_gen.assembly_id"):
            return {"declarados": [], "usado": None, "estado": "unidad_asimetrica", "motivo": (
                "el archivo declara ensamblajes pero sus tablas están incompletas y no se pudieron interpretar")}, None
        return {"declarados": [], "usado": None, "estado": "unidad_asimetrica",
                "motivo": "el archivo no declara ensamblajes"}, None
    elegido = next((a for a in st.assemblies if a.name == "1"), st.assemblies[0])
    poliemros = {r.subchain for ch in st[0] for r in ch if r.entity_type == gemmi.EntityType.Polymer}
    cubiertos: set[str] = set()
    conjuntos = []
    for g in elegido.generators:
        cubiertos |= set(g.subchains)
        conjuntos.append(tuple((o.name, tuple(map(tuple, o.transform.mat.tolist())),
                               tuple(o.transform.vec.tolist())) for o in g.operators))
    base = {"declarados": declarados, "usado": elegido.name}
    if not poliemros <= cubiertos:
        return {**base, "usado": None, "estado": "unidad_asimetrica", "motivo": (
            f"el ensamblaje {elegido.name} no cubre todos los polímeros del archivo "
            f"({', '.join(sorted(poliemros - cubiertos))} quedan fuera) y aplicar sus operadores a "
            "todas las cadenas inventaría copias")}, None
    if len(set(conjuntos)) > 1:
        return {**base, "usado": None, "estado": "unidad_asimetrica", "motivo": (
            f"el ensamblaje {elegido.name} usa operadores distintos para cadenas distintas y el formato "
            "de matrices que lee MolDesign no puede expresarlo")}, None
    matrices = []
    for o in elegido.generators[0].operators:
        fila = [list(map(float, o.transform.mat.tolist()[i])) + [float(o.transform.vec.tolist()[i])]
                for i in range(3)]
        matrices.append(fila)
    return {**base, "estado": "aplicado", "operadores_aplicados": len(matrices),
            "motivo": f"se usa el ensamblaje {elegido.name} declarado por el depósito"}, matrices


# ── Metadatos ─────────────────────────────────────────────────────────────


def _primero(bloque: gemmi.cif.Block, *columnas: str) -> str | None:
    for columna in columnas:
        for valor in bloque.find_values(columna):
            texto = gemmi.cif.as_string(valor)
            if texto and texto not in ("?", "."):
                return texto
    return None


def _formato_linea(serial: int, atomo: gemmi.Atom, residuo: gemmi.Residue, nombre_residuo: str,
                   cadena: str) -> str:
    nombre = atomo.name
    elemento = atomo.element.name.upper()
    if len(nombre) >= 4:
        campo = nombre[:4]
    elif len(elemento) == 1:
        campo = (" " + nombre).ljust(4)
    else:
        campo = nombre.ljust(4)
    registro = "HETATM" if residuo.het_flag == "H" else "ATOM  "
    altloc = atomo.altloc if atomo.altloc != "\0" else " "
    icode = residuo.seqid.icode if residuo.seqid.icode not in ("\0", " ") else " "
    p = atomo.pos
    return (f"{registro}{serial:>5} {campo}{altloc}{nombre_residuo:>3} {cadena}{residuo.seqid.num:>4}{icode}   "
            f"{p.x:8.3f}{p.y:8.3f}{p.z:8.3f}{atomo.occ:6.2f}{atomo.b_iso:6.2f}          {elemento:>2}")


def mmcif_a_pdb(texto: str, nombre: str = "archivo") -> ConversionMmcif:
    """Convierte un mmCIF en un PDB clásico y devuelve, aparte, cada decisión que hubo que tomar."""
    bloque = _leer_bloque(texto, nombre)
    try:
        st = gemmi.make_structure_from_block(bloque)
    except Exception as exc:
        raise ErrorDeSubida(
            "MMCIF_ILEGIBLE",
            f"«{nombre}» tiene la tabla de átomos pero gemmi no pudo construir la estructura "
            f"({_sin_ruta(str(exc))}).",
            f"«{nombre}» has the atom table but gemmi could not build the structure "
            f"({_sin_ruta(str(exc))}).",
        ) from exc
    if len(st) == 0 or sum(len(r) for ch in st[0] for r in ch) == 0:
        raise ErrorDeSubida(
            "MMCIF_SIN_ATOMOS", f"«{nombre}» no contiene ningún átomo.", f"«{nombre}» contains no atoms.")
    st.setup_entities()
    modelo = st[0]
    modelos_en_archivo = len(st)

    nombres_de_cadena = list(dict.fromkeys(ch.name for ch in modelo))
    cadenas = _correspondencia_de_cadenas(nombres_de_cadena)
    existentes = {r.name for ch in modelo for r in ch}
    largos = {n for n in existentes if len(n) > 3}
    sustitutos = _sustitutos_de_residuos(largos, existentes)

    ensamblaje, matrices = _decidir_ensamblaje(st, bloque)

    # ── Las líneas de átomos, validando que cada valor cabe en su columna ──
    lineas: list[str] = []
    serial_real = 0
    renombrados: dict[tuple[str, str, int, str], dict[str, Any]] = {}
    hidrogenos = altlocs = 0
    for ch in modelo:
        letra = cadenas[ch.name]
        for res in ch:
            numero = res.seqid.num
            if not MIN_RESIDUO <= numero <= MAX_RESIDUO:
                raise ErrorDeSubida(
                    "MMCIF_NUMERACION_NO_REPRESENTABLE",
                    f"El residuo {ch.name}:{numero} ({res.name}) no cabe en el formato PDB clásico, que "
                    f"admite números de residuo entre {MIN_RESIDUO} y {MAX_RESIDUO}. Renumera esa cadena o "
                    "recórtala del archivo y vuelve a subirlo.",
                    f"Residue {ch.name}:{numero} ({res.name}) does not fit classic PDB format, which allows "
                    f"residue numbers between {MIN_RESIDUO} and {MAX_RESIDUO}. Renumber that chain or "
                    "remove it from the file and upload again.",
                )
            nombre_pdb = sustitutos.get(res.name, res.name)
            if nombre_pdb != res.name:
                clave = (res.name, ch.name, numero, str(res.seqid.icode).strip("\0 "))
                renombrados.setdefault(clave, {
                    "original": res.name, "pdb": nombre_pdb, "cadena": ch.name, "cadena_pdb": letra,
                    "numero": numero, "insercion": clave[3] or None, "atomos": 0})["atomos"] += len(res)
            for atomo in res:
                p = atomo.pos
                if max(abs(p.x), abs(p.y), abs(p.z)) > LIMITE_COORDENADA or not all(
                        math.isfinite(v) for v in (p.x, p.y, p.z)):
                    raise ErrorDeSubida(
                        "MMCIF_COORDENADA_NO_REPRESENTABLE",
                        f"Una coordenada del residuo {ch.name}:{numero} está fuera del rango del formato PDB "
                        "(±9999,999 Å) o no es un número. Centra la estructura o revisa el archivo.",
                        f"A coordinate of residue {ch.name}:{numero} is outside the PDB format range "
                        "(±9999.999 Å) or is not a number. Center the structure or check the file.",
                    )
                serial_real += 1
                serial = (serial_real - 1) % MAX_SERIAL + 1
                lineas.append(_formato_linea(serial, atomo, res, nombre_pdb, letra))
                hidrogenos += atomo.element.name in ("H", "D")
                altlocs += atomo.altloc != "\0"
    serial_renumerado = serial_real > MAX_SERIAL

    # ── Cabecera: lo que ya leen las funciones del producto ──
    metodo = _primero(bloque, "_exptl.method")
    resolucion_texto = _primero(bloque, "_refine.ls_d_res_high", "_em_3d_reconstruction.resolution",
                                "_reflns.d_resolution_high")
    try:
        resolucion = float(resolucion_texto) if resolucion_texto else None
    except ValueError:
        resolucion = None
    organismo = _primero(bloque, "_entity_src_gen.pdbx_gene_src_scientific_name",
                         "_entity_src_nat.pdbx_organism_scientific",
                         "_pdbx_entity_src_syn.organism_scientific")
    cabecera: list[str] = []
    if metodo:
        cabecera.append(f"EXPDTA    {metodo.upper()}"[:80])
    if organismo:
        cabecera.append(f"SOURCE    MOL_ID: 1; ORGANISM_SCIENTIFIC: {organismo};"[:80])
    if resolucion is not None:
        cabecera.append(f"REMARK   2 RESOLUTION.    {resolucion:.2f} ANGSTROMS.")
    cabecera.extend(_remark_465(bloque, cadenas, sustitutos))
    if matrices is not None:
        cabecera.append("REMARK 350 BIOMOLECULE: 1")
        for i, fila in enumerate(matrices, start=1):
            for eje, valores in enumerate(fila, start=1):
                cabecera.append(
                    f"REMARK 350   BIOMT{eje}{i:>4}{valores[0]:>10.6f}{valores[1]:>10.6f}"
                    f"{valores[2]:>10.6f}{valores[3]:>15.5f}")

    avisos: list[dict[str, Any]] = []
    if modelos_en_archivo > 1:
        avisos.append({
            "codigo": "MMCIF_VARIOS_MODELOS",
            "es": f"El archivo trae {modelos_en_archivo} modelos (¿un conjunto de RMN?): se usa el modelo 1.",
            "en": f"The file has {modelos_en_archivo} models (an NMR ensemble?): model 1 is used.",
        })
    if serial_renumerado:
        avisos.append({
            "codigo": "MMCIF_SERIE_RENUMERADA",
            "es": f"El archivo tiene {serial_real} átomos y el PDB clásico sólo numera 99 999: los números de "
                  "serie se repiten (los átomos se identifican por cadena, residuo y nombre, no por serie).",
            "en": f"The file has {serial_real} atoms and classic PDB only numbers 99,999: serial numbers repeat "
                  "(atoms are identified by chain, residue and name, not by serial).",
        })
    if cadenas and any(a != b for a, b in cadenas.items()):
        avisos.append({
            "codigo": "MMCIF_CADENAS_RENOMBRADAS",
            "es": "Hay cadenas cuyo identificador no cabe en una letra; se les asignó una letra libre. La "
                  "correspondencia está en el informe de preparación.",
            "en": "Some chains have identifiers that do not fit in one letter; each was given a free letter. "
                  "The mapping is in the preparation report.",
        })
    if renombrados:
        avisos.append({
            "codigo": "MMCIF_RESIDUOS_RENOMBRADOS",
            "es": "Hay residuos con código de más de tres caracteres (CCD reciente); se les asignó un código "
                  "sustituto único. La correspondencia está en el informe de preparación.",
            "en": "Some residues have codes longer than three characters (recent CCD); each was given a unique "
                  "substitute code. The mapping is in the preparation report.",
        })

    pdb = "\n".join([*cabecera, *lineas, "END"]) + "\n"
    informe = {
        "origen_formato": "mmcif",
        "bloque": bloque.name,
        "metodo": metodo,
        "modelos": {"en_el_archivo": modelos_en_archivo, "usado": 1},
        "atomos": serial_real,
        "hidrogenos": hidrogenos,
        "atomos_con_altloc": altlocs,
        "cadenas": [{"original": n, "pdb": cadenas[n], "renombrada": n != cadenas[n]} for n in nombres_de_cadena],
        "residuos_renombrados": sorted(renombrados.values(), key=lambda r: (r["cadena"], r["numero"], r["pdb"])),
        "ensamblaje": ensamblaje,
        "serie_renumerada": serial_renumerado,
        "coordenadas": "redondeadas a 3 decimales (formato PDB)",
        "avisos": [a["codigo"] for a in avisos],
    }
    return ConversionMmcif(pdb=pdb, informe=informe, organismo=organismo, resolucion=resolucion,
                           metodo=metodo, avisos=avisos)


def _remark_465(bloque: gemmi.cif.Block, cadenas: dict[str, str], sustitutos: dict[str, str]) -> list[str]:
    """``REMARK 465`` desde ``_pdbx_unobs_or_zero_occ_residues`` (residuos sin coordenadas)."""
    tabla = bloque.find("_pdbx_unobs_or_zero_occ_residues.",
                        ["auth_asym_id", "auth_comp_id", "auth_seq_id", "occupancy_flag"])
    lineas: list[str] = []
    for fila in tabla:
        cadena, residuo, numero, bandera = (gemmi.cif.as_string(v) for v in fila)
        if bandera != "1" or cadena not in cadenas:
            continue
        residuo = sustitutos.get(residuo, residuo)
        if len(residuo) > 3 or not numero.lstrip("-").isdigit():
            continue
        lineas.append(f"REMARK 465     {residuo:>3} {cadenas[cadena]} {int(numero):>5}")
    return lineas


def a_pdb_clasico(archivo) -> tuple[str, dict[str, Any]]:
    """El texto PDB clásico de una estructura subida (``ArchivoSubido``) y lo que hubo que declarar.

    Un PDB pasa tal cual (``{}``); un mmCIF se convierte con :func:`mmcif_a_pdb` (``{"conversion": …}``) y un PQR
    con :func:`lector_pqr.pqr_a_pdb` (``{"pqr": …}``). Un PDBQT no es una estructura de origen: se rechaza.
    """
    if archivo.formato == "pdb":
        return archivo.texto, {}
    if archivo.formato == "mmcif":
        conversion = mmcif_a_pdb(archivo.texto, archivo.nombre)
        return conversion.pdb, {"conversion": conversion.informe}
    if archivo.formato == "pqr":
        from services.targets.lector_pqr import pqr_a_pdb

        texto, informe = pqr_a_pdb(archivo.texto, archivo.nombre)
        return texto, {"pqr": informe}
    raise ErrorDeSubida(
        "FORMATO_AUN_NO_SOPORTADO",
        f"El formato {archivo.formato.upper()} todavía no se prepara en este modo. Súbelo como PDB.",
        f"The {archivo.formato.upper()} format is not prepared in this mode yet. Upload it as PDB.",
    )
