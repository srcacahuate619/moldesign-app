"""Recentra en el inhibidor las entradas del catálogo cuyo «ligando del cristal» era un cofactor.

# El defecto

Trece entradas declaraban como `site_ligand` el cofactor del complejo, no el inhibidor que define el sitio: el hemo
en diez COX-1/COX-2 y en CYP2D6 (5TFT), el NADP en la DHFR de S. aureus (3SRW) y el FMN en la DHODH de
P. falciparum (5TBO). La caja estaba centrada en el cofactor —en las COX, en el sitio peroxidasa, a unos 20 Å del
canal de la ciclooxigenasa donde se une el AINE— y la preparación retiraba el cofactor como si fuera el ligando, así
que el sitio acoplado quedaba sin él. Preparación lo bloquea desde `7b3ad800` («Cofactor retirado como ligando del
cristal»); esto corrige la anotación.

# De dónde salen las referencias

Del worktree de curación de receptores (rama `codex/receptores-curacion-20261008-wip`, `affbc92e`,
`docs/auditorias/receptores-continuacion-20261008/decisiones_referencia.json`): código CCD e instancia (cadena y
número) del inhibidor de cada complejo.

3N8Y se dejó fuera el primer día porque es la COX-1 tratada con aspirina y lleva una serina acetilada (OAS): parecía
pedir una preparación covalente. Medido después (2026-10-11), la OAS sólo está en la cadena B, como
microheterogeneidad (dos conformaciones) y a 34,8 Å del diclofenaco de la cadena A. La cadena A, que es la del
catálogo, tiene la Ser530 sin modificar, y el carboxilato del diclofenaco A:701 le da un puente de hidrógeno (O–OG
2,53 Å): es el modo de unión invertido del diclofenaco, contra Tyr385 y Ser530. Entra con `--solo 3N8Y`.

# Qué se mide aquí, con el código de desarrollo

* centro = centroide de los átomos pesados de ESA instancia (sin altloc o el A); el lado de la caja no cambia y el
  ligando tiene que quedar a 4 Å o más de cada cara;
* `site_chains`, `site_chain_atoms`, `site_evidence` y `site_ligand` = `anotar_sitio` sobre la caja nueva, que tiene
  que elegir esa misma referencia;
* hotspots = el criterio de `reanotar_hotspots_del_ligando.py` (residuos a <= 4,5 Å del ligando de la caja, los 15
  más cercanos), con `hotspots_source = box_ligand_contacts`; cada uno se comprueba otra vez contra la instancia.

Una entrada con cualquier problema no se aplica. Los pesos de los hotspots son una heurística de visualización, no
energía. Recentrar no valida el receptor: 5TBO sigue con el hueco VAL343→GLU356.

Uso:
    python scripts/corregir_referencias_cofactor.py            # mide y escribe la evidencia, no toca el catálogo
    python scripts/corregir_referencias_cofactor.py --aplicar  # además reescribe curated_targets.json
    python scripts/corregir_referencias_cofactor.py --solo 3N8Y --aplicar
                                    # sólo esa entrada; conserva las filas de las demás en la evidencia

Con `--solo` las otras filas no se vuelven a medir: después de aplicarlas, su «antes» sería el catálogo ya corregido.
"""
from __future__ import annotations

import argparse
import gzip
import json
import math
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(RAIZ / "backend"), str(RAIZ / "scripts")]

from services.targets.sitio_de_union import CORTE_CONTACTO, anotar_sitio  # noqa: E402
import reanotar_hotspots_del_ligando as reanotacion  # noqa: E402

CATALOGO = RAIZ / "curated_targets.json"
EVIDENCIA = RAIZ / "docs" / "auditorias" / "referencias_del_sitio_2026-10-11.json"
FUENTE_DE_LA_DECISION = (
    "codex/receptores-curacion-20261008-wip (affbc92e): "
    "docs/auditorias/receptores-continuacion-20261008/decisiones_referencia.json"
)
MARGEN_MINIMO_A = 4.0

#: pdb -> (referencia, cadena, número, motivo de la revisión).
REFERENCIAS: dict[str, tuple[str, str, str, str]] = {
    "1CX2": ("S58", "A", "701", "COX-2 murina con SC-558; el hemo se conserva como cofactor."),
    "1Q4G": ("BFL", "A", "701", "COX-1 ovina con ácido alfa-metil-4-bifenilacético."),
    "2OYE": ("IM8", "P", "700", "Indometacina-(R)-alfa-etil-etanolamida en COX-1."),
    "2OYU": ("IMS", "P", "700", "Indometacina-(S)-alfa-etil-etanolamida en COX-1; no intercambiar enantiómeros."),
    "3KK6": ("CEL", "A", "701", "Celecoxib define el sitio del complejo COX-1; su fallo de preparación se conserva."),
    "3N8W": ("FLP", "A", "802", "Flurbiprofeno en A del heterodímero R120Q/nativo; no es la enzima nativa homogénea."),
    "3N8X": ("NIM", "A", "701", "COX-1 con nimesulida."),
    "3N8Y": ("DIF", "A", "701", "COX-1 tratada con aspirina, con diclofenaco en la cadena A. La serina acetilada "
                                "(OAS) sólo está en la B, a 34,8 Å; en la A la Ser530 está sin modificar."),
    "3N8Z": ("FLP", "A", "701", "COX-1 con flurbiprofeno."),
    "3SRW": ("Q27", "X", "168", "DHFR de S. aureus con una 7-aril-2,4-diaminoquinazolina; el NADP es cofactor."),
    "5TBO": ("78Z", "A", "1001", "DHODH de P. falciparum con DSM421; el FMN es cofactor."),
    "5TFT": ("P6U", "A", "604", "CYP2D6 con un inhibidor de BACE1; el hemo no se retira como si fuera el ligando."),
    "5U6X": ("P6A", "A", "702", "Complejo COX-1:P6."),
    "5WBE": ("63X", "A", "803", "Complejo COX-1:mofezolac."),
}


def _atomos_pesados(fuente: str, ref: str, cadena: str, numero: str) -> tuple[list[tuple[float, float, float]], set[str]]:
    atomos, altlocs = [], set()
    for linea in fuente.splitlines():
        if (linea.startswith("HETATM") and linea[17:20].strip() == ref and linea[21:22].strip() == cadena
                and linea[22:26].strip() == numero and linea[76:78].strip().upper() not in {"H", "D"}):
            alt = linea[16:17].strip()
            altlocs.add(alt)
            if alt in ("", "A"):
                atomos.append(tuple(float(linea[i:i + 8]) for i in (30, 38, 46)))
    return atomos, altlocs


def medir(entrada: dict) -> tuple[dict, dict | None]:
    """La fila de evidencia y, si no hay ningún problema, los campos nuevos de la entrada."""
    pdb = entrada["pdb_id"].upper()
    ref, cadena, numero, motivo = REFERENCIAS[pdb]
    fila: dict = {
        "pdb_id": pdb, "referencia": f"{ref} {cadena}:{numero}", "motivo": motivo,
        "antes": {
            "site_ligand": entrada.get("site_ligand"),
            "centro": [entrada[f"grid_center_{e}"] for e in "xyz"],
            "hotspots": [h["name"] for h in entrada.get("hotspots") or []],
            "hotspots_source": entrada.get("hotspots_source"),
            "site_chains": entrada.get("site_chains"),
        },
        "problemas": [],
    }
    with gzip.open(RAIZ / "data" / "targets" / f"{pdb}.pdb.gz", "rt", encoding="utf-8") as fh:
        fuente = fh.read()
    atomos, altlocs = _atomos_pesados(fuente, ref, cadena, numero)
    fila["atomos_pesados"] = len(atomos)
    fila["altlocs"] = sorted(altlocs)
    if len(atomos) < 6:
        fila["problemas"].append(f"la instancia tiene {len(atomos)} átomos pesados")
        return fila, None
    centro = tuple(round(sum(p[i] for p in atomos) / len(atomos), 3) for i in range(3))
    lado = tuple(float(entrada[f"grid_size_{e}"]) for e in "xyz")
    margen = min(lado[i] / 2 - abs(p[i] - centro[i]) for p in atomos for i in range(3))
    fila["despues"] = {"centro": list(centro), "lado": list(lado)}
    fila["desplazamiento_del_centro_A"] = round(math.dist(centro, fila["antes"]["centro"]), 2)
    fila["margen_minimo_del_ligando_A"] = round(margen, 2)
    if margen < MARGEN_MINIMO_A:
        fila["problemas"].append(f"el ligando queda a {margen:.2f} Å de una cara de la caja")
    sitio = anotar_sitio(fuente, centro, lado)
    if not sitio or sitio.get("site_ligand") != ref:
        fila["problemas"].append(f"anotar_sitio elige {sitio and sitio.get('site_ligand')!r}")
    elif entrada.get("chain") not in sitio["site_chains"]:
        fila["problemas"].append(f"la cadena {entrada.get('chain')} no forma el sitio {sitio['site_chains']}")
    hotspots = reanotacion.reanotar(dict(entrada, grid_center_x=centro[0], grid_center_y=centro[1],
                                         grid_center_z=centro[2]))
    if isinstance(hotspots, str):
        fila["problemas"].append(f"hotspots: {hotspots}")
        return fila, None
    if hotspots["ligando"] != ref:
        fila["problemas"].append(f"los hotspots siguen a {hotspots['ligando']}")
    for h in hotspots["hotspots"]:
        c, etiqueta = h["name"].split(":")
        puntos = [tuple(float(l[i:i + 8]) for i in (30, 38, 46)) for l in fuente.splitlines()
                  if l.startswith("ATOM") and l[21:22].strip() == c and l[17:20].strip() + l[22:26].strip() == etiqueta]
        if not puntos or min(math.dist(p, q) for p in puntos for q in atomos) > CORTE_CONTACTO:
            fila["problemas"].append(f"el hotspot {h['name']} no toca la referencia")
    fila["despues"].update(sitio or {})
    fila["despues"]["hotspots"] = [h["name"] for h in hotspots["hotspots"]]
    if fila["problemas"]:
        return fila, None
    return fila, {
        "grid_center_x": centro[0], "grid_center_y": centro[1], "grid_center_z": centro[2],
        "hotspots": hotspots["hotspots"], "hotspots_source": reanotacion.FUENTE_REANOTADA, **sitio,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--aplicar", action="store_true", help="reescribe curated_targets.json")
    ap.add_argument("--solo", nargs="+", metavar="PDB",
                    help="mide sólo estas entradas y conserva las filas de las demás en la evidencia")
    args = ap.parse_args()
    solo = {p.upper() for p in args.solo or []}
    assert solo <= set(REFERENCIAS), f"sin referencia: {sorted(solo - set(REFERENCIAS))}"
    previas = ({d["pdb_id"]: d for d in json.loads(EVIDENCIA.read_text(encoding="utf-8"))["decisiones"]}
               if solo else {})
    assert not solo or set(previas) | solo == set(REFERENCIAS), "la evidencia previa no cubre las demás"

    catalogo = json.loads(CATALOGO.read_text(encoding="utf-8"))
    filas, aplicadas = [], []
    for entrada in catalogo:
        pdb = entrada["pdb_id"].upper()
        if pdb not in REFERENCIAS:
            continue
        if solo and pdb not in solo:
            filas.append(previas[pdb])
            continue
        fila, nuevos = medir(entrada)
        filas.append(fila)
        estado = "OK" if nuevos else "NO SE APLICA: " + "; ".join(fila["problemas"])
        print(f"{fila['pdb_id']}  {fila['antes']['site_ligand']} -> {fila['referencia']}  "
              f"{fila.get('desplazamiento_del_centro_A')} Å  {estado}")
        if nuevos and args.aplicar:
            entrada.update(nuevos)
            aplicadas.append(fila["pdb_id"])
    assert len(filas) == len(REFERENCIAS), "falta alguna entrada en el catálogo"

    EVIDENCIA.write_text(json.dumps({
        "herramienta": "scripts/corregir_referencias_cofactor.py",
        "fuente_de_la_decision": FUENTE_DE_LA_DECISION,
        "criterio": (f"centro en el centroide de la instancia; ligando a >= {MARGEN_MINIMO_A} Å de cada cara; "
                     f"sitio con anotar_sitio; hotspots a <= {CORTE_CONTACTO} Å del ligando de la caja"),
        "fuera_a_proposito": {},
        "revisadas": {"3N8Y": (
            "Fuera el primer día por la serina acetilada (OAS). Medido después: la OAS sólo está en la cadena B "
            "(microheterogénea, a 34,8 Å del diclofenaco A:701); la cadena A del catálogo tiene la Ser530 sin "
            "modificar y el carboxilato del diclofenaco le da un puente de hidrógeno (2,53 Å).")},
        "decisiones": filas,
    }, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    if args.aplicar:
        # En LF, como el resto del catálogo: va con `-text` y su SHA-256 está en docs/catalog_versions/.
        CATALOGO.write_text(json.dumps(catalogo, indent=2, ensure_ascii=False) + "\n", encoding="utf-8",
                            newline="\n")
        print(f"aplicadas {len(aplicadas)}: {' '.join(aplicadas)}")
    else:
        print("catálogo sin tocar: falta --aplicar")
    print(f"evidencia: {EVIDENCIA.relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
