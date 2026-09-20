"""El lector de SDF frente a salidas REALES de `mk_export`.

**El defecto que cubre.** `parse_vina_output_sdf` reconocía la cabecera de una
propiedad con ``re.match(r"^>\\s+<([^>]+)>\\s*$", ...)``: el ``$`` exigía que la
línea acabara justo tras el ángulo de cierre. Meeko escribe
``>  <meeko>  (1) `` —con el índice del registro detrás—, así que ninguna de sus
propiedades casaba y la función devolvía ``[]`` para *todo* SDF de Meeko. Open
Babel escribe ``>  <REMARK>`` sin sufijo y sí casaba, de modo que el ancla se
ajustó al camino de respaldo mientras el principal llevaba roto desde siempre.

Medido el 2026-09-19 sobre `ENS-PILOT-01`: **172 acoplamientos, 171 por el
respaldo de Open Babel, cero por Meeko.** El archivo entregado perdía entonces
los hidrógenos no polares y, en macrociclos, dos carbonos del anillo salían como
pseudo-átomos con el ciclo abierto.

**Por qué estas pruebas usan archivos y no cadenas.** El defecto sobrevivió a la
batería entera porque las pruebas existentes construían la cabecera a mano, con
el formato del docstring —``> <meeko>``— que ningún programa emite. Un guardián
que valida la documentación en vez del artefacto no vigila nada. Las fixtures de
`fixtures/meeko_export/` las escribieron Vina y `mk_export`; su procedencia está
en el README de esa carpeta.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from services.docking.vina_service import _is_valid_sdf
from utils.file_handlers import (
    fusionar_rmsd_desde_pdbqt,
    parse_vina_output_pdbqt,
    parse_vina_output_sdf,
)

FIXTURES = Path(__file__).parent / "fixtures" / "meeko_export"

#: El ancla que causaba el defecto, conservada para poder demostrar que estas
#: pruebas lo detectan. Si alguien la reintroduce, los casos de abajo fallan.
REGEX_CON_EL_DEFECTO = re.compile(r"^>\s+<([^>]+)>\s*$")


def leer(nombre: str) -> str:
    """Como lo lee producción: `vina_service` usa `errors="replace"`."""
    return (FIXTURES / nombre).read_text(encoding="utf-8", errors="replace")


def composicion(sdf: str, registro: int = 0) -> tuple[int, int, dict[str, int]]:
    """(átomos, enlaces, conteo por símbolo) de un molblock V2000.

    Se lee el texto y no RDKit, por el mismo motivo que `parse_vina_output_sdf`:
    sanear la molécula podría corregir en memoria justo lo que se quiere medir en
    el archivo.
    """
    lineas = sdf.split("$$$$")[registro].splitlines()
    indice = next(i for i, linea in enumerate(lineas) if "V2000" in linea)
    atomos = int(lineas[indice][0:3])
    enlaces = int(lineas[indice][3:6])
    conteo: dict[str, int] = {}
    for linea in lineas[indice + 1:indice + 1 + atomos]:
        simbolo = linea[31:34].strip()
        conteo[simbolo] = conteo.get(simbolo, 0) + 1
    return atomos, enlaces, conteo


# ─────────────────────────────────────────────────────────────────────────────
# La cabecera real, y la prueba de que estas pruebas ven
# ─────────────────────────────────────────────────────────────────────────────

def test_meeko_no_escribe_la_cabecera_que_documentaba_el_parser():
    """La cabecera real trae el índice del registro detrás del nombre."""
    sdf = leer("paracetamol_9_poses.sdf")
    cabeceras = [x for x in sdf.splitlines() if x.lstrip().startswith(">")]

    assert cabeceras, "la fixture debería traer propiedades"
    assert all("<meeko>" in c for c in cabeceras)
    # Lo que de verdad emite mk_export, con su sufijo y su espacio final.
    assert cabeceras[0].rstrip("\r") == ">  <meeko>  (1) "
    # Y NO lo que el docstring ilustraba.
    assert "> <meeko>\n" not in sdf


def test_el_ancla_del_defecto_no_ve_ninguna_cabecera_real():
    """Autotest del guardián: con el regex viejo, esto no detecta nada.

    Sin este caso, las pruebas de abajo podrían pasar por accidente y nadie
    sabría que cubren el defecto. Es la restricción 2 de AGENTS.md: un guardián
    tiene que demostrar que ve.
    """
    sdf = leer("paracetamol_9_poses.sdf")
    cabeceras = [x.strip() for x in sdf.splitlines() if x.lstrip().startswith(">")]

    assert not any(REGEX_CON_EL_DEFECTO.match(c) for c in cabeceras), (
        "el regex con el defecto no debería casar con ninguna cabecera de Meeko; "
        "si casa, esta prueba ya no distingue el arreglo del defecto"
    )


def test_el_ancla_del_defecto_si_veia_las_cabeceras_de_open_babel():
    """Por qué el defecto pasó inadvertido: el respaldo sí casaba."""
    assert REGEX_CON_EL_DEFECTO.match(">  <REMARK>")
    assert REGEX_CON_EL_DEFECTO.match(">  <MODEL>")


# ─────────────────────────────────────────────────────────────────────────────
# El camino principal entrega sus poses
# ─────────────────────────────────────────────────────────────────────────────

def test_el_sdf_real_de_meeko_pasa_la_validacion_previa():
    """`_is_valid_sdf` es la puerta anterior al parser; no era ella la rota."""
    assert _is_valid_sdf(leer("paracetamol_9_poses.sdf")) is True


def test_el_sdf_real_de_meeko_entrega_una_pose_por_registro():
    sdf = leer("paracetamol_9_poses.sdf")
    poses = parse_vina_output_sdf(sdf)

    assert len(poses) == sdf.count("$$$$") == 9
    assert [p["rank"] for p in poses] == list(range(1, 10))


def test_las_afinidades_del_sdf_son_las_que_escribio_vina():
    """Meeko copia `free_energy` de las mismas líneas `REMARK VINA RESULT`."""
    desde_sdf = parse_vina_output_sdf(leer("paracetamol_9_poses.sdf"))
    desde_pdbqt = parse_vina_output_pdbqt(leer("paracetamol_9_poses.pdbqt"))

    assert len(desde_sdf) == len(desde_pdbqt)
    for sdf_pose, pdbqt_pose in zip(desde_sdf, desde_pdbqt, strict=True):
        assert sdf_pose["affinity"] == pytest.approx(pdbqt_pose["affinity"], abs=1e-3)


def test_las_afinidades_estan_ordenadas_de_mejor_a_peor():
    afinidades = [p["affinity"] for p in parse_vina_output_sdf(leer("paracetamol_9_poses.sdf"))]
    assert afinidades == sorted(afinidades)


# ─────────────────────────────────────────────────────────────────────────────
# El RMSD no está en el SDF, y un 0.0 entregado sería una afirmación falsa
# ─────────────────────────────────────────────────────────────────────────────

def test_meeko_no_exporta_rmsd_y_el_parser_no_se_lo_inventa():
    poses = parse_vina_output_sdf(leer("paracetamol_9_poses.sdf"))
    assert all(p["rmsd_lb"] == 0.0 and p["rmsd_ub"] == 0.0 for p in poses)


def test_la_fusion_trae_el_rmsd_del_pdbqt_sin_tocar_la_afinidad():
    sdf = parse_vina_output_sdf(leer("paracetamol_9_poses.sdf"))
    pdbqt_txt = leer("paracetamol_9_poses.pdbqt")
    fusionadas, diagnostico = fusionar_rmsd_desde_pdbqt(sdf, pdbqt_txt)

    assert diagnostico["fusionado"] is True
    assert diagnostico["afinidades_discrepantes"] == []

    esperado = parse_vina_output_pdbqt(pdbqt_txt)
    for resultado, referencia, original in zip(fusionadas, esperado, sdf, strict=True):
        assert resultado["rmsd_lb"] == referencia["rmsd_lb"]
        assert resultado["rmsd_ub"] == referencia["rmsd_ub"]
        assert resultado["affinity"] == original["affinity"]


def test_sin_la_fusion_el_dossier_afirmaria_que_todas_las_poses_son_la_primera():
    """El daño concreto que evita la fusión, escrito como medida.

    `rmsd_lb`/`rmsd_ub` a 0.0 no es un hueco en la tabla de poses del dossier:
    afirma que esa pose es idéntica a la pose 1.
    """
    fusionadas, _ = fusionar_rmsd_desde_pdbqt(
        parse_vina_output_sdf(leer("paracetamol_9_poses.sdf")),
        leer("paracetamol_9_poses.pdbqt"),
    )

    assert fusionadas[0]["rmsd_lb"] == 0.0, "la pose 1 sí es idéntica a sí misma"
    distintas_de_la_primera = [p for p in fusionadas[1:] if p["rmsd_ub"] > 0.0]
    assert len(distintas_de_la_primera) == len(fusionadas) - 1


def test_la_fusion_se_abstiene_si_los_recuentos_no_coinciden():
    """Emparejar de más pondría el RMSD de una pose sobre otra geometría."""
    sdf = parse_vina_output_sdf(leer("paracetamol_9_poses.sdf"))
    fusionadas, diagnostico = fusionar_rmsd_desde_pdbqt(sdf[:4], leer("paracetamol_9_poses.pdbqt"))

    assert diagnostico["fusionado"] is False
    assert diagnostico["poses_en_sdf"] == 4
    assert diagnostico["poses_en_pdbqt"] == 9
    assert all(p["rmsd_lb"] == 0.0 and p["rmsd_ub"] == 0.0 for p in fusionadas)


def test_la_fusion_declara_una_afinidad_que_no_cuadra():
    """Ambos números salen de la misma línea de Vina: divergir es un defecto."""
    sdf = parse_vina_output_sdf(leer("paracetamol_9_poses.sdf"))
    sdf[2]["affinity"] = sdf[2]["affinity"] + 5.0

    _, diagnostico = fusionar_rmsd_desde_pdbqt(sdf, leer("paracetamol_9_poses.pdbqt"))

    assert [d["rank"] for d in diagnostico["afinidades_discrepantes"]] == [3]


def test_la_fusion_no_muta_la_lista_que_recibe():
    sdf = parse_vina_output_sdf(leer("paracetamol_9_poses.sdf"))
    antes = [dict(p) for p in sdf]

    fusionar_rmsd_desde_pdbqt(sdf, leer("paracetamol_9_poses.pdbqt"))

    assert sdf == antes


# ─────────────────────────────────────────────────────────────────────────────
# Macrociclos: lo que el respaldo rompía
# ─────────────────────────────────────────────────────────────────────────────

def test_el_macrociclo_vuelve_con_la_composicion_del_conformero_de_entrada():
    """G5 de `pose_recovery` compara exactamente esto, y con el respaldo fallaba.

    Open Babel no reconoce los tipos de pegado que Meeko inserta al abrir un
    macrociclo: escribía dos carbonos del anillo como pseudo-átomos `*` y
    entregaba 17 átomos con 14 enlaces —el ciclo abierto— donde corresponden 17
    y 17. Medido en `ENS-PILOT-01`: 0 de 9 poses recuperables en los dos
    macrociclos, frente a 9 de 9 en los ocho ligandos restantes.
    """
    entrada = composicion(leer("exaltolida_conformero_de_entrada.sdf"))
    salida = composicion(leer("exaltolida_macrociclo.sdf"))

    assert salida == entrada
    assert salida[2] == {"C": 15, "H": 28, "O": 2}


def test_el_macrociclo_no_trae_pseudoatomos_de_pegado():
    _, _, conteo = composicion(leer("exaltolida_macrociclo.sdf"))
    assert "*" not in conteo


def test_el_anillo_del_macrociclo_vuelve_cerrado():
    """Tantos enlaces como átomos: una molécula acíclica tendría uno menos."""
    atomos, enlaces, _ = composicion(leer("exaltolida_macrociclo.sdf"))
    assert enlaces == atomos


def test_todas_las_poses_del_macrociclo_conservan_el_anillo():
    sdf = leer("exaltolida_macrociclo.sdf")
    registros = sdf.count("$$$$")

    assert registros >= 2
    for indice in range(registros):
        atomos, enlaces, conteo = composicion(sdf, indice)
        assert enlaces == atomos
        assert "*" not in conteo


# ─────────────────────────────────────────────────────────────────────────────
# Las puertas de `pose_recovery` sobre el archivo que ahora se entrega
# ─────────────────────────────────────────────────────────────────────────────

def bloques_pdbqt(texto: str) -> list[str]:
    bloques: list[str] = []
    actual: list[str] = []
    for linea in texto.splitlines():
        if linea.startswith("MODEL"):
            actual = []
        elif linea.startswith("ENDMDL"):
            bloques.append("\n".join(actual))
        else:
            actual.append(linea)
    return bloques


@pytest.mark.parametrize("sdf_nombre, pdbqt_nombre", [
    ("paracetamol_9_poses.sdf", "paracetamol_9_poses.pdbqt"),
    ("exaltolida_macrociclo.sdf", "exaltolida_macrociclo.pdbqt"),
])
def test_g6_empareja_cada_coordenada_entregada_con_el_registro(sdf_nombre, pdbqt_nombre):
    """El SDF de Meeko trae los hidrógenos no polares; G6 no debe confundirse.

    G6 recorre las coordenadas del PDBQT y exige UNA sola contrapartida en el
    registro a 0.002 Å. Los hidrógenos de más quedan sin emparejar, que es lo
    correcto; lo que había que descartar es que alguno cayera tan cerca de un
    pesado como para romper la biyección.
    """
    from services.docking.pose_recovery import (
        TOLERANCIA_A,
        _atomos_de_registro_sdf,
        _coordenadas_de_pdbqt,
        _correspondencia_geometrica,
        _registros,
    )

    registros = _registros(leer(sdf_nombre))
    bloques = bloques_pdbqt(leer(pdbqt_nombre))
    assert len(registros) == len(bloques) >= 3

    for registro, bloque in zip(registros, bloques, strict=True):
        atomos = _atomos_de_registro_sdf(registro)
        entregadas, _pseudo = _coordenadas_de_pdbqt(bloque)
        emparejadas, maximo = _correspondencia_geometrica(entregadas, atomos, TOLERANCIA_A)
        assert emparejadas == len(entregadas)
        assert maximo <= TOLERANCIA_A


def test_g5_del_macrociclo_reconoce_el_conformero_que_se_acoplo():
    """Con el respaldo esto daba `{'C': 13, 'O': 2, '*': 2}` y G5 rechazaba.

    Medido en `ENS-PILOT-01` antes del arreglo: 0 de 9 poses recuperables en
    muscona y en exaltólida, frente a 9 de 9 en los ocho ligandos no
    macrocíclicos.
    """
    from services.docking.pose_recovery import (
        _atomos_de_registro_sdf,
        _pesados,
        _registros,
    )

    entrada = _pesados(
        _atomos_de_registro_sdf(_registros(leer("exaltolida_conformero_de_entrada.sdf"))[0])
    )
    assert entrada == {"C": 15, "O": 2}

    for registro in _registros(leer("exaltolida_macrociclo.sdf")):
        assert _pesados(_atomos_de_registro_sdf(registro)) == entrada


def test_los_pseudoatomos_de_pegado_siguen_descartandose_del_pdbqt():
    """El PDBQT del macrociclo sí los trae; el filtro por tipo debe verlos."""
    from services.docking.pose_recovery import _coordenadas_de_pdbqt

    for bloque in bloques_pdbqt(leer("exaltolida_macrociclo.pdbqt")):
        _coords, pseudoatomos = _coordenadas_de_pdbqt(bloque)
        assert pseudoatomos == 2


# ─────────────────────────────────────────────────────────────────────────────
# Lo que el arreglo NO podía relajar
# ─────────────────────────────────────────────────────────────────────────────

def test_el_invariante_todo_o_nada_sigue_vigente():
    """Un registro sin afinidad invalida la lista entera.

    Las posiciones de esta lista se emparejan con los bloques PDBQT originales;
    saltarse un registro pondría un score sobre otra geometría. Quitar el ancla
    del regex no podía relajar esto.
    """
    sdf = leer("paracetamol_9_poses.sdf")
    registros = sdf.split("$$$$")
    # Se deja el registro sin su propiedad, conservando el resto del archivo.
    mutilado = registros[0].replace(">  <meeko>  (1) ", ">  <otra_cosa>  (1) ", 1)
    reconstruido = "$$$$".join([mutilado] + registros[1:])

    assert parse_vina_output_sdf(reconstruido) == []


def test_el_sdf_de_open_babel_sigue_leyendose():
    """El respaldo debe seguir funcionando: ahora sí como respaldo."""
    registro = (
        "molecula\n"
        "  OpenBabel\n\n"
        "  1  0  0  0  0  0  0  0  0  0999 V2000\n"
        "    0.0000    0.0000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0\n"
        "M  END\n"
        ">  <REMARK>\n"
        "VINA RESULT:      -7.3      1.234      5.678\n\n"
        "$$$$\n"
    )
    poses = parse_vina_output_sdf(registro)

    assert poses == [{"rank": 1, "affinity": -7.3, "rmsd_lb": 1.234, "rmsd_ub": 5.678}]


def test_el_formato_heredado_sigue_leyendose():
    registro = "molecula\n> <minimizedAffinity>\n-8.5\n\n$$$$\n"
    assert parse_vina_output_sdf(registro) == [
        {"rank": 1, "affinity": -8.5, "rmsd_lb": 0.0, "rmsd_ub": 0.0}
    ]
