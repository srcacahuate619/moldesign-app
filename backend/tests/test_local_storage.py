"""
Tests de regresión para el hallazgo de auditoría F-03.

F-03: utils/file_handlers.py era la abstracción activa de archivos en desktop
(disco local) y ahora expone exclusivamente operaciones de filesystem
ensure_bucket_exists, presigned URLs, upload/download/object_*). La deuda es
conceptual: el storage real en desktop es el filesystem bajo
settings.local_data_dir.

Estos tests prueban la nueva abstracción utils/local_storage.py:
- write_text persiste bajo local_data_dir con el prefijo lógico correcto.
- read_text hace round-trip del contenido.
- exists() distingue presencia/ausencia.
- delete() elimina el objeto.
- Los símbolos de storage que usa el flujo de preparación (preparer.py)
  resuelven a local_storage.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import utils.local_storage as ls
from core.exceptions import LocalFileNotFound
from utils.file_handlers import StoragePath


@pytest.fixture(autouse=True)
def _isolated_data_dir(monkeypatch, tmp_path):
    """Apunta local_data_dir y vina_temp_dir a un directorio temporal."""
    monkeypatch.setattr(ls.settings, "local_data_dir", str(tmp_path / "data"))
    monkeypatch.setattr(ls.settings, "vina_temp_dir", str(tmp_path / "vina"))
    Path(ls.settings.vina_temp_dir).mkdir(parents=True, exist_ok=True)


class TestLocalStorageWriteText:
    @pytest.mark.asyncio
    async def test_write_text_persists_under_local_data_dir_with_logical_prefix(self):
        """write_text escribe en local_data_dir respetando el prefijo lógico targets/."""
        object_name = StoragePath.target_raw("7E2Y")
        result = await ls.write_text(object_name, "ATOM  1 ...")

        assert result == object_name
        expected = Path(ls.settings.local_data_dir) / "targets" / "7E2Y" / "raw.pdb"
        assert expected.is_file()
        assert expected.read_text(encoding="utf-8") == "ATOM  1 ..."

    @pytest.mark.asyncio
    async def test_write_text_keeps_ligands_and_poses_prefixes(self):
        """Los prefijos lógicos ligands/ y poses/ no cambian (contrato de datos)."""
        ligand = StoragePath.ligand_conformer("abc123")
        poses = StoragePath.docking_poses("abc123", "7E2Y")

        await ls.write_text(ligand, "SDF")
        await ls.write_text(poses, "POSES")

        data_dir = Path(ls.settings.local_data_dir)
        assert (data_dir / "ligands" / "abc123" / "conformer.sdf").is_file()
        assert (data_dir / "poses" / "abc123" / "7E2Y" / "poses.sdf").is_file()


class TestLocalStorageReadText:
    @pytest.mark.asyncio
    async def test_read_text_round_trip(self):
        """write_text → read_text devuelve el mismo contenido."""
        object_name = StoragePath.ligand_conformer("hash123")
        content = "mol block\n$$$$\n"
        await ls.write_text(object_name, content)

        assert await ls.read_text(object_name) == content

    @pytest.mark.asyncio
    async def test_read_text_missing_raises_file_not_found(self):
        """read_text sobre una ruta inexistente lanza LocalFileNotFound."""
        with pytest.raises(LocalFileNotFound):
            await ls.read_text(StoragePath.target_raw("NOPE"))


class TestLocalStorageExists:
    @pytest.mark.asyncio
    async def test_exists_true_after_write(self):
        object_name = StoragePath.target_prepared("7E2Y")
        assert await ls.exists(object_name) is False

        await ls.write_text(object_name, "REMARK ...")
        assert await ls.exists(object_name) is True

    @pytest.mark.asyncio
    async def test_exists_false_for_absent_object(self):
        assert await ls.exists(StoragePath.docking_poses("nada", "NOPE")) is False


class TestLocalStorageDelete:
    @pytest.mark.asyncio
    async def test_delete_removes_object(self):
        object_name = StoragePath.ligand_conformer("borrar123")
        await ls.write_text(object_name, "tmp")

        assert await ls.delete(object_name) is True
        assert await ls.exists(object_name) is False

    @pytest.mark.asyncio
    async def test_delete_missing_object_is_not_an_error(self):
        """delete es idempotente: eliminar algo que no existe retorna True."""
        assert await ls.delete(StoragePath.ligand_conformer("nunca_existió")) is True


class TestLocalStorageBytes:
    @pytest.mark.asyncio
    async def test_write_bytes_read_bytes_round_trip(self):
        object_name = StoragePath.target_raw("7E2Y")
        payload = b"ATOM\x00binary"

        await ls.write_bytes(payload, object_name)
        assert await ls.read_bytes(object_name) == payload


class TestLocalStorageWriteFile:
    @pytest.mark.asyncio
    async def test_write_file_copies_local_file(self, tmp_path):
        source = tmp_path / "vina_out.sdf"
        source.write_bytes(b"poses sdf")

        object_name = StoragePath.docking_poses("h", "7E2Y")
        result = await ls.write_file(source, object_name)

        assert result == object_name
        assert ls.path_for(object_name).read_bytes() == b"poses sdf"

    @pytest.mark.asyncio
    async def test_write_file_missing_source_raises(self):
        with pytest.raises(FileNotFoundError):
            await ls.write_file(Path("no/existe.sdf"), StoragePath.docking_poses("h", "7E2Y"))


class TestLocalStorageTempFile:
    @pytest.mark.asyncio
    async def test_temp_file_materializes_and_cleans_up(self):
        object_name = StoragePath.target_prepared("7E2Y")
        await ls.write_text(object_name, "RECEPTOR")

        async with ls.temp_file(object_name, suffix=".pdbqt") as tmp_path_file:
            assert tmp_path_file.is_file()
            assert tmp_path_file.read_text(encoding="utf-8") == "RECEPTOR"

        # Al salir del bloque el archivo temporal se elimina.
        assert not tmp_path_file.exists()


class TestPreparerStorageSymbolsResolve:
    """El flujo de preparación (preparer.py) usa la nueva interfaz local."""

    def test_preparer_imports_resolve_to_local_storage(self):
        import services.docking.preparer as prep

        assert prep.exists is ls.exists
        assert prep.read_text is ls.read_text
        assert prep.write_text is ls.write_text
        assert prep.write_file is ls.write_file

    @pytest.mark.asyncio
    async def test_preparer_storage_round_trip_on_local_disk(self):
        import services.docking.preparer as prep

        raw_path = StoragePath.target_raw("7E2Y")
        await prep.write_text(raw_path, "ATOM  1 ...")

        assert await prep.exists(raw_path) is True
        assert await prep.read_text(raw_path) == "ATOM  1 ..."

        expected = Path(ls.settings.local_data_dir) / "targets" / "7E2Y" / "raw.pdb"
        assert expected.is_file()
