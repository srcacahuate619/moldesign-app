r"""CAL-D-01 R4: calibración de 8T69 (VMAT2) contra los Ki publicados de la patente US11718618B2.

Arnés parametrizado de `scripts/calibracion_receptor.py` (CAL-8HFI-01): se importa sin modificarlo y
se usan tal cual su evaluación por la API, el microestado, el top-1 y el RMSD simétrico sin alinear.
Cambian el receptor, el ligando del cristal, el panel y el criterio de decisión (REGISTRO_PREVIO_R4.md).
El estadístico P1 (ρ y ρ de peor caso con IC por bootstrap pareado por padre) vive en rho_peor.py.

Uso, siempre con el Python embebido, desde el worktree congelado:

    python scripts/cal_d01r4/cal_d01r4.py selftest
    python scripts/cal_d01r4/cal_d01r4.py congelar              # panel, microestados, receptor y protocolo
    python scripts/cal_d01r4/cal_d01r4.py ejecutar --fase pose  # 5 redockings del cristal (YHL)
    python scripts/cal_d01r4/cal_d01r4.py analizar --fase pose  # puerta de pose; sin ella no se acopla el panel
    python scripts/cal_d01r4/cal_d01r4.py ejecutar --fase panel --shard 1 --shards 2
    python scripts/cal_d01r4/cal_d01r4.py ejecutar --fase sens
    python scripts/cal_d01r4/cal_d01r4.py analizar              # P1, P2, sensibilidades y decisión

`congelar` se ejecuta y se commitea ANTES de `ejecutar`. Una corrida con deriva (microestado, receptor o
parámetros distintos de los congelados) detiene la campaña; no se reacopla con otra cosa.
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
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

AQUI = Path(__file__).resolve().parent
RAIZ = next(p for p in AQUI.parents if (p / "curated_targets.json").is_file())
EXP = RAIZ / "scripts" / "artifacts_science" / "CAL-D-01-R4-VMAT2-8T69"
ENTRADA = EXP / "entrada"
TRABAJO = EXP / "_work"
REGISTRO = Path(r"D:\moldesign-audits\CAL_D_01_R4\registro_previo")
UNIVERSO_R2 = Path(r"D:\moldesign-audits\CAL_D_01_R2\entrega\universo_8T69_auditado.csv")
CCD_YHL = Path(r"D:\moldesign-audits\CAL_D_01_R2\entrega\fuentes\YHL_ccd.cif")

# ── Lo que el registro previo congeló (SHA-256 anotados fuera de su carpeta) ──
SHA_REGISTRO = "0a1a4aed5b67c8f62190957de7cc3a6490aebff87e94ccf2e817373456a7c93f"
SHA_PANEL = "ff5e0c69eda2fea39e143db5360a384ff183baa02124f40f717f508560722ca9"
SHA_UNIVERSO = "b63c0763ebd64e1f02a6ddab7598bb659b1f8ee791cf09179493e58b557460cd"
SHA_CCD_YHL = "ea7eff7900bfd409b1ebb4d0acf580d8ea995ab996b2d44c10a09d9e12bedea8"
ANCLAJE = "6f3ff1b5"
PDB_ID, CADENA = "8T69", "A"
LIGANDO_CRISTAL = ("YHL", "A", 901)
SEMILLAS_REDOCKING = (42, 43, 44, 45, 46)
SEMILLA_PANEL = 42
RMSD_MAX_A = 2.0
SEMILLAS_OK_MINIMAS = 3
CPU_POR_PROCESO = 4
TOPE_CPU_H = 168.0
MIN_PADRES = 85
INTENTOS = 2
ID_SENS = "S-4-31-118"

sys.path.insert(0, str(RAIZ / "scripts"))
sys.path.insert(0, str(AQUI))
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
sys.dont_write_bytecode = True


def _sha_b(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _sha(p: Path) -> str:
    return _sha_b(p.read_bytes())


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _leer(p: Path) -> Any:
    return json.loads(p.read_text(encoding="utf-8"))


def _escribir(p: Path, o: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(o, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8", newline="\n")


def _git(*a: str) -> str:
    return subprocess.run(["git", "-C", str(RAIZ), *a], capture_output=True, text=True).stdout.strip()


def _cal():
    import calibracion_receptor as cal
    return cal


# ── Congelar ─────────────────────────────────────────────────────────────────

def _smiles_ligando_cristal() -> str:
    """El SMILES de YHL del CCD, comprobado contra la geometría del depósito del catálogo."""
    from rdkit import Chem
    from rdkit.Chem import AllChem
    if _sha(CCD_YHL) != SHA_CCD_YHL:
        raise SystemExit("el CCD de YHL no es el de la fuente de R2")
    import re
    d = {}
    for l in CCD_YHL.read_text(encoding="utf-8").splitlines():
        m = re.match(r'YHL SMILES_CANONICAL\s+"?(CACTVS|OpenEye)[^"\s]*(?:\s+OEToolkits)?"?\s+\S+\s+"([^"]+)"', l)
        if m:
            d[m.group(1)] = m.group(2)
    if set(d) != {"CACTVS", "OpenEye"}:
        raise SystemExit(f"no se leyeron los dos SMILES canónicos del CCD: {d}")
    cactvs, openeye = d["CACTVS"], d["OpenEye"]
    canon = lambda s: Chem.MolToSmiles(Chem.MolFromSmiles(s))
    if canon(cactvs) != canon(openeye):
        raise SystemExit("CACTVS y OpenEye no describen la misma molécula")
    ref = _cristal_mol(canon(cactvs))
    if Chem.MolToSmiles(ref) != canon(cactvs):
        raise SystemExit("el ligando del depósito no coincide con el CCD (estereoquímica)")
    return canon(cactvs)


def _cristal_mol(smiles: str):
    """YHL A901 del depósito del catálogo, con órdenes de enlace y estereoquímica de la plantilla."""
    from rdkit import Chem
    from rdkit.Chem import AllChem
    texto = gzip.decompress((RAIZ / "data" / "targets" / f"{PDB_ID}.pdb.gz").read_bytes()).decode("utf-8")
    lig = [l for l in texto.splitlines() if l.startswith("HETATM") and l[17:20].strip() == LIGANDO_CRISTAL[0]
           and l[21] == LIGANDO_CRISTAL[1] and int(l[22:26]) == LIGANDO_CRISTAL[2]]
    if len(lig) != 23:
        raise SystemExit(f"YHL esperado con 23 átomos, hay {len(lig)}")
    ref = Chem.MolFromPDBBlock("\n".join(lig) + "\nEND\n", removeHs=True, sanitize=False)
    m = AllChem.AssignBondOrdersFromTemplate(Chem.MolFromSmiles(smiles), ref)
    Chem.AssignStereochemistryFrom3D(m)
    return m


def _panel_fuentes() -> list[dict[str, Any]]:
    from rdkit import Chem
    if _sha(REGISTRO / "REGISTRO_PREVIO_R4.md") != SHA_REGISTRO:
        raise SystemExit("REGISTRO_PREVIO_R4.md cambió desde que se anotó su hash")
    if _sha(REGISTRO / "panel_89_8T69.csv") != SHA_PANEL:
        raise SystemExit("panel_89_8T69.csv cambió")
    if _sha(UNIVERSO_R2) != SHA_UNIVERSO:
        raise SystemExit("el universo de R2 cambió")
    filas = list(csv.DictReader((REGISTRO / "panel_89_8T69.csv").open(encoding="utf-8-sig")))
    if len(filas) != 89 or {f["operador"] for f in filas} != {"="} or {f["unidad"] for f in filas} != {"nM"}:
        raise SystemExit("el panel no son 89 Ki puntuales en nM")
    out = []
    for f in filas:
        ki = float(f["valor"])
        m = Chem.MolFromSmiles(f["smiles_isomerico_completo"])
        out.append({"padre": f["id_ejemplo"], "tabla": f["tabla"], "ki_nM": f["valor"],
                    "pki": round(9.0 - math.log10(ki), 6),
                    "smiles": Chem.MolToSmiles(m), "rol": "primario"})
    # sensibilidad: 4-31 y 4-118 son la misma molécula (Ki 1,6 y 13 nM): se acopla una vez
    u = {r["id_ejemplo"]: r for r in csv.DictReader(UNIVERSO_R2.open(encoding="utf-8-sig"))}
    a, b = u["4-31"], u["4-118"]
    if a["smiles_isomerico_completo"] != b["smiles_isomerico_completo"]:
        raise SystemExit("4-31 y 4-118 ya no son la misma molécula")
    out.append({"padre": ID_SENS, "tabla": "15A/15B", "ki_nM": f"{a['valor']}|{b['valor']}", "pki": None,
                "smiles": Chem.MolToSmiles(Chem.MolFromSmiles(a["smiles_isomerico_completo"])), "rol": "sensibilidad"})
    if len({p["padre"] for p in out}) != 90:
        raise SystemExit("identificadores de padre repetidos")
    return out


_SONDA_RECEPTOR = r"""
import asyncio, hashlib, json, sys
sys.path[:0] = [sys.argv[1]]
from services.docking.preparer import prepare_target
from utils.local_storage import path_for
e = json.loads(sys.stdin.read())
p = asyncio.run(prepare_target(e['pdb_id'], e['chain'], tuple(e['grid_center_' + c] for c in 'xyz'),
                tuple(e['grid_size_' + c] for c in 'xyz'), force_reprepare=True, cofactors_whitelist=[],
                site_chains=e.get('site_chains'), site_ligand=e.get('site_ligand')))
p = path_for(p)
print(json.dumps({'sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'bytes': p.stat().st_size}))
"""


def _receptor_preparado(datos: Path, entrada_catalogo: dict, env: dict | None = None) -> dict:
    """Prepara el receptor del catálogo en un proceso aparte. Con `env` (el de una cápsula) usa sus datos."""
    if env is None:
        cal = _cal()
        g = cal._arnes()
        datos.mkdir(parents=True, exist_ok=True)
        env = g.entorno_runtime(datos, datos / "vina-tmp")
    r = subprocess.run([sys.executable, "-c", _SONDA_RECEPTOR, str(RAIZ / "backend")], input=json.dumps(entrada_catalogo),
                       capture_output=True, text=True, env=env, cwd=str(RAIZ / "backend"))
    if r.returncode:
        raise SystemExit(f"la preparación del receptor falló:\n{r.stderr[-3000:]}")
    return json.loads(r.stdout.strip().splitlines()[-1])


def cmd_congelar(args: argparse.Namespace) -> int:
    if (TRABAJO / "pose").exists() or (TRABAJO / "panel").exists():
        raise SystemExit("ya hay corridas: el protocolo no se vuelve a congelar")
    if _git("status", "--porcelain", "--untracked-files=no"):
        raise SystemExit("el árbol tiene cambios sin commitear; congela sobre un commit limpio")
    cal = _cal()
    datos = Path(args.datos)
    smiles_cristal = _smiles_ligando_cristal()
    panel = _panel_fuentes()
    entradas = [smiles_cristal] + [p["smiles"] for p in panel]
    a = cal._microestados(entradas, datos / "sonda-1")
    b = cal._microestados(entradas, datos / "sonda-2")
    if a != b:
        raise SystemExit(f"microestado no reproducible entre procesos en {sum(a[s] != b[s] for s in entradas)} entradas")
    for p in panel:
        p["smiles_acoplado_esperado"] = a[p["smiles"]]["smiles_acoplado"]
        p["carga_esperada"] = a[p["smiles"]]["carga"]
        if not p["smiles_acoplado_esperado"]:
            raise SystemExit(f"sin microestado para {p['padre']}")
    cat = next(e for e in _leer(RAIZ / "curated_targets.json") if e["pdb_id"] == PDB_ID)
    r1 = _receptor_preparado(datos / "receptor-1", cat)
    r2 = _receptor_preparado(datos / "receptor-2", cat)
    if r1 != r2:
        raise SystemExit(f"el receptor preparado no es reproducible: {r1} {r2}")

    ENTRADA.mkdir(parents=True, exist_ok=True)
    for nombre, fuente in (("REGISTRO_PREVIO_R4.md", REGISTRO), ("panel_89_8T69.csv", REGISTRO)):
        (ENTRADA / nombre).write_bytes((fuente / nombre).read_bytes())
    (ENTRADA / "universo_8T69_auditado.csv").write_bytes(UNIVERSO_R2.read_bytes())
    (ENTRADA / "YHL_ccd.cif").write_bytes(CCD_YHL.read_bytes())
    ruta = ENTRADA / "panel_congelado.csv"
    with ruta.open("w", encoding="utf-8", newline="\n") as fh:
        w = csv.DictWriter(fh, fieldnames=list(panel[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(panel)
    protocolo = {
        "experimento": EXP.name, "congelado_en": _ahora(), "git_head": _git("rev-parse", "HEAD"),
        "anclaje_del_registro": ANCLAJE,
        "registro_previo_sha256": SHA_REGISTRO,
        "receptor": {"pdb_id": PDB_ID, "cadena": CADENA, "site_chains": cat.get("site_chains"),
                     "site_ligand": cat.get("site_ligand"),
                     "caja_catalogo": {"centro": [cat[f"grid_center_{e}"] for e in "xyz"],
                                       "tamano": [cat[f"grid_size_{e}"] for e in "xyz"]},
                     "fuente_sha256": _sha(RAIZ / "data" / "targets" / f"{PDB_ID}.pdb.gz"),
                     "cofactors_whitelist": cat.get("cofactors_whitelist") or [],
                     "receptor_preparado_sha256": r1["sha256"], "receptor_preparado_bytes": r1["bytes"],
                     "reproducible_en_dos_procesos": True},
        "configuracion_del_caso": cal.CONFIG_CASO,
        "cpu_por_proceso": CPU_POR_PROCESO, "tope_cpu_core_h": TOPE_CPU_H,
        "verificacion": {"ligando_cristal": {"ccd": LIGANDO_CRISTAL[0], "cadena": LIGANDO_CRISTAL[1],
                                             "numero": LIGANDO_CRISTAL[2], "smiles_entrada": smiles_cristal,
                                             "smiles_acoplado_esperado": a[smiles_cristal]["smiles_acoplado"]},
                         "semillas": list(SEMILLAS_REDOCKING), "rmsd_max_A": RMSD_MAX_A,
                         "rmsd": "simétrico, átomos pesados, SIN alinear (rdMolAlign.CalcRMS), top-1 de Vina",
                         "gate": f">= {SEMILLAS_OK_MINIMAS} de {len(SEMILLAS_REDOCKING)} semillas con RMSD <= {RMSD_MAX_A} A "
                                 "y el top-1 de cada una de ellas válido en PoseBusters (MF-33-H-COR); si falla, NO_GO y no se acopla el panel"},
        "calibracion": {"n_padres_primario": 89, "semilla": SEMILLA_PANEL, "score": "Q = -E(top-1 de Vina)",
                        "p1": "GO si el límite inferior del IC95 % de rho Y el de rho_peor son > 0 "
                              "(bootstrap pareado por padre, 10 000, semilla 20261021), sin fallos persistentes ni desviaciones",
                        "factor_F": "1015/703", "minimo_padres": MIN_PADRES,
                        "sensibilidades": "P2 concordancia de pares con cociente de Ki > F; rho con 4-31, con 4-118 y con la mediana de ambos"},
        "fallos": "un reintento técnico idéntico; los dos intentos se conservan; deriva = parada",
        "hashes": {"panel_congelado.csv": _sha(ruta), "cal_d01r4.py": _sha(Path(__file__)),
                   "rho_peor.py": _sha(AQUI / "rho_peor.py"), "capsula.mjs": _sha(AQUI / "capsula.mjs"),
                   "calibracion_receptor.py": _sha(RAIZ / "scripts" / "calibracion_receptor.py"),
                   "vina.exe": _sha(RAIZ / "tools" / "vina" / "vina.exe"), "python": sys.version.split()[0]},
    }
    _escribir(ENTRADA / "protocolo.json", protocolo)
    print(f"congelado: {len(panel)} padres (89 + sensibilidad), receptor {r1['sha256'][:12]}…, microestados reproducibles")
    return 0


# ── Ejecutar ─────────────────────────────────────────────────────────────────

class Capsula:
    """Backend de la API con perfil y datos aislados (el de MET-01-R1), 4 CPU de Vina."""

    def __init__(self, ruta: Path, numero: int):
        r = subprocess.run(["node", str(AQUI / "capsula.mjs"), str(RAIZ), "D:/moldesign-build", str(ruta), str(numero)],
                           capture_output=True, text=True)
        if r.returncode:
            raise RuntimeError(r.stderr)
        self.ruta, self.numero = ruta, numero
        s = _leer(ruta / "private-session.json")
        self.base, self.secret, self.env = s["base"], s["secret"], s["env"]
        self.login()

    def login(self) -> None:
        req = urllib.request.Request(self.base + "/auth/desktop-login", headers={"X-MolDesign-Launch": self.secret})
        with urllib.request.urlopen(req, timeout=120) as r:
            self.token = json.load(r)["access_token"]

    def evaluar(self, smiles: str, semilla: int, nombre: str, pdb: str = PDB_ID, cadena: str = CADENA) -> dict[str, Any]:
        cal = _cal()
        self.login()
        be = cal.Backend(self.ruta)
        be.base, be.token = self.base, self.token
        return be.evaluar(smiles, pdb, cadena, semilla, nombre)

    def parar(self) -> None:
        subprocess.run(["node", str(AQUI / "capsula.mjs"), str(RAIZ), "D:/moldesign-build", str(self.ruta), str(self.numero), "down"],
                       capture_output=True, text=True)


def comprobar_corrida(raw: dict[str, Any], esperado: dict[str, Any], semilla: int) -> list[str]:
    """Desviaciones de una corrida respecto de lo congelado. Vacío = sin deriva."""
    res = raw["resultado"]
    dp = res.get("docking_protocol") or {}
    prov = dp.get("execution_provenance") or {}
    estado = res.get("ligand_state") or {}
    d = []
    if estado.get("smiles_acoplado") != esperado["smiles_acoplado_esperado"]:
        d.append(f"microestado {estado.get('smiles_acoplado')} != {esperado['smiles_acoplado_esperado']}")
    if prov.get("receptor_sha256") != esperado["receptor_sha256"]:
        d.append(f"receptor {prov.get('receptor_sha256')} != {esperado['receptor_sha256']}")
    if dp.get("seed") != semilla:
        d.append(f"semilla efectiva {dp.get('seed')} != {semilla}")
    if (dp.get("exhaustiveness"), dp.get("num_poses")) != (8, 9):
        d.append(f"exhaustividad/poses {dp.get('exhaustiveness')}/{dp.get('num_poses')}")
    if res.get("vina_version") != "1.2.7":
        d.append(f"Vina {res.get('vina_version')}")
    if prov.get("cpu") != CPU_POR_PROCESO:
        d.append(f"cpu {prov.get('cpu')} != {CPU_POR_PROCESO}")
    return d


def trabajos(fase: str, protocolo: dict) -> list[dict[str, Any]]:
    panel = list(csv.DictReader((ENTRADA / "panel_congelado.csv").open(encoding="utf-8")))
    cristal = protocolo["verificacion"]["ligando_cristal"]
    if fase == "pose":
        return [{"id": f"redock-s{s}", "smiles": cristal["smiles_entrada"], "semilla": s,
                 "smiles_acoplado_esperado": cristal["smiles_acoplado_esperado"]} for s in SEMILLAS_REDOCKING]
    filas = [p for p in panel if (p["rol"] == "primario") == (fase == "panel")]
    return [{"id": f"panel-{p['padre']}", "smiles": p["smiles"], "semilla": SEMILLA_PANEL,
             "smiles_acoplado_esperado": p["smiles_acoplado_esperado"]} for p in sorted(filas, key=lambda x: x["padre"])]


def cpu_horas(raiz_trabajo: Path) -> float:
    total = 0.0
    for t in raiz_trabajo.glob("*/shard-*/*.terminal.json"):
        r = _leer(t)
        total += sum(i.get("segundos", 0) for i in r.get("intentos", [])) * CPU_POR_PROCESO / 3600
    return total


def ejecutar_trabajos(capsula, jobs: list[dict[str, Any]], salida: Path, receptor_sha: str, guardia, tope_h: float,
                      escribir_raw=None) -> dict[str, int]:
    """Bucle reanudable. Nunca sobrescribe un registro terminal ni un crudo."""
    salida.mkdir(parents=True, exist_ok=True)
    hechos = fallos = 0
    for job in jobs:
        terminal = salida / f"{job['id']}.terminal.json"
        if terminal.exists():
            continue
        guardia()
        horas = cpu_horas(salida.parent.parent)
        if horas >= tope_h:
            _escribir(salida.parent.parent / "PARADA_PRESUPUESTO.json", {"cpu_core_h": horas, "tope": tope_h, "en": _ahora()})
            raise RuntimeError(f"tope de {tope_h} CPU-core-h alcanzado ({horas:.1f}); resultado INCONCLUSIVE")
        reg: dict[str, Any] = {"id": job["id"], "smiles": job["smiles"], "semilla": job["semilla"], "intentos": []}
        for n in range(1, INTENTOS + 1):
            t0 = time.monotonic()
            try:
                raw = capsula.evaluar(job["smiles"], job["semilla"], job["id"])
            except Exception as exc:  # noqa: BLE001 - se registra y se cuenta
                reg["intentos"].append({"n": n, "error": f"{type(exc).__name__}: {str(exc)[:800]}",
                                        "segundos": round(time.monotonic() - t0, 1)})
                continue
            crudo = salida / f"{job['id']}-intento{n}.json.gz"
            if crudo.exists():
                raise RuntimeError(f"se niega a sobrescribir {crudo.name}")
            data = gzip.compress(json.dumps(raw, ensure_ascii=False, allow_nan=False).encode("utf-8"), mtime=0)
            (escribir_raw or (lambda p, d: p.write_bytes(d)))(crudo, data)
            deriva = comprobar_corrida(raw, {"smiles_acoplado_esperado": job["smiles_acoplado_esperado"],
                                             "receptor_sha256": receptor_sha}, job["semilla"])
            reg["intentos"].append({"n": n, "ok": not deriva, "segundos": raw["segundos"], "crudo": crudo.name,
                                    "crudo_sha256": _sha_b(data), "task_id": raw["task_id"]})
            if deriva:
                reg.update({"estado": "DERIVA", "desviaciones": deriva, "registrado_en": _ahora()})
                _escribir(terminal, reg)
                _escribir(salida.parent.parent / "STOP.json", {"id": job["id"], "desviaciones": deriva, "en": _ahora()})
                raise RuntimeError(f"deriva en {job['id']}: {deriva}")
            reg.update({"estado": "SUCCESS", "task_id": raw["task_id"], "crudo": crudo.name, "crudo_sha256": _sha_b(data)})
            break
        else:
            reg["estado"] = "FALLO"
            fallos += 1
        reg["registrado_en"] = _ahora()
        _escribir(terminal, reg)
        hechos += 1
        print(job["id"], reg["estado"], reg["intentos"][-1].get("segundos"), flush=True)
    return {"hechos": hechos, "fallos": fallos}


def _guardia_git(congelado: str):
    def g() -> None:
        if (TRABAJO / "STOP.json").exists():
            raise RuntimeError("STOP.json existe")
        if _git("rev-parse", "HEAD") != congelado or _git("status", "--porcelain", "--untracked-files=no"):
            raise RuntimeError("el worktree congelado cambió")
    return g


def cmd_ejecutar(args: argparse.Namespace) -> int:
    protocolo = _leer(ENTRADA / "protocolo.json")
    for k, p in {"panel_congelado.csv": ENTRADA / "panel_congelado.csv", "cal_d01r4.py": Path(__file__),
                 "rho_peor.py": AQUI / "rho_peor.py", "capsula.mjs": AQUI / "capsula.mjs",
                 "calibracion_receptor.py": RAIZ / "scripts" / "calibracion_receptor.py"}.items():
        if protocolo["hashes"][k] != _sha(p):
            raise SystemExit(f"{k} cambió desde que se congeló el protocolo")
    if args.fase in ("panel", "sens"):
        puerta = _leer(EXP / "puerta_pose.json") if (EXP / "puerta_pose.json").exists() else None
        if not puerta or puerta["decision"] != "GO":
            raise SystemExit("la puerta de pose no está superada: no se acopla el panel")
    if args.fase == "sens" and cpu_horas(TRABAJO) and not list((TRABAJO / "panel").glob("shard-*/*.terminal.json")):
        raise SystemExit("la sensibilidad va después del panel")
    jobs = trabajos(args.fase, protocolo)
    jobs = [j for i, j in enumerate(jobs) if i % args.shards == args.shard - 1]
    congelado = _git("rev-parse", "HEAD")
    sesion = AQUI / "tmp" / f"c-{args.fase[0]}{args.shard}-{time.time_ns():x}"
    capsula = Capsula(sesion, args.shard)
    salida = TRABAJO / args.fase / f"shard-{args.shard}"
    try:
        cat = next(e for e in _leer(RAIZ / "curated_targets.json") if e["pdb_id"] == PDB_ID)
        previo = _receptor_preparado(sesion, cat, env=capsula.env)
        if previo["sha256"] != protocolo["receptor"]["receptor_preparado_sha256"]:
            raise RuntimeError(f"deriva del receptor preparado en la cápsula: {previo['sha256']} != "
                               f"{protocolo['receptor']['receptor_preparado_sha256']}")
        r = ejecutar_trabajos(capsula, jobs, salida, protocolo["receptor"]["receptor_preparado_sha256"],
                              _guardia_git(congelado), TOPE_CPU_H)
    finally:
        capsula.parar()
    print(json.dumps(r))
    return 0


# ── Analizar ─────────────────────────────────────────────────────────────────

def _corridas(fase: str) -> dict[str, dict[str, Any]]:
    return {r["id"]: r for r in (_leer(p) for p in sorted((TRABAJO / fase).glob("shard-*/*.terminal.json")))}


def _extraer_pose(raw: dict[str, Any], ref_n=None):
    """Top-1, su energía y su validez física. El RMSD sólo se calcula frente al cristal (ref_n) en el redocking."""
    from rdkit.Chem import rdMolAlign
    cal = _cal()
    mol, e, casa = cal._top1(raw)
    res = raw["resultado"]
    top = next((p for p in (res.get("structural_evidence") or {}).get("poses") or [] if p.get("rank") == 1), {})
    rmsd = float(rdMolAlign.CalcRMS(cal._neutro_sin_h(mol), ref_n)) if ref_n is not None else None
    return {"E_kcal": e, "rmsd_A": rmsd, "casa_sdf_pdbqt": casa, "estado_fisico": top.get("status"),
            "valida": top.get("status") == "passed", "engine": top.get("engine")}


def cmd_analizar(args: argparse.Namespace) -> int:
    protocolo = _leer(ENTRADA / "protocolo.json")
    cal = _cal()
    cristal = protocolo["verificacion"]["ligando_cristal"]
    ref_n = cal._neutro_sin_h(_cristal_mol(cristal["smiles_entrada"]))
    if args.fase == "pose":
        return _analizar_pose(protocolo, ref_n)
    import rho_peor as rp
    import numpy as np

    puerta = _leer(EXP / "puerta_pose.json")
    corridas = _corridas("panel")
    corr_s = _corridas("sens")
    panel = {p["padre"]: p for p in csv.DictReader((ENTRADA / "panel_congelado.csv").open(encoding="utf-8"))}
    filas, fallos, desviaciones = [], [], []

    def rec(padre: str, fuente: dict[str, dict[str, Any]]):
        c = fuente.get(f"panel-{padre}")
        if not c or c["estado"] != "SUCCESS":
            fallos.append({"id": f"panel-{padre}", "estado": (c or {}).get("estado"), "intentos": (c or {}).get("intentos")})
            return None
        raw = json.loads(gzip.decompress((TRABAJO / ("panel" if padre != ID_SENS else "sens") /
                                          f"shard-{_shard_de(fuente, c['id'], padre)}" / c["crudo"]).read_bytes()))
        x = _extraer_pose(raw)
        if not x["casa_sdf_pdbqt"]:
            desviaciones.append({"id": c["id"], "desviacion": "el SDF top-1 no casa con el PDBQT del rank 1"})
        return x

    q, ki, pki, padres = [], [], [], []
    for padre, p in panel.items():
        if p["rol"] != "primario":
            continue
        x = rec(padre, corridas)
        if x is None:
            continue
        q.append(-x["E_kcal"]); ki.append(p["ki_nM"]); pki.append(float(p["pki"])); padres.append(padre)
        filas.append({"id": f"panel-{padre}", "tipo": "panel", "padre": padre, "ki_nM": p["ki_nM"], "pki": float(p["pki"]),
                      "E_kcal": x["E_kcal"], "Q": -x["E_kcal"], "valida_top1": x["valida"]})
    n = len(q)
    r: dict[str, Any] = {"n_evaluados": n, "fallos_persistentes": len(fallos), "desviaciones": desviaciones}
    horas = cpu_horas(TRABAJO)
    if puerta["decision"] != "GO":
        decision, razon = "NO_GO", "puerta de pose no superada"
    elif (EXP / "_work" / "PARADA_PRESUPUESTO.json").exists() or horas >= TOPE_CPU_H:
        decision, razon = "INCONCLUSIVE", f"tope de {TOPE_CPU_H} CPU-core-h"
    elif n < MIN_PADRES:
        decision, razon = "EXPLORATORIO", f"{n} padres evaluados (< {MIN_PADRES}); sin promoción"
    else:
        panel_p = rp.Panel(ki)
        rho = rp.spearman(q, pki)
        peor = rp.rho_peor(panel_p, q)
        asign, _ = rp.asignacion_peor(panel_p, q)
        chk = rp.rho_asignacion(ki, q, asign)
        comp = rp.pares_comparables(ki)
        conc = rp.concordancia(comp, q)
        ic = rp.bootstrap(ki, q, progreso=lambda k: print("bootstrap", k, flush=True))
        r.update({"rho_Q_pKi": rho, "rho_E_pKi": -rho, "rho_peor": peor,
                  "rho_peor_asignacion_verifica": chk, "n_con_b1_en_la_peor_asignacion": int(sum(asign)),
                  "ic95_rho": ic["rho"], "ic95_rho_peor": ic["rho_peor"], "bootstrap": {k: ic[k] for k in ("n_replicas", "descartadas", "semilla")},
                  "p2": {"concordancia": conc, "pares_comparables": int(comp.sum()), "pares_totales": n * (n - 1) // 2,
                         "ic95": ic["concordancia"]}})
        sens = {}
        x = rec(ID_SENS, corr_s)
        if x is not None:
            qs = -x["E_kcal"]
            k1, k2 = protocolo_ki_sens(panel)
            for nombre, kk in (("con_4-31", k1), ("con_4-118", k2), ("con_la_mediana_de_ambos", math.sqrt(k1 * k2))):
                ki2, q2 = ki + [str(kk)], q + [qs]
                pk2 = pki + [9.0 - math.log10(kk)]
                sens[nombre] = {"n": len(q2), "ki_nM": kk, "rho": rp.spearman(q2, pk2),
                                "rho_peor": rp.rho_peor(rp.Panel(ki2), q2)}
        r["p2_sensibilidades"] = sens
        ok_ic = ic["rho"][0] > 0 and ic["rho_peor"][0] > 0
        limpio = not fallos and not desviaciones
        if ok_ic and limpio:
            decision, razon = "GO", "límite inferior del IC95 % de rho y de rho_peor > 0, sin fallos ni desviaciones"
        else:
            decision = "NO_GO"
            razon = ("IC95 inferior de rho %.4f y de rho_peor %.4f; fallos %d, desviaciones %d"
                     % (ic["rho"][0], ic["rho_peor"][0], len(fallos), len(desviaciones)))
    r.update({"decision": decision, "razon": razon, "cpu_core_h": round(horas, 2), "puerta_pose": puerta["decision"]})
    _escribir(EXP / "metrics.json", {"experimento": EXP.name, "analizado_en": _ahora(), "protocolo_sha256": _sha(ENTRADA / "protocolo.json"), **r})
    with (EXP / "per_complex.jsonl").open("w", encoding="utf-8", newline="\n") as fh:
        for f in filas:
            fh.write(json.dumps(f, ensure_ascii=False) + "\n")
    with (EXP / "failures.jsonl").open("w", encoding="utf-8", newline="\n") as fh:
        for f in fallos:
            fh.write(json.dumps(f, ensure_ascii=False) + "\n")
    print(json.dumps(r, indent=2, ensure_ascii=False))
    return 0


def protocolo_ki_sens(panel: dict[str, dict[str, str]]) -> tuple[float, float]:
    a, b = panel[ID_SENS]["ki_nM"].split("|")
    return float(a), float(b)


def _shard_de(fuente: dict, ident: str, padre: str) -> int:
    base = TRABAJO / ("sens" if padre == ID_SENS else "panel")
    for p in base.glob(f"shard-*/{ident}.terminal.json"):
        return int(p.parent.name.split("-")[1])
    raise FileNotFoundError(ident)


def _analizar_pose(protocolo: dict, ref_n) -> int:
    corridas = _corridas("pose")
    semillas, desv = [], []
    for s in SEMILLAS_REDOCKING:
        c = corridas.get(f"redock-s{s}")
        if not c or c["estado"] != "SUCCESS":
            semillas.append({"semilla": s, "estado": (c or {}).get("estado", "SIN CORRER"), "rmsd_A": None, "valida": False})
            continue
        shard = next((p.parent.name for p in (TRABAJO / "pose").glob(f"shard-*/{c['id']}.terminal.json")))
        raw = json.loads(gzip.decompress((TRABAJO / "pose" / shard / c["crudo"]).read_bytes()))
        x = _extraer_pose(raw, ref_n)
        if not x["casa_sdf_pdbqt"]:
            desv.append({"id": c["id"], "desviacion": "SDF top-1 no casa con el PDBQT"})
        semillas.append({"semilla": s, "estado": "SUCCESS", "rmsd_A": round(x["rmsd_A"], 3), "E_kcal": x["E_kcal"],
                         "valida": x["valida"], "estado_fisico": x["estado_fisico"]})
    ok = [s for s in semillas if s["rmsd_A"] is not None and s["rmsd_A"] <= RMSD_MAX_A]
    valida = bool(ok) and all(s["valida"] for s in ok)
    go = len(ok) >= SEMILLAS_OK_MINIMAS and valida and not desv
    out = {"experimento": EXP.name, "analizado_en": _ahora(), "semillas": semillas, "semillas_rmsd_ok": len(ok),
           "posebusters_valida_en_las_que_cumplen": valida, "desviaciones": desv, "decision": "GO" if go else "NO_GO",
           "si_falla": "NO_GO; no se acopla el panel ni se prueba otra estructura"}
    _escribir(EXP / "puerta_pose.json", out)
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


def cmd_piloto(args: argparse.Namespace) -> int:
    """Transporte real con un caso ajeno al experimento (otro receptor, otra molécula): ningún score de 8T69."""
    sesion = Path(args.salida) / f"c-piloto-{time.time_ns():x}"
    capsula = Capsula(sesion, 1)
    try:
        raw = capsula.evaluar("CC(=O)OC1=CC=CC=C1C(=O)O", 42, "piloto-aspirina", pdb="3F75", cadena="A")
    finally:
        capsula.parar()
    res = raw["resultado"]
    dp = res["docking_protocol"]
    prov = dp["execution_provenance"]
    print(json.dumps({"segundos": raw["segundos"], "vina": res.get("vina_version"), "cpu": prov.get("cpu"),
                      "seed": dp.get("seed"), "exhaustiveness": dp.get("exhaustiveness"), "num_poses": dp.get("num_poses"),
                      "microestado": (res.get("ligand_state") or {}).get("smiles_acoplado"),
                      "receptor_sha256": prov.get("receptor_sha256"), "poses_sdf_bytes": len(raw["poses_sdf"]),
                      "top1_status": next((p.get("status") for p in (res.get("structural_evidence") or {}).get("poses") or []
                                           if p.get("rank") == 1), None)}, indent=2))
    assert res.get("vina_version") == "1.2.7" and prov.get("cpu") == CPU_POR_PROCESO and dp.get("seed") == 42
    return 0


# ── Autotest con transporte simulado ─────────────────────────────────────────

class _CapsulaSimulada:
    def __init__(self, deriva_en: str | None = None, falla: set[str] | None = None):
        self.deriva_en, self.falla, self.llamadas = deriva_en, falla or set(), []

    def evaluar(self, smiles, semilla, nombre):
        self.llamadas.append(nombre)
        if nombre in self.falla:
            raise RuntimeError("fallo simulado")
        sha = "bad" if nombre == self.deriva_en else "RECEPTOR"
        return {"task_id": f"t-{nombre}", "segundos": 10.0, "resultado": {
            "vina_version": "1.2.7", "ligand_state": {"smiles_acoplado": "ACOPLADO"},
            "docking_protocol": {"seed": semilla, "exhaustiveness": 8, "num_poses": 9,
                                 "execution_provenance": {"receptor_sha256": sha, "cpu": 4}}}}


def cmd_selftest(_: argparse.Namespace) -> int:
    import tempfile
    import numpy as np
    jobs = [{"id": f"panel-P{i}", "smiles": "C", "semilla": 42, "smiles_acoplado_esperado": "ACOPLADO"} for i in range(4)]
    nada = lambda: None
    with tempfile.TemporaryDirectory() as t:
        base = Path(t) / "panel" / "shard-1"
        # 1. corre, registra y es reanudable sin repetir
        c = _CapsulaSimulada()
        r = ejecutar_trabajos(c, jobs, base, "RECEPTOR", nada, TOPE_CPU_H)
        assert r == {"hechos": 4, "fallos": 0} and len(c.llamadas) == 4
        c2 = _CapsulaSimulada()
        assert ejecutar_trabajos(c2, jobs, base, "RECEPTOR", nada, TOPE_CPU_H)["hechos"] == 0 and not c2.llamadas
        # 2. se niega a sobrescribir un crudo
        (base / "panel-P0.terminal.json").unlink()
        try:
            ejecutar_trabajos(_CapsulaSimulada(), jobs, base, "RECEPTOR", nada, TOPE_CPU_H)
            raise AssertionError("debía negarse a sobrescribir")
        except RuntimeError as e:
            assert "sobrescribir" in str(e)
    with tempfile.TemporaryDirectory() as t:
        # 3. un fallo se reintenta una vez y, si persiste, queda registrado como FALLO sin parar la campaña
        base = Path(t) / "panel" / "shard-1"
        c = _CapsulaSimulada(falla={"panel-P1"})
        r = ejecutar_trabajos(c, jobs, base, "RECEPTOR", nada, TOPE_CPU_H)
        assert r["fallos"] == 1 and c.llamadas.count("panel-P1") == INTENTOS
        assert _leer(base / "panel-P1.terminal.json")["estado"] == "FALLO"
    with tempfile.TemporaryDirectory() as t:
        # 4. una deriva del receptor para la campaña y deja STOP
        base = Path(t) / "panel" / "shard-1"
        try:
            ejecutar_trabajos(_CapsulaSimulada(deriva_en="panel-P2"), jobs, base, "RECEPTOR", nada, TOPE_CPU_H)
            raise AssertionError("debía parar")
        except RuntimeError as e:
            assert "deriva" in str(e)
        assert (Path(t) / "STOP.json").exists() and not (base / "panel-P3.terminal.json").exists()
    with tempfile.TemporaryDirectory() as t:
        # 5. el tope de presupuesto para y deja constancia
        base = Path(t) / "panel" / "shard-1"
        try:
            ejecutar_trabajos(_CapsulaSimulada(), jobs, base, "RECEPTOR", nada, 10 * CPU_POR_PROCESO / 3600 * 2)
            raise AssertionError("debía parar por presupuesto")
        except RuntimeError as e:
            assert "tope" in str(e)
        assert (Path(t) / "PARADA_PRESUPUESTO.json").exists()
    # 6. el RMSD simétrico sin alinear distingue una pose protonada del cristal de la misma desplazada
    from rdkit import Chem
    from rdkit.Chem import AllChem, rdMolAlign
    smi = _smiles_ligando_cristal()
    ref_n = _cal()._neutro_sin_h(_cristal_mol(smi))
    prot = Chem.AddHs(Chem.MolFromSmiles(smi.replace("N1", "[NH+]1", 1) if "N1" in smi else smi))
    mol = Chem.AddHs(Chem.MolFromSmiles("COc1cc2CC[NH+]3C[C@@H](CC(C)C)C(=O)C[C@@H]3c2cc1OC"))
    assert AllChem.EmbedMolecule(mol, randomSeed=1) == 0
    neutro = _cal()._neutro_sin_h(mol)
    rms = rdMolAlign.CalcRMS(neutro, ref_n)       # no debe lanzar por la carga del N protonado
    assert math.isfinite(rms)
    # 7. la decisión estadística: IC inferiores positivos -> pasa; señal nula -> no
    import rho_peor as rp
    rng = np.random.default_rng(5)
    ki = [str(round(float(v), 1)) for v in np.exp(rng.uniform(0, 5, 60))]
    pk = [9 - math.log10(float(k)) for k in ki]
    fuerte = [p + rng.normal(0, 0.3) for p in pk]
    nulo = list(rng.normal(8, 1, 60))
    a = rp.bootstrap(ki, fuerte, n_rep=300)
    b = rp.bootstrap(ki, nulo, n_rep=300)
    assert a["rho"][0] > 0 and a["rho_peor"][0] > 0, a
    assert not (b["rho"][0] > 0 and b["rho_peor"][0] > 0), b
    print("Autotest PASSED: reanuda sin repetir, no sobrescribe, reintento único, deriva y presupuesto paran, "
          "RMSD con N protonado, IC de P1 separan señal de ruido")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 2)[1])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("selftest"); s.set_defaults(func=cmd_selftest)
    s = sub.add_parser("piloto"); s.add_argument("--salida", required=True); s.set_defaults(func=cmd_piloto)
    s = sub.add_parser("congelar"); s.add_argument("--datos", required=True); s.set_defaults(func=cmd_congelar)
    s = sub.add_parser("ejecutar")
    s.add_argument("--fase", choices=["pose", "panel", "sens"], required=True)
    s.add_argument("--shard", type=int, default=1); s.add_argument("--shards", type=int, default=1)
    s.set_defaults(func=cmd_ejecutar)
    s = sub.add_parser("analizar"); s.add_argument("--fase", choices=["pose", "final"], default="final"); s.set_defaults(func=cmd_analizar)
    a = ap.parse_args()
    raise SystemExit(a.func(a))
