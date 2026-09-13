"""AUDITORIA: cuanta cavidad pierde el receptor al conservar UNA sola cadena.

# Que mide, y por que se mide en vez de opinarse

`preparer.py` filtra el PDB a la cadena que declara el catalogo
(`if current_chain != chain_id: continue`). Para una proteina monomerica eso es
ortodoxo. Cuando el sitio activo se forma entre varias cadenas, en cambio, el
ligando acopla contra media cavidad — o contra ninguna.

Esta auditoria cuenta, para cada objetivo, cuantos atomos que caen DENTRO de la
caja de docking pertenecen a cadenas que la preparacion va a descartar.

# Lo que encontro el 2026-09-02, sobre los 387 objetivos del catalogo

    pierden >=20% de los atomos de la caja : 149
    pierden entre 5% y 20%                 :  19
    pierden <5%                            : 219

Y al menos veinte pierden el 100%: la cadena declarada no aporta NI UN ATOMO a
la caja. Tres modos de fallo distintos, verificados uno a uno:

  1IAS  5 cadenas. La caja esta sobre la B (3,4 A). La declarada, A, esta a
        19,1 A. El receptor preparado no tiene nada dentro de la caja:
        **Vina acopla contra el vacio** y devuelve una afinidad igualmente.

  2OYE  El PDB solo contiene la cadena P. El catalogo declara A, que no existe.

  1TW7  Proteasa del VIH, homodimero. Ambas cadenas a 2,0 A del centro, con 309
        y 316 atomos en la caja. El sitio activo ESTA en la interfaz: conservar
        solo A descarta la mitad del bolsillo.

# Que NO decide esta herramienta

Que hacer con cada caso. Corregir la cadena declarada, preparar el receptor con
varias cadenas, o retirar el objetivo del catalogo son decisiones cientificas
distintas y con consecuencias distintas sobre los resultados ya sellados. Esto
solo pone la lista sobre la mesa, medida.

# Uso

    python scripts/auditar_cadena_del_receptor.py
"""
import collections
import gzip
import json
import pathlib

RAIZ = pathlib.Path("D:/moldesign-build")
ESTRUCTURAS = RAIZ / "data" / "targets"

catalogo = json.loads((RAIZ / "curated_targets.json").read_text(encoding="utf-8"))

filas = []
sin_estructura = 0
for t in catalogo:
    pdb = (t.get("pdb_id") or "").upper()
    cadena = (t.get("chain") or "").strip().upper()
    cx, cy, cz = t.get("grid_center_x"), t.get("grid_center_y"), t.get("grid_center_z")
    sx = t.get("grid_size_x") or 25.0
    if not pdb or not cadena or cx is None:
        continue
    f = ESTRUCTURAS / f"{pdb}.pdb.gz"
    if not f.is_file():
        sin_estructura += 1
        continue
    mitad = float(sx) / 2.0
    dentro = collections.Counter()
    try:
        with gzip.open(f, "rt", encoding="utf-8", errors="replace") as fh:
            for l in fh:
                if not l.startswith("ATOM"):
                    continue
                try:
                    x = float(l[30:38]); y = float(l[38:46]); z = float(l[46:54])
                except ValueError:
                    continue
                if abs(x - cx) <= mitad and abs(y - cy) <= mitad and abs(z - cz) <= mitad:
                    dentro[l[21].strip() or "?"] += 1
    except OSError:
        continue
    total = sum(dentro.values())
    if total == 0:
        continue
    conservados = dentro.get(cadena, 0)
    perdidos = total - conservados
    filas.append((pdb, cadena, total, conservados, perdidos, dict(dentro)))

filas.sort(key=lambda r: -(r[4] / max(r[2], 1)))
print(f"targets evaluados     : {len(filas)}")
print(f"sin estructura en disco: {sin_estructura}\n")

graves = [r for r in filas if r[4] / max(r[2], 1) >= 0.20]
algo = [r for r in filas if 0.05 <= r[4] / max(r[2], 1) < 0.20]
limpios = [r for r in filas if r[4] / max(r[2], 1) < 0.05]

print(f"pierden >=20% de los atomos de la caja : {len(graves)}   <-- media cavidad o mas")
print(f"pierden entre 5% y 20%                 : {len(algo)}")
print(f"pierden <5%                            : {len(limpios)}")
print()
print("Los 20 peores (pdb, cadena declarada, atomos en caja, conservados, perdidos, %):")
for pdb, cadena, total, cons, perd, det in filas[:20]:
    print(f"  {pdb}  '{cadena}'  {total:5d} -> {cons:5d}  pierde {perd:5d} ({perd/total*100:4.1f}%)  {det}")
