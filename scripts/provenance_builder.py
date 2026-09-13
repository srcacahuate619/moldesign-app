# -*- coding: utf-8 -*-
"""
provenance_builder.py — Consumo de provenance.json de los generadores y
emisión del sidecar canónico (FND-06, cierre de garantía futura).

El builder de poses (build_pose_selector_dataset.py) descartaba todo
metadato de corrida. Desde el cierre de FND-06, los tres generadores emiten
un provenance.json canónico (contrato v1.1: clave pid|source|file_stem,
semillas separadas seed_conformer/seed_docking, conformer_id, box,
preparación, engine, experiment_id, created_at ISO 8601) y este módulo lo
consume en la ingesta de poses futuras:

  1. registros_del_trabajo(trabajo): localiza el provenance.json del
     generador (dict o lista de dicts) y filtra los registros del trabajo.
  2. errores_de_coherencia(registro, trabajo): clave exacta
     pid|source|file_stem, identidad del trabajo y esquema del contrato.
  3. construir_sidecar(trabajos): {clave: registro} canónico. Los errores
     (clave duplicada, incoherente, registro inválido o provenance legacy
     pre-cierre) se reportan con detalle y NO se emiten.
  4. emitir_sidecar(registros, out): JSONL determinista (claves ordenadas,
     escritura atómica), 1 registro por corrida.

Solo stdlib. No modifica el dataset histórico sellado
(data/pose_selector_dataset/ es solo lectura): la emisión recibe la ruta de
salida explícita (--sidecar-out del builder), típicamente junto a un dataset
futuro.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
import pose_provenance as pp  # noqa: E402

PDBBIND = PROJECT_ROOT / "data" / "pdbbind"
WORK_V3 = PROJECT_ROOT / "scripts" / ".work_molflex_v3"
RUTA_A = PROJECT_ROOT / "tmp" / "ruta_a"


def ruta_provenance(trabajo: dict) -> Path | None:
    """Ruta del provenance.json del generador del trabajo (o None)."""
    pid = str(trabajo["pid"])
    fuente = str(trabajo["fuente"])
    if fuente == "molflex":
        return WORK_V3 / pid / "provenance.json"
    if fuente == "flexible_redock":
        return PDBBIND / "vina_redock_work" / pid / "provenance.json"
    if fuente == "ruta_a":
        return RUTA_A / pid / str(trabajo["stem"]) / "provenance.json"
    return None


def leer_provenance_json(ruta) -> list:
    """provenance.json (dict o lista de dicts) → lista de registros.

    Un archivo ilegible o con forma desconocida devuelve lista vacía (el
    llamador lo trata como "sin provenance disponible").
    """
    try:
        datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
    except Exception:
        return []
    if isinstance(datos, dict):
        return [datos]
    if isinstance(datos, list):
        return [d for d in datos if isinstance(d, dict)]
    return []


def registros_del_trabajo(trabajo: dict) -> list:
    """Registros de provenance del trabajo (filtrados por identidad).

    Vacío si el generador no emitió provenance.json para esta corrida.
    """
    ruta = ruta_provenance(trabajo)
    if ruta is None or not ruta.is_file():
        return []
    esperados = {campo: str(trabajo[campo])
                 for campo in ("pid", "fuente", "stem")}
    out = []
    for reg in leer_provenance_json(ruta):
        if (str(reg.get("pid")) == esperados["pid"]
                and str(reg.get("source")) == esperados["fuente"]
                and str(reg.get("file_stem")) == esperados["stem"]):
            out.append(reg)
    return out


def errores_de_coherencia(registro: dict, trabajo: dict) -> list:
    """Errores de coherencia del registro contra el trabajo ([] si coherente)."""
    if not isinstance(registro, dict):
        return ["registro_no_es_dict"]
    esperados = {"pid": str(trabajo["pid"]), "source": str(trabajo["fuente"]),
                 "file_stem": str(trabajo["stem"])}
    esperada = pp._clave(esperados["pid"], esperados["source"],
                         esperados["file_stem"])
    errores = []
    if registro.get("key") != esperada:
        errores.append(f"key_incoherente:{registro.get('key')!r}_esperada:"
                       f"{esperada!r}")
    for campo in ("pid", "source", "file_stem"):
        if str(registro.get(campo, "")) != esperados[campo]:
            errores.append(f"{campo}_incoherente:{registro.get(campo)!r}_"
                           f"esperado:{esperados[campo]!r}")
    errores.extend(pp.validar_registro(registro))
    return sorted(set(errores))


def construir_sidecar(trabajos: list) -> tuple:
    """{clave: registro} canónico + lista de errores con detalle.

    Solo se emiten registros con clave única, coherente con la identidad del
    trabajo y con esquema de contrato válido. Los registros legacy
    (provenance.json pre-cierre) se reportan como incoherentes y no se emiten.
    """
    registros = {}
    errores = []
    for t in trabajos:
        clave_t = pp._clave(str(t["pid"]), str(t["fuente"]), str(t["stem"]))
        regs = registros_del_trabajo(t)
        if not regs:
            continue  # generador sin provenance.json: nada que emitir
        if len(regs) > 1:
            errores.append(f"{clave_t}: {len(regs)} registros de provenance "
                           "para el mismo trabajo; no se emite")
            continue
        if clave_t in registros:
            errores.append(f"{clave_t}: clave duplicada entre generadores; "
                           "no se emite")
            continue
        detalle = errores_de_coherencia(regs[0], t)
        if detalle:
            errores.append(f"{clave_t}: {'; '.join(detalle)}; no se emite")
            continue
        registros[clave_t] = regs[0]
    return registros, errores


def emitir_sidecar(registros: dict, out_path) -> int:
    """Escribe el sidecar canónico (JSONL determinista, claves ordenadas,
    escritura atómica). Devuelve el número de registros emitidos."""
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    lineas = [json.dumps(registros[k], ensure_ascii=False)
              for k in sorted(registros)]
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text("\n".join(lineas) + ("\n" if lineas else ""),
                   encoding="utf-8")
    tmp.replace(out)
    return len(lineas)
