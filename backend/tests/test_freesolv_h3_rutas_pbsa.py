"""pbsa no puede recibir una ruta que su Fortran vaya a cortar.

La primera medida de MMGBSA-H3-FREESOLV-RADIOS (2026-09-23) perdió las 37
moléculas con Br o I, que son todo el gate: pbsa corta cada nombre de archivo a
80 caracteres, y la ruta absoluta del prmtop del brazo B
(`/work/resultados/MMGBSA-H3-FREESOLV-RADIOS/trabajo/mobley_1107178/brazo_B/ligand.prmtop`)
medía 81 o más. El log decía `Unit 8 Error on OPEN: .../brazo_B/ligand`.

Estas pruebas no necesitan AmberTools: sustituyen el subproceso y miran qué
argumentos recibe.
"""
from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from audits import freesolv_h3


def _falso_pbsa(llamadas):
    def run(orden, cwd, **_):
        llamadas.append((orden, Path(cwd)))
        (Path(cwd) / "pb.out").write_text(" EPB    =        -7.1234\n")
        return SimpleNamespace(returncode=0, stderr="")
    return run


def test_pbsa_recibe_rutas_cortas_que_existen_desde_su_directorio(tmp_path, monkeypatch):
    raiz = tmp_path / ("resultados_" + "x" * 60) / "MMGBSA-H3-FREESOLV-RADIOS" / "trabajo" / "mobley_1107178"
    (raiz / "brazo_B").mkdir(parents=True)
    prmtop, inpcrd = raiz / "brazo_B" / "ligand.prmtop", raiz / "ligand.inpcrd"
    prmtop.write_text("prmtop")
    inpcrd.write_text("inpcrd")
    assert len(str(prmtop.resolve())) > freesolv_h3.PBSA_MAX_RUTA, "el caso tiene que reproducir el fallo"

    llamadas: list = []
    monkeypatch.setattr(freesolv_h3.subprocess, "run", _falso_pbsa(llamadas))
    assert freesolv_h3._pb(prmtop, inpcrd, raiz / "pb_B") == pytest.approx(-7.1234)

    (orden, cwd), = llamadas
    for bandera, esperado in (("-p", prmtop), ("-c", inpcrd)):
        ruta = orden[orden.index(bandera) + 1]
        assert len(ruta) <= freesolv_h3.PBSA_MAX_RUTA
        assert not os.path.isabs(ruta)
        assert (cwd / ruta).resolve() == esperado.resolve()


def test_una_ruta_que_pbsa_cortaria_es_un_error_y_no_un_truncado(tmp_path):
    lejos = tmp_path / ("y" * 90) / "ligand.prmtop"
    cerca = tmp_path / "pb_B"
    cerca.mkdir()
    with pytest.raises(RuntimeError, match="ruta para pbsa"):
        freesolv_h3._ruta_pbsa(lejos, cerca)
