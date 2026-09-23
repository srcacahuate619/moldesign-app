#!/usr/bin/env python3
r"""lcpo_bri_h2.py — MM-GBSA, H2 y H10: P1-P4 de LCPO ajustados por elemento para Br e I.

**Tipo: ajuste en entrenamiento, evaluación en validación y prueba.** Hipótesis
H2 y H10 de `docs/validacion_mmgbsa.md`, después de que H1 (los coeficientes
del Cl publicado con radios de Bondi) quedara NO_GO (`MMGBSA-H1-LCPO-BONDI`).

# El ajuste

El radio es el de H1 (Bondi: Br 1,85 Å, I 1,98 Å) y no se ajusta: define la
esfera cuya SASA exacta se aproxima, así que ajustarlo no tendría objetivo.
Lo que se ajusta son P1-P4. El área LCPO de un átomo es **lineal** en sus
propios coeficientes:

    A_i = P1·S_i + P2·ΣA_ij + P3·ΣΣA_jk + P4·Σ(A_ij·Σ_k A_jk)

y no depende de los P de ningún otro átomo. Por eso cada término se obtiene
evaluando `areas_lcpo` (la implementación validada contra OpenMM, sin tocarla)
con un P unitario, y el ajuste es un mínimo cuadrado ordinario exacto, por
elemento, sólo con los átomos de **entrenamiento** de las particiones selladas
(`MMGBSA-PARTICIONES-BRI-V1`). Como el radio no cambia, el área de los vecinos
es la de H1, que ya no empeoraba.

Guardián: con los P del Cl publicado, la suma de los cuatro términos reproduce
el área LCPO que H1 registró para cada átomo (≤ 1e-6 Å²). Un término mal
calculado daría un ajuste de otro modelo.

# H10 en la misma corrida

El mismo ajuste con una partición **aleatoria por molécula** (misma semilla,
mismos tamaños 60/20/20) en vez de por scaffold. Si el error en la validación
por scaffold es mucho mayor que en la aleatoria, los coeficientes han
memorizado familias químicas.

# Etapas

    python backend/audits/lcpo_bri_h2.py bases --trabajo <dir> --salida <crudo.json>
    python backend/audits/lcpo_bri_h2.py ajustar --crudo <crudo.json> --artefactos <dir>
    python backend/audits/lcpo_bri_h2.py estabilidad --crudo <crudo.json>   # sólo entrenamiento

Lo que NO hace: no toca el término polar (H3) ni activa MM-GBSA.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import numpy as np

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import lcpo_bri_h1 as h1  # noqa: E402 - sellado, sin modificar
from lcpo_vs_sasa_exacta import (  # noqa: E402 - sin modificar
    _desempaquetar,
    _TiposEnMayuscula,
    areas_lcpo,
    sasa_numerica,
)

REMUESTREOS_ESTABILIDAD = 1000


def _sha(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


# ── 1. Términos de la base ───────────────────────────────────────────────

def _bases_uno(pid: str, trabajo: str, puntos: int) -> dict[str, Any]:
    from openmm import app, unit
    from openmm.app import element as elemento
    from openmm.app.internal import lcpo
    t0 = time.time()
    try:
        carpeta = Path(trabajo) / pid
        topologia = app.AmberPrmtopFile(str(carpeta / "ligand.prmtop"))
        coords = np.array(app.AmberInpcrdFile(str(carpeta / "ligand.inpcrd"))
                          .positions.value_in_unit(unit.angstrom), dtype=np.float64)
        elementos = list(topologia.elements)
        numeros = [0 if e is None else e.atomic_number for e in elementos]
        marcador = [elemento.chlorine if z in h1.BRI else e for z, e in zip(numeros, elementos, strict=True)]
        base = lcpo.getLCPOParamsAmber(_TiposEnMayuscula(topologia._prmtop), marcador)
        cl = lcpo.LCPO_PARAMETERS["Cl"]
        bri = {i: h1.BRI[z] for i, z in enumerate(numeros) if z in h1.BRI}
        parametros = [(h1.RADIO_BONDI[bri[i]], *cl[1:]) if i in bri else fila for i, fila in enumerate(base)]
        radios, *_ = _desempaquetar(parametros)
        terminos = []
        for k in range(4):
            unitario = [np.zeros(len(radios)) for _ in range(4)]
            unitario[k][:] = 1.0
            terminos.append(areas_lcpo(coords, radios, *unitario))
        terminos = np.array(terminos)                     # (4, n_atomos)
        exacta = sasa_numerica(coords, radios, puntos, 0.0)
        con_cl = np.array(cl[1:]) @ terminos             # el área de H1 reconstruida
        return {"pid": pid, "estado": "ok", "duracion_s": round(time.time() - t0, 2), "atomos": [
            {"indice": i, "elemento": bri[i], "terminos": [float(x) for x in terminos[:, i]],
             "sasa_exacta_A2": float(exacta[i]), "lcpo_con_cl_publicado_A2": float(con_cl[i])} for i in sorted(bri)]}
    except Exception as exc:  # noqa: BLE001 - un fallo es un resultado: se registra, no se oculta
        return {"pid": pid, "estado": "fallo", "motivo": f"{type(exc).__name__}: {exc}"[:400]}


def bases(args) -> int:
    salida = Path(args.salida)
    if salida.exists():
        raise SystemExit(f"{salida} ya existe")
    trabajo = Path(args.trabajo)
    pids = sorted(p.name for p in trabajo.iterdir() if (p / "ligand.prmtop").is_file())
    t0 = time.time()
    resultados = []
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        futuros = [ex.submit(_bases_uno, p, str(trabajo), args.puntos) for p in pids]
        for i, f in enumerate(as_completed(futuros), 1):
            r = f.result()
            resultados.append(r)
            print(f"  [{i}/{len(pids)}] {r['pid']}: {r['estado']} {r.get('motivo', '')}", flush=True)
    resultados.sort(key=lambda r: r["pid"])
    import openmm
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(json.dumps({"experimento": "MMGBSA-H2-LCPO-AJUSTE", "generado_utc": h1._ahora(),
                                  "openmm": openmm.__version__, "puntos_shrake_rupley": args.puntos,
                                  "radios_A": h1.RADIO_BONDI, "duracion_s": round(time.time() - t0, 1),
                                  "ligandos": resultados}, ensure_ascii=False) + "\n",
                      encoding="utf-8", newline="\n")
    print(f"escrito {salida} ({round(time.time() - t0, 1)} s)")
    return 0


# ── Gate de H2 y H10 (el del prerregistro) ──────────────────────────────
#
# Piloto de estabilidad SÓLO en entrenamiento (etapa `estabilidad`, antes del
# prerregistro): los cuatro términos están casi alineados (número de condición
# ~1e4) y los coeficientes sueltos no están identificados — CV de P3 94 % (Br)
# y 997 % (I) — mientras el área predicha varía menos de 1 Å² entre
# remuestreos. El criterio del documento (CV < 20 % en cada coeficiente)
# fallaría siempre sin decir nada del ajuste; la estabilidad se mide donde
# importa, en la predicción, y en P1, que es el término dominante.
#
# Brazos: `completo` (P1-P4) y `reducido` (P1, P2; P3 y P4 los del Cl
# publicado). Por elemento se elige en VALIDACIÓN: el reducido, salvo que el
# completo baje la mediana |error| de validación en más de 0,5 Å². La prueba
# sólo confirma el elegido. Criterios, en validación y en prueba, para el
# elegido: los 1 y 2 de H1 (mediana ≤ 2,81, p90 ≤ 7,25, IC95 del sesgo dentro
# de ±2,81 Å²); CV bootstrap de P1 < 20 %; y mediana de la DE bootstrap del
# área predicha en validación ≤ 1,0 Å². Los vecinos no cambian respecto de H1
# (mismo radio), donde ya no empeoraban. H10, veredicto aparte: con el brazo
# elegido, la mediana de validación por scaffold no supera a la de una
# partición aleatoria por molécula en más de 1,0 Å².

MARGEN_PARSIMONIA = 0.5
TOPE_CV_P1 = 0.20
TOPE_DE_PREDICCION = 1.0
MARGEN_H10 = 1.0


# ── 2. Datos, particiones y ajuste ───────────────────────────────────────

def _cargar(crudo: dict[str, Any]):
    seleccion = json.loads((h1.SALIDA / "seleccion.json").read_text(encoding="utf-8"))
    particiones = json.loads((h1.SALIDA / "particiones.json").read_text(encoding="utf-8"))
    info = {x["pid"]: x for x in seleccion["ligandos"]}
    filas = []
    for r in crudo["ligandos"]:
        if r["estado"] != "ok":
            continue
        for a in r["atomos"]:
            filas.append({"pid": r["pid"], "grupo": info[r["pid"]]["grupo"], "elemento": a["elemento"],
                          "particion": particiones["por_pid"][r["pid"]], "x": np.array(a["terminos"]),
                          "y": a["sasa_exacta_A2"], "con_cl": a["lcpo_con_cl_publicado_A2"]})
    return filas, info, particiones


def _particion_aleatoria(pids: list[str]) -> dict[str, str]:
    """H10: 60/20/20 por molécula, al azar con la semilla sellada; sin mirar scaffolds."""
    orden = sorted(pids, key=lambda p: hashlib.sha256(f"{h1.SEMILLA}:aleatoria:{p}".encode()).hexdigest())
    n = len(orden)
    cortes = (round(0.6 * n), round(0.8 * n))
    return {p: ("entrenamiento" if i < cortes[0] else "validacion" if i < cortes[1] else "prueba")
            for i, p in enumerate(orden)}


P_CL = None  # P1-P4 del Cl publicado; se leen de OpenMM al primer uso


def _p_cl() -> np.ndarray:
    global P_CL
    if P_CL is None:
        from openmm.app.internal import lcpo
        P_CL = np.array(lcpo.LCPO_PARAMETERS["Cl"][1:], dtype=np.float64)
    return P_CL


def _ajustar(filas, brazo: str = "completo") -> np.ndarray:
    x = np.array([f["x"] for f in filas])
    y = np.array([f["y"] for f in filas])
    if brazo == "completo":
        beta, *_ = np.linalg.lstsq(x, y, rcond=None)
        return beta
    fijos = _p_cl()[2:]
    beta12, *_ = np.linalg.lstsq(x[:, :2], y - x[:, 2:] @ fijos, rcond=None)
    return np.concatenate([beta12, fijos])


def _bootstrap_coeficientes(filas, rng, n, brazo: str = "completo"):
    por_grupo = defaultdict(list)
    for f in filas:
        por_grupo[f["grupo"]].append(f)
    grupos = sorted(por_grupo)
    betas = []
    for _ in range(n):
        elegidos = rng.choice(len(grupos), size=len(grupos), replace=True)
        muestra = [f for k in elegidos for f in por_grupo[grupos[k]]]
        betas.append(_ajustar(muestra, brazo))
    return np.array(betas)


def ajustar(args) -> int:
    crudo_ruta = Path(args.crudo)
    crudo = json.loads(crudo_ruta.read_text(encoding="utf-8"))
    filas, info, particiones = _cargar(crudo)
    rng = np.random.default_rng(h1.SEMILLA)

    def est(fs, beta):
        errores = [float(f["x"] @ beta - f["y"]) for f in fs]
        return h1._estadistica(errores, [f["grupo"] for f in fs], rng)

    def criterios(d):
        if d is None or d["n"] < h1.MIN_ATOMOS:
            return None
        return {"mediana": d["mediana_abs_A2"] <= h1.FONDO_MEDIANA, "p90": d["p90_abs_A2"] <= h1.FONDO_P90,
                "sesgo": (-h1.FONDO_MEDIANA <= d["ic95_media_con_signo_A2"][0]
                          and d["ic95_media_con_signo_A2"][1] <= h1.FONDO_MEDIANA)}

    resultado: dict[str, Any] = {}
    for e in ("Br", "I"):
        de = [f for f in filas if f["elemento"] == e]
        por_s = {s: [f for f in de if f["particion"] == s] for s in h1.OBJETIVO}
        brazos = {}
        for brazo in ("completo", "reducido"):
            beta = _ajustar(por_s["entrenamiento"], brazo)
            betas = _bootstrap_coeficientes(por_s["entrenamiento"], rng, REMUESTREOS_ESTABILIDAD, brazo)
            x_val = np.array([f["x"] for f in por_s["validacion"]])
            de_pred = betas @ x_val.T if len(x_val) else np.zeros((1, 0))
            brazos[brazo] = {
                "P": [float(v) for v in beta],
                "cv_bootstrap": [float(v) for v in betas.std(axis=0) / np.maximum(np.abs(betas.mean(axis=0)), 1e-300)],
                "de_prediccion_validacion_mediana_A2": float(np.median(de_pred.std(axis=0))) if de_pred.size else None,
                "numero_de_condicion_entrenamiento": float(np.linalg.cond(np.array([f["x"] for f in por_s["entrenamiento"]]))),
                "por_particion": {s: est(por_s[s], beta) for s in h1.OBJETIVO},
            }
        mediana_val = {b: brazos[b]["por_particion"]["validacion"]["mediana_abs_A2"] for b in brazos}
        elegido = "completo" if mediana_val["completo"] < mediana_val["reducido"] - MARGEN_PARSIMONIA else "reducido"
        b = brazos[elegido]
        veredictos = {}
        for s in ("validacion", "prueba"):
            c = criterios(b["por_particion"][s])
            if c is None:
                veredictos[s] = {"resultado": "INDETERMINADO", "motivo": f"menos de {h1.MIN_ATOMOS} átomos"}
                continue
            c["cv_P1"] = b["cv_bootstrap"][0] < TOPE_CV_P1
            c["de_prediccion"] = (b["de_prediccion_validacion_mediana_A2"] is not None
                                  and b["de_prediccion_validacion_mediana_A2"] <= TOPE_DE_PREDICCION)
            veredictos[s] = {"resultado": "PASA" if all(c.values()) else "FALLA", "comprobaciones": c}

        # H10: el mismo brazo, con una partición aleatoria por molécula.
        aleatoria = _particion_aleatoria(sorted({f["pid"] for f in filas}))
        ent_a = [f for f in de if aleatoria[f["pid"]] == "entrenamiento"]
        val_a = [f for f in de if aleatoria[f["pid"]] == "validacion"]
        beta_a = _ajustar(ent_a, elegido)
        d_a = est(val_a, beta_a)
        h10 = {"mediana_validacion_scaffold_A2": b["por_particion"]["validacion"]["mediana_abs_A2"],
               "mediana_validacion_aleatoria_A2": d_a["mediana_abs_A2"] if d_a else None,
               "n_validacion_aleatoria": d_a["n"] if d_a else 0, "P_aleatoria": [float(v) for v in beta_a]}
        h10["resultado"] = ("INDETERMINADO" if not d_a or d_a["n"] < h1.MIN_ATOMOS else
                            "PASA" if h10["mediana_validacion_scaffold_A2"] <= h10["mediana_validacion_aleatoria_A2"] + MARGEN_H10
                            else "FALLA")
        resultado[e] = {"n_atomos": {s: len(por_s[s]) for s in por_s}, "brazos": brazos, "elegido": elegido,
                        "regla_de_eleccion": f"reducido salvo que completo baje la mediana de validación > {MARGEN_PARSIMONIA} Å²",
                        "gate": veredictos, "h10": h10}

    casos = [resultado[e]["gate"][s]["resultado"] for e in resultado for s in resultado[e]["gate"]]
    decision = ("GO" if all(c == "PASA" for c in casos) else
                "NO_GO" if any(c == "FALLA" for c in casos) else "INCONCLUSIVE")
    h10_casos = [resultado[e]["h10"]["resultado"] for e in resultado]
    metricas = {
        "experimento": "MMGBSA-H2-LCPO-AJUSTE", "generado_utc": h1._ahora(),
        "crudo": {"archivo": crudo_ruta.name, "sha256": _sha(crudo_ruta), "openmm": crudo["openmm"],
                  "puntos_shrake_rupley": crudo["puntos_shrake_rupley"]},
        "particiones_sha256": _sha(h1.SALIDA / "particiones.json"), "radios_A": h1.RADIO_BONDI,
        "P_cl_publicado": [float(v) for v in _p_cl()],
        "umbrales": {"fondo_mediana_A2": h1.FONDO_MEDIANA, "fondo_p90_A2": h1.FONDO_P90, "tope_cv_P1": TOPE_CV_P1,
                     "tope_de_prediccion_A2": TOPE_DE_PREDICCION, "margen_parsimonia_A2": MARGEN_PARSIMONIA,
                     "margen_h10_A2": MARGEN_H10, "remuestreos": REMUESTREOS_ESTABILIDAD, "semilla": h1.SEMILLA},
        "fallos": [{"pid": r["pid"], "motivo": r["motivo"]} for r in crudo["ligandos"] if r["estado"] != "ok"],
        "por_elemento": resultado, "decision_h2_por_el_gate": decision,
        "h10": "PASA" if all(c == "PASA" for c in h10_casos) else "FALLA" if "FALLA" in h10_casos else "INDETERMINADO",
        "no_demuestra": ("Que el área LCPO sea el término no polar correcto: la SASA numérica es una referencia "
                         "geométrica. Tampoco valida el término polar (H3)."),
    }
    destino = Path(args.artefactos)
    destino.mkdir(parents=True, exist_ok=True)
    (destino / "metrics.json").write_text(json.dumps(metricas, ensure_ascii=False, indent=1) + "\n",
                                          encoding="utf-8", newline="\n")
    with open(destino / "per_complex.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for f in filas:
            fila = {"pid": f["pid"], "grupo": f["grupo"], "elemento": f["elemento"], "particion": f["particion"],
                    "sasa_exacta_A2": round(f["y"], 4), "terminos": [round(float(v), 6) for v in f["x"]]}
            for e in resultado:
                if e == f["elemento"]:
                    for brazo, d in resultado[e]["brazos"].items():
                        fila[f"lcpo_{brazo}_A2"] = round(float(f["x"] @ np.array(d["P"])), 4)
            fh.write(json.dumps(fila, ensure_ascii=False) + "\n")

    for e, r in resultado.items():
        print(f"\n== {e}: átomos {r['n_atomos']}; elegido en validación: {r['elegido']}")
        for brazo, d in r["brazos"].items():
            print(f"   {brazo:9s} P {np.round(d['P'], 6).tolist()}  CV {np.round(d['cv_bootstrap'], 3).tolist()}"
                  f"  DE pred. val. {d['de_prediccion_validacion_mediana_A2']:.3f}")
            for s, x in d["por_particion"].items():
                if x:
                    print(f"      {s:13s} n {x['n']:3d}  mediana {x['mediana_abs_A2']:6.3f}  p90 {x['p90_abs_A2']:6.3f}"
                          f"  media {x['media_con_signo_A2']:+6.3f}  IC95 {x['ic95_media_con_signo_A2']}")
        print(f"   gate: {json.dumps(r['gate'], ensure_ascii=False)}")
        print(f"   H10: {r['h10']}")
    print(f"\ndecisión H2 por el gate: {decision}; H10: {metricas['h10']}")
    return 0


def estabilidad(args) -> int:
    """Sólo entrenamiento: cuánto varía cada coeficiente entre remuestreos. No mira validación ni prueba."""
    crudo = json.loads(Path(args.crudo).read_text(encoding="utf-8"))
    filas, _, _ = _cargar(crudo)
    rng = np.random.default_rng(h1.SEMILLA)
    for e in ("Br", "I"):
        entrenamiento = [f for f in filas if f["elemento"] == e and f["particion"] == "entrenamiento"]
        beta = _ajustar(entrenamiento)
        betas = _bootstrap_coeficientes(entrenamiento, rng, REMUESTREOS_ESTABILIDAD)
        x = np.array([f["x"] for f in entrenamiento])
        prediccion = betas @ x.T
        print(f"{e}: n {len(entrenamiento)} átomos en {len({f['grupo'] for f in entrenamiento})} grupos; "
              f"número de condición {np.linalg.cond(x):.3e}")
        print(f"   P ajustados {np.round(beta, 6).tolist()}")
        print(f"   CV bootstrap {np.round(betas.std(axis=0) / np.abs(betas.mean(axis=0)), 3).tolist()}")
        print(f"   DE bootstrap del área predicha en entrenamiento: mediana {np.median(prediccion.std(axis=0)):.3f} Å²")
    return 0


def main() -> int:
    for flujo in (sys.stdout, sys.stderr):
        if hasattr(flujo, "reconfigure"):
            flujo.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="etapa", required=True)
    b = sub.add_parser("bases")
    b.add_argument("--trabajo", type=Path, required=True)
    b.add_argument("--salida", type=Path, required=True)
    b.add_argument("--puntos", type=int, default=50_000)
    b.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    b.set_defaults(func=bases)
    a = sub.add_parser("ajustar")
    a.add_argument("--crudo", type=Path, required=True)
    a.add_argument("--artefactos", type=Path, required=True)
    a.set_defaults(func=ajustar)
    s = sub.add_parser("estabilidad")
    s.add_argument("--crudo", type=Path, required=True)
    s.set_defaults(func=estabilidad)
    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
