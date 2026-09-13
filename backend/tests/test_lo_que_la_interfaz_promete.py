"""Lo que la interfaz promete tiene que existir en el backend.

Auditoría del 2026-09-04, §4. El diagrama del pipeline y la red de tecnologías
anunciaban capacidades y cifras que el árbol no respalda:

* **«7 anti-targets clínicos: hERG, CYP2D6/CYP3A4, 5-HT2B, PXR, BSEP, DAT»**
  El panel real (`services/docking/selectivity.py::ANTI_TARGET_PANEL`) tiene
  CINCO, y no son esos: hERG (5VA1), CYP3A4 (4NY4), 5-HT2B (4NC3), PDE3A
  (1SO2) y NaV1.5 (6MVW). CYP2D6, PXR, BSEP y DAT no están.

* **«predicción 91.5% en 94 fármacos»** para BBB. Esa cifra no aparece en
  ninguna parte del backend ni de las pruebas. Lo que hay medido es 39 de 41
  fármacos de difusión pasiva dentro de una cohorte de regresión de 46, sin
  holdout independiente: es el conjunto con el que se ajustó el consenso, no
  una validación externa.

* **«veredicto de seguridad»**. El módulo de selectividad devuelve un margen
  on/off-target y, cuando no hay datos suficientes, la constante
  `VEREDICTO_SIN_DATOS`. No emite un veredicto de seguridad.

* **«Reemplaza Antechamber/GAFF2»** y **«precisión DFT»** para xTB. GFN2-xTB es
  tight-binding semi-empírico, no DFT, y MMFF94 no es equivalente a GAFF2.

Una cifra en la interfaz es una afirmación del producto. Si el backend no la
sostiene, la interfaz miente aunque el código funcione.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
FLOWCHART = RAIZ / "frontend" / "components" / "PipelineFlowchart.tsx"
TECH_NETWORK = RAIZ / "frontend" / "components" / "TechNetwork3D.tsx"
VISTAS = (FLOWCHART, TECH_NETWORK)


def _texto(rutas) -> str:
    return "\n".join(r.read_text(encoding="utf-8") for r in rutas if r.is_file())


def _sin_comentarios(rutas) -> str:
    """El texto que el usuario ve, sin los comentarios que citan el original.

    Las correcciones de esta auditoría dejan escrito qué decía antes cada
    afirmación —es lo que hace revisable el cambio—, así que buscar la frase
    vieja en el archivo entero la encuentra siempre. Se quitan los comentarios
    de bloque y los de línea antes de comprobar.
    """
    texto = _texto(rutas)
    texto = re.sub(r"\{/\*.*?\*/\}", "", texto, flags=re.S)
    texto = re.sub(r"/\*.*?\*/", "", texto, flags=re.S)
    return "\n".join(
        linea for linea in texto.splitlines() if not linea.strip().startswith("//")
    )


def test_el_numero_de_anti_targets_anunciado_es_el_que_hay():
    from services.docking.selectivity import ANTI_TARGET_PANEL

    reales = len(ANTI_TARGET_PANEL)
    assert reales == 5, (
        f"el panel cambió a {reales} anti-targets: actualiza esta prueba Y el "
        "texto de la interfaz, que los anuncia por número."
    )

    texto = _texto(VISTAS)
    anuncios = re.findall(r"(\d+)\s+anti-?targets", texto, re.I)
    for anunciado in anuncios:
        assert int(anunciado) == reales, (
            f"la interfaz anuncia {anunciado} anti-targets y el panel tiene "
            f"{reales}. Ver ANTI_TARGET_PANEL."
        )


def test_los_anti_targets_nombrados_en_la_interfaz_estan_en_el_panel():
    from services.docking.selectivity import ANTI_TARGET_PANEL

    en_el_panel = " ".join(
        f"{e.get('name', '')} {e.get('pdb_id', '')}" for e in ANTI_TARGET_PANEL
    ).upper()
    texto = _texto(VISTAS).upper()

    # Los cuatro que la interfaz nombraba y el backend no acopla.
    for ausente in ("PXR", "BSEP", "CYP2D6"):
        if ausente in texto:
            assert ausente in en_el_panel, (
                f"la interfaz nombra {ausente} como anti-target y no está en "
                "ANTI_TARGET_PANEL. Añádelo al panel o quítalo del texto."
            )


def test_no_se_anuncia_una_cifra_de_bbb_que_el_arbol_no_sostiene():
    texto = _texto(VISTAS)
    assert "91.5" not in texto, (
        "vuelve el «91.5% en 94 fármacos» de BBB. Esa cifra no está medida en "
        "ninguna parte del backend. Lo que hay es 39/41 de difusión pasiva en "
        "una cohorte de regresión de 46, sin holdout: ver test_bbb_consenso.py."
    )


def test_la_cohorte_de_bbb_es_la_que_dice_la_prueba():
    """Ancla la cifra real, para que el texto de la interfaz pueda citarla."""
    fuente = (Path(__file__).parent / "test_bbb_consenso.py").read_text(encoding="utf-8")
    assert "46" in fuente, (
        "la cohorte del consenso de BBB cambió de tamaño: revisa lo que la "
        "interfaz dice sobre ella"
    )


def test_la_seleccion_no_promete_un_veredicto_de_seguridad():
    from services.docking import selectividad_margen

    assert hasattr(selectividad_margen, "VEREDICTO_SIN_DATOS"), (
        "desapareció la constante que representa «sin datos suficientes»"
    )
    # La afirmación, no su negación: el texto corregido dice justamente «no
    # emite un veredicto de seguridad», y eso tiene que poder decirse.
    texto = _sin_comentarios(VISTAS).lower()
    for previo in re.findall(r"(.{0,14})veredicto de seguridad", texto):
        assert "no " in previo, (
            "la interfaz vuelve a prometer un «veredicto de seguridad». El "
            "módulo devuelve un margen on/off-target y, sin datos, se abstiene."
        )


# Las AFIRMACIONES que se retiraron, no la palabra suelta: el texto corregido
# nombra GAFF2 y DFT precisamente para decir que no lo es.
_EQUIVALENCIAS_RETIRADAS = [
    "Reemplaza Antechamber/GAFF2",
    "equivalentes funcionales a GAFF2",
    "GAFF2 equivalent",
    "precisión DFT",
    "precision DFT",
    "Motor Cuántico DFT",
]


@pytest.mark.parametrize("afirmacion", _EQUIVALENCIAS_RETIRADAS)
def test_no_se_equipara_xtb_ni_mmff94_con_lo_que_no_son(afirmacion: str):
    texto = _sin_comentarios(VISTAS)
    assert afirmacion not in texto, (
        f"la interfaz vuelve a afirmar «{afirmacion}». GFN2-xTB es "
        "tight-binding semi-empírico, no DFT, y MMFF94 no es equivalente a "
        "GAFF2: son campos de fuerza distintos y aquí no se ha medido ninguna "
        "correspondencia."
    )


def test_el_indice_cuantico_ya_no_entra_al_score_principal():
    """Si vuelve al stacking, el texto de la interfaz deja de ser cierto."""
    fuente = (RAIZ / "backend" / "scoring" / "engine.py").read_text(encoding="utf-8")
    codigo = [
        linea.strip()
        for linea in fuente.splitlines()
        if not linea.strip().startswith("#")
    ]
    culpables = [
        linea
        for linea in codigo
        if "stacking_raw" in linea and "quantum" in linea.lower() and "+=" in linea
    ]
    assert not culpables, (
        f"el índice cuántico volvió al stacking: {culpables}. Es una "
        "combinación lineal con pesos elegidos a mano y un signo por familia "
        "sin justificar; no puede mover un ranking que se sella y se certifica."
    )


def test_el_indice_cuantico_se_sigue_calculando_y_guardando():
    """Sacarlo del ranking no es borrarlo: los descriptores son útiles."""
    from core.models import EvaluationResultORM

    columnas = {c.name for c in EvaluationResultORM.__table__.columns}
    assert "quantum_score" in columnas, (
        "se perdió la columna: el índice informa aunque no decida"
    )


def test_el_perfil_sanguineo_no_se_presenta_como_pronostico():
    texto = _sin_comentarios(
        (
            RAIZ / "frontend" / "components" / "ScoreCard.tsx",
            RAIZ / "frontend" / "components" / "interfaces" / "pro" / "ProParametersTab.tsx",
        )
    )
    assert "sobreviva en la sangre" not in texto, (
        "vuelve la explicación que presentaba el índice como un pronóstico de "
        "supervivencia en sangre. Es la media geométrica de tres factores con "
        "constantes elegidas a mano."
    )
