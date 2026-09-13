"""Cuatro componentes que se anunciaban y no se ejecutaban.

Auditoría del 2026-09-04. Los cuatro fallaban en silencio, cada uno detrás de
un `except` que trataba la ausencia de resultado como «no disponible».

MM-GBSA — muerto en los dos caminos desde el commit que decía arreglarlo
    El wrapper acepta `<proteina> <smiles> [max_iter] [poses_sdf]` y los dos
    llamadores construían `[proteina, smiles]` y añadían el SDF, que caía en la
    posición de `max_iter`:

        ValueError: invalid literal for int() with base 10: ...sdf

    El proceso moría en la primera línea útil. El comentario encima del
    llamador decía «FIX v2.1 (2026-08-04): pasar el SDF de poses de Vina al
    subprocess para que MM-GBSA calcule sobre la pose REAL».

TabPFN — nunca clasificó nada
    `properties.logp` no existe; el campo es `log_p`. Cada llamada lanzaba
    AttributeError. Además `_tabpfn_loaded = True` se ponía ANTES de cargar,
    así que un fallo de carga era permanente. Y la interfaz pintaba «Sin
    alertas identificadas por TabPFN» en verde, porque una lista vacía no
    distinguía «miró y no encontró» de «no llegó a mirar».

ADMET — rellenaba las claves ausentes con el valor favorable
    PPB=90, BBB=1, HIA=1, hERG=0, Clearance=10, CYP=0. Una salida a la que le
    faltara una cabeza salía convertida en un perfil limpio. ADMET-AI v2 está
    reentrenado y no reproduce v1: un cambio de esquema no es hipotético.

El censo de aguas — NameError en cada corrida
    `read_text` se usaba sin importarlo. El `except Exception` lo convertía en
    «no se pudo medir», así que el censo añadido el 2026-09-04 no llegó a
    contar una sola agua.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
WRAPPER = BACKEND / "services" / "docking" / "mmgbsa_subprocess.py"
EJECUTORES = {
    "queue_handler": BACKEND / "services" / "docking" / "queue_handler.py",
    "runner_pro": BACKEND / "services" / "pipeline" / "runner.py",
}


# ── MM-GBSA ──────────────────────────────────────────────────────────────

def test_el_wrapper_no_muere_al_recibir_un_sdf_donde_iba_max_iter():
    """El fallo exacto, reproducido: un .sdf en el tercer posicional."""
    proceso = subprocess.run(
        [sys.executable, str(WRAPPER), "inexistente.pdb", "CCO", "poses.sdf"],
        capture_output=True, text=True, timeout=180,
    )
    salida = proceso.stdout + proceso.stderr
    assert "invalid literal for int()" not in salida, (
        "el wrapper vuelve a parsear el SDF como `max_iter`: MM-GBSA muere "
        "antes de calcular nada, en los dos caminos de producción."
    )


def test_el_wrapper_acepta_las_poses_por_nombre():
    proceso = subprocess.run(
        [sys.executable, str(WRAPPER), "inexistente.pdb", "CCO", "--poses", "poses.sdf"],
        capture_output=True, text=True, timeout=180,
    )
    salida = proceso.stdout + proceso.stderr
    assert "invalid literal for int()" not in salida
    assert "no interpretable" not in salida


@pytest.mark.parametrize("nombre,ruta", EJECUTORES.items(), ids=list(EJECUTORES))
def test_los_llamadores_pasan_las_poses_por_nombre(nombre: str, ruta: Path):
    fuente = ruta.read_text(encoding="utf-8")
    assert "--poses" in fuente, (
        f"{nombre} vuelve a pasar el SDF como posicional. Cae en la posición de "
        "`max_iter` y el subprocess muere antes de calcular."
    )


# ── TabPFN ───────────────────────────────────────────────────────────────

def test_tabpfn_lee_el_campo_que_existe():
    """`properties.logp` no existe: el campo es `log_p`."""
    from core.models import PhysicochemicalProperties

    campos = set(PhysicochemicalProperties.model_fields)
    assert "log_p" in campos and "logp" not in campos

    fuente = (BACKEND / "chem" / "blood_viability.py").read_text(encoding="utf-8")
    assert "properties.logp," not in fuente, (
        "vuelve a leerse `properties.logp`, que no existe: TabPFN lanzaría "
        "AttributeError en cada llamada y no clasificaría nunca."
    )


def test_tabpfn_no_se_marca_cargado_antes_de_estarlo():
    """Puesta antes del fit, la bandera volvía permanente un fallo de carga."""
    # Sólo código: el comentario que explica el defecto cita la línea vieja, y
    # buscarla en el texto plano encontraría la explicación antes que el código.
    lineas = [
        (i, linea.strip())
        for i, linea in enumerate(
            (BACKEND / "chem" / "blood_viability.py").read_text(encoding="utf-8").splitlines()
        )
        if not linea.strip().startswith("#")
    ]
    pos_fit = next(i for i, l in lineas if "_tabpfn_classifier.fit(" in l)
    pos_marca = next(i for i, l in lineas if l == "_tabpfn_loaded = True")
    assert pos_marca > pos_fit, (
        "`_tabpfn_loaded = True` volvió a ponerse antes del `fit`: si la carga "
        "falla, no se reintenta nunca y el clasificador queda en None para "
        "siempre."
    )


def test_el_estado_de_tabpfn_llega_al_resultado():
    """Una lista de alertas vacía no puede pintarse igual que un aprobado."""
    from core.models import EvaluationResultORM, PhysicochemicalProperties

    assert "blood_tabpfn_estado" in PhysicochemicalProperties.model_fields
    columnas = {c.name for c in EvaluationResultORM.__table__.columns}
    assert "blood_tabpfn_estado" in columnas, (
        "sin esta columna la interfaz no puede distinguir «TabPFN no encontró "
        "nada» de «TabPFN no corrió», que es lo que la pintaba en verde."
    )


# ── ADMET ────────────────────────────────────────────────────────────────

def test_una_cabeza_ausente_de_admet_no_se_rellena_con_el_valor_benigno():
    """El defecto: cada `default=` era la predicción favorable."""
    fuente = (BACKEND / "chem" / "blood_viability.py").read_text(encoding="utf-8")
    for rastro in ("default=90.0", "default=10.0", "default=-3.0"):
        assert rastro not in fuente, (
            f"volvió un default fabricado en las lecturas de ADMET ({rastro}). "
            "Una clave ausente es None, no un valor típico."
        )


def test_admet_avisa_cuando_le_falta_una_cabeza():
    fuente = (BACKEND / "chem" / "blood_viability.py").read_text(encoding="utf-8")
    assert "admet_cabezas_ausentes" in fuente, (
        "no se registra qué claves faltaron. ADMET-AI v2 está reentrenado y no "
        "reproduce v1: un cambio de nombre de salida tiene que verse."
    )


def test_una_prediccion_real_de_admet_sigue_devolviendo_numeros():
    """La contrapartida: quitar los defaults no puede vaciar el panel."""
    from chem.blood_viability import predict_admet_ai

    resultado = predict_admet_ai("CC(=O)Oc1ccccc1C(=O)O")
    if all(v is None for v in resultado.values()):
        pytest.skip("ADMET-AI no está disponible en este equipo")

    for clave in ("Solubility", "PPB", "BBB", "hERG_prob"):
        assert resultado[clave] is not None, (
            f"{clave} salió None con el modelo disponible: se perdió una lectura "
            "real, no un default"
        )


# ── CL-GNN ───────────────────────────────────────────────────────────────

def test_clgnn_exige_la_pose_acoplada():
    """Sin pose no hay nada que puntuar: antes se inventaba un confórmero."""
    import inspect

    from services.ai.clgnn_inference import predict_clgnn

    firma = inspect.signature(predict_clgnn)
    for parametro in ("pose_sdf_path", "pose_pdbqt_block"):
        assert parametro in firma.parameters, (
            f"`predict_clgnn` ya no recibe {parametro}: volvería a generar su "
            "propia conformación ETKDG, en un marco de coordenadas distinto al "
            "del receptor."
        )

    assert predict_clgnn("CCO", "cualquiera.pdb") is None, (
        "sin pose tiene que devolver None, no fabricar una conformación"
    )


def test_clgnn_resuelve_el_nombre_logico_de_la_pose(tmp_path, monkeypatch):
    """La DB guarda ``runs/...``, mientras RDKit necesita la ruta local real."""
    import services.ai.clgnn_inference as clgnn

    pose = tmp_path / "data" / "runs" / "docking" / "poses.sdf"
    pose.parent.mkdir(parents=True)
    pose.write_text("pose real", encoding="utf-8")
    monkeypatch.setattr(clgnn, "_storage_path_for", lambda name: tmp_path / "data" / name)

    assert clgnn._resolve_pose_sdf_path("runs/docking/poses.sdf") == pose


def test_clgnn_no_reinterpreta_una_ruta_absoluta_ausente(tmp_path, monkeypatch):
    """Una ruta absoluta rota no puede convertirse silenciosamente en otro objeto."""
    import services.ai.clgnn_inference as clgnn

    monkeypatch.setattr(
        clgnn,
        "_storage_path_for",
        lambda name: pytest.fail("una ruta absoluta no debe cruzar esta frontera"),
    )

    assert clgnn._resolve_pose_sdf_path(str(tmp_path / "ausente.sdf")) is None


@pytest.mark.parametrize("nombre,ruta", EJECUTORES.items(), ids=list(EJECUTORES))
def test_los_llamadores_de_clgnn_le_dan_la_pose(nombre: str, ruta: Path):
    fuente = ruta.read_text(encoding="utf-8")
    assert "pose_pdbqt_block=" in fuente, (
        f"{nombre} llama a CL-GNN sin la pose: devolvería None siempre"
    )


# ── El censo de aguas ────────────────────────────────────────────────────

def test_vina_service_importa_read_text():
    """Se usaba sin importarlo; el `except` amplio lo escondía."""
    import services.docking.vina_service as vina_service

    assert hasattr(vina_service, "read_text"), (
        "`read_text` volvió a faltar en los imports de `vina_service`. El censo "
        "de aguas lo llama y el NameError se convierte en «no se pudo medir», "
        "así que el censo no cuenta nada y nadie se entera."
    )
