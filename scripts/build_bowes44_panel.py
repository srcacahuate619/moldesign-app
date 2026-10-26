#!/usr/bin/env python3
r"""Convierte la validación del panel de Bowes 2012 en el archivo que lee el backend.

# Qué produce

`backend/data/anti_dianas_bowes44.json`: las 44 dianas del panel mínimo de
Bowes et al. 2012, cada una con su estado:

- `validada`: hay una estructura humana cuya preparación termina y en la que el
  **ligando cocristalizado se reacopla en su propia cavidad**: el centroide de la
  primera pose queda a ≤ 4 Å del cristalográfico. Viaja con su caja, sus cadenas
  del sitio y las cifras del redocking. `pose_reproducida` dice, además, si el
  RMSD baja de 2 Å; eso mide la exactitud de Vina, no la estructura, y no decide.
- `sin_estructura_preparable`: hay estructura, pero la preparación o el
  redocking no pasan. Se ofrece en la lista y no se puede seleccionar.
- `sin_estructura`: no hay estructura humana que cumpla los filtros.

El redocking demuestra que la caja describe el sitio de ESE ligando. **No
demuestra que ese sitio sea el farmacológicamente relevante**: con hERG, las
estructuras de rayos X son del dominio PAS y no del poro (DOCK-016). Por eso
`sitio_adjudicado` sólo es cierto donde una persona lo revisó, y las dos dianas
del panel por defecto (hERG 5VA1 y 5-HT2B 7SRQ) siguen viniendo del catálogo
curado, no de aquí.

# Uso

    python scripts/build_bowes44_panel.py --write
    python scripts/build_bowes44_panel.py --check
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
VALIDACION = RAIZ / "docs" / "auditorias" / "ae4db6a" / "bowes44_validacion.json"
DESTINO = RAIZ / "backend" / "data" / "anti_dianas_bowes44.json"

#: Qué reacción adversa motiva su presencia en el panel. Farmacología de manual;
#: no son predicciones del producto ni cifras medidas aquí.
RIESGO: dict[str, str] = {
    "A2A": "Receptor de adenosina: efectos cardiovasculares y sobre el sistema nervioso central.",
    "alpha1A": "Receptor adrenérgico: hipotensión ortostática y taquicardia refleja.",
    "alpha2A": "Receptor adrenérgico: sedación, hipotensión y bradicardia.",
    "beta1": "Receptor adrenérgico cardiaco: frecuencia y contractilidad.",
    "beta2": "Receptor adrenérgico: temblor, taquicardia y tono bronquial.",
    "CB1": "Receptor cannabinoide: efectos psiquiátricos (retirada del rimonabant).",
    "CB2": "Receptor cannabinoide periférico: efectos inmunitarios.",
    "CCK1 (CCKA)": "Receptor de colecistoquinina: motilidad y secreción gastrointestinal.",
    "D1": "Receptor dopaminérgico: efectos motores y cardiovasculares.",
    "D2S": "Receptor dopaminérgico: efectos extrapiramidales e hiperprolactinemia.",
    "ETA": "Receptor de endotelina: vasoconstricción e hipertensión.",
    "H1": "Receptor de histamina: sedación y aumento de peso.",
    "H2": "Receptor de histamina: secreción ácida gástrica.",
    "M1": "Receptor muscarínico: efectos anticolinérgicos centrales, incluida confusión.",
    "M2": "Receptor muscarínico cardiaco: taquicardia por bloqueo vagal.",
    "M3": "Receptor muscarínico: sequedad de boca, retención urinaria, visión borrosa.",
    "delta2 (DOP)": "Receptor opioide delta: efectos sobre el sistema nervioso central y convulsiones.",
    "kappa (KOP)": "Receptor opioide kappa: disforia y sedación.",
    "mu (MOP)": "Receptor opioide mu: depresión respiratoria y dependencia.",
    "5-HT1A": "Receptor serotoninérgico: efectos sobre el sistema nervioso central.",
    "5-HT1B": "Receptor serotoninérgico: vasoconstricción, incluida la coronaria.",
    "5-HT2A": "Receptor serotoninérgico: efectos alucinógenos por agonismo.",
    "5-HT2B": "Su agonismo produce valvulopatía cardiaca (fenfluramina, pergolida).",
    "V1a": "Receptor de vasopresina: vasoconstricción y efectos renales.",
    "dopamine transporter": "Transportador de dopamina: potencial de abuso y efectos motores.",
    "norepinephrine transporter": "Transportador de noradrenalina: efectos cardiovasculares.",
    "5-HT transporter": "Transportador de serotonina: síndrome serotoninérgico y efectos digestivos.",
    "BZD (central)": "Sitio de benzodiacepinas del receptor GABA-A: sedación y dependencia.",
    "NMDA": "Receptor de glutamato: efectos psicomiméticos y neurotoxicidad.",
    "N neuronal alpha4beta2": "Receptor nicotínico neuronal: efectos sobre el sistema nervioso central.",
    "5-HT3": "Receptor serotoninérgico ionotrópico: náuseas, vómitos y motilidad intestinal.",
    "Ca2+ channel (L, dihydropyridine site)": "Canal de calcio tipo L: hipotensión y efectos cardiacos.",
    "hERG": "Arritmia cardiaca por prolongación del QT (terfenadina, cisaprida, grepafloxacino).",
    "KV channel": "Canal de potasio dependiente de voltaje: efectos cardiacos y neuronales.",
    "Na+ channel (site 2)": "Canal de sodio cardiaco: alteraciones de la conducción.",
    "AR": "Receptor de andrógenos: efectos endocrinos antiandrogénicos.",
    "GR": "Receptor de glucocorticoides: efectos metabólicos e inmunitarios.",
    "Lck kinase": "Quinasa de linfocitos T: inmunosupresión.",
    "COX1": "Ciclooxigenasa 1: lesión gastrointestinal y efecto antiagregante.",
    "COX2": "Ciclooxigenasa 2: riesgo cardiovascular y renal.",
    "acetylcholinesterase": "Acetilcolinesterasa: síndrome colinérgico.",
    "MAO-A": "Monoaminooxidasa A: crisis hipertensiva por tiramina y síndrome serotoninérgico.",
    "PDE3A": "Fosfodiesterasa 3: inotropismo y arritmias (la milrinona es de uso hospitalario).",
    "PDE4D2": "Fosfodiesterasa 4: náuseas, vómitos y vasculitis en modelos animales.",
}

#: Las dos que vienen del catálogo curado, con su sitio ya adjudicado en la
#: fase 1 (hERG sobre el tetrámero y sus hotspots T623/S624/Y652/F656).
DEL_CATALOGO = {"hERG": "5VA1", "5-HT2B": "7SRQ"}
ADOPCION_5HT2B = RAIZ / "docs" / "catalog_versions" / "anti-diana-5ht2b-2026-10-05.json"

#: Los mismos umbrales que la validación: el sitio decide, el RMSD se informa.
SITIO_MAX_A = 4.0
RMSD_MAX_A = 2.0


def construir() -> dict:
    datos = json.loads(VALIDACION.read_text(encoding="utf-8"))
    dianas = []
    for fila in datos["dianas"]:
        assay = fila["assay"]
        entrada: dict = {
            "assay": assay,
            "familia": fila["familia"],
            "gen": fila.get("gen"),
            "uniprot": (fila.get("uniprot") or {}).get("accession"),
            "nombre_proteina": (fila.get("uniprot") or {}).get("protein_name"),
            "riesgo": RIESGO.get(assay, "Diana del panel mínimo de Bowes et al. 2012."),
        }
        buenas = [e for e in fila["estructuras"] if e.get("estado") == "sitio_confirmado"]
        if assay in DEL_CATALOGO:
            entrada.update({
                "estado": "en_el_panel_por_defecto", "pdb_id": DEL_CATALOGO[assay],
                "sitio_adjudicado": True,
                "procedencia_sitio": "catálogo curado; sitio adjudicado en la fase 1 de la auditoría",
            })
            # La diana no se duplica, pero su medida no se tira: es la
            # corroboración independiente del sitio que usa el panel por defecto.
            # En hERG, 8ZYQ trae pimozide en el poro con las cuatro subunidades
            # explícitas, mientras 5VA1 deposita una sola y reconstruye el
            # tetrámero por BIOMT.
            if buenas:
                otra = min(buenas, key=lambda e: e.get("distancia_centroides_A") or 99)
                entrada["alternativa_medida"] = {
                    "pdb_id": otra["pdb_id"], "metodo": otra.get("metodo"),
                    "resolucion_A": otra.get("resolucion_A"), "titulo": otra.get("titulo"),
                    "site_chains": otra.get("site_chains"),
                    "site_ligand": otra.get("site_ligand"),
                    "center": otra["caja"]["centro"], "size": otra["caja"]["tamano"],
                    "distancia_centroides_A": otra.get("distancia_centroides_A"),
                    "pose_reproducida": otra.get("pose_reproducida"),
                    "rmsd_pose1_A": otra.get("rmsd_pose1_A"),
                    "nota": ("no se ofrece como anti-diana aparte para no duplicar la diana; "
                             "queda como medida independiente del sitio"),
                }
            if assay == "5-HT2B":
                nueva = json.loads(ADOPCION_5HT2B.read_text(encoding="utf-8"))["5ht2b_adoption"]
                medida = nueva["redocking"]
                entrada.update({
                    "metodo": nueva["metodo"], "resolucion_A": nueva["resolucion_A"],
                    "site_ligand": nueva["site_ligand"],
                    "redock": {**medida, "vina": nueva["vina"], "ligando": nueva["site_ligand"]},
                    "truncadas_en_sitio": sum(t["site_critical"] for t in nueva["preparation"]["truncated_sidechains"]),
                    "procedencia_sitio": "LSD 7LD ortostérico; continuidad y redocking medidos en anti-diana-5ht2b-2026-10-05.json",
                })
            dianas.append(entrada)
            continue
        if buenas:
            mejor = min(buenas, key=lambda e: e.get("distancia_centroides_A") or 99)
            entrada.update({
                "estado": "validada",
                "pdb_id": mejor["pdb_id"], "metodo": mejor.get("metodo"),
                "resolucion_A": mejor.get("resolucion_A"), "titulo": mejor.get("titulo"),
                "chain": (mejor.get("site_chains") or ["A"])[0],
                "site_chains": mejor.get("site_chains"),
                "site_ligand": mejor.get("site_ligand"),
                "center": mejor["caja"]["centro"], "size": mejor["caja"]["tamano"],
                "affinity_threshold": -7.0,
                "redock": {"distancia_centroides_A": mejor.get("distancia_centroides_A"),
                           "pose_reproducida": mejor.get("pose_reproducida"),
                           "rmsd_pose1_A": mejor.get("rmsd_pose1_A"),
                           "rmsd_mejor_A": mejor.get("rmsd_mejor_A"),
                           "afinidad_kcal": mejor.get("afinidad_mejor_kcal"),
                           "ligando": (mejor.get("ligando") or {}).get("comp_id"),
                           "vina": {"exhaustiveness": 16, "seed": 42}},
                "receptor_sha256": mejor.get("receptor_sha256"),
                "sitio_adjudicado": False,
                "procedencia_sitio": ("caja derivada del ligando cocristalizado; el redocking "
                                      "confirma ese sitio, no que sea el farmacológicamente relevante"),
            })
        elif fila["estructuras"]:
            estados = sorted({e.get("estado") for e in fila["estructuras"] if e.get("estado")})
            entrada.update({
                "estado": "sin_estructura_preparable",
                "intentos": [{"pdb_id": e["pdb_id"], "ligando": (e.get("ligando") or {}).get("comp_id"),
                              "estado": e.get("estado"), "rmsd_pose1_A": e.get("rmsd_pose1_A")}
                             for e in fila["estructuras"]],
                "motivo": ("Ninguna estructura pasó: "
                           + "; ".join(_GLOSA.get(e, e) for e in estados)
                           + f". El criterio es el centroide de la primera pose a ≤ {SITIO_MAX_A} Å "
                             "del ligando cristalizado."
                           + ("" if assay not in _CAUSA_MEDIDA else " " + _CAUSA_MEDIDA[assay])),
            })
        else:
            motivo = fila.get("nota") or "sin estructura humana que cumpla los filtros"
            if assay in _CAUSA_MEDIDA:
                motivo = f"{motivo}. {_CAUSA_MEDIDA[assay]}"
            entrada.update({"estado": "sin_estructura", "motivo": motivo})
        dianas.append(entrada)
    return {
        "_doc": ("Panel mínimo de Bowes et al. 2012 (44 dianas) para selectividad. Generado por "
                 "scripts/build_bowes44_panel.py desde bowes44_validacion.json; no editar a mano."),
        "referencia": "Bowes et al. 2012, Nat Rev Drug Discov 11:909-922, tabla 1",
        "criterio_validacion": {
            "sitio": f"centroide de la primera pose a ≤ {SITIO_MAX_A} Å del ligando cristalizado",
            "pose_reproducida": f"además, RMSD simétrico de la primera pose ≤ {RMSD_MAX_A} Å",
            "limite": ("el redocking demuestra que la caja describe el sitio de ese ligando; "
                       "no que ese sitio sea el relevante para la reacción adversa"),
        },
        "dianas": dianas,
    }


DOC = RAIZ / "docs" / "auditorias" / "panel_bowes44_actual.md"

#: Qué significa cada estado de intento, para que el motivo se lea sin el código
#: delante. `no_es_farmaco` es el más fácil de malinterpretar: no es que faltara
#: estructura, es que su único HETATM era un cofactor, un lípido o un tampón.
_GLOSA = {
    "no_es_farmaco": ("su único ligando no es un fármaco (cofactor, lípido, "
                      "detergente, tampón o análogo de nucleótido)"),
    "no_preparable": "Meeko no pudo preparar el receptor",
    "no_descargable": "el RCSB no la sirvió",
    "sin_ligando": "el ligando declarado no aparece en las coordenadas",
    "sin_sdf_ideal": "el CCD no da SDF ideal del ligando",
    "ligando_no_preparable": "el ligando no se pudo preparar para Vina",
    "vina_falló": "Vina no terminó",
    "pose_fuera_del_sitio": "la pose cayó fuera de la cavidad del ligando cristalizado",
    "sitio_sin_contactos": "ningún átomo proteico a 4,5 Å del ligando",
}

#: La causa concreta, medida, de las que no entran. El estado genérico no la dice
#: y sin ella el lector no sabe si falta trabajo o falta estructura.
_CAUSA_MEDIDA = {
    "COX1": ("La única entrada humana del PDB con ligando bajo los filtros es 6Y3C "
             "(3,36 Å) y su único HETATM es citrato: la COX-1 cristalizada con "
             "inhibidor es casi siempre ovina, y sustituir de especie cambia el sitio. "
             "Queda abierto: fijar a mano una estructura y adjudicar el sitio."),
    "MAO-A": ("En las cuatro entradas (2Z5Y, 2Z5X, 2BXR, 2BXS) Meeko avisa «matched "
              "with excess inter-residue bond(s)» sobre el residuo del FAD y aborta "
              "con «adjacent_mol doesn't contain the mapped atoms». El enlace de más "
              "es el que une el FAD covalentemente a una cisteína del sitio activo, "
              "propio de las monoamino-oxidasas. No es la caja: el producto no "
              "prepara cofactores covalentes. Queda declarado, no sorteado."),
    "N neuronal alpha4beta2": ("Las estructuras de α4β2 son crio-EM por encima de "
                               "3,5 Å, el tope del filtro. Subir el tope es una "
                               "decisión que hay que medir, no asumir."),
    "KV channel": ("La tabla 1 de Bowes dice «KV channel» sin subtipo, y KCNQ1, "
                   "KCNA5 o KCNH2 no comparten sitio. Fijar el subtipo es una "
                   "decisión de quien use el panel."),
}

#: Cómo se lee cada estado en la tabla.
_LEYENDA = {
    "validada": "ofrecible",
    "en_el_panel_por_defecto": "ya en el panel por defecto",
    "sin_estructura_preparable": "sin sitio confirmado",
    "sin_estructura": "sin estructura humana",
}


def markdown(datos: dict) -> str:
    """La tabla del panel, derivada del JSON para que no pueda divergir de él."""
    from collections import Counter

    cuenta = Counter(d["estado"] for d in datos["dianas"])
    lineas = [
        "# Panel de anti-dianas de Bowes et al. 2012",
        "",
        "**Generado por `scripts/build_bowes44_panel.py --write`. No editar a mano.**",
        "",
        f"Referencia: {datos['referencia']}.",
        "",
        "## Qué mide cada fila, y qué no",
        "",
        "- **Sitio**: distancia entre el centroide de la primera pose de redocking y",
        f"  el del ligando cristalizado. Es el criterio de admisión (≤ {SITIO_MAX_A} Å) y",
        "  valida la **estructura**: dice que la caja describe la cavidad de ese ligando.",
        "- **Pose**: RMSD simétrico de esa pose. Mide a **Vina**, no a la estructura, y",
        "  **no decide**. Un ligando alargado puede quedar girado en la misma cavidad:",
        "  ambrisentán en ETA da 3,2 Å de centroide con 4,2 Å de RMSD.",
        "- Ninguna de las dos dice que el sitio sea el **relevante para la reacción",
        "  adversa**. Eso lo adjudica una persona, y por eso todas las filas salen con",
        "  `sitio_adjudicado: false`.",
        "- El ligando de cada fila es un fármaco o un agonista endógeno, nunca un",
        "  cofactor, lípido, detergente o tampón: cuatro filas lo fueron y el redocking",
        "  «confirmaba» el bolsillo equivocado.",
        "",
        "## Estado",
        "",
        "| Estado | Dianas |",
        "|---|---:|",
    ]
    for estado, n in cuenta.most_common():
        lineas.append(f"| {_LEYENDA.get(estado, estado)} (`{estado}`) | {n} |")
    lineas += [
        f"| **total** | **{len(datos['dianas'])}** |",
        "",
        "## Las 44",
        "",
        "| Ensayo | Gen | Familia | Estado | PDB | Ligando | Sitio (Å) | Pose (Å) | Pose ≤2 Å |",
        "|---|---|---|---|---|---|---:|---:|:-:|",
    ]
    for d in datos["dianas"]:
        r = d.get("redock") or {}
        alt = d.get("alternativa_medida") or {}
        pdb = d.get("pdb_id") or "—"
        if alt and not r:
            # Las cifras son de OTRA estructura: decirlo, o la fila mezcla el PDB
            # que se acopla con la medida de una entrada distinta.
            pdb = f"{pdb} (medida: {alt.get('pdb_id')})"
        lig = r.get("ligando") or alt.get("site_ligand") or "—"
        sitio = r.get("distancia_centroides_A", alt.get("distancia_centroides_A"))
        pose = r.get("rmsd_pose1_A", alt.get("rmsd_pose1_A"))
        ok = r.get("pose_reproducida", alt.get("pose_reproducida"))
        lineas.append(
            f"| {d['assay']} | {d.get('gen') or '—'} | {d.get('familia') or '—'} "
            f"| {_LEYENDA.get(d['estado'], d['estado'])} | {pdb} | {lig} "
            f"| {'—' if sitio is None else f'{sitio:.2f}'} "
            f"| {'—' if pose is None else f'{pose:.2f}'} "
            f"| {'' if ok is None else ('sí' if ok else 'no')} |")
    sin = [d for d in datos["dianas"]
           if d["estado"] in ("sin_estructura", "sin_estructura_preparable")]
    if sin:
        lineas += ["", "## Las que no entran, y por qué", ""]
        for d in sin:
            lineas.append(f"- **{d['assay']}** ({d.get('gen') or '—'}): {d.get('motivo') or '—'}")
    return "\n".join(lineas) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 2)[1])
    modo = parser.add_mutually_exclusive_group(required=True)
    modo.add_argument("--write", action="store_true")
    modo.add_argument("--check", action="store_true")
    args = parser.parse_args()
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    datos = construir()
    texto = json.dumps(datos, ensure_ascii=False, indent=1) + "\n"
    doc = markdown(datos)
    if args.write:
        DESTINO.write_text(texto, encoding="utf-8", newline="\n")
        DOC.write_text(doc, encoding="utf-8", newline="\n")
        from collections import Counter
        print(f"Generado: {DESTINO.relative_to(RAIZ)} y {DOC.relative_to(RAIZ)} — "
              f"{dict(Counter(d['estado'] for d in datos['dianas']))}")
        return 0
    for ruta, esperado in ((DESTINO, texto), (DOC, doc)):
        actual = ruta.read_text(encoding="utf-8") if ruta.is_file() else ""
        if actual != esperado:
            print(f"{ruta.relative_to(RAIZ)} desactualizado: ejecuta --write y revisa el diff.")
            return 1
    print("Panel de Bowes 2012 al día.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
