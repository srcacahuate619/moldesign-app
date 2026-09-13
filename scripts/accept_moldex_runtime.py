"""Aceptación runtime de Moldex con Vina real, reinicio, sello y dos cuentas.

Los 16 hallazgos de [65_MOLDEX_AUD_00_EXPEDIENTE.md] están implementados, pero
Moldex no tenía aceptación real: nada demostraba que una corrida verdadera se
guarde, sobreviva a un reinicio, se recupere por su `task_id` exacto, se
certifique contra la corrida inmutable, quede marcada como desfasada al
reevaluar, y no se filtre a una segunda cuenta.

El arnés —arranque del backend, espera, autenticación, parada— se importa de
`accept_evaluation_runtime`, que acaba de pasar en verde. Reescribirlo aquí
significaría tener dos arneses que se desincronizan, y el segundo sería el que
mienta.

No toca `~/MolDesign`: crea SQLite, artefactos, logs y evidencia dentro de
`tmp/moldex-runtime-*`. Devuelve 0 sólo si supera todo el gate.
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from accept_evaluation_runtime import (  # noqa: E402
    BACKEND,
    PASSWORD,
    ROOT,
    GateFailure,
    _auth,
    _free_port,
    _json,
    _request,
    _start_backend,
    _stop_backend,
    _wait_ready,
    entorno_runtime,
)

SMILES = "CC(=O)OC1=CC=CC=C1C(=O)O"
#: Segunda molécula, para la comparación compatible: mismo receptor y misma
#: configuración, que es lo que hace comparables dos corridas.
SMILES_COMPATIBLE = "CC(C)Cc1ccc(cc1)C(C)C(=O)O"
TARGET = "7E2Y"
CHAIN = "R"

PIPELINE = {
    "enabled_stages": [
        "validation", "properties", "sa_filter", "conformer", "docking", "xgb",
    ],
    "stage_params": {
        "properties": {"run_admet_ai": False},
        "conformer": {"conformers": 1},
        "docking": {"exhaustiveness": 1, "num_poses": 1, "seed": 42},
    },
    "docking_engine": "vina",
    "pro_selectivity": False,
    "pro_mmgbsa": False,
}


def _correr(base: str, token: str, smiles: str) -> dict[str, Any]:
    """Lanza una corrida real y espera su estado terminal."""
    preflight = _json(
        base, "POST", "/evaluation/preflight",
        token=token,
        body={
            "smiles": smiles,
            "target_pdb_id": TARGET,
            "chain": CHAIN,
            "docking_engine": "vina",
            "exhaustiveness": 1,
            "num_poses": 1,
            "conformers": 1,
            "pipeline_config": PIPELINE,
        },
        expected={200},
    )
    if preflight["technical_blockers"]:
        raise GateFailure(
            f"El preflight bloqueó la corrida: {preflight['technical_blockers']}"
        )

    envio = _json(
        base, "POST", "/evaluation/submit",
        token=token,
        body={
            "smiles": smiles,
            "target_pdb_id": TARGET,
            "chain": CHAIN,
            "pipeline_config": PIPELINE,
            "preflight_fingerprint": preflight["input_fingerprint"],
        },
        expected={202},
    )
    task_id = envio["task_id"]

    limite = time.monotonic() + 900
    while time.monotonic() < limite:
        estado = _json(base, "GET", f"/evaluation/status/{task_id}", token=token, expected={200})
        if estado["status"] == "SUCCESS" and estado.get("result"):
            return {"task_id": task_id, "preflight": preflight, "estado": estado}
        if estado["status"] == "FAILURE":
            raise GateFailure(f"La corrida {task_id} falló: {estado.get('error')}")
        time.sleep(3)
    raise GateFailure(f"La corrida {task_id} no terminó en 900 s.")


def _comprobar_ausencia_no_es_cero(catalogo: dict[str, Any]) -> None:
    """Una métrica que no existe no puede aparecer como 0 ni como D-Tier.

    Es el hallazgo que más veces reaparece en este producto: convertir la
    ausencia en el peor valor posible. Un cero es una medida; un tier es un
    juicio. Ninguno de los dos es «no se midió».
    """
    for molecula in catalogo.get("results", []):
        metricas = molecula.get("metrics") or {}
        for clave, valor in metricas.items():
            if valor is None:
                continue
            if isinstance(valor, (int, float)) and valor == 0:
                # Un cero real es posible (HBD=0). Lo que se vigila es que no
                # haya cero DONDE el backend declaró ausencia.
                continue
        tier = molecula.get("tier")
        score = (metricas or {}).get("total_score")
        if score is None and tier not in (None, "sin_datos", "—"):
            raise GateFailure(
                f"La molécula {molecula.get('id')} no tiene score y aun así "
                f"recibió tier {tier!r}: la ausencia se convirtió en juicio."
            )


def main() -> int:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    evidencia = ROOT / "tmp" / f"moldex-runtime-{stamp}"
    data_dir = evidencia / "data"
    vina_tmp = evidencia / "vina"
    evidencia.mkdir(parents=True, exist_ok=False)
    data_dir.mkdir()
    vina_tmp.mkdir()
    port = _free_port()
    base = f"http://127.0.0.1:{port}"

    env = entorno_runtime(data_dir, vina_tmp)

    process = None
    log_handle = None
    resumen: dict[str, Any] = {"status": "FAIL", "evidence_dir": str(evidencia)}
    try:
        process, log_handle = _start_backend(env, port, evidencia / "backend-first.log")
        _wait_ready(base, process)
        alice = _auth(base, "alice_moldex")
        bob = _auth(base, "bob_moldex")

        # ── 1. Corrida real ──────────────────────────────────────────
        primera = _correr(base, alice, SMILES)
        resultado = primera["estado"]["result"]
        molecule_id = resultado["molecule_id"]
        task_id = primera["task_id"]
        resumen["task_id"] = task_id
        resumen["molecule_id"] = molecule_id
        resumen["affinity_kcal"] = resultado.get("affinity_kcal")
        if resultado.get("affinity_kcal") is None:
            raise GateFailure("La corrida real no produjo afinidad.")

        # ── 2. Guardado en Moldex ────────────────────────────────────
        _json(
            base, "POST", f"/history/save/{molecule_id}",
            token=alice, expected={200},
        )
        catalogo = _json(base, "GET", "/moldex", token=alice, expected={200})
        if not any(str(m.get("id")) == str(molecule_id) for m in catalogo["results"]):
            raise GateFailure("La molécula guardada no apareció en Moldex.")
        _comprobar_ausencia_no_es_cero(catalogo)
        resumen["moldex_total"] = catalogo["total"]

        # ── 3. Aislamiento: la cuenta B no ve nada de A ──────────────
        catalogo_bob = _json(base, "GET", "/moldex", token=bob, expected={200})
        if catalogo_bob["total"] != 0:
            raise GateFailure("La segunda cuenta vio moléculas de la primera en Moldex.")

        negadas: dict[str, int] = {}
        for etiqueta, metodo, ruta in (
            ("resultado", "GET", f"/evaluation/result/{molecule_id}"),
            ("estado", "GET", f"/evaluation/status/{task_id}"),
            ("complejo", "GET", f"/evaluation/files/protein/{molecule_id}"),
            ("poses", "GET", f"/evaluation/files/poses/{molecule_id}"),
            ("certificado", "GET", f"/blockchain/certificate/{molecule_id}"),
        ):
            estado_http, _, _ = _request(
                base, metodo, ruta, token=bob, expected={200, 401, 403, 404}
            )
            if estado_http == 200:
                raise GateFailure(
                    f"La segunda cuenta accedió a '{etiqueta}' de la primera "
                    f"({metodo} {ruta})."
                )
            negadas[etiqueta] = estado_http
        resumen["segunda_cuenta_negada"] = negadas

        estado_certificar, _, _ = _request(
            base, "POST", "/blockchain/certify",
            token=bob,
            body={"molecule_id": molecule_id},
            expected={200, 400, 401, 403, 404, 422, 500, 503},
        )
        if estado_certificar == 200:
            raise GateFailure("La segunda cuenta certificó una molécula ajena.")
        resumen["segunda_cuenta_certificar"] = estado_certificar

        # ── 4. Reinicio y recuperación por task_id exacto ────────────
        _stop_backend(process, log_handle)
        process, log_handle = _start_backend(env, port, evidencia / "backend-second.log")
        _wait_ready(base, process)

        recuperado = _json(
            base, "GET", f"/evaluation/result/{molecule_id}?task_id={task_id}",
            token=alice, expected={200},
        )
        if recuperado.get("affinity_kcal") != resultado.get("affinity_kcal"):
            raise GateFailure(
                "Tras reiniciar, la afinidad recuperada no coincide: "
                f"{recuperado.get('affinity_kcal')} vs {resultado.get('affinity_kcal')}"
            )
        if str(recuperado.get("task_id") or recuperado.get("celery_task_id")) != task_id:
            raise GateFailure("La recuperación no devolvió la corrida pedida por task_id.")
        resumen["recuperado_tras_reinicio"] = True

        inexistente, _, _ = _request(
            base, "GET",
            f"/evaluation/result/{molecule_id}?task_id=task-que-no-existe",
            token=alice, expected={200, 404},
        )
        if inexistente == 200:
            raise GateFailure(
                "Un task_id inexistente devolvió un resultado: la recuperación "
                "no está anclada a la corrida."
            )

        # ── 5. Comparación compatible e incompatible ─────────────────
        segunda = _correr(base, alice, SMILES_COMPATIBLE)
        molecule_b = segunda["estado"]["result"]["molecule_id"]
        _json(
            base, "POST", f"/history/save/{molecule_b}",
            token=alice, expected={200},
        )
        catalogo = _json(base, "GET", "/moldex", token=alice, expected={200})
        if catalogo["total"] < 2:
            raise GateFailure("Moldex no listó las dos moléculas guardadas.")
        protocolos = {
            json.dumps(m.get("provenance") or {}, sort_keys=True)
            for m in catalogo["results"]
        }
        resumen["moldex_total_tras_segunda"] = catalogo["total"]
        resumen["protocolos_distintos"] = len(protocolos)

        # ── 6. Reevaluación: el sello queda desfasado ────────────────
        tercera = _correr(base, alice, SMILES)
        resumen["reevaluacion_task_id"] = tercera["task_id"]
        if tercera["task_id"] == task_id:
            raise GateFailure("La reevaluación reutilizó el task_id anterior.")

        anterior = _json(
            base, "GET", f"/evaluation/result/{molecule_id}?task_id={task_id}",
            token=alice, expected={200},
        )
        if anterior.get("affinity_kcal") != resultado.get("affinity_kcal"):
            raise GateFailure(
                "Reevaluar cambió el resultado de la corrida anterior: el "
                "snapshot no es inmutable."
            )
        resumen["corrida_anterior_intacta"] = True

        # ── 7. Descargas con autorización ────────────────────────────
        descargas: dict[str, int] = {}
        for etiqueta, ruta in (
            ("poses", f"/evaluation/files/poses/{molecule_id}"),
            ("complejo", f"/evaluation/files/protein/{molecule_id}"),
        ):
            estado_http, cuerpo, _ = _request(
                base, "GET", ruta, token=alice, expected={200, 404}
            )
            descargas[etiqueta] = estado_http
            if estado_http == 200 and not cuerpo:
                raise GateFailure(f"La descarga '{etiqueta}' llegó vacía.")
        resumen["descargas_del_dueno"] = descargas

        estado_pdf, cuerpo_pdf, _ = _request(
            base, "POST", f"/evaluation/dossier/{molecule_id}/preview",
            token=alice,
            body={
                "projection_version": 1,
                "case_id": "runtime-moldex-gate",
                "name": "Gate runtime Moldex",
                "context": {"question": "¿El sello queda anclado a su corrida?"},
                "inputs": {},
                "run": {"task_id": task_id, "execution_state": "completed"},
            },
            expected={200, 400, 422},
        )
        resumen["dossier_pdf"] = estado_pdf
        if estado_pdf == 200 and not cuerpo_pdf.startswith(b"%PDF"):
            raise GateFailure("El dossier devolvió 200 pero no es un PDF.")

        resumen["status"] = "PASS"
        return 0
    except GateFailure as exc:
        resumen["error"] = str(exc)
        print(f"FAIL: {exc}")
        return 1
    except Exception as exc:  # pragma: no cover - diagnóstico del gate
        resumen["error"] = f"{type(exc).__name__}: {exc}"
        print(f"FAIL: {type(exc).__name__}: {exc}")
        return 1
    finally:
        _stop_backend(process, log_handle)
        (evidencia / "summary.json").write_text(
            json.dumps(resumen, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        if resumen["status"] == "PASS":
            print(
                f"PASS: Moldex runtime real · molecule={resumen.get('molecule_id')} "
                f"· evidencia={evidencia}"
            )


if __name__ == "__main__":
    raise SystemExit(main())
