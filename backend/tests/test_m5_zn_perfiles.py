"""M5-Zn V1: los tres perfiles, reconstruidos desde los checkpoints.

Implementa los gates de aceptación del §10 de
`docs/75_DECISION_CIENTIFICA_M5_ZN_V1.md`. Ese ADR es normativo: si algo del
código y algo del ADR discrepan, manda el ADR.

═══════════════════════════════════════════════════════════════════════════
LA RECONSTRUCCIÓN, QUE ES EL GATE §10.4
═══════════════════════════════════════════════════════════════════════════

Las tres fórmulas se recalculan desde los checkpoints originales y se comparan
con `data/molchamb_loto/delong_paired_report.json`. Medido antes de implementar
nada:

    perfil    n     pos   AUC M5 reconstruida   AUC del reporte    delta
    CA2     1933     37       0.9313775801        0.9313775801    +1.1e-16
    MMP9    1925     50       0.9207733333        0.9207733333     0.0
    ACE     2003     46       0.6707693675        0.6707693675    -1.1e-16

Precisión de máquina. Y las tres constantes de normalización congeladas por el
§3 salen exactas del máximo de |Vina| de cada checkpoint.

Sin esta prueba, un cambio de un dígito en un peso —o volver al UMS histórico
con donantes y MolChamb— produciría otros números sin que nada fallara.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.pipeline.protocols.m5.zinc import (
    PERFILES,
    EstadoM5Zn,
    calcular,
    perfil_para,
    ums_desde_smiles,
    ums_warhead_score,
    vina_normalizada,
)

RAIZ = Path(__file__).resolve().parents[2]
DELONG = RAIZ / "data" / "molchamb_loto" / "delong_paired_report.json"

#: (pdb, clave en el reporte DeLong)
CASOS = [("3DC3", "ca2"), ("1GKC", "mmp9"), ("1O86", "ace")]


def _checkpoint(perfil) -> list[dict]:
    ruta = RAIZ / perfil.checkpoint
    if not ruta.is_file():
        pytest.skip(f"checkpoint ausente: {perfil.checkpoint}")
    return json.loads(ruta.read_text(encoding="utf-8"))["results"]


# ── El UMS autorizado ────────────────────────────────────────────────────

def test_ums_es_la_variante_smarts_del_adr():
    """§2: SMARTS puro, sin donantes ni MolChamb."""
    assert ums_warhead_score(0) == 0.0
    assert ums_warhead_score(1) == pytest.approx(0.85 + 0.10 * (1 / 3))
    assert ums_warhead_score(2) == pytest.approx(0.85 + 0.10 * (2 / 3))
    assert ums_warhead_score(3) == pytest.approx(0.95)
    # Saturado a partir de tres.
    assert ums_warhead_score(7) == pytest.approx(0.95)
    assert ums_warhead_score(-1) == 0.0


def test_produccion_y_el_script_del_paper_calculan_lo_mismo():
    """§10.3: la misma implementación, no dos que se parecen.

    `scripts/bootstrap_ci.py::warhead_only_score` es la que produjo los
    intervalos publicados. Se comprueba sobre moléculas reales, no sobre la
    fórmula: dos fórmulas iguales con detectores distintos dan valores
    distintos.
    """
    from scoring.ums import detect_warheads

    def warhead_only_score(smi: str) -> float:
        wh = detect_warheads(smi)
        if not any(wh.values()):
            return 0.0
        n = sum(1 for v in wh.values() if v)
        return 0.85 + 0.10 * min(n / 3.0, 1.0)

    moleculas = [
        "CC(=O)Nc1nnc(S(N)(=O)=O)s1",   # acetazolamida, sulfonamida
        "ONC(=O)CCCc1ccccc1",            # hidroxámico
        "CC(=O)Oc1ccccc1C(=O)O",         # aspirina, carboxilato
        "CN1C=NC2=C1C(=O)N(C)C(=O)N2C",  # cafeína, sin warhead
        "c1ccccc1",                       # benceno
    ]
    for smi in moleculas:
        assert ums_desde_smiles(smi) == pytest.approx(warhead_only_score(smi)), (
            f"producción y el script del paper divergen en {smi}"
        )


def test_no_se_usa_el_ums_historico():
    """El de donantes y MolChamb da otros valores y no es el autorizado."""
    from scoring.ums import compute_universal_metal_score

    smi = "CC(=O)Nc1nnc(S(N)(=O)=O)s1"
    historico, _ = compute_universal_metal_score(smi, 0.5, "metalloenzyme")
    autorizado = ums_desde_smiles(smi)
    assert historico != pytest.approx(autorizado), (
        "el UMS histórico y el autorizado coinciden: o se cambió uno de los "
        "dos, o se está usando el que no toca"
    )


# ── Normalización congelada ──────────────────────────────────────────────

@pytest.mark.parametrize("pdb,clave", CASOS, ids=[c[1] for c in CASOS])
def test_la_constante_congelada_es_el_maximo_del_checkpoint(pdb: str, clave: str):
    """§3: las tres salen de los checkpoints, no de un número elegido."""
    perfil = PERFILES[pdb]
    resultados = _checkpoint(perfil)
    maximo = max(
        abs(float(r["vina_score"])) for r in resultados if r.get("vina_score") is not None
    )
    assert maximo == pytest.approx(perfil.vina_reference_max, abs=1e-3), (
        f"{clave}: el máximo del checkpoint es {maximo:.3f} y la constante "
        f"congelada dice {perfil.vina_reference_max}"
    )


def test_la_normalizacion_no_depende_de_las_otras_moleculas():
    """§10.6: el score de una molécula no puede cambiar con sus vecinas."""
    perfil = PERFILES["3DC3"]
    uno = vina_normalizada(-8.0, perfil.vina_reference_max)
    otro = vina_normalizada(-8.0, perfil.vina_reference_max)
    assert uno == otro
    assert uno == pytest.approx(8.0 / 10.450)
    # Acotada: una afinidad mejor que la referencia no pasa de 1.
    assert vina_normalizada(-99.0, perfil.vina_reference_max) == 1.0


# ── El gate §10.4: reconstruir las AUC ───────────────────────────────────

@pytest.mark.parametrize("pdb,clave", CASOS, ids=[c[1] for c in CASOS])
def test_el_perfil_reconstruye_la_auc_publicada(pdb: str, clave: str):
    from sklearn.metrics import roc_auc_score

    perfil = PERFILES[pdb]
    resultados = _checkpoint(perfil)
    referencia = json.loads(DELONG.read_text(encoding="utf-8"))[clave]

    etiquetas, scores = [], []
    for r in resultados:
        vina, xgb = r.get("vina_score"), r.get("prob")
        if vina is None or xgb is None:
            continue
        gnn_d = r.get("gnn_d_prob")
        if perfil.peso_gnn_d and gnn_d is None:
            continue
        scores.append(
            perfil.peso_vina * vina_normalizada(vina, perfil.vina_reference_max)
            + perfil.peso_xgb * float(xgb)
            + perfil.peso_gnn_d * float(gnn_d or 0.0)
            + perfil.peso_ums * ums_desde_smiles(r.get("smiles", ""))
        )
        etiquetas.append(1 if r.get("is_active") else 0)

    assert len(etiquetas) == referencia["n_total"], (
        f"{clave}: {len(etiquetas)} moléculas y el reporte dice "
        f"{referencia['n_total']}"
    )
    assert sum(etiquetas) == referencia["n_pos"]

    auc = roc_auc_score(etiquetas, scores)
    assert auc == pytest.approx(referencia["auc_m5"], abs=1e-9), (
        f"{clave}: la fórmula del perfil da AUC {auc:.10f} y el reporte DeLong "
        f"dice {referencia['auc_m5']:.10f}. Revisa pesos, normalización y "
        "variante de UMS antes que esta prueba."
    )
    assert auc == pytest.approx(perfil.auc_m5_referencia, abs=1e-9)


# ── Las fórmulas exactas del §4 ──────────────────────────────────────────

def test_ca2_usa_gnn_d_y_no_clgnn():
    """El motivo por el que no bastaba cambiar 0.06 por 0.40."""
    perfil = PERFILES["3DC3"]
    assert perfil.peso_gnn_d == 0.20
    assert "GNN-D" in perfil.formula
    assert "CL-GNN" not in perfil.formula and "clgnn" not in perfil.formula.lower()


def test_mmp9_no_usa_ni_vina_ni_gnn():
    """§4.2: no se les da peso por estar disponibles."""
    perfil = PERFILES["1GKC"]
    assert perfil.peso_vina == 0.0 and perfil.peso_gnn_d == 0.0
    assert perfil.componentes_requeridos == ("xgb", "ums")


def test_ace_no_usa_gnn():
    perfil = PERFILES["1O86"]
    assert perfil.peso_gnn_d == 0.0
    assert perfil.componentes_requeridos == ("vina", "xgb", "ums")


@pytest.mark.parametrize("pdb", [c[0] for c in CASOS])
def test_los_pesos_suman_uno(pdb: str):
    perfil = PERFILES[pdb]
    total = perfil.peso_vina + perfil.peso_xgb + perfil.peso_gnn_d + perfil.peso_ums
    assert total == pytest.approx(1.0)


# ── Abstenciones del §5 y §7 ─────────────────────────────────────────────

def test_fuera_de_las_tres_dianas_no_hay_score():
    """§7.2: se ejecuta la auditoría, no se heredan pesos."""
    resultado = calcular(
        pdb_id="1BN1",  # otra estructura de CA2
        smiles="CC(=O)Nc1nnc(S(N)(=O)=O)s1",
        vina_kcal_mol=-8.0, xgb_prob=0.9, gnn_d_prob=0.8,
        hay_zinc_confirmado=True,
    )
    assert resultado.m5_score is None
    assert resultado.estado is EstadoM5Zn.FUERA_DE_DIANA
    # Las señales sí se conservan.
    assert resultado.señales["ums_warhead"] > 0


def test_falta_un_componente_y_no_se_renormaliza():
    """§5: no se reparten los pesos del que falta."""
    resultado = calcular(
        pdb_id="3DC3",
        smiles="CC(=O)Nc1nnc(S(N)(=O)=O)s1",
        vina_kcal_mol=-8.0, xgb_prob=0.9,
        gnn_d_prob=None,  # CA2 lo necesita
        hay_zinc_confirmado=True,
    )
    assert resultado.m5_score is None
    assert resultado.estado is EstadoM5Zn.FALTA_COMPONENTE
    assert "gnn_d" in resultado.componentes_ausentes


def test_no_se_sustituye_gnn_d_por_clgnn():
    """§4.1, explícito: ni sustituir ni redistribuir."""
    fuente = (
        RAIZ / "backend" / "services" / "pipeline" / "protocols" / "m5" / "zinc.py"
    ).read_text(encoding="utf-8")
    # Fuera el docstring del módulo: nombra CL-GNN a propósito, para decir que
    # NO se usa. Buscarlo ahí encontraría siempre la explicación.
    cuerpo = fuente.split('"""', 2)[2]
    codigo = [l for l in cuerpo.splitlines() if not l.strip().startswith("#")]
    assert not [l for l in codigo if "clgnn" in l.lower()], (
        "aparece CL-GNN en el código del perfil: CA2 usa GNN-D y su ausencia "
        "produce NOT_EVALUATED, no una sustitución"
    )


def test_un_warhead_no_convierte_el_caso_en_metalico():
    """§8: la sulfonamida es una feature, no una condición suficiente."""
    resultado = calcular(
        pdb_id="3DC3",
        smiles="CC(=O)Nc1nnc(S(N)(=O)=O)s1",
        vina_kcal_mol=-8.0, xgb_prob=0.9, gnn_d_prob=0.8,
        hay_zinc_confirmado=False,
    )
    assert resultado.m5_score is None
    assert "zinc_confirmado" in resultado.componentes_ausentes


def test_un_valor_no_finito_cuenta_como_ausente():
    """§5: NaN o infinito producen abstención explícita."""
    resultado = calcular(
        pdb_id="1GKC", smiles="ONC(=O)CCCc1ccccc1",
        xgb_prob=float("nan"), hay_zinc_confirmado=True,
    )
    assert resultado.m5_score is None
    assert resultado.estado is EstadoM5Zn.FALTA_COMPONENTE


def test_el_perfil_completo_si_produce_score():
    """La formula se aplica y el numero sale. Lo que cambio es como se llama.

    Desde el corrigendum del 2026-09-04 MMP9 esta en cuarentena: el score se
    CALCULA —es reproducible y sirve para comparar corridas entre si— y el
    estado es `BENCHMARK_EN_REVISION`, no `VALIDADO`. Ocultar el numero habria
    sido peor: dejaria de poder auditarse justo cuando hace falta auditarlo.
    """
    resultado = calcular(
        pdb_id="1GKC", smiles="ONC(=O)CCCc1ccccc1",
        xgb_prob=0.80, hay_zinc_confirmado=True,
    )
    assert resultado.estado is EstadoM5Zn.BENCHMARK_EN_REVISION
    esperado = 0.75 * 0.80 + 0.25 * ums_desde_smiles("ONC(=O)CCCc1ccccc1")
    assert resultado.m5_score == pytest.approx(esperado, abs=1e-6)
    assert resultado.protocol_id == "M5_ZN_MMP9_1GKC_V1"
    assert "NINGUN zinc cae dentro de la caja" in resultado.motivo


def test_ningun_perfil_produce_validado_hoy():
    """El estado del producto, fijado donde no se pueda olvidar.

    CA2 se abstiene por ausencia de GNN-D; MMP9 y ACE estan en cuarentena
    porque sus benchmarks no acoplaron en el sitio del zinc catalitico. Esta
    prueba falla el dia que uno vuelva a validar — y ese dia hay que comprobar
    que la evidencia se rehizo, no solo que el estado cambio.
    """
    from services.pipeline.protocols.m5.zinc import PERFILES

    en_cuarentena = {p for p, perfil in PERFILES.items() if perfil.en_cuarentena}
    assert en_cuarentena == {"1GKC", "1O86"}, (
        "cambio el conjunto de perfiles en cuarentena; revisa "
        "docs/77_CORRIGENDUM_SITIO_DEL_BENCHMARK_M5_ZN.md"
    )
    for pdb in en_cuarentena:
        assert "docs/77_CORRIGENDUM" in PERFILES[pdb].cuarentena, (
            f"{pdb} no enlaza el corrigendum: un perfil cuestionado tiene que "
            "decir donde esta la evidencia"
        )
    # Y los DOS estados son distintos: uno se demostro y el otro no.
    assert PERFILES["1GKC"].estado_de_cuarentena is EstadoM5Zn.BENCHMARK_EN_REVISION
    assert PERFILES["1O86"].estado_de_cuarentena is EstadoM5Zn.TOP1_SIN_COORDINACION


def test_el_pdb_se_compara_exacto_no_por_nombre():
    """§7.1: otra estructura de la misma proteína no hereda el perfil."""
    assert perfil_para("3DC3") is not None
    assert perfil_para("3dc3") is not None, "la comparación es insensible a caja"
    assert perfil_para("1BN1") is None, "1BN1 también es CA2 y NO tiene perfil"
    assert perfil_para(None) is None


# ── La grafía canónica del §6 ────────────────────────────────────────────

def test_la_grafia_canonica_es_la_inglesa():
    from scoring.ums import FAMILIA_CANONICA_METAL, normalizar_familia

    assert FAMILIA_CANONICA_METAL == "metalloenzyme"
    assert normalizar_familia("metaloenzyme") == "metalloenzyme"
    assert normalizar_familia("METALOENZYME") == "metalloenzyme"
    assert normalizar_familia("kinase") == "kinase"
    assert normalizar_familia(None) is None


def test_no_se_clasifica_por_coincidencia_difusa():
    """§6.3: `metalloprotease` no es una metaloenzima de este catálogo."""
    from scoring.ums import _is_metalloenzyme_family

    for otra in ("metalloprotease", "metallothionein", "metal", "metaloide"):
        assert not _is_metalloenzyme_family(otra), (
            f"«{otra}» se clasificó como metaloenzima: la comparación tiene que "
            "ser por igualdad exacta tras normalizar"
        )


def test_unificar_la_grafia_ya_no_activa_el_stack_generico():
    """§6: la migración de grafía y los pesos van en el mismo cambio.

    Antes, las dos grafías recibían pesos distintos —una caía a `default` y la
    otra a `clgnn=1.0`— y corregir sólo el nombre habría activado la política
    genérica que no reproduce ningún perfil.
    """
    from scoring.engine import _get_stacking_weights

    limpio = lambda d: {k: v for k, v in d.items() if not k.startswith("_")}
    assert limpio(_get_stacking_weights("metaloenzyme")) == limpio(
        _get_stacking_weights("metalloenzyme")
    )


def test_la_entrada_generica_de_metal_ya_no_existe():
    pesos = json.loads(
        (RAIZ / "rescoring" / "artifacts" / "stacking_weights.json").read_text(
            encoding="utf-8"
        )
    )
    assert "metaloenzyme" not in pesos, (
        "volvió la entrada genérica `clgnn=1.0`, que no reproduce ninguno de "
        "los tres perfiles autorizados"
    )
    assert "_nota_metaloenzyme" in pesos, (
        "se borró sin dejar constancia de por qué"
    )


def test_el_motor_m4_ya_no_suma_ums_al_ranking():
    """§1: el peso 0.06 encogiendo no reproduce ningún experimento."""
    fuente = (RAIZ / "backend" / "scoring" / "engine.py").read_text(encoding="utf-8")
    codigo = [l for l in fuente.splitlines() if not l.strip().startswith("#")]
    culpables = [l.strip() for l in codigo if "stacking_raw" in l and "ums" in l.lower()]
    assert not culpables, (
        f"el motor de M4 vuelve a sumar UMS al ranking: {culpables}. El score "
        "de metal lo calcula el perfil M5-Zn."
    )
