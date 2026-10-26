"""El spike de NVIDIA (`scripts/spike_nvidia_nim.py`, Fase 0 de `docs/97`) maneja una clave de terceros.

No es producto, pero la clave es del propietario y es temporal: lo único que importa es que no llegue a ningún
sitio donde se pueda quedar. Estas pruebas fijan las tres rutas de fuga que importan:

1. **lo que se escribe a disco o se imprime** pasa por `redactar`, también cuando el servidor devuelve la clave
   dentro de un mensaje de error;
2. **un archivo de clave dentro del repositorio se rechaza**, porque el siguiente `git add` lo subiría;
3. **el código no lleva ninguna clave**: la guarda de `check_push_publico.py` rechaza `nvapi-` + 20 caracteres.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "spike_nvidia_nim.py"

#: Una clave FALSA con la forma de las reales, construida aquí para que ningún literal la delate.
CLAVE_FALSA = "nvapi-" + "Ab" * 20


@pytest.fixture(scope="module")
def spike():
    especificacion = importlib.util.spec_from_file_location("spike_nvidia_nim", SCRIPT)
    modulo = importlib.util.module_from_spec(especificacion)
    especificacion.loader.exec_module(modulo)
    return modulo


def test_redactar_oculta_la_clave_dada_y_cualquier_otra_con_su_forma(spike):
    texto = f"401: la clave {CLAVE_FALSA} no es válida; probé también nvapi-{'Zz' * 15}"
    limpio = spike.redactar(texto, CLAVE_FALSA)
    assert CLAVE_FALSA not in limpio
    assert "nvapi-Zz" not in limpio
    assert limpio.count("nvapi-***") == 2


def test_redactar_tambien_limpia_estructuras_y_no_las_rompe(spike):
    obs = {"error": f"Bearer {CLAVE_FALSA}", "segundos": 1.5}
    limpio = spike.redactar(obs, CLAVE_FALSA)
    assert CLAVE_FALSA not in limpio
    assert "segundos" in limpio


def test_un_archivo_de_clave_dentro_del_repositorio_se_rechaza(spike, tmp_path, monkeypatch):
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    monkeypatch.setattr(spike, "RAIZ", tmp_path)
    dentro = tmp_path / "nvidia.key"
    dentro.write_text(CLAVE_FALSA, encoding="utf-8")
    with pytest.raises(SystemExit) as salida:
        spike.leer_clave(dentro)
    assert "repositorio" in str(salida.value)
    assert CLAVE_FALSA not in str(salida.value)


def test_un_archivo_fuera_del_repositorio_se_lee(spike, tmp_path, monkeypatch):
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    monkeypatch.setattr(spike, "RAIZ", tmp_path / "repo")
    fuera = tmp_path / "secretos" / "nvidia.key"
    fuera.parent.mkdir()
    fuera.write_text(CLAVE_FALSA + "\n", encoding="utf-8")
    assert spike.leer_clave(fuera) == CLAVE_FALSA


def test_sin_clave_se_niega_y_no_la_inventa(spike, tmp_path, monkeypatch):
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    with pytest.raises(SystemExit):
        spike.leer_clave(tmp_path / "no-existe.key")


def test_las_cargas_publicas_tienen_la_forma_que_se_va_a_enviar(spike):
    boltz = spike.carga_boltz2()
    assert boltz["polymers"][0]["molecule_type"] == "protein"
    assert boltz["ligands"][0]["predict_affinity"] is True
    assert boltz["output_format"] == "mmcif"
    rdkit = pytest.importorskip("rdkit")
    from rdkit import Chem

    molecula = Chem.MolFromSmiles(spike.INDINAVIR)
    assert molecula is not None
    # Indinavir es C36H47N5O4: 45 átomos pesados. Si cambia, el SMILES ya no es el del fármaco.
    assert molecula.GetNumHeavyAtoms() == 45
    assert rdkit is not None


def test_la_carga_minima_no_lleva_ligando_ni_afinidad(spike):
    minima = spike.carga_boltz2(minima=True)
    assert list(minima) == ["polymers"]
    assert minima["polymers"][0]["sequence"] == spike.SECUENCIA_MINIMA


def test_el_script_no_lleva_ninguna_clave_dentro(spike):
    fuente = SCRIPT.read_text(encoding="utf-8")
    assert not re.search(r"nvapi-[A-Za-z0-9_-]{20,}", fuente)
