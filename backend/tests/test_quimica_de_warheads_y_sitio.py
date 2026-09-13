"""Dos afirmaciones químicas que el producto hacía y no sostenía.

═══════════════════════════════════════════════════════════════════════════
1. EL GRUPO NITRO NO COORDINA ZINC
═══════════════════════════════════════════════════════════════════════════

`_WARHEAD_SMARTS["n_hydroxy"]` incluía `"N(O)"` con el comentario «notación
explícita N-óxido». En SMARTS eso es «nitrógeno alifático unido por enlace
simple a oxígeno alifático», y el enlace N–[O-] de CUALQUIER grupo nitro es
exactamente eso. Medido antes de corregirlo, con `target_family=metalloenzyme`:

    nitrobenceno    UMS 0.6500        lisinopril (quelante real de ACE)  0.6833
    metronidazol    UMS 0.6700
    nifedipino      UMS 0.6833

El nitro es uno de los grupos más comunes de la química medicinal. Un
nitroaromático cualquiera puntuaba como un quelante de zinc.

Y una segunda, del mismo detector: `n_warheads` contaba CLAVES que casaron, no
grupos químicos. Una sulfonamida primaria casa `sulfonamide` y
`primary_sulfonamide`; un hidroxámico lleva un N–OH dentro. Como
`0.85 + 0.10·min(n/3, 1)` es monótona en n, un solo grupo funcional entraba en
la fórmula valiendo el doble.

Rehacer las AUC de los tres perfiles M5-Zn sobre sus mismos checkpoints, con
los mismos pesos y sólo el detector corregido, da +0.0193 (CA2), +0.0081 (MMP9)
y +0.0471 (ACE). Ordena mejor; por eso el arreglo es V2 y no un parche.

═══════════════════════════════════════════════════════════════════════════
2. EL CENTRO DE LA CAJA ERA EL PROMEDIO DE TODAS LAS COPIAS
═══════════════════════════════════════════════════════════════════════════

`extract_accurate_pocket_centroid` agrupaba los HETATM por NOMBRE de residuo.
Con el mismo ligando en varias cadenas, el «centroide del ligando» era el
promedio de todas las copias: cae entre ellas y no dentro de ninguna.

Medido sobre las 411 estructuras del catálogo local: 184 promediaban copias y
**139 daban un centro más lejos del semilado de la caja que la copia más
cercana** — la caja no contenía ningún sitio de unión. Es el mismo modo de
fallo que el corrigendum de M5 documentó para el benchmark de MMP9, pero en la
ruta viva.
"""

from __future__ import annotations

import pytest

from scoring.ums import (
    compute_universal_metal_score,
    contar_warheads_distintos,
    detect_warheads,
)
from services.chemistry.protein_surgery import extract_accurate_pocket_centroid

METAL = "metalloenzyme"

#: Nitroaromáticos reales. Ninguno es un quelante de zinc.
NITRO = [
    ("nitrobenceno", "[O-][N+](=O)c1ccccc1"),
    ("metronidazol", "Cc1ncc([N+](=O)[O-])n1CCO"),
    ("nifedipino", "COC(=O)C1=C(C)NC(C)=C(C(=O)OC)C1c1ccccc1[N+](=O)[O-]"),
]

#: Quelantes de zinc de manual, uno por clase de warhead.
QUELANTES = [
    ("acetazolamida", "CC(=O)Nc1nnc(s1)S(N)(=O)=O", "sulfonamida"),
    ("vorinostat", "ONC(=O)CCCCCCC(=O)Nc1ccccc1", "hidroxamico"),
    ("captopril", "CC(CS)C(=O)N1CCCC1C(=O)O", "tiol"),
]


# ── El nitro ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("nombre,smiles", NITRO, ids=[n for n, _ in NITRO])
def test_un_nitro_no_es_un_warhead_de_zinc(nombre: str, smiles: str):
    warheads = detect_warheads(smiles)
    assert not any(warheads.values()), (
        f"{nombre}: el detector marca {sorted(k for k, v in warheads.items() if v)}. "
        "El grupo nitro no coordina zinc."
    )


@pytest.mark.parametrize("nombre,smiles", NITRO, ids=[n for n, _ in NITRO])
def test_un_nitro_no_puntua_como_un_quelante(nombre: str, smiles: str):
    score, _ = compute_universal_metal_score(smiles, target_family=METAL)
    # Sin warhead el score vive en la zona baja: 0.20·donantes + 0.20·molchamb.
    assert score < 0.30, f"{nombre}: UMS {score}, y no tiene warhead ninguno"


def test_un_nitro_puntua_por_debajo_de_un_quelante_real():
    """La comprobación que importa es el ORDEN, no el valor absoluto."""
    nitro, _ = compute_universal_metal_score(NITRO[0][1], target_family=METAL)
    lisinopril, _ = compute_universal_metal_score(
        "NCCCCC(NC(CCc1ccccc1)C(=O)O)C(=O)N1CCCC1C(=O)O", target_family=METAL
    )
    assert nitro < lisinopril


# ── Los quelantes de verdad siguen detectándose ──────────────────────────

@pytest.mark.parametrize("nombre,smiles,_f", QUELANTES, ids=[q[0] for q in QUELANTES])
def test_los_quelantes_reales_siguen_saliendo(nombre: str, smiles: str, _f: str):
    assert any(detect_warheads(smiles).values()), f"{nombre} dejó de detectarse"


# ── La sulfonamida necesita un N–H para coordinar ────────────────────────

def test_una_sulfonamida_terciaria_no_es_un_quelante():
    """El zinc se une a R-SO2-NH(-); sin hidrógeno no hay forma desprotonada.

    El sildenafilo lleva una sulfonamida N,N-disustituida y puntuaba 0.7033,
    por encima del lisinopril (0.6833), que sí quela el zinc de ACE.
    """
    sildenafilo = "CCCc1nn(C)c2c1nc([nH]c2=O)-c1cc(ccc1OCC)S(=O)(=O)N1CCN(C)CC1"
    assert detect_warheads(sildenafilo)["sulfonamide"] is False


def test_una_sulfonamida_primaria_si_lo_es():
    assert detect_warheads("Cc1ccc(cc1)-c1cc(nn1-c1ccc(cc1)S(N)(=O)=O)C(F)(F)F")[
        "primary_sulfonamide"
    ] is True


# ── El conteo: grupos, no claves ─────────────────────────────────────────

def test_una_sulfonamida_primaria_es_un_grupo_y_no_dos():
    warheads = detect_warheads("CC(=O)Nc1nnc(s1)S(N)(=O)=O")
    assert warheads["sulfonamide"] and warheads["primary_sulfonamide"]
    assert contar_warheads_distintos(warheads) == 1, (
        "las dos claves describen el mismo grupo funcional"
    )


def test_un_hidroxamico_es_un_grupo_y_no_dos():
    warheads = detect_warheads("ONC(=O)CCCCCCC(=O)Nc1ccccc1")
    assert warheads["hydroxamic"]
    assert contar_warheads_distintos(warheads) == 1


def test_dos_grupos_distintos_si_cuentan_dos():
    # Captopril: tiol y carboxilato, que son dos modos de coordinación.
    warheads = detect_warheads("CC(CS)C(=O)N1CCCC1C(=O)O")
    assert contar_warheads_distintos(warheads) == 2


# ── El centro de la caja ─────────────────────────────────────────────────

def _linea_het(serie: int, atomo: str, res: str, cadena: str, num: int,
               x: float, y: float, z: float, elem: str) -> str:
    """Una línea HETATM con las columnas del formato PDB donde toca.

    `res` va en [17:20] y la cadena en [21]; una sola columna de desfase hace
    que el parser lea otro residuo, que es justo lo que esta suite comprueba.
    """
    return (
        f"HETATM{serie:5d} {atomo:<4s} {res:>3s} {cadena}{num:4d}    "
        f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00 20.00          {elem:>2s}\n"
    )


def _linea_atom(serie: int, x: float, y: float, z: float) -> str:
    return (
        f"ATOM  {serie:5d}  CA  ALA A{serie:4d}    "
        f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00 20.00           C\n"
    )


def test_el_centro_cae_sobre_una_copia_y_no_entre_todas(tmp_path):
    """Dos copias del mismo ligando, a 60 Å. El promedio no está en ninguna."""
    pdb = tmp_path / "dos_copias.pdb"
    lineas = [_linea_atom(1, 0.0, 0.0, 0.0)]
    # Copia A en el origen, copia B a 60 Å en x. Cuatro átomos cada una.
    for i in range(4):
        lineas.append(_linea_het(100 + i, f"C{i}", "STI", "A", 1, i * 1.0, 0.0, 0.0, "C"))
    for i in range(4):
        lineas.append(_linea_het(200 + i, f"C{i}", "STI", "B", 1, 60.0 + i * 1.0, 0.0, 0.0, "C"))
    pdb.write_text("".join(lineas), encoding="utf-8")

    centro, metodo = extract_accurate_pocket_centroid(str(pdb))

    assert centro is not None
    assert metodo.startswith("DRUG_LIGAND")
    # El promedio de las dos copias estaría en x≈31.5, que no es ninguna.
    assert centro[0] < 10.0 or centro[0] > 55.0, (
        f"el centro {centro} es el promedio de las dos copias: no está en ninguna"
    )
    assert "2 copias" in metodo, (
        "la etiqueta tiene que declarar que había más de una copia"
    )


def test_entre_metales_manda_la_preferencia_catalitica_y_no_la_cuenta(tmp_path):
    """MMP9: cinco calcios estructurales y un zinc catalítico.

    Elegir por número de iones devuelve CA, que es el error de sitio que
    `protocols/m5/base.py` nombra explícitamente.
    """
    pdb = tmp_path / "mmp9_sintetico.pdb"
    lineas = [_linea_atom(1, 0.0, 0.0, 0.0)]
    for i in range(5):
        lineas.append(_linea_het(300 + i, "CA", "CA", "A", 1400 + i, 40.0 + i, 0.0, 0.0, "CA"))
    lineas.append(_linea_het(400, "ZN", "ZN", "A", 1450, 1.0, 2.0, 3.0, "ZN"))
    pdb.write_text("".join(lineas), encoding="utf-8")

    centro, metodo = extract_accurate_pocket_centroid(str(pdb))

    assert metodo.startswith("CATALYTIC_METAL (ZN"), (
        f"eligió {metodo}: el catalítico es el zinc, no el calcio estructural"
    )
    assert centro == (1.0, 2.0, 3.0)


def test_la_etiqueta_nombra_la_copia_concreta(tmp_path):
    """Un centro que no se puede explicar no se puede auditar."""
    pdb = tmp_path / "una_copia.pdb"
    lineas = [_linea_atom(1, 0.0, 0.0, 0.0)]
    for i in range(3):
        lineas.append(_linea_het(100 + i, f"C{i}", "STI", "B", 777, i * 1.0, 0.0, 0.0, "C"))
    pdb.write_text("".join(lineas), encoding="utf-8")

    _, metodo = extract_accurate_pocket_centroid(str(pdb))

    assert "STI" in metodo and "B777" in metodo
