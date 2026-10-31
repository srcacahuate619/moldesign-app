r"""SUP-05-CORTES-DEL-SITIO: ¿cuánto cambia el estado de Preparación al mover sus cortes de 8 Å y 6 Å? (2026-10-25).

Reproduce, con las funciones del producto sin modificarlas, lo que `prepare_target` hace antes de Meeko en las 381 entradas
del catálogo, y mide desde el ligando del cristal la distancia de cada hueco del esqueleto, cadena lateral truncada y especie
retirada. Registro previo: `scripts/artifacts_science/SUP-05-CORTES-DEL-SITIO/entrada/REGISTRO_PREVIO.md`.

    python-embed\python.exe -X utf8 scripts\sup05_cortes\medir.py medir     # escribe _work/distancias.jsonl
    python-embed\python.exe -X utf8 scripts\sup05_cortes\medir.py analizar  # metrics.json, per_complex.jsonl
"""
from __future__ import annotations

import argparse
import gzip
import json
import math
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
EXP = RAIZ / "scripts" / "artifacts_science" / "SUP-05-CORTES-DEL-SITIO"
TRABAJO = EXP / "_work"
ABS_TR = RAIZ / "scripts" / "artifacts_science" / "ABS-TR-01-VALIDEZ-R1" / "per_system.jsonl"
CORTES_HUECO = (6.0, 7.0, 8.0, 9.0, 10.0)
CORTES_ESPECIE = (5.0, 6.0, 7.0, 8.0)
FILO = 0.05
MIN_MEDIBLES = 300

os.environ.setdefault("MOLDESIGN_DATA_DIR", tempfile.mkdtemp(prefix="sup05-"))
sys.path.insert(0, str(RAIZ / "backend"))
from services.chemistry.ensamblaje_biologico import generar_unidad_biologica  # noqa: E402
from services.docking import preparer as P  # noqa: E402
from services.dossier import contexto_estructural as C  # noqa: E402


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _min(a, b) -> float | None:
    return round(min(math.dist(p, q) for p in a for q in b), 2) if a and b else None


def medir_entrada(e: dict) -> dict:
    pdb = e["pdb_id"].upper()
    fila: dict = {"pdb": pdb}
    ruta = RAIZ / "data" / "targets" / f"{pdb}.pdb.gz"
    if not ruta.exists():
        return {**fila, "fuera": "SIN_DEPOSITO"}
    crudo = gzip.decompress(ruta.read_bytes()).decode("utf-8", errors="replace")
    centro = tuple(float(e[f"grid_center_{c}"]) for c in "xyz")
    lado = tuple(float(e[f"grid_size_{c}"]) for c in "xyz")
    del_sitio = sorted({c.strip() for c in (e.get("site_chains") or []) if c and c.strip()})
    cadenas = set(del_sitio) if len(del_sitio) > 1 else {str(e["chain"]).strip()}
    ensamblaje = generar_unidad_biologica(crudo, pdb_id=pdb).pdb
    filtrado = P._filter_pdb_content(ensamblaje, cadenas, keep_hetatm=True,
                                     cofactors_whitelist=list(e.get("cofactors_whitelist") or []),
                                     site_ligand=e.get("site_ligand"))
    filtrado, truncadas = P.truncar_cadenas_laterales_incompletas(filtrado, centro, lado)
    filtrado, _ = P.retirar_hidrogenos_depositados_contradictorios(filtrado)
    huecos = P.huecos_del_esqueleto(filtrado, crudo, centro, lado)

    por_residuo: dict[tuple[str, str, str, str], list] = {}
    for a in C._atomos(ensamblaje):
        por_residuo.setdefault(a.clave_con_nombre, []).append(a)
    ligando = str(e.get("site_ligand") or "").upper()
    copias = [v for k, v in por_residuo.items() if v[0].registro == "HETATM" and k[3] == ligando] if ligando else []
    if not copias:
        return {**fila, "fuera": "SIN_LIGANDO_DEL_CRISTAL", "huecos": len(huecos)}
    cristal = min(copias, key=lambda v: min(math.dist(a.xyz, centro) for a in v))
    ref = [a.xyz for a in cristal]
    donadores = [a for a in cristal if (a.elemento or a.nombre)[:1] in ("N", "O", "S")]

    fila["huecos"] = []
    for h in huecos:
        atomos = []
        for extremo in (str(h.get("after")), str(h.get("before"))):
            numero, insercion = C._numero(extremo)
            atomos += por_residuo.get((str(h.get("chain")), numero, insercion, extremo.split()[0]), [])
        fila["huecos"].append({"chain": h.get("chain"), "after": h.get("after"), "before": h.get("before"),
                               "d": _min([a.xyz for a in atomos], ref), "site_critical": bool(h.get("site_critical"))})
    fila["truncadas"] = []
    for t in truncadas:
        clave = (str(t.get("chain")), str(t.get("residue_number")), str(t.get("insertion_code") or ""), str(t.get("name")))
        fila["truncadas"].append({"residuo": ":".join(clave), "d": _min([a.xyz for a in por_residuo.get(clave, [])], ref)})
    fila["especies"] = []
    for clave, atomos in por_residuo.items():
        if atomos[0].registro != "HETATM" or atomos is cristal or clave[3] in P.WATER_RESIDUES:
            continue
        if clave[0] in cadenas and {"N", "CA", "C"} <= {a.nombre for a in atomos}:
            continue  # residuo modificado de la cadena (SEP, MSE…): es proteína
        metal = any((a.elemento or (a.nombre.upper() if a.nombre == a.residuo else "")) in C.METALES_PDB for a in atomos)
        clase = "metal" if metal else ("copia_del_ligando" if clave[3] == ligando else "organica")
        fila["especies"].append({"residuo": ":".join(clave), "clase": clase, "d": _min([a.xyz for a in atomos], ref),
                                 "coordinado": bool(metal and C._coordinacion(atomos, donadores))})
    return fila


def cmd_medir(_a) -> int:
    TRABAJO.mkdir(parents=True, exist_ok=True)
    salida = TRABAJO / "distancias.jsonl"
    if salida.exists():
        raise SystemExit(f"{salida} ya existe: no se sobrescribe")
    catalogo = json.loads((RAIZ / "curated_targets.json").read_text(encoding="utf-8"))
    with salida.open("w", encoding="utf-8", newline="\n") as fh:
        for i, e in enumerate(catalogo, 1):
            try:
                fila = medir_entrada(e)
            except Exception as exc:  # noqa: BLE001 - se registra como fuera del denominador
                fila = {"pdb": e["pdb_id"].upper(), "fuera": f"ERROR {type(exc).__name__}: {str(exc)[:300]}"}
            fh.write(json.dumps(fila, ensure_ascii=False) + "\n")
            if i % 25 == 0:
                print(i, flush=True)
    print(f"{salida} ({len(catalogo)} entradas, {_ahora()})")
    return 0


def _con(lista: list[dict], t: float, filtro=lambda x: True) -> bool:
    return any(x["d"] is not None and x["d"] <= t and filtro(x) for x in lista)


def cmd_analizar(_a) -> int:
    filas = [json.loads(l) for l in (TRABAJO / "distancias.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    medibles = [f for f in filas if "fuera" not in f]
    fuera: dict[str, int] = {}
    for f in filas:
        if "fuera" in f:
            k = f["fuera"].split(":")[0]
            fuera[k] = fuera.get(k, 0) + 1
    n = len(medibles)
    sin_coord = lambda x: not x.get("coordinado")  # noqa: E731
    tabla_huecos = {f"{t:g}": {"abstienen_por_hueco": sum(_con(f["huecos"], t) for f in medibles),
                               "con_truncada": sum(_con(f["truncadas"], t) for f in medibles)} for t in CORTES_HUECO}
    tabla_especies = {}
    for t in CORTES_ESPECIE:
        tabla_especies[f"{t:g}"] = {"alguna": sum(_con(f["especies"], t, sin_coord) for f in medibles),
                                    **{c: sum(_con(f["especies"], t, lambda x, c=c: x["clase"] == c and sin_coord(x))
                                              for f in medibles) for c in ("metal", "copia_del_ligando", "organica")}}
    cambia_hueco = sorted(f["pdb"] for f in medibles if _con(f["huecos"], 7.0) != _con(f["huecos"], 9.0))
    cambia_especie = sorted(f["pdb"] for f in medibles
                            if _con(f["especies"], 5.0, sin_coord) != _con(f["especies"], 7.0, sin_coord))
    coordinados = sorted(f["pdb"] for f in medibles if any(x.get("coordinado") for x in f["especies"]))
    mas_cercano = sorted(min((h["d"] for h in f["huecos"] if h["d"] is not None), default=None) or 99.0 for f in medibles)
    histograma = {f"{a}-{a + 2}": sum(a <= d < a + 2 for d in mas_cercano) for a in range(0, 20, 2)}
    histograma[">=20 o ninguno"] = sum(d >= 20 for d in mas_cercano)

    abs_tr = {}
    if ABS_TR.exists():
        panel = {json.loads(l)["pdb"]: json.loads(l) for l in ABS_TR.read_text(encoding="utf-8").splitlines() if l.strip()}
        por_pdb = {f["pdb"]: f for f in medibles}
        for pdb, p in sorted(panel.items()):
            f = por_pdb.get(pdb)
            if f is None:
                abs_tr[pdb] = {"medido": False}
                continue
            abs_tr[pdb] = {"panel": p.get("ref_mayoria_5"),
                           "abstiene_por_hueco": {f"{t:g}": _con(f["huecos"], t) for t in CORTES_HUECO},
                           "hueco_mas_cercano_A": min((h["d"] for h in f["huecos"] if h["d"] is not None), default=None)}
        falsos = {f"{t:g}": sorted(k for k, v in abs_tr.items() if v.get("medido", True) and v.get("panel") == "NO_DETENER"
                                   and v["abstiene_por_hueco"][f"{t:g}"]) for t in CORTES_HUECO}
    else:
        falsos = None

    p1, p2 = len(cambia_hueco), len(cambia_especie)
    if n < MIN_MEDIBLES:
        decision, razon = "INCONCLUSIVE", f"{n} entradas medibles (< {MIN_MEDIBLES})"
    elif p1 <= FILO * n and p2 <= FILO * n:
        decision = "GO"
        razon = (f"Entre 7 y 9 Å cambia el estado por huecos en {p1} de {n} entradas ({100 * p1 / n:.1f} %) y entre 5 y 7 Å "
                 f"el de especies en {p2} ({100 * p2 / n:.1f} %): ninguno pasa del 5 %")
    else:
        decision = "NO_GO"
        razon = (f"Entre 7 y 9 Å cambia el estado por huecos en {p1} de {n} entradas ({100 * p1 / n:.1f} %) y entre 5 y 7 Å "
                 f"el de especies en {p2} ({100 * p2 / n:.1f} %): {'el corte de huecos' if p1 > FILO * n else ''}"
                 f"{' y ' if p1 > FILO * n and p2 > FILO * n else ''}{'el de especies' if p2 > FILO * n else ''} es un filo")
    metricas = {"experimento": EXP.name, "analizado_en": _ahora(), "decision": decision, "razon": razon,
                "entradas": len(filas), "medibles": n, "fuera_del_denominador": fuera,
                "primaria_1_cambia_por_hueco_7_a_9": {"n": p1, "fraccion": round(p1 / n, 4) if n else None, "pdb": cambia_hueco},
                "primaria_2_cambia_por_especie_5_a_7": {"n": p2, "fraccion": round(p2 / n, 4) if n else None, "pdb": cambia_especie},
                "por_corte_de_hueco": tabla_huecos, "por_corte_de_especie": tabla_especies,
                "metal_coordinado_por_el_ligando": {"n": len(coordinados), "pdb": coordinados},
                "hueco_mas_cercano_histograma_A": histograma,
                "abs_tr_01_validez_r1": {"sistemas": abs_tr, "falsos_bloqueos_por_hueco": falsos},
                "4JVB_hueco_mas_cercano_A": next((min((h["d"] for h in f["huecos"] if h["d"] is not None), default=None)
                                                  for f in medibles if f["pdb"] == "4JVB"), None)}
    (EXP / "metrics.json").write_text(json.dumps(metricas, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (EXP / "per_complex.jsonl").open("w", encoding="utf-8", newline="\n") as fh:
        for f in filas:
            fh.write(json.dumps(f, ensure_ascii=False) + "\n")
    with (EXP / "failures.jsonl").open("w", encoding="utf-8", newline="\n") as fh:
        for f in filas:
            if "fuera" in f:
                fh.write(json.dumps({"pdb": f["pdb"], "fuera": f["fuera"]}, ensure_ascii=False) + "\n")
    print(json.dumps({k: metricas[k] for k in ("decision", "razon", "medibles", "fuera_del_denominador")},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("medir").set_defaults(func=cmd_medir)
    sub.add_parser("analizar").set_defaults(func=cmd_analizar)
    a = ap.parse_args()
    raise SystemExit(a.func(a))
