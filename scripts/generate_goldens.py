#!/usr/bin/env python3
"""Genera las corridas doradas de M4, M5-Zn y péptidos.

Punto 6 de la Fase 0 de `docs/74_ARQUITECTURA_DISPATCHER_DE_PROTOCOLOS.md`.

# Qué sella cada golden

No la salida literal del programa, sino el **significado científico** que las
entradas deben producir: qué protocolo se eligió, qué señales son observaciones
y cuáles interpretaciones, qué componentes faltaron, y en qué dominio puede
leerse el resultado.

Se excluye a propósito todo lo que depende del reloj o de la máquina —fechas,
semillas aleatorias de proceso, rutas absolutas, tiempos— porque un golden que
cambia solo no protege nada.

# Los cinco

    m4_small_molecule       la afinidad de Vina cruda, intacta, con su procedencia
    m5_zn_ca2_3dc3          el perfil más completo: Vina + XGBoost + GNN-D + UMS
    m5_zn_replay            las tres AUC reconstruidas desde los checkpoints
    peptide_sin_pesos       abstención limpia cuando ESMFold no está instalado
    peptide_con_sidecar     corrida positiva con el sidecar disponible

Los dos de péptidos son dos goldens y no uno porque son dos contratos
distintos: uno dice que la ausencia se declara y se pide la descarga, el otro
que pLDDT y afinidad viajan separados y que ninguna afinidad se deriva de una
confianza.

# Uso

    python scripts/generate_goldens.py            # escribe
    python scripts/generate_goldens.py --check    # falla si difieren
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from types import SimpleNamespace

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "backend"))

DESTINO = RAIZ / "backend" / "tests" / "goldens"

GOLDEN_VERSION = 1


def serializar(datos: dict) -> str:
    """Forma canónica. `--check` compara bytes."""
    return json.dumps(datos, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


# ── M4: la afinidad de Vina, intacta ─────────────────────────────────────

def golden_m4() -> dict:
    """El contrato de M4: la observación primaria no la pisa nadie.

    Se sella el CONTRATO, no una corrida: acoplar de verdad exige el binario de
    Vina y un receptor preparado, y eso no cabe en una prueba de unidad. Lo que
    sí cabe —y es lo que se rompió en producción— es que `affinity_kcal` sea el
    score de Vina y no la regresión de XGBoost, y que las métricas derivadas
    salgan de ahí.
    """
    from core.models import EvaluationResultRead
    from scoring.eficiencia import calcular as calcular_eficiencia

    # Una corrida M4 típica: aspirina, afinidad de Vina, XGBoost fuera de
    # dominio. Los números son de entrada, no medidos: lo que se sella es cómo
    # se combinan y qué se puede afirmar de ellos.
    vina_kcal = -6.5
    heavy_atoms = 13
    ml_pki = 4.9  # equivale a -6.67 kcal/mol: parecido, y distinto

    metricas = calcular_eficiencia(vina_kcal, heavy_atoms)

    return {
        "golden_version": GOLDEN_VERSION,
        "protocolo": "M4_SMALL_MOLECULE",
        "entrada": {
            "smiles": "CC(=O)Oc1ccccc1C(=O)O",
            "nombre": "aspirina",
            "heavy_atoms": heavy_atoms,
        },
        "observaciones_crudas": {
            "vina_affinity_kcal_mol": vina_kcal,
            "unidades": "kcal/mol",
            "nota": (
                "Salida literal de AutoDock Vina. No es energía libre ni se "
                "traduce a una concentración."
            ),
        },
        "interpretaciones": {
            "ml_pki": ml_pki,
            "ml_pki_aplicada": False,
            "ml_pki_equivalente_kcal": round(-1.36 * ml_pki, 4),
            "nota": (
                "La regresión de XGBoost viaja en su propia columna. Hasta el "
                "2026-09-04 se convertía a kcal y se escribía SOBRE "
                "affinity_kcal, destruyendo la observación primaria."
            ),
        },
        "eficiencia_normalizada": {
            "ligand_efficiency_vina": metricas.ligand_efficiency_vina,
            "sile_vina": metricas.sile_vina,
            "fq_vina_proxy": metricas.fq_vina_proxy,
            "le_scale_pki": metricas.le_scale_pki,
            "escala_sujetada": metricas.escala_sujetada,
            "ha_para_la_escala": metricas.ha_para_la_escala,
        },
        "invariantes": {
            "affinity_kcal_es_de_vina": True,
            "ml_pki_en_columna_propia": True,
            "metricas_derivadas_de_vina_no_de_ml": True,
            "campos_del_contrato": sorted(
                c for c in EvaluationResultRead.model_fields
                if c in {"affinity_kcal", "ml_pki", "ml_pki_aplicada"}
            ),
        },
    }


# ── M5-Zn: el perfil completo, y el replay de los tres ───────────────────

def golden_m5_zn_ca2() -> dict:
    """CA2/3DC3: el perfil con los cuatro componentes."""
    from services.pipeline.protocols.m5.zinc import PERFILES, calcular

    perfil = PERFILES["3DC3"]
    # Acetazolamida: el fármaco de CA2, sulfonamida primaria.
    smiles = "CC(=O)Nc1nnc(S(N)(=O)=O)s1"
    entrada = dict(
        pdb_id="3DC3", smiles=smiles,
        vina_kcal_mol=-7.2, xgb_prob=0.84, gnn_d_prob=0.66,
        hay_zinc_confirmado=True,
    )
    resultado = calcular(**entrada)

    # El mismo caso sin GNN-D: CA2 lo requiere, así que abstiene.
    sin_gnn = calcular(**{**entrada, "gnn_d_prob": None})
    # Y sin zinc confirmado: un warhead no basta.
    sin_zinc = calcular(**{**entrada, "hay_zinc_confirmado": False})

    return {
        "golden_version": GOLDEN_VERSION,
        "protocolo": perfil.protocol_id,
        "formula": perfil.formula,
        "entrada": {k: v for k, v in entrada.items()},
        "resultado": {
            "estado": resultado.estado.value,
            "m5_score": resultado.m5_score,
            "componentes_ausentes": list(resultado.componentes_ausentes),
            "señales": resultado.señales,
        },
        "abstenciones": {
            "sin_gnn_d": {
                "estado": sin_gnn.estado.value,
                "m5_score": sin_gnn.m5_score,
                "componentes_ausentes": list(sin_gnn.componentes_ausentes),
                "nota": (
                    "CA2 requiere GNN-D. No se sustituye por CL-GNN ni se "
                    "redistribuyen sus pesos (§4.1 del ADR 75)."
                ),
            },
            "sin_zinc_confirmado": {
                "estado": sin_zinc.estado.value,
                "m5_score": sin_zinc.m5_score,
                "componentes_ausentes": list(sin_zinc.componentes_ausentes),
                "nota": (
                    "Un warhead del ligando es una feature, no una condición "
                    "suficiente (§8 del ADR 75)."
                ),
            },
        },
    }


def golden_m5_replay() -> dict:
    """Las tres AUC, reconstruidas desde los checkpoints originales.

    Es la garantía de que la fórmula implementada sigue siendo la publicada.
    """
    from sklearn.metrics import roc_auc_score

    from services.pipeline.protocols.m5.zinc import (
        PERFILES,
        ums_desde_smiles,
        vina_normalizada,
    )

    delong = json.loads(
        (RAIZ / "data" / "molchamb_loto" / "delong_paired_report.json").read_text(
            encoding="utf-8"
        )
    )
    claves = {"3DC3": "ca2", "1GKC": "mmp9", "1O86": "ace"}

    perfiles = {}
    for pdb, clave in claves.items():
        perfil = PERFILES[pdb]
        ruta = RAIZ / perfil.checkpoint
        if not ruta.is_file():
            perfiles[pdb] = {"checkpoint_ausente": perfil.checkpoint}
            continue

        resultados = json.loads(ruta.read_text(encoding="utf-8"))["results"]
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

        auc = roc_auc_score(etiquetas, scores)
        referencia = delong[clave]
        perfiles[pdb] = {
            "protocol_id": perfil.protocol_id,
            "n_total": len(etiquetas),
            "n_positivos": sum(etiquetas),
            "auc_m5_reconstruida": round(auc, 10),
            # Lo que el PERFIL declara. Desde V2 no es lo que dice el reporte
            # DeLong, y comparar contra el reporte marcaría los tres como
            # discrepantes: el detector de warheads cambió, no los datos.
            "auc_m5_declarada": round(perfil.auc_m5_referencia, 10),
            "coincide_con_el_perfil": abs(auc - perfil.auc_m5_referencia) < 1e-9,
            # La de V1, para que el cambio de versión quede en el registro.
            "auc_m5_publicada_v1": round(referencia["auc_m5"], 10),
            "mejora_sobre_v1": round(auc - referencia["auc_m5"], 10),
            "vina_reference_max": perfil.vina_reference_max,
        }

    return {
        "golden_version": GOLDEN_VERSION,
        "descripcion": (
            "Replay matemático de los tres perfiles desde los checkpoints "
            "originales, comparado con la AUC que declara cada perfil. Desde "
            "V2 esa AUC ya no es la de delong_paired_report.json: el §2 del "
            "ADR obliga a versión nueva al cambiar un patrón de warhead, y "
            "aquí cambiaron dos (el nitro y el doble conteo)."
        ),
        "fuente_de_referencia": (
            "backend/services/pipeline/protocols/m5/zinc.py::PERFILES "
            "(V1 en data/molchamb_loto/delong_paired_report.json)"
        ),
        "perfiles": perfiles,
    }


# ── Péptidos: los dos contratos ──────────────────────────────────────────

def golden_peptido_sin_pesos() -> dict:
    """Sin ESMFold instalado: abstención limpia, no una afinidad inventada."""
    return {
        "golden_version": GOLDEN_VERSION,
        "protocolo": "PEPTIDE_ESMFOLD_VINA",
        "escenario": "sin_pesos_instalados",
        "entrada": {
            "smiles": "C[C@H](N)C(=O)N[C@@H](C)C(=O)N[C@@H](C)C(O)=O",
            "nombre": "tri-alanina",
            "peptide_docking_engine": "esmfold",
        },
        "contrato": {
            "requested_engine": "esmfold",
            "executed_engine": "vina",
            "aviso_esperado": "MOTOR_SUSTITUIDO",
            "severidad_esperada": "CRITICA",
            "vina_affinity_kcal_mol": "real, del acoplamiento de sustitución",
            "fold_plddt": None,
            "afinidad_derivada_de_confianza": False,
            "nota": (
                "El motor pedido no está: se declara la sustitución en CRÍTICA "
                "y el número que se reporta es de Vina. Antes esta ruta "
                "devolvía -4.0 kcal/mol siempre."
            ),
        },
        "invariantes": {
            "ninguna_afinidad_derivada_de_plddt": True,
            "requested_distinto_de_executed_se_declara": True,
            "sin_caja_declarada_la_corrida_falla": True,
        },
    }


def golden_peptido_con_sidecar() -> dict:
    """Con ESMFold instalado: lo que la ejecución REAL produjo.

    Este golden se escribió a partir de una corrida de verdad el 2026-09-04,
    con los pesos de `esmfold/models` (8.44 GB) sobre CPU. No es un contrato
    aspiracional: son los números medidos, incluido el punto donde se detiene.

    Lo que funciona:

        carga del modelo          ~14-19 s
        plegado (tri-Ala)         ~4 s, 15 átomos, pLDDT 59.5
        plegado (angiotensina II) ~12 s, 74 átomos, pLDDT 72

    Lo que NO llega a ejecutarse, y por qué está aquí sellado como tal: el
    ligando plegado no se puede preparar para Vina. El PDB de ESMFold no trae
    OXT —no está en la representación atom37— así que su topología no casa con
    el SMILES de entrada (15 átomos frente a 16), y RDKit no puede inferir los
    enlaces peptídicos desde la geometría sin romper una valencia.

    El resultado es honesto: `origen=folded_structure_only`,
    `vina_affinity_kcal_mol=None`, y NINGUNA afinidad fabricada. Antes de las
    correcciones de esta sesión, este mismo caso habría reportado -4.0 kcal/mol.
    """
    return {
        "golden_version": GOLDEN_VERSION,
        "protocolo": "PEPTIDE_ESMFOLD_VINA",
        "escenario": "sidecar_disponible",
        "medido_el": "2026-09-04",
        "entrada": {
            "smiles": "C[C@H](N)C(=O)N[C@@H](C)C(=O)N[C@@H](C)C(O)=O",
            "nombre": "tri-alanina",
            "secuencia": "AAA",
            "peptide_docking_engine": "esmfold",
            "modelo": "esmfold/models (8.44 GB)",
            "dispositivo": "cpu",
        },
        "plegado": {
            "ejecutado": True,
            "atomos": 15,
            "plddt_0_100": 59.5,
            "confidence_0_1": 0.595,
            "nota": (
                "pLDDT en la escala convencional 0-100. `output_to_pdb` los "
                "escribe en 0-1 y el sidecar los normaliza al leerlos; antes "
                "los tomaba tal cual, con lo que el aviso «pLDDT bajo» se "
                "disparaba siempre y la confianza salía cien veces menor."
            ),
        },
        "acoplamiento": {
            "ejecutado": False,
            "motivo": "ligando_pdb_no_parseable",
            "detalle": (
                "El PDB de ESMFold no incluye OXT (fuera de la representación "
                "atom37), así que tiene 15 átomos frente a los 16 del SMILES de "
                "entrada. RDKit no puede asignar los enlaces desde la geometría "
                "sin generar un oxígeno de valencia 3, y sin enlaces Meeko "
                "produce 74 fragmentos sueltos."
            ),
            "vina_affinity_kcal_mol": None,
        },
        "contrato": {
            "requested_engine": "esmfold",
            "executed_engine": "esmfold",
            "pose_origen": "folded_structure_only",
            "afinidad_derivada_de_confianza": False,
            "scientific_status": "EXPERIMENTAL",
            "campos_separados": [
                "fold_plddt",
                "vina_affinity_kcal_mol",
                "pose_generation_method",
                "refinement_status",
                "scientific_status",
            ],
        },
        "invariantes": {
            "plddt_no_se_convierte_a_kcal": True,
            "estructura_sin_docking_no_pasa_por_pose": True,
            "sin_acoplamiento_la_afinidad_es_null": True,
            "la_confianza_del_plegado_si_viaja": True,
        },
        "pendiente_de_decision": (
            "Para que este perfil produzca una afinidad hace falta decidir cómo "
            "el péptido plegado se convierte en ligando acoplable: reconstruir "
            "OXT, o transferir las coordenadas de ESMFold a un mol construido "
            "desde el SMILES. Es una decisión de protocolo, no un arreglo."
        ),
    }


# ── Los dossieres, sellados por su semántica ─────────────────────────────

def _campos_de_dossier(eval_result: dict, resumen: dict, pdb: str) -> list[dict]:
    """Los campos de protocolo tal como el dossier los emite.

    Se llama a `_campos_por_protocolo`, que es LA composición que usa
    `build_case_dossier`; aquí no se vuelve a componer. Componerla dos veces es
    parte de por qué faltaba el objetivo sin que nada lo dijera: el golden
    llamaba a los bloques por su cuenta y les pasaba en el resultado un PDB que
    en la base de datos no viaja ahí.

    El PDB llega envuelto en un objeto con `pdb_id` porque eso es lo que recibe
    el dossier: la fila de `targets` del objetivo de la molécula.
    """
    from services.dossier.model import _campos_por_protocolo

    objetivo = SimpleNamespace(pdb_id=pdb)
    return [c.as_dict() for c in _campos_por_protocolo(eval_result, resumen, objetivo)]


def golden_dossier_m4() -> dict:
    """M4: observación de Vina e interpretación de ML, y el caso fuera de dominio."""
    base = {
        "target_family": "kinase",
        "model_used": "universal", "xgb_score": 0.71,
    }
    resumen = {"top_pose_affinity": -6.5}

    en_dominio = _campos_de_dossier(
        {**base, "ml_pki": 4.9, "ml_pki_aplicada": True},
        resumen, "3PP0",
    )
    fuera = _campos_de_dossier(
        {**base, "ml_pki": 4.9, "ml_pki_aplicada": False},
        resumen, "3PP0",
    )
    sin_ml = _campos_de_dossier(
        {**base, "ml_pki": None, "ml_pki_aplicada": None},
        resumen, "3PP0",
    )

    return {
        "golden_version": GOLDEN_VERSION,
        "protocolo": "M4_SMALL_MOLECULE",
        "descripcion": (
            "Los campos de dossier de M4. La observación de Vina y la "
            "interpretación de XGBoost coexisten y se distinguen; hasta el "
            "2026-09-04 no podían, porque la segunda sobrescribía a la primera."
        ),
        "estados": {
            "ml_dentro_del_dominio": en_dominio,
            "ml_fuera_del_dominio": fuera,
            "sin_regresion_de_ml": sin_ml,
        },
    }


def golden_dossier_m5_zn() -> dict:
    """Los tres estados de M5-Zn que el dossier tiene que saber contar."""
    resumen_completo = {"top_pose_affinity": -7.2}

    # MMP9 calcula su score de punta a punta —0.75*XGB + 0.25*UMS, dos senales
    # que produccion produce— y ESTA EN CUARENTENA: ningun zinc cae dentro de su
    # caja declarada por el criterio POR EJE, y el inhibidor cristalografico
    # tiene 4 de sus 22 atomos dentro. El numero se muestra con la advertencia al
    # lado; ocultarlo dejaria de poder auditarse.
    # Ver docs/77_CORRIGENDUM_SITIO_DEL_BENCHMARK_M5_ZN.md §1.1.
    completo = _campos_de_dossier(
        {"target_family": "metalloenzyme",
         "xgb_score": 0.84, "ums_warhead": 0.8833333333333333,
         "m5_score": 0.850833, "m5_protocol_id": "M5_ZN_MMP9_1GKC_V2",
         "m5_scientific_status": "REVIEW_INVALID_BENCHMARK_SITE"},
        resumen_completo, "1GKC",
    )
    # CA2 requiere GNN-D, y GNN-D NO TIENE PRODUCTOR en produccion: solo aparece
    # en los checkpoints de benchmark. Asi que este no es un caso hipotetico —
    # es lo que 3DC3 devuelve hoy en una corrida real.
    falta_componente = _campos_de_dossier(
        {"target_family": "metalloenzyme",
         "xgb_score": 0.84, "ums_warhead": 0.8833333333333333,
         "m5_score": None, "m5_protocol_id": "M5_ZN_CA2_3DC3_V2",
         "m5_scientific_status": "NOT_EVALUATED_MISSING_COMPONENT"},
        resumen_completo, "3DC3",
    )
    # ACE: el sitio era CORRECTO —su zinc es el centro exacto de la caja y las
    # poses caen dentro— y aun asi ninguna POSE TOP-1 de los 47 activos
    # evaluables acerca un donante a <=4.0 A del metal. Esas top-1 son las que
    # sostienen el AUC. Lo que hubieran hecho las poses descartadas NO se sabe:
    # el checkpoint no las guardo. Ver docs/77 §8.
    sin_verificar = _campos_de_dossier(
        {"target_family": "metalloenzyme",
         "xgb_score": 0.84, "ums_warhead": 0.8833333333333333,
         "m5_score": 0.839867, "m5_protocol_id": "M5_ZN_ACE_1O86_V2",
         "m5_scientific_status": "REVIEW_BENCHMARK_TOP1_NOT_METAL_COORDINATING"},
        {"top_pose_affinity": -7.2}, "1O86",
    )
    # Y una corrida anterior a SCHEMA 18: el protocolo no se ejecuto, y la unica
    # senal de warheads que guardo es el UMS HISTORICO, que no es la autorizada.
    legacy_sin_m5 = _campos_de_dossier(
        {"target_family": "metalloenzyme",
         "xgb_score": 0.84, "ums_score": 0.9167},
        resumen_completo, "1GKC",
    )
    # Otra metaloenzima de zinc: señales sí, score compuesto no.
    fuera_de_diana = _campos_de_dossier(
        {"target_family": "metalloenzyme",
         "xgb_score": 0.84, "ums_warhead": 0.8833333333333333,
         "m5_scientific_status": "REVIEW_OUT_OF_VALIDATED_TARGET"},
        resumen_completo, "1BN1",
    )
    # Y la grafía legacy tiene que dar exactamente lo mismo.
    alias_legacy = _campos_de_dossier(
        {"target_family": "metaloenzyme",
         "xgb_score": 0.84, "ums_warhead": 0.8833333333333333,
         "m5_scientific_status": "REVIEW_OUT_OF_VALIDATED_TARGET"},
        resumen_completo, "1BN1",
    )

    return {
        "golden_version": GOLDEN_VERSION,
        "protocolo": "M5_ZN",
        "adr": "docs/75_DECISION_CIENTIFICA_M5_ZN_V1.md",
        "descripcion": (
            "Los tres estados de dossier de M5-Zn. En los dos últimos el score "
            "compuesto es null y NUNCA un valor neutral fabricado (§5 del ADR)."
        ),
        "estados": {
            "perfil_con_benchmark_en_revision": completo,
            "perfil_exacto_falta_componente": falta_componente,
            "zinc_fuera_de_las_tres_dianas": fuera_de_diana,
            "perfil_con_top1_que_no_coordina": sin_verificar,
            "corrida_anterior_a_schema_18": legacy_sin_m5,
        },
        "alias_de_grafia": {
            "descripcion": (
                "`metaloenzyme` es alias de lectura de `metalloenzyme` (§6 del "
                "ADR 75). La DECISIÓN tiene que ser idéntica; el campo de "
                "procedencia sí difiere a propósito, porque §6.5 dice que la "
                "grafía histórica se conserva y se normaliza al cargarla."
            ),
            "la_decision_coincide": [
                c for c in alias_legacy if c["etiqueta"].startswith(("Protocolo", "Score"))
            ] == [
                c for c in fuera_de_diana if c["etiqueta"].startswith(("Protocolo", "Score"))
            ],
            "procedencia_legacy": next(
                c["valor"] for c in alias_legacy
                if c["etiqueta"].startswith("Modelo de rescoring")
            ),
            "procedencia_canonica": next(
                c["valor"] for c in fuera_de_diana
                if c["etiqueta"].startswith("Modelo de rescoring")
            ),
        },
    }


def golden_dossier_peptido() -> dict:
    """La abstención peptídica, tal como el dossier la cuenta."""
    from services.dossier.model import _campos_de_protocolo_y_abstencion

    campos = _campos_de_protocolo_y_abstencion(
        {"docking_protocol": {"requested_engine": "esmfold",
                              "executed_engine": "esmfold"}},
        {"top_pose_affinity": None},
    )
    sustituido = _campos_de_protocolo_y_abstencion(
        {"docking_protocol": {"requested_engine": "esmfold",
                              "executed_engine": "vina"}},
        {"top_pose_affinity": -5.4},
    )

    return {
        "golden_version": GOLDEN_VERSION,
        "protocolo": "PEPTIDE_ESMFOLD_VINA",
        "adr": "docs/76_DECISION_TRANSFERENCIA_ESMFOLD_A_LIGANDO_V1.md",
        "descripcion": (
            "La abstención en la frontera estructura→ligando, y el caso en que "
            "el motor pedido no está y se sustituye."
        ),
        "estados": {
            "estructura_generada_sin_acoplamiento": [c.as_dict() for c in campos],
            "motor_sustituido_por_vina": [c.as_dict() for c in sustituido],
        },
    }


GENERADORES = {
    "m4_small_molecule": golden_m4,
    "m5_zn_ca2_3dc3": golden_m5_zn_ca2,
    "m5_zn_replay": golden_m5_replay,
    "peptide_sin_pesos": golden_peptido_sin_pesos,
    "peptide_con_sidecar": golden_peptido_con_sidecar,
    "dossier_m4": golden_dossier_m4,
    "dossier_m5_zn": golden_dossier_m5_zn,
    "dossier_peptido": golden_dossier_peptido,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    DESTINO.mkdir(parents=True, exist_ok=True)
    diferencias = []
    for nombre, generador in sorted(GENERADORES.items()):
        ruta = DESTINO / f"{nombre}.json"
        esperado = serializar(generador())
        if args.check:
            if not ruta.is_file():
                diferencias.append(f"falta {ruta.name}")
            elif ruta.read_text(encoding="utf-8") != esperado:
                diferencias.append(f"{ruta.name} difiere")
        else:
            ruta.write_text(esperado, encoding="utf-8")
            print(f"golden escrito: {ruta.name}")

    if args.check:
        if diferencias:
            print(
                "ERROR: corridas doradas desalineadas:\n  - "
                + "\n  - ".join(diferencias)
                + "\n\nUna diferencia EXIGE explicación. No se regenera porque el "
                "test falle: el fallo dice que algo cambió de significado."
            )
            return 1
        print(f"Corridas doradas verificadas: {len(GENERADORES)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
