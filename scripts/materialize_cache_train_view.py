#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""materialize_cache_train_view.py — RS-01 IT1/IT2, B4 del maintainer + C2.

Materializa una VISTA train-only del cache de features v0.5/v0.6
(data/pose_selector_dataset/features_v05_progress.jsonl) sin violar la
cuarentena de val/test:

  - ABRE SOLO: (lectura) el cache origen + MF-01-UNION/union_candidates_train.jsonl;
    (escritura) la vista y su manifest. NUNCA abre poses_val.jsonl ni
    poses_test.jsonl (ni ningún otro archivo de split).
  - Lee SOLO los primeros 2739 registros del cache (líneas 2..2740) en UNA
    sola pasada; el manejador del archivo origen nunca supera el fin del
    bloque train. NO se relee el archivo completo ni se hashea el bloque
    val/test del cache (C2: el sha del origen es PROVENANCE NO RECALCULADA).
  - Verifica: índices posicionales idx == 0..2738, split == "train" en todos,
    e identidad posicional (train|pid|source|file_stem|model_idx) contra las
    2739 identidades de la unión original EN EL MISMO ORDEN.
  - Escribe la vista con los BYTES EXACTOS de las líneas del origen (sin
    re-serialización) + cache_view_manifest.json con sha de la vista, bytes
    LEÍDOS del origen (solo el bloque train), rango de registros/bytes,
    provenance del sha del origen (sin recalcular) y verificación posicional.
  - Instrumentación (C2): el manifest registra cuántos bytes leyó el script
    del archivo origen — deben ser exactamente los del bloque train + cabecera.

Determinista: sin timestamps ni aleatoriedad; dos corridas producen bytes
idénticos. Sin pip, sin red, sin commits.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE_ORIGEN = ROOT / "data" / "pose_selector_dataset" / "features_v05_progress.jsonl"
UNION_TRAIN = ROOT / "scripts" / "artifacts_science" / "MF-01-UNION" / "union_candidates_train.jsonl"
OUT_VIEW = ROOT / "scripts" / "artifacts_science" / "RS-01" / "cache_train_only_view.jsonl"
OUT_MANIFEST = ROOT / "scripts" / "artifacts_science" / "RS-01" / "cache_view_manifest.json"

N_TRAIN_ESPERADO = 2739

# Provenance NO recalculada en IT2: sha256 del archivo origen registrada en el
# inventario RS-01 (IT0, assets_entrenamiento_clones.deps_datos). NO se relee
# el archivo completo para volver a calcularla.
SHA_ORIGEN_PROVENANCE = "1d487db9ab5c35ca4e8e74c7b42cddd2e67069ec002e16d9b84052e7a696ce48"

ABIERTOS: list[str] = []


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def registrar(path: Path, modo: str) -> None:
    ABIERTOS.append(f"{modo}:{path.as_posix()}")


def main() -> int:
    # ── 1. Identidades de la unión original (referencia posicional) ──
    identidades_union: list[str] = []
    with open(UNION_TRAIN, encoding="utf-8") as fh:
        registrar(UNION_TRAIN, "lectura")
        for linea in fh:
            if linea.strip():
                identidades_union.append(json.loads(linea)["identity"])
    if len(identidades_union) != N_TRAIN_ESPERADO:
        print(f"FATAL: la unión train tiene {len(identidades_union)} registros "
              f"(se esperaban {N_TRAIN_ESPERADO})")
        return 1

    # ── 2. Cabecera + 2739 registros del cache (bytes exactos, UNA pasada) ──
    # El origen usa CRLF: se lee en binario para preservar los bytes exactos
    # de cada línea (la vista NO re-serializa). El manejador se cierra al
    # terminar el bloque train: NUNCA se lee ni se hashea el resto del archivo.
    with open(CACHE_ORIGEN, "rb") as fh:
        registrar(CACHE_ORIGEN, "lectura")
        cabecera_raw = fh.readline()
        cabecera = json.loads(cabecera_raw.decode("utf-8"))
        inicio_registros = fh.tell()
        lineas_raw: list[bytes] = []
        idx_vistos: list[int] = []
        splits: list[str] = []
        identidades_cache: list[str] = []
        for _ in range(N_TRAIN_ESPERADO):
            linea = fh.readline()
            if not linea:
                print("FATAL: el cache terminó antes de 2739 registros")
                return 1
            lineas_raw.append(linea)
            reg = json.loads(linea.decode("utf-8"))
            idx_vistos.append(int(reg["idx"]))
            splits.append(str(reg["split"]))
            identidades_cache.append(
                f"train|{reg['pid']}|{reg['source']}|{reg['file_stem']}|{reg['model_idx']}"
            )
        fin_registros = fh.tell()
    # El manejador se cerró aquí: bytes leídos del origen = fin_registros
    # (cabecera + bloque train). El bloque val/test del cache NO fue leído.

    # ── 3. Verificaciones posicionales ──
    idx_ok = idx_vistos == list(range(N_TRAIN_ESPERADO))
    split_ok = all(s == "train" for s in splits)
    coincidencias = sum(
        1 for a, b in zip(identidades_cache, identidades_union) if a == b
    )
    identidad_ok = coincidencias == N_TRAIN_ESPERADO
    if not (idx_ok and split_ok and identidad_ok):
        print(f"FATAL: verificación posicional falló (idx_ok={idx_ok}, "
              f"split_ok={split_ok}, identidades {coincidencias}/{N_TRAIN_ESPERADO})")
        return 1

    # ── 4. Vista (bytes exactos leídos del origen, sin relectura) ──
    contenido = b"".join(lineas_raw)
    sha_vista = sha256_bytes(contenido)

    with open(OUT_VIEW, "wb") as fh:
        registrar(OUT_VIEW, "escritura")
        fh.write(contenido)

    # ── 5. Manifest de la vista (determinista, sin timestamps) ──
    manifest = {
        "schema": "rs01_cache_view_manifest_v1",
        "vista": "scripts/artifacts_science/RS-01/cache_train_only_view.jsonl",
        "sha256_vista": sha_vista,
        "n_registros_vista": N_TRAIN_ESPERADO,
        "origen": {
            "archivo": "data/pose_selector_dataset/features_v05_progress.jsonl",
            "sha256_archivo_origen": SHA_ORIGEN_PROVENANCE,
            "provenance_sha_origen": "NO_RECALCULADA (IT2/C2): valor registrado en el "
                                     "inventario RS-01 (assets_entrenamiento_clones.deps_datos, "
                                     "IT0). El script NO relee el archivo completo para hashearlo",
            "cabecera": {
                "version": cabecera.get("version"),
                "n_features_rich": cabecera.get("n_features_rich"),
                "sha256_splits": cabecera.get("sha256_splits"),
                "generated_at_origen": cabecera.get("generated_at"),
            },
        },
        "rango": {
            "registros": f"0..{N_TRAIN_ESPERADO - 1} (idx del cache)",
            "lineas_del_archivo": f"2..{N_TRAIN_ESPERADO + 1} (la línea 1 es la cabecera)",
            "bytes": f"{inicio_registros}..{fin_registros}",
        },
        "instrumentacion_lectura_c2": {
            "bytes_leidos_del_origen": fin_registros,
            "bytes_cabecera": inicio_registros,
            "bytes_bloque_train": fin_registros - inicio_registros,
            "pasadas_sobre_el_origen": 1,
            "bloque_val_test_leido": False,
            "nota": "bytes_leidos_del_origen corresponde exactamente a cabecera + "
                    "2739 registros train; el manejador se cerró en esa posición "
                    "y el archivo origen NO se reabrió",
        },
        "verificacion_posicional": {
            "idx_consecutivos_0_a_2738": idx_ok,
            "split_train_en_los_2739": split_ok,
            "identidades_coincidentes_contra_union": coincidencias,
            "identidades_totales_union": len(identidades_union),
            "identidad_posicional_ok": identidad_ok,
            "vista_construida_de_los_bytes_leidos_sin_relectura": True,
        },
        "archivos_abiertos_por_el_script": ABIERTOS,
        "garantia_cuarentena": (
            "el script NO abre poses_val.jsonl ni poses_test.jsonl; la lectura "
            "del cache terminó exactamente en el registro idx=2738 (una sola "
            "pasada); NO se hasheó el bloque val/test del cache; la lista "
            "'archivos_abiertos_por_el_script' es la auditoría completa"
        ),
        "determinismo": "sin timestamps ni aleatoriedad; dos corridas producen bytes idénticos",
    }
    with open(OUT_MANIFEST, "w", encoding="utf-8") as fh:
        registrar(OUT_MANIFEST, "escritura")
        json.dump(manifest, fh, ensure_ascii=False, indent=2)
        fh.write("\n")

    print(f"Vista OK: {N_TRAIN_ESPERADO} registros | identidades coincidentes: "
          f"{coincidencias}/{N_TRAIN_ESPERADO} | bytes_leidos_origen={fin_registros} "
          f"| sha_vista={sha_vista[:16]}...")
    return 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    sys.exit(main())
