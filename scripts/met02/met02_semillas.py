"""MET-02-SEMILLA: ¿cambia la decisión de Preparación sobre metales y cofactores sólo por la semilla de Vina?

Recomendación 5 del 2026-10-22. ABS-TR-01-VALIDEZ encontró que la distancia de un metal se medía contra el mínimo entre la pose
top-1 y el ligando del cristal, así que la abstención dependía de la pose (1RKP: 5,17 Å por la pose, 6,52 Å el cristal). La regla
en dos niveles (`claude/metales-dos-niveles`) la mide desde el cristal y separa «coordinado» de «sólo cerca».

Panel: las 41 entradas del inventario de metales junto al sitio (`docs/auditorias/metales_junto_al_sitio_2026-10-11.json`) más 1RKP
y 4NY4 de ABS-TR-01. Cinco semillas. Cada corrida, con el producto de antes (`861f6a0e`) y el de después (`878c215b`), cada uno en su
worktree y su cápsula de API aislada. Vina con la misma semilla y el mismo receptor da las mismas poses: sólo cambia la regla.

Uso:  python-embed\\python.exe scripts\\met02\\met02_semillas.py congelar
      python-embed\\python.exe scripts\\met02\\met02_semillas.py ejecutar antes|despues
      python-embed\\python.exe scripts\\met02\\met02_semillas.py analizar
"""
from __future__ import annotations

import hashlib
import json
import math
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

AQUI = Path(__file__).resolve().parent
RAIZ = next(p for p in AQUI.parents if (p / "curated_targets.json").is_file())
EXP = RAIZ / "scripts" / "artifacts_science" / "MET-02-SEMILLA"
ENTRADA = EXP / "entrada"
TRABAJO = EXP / "_work"
SEMILLAS = (42, 7, 13, 101, 2026)
BRAZOS = {
    "antes": {"repo": Path(r"D:\moldesign-worktrees\met02-antes"), "commit": "861f6a0e", "capsula": 7},
    "despues": {"repo": Path(r"D:\moldesign-worktrees\metales"), "commit": "878c215b", "capsula": 8},
}
RUNTIME = Path(r"D:\moldesign-build")
CONFIG_CASO = {
    "enabled_stages": ["validation", "properties", "sa_filter", "conformer", "docking", "xgb", "clgnn"],
    "stage_params": {"properties": {"run_admet_ai": False}, "conformer": {"conformers": 1},
                     "docking": {"exhaustiveness": 8, "num_poses": 9}},
    "docking_engine": "vina", "pro_selectivity": False, "pro_mmgbsa": False,
}
EXTRA_ABS = ("1RKP", "4NY4")


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _leer(p: Path) -> Any:
    return json.loads(p.read_text(encoding="utf-8"))


def _escribir(p: Path, o: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(o, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8", newline="\n")


def _git(repo: Path, *a: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *a], capture_output=True, text=True).stdout.strip()


# ── Congelar ─────────────────────────────────────────────────────────────────

def cmd_congelar() -> int:
    if (ENTRADA / "panel.json").exists():
        raise SystemExit("ya congelado: no se sobrescribe")
    inventario = RAIZ / "docs/auditorias/metales_junto_al_sitio_2026-10-11.json"
    ligandos = RAIZ / "scripts/met01r1/ligandos.json"
    sistemas = RAIZ / "scripts/artifacts_science/ABS-TR-01-VALIDEZ/entrada/sistemas.json"
    filas = _leer(inventario)["filas"]
    lig = {e["pdb_id"]: e for e in _leer(ligandos)["entries"]}
    abs_ = {s["pdb"]: s for s in _leer(sistemas)}
    cat = {e["pdb_id"].upper(): e for e in _leer(RAIZ / "curated_targets.json")}
    panel = []
    for pdb in sorted({f["pdb_id"] for f in filas}):
        iones = [f for f in filas if f["pdb_id"] == pdb]
        e = lig[pdb]
        panel.append({"pdb": pdb, "cadena": cat[pdb]["chain"], "smiles": e["ccd"]["smiles"],
                      "microestado_esperado": e["microstate"]["smiles_acoplado"], "origen": "inventario de metales",
                      "iones_a_6_A": len(iones), "coordinado_en_el_inventario": any(f["lo_coordina_el_ligando"] for f in iones),
                      "deposito_sha256": _sha((RAIZ / "data/targets" / f"{pdb}.pdb.gz").read_bytes())})
    for pdb in EXTRA_ABS:
        s = abs_[pdb]
        panel.append({"pdb": pdb, "cadena": cat[pdb]["chain"], "smiles": s["smiles"],
                      "microestado_esperado": s["smiles_acoplado_esperado"], "origen": "ABS-TR-01-VALIDEZ",
                      "iones_a_6_A": None, "coordinado_en_el_inventario": None,
                      "deposito_sha256": _sha((RAIZ / "data/targets" / f"{pdb}.pdb.gz").read_bytes())})
    _escribir(ENTRADA / "panel.json", panel)
    protocolo = {
        "experimento": "MET-02-SEMILLA", "creado": _ahora(), "semillas": list(SEMILLAS),
        "configuracion": "un caso: exhaustividad 8, 9 poses, 1 conformero, Vina 1.2.7, 4 CPU por proceso, cápsula de API aislada",
        "brazos": {k: {"commit": v["commit"], "regla": "mínimo pose/cristal, un nivel" if k == "antes"
                       else "desde el cristal, coordinado→abstención, sólo cerca→revisión"} for k, v in BRAZOS.items()},
        "ruta": "catálogo, POST /evaluation/preflight → submit → result → POST /evaluation/dossier/{id}/preparacion",
        "medida": "estado de entorno.metales_cofactores por (entrada, semilla, brazo); estado global; hash de la pose top-1",
        "evaluable": "entrada con las 5 semillas completadas en los dos brazos",
        "primario": "entradas evaluables cuya auditoría declara el ligando del cristal en entorno.referencia",
        "hipotesis": {
            "H1": "Con la regla de antes, alguna entrada evaluable cambia de estado de metales sólo por la semilla (descriptivo).",
            "H2": "Con la regla de después, ninguna entrada primaria cambia de estado por la semilla.",
            "H3": "Con la regla de después, en las 41 del inventario el estado es ABSTENCION si el inventario dice que el ligando "
                  "coordina algún ion y REVISAR si no (salvo REGISTRADO por otra especie ya declarada).",
        },
        "decision": {
            "GO": "H2 sin ninguna excepción, H3 en todas las primarias del inventario (las discrepancias se explican una a una "
                  "antes de decidir y cuentan como fallo si no se explican por una diferencia declarada del criterio), "
                  "≥ 30 entradas primarias evaluables, y la pose top-1 idéntica entre brazos en ≥ 95 % de los pares.",
            "NO_GO": "alguna entrada primaria cambia de estado por la semilla con la regla de después.",
            "INCONCLUSIVE": "en cualquier otro caso.",
        },
        "intervalos": "Clopper–Pearson exactos al 95 %",
        "no_dice": "si abstenerse o revisar es la decisión correcta para cada metal (no hay etiquetas); ni nada de la calidad del docking.",
        "entradas": {"inventario": {"ruta": str(inventario.relative_to(RAIZ)).replace("\\", "/"), "sha256": _sha(inventario.read_bytes())},
                     "ligandos": {"ruta": "scripts/met01r1/ligandos.json", "sha256": _sha(ligandos.read_bytes())},
                     "sistemas_abs": {"ruta": "scripts/artifacts_science/ABS-TR-01-VALIDEZ/entrada/sistemas.json",
                                      "sha256": _sha(sistemas.read_bytes())},
                     "panel.json": _sha((ENTRADA / "panel.json").read_bytes()),
                     "vina.exe": _sha((RUNTIME / "tools/vina/vina.exe").read_bytes())},
    }
    _escribir(ENTRADA / "protocolo.json", protocolo)
    print(f"congelado: {len(panel)} entradas × {len(SEMILLAS)} semillas × 2 brazos")
    return 0


# ── Ejecutar ─────────────────────────────────────────────────────────────────

class Capsula:
    def __init__(self, repo: Path, ruta: Path, numero: int):
        r = subprocess.run(["node", str(RAIZ / "scripts/abs_tr_01/capsula.mjs"), str(repo), str(RUNTIME), str(ruta), str(numero)],
                           capture_output=True, text=True)
        if r.returncode:
            raise RuntimeError(r.stderr)
        self.repo, self.ruta, self.numero = repo, ruta, numero
        s = _leer(ruta / "private-session.json")
        self.base, self.secret, self.token, self.t = s["base"], s["secret"], None, 0.0

    def api(self, metodo: str, ruta: str, cuerpo: dict | None = None, esperado=(200,), timeout: float = 900) -> tuple[int, Any]:
        if time.monotonic() - self.t > 900:
            req = urllib.request.Request(self.base + "/auth/desktop-login", headers={"X-MolDesign-Launch": self.secret})
            with urllib.request.urlopen(req, timeout=120) as r:
                self.token, self.t = json.load(r)["access_token"], time.monotonic()
        datos = None if cuerpo is None else json.dumps(cuerpo).encode()
        h = {"Accept": "application/json", "Accept-Language": "es", "Authorization": "Bearer " + self.token}
        if datos:
            h["Content-Type"] = "application/json"
        req = urllib.request.Request(self.base + ruta, data=datos, headers=h, method=metodo)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            crudo = e.read()
            try:
                c = json.loads(crudo)
            except ValueError:
                c = crudo.decode(errors="replace")
            if e.code in esperado:
                return e.code, c
            raise RuntimeError(f"HTTP {e.code} {ruta}: {str(c)[:800]}") from e

    def parar(self) -> None:
        subprocess.run(["node", str(RAIZ / "scripts/abs_tr_01/capsula.mjs"), str(self.repo), str(RUNTIME), str(self.ruta),
                        str(self.numero), "down"], capture_output=True, text=True)


def _requisito(aud: dict, clave: str) -> dict | None:
    bloques = aud["bloques"].values() if isinstance(aud["bloques"], dict) else aud["bloques"]
    return next((r for b in bloques for r in b["requisitos"] if r.get("clave") == clave), None)


def _proyeccion(pdb: str, semilla: int, task: str, pre: dict, smiles: str) -> dict:
    c, rec, lig = pre["effective_config"], pre["receptor"], pre["ligand"]
    return {"projection_version": 1, "case_id": f"met02-{pdb}-{semilla}", "name": f"met02-{pdb}-{semilla}",
            "context": {"question": "¿Cambia la decisión sobre metales con la semilla?"},
            "inputs": {"receptor": {"pdb_id": rec["pdb_id"], "chain": rec["chain"], "origin": "catalog"},
                       "ligand": {"input_smiles": smiles, "canonical_smiles": lig.get("canonical_smiles")},
                       "config": {k: c.get(k) for k in ("grid_center", "grid_size", "docking_engine", "exhaustiveness",
                                                         "num_poses", "seed", "pipeline_config")}},
            "preflight": {"fingerprint": pre["input_fingerprint"], "generated_at": pre.get("generated_at"),
                          "schema_version": pre.get("schema_version"), "execution_route": pre.get("execution_route"),
                          "blockers": pre.get("technical_blockers", []), "warnings": pre.get("warnings", []),
                          "not_evaluated": pre.get("not_evaluated", [])},
            "run": {"task_id": task, "input_fingerprint": pre["input_fingerprint"], "execution_state": "completed"},
            "run_inputs_relation": "corresponde"}


def correr(cap: Capsula, e: dict, semilla: int) -> dict:
    config = json.loads(json.dumps(CONFIG_CASO))
    config["stage_params"]["docking"]["seed"] = semilla
    t0 = time.monotonic()
    fila: dict[str, Any] = {"pdb": e["pdb"], "semilla": semilla, "inicio": _ahora()}
    codigo, pre = cap.api("POST", "/evaluation/preflight", {
        "smiles": e["smiles"], "target_pdb_id": e["pdb"], "chain": e["cadena"], "docking_engine": "vina", "exhaustiveness": 8,
        "num_poses": 9, "conformers": 1, "pipeline_config": config}, esperado=(200, 400, 409, 422))
    if codigo != 200 or pre.get("technical_blockers"):
        fila.update(resultado="detenido_en_preflight", http=codigo, motivo=str(pre)[:1500], segundos=round(time.monotonic() - t0, 1))
        return fila
    ef = pre["effective_config"]
    _, env = cap.api("POST", "/evaluation/submit", {
        "smiles": e["smiles"], "target_pdb_id": e["pdb"], "chain": e["cadena"], "molecule_name": f"MET02-{e['pdb']}",
        "grid_center": ef["grid_center"], "grid_size": ef["grid_size"], "pipeline_config": config,
        "preflight_fingerprint": pre["input_fingerprint"]}, esperado=(202,))
    task = env["task_id"]
    while True:
        _, st = cap.api("GET", f"/evaluation/status/{task}")
        if st.get("status") in {"SUCCESS", "FAILURE", "REVOKED"}:
            break
        if time.monotonic() - t0 > 3600:
            raise RuntimeError("la corrida no terminó en 60 min")
        time.sleep(2)
    if st.get("status") != "SUCCESS":
        fila.update(resultado="corrida_fallida", motivo=str({k: v for k, v in st.items() if k != "result"})[:1500],
                    segundos=round(time.monotonic() - t0, 1))
        return fila
    mid = st["result"]["molecule_id"]
    _, res = cap.api("GET", f"/evaluation/result/{mid}?task_id={task}")
    _, aud = cap.api("POST", f"/evaluation/dossier/{mid}/preparacion", _proyeccion(e["pdb"], semilla, task, pre, e["smiles"]))
    met, ref = _requisito(aud, "entorno.metales_cofactores") or {}, _requisito(aud, "entorno.referencia") or {}
    poses = sorted(res.get("docking_poses") or [], key=lambda p: p.get("rank") or 99)
    dp = res.get("docking_protocol") or {}
    fila.update(resultado="auditada", task_id=task, estado_global=aud.get("estado"),
                metales={k: met.get(k) for k in ("estado", "valor", "razon", "accion_recomendada")},
                referencia=ref.get("valor"), cristal_en_la_referencia="ligando del cristal" in str(ref.get("valor") or ""),
                pose_top1_sha256=_sha((poses[0].get("pdbqt_block") or "").encode()) if poses else None,
                afinidad_top1=res.get("affinity_kcal"), microestado=(res.get("ligand_state") or {}).get("smiles_acoplado"),
                microestado_coincide=(res.get("ligand_state") or {}).get("smiles_acoplado") == e["microestado_esperado"],
                semilla_declarada=dp.get("seed"), vina=res.get("vina_version"), receptor_sha256=res.get("receptor_sha256"),
                segundos=round(time.monotonic() - t0, 1), fin=_ahora())
    return fila


def cmd_ejecutar(brazo: str) -> int:
    b = BRAZOS[brazo]
    if _git(b["repo"], "rev-parse", "--short=8", "HEAD") != b["commit"]:
        raise SystemExit(f"{b['repo']} no está en {b['commit']}")
    panel = _leer(ENTRADA / "panel.json")
    dest = TRABAJO / brazo
    dest.mkdir(parents=True, exist_ok=True)
    cap = Capsula(b["repo"], dest / f"capsula-{datetime.now().strftime('%Y%m%d-%H%M%S')}", b["capsula"])
    try:
        for semilla in SEMILLAS:
            for e in panel:
                f = dest / "corridas" / f"{e['pdb']}_{semilla}.json"
                if f.exists():
                    continue
                for intento in (1, 2):
                    try:
                        fila = correr(cap, e, semilla)
                        break
                    except Exception as exc:  # noqa: BLE001 — un fallo técnico se reintenta una vez y se registra
                        fila = {"pdb": e["pdb"], "semilla": semilla, "resultado": "fallo_tecnico", "intento": intento,
                                "error": f"{type(exc).__name__}: {exc}"[:1500]}
                fila["brazo"], fila["commit"] = brazo, b["commit"]
                _escribir(f, fila)
                print(brazo, e["pdb"], semilla, fila["resultado"], (fila.get("metales") or {}).get("estado"), flush=True)
    finally:
        cap.parar()
    return 0


# ── Analizar ─────────────────────────────────────────────────────────────────

def _cp(k: int, n: int, alfa: float = 0.05) -> list[float] | None:
    if n == 0:
        return None
    from scipy.stats import beta
    lo = 0.0 if k == 0 else float(beta.ppf(alfa / 2, k, n - k + 1))
    hi = 1.0 if k == n else float(beta.ppf(1 - alfa / 2, k + 1, n - k))
    return [round(lo, 4), round(hi, 4)]


def cmd_analizar() -> int:
    panel = _leer(ENTRADA / "panel.json")
    filas = {(b, e["pdb"], s): (_leer(p) if (p := TRABAJO / b / "corridas" / f"{e['pdb']}_{s}.json").exists() else None)
             for b in BRAZOS for e in panel for s in SEMILLAS}
    por_entrada, pares, iguales = [], 0, 0
    for e in panel:
        ok = all((f := filas[(b, e["pdb"], s)]) and f["resultado"] == "auditada" for b in BRAZOS for s in SEMILLAS)
        fila = {"pdb": e["pdb"], "origen": e["origen"], "evaluable": ok, "coordinado_en_el_inventario": e["coordinado_en_el_inventario"]}
        if ok:
            for b in BRAZOS:
                estados = [filas[(b, e["pdb"], s)]["metales"]["estado"] for s in SEMILLAS]
                fila[b] = {"estados": estados, "cambia_con_la_semilla": len(set(estados)) > 1,
                           "global": [filas[(b, e["pdb"], s)]["estado_global"] for s in SEMILLAS]}
            fila["primaria"] = all(filas[("despues", e["pdb"], s)]["cristal_en_la_referencia"] for s in SEMILLAS)
            for s in SEMILLAS:
                pares += 1
                iguales += filas[("antes", e["pdb"], s)]["pose_top1_sha256"] == filas[("despues", e["pdb"], s)]["pose_top1_sha256"]
            if e["coordinado_en_el_inventario"] is not None:
                esperado = "ABSTENCION" if e["coordinado_en_el_inventario"] else "REVISAR"
                fila["h3_esperado"], fila["h3_coincide"] = esperado, set(fila["despues"]["estados"]) == {esperado}
        else:
            fila["fallos"] = {f"{b}/{s}": (filas[(b, e["pdb"], s)] or {}).get("resultado", "sin_corrida") for b in BRAZOS for s in SEMILLAS
                              if not (filas[(b, e["pdb"], s)] and filas[(b, e["pdb"], s)]["resultado"] == "auditada")}
        por_entrada.append(fila)
    ev = [f for f in por_entrada if f["evaluable"]]
    prim = [f for f in ev if f.get("primaria")]
    h1 = sum(f["antes"]["cambia_con_la_semilla"] for f in ev)
    h2 = sum(f["despues"]["cambia_con_la_semilla"] for f in prim)
    h2_no_prim = sum(f["despues"]["cambia_con_la_semilla"] for f in ev if not f.get("primaria"))
    h3 = [f for f in prim if "h3_esperado" in f]
    h3_ok = sum(f["h3_coincide"] for f in h3)
    metricas = {
        "entradas": len(panel), "evaluables": len(ev), "primarias": len(prim),
        "H1_antes_cambian_con_la_semilla": {"k": h1, "n": len(ev), "ic95": _cp(h1, len(ev))},
        "H2_despues_cambian_con_la_semilla_primarias": {"k": h2, "n": len(prim), "ic95": _cp(h2, len(prim))},
        "despues_cambian_no_primarias": {"k": h2_no_prim, "n": len(ev) - len(prim)},
        "H3_coincide_con_el_inventario": {"k": h3_ok, "n": len(h3), "discrepancias": [f["pdb"] for f in h3 if not f["h3_coincide"]]},
        "pose_top1_identica_entre_brazos": {"k": iguales, "n": pares, "fraccion": round(iguales / pares, 4) if pares else None},
        "estados_despues": dict(Counter(st for f in ev for st in f["despues"]["estados"])),
        "estados_antes": dict(Counter(st for f in ev for st in f["antes"]["estados"])),
    }
    _escribir(TRABAJO / "metricas_borrador.json", metricas)
    _escribir(TRABAJO / "por_entrada_borrador.json", por_entrada)
    print(json.dumps(metricas, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    accion = sys.argv[1] if len(sys.argv) > 1 else ""
    if accion == "congelar":
        raise SystemExit(cmd_congelar())
    if accion == "ejecutar" and len(sys.argv) == 3:
        raise SystemExit(cmd_ejecutar(sys.argv[2]))
    if accion == "analizar":
        raise SystemExit(cmd_analizar())
    raise SystemExit(__doc__)
