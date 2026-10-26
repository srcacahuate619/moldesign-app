r"""SUP-04-EXHAUSTIVIDAD-8T69: el panel de CAL-D-01-R4-2 con exhaustividad 8, 16 y 32 (2026-10-25).

Reutiliza `scripts/cal_d01r4/cal_d01r4.py` tal cual —activo sellado de R4, no se edita— y sólo cambia la exhaustividad
pedida, la comprobación de deriva que la acompaña, la semilla del panel del brazo `e8s43` y dónde escribe:
`scripts/artifacts_science/SUP-04-EXHAUSTIVIDAD-8T69/_work/<brazo>/`. Registro previo: `entrada/REGISTRO_PREVIO.md`.

    python-embed\python.exe scripts\sup04_exhaustividad\medir.py preparar
    python-embed\python.exe scripts\sup04_exhaustividad\medir.py ejecutar --brazo e32 --fase pose
    python-embed\python.exe scripts\sup04_exhaustividad\medir.py ejecutar --brazo e32 --fase panel --shard 1 --shards 2
    python-embed\python.exe scripts\sup04_exhaustividad\medir.py analizar

`ejecutar` exige el HEAD fijo y el árbol limpio durante toda la campaña (la guardia de R4).
"""
from __future__ import annotations

import argparse
import csv
import gzip
import importlib.util
import json
import random
import shutil
import sys
import time
from pathlib import Path

AQUI = Path(__file__).resolve().parent
_R4 = AQUI.parent / "cal_d01r4" / "cal_d01r4.py"
_spec = importlib.util.spec_from_file_location("cal_d01r4", _R4)
r4 = importlib.util.module_from_spec(_spec)
sys.modules["cal_d01r4"] = r4
_spec.loader.exec_module(r4)
import rho_peor as rp  # noqa: E402  (r4 pone su carpeta en sys.path)

R4_2 = r4.RAIZ / "scripts" / "artifacts_science" / "CAL-D-01-R4-2-VMAT2-8T69"
EXP = r4.RAIZ / "scripts" / "artifacts_science" / "SUP-04-EXHAUSTIVIDAD-8T69"
ENTRADA = EXP / "entrada"
r4.EXP, r4.ENTRADA = EXP, ENTRADA

#: brazo → (exhaustividad, semilla del panel, ¿redocking del cristal?)
BRAZOS = {"e8": (8, 42, True), "e8s43": (8, 43, False), "e16": (16, 42, True), "e32": (32, 42, True)}
MARGEN_RHO = 0.10
BOOT_N, BOOT_SEMILLA = 10_000, 20261025
TOLERANCIA_E = 0.001


def _trabajo(brazo: str) -> Path:
    return EXP / "_work" / brazo


def preparar() -> int:
    """Copia la entrada sellada de R4-2 (sin su registro previo); se niega si ya hay una distinta."""
    for origen in sorted((R4_2 / "entrada").rglob("*")):
        if not origen.is_file() or origen.name.startswith("REGISTRO_PREVIO"):
            continue
        destino = ENTRADA / origen.relative_to(R4_2 / "entrada")
        if destino.exists():
            if destino.read_bytes() != origen.read_bytes():
                raise SystemExit(f"{destino} existe y difiere de {origen}")
            continue
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(origen, destino)
    print(f"entrada copiada de {R4_2 / 'entrada'}")
    return 0


def _evaluar_con(exhaustividad: int):
    """`Backend.evaluar` de calibracion_receptor con la exhaustividad del brazo; lo demás, idéntico."""
    def evaluar(self, smiles: str, semilla: int, nombre: str) -> dict:
        cal = r4._cal()
        self.login()
        g = cal._arnes()
        config = json.loads(json.dumps(cal.CONFIG_CASO))
        config["stage_params"]["docking"]["exhaustiveness"] = exhaustividad
        config["stage_params"]["docking"]["seed"] = semilla
        preflight = g._json(self.base, "POST", "/evaluation/preflight", token=self.token, body={
            "smiles": smiles, "target_pdb_id": r4.PDB_ID, "chain": r4.CADENA, "docking_engine": "vina",
            "exhaustiveness": exhaustividad, "num_poses": 9, "conformers": 1, "pipeline_config": config,
        }, timeout=600)
        if preflight.get("technical_blockers"):
            raise RuntimeError(f"preflight bloqueado: {preflight['technical_blockers']}")
        efectiva = preflight["effective_config"]
        enviado = g._json(self.base, "POST", "/evaluation/submit", token=self.token, expected={202}, body={
            "smiles": smiles, "target_pdb_id": r4.PDB_ID, "chain": r4.CADENA, "molecule_name": nombre,
            "grid_center": efectiva["grid_center"], "grid_size": efectiva["grid_size"],
            "pipeline_config": config, "preflight_fingerprint": preflight["input_fingerprint"],
        })
        task_id, t0, estado = enviado["task_id"], time.monotonic(), {}
        while time.monotonic() - t0 < 3600:
            estado = g._json(self.base, "GET", f"/evaluation/status/{task_id}", token=self.token)
            if estado.get("status") in {"SUCCESS", "FAILURE", "REVOKED"}:
                break
            time.sleep(2.0)
        if estado.get("status") != "SUCCESS":
            raise RuntimeError(f"la corrida no terminó en SUCCESS: {str(estado)[:600]}")
        resultado = estado.get("result") or {}
        _, poses, _ = g._request(self.base, "GET", f"/evaluation/files/poses/{resultado.get('molecule_id')}", token=self.token)
        return {"task_id": task_id, "segundos": round(time.monotonic() - t0, 1),
                "preflight": {"effective_config": efectiva, "warnings": preflight.get("warnings"),
                              "not_evaluated": preflight.get("not_evaluated")},
                "resultado": resultado, "poses_sdf": poses.decode("utf-8", errors="replace")}
    return evaluar


def _comprobar_con(exhaustividad: int):
    """`comprobar_corrida` de R4 con la exhaustividad del brazo en lugar de 8."""
    original = r4.comprobar_corrida

    def comprobar(raw: dict, esperado: dict, semilla: int) -> list[str]:
        dp = raw["resultado"].get("docking_protocol") or {}
        d = [x for x in original(raw, esperado, semilla) if not x.startswith("exhaustividad/poses")]
        if (dp.get("exhaustiveness"), dp.get("num_poses")) != (exhaustividad, 9):
            d.append(f"exhaustividad/poses {dp.get('exhaustiveness')}/{dp.get('num_poses')} != {exhaustividad}/9")
        return d
    return comprobar


def ejecutar(args) -> int:
    exhaustividad, semilla_panel, con_pose = BRAZOS[args.brazo]
    if args.fase == "pose" and not con_pose:
        raise SystemExit(f"el brazo {args.brazo} no tiene redocking")
    protocolo = r4._leer(ENTRADA / "protocolo.json")
    if r4._sha(ENTRADA / "panel_congelado.csv") != protocolo["hashes"]["panel_congelado.csv"]:
        raise SystemExit("panel_congelado.csv no es el congelado")
    r4.TRABAJO = _trabajo(args.brazo)
    r4.SEMILLA_PANEL = semilla_panel
    r4.Capsula.evaluar = _evaluar_con(exhaustividad)
    r4.comprobar_corrida = _comprobar_con(exhaustividad)
    jobs = r4.trabajos(args.fase, protocolo)
    jobs = [j for i, j in enumerate(jobs) if i % args.shards == args.shard - 1]
    congelado = r4._git("rev-parse", "HEAD")
    sesion = AQUI / "tmp" / f"c-{args.brazo}-{args.fase[0]}{args.shard}-{time.time_ns():x}"
    # Cápsulas 3 y 4 (puertos 18013-18014): la 1 la ocupa la cápsula de QA de otra sesión.
    capsula = r4.Capsula(sesion, args.shard + 2)
    try:
        cat = next(e for e in r4._leer(r4.RAIZ / "curated_targets.json") if e["pdb_id"] == r4.PDB_ID)
        previo = r4._receptor_preparado(sesion, cat, env=capsula.env)
        if previo["sha256"] != protocolo["receptor"]["receptor_preparado_sha256"]:
            raise RuntimeError(f"deriva del receptor preparado: {previo['sha256']}")
        r = r4.ejecutar_trabajos(capsula, jobs, r4.TRABAJO / args.fase / f"shard-{args.shard}",
                                 protocolo["receptor"]["receptor_preparado_sha256"], r4._guardia_git(congelado),
                                 r4.TOPE_CPU_H)
    finally:
        capsula.parar()
    print(json.dumps({"brazo": args.brazo, **r}))
    return 0


# ── Analizar ─────────────────────────────────────────────────────────────────

def _brazo(brazo: str, fase: str, ref_n=None) -> dict[str, dict]:
    """id → top-1 (E, RMSD si ref_n) de las corridas SUCCESS del brazo."""
    salida = {}
    for t in sorted((_trabajo(brazo) / fase).glob("shard-*/*.terminal.json")):
        c = r4._leer(t)
        if c["estado"] != "SUCCESS":
            salida[c["id"]] = {"estado": c["estado"]}
            continue
        raw = json.loads(gzip.decompress((t.parent / c["crudo"]).read_bytes()))
        salida[c["id"]] = {"estado": "SUCCESS", "segundos": raw["segundos"], **r4._extraer_pose(raw, ref_n)}
    return salida


def _rho(padres, q, pki):
    return rp.spearman([q[p] for p in padres], [pki[p] for p in padres])


def _delta(padres, qa, qb, pki):
    """Δρ = ρ(b) − ρ(a) y su IC 95 % por bootstrap pareado por padre."""
    rng = random.Random(BOOT_SEMILLA)
    d = _rho(padres, qb, pki) - _rho(padres, qa, pki)
    reps = []
    for _ in range(BOOT_N):
        m = [padres[rng.randrange(len(padres))] for _ in padres]
        if len({pki[p] for p in m}) < 3:
            continue
        reps.append(_rho(m, qb, pki) - _rho(m, qa, pki))
    reps.sort()
    return {"delta": d, "ic95": [reps[int(0.025 * len(reps))], reps[int(0.975 * len(reps)) - 1]],
            "n": len(padres), "replicas": len(reps), "semilla": BOOT_SEMILLA}


def analizar(_args) -> int:
    protocolo = r4._leer(ENTRADA / "protocolo.json")
    cal = r4._cal()
    ref_n = cal._neutro_sin_h(r4._cristal_mol(protocolo["verificacion"]["ligando_cristal"]["smiles_entrada"]))
    panel = {p["padre"]: p for p in csv.DictReader((ENTRADA / "panel_congelado.csv").open(encoding="utf-8"))
             if p["rol"] == "primario"}
    pki = {k: float(p["pki"]) for k, p in panel.items()}
    brazos, q, fallos = {}, {}, []
    for b in BRAZOS:
        corr = _brazo(b, "panel")
        q[b] = {k[len("panel-"):]: -v["E_kcal"] for k, v in corr.items() if v["estado"] == "SUCCESS"}
        fallos += [{"brazo": b, "id": k, "estado": v["estado"]} for k, v in corr.items() if v["estado"] != "SUCCESS"]
        comunes = sorted(set(q[b]) & set(panel))
        info = {"n": len(comunes), "rho": _rho(comunes, q[b], pki),
                "rho_peor": rp.rho_peor(rp.Panel([panel[p]["ki_nM"] for p in comunes]), [q[b][p] for p in comunes]),
                "cpu_core_h": round(r4.cpu_horas(_trabajo(b)), 2)}
        if BRAZOS[b][2]:
            pose = _brazo(b, "pose", ref_n)
            info["redocking"] = {k: {"rmsd_A": v.get("rmsd_A"), "valida": v.get("valida"), "E_kcal": v.get("E_kcal")}
                                 for k, v in pose.items()}
            info["redocking_a_2A"] = sum(1 for v in pose.values() if v.get("rmsd_A") is not None and v["rmsd_A"] <= 2.0)
        brazos[b] = info
    comunes = sorted(set(q["e8"]) & set(q["e32"]) & set(panel))
    primaria = _delta(comunes, q["e8"], q["e32"], pki)
    declaradas = {}
    for b in ("e16", "e8s43"):
        cb = sorted(set(q["e8"]) & set(q[b]) & set(panel))
        declaradas[f"delta_{b}_menos_e8"] = _delta(cb, q["e8"], q[b], pki)
    dE = {p: q["e32"][p] - q["e8"][p] for p in comunes}  # > 0: la energía baja con 32
    declaradas["energia_e32_frente_a_e8"] = {
        "baja_mas_de_0_1": sum(v > 0.1 for v in dE.values()), "baja_mas_de_0_5": sum(v > 0.5 for v in dE.values()),
        "sube_mas_de_0_1": sum(v < -0.1 for v in dE.values()), "media_kcal": round(sum(dE.values()) / len(dE), 4),
        "rho_e8_e32": rp.spearman([q["e8"][p] for p in comunes], [q["e32"][p] for p in comunes])}
    previas = {json.loads(l)["padre"]: json.loads(l)["Q"] for l in
               (R4_2 / "per_complex.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()}
    rep = [abs(q["e8"][p] - previas[p]) for p in q["e8"] if p in previas]
    declaradas["e8_frente_a_R4_2"] = {"comunes": len(rep), "misma_energia": sum(d <= TOLERANCIA_E for d in rep),
                                      "max_diferencia_kcal": round(max(rep), 4) if rep else None}
    ic = primaria["ic95"]
    pose_peor = brazos["e8"]["redocking_a_2A"] < brazos["e32"]["redocking_a_2A"]
    if len(comunes) < r4.MIN_PADRES:
        decision, razon = "EXPLORATORIO", f"{len(comunes)} padres comunes (< {r4.MIN_PADRES})"
    elif ic[0] > 0 or pose_peor:
        decision = "NO_GO"
        razon = (f"Δρ(e32−e8) = {primaria['delta']:+.3f} (IC95 {ic[0]:+.3f} a {ic[1]:+.3f}); redocking a ≤ 2 Å: "
                 f"e8 {brazos['e8']['redocking_a_2A']}/5, e32 {brazos['e32']['redocking_a_2A']}/5")
    elif -MARGEN_RHO <= ic[0] and ic[1] <= MARGEN_RHO:
        decision = "GO"
        razon = (f"Δρ(e32−e8) = {primaria['delta']:+.3f} (IC95 {ic[0]:+.3f} a {ic[1]:+.3f}) dentro de ±{MARGEN_RHO}; "
                 f"redocking a ≤ 2 Å: e8 {brazos['e8']['redocking_a_2A']}/5, e32 {brazos['e32']['redocking_a_2A']}/5")
    else:
        decision = "INCONCLUSIVE"
        razon = f"Δρ(e32−e8) = {primaria['delta']:+.3f} (IC95 {ic[0]:+.3f} a {ic[1]:+.3f}): ni excluye el cero ni cabe en ±{MARGEN_RHO}"
    metricas = {"experimento": EXP.name, "analizado_en": r4._ahora(), "decision": decision, "razon": razon,
                "primaria_delta_rho_e32_menos_e8": primaria, "brazos": brazos, "declaradas": declaradas,
                "fallos": fallos}
    r4._escribir(EXP / "metrics.json", metricas)
    with (EXP / "per_complex.jsonl").open("w", encoding="utf-8", newline="\n") as fh:
        for p in sorted(panel):
            fh.write(json.dumps({"padre": p, "pki": pki[p], **{f"Q_{b}": q[b].get(p) for b in BRAZOS}}, ensure_ascii=False) + "\n")
    with (EXP / "failures.jsonl").open("w", encoding="utf-8", newline="\n") as fh:
        for f in fallos:
            fh.write(json.dumps(f, ensure_ascii=False) + "\n")
    print(json.dumps({k: metricas[k] for k in ("decision", "razon")}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("preparar").set_defaults(func=lambda a: preparar())
    s = sub.add_parser("ejecutar")
    s.add_argument("--brazo", choices=list(BRAZOS), required=True)
    s.add_argument("--fase", choices=["pose", "panel"], required=True)
    s.add_argument("--shard", type=int, default=1); s.add_argument("--shards", type=int, default=1)
    s.set_defaults(func=ejecutar)
    sub.add_parser("analizar").set_defaults(func=analizar)
    a = ap.parse_args()
    raise SystemExit(a.func(a))
