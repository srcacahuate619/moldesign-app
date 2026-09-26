"""DOCK-003 con margen de sitio, disponibilidad del catálogo, DOCK-012 y panel de Bowes.

Contexto (verificación del 2026-09-26): la guarda de cofactores de la fase 1
bloqueaba cualquier cofactor sin plantilla, también a 30 Å del sitio (el FMN
de la flavodoxina fusionada a CB1 en 5TGZ). Ahora se aplica el mismo margen
que a los residuos que pierde Meeko.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import math
from pathlib import Path

import pytest

from services.docking import preparer
from services.docking.preparer import (
    MARGEN_SITIO_A,
    cofactores_sin_plantilla,
    retirar_cofactores_fuera_del_sitio,
)

RAIZ = Path(__file__).resolve().parents[2]
CAJA = ((0.0, 0.0, 0.0), (10.0, 10.0, 10.0))  # de -5 a 5 en cada eje


def _hetatm(serial, nombre, resname, cadena, num, x, y=0.0, z=0.0, elemento="C"):
    return (f"HETATM{serial:5d} {nombre:<4} {resname:>3} {cadena}{num:>4}    "
            f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00 20.00          {elemento:>2}")


def _pdb(*lineas):
    return "\n".join(lineas) + "\nEND\n"


def test_cofactor_sin_plantilla_en_el_sitio_bloquea_y_lejano_no():
    # NTP no está en Meeko ni en la biblioteca local: sirve de cofactor sin plantilla.
    raw = _pdb(
        _hetatm(1, "P", "NTP", "A", 500, 1.0, elemento="P"),      # dentro de la caja
        _hetatm(2, "P", "NTP", "A", 600, 40.0, elemento="P"),     # a 35 Å
    )
    en_sitio, fuera = cofactores_sin_plantilla(
        raw, cadenas={"A"}, site_ligand=None, cofactors_whitelist=["NTP"], center=CAJA[0], size=CAJA[1])
    assert [f["name"] for f in en_sitio] == ["NTP"]
    assert [(f["name"], f["action"]) for f in fuera] == [("NTP", "retirado")]


def test_los_cofactores_con_plantilla_local_no_bloquean():
    """El hemo bloqueaba cualquier CYP; ahora su plantilla viaja con el repositorio."""
    from services.docking.preparer import residuos_con_plantilla

    con_plantilla = residuos_con_plantilla()
    for res in ("HEM", "HEC", "FAD", "FMN", "NAD", "NAP", "ADP", "ATP", "SAM", "SF4"):
        assert res in con_plantilla, res
    # Meeko 0.7.1 ya traía los fosfo-residuos: la fase 1 los bloqueaba sin serlo.
    for res in ("SEP", "TPO", "PTR"):
        assert res in con_plantilla, res
    raw = _pdb(_hetatm(1, "FE", "HEM", "A", 500, 1.0, elemento="FE"))
    assert cofactores_sin_plantilla(
        raw, cadenas={"A"}, site_ligand=None, cofactors_whitelist=["HEM"],
        center=CAJA[0], size=CAJA[1]) == ([], [])


def test_las_plantillas_de_cofactores_se_reconstruyen_igual():
    """`--check` del generador: mismos bytes desde el CCD versionado."""
    import subprocess

    ruta = RAIZ / "scripts" / "build_meeko_cofactor_templates.py"
    r = subprocess.run([sys.executable, str(ruta), "--check"], capture_output=True, text=True, cwd=RAIZ)
    assert r.returncode == 0, r.stdout + r.stderr


def test_el_margen_es_el_mismo_que_para_residuos_perdidos():
    # A 5 + 6 Å del centro: en el borde del margen, cuenta como sitio.
    borde = _pdb(_hetatm(1, "P", "NTP", "A", 600, 5.0 + MARGEN_SITIO_A, elemento="P"))
    lejos = _pdb(_hetatm(1, "P", "NTP", "A", 600, 5.0 + MARGEN_SITIO_A + 0.01, elemento="P"))
    kw = dict(cadenas={"A"}, site_ligand=None, cofactors_whitelist=["NTP"], center=CAJA[0], size=CAJA[1])
    assert cofactores_sin_plantilla(borde, **kw)[0]
    assert not cofactores_sin_plantilla(lejos, **kw)[0]


def test_otra_cadena_y_ligando_del_sitio_no_cuentan():
    raw = _pdb(
        _hetatm(1, "P", "NTP", "B", 500, 1.0, elemento="P"),      # cadena no pedida
        _hetatm(2, "C1", "ATP", "A", 700, 1.0),                   # es el ligando del sitio
    )
    en_sitio, fuera = cofactores_sin_plantilla(
        raw, cadenas={"A"}, site_ligand="ATP", cofactors_whitelist=["NTP"],
        center=CAJA[0], size=CAJA[1])
    assert en_sitio == [] and fuera == []


# ── Cadenas laterales incompletas ──────────────────────────────────────


def _atom(serial, nombre, resname, cadena, num, x, elemento="C"):
    return (f"ATOM  {serial:5d} {nombre:<4} {resname:>3} {cadena}{num:>4}    "
            f"{x:8.3f}{0.0:8.3f}{0.0:8.3f}  1.00 20.00          {elemento:>2}")


def test_una_lisina_sin_cadena_lateral_se_trunca_a_ala():
    from services.docking.preparer import truncar_cadenas_laterales_incompletas

    raw = _pdb(*(_atom(i + 1, a, "LYS", "A", 10, 1.0 + i * 0.1,
                       "N" if a == "N" else "C") for i, a in enumerate(["N", "CA", "C", "O", "CB"])))
    salida, filas = truncar_cadenas_laterales_incompletas(raw, CAJA[0], CAJA[1])
    assert [f["action"] for f in filas] == ["truncado a ALA"]
    assert filas[0]["atoms_missing"] == ["CD", "CE", "CG", "NZ"]
    assert filas[0]["site_critical"] is True
    assert {l[17:20] for l in salida.splitlines() if l.startswith("ATOM")} == {"ALA"}


def test_sin_cb_se_trunca_a_gly_y_un_residuo_completo_no_se_toca():
    from services.docking.preparer import truncar_cadenas_laterales_incompletas

    sin_cb = _pdb(*(_atom(i + 1, a, "LYS", "A", 10, 1.0 + i * 0.1,
                          "N" if a == "N" else "C") for i, a in enumerate(["N", "CA", "C", "O"])))
    salida, filas = truncar_cadenas_laterales_incompletas(sin_cb, CAJA[0], CAJA[1])
    assert [f["action"] for f in filas] == ["truncado a GLY"]
    assert {l[17:20] for l in salida.splitlines() if l.startswith("ATOM")} == {"GLY"}

    completo = _pdb(*(_atom(i + 1, a, "SER", "A", 11, 1.0 + i * 0.1,
                            "O" if a.startswith("O") else ("N" if a == "N" else "C"))
                      for i, a in enumerate(["N", "CA", "C", "O", "CB", "OG"])))
    assert truncar_cadenas_laterales_incompletas(completo, CAJA[0], CAJA[1]) == (completo, [])


def test_el_truncado_no_inventa_coordenadas_ni_pierde_cadenas():
    """Determinista por construcción: sólo se quitan átomos y se renombra el residuo.

    Es la razón de no usar PDBFixer: su `addMissingAtoms` daba rotámeros
    distintos entre procesos para 5VA1 y cambiaba los bytes del receptor.
    """
    from services.docking.preparer import truncar_cadenas_laterales_incompletas

    raw = _pdb(
        *(_atom(i + 1, a, "GLU", "A", 10, 1.0 + i * 0.1, "N" if a == "N" else "C")
          for i, a in enumerate(["N", "CA", "C", "O", "CB"])),
        *(_atom(i + 10, a, "GLU", "B", 10, 1.0 + i * 0.1, "N" if a == "N" else "C")
          for i, a in enumerate(["N", "CA", "C", "O", "CB"])),
    )
    salida, filas = truncar_cadenas_laterales_incompletas(raw, CAJA[0], CAJA[1])
    entrada_xyz = [l[30:54] for l in raw.splitlines() if l.startswith("ATOM")]
    salida_xyz = [l[30:54] for l in salida.splitlines() if l.startswith("ATOM")]
    assert entrada_xyz == salida_xyz, "el truncado no debe mover ningún átomo"
    assert sorted(f["chain"] for f in filas) == ["A", "B"]


# ── Disponibilidad del catálogo ────────────────────────────────────────


def _generador():
    ruta = RAIZ / "scripts" / "generate_catalog_availability.py"
    spec = importlib.util.spec_from_file_location("generate_catalog_availability", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_el_inventario_coincide_con_la_funcion_de_prepare_target():
    """Lo mismo que `--check`: si el código o el catálogo cambian, esto cae."""
    g = _generador()
    anterior = json.loads(g.DESTINO.read_text(encoding="utf-8"))
    assert g.serializar(g.conservar_medidas(g.construir(), anterior)) == g.DESTINO.read_text(encoding="utf-8")


def test_el_inventario_no_lleva_rutas_de_la_maquina_que_midio():
    texto = (RAIZ / "backend" / "data" / "disponibilidad_catalogo.json").read_text(encoding="utf-8")
    assert ":\\" not in texto and "/home/" not in texto and "python-embed" not in texto


def test_las_dianas_recuperadas_siguen_disponibles():
    """Las que bloqueaban antes del 2026-09-26 y ahora se preparan.

    4NY4 (CYP3A4) y 2NNJ/4EJJ/4O1Z por el hemo; 6GUE y 4E4N por fosfo-residuos;
    5TGZ por el FMN de su proteína de fusión; 1AJ6, 1BN1 y 1GPK por cadenas
    laterales incompletas. Medido con el barrido real de Meeko.
    """
    from services.targets.disponibilidad import motivo_no_disponible

    for pdb_id in ("4NY4", "2NNJ", "4EJJ", "4O1Z", "6GUE", "4E4N", "5TGZ",
                   "1AJ6", "1BN1", "1GPK", "5VA1", "4NC3"):
        assert motivo_no_disponible(pdb_id) is None, pdb_id


def test_el_inventario_declara_lo_que_todavia_no_se_puede_preparar():
    datos = json.loads((RAIZ / "backend" / "data" / "disponibilidad_catalogo.json").read_text(encoding="utf-8"))
    assert datos["receta_receptor"] == preparer.RECEPTOR_RECIPE_VERSION
    # No es una cifra que deba crecer sin que alguien lo mire.
    assert len(datos["no_disponibles"]) <= 20, sorted(datos["no_disponibles"])
    for pdb_id, fila in datos["no_disponibles"].items():
        assert fila["motivo"].strip(), pdb_id


def test_el_modelo_target_se_lee_disponible_por_defecto():
    from core.models import Target

    campos = Target.model_fields
    assert campos["disponible"].default is True
    assert campos["motivo_no_disponible"].default is None


# ── DOCK-012 ───────────────────────────────────────────────────────────


def _rotar(coords, angulo):
    c, s = math.cos(angulo), math.sin(angulo)
    return [(c * x - s * y, s * x + c * y, z) for x, y, z in coords]


def _pdbqt(tmp_path, coords):
    lineas = [f"ATOM  {i + 1:5d}  C   LIG A   1    {x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00     0.000 C"
              for i, (x, y, z) in enumerate(coords)]
    ruta = tmp_path / f"lig_{len(list(tmp_path.iterdir()))}.pdbqt"
    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    return ruta


@pytest.mark.parametrize("angulo", [0.0, math.pi / 4, math.pi / 3, 1.1])
def test_el_aviso_de_caja_no_depende_de_la_orientacion(tmp_path, angulo):
    from services.docking.vina_service import _check_ligand_fits_box

    varilla = [(i * 1.5, 0.0, 0.0) for i in range(11)]            # 15 Å de largo
    caja = (18.0, 18.0, 18.0)                                       # 15 + 4 > 18: no cabe
    assert _check_ligand_fits_box(_pdbqt(tmp_path, _rotar(varilla, angulo)), caja, "TEST")
    holgada = (20.0, 20.0, 20.0)                                    # 15 + 4 < 20: cabe
    assert _check_ligand_fits_box(_pdbqt(tmp_path, _rotar(varilla, angulo)), holgada, "TEST") is None


# ── Panel de selectividad ──────────────────────────────────────────────


def test_panel_por_defecto_sin_cyp3a4_y_sugeridas_aparte():
    from services.docking.selectivity import ANTI_DIANAS_BOWES_2012, ANTI_TARGET_PANEL

    por_defecto = {t["pdb_id"] for t in ANTI_TARGET_PANEL}
    assert por_defecto == {"5VA1", "4NC3"}
    sugeridas = {t["pdb_id"] for t in ANTI_DIANAS_BOWES_2012}
    assert not por_defecto & sugeridas
    # Estructuras que el catálogo etiqueta como humanas y no lo son.
    assert not sugeridas & {"4BVN", "1GPK", "6Y5A"}


@pytest.mark.asyncio
async def test_una_sugerida_elegida_conserva_su_categoria():
    from services.docking.selectivity import seleccionar_anti_dianas

    class Repo:
        async def get_target_by_pdb_id(self, pdb_id):
            return type("Fila", (), {"name": "catálogo", "chain": "R", "affinity_threshold": -7.0,
                                     "anti_target_risk": None})()

    elegidas, desconocidas = await seleccionar_anti_dianas(["7E2Y"], repository=Repo())
    assert desconocidas == []
    assert elegidas[0]["category"].startswith("Bowes 2012")
    assert elegidas[0]["name"] == "5-HT1A (HTR1A)"
    assert "center" not in elegidas[0]      # la caja sale del catálogo


def test_prepare_target_usa_la_funcion_compartida():
    """Que la guarda y el inventario no puedan divergir: una sola función."""
    import inspect

    fuente = inspect.getsource(preparer.prepare_target)
    assert "cofactores_sin_plantilla(" in fuente
    assert "retirar_cofactores_fuera_del_sitio(" in fuente
    assert "truncar_cadenas_laterales_incompletas(" in fuente
    # El receptor que puntúa el rescoring es el mismo que se acopla.
    assert fuente.count("truncar_cadenas_laterales_incompletas(") >= 2


def test_la_interfaz_no_pide_por_defecto_anti_dianas_retiradas():
    """La fase 1 sacó 6MVW (NavAb) y 1SO2 (PDE3B) del panel, pero la interfaz
    las seguía enviando por defecto y el backend las acoplaba como «anti-diana
    del usuario». El valor por defecto de la interfaz es el panel del backend."""
    import re

    from services.docking.selectivity import ANTI_TARGET_PANEL

    esperado = sorted(t["pdb_id"] for t in ANTI_TARGET_PANEL)
    front = RAIZ / "frontend" / "components"
    for rel in ("evaluation/CaseEvaluationRunner.tsx", "interfaces/pro/ProEvaluation.tsx",
                "interfaces/pro/ProOptionsModal.tsx"):
        fuente = (front / rel).read_text(encoding="utf-8")
        listas = re.findall(r"(?:pro_anti_targets|selectedAntiTargets)[^\[]*\[([^\]]*)\]", fuente)
        assert listas, rel
        for lista in listas:
            ids = sorted(re.findall(r'"([0-9A-Z]{4})"', lista))
            if ids:
                assert ids == esperado, (rel, ids)


# ── Organismo declarado en el catálogo ─────────────────────────────────

#: Organismos que acompañan a la diana en el cristal (fusiones, etiquetas) y no
#: son su procedencia: no valen para dar por bueno el campo `organism`.
_ACOMPANANTES = (
    "escherichia coli", "enterobacteria phage t4", "desulfovibrio vulgaris",
    "synthetic construct", "pyrococcus abyssi", "thermus thermophilus",
    "rhodothermus marinus",
)


def _organismos_del_pdb(pdb_id: str) -> list[str]:
    """`SOURCE ORGANISM_SCIENTIFIC` del PDB depositado, uniendo continuaciones."""
    import gzip
    import re

    ruta = RAIZ / "data" / "targets" / f"{pdb_id}.pdb.gz"
    if not ruta.is_file():
        return []
    with gzip.open(ruta, "rt", encoding="utf-8", errors="replace") as fh:
        texto = fh.read()
    cuerpo = " ".join(l[10:].strip() for l in texto.splitlines() if l.startswith("SOURCE"))
    return [re.sub(r"\s+", " ", campo.split("ORGANISM_SCIENTIFIC:", 1)[1]).strip().lower()
            for campo in cuerpo.split(";") if "ORGANISM_SCIENTIFIC:" in campo]


def test_el_organismo_del_catalogo_es_el_del_pdb():
    """20 entradas decían «Homo sapiens» sobre PDB de VIH, SARS-CoV-2, bacterias,
    pavo o Torpedo (verificación del 2026-09-26). Se corrigieron; esto lo fija."""
    import re

    catalogo = json.loads((RAIZ / "curated_targets.json").read_text(encoding="utf-8"))
    mal = []
    for entrada in catalogo:
        declarado = re.sub(r"\s+", " ", (entrada.get("organism") or "")).strip().lower()
        organismos = _organismos_del_pdb(entrada["pdb_id"].upper())
        if not declarado or not organismos:
            continue
        partes = [p.strip() for p in declarado.split(",") if p.strip()]
        if not any(p in o or o in p for o in organismos for p in partes):
            mal.append((entrada["pdb_id"], entrada.get("organism"), organismos))
    assert mal == [], (
        "el catálogo declara un organismo que no aparece en el SOURCE de su propio PDB: "
        f"{mal}. Corrige el campo `organism`; no lo supongas por el nombre."
    )


def test_una_diana_humana_sobre_un_pdb_de_otro_organismo_se_detecta():
    """El guardián tiene que ver: 6MVW es de *Arcobacter butzleri*."""
    organismos = _organismos_del_pdb("6MVW")
    assert organismos, "6MVW debería traer SOURCE en su PDB"
    assert not any("homo sapiens" in o for o in organismos)
    assert any("arcobacter" in o for o in organismos)
