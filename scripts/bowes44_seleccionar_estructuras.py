#!/usr/bin/env python3
r"""Elige una estructura humana para cada diana del panel mínimo de Bowes 2012.

# Qué hace

Para cada una de las 44 dianas del panel (Bowes et al. 2012, Nat Rev Drug Discov
11:909-922, tabla 1; lo distribuye Eurofins como SafetyScreen44):

1. resuelve el símbolo del gen a su accesión de UniProt **revisada y humana**,
   por la API de UniProt;
2. pide al RCSB las estructuras de esa accesión, y se queda con las de rayos X
   con un ligando drug-like en el sitio;
3. ordena por resolución y anota los candidatos con su procedencia.

**No decide el sitio.** La caja, la preparación y el redocking del ligando
cristalizado los mide `bowes44_validar_estructuras.py`: una estructura sólo entra
en el panel si su ligando se reacopla en su propio sitio.

La identidad se comprueba con lo que devuelve la API (nombre de la proteína y
gen), no con lo que este archivo supone. Un símbolo que no resuelva, o una diana
sin estructura que pase los filtros, queda declarada sin candidato.

# Uso

    python scripts/bowes44_seleccionar_estructuras.py --write   # consulta la red
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
DESTINO = RAIZ / "docs" / "auditorias" / "ae4db6a" / "bowes44_candidatos.json"

#: Las 44 dianas, como las nombra la ficha de SafetyScreen44, con su símbolo de
#: gen (HGNC). `None` donde la ficha no identifica un gen sin ambigüedad.
PANEL: tuple[tuple[str, str, str | None], ...] = (
    ("A2A", "GPCR", "ADORA2A"),
    ("alpha1A", "GPCR", "ADRA1A"),
    ("alpha2A", "GPCR", "ADRA2A"),
    ("beta1", "GPCR", "ADRB1"),
    ("beta2", "GPCR", "ADRB2"),
    ("CB1", "GPCR", "CNR1"),
    ("CB2", "GPCR", "CNR2"),
    ("CCK1 (CCKA)", "GPCR", "CCKAR"),
    ("D1", "GPCR", "DRD1"),
    ("D2S", "GPCR", "DRD2"),
    ("ETA", "GPCR", "EDNRA"),
    ("H1", "GPCR", "HRH1"),
    ("H2", "GPCR", "HRH2"),
    ("M1", "GPCR", "CHRM1"),
    ("M2", "GPCR", "CHRM2"),
    ("M3", "GPCR", "CHRM3"),
    ("delta2 (DOP)", "GPCR", "OPRD1"),
    ("kappa (KOP)", "GPCR", "OPRK1"),
    ("mu (MOP)", "GPCR", "OPRM1"),
    ("5-HT1A", "GPCR", "HTR1A"),
    ("5-HT1B", "GPCR", "HTR1B"),
    ("5-HT2A", "GPCR", "HTR2A"),
    ("5-HT2B", "GPCR", "HTR2B"),
    ("V1a", "GPCR", "AVPR1A"),
    ("dopamine transporter", "Transportador", "SLC6A3"),
    ("norepinephrine transporter", "Transportador", "SLC6A2"),
    ("5-HT transporter", "Transportador", "SLC6A4"),
    ("BZD (central)", "Canal iónico", "GABRA1"),
    ("NMDA", "Canal iónico", "GRIN1"),
    ("N neuronal alpha4beta2", "Canal iónico", "CHRNA4"),
    ("5-HT3", "Canal iónico", "HTR3A"),
    ("Ca2+ channel (L, dihydropyridine site)", "Canal iónico", "CACNA1C"),
    ("hERG", "Canal iónico", "KCNH2"),
    # La ficha dice «KV channel» sin precisar el subtipo: no se elige por
    # nosotros. Bowes 2012 hay que consultarlo para fijarlo.
    ("KV channel", "Canal iónico", None),
    ("Na+ channel (site 2)", "Canal iónico", "SCN5A"),
    ("AR", "Receptor nuclear", "AR"),
    ("GR", "Receptor nuclear", "NR3C1"),
    ("Lck kinase", "Quinasa", "LCK"),
    ("COX1", "Enzima", "PTGS1"),
    ("COX2", "Enzima", "PTGS2"),
    ("acetylcholinesterase", "Enzima", "ACHE"),
    ("MAO-A", "Enzima", "MAOA"),
    ("PDE3A", "Enzima", "PDE3A"),
    ("PDE4D2", "Enzima", "PDE4D"),
)

#: Heteroátomos que no cuentan como ligando del sitio: iones, tampones,
#: crioprotectores, detergentes y lípidos frecuentes en cristalografía.
#: Lo que aparece en un cristal y **no** es el ligando farmacológico. No es una
#: preferencia estética: si se cuela uno, el redocking confirma un sitio que no
#: es el del fármaco y el panel afirma algo falso. Medido: el PTY de 8ZP2
#: (fosfatidiletanolamina, 700 Da, dentro de la ventana de masa) daba el sitio
#: «confirmado» a 0,99 Å sobre un bolsillo lipídico del transportador de
#: noradrenalina. Los cofactores se excluyen aparte, por plantilla.
NO_LIGANDOS = frozenset({
    # agua, iones y sales
    "HOH", "DOD", "NA", "K", "MG", "CA", "ZN", "MN", "FE", "FE2", "CU", "NI", "CO", "CD", "HG",
    "CL", "BR", "IOD", "F", "SO4", "PO4", "NO3", "ACT", "NH4", "CYN", "AZI", "FLC", "SCN",
    # crioprotectores, tampones y aditivos
    "EDO", "GOL", "PEG", "PG4", "PGE", "1PE", "P6G", "2PE", "DMS", "TRS", "MES", "EPE",
    "IMD", "MPD", "FMT", "ACY", "TLA", "CIT", "FLC", "DTT", "BME", "SIN", "MLI", "BTB", "POP",
    "CPS", "CHAPSO", "CXS", "NHE", "EPE", "HEZ",
    # análogos de nucleótido: marcan el sitio del cofactor, no el de un fármaco.
    # Medido: `ANP` (AMP-PNP) daba «sitio_confirmado» en 8UKP, cuyo ensayo es el
    # sitio de dihidropiridinas del canal de Ca²⁺ — otro bolsillo. En una quinasa
    # el sitio del ATP sí es el de los inhibidores, pero AMP-PNP tampoco es uno:
    # la estructura que vale es la que trae el inhibidor.
    "ANP", "ACP", "AGS", "GNP", "GSP", "ADX", "APC", "ATR",
    # lípidos, esteroles y ácidos grasos de membrana
    "OLC", "OLA", "PLM", "MYR", "STE", "PTY", "3PE", "POV", "PX4", "D10", "HP6",
    "CLR", "CHS", "Y01",
    # vistos con su nombre en los candidatos del panel, uno a uno:
    "PX2",    # 1,2-dilauroil-sn-glicero-3-fosfato
    "PGW",    # fosfatidilglicerol
    "PIO", "J40",   # fosfoinosítidos
    "Q3G",    # fosfatidilserina
    "A1EFM",  # fosfolípido de cadena corta
    "DGA",    # diacilglicerol
    "8K6", "MYS", "TRD",   # octadecano, pentadecano, tridecano
    "12P",    # dodecaetilenglicol
    "VSN",    # análogo de GDP con tiofosfato
    # detergentes
    "LMT", "LDA", "LMN", "BOG", "BNG", "C8E", "CXE", "DDQ", "TWT", "SDS", "R16",
    "DCX",    # óxido de decil(dimetil)fosfina
    # glicanos
    "NAG", "NDG", "BMA", "MAN", "GAL", "FUC", "BGC", "GLC", "XYP", "SIA", "A2G", "NGA",
    # entrecruzadores y reactivos de marcaje: no son fármaco
    "8VY", "MTS", "IOA", "EMA",
    # sin identidad química declarada: no se puede acoplar ni citar
    "UNL", "UNX", "UNK", "DUM",
})

#: Segundo filtro, y el que de verdad cubre: fragmentos del **nombre que declara
#: el CCD**. La lista de códigos de arriba es un suelo escrito de memoria y se
#: queda corta con cada entrada nueva; esto es evidencia del propio RCSB.
NOMBRES_NO_FARMACO = (
    "phosphatidyl", "phosphocholine", "phosphoethanolamine", "phosphoglycerol",
    "monoolein", "cholesterol", "cholesteryl", "cholic acid", "sphingo", "ceramide",
    "maltoside", "glucoside", "glucopyranoside", "maltopyranoside", "detergent",
    "polyethylene glycol", "oxyethylene", "nonaethylene", "octaethylene",
    "myristic", "palmitic", "oleic", "stearic", "lauric", "decanoic", "dodecane",
    "hexadecane", "undecane", "tetradecane", "nonane", "octane ", "heptane",
    "digitonin", "lauryl", "decyl", "triton", "tween", "nonidet", "chaps",
    "phosphine oxide",
    # CHAPS entra por su nombre sistemático, no por la marca: 4UDD lo declara
    # «3-[(3-cholamidopropyl)dimethylammonio]-1-propanesulfonate».
    "cholamido",
    # tampones y análogos de nucleótido que el código no cubre
    "citrate", "tartrate", "phosphoaminophosphonic", "imidodiphosphate",
    "thiophosphate", "methylenediphosphonate", "propylsulfonic", "propanesulfonic",
    # cadenas de lípido y alcanos. «decane» cubre de un golpe dodecano,
    # tridecano, pentadecano y octadecano; «anoyloxy» cubre los ésteres de
    # ácido graso. No se filtra por «phospho» a secas: `L2Y` es un inhibidor
    # covalente real de la acetilcolinesterasa y caería con él.
    "glycero", "diacyl", "anoyloxy", "decane", "ethylene glycol",
    "bis(bromomethyl)", "bromomethyl)benzene", "maleimide", "iodoacetamide",
)


def descarte_no_farmacologico(comp_id: str, nombre: str | None) -> str | None:
    """Motivo por el que este HETATM no es el ligando farmacológico, o `None`.

    Si un lípido o un detergente pasa por ligando, el redocking «confirma» un
    sitio que no es el del fármaco y el panel afirma algo falso. Medido: el PTY
    de 8ZP2 (fosfatidiletanolamina, 700 Da, dentro de la ventana de masa) daba
    `sitio_confirmado` a 0,99 Å sobre un bolsillo lipídico del transportador de
    noradrenalina. Los cofactores se excluyen aparte, por plantilla.
    """
    if comp_id.upper() in NO_LIGANDOS:
        return f"{comp_id} está en la lista de componentes que no son fármaco"
    bajo = (nombre or "").lower()
    for marca in NOMBRES_NO_FARMACO:
        if marca in bajo:
            return f"el CCD nombra {comp_id} «{nombre}»: contiene «{marca.strip()}»"
    return None
USER_AGENT = "MolDesign/1.0.2 (panel Bowes 2012; contacto: repositorio público)"


def _pedir(url: str, reintentos: int = 4) -> dict | None:
    for intento in range(reintentos):
        try:
            peticion = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(peticion, timeout=60) as r:
                return json.load(r)
        except Exception as exc:  # noqa: BLE001 - se reintenta y se declara
            if intento == reintentos - 1:
                print(f"    ! {type(exc).__name__}: {str(exc)[:90]}", flush=True)
                return None
            time.sleep(2 * (intento + 1))
    return None


def accesion_humana(gen: str) -> dict | None:
    """Accesión UniProt revisada de ese gen en humano, con el nombre que declara."""
    consulta = urllib.parse.quote(f'gene_exact:{gen} AND organism_id:9606 AND reviewed:true')
    datos = _pedir("https://rest.uniprot.org/uniprotkb/search?query=" + consulta
                   + "&fields=accession,id,protein_name,gene_primary&size=5")
    for fila in (datos or {}).get("results", []):
        if (fila.get("genes") or [{}])[0].get("geneName", {}).get("value", "").upper() == gen.upper():
            nombre = (((fila.get("proteinDescription") or {}).get("recommendedName") or {})
                      .get("fullName") or {}).get("value")
            return {"accession": fila["primaryAccession"], "uniprot_id": fila.get("uniProtkbId"),
                    "protein_name": nombre, "gene": gen}
    return None


#: Métodos y resolución admitidos. La cryo-EM entra porque muchas dianas del
#: panel —canales, transportadores y varios GPCR— sólo existen así; el propio
#: 5VA1 (hERG) del catálogo es cryo-EM. Lo que decide es el redocking, no el método.
METODOS = ("X-RAY DIFFRACTION", "ELECTRON MICROSCOPY")
RESOLUCION_MAX_A = 3.5


def estructuras_de(accesion: str) -> list[str]:
    """PDB de esa accesión con método y resolución admitidos, mejor resolución primero."""
    consulta = {
        "query": {"type": "group", "logical_operator": "and", "nodes": [
            {"type": "terminal", "service": "text", "parameters": {
                "attribute": "rcsb_polymer_entity_container_identifiers."
                             "reference_sequence_identifiers.database_accession",
                "operator": "exact_match", "value": accesion}},
            {"type": "terminal", "service": "text", "parameters": {
                "attribute": "rcsb_polymer_entity_container_identifiers."
                             "reference_sequence_identifiers.database_name",
                "operator": "exact_match", "value": "UniProt"}},
            {"type": "group", "logical_operator": "or", "nodes": [
                {"type": "terminal", "service": "text", "parameters": {
                    "attribute": "exptl.method", "operator": "exact_match", "value": metodo}}
                for metodo in METODOS]},
            {"type": "terminal", "service": "text", "parameters": {
                "attribute": "rcsb_entry_info.resolution_combined",
                "operator": "less_or_equal", "value": RESOLUCION_MAX_A}},
        ]},
        "return_type": "entry",
        "request_options": {"paginate": {"start": 0, "rows": 60},
                            "sort": [{"sort_by": "rcsb_entry_info.resolution_combined",
                                      "direction": "asc"}]},
    }
    cuerpo = json.dumps(consulta).encode()
    peticion = urllib.request.Request(
        "https://search.rcsb.org/rcsbsearch/v2/query", data=cuerpo,
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT})
    for intento in range(4):
        try:
            with urllib.request.urlopen(peticion, timeout=60) as r:
                datos = json.load(r)
            return [f["identifier"] for f in datos.get("result_set", [])]
        except json.JSONDecodeError:
            return []                                  # cuerpo vacío: sin resultados
        except Exception as exc:  # noqa: BLE001
            if getattr(exc, "code", None) == 204:      # sin resultados
                return []
            if intento == 3:
                print(f"    ! RCSB {type(exc).__name__}: {str(exc)[:90]}", flush=True)
                return []
            time.sleep(2 * (intento + 1))
    return []


def ligandos_de(pdb_id: str) -> tuple[list[dict], dict]:
    """Ligandos drug-like de la entrada, con su masa y su código, y cómo se resolvió."""
    datos = _pedir(f"https://data.rcsb.org/rest/v1/core/entry/{pdb_id}")
    if not datos:
        return [], {}
    estructura = {
        "metodo": (datos.get("exptl") or [{}])[0].get("method"),
        "resolucion_A": ((datos.get("rcsb_entry_info") or {}).get("resolution_combined") or [None])[0],
        "titulo": (datos.get("struct") or {}).get("title"),
    }
    ligandos = []
    for comp_id in (datos.get("rcsb_entry_container_identifiers") or {}).get("non_polymer_entity_ids", []):
        entidad = _pedir(f"https://data.rcsb.org/rest/v1/core/nonpolymer_entity/{pdb_id}/{comp_id}")
        ident = ((entidad or {}).get("pdbx_entity_nonpoly") or {})
        codigo = ident.get("comp_id")
        if not codigo:
            continue
        info = _pedir(f"https://data.rcsb.org/rest/v1/core/chemcomp/{codigo}")
        quimica = ((info or {}).get("chem_comp") or {})
        # El nombre del CCD manda sobre el de la entidad: es el que se cita.
        nombre = quimica.get("name") or ident.get("name")
        descarte = descarte_no_farmacologico(codigo, nombre)
        if descarte:
            print(f"    - {codigo} descartado: {descarte}", flush=True)
            continue
        masa = quimica.get("formula_weight")
        if masa is None or not (150.0 <= float(masa) <= 900.0):
            continue
        ligandos.append({"comp_id": codigo, "name": nombre, "formula_weight": masa})
    return ligandos, estructura


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 2)[1])
    parser.add_argument("--write", action="store_true", required=True)
    parser.add_argument("--solo", default="",
                        help="genes a re-seleccionar; el resto del archivo se conserva")
    parser.add_argument("--max-candidatos", type=int, default=6,
                        help="estructuras con ligando que se anotan por diana")
    args = parser.parse_args()
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    salida = {"_doc": ("Candidatos para el panel de Bowes 2012. Generado por "
                       "scripts/bowes44_seleccionar_estructuras.py; la validación (caja, "
                       "preparación y redocking) la hace bowes44_validar_estructuras.py."),
              "referencia": "Bowes et al. 2012, Nat Rev Drug Discov 11:909-922, tabla 1",
              "filtros": {"organismo": "Homo sapiens (UniProt revisada)",
                          "metodos": list(METODOS), "resolucion_max_A": RESOLUCION_MAX_A,
                          "ligando": "no polimérico, 150-900 Da, fuera de la lista de tampones"},
              "dianas": []}
    # Re-seleccionar unas pocas dianas conserva lo ya medido de las demás: el
    # archivo se reescribe entero, así que lo anterior hay que traerlo.
    solo = {s.strip().upper() for s in (args.solo or "").split(",") if s.strip()}
    previas: dict[str, dict] = {}
    if solo and DESTINO.is_file():
        anterior = json.loads(DESTINO.read_text(encoding="utf-8"))
        previas = {d["assay"]: d for d in anterior.get("dianas") or []}
        salida["filtros"] = anterior.get("filtros", salida["filtros"])
    for etiqueta, familia, gen in PANEL:
        if solo and (gen or "").upper() not in solo:
            # Nunca se re-selecciona lo que no se pidió: si falta en el archivo
            # anterior, se declara en vez de medirlo a escondidas.
            salida["dianas"].append(previas.get(etiqueta) or {
                "assay": etiqueta, "familia": familia, "gen": gen, "candidatos": [],
                "nota": "no medida en esta corrida (--solo) y ausente del archivo anterior",
            })
            continue
        fila: dict = {"assay": etiqueta, "familia": familia, "gen": gen, "candidatos": []}
        print(f"{etiqueta} ({gen})", flush=True)
        if gen is None:
            fila["nota"] = "la ficha no identifica el subtipo; hay que fijarlo a mano"
            salida["dianas"].append(fila)
            continue
        acc = accesion_humana(gen)
        if acc is None:
            fila["nota"] = "sin accesión UniProt revisada para ese gen en humano"
            salida["dianas"].append(fila)
            continue
        fila["uniprot"] = acc
        for pdb_id in estructuras_de(acc["accession"]):
            ligandos, estructura = ligandos_de(pdb_id)
            if not ligandos:
                continue
            fila["candidatos"].append({"pdb_id": pdb_id, **estructura, "ligandos": ligandos})
            print(f"    {pdb_id} ({estructura.get('metodo')}, {estructura.get('resolucion_A')} Å): "
                  f"{[l['comp_id'] for l in ligandos]}", flush=True)
            if len(fila["candidatos"]) >= args.max_candidatos:
                break
        if not fila["candidatos"]:
            fila["nota"] = (f"sin estructura {'/'.join(METODOS)} ≤{RESOLUCION_MAX_A} Å "
                            "con ligando drug-like")
        salida["dianas"].append(fila)

    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    DESTINO.write_text(json.dumps(salida, ensure_ascii=False, indent=1) + "\n",
                       encoding="utf-8", newline="\n")
    con = sum(1 for d in salida["dianas"] if d["candidatos"])
    print(f"\n{con}/{len(PANEL)} dianas con candidato; escrito {DESTINO.relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
