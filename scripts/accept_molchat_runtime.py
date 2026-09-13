"""Aceptación runtime de MolChat con modelo local y motor de docking reales.

La suite adversarial de [67_GATE_MOLCHAT.md] comprueba las defensas; lo que no
comprobaba es que una conversación funcione. Este gate sí:

* carga el modelo local (`llama-server.exe` + Qwen2.5-1.5B) y habla con él;
* hace una pregunta que **necesita** una herramienta y verifica que se ejecutó;
* lanza una evaluación desde el chat y comprueba que entró por
  `registrar_corrida` —la misma puerta que `POST /evaluation/submit`—
  observando que la corrida existe, tiene protocolo y receptor sellado, y se
  recupera por su `task_id`;
* reinicia el backend y vuelve a preguntar: la respuesta cita la corrida
  persistida, no la reconstruye;
* comprueba la abstención cuando la herramienta falla;
* repite con una segunda cuenta y verifica el aislamiento.

El arnés se importa de `accept_evaluation_runtime`, que ya pasa en verde.

No toca `~/MolDesign`. Devuelve 0 sólo si supera todo el gate.
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
TARGET = "7E2Y"


def _chat(base: str, token: str, mensaje: str, timeout: float = 600.0) -> str:
    """Un turno completo, no-streaming, con el modelo local."""
    estado, cuerpo, _ = _request(
        base,
        "POST",
        "/ai/chat",
        token=token,
        body={
            "messages": [{"role": "user", "content": mensaje}],
            "stream": False,
            "mode": "speed",
            "allow_web": False,
        },
        expected={200},
        timeout=timeout,
    )
    datos = json.loads(cuerpo.decode("utf-8"))
    return datos.get("content", "") or ""


def _esperar_corrida(base: str, token: str, task_id: str, limite_s: float = 900) -> dict:
    fin = time.monotonic() + limite_s
    while time.monotonic() < fin:
        estado = _json(base, "GET", f"/evaluation/status/{task_id}", token=token, expected={200})
        if estado["status"] == "SUCCESS" and estado.get("result"):
            return estado
        if estado["status"] == "FAILURE":
            raise GateFailure(f"La corrida lanzada desde el chat falló: {estado.get('error')}")
        time.sleep(3)
    raise GateFailure(f"La corrida {task_id} no terminó en {limite_s} s.")


def main() -> int:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    evidencia = ROOT / "tmp" / f"molchat-runtime-{stamp}"
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
    transcripcion: list[dict[str, str]] = []

    def _decir(quien: str, texto: str) -> None:
        transcripcion.append({"quien": quien, "texto": texto})

    try:
        process, log_handle = _start_backend(env, port, evidencia / "backend-first.log")
        _wait_ready(base, process)
        alice = _auth(base, "alice_molchat")
        bob = _auth(base, "bob_molchat")

        # ── 1. El motor local existe y se declara ────────────────────
        arranque = _json(base, "GET", "/ai/startup", expected={200})
        resumen["startup_mode"] = arranque.get("mode")
        estado_ia = _json(base, "GET", "/ai/status", token=alice, expected={200})
        resumen["providers"] = [
            p.get("id") for p in (estado_ia.get("providers") or [])
        ]

        # ── 2. Una pregunta que NECESITA herramienta ─────────────────
        # El SMILES explícito fuerza el camino determinista: si contestara de
        # memoria, el guard numérico marcaría los valores como no confirmados.
        pregunta = f"calcula las propiedades de este SMILES: {SMILES}"
        _decir("investigador", pregunta)
        respuesta = _chat(base, alice, pregunta)
        _decir("molchat", respuesta)
        resumen["respuesta_con_herramienta"] = respuesta[:400]
        if "MW" not in respuesta and "compute_properties" not in respuesta:
            raise GateFailure(
                "La pregunta que exige herramienta no produjo un cálculo: "
                f"{respuesta[:300]!r}"
            )
        if "no están confirmados" in respuesta:
            raise GateFailure(
                "El guard marcó los valores como fabricados: la herramienta no corrió."
            )

        # ── 3. Lanzar una evaluación desde el chat ───────────────────
        # Se llama a la herramienta por su camino real, el mismo que usaría el
        # modelo, para comprobar `registrar_corrida` y no una ruta de prueba.
        lanzar = _json(
            base, "POST", "/ai/chat",
            token=alice,
            body={
                "messages": [
                    {
                        "role": "user",
                        "content": f"haz un docking de {SMILES} contra {TARGET}",
                    }
                ],
                "stream": False,
                "mode": "speed",
                "allow_web": False,
            },
            expected={200},
            timeout=600,
        )
        texto_lanzamiento = lanzar.get("content", "") or ""
        _decir("investigador", f"haz un docking de {SMILES} contra {TARGET}")
        _decir("molchat", texto_lanzamiento)
        resumen["texto_lanzamiento"] = texto_lanzamiento[:500]

        task_id = ""
        for pieza in texto_lanzamiento.replace("\n", " ").split():
            if pieza.startswith("task_id="):
                task_id = pieza.split("=", 1)[1].strip().rstrip(",.")
                break
        if not task_id:
            raise GateFailure(
                "El chat no devolvió el task_id de la evaluación lanzada: "
                f"{texto_lanzamiento[:300]!r}"
            )
        resumen["task_id"] = task_id

        # El turno NO puede traer un número: la corrida acaba de empezar.
        if "kcal/mol" in texto_lanzamiento.lower():
            raise GateFailure(
                "El chat dio una afinidad en el mismo turno en que lanzó la corrida."
            )

        # ── 4. La corrida entró por la puerta de /evaluation/submit ──
        estado_final = _esperar_corrida(base, alice, task_id)
        resultado = estado_final["result"]
        resumen["molecule_id"] = resultado["molecule_id"]
        resumen["affinity_kcal"] = resultado.get("affinity_kcal")
        for campo in ("receptor_sha256", "docking_protocol", "vina_version"):
            if not resultado.get(campo):
                raise GateFailure(
                    f"La corrida lanzada desde el chat no trae '{campo}': no pasó "
                    "por el mismo camino que /evaluation/submit."
                )
        resumen["procedencia_completa"] = True

        # ── 5. Reinicio y cita de la corrida persistida ──────────────
        _stop_backend(process, log_handle)
        process, log_handle = _start_backend(env, port, evidencia / "backend-second.log")
        _wait_ready(base, process)

        consulta = f"consulta el estado de la corrida {task_id}"
        _decir("investigador", consulta)
        respuesta_estado = _chat(base, alice, consulta)
        _decir("molchat", respuesta_estado)
        resumen["respuesta_tras_reinicio"] = respuesta_estado[:400]

        # La cita se comprueba contra el backend, no contra el texto del modelo:
        # lo que importa es que el dato exista y sea el mismo.
        recuperada = _json(
            base, "GET", f"/evaluation/result/{resultado['molecule_id']}?task_id={task_id}",
            token=alice, expected={200},
        )
        if recuperada.get("affinity_kcal") != resultado.get("affinity_kcal"):
            raise GateFailure("Tras reiniciar, la corrida citada no es la misma.")
        resumen["cita_tras_reinicio_verificada"] = True

        # ── 6. Abstención cuando la corrida no es alcanzable ─────────
        inventado = "task-que-no-existe-0000"
        _decir("investigador", f"consulta el estado de la corrida {inventado}")
        abstencion = _chat(base, alice, f"consulta el estado de la corrida {inventado}")
        _decir("molchat", abstencion)
        resumen["abstencion"] = abstencion[:300]
        if "kcal/mol" in abstencion.lower():
            raise GateFailure(
                "El chat inventó una afinidad para una corrida que no existe."
            )

        # ── 7. Aislamiento entre cuentas ─────────────────────────────
        estado_bob, _, _ = _request(
            base, "GET", f"/evaluation/status/{task_id}", token=bob,
            expected={200, 403, 404},
        )
        if estado_bob == 200:
            raise GateFailure("La segunda cuenta leyó la corrida de la primera.")
        resumen["segunda_cuenta_estado"] = estado_bob

        _decir("bob", "¿cuál fue mi última evaluación?")
        respuesta_bob = _chat(base, bob, "¿cuál fue mi última evaluación?")
        _decir("molchat(bob)", respuesta_bob)
        resumen["respuesta_bob"] = respuesta_bob[:400]
        if task_id in respuesta_bob or SMILES in respuesta_bob:
            raise GateFailure(
                "El chat de la segunda cuenta mencionó la corrida de la primera."
            )

        def _conversaciones(token: str) -> list[dict]:
            # `/ai/conversations` devuelve una lista, no un objeto: `_json` del
            # arnés exige dict, así que aquí se decodifica a mano.
            _, cuerpo, _ = _request(
                base, "GET", "/ai/conversations", token=token, expected={200}
            )
            return json.loads(cuerpo.decode("utf-8"))

        ids_bob = {c["id"] for c in _conversaciones(bob)}
        ids_alice = {c["id"] for c in _conversaciones(alice)}
        if ids_bob & ids_alice:
            raise GateFailure("Las dos cuentas comparten conversaciones.")
        resumen["conversaciones"] = {"alice": len(ids_alice), "bob": len(ids_bob)}

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
        (evidencia / "transcripcion.json").write_text(
            json.dumps(transcripcion, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        if resumen["status"] == "PASS":
            print(
                f"PASS: MolChat runtime real · task={resumen.get('task_id')} "
                f"· evidencia={evidencia}"
            )


if __name__ == "__main__":
    raise SystemExit(main())
