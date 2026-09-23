#!/usr/bin/env python3
r"""freesolv_h3.py — MM-GBSA, H3: ¿el radio GB de Bondi para Br e I acierta mejor la hidratación que 1,5 Å?

**Tipo: medición contra experimento, sin ajustar nada en Br ni en I.** Hipótesis
H3 de `docs/validacion_mmgbsa.md`, con las notas del propietario (informe del
2026-09-23): se prueba el radio GB dentro del dominio de GBn2 (la tabla del
cuello sólo admite 1-2 Å); los radios PB optimizados con punto extra
(Fortuna y Costa 2021, Br 2,3-2,8 Å, I 2,5-3,1 Å) quedan fuera de GBn2 y de
esta hipótesis.

# Datos

FreeSolv v0.52 (Mobley y Guthrie 2014; release DOI 10.5281/zenodo.1161245;
datos CC BY 4.0, código MIT). 642 moléculas neutras: 25 con Br (21 sólo con
Br; 2 también con Cl y 2 con F) y 12 con I. Se usan las coordenadas 3D de sus SDF, **un solo
confórmero y sin minimizar**: es una estimación estática de solvatación
implícita, no un cálculo de energía libre con muestreo. Los datos no se
redistribuyen en el repositorio: sólo identificadores, valores calculados y la
atribución.

# El modelo, capa por capa (declarado antes de medir)

- **Polar:** GBn2 de OpenMM 8.5.2 con las correcciones del protocolo candidato
  (fósforo y descreening de Amber, MMGBSA-H13), ε 1 / 78,5, sin sal. GAFF2 y
  AM1-BCC con antechamber; radios mbondi3 de tleap para todo salvo el brazo.
- **No polar:** γ·SASA + b, con la SASA de FreeSASA (Lee-Richards, la de la RDKit
  que viaja; MMGBSA-H12) con radios de Bondi y sin hidrógenos. γ y b se ajustan
  **sólo con las moléculas sin halógeno** (C, H, N, O, S, P), antes de mirar Br
  o I: así ningún radio de Br/I puede compensar un sesgo del término no polar.
- **Brazos del radio GB de Br e I** (el apantallamiento y α, β, γ de GBn2 no
  cambian): A = el de hoy, 1,5 Å (mbondi3); B = Bondi, Br 1,85 Å, I 1,98 Å. El
  radio se cambia en el prmtop antes de construir el sistema, porque OpenMM arma
  la tabla del cuello con los radios de entrada.
- **Referencia electrostática (capa 1, fuera del gate):** PB de AmberTools
  (`pbsa`, radiopt=0: los mismos radios del prmtop) para cada brazo.

# Gate (el del prerregistro)

Ningún parámetro de Br o I se ajusta, así que las 37 moléculas con Br o I son
todas de prueba. GO si MAE_BrI(B) ≤ 0,8 · MAE_BrI(A) y el IC bootstrap al 95 %
(1000 remuestreos de moléculas) de MAE_B − MAE_A queda entero por debajo de 0.
El Br y el I se informan por separado (sin las 4 mixtas), y los
controles (Cl, F, sin halógeno) no cambian entre brazos por construcción.

# Etapas

    python backend/audits/freesolv_h3.py curar --freesolv <repo> --sdf <dir>
    python backend/audits/freesolv_h3.py parametrizar --sdf <dir> --trabajo <dir> --salida <json>   # AmberTools
    python backend/audits/freesolv_h3.py medir --trabajo <dir> --salida <crudo.json> [--sin-pb]
    python backend/audits/freesolv_h3.py resumir --crudo <crudo.json> --artefactos <dir>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import numpy as np

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(AQUI.parent))

SALIDA = AQUI / "freesolv_h3"
ATRIBUCION = ("FreeSolv v0.52 (Mobley y Guthrie, J. Comput.-Aided Mol. Des. 2014; release DOI "
              "10.5281/zenodo.1161245), datos bajo CC BY 4.0. Los autores advierten que parte de los "
              "datos procede de fuentes con restricciones que podrían desconocer.")
BONDI = {1: 1.20, 6: 1.70, 7: 1.55, 8: 1.52, 9: 1.47, 15: 1.80, 16: 1.80, 17: 1.75, 35: 1.85, 53: 1.98}
RADIO_GB_BRAZO_B = {35: 1.85, 53: 1.98}
SEMILLA = 20260923
REMUESTREOS = 1000
REDUCCION_MINIMA = 0.20


def _ahora() -> str:
    from datetime import UTC, datetime
    return datetime.now(UTC).isoformat()


def _sha(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def _grupo(simbolos: set[str]) -> str:
    hal = simbolos & {"F", "Cl", "Br", "I"}
    if hal == {"Br"}:
        return "Br"
    if hal == {"I"}:
        return "I"
    if "Br" in hal:
        return "Br_mixto"
    if "I" in hal:
        return "I_mixto"
    if not hal:
        return "sin_halogeno"
    if hal == {"Cl"}:
        return "Cl"
    if hal == {"F"}:
        return "F"
    return "otro_halogeno"


# ── 1. Curación ──────────────────────────────────────────────────────────
#
# Los SDF de FreeSolv (OEChem) escriben el nitro como N(-O-)(-O-): enlaces
# sencillos, dos O con carga -1 y el N neutro (carga neta -2), aunque el
# SMILES de la misma molécula es [N+](=O)[O-]. Visto el 2026-09-23 en 37
# moléculas, antes de medir. Regla declarada: en un N con exactamente dos
# vecinos O de carga -1 y enlace sencillo y un tercer vecino, un N-O pasa a
# doble, ese O a neutro y el N a +1. Después se exige que el InChIKey del SDF
# corregido coincida con el del SMILES; si no, la molécula es INDETERMINADA.
# Dos moléculas difieren sólo en la estereoquímica: en un disolvente aquiral
# los dos enantiómeros tienen la misma energía de hidratación y se aceptan.

def _corregir_nitro(mol):
    from rdkit import Chem
    rw = Chem.RWMol(mol)
    corregidos = 0
    for n in rw.GetAtoms():
        if n.GetAtomicNum() != 7 or n.GetFormalCharge() != 0 or n.GetDegree() != 3:
            continue
        oxigenos = [b for b in n.GetBonds() if b.GetOtherAtom(n).GetAtomicNum() == 8
                    and b.GetOtherAtom(n).GetFormalCharge() == -1 and b.GetBondType() == Chem.BondType.SINGLE
                    and b.GetOtherAtom(n).GetDegree() == 1]
        if len(oxigenos) != 2:
            continue
        oxigenos[0].SetBondType(Chem.BondType.DOUBLE)
        oxigenos[0].GetOtherAtom(n).SetFormalCharge(0)
        n.SetFormalCharge(1)
        corregidos += 1
    if corregidos:
        m = rw.GetMol()
        Chem.SanitizeMol(m)
        return m, corregidos
    return mol, 0


def curar(args) -> int:
    import rdkit
    from rdkit import Chem, RDLogger

    import lcpo_bri_h1 as h1
    RDLogger.DisableLog("rdApp.*")
    base = Path(args.freesolv) / "database.txt"
    filas = [linea.rstrip("\n").split("; ") for linea in base.read_text(encoding="utf-8").splitlines()
             if linea and not linea.startswith("#")]
    moleculas = []
    for f in filas:
        cid, smiles = f[0], f[1]
        sdf = Path(args.sdf) / f"{cid}.sdf"
        mol = Chem.MolFromMolFile(str(sdf), removeHs=False)
        ref = Chem.MolFromSmiles(smiles)
        nitros = 0
        if mol is not None:
            mol, nitros = _corregir_nitro(mol)
            if nitros:
                corregido = Path(args.sdf).parent / "sdf_corregidos" / f"{cid}.sdf"
                corregido.parent.mkdir(parents=True, exist_ok=True)
                Chem.MolToMolFile(mol, str(corregido), kekulize=True)
        fila: dict[str, Any] = {"id": cid, "smiles": smiles, "exp_kcal_mol": float(f[3]),
                                "incertidumbre_exp_kcal_mol": float(f[4]),
                                "freesolv_gaff_alquimico_kcal_mol": float(f[5])}
        if mol is None or ref is None:
            fila["estado"] = "ilegible"
            moleculas.append(fila)
            continue
        simbolos = {a.GetSymbol() for a in mol.GetAtoms()}
        entornos = []
        for a in mol.GetAtoms():
            if a.GetAtomicNum() in (35, 53):
                v = a.GetNeighbors()[0] if a.GetDegree() == 1 else None
                if v is not None and v.GetIsAromatic():
                    ent = "arilo"
                elif v is not None and v.GetAtomicNum() == 6 and v.GetHybridization() == Chem.HybridizationType.SP3:
                    ent = "alquilo"
                else:
                    ent = "otro_sp2_o_heterociclo"
                entornos.append({"elemento": a.GetSymbol(), "entorno": ent})
        violaciones = h1._geometria_rdkit(mol)
        ik_sdf, ik_ref = Chem.MolToInchiKey(Chem.RemoveHs(mol)), Chem.MolToInchiKey(ref)
        fila.update({
            "estado": "ok" if ik_sdf[:14] == ik_ref[:14] else "indeterminado_identidad",
            "sdf_sha256": _sha(sdf), "grupo": _grupo(simbolos), "nitros_corregidos": nitros,
            "mismo_inchikey_que_smiles": ik_sdf == ik_ref, "misma_conectividad_que_smiles": ik_sdf[:14] == ik_ref[:14],
            "n_pesados": mol.GetNumHeavyAtoms(), "carga_formal": Chem.GetFormalCharge(mol),
            "halogenos_pesados": entornos, "geometria_imposible": bool(violaciones), "violaciones": violaciones,
        })
        moleculas.append(fila)
    cuenta: dict[str, int] = defaultdict(int)
    for m in moleculas:
        cuenta[m.get("grupo", m["estado"])] += 1
    SALIDA.mkdir(exist_ok=True)
    seleccion = {"generado_utc": _ahora(), "rdkit": rdkit.__version__, "atribucion": ATRIBUCION,
                 "database_sha256": _sha(base), "n": len(moleculas), "por_grupo": dict(cuenta),
                 "moleculas": moleculas}
    (SALIDA / "seleccion.json").write_text(json.dumps(seleccion, ensure_ascii=False, indent=1) + "\n",
                                           encoding="utf-8", newline="\n")
    print(dict(cuenta), "nitros corregidos en", sum(1 for m in moleculas if m.get("nitros_corregidos")), "moléculas;",
          "geometría imposible:", [m["id"] for m in moleculas if m.get("geometria_imposible")],
          "; estereoquímica distinta (se aceptan):", [m["id"] for m in moleculas if m.get("estado") == "ok"
                                                      and not m["mismo_inchikey_que_smiles"]],
          "; identidad no recuperada:", [m["id"] for m in moleculas if m.get("estado") == "indeterminado_identidad"])
    return 0


# ── 2. Parametrización (AmberTools) ──────────────────────────────────────

def _orden(args: list[str], carpeta: Path, nombre: str) -> None:
    with open(carpeta / f"{nombre}.stdout", "w") as out, open(carpeta / f"{nombre}.stderr", "w") as err:
        r = subprocess.run(args, cwd=carpeta, stdout=out, stderr=err, timeout=900, check=False)
    if r.returncode:
        raise RuntimeError(f"{nombre} rc={r.returncode}: {(carpeta / f'{nombre}.stderr').read_text(errors='replace')[-300:]}")


def _parametrizar_uno(cid: str, sdf_dir: str, trabajo: str) -> dict[str, Any]:
    carpeta = Path(trabajo) / cid
    t0 = time.time()
    try:
        carpeta.mkdir(parents=True, exist_ok=False)
        corregido = Path(sdf_dir).parent / "sdf_corregidos" / f"{cid}.sdf"
        origen = corregido if corregido.is_file() else Path(sdf_dir) / f"{cid}.sdf"
        (carpeta / "input.sdf").write_bytes(origen.read_bytes())
        _orden(["antechamber", "-i", "input.sdf", "-fi", "sdf", "-o", "ligand.mol2", "-fo", "mol2",
                "-at", "gaff2", "-c", "bcc", "-nc", "0", "-rn", "MOL", "-s", "2"], carpeta, "antechamber")
        _orden(["parmchk2", "-i", "ligand.mol2", "-f", "mol2", "-o", "ligand.frcmod", "-s", "gaff2"],
               carpeta, "parmchk2")
        if "ATTN" in (carpeta / "ligand.frcmod").read_text(errors="replace"):
            raise RuntimeError("parmchk2 dejó parámetros sin resolver (ATTN)")
        (carpeta / "leap.in").write_text(
            "source leaprc.gaff2\nset default PBRadii mbondi3\nloadamberparams ligand.frcmod\n"
            "MOL = loadmol2 ligand.mol2\nsaveamberparm MOL ligand.prmtop ligand.inpcrd\nquit\n")
        _orden(["tleap", "-f", "leap.in"], carpeta, "tleap")
        return {"id": cid, "estado": "ok", "duracion_s": round(time.time() - t0, 1)}
    except Exception as exc:  # noqa: BLE001 - un fallo es un resultado: se registra, no se oculta
        return {"id": cid, "estado": "fallo", "motivo": f"{type(exc).__name__}: {exc}"[:400],
                "duracion_s": round(time.time() - t0, 1)}


def parametrizar(args) -> int:
    seleccion = json.loads((SALIDA / "seleccion.json").read_text(encoding="utf-8"))
    ids = [m["id"] for m in seleccion["moleculas"] if m["estado"] == "ok" and not m["geometria_imposible"]]
    if args.solo:
        ids = [i for i in ids if i in set(args.solo)]
    resultados = []
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        futuros = [ex.submit(_parametrizar_uno, i, str(args.sdf), str(args.trabajo)) for i in ids]
        for k, f in enumerate(as_completed(futuros), 1):
            r = f.result()
            resultados.append(r)
            print(f"  [{k}/{len(ids)}] {r['id']}: {r['estado']} {r.get('motivo', '')}", flush=True)
    resultados.sort(key=lambda r: r["id"])
    Path(args.salida).write_text(json.dumps({"generado_utc": _ahora(), "n": len(resultados),
                                             "ok": sum(r["estado"] == "ok" for r in resultados),
                                             "fallos": [r for r in resultados if r["estado"] != "ok"],
                                             "moleculas": resultados}, ensure_ascii=False, indent=1) + "\n",
                                 encoding="utf-8", newline="\n")
    print(f"parametrizadas {sum(r['estado'] == 'ok' for r in resultados)}/{len(resultados)}")
    return 0


# ── 3. Medida ────────────────────────────────────────────────────────────

def _prmtop_con_radios(prmtop: Path, destino: Path, radios: dict[int, float]) -> int:
    """Copia del prmtop con el RADII de los átomos de esos números atómicos cambiado."""
    lineas = prmtop.read_text().splitlines(keepends=True)

    def bloque(flag):
        i = next(k for k, linea in enumerate(lineas) if linea.startswith(f"%FLAG {flag}"))
        fin = next(k for k in range(i + 2, len(lineas)) if lineas[k].startswith("%FLAG"))
        return i, fin

    i, fin = bloque("ATOMIC_NUMBER")
    numeros = [int(linea[k:k + 8]) for linea in lineas[i + 2:fin] for k in range(0, len(linea.rstrip("\n")), 8)]
    i, fin = bloque("RADII")
    if not lineas[i + 1].startswith("%FORMAT(5E16.8)"):
        raise RuntimeError("RADII sin el formato 5E16.8 esperado")
    valores = [float(linea[k:k + 16]) for linea in lineas[i + 2:fin] for k in range(0, len(linea.rstrip("\n")), 16)]
    if len(valores) != len(numeros):
        raise RuntimeError("RADII y ATOMIC_NUMBER no tienen la misma longitud")
    cambiados = 0
    for k, z in enumerate(numeros):
        if z in radios:
            valores[k] = radios[z]
            cambiados += 1
    nuevo = ["".join(f"{v:16.8E}" for v in valores[k:k + 5]) + "\n" for k in range(0, len(valores), 5)]
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text("".join(lineas[:i + 2] + nuevo + lineas[fin:]))
    return cambiados


def _gb_openmm(prmtop: Path, inpcrd: Path) -> float:
    import openmm
    from openmm import app, unit

    from services.chemistry.amber_compatibility import apply_amber_gbn2_descreening, apply_amber_gbn2_phosphorus
    topologia = app.AmberPrmtopFile(str(prmtop))
    sistema = topologia.createSystem(nonbondedMethod=app.NoCutoff, constraints=None, implicitSolvent=app.GBn2,
                                     soluteDielectric=1.0, solventDielectric=78.5, sasaMethod=None,
                                     removeCMMotion=False)
    apply_amber_gbn2_phosphorus(sistema, topologia.topology)
    apply_amber_gbn2_descreening(sistema)
    for f in sistema.getForces():
        f.setForceGroup(1 if isinstance(f, openmm.CustomGBForce) else 0)
    contexto = openmm.Context(sistema, openmm.VerletIntegrator(0.001), openmm.Platform.getPlatformByName("Reference"))
    contexto.setPositions(app.AmberInpcrdFile(str(inpcrd)).positions)
    return float(contexto.getState(getEnergy=True, groups={1}).getPotentialEnergy()
                 .value_in_unit(unit.kilocalories_per_mole))


PB_IN = """PB de un solo punto, radios del prmtop (radiopt=0), sin término no polar
&cntrl
  imin=1, maxcyc=0, ntx=1, ipb=2, inp=0, ntb=0, cut=999.0,
/
&pb
  npbverb=0, istrng=0.0, epsin=1.0, epsout=78.5, radiopt=0, sprob=1.4, space=0.25, fillratio=4.0,
/
"""


def _pb(prmtop: Path, inpcrd: Path, carpeta: Path) -> float:
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / "pb.in").write_text(PB_IN)
    r = subprocess.run(["pbsa", "-O", "-i", "pb.in", "-o", "pb.out", "-p", str(prmtop.resolve()),
                        "-c", str(inpcrd.resolve())], cwd=carpeta, capture_output=True, text=True, timeout=900)
    salida = (carpeta / "pb.out").read_text(errors="replace") if (carpeta / "pb.out").is_file() else ""
    m = re.findall(r"EPB\s*=\s*(-?\d+\.\d+)", salida)
    if r.returncode or not m:
        raise RuntimeError(f"pbsa rc={r.returncode}: {(r.stderr or salida)[-300:]}")
    return float(m[-1])


def _sasa(prmtop: Path, inpcrd: Path) -> float:
    from openmm import app, unit
    from rdkit import Chem
    from rdkit.Chem import rdFreeSASA
    from rdkit.Geometry import Point3D
    topologia = app.AmberPrmtopFile(str(prmtop))
    xyz = app.AmberInpcrdFile(str(inpcrd)).positions.value_in_unit(unit.angstrom)
    rw = Chem.RWMol()
    numeros = [a.element.atomic_number for a in topologia.topology.atoms()]
    for z in numeros:
        rw.AddAtom(Chem.Atom(z))
    conf = Chem.Conformer(len(numeros))
    for k, p in enumerate(xyz):
        conf.SetAtomPosition(k, Point3D(float(p[0]), float(p[1]), float(p[2])))
    mol = rw.GetMol()
    mol.AddConformer(conf, assignId=True)
    radios = [0.0 if z == 1 else BONDI[z] for z in numeros]
    opciones = rdFreeSASA.SASAOpts(rdFreeSASA.SASAAlgorithm.LeeRichards, rdFreeSASA.SASAClassifier.Protor)
    return float(rdFreeSASA.CalcSASA(mol, radios, confIdx=-1, opts=opciones))


def _medir_uno(cid: str, trabajo: str, con_pb: bool) -> dict[str, Any]:
    carpeta = Path(trabajo) / cid
    t0 = time.time()
    try:
        prmtop, inpcrd = carpeta / "ligand.prmtop", carpeta / "ligand.inpcrd"
        b = carpeta / "brazo_B" / "ligand.prmtop"
        n_cambiados = _prmtop_con_radios(prmtop, b, RADIO_GB_BRAZO_B)
        fila: dict[str, Any] = {"id": cid, "estado": "ok", "prmtop_sha256": _sha(prmtop), "inpcrd_sha256": _sha(inpcrd),
                                "atomos_br_i": n_cambiados, "sasa_freesasa_A2": _sasa(prmtop, inpcrd),
                                "gb_A_kcal_mol": _gb_openmm(prmtop, inpcrd)}
        fila["gb_B_kcal_mol"] = _gb_openmm(b, inpcrd) if n_cambiados else fila["gb_A_kcal_mol"]
        if con_pb:
            fila["pb_A_kcal_mol"] = _pb(prmtop, inpcrd, carpeta / "pb_A")
            fila["pb_B_kcal_mol"] = _pb(b, inpcrd, carpeta / "pb_B") if n_cambiados else fila["pb_A_kcal_mol"]
        fila["duracion_s"] = round(time.time() - t0, 2)
        return fila
    except Exception as exc:  # noqa: BLE001 - un fallo es un resultado: se registra, no se oculta
        return {"id": cid, "estado": "fallo", "motivo": f"{type(exc).__name__}: {exc}"[:400]}


def medir(args) -> int:
    import openmm
    salida = Path(args.salida)
    if salida.exists():
        raise SystemExit(f"{salida} ya existe")
    trabajo = Path(args.trabajo)
    ids = sorted(p.name for p in trabajo.iterdir() if (p / "ligand.prmtop").is_file())
    if args.solo:
        ids = [i for i in ids if i in set(args.solo)]
    t0 = time.time()
    resultados = []
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        futuros = [ex.submit(_medir_uno, i, str(trabajo), not args.sin_pb) for i in ids]
        for k, f in enumerate(as_completed(futuros), 1):
            r = f.result()
            resultados.append(r)
            print(f"  [{k}/{len(ids)}] {r['id']}: {r['estado']} {r.get('motivo', '')}", flush=True)
    resultados.sort(key=lambda r: r["id"])
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(json.dumps({"experimento": "MMGBSA-H3-FREESOLV-RADIOS", "generado_utc": _ahora(),
                                  "openmm": openmm.__version__, "con_pb": not args.sin_pb,
                                  "duracion_s": round(time.time() - t0, 1), "moleculas": resultados},
                                 ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(f"escrito {salida} ({round(time.time() - t0, 1)} s)")
    return 0


# ── 4. Resumen y gate ────────────────────────────────────────────────────

def _mae(errores) -> float | None:
    return float(np.mean(np.abs(errores))) if len(errores) else None


def resumir(args) -> int:
    crudo_ruta = Path(args.crudo)
    crudo = json.loads(crudo_ruta.read_text(encoding="utf-8"))
    seleccion = json.loads((SALIDA / "seleccion.json").read_text(encoding="utf-8"))
    info = {m["id"]: m for m in seleccion["moleculas"]}
    ok = [dict(r, **{k: info[r["id"]][k] for k in ("grupo", "exp_kcal_mol", "incertidumbre_exp_kcal_mol",
                                                  "freesolv_gaff_alquimico_kcal_mol", "halogenos_pesados")})
          for r in crudo["moleculas"] if r["estado"] == "ok"]
    con_pb = crudo["con_pb"]

    # No polar calibrado sólo con moléculas sin halógeno (A = B para ellas).
    control = [r for r in ok if r["grupo"] == "sin_halogeno"]
    x = np.array([[r["sasa_freesasa_A2"], 1.0] for r in control])
    y = np.array([r["exp_kcal_mol"] - r["gb_A_kcal_mol"] for r in control])
    (gamma, b), *_ = np.linalg.lstsq(x, y, rcond=None)

    def calc(r, brazo):
        return r[f"gb_{brazo}_kcal_mol"] + gamma * r["sasa_freesasa_A2"] + b

    def errores(grupo_filas, brazo):
        return np.array([calc(r, brazo) - r["exp_kcal_mol"] for r in grupo_filas])

    grupos = {g: [r for r in ok if r["grupo"] == g]
              for g in ("Br", "I", "Br_mixto", "I_mixto", "Cl", "F", "sin_halogeno", "otro_halogeno")}
    bri = grupos["Br"] + grupos["I"] + grupos["Br_mixto"] + grupos["I_mixto"]
    tabla: dict[str, Any] = {}
    for g, filas in {**grupos, "Br_I_todas": bri}.items():
        if not filas:
            continue
        ea, eb = errores(filas, "A"), errores(filas, "B")
        fila = {"n": len(filas), "MAE_A": _mae(ea), "MAE_B": _mae(eb), "sesgo_A": float(ea.mean()), "sesgo_B": float(eb.mean()),
                "MAE_gaff_alquimico_freesolv": _mae(np.array([r["freesolv_gaff_alquimico_kcal_mol"] - r["exp_kcal_mol"]
                                                             for r in filas]))}
        if con_pb:
            fila["GB_menos_PB_A_mediana_abs"] = float(np.median([abs(r["gb_A_kcal_mol"] - r["pb_A_kcal_mol"]) for r in filas]))
            fila["GB_menos_PB_B_mediana_abs"] = float(np.median([abs(r["gb_B_kcal_mol"] - r["pb_B_kcal_mol"]) for r in filas]))
            fila["PB_B_menos_PB_A_media"] = float(np.mean([r["pb_B_kcal_mol"] - r["pb_A_kcal_mol"] for r in filas]))
            fila["GB_B_menos_GB_A_media"] = float(np.mean([r["gb_B_kcal_mol"] - r["gb_A_kcal_mol"] for r in filas]))
        tabla[g] = fila

    rng = np.random.default_rng(SEMILLA)
    ea, eb = np.abs(errores(bri, "A")), np.abs(errores(bri, "B"))
    difs = []
    for _ in range(REMUESTREOS):
        k = rng.integers(0, len(bri), len(bri))
        difs.append(float(eb[k].mean() - ea[k].mean()))
    ic = [float(np.percentile(difs, 2.5)), float(np.percentile(difs, 97.5))]
    mae_a, mae_b = float(ea.mean()), float(eb.mean())
    gate = {"MAE_A": mae_a, "MAE_B": mae_b, "reduccion_relativa": 1 - mae_b / mae_a,
            "ic95_MAE_B_menos_MAE_A": ic,
            "reduccion_suficiente": mae_b <= (1 - REDUCCION_MINIMA) * mae_a, "ic_entero_bajo_cero": ic[1] < 0}
    decision = "GO" if gate["reduccion_suficiente"] and gate["ic_entero_bajo_cero"] else "NO_GO"
    metricas = {
        "experimento": "MMGBSA-H3-FREESOLV-RADIOS", "generado_utc": _ahora(), "atribucion": ATRIBUCION,
        "crudo": {"archivo": crudo_ruta.name, "sha256": _sha(crudo_ruta), "openmm": crudo["openmm"]},
        "seleccion_sha256": _sha(SALIDA / "seleccion.json"),
        "modelo": {"polar": "GBn2 OpenMM 8.5.2 + fósforo + descreening de Amber (H13), eps 1/78.5",
                   "no_polar": "gamma*SASA + b; SASA FreeSASA Lee-Richards, radios de Bondi, sin H",
                   "no_polar_calibrado_en": f"{len(control)} moléculas sin halógeno",
                   "gamma_kcal_mol_A2": float(gamma), "b_kcal_mol": float(b),
                   "brazos_radio_gb": {"A": "mbondi3 (Br, I 1.5 A)", "B": "Bondi (Br 1.85, I 1.98 A)"}},
        "n": {"medidas": len(ok), "fallos": [r for r in crudo["moleculas"] if r["estado"] != "ok"]},
        "tabla": tabla, "gate": gate, "decision_por_el_gate": decision,
        "no_demuestra": ("Energías libres de hidratación con muestreo: es una estimación estática de un solo "
                         "confórmero. Tampoco dice nada del agujero sigma, que las cargas atómicas no representan."),
    }
    destino = Path(args.artefactos)
    destino.mkdir(parents=True, exist_ok=True)
    (destino / "metrics.json").write_text(json.dumps(metricas, ensure_ascii=False, indent=1) + "\n",
                                          encoding="utf-8", newline="\n")
    with open(destino / "per_complex.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for r in ok:
            fh.write(json.dumps({"id": r["id"], "grupo": r["grupo"], "exp_kcal_mol": r["exp_kcal_mol"],
                                 "calc_A_kcal_mol": round(calc(r, "A"), 4), "calc_B_kcal_mol": round(calc(r, "B"), 4),
                                 "gb_A_kcal_mol": round(r["gb_A_kcal_mol"], 4), "gb_B_kcal_mol": round(r["gb_B_kcal_mol"], 4),
                                 **({"pb_A_kcal_mol": round(r["pb_A_kcal_mol"], 4), "pb_B_kcal_mol": round(r["pb_B_kcal_mol"], 4)}
                                    if con_pb else {}),
                                 "sasa_A2": round(r["sasa_freesasa_A2"], 3), "halogenos_pesados": r["halogenos_pesados"]},
                                ensure_ascii=False) + "\n")
    print(f"no polar: gamma {gamma:.5f} kcal/mol/A2, b {b:.3f} kcal/mol ({len(control)} moléculas sin halógeno)")
    for g, f in tabla.items():
        pb = (f"  |GB-PB| A {f['GB_menos_PB_A_mediana_abs']:.2f} B {f['GB_menos_PB_B_mediana_abs']:.2f}" if con_pb else "")
        print(f"  {g:13s} n {f['n']:3d}  MAE A {f['MAE_A']:.2f}  B {f['MAE_B']:.2f}  sesgo A {f['sesgo_A']:+.2f} B {f['sesgo_B']:+.2f}"
              f"  (GAFF alquímico de FreeSolv {f['MAE_gaff_alquimico_freesolv']:.2f}){pb}")
    print(f"gate: {gate}\ndecisión por el gate: {decision}")
    return 0


def main() -> int:
    for flujo in (sys.stdout, sys.stderr):
        if hasattr(flujo, "reconfigure"):
            flujo.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="etapa", required=True)
    c = sub.add_parser("curar")
    c.add_argument("--freesolv", type=Path, required=True)
    c.add_argument("--sdf", type=Path, required=True)
    c.set_defaults(func=curar)
    p = sub.add_parser("parametrizar")
    p.add_argument("--sdf", type=Path, required=True)
    p.add_argument("--trabajo", type=Path, required=True)
    p.add_argument("--salida", type=Path, required=True)
    p.add_argument("--solo", nargs="*")
    p.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    p.set_defaults(func=parametrizar)
    m = sub.add_parser("medir")
    m.add_argument("--trabajo", type=Path, required=True)
    m.add_argument("--salida", type=Path, required=True)
    m.add_argument("--sin-pb", action="store_true")
    m.add_argument("--solo", nargs="*")
    m.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    m.set_defaults(func=medir)
    r = sub.add_parser("resumir")
    r.add_argument("--crudo", type=Path, required=True)
    r.add_argument("--artefactos", type=Path, required=True)
    r.set_defaults(func=resumir)
    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
