"""Cierre FEP-09 con árbol limpio y prueba de bytes versionados antes del sello.

--seal y --finish son pasos separados: se commitea el sello entre ambos.
No modifica el producto ni experimentos ajenos.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

import experiment_manifest as em

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "scripts/artifacts_science/FEP-09-SENSIBILIDAD"
EXP = ART.name


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def clean():
    assert not git("status", "--porcelain"), "Se requiere árbol limpio antes de seal/finish"
    assert not git("diff", "f183e0af", "--", "backend", "frontend", "rescoring", "tools")


def assets():
    paths = list((ROOT / "scripts").glob("fep09_*.py"))
    paths += [ROOT / p for p in ("docs/auditorias/FEP-09-prerregistro.md",
                               "docs/auditorias/FEP-09-reconocimiento.md",
                               "docs/papers/FEP-09-SENSIBILIDAD.md",
                               "docs/auditorias/preparacion-sensibilidad-2026-10-11.md")]
    paths += [p for p in ART.rglob("*") if p.is_file() and p.name not in {"manifest.json", "README.md"}]
    return sorted(set(paths))


def check_tracked(paths):
    relative_paths = [p.relative_to(ROOT).as_posix() for p in paths]
    requests = "".join("HEAD:"+p+"\n" for p in relative_paths).encode("utf-8")
    batch = subprocess.check_output(["git", "cat-file", "--batch"], input=requests, cwd=ROOT)
    position = 0
    for path, relative in zip(paths, relative_paths):
        newline = batch.index(b"\n", position)
        header = batch[position:newline].split()
        assert len(header) == 3 and header[1] == b"blob", "Activo no versionado: "+relative
        size = int(header[2])
        position = newline+1
        stored = memoryview(batch)[position:position+size]
        assert hashlib.sha256(stored).digest() == hashlib.sha256(path.read_bytes()).digest(), relative
        position += size+1
    assert position == len(batch)


def main():
    ap = argparse.ArgumentParser()
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--seal", action="store_true")
    mode.add_argument("--finish", action="store_true")
    args = ap.parse_args()
    clean()
    plan = json.loads((ART / "inventory.json").read_text(encoding="utf-8"))
    rows = [json.loads(l) for l in (ART / "per_complex.jsonl").read_text(encoding="utf-8").splitlines() if l]
    metrics = json.loads((ART / "metrics.json").read_text(encoding="utf-8"))
    assert len(rows) == len(plan["cases"]) == metrics["n_terminal"]
    assert all((ART / "_work" / f"shard-{i}/complete.json").is_file() for i in range(3))
    selected = assets()
    check_tracked(selected)
    assert em.cmd_validate([EXP]) == 0
    if args.seal:
        dataset = sorted({s[k] for s in plan["systems"] for k in ("pdb_path", "sdf_path")})
        dataset.append("E:/MolDesign-science/openff-plb/data/targets.yml")
        runtime = ROOT.parents[1]
        binaries = [runtime / p for p in ("tools/vina/vina.exe", "tools/vina/vina_trace.exe",
                                          "python-embed/python.exe", "python-embed/python311.dll")]
        argv = [EXP, "--dataset", *dataset, "--binaries", *(str(p) for p in binaries),
                "--assets", *(str(p) for p in selected)]
        print(f"Prueba previa: {len(selected)} activos presentes en HEAD con bytes exactos")
        return em.cmd_seal(argv)
    manifest = json.loads((ART / "manifest.json").read_text(encoding="utf-8"))
    assert manifest.get("sealed") and manifest["decision"] == "PENDING"
    start = min(datetime.fromisoformat(r["started_utc"]) for r in rows)
    end = max(datetime.fromisoformat(r["started_utc"])+timedelta(seconds=r["elapsed_s"]) for r in rows)
    gap = metrics["categories"]["hueco_en_el_sitio"]
    rationale = (f"{len(rows)} corridas confirmatorias, producto f183e0af, B/respetar, Vina 8/9/42. "
                 f"Huecos: {gap['detections_route']}/{gap['n_applicable']}, CP95 {gap['cp95_route']}, "
                 f"gate {gap['decision']}; falsa alarma {metrics['false_alarm']['rate']}. "
                 "Estereo n=3, tautómero minoritario y especie con pKa independientes n=0: "
                 "no permiten GO global. Proxies, límites y brazo C fuera del gate estricto. "
                 "Modo tautomérico efectivo entrada; descripción preregistrada canónica incorrecta, "
                 "publicada sin modificar protocolo ni reintentar corridas. "
                 "Duración: reloj de fase confirmatoria entre primer inicio y último término, cápsulas paralelas.")
    return em.cmd_finish([EXP, "--decision", metrics["decision"], "--rationale", rationale,
                          "--duration-seconds", str((end-start).total_seconds())])


if __name__ == "__main__":
    raise SystemExit(main())
