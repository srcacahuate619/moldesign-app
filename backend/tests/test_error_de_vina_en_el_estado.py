"""Cuando Vina falla, el estado de la tarea tiene que decir lo que dijo Vina.

# El fallo que vigila (1HSG, 2026-10-10)

La evaluación de 1HSG con indinavir terminó en

    DockingFailed: Docking falló para molécula 'tmpre11suvw' contra target '1HSG' (Vina exit code: 1)

Vina sí había dicho la causa —«PDBQT parsing error: Unknown or inappropriate
tag … > ENDBRANCH  39  41»—, pero sólo llegaba a `detail` y al `vina.log` de la
corrida. El estado de la tarea guarda `str(exc)`, y ahí no estaba. La molécula,
además, se nombraba por el temporal (`tmpre11suvw`), que no identifica nada.
"""
from __future__ import annotations

import pytest

from core.exceptions import DockingFailed
from services.docking import vina_service

ERROR_DE_PARSEO = (
    "\n\nPDBQT parsing error: Unknown or inappropriate tag found in flex residue or ligand.\n"
    " > ENDBRANCH  39  41\n"
)


def test_el_mensaje_cita_la_causa_y_no_los_avisos():
    stderr = "WARNING: At low exhaustiveness, it may be impossible to utilize all CPUs.\n" + ERROR_DE_PARSEO
    assert vina_service._mensaje_de_vina(stderr) == (
        "PDBQT parsing error: Unknown or inappropriate tag found in flex residue or ligand. "
        "> ENDBRANCH  39  41"
    )


def test_sin_stderr_no_se_inventa_una_causa():
    assert vina_service._mensaje_de_vina("") is None
    assert vina_service._mensaje_de_vina("WARNING: algo\n\n") is None


def test_un_stderr_enorme_se_recorta():
    texto = vina_service._mensaje_de_vina("x" * 5000)
    assert len(texto) == 400 and texto.endswith("…")


def test_sin_mensaje_el_texto_de_la_excepcion_no_cambia():
    exc = DockingFailed(molecule_id="m", target_pdb_id="1HSG", vina_exit_code=1)
    assert str(exc) == "Docking falló para molécula 'm' contra target '1HSG' (Vina exit code: 1)"


class _ProcesoQueFalla:
    returncode = 1


@pytest.mark.asyncio
async def test_el_estado_de_la_tarea_lleva_el_error_de_vina(tmp_path, monkeypatch):
    """`str(exc)` es lo que guarda el estado: ahí tiene que estar la causa."""
    async def lanzar(*_args, **_kwargs):
        return _ProcesoQueFalla()

    async def comunicar(_proceso, timeout):
        return b"AutoDock Vina v1.2.7\n", ERROR_DE_PARSEO.encode()

    monkeypatch.setattr(vina_service, "_resolve_executable", lambda _ruta: str(tmp_path / "vina.exe"))
    monkeypatch.setattr(vina_service.asyncio, "create_subprocess_exec", lanzar)
    monkeypatch.setattr(vina_service, "communicate_managed", comunicar)
    ligando = tmp_path / "tmpre11suvw.pdbqt"
    with pytest.raises(DockingFailed) as error:
        await vina_service._run_vina_subprocess(
            receptor_path=tmp_path / "receptor.pdbqt", ligand_path=ligando,
            output_path=tmp_path / "poses.pdbqt", log_path=tmp_path / "vina.log",
            target_pdb_id="1HSG", center=(0.0, 0.0, 0.0), size=(25.0, 25.0, 25.0),
            molecule_id="fc41d9d8", exhaustiveness=8, num_poses=9, seed=42,
        )
    mensaje = str(error.value)
    assert "Vina exit code: 1" in mensaje
    assert "PDBQT parsing error" in mensaje and "ENDBRANCH  39  41" in mensaje
    assert "'fc41d9d8'" in mensaje and "tmpre11suvw" not in mensaje
    # El stderr completo sigue en `detail` y en el log de la corrida.
    assert "ENDBRANCH  39  41" in error.value.detail
    assert "ENDBRANCH  39  41" in (tmp_path / "vina.log").read_text(encoding="utf-8")
