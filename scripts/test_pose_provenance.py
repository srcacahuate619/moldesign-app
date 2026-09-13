# -*- coding: utf-8 -*-
"""
test_pose_provenance.py — Pruebas del contrato de provenance de poses (FND-06).

Solo stdlib; fixtures sintéticos en tempdir. Ejecutar:

    python scripts/test_pose_provenance.py

Imprime "OK  <prueba>" por cada prueba que pasa y un resumen final. Exit 0 si
todas pasan; exit 1 y detalle del fallo en caso contrario.

Cubre el cierre de garantía futura (FND-06):
  (a) sidecar válido pasa
  (b) clave duplicada en el sidecar falla
  (c) clave incoherente con pid/source/file_stem falla
  (d) created_at no ISO 8601 falla
  (e) pose sin registro en el sidecar falla (modo estricto)
  (f) lote histórico con unknowns: pasa en modo histórico, falla con
      --strict-unknown
  (g) determinismo del backfill: 2 corridas, mismo sha256
  (h) registro canónico futuro (seed_conformer/seed_docking) válido
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import pose_provenance as pp  # noqa: E402
import backfill_pose_provenance as bf  # noqa: E402

PRUEBAS = []


def prueba(func):
    PRUEBAS.append(func)
    return func


def _registro(pid, fuente, stem, seed=None, seed_conformer=None,
              seed_docking=None, conformer_id=0, created_at="unknown"):
    kwargs = dict(
        pid=pid, source=fuente, file_stem=stem,
        conformer_id=conformer_id, exhaustiveness=8, num_modes=9,
        box={"center": [1.0, 2.0, 3.0], "size": [25.0, 25.0, 25.0],
             "method": "center_from_crystal_ligand"},
        preparation={"ligand": {"method": "m", "tool": "t"},
                     "receptor": {"protonation": "p", "tool": "t"}},
        engine={"name": "vina", "version": "1.2.7"},
        experiment_id="sintetico", created_at=created_at,
    )
    if seed_conformer is not None or seed_docking is not None:
        kwargs.update(seed_conformer=seed_conformer, seed_docking=seed_docking)
    else:
        kwargs.update(seed=seed)
    return pp.construir_registro(**kwargs)


def _poses(*trios):
    return [{"pid": p, "source": s, "file_stem": f} for p, s, f in trios]


def _checker(*poses_sidecar_args):
    """Corre el CLI --check y devuelve (returncode, stderr)."""
    r = subprocess.run(
        [sys.executable, str(SCRIPT_DIR / "pose_provenance.py"), "--check",
         "--provenance", "sidecar"] + [str(a) for a in poses_sidecar_args],
        capture_output=True, text=True)
    return r.returncode, r.stderr


@prueba
def test_sidecar_valido_pasa():
    poses = _poses(("1a4w", "molflex", "conf0.out"),
                   ("1a4w", "molflex", "conf1.out"))
    regs = {r["key"]: r for r in [
        _registro("1a4w", "molflex", "conf0.out", seed=42, conformer_id=0,
                  created_at="2026-08-15T18:30:00+02:00"),
        _registro("1a4w", "molflex", "conf1.out", seed=42, conformer_id=1,
                  created_at="2026-08-15T18:30:00+02:00")]}
    rep = pp.validar_lote(poses, regs)
    assert rep["n_sin_provenance"] == 0, rep
    assert rep["n_registros_invalidos"] == 0, rep
    assert rep["n_incoherencias"] == 0, rep
    assert rep["claves_sin_provenance"] == [], rep
    assert pp._exito(rep, strict_unknown=False) == 0
    assert pp._exito(rep, strict_unknown=True) == 0


@prueba
def test_clave_duplicada_falla():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        r = _registro("1a4w", "molflex", "conf0.out", seed=42)
        sidecar = td / "poses_provenance.jsonl"
        sidecar.write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for _ in range(2))
            + "\n", encoding="utf-8")
        try:
            pp.cargar_provenance_sidecar(sidecar)
            raise AssertionError("esperaba ValueError por clave duplicada")
        except ValueError as exc:
            assert "duplicada" in str(exc), exc
        poses = td / "poses.jsonl"
        poses.write_text(json.dumps(
            {"pid": "1a4w", "source": "molflex", "file_stem": "conf0.out"})
            + "\n", encoding="utf-8")
        rc, err = _checker("--sidecar", sidecar, poses)
        assert rc == 1, err
        assert "duplicada" in err, err


@prueba
def test_clave_incoherente_falla():
    r = _registro("1a4w", "molflex", "conf0.out", seed=42)
    r["key"] = "1a4w|molflex|conf9.out"
    errores = pp.validar_registro(r)
    assert any(e.startswith("key_incoherente") for e in errores), errores
    rep = pp.validar_lote(_poses(("1a4w", "molflex", "conf0.out")),
                          {r["key"]: r})
    assert rep["n_incoherencias"] >= 1, rep
    assert any("key_incoherente" in inc["detalle"][0]
               for inc in rep["incoherencias"]), rep
    assert pp._exito(rep, strict_unknown=False) == 1


@prueba
def test_created_at_invalido_falla():
    r = _registro("1a4w", "molflex", "conf0.out", seed=42,
                  created_at="2026-02-30T99:99:99")
    errores = pp.validar_registro(r)
    assert any(e.startswith("created_at_no_iso8601") for e in errores), errores
    r2 = _registro("1a4w", "molflex", "conf0.out", seed=42,
                   created_at="2026-08-15T18:30:00+02:00")
    assert pp.validar_registro(r2) == [], pp.validar_registro(r2)


@prueba
def test_pose_sin_registro_falla():
    poses = _poses(("1a4w", "molflex", "conf0.out"),
                   ("1a4w", "molflex", "conf9.out"))
    r = _registro("1a4w", "molflex", "conf0.out", seed=42)
    rep = pp.validar_lote(poses, {r["key"]: r})
    assert rep["n_sin_provenance"] == 1, rep
    assert "1a4w|molflex|conf9.out" in rep["claves_sin_provenance"], rep
    assert pp._exito(rep, strict_unknown=False) == 1
    assert pp._exito(rep, strict_unknown=True) == 1


@prueba
def test_historico_unknowns_pasa_y_strict_falla():
    r = _registro("1a4w", "flexible_redock", "1a4w", seed="unknown",
                  conformer_id="crystal")
    rep = pp.validar_lote(_poses(("1a4w", "flexible_redock", "1a4w")),
                          {r["key"]: r})
    assert rep["campos"]["seed"]["unknown"] >= 1, rep
    assert pp._exito(rep, strict_unknown=False) == 0
    assert pp._exito(rep, strict_unknown=True) == 1


@prueba
def test_determinismo_backfill():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        out1, out2 = td / "a.jsonl", td / "b.jsonl"
        rep1, rep2 = td / "ra.json", td / "rb.json"
        rc1 = bf.main(["--out", str(out1), "--report-out", str(rep1)])
        rc2 = bf.main(["--out", str(out2), "--report-out", str(rep2)])
        assert rc1 == 0 and rc2 == 0
        h1 = hashlib.sha256(out1.read_bytes()).hexdigest()
        h2 = hashlib.sha256(out2.read_bytes()).hexdigest()
        assert h1 == h2, (h1, h2)
        assert out1.read_text(encoding="utf-8") == \
            out2.read_text(encoding="utf-8")


@prueba
def test_registro_canonico_futuro_valido():
    r = _registro("1a4w", "molflex", "conf0.out",
                  seed_conformer=42, seed_docking=42, conformer_id=0,
                  created_at="2026-08-15T18:30:00+02:00")
    assert "seed" not in r, r
    assert pp.validar_registro(r) == [], pp.validar_registro(r)
    assert pp.clasificar_campo(r, "seed") == "conocido"
    r2 = _registro("1a4w", "ruta_a", "exh1", seed_conformer="crystal",
                   seed_docking=42, conformer_id="crystal",
                   created_at="2026-08-15T18:30:00+02:00")
    assert pp.validar_registro(r2) == [], pp.validar_registro(r2)
    assert pp.clasificar_campo(r2, "seed") == "conocido"


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    fallos = []
    for f in PRUEBAS:
        try:
            f()
            print(f"OK  {f.__name__}")
        except Exception as exc:
            fallos.append(f.__name__)
            print(f"FAIL {f.__name__}: {type(exc).__name__}: {exc}")
    print(f"OK: {len(PRUEBAS) - len(fallos)} de {len(PRUEBAS)} pruebas")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
