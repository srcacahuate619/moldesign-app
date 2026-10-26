r"""ABS-TR-01, validez de la decisión: la pestaña Preparación frente al panel ciego de revisores LLM.

Los 29 sistemas reales de ABS-TR-01 (los mismos depósitos que juzgaron los revisores) se evalúan con el producto
por su API, como lo haría un usuario con un receptor del catálogo: el ligando del cristal (SMILES del CCD), Vina
1.2.7 con la configuración de un caso, y después la auditoría de Preparación de esa corrida. Lo que se compara es
la decisión de Preparación (detenerse, avisar, seguir) con la de los revisores. Las reglas están en
`entrada/REGISTRO_PREVIO.md` y se congelan con `congelar` antes de cualquier salida del producto.

Uso, con el Python embebido, desde el worktree congelado:

    python scripts/abs_tr_01/abs_tr_01.py congelar      # referencia de los revisores, CCD y microestados
    python scripts/abs_tr_01/abs_tr_01.py ejecutar --shard 1 --shards 2
    python scripts/abs_tr_01/abs_tr_01.py analizar
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

AQUI = Path(__file__).resolve().parent
RAIZ = next(p for p in AQUI.parents if (p / "curated_targets.json").is_file())
EXP = RAIZ / "scripts" / "artifacts_science" / "ABS-TR-01-VALIDEZ"
ENTRADA = EXP / "entrada"
TRABAJO = EXP / "_work"
CCD_MET01R1 = RAIZ / "scripts" / "met01r1" / "ccd"

AUD = Path(r"D:\moldesign-audits\ABS_TR_01")
MAPA_R1 = AUD / "registro" / "mapa_privado.json"
MAPA_R2 = AUD / "registro_R2" / "mapa_privado_r2.json"
RAIZ_R1 = Path(r"E:\ABS-TR-01")
RAIZ_R2 = Path(r"E:\ABS-TR-01-R2")
# (nombre, ronda, carpeta). Opus 5.5 no entregó la ronda 2: por decisión del propietario (2026-10-22) cuenta su
# ronda 1, que juzgó los mismos 29 depósitos con tres estados (sin REVISAR).
REVISORES = (("astra6", "R2", "astra6"), ("sol6.1", "R2", "sol6,1"), ("glm5.3", "R2", "glm5.3"),
             ("step5preview", "R2", "step5preview"), ("opus5.5", "R1", "opus5.5"))
CONTROLES = [f"C{i:02d}" for i in range(1, 11)]
# Requisitos de Preparación que miran lo mismo que cada control del panel. Análisis secundario: hay controles que
# Preparación sólo registra (caja, cadenas) o no mira (completitud del ligando del cristal).
CORRESPONDENCIA = {
    "C01": ["receptor.huecos"],
    "C02": ["receptor.cadenas_truncadas"],
    "C03": ["receptor.altlocs"],
    "C04": ["receptor.cadenas", "receptor.cadenas_excluidas"],
    "C05": ["entorno.metales_cofactores", "entorno.otras_especies"],
    "C06": ["entorno.aguas"],
    "C07": ["ligando.covalente"],
    "C08": ["ligando.identidad", "ligando.estereoquimica", "ligando.tautomero"],
    "C09": ["receptor.protonacion"],
    "C10": ["receptor.caja"],
}
SEMILLA = 42
CPU_POR_PROCESO = 4
TOPE_CPU_H = 30.0
INTENTOS = 2
MAX_FALLOS = 3
OBJETIVO_FB = 0.10

sys.path.insert(0, str(RAIZ / "scripts"))
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

def _sistemas() -> list[dict[str, Any]]:
    """Los 29 sistemas, con su id en cada ronda, su entrada del catálogo y la ficha que vieron los revisores."""
    r1 = {i["pdb"]: i["id"] for i in _leer(MAPA_R1)["items"] if i["grupo"] == "sistema"}
    cat = {e["pdb_id"].upper(): e for e in _leer(RAIZ / "curated_targets.json")}
    out = []
    for i in _leer(MAPA_R2)["items"]:
        if i["grupo"] != "sistema":
            continue
        e = cat[i["pdb"]]
        deposito = RAIZ / "data" / "targets" / f"{i['pdb']}.pdb.gz"
        if _sha(deposito) != i["deposito_sha256"]:
            raise SystemExit(f"{i['pdb']}: el depósito del catálogo no es el que vieron los revisores")
        ficha = _leer(RAIZ_R2 / "_paquete" / i["id"] / "ficha.json")
        out.append({"id_r2": i["id"], "id_r1": r1[i["pdb"]], "pdb": i["pdb"], "cadena": e["chain"],
                    "site_chains": e.get("site_chains"), "site_ligand": e["site_ligand"],
                    "ligando_de_referencia": ficha["ligando_de_referencia"], "deposito_sha256": i["deposito_sha256"]})
    if len(out) != 29:
        raise SystemExit(f"se esperaban 29 sistemas, hay {len(out)}")
    return out


def _referencia(sistemas: list[dict[str, Any]]) -> dict[str, Any]:
    """Estados por control y veredicto de cada revisor en cada sistema (sin la evidencia en texto)."""
    fuentes, filas = {}, {s["pdb"]: {} for s in sistemas}
    for nombre, ronda, carpeta in REVISORES:
        ruta = (RAIZ_R2 if ronda == "R2" else RAIZ_R1) / carpeta / "respuestas.json"
        fuentes[nombre] = {"ronda": ronda, "archivo": str(ruta), "sha256": _sha(ruta)}
        items = {it["id"]: it for it in _leer(ruta)["items"]}
        for s in sistemas:
            it = items[s["id_r2"] if ronda == "R2" else s["id_r1"]]
            filas[s["pdb"]][nombre] = {"veredicto": it["veredicto"],
                                       "controles": {k: it["controles"][k]["estado"] for k in CONTROLES}}
    return {"revisores": fuentes, "sistemas": filas}


def _ccd(codigos: list[str]) -> dict[str, Any]:
    """SMILES de cada ligando desde su definición del CCD (archivada con URL, fecha y SHA-256), como MET-01."""
    from Bio.PDB.MMCIF2Dict import MMCIF2Dict
    from rdkit import Chem
    carpeta = ENTRADA / "ccd"
    carpeta.mkdir(parents=True, exist_ok=True)
    filas = {}
    for code in codigos:
        ruta, sello = carpeta / f"{code}.cif", carpeta / f"{code}.source.json"
        if not ruta.exists() and (CCD_MET01R1 / f"{code}.cif").exists():
            ruta.write_bytes((CCD_MET01R1 / f"{code}.cif").read_bytes())
            sello.write_bytes((CCD_MET01R1 / f"{code}.source.json").read_bytes())
        if not ruta.exists():
            url = f"https://files.rcsb.org/ligands/download/{code}.cif"
            with urllib.request.urlopen(url, timeout=60) as r:
                datos = r.read()
            ruta.write_bytes(datos)
            _escribir(sello, {"url": url, "downloaded_at": _ahora(), "sha256": _sha_b(datos)})
        d = MMCIF2Dict(str(ruta))
        desc = [dict(zip(["type", "program", "version", "smiles"], v)) for v in zip(
            *(d["_pdbx_chem_comp_descriptor." + x] for x in ["type", "program", "program_version", "descriptor"]))
            if v[0] == "SMILES_CANONICAL"]
        desc.sort(key=lambda v: (0 if v["program"].startswith("OpenEye") else 1, v["program"], v["version"], v["smiles"]))
        elegido = next(v for v in desc if Chem.MolFromSmiles(v["smiles"]) is not None)
        mol = Chem.MolFromSmiles(elegido["smiles"])
        filas[code] = {"source": _leer(sello), "descriptor": elegido,
                       "smiles": Chem.MolToSmiles(mol, isomericSmiles=True), "atomos_pesados": mol.GetNumHeavyAtoms()}
    return filas


_SONDA_VALIDADOR = r"""
import json, sys
sys.path[:0] = [sys.argv[1]]
from chem.validator import validate_smiles_or_raise
out = {}
for s in json.loads(sys.stdin.read()):
    try:
        validate_smiles_or_raise(s)
        out[s] = None
    except Exception as e:
        out[s] = f"{type(e).__name__}: {e}"
print(json.dumps(out, ensure_ascii=False))
"""


def _rechazos_del_validador(smiles: list[str], datos: Path) -> dict[str, str | None]:
    """Qué SMILES rechaza el validador del producto antes de prepararlos (p. ej., elementos sin parámetros de Vina)."""
    g = _cal()._arnes()
    datos.mkdir(parents=True, exist_ok=True)
    env = g.entorno_runtime(datos, datos / "vina-tmp")
    r = subprocess.run([sys.executable, "-c", _SONDA_VALIDADOR, str(RAIZ / "backend")], input=json.dumps(smiles),
                       capture_output=True, text=True, env=env, cwd=str(RAIZ / "backend"), encoding="utf-8")
    if r.returncode:
        raise SystemExit(f"la sonda del validador falló:\n{r.stderr[-3000:]}")
    return json.loads(r.stdout.strip().splitlines()[-1])


def cmd_congelar(args: argparse.Namespace) -> int:
    if TRABAJO.exists() and any(TRABAJO.glob("corridas/*/*.terminal.json")):
        raise SystemExit("ya hay corridas: no se vuelve a congelar")
    if _git("status", "--porcelain", "--untracked-files=no"):
        raise SystemExit("el árbol tiene cambios sin commitear; congela sobre un commit limpio")
    registro = ENTRADA / "REGISTRO_PREVIO.md"
    if not registro.exists():
        raise SystemExit("falta entrada/REGISTRO_PREVIO.md")
    sistemas = _sistemas()
    referencia = _referencia(sistemas)
    ccd = _ccd(sorted({s["site_ligand"] for s in sistemas}))
    for s in sistemas:
        c = ccd[s["site_ligand"]]
        s["smiles"] = c["smiles"]
        s["ligando_completo_en_el_deposito"] = s["ligando_de_referencia"]["atomos_pesados"] == c["atomos_pesados"]
    cal = _cal()
    datos = Path(args.datos)
    rechazos = _rechazos_del_validador(sorted({s["smiles"] for s in sistemas}), datos / "validador")
    entradas = sorted({s["smiles"] for s in sistemas if rechazos[s["smiles"]] is None})
    a = cal._microestados(entradas, datos / "sonda-1")
    b = cal._microestados(entradas, datos / "sonda-2")
    distintos = [x for x in entradas if a[x] != b[x]]
    if distintos:
        raise SystemExit(f"microestado no reproducible entre procesos en {len(distintos)}: {distintos[:3]}")
    for s in sistemas:
        s["rechazo_del_validador"] = rechazos[s["smiles"]]
        s["smiles_acoplado_esperado"] = a[s["smiles"]]["smiles_acoplado"] if s["smiles"] in a else None
        s["carga_esperada"] = a[s["smiles"]]["carga"] if s["smiles"] in a else None
    _escribir(ENTRADA / "referencia_revisores.json", referencia)
    _escribir(ENTRADA / "ccd.json", ccd)
    _escribir(ENTRADA / "sistemas.json", sistemas)
    protocolo = {
        "experimento": EXP.name, "congelado_en": _ahora(), "git_head": _git("rev-parse", "HEAD"),
        "registro_previo_sha256": _sha(registro),
        "mapas": {"r1_sha256": _sha(MAPA_R1), "r2_sha256": _sha(MAPA_R2)},
        "ruta": "catálogo (Demostración), POST /evaluation/preflight → submit → result → POST /evaluation/dossier/{id}/preparacion",
        "configuracion_del_caso": cal.CONFIG_CASO, "semilla": SEMILLA, "cpu_por_proceso": CPU_POR_PROCESO,
        "tope_cpu_core_h": TOPE_CPU_H, "intentos": INTENTOS, "max_fallos_de_infraestructura": MAX_FALLOS,
        "objetivo_falso_bloqueo": OBJETIVO_FB, "correspondencia_controles": CORRESPONDENCIA,
        "hashes": {"abs_tr_01.py": _sha(Path(__file__)), "capsula.mjs": _sha(AQUI / "capsula.mjs"),
                   "calibracion_receptor.py": _sha(RAIZ / "scripts" / "calibracion_receptor.py"),
                   "referencia_revisores.json": _sha(ENTRADA / "referencia_revisores.json"),
                   "sistemas.json": _sha(ENTRADA / "sistemas.json"), "ccd.json": _sha(ENTRADA / "ccd.json"),
                   "vina.exe": _sha(RAIZ / "tools" / "vina" / "vina.exe"), "python": sys.version.split()[0]},
    }
    _escribir(ENTRADA / "protocolo.json", protocolo)
    incompletos = [s["pdb"] for s in sistemas if not s["ligando_completo_en_el_deposito"]]
    print(f"congelado: 29 sistemas, {len(ccd)} ligandos del CCD, microestados reproducibles; "
          f"ligando incompleto en el depósito: {incompletos}")
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
        self.base, self.secret = s["base"], s["secret"]
        self.g = _cal()._arnes()
        self.login()

    def login(self) -> None:
        req = urllib.request.Request(self.base + "/auth/desktop-login", headers={"X-MolDesign-Launch": self.secret})
        with urllib.request.urlopen(req, timeout=120) as r:
            self.token = json.load(r)["access_token"]

    def api(self, metodo: str, ruta: str, body: dict | None = None, esperado=(200,), timeout: float = 600) -> dict:
        return self.g._json(self.base, metodo, ruta, body=body, token=self.token, expected=set(esperado), timeout=timeout)

    def evaluar(self, s: dict[str, Any]) -> dict[str, Any]:
        """Preflight → (si no se detiene) submit, espera, resultado y Preparación. Devuelve todo lo que respondió."""
        self.login()
        config = json.loads(json.dumps(_cal().CONFIG_CASO))
        config["stage_params"]["docking"]["seed"] = SEMILLA
        t0 = time.monotonic()
        # Un 400/409/422 del preflight es el producto rechazando la entrada: se detiene ahí, como con un bloqueo técnico.
        codigo, cuerpo, _ = self.g._request(self.base, "POST", "/evaluation/preflight", token=self.token, body={
            "smiles": s["smiles"], "target_pdb_id": s["pdb"], "chain": s["cadena"], "docking_engine": "vina",
            "exhaustiveness": 8, "num_poses": 9, "conformers": 1, "pipeline_config": config},
            expected={200, 400, 409, 422}, timeout=600)
        pre = json.loads(cuerpo)
        raw: dict[str, Any] = {"preflight": pre, "preflight_http": codigo}
        if codigo != 200 or pre.get("technical_blockers"):
            raw.update(detenido_en="preflight", segundos=round(time.monotonic() - t0, 1))
            return raw
        efectiva = pre["effective_config"]
        enviado = self.api("POST", "/evaluation/submit", {
            "smiles": s["smiles"], "target_pdb_id": s["pdb"], "chain": s["cadena"], "molecule_name": f"ABS-{s['pdb']}",
            "grid_center": efectiva["grid_center"], "grid_size": efectiva["grid_size"], "pipeline_config": config,
            "preflight_fingerprint": pre["input_fingerprint"]}, esperado=(202,))
        task = raw["task_id"] = enviado["task_id"]
        estado: dict[str, Any] = {}
        while time.monotonic() - t0 < 3600:
            estado = self.api("GET", f"/evaluation/status/{task}")
            if estado.get("status") in {"SUCCESS", "FAILURE", "REVOKED"}:
                break
            time.sleep(2.0)
        if estado.get("status") != "SUCCESS":
            raise RuntimeError(f"la corrida no terminó en SUCCESS: {str({k: v for k, v in estado.items() if k != 'result'})[:600]}")
        mid = estado["result"]["molecule_id"]
        raw["resultado"] = self.api("GET", f"/evaluation/result/{mid}?task_id={task}")
        g = self.g
        old = g.SMILES
        g.SMILES = s["smiles"]
        try:
            proj = g._projection(task, pre["input_fingerprint"], pre)
        finally:
            g.SMILES = old
        proj["case_id"] = proj["name"] = f"abs-tr-01-{s['pdb']}"
        raw["projection"] = proj
        raw["preparacion"] = self.api("POST", f"/evaluation/dossier/{mid}/preparacion", proj)
        raw["segundos"] = round(time.monotonic() - t0, 1)
        return raw

    def parar(self) -> None:
        subprocess.run(["node", str(AQUI / "capsula.mjs"), str(RAIZ), "D:/moldesign-build", str(self.ruta), str(self.numero), "down"],
                       capture_output=True, text=True)


def comprobar(raw: dict[str, Any], s: dict[str, Any]) -> list[str]:
    """Deriva respecto de lo congelado. Vacío = sin deriva. Una corrida detenida en el preflight no tiene nada que comprobar."""
    if "resultado" not in raw:
        return []
    res = raw["resultado"]
    dp = res.get("docking_protocol") or {}
    prov = dp.get("execution_provenance") or {}
    d = []
    if (res.get("ligand_state") or {}).get("smiles_acoplado") != s["smiles_acoplado_esperado"]:
        d.append(f"microestado {(res.get('ligand_state') or {}).get('smiles_acoplado')} != {s['smiles_acoplado_esperado']}")
    if dp.get("seed") != SEMILLA or (dp.get("exhaustiveness"), dp.get("num_poses")) != (8, 9):
        d.append(f"semilla/exhaustividad/poses {dp.get('seed')}/{dp.get('exhaustiveness')}/{dp.get('num_poses')}")
    if res.get("vina_version") != "1.2.7":
        d.append(f"Vina {res.get('vina_version')}")
    if prov.get("cpu") != CPU_POR_PROCESO:
        d.append(f"cpu {prov.get('cpu')}")
    return d


def cpu_horas() -> float:
    return sum(sum(i.get("segundos", 0) for i in _leer(t).get("intentos", [])) * CPU_POR_PROCESO / 3600
               for t in TRABAJO.glob("corridas/shard-*/*.terminal.json"))


def cmd_ejecutar(args: argparse.Namespace) -> int:
    protocolo = _leer(ENTRADA / "protocolo.json")
    for k, p in {"abs_tr_01.py": Path(__file__), "capsula.mjs": AQUI / "capsula.mjs",
                 "calibracion_receptor.py": RAIZ / "scripts" / "calibracion_receptor.py",
                 "referencia_revisores.json": ENTRADA / "referencia_revisores.json",
                 "sistemas.json": ENTRADA / "sistemas.json", "ccd.json": ENTRADA / "ccd.json"}.items():
        if protocolo["hashes"][k] != _sha(p):
            raise SystemExit(f"{k} cambió desde que se congeló el protocolo")
    congelado = _git("rev-parse", "HEAD")
    sistemas = [s for i, s in enumerate(_leer(ENTRADA / "sistemas.json")) if i % args.shards == args.shard - 1]
    salida = TRABAJO / "corridas" / f"shard-{args.shard}"
    salida.mkdir(parents=True, exist_ok=True)
    capsula = Capsula(AQUI / "tmp" / f"c{args.shard}-{time.time_ns():x}", args.shard)
    try:
        for s in sistemas:
            terminal = salida / f"{s['id_r2']}-{s['pdb']}.terminal.json"
            if terminal.exists():
                continue
            if (TRABAJO / "STOP.json").exists():
                raise RuntimeError("STOP.json existe")
            if _git("rev-parse", "HEAD") != congelado or _git("status", "--porcelain", "--untracked-files=no"):
                raise RuntimeError("el worktree congelado cambió")
            if cpu_horas() >= TOPE_CPU_H:
                _escribir(TRABAJO / "PARADA_PRESUPUESTO.json", {"cpu_core_h": cpu_horas(), "en": _ahora()})
                raise RuntimeError("tope de CPU-core-h alcanzado")
            reg: dict[str, Any] = {"id_r2": s["id_r2"], "pdb": s["pdb"], "intentos": []}
            for n in range(1, INTENTOS + 1):
                t0 = time.monotonic()
                try:
                    raw = capsula.evaluar(s)
                except Exception as exc:  # noqa: BLE001 - se registra y se cuenta
                    reg["intentos"].append({"n": n, "error": f"{type(exc).__name__}: {str(exc)[:800]}",
                                            "segundos": round(time.monotonic() - t0, 1)})
                    continue
                crudo = salida / f"{s['id_r2']}-{s['pdb']}-intento{n}.json.gz"
                if crudo.exists():
                    raise RuntimeError(f"se niega a sobrescribir {crudo.name}")
                data = gzip.compress(json.dumps(raw, ensure_ascii=False, allow_nan=False).encode("utf-8"), mtime=0)
                crudo.write_bytes(data)
                deriva = comprobar(raw, s)
                reg["intentos"].append({"n": n, "segundos": raw["segundos"], "crudo": crudo.name, "crudo_sha256": _sha_b(data)})
                if deriva:
                    reg.update(estado="DERIVA", desviaciones=deriva, registrado_en=_ahora())
                    _escribir(terminal, reg)
                    _escribir(TRABAJO / "STOP.json", {"pdb": s["pdb"], "desviaciones": deriva, "en": _ahora()})
                    raise RuntimeError(f"deriva en {s['pdb']}: {deriva}")
                reg.update(estado="DETENIDO_EN_PREFLIGHT" if raw.get("detenido_en") else "AUDITADO",
                           crudo=crudo.name, crudo_sha256=_sha_b(data))
                break
            else:
                reg["estado"] = "FALLO"
            reg["registrado_en"] = _ahora()
            _escribir(terminal, reg)
            print(s["id_r2"], s["pdb"], reg["estado"], reg["intentos"][-1].get("segundos"), flush=True)
    finally:
        capsula.parar()
    return 0


# ── Analizar ─────────────────────────────────────────────────────────────────

def _cp(k: int, n: int, alfa: float = 0.05) -> tuple[float, float]:
    """Límites unilaterales al 95 % (Clopper-Pearson) de una proporción k/n: (inferior, superior)."""
    from scipy.stats import beta
    inf = 0.0 if k == 0 else float(beta.ppf(alfa, k, n - k + 1))
    sup = 1.0 if k == n else float(beta.ppf(1 - alfa, k + 1, n - k))
    return inf, sup


def decision_del_producto(raw: dict[str, Any]) -> str:
    if raw.get("detenido_en"):
        return "DETENER"
    p = raw["preparacion"]
    if p["estado"] == "BLOQUEADO":
        return "DETENER"
    if p["estado"] == "TRANSFERIBLE" or p.get("solo_rutinaria"):
        return "SEGUIR"
    return "AVISAR"


def estado_por_control(raw: dict[str, Any]) -> dict[str, str]:
    """El estado de Preparación en los requisitos que corresponden a cada control (secundario)."""
    if raw.get("detenido_en"):
        return {k: "SIN_AUDITORIA" for k in CONTROLES}
    p = raw["preparacion"]
    claves = {r["clave"] for b in p["bloques"] for r in b["requisitos"]}
    bloq, rev, rut = set(p["bloqueantes"]), set(p["en_revision"]), set(p["en_revision_rutinaria"])
    out = {}
    for k, ks in CORRESPONDENCIA.items():
        presentes = [c for c in ks if c in claves]
        if not presentes:
            out[k] = "NO_LO_MIRA"
        elif any(c in bloq for c in presentes):
            out[k] = "CRITICO"
        elif any(c in rev and c not in rut for c in presentes):
            out[k] = "REVISAR"
        else:
            out[k] = "ACEPTABLE"
    return out


def _tasa(k: int, n: int) -> dict[str, Any]:
    if not n:
        return {"k": k, "n": n, "tasa": None, "ic95_unilateral": None}
    inf, sup = _cp(k, n)
    return {"k": k, "n": n, "tasa": k / n, "limite_inferior_95": inf, "limite_superior_95": sup}


def _cruce(filas: list[dict[str, Any]], ref: str) -> dict[str, Any]:
    neg = [f for f in filas if f[ref] == "NO_DETENER"]
    pos = [f for f in filas if f[ref] == "DETENER"]
    return {
        "falso_bloqueo": _tasa(sum(f["producto"] == "DETENER" for f in neg), len(neg)),
        "falsa_autorizacion": _tasa(sum(f["producto"] == "SEGUIR" for f in pos), len(pos)),
        "aviso_sin_bloqueo": _tasa(sum(f["producto"] == "AVISAR" for f in pos), len(pos)),
        "bloqueo_correcto": _tasa(sum(f["producto"] == "DETENER" for f in pos), len(pos)),
        "matriz": {f"{r}→{p}": sum(f[ref] == r and f["producto"] == p for f in filas)
                   for r in ("DETENER", "NO_DETENER", "DISPUTADO") for p in ("DETENER", "AVISAR", "SEGUIR")},
        "falsos_bloqueos": [f["pdb"] for f in neg if f["producto"] == "DETENER"],
        "falsas_autorizaciones": [f["pdb"] for f in pos if f["producto"] == "SEGUIR"],
        "avisos_sin_bloqueo": [f["pdb"] for f in pos if f["producto"] == "AVISAR"],
    }


def cmd_analizar(args: argparse.Namespace) -> int:
    protocolo = _leer(ENTRADA / "protocolo.json")
    sistemas = _leer(ENTRADA / "sistemas.json")
    ref = _leer(ENTRADA / "referencia_revisores.json")["sistemas"]
    terminales = {t.name.split("-")[1].split(".")[0]: _leer(t) for t in TRABAJO.glob("corridas/shard-*/*.terminal.json")}
    if len(terminales) != 29:
        raise SystemExit(f"faltan corridas: {len(terminales)} de 29")
    filas, fallos = [], []
    nombres = [r[0] for r in REVISORES]
    for s in sistemas:
        t = terminales[s["pdb"]]
        if t["estado"] == "FALLO":
            fallos.append({"pdb": s["pdb"], "intentos": t["intentos"]})
            continue
        crudo = next(TRABAJO.glob(f"corridas/shard-*/{t['crudo']}"))
        if _sha(crudo) != t["crudo_sha256"]:
            raise SystemExit(f"{crudo.name} cambió")
        raw = json.loads(gzip.decompress(crudo.read_bytes()))
        votos = {n: ref[s["pdb"]][n]["veredicto"] == "NO_APTO" for n in nombres}
        v5, v4 = sum(votos.values()), sum(votos[n] for n in nombres[:4])
        p = raw.get("preparacion") or {}
        filas.append({
            "pdb": s["pdb"], "id_r2": s["id_r2"], "producto": decision_del_producto(raw),
            "estado_preparacion": p.get("estado") or "DETENIDO_EN_PREFLIGHT", "razon": p.get("razon"),
            "bloqueantes": p.get("bloqueantes") or ((raw["preflight"].get("technical_blockers") or raw["preflight"])
                                                    if raw.get("detenido_en") else []),
            "en_revision_no_rutinaria": [c for c in p.get("en_revision", []) if c not in p.get("en_revision_rutinaria", [])],
            "votos_detener": votos, "votos_5": v5, "votos_r2": v4,
            "ref_mayoria_5": "DETENER" if v5 >= 3 else "NO_DETENER",
            "ref_unanime_5": "DETENER" if v5 == 5 else "NO_DETENER" if v5 == 0 else "DISPUTADO",
            "ref_mayoria_r2": "DETENER" if v4 >= 3 else "NO_DETENER" if v4 <= 1 else "DISPUTADO",
            "producto_por_control": estado_por_control(raw),
            "receptor_sha256": (raw.get("resultado") or {}).get("receptor_sha256"),
            "task_id": raw.get("task_id"),
        })
    primario = _cruce(filas, "ref_mayoria_5")
    unanime = _cruce(filas, "ref_unanime_5")
    r2 = _cruce(filas, "ref_mayoria_r2")
    # Por control: el estado del producto frente a la mayoría de los revisores (secundario).
    por_control = {}
    for k in CONTROLES:
        c = Counter()
        for f in filas:
            estados = [ref[f["pdb"]][n]["controles"][k] for n in nombres]
            mayoria = Counter(estados).most_common(1)[0][0]
            c[(mayoria, f["producto_por_control"][k])] += 1
        por_control[k] = {"requisitos": CORRESPONDENCIA[k], "revisores→producto": {f"{a}→{b}": n for (a, b), n in sorted(c.items())}}

    fb = primario["falso_bloqueo"]
    fa_unanime = unanime["falsas_autorizaciones"]
    if len(fallos) > MAX_FALLOS:
        decision, razon = "INCONCLUSIVE", f"{len(fallos)} sistemas sin auditoría por fallo de infraestructura (máximo {MAX_FALLOS})"
    elif fa_unanime or (fb["n"] and fb["limite_inferior_95"] > OBJETIVO_FB):
        decision = "NO_GO"
        razon = "; ".join(x for x in (
            f"falsa autorización en sistemas que los cinco revisores detienen: {fa_unanime}" if fa_unanime else "",
            f"falso bloqueo {fb['k']}/{fb['n']}, límite inferior 95 % {fb['limite_inferior_95']:.3f} > {OBJETIVO_FB}"
            if fb["n"] and fb["limite_inferior_95"] > OBJETIVO_FB else "") if x)
    elif fb["n"] and fb["limite_superior_95"] <= OBJETIVO_FB and not primario["falsas_autorizaciones"]:
        decision, razon = "GO", f"falso bloqueo {fb['k']}/{fb['n']}, límite superior 95 % {fb['limite_superior_95']:.3f} ≤ {OBJETIVO_FB}"
    else:
        decision = "INCONCLUSIVE"
        razon = (f"falso bloqueo {fb['k']}/{fb['n']} (límite superior 95 % {fb['limite_superior_95']:.3f}): "
                 f"{'por encima' if fb['tasa'] > OBJETIVO_FB else 'dentro'} del objetivo en la estimación puntual, "
                 f"sin potencia para concluir con {fb['n']} negativos")
    metrics = {
        "experimento": EXP.name, "analizado_en": _ahora(), "protocolo_sha256": _sha(ENTRADA / "protocolo.json"),
        "producto": protocolo["git_head"], "n_sistemas": 29, "n_auditados": len(filas), "fallos": fallos,
        "decision_del_producto": dict(Counter(f["producto"] for f in filas)),
        "estado_preparacion": dict(Counter(f["estado_preparacion"] for f in filas)),
        "referencia": {"mayoria_5": dict(Counter(f["ref_mayoria_5"] for f in filas)),
                       "unanime_5": dict(Counter(f["ref_unanime_5"] for f in filas)),
                       "mayoria_r2": dict(Counter(f["ref_mayoria_r2"] for f in filas))},
        "primario_mayoria_5": primario, "sensibilidad_unanime_5": unanime, "sensibilidad_r2_sin_opus": r2,
        "por_control": por_control, "cpu_core_h": round(cpu_horas(), 2),
        "decision": decision, "razon": razon,
    }
    _escribir(EXP / "metrics.json", metrics)
    with (EXP / "per_system.jsonl").open("w", encoding="utf-8", newline="\n") as fh:
        for f in filas:
            fh.write(json.dumps(f, ensure_ascii=False) + "\n")
    with (EXP / "failures.jsonl").open("w", encoding="utf-8", newline="\n") as fh:
        for f in fallos:
            fh.write(json.dumps(f, ensure_ascii=False) + "\n")
    print(json.dumps({k: metrics[k] for k in ("decision_del_producto", "estado_preparacion", "referencia", "decision", "razon")},
                     indent=2, ensure_ascii=False))
    for nombre, c in (("primario (mayoría de 5)", primario), ("unánime", unanime), ("R2 sin Opus", r2)):
        print(nombre, json.dumps({k: c[k] for k in ("matriz", "falsos_bloqueos", "falsas_autorizaciones", "avisos_sin_bloqueo")},
                                 ensure_ascii=False))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("congelar")
    c.add_argument("--datos", default=str(AQUI / "tmp" / "congelar"))
    e = sub.add_parser("ejecutar")
    e.add_argument("--shard", type=int, required=True)
    e.add_argument("--shards", type=int, default=2)
    sub.add_parser("analizar")
    a = ap.parse_args()
    return {"congelar": cmd_congelar, "ejecutar": cmd_ejecutar, "analizar": cmd_analizar}[a.cmd](a)


if __name__ == "__main__":
    raise SystemExit(main())
