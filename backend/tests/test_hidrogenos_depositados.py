"""Hidrógenos depositados que contradicen la estructura: 3KK6 y 6S1Z no se podían preparar (2026-10-11).

Algunos depósitos traen los hidrógenos del refinamiento. En 3KK6 (PHENIX, ocupación 0) las 36 histidinas los llevan
pero ninguna en el anillo, y cinco cisteínas de puentes disulfuro llevan su HG. Meeko toma esos hidrógenos como
datos: con las His empata HIE y HID («tied for fewest missing and excess H») y con las Cys lee el HG como un segundo
enlace entre los dos residuos («Expected 4 paddings … but got 0»). `preparer` los retira antes de Meeko, sólo en
esos residuos y sólo cuando aparecen; el hash de la receta y el informe lo declaran sólo entonces, así que ningún
receptor que ya se preparaba cambia.
"""
from __future__ import annotations

import gzip
import json
import subprocess
import sys
from pathlib import Path

import pytest

from services.docking import preparer

RAIZ = Path(__file__).resolve().parents[2]


def _atomo(n: int, nombre: str, residuo: str, numero: int, xyz: tuple[float, float, float],
           elemento: str, cadena: str = "A") -> str:
    return (f"ATOM  {n:5d} {nombre:<4} {residuo:>3} {cadena}{numero:4d}    "
            f"{xyz[0]:8.3f}{xyz[1]:8.3f}{xyz[2]:8.3f}  1.00  0.00          {elemento:>2}\n")


def _his(numero: int, hidrogenos: tuple[str, ...]) -> str:
    pesados = ("N", "CA", "C", "O", "CB", "CG", "ND1", "CD2", "CE1", "NE2")
    lineas = [_atomo(i, n, "HIS", numero, (float(i), 0.0, 0.0), n[0]) for i, n in enumerate(pesados, 1)]
    lineas += [_atomo(20 + i, h, "HIS", numero, (float(i), 1.0, 0.0), "H") for i, h in enumerate(hidrogenos)]
    return "".join(lineas)


def _cys(numero: int, sg: tuple[float, float, float], con_hg: bool) -> str:
    texto = "".join(_atomo(i, n, "CYS", numero, (sg[0] - 3 + i * 0.5, sg[1], sg[2]), n[0])
                    for i, n in enumerate(("N", "CA", "C", "O", "CB"), 1))
    texto += _atomo(6, "SG", "CYS", numero, sg, "S") + _atomo(7, "HA", "CYS", numero, (sg[0], sg[1] + 2, sg[2]), "H")
    return texto + (_atomo(8, "HG", "CYS", numero, (sg[0] + 0.9, sg[1] + 0.9, sg[2]), "H") if con_hg else "")


def test_una_his_con_hidrogenos_y_ninguno_en_el_anillo_se_detecta():
    texto = _his(43, ("H", "HA", "HB2", "HB3", "HD2", "HE1"))
    filas = preparer.hidrogenos_depositados_contradictorios(texto)
    assert filas == [{"residue": "A:43", "name": "HIS", "removed": "all_h",
                      "reason": "hidrógenos depositados sin ninguno en ND1 ni NE2"}]
    limpio, retiradas = preparer.retirar_hidrogenos_depositados_contradictorios(texto)
    assert retiradas == filas
    # Se van todos sus hidrógenos y ningún átomo pesado.
    assert [l[12:16].strip() for l in limpio.splitlines()] == [
        "N", "CA", "C", "O", "CB", "CG", "ND1", "CD2", "CE1", "NE2"]


@pytest.mark.parametrize("hidrogenos", [(), ("H", "HD1"), ("H", "HE2"), ("HD1", "HE2"), ("DE2",)])
def test_una_his_que_decide_su_estado_o_no_trae_hidrogenos_no_se_toca(hidrogenos):
    texto = _his(90, hidrogenos)
    assert preparer.hidrogenos_depositados_contradictorios(texto) == []
    assert preparer.retirar_hidrogenos_depositados_contradictorios(texto) == (texto, [])


def test_una_his_sin_anillo_no_cuenta_porque_se_trunca():
    texto = "".join(l for l in _his(95, ("H", "HA")).splitlines(keepends=True)
                    if l[12:16].strip() not in ("ND1", "CE1", "NE2"))
    assert preparer.hidrogenos_depositados_contradictorios(texto) == []


def test_el_hg_de_una_cisteina_con_puente_disulfuro_se_retira_y_nada_mas():
    texto = _cys(36, (0.0, 0.0, 0.0), con_hg=True) + _cys(47, (2.05, 0.0, 0.0), con_hg=False)
    limpio, filas = preparer.retirar_hidrogenos_depositados_contradictorios(texto)
    assert filas == [{"residue": "A:36", "name": "CYS", "removed": "HG",
                      "reason": "HG en una cisteína con puente disulfuro con A:47"}]
    assert limpio == "".join(l for l in texto.splitlines(keepends=True) if l[12:16].strip() != "HG")
    assert sum(1 for l in limpio.splitlines() if l[12:16].strip() == "HA") == 2


def test_el_hg_de_una_cisteina_libre_se_conserva():
    texto = _cys(36, (0.0, 0.0, 0.0), con_hg=True) + _cys(47, (4.0, 0.0, 0.0), con_hg=True)
    assert preparer.hidrogenos_depositados_contradictorios(texto) == []


def test_el_hash_de_la_receta_solo_cambia_cuando_la_regla_actua(monkeypatch):
    args = dict(chains={"A"}, cofactors_whitelist=[], center=(0.0, 0.0, 0.0), size=(20.0, 20.0, 20.0))
    sin = _his(90, ("H", "HD1"))
    con = _his(43, ("H", "HA"))
    hash_sin, hash_con = preparer.receptor_recipe_hash(sin, **args), preparer.receptor_recipe_hash(con, **args)
    monkeypatch.setattr(preparer, "hidrogenos_depositados_contradictorios", lambda texto: [])
    assert preparer.receptor_recipe_hash(sin, **args) == hash_sin
    assert preparer.receptor_recipe_hash(con, **args) != hash_con


def _depositos():
    catalogo = json.loads((RAIZ / "curated_targets.json").read_text(encoding="utf-8"))
    for entrada in catalogo:
        ruta = RAIZ / "data" / "targets" / f"{entrada['pdb_id'].upper()}.pdb.gz"
        if ruta.is_file():
            with gzip.open(ruta, "rt", encoding="utf-8", errors="replace") as fh:
                yield entrada["pdb_id"].upper(), fh.read()


def test_la_regla_solo_actua_en_las_dos_entradas_que_no_se_preparaban():
    """Guardián de la receta 7: si actuara en otra entrada, su receptor y su hash cambiarían."""
    afectadas = {}
    for pdb_id, texto in _depositos():
        filas = preparer.hidrogenos_depositados_contradictorios(texto)
        if filas:
            afectadas[pdb_id] = sorted({(f["name"], f["removed"]) for f in filas}), len(filas)
    assert set(afectadas) == {"3KK6", "6S1Z"}, afectadas
    assert afectadas["6S1Z"] == ([("HIS", "all_h")], 1)
    # 3KK6: las 36 His de las dos cadenas y el HG de cada Cys de un puente disulfuro.
    assert afectadas["3KK6"][0] == [("CYS", "HG"), ("HIS", "all_h")]
    assert afectadas["3KK6"][1] >= 36 + 5


def test_prepare_target_aplica_la_regla_al_receptor_y_a_la_copia_del_rescoring():
    import inspect

    fuente = inspect.getsource(preparer.prepare_target)
    assert fuente.count("retirar_hidrogenos_depositados_contradictorios(") == 2
    assert 'report["deposited_h_removed"]' in fuente


def _entrada_de_meeko_3kk6(con_la_regla: bool) -> str:
    entrada = next(e for e in json.loads((RAIZ / "curated_targets.json").read_text(encoding="utf-8"))
                   if e["pdb_id"] == "3KK6")
    with gzip.open(RAIZ / "data" / "targets" / "3KK6.pdb.gz", "rt", encoding="utf-8") as fh:
        fuente = fh.read()
    centro = tuple(entrada[f"grid_center_{e}"] for e in "xyz")
    lado = tuple(entrada[f"grid_size_{e}"] for e in "xyz")
    filtrado = preparer.filter_pdb_content(fuente, entrada["chain"], keep_hetatm=True,
                                           cofactors_whitelist=entrada.get("cofactors_whitelist"),
                                           site_ligand=entrada["site_ligand"])
    filtrado = preparer.truncar_cadenas_laterales_incompletas(filtrado, centro, lado)[0]
    if con_la_regla:
        filtrado = preparer.retirar_hidrogenos_depositados_contradictorios(filtrado)[0]
    return filtrado


@pytest.mark.parametrize("con_la_regla", [False, True], ids=["antes", "despues"])
def test_meeko_prepara_3kk6_solo_con_la_regla(tmp_path, con_la_regla):
    """Con Meeko de verdad y sus mismas opciones de la receta. El control negativo reproduce el fallo del barrido."""
    pytest.importorskip("meeko", reason="Meeko no instalado en este equipo")
    entrada = tmp_path / "3KK6_A.pdb"
    entrada.write_text(_entrada_de_meeko_3kk6(con_la_regla), encoding="utf-8")
    proceso = subprocess.run(
        [sys.executable, "-m", "meeko.cli.mk_prepare_receptor", "--read_pdb", str(entrada),
         "-o", str(tmp_path / "salida"), "-p", "-j", "-a", "--default_altloc", "A",
         "--add_templates", str(preparer.RUTA_PLANTILLAS_COFACTORES)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600, cwd=tmp_path)
    if con_la_regla:
        assert proceso.returncode == 0, proceso.stderr[-1500:]
        plantillas = json.loads((tmp_path / "salida.json").read_text(encoding="utf-8"))["monomers"]
        his = {k: v["residue_template_key"] for k, v in plantillas.items() if v.get("input_resname") == "HIS"}
        assert len(his) == 18 and set(his.values()) == {"HIE"}
        cys = {k: v["residue_template_key"] for k, v in plantillas.items() if v.get("input_resname") == "CYS"}
        assert all(cys[k] == "CYX" for k in ("A:36", "A:37", "A:41", "A:47", "A:57", "A:159"))
    else:
        assert proceso.returncode != 0
        assert "tied for fewest missing and excess H" in proceso.stderr


def _protonacion(prep_extra: dict) -> tuple[dict, dict]:
    from services.dossier.localization import traducir_dossier
    from tests.test_preparacion_entrada import _auditar_con, _requisito

    prep = {"source": "meeko_report", "recipe_hash": "5" * 64, "chain": "A", "site_chains": ["A"],
            "removed_residues": [], "cofactors_outside_site": [],
            "protonation_method": "Meeko 0.7.1; asignación por plantilla, sin pH experimental declarado",
            **prep_extra}
    auditoria = _auditar_con(prep)
    return (_requisito(auditoria, "receptor.protonacion"),
            _requisito(traducir_dossier(auditoria, "en"), "receptor.protonacion"))


def test_preparacion_dice_que_hidrogenos_del_deposito_se_retiraron_en_los_dos_idiomas():
    from tests.test_dossier_en_ingles_completo import _parece_espanol

    retirados = [
        {"residue": "A:43", "name": "HIS", "removed": "all_h", "reason": "x"},
        {"residue": "A:90", "name": "HIS", "removed": "all_h", "reason": "x"},
        {"residue": "A:36", "name": "CYS", "removed": "HG", "reason": "x"},
    ]
    es, en = _protonacion({"deposited_h_removed": retirados})
    assert es["estado"] == "REVISAR"
    assert ("se retiraron antes de Meeko: 2 His sin hidrógeno en ND1 ni NE2" in es["razon"]
            and "y 1 HG de cisteínas con puente disulfuro." in es["razon"])
    assert "2 His without hydrogen on ND1 or NE2" in en["razon"] and "1 HG of disulfide-bonded cysteines" in en["razon"]
    assert not _parece_espanol(en["razon"]), en["razon"]


def test_sin_hidrogenos_retirados_preparacion_no_dice_nada():
    es, _ = _protonacion({})
    assert "El depósito traía hidrógenos" not in es["razon"]
