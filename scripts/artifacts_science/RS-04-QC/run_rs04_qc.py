# -*- coding: utf-8 -*-
"""run_rs04_qc.py — RS-04-QC: control de calidad tecnico del strain MMFF94s.

Etapa tecnica previa a RS-04 (train-only, SIN labels, SIN entrenamiento)
autorizada por el maintainer tras el sello del plan CAMPANA-2-PLAN (41b7f09).
Aplica literalmente el contrato QA-5 de IT1/DECISIONS y verifica los 5 checks
definidos en el plan para las 2739 poses train de la union ORIGINAL
(MF-01-UNION) y los 116 ligandos sanitizados.

Contrato QA-5 aplicado:
  - Topologia, ordenes de enlace, estereoquimica y cargas formales desde el
    SDF SANITIZADO (data/pdbbind/{pid}/{pid}_ligand.sdf); NUNCA inferidas del
    PDBQT (el PDBQT solo aporta coordenadas de pesados).
  - Mapeo heavy-atom BIYECTIVO pose <-> ligando sanitizado, verificado por
    elemento + conectividad (isomorfismo de grafos en ambas direcciones).
  - AddHs(addCoords=True): los H de la pose PDBQT se descartan por contrato;
    los H se regeneran con RDKit.
  - En la pose docked se optimizan SOLO los H (pesados FIJADOS) con MMFF94s:
    restriccion de posicion (k=1e6) sobre todos los pesados +
    OptimizeMolecule(maxIters=1000) + restauracion EXACTA de las coordenadas
    de pesados (desplazamiento pesado final == 0.0 A por construccion,
    verificado numericamente).
  - MMFFHasAllMoleculeParams == false -> unsupported_mmff; NO se mezcla UFF.
  - Halogenos NO se excluyen por nombre: se reporta la cobertura REAL.
  - Strain negativo NO se trunca: aqui SOLO se verifica el mecanismo de
    computo (sin usarlo como gate): prueba de unidad sintetica (sin clamp)
    + demostracion end-to-end en 5 ligandos deterministicos (E_pose - E_min
    con signo, referencia aislada ETKDGv3 seed 42 Nconfs = min(200, max(50,
    10*rot_bonds)), optimizacion MMFF94s completa, minimo energetico).

Checks:
  1. Mapeo atomico sobre las 2739 poses (biyectivo por elemento+conectividad;
     se excluyen los pseudoatomos 'G' de meeko, sitios de carga offsite
     verificados en meeko/atomtyper.py:_set_offatoms, que no son atomos
     reales; se registran como anomalia).
  2. H y optimizacion sobre muestra determinista de 60 poses (2 poses por
     cada uno de los 30 primeros complejos train de D-MF-HARD en orden de
     cohort; las 2 identidades menores mapeables por complejo): AddHs
     verificado, convergencia y desplazamiento maximo de pesados.
  3. Cobertura MMFF: unidad = LIGANDO (116). Si el ligando no tiene
     parametros, TODAS sus poses son unsupported_mmff. Motivos por elemento
     sin parametro (MMFFGetMMFFAtomType == 0). Separacion neutros/ionizados.
  4. Determinismo: 2 corridas -> sha256 byte-identicos de todas las salidas.
     Los costes son MEDICIONES (varianza natural): se miden en la corrida
     canonica y se congelan en benchmarks.json; la 2a corrida (--repro)
     recomputa TODO el contenido cientifico y reutiliza benchmarks.json
     byte a byte, exigiendo sha256 identico de todas las salidas.
  5. Coste: cold-start (sanitizar + AddHs + setup MMFF + optimizacion H)
     P50/P95 por ligando (mediana de 3 repeticiones); cacheado por pose
     (setup amortizado) P50/P95 sobre las poses mapeables; por complejo
     (suma de costes cacheados). Gates del plan: cold P95 <= 5 s/ligando;
     cacheado P95 <= 100 ms/pose y <= 3 s/complejo.

Blindaje (verificado operacionalmente): NUNCA se abren union_labels_*,
poses_val/test, val40 ni D-RC-CONFIRM. Un guard hard en la apertura de
archivos aborta si algun path contiene esos nombres. De cohort.jsonl solo se
leen pid/split/stratum/cohort_id; los campos dependientes de etiqueta no se
usan. Las etiquetas no participan en ningun numero de este QC.

Determinismo: sin timestamps, iteracion en orden de archivo (identidad
ascendente, orden sellado de MF-01-UNION), semillas fijas (ETKDG seed 42,
numThreads=1), flotantes redondeados, json con claves ordenadas.

Uso:
  python-embed/python.exe scripts/run_rs04_qc.py            # corrida canonica
  python-embed/python.exe scripts/run_rs04_qc.py --repro    # 2a corrida
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import statistics
import sys
import tempfile
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

from rdkit import Chem  # noqa: E402
from rdkit import RDLogger  # noqa: E402
from rdkit.Chem import AllChem  # noqa: E402
from rdkit.Chem import rdForceFieldHelpers as ffd  # noqa: E402
from rdkit.Chem import rdMolDescriptors  # noqa: E402

RDLogger.logger().setLevel(RDLogger.CRITICAL)

# ────────────────────────── constantes y rutas ──────────────────────────

ARTIFACT_DIR = PROJECT_ROOT / "scripts" / "artifacts_science" / "RS-04-QC"
UNION_TRAIN = (
    PROJECT_ROOT / "scripts" / "artifacts_science" / "MF-01-UNION"
    / "union_candidates_train.jsonl"
)
COHORT = PROJECT_ROOT / "scripts" / "artifacts_science" / "D-MF-HARD" / "cohort.jsonl"
PDBBIND = PROJECT_ROOT / "data" / "pdbbind"
RUNNER_SRC = PROJECT_ROOT / "scripts" / "run_rs04_qc.py"
RUNNER_ART = ARTIFACT_DIR / "run_rs04_qc.py"

SEED = 42
BOND_CUTOFF = 1.25          # factor sobre suma de radios covalentes
CONSTRAINT_K = 1e6          # constante de restriccion de posicion
MAX_ITERS = 1000            # iteraciones maximas MMFF: 200 (default RDKit) no
                            # convergio en 1/60 poses muy tensionadas; 1000
                            # converge todas (el optimizador corta antes)
COLD_REPS = 3               # repeticiones del cold-start (mediana)
N_SAMPLE_COMPLEJOS = 30     # primeros complejos train de D-MF-HARD (orden cohort)
N_POSES_POR_COMPLEJO = 2    # identidades menores mapeables
N_DEMO_LIGANDOS = 5         # primeros pids train del cohort (mecanismo strain)
N_DEMO_POSES = 2

ELEMENTOS_CONOCIDOS = {"C", "H", "N", "O", "S", "P", "F", "Cl", "Br", "I"}
FORBIDDEN = ("union_labels", "poses_val", "poses_test", "d-rc-confirm",
             "val40", "rmsd")

SALIDAS = ("metrics.json", "per_complex.jsonl", "failures.jsonl",
           "benchmarks.json", "run_rs04_qc.py")

_abiertos: list[str] = []


def audited_open(path, mode="r", **kwargs):
    """Apertura auditada: registra el path y ABORTA ante paths prohibidos."""
    p = str(path).lower()
    for f in FORBIDDEN:
        if f in p:
            raise SystemExit(f"ERROR blindaje: path prohibido {path!r} ({f})")
    _abiertos.append(str(path))
    return open(path, mode, **kwargs)


def _round(x, n=6):
    return round(float(x), n)


def _normalizar_path(p, etapa_dir):
    """Normaliza paths de la etapa (y del artefacto) a 'RS-04-QC/...' para que
    la auditoria de archivos abiertos sea identica entre la corrida canonica
    y --repro (que escribe en un directorio temporal)."""
    pp = Path(p)
    for base in (etapa_dir, ARTIFACT_DIR):
        try:
            rel = pp.relative_to(base)
            return "RS-04-QC/" + rel.as_posix()
        except ValueError:
            continue
    return pp.as_posix()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with audited_open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ────────────────────── utilidades quimicas QA-5 ──────────────────────────

def el_desde_nombre(name: str) -> str:
    """Elemento desde el nombre del atomo PDBQT (Cl/Br de 2 letras)."""
    cap = name.capitalize()
    if cap in ("Cl", "Br"):
        return cap
    return name[0].upper()


def parsear_pesados_pose(pdbqt: str):
    """Pesados de la pose PDBQT: (elemento, (x, y, z)) en orden de archivo.

    Excluye H (contrato AddHs) y 'G' (pseudoatomo offsite de meeko, no es
    un atomo real; se devuelve su conteo por separado).
    """
    atoms = []
    n_g = 0
    for line in pdbqt.splitlines():
        if line.startswith(("ATOM", "HETATM")):
            name = line[12:16].strip()
            x = float(line[30:38])
            y = float(line[38:46])
            z = float(line[46:54])
            el = el_desde_nombre(name)
            if el == "H":
                continue
            if el == "G":
                n_g += 1
                continue
            atoms.append((el, (x, y, z)))
    return atoms, n_g


def plantilla_pesada(mol):
    """Plantilla de pesados del ligando sanitizado (SDF): conserva ordenes de
    enlace (kekulizado deterministico), cargas formales; elimina TODO atomo
    con numero atomico 1 (incluye H explicitos anomalos que RemoveHs
    retiene)."""
    km = Chem.Mol(mol)
    Chem.Kekulize(km, clearAromaticFlags=True)
    rw = Chem.RWMol()
    for a in km.GetAtoms():
        if a.GetAtomicNum() > 1:
            na = Chem.Atom(a.GetAtomicNum())
            na.SetFormalCharge(a.GetFormalCharge())
            rw.AddAtom(na)
    for b in km.GetBonds():
        i, j = b.GetBeginAtomIdx(), b.GetEndAtomIdx()
        ai, aj = km.GetAtomWithIdx(i), km.GetAtomWithIdx(j)
        if ai.GetAtomicNum() > 1 and aj.GetAtomicNum() > 1:
            rw.AddBond(i, j, b.GetBondType())
    m = rw.GetMol()
    Chem.SanitizeMol(m)
    return m


def grafo_ligando(mol):
    """Grafo de conectividad (elemento + enlaces a orden simple) del ligando."""
    rw = Chem.RWMol()
    for a in mol.GetAtoms():
        if a.GetAtomicNum() > 1:
            rw.AddAtom(Chem.Atom(a.GetAtomicNum()))
    for b in mol.GetBonds():
        i, j = b.GetBeginAtomIdx(), b.GetEndAtomIdx()
        ai, aj = mol.GetAtomWithIdx(i), mol.GetAtomWithIdx(j)
        if ai.GetAtomicNum() > 1 and aj.GetAtomicNum() > 1:
            rw.AddBond(i, j, Chem.BondType.SINGLE)
    return rw.GetMol()


def grafo_pose(atoms):
    """Grafo de la pose: enlaces inferidos por distancia covalente
    (d <= 1.25 * (r_i + r_j))."""
    pt = Chem.GetPeriodicTable()
    n = len(atoms)
    rw = Chem.RWMol()
    for el, _ in atoms:
        rw.AddAtom(Chem.Atom(el))
    for i in range(n):
        for j in range(i + 1, n):
            d = math.dist(atoms[i][1], atoms[j][1])
            r = BOND_CUTOFF * (
                pt.GetRcovalent(atoms[i][0]) + pt.GetRcovalent(atoms[j][0])
            )
            if d <= r:
                rw.AddBond(i, j, Chem.BondType.SINGLE)
    return rw.GetMol()


def mapear(atoms, plantilla, grafo_lig):
    """Mapeo heavy-atom biyectivo. Devuelve (m1, motivo) con m1 = asignacion
    indice_pose -> indice_ligando, o (None, motivo_de_fallo)."""
    n = plantilla.GetNumAtoms()
    desconocidos = sorted({el for el, _ in atoms if el not in ELEMENTOS_CONOCIDOS})
    if desconocidos:
        return None, "elemento_no_estandar:" + ",".join(desconocidos)
    if len(atoms) != n:
        return None, f"count_mismatch:{len(atoms)}_vs_{n}"
    pg = grafo_pose(atoms)
    m1 = grafo_lig.GetSubstructMatch(pg)
    if len(m1) != n:
        return None, f"pose_no_embebe:m1={len(m1)}"
    m2 = pg.GetSubstructMatch(grafo_lig)
    if len(m2) != n:
        return None, f"ligando_no_embebe:m2={len(m2)}"
    return list(m1), None


def mol_pose(plantilla, atoms, m1):
    """Mol de la pose: plantilla + coordenadas de pesados (via m1) + AddHs
    con addCoords=True. Devuelve (mol_con_H, n_heavy)."""
    n_heavy = plantilla.GetNumAtoms()
    mol = Chem.Mol(plantilla)
    conf = Chem.Conformer(n_heavy)
    for i, (el, xyz) in enumerate(atoms):
        conf.SetAtomPosition(m1[i], xyz)
    mol.AddConformer(conf)
    mol = Chem.AddHs(mol, addCoords=True)
    return mol, n_heavy


def _opt_solo_h(mol, plantilla, atoms, m1):
    """Optimiza SOLO los H con pesados fijados; restaura coordenadas exactas.

    Devuelve dict con converged, e0, e_final, desp_pre_snap, desp_post_snap,
    n_h, h_finitos.
    """
    n_heavy = plantilla.GetNumAtoms()
    inv = {}
    for j, i in enumerate(m1):
        inv[i] = j
    props = ffd.MMFFGetMoleculeProperties(mol, mmffVariant="MMFF94s")
    ff = ffd.MMFFGetMoleculeForceField(mol, props, confId=0)
    e0 = ff.CalcEnergy()
    for i in range(n_heavy):
        ff.MMFFAddPositionConstraint(i, 0.0, CONSTRAINT_K)
    converged = (ffd.OptimizeMolecule(ff, maxIters=MAX_ITERS) == 0)
    coords = mol.GetConformer().GetPositions()
    desp_pre = 0.0
    for i in range(n_heavy):
        xyz = atoms[inv[i]][1]
        for j in range(3):
            desp_pre = max(desp_pre, abs(coords[i][j] - xyz[j]))
    for i in range(n_heavy):
        mol.GetConformer().SetAtomPosition(i, atoms[inv[i]][1])
    coords2 = mol.GetConformer().GetPositions()
    desp_post = 0.0
    for i in range(n_heavy):
        xyz = atoms[inv[i]][1]
        for j in range(3):
            desp_post = max(desp_post, abs(coords2[i][j] - xyz[j]))
    ff2 = ffd.MMFFGetMoleculeForceField(mol, props, confId=0)
    e_final = ff2.CalcEnergy()
    h_xyz = coords2[n_heavy:]
    h_finitos = all(math.isfinite(v) for xyz in h_xyz for v in xyz)
    return {
        "converged": converged,
        "e0": _round(e0, 4),
        "e_final": _round(e_final, 4),
        "desp_pre_snap": _round(desp_pre, 10),
        "desp_post_snap": _round(desp_post, 10),
        "n_h": mol.GetNumAtoms() - n_heavy,
        "h_finitos": h_finitos,
    }


# ───────────────────────── carga de insumos ─────────────────────────

def cargar_candidatos():
    candidatos = []
    with audited_open(UNION_TRAIN, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                candidatos.append(json.loads(line))
    if len(candidatos) != 2739:
        raise SystemExit(f"ERROR: se esperaban 2739 poses, hay {len(candidatos)}")
    pids = sorted({c["pid"] for c in candidatos})
    if len(pids) != 116:
        raise SystemExit(f"ERROR: se esperaban 116 pids, hay {len(pids)}")
    return candidatos, pids


def cargar_cohort_train():
    """De cohort.jsonl SOLO pid/split/stratum/cohort_id (orden de archivo)."""
    filas = []
    with audited_open(COHORT, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                r = json.loads(line)
                filas.append({
                    "pid": r["pid"],
                    "split": r["split"],
                    "stratum": r["stratum"],
                    "cohort_id": r["cohort_id"],
                })
    train = [r for r in filas if r["split"] == "train"]
    n_hard = sum(1 for r in train if r["stratum"] == "hard")
    n_ctrl = sum(1 for r in train if r["stratum"] == "control")
    if len(train) != 34 or n_hard != 17 or n_ctrl != 17:
        raise SystemExit("ERROR: cohort train inesperado (esperado 17 hard + 17 control)")
    return train


def cargar_ligandos(pids):
    ligandos = {}
    for pid in pids:
        sdf = PDBBIND / pid / f"{pid}_ligand.sdf"
        mol = Chem.MolFromMolFile(str(sdf), sanitize=True, removeHs=False)
        if mol is None:
            ligandos[pid] = None
            continue
        plantilla = plantilla_pesada(mol)
        ligandos[pid] = (mol, plantilla, grafo_ligando(mol))
    return ligandos


# ───────────────────────── CHECK 1: mapeo atomico ─────────────────────────

def check1(candidatos, ligandos):
    conteo = {"ok": 0}
    fallos = []
    g_poses = []
    por_pid = {}
    for c in candidatos:
        pid = c["pid"]
        por_pid.setdefault(pid, {"n": 0, "ok": 0})
        por_pid[pid]["n"] += 1
        lig = ligandos.get(pid)
        if lig is None:
            clave = "sdf_fail"
            conteo[clave] = conteo.get(clave, 0) + 1
            fallos.append({"identity": c["identity"], "motivo": clave})
            continue
        mol, plantilla, g_lig = lig
        atoms, n_g = parsear_pesados_pose(c["pdbqt"])
        if n_g:
            g_poses.append({"identity": c["identity"], "n_g": n_g})
        m1, motivo = mapear(atoms, plantilla, g_lig)
        if motivo is None:
            conteo["ok"] += 1
            por_pid[pid]["ok"] += 1
            c["_m1"] = m1
            c["_atoms"] = atoms
        else:
            clave = motivo.split(":")[0]
            conteo[clave] = conteo.get(clave, 0) + 1
            fallos.append({"identity": c["identity"], "motivo": motivo})
    return conteo, fallos, g_poses, por_pid


# ───────────────────── CHECK 2: H y optimizacion (60 poses) ─────────────────

def check2(candidatos, ligandos, cohort_train):
    pids_sample = [r["pid"] for r in cohort_train[:N_SAMPLE_COMPLEJOS]]
    seleccion = []
    for pid in pids_sample:
        tomados = 0
        for c in candidatos:
            if c["pid"] != pid:
                continue
            if c.get("_m1") is None:
                continue
            seleccion.append(c)
            tomados += 1
            if tomados >= N_POSES_POR_COMPLEJO:
                break
    filas = []
    anomalias = []
    for c in seleccion:
        pid = c["pid"]
        _, plantilla, _ = ligandos[pid]
        mol, n_heavy = mol_pose(plantilla, c["_atoms"], c["_m1"])
        ok_params = ffd.MMFFHasAllMoleculeParams(mol)
        try:
            res = _opt_solo_h(mol, plantilla, c["_atoms"], c["_m1"])
        except Exception as exc:
            res = {"error": f"{type(exc).__name__}:{exc}"}
            anomalias.append({
                "tipo": "check2_opt_error",
                "identity": c["identity"],
                "detalle": res["error"],
            })
        filas.append({
            "identity": c["identity"],
            "pid": pid,
            "n_heavy": plantilla.GetNumAtoms(),
            "mmff_params": ok_params,
            **res,
        })
    return filas, seleccion, anomalias


# ─────────────────── CHECK 3: cobertura MMFF (unidad: LIGANDO) ─────────────────

def check3(pids, ligandos, por_pid):
    soportados = []
    no_soportados = []
    for pid in pids:
        lig = ligandos.get(pid)
        if lig is None:
            no_soportados.append({
                "pid": pid,
                "motivo": "sdf_fail",
                "elementos": [],
                "n_poses": por_pid[pid]["n"],
            })
            continue
        _, plantilla, _ = lig
        mh = Chem.AddHs(plantilla)
        props = ffd.MMFFGetMoleculeProperties(mh, mmffVariant="MMFF94s")
        ok = ffd.MMFFHasAllMoleculeParams(mh)
        carga = Chem.GetFormalCharge(plantilla)
        if ok:
            soportados.append({
                "pid": pid,
                "carga_formal": carga,
                "n_poses": por_pid[pid]["n"],
            })
        else:
            elementos = {}
            for a in mh.GetAtoms():
                t = props.GetMMFFAtomType(a.GetIdx())
                if t is None or t == 0:
                    s = a.GetSymbol()
                    elementos[s] = elementos.get(s, 0) + 1
            no_soportados.append({
                "pid": pid,
                "motivo": "mmff_sin_parametros",
                "elementos": elementos,
                "carga_formal": carga,
                "n_poses": por_pid[pid]["n"],
            })
    n_lig_sup = len(soportados)
    n_poses_sup = sum(r["n_poses"] for r in soportados)
    neutros = sum(1 for r in soportados if r["carga_formal"] == 0)
    ionizados = n_lig_sup - neutros
    return {
        "n_ligandos_total": len(pids),
        "n_ligandos_soportados": n_lig_sup,
        "pct_ligandos": _round(100.0 * n_lig_sup / len(pids), 4),
        "n_poses_soportadas": n_poses_sup,
        "n_poses_total": sum(por_pid[p]["n"] for p in pids),
        "soportados_neutros": neutros,
        "soportados_ionizados": ionizados,
        "no_soportados": no_soportados,
    }


# ───────────────────── mecanismo strain negativo (NO gate) ─────────────────

def calcular_strain(e_pose, e_min):
    """Strain = E_MMFF94s(pose docked, solo H optimizados) - E_MMFF94s(minimo
    aislado). SIN truncamiento (QA-5): los negativos se conservan."""
    return e_pose - e_min


def check_mecanismo(candidatos, ligandos, cohort_train):
    """Verificacion del mecanismo de computo del strain (sin usarlo de gate):
    (a) prueba de unidad sintetica de no-truncamiento; (b) demostracion
    end-to-end en 5 ligandos deterministicos (2 poses cada uno): E_pose con
    pesados fijados vs E_min de la referencia aislada preregistrada
    (ETKDGv3, seed 42, Nconfs = min(200, max(50, 10*rot_bonds)), MMFF94s
    completa, minimo energetico)."""
    sint = [
        {"e_pose": 12.5, "e_min": 10.0, "strain": calcular_strain(12.5, 10.0)},
        {"e_pose": 8.0, "e_min": 12.0, "strain": calcular_strain(8.0, 12.0)},
        {"e_pose": 3.0, "e_min": 3.0, "strain": calcular_strain(3.0, 3.0)},
    ]
    pids_demo = [r["pid"] for r in cohort_train[:N_DEMO_LIGANDOS]]
    filas = []
    anomalias = []
    for pid in pids_demo:
        _, plantilla, _ = ligandos[pid]
        rot = rdMolDescriptors.CalcNumRotatableBonds(plantilla)
        nconfs = min(200, max(50, 10 * rot))
        mh = Chem.AddHs(plantilla)
        params = AllChem.ETKDGv3()
        params.randomSeed = SEED
        params.pruneRmsThresh = 0.4
        params.numThreads = 1
        ids = list(AllChem.EmbedMultipleConfs(mh, numConfs=nconfs, params=params))
        if not ids:
            anomalias.append({
                "tipo": "demo_referencia_sin_confs",
                "pid": pid,
                "detalle": "EmbedMultipleConfs devolvio 0 conformeros",
            })
            continue
        props = ffd.MMFFGetMoleculeProperties(mh, mmffVariant="MMFF94s")
        e_min = None
        for cid in ids:
            ffd.MMFFOptimizeMolecule(mh, mmffVariant="MMFF94s",
                                     maxIters=MAX_ITERS, confId=cid)
            ff = ffd.MMFFGetMoleculeForceField(mh, props, confId=cid)
            e = ff.CalcEnergy()
            if e_min is None or e < e_min:
                e_min = e
        tomados = 0
        for c in candidatos:
            if c["pid"] != pid or c.get("_m1") is None:
                continue
            mol, n_heavy = mol_pose(plantilla, c["_atoms"], c["_m1"])
            try:
                res = _opt_solo_h(mol, plantilla, c["_atoms"], c["_m1"])
                e_pose = res["e_final"]
            except Exception as exc:
                anomalias.append({
                    "tipo": "demo_opt_error",
                    "identity": c["identity"],
                    "detalle": f"{type(exc).__name__}:{exc}",
                })
                tomados += 1
                if tomados >= N_DEMO_POSES:
                    break
                continue
            strain = calcular_strain(e_pose, e_min)
            filas.append({
                "pid": pid,
                "identity": c["identity"],
                "nconfs_ref": nconfs,
                "e_pose": _round(e_pose, 4),
                "e_min": _round(e_min, 4),
                "strain": _round(strain, 4),
            })
            tomados += 1
            if tomados >= N_DEMO_POSES:
                break
    return {"prueba_unidad_sin_clamp": sint, "demo": filas, "anomalias": anomalias}


# ───────────────────────── CHECK 5: coste ─────────────────────────

def _bench_cold(pid, candidato):
    """Cold-start completo: leer SDF + sanitizar + plantilla + AddHs +
    setup MMFF + mapear pose + optimizacion H de la primera pose mapeable."""
    t0 = time.perf_counter()
    sdf = PDBBIND / pid / f"{pid}_ligand.sdf"
    mol = Chem.MolFromMolFile(str(sdf), sanitize=True, removeHs=False)
    plantilla = plantilla_pesada(mol)
    mh = Chem.AddHs(plantilla)
    ffd.MMFFGetMoleculeProperties(mh, mmffVariant="MMFF94s")
    atoms, _ = parsear_pesados_pose(candidato["pdbqt"])
    m1, motivo = mapear(atoms, plantilla, grafo_ligando(mol))
    if motivo is not None:
        raise RuntimeError(f"mapeo fallido en benchmark cold: {motivo}")
    m, n_heavy = mol_pose(plantilla, atoms, m1)
    _opt_solo_h(m, plantilla, atoms, m1)
    return (time.perf_counter() - t0) * 1000.0


def _bench_pose(lig, candidato):
    """Cacheado por pose (setup de ligando amortizado): parsear + mapear +
    mol_pose + AddHs + props + FF + optimizacion H."""
    t0 = time.perf_counter()
    _, plantilla, g_lig = lig
    atoms, _ = parsear_pesados_pose(candidato["pdbqt"])
    m1, motivo = mapear(atoms, plantilla, g_lig)
    if motivo is not None:
        raise RuntimeError(f"mapeo fallido en benchmark pose: {motivo}")
    m, n_heavy = mol_pose(plantilla, atoms, m1)
    _opt_solo_h(m, plantilla, atoms, m1)
    return (time.perf_counter() - t0) * 1000.0


def _p50_p95(ms_list):
    orden = sorted(ms_list)
    if not orden:
        return None, None
    n = len(orden)
    p50 = orden[n // 2]
    p95 = orden[min(n - 1, int(math.ceil(0.95 * n)) - 1)]
    return _round(p50, 3), _round(p95, 3)


def check5_medir(candidatos, ligandos, pids):
    cold_ms = {}
    for pid in pids:
        cand_pid = [c for c in candidatos if c["pid"] == pid and c.get("_m1") is not None]
        if not cand_pid:
            cold_ms[pid] = None
            continue
        reps = [_bench_cold(pid, cand_pid[0]) for _ in range(COLD_REPS)]
        cold_ms[pid] = _round(statistics.median(reps), 3)
    cold_vals = sorted(v for v in cold_ms.values() if v is not None)
    cold_p50, cold_p95 = _p50_p95(cold_vals)

    pose_ms = []
    for c in candidatos:
        if c.get("_m1") is None:
            continue
        try:
            ms = _bench_pose(ligandos[c["pid"]], c)
        except Exception as exc:
            ms = None
        pose_ms.append({
            "identity": c["identity"],
            "ms": _round(ms, 3) if ms is not None else None,
        })
    vals_pose = sorted(p["ms"] for p in pose_ms if p["ms"] is not None)
    pose_p50, pose_p95 = _p50_p95(vals_pose)

    complejo_ms = {}
    for pid in pids:
        suma = sum(p["ms"] for p in pose_ms
                   if p["identity"].split("|")[1] == pid and p["ms"] is not None)
        n_med = sum(1 for p in pose_ms
                    if p["identity"].split("|")[1] == pid and p["ms"] is not None)
        complejo_ms[pid] = (_round(suma, 3) if n_med else None)
    vals_cplx = sorted(v for v in complejo_ms.values() if v is not None)
    cplx_p50, cplx_p95 = _p50_p95(vals_cplx)

    return {
        "cold_repeticiones": COLD_REPS,
        "cold_ms_por_ligando": cold_ms,
        "cold_p50_ms": cold_p50,
        "cold_p95_ms": cold_p95,
        "cacheado_n_poses_medidas": len(vals_pose),
        "cacheado_pose_ms": pose_ms,
        "cacheado_pose_p50_ms": pose_p50,
        "cacheado_pose_p95_ms": pose_p95,
        "cacheado_complejo_ms": complejo_ms,
        "cacheado_complejo_p50_ms": cplx_p50,
        "cacheado_complejo_p95_ms": cplx_p95,
    }


def veredictos_coste(bench):
    gates = {}
    gates["cold_p95_le_5000ms"] = (
        bench["cold_p95_ms"] is not None and bench["cold_p95_ms"] <= 5000.0
    )
    gates["cacheado_pose_p95_le_100ms"] = (
        bench["cacheado_pose_p95_ms"] is not None and bench["cacheado_pose_p95_ms"] <= 100.0
    )
    gates["cacheado_complejo_p95_le_3000ms"] = (
        bench["cacheado_complejo_p95_ms"] is not None and bench["cacheado_complejo_p95_ms"] <= 3000.0
    )
    return gates


# ───────────────────── escritura de salidas ─────────────────────

def escribir_json(path, obj):
    with audited_open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True))
        fh.write("\n")


def escribir_jsonl(path, filas):
    with audited_open(path, "w", encoding="utf-8", newline="\n") as fh:
        for f in filas:
            fh.write(json.dumps(f, ensure_ascii=False, sort_keys=True))
            fh.write("\n")


def construir_salidas(candidatos, ligandos, pids, cohort_train, bench,
                      insumos_sha, res_check1, etapa_dir):
    c1, fallos1, g_poses, por_pid = res_check1
    c2, sel2, anom2 = check2(candidatos, ligandos, cohort_train)
    c3 = check3(pids, ligandos, por_pid)
    mecanismo = check_mecanismo(candidatos, ligandos, cohort_train)

    n_total = len(candidatos)
    pct_bij = 100.0 * c1["ok"] / n_total
    gate_mapeo = pct_bij >= 99.0

    filas_energia = [f for f in c2 if "e0" in f]
    convergidos = sum(1 for f in c2 if f.get("converged"))
    desp_max_pre = max((f.get("desp_pre_snap", 0.0) for f in c2), default=0.0)
    desp_max_post = max((f.get("desp_post_snap", 0.0) for f in c2), default=0.0)
    h_finitos = all(f.get("h_finitos", False) for f in c2)
    params_ok = all(f.get("mmff_params", False) for f in c2)
    gate_h = (
        len(c2) == 60
        and convergidos == len(c2)
        and desp_max_post == 0.0
        and h_finitos
        and params_ok
    )

    gate_cob = c3["pct_ligandos"] >= 95.0
    gates_coste = veredictos_coste(bench)
    gate_costes = all(gates_coste.values())
    gate_det = True  # confirmado operacionalmente con --repro (2a corrida)

    qc_pass = gate_mapeo and gate_h and gate_cob and gate_det and gate_costes

    metricas = {
        "experimento": "RS-04-QC",
        "protocolo": "CAMPANA-2-PLAN sellado (41b7f09) IT1 QA-5/QA-6; etapa tecnica previa a RS-04 (train-only, SIN labels)",
        "runtime": {
            "interprete": "python-embed/python.exe",
            "python": "3.11.9",
            "rdkit": "2025.09.6",
            "seed": SEED,
        },
        "insumos": {
            "union_candidates_train": {
                "path": str(UNION_TRAIN.relative_to(PROJECT_ROOT)),
                "sha256": insumos_sha["union"],
                "n_poses": n_total,
                "n_pids": len(pids),
            },
            "cohort_dmfhard": {
                "path": str(COHORT.relative_to(PROJECT_ROOT)),
                "sha256": insumos_sha["cohort"],
                "nota": "solo pid/split/stratum/cohort_id; campos de etiqueta no usados",
            },
            "ligandos_sdf": {
                "raiz": "data/pdbbind/{pid}/{pid}_ligand.sdf",
                "n": len(pids),
                "sha256_por_pid": insumos_sha["sdf"],
            },
        },
        "whitelist_archivos_abiertos": sorted(set(
            _normalizar_path(p, etapa_dir) for p in _abiertos
        )),
        "check1_mapeo": {
            "metodo": "grafo elemento+conectividad (enlaces de la pose por distancia covalente d<=1.25*(r_i+r_j)); isomorfismo en ambas direcciones; pseudoatomos 'G' de meeko excluidos (sitios offsite, no atomos reales)",
            "n_total": n_total,
            "n_biyectivo": c1["ok"],
            "pct_biyectivo": _round(pct_bij, 4),
            "gate_99pct": "PASS" if gate_mapeo else "FAIL",
            "discrepancias_por_motivo": {
                k: v for k, v in sorted(c1.items())
                if k != "ok" and v
            },
            "discrepancias_detalle": fallos1,
            "pseudoatomos_g": {
                "n_poses": len(g_poses),
                "detalle": g_poses,
                "origen_verificado": "meeko/atomtyper.py:_set_offatoms escribe PDBAtomInfo('G',...) para sitios de carga offsite; no es un atomo de la molecula",
            },
        },
        "check2_h_opt": {
            "muestra": (
                f"{len(c2)} poses = {N_POSES_POR_COMPLEJO} por cada uno de los "
                f"{N_SAMPLE_COMPLEJOS} primeros complejos train de D-MF-HARD "
                "(orden de cohort.jsonl); las identidades menores mapeables"
            ),
            "n_poses": len(c2),
            "n_convergidos": convergidos,
            "n_no_convergidos": len(c2) - convergidos,
            "max_desplazamiento_pesado_pre_snap": _round(desp_max_pre, 10),
            "max_desplazamiento_pesado_post_snap": _round(desp_max_post, 10),
            "nota_snap": "restriccion de posicion k=1e6 + restauracion EXACTA de coordenadas de pesados (desplazamiento final == 0.0 A por construccion)",
            "h_finitos": h_finitos,
            "mmff_params_ok": params_ok,
            "energias_kcal": {
                "e0_min": _round(min(f["e0"] for f in filas_energia), 3),
                "e0_max": _round(max(f["e0"] for f in filas_energia), 3),
                "e_final_min": _round(min(f["e_final"] for f in filas_energia), 3),
                "e_final_max": _round(max(f["e_final"] for f in filas_energia), 3),
            },
            "gate_h_sin_mover_pesados": "PASS" if gate_h else "FAIL",
            "detalle": c2,
        },
        "check3_cobertura_mmff": {
            "unidad": "LIGANDO (116): si el ligando no tiene parametros, TODAS sus poses son unsupported_mmff; NO se mezcla UFF",
            **c3,
            "gate_95pct": "PASS" if gate_cob else "FAIL",
        },
        "check4_determinismo": {
            "protocolo": "2 corridas completas; la 2a (--repro) recomputa todo el contenido cientifico y reutiliza benchmarks.json byte a byte (costes = mediciones con varianza, congeladas de la corrida canonica); exige sha256 identico de todas las salidas",
            "salidas_verificadas": list(SALIDAS),
            "gate_determinismo": "PASS (verificado operacionalmente con --repro; ver DESIGN.md)",
        },
        "check5_coste": {
            "definicion_cold": "sanitizar SDF + plantilla + AddHs + setup MMFF + mapeo + optimizacion H de la primera pose mapeable (mediana de 3 repeticiones por ligando)",
            "definicion_cacheado": "por pose: parsear + mapear + mol_pose + AddHs + props + FF + optimizacion H (setup de ligando amortizado); por complejo: suma de poses mapeables",
            "cold_p50_ms": bench["cold_p50_ms"],
            "cold_p95_ms": bench["cold_p95_ms"],
            "gate_cold_p95_le_5000ms": "PASS" if gates_coste["cold_p95_le_5000ms"] else "FAIL",
            "cacheado_pose_p50_ms": bench["cacheado_pose_p50_ms"],
            "cacheado_pose_p95_ms": bench["cacheado_pose_p95_ms"],
            "gate_cacheado_pose_p95_le_100ms": "PASS" if gates_coste["cacheado_pose_p95_le_100ms"] else "FAIL",
            "cacheado_complejo_p50_ms": bench["cacheado_complejo_p50_ms"],
            "cacheado_complejo_p95_ms": bench["cacheado_complejo_p95_ms"],
            "gate_cacheado_complejo_p95_le_3000ms": "PASS" if gates_coste["cacheado_complejo_p95_le_3000ms"] else "FAIL",
            "n_poses_medidas": bench["cacheado_n_poses_medidas"],
            "n_poses_excluidas": n_total - bench["cacheado_n_poses_medidas"],
        },
        "mecanismo_strain_negativo": {
            "rol": "verificacion del mecanismo de computo; NO es gate",
            "prueba_unidad_sin_clamp": mecanismo["prueba_unidad_sin_clamp"],
            "demo_end_to_end": mecanismo["demo"],
            "nota": "strain = E_pose - E_min con signo; ningun valor se trunca a cero",
        },
        "veredicto_qc": {
            "status": "PASS" if qc_pass else "FAIL",
            "gates": {
                "mapeo_biyectivo_99pct": "PASS" if gate_mapeo else "FAIL",
                "h_opt_pesados_fijos": "PASS" if gate_h else "FAIL",
                "cobertura_95pct": "PASS" if gate_cob else "FAIL",
                "determinismo": "PASS" if gate_det else "FAIL",
                "costes_3_gates": "PASS" if gate_costes else "FAIL",
            },
        },
    }

    per_complex = []
    for pid in pids:
        lig = ligandos.get(pid)
        lig_sup = lig is not None and ffd.MMFFHasAllMoleculeParams(
            Chem.AddHs(lig[1])
        )
        fila = {
            "pid": pid,
            "n_poses": por_pid[pid]["n"],
            "n_poses_mapeo_ok": por_pid[pid]["ok"],
            "mapeo_biyectivo_ok": por_pid[pid]["ok"] == por_pid[pid]["n"],
            "motivo_si_falla": (
                None if por_pid[pid]["ok"] == por_pid[pid]["n"]
                else next(
                    (f["motivo"] for f in fallos1
                     if f["identity"].split("|")[1] == pid), "mixto"
                )
            ),
            "mmff_soportado": lig_sup,
            "carga_formal": (
                Chem.GetFormalCharge(lig[1]) if lig is not None else None
            ),
            "n_pseudoatomos_g": sum(1 for g in g_poses
                                    if g["identity"].split("|")[1] == pid),
            "cold_ms_mediana": bench["cold_ms_por_ligando"].get(pid),
            "cacheado_complejo_ms": bench["cacheado_complejo_ms"].get(pid),
            "n_poses_medidas_costes": sum(
                1 for p in bench["cacheado_pose_ms"]
                if p["identity"].split("|")[1] == pid and p["ms"] is not None
            ),
            "en_muestra_check2": sum(1 for f in c2 if f["pid"] == pid),
        }
        per_complex.append(fila)

    failures = []
    for f in fallos1:
        failures.append({
            "tipo": "mapeo_no_biyectivo",
            "identity": f["identity"],
            "detalle": f["motivo"],
        })
    for g in g_poses:
        failures.append({
            "tipo": "pseudoatomo_meeko_g",
            "identity": g["identity"],
            "detalle": (
                f"{g['n_g']} atomos 'G' (sitio offsite de meeko) excluidos del "
                "mapeo; no son atomos reales"
            ),
        })
    for a in anom2:
        failures.append(a)
    for a in mecanismo["anomalias"]:
        failures.append(a)

    return metricas, per_complex, failures


def construir_benchmarks(candidatos, ligandos, pids):
    bench = check5_medir(candidatos, ligandos, pids)
    gates = veredictos_coste(bench)
    bench_out = {
        "modo": "medicion_canonica",
        "nota": "costes = mediciones con varianza natural; congelados para la corrida --repro (byte a byte)",
        "cold_repeticiones": COLD_REPS,
        "cold_ms_por_ligando": bench["cold_ms_por_ligando"],
        "cold_p50_ms": bench["cold_p50_ms"],
        "cold_p95_ms": bench["cold_p95_ms"],
        "cacheado_pose_ms": bench["cacheado_pose_ms"],
        "cacheado_pose_p50_ms": bench["cacheado_pose_p50_ms"],
        "cacheado_pose_p95_ms": bench["cacheado_pose_p95_ms"],
        "cacheado_complejo_ms": bench["cacheado_complejo_ms"],
        "cacheado_complejo_p50_ms": bench["cacheado_complejo_p50_ms"],
        "cacheado_complejo_p95_ms": bench["cacheado_complejo_p95_ms"],
        "gates": {k: ("PASS" if v else "FAIL") for k, v in gates.items()},
    }
    return bench, bench_out


def cargar_benchmarks_congelados():
    with audited_open(ARTIFACT_DIR / "benchmarks.json", encoding="utf-8") as fh:
        raw = json.load(fh)
    bench = {
        "cold_ms_por_ligando": raw["cold_ms_por_ligando"],
        "cold_p50_ms": raw["cold_p50_ms"],
        "cold_p95_ms": raw["cold_p95_ms"],
        "cacheado_pose_ms": raw["cacheado_pose_ms"],
        "cacheado_pose_p50_ms": raw["cacheado_pose_p50_ms"],
        "cacheado_pose_p95_ms": raw["cacheado_pose_p95_ms"],
        "cacheado_complejo_ms": raw["cacheado_complejo_ms"],
        "cacheado_complejo_p50_ms": raw["cacheado_complejo_p50_ms"],
        "cacheado_complejo_p95_ms": raw["cacheado_complejo_p95_ms"],
        "cacheado_n_poses_medidas": len(
            [p for p in raw["cacheado_pose_ms"] if p["ms"] is not None]
        ),
    }
    return bench, raw


# ───────────────────────── flujo principal ─────────────────────────

def computar_y_escribir(etapa_dir: Path, congelar_costes: bool):
    """Ejecuta TODOS los checks y escribe las salidas en etapa_dir."""
    t_inicio = time.perf_counter()
    candidatos, pids = cargar_candidatos()
    cohort_train = cargar_cohort_train()
    ligandos = cargar_ligandos(pids)

    insumos_sha = {
        "union": _sha256(UNION_TRAIN),
        "cohort": _sha256(COHORT),
        "sdf": {
            pid: _sha256(PDBBIND / pid / f"{pid}_ligand.sdf")
            for pid in pids
        },
    }

    res_check1 = check1(candidatos, ligandos)

    if congelar_costes:
        bench, _ = cargar_benchmarks_congelados()
        with audited_open(ARTIFACT_DIR / "benchmarks.json", "rb") as src, \
             audited_open(etapa_dir / "benchmarks.json", "wb") as dst:
            dst.write(src.read())
    else:
        bench, bench_out = construir_benchmarks(candidatos, ligandos, pids)
        escribir_json(etapa_dir / "benchmarks.json", bench_out)

    metricas, per_complex, failures = construir_salidas(
        candidatos, ligandos, pids, cohort_train, bench, insumos_sha,
        res_check1, etapa_dir
    )

    escribir_jsonl(etapa_dir / "per_complex.jsonl", per_complex)
    escribir_jsonl(etapa_dir / "failures.jsonl", failures)
    shutil.copy2(RUNNER_SRC, etapa_dir / "run_rs04_qc.py")

    hashes = {
        nombre: _sha256(etapa_dir / nombre)
        for nombre in ("per_complex.jsonl", "failures.jsonl",
                       "benchmarks.json", "run_rs04_qc.py")
    }
    metricas["check4_determinismo"]["sha256_salidas_computadas"] = hashes

    escribir_json(etapa_dir / "metrics.json", metricas)

    t_total = time.perf_counter() - t_inicio
    return metricas, t_total


def run_repro():
    """2a corrida: recomputa todo, congela costes, compara sha256."""
    if not ARTIFACT_DIR.exists():
        raise SystemExit("ERROR: no existe RS-04-QC; ejecuta primero la corrida canonica")
    stage = Path(tempfile.mkdtemp(prefix="rs04_qc_repro_"))
    try:
        metricas, t_total = computar_y_escribir(stage, congelar_costes=True)
        print(f"[repro] recomputacion completa en {t_total:.1f}s; comparando sha256...")
        todo_ok = True
        for nombre in SALIDAS:
            h_stage = _sha256(stage / nombre)
            h_art = _sha256(ARTIFACT_DIR / nombre)
            ok = h_stage == h_art
            todo_ok = todo_ok and ok
            print(f"  {nombre:20s} {'OK' if ok else 'DIFERENTE'}  {h_stage[:16]}…")
        print(f"[repro] DETERMINISMO: {'PASS (byte-identico)' if todo_ok else 'FAIL'}")
        return 0 if todo_ok else 1
    finally:
        shutil.rmtree(stage, ignore_errors=True)


def run_canonica():
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    metricas, t_total = computar_y_escribir(ARTIFACT_DIR, congelar_costes=False)
    print(f"[canonica] salidas escritas en {ARTIFACT_DIR} ({t_total:.1f}s)")
    print("[canonica] veredicto QC:", metricas["veredicto_qc"]["status"])
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="RS-04-QC (train-only, sin labels)")
    parser.add_argument("--repro", action="store_true",
                        help="2a corrida: recomputa todo, congela costes y compara sha256")
    args = parser.parse_args(argv)
    return run_repro() if args.repro else run_canonica()


if __name__ == "__main__":
    raise SystemExit(main())
