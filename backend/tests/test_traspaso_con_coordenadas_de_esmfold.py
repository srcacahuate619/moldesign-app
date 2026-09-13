"""El traspaso, con coordenadas del motor de verdad.

═══════════════════════════════════════════════════════════════════════════
POR QUÉ HACÍA FALTA OTRA SUITE
═══════════════════════════════════════════════════════════════════════════

`test_peptide_transfer.py` ya cubre `transferir_coordenadas`. Construye su PDB
así:

    mol = Chem.MolFromFASTA(sequence)
    AllChem.EmbedMolecule(mol, randomSeed=42)
    Chem.MolToPDBBlock(mol)

Es decir, **un conformero de RDKit**. Y con un conformero de RDKit el traspaso
funcionaba incluso con el código roto: la geometría ya es la que el propio campo
de fuerzas de RDKit considera relajada, así que la minimización restringida no
tiene nada contra lo que pelear. Medido: siete péptidos, desvío 0.250 Å, un solo
paso de minimización, todos pasan.

Con coordenadas de **ESMFold** —una estructura predicha, no una relajada por
MMFF— los mismos siete fallaban. **Diez de diez.** La suite estaba verde sobre
un camino que nunca había funcionado con el motor real.

Es la regla 6 del método de este proyecto, en otra forma: verde con un
sustituto no es verde.

═══════════════════════════════════════════════════════════════════════════
LOS FIXTURES SON PLEGADOS REALES, SELLADOS
═══════════════════════════════════════════════════════════════════════════

ESMFold son 8.44 GB y no puede estar en la suite. Así que se plegó una vez con
el modelo real —modo `fast`, CPU, runtime embebido— y los PDB quedaron en
`tests/fixtures/esmfold_plegados/`. Cada uno lleva su pLDDT en un REMARK.

Los cuatro casos no son arbitrarios: son un comportamiento cada uno.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from rdkit import Chem

RAIZ = Path(__file__).resolve().parents[1]
SIDECAR = str(RAIZ / "sidecars" / "esmfold")
if SIDECAR not in sys.path:
    sys.path.insert(0, SIDECAR)

from ligand_transfer import (  # noqa: E402
    TransferenciaPeptidicaError,
    transferir_coordenadas,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "esmfold_plegados"

#: (secuencia, ¿completa el traspaso?, por qué está en la lista)
CASOS = [
    ("GRGDSP", True,
     "hexapéptido con el traspaso completo: el caso de referencia"),
    ("YGGFM", True,
     "met-encefalina, un péptido real de cinco residuos"),
    ("GG", False,
     "dipéptido: nueve átomos pesados y el OXT libre no dejan geometría que "
     "satisfacer. Se abstiene a cualquier ancho de restricción, y debe hacerlo"),
    ("SIINFEKL", False,
     "se abstiene por 0.275 Å, apenas por encima del umbral de 0.26. Fija el "
     "borde: subir el umbral convertiría esto en una pose cuya geometría ya no "
     "es la que se plegó"),
]


def _plegado(seq: str) -> str:
    ruta = FIXTURES / f"{seq}.pdb"
    if not ruta.is_file():
        pytest.skip(f"falta el fixture {ruta.name}; se regenera plegando con ESMFold")
    return ruta.read_text(encoding="utf-8")


def _smiles(seq: str) -> str:
    return Chem.MolToSmiles(Chem.MolFromFASTA(seq))


# ── Los fixtures son lo que dicen ser ────────────────────────────────────

@pytest.mark.parametrize("seq,_ok,_nota", CASOS, ids=[c[0] for c in CASOS])
def test_el_fixture_es_un_plegado_real_y_lo_declara(seq: str, _ok: bool, _nota: str):
    texto = _plegado(seq)
    assert "ESMFold" in texto, "el fixture no declara su procedencia"
    assert "pLDDT" in texto, "el fixture no declara su confianza"
    atomos = [l for l in texto.splitlines() if l.startswith(("ATOM", "HETATM"))]
    assert atomos, "el fixture no tiene coordenadas"


def test_los_fixtures_no_son_conformeros_de_rdkit():
    """La comprobación que le da sentido a toda esta suite.

    Un conformero de RDKit trae OXT; ESMFold no lo emite. Si algún día alguien
    regenera estos fixtures con RDKit «porque es más cómodo», esta prueba lo
    dice antes de que la suite vuelva a estar verde sobre nada.
    """
    for seq, _ok, _nota in CASOS:
        texto = _plegado(seq)
        nombres = {l[12:16].strip() for l in texto.splitlines()
                   if l.startswith(("ATOM", "HETATM"))}
        assert "OXT" not in nombres, (
            f"{seq}: el fixture trae OXT, así que no viene de ESMFold. El átomo "
            "libre es justo lo que hace difícil el traspaso."
        )


# ── El traspaso, sobre esas coordenadas ──────────────────────────────────

@pytest.mark.parametrize("seq,completa,_nota", CASOS, ids=[c[0] for c in CASOS])
def test_el_traspaso_hace_lo_que_debe_con_cada_peptido(seq: str, completa: bool, _nota: str):
    smiles = _smiles(seq)
    if completa:
        t = transferir_coordenadas(smiles, _plegado(seq))
        m = t.manifest
        assert m["status"] == "completed"
        # La identidad química es la promesa del traspaso: el grafo que entra
        # es el que sale, átomo por átomo.
        assert m["input_graph_hash"] == m["output_graph_hash"]
        assert m["coordinates_transferred"] > 0
        # ESMFold no emite OXT; lo completa la minimización restringida.
        assert m["completed_atom_names"] == ["OXT"]
        assert m["coordinates_completed"] == 1
    else:
        with pytest.raises(TransferenciaPeptidicaError) as exc:
            transferir_coordenadas(smiles, _plegado(seq))
        assert exc.value.code == "LIGAND_GEOMETRY_COMPLETION_FAILED"
        # La abstención dice CUÁNTO se desvió, no sólo que falló.
        assert "desvio" in str(exc.value)


def test_una_abstencion_nunca_devuelve_geometria():
    """Abstenerse es no entregar nada, no entregar algo peor.

    Si alguna vez se relaja el umbral, lo que entra en el dossier es una pose
    cuya geometría ya no es la que ESMFold plegó — y nada en el expediente lo
    diría, porque el manifiesto seguiría declarando `coordinate_source:
    esmfold`.
    """
    with pytest.raises(TransferenciaPeptidicaError):
        transferir_coordenadas(_smiles("GG"), _plegado("GG"))


# ── El defecto concreto que se corrigió ──────────────────────────────────

def test_la_restriccion_es_mas_estrecha_que_el_umbral_que_la_juzga():
    """El defecto, fijado donde vive.

    `MMFFAddPositionConstraint(idx, ancho, ...)` deja moverse `ancho` SIN COSTE,
    y el traspaso rechaza por encima de 0.26 Å. Con ancho 0.25 quedaban 0.01 Å
    entre lo que el campo de fuerzas regala y lo que la comprobación admite: de
    diez péptidos pasaban cero. Con 0.05 pasan siete, y los tres que no tienen
    su número.

    Si alguien vuelve a igualarlos, esto falla antes que la ciencia.
    """
    import re

    fuente = (Path(SIDECAR) / "ligand_transfer.py").read_text(encoding="utf-8")

    def _constante(nombre: str) -> float:
        m = re.search(rf"^\s*{nombre}\s*=\s*([0-9.]+)\s*$", fuente, re.M)
        assert m, f"{nombre} dejó de ser una constante con nombre y valor literal"
        return float(m.group(1))

    ancho = _constante("ANCHO_RESTRICCION_A")
    umbral = _constante("TOLERANCIA_TRASPASO_A")

    assert ancho < umbral, (
        f"ancho {ancho} y umbral {umbral}: la comprobación mide su propia "
        "holgura, no la geometría"
    )
    # Un margen de 5x. No es cosmético: con 0.01 de margen pasaban 2 de 7.
    assert umbral >= ancho * 4
