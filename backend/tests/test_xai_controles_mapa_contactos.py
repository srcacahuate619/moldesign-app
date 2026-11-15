"""Controles con respuesta conocida de los contactos y del mapa que ve el usuario en Explicabilidad.

Cada contacto se CONSTRUYE con una geometría conocida (distancia exacta, átomo exacto), se pasa por
el analizador y el generador de mapas reales de producción, y se comprueba que el producto recupera
lo construido:

  M01  π-stacking: una Phe y un tolueno a 3,8 Å de plano a plano → el contacto es `pi_stacking`
       con la Phe, a 3,8 Å, y resalta los SEIS átomos del anillo (no el metilo);
  M02  puente de H Ser/Thr/Tyr–O=C a 2,8 Å → `hbond` y se resalta SÓLO el oxígeno aceptor;
  M03  reordenar los átomos del ligando mueve el resaltado con su átomo químico, no con el índice;
  M04  umbral: el puente de H aparece a 2,8 y 3,2 Å y no a 4,0 ni 4,6 Å (corte de ProLIF: 3,5 Å);
  M05  control negativo: un ligando a 40 Å no tiene contactos ni resaltado;
  M06  Meeko → SDF conserva los elementos en salidas REALES de Vina (9 poses de paracetamol y un
       macrociclo) y en ligandos con fósforo: la conversión no inventa ni cambia elementos;
  M07  la caché del informe no mezcla poses ni receptores distintos, y acierta cuando nada cambió.

Nota de método: el péptido se construye con `addResidueInfo=True`. Sin ella sus H salen como HETATM y
el analizador, que sólo lee registros ATOM (como el receptor real, cuyos H polares son ATOM), los
descarta y los regenera en otra posición: el primer montaje de M02 no detectó el puente por eso.
"""

from __future__ import annotations

import collections
import random
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import numpy as np
import pytest

Chem = pytest.importorskip("rdkit.Chem")
from rdkit.Chem import AllChem  # noqa: E402

from services.interactions.analyzer import analyze_complex  # noqa: E402
from services.interactions.contact_map import build_contact_map  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "meeko_export"


# ─────────────────────────────────────────────────────────────────────────────
# Armado
# ─────────────────────────────────────────────────────────────────────────────


def _peptido(secuencia: str):
    m = Chem.AddHs(Chem.MolFromSequence(secuencia), addCoords=True, addResidueInfo=True)
    p = AllChem.ETKDGv3()
    p.useRandomCoords = True
    p.randomSeed = 7
    p.maxIterations = 2000
    assert AllChem.EmbedMolecule(m, p) == 0
    AllChem.MMFFOptimizeMolecule(m, maxIters=2000)
    return m


@pytest.fixture(scope="module")
def peptidos(tmp_path_factory):
    d = tmp_path_factory.mktemp("peptidos")
    salida = {}
    for nombre, seq in (("A", "ACDEFGHIKL"), ("B", "MNPQRSTVWY")):  # A trae Phe; B trae Ser, Thr y Tyr
        mol = _peptido(seq)
        pdb = d / f"{nombre}.pdb"
        Chem.MolToPDBFile(mol, str(pdb))
        salida[nombre] = {"mol": mol, "pdb": str(pdb), "pos": mol.GetConformer().GetPositions()}
    return salida


def _ligando(smiles: str, semilla: int = 11):
    m = Chem.AddHs(Chem.MolFromSmiles(smiles))
    assert AllChem.EmbedMolecule(m, randomSeed=semilla) == 0
    return m


def _poner(mol, posiciones: np.ndarray):
    conf = mol.GetConformer()
    for i, p in enumerate(np.round(posiciones, 3)):  # 3 decimales, como un PDBQT
        conf.SetAtomPosition(i, p.tolist())


def _sdf(mol, ruta: Path) -> str:
    w = Chem.SDWriter(str(ruta))
    w.write(mol)
    w.close()
    return str(ruta)


def _rotacion(de: np.ndarray, a: np.ndarray) -> np.ndarray:
    de, a = de / np.linalg.norm(de), a / np.linalg.norm(a)
    c, d = np.cross(de, a), float(np.dot(de, a))
    s = np.linalg.norm(c)
    if s < 1e-9:
        return np.eye(3) if d > 0 else -np.eye(3)
    k = np.array([[0, -c[2], c[1]], [c[2], 0, -c[0]], [-c[1], c[0], 0]])
    return np.eye(3) + k + k @ k * ((1 - d) / s**2)


def _indice(mol, residuo: str, atomo: str) -> int:
    for a in mol.GetAtoms():
        ri = a.GetPDBResidueInfo()
        if ri is not None and ri.GetResidueName() == residuo and ri.GetName().strip() == atomo:
            return a.GetIdx()
    raise KeyError((residuo, atomo))


def _normal_y_centro(p: np.ndarray):
    c = p.mean(axis=0)
    return c, np.linalg.svd(p - c)[2][2]


def _acetamida_sobre_donador(pep, residuo: str, atomo: str, distancia: float, tmp: Path, nombre: str):
    """N-metilacetamida con su O carbonílico en la prolongación del enlace O–H del donador, a `distancia` Å.
    Devuelve (sdf, índice del O, molécula)."""
    mol, pos = pep["mol"], pep["pos"]
    d_idx = _indice(mol, residuo, atomo)
    h = next(n.GetIdx() for n in mol.GetAtomWithIdx(d_idx).GetNeighbors() if n.GetAtomicNum() == 1)
    eje = pos[h] - pos[d_idx]
    eje /= np.linalg.norm(eje)
    lig = _ligando("CC(=O)NC")
    l = lig.GetConformer().GetPositions()
    o = next(a.GetIdx() for a in lig.GetAtoms() if a.GetSymbol() == "O")
    c = lig.GetAtomWithIdx(o).GetNeighbors()[0].GetIdx()
    R = _rotacion(l[c] - l[o], eje)
    _poner(lig, (l - l[o]) @ R.T + (pos[d_idx] + distancia * eje))
    return _sdf(lig, tmp / f"{nombre}.sdf"), o, lig


def _contactos(tipo: str, informe) -> list:
    return [i for i in informe.interactions if i.type == tipo]


# ─────────────────────────────────────────────────────────────────────────────
# M01 — π-stacking
# ─────────────────────────────────────────────────────────────────────────────


def test_m01_pi_stacking_a_3_8_angstrom_resalta_los_seis_atomos_del_anillo(peptidos, tmp_path):
    pep = peptidos["A"]
    anillo_phe = [_indice(pep["mol"], "PHE", n) for n in ("CG", "CD1", "CD2", "CE1", "CE2", "CZ")]
    c_phe, n_phe = _normal_y_centro(pep["pos"][anillo_phe])
    tolueno = _ligando("Cc1ccccc1")
    l = tolueno.GetConformer().GetPositions()
    anillo = [a.GetIdx() for a in tolueno.GetAtoms() if a.GetIsAromatic()]
    c_l, n_l = _normal_y_centro(l[anillo])
    _poner(tolueno, (l - c_l) @ _rotacion(n_l, n_phe).T + c_phe + 3.8 * n_phe)
    sdf = _sdf(tolueno, tmp_path / "tolueno.sdf")

    informe = analyze_complex(pep["pdb"], sdf, "m", "TEST", 1)
    assert informe.engine.startswith("prolif:")
    apilados = _contactos("pi_stacking", informe)
    assert len(apilados) == 1
    contacto = apilados[0]
    assert contacto.residue_name == "PHE"
    assert contacto.distance == pytest.approx(3.8, abs=0.05)
    assert set(contacto.ligand_atom_indices) == set(anillo) == {1, 2, 3, 4, 5, 6}

    mapa = build_contact_map(sdf, informe)
    assert mapa["status"] == "ready"
    en_el_mapa = next(m for m in mapa["contacts"] if informe.interactions[m["contact_index"]] is contacto)
    assert set(en_el_mapa["atom_indices"]) == set(anillo) and en_el_mapa["hidden_hydrogen_indices"] == []
    assert 0 not in mapa["highlighted_atom_indices"], "el metilo no participa del apilamiento ni se resalta"
    assert {a["index"]: a["element"] for a in mapa["atoms"]}[1] == "C"


# ─────────────────────────────────────────────────────────────────────────────
# M02 — puente de hidrógeno: sólo se resalta el aceptor
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("residuo,atomo", [("SER", "OG"), ("THR", "OG1"), ("TYR", "OH")])
def test_m02_puente_de_h_a_2_8_angstrom_resalta_solo_el_oxigeno_aceptor(peptidos, tmp_path, residuo, atomo):
    sdf, o, _ = _acetamida_sobre_donador(peptidos["B"], residuo, atomo, 2.8, tmp_path, f"nma_{residuo}")
    informe = analyze_complex(peptidos["B"]["pdb"], sdf, "m", "TEST", 1)
    puentes = _contactos("hbond", informe)
    assert len(puentes) == 1, [(i.type, i.residue_name) for i in informe.interactions]
    assert puentes[0].residue_name == residuo
    assert puentes[0].distance == pytest.approx(2.8, abs=0.05)
    assert puentes[0].ligand_atom_indices == (o,)
    mapa = build_contact_map(sdf, informe)
    assert mapa["status"] == "ready"
    assert mapa["highlighted_atom_indices"] == [o]
    assert {a["index"]: a["element"] for a in mapa["atoms"]}[o] == "O"


# ─────────────────────────────────────────────────────────────────────────────
# M03 — el resaltado sigue al átomo químico, no al índice
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("semilla", [1, 4, 9])
def test_m03_reordenar_los_atomos_del_ligando_mueve_el_resaltado_con_su_atomo(peptidos, tmp_path, semilla):
    sdf, o, lig = _acetamida_sobre_donador(peptidos["B"], "SER", "OG", 2.8, tmp_path, "orig")
    orden = list(range(lig.GetNumAtoms()))
    random.Random(semilla).shuffle(orden)
    permutado = Chem.RenumberAtoms(lig, orden)
    sdf_p = _sdf(permutado, tmp_path / "perm.sdf")
    nuevo_o = orden.index(o)  # RenumberAtoms: el átomo nuevo i es el antiguo orden[i]

    informe = analyze_complex(peptidos["B"]["pdb"], sdf_p, "m", "TEST", 1)
    mapa = build_contact_map(sdf_p, informe)
    assert [i.ligand_atom_indices for i in _contactos("hbond", informe)] == [(nuevo_o,)]
    assert mapa["highlighted_atom_indices"] == [nuevo_o]
    assert {a["index"]: a["element"] for a in mapa["atoms"]}[nuevo_o] == "O"


def test_m03_el_barajado_de_control_mueve_al_menos_un_oxigeno(peptidos, tmp_path):
    """Si ninguna semilla moviera el oxígeno, M03 no probaría nada: se exige que alguna lo mueva."""
    _, o, lig = _acetamida_sobre_donador(peptidos["B"], "SER", "OG", 2.8, tmp_path, "orig2")
    movido = []
    for semilla in (1, 4, 9):
        orden = list(range(lig.GetNumAtoms()))
        random.Random(semilla).shuffle(orden)
        movido.append(orden.index(o) != o)
    assert any(movido)


# ─────────────────────────────────────────────────────────────────────────────
# M04 — umbral de distancia del puente de H; M05 — control negativo
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("distancia,detectado", [(2.8, True), (3.2, True), (4.0, False), (4.6, False)])
def test_m04_el_puente_de_h_se_detecta_dentro_del_corte_y_no_fuera(peptidos, tmp_path, distancia, detectado):
    sdf, o, _ = _acetamida_sobre_donador(peptidos["B"], "SER", "OG", distancia, tmp_path, f"d{distancia}")
    informe = analyze_complex(peptidos["B"]["pdb"], sdf, "m", "TEST", 1)
    assert bool(_contactos("hbond", informe)) is detectado


def test_m05_un_ligando_a_40_angstrom_no_tiene_contactos_ni_resaltado(peptidos, tmp_path):
    _, _, lig = _acetamida_sobre_donador(peptidos["B"], "SER", "OG", 2.8, tmp_path, "cerca")
    _poner(lig, lig.GetConformer().GetPositions() + np.array([40.0, 0.0, 0.0]))
    sdf = _sdf(lig, tmp_path / "lejos.sdf")
    informe = analyze_complex(peptidos["B"]["pdb"], sdf, "m", "TEST", 1)
    assert informe.interactions == []
    mapa = build_contact_map(sdf, informe)
    assert mapa["status"] == "ready" and mapa["highlighted_atom_indices"] == []


# ─────────────────────────────────────────────────────────────────────────────
# M06 — Meeko → SDF conserva los elementos
# ─────────────────────────────────────────────────────────────────────────────


def _pesados(mol) -> dict[str, int]:
    return dict(collections.Counter(a.GetSymbol() for a in mol.GetAtoms() if a.GetAtomicNum() > 1))


@pytest.mark.skipif(not FIXTURES.exists(), reason="faltan las salidas reales de Vina")
@pytest.mark.parametrize("nombre,registros", [("paracetamol_9_poses", 9), ("exaltolida_macrociclo", 3)])
def test_m06_mk_export_de_una_salida_real_de_vina_conserva_los_elementos_del_smiles(tmp_path, nombre, registros):
    pdbqt = FIXTURES / f"{nombre}.pdbqt"
    smiles = next(
        l.split(None, 2)[2] for l in pdbqt.read_text(errors="replace").splitlines()
        if l.startswith("REMARK SMILES ") and "IDX" not in l
    )
    salida = tmp_path / f"{nombre}.sdf"
    r = subprocess.run([sys.executable, "-m", "meeko.cli.mk_export", str(pdbqt), "-s", str(salida)],
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr[-300:]
    moldes = list(Chem.SDMolSupplier(str(salida), removeHs=False))
    assert len(moldes) == registros
    esperado = _pesados(Chem.MolFromSmiles(smiles))
    assert all(_pesados(m) == esperado for m in moldes), (esperado, [_pesados(m) for m in moldes][:2])


@pytest.mark.parametrize("nombre,smiles", [
    ("aspirina", "CC(=O)Oc1ccccc1C(=O)O"),       # sin P: el «PH» de una captura no puede salir de aquí
    ("fosfonato", "COP(=O)(O)C"),                 # con P: debe seguir siendo P
    ("fosfina", "OC(=O)c1ccccc1P"),
])
def test_m06_el_camino_meeko_del_producto_conserva_los_elementos(tmp_path, nombre, smiles):
    """`mk_prepare_ligand` (como en `vina_service`) y `mk_export` (como al exportar las poses)."""
    m = Chem.AddHs(Chem.MolFromSmiles(smiles))
    assert AllChem.EmbedMolecule(m, randomSeed=3) == 0
    entrada = _sdf(m, tmp_path / f"{nombre}.sdf")
    pdbqt = tmp_path / f"{nombre}.pdbqt"
    r = subprocess.run([sys.executable, "-m", "meeko.cli.mk_prepare_ligand", "-i", entrada, "-o", str(pdbqt)],
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, (r.stderr or r.stdout)[-300:]
    como_vina = tmp_path / f"{nombre}_modelos.pdbqt"
    como_vina.write_text("MODEL 1\n" + pdbqt.read_text() + "ENDMDL\n")
    salida = tmp_path / f"{nombre}_pose.sdf"
    r = subprocess.run([sys.executable, "-m", "meeko.cli.mk_export", str(como_vina), "-s", str(salida)],
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr[-300:]
    exportado = Chem.SDMolSupplier(str(salida), removeHs=False)[0]
    assert _pesados(exportado) == _pesados(m)


# ─────────────────────────────────────────────────────────────────────────────
# M07 — la caché del informe de contactos
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_m07_la_cache_acierta_si_nada_cambio_y_no_mezcla_poses_ni_corridas(monkeypatch):
    from api.routers import interactions as ruta
    from services.interactions.analyzer import InteractionReport
    import services.interactions.analyzer as analizador
    from tests.test_interacciones_pose_corrida import _preparar, _sdf_tres_poses

    llamadas = []

    def espia(*, ligand_sdf_path, **kwargs):
        llamadas.append(kwargs["pose_rank"])
        return InteractionReport(molecule_id=kwargs["molecule_id"], target_pdb_id=kwargs["target_pdb_id"],
                                 pose_rank=kwargs["pose_rank"])

    monkeypatch.setattr(analizador, "analyze_complex", espia)
    mol_id = str(uuid4())
    pedir = lambda rank: ruta.get_interactions(mol_id, pose_rank=rank, db=object(), current_user=None)

    _preparar(monkeypatch, _sdf_tres_poses())
    primera = await pedir(2)
    assert llamadas == [2]
    segunda = await pedir(2)
    assert llamadas == [2], "con la misma pose y el mismo receptor no se recalcula"
    assert segunda["computed_at"] == primera["computed_at"]

    await pedir(3)
    assert llamadas == [2, 3], "otra pose es otro informe"

    # La misma molécula y pose, pero con el archivo de poses cambiado: el hash cambia y no hay acierto.
    otro = _sdf_tres_poses().replace("RDKit", "RDKiT")  # un byte distinto en la cabecera: otro hash, mismo contenido químico
    assert otro != _sdf_tres_poses()
    _preparar(monkeypatch, otro)
    await pedir(2)
    assert llamadas == [2, 3, 2], "poses con otro hash no reutilizan el informe de las anteriores"

    ruta.limpiar_cache_de_interacciones()
    _preparar(monkeypatch, otro)
    await pedir(2)
    assert llamadas == [2, 3, 2, 2], "vaciada la caché se vuelve a calcular"


def test_m07_la_cache_tiene_un_tope_y_expulsa_la_mas_antigua():
    from api.routers import interactions as ruta

    ruta.limpiar_cache_de_interacciones()
    for i in range(ruta._CACHE_DE_INTERACCIONES_MAX + 5):
        ruta._cache_put(("k", i), {"i": i})
    assert len(ruta._cache_de_interacciones) == ruta._CACHE_DE_INTERACCIONES_MAX
    assert ruta._cache_get(("k", 0)) is None and ruta._cache_get(("k", 4)) is None
    assert ruta._cache_get(("k", ruta._CACHE_DE_INTERACCIONES_MAX + 4)) == {"i": ruta._CACHE_DE_INTERACCIONES_MAX + 4}
    ruta.limpiar_cache_de_interacciones()
