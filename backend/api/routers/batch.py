"""
api/routers/batch.py

Batch virtual screening: subi un archivo CSV/Excel/SDF con multiples
SMILES, evalua todas contra un target, y descarga los resultados
rankeados de mejor a peor en Excel.
"""

from __future__ import annotations

import asyncio
import io
import uuid as _uuid_mod
from datetime import datetime, UTC
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from core.database import get_db
from core.models import UserORM
from api.dependencies import get_current_user_optional
from services.targets.access import get_target_for_user
from db.repository import Repository
from utils.logger import get_logger

log = get_logger(__name__)
router = APIRouter(prefix="/evaluation", tags=["Batch Screening"])
settings = get_settings()

# ── Batch state (in-memory, se pierde al reiniciar) ────────────────────────
_batches: dict[str, dict[str, Any]] = {}
_batch_lock = asyncio.Lock()


def _owner_of(current_user: UserORM | None) -> str:
    """BATCH-BE-002. Un cribado pertenece a la cuenta que lo lanzó.

    El estado vive en memoria y no tenía dueño: bastaba conocer el
    identificador —que viaja en enlaces, capturas y paquetes de soporte— para
    leer o exportar el cribado de otra cuenta en la misma máquina. El espacio
    anónimo comparte la etiqueta `demo`, igual que en el resto de `/evaluation`.
    """
    return str(current_user.id) if current_user else "demo"


def _require_own_batch(batch: dict[str, Any] | None, current_user: UserORM | None) -> dict[str, Any]:
    """404 —no 403— para no confirmar la existencia de un cribado ajeno."""
    if batch is None or batch.get("owner_id") != _owner_of(current_user):
        raise HTTPException(status_code=404, detail="Batch no encontrado")
    return batch


def _extract_from_csv(content: str) -> tuple[list[dict[str, str]], dict[str, bool]]:
    """Extrae SMILES + nombres + labels active/inactive desde CSV."""
    import csv
    reader = csv.DictReader(io.StringIO(content))
    molecules = []
    labels = {}
    for row in reader:
        smiles = None
        name = None
        is_active = None
        for key in row:
            kl = key.lower().strip()
            if kl in ("smiles", "canonical_smiles", "structure"):
                smiles = row[key].strip()
            if kl in ("name", "id", "identifier", "molecule_name"):
                name = row[key].strip()
            if kl == "active":
                try:
                    is_active = bool(int(row[key].strip()))
                except (ValueError, TypeError):
                    pass
        if smiles and len(smiles) > 1:
            molecules.append({"smiles": smiles, "name": name or smiles[:20]})
            if name and is_active is not None:
                labels[name] = is_active
    return molecules, labels


def _extract_from_excel(content: bytes) -> tuple[list[dict[str, str]], dict[str, bool]]:
    """Extrae SMILES + nombres + labels active/inactive desde Excel."""
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return [], {}

    headers = [str(h).lower().strip() if h else "" for h in rows[0]]
    smiles_col = next((i for i, h in enumerate(headers) if h in ("smiles", "canonical_smiles", "structure")), None)
    name_col = next((i for i, h in enumerate(headers) if h in ("name", "id", "identifier", "molecule_name")), None)
    active_col = next((i for i, h in enumerate(headers) if h == "active"), None)

    molecules = []
    labels = {}
    for row in rows[1:]:
        smiles = str(row[smiles_col]).strip() if smiles_col is not None and row[smiles_col] else None
        name = str(row[name_col]).strip() if name_col is not None and row[name_col] else None
        if smiles and len(smiles) > 1:
            molecules.append({"smiles": smiles, "name": name or smiles[:20]})
            if name and active_col is not None:
                try:
                    labels[name] = bool(int(row[active_col]))
                except (ValueError, TypeError, IndexError):
                    pass
    wb.close()
    return molecules, labels


async def _get_default_targets() -> list[str]:
    """Todos los targets registrados en la DB (v1.5: 19 targets offline-first)."""
    try:
        from core.database import get_db_session
        from db.repository import Repository
        async with get_db_session() as db:
            repo = Repository(db)
            all_targets = await repo.get_all_targets()
            return [t.pdb_id for t in all_targets if t.is_prepared and t.pdb_id]
    except Exception:
        return ["7E2Y", "3PP0", "1HSG", "3ERT", "1GPK", "1F0R", "1BN1", "1XP0"]


def _extract_smiles_from_sdf(content: str) -> list[dict[str, str]]:
    try:
        from rdkit import Chem
        supplier = Chem.SDMolSupplier()
        supplier.SetData(content)
        molecules = []
        for i, mol in enumerate(supplier):
            if mol is None:
                continue
            smiles = Chem.MolToSmiles(mol)
            name = mol.GetProp("_Name") if mol.HasProp("_Name") else f"MOL-{i+1:03d}"
            molecules.append({"smiles": smiles, "name": name})
        return molecules
    except Exception:
        return []


@router.post("/batch")
async def submit_batch(
    file: UploadFile = File(...),
    target_pdb_id: str = Query("7E2Y", min_length=4, max_length=10,
        description="Target PDB ID. Usar 'ALL' para correr contra todos los targets pre-curados."),
    num_workers: int = Query(2, ge=1, le=6),
    early_exit: bool = Query(
        True,
        deprecated=True,
        description=(
            "RETIRADO (BATCH-SCI-001). Se acepta por compatibilidad y se "
            "ignora: el pre-filtro de vecindad saltaba el acoplamiento y "
            "publicaba ceros como si fueran medidas. La respuesta declara "
            "`early_exit_enabled: false`."
        ),
    ),
    current_user: UserORM | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Virtual screening batch. Subi un archivo con SMILES, los evalua contra el target,
    y devuelve resultados rankeados.

    Multi-target: usa target_pdb_id=ALL para correr contra todos los targets pre-curados.
    Early Exit: si esta activado, MolGraph pre-filtra moleculas similares a inactivos conocidos.
    Label opcional: si el CSV/Excel tiene columna 'active' (1/0), se computa EF/AUC.
    """
    # La ejecución histórica también comparte el contrato de propiedad. Aunque
    # la UI nueva no la use, conocer un PDB ID privado no autoriza a ejecutarlo.
    target_pdb_id = target_pdb_id.upper()
    if target_pdb_id.startswith("USR_"):
        await get_target_for_user(
            Repository(db), target_pdb_id, current_user, allow_missing=True
        )

    # ── Parse file ─────────────────────────────────────────────────
    content = await file.read()
    filename = (file.filename or "batch").lower()

    molecules = []
    active_labels: dict[str, bool] = {}  # name → is_active

    if filename.endswith(".csv"):
        molecules, active_labels = _extract_from_csv(content.decode("utf-8", errors="replace"))
    elif filename.endswith((".xlsx", ".xls")):
        molecules, active_labels = _extract_from_excel(content)
    elif filename.endswith(".sdf"):
        molecules = _extract_smiles_from_sdf(content.decode("utf-8", errors="replace"))
        active_labels = {}
    elif filename.endswith(".txt") or filename.endswith(".smi"):
        text = content.decode("utf-8", errors="replace")
        for line in text.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                parts = line.split()
                smiles = parts[0]
                name = parts[1] if len(parts) > 1 else smiles[:20]
                label = int(parts[2]) if len(parts) > 2 else None
                molecules.append({"smiles": smiles, "name": name})
                if label is not None:
                    active_labels[name] = bool(label)
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Formato no soportado: {filename}. Usa .csv, .xlsx, .sdf, .smi o .txt",
        )

    if not molecules:
        raise HTTPException(status_code=400, detail="No se encontraron SMILES validos en el archivo")

    if len(molecules) > 500:
        raise HTTPException(status_code=400, detail=f"Maximo 500 moleculas por batch. Recibido: {len(molecules)}")

    # ── Resolve targets ───────────────────────────────────────────
    if target_pdb_id == "ALL":
        targets = await _get_default_targets()
    else:
        targets = [target_pdb_id]

    # ── Validate SMILES ────────────────────────────────────────────
    from chem.validator import validate_smiles_or_raise
    valid = []
    invalid = 0
    for m in molecules:
        try:
            v = validate_smiles_or_raise(m["smiles"])
            valid.append({
                "smiles": v.canonical_smiles,
                "name": m["name"],
                "original": m["smiles"],
                "is_active": active_labels.get(m["name"]),
            })
        except Exception:
            invalid += 1

    if not valid:
        raise HTTPException(status_code=400, detail="Ningun SMILES valido en el archivo")

    has_labels = any(m["is_active"] is not None for m in valid)

    # ── Create batch record ────────────────────────────────────────
    batch_id = str(_uuid_mod.uuid4())
    batch = {
        "id": batch_id,
        "targets": targets,
        "total": len(valid) * len(targets),
        "total_molecules": len(valid),
        "completed": 0,
        "failed": 0,
        "skipped_early_exit": 0,
        "invalid_input": invalid,
        "status": "running",
        "results": [],
        "created_at": datetime.now(UTC).isoformat(),
        "num_workers": num_workers,
        "owner_id": _owner_of(current_user),
        # Se guarda el hecho, no la petición: el pre-filtro no se aplica.
        "early_exit": False,
        "has_labels": has_labels,
        "ef_metrics": None,
    }

    async with _batch_lock:
        _batches[batch_id] = batch

    # ── Launch evaluation in background ────────────────────────────
    asyncio.create_task(_process_batch(batch_id, valid, targets, num_workers, False, has_labels))

    return {
        "batch_id": batch_id,
        "total_molecules": len(valid),
        "invalid_skipped": invalid,
        "targets": targets,
        "early_exit_enabled": False,
        "has_active_labels": has_labels,
        "status": "running",
        "estimated_seconds": len(valid) * len(targets) * 25 // num_workers,
    }


@router.get("/batch/{batch_id}")
async def get_batch_status(
    batch_id: str,
    current_user: UserORM | None = Depends(get_current_user_optional),
) -> dict[str, Any]:
    """Get batch evaluation status and partial results."""
    async with _batch_lock:
        batch = _require_own_batch(_batches.get(batch_id), current_user)

    # Return sorted results (best first) if complete
    results = batch.get("results", [])
    if batch["status"] == "completed":
        results = sorted(
            results,
            key=lambda r: r.get("total_score") or 0,
            reverse=True,
        )

    return {
        "batch_id": batch["id"],
        "status": batch["status"],
        "total": batch["total"],
        "completed": batch["completed"],
        "failed": batch.get("failed", 0),
        "skipped_early_exit": batch.get("skipped_early_exit", 0),
        "invalid_input": batch.get("invalid_input", 0),
        "targets": batch.get("targets", [batch.get("target_pdb_id", "")]),
        "early_exit_enabled": batch.get("early_exit", False),
        "has_active_labels": batch.get("has_labels", False),
        "ef_metrics": batch.get("ef_metrics"),
        "results": results,
    }


@router.get("/batch/{batch_id}/export")
async def export_batch_excel(
    batch_id: str,
    current_user: UserORM | None = Depends(get_current_user_optional),
) -> StreamingResponse:
    """Export batch results as Excel file, ranked best to worst."""
    async with _batch_lock:
        batch = _require_own_batch(_batches.get(batch_id), current_user)

    if batch["status"] != "completed":
        raise HTTPException(status_code=400, detail="Batch aun en progreso")

    results = sorted(
        batch["results"],
        key=lambda r: r.get("total_score") or 0,
        reverse=True,
    )

    # ── Build Excel ─────────────────────────────────────────────────
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = f"Batch_{batch_id[:8]}"

        # Styles
        header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="1a1a2e", end_color="1a1a2e", fill_type="solid")
        pass_fill = PatternFill(start_color="dcfce7", end_color="dcfce7", fill_type="solid")
        fail_fill = PatternFill(start_color="fee2e2", end_color="fee2e2", fill_type="solid")
        thin_border = Border(
            left=Side(style="thin", color="e2e8f0"),
            right=Side(style="thin", color="e2e8f0"),
            top=Side(style="thin", color="e2e8f0"),
            bottom=Side(style="thin", color="e2e8f0"),
        )

        # Headers
        headers = [
            "Rank", "Molecule Name", "SMILES", "Total Score", "Affinity (kcal/mol)",
            "MW (Da)", "LogP", "TPSA", "HBD", "HBA",
            "Lipinski", "Veber", "Ghose", "Egan", "Muegge",
            "Fsp3", "QED", "SA Score", "PAINS", "ADMET Score",
            "BBB", "hERG Alerts",
        ]
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", wrap_text=True)
            cell.border = thin_border

        # Data rows
        for i, r in enumerate(results):
            row = i + 2
            is_pains = r.get("is_pains", False) or (r.get("pains_count", 0) > 0)
            row_fill = fail_fill if is_pains else None

            values = [
                i + 1,
                r.get("name", ""),
                r.get("smiles", ""),
                round(r.get("total_score") or 0, 1),
                round(r.get("affinity_kcal") or 0, 2),
                round(r.get("molecular_weight") or 0, 1),
                round(r.get("log_p") or 0, 2),
                round(r.get("tpsa") or 0, 1),
                r.get("hbd", 0),
                r.get("hba", 0),
                "PASS" if r.get("lipinski_pass") else "FAIL",
                "PASS" if r.get("veber_pass") else "FAIL",
                "PASS" if r.get("ghose_pass") else "FAIL",
                "PASS" if r.get("egan_pass") else "FAIL",
                f"{r.get('muegge_score', '?')}/9" if r.get("muegge_pass") is not None else "N/A",
                round(r.get("fsp3") or 0, 3),
                round(r.get("qed") or 0, 3),
                round(r.get("sa_score") or 0, 1),
                "YES" if is_pains else "NO",
                round(r.get("admet_score") or 0, 1),
                "YES" if r.get("bbb_permeable") else "NO",
                r.get("herg_alerts", 0),
            ]

            for col, value in enumerate(values, 1):
                cell = ws.cell(row=row, column=col, value=value)
                cell.border = thin_border
                cell.alignment = Alignment(horizontal="center" if col != 2 and col != 3 else "left")
                if row_fill:
                    cell.fill = row_fill
                # Highlight PAINS
                if col == 19 and is_pains:
                    cell.font = Font(color="dc2626", bold=True)

        # Column widths
        widths = [6, 22, 35, 11, 14, 9, 8, 8, 6, 6, 10, 10, 10, 10, 10, 9, 9, 9, 8, 11, 6, 10]
        for i, w in enumerate(widths):
            ws.column_dimensions[get_column_letter(i + 1)].width = w

        # Freeze header
        ws.freeze_panes = "A2"

        # Auto-filter
        ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{len(results) + 1}"

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        wb.close()

        targets = batch.get("targets", [])
        target_label = targets[0] if targets and len(targets) == 1 else "ALL"
        filename = f"MolDesign_Batch_{batch_id[:8]}_{target_label}.xlsx"
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    except ImportError:
        raise HTTPException(status_code=500, detail="openpyxl no instalado. Instalar con: pip install openpyxl")


@router.get("/batch/{batch_id}/csv")
async def export_batch_csv(
    batch_id: str,
    current_user: UserORM | None = Depends(get_current_user_optional),
) -> StreamingResponse:
    """Export batch results as CSV file."""
    async with _batch_lock:
        propio = _batches.get(batch_id)
        # El 400 histórico distingue «existe pero no ha terminado». Se conserva
        # SÓLO para el dueño: a una cuenta ajena no se le confirma nada.
        batch = _require_own_batch(propio, current_user)

    if batch["status"] != "completed":
        raise HTTPException(status_code=400, detail="Batch no completado")

    results = sorted(
        batch["results"],
        key=lambda r: r.get("total_score") or 0,
        reverse=True,
    )

    output = io.StringIO()
    headers = [
        "Rank", "Name", "SMILES", "TotalScore", "Affinity_kcal",
        "MW", "LogP", "TPSA", "Lipinski", "Veber", "Ghose", "Egan", "Muegge",
        "Fsp3", "QED", "SAScore", "PAINS", "ADMET_Score",
    ]
    output.write(",".join(headers) + "\n")

    for i, r in enumerate(results):
        row = [
            str(i + 1),
            f'"{r.get("name", "")}"',
            r.get("smiles", ""),
            str(round(r.get("total_score") or 0, 1)),
            str(round(r.get("affinity_kcal") or 0, 2)),
            str(round(r.get("molecular_weight") or 0, 1)),
            str(round(r.get("log_p") or 0, 2)),
            str(round(r.get("tpsa") or 0, 1)),
            "PASS" if r.get("lipinski_pass") else "FAIL",
            "PASS" if r.get("veber_pass") else "FAIL",
            "PASS" if r.get("ghose_pass") else "FAIL",
            "PASS" if r.get("egan_pass") else "FAIL",
            str(r.get("muegge_score", "?")) if r.get("muegge_pass") is not None else "N/A",
            str(round(r.get("fsp3") or 0, 3)),
            str(round(r.get("qed") or 0, 3)),
            str(round(r.get("sa_score") or 0, 1)),
            "YES" if r.get("is_pains") else "NO",
            str(round(r.get("admet_score") or 0, 1)),
        ]
        output.write(",".join(row) + "\n")

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="batch_{batch_id[:8]}.csv"'},
    )


# ── Background processing ────────────────────────────────────────────────────

async def _process_batch(
    batch_id: str,
    molecules: list[dict],
    targets: list[str],
    num_workers: int,
    early_exit: bool,
    has_labels: bool,
) -> None:
    """Evalúa cada molécula contra cada target y acumula lo que se calculó.

    `early_exit` sobrevive en la firma porque la llamada histórica lo pasa
    posicionalmente; ya no gobierna nada (BATCH-SCI-001). Toda molécula válida
    se acopla: el descarte heurístico no puede decidir qué entra en el
    denominador de EF/ROC-AUC ni publicar un cero por una medida.
    """
    import asyncio as _asyncio

    sem = _asyncio.Semaphore(num_workers)
    early_exit_skipped = 0  # se conserva en el contrato de métricas: siempre 0

    # ── Per-target + per-molecule evaluation ──────────────────────
    for target_pdb_id in targets:
        target_pdb_id = target_pdb_id.upper()

        for mol in molecules:
            name = mol["name"]
            smiles = mol["smiles"]

            async with sem:
                # BATCH-SCI-001. Aqui vivia un pre-filtro de vecindad
                # (`predict_early_exit`) que saltaba el acoplamiento y metia la
                # molecula en la tabla con `total_score: 0` y
                # `affinity_kcal: 0` — cifras que nadie midio. Ademas solo se
                # aplicaba a las moleculas NO marcadas como activas, de modo
                # que descartaba senuelos usando la etiqueta que EF y ROC-AUC
                # pretenden medir. Se acopla todo lo que entra; el descarte
                # heuristico no decide el denominador de un benchmark.

                # ── Full evaluation ────────────────────────────────
                try:
                    from services.docking.queue_handler import _run_full_evaluation_async

                    task_id = str(_uuid_mod.uuid4())
                    pipeline_result = await _run_full_evaluation_async(
                        task_id=task_id,
                        smiles=smiles,
                        target_pdb_id=target_pdb_id,
                        molecule_name=name,
                    )

                    molecule_id = pipeline_result.get("molecule_id")
                    if not molecule_id:
                        result = {"name": name, "smiles": smiles, "target": target_pdb_id,
                                  "status": "failed", "error": "No molecule_id"}
                    else:
                        from uuid import UUID
                        from core.database import get_db_session
                        from db.repository import Repository
                        from core.models import EvaluationResultRead

                        async with get_db_session() as db:
                            repo = Repository(db)
                            eval_data = await repo.get_evaluation_result(UUID(molecule_id))
                            if eval_data:
                                r = EvaluationResultRead.model_validate(eval_data)
                                pains_count = len(r.pains_matches) if r.pains_matches else 0
                                result = {
                                    "molecule_id": str(r.molecule_id),
                                    "name": name, "smiles": smiles, "target": target_pdb_id,
                                    "status": "success",
                                    "affinity_kcal": r.affinity_kcal,
                                    "total_score": r.total_score,
                                    "adme_score": r.adme_score,
                                    "molecular_weight": r.molecular_weight,
                                    "log_p": r.log_p, "tpsa": r.tpsa,
                                    "lipinski_pass": r.lipinski_pass,
                                    "veber_pass": r.veber_pass,
                                    "pains_count": pains_count,
                                    "is_pains": r.is_pains,
                                    "qed": r.qed, "sa_score": r.sa_score,
                                }
                            else:
                                result = {"name": name, "smiles": smiles, "target": target_pdb_id,
                                          "status": "failed", "error": "Result not found in DB"}
                except Exception as e:
                    result = {"name": name, "smiles": smiles, "target": target_pdb_id,
                              "status": "failed", "error": str(e)[:200]}

                # ── Update batch state ────────────────────────────
                async with _batch_lock:
                    batch = _batches.get(batch_id)
                    if batch:
                        batch["completed"] += 1
                        if result.get("status") == "failed":
                            batch["failed"] += 1
                        batch["results"].append(result)
                        if batch["completed"] >= batch["total"]:
                            batch["status"] = "completed"

    # ── EF/AUC si hay labels ──────────────────────────────────────
    async with _batch_lock:
        batch = _batches.get(batch_id)
        if batch and has_labels and batch["status"] == "completed":
            try:
                batch["ef_metrics"] = _compute_ef_metrics(
                    batch["results"], molecules, early_exit_skipped
                )
            except Exception as e:
                log.warning("ef_computation_failed", error=str(e))

    log.info("batch_complete", batch_id=batch_id, targets=len(targets), total=batch["total"] if batch else 0)


def _compute_ef_metrics(results: list[dict], molecules: list[dict], skipped: int) -> dict | None:
    """Computa EF@1%, EF@5%, EF@10% y ROC-AUC si hay labels active/inactive."""

    name_to_active = {m["name"]: m.get("is_active", False) for m in molecules}

    scored = [
        (r.get("total_score") or 0, bool(name_to_active.get(r["name"], False)))
        for r in results
        if r.get("status") == "success" and r.get("total_score") is not None
    ]
    if not scored or not any(a for _, a in scored):
        return None

    scored.sort(key=lambda x: x[0], reverse=True)
    n = len(scored)
    n_act = sum(1 for _, a in scored if a)
    if n_act == 0:
        return None

    def ef_at(pct: float) -> float:
        top_n = max(1, int(n * pct / 100))
        found = sum(1 for _, a in scored[:top_n] if a)
        expected = n_act * (top_n / n)
        return round(found / expected, 2) if expected > 0 else 0.0

    try:
        from sklearn.metrics import roc_auc_score
        y_true = [int(a) for _, a in scored]
        y_score = [s for s, _ in scored]
        auc = round(float(roc_auc_score(y_true, y_score)), 4)
    except Exception:
        auc = None

    return {
        "n_total": n,
        "n_actives": n_act,
        "n_early_exit_skipped": skipped,
        "ef_1pct": ef_at(1.0),
        "ef_5pct": ef_at(5.0),
        "ef_10pct": ef_at(10.0),
        "roc_auc": auc,
    }
