"""MM-GBSA retirado: la API no debe lanzar trabajo legacy."""
import ast
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]


def awaited_names(tree):
    return {
        (n.value.func.id if isinstance(n.value.func, ast.Name) else n.value.func.attr)
        for n in ast.walk(tree)
        if isinstance(n, ast.Await) and isinstance(n.value, ast.Call)
        and isinstance(n.value.func, (ast.Name, ast.Attribute))
    }


def test_mmgbsa_endpoint_no_lanza_worker_legacy():
    tree = ast.parse((BACKEND / "api/routers/pro_features.py").read_text(encoding="utf-8"))
    endpoint = next(n for n in ast.walk(tree) if isinstance(n, ast.AsyncFunctionDef)
                    and n.name == "run_mmgbsa_endpoint")
    assert "run_mmgbsa_pose_subprocess" not in awaited_names(endpoint)
    assert "require_owned_molecule" in awaited_names(endpoint)
    assert not any(isinstance(n, ast.Name) and n.id == "compute_mmgbsa_from_pose"
                   for n in ast.walk(endpoint))
    worker = ast.parse((BACKEND / "services/docking/mmgbsa_worker.py").read_text(encoding="utf-8"))
    assert {"create_subprocess_exec", "communicate_managed"} <= awaited_names(worker)
