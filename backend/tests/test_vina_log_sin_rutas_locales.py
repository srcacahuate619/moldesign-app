"""El `vina.log` de una corrida no lleva rutas del equipo que la hizo.

# El defecto (2026-10-25, al grabar el vídeo de Preparación)

`logs/vina.log` viaja en el paquete de la corrida, el que se manda a quien hará el cálculo siguiente. Llevaba cuatro
rutas absolutas: las dos de nuestra cabecera (`# receptor=`, `# ligand=`) y las dos que Vina repite («Rigid
receptor:», «Ligand:»). En una instalación real son `C:\\Users\\<nombre>\\…`: el nombre del usuario salía del equipo.
Ahora el log lleva el nombre de cada archivo; `log_sha256` se calcula después, sobre estos mismos bytes.
"""
from __future__ import annotations

import pytest

from services.docking import vina_service


class _ProcesoQueTermina:
    returncode = 0


@pytest.mark.asyncio
async def test_el_log_no_lleva_las_rutas_de_la_corrida(tmp_path, monkeypatch):
    receptor = tmp_path / "vina-077c4c69-8T69" / "receptor_snapshot.pdbqt"
    ligando = tmp_path / "tmpukz57c54.pdbqt"
    eco = (
        "AutoDock Vina v1.2.7\n"
        f"Rigid receptor: {receptor}\n"
        f"Ligand: {ligando}\n"
        f"Output: {str(tmp_path / 'poses.pdbqt').replace(chr(92), '/')}\n"
        "mode |   affinity\n   1       -10.26\n"
    )
    # control: el eco simulado sí trae las rutas, así que una prueba verde no es una prueba vacía
    assert str(tmp_path) in eco

    async def lanzar(*_args, **_kwargs):
        return _ProcesoQueTermina()

    async def comunicar(_proceso, timeout):
        return eco.encode(), f"WARNING: {ligando}\n".encode()

    monkeypatch.setattr(vina_service, "_resolve_executable", lambda _ruta: str(tmp_path / "vina.exe"))
    monkeypatch.setattr(vina_service.asyncio, "create_subprocess_exec", lanzar)
    monkeypatch.setattr(vina_service, "communicate_managed", comunicar)
    salida = await vina_service._run_vina_subprocess(
        receptor_path=receptor, ligand_path=ligando,
        output_path=tmp_path / "poses.pdbqt", log_path=tmp_path / "vina.log",
        target_pdb_id="8T69", center=(0.0, 0.0, 0.0), size=(30.0, 30.0, 30.0),
        molecule_id="3e0a5eff", exhaustiveness=8, num_poses=9, seed=42,
    )
    log = (tmp_path / "vina.log").read_text(encoding="utf-8")
    assert str(tmp_path) not in log
    assert str(tmp_path).replace("\\", "/") not in log
    assert "# receptor=receptor_snapshot.pdbqt" in log and "# ligand=tmpukz57c54.pdbqt" in log
    assert "Rigid receptor: receptor_snapshot.pdbqt" in log and "Ligand: tmpukz57c54.pdbqt" in log
    assert "Output: poses.pdbqt" in log and "WARNING: tmpukz57c54.pdbqt" in log
    # lo demás del log no cambia, y lo que se devuelve para leer las afinidades es el eco de Vina tal cual
    assert "-10.26" in log and "# exhaustiveness=8" in log and "# num_modes=9" in log
    assert salida == eco


def test_sin_rutas_locales_sólo_toca_las_rutas_pedidas():
    rutas = (r"C:\Users\Ana\AppData\Local\Temp\vina\receptor.pdbqt",)
    texto = (
        "Rigid receptor: C:\\Users\\Ana\\AppData\\Local\\Temp\\vina\\receptor.pdbqt\n"
        "Rigid receptor: C:/Users/Ana/AppData/Local/Temp/vina/receptor.pdbqt\n"
        "Grid center: X 127.862 Y 123.474 Z 104.225\n"
    )
    limpio = vina_service._sin_rutas_locales(texto, rutas)
    assert "Ana" not in limpio and limpio.count("Rigid receptor: receptor.pdbqt") == 2
    assert "Grid center: X 127.862 Y 123.474 Z 104.225" in limpio
    assert vina_service._sin_rutas_locales("sin rutas", rutas) == "sin rutas"
