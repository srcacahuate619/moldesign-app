#!/usr/bin/env python3
r"""Valida cada candidato del panel de Bowes 2012 acoplando su propio ligando.

# Qué mide, y qué NO

Para cada estructura candidata de `bowes44_candidatos.json`:

1. descarga el PDB del RCSB y lo guarda comprimido en `data/targets/`;
2. deriva la caja del **ligando cocristalizado** (centroide y extensión + margen);
3. prepara el receptor con la misma ruta del producto (`prepare_target`), lo que
   incluye la unidad biológica, el truncado de cadenas laterales incompletas y
   las plantillas locales de cofactores;
4. **reacopla ese mismo ligando con Vina** y mide dos cosas distintas.

Las dos cifras responden preguntas distintas y sólo la primera decide:

- **distancia entre centroides** (primera pose contra el ligando cristalizado):
  mide si la caja y el receptor describen la cavidad de ese ligando. Valida la
  ESTRUCTURA, y es el criterio de admisión (`SITIO_MAX_A`).
- **RMSD simétrico**: mide si **Vina** reproduce la pose. Se informa como
  `pose_reproducida` y **nunca decide**, porque un fallo ahí es un fallo del
  motor, no de la estructura. Medido: ZM-241385 en A2A queda a 2,6 Å de
  centroide con 9,2 Å de RMSD — girado dentro de la misma cavidad.

**Ninguna de las dos demuestra que el sitio sea el farmacológicamente
relevante.** Una estructura
puede traer un ligando en un dominio accesorio y reacoplarlo perfectamente: es
lo que pasó con hERG, donde 4HQA y 1BYW son el dominio PAS y no el poro
(DOCK-016). Por eso el panel sale con `sitio_adjudicado: false`: la
adjudicación del sitio la hace una persona, y queda escrita.

# Uso

    python scripts/bowes44_validar_estructuras.py --write [--solo A2A,CB1] [--max-por-diana 2]
"""

from __future__ import annotations

import argparse
import asyncio
import gzip
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
CANDIDATOS = RAIZ / "docs" / "auditorias" / "ae4db6a" / "bowes44_candidatos.json"
DESTINO = RAIZ / "docs" / "auditorias" / "ae4db6a" / "bowes44_validacion.json"
ESTRUCTURAS = RAIZ / "data" / "targets"
USER_AGENT = "MolDesign/1.0.2 (panel Bowes 2012; contacto: repositorio público)"

#: Margen (Å) que se añade a la extensión del ligando para formar la caja. 8 Å es
#: lo que usa el catálogo curado y deja sitio a la solvatación y a los rotámeros.
MARGEN_CAJA_A = 8.0
#: La caja no baja de esto ni sube de aquí: fuera de rango el preflight la rechaza.
CAJA_MIN_A, CAJA_MAX_A = 18.0, 40.0
#: Dos criterios distintos, y el panel sólo exige el primero:
#:
#: `SITIO_MAX_A` — cuánto puede alejarse el centroide de la primera pose del
#: centroide del ligando cristalizado para aceptar que la caja describe SU sitio.
#: Es lo que valida la estructura. 4 Å es menos de la mitad del tamaño de un
#: ligando de fármaco: la pose ocupa la misma cavidad.
#:
#: `RMSD_MAX_A` — cuánto se parece la pose a la cristalográfica. Es el criterio
#: clásico de exactitud de docking, y mide a **Vina**, no a la estructura: con
#: ZM-241385 en A2A (5IU4) el centroide cae a 2,6 Å pero el RMSD es 8,7 porque la
#: molécula, alargada, queda girada en la misma cavidad. Exigirlo dejaría fuera
#: sitios correctos, así que se informa y no decide.
SITIO_MAX_A = 4.0
RMSD_MAX_A = 2.0

os.environ.setdefault("MOLDESIGN_TESTING", "1")
# `MOLDESIGN_TESTING` sólo aísla `directorio_de_datos`; los receptores preparados
# pasan por `utils.local_storage`, que lee `settings.local_data_dir` y por defecto
# es `~/MolDesign/data`. Sin esto, validar el panel dejaba 44 receptores dentro de
# los datos del investigador — la misma clase de fuga que el smoke de producción
# tuvo con `molgraph.db`.
os.environ.setdefault("LOCAL_DATA_DIR", str(RAIZ / ".tmp" / "bowes" / "data"))
sys.path[:0] = [str(RAIZ / "backend"), str(RAIZ), str(Path(__file__).resolve().parent)]

from bowes44_seleccionar_estructuras import descarte_no_farmacologico  # noqa: E402


def descargar_pdb(pdb_id: str) -> Path:
    """Guarda `data/targets/<ID>.pdb.gz` si no está ya, y devuelve su ruta."""
    destino = ESTRUCTURAS / f"{pdb_id.upper()}.pdb.gz"
    if destino.is_file():
        return destino
    try:
        url = f"https://files.rcsb.org/download/{pdb_id.upper()}.pdb"
        peticion = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(peticion, timeout=120) as r:
            contenido = r.read()
        if not contenido.startswith(b"HEADER") and b"ATOM" not in contenido[:4000]:
            raise RuntimeError("el RCSB no devolvió un PDB")
    except Exception:  # noqa: BLE001 - se intenta el mmCIF, que es el formato vigente
        # Las entradas grandes o recientes ya sólo se publican en mmCIF. gemmi
        # las convierte sin red; el resto del producto trabaja sobre PDB.
        import gemmi

        url = f"https://files.rcsb.org/download/{pdb_id.upper()}.cif"
        peticion = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(peticion, timeout=180) as r:
            cif = r.read()
        with tempfile.TemporaryDirectory() as tmp:
            ruta_cif = Path(tmp) / f"{pdb_id}.cif"
            ruta_cif.write_bytes(cif)
            estructura = gemmi.read_structure(str(ruta_cif))
            estructura.setup_entities()
            if len(estructura) > 1:
                del estructura[1:]            # sólo el primer modelo
            contenido = estructura.make_pdb_string().encode("utf-8")
        if b"ATOM" not in contenido[:200000]:
            raise RuntimeError(f"{pdb_id}: ni PDB ni mmCIF convertible")
    destino.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(destino, "wb", compresslevel=9) as fh:
        fh.write(contenido)
    return destino


def leer(pdb_id: str) -> str:
    with gzip.open(ESTRUCTURAS / f"{pdb_id.upper()}.pdb.gz", "rt", encoding="utf-8",
                   errors="replace") as fh:
        return fh.read()


#: `HET` con código CCD de más de tres caracteres; ver `het_de_codigo_largo`.
_HET_LARGO = re.compile(
    r"^(?P<codigo>\S{4,})\s+(?P<cadena>\S)\s*(?P<numero>\d+)")


def het_de_codigo_largo(texto: str) -> dict[tuple[str, str], str]:
    r"""Residuos cuyo código CCD no cabe en el formato PDB, por (cadena, número).

    El campo `resName` del PDB clásico tiene **tres columnas**, y desde 2023 el
    CCD emite códigos de cinco caracteres (`A1D5J` = ambrisentán en 8XVK). Al
    convertir mmCIF→PDB, gemmi escribe el código completo en el registro `HET`
    y **trunca a tres** el de cada `HETATM`, así que buscar por nombre no
    encuentra nada y dos códigos con el mismo prefijo colisionarían.

    Se casa por `(cadena, número de residuo)`, que sí es exacto.
    """
    mapa: dict[tuple[str, str], str] = {}
    for line in texto.splitlines():
        if not line.startswith("HET "):
            continue
        # El número de residuo puede venir pegado a la cadena («R1201», sin hueco
        # para cuatro dígitos) o separado («R 401»): las dos formas salen de gemmi.
        casa = _HET_LARGO.match(line[7:])
        if casa:
            mapa[(casa.group("cadena"), casa.group("numero"))] = casa.group("codigo")
    return mapa


def instancias_del_ligando(texto: str, comp_id: str) -> dict[tuple[str, str], list[tuple]]:
    """Átomos pesados de cada copia del ligando, por (cadena, número de residuo)."""
    # El mapa se construye siempre, también para un `comp_id` de tres caracteres:
    # si no, pedir «A1D» casaría los HETATM truncados de A1D5J y A1D67 a la vez
    # y devolvería dos ligandos distintos como si fueran copias de uno.
    largos = het_de_codigo_largo(texto)
    copias: dict[tuple[str, str], list[tuple]] = {}
    for line in texto.splitlines():
        if not line.startswith("HETATM") or len(line) < 54:
            continue
        sitio = (line[21:22].strip() or "A", line[22:26].strip())
        if largos.get(sitio, line[17:20].strip()) != comp_id:
            continue
        if len(line) >= 78 and line[76:78].strip() in ("H", "D"):
            continue
        try:
            pos = tuple(float(line[i:i + 8]) for i in (30, 38, 46))
        except ValueError:
            continue
        copias.setdefault((line[21:22].strip() or "A", line[22:26].strip()), []).append(
            (line[12:16].strip(), pos, line[76:78].strip()))
    return copias


def caja_del_ligando(atomos: list[tuple]) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    coords = [a[1] for a in atomos]
    centro = tuple(round(sum(c[i] for c in coords) / len(coords), 3) for i in range(3))
    lado = max(max(c[i] for c in coords) - min(c[i] for c in coords) for i in range(3)) + MARGEN_CAJA_A
    lado = round(min(max(lado, CAJA_MIN_A), CAJA_MAX_A), 1)
    return centro, (lado, lado, lado)


def cadenas_del_sitio(texto: str, atomos: list[tuple], umbral: float = 4.5) -> list[str]:
    """Cadenas con algún átomo proteico a ≤4,5 Å del ligando (evidencia fuerte)."""
    coords = [a[1] for a in atomos]
    cerca: dict[str, int] = {}
    for line in texto.splitlines():
        if not line.startswith("ATOM") or len(line) < 54:
            continue
        try:
            pos = tuple(float(line[i:i + 8]) for i in (30, 38, 46))
        except ValueError:
            continue
        if any(math.dist(pos, c) <= umbral for c in coords):
            cadena = line[21:22].strip() or "A"
            cerca[cadena] = cerca.get(cadena, 0) + 1
    return [c for c, _ in sorted(cerca.items(), key=lambda kv: -kv[1])]


def sdf_ideal(comp_id: str, destino: Path) -> tuple[Path, str]:
    """SDF ideal del CCD: la topología del ligando, con sus órdenes de enlace.

    Se acopla esta molécula, no las coordenadas del cristal: Vina genera la
    conformación y el cristal sólo sirve de referencia para el RMSD. Sacar la
    topología del PDB obligaría a adivinar los enlaces.
    """
    ruta = destino / f"{comp_id}_ideal.sdf"
    if not ruta.is_file():
        url = f"https://files.rcsb.org/ligands/download/{comp_id}_ideal.sdf"
        peticion = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(peticion, timeout=120) as r:
            ruta.write_bytes(r.read())
    return ruta, hashlib.sha256(ruta.read_bytes()).hexdigest()


def centroides_de_pdbqt(texto: str) -> list[tuple[float, float, float]]:
    """Centroide de los átomos pesados de cada MODEL del PDBQT de salida."""
    centroides, actual = [], []
    for line in texto.splitlines():
        if line.startswith("MODEL"):
            actual = []
        elif line.startswith(("ATOM", "HETATM")) and len(line) >= 79:
            if line[77:79].strip() in ("H", "HD", "D"):
                continue
            try:
                actual.append(tuple(float(line[i:i + 8]) for i in (30, 38, 46)))
            except ValueError:
                continue
        elif line.startswith("ENDMDL") and actual:
            centroides.append(tuple(sum(a[i] for a in actual) / len(actual) for i in range(3)))
            actual = []
    return centroides


def rmsd_de_redocking(pdbqt_poses: str, ligando_cristal: list[tuple], sdf_ideal_texto: str
                      ) -> tuple[list[float | None], str | None]:
    """RMSD simétrico de cada pose contra el ligando cristalográfico, sin alinear.

    Usa `RDKitMolCreate` de Meeko para reconstruir las poses desde el PDBQT —la
    misma exportación que el producto, auditada como fiel al grafo— y
    `rdMolAlign.CalcRMS`, que considera la simetría topológica. Un RMSD por
    emparejamiento greedy inflaba la cifra en moléculas simétricas y habría
    descartado sitios correctos.

    La referencia se construye con la topología del SDF ideal y las coordenadas
    del cristal: si no encajan (número de átomos pesados distinto, por ejemplo
    porque el cristal tiene el ligando incompleto) devuelve el motivo.
    """
    from meeko import PDBQTMolecule, RDKitMolCreate
    from rdkit import Chem
    from rdkit.Chem import rdMolAlign

    plantilla = Chem.MolFromMolBlock(sdf_ideal_texto, removeHs=True)
    if plantilla is None:
        return [], "el SDF ideal del CCD no se pudo leer"
    pesados_cristal = [a for a in ligando_cristal if (a[2] or "").upper() not in ("H", "D")]
    if plantilla.GetNumAtoms() != len(pesados_cristal):
        return [], (f"el cristal trae {len(pesados_cristal)} átomos pesados y la definición del CCD "
                    f"{plantilla.GetNumAtoms()}: ligando incompleto o alterado")
    # La referencia se construye desde el PDB del cristal y se le asignan los
    # órdenes de enlace por subestructura contra el SDF ideal. Suponer que ambos
    # comparten el orden de átomos del CCD daba RMSD sin sentido (8,65 Å para el
    # ZM-241385 de A2A, cuyo sitio es correcto).
    from rdkit.Chem import AllChem

    bloque = "\n".join(
        f"HETATM{i + 1:5d} {nombre:<4}{'LIG':>4} A   1    "
        f"{pos[0]:8.3f}{pos[1]:8.3f}{pos[2]:8.3f}  1.00  0.00          {(elem or nombre[0]):>2}"
        for i, (nombre, pos, elem) in enumerate(pesados_cristal)
    ) + "\nEND\n"
    crudo = Chem.MolFromPDBBlock(bloque, removeHs=True, proximityBonding=True, sanitize=False)
    if crudo is None:
        return [], "el ligando del cristal no se pudo leer como molécula"
    try:
        referencia = AllChem.AssignBondOrdersFromTemplate(plantilla, crudo)
    except Exception as exc:  # noqa: BLE001 - topología del cristal que no encaja
        return [], (f"el ligando del cristal no coincide con la definición del CCD "
                    f"({type(exc).__name__}): ¿incompleto o con otra conectividad?")

    poses = RDKitMolCreate.from_pdbqt_mol(PDBQTMolecule(pdbqt_poses, is_dlg=False, skip_typing=True))
    if not poses or poses[0] is None:
        return [], "Meeko no pudo reconstruir las poses del PDBQT"
    molecula = Chem.RemoveHs(poses[0])
    salida: list[float | None] = []
    for conformero in range(molecula.GetNumConformers()):
        una = Chem.Mol(molecula)
        una.RemoveAllConformers()
        una.AddConformer(Chem.Conformer(molecula.GetConformer(conformero)), assignId=True)
        try:
            salida.append(round(rdMolAlign.CalcRMS(una, referencia), 2))
        except Exception:  # noqa: BLE001 - topologías que no encajan
            salida.append(None)
    return salida, None


async def validar(pdb_id: str, comp_id: str, tmp: Path) -> dict:
    """Prepara el receptor, reacopla el ligando cristalizado y mide el RMSD."""
    from services.docking.preparer import prepare_target
    from utils.local_storage import path_for

    texto = leer(pdb_id)
    copias = instancias_del_ligando(texto, comp_id)
    if not copias:
        return {"estado": "sin_ligando", "detalle": f"{comp_id} no aparece como HETATM en {pdb_id}"}
    (cadena_lig, num_lig), atomos = max(copias.items(), key=lambda kv: len(kv[1]))
    centro, tamano = caja_del_ligando(atomos)
    sitio = cadenas_del_sitio(texto, atomos)
    if not sitio:
        return {"estado": "sitio_sin_contactos",
                "detalle": f"ningún átomo proteico a 4,5 Å de {comp_id} {cadena_lig}{num_lig}"}
    try:
        ruta = await prepare_target(pdb_id, sitio[0], centro, tamano, force_reprepare=True,
                                    cofactors_whitelist=[], site_chains=sitio, site_ligand=comp_id)
    except Exception as exc:  # noqa: BLE001 - se declara
        return {"estado": "no_preparable", "paso": getattr(exc, "step", None),
                "detalle": str(getattr(exc, "detail", exc))[-400:],
                "caja": {"centro": centro, "tamano": tamano}, "site_chains": sitio}

    receptor = Path(path_for(ruta))
    try:
        lig_sdf, sdf_sha = sdf_ideal(comp_id, tmp)
    except Exception as exc:  # noqa: BLE001 - se declara y se pasa al siguiente
        return {"estado": "sin_sdf_ideal", "detalle": f"{type(exc).__name__}: {exc}"[:200],
                "caja": {"centro": centro, "tamano": tamano}, "site_chains": sitio}
    lig_pdbqt = tmp / f"{comp_id}.pdbqt"
    r = subprocess.run([sys.executable, "-m", "meeko.cli.mk_prepare_ligand",
                        "-i", str(lig_sdf), "-o", str(lig_pdbqt)],
                       capture_output=True, text=True, timeout=600)
    if not lig_pdbqt.is_file():
        return {"estado": "ligando_no_preparable", "detalle": (r.stderr or r.stdout)[-300:],
                "caja": {"centro": centro, "tamano": tamano}, "site_chains": sitio}

    salida = tmp / f"{pdb_id}_{comp_id}_out.pdbqt"
    vina = RAIZ / "tools" / "vina" / "vina.exe"
    cmd = [str(vina), "--receptor", str(receptor), "--ligand", str(lig_pdbqt),
           "--center_x", str(centro[0]), "--center_y", str(centro[1]), "--center_z", str(centro[2]),
           "--size_x", str(tamano[0]), "--size_y", str(tamano[1]), "--size_z", str(tamano[2]),
           "--exhaustiveness", "16", "--seed", "42", "--num_modes", "9", "--out", str(salida)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    if r.returncode != 0 or not salida.is_file():
        return {"estado": "vina_falló", "detalle": (r.stderr or r.stdout)[-300:],
                "caja": {"centro": centro, "tamano": tamano}, "site_chains": sitio}

    rmsds, motivo_rmsd = rmsd_de_redocking(
        salida.read_text(encoding="utf-8", errors="replace"), atomos,
        lig_sdf.read_text(encoding="utf-8", errors="replace"))
    afinidades = [float(l.split()[3]) for l in salida.read_text(errors="replace").splitlines()
                  if l.startswith("REMARK VINA RESULT")]
    validos = [(i, d) for i, d in enumerate(rmsds) if d is not None]
    mejor = min(validos, key=lambda x: x[1]) if validos else None
    centroides = centroides_de_pdbqt(salida.read_text(encoding="utf-8", errors="replace"))
    centro_cristal = tuple(sum(a[1][i] for a in atomos) / len(atomos) for i in range(3))
    dist_sitio = round(math.dist(centroides[0], centro_cristal), 2) if centroides else None
    en_el_sitio = dist_sitio is not None and dist_sitio <= SITIO_MAX_A
    return {
        "estado": "sitio_confirmado" if en_el_sitio else "pose_fuera_del_sitio",
        "pose_reproducida": bool(rmsds and rmsds[0] is not None and rmsds[0] <= RMSD_MAX_A),
        "distancia_centroides_A": dist_sitio,
        "detalle": motivo_rmsd,
        "caja": {"centro": centro, "tamano": tamano},
        "site_chains": sitio, "site_ligand": comp_id,
        "ligando_cadena": f"{cadena_lig}{num_lig}", "atomos_pesados_ligando": len(atomos),
        "receptor_sha256": hashlib.sha256(receptor.read_bytes()).hexdigest(),
        "sdf_ideal_sha256": sdf_sha,
        "afinidad_mejor_kcal": afinidades[0] if afinidades else None,
        "rmsd_pose1_A": rmsds[0] if rmsds else None,
        "rmsd_mejor_A": None if mejor is None else mejor[1],
        "rmsd_mejor_pose": None if mejor is None else mejor[0] + 1,
        "poses": len(rmsds),
    }


async def principal(args) -> int:
    datos = json.loads(CANDIDATOS.read_text(encoding="utf-8"))
    solo = {s.strip().upper() for s in (args.solo or "").split(",") if s.strip()}
    salida = {"_doc": ("Validación del panel de Bowes 2012: caja del ligando cocristalizado, "
                       "preparación con la ruta del producto y redocking de ese ligando. "
                       "Generado por scripts/bowes44_validar_estructuras.py."),
              "criterios": {"sitio_max_A": SITIO_MAX_A, "rmsd_max_A": RMSD_MAX_A, "margen_caja_A": MARGEN_CAJA_A,
                            "vina": {"exhaustiveness": 16, "seed": 42, "num_modes": 9},
                            "rmsd": "asignación greedy por elemento: cota superior del RMSD real"},
              "dianas": []}
    if DESTINO.is_file() and solo:
        anterior = json.loads(DESTINO.read_text(encoding="utf-8"))
        salida["dianas"] = [d for d in anterior.get("dianas", [])
                            if (d.get("gen") or "").upper() not in solo]
    with tempfile.TemporaryDirectory(dir=str(RAIZ / "tmp") if (RAIZ / "tmp").is_dir() else None) as tmp:
        for diana in datos["dianas"]:
            gen = (diana.get("gen") or "")
            if solo and gen.upper() not in solo:
                continue
            fila = {"assay": diana["assay"], "familia": diana["familia"], "gen": gen or None,
                    "uniprot": diana.get("uniprot"), "nota": diana.get("nota"), "estructuras": []}
            print(f"\n{diana['assay']} ({gen})", flush=True)
            for candidato in diana["candidatos"][:args.max_por_diana]:
                pdb_id = candidato["pdb_id"]
                try:
                    descargar_pdb(pdb_id)
                except Exception as exc:  # noqa: BLE001
                    fila["estructuras"].append({"pdb_id": pdb_id, "estado": "no_descargable",
                                                "detalle": f"{type(exc).__name__}: {exc}"[:200]})
                    print(f"  {pdb_id}: no descargable", flush=True)
                    continue
                # Un cofactor no es el ligando farmacológico: el FAD de la MAO-A
                # reacopla en su propio bolsillo y no dice nada del sitio de los
                # inhibidores. Los que tienen plantilla local son justo los cofactores.
                # Lo mismo con lípidos y detergentes de la membrana: medido, el
                # PTY de 8ZP2 daba «sitio_confirmado» a 0,99 Å sobre un bolsillo
                # lipídico del transportador de noradrenalina, no sobre el suyo.
                # La exclusión se aplica AQUÍ, no sólo al seleccionar, para que
                # un `bowes44_candidatos.json` anterior también quede filtrado.
                from services.docking.preparer import residuos_con_plantilla
                cofactores = residuos_con_plantilla()
                ligandos = []
                for l in candidato["ligandos"]:
                    motivo = (f"{l['comp_id']} es un cofactor con plantilla"
                              if l["comp_id"] in cofactores
                              else descarte_no_farmacologico(l["comp_id"], l.get("name")))
                    if motivo:
                        fila["estructuras"].append(
                            {"pdb_id": pdb_id, "estado": "no_es_farmaco",
                             "detalle": motivo, "ligando": l})
                        print(f"  {pdb_id} + {l['comp_id']}: descartado, {motivo}", flush=True)
                        continue
                    ligandos.append(l)
                for ligando in ligandos[:args.max_ligandos]:
                    resultado = await validar(pdb_id, ligando["comp_id"], Path(tmp))
                    resultado.update({"pdb_id": pdb_id, "metodo": candidato.get("metodo"),
                                      "resolucion_A": candidato.get("resolucion_A"),
                                      "titulo": candidato.get("titulo"),
                                      "ligando": ligando})
                    fila["estructuras"].append(resultado)
                    print(f"  {pdb_id} + {ligando['comp_id']}: {resultado['estado']}"
                          f" centroide={resultado.get('distancia_centroides_A')} Å rmsd={resultado.get('rmsd_pose1_A')}"
                          f" aff={resultado.get('afinidad_mejor_kcal')}", flush=True)
                    if resultado["estado"] == "sitio_confirmado":
                        break
                if any(e.get("estado") == "sitio_confirmado" for e in fila["estructuras"]):
                    break
            salida["dianas"].append(fila)
            DESTINO.write_text(json.dumps(salida, ensure_ascii=False, indent=1) + "\n",
                               encoding="utf-8", newline="\n")
    ok = sum(1 for d in salida["dianas"]
             if any(e.get("estado") == "sitio_confirmado" for e in d["estructuras"]))
    print(f"\n{ok}/{len(salida['dianas'])} dianas con el sitio confirmado")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 2)[1])
    parser.add_argument("--write", action="store_true", required=True)
    parser.add_argument("--solo", default="", help="genes a validar, separados por comas")
    parser.add_argument("--max-por-diana", type=int, default=3)
    parser.add_argument("--max-ligandos", type=int, default=2)
    args = parser.parse_args()
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    if not (RAIZ / "tools" / "vina" / "vina.exe").is_file():
        print("Falta tools/vina/vina.exe: la validación acopla de verdad.")
        return 2
    return asyncio.run(principal(args))


if __name__ == "__main__":
    sys.exit(main())
