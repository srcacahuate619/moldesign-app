"""El sello quemado en el fotograma.

Por defecto se quema el CREDITO de marca. La procedencia verificable —el
pdb_id y el git_sha corto— vive en el acta `build_*.json` y en el
`MANIFEST.sha256`, que viajan con el archivo, y la esquina inferior del cuadro
ya identifica la estructura. `texto()` queda como nota tecnica para quien
prefiera quemarla en vez del credito.

Se usa el sellado NATIVO de Blender y no un objeto de texto en 3D. Un texto
colgado de la camara tiene dos problemas que no compensan: hay que ponerlo muy
cerca para que no lo tape la geometria, y entonces la profundidad de campo
—enfocada al sitio activo, a 3.4 unidades— lo pulveriza. El sellado nativo se
quema sobre la imagen ya renderizada: siempre nitido, nunca ocluido, y ademas
es exactamente para lo que existe.
"""
from __future__ import annotations

import bpy

#: Lo que se quema arriba a la izquierda.
CREDITO = "Video generado por MolDesign"


def texto(paq, ancho: int = 1920) -> str:
    """El nombre del receptor solo cabe en cuadro ancho.

    En 9:16 el sello se parte en dos lineas y estorba, asi que ahi se queda en
    identificador y version, que es lo que hace verificable el video.
    """
    p = paq.procedencia or {}
    sha = (p.get("git_sha") or "")[:7]
    sucio = "+" if p.get("arbol_sucio") else ""
    partes = [paq.pdb_id]
    if ancho >= 1600 and paq.nombre and paq.nombre != paq.pdb_id:
        # Algunos titulos del PDB son una frase entera ("CYCLOOXYGENASE-2
        # (PROSTAGLANDIN SYNTHASE-2) COMPLEXED WITH A SELECTIVE...") y se comen
        # el ancho del cuadro. Se corta por el primer parentesis o coma.
        nombre = paq.nombre.split("(")[0].split(",")[0].strip()
        if len(nombre) > 34:
            nombre = nombre[:33].rstrip() + "…"
        partes.append(nombre)
    if sha:
        partes.append(f"{sha}{sucio}")
    return "  ·  ".join(partes)


def sellar(paq, formato, nota: str | None = None) -> str | None:
    """Configura el sellado nativo. Devuelve el texto grabado, o None."""
    r = bpy.context.scene.render
    if not formato.sello_procedencia:
        r.use_stamp = False
        return None
    nota = nota or texto(paq, formato.ancho)
    r.use_stamp = True
    r.use_stamp_note = True
    r.stamp_note_text = nota
    # solo la nota: nada de fecha, fotograma, nombre de escena ni de camara
    for attr in ("use_stamp_date", "use_stamp_time", "use_stamp_render_time",
                 "use_stamp_frame", "use_stamp_frame_range", "use_stamp_scene",
                 "use_stamp_camera", "use_stamp_lens", "use_stamp_filename",
                 "use_stamp_marker", "use_stamp_sequencer_strip",
                 "use_stamp_memory", "use_stamp_hostname"):
        if hasattr(r, attr):
            setattr(r, attr, False)
    r.use_stamp_labels = False
    # En pixeles de SALIDA: a resolucion reducida (borrador al 50 %) el sello
    # salia el doble de grande respecto al cuadro.
    r.stamp_font_size = max(8, int(formato.alto * 0.016 * formato.escala_render / 100))
    r.stamp_foreground = (0.88, 0.62, 0.30, 0.72)   # el naranja de las etiquetas
    r.stamp_background = (0.0, 0.0, 0.0, 0.0)
    return nota
