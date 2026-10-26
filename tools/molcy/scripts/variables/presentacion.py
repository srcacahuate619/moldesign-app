"""Ocho controles cosméticos, separados de fuentes y mediciones científicas."""
from __future__ import annotations

import re

SCHEMA = "moldesign.presentacion/1"


def validar(datos):
    if not isinstance(datos, dict):
        raise ValueError("presentacion debe ser un objeto")
    permitidos = {"schema", "titulo", "color_receptor", "color_residuos",
                  "colores_lineas", "receptor", "muestra_anterior", "etiquetas", "contactos"}
    if set(datos) - permitidos:
        raise ValueError("campos de presentación desconocidos: " + ", ".join(sorted(set(datos) - permitidos)))
    if datos.get("schema", SCHEMA) != SCHEMA:
        raise ValueError("esquema de presentación desconocido")
    titulo = datos.get("titulo")
    if titulo is not None:
        if not isinstance(titulo, str) or not 1 <= len(titulo.strip()) <= 80 or any(ord(c) < 32 for c in titulo):
            raise ValueError("el alias del título debe tener de 1 a 80 caracteres sin controles")
        titulo = titulo.strip()

    def color(v):
        if v is not None and (not isinstance(v, str) or not re.fullmatch(r"#[0-9A-Fa-f]{6}", v)):
            raise ValueError("un color debe ser #RRGGBB o null para automático")
        return v.upper() if v else None

    lineas = datos.get("colores_lineas")
    if lineas is None:
        lineas = {}
    if not isinstance(lineas, dict) or set(lineas) - {"polar", "apolar"}:
        raise ValueError("colores_lineas sólo admite polar y apolar")
    modo = datos.get("receptor", "automatico")
    if modo not in {"automatico", "visible", "oculto"}:
        raise ValueError("visibilidad del receptor desconocida")
    out = {"schema": SCHEMA, "titulo": titulo,
           "color_receptor": color(datos.get("color_receptor")),
           "color_residuos": color(datos.get("color_residuos")),
           "colores_lineas": {k: color(lineas.get(k)) for k in ("polar", "apolar")},
           "receptor": modo}
    for k in ("muestra_anterior", "etiquetas", "contactos"):
        valor = datos.get(k, True)
        if type(valor) is not bool:
            raise ValueError(f"{k} debe ser booleano")
        out[k] = valor
    return out


def validar_ensamble(datos):
    if not isinstance(datos, dict) or set(datos) - {"variante", "conformero"}:
        raise ValueError("ajustes de ensamble fluido desconocidos")
    if datos.get("variante") not in {"lenta", "detallada"}:
        raise ValueError("variante de ensamble fluido desconocida")
    out = {"variante": datos["variante"]}
    if "conformero" in datos:
        if type(datos["conformero"]) is not int or datos["conformero"] < 0:
            raise ValueError("el ID del conformero debe ser un entero no negativo")
        out["conformero"] = datos["conformero"]
    return out


def rgba(hexadecimal):
    """Color sRGB de la UI a componentes lineales para los materiales de Blender."""
    canales = [int(hexadecimal[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    return tuple(c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4 for c in canales) + (1.0,)


def tintar_material(material, hexadecimal):
    if material is None or hexadecimal is None:
        return
    valor = rgba(hexadecimal)
    material.diffuse_color = valor
    nt = getattr(material, "node_tree", None)
    if nt is None:
        return
    for nodo in nt.nodes:
        nombres = ("Base Color", "Emission Color") if nodo.type == "BSDF_PRINCIPLED" else (
            ("Color",) if nodo.type == "EMISSION" else ())
        for nombre in nombres:
            entrada = nodo.inputs.get(nombre)
            if entrada is not None:
                for enlace in list(entrada.links):
                    nt.links.remove(enlace)
                entrada.default_value = valor


def aplicar_colores_interaccion(datos):
    """Antes de montar: líneas y rótulos nacen con la misma leyenda de clase."""
    from nucleo import interacciones
    colores = datos["colores_lineas"]
    if colores["polar"]:
        interacciones.COLOR_POLAR = rgba(colores["polar"])[:3]
    if colores["apolar"]:
        interacciones.COLOR_APOLAR = rgba(colores["apolar"])[:3]


def aplicar_montado(datos, rec, montado):
    """Después de crear varillas; no modifica geometría ni valores medidos."""
    tintar_material(rec.mat_cartoon, datos["color_receptor"])
    tintar_material(rec.mat_hotspots, datos["color_residuos"])
    for material, clase in zip(montado.extra.get("materiales_contacto") or montado.materiales_secundarios, ("polar", "apolar")):
        tintar_material(material, datos["colores_lineas"][clase])
    montado.extra["contactos_visibles"] = datos["contactos"]
    montado.extra["muestra_anterior_visible"] = datos["muestra_anterior"]
    montado.medido["presentacion"] = datos
    if datos["receptor"] == "oculto":
        rec.objeto.hide_render = True
        rec.objeto.hide_viewport = True
    elif datos["receptor"] == "visible":
        rec.objeto.hide_render = False
        rec.objeto.hide_viewport = False
    if not datos["muestra_anterior"]:
        import bpy
        for muestra in montado.extra.get("instantaneas") or []:
            nombre = muestra.get("fantasma")
            if nombre:
                obj = bpy.data.objects.get(nombre)
                if obj is not None:
                    bpy.data.objects.remove(obj, do_unlink=True)
                muestra["fantasma"] = None


def fijar_alias_en_cuadro(objeto, camara, frames, lente_referencia):
    """Mantiene el alias en píxeles al cambiar la lente, con claves horneadas."""
    import bpy
    from nucleo.horneado import hornear
    sc = bpy.context.scene
    posicion, escala = tuple(objeto.location), tuple(objeto.scale)
    factores = []
    for frame in frames:
        sc.frame_set(frame)
        factores.append(lente_referencia / camara.data.lens)
    for i in (0, 1):
        hornear(objeto, "location", i, frames, [posicion[i] * f for f in factores])
    for i in range(3):
        hornear(objeto, "scale", i, frames, [escala[i] * f for f in factores])
    sc.frame_set(1)
