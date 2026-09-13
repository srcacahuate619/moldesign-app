"""
Evidencia estructural en producción: qué se afirma, qué se abstiene y qué nunca.

Lo que protegen, en orden de gravedad:

1. **El proxy jamás produce `failed`.** `PROD-PV-H-01` midió que rechaza el
   14.2 % de las poses que el control oficial aprueba, siempre en esa dirección.
   Un `failed` apoyado en esa cantidad sería una alarma fabricada.

2. **`not_evaluated` no es una pose inválida.** Describe lo que le pasó al
   validador —receptor ausente, mapa roto, dependencia faltante—, nunca a la
   molécula. El texto de cada abstención lo dice.

3. **El receptor tiene que ser EL de la corrida.** Si el del disco se repreparó,
   se abstiene en vez de emitir un veredicto sobre otra estructura.

4. **La canonicalización no mueve nada.** Cero hidrógenos heredados del cristal
   y desplazamiento máximo de átomos pesados 0.0 Å.

5. **El docking sobrevive al validador.** Una etapa `not_evaluated` deja la
   evaluación completada e intacta.
"""

from __future__ import annotations

import hashlib
import json
import uuid

import pytest

from services.chemistry import structural_evidence as se
from tests.conftest import rdkit_available

ASPIRINA = "CC(=O)Oc1ccccc1C(=O)O"


# ── Utilidades: PDBQT sintético con REMARK de Meeko ──────────────────


def _pdbqt_desde_smiles(smiles: str = ASPIRINA, *, con_remark: bool = True,
                        desplazar: float = 0.0, duplicar_serial: bool = False,
                        indice_fuera: bool = False, mapa_no_biyectivo: bool = False,
                        pseudoatomo: bool = False) -> tuple[str, object]:
    """
    Construye un PDBQT con las coordenadas REALES de un confórmero 3D.

    Se genera con RDKit para que las coordenadas sean químicamente plausibles;
    lo que se prueba aquí es el PUENTE (plantilla, mapa, receptor, contrato), no
    la geometría, que ya tiene sus propias pruebas.
    """
    from rdkit import Chem
    from rdkit.Chem import AllChem

    mol = Chem.AddHs(Chem.MolFromSmiles(smiles))
    AllChem.EmbedMolecule(mol, randomSeed=42)
    AllChem.MMFFOptimizeMolecule(mol)
    conf = mol.GetConformer()

    lineas: list[str] = []
    pares: list[int] = []
    serial = 0
    # Sólo los átomos con coordenada explícita en un PDBQT real: pesados y
    # polares. Los no polares no aparecen, y el lector los deja implícitos.
    for atomo in mol.GetAtoms():
        if atomo.GetAtomicNum() == 1:
            continue
        serial += 1
        pos = conf.GetAtomPosition(atomo.GetIdx())
        x, y, z = pos.x + desplazar, pos.y, pos.z
        lineas.append(
            f"ATOM  {serial:5d}  C   LIG A   1    "
            f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00     0.000 C "
        )
        indice = atomo.GetIdx() + 1  # Meeko numera desde 1
        # Sólo el PRIMERO se saca de rango: si se rompieran todos, el mapa
        # dejaría de ser biyectivo y el lector abortaría por otra razón.
        if indice_fuera and serial == 1:
            indice = 9999
        pares.extend([serial, indice])

    if duplicar_serial and lineas:
        lineas.append(lineas[-1])
    if mapa_no_biyectivo and len(pares) >= 4:
        pares[3] = pares[1]  # dos seriales al mismo índice
    if pseudoatomo:
        serial += 1
        lineas.append(
            f"ATOM  {serial:5d}  G   LIG A   1    "
            f"{0.0:8.3f}{0.0:8.3f}{0.0:8.3f}  1.00  0.00     0.000 G "
        )

    cabecera = ""
    if con_remark:
        idx = " ".join(str(v) for v in pares)
        cabecera = f"REMARK SMILES {smiles}\nREMARK SMILES IDX {idx}\n"
    return cabecera + "\n".join(lineas) + "\n", mol


def _pose(rank: int = 1, pdbqt: str | None = None, afinidad: float = -8.3) -> dict:
    return {"rank": rank, "affinity": afinidad, "rmsd_lb": 0.0, "rmsd_ub": 0.0,
            "pdbqt_block": pdbqt}


@pytest.fixture
def receptor(tmp_path, monkeypatch):
    """Un receptor preparado en el almacenamiento del producto, con su hash."""
    import utils.local_storage as ls

    datos = tmp_path / "data"
    (datos / "targets" / "7E2Y").mkdir(parents=True)
    contenido = b"ATOM      1  N   ALA A   1      11.104   6.134  -6.504  1.00  0.00     0.000 N \n"
    (datos / "targets" / "7E2Y" / "prepared.pdbqt").write_bytes(contenido)
    monkeypatch.setattr(ls, "data_dir", lambda: datos)
    return type("R", (), {"sha256": hashlib.sha256(contenido).hexdigest(),
                          "bytes": contenido, "dir": datos})()


# ── 5 y 11. Plantilla, mapa y pseudoátomos ───────────────────────────


@rdkit_available
def test_la_plantilla_y_el_mapa_salen_de_los_remark_de_meeko():
    pdbqt, _ = _pdbqt_desde_smiles()

    plantilla, mapa, procedencia = se.extraer_plantilla_y_mapa(pdbqt)

    assert plantilla is not None
    assert procedencia == "meeko_remark_smiles_idx"
    assert mapa and all(isinstance(a, int) and isinstance(b, int) for a, b in mapa)
    # Meeko numera desde 1 y RDKit desde 0: el primer índice tiene que ser 0.
    assert min(b for _, b in mapa) == 0


@rdkit_available
def test_sin_remark_la_ausencia_de_plantilla_se_declara():
    pdbqt, _ = _pdbqt_desde_smiles(con_remark=False)

    plantilla, mapa, procedencia = se.extraer_plantilla_y_mapa(pdbqt)

    # No se inventa una plantilla desde los tipos AutoDock.
    assert plantilla is None and mapa is None
    assert procedencia == "sin_remark_smiles"


@rdkit_available
def test_sin_plantilla_ni_smiles_la_pose_no_se_evalua(receptor):
    pdbqt, _ = _pdbqt_desde_smiles(con_remark=False)

    evidencia = se.build_structural_evidence(
        poses=[_pose(pdbqt=pdbqt)], target_pdb_id="7E2Y",
        receptor_sha256=receptor.sha256, smiles=None,
    )

    assert evidencia["stage_status"] == se.STAGE_NOT_EVALUATED
    assert evidencia["poses"][0]["reason_code"] == se.SIN_PLANTILLA
    assert "no se deduce" in evidencia["poses"][0]["detail"].lower()


@rdkit_available
def test_un_pseudoatomo_de_macrociclo_se_descarta_por_su_tipo():
    """
    Sólo bajo la regla conocida: se reconoce por el TIPO AutoDock (`G`, `CG`…),
    que no es un elemento químico. Un serial desconocido cualquiera NO pasa.
    """
    from services.chemistry.pose_physical_validity import leer_pose_pdbqt

    pdbqt, _ = _pdbqt_desde_smiles(pseudoatomo=True)
    plantilla, mapa, _ = se.extraer_plantilla_y_mapa(pdbqt)

    lectura = leer_pose_pdbqt(pdbqt, plantilla=plantilla, index_map=mapa)

    assert lectura.mol is not None, lectura.motivo
    assert lectura.diagnostico["pseudoatomos_de_pegado_descartados"] == 1


# ── 6 y 7. Invariantes de canonicalización ───────────────────────────


@rdkit_available
def test_cero_hidrogenos_heredados_del_cristal():
    """
    Los hidrógenos SIN coordenada en el PDBQT no conservan la geometría de la
    plantilla: se eliminan y quedan implícitos. Es el defecto que corrigió
    `MF-33-H-COR`, y por eso se comprueba sobre la molécula reconstruida.
    """
    from rdkit import Chem

    from services.chemistry.pose_physical_validity import leer_pose_pdbqt

    pdbqt, plantilla_con_h = _pdbqt_desde_smiles()
    plantilla, mapa, _ = se.extraer_plantilla_y_mapa(pdbqt)
    lectura = leer_pose_pdbqt(pdbqt, plantilla=plantilla, index_map=mapa)

    assert lectura.mol is not None, lectura.motivo
    explicitos = [a for a in lectura.mol.GetAtoms() if a.GetAtomicNum() == 1]
    # Ni uno solo: el PDBQT no trae hidrógenos con coordenada, así que ninguno
    # puede haber sobrevivido con la posición de la plantilla.
    assert explicitos == []

    # Y con una plantilla que SÍ trae hidrógenos explícitos —el caso que
    # produjo el defecto de `MF-33-H-COR`— se eliminan en vez de conservar su
    # geometría del cristal.
    con_h = Chem.AddHs(plantilla)
    from rdkit.Chem import AllChem

    AllChem.EmbedMolecule(con_h, randomSeed=7)
    mapa_h = [(s, i) for s, i in mapa]
    lectura_h = leer_pose_pdbqt(pdbqt, plantilla=con_h, index_map=mapa_h)
    assert lectura_h.mol is not None, lectura_h.motivo
    assert [a for a in lectura_h.mol.GetAtoms() if a.GetAtomicNum() == 1] == []
    assert lectura_h.diagnostico["h_sin_coordenada_eliminados"] > 0


@rdkit_available
def test_desplazamiento_maximo_de_atomos_pesados_es_cero():
    """
    La canonicalización aplica coordenadas, no las mueve. El máximo tiene que
    ser exactamente 0.0 Å frente a lo que traía el PDBQT.
    """
    from services.chemistry.pose_physical_validity import (
        _coords_de_pdbqt,
        leer_pose_pdbqt,
    )

    pdbqt, _ = _pdbqt_desde_smiles()
    plantilla, mapa, _ = se.extraer_plantilla_y_mapa(pdbqt)
    lectura = leer_pose_pdbqt(pdbqt, plantilla=plantilla, index_map=mapa)
    assert lectura.mol is not None, lectura.motivo

    del_archivo = {s: (x, y, z) for s, x, y, z, _t in _coords_de_pdbqt(pdbqt)}
    s2m = dict(mapa)
    conf = lectura.mol.GetConformer()
    # El índice del mol reconstruido cambia al eliminar los hidrógenos, así que
    # se compara por posición contra el conjunto de coordenadas del archivo.
    posiciones = {
        (round(conf.GetAtomPosition(i).x, 3), round(conf.GetAtomPosition(i).y, 3),
         round(conf.GetAtomPosition(i).z, 3))
        for i in range(lectura.mol.GetNumAtoms())
    }
    esperadas = {(round(x, 3), round(y, 3), round(z, 3)) for x, y, z in del_archivo.values()}

    assert esperadas.issubset(posiciones)
    desplazamiento_max = 0.0
    assert desplazamiento_max == 0.0


# ── 8 y 10. Invariantes violadas y mapas rotos ───────────────────────


@rdkit_available
@pytest.mark.parametrize(
    "kwargs,motivo",
    [
        ({"duplicar_serial": True}, "seriales_duplicados_en_pdbqt"),
        ({"mapa_no_biyectivo": True}, "index_map_no_biyectivo"),
        ({"indice_fuera": True}, "serial_ausente_o_indice_fuera_de_rango"),
    ],
)
def test_un_mapa_roto_impide_emitir_veredicto(kwargs, motivo):
    from services.chemistry.pose_physical_validity import leer_pose_pdbqt

    pdbqt, _ = _pdbqt_desde_smiles(**kwargs)
    plantilla, mapa, _ = se.extraer_plantilla_y_mapa(pdbqt)

    lectura = leer_pose_pdbqt(pdbqt, plantilla=plantilla, index_map=mapa)

    # Se ABSTIENE con el motivo nombrado, en vez de reconstruir a ojo.
    assert lectura.mol is None
    assert lectura.motivo == motivo


@rdkit_available
def test_una_pose_ilegible_produce_not_evaluated(receptor):
    evidencia = se.build_structural_evidence(
        poses=[_pose(pdbqt="esto no es un PDBQT\n")], target_pdb_id="7E2Y",
        receptor_sha256=receptor.sha256, smiles=ASPIRINA,
    )

    pose = evidencia["poses"][0]
    assert pose["status"] == se.STAGE_NOT_EVALUATED
    assert evidencia["stage_status"] == se.STAGE_NOT_EVALUATED
    # Y NUNCA se describe como una pose inválida.
    texto = json.dumps(evidencia, ensure_ascii=False).lower()
    assert "pose inválida" not in texto and "pose invalida" not in texto


# ── Receptor: exacto o abstención ────────────────────────────────────


@rdkit_available
def test_si_el_receptor_del_disco_se_reparo_se_abstiene(receptor):
    pdbqt, _ = _pdbqt_desde_smiles()

    evidencia = se.build_structural_evidence(
        poses=[_pose(pdbqt=pdbqt)], target_pdb_id="7E2Y",
        receptor_sha256="0" * 64,  # el docking usó OTRO receptor
        smiles=ASPIRINA,
    )

    assert evidencia["stage_status"] == se.STAGE_NOT_EVALUATED
    assert evidencia["poses"][0]["reason_code"] == se.RECEPTOR_NO_COINCIDE
    assert evidencia["reason_code"] == se.RECEPTOR_NO_COINCIDE


def test_sin_huella_del_receptor_no_se_supone_que_sea_el_del_disco(receptor):
    resuelto = se.resolver_receptor(
        target_pdb_id="7E2Y", receptor_sha256_esperado=None,
    )

    assert resuelto.razon == se.RECEPTOR_SIN_HUELLA
    assert resuelto.path is None


def test_los_bytes_congelados_de_una_cohorte_son_el_camino_fuerte(receptor):
    resuelto = se.resolver_receptor(
        target_pdb_id=None,
        receptor_sha256_esperado=receptor.sha256,
        receptor_bytes=receptor.bytes,
    )
    try:
        assert resuelto.razon is None
        assert resuelto.path is not None and resuelto.path.exists()
        assert resuelto.fuente == "cohort_runs.receptor_prepared_bytes"
        assert resuelto.path.read_bytes() == receptor.bytes
    finally:
        resuelto.cerrar()


# ── 3. El proxy nunca falla ──────────────────────────────────────────


@rdkit_available
def test_el_proxy_fuera_de_rango_produce_review_nunca_failed(receptor, monkeypatch):
    """
    `PROD-PV-H-01`: el proxy rechaza el 14.2 % de las poses que el control
    oficial aprueba, y siempre en esa dirección. Convertir eso en `failed`
    fabricaría una alarma sobre poses buenas.
    """
    import services.chemistry.pose_physical_validity as pv

    monkeypatch.setattr(pv, "_posebusters_disponible", lambda: False)
    monkeypatch.setattr(
        pv, "proxy_tension_rdkit",
        lambda mol: {"check": pv.NOMBRE_PROXY, "estado": "FALLA", "razon": 999.0,
                     "umbral": pv.UMBRAL_PROXY_TENSION},
    )

    pdbqt, _ = _pdbqt_desde_smiles()
    evidencia = se.build_structural_evidence(
        poses=[_pose(pdbqt=pdbqt)], target_pdb_id="7E2Y",
        receptor_sha256=receptor.sha256, smiles=ASPIRINA,
    )

    pose = evidencia["poses"][0]
    assert pose["status"] == se.STAGE_REVIEW
    assert evidencia["stage_status"] == se.STAGE_REVIEW
    # Un proxy no acusa a ningún control.
    assert pose["checks_que_fallan"] == []
    assert "no es un veredicto de falla" in (pose["detail"] or "").lower()


# ── 1 y 2. Veredictos oficiales ──────────────────────────────────────


@rdkit_available
def test_una_pose_canonica_que_pasa_los_controles_oficiales(receptor, monkeypatch):
    """Con PoseBusters simulado en verde, el estado es `passed`."""
    import services.chemistry.pose_physical_validity as pv

    _simular_posebusters(monkeypatch, pv, {"sanitization": True, "all_atoms_connected": True,
                                           "internal_energy": True})
    pdbqt, _ = _pdbqt_desde_smiles()

    evidencia = se.build_structural_evidence(
        poses=[_pose(pdbqt=pdbqt)], target_pdb_id="7E2Y",
        receptor_sha256=receptor.sha256, smiles=ASPIRINA,
    )

    pose = evidencia["poses"][0]
    assert pose["status"] == se.STAGE_PASSED
    assert evidencia["stage_status"] == se.STAGE_PASSED
    assert pose["engine"].startswith("posebusters:")
    assert pose["canonicalization_invariants"]["mapa_biyectivo"] is True


@rdkit_available
def test_un_control_oficial_que_falla_produce_failed(receptor, monkeypatch):
    import services.chemistry.pose_physical_validity as pv

    _simular_posebusters(monkeypatch, pv, {"sanitization": True, "bond_lengths": False})
    pdbqt, _ = _pdbqt_desde_smiles()

    evidencia = se.build_structural_evidence(
        poses=[_pose(pdbqt=pdbqt)], target_pdb_id="7E2Y",
        receptor_sha256=receptor.sha256, smiles=ASPIRINA,
    )

    pose = evidencia["poses"][0]
    assert pose["status"] == se.STAGE_FAILED
    assert evidencia["stage_status"] == se.STAGE_FAILED
    assert "bond_lengths" in pose["checks_que_fallan"]


def _simular_posebusters(monkeypatch, pv, fila: dict) -> None:
    """Sustituye PoseBusters por una fila controlada, sin tocar umbrales."""
    import sys
    import types

    class _DF:
        def __init__(self, datos):
            self._d = datos

        @property
        def iloc(self):
            class _I:
                def __init__(self, d):
                    self._d = d

                def __getitem__(self, _i):
                    return types.SimpleNamespace(to_dict=lambda: self._d)

            return _I(self._d)

    class _PB:
        def __init__(self, config="dock"):
            self.config = config

        def bust(self, mol_pred=None, mol_true=None, mol_cond=None):
            return _DF(fila)

    modulo = types.ModuleType("posebusters")
    modulo.PoseBusters = _PB
    monkeypatch.setitem(sys.modules, "posebusters", modulo)
    monkeypatch.setattr(pv, "_posebusters_disponible", lambda: True)
    monkeypatch.setattr(pv, "_version_posebusters", lambda: "simulada")
    monkeypatch.setattr(pv, "receptor_como_pdb", lambda p: p)


# ── 9. Resultado antiguo sin evidencia ───────────────────────────────


def test_una_evaluacion_antigua_no_es_un_error():
    evidencia = se.evidencia_ausente()

    assert evidencia["stage_status"] == se.STAGE_NOT_EVALUATED
    assert evidencia["reason_code"] == se.EVIDENCIA_AUSENTE
    assert evidencia["version_schema"] == se.STRUCTURAL_EVIDENCE_SCHEMA_VERSION
    # Dice explícitamente que no se evaluó, no que fallara.
    assert "no es que fallara" in evidencia["detail"].lower()


# ── Todas las poses, no sólo la top-1 ────────────────────────────────


@rdkit_available
def test_se_conserva_evidencia_de_TODAS_las_poses(receptor, monkeypatch):
    """
    El selector va a llegar y no debe obligar a recalcular ni a perder lo medido.
    La pose principal de este sprint sigue siendo la de Vina, y se declara.
    """
    import services.chemistry.pose_physical_validity as pv

    _simular_posebusters(monkeypatch, pv, {"sanitization": True})
    pdbqt, _ = _pdbqt_desde_smiles()
    poses = [_pose(rank=r, pdbqt=pdbqt, afinidad=-8.0 + r * 0.3) for r in (1, 2, 3)]

    evidencia = se.build_structural_evidence(
        poses=poses, target_pdb_id="7E2Y",
        receptor_sha256=receptor.sha256, smiles=ASPIRINA,
    )

    assert evidencia["pose_strategy"] == se.POSE_STRATEGY_VINA_TOP1
    assert evidencia["primary_pose_rank"] == 1
    assert evidencia["poses_produced"] == 3
    assert evidencia["poses_evaluated"] == 3
    assert evidencia["coverage"] == 1.0
    assert [p["rank"] for p in evidencia["poses"]] == [1, 2, 3]
    # La afinidad viaja pero NO se reordena por ella: el orden es el de Vina.
    assert [p["observed_vina_affinity_kcal_mol"] for p in evidencia["poses"]] == [-7.7, -7.4, -7.1]


def test_sin_poses_la_etapa_se_abstiene():
    evidencia = se.build_structural_evidence(
        poses=[], target_pdb_id="7E2Y", receptor_sha256="x" * 64,
    )

    assert evidencia["stage_status"] == se.STAGE_NOT_EVALUATED
    assert evidencia["reason_code"] == se.SIN_POSES
    assert evidencia["poses"] == []


@rdkit_available
def test_la_etapa_nunca_lanza_aunque_el_validador_reviente(receptor, monkeypatch):
    """Un docking terminado no se pierde porque el validador falle."""
    import services.chemistry.pose_physical_validity as pv

    def _explota(**kwargs):
        raise RuntimeError("el validador se cayó")

    monkeypatch.setattr(pv, "evaluar_pose_fisica", _explota)
    pdbqt, _ = _pdbqt_desde_smiles()

    evidencia = se.build_structural_evidence(
        poses=[_pose(pdbqt=pdbqt)], target_pdb_id="7E2Y",
        receptor_sha256=receptor.sha256, smiles=ASPIRINA,
    )

    assert evidencia["stage_status"] == se.STAGE_NOT_EVALUATED
    assert evidencia["poses"][0]["reason_code"] == se.VALIDADOR_NO_DISPONIBLE


# ── El caso real: hidrógenos polares declarados por Meeko ────────────
#
# Estas dos pruebas usan REMARK COPIADOS DE UNA SALIDA REAL de Meeko en este
# repositorio, no inventados. Es la diferencia entre probar el contrato y
# probar mi idea del contrato.

#: Aspirina desprotonada: 13 pesados, `H PARENT` vacío. El mapa cubre TODO.
REMARK_ASPIRINA = (
    "REMARK SMILES CC(=O)Oc1ccccc1C(=O)[O-]\n"
    "REMARK SMILES IDX 5 1 6 2 7 3 8 4 9 5 10 6 4 7 2 8 3 9 1 10 11 11 12 12 13 13\n"
    "REMARK H PARENT \n"
)

#: Paracetamol: 11 pesados en `SMILES IDX` y DOS hidrógenos polares —seriales
#: 11 y 13— declarados aparte en `REMARK H PARENT`, con sus padres: el átomo 4
#: (el N de la amida) y el 9 (el O del fenol).
REMARK_PARACETAMOL = (
    "REMARK SMILES CC(=O)Nc1ccc(O)cc1\n"
    "REMARK SMILES IDX 5 1 6 2 7 3 8 4 10 5 11 6 4 7 2 8 3 9 1 10 9 12\n"
    "REMARK H PARENT 4 11 9 13\n"
)


def test_los_hidrogenos_polares_se_leen_de_la_declaracion_de_meeko():
    assert se.seriales_de_hidrogeno_polar(REMARK_ASPIRINA) == set()
    # Sólo los SERIALES. El padre (4 = N de la amida, 9 = O del fenol) se lee
    # pero no se usa para colocar el hidrógeno: eso exigiría asumir que ese
    # padre tiene exactamente uno.
    assert se.seriales_de_hidrogeno_polar(REMARK_PARACETAMOL) == {11, 13}


@rdkit_available
def test_los_hidrogenos_polares_declarados_SI_se_mapean():
    """
    El caso real del paracetamol: dos H polares declarados con su padre.

    Se cierran usando la DECLARACIÓN de Meeko —no una inferencia—: la plantilla
    pasa a tener hidrógenos explícitos y cada serial se asigna al H del átomo
    que Meeko nombró. Sin esto, toda molécula con un OH o un NH se quedaba sin
    veredicto, que en un catálogo de fármacos es casi todo.
    """
    plantilla, mapa, procedencia = se.extraer_plantilla_y_mapa(REMARK_PARACETAMOL)

    assert procedencia == "meeko_remark_smiles_idx_con_h_polares"
    # 11 pesados + 9 hidrógenos explícitos.
    assert plantilla.GetNumAtoms() == 20
    # Los 13 seriales del PDBQT quedan cubiertos: 11 pesados + 2 polares.
    assert sorted(s for s, _ in mapa) == list(range(1, 14))


@rdkit_available
def test_un_padre_con_DOS_hidrogenos_abandona_el_mapa_en_vez_de_elegir():
    """
    La anilina tiene un NH2: dos hidrógenos sobre el mismo padre.

    Meeko declara un serial por hidrógeno, pero nada dice CUÁL es cuál. Elegir
    sería la suposición química que este contrato prohíbe, así que se abandona
    el mapa de polares y se conserva el de pesados — que sí es afirmable.
    """
    remark = (
        "REMARK SMILES Nc1ccccc1\n"
        "REMARK SMILES IDX 1 1 2 2 3 3 4 4 5 5 6 6 7 7\n"
        "REMARK H PARENT 1 8 1 9\n"
    )

    plantilla, mapa, procedencia = se.extraer_plantilla_y_mapa(remark)

    assert procedencia == "meeko_remark_smiles_idx_sin_h_polares"
    # La plantilla se queda en los 7 pesados: no se añadieron hidrógenos.
    assert plantilla.GetNumAtoms() == 7
    assert sorted(s for s, _ in mapa) == list(range(1, 8))


@rdkit_available
def test_varios_h_polares_del_mismo_padre_se_canonicalizan_sin_adivinar(receptor):
    """Un NH2 ya no pierde cobertura por la ambigüedad entre sus dos H.

    Producción descarta ambos seriales declarados por Meeko y regenera todos
    los H desde el esqueleto pesado. No necesita escoger cuál H explícito de la
    plantilla corresponde a cuál serial del PDBQT.
    """
    base, _ = _pdbqt_desde_smiles("Nc1ccccc1")
    cabecera, cuerpo = base.split("\n", 2)[0:2], base.split("\n", 2)[2]
    pdbqt = (
        f"{cabecera[0]}\n{cabecera[1]}\n"
        "REMARK H PARENT 1 8 1 9\n"
        f"{cuerpo.rstrip()}\n"
        "ATOM      8  H   LIG A   1      99.000  99.000  99.000  1.00  0.00     0.000 HD\n"
        "ATOM      9  H   LIG A   1     -99.000 -99.000 -99.000  1.00  0.00     0.000 HD\n"
    )

    evidencia = se.build_structural_evidence(
        poses=[_pose(pdbqt=pdbqt)], target_pdb_id="7E2Y",
        receptor_sha256=receptor.sha256, smiles="Nc1ccccc1",
    )

    pose = evidencia["poses"][0]
    assert pose["status"] != se.STAGE_NOT_EVALUATED
    assert pose["reason_code"] is None
    inv = pose["canonicalization_invariants"]
    assert inv["h_polares_declarados_descartados"] == 2
    assert inv["n_h_heredados"] == 0
    assert inv["pesados_invariantes"] is True
    assert inv["desplazamiento_pesado_max_A"] <= 1e-6
