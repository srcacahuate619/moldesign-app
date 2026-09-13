"""Pone en `chain` la cadena que mas aporta al sitio, cuando la declarada no lo forma.

# Por que ya no es una decision cientifica

Hasta ahora `chain` decidia el receptor: `preparer.py` conservaba esa cadena y
ninguna otra. Elegirla mal era acoplar contra media cavidad o contra el vacio, y
por eso el doc 71 la trataba como una decision con consecuencias.

Con la preparacion multicadena conectada, **el docking ya no depende de `chain`**
en estos objetivos: `prepare_target` deriva las cadenas a conservar de
`site_chains`. Lo que queda de `chain` es su papel de etiqueta: la usan el visor
para resolver coordenadas de hotspots, el dossier para nombrar el receptor y el
selector para describirlo.

Y ahi si esta mintiendo. Los 21 declaran `"A"`, que es el `default="A"` de
`TargetORM.chain`; ninguno tiene un solo hotspot que nombre esa cadena, y la
distancia mediana de esa cadena al centro de la caja es de 34 A -115,7 A en
7T9I-. No es una anotacion equivocada: es una anotacion que nunca se hizo.

Poner la cadena que mas aporta al sitio no elige nada: **describe lo que ya esta
medido en `site_chains`**, cuyo primer elemento es, por construccion, el mayor
contribuyente.

# Lo que NO cambia

El receptor que se acopla. Ese lo determinan las cadenas del sitio, todas, desde
que `prepare_target` recibe `site_chains`. Este cambio no mueve ningun numero:
arregla lo que el usuario LEE.

# Uso

    python scripts/declarar_cadena_primaria.py [--aplicar]
"""

from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scripts"))

from revisar_cadena_por_receptor import CATALOGO  # noqa: E402

DECISIONES = RAIZ / "docs" / "auditorias" / "cadena_primaria_declarada.json"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--aplicar", action="store_true")
    args = ap.parse_args()

    catalogo = json.loads(CATALOGO.read_text(encoding="utf-8"))
    decisiones = []
    for objetivo in catalogo:
        cadenas = objetivo.get("site_chains") or []
        declarada = (objetivo.get("chain") or "").strip().upper()
        if not cadenas or declarada in cadenas:
            continue
        if len(cadenas) < 2:
            # Sitio de una sola cadena con la declarada equivocada: eso NO es
            # esto. Lo cubre `aplicar_rescates_mecanicos.py`, que exige dos
            # evidencias antes de mover una cadena de la que depende el docking.
            print(f"{objetivo['pdb_id']}: sitio de una cadena, no es caso de este script")
            continue
        hotspots = {(h.get("name") or "").split(":", 1)[0].strip().upper()
                    for h in objetivo.get("hotspots") or [] if ":" in (h.get("name") or "")}
        decisiones.append({
            "pdb_id": objetivo["pdb_id"].upper(),
            "cadena_antes": declarada,
            "cadena_despues": cadenas[0],
            "site_chains": cadenas,
            "aporte_por_cadena": objetivo.get("site_chain_atoms"),
            "hotspots_en_la_cadena_anterior": declarada in hotspots,
            "cadenas_que_nombran_los_hotspots": sorted(hotspots),
        })
        if args.aplicar:
            objetivo["chain"] = cadenas[0]

    for d in decisiones:
        print(f"{d['pdb_id']}  {d['cadena_antes']} -> {d['cadena_despues']}"
              f"   sitio {d['site_chains']}"
              f"   hotspots en {d['cadenas_que_nombran_los_hotspots']}")
    print(f"\n{len(decisiones)} cadenas primarias a declarar")

    if not args.aplicar:
        print("Nada escrito: falta --aplicar")
        return 0

    CATALOGO.write_text(json.dumps(catalogo, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    DECISIONES.write_text(json.dumps({
        "fecha": datetime.date.today().isoformat(),
        "herramienta": "scripts/declarar_cadena_primaria.py",
        "criterio": ("`chain` pasa a ser la primera de `site_chains` -la que mas aporta- "
                     "cuando la declarada no forma el sitio Y el sitio es multicadena"),
        "no_mueve_numeros": ("el receptor que se acopla lo determinan TODAS las cadenas del "
                             "sitio desde que prepare_target recibe site_chains; esto arregla "
                             "lo que el usuario lee, no lo que Vina calcula"),
        "total": len(decisiones),
        "decisiones": decisiones,
    }, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"aplicado. Evidencia en {DECISIONES.relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
