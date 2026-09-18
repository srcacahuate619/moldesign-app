"""
Recuperar la pose exacta de una piscina, o abstenerse. Nunca a medias.

EL HUECO QUE CIERRAN (ENS-04)
═══════════════════════════════════════════════════════════════════════════

El resultado agrupado del ensemble tiene `poses_file_path=None` a propósito: la
piscina mezcla archivos de K corridas, y apuntar al de la primera presentaría
coordenadas distintas de las poses entregadas. Desde el 2026-09-17 cada pose
conserva la ruta y el rank de SU corrida, así que se podría ir a buscar el
registro; la auditoría declaró eso insuficiente y con razón:

    «source_provenance NO certifica por sí sola correspondencia atómica ni
    integridad de bytes. Antes de recuperar SDF por rank de origen se exige
    comprobar hash del artefacto, identidad química y correspondencia
    geométrica con el bloque PDBQT entregado, sin conversión desde SMILES ni
    herencia de la pose de otra conformación.»

Una ruta y un número no demuestran nada: el archivo puede haber cambiado, el
exportador puede haber reordenado átomos, y un rank desplazado devuelve la
geometría de otra pose sin protestar.

Estas pruebas fijan las seis puertas y, sobre todo, fijan que cada una FALLA
cuando debe. Una puerta que nunca rechaza no es una puerta.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from core.models import DockingPose
from services.docking.pose_recovery import (
    PoseNoRecuperable,
    recuperar_pose_agrupada,
)

pytestmark = pytest.mark.asyncio


# ── Fixtures de formato: SDF V2000 y PDBQT, escritos a mano ───────────
#
# A mano y no con RDKit: lo que se comprueba es la lectura por columnas de un
# archivo real. Generarlos con la misma biblioteca que los lee probaría que la
# biblioteca es consistente consigo misma, no que el lector entiende el formato.

def _sdf(atomos: list[tuple[str, float, float, float]], nombre: str = "pose") -> str:
    cabecera = f"{nombre}\n     RDKit          3D\n\n"
    conteos = f"{len(atomos):3d}  0  0  0  0  0  0  0  0  0999 V2000\n"
    cuerpo = "".join(
        f"{x:10.4f}{y:10.4f}{z:10.4f} {simbolo:<3s} 0  0  0  0  0  0  0  0  0  0  0  0\n"
        for simbolo, x, y, z in atomos
    )
    return cabecera + conteos + cuerpo + "M  END\n"


def _pdbqt(coordenadas: list[tuple[float, float, float]], tipo: str = "C") -> str:
    lineas = ["ROOT"]
    for i, (x, y, z) in enumerate(coordenadas, start=1):
        lineas.append(
            f"ATOM  {i:5d}  C   UNL     1    "
            f"{x:8.3f}{y:8.3f}{z:8.3f}  0.00  0.00    +0.000 {tipo:<2s}"
        )
    lineas += ["ENDROOT", "TORSDOF 0"]
    return "\n".join(lineas) + "\n"


#: Tres átomos pesados, coordenadas que sobreviven al redondeo de los dos
#: formatos: el SDF escribe cuatro decimales y el PDBQT tres.
GEOMETRIA = [("C", 1.0, 2.0, 3.0), ("N", 4.5, -1.25, 0.5), ("O", -2.0, 0.0, 7.125)]
OTRA_GEOMETRIA = [("C", 1.0, 2.0, 3.0), ("N", 4.5, -1.25, 0.5), ("O", -2.0, 0.0, 9.0)]


@pytest.fixture
def almacen(monkeypatch, tmp_path):
    import utils.local_storage as ls

    monkeypatch.setattr(ls.settings, "local_data_dir", str(tmp_path / "data"))
    monkeypatch.setattr(ls.settings, "vina_temp_dir", str(tmp_path / "vina"))
    Path(ls.settings.vina_temp_dir).mkdir(parents=True, exist_ok=True)
    return ls


async def _escenario(almacen, *, poses=None, entrada=None, rank=2):
    """Un archivo de dos poses y la conformación de entrada, todo coherente."""
    poses = poses or [OTRA_GEOMETRIA, GEOMETRIA]
    entrada = entrada or GEOMETRIA
    archivo = "runs/docking/abc/7E2Y/huella/poses.sdf"
    conformero = "ligands/abc__c03/conformer.sdf"
    contenido = "".join(_sdf(p, f"pose{i}") + "$$$$\n" for i, p in enumerate(poses, 1))
    await almacen.write_text(archivo, contenido)
    await almacen.write_text(conformero, _sdf(entrada, "conformero") + "$$$$\n")

    pose = DockingPose(
        rank=1, affinity=-9.0, rmsd_lb=0.0, rmsd_ub=0.0,
        conformer_index=3,
        pdbqt_block=_pdbqt([(x, y, z) for _, x, y, z in poses[rank - 1]]),
        source_provenance={
            "rank": rank,
            "poses_file_path": archivo,
            "poses_file_sha256": hashlib.sha256(
                contenido.encode("utf-8")
            ).hexdigest(),
            "parsing_source": "sdf",
            "conversor_estructural": None,
            "ligand_input": {
                "conformer_path": conformero,
                "conformer_sha256": hashlib.sha256(
                    (_sdf(entrada, "conformero") + "$$$$\n").encode("utf-8")
                ).hexdigest(),
                "semilla_conformacional": 453,
            },
        },
    )
    return pose, archivo, conformero


# ── El camino que sí se puede demostrar ───────────────────────────────


async def test_recupera_el_registro_exacto_del_rank_de_origen(almacen):
    """La pose 2 del archivo, no la 1, y con la medida que lo respalda."""
    pose, archivo, conformero = await _escenario(almacen)

    recuperada = await recuperar_pose_agrupada(pose)

    assert recuperada.poses_file_path == archivo
    assert recuperada.rank_original == 2
    assert recuperada.conformer_index == 3
    assert recuperada.conformer_path == conformero
    assert recuperada.atomos_verificados == 3
    assert recuperada.max_desplazamiento_A < 0.001
    # El registro devuelto es el segundo, y se puede comprobar por su nombre.
    assert "pose2" in recuperada.sdf_record
    assert "pose1" not in recuperada.sdf_record


async def test_los_hidrogenos_del_sdf_no_rompen_la_correspondencia(almacen):
    """
    El PDBQT de Vina trae los pesados y los polares; el SDF puede traer todos.

    Un hidrógeno no polar sin coordenada en el bloque entregado NO invalida la
    correspondencia: lo que invalidaría es un átomo PESADO sin contrapartida.
    """
    con_hidrogenos = GEOMETRIA + [("H", 9.0, 9.0, 9.0), ("H", 8.0, 8.0, 8.0)]
    pose, _, _ = await _escenario(
        almacen, poses=[con_hidrogenos], entrada=con_hidrogenos, rank=1
    )
    pose.pdbqt_block = _pdbqt([(x, y, z) for _, x, y, z in GEOMETRIA])

    recuperada = await recuperar_pose_agrupada(pose)
    assert recuperada.atomos_verificados == 3


# ── Cada puerta, rechazando ───────────────────────────────────────────


async def test_sin_procedencia_no_se_busca_nada(almacen):
    pose = DockingPose(rank=1, affinity=-8.0, rmsd_lb=0, rmsd_ub=0)
    with pytest.raises(PoseNoRecuperable, match="no conserva procedencia"):
        await recuperar_pose_agrupada(pose)


@pytest.mark.parametrize("campo", [
    "rank", "poses_file_path", "poses_file_sha256",
])
async def test_procedencia_incompleta_se_rechaza_nombrando_el_campo(almacen, campo):
    pose, _, _ = await _escenario(almacen)
    pose.source_provenance[campo] = None

    with pytest.raises(PoseNoRecuperable, match=campo):
        await recuperar_pose_agrupada(pose)


@pytest.mark.parametrize("campo", ["conformer_path", "conformer_sha256"])
async def test_sin_identidad_de_la_entrada_se_rechaza(almacen, campo):
    pose, _, _ = await _escenario(almacen)
    pose.source_provenance["ligand_input"][campo] = None

    with pytest.raises(PoseNoRecuperable, match=campo):
        await recuperar_pose_agrupada(pose)


async def test_sin_bloque_pdbqt_no_hay_nada_contra_lo_que_comprobar(almacen):
    pose, _, _ = await _escenario(almacen)
    pose.pdbqt_block = None

    with pytest.raises(PoseNoRecuperable, match="bloque PDBQT"):
        await recuperar_pose_agrupada(pose)


async def test_un_archivo_que_cambio_se_rechaza(almacen):
    """El hash es lo que convierte «el registro 2» en una afirmación."""
    pose, archivo, _ = await _escenario(almacen)
    await almacen.write_text(
        archivo,
        "".join(_sdf(p, f"pose{i}") + "$$$$\n"
                for i, p in enumerate([GEOMETRIA, OTRA_GEOMETRIA], 1)),
    )

    with pytest.raises(PoseNoRecuperable, match="archivo de poses cambió"):
        await recuperar_pose_agrupada(pose)


async def test_una_entrada_que_cambio_se_rechaza(almacen):
    pose, _, conformero = await _escenario(almacen)
    await almacen.write_text(conformero, _sdf(OTRA_GEOMETRIA) + "$$$$\n")

    with pytest.raises(PoseNoRecuperable, match="entrada cambió"):
        await recuperar_pose_agrupada(pose)


async def test_un_archivo_ausente_se_rechaza_sin_inventar(almacen):
    pose, archivo, _ = await _escenario(almacen)
    await almacen.delete(archivo)

    with pytest.raises(PoseNoRecuperable, match="No se puede leer"):
        await recuperar_pose_agrupada(pose)


async def test_un_rank_fuera_del_archivo_se_rechaza(almacen):
    pose, _, _ = await _escenario(almacen)
    pose.source_provenance["rank"] = 9

    with pytest.raises(PoseNoRecuperable, match="fuera del archivo"):
        await recuperar_pose_agrupada(pose)


async def test_otra_molecula_en_el_registro_se_rechaza(almacen):
    """
    Identidad química contra la conformación que se acopló, no contra un SMILES.

    Comparar con un SMILES obligaría a reconstruir la molécula desde texto, que
    es precisamente la conversión que ENS-04 prohíbe. La entrada real está en
    disco y su hash ya se verificó.
    """
    distinta = [("C", 1.0, 2.0, 3.0), ("C", 4.5, -1.25, 0.5), ("O", -2.0, 0.0, 7.125)]
    pose, _, _ = await _escenario(almacen, poses=[distinta], entrada=GEOMETRIA, rank=1)

    with pytest.raises(PoseNoRecuperable, match="átomos pesados del registro"):
        await recuperar_pose_agrupada(pose)


async def test_un_rank_que_apunta_a_otra_geometria_se_rechaza(almacen):
    """
    La puerta que de verdad cierra ENS-04.

    Mismo archivo, misma molécula, hashes correctos: sólo el rank está
    desplazado. El resultado sería la pose equivocada con procedencia perfecta,
    y es exactamente el fallo que no se puede detectar con una ruta y un número.
    """
    pose, _, _ = await _escenario(almacen, rank=2)
    pose.source_provenance["rank"] = 1     # apunta a OTRA_GEOMETRIA

    with pytest.raises(PoseNoRecuperable, match="no aparece en el registro"):
        await recuperar_pose_agrupada(pose)


async def test_un_atomo_pesado_sin_contrapartida_se_rechaza(almacen):
    """El registro no puede tener pesados que el bloque entregado no tenga."""
    pose, _, _ = await _escenario(almacen, poses=[GEOMETRIA], entrada=GEOMETRIA, rank=1)
    pose.pdbqt_block = _pdbqt([(x, y, z) for _, x, y, z in GEOMETRIA[:2]])

    with pytest.raises(PoseNoRecuperable, match="átomo\\(s\\) pesado\\(s\\) sin"):
        await recuperar_pose_agrupada(pose)


async def test_un_macrociclo_no_queda_irrecuperable_por_sus_pseudoatomos(almacen):
    """
    Los pseudo-átomos de pegado no existen en la molécula, ni en el SDF.

    Meeko los inserta al abrir un macrociclo para hacerlo flexible. Si se les
    exigiera contrapartida en el registro, TODA pose de un ligando macrocíclico
    quedaría declarada irrecuperable: una abstención masiva por una convención de
    formato, no por una duda científica. Se descartan por su tipo AutoDock —la
    única cosa que se lee de las columnas 77-78— y se informa cuántos.
    """
    pose, _, _ = await _escenario(almacen, poses=[GEOMETRIA], entrada=GEOMETRIA, rank=1)
    bloque = _pdbqt([(x, y, z) for _, x, y, z in GEOMETRIA])
    pegado = (
        "ATOM      9  G   UNL     1     -50.000 -50.000 -50.000  "
        "0.00  0.00    +0.000 G \n"
    )
    pose.pdbqt_block = bloque.replace("ENDROOT", pegado + "ENDROOT")

    recuperada = await recuperar_pose_agrupada(pose)
    assert recuperada.atomos_verificados == 3
    assert recuperada.pseudoatomos_de_pegado == 1


async def test_un_sdf_v3000_se_rechaza_en_vez_de_interpretarse(almacen):
    """Un formato que este lector no cubre se declara, no se adivina."""
    pose, archivo, _ = await _escenario(almacen, rank=1)
    contenido = (
        "pose1\n     RDKit          3D\n\n"
        "  0  0  0     0  0            999 V3000\nM  END\n$$$$\n"
    )
    await almacen.write_text(archivo, contenido)
    pose.source_provenance["poses_file_sha256"] = hashlib.sha256(
        contenido.encode("utf-8")
    ).hexdigest()

    with pytest.raises(PoseNoRecuperable, match="V2000"):
        await recuperar_pose_agrupada(pose)


async def test_la_tolerancia_no_se_amplia_para_que_pase_un_caso(almacen):
    """
    Media décima de ångström NO es la misma pose.

    La tolerancia cubre el redondeo entre formatos —tres decimales frente a
    cuatro—, no diferencias conformacionales. Este caso documenta dónde está la
    frontera: si alguien la mueve para «arreglar» un rechazo, esta prueba cae.
    """
    desplazada = [(x, y, z + 0.05) for _, x, y, z in GEOMETRIA]
    pose, _, _ = await _escenario(almacen, poses=[GEOMETRIA], entrada=GEOMETRIA, rank=1)
    pose.pdbqt_block = _pdbqt(desplazada)

    with pytest.raises(PoseNoRecuperable, match="no aparece en el registro"):
        await recuperar_pose_agrupada(pose)


# ── De punta a punta: la piscina real ─────────────────────────────────


async def test_una_pose_de_una_piscina_real_se_recupera(almacen):
    """
    El ensemble completo: dos conformaciones, dos archivos, una piscina.

    Cada pose entregada tiene que poder recuperar SU registro, del archivo de SU
    corrida, sin que la renumeración de la piscina desplace nada.
    """
    from core.models import DockingResult
    from services.docking.ensemble import run_ensemble_docking

    geometrias = {0: OTRA_GEOMETRIA, 1: GEOMETRIA}
    conformeros = []
    for indice, geometria in geometrias.items():
        ruta = f"ligands/xyz__c{indice:02d}/conformer.sdf"
        contenido = _sdf(geometria, f"conf{indice}") + "$$$$\n"
        await almacen.write_text(ruta, contenido)
        conformeros.append({
            "indice": indice,
            "smiles_hash": f"xyz__c{indice:02d}",
            "conformer_path": ruta,
            "conformer_sha256": hashlib.sha256(contenido.encode("utf-8")).hexdigest(),
            "semilla": 42 + indice,
        })

    async def acoplar(smiles_hash: str, smiles: str | None = None):
        indice = int(smiles_hash.split("__c")[1])
        geometria = geometrias[indice]
        archivo = f"runs/docking/{smiles_hash}/7E2Y/h/poses.sdf"
        await almacen.write_text(archivo, _sdf(geometria, f"p{indice}") + "$$$$\n")
        return DockingResult(
            best_affinity=-8.0 - indice,
            poses=[DockingPose(
                rank=1, affinity=-8.0 - indice, rmsd_lb=0, rmsd_ub=0,
                pdbqt_block=_pdbqt([(x, y, z) for _, x, y, z in geometria]),
            )],
            poses_file_path=archivo,
            parsing_source="sdf",
        )

    piscina = await run_ensemble_docking(
        smiles="CCO", conformeros=conformeros, num_poses=2, dock_una=acoplar
    )

    assert piscina.poses_file_path is None, "la piscina no puede citar un solo archivo"
    for pose in piscina.poses:
        recuperada = await recuperar_pose_agrupada(pose)
        assert recuperada.conformer_index == pose.conformer_index
        assert f"__c{pose.conformer_index:02d}" in recuperada.poses_file_path
        assert f"p{pose.conformer_index}" in recuperada.sdf_record
        assert recuperada.max_desplazamiento_A < 0.001
