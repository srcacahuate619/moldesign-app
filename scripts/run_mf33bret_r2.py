#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MF-33-B-RET-R2: repara el unico dock que murio en R1, y nada mas.

QUE PASO. `MF-33-B-RET-R1` completo los 48 complejos y reprodujo el brazo B sellado de
`MF-33` de forma perfecta -G1 = 47/47 = 1.0000-, pero su G0 tecnico fallo por UN dock de
970: `1afl` conformero 29, Vina returncode 1 a los 154.9 s. El contrato es ITT y no admite
excepcion por tamano, asi que la lectura primaria fue `NO_LEER_GATES_TECNICOS`.

EL FALLO ESTA CARACTERIZADO Y NO ES QUIMICA. El stdout de ese dock muestra que Vina calculo
el grid y empezo a dockear, con la barra de progreso cortada a media altura y stderr VACIO.
Re-ejecutado aislado con el protocolo identico, termina rc=0 y nueve poses. El checkpoint se
escribio mientras en la misma maquina corrian PoseBusters, pytest y generacion de
conformeros: es contencion de recursos, la trampa que el registro ya tenia documentada.

QUE HACE ESTE R2, Y NADA MAS:
  1. reusa VERBATIM los 47 checkpoints buenos de R1, registrando el sha256 de cada uno;
  2. re-ejecuta SOLO `1afl`, sus 30 conformeros, con el protocolo importado de R1;
  3. recalcula G0, G1 y los bloques con las MISMAS reglas selladas, sin tocar ninguna.

El protocolo es identico POR CONSTRUCCION y no por copia: este script IMPORTA
`run_mf33bret_r1.py`, sellado como asset de `MF-33-B-RET-R1`, y reutiliza su `analizar`, su
`_block` y sus constantes. Es el patron del docs/49 seccion 17.

ADVERTENCIA DE PROCEDENCIA, ESCRITA ANTES DE EJECUTAR Y NO DESPUES. Al diagnosticar el
fallo se vieron los bloques cientificos del `metrics.json` de R1. **Este R2 NO es una
confirmacion ciega y no puede presentarse como tal.** Lo que sigue siendo ciego es la REGLA
DE DECISION, sellada en `MF-33-B-RET-PRE` y `MF-33-B-RET-R1-PRE` antes de todo esto, que no
se puede mover y no se mueve. Lo que se perdio es la ceguera sobre el desenlace.

UN SOLO INTENTO. Si `1afl` vuelve a fallar, el fallo NO era ambiental, G0 vuelve a fallar y
la lectura vuelve a ser `NO_LEER_GATES_TECNICOS`. No habra un R3 por la via de repetir: haria
falta un diseno distinto. Declararlo aqui es lo que impide que esto degenere en repetir
hasta que salga.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import run_mf33bret_r1 as r1          # sellado como asset de MF-33-B-RET-R1

PID_REPARADO = "1afl"


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    from estadistica_fnd04 import mcnemar_exacto  # noqa: F401  (lo usa r1._block)

    ws = ROOT
    art = ws / "scripts" / "artifacts_science"
    origen = art / "MF-33-B-RET-R1"
    out_dir = art / "MF-33-B-RET-R2"
    (out_dir / "checkpoints").mkdir(parents=True, exist_ok=True)
    (out_dir / "per_pose").mkdir(parents=True, exist_ok=True)

    parent = {x["pid"]: x for x in
              (json.loads(s) for s in
               (art / "MF-33" / "per_complex.jsonl").read_text(encoding="utf-8").splitlines()
               if s.strip())}
    jobs = sorted((pid, r["estrato"]) for pid, r in parent.items())

    # 1. Reusar los 47 buenos, con su hash de procedencia.
    procedencia: dict[str, str] = {}
    for p in sorted((origen / "checkpoints").glob("*.json")):
        if p.stem == PID_REPARADO:
            continue
        shutil.copyfile(p, out_dir / "checkpoints" / p.name)
        procedencia[p.stem] = _sha(p)
        pp = origen / "per_pose" / p.name
        if pp.exists():
            shutil.copyfile(pp, out_dir / "per_pose" / p.name)
    print(f"[R2] reusados {len(procedencia)} checkpoints de R1, con sha256 registrado",
          flush=True)

    # 2. Re-ejecutar solo el complejo afectado.
    estrato = dict(jobs)[PID_REPARADO]
    print(f"[R2] re-ejecutando {PID_REPARADO} ({estrato}) ...", flush=True)
    r = r1.analizar(str(ws), PID_REPARADO, estrato, str(out_dir))
    poses = r.pop("poses")
    fallos_nuevos = list(r.get("failures", []))
    r1._write(out_dir / "checkpoints" / f"{PID_REPARADO}.json", r)
    r1._write(out_dir / "per_pose" / f"{PID_REPARADO}.json", poses)
    print(f"[R2] {PID_REPARADO}: K={r.get('K')} poses={r.get('ENSEMBLE',{}).get('n_poses')} "
          f"failures={len(fallos_nuevos)} ({r.get('duration_s')}s)", flush=True)

    # 3. Recomponer y aplicar las MISMAS reglas selladas.
    completed: dict[str, dict[str, Any]] = {}
    for p in (out_dir / "checkpoints").glob("*.json"):
        try:
            x = json.loads(p.read_text(encoding="utf-8"))
            completed[x["pid"]] = x
        except (json.JSONDecodeError, KeyError):
            pass
    rows = [completed[p] for p, _ in jobs if p in completed]
    failures = [f for x in rows for f in x.get("failures", [])]
    ok = [x for x in rows if not x.get("error") and not x.get("failures")
          and x.get("ENSEMBLE", {}).get("n_poses", 0) > 0]
    for x in rows:
        x.pop("failures", None)

    r1._write(out_dir / "per_complex.jsonl",
              "".join(json.dumps(x, ensure_ascii=False, sort_keys=True) + "\n" for x in rows))
    r1._write(out_dir / "failures.jsonl",
              "".join(json.dumps(f, ensure_ascii=False, sort_keys=True) + "\n" for f in failures))

    comp = [(x, parent[x["pid"]]["brazos"].get("B", {}).get("rmsd_min")) for x in ok]
    equal = sum(abs(x["ENSEMBLE"]["oraculo"] - ref) <= r1.G1_TOL for x, ref in comp
                if ref is not None)
    g1n = sum(ref is not None for _, ref in comp)
    g1 = equal / g1n if g1n else 0.0
    todos, coloc = r1._block(ok, "TODOS"), r1._block(
        [x for x in ok if x["estrato"] == "COLOCACION"], "COLOCACION")

    mejora_o = (todos["oraculo"]["mcnemar_p"] < .05
                and todos["oraculo"]["b_gana_ensemble"] > todos["oraculo"]["c_gana_single"])
    mejora_t = (todos["top1"]["mcnemar_p"] < .05
                and todos["top1"]["b_gana_ensemble"] > todos["top1"]["c_gana_single"])
    tecnico = len(rows) == len(jobs) and not failures and len(ok) == len(jobs) and g1 >= r1.G1_MIN
    lectura = (("LA_VENTAJA_LLEGA_AL_USUARIO" if mejora_o and mejora_t
                else "EL_CUELLO_SE_DESPLAZA_A_LA_SELECCION" if mejora_o
                else "SIN_EFECTO_EN_LA_ENTREGA")
               if tecnico else "NO_LEER_GATES_TECNICOS")

    metrics = {
        "experiment_id": "MF-33-B-RET-R2",
        "tipo": "reparacion de un dock ambiental; reglas y protocolo importados sin cambios",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "no_es_ciego": (
            "Al diagnosticar el fallo de R1 se vieron sus bloques cientificos. Este R2 NO es "
            "confirmacion ciega. La REGLA DE DECISION sigue siendo la sellada en "
            "MF-33-B-RET-PRE y MF-33-B-RET-R1-PRE, y no se ha movido."),
        "reparacion": {
            "pid": PID_REPARADO,
            "motivo": "Vina rc=1 en conf29 por contencion de recursos; re-ejecutado aislado da rc=0",
            "intentos_permitidos": 1,
            "failures_en_la_reejecucion": fallos_nuevos,
        },
        "procedencia_reusada": {
            "n_checkpoints_de_R1": len(procedencia),
            "sha256_por_pid": procedencia,
            "origen": "scripts/artifacts_science/MF-33-B-RET-R1 (sellado INCONCLUSIVE)"},
        "config": {"exhaustiveness": r1.EXH, "num_modes": r1.NUM_MODES, "seed": r1.SEED,
                   "box_A": r1.BOX, "cpu": 1, "threshold_A": r1.UMBRAL_A},
        "technical_gate": {"expected_complexes": len(jobs), "completed": len(rows),
                           "failures": len(failures), "pasa": tecnico},
        "G1_REPRODUCE_BRAZO_B_SELLADO": {"iguales": equal, "de": g1n,
                                         "fraccion": round(g1, 4), "minimo": r1.G1_MIN,
                                         "pasa": g1 >= r1.G1_MIN},
        "TODOS": todos, "COLOCACION": coloc,
        "lectura_preregistrada": lectura,
    }
    r1._write(out_dir / "metrics.json", metrics)
    print(f"[MF-33-B-RET-R2] tecnico={tecnico} G1={g1:.4f} n_ok={len(ok)} "
          f"failures={len(failures)} lectura={lectura}", flush=True)
    return 0 if tecnico else 2


if __name__ == "__main__":
    raise SystemExit(main())
