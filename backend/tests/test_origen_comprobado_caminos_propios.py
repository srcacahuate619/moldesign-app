"""Los receptores propios de los caminos B y C se comprueban con SU receta (FEP-09, defecto P01).

`origen_comprobado` decide si el archivo de origen es el que preparó el receptor de la
corrida recalculando la receta. Hasta el 2026-10-11 recalculaba siempre la automática
(`preparer.receptor_recipe_hash`), que no es la de ningún receptor propio:

- el camino B (respetar el archivo) registra `receta_respetando`;
- el camino C (PDBQT listo para Vina) registra `receta_pdbqt`.

FEP-09 lo midió con Vina real por la API: en 127 de 127 auditorías del camino B,
`entorno.referencia` quedó NO_EVALUADO, todo se midió desde la caja y la pestaña decía
que el archivo de origen no era el de la corrida, que era falso. Estas pruebas fijan el
contrato de cada camino, con sus controles negativos: un archivo cambiado, otra receta
u otro perfil no pasan.
"""

from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace

import pytest

from services.dossier.contexto_estructural import medir, origen_comprobado
from tests.test_preparacion_revision_rutinaria import _pdb

CENTRO = (0.0, 0.0, 0.0)
LADO = (20.0, 20.0, 20.0)
RECETA_DISTINTA = "El archivo de origen no es el que preparó el receptor de esta corrida (la receta no coincide)"


def _corrida(receta: str, *, modo: str | None, receptor_path=None, receptor_sha256="c" * 64, diff=None):
    prep = {"recipe_hash": receta, "chain": "A", "site_chains": ["A"]}
    if modo is not None:
        prep["modo_de_preparacion"] = modo
    if diff is not None:
        prep["species_diff"] = diff
    pose = "\n".join([
        "ATOM      1  O1  UNL     1       0.000   0.000   0.000  0.00  0.00    -0.300 OA",
        "ATOM      2  C1  UNL     1       1.400   0.000   0.000  0.00  0.00     0.100 C ",
    ])
    return SimpleNamespace(
        receptor_path=receptor_path,
        docking_poses=[{"rank": 1, "pdbqt_block": pose}],
        docking_protocol={"execution_provenance": {
            "box_center": list(CENTRO), "box_size": list(LADO), "receptor_sha256": receptor_sha256,
            "receptor_prep": prep,
        }},
    )


# ── Camino B: respetar el archivo ────────────────────────────────────


@pytest.fixture
def deposito_b(tmp_path, monkeypatch):
    """Un receptor preparado por el equipo, con nombres de CHARMM y un agua que puentea.

    His A:2 (HSE en el archivo) tiene NE2 a 2.9 Å del O del ligando; el agua A:401 (WAT en
    el archivo) está a 3.0 Å del ligando y a 2.8 Å del OG de la Ser A:3.
    """
    from services.docking import preparer
    from services.docking.preparer_respetando import receta_respetando
    from utils import local_storage
    from utils.file_handlers import StoragePath

    monkeypatch.setattr(local_storage, "data_dir", lambda: tmp_path)
    lineas = [
        "HEADER    HYDROLASE",
        _pdb("ATOM", 1, "N", "HSE", 2, (0.0, 9.0, 0.0), "N"),
        _pdb("ATOM", 2, "CA", "HSE", 2, (0.0, 8.0, 0.0), "C"),
        _pdb("ATOM", 3, "ND1", "HSE", 2, (0.0, 5.0, 0.0), "N"),
        _pdb("ATOM", 4, "NE2", "HSE", 2, (0.0, 2.9, 0.0), "N"),
        _pdb("ATOM", 5, "CA", "SER", 3, (0.0, 0.0, 7.0), "C"),
        _pdb("ATOM", 6, "OG", "SER", 3, (0.0, 0.0, 5.8), "O"),
        _pdb("HETATM", 7, "O", "WAT", 401, (0.0, 0.0, 3.0), "O"),
        "END",
    ]
    archivo = tmp_path / "raw.pdb"
    archivo.write_bytes(("\n".join(lineas) + "\n").encode("utf-8"))
    monkeypatch.setattr(preparer, "receptor_source_path_no_network", lambda pdb_id: archivo)
    # La receta como la calcula `preparar_respetando`: sobre el crudo leído con `read_text`,
    # que decodifica los bytes sin traducir saltos de línea.
    receta = receta_respetando(archivo.read_bytes().decode("utf-8"), {"A"}, CENTRO, LADO)
    informe = local_storage.path_for(preparer._meeko_report_path(StoragePath.target_prepared("USR_B1", receta)))
    informe.parent.mkdir(parents=True, exist_ok=True)
    informe.write_text(json.dumps({"receptor_sha256": "c" * 64, "protonation_templates": {
        "A:2": {"template": "HIE", "input_resname": "HIE"}}}), encoding="utf-8")
    # Como lo escribe `preparar_respetando`: el diff es del texto traducido, así que el agua es HOH.
    agua = {"chain": "A", "residue_number": "401", "insertion_code": "", "name": "HOH",
            "category": "water", "distance_to_box_A": 0.0}
    diff = {"state": "evaluado", "site_ligand": None,
            "near_site": {"margin_A": 6.0, "removed": [], "preserved": [agua]}}
    return archivo, receta, diff


def test_el_camino_b_se_comprueba_con_la_receta_que_lo_preparo(deposito_b):
    from services.docking import preparer

    archivo, receta, diff = deposito_b
    comprobado = origen_comprobado(_corrida(receta, modo="respetar", diff=diff), "USR_B1")

    assert not isinstance(comprobado, str), comprobado
    assert comprobado.datos == archivo.read_bytes()
    assert comprobado.sha256 == hashlib.sha256(archivo.read_bytes()).hexdigest()
    # El defecto: la receta automática de este archivo no es la del camino B, así que la
    # comprobación de antes no podía dar por bueno ningún receptor respetado.
    automatica = preparer.receptor_recipe_hash(
        archivo.read_bytes().decode("utf-8"), chains={"A"}, cofactors_whitelist=None,
        center=CENTRO, size=LADO, site_ligand=None)
    assert automatica != receta


def test_en_el_camino_b_viaja_el_crudo_y_se_mide_el_texto_traducido(deposito_b):
    _, receta, diff = deposito_b
    comprobado = origen_comprobado(_corrida(receta, modo="respetar", diff=diff), "USR_B1")

    assert b"WAT" in comprobado.datos and b"HSE" in comprobado.datos
    assert " WAT " not in comprobado.texto and " HSE " not in comprobado.texto
    assert " HOH A 401" in comprobado.texto and " HIE A   2" in comprobado.texto


def test_el_camino_b_mide_desde_el_ligando(deposito_b):
    _, receta, diff = deposito_b
    contexto = medir(_corrida(receta, modo="respetar", diff=diff), "USR_B1")

    assert contexto.medido, contexto.razon
    assert contexto.referencia == "Pose top-1"
    # El agua se llama WAT en el archivo y HOH en el diff: sin traducir, quedaba sin distancia.
    assert contexto.especies[("A", "401", "", "HOH")] == 3.0
    assert contexto.aguas_a_la_proteina[("A", "401", "", "HOH")] == 2.8
    assert contexto.aguas_al_ligando_polar[("A", "401", "", "HOH")] == 3.0
    assert contexto.anillos_his == {"A:2": 2.9}


def test_un_crudo_cambiado_despues_de_preparar_no_pasa_en_el_camino_b(deposito_b):
    archivo, receta, diff = deposito_b
    archivo.write_bytes(archivo.read_bytes().replace(b"   3.000", b"   3.100"))

    assert origen_comprobado(_corrida(receta, modo="respetar", diff=diff), "USR_B1") == RECETA_DISTINTA
    contexto = medir(_corrida(receta, modo="respetar", diff=diff), "USR_B1")
    assert not contexto.medido
    assert contexto.razon.startswith(RECETA_DISTINTA)


def test_la_receta_b_no_vale_para_una_corrida_que_no_es_del_camino_b(deposito_b):
    # La receta se recalcula con la del camino que registró la corrida, no con la que encaje.
    _, receta, diff = deposito_b
    assert origen_comprobado(_corrida(receta, modo=None, diff=diff), "USR_B1") == RECETA_DISTINTA
    assert origen_comprobado(_corrida(receta, modo="automatico", diff=diff), "USR_B1") == RECETA_DISTINTA


# ── Camino C: PDBQT con su estructura de origen ──────────────────────


def _como_pdbqt(linea_pdb: str, tipo: str) -> str:
    return f"{linea_pdb[:66]}    {0.0:+.3f} {tipo:<2}"


@pytest.fixture
def deposito_c(tmp_path, monkeypatch):
    """Un PDBQT subido con su origen: el perfil, el PDBQT sellado y el origen convertido a PDB."""
    from services.docking import preparer
    from services.docking.preparer_propio import receta_pdbqt
    from services.targets import perfil_receptor
    from utils import local_storage
    from utils.file_handlers import StoragePath

    monkeypatch.setattr(local_storage, "data_dir", lambda: tmp_path)
    atomos = [("N", "N", "N"), ("CA", "C", "C"), ("C", "C", "C"), ("O", "O", "OA")]
    origen, pdbqt = ["HEADER    TRANSFERASE"], []
    serie = 0
    for numero, residuo in enumerate(("ALA", "SER", "GLY", "LEU", "VAL"), start=1):
        for i, (nombre, elemento, tipo) in enumerate(atomos):
            serie += 1
            linea = _pdb("ATOM", serie, nombre, residuo, numero, (1.5 * numero, 0.4 * i, 0.0), elemento)
            origen.append(linea)
            pdbqt.append(_como_pdbqt(linea, tipo))
    archivo = tmp_path / "raw.pdb"
    archivo.write_bytes(("\n".join(origen + ["END"]) + "\n").encode("utf-8"))
    monkeypatch.setattr(preparer, "receptor_source_path_no_network", lambda pdb_id: archivo)

    datos_pdbqt = ("\n".join(pdbqt) + "\n").encode("utf-8")
    sha = hashlib.sha256(datos_pdbqt).hexdigest()
    perfil = {"schema": perfil_receptor.SCHEMA, "pdb_id": "USR_C1", "modo": perfil_receptor.MODO_PDBQT,
              "camino": "C", "receptor_sha256": sha, "chain": "A",
              "origen": {"formato": "pdb", "sha256_contenido": "e" * 64}}
    perfiles = {"USR_C1": perfil}
    monkeypatch.setattr(perfil_receptor, "cargar", lambda pdb_id: perfiles.get(pdb_id))
    receta = receta_pdbqt(perfil, CENTRO, LADO)
    logico = StoragePath.target_prepared("USR_C1", receta)
    local_storage.path_for(logico).parent.mkdir(parents=True, exist_ok=True)
    local_storage.path_for(logico).write_bytes(datos_pdbqt)
    corrida = _corrida(receta, modo="pdbqt_con_origen", receptor_path=logico, receptor_sha256=sha)
    return SimpleNamespace(archivo=archivo, receta=receta, corrida=corrida, perfiles=perfiles,
                           pdbqt=local_storage.path_for(logico))


def test_el_camino_c_con_origen_se_comprueba_con_su_receta(deposito_c):
    comprobado = origen_comprobado(deposito_c.corrida, "USR_C1")

    assert not isinstance(comprobado, str), comprobado
    assert comprobado.datos == deposito_c.archivo.read_bytes()
    assert comprobado.texto == deposito_c.archivo.read_bytes().decode("utf-8")


def test_un_origen_que_ya_no_corresponde_al_pdbqt_no_pasa(deposito_c):
    # La receta de C liga la corrida al PDBQT y al hash del origen SUBIDO, no al crudo
    # convertido: el crudo se exige que siga correspondiendo al PDBQT acoplado.
    texto = deposito_c.archivo.read_text(encoding="utf-8")
    movido = "\n".join(
        linea[:30] + f"{float(linea[30:38]) + 5.0:8.3f}" + linea[38:] if linea.startswith("ATOM") else linea
        for linea in texto.split("\n"))
    deposito_c.archivo.write_text(movido, encoding="utf-8")

    assert origen_comprobado(deposito_c.corrida, "USR_C1") == (
        "La estructura de origen ya no corresponde al PDBQT de esta corrida")


def test_otro_perfil_da_otra_receta_en_el_camino_c(deposito_c):
    deposito_c.perfiles["USR_C1"] = {**deposito_c.perfiles["USR_C1"],
                                     "origen": {"formato": "pdb", "sha256_contenido": "d" * 64}}
    assert origen_comprobado(deposito_c.corrida, "USR_C1") == RECETA_DISTINTA


def test_sin_perfil_el_camino_c_dice_por_que(deposito_c):
    deposito_c.perfiles.clear()
    assert origen_comprobado(deposito_c.corrida, "USR_C1") == (
        "No se encontró el perfil del receptor propio con el que se preparó esta corrida")


def test_un_pdbqt_alterado_no_sirve_para_comprobar_el_origen(deposito_c):
    deposito_c.pdbqt.write_bytes(deposito_c.pdbqt.read_bytes() + b"REMARK alterado\n")
    assert origen_comprobado(deposito_c.corrida, "USR_C1") == (
        "No se pudo comprobar la estructura de origen del receptor")


def test_las_razones_nuevas_se_leen_en_ingles():
    from core.i18n_plantillas import _PARECE_CASTELLANO, traducir

    for razon in ("No se encontró el perfil del receptor propio con el que se preparó esta corrida",
                  "La estructura de origen ya no corresponde al PDBQT de esta corrida"):
        for texto in (razon, f"{razon}: las distancias se miden desde la caja."):
            en = traducir(texto, "en")
            assert en != texto and not _PARECE_CASTELLANO.search(en), texto
