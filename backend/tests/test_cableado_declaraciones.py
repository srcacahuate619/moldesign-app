"""
Que las declaraciones lleguen de verdad a la corrida, no sólo existan.

Dos módulos nuevos calculan bien y tienen sus pruebas —`censo_de_aguas` y el
`estado_del_ligando` de `chem/conformer.py`—, pero un cálculo correcto que
nadie enchufa no declara nada. Estas pruebas miran el CABLE, que es lo que
ninguna de las otras cubre.

Son estructurales a propósito: ejercitar el camino real exigiría receptor
preparado, Vina y base de datos. Lo que puede romperse en silencio es que
alguien quite la llamada, y eso se ve en el árbol sintáctico.
"""

import ast
import inspect
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]


# ── El censo de aguas llega al acoplamiento ────────────────────────────────

def test_vina_service_censa_las_aguas_antes_de_acoplar():
    fuente = (RAIZ / "services" / "docking" / "vina_service.py").read_text(encoding="utf-8")
    assert "from services.chemistry.censo_de_aguas import" in fuente
    assert "censar_aguas(" in fuente
    assert "describir_censo(" in fuente


def test_el_censo_se_emite_como_aviso_declarado():
    """Con severidad, no como texto suelto: así llega a la pestaña y al dossier."""
    fuente = (RAIZ / "services" / "docking" / "vina_service.py").read_text(encoding="utf-8")
    assert 'aviso(\n                        "SITIO_DESOLVATADO", Severidad.INFO' in fuente or (
        "SITIO_DESOLVATADO" in fuente and "Severidad.INFO" in fuente
    )


def test_se_mide_sobre_el_pdb_depositado_no_sobre_el_preparado():
    """El preparado ya no tiene aguas: censarlo daría siempre cero."""
    fuente = (RAIZ / "services" / "docking" / "vina_service.py").read_text(encoding="utf-8")
    indice = fuente.index("censar_aguas(")
    contexto = fuente[max(0, indice - 600):indice]
    assert "StoragePath.target_raw(" in contexto


def test_si_no_se_puede_censar_se_dice():
    """«Sin la línea de aguas» y «no se pudo medir» no significan lo mismo."""
    fuente = (RAIZ / "services" / "docking" / "vina_service.py").read_text(encoding="utf-8")
    assert "No se pudo leer la estructura" in fuente


def test_el_censo_usa_la_caja_efectiva_y_no_la_declarada():
    """La caja puede resolverse dinámicamente; censar otra sería censar otro sitio."""
    fuente = (RAIZ / "services" / "docking" / "vina_service.py").read_text(encoding="utf-8")
    indice = fuente.index("censar_aguas(")
    llamada = fuente[indice:indice + 120]
    assert "effective_center" in llamada and "effective_size" in llamada


# ── El estado del ligando se persiste ──────────────────────────────────────

def test_el_conformer_devuelve_el_estado_del_ligando():
    """La clave viaja en el resultado, la construya la mitad que la construya.

    `generate_conformer` se partió en dos el 2026-09-04 para sacar el trabajo de
    RDKit del bucle de eventos (ver `test_rdkit_no_bloquea_el_bucle.py`): el
    envoltorio asíncrono escribe el .sdf y `_construir_conformero` hace el resto.
    La clave se arma en el cuerpo y el envoltorio la reenvía, así que mirar sólo
    la fuente del envoltorio dejó de ver nada. Se comprueban las dos mitades, y
    que el envoltorio propague de verdad lo que el cuerpo devuelve.
    """
    from chem.conformer import _construir_conformero, generate_conformer

    cuerpo = inspect.getsource(_construir_conformero)
    envoltorio = inspect.getsource(generate_conformer)

    assert '"estado_del_ligando"' in cuerpo, (
        "el cuerpo del conformer dejó de construir estado_del_ligando"
    )
    assert "**datos" in envoltorio, (
        "el envoltorio dejó de propagar el resultado del cuerpo: la clave "
        "podría construirse y no llegar a quien llama"
    )


def test_el_repositorio_acepta_y_escribe_ligand_state():
    from db.repository import Repository

    firma = inspect.signature(Repository.upsert_evaluation_result)
    assert "ligand_state" in firma.parameters

    fuente = inspect.getsource(Repository.upsert_evaluation_result)
    # Misma regla de upsert que el resto: un `None` intermedio no borra.
    assert "if ligand_state is not None:" in fuente
    assert "result.ligand_state = ligand_state" in fuente


def test_la_columna_existe_en_el_orm_y_en_el_esquema_de_lectura():
    from core.models import EvaluationResultORM, EvaluationResultRead

    assert hasattr(EvaluationResultORM, "ligand_state")
    assert "ligand_state" in EvaluationResultRead.model_fields


def test_el_pipeline_pasa_el_estado_al_guardar():
    fuente = (RAIZ / "services" / "docking" / "queue_handler.py").read_text(encoding="utf-8")
    assert "ligand_state=_estado_del_ligando_persistible" in fuente
    # Y se inicializa antes del camino que lo rellena, para que un péptido
    # —que no pasa por el conformer— no levante NameError.
    assert "_estado_del_ligando_persistible: dict | None = None" in fuente


def test_la_sustitucion_de_especie_se_declara_como_aviso():
    fuente = (RAIZ / "services" / "docking" / "queue_handler.py").read_text(encoding="utf-8")
    assert "ESPECIE_ACOPLADA_DISTINTA" in fuente
    assert "SIN_CORRECCION_DE_PROTONACION" in fuente


# ── Que ningún aviso nuevo se emita sin severidad ──────────────────────────

@pytest.mark.parametrize(
    "ruta",
    [
        "services/docking/vina_service.py",
        "services/docking/queue_handler.py",
        "services/docking/peptide_docking.py",
        "services/docking/quantum_ad4_service.py",
    ],
)
def test_todo_aviso_declara_su_severidad(ruta: str):
    """`aviso(...)` siempre con un `Severidad.X` como segundo argumento.

    Es la propiedad que impide volver a la adivinación por subcadenas: si
    alguien añade un aviso sin severidad, la interfaz tendría que decidirla.
    """
    arbol = ast.parse((RAIZ / ruta).read_text(encoding="utf-8"))
    sin_severidad = []
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, ast.Call):
            continue
        if getattr(nodo.func, "id", None) != "aviso":
            continue
        if len(nodo.args) < 2:
            sin_severidad.append(nodo.lineno)
            continue
        segundo = nodo.args[1]
        es_severidad = (
            isinstance(segundo, ast.Attribute)
            and isinstance(segundo.value, ast.Name)
            and segundo.value.id == "Severidad"
        )
        if not es_severidad:
            sin_severidad.append(nodo.lineno)

    assert not sin_severidad, (
        f"{ruta}: avisos sin `Severidad.X` en las líneas {sin_severidad}"
    )
