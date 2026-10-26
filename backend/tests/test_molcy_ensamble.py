"""La evidencia del ensamble para Molcy: lo que se demuestra y cuándo se abstiene.

Se prueba con moléculas reales de RDKit: las «poses» son transformaciones RÍGIDAS de
cada conformación, así que se sabe de antemano qué debe salir (los diedros no cambian,
la conformación de la pose 1 se superpone con RMSD cero, etc.).
"""
from __future__ import annotations

import hashlib
import math

import pytest

rdkit = pytest.importorskip("rdkit")
from rdkit import Chem                                          # noqa: E402
from rdkit.Chem import AllChem, rdMolTransforms                 # noqa: E402

from services.docking.pose_recovery import PoseNoRecuperable, PoseRecuperada  # noqa: E402
from services.molcy import ensamble as ens                      # noqa: E402

SMILES = "CCOC(=O)c1ccccc1OC"          # éster aromático: tres enlaces rotables


def _conformaciones(n=3, smiles=SMILES):
    base = Chem.AddHs(Chem.MolFromSmiles(smiles))
    ids = AllChem.EmbedMultipleConfs(base, numConfs=n, randomSeed=7)
    assert len(ids) == n
    salida = []
    for i in ids:
        mol = Chem.Mol(base, confId=i) if False else Chem.Mol(base)
        mol.RemoveAllConformers()
        mol.AddConformer(base.GetConformer(i), assignId=True)
        salida.append(mol)
    return salida


def _bloque(mol) -> bytes:
    return (Chem.MolToMolBlock(mol) + "\n$$$$\n").encode("utf-8")


def _mover(mol, angulo=0.9, traslacion=(3.0, -2.0, 5.0)):
    """Una transformación rígida: lo que un acoplamiento cambia, salvo las torsiones."""
    copia = Chem.Mol(mol)
    c, s = math.cos(angulo), math.sin(angulo)
    conf = copia.GetConformer()
    for i in range(copia.GetNumAtoms()):
        x, y, z = conf.GetAtomPosition(i)
        conf.SetAtomPosition(i, (c * x - s * y + traslacion[0], s * x + c * y + traslacion[1],
                                 z + traslacion[2]))
    return copia


def _diedros(mol):
    sin_h = Chem.RemoveHs(mol)
    return ens._diedros(sin_h)


# ── es_ensamble: la comprobación barata ───────────────────────────────────────
def _snap(generadas=3, por_conformacion=True, poses=True):
    return {
        "docking_protocol": {
            "conformers_generated": generadas,
            "execution_provenance": ({"por_conformacion": [{"indice": 0}]}
                                     if por_conformacion else {"box_center": [0, 0, 0]})},
        "docking_poses": ([{"rank": 1, "affinity": -7.0, "conformer_index": 0,
                            "source_provenance": {"rank": 1}}] if poses else []),
    }


def test_un_ensamble_completo_pasa_la_comprobacion_estructural():
    assert ens.es_ensamble(_snap()) == (True, None)


@pytest.mark.parametrize("snap,fragmento", [
    (_snap(generadas=1), "no es un ensamble"),
    (_snap(por_conformacion=False), "procedencia de cada conformación"),
    (_snap(poses=False), "de qué conformación"),
])
def test_lo_que_no_es_un_ensamble_dice_por_que(snap, fragmento):
    ok, motivo = ens.es_ensamble(snap)
    assert not ok and fragmento in motivo


def test_una_pose_sin_linaje_invalida_todo_el_ensamble():
    snap = _snap()
    snap["docking_poses"].append({"rank": 2, "affinity": -6.0, "conformer_index": None,
                                  "source_provenance": {"rank": 2}})
    assert ens.es_ensamble(snap)[0] is False


# ── controles físicos: sólo si son de esa pose ────────────────────────────────
def _con_evidencia(estado="passed", checks=None, afinidad=-7.0, receptor="r" * 64):
    return {
        "receptor_sha256": "r" * 64,
        "structural_evidence": {
            "stage_status": "passed", "receptor_sha256": receptor,
            "validation_engine": "posebusters:0.6.5:dock", "coverage": 1.0,
            "poses": [{"rank": 1, "status": estado, "engine": "posebusters:0.6.5:dock",
                       "observed_vina_affinity_kcal_mol": afinidad,
                       "checks": checks if checks is not None else
                       [{"check": "sanitization", "estado": "PASA"},
                        {"check": "bond_lengths", "estado": "PASA"}]}]}}


POSE_1 = {"rank": 1, "affinity": -7.0}


def test_controles_aprobados_se_cuentan():
    c = ens.controles_de(_con_evidencia(), POSE_1)
    assert (c["aprobadas"], c["pruebas"], c["fallos"], c["no_evaluados"]) == (2, 2, [], 0)


def test_controles_que_fallan_y_no_evaluados_no_cuentan_como_aprobados():
    checks = [{"check": "a", "estado": "PASA"}, {"check": "internal_energy", "estado": "FALLA"},
              {"check": "c", "estado": "NO_EVALUADO"}]
    c = ens.controles_de(_con_evidencia(estado="review", checks=checks), POSE_1)
    assert (c["aprobadas"], c["pruebas"], c["no_evaluados"]) == (1, 3, 1)
    assert c["fallos"] == ["internal_energy"]


def test_una_pose_no_evaluada_queda_no_evaluada():
    c = ens.controles_de(_con_evidencia(estado="not_evaluated", checks=[]), POSE_1)
    assert c["estado"] == "not_evaluated" and c["pruebas"] is None


@pytest.mark.parametrize("snap", [
    {},                                                     # sin evidencia
    _con_evidencia(receptor="x" * 64),                      # de otro receptor
    _con_evidencia(afinidad=-5.0),                          # de otra pose
    {**_con_evidencia(), "structural_evidence": {**_con_evidencia()["structural_evidence"],
                                                 "stage_status": "abstained"}},
])
def test_controles_que_no_se_pueden_atribuir_son_none(snap):
    assert ens.controles_de(snap, POSE_1) is None


def test_si_la_pose_no_esta_en_la_evidencia_es_none():
    assert ens.controles_de(_con_evidencia(), {"rank": 2, "affinity": -7.0}) is None


# ── SCI-A-027: una etapa con reserva NO borra los controles de la pose ────────
def _con_etapa(stage_status, estado="passed", checks=None):
    """La misma evidencia, cambiando el estado de la ETAPA, no el de la pose."""
    snap = _con_evidencia(estado=estado, checks=checks)
    snap["structural_evidence"]["stage_status"] = stage_status
    return snap


@pytest.mark.parametrize("stage_status", ["review", "failed"])
def test_una_etapa_en_reserva_conserva_los_controles_medidos(stage_status):
    # Antes se exigia `passed` para conservar cualquier control, asi que estas
    # corridas salian al video como «CONTROLES FISICOS: NO EVALUADOS»: un fallo
    # medido presentado como ausencia de medida.
    c = ens.controles_de(_con_etapa(stage_status), POSE_1)

    assert c is not None, "los controles de esta pose si se midieron"
    assert (c["aprobadas"], c["pruebas"]) == (2, 2)


def test_una_pose_que_falla_viaja_con_su_fallo_y_no_como_no_evaluada():
    checks = [{"check": "sanitization", "estado": "PASA"},
              {"check": "internal_energy", "estado": "FALLA"}]
    c = ens.controles_de(_con_etapa("failed", estado="failed", checks=checks), POSE_1)

    assert c["estado"] == "failed"
    assert c["fallos"] == ["internal_energy"]
    # `failed` habla de la pose; `not_evaluated`, del validador. No son lo mismo.
    assert c["estado"] != "not_evaluated"


def test_un_estado_de_etapa_desconocido_sigue_sin_exportar_controles():
    # La lista es blanca: de lo que no se sabe leer no se exportan controles.
    assert ens.controles_de(_con_etapa("abstained"), POSE_1) is None


# ── geometría ─────────────────────────────────────────────────────────────────
def test_los_diedros_se_miden_sobre_la_entrada_y_no_cambian_con_el_acoplamiento():
    confs = _conformaciones(1)
    antes = _diedros(confs[0])
    despues = _diedros(_mover(confs[0]))
    assert len(antes) >= 3
    for a, b in zip(antes, despues):
        assert a["atomos"] == b["atomos"]
        assert a["angulo_grados"] == pytest.approx(b["angulo_grados"], abs=0.01)
    assert all(len(d["atomos"]) == 4 for d in antes)


def test_la_geometria_alinea_la_conformacion_de_la_pose_uno_sobre_ella():
    confs = _conformaciones(3)
    registros = [(i + 1, _bloque(_mover(m, 0.4 + i, (1.0 * i, 2.0, -3.0 * i))).decode())
                 for i, m in enumerate(confs)]
    sdfs = {i: _bloque(m) for i, m in enumerate(confs)}

    g = ens.construir_geometria(registros, sdfs)

    assert set(g["conformeros"]) == {0, 1, 2}
    # La conformación 0 ES la pose 1 sin mover: su superposición debe ser exacta.
    assert g["conformeros"][0]["rmsd_alineacion_a"] == pytest.approx(0.0, abs=1e-3)
    # Las otras son otras geometrías: se alinean, pero no coinciden.
    assert g["conformeros"][1]["rmsd_alineacion_a"] > 0.05
    assert {f"docking/ensamble/pose_{r:03d}.{e}" for r in (1, 2, 3) for e in ("pdb", "sdf")} <= set(g["archivos"])
    assert {f"docking/ensamble/conf_{i:02d}.pdb" for i in (0, 1, 2)} <= set(g["archivos"])
    # El .sdf de la pose es el registro demostrado, byte a byte, no una copia sin H.
    assert g["archivos"]["docking/ensamble/pose_001.sdf"].decode().rstrip().endswith("$$$$")
    assert b" H " in g["archivos"]["docking/ensamble/pose_001.sdf"] or b"H  " in g["archivos"]["docking/ensamble/pose_001.sdf"]


def test_cada_atomo_de_un_diedro_existe_con_ese_nombre_en_el_archivo_que_se_dibuja():
    confs = _conformaciones(1)
    g = ens.construir_geometria([(1, _bloque(_mover(confs[0])).decode())], {0: _bloque(confs[0])})
    nombres_pdb = {linea[12:16].strip() for linea in
                   g["archivos"]["docking/ensamble/conf_00.pdb"].decode().splitlines()
                   if linea.startswith("HETATM")}
    torsiones = g["conformeros"][0]["torsiones"]
    assert torsiones
    for torsion in torsiones:
        assert set(torsion["atomos"]) <= nombres_pdb, (torsion, nombres_pdb)


def test_la_copia_alineada_no_toca_la_entrada_que_recibio_vina():
    confs = _conformaciones(2)
    registros = [(1, _bloque(_mover(confs[0])).decode())]
    entrada = _bloque(confs[1])
    g = ens.construir_geometria(registros, {1: entrada})
    assert g["archivos"]["docking/ensamble/conf_01_entrada.sdf"] == entrada


def test_sin_correspondencia_entre_moleculas_se_abstiene_en_vez_de_superponer_otra_cosa():
    pose = _bloque(_mover(_conformaciones(1)[0])).decode()
    otra = _bloque(_conformaciones(1, smiles="CCCCCCCCN")[0])
    with pytest.raises(ens.EnsambleNoDisponible, match="no se corresponde"):
        ens.construir_geometria([(1, pose)], {0: otra})


def test_si_los_ordenes_de_enlace_difieren_se_alinea_por_el_grafo():
    """Vina y RDKit pueden exportar distintos órdenes de enlace del mismo ligando."""
    m = _conformaciones(1)[0]
    sin_ordenes = Chem.RWMol(m)
    for enlace in sin_ordenes.GetBonds():
        enlace.SetBondType(Chem.BondType.SINGLE)
        enlace.SetIsAromatic(False)
    for atomo in sin_ordenes.GetAtoms():
        atomo.SetIsAromatic(False)
    pose = _bloque(_mover(sin_ordenes.GetMol())).decode()
    g = ens.construir_geometria([(1, pose)], {0: _bloque(m)})
    assert g["conformeros"][0]["rmsd_alineacion_a"] == pytest.approx(0.0, abs=1e-2)


# ── el contrato ───────────────────────────────────────────────────────────────
def _snap_completo(n_conf=3):
    por_conformacion = [{"indice": 10 + i, "semilla_conformacional": 500 + i,
                         "energia_mmff": 20.0 + i, "num_poses": 9,
                         "mejor_afinidad_kcal_mol": -7.0 - i} for i in range(n_conf)]
    snap = {
        "vina_version": "1.2.7", "vina_random_seed": 42,
        "docking_protocol": {
            "conformers_requested": 30, "conformers_generated": 30, "exhaustiveness": 8,
            "num_poses": 9,
            "execution_provenance": {"box_center": [1.0, 2.0, 3.0],
                                     "box_size": [20.0, 20.0, 20.0],
                                     "por_conformacion": por_conformacion}},
        **_con_evidencia(),
    }
    return snap


def _contrato(n_conf=3, snap=None):
    confs = _conformaciones(n_conf)
    # Las poses salen de las conformaciones 12, 10, 11 en ese orden de piscina.
    orden = [2, 0, 1][:n_conf]
    registros = [(r, _bloque(_mover(confs[i], 0.2 * r)).decode()) for r, i in enumerate(orden, 1)]
    sdfs = {10 + i: _bloque(confs[i]) for i in orden}
    # `registros` usa índices de conformación 0..n; el contrato los llama 10+i.
    entregadas = [{"rank": r, "affinity": -7.0 + 0.1 * (r - 1), "conformer_index": 10 + i,
                   "rank_local": 1, "source_provenance": {}} for r, i in enumerate(orden, 1)]
    geometria = ens.construir_geometria(registros, sdfs)
    return ens.armar_contrato(snap or _snap_completo(n_conf), entregadas, geometria,
                              origen={"origen": "moldex"}), entregadas


def test_el_contrato_cita_archivos_con_su_sha256_real():
    r, _ = _contrato()
    contrato, archivos = r["contrato"], r["archivos"]
    for item in contrato["conformeros"] + contrato["poses"]:
        assert hashlib.sha256(archivos[item["archivo"]]).hexdigest() == item["sha256"]
        assert hashlib.sha256(archivos[item["sdf"]]).hexdigest() == item["sdf_sha256"]


def test_las_conformaciones_van_en_el_orden_de_su_mejor_pose_de_la_piscina():
    r, _ = _contrato()
    assert [c["indice"] for c in r["contrato"]["conformeros"]] == [12, 10, 11]


def test_el_contrato_lleva_las_cuentas_de_la_corrida_no_de_un_aviso():
    resumen = _contrato()[0]["contrato"]["resumen"]
    assert resumen == {"conformaciones_pedidas": 30, "conformaciones_generadas": 30,
                       "conformaciones_acopladas": 3, "poses_candidatas": 27,
                       "poses_entregadas": 3, "conformaciones_con_poses_entregadas": 3}


def test_las_candidatas_se_declaran_desconocidas_si_alguna_corrida_no_las_conto():
    snap = _snap_completo()
    del snap["docking_protocol"]["execution_provenance"]["por_conformacion"][1]["num_poses"]
    assert _contrato(snap=snap)[0]["contrato"]["resumen"]["poses_candidatas"] is None


def test_semilla_y_energia_son_las_de_la_corrida_y_la_energia_ausente_no_se_inventa():
    snap = _snap_completo()
    del snap["docking_protocol"]["execution_provenance"]["por_conformacion"][0]["energia_mmff"]
    conformeros = {c["indice"]: c for c in _contrato(snap=snap)[0]["contrato"]["conformeros"]}
    assert conformeros[10]["semilla"] == 500 and conformeros[10]["energia_mmff"] is None
    assert conformeros[11]["energia_mmff"] == 21.0


def test_el_contrato_declara_la_caja_el_motor_y_las_reservas():
    contrato = _contrato()[0]["contrato"]
    assert contrato["schema"] == "moldesign.ensamble/1"
    assert contrato["caja"] == {"centro": [1.0, 2.0, 3.0], "tamano": [20.0, 20.0, 20.0]}
    assert contrato["motor"]["version"] == "1.2.7" and contrato["motor"]["semilla"] == 42
    assert any("alinean" in d for d in contrato["declaraciones"])
    assert any("no evaluado" in d for d in contrato["declaraciones"])


def test_sin_controles_atribuibles_el_contrato_no_declara_validacion():
    snap = _snap_completo()
    snap["structural_evidence"]["stage_status"] = "abstained"
    contrato = _contrato(snap=snap)[0]["contrato"]
    assert contrato["validacion"] is None
    assert all(p["controles"] is None for p in contrato["poses"])


# ── recoger: todo o nada ──────────────────────────────────────────────────────
class _Pose(dict):
    pass


def _snap_con_poses(n=3):
    snap = _snap_completo(n)
    snap["docking_poses"] = [
        {"rank": r, "affinity": -7.0 + 0.1 * (r - 1), "rmsd_lb": 0.0, "rmsd_ub": 0.0,
         "pdbqt_block": "MODEL 1\nENDMDL\n", "conformer_index": 10 + (r - 1),
         "source_provenance": {"rank": 1, "poses_file_path": f"p{r}.sdf",
                               "poses_file_sha256": "a" * 64,
                               "ligand_input": {"conformer_path": f"c{r}.sdf",
                                                "conformer_sha256": "b" * 64,
                                                "semilla_conformacional": 500 + r}}}
        for r in range(1, n + 1)]
    return snap


@pytest.mark.asyncio
async def test_recoger_demuestra_cada_pose_y_devuelve_el_contrato(monkeypatch):
    confs = _conformaciones(3)
    por_rank = {r: _bloque(_mover(confs[r - 1], 0.3 * r)).decode() for r in (1, 2, 3)}

    async def recuperar(pose):
        return PoseRecuperada(sdf_record=por_rank[pose.rank], poses_file_path=f"p{pose.rank}.sdf",
                              rank_original=1, conformer_index=pose.conformer_index,
                              conformer_path=f"c{pose.rank}.sdf", atomos_verificados=10,
                              max_desplazamiento_A=0.0)

    async def leer(ruta):
        return _bloque(confs[int(ruta[1]) - 1])

    monkeypatch.setattr(ens, "recuperar_pose_agrupada", recuperar)
    monkeypatch.setattr(ens, "read_bytes", leer)

    r = await ens.recoger(_snap_con_poses(), origen={"origen": "moldex"})

    assert [p["rank"] for p in r["contrato"]["poses"]] == [1, 2, 3]
    assert len(r["contrato"]["conformeros"]) == 3
    assert r["contrato"]["origen"] == {"origen": "moldex"}


@pytest.mark.asyncio
async def test_si_una_sola_pose_no_se_demuestra_no_se_monta_el_ensamble(monkeypatch):
    confs = _conformaciones(3)

    async def recuperar(pose):
        if pose.rank == 2:
            raise PoseNoRecuperable("El archivo de poses cambió desde la corrida")
        return PoseRecuperada(sdf_record=_bloque(confs[0]).decode(), poses_file_path="p.sdf",
                              rank_original=1, conformer_index=pose.conformer_index,
                              conformer_path="c1.sdf", atomos_verificados=10,
                              max_desplazamiento_A=0.0)

    async def leer(ruta):
        return _bloque(confs[0])

    monkeypatch.setattr(ens, "recuperar_pose_agrupada", recuperar)
    monkeypatch.setattr(ens, "read_bytes", leer)

    with pytest.raises(ens.EnsambleNoDisponible, match="pose 2.*cambió"):
        await ens.recoger(_snap_con_poses())


@pytest.mark.asyncio
async def test_sin_la_caja_exacta_se_abstiene_antes_de_leer_nada(monkeypatch):
    snap = _snap_con_poses()
    del snap["docking_protocol"]["execution_provenance"]["box_center"]

    async def no_debe_llamarse(*a, **k):
        raise AssertionError("no debía tocar el disco")

    monkeypatch.setattr(ens, "recuperar_pose_agrupada", no_debe_llamarse)
    with pytest.raises(ens.EnsambleNoDisponible, match="caja"):
        await ens.recoger(snap)


@pytest.mark.asyncio
async def test_una_conformacion_de_entrada_ausente_es_una_abstencion_no_un_500(monkeypatch):
    confs = _conformaciones(1)

    async def recuperar(pose):
        return PoseRecuperada(sdf_record=_bloque(confs[0]).decode(), poses_file_path="p.sdf",
                              rank_original=1, conformer_index=pose.conformer_index,
                              conformer_path="falta.sdf", atomos_verificados=10,
                              max_desplazamiento_A=0.0)

    async def leer(ruta):
        raise OSError("no existe")

    monkeypatch.setattr(ens, "recuperar_pose_agrupada", recuperar)
    monkeypatch.setattr(ens, "read_bytes", leer)
    with pytest.raises(ens.EnsambleNoDisponible, match="conformación 10"):
        await ens.recoger(_snap_con_poses(1))


# ── el paquete ────────────────────────────────────────────────────────────────
def _receptor() -> bytes:
    def atom(serial: int, residuo: int, x: float) -> str:
        return (f"ATOM  {serial:5d}  CA  ALA A{residuo:4d}    {x:8.3f}{0.:8.3f}{0.:8.3f}"
                f"  1.00  0.00    0.000 C\n")
    return (atom(1, 1, 0.) + atom(2, 2, 3.8)).encode()


def _paquete(tmp_path, ensamble, centro=(1.0, 2.0, 3.0), tamano=(20.0, 20.0, 20.0)):
    from services.molcy.package import construir_paquete, sha256 as huella
    receptor = _receptor()
    return construir_paquete(
        tmp_path, receptor_pdbqt=receptor, receptor_sha256=huella(receptor), pdb_id="TEST",
        nombre="Prueba", cadena="A", centro=centro, tamano=tamano,
        fuente={"origen": "moldex", "task_id": "corrida"}, ensamble=ensamble)


def test_el_paquete_escribe_el_contrato_con_su_origen_y_un_manifiesto_verificable(tmp_path):
    import json
    from services.molcy.package import sha256 as huella
    r, _ = _contrato()
    escena = _paquete(tmp_path, r)

    contrato = json.loads((tmp_path / "ensamble.json").read_text(encoding="utf-8"))
    assert contrato["origen"] == {"origen": "moldex", "task_id": "corrida"}
    assert not (tmp_path / "docking.json").exists()     # sin archivo de poses único
    assert any("Ensamble" in d for d in escena["declarar_si_se_dibuja"])
    lineas = (tmp_path / "MANIFEST.sha256").read_text().splitlines()
    assert {linea.split("  ", 1)[1] for linea in lineas} >= {
        "ensamble.json", "docking/ensamble/pose_001.pdb", "docking/ensamble/conf_12.pdb"}
    for linea in lineas:
        digest, relativo = linea.split("  ", 1)
        assert huella((tmp_path / relativo).read_bytes()) == digest


def test_el_paquete_rechaza_un_ensamble_de_otra_caja(tmp_path):
    r, _ = _contrato()
    with pytest.raises(ValueError, match="caja"):
        _paquete(tmp_path, r, centro=(9.0, 9.0, 9.0))


def test_el_paquete_rechaza_un_hash_que_no_es_el_del_archivo(tmp_path):
    r, _ = _contrato()
    r["contrato"]["poses"][0]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="SHA-256"):
        _paquete(tmp_path, r)


def test_el_paquete_no_escribe_fuera_de_su_carpeta(tmp_path):
    r, _ = _contrato()
    r["archivos"]["../fuera.txt"] = b"x"
    with pytest.raises(ValueError, match="fuera del paquete"):
        _paquete(tmp_path / "paquete", r)
    assert not (tmp_path / "fuera.txt").exists()


# ── los motivos de abstención se leen también en inglés ───────────────────────
def _en(texto: str) -> str:
    from core import i18n
    token = i18n.set_request_locale("en-US")
    try:
        return i18n.translate_text(texto)
    finally:
        i18n.reset_request_locale(token)


def test_los_motivos_de_abstencion_tienen_version_en_ingles():
    motivos = [
        ens.es_ensamble(_snap(generadas=1))[1],
        ens.es_ensamble(_snap(por_conformacion=False))[1],
        ens.es_ensamble(_snap(poses=False))[1],
        "No se puede demostrar la pose 3 de la piscina: el archivo cambió",
        "Falta la conformación 7 de entrada.",
        "No se pudo reconstruir la geometría del ensamble: algo",
    ]
    for motivo in motivos:
        assert _en(motivo) != motivo, f"sin traducción: {motivo}"
    with pytest.raises(ens.EnsambleNoDisponible) as geometria:
        ens._primer_registro("sin geometria")
    assert _en(str(geometria.value)) != str(geometria.value)
    pose = _bloque(_mover(_conformaciones(1)[0])).decode()
    otra = _bloque(_conformaciones(1, smiles="CCCCCCCCN")[0])
    with pytest.raises(ens.EnsambleNoDisponible) as alineacion:
        ens.construir_geometria([(1, pose)], {0: otra})
    assert _en(str(alineacion.value)) != str(alineacion.value)


# La ilustración fluida usa un grafo comprobable del mismo SDF; no añade una simulación.
def test_el_rig_usa_el_hash_original_y_los_nombres_xyz_del_pdb_alineado():
    conf = _conformaciones(1)[0]
    original = _bloque(conf)
    g = ens.construir_geometria([(1, _bloque(_mover(conf)).decode())], {7: original})
    rig = g["conformeros"][7]["rig_torsional"]
    rows = [line for line in g["archivos"]["docking/ensamble/conf_07.pdb"].decode().splitlines()
            if line.startswith(("ATOM  ", "HETATM"))]
    assert rig["sdf_sha256"] == hashlib.sha256(original).hexdigest()
    assert g["archivos"]["docking/ensamble/conf_07_entrada.sdf"] == original
    assert rig["atomos"] == [{"id": line[12:16].strip(), "elemento": line[76:78].strip(),
                              "xyz_a": [float(line[start:start + 8]) for start in (30, 38, 46)]} for line in rows]
    assert all(a["elemento"] != "H" for a in rig["atomos"])


@pytest.mark.parametrize("smiles", ["CCCCCC", "CC(C)CCOC(=O)c1ccccc1"])
def test_cada_eje_mueve_toda_la_componente_y_solo_puentes_simples_no_conjugados(smiles):
    conf = _conformaciones(1, smiles)[0]
    g = ens.construir_geometria([(1, _bloque(_mover(conf)).decode())], {0: _bloque(conf)})
    rig = g["conformeros"][0]["rig_torsional"]
    assert rig["ejes"]
    graph = {a["id"]: set() for a in rig["atomos"]}
    links = {}
    for link in rig["enlaces"]:
        a, b = link["atomos"]
        graph[a].add(b); graph[b].add(a)
        links[frozenset((a, b))] = link
    for axis in rig["ejes"]:
        i, j, k, l = axis["atomos"]
        edge = links[frozenset((j, k))]
        assert edge["orden"] == 1
        assert all(edge[key] is False for key in ("anillo", "aromatico", "conjugado"))
        assert i in graph[j] and l in graph[k]
        visited, pending = set(), [k]
        while pending:
            current = pending.pop()
            if current in visited:
                continue
            visited.add(current)
            pending.extend(other for other in graph[current]
                           if frozenset((current, other)) != frozenset((j, k)))
        assert set(axis["moviles"]) == visited
        assert j not in visited and k in visited and l in visited
        assert axis["amplitud_grados"] == 30.0


@pytest.mark.parametrize("smiles", ["C1CCCCC1", "c1ccccc1", "CC", "C=CC=C"])
def test_sin_eje_elegible_el_ensamble_discreto_persiste_y_no_inventa_movimiento(smiles):
    conf = _conformaciones(1, smiles)[0]
    g = ens.construir_geometria([(1, _bloque(_mover(conf)).decode())], {0: _bloque(conf)})
    assert g["conformeros"][0]["rig_torsional"]["ejes"] == []
    assert g["conformeros"][0]["rig_torsional_motivo"]
    assert g["archivos"]["docking/ensamble/conf_00_entrada.sdf"] == _bloque(conf)


def test_el_contrato_transporta_el_rig_ligado_a_su_sdf_sin_cambiar_las_medidas():
    resultado, _ = _contrato()
    for c in resultado["contrato"]["conformeros"]:
        assert c["rig_torsional"]["sdf_sha256"] == c["sdf_sha256"]
        assert c["rig_torsional"]["schema"] == "moldesign.rig-torsional/1"
        assert "energia_mmff" in c and "torsiones" in c
