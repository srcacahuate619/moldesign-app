"""Interacciones ligando–receptor que se dibujan y se rotulan: polares y apolares.

Reúne lo que `contactos` mide y lo que el vídeo enseña, para que una pose
dockeada (Resultado, Búsqueda) tenga las mismas líneas y los mismos rótulos de
distancia que tenía el ligando cocristalizado:

- **polar**: proximidad N/O entre 2,4 y 3,5 Å; línea punteada.
- **apolar**: carbono apolar del ligando contra una cadena lateral, 2,8–4,5 Å;
  línea de trazos.

Cada clase tiene su color, pero ningún texto lo nombra: el rótulo dice POLAR o
APOLAR (el nombre de un color puede leerse como el de un elemento).

Se miden contra TODOS los residuos del bolsillo, no sólo contra los hotspots del
catálogo (muchos receptores no traen ninguno y la escena salía sin una sola
interacción); los hotspots que sí existan pasan primero (`preferidos`). Un
contacto por residuo y clase, como en el motor original.

Lo que NO es: no hay protonación ni ángulos donante–H–aceptor, así que «polar» es
una proximidad geométrica y no un puente de hidrógeno confirmado, y «apolar» es
compatible con asociación hidrofóbica, no una energía. El rótulo dice exactamente
eso (POLAR / APOLAR + la distancia medida) y las notas del acta lo declaran.
"""
from __future__ import annotations

#: Por clase y por pose: más líneas tapan el bolsillo y los rótulos no caben.
MAX_POR_TIPO = 3
#: Entorno del ligando donde se buscan átomos del receptor, en Å.
RADIO_A = 12.0

#: Tamaño del rótulo de una interacción respecto al de los demás rótulos 3D (que se calibraron
#: para una cámara más lejana): son dos líneas por interacción y hasta seis por pose.
ESCALA_ROTULO = 0.36
#: El rótulo del sujeto («Vina top-1») y el de un hotspot, en la misma escala: a 1.0 el del
#: sujeto ocupaba en vertical medio ancho de cuadro y las interacciones caían encima.
ESCALA_SUJETO = 0.50
ESCALA_HOTSPOT = 0.40

#: Colores de los rótulos, iguales a los de sus líneas (ámbar y turquesa); sólo en el render.
#: El texto sólo emite (`rotulos.tintar`): así conserva el tono en vez de blanquearse.
COLOR_POLAR = (1.0, 0.72, 0.20)
COLOR_APOLAR = (0.20, 0.82, 0.84)
#: Un hotspot no es una interacción: neutro, sin el color de ninguna clase.
COLOR_HOTSPOT = (0.86, 0.89, 0.93)
#: Emisión de las líneas punteadas. A 6.0 y 4.5 (antes) AgX las llevaba al blanco y la
#: polar y la apolar dejaban de distinguirse entre sí y de sus rótulos.
EMISION_LINEA_POLAR, EMISION_LINEA_APOLAR = 3.0, 2.6


def mapa_de_residuos(ruta_pdb) -> dict[tuple[str, int], str]:
    """{(cadena, res_id): RESNAME} leído del PDB.

    Molecular Nodes guarda `res_name` y `chain_id` como enteros, así que el
    nombre real se lee del archivo. SCI-A-030: antes la clave era sólo el
    número, y el primero que aparecía ganaba; en un receptor de dos cadenas con
    la misma numeración, el contacto con B:ASP1 se rotulaba con el nombre de
    A:ALA1. Ahora la clave lleva la cadena (columna 22). Si un mismo (cadena,
    número) trae dos nombres —códigos de inserción, que Molecular Nodes no
    distingue—, el nombre no es inequívoco y queda «?».

    Puro (sin bpy): se puede probar sin Blender.
    """
    out: dict[tuple[str, int], str] = {}
    ambiguos: set[tuple[str, int]] = set()
    try:
        with open(ruta_pdb, encoding="utf-8", errors="ignore") as fh:
            for L in fh:
                if not L.startswith(("ATOM", "HETATM")):
                    continue
                try:
                    clave = (L[21:22] or " ", int(L[22:26]))
                except ValueError:
                    continue
                nombre = L[17:20].strip()
                if clave in out and out[clave] != nombre:
                    ambiguos.add(clave)
                out.setdefault(clave, nombre)
    except OSError:
        pass
    for clave in ambiguos:
        out[clave] = "?"
    return out


def nombre_de_residuo(nombres, cadena: str, numero: int) -> str:
    """El nombre del residuo de ESA cadena y número, o «?» si no consta o es ambiguo."""
    return (nombres or {}).get((cadena, numero), "?")


def medir(receptor_mol, sujeto_mol, centro, *, nombres=None, cadenas=None,
          preferidos=(), max_por_tipo: int = MAX_POR_TIPO):
    """(elegidos, n_polares_medidos, n_apolares_medidos) de un ligando en su pose."""
    from . import contactos          # importa bpy: sólo cuando se mide, no al rotular
    polares = contactos.medir(receptor_mol, sujeto_mol, cerca_de=centro,
                              radio_a=RADIO_A, nombres=nombres, cadenas=cadenas)
    apolares = contactos.medir_hidrofobicos(receptor_mol, sujeto_mol, cerca_de=centro,
                                            radio_a=RADIO_A, nombres=nombres,
                                            cadenas=cadenas)
    elegidos = contactos.elegir_por_tipo(polares, apolares, max_por_tipo,
                                         preferidos=preferidos)
    return elegidos, len(polares), len(apolares)


def materiales_de_linea(plantilla: dict, prefijo: str):
    """(polar, apolar): los materiales de las líneas punteadas, con la emisión de la clase."""
    from . import arte, contactos      # importan bpy: sólo al montar la escena
    polar = arte.copiar_material(plantilla["HBond_EGFR_Gold"], f"{prefijo}ContactoPolar")
    arte.subir_emision(polar, EMISION_LINEA_POLAR)
    apolar = contactos.material_hidrofobico(f"{prefijo}ContactoApolar")
    arte.subir_emision(apolar, EMISION_LINEA_APOLAR)
    return polar, apolar


def tipo(c) -> str:
    return "apolar" if c.tipo == "hidrofobico" else "polar"


def color(c):
    return COLOR_APOLAR if c.tipo == "hidrofobico" else COLOR_POLAR


def texto(c, con_cadena: bool = False) -> str:
    """Rótulo de una interacción: residuo, clase y distancia medida, en dos líneas.

    Sin tildes ni signos raros salvo la Å: es la tipografía del resto de rótulos.
    """
    nombre = (c.resname if c.resname and c.resname != "?" else "RES").upper()
    cadena = f":{c.cadena}" if con_cadena and c.cadena not in ("", "-1") else ""
    return f"{nombre}{c.resid}{cadena}\n{tipo(c).upper()}  {c.etiqueta}"


def registro(c) -> dict:
    """Lo que queda en el acta de cada interacción dibujada."""
    return {"tipo": tipo(c), "resname": c.resname, "resid": c.resid,
            "cadena": c.cadena, "distancia_a": round(c.distancia_a, 2)}


NOTA = ("Interacciones medidas por distancia sobre las coordenadas del paquete: polar = "
        "proximidad N/O de 2.4 a 3.5 A (linea punteada); apolar = carbono apolar del ligando contra "
        "cadena lateral de 2.8 a 4.5 A (linea de trazos). Un contacto por residuo y clase. NO es un "
        "PLIF: sin protonar, sin angulos donante-H-aceptor; no son puentes de hidrogeno "
        "confirmados ni energias de union.")
