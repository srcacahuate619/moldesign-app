"""Preparación declara la regla con la que se eligió cada altloc, desempate incluido (FEP-06-PRE, 2026-10-24).

En 1M17 (P01 y P10) las dos conformaciones de CYS A:751 y ASP A:831 tienen 0,50/0,50 y la preparación eligió A. El texto
decía «la de mayor ocupación sin declararlo», que no explica un empate; la regla es ocupación sumada y, si empatan, la
primera por letra.
"""
from __future__ import annotations

from pathlib import Path

from services.docking.preparer import _filter_pdb_content


def _atomo(n: int, nombre: str, alt: str, ocupacion: float, x: float) -> str:
    return (f"ATOM  {n:5d}  {nombre:<3}{alt}ASP A 831    {x:8.3f}   0.000   0.000{ocupacion:6.2f}  0.00           "
            f"{nombre[0]}\n")


def test_con_empate_se_elige_la_primera_letra_como_dice_el_texto():
    pdb = (_atomo(1, "CA", "", 1.0, 0.0) + _atomo(2, "CG", "A", 0.5, 1.0) + _atomo(3, "CG", "B", 0.5, 2.0))
    filtrado = _filter_pdb_content(pdb, chain_id="A", keep_hetatm=False)
    cg = [l for l in filtrado.splitlines() if l[12:16].strip() == "CG"]
    assert len(cg) == 1 and float(cg[0][30:38]) == 1.0

    texto = (Path(__file__).resolve().parents[1] / "services" / "dossier" / "preparacion.py").read_text(encoding="utf-8")
    assert "si empatan, la " in texto and "primera por letra (A antes que B)" in texto
    assert "sin declararlo" not in texto
