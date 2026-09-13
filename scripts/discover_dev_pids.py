#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""discover_dev_pids.py — generador reproducible de dev_seen_pids.json (FND-05).

Escanea EN MODO LECTURA las 8 fuentes locales de pids ya vistos en desarrollo y
escribe el JSON por categoría que consume `scripts/build_confirm_cohort.py`
(opción --dev-pids). Solo biblioteca estándar; determinista (las listas salen
ordenadas y los recorridos usan orden lexicográfico).

Fuentes (reglas de extracción documentadas):

  1. ruta_c:        pids de `data/pose_selector_dataset/poses_{train,val,test}.jsonl`
                    (claves pid/pdb_id/pdb de cada línea).
  2. fase_a:        primera columna del backup
                    `data/pdbbind/INDEX_refined_data.2020.faseA_20260813_184212`.
  3. fase_b_new:    `selected_new_ids` de
                    `data/pdbbind/faseb_selection_manifest.json`.
  4. artifacts_scripts: pids mencionados en `scripts/artifacts_ruta_c_*.json`,
                    `scripts/artifacts_ruta_a.json`, `scripts/artifacts_molflex_*.json`
                    y `scripts/.molflex_cheap_test.json`. Regla conservadora y
                    documentada: tokens `[0-9][a-z0-9]{3}` que aparezcan como
                    CLAVES de dict, o como VALORES de claves cuyo nombre contiene
                    "pid"/"pdb". (Regla actual = superconjunto del conteo histórico.)
  5. gnn_v31:       tokens de `data/gnn_v31/pids_in_dataset.txt`.
  6. target_library: `pdb_ids` de todas las áreas de
                    `data/target_library/targets_manifest.json`.
  7. data_pdbs:     prefijos de 4 caracteres de los nombres de archivo de
                    `data/*.pdb`, `data/pdbs/*.pdb` y `data/targets/**/*.pdb`.
  8. otros_artifacts_data: pids (claves de dict o valores bajo claves con
                    "pid"/"pdb") de los JSON/JSONL de data/{multitarget,
                    molchamb_loto, gnn_fixed, gnn_v2_dataset, backups,
                    box_test_7e2y}. (Regla actual = superconjunto del conteo
                    histórico.)

Uso:

  python scripts/discover_dev_pids.py \
      --out scripts/artifacts_science/FND-05/dev_seen_pids.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

PROYECTO = Path(__file__).resolve().parent.parent
PID_RE = re.compile(r"^[0-9][a-z0-9]{3}$")
TOKEN_RE = re.compile(r"[0-9][a-z0-9]{3}")


def _pids_de_texto(texto: str) -> set[str]:
    """Tokens de 4 caracteres con formato de PDB id (p. ej. 1a4w, 10gs)."""
    return {t for t in TOKEN_RE.findall(texto.lower()) if PID_RE.match(t)}


def _pids_de_json(path: Path) -> set[str]:
    """Pids de un JSON: claves de dict con formato pid o valores bajo claves pid/pdb."""
    try:
        dato = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return set()
    pids: set[str] = set()

    def walk(x, clave: str | None = None) -> None:
        if isinstance(x, dict):
            for k, v in x.items():
                if isinstance(k, str) and PID_RE.match(k.lower()):
                    pids.add(k.lower())
                walk(v, str(k))
        elif isinstance(x, list):
            for v in x:
                walk(v, clave)
        elif isinstance(x, str):
            if PID_RE.match(x.lower()) and clave and ("pid" in clave.lower()
                                                     or "pdb" in clave.lower()):
                pids.add(x.lower())

    walk(dato)
    return pids


def _pids_de_jsonl(path: Path, claves: tuple[str, ...]) -> set[str]:
    """Pids de un JSONL usando el primer campo disponible entre `claves`."""
    pids: set[str] = set()
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for linea in fh:
                try:
                    registro = json.loads(linea)
                except json.JSONDecodeError:
                    continue
                for k in claves:
                    if k in registro:
                        v = str(registro[k]).strip().lower()
                        if PID_RE.match(v):
                            pids.add(v)
                        break
    except OSError:
        pass
    return pids


def fuente_ruta_c() -> set[str]:
    """Pids de las particiones train/val/test del pose_selector_dataset."""
    pids: set[str] = set()
    base = PROYECTO / "data" / "pose_selector_dataset"
    for nombre in ("poses_train.jsonl", "poses_val.jsonl", "poses_test.jsonl"):
        pids |= _pids_de_jsonl(base / nombre, ("pid", "pdb_id", "pdb"))
    return pids


def fuente_fase_a() -> set[str]:
    """Pids de la Fase A (865) desde el backup del índice refined."""
    pids: set[str] = set()
    path = PROYECTO / "data" / "pdbbind" / "INDEX_refined_data.2020.faseA_20260813_184212"
    try:
        for linea in path.read_text(encoding="utf-8", errors="replace").splitlines():
            linea = linea.rstrip("\n")
            if not linea or linea.startswith("#") or "//" not in linea:
                continue
            partes = linea.split()
            if len(partes) >= 6 and PID_RE.match(partes[0].lower()):
                pids.add(partes[0].lower())
    except OSError:
        pass
    return pids


def fuente_fase_b() -> set[str]:
    """Pids nuevos de la Fase B (300) desde el manifest de selección."""
    path = PROYECTO / "data" / "pdbbind" / "faseb_selection_manifest.json"
    try:
        dato = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError):
        return set()
    ids = dato.get("selected_new_ids", [])
    return {str(v).strip().lower() for v in ids if PID_RE.match(str(v).strip().lower())}


def fuente_artifacts_scripts() -> set[str]:
    """Pids mencionados en los artefactos JSON de los scripts de experimentos."""
    base = PROYECTO / "scripts"
    rutas = sorted(base.glob("artifacts_ruta_c_*.json"))
    rutas.append(base / "artifacts_ruta_a.json")
    rutas.extend(sorted(base.glob("artifacts_molflex_*.json")))
    rutas.append(base / ".molflex_cheap_test.json")
    pids: set[str] = set()
    for path in rutas:
        if path.is_file():
            pids |= _pids_de_json(path)
    return pids


def fuente_gnn_v31() -> set[str]:
    """Pids del dataset GNN v3.1 (pids_in_dataset.txt)."""
    path = PROYECTO / "data" / "gnn_v31" / "pids_in_dataset.txt"
    try:
        texto = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set()
    return _pids_de_texto(texto)


def fuente_target_library() -> set[str]:
    """Pids de la librería de targets (targets_manifest.json → pdb_ids)."""
    path = PROYECTO / "data" / "target_library" / "targets_manifest.json"
    try:
        dato = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError):
        return set()
    pids: set[str] = set()
    for area in dato.get("areas", {}).values():
        if isinstance(area, dict):
            for v in area.get("pdb_ids", []):
                v = str(v).strip().lower()
                if PID_RE.match(v):
                    pids.add(v)
    return pids


def fuente_data_pdbs() -> set[str]:
    """Pids de los nombres de archivo de los PDB sueltos de data/ y data/targets/.

    data/ se recorre SIN recursión (solo archivos sueltos; el árbol
    data/pdbbind queda excluido por ser el pool candidato, no desarrollo).
    """
    pids: set[str] = set()
    rutas = list((PROYECTO / "data").glob("*.pdb"))
    rutas += list((PROYECTO / "data").glob("*.PDB"))
    if (PROYECTO / "data" / "pdbs").is_dir():
        rutas += list((PROYECTO / "data" / "pdbs").glob("*.pdb"))
        rutas += list((PROYECTO / "data" / "pdbs").glob("*.PDB"))
    if (PROYECTO / "data" / "targets").is_dir():
        rutas += list((PROYECTO / "data" / "targets").rglob("*.pdb"))
        rutas += list((PROYECTO / "data" / "targets").rglob("*.PDB"))
    for path in rutas:
        m = PID_RE.match(path.name[:4].lower())
        if m:
            pids.add(m.group(0))
    return pids


def fuente_otros_artifacts_data() -> set[str]:
    """Pids de los JSON/JSONL de directorios de artefactos de datos variados."""
    dirs = ["multitarget", "molchamb_loto", "gnn_fixed", "gnn_v2_dataset",
            "backups", "box_test_7e2y"]
    pids: set[str] = set()
    for nombre in dirs:
        raiz = PROYECTO / "data" / nombre
        if not raiz.is_dir():
            continue
        for path in sorted(raiz.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in (".json", ".jsonl"):
                continue
            try:
                texto = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if path.suffix.lower() == ".jsonl":
                for linea in texto.splitlines():
                    try:
                        dato = json.loads(linea)
                    except json.JSONDecodeError:
                        continue
                    pids |= _pids_de_json_from_data(dato)
            else:
                try:
                    dato = json.loads(texto)
                except json.JSONDecodeError:
                    continue
                pids |= _pids_de_json_from_data(dato)
    return pids


def _pids_de_json_from_data(dato) -> set[str]:
    """Extracción de pids desde estructuras JSON ya parseadas (claves o valores)."""
    pids: set[str] = set()

    def walk(x, clave: str | None = None) -> None:
        if isinstance(x, dict):
            for k, v in x.items():
                if isinstance(k, str) and PID_RE.match(k.lower()):
                    pids.add(k.lower())
                walk(v, str(k))
        elif isinstance(x, list):
            for v in x:
                walk(v, clave)
        elif isinstance(x, str):
            if PID_RE.match(x.lower()) and clave and ("pid" in clave.lower()
                                                     or "pdb" in clave.lower()):
                pids.add(x.lower())

    walk(dato)
    return pids


def descubrir() -> dict[str, list[str]]:
    """Ejecuta las 8 fuentes y devuelve {categoria: [pids ordenados]}."""
    fuentes = {
        "ruta_c": fuente_ruta_c,
        "fase_a": fuente_fase_a,
        "fase_b_new": fuente_fase_b,
        "artifacts_scripts": fuente_artifacts_scripts,
        "gnn_v31": fuente_gnn_v31,
        "target_library": fuente_target_library,
        "data_pdbs": fuente_data_pdbs,
        "otros_artifacts_data": fuente_otros_artifacts_data,
    }
    salida: dict[str, list[str]] = {}
    for categoria, fn in fuentes.items():
        salida[categoria] = sorted(fn())
    return salida


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    parser = argparse.ArgumentParser(
        description="Genera dev_seen_pids.json escaneando las 8 fuentes de desarrollo (FND-05).")
    parser.add_argument("--out", required=True,
                        help="ruta del JSON de salida (p. ej. scripts/artifacts_science/FND-05/dev_seen_pids.json)")
    args = parser.parse_args()

    salida = descubrir()
    union = {pid for pids in salida.values() for pid in pids}
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + ".tmp")
    tmp.write_text(json.dumps(salida, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8", newline="\n")
    tmp.replace(out)
    print("Categorías:")
    for categoria, pids in salida.items():
        print(f"  {categoria}: {len(pids)}")
    print(f"Unión deduplicada: {len(union)} pids")
    print(f"Escrito en {out}")


if __name__ == "__main__":
    main()
