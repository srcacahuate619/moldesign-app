"""Repaso receptor por receptor: que cadena forma de verdad el sitio de union.

# Por que hace falta mas que contar atomos

`preparer.py` conserva solo la cadena que declara el catalogo. El doc 71 mide
cuanta cavidad se pierde con eso, pero para DECIDIR la cadena correcta un
recuento de atomos no basta: dos cadenas pueden aportar volumen parecido y solo
una formar el bolsillo.

La evidencia fuerte es el **ligando co-cristalizado**. Si en la estructura hay un
heteroatomo con pinta de farmaco dentro de la caja, las cadenas que lo contactan
a menos de 4,5 A son las que forman el sitio. Eso es lo que un cristalografo
miraria, y es reproducible.

# Que produce, por objetivo

    cadena declarada, centro y tamaño de la caja
    atomos de CADA cadena dentro de la caja
    ligando co-cristalizado en la caja, si lo hay
    cadenas que contactan ese ligando (<=4.5 A), con cuentas
    una CLASIFICACION propuesta, con su motivo

# Las clasificaciones, y por que estan separadas asi

    OK               la cadena declarada domina el sitio. Nada que hacer.
    CORREGIR         el sitio lo forma OTRA cadena, sola y sin ambiguedad.
                     La declarada aporta poco o nada. Decision mecanica.
    INEXISTENTE      la cadena declarada no esta en el PDB. Decision mecanica.
    MULTICADENA      el sitio lo forman varias cadenas de verdad. NO es
                     mecanico: exige decidir si el receptor multicadena entra
                     en el contrato de preparacion, y eso cambia los numeros de
                     todo lo corrido antes.
    REVISAR          la evidencia no alcanza. Se dice, no se adivina.

`CORREGIR` e `INEXISTENTE` se pueden aplicar sin criterio cientifico: la cadena
declarada esta objetivamente mal. `MULTICADENA` no, y por eso va aparte.

# Uso

    python scripts/revisar_cadena_por_receptor.py [--limite N] [--json salida.json]
"""

from __future__ import annotations

import argparse
import collections
import gzip
import json
import math
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[1]
ESTRUCTURAS = RAIZ / "data" / "targets"
CATALOGO = RAIZ / "curated_targets.json"

# UNA sola implementacion. Los criterios -que heteroatomos no son ligando, como
# se elige entre copias, que distancia es contacto- viven en el backend porque
# los comparten el catalogo, la ingesta automatica y la subida manual. Tenerlos
# aqui duplicados es como se llega a que el catalogo diga «interfaz B·A» y un
# receptor subido por el usuario diga «cadena A» para la misma proteina.
sys.path.insert(0, str(RAIZ / "backend"))
from services.targets.sitio_de_union import (  # noqa: E402
    APORTE_MINIMO,
    CORTE_CONTACTO,
    MIN_ATOMOS_LIGANDO,
    MIN_CONTACTOS_PARA_ESTAR_UNIDO,
    NO_SON_LIGANDO,
    PREFIJOS_DETERGENTE,
    RESIDUOS_MODIFICADOS,
    elegir_ligando,
)

DOMINA = 0.90             # >=90% de los atomos de la caja: manda sola.
COMPARTE = 0.80           # <80%: el sitio se comparte de verdad.

def leer_estructura(pdb_id: str):
    """Atomos de proteina y heteroatomos, o None si no hay estructura."""
    for nombre in (f"{pdb_id}.pdb.gz", f"{pdb_id}.pdb"):
        f = ESTRUCTURAS / nombre
        if not f.is_file():
            continue
        abrir = (lambda p: gzip.open(p, "rt", encoding="utf-8", errors="replace")) \
            if nombre.endswith(".gz") else \
            (lambda p: open(p, encoding="utf-8", errors="replace"))
        proteina, heteros = [], collections.defaultdict(list)
        with abrir(f) as fh:
            for l in fh:
                if not l.startswith(("ATOM", "HETATM")):
                    continue
                try:
                    x, y, z = float(l[30:38]), float(l[38:46]), float(l[46:54])
                except ValueError:
                    continue
                cadena = l[21].strip() or "?"
                if l.startswith("ATOM"):
                    proteina.append((cadena, x, y, z))
                else:
                    residuo = l[17:20].strip().upper()
                    if (residuo in NO_SON_LIGANDO
                            or residuo in RESIDUOS_MODIFICADOS
                            or residuo.startswith(PREFIJOS_DETERGENTE)):
                        continue
                    clave = (residuo, cadena, l[22:27].strip())
                    heteros[clave].append((x, y, z))
        return proteina, heteros
    return None


def revisar(t: dict) -> dict | None:
    pdb = (t.get("pdb_id") or "").upper()
    declarada = (t.get("chain") or "").strip().upper()
    cx, cy, cz = t.get("grid_center_x"), t.get("grid_center_y"), t.get("grid_center_z")
    if not pdb or not declarada or cx is None:
        return None
    datos = leer_estructura(pdb)
    if datos is None:
        return None
    proteina, heteros = datos
    mitad = float(t.get("grid_size_x") or 25.0) / 2.0

    cadenas_del_pdb = {c for c, *_ in proteina}
    en_caja = collections.Counter()
    for c, x, y, z in proteina:
        if abs(x - cx) <= mitad and abs(y - cy) <= mitad and abs(z - cz) <= mitad:
            en_caja[c] += 1
    total = sum(en_caja.values())

    # --- El ligando co-cristalizado que ocupa la caja, si lo hay -------------
    elegido = elegir_ligando(heteros, proteina, (cx, cy, cz), mitad)

    contactos = collections.Counter()
    ligando = None
    if elegido and elegido[2] <= mitad:
        (residuo, cad_lig, _), coords, mejor_dist = elegido
        ligando = {"residuo": residuo, "cadena": cad_lig,
                   "atomos": len(coords), "dist_centro": round(mejor_dist, 1)}
        corte2 = CORTE_CONTACTO ** 2
        for c, x, y, z in proteina:
            for lx, ly, lz in coords:
                if (x - lx) ** 2 + (y - ly) ** 2 + (z - lz) ** 2 <= corte2:
                    contactos[c] += 1
                    break

    # --- Clasificacion -------------------------------------------------------
    prop = en_caja.get(declarada, 0) / total if total else 0.0
    # La evidencia del ligando manda sobre el recuento de volumen cuando existe.
    reparto = contactos if contactos else en_caja
    total_rep = sum(reparto.values())
    prop_decl = reparto.get(declarada, 0) / total_rep if total_rep else 0.0
    lider, n_lider = (reparto.most_common(1)[0] if reparto else (None, 0))
    prop_lider = n_lider / total_rep if total_rep else 0.0

    if declarada not in cadenas_del_pdb:
        clase, motivo, sugerida = "INEXISTENTE", \
            f"la cadena '{declarada}' no esta en el PDB (hay {sorted(cadenas_del_pdb)})", lider
    elif total == 0:
        clase, motivo, sugerida = "REVISAR", "la caja no contiene ningun atomo de proteina", None
    elif prop_decl >= DOMINA:
        clase, motivo, sugerida = "OK", \
            f"la cadena declarada aporta el {prop_decl*100:.0f}% del sitio", declarada
    elif prop_lider >= DOMINA and lider != declarada:
        clase, motivo, sugerida = "CORREGIR", \
            f"el sitio lo forma '{lider}' ({prop_lider*100:.0f}%); la declarada aporta {prop_decl*100:.0f}%", lider
    elif prop_lider < COMPARTE or (prop_decl > 0.05 and prop_lider < DOMINA):
        clase, motivo, sugerida = "MULTICADENA", \
            "el sitio lo forman varias cadenas: " + ", ".join(
                f"{c} {n/total_rep*100:.0f}%" for c, n in reparto.most_common(4)), None
    else:
        clase, motivo, sugerida = "REVISAR", \
            f"lider '{lider}' con {prop_lider*100:.0f}%, declarada {prop_decl*100:.0f}%", None

    return {
        "pdb_id": pdb, "declarada": declarada, "clase": clase, "motivo": motivo,
        "sugerida": sugerida,
        "atomos_en_caja": dict(en_caja.most_common()),
        "proporcion_declarada_en_caja": round(prop, 3),
        "ligando": ligando,
        "contactos_del_ligando": dict(contactos.most_common()) if contactos else None,
        "evidencia": "ligando co-cristalizado" if contactos else "volumen en la caja",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limite", type=int, default=100, help="cuantos revisar (por gravedad)")
    ap.add_argument("--json", type=str, default=None, help="guardar el detalle")
    ap.add_argument("--clase", type=str, default=None, help="filtrar por clasificacion")
    args = ap.parse_args()

    catalogo = json.loads(CATALOGO.read_text(encoding="utf-8"))
    revisados = [r for r in (revisar(t) for t in catalogo) if r]
    # Los mas graves primero: los que menos aportan de la cadena declarada.
    revisados.sort(key=lambda r: r["proporcion_declarada_en_caja"])
    seleccion = revisados[: args.limite]
    if args.clase:
        seleccion = [r for r in seleccion if r["clase"] == args.clase.upper()]

    resumen = collections.Counter(r["clase"] for r in seleccion)
    print(f"revisados: {len(revisados)}   mostrados: {len(seleccion)}")
    print("  " + "   ".join(f"{k}={v}" for k, v in resumen.most_common()))
    print()
    for r in seleccion:
        lig = r["ligando"]
        desc_lig = (f"{lig['residuo']} ({lig['atomos']} at, {lig['dist_centro']} A del centro)"
                    if lig else "sin ligando en la caja")
        print(f"{r['pdb_id']}  declara '{r['declarada']}'  ->  {r['clase']}"
              + (f"  sugerida '{r['sugerida']}'" if r["sugerida"] else ""))
        print(f"    {r['motivo']}")
        print(f"    caja: {r['atomos_en_caja']}")
        print(f"    ligando: {desc_lig}"
              + (f"   contactos: {r['contactos_del_ligando']}" if r["contactos_del_ligando"] else ""))
        print()

    if args.json:
        pathlib.Path(args.json).write_text(
            json.dumps(revisados, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"detalle completo en {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
