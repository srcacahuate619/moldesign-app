r"""CAL-D-01-R4-2: el panel de R4 con el producto de 1.0.4, 4-67 incluido (2026-10-24).

Reutiliza `scripts/cal_d01r4/cal_d01r4.py` tal cual —es un activo sellado de R4 y no se edita— y sólo cambia dónde
escribe: `scripts/artifacts_science/CAL-D-01-R4-2-VMAT2-8T69/`. La entrada de R4 (panel, microestados, receptor y
protocolo) se copia byte a byte; `ejecutar` comprueba los hashes antes de acoplar (`cal_d01r4.py` contra el sello de R4,
ver su docstring). La decisión es la de R4. Lo único nuevo,
que no decide, es `declarar`: la advertencia «validación física no evaluada», la sensibilidad sin esos padres y la
reproducibilidad frente a R4. Registro previo: D:\moldesign-audits\CAL_D_01_R4_2\REGISTRO_PREVIO_R4_2.md.

    python-embed\python.exe scripts\cal_d01r4_2\cal_d01r4_2.py preparar
    python-embed\python.exe scripts\cal_d01r4_2\cal_d01r4_2.py ejecutar --fase pose
    python-embed\python.exe scripts\cal_d01r4_2\cal_d01r4_2.py analizar --fase pose
    python-embed\python.exe scripts\cal_d01r4_2\cal_d01r4_2.py ejecutar --fase panel --shard 1 --shards 2
    python-embed\python.exe scripts\cal_d01r4_2\cal_d01r4_2.py ejecutar --fase sens
    python-embed\python.exe scripts\cal_d01r4_2\cal_d01r4_2.py analizar
    python-embed\python.exe scripts\cal_d01r4_2\cal_d01r4_2.py declarar
"""
from __future__ import annotations

import gzip
import importlib.util
import json
import shutil
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
_R4 = AQUI.parent / "cal_d01r4" / "cal_d01r4.py"
_spec = importlib.util.spec_from_file_location("cal_d01r4", _R4)
r4 = importlib.util.module_from_spec(_spec)
sys.modules["cal_d01r4"] = r4
_spec.loader.exec_module(r4)

R4_EXP = r4.EXP
REGISTRO = Path(r"D:\moldesign-audits\CAL_D_01_R4_2\REGISTRO_PREVIO_R4_2.md")
r4.EXP = r4.RAIZ / "scripts" / "artifacts_science" / "CAL-D-01-R4-2-VMAT2-8T69"
r4.ENTRADA = r4.EXP / "entrada"
r4.TRABAJO = r4.EXP / "_work"
EXP, ENTRADA, TRABAJO = r4.EXP, r4.ENTRADA, r4.TRABAJO
TOLERANCIA_E = 0.001


def preparar() -> int:
    """Copia la entrada sellada de R4 y el registro previo de R4-2; se niega si ya hay una distinta."""
    pares = [(o, ENTRADA / o.relative_to(R4_EXP / "entrada")) for o in sorted((R4_EXP / "entrada").rglob("*")) if o.is_file()]
    pares.append((REGISTRO, ENTRADA / REGISTRO.name))
    for origen, destino in pares:
        if destino.exists():
            if destino.read_bytes() != origen.read_bytes():
                raise SystemExit(f"{destino} existe y difiere de {origen}")
            continue
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(origen, destino)
    print(f"entrada copiada de {R4_EXP / 'entrada'} y {REGISTRO.name}")
    return 0


def ejecutar(args) -> int:
    """`cmd_ejecutar` de R4, con una sola diferencia: `cal_d01r4.py` se compara con el hash del sello de R4.

    `protocolo.json` guarda el de antes del arreglo del análisis que R4 declaró (desviación 3: el RMSD frente al cristal
    sólo en el redocking); el manifiesto sellado de R4 guarda el de la versión con la que se analizó y se selló.
    """
    protocolo = r4._leer(ENTRADA / "protocolo.json")
    sellado = r4._leer(R4_EXP / "manifest.json")["assets_hashes"]["scripts/cal_d01r4/cal_d01r4.py"]
    esperados = dict(protocolo["hashes"], **{"cal_d01r4.py": sellado})
    for k, p in {"panel_congelado.csv": ENTRADA / "panel_congelado.csv", "cal_d01r4.py": _R4,
                 "rho_peor.py": _R4.parent / "rho_peor.py", "capsula.mjs": _R4.parent / "capsula.mjs",
                 "calibracion_receptor.py": r4.RAIZ / "scripts" / "calibracion_receptor.py"}.items():
        if esperados[k] != r4._sha(p):
            raise SystemExit(f"{k} no es el congelado ni el sellado de R4")
    if args.fase in ("panel", "sens"):
        puerta = r4._leer(EXP / "puerta_pose.json") if (EXP / "puerta_pose.json").exists() else None
        if not puerta or puerta["decision"] != "GO":
            raise SystemExit("la puerta de pose no está superada: no se acopla el panel")
    if args.fase == "sens" and not list((TRABAJO / "panel").glob("shard-*/*.terminal.json")):
        raise SystemExit("la sensibilidad va después del panel")
    jobs = r4.trabajos(args.fase, protocolo)
    jobs = [j for i, j in enumerate(jobs) if i % args.shards == args.shard - 1]
    congelado = r4._git("rev-parse", "HEAD")
    sesion = AQUI / "tmp" / f"c-{args.fase[0]}{args.shard}-{r4.time.time_ns():x}"
    capsula = r4.Capsula(sesion, args.shard)
    salida = TRABAJO / args.fase / f"shard-{args.shard}"
    try:
        cat = next(e for e in r4._leer(r4.RAIZ / "curated_targets.json") if e["pdb_id"] == r4.PDB_ID)
        previo = r4._receptor_preparado(sesion, cat, env=capsula.env)
        if previo["sha256"] != protocolo["receptor"]["receptor_preparado_sha256"]:
            raise RuntimeError(f"deriva del receptor preparado en la cápsula: {previo['sha256']} != "
                               f"{protocolo['receptor']['receptor_preparado_sha256']}")
        r = r4.ejecutar_trabajos(capsula, jobs, salida, protocolo["receptor"]["receptor_preparado_sha256"],
                                 r4._guardia_git(congelado), r4.TOPE_CPU_H)
    finally:
        capsula.parar()
    print(json.dumps(r))
    return 0


def _no_evaluada(raw: dict) -> tuple[bool, str | None, str | None]:
    se = raw["resultado"].get("structural_evidence")
    if not isinstance(se, dict):
        return True, None, "SIN_STRUCTURAL_EVIDENCE"
    estado = se.get("stage_status")
    return estado in (None, "not_evaluated"), estado, se.get("reason_code")


def declarar() -> int:
    """Lo que el registro previo declara sin que decida (§5). Va después de `analizar`."""
    import rho_peor as rp
    metricas = r4._leer(EXP / "metrics.json")
    filas = [json.loads(l) for l in (EXP / "per_complex.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    corridas = r4._corridas("panel")
    estados: dict[str, int] = {}
    advertidas = []
    for f in filas:
        c = corridas[f["id"]]
        shard = r4._shard_de(corridas, c["id"], f["padre"])
        raw = json.loads(gzip.decompress((TRABAJO / "panel" / f"shard-{shard}" / c["crudo"]).read_bytes()))
        no_ev, estado, motivo = _no_evaluada(raw)
        estados[str(estado)] = estados.get(str(estado), 0) + 1
        if no_ev:
            advertidas.append({"padre": f["padre"], "stage_status": estado, "reason_code": motivo})
    fuera = {a["padre"] for a in advertidas}
    resto = [f for f in filas if f["padre"] not in fuera]
    ki, q, pki = [f["ki_nM"] for f in resto], [f["Q"] for f in resto], [f["pki"] for f in resto]
    sens = {"n": len(resto), "excluidos": sorted(fuera)}
    if fuera and len(resto) > 2:
        ic = rp.bootstrap(ki, q)
        sens.update({"rho": rp.spearman(q, pki), "rho_peor": rp.rho_peor(rp.Panel(ki), q),
                     "ic95_rho": ic["rho"], "ic95_rho_peor": ic["rho_peor"],
                     "bootstrap": {k: ic[k] for k in ("n_replicas", "descartadas", "semilla")}})
    previas = {json.loads(l)["padre"]: json.loads(l) for l in (R4_EXP / "per_complex.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()}
    comunes = [(f, previas[f["padre"]]) for f in filas if f["padre"] in previas]
    difs = [abs(f["E_kcal"] - p["E_kcal"]) for f, p in comunes]
    salida = {
        "experimento": EXP.name, "declarado_en": r4._ahora(), "decide": False,
        "decision_de_P1": metricas["decision"],
        "advertencia_validacion_fisica_no_evaluada": {"n": len(advertidas), "padres": advertidas},
        "stage_status_del_panel": estados,
        "sensibilidad_sin_advertidos": sens,
        "reproducibilidad_frente_a_R4": {
            "padres_comunes": len(comunes),
            "misma_energia_top1": sum(d <= TOLERANCIA_E for d in difs), "tolerancia_kcal": TOLERANCIA_E,
            "max_diferencia_kcal": round(max(difs), 4) if difs else None,
            "difieren": [f["padre"] for (f, _), d in zip(comunes, difs) if d > TOLERANCIA_E],
            "solo_en_R4_2": sorted({f["padre"] for f in filas} - set(previas))},
    }
    r4._escribir(EXP / "declaraciones.json", salida)
    print(json.dumps(salida, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    orden = sys.argv[1:2]
    if orden == ["preparar"]:
        raise SystemExit(preparar())
    if orden == ["declarar"]:
        raise SystemExit(declarar())
    sys.argv[0] = str(_R4)
    ap = r4.argparse.ArgumentParser(description=__doc__.split("\n", 2)[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("ejecutar")
    s.add_argument("--fase", choices=["pose", "panel", "sens"], required=True)
    s.add_argument("--shard", type=int, default=1); s.add_argument("--shards", type=int, default=1)
    s.set_defaults(func=ejecutar)
    s = sub.add_parser("analizar"); s.add_argument("--fase", choices=["pose", "final"], default="final")
    s.set_defaults(func=r4.cmd_analizar)
    a = ap.parse_args()
    raise SystemExit(a.func(a))
