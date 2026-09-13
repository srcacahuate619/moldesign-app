#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""analisis_mf33dosis_cuando_hace_falta_ensemble.py — MF-33-DOSIS: ¿se puede saber ANTES?

Analisis **EXPLORATORIO**, sin gates de decision. Genera hipotesis; no las establece.

La pregunta
-----------
`MF-33-A3` establecio que la ventaja del ensemble flexible es **diversidad conformacional**
y no conteo de poses, reinicios ni CPU. Eso responde *que* aspecto de MolFlex sirve. La
pregunta siguiente, que vale mas para el producto, es **cuando**:

  > ¿existe una variable, computable **antes de dockear**, que prediga en que complejos vale
  > la pena pagar el coste del ensemble?

Si la hay, MolFlex deja de ser un generador universal y pasa a ser una **politica adaptativa
de muestreo**: ligando sencillo -> docking barato; ligando conformacionalmente dificil ->
ensemble flexible. Los CONTROL ya estan practicamente resueltos por cualquier brazo (14-15 de
15), asi que gastar ensemble en ellos es coste sin retorno.

La hipotesis general que se pone a prueba
------------------------------------------
    En ligandos conformacionalmente dificiles, aumentar la profundidad de busqueda desde un
    UNICO estado tiene rendimientos decrecientes, porque conformaciones iniciales distintas
    acceden a cuencas de pose distintas.

Si es cierta, el beneficio B - A3 debe **crecer** con alguna medida de dificultad
conformacional. Si no correlaciona con ninguna, la ventaja del ensemble existe pero no es
predecible por estas variables, y la politica adaptativa no se puede construir sobre ellas.

Respuestas y predictores
------------------------
**Respuesta continua** -la de mas potencia-: `beneficio = rmsd_A3 - rmsd_B`. Positiva cuando
el ensemble encuentra mejor pose. Se prefiere a la binaria porque los discordantes son solo 7
y una variable continua usa los 33.

**Respuesta binaria** -la del gate de A3-: `g_B`, el complejo donde B alcanza <=2 A y A3 no.
Se reporta por completitud, con la potencia que da n=7.

**Seis predictores**, todos computables antes de dockear salvo el ultimo:

  1. `torsdof`      del `conf0.flex.pdbqt`, que es la dimension que Vina busca
  2. `rot_bonds`    conteo de RDKit, que difiere del anterior y se reporta aparte
  3. `n_conformeros` K del ensemble; **igualado entre brazos**, asi que no es circular
  4. `diversidad`   RMSD medio por pares entre los conformeros del ensemble, alineados
  5. `n_heavy`      tamano molecular
  6. `frac_vuelve`  rugosidad de la cuenca de `MF-14` a 0.5 A, via `MF-33-CRUCES`.
     **Este NO es prospectivo**: se mide perturbando la pose nativa, que en produccion no
     existe. Se incluye porque es mecanicisticamente informativo, y se marca como tal.

Metodo, y por que asi
---------------------
Spearman de rangos: no asume linealidad y resiste los valores extremos, que con n=33 pesan.
Estrato primario **COLOCACION (n=33)**, que es donde hay variacion; los 48 completos como
secundario, sabiendo que los 15 de CONTROL comprimen el rango.

**Correccion por comparaciones multiples con Benjamini-Hochberg** (`estadistica_fnd04`), q =
0.05, sobre los 6 predictores. Es obligatorio y no cosmetico: con 6 contrastes y n=33, la
probabilidad de que **alguno** salga con p < 0.05 bajo la hipotesis nula es del **26%**. Sin
FDR, este analisis encontraria un predictor casi seguro y no significaria nada.

LO QUE ESTE ANALISIS NO PUEDE HACER, y quien si
-----------------------------------------------
Con n=33, seis predictores y una busqueda posterior a ver el resultado de `MF-33-A3`, esto es
**generacion de hipotesis**. Ni con FDR pasa a ser confirmatorio: el conjunto ya se ha mirado.

La validacion honesta existe y **ya esta corriendo**: `MF-33-EXT` esta midiendo el mismo brazo
B sobre los **116** de train. Sesenta y ocho de esos complejos **no estan** en la cohorte de
48. Eso da un conjunto de validacion fuera de muestra sin coste adicional.

El protocolo correcto, y queda escrito aqui antes de mirar nada:

  1. este analisis produce un **ranking** de predictores sobre los 48;
  2. el primero se **prerregistra** con su direccion y su umbral **antes** de que `MF-33-EXT`
     cierre;
  3. se contrasta en los 68 complejos nuevos.

Un predictor que sobreviva a ese paso es una afirmacion prospectiva. Uno que solo aparezca
aqui es una correlacion en 33 puntos.

Limites declarados
------------------
1. **Exploratorio y sin gates.** No autoriza cambiar ninguna politica de muestreo.
2. La diversidad conformacional se calcula con correspondencia atomica 1:1 y **sin tratar
   simetria molecular**: en ligandos simetricos la RMSD por pares queda inflada. Es una cota
   superior del desorden real.
3. `frac_vuelve` **no es prospectivo** y se marca en la salida. Si resultara el mejor
   predictor, no serviria para la politica adaptativa sin un sustituto computable a ciegas.
4. No dice **por que** la diversidad ayuda. `MF-33-A3` tampoco.
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
import sys
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

Q_FDR = 0.05


def _jsonl(p: Path) -> List[Dict[str, Any]]:
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def _coords_pdbqt(texto: str) -> Dict[int, Tuple[float, float, float]]:
    """serial -> (x,y,z) de un PDBQT de ligando."""
    out = {}
    for l in texto.splitlines():
        if l.startswith(("ATOM", "HETATM")) and len(l) >= 54:
            try:
                out[int(l[6:11])] = (float(l[30:38]), float(l[38:46]), float(l[46:54]))
            except ValueError:
                continue
    return out


def _torsdof(texto: str) -> Optional[int]:
    for l in texto.splitlines():
        if l.startswith("TORSDOF"):
            try:
                return int(l.split()[1])
            except (IndexError, ValueError):
                return None
    return None


def _rmsd_kabsch(P, Q) -> float:
    """RMSD tras alineamiento optimo. Correspondencia 1:1, sin simetria (ver limites)."""
    import numpy as np
    P = np.asarray(P, dtype=float); Q = np.asarray(Q, dtype=float)
    P = P - P.mean(axis=0); Q = Q - Q.mean(axis=0)
    V, S, W = np.linalg.svd(P.T @ Q)
    d = np.sign(np.linalg.det(V @ W))
    D = np.diag([1.0, 1.0, d])
    P_rot = P @ (V @ D @ W)
    return float(np.sqrt(((P_rot - Q) ** 2).sum(axis=1).mean()))


def diversidad_conformeros(w: Path, pesados_serials: set, max_confs: int = 30) -> Optional[float]:
    """RMSD medio por pares entre los conformeros del ensemble, sobre atomos pesados."""
    import re
    archivos = sorted([f for f in w.glob("conf*.flex.pdbqt")
                       if re.fullmatch(r"conf\d+\.flex\.pdbqt", f.name)],
                      key=lambda f: int(re.search(r"conf(\d+)", f.name).group(1)))[:max_confs]
    if len(archivos) < 2:
        return None
    juegos = []
    for f in archivos:
        c = _coords_pdbqt(f.read_text(encoding="utf-8", errors="replace"))
        sel = sorted(s for s in c if s in pesados_serials)
        if sel:
            juegos.append([c[s] for s in sel])
    juegos = [j for j in juegos if len(j) == len(juegos[0])] if juegos else []
    if len(juegos) < 2:
        return None
    vals = []
    for i in range(len(juegos)):
        for j in range(i + 1, len(juegos)):
            vals.append(_rmsd_kabsch(juegos[i], juegos[j]))
    return round(mean(vals), 4) if vals else None


def main() -> int:
    from scipy.stats import spearmanr
    from estadistica_fnd04 import benjamini_hochberg
    import molflex as mf

    ap = argparse.ArgumentParser(description="MF-33-DOSIS: cuando hace falta el ensemble")
    ap.add_argument("--workspace", default=str(PROJECT_ROOT))
    args = ap.parse_args()
    ws = Path(args.workspace)
    art = ws / "scripts" / "artifacts_science"
    out_dir = art / "MF-33-DOSIS"
    out_dir.mkdir(parents=True, exist_ok=True)

    a3 = {r["pid"]: r for r in _jsonl(art / "MF-33-A3" / "per_complex.jsonl")}
    cruces = {r["pid"]: r for r in _jsonl(art / "MF-33-CRUCES" / "per_complex.jsonl")}

    filas: List[Dict[str, Any]] = []
    for pid, r in sorted(a3.items()):
        w = ws / "data" / "molflex_train_v2" / pid / pid
        f: Dict[str, Any] = {"pid": pid, "estrato": r["estrato"]}

        rb = r.get("B", {}).get("rmsd_min")
        ra = r.get("rmsd_min")
        f["rmsd_B"], f["rmsd_A3"] = rb, ra
        f["beneficio"] = round(ra - rb, 4) if (ra is not None and rb is not None) else None
        f["gB"] = bool(r.get("B", {}).get("alcanza") and not r.get("alcanza"))
        f["n_conformeros"] = r.get("k_corridas")

        lig = w / "conf0.flex.pdbqt"
        pesados_serials: set = set()
        if lig.exists():
            txt = lig.read_text(encoding="utf-8", errors="replace")
            f["torsdof"] = _torsdof(txt)
            for l in txt.splitlines():
                if l.startswith(("ATOM", "HETATM")) and len(l) >= 78:
                    if l[77:79].strip().upper() not in ("H", "HD", "HS"):
                        try:
                            pesados_serials.add(int(l[6:11]))
                        except ValueError:
                            pass
        crystal = mf.leer_ligando(ws / "data" / "pdbbind" / pid / f"{pid}_ligand.sdf")
        if crystal is not None:
            from rdkit.Chem import Descriptors, rdMolDescriptors
            f["rot_bonds"] = rdMolDescriptors.CalcNumRotatableBonds(crystal)
            f["n_heavy"] = crystal.GetNumHeavyAtoms()
            f["mw"] = round(Descriptors.MolWt(crystal), 2)
        f["diversidad"] = diversidad_conformeros(w, pesados_serials) if pesados_serials else None
        f["frac_vuelve"] = (cruces.get(pid) or {}).get("frac_vuelve_0.5")
        filas.append(f)

    PREDICTORES = [
        ("torsdof", True), ("rot_bonds", True), ("n_conformeros", True),
        ("diversidad", True), ("n_heavy", True), ("frac_vuelve", False),
    ]

    def correlar(sub: List[Dict[str, Any]], respuesta: str) -> Dict[str, Any]:
        res: Dict[str, Any] = {}
        pvals, claves = [], []
        for nombre, prospectivo in PREDICTORES:
            pares = [(f[nombre], f[respuesta]) for f in sub
                     if f.get(nombre) is not None and f.get(respuesta) is not None]
            if len(pares) < 8:
                res[nombre] = {"n": len(pares), "rho": None, "p": None,
                               "prospectivo": prospectivo, "motivo": "n_insuficiente"}
                continue
            xs = [p[0] for p in pares]
            ys = [float(p[1]) for p in pares]
            if len(set(xs)) < 3:
                res[nombre] = {"n": len(pares), "rho": None, "p": None,
                               "prospectivo": prospectivo, "motivo": "sin_variacion"}
                continue
            rho, p = spearmanr(xs, ys)
            if math.isnan(rho):
                res[nombre] = {"n": len(pares), "rho": None, "p": None,
                               "prospectivo": prospectivo, "motivo": "rho_nan"}
                continue
            res[nombre] = {"n": len(pares), "rho": round(float(rho), 4),
                           "p": round(float(p), 6), "prospectivo": prospectivo}
            pvals.append(float(p)); claves.append(nombre)
        if pvals:
            sig = benjamini_hochberg(pvals, q=Q_FDR)
            for k, s in zip(claves, sig):
                res[k]["significativo_tras_FDR"] = bool(s)
        return res

    col = [f for f in filas if f["estrato"] == "COLOCACION"]
    todos = filas

    def rho_detectable(n: int, alpha: float = 0.05, potencia: float = 0.80) -> Optional[float]:
        """|rho| mas pequeno que un Spearman con n pares puede detectar.

        Via transformacion z de Fisher: |z| = (z_alpha/2 + z_potencia) / sqrt(n - 3), y
        rho = tanh(z). Es la version para correlacion de lo que `efecto_minimo_detectable`
        de FND-04 hace para diferencias pareadas, y existe por la misma razon: RS-14
        descubrio su limite de resolucion DESPUES de ejecutar.
        """
        if n < 5:
            return None
        from estadistica_fnd04 import _ppf
        z = (_ppf(1 - alpha / 2) + _ppf(potencia)) / math.sqrt(n - 3)
        return round(math.tanh(z), 4)

    salida = {
        "analisis_id": "MF-33-DOSIS",
        "tipo": "EXPLORATORIO, generacion de hipotesis, sin gates de decision",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "pregunta": "existe una variable computable antes de dockear que prediga cuando vale la "
                    "pena pagar el coste del ensemble flexible",
        "hipotesis_general": "en ligandos conformacionalmente dificiles, aumentar la profundidad "
                             "de busqueda desde un UNICO estado tiene rendimientos decrecientes, "
                             "porque conformaciones iniciales distintas acceden a cuencas distintas",
        "respuesta_continua": "beneficio = rmsd_A3 - rmsd_B; positiva cuando el ensemble gana",
        "correccion_multiple": f"Benjamini-Hochberg q={Q_FDR} sobre los 6 predictores. "
                               "Con 6 contrastes y n=33, P(alguno con p<0.05 | H0) = 26%.",
        "EFECTO_MINIMO_DETECTABLE": {
            "criterio": "|rho| de Spearman detectable con alpha=0.05 y potencia=0.80, via z de Fisher",
            "COLOCACION_n33": rho_detectable(len(col)),
            "TODOS_n48": rho_detectable(len(todos)),
            "advertencia": "por debajo de ese |rho| este diseno NO PUEDE VER el efecto. Un "
                           "resultado nulo aqui significa 'no detectable con esta cohorte', "
                           "NO 'no existe'. Y tras la correccion FDR sobre 6 predictores el "
                           "umbral efectivo es todavia mas exigente.",
            "leccion_de": "RS-14, que descubrio su limite de resolucion despues de ejecutar"},
        "COLOCACION_n33": {
            "n": len(col),
            "beneficio_continuo": correlar(col, "beneficio"),
            "discordancia_gB": correlar(col, "gB"),
            "n_discordantes_gB": sum(1 for f in col if f["gB"])},
        "TODOS_n48": {
            "n": len(todos),
            "beneficio_continuo": correlar(todos, "beneficio"),
            "nota": "los 15 de CONTROL comprimen el rango: casi todos los brazos los resuelven"},
        "VALIDACION_FUERA_DE_MUESTRA": {
            "estado": "PENDIENTE, y es la parte que convierte esto en una afirmacion",
            "conjunto": "MF-33-EXT esta midiendo el brazo B sobre los 116 de train; 68 no estan "
                        "en la cohorte de 48",
            "protocolo_escrito_antes": [
                "este analisis produce un ranking de predictores sobre los 48",
                "el primero se prerregistra con direccion y umbral ANTES de que MF-33-EXT cierre",
                "se contrasta en los 68 complejos nuevos"],
            "por_que": "con n=33, seis predictores y una busqueda posterior a ver el resultado de "
                       "MF-33-A3, ni con FDR esto pasa a confirmatorio: el conjunto ya se ha mirado"},
        "limites_declarados": [
            "exploratorio y sin gates: no autoriza cambiar ninguna politica de muestreo",
            "la diversidad usa correspondencia 1:1 sin tratar simetria: en ligandos simetricos "
            "queda inflada, es cota superior del desorden real",
            "frac_vuelve NO es prospectivo -se mide perturbando la pose nativa- y va marcado",
            "no dice por que la diversidad ayuda; MF-33-A3 tampoco",
        ],
        "per_complex": filas,
    }
    (out_dir / "metrics.json").write_text(json.dumps(salida, ensure_ascii=False, indent=1),
                                          encoding="utf-8", newline="\n")
    with open(out_dir / "per_complex.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for f in filas:
            fh.write(json.dumps(f, ensure_ascii=False) + "\n")

    mde = salida["EFECTO_MINIMO_DETECTABLE"]
    print(f"[MF-33-DOSIS] COLOCACION n={len(col)}, discordantes gB={salida['COLOCACION_n33']['n_discordantes_gB']}")
    print(f"  MDE: este diseno solo ve |rho| >= {mde['COLOCACION_n33']} (n=33) / "
          f"{mde['TODOS_n48']} (n=48). Debajo de eso, nulo != inexistente.")
    print("  beneficio continuo (rmsd_A3 - rmsd_B), Spearman + FDR:")
    for k, v in sorted(salida["COLOCACION_n33"]["beneficio_continuo"].items(),
                       key=lambda kv: (kv[1].get("p") is None, kv[1].get("p", 1))):
        marca = "" if v.get("prospectivo") else "  [NO prospectivo]"
        if v.get("rho") is None:
            print(f"    {k:16s} n={v['n']:3d}  {v.get('motivo')}{marca}")
        else:
            print(f"    {k:16s} n={v['n']:3d}  rho={v['rho']:+.3f}  p={v['p']:.4f}  "
                  f"FDR={'SI' if v.get('significativo_tras_FDR') else 'no'}{marca}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
