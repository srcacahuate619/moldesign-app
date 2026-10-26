"""M5-Zn sólo se ejecuta donde hay zinc o la familia curada lo respalda (decisión del 2026-10-04).

Medido sobre los 380 receptores del catálogo: 137 recibían el bloque M5-Zn —«metaloenzimas de zinc»—
y sólo 47 tienen zinc; en 90 el único metal observado era un Na, Mg o Ca de tampón o estructural.
`detectar_contexto_metalico` da `es_metalica = bool(fuentes)` y CUALQUIER ion observado es una fuente.

Y el dossier decidía por otra cosa que la pantalla: sólo miraba la familia curada, así que un receptor
con zinc observado y otra familia enseñaba el bloque en la tarjeta y no en el documento.

Aquí se fija: sólo zinc observado, familia curada o declaración de la persona dispara M5-Zn, y el dossier
sigue a la corrida (`m5_scientific_status`), con la familia como respaldo para corridas antiguas.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from services.pipeline.protocols.m5.ejecucion import ejecutar

SULFONAMIDA = "NS(=O)(=O)c1ccc(cc1)C(=O)N"
#: Un PDB que ningún perfil de M5-Zn reconoce: el bloque, si aplica, sale «fuera de diana».
PDB_AJENO = "9ZZZ"


def _pdb(tmp_path, *elementos: str) -> str:
    """Una estructura mínima con un ion por elemento, con la columna de elemento (77-78) bien puesta."""
    lineas = [
        "ATOM      1  N   ALA A   1      11.000  11.000  11.000  1.00 20.00           N",
    ]
    for i, el in enumerate(elementos, start=2):
        lineas.append(
            f"HETATM{i:5d} {el:<4s} {el:>3s} A{100 + i:4d}    {10.0 * i:8.3f}{10.0:8.3f}{10.0:8.3f}"
            f"  1.00 20.00          {el:>2s}"
        )
    ruta = tmp_path / ("receptor_" + "_".join(elementos or ("sin_iones",)) + ".pdb")
    ruta.write_text("\n".join(lineas) + "\nEND\n", encoding="utf-8")
    return str(ruta)


def _ejecutar(tmp_path, elementos: tuple[str, ...], familia: str):
    return ejecutar(
        smiles=SULFONAMIDA,
        target_pdb_id=PDB_AJENO,
        target_family=familia,
        vina_kcal_mol=-7.2,
        xgb_prob=0.84,
        ruta_receptor=_pdb(tmp_path, *elementos),
    )


# ── El guardián de la estructura de prueba tiene que ver ─────────────


def test_el_pdb_de_prueba_se_lee_como_se_espera(tmp_path):
    from services.chemistry.protein_surgery import detect_metals_in_protein

    metales = detect_metals_in_protein(_pdb(tmp_path, "ZN", "NA"))
    assert sorted(m["element"] for m in metales) == ["NA", "ZN"]
    # El átomo N del polímero (registro ATOM) no cuenta como metal.
    assert detect_metals_in_protein(_pdb(tmp_path)) == []


# ── Un ion que no es zinc ya no dispara el bloque ────────────────────


@pytest.mark.parametrize("ion", ["NA", "MG", "CA", "K"])
def test_un_ion_que_no_es_zinc_no_dispara_m5_zn(tmp_path, ion):
    assert _ejecutar(tmp_path, (ion,), "kinase") is None


def test_varios_iones_sin_zinc_tampoco(tmp_path):
    assert _ejecutar(tmp_path, ("NA", "MG", "CA"), "protease") is None


# ── Lo que sí la dispara ─────────────────────────────────────────────


def test_el_zinc_observado_la_dispara_aunque_la_familia_no_sea_metaloenzima(tmp_path):
    salida = _ejecutar(tmp_path, ("ZN",), "kinase")
    assert salida is not None
    assert salida.estado == "REVIEW_OUT_OF_VALIDATED_TARGET"
    # Y dice lo cierto: hay un ion, pero el catálogo no la clasifica como metaloenzima.
    assert any("no clasifica esta diana como metaloenzima" in aviso for aviso in salida.avisos)


def test_zinc_junto_a_otros_iones_cuenta_como_zinc(tmp_path):
    assert _ejecutar(tmp_path, ("ZN", "NA", "CA"), "protease") is not None


def test_la_familia_curada_la_dispara_aunque_el_unico_ion_no_sea_zinc(tmp_path):
    # El catálogo la declara metaloenzima: ese respaldo basta, y el aviso de discrepancia viaja.
    assert _ejecutar(tmp_path, ("NA",), "metalloenzyme") is not None


def test_la_familia_curada_sin_ningun_ion_observado_tambien(tmp_path):
    salida = _ejecutar(tmp_path, (), "metalloenzyme")
    assert salida is not None
    assert any("no se observó ningún ion metálico" in aviso for aviso in salida.avisos)


def test_sin_iones_y_sin_familia_no_hay_bloque(tmp_path):
    assert _ejecutar(tmp_path, (), "kinase") is None


# ── El dossier sigue a la corrida, no sólo a la familia ──────────────


def _campos_dossier(eval_result):
    from services.dossier.bloques_protocolo import campos_de_m5_zn
    from services.dossier.model import Campo, _campo_dato, _v

    return [
        c.as_dict()
        for c in campos_de_m5_zn(
            Campo, _campo_dato, _v, eval_result, {"top_pose_affinity": -7.2}, SimpleNamespace(pdb_id=PDB_AJENO)
        )
    ]


def test_el_dossier_muestra_el_bloque_si_la_corrida_ejecuto_m5_aunque_la_familia_no_sea_metaloenzima():
    resultado = SimpleNamespace(
        target_family="kinase", m5_scientific_status="REVIEW_OUT_OF_VALIDATED_TARGET", ums_warhead=0.9
    )
    campos = _campos_dossier(resultado)
    assert any(c["etiqueta"] == "Protocolo M5-Zn" for c in campos), campos


def test_el_dossier_no_muestra_el_bloque_si_la_corrida_no_lo_ejecuto_y_la_familia_no_lo_pide():
    # El caso del Na de tampón: `ejecutar` devolvió None, las columnas m5 quedaron a NULL.
    resultado = SimpleNamespace(target_family="kinase", m5_scientific_status=None)
    assert _campos_dossier(resultado) == []


def test_corridas_anteriores_a_la_columna_siguen_decidiendo_por_la_familia():
    # Control de compatibilidad: una corrida antigua de una metaloenzima no pierde su bloque.
    resultado = SimpleNamespace(target_family="metalloenzyme", m5_scientific_status=None, ums_score=0.9)
    campos = _campos_dossier(resultado)
    assert any(c["etiqueta"] == "Protocolo M5-Zn" for c in campos), campos
