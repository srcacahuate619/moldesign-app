"""Las corridas doradas: el contrato que el refactor no puede romper.

Punto 6 de la Fase 0 de `docs/74_ARQUITECTURA_DISPATCHER_DE_PROTOCOLOS.md`, y
la especificación ejecutable del dossier.

═══════════════════════════════════════════════════════════════════════════
QUÉ SELLAN, Y QUÉ NO
═══════════════════════════════════════════════════════════════════════════

El **significado científico** de unas entradas: qué protocolo se eligió, qué
señales son observaciones y cuáles interpretaciones, qué componentes faltaron,
y en qué dominio puede leerse el resultado.

No sellan «lo que salió el día que se escribió el test». Se excluye todo lo que
depende del reloj o de la máquina —fechas, semillas de proceso, rutas
absolutas, tiempos— porque un golden que cambia solo no protege nada.

Una diferencia **exige explicación**. No se regenera porque el test falle: el
fallo dice que algo cambió de significado, y hay que decidir si ese cambio es
correcto antes de sellarlo.

═══════════════════════════════════════════════════════════════════════════
POR QUÉ CINCO Y NO TRES
═══════════════════════════════════════════════════════════════════════════

M5-Zn tiene dos: uno ejercita el perfil sobre un caso —que el código aplica la
fórmula— y otro reconstruye las tres AUC desde los checkpoints —que la fórmula
sigue siendo la publicada—. Son garantías distintas.

Péptidos tiene dos porque son dos contratos: sin pesos instalados, la ausencia
se declara y se sustituye el motor en CRÍTICA; con el sidecar disponible,
pLDDT y afinidad viajan separados y ninguna afinidad se deriva de una
confianza.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
GOLDENS = RAIZ / "backend" / "tests" / "goldens"
GENERADOR = RAIZ / "scripts" / "generate_goldens.py"

NOMBRES = [
    "m4_small_molecule",
    "m5_zn_ca2_3dc3",
    "m5_zn_replay",
    "peptide_sin_pesos",
    "peptide_con_sidecar",
]


def _generador():
    spec = importlib.util.spec_from_file_location("generar_goldens", GENERADOR)
    assert spec and spec.loader
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _golden(nombre: str) -> dict:
    return json.loads((GOLDENS / f"{nombre}.json").read_text(encoding="utf-8"))


# ── La guardia ───────────────────────────────────────────────────────────

def _saltar_si_el_golden_necesita_datos_ausentes(nombre: str) -> None:
    """`m5_zn_replay` reconstruye los AUC desde los checkpoints de benchmark.

    Esos checkpoints están en .gitignore: no viajan. Sin ellos el generador
    emite `checkpoint_ausente` en vez del AUC reconstruido —que es la
    degradación correcta, no un fallo— y el golden, que registra una
    reconstrucción real, deja de coincidir. Bajarlo a un golden de ausencia
    sería peor: perdería justo lo que demuestra.

    Con MOLDESIGN_EXIGE_CHECKPOINTS=1 la ausencia vuelve a ser fallo.
    """
    if nombre != "m5_zn_replay":
        return
    import os

    manifiesto = json.loads(
        (RAIZ / "backend" / "services" / "pipeline" / "protocols" / "m5"
         / "m5_zn_manifest.json").read_text(encoding="utf-8")
    )
    faltan = [
        perfil["checkpoint"]["path"]
        for perfil in manifiesto["profiles"].values()
        if not (RAIZ / perfil["checkpoint"]["path"]).is_file()
    ]
    if not faltan:
        return
    if os.environ.get("MOLDESIGN_EXIGE_CHECKPOINTS") == "1":
        raise AssertionError(f"checkpoints exigidos y ausentes: {', '.join(faltan)}")
    pytest.skip(
        "checkpoints de benchmark no distribuidos por el repositorio: "
        + ", ".join(faltan)
        + ". Define MOLDESIGN_EXIGE_CHECKPOINTS=1 para exigirlos."
    )


@pytest.mark.parametrize("nombre", NOMBRES)
def test_el_golden_commiteado_coincide_con_lo_que_produce_el_codigo(nombre: str):
    """La comprobación central. Compara bytes."""
    _saltar_si_el_golden_necesita_datos_ausentes(nombre)
    modulo = _generador()
    esperado = modulo.serializar(modulo.GENERADORES[nombre]())
    actual = (GOLDENS / f"{nombre}.json").read_text(encoding="utf-8")
    assert actual == esperado, (
        f"El golden «{nombre}» ya no coincide con lo que produce el código.\n\n"
        "Esto NO se arregla regenerando. El fallo dice que algo cambió de "
        "significado: decide primero si el cambio es correcto, y sólo entonces\n"
        "    python scripts/generate_goldens.py"
    )


@pytest.mark.parametrize("nombre", NOMBRES)
def test_el_golden_no_contiene_nada_que_cambie_solo(nombre: str):
    """Fechas, rutas absolutas o tiempos harían el golden inútil."""
    texto = (GOLDENS / f"{nombre}.json").read_text(encoding="utf-8")
    for prohibido in ("D:\\\\", "C:\\\\", "/home/", "execution_time", "timestamp"):
        assert prohibido not in texto, (
            f"«{nombre}» contiene «{prohibido}»: un golden que depende del "
            "reloj o de la máquina no protege nada"
        )


def test_la_generacion_es_determinista():
    modulo = _generador()
    for nombre, generador in modulo.GENERADORES.items():
        assert modulo.serializar(generador()) == modulo.serializar(generador()), (
            f"«{nombre}» no es determinista"
        )


# ── M4: la observación primaria ──────────────────────────────────────────

def test_m4_conserva_la_afinidad_de_vina_intacta():
    d = _golden("m4_small_molecule")
    assert d["observaciones_crudas"]["vina_affinity_kcal_mol"] == -6.5
    assert d["invariantes"]["affinity_kcal_es_de_vina"] is True
    assert d["invariantes"]["ml_pki_en_columna_propia"] is True


def test_m4_separa_observacion_de_interpretacion():
    """La regresión de XGBoost no puede volver a pisar la de Vina."""
    d = _golden("m4_small_molecule")
    vina = d["observaciones_crudas"]["vina_affinity_kcal_mol"]
    ml = d["interpretaciones"]["ml_pki_equivalente_kcal"]
    assert vina != ml, (
        "el golden dejó de ejercer el caso: si los dos números coinciden, no "
        "distingue haber conservado la observación de haberla sobrescrito"
    )
    assert d["interpretaciones"]["ml_pki_aplicada"] is False


def test_m4_deriva_las_metricas_de_vina_y_no_del_ml():
    from scoring.eficiencia import calcular

    d = _golden("m4_small_molecule")
    vina = d["observaciones_crudas"]["vina_affinity_kcal_mol"]
    ha = d["entrada"]["heavy_atoms"]
    metricas = calcular(vina, ha)
    assert d["eficiencia_normalizada"]["fq_vina_proxy"] == metricas.fq_vina_proxy
    assert d["eficiencia_normalizada"]["sile_vina"] == metricas.sile_vina


# ── M5-Zn ────────────────────────────────────────────────────────────────

def test_m5_zn_ejercita_el_perfil_mas_completo():
    """CA2/3DC3 es el único con los cuatro componentes."""
    d = _golden("m5_zn_ca2_3dc3")
    assert d["protocolo"] == "M5_ZN_CA2_3DC3_V2"
    assert "GNN-D" in d["formula"]
    assert d["resultado"]["estado"] == "VALIDATED_PROFILE"
    assert d["resultado"]["m5_score"] is not None


def test_m5_zn_sella_las_dos_abstenciones():
    d = _golden("m5_zn_ca2_3dc3")
    sin_gnn = d["abstenciones"]["sin_gnn_d"]
    assert sin_gnn["m5_score"] is None
    assert sin_gnn["estado"] == "NOT_EVALUATED_MISSING_COMPONENT"
    assert "gnn_d" in sin_gnn["componentes_ausentes"]

    sin_zinc = d["abstenciones"]["sin_zinc_confirmado"]
    assert sin_zinc["m5_score"] is None
    assert "zinc_confirmado" in sin_zinc["componentes_ausentes"]


@pytest.mark.parametrize("pdb", ["3DC3", "1GKC", "1O86"])
def test_el_replay_reproduce_la_auc_declarada(pdb: str):
    """La garantía de que la fórmula sigue siendo la del perfil.

    Comparaba contra `auc_m5_publicada`, que es la de V1. Desde V2 el detector
    de warheads es otro —el nitro dejó de contar como quelante y `n_warheads`
    cuenta grupos, no claves— así que la referencia correcta es la que el
    PERFIL declara. La de V1 se conserva en el golden para que el cambio de
    versión quede en el registro, y la mejora se comprueba abajo.
    """
    perfil = _golden("m5_zn_replay")["perfiles"][pdb]
    if "checkpoint_ausente" in perfil:
        pytest.skip(f"checkpoint ausente: {perfil['checkpoint_ausente']}")
    assert perfil["coincide_con_el_perfil"] is True, (
        f"{pdb}: la AUC reconstruida ({perfil['auc_m5_reconstruida']}) no "
        f"coincide con la que declara el perfil ({perfil['auc_m5_declarada']})"
    )


@pytest.mark.parametrize("pdb", ["3DC3", "1GKC", "1O86"])
def test_v2_ordena_mejor_que_v1_en_los_tres(pdb: str):
    """Lo que justifica el cambio de versión, medido y no supuesto.

    Corregir el detector no era sólo química correcta: mejora el orden en los
    tres perfiles sobre sus propios checkpoints. Si algún día deja de mejorar,
    el detector volvió a cambiar y hay que rehacer la medición antes de sellar.
    """
    perfil = _golden("m5_zn_replay")["perfiles"][pdb]
    if "checkpoint_ausente" in perfil:
        pytest.skip(f"checkpoint ausente: {perfil['checkpoint_ausente']}")
    assert perfil["mejora_sobre_v1"] > 0, (
        f"{pdb}: V2 mide {perfil['auc_m5_reconstruida']} y V1 medía "
        f"{perfil['auc_m5_publicada_v1']}"
    )


def test_el_replay_cubre_los_tres_perfiles():
    perfiles = _golden("m5_zn_replay")["perfiles"]
    assert set(perfiles) == {"3DC3", "1GKC", "1O86"}


# ── Péptidos: los dos contratos ──────────────────────────────────────────

def test_sin_pesos_se_declara_la_sustitucion_en_critica():
    d = _golden("peptide_sin_pesos")
    contrato = d["contrato"]
    assert contrato["requested_engine"] != contrato["executed_engine"]
    assert contrato["aviso_esperado"] == "MOTOR_SUSTITUIDO"
    assert contrato["severidad_esperada"] == "CRITICA"
    assert contrato["afinidad_derivada_de_confianza"] is False


def test_con_sidecar_plddt_y_afinidad_van_separados():
    d = _golden("peptide_con_sidecar")
    campos = d["contrato"]["campos_separados"]
    assert "fold_plddt" in campos and "vina_affinity_kcal_mol" in campos
    assert d["contrato"]["afinidad_derivada_de_confianza"] is False
    assert d["invariantes"]["plddt_no_se_convierte_a_kcal"] is True


def test_los_dos_goldens_de_peptido_son_escenarios_distintos():
    """Si fueran el mismo, uno de los dos contratos no se estaría probando."""
    sin_pesos = _golden("peptide_sin_pesos")
    con_sidecar = _golden("peptide_con_sidecar")
    assert sin_pesos["escenario"] != con_sidecar["escenario"]
    assert (
        sin_pesos["contrato"]["executed_engine"]
        != con_sidecar["contrato"]["executed_engine"]
    )


@pytest.mark.parametrize("nombre", ["peptide_sin_pesos", "peptide_con_sidecar"])
def test_ningun_golden_de_peptido_admite_afinidad_desde_confianza(nombre: str):
    """El defecto que devolvía −4.0 kcal/mol siempre."""
    d = _golden(nombre)
    assert d["contrato"]["afinidad_derivada_de_confianza"] is False
    texto = json.dumps(d, ensure_ascii=False)
    assert "-4.0 - 8.0" not in texto and "-1.5 * conf" not in texto


# ── El criterio de cierre ────────────────────────────────────────────────

def test_cada_golden_declara_requested_frente_a_executed_cuando_aplica():
    """Un fallback silencioso es lo que estos goldens existen para impedir."""
    for nombre in ("peptide_sin_pesos", "peptide_con_sidecar"):
        contrato = _golden(nombre)["contrato"]
        assert "requested_engine" in contrato and "executed_engine" in contrato


def test_todos_los_goldens_declaran_su_version():
    for nombre in NOMBRES:
        assert _golden(nombre)["golden_version"] >= 1
