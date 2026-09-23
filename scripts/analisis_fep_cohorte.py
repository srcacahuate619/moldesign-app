#!/usr/bin/env python3
r"""¿Qué cohorte congenérica de PDBBind conviene para el primer paquete FEP-ready?

**Tipo: análisis sobre artefactos ya producidos.** No calcula MCS ni acopla:
cruza FEP-03-PDBBIND (qué parejas son aptas), FEP-01-PDBBIND (tautomería y
estereoquímica por ligando), FEP-02-PDBBIND (preparación del receptor) y las
afinidades del INDEX local.

# Qué se mide por diana

Una lista de parejas aptas no es un mapa FEP: el cálculo relativo necesita que
los ligandos estén **conectados** por perturbaciones pequeñas. Así que por cada
diana con serie se construye el grafo de parejas aptas y se toma su
**componente conexa mayor**. Dentro de ella:

- cuántos ligandos tienen afinidad experimental y en qué rango de pK (sin
  referencia experimental no hay nada contra qué validar un cálculo);
- qué fracción tiene tautómero ambiguo o estereoquímica indefinida (FEP-01);
- qué fracción de receptores es documentable y cuántos tienen metales en el
  sitio (FEP-02).

# Las afinidades: sólo la Fase A, y por qué

El INDEX local es una reconstrucción propia a partir de fuentes públicas, no
el oficial de pdbbind.org.cn. Medido el 2026-09-22 sobre las dianas con más
de un complejo, contando ligandos con el MISMO dato literal que otro de su
diana:

- `INDEX_refined_data.2020.faseA_*` (865): 77 de 770, el 10%. Compatible con
  el mismo ligando cristalizado varias veces.
- `INDEX_refined_data.2020` (1165 = Fase A + selección de BindingDB): 259 de
  1020. Las ~300 entradas de BindingDB aportan 182 de esos duplicados.
- `INDEX_faseb_enriched_full_*.2020` (3815): 1670 de 2520. 184l y 185l
  comparten Ki=1470 nM cuando Fase A les da 19 µM y 290 µM.

Lo añadido desde BindingDB está emparejado por diana, no por ligando: no sirve
como referencia de un cálculo relativo entre ligandos. Se usa sólo Fase A.

Uso:

    python scripts/analisis_fep_cohorte.py            # usa la caché de nombres si existe
    python scripts/analisis_fep_cohorte.py --red      # pide a RCSB los nombres que falten
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median
from typing import Any

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))
try:
    from salida_consola import consola_utf8
except ImportError:  # pragma: no cover
    def consola_utf8() -> None:
        pass
consola_utf8()

ART = RAIZ / "scripts" / "artifacts_science"
F01 = ART / "FEP-01-PDBBIND" / "per_complex.jsonl"
F02 = ART / "FEP-02-PDBBIND" / "per_complex.jsonl"
F03 = ART / "FEP-03-PDBBIND"
PDBBIND = RAIZ / "data" / "pdbbind"
SALIDA = F03 / "cohortes_candidatas.json"
CACHE_NOMBRES = F03 / "nombres_rcsb.json"


def _jsonl(ruta: Path) -> dict[str, dict[str, Any]]:
    with open(ruta, encoding="utf-8") as fh:
        return {r["pid"]: r for r in (json.loads(l) for l in fh if l.strip())}


def _index(ruta: Path) -> dict[str, float]:
    valores: dict[str, float] = {}
    for linea in ruta.read_text(encoding="utf-8", errors="replace").splitlines():
        if not linea.strip() or linea.startswith("#") or "//" not in linea:
            continue
        pid = linea.split()[0].lower()
        try:
            valores[pid] = float(linea.split("//")[1].split()[0])
        except (IndexError, ValueError):
            continue
    return valores


def _componentes(aristas: list[tuple[str, str]]) -> list[set[str]]:
    vecinos: dict[str, set[str]] = defaultdict(set)
    for a, b in aristas:
        vecinos[a].add(b)
        vecinos[b].add(a)
    vistos: set[str] = set()
    componentes = []
    for inicio in vecinos:
        if inicio in vistos:
            continue
        pila, comp = [inicio], set()
        while pila:
            n = pila.pop()
            if n in comp:
                continue
            comp.add(n)
            pila.extend(vecinos[n] - comp)
        vistos |= comp
        componentes.append(comp)
    return sorted(componentes, key=len, reverse=True)


def _nombre_rcsb(pid: str) -> str | None:
    url = f"https://data.rcsb.org/rest/v1/core/polymer_entity/{pid.upper()}/1"
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            datos = json.load(r)
        return datos.get("rcsb_polymer_entity", {}).get("pdbx_description")
    except Exception:  # noqa: BLE001 - un nombre que falta no invalida el análisis
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--red", action="store_true", help="pide a RCSB los nombres que no estén en caché")
    ap.add_argument("--top", type=int, default=20)
    args = ap.parse_args()

    f01, f02 = _jsonl(F01), _jsonl(F02)
    grupos = json.loads((F03 / "grupos.json").read_text(encoding="utf-8"))["grupos"]
    multi = [g for g in grupos if len(g) >= 2]
    grupo_de = {p: k for k, g in enumerate(multi) for p in g}
    refined = _index(max(PDBBIND.glob("INDEX_refined_data.2020.faseA_*")))
    enriquecido_ruta = sorted(PDBBIND.glob("INDEX_faseb_enriched_full_*.2020"))
    enriquecido = _index(enriquecido_ruta[-1]) if enriquecido_ruta else {}

    aristas: dict[int, list[tuple[str, str]]] = defaultdict(list)
    for shard in sorted((F03 / "pares").glob("shard_*.jsonl")):
        with open(shard, encoding="utf-8") as fh:
            for linea in fh:
                r = json.loads(linea)
                if r["apta_fep"]:
                    aristas[grupo_de[r["pid_a"]]].append((r["pid_a"], r["pid_b"]))

    # Cuántos valores del índice enriquecido se repiten dentro de su diana.
    repetidos = total = 0
    for g in multi:
        valores = [enriquecido[p] for p in g if p in enriquecido]
        total += len(valores)
        repetidos += sum(n for n in Counter(valores).values() if n > 1)

    nombres: dict[str, str | None] = {}
    if CACHE_NOMBRES.is_file():
        nombres = json.loads(CACHE_NOMBRES.read_text(encoding="utf-8"))

    filas = []
    for k, ars in aristas.items():
        comp = _componentes(ars)[0]
        pks = sorted(refined[p] for p in comp if p in refined)
        ok01 = [f01[p] for p in comp if p in f01 and "tautomero_ambiguo" in f01[p]]
        ok02 = [f02[p] for p in comp if p in f02 and "documentado_para_fep" in f02[p]]
        filas.append({
            "grupo": k,
            "ejemplo": min(comp),
            "n_miembros_diana": len(multi[k]),
            "n_componente_mayor": len(comp),
            "n_parejas_aptas": len(ars),
            "n_con_afinidad_faseA": len(pks),
            "rango_pk_faseA": round(pks[-1] - pks[0], 2) if len(pks) >= 2 else 0.0,
            "pk_mediana": round(median(pks), 2) if pks else None,
            "frac_tautomero_ambiguo": round(sum(r["tautomero_ambiguo"] for r in ok01) / len(ok01), 2) if ok01 else None,
            "frac_estereo_indefinido": round(sum(r["estereo_indefinido"] for r in ok01) / len(ok01), 2) if ok01 else None,
            "frac_receptor_documentable": round(sum(r["documentado_para_fep"] for r in ok02) / len(ok02), 2) if ok02 else None,
            "n_con_metales_en_sitio": sum(1 for r in ok02 if r.get("metales_en_sitio")),
            "n_receptor_evaluado": len(ok02),
            "ligandos": sorted(comp),
        })
    filas.sort(key=lambda f: (-f["n_con_afinidad_faseA"], -f["n_componente_mayor"]))

    if args.red:
        for f in filas[: args.top]:
            if f["ejemplo"] not in nombres:
                nombres[f["ejemplo"]] = _nombre_rcsb(f["ejemplo"])
        CACHE_NOMBRES.write_text(json.dumps(nombres, ensure_ascii=False, indent=1) + "\n",
                                 encoding="utf-8", newline="\n")
    for f in filas:
        f["proteina_rcsb"] = nombres.get(f["ejemplo"])

    resultado = {
        "criterio_de_orden": "ligandos con afinidad de Fase A dentro de la componente conexa mayor de parejas aptas",
        "afinidades": "INDEX_refined_data.2020.faseA_* (865); lo añadido desde BindingDB empareja por diana y no se usa",
        "indice_enriquecido": {"valores_en_dianas_multiples": total, "valores_repetidos_dentro_de_su_diana": repetidos,
                               "uso": "no se usa para elegir: empareja por diana, no por ligando"},
        "n_dianas_con_serie": len(filas),
        "dianas": filas,
    }
    SALIDA.write_text(json.dumps(resultado, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")

    print(f"índice enriquecido: {repetidos} de {total} valores repetidos dentro de su diana")
    cab = ("ejemplo", "proteína", "comp", "c/afin", "rango", "taut", "rec_doc", "metal")
    print("  ".join(f"{c:>8}" for c in cab))
    for f in filas[: args.top]:
        print(f"{f['ejemplo']:>8}  {str(f['proteina_rcsb'] or '?')[:28]:>28}  {f['n_componente_mayor']:>4}  "
              f"{f['n_con_afinidad_faseA']:>6}  {f['rango_pk_faseA']:>5}  {f['frac_tautomero_ambiguo']!s:>5}  "
              f"{f['frac_receptor_documentable']!s:>7}  {f['n_con_metales_en_sitio']:>3}/{f['n_receptor_evaluado']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
