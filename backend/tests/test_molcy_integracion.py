"""Contrato del paquete Molcy y frontera del renderizador sin Blender."""
from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from tests.molcy_ayudas import acta_con_cierre, mp4_falso
from services.molcy.package import construir_paquete, sha256
from services.molcy import renderer


def _receptor() -> bytes:
    def atom(serial: int, residuo: int, x: float) -> str:
        return (f"ATOM  {serial:5d}  CA  ALA A{residuo:4d}    {x:8.3f}{0.:8.3f}{0.:8.3f}"
                f"  1.00  0.00    0.000 C\n")
    # El salto 1→3 y 7.6 Å impiden dibujar una cinta continua.
    return (atom(1, 1, 0.) + atom(2, 3, 7.6)).encode()


def test_paquete_conserva_pose_y_declara_hueco(tmp_path: Path) -> None:
    from rdkit import Chem
    from rdkit.Chem import AllChem

    mol = Chem.AddHs(Chem.MolFromSmiles("CCO"))
    assert AllChem.EmbedMolecule(mol, randomSeed=42) == 0
    sdf = (Chem.MolToMolBlock(mol) + "\n$$$$\n").encode()
    receptor = _receptor()
    escena = construir_paquete(
        tmp_path, receptor_pdbqt=receptor, receptor_sha256=sha256(receptor),
        pdb_id="TEST", nombre="Prueba", cadena="A", centro=(1., 2., 3.),
        tamano=(20., 20., 20.), fuente={"origen": "moldex", "task_id": "corrida"},
        poses_sdf=sdf, poses_sha256=sha256(sdf), afinidad=-4.2,
        version_vina="1.2.7", semilla=42,
    )
    contrato = json.loads((tmp_path / "docking.json").read_text(encoding="utf-8"))
    assert escena["declarado"]["huecos_de_cadena"][0]["entre_residuos"] == [1, 3]
    assert {v["id"] for v in escena["no_dibujar"]} == {"busqueda", "trayectoria_de_union"}
    assert contrato["coleccion"]["sha256"] == sha256(sdf)
    assert contrato["poses"][0]["afinidad_kcal_mol"] == -4.2
    for line in (tmp_path / "MANIFEST.sha256").read_text().splitlines():
        digest, relative = line.split("  ", 1)
        assert sha256((tmp_path / relative).read_bytes()) == digest


def test_paquete_rechaza_fuente_modificada(tmp_path: Path) -> None:
    receptor = _receptor()
    with pytest.raises(ValueError, match="SHA-256"):
        construir_paquete(tmp_path, receptor_pdbqt=receptor, receptor_sha256="0" * 64,
                         pdb_id="TEST", nombre="Prueba", cadena="A",
                         centro=(0., 0., 0.), tamano=(20., 20., 20.),
                         fuente={"origen": "receptor"})


def test_sin_blender_se_abstiene_y_no_busca_por_path(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(renderer, "_blender_candidatos", lambda: [tmp_path / "ausente.exe"])
    capacidad = renderer.detectar()
    assert capacidad["disponible"] is False
    assert "Blender" in capacidad["motivo"]


def test_producto_no_importa_blender_ni_motor() -> None:
    raiz = Path(__file__).resolve().parents[2]
    prohibidos = ("bpy", "bl_ext", "molecularnodes", "nucleo", "variables.sujeto")
    for carpeta in (raiz / "backend", raiz / "rescoring"):
        for path in carpeta.rglob("*.py"):
            if "tests" in path.parts:
                continue
            arbol = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for nodo in ast.walk(arbol):
                if isinstance(nodo, ast.Import):
                    nombres = [alias.name for alias in nodo.names]
                elif isinstance(nodo, ast.ImportFrom):
                    nombres = [nodo.module or ""]
                else:
                    continue
                assert not any(nombre == p or nombre.startswith(p + ".")
                               for nombre in nombres for p in prohibidos), path


def test_lanzador_externo_con_motor_falso(monkeypatch, tmp_path: Path) -> None:
    """El mismo adaptador lanza un proceso independiente y valida su acta."""
    # El motor falso entrega un MP4 cuya cabecera dura escena + cierre (6,6 s) y un acta que acredita el cierre: sin eso el backend no lo da por completo.
    contenido = mp4_falso(6.6)
    video_listo = tmp_path / "video_listo.mp4"
    video_listo.write_bytes(contenido)
    acta_lista = tmp_path / "acta_lista.json"
    acta_lista.write_text(json.dumps(acta_con_cierre(
        render_ajustes={"motor": "BLENDER_EEVEE"}, video={"segundos": 6.6, "sha256": hashlib.sha256(contenido).hexdigest()})), encoding="utf-8")
    fake = tmp_path / "fake_renderer.py"
    fake.write_text(
        "import pathlib,shutil,sys\n"
        "out=pathlib.Path(sys.argv[1]); out.mkdir(exist_ok=True)\n"
        "shutil.copyfile(sys.argv[4], out/sys.argv[2]); shutil.copyfile(sys.argv[5], out/sys.argv[3])\n",
        encoding="utf-8",
    )
    engine = tmp_path / "engine"
    (engine / "scripts").mkdir(parents=True)
    (engine / "scripts" / "correr_caso.ps1").write_text("# fake")
    root = tmp_path / "job"
    root.mkdir()
    job_id = "12345678-1234-1234-1234-123456789012"
    suffix = job_id.replace("-", "")[:12]
    video = f"1HSG_sitio_activo_previsualizacion_{suffix}.mp4"
    build = f"build_previsualizacion_{suffix}.json"
    calls = []
    real_run = subprocess.run

    def fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        assert Path(cmd[0]).is_absolute()
        assert Path(cmd[cmd.index("-Blender") + 1]).is_absolute()
        assert cmd[cmd.index("-Renderizador") + 1] == "gpu"
        assert cmd[cmd.index("-Python") + 1] == str(python_falso)
        assert kwargs["env"]["MOLCY_SCENES_DIR"] == str(root / "escenas")
        assert kwargs["env"]["MOLCY_BRAND_CACHE_DIR"].endswith("molcy\\cache\\cierre") or kwargs["env"]["MOLCY_BRAND_CACHE_DIR"].endswith("molcy/cache/cierre")
        return real_run([sys.executable, str(fake), str(root / "salida"), video, build, str(video_listo), str(acta_lista)],
                        check=False, capture_output=True)

    python_falso = tmp_path / "python_auxiliar" / "python.exe"  # el Python que usan el halo y el sellado (python_auxiliar.py)
    monkeypatch.setattr(renderer, "python_auxiliar", lambda: python_falso)
    monkeypatch.setattr(renderer, "run_owned", fake_run)
    estado = {"id": job_id, "estado": "en_cola", "formato": "previsualizacion",
              "sujeto": "pose_evaluada", "dispositivo": "gpu", "renderizador": {
                  "motor": str(engine), "blender": str(tmp_path / "blender.exe")}}
    renderer._ejecutar(root, estado, "1HSG")
    assert len(calls) == 1
    assert estado["estado"] == "completo"
    assert estado["video_sha256"] == hashlib.sha256(contenido).hexdigest()
