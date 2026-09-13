# -*- coding: utf-8 -*-
"""
molflex.py — Motor MolFlex v2: docking rígido por ensemble + relax en el pocket.

Fases (protocolo pre-registrado: docs/40_MOLFLEX_PROTOCOL.md):
  1. Ensemble ETKDG (seed=42, pruneRmsThresh=0.4) → un PDBQT rígido por
     conformero (ROOT único, TORSDOF 0) + su PDBQT flexible meeko (Fase 3).
  2. Docking rígido por conformero (Vina exh=8, num_modes=9, box 25Å³ centrado
     en el ligando cristalográfico, cpu explícito).
  3. Relax de las top-K poses. Cadena pre-registrada: minimización OpenMM con
     la proteína congelada (restricciones armónicas k=100 kcal/mol/Å²) y solo
     el ligando libre; re-score con Vina --score_only (misma función de
     puntuación para comparabilidad).

REALIDAD DEL ENTORNO (verificada 2026-08-13 en esta máquina):
  - `import openmmforcefields` → OK (0.15.1), pero SMIRNOFFTemplateGenerator
    falla con ModuleNotFoundError('openff'): no hay openff-toolkit.
  - `ForceField("amber14-all.xml", "openff-2.0.0.offxml")` → ValueError: el
    archivo offxml no existe en el sistema (openmmforcefields 0.15 ya no lo
    empaqueta y no hay openff-toolkit que lo provea).
  - `ForceField("amber14-all.xml")` + topología proteína+ligando → ValueError
    "No template found for residue UNL" (los XML de GAFF que trae
    openmmforcefields no incluyen templates de residuos y no hay antechamber
    para asignar tipos atómicos).
  → El sondeo de capacidad documenta los errores exactos y el motor degrada a
    `vina --local_only` (búsqueda local torsional en el pocket con la MISMA
    función de puntuación Vina) + re-score `--score_only` del pose relajado
    convertido a rígido (comparabilidad de scores: rígido vs rígido).
    La implementación OpenMM completa queda activa si el sondeo pasa.

Uso (CLI):
  python scripts/molflex.py --pdb-id 1a4w [--n-conf 30] [--top-k 3] [--cpu 1]
                            [--out-dir DIR] [--keep] [--out-json FILE]
                            [--experiment-id ID]

Preregistro de semillas (FND-06, cierre de garantía futura):
  seed_docking=42 preregistrado 2026-08-15 para todas las corridas futuras de
  Vina: TODAS las invocaciones de Vina de este módulo pasan --seed 42
  explícito (SEMILLA_VINA). SEMILLA_ETKDG=42 es la semilla de CONFORMEROS
  (ETKDG), no del dock; ambas se registran por separado en provenance.json
  (seed_conformer / seed_docking). El cambio aplica a corridas FUTURAS y no
  toca poses históricas ya dockeadas.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PDBBIND = PROJECT_ROOT / "data" / "pdbbind"
VINA = str(PROJECT_ROOT / "tools" / "vina" / "vina.exe")

sys.path.insert(0, str(PROJECT_ROOT / "rescoring" / "scripts"))
import redock_pdbbind as rp  # noqa: E402

DEFAULT_N_CONF = 30
DEFAULT_TOP_K = 3
DEFAULT_EXPERIMENT_ID = "molflex"
BOX_SIZE = 25.0
# Valor congelado del protocolo (docs/40): 8. La variable de entorno permite a un
# experimento declarar otro presupuesto de búsqueda sin tocar el default; el valor
# efectivo se emite en provenance.json, de modo que la corrida queda auditada.
EXHAUSTIVENESS = int(os.environ.get("MOLFLEX_EXHAUSTIVENESS", "8"))
NUM_MODES = 9
SEMILLA_ETKDG = 42     # seed de CONFORMEROS ETKDG (preregistrado, docs/40);
                       # emitida como seed_conformer en provenance.json (FND-06)
SEMILLA_VINA = 42      # seed de DOCKING Vina — preregistrada 2026-08-15
                       # (FND-06): TODAS las invocaciones de Vina de este
                       # módulo la pasan explícitamente vía --seed; emitida
                       # como seed_docking en provenance.json
VERSION_MEEKO = "0.7.1"  # verificada en el entorno (redock_pdbbind.py)
RESTRAINT_K = 100.0  # kcal/mol/Å² — restricción armónica de la proteína
MIN_STEPS = 300      # pasos de minimización OpenMM (Fase 3)
TIMEOUT_DOCK = 240   # s por dock rígido
TIMEOUT_RELAX = 180  # s por relax
TIMEOUT_SCORE = 120  # s por score_only

# Caché del sondeo de capacidad OpenMM (una vez por proceso).
_SONDEO_OPENMM: dict | None = None

# Caché de la versión del binario Vina (una vez por proceso).
_VERSION_VINA: str | None = None


def version_vina() -> str:
    """Versión del binario Vina (probe `--version` en caché por proceso).

    Solo lectura de metadatos: no ejecuta docking. Usado por el sidecar de
    provenance (FND-06) y por los reports de corrida.
    """
    global _VERSION_VINA
    if _VERSION_VINA is None:
        try:
            r = subprocess.run([VINA, "--version"], capture_output=True,
                               text=True, timeout=10)
            m = re.search(r"v(\d+\.\d+(?:\.\d+)?)", r.stdout or "")
            _VERSION_VINA = m.group(1) if m else "unknown"
        except Exception:
            _VERSION_VINA = "unknown"
    return _VERSION_VINA


# ───────────────────────── utilidades RDKit/meeko ─────────────────────────

def leer_ligando(sdf_path: str | Path):
    """Lee el SDF cristalográfico. Primero con sanitización normal (requerida
    por meeko), y como fallback sin sanitizar. Devuelve el mol o None
    (sdf_unreadable)."""
    from rdkit import Chem, RDLogger

    RDLogger.logger().setLevel(RDLogger.ERROR)
    p = str(sdf_path)
    try:
        m = Chem.MolFromMolFile(p)
        if m is not None:
            return m
    except Exception:
        pass
    try:
        m = Chem.MolFromMolFile(p, sanitize=False, removeHs=False)
        if m is not None:
            return m
    except Exception:
        pass
    return None


def construir_ensemble(crystal, n_conf: int):
    """ETKDG con preferencias experimentales de torsión (CSD) y seed fija.
    Devuelve (mol_con_H, lista_de_conf_ids)."""
    from rdkit import Chem
    from rdkit.Chem import AllChem

    mh = Chem.AddHs(crystal)
    try:
        ids = list(AllChem.EmbedMultipleConfs(
            mh, numConfs=n_conf, randomSeed=SEMILLA_ETKDG,
            useExpTorsionAnglePrefs=True, useBasicKnowledge=True,
            pruneRmsThresh=0.4, numThreads=0,
        ))
    except Exception:
        ids = []
    return mh, ids


def escribir_pdbqt(setup):
    """Escribe el PDBQT flexible (con mapa de índices) y su variante rígida
    (ROOT único, TORSDOF 0). Devuelve (rigid_str, flex_str, serial_a_mol, err).
    serial_a_mol: {serial_pdbqt: índice_atómico_mol} desde REMARK INDEX MAP."""
    from meeko import PDBQTWriterLegacy

    flex_str, ok, err = PDBQTWriterLegacy.write_string(setup, add_index_map=True)
    if not ok or not flex_str:
        return None, None, {}, err or "meeko_write_failed"
    atoms = [l for l in flex_str.splitlines() if l.startswith(("ATOM", "HETATM"))]
    rigid_str = "\n".join(["ROOT"] + atoms + ["ENDROOT", "TORSDOF 0"]) + "\n"
    serial_a_mol: dict[int, int] = {}
    for l in flex_str.splitlines():
        if l.startswith("REMARK INDEX MAP"):
            toks = l.split()[3:]
            for k in range(0, len(toks) - 1, 2):
                try:
                    serial_a_mol[int(toks[k + 1])] = int(toks[k]) - 1
                except Exception:
                    continue
    return rigid_str, flex_str, serial_a_mol, None


def rigidizar(pdbqt_str: str) -> str:
    """Convierte cualquier PDBQT (rígido o flexible) a rígido de un solo ROOT."""
    atoms = [l for l in pdbqt_str.splitlines() if l.startswith(("ATOM", "HETATM"))]
    return "\n".join(["ROOT"] + atoms + ["ENDROOT", "TORSDOF 0"]) + "\n"


def cirugia_coordenadas(flex_str: str, pose: list) -> str:
    """Reemplaza las coordenadas del PDBQT flexible por las del pose rígido
    (emparejando por serial). Vina preserva los seriales entre entrada/salida."""
    coords = {}
    for s, x, y, z in pose:
        coords[int(s)] = (float(x), float(y), float(z))
    out = []
    for l in flex_str.splitlines():
        if l.startswith(("ATOM", "HETATM")):
            try:
                s = int(l[6:11])
            except Exception:
                out.append(l)
                continue
            if s in coords:
                x, y, z = coords[s]
                l = f"{l[:30]}{x:8.3f}{y:8.3f}{z:8.3f}{l[54:]}"
        out.append(l)
    return "\n".join(out) + "\n"


# ───────────────────────── parsing de Vina ────────────────────────────────

def parsear_scores_tabla(stdout: str) -> list:
    """Extrae la columna de afinidad de la tabla 'mode | affinity' de Vina."""
    scores = []
    for l in stdout.splitlines():
        parts = l.strip().split()
        if len(parts) >= 4 and parts[0].isdigit():
            try:
                scores.append(float(parts[1]))
            except ValueError:
                continue
    return scores


def parsear_energia_estimada(stdout: str):
    """Extrae 'Estimated Free Energy of Binding' (--local_only / --score_only)."""
    for l in stdout.splitlines():
        if "Estimated Free Energy of Binding" in l:
            try:
                return float(l.split(":")[1].split("(")[0].strip())
            except Exception:
                return None
    return None


def parsear_out_vina(texto: str) -> list:
    """Parsea el PDBQT de salida de Vina. Devuelve [(score, [(serial,x,y,z)])]
    por MODEL. El score es None si no hay REMARK VINA RESULT (caso local_only,
    que tampoco escribe MODEL/ENDMDL)."""
    lineas = texto.splitlines()
    modelos = []
    cur_score = None
    cur_atoms: list = []
    hay_model = any(l.startswith("MODEL") for l in lineas)
    for l in lineas:
        if l.startswith("MODEL"):
            cur_score, cur_atoms = None, []
        elif l.startswith("REMARK VINA RESULT"):
            try:
                cur_score = float(l.split()[3])
            except Exception:
                cur_score = None
        elif l.startswith(("ATOM", "HETATM")):
            try:
                cur_atoms.append([int(l[6:11]), float(l[30:38]),
                                  float(l[38:46]), float(l[46:54])])
            except Exception:
                continue
        elif l.startswith("ENDMDL"):
            if cur_atoms:
                modelos.append([cur_score, cur_atoms])
                cur_atoms = []
    if not hay_model and cur_atoms:
        modelos.append([cur_score, cur_atoms])
    return modelos


def coords_pose_a_por_mol(pose: list, serial_a_mol: dict) -> dict:
    """Convierte coords por serial a {índice_mol: (x, y, z)}."""
    return {serial_a_mol[int(s)]: (float(x), float(y), float(z))
            for s, x, y, z in pose if int(s) in serial_a_mol}


def rmsd_pesados(crystal, coords_por_mol: dict):
    """RMSD de átomos pesados (GetBestRMS) entre el cristal y un pose dado
    como {índice_mol: (x,y,z)}. Si algún átomo pesado no está mapeado, se
    podan ambos lados al subconjunto mapeado."""
    from rdkit import Chem
    from rdkit.Chem import AllChem

    pesados = [i for i, a in enumerate(crystal.GetAtoms()) if a.GetAtomicNum() > 1]
    mapeados = [i for i in pesados if i in coords_por_mol]
    if not mapeados:
        return None

    def podar(m, idxs):
        rw = Chem.RWMol()
        conf = Chem.Conformer(len(idxs))
        for k, i in enumerate(idxs):
            rw.AddAtom(Chem.Atom(m.GetAtomWithIdx(i).GetAtomicNum()))
            pos = m.GetConformer(0).GetAtomPosition(i)
            conf.SetAtomPosition(k, pos)
        nm = rw.GetMol()
        nm.AddConformer(conf)
        return nm

    ref = Chem.Mol(crystal)
    prb = Chem.Mol(crystal)
    for i in mapeados:
        prb.GetConformer(0).SetAtomPosition(i, coords_por_mol[i])
    if len(mapeados) < len(pesados):
        ref = podar(ref, mapeados)
        prb = podar(prb, mapeados)
    try:
        return AllChem.GetBestRMS(prb, ref, 0, 0)
    except Exception:
        return None


def rmsd_pose_pocket(crystal, coords_por_mol: dict):
    """RMSD de átomos pesados EN EL MARCO DEL POCKET, sin alineamiento:
    compara las coords de la pose 1:1 contra las del cristal (mismo sistema
    de coordenadas; el receptor es fijo, así que traslación/rotación de la
    pose NO se compensan). Mide si la pose está en el lugar bioactivo, no
    solo si su geometría interna coincide.

    Lección de la auditoría Ruta A (2026-08-14): rmsd_pesados usa
    AllChem.GetBestRMS, que ALINEA los dos mols y oculta desplazamientos —
    una pose movida ~4 Å del pocket puede reportar RMSD ~0. GetBestRMS sigue
    siendo correcto para cobertura de conformeros (geometría interna libre);
    para poses dockeadas usar ESTA función.
    """
    pesados = [i for i, a in enumerate(crystal.GetAtoms()) if a.GetAtomicNum() > 1]
    mapeados = [i for i in pesados if i in coords_por_mol]
    if not mapeados:
        return None
    conf = crystal.GetConformer(0)
    s = 0.0
    for i in mapeados:
        p = conf.GetAtomPosition(i)
        x, y, z = coords_por_mol[i]
        s += (p.x - x) ** 2 + (p.y - y) ** 2 + (p.z - z) ** 2
    return float((s / len(mapeados)) ** 0.5)


def rmsd_conf_a_cristal(mh, crystal, cid):
    """Min-RMSD de un conformero del ensemble al cristal usando SOLO átomos
    pesados y sin sanitización (RemoveHs lanza KekulizeException en ligandos
    aromáticos no kekulizables, p. ej. 185l)."""
    pesados = [i for i, a in enumerate(crystal.GetAtoms()) if a.GetAtomicNum() > 1]
    if mh.GetNumAtoms() < crystal.GetNumAtoms() or not pesados:
        return None
    coords = {}
    for i in pesados:
        p = mh.GetConformer(cid).GetAtomPosition(i)
        coords[i] = (float(p[0]), float(p[1]), float(p[2]))
    return rmsd_pesados(crystal, coords)


# ───────────────────────── preparación por complejo ───────────────────────

def preparar_complejo(pid: str, n_conf: int, work: str | Path,
                      experiment_id: str = DEFAULT_EXPERIMENT_ID) -> dict:
    """Fase 1: receptor PDBQT, centro de caja, ensemble ETKDG y PDBQTs
    rígido+flexible por conformero. Escribe todo bajo work/pid/. Devuelve
    metadatos serializables (sin objetos RDKit).

    experiment_id: identificador del experimento para provenance.json
    (FND-06). Default "molflex"; las corridas futuras deben pasarlo explícito
    vía --experiment-id.
    """
    from meeko import MoleculePreparation

    w = Path(work) / pid
    w.mkdir(parents=True, exist_ok=True)
    t0 = time.monotonic()
    d = PDBBIND / pid
    sdf = d / f"{pid}_ligand.sdf"
    prot = d / f"{pid}_protein.pdb"

    if not sdf.exists() or not prot.exists():
        return {"ok": False, "reason": "missing_files", "t": round(time.monotonic() - t0, 1)}
    crystal = leer_ligando(sdf)
    if crystal is None:
        return {"ok": False, "reason": "sdf_unreadable", "t": round(time.monotonic() - t0, 1)}

    rec = str(w / "rec.pdbqt")
    if not rp.prepare_receptor_pdbqt(str(prot), rec):
        return {"ok": False, "reason": "receptor_prep_failed", "t": round(time.monotonic() - t0, 1)}
    center = rp.find_binding_center(str(sdf))
    if center is None:
        return {"ok": False, "reason": "binding_center_failed", "t": round(time.monotonic() - t0, 1)}
    (w / "center.json").write_text(json.dumps(list(center)), encoding="utf-8")

    mh, ids = construir_ensemble(crystal, n_conf)
    if not ids:
        return {"ok": False, "reason": "no_conformers", "t": round(time.monotonic() - t0, 1)}

    prep = MoleculePreparation()
    cids: list = []
    rmsds: list = []
    serial_a_mol: dict = {}
    for cid in ids:
        try:
            setups = prep.prepare(mh, conformer_id=cid)
            rigid_str, flex_str, mapa, _err = escribir_pdbqt(setups[0])
            if not rigid_str or not flex_str or not mapa:
                continue
            (w / f"conf{cid}.rigid.pdbqt").write_text(rigid_str, encoding="utf-8")
            (w / f"conf{cid}.flex.pdbqt").write_text(flex_str, encoding="utf-8")
            serial_a_mol = mapa  # idéntico entre conformeros (misma topología)
            try:
                r = rmsd_conf_a_cristal(mh, crystal, cid)
            except Exception:
                r = None
            cids.append(cid)
            rmsds.append([cid, round(r, 3) if r is not None else None])
        except Exception:
            continue
    if not cids:
        return {"ok": False, "reason": "meeko_all_failed", "t": round(time.monotonic() - t0, 1)}

    (w / "index_map.json").write_text(
        json.dumps([[s, m] for s, m in serial_a_mol.items()]), encoding="utf-8")

    # Sidecar de provenance por corrida (FND-06, contrato canónico v1.1):
    # un registro por conformero con clave pid|molflex|conf{cid}.out y todos
    # los campos canónicos (semillas separadas, box, preparación, engine,
    # experiment_id, created_at ISO 8601). Solo emite parámetros que ya
    # existen en esta función; no altera la lógica de docking.
    created_at = datetime.now().astimezone().isoformat(timespec="seconds")
    registros_provenance = []
    for cid in cids:
        registros_provenance.append({
            "key": f"{pid}|molflex|conf{cid}.out",
            "pid": pid,
            "source": "molflex",
            "file_stem": f"conf{cid}.out",
            "seed_conformer": SEMILLA_ETKDG,
            "seed_docking": SEMILLA_VINA,
            "conformer_id": cid,
            "exhaustiveness": EXHAUSTIVENESS,
            "num_modes": NUM_MODES,
            "box": {"center": list(center),
                    "size": [BOX_SIZE, BOX_SIZE, BOX_SIZE],
                    "method": "center_from_crystal_ligand"},
            "preparation": {
                "ligand": {"method": "meeko_molecule_preparation_etkdg",
                           "tool": "meeko", "version": VERSION_MEEKO},
                "receptor": {"protonation": "pdb_original",
                             "tool": "openbabel_pdb2pdbqt_rigido"},
            },
            "engine": {"name": "vina", "version": version_vina()},
            "experiment_id": experiment_id,
            "created_at": created_at,
        })
    (w / "provenance.json").write_text(
        json.dumps(registros_provenance, indent=2, ensure_ascii=False),
        encoding="utf-8")

    return {
        "ok": True, "n_conf": len(cids), "cids": cids,
        "ensemble_rmsds": rmsds, "center": list(center),
        "t": round(time.monotonic() - t0, 1),
    }


def cargar_mapa_indices(work_pid: str | Path) -> dict:
    """Lee index_map.json → {serial: índice_mol}."""
    p = Path(work_pid) / "index_map.json"
    if not p.exists():
        return {}
    return {int(s): int(m) for s, m in json.loads(p.read_text(encoding="utf-8"))}


def _args_box(center: list) -> list:
    """Argumentos de caja de búsqueda centrada en el ligando cristalográfico."""
    return [
        "--center_x", str(center[0]), "--center_y", str(center[1]),
        "--center_z", str(center[2]),
        "--size_x", str(BOX_SIZE), "--size_y", str(BOX_SIZE), "--size_z", str(BOX_SIZE),
    ]


# ───────────────────────── Fase 2: dock rígido ────────────────────────────

def dock_rigido_archivo(pid: str, cid: int, work: str | Path, cpu: int = 1,
                        maps_prefix: str | None = None,
                        write_maps: bool = False) -> dict:
    """Dockea un conformero rígido (Vina exh=8, num_modes=9). Devuelve scores
    de todos los modos y las coords del modo 1 (por serial).

    Caché de grid (fix E2, comportamiento de Vina 1.2.7 verificado empíricamente
    con un sondeo sobre 184l y 1aaq, 2026-08-14):
      - write_maps=True : primer dock del complejo. Escribe los mapas de
        afinidad (--write_maps + --force_even_voxels, OBLIGATORIO para el
        formato .map: sin el flag Vina aborta con "Number of voxels is odd")
        Y ejecuta el dock completo como un dock normal (doble uso: el escritor
        de mapas ES el dock del conformero 0). El grid queda discretizado con
        n_voxels par (span 25.5Å en vez de 25.125Å) — side effect documentado.
      - maps_prefix     : reutiliza los mapas (--maps). Vina 1.2.7 PROHÍBE
        combinar --maps con --receptor ("Cannot specify both receptor and
        affinity maps at the same time"); el grid completo (dimensiones y
        centro) sale de los mapas, así que no se pasan --center/--size.
      - ninguno         : comportamiento clásico (receptor fresco, grid
        recalculado por llamada).
    """
    w = Path(work) / pid
    rec = str(w / "rec.pdbqt")
    rig = str(w / f"conf{cid}.rigid.pdbqt")
    out = w / f"conf{cid}.out.pdbqt"
    try:
        center = json.loads((w / "center.json").read_text(encoding="utf-8"))
    except Exception:
        return {"pid": pid, "cid": cid, "ok": False, "reason": "no_center", "t": 0.0}
    base = ["--exhaustiveness", str(EXHAUSTIVENESS),
            "--num_modes", str(NUM_MODES),
            "--seed", str(SEMILLA_VINA),
            "--cpu", str(cpu), "--out", str(out)]
    if write_maps:
        cmd = [VINA, "--receptor", rec, "--ligand", rig] + _args_box(center) + base + [
            "--write_maps", maps_prefix, "--force_even_voxels"]
        modo = "write_maps"
    elif maps_prefix:
        cmd = [VINA, "--ligand", rig, "--maps", maps_prefix] + base
        modo = "maps"
    else:
        cmd = [VINA, "--receptor", rec, "--ligand", rig] + _args_box(center) + base
        modo = "fresh"
    t0 = time.monotonic()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT_DOCK)
    except subprocess.TimeoutExpired:
        return {"pid": pid, "cid": cid, "ok": False, "reason": "timeout", "t": TIMEOUT_DOCK}
    dt = round(time.monotonic() - t0, 1)
    if r.returncode != 0:
        return {"pid": pid, "cid": cid, "ok": False, "reason": f"rc={r.returncode}",
                "t": dt, "stderr_head": r.stderr[:200]}
    scores = parsear_scores_tabla(r.stdout)
    if not scores:
        return {"pid": pid, "cid": cid, "ok": False, "reason": "no_scores", "t": dt}
    pose: list = []
    try:
        modelos = parsear_out_vina(out.read_text(encoding="utf-8"))
        if modelos:
            pose = modelos[0][1]
    except Exception:
        pose = []
    if not pose:
        return {"pid": pid, "cid": cid, "ok": False, "reason": "no_pose", "t": dt}
    return {"pid": pid, "cid": cid, "ok": True, "scores": scores,
            "best": scores[0], "pose": pose, "t": dt, "grid_mode": modo}


# ───────────────────────── Fase 3: relax ──────────────────────────────────

def relax_pose_archivo(pid: str, cid: int, pose: list, work: str | Path,
                       cpu: int = 1, engine: str = "vina_local_only",
                       maps_prefix: str | None = None) -> dict:
    """Relax del pose rígido: reconstruye el PDBQT flexible con las coords del
    pose → vina --local_only → re-score del pose relajado como rígido
    (--score_only, comparabilidad de scores: rígido vs rígido).

    Si maps_prefix está disponible (grid cacheado del complejo), tanto
    --local_only como --score_only usan --maps (sin --receptor, que Vina 1.2.7
    prohíbe combinar con mapas). Si la variante con mapas falla, se reintenta
    con receptor fresco (fallback documentado)."""
    w = Path(work) / pid
    try:
        center = json.loads((w / "center.json").read_text(encoding="utf-8"))
        flex_str = (w / f"conf{cid}.flex.pdbqt").read_text(encoding="utf-8")
    except Exception:
        return {"pid": pid, "cid": cid, "ok": False, "reason": "no_inputs", "t": 0.0}

    if engine == "openmm":
        return fase3_openmm_relax(pid, cid, pose, work, cpu)

    flex_pose = cirugia_coordenadas(flex_str, pose)
    (w / f"conf{cid}.flexpose.pdbqt").write_text(flex_pose, encoding="utf-8")
    rec = str(w / "rec.pdbqt")
    out = w / f"conf{cid}.relax.pdbqt"

    lig_flexpose = str(w / f"conf{cid}.flexpose.pdbqt")
    if maps_prefix:
        cmd = [VINA, "--ligand", lig_flexpose, "--maps", maps_prefix] + \
            ["--local_only", "--seed", str(SEMILLA_VINA),
             "--cpu", str(cpu), "--out", str(out)]
    else:
        cmd = [VINA, "--receptor", rec, "--ligand", lig_flexpose] + \
            _args_box(center) + ["--local_only", "--seed", str(SEMILLA_VINA),
                                 "--cpu", str(cpu), "--out", str(out)]
    t0 = time.monotonic()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT_RELAX)
    except subprocess.TimeoutExpired:
        return {"pid": pid, "cid": cid, "ok": False, "reason": "relax_timeout", "t": TIMEOUT_RELAX}
    if r.returncode != 0:
        if maps_prefix:
            # Fallback: receptor fresco si la variante con mapas falló.
            cmd = [VINA, "--receptor", rec, "--ligand", lig_flexpose] + \
                _args_box(center) + ["--local_only", "--seed",
                                     str(SEMILLA_VINA),
                                     "--cpu", str(cpu), "--out", str(out)]
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT_RELAX)
            except subprocess.TimeoutExpired:
                return {"pid": pid, "cid": cid, "ok": False, "reason": "relax_timeout",
                        "t": TIMEOUT_RELAX}
        if r.returncode != 0:
            return {"pid": pid, "cid": cid, "ok": False, "reason": f"relax_rc={r.returncode}",
                    "t": round(time.monotonic() - t0, 1)}
    score_local = parsear_energia_estimada(r.stdout)
    try:
        modelos = parsear_out_vina(out.read_text(encoding="utf-8"))
        coords = modelos[0][1] if modelos else []
    except Exception:
        coords = []
    if not coords:
        return {"pid": pid, "cid": cid, "ok": False, "reason": "no_relaxed_pose",
                "t": round(time.monotonic() - t0, 1)}

    # Re-score con la MISMA función de puntuación: pose relajado → rígido.
    rig_relax = rigidizar(out.read_text(encoding="utf-8"))
    (w / f"conf{cid}.relax.rigid.pdbqt").write_text(rig_relax, encoding="utf-8")
    lig_relax_rigid = str(w / f"conf{cid}.relax.rigid.pdbqt")
    if maps_prefix:
        cmd2 = [VINA, "--ligand", lig_relax_rigid, "--maps", maps_prefix] + \
            ["--score_only", "--seed", str(SEMILLA_VINA), "--cpu", str(cpu)]
    else:
        cmd2 = [VINA, "--receptor", rec, "--ligand", lig_relax_rigid] + \
            _args_box(center) + ["--score_only", "--seed", str(SEMILLA_VINA),
                                 "--cpu", str(cpu)]
    try:
        r2 = subprocess.run(cmd2, capture_output=True, text=True, timeout=TIMEOUT_SCORE)
    except subprocess.TimeoutExpired:
        return {"pid": pid, "cid": cid, "ok": False, "reason": "score_timeout",
                "t": round(time.monotonic() - t0, 1)}
    if r2.returncode != 0:
        if maps_prefix:
            # Fallback: receptor fresco para el re-score.
            cmd2 = [VINA, "--receptor", rec, "--ligand", lig_relax_rigid] + \
                _args_box(center) + ["--score_only", "--seed",
                                     str(SEMILLA_VINA), "--cpu", str(cpu)]
            try:
                r2 = subprocess.run(cmd2, capture_output=True, text=True, timeout=TIMEOUT_SCORE)
            except subprocess.TimeoutExpired:
                return {"pid": pid, "cid": cid, "ok": False, "reason": "score_timeout",
                        "t": round(time.monotonic() - t0, 1)}
        if r2.returncode != 0:
            return {"pid": pid, "cid": cid, "ok": False, "reason": f"score_rc={r2.returncode}",
                    "t": round(time.monotonic() - t0, 1)}
    score_rigid = parsear_energia_estimada(r2.stdout)
    return {"pid": pid, "cid": cid, "ok": score_rigid is not None,
            "relaxed_local": score_local, "relaxed_rigid": score_rigid,
            "coords": coords, "engine": engine, "t": round(time.monotonic() - t0, 1),
            "grid_mode": "maps" if maps_prefix else "fresh"}

# -*- coding: utf-8 -*-
# ─────────────────── Fase 3 OpenMM (si el sondeo de capacidad pasa) ───────

def sondeo_openmm_relax() -> dict:
    """Sondeo de capacidad de la Fase 3 OpenMM (una vez por proceso).
    Documenta la cadena de fallos pre-registrada: SMIRNOFF → offxml → amber14
    con ligando UNL. available=True solo si createSystem funciona."""
    global _SONDEO_OPENMM
    if _SONDEO_OPENMM is not None:
        return _SONDEO_OPENMM
    razones = []
    disponible = False

    try:
        import openmmforcefields  # noqa: F401
        from openmmforcefields.generators import SMIRNOFFTemplateGenerator
        try:
            SMIRNOFFTemplateGenerator()
            disponible = True
            razones.append("SMIRNOFFTemplateGenerator disponible")
        except Exception as e:
            razones.append(f"SMIRNOFFTemplateGenerator: {type(e).__name__}: {e}")
    except Exception as e:
        razones.append(f"import openmmforcefields: {type(e).__name__}: {e}")

    try:
        from openmm.app import ForceField
        ForceField("amber14-all.xml", "openff-2.0.0.offxml")
        disponible = True
        razones.append("ForceField con offxml disponible")
    except Exception as e:
        razones.append(f"ForceField(+offxml): {type(e).__name__}: {e}")

    try:
        import openmm.app as app
        import openmm.unit as unit
        from openmm.app.element import Element
        prot_demo = PDBBIND / "1a4w" / "1a4w_protein.pdb"
        if prot_demo.exists():
            from pdbfixer import PDBFixer
            fixer = PDBFixer(filename=str(prot_demo))
            fixer.removeHeterogens(keepWater=False)
            try:
                fixer.findMissingResidues()
            except Exception:
                pass
            try:
                fixer.findMissingAtoms()
                fixer.addMissingAtoms()
            except Exception:
                pass
            try:
                fixer.addMissingHydrogens(pH=7.4)
            except Exception:
                pass
            mod = app.Modeller(fixer.topology, fixer.positions)
            lig = app.Topology()
            chain = lig.addChain()
            res = lig.addResidue("UNL", chain)
            for sym in ("C", "N", "O"):
                lig.addAtom(sym, Element.getBySymbol(sym), res)
            mod.add(lig, [unit.Quantity((0, 0, 0), unit.angstroms)] * 3)
            ff = app.ForceField("amber14-all.xml")
            try:
                ff.createSystem(mod.topology, nonbondedMethod=app.NoCutoff)
                disponible = True
                razones.append("amber14-all createSystem proteína+UNL OK")
            except Exception as e:
                razones.append(f"amber14-all createSystem: {type(e).__name__}: {e}")
    except Exception as e:
        razones.append(f"sondeo proteína+ligando: {type(e).__name__}: {e}")

    _SONDEO_OPENMM = {"available": disponible, "reasons": razones,
                      "relax_engine": "openmm" if disponible else "vina_local_only"}
    return _SONDEO_OPENMM


def fase3_openmm_relax(pid: str, cid: int, pose: list, work: str | Path,
                       cpu: int = 1) -> dict:
    """Fase 3 con OpenMM (solo si el sondeo pasó). Proteína con restricciones
    armónicas (k=100 kcal/mol/Å²), ligando libre, minimización de 300 pasos,
    exportación del ligando relajado y re-score con Vina --score_only."""
    import openmm
    import openmm.app as app
    import openmm.unit as unit

    w = Path(work) / pid
    prot_pdb = str(PDBBIND / pid / f"{pid}_protein.pdb")
    try:
        center = json.loads((w / "center.json").read_text(encoding="utf-8"))
        crystal = leer_ligando(str(PDBBIND / pid / f"{pid}_ligand.sdf"))
        serial_a_mol = cargar_mapa_indices(w)
    except Exception:
        return {"pid": pid, "cid": cid, "ok": False, "reason": "no_inputs", "t": 0.0}

    t0 = time.monotonic()
    try:
        # Proteína reparada con PDBFixer (patrón de backend/scoring/mmgbsa.py).
        from pdbfixer import PDBFixer
        fixer = PDBFixer(filename=prot_pdb)
        fixer.removeHeterogens(keepWater=False)
        try:
            fixer.findMissingResidues()
        except Exception:
            pass
        try:
            fixer.findMissingAtoms()
            fixer.addMissingAtoms()
        except Exception:
            pass
        try:
            fixer.addMissingHydrogens(pH=7.4)
        except Exception:
            pass

        # PDB del ligando (solo pesados) con las coords del pose.
        mol_a_serial = {m: s for s, m in serial_a_mol.items()}
        lig_lines = []
        for i in range(crystal.GetNumAtoms()):
            a = crystal.GetAtomWithIdx(i)
            if a.GetAtomicNum() <= 1 or i not in mol_a_serial:
                continue
            x, y, z = next(((px, py, pz) for s, px, py, pz in pose
                            if int(s) == mol_a_serial[i]), (0.0, 0.0, 0.0))
            lig_lines.append(
                "HETATM{:5d}  {:<3s} UNL     1    {:8.3f}{:8.3f}{:8.3f}"
                "{:6.2f}{:6.2f}          {:>2s}".format(
                    len(lig_lines) + 1, a.GetSymbol(), x, y, z,
                    1.0, 0.0, a.GetSymbol()))
        lig_pdb = w / f"conf{cid}.pose.pdb"
        lig_pdb.write_text("\n".join(lig_lines) + "\n", encoding="utf-8")
        lig = app.PDBFile(str(lig_pdb))
        n_prot = fixer.topology.getNumAtoms()
        mod = app.Modeller(fixer.topology, fixer.positions)
        mod.add(lig.topology, lig.positions)

        ff = app.ForceField("amber14-all.xml")
        system = ff.createSystem(
            mod.topology, nonbondedMethod=app.CutoffNonPeriodic,
            nonbondedCutoff=1.0 * unit.nanometer, constraints=app.HBonds)

        # Congelar la proteína: restricción armónica sobre TODOS sus átomos.
        k = RESTRAINT_K * unit.kilocalories_per_mole / unit.angstroms**2
        rest = openmm.CustomExternalForce("k*((x-x0)^2+(y-y0)^2+(z-z0)^2)")
        rest.addGlobalParameter("k", k)
        for i in range(n_prot):
            pos = mod.positions[i].value_in_unit(unit.nanometers)
            rest.addParticle(i, pos)
        system.addForce(rest)

        integ = openmm.LangevinMiddleIntegrator(
            0 * unit.kelvin, 1.0 / unit.picosecond, 2.0 * unit.femtosecond)
        sim = app.Simulation(mod.topology, system, integ)
        sim.context.setPositions(mod.positions)
        sim.minimizeEnergy(maxIterations=MIN_STEPS)
        state = sim.context.getState(getPositions=True)
        posiciones = state.getPositions(asNumpy=True)

        # Exportar el ligando relajado: serial → nuevas coords (átomos en el
        # orden en que se agregaron al PDB, i.e. pesados en orden del cristal).
        orden_serial = []
        for i in range(crystal.GetNumAtoms()):
            a = crystal.GetAtomWithIdx(i)
            if a.GetAtomicNum() > 1 and i in mol_a_serial:
                orden_serial.append(mol_a_serial[i])
        nuevas = {s: (float(posiciones[n_prot + k][0]),
                      float(posiciones[n_prot + k][1]),
                      float(posiciones[n_prot + k][2]))
                  for k, s in enumerate(orden_serial)}
        # Plantillas ATOM del flexible original para conservar tipos/cargas.
        plantillas = {s: l for l in (w / f"conf{cid}.flex.pdbqt")
                      .read_text(encoding="utf-8").splitlines()
                      if l.startswith(("ATOM", "HETATM")) and int(l[6:11]) == s}
        lineas = []
        for s in orden_serial:
            l = plantillas.get(s)
            if l is None:
                continue
            x, y, z = nuevas[s]
            lineas.append(f"{l[:30]}{x:8.3f}{y:8.3f}{z:8.3f}{l[54:]}")
        rig_relax = "\n".join(["ROOT"] + lineas + ["ENDROOT", "TORSDOF 0"]) + "\n"
        (w / f"conf{cid}.relax.rigid.pdbqt").write_text(rig_relax, encoding="utf-8")

        rec = str(w / "rec.pdbqt")
        cmd2 = [VINA, "--receptor", rec, "--ligand",
                str(w / f"conf{cid}.relax.rigid.pdbqt")] + _args_box(center) + [
                "--score_only", "--seed", str(SEMILLA_VINA), "--cpu", str(cpu)]
        r2 = subprocess.run(cmd2, capture_output=True, text=True,
                            timeout=TIMEOUT_SCORE)
        if r2.returncode != 0:
            return {"pid": pid, "cid": cid, "ok": False,
                    "reason": f"score_rc={r2.returncode}",
                    "t": round(time.monotonic() - t0, 1)}
        score_rigid = parsear_energia_estimada(r2.stdout)
        coords = [[s, x, y, z] for s, (x, y, z) in nuevas.items()]
        return {"pid": pid, "cid": cid, "ok": score_rigid is not None,
                "relaxed_local": None, "relaxed_rigid": score_rigid,
                "coords": coords, "engine": "openmm",
                "t": round(time.monotonic() - t0, 1)}
    except Exception as e:
        return {"pid": pid, "cid": cid, "ok": False,
                "reason": f"openmm: {type(e).__name__}: {e}",
                "t": round(time.monotonic() - t0, 1)}


# ────────────────────── flujo secuencial (CLI de referencia) ───────────────

def ejecutar_complejo(pid: str, n_conf: int = DEFAULT_N_CONF,
                      top_k: int = DEFAULT_TOP_K, cpu: int = 1,
                      out_dir: str | None = None, keep: bool = False,
                      experiment_id: str = DEFAULT_EXPERIMENT_ID) -> dict:
    """Ejecuta las Fases 1-3 secuencialmente para un complejo (referencia).
    El experimento global paralelo usa las funciones por trabajo directamente.
    experiment_id se registra en provenance.json (FND-06)."""
    work = Path(out_dir) if out_dir else Path(tempfile.mkdtemp(prefix=f"molflex_{pid}_"))
    work.mkdir(parents=True, exist_ok=True)
    t_inicio = time.monotonic()
    sondeo = sondeo_openmm_relax()
    resultado = {
        "pdb_id": pid, "ok": False, "n_conf": n_conf, "top_k": top_k,
        "cpu": cpu, "relax_engine": sondeo["relax_engine"],
        "openmm_status": sondeo,
        "time_fase1": 0.0, "time_fase2": 0.0, "time_fase3": 0.0,
        "total_time_s": 0.0,
    }
    try:
        t0 = time.monotonic()
        prep = preparar_complejo(pid, n_conf, work, experiment_id)
        resultado["time_fase1"] = round(time.monotonic() - t0, 1)
        if not prep["ok"]:
            resultado["reason"] = prep["reason"]
            resultado["total_time_s"] = round(time.monotonic() - t_inicio, 1)
            return resultado
        resultado["n_conf"] = prep["n_conf"]
        resultado["ensemble_min_rmsd"] = min(
            (r for _, r in prep["ensemble_rmsds"] if r is not None), default=None)

        # Fase 2: dock rígido por conformero (secuencial). El primer dock
        # escribe los mapas del receptor (--write_maps, grid cacheado); el
        # resto reutiliza los mapas (--maps). Fallback a receptor fresco si
        # no se generaron mapas o si un dock con mapas falla.
        t0 = time.monotonic()
        docks = {}
        maps_dir = Path(work) / pid / "maps"
        maps_prefix = str(maps_dir / "grid")
        cids = prep["cids"]
        if cids:
            maps_dir.mkdir(parents=True, exist_ok=True)
            primero = cids[0]
            docks[primero] = dock_rigido_archivo(pid, primero, work, cpu,
                                                 maps_prefix=maps_prefix,
                                                 write_maps=True)
            hay_mapas = any(maps_dir.glob("*.map"))
            for cid in cids[1:]:
                d = dock_rigido_archivo(pid, cid, work, cpu,
                                        maps_prefix=maps_prefix if hay_mapas else None)
                if not d["ok"] and hay_mapas:
                    # Reintento con receptor fresco si el dock con mapas falló.
                    d2 = dock_rigido_archivo(pid, cid, work, cpu)
                    d2["fallback"] = "fresh_tras_maps"
                    d = d2
                docks[cid] = d
        resultado["time_fase2"] = round(time.monotonic() - t0, 1)
        resultado["grid_cache"] = {
            "mapas_generados": bool(cids) and any(maps_dir.glob("*.map")),
            "n_docks_maps": sum(1 for d in docks.values()
                                if d.get("grid_mode") == "maps"),
            "n_docks_write": sum(1 for d in docks.values()
                                 if d.get("grid_mode") == "write_maps"),
            "n_docks_fresh": sum(1 for d in docks.values()
                                 if d.get("grid_mode") == "fresh"),
        }
        oks = {c: d for c, d in docks.items() if d["ok"]}
        if not oks:
            resultado["reason"] = "all_docks_failed"
            resultado["total_time_s"] = round(time.monotonic() - t_inicio, 1)
            return resultado
        resultado["rigid_scores"] = [d["best"] for _, d in sorted(oks.items())]
        resultado["rigid_best"] = round(min(d["best"] for d in oks.values()), 3)
        ranking = sorted(oks.items(), key=lambda kv: kv[1]["best"])[:top_k]

        # Fase 3: relax de las top-K poses (con grid cacheado si hay mapas).
        t0 = time.monotonic()
        crystal = leer_ligando(str(PDBBIND / pid / f"{pid}_ligand.sdf"))
        serial_a_mol = cargar_mapa_indices(work / pid)
        hay_mapas = any((Path(work) / pid / "maps").glob("*.map"))
        relajadas = []
        for cid, d in ranking:
            rr = relax_pose_archivo(pid, cid, d["pose"], work, cpu,
                                    maps_prefix=(str(Path(work) / pid / "maps" / "grid")
                                                 if hay_mapas else None))
            if not rr["ok"]:
                relajadas.append({"conf_id": cid, "rigid_score": d["best"],
                                  "ok": False, "reason": rr.get("reason")})
                continue
            por_mol = coords_pose_a_por_mol(rr["coords"], serial_a_mol)
            rmsd = rmsd_pesados(crystal, por_mol)
            relajadas.append({
                "conf_id": cid, "rigid_score": d["best"],
                "relaxed_score": round(rr["relaxed_rigid"], 3),
                "relaxed_local_score": (round(rr["relaxed_local"], 3)
                                        if rr["relaxed_local"] is not None else None),
                "delta": round(rr["relaxed_rigid"] - d["best"], 3),
                "rmsd_to_crystal": round(rmsd, 3) if rmsd is not None else None,
                "engine": rr["engine"], "ok": True,
            })
        resultado["time_fase3"] = round(time.monotonic() - t0, 1)
        resultado["top_k_relaxed"] = relajadas
        resultado["ok"] = any(r.get("ok") for r in relajadas)

        # RMSD del mejor pose rígido (top-1) al cristal.
        mejor_cid, mejor = ranking[0]
        por_mol = coords_pose_a_por_mol(mejor["pose"], serial_a_mol)
        r = rmsd_pesados(crystal, por_mol)
        resultado["rmsd_best_to_crystal"] = round(r, 3) if r is not None else None
        resultado["total_time_s"] = round(time.monotonic() - t_inicio, 1)
        if not resultado["ok"]:
            resultado["reason"] = "relax_unavailable"
        return resultado
    finally:
        if not keep and not out_dir:
            shutil.rmtree(work, ignore_errors=True)


# ───────────────────────────────── CLI ─────────────────────────────────────

def main() -> None:
    # Consola de Windows: forzar UTF-8 con reemplazo (patrón de
    # scripts/fase_b_expand_dataset.py).
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description="Motor MolFlex v2 (docking por ensemble + relax)")
    ap.add_argument("--pdb-id", required=True, help="Identificador PDBbind (4 caracteres)")
    ap.add_argument("--n-conf", type=int, default=DEFAULT_N_CONF)
    ap.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    ap.add_argument("--cpu", type=int, default=1, help="CPU por proceso Vina")
    ap.add_argument("--out-dir", default=None, help="Directorio de trabajo (default: temporal)")
    ap.add_argument("--keep", action="store_true", help="Conservar los archivos de trabajo")
    ap.add_argument("--out-json", default=None, help="Guardar el resultado JSON en un archivo")
    ap.add_argument("--experiment-id", default=DEFAULT_EXPERIMENT_ID,
                    help="Identificador del experimento para provenance.json "
                         "(FND-06; las corridas futuras deben pasarlo explicito)")
    args = ap.parse_args()

    sondeo = sondeo_openmm_relax()
    print("── Sondeo de capacidad OpenMM (Fase 3) ──")
    print(json.dumps(sondeo, indent=2, ensure_ascii=False))

    res = ejecutar_complejo(args.pdb_id, args.n_conf, args.top_k, args.cpu,
                            args.out_dir, args.keep, args.experiment_id)
    if args.out_json:
        Path(args.out_json).write_text(
            json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    print("── Resultado ──")
    print(json.dumps(res, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
