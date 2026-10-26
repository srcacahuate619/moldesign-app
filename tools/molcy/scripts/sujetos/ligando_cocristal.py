"""SUJETO: el ligando cocristalizado del propio deposito, con sus contactos.

Es el unico que el exportador respalda hoy: sale de `geometry/site_ligand.pdb`,
extraido de los registros HETATM del PDB.

Ademas del ligando dibuja sus **contactos polares medidos** contra el receptor.
No es un PLIF —no hay protonacion ni angulos— y va rotulado como lo que es. El
contrato lo permite en `angulo_puente_hidrogeno.permitido_en_su_lugar`: «la
linea punteada del contacto y su distancia en A, sin H».
"""
from __future__ import annotations

import collections
import math
import tempfile
from pathlib import Path

import bl_ext.blender_org.molecularnodes as mn
from mathutils import Vector

from nucleo import arte, contactos
from nucleo.ciencia import ESCALA
from variables.sujeto import Contexto, Montado, SujetoNoDisponible

ID = "ligando_cocristal"
DESCRIPCION = "El ligando cocristalizado del deposito (HETATM) y sus contactos medidos."

CORTE_ENLACE_A = 1.95
MAX_CONTACTOS = 3          # mas de tres lineas tapan el bolsillo
MAX_ETIQUETAS_DISTANCIA = 2


def disponible(paq) -> tuple[bool, str]:
    if not paq.tiene_ligando:
        return False, ("el paquete no trae site_ligand.pdb: esta estructura no "
                       "tiene ligando cocristalizado (109 de los 380)")
    return True, f"codigo HET {paq.codigo_het or '?'}"


def copia_del_sitio(ruta_pdb, objetivo_a, media_caja_a: float):
    """Se queda con la copia del ligando que esta en la caja adjudicada.

    `site_ligand.pdb` sale de los HETATM de la UNIDAD BIOLOGICA, asi que en un
    homotetramero trae las cuatro copias. Medido: en 1HWK las cuatro copias de
    la estatina se reparten 33.5 A y el centroide del conjunto cae a 26.4 A del
    objetivo; en 1CX2, 53.1 A y 33.6 A. Cargarlas todas dispara la distancia de
    primer plano por encima de la del plano general y **la camara se aleja en
    vez de acercarse**. En ambos casos la copia de la cadena A esta a 0.0 A del
    objetivo y las otras tres a 36-72 A.

    Devuelve (ruta_temporal, elegida, descartadas) o (None, None, []) si
    ninguna copia cae dentro de la caja.
    """
    grupos = collections.defaultdict(list)
    cabecera = []
    for L in open(ruta_pdb, encoding="utf-8", errors="ignore"):
        if L.startswith(("ATOM", "HETATM")):
            grupos[(L[17:20].strip(), L[21], L[22:26].strip())].append(L)
        elif L.startswith(("CRYST", "REMARK", "HEADER")):
            cabecera.append(L)
    if len(grupos) <= 1:
        return None, None, []

    def centro(lineas):
        P = [(float(x[30:38]), float(x[38:46]), float(x[46:54])) for x in lineas]
        return [sum(v) / len(P) for v in zip(*P)]

    medidas = {k: math.dist(centro(v), list(objetivo_a)) for k, v in grupos.items()}
    elegida = min(medidas, key=medidas.get)
    if medidas[elegida] > media_caja_a:
        return None, None, [{"copia": "/".join(k), "dist_a": round(d, 1)}
                            for k, d in sorted(medidas.items(), key=lambda x: x[1])]

    tmp = Path(tempfile.gettempdir()) / f"sitio_{'_'.join(elegida)}.pdb"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.writelines(cabecera)
        fh.writelines(grupos[elegida])
        fh.write("END\n")
    descartadas = [{"copia": "/".join(k), "dist_a": round(d, 1)}
                   for k, d in sorted(medidas.items(), key=lambda x: x[1])
                   if k != elegida]
    return tmp, {"copia": "/".join(elegida), "dist_a": round(medidas[elegida], 1)}, descartadas


def inferir_enlaces(obj, corte_a: float = CORTE_ENLACE_A) -> int:
    """Conectividad por distancia, porque el PDB no la trae.

    Los HETATM no llevan CONECT ni ordenes de enlace, asi que Molecular Nodes
    dibuja una nube de esferas sueltas. Inferir la CONECTIVIDAD por distancia es
    estandar; lo que no se puede inferir son los ORDENES (aromaticos, dobles),
    asi que se dibujan todos simples y queda declarado.
    """
    me = obj.data
    if len(me.edges) or len(me.vertices) < 2:
        return 0
    corte = corte_a * ESCALA
    P = [v.co for v in me.vertices]
    pares = []
    for i in range(len(P)):
        for j in range(i + 1, len(P)):
            d = P[i] - P[j]
            if abs(d.x) > corte or abs(d.y) > corte or abs(d.z) > corte:
                continue
            if d.length <= corte:
                pares.append((i, j))
    if not pares:
        return 0
    me.edges.add(len(pares))
    me.edges.foreach_set("vertices", [x for p in pares for x in p])
    me.update()
    if "bond_type" not in me.attributes:
        me.attributes.new("bond_type", "INT", "EDGE")
    a = me.attributes["bond_type"].data
    for e in range(len(me.edges)):
        a[e].value = 1
    return len(pares)


def cargar(paq, ctx: Contexto | None = None) -> Montado:
    ok, razon = disponible(paq)
    if not ok:
        raise SujetoNoDisponible(razon)
    ctx = ctx or Contexto()

    m = Montado()
    ruta = paq.ruta("site_ligand")
    media_caja = max(paq.caja_a) / 2.0
    tmp, elegida, descartadas = copia_del_sitio(ruta, paq.objetivo_a, media_caja)
    if descartadas and tmp is None:
        raise SujetoNoDisponible(
            "ninguna copia del ligando cae dentro de la caja de acoplamiento "
            f"(media caja {media_caja:.1f} A); la mas cercana a "
            f"{descartadas[0]['dist_a']} A")
    if tmp is not None:
        ruta = tmp
        m.medido["copia_elegida"] = elegida
        m.medido["copias_descartadas"] = descartadas
        m.notas.append(
            f"site_ligand.pdb traia {len(descartadas) + 1} copias del ligando "
            f"(unidad biologica); se usa la de la caja adjudicada "
            f"({elegida['copia']}, a {elegida['dist_a']} A del objetivo) y se "
            f"descartan las demas, a "
            f"{', '.join(str(d['dist_a']) for d in descartadas)} A.")
    if paq.es_cofactor:
        m.notas.append(
            f"AVISO: el ligando del sitio designado es {paq.codigo_het}, que es "
            "un COFACTOR, no un farmaco. El video es honesto —esa molecula esta "
            "en la caja adjudicada— pero la adjudicacion del sitio merece "
            "revision en moldesign-build. En 1CX2 (COX-2) el inhibidor real es "
            "SC-558 y el sitio adjudicado es el del hemo.")
        m.medido["ligando_es_cofactor"] = paq.codigo_het

    lig = mn.Molecule.load(str(ruta), name=f"{paq.pdb_id}_ligando")
    n = inferir_enlaces(lig.object)
    if n:
        m.notas.append(
            f"ligando: {n} enlaces inferidos por distancia (<{CORTE_ENLACE_A} A). "
            "site_ligand.pdb viene de HETATM y no trae ordenes de enlace; se "
            "dibujan todos simples. Para quimica correcta hace falta el SDF "
            "ideal del CCD de ese codigo HET.")
    lig.add_style("ball_and_stick", name="lig")
    mat = arte.material_del_estilo(lig, "Ball and Stick", f"{paq.pdb_id}_Ligando")
    arte.realzar_protagonista(mat)

    m.objetos.append(lig.object)
    if mat:
        m.materiales.append(mat)
    m.anclas.append(("lig", paq.codigo_het or "Ligando",
                     arte.centro_evaluado(lig.object)))
    pts = arte.puntos_evaluados(lig.object)
    m.dianas += pts[:: max(1, len(pts) // 120)]

    # ── contactos polares medidos ────────────────────────────────────────
    if ctx.receptor is None or ctx.receptor.molecula is None:
        m.notas.append("sin contexto de receptor: no se midieron contactos")
        return m

    todos = contactos.medir(
        ctx.receptor.molecula, lig, cerca_de=ctx.pivote or None,
        nombres=contactos.mapa_de_residuos(paq.ruta("prepared")),
        cadenas=(paq.cadenas_conservadas or [paq.cadena_principal]))
    presentados = [h.numero for h in (ctx.receptor.hotspots or [])]
    elegidos = contactos.sin_duplicar_residuo(todos, MAX_CONTACTOS,
                                              preferidos=presentados)
    if not elegidos:
        m.notas.append("no se midio ningun contacto polar N/O entre "
                       f"{contactos.MIN_A} y {contactos.MAX_A} A")
        m.medido["contactos"] = []
        return m

    mat_linea = arte.copiar_material(ctx.arte["HBond_EGFR_Gold"],
                                     f"{paq.pdb_id}_Contacto")
    arte.subir_emision(mat_linea, 6.0)   # tiene que ganar al carton iluminado
    for i, c in enumerate(elegidos):
        obj = contactos.malla_punteada(f"Contacto_{i}", c.a, c.b, mat_linea)
        if obj is not None:
            m.secundarios.append(obj)
    m.materiales_secundarios.append(mat_linea)

    for i, c in enumerate(elegidos[:MAX_ETIQUETAS_DISTANCIA]):
        m.anclas.append((f"dist{i}", c.etiqueta, c.medio))

    m.medido["contactos"] = [
        {"resname": c.resname, "resid": c.resid, "cadena": c.cadena,
         "distancia_a": round(c.distancia_a, 2)} for c in elegidos]
    m.medido["contactos_candidatos"] = len(todos)
    m.medido["residuos_de_contacto"] = sorted({c.resid for c in elegidos})
    coinciden = sorted({c.resid for c in elegidos} & set(presentados))
    m.medido["contactos_sobre_hotspots_presentados"] = coinciden
    m.notas.append(
        f"{len(elegidos)} contacto(s) polar(es) dibujado(s) de {len(todos)} "
        f"medidos entre atomos pesados N/O a {contactos.MIN_A}-{contactos.MAX_A} A. "
        "NO es un PLIF: sin protonar, sin angulos donante-H-aceptor y sin tipado "
        "quimico. Es medicion geometrica directa sobre las coordenadas del "
        "paquete, que es lo que el contrato permite dibujar.")
    return m
