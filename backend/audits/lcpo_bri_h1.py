#!/usr/bin/env python3
r"""lcpo_bri_h1.py — MM-GBSA, H1: el LCPO del cloro publicado con radios de Bondi basta para Br e I.

**Tipo: medición sin ajuste.** Hipótesis H1 de `docs/validacion_mmgbsa.md`.
Se prueba si los coeficientes P1-P4 del Cl publicado (Weiser, Shenkin y Still,
1999), con el radio de van der Waals de Bondi (Br 1,85 Å; I 1,98 Å) y sin
reajustar nada, aproximan la SASA numéricamente exacta de los átomos de Br e I
dentro del error de fondo de LCPO. Mismo método que la adjudicación del cloro y
que `lcpo_halogenos.py`, cuyas funciones se importan sin modificarlas.

# Etapas

    python backend/audits/lcpo_bri_h1.py curar                        # RDKit 2025.09.6, esta máquina
    python backend/audits/lcpo_bri_h1.py particionar                  # asignación sellada por scaffold
    python backend/audits/lcpo_bri_h1.py parametrizar --trabajo <dir> # AmberTools (servidor)
    python backend/audits/lcpo_bri_h1.py medir --trabajo <dir> --salida <crudo.json>
    python backend/audits/lcpo_bri_h1.py resumir --crudo <crudo.json> --artefactos <dir>

# Universo y curación (declarados antes de medir)

Todos los ligandos de PDBBind legibles por RDKit (FEP-01-PDBBIND) con al menos
un Br o un I: 122. Todos tienen sólo H, C, N, O, S, P, F, Cl, Br, I e
hidrógenos explícitos; no se filtra por tamaño ni por carga (el área no depende
de las cargas: se usan Gasteiger, como en `lcpo_halogenos.py`). Una geometría
imposible (dos átomos a < 0,5 Å o un ángulo de valencia < 30°, la regla de
MMGBSA-H5-R1) es INDETERMINADA y no entra en la estadística.

# Particiones (declaradas antes de medir; se sellan aparte y se reutilizan en H2, H3 y H10)

Grupos por **scaffold de Bemis-Murcko** (RDKit, canónico, sin hidrógenos); un
ligando acíclico forma su propio grupo por InChIKey. Un grupo entero va a una
sola partición, así que ningún scaffold cruza de entrenamiento a prueba. Los
grupos se recorren en el orden de SHA-256(«semilla:grupo») y cada uno va a la
partición que más lejos está de su objetivo (60/20/20), medido por separado
para los ligandos con Br y los ligandos con I, para que el yodo, escaso, llegue
a las tres. El entorno del halógeno (arilo / alifático) se registra por átomo y
se informa estratificado.

# Brazos

Para cada átomo de Br o I, con todos los demás átomos con sus parámetros de
Amber/OpenMM:

- `H1_Cl_publicado_radio_Bondi`: P1-P4 del Cl publicado; radio 1,85 (Br) o 1,98 (I). **La hipótesis.**
- `respaldo_Amber_C_sp2_2`: lo que hace Amber hoy (radio 1,7). Control negativo.
- `diagnostico_Cl_publicado_r1_8`: la lectura de `lcpo_halogenos.py` (radio 1,8), por continuidad.

Cada brazo se compara con la SASA exacta calculada con SU propio radio. Además
se mide, por brazo, el error de los átomos pesados que no son Br ni I, y en
particular de los que solapan con la esfera de un Br o un I: son los que un
radio mal elegido puede estropear.

# Gate de H1 (el del prerregistro)

Para Br y para I por separado, en validación y en prueba, con el brazo H1:

1. mediana |error| ≤ 2,81 Å² y p90 ≤ 7,25 Å² (el fondo de `lcpo_halogenos.py`;
   es el criterio de H1 en `docs/validacion_mmgbsa.md`);
2. el IC bootstrap al 95 % (1000 remuestreos de grupos de scaffold) del error
   medio con signo, dentro de ±2,81 Å²: el sesgo es menor que el error típico;
3. **no empeora a los vecinos** (el criterio 4 de «validado» del documento):
   en los átomos pesados que solapan con la esfera de un Br o un I, la cota
   superior del IC bootstrap al 95 % de la media pareada
   |error con H1| − |error con el respaldo de Amber| es ≤ +0,5 Å² (0,0025
   kcal/mol por átomo a 0,005 kcal/mol/Å²).

Menos de 5 átomos de un elemento en una partición → INDETERMINADO.

El criterio 3 se escribió primero como umbral absoluto (vecinos con mediana
≤ 2,81 y p90 ≤ 7,25). Un piloto de 5 ligandos, antes del prerregistro, mostró
que el p90 de los vecinos supera 7,25 en los TRES brazos, incluido el de Amber:
es un límite de LCPO cerca de una esfera grande, no del radio elegido. Se
volvió a la formulación del documento, «no empeorar», como comparación
pareada. Los criterios 1 y 2 no se tocaron.

Lo que NO hace: no ajusta nada (eso es H2), no toca el término polar (H3) y no
activa MM-GBSA.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from itertools import combinations
from pathlib import Path
from typing import Any

import numpy as np

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[1]
sys.path.insert(0, str(AQUI))
import lcpo_halogenos as lh  # noqa: E402 - sin modificar
from lcpo_vs_sasa_exacta import (  # noqa: E402 - sin modificar
    TENSION_SUPERFICIAL,
    _desempaquetar,
    _TiposEnMayuscula,
    _valor,
    areas_lcpo,
    sasa_numerica,
)

SALIDA = AQUI / "bri_h1"
PDBBIND = RAIZ / "data" / "pdbbind"
F01 = RAIZ / "scripts" / "artifacts_science" / "FEP-01-PDBBIND" / "per_complex.jsonl"
BRI = {35: "Br", 53: "I"}
RADIO_BONDI = {"Br": 1.85, "I": 1.98}        # Bondi (1964)
SEMILLA = 20260923
OBJETIVO = {"entrenamiento": 0.6, "validacion": 0.2, "prueba": 0.2}
DISTANCIA_MINIMA_A, ANGULO_MINIMO_GRADOS = 0.5, 30.0   # la regla de MMGBSA-H5-R1
FONDO_MEDIANA, FONDO_P90 = 2.81, 7.25       # lcpo_halogenos.py, 784 átomos, 2026-09-23
MIN_ATOMOS = 5
TOLERANCIA_VECINOS = 0.5                 # Å²: 0,0025 kcal/mol por átomo
REMUESTREOS = 1000


def _ahora() -> str:
    from datetime import UTC, datetime
    return datetime.now(UTC).isoformat()


def _sha(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


# ── 1. Curación ──────────────────────────────────────────────────────────

def _geometria_rdkit(mol) -> list[dict[str, Any]]:
    xyz = mol.GetConformer().GetPositions()
    violaciones = []
    for i, j in combinations(range(mol.GetNumAtoms()), 2):
        d = float(np.linalg.norm(xyz[i] - xyz[j]))
        if d < DISTANCIA_MINIMA_A:
            violaciones.append({"tipo": "distancia", "indices": [i, j], "valor": round(d, 4)})
    for b in mol.GetAtoms():
        for a, c in combinations([n.GetIdx() for n in b.GetNeighbors()], 2):
            u, v = xyz[a] - xyz[b.GetIdx()], xyz[c] - xyz[b.GetIdx()]
            t = float(np.degrees(np.arccos(np.clip(np.dot(u, v) / np.linalg.norm(u) / np.linalg.norm(v), -1, 1))))
            if t < ANGULO_MINIMO_GRADOS:
                violaciones.append({"tipo": "angulo", "indices": [a, b.GetIdx(), c], "valor": round(t, 3)})
    return violaciones


def curar(_args) -> int:
    import rdkit
    from rdkit import Chem, RDLogger
    from rdkit.Chem.Scaffolds import MurckoScaffold
    RDLogger.DisableLog("rdApp.*")
    with open(F01, encoding="utf-8") as fh:
        legibles = [r["pid"] for r in map(json.loads, fh) if "error" not in r]
    ligandos, descartes = [], defaultdict(int)
    for pid in sorted(legibles):
        sdf = PDBBIND / pid / f"{pid}_ligand.sdf"
        mol = Chem.MolFromMolFile(str(sdf), removeHs=False)
        if mol is None:
            descartes["ilegible"] += 1
            continue
        numeros = {a.GetAtomicNum() for a in mol.GetAtoms()}
        if not numeros & set(BRI):
            continue
        if not numeros <= lh.PERMITIDOS:
            descartes["elemento_no_permitido"] += 1
            continue
        if mol.GetNumAtoms() == mol.GetNumHeavyAtoms():
            descartes["sin_hidrogenos"] += 1
            continue
        sin_h = Chem.RemoveHs(mol)
        scaffold = MurckoScaffold.MurckoScaffoldSmiles(mol=sin_h)
        inchikey = Chem.MolToInchiKey(sin_h)
        atomos = []
        for a in mol.GetAtoms():
            if a.GetAtomicNum() in BRI:
                vecino = a.GetNeighbors()[0] if a.GetDegree() == 1 else None
                atomos.append({"indice": a.GetIdx(), "elemento": BRI[a.GetAtomicNum()],
                               "entorno": "arilo" if vecino is not None and vecino.GetIsAromatic() else "alifatico"})
        violaciones = _geometria_rdkit(mol)
        ligandos.append({
            "pid": pid, "sdf_sha256": _sha(sdf), "inchikey": inchikey, "n_pesados": mol.GetNumHeavyAtoms(),
            "carga_formal": Chem.GetFormalCharge(mol), "scaffold": scaffold,
            "grupo": scaffold if scaffold else f"aciclico:{inchikey}",
            "elementos": sorted({x["elemento"] for x in atomos}), "atomos_bri": atomos,
            "geometria_imposible": bool(violaciones), "violaciones": violaciones,
        })
    SALIDA.mkdir(exist_ok=True)
    seleccion = {
        "generado_utc": _ahora(), "rdkit": rdkit.__version__,
        "universo": "ligandos de PDBBind legibles por RDKit (FEP-01-PDBBIND) con Br o I",
        "descartes": dict(descartes), "n": len(ligandos),
        "n_geometria_imposible": sum(x["geometria_imposible"] for x in ligandos),
        "n_inchikey_distintos": len({x["inchikey"] for x in ligandos}),
        "n_grupos": len({x["grupo"] for x in ligandos}),
        "ligandos": ligandos,
    }
    (SALIDA / "seleccion.json").write_text(json.dumps(seleccion, ensure_ascii=False, indent=1) + "\n",
                                           encoding="utf-8", newline="\n")
    print(f"{len(ligandos)} ligandos con Br o I; descartes {dict(descartes)}; "
          f"{seleccion['n_grupos']} grupos de scaffold; {seleccion['n_inchikey_distintos']} InChIKey distintos; "
          f"geometría imposible: {[x['pid'] for x in ligandos if x['geometria_imposible']]}")
    return 0


# ── 2. Particiones ───────────────────────────────────────────────────────

def particionar(_args) -> int:
    seleccion = json.loads((SALIDA / "seleccion.json").read_text(encoding="utf-8"))
    grupos: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for x in seleccion["ligandos"]:
        grupos[x["grupo"]].append(x)
    totales = {e: sum(e in x["elementos"] for x in seleccion["ligandos"]) for e in ("Br", "I")}
    cuenta = {s: {"Br": 0, "I": 0} for s in OBJETIVO}
    asignacion: dict[str, str] = {}
    orden = sorted(grupos, key=lambda g: hashlib.sha256(f"{SEMILLA}:{g}".encode()).hexdigest())
    for g in orden:
        presentes = {e: sum(e in x["elementos"] for x in grupos[g]) for e in ("Br", "I")}

        def deficit(s, presentes=presentes):
            return sum((OBJETIVO[s] * totales[e] - cuenta[s][e]) / totales[e] for e in presentes if presentes[e])

        destino = max(OBJETIVO, key=lambda s: (deficit(s), OBJETIVO[s]))
        asignacion[g] = destino
        for e in presentes:
            cuenta[destino][e] += presentes[e]
    por_pid = {x["pid"]: asignacion[x["grupo"]] for x in seleccion["ligandos"]}
    resumen = {s: {"ligandos": sum(v == s for v in por_pid.values()),
                   "grupos": sum(v == s for v in asignacion.values()),
                   "ligandos_con_Br": cuenta[s]["Br"], "ligandos_con_I": cuenta[s]["I"],
                   "atomos": {e: sum(1 for x in seleccion["ligandos"] if por_pid[x["pid"]] == s
                                     for a in x["atomos_bri"] if a["elemento"] == e) for e in ("Br", "I")}}
               for s in OBJETIVO}
    particiones = {
        "nombre": "PDBBind-BrI-v1", "generado_utc": _ahora(), "semilla": SEMILLA, "objetivo": OBJETIVO,
        "seleccion_sha256": _sha(SALIDA / "seleccion.json"),
        "regla": ("grupos por scaffold de Bemis-Murcko (acíclicos: por InChIKey); orden SHA-256(semilla:grupo); "
                  "cada grupo a la partición con mayor déficit relativo, por separado para ligandos con Br y con I"),
        "resumen": resumen, "por_grupo": dict(sorted(asignacion.items())), "por_pid": dict(sorted(por_pid.items())),
    }
    (SALIDA / "particiones.json").write_text(json.dumps(particiones, ensure_ascii=False, indent=1) + "\n",
                                             encoding="utf-8", newline="\n")
    for s, r in resumen.items():
        print(f"  {s:13s} {r['ligandos']:3d} ligandos en {r['grupos']:3d} grupos; con Br {r['ligandos_con_Br']:3d}, "
              f"con I {r['ligandos_con_I']:2d}; átomos {r['atomos']}")
    return 0


# ── 3. Parametrización: la de lcpo_halogenos.py, sin tocarla ─────────────

def parametrizar(args) -> int:
    seleccion = json.loads((SALIDA / "seleccion.json").read_text(encoding="utf-8"))
    pids = [x["pid"] for x in seleccion["ligandos"] if not x["geometria_imposible"]]
    resultados = []
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        futuros = [ex.submit(lh._parametrizar_uno, p, str(args.trabajo)) for p in pids]
        for i, f in enumerate(as_completed(futuros), 1):
            r = f.result()
            resultados.append(r)
            print(f"  [{i}/{len(pids)}] {r['pid']}: {r['estado']} {r.get('motivo', '')}", flush=True)
    resultados.sort(key=lambda r: r["pid"])
    destino = Path(args.salida)
    if destino.exists():
        raise SystemExit(f"{destino} ya existe")
    destino.write_text(json.dumps({"generado_utc": _ahora(), "n": len(resultados),
                                   "ok": sum(r["estado"] in ("ok", "ya_estaba") for r in resultados),
                                   "fallos": [r for r in resultados if r["estado"] == "fallo"],
                                   "ligandos": resultados}, ensure_ascii=False, indent=1) + "\n",
                       encoding="utf-8", newline="\n")
    print(f"parametrizados {sum(r['estado'] in ('ok', 'ya_estaba') for r in resultados)}/{len(resultados)}")
    return 0


# ── 4. Medida ────────────────────────────────────────────────────────────

def _medir_uno(pid: str, trabajo: str, puntos: int) -> dict[str, Any]:
    from openmm import app, unit
    from openmm.app import element as elemento
    from openmm.app.internal import lcpo
    carpeta = Path(trabajo) / pid
    t0 = time.time()
    try:
        topologia = app.AmberPrmtopFile(str(carpeta / "ligand.prmtop"))
        coords = np.array(app.AmberInpcrdFile(str(carpeta / "ligand.inpcrd"))
                          .positions.value_in_unit(unit.angstrom), dtype=np.float64)
        elementos = list(topologia.elements)
        numeros = [0 if e is None else e.atomic_number for e in elementos]
        marcador = [elemento.chlorine if z in BRI else e for z, e in zip(numeros, elementos, strict=True)]
        base = lcpo.getLCPOParamsAmber(_TiposEnMayuscula(topologia._prmtop), marcador)
        tabla = lcpo.LCPO_PARAMETERS

        # Guardián: la implementación propia reproduce a OpenMM con los parámetros base.
        radios, p1, p2, p3, p4 = _desempaquetar(base)
        propias = areas_lcpo(coords, radios, p1, p2, p3, p4)
        area_openmm = lh._energia_lcpo(topologia, coords, base) / TENSION_SUPERFICIAL
        if abs(propias.sum() - area_openmm) > 1e-6 * max(1.0, abs(area_openmm)):
            return {"pid": pid, "estado": "fallo", "motivo": f"LCPO propio {propias.sum():.6f} != OpenMM {area_openmm:.6f}"}

        bri = {i: BRI[z] for i, z in enumerate(numeros) if z in BRI}
        cl = tabla["Cl"]
        brazos = {
            "H1_Cl_publicado_radio_Bondi": {s: (RADIO_BONDI[s], *cl[1:]) for s in ("Br", "I")},
            "respaldo_Amber_C_sp2_2": {s: tabla["C_sp2_2"] for s in ("Br", "I")},
            "diagnostico_Cl_publicado_r1_8": {s: cl for s in ("Br", "I")},
        }
        salida: dict[str, Any] = {"pid": pid, "estado": "ok", "n_atomos": len(numeros), "brazos": {}}
        for nombre, filas in brazos.items():
            parametros = [filas[bri[i]] if i in bri else fila for i, fila in enumerate(base)]
            r_, a1, a2, a3, a4 = _desempaquetar(parametros)
            lc = areas_lcpo(coords, r_, a1, a2, a3, a4)
            ex = sasa_numerica(coords, r_, puntos, 0.0)
            ex_b = sasa_numerica(coords, r_, puntos, 0.37)
            distancias = np.linalg.norm(coords[:, None] - coords[None], axis=2)
            solapan = {j for i in bri for j in range(len(r_))
                       if j not in bri and r_[j] > 0 and distancias[i, j] < r_[i] + r_[j]}
            salida["brazos"][nombre] = {
                "halogenos": [{"indice": i, "elemento": bri[i], "tipo_amber": topologia._prmtop.getAtomType(i),
                               "radio_sin_sonda_A": _valor(parametros[i][0]),
                               "sasa_exacta_A2": round(float(ex[i]), 4), "sasa_lcpo_A2": round(float(lc[i]), 4),
                               "error_A2": round(float(lc[i] - ex[i]), 4),
                               "incertidumbre_malla_A2": round(abs(float(ex[i] - ex_b[i])), 4)} for i in sorted(bri)],
                "fondo": [{"indice": j, "z": numeros[j], "solapa_con_BrI": j in solapan,
                           "error_A2": round(float(lc[j] - ex[j]), 4)}
                          for j in range(len(r_)) if r_[j] > 0 and j not in bri],
            }
        salida["duracion_s"] = round(time.time() - t0, 2)
        return salida
    except Exception as exc:  # noqa: BLE001 - un fallo es un resultado: se registra, no se oculta
        return {"pid": pid, "estado": "fallo", "motivo": f"{type(exc).__name__}: {exc}"[:400]}


def medir(args) -> int:
    import openmm
    salida = Path(args.salida)
    if salida.exists():
        raise SystemExit(f"{salida} ya existe: cada corrida escribe en un archivo nuevo")
    trabajo = Path(args.trabajo)
    pids = sorted(p.name for p in trabajo.iterdir() if (p / "ligand.prmtop").is_file())
    t0 = time.time()
    resultados = []
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        futuros = [ex.submit(_medir_uno, p, str(trabajo), args.puntos) for p in pids]
        for i, f in enumerate(as_completed(futuros), 1):
            r = f.result()
            resultados.append(r)
            print(f"  [{i}/{len(pids)}] {r['pid']}: {r['estado']} {r.get('motivo', '')} {r.get('duracion_s', '')}",
                  flush=True)
    resultados.sort(key=lambda r: r["pid"])
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(json.dumps({"experimento": "MMGBSA-H1-LCPO-BONDI", "generado_utc": _ahora(),
                                  "openmm": openmm.__version__, "puntos_shrake_rupley": args.puntos,
                                  "duracion_s": round(time.time() - t0, 1), "ligandos": resultados},
                                 ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(f"escrito {salida} ({len(resultados)} ligandos, {round(time.time() - t0, 1)} s)")
    return 0


# ── 5. Resumen y gate ────────────────────────────────────────────────────

def _estadistica(errores: list[float], grupos: list[str], rng: np.random.Generator) -> dict[str, Any] | None:
    if not errores:
        return None
    e = np.array(errores)
    salida = {"n": int(e.size), "mediana_abs_A2": round(float(np.median(np.abs(e))), 4),
              "p90_abs_A2": round(float(np.percentile(np.abs(e), 90)), 4),
              "max_abs_A2": round(float(np.abs(e).max()), 4), "media_con_signo_A2": round(float(e.mean()), 4)}
    por_grupo: dict[str, list[float]] = defaultdict(list)
    for v, g in zip(errores, grupos, strict=True):
        por_grupo[g].append(v)
    claves = sorted(por_grupo)
    medias = []
    for _ in range(REMUESTREOS):
        elegidos = rng.choice(len(claves), size=len(claves), replace=True)
        valores = [v for k in elegidos for v in por_grupo[claves[k]]]
        medias.append(float(np.mean(valores)))
    salida["ic95_media_con_signo_A2"] = [round(float(np.percentile(medias, 2.5)), 4),
                                         round(float(np.percentile(medias, 97.5)), 4)]
    salida["n_grupos"] = len(claves)
    return salida


def resumir(args) -> int:
    crudo_ruta = Path(args.crudo)
    crudo = json.loads(crudo_ruta.read_text(encoding="utf-8"))
    seleccion = json.loads((SALIDA / "seleccion.json").read_text(encoding="utf-8"))
    particiones = json.loads((SALIDA / "particiones.json").read_text(encoding="utf-8"))
    info = {x["pid"]: x for x in seleccion["ligandos"]}
    particion = particiones["por_pid"]
    ok = [r for r in crudo["ligandos"] if r["estado"] == "ok"]
    rng = np.random.default_rng(SEMILLA)

    def filas(brazo, particion_s, elemento=None, entorno=None):
        out = []
        for r in ok:
            if particion_s and particion[r["pid"]] != particion_s:
                continue
            entornos = {a["indice"]: a["entorno"] for a in info[r["pid"]]["atomos_bri"]}
            for h in r["brazos"][brazo]["halogenos"]:
                if elemento and h["elemento"] != elemento:
                    continue
                if entorno and entornos.get(h["indice"]) != entorno:
                    continue
                out.append((h["error_A2"], info[r["pid"]]["grupo"]))
        return out

    def fondo(brazo, particion_s, solo_solapan):
        out = []
        for r in ok:
            if particion_s and particion[r["pid"]] != particion_s:
                continue
            for f in r["brazos"][brazo]["fondo"]:
                if solo_solapan and not f["solapa_con_BrI"]:
                    continue
                out.append((f["error_A2"], info[r["pid"]]["grupo"]))
        return out

    def est(pares):
        return _estadistica([p[0] for p in pares], [p[1] for p in pares], rng)

    brazos = sorted(ok[0]["brazos"]) if ok else []
    tabla: dict[str, Any] = {}
    for brazo in brazos:
        tabla[brazo] = {}
        for s in (*OBJETIVO, "todas"):
            clave = None if s == "todas" else s
            tabla[brazo][s] = {
                "Br": est(filas(brazo, clave, "Br")), "I": est(filas(brazo, clave, "I")),
                "Br_arilo": est(filas(brazo, clave, "Br", "arilo")),
                "Br_alifatico": est(filas(brazo, clave, "Br", "alifatico")),
                "I_arilo": est(filas(brazo, clave, "I", "arilo")),
                "I_alifatico": est(filas(brazo, clave, "I", "alifatico")),
                "fondo_solapan_BrI": est(fondo(brazo, clave, True)),
                "fondo_todos": est(fondo(brazo, clave, False)),
            }

    def vecinos_pareados(particion_s):
        """|error H1| − |error respaldo| por átomo vecino, con el grupo de su ligando."""
        pares = []
        for r in ok:
            if particion[r["pid"]] != particion_s:
                continue
            h1 = {f["indice"]: f for f in r["brazos"]["H1_Cl_publicado_radio_Bondi"]["fondo"]}
            for f in r["brazos"]["respaldo_Amber_C_sp2_2"]["fondo"]:
                g = h1[f["indice"]]
                if f["solapa_con_BrI"] or g["solapa_con_BrI"]:
                    pares.append((abs(g["error_A2"]) - abs(f["error_A2"]), info[r["pid"]]["grupo"]))
        return est(pares)

    def veredicto(s, elemento):
        d = tabla["H1_Cl_publicado_radio_Bondi"][s][elemento]
        if d is None or d["n"] < MIN_ATOMOS:
            return "INDETERMINADO", {"motivo": f"menos de {MIN_ATOMOS} átomos"}
        v = vecinos[s]
        comprobaciones = {
            "mediana": d["mediana_abs_A2"] <= FONDO_MEDIANA, "p90": d["p90_abs_A2"] <= FONDO_P90,
            "sesgo": -FONDO_MEDIANA <= d["ic95_media_con_signo_A2"][0] and d["ic95_media_con_signo_A2"][1] <= FONDO_MEDIANA,
            "no_empeora_vecinos": v is not None and v["ic95_media_con_signo_A2"][1] <= TOLERANCIA_VECINOS,
        }
        return ("PASA" if all(comprobaciones.values()) else "FALLA"), comprobaciones

    vecinos = {s: vecinos_pareados(s) for s in OBJETIVO}

    gate = {s: {e: dict(zip(("resultado", "comprobaciones"), veredicto(s, e), strict=True)) for e in ("Br", "I")}
            for s in ("validacion", "prueba")}
    resultados = [gate[s][e]["resultado"] for s in gate for e in gate[s]]
    decision = ("GO" if all(r == "PASA" for r in resultados)
                else "NO_GO" if any(r == "FALLA" for r in resultados) else "INCONCLUSIVE")
    metricas = {
        "experimento": "MMGBSA-H1-LCPO-BONDI", "generado_utc": _ahora(),
        "crudo": {"archivo": crudo_ruta.name, "sha256": _sha(crudo_ruta), "openmm": crudo["openmm"],
                  "puntos_shrake_rupley": crudo["puntos_shrake_rupley"]},
        "seleccion_sha256": _sha(SALIDA / "seleccion.json"), "particiones_sha256": _sha(SALIDA / "particiones.json"),
        "radios_bondi_A": RADIO_BONDI,
        "umbrales": {"fondo_mediana_A2": FONDO_MEDIANA, "fondo_p90_A2": FONDO_P90, "min_atomos": MIN_ATOMOS,
                     "tolerancia_vecinos_A2": TOLERANCIA_VECINOS,
                     "remuestreos": REMUESTREOS, "semilla": SEMILLA},
        "n_ligandos": {"seleccion": seleccion["n"], "geometria_imposible": seleccion["n_geometria_imposible"],
                       "medidos": len(ok), "fallos": [r for r in crudo["ligandos"] if r["estado"] != "ok"]},
        "vecinos_pareados_H1_menos_respaldo": vecinos,
        "tabla": tabla, "gate": gate, "decision_por_el_gate": decision,
        "no_demuestra": ("Que el área LCPO sea el término no polar correcto, ni que estos radios valgan para el "
                         "término polar (H3): la SASA numérica es una referencia geométrica, no experimental."),
    }
    destino = Path(args.artefactos)
    destino.mkdir(parents=True, exist_ok=True)
    (destino / "metrics.json").write_text(json.dumps(metricas, ensure_ascii=False, indent=1) + "\n",
                                          encoding="utf-8", newline="\n")
    with open(destino / "per_complex.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for r in crudo["ligandos"]:
            fila = {"pid": r["pid"], "estado": r["estado"], "particion": particion.get(r["pid"]),
                    "grupo": info[r["pid"]]["grupo"]}
            if r["estado"] == "ok":
                fila["halogenos"] = {b: r["brazos"][b]["halogenos"] for b in r["brazos"]}
            else:
                fila["motivo"] = r.get("motivo")
            fh.write(json.dumps(fila, ensure_ascii=False) + "\n")

    for brazo in brazos:
        print(f"\n== {brazo}")
        for s in (*OBJETIVO, "todas"):
            for clave in ("Br", "I", "fondo_solapan_BrI"):
                d = tabla[brazo][s][clave]
                if d:
                    print(f"   {s:13s} {clave:18s} n {d['n']:4d}  mediana {d['mediana_abs_A2']:7.3f}  p90 "
                          f"{d['p90_abs_A2']:7.3f}  media {d['media_con_signo_A2']:+7.3f}  IC95 {d['ic95_media_con_signo_A2']}")
    for s, v in vecinos.items():
        if v:
            print(f"   vecinos pareados {s:13s} n {v['n']:4d}  media |H1|-|respaldo| {v['media_con_signo_A2']:+7.3f}"
                  f"  IC95 {v['ic95_media_con_signo_A2']}")
    print(f"\ngate: {json.dumps(gate, ensure_ascii=False)}\ndecisión por el gate: {decision}")
    return 0


def main() -> int:
    for flujo in (sys.stdout, sys.stderr):
        if hasattr(flujo, "reconfigure"):
            flujo.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="etapa", required=True)
    sub.add_parser("curar").set_defaults(func=curar)
    sub.add_parser("particionar").set_defaults(func=particionar)
    p = sub.add_parser("parametrizar")
    p.add_argument("--trabajo", type=Path, required=True)
    p.add_argument("--salida", type=Path, required=True)
    p.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    p.set_defaults(func=parametrizar)
    m = sub.add_parser("medir")
    m.add_argument("--trabajo", type=Path, required=True)
    m.add_argument("--salida", type=Path, required=True)
    m.add_argument("--puntos", type=int, default=50_000)
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
