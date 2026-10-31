"""Preparación de los receptores propios que NO usan la receta del catálogo.

``preparer.prepare_target`` delega aquí cuando el receptor tiene un perfil
(``services/targets/perfil_receptor.py``) con modo ``pdbqt`` o ``respetar``. El
catálogo no tiene perfil, así que nunca llega a este módulo y su receta 7 no se
toca.

Este archivo cubre el camino C (PDBQT listo para Vina). El camino B (respetar la
protonación y las especies del archivo) vive en ``preparer_respetando.py``.

# El contrato del informe

``vina_service`` lee de ``<receptor>.report.json`` lo mismo que de un receptor del
catálogo, así que el informe de un PDBQT propio lleva los mismos campos. Lo que
no se puede saber va en ``null`` y su motivo en ``no_disponible``; nunca se
rellena con un valor plausible.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from core.exceptions import ProteinPreparationError
from services.targets import pdbqt_propio
from services.targets.perfil_receptor import MODO_PDBQT, extras_del_informe
from utils.file_handlers import StoragePath
from utils.local_storage import exists, read_bytes, read_text, write_bytes, write_text
from utils.logger import get_logger

log = get_logger(__name__)

#: Elemento químico de cada tipo de átomo AutoDock, para reconstruir un PDB desde un PDBQT.
_ELEMENTO_DE_TIPO = {
    "A": "C", "C": "C", "N": "N", "NA": "N", "OA": "O", "SA": "S", "S": "S", "HD": "H", "H": "H",
    "P": "P", "F": "F", "I": "I", "Cl": "CL", "Br": "BR", "Zn": "ZN", "Fe": "FE", "Mg": "MG",
    "Ca": "CA", "Mn": "MN", "Cu": "CU", "Na": "NA", "K": "K", "Ni": "NI", "Co": "CO", "Cd": "CD",
    "Hg": "HG", "Si": "SI", "At": "AT", "G0": "C", "W": "O",
}

_AMINOACIDOS = frozenset({
    "ALA", "ARG", "ASN", "ASP", "CYS", "GLN", "GLU", "GLY", "HIS", "ILE", "LEU", "LYS", "MET", "PHE",
    "PRO", "SER", "THR", "TRP", "TYR", "VAL", "HID", "HIE", "HIP", "CYX", "CYM", "ASH", "GLH", "LYN",
    "ACE", "NME", "NMA", "NHE",
})

RECETA_PDBQT_VERSION = 1


def elemento_de_tipo(tipo: str) -> str | None:
    """El elemento de un tipo de átomo AutoDock conocido (``Zn`` → ZN, ``A`` → C), o None."""
    return _ELEMENTO_DE_TIPO.get(tipo)


def pdbqt_como_pdb(texto: str, *, con_hidrogenos: bool = False) -> str:
    """Un PDB clásico con los mismos átomos que un PDBQT (sin cargas ni tipos AutoDock).

    Sirve para dos cosas: contar especies con las mismas funciones que usa el resto del
    producto y escribir la copia que consumen el rescoring y la validación física.
    Es una reconstrucción, no el archivo de origen: el elemento sale del tipo de átomo
    (``A`` → C, ``OA`` → O, ``Zn`` → ZN).
    """
    salida: list[str] = []
    for linea in texto.splitlines():
        if not linea.startswith(("ATOM", "HETATM")) or len(linea) < 54:
            continue
        tipo = pdbqt_propio._tipo(linea)
        elemento = _ELEMENTO_DE_TIPO.get(tipo, tipo.upper()[:2])
        if elemento == "H" and not con_hidrogenos:
            continue
        residuo = linea[17:20].strip()
        registro = "ATOM  " if residuo in _AMINOACIDOS else "HETATM"
        cuerpo = linea[6:66] if len(linea) >= 66 else linea[6:].ljust(60)
        salida.append(f"{registro}{cuerpo}          {elemento:>2}")
    return "\n".join(salida) + ("\n" if salida else "")


def receta_pdbqt(perfil: dict[str, Any], center, size) -> str:
    """La identidad del receptor preparado: el PDBQT, su origen y la caja con que se audita."""
    documento = {
        "version": RECETA_PDBQT_VERSION,
        "modo": MODO_PDBQT,
        "receptor_sha256": perfil["receptor_sha256"],
        "origen_sha256": (perfil.get("origen") or {}).get("sha256_contenido"),
        "box_center": [round(float(v), 3) for v in center],
        "box_size": [round(float(v), 3) for v in size],
    }
    canonico = json.dumps(documento, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonico.encode("ascii")).hexdigest()


def _no_disponible_sin_origen() -> dict[str, str]:
    motivo = (
        "Sin la estructura de origen no se puede saber qué se retiró al preparar este PDBQT: "
        "súbela junto al PDBQT para auditar."
    )
    return {
        "species_diff": motivo,
        "removed_residues": motivo,
        "truncated_sidechains": motivo,
        "backbone_gaps": motivo,
        "cofactors_outside_site": motivo,
        "protonation_templates": (
            "Un PDBQT no lleva el JSON de plantillas de Meeko: la protonación es la que declaró "
            "quien lo preparó y MolDesign no la puede comprobar."
        ),
    }


def _auditoria_con_origen(origen: str, pdbqt: str, center, size, cadenas: list[str]) -> dict[str, Any]:
    """Compara el origen contra el PDBQT con las mismas funciones que audita el catálogo."""
    from services.docking import preparer
    from services.docking.preflight import diff_de_especies_de_la_corrida

    pdb_del_pdbqt = pdbqt_como_pdb(pdbqt, con_hidrogenos=True)
    etiqueta = "+".join(cadenas) if cadenas else "A"
    species_diff = diff_de_especies_de_la_corrida(
        origen, pdb_del_pdbqt, cadenas=etiqueta, center=center, size=size, site_ligand=None,
    )
    # Residuos del origen (proteína de las cadenas del PDBQT) que no llegaron al PDBQT.
    del_origen = "\n".join(
        l for l in origen.splitlines()
        if l.startswith("ATOM") and ((l[21:22].strip() or "A") in set(cadenas or ["A"]))
    )
    retirados = preparer._residuos_eliminados(del_origen, pdb_del_pdbqt, center=center, size=size)
    truncadas = preparer.truncar_cadenas_laterales_incompletas(
        "\n".join(l for l in pdb_del_pdbqt.splitlines() if l.startswith("ATOM")) + "\n", center, size)[1]
    por_clave_origen: dict[tuple[str, str, str], set[str]] = {}
    for l in origen.splitlines():
        if l.startswith("ATOM") and len(l) >= 54:
            por_clave_origen.setdefault(
                (l[21:22].strip() or "A", l[22:26].strip(), l[26:27].strip()), set()).add(l[12:16].strip())
    for fila in truncadas:
        clave = (str(fila["chain"]), str(fila["residue_number"]), str(fila["insertion_code"]))
        presentes = por_clave_origen.get(clave, set())
        # True: el origen sí tenía esos átomos, así que se perdieron al preparar el PDBQT.
        fila["atoms_present_in_source"] = all(a in presentes for a in fila["atoms_missing"])
    huecos = preparer.huecos_del_esqueleto(pdb_del_pdbqt, origen, center, size)
    return {
        "species_diff": species_diff,
        "removed_residues": retirados,
        "truncated_sidechains": truncadas,
        "backbone_gaps": huecos,
    }


def construir_informe(
    perfil: dict[str, Any], pdbqt_texto: str, *, recipe_hash: str, center, size,
    origen_texto: str | None,
) -> dict[str, Any]:
    resumen = pdbqt_propio.analizar_pdbqt(pdbqt_texto)
    con_origen = origen_texto is not None
    informe: dict[str, Any] = {
        "recipe_hash": recipe_hash,
        "receptor_sha256": perfil["receptor_sha256"],
        "modo_de_preparacion": "pdbqt_con_origen" if con_origen else "pdbqt_sin_origen",
        # El PDBQT no trae el JSON parametrizado de Meeko: se declara vacío, no se inventa.
        "protonation_templates": {},
        "meeko_parameterized_json_sha256": None,
        "cofactor_templates_sha256": None,
        "cofactors_outside_site": None,
        "meeko_reported_residues": [],
        "protonation_method": (
            "Declarada por quien preparó el PDBQT; MolDesign no la comprueba (no hay informe de la "
            "herramienta que lo preparó ni pH declarado)"
        ),
        "protonacion_declarada": {
            "origen": "usuario",
            "verificada": False,
            "motivo": "El PDBQT se usa tal cual; no pasa por Meeko ni se vuelve a protonar.",
        },
        "pdbqt": resumen.como_dict(),
        **{k: v for k, v in extras_del_informe(perfil["pdb_id"], texto=pdbqt_texto, center=center, size=size).items()
           if k != "modo_de_preparacion"},
    }
    if con_origen:
        informe.update(_auditoria_con_origen(origen_texto, pdbqt_texto, center, size, resumen.cadenas))
        informe["correspondencia_con_el_origen"] = perfil.get("correspondencia")
        informe["no_disponible"] = {
            "protonation_templates": _no_disponible_sin_origen()["protonation_templates"],
        }
    else:
        informe.update({
            "species_diff": None, "removed_residues": None,
            "truncated_sidechains": None, "backbone_gaps": None,
        })
        informe["no_disponible"] = _no_disponible_sin_origen()
    return informe


async def preparar_pdbqt(pdb_id: str, perfil: dict[str, Any], *, center, size) -> str:
    """Deja listo el PDBQT del usuario para esta caja y devuelve su ruta lógica.

    Es idempotente: si el receptor preparado y su informe ya existen para esta receta,
    los reutiliza. El contenido es SIEMPRE el que subió la persona.
    """
    receta = receta_pdbqt(perfil, center, size)
    ruta = StoragePath.target_prepared(pdb_id, receta)
    ruta_informe = ruta[:-6] + ".report.json"
    almacen = perfil["almacen"]
    contenido = await read_bytes(almacen["receptor"])
    if hashlib.sha256(contenido).hexdigest() != perfil["receptor_sha256"]:
        raise ProteinPreparationError(
            pdb_id=pdb_id, step="pdbqt_propio_alterado",
            detail="El PDBQT guardado ya no coincide con el hash registrado al subirlo; no se evalúa.",
        )
    if await exists(ruta) and await exists(ruta_informe):
        copia = await read_bytes(ruta)
        if hashlib.sha256(copia).hexdigest() != perfil["receptor_sha256"]:
            raise ProteinPreparationError(
                pdb_id=pdb_id, step="pdbqt_propio_alterado",
                detail="La copia preparada ya no coincide con el PDBQT subido; no se evalúa.",
            )
        return ruta
    texto = contenido.decode("utf-8", errors="replace")
    origen_texto = None
    if almacen.get("origen"):
        origen_texto = await read_text(almacen["origen"])
    informe = construir_informe(
        {**perfil, "pdb_id": pdb_id}, texto, recipe_hash=receta, center=center, size=size,
        origen_texto=origen_texto,
    )
    await write_text(ruta_informe, json.dumps(informe, sort_keys=True))
    await write_bytes(contenido, ruta)
    log.info("receptor_pdbqt_propio_listo", pdb_id=pdb_id, con_origen=origen_texto is not None,
             atomos=informe["pdbqt"]["atomos"])
    return ruta
