#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sellar_experimento.py — sellar y cerrar un experimento con su procedencia completa.

`experiment_manifest.py seal` acepta un sello sin entradas, `finish` no registra ninguna
salida y `dependencies.packages` se queda vacío. Un sello así acredita que unos bytes no
cambiaron, pero no qué entradas, qué salidas ni qué paquetes produjeron el resultado: es lo
que la auditoría científica encontró en FEP-04 (SCI-B-045), donde los agregados se pueden
recalcular pero la extracción molecular no se puede regenerar.

`experiment_manifest.py` y `manifest.schema.json` no se tocan: están sellados como activos en
27 experimentos, y el esquema no admite campos nuevos. La regla nueva vive aquí, como la de
SCI-B-016, y deja su registro en `<experimento>/procedencia.json`:

* `sellar` **exige entradas** (`--entradas`) o un motivo declarado (`--sin-entradas`), y
  registra el intérprete y las versiones de todos los paquetes instalados;
* `cerrar` **exige las salidas** (`metrics.json` no vacío y `per_complex.jsonl`) y registra el
  SHA-256 de cada fichero de salida antes de escribir la decisión;
* `comprobar` verifica que entradas y salidas siguen teniendo esos hashes.

El sello y la decisión los sigue escribiendo `experiment_manifest.py`, igual que siempre.
`scripts/tests/test_procedencia_obligatoria.py` falla si un experimento creado desde el
2026-10-23 no tiene `procedencia.json` completa: los sellados antes no se tocan.

Uso:
    python scripts/sellar_experimento.py sellar ID --entradas RUTA... [--binarios RUTA...] [--activos RUTA...]
    python scripts/sellar_experimento.py sellar ID --sin-entradas "motivo" [...]
    python scripts/sellar_experimento.py cerrar ID --decision NO_GO --razon "..." [--duracion-s N]
    python scripts/sellar_experimento.py comprobar ID
"""
from __future__ import annotations

import argparse
import importlib.metadata
import importlib.util
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROCEDENCIA = "procedencia.json"
SALIDAS = ("metrics.json", "per_complex.jsonl", "failures.jsonl")
#: Los experimentos creados desde esta fecha deben llevar procedencia.json completa.
OBLIGATORIA_DESDE = "2026-10-23T00:00:00+00:00"


def _manifest_tool():
    """El módulo sellado, importado sin modificarlo (igual que validar_sellos.py)."""
    ruta = Path(__file__).resolve().parent / "experiment_manifest.py"
    spec = importlib.util.spec_from_file_location("experiment_manifest", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def paquetes_instalados() -> List[str]:
    nombres = {}
    for dist in importlib.metadata.distributions():
        nombre = dist.metadata.get("Name")
        if nombre:
            nombres[nombre.lower()] = f"{nombre}=={dist.version}"
    return [nombres[k] for k in sorted(nombres)]


def _hashes(em, rutas: Optional[List[str]]) -> Dict[str, str]:
    salida: Dict[str, str] = {}
    for ruta in rutas or []:
        salida.update(em._collect_hashes(ruta))
    return salida


def _escribir(dir_exp: Path, datos: Dict[str, Any]) -> None:
    (dir_exp / PROCEDENCIA).write_text(json.dumps(datos, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                                       encoding="utf-8", newline="\n")


def _leer(dir_exp: Path) -> Dict[str, Any]:
    ruta = dir_exp / PROCEDENCIA
    return json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {}


def sellar(args, em=None) -> int:
    em = em or _manifest_tool()
    if not args.entradas and not args.sin_entradas:
        print("ERROR: un sello necesita sus entradas (--entradas) o el motivo de que no las tenga "
              "(--sin-entradas). Sin ellas el resultado no se puede regenerar (SCI-B-045).", file=sys.stderr)
        return 1
    if args.entradas and args.sin_entradas:
        print("ERROR: --entradas y --sin-entradas se excluyen.", file=sys.stderr)
        return 1
    try:
        entradas = _hashes(em, args.entradas)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if args.entradas and not entradas:
        print("ERROR: las rutas de --entradas no contienen ningún fichero.", file=sys.stderr)
        return 1
    cli = ["seal", args.experiment_id]
    for bandera, valores in (("--dataset", args.entradas), ("--binaries", args.binarios), ("--assets", args.activos)):
        if valores:
            cli += [bandera, *valores]
    codigo = em.main(cli)
    if codigo != 0:
        return codigo
    dir_exp = em._experiment_dir(args.experiment_id)
    _escribir(dir_exp, {
        "experimento": args.experiment_id,
        "sellado_utc": datetime.now(timezone.utc).isoformat(),
        "entradas": entradas,
        "entradas_ausentes_motivo": args.sin_entradas,
        "interprete": {"python": platform.python_version(), "ejecutable": Path(sys.executable).name},
        "paquetes": paquetes_instalados(),
        "salidas": {},
    })
    return 0


def cerrar(args, em=None) -> int:
    em = em or _manifest_tool()
    dir_exp = em._experiment_dir(args.experiment_id)
    procedencia = _leer(dir_exp)
    if not procedencia:
        print(f"ERROR: {PROCEDENCIA} no existe: sella con este script antes de cerrar.", file=sys.stderr)
        return 1
    metrics = dir_exp / "metrics.json"
    if not metrics.exists() or json.loads(metrics.read_text(encoding="utf-8") or "{}") == {}:
        print("ERROR: metrics.json está vacío: no hay salida que registrar.", file=sys.stderr)
        return 1
    if not (dir_exp / "per_complex.jsonl").exists():
        print("ERROR: falta per_complex.jsonl.", file=sys.stderr)
        return 1
    salidas = {}
    for nombre in SALIDAS:
        if (dir_exp / nombre).exists():
            salidas.update(em._collect_hashes(str(dir_exp / nombre)))
    try:
        salidas.update(_hashes(em, args.salidas))
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    cli = ["finish", args.experiment_id, "--decision", args.decision, "--rationale", args.razon]
    if args.duracion_s is not None:
        cli += ["--duration-seconds", str(args.duracion_s)]
    codigo = em.main(cli)
    if codigo != 0:
        return codigo
    procedencia["salidas"] = salidas
    procedencia["cerrado_utc"] = datetime.now(timezone.utc).isoformat()
    procedencia["decision"] = args.decision
    _escribir(dir_exp, procedencia)
    return 0


def comprobar(experiment_id: str, em=None) -> List[str]:
    """Fallos de procedencia: vacía, sin entradas ni motivo, sin salidas o con un hash distinto."""
    em = em or _manifest_tool()
    dir_exp = em._experiment_dir(experiment_id)
    p = _leer(dir_exp)
    if not p:
        return [f"{experiment_id}: falta {PROCEDENCIA}"]
    fallos = []
    if not p.get("entradas") and not p.get("entradas_ausentes_motivo"):
        fallos.append(f"{experiment_id}: sin entradas ni motivo")
    if not p.get("paquetes"):
        fallos.append(f"{experiment_id}: sin versiones de paquetes")
    if not p.get("salidas"):
        fallos.append(f"{experiment_id}: sin salidas registradas (¿se cerró con este script?)")
    base = em._git_toplevel()
    for grupo in ("entradas", "salidas"):
        for guardada, esperado in (p.get(grupo) or {}).items():
            ruta = em._resolve_stored_path(guardada, base)
            if not Path(ruta).is_file():
                fallos.append(f"{experiment_id}: {grupo} ausente: {guardada}")
            elif em._sha256_file(ruta) != esperado:
                fallos.append(f"{experiment_id}: {grupo} con otro hash: {guardada}")
    return fallos


def fallos_de_procedencia(em=None) -> List[str]:
    """Los experimentos sellados creados desde OBLIGATORIA_DESDE sin procedencia completa.

    Los anteriores no se miran: se sellaron con la regla vieja y no se tocan.
    """
    em = em or _manifest_tool()
    fallos: List[str] = []
    for manifest in sorted(Path(em.ARTIFACTS_BASE).glob("*/manifest.json")):
        try:
            m = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        creado = m.get("created_at")
        if not m.get("sealed") or not creado:
            continue
        if datetime.fromisoformat(creado) >= datetime.fromisoformat(OBLIGATORIA_DESDE):
            fallos += comprobar(manifest.parent.name, em)
    return fallos


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Sellar y cerrar con procedencia completa")
    sub = ap.add_subparsers(dest="orden", required=True)
    s = sub.add_parser("sellar")
    s.add_argument("experiment_id")
    s.add_argument("--entradas", nargs="+")
    s.add_argument("--sin-entradas", dest="sin_entradas")
    s.add_argument("--binarios", nargs="+")
    s.add_argument("--activos", nargs="+")
    c = sub.add_parser("cerrar")
    c.add_argument("experiment_id")
    c.add_argument("--decision", required=True, choices=["GO", "NO_GO", "INCONCLUSIVE"])
    c.add_argument("--razon", required=True)
    c.add_argument("--duracion-s", dest="duracion_s", type=float)
    c.add_argument("--salidas", nargs="+", help="salidas adicionales a las estándar")
    k = sub.add_parser("comprobar")
    k.add_argument("experiment_id")
    args = ap.parse_args(argv)
    if args.orden == "sellar":
        return sellar(args)
    if args.orden == "cerrar":
        return cerrar(args)
    fallos = comprobar(args.experiment_id)
    for f in fallos:
        print(f)
    print("procedencia completa" if not fallos else f"{len(fallos)} fallo(s)")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
