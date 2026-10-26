"""Todo fichero versionado que un sello hashea fuera de artifacts_science/ lleva `-text`.

Sin el atributo, un checkout con core.autocrlf=true lo escribe con CRLF y su sello deja de
validar. Pasó con REC-07-R1: su runner validaba en el worktree donde se selló y era DISTINTO en
un worktree nuevo del mismo commit (lo detectó la entrega de Sol de la fase 1b).
"""
import json
import subprocess
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]


def _rutas_selladas():
    rutas = set()
    for man in (RAIZ / "scripts" / "artifacts_science").glob("*/manifest.json"):
        m = json.loads(man.read_text(encoding="utf-8-sig"))
        for clave in ("dataset_hashes", "binaries_hashes", "assets_hashes", "model_hashes"):
            for r in m.get(clave) or {}:
                r = r.replace("\\", "/")
                if not r.startswith("scripts/artifacts_science/") and ":" not in r and not r.startswith("/"):
                    rutas.add(r)
    return sorted(rutas)


def _git_por_tandas(argumentos, rutas, tanda=200):
    # Una sola llamada con todas las rutas selladas (más de 7000) supera la línea de comandos de Windows (WinError 206).
    return "".join(subprocess.run(["git", *argumentos, "--"] + rutas[i:i + tanda], cwd=RAIZ, capture_output=True,
                                  text=True, check=True).stdout for i in range(0, len(rutas), tanda))


def _sin_atributo(rutas):
    versionadas = _git_por_tandas(["ls-files"], rutas).split()
    salida = _git_por_tandas(["check-attr", "text"], versionadas)
    return [l.split(": text:")[0] for l in salida.splitlines() if not l.endswith(": unset")]


def test_el_detector_ve_una_ruta_sin_atributo():
    assert _sin_atributo(["scripts/sellar_experimento.py"]) == ["scripts/sellar_experimento.py"]


def test_todo_fichero_sellado_y_versionado_lleva_menos_text():
    assert _sin_atributo(_rutas_selladas()) == []
