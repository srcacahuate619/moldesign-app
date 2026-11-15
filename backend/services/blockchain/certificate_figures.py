"""Renderers de figuras para certificados PDF.

Los helpers devuelven ``reportlab.platypus.Image`` o ``None``. No calculan
afinidad, contactos ni métricas: transforman datos ya persistidos en figuras
para que ``pdf_generator`` se concentre en la composición del documento.
"""

import io

from core.i18n import translate_text

from rdkit import Chem
from reportlab.lib.units import inch
from reportlab.platypus import Image

#: Resolución mínima de una figura en el papel. Medido en la cápsula de QA (2026-11-11): el perfil de energía y el SHAP salían a
#: 141 dpi, y la molécula 2D y el diagrama de contactos a 160–180 dpi con un rótulo de ~4 pt (F2, F3). 300 dpi de origen dan
#: más de 200 al tamaño con el que se colocan.
DPI_DE_FIGURA = 300

#: Lo que se le exige a una figura de molécula ya recortada, en el tamaño con el que se coloca.
DPI_MINIMO_DE_FIGURA = 220

#: Lado del lienzo con el que RDKit dibuja una molécula (2 px de línea a 400 px; la misma proporción a 800 px).
_LIENZO_RDKIT = 800
_GROSOR_DE_ENLACE_RDKIT = 4


def _recortar_al_contenido(png: bytes, margen_px: int = 24) -> bytes:
    """El PNG sin el borde en blanco o transparente que RDKit deja alrededor de una molécula.

    Una molécula ancha en un lienzo cuadrado ocupa un 60 % de su alto: el resto era blanco que reducía la figura sin añadir
    nada. Recortado, la misma molécula se dibuja un tercio mayor en el mismo ancho del papel.
    """
    from PIL import Image as PILImage
    from PIL import ImageChops

    with PILImage.open(io.BytesIO(png)) as original:
        im = original.convert("RGBA")
    fondo_blanco = PILImage.new("RGBA", im.size, (255, 255, 255, 255))
    sobre_blanco = PILImage.alpha_composite(fondo_blanco, im).convert("RGB")
    caja = ImageChops.difference(sobre_blanco, PILImage.new("RGB", im.size, (255, 255, 255))).getbbox()
    if caja is None:
        return png
    x0, y0, x1, y1 = caja
    caja = (max(0, x0 - margen_px), max(0, y0 - margen_px), min(im.width, x1 + margen_px), min(im.height, y1 + margen_px))
    salida = io.BytesIO()
    sobre_blanco.crop(caja).save(salida, format="PNG", optimize=True)
    return salida.getvalue()


def _imagen_sin_deformar(png: bytes, ancho: float, alto_max: float | None = None) -> Image:
    """`Image` de ReportLab que conserva la proporción del PNG: `ancho` es el que se pide y `alto_max`, el tope.

    Antes cada figura se colocaba en una caja fija sin mirar la proporción de lo que `matplotlib` había recortado (`bbox_inches=
    "tight"`), y salía estirada un 2 % (F3).
    """
    from PIL import Image as PILImage

    with PILImage.open(io.BytesIO(png)) as im:
        px_ancho, px_alto = im.size
    alto = ancho * px_alto / px_ancho
    if alto_max is not None and alto > alto_max:
        alto = alto_max
        ancho = alto * px_ancho / px_alto
    return Image(io.BytesIO(png), width=ancho, height=alto)


def _dibujar_molecula(mol, lienzo: int = _LIENZO_RDKIT, **opciones) -> bytes:
    from rdkit.Chem.Draw import rdMolDraw2D

    d = rdMolDraw2D.MolDraw2DCairo(lienzo, lienzo)
    o = d.drawOptions()
    o.clearBackground = True
    # 2 px a 400 px de lienzo: el grosor del enlace crece con él para que la línea no se afine al ampliar.
    o.bondLineWidth = max(2, round(lienzo / 200))
    for nombre, valor in opciones.pop("opciones", {}).items():
        setattr(o, nombre, valor)
    d.DrawMolecule(mol, **opciones)
    d.FinishDrawing()
    return d.GetDrawingText()


def _figura_de_molecula(mol, ancho: float, alto_max: float, **opciones) -> Image:
    """La molécula dibujada, recortada y colocada sin deformar, con al menos `DPI_MINIMO_DE_FIGURA` en el papel.

    El recorte quita el blanco del lienzo, así que cuántos píxeles quedan depende de la molécula: se aumenta el lienzo hasta
    que el dibujo ya recortado tenga los píxeles que su tamaño en el papel pide.
    """
    from PIL import Image as PILImage

    for lienzo in (_LIENZO_RDKIT, 1200, 1600, 2400):
        recortado = _recortar_al_contenido(_dibujar_molecula(mol, lienzo, **dict(opciones)))
        with PILImage.open(io.BytesIO(recortado)) as im:
            px_ancho, px_alto = im.size
        ancho_final = min(ancho, alto_max * px_ancho / px_alto)
        if px_ancho >= ancho_final / 72 * DPI_MINIMO_DE_FIGURA:
            break
    return _imagen_sin_deformar(recortado, ancho, alto_max)


def get_2d_image(smiles: str, width=2.5 * inch, height=2.5 * inch):
    mol = Chem.MolFromSmiles(smiles)
    if not mol:
        return None
    return _figura_de_molecula(mol, width, height)


def generate_energy_profile_plot(poses: list[dict], width=4.5 * inch, height=2.0 * inch):
    if not poses:
        return None
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        plt.clf()
        plt.close("all")

        ranks = [p.get("rank") for p in poses if p.get("rank") is not None]
        affinities = [p.get("affinity") for p in poses if p.get("affinity") is not None]

        if not ranks or not affinities:
            return None

        fig, ax = plt.subplots(figsize=(6.5, 2.5), dpi=DPI_DE_FIGURA)
        ax.plot(ranks, affinities, marker="o", color="#3b82f6", linewidth=2, markersize=5, markerfacecolor="#1e3a8a")

        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_color("#cbd5e1")
        ax.spines["bottom"].set_color("#cbd5e1")
        ax.tick_params(axis="both", colors="#475569", labelsize=8)

        ax.set_ylabel(translate_text("Afinidad (kcal/mol)"), fontsize=8, color="#475569")
        ax.set_xlabel(translate_text("Pose (posición)"), fontsize=8, color="#475569")
        ax.set_xticks(ranks)
        ax.grid(True, linestyle=":", alpha=0.6, color="#cbd5e1")

        plt.tight_layout()

        buf = io.BytesIO()
        plt.savefig(buf, format="png", bbox_inches="tight", transparent=True, dpi=DPI_DE_FIGURA)
        plt.close(fig)
        return _imagen_sin_deformar(buf.getvalue(), width, height)
    except Exception:
        return None


def generate_shap_image(shap_values: dict, width=6.8 * inch, height=2.8 * inch):
    if not shap_values:
        return None
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        plt.clf()
        plt.close("all")

        sorted_items = sorted(shap_values.items(), key=lambda x: abs(x[1]))[-8:]
        features = [item[0] for item in sorted_items]
        values = [item[1] for item in sorted_items]

        labels = [f.replace("_", " ").title() for f in features]
        colors_list = ["#10b981" if v > 0 else "#f43f5e" for v in values]

        fig, ax = plt.subplots(figsize=(6.5, 2.8), dpi=DPI_DE_FIGURA)
        ax.barh(labels, values, color=colors_list, height=0.6)
        ax.axvline(0, color="#64748b", linewidth=0.8, linestyle="--")

        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_color("#cbd5e1")
        ax.spines["bottom"].set_color("#cbd5e1")
        ax.tick_params(axis="both", colors="#475569", labelsize=8)

        ax.set_xlabel(translate_text("Contribución a Afinidad (SHAP Value)"), fontsize=8, color="#475569")

        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format="png", bbox_inches="tight", transparent=True, dpi=DPI_DE_FIGURA)
        plt.close(fig)
        return _imagen_sin_deformar(buf.getvalue(), width, height)
    except Exception:
        return None


def generate_gnn_attention_image(smiles: str, attention: list[float], width=6.8 * inch, height=3.8 * inch):
    if not attention:
        return None
    mol = Chem.MolFromSmiles(smiles)
    if not mol:
        return None
    try:
        num_atoms = mol.GetNumAtoms()
        weights = list(attention)
        if len(weights) < num_atoms:
            weights += [0.0] * (num_atoms - len(weights))
        else:
            weights = weights[:num_atoms]

        from rdkit.Chem.Draw import SimilarityMaps, rdMolDraw2D

        d = rdMolDraw2D.MolDraw2DCairo(800, 450)
        opts = d.drawOptions()
        opts.clearBackground = True
        SimilarityMaps.GetSimilarityMapFromWeights(mol, weights, draw2d=d)
        d.FinishDrawing()
        png_data = d.GetDrawingText()

        buf = io.BytesIO(png_data)
        return Image(buf, width=width, height=height)
    except Exception:
        return None


def primera_pose(ligand_sdf: str | None):
    """La primera pose del SDF, leída como la lee el mapa de contactos.

    Los índices de átomo que llevan los contactos (`ligand_atoms`) son los de
    esta molécula; por eso el mapa y el diagrama la leen con la MISMA llamada.
    """
    if not ligand_sdf:
        return None
    suppl = Chem.SDMolSupplier()
    suppl.SetData(ligand_sdf)
    return next((m for m in suppl if m is not None), None)


def notas_de_contacto(contacts: list[dict], num_atoms: int) -> dict[int, str]:
    """Átomo → rótulo, sólo para los átomos que cada contacto nombra.

    SCI-A-057: antes se rotulaba con el primer puente de hidrógeno CUALQUIER N, O,
    F o S del ligando, lo formara o no. Un contacto sin `ligand_atoms` no se
    localiza en ningún átomo: la tabla lo da por residuo.
    """
    notas: dict[int, list[str]] = {}
    for contact in contacts:
        if "H-Bond" not in contact["type"] and "Salt Bridge" not in contact["type"]:
            continue
        rotulo = f"{contact['residue'].split()[0]} ({contact['distance']})"
        for i in contact.get("ligand_atoms") or ():
            if isinstance(i, int) and 0 <= i < num_atoms and rotulo not in notas.setdefault(i, []):
                notas[i].append(rotulo)
    return {i: ", ".join(r) for i, r in notas.items()}


def _rotulo_dibujable(nota: str) -> str:
    """El rótulo sin «Å»: la fuente de RDKit no tiene ese glifo y lo pintaba como un hueco («3.10 )»).

    La unidad no se pierde: la figura lleva una leyenda que la dice (`LEYENDA_DEL_DIAGRAMA`), y la tabla de al lado imprime
    cada distancia con ella.
    """
    return nota.replace(" Å", "").replace("Å", "")


#: Lo que dice un rótulo del diagrama. Va bajo la figura, en el idioma del documento.
LEYENDA_DEL_DIAGRAMA = "Rótulo: residuo (distancia al átomo marcado, en Å)."


def generate_2d_interaction_diagram(smiles: str, contacts: list[dict], width=2.4 * inch, height=2.4 * inch,
                                    pose_sdf: str | None = None) -> Image:
    """Renderiza contactos recibidos; no los calcula ni los reclasifica.

    Los contactos se localizan en átomos sólo si se dibuja la pose de la que salen
    sus índices (`pose_sdf`). Desde el SMILES los índices no corresponden, así que
    se dibuja el ligando sin localizar ninguno.

    `width` y `height` son la caja en puntos en la que cabe la figura: se conserva su proporción, y se dibuja a
    `DPI_DE_FIGURA` con los rótulos en una letra que a ese tamaño se lee (en 400 px a 180 pt medían ~4 pt).
    """
    pose = primera_pose(pose_sdf)
    mol = Chem.Mol(pose) if pose is not None else Chem.MolFromSmiles(smiles)
    if not mol:
        return None
    try:
        from rdkit.Chem import rdDepictor

        mol.RemoveAllConformers()
        rdDepictor.Compute2DCoords(mol)

        atom_notes = notas_de_contacto(contacts, mol.GetNumAtoms()) if pose is not None else {}
        highlight_atoms = list(atom_notes)
        highlight_colors = {i: (0.2, 0.8, 0.2) for i in atom_notes}

        for idx, note in atom_notes.items():
            mol.GetAtomWithIdx(idx).SetProp("atomNote", _rotulo_dibujable(note))

        return _figura_de_molecula(
            mol, width, height, highlightAtoms=highlight_atoms, highlightAtomColors=highlight_colors,
            opciones={"annotationFontScale": 0.8, "baseFontSize": 0.7},
        )
    except Exception:
        return None
