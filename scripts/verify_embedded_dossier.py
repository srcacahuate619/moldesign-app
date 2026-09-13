#!/usr/bin/env python3
"""El dossier del runtime embebido, pedido por su API pública.

Paso 4 del plan de la Fase 0 de
`docs/74_ARQUITECTURA_DISPATCHER_DE_PROTOCOLOS.md`: cerrar la cadena

    código → manifiesto → backend embebido → corrida → snapshot → dossier

═══════════════════════════════════════════════════════════════════════════
POR QUÉ NO BASTA CON IMPORTAR EL CONSTRUCTOR
═══════════════════════════════════════════════════════════════════════════

`scripts/generate_goldens.py` sella lo que `campos_de_m4` y `campos_de_m5_zn`
producen a partir de un `eval_result`. Es el contrato del BLOQUE, y se comprueba
llamando a la función.

Eso deja fuera justo lo que rompe en producción: de dónde sale ese
`eval_result`. Un bloque puede leer un campo que el objeto real no tiene y
devolver la rama de ausencia —con su motivo, correctamente redactado— sin que
ninguna prueba de unidad se entere, porque las pruebas le pasan un diccionario
que sí lo tiene.

Por eso aquí el dossier se pide por HTTP, al proceso embebido, sobre filas que
ese proceso lee de su propia base:

    POST /evaluation/dossier/{molecule_id}/package  ->  case/dossier_model.json

═══════════════════════════════════════════════════════════════════════════
LOS DOS NIVELES DE COMPARACIÓN
═══════════════════════════════════════════════════════════════════════════

    nivel 1   los bloques de protocolo, contra las corridas doradas
              (`dossier_m4`, `dossier_m5_zn`, `dossier_peptido`)

    nivel 2   el dossier canónico ENTERO, desarrollo contra embebido,
              excluyendo sólo `generated_at`

El nivel 2 usa UUID deterministas para molécula y objetivo, así que la única
diferencia legítima entre los dos JSON es el reloj. Cualquier otra es un cambio
de significado entre lo que se prueba y lo que se instala.

El PDF se renderiza desde ese mismo objeto (`render_dossier_pdf(dossier)`), así
que la igualdad del JSON canónico es la igualdad del contenido científico del
PDF; sus metadatos —fecha de creación— sí pueden variar.

═══════════════════════════════════════════════════════════════════════════
AISLAMIENTO
═══════════════════════════════════════════════════════════════════════════

Un gate que pueda importar el repositorio no comprueba el bundle: comprueba la
máquina de quien lo ejecuta. Aquí:

    · el entorno se construye DESDE CERO, no con `os.environ.copy()`;
    · las variables son las de `spawn_backend` (frontend/src-tauri/src/backend.rs)
      y ninguna más;
    · el perfil de usuario se redirige a un directorio temporal, que es lo que
      mueve la base SQLite y `~/.moldesign` fuera del equipo real — Tauri no
      pone `LOCAL_DATA_DIR`, así que redirigir el HOME es la forma de aislar
      sin inventarse una variable que el producto no tiene;
    · el puerto se reserva en el momento, así que no se puede estar hablando con
      un backend de desarrollo ya abierto;
    · y hay un CANARIO: `backend/tests/` existe en el repositorio y
      `bundle_helper` lo excluye del bundle. Si el proceso embebido consigue
      importar `tests`, es que el árbol del repositorio está en su ruta de
      búsqueda y todo lo demás que diga este script no vale nada.

Uso:

    python scripts/verify_embedded_dossier.py [raíz]
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
import zipfile
from contextlib import contextmanager
from pathlib import Path

# El informe lleva fórmulas y texto científico con acentos, «ρ» y «→». La
# consola de Windows abre en cp1252 y `print` moriría con UnicodeEncodeError
# justo al redactar el fallo — es decir, el gate se caería en vez de contarlo.
for _flujo in (sys.stdout, sys.stderr):
    try:
        _flujo.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):  # pragma: no cover - flujo redirigido
        pass

RAIZ_POR_DEFECTO = Path(__file__).resolve().parents[1]

#: Espacio de nombres de los UUID deterministas. Que molécula y objetivo tengan
#: el mismo id en desarrollo y en el runtime embebido es lo que permite comparar
#: los dos dossieres enteros en vez de campo a campo.
NS_VERIFICACION = uuid.UUID("2f0a1b3c-4d5e-6f70-8192-a3b4c5d6e7f8")


def uid(*partes: str) -> str:
    return str(uuid.uuid5(NS_VERIFICACION, "moldesign/verify/" + "/".join(partes)))


# ══════════════════════════════════════════════════════════════════════════
# Los casos que se siembran
# ══════════════════════════════════════════════════════════════════════════
#
# Las entradas son las MISMAS que usa `scripts/generate_goldens.py` para los
# tres goldens de dossier. Aquí viajan por columnas de SQLite en vez de por un
# diccionario en memoria, que es exactamente la diferencia que se quiere medir.

CASOS = [
    # ── M4 ───────────────────────────────────────────────────────────
    {
        "clave": "m4_ml_dentro_del_dominio",
        "golden": "dossier_m4",
        "estado": "ml_dentro_del_dominio",
        "pdb": "3PP0",
        "smiles": "CC(=O)Oc1ccccc1C(=O)O",
        "resultado": {
            "affinity_kcal": -6.5,
            "docking_poses": [{"affinity": -6.5, "rmsd_lb": 0.0, "rmsd_ub": 0.0}],
            "heavy_atom_count": 13,
            "target_family": "kinase",
            "model_used": "universal",
            "xgb_score": 0.71,
            "ml_pki": 4.9,
            "ml_pki_aplicada": True,
        },
    },
    {
        "clave": "m4_ml_fuera_del_dominio",
        "golden": "dossier_m4",
        "estado": "ml_fuera_del_dominio",
        "pdb": "3PP0",
        "smiles": "CC(=O)Oc1ccccc1C(=O)O",
        "resultado": {
            "affinity_kcal": -6.5,
            "docking_poses": [{"affinity": -6.5, "rmsd_lb": 0.0, "rmsd_ub": 0.0}],
            "heavy_atom_count": 13,
            "target_family": "kinase",
            "model_used": "universal",
            "xgb_score": 0.71,
            "ml_pki": 4.9,
            "ml_pki_aplicada": False,
        },
    },
    {
        "clave": "m4_sin_regresion_de_ml",
        "golden": "dossier_m4",
        "estado": "sin_regresion_de_ml",
        "pdb": "3PP0",
        "smiles": "CC(=O)Oc1ccccc1C(=O)O",
        "resultado": {
            "affinity_kcal": -6.5,
            "docking_poses": [{"affinity": -6.5, "rmsd_lb": 0.0, "rmsd_ub": 0.0}],
            "heavy_atom_count": 13,
            "target_family": "kinase",
            "model_used": "universal",
            "xgb_score": 0.71,
            "ml_pki": None,
            "ml_pki_aplicada": None,
        },
    },
    # ── M5-Zn ────────────────────────────────────────────────────────
    #
    # Los CINCO estados que el dossier tiene que saber contar. Las entradas son
    # las mismas que sella `generate_goldens.py`, y viajan aquí por columnas de
    # SQLite en vez de por un diccionario en memoria.
    #
    # Ninguno es VALIDATED, y eso es el contrato de M5-V1: CA2 se abstiene por
    # ausencia de GNN-D, MMP9 y ACE tienen su benchmark en revisión.
    # Ver docs/77_CORRIGENDUM_SITIO_DEL_BENCHMARK_M5_ZN.md.
    {
        "clave": "m5_benchmark_en_revision",
        "golden": "dossier_m5_zn",
        "estado": "perfil_con_benchmark_en_revision",
        "pdb": "1GKC",
        "smiles": "NS(=O)(=O)c1ccc(cc1)C(=O)N",
        "resultado": {
            "affinity_kcal": -7.2,
            "docking_poses": [{"affinity": -7.2, "rmsd_lb": 0.0, "rmsd_ub": 0.0}],
            "heavy_atom_count": 16,
            "target_family": "metalloenzyme",
            "xgb_score": 0.84,
            "ums_warhead": 0.9166666666666666,
            "m5_score": 0.859167,
            "m5_protocol_id": "M5_ZN_MMP9_1GKC_V1",
            "m5_scientific_status": "REVIEW_INVALID_BENCHMARK_SITE",
        },
    },
    {
        "clave": "m5_top1_que_no_coordina",
        "golden": "dossier_m5_zn",
        "estado": "perfil_con_top1_que_no_coordina",
        "pdb": "1O86",
        "smiles": "NS(=O)(=O)c1ccc(cc1)C(=O)NCCC",
        "resultado": {
            "affinity_kcal": -7.2,
            "docking_poses": [{"affinity": -7.2, "rmsd_lb": 0.0, "rmsd_ub": 0.0}],
            "heavy_atom_count": 19,
            "target_family": "metalloenzyme",
            "xgb_score": 0.84,
            "ums_warhead": 0.9166666666666666,
            "m5_score": 0.8532,
            "m5_protocol_id": "M5_ZN_ACE_1O86_V1",
            "m5_scientific_status": "REVIEW_BENCHMARK_TOP1_NOT_METAL_COORDINATING",
        },
    },
    {
        "clave": "m5_perfil_exacto_falta_componente",
        "golden": "dossier_m5_zn",
        "estado": "perfil_exacto_falta_componente",
        "pdb": "3DC3",
        "smiles": "NS(=O)(=O)c1ccc(cc1)C(=O)NC",
        "resultado": {
            "affinity_kcal": -7.2,
            "docking_poses": [{"affinity": -7.2, "rmsd_lb": 0.0, "rmsd_ub": 0.0}],
            "heavy_atom_count": 17,
            "target_family": "metalloenzyme",
            "xgb_score": 0.84,
            "ums_warhead": 0.9166666666666666,
            "m5_score": None,
            "m5_protocol_id": "M5_ZN_CA2_3DC3_V1",
            "m5_scientific_status": "NOT_EVALUATED_MISSING_COMPONENT",
        },
    },
    {
        "clave": "m5_zinc_fuera_de_las_tres_dianas",
        "golden": "dossier_m5_zn",
        "estado": "zinc_fuera_de_las_tres_dianas",
        "pdb": "1BN1",
        "smiles": "NS(=O)(=O)c1ccc(cc1)C(=O)NCC",
        "resultado": {
            "affinity_kcal": -7.2,
            "docking_poses": [{"affinity": -7.2, "rmsd_lb": 0.0, "rmsd_ub": 0.0}],
            "heavy_atom_count": 18,
            "target_family": "metalloenzyme",
            "xgb_score": 0.84,
            "ums_warhead": 0.9166666666666666,
            "m5_scientific_status": "REVIEW_OUT_OF_VALIDATED_TARGET",
        },
    },
    {
        # Una corrida anterior a SCHEMA 18: sin estado M5 y con el UMS
        # HISTORICO como unica senal de warheads.
        "clave": "m5_corrida_anterior_a_schema_18",
        "golden": "dossier_m5_zn",
        "estado": "corrida_anterior_a_schema_18",
        "pdb": "1GKC",
        "smiles": "NS(=O)(=O)c1ccc(cc1)C(=O)NCCCC",
        "resultado": {
            "affinity_kcal": -7.2,
            "docking_poses": [{"affinity": -7.2, "rmsd_lb": 0.0, "rmsd_ub": 0.0}],
            "heavy_atom_count": 20,
            "target_family": "metalloenzyme",
            "xgb_score": 0.84,
            "ums_score": 0.9167,
        },
    },
    # ── Péptidos ─────────────────────────────────────────────────────
    {
        "clave": "peptido_estructura_sin_acoplamiento",
        "golden": "dossier_peptido",
        "estado": "estructura_generada_sin_acoplamiento",
        "pdb": "7E2Y",
        "smiles": "CC(C)C[C@H](NC(=O)[C@@H](N)Cc1ccccc1)C(=O)O",
        "resultado": {
            "affinity_kcal": None,
            "docking_poses": [],
            "docking_protocol": {
                "requested_engine": "esmfold",
                "executed_engine": "esmfold",
            },
        },
    },
    {
        "clave": "peptido_motor_sustituido",
        "golden": "dossier_peptido",
        "estado": "motor_sustituido_por_vina",
        "pdb": "7E2Y",
        "smiles": "CC(C)C[C@H](NC(=O)[C@@H](N)Cc1ccccc1)C(=O)N",
        "resultado": {
            "affinity_kcal": -5.4,
            "docking_poses": [{"affinity": -5.4, "rmsd_lb": 0.0, "rmsd_ub": 0.0}],
            "docking_protocol": {
                "requested_engine": "esmfold",
                "executed_engine": "vina",
            },
        },
    },
]

#: Cajas de rejilla de los objetivos que se siembran. Valores arbitrarios y
#: FIJOS: no se acopla nada, sólo tienen que existir y ser iguales en los dos
#: lados de la comparación.
REJILLA = {"cx": 0.0, "cy": 0.0, "cz": 0.0, "sx": 20.0, "sy": 20.0, "sz": 20.0}

#: Fecha de la corrida, congelada. `evaluated_at` y `created_at` tienen
#: `server_default=func.now()`, así que sembrar los dos runtimes con segundos de
#: diferencia metía dos relojes distintos en la portada del dossier —«Fecha de
#: la corrida»— y la comparación los reportaba como divergencia científica.
#:
#: Se arregla congelando la siembra, no excluyendo el campo: excluirlo dejaría
#: de comprobar que la fecha de la corrida viaja, que es un dato del documento.
MOMENTO_DE_LA_CORRIDA = "2026-09-04T12:00:00+00:00"


# ══════════════════════════════════════════════════════════════════════════
# Entorno
# ══════════════════════════════════════════════════════════════════════════

#: Lo mínimo que un proceso de Windows necesita para arrancar. Todo lo demás
#: —incluido cualquier `MOLDESIGN_*` o `PYTHON*` del entorno de quien ejecuta
#: este script— se queda fuera a propósito.
_VARIABLES_DEL_SISTEMA = (
    "SystemRoot", "SystemDrive", "windir", "COMSPEC", "PATHEXT",
    "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE", "PROCESSOR_IDENTIFIER",
    "OS", "COMPUTERNAME", "PROGRAMDATA", "PROGRAMFILES", "PROGRAMFILES(X86)",
    "COMMONPROGRAMFILES", "PUBLIC",
)


def entorno_de_tauri(backend: Path, vina: Path, hogar: Path) -> dict[str, str]:
    """El entorno de `spawn_backend`, sobre una base construida desde cero.

    Las siete variables de abajo son literalmente las que pone Tauri
    (`frontend/src-tauri/src/backend.rs`). No se añade ninguna más:
    `LOCAL_DATA_DIR`, `SECRET_KEY` y `MOLDESIGN_BUNDLE_BACKEND` —que sí usa
    `verify_desktop_bundle.py`— no existen en producción, y ponerlas aquí
    comprobaría un arranque que ningún usuario tiene.

    El aislamiento se consigue moviendo el PERFIL DE USUARIO, no inventando
    variables: `local_data_dir` y la `secret_key` persistida cuelgan de
    `Path.home()`, así que con `USERPROFILE` en un temporal la corrida no toca
    nada del equipo y sigue ejecutando el mismo código.
    """
    sistema = Path(os.environ.get("SystemRoot", r"C:\Windows"))
    entorno = {
        clave: os.environ[clave]
        for clave in _VARIABLES_DEL_SISTEMA
        if clave in os.environ
    }
    entorno.update({
        # PATH mínimo: el intérprete embebido y las DLL del sistema. Sin esto
        # se heredaría el PATH del desarrollador, que es justo lo que puede
        # tapar una dependencia que falta en el bundle.
        "PATH": os.pathsep.join([str(sistema / "System32"), str(sistema)]),
        "TEMP": str(hogar / "tmp"),
        "TMP": str(hogar / "tmp"),
        "USERPROFILE": str(hogar),
        "HOMEDRIVE": hogar.drive,
        "HOMEPATH": str(hogar)[len(hogar.drive):],
        # ── Las de Tauri, y sólo estas ───────────────────────────────
        "APP_MODE": "DESKTOP",
        "ENVIRONMENT": "production",
        "PYTHONPATH": str(backend),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONUTF8": "1",
        "VINA_EXECUTABLE_PATH": str(vina),
        "TABPFN_NO_BROWSER": "true",
    })
    (hogar / "tmp").mkdir(parents=True, exist_ok=True)
    return entorno


def puerto_libre() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


# ══════════════════════════════════════════════════════════════════════════
# Sondas que corren DENTRO del runtime que se verifica
# ══════════════════════════════════════════════════════════════════════════

SONDA_PROCEDENCIA = r'''
"""Dice de dónde sale cada cosa. No comprueba: informa, y el padre juzga."""
import hashlib, importlib, json, sys
from pathlib import Path

backend = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(backend))   # lo mismo que `uvicorn --app-dir`

informe = {"sys_executable": sys.executable, "sys_path": list(sys.path), "modulos": {}}

# El canario. `backend/tests/` existe en el repositorio y `bundle_helper` lo
# excluye del bundle: si esto importa, el repositorio está en la ruta.
try:
    import tests as _canario
    informe["canario_tests"] = getattr(_canario, "__file__", "<sin archivo>")
except Exception as exc:
    informe["canario_tests"] = None
    informe["canario_error"] = f"{type(exc).__name__}: {exc}"

for nombre in (
    "api.main",
    "core.models",
    "scoring.eficiencia",
    "scoring.ums",
    "services.dossier.model",
    "services.dossier.bloques_protocolo",
    "services.pipeline.protocols.m5.zinc",
):
    try:
        modulo = importlib.import_module(nombre)
        informe["modulos"][nombre] = getattr(modulo, "__file__", None)
    except Exception as exc:
        informe["modulos"][nombre] = f"ERROR {type(exc).__name__}: {exc}"

# ── El manifiesto de M5-Zn, y si sigue describiendo al módulo empaquetado ──
#
# Nada lo lee en tiempo de ejecución: es una DECLARACIÓN. Por eso no basta con
# comprobar que viaja; hay que comprobar que lo que declara es lo que el
# `zinc.py` empaquetado hace hoy. Se comparan los campos que definen el
# protocolo, no el archivo entero: `sha256_actual` y `presente` de los
# checkpoints describen el árbol del repositorio, que el bundle no lleva.
ruta_manifiesto = backend / "services" / "pipeline" / "protocols" / "m5" / "m5_zn_manifest.json"
informe["manifiesto_m5"] = {"ruta": str(ruta_manifiesto), "presente": ruta_manifiesto.is_file()}
if ruta_manifiesto.is_file():
    crudo = ruta_manifiesto.read_bytes()
    informe["manifiesto_m5"]["sha256"] = hashlib.sha256(crudo).hexdigest()
    manifiesto = json.loads(crudo.decode("utf-8"))
    from services.pipeline.protocols.m5.zinc import PERFILES
    from scoring.ums import _WARHEAD_SMARTS

    canonico = json.dumps(
        {k: sorted(_WARHEAD_SMARTS[k]) for k in sorted(_WARHEAD_SMARTS)},
        sort_keys=True, ensure_ascii=False,
    )
    informe["manifiesto_m5"]["smarts_sha256_del_modulo"] = hashlib.sha256(
        canonico.encode("utf-8")
    ).hexdigest()
    informe["manifiesto_m5"]["smarts_sha256_declarado"] = (
        manifiesto.get("ums", {}).get("warhead_smarts_sha256")
    )

    divergencias = []
    declarados = manifiesto.get("profiles", {})
    if sorted(declarados) != sorted(PERFILES):
        divergencias.append(
            f"perfiles: manifiesto {sorted(declarados)} != modulo {sorted(PERFILES)}"
        )
    for pdb, perfil in sorted(PERFILES.items()):
        d = declarados.get(pdb, {})
        esperado = {
            "protocol_id": perfil.protocol_id,
            "formula": perfil.formula,
            "weights": {
                "vina_norm": perfil.peso_vina,
                "xgboost": perfil.peso_xgb,
                "gnn_d": perfil.peso_gnn_d,
                "ums_warhead": perfil.peso_ums,
            },
            "required_components": list(perfil.componentes_requeridos),
            "vina_reference_max": perfil.vina_reference_max,
            "checkpoint_path": perfil.checkpoint,
            "checkpoint_sha256": perfil.checkpoint_sha256,
        }
        actual = {
            "protocol_id": d.get("protocol_id"),
            "formula": d.get("formula"),
            "weights": d.get("weights"),
            "required_components": d.get("required_components"),
            "vina_reference_max": (d.get("normalizer") or {}).get("vina_reference_max"),
            "checkpoint_path": (d.get("checkpoint") or {}).get("path"),
            "checkpoint_sha256": (d.get("checkpoint") or {}).get("sha256_declarado"),
        }
        if esperado != actual:
            divergencias.append(f"{pdb}: {esperado} != {actual}")
    informe["manifiesto_m5"]["divergencias"] = divergencias

# ── La abstención peptídica, bajo el entorno EXACTO de Tauri ──────────────
#
# `verify_desktop_bundle.py` ya ejerce esta primitiva, pero con un entorno que
# añade LOCAL_DATA_DIR, SECRET_KEY y MOLDESIGN_BUNDLE_BACKEND, tres variables
# que en producción no existen. Aquí se ejerce con las de Tauri y con un PDB
# que SÍ trae B-factors, para que el pLDDT no sea el 0.0 de «no había archivo»
# —que es un valor que pasaría la prueba sin comprobar nada—.
import tempfile

sys.path.insert(0, str(backend / "sidecars" / "esmfold"))
try:
    from predictor import ESMFoldFastPredictor, ORIGEN_SOLO_PLEGADO

    # B-factors en 0-1, que es la escala que escribe `output_to_pdb`.
    lineas = [
        f"ATOM  {i:>5}  CA  ALA A{i:>4}    {float(i):>8.3f}{0.0:>8.3f}{0.0:>8.3f}"
        f"{1.0:>6.2f}{0.72:>6.2f}           C"
        for i in (1, 2, 3)
    ]
    salto = chr(10)
    plegado = salto.join(lineas) + salto + "END" + salto
    with tempfile.NamedTemporaryFile("w", suffix=".pdb", delete=False,
                                     encoding="utf-8") as fichero:
        fichero.write(plegado)
        ruta_plegado = fichero.name

    pose = ESMFoldFastPredictor._fallback_poses(ruta_plegado)[0]
    informe["peptido"] = {
        "origen": pose.origen,
        "origen_esperado": ORIGEN_SOLO_PLEGADO,
        "vina_affinity_kcal_mol": pose.vina_affinity_kcal_mol,
        "confianza_del_plegado": pose.confidence,
        "plddt_0_100": ESMFoldFastPredictor._compute_plddt_from_pdb(plegado),
        "best_affinity_obligatorio": None,
    }
    from core.models import DockingResult

    informe["peptido"]["best_affinity_obligatorio"] = (
        DockingResult.model_fields["best_affinity"].is_required()
    )
    Path(ruta_plegado).unlink(missing_ok=True)
except Exception as exc:
    informe["peptido"] = {"error": f"{type(exc).__name__}: {exc}"}

# ── M5-Zn ejecutado DENTRO del runtime empaquetado ───────────────────────
#
# No basta con que el dossier sepa pintar los estados: hay que comprobar que el
# backend EMPAQUETADO los produce. Esto llama al protocolo real, con las
# estructuras que viajan en el bundle, y anota qué estado sale para cada diana.
#
# Los tres son distintos a proposito:
#
#   3DC3  NOT_EVALUATED_MISSING_COMPONENT               falta GNN-D
#   1GKC  REVIEW_INVALID_BENCHMARK_SITE                 sitio incorrecto
#   1O86  REVIEW_BENCHMARK_TOP1_NOT_METAL_COORDINATING  top-1 sin coordinar
#
# Y ninguno es VALIDATED. Si alguno lo fuera en el bundle y no en desarrollo,
# el producto instalado estaria afirmando algo que el repositorio no sostiene.
try:
    from services.pipeline.protocols.m5.ejecucion import ejecutar as _m5

    informe["m5_zn"] = {}
    for _pdb in ("3DC3", "1GKC", "1O86", "1BN1"):
        _s = _m5(
            smiles="NS(=O)(=O)c1ccc(cc1)C(=O)N",
            target_pdb_id=_pdb,
            target_family="metalloenzyme",
            vina_kcal_mol=-7.2,
            xgb_prob=0.84,
        )
        informe["m5_zn"][_pdb] = None if _s is None else {
            "estado": _s.estado,
            "protocol_id": _s.protocol_id,
            "score": _s.score,
            "ums_warhead": _s.ums_warhead,
            "componentes_ausentes": list(_s.componentes_ausentes),
        }

    from services.pipeline.protocols.interpretabilidad import es_interpretable

    informe["m5_zn"]["_habilitan_conclusion"] = {
        pdb: es_interpretable((datos or {}).get("estado"))
        for pdb, datos in informe["m5_zn"].items()
        if not pdb.startswith("_")
    }
except Exception as exc:
    informe["m5_zn"] = {"error": f"{type(exc).__name__}: {exc}"}

print(json.dumps(informe, ensure_ascii=False))
'''


SONDA_SIEMBRA = r'''
"""Crea las corridas en la base del runtime que se verifica.

Escribe filas, no dossieres: el dossier lo pide después el padre por HTTP, que
es lo que hace que la comprobación pase por el producto y no por una función.
"""
import asyncio, json, sys, uuid
from datetime import datetime
from pathlib import Path

backend = Path(sys.argv[1]).resolve()
casos = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
sys.path.insert(0, str(backend))


async def sembrar():
    from core.database import close_engine, create_all_tables, get_db_session
    from core.models import EvaluationResultORM, MoleculeORM, MoleculeStatus, TargetORM
    from db.repository import Repository

    await create_all_tables()
    async with get_db_session() as db:
        demo = await Repository(db).get_or_create_test_user()
        vistos = set()
        for caso in casos:
            tid = uuid.UUID(caso["target_uuid"])
            if tid not in vistos:
                vistos.add(tid)
                if await db.get(TargetORM, tid) is None:
                    db.add(TargetORM(
                        id=tid, pdb_id=caso["pdb"], name=f"Objetivo {caso['pdb']}",
                        chain="A",
                        grid_center_x=caso["rejilla"]["cx"],
                        grid_center_y=caso["rejilla"]["cy"],
                        grid_center_z=caso["rejilla"]["cz"],
                        grid_size_x=caso["rejilla"]["sx"],
                        grid_size_y=caso["rejilla"]["sy"],
                        grid_size_z=caso["rejilla"]["sz"],
                    ))
                    await db.flush()

            mid = uuid.UUID(caso["molecule_uuid"])
            if await db.get(MoleculeORM, mid) is None:
                db.add(MoleculeORM(
                    id=mid, smiles=caso["smiles"], name=caso["clave"],
                    status=MoleculeStatus.EVALUATED, user_id=demo.id, target_id=tid,
                    smiles_hash=caso["smiles_hash"], is_saved=True,
                    created_at=datetime.fromisoformat(caso["momento"]),
                ))
                await db.flush()

            if await db.get(EvaluationResultORM, uuid.UUID(caso["result_uuid"])) is None:
                db.add(EvaluationResultORM(
                    id=uuid.UUID(caso["result_uuid"]),
                    molecule_id=mid,
                    task_id=caso["task_id"],
                    evaluated_at=datetime.fromisoformat(caso["momento"]),
                    **caso["resultado"],
                ))
                await db.flush()
    await close_engine()


asyncio.run(sembrar())
print("sembrado")
'''


def _ejecutar(python: Path, argv: list[str], *, cwd: Path, env: dict[str, str],
              timeout: int, que: str) -> str:
    proceso = subprocess.run(
        [str(python), *argv], cwd=str(cwd), env=env,
        capture_output=True, text=True, timeout=timeout, check=False,
    )
    if proceso.returncode != 0:
        salida = "\n".join(x for x in (proceso.stdout, proceso.stderr) if x)
        raise RuntimeError(f"{que} falló (código {proceso.returncode}):\n{salida[-6000:]}")
    return proceso.stdout


@contextmanager
def backend_en_marcha(python: Path, backend: Path, env: dict[str, str], registro: Path):
    """Arranca uvicorn con el MISMO argv que `spawn_backend`."""
    puerto = puerto_libre()
    with registro.open("w", encoding="utf-8") as log:
        proceso = subprocess.Popen(
            [
                str(python), "-m", "uvicorn", "api.main:app",
                "--host", "127.0.0.1", "--port", str(puerto),
                "--loop", "asyncio", "--app-dir", str(backend),
            ],
            cwd=str(backend), env=env, stdout=log, stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    try:
        limite = time.monotonic() + 300
        ultimo = "sin respuesta"
        while time.monotonic() < limite:
            if proceso.poll() is not None:
                cola = registro.read_text(encoding="utf-8", errors="replace")[-5000:]
                raise RuntimeError(
                    f"el backend murió con código {proceso.returncode}:\n{cola}"
                )
            try:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{puerto}/health", timeout=3
                ) as respuesta:
                    cuerpo = json.loads(respuesta.read().decode("utf-8"))
                if cuerpo.get("app") == "mol-design" and cuerpo.get("app_mode") == "DESKTOP":
                    yield puerto, cuerpo
                    return
                ultimo = f"contrato de salud incompleto: {cuerpo}"
            except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
                ultimo = str(exc)
            time.sleep(0.5)
        cola = registro.read_text(encoding="utf-8", errors="replace")[-5000:]
        raise RuntimeError(f"el backend no respondió a /health: {ultimo}\n{cola}")
    finally:
        if proceso.poll() is None:
            proceso.terminate()
            try:
                proceso.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proceso.kill()
                proceso.wait(timeout=15)


def snapshot_por_http(puerto: int, caso: dict) -> dict:
    """Pide el paquete del caso y devuelve `case/dossier_model.json`.

    Es la superficie pública: la misma que usa la aplicación para exportar.
    """
    proyeccion = {
        "case_id": caso["clave"],
        "name": f"Verificacion runtime embebido - {caso['clave']}",
        "context": {
            "study_kind": "verificacion_de_runtime",
            "question": "El backend empaquetado emite el mismo dossier que el de desarrollo.",
        },
        "inputs": {
            "receptor": {"pdb_id": caso["pdb"], "chain": "A"},
            "ligand": {"input_smiles": caso["smiles"]},
        },
        "run": {"task_id": caso["task_id"]},
    }
    peticion = urllib.request.Request(
        f"http://127.0.0.1:{puerto}/evaluation/dossier/{caso['molecule_uuid']}/package",
        data=json.dumps(proyeccion).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(peticion, timeout=180) as respuesta:
            crudo = respuesta.read()
    except urllib.error.HTTPError as exc:
        raise RuntimeError(
            f"{caso['clave']}: la API devolvió {exc.code}: "
            f"{exc.read().decode('utf-8', 'replace')[:2000]}"
        ) from exc

    with zipfile.ZipFile(io.BytesIO(crudo)) as paquete:
        nombres = paquete.namelist()
        interno = next(
            (n for n in nombres if n.endswith("case/dossier_model.json")), None
        )
        if interno is None:
            raise RuntimeError(
                f"{caso['clave']}: el paquete no trae case/dossier_model.json. "
                f"Contiene: {nombres[:20]}"
            )
        return json.loads(paquete.read(interno).decode("utf-8"))


# ══════════════════════════════════════════════════════════════════════════
# Comparación
# ══════════════════════════════════════════════════════════════════════════

def campos_de_generacion(dossier: dict) -> list[dict]:
    return list(dossier.get("generacion") or [])


def comparar_con_golden(dossier: dict, golden: dict, estado: str, clave: str) -> list[str]:
    """Nivel 1: los bloques de protocolo, contra la corrida dorada.

    Se comparan los campos que el golden sella, en su mismo orden y con sus
    cuatro claves. Un campo del golden que no aparezca en el dossier es un
    fallo; los que el dossier añade —eficiencia, cobertura— no lo son: el
    golden sella un bloque, no la sección entera.
    """
    esperados = golden["estados"][estado]
    etiquetas = [c["etiqueta"] for c in esperados]
    presentes = {c["etiqueta"]: c for c in campos_de_generacion(dossier)}

    problemas = [
        f"{clave}: falta el campo «{etiqueta}» en el dossier emitido"
        for etiqueta in etiquetas if etiqueta not in presentes
    ]

    for esperado in esperados:
        actual = presentes.get(esperado["etiqueta"])
        if actual is None:
            continue
        for llave in ("valor", "estado", "razon", "valor_es_clasificacion"):
            if esperado.get(llave) != actual.get(llave):
                problemas.append(
                    f"{clave} · «{esperado['etiqueta']}» · {llave}:\n"
                    f"    golden   : {esperado.get(llave)!r}\n"
                    f"    embebido : {actual.get(llave)!r}"
                )

    # El ORDEN también es contrato: el dossier se lee de arriba abajo.
    orden_emitido = [c["etiqueta"] for c in campos_de_generacion(dossier) if c["etiqueta"] in set(etiquetas)]
    if orden_emitido != [e for e in etiquetas if e in set(orden_emitido)]:
        problemas.append(
            f"{clave}: el orden de los campos difiere.\n"
            f"    golden   : {etiquetas}\n"
            f"    embebido : {orden_emitido}"
        )
    return problemas


#: Lo único que puede diferir entre desarrollo y runtime embebido. Cada entrada
#: es una ruta dentro del JSON canónico, y cada una tiene que estar justificada:
#: `generated_at` es el reloj. Nada más entra aquí sin un motivo escrito.
EXCLUSIONES = ("generated_at",)


def comparar_dossieres(desarrollo: dict, embebido: dict, clave: str) -> list[str]:
    """Nivel 2: el dossier entero, salvo el reloj."""
    a = {k: v for k, v in desarrollo.items() if k not in EXCLUSIONES}
    b = {k: v for k, v in embebido.items() if k not in EXCLUSIONES}
    if a == b:
        return []

    problemas = []
    for llave in sorted(set(a) | set(b)):
        if a.get(llave) != b.get(llave):
            izq = json.dumps(a.get(llave), ensure_ascii=False, sort_keys=True, indent=2)
            der = json.dumps(b.get(llave), ensure_ascii=False, sort_keys=True, indent=2)
            problemas.append(
                f"{clave} · sección «{llave}» difiere entre desarrollo y runtime "
                f"embebido:\n  desarrollo:\n{izq[:2500]}\n  embebido:\n{der[:2500]}"
            )
    return problemas


# ══════════════════════════════════════════════════════════════════════════
# Orquestación
# ══════════════════════════════════════════════════════════════════════════

def preparar_casos() -> list[dict]:
    casos = []
    for caso in CASOS:
        clave = caso["clave"]
        casos.append({
            **caso,
            "rejilla": REJILLA,
            "target_uuid": uid("target", caso["pdb"]),
            "molecule_uuid": uid("molecule", clave),
            "result_uuid": uid("result", clave),
            "task_id": f"verify-{clave}",
            "smiles_hash": hashlib.sha256(caso["smiles"].encode("utf-8")).hexdigest(),
            "momento": MOMENTO_DE_LA_CORRIDA,
        })
    return casos


def corrida(nombre: str, python: Path, backend: Path, vina: Path, casos: list[dict],
            temporal: Path) -> tuple[dict[str, dict], dict]:
    """Siembra, arranca y pide los snapshots de un runtime. Devuelve (snapshots, salud)."""
    hogar = temporal / nombre
    hogar.mkdir(parents=True, exist_ok=True)
    env = entorno_de_tauri(backend, vina, hogar)

    especificacion = temporal / f"casos_{nombre}.json"
    especificacion.write_text(json.dumps(casos, ensure_ascii=False), encoding="utf-8")

    sonda = temporal / f"sonda_siembra_{nombre}.py"
    sonda.write_text(SONDA_SIEMBRA, encoding="utf-8")
    _ejecutar(python, [str(sonda), str(backend), str(especificacion)],
              cwd=backend, env=env, timeout=600, que=f"la siembra de «{nombre}»")

    registro = temporal / f"backend_{nombre}.log"
    snapshots: dict[str, dict] = {}
    with backend_en_marcha(python, backend, env, registro) as (puerto, salud):
        for caso in casos:
            snapshots[caso["clave"]] = snapshot_por_http(puerto, caso)
    return snapshots, salud


def procedencia(nombre: str, python: Path, backend: Path, vina: Path,
                temporal: Path) -> dict:
    hogar = temporal / f"proc_{nombre}"
    hogar.mkdir(parents=True, exist_ok=True)
    env = entorno_de_tauri(backend, vina, hogar)
    sonda = temporal / f"sonda_procedencia_{nombre}.py"
    sonda.write_text(SONDA_PROCEDENCIA, encoding="utf-8")
    salida = _ejecutar(python, [str(sonda), str(backend)], cwd=backend, env=env,
                       timeout=600, que=f"la sonda de procedencia de «{nombre}»")
    return json.loads(salida.strip().splitlines()[-1])


def revisar_aislamiento(informe: dict, raiz: Path, backend_esperado: Path) -> list[str]:
    problemas = []
    if informe.get("canario_tests") is not None:
        problemas.append(
            "CANARIO: el proceso embebido pudo importar `tests`, que sólo existe "
            f"en el repositorio ({informe['canario_tests']}). El árbol de "
            "desarrollo está en su ruta de búsqueda: nada de lo que compruebe "
            "este script describe el bundle."
        )
    raiz_backend = (raiz / "backend").resolve()
    for nombre, archivo in informe.get("modulos", {}).items():
        if archivo is None or str(archivo).startswith("ERROR"):
            problemas.append(f"módulo no importable en el runtime: {nombre} -> {archivo}")
            continue
        resuelto = Path(archivo).resolve()
        if not str(resuelto).lower().startswith(str(backend_esperado.resolve()).lower()):
            problemas.append(
                f"`{nombre}` se resolvió fuera del backend verificado:\n"
                f"    esperado bajo : {backend_esperado}\n"
                f"    resuelto      : {resuelto}"
            )
        elif backend_esperado.resolve() != raiz_backend and str(resuelto).lower().startswith(
            str(raiz_backend).lower()
        ):
            problemas.append(f"`{nombre}` se cargó del repositorio: {resuelto}")
    return problemas


def revisar_manifiesto(informe: dict, raiz: Path) -> list[str]:
    manifiesto = informe.get("manifiesto_m5") or {}
    if not manifiesto.get("presente"):
        return ["el runtime no lleva `m5_zn_manifest.json`: no puede declarar sus perfiles"]

    problemas = []
    origen = raiz / "backend" / "services" / "pipeline" / "protocols" / "m5" / "m5_zn_manifest.json"
    if origen.is_file():
        esperado = hashlib.sha256(origen.read_bytes()).hexdigest()
        if manifiesto.get("sha256") != esperado:
            problemas.append(
                "el manifiesto M5-Zn empaquetado no es el del repositorio:\n"
                f"    repositorio : {esperado}\n"
                f"    empaquetado : {manifiesto.get('sha256')}"
            )
    if manifiesto.get("smarts_sha256_del_modulo") != manifiesto.get("smarts_sha256_declarado"):
        problemas.append(
            "la tabla de SMARTS del `scoring.ums` empaquetado no es la que declara "
            "el manifiesto: el score cambiaría sin que el manifiesto lo dijera.\n"
            f"    módulo     : {manifiesto.get('smarts_sha256_del_modulo')}\n"
            f"    manifiesto : {manifiesto.get('smarts_sha256_declarado')}"
        )
    for divergencia in manifiesto.get("divergencias") or []:
        problemas.append(f"perfil M5-Zn divergente entre módulo y manifiesto: {divergencia}")
    return problemas


#: Lo que el runtime embebido tiene que producir para cada diana de zinc. Es el
#: contrato cientifico de M5-V1, y esta aqui —en el gate del bundle— porque un
#: instalador que produjera otra cosa estaria afirmando algo distinto de lo
#: probado. Ver `docs/77_CORRIGENDUM_SITIO_DEL_BENCHMARK_M5_ZN.md`.
ESTADOS_M5_ESPERADOS = {
    "3DC3": "NOT_EVALUATED_MISSING_COMPONENT",
    "1GKC": "REVIEW_INVALID_BENCHMARK_SITE",
    "1O86": "REVIEW_BENCHMARK_TOP1_NOT_METAL_COORDINATING",
    "1BN1": "REVIEW_OUT_OF_VALIDATED_TARGET",
}


def revisar_m5(informe: dict) -> list[str]:
    """Los tres estados de M5-Zn, producidos por el backend EMPAQUETADO.

    Y el invariante que los gobierna: ninguno habilita una conclusión. Si
    alguno saliera `VALIDATED` en el bundle, el producto instalado estaría
    afirmando algo que el repositorio no sostiene.
    """
    datos = informe.get("m5_zn") or {}
    if "error" in datos:
        return [f"M5-Zn no se pudo ejecutar en el runtime embebido: {datos['error']}"]

    problemas = []
    for pdb, esperado in ESTADOS_M5_ESPERADOS.items():
        obtenido = (datos.get(pdb) or {}).get("estado")
        if obtenido != esperado:
            problemas.append(
                f"M5-Zn/{pdb}: el runtime embebido produce «{obtenido}» y se "
                f"esperaba «{esperado}»"
            )

    habilitan = datos.get("_habilitan_conclusion") or {}
    liberables = [pdb for pdb, ok in habilitan.items() if ok]
    if liberables:
        problemas.append(
            f"M5-Zn: {liberables} habilitan una conclusión en el runtime "
            "embebido. Hoy NINGÚN perfil es científicamente liberable: CA2 se "
            "abstiene por ausencia de GNN-D, y MMP9 y ACE tienen su benchmark "
            "en revisión (docs/77)."
        )

    # El score de los perfiles en cuarentena SÍ tiene que estar: ocultarlo
    # impediría auditarlo. Lo que no puede es habilitar nada.
    for pdb in ("1GKC", "1O86"):
        if (datos.get(pdb) or {}).get("score") is None:
            problemas.append(
                f"M5-Zn/{pdb}: el score desapareció. Un perfil en cuarentena "
                "sigue calculándolo —es reproducible— y se muestra como "
                "evidencia de auditoría."
            )
    return problemas


def revisar_peptido(informe: dict) -> list[str]:
    """La abstención peptídica, tal como la ejerce el runtime empaquetado.

    ADR 76 §5 y §9.8: la estructura plegada y su pLDDT son evidencia válida; la
    afinidad no existe y no se fabrica. Las tres cosas tienen que viajar juntas
    o el estado deja de ser distinguible de un acoplamiento fallido.
    """
    datos = informe.get("peptido") or {}
    if "error" in datos:
        return [f"la primitiva de abstención peptídica no se pudo ejercer: {datos['error']}"]

    problemas = []
    if datos.get("origen") != datos.get("origen_esperado"):
        problemas.append(
            f"la pose sin acoplar se marca «{datos.get('origen')}» y no "
            f"«{datos.get('origen_esperado')}»: una estructura plegada estaría "
            "viajando etiquetada como acoplada"
        )
    if datos.get("vina_affinity_kcal_mol") is not None:
        problemas.append(
            f"se fabricó una afinidad sin acoplamiento: "
            f"{datos['vina_affinity_kcal_mol']}"
        )
    # El pLDDT viene de un PDB con B-factors en 0-1, como los escribe
    # `output_to_pdb`. Que salga 72.0 y no 0.72 es la normalización de escala
    # que faltaba y hacía que TODA corrida de ESMFold avisara de «pLDDT bajo» y
    # reportara una centésima parte de la confianza que tenía.
    plddt = datos.get("plddt_0_100")
    if not isinstance(plddt, (int, float)) or abs(plddt - 72.0) > 1e-6:
        problemas.append(
            f"el pLDDT empaquetado no está en escala 0-100: {plddt} (se esperaba "
            "72.0 a partir de B-factors 0.72, que es la escala que escribe "
            "`output_to_pdb`)"
        )
    if datos.get("confianza_del_plegado") != 0.72:
        problemas.append(
            "la confianza del plegado no llega a la pose: "
            f"{datos.get('confianza_del_plegado')}"
        )
    if datos.get("best_affinity_obligatorio") is not True:
        problemas.append(
            "`DockingResult.best_affinity` dejó de ser obligatorio en el bundle. "
            "Ese contrato se cumplía antes rellenándolo con −4.0; la solución no "
            "es hacerlo opcional, es no construir el resultado sin acoplamiento."
        )
    return problemas


def compilar_las_sondas() -> None:
    """Las sondas son CADENAS: compilar este archivo no las compila.

    Un error de sintaxis dentro de una de ellas no se ve hasta que arranca el
    subproceso, y para entonces ya se ha pagado el arranque en frío de un
    runtime de 1.9 GB. Compilarlas aquí cuesta microsegundos.
    """
    for nombre, fuente in (
        ("SONDA_PROCEDENCIA", SONDA_PROCEDENCIA),
        ("SONDA_SIEMBRA", SONDA_SIEMBRA),
    ):
        compile(fuente, f"<{nombre}>", "exec")


def validar_los_casos(raiz: Path) -> None:
    """Cada caso apunta a un estado que el golden tiene. Se comprueba ANTES.

    Este gate arranca dos runtimes y pide diez dossieres por HTTP: unos ocho
    minutos. Descubrir en el minuto siete que un caso apunta a un estado
    renombrado —un `KeyError` seco— cuesta la corrida entera, y ya la costó una
    vez, al renombrar `perfil_exacto_completo` tras la cuarentena de MMP9.
    """
    for caso in CASOS:
        ruta = raiz / "backend" / "tests" / "goldens" / f"{caso['golden']}.json"
        estados = json.loads(ruta.read_text(encoding="utf-8"))["estados"]
        if caso["estado"] not in estados:
            raise KeyError(
                f"el caso «{caso['clave']}» apunta al estado "
                f"«{caso['estado']}», que {caso['golden']} ya no tiene. "
                f"Tiene: {sorted(estados)}"
            )


def main(raiz: Path) -> int:
    compilar_las_sondas()
    raiz = raiz.resolve()
    validar_los_casos(raiz)
    recursos = raiz / "frontend" / "src-tauri" / "resources"
    python_embebido = recursos / "python" / "python.exe"
    backend_embebido = recursos / "backend"
    vina_embebido = recursos / "tools" / "vina" / "vina.exe"

    python_desarrollo = raiz / "python-embed" / "python.exe"
    backend_desarrollo = raiz / "backend"
    vina_desarrollo = raiz / "tools" / "vina" / "vina.exe"

    for ruta in (python_embebido, backend_embebido, python_desarrollo, backend_desarrollo):
        if not ruta.exists():
            raise FileNotFoundError(
                f"falta {ruta}. Ejecuta `npm run stage:desktop` antes de verificar."
            )

    goldens = {
        nombre: json.loads(
            (raiz / "backend" / "tests" / "goldens" / f"{nombre}.json").read_text(
                encoding="utf-8"
            )
        )
        for nombre in ("dossier_m4", "dossier_m5_zn", "dossier_peptido")
    }
    casos = preparar_casos()
    problemas: list[str] = []

    temporal = Path(tempfile.mkdtemp(prefix="moldesign-dossier-embebido-"))
    try:
        print("[1/5] procedencia del runtime embebido")
        informe = procedencia("embebido", python_embebido, backend_embebido,
                              vina_embebido, temporal)
        print(f"      sys.executable          {informe['sys_executable']}")
        for nombre, archivo in sorted(informe["modulos"].items()):
            print(f"      {nombre:<44} {archivo}")
        manifiesto = informe.get("manifiesto_m5") or {}
        print(f"      manifiesto M5-Zn        {manifiesto.get('ruta')}")
        print(f"      sha256                  {manifiesto.get('sha256')}")
        print(f"      canario `tests`         no importable: {informe.get('canario_error')}")
        peptido = informe.get("peptido") or {}
        print(
            f"      abstención peptídica    origen={peptido.get('origen')} · "
            f"afinidad={peptido.get('vina_affinity_kcal_mol')} · "
            f"pLDDT={peptido.get('plddt_0_100')}"
        )
        problemas += revisar_aislamiento(informe, raiz, backend_embebido)
        problemas += revisar_manifiesto(informe, raiz)
        problemas += revisar_peptido(informe)
        problemas += revisar_m5(informe)
        m5 = informe.get("m5_zn") or {}
        for _pdb in ("3DC3", "1GKC", "1O86"):
            _d = m5.get(_pdb) or {}
            print(f"      M5-Zn {_pdb:<18} {_d.get('estado')}")
        if problemas:
            print("\nERROR de aislamiento o procedencia:\n  - " + "\n  - ".join(problemas))
            return 1

        print(f"[2/5] corrida embebida: sembrando y pidiendo {len(casos)} dossieres por HTTP")
        embebidos, salud = corrida("embebido", python_embebido, backend_embebido,
                                   vina_embebido, casos, temporal)
        print(f"      backend {salud.get('version')} · {len(embebidos)} snapshots")

        print("[3/5] corrida de desarrollo, por la misma superficie")
        desarrollados, _ = corrida("desarrollo", python_desarrollo, backend_desarrollo,
                                   vina_desarrollo, casos, temporal)

        print("[4/5] nivel 1: bloques de protocolo contra las corridas doradas")
        for caso in casos:
            problemas += comparar_con_golden(
                embebidos[caso["clave"]], goldens[caso["golden"]],
                caso["estado"], caso["clave"],
            )

        print("[5/5] nivel 2: dossier canónico completo, desarrollo contra embebido")
        for caso in casos:
            problemas += comparar_dossieres(
                desarrollados[caso["clave"]], embebidos[caso["clave"]], caso["clave"]
            )
    finally:
        shutil.rmtree(temporal, ignore_errors=True)

    if problemas:
        print(
            "\nERROR: el dossier del runtime embebido no coincide.\n\n"
            + "\n\n".join(problemas[:40])
            + "\n\nUna diferencia EXIGE explicación. Los goldens no se regeneran "
            "porque este gate falle: el fallo dice que el producto instalado "
            "afirma algo distinto de lo que se probó."
        )
        return 1

    print(
        f"\nCadena cerrada: {len(casos)} casos. Los bloques de protocolo del runtime "
        "embebido coinciden con las corridas doradas, y el dossier canónico completo "
        "coincide con el de desarrollo salvo `generated_at`. El PDF se renderiza de "
        "ese mismo objeto, así que su contenido científico es el mismo."
    )
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=RAIZ_POR_DEFECTO)
    raise SystemExit(main(parser.parse_args().root))
