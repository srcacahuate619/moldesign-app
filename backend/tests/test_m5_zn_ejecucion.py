"""M5-Zn deja de estar implementado y sin ejecutar.

`docs/75_DECISION_CIENTIFICA_M5_ZN_V1.md` §4, §5, §7 y §8.

═══════════════════════════════════════════════════════════════════════════
LO QUE ESTA SUITE FIJA, Y POR QUÉ HACÍA FALTA
═══════════════════════════════════════════════════════════════════════════

`zinc.py` reproducía las tres AUC a precisión de máquina, tenía manifiesto,
tenía pruebas — y `calcular` no tenía NINGÚN llamador en producción. Un
protocolo puede estar entero y no existir para el usuario.

`tests/test_m5_zn_perfiles.py` comprueba la FÓRMULA. Esto comprueba el CAMINO:
qué señal de la corrida entra en cada hueco, y qué pasa cuando una falta.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from services.pipeline.protocols.m5.ejecucion import SalidaM5Zn, ejecutar, ums_autorizado

RAIZ = Path(__file__).resolve().parents[2]

#: Una sulfonamida aromática: warhead de zinc reconocido por los SMARTS.
SULFONAMIDA = "NS(=O)(=O)c1ccc(cc1)C(=O)N"


def _ejecutar(pdb: str, **kwargs) -> SalidaM5Zn | None:
    base = dict(
        smiles=SULFONAMIDA,
        target_pdb_id=pdb,
        target_family="metalloenzyme",
        vina_kcal_mol=-7.2,
        xgb_prob=0.84,
    )
    base.update(kwargs)
    return ejecutar(**base)


# ── Los dos perfiles que calculan score, y estan en cuarentena ───────────

def test_mmp9_calcula_su_score_y_queda_en_revision():
    """0.75*XGB + 0.25*UMS: las dos señales existen en producción.

    El numero sale y es reproducible. El estado NO es VALIDATED porque NINGUN
    zinc cae dentro de su caja declarada por el criterio POR EJE —el catalitico
    queda fuera por dz=-17.34 con semilado 12.5— y el inhibidor cristalografico
    tiene solo 4 de sus 22 atomos dentro. Medido atomo a atomo, el donante mas
    cercano de un activo esta a 15.99 A del zinc.
    Ver docs/77_CORRIGENDUM_SITIO_DEL_BENCHMARK_M5_ZN.md §1.1.
    """
    salida = _ejecutar("1GKC")
    assert salida is not None
    assert salida.estado == "REVIEW_INVALID_BENCHMARK_SITE"
    assert salida.protocol_id == "M5_ZN_MMP9_1GKC_V2"
    # 0.75*0.84 + 0.25*(0.85 + 0.10*min(1/3,1)) — a mano, no desde el módulo.
    # V2: la sulfonamida primaria es UN grupo, aunque case dos claves.
    esperado = 0.75 * 0.84 + 0.25 * salida.ums_warhead
    assert salida.score == pytest.approx(esperado, abs=1e-6), (
        "el score se sigue calculando: ocultarlo dejaria de poder auditarse"
    )


def test_ace_normaliza_vina_con_su_constante_congelada():
    """La normalización es del PERFIL, no de la cohorte cargada.

    Que dependiera del máximo de la cohorte hacía que el score de una molécula
    cambiara según qué otras se estuvieran evaluando.
    """
    salida = _ejecutar("1O86")
    assert salida is not None
    vina_norm = min(abs(-7.2) / 9.566, 1.0)
    esperado = 0.20 * vina_norm + 0.40 * 0.84 + 0.40 * salida.ums_warhead
    assert salida.score == pytest.approx(esperado, abs=1e-6)


def _motivo_de(pdb: str) -> str:
    from services.pipeline.protocols.m5.zinc import PERFILES

    return PERFILES[pdb].cuarentena or ""


def test_ace_tiene_el_sitio_bien_y_su_top1_no_coordina():
    """Tres diagnosticos distintos, tres estados distintos.

    ACE se invalido primero comparando la distancia EUCLIDEA al centro contra
    el semilado de un CUBO —su esfera inscrita—. Con el criterio por eje su
    zinc esta dentro de la caja: es su centro exacto, y las poses caen dentro.

    Y aun asi, de los 47 activos evaluables, NINGUNA POSE TOP-1 acerca un atomo
    donante a <=4.0 A del metal (minima 6.13 A). Esas top-1 son las que
    produjeron las features y sostienen el AUC.
    """
    salida = _ejecutar("1O86")
    assert salida.estado == "REVIEW_BENCHMARK_TOP1_NOT_METAL_COORDINATING"
    assert salida.estado != "REVIEW_INVALID_BENCHMARK_SITE", (
        "la caja de ACE NO estaba mal: confundir «el sitio es incorrecto» con "
        "«la top-1 no coordina» pierde justo el diagnostico util"
    )


def test_el_estado_no_afirma_mas_de_lo_demostrado():
    """El nombre dice TOP1, y el motivo declara lo que NO se sabe.

    El checkpoint descarto las poses alternativas, asi que no se puede saber si
    alguna coordinaba. Un estado llamado «no probo el metal» convertiria un
    oraculo ausente en un muestreo fallido — una conclusion que el artefacto no
    sostiene.
    """
    salida = _ejecutar("1O86")
    assert "TOP1" in salida.estado
    assert "DID_NOT_PROBE" not in salida.estado
    assert "NO se sabe si alguna pose descartada" in _motivo_de("1O86")


def test_hoy_ninguna_diana_devuelve_validated():
    """El estado liberable del producto, fijado de punta a punta.

    Si alguna vuelve a VALIDATED, esta prueba falla y obliga a comprobar que se
    rehizo la evidencia — no solo que se cambio una cadena.
    """
    estados = {pdb: _ejecutar(pdb).estado for pdb in ("3DC3", "1GKC", "1O86")}
    assert "VALIDATED" not in estados.values(), estados
    assert estados == {
        "3DC3": "NOT_EVALUATED_MISSING_COMPONENT",
        "1GKC": "REVIEW_INVALID_BENCHMARK_SITE",
        "1O86": "REVIEW_BENCHMARK_TOP1_NOT_METAL_COORDINATING",
    }


# ── CA2: la abstención que el ADR ordena ─────────────────────────────────

def test_ca2_se_abstiene_porque_gnn_d_no_tiene_productor():
    """No es un caso hipotético: es lo que 3DC3 devuelve en una corrida real.

    `gnn_d_prob` sólo existe en los checkpoints de benchmark. El §4.1 prohíbe
    sustituirla por CL-GNN y prohíbe redistribuir su peso, así que el perfil
    más completo de los tres es el único que no puede completarse.
    """
    salida = _ejecutar("3DC3")
    assert salida is not None
    assert salida.protocol_id == "M5_ZN_CA2_3DC3_V2"
    assert salida.estado == "NOT_EVALUATED_MISSING_COMPONENT"
    assert salida.score is None, "§5: no se fabrica un neutro"
    assert salida.componentes_ausentes == ("gnn_d",)


def test_con_gnn_d_ca2_si_puntua():
    """El día que exista el productor, conectarlo es pasar un argumento.

    CA2 NO esta en cuarentena: su sitio no se ha auditado todavia. Lo que le
    falta es el productor de GNN-D.
    """
    salida = _ejecutar("3DC3", gnn_d_prob=0.66)
    assert salida is not None and salida.estado == "VALIDATED"
    vina_norm = min(abs(-7.2) / 10.450, 1.0)
    esperado = (
        0.20 * vina_norm + 0.20 * 0.84 + 0.20 * 0.66 + 0.40 * salida.ums_warhead
    )
    assert salida.score == pytest.approx(esperado, abs=1e-6)


# ── Las dos abstenciones de frontera ─────────────────────────────────────

def test_otra_metaloenzima_de_zinc_no_hereda_pesos():
    """§7.2: se ejecuta la auditoría, no se hereda el perfil de otra diana."""
    salida = _ejecutar("1BN1")
    assert salida is not None
    assert salida.estado == "REVIEW_OUT_OF_VALIDATED_TARGET"
    assert salida.score is None and salida.protocol_id is None
    assert salida.ums_warhead is not None, (
        "las señales individuales SÍ se calculan fuera de perfil; lo que no se "
        "calcula es el score compuesto"
    )


def test_una_diana_que_no_es_de_metal_no_devuelve_salida():
    """`None` es «este bloque no aplica», distinto de «no se pudo puntuar»."""
    assert ejecutar(
        smiles=SULFONAMIDA, target_pdb_id="3PP0", target_family="kinase",
        vina_kcal_mol=-7.2, xgb_prob=0.84,
    ) is None


# ── El UMS autorizado ────────────────────────────────────────────────────

def test_el_ums_es_la_variante_smarts_only():
    """Sin donantes y sin MolChamb: el §2 del ADR sólo autoriza esta."""
    # V2: una sulfonamida primaria casa DOS claves —`sulfonamide` y
    # `primary_sulfonamide`— y sigue siendo UN grupo químico, así que n=1.
    # Antes contaba 2 y la fórmula, monótona en n, le regalaba 0.033.
    assert ums_autorizado(SULFONAMIDA) == pytest.approx(0.85 + 0.10 * (1 / 3), abs=1e-9)


def test_sin_warheads_es_cero_y_sin_smiles_es_ausencia():
    """Cero warheads es una observación; no poder leer el SMILES no lo es."""
    assert ums_autorizado("CCO") == 0.0
    assert ums_autorizado(None) is None
    assert ums_autorizado("") is None


def test_no_se_usa_el_ums_historico_en_ninguna_parte_del_modulo():
    """El histórico mezcla warheads, donantes y MolChamb. §9.4.

    Se comprueba sobre el árbol sintáctico: lo que importa es qué función se
    llama, no qué texto hay cerca.
    """
    fuente = (
        RAIZ / "backend" / "services" / "pipeline" / "protocols" / "m5" / "ejecucion.py"
    ).read_text(encoding="utf-8")
    llamadas = {
        nodo.func.id if isinstance(nodo.func, ast.Name) else getattr(nodo.func, "attr", "")
        for nodo in ast.walk(ast.parse(fuente))
        if isinstance(nodo, ast.Call)
    }
    assert "compute_universal_metal_score" not in llamadas, (
        "el UMS histórico no entra en los tres perfiles: mezcla donantes y "
        "MolChamb con los warheads, y las AUC del reporte de DeLong se "
        "calcularon con la variante SMARTS-only"
    )


# ── Que siga teniendo llamadores ─────────────────────────────────────────

@pytest.mark.parametrize("ejecutor", [
    "backend/services/docking/queue_handler.py",
    "backend/services/pipeline/runner.py",
])
def test_los_dos_ejecutores_llaman_al_protocolo(ejecutor: str):
    """La prueba que no existía, y por eso el protocolo vivía sin ejecutarse.

    Los DOS: si sólo uno lo llama, el resultado de una molécula depende de qué
    camino la evaluó, que es justo lo que el documento 74 quiere terminar.
    """
    fuente = (RAIZ / ejecutor).read_text(encoding="utf-8")
    assert "protocols.m5.ejecucion import ejecutar" in fuente, (
        f"{ejecutor} no ejecuta M5-Zn. El protocolo volvería a estar "
        "implementado y sin llamador."
    )
    assert "m5_columnas" in fuente, (
        f"{ejecutor} ejecuta M5-Zn y no persiste su resultado: el dossier lee "
        "lo persistido, así que sin esto seguiría sin poder informarlo"
    )


def test_componentes_ausentes_se_persisten_en_columnas():
    """El motivo de abstencion sobrevive a la recarga, no solo al estado."""
    salida = _ejecutar("3DC3")
    assert salida is not None
    assert salida.as_columns()["m5_missing_components"] == ["gnn_d"]