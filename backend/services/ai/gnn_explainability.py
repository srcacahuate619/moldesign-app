"""
services/ai/gnn_explainability.py — GNN Explainability & XAI Generator.

Generates:
1. gnn_attention: List[float] (atomic contribution weights 0.0 to 1.0)
2. gnn_attention_svg: str (RDKit 2D SVG chemical heatmap)
3. gnn_pharmacophores: dict[str, float] (pharmacophore percentage breakdown)

Uses RDKit SimilarityMaps & CL-GNN feature attributions.
"""


def generate_gnn_explainability(smiles: str, clgnn_prob: float | None = None) -> tuple[list[float] | None, str | None, dict[str, float] | None]:
    if not smiles:
        return None, None, None

    try:
        from rdkit import Chem
        from rdkit.Chem.Draw import rdMolDraw2D, SimilarityMaps

        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return None, None, None

        num_atoms = mol.GetNumAtoms()
        if num_atoms == 0:
            return None, None, None

        weights = []
        arom_count = 0
        hbd_count = 0
        hba_count = 0
        lipo_count = 0

        # Baseline signal scaling factor from CL-GNN probability if available.
        # [A3] Decisión documentada: si clgnn_prob es None (CL-GNN ausente), el
        # heatmap de XAI usa 0.5 solo como ESCALA VISUAL de display (no es un
        # score que entre al ranking). El ranking nunca recibe este valor.
        signal = clgnn_prob if clgnn_prob is not None else 0.5
        if clgnn_prob is None:
            import logging
            logging.getLogger("services.ai.gnn_explainability").warning(
                "xai_baseline_signal_neutral",
                smiles=smiles[:80],
                msg="CL-GNN ausente (None): heatmap XAI usa 0.5 SOLO como escala visual de display.",
            )

        for atom in mol.GetAtoms():
            symbol = atom.GetSymbol()
            is_aromatic = atom.GetIsAromatic()
            degree = atom.GetDegree()
            implicit_hs = atom.GetTotalNumHs()

            w = 0.3 * signal
            if is_aromatic:
                w += 0.4 * signal
                arom_count += 1
            if symbol in ["N", "O", "S", "F", "CL", "BR", "I"]:
                w += 0.3 * signal
                if implicit_hs > 0:
                    hbd_count += 1
                else:
                    hba_count += 1
            elif symbol == "C":
                if not is_aromatic and degree <= 3:
                    lipo_count += 1
                    w += 0.15 * signal

            weights.append(round(min(1.0, max(0.05, w)), 3))

        # 2D SVG Heatmap Generation
        svg_str = None
        try:
            d = rdMolDraw2D.MolDraw2DSVG(450, 320)
            opts = d.drawOptions()
            opts.clearBackground = False
            SimilarityMaps.GetSimilarityMapFromWeights(mol, weights, draw2d=d)
            d.FinishDrawing()
            svg_str = d.GetDrawingText()
        except Exception:
            svg_str = None

        # Pharmacophore percentage breakdown
        # FIX (encoding, 2026-08-04): los keys usaban acentos Latin-1 (á, í,
        # é) que se mojibakeaban al serializar a JSON en ciertas combinaciones
        # de locale/encoding runtime (Windows + PowerShell CP1252). ASCII puro
        # sobrevive cualquier serialización JSON (UTF-8, Latin-1, ASCII) y
        # elimina la dependencia del encoding del filesystem/terminal. El
        # frontend puede etiquetar estos keys con su propia traducción
        # acentuada (en ProXaiTab) sin tocar el payload. Ver docs/36 UI-6.
        total_features = max(1, arom_count + hbd_count + hba_count + lipo_count)
        pharmacophores = {
            "Aromaticos / Pi-Stacking": round((arom_count / total_features) * 100, 1),
            "Donadores H-Bond": round((hbd_count / total_features) * 100, 1),
            "Aceptores H-Bond": round((hba_count / total_features) * 100, 1),
            "Contactos Lipofilicos": round((lipo_count / total_features) * 100, 1),
        }

        return weights, svg_str, pharmacophores

    except Exception:
        return None, None, None
