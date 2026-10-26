"""La suite no escribe en la carpeta de datos REAL de la aplicación (`~/MolDesign`).

Hasta el 2026-10-05 sólo la base de datos estaba protegida (`MOLDESIGN_TESTING`): los conformeros de los ligandos y el log se escribían en
`~/MolDesign/data/ligands/` y `~/MolDesign/logs/` en cada ejecución de la suite, sobre ficheros de quien tuviera la aplicación instalada.
"""
from pathlib import Path

from core.config import get_settings
from utils.local_storage import data_dir


def _bajo(ruta: Path, carpeta: Path) -> bool:
    return ruta.resolve().is_relative_to(carpeta.resolve())


def test_el_directorio_de_datos_de_las_pruebas_no_es_el_del_usuario():
    real = Path.home() / "MolDesign"
    assert not _bajo(Path(get_settings().local_data_dir), real)
    assert not _bajo(data_dir(), real)


def test_el_log_de_las_pruebas_no_cae_junto_a_los_datos_del_usuario():
    real = Path.home() / "MolDesign"
    assert not _bajo(Path(get_settings().local_data_dir).parent / "logs", real)
