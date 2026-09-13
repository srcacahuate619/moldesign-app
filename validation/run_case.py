"""Ejecuta casos contra el backend embebido y guarda el resultado CRUDO.

No interpreta ni puntua: somete, espera y persiste. La lectura cientifica se
hace despues, sobre el JSON, para que ninguna decision de metrica se tome
mientras se mira el caso correr.

Arranca el backend con `entorno_de_produccion()` del arnes, es decir con el
mismo entorno que le pasa la aplicacion de escritorio. Sin eso se mide otro
producto (ver el docstring de scripts/qa_embedded_controls.py).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
from qa_embedded_controls import Backend, Contrato, ArnesAbortado, verificar_prerregistro  # noqa: E402


def post(be: Backend, ruta: str, payload: dict, timeout: float = 120):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"http://127.0.0.1:{be.port}{ruta}", data=data,
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        cuerpo = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(cuerpo)
        except Exception:
            return e.code, {"_raw": cuerpo[:4000]}
    except Exception as e:
        return None, {"_transporte": repr(e)}


def ejecutar(be: Backend, contrato: Contrato, caso: dict, espera_s: float) -> dict:
    """preflight -> submit -> status. Devuelve todo lo observado, sin filtrar."""
    contrato.exige("/evaluation/preflight", "post")
    contrato.exige("/evaluation/submit", "post")
    contrato.exige("/evaluation/status/{task_id}", "get")

    obs: dict = {"caso": caso, "t_inicio_utc": datetime.now(timezone.utc).isoformat()}

    t0 = time.time()
    st_pre, pre = post(be, "/evaluation/preflight", {
        "smiles": caso["smiles"], "target_pdb_id": caso["target_pdb_id"],
        **({"chain": caso["chain"]} if caso.get("chain") else {}),
    })
    obs["preflight"] = {"status": st_pre, "cuerpo": pre, "s": round(time.time() - t0, 2)}

    cuerpo_submit = {
        "smiles": caso["smiles"], "target_pdb_id": caso["target_pdb_id"],
        "molecule_name": caso.get("nombre"),
        "is_control": bool(caso.get("is_control", False)),
    }
    if caso.get("chain"):
        cuerpo_submit["chain"] = caso["chain"]
    # La huella del preflight es una puerta del backend: se reenvia tal cual si
    # el preflight la emitio. No se fabrica.
    huella = (pre or {}).get("fingerprint") or (pre or {}).get("preflight_fingerprint")
    if isinstance(huella, str) and len(huella) == 71:
        cuerpo_submit["preflight_fingerprint"] = huella

    t1 = time.time()
    st_sub, sub = post(be, "/evaluation/submit", cuerpo_submit)
    obs["submit"] = {"status": st_sub, "cuerpo": sub, "s": round(time.time() - t1, 2)}

    task_id = (sub or {}).get("task_id")
    if not task_id:
        obs["desenlace"] = "SIN_TASK_ID"
        return obs

    t2 = time.time()
    ultimo = None
    while time.time() - t2 < espera_s:
        st, cuerpo = be.json(f"/evaluation/status/{task_id}", timeout=60)
        ultimo = {"status": st, "cuerpo": cuerpo}
        estado = (cuerpo or {}).get("status") or (cuerpo or {}).get("estado")
        if estado in ("SUCCESS", "FAILURE", "FAILED", "ERROR", "CANCELLED", "ABSTAINED"):
            break
        time.sleep(3)
    obs["status_final"] = ultimo
    obs["s_total"] = round(time.time() - t2, 2)
    obs["desenlace"] = ((ultimo or {}).get("cuerpo") or {}).get("status", "TIMEOUT")
    return obs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle", type=Path, required=True)
    ap.add_argument("--casos", type=Path, required=True,
                    help="JSON con una lista de casos.")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--espera-s", type=float, default=1800)
    ap.add_argument("--modo", required=True, choices=("VM_LIMPIA", "COPIA_AISLADA", "DEV"))
    args = ap.parse_args()

    pre = verificar_prerregistro()
    casos = json.loads(args.casos.read_text(encoding="utf-8"))
    args.out.parent.mkdir(parents=True, exist_ok=True)

    salida = {
        "protocolo": pre, "modo": args.modo,
        "declaracion": "NO EJECUTADO EN VM" if args.modo != "VM_LIMPIA" else "EJECUTADO EN VM LIMPIA",
        "bundle": str(args.bundle), "observaciones": [],
    }
    with Backend(args.bundle.resolve(), args.out.parent / "logs" / "backend_casos.log") as be:
        salida["arranque_s"] = be.arranque_s
        st, spec = be.json("/openapi.json")
        if st != 200:
            raise ArnesAbortado(f"OpenAPI no disponible: {st}")
        contrato = Contrato(spec)
        for caso in casos:
            print(f"-> {caso.get('id')} ...", flush=True)
            obs = ejecutar(be, contrato, caso, args.espera_s)
            print(f"   {obs.get('desenlace')} en {obs.get('s_total')} s", flush=True)
            salida["observaciones"].append(obs)
            args.out.write_text(json.dumps(salida, indent=2, ensure_ascii=False, default=str),
                                encoding="utf-8")
    print(f"-> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
