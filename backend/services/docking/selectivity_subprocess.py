"""Wrapper de subprocess para el Panel de Selectividad (v1.7.3).

PROBLEMA ORIGINAL: el stage `selectivity` del pipeline corría
`run_selectivity_panel` INLINE → bloqueaba el pipeline hasta terminar
5 docks anti-target (minutos) y DUPLICABA el trabajo del frontend
(ProSelectivityPanel corre 1-a-1 por su cuenta).

SOLUCIÓN (patrón MM-GBSA v1.7.2): el pipeline lanza ESTE script como
SUBPROCESS en background. El pipeline reporta "done" INMEDIATAMENTE
(selectivity_ran=False) y este proceso persiste los resultados en DB
cuando termina — con SU PROPIA sesión, sin tocar el snapshot del runner.
El caller registra el proceso con su `task_id` en el registro local para que
el botón "Cancelar" afecte sólo a esa evaluación.

Uso:
    python selectivity_subprocess.py <molecule_id> <smiles> <smiles_hash>
        <target_pdb_id> <on_affinity> <num_workers> <anti_targets_csv>

Escribe el resultado como JSON en stdout (para logging del caller).
"""
from __future__ import annotations

import json
import math
import os
import sys

# Ruta del backend derivada de la ubicación de ESTE archivo:
#   services/docking/selectivity_subprocess.py -> backend/
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from services.docking.selectividad_margen import veredicto_de_margen


def main() -> int:
    if len(sys.argv) < 7:
        print(json.dumps({"error": "faltan argumentos"}))
        return 2

    molecule_id = sys.argv[1]
    smiles = sys.argv[2]
    smiles_hash = sys.argv[3]
    target_pdb_id = sys.argv[4]
    try:
        on_affinity = float(sys.argv[5])
        if not math.isfinite(on_affinity):
            raise ValueError("afinidad no finita")
    except ValueError:
        print(json.dumps({"status": "not_evaluated", "error":
                          "Selectividad no evaluada: falta afinidad principal finita."}))
        return 2
    try:
        num_workers = int(sys.argv[6])
    except ValueError:
        num_workers = 2
    anti_targets_csv = sys.argv[7] if len(sys.argv) > 7 else ""
    task_id = sys.argv[8] if len(sys.argv) > 8 else None
    anti_ids = [a.strip() for a in anti_targets_csv.split(",") if a.strip()] or None

    import asyncio
    from uuid import UUID

    try:
        mol_uuid = UUID(molecule_id)
    except ValueError:
        print(json.dumps({"error": f"molecule_id invalido: {molecule_id}"}))
        return 2

    async def _run() -> dict:
        from services.docking.selectivity import run_selectivity_panel
        from db.repository import Repository
        from core.database import get_db_session, flush_with_retry

        result = await run_selectivity_panel(
            smiles=smiles,
            smiles_hash=smiles_hash,
            on_target_pdb=target_pdb_id,
            on_target_affinity=on_affinity,
            num_workers=num_workers,
            anti_targets=anti_ids,
        )

        payload = {
            "molecule_id": molecule_id,
            "on_target_pdb": result.on_target_pdb,
            "selectivity_ratio": result.selectivity_ratio,
            # Misma métrica que las otras dos rutas: ΔΔG, no el cociente.
            "selectivity_delta_delta_g": result.delta_delta_g_kcal,
            "selectivity_verdict": veredicto_de_margen(result.delta_delta_g_kcal),
            "off_targets": result.off_targets,
            "safety_flags": result.safety_flags,
            "execution_time_s": result.execution_time_s,
        }

        # Persistir en DB con sesión propia (post-hoc, no bloquea el pipeline)
        async with get_db_session() as db:
            repo = Repository(db)
            values = dict(
                selectivity_ratio=result.selectivity_ratio,
                selectivity_ran=True,
                selectivity_verdict=payload["selectivity_verdict"],
                anti_target_results=result.off_targets or [],
            )
            if task_id is not None:
                updated = await repo.update_evaluation_for_task(mol_uuid, task_id, **values)
                if not updated:
                    payload["persistence_skipped"] = "projection_belongs_to_another_run"
            else:
                await repo.set_selectivity_results(molecule_id=mol_uuid, **values)
            await flush_with_retry(db)
            await db.commit()

        return payload

    try:
        payload = asyncio.run(_run())
        print(json.dumps(payload))
        return 0
    except Exception as exc:
        print(json.dumps({"error": str(exc)[:500]}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
