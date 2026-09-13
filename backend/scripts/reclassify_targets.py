#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
backend/scripts/reclassify_targets.py

Reclasifica los targets de la DB local (tabla `targets`) sobre DOS ejes:

  1. Familia QUÍMICA  → columna `structural_family` (ya existente)
  2. Familia TERAPÉUTICA → columna `therapeutic_family` (NUEVA — el ORM la
     auto-migra al arrancar el backend; si falta, --apply aborta)

Fuente de verdad: backend/scripts/data/pdb_overrides.json (84 entradas curadas
a mano). El resto (~304 filas batch) se clasifica con heurísticas conservadoras
de regex sobre el título/descripción real de RCSB. Toda fila sin asignación
confiable en ALGUNO de los dos ejes va a PENDIENTES — jamás se clasifica en
silencio ni se escribe a medias.

Uso:
    python reclassify_targets.py                  # DRY-RUN (default): análisis completo, no escribe NADA
    python reclassify_targets.py --apply          # backup <db>.bak + UPDATE/DELETE/INSERT en transacción
    python reclassify_targets.py --report         # solo el listado de PENDIENTES (solo lectura)
    python reclassify_targets.py --overrides <path>

Solo stdlib (sqlite3, json, re, pathlib, uuid, argparse, datetime, shutil, sys).
"""

import argparse
import json
import re
import shutil
import sqlite3
import sys
import uuid
from datetime import datetime
from pathlib import Path


# ── Rutas por defecto ──────────────────────────────────────────────────────────

def _base_de_datos_por_defecto() -> Path:
    """Donde vive la base en ESTA maquina, no en la de quien escribio el script.

    Aqui habia una ruta absoluta con un nombre de usuario dentro. Este archivo
    se INSTALA -el empaquetador copia `backend/` entero, `scripts/` incluido-,
    asi que ese nombre viajaba en el producto y la ruta no existia en ninguna
    maquina que no fuera aquella: el script no encontraba nada y no decia por
    que.
    """
    import os

    raiz = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    if raiz:
        candidata = Path(raiz) / "MolDesign" / "data" / "moldesign_local.db"
        if candidata.exists():
            return candidata
    # El arbol de desarrollo: <repo>/backend/moldesign_local.db
    return Path(__file__).resolve().parents[1] / "moldesign_local.db"


DEFAULT_DB = _base_de_datos_por_defecto()
DEFAULT_OVERRIDES = Path(__file__).resolve().parent / "data" / "pdb_overrides.json"


# ── Vocabulario de familias ────────────────────────────────────────────────────
# Valores canónicos. Las familias de los overrides se aplican VERBATIM aunque
# no estén en esta lista (p. ej. "transferase", "otra") — el vocabulario solo
# gobierna la clasificación batch y la validación.

CHEMICAL_FAMILIES = {
    "gpcr", "kinase", "protease", "ion_channel", "nuclear_receptor",
    "phosphodiesterase", "transporter", "cytochrome_p450", "oxidoreductase",
    "hydrolase", "methyltransferase", "topoisomerase", "polymerase",
    "nuclease", "proteasome", "lipid_binding_protein", "growth_factor",
    "protein_interaction", "chaperone", "gtpase", "metalloenzyme",
    "bromodomain", "atp_synthase", "ligase", "lyase", "isomerase",
    "transcription_factor", "ubiquitin_ligase", "prenyl_binding_protein",
    "transferase",
}

THERAPEUTIC_FAMILIES = {
    "cardiovascular", "endocrinologia", "metabolismo", "inmuno-oncologia",
    "neurodegeneracion", "antivirales", "antibacterianos", "fibrosis",
    "epigenetica", "ubiquitina-proteasoma", "senescencia___aging",
    "inflamacion___dolor", "enfermedades_raras", "oncologia", "psiquiatria",
    "coagulacion___hemostasia", "antiparasitarios",
}

# Valores que HOY viven en `structural_family` pero en realidad son terapéuticos
# (herencia del schema anterior de un solo eje). Si el valor normalizado cae
# acá, se toma como familia terapéutica y la química sale por regex del título.
LEGACY_THERAPEUTIC_VALUES = {
    "antivirales", "fibrosis", "ubiquitina-proteasoma", "antibacterianos",
    "enfermedades_raras", "senescencia___aging", "inflamacion___dolor",
    "transportadores", "neurodegeneracion", "endocrinologia", "epigenetica",
    "cardiovascular", "metabolismo", "inmuno-oncologia",
}

# Remapeo de valores heredados a familias terapéuticas canónicas.
THERAPEUTIC_REMAP = {
    "transportadores": "psiquiatria",
}

# Alias de normalización para `structural_family` (lowercase previo incluido).
FAMILY_ALIASES = {
    "gpcr": "gpcr",
    "kinase": "kinase",
    "serine protease": "protease",
    "cytochrome": "cytochrome_p450",
    "metaloenzyme": "metalloenzyme",
    "isomerase": "topoisomerase",
}


# ── Heurísticas regex (títulos reales de RCSB) ─────────────────────────────────
# Cada tupla: (patron_tokens, familia_quimica o None, familia_terapeutica o None).
# El orden ES prioridad: para el eje que falta, gana la PRIMERA regla que matchea
# (las reglas del eje ya cubierto se ignoran). Tokens separados por "|";
# los bordes de palabra se agregan automáticamente (ver _compilar_regex).

# Tokens que son RAÍZ de palabra: admiten letras a continuación. Sin esto,
# 'inflamm' jamás matchearía ("inflamm*ation*"), 'proteasom' no cubriría
# "proteasoma"/"proteasome", y los PDE isoforma (PDE5A1, PDE6D…) quedarían fuera.
# IMPORTANTE: el set se compara contra token.lower() en _compilar_regex,
# por eso TODO debe estar en minúsculas (PDE5 → pde5). Con mayúsculas, el
# token "PDE5" no entraba al set y el ancla (?![a-z]) mataba PDE5A1, TBRPDEB1…
STEM_ALLOW_TRAILING = {
    "inflamm", "proteasom", "retinoic", "retinoid",
    "pde5", "pde6d", "pde9a", "pde10a", "tbrpde", "tcprdec",
}

# Orden ES prioridad (primera regla que matchea por eje). Los tokens más
# específicos van primero: p. ej. "TGF-BETA RECEPTOR" es kinase (TGFBR), mientras
# que "TGF-BETA3" (sin receptor) es growth_factor. FVIIa es protease + coagulación.
REGEX_RULES = [
    # ── Eje químico ──────────────────────────────────────────────────────
    (r"kinase|mTOR|CDK|Erk2|BRAF|JAK|BTK|KIT|PI3K|Aurora|TGFBR|ABL|SRC|EGFR|VEGFR|FGFR", "kinase", None),
    (r"protease|peptidase|cathepsin|thrombin|Mpro|NS3|factor VIIa|factor VII|BACE|APP-CLEAVING|insulin degrading|angiotensin converting|angiotensin-converting|ANCE|ANOACE|HIV", "protease", None),
    (r"cyclooxygenase|COX|prostaglandin", "oxidoreductase", None),
    (r"telomerase|reverse transcriptase|TERT|TETRAHYMENA|template boundary", "polymerase", None),
    (r"deacetylase|HDAC|O-GLCNAC|glcnac|alkaline phosphatase", "hydrolase", None),
    (r"proteasom", "proteasome", None),
    (r"gyrase|topoisomerase|novobiocin|chlorobiocin|clorobiocin|ATPASE DOMAIN|MYCOBACTERIUM|TUBERCULOSIS", "topoisomerase", None),
    (r"TREX1|exonuclease|nuclease", "nuclease", None),
    (r"CYP|cytochrome P450", "cytochrome_p450", "metabolismo"),
    (r"FXR|farnesoid|PPAR|RETINOIC ACID RECEPTOR|NUCLEAR RECEPTOR", "nuclear_receptor", None),
    (r"TSH|TSHR|thyrotropin|thyroid stimulating|follicle stimulating|gonadotropin|FSH|SEROTONIN RECEPTOR|DOPAMINE RECEPTOR|ADENOSINE|ADRENERGIC|MUSCARINIC|OPIOID", "gpcr", None),
    (r"TGF|transforming growth|BMP|GDF|myostatin|growth differentiation", "growth_factor", None),
    (r"follistatin|fibrillin|TAB1|amyloid|fibril|abeta|APLP2|beta-hairpin|serum amyloid|nanobody|VHH|PDZ|PILS|TYPE IVB|immunoglobulin|antibody|FAB", "protein_interaction", None),
    (r"NET|VMAT|norepinephrine|noradrenaline|FapF", "transporter", None),
    (r"retinoic acid binding|retinoid|beta-lactoglobulin", "lipid_binding_protein", None),
    (r"carbonic anhydrase", "metalloenzyme", None),
    (r"CFTR|cystic fibrosis transmembrane|hERG|KCNH2|NavAb|NavMs|CavAb|voltage-gated|sodium channel|potassium channel|calcium channel", "ion_channel", None),
    (r"CIF|CFTR INHIBITORY", "hydrolase", None),
    (r"PDE6D", "prenyl_binding_protein", None),
    (r"PDE|phosphodiesterase", "phosphodiesterase", None),
    (r"ELF3", "transcription_factor", None),
    # ── Eje terapéutico ───────────────────────────────────────────────────
    (r"toxoplasma|schistosoma|trypanosoma|leishmania|plasmodium|malaria|TBRPDE|TCRPDEC", None, "antiparasitarios"),
    (r"factor VIIa|factor VII|FVII|FXa|thrombin|P2Y12", None, "coagulacion___hemostasia"),
    (r"HIV|HCV|SARS|coronavirus", None, "antivirales"),
    (r"5-HT|serotonin|dopamine|NET|VMAT|nemonapride|risperidone|norepinephrine|noradrenaline|PDE10A", None, "psiquiatria"),
    (r"CFTR|cystic fibrosis", None, "enfermedades_raras"),
    (r"amyloid|BACE|APP-CLEAVING|alzheimer|PDE9A|phosphodiesterase-9a", None, "neurodegeneracion"),
    (r"COX|inflamm|dolor|prostaglandin|cathepsin k", None, "inflamacion___dolor"),
    (r"HDAC|deacetylase|methyltransfer", None, "epigenetica"),
    (r"cancer|tumor|CDK|BRAF|PARP|ERK|PI3K|AKT|Aurora|PDE6D|SRC|ABL|cathepsin b|cathepsin f|cathepsin v|cathepsin l", None, "oncologia"),
    (r"hERG|KCNH2|NavAb|NavMs|CavAb|voltage-gated|diltiazem|amlodipine|angiotensin|ANCE|ANOACE|PDE5", None, "cardiovascular"),
    (r"FXR|farnesoid|CYP|cytochrome P450|carbonic anhydrase|insulin", None, "metabolismo"),
    (r"TSH|TSHR|thyrotropin|thyroid stimulating|follicle stimulating|FSH|retinoic|retinoid|RAR", None, "endocrinologia"),
    (r"TGF|BMP|GDF|myostatin|follistatin|fibrillin|TAB1|fibrosis", None, "fibrosis"),
    (r"telomerase|TERT|senescen|TETRAHYMENA|template boundary", None, "senescencia___aging"),
    (r"gyrase|novobiocin|chlorobiocin|mycobacterium|tuberculosis|lysozyme|DHFR|dihydrofolate|ATPASE DOMAIN", None, "antibacterianos"),
    (r"TREX1|checkpoint|PD-L1|CTLA|immune", None, "inmuno-oncologia"),
]


def _compilar_regex(tokens):
    """Convierte 'tok1|tok2|frase con espacios' en un regex seguro.

    Borde de palabra por letras (IGNORECASE): evita matches dentro de palabras
    ('NET' no matchea 'internet') pero permite dígitos a continuación
    ('CDK' matchea 'CDK2', 'CYP' matchea 'CYP3A4'). Los tokens raíz en
    STEM_ALLOW_TRAILING admiten letras a continuación ('inflamm' → 'inflammation').
    Es deliberadamente conservador: 'mTORC1' NO matchea 'mTOR' y queda en
    pendientes.
    """
    partes = []
    for token in tokens.split("|"):
        token = token.strip()
        if not token:
            continue
        escapado = re.escape(token)
        escapado = escapado.replace(r"\ ", r"\s+").replace(" ", r"\s+")
        fin = "" if token.lower() in STEM_ALLOW_TRAILING else r"(?![a-z])"
        partes.append(r"(?<![a-z])" + escapado + fin)
    return re.compile("|".join(partes), re.IGNORECASE)


REGEX_COMPILED = [(_compilar_regex(p), q, t) for p, q, t in REGEX_RULES]


# ── Alta planificada de 4JSX ───────────────────────────────────────────────────
# Nueva entrada curada: complejo mTORDeltaN-mLST8-Torin2 (mTOR = kinase,
# contexto oncológico). No está en el JSON de overrides: se inserta siempre.

NEW_TARGET = {
    "pdb_id": "4JSX",
    "name": "structure of mTORDeltaN-mLST8-Torin2 complex",
    "chain": "A",
    "chemical_family": "kinase",
    "therapeutic_family": "oncologia",
    "grid_center": (0.0, 0.0, 0.0),
    "grid_size": 22.0,  # caja cúbica: x = y = z
    "requires_cns": False,
}


# ── Utilidades ─────────────────────────────────────────────────────────────────

def configurar_stdout():
    """Fuerza UTF-8 en la consola (Windows) para no romper acentos ni nombres."""
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def cargar_overrides(path):
    """Carga el JSON de overrides {pdb_id: {chemical_family, therapeutic_family,
    corrected_name, delete}}."""
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def conectar_ro(db_path):
    """Conexión SOLO LECTURA (uri mode=ro): garantiza que dry-run no escriba nada."""
    uri = "file:" + db_path.as_posix() + "?mode=ro"
    return sqlite3.connect(uri, uri=True)


def leer_targets(conn):
    """Lee las filas de targets: (pdb_id, name, description, structural_family)."""
    cur = conn.cursor()
    cur.execute("SELECT pdb_id, name, description, structural_family FROM targets")
    return cur.fetchall()


def tiene_columna_terapeutica(db_path):
    """¿La columna therapeutic_family ya existe en la DB?
    El ORM la crea en el arranque del backend (auto-migración)."""
    conn = conectar_ro(db_path)
    try:
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(targets)")
        columnas = [fila[1] for fila in cur.fetchall()]
    finally:
        conn.close()
    return "therapeutic_family" in columnas


# ── Clasificación batch ────────────────────────────────────────────────────────

def normalizar_familia(valor):
    """Lowercase + alias de la familia estructural actual."""
    if not valor:
        return None
    v = valor.strip().lower()
    return FAMILY_ALIASES.get(v, v)


def regex_para_eje(texto, eje):
    """Primera regla de la tabla (en orden) que asigna el eje pedido
    ('chemical' | 'therapeutic'). Retorna la familia o None."""
    for patron, quimica, terapeutica in REGEX_COMPILED:
        familia = quimica if eje == "chemical" else terapeutica
        if familia and patron.search(texto):
            return familia
    return None


def clasificar_batch(pdb_id, name, description, familia_actual):
    """Clasifica una fila batch (sin override) sobre ambos ejes.

    Retorna (familia_quimica, familia_terapeutica) o (None, None, motivo)
    si no hay asignación confiable en algún eje → PENDIENTE.

    Lógica (conservadora, por diseño):
      · familia actual química conocida  → se conserva; terapéutica por regex
      · familia actual terapéutica (legacy) → se conserva (con remapeo);
        química por regex
      · cualquier otra familia actual → PENDIENTE (nunca se adivina)
    """
    normalizada = normalizar_familia(familia_actual)
    texto = (name or "") + "\n" + (description or "")

    if normalizada in CHEMICAL_FAMILIES:
        quimica = normalizada
        terapeutica = regex_para_eje(texto, "therapeutic")
        if terapeutica is None:
            return None, None, "falta familia terapéutica en título/descripción"
        return quimica, terapeutica, None

    if normalizada in LEGACY_THERAPEUTIC_VALUES:
        terapeutica = THERAPEUTIC_REMAP.get(normalizada, normalizada)
        quimica = regex_para_eje(texto, "chemical")
        if quimica is None:
            return None, None, "falta familia química en título/descripción"
        return quimica, terapeutica, None

    return None, None, f"familia estructural '{familia_actual}' no es ni química ni terapéutica conocida"


# ── Plan de cambios ────────────────────────────────────────────────────────────

def construir_plan(rows, overrides):
    """Construye el plan completo: actualizar / eliminar / insertar / pendientes.
    Nunca toca la DB: es la foto de lo que se haría en --apply."""
    plan = {
        "total": len(rows),
        "con_override": 0,
        "batch": 0,
        "actualizar": [],      # dicts {pdb_id, name, familia_actual, quimica, terapeutica, corrected_name}
        "eliminar": [],        # [pdb_id]
        "insertar": dict(NEW_TARGET),
        "pendientes": [],      # dicts {pdb_id, name, familia_actual, motivo}
        "nombres_corregidos": 0,
        "overrides_fuera_vocabulario": [],  # familias de overrides que no están en el vocabulario
    }
    vocabulario = CHEMICAL_FAMILIES | THERAPEUTIC_FAMILIES

    for pdb_id, name, description, familia_actual in rows:
        override = overrides.get(pdb_id)

        if override is not None:
            plan["con_override"] += 1
            quimica = (override.get("chemical_family") or "").strip()
            terapeutica = (override.get("therapeutic_family") or "").strip()

            # El override es la fuente de verdad: se aplica verbatim.
            for fam in (quimica, terapeutica):
                if fam and fam not in vocabulario and fam not in plan["overrides_fuera_vocabulario"]:
                    plan["overrides_fuera_vocabulario"].append(fam)

            if not quimica or not terapeutica:
                plan["pendientes"].append({
                    "pdb_id": pdb_id, "name": name,
                    "familia_actual": familia_actual, "motivo": "override incompleto (faltan familias)",
                })
                continue

            if override.get("delete"):
                plan["eliminar"].append(pdb_id)
                continue

            corrected_name = override.get("corrected_name")
            if corrected_name is not None:
                plan["nombres_corregidos"] += 1
            plan["actualizar"].append({
                "pdb_id": pdb_id,
                "name": name,
                "familia_actual": familia_actual,
                "quimica": quimica,
                "terapeutica": terapeutica,
                "corrected_name": corrected_name,
            })
            continue

        # Fila batch (~304): heurísticas conservadoras.
        plan["batch"] += 1
        quimica, terapeutica, motivo = clasificar_batch(pdb_id, name, description, familia_actual)
        if motivo is not None:
            plan["pendientes"].append({
                "pdb_id": pdb_id, "name": name,
                "familia_actual": familia_actual, "motivo": motivo,
            })
        else:
            plan["actualizar"].append({
                "pdb_id": pdb_id,
                "name": name,
                "familia_actual": familia_actual,
                "quimica": quimica,
                "terapeutica": terapeutica,
                "corrected_name": None,
            })

    return plan


# ── Reporte ────────────────────────────────────────────────────────────────────

def _conteos_por_familia(plan):
    """Conteo por familia en ambos ejes sobre las filas a actualizar + el alta 4JSX."""
    quimica = {}
    terapeutica = {}
    for upd in plan["actualizar"]:
        quimica[upd["quimica"]] = quimica.get(upd["quimica"], 0) + 1
        terapeutica[upd["terapeutica"]] = terapeutica.get(upd["terapeutica"], 0) + 1
    # El alta planificada forma parte del estado final.
    t = plan["insertar"]
    quimica[t["chemical_family"]] = quimica.get(t["chemical_family"], 0) + 1
    terapeutica[t["therapeutic_family"]] = terapeutica.get(t["therapeutic_family"], 0) + 1
    return quimica, terapeutica


def _imprimir_tabla_familias(conteos):
    for familia, cantidad in sorted(conteos.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"    {familia:<28} {cantidad:>4}")
    print()


def imprimir_pendientes(plan):
    """Listado de PENDIENTES (modo --report: es TODO el output)."""
    print("=" * 78)
    print(f"PENDIENTES ({len(plan['pendientes'])}) — nunca clasificadas silenciosamente")
    print("=" * 78)
    if not plan["pendientes"]:
        print("  (sin pendientes: todo clasificado con confianza)")
        return
    for p in sorted(plan["pendientes"], key=lambda x: x["pdb_id"]):
        print(f"  {p['pdb_id']:<6} | familia actual: {p['familia_actual'] or 'NULL':<24} | "
              f"falta: {p['motivo']}")
        print(f"          | nombre: {p['name']}")


def imprimir_reporte(plan, modo, db_path, overrides_path):
    """Reporte completo. modo: 'dry-run' (no escribe) | 'apply' (va a escribir)."""
    verbo = "se actualizarían" if modo == "dry-run" else "se actualizan"
    quimica, terapeutica = _conteos_por_familia(plan)

    print("=" * 78)
    print(f"RECLASIFICACIÓN DUAL DE TARGETS — modo {modo.upper()}")
    print("=" * 78)
    print(f"  DB:        {db_path}")
    print(f"  Overrides: {overrides_path}")
    if modo == "dry-run":
        print("  (solo lectura: conexión mode=ro, NO se escribe absolutamente nada)")
    print()

    print("── Resumen ──────────────────────────────────────────────")
    print(f"  Total de targets:          {plan['total']:>4}")
    print(f"    · con override curado:   {plan['con_override']:>4}")
    print(f"    · batch (heurísticas):   {plan['batch']:>4}")
    print(f"  Filas que {verbo}:      {len(plan['actualizar']):>4}")
    print(f"  Filas a eliminar:          {len(plan['eliminar']):>4}"
          + (f"  ({', '.join(plan['eliminar'])})" if plan["eliminar"] else ""))
    print(f"  Nombres corregidos:        {plan['nombres_corregidos']:>4}"
          "  (corrected_name verbatim desde overrides)")
    print(f"  Alta planificada:          {plan['insertar']['pdb_id']:>4}"
          f"  ({plan['insertar']['name']})")
    print(f"  PENDIENTES:                {len(plan['pendientes']):>4}"
          "  ← ver listado al final; nunca se escriben")
    if plan["overrides_fuera_vocabulario"]:
        print(f"  Nota: overrides con familias fuera del vocabulario (se aplican "
              f"verbatim): {', '.join(sorted(plan['overrides_fuera_vocabulario']))}")
    print()

    print("── Conteo por familia QUÍMICA (estado final, incluye 4JSX) ──")
    _imprimir_tabla_familias(quimica)
    print("── Conteo por familia TERAPÉUTICA (estado final, incluye 4JSX) ──")
    _imprimir_tabla_familias(terapeutica)

    if plan["pendientes"]:
        imprimir_pendientes(plan)
    else:
        print("  (sin pendientes: todo clasificado con confianza)")
    print()


# ── Aplicación (--apply) ───────────────────────────────────────────────────────

def aplicar(plan, db_path):
    """Backup + UPDATE/DELETE/INSERT en una sola transacción."""
    backup = db_path.with_suffix(db_path.suffix + ".bak")
    shutil.copy2(db_path, backup)
    print(f"[apply] Backup creado: {backup}")

    conn = sqlite3.connect(str(db_path))
    conn.isolation_level = None  # autocomit off: transacción explícita
    cur = conn.cursor()
    try:
        cur.execute("BEGIN")

        # 1) UPDATE: familias en ambos ejes + nombre corregido si aplica.
        for upd in plan["actualizar"]:
            if upd["corrected_name"] is not None:
                cur.execute(
                    "UPDATE targets SET structural_family = ?, therapeutic_family = ?, name = ? "
                    "WHERE pdb_id = ?",
                    (upd["quimica"], upd["terapeutica"], upd["corrected_name"], upd["pdb_id"]),
                )
            else:
                cur.execute(
                    "UPDATE targets SET structural_family = ?, therapeutic_family = ? "
                    "WHERE pdb_id = ?",
                    (upd["quimica"], upd["terapeutica"], upd["pdb_id"]),
                )

        # 2) DELETE: filas marcadas delete:true en overrides (hoy solo 4OTW).
        for pdb_id in plan["eliminar"]:
            cur.execute("DELETE FROM targets WHERE pdb_id = ?", (pdb_id,))

        # 3) INSERT: alta de 4JSX (idempotente: si ya existe, se omite).
        t = plan["insertar"]
        cur.execute("SELECT COUNT(*) FROM targets WHERE pdb_id = ?", (t["pdb_id"],))
        ya_existe = cur.fetchone()[0] > 0
        if ya_existe:
            print(f"[apply] {t['pdb_id']} ya existe en la DB — se omite el INSERT.")
        else:
            cur.execute(
                "INSERT INTO targets (id, pdb_id, name, chain, description, "
                "grid_center_x, grid_center_y, grid_center_z, "
                "grid_size_x, grid_size_y, grid_size_z, requires_cns, "
                "structural_family, therapeutic_family, created_at, "
                "is_hot, is_prepared, is_private, is_community, is_anti_target) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, 0)",
                (
                    str(uuid.uuid4()),
                    t["pdb_id"],
                    t["name"],
                    t["chain"],
                    None,  # description
                    t["grid_center"][0], t["grid_center"][1], t["grid_center"][2],
                    t["grid_size"], t["grid_size"], t["grid_size"],
                    1 if t["requires_cns"] else 0,
                    t["chemical_family"],
                    t["therapeutic_family"],
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                ),
            )
            print(f"[apply] Insertado: {t['pdb_id']} ({t['name']})")

        cur.execute("COMMIT")
    except Exception:
        cur.execute("ROLLBACK")
        conn.close()
        raise

    conn.close()
    print(f"[apply] Transacción COMMITEADA: {len(plan['actualizar'])} filas actualizadas, "
          f"{len(plan['eliminar'])} eliminadas, 1 alta planificada. "
          f"Pendientes sin tocar: {len(plan['pendientes'])}.")


# ── CLI ────────────────────────────────────────────────────────────────────────

def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Reclasifica targets sobre familia química (structural_family) "
                    "y familia terapéutica (therapeutic_family).",
    )
    grupo = parser.add_mutually_exclusive_group()
    grupo.add_argument("--dry-run", action="store_true",
                       help="solo análisis, DB abierta en modo lectura (DEFAULT)")
    grupo.add_argument("--apply", action="store_true",
                       help="escribe: backup <db>.bak + UPDATE/DELETE/INSERT en transacción")
    grupo.add_argument("--report", action="store_true",
                       help="imprime únicamente el listado de PENDIENTES (solo lectura)")
    parser.add_argument("--overrides", type=Path, default=DEFAULT_OVERRIDES,
                        help=f"JSON de overrides (default: {DEFAULT_OVERRIDES})")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB,
                        help=f"ruta a la DB SQLite (default: {DEFAULT_DB})")
    args = parser.parse_args(argv)
    args.modo = "apply" if args.apply else ("report" if args.report else "dry-run")
    return args


def main(argv=None):
    configurar_stdout()
    args = parse_args(argv)

    if not args.db.exists():
        print(f"ERROR: no existe la DB: {args.db}")
        return 2
    if not args.overrides.exists():
        print(f"ERROR: no existe el archivo de overrides: {args.overrides}")
        return 2

    overrides = cargar_overrides(args.overrides)

    # --apply exige la columna therapeutic_family: el ORM la crea al arrancar
    # el backend (auto-migración). Si falta, se aborta ANTES de tocar la DB.
    if args.modo == "apply" and not tiene_columna_terapeutica(args.db):
        print("ERROR: la columna 'therapeutic_family' no existe todavía en la DB.")
        print("       Arrancá el backend una vez para que el ORM la cree "
              "(auto-migración) y volvé a correr con --apply.")
        return 2

    conn = conectar_ro(args.db)
    try:
        rows = leer_targets(conn)
    finally:
        conn.close()

    plan = construir_plan(rows, overrides)

    if args.modo == "report":
        imprimir_pendientes(plan)
        return 0

    imprimir_reporte(plan, "apply" if args.modo == "apply" else "dry-run",
                     args.db, args.overrides)

    if args.modo == "apply":
        aplicar(plan, args.db)

    return 0


if __name__ == "__main__":
    sys.exit(main())
