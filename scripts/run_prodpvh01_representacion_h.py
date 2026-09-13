#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PROD-PV-H-01: que procedimiento puede llamarse `internal_energy` dentro del producto.

NO ES UN EXPERIMENTO DE RENDIMIENTO DEL DOCKING. Es una VALIDACION DE CONFORMIDAD DE LA
MEDICION. No mide si el pipeline coloca bien las poses; mide si la cantidad que el dossier
llama validez fisica es la que dice ser. Las poses son fijas y los atomos pesados IDENTICOS
en los tres brazos: lo unico que cambia es la representacion de hidrogenos y el evaluador.

DE DONDE VIENE. `MF-33-H-COR` demostro que la reconstruccion de hidrogenos puede dominar la
validez fisica sin que se note: los hidrogenos no polares en coordenadas del cristal
disparaban `internal_energy` 8006 veces, y con reconstruccion canonica caen a 7. Produccion
NO tiene ese defecto -no hay cristal del que heredar nada- pero tampoco tiene la
reconstruccion canonica, y eso deja DOS preguntas abiertas que este artefacto separa.

LOS TRES BRAZOS, y por que asi:

  A) PROD_FULL_CURRENT   PDBQT -> representacion MIXTA actual -> PoseBusters oficial
  B) PROD_PROXY_CURRENT  PDBQT -> representacion MIXTA actual -> proxy RDKit propio
  C) TARGET_CANONICAL    PDBQT -> reconstruccion CANONICA     -> PoseBusters oficial

  A vs C aisla el efecto EXCLUSIVO de la representacion de hidrogenos, con el mismo
  evaluador oficial a los dos lados. B vs A aisla el efecto del PROXY frente al evaluador
  oficial, sobre la misma representacion. Un cuarto brazo -proxy sobre canonica- se calcula
  como SECUNDARIO descriptivo; no es primario porque no responde ninguna de las dos.

EL MECANISMO QUE HACE QUE A Y C DIFIERAN, leido en el codigo de PoseBusters 0.6.5 y no
supuesto. `add_hydrogens_with_uff_positions` llama a `optimize_positions(mol, indices_before)`,
donde `indices_before` son TODOS los atomos que ya venian: heavy atoms **y los hidrogenos
polares que trajo Vina**. Es decir, PoseBusters anade solo los hidrogenos que faltan, los
relaja, y deja los polares CONGELADOS en la geometria en que Vina los dejo. Ademas, si no
falta ninguno -`mol.GetNumAtoms() == len(fixed)`- devuelve la energia SIN minimizar nada.

  En el brazo A eso significa: polares de Vina congelados, no polares relajados.
  En el brazo C significa: `num_h_added` deberia ser 0 y PoseBusters no optimiza nada,
  porque la molecula ya llega con todos los hidrogenos regenerados y relajados con los
  pesados fijos. `num_h_added == 0` es el MARCADOR de que la canonicalizacion llego entera.

LA CANONICALIZACION NO SE REIMPLEMENTA. Se importa `reconstruir(..., corregida=True)` de
`scripts/run_mf33hcor_reconstruccion.py`, el runner sellado en `MF-33-H-COR` con
SHA-256 `072746e4530ec8fc2cbdaae0356b2b71fb52b65d23e0f758e192fbbcd09b5e95`, y el hash se
COMPRUEBA en tiempo de ejecucion. Se le pasa `coords_pose={}` a proposito: esa funcion
sustituye coordenadas por indice sobre la molecula que recibe, y aqui la molecula que
produce `pose_pdbqt_a_mol` YA trae las coordenadas dockeadas. Un diccionario vacio no es un
atajo: es la forma de decir «no hay nada que sustituir», y deja intacta la rama canonica.

LOS PARAMETROS OFICIALES son los de `posebusters/config/dock.yml`, no los defaults de la
funcion aislada: UFF, 50 conformeros, umbral `energy_ratio <= 100`, y
`energy_ratio = mol_pred_energy / ensemble_avg_energy`. El 7.0 / 100 conformeros que se cito
en algun momento son los defaults de `check_energy_ratio`, que `dock` NO usa. Se leen del
YAML instalado en vez de codificarse, para que una actualizacion del paquete no los
desincronice en silencio.

REGLAS DE DECISION -preregistradas, y ninguna se lee con `--limite`-:

  R1. Algun A:PASA -> C:FALLA  =>  la representacion mixta NO se promueve: da falsa
      tranquilidad. Es la regla que mas pesa, porque el error es en la direccion peligrosa.
  R2. Algun A:FALLA -> C:PASA  =>  la ruta actual produce falsas alarmas; tambien favorece
      canonicalizar.
  R3. B discrepa de A en cualquier pose  =>  el proxy NO puede etiquetarse `internal_energy`.
  R4. Aunque B coincidiera en TODAS, sigue siendo un proxy: una formula distinta no se
      convierte en la metrica oficial por concordancia empirica. R4 no depende de los datos y
      por eso se declara aqui: ningun resultado de este artefacto puede promover el proxy.
  R5. Sin PoseBusters solo hay dos salidas honestas: `NO_EVALUADA`, o proxy declarado sin
      identidad ni autoridad de PoseBusters.

Uso:
    python scripts/run_prodpvh01_representacion_h.py --tecnico          # prueba tecnica
    python scripts/run_prodpvh01_representacion_h.py --workspace .      # cohorte completa
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "backend"))

RE_OUT = re.compile(r"conf(\d+)\.out\.pdbqt$")
RE_SCORE = re.compile(r"REMARK VINA RESULT:\s*(-?\d+\.?\d*)")

# El runner sellado por MF-33-H-COR. El hash se verifica antes de usarlo: si alguien lo
# edita, este artefacto debe negarse a correr en vez de canonicalizar de otra manera.
SHA_RUNNER_HCOR = "072746e4530ec8fc2cbdaae0356b2b71fb52b65d23e0f758e192fbbcd09b5e95"
RUTA_RUNNER_HCOR = ROOT / "scripts" / "run_mf33hcor_reconstruccion.py"

BRAZOS = ("A_PROD_FULL_CURRENT", "B_PROD_PROXY_CURRENT", "C_TARGET_CANONICAL")
SECUNDARIO = "D_PROXY_SOBRE_CANONICA"


# ────────────────────── parametros oficiales de PoseBusters ──────────────────────

def parametros_dock_oficiales() -> Dict[str, Any]:
    """Lee `threshold_energy_ratio` y `ensemble_number_conformations` del `dock.yml` real.

    No se codifican a mano: los umbrales viven en el paquete, y una actualizacion que los
    cambie tiene que verse aqui en vez de quedar desincronizada en un literal.
    """
    import posebusters
    import yaml

    cfg = Path(posebusters.__file__).parent / "config" / "dock.yml"
    datos = yaml.safe_load(cfg.read_text(encoding="utf-8"))
    for modulo in datos.get("modules", []):
        if modulo.get("function") == "energy_ratio":
            p = modulo.get("parameters", {})
            return {
                "threshold_energy_ratio": float(p["threshold_energy_ratio"]),
                "ensemble_number_conformations": int(p["ensemble_number_conformations"]),
                "version_posebusters": getattr(posebusters, "__version__", "desconocida"),
                "origen": str(cfg),
                "campo_de_fuerza": "UFF",
                "formula": "energy_ratio = mol_pred_energy / ensemble_avg_energy",
            }
    raise RuntimeError("dock.yml no declara el modulo energy_ratio: el contrato cambio")


def _verificar_runner_sellado() -> None:
    real = hashlib.sha256(RUTA_RUNNER_HCOR.read_bytes()).hexdigest()
    if real != SHA_RUNNER_HCOR:
        raise RuntimeError(
            f"{RUTA_RUNNER_HCOR.name} NO coincide con el hash sellado en MF-33-H-COR.\n"
            f"  sellado: {SHA_RUNNER_HCOR}\n  en disco: {real}\n"
            "La canonicalizacion de este artefacto se define por ese archivo. Se aborta.")


# ────────────────────────────── entrada: poses ──────────────────────────────

def modelos_de_pdbqt(texto: str) -> List[Tuple[Optional[float], str]]:
    """Parte un `.out.pdbqt` de Vina en (score, texto_del_modelo) por MODEL.

    Produccion recibe UNA pose, no el archivo entero; alimentar `pose_pdbqt_a_mol` con los
    nueve modelos juntos mediria otra cosa.
    """
    modelos: List[Tuple[Optional[float], str]] = []
    actual: List[str] = []
    score: Optional[float] = None
    for linea in texto.splitlines():
        if linea.startswith("MODEL"):
            actual, score = [], None
            continue
        if linea.startswith("ENDMDL"):
            if actual:
                modelos.append((score, "\n".join(actual) + "\nEND\n"))
            actual = []
            continue
        m = RE_SCORE.match(linea)
        if m:
            score = float(m.group(1))
        if linea.startswith(("ATOM", "HETATM")):
            actual.append(linea)
    if actual:
        modelos.append((score, "\n".join(actual) + "\nEND\n"))
    return modelos


def top1_por_brazo(dir_complejo: Path) -> Dict[str, Dict[str, Any]]:
    """Top-1 de SINGLE (conf0) y de ENSEMBLE (todos), igual que MF-33-TOP1 y el ambito B.

    Se replica la regla del artefacto sellado para que la cohorte sea la MISMA y los dos
    resultados se puedan contrastar.
    """
    cand: List[Dict[str, Any]] = []
    archivos = sorted((p for p in dir_complejo.glob("conf*.out.pdbqt") if RE_OUT.search(p.name)),
                      key=lambda p: int(RE_OUT.search(p.name).group(1)))
    for p in archivos:
        conf = int(RE_OUT.search(p.name).group(1))
        for i, (sc, texto) in enumerate(modelos_de_pdbqt(
                p.read_text(encoding="utf-8", errors="replace"))):
            if sc is None:
                continue
            cand.append({"conformer": conf, "model_idx": i, "score": float(sc),
                         "pdbqt": texto, "archivo": p.name})
    if not cand:
        return {}
    mejor_ens = min(cand, key=lambda x: (x["score"], x["conformer"], x["model_idx"]))
    s0 = [x for x in cand if x["conformer"] == 0]
    salida = {"ENSEMBLE": mejor_ens}
    if s0:
        salida["SINGLE"] = min(s0, key=lambda x: (x["score"], x["model_idx"]))
    return salida


def plantilla_y_mapa(pid: str, ws: Path) -> Tuple[Any, Any, Optional[str]]:
    """(plantilla_quimica, index_map, motivo). El PDBQT NO define quimica; esto si.

    La plantilla es la molecula que el pipeline preparo -`mol_con_hidrogenos` del ligando de
    referencia-, que es a la que apuntan los indices de `index_map.json`. En produccion ese
    papel lo juega la molecula que MolDesign construye del SMILES del usuario, y el mapa se
    persiste junto a la corrida; aqui se usa la de referencia porque es la misma IDENTIDAD
    quimica. De ella se usa el GRAFO, nunca la geometria: el lector sustituye todas las
    coordenadas de los atomos mapeados y ELIMINA los no mapeados.
    """
    import molflex as mf
    import posebusters_metrica as pbm

    w = ws / "data" / "molflex_train_v2" / pid / pid
    f_mapa = w / "index_map.json"
    if not f_mapa.exists():
        return None, None, "SIN_INDEX_MAP"
    crystal = mf.leer_ligando(ws / "data" / "pdbbind" / pid / f"{pid}_ligand.sdf")
    if crystal is None:
        return None, None, "LIGANDO_DE_REFERENCIA_ILEGIBLE"
    try:
        mapa = json.loads(f_mapa.read_text(encoding="utf-8"))
    except Exception:                                          # noqa: BLE001
        return None, None, "INDEX_MAP_ILEGIBLE"
    return pbm.mol_con_hidrogenos(crystal), mapa, None


def smiles_de_referencia(pid: str, ws: Path) -> Optional[str]:
    """SMILES de la molecula, tomado del ligando de referencia.

    LIMITE DECLARADO: en produccion el SMILES lo aporta el usuario. Aqui se deriva del SDF
    de referencia porque es la misma IDENTIDAD QUIMICA que el usuario enviaria, y este
    artefacto mide representacion de hidrogenos, no perceptualizacion de la entrada. Lo que
    NO se usa en ningun brazo es la GEOMETRIA del cristal.
    """
    import molflex as mf
    from rdkit import Chem

    crystal = mf.leer_ligando(ws / "data" / "pdbbind" / pid / f"{pid}_ligand.sdf")
    if crystal is None:
        return None
    try:
        return Chem.MolToSmiles(Chem.RemoveAllHs(Chem.Mol(crystal)))
    except Exception:                                          # noqa: BLE001
        return None


# ────────────────────────────── los tres brazos ──────────────────────────────

def evaluar_oficial(mol, params: Dict[str, Any]) -> Dict[str, Any]:
    """`check_energy_ratio` de PoseBusters, con los parametros de `dock`. Sin envoltorios.

    El contrato de salida es el del paquete, no uno nuestro: `energy_ratio_passes` puede ser
    NaN, y NaN NO es aprobado. Ver `clasificar_resultado_pb` en el modulo de produccion.
    """
    from math import isfinite

    from posebusters.modules.energy_ratio import check_energy_ratio
    from services.chemistry.pose_physical_validity import clasificar_resultado_pb

    t0 = time.time()
    try:
        salida = check_energy_ratio(
            mol_pred=mol,
            threshold_energy_ratio=params["threshold_energy_ratio"],
            ensemble_number_conformations=params["ensemble_number_conformations"],
            inchi_strict=False,
            num_threads=0,
        )["results"]
    except Exception as exc:                                   # noqa: BLE001
        return {"estado": "NO_EVALUADO", "motivo": f"excepcion:{type(exc).__name__}",
                "duration_s": round(time.time() - t0, 3)}

    ratio = salida.get("energy_ratio")
    estado = clasificar_resultado_pb(salida.get("energy_ratio_passes"))
    motivo = None
    if estado == "NO_EVALUADO":
        motivo = ("energy_ratio no finito o modulo abortado; PoseBusters devuelve NaN en "
                  "_empty_results por: sin conformero, no sanitiza, UFF sin parametros, o "
                  "InChI irreconstruible")
    return {
        "estado": estado,
        "motivo": motivo,
        "energy_ratio": float(ratio) if ratio is not None and isfinite(float(ratio)) else None,
        "mol_pred_energy": _num(salida.get("mol_pred_energy")),
        "ensemble_avg_energy": _num(salida.get("ensemble_avg_energy")),
        "num_h_added": _num(salida.get("num_h_added")),
        "umbral": params["threshold_energy_ratio"],
        "n_conformeros": params["ensemble_number_conformations"],
        "motor": f"posebusters:{params['version_posebusters']}:energy_ratio",
        "duration_s": round(time.time() - t0, 3),
    }


def _num(v) -> Optional[float]:
    from math import isfinite
    try:
        f = float(v)
        return f if isfinite(f) else None
    except (TypeError, ValueError):
        return None


def evaluar_proxy(mol) -> Dict[str, Any]:
    """El escalon 2 de produccion, tal como esta hoy. NO es `internal_energy`."""
    from services.chemistry.pose_physical_validity import proxy_tension_rdkit

    t0 = time.time()
    r = proxy_tension_rdkit(mol)
    return {
        "estado": r["estado"],
        "motivo": r.get("motivo"),
        "razon": r.get("razon"),
        "umbral": r.get("umbral"),
        "energia_pose": r.get("energia_pose"),
        "energia_ensemble_media": r.get("energia_ensemble_media"),
        "motor": "rdkit:energy_strain_proxy_no_calibrado",
        "duration_s": round(time.time() - t0, 3),
    }


def canonicalizar(mol_mixta):
    """Reconstruccion canonica REUTILIZADA de `MF-33-H-COR`, no reimplementada.

    `coords_pose={}` porque `pose_a_mol` sustituye coordenadas por indice y la molecula que
    llega ya trae las dockeadas: no hay nada que sustituir. La rama canonica -quitar todos
    los H, regenerarlos desde la geometria de pesados, minimizarlos con los pesados fijos y
    verificar las invariantes- corre exactamente igual que en el artefacto sellado.
    """
    from run_mf33hcor_reconstruccion import reconstruir
    return reconstruir(mol_mixta, {}, corregida=True)


# ────────────────────────────── descriptores ──────────────────────────────

def descriptores(mol) -> Dict[str, Any]:
    """Con que covaria el cambio de veredicto. Se miden sobre la molecula MIXTA."""
    from rdkit import Chem
    from rdkit.Chem import Descriptors, Lipinski

    try:
        pesados = sum(1 for a in mol.GetAtoms() if a.GetAtomicNum() > 1)
        h_explicitos = sum(1 for a in mol.GetAtoms() if a.GetAtomicNum() == 1)
        h_polares = sum(1 for a in mol.GetAtoms()
                        if a.GetAtomicNum() == 1 and a.GetDegree() == 1
                        and a.GetNeighbors()[0].GetAtomicNum() in (7, 8, 16))
        con_h = Chem.AddHs(Chem.Mol(mol))
        return {
            "n_atomos_pesados": pesados,
            "n_h_explicitos_en_pdbqt": h_explicitos,
            "n_h_polares_explicitos": h_polares,
            "n_h_totales_si_se_completan": sum(1 for a in con_h.GetAtoms()
                                               if a.GetAtomicNum() == 1),
            "carga_formal": Chem.GetFormalCharge(mol),
            "n_donadores_NHOH": Lipinski.NHOHCount(mol),
            "peso_molecular": round(Descriptors.MolWt(mol), 2),
        }
    except Exception as exc:                                   # noqa: BLE001
        return {"error_descriptores": type(exc).__name__}


def invariantes_de_identidad(mixta, canonica) -> Dict[str, Any]:
    """Ademas de las cinco de MF-33-H-COR, la ESTEREOQUIMICA, que aquel no comprobaba."""
    from rdkit import Chem

    def _sin_h(m):
        return Chem.RemoveAllHs(Chem.Mol(m))

    def _estereo(m):
        mm = _sin_h(m)
        Chem.AssignStereochemistry(mm, cleanIt=True, force=True)
        return Chem.MolToSmiles(mm, isomericSmiles=True)

    try:
        return {
            "smiles_isomerico_identico": _estereo(mixta) == _estereo(canonica),
            "carga_formal_identica": Chem.GetFormalCharge(mixta) == Chem.GetFormalCharge(canonica),
            "n_enlaces_pesados_identico": _sin_h(mixta).GetNumBonds() == _sin_h(canonica).GetNumBonds(),
        }
    except Exception as exc:                                   # noqa: BLE001
        return {"error_invariantes": type(exc).__name__}


# ────────────────────────────── una pose ──────────────────────────────

def leer(trabajo: Dict[str, Any], plantilla, mapa) -> Any:
    """La lectura, aislada, para poder medir SU cobertura sin ejecutar energias."""
    from services.chemistry.pose_physical_validity import leer_pose_pdbqt
    return leer_pose_pdbqt(trabajo["pdbqt"], plantilla=plantilla, index_map=mapa)


def analizar_pose(pid: str, brazo_docking: str, trabajo: Dict[str, Any], plantilla, mapa,
                  params: Dict[str, Any], determinismo: bool,
                  solo_cobertura: bool = False) -> Dict[str, Any]:
    fila: Dict[str, Any] = {
        "pid": pid, "brazo_docking": brazo_docking,
        "identity": f"{pid}|conf{trabajo['conformer']}|model{trabajo['model_idx']}",
        "conformer": trabajo["conformer"], "model_idx": trabajo["model_idx"],
        "score": trabajo["score"],
        "politica_h": {"MIXTA": "polares explicitos de Vina, no polares implicitos",
                       "CANONICA": "todos regenerados y relajados con pesados fijos"},
    }

    # COBERTURA 1: el LECTOR. ¿Se pudo reconstruir grafo y coordenadas sin ambiguedad?
    lectura = leer(trabajo, plantilla, mapa)
    fila["cobertura_lector"] = {"ok": lectura.mol is not None, "ruta": lectura.ruta,
                                "motivo": lectura.motivo, **lectura.diagnostico}
    mixta = lectura.mol
    if mixta is None:
        fila["error"] = f"LECTOR:{lectura.motivo}"
        return fila
    fila["descriptores"] = descriptores(mixta)

    if solo_cobertura:
        # COBERTURA 2: la CANONICALIZACION, que no necesita energias para medirse.
        canonica, inv = canonicalizar(mixta)
        fila["cobertura_canonicalizacion"] = {
            "ok": canonica is not None,
            "motivo": None if canonica is not None else str(inv),
            "invariantes": (dict(inv, **invariantes_de_identidad(mixta, canonica))
                            if canonica is not None else None),
        }
        return fila

    fila[BRAZOS[0]] = evaluar_oficial(mixta, params)
    fila[BRAZOS[1]] = evaluar_proxy(mixta)

    canonica, inv = canonicalizar(mixta)
    fila["cobertura_canonicalizacion"] = {"ok": canonica is not None,
                                          "motivo": None if canonica is not None else str(inv)}
    if canonica is None:
        fila[BRAZOS[2]] = {"estado": "NO_EVALUADO", "motivo": f"CANONICALIZACION_FALLO:{inv}"}
        fila[SECUNDARIO] = {"estado": "NO_EVALUADO", "motivo": "sin molecula canonica"}
        return fila

    fila["invariantes"] = dict(inv, **invariantes_de_identidad(mixta, canonica))
    fila[BRAZOS[2]] = evaluar_oficial(canonica, params)
    fila[SECUNDARIO] = evaluar_proxy(canonica)

    if determinismo:
        repeticion = evaluar_oficial(canonica, params)
        fila["determinismo_C"] = {
            "energy_ratio_1": fila[BRAZOS[2]].get("energy_ratio"),
            "energy_ratio_2": repeticion.get("energy_ratio"),
            "identico": fila[BRAZOS[2]].get("energy_ratio") == repeticion.get("energy_ratio"),
        }
    return fila


# ────────────────────────────── agregacion ──────────────────────────────

def matriz(filas: List[dict], desde: str, hasta: str) -> Dict[str, Any]:
    """Matriz de cambios entre dos brazos, por pose. Las celdas fuera de la diagonal mandan."""
    m = Counter()
    ejemplos: Dict[str, List[str]] = {}
    for f in filas:
        a, b = f.get(desde, {}).get("estado"), f.get(hasta, {}).get("estado")
        if a is None or b is None:
            continue
        clave = f"{a}->{b}"
        m[clave] += 1
        if a != b:
            ejemplos.setdefault(clave, [])
            if len(ejemplos[clave]) < 10:
                ejemplos[clave].append(f["identity"])
    return {
        "de": desde, "a": hasta,
        "celdas": dict(sorted(m.items())),
        "n_pareadas": sum(m.values()),
        "discordantes": sum(v for k, v in m.items() if k.split("->")[0] != k.split("->")[1]),
        "ejemplos_discordantes": ejemplos,
    }


def asociacion(filas: List[dict], desde: str, hasta: str) -> Dict[str, Any]:
    """Descriptores medianos de las poses que cambian frente a las que no."""
    import statistics as st

    campos = ("n_h_polares_explicitos", "n_h_explicitos_en_pdbqt", "n_h_totales_si_se_completan",
              "carga_formal", "n_atomos_pesados", "n_donadores_NHOH", "peso_molecular")
    cambian, iguales = [], []
    for f in filas:
        a, b = f.get(desde, {}).get("estado"), f.get(hasta, {}).get("estado")
        d = f.get("descriptores") or {}
        if a is None or b is None or "error_descriptores" in d:
            continue
        (cambian if a != b else iguales).append(d)

    def _res(grupo):
        if not grupo:
            return None
        return {c: round(st.median([g[c] for g in grupo if c in g]), 3)
                for c in campos if any(c in g for g in grupo)}

    return {"n_cambian": len(cambian), "n_iguales": len(iguales),
            "mediana_de_las_que_cambian": _res(cambian),
            "mediana_de_las_que_no": _res(iguales),
            "NOTA": ("descriptivo y sin prueba de hipotesis: con estos n una diferencia de "
                     "medianas no sostiene una afirmacion causal")}


def leer_reglas(filas: List[dict]) -> Dict[str, Any]:
    """Las reglas preregistradas. NO se llama con `--limite`."""
    a_pasa_c_falla = [f["identity"] for f in filas
                      if f.get(BRAZOS[0], {}).get("estado") == "PASA"
                      and f.get(BRAZOS[2], {}).get("estado") == "FALLA"]
    a_falla_c_pasa = [f["identity"] for f in filas
                      if f.get(BRAZOS[0], {}).get("estado") == "FALLA"
                      and f.get(BRAZOS[2], {}).get("estado") == "PASA"]
    b_discrepa = [f["identity"] for f in filas
                  if f.get(BRAZOS[1], {}).get("estado") and f.get(BRAZOS[0], {}).get("estado")
                  and f[BRAZOS[1]]["estado"] != f[BRAZOS[0]]["estado"]]
    return {
        "R1_falsa_tranquilidad_A_pasa_C_falla": {
            "n": len(a_pasa_c_falla), "ejemplos": a_pasa_c_falla[:10],
            "veredicto": ("LA REPRESENTACION MIXTA NO SE PROMUEVE" if a_pasa_c_falla
                          else "sin casos"),
        },
        "R2_falsa_alarma_A_falla_C_pasa": {
            "n": len(a_falla_c_pasa), "ejemplos": a_falla_c_pasa[:10],
            "veredicto": ("LA RUTA ACTUAL PRODUCE FALSAS ALARMAS" if a_falla_c_pasa
                          else "sin casos"),
        },
        "R3_proxy_discrepa_de_oficial": {
            "n": len(b_discrepa), "ejemplos": b_discrepa[:10],
            "veredicto": ("EL PROXY NO PUEDE ETIQUETARSE internal_energy" if b_discrepa
                          else "concordancia total en esta cohorte"),
        },
        "R4_el_proxy_sigue_siendo_proxy": (
            "NO DEPENDE DE LOS DATOS. Una formula distinta -MMFF contra UFF, 16 conformeros "
            "contra 50, (pose-min)/(media-min) contra pose/media- no se convierte en la "
            "metrica oficial por concordancia empirica. Ningun resultado de este artefacto "
            "puede promover el proxy a `internal_energy`."),
        "R5_sin_posebusters": (
            "Dos salidas honestas y solo dos: NO_EVALUADA, o proxy declarado sin identidad "
            "ni autoridad de PoseBusters."),
    }


# ────────────────────────────── prueba tecnica ──────────────────────────────

def caso_sintetico_nan() -> Dict[str, Any]:
    """Fuerza el camino NaN de PoseBusters y comprueba que NO se cuenta como aprobado.

    Una molecula sin conformero entra por el primer `return _empty_results` de
    `energy_ratio.py`. Es el caso que en produccion convertia una bateria incompleta en
    CONTROLES SUPERADOS.
    """
    from rdkit import Chem

    from services.chemistry.pose_physical_validity import clasificar_resultado_pb

    mol = Chem.MolFromSmiles("CCO")            # sin conformero, a proposito
    params = parametros_dock_oficiales()
    r = evaluar_oficial(mol, params)
    return {
        "caso": "molecula sin conformero -> _empty_results -> energy_ratio_passes = NaN",
        "estado_obtenido": r["estado"],
        "energy_ratio": r.get("energy_ratio"),
        "contrato_ok": r["estado"] == "NO_EVALUADO",
        "clasificador_directo_sobre_nan": clasificar_resultado_pb(float("nan")),
    }


def cohorte_diagnostica(ws: Path, pids: List[str]) -> List[str]:
    """Casos de diagnostico, no una muestra para leer el resultado global.

    Los tres nombrados vienen del piloto de `MF-33-H-COR` -`10gs` con muchos H ausentes,
    `1amw`, y `1bcd` que no tenia hidrogenos huerfanos-. Los otros dos se BUSCAN en la
    cohorte en vez de adivinarse: el primer ligando con carga formal distinta de cero y el
    primero sin ningun hidrogeno polar explicito.
    """
    from rdkit import Chem

    from services.chemistry.pose_physical_validity import pose_pdbqt_a_mol

    elegidos = [p for p in ("10gs", "1amw", "1bcd") if p in pids]
    con_carga = sin_polares = None
    for pid in pids:
        if con_carga and sin_polares:
            break
        d = ws / "data" / "molflex_train_v2" / pid / pid
        if not d.exists():
            continue
        top = top1_por_brazo(d)
        smi = smiles_de_referencia(pid, ws)
        if not top or not smi:
            continue
        mol, _ = pose_pdbqt_a_mol(next(iter(top.values()))["pdbqt"], smi)
        if mol is None:
            continue
        if con_carga is None and Chem.GetFormalCharge(mol) != 0:
            con_carga = pid
        pol = sum(1 for a in mol.GetAtoms()
                  if a.GetAtomicNum() == 1 and a.GetDegree() == 1
                  and a.GetNeighbors()[0].GetAtomicNum() in (7, 8, 16))
        if sin_polares is None and pol == 0:
            sin_polares = pid
    for p in (con_carga, sin_polares):
        if p and p not in elegidos:
            elegidos.append(p)
    return elegidos


# ────────────────────────────── main ──────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description="PROD-PV-H-01: conformidad de la medicion de "
                                             "validez fisica en produccion")
    ap.add_argument("--workspace", default=str(ROOT))
    ap.add_argument("--salida", default=None, help="directorio del artefacto")
    ap.add_argument("--coverage-only", action="store_true", dest="coverage_only",
                    help="CALIFICACION DEL INSTRUMENTO sobre la cohorte entera: mide lector y "
                         "canonicalizacion y NO ejecuta ni lee los brazos energeticos")
    ap.add_argument("--tecnico", action="store_true",
                    help="prueba tecnica sobre casos diagnosticos; NO produce lectura de reglas")
    ap.add_argument("--limite", type=int, default=None,
                    help="corta la cohorte; como --tecnico, NO produce lectura de reglas")
    args = ap.parse_args()

    ws = Path(args.workspace)
    solo_cobertura = bool(args.coverage_only)
    tecnico = bool(args.tecnico or args.limite)
    out_dir = Path(args.salida) if args.salida else (
        ROOT / "scripts" / "artifacts_science" /
        ("PROD-PV-H-01-COBERTURA" if solo_cobertura else
         "PROD-PV-H-01-TECNICO" if tecnico else "PROD-PV-H-01"))
    out_dir.mkdir(parents=True, exist_ok=True)

    _verificar_runner_sellado()
    params = parametros_dock_oficiales()
    print(f"[PROD-PV-H-01] PoseBusters {params['version_posebusters']} config dock: "
          f"umbral={params['threshold_energy_ratio']} "
          f"conformeros={params['ensemble_number_conformations']}", flush=True)

    art = ROOT / "scripts" / "artifacts_science"
    pids = sorted({json.loads(l)["pid"] for l in
                   (art / "MF-13" / "per_complex.jsonl").read_text(encoding="utf-8").splitlines()
                   if l.strip()})

    if tecnico:
        pids = cohorte_diagnostica(ws, pids)
        if args.limite:
            pids = pids[:args.limite]
        print(f"[PROD-PV-H-01] MODO TECNICO. Casos diagnosticos: {pids}", flush=True)

    filas: List[dict] = []
    fallos: List[dict] = []
    t0 = time.time()
    for n, pid in enumerate(pids, 1):
        d = ws / "data" / "molflex_train_v2" / pid / pid
        if not d.exists():
            fallos.append({"pid": pid, "error": "DIRECTORIO_AUSENTE"})
            continue
        plantilla, mapa, motivo = plantilla_y_mapa(pid, ws)
        if plantilla is None:
            fallos.append({"pid": pid, "error": motivo})
            continue
        top = top1_por_brazo(d)
        if not top:
            fallos.append({"pid": pid, "error": "SIN_POSES"})
            continue
        for brazo_docking, trabajo in sorted(top.items()):
            fila = analizar_pose(pid, brazo_docking, trabajo, plantilla, mapa, params,
                                 determinismo=tecnico, solo_cobertura=solo_cobertura)
            filas.append(fila)
            if "error" in fila:
                fallos.append({"pid": pid, "brazo_docking": brazo_docking,
                               "error": fila["error"]})
        print(f"  [{n}/{len(pids)}] {pid} poses={len(top)} "
              f"A={[f[BRAZOS[0]]['estado'] for f in filas[-len(top):] if BRAZOS[0] in f]} "
              f"C={[f[BRAZOS[2]]['estado'] for f in filas[-len(top):] if BRAZOS[2] in f]}",
              flush=True)

    validas = [f for f in filas if "error" not in f]
    resumen = {b: dict(Counter(f.get(b, {}).get("estado") for f in validas)) for b in
               (*BRAZOS, SECUNDARIO)}
    inv_malas = [f["identity"] for f in validas
                 if not all(v for k, v in (f.get("invariantes") or {}).items()
                            if isinstance(v, bool))]
    h_added_no_cero = [f["identity"] for f in validas
                       if (f.get(BRAZOS[2], {}) or {}).get("num_h_added") not in (0, 0.0, None)]

    metrics: Dict[str, Any] = {
        "experiment_id": "PROD-PV-H-01" + ("-TECNICO" if tecnico else ""),
        "tipo": ("VALIDACION DE CONFORMIDAD DE LA MEDICION: que procedimiento puede llamarse "
                 "internal_energy dentro del producto. NO mide rendimiento de docking."),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "parametros_oficiales": params,
        "brazos": {
            BRAZOS[0]: "PDBQT -> representacion MIXTA actual -> PoseBusters oficial",
            BRAZOS[1]: "PDBQT -> representacion MIXTA actual -> proxy RDKit propio",
            BRAZOS[2]: "PDBQT -> reconstruccion CANONICA (MF-33-H-COR) -> PoseBusters oficial",
            SECUNDARIO: "SECUNDARIO descriptivo, no primario: proxy sobre la canonica",
        },
        "canonicalizacion": {
            "procedencia": f"scripts/run_mf33hcor_reconstruccion.py, sellado en MF-33-H-COR",
            "sha256_verificado_en_ejecucion": SHA_RUNNER_HCOR,
            "nota_coords_vacias": ("se invoca con coords_pose={} porque la molecula ya trae "
                                   "las coordenadas dockeadas: no hay nada que sustituir"),
        },
        "n_complejos": len(pids), "n_poses": len(filas), "n_poses_validas": len(validas),
        "resumen_por_brazo": resumen,
        "invariantes": {
            "poses_con_invariante_violada": len(inv_malas), "ejemplos": inv_malas[:10],
            "C_con_num_h_added_distinto_de_cero": {
                "n": len(h_added_no_cero), "ejemplos": h_added_no_cero[:10],
                "por_que_importa": ("si la canonicalizacion llego entera, PoseBusters no "
                                    "deberia anadir ningun hidrogeno; num_h_added > 0 "
                                    "significa que el brazo C no es canonico de verdad")},
        },
        "matrices": {
            "A_vs_C_efecto_de_la_representacion": matriz(validas, BRAZOS[0], BRAZOS[2]),
            "B_vs_A_efecto_del_proxy": matriz(validas, BRAZOS[1], BRAZOS[0]),
            "B_vs_D_proxy_mixta_contra_canonica": matriz(validas, BRAZOS[1], SECUNDARIO),
        },
        "asociacion_con_descriptores": {
            "A_vs_C": asociacion(validas, BRAZOS[0], BRAZOS[2]),
            "B_vs_A": asociacion(validas, BRAZOS[1], BRAZOS[0]),
        },
        "tiempos_s": {b: round(sum((f.get(b, {}) or {}).get("duration_s") or 0
                                   for f in validas), 1) for b in (*BRAZOS, SECUNDARIO)},
        "duracion_total_s": round(time.time() - t0, 1),
        "limites_declarados": [
            "el SMILES se deriva del ligando de referencia; en produccion lo aporta el usuario. La GEOMETRIA del cristal no se usa en ningun brazo",
            "cohorte del protocolo RIGIDO, top-1 de los dos brazos de docking: la misma del ambito B de MF-33-H-COR, para que los dos artefactos se puedan contrastar",
            "mide el control energetico, no la bateria completa: distancias al receptor, valencias y planaridad no entran aqui",
            "no mide exactitud de pose ni de union, y no dice nada sobre el protocolo de docking",
        ],
    }

    # LAS TRES COBERTURAS, siempre y por separado. Un NO_EVALUADA no dice lo mismo si viene
    # del formato, de la identidad quimica o de la parametrizacion, y agregarlas las confunde.
    cob_lector = Counter()
    cob_canon = Counter()
    for f in filas:
        c = f.get("cobertura_lector") or {}
        cob_lector["ok" if c.get("ok") else (c.get("motivo") or "desconocido")] += 1
        k = f.get("cobertura_canonicalizacion")
        if k is not None:
            cob_canon["ok" if k.get("ok") else (k.get("motivo") or "desconocido")] += 1
    cob_eval = Counter()
    for f in validas:
        e = (f.get(BRAZOS[2]) or {}).get("estado")
        if e is not None:
            cob_eval["finito" if e in ("PASA", "FALLA") else "NO_EVALUADO"] += 1

    n_poses = len(filas)
    metrics["coberturas"] = {
        "1_lector": {"detalle": dict(cob_lector), "ok": cob_lector["ok"], "de": n_poses,
                     "tasa": round(cob_lector["ok"] / n_poses, 4) if n_poses else None,
                     "que_mide": "se reconstruyo grafo y coordenadas sin ambiguedad"},
        "2_canonicalizacion": {"detalle": dict(cob_canon), "ok": cob_canon["ok"],
                               "de": sum(cob_canon.values()),
                               "que_mide": "se regeneraron los H preservando las invariantes"},
        "3_evaluador": {"detalle": dict(cob_eval), "de": sum(cob_eval.values()),
                        "que_mide": "PoseBusters produjo un energy_ratio finito"},
        "por_que_separadas": ("un NO EVALUADA puede venir de formato, identidad/mapeo, "
                              "quimica, parametrizacion, generacion de conformeros o del "
                              "propio PoseBusters. Agregarlas esconde cual de los seis fallo."),
    }
    metrics["calificacion_del_instrumento"] = {
        "observado_antes_del_sello": (
            "CALIFICACION DEL INSTRUMENTO, observada ANTES del sello y NO es resultado de "
            "este experimento. El lector ORIGINAL cubrio 40/232 (17.2%) y el truncado a "
            "columnas PDB 156/232 (67.2%); el fallo estaba CORRELACIONADO CON LA "
            "AROMATICIDAD -el tipo AutoDock `A` en las columnas 77-78-, que es la peor forma "
            "de perder datos. El lector reparado -plantilla quimica + index_map + "
            "coordenadas por columnas fijas- se califico sobre la cohorte ENTERA en modo "
            "coverage-only, sin ejecutar ni leer los brazos energeticos: 232/232 en lector y "
            "232/232 en canonicalizacion, 0 invariantes violadas, desplazamiento pesado 0.0 "
            "A, y 12 pseudo-atomos de pegado de macrociclo descartados por tipo en los tres "
            "macrociclos de la cohorte."),
        "observaciones_tecnicas_NO_INTERPRETABLES": (
            "De la prueba tecnica, y NO entran en ninguna conclusion porque los casos se "
            "eligieron por diagnostico y no por muestreo: con el lector viejo el proxy dio "
            "NO_EVALUADO en 2 de 6 poses donde el oficial dio PASA; con el lector reparado "
            "dio FALLA en 2 de 10 donde el oficial dio PASA. Se registran para que no "
            "parezcan un descubrimiento cuando la corrida completa los reproduzca."),
        "regla": ("el experimento empieza solo cuando el instrumento puede medir la cohorte "
                  "sin sesgo estructural obvio. Una exclusion correlacionada con "
                  "aromaticidad o carga NO se acepta."),
    }

    if solo_cobertura:
        metrics["MODO"] = "COVERAGE_ONLY"
        metrics["NO_HAY_BRAZOS_ENERGETICOS"] = (
            "CALIFICACION DEL INSTRUMENTO. No se ejecutaron ni se leyeron los brazos "
            "energeticos: este modo solo mide si el lector y la canonicalizacion cubren la "
            "cohorte. No produce lectura de reglas ni resultado citable.")
    elif tecnico:
        metrics["NO_LEER_GATES_TECNICOS"] = (
            "PRUEBA TECNICA. Casos elegidos por diagnostico y no por muestreo: NO produce "
            "lectura de las reglas de decision y NO puede citarse como resultado. Solo "
            "comprueba que los tres brazos corren, que las invariantes se cumplen, que la "
            "salida respeta el contrato y que el NaN no se cuenta como aprobado.")
        metrics["caso_sintetico_nan"] = caso_sintetico_nan()
        metrics["determinismo"] = {
            "poses_comprobadas": sum(1 for f in validas if "determinismo_C" in f),
            "todas_identicas": all(f["determinismo_C"]["identico"]
                                   for f in validas if "determinismo_C" in f),
        }
    else:
        metrics["lectura_preregistrada"] = leer_reglas(validas)

    (out_dir / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=1),
                                          encoding="utf-8", newline="\n")
    (out_dir / "per_complex.jsonl").write_text(
        "".join(json.dumps(f, ensure_ascii=False, sort_keys=True) + "\n" for f in filas),
        encoding="utf-8", newline="\n")
    (out_dir / "failures.jsonl").write_text(
        "".join(json.dumps(f, ensure_ascii=False) + "\n" for f in fallos),
        encoding="utf-8", newline="\n")

    cb = metrics["coberturas"]
    print(f"\n[PROD-PV-H-01] {len(filas)} poses")
    print(f"  cobertura 1 LECTOR           : {cb['1_lector']['ok']}/{cb['1_lector']['de']} "
          f"{cb['1_lector']['detalle']}")
    print(f"  cobertura 2 CANONICALIZACION : {cb['2_canonicalizacion']['ok']}/"
          f"{cb['2_canonicalizacion']['de']} {cb['2_canonicalizacion']['detalle']}")
    if solo_cobertura:
        print("  MODO COVERAGE_ONLY: los brazos energeticos NO se ejecutaron ni se leyeron")
        print(f"  -> {out_dir}")
        return 0
    print(f"  cobertura 3 EVALUADOR        : {cb['3_evaluador']['detalle']}")
    print("  resumen por brazo:")
    for b in (*BRAZOS, SECUNDARIO):
        print(f"  {b:24s} {resumen[b]}")
    print(f"  invariantes violadas: {len(inv_malas)} | C con num_h_added != 0: "
          f"{len(h_added_no_cero)}")
    for nombre, m in metrics["matrices"].items():
        print(f"  {nombre}: discordantes={m['discordantes']}/{m['n_pareadas']} {m['celdas']}")
    if tecnico:
        print(f"  NaN sintetico: {metrics['caso_sintetico_nan']['estado_obtenido']} "
              f"(contrato_ok={metrics['caso_sintetico_nan']['contrato_ok']})")
        print(f"  determinismo: {metrics['determinismo']}")
        print("  NO_LEER_GATES_TECNICOS")
    print(f"  -> {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
