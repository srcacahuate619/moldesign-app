"""
Dos enantiómeros no pueden salir con el mismo hash.

# El fallo

`generate_conformer` canonicaliza el tautómero antes de generar coordenadas:

    te = rdMolStandardize.TautomerEnumerator()
    canonical = Chem.MolToSmiles(te.Canonicalize(mol))

`TautomerEnumerator()` trae `tautomerRemoveSp3Stereo = True` por defecto: al
canonicalizar, RDKit **borra** la configuración de todo estereocentro sp3
implicado en el sistema tautomérico. Es un valor por defecto razonable para
deduplicar catálogos, y desastroso para preparar una molécula que se va a
acoplar. Medido antes del arreglo:

    entrada           tras Canonicalize()
    (S)-talidomida    O=C1CCC(N2C(=O)c3ccccc3C2=O)C(=O)N1
    (R)-talidomida    O=C1CCC(N2C(=O)c3ccccc3C2=O)C(=O)N1   ← la misma

Los dos enantiómeros de la talidomida, que es el caso por el que la quiralidad
se enseña en primero, salían siendo la misma molécula. Y como el hash se
recalcula sobre el SMILES transformado, tri-Ala-L y tri-Ala-D producían el
mismo `smiles_hash` (`10c896f8`), el mismo `conformer.sdf` en disco y la misma
entrada de caché de docking: una corrida servía el resultado de la otra.

# Y la pregunta de los D-péptidos

Quedaba abierto «decidir si Vina sostiene esa flexibilidad». La medición dice
que la pregunta era otra: **un D-péptido no llegaba a Vina como D**. ESMFold y
RFdiffusion lo rechazan explícitamente (ver `sidecars/esmfold/secuencia.py`), la
corrida cae al respaldo de Vina, y este paso le quitaba la quiralidad sin decir
nada. Sobre la flexibilidad en sí, medido aparte con el binario empaquetado
(Vina 1.2.7): acepta hasta 51 torsiones activas —un péptido de 13 residuos— sin
error, así que no hay un techo duro que declarar.

# Qué cubre este archivo

Arreglar el tautomerizador dejaba una pregunta abierta: ¿era el único punto de
fuga? Se auditaron los demás pasos del camino, uno a uno, y **ninguno pierde la
configuración**. Esas comprobaciones están aquí para que siga siendo verdad:

    paso                              cómo se prueba
    canonicalización de tautómeros    el fallo original, arriba
    protonación (dimorphite-dl)       `test_la_protonacion_...`
    conformero 3D -> SDF en disco     `test_el_sdf_que_se_guarda_...`
    SDF -> PDBQT -> SDF (Meeko)       `test_la_ida_y_vuelta_por_meeko_...`

El último va marcado `slow` y ejecuta las MISMAS herramientas de línea de
comandos que el pipeline —`mk_prepare_ligand` y `mk_export`, en subproceso—, no
la API de Python de Meeko. La distinción importa: es ese par el que reconstruye
conectividad y órdenes de enlace sobre las coordenadas que devuelve Vina, y es
donde una pérdida de estereoquímica pasaría inadvertida. Son ocho subprocesos y
tardan unos 37 s en total; casi todo es arranque de intérprete e importación,
así que el coste lo pone el número de moléculas y no su tamaño.

Vina en sí no puede epimerizar nada: sólo gira torsiones sobre las coordenadas
que recibe. Por eso el trayecto que hay que cubrir es el de preparación y
reconstrucción, no el acoplamiento.
"""

from __future__ import annotations

import asyncio

import pytest
from rdkit import Chem
from rdkit.Chem import AllChem

from chem.conformer import generate_conformer

# (nombre, SMILES del par de enantiómeros)
PARES = [
    (
        "talidomida",
        "O=C1CC[C@H](N2C(=O)c3ccccc3C2=O)C(=O)N1",
        "O=C1CC[C@@H](N2C(=O)c3ccccc3C2=O)C(=O)N1",
    ),
    (
        "ibuprofeno",
        "CC(C)Cc1ccc(cc1)[C@@H](C)C(O)=O",
        "CC(C)Cc1ccc(cc1)[C@H](C)C(O)=O",
    ),
    (
        "tri_alanina",
        "C[C@H](N)C(=O)N[C@@H](C)C(=O)N[C@@H](C)C(=O)O",
        "C[C@@H](N)C(=O)N[C@H](C)C(=O)N[C@H](C)C(=O)O",
    ),
    # Una amina básica con hidroxilo: la protonación a pH 7.4 la carga, así que
    # es el par que ejercita de verdad el paso de dimorphite-dl.
    (
        "propranolol",
        "CC(C)NC[C@H](O)COc1cccc2ccccc12",
        "CC(C)NC[C@@H](O)COc1cccc2ccccc12",
    ),
]


def _canonicalizar_tautomero(smiles: str) -> str:
    """El paso exacto de `generate_conformer`, aislado."""
    from rdkit.Chem.MolStandardize import rdMolStandardize

    parametros = rdMolStandardize.CleanupParameters()
    parametros.tautomerRemoveSp3Stereo = False
    te = rdMolStandardize.TautomerEnumerator(parametros)
    return Chem.MolToSmiles(te.Canonicalize(Chem.MolFromSmiles(smiles)))


@pytest.mark.parametrize(("nombre", "uno", "otro"), PARES)
def test_el_tautomero_canonico_conserva_el_estereocentro(nombre, uno, otro):
    a, b = _canonicalizar_tautomero(uno), _canonicalizar_tautomero(otro)
    assert a != b, f"{nombre}: los dos enantiómeros colapsan en {a}"
    assert "@" in a and "@" in b, f"{nombre}: se perdió la configuración"


@pytest.mark.parametrize(("nombre", "uno", "otro"), PARES)
def test_dos_enantiomeros_no_comparten_hash_ni_conformero(nombre, uno, otro):
    """El hash decide el archivo en disco Y la entrada de caché del docking."""
    a = asyncio.run(generate_conformer(uno))
    b = asyncio.run(generate_conformer(otro))
    assert a["smiles_hash"] != b["smiles_hash"], (
        f"{nombre}: los dos enantiómeros producen el hash {a['smiles_hash'][:8]}, "
        f"así que comparten conformero en disco y entrada de caché"
    )
    assert a["conformer_path"] != b["conformer_path"]


def test_la_canonicalizacion_de_tautomeros_sigue_funcionando():
    """Conservar la quiralidad no puede apagar lo que este paso hace.

    La guanina tiene tautómeros de verdad y debe seguir convergiendo a uno solo.
    """
    formas = [
        "Nc1nc2[nH]cnc2c(=O)[nH]1",
        "Nc1nc(=O)c2[nH]cnc2[nH]1",
    ]
    canonicos = {_canonicalizar_tautomero(f) for f in formas}
    assert len(canonicos) == 1, f"la guanina no converge: {canonicos}"


def test_el_conformero_declara_que_conserva_la_configuracion():
    """El SMILES que se acopla tiene que llevar la quiralidad de la entrada."""
    d = asyncio.run(
        generate_conformer("C[C@@H](N)C(=O)N[C@H](C)C(=O)N[C@H](C)C(=O)O")
    )
    assert "@" in d["canonical_smiles"], (
        f"el SMILES que se acopla perdió la configuración: {d['canonical_smiles']}"
    )


# ── Los demás pasos del camino ─────────────────────────────────────────────
#
# El tautomerizador era la fuga, pero no había ninguna prueba de que fuera la
# única. Estas cubren el resto, en el mismo orden en que corren.

def _centros(smiles: str) -> list[tuple[int, str]]:
    """Los estereocentros asignados, como `(índice, 'R'|'S')`."""
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return []
    Chem.AssignStereochemistry(mol, cleanIt=True, force=True)
    return Chem.FindMolChiralCenters(mol, includeUnassigned=False, useLegacyImplementation=False)


def _no_colapsan(nombre: str, uno: str, otro: str, esperados: int) -> None:
    """Dos enantiómeros siguen siendo dos, y con todos sus centros asignados."""
    assert Chem.CanonSmiles(uno) != Chem.CanonSmiles(otro), (
        f"{nombre}: los dos enantiómeros colapsan en {Chem.CanonSmiles(uno)}"
    )
    for etiqueta, smiles in (("A", uno), ("B", otro)):
        centros = _centros(smiles)
        assert len(centros) == esperados, (
            f"{nombre} ({etiqueta}): quedan {len(centros)} estereocentros "
            f"asignados de {esperados}; se perdió configuración por el camino"
        )
        assert all(codigo in ("R", "S") for _idx, codigo in centros), (
            f"{nombre} ({etiqueta}): hay centros sin asignar: {centros}"
        )


@pytest.mark.parametrize(("nombre", "uno", "otro"), PARES)
def test_la_protonacion_conserva_el_estereocentro(nombre, uno, otro):
    """dimorphite-dl reescribe el SMILES para cargarlo a pH 7.4.

    Reescribir un SMILES es exactamente la operación que perdió la
    estereoquímica en el tautomerizador, así que se comprueba igual. Se llama
    con los mismos argumentos que `generate_conformer`.
    """
    dimorphite_dl = pytest.importorskip(
        "dimorphite_dl", reason="no instalado en este equipo; el pipeline lo declara y sigue"
    )

    def protonar(smiles: str) -> str:
        salida = dimorphite_dl.protonate_smiles(
            smiles, ph_min=7.4, ph_max=7.4, precision=1.0
        )
        # El pipeline se queda con el primero y descarta el resto.
        return salida[0] if salida else smiles

    esperados = len(_centros(uno))
    _no_colapsan(nombre, protonar(uno), protonar(otro), esperados)


@pytest.mark.parametrize(("nombre", "uno", "otro"), PARES)
def test_el_sdf_que_se_guarda_conserva_el_estereocentro(nombre, uno, otro):
    """El `conformer.sdf` de disco es lo que alimenta a Meeko.

    Se usa `_mol_to_sdf_string`, que es el serializador del proyecto, y no un
    `MolToMolBlock` cualquiera: si algún día ese writer cambia de opciones, esta
    prueba lo nota.
    """
    from chem.conformer import _mol_to_sdf_string

    def ida_y_vuelta(smiles: str) -> str:
        mol = Chem.AddHs(Chem.MolFromSmiles(smiles))
        parametros = AllChem.ETKDGv3()
        parametros.randomSeed = 42
        assert AllChem.EmbedMolecule(mol, parametros) == 0, f"{nombre}: no embebió"
        AllChem.MMFFOptimizeMolecule(mol)
        de_vuelta = Chem.MolFromMolBlock(_mol_to_sdf_string(mol, smiles), removeHs=True)
        assert de_vuelta is not None, f"{nombre}: el SDF guardado no se puede releer"
        return Chem.MolToSmiles(de_vuelta)

    esperados = len(_centros(uno))
    _no_colapsan(nombre, ida_y_vuelta(uno), ida_y_vuelta(otro), esperados)


# El par emblemático y el que originó la pregunta de los D-péptidos. Dos, y no
# los cuatro, porque cada molécula cuesta unos 37 s de subprocesos.
PARES_MEEKO = [p for p in PARES if p[0] in ("talidomida", "tri_alanina")]


@pytest.mark.slow
@pytest.mark.parametrize(("nombre", "uno", "otro"), PARES_MEEKO)
def test_la_ida_y_vuelta_por_meeko_conserva_el_estereocentro(nombre, uno, otro, tmp_path):
    """`mk_prepare_ligand` y `mk_export`, en subproceso, como en producción.

    Es el par que convierte el conformero al PDBQT que Vina lee y reconstruye
    después la pose desde el PDBQT que Vina escribe. Vina no puede epimerizar
    nada —sólo gira torsiones—, así que si la configuración se perdiera entre el
    conformero y la pose guardada, sería aquí.

    Se ejecutan los ejecutables de línea de comandos y no la API de Python
    a propósito: es lo que corre `vina_service`, y una diferencia entre las dos
    rutas es justo lo que esta prueba tiene que ver.
    """
    import subprocess
    import sys

    pytest.importorskip("meeko", reason="Meeko no instalado en este equipo")

    from chem.conformer import _mol_to_sdf_string

    def ida_y_vuelta(smiles: str, etiqueta: str) -> str:
        carpeta = tmp_path / etiqueta
        carpeta.mkdir()
        mol = Chem.AddHs(Chem.MolFromSmiles(smiles))
        parametros = AllChem.ETKDGv3()
        parametros.randomSeed = 42
        assert AllChem.EmbedMolecule(mol, parametros) == 0, f"{nombre}: no embebió"
        AllChem.MMFFOptimizeMolecule(mol)

        entrada = carpeta / "conformer.sdf"
        entrada.write_text(_mol_to_sdf_string(mol, smiles), encoding="utf-8")
        pdbqt = carpeta / "ligando.pdbqt"
        salida = carpeta / "pose.sdf"

        preparado = subprocess.run(
            [sys.executable, "-m", "meeko.cli.mk_prepare_ligand",
             "-i", str(entrada), "-o", str(pdbqt)],
            capture_output=True, text=True, timeout=300,
        )
        assert preparado.returncode == 0 and pdbqt.exists(), (
            f"{nombre}: mk_prepare_ligand falló — "
            f"{(preparado.stderr or preparado.stdout)[:300]}"
        )

        exportado = subprocess.run(
            [sys.executable, "-m", "meeko.cli.mk_export", str(pdbqt), "-s", str(salida)],
            capture_output=True, text=True, timeout=300,
        )
        assert exportado.returncode == 0 and salida.exists(), (
            f"{nombre}: mk_export falló — "
            f"{(exportado.stderr or exportado.stdout)[:300]}"
        )

        pose = Chem.MolFromMolFile(str(salida), removeHs=True)
        assert pose is not None, f"{nombre}: la pose exportada no se puede leer"
        return Chem.MolToSmiles(pose)

    esperados = len(_centros(uno))
    _no_colapsan(nombre, ida_y_vuelta(uno, "a"), ida_y_vuelta(otro, "b"), esperados)
