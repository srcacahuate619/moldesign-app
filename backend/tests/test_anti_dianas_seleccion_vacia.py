"""Ninguna significa cero receptores; None conserva el defecto histórico."""
import ast
from pathlib import Path
import pytest
from services.docking.selectivity import ANTI_TARGET_PANEL, seleccionar_anti_dianas

@pytest.mark.asyncio
async def test_ninguna_no_reactiva_el_panel_por_defecto():
    assert await seleccionar_anti_dianas([]) == ([], [])

@pytest.mark.asyncio
async def test_omitir_la_seleccion_conserva_el_panel_por_defecto():
    assert await seleccionar_anti_dianas(None) == (list(ANTI_TARGET_PANEL), [])

def test_el_subproceso_no_convierte_la_seleccion_vacia_en_none():
    source = Path(__file__).parents[1] / "services/docking/selectivity_subprocess.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    assignment = next(n for n in ast.walk(tree) if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "anti_ids" for t in n.targets))
    namespace = {"anti_targets_csv": ""}
    exec(compile(ast.Module(body=[assignment], type_ignores=[]), str(source), "exec"), namespace)
    assert namespace["anti_ids"] == []
