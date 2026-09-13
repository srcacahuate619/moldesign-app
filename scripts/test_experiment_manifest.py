#!/usr/bin/env python3
"""Pruebas autocontenidas para scripts/experiment_manifest.py (FND-01).

Ejecutar desde la raíz del repositorio:

    python scripts/test_experiment_manifest.py

No requiere pytest ni dependencias externas. Usa asserts, un directorio
temporal (tempfile.mkdtemp()) y reemplaza la ruta base de artefactos del
módulo para no ensuciar scripts/artifacts_science/.

Imprime "OK" al final y sale con código 0 si todas las pruebas pasan.
"""

import contextlib
import io
import json
import shutil
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import experiment_manifest as em  # noqa: E402

EXPECTED_ARTIFACTS = (
    "manifest.json",
    "metrics.json",
    "per_complex.jsonl",
    "failures.jsonl",
    "README.md",
)


def _load_json(path):
    """Carga un archivo JSON con encoding UTF-8."""
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def main():
    tmp = Path(tempfile.mkdtemp(prefix="test_experiment_manifest_"))
    try:
        # Desvía la base de artefactos a un directorio temporal.
        em.ARTIFACTS_BASE = tmp / "artifacts_science"
        em.ARTIFACTS_BASE.mkdir(parents=True)

        # --- 1. init crea los 5 artefactos ---
        rc = em.cmd_init(
            [
                "TEST-01",
                "--hypothesis", "la infraestructura de manifest funciona",
                "--protocol", "docs/49",
                "--gate", "exit 0",
            ]
        )
        assert rc == 0, "init debe salir con 0"
        exp_dir = em.ARTIFACTS_BASE / "TEST-01"
        for name in EXPECTED_ARTIFACTS:
            assert (exp_dir / name).is_file(), f"falta {name}"
        manifest = _load_json(exp_dir / "manifest.json")
        assert manifest["experiment_id"] == "TEST-01"
        assert manifest["seeds"] == 42
        assert manifest["decision"] == "PENDING"
        assert manifest["status"] == "created"
        assert manifest["git_state"]["branch"]
        assert manifest["git_state"]["commit"]
        assert isinstance(manifest["git_state"]["dirty"], bool)
        assert manifest["environment"]["gpu"]
        assert manifest["environment"]["total_ram_mb"] >= 0
        assert _load_json(exp_dir / "metrics.json") == {}
        with open(exp_dir / "per_complex.jsonl", encoding="utf-8") as fh:
            assert fh.read() == ""
        with open(exp_dir / "failures.jsonl", encoding="utf-8") as fh:
            assert fh.read() == ""

        # --- 2. validate pasa tras init ---
        rc = em.cmd_validate(["TEST-01"])
        assert rc == 0, "validate debe pasar tras init"

        readme = (exp_dir / "README.md").read_text(encoding="utf-8")
        assert "created" in readme, "el README inicial debe reflejar status=created"

        # --- 3. seal registra hashes y validate detecta modificaciones ---
        dataset_dir = tmp / "dataset"
        dataset_dir.mkdir()
        file_a = dataset_dir / "a.txt"
        file_b = dataset_dir / "b.txt"
        file_a.write_text("contenido A", encoding="utf-8")
        file_b.write_text("contenido B", encoding="utf-8")

        rc = em.cmd_seal(["TEST-01", "--dataset", str(dataset_dir)])
        assert rc == 0, "seal debe salir con 0"
        manifest = _load_json(exp_dir / "manifest.json")
        assert manifest["sealed"] is True
        assert manifest["sealed_at"]
        assert manifest["status"] == "sealed"
        hashes = manifest["dataset_hashes"]
        assert len(hashes) == 2, "el directorio sellado debe expandirse por archivo"
        for entry in hashes.values():
            assert len(entry) == 64, "sha256 debe tener 64 caracteres hex"
            assert all(char in "0123456789abcdef" for char in entry)

        # (c) README se regenera tras seal y refleja el sellado
        readme = (exp_dir / "README.md").read_text(encoding="utf-8")
        assert "sealed" in readme, "el README post-seal debe reflejar status=sealed"
        assert "Sellado: sí" in readme, "el README post-seal debe indicar el sellado"
        assert "Hashes de dataset" in readme, "el README post-seal debe listar los hashes"

        rc = em.cmd_validate(["TEST-01"])
        assert rc == 0, "validate debe pasar con los archivos intactos"

        file_b.write_text("contenido MODIFICADO", encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            rc = em.cmd_validate(["TEST-01"])
        assert rc == 1, "validate debe fallar tras modificar un archivo sellado"

        file_b.write_text("contenido B", encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            rc = em.cmd_seal(["TEST-01", "--dataset", str(dataset_dir)])
        assert rc == 1, "re-sellar un experimento sellado debe fallar (FND-05)"

        # --- 4. finish escribe la decisión ---
        rc = em.cmd_finish(
            [
                "TEST-01",
                "--decision", "GO",
                "--rationale", "prueba autocontenida",
                "--duration-seconds", "7.5",
            ]
        )
        assert rc == 0, "finish debe salir con 0"
        manifest = _load_json(exp_dir / "manifest.json")
        assert manifest["decision"] == "GO"
        assert manifest["decision_rationale"] == "prueba autocontenida"
        assert manifest["duration_seconds"] == 7.5
        assert manifest["finished_at"]
        assert manifest["status"] == "finished"

        # (c) README se regenera tras finish y refleja la decisión
        readme = (exp_dir / "README.md").read_text(encoding="utf-8")
        assert "GO" in readme, "el README post-finish debe contener la decisión"
        assert "Razón de la decisión: prueba autocontenida" in readme, (
            "el README post-finish debe incluir el rationale"
        )
        assert "Finalizado:" in readme, "el README post-finish debe incluir finished_at"

        # --- 5. init sin --force falla si el directorio ya existe ---
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            rc = em.cmd_init(
                ["TEST-01", "--hypothesis", "x", "--protocol", "y", "--gate", "z"]
            )
        assert rc == 1, "init debe fallar si el directorio ya existe"

        # --force regenera los skeletons sin tocar manifest.json
        manifest_before = (exp_dir / "manifest.json").read_bytes()
        (exp_dir / "metrics.json").write_text('{"extra": 1}\n', encoding="utf-8")
        rc = em.cmd_init(
            ["TEST-01", "--hypothesis", "x", "--protocol", "y", "--gate", "z", "--force"]
        )
        assert rc == 0, "init --force debe salir con 0"
        assert (exp_dir / "manifest.json").read_bytes() == manifest_before, (
            "--force no debe tocar manifest.json existente"
        )
        assert _load_json(exp_dir / "metrics.json") == {}, (
            "--force debe regenerar metrics.json como skeleton vacío"
        )

        # --- 6. seal con flags repetidos registra todos los buckets ---
        rc = em.cmd_init(
            [
                "TEST-02",
                "--hypothesis", "flags repetibles y assets",
                "--protocol", "docs/49",
                "--gate", "exit 0",
            ]
        )
        assert rc == 0, "init de TEST-02 debe salir con 0"
        exp2_dir = em.ARTIFACTS_BASE / "TEST-02"

        dataset_a = tmp / "ds_a"
        dataset_b = tmp / "ds_b"
        dataset_a.mkdir()
        dataset_b.mkdir()
        file_da = dataset_a / "da.txt"
        file_db = dataset_b / "db.txt"
        file_da.write_text("dataset A", encoding="utf-8")
        file_db.write_text("dataset B", encoding="utf-8")

        asset_a = tmp / "asset_a.cfg"
        asset_b = tmp / "asset_b.md"
        asset_a.write_text("asset A", encoding="utf-8")
        asset_b.write_text("asset B", encoding="utf-8")

        rc = em.cmd_seal(
            [
                "TEST-02",
                "--assets", str(asset_a), "--assets", str(asset_b),
                "--dataset", str(dataset_a), "--dataset", str(dataset_b),
            ]
        )
        assert rc == 0, "seal con flags repetidos debe salir con 0"
        manifest = _load_json(exp2_dir / "manifest.json")
        dataset_hashes = manifest["dataset_hashes"]
        assets_hashes = manifest["assets_hashes"]
        assert set(dataset_hashes) == {
            em._stored_path(str(file_da)),
            em._stored_path(str(file_db)),
        }, "todos los --dataset repetidos deben registrarse en dataset_hashes"
        assert set(assets_hashes) == {
            em._stored_path(str(asset_a)),
            em._stored_path(str(asset_b)),
        }, "todos los --assets repetidos deben registrarse en assets_hashes"
        for bucket in (dataset_hashes, assets_hashes):
            for value in bucket.values():
                assert len(value) == 64, "sha256 debe tener 64 caracteres hex"
                assert all(char in "0123456789abcdef" for char in value)

        readme = (exp2_dir / "README.md").read_text(encoding="utf-8")
        assert "sealed" in readme, "el README post-seal debe reflejar el sellado"
        assert "Hashes de assets" in readme, "el README post-seal debe listar los assets"

        rc = em.cmd_validate(["TEST-02"])
        assert rc == 0, "validate debe pasar con los archivos sellados intactos"

        # (b) validate post-seal falla si un archivo de assets cambia
        asset_b.write_text("asset B MODIFICADO", encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            rc = em.cmd_validate(["TEST-02"])
        assert rc == 1, "validate debe fallar tras modificar un asset sellado"
        asset_b.write_text("asset B", encoding="utf-8")
        rc = em.cmd_validate(["TEST-02"])
        assert rc == 0, "validate debe volver a pasar tras restaurar el asset"

        rc = em.cmd_finish(
            [
                "TEST-02",
                "--decision", "GO",
                "--rationale", "assets verificados",
            ]
        )
        assert rc == 0, "finish de TEST-02 debe salir con 0"
        readme = (exp2_dir / "README.md").read_text(encoding="utf-8")
        assert "GO" in readme, "el README post-finish debe contener la decisión"
        assert "Razón de la decisión: assets verificados" in readme, (
            "el README post-finish debe incluir el rationale"
        )

        # (d) finish con GO en experimento SIN sellar debe fallar (guard nuevo)
        exp3_dir = em.ARTIFACTS_BASE / "TEST-03"
        rc = em.cmd_init(
            [
                "TEST-03",
                "--hypothesis", "guard",
                "--protocol", "docs/49",
                "--gate", "n/a",
                "--seeds", "1",
            ]
        )
        assert rc == 0, "init de TEST-03 debe salir con 0"
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            rc = em.cmd_finish(
                ["TEST-03", "--decision", "GO", "--rationale", "sin sellar"]
            )
        assert rc == 1, "finish GO sin sello debe fallar (exit 1)"
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            rc = em.cmd_finish(
                ["TEST-03", "--decision", "NO_GO", "--rationale", "sin sellar"]
            )
        assert rc == 0, "finish NO_GO sin sello debe permitirse (experimento fallido no requiere sello)"

        # --- 7. maintain: mantenimiento auditado de assets sellados ---

        # (a) maintain sobre experimento NO sellado → exit 1
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as err_a:
            rc = em.cmd_maintain(
                [
                    "TEST-03", "--assets", str(asset_a),
                    "--reason", "deriva", "--content-commit", "abc1234",
                ]
            )
        assert rc == 1, "maintain sobre experimento no sellado debe fallar (exit 1)"
        assert "solo aplica a experimentos sellados" in err_a.getvalue(), (
            "mensaje de precondicion de sellado"
        )

        # Fixture sellado para (b)-(e)
        rc = em.cmd_init(
            [
                "TEST-04",
                "--hypothesis", "maintain auditado",
                "--protocol", "docs/49",
                "--gate", "n/a",
            ]
        )
        assert rc == 0, "init de TEST-04 debe salir con 0"
        exp4_dir = em.ARTIFACTS_BASE / "TEST-04"
        asset_m = tmp / "asset_m.txt"
        asset_m.write_text("v1", encoding="utf-8")
        rc = em.cmd_seal(["TEST-04", "--assets", str(asset_m)])
        assert rc == 0, "seal de TEST-04 debe salir con 0"

        # (b) maintain sin --reason o sin --content-commit → exit 1
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            rc = em.cmd_maintain(
                ["TEST-04", "--assets", str(asset_m), "--content-commit", "abc1234"]
            )
        assert rc == 1, "maintain sin --reason debe fallar (exit 1)"
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            rc = em.cmd_maintain(
                ["TEST-04", "--assets", str(asset_m), "--reason", "deriva"]
            )
        assert rc == 1, "maintain sin --content-commit debe fallar (exit 1)"

        # (c) maintain con --dataset → exit 1 (solo assets)
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as err_c:
            rc = em.cmd_maintain(
                [
                    "TEST-04", "--assets", str(asset_m), "--dataset", str(dataset_a),
                    "--reason", "deriva", "--content-commit", "abc1234",
                ]
            )
        assert rc == 1, "maintain con --dataset debe fallar (solo assets)"
        assert "solo mantiene assets" in err_c.getvalue(), "mensaje de restriccion de buckets"

        # (d) maintain sobre experimento sellado con UN asset cambiado → exit 0,
        #     entrada auditada, assets_hashes actualizado, validate OK, README regenerado
        stored_m = em._stored_path(str(asset_m))
        m_before = _load_json(exp4_dir / "manifest.json")
        sealed_at_before = m_before["sealed_at"]
        prev_hash = m_before["assets_hashes"][stored_m]
        asset_m.write_text("v2", encoding="utf-8")
        new_hash = em._sha256_file(str(asset_m))
        rc = em.cmd_maintain(
            [
                "TEST-04", "--assets", str(asset_m),
                "--reason", "reformulacion del documento vivo",
                "--content-commit", "deadbeef",
            ]
        )
        assert rc == 0, "maintain con asset cambiado debe salir con 0"
        m_after = _load_json(exp4_dir / "manifest.json")
        assert m_after["sealed"] is True, "el sello original se conserva"
        assert m_after["sealed_at"] == sealed_at_before, "sealed_at no se toca"
        entries = m_after["seal_maintenance"]
        assert len(entries) == 1, "una entrada de mantenimiento por asset cambiado"
        entry = entries[0]
        assert entry["path"] == stored_m
        assert entry["previous_hash"] == prev_hash, "el hash viejo se conserva"
        assert entry["new_hash"] == new_hash, "el hash nuevo es el actual"
        assert entry["reason"] == "reformulacion del documento vivo"
        assert entry["content_commit"] == "deadbeef"
        assert em.DATETIME_RE.fullmatch(entry["date"]) is not None, "date ISO 8601"
        assert m_after["assets_hashes"][stored_m] == new_hash, "assets_hashes actualizado"
        rc = em.cmd_validate(["TEST-04"])
        assert rc == 0, "validate post-maintain debe pasar"
        readme = (exp4_dir / "README.md").read_text(encoding="utf-8")
        assert "Mantenimiento del sello" in readme, (
            "el README post-maintain debe tener la subseccion de mantenimiento"
        )
        assert "reformulacion del documento vivo" in readme, (
            "el README post-maintain debe incluir el motivo"
        )
        assert stored_m in readme, "el README post-maintain debe incluir el path"
        assert "deadbeef" in readme, "el README post-maintain debe incluir el commit"

        # (e) maintain con asset SIN cambios → no-op, sin entrada nueva
        n_entries_before = len(_load_json(exp4_dir / "manifest.json")["seal_maintenance"])
        with contextlib.redirect_stdout(io.StringIO()) as out_e, contextlib.redirect_stderr(io.StringIO()):
            rc = em.cmd_maintain(
                [
                    "TEST-04", "--assets", str(asset_m),
                    "--reason", "otro motivo", "--content-commit", "beef",
                ]
            )
        assert rc == 0, "maintain con asset sin cambios debe salir con 0"
        m_e = _load_json(exp4_dir / "manifest.json")
        assert len(m_e["seal_maintenance"]) == n_entries_before, (
            "asset sin cambios → sin entrada nueva de mantenimiento"
        )
        assert "unchanged, skipped" in out_e.getvalue(), "mensaje de no-op"
        assert m_e["assets_hashes"][stored_m] == new_hash, "hash sin cambios"

        # (f) maintain NO altera dataset_hashes/model_hashes/binary_hashes
        rc = em.cmd_init(
            [
                "TEST-05",
                "--hypothesis", "inmutabilidad de buckets",
                "--protocol", "docs/49",
                "--gate", "n/a",
            ]
        )
        assert rc == 0, "init de TEST-05 debe salir con 0"
        exp5_dir = em.ARTIFACTS_BASE / "TEST-05"
        ds5 = tmp / "ds5"
        ds5.mkdir()
        file_d5 = ds5 / "d5.txt"
        file_d5.write_text("dataset 5", encoding="utf-8")
        mdl5 = tmp / "model5.pkl"
        mdl5.write_text("modelo 5", encoding="utf-8")
        bin5 = tmp / "tool5.bin"
        bin5.write_text("binario 5", encoding="utf-8")
        ast5 = tmp / "ast5.txt"
        ast5.write_text("asset 5 v1", encoding="utf-8")
        rc = em.cmd_seal(
            [
                "TEST-05", "--dataset", str(ds5), "--models", str(mdl5),
                "--binaries", str(bin5), "--assets", str(ast5),
            ]
        )
        assert rc == 0, "seal de TEST-05 debe salir con 0"
        m5_before = _load_json(exp5_dir / "manifest.json")
        datasets_before = dict(m5_before["dataset_hashes"])
        models_before = dict(m5_before["model_hashes"])
        binaries_before = dict(m5_before["binary_hashes"])
        ast5.write_text("asset 5 v2", encoding="utf-8")
        rc = em.cmd_maintain(
            ["TEST-05", "--assets", str(ast5), "--reason", "deriva", "--content-commit", "cafe"]
        )
        assert rc == 0, "maintain de TEST-05 debe salir con 0"
        m5_after = _load_json(exp5_dir / "manifest.json")
        assert m5_after["dataset_hashes"] == datasets_before, "dataset_hashes intacto"
        assert m5_after["model_hashes"] == models_before, "model_hashes intacto"
        assert m5_after["binary_hashes"] == binaries_before, "binary_hashes intacto"
        assert m5_after["sealed"] is True and m5_after["sealed_at"] == m5_before["sealed_at"], (
            "el sello original no se toca"
        )

        # (g) path de --assets que está en dataset_hashes → exit 1 y no se toca
        m5_bytes_before = (exp5_dir / "manifest.json").read_bytes()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            rc = em.cmd_maintain(
                ["TEST-05", "--assets", str(ds5), "--reason", "deriva", "--content-commit", "cafe"]
            )
        assert rc == 1, "asset que pertenece a dataset_hashes debe fallar (exit 1)"
        assert (exp5_dir / "manifest.json").read_bytes() == m5_bytes_before, (
            "manifest no se toca ante el error"
        )
        assert file_d5.read_text(encoding="utf-8") == "dataset 5", "el dataset no se toca"

        print("OK")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
