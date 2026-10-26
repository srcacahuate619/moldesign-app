#!/usr/bin/env python3
r"""Verificación y calibración de un receptor del catálogo con el producto tal como corre.

# Qué mide

Para un receptor (hoy 8HFI) y un panel experimental de un solo ensayo:

1. **Verificación de pose**: el ligando del cristal, introducido como SMILES
   (conformación independiente del cristal), se evalúa con 5 semillas. Una
   semilla cuenta si el top-1 de Vina queda a RMSD ≤ 2 Å del cristal (simétrico,
   SIN alinear). La pose es válida si el top-1 de cada semilla que cuenta pasa la
   evidencia estructural que calcula el propio producto (PoseBusters `dock`,
   `status == "passed"`, el PASA del dossier). Gate: ≥ 3 de 5 y todas válidas.
2. **Calibración**: ρ de Spearman entre Q = −E (afinidad del top-1 de Vina) y la
   mediana de pKi por padre, con IC 95 % percentil por bootstrap de compuestos
   (10 000 remuestreos, semilla 42). Gate: límite inferior > 0 y ningún fallo
   (un compuesto que falla dos veces —un reintento técnico— hace fallar el gate:
   descartarlo cambiaría n en silencio).

# Cómo lo mide

Por la API, como la aplicación: un backend con datos propios y desechables,
`/evaluation/preflight` y `/evaluation/submit` con la configuración por defecto
de un caso (`CaseEvaluationRunner.configuracionPorDefecto`: exhaustividad 8,
9 poses, un conformador, sin ADMET-AI) y la semilla del protocolo. El arnés del
backend es el de `scripts/accept_evaluation_runtime.py`, el de la puerta
`check:evaluation-runtime`. Nada se reimplementa: microestado, conformador,
preparación del receptor, Vina y validez física son los del producto.

# Uso (con el Python embebido)

    python calibracion_receptor.py piloto   --salida DIR   # forma del resultado; ajeno al experimento
    python calibracion_receptor.py congelar --datos DIR    # panel, microestados y protocolo
    python calibracion_receptor.py ejecutar --datos DIR    # redocking y panel (reanudable)
    python calibracion_receptor.py analizar                # métricas, gates y fallos

`congelar` se ejecuta y se commitea ANTES de `ejecutar`: es el preregistro.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parents[1]
EXPERIMENTO = "CAL-8HFI-01"
DIR_EXP = RAIZ / "scripts" / "artifacts_science" / EXPERIMENTO
ENTRADA = DIR_EXP / "entrada"
TRABAJO = DIR_EXP / "_work"
CORRIDAS = TRABAJO / "corridas.jsonl"

# ── Protocolo preregistrado (aprobado por el propietario el 2026-10-09) ──────
PDB_ID = "8HFI"
CADENA = "A"
LIGANDO_CRISTAL = ("DSM", "A", 701)  # desipramina en S1
SMILES_CRISTAL = "CNCCCN1c2ccccc2CCc2ccccc21"  # desipramina; se comprueba contra el cristal
CLORURO = ("CL", "A", 702)           # único ion depositado; la receta 7 lo retira
SEMILLAS_REDOCKING = (42, 43, 44, 45, 46)
SEMILLA_PANEL = 42
RMSD_MAX_A = 2.0
SEMILLAS_OK_MINIMAS = 3
BOOTSTRAP_N = 10_000
BOOTSTRAP_SEMILLA = 42
INTENTOS = 2  # uno + un reintento técnico idéntico
CONFIG_CASO = {
    "enabled_stages": ["validation", "properties", "sa_filter", "conformer", "docking", "xgb", "clgnn"],
    "stage_params": {
        "properties": {"run_admet_ai": False},
        "conformer": {"conformers": 1},
        "docking": {"exhaustiveness": 8, "num_poses": 9},
    },
    "docking_engine": "vina",
    "pro_selectivity": False,
    "pro_mmgbsa": False,
}
CONDICIONES = ["RECEPTOR_SIN_IONES", "SERIE_CONGENERICA", "CONDICIONES_DEL_ENSAYO_NO_DOCUMENTADAS"]

#: Correcciones del análisis tras congelar, con su motivo. El primer `analizar`
#: se detuvo al casar átomos, antes de calcular ningún RMSD ni ρ; ninguna de las
#: dos depende del resultado ni cambia un umbral, una entrada o una corrida.
DESVIACIONES_DEL_ANALISIS = [
    "Neutralización: se quitan los H antes del Uncharger. Con los H explícitos del SDF del "
    "producto la amina protonada seguía cargada y no casaba con el cristal neutro (el control "
    "previo usaba una molécula sin H explícitos y no lo vio).",
    "Contraste SDF/PDBQT del top-1: se excluyen los pseudoátomos G0/G1… con que Meeko abre el "
    "anillo de siete de la desipramina y se acepta ≤ 0,05 Å por átomo; antes se exigía igualdad "
    "exacta de conjuntos y los pseudoátomos la rompían (el top-1 coincidía a 0,012 Å).",
]
FUENTE_PANEL = Path(r"D:\moldesign-audits\verificacion-8hfi-20261008")


def _sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _sha(path: Path) -> str:
    return _sha_bytes(path.read_bytes())


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _escribir_json(path: Path, datos: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(datos, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def _git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(RAIZ), *args], capture_output=True, text=True).stdout.strip()


# ── Arnés: el de la puerta check:evaluation-runtime ──────────────────────────

def _arnes():
    os.environ.setdefault("MOLDESIGN_GATE_PYTHON", str(Path(sys.executable)))
    sys.path.insert(0, str(RAIZ / "scripts"))
    import accept_evaluation_runtime as gate  # noqa: E402
    return gate


class Backend:
    """Un backend con datos desechables, vivo mientras dura el bloque `with`."""

    def __init__(self, datos: Path):
        self.gate = _arnes()
        self.datos = datos

    def __enter__(self):
        g = self.gate
        self.datos.mkdir(parents=True, exist_ok=True)
        vina_tmp = self.datos / "vina-tmp"
        vina_tmp.mkdir(exist_ok=True)
        env = g.entorno_runtime(self.datos, vina_tmp)
        self.port = g._free_port()
        self.base = f"http://127.0.0.1:{self.port}"
        self.proc, self.log = g._start_backend(env, self.port, self.datos / "backend.log")
        g._wait_ready(self.base, self.proc, timeout=180)
        self.token = g._auth(self.base, f"cal{int(time.time())}")
        return self

    def __exit__(self, *exc):
        self.gate._stop_backend(self.proc, self.log)

    def evaluar(self, smiles: str, pdb_id: str, chain: str, seed: int, nombre: str) -> dict[str, Any]:
        """Preflight + submit + espera + resultado + SDF de poses. Lanza si no hay SUCCESS."""
        g = self.gate
        config = json.loads(json.dumps(CONFIG_CASO))
        config["stage_params"]["docking"]["seed"] = seed
        preflight = g._json(self.base, "POST", "/evaluation/preflight", token=self.token, body={
            "smiles": smiles, "target_pdb_id": pdb_id, "chain": chain, "docking_engine": "vina",
            "exhaustiveness": 8, "num_poses": 9, "conformers": 1, "pipeline_config": config,
        }, timeout=600)
        bloqueantes = preflight.get("technical_blockers") or []
        if bloqueantes:
            raise RuntimeError(f"preflight bloqueado: {bloqueantes}")
        efectiva = preflight["effective_config"]
        enviado = g._json(self.base, "POST", "/evaluation/submit", token=self.token, expected={202}, body={
            "smiles": smiles, "target_pdb_id": pdb_id, "chain": chain, "molecule_name": nombre,
            "grid_center": efectiva["grid_center"], "grid_size": efectiva["grid_size"],
            "pipeline_config": config, "preflight_fingerprint": preflight["input_fingerprint"],
        })
        task_id = enviado["task_id"]
        t0 = time.monotonic()
        estado: dict[str, Any] = {}
        while time.monotonic() - t0 < 3600:
            estado = g._json(self.base, "GET", f"/evaluation/status/{task_id}", token=self.token)
            if estado.get("status") in {"SUCCESS", "FAILURE", "REVOKED"}:
                break
            time.sleep(2.0)
        if estado.get("status") != "SUCCESS":
            raise RuntimeError(f"la corrida no terminó en SUCCESS: {str(estado)[:600]}")
        resultado = estado.get("result") or {}
        molecule_id = resultado.get("molecule_id")
        _, poses, _ = g._request(self.base, "GET", f"/evaluation/files/poses/{molecule_id}", token=self.token)
        return {
            "task_id": task_id,
            "segundos": round(time.monotonic() - t0, 1),
            "preflight": {"effective_config": efectiva, "warnings": preflight.get("warnings"),
                          "not_evaluated": preflight.get("not_evaluated")},
            "resultado": resultado,
            "poses_sdf": poses.decode("utf-8", errors="replace"),
        }


# ── Piloto: sólo la forma del resultado, con un caso ajeno al experimento ────

def cmd_piloto(args: argparse.Namespace) -> int:
    salida = Path(args.salida)
    with Backend(salida / "datos") as be:
        r = be.evaluar("CC(=O)OC1=CC=CC=C1C(=O)O", "3F75", "A", 42, "piloto-aspirina")
    _escribir_json(salida / "piloto_resultado.json", r)
    print("piloto en", salida, "·", r["segundos"], "s")
    return 0


# ── Congelar: panel, microestados y protocolo ────────────────────────────────

def _panel_desde_fuentes() -> list[dict[str, Any]]:
    """Los 57 padres con su mediana de pKi, contrastados con la descarga de ChEMBL."""
    from rdkit import Chem

    filas = list(csv.DictReader((FUENTE_PANEL / "panel_8hfi.csv").open(encoding="utf-8-sig")))
    chembl = json.loads((FUENTE_PANEL / "fuentes" / "chembl_activities_CHEMBL853189.json").read_text(encoding="utf-8"))
    por_actividad = {str(a["activity_id"]): a for a in chembl["activities"]}
    if len(filas) != 58 or len(por_actividad) != 58:
        raise SystemExit(f"panel inesperado: {len(filas)} filas, {len(por_actividad)} actividades")

    def canon(smi: str) -> str:
        return Chem.MolToSmiles(Chem.MolFromSmiles(smi))

    padres: dict[str, dict[str, Any]] = {}
    for f in filas:
        a = por_actividad[f["activity_id"]]
        if (a["assay_chembl_id"], a["standard_type"], a["standard_relation"], a["standard_units"]) != \
                ("CHEMBL853189", "Ki", "=", "nM"):
            raise SystemExit(f"actividad {f['activity_id']} fuera del ensayo o con relación distinta")
        if a["parent_molecule_chembl_id"] != f["parent_molecule_chembl_id"]:
            raise SystemExit(f"padre distinto en {f['activity_id']}")
        if abs(float(a["standard_value"]) - float(f["standard_value_nM"])) > 1e-9:
            raise SystemExit(f"Ki distinto en {f['activity_id']}")
        # El padre tiene que ser exactamente un componente de la forma ensayada.
        componentes = {canon(c) for c in a["canonical_smiles"].split(".")}
        if canon(f["parent_smiles"]) not in componentes:
            raise SystemExit(f"el padre de {f['activity_id']} no es un componente de lo ensayado")
        p = padres.setdefault(f["parent_molecule_chembl_id"], {
            "padre": f["parent_molecule_chembl_id"], "smiles": canon(f["parent_smiles"]), "pki": [],
            "actividades": [],
        })
        p["pki"].append(9.0 - math.log10(float(a["standard_value"])))
        p["actividades"].append(str(a["activity_id"]))
    salida = []
    for p in sorted(padres.values(), key=lambda x: x["padre"]):
        pki = sorted(p["pki"])
        mediana = pki[len(pki) // 2] if len(pki) % 2 else (pki[len(pki) // 2 - 1] + pki[len(pki) // 2]) / 2
        salida.append({"padre": p["padre"], "smiles": p["smiles"], "pki": round(mediana, 6),
                       "n_actividades": len(pki), "actividades": ";".join(p["actividades"])})
    if len(salida) != 57:
        raise SystemExit(f"se esperaban 57 padres, hay {len(salida)}")
    return salida


_SONDA_MICROESTADO = r"""
import asyncio, json, sys
sys.path[:0] = [sys.argv[1]]
from chem.conformer import generate_conformer
smiles = json.loads(sys.stdin.read())
out = {}
for s in smiles:
    r = asyncio.run(generate_conformer(s))
    e = r.get("estado_del_ligando") or {}
    out[s] = {"smiles_acoplado": e.get("smiles_acoplado"), "carga": e.get("carga_formal_neta")}
print(json.dumps(out))
"""


def _microestados(smiles: list[str], datos: Path) -> dict[str, Any]:
    """La preparación del ligando del producto, en un proceso aparte con datos desechables."""
    g = _arnes()
    datos.mkdir(parents=True, exist_ok=True)
    env = g.entorno_runtime(datos, datos / "vina-tmp")
    r = subprocess.run([sys.executable, "-c", _SONDA_MICROESTADO, str(RAIZ / "backend")],
                       input=json.dumps(smiles), capture_output=True, text=True, env=env,
                       cwd=str(RAIZ / "backend"))
    if r.returncode != 0:
        raise SystemExit(f"la sonda de microestados falló:\n{r.stderr[-3000:]}")
    return json.loads(r.stdout.strip().splitlines()[-1])


def cmd_congelar(args: argparse.Namespace) -> int:
    if CORRIDAS.exists():
        raise SystemExit("ya hay corridas: el protocolo no se vuelve a congelar")
    datos = Path(args.datos)
    panel = _panel_desde_fuentes()
    entradas = [SMILES_CRISTAL] + [p["smiles"] for p in panel]
    # Dos procesos: el microestado tiene que ser reproducible entre procesos
    # (dimorphite barajaba la lista en cada proceso; ver la memoria del proyecto).
    a = _microestados(entradas, datos / "sonda-1")
    b = _microestados(entradas, datos / "sonda-2")
    if a != b:
        distintos = [s for s in entradas if a[s] != b[s]]
        raise SystemExit(f"microestado no reproducible entre procesos en {len(distintos)}: {distintos[:5]}")
    for p in panel:
        p["smiles_acoplado_esperado"] = a[p["smiles"]]["smiles_acoplado"]
        p["carga_esperada"] = a[p["smiles"]]["carga"]

    ENTRADA.mkdir(parents=True, exist_ok=True)
    ruta_panel = ENTRADA / "panel_congelado.csv"
    with ruta_panel.open("w", encoding="utf-8", newline="\n") as fh:
        w = csv.DictWriter(fh, fieldnames=list(panel[0].keys()), lineterminator="\n")
        w.writeheader()
        w.writerows(panel)
    for nombre in ("panel_8hfi.csv", "PROTOCOLO_8HFI_BORRADOR.md", "DECISIONES_PENDIENTES.md"):
        (ENTRADA / nombre).write_bytes((FUENTE_PANEL / nombre).read_bytes())
    (ENTRADA / "chembl_activities_CHEMBL853189.json").write_bytes(
        (FUENTE_PANEL / "fuentes" / "chembl_activities_CHEMBL853189.json").read_bytes())

    catalogo = json.loads((RAIZ / "curated_targets.json").read_text(encoding="utf-8"))
    entrada_cat = next(e for e in catalogo if e["pdb_id"] == PDB_ID)
    protocolo = {
        "experimento": EXPERIMENTO,
        "congelado_en": _ahora(),
        "git_head": _git("rev-parse", "HEAD"),
        "arbol_limpio_backend": _git("status", "--porcelain", "backend", "data", "curated_targets.json") == "",
        "receptor": {
            "pdb_id": PDB_ID, "cadena": CADENA, "site_chains": entrada_cat.get("site_chains"),
            "caja_catalogo": {"centro": [entrada_cat[f"grid_center_{e}"] for e in "xyz"],
                              "tamano": [entrada_cat[f"grid_size_{e}"] for e in "xyz"]},
            "fuente_sha256": _sha(RAIZ / "data" / "targets" / f"{PDB_ID}.pdb.gz"),
            "receta": 7, "cofactors_whitelist": entrada_cat.get("cofactors_whitelist") or [],
        },
        "configuracion_del_caso": CONFIG_CASO,
        "verificacion": {
            "ligando_cristal": {"ccd": LIGANDO_CRISTAL[0], "cadena": LIGANDO_CRISTAL[1],
                                "numero": LIGANDO_CRISTAL[2], "smiles_entrada": SMILES_CRISTAL,
                                "smiles_acoplado_esperado": a[SMILES_CRISTAL]["smiles_acoplado"]},
            "semillas": list(SEMILLAS_REDOCKING),
            "rmsd": "simétrico, átomos pesados, SIN alinear (RDKit rdMolAlign.CalcRMS), top-1 de Vina",
            "rmsd_max_A": RMSD_MAX_A,
            "validez": "evidencia estructural del producto (PoseBusters dock, condición MF-33-H-COR): "
                       "top-1 con status == 'passed'",
            "gate": f">= {SEMILLAS_OK_MINIMAS} de {len(SEMILLAS_REDOCKING)} semillas con RMSD <= {RMSD_MAX_A} A, "
                    "y el top-1 de cada una de ellas válido",
        },
        "calibracion": {
            "panel": "CHEMBL853189 (Boot et al. 2006, DOI 10.1016/j.bmcl.2006.02.008)",
            "n_padres": len(panel), "endpoint": "Ki", "pki": "mediana por padre de -log10(Ki/M)",
            "semilla": SEMILLA_PANEL,
            "score": "Q = -E, con E la afinidad del top-1 de Vina (docking_poses rank 1)",
            "metrica": "rho de Spearman (rangos promedio en empates) entre Q y pKi; se publica también rho(E, pKi)",
            "ic": f"percentil 2,5-97,5 de {BOOTSTRAP_N} remuestreos de compuestos, numpy default_rng({BOOTSTRAP_SEMILLA}); "
                  "Fisher como referencia secundaria",
            "gate": "limite inferior del IC > 0 y cero fallos tras un reintento técnico",
            "potencia": "con n = 57, Fisher exige rho ~> 0,26 para un limite inferior > 0",
            "alcance": "53 de 57 padres comparten andamio de Murcko: la rho describe una serie congenérica",
        },
        "fallos": "un reintento técnico idéntico; un fallo persistente en el panel hace fallar el gate de "
                  "calibración y se publica; en el redocking cuenta como semilla no superada",
        "diagnosticos": [
            f"distancia mínima del top-1 de cada corrida al {CLORURO[0]} {CLORURO[1]}:{CLORURO[2]} depositado",
            "microestado acoplado frente al esperado (desviación de protocolo si difiere)",
            "parámetros efectivos (exhaustiveness, num_poses, seed) y receptor_sha256 únicos en todas las corridas",
        ],
        "condiciones_declaradas": CONDICIONES,
        "decisiones_del_propietario": "2026-10-09: iones declarados como condición; parámetros por defecto del "
                                      "caso 8/9/42; bootstrap por compuesto con alcance de serie; microestados "
                                      "del producto; condiciones del ensayo como limitación",
        "hashes": {
            "panel_congelado.csv": _sha(ruta_panel),
            "chembl_activities_CHEMBL853189.json": _sha(ENTRADA / "chembl_activities_CHEMBL853189.json"),
            "calibracion_receptor.py": _sha(Path(__file__)),
            "vina.exe": _sha(RAIZ / "tools" / "vina" / "vina.exe"),
            "python": sys.version.split()[0],
        },
    }
    _escribir_json(ENTRADA / "protocolo.json", protocolo)
    print(f"congelado: {len(panel)} padres; microestados reproducibles; protocolo en {ENTRADA}")
    return 0


# ── Ejecutar: redocking y panel, reanudable ──────────────────────────────────

def _hechas() -> dict[str, dict[str, Any]]:
    if not CORRIDAS.exists():
        return {}
    return {json.loads(l)["id"]: json.loads(l) for l in CORRIDAS.read_text(encoding="utf-8").splitlines() if l.strip()}


def cmd_ejecutar(args: argparse.Namespace) -> int:
    protocolo = json.loads((ENTRADA / "protocolo.json").read_text(encoding="utf-8"))
    if protocolo["hashes"]["calibracion_receptor.py"] != _sha(Path(__file__)):
        raise SystemExit("el script cambió desde que se congeló el protocolo")
    if protocolo["hashes"]["panel_congelado.csv"] != _sha(ENTRADA / "panel_congelado.csv"):
        raise SystemExit("el panel cambió desde que se congeló")
    panel = list(csv.DictReader((ENTRADA / "panel_congelado.csv").open(encoding="utf-8")))
    trabajos = [(f"redock-s{s}", SMILES_CRISTAL, s) for s in SEMILLAS_REDOCKING]
    trabajos += [(f"panel-{p['padre']}", p["smiles"], SEMILLA_PANEL) for p in panel]
    hechas = _hechas()
    TRABAJO.mkdir(parents=True, exist_ok=True)
    with Backend(Path(args.datos)) as be:
        for ident, smiles, seed in trabajos:
            if ident in hechas:
                continue
            intentos = []
            registro: dict[str, Any] = {"id": ident, "smiles": smiles, "semilla": seed}
            for n in range(1, INTENTOS + 1):
                t0 = time.monotonic()
                try:
                    r = be.evaluar(smiles, PDB_ID, CADENA, seed, ident)
                except Exception as exc:  # noqa: BLE001 - se registra y cuenta
                    intentos.append({"n": n, "error": f"{type(exc).__name__}: {str(exc)[:800]}",
                                     "segundos": round(time.monotonic() - t0, 1)})
                    continue
                crudo = TRABAJO / f"{ident}.json.gz"
                crudo.write_bytes(gzip.compress(json.dumps(r, ensure_ascii=False).encode("utf-8"), mtime=0))
                intentos.append({"n": n, "ok": True, "segundos": r["segundos"]})
                registro.update({"estado": "SUCCESS", "task_id": r["task_id"], "crudo": crudo.name,
                                 "crudo_sha256": _sha(crudo)})
                break
            else:
                registro["estado"] = "FALLO"
            registro["intentos"] = intentos
            registro["registrado_en"] = _ahora()
            with CORRIDAS.open("a", encoding="utf-8", newline="\n") as fh:
                fh.write(json.dumps(registro, ensure_ascii=False) + "\n")
            print(ident, registro["estado"], intentos[-1].get("segundos"), flush=True)
    return 0


# ── Analizar ─────────────────────────────────────────────────────────────────

def _cristal():
    """Desipramina y cloruro del depósito, en el marco del receptor."""
    from rdkit import Chem
    from rdkit.Chem import AllChem

    texto = gzip.decompress((RAIZ / "data" / "targets" / f"{PDB_ID}.pdb.gz").read_bytes()).decode("utf-8")
    lig = [l for l in texto.splitlines() if l.startswith("HETATM") and l[17:20].strip() == LIGANDO_CRISTAL[0]
           and l[21] == LIGANDO_CRISTAL[1] and int(l[22:26]) == LIGANDO_CRISTAL[2]]
    cl = [l for l in texto.splitlines() if l.startswith("HETATM") and l[17:20].strip() == CLORURO[0]
          and l[21] == CLORURO[1] and int(l[22:26]) == CLORURO[2]]
    if len(cl) != 1:
        raise SystemExit(f"cloruro esperado una vez, hay {len(cl)}")
    bloque = "\n".join(lig) + "\nEND\n"
    ref = Chem.MolFromPDBBlock(bloque, removeHs=True, sanitize=False)
    ref = AllChem.AssignBondOrdersFromTemplate(Chem.MolFromSmiles(SMILES_CRISTAL), ref)
    if ref.GetNumAtoms() != Chem.MolFromSmiles(SMILES_CRISTAL).GetNumAtoms():
        raise SystemExit("el ligando del cristal no casa con el SMILES de la desipramina")
    pos_cl = tuple(float(cl[0][i:i + 8]) for i in (30, 38, 46))
    return ref, pos_cl


def _neutro_sin_h(mol):
    """Átomos pesados en forma neutra, para casar la pose con el cristal.

    Primero se quitan los H y después se neutraliza: con los H explícitos de la
    pose (el SDF del producto los trae) el Uncharger no puede retirar el protón
    de una amina y la carga impedía casar con el cristal neutro. Corrección
    técnica tras el primer intento de `analizar`, que falló al casar átomos
    antes de calcular ningún RMSD (ver metrics.json, desviaciones del análisis).
    """
    from rdkit import Chem
    from rdkit.Chem.MolStandardize import rdMolStandardize

    return rdMolStandardize.Uncharger().uncharge(Chem.RemoveHs(Chem.Mol(mol)))


def _top1(r: dict[str, Any]):
    """El top-1 del SDF de poses, contrastado con el bloque PDBQT del rank 1."""
    from rdkit import Chem

    sup = Chem.SDMolSupplier()
    sup.SetData(r["poses_sdf"], removeHs=False)
    mols = [m for m in sup if m is not None]
    poses = r["resultado"]["docking_poses"]
    rank1 = next(p for p in poses if p["rank"] == 1)
    # Los pseudoátomos G0, G1… con que Meeko abre un anillo para darle
    # flexibilidad no son átomos: se excluyen. Cada átomo pesado del PDBQT
    # tiene que tener uno del SDF a ≤ 0,05 Å (redondeo y cierre del anillo).
    pdbqt = [tuple(float(l[i:i + 8]) for i in (30, 38, 46)) for l in rank1["pdbqt_block"].splitlines()
             if l.startswith(("ATOM", "HETATM")) and l[77:79].strip() not in {"HD", "H"}
             and not l[77:79].strip().startswith("G")]
    sdf = [tuple(mols[0].GetConformer().GetAtomPosition(a.GetIdx()))
           for a in mols[0].GetAtoms() if a.GetAtomicNum() > 1]
    casa = len(pdbqt) == len(sdf) and all(min(math.dist(p, q) for q in sdf) <= 0.05 for p in pdbqt)
    return mols[0], rank1["affinity"], casa


def _rangos(x):
    import numpy as np
    from scipy.stats import rankdata
    return rankdata(np.asarray(x, dtype=float), method="average")


def _spearman(x, y) -> float:
    import numpy as np
    rx, ry = _rangos(x), _rangos(y)
    return float(np.corrcoef(rx, ry)[0, 1])


def cmd_analizar(args: argparse.Namespace) -> int:
    import numpy as np
    from rdkit.Chem import rdMolAlign

    protocolo = json.loads((ENTRADA / "protocolo.json").read_text(encoding="utf-8"))
    panel = {p["padre"]: p for p in csv.DictReader((ENTRADA / "panel_congelado.csv").open(encoding="utf-8"))}
    corridas = _hechas()
    ref, pos_cl = _cristal()
    ref_n = _neutro_sin_h(ref)
    por_complejo, fallos, desviaciones = [], [], []
    shas, parametros = set(), set()

    def comunes(ident: str, r: dict[str, Any]) -> dict[str, Any]:
        res = r["resultado"]
        prov = (res.get("docking_protocol") or {}).get("execution_provenance") or {}
        dp = res.get("docking_protocol") or {}
        shas.add(prov.get("receptor_sha256"))
        parametros.add((dp.get("exhaustiveness"), dp.get("num_poses")))
        mol, e, casa = _top1(r)
        if not casa:
            desviaciones.append({"id": ident, "desviacion": "el SDF top-1 no casa con el PDBQT del rank 1"})
        se = res.get("structural_evidence") or {}
        top = next((p for p in se.get("poses") or [] if p.get("rank") == 1), {})
        conf = mol.GetConformer()
        d_cl = min(math.dist(pos_cl, tuple(conf.GetAtomPosition(a.GetIdx())))
                   for a in mol.GetAtoms() if a.GetAtomicNum() > 1)
        return {"mol": mol, "E": e, "valida": top.get("status") == "passed",
                "estado_fisico": top.get("status"), "seed": dp.get("seed"),
                "smiles_acoplado": (res.get("ligand_state") or {}).get("smiles_acoplado"),
                "d_cloruro_A": round(d_cl, 3), "receptor_sha256": prov.get("receptor_sha256"),
                "receta": prov.get("receta_receptor")}

    # Verificación de pose
    semillas = []
    for s in SEMILLAS_REDOCKING:
        ident = f"redock-s{s}"
        c = corridas.get(ident)
        if not c or c.get("estado") != "SUCCESS":
            semillas.append({"semilla": s, "estado": "FALLO", "rmsd_A": None, "valida": False})
            fallos.append({"id": ident, "intentos": (c or {}).get("intentos")})
            continue
        r = json.loads(gzip.decompress((TRABAJO / c["crudo"]).read_bytes()))
        x = comunes(ident, r)
        if x["seed"] != s:
            desviaciones.append({"id": ident, "desviacion": f"semilla efectiva {x['seed']} != {s}"})
        if x["smiles_acoplado"] != protocolo["verificacion"]["ligando_cristal"]["smiles_acoplado_esperado"]:
            desviaciones.append({"id": ident, "desviacion": f"microestado {x['smiles_acoplado']}"})
        rmsd = rdMolAlign.CalcRMS(_neutro_sin_h(x["mol"]), ref_n)
        fila = {"id": ident, "tipo": "redocking", "semilla": s, "E_kcal": x["E"], "rmsd_A": round(rmsd, 3),
                "valida": x["valida"], "estado_fisico": x["estado_fisico"], "d_cloruro_A": x["d_cloruro_A"],
                "receptor_sha256": x["receptor_sha256"], "receta": x["receta"]}
        semillas.append({"semilla": s, "estado": "SUCCESS", "rmsd_A": fila["rmsd_A"], "valida": x["valida"]})
        por_complejo.append(fila)
    ok = [s for s in semillas if s["rmsd_A"] is not None and s["rmsd_A"] <= RMSD_MAX_A]
    pose_valida = bool(ok) and all(s["valida"] for s in ok)
    gate_pose = len(ok) >= SEMILLAS_OK_MINIMAS and pose_valida

    # Calibración
    q, pki, fallos_panel = [], [], 0
    for padre, p in panel.items():
        ident = f"panel-{padre}"
        c = corridas.get(ident)
        if not c or c.get("estado") != "SUCCESS":
            fallos_panel += 1
            fallos.append({"id": ident, "intentos": (c or {}).get("intentos")})
            continue
        r = json.loads(gzip.decompress((TRABAJO / c["crudo"]).read_bytes()))
        x = comunes(ident, r)
        if x["seed"] != SEMILLA_PANEL:
            desviaciones.append({"id": ident, "desviacion": f"semilla efectiva {x['seed']}"})
        if x["smiles_acoplado"] != p["smiles_acoplado_esperado"]:
            desviaciones.append({"id": ident, "desviacion": f"microestado {x['smiles_acoplado']} != "
                                                           f"{p['smiles_acoplado_esperado']}"})
        q.append(-x["E"])
        pki.append(float(p["pki"]))
        por_complejo.append({"id": ident, "tipo": "panel", "padre": padre, "pki": float(p["pki"]),
                             "E_kcal": x["E"], "Q": -x["E"], "valida_top1": x["valida"],
                             "d_cloruro_A": x["d_cloruro_A"], "receptor_sha256": x["receptor_sha256"],
                             "receta": x["receta"]})
    n = len(q)
    rho = _spearman(q, pki) if n >= 3 else None
    ic = None
    fisher = None
    if rho is not None:
        rng = np.random.default_rng(BOOTSTRAP_SEMILLA)
        qa, pa = np.asarray(q), np.asarray(pki)
        boots = []
        for _ in range(BOOTSTRAP_N):
            idx = rng.integers(0, n, n)
            if np.unique(qa[idx]).size < 2 or np.unique(pa[idx]).size < 2:
                continue
            boots.append(_spearman(qa[idx], pa[idx]))
        ic = [round(float(np.percentile(boots, 2.5)), 4), round(float(np.percentile(boots, 97.5)), 4)]
        z, se = math.atanh(rho), 1 / math.sqrt(n - 3)
        fisher = [round(math.tanh(z - 1.96 * se), 4), round(math.tanh(z + 1.96 * se), 4)]
    gate_cal = rho is not None and ic is not None and ic[0] > 0 and fallos_panel == 0

    metrics = {
        "experimento": EXPERIMENTO,
        "analizado_en": _ahora(),
        "receptor_sha256_distintos": sorted(s for s in shas if s),
        "parametros_efectivos": sorted([list(p) for p in parametros]),
        "verificacion": {"semillas": semillas, "semillas_rmsd_ok": len(ok), "posebusters_valida": pose_valida,
                         "gate": "GO" if gate_pose else "NO_GO"},
        "calibracion": {"n": n, "fallos": fallos_panel, "rho_Q_pKi": None if rho is None else round(rho, 4),
                        "rho_E_pKi": None if rho is None else round(-rho, 4), "ic95_bootstrap": ic,
                        "ic95_fisher": fisher, "bootstrap": {"n": BOOTSTRAP_N, "semilla": BOOTSTRAP_SEMILLA},
                        "rango_pki": [min(pki), max(pki)] if pki else None,
                        "gate": "GO" if gate_cal else "NO_GO"},
        "diagnostico_cloruro": {
            "d_min_A": min((f["d_cloruro_A"] for f in por_complejo), default=None),
            "n_top1_a_menos_de_8A": sum(1 for f in por_complejo if f["d_cloruro_A"] < 8.0),
        },
        "desviaciones": desviaciones,
        "desviaciones_del_analisis": DESVIACIONES_DEL_ANALISIS,
        "decision": "GO" if gate_pose and gate_cal and len(shas - {None}) == 1 else "NO_GO",
    }
    _escribir_json(DIR_EXP / "metrics.json", metrics)
    with (DIR_EXP / "per_complex.jsonl").open("w", encoding="utf-8", newline="\n") as fh:
        for f in por_complejo:
            fh.write(json.dumps(f, ensure_ascii=False) + "\n")
    with (DIR_EXP / "failures.jsonl").open("w", encoding="utf-8", newline="\n") as fh:
        for f in fallos:
            fh.write(json.dumps(f, ensure_ascii=False) + "\n")
    print(json.dumps({k: metrics[k] for k in ("verificacion", "calibracion", "diagnostico_cloruro", "decision")},
                     indent=2, ensure_ascii=False))
    print("desviaciones:", len(desviaciones))
    return 0


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__.split("\n", 2)[1])
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("piloto")
    s.add_argument("--salida", required=True)
    s.set_defaults(func=cmd_piloto)
    s = sub.add_parser("congelar")
    s.add_argument("--datos", required=True)
    s.set_defaults(func=cmd_congelar)
    s = sub.add_parser("ejecutar")
    s.add_argument("--datos", required=True)
    s.set_defaults(func=cmd_ejecutar)
    s = sub.add_parser("analizar")
    s.set_defaults(func=cmd_analizar)
    a = p.parse_args()
    raise SystemExit(a.func(a))
