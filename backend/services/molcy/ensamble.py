"""Evidencia del ensamble para Molcy: de la corrida guardada al contrato `moldesign.ensamble/1`.

La escena «Ensamble» cuenta lo que el producto hizo con una evaluación en modo
ensamble: K conformaciones de entrada, K corridas independientes de Vina, UNA
piscina de poses reordenada por afinidad y los controles físicos de las entregadas.
Este módulo reúne esa evidencia **sin rehacer nada**: lee lo que la corrida guardó y
se abstiene —diciendo qué falta— cuando no puede demostrarlo.

Qué se demuestra y cómo:

- Cada pose entregada se recupera con `pose_recovery.recuperar_pose_agrupada`, que
  tiene seis puertas (procedencia, integridad del archivo y de la entrada, rank,
  identidad química y correspondencia geométrica). No se lee el SDF de la corrida
  «por rank»: una ruta y un número no demuestran que ese registro sea esa pose.
  Si UNA pose no pasa, no se monta el ensamble: contar nueve entregadas con ocho
  demostradas sería describir otra corrida.
- Las conformaciones que se enseñan son las que aportaron poses entregadas, con la
  geometría exacta que recibió Vina (su SHA-256 lo verificó la puerta G3).
- Los controles físicos salen de `structural_evidence` de la propia corrida, pose
  por pose y sólo si coinciden con ella (receptor y afinidad); «no evaluado» queda
  como «no evaluado», nunca como aprobado.

Lo que NO hace: no alinea nada que Vina vaya a recibir (la copia alineada es sólo
para ver, y el contrato lo declara), no mide energías que la corrida no guardó y no
inventa una trayectoria entre conformaciones.
"""
from __future__ import annotations

import asyncio
import hashlib
from typing import Any

from core.models import DockingPose
from services.chemistry.structural_evidence import (
    STAGE_FAILED,
    STAGE_NOT_EVALUATED,
    STAGE_PASSED,
    STAGE_REVIEW,
)
from services.docking.pose_recovery import PoseNoRecuperable, recuperar_pose_agrupada
from utils.local_storage import read_bytes

SCHEMA = "moldesign.ensamble/1"
CARPETA = "docking/ensamble"

#: Diedros que se miden en la geometría de entrada: enlaces simples, no anulares,
#: entre átomos pesados que no son terminales ni triples.
_ROTABLE = "[!$(*#*)&!D1]-&!@[!$(*#*)&!D1]"
#: Tope de coincidencias que se prueban al alinear (simetrías del ligando).
_MAX_COINCIDENCIAS = 500


class EnsambleNoDisponible(ValueError):
    """La corrida no conserva lo necesario para contar su ensamble; el mensaje dice qué."""


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ── ¿es un ensamble que se pueda contar? (barato: sin tocar el disco) ──────────
def es_ensamble(snap: dict) -> tuple[bool, str | None]:
    """Comprobación estructural del snapshot; la demostración real ocurre en `recoger`."""
    protocolo = snap.get("docking_protocol") or {}
    if int(protocolo.get("conformers_generated") or 1) < 2:
        return False, "La corrida no es un ensamble de conformaciones."
    procedencia = protocolo.get("execution_provenance") or {}
    if not procedencia.get("por_conformacion"):
        return False, ("La corrida no conserva la procedencia de cada conformación; "
                       "las evaluaciones de ensamble nuevas la guardan automáticamente.")
    poses = snap.get("docking_poses") or []
    if not poses or any(p.get("conformer_index") is None or not p.get("source_provenance")
                        for p in poses):
        return False, "Las poses entregadas no conservan de qué conformación salieron."
    return True, None


# ── controles físicos de la corrida, pose por pose ────────────────────────────
def controles_de(snap: dict, pose: dict) -> dict | None:
    """Los controles de ESA pose, o None si no se pueden atribuir con certeza."""
    evidencia = snap.get("structural_evidence")
    if not isinstance(evidencia, dict):
        return None
    # SCI-A-027. Antes se exigía `stage_status == "passed"` para conservar
    # CUALQUIER control, así que una corrida en `review` o en `failed` salía al
    # vídeo como «CONTROLES FÍSICOS: NO EVALUADOS». Eso convierte un fallo
    # medido en ausencia de medida, que es justo la mentira que este producto
    # existe para no contar: `failed` describe la pose, `not_evaluated` describe
    # al validador. Lo que decide si los controles se pueden atribuir a ESTA
    # pose es la identidad —mismo receptor, mismo rango, misma afinidad—, no su
    # veredicto, y esas comprobaciones siguen abajo intactas.
    #
    # La lista es blanca a propósito: son los cuatro estados que declara
    # `structural_evidence.STAGE_*`. Un estado que no esté ahí no se sabe leer,
    # y de lo que no se sabe leer no se exportan controles.
    if evidencia.get("stage_status") not in {STAGE_PASSED, STAGE_FAILED,
                                             STAGE_REVIEW, STAGE_NOT_EVALUATED}:
        return None
    if evidencia.get("receptor_sha256") != snap.get("receptor_sha256"):
        return None
    entrada = next((p for p in evidencia.get("poses") or []
                    if isinstance(p, dict) and p.get("rank") == pose["rank"]), None)
    if entrada is None:
        return None
    observada = entrada.get("observed_vina_affinity_kcal_mol")
    if not isinstance(observada, (int, float)) or abs(observada - pose["affinity"]) > 1e-6:
        return None
    if entrada.get("status") == "not_evaluated":
        return {"estado": "not_evaluated", "aprobadas": None, "pruebas": None,
                "fallos": [], "no_evaluados": 0, "motor": entrada.get("engine")}
    checks = [c for c in entrada.get("checks") or [] if isinstance(c, dict)]
    if not checks:
        return None
    estados = [str(c.get("estado")) for c in checks]
    return {"estado": entrada.get("status"),
            "aprobadas": estados.count("PASA"), "pruebas": len(checks),
            "fallos": [str(c.get("check")) for c in checks if c.get("estado") == "FALLA"],
            "no_evaluados": estados.count("NO_EVALUADO"), "motor": entrada.get("engine")}


# ── geometría: sólo RDKit, sin disco ni base de datos ─────────────────────────
def _primer_registro(sdf: bytes | str):
    from rdkit import Chem
    texto = sdf.decode("utf-8") if isinstance(sdf, bytes) else sdf
    mol = Chem.MolFromMolBlock(texto.split("$$$$")[0], removeHs=False)
    if mol is None or mol.GetNumConformers() == 0:
        raise EnsambleNoDisponible("Un SDF de la corrida no conserva una geometría 3D legible.")
    return mol


def _coincidencias(referencia, sonda) -> list[tuple[int, ...]]:
    """Cómo se corresponden los átomos pesados de la sonda con los de la referencia.

    Primero con enlaces y aromaticidad tal cual; si la exportación de Vina y la de
    RDKit no coinciden en órdenes de enlace, con el grafo solo. Sin correspondencia
    no se alinea: abstenerse es mejor que superponer átomos que no son los mismos.
    """
    from rdkit import Chem
    maximo = _MAX_COINCIDENCIAS
    hallados = referencia.GetSubstructMatches(sonda, uniquify=False, maxMatches=maximo)
    if hallados:
        return [tuple(m) for m in hallados]

    def grafo(mol):
        copia = Chem.RWMol(mol)
        for atomo in copia.GetAtoms():
            atomo.SetIsAromatic(False)
            atomo.SetFormalCharge(0)
            atomo.SetNoImplicit(True)
        for enlace in copia.GetBonds():
            enlace.SetBondType(Chem.BondType.SINGLE)
            enlace.SetIsAromatic(False)
        return copia.GetMol()

    return [tuple(m) for m in grafo(referencia).GetSubstructMatches(
        grafo(sonda), uniquify=False, maxMatches=maximo)]


def _alinear(referencia, sonda) -> float:
    """Superpone RÍGIDAMENTE `sonda` sobre `referencia` (en su sitio) y devuelve el RMSD.

    Sólo para poder comparar visualmente; no cambia ninguna geometría que Vina vea.
    """
    from rdkit.Chem import rdMolAlign, rdMolTransforms
    mejor = None
    for correspondencia in _coincidencias(referencia, sonda):
        mapa = list(enumerate(correspondencia))
        rmsd, matriz = rdMolAlign.GetAlignmentTransform(sonda, referencia, atomMap=mapa)
        if mejor is None or rmsd < mejor[0]:
            mejor = (rmsd, matriz)
    if mejor is None:
        raise EnsambleNoDisponible(
            "Una conformación no se corresponde átomo a átomo con las poses; no se alinea.")
    rdMolTransforms.TransformConformer(sonda.GetConformer(), mejor[1])
    return float(mejor[0])


def _diedros(mol_sin_h) -> list[dict[str, Any]]:
    """Todos los diedros de enlaces rotables, medidos por sus cuatro átomos reales."""
    from rdkit import Chem
    from rdkit.Chem import rdMolTransforms
    conformacion = mol_sin_h.GetConformer()
    patron = Chem.MolFromSmarts(_ROTABLE)

    def nombre(i):
        # El nombre que RDKit pone al átomo en el PDB que se dibuja: elemento y
        # contador de ese elemento (C1, C2, O1…). Así cada rótulo se puede
        # cruzar con el archivo.
        simbolo = mol_sin_h.GetAtomWithIdx(i).GetSymbol()
        ordinal = sum(1 for a in mol_sin_h.GetAtoms()
                      if a.GetIdx() <= i and a.GetSymbol() == simbolo)
        return f"{simbolo.upper()}{ordinal}"

    salida = []
    for a, b in mol_sin_h.GetSubstructMatches(patron):
        izquierda = next((v.GetIdx() for v in mol_sin_h.GetAtomWithIdx(a).GetNeighbors()
                          if v.GetIdx() != b), None)
        derecha = next((v.GetIdx() for v in mol_sin_h.GetAtomWithIdx(b).GetNeighbors()
                        if v.GetIdx() != a), None)
        if izquierda is None or derecha is None or izquierda == derecha:
            continue
        angulo = rdMolTransforms.GetDihedralDeg(conformacion, izquierda, a, b, derecha)
        salida.append({"atomos": [nombre(izquierda), nombre(a), nombre(b), nombre(derecha)],
                       "angulo_grados": round(float(angulo), 2)})
    return salida


def _rig_torsional(mol, pdb_visual: bytes, sdf: bytes) -> dict[str, Any]:
    """Grafo SDF y ejes demostrables de la copia visual; nunca una trayectoria.

    Los nombres y xyz salen del PDB escrito, incluyendo su precisión de 0,001 Å.
    Sólo una componente completa unida por un puente simple puede girar.
    """
    from rdkit import Chem
    import math

    rows = [line for line in pdb_visual.decode("utf-8").splitlines()
            if line.startswith(("ATOM  ", "HETATM"))]
    if len(rows) != mol.GetNumAtoms():
        raise EnsambleNoDisponible("El PDB visual no corresponde átomo a átomo al SDF.")
    atoms = []
    names = []
    for atom, line in zip(mol.GetAtoms(), rows):
        name = line[12:16].strip()
        xyz = [float(line[start:start + 8]) for start in (30, 38, 46)]
        if (not name or name in names or atom.GetAtomicNum() == 1
                or line[76:78].strip().upper() != atom.GetSymbol().upper()
                or not all(math.isfinite(value) for value in xyz)):
            raise EnsambleNoDisponible("El PDB visual no conserva identidades atómicas inequívocas.")
        names.append(name)
        atoms.append({"id": name, "elemento": atom.GetSymbol(), "xyz_a": xyz})

    links, axes = [], []
    for bond in mol.GetBonds():
        a, b = bond.GetBeginAtomIdx(), bond.GetEndAtomIdx()
        order = bond.GetBondTypeAsDouble()
        links.append({"atomos": [names[a], names[b]],
                      "orden": int(order) if order.is_integer() else order,
                      "anillo": bond.IsInRing(), "aromatico": bond.GetIsAromatic(),
                      "conjugado": bond.GetIsConjugated()})
        if (bond.GetBondType() != Chem.BondType.SINGLE or bond.IsInRing()
                or bond.GetIsAromatic() or bond.GetIsConjugated()):
            continue
        left = sorted(atom.GetIdx() for atom in mol.GetAtomWithIdx(a).GetNeighbors() if atom.GetIdx() != b)
        right = sorted(atom.GetIdx() for atom in mol.GetAtomWithIdx(b).GetNeighbors() if atom.GetIdx() != a)
        if not left or not right:
            continue
        movable, todo = set(), [b]
        while todo:
            current = todo.pop()
            if current in movable:
                continue
            movable.add(current)
            for neighbor in mol.GetAtomWithIdx(current).GetNeighbors():
                other = neighbor.GetIdx()
                if {current, other} != {a, b} and other not in movable:
                    todo.append(other)
        if a in movable:          # Control de puente, independiente del flag de anillo.
            continue
        axes.append({"atomos": [names[left[0]], names[a], names[b], names[right[0]]],
                     "moviles": [names[index] for index in sorted(movable)],
                     "amplitud_grados": 30.0})
    return {"schema": "moldesign.rig-torsional/1", "sdf_sha256": sha256(sdf),
            "atomos": atoms, "enlaces": links, "ejes": axes}


def construir_geometria(registros_pose: list[tuple[int, str]],
                        conformeros_sdf: dict[int, bytes]) -> dict[str, Any]:
    """Los archivos visuales y las medidas geométricas, sin tocar el disco.

    `registros_pose`: (rank, registro SDF demostrado) en el orden de la piscina.
    `conformeros_sdf`: índice de conformación -> bytes del SDF que recibió Vina.
    """
    from rdkit import Chem

    poses = {}
    for rank, registro in registros_pose:
        poses[rank] = Chem.RemoveHs(_primer_registro(registro))
    referencia = poses[min(poses)]

    archivos: dict[str, bytes] = {}
    pose_datos: dict[int, dict] = {}
    for rank, registro in registros_pose:
        mol = poses[rank]
        # El .sdf es el registro DEMOSTRADO, tal cual; el .pdb es sólo la vista
        # (sin hidrógenos) que dibuja Molecular Nodes.
        demostrado = registro.rstrip("\n")
        if not demostrado.endswith("$$$$"):
            demostrado += "\n$$$$"
        archivos[f"{CARPETA}/pose_{rank:03d}.pdb"] = Chem.MolToPDBBlock(mol).encode("utf-8")
        archivos[f"{CARPETA}/pose_{rank:03d}.sdf"] = (demostrado + "\n").encode("utf-8")
        pose_datos[rank] = {"atomos": mol.GetNumAtoms()}

    conf_datos: dict[int, dict] = {}
    for indice, sdf in conformeros_sdf.items():
        original = Chem.RemoveHs(_primer_registro(sdf))
        torsiones = _diedros(original)
        visual = Chem.Mol(original)
        rmsd = _alinear(referencia, visual)
        pdb_visual = Chem.MolToPDBBlock(visual).encode("utf-8")
        sdf_original = sdf if isinstance(sdf, bytes) else sdf.encode("utf-8")
        archivos[f"{CARPETA}/conf_{indice:02d}.pdb"] = pdb_visual
        archivos[f"{CARPETA}/conf_{indice:02d}_entrada.sdf"] = sdf_original
        conf_datos[indice] = {"torsiones": torsiones, "rmsd_alineacion_a": round(rmsd, 3),
                              "atomos": original.GetNumAtoms()}
        try:
            rig = _rig_torsional(visual, pdb_visual, sdf_original)
            conf_datos[indice]["rig_torsional"] = rig
            if not rig["ejes"]:
                conf_datos[indice]["rig_torsional_motivo"] = "No hay un puente simple no conjugado con cuatro átomos pesados."
        except (EnsambleNoDisponible, ValueError) as exc:
            # La disponibilidad de una ilustración no invalida el ensamble discreto.
            conf_datos[indice]["rig_torsional_motivo"] = str(exc)
    return {"archivos": archivos, "poses": pose_datos, "conformeros": conf_datos}


# ── el contrato ───────────────────────────────────────────────────────────────
def armar_contrato(snap: dict, entregadas: list[dict], geometria: dict[str, Any],
                   *, origen: dict | None = None) -> dict[str, Any]:
    """`ensamble.json` + los archivos que cita, a partir de lo ya demostrado.

    `entregadas`: una entrada por pose, en el orden de la piscina, con `rank`,
    `affinity`, `conformer_index` y `rank_local`.
    """
    protocolo = snap.get("docking_protocol") or {}
    procedencia = protocolo.get("execution_provenance") or {}
    por_conformacion = {c["indice"]: c for c in procedencia.get("por_conformacion") or []}
    archivos = dict(geometria["archivos"])

    def citar(ruta: str) -> dict[str, str]:
        return {"archivo": ruta, "sha256": sha256(archivos[ruta])}

    # Conformaciones: las que aportaron poses entregadas, mejores primero.
    primera_vez: dict[int, int] = {}
    for pose in entregadas:
        primera_vez.setdefault(pose["conformer_index"], pose["rank"])
    conformeros = []
    for indice in sorted(primera_vez, key=primera_vez.get):
        datos = geometria["conformeros"][indice]
        detalle = por_conformacion.get(indice, {})
        suyas = [p for p in entregadas if p["conformer_index"] == indice]
        entrada = {"indice": indice, **citar(f"{CARPETA}/conf_{indice:02d}.pdb"),
                   "sdf": f"{CARPETA}/conf_{indice:02d}_entrada.sdf",
                   "sdf_sha256": sha256(archivos[f"{CARPETA}/conf_{indice:02d}_entrada.sdf"]),
                   "semilla": detalle.get("semilla_conformacional"),
                   "energia_mmff": detalle.get("energia_mmff"),
                   "minimizacion": detalle.get("minimizacion"),
                   "torsiones": datos["torsiones"],
                   "rmsd_alineacion_a": datos["rmsd_alineacion_a"],
                   "mejor_afinidad_kcal_mol": min(p["affinity"] for p in suyas),
                   "poses_candidatas": detalle.get("num_poses"),
                   "poses_entregadas": len(suyas)}
        if entrada["semilla"] is None:       # la pose la lleva aunque la corrida no
            entrada["semilla"] = ((suyas[0].get("source_provenance") or {})
                                  .get("ligand_input") or {}).get("semilla_conformacional")
        if "rig_torsional" in datos:
            entrada["rig_torsional"] = datos["rig_torsional"]
        if "rig_torsional_motivo" in datos:
            entrada["rig_torsional_motivo"] = datos["rig_torsional_motivo"]
        conformeros.append(entrada)

    poses = []
    for pose in entregadas:
        rank = pose["rank"]
        poses.append({
            "rank": rank, "conformero": pose["conformer_index"],
            "rank_local": pose["rank_local"], "afinidad_kcal_mol": pose["affinity"],
            **citar(f"{CARPETA}/pose_{rank:03d}.pdb"),
            "sdf": f"{CARPETA}/pose_{rank:03d}.sdf",
            "sdf_sha256": sha256(archivos[f"{CARPETA}/pose_{rank:03d}.sdf"]),
            "controles": controles_de(snap, pose)})

    candidatas = [c.get("num_poses") for c in por_conformacion.values()]
    evidencia = snap.get("structural_evidence") if isinstance(
        snap.get("structural_evidence"), dict) else {}
    controles_reales = [p["controles"] for p in poses if p["controles"]]
    validacion = None
    if controles_reales:
        validacion = {"motor": evidencia.get("validation_engine"),
                      "estado": evidencia.get("stage_status"),
                      "cobertura": evidencia.get("coverage")}
    contrato = {
        "schema": SCHEMA,
        "origen": origen or {},
        "caja": {"centro": list(procedencia["box_center"]),
                 "tamano": list(procedencia["box_size"])},
        "motor": {"nombre": "AutoDock Vina", "version": snap.get("vina_version"),
                  "semilla": snap.get("vina_random_seed"),
                  "exhaustiveness": protocolo.get("exhaustiveness"),
                  "num_poses": protocolo.get("num_poses")},
        "resumen": {
            "conformaciones_pedidas": protocolo.get("conformers_requested"),
            "conformaciones_generadas": protocolo.get("conformers_generated"),
            "conformaciones_acopladas": len(por_conformacion),
            "poses_candidatas": (sum(candidatas) if all(isinstance(n, int) for n in candidatas)
                                 and candidatas else None),
            "poses_entregadas": len(poses),
            "conformaciones_con_poses_entregadas": len(conformeros)},
        "conformeros": conformeros,
        "poses": poses,
        "validacion": validacion,
        "declaraciones": [
            "Las conformaciones se alinean rigidamente a la mejor pose solo para compararlas; "
            "Vina recibio cada una sin alinear.",
            "La piscina reordena por afinidad observada de Vina; no demuestra que una "
            "conformacion sea la correcta.",
            "Los controles fisicos se aplicaron despues del acoplamiento; 'no evaluado' no "
            "significa 'invalido'."],
    }
    return {"contrato": contrato, "archivos": archivos}


# ── la recogida completa (con disco) ──────────────────────────────────────────
async def recoger(snap: dict, *, origen: dict | None = None) -> dict[str, Any]:
    """Demuestra y reúne el ensamble de una corrida guardada, o se abstiene.

    Devuelve `{"contrato": {...}, "archivos": {ruta_relativa: bytes}}`.
    """
    ok, motivo = es_ensamble(snap)
    if not ok:
        raise EnsambleNoDisponible(motivo)
    procedencia = (snap.get("docking_protocol") or {}).get("execution_provenance") or {}
    if not (procedencia.get("box_center") and procedencia.get("box_size")):
        raise EnsambleNoDisponible("La corrida no conserva su caja de docking exacta.")

    entregadas, registros, conformeros = [], [], {}
    for crudo in sorted(snap["docking_poses"], key=lambda p: p["rank"]):
        pose = DockingPose.model_validate(crudo)
        try:
            recuperada = await recuperar_pose_agrupada(pose)
        except PoseNoRecuperable as exc:
            raise EnsambleNoDisponible(
                f"No se puede demostrar la pose {pose.rank} de la piscina: {exc}") from exc
        entregadas.append({"rank": pose.rank, "affinity": pose.affinity,
                           "conformer_index": pose.conformer_index,
                           "rank_local": recuperada.rank_original,
                           "source_provenance": pose.source_provenance})
        registros.append((pose.rank, recuperada.sdf_record))
        if pose.conformer_index not in conformeros:
            try:
                conformeros[pose.conformer_index] = await read_bytes(recuperada.conformer_path)
            except (OSError, ValueError) as exc:
                raise EnsambleNoDisponible(
                    f"Falta la conformación {pose.conformer_index} de entrada.") from exc
    try:
        geometria = await asyncio.to_thread(construir_geometria, registros, conformeros)
    except EnsambleNoDisponible:
        raise
    except Exception as exc:       # RDKit: una molécula ilegible no es un fallo del servidor
        raise EnsambleNoDisponible(
            f"No se pudo reconstruir la geometría del ensamble: {exc}") from exc
    return armar_contrato(snap, entregadas, geometria, origen=origen)
