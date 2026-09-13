#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""analisis_rec12_cofactores.py — REC-12: los cofactores que nadie ha inventariado.

Sin computo de docking. Parsea estructuras.

El hueco
--------
`REC-08-EXT` inventario dos clases de HETATM del sitio: **metales** (42 de 42 conservados) y
**aguas** (1788 de 1788). Queda una tercera clase que nadie ha contado nunca: el resto de
HETATM que no son ni agua ni metal —cofactores como NAD, FAD o hemo, y tambien crioprotectores
y aditivos de cristalizacion como glicerol, sulfato o etilenglicol—.

La distincion importa y no es cosmetica:

  * un **cofactor** que forma parte del sitio y desaparece al preparar deja un bolsillo que no
    existe, igual que perder un metal;
  * un **aditivo de cristalizacion** que se conserva ocupa espacio que in vivo esta libre, igual
    que un agua que sobra.

Los dos son defectos y son opuestos, asi que este inventario no puede leerse en una sola
direccion.

Por que ahora
-------------
`REC-09` dejo una pregunta concreta abierta: **`1d7i` y `1ew9` puntuan absurdamente mal
—por encima de -3.0 kcal/mol— con CERO aguas bloqueantes**. Su causa no son las aguas. Los
cofactores no metalicos son la siguiente hipotesis, y hasta hoy no habia con que comprobarla.

Y en el marco mas amplio: de los ejes de especificacion que el programa ha medido —huecos de
cadena (`FEP-02-EXT`), metales y aguas (`REC-08-EXT`), tautomeros (`FEP-01-EXT`), provenance
(`FND-06`)— este es el unico **prospectivo** que sigue sin medir. Prospectivo significa
computable del input, antes de dockear y sin conocer la respuesta, que es lo que un criterio
de adecuacion necesita para servir de algo.

Que se mide
-----------
Metodo identico al de `REC-08-EXT`, tercera entidad: sitio a **8 A** de un atomo pesado del
ligando cristalografico (el radio que `FEP-02` uso), emparejamiento entre original y preparado
**por coordenada** con tolerancia de **0.5 A**, porque la preparacion renumera.

Para cada complejo:

  1. HETATM del sitio en el ORIGINAL que no son agua, ni metal, ni el propio ligando;
  2. cuantos sobreviven en `rec.pdbqt`;
  3. la especie de cada uno, para poder separar cofactor de aditivo a mano despues.

Limites declarados
------------------
1. **Sin gates de decision.** Es un inventario. No clasifica automaticamente cofactor
   funcional frente a aditivo de cristalizacion: esa distincion es quimica y por complejo, y
   hacerla con una lista de codigos PDB seria inventarla. Lo que este artefacto entrega es la
   lista para que alguien la haga.
2. **No decide sobre `1d7i` ni `1ew9`.** Si aparecen cofactores en su sitio, queda una
   hipotesis mejor que la actual; si no aparecen, quedan descartadas dos causas y no hay
   tercera candidata medida.
3. El emparejamiento por coordenada hace que un atomo desplazado mas de 0.5 A por la
   preparacion cuente como perdido: **los recuentos de perdida son cota superior**, la misma
   limitacion que `REC-08-EXT` declaro.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent

R_SITIO = 8.0
TOL = 0.5
METALES = {"ZN", "MG", "MN", "FE", "CA", "CU", "NI", "CO", "CD", "HG",
           "NA", "K", "MO", "W", "V", "PT", "AU", "AG", "PB", "SR", "BA"}
AGUAS = {"HOH", "WAT", "DOD", "H2O"}


def _hetatm(p: Path) -> List[Tuple[str, str, float, float, float]]:
    out = []
    for l in p.read_text(encoding="utf-8", errors="replace").splitlines():
        if l.startswith("HETATM") and len(l) >= 54:
            try:
                el = (l[76:78].strip().upper() if len(l) >= 78 else "")
                out.append((l[17:20].strip().upper(), el,
                            float(l[30:38]), float(l[38:46]), float(l[46:54])))
            except ValueError:
                continue
    return out


def _todos(p: Path) -> List[Tuple[float, float, float]]:
    out = []
    for l in p.read_text(encoding="utf-8", errors="replace").splitlines():
        if l.startswith(("ATOM", "HETATM")) and len(l) >= 54:
            try:
                out.append((float(l[30:38]), float(l[38:46]), float(l[46:54])))
            except ValueError:
                continue
    return out


def _cerca(x, y, z, pts, r) -> bool:
    r2 = r * r
    for px, py, pz in pts:
        if (x - px) ** 2 + (y - py) ** 2 + (z - pz) ** 2 <= r2:
            return True
    return False


def main() -> int:
    import molflex as mf

    ap = argparse.ArgumentParser(description="REC-12: inventario de cofactores no metalicos del sitio")
    ap.add_argument("--workspace", default="/workspace")
    args = ap.parse_args()
    ws = Path(args.workspace)
    art = ws / "scripts" / "artifacts_science"
    out_dir = art / "REC-12"
    out_dir.mkdir(parents=True, exist_ok=True)

    m13 = {}
    for l in (art / "MF-13" / "per_complex.jsonl").read_text(encoding="utf-8").splitlines():
        if l.strip():
            r = json.loads(l)
            m13[r["pid"]] = r.get("estrato", "RESTO")

    r09 = {}
    p09 = art / "REC-09" / "per_complex.jsonl"
    if p09.exists():
        for l in p09.read_text(encoding="utf-8").splitlines():
            if l.strip():
                r = json.loads(l)
                r09[r["pid"]] = r

    filas: List[Dict[str, Any]] = []
    especies = Counter()
    for pid, estrato in sorted(m13.items()):
        f: Dict[str, Any] = {"pid": pid, "estrato": estrato}
        orig = ws / "data" / "pdbbind" / pid / f"{pid}_protein.pdb"
        prep = ws / "data" / "molflex_train_v2" / pid / pid / "rec.pdbqt"
        sdf = ws / "data" / "pdbbind" / pid / f"{pid}_ligand.sdf"
        if not orig.exists() or not prep.exists() or not sdf.exists():
            f["error"] = "SIN_ESTRUCTURA"
            filas.append(f)
            continue
        crystal = mf.leer_ligando(sdf)
        if crystal is None:
            f["error"] = "SDF_ILEGIBLE"
            filas.append(f)
            continue
        conf = crystal.GetConformer()
        lig_pts = [(conf.GetAtomPosition(a.GetIdx()).x, conf.GetAtomPosition(a.GetIdx()).y,
                    conf.GetAtomPosition(a.GetIdx()).z)
                   for a in crystal.GetAtoms() if a.GetAtomicNum() > 1]

        prep_pts = _todos(prep)
        cof, vivos = [], 0
        # G1: la fuente, ¿contiene siquiera HETATM que no sean agua ni metal, en cualquier
        # sitio de la estructura? Si no, no hay nada que inventariar y el cero de abajo
        # seria del ARCHIVO, no de las estructuras.
        f["hetatm_no_agua_no_metal_en_toda_la_estructura"] = sum(
            1 for resn, el, _x, _y, _z in _hetatm(orig)
            if resn not in AGUAS and el not in METALES and resn not in METALES)
        for resn, el, x, y, z in _hetatm(orig):
            if resn in AGUAS or el in METALES or resn in METALES:
                continue
            if not _cerca(x, y, z, lig_pts, R_SITIO):
                continue
            # el propio ligando aparece como HETATM: se descarta por solapamiento exacto
            if _cerca(x, y, z, lig_pts, TOL):
                continue
            cof.append(resn)
            if _cerca(x, y, z, prep_pts, TOL):
                vivos += 1
        for r in set(cof):
            especies[r] += 1
        f["cofactores_atomos_sitio"] = len(cof)
        f["cofactores_conservados"] = vivos
        f["cofactores_perdidos"] = len(cof) - vivos
        f["especies"] = sorted(set(cof))
        f["tiene_cofactor"] = bool(cof)
        if pid in r09:
            f["score_cristal"] = r09[pid].get("score_con_aguas")
            f["absurdo"] = r09[pid].get("absurdo")
            f["aguas_bloqueantes"] = r09[pid].get("n_aguas_bloqueantes")
        filas.append(f)

    ok = [f for f in filas if "cofactores_atomos_sitio" in f]
    con = [f for f in ok if f["tiene_cofactor"]]
    absurdos = [f for f in ok if f.get("absurdo")]
    sin_agua_bloq = [f for f in absurdos if (f.get("aguas_bloqueantes") or 0) == 0]

    con_hetatm = sum(1 for f in ok if f.get("hetatm_no_agua_no_metal_en_toda_la_estructura", 0) > 0)
    g1 = round(con_hetatm / len(ok), 4) if ok else 0.0

    out = {
        "analisis_id": "REC-12",
        "tipo": "inventario con gate de validez de la fuente, sin computo de docking",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "metodo": "identico a REC-08-EXT, tercera entidad: HETATM del sitio que no son agua ni metal",
        "umbrales": {"sitio_A": R_SITIO, "emparejado_por_coordenada_A": TOL},
        "n_complejos": len(filas), "n_ok": len(ok),
        "G1_VALIDEZ_DE_LA_FUENTE": {
            "criterio": "la fuente debe contener HETATM que no sean agua ni metal en algun sitio de la estructura; si no, un inventario de cero seria del ARCHIVO y no de las estructuras",
            "complejos_con_alguno": con_hetatm, "de": len(ok), "fraccion": g1,
            "minimo_para_leer_el_inventario": 0.05,
            "pasa": bool(g1 >= 0.05),
            "nota": "PDBBind entrega en <pid>_protein.pdb una estructura LIMPIADA: conserva aguas y metales y elimina el resto de heteroatomos. Con esta fuente el inventario NO ES MEDIBLE.",
        },
        "COFACTORES": {
            "complejos_con_cofactor_en_sitio": len(con),
            "atomos_totales": sum(f["cofactores_atomos_sitio"] for f in con),
            "conservados": sum(f["cofactores_conservados"] for f in con),
            "PERDIDOS": sum(f["cofactores_perdidos"] for f in con),
            "complejos_que_pierden_alguno": sorted(f["pid"] for f in con
                                                   if f["cofactores_perdidos"] > 0),
            "especies_por_n_complejos": dict(especies.most_common()),
        },
        "cruce_con_REC09": {
            "pregunta": "los cristales que puntuan absurdo sin aguas bloqueantes, tienen cofactor en el sitio?",
            "absurdos": sorted(f["pid"] for f in absurdos),
            "absurdos_sin_agua_bloqueante": sorted(f["pid"] for f in sin_agua_bloq),
            "de_esos_con_cofactor": sorted(f["pid"] for f in sin_agua_bloq if f["tiene_cofactor"]),
            "frac_con_cofactor_entre_absurdos": (
                round(sum(1 for f in absurdos if f["tiene_cofactor"]) / len(absurdos), 4)
                if absurdos else None),
            "frac_con_cofactor_entre_no_absurdos": (
                round(sum(1 for f in ok if not f.get("absurdo") and f["tiene_cofactor"])
                      / max(1, sum(1 for f in ok if not f.get("absurdo"))), 4)),
        },
        "limites_declarados": [
            "sin gates: es un inventario y no clasifica cofactor funcional frente a aditivo de cristalizacion",
            "no decide sobre 1d7i ni 1ew9: genera o descarta una hipotesis, no la establece",
            "emparejamiento por coordenada a 0.5 A: los recuentos de perdida son cota superior",
        ],
        "per_complex": filas,
    }
    (out_dir / "metrics.json").write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                          encoding="utf-8", newline="\n")
    with open(out_dir / "per_complex.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for f in filas:
            fh.write(json.dumps(f, ensure_ascii=False) + "\n")

    C = out["COFACTORES"]
    X = out["cruce_con_REC09"]
    print(f"[REC-12] {len(ok)} complejos | con cofactor en sitio: {C['complejos_con_cofactor_en_sitio']}")
    print(f"  atomos {C['atomos_totales']}, conservados {C['conservados']}, PERDIDOS {C['PERDIDOS']}")
    print(f"  especies: {list(C['especies_por_n_complejos'].items())[:12]}")
    print(f"  absurdos sin agua bloqueante: {X['absurdos_sin_agua_bloqueante']} "
          f"-> con cofactor: {X['de_esos_con_cofactor']}")
    print(f"  frac con cofactor: absurdos {X['frac_con_cofactor_entre_absurdos']} vs "
          f"no absurdos {X['frac_con_cofactor_entre_no_absurdos']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
