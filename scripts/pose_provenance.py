# -*- coding: utf-8 -*-
"""
pose_provenance.py — Contrato de provenance de poses y verificador (FND-06).

Implementa el contrato canónico de provenance definido en
`scripts/artifacts_science/FND-06/DESIGN.md` (docs/49, Cartera A, FND-06):

    "Provenance de poses explica parte del error" — persistir source, seed,
    conformer, exhaustiveness, box y preparación. Gate: 100% de poses
    experimentales trazables.

Contenido:

  - construir_registro(...): arma un registro de provenance válido según el
    contrato v1 (campos obligatorios + opcionales recomendados).
  - validar_registro(record): errores de esquema de un registro.
  - validar_lote(poses, provenance): verifica que TODAS las poses tienen
    provenance con los campos obligatorios; devuelve un reporte determinista
    de cobertura por campo y por fuente.

CLI (solo stdlib):

  python scripts/pose_provenance.py --check POSES... [--provenance sidecar|inline]
      [--sidecar FILE] [--strict-unknown] [--out-dir DIR]

      Verifica un lote de poses y escribe el reporte de cobertura. Código de
      salida 1 si hay poses sin provenance, registros inválidos o campos
      obligatorios faltantes; con --strict-unknown también falla si algún
      campo obligatorio está marcado "unknown" (gate de poses NUEVAS).

  python scripts/pose_provenance.py --report POSES... [--provenance ...]
      [--sidecar FILE] [--report-file FILE]

      Genera solo la tabla de cobertura (siempre termina con exit 0).

Modos de provenance:

  sidecar (default): registros en un JSONL externo claveados por
    "pid|source|file_stem" (--sidecar; si se omite, busca
    "poses_provenance.jsonl" junto al primer archivo de poses).
  inline: cada línea de poses lleva su registro bajo la clave "provenance".

El valor "unknown" (string) es el marcador honesto de irrecoverable: el campo
está presente, pero la fuente original no lo registró. Un campo AUSENTE es una
violación del contrato (fallo de esquema), no un desconocido.

Familia de semillas (cierre de garantía futura, 2026-08-15): el canónico
futuro separa `seed_conformer` (semilla de conformeros, p. ej. ETKDG; "crystal"
si el input es la conformación cristalográfica, sin generación estocástica) y
`seed_docking` (semilla de Vina --seed preregistrada). El histórico usa la
forma legacy `seed`. El verificador acepta ambas formas.

Endurecimiento del sidecar (mismo cierre):

  - clave duplicada en el sidecar → ERROR (nunca se sobrescribe en silencio);
  - coherencia: `key` debe ser exactamente `{pid}|{source}|{file_stem}` y,
    en modo sidecar, cada pose debe tener su clave presente;
  - `created_at`: si no es "unknown", debe ser ISO 8601 parseable por
    datetime.fromisoformat.

Salidas deterministas: orden canónico de campos y fuentes, sin marcas de
tiempo. Dos corridas sobre los mismos insumos producen bytes idénticos.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# ───────────────────────── contrato canónico v1 ────────────────────────────

CAMPOS_OBLIGATORIOS = [
    "source", "seed", "conformer_id", "exhaustiveness", "num_modes",
    "box", "preparation", "engine", "experiment_id", "created_at",
]
CAMPOS_OPCIONALES_RECOMENDADOS = ["cluster_id", "dedup_rmsd_threshold", "timeout"]
FUENTES = ("molflex", "flexible_redock", "ruta_a", "futuro")
METODOS_BOX = ("center_from_crystal_ligand", "molpocket_top1", "fixed")
DESCONOCIDO = "unknown"

# Sub-campos requeridos dentro de los campos compuestos (dict).
SUBCAMPOS = {
    "box": ("center", "size", "method"),
    "preparation": (("ligand", ("method", "tool")),
                    ("receptor", ("protonation", "tool"))),
    "engine": ("name", "version"),
}

CLAVE_SEPARADOR = "|"


# ───────────────────────── construcción de registros ───────────────────────

def _clave(pid: str, source: str, file_stem: str) -> str:
    """Clave canónica de un registro de provenance (corrida)."""
    return CLAVE_SEPARADOR.join([pid, source, file_stem])


def _es_desconocido(v) -> bool:
    return isinstance(v, str) and v == DESCONOCIDO


def construir_registro(pid, source, file_stem, seed=None, conformer_id=None,
                       exhaustiveness=None, num_modes=None, box=None,
                       preparation=None, engine=None, experiment_id=None,
                       created_at=None, seed_conformer=None, seed_docking=None,
                       **opcionales):
    """Arma un registro de provenance válido según el contrato.

    Parámetros:
      pid, source, file_stem: identidad de la corrida (clave).
      seed: forma legacy (int, lista de int, o "unknown") para registros
        históricos. Excluyente con seed_conformer/seed_docking.
      seed_conformer, seed_docking: forma canónica futura (semilla de
        conformeros y semilla de docking; int, lista de int, "unknown", y
        además "crystal" para seed_conformer cuando el input es la
        conformación cristalográfica sin generación estocástica).
      conformer_id: int (índice de conformero), "crystal" o "unknown".
      exhaustiveness, num_modes: int o "unknown".
      box: dict con center (lista de 3 números o "unknown"), size (idem) y
        method (center_from_crystal_ligand|molpocket_top1|fixed).
      preparation: dict con ligand {method, tool, version} y
        receptor {protonation, tool}.
      engine: dict con name y version.
      experiment_id: identificador del experimento/corrida.
      created_at: ISO 8601 o "unknown".
      **opcionales: campos opcionales recomendados (cluster_id,
        dedup_rmsd_threshold, timeout) y extensiones libres.

    Devuelve el registro (dict) con "key" calculada. No valida el esquema;
    use validar_registro para eso.
    """
    registro = {
        "key": _clave(str(pid), str(source), str(file_stem)),
        "pid": str(pid),
        "source": source,
        "file_stem": str(file_stem),
    }
    if seed_conformer is not None or seed_docking is not None:
        registro["seed_conformer"] = seed_conformer
        registro["seed_docking"] = seed_docking
    else:
        registro["seed"] = seed
    registro.update({
        "conformer_id": conformer_id,
        "exhaustiveness": exhaustiveness,
        "num_modes": num_modes,
        "box": box,
        "preparation": preparation,
        "engine": engine,
        "experiment_id": experiment_id,
        "created_at": created_at,
    })
    registro.update(opcionales)
    return registro


# ───────────────────────── validación de registros ─────────────────────────

def _semilla_valida(v, permitir_crystal: bool = False) -> bool:
    """Una semilla es válida si es int, lista de int, "unknown" o, para
    seed_conformer, "crystal" (input cristalográfico determinista)."""
    if _es_desconocido(v):
        return True
    if isinstance(v, int):
        return True
    if isinstance(v, list) and all(isinstance(x, int) for x in v):
        return True
    if permitir_crystal and isinstance(v, str) and v == "crystal":
        return True
    return False


def _incoherencias_de_clave(record) -> list:
    """Incoherencias de identidad del registro (clave vs pid/source/file_stem)."""
    if not isinstance(record, dict) or "key" not in record:
        return ["falta_campo:key"]
    esperada = _clave(str(record.get("pid", "")), str(record.get("source", "")),
                      str(record.get("file_stem", "")))
    if record["key"] != esperada:
        return [f"key_incoherente:{record['key']!r}_esperada:{esperada!r}"]
    return []


def validar_registro(record) -> list:
    """Errores de esquema del registro (lista vacía si es válido)."""
    errores = []
    if not isinstance(record, dict):
        return ["registro_no_es_dict"]
    # La coherencia de clave aplica cuando el registro porta "key" (canónico).
    # Los registros inline legacy pueden carecer de key/pid/file_stem.
    if "key" in record:
        errores.extend(_incoherencias_de_clave(record))
    # Familia de semillas: canónico futuro = seed_conformer + seed_docking;
    # legacy histórico = seed. Ambas formas son válidas y excluyentes.
    if "seed_conformer" in record or "seed_docking" in record:
        for sub in ("seed_conformer", "seed_docking"):
            if sub not in record:
                errores.append(f"falta_campo_obligatorio:{sub}")
                continue
            v = record[sub]
            if not _semilla_valida(v, permitir_crystal=(sub == "seed_conformer")):
                errores.append(f"{sub}_invalido:{v!r}")
    elif "seed" not in record:
        errores.append("falta_campo_obligatorio:seed")
    elif not _semilla_valida(record["seed"]):
        errores.append(f"seed_invalido:{record['seed']!r}")
    for campo in CAMPOS_OBLIGATORIOS:
        if campo == "seed":
            continue  # validada arriba en la familia de semillas
        if campo not in record:
            errores.append(f"falta_campo_obligatorio:{campo}")
            continue
        v = record[campo]
        if campo == "source":
            if v not in FUENTES:
                errores.append(f"source_invalido:{v!r}")
        elif campo == "conformer_id":
            if not (_es_desconocido(v) or isinstance(v, int)
                    or v == "crystal"):
                errores.append(f"conformer_id_invalido:{v!r}")
        elif campo in ("exhaustiveness", "num_modes"):
            if not (_es_desconocido(v) or isinstance(v, int)):
                errores.append(f"{campo}_invalido:{v!r}")
        elif campo == "box":
            if not _es_desconocido(v):
                if not isinstance(v, dict):
                    errores.append("box_invalido:no_dict")
                else:
                    if "method" in v and v["method"] not in METODOS_BOX \
                            and not _es_desconocido(v["method"]):
                        errores.append(f"box_method_invalido:{v['method']!r}")
                    for sub in ("center", "size"):
                        s = v.get(sub)
                        if not (_es_desconocido(s) or (
                                isinstance(s, list) and len(s) == 3
                                and all(isinstance(x, (int, float))
                                        and not isinstance(x, bool)
                                        for x in s))):
                            errores.append(f"box_{sub}_invalido:{s!r}")
        elif campo == "preparation":
            if not _es_desconocido(v):
                if not isinstance(v, dict):
                    errores.append("preparation_invalido:no_dict")
                else:
                    for rama, subs in (("ligand", ("method", "tool")),
                                       ("receptor", ("protonation", "tool"))):
                        d = v.get(rama)
                        if not isinstance(d, dict):
                            errores.append(f"preparation_{rama}_no_dict")
                            continue
                        for sub in subs:
                            s = d.get(sub)
                            if not (_es_desconocido(s) or isinstance(s, str)):
                                errores.append(
                                    f"preparation_{rama}_{sub}_invalido:{s!r}")
        elif campo == "engine":
            if not _es_desconocido(v):
                if not isinstance(v, dict):
                    errores.append("engine_invalido:no_dict")
                else:
                    for sub in ("name", "version"):
                        s = v.get(sub)
                        if not (_es_desconocido(s) or isinstance(s, str)):
                            errores.append(f"engine_{sub}_invalido:{s!r}")
        elif campo == "experiment_id":
            if not (_es_desconocido(v) or isinstance(v, str)):
                errores.append(f"experiment_id_invalido:{v!r}")
        elif campo == "created_at":
            if not (_es_desconocido(v) or isinstance(v, str)):
                errores.append(f"created_at_invalido:{v!r}")
            elif isinstance(v, str) and v != DESCONOCIDO:
                try:
                    datetime.fromisoformat(v)
                except ValueError:
                    errores.append(f"created_at_no_iso8601:{v!r}")
    return errores


# ───────────────────────── clasificación por campo ─────────────────────────

def _estado_familia_semilla(record: dict) -> str:
    """Estado de la familia de semillas: combina seed_conformer/seed_docking
    (canónico futuro) o seed (legacy histórico)."""
    if "seed_conformer" in record or "seed_docking" in record:
        for sub in ("seed_conformer", "seed_docking"):
            if sub not in record:
                return "faltante"
        estado = "conocido"
        for sub in ("seed_conformer", "seed_docking"):
            if _es_desconocido(record[sub]):
                estado = "unknown"
        return estado
    if "seed" not in record:
        return "faltante"
    return "unknown" if _es_desconocido(record["seed"]) else "conocido"


def clasificar_campo(record: dict, campo: str) -> str:
    """Estado de un campo obligatorio: 'conocido' | 'unknown' | 'faltante'."""
    if campo == "seed":
        return _estado_familia_semilla(record)
    if campo not in record:
        return "faltante"
    v = record[campo]
    if campo in SUBCAMPOS:
        if _es_desconocido(v):
            return "unknown"
        if not isinstance(v, dict):
            return "faltante"
        if campo == "preparation":
            estado = "conocido"
            for rama, subs in SUBCAMPOS[campo]:
                d = v.get(rama)
                if not isinstance(d, dict):
                    return "faltante"
                for sub in subs:
                    if sub not in d:
                        return "faltante"
                    if _es_desconocido(d[sub]):
                        estado = "unknown"
            return estado
        for sub in SUBCAMPOS[campo]:
            if sub not in v:
                return "faltante"
            if _es_desconocido(v[sub]):
                return "unknown"
        return "conocido"
    return "unknown" if _es_desconocido(v) else "conocido"


# ───────────────────────── carga de insumos ────────────────────────────────

def _abrir_jsonl(ruta) -> list:
    """Lee un JSONL como lista de dicts (líneas vacías ignoradas)."""
    salida = []
    with open(ruta, "r", encoding="utf-8") as fh:
        for linea in fh:
            linea = linea.strip()
            if not linea:
                continue
            salida.append(json.loads(linea))
    return salida


def cargar_poses(rutas) -> list:
    """Carga uno o varios JSONL de poses (en el orden dado)."""
    poses = []
    for ruta in rutas:
        poses.extend(_abrir_jsonl(ruta))
    return poses


def cargar_provenance_sidecar(ruta) -> dict:
    """Sidecar JSONL → {clave: registro}.

    Estricto: un registro sin "key" o una clave duplicada lanza ValueError
    con detalle — el contrato exige una clave única por corrida y nunca se
    sobrescribe en silencio.
    """
    registros = {}
    for num_linea, reg in enumerate(_abrir_jsonl(ruta), 1):
        if not isinstance(reg, dict) or "key" not in reg:
            raise ValueError(
                f"registro sin clave en la linea {num_linea} del sidecar "
                f"{ruta}: el contrato exige key = pid|source|file_stem")
        clave = reg["key"]
        if clave in registros:
            raise ValueError(
                f"clave duplicada {clave!r} en la linea {num_linea} del "
                f"sidecar {ruta}: una clave por corrida")
        registros[clave] = reg
    return registros


def _resolver_registro(pose, registros: dict, modo: str) -> dict | None:
    """Registro de provenance de una pose, o None si no lo tiene."""
    if modo == "inline":
        reg = pose.get("provenance")
        return reg if isinstance(reg, dict) else None
    if isinstance(pose, dict) and all(k in pose for k in
                                      ("pid", "source", "file_stem")):
        clave = _clave(str(pose["pid"]), str(pose["source"]),
                       str(pose["file_stem"]))
        return registros.get(clave)
    return None


# ───────────────────────── validación de lote ──────────────────────────────

def validar_lote(poses, provenance=None) -> dict:
    """Verifica que TODAS las poses tienen provenance con campos obligatorios.

    Parámetros:
      poses: ruta(s) a JSONL de poses, o lista de dicts de poses.
      provenance: None → modo inline (clave "provenance" en cada pose);
        ruta a sidecar JSONL, o dict {clave: registro}.

    Devuelve un reporte determinista:

      {n_poses, n_sin_provenance, n_registros, n_registros_invalidos,
       registros_invalidos, campos, por_fuente}
    """
    if isinstance(poses, (str, Path)):
        poses = cargar_poses([poses])
    elif all(isinstance(x, (str, Path)) for x in poses):
        poses = cargar_poses(list(poses))

    if provenance is None:
        modo = "inline"
        registros = {}
    elif isinstance(provenance, dict):
        modo = "sidecar"
        registros = provenance
    else:
        modo = "sidecar"
        registros = cargar_provenance_sidecar(provenance)

    # Coherencia de identidad de los registros del sidecar (clave canónica).
    incoherencias = []
    if modo == "sidecar":
        for clave, reg in registros.items():
            detalle = _incoherencias_de_clave(reg)
            if detalle:
                incoherencias.append({"key": clave, "detalle": detalle})

    conteo_campos = {c: {"conocido": 0, "unknown": 0, "faltante": 0}
                     for c in CAMPOS_OBLIGATORIOS}
    por_fuente = {f: {"n_poses": 0, "sin_provenance": 0,
                      "campos": {c: {"conocido": 0, "unknown": 0, "faltante": 0}
                                 for c in CAMPOS_OBLIGATORIOS}}
                  for f in FUENTES}
    n_sin = 0
    invalidas = {}
    pids_sin = set()
    claves_sin = set()

    for pose in poses:
        fuente = str(pose.get("source", "?"))
        bloque = por_fuente.get(fuente)
        if bloque is None:
            por_fuente.setdefault(fuente, {"n_poses": 0, "sin_provenance": 0,
                                           "campos": {c: {"conocido": 0,
                                                          "unknown": 0,
                                                          "faltante": 0}
                                                      for c in
                                                      CAMPOS_OBLIGATORIOS}})
            bloque = por_fuente[fuente]
        bloque["n_poses"] += 1
        reg = _resolver_registro(pose, registros, modo)
        if reg is None:
            n_sin += 1
            bloque["sin_provenance"] += 1
            if isinstance(pose, dict) and pose.get("pid"):
                pids_sin.add(str(pose["pid"]))
            if modo == "sidecar" and isinstance(pose, dict) and all(
                    k in pose for k in ("pid", "source", "file_stem")):
                claves_sin.add(_clave(str(pose["pid"]), str(pose["source"]),
                                      str(pose["file_stem"])))
            continue
        clave = reg.get("key", "?")
        errores = validar_registro(reg)
        if errores:
            invalidas.setdefault(clave, errores)
            n_sin += 1
            bloque["sin_provenance"] += 1
            continue
        for campo in CAMPOS_OBLIGATORIOS:
            estado = clasificar_campo(reg, campo)
            conteo_campos[campo][estado] += 1
            bloque["campos"][campo][estado] += 1

    reporte = {
        "n_poses": len(poses),
        "n_sin_provenance": n_sin,
        "n_registros": len(registros) if modo == "sidecar" else None,
        "n_registros_invalidos": len(invalidas),
        "registros_invalidos": [{"key": k, "errores": sorted(set(v))}
                                for k, v in sorted(invalidas.items())],
        "n_incoherencias": len(incoherencias),
        "incoherencias": incoherencias,
        "claves_sin_provenance": sorted(claves_sin),
        "campos": conteo_campos,
        "por_fuente": {f: por_fuente[f] for f in sorted(por_fuente)},
        "pids_sin_provenance": sorted(pids_sin),
        "modo": modo,
    }
    return reporte


# ───────────────────────── reporte legible ─────────────────────────────────

def _pct(conocido, total) -> str:
    if total == 0:
        return "  n/a "
    return f"{100.0 * conocido / total:5.1f}%"


def tabla_cobertura(reporte: dict) -> str:
    """Tabla de cobertura por campo y fuente (texto determinista)."""
    lineas = []
    lineas.append("== Cobertura de provenance por campo y fuente (FND-06) ==")
    n_reg = reporte.get("n_registros")
    reg_txt = str(n_reg) if n_reg is not None else "inline"
    lineas.append(f"modo: {reporte['modo']} | poses: {reporte['n_poses']} | "
                  f"sin provenance: {reporte['n_sin_provenance']} | "
                  f"registros: {reg_txt} | "
                  f"registros invalidos: {reporte['n_registros_invalidos']}")
    lineas.append("")

    fuentes = [f for f in sorted(reporte["por_fuente"])
               if reporte["por_fuente"][f]["n_poses"] > 0]
    encabezados = ["campo"] + [f"{f}({reporte['por_fuente'][f]['n_poses']})"
                               for f in fuentes] + ["total"]
    filas = []
    for campo in CAMPOS_OBLIGATORIOS:
        fila = [campo]
        total = {"conocido": 0, "unknown": 0, "faltante": 0}
        for f in fuentes:
            c = reporte["por_fuente"][f]["campos"][campo]
            n = sum(c.values())
            celda = (f"{c['conocido']}/{c['unknown']}/{c['faltante']} "
                     f"{_pct(c['conocido'], n).strip()}")
            fila.append(celda)
            for k in total:
                total[k] += c[k]
        n = sum(total.values())
        fila.append(f"{total['conocido']}/{total['unknown']}/{total['faltante']} "
                    f"{_pct(total['conocido'], n).strip()}")
        filas.append(fila)

    anchos = [max(len(fila[i]) for fila in [encabezados] + filas)
              for i in range(len(encabezados))]
    fmt = "  ".join(f"{{:<{a}}}" for a in anchos)
    lineas.append(fmt.format(*encabezados))
    lineas.append("  ".join("-" * a for a in anchos))
    for fila in filas:
        lineas.append(fmt.format(*fila))
    lineas.append("")
    lineas.append("Celda: conocido/unknown/faltante + % conocido "
                  "(faltante = sin clave en el registro).")
    return "\n".join(lineas)


def _trazabilidad_poses(poses, registros: dict, modo: str) -> tuple:
    """(n_poses con los 10 campos conocidos, n_poses con provenance pero
    incompletas, porcentaje de completas sobre el total)."""
    completas = 0
    parciales = 0
    for pose in poses:
        reg = _resolver_registro(pose, registros, modo)
        if reg is None or validar_registro(reg):
            continue
        if all(clasificar_campo(reg, c) == "conocido"
               for c in CAMPOS_OBLIGATORIOS):
            completas += 1
        else:
            parciales += 1
    pct = round(100.0 * completas / len(poses), 2) if poses else 0.0
    return completas, parciales, pct


# ───────────────────────── artefactos de auditoría ─────────────────────────

def _razones_por_grupo(poses, registros: dict, modo: str) -> dict:
    """{(fuente, campo, estado): (razones set, pids set)} para unknown/faltante."""
    grupos = {}
    for pose in poses:
        reg = _resolver_registro(pose, registros, modo)
        if not isinstance(reg, dict) or validar_registro(reg):
            continue
        fuente = str(pose.get("source", "?"))
        for campo in CAMPOS_OBLIGATORIOS:
            estado = clasificar_campo(reg, campo)
            if estado == "conocido":
                continue
            clave_g = (fuente, campo, estado)
            if clave_g not in grupos:
                grupos[clave_g] = (set(), set())
            rec = reg.get("recovery", {})
            razon = rec.get(campo)
            if isinstance(razon, str):
                grupos[clave_g][0].add(razon)
            else:
                grupos[clave_g][0].add("sin_registro_de_recuperacion")
            grupos[clave_g][1].add(str(pose.get("pid", "?")))
    return grupos


def escribir_artefactos(reporte: dict, poses, registros: dict, modo: str,
                        out_dir) -> None:
    """Escribe metrics.json, failures.jsonl y per_complex.jsonl (deterministas)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    completas, parciales, pct = _trazabilidad_poses(poses, registros, modo)
    irrecuperables = {}
    for campo in CAMPOS_OBLIGATORIOS:
        irrecuperables[campo] = {
            f: bloque["campos"][campo]["unknown"]
            for f, bloque in sorted(reporte["por_fuente"].items())
        }
    metrics = {
        "n_poses": reporte["n_poses"],
        "n_sin_provenance": reporte["n_sin_provenance"],
        "n_registros": reporte["n_registros"],
        "n_registros_invalidos": reporte["n_registros_invalidos"],
        "cobertura_por_campo": reporte["campos"],
        "cobertura_por_fuente": reporte["por_fuente"],
        "poses_completamente_trazables": completas,
        "poses_parcialmente_trazables": parciales,
        "pct_poses_completamente_trazables": pct,
        "unknown_por_campo_fuente": irrecuperables,
        "notas": [
            "Determinista: dos corridas sobre los mismos insumos producen "
            "bytes identicos (sin marcas de tiempo).",
            "Regla del laboratorio: lo irrecuperable se marca 'unknown' con "
            "justificacion en failures.jsonl, nunca se inventa.",
        ],
    }
    _escribir_json_atomico(out_dir / "metrics.json", metrics)

    grupos = _razones_por_grupo(poses, registros, modo)
    lineas = []
    for (fuente, campo, estado) in sorted(grupos):
        razones, pids = grupos[(fuente, campo, estado)]
        lineas.append(json.dumps({
            "fuente": fuente,
            "campo": campo,
            "tipo": estado,
            "razon": " | ".join(sorted(razones)),
            "n_poses_afectadas": reporte["por_fuente"].get(fuente, {})
            .get("campos", {}).get(campo, {}).get(estado, 0),
            "pids": sorted(pids),
        }, ensure_ascii=False))
    _escribir_jsonl_atomico(out_dir / "failures.jsonl", lineas)

    por_pid = {}
    for pose in poses:
        pid = str(pose.get("pid", "?"))
        if pid not in por_pid:
            por_pid[pid] = {"pid": pid, "n_poses": 0, "sin_provenance": 0,
                            "por_fuente": {},
                            "campos": {c: {"conocido": 0, "unknown": 0,
                                           "faltante": 0}
                                       for c in CAMPOS_OBLIGATORIOS}}
        bloque = por_pid[pid]
        bloque["n_poses"] += 1
        fuente = str(pose.get("source", "?"))
        bloque["por_fuente"][fuente] = bloque["por_fuente"].get(fuente, 0) + 1
        reg = _resolver_registro(pose, registros, modo)
        if reg is None or validar_registro(reg):
            bloque["sin_provenance"] += 1
            continue
        for campo in CAMPOS_OBLIGATORIOS:
            estado = clasificar_campo(reg, campo)
            bloque["campos"][campo][estado] += 1
    lineas = [json.dumps(por_pid[p], ensure_ascii=False)
              for p in sorted(por_pid)]
    _escribir_jsonl_atomico(out_dir / "per_complex.jsonl", lineas)


def _escribir_json_atomico(ruta, datos) -> None:
    tmp = ruta.with_suffix(ruta.suffix + ".tmp")
    tmp.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    tmp.replace(ruta)


def _escribir_jsonl_atomico(ruta, lineas) -> None:
    tmp = ruta.with_suffix(ruta.suffix + ".tmp")
    tmp.write_text(("\n".join(lineas) + ("\n" if lineas else "")),
                   encoding="utf-8")
    tmp.replace(ruta)


# ───────────────────────── CLI ─────────────────────────────────────────────

def _resolver_insumos(args):
    """Carga poses y registros según los flags. Devuelve (poses, registros, modo)."""
    modo = args.provenance
    poses = cargar_poses(args.poses)
    if modo == "sidecar":
        ruta_sidecar = args.sidecar
        if ruta_sidecar is None:
            ruta_sidecar = Path(args.poses[0]).resolve().parent / \
                "poses_provenance.jsonl"
        if not Path(ruta_sidecar).is_file():
            raise FileNotFoundError(f"sidecar no encontrado: {ruta_sidecar}")
        registros = cargar_provenance_sidecar(ruta_sidecar)
    else:
        registros = {}
    return poses, registros, modo


def _exito(reporte: dict, strict_unknown: bool) -> int:
    """Código de salida: 0 si todas las poses trazables (según el modo)."""
    fallo = (reporte["n_sin_provenance"] > 0
             or reporte["n_registros_invalidos"] > 0
             or reporte["n_incoherencias"] > 0
             or any(c["faltante"] > 0 for c in reporte["campos"].values()))
    if strict_unknown:
        fallo = fallo or any(c["unknown"] > 0
                             for c in reporte["campos"].values())
    return 1 if fallo else 0


def main(argv=None) -> int:
    """Punto de entrada del CLI."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    parser = argparse.ArgumentParser(
        prog="pose_provenance.py",
        description="Contrato y verificador de provenance de poses (FND-06).")
    parser.add_argument("poses", nargs="+", metavar="POSES",
                        help="uno o mas JSONL de poses")
    grupo = parser.add_mutually_exclusive_group()
    grupo.add_argument("--check", action="store_true",
                       help="verifica el lote y reporta cobertura")
    grupo.add_argument("--report", action="store_true",
                       help="genera solo la tabla de cobertura (exit 0)")
    parser.add_argument("--provenance", choices=["sidecar", "inline"],
                        default="sidecar",
                        help="modo de provenance (default: sidecar)")
    parser.add_argument("--sidecar", metavar="FILE",
                        help="ruta del sidecar JSONL (default: "
                             "poses_provenance.jsonl junto a las poses)")
    parser.add_argument("--strict-unknown", action="store_true",
                        help="falla si algun campo obligatorio esta "
                             "'unknown' (gate de poses NUEVAS)")
    parser.add_argument("--out-dir", metavar="DIR",
                        help="escribe metrics.json, failures.jsonl y "
                             "per_complex.jsonl en DIR")
    parser.add_argument("--report-file", metavar="FILE",
                        help="guarda la tabla de cobertura en FILE")
    args = parser.parse_args(argv)

    try:
        poses, registros, modo = _resolver_insumos(args)
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    reporte = validar_lote(poses, registros)
    tabla = tabla_cobertura(reporte)

    if args.out_dir:
        escribir_artefactos(reporte, poses, registros, modo, args.out_dir)
        print(f"Artefactos escritos en {args.out_dir}: metrics.json, "
              f"failures.jsonl, per_complex.jsonl")

    print(tabla)
    if args.report_file:
        Path(args.report_file).write_text(tabla + "\n", encoding="utf-8")
        print(f"Reporte guardado en {args.report_file}")

    if args.report:
        return 0
    if args.check:
        return _exito(reporte, args.strict_unknown)

    parser.error("elige --check o --report")
    return 2


if __name__ == "__main__":
    sys.exit(main())
