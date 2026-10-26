"""`vina_trace.exe` tiene que leer un ligando igual que `vina.exe`.

# El fallo que vigila (1HSG + indinavir, 2026-10-10)

La evaluación de 1HSG con indinavir terminaba en «Vina exit code: 1». El
pipeline sustituye `vina.exe` por `vina_trace.exe` (la traza que usa Molcy), y
la traza rechazaba un PDBQT que `vina.exe` acoplaba:

    PDBQT parsing error: Unknown or inappropriate tag found in flex residue or ligand.
     > ENDBRANCH  39  41

El parser no tenía nada que ver: es el de upstream, y leía las 89 líneas sin
error. El fallo estaba en `get_file_contents` (`src/lib/utils.cpp`): reserva
`tellg()` bytes y los lee en modo texto. Meeko escribe el PDBQT con CRLF en
Windows, el modo texto convierte cada CRLF en LF y `read()` devuelve tantos
caracteres menos como líneas tiene el archivo. En el `vina.exe` de referencia
ese resto queda en `'\\0'`, que el parser ignora a propósito. En la compilación
MinGW de la traza, desde 4096 bytes, el resto conserva bytes viejos del propio
archivo, y el parser los leía como una línea más: `ENDBRANCH  39  41`, repetida
detrás de `TORSDOF 14`.

Así que no fallaba «una rama profunda»: fallaba **todo ligando de 4096 bytes o
más**. Medido con ligandos preparados como el producto: 51 de 345 de una muestra
de PDBbind (14,8 %), además de indinavir, Leu-encefalina, ciclo(RGDfV) y los
inhibidores de proteasa 2BQV, 1HVR y 1OHR. Detalle en
`docs/TRAZA_BUSQUEDA_MOLCY.md`.

# Qué se comprueba

Que el ligando de la prueba sigue disparando la condición (CRLF y ≥ 4096
bytes: si alguien lo normaliza, la prueba lo dice en vez de pasar sin ver), que
la traza lo lee y le calcula la misma energía que `vina.exe`, y que una corrida
por `_run_vina_subprocess` —el camino del producto, con traza— termina.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess

import pytest

from services.docking import search_trace, vina_service

ROOT = Path(__file__).resolve().parents[2]
#: El PDBQT que preparó el pipeline para la corrida de 1HSG, byte a byte
#: (`pdbqt_sha256` de su `vina_input.source.json`).
LIGANDO = ROOT / "backend/tests/fixtures/vina_trace/indinavir_1hsg_crlf.pdbqt"
SHA_DEL_PIPELINE = "af30b5bab7c896c6c7e0ce5394d0cea1160cd4a99d26b5839310aa0864bba2c5"
RECEPTOR = b"ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00  0.00     0.000 C\n"
SIN_VENTANA = 0x08000000 if os.name == "nt" else 0


def test_el_ligando_de_la_prueba_sigue_disparando_el_fallo():
    """Sin CRLF o por debajo de 4096 bytes, la traza vieja también lo leía."""
    datos = LIGANDO.read_bytes()
    assert search_trace.sha(datos) == SHA_DEL_PIPELINE, (
        "El ligando de la prueba ya no es el que escribió el pipeline. Si git lo "
        "normalizó (LF), la prueba dejaría de ver el fallo: `*.pdbqt` debe seguir "
        "siendo `-text` en .gitattributes."
    )
    lineas = datos.count(b"\n")
    assert datos.count(b"\r\n") == lineas == 89
    assert len(datos) >= 4096


@pytest.fixture(scope="module")
def binarios():
    referencia = ROOT / "tools/vina/vina.exe"
    if not referencia.is_file():
        pytest.skip("Vina no está instalado en este árbol (los binarios no se versionan)")
    traza, identidad = search_trace.instrumented(str(referencia))
    if identidad is None:
        pytest.skip("No hay Vina instrumentado junto a esta referencia")
    return referencia, Path(traza)


def _puntuar(binario: Path, carpeta: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(binario), "--receptor", str(carpeta / "receptor.pdbqt"),
         "--ligand", str(LIGANDO), "--score_only", "--autobox"],
        capture_output=True, text=True, timeout=120, creationflags=SIN_VENTANA,
    )


def _energias(stdout: str) -> list[str]:
    """Las líneas de energía de `--score_only`: sin búsqueda ni semilla."""
    return re.findall(r"^\s*(?:Estimated Free Energy|Final Intermolecular|\(1\)|\(2\)|\(3\)|"
                      r"Intramolecular|Torsional|Unbound)[^\n]*", stdout, re.M)


def test_la_traza_lee_el_ligando_como_la_referencia(binarios, tmp_path):
    referencia, traza = binarios
    (tmp_path / "receptor.pdbqt").write_bytes(RECEPTOR)
    esperado = _puntuar(referencia, tmp_path)
    obtenido = _puntuar(traza, tmp_path)
    assert esperado.returncode == 0, esperado.stderr
    assert obtenido.returncode == 0, (
        "vina_trace.exe rechaza un PDBQT que vina.exe lee. Antes del arreglo: "
        "«Unknown or inappropriate tag … > ENDBRANCH  39  41».\n" + obtenido.stderr
    )
    energias = _energias(esperado.stdout)
    assert energias, esperado.stdout
    assert _energias(obtenido.stdout) == energias


@pytest.mark.asyncio
async def test_una_corrida_con_traza_acopla_el_ligando(binarios, tmp_path, monkeypatch):
    """El camino del producto: `_run_vina_subprocess` elige la traza y termina."""
    referencia, _ = binarios
    monkeypatch.setattr(vina_service.settings, "vina_executable_path", str(referencia))
    monkeypatch.setattr(vina_service.settings, "vina_cpu", 1)
    (tmp_path / "receptor.pdbqt").write_bytes(RECEPTOR)
    salida = tmp_path / "poses.pdbqt"
    stdout = await vina_service._run_vina_subprocess(
        receptor_path=tmp_path / "receptor.pdbqt", ligand_path=LIGANDO,
        output_path=salida, log_path=tmp_path / "vina.log", target_pdb_id="1HSG",
        center=(-1.5, -1.0, 0.0), size=(25.0, 25.0, 25.0), molecule_id="indinavir",
        exhaustiveness=1, num_poses=1, seed=42,
    )
    assert "v1.2.7-trace" in stdout, "La corrida no usó el binario instrumentado"
    assert "REMARK VINA RESULT" in salida.read_text(errors="replace")
    assert (tmp_path / "search_task_0.csv").is_file(), "La corrida no dejó traza"
