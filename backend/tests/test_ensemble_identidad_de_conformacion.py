"""
La conformación que Vina recibe es la que el ensemble dice que recibió.

EL FALLO QUE PRUEBAN (ENS-05, medido el 2026-09-17)
═══════════════════════════════════════════════════════════════════════════

`_prepare_ligand_pdbqt` recibe el hash DERIVADO de cada conformación del
ensemble —`<hash>__c07`— y, antes de buscar su `.sdf`, intentaba «mejorar» la
ruta: revalidaba el SMILES y, si existía el conformero del hash canónico, lo
usaba en su lugar. En una corrida de ensemble ese archivo existe SIEMPRE —es la
conformación 0, que el generador escribe primero—, así que las K corridas de
Vina recibían la MISMA geometría de entrada.

Es decir: las K corridas partían de la misma geometría. La diversidad
conformacional que el ensemble existe para aportar no estaba, y cada pose de la
piscina declaraba venir de una conformación distinta, así que el
`conformer_index` era falso y la lectura que el ensemble existe para permitir
—«la misma solución encontrada desde puntos de partida distintos»— era
imposible, porque el punto de partida era uno solo.

No se midió si las K salidas eran idénticas entre sí: `vina_cpu` vale 0 por
defecto y la búsqueda paralela de Vina no garantiza reproducibilidad bit a bit,
así que no se afirma.

Medido antes del arreglo, con un ensemble real de tres conformaciones de
benceno y Meeko instrumentado:

    SDF de cada conformación    d18bd2789cc3  79e5e727d44e  14609fa750c7
    SDF que recibió Meeko       d18bd2789cc3  d18bd2789cc3  d18bd2789cc3

No es una hipótesis de concurrencia ni una colisión de hashes: es sustitución
determinista, y sólo ocurre cuando el hash post-protonación coincide con el del
validador —el caso de cualquier ligando neutro—, así que colapsaba el ensemble
en silencio para unas moléculas y no para otras.

LO QUE ESTAS PRUEBAS FIJAN
═══════════════════════════════════════════════════════════════════════════

1. Cada conformación se prepara desde SU propio `.sdf`.
2. El `.pdbqt` preparado declara de qué SDF salió, y ese registro se comprueba
   antes de reutilizarlo. Sin esto el arreglo no llegaría a los discos donde ya
   hay un `vina_input.pdbqt` construido desde la conformación equivocada: la
   caché lo habría devuelto igual.
3. Una conformación del ensemble sin su SDF NO se sustituye por otra ni se
   regenera desde el SMILES. Se aborta diciendo qué falta.
4. La huella de caché del docking distingue la geometría del ligando, no sólo
   el hash de la molécula.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from core.exceptions import DockingFailed
from utils.file_handlers import StoragePath

pytestmark = pytest.mark.asyncio

#: Neutro a propósito: es el caso en el que el hash post-protonación coincide
#: con el del validador, que es el que activaba la sustitución.
BENCENO = "c1ccccc1"

PDBQT_MINIMO = (
    "ROOT\n"
    "ATOM      1  C   UNL     1       0.000   0.000   0.000  0.00  0.00    +0.000 C \n"
    "ENDROOT\n"
    "TORSDOF 0\n"
)


@pytest.fixture
def almacen(monkeypatch, tmp_path):
    """Datos y temporales de Vina aislados en el `tmp_path` de la prueba."""
    import utils.local_storage as ls

    monkeypatch.setattr(ls.settings, "local_data_dir", str(tmp_path / "data"))
    monkeypatch.setattr(ls.settings, "vina_temp_dir", str(tmp_path / "vina"))
    Path(ls.settings.vina_temp_dir).mkdir(parents=True, exist_ok=True)
    return ls


@pytest.fixture
def meeko(monkeypatch):
    """
    Sustituye `mk_prepare_ligand` por un doble que ANOTA el SDF que recibió.

    No se simula Meeko para ahorrar tiempo: se simula para poder ver la entrada.
    El defecto era invisible desde el resultado —los tres `.pdbqt` eran válidos—
    y sólo se ve mirando qué archivo entró en cada llamada.
    """
    import services.docking.vina_service as vs

    recibidos: list[str] = []

    class ProcesoFalso:
        returncode = 0

        async def communicate(self):
            return (b"", b"")

    async def ejecutar(*command, **kwargs):
        argumentos = list(command)
        entrada = Path(argumentos[argumentos.index("-i") + 1])
        salida = Path(argumentos[argumentos.index("-o") + 1])
        recibidos.append(
            hashlib.sha256(entrada.read_bytes()).hexdigest()
        )
        salida.write_text(PDBQT_MINIMO, encoding="utf-8")
        return ProcesoFalso()

    monkeypatch.setattr(vs.asyncio, "create_subprocess_exec", ejecutar)
    monkeypatch.setattr(vs, "_resolve_executable", lambda ruta: "meeko-doble")
    return recibidos


async def _ensemble_de_tres(almacen):
    """Un ensemble real: tres conformaciones distintas, escritas en disco."""
    from chem.conformer_ensemble import generate_conformer_ensemble

    resultado = await generate_conformer_ensemble(BENCENO, 3)
    assert resultado["conformers_generated"] == 3, "el generador no produjo el ensemble"

    huellas = {}
    for conformero in resultado["conformers"]:
        datos = await almacen.read_bytes(conformero["conformer_path"])
        huellas[conformero["indice"]] = hashlib.sha256(datos).hexdigest()
    assert len(set(huellas.values())) == 3, (
        "las tres conformaciones salieron con la misma geometría: el ensemble "
        "no está variando nada y el resto de la prueba no mediría el defecto"
    )
    return resultado, huellas


# ── 1. Cada conformación entra con su propia geometría ────────────────


async def test_cada_conformacion_se_prepara_desde_su_propio_sdf(almacen, meeko):
    """El defecto entero, reproducido de punta a punta."""
    import services.docking.vina_service as vs

    resultado, huellas = await _ensemble_de_tres(almacen)

    for conformero in resultado["conformers"]:
        await vs._prepare_ligand_pdbqt(
            conformero["smiles_hash"], smiles=BENCENO, target_pdb_id="PRUEBA"
        )

    esperado = [huellas[0], huellas[1], huellas[2]]
    assert meeko == esperado, (
        "Meeko no recibió la conformación que se le pidió preparar.\n"
        f"  pedido:   {[h[:12] for h in esperado]}\n"
        f"  recibido: {[h[:12] for h in meeko]}\n"
        "Si las tres son iguales, la búsqueda por SMILES volvió a sustituir el "
        "conformero derivado por el de la conformación 0 y el ensemble está "
        "acoplando la misma geometría K veces."
    )


async def test_el_camino_de_una_sola_conformacion_no_cambia(almacen, meeko):
    """K=1 sigue preparándose desde el conformero del hash canónico."""
    import services.docking.vina_service as vs
    from chem.conformer_ensemble import generate_conformer_ensemble

    resultado = await generate_conformer_ensemble(BENCENO, 1)
    base = resultado["conformers"][0]
    esperada = hashlib.sha256(
        await almacen.read_bytes(base["conformer_path"])
    ).hexdigest()

    objeto = await vs._prepare_ligand_pdbqt(
        base["smiles_hash"], smiles=BENCENO, target_pdb_id="PRUEBA"
    )

    assert meeko == [esperada]
    assert objeto == StoragePath.ligand_vina_input(resultado["smiles_hash"])


# ── 2. El PDBQT en caché declara de qué SDF salió ─────────────────────


async def test_el_pdbqt_declara_y_comprueba_su_conformero_de_origen(almacen, meeko):
    """La segunda llamada reutiliza la caché SÓLO porque puede demostrarla."""
    import services.docking.vina_service as vs

    resultado, huellas = await _ensemble_de_tres(almacen)
    conformero = resultado["conformers"][1]

    objeto = await vs._prepare_ligand_pdbqt(
        conformero["smiles_hash"], smiles=BENCENO, target_pdb_id="PRUEBA"
    )

    procedencia = StoragePath.ligand_vina_input_provenance(conformero["smiles_hash"])
    assert await almacen.exists(procedencia), (
        "el PDBQT preparado no dejó registro de su conformero de origen"
    )
    import json

    registro = json.loads(await almacen.read_text(procedencia))
    assert registro["conformer_object"] == conformero["conformer_path"]
    assert registro["conformer_sha256"] == huellas[1]
    assert registro["pdbqt_sha256"] == hashlib.sha256(
        await almacen.read_bytes(objeto)
    ).hexdigest()

    # Segunda llamada: no vuelve a preparar nada.
    await vs._prepare_ligand_pdbqt(
        conformero["smiles_hash"], smiles=BENCENO, target_pdb_id="PRUEBA"
    )
    assert len(meeko) == 1, "la caché verificada volvió a invocar a Meeko"


async def test_un_pdbqt_heredado_sin_procedencia_se_vuelve_a_preparar(almacen, meeko):
    """
    El arreglo tiene que llegar a los discos ya contaminados.

    Un `vina_input.pdbqt` escrito antes de este contrato pudo construirse desde
    la conformación 0 aunque viva en el directorio de la 2. Es indistinguible de
    uno correcto, así que la única salida honesta es volver a prepararlo.
    """
    import services.docking.vina_service as vs

    resultado, huellas = await _ensemble_de_tres(almacen)
    conformero = resultado["conformers"][2]

    # Caché heredada: el PDBQT existe y no hay registro de procedencia.
    await almacen.write_text(
        StoragePath.ligand_vina_input(conformero["smiles_hash"]), PDBQT_MINIMO
    )

    await vs._prepare_ligand_pdbqt(
        conformero["smiles_hash"], smiles=BENCENO, target_pdb_id="PRUEBA"
    )

    assert meeko == [huellas[2]], (
        "un PDBQT sin procedencia se reutilizó: el arreglo no alcanza a las "
        "instalaciones donde ya hay uno construido desde otra conformación"
    )


async def test_un_pdbqt_de_otra_geometria_no_se_reutiliza(almacen, meeko):
    """Si el SDF cambió, el PDBQT que salió del anterior ya no lo representa."""
    import services.docking.vina_service as vs

    resultado, huellas = await _ensemble_de_tres(almacen)
    conformero = resultado["conformers"][1]

    await vs._prepare_ligand_pdbqt(
        conformero["smiles_hash"], smiles=BENCENO, target_pdb_id="PRUEBA"
    )
    assert len(meeko) == 1

    # La geometría de esa conformación se sustituye por otra distinta.
    otra = await almacen.read_bytes(resultado["conformers"][2]["conformer_path"])
    await almacen.write_bytes(otra, conformero["conformer_path"])

    await vs._prepare_ligand_pdbqt(
        conformero["smiles_hash"], smiles=BENCENO, target_pdb_id="PRUEBA"
    )
    assert meeko == [huellas[1], huellas[2]], (
        "el PDBQT de la geometría anterior se reutilizó para una nueva"
    )


# ── 3. Nada se sustituye ni se regenera desde el SMILES ───────────────


async def test_una_conformacion_sin_sdf_no_se_sustituye_por_otra(almacen, meeko):
    """
    Abortar es la única salida correcta.

    Regenerar desde el SMILES daría la conformación 0 otra vez —misma semilla,
    mismo ETKDG— escrita en la ruta de la 2. Sustituirla por la 0 es el defecto
    original. Ambas producirían un `conformer_index` falso.
    """
    import services.docking.vina_service as vs
    from chem.conformer_ensemble import hash_de_conformero

    resultado, _ = await _ensemble_de_tres(almacen)
    ausente = hash_de_conformero(resultado["smiles_hash"], 7)

    with pytest.raises(DockingFailed) as fallo:
        await vs._prepare_ligand_pdbqt(
            ausente, smiles=BENCENO, target_pdb_id="PRUEBA"
        )

    assert "__c07" in str(fallo.value) or ausente in str(fallo.value)
    assert meeko == [], (
        "se preparó un PDBQT para una conformación que no tiene geometría: "
        "sea por sustitución o por regeneración, el resultado es una pose "
        "atribuida a un punto de partida que nunca existió"
    )


async def test_la_busqueda_por_smiles_solo_actua_si_falta_el_conformero(almacen, meeko):
    """
    El motivo por el que la búsqueda existe se conserva.

    Servía para el desajuste histórico de hash pre/post-protonación: el llamante
    pide un hash y el conformero está escrito en otro. Eso sigue funcionando
    —para hashes canónicos— porque sólo actúa cuando el pedido NO tiene SDF.
    """
    import services.docking.vina_service as vs
    from chem.validator import validate_smiles_or_raise

    validado = validate_smiles_or_raise(BENCENO)
    contenido = (
        "benceno\n     RDKit          3D\n\n"
        "  0  0  0  0  0  0  0  0  0  0999 V2000\nM  END\n$$$$\n"
    )
    await almacen.write_text(
        StoragePath.ligand_conformer(validado.smiles_hash), contenido
    )
    huella = hashlib.sha256(contenido.encode("utf-8")).hexdigest()

    otro_hash = "0" * 64
    await vs._prepare_ligand_pdbqt(otro_hash, smiles=BENCENO, target_pdb_id="PRUEBA")

    assert meeko == [huella], (
        "la búsqueda por SMILES dejó de rescatar el desajuste de hash que la "
        "justificaba"
    )


# ── 4. La huella de caché distingue la geometría ──────────────────────


async def test_la_huella_de_cache_incluye_la_geometria_del_ligando(almacen):
    """
    Dos geometrías distintas no pueden compartir un resultado de docking.

    El caché de docking vive en memoria y se indexa por `smiles_hash`, que en el
    ensemble ES distinto por conformación. La huella añade la identidad del SDF
    para que un cambio de geometría bajo el mismo hash tampoco se reutilice:
    es el mismo argumento por el que la huella ya incluía receptor y caja.
    """
    import services.docking.vina_service as vs

    resultado, _ = await _ensemble_de_tres(almacen)
    primera = resultado["conformers"][0]
    segunda = resultado["conformers"][1]

    comun = dict(
        receptor_sha256="a" * 64,
        target_chain="A",
        center=(0.0, 0.0, 0.0),
        size=(20.0, 20.0, 20.0),
        hotspots=None,
        docking_engine="vina",
        exhaustiveness=8,
        num_poses=9,
        seed=42,
    )
    huella_a = vs._docking_cache_fingerprint(
        ligand_input_sha256=await vs._huella_del_conformero(primera["smiles_hash"]),
        **comun,
    )
    huella_b = vs._docking_cache_fingerprint(
        ligand_input_sha256=await vs._huella_del_conformero(segunda["smiles_hash"]),
        **comun,
    )
    assert huella_a != huella_b, (
        "dos conformaciones distintas producen la misma huella de caché"
    )
    assert huella_a == vs._docking_cache_fingerprint(
        ligand_input_sha256=await vs._huella_del_conformero(primera["smiles_hash"]),
        **comun,
    ), "la huella dejó de ser determinista"


async def test_sin_conformero_en_disco_la_huella_lo_declara(almacen):
    """Un dato que no se puede leer se declara ausente, no se inventa."""
    import services.docking.vina_service as vs

    assert await vs._huella_del_conformero("f" * 64) is None


# ── 5. La piscina conserva QUÉ geometría se acopló ────────────────────


async def test_cada_pose_conserva_la_identidad_de_la_geometria_que_se_acoplo(almacen):
    """
    `conformer_index` con qué comprobarlo.

    Un índice es una etiqueta: dice de qué conformación se DICE que salió la
    pose. Es justamente lo que hizo invisible el defecto durante toda su vida.
    Ahora cada pose conserva además la ruta y el SHA-256 del `.sdf` que entró a
    Vina, así que la atribución se puede comprobar en vez de creerse.
    """
    from core.models import DockingPose, DockingResult
    from services.docking.ensemble import run_ensemble_docking

    resultado, huellas = await _ensemble_de_tres(almacen)
    conformeros = resultado["conformers"]
    for conformero in conformeros:
        assert conformero["conformer_sha256"] == huellas[conformero["indice"]], (
            "el generador dejó de declarar la huella de la geometría que escribió"
        )

    async def acoplar(smiles_hash: str, smiles: str | None = None):
        indice = 0 if "__c" not in smiles_hash else int(smiles_hash.split("__c")[1])
        return DockingResult(
            best_affinity=-8.0 - indice,
            poses=[DockingPose(rank=1, affinity=-8.0 - indice, rmsd_lb=0, rmsd_ub=0)],
            poses_file_path=f"runs/{smiles_hash}/poses.sdf",
            parsing_source="sdf",
        )

    piscina = await run_ensemble_docking(
        smiles=BENCENO, conformeros=conformeros, num_poses=3, dock_una=acoplar
    )

    for pose in piscina.poses:
        entrada = pose.source_provenance["ligand_input"]
        assert entrada["conformer_sha256"] == huellas[pose.conformer_index], (
            f"la pose atribuida a la conformación {pose.conformer_index} no "
            "conserva la huella de esa geometría"
        )
        assert entrada["conformer_path"] == (
            conformeros[pose.conformer_index]["conformer_path"]
        )
    # Tres geometrías distintas, tres huellas distintas: si el defecto volviera,
    # las tres poses declararían la misma.
    assert len({p.source_provenance["ligand_input"]["conformer_sha256"]
                for p in piscina.poses}) == 3
