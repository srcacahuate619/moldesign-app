#!/usr/bin/env python3
r"""gbn2_azufre_amber_h13.py — MMGBSA-H13: OpenMM descreena como egb.F90 y el azufre deja de discrepar.

**Tipo: medición de implementación.** `MMGBSA-H5-GBN2-PARIDAD` encontró que
OpenMM 8.5.2 y sander discrepan en GBn2 hasta 11,24 kcal/mol en toda
topología con azufre. El código de Amber (AmberClassic `src/msander/egb.F90`,
leído el 2026-09-23) lo explica: el radio apantallado del S es negativo
(screen −0,703469), la condición `dij > 4*sj` se cumple siempre y Amber usa
SIEMPRE su serie de Taylor para el S, mientras OpenMM evalúa la integral
cerrada. Amber es la referencia de GBn2: el modelo se parametrizó con ese
código (Nguyen, Roe y Simmerling, 2013).

`apply_amber_gbn2_descreening` (`services/chemistry/amber_compatibility.py`)
reescribe las dos expresiones de GBn2 de OpenMM con las ramas de egb.F90:
corte y cola de rgbmax (25 Å, el de sander con igb=8), serie para
dij > 4·sj, integral cerrada en el resto y el tope de 1/30 Å⁻¹ del radio
inverso. Aquí se mide si con esa corrección OpenMM reproduce a sander.

# Casos

- Las 55 topologías de `lcpo_halogenos.py` (12 con S). La regla geométrica de
  MMGBSA-H5-R1 deja INDETERMINADAS las imposibles (5mlj, 6gnp).
- Dos péptidos ff14SB con Met y Cys construidos con tleap: `ACE MET CYS NME`
  y uno de 17 residuos (`ACE`, 4 Ala, Met, 4 Ala, Cys, 4 Ala, `NME`), cuya
  extensión supera 25 Å y ejercita la cola y el corte de rgbmax.

# Etapas

    python backend/audits/gbn2_azufre_amber_h13.py peptidos --trabajo <dir>       # tleap (servidor)
    python backend/audits/gbn2_azufre_amber_h13.py medir --trabajo <dir> --salida <crudo.json> [--sin-sander]
    python backend/audits/gbn2_azufre_amber_h13.py comparar --linux <crudo.json> --windows <crudo.json> --artefactos <dir>

Lo que NO hace: no conecta nada a producción (MM-GBSA sigue
EXPERIMENTAL_NOT_ENABLED) ni dice que GBn2 sea bueno para el S: dice si
OpenMM calcula el mismo modelo que se parametrizó.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import numpy as np

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(AQUI.parent))
import gbn2_paridad_halogenos as h5  # noqa: E402 - sellado, sin modificar
import gbn2_paridad_halogenos_r1 as r1  # noqa: E402 - sellado, sin modificar

# La corrección con el rgbmax de sander, OpenMM tal cual, y un diagnóstico que
# no entra en el gate: las ramas de Amber sin corte (rgbmax enorme), para
# separar lo que es del azufre de lo que es del corte a 25 Å.
VARIANTES = {"openmm_8.5.2": None, "con_ramas_de_amber": 25.0, "diagnostico_ramas_sin_rgbmax": 1.0e4}

PEPTIDOS = {
    "pep_met_cys": "ACE MET CYS NME",
    "pep_largo_met_cys": "ACE ALA ALA ALA ALA MET ALA ALA ALA ALA CYS ALA ALA ALA ALA NME",
}


def peptidos(args) -> int:
    trabajo = Path(args.trabajo)
    for nombre, secuencia in PEPTIDOS.items():
        carpeta = trabajo / nombre
        carpeta.mkdir(parents=True, exist_ok=False)
        (carpeta / "leap.in").write_text(
            "source leaprc.protein.ff14SB\nset default PBRadii mbondi3\n"
            f"p = sequence {{ {secuencia} }}\nsaveamberparm p ligand.prmtop ligand.inpcrd\nquit\n")
        with open(carpeta / "tleap.stdout", "w") as out:
            subprocess.run(["tleap", "-f", "leap.in"], cwd=carpeta, stdout=out, stderr=subprocess.STDOUT,
                           check=True, timeout=300)
        print(nombre, (carpeta / "ligand.prmtop").is_file())
    return 0


def _openmm_gb(topologia, posiciones, rgbmax: float | None) -> dict[str, Any]:
    """rgbmax None: OpenMM tal cual; un número: las ramas de egb.F90 con ese rgbmax en Å."""
    import openmm
    from openmm import app, unit

    from services.chemistry.amber_compatibility import (
        apply_amber_gbn2_descreening,
        apply_amber_gbn2_phosphorus,
    )
    sistema = topologia.createSystem(nonbondedMethod=app.NoCutoff, constraints=None, implicitSolvent=app.GBn2,
                                     soluteDielectric=1.0, solventDielectric=78.5, sasaMethod=None,
                                     removeCMMotion=False)
    apply_amber_gbn2_phosphorus(sistema, topologia.topology)
    if rgbmax is not None:
        apply_amber_gbn2_descreening(sistema, rgbmax_angstrom=rgbmax)
    nb = gb = None
    for f in sistema.getForces():
        if isinstance(f, openmm.NonbondedForce):
            f.setForceGroup(h5.GRUPO_NB)
            nb = f
        elif isinstance(f, openmm.CustomGBForce):
            f.setForceGroup(h5.GRUPO_GB)
            gb = f
        else:
            f.setForceGroup(h5.GRUPO_ENLACE)
    contexto = openmm.Context(sistema, openmm.VerletIntegrator(0.001), openmm.Platform.getPlatformByName("Reference"))
    contexto.setPositions(posiciones)
    kcal = unit.kilocalories_per_mole

    def grupo(g):
        e = contexto.getState(getEnergy=True, getForces=True, groups={g})
        return e.getPotentialEnergy().value_in_unit(kcal), e.getForces(asNumpy=True).value_in_unit(kcal / unit.angstrom)

    e_enl, f_enl = grupo(h5.GRUPO_ENLACE)
    e_nb, f_nb = grupo(h5.GRUPO_NB)
    e_gb, f_gb = grupo(h5.GRUPO_GB)
    total = contexto.getState(getEnergy=True)
    e_tot = total.getPotentialEnergy().value_in_unit(kcal)
    for i in range(nb.getNumParticles()):
        _, s, e = nb.getParticleParameters(i)
        nb.setParticleParameters(i, 0.0, s, e)
    for j in range(nb.getNumExceptions()):
        a, b, _, s, e = nb.getExceptionParameters(j)
        nb.setExceptionParameters(j, a, b, 0.0, s, e)
    nb.updateParametersInContext(contexto)
    e_lj, f_lj = grupo(h5.GRUPO_NB)
    f_coul = f_nb - f_lj
    assert gb is not None
    return {"energia_kcal_mol": e_tot, "gb_kcal_mol": e_gb,
            "fuerzas_convertidas": (f_enl + f_lj + f_coul * (h5.K_AMBER / h5.K_OPENMM_NB)
                                    + f_gb * (h5.K_AMBER / h5.K_OPENMM_GB))}


def _medir_uno(nombre: str, trabajo: str, con_sander: bool) -> dict[str, Any]:
    from openmm import app, unit
    carpeta = Path(trabajo) / nombre
    t0 = time.time()
    try:
        prmtop, inpcrd = carpeta / "ligand.prmtop", carpeta / "ligand.inpcrd"
        topologia = app.AmberPrmtopFile(str(prmtop))
        coordenadas = app.AmberInpcrdFile(str(inpcrd))
        xyz = np.array(coordenadas.positions.value_in_unit(unit.angstrom), dtype=np.float64)
        numeros = [0 if e is None else e.atomic_number for e in topologia.elements]
        d = np.linalg.norm(xyz[:, None] - xyz[None], axis=2)
        fila: dict[str, Any] = {
            "caso": nombre, "estado": "ok", "n_atomos": len(numeros), "n_azufre": numeros.count(16),
            "extension_maxima_A": round(float(d.max()), 3), "geometria": r1.geometria(topologia, xyz),
            "prmtop_sha256": h5._sha(prmtop), "inpcrd_sha256": h5._sha(inpcrd), "variantes": {}}
        for variante, rgbmax in VARIANTES.items():
            om = _openmm_gb(topologia, coordenadas.positions, rgbmax)
            fila["variantes"][variante] = {"energia_kcal_mol": om["energia_kcal_mol"], "gb_kcal_mol": om["gb_kcal_mol"],
                                           "fuerzas_convertidas": om["fuerzas_convertidas"].tolist()}
        if con_sander:
            sa = h5._sander(prmtop, xyz, True)
            t = sa["terminos_kcal_mol"]
            diferencia = ((h5.K_OPENMM_NB / h5.K_AMBER - 1) * (t["elec"] + t["elec_14"])
                          + (h5.K_OPENMM_GB / h5.K_AMBER - 1) * t["gb"])
            fila["sander"] = {"tot_kcal_mol": t["tot"], "gb_kcal_mol": t["gb"],
                              "diferencia_de_constantes_kcal_mol": diferencia,
                              "fuerzas": sa["fuerzas"].tolist()}
            for v in fila["variantes"].values():
                v["residuo_kcal_mol"] = abs(v["energia_kcal_mol"] - t["tot"] - diferencia)
                v["max_error_fuerza_kcal_mol_A"] = float(np.max(np.abs(np.array(v["fuerzas_convertidas"])
                                                                      - sa["fuerzas"])))
                v["pasa"] = v["residuo_kcal_mol"] < h5.TOLERANCIA_ENERGIA and \
                    v["max_error_fuerza_kcal_mol_A"] < h5.TOLERANCIA_FUERZA
        fila["duracion_s"] = round(time.time() - t0, 2)
        return fila
    except Exception as exc:  # noqa: BLE001 - un fallo es un resultado: se registra, no se oculta
        return {"caso": nombre, "estado": "fallo", "motivo": f"{type(exc).__name__}: {exc}"[:400]}


def medir(args) -> int:
    import openmm
    salida = Path(args.salida)
    if salida.exists():
        raise SystemExit(f"{salida} ya existe")
    casos = []
    for raiz in args.trabajo:
        casos += [(p.name, str(raiz)) for p in sorted(Path(raiz).iterdir()) if (p / "ligand.prmtop").is_file()]
    t0 = time.time()
    resultados = []
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        futuros = [ex.submit(_medir_uno, n, r, not args.sin_sander) for n, r in casos]
        for i, f in enumerate(as_completed(futuros), 1):
            r = f.result()
            resultados.append(r)
            estado = r["estado"]
            if estado == "ok" and "sander" in r:
                estado = " / ".join(f"{k}: {'PASA' if v['pasa'] else 'NO PASA'}" for k, v in r["variantes"].items())
            print(f"  [{i}/{len(casos)}] {r['caso']}: {estado} {r.get('motivo', '')}", flush=True)
    resultados.sort(key=lambda r: r["caso"])
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(json.dumps({"experimento": "MMGBSA-H13-AZUFRE-AMBER", "generado_utc": h5._ahora(),
                                  "con_sander": not args.sin_sander, "entorno": h5._entorno(not args.sin_sander),
                                  "openmm": openmm.__version__, "duracion_s": round(time.time() - t0, 1),
                                  "casos": resultados}, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(f"escrito {salida}")
    return 0


def comparar(args) -> int:
    linux = json.loads(Path(args.linux).read_text(encoding="utf-8"))
    windows = json.loads(Path(args.windows).read_text(encoding="utf-8")) if args.windows else None
    por_w = {c["caso"]: c for c in windows["casos"]} if windows else {}
    filas = []
    for c in linux["casos"]:
        if c["estado"] != "ok":
            filas.append({"caso": c["caso"], "estado": c["estado"], "motivo": c.get("motivo")})
            continue
        f = {"caso": c["caso"], "estado": "ok", "n_atomos": c["n_atomos"], "n_azufre": c["n_azufre"],
             "extension_maxima_A": c["extension_maxima_A"], "geometria_imposible": c["geometria"]["imposible"],
             "prmtop_sha256": c["prmtop_sha256"], "inpcrd_sha256": c["inpcrd_sha256"],
             "sander_gb_kcal_mol": c["sander"]["gb_kcal_mol"]}
        for k, v in c["variantes"].items():
            f[k] = {"gb_kcal_mol": v["gb_kcal_mol"], "residuo_kcal_mol": v["residuo_kcal_mol"],
                    "max_error_fuerza_kcal_mol_A": v["max_error_fuerza_kcal_mol_A"], "pasa": v["pasa"]}
        w = por_w.get(c["caso"])
        if w and w["estado"] == "ok":
            vw = w["variantes"]["con_ramas_de_amber"]
            vl = c["variantes"]["con_ramas_de_amber"]
            f["windows"] = {
                "mismas_entradas": w["prmtop_sha256"] == c["prmtop_sha256"] and w["inpcrd_sha256"] == c["inpcrd_sha256"],
                "diferencia_energia_kcal_mol": abs(vw["energia_kcal_mol"] - vl["energia_kcal_mol"]),
                "diferencia_fuerza_kcal_mol_A": float(np.max(np.abs(np.array(vw["fuerzas_convertidas"])
                                                                   - np.array(vl["fuerzas_convertidas"]))))}
        f["resultado"] = ("INDETERMINADO" if f["geometria_imposible"]
                          else "PASA" if f["con_ramas_de_amber"]["pasa"] else "FALLA")
        filas.append(f)
    ok = [f for f in filas if f["estado"] == "ok"]

    def resumen(grupo):
        return {"n": len(grupo), **{r: sum(f["resultado"] == r for f in grupo) for r in ("PASA", "FALLA", "INDETERMINADO")},
                "pasan_sin_parche": sum(f["openmm_8.5.2"]["pasa"] for f in grupo),
                "max_residuo_con_parche_kcal_mol": h5._max(f["con_ramas_de_amber"]["residuo_kcal_mol"]
                                                          for f in grupo if not f["geometria_imposible"]),
                "max_residuo_sin_parche_kcal_mol": h5._max(f["openmm_8.5.2"]["residuo_kcal_mol"]
                                                          for f in grupo if not f["geometria_imposible"])}

    con_s = [f for f in ok if f["n_azufre"]]
    sin_s = [f for f in ok if not f["n_azufre"]]
    pep = [f for f in ok if f["caso"].startswith("pep_")]
    ww = [f.get("windows") for f in ok]
    metricas = {
        "experimento": "MMGBSA-H13-AZUFRE-AMBER", "generado_utc": h5._ahora(),
        "rgbmax_A": 25.0, "tolerancias": {"energia": h5.TOLERANCIA_ENERGIA, "fuerza": h5.TOLERANCIA_FUERZA,
                                          "entre_maquinas": h5.TOLERANCIA_ENTRE_MAQUINAS},
        "con_azufre": resumen(con_s), "sin_azufre": resumen(sin_s), "peptidos": resumen(pep),
        "fallos": [f for f in filas if f["estado"] != "ok"],
        "windows": None if windows is None else {
            "comparaciones": sum(x is not None for x in ww), "esperadas": len(ok),
            "mismas_entradas": sum(bool(x and x["mismas_entradas"]) for x in ww),
            "max_diferencia_energia_kcal_mol": h5._max(x and x["diferencia_energia_kcal_mol"] for x in ww),
            "max_diferencia_fuerza_kcal_mol_A": h5._max(x and x["diferencia_fuerza_kcal_mol_A"] for x in ww)},
    }
    evaluables = [f for f in ok if not f["geometria_imposible"]]
    w = metricas["windows"]
    metricas["pasa_gate"] = bool(
        not metricas["fallos"] and all(f["resultado"] == "PASA" for f in evaluables)
        and len(pep) == 2 and any(f["extension_maxima_A"] > 25.0 for f in pep)
        and w is not None and w["comparaciones"] == w["esperadas"] == w["mismas_entradas"]
        and w["max_diferencia_energia_kcal_mol"] < h5.TOLERANCIA_ENTRE_MAQUINAS
        and w["max_diferencia_fuerza_kcal_mol_A"] < h5.TOLERANCIA_ENTRE_MAQUINAS)
    destino = Path(args.artefactos)
    destino.mkdir(parents=True, exist_ok=True)
    (destino / "metrics.json").write_text(json.dumps(metricas, ensure_ascii=False, indent=1) + "\n",
                                          encoding="utf-8", newline="\n")
    with open(destino / "per_complex.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for f in filas:
            fh.write(json.dumps(f, ensure_ascii=False) + "\n")
    for k in ("con_azufre", "sin_azufre", "peptidos"):
        print(k, metricas[k])
    print("windows", metricas["windows"])
    for f in pep:
        print(f"  {f['caso']}: extensión {f['extension_maxima_A']} Å, S {f['n_azufre']}, sin parche residuo "
              f"{f['openmm_8.5.2']['residuo_kcal_mol']:.3e}, con parche {f['con_ramas_de_amber']['residuo_kcal_mol']:.3e}")
    print(f"gate: {'PASA' if metricas['pasa_gate'] else 'NO PASA'}")
    return 0


def main() -> int:
    for flujo in (sys.stdout, sys.stderr):
        if hasattr(flujo, "reconfigure"):
            flujo.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="etapa", required=True)
    p = sub.add_parser("peptidos")
    p.add_argument("--trabajo", type=Path, required=True)
    p.set_defaults(func=peptidos)
    m = sub.add_parser("medir")
    m.add_argument("--trabajo", type=Path, nargs="+", required=True)
    m.add_argument("--salida", type=Path, required=True)
    m.add_argument("--sin-sander", action="store_true")
    m.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    m.set_defaults(func=medir)
    c = sub.add_parser("comparar")
    c.add_argument("--linux", type=Path, required=True)
    c.add_argument("--windows", type=Path)
    c.add_argument("--artefactos", type=Path, required=True)
    c.set_defaults(func=comparar)
    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
