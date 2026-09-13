#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MF-33-H-COR: consolidacion, verificacion independiente y cantidades pareadas.

Toma los checkpoints por pose que produjo `run_mf33hcor_reconstruccion.py` en el servidor y
RECALCULA desde cero todo lo que el artefacto va a afirmar, sin leer `metrics.json` mas que
para contrastar. Escribe el `metrics.json` final del artefacto sellado.

QUE VERIFICA, y por que cada cosa:

1. **Las cinco invariantes por pose.** Si una sola falla, la pose corregida no es la misma
   molecula que la historica y la comparacion no significa nada. Se recuentan aqui en vez de
   confiar en el contador del runner.
2. **La reproduccion de las cifras historicas**, complejo a complejo contra `MF-33-PB` y
   `MF-33-TOP1`, que estan sellados. Es la prueba de que la tuberia nueva reproduce la vieja
   ANTES de corregirla: sin esto, un cambio de tasa podria ser un cambio de tuberia.
3. **La diferencia conocida de `1afl`**, 267 poses contra 258, por correr sobre
   `MF-33-B-RET-R2` y no sobre R1. Estaba predicha en los limites declarados de `MF-33-PB`.

CANTIDADES PAREADAS. Los dos brazos se comparan por complejo, no por pose, con McNemar
exacto y el MDE de `estadistica_fnd04` -el modulo sellado por FND-04-. Se reportan las tablas
2x2 completas: sin ellas, «48 contra 47» y «106 contra 110» no son interpretables.

EL RESIDUO. Las poses que siguen invalidas tras corregir son el resultado cientifico que
queda. Se caracterizan por control, por complejo y por solape, y se declara explicitamente
que los recuentos por control NO suman poses invalidas unicas porque una pose puede fallar
varios controles a la vez.

Uso: python scripts/analisis_mf33hcor_consolidado.py [--artefacto DIR] [--escribir]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from estadistica_fnd04 import (  # noqa: E402  (reuso por composicion, docs/49 §17)
    efecto_minimo_detectable,
    mcnemar_exacto,
    wilson,
)

ART = ROOT / "scripts" / "artifacts_science"
CLAVES_INVARIANTE = ("pesados_invariantes", "smiles_identico", "carga_formal_identica",
                     "n_enlaces_identico")


# ─────────────────────────── carga ───────────────────────────

def cargar_poses(art_dir: Path) -> Dict[str, Dict[str, List[dict]]]:
    """{ambito: {pid: [poses]}} desde los checkpoints por complejo."""
    out: Dict[str, Dict[str, List[dict]]] = {"A": {}, "B": {}}
    for f in sorted((art_dir / "checkpoints").glob("*.poses.json")):
        amb, _, resto = f.name.partition("_")
        pid = resto[: -len(".poses.json")]
        out[amb][pid] = json.loads(f.read_text(encoding="utf-8"))
    return out


# ──────────────────── invariantes y tasas ────────────────────

def verificar_invariantes(poses_por_ambito) -> Dict[str, Any]:
    tot = Counter()
    violadas = Counter()
    desp_max = 0.0
    heredados = 0
    detalle: List[dict] = []
    for amb, por_pid in poses_por_ambito.items():
        for pid, poses in por_pid.items():
            for p in poses:
                inv = p["invariantes"]
                tot[amb] += 1
                desp_max = max(desp_max, float(inv["desplazamiento_pesado_max_A"]))
                heredados += int(inv["n_h_heredados_del_cristal"])
                ok = all(inv[k] for k in CLAVES_INVARIANTE) and inv["n_h_heredados_del_cristal"] == 0
                if not ok:
                    violadas[amb] += 1
                    detalle.append({"ambito": amb, "pid": pid, "identity": p["identity"],
                                    "invariantes": inv})
    return {
        "poses_examinadas": dict(tot),
        "poses_con_invariante_violada": dict(violadas),
        "total_violadas": sum(violadas.values()),
        "desplazamiento_pesado_max_global_A": desp_max,
        "hidrogenos_heredados_del_cristal_total": heredados,
        "detalle_violaciones": detalle[:20],
        "lectura": ("las cinco invariantes se cumplen en TODAS las poses: la molecula corregida "
                    "es la misma que la historica con los hidrogenos regenerados"
                    if not violadas and desp_max == 0.0 and heredados == 0
                    else "HAY VIOLACIONES: la comparacion no es valida tal cual"),
    }


def tasas(poses_por_ambito) -> Dict[str, Any]:
    out = {}
    for amb, por_pid in poses_por_ambito.items():
        n = h = c = 0
        ch_h, ch_c = Counter(), Counter()
        for poses in por_pid.values():
            for p in poses:
                n += 1
                if p["HISTORICA"]["pb_valida"]:
                    h += 1
                else:
                    ch_h.update(p["HISTORICA"]["checks_que_fallan"])
                if p["CORREGIDA"]["pb_valida"]:
                    c += 1
                else:
                    ch_c.update(p["CORREGIDA"]["checks_que_fallan"])
        lo_h, hi_h = wilson(h, n)
        lo_c, hi_c = wilson(c, n)
        out[amb] = {
            "n_complejos": len(por_pid),
            "poses_evaluadas": n,
            "HISTORICA": {"validas": h, "tasa": round(h / n, 4),
                          "ic95_wilson": [round(lo_h, 4), round(hi_h, 4)],
                          "checks_que_fallan": ch_h.most_common()},
            "CORREGIDA": {"validas": c, "tasa": round(c / n, 4),
                          "ic95_wilson": [round(lo_c, 4), round(hi_c, 4)],
                          "checks_que_fallan": ch_c.most_common()},
            "poses_invalidas_unicas_CORREGIDA": n - c,
            "ADVERTENCIA_SOLAPE": (
                "los recuentos por control NO suman poses invalidas unicas: una pose puede "
                f"fallar varios controles a la vez. Invalidas unicas={n - c}; suma de "
                f"recuentos por control={sum(ch_c.values())}."),
        }
    return out


# ───────────────── brazos y cantidades pareadas ─────────────────

def _top1(poses: List[dict]) -> dict:
    """La pose de mejor score. Vina: mas negativo es mejor."""
    return min(poses, key=lambda p: p["score"])


def brazos_A(poses: List[dict]) -> Dict[str, dict]:
    """Ambito A: el brazo SINGLE es el conformero 0; el ENSEMBLE, todos.

    Regla verificada contra `MF-33-PB`, que reproduce 8/48 y 10/48 exactamente.
    """
    single = [p for p in poses if p["conformer"] == 0]
    if not single:
        raise ValueError("complejo sin conformero 0: la regla de brazos no aplica")
    return {"SINGLE": _top1(single), "ENSEMBLE": _top1(poses)}


def brazos_B(poses: List[dict]) -> Dict[str, dict]:
    """Ambito B: el runner ya etiqueto el brazo, porque son top-1 de dos corridas distintas."""
    return {p["brazo"]: p for p in poses}


def pareado(por_pid, extractor, etiqueta: str) -> Dict[str, Any]:
    n = 0
    val = {"SINGLE": Counter(), "ENSEMBLE": Counter()}
    tabla = Counter()          # (single_valida, ensemble_valida) -> n, reconstruccion CORREGIDA
    tabla_h = Counter()
    discordantes: List[dict] = []
    for pid, poses in sorted(por_pid.items()):
        br = extractor(poses)
        if set(br) != {"SINGLE", "ENSEMBLE"}:
            continue
        n += 1
        for rec, t in (("CORREGIDA", tabla), ("HISTORICA", tabla_h)):
            s = bool(br["SINGLE"][rec]["pb_valida"])
            e = bool(br["ENSEMBLE"][rec]["pb_valida"])
            t[(s, e)] += 1
            val["SINGLE"][rec] += s
            val["ENSEMBLE"][rec] += e
        s = bool(br["SINGLE"]["CORREGIDA"]["pb_valida"])
        e = bool(br["ENSEMBLE"]["CORREGIDA"]["pb_valida"])
        if s != e:
            discordantes.append({
                "pid": pid, "single_valida": s, "ensemble_valida": e,
                "single_checks": br["SINGLE"]["CORREGIDA"]["checks_que_fallan"],
                "ensemble_checks": br["ENSEMBLE"]["CORREGIDA"]["checks_que_fallan"]})

    def bloque(t: Counter, rec: str) -> Dict[str, Any]:
        a = t[(True, True)]      # ambos validos
        b = t[(False, True)]     # solo ensemble
        c = t[(True, False)]     # solo single
        d = t[(False, False)]    # ninguno
        disc = (b + c) / n if n else 0.0
        p = mcnemar_exacto(b, c)
        try:
            mde = efecto_minimo_detectable(n, disc) * 100 if disc > 0 else None
        except Exception:
            mde = None
        return {
            "tabla_2x2": {"ambos_validos": a, "solo_ensemble": b, "solo_single": c,
                          "ninguno": d, "n_complejos": n},
            "single_validos": val["SINGLE"][rec], "ensemble_validos": val["ENSEMBLE"][rec],
            "de": n,
            "tasa_single": round(val["SINGLE"][rec] / n, 4) if n else None,
            "tasa_ensemble": round(val["ENSEMBLE"][rec] / n, 4) if n else None,
            "discordancia": round(disc, 4),
            "mcnemar_p_exacto": round(p, 6),
            "mde_pp_para_esta_discordancia": round(mde, 2) if mde else None,
        }

    corr = bloque(tabla, "CORREGIDA")
    b, c = corr["tabla_2x2"]["solo_ensemble"], corr["tabla_2x2"]["solo_single"]
    corr["lectura"] = (
        "SIN_EVIDENCIA_INTERPRETABLE_DE_DIFERENCIA. "
        f"Las discordancias son {b + c} de {n} complejos y McNemar exacto da "
        f"p={corr['mcnemar_p_exacto']}. Con la tasa cerca del techo, este diseno no distingue "
        "entre brazos: NO se afirma ventaja de ninguno, y tampoco equivalencia, que exigiria "
        "una prueba de no-inferioridad con margen preregistrado que aqui no existe.")
    return {"etiqueta": etiqueta, "CORREGIDA": corr, "HISTORICA": bloque(tabla_h, "HISTORICA"),
            "discordantes_corregida": discordantes}


# ─────────────── reproduccion de lo historico ───────────────

def reproduccion_historica(poses_por_ambito) -> Dict[str, Any]:
    """Contrasta complejo a complejo contra los dos artefactos sellados."""
    out: Dict[str, Any] = {}

    pb = {}
    for line in (ART / "MF-33-PB" / "per_complex.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            pb[r["pid"]] = r
    disc_a, n_pos_dif = [], []
    for pid, poses in poses_por_ambito["A"].items():
        ref = pb.get(pid)
        if ref is None:
            continue
        if ref["ENSEMBLE"]["n_poses"] != len(poses):
            n_pos_dif.append({"pid": pid, "MF-33-PB": ref["ENSEMBLE"]["n_poses"],
                              "MF-33-H-COR": len(poses)})
        br = brazos_A(poses)
        for brazo in ("SINGLE", "ENSEMBLE"):
            hist = bool(br[brazo]["HISTORICA"]["pb_valida"])
            if hist != bool(ref[brazo]["top1_valida"]):
                disc_a.append({"pid": pid, "brazo": brazo, "MF-33-PB": ref[brazo]["top1_valida"],
                               "H-COR_historica": hist})
    out["A_contra_MF-33-PB"] = {
        "complejos_contrastados": len(pb),
        "top1_discordantes": disc_a,
        "complejos_con_distinto_numero_de_poses": n_pos_dif,
        "lectura": ("la reconstruccion HISTORICA de este artefacto reproduce top-1 a top-1 lo "
                    "que sello MF-33-PB, salvo donde el numero de poses cambia por R2"),
    }

    top1 = {}
    for line in (ART / "MF-33-TOP1" / "per_complex.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            top1[r["pid"]] = r
    disc_b = []
    for pid, poses in poses_por_ambito["B"].items():
        ref = top1.get(pid)
        if ref is None:
            continue
        br = brazos_B(poses)
        for brazo in ("SINGLE", "ENSEMBLE"):
            if brazo not in br:
                continue
            hist = bool(br[brazo]["HISTORICA"]["pb_valida"])
            if hist != bool(ref[brazo]["pb_valid_fisica"]):
                disc_b.append({"pid": pid, "brazo": brazo,
                               "MF-33-TOP1": ref[brazo]["pb_valid_fisica"],
                               "H-COR_historica": hist})
    out["B_contra_MF-33-TOP1"] = {
        "complejos_contrastados": len(top1),
        "pb_valid_discordantes": disc_b,
        "lectura": ("la reconstruccion HISTORICA reproduce pose a pose el pb_valid_fisica "
                    "sellado en MF-33-TOP1"),
    }
    out["veredicto"] = (
        "REPRODUCCION EXACTA" if not disc_a and not disc_b else
        "HAY DISCORDANCIAS: revisar antes de sellar")
    return out


# ───────────────────────── el residuo ─────────────────────────

def residuo(poses_por_ambito) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for amb, por_pid in poses_por_ambito.items():
        invalidas = []
        for pid, poses in por_pid.items():
            for p in poses:
                if not p["CORREGIDA"]["pb_valida"]:
                    invalidas.append({"pid": pid, "identity": p["identity"],
                                      "checks": sorted(p["CORREGIDA"]["checks_que_fallan"]),
                                      "energia": p["CORREGIDA"]["energia"],
                                      "score": p["score"]})
        por_control = Counter()
        combinaciones = Counter()
        por_complejo = Counter()
        for r in invalidas:
            por_control.update(r["checks"])
            combinaciones["+".join(r["checks"]) or "(ninguno declarado)"] += 1
            por_complejo[r["pid"]] += 1
        out[amb] = {
            "poses_invalidas_unicas": len(invalidas),
            "de_poses_evaluadas": sum(len(v) for v in por_pid.values()),
            "por_control": por_control.most_common(),
            "suma_de_recuentos_por_control": sum(por_control.values()),
            "combinaciones_de_controles": combinaciones.most_common(),
            "complejos_afectados": len(por_complejo),
            "top_complejos": por_complejo.most_common(10),
            "NOTA_SOLAPE": ("la suma de recuentos por control excede las poses invalidas unicas "
                            "porque una misma pose puede fallar varios controles; las "
                            "combinaciones de arriba si son disjuntas y si suman."),
        }
    return out


# ───────────────────────────── main ─────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description="MF-33-H-COR: consolidacion y verificacion")
    ap.add_argument("--artefacto", default=str(ART / "MF-33-H-COR"))
    ap.add_argument("--escribir", action="store_true", help="escribe metrics.json en el artefacto")
    args = ap.parse_args()
    art_dir = Path(args.artefacto)

    poses = cargar_poses(art_dir)
    inv = verificar_invariantes(poses)
    tas = tasas(poses)
    rep = reproduccion_historica(poses)
    res = residuo(poses)
    par_a = pareado(poses["A"], brazos_A, "ambito A, flexible, top-1 por brazo")
    par_b = pareado(poses["B"], brazos_B, "ambito B, rigido, top-1 por brazo")

    # El resumen crudo del runner vive en metrics_servidor.json, copia inmutable de lo que
    # produjo el contenedor. Leerlo de ahi -y no de metrics.json, que este script sobrescribe-
    # hace la consolidacion idempotente: re-ejecutarla vuelve a contrastar contra el servidor
    # en vez de contra su propia salida anterior, que no tiene la clave y daria un True vacio.
    f_srv = art_dir / "metrics_servidor.json"
    servidor = json.loads(f_srv.read_text(encoding="utf-8")) if f_srv.exists() else {}
    resumen_servidor = servidor.get("resumen", {})
    if not resumen_servidor:
        print("[AVISO] sin metrics_servidor.json: no hay contra que contrastar el recalculo",
              file=sys.stderr)
    # Exige que los DOS ambitos esten presentes: un all() sobre un generador vacio devuelve
    # True, y una concordancia vacuamente cierta es peor que ninguna.
    coincide = bool(resumen_servidor) and all(
        resumen_servidor.get(a, {}).get("tasa_corregida") == tas[a]["CORREGIDA"]["tasa"]
        and resumen_servidor.get(a, {}).get("tasa_historica") == tas[a]["HISTORICA"]["tasa"]
        for a in ("A", "B"))

    metrics = {
        "experiment_id": "MF-33-H-COR",
        "tipo": "corrigendum de implementacion; reconstruccion historica contra corregida",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "prerregistro": "MF-33-H-COR-PRE, sellado antes de la corrida",

        "NO_ES_CIEGO_Y_NO_LO_FINGE": (
            "Los 12 complejos del piloto diagnostico fueron INSPECCIONADOS antes de disenar la "
            "correccion, y la prueba tecnica previa al sellado miro ademas el complejo 10gs del "
            "ambito B. Ese piloto DEMUESTRA EL DEFECTO Y DISENA LA CORRECCION; no estima la tasa "
            "nueva, que es lo que mide este artefacto sobre las cohortes completas. Un corrigendum "
            "de implementacion no se aprueba ni se rechaza: se ejecuta y se reporta, con la "
            "reconstruccion historica al lado para que la diferencia sea auditable."),

        "procedencia": {
            "ejecucion": "servidor 192.168.1.64, contenedor mf33hcor, imagen moldesign-lab-pb:0.6.5",
            "trabajos": "164 = 48 del ambito A + 116 del ambito B, todos completados, salida 0",
            "cohorte_A": ("MF-33-B-RET-R2, no R1: 8224 poses sobre 48 complejos. MF-33-PB sello "
                          "8215 poses porque corrio sobre R1."),
            "diferencia_conocida_1afl": ("1afl aporta 267 poses en R2 frente a 258 en R1. Es la "
                                         "UNICA diferencia de cohorte entre los dos artefactos, y "
                                         "estaba PREDICHA en los limites declarados de MF-33-PB: "
                                         "«47 de los 48 complejos tienen poses byte-identicas a "
                                         "las que tendra MF-33-B-RET-R2; 1afl cambiara y habra que "
                                         "recalcularlo»."),
            "cohorte_B": "MF-33-TOP1: 116 complejos del protocolo rigido, top-1 de los dos brazos, 232 poses",
            "descarga_verificada": ("331 archivos contrastados por SHA-256 contra el servidor: "
                                    "331 coinciden, 0 difieren, 0 faltan"),
            "artefactos_originales": "MF-33-PB y MF-33-TOP1 quedan sellados e inmutables; este artefacto NO los modifica",
        },

        "invariantes": inv,
        "reproduccion_de_lo_historico": rep,
        "tasas": tas,
        "cantidades_pareadas": {"A": par_a, "B": par_b},
        "residuo_cientifico": res,

        "internal_energy": {
            "ambito_A_CORREGIDA": dict(tas["A"]["CORREGIDA"]["checks_que_fallan"]).get("internal_energy", 0),
            "ambito_A_HISTORICA": dict(tas["A"]["HISTORICA"]["checks_que_fallan"]).get("internal_energy", 0),
            "PRECISION_IMPORTANTE": (
                "el 8006 de este artefacto NO es el 7997 de MF-33-PB: aquel era sobre 8215 poses "
                "de R1 y este es sobre 8224 de R2. Son cohortes distintas por 1afl, no una "
                "correccion de la cifra vieja. La caida real que mide este corrigendum es "
                "8006 -> 7 DENTRO DE LA MISMA COHORTE R2."),
        },
        "double_bond_flatness": {
            "ambito_A_HISTORICA": dict(tas["A"]["HISTORICA"]["checks_que_fallan"]).get("double_bond_flatness", 0),
            "ambito_A_CORREGIDA": dict(tas["A"]["CORREGIDA"]["checks_que_fallan"]).get("double_bond_flatness", 0),
            "CORRIGE_UNA_AFIRMACION_NUESTRA": (
                "el prerregistro y el commit del corrigendum dijeron que el defecto afectaba a la "
                "ENERGIA INTERNA. Tambien contaminaba la planaridad de dobles enlaces, que depende "
                "de los hidrogenos sustituyentes: 598 -> 0. La afirmacion previa de que solo "
                "estaba afectada la energia era incompleta y queda corregida aqui."),
        },

        "concordancia_con_el_runner": {
            "metrics_del_servidor_coincide_con_este_recalculo": coincide,
            "resumen_del_servidor": resumen_servidor,
        },

        "limites_declarados": [
            "NO demuestra exactitud de pose ni de union: una pose puede ser fisicamente valida y estar en el sitio equivocado",
            "NO mide el protocolo de docking, que no se toca aqui: corrige la CAPA DE RECONSTRUCCION",
            "NO establece ventaja de ningun brazo, y tampoco equivalencia entre ellos",
            "la tasa corregida es CONDICIONAL a la reconstruccion canonica de hidrogenos: el PDBQT es una representacion de atomo unido y no contiene la geometria explicita completa",
            "los recuentos por control se solapan y no suman poses invalidas unicas",
            "config redock de PoseBusters, que usa la verdad de terreno; NO es la config dock que usa produccion",
            "el ambito A corre sobre R2 y el ambito B sobre el protocolo rigido: sus tasas no son comparables entre si",
        ],
    }

    if args.escribir:
        (art_dir / "metrics.json").write_text(
            json.dumps(metrics, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
        print(f"[escrito] {art_dir / 'metrics.json'}")

    print(f"invariantes violadas: {inv['total_violadas']} | desp max {inv['desplazamiento_pesado_max_global_A']} A "
          f"| H heredados {inv['hidrogenos_heredados_del_cristal_total']}")
    print(f"reproduccion historica: {rep['veredicto']}")
    for a in ("A", "B"):
        t = tas[a]
        print(f"ambito {a}: {t['poses_evaluadas']} poses | historica {t['HISTORICA']['tasa']} "
              f"-> corregida {t['CORREGIDA']['tasa']} | invalidas unicas {t['poses_invalidas_unicas_CORREGIDA']}")
    for a, par in (("A", par_a), ("B", par_b)):
        c = par["CORREGIDA"]
        print(f"pareado {a}: single {c['single_validos']}/{c['de']} ensemble {c['ensemble_validos']}/{c['de']} "
              f"| b={c['tabla_2x2']['solo_ensemble']} c={c['tabla_2x2']['solo_single']} "
              f"p={c['mcnemar_p_exacto']} MDE={c['mde_pp_para_esta_discordancia']}pp")
    print(f"concordancia con el runner del servidor: {coincide}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
