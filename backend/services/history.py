"""Proyección paginable del historial: snapshots por corrida y filas heredadas."""
from sqlalchemy import and_, case, exists, literal, or_, select, union_all
from sqlalchemy.orm import aliased
from core.models import EvaluationResultORM, EvaluationRunORM, MoleculeORM, TargetORM

NUMERIC_FIELDS = (
    'total_score', 'affinity_kcal', 'affinity_score', 'adme_score', 'druglikeness_score',
    'molecular_weight', 'log_p', 'tpsa', 'qed', 'sa_score', 'gnn_score',
)
BOOLEAN_FIELDS = ('lipinski_pass', 'is_pains')
STRING_FIELDS = ('blockchain_tx_id', 'evaluated_at', 'weights_calibration_id', 'target_family')

def history_rows(user_id):
    """La proyección actual sólo entra si su task_id aún no tiene snapshot.

    Los campos científicos de una corrida provienen exclusivamente de su JSON.
    Molécula y target aportan identidad y etiquetas; nunca cifras de otra corrida.
    Las filas sin task_id anteriores a snapshots se conservan sin inventar un ID.
    """
    def identity(saved):
        return [MoleculeORM.id.label('molecule_id'), MoleculeORM.smiles, MoleculeORM.name,
                TargetORM.pdb_id.label('target_pdb_id'), MoleculeORM.target_id, saved.label('is_saved')]
    snap = EvaluationRunORM.snapshot_json
    archive = EvaluationRunORM.task_id.like('projection-archive:%')
    recorded_task = snap['task_id'].as_string()
    other_run = aliased(EvaluationRunORM)
    already_preserved = exists(select(other_run.id).where(
        other_run.molecule_id == EvaluationRunORM.molecule_id,
        other_run.task_id == recorded_task,
        other_run.id != EvaluationRunORM.id,
    )).correlate(EvaluationRunORM)
    canonical_task = case((and_(archive, recorded_task.isnot(None)), recorded_task),
                          else_=EvaluationRunORM.task_id)
    frozen = select(
        *identity(EvaluationRunORM.saved_at.isnot(None)), EvaluationRunORM.id.label('run_id'), canonical_task.label('task_id'),
        case((EvaluationRunORM.status == 'SUCCESS', 'evaluated'),
             (EvaluationRunORM.status == 'FAILURE', 'failed'), else_=EvaluationRunORM.status).label('status'),
        EvaluationRunORM.created_at,
        *[snap[key].as_float().label(key) for key in NUMERIC_FIELDS],
        *[snap[key].as_boolean().label(key) for key in BOOLEAN_FIELDS],
        *[snap[key].as_string().label(key) for key in STRING_FIELDS],
        snap['docking_protocol'].as_json().label('docking_protocol'),
    ).select_from(EvaluationRunORM).join(MoleculeORM, EvaluationRunORM.molecule_id == MoleculeORM.id
    ).join(TargetORM, MoleculeORM.target_id == TargetORM.id).where(MoleculeORM.user_id == user_id,
        or_(~archive, recorded_task.is_(None), ~already_preserved))
    matching = exists(select(EvaluationRunORM.id).where(
        EvaluationRunORM.molecule_id == MoleculeORM.id,
        or_(EvaluationRunORM.task_id == EvaluationResultORM.task_id,
            and_(archive, recorded_task == EvaluationResultORM.task_id)),
    )).correlate(MoleculeORM, EvaluationResultORM)
    any_run = exists(select(EvaluationRunORM.id).where(
        EvaluationRunORM.molecule_id == MoleculeORM.id,
    )).correlate(MoleculeORM)
    # `is_saved` es de la corrida. Una fila heredada sin snapshot sólo se marca
    # cuando la molécula se guardó por la vía anterior y ninguna ficha propia
    # de corrida la sustituyó.
    any_saved_run = exists(select(EvaluationRunORM.id).where(
        EvaluationRunORM.molecule_id == MoleculeORM.id,
        EvaluationRunORM.saved_at.isnot(None),
    )).correlate(MoleculeORM)
    legacy = select(
        *identity(and_(MoleculeORM.is_saved.is_(True), ~any_saved_run)), literal(None).label('run_id'), EvaluationResultORM.task_id,
        MoleculeORM.status.label('status'), MoleculeORM.created_at,
        *[getattr(EvaluationResultORM, key) for key in NUMERIC_FIELDS],
        *[getattr(EvaluationResultORM, key) for key in BOOLEAN_FIELDS],
        *[getattr(EvaluationResultORM, key) for key in STRING_FIELDS],
        EvaluationResultORM.docking_protocol,
    ).select_from(MoleculeORM).join(TargetORM, MoleculeORM.target_id == TargetORM.id
    ).outerjoin(EvaluationResultORM, EvaluationResultORM.molecule_id == MoleculeORM.id
    ).where(MoleculeORM.user_id == user_id, or_(
        and_(EvaluationResultORM.task_id.isnot(None), ~matching), ~any_run,
    ))
    return union_all(frozen, legacy).subquery('history_rows')

def render_history_receipt(molecule, snapshot):
    """Renderiza el recibo conservado; no consulta el resultado mutable actual."""
    from datetime import datetime
    from uuid import UUID
    from hashlib import sha256
    from sqlalchemy import DateTime, Uuid
    from services.blockchain.pdf_generator import generate_certificate_pdf
    from utils.local_storage import path_for

    values = {}
    for column in EvaluationResultORM.__table__.columns:
        value = snapshot.get(column.name)
        if value is not None and isinstance(column.type, DateTime):
            value = datetime.fromisoformat(value)
        elif value is not None and isinstance(column.type, Uuid):
            value = UUID(value)
        values[column.name] = value
    evaluation = EvaluationResultORM(**values)
    poses = None
    expected = ((snapshot.get('docking_protocol') or {}).get('execution_provenance') or {}).get('poses_sha256')
    if expected and snapshot.get('poses_file_path'):
        try:
            raw = path_for(snapshot['poses_file_path']).read_bytes()
            if sha256(raw).hexdigest() == expected:
                poses = raw.decode('utf-8')
        except (OSError, ValueError, UnicodeError):
            pass  # ausencia visible; nunca sustituir por las poses de otra ejecución
    return generate_certificate_pdf(molecule, evaluation, molecule.target.name,
                                    pose_sdf_content=poses, receptor_pdb_content=None).getvalue()
