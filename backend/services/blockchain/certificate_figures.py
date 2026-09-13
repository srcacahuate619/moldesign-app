"""Renderers de figuras para certificados PDF.

Los helpers devuelven ``reportlab.platypus.Image`` o ``None``. No calculan
afinidad, contactos ni métricas: transforman datos ya persistidos en figuras
para que ``pdf_generator`` se concentre en la composición del documento.
"""

import io

from rdkit import Chem
from rdkit.Chem import Draw
from reportlab.lib.units import inch
from reportlab.platypus import Image


def get_2d_image(smiles: str, width=2.5 * inch, height=2.5 * inch):
    mol = Chem.MolFromSmiles(smiles)
    if not mol:
        return None
    img = Draw.MolToImage(mol, size=(400, 400))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return Image(buf, width=width, height=height)


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

        fig, ax = plt.subplots(figsize=(6.5, 2.5), dpi=150)
        ax.plot(ranks, affinities, marker="o", color="#3b82f6", linewidth=2, markersize=5, markerfacecolor="#1e3a8a")

        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_color("#cbd5e1")
        ax.spines["bottom"].set_color("#cbd5e1")
        ax.tick_params(axis="both", colors="#475569", labelsize=8)

        ax.set_ylabel("Afinidad (kcal/mol)", fontsize=8, color="#475569")
        ax.set_xlabel("Pose (Rank)", fontsize=8, color="#475569")
        ax.set_xticks(ranks)
        ax.grid(True, linestyle=":", alpha=0.6, color="#cbd5e1")

        plt.tight_layout()

        buf = io.BytesIO()
        plt.savefig(buf, format="png", bbox_inches="tight", transparent=True)
        buf.seek(0)
        plt.close(fig)
        return Image(buf, width=width, height=height)
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

        fig, ax = plt.subplots(figsize=(6.5, 2.8), dpi=150)
        ax.barh(labels, values, color=colors_list, height=0.6)
        ax.axvline(0, color="#64748b", linewidth=0.8, linestyle="--")

        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_color("#cbd5e1")
        ax.spines["bottom"].set_color("#cbd5e1")
        ax.tick_params(axis="both", colors="#475569", labelsize=8)

        ax.set_xlabel("Contribución a Afinidad (SHAP Value)", fontsize=8, color="#475569")

        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format="png", bbox_inches="tight", transparent=True)
        buf.seek(0)
        plt.close(fig)
        return Image(buf, width=width, height=height)
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


def generate_2d_interaction_diagram(smiles: str, contacts: list[dict], width=2.4 * inch, height=2.4 * inch) -> Image:
    """Renderiza contactos recibidos; no los calcula ni los reclasifica."""
    mol = Chem.MolFromSmiles(smiles)
    if not mol:
        return None
    try:
        from rdkit.Chem import rdDepictor
        from rdkit.Chem.Draw import rdMolDraw2D

        rdDepictor.Compute2DCoords(mol)

        highlight_atoms = []
        highlight_colors = {}
        atom_notes = {}

        for i, atom in enumerate(mol.GetAtoms()):
            symbol = atom.GetSymbol().upper()
            for contact in contacts:
                res_label = contact["residue"].split()[0]
                dist = contact["distance"]
                contact_type = contact["type"]

                if "H-Bond" in contact_type or "Salt Bridge" in contact_type:
                    if symbol in ("N", "O", "F", "S"):
                        if i not in highlight_atoms:
                            highlight_atoms.append(i)
                            highlight_colors[i] = (0.2, 0.8, 0.2)
                            atom_notes[i] = f"{res_label} ({dist})"
                            break

        d = rdMolDraw2D.MolDraw2DCairo(400, 400)
        opts = d.drawOptions()
        opts.clearBackground = True

        for idx, note in atom_notes.items():
            mol.GetAtomWithIdx(idx).SetProp("atomNote", note)

        d.DrawMolecule(mol, highlightAtoms=highlight_atoms, highlightAtomColors=highlight_colors)
        d.FinishDrawing()
        png_data = d.GetDrawingText()

        buf = io.BytesIO(png_data)
        return Image(buf, width=width, height=height)
    except Exception:
        return None
