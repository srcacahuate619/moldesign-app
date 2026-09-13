import io
import os
from datetime import datetime, timezone
from pathlib import Path
from rdkit import Chem
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import KeepTogether, SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from core.models import MoleculeORM, EvaluationResultORM
from services.blockchain.certificate_context import generate_physiological_context
from services.blockchain.evidence_summary import build_evidence_summary
from services.blockchain.certificate_figures import (
    generate_2d_interaction_diagram,
    generate_energy_profile_plot,
    generate_gnn_attention_image,
    generate_shap_image,
    get_2d_image,
)

# ═════════════════════════════════════════════════════════════════════════════
# DESIGN TOKENS — paleta centralizada (disciplina Hallmark: sin improvisar color
# a mitad del render; todo token con nombre).
# Validez científica primero: los tokens solo afectan presentación, nunca datos.
# ═════════════════════════════════════════════════════════════════════════════
BRAND      = colors.HexColor("#2563eb")   # azul MolDesign — acento de marca
BRAND_DARK = colors.HexColor("#1e40af")   # azul profundo — títulos de sección
INK        = colors.HexColor("#0f172a")   # casi negro — cuerpo principal
SLATE      = colors.HexColor("#475569")   # gris pizarra — texto secundario
SLATE_LT   = colors.HexColor("#94a3b8")   # gris claro — notas y footer
LINE       = colors.HexColor("#e2e8f0")   # borde de tablas
HEAD_BG    = colors.HexColor("#f1f5f9")   # fondo de cabecera de tabla
GOOD       = colors.HexColor("#15803d")   # verde — PASA / SEGURO
WARN       = colors.HexColor("#b45309")   # ámbar — precaución
BAD        = colors.HexColor("#b91c1c")   # rojo — FALLA / RIESGO
PAPER      = colors.white                 # fondo del documento

# Logo MolDesign para marca de agua gigante centrada en cada hoja.
# Candidatos en orden: assets del backend (self-contained) → repo frontend →
# rutas docker/compose.
_LOGO_CANDIDATES = [
    Path(__file__).resolve().parent.parent.parent / "assets" / "logo.png",
    Path(__file__).resolve().parents[3] / "frontend" / "public" / "logo.png",
    Path("/app/assets/logo.png"),
]
_LOGO_WATERMARK_CACHE = None

def _get_logo_watermark():
    """Devuelve un ImageReader del logo con alpha ~8% (marca de agua sutil
    pero legible por encima del contenido). Cacheado por proceso."""
    global _LOGO_WATERMARK_CACHE
    if _LOGO_WATERMARK_CACHE is not None:
        return _LOGO_WATERMARK_CACHE
    try:
        from PIL import Image as PILImage
        for p in _LOGO_CANDIDATES:
            if os.path.exists(p):
                img = PILImage.open(p).convert("RGBA")
                r, g, b, a = img.split()
                a = a.point(lambda v: int(v * 0.08))
                img = PILImage.merge("RGBA", (r, g, b, a))
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                buf.seek(0)
                _LOGO_WATERMARK_CACHE = ImageReader(buf)
                return _LOGO_WATERMARK_CACHE
    except Exception:
        pass
    _LOGO_WATERMARK_CACHE = False
    return None

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self._draw_chrome()
            self.draw_page_number(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def _draw_chrome(self):
        """Chrome por página: banda superior de marca + marca de agua gigante
        del logo centrada. Se dibuja DESPUÉS del contenido con alpha bajo, de
        modo que la marca de agua es un vestigio sutil y el texto se lee bien."""
        # Banda superior fina de marca (3 pt, azul MolDesign)
        self.saveState()
        self.setFillColor(BRAND)
        self.rect(0, A4[1] - 0.28*cm, A4[0], 0.28*cm, stroke=0, fill=1)
        self.restoreState()

        # Marca de agua gigante centrada (~55% del ancho de hoja)
        wm = _get_logo_watermark()
        if wm:
            try:
                self.saveState()
                w = A4[0] * 0.55
                h = w * (479.0 / 521.0)  # ratio del logo original
                x = (A4[0] - w) / 2.0
                y = (A4[1] - h) / 2.0
                self.drawImage(wm, x, y, width=w, height=h, mask="auto")
                self.restoreState()
            except Exception:
                pass

    def draw_page_number(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 7)
        self.setFillColor(colors.HexColor("#64748b"))

        # Read metadata parameters if we cached them
        target_info = getattr(self, "target_info", "MolDesign Target")
        affinity_info = getattr(self, "affinity_info", "")
        score_info = getattr(self, "score_info", "")

        # Left executive summary
        summary_text = f"{target_info} | {affinity_info} | {score_info} | MolDesign AI"
        self.drawString(1.5*cm, 0.8*cm, summary_text)

        # Right page number
        page_text = f"Página {self._pageNumber} de {page_count}"
        self.drawRightString(A4[0] - 1.5*cm, 0.8*cm, page_text)

        # Thin divider line
        self.setStrokeColor(colors.HexColor("#e2e8f0"))
        self.setLineWidth(0.5)
        self.line(1.5*cm, 1.1*cm, A4[0] - 1.5*cm, 1.1*cm)
        self.restoreState()

CO_CRYSTAL_LIGANDS = {
    "7E2Y": "5-HT (Serotonina)",
    "6B3J": "Exendin-P5 (Péptido)",
    "6X1A": "Danuglipron (PF-06882961)",
    "2P4E": "SBC-115076",
    "6U26": "Inhibidor Alostérico 11a",
    "3OSK": "Péptido MYPPPY (B7-1)",
    "3ERT": "4-Hidroxitamoxifeno (OHT)",
    "5L2I": "Palbociclib (Ibrance)",
    "2W96": "Palbociclib (CDK4/6)",
    "4JPS": "Alpelisib (BYL719)",
    "3O96": "Inhibidor Alostérico VIII",
    "3PP0": "SYR-475",
    "4ZZZ": "NMS-P118",
    "1HVY": "Raltitrexed (Tomudex)",
    "4I5I": "EX-527 (Selisistat)",
    "6D8X": "GW1929",
    "5IKR": "Ácido Mefenámico",
    "4RER": "Estaurosporina (STU)",
    "5VEW": "PF-06305591",
    "1ERE": "Estradiol (EST)",
    "4EKL": "Ipatasertib (0RF)"
}


def get_pubchem_names(smiles: str) -> tuple[str, str]:
    """Devuelve nombres disponibles localmente sin transmitir el SMILES.

    El certificado se genera como parte de la experiencia desktop y no puede
    enviar una molécula del usuario a PubChem de forma implícita. El nombre
    asignado por la persona ya se imprime en el certificado; para la etiqueta
    sistemática sólo se intenta el resolver local opcional de RDKit.
    """
    del smiles

    common_name = "N/A"
    iupac_name = "N/A"
    return common_name, iupac_name

def compute_residue_interactions(receptor_pdb: str | None, ligand_sdf: str | None) -> list[dict]:
    if not receptor_pdb or not ligand_sdf:
        return []
    try:
        receptor_atoms = []
        for line in receptor_pdb.splitlines():
            if line.startswith(("ATOM", "HETATM")):
                try:
                    atom_name = line[12:16].strip()
                    res_name = line[17:20].strip()
                    chain = line[21].strip()
                    res_num = int(line[22:26].strip())
                    x = float(line[30:38])
                    y = float(line[38:46])
                    z = float(line[46:54])
                    element = line[76:78].strip() or atom_name[0]
                    receptor_atoms.append({
                        "atom_name": atom_name, "res_name": res_name, "chain": chain,
                        "res_num": res_num, "x": x, "y": y, "z": z, "element": element.upper()
                    })
                except (ValueError, IndexError):
                    continue

        suppl = Chem.SDMolSupplier()
        suppl.SetData(ligand_sdf)
        poses = [m for m in suppl if m is not None]
        if not poses:
            return []

        best_pose = poses[0]
        ligand_atoms = []
        conf = best_pose.GetConformer()
        for i, atom in enumerate(best_pose.GetAtoms()):
            pos = conf.GetAtomPosition(i)
            ligand_atoms.append({
                "idx": i, "element": atom.GetSymbol().upper(),
                "x": pos.x, "y": pos.y, "z": pos.z, "is_aromatic": atom.GetIsAromatic()
            })

        res_contacts = {}
        # Umbral mínimo físico: dos átomos no pueden estar a <0.8 Å (radios
        # covalentes ~0.7-1.5 Å). Si el SDF de poses y el PDB del receptor no
        # están en el MISMO frame de coordenadas, el cálculo reporta distancias
        # absurdas (0.3-0.4 Å) — descartarlas evita H-bonds físicamente
        # imposibles en el reporte.
        MIN_FEASIBLE_DIST = 0.8
        for latom in ligand_atoms:
            for ratom in receptor_atoms:
                dx = latom["x"] - ratom["x"]
                dy = latom["y"] - ratom["y"]
                dz = latom["z"] - ratom["z"]
                dist = (dx**2 + dy**2 + dz**2)**0.5
                if dist < MIN_FEASIBLE_DIST:
                    continue  # frame corrupto / coordenadas superpuestas
                if dist < 4.5:
                    res_key = (ratom["chain"], ratom["res_name"], ratom["res_num"])
                    if res_key not in res_contacts:
                        res_contacts[res_key] = []
                    res_contacts[res_key].append((latom, ratom, dist))

        classified = []
        for (chain, res_name, res_num), contacts in res_contacts.items():
            min_dist = min(c[2] for c in contacts)
            int_types = set()

            # Keep track of atoms to ensure mutual exclusivity
            atoms_in_hb = set()
            atoms_in_sb = set()

            # 1. H-Bond (Distancia < 3.2A y polares)
            for latom, ratom, dist in contacts:
                if dist < 3.2 and latom["element"] in ("N", "O", "F") and ratom["element"] in ("N", "O", "F"):
                    int_types.add("H-Bond")
                    atoms_in_hb.add(latom["idx"])

            # 2. Salt Bridge (Dist < 4.0A entre residuos ácidos/básicos y nitrógeno/oxígeno)
            if not int_types:
                for latom, ratom, dist in contacts:
                    if dist < 4.0 and latom["element"] in ("N", "O") and ratom["element"] in ("N", "O") and res_name in ("ASP", "GLU", "ARG", "LYS"):
                        int_types.add("Salt Bridge")
                        atoms_in_sb.add(latom["idx"])

            # 3. Pi-Stacking (Dist < 4.5A entre centroides de anillos aromáticos)
            if not int_types:
                for latom, ratom, dist in contacts:
                    if dist < 4.5 and latom["is_aromatic"] and res_name in ("PHE", "TYR", "TRP", "HIS") and ratom["element"] == "C":
                        int_types.add("Pi-Stacking")

            # 4. Hydrophobic (Carbono-Carbono dist < 4.2A, libre de H-bond/Salt Bridge/Pi-Stacking)
            if not int_types:
                for latom, ratom, dist in contacts:
                    if dist < 4.2 and latom["element"] == "C" and ratom["element"] == "C":
                        if latom["idx"] not in atoms_in_hb and latom["idx"] not in atoms_in_sb:
                            if res_name in ("ALA", "VAL", "LEU", "ILE", "PHE", "TYR", "TRP", "MET", "PRO"):
                                int_types.add("Hydrophobic")

            # Fallback simple
            if not int_types and min_dist < 4.0:
                if res_name in ("ALA", "VAL", "LEU", "ILE", "PHE", "TYR", "TRP", "MET", "PRO"):
                    int_types.add("Hydrophobic Contact")
                else:
                    int_types.add("Van der Waals")

            if int_types:
                classified.append({
                    "residue": f"{res_name}{res_num} ({chain})",
                    "type": "/".join(sorted(list(int_types))),
                    "distance": f"{min_dist:.2f} Å",
                    "min_dist_val": min_dist
                })
        classified.sort(key=lambda x: x["min_dist_val"])
        return classified[:10]  # Top 10 interactions
    except Exception:
        return []

# ── Marcadores que sobreviven a la extracción de texto ──────────────────────
#
# DOC 71, DEFECTO D2. El PDF usaba `·` (U+2022) como viñeta y se extraía como
# U+007F —el carácter DEL—: los marcadores de lista salían como caracteres de
# control. Perjudica búsqueda, copiado y lectores de pantalla, que es justo lo
# que un dossier no puede permitirse.
#
# La causa no es el texto sino la fuente. `font_path` apunta a
# `/usr/share/fonts/truetype/dejavu/...`, una ruta de Linux que en Windows
# —la plataforma real de este producto— nunca existe, así que se cae a Courier.
# Ni Courier ni Helvetica llevan el glifo del bullet en su codificación, y
# ReportLab lo sustituye.
#
# MEDIDO, no supuesto. Generando un PDF y extrayendo su texto con pypdf:
#
#     -   U+002D  sobrevive        ·   U+2022  ->  U+007F
#     *   U+002A  sobrevive        ⚠   U+26A0  ->  ■
#     ·   U+00B7  sobrevive        ▪   U+25AA  ->  ■
#     –   U+2013  sobrevive
#     →   U+2192  sobrevive        ✓   U+2713  sobrevive
#
# Se usa el punto medio: es el más parecido a una viñeta de los que sobreviven.
# La prueba `test_pdf_extraible.py` genera el documento y comprueba la
# extracción, así que no depende de que nadie recuerde esta lista.
VINETA = "·"

def generate_certificate_pdf(
    mol: MoleculeORM,
    eval_result: EvaluationResultORM,
    target_name: str,
    pose_sdf_content: str | None = None,
    receptor_pdb_content: str | None = None
) -> io.BytesIO:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        rightMargin=1.5*cm, leftMargin=1.5*cm,
        topMargin=1.5*cm, bottomMargin=1.5*cm
    )

    styles = getSampleStyleSheet()

    # DOC 71, DEFECTO E5. `allowWidows = 1` es el valor por defecto de ReportLab
    # y permite dejar la ULTIMA LINEA de un parrafo sola al principio de la
    # pagina siguiente. Es lo que producia «una frase de la seccion 9 cortada
    # entre paginas» y, encadenado con el apendice, una pagina con casi nada.
    #
    # Se apaga en la hoja de estilos entera, que es de donde heredan los
    # parrafos del documento. `allowOrphans` ya viene en 0 por defecto.
    for _estilo in styles.byName.values():
        if hasattr(_estilo, "allowWidows"):
            _estilo.allowWidows = 0
    # ── La fuente monoespaciada, buscada donde de verdad puede estar ────────
    #
    # DOC 71, DEFECTO D2, LA CAUSA. Aqui habia una sola candidata:
    # `/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf`. Es una ruta de
    # Linux, en Windows -la plataforma real de este producto- nunca existe, y el
    # documento se componia SIEMPRE con Courier, la Type1 incorporada.
    #
    # De ahi salia el sintoma que reporto la VM. MEDIDO extrayendo el texto del
    # PDF generado:
    #
    #     Courier / Helvetica (Type1)   «•» -> U+007F      «·» -> «·»
    #     Consolas / Courier New (TTF)  «•» -> «•»         «·» -> «·»
    #
    # Es decir: con una TrueType de verdad registrada el bullet sobrevive; era
    # la fuente incorporada la que lo perdia. Se arreglan las dos cosas por
    # separado -la vineta pasa a ser el punto medio, que sobrevive en todos los
    # casos, y la fuente se busca donde puede estar- porque depender de que un
    # glifo exista es una fragilidad que no hace falta correr.
    #
    # `⚠` (U+26A0) se extrae como U+0000 incluso con Consolas: no lo tiene
    # ninguna de estas fuentes. `test_pdf_extraible.py` lo impide.
    font_name = 'Courier'
    fuentes_mono = [
        # Windows: presentes desde Vista, no hay que empaquetar nada.
        os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "consola.ttf"),
        os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "cour.ttf"),
        # Linux, que es de donde venia la ruta original.
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
    ]
    for ruta_fuente in fuentes_mono:
        if not os.path.exists(ruta_fuente):
            continue
        try:
            registrada = os.path.splitext(os.path.basename(ruta_fuente))[0]
            pdfmetrics.registerFont(TTFont(registrada, ruta_fuente))
            font_name = registrada
            break
        except Exception:
            # Una fuente ilegible no puede tumbar el certificado: se prueba la
            # siguiente y, si ninguna sirve, queda Courier.
            continue
            pass

    title_style = ParagraphStyle(
        'MainTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=BRAND_DARK,
        alignment=1, # Center
        spaceAfter=4
    )

    subtitle_style = ParagraphStyle(
        'SubTitle',
        parent=styles['Normal'],
        fontSize=11,
        textColor=SLATE,
        alignment=1,
        spaceAfter=6
    )

    meta_style = ParagraphStyle(
        'MetaLine',
        parent=styles['Normal'],
        fontSize=8,
        textColor=SLATE_LT,
        alignment=1,
        spaceAfter=14
    )

    section_title_style = ParagraphStyle(
        'SectionTitle',
        parent=styles['Heading2'],
        fontSize=13,
        textColor=BRAND_DARK,
        spaceBefore=12,
        spaceAfter=8,
        borderPadding=(0,0,2,0),
        borderColor=BRAND,
        borderWidth=1
    )

    xai_header_style = ParagraphStyle(
        'XaiHeaderStyle',
        parent=styles['Normal'],
        fontSize=10,
        textColor=INK,
        fontName='Helvetica-Bold',
        spaceAfter=4,
        alignment=0 # Left
    )

    normal_style = styles['Normal']
    normal_style.fontSize = 9
    normal_style.leading = 13
    normal_style.textColor = INK

    mono_style = ParagraphStyle(
        'Mono',
        parent=styles['Normal'],
        fontName=font_name,
        fontSize=8,
        textColor=SLATE
    )

    story = []
    evidence_summary = build_evidence_summary(eval_result, getattr(mol, "target", None))

    # HEADER
    story.append(Paragraph("DOSSIER DE EVIDENCIA COMPUTACIONAL", title_style))

    # Fecha real de la evaluación (no la de descarga). evaluated_at es la
    # autoridad temporal del pipeline; se formatea en UTC y en zona local.
    if eval_result.evaluated_at is not None:
        ev_tz = eval_result.evaluated_at
        if ev_tz.tzinfo is None:
            ev_tz = ev_tz.replace(tzinfo=timezone.utc)
        cert_date = ev_tz.strftime("%Y-%m-%d %H:%M:%S UTC")
    else:
        # `utcnow()` devuelve un datetime naive y esta deprecado; aqui la
        # cadena ya decia "UTC" a mano, asi que el texto no cambia -pero la
        # fuente deja de ser ambigua-. Misma familia que el defecto E3.
        cert_date = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    story.append(Paragraph("Evidencia, reproducibilidad, supuestos, controles e incertidumbres", subtitle_style))
    story.append(Paragraph(f"Registro temporal de la evaluación: {cert_date} &nbsp;·&nbsp; MolDesign AI", meta_style))

    # EXECUTIVE EVIDENCE SUMMARY - first-page decision surface. El dossier
    # describe una corrida; no califica si la molécula es un "buen fármaco".
    status_colors = {"ready": GOOD, "review": WARN, "incomplete": BAD}
    evidence_color = status_colors[evidence_summary["status"]]
    model_context = evidence_summary["model_context"]
    domain_label = (
        "dentro del dominio declarado" if model_context["in_domain"] is True
        else "fuera del dominio declarado" if model_context["in_domain"] is False
        else "dominio no informado"
    )
    model_label = " / ".join(
        str(value) for value in (model_context["engine"], model_context["model"]) if value
    ) or "motor y modelo no informados"
    dimension_colors = {
        "available": GOOD,
        "review": WARN,
        "missing": BAD,
        "not_evaluated": SLATE,
    }
    next_action = evidence_summary["next_action"]
    action_color = {"proceed": GOOD, "review": WARN, "abstain": BAD}[next_action["status"]]

    story.append(Paragraph("Propósito del dossier", section_title_style))
    story.append(Paragraph(
        "Este documento responde qué evidencia computacional produjo la corrida, qué partes son reproducibles, "
        "qué supuestos hizo, qué controles superó, qué incertidumbres permanecen y qué sería justificable hacer después. "
        "No responde si la molécula es un buen fármaco.",
        normal_style,
    ))

    story.append(Paragraph("Conclusión operativa de la corrida", section_title_style))
    story.append(Paragraph(
        f"<font color='{evidence_color.hexval()}'><b>{evidence_summary['label']}</b></font> - "
        f"{evidence_summary['summary']}",
        normal_style,
    ))
    story.append(Paragraph(
        f"<font color='{action_color.hexval()}'><b>SIGUIENTE ACCIÓN JUSTIFICABLE: {next_action['label']}</b></font><br/>"
        f"{next_action['detail']}",
        ParagraphStyle('NextAction', parent=normal_style, borderColor=action_color, borderWidth=0.8, borderPadding=7, spaceBefore=6, spaceAfter=8),
    ))

    story.append(Paragraph("Matriz de evidencia por dimensión", section_title_style))
    evidence_rows = [["Dimensión", "Estado", "Evidencia o límite observado"]]
    for dimension in evidence_summary["dimensions"]:
        color = dimension_colors[dimension["status"]]
        evidence_rows.append([
            Paragraph(f"<b>{dimension['label']}</b>", normal_style),
            Paragraph(f"<font color='{color.hexval()}'><b>{dimension['status_label']}</b></font>", normal_style),
            Paragraph(dimension["detail"], normal_style),
        ])
    evidence_table = Table(
        evidence_rows,
        colWidths=[125, 115, 250],
        repeatRows=1,
    )
    evidence_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, LINE),
        ('BACKGROUND', (0, 0), (-1, 0), HEAD_BG),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BACKGROUND', (0, 1), (0, -1), colors.HexColor('#f8fafc')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('PADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(evidence_table)

    assumptions_text = "<br/>".join(f"- {item}" for item in evidence_summary["assumptions"])
    uncertainty_items = evidence_summary["uncertainties"] or ["No se registraron incertidumbres adicionales a las limitaciones generales del protocolo."]
    uncertainties_text = "<br/>".join(f"- {item}" for item in uncertainty_items)
    story.append(KeepTogether([
        Paragraph("Supuestos e incertidumbres abiertas", section_title_style),
        Table([
            [Paragraph("<b>Supuestos registrados</b>", normal_style), Paragraph("<b>Incertidumbres abiertas</b>", normal_style)],
            [Paragraph(assumptions_text, normal_style), Paragraph(uncertainties_text, normal_style)],
        ], colWidths=[245, 245], style=TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.5, LINE),
            ('BACKGROUND', (0, 0), (-1, 0), HEAD_BG),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('PADDING', (0, 0), (-1, -1), 5),
        ])),
    ]))

    # TARGET SECTION
    target_heading = Paragraph("Receptor Biológico (Target)", section_title_style)
    rho_val = f" | <b>Spearman ρ:</b> {mol.target.spearman_rho:.3f}" if (mol.target and mol.target.spearman_rho is not None) else ""

    ref_ligand = CO_CRYSTAL_LIGANDS.get(mol.target.pdb_id.upper() if mol.target else "", "N/A")
    ref_str = f" | <b>Ligando Co-cristalizado:</b> {ref_ligand}" if ref_ligand != "N/A" else ""

    target_identity = Paragraph(f"<b>PDB ID:</b> {mol.target.pdb_id.upper() if mol.target else 'N/A'} | <b>Nombre:</b> {target_name}{rho_val}{ref_str}", normal_style)

    # QA Check on Target Origin
    is_custom = mol.target and (mol.target.pdb_id.upper().startswith("USR_") or mol.target.is_private)
    if is_custom:
        qa_banner = (
            "<font color='#d97706'><b>[SISTEMA: ARCHIVO DE USUARIO]</b> "
            "La estructura fue aportada por el usuario. No se infieren operaciones de protonación o minimización que no estén registradas.</font>"
        )
    elif evidence_summary["target_readiness"] == "listo":
        qa_banner = (
            "<font color='#16a34a'><b>[SISTEMA: LISTO PARA EVALUAR]</b> "
            "El receptor está preparado y dispone de grid y referencias estructurales. Esto no implica validación experimental.</font>"
        )
    else:
        qa_banner = (
            "<font color='#d97706'><b>[SISTEMA: REVISAR PREPARACIÓN]</b> "
            "El inventario del receptor no permite afirmar que preparación, grid y hotspots estén completos.</font>"
        )
    # Flag de control: usa la ruta de penalización ADME ignorada (is_control).
    if getattr(eval_result, "is_control", False):
        qa_banner += " <font color='#7c3aed'><b>[CONTROL]</b> Molécula de control: las penalizaciones ADME se ignoran por diseño en este modo.</font>"
    story.append(KeepTogether([
        target_heading,
        target_identity,
        Spacer(1, 4),
        Paragraph(qa_banner, normal_style),
        Spacer(1, 6),
    ]))

    target_desc = mol.target.description
    # Una description genérica del seed ("Target pre-curado...") o los fallbacks
    # del fetch NO son contexto fisiológico: en ese caso se genera el contexto
    # a partir de los headers del PDB local.
    _generic_prefixes = (
        "Target pre-curado para virtual screening offline",
        "Target pre-curado de la libreria offline",
        "Target pre-curado offline",
        "Target pre-curado (",
        "Descripción fisiológica no disponible.",
        "Receptor Biológico PDB:",
    )
    _desc_is_generic = (
        not target_desc
        or any(target_desc.startswith(p) for p in _generic_prefixes)
    )
    if _desc_is_generic:
        target_desc = generate_physiological_context(mol.target.pdb_id if mol.target else "7E2Y", receptor_pdb_content)
    story.append(Paragraph(f"<b>Contexto Fisiológico:</b> {target_desc}", normal_style))
    story.append(Spacer(1, 10))

    # MOLECULE SECTION
    story.append(Paragraph("Detalles de la Molécula", section_title_style))

    # Fetch common and IUPAC name from PubChem
    common_name, iupac_name = get_pubchem_names(mol.smiles)

    # IUPAC Truncation to avoid visual table overflow
    if iupac_name and len(iupac_name) > 80:
        iupac_name = iupac_name[:77] + "..."

    mol_info_data = [
        [Paragraph("<b>Nombre Asignado:</b>", normal_style), Paragraph(mol.name or f"Ligando {mol.smiles_hash[:8]}", normal_style)],
        [Paragraph("<b>Nombre Común (PubChem):</b>", normal_style), Paragraph(common_name, normal_style)],
        [Paragraph("<b>Nombre Sistemático (IUPAC):</b>", normal_style), Paragraph(iupac_name, normal_style)],
        [Paragraph("<b>ID de Sistema:</b>", normal_style), Paragraph(str(mol.id), mono_style)],
        [Paragraph("<b>SMILES Hash:</b>", normal_style), Paragraph(mol.smiles_hash, mono_style)],
        [Paragraph("<b>Estructura SMILES:</b>", normal_style), Paragraph(mol.smiles, mono_style)]
    ]

    mol_table = Table(mol_info_data, colWidths=[140, 350])
    mol_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
    ]))

    img = get_2d_image(mol.smiles)
    if img:
        layout_table = Table([[mol_table, img]], colWidths=[350, 140])
        layout_table.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP')]))
        story.append(layout_table)
    else:
        story.append(mol_table)

    story.append(Spacer(1, 10))

    # DOCKING & INTERACTION SECTION
    story.append(Paragraph("Interacción Molecular y Docking (AutoDock Vina)", section_title_style))

    # affinity_kcal es la señal final serializada por el pipeline. Se presenta
    # separada de las poses Vina crudas para conservar procedencia y evitar
    # equiparar un score algorítmico con energía libre experimental.
    main_affinity = eval_result.affinity_kcal

    le = None
    if main_affinity is not None and eval_result.heavy_atom_count and eval_result.heavy_atom_count > 0:
        le = main_affinity / eval_result.heavy_atom_count

    lle = None
    if main_affinity is not None and eval_result.log_p is not None:
        lle = (-main_affinity / 1.36) - eval_result.log_p

    pdb_upper = (mol.target.pdb_id.upper() if mol.target else "")
    top_pose = evidence_summary["top_pose_affinity"]
    pose_gap = evidence_summary["pose_gap"]
    dock_headers = ["Señal computacional", "Valor observado"]
    dock_data = [
        dock_headers,
        ["Afinidad reportada por el pipeline", f"{main_affinity:.2f} kcal/mol" if main_affinity is not None else "N/A"],
        ["Mejor pose Vina cruda", f"{top_pose:.2f} kcal/mol" if top_pose is not None else "N/A"],
        ["Separación entre poses 1 y 2", f"{pose_gap:.2f} kcal/mol" if pose_gap is not None else "N/A"],
        ["Poses serializadas", str(evidence_summary["pose_count"])],
        ["Eficiencia de Ligando (LE)", f"{le:.3f}" if le is not None else "N/A"],
        ["Eficiencia Lipofílica (LLE)", f"{lle:.3f}" if lle is not None else "N/A"],
    ]

    dock_table = Table(dock_data, colWidths=[245, 245], repeatRows=1)
    dock_table.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f1f5f9')),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BACKGROUND', (0,1), (0,-1), colors.HexColor('#f8fafc')),
        ('FONTNAME', (0,1), (0,-1), 'Helvetica-Bold'),
        ('PADDING', (0,0), (-1,-1), 4),
        ('ALIGN', (1,0), (-1,-1), 'CENTER')
    ]))
    story.append(dock_table)
    story.append(Paragraph(
        "La separación entre poses es una señal descriptiva no calibrada; no debe interpretarse como confianza estadística.",
        ParagraphStyle('PoseGapNote', parent=normal_style, fontSize=7.5, textColor=SLATE, spaceBefore=4),
    ))

    story.append(Spacer(1, 6))

    # ── Reproducibilidad del docking (parsing_source, vina_version, seed) ──
    # Estos campos vienen del pipeline real; la metodología hardcodeada abajo
    # se mantiene como contexto, pero la versión/semilla reales son la fuente.
    repro_rows = []
    if getattr(eval_result, "vina_version", None):
        repro_rows.append(["Versión del Motor de Docking", str(eval_result.vina_version)])
    if getattr(eval_result, "parsing_source", None):
        repro_rows.append(["Formato de Entrada", str(eval_result.parsing_source)])
    if getattr(eval_result, "vina_random_seed", None) is not None:
        repro_rows.append(["Semilla Estocástica", str(eval_result.vina_random_seed)])
    if repro_rows:
        repro_headers = ["Parámetro de Reproducibilidad", "Valor"]
        repro_data = [repro_headers] + [[r[0], r[1]] for r in repro_rows]
        repro_table = Table(repro_data, colWidths=[200, 290])
        repro_table.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.5, LINE),
            ('BACKGROUND', (0,0), (-1,0), HEAD_BG),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('BACKGROUND', (0,1), (0,-1), colors.HexColor('#f8fafc')),
            ('FONTNAME', (0,1), (0,-1), 'Helvetica-Bold'),
            ('PADDING', (0,0), (-1,-1), 4),
            ('FONTSIZE', (0,0), (-1,-1), 8),
            ('ALIGN', (1,0), (-1,-1), 'CENTER')
        ]))
        story.append(repro_table)
        story.append(Spacer(1, 6))

    if eval_result.hotspots_hit:
        hotspots_str = ", ".join(eval_result.hotspots_hit)
        story.append(Paragraph(f"<b>Residuos Hotspots Impactados:</b> {hotspots_str}", normal_style))

    if eval_result.specificity_score is not None and eval_result.specificity_score < 40.0:
        # La afinidad y los contactos se reportan con el valor autoritativo
        # (affinity_kcal) para que la nota sea consistente con la tabla.
        aff_display = f"{eval_result.affinity_kcal:.2f}" if eval_result.affinity_kcal is not None else "N/A"
        spec_warning = (
            "<font color='#b91c1c'><b>Reserva de especificidad:</b> La señal normalizada quedó por debajo "
            "del umbral operativo del pipeline. Los contactos reportados no coinciden suficientemente con "
            "los hotspots de referencia del catálogo. Esta observación exige revisión del patrón de contactos; "
            f"no demuestra promiscuidad. La afinidad de referencia es {aff_display} kcal/mol.</font>"
        )
        story.append(Spacer(1, 4))
        story.append(Paragraph(spec_warning, normal_style))

    # Residue-Ligand Interactions Sub-Section
    contacts = compute_residue_interactions(receptor_pdb_content, pose_sdf_content)
    if contacts:
        story.append(Spacer(1, 10))
        story.append(Paragraph("<b>Mapeo de Contactos de Sitio Activo (Residuo-Ligando)</b>", normal_style))
        story.append(Spacer(1, 4))

        contact_rows = [["Residuo", "Tipo de Interacción", "Distancia"]]
        for c in contacts[:7]:  # Show top 7 in table to leave space
            contact_rows.append([c["residue"], c["type"], c["distance"]])

        contact_table = Table(contact_rows, colWidths=[100, 140, 60]) # Narrower for side-by-side
        contact_table.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f1f5f9')),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 8),
            ('PADDING', (0,0), (-1,-1), 3)
        ]))

        # Draw 2D Interaction Diagram side-by-side
        diag_img = generate_2d_interaction_diagram(mol.smiles, contacts, 180, 180)
        if diag_img:
            layout_table = Table([[contact_table, diag_img]], colWidths=[310, 180])
            layout_table.setStyle(TableStyle([
                ('VALIGN', (0,0), (-1,-1), 'TOP'),
                ('LEFTPADDING', (1,0), (1,0), 10),
                ('RIGHTPADDING', (0,0), (-1,-1), 0),
                ('BOTTOMPADDING', (0,0), (-1,-1), 0)
            ]))
            story.append(layout_table)
        else:
            # Fallback to full width if diagram failed
            fallback_rows = [["Residuo", "Tipo de Interacción", "Distancia Mínima"]]
            for c in contacts:
                fallback_rows.append([c["residue"], c["type"], c["distance"]])
            contact_table_full = Table(fallback_rows, colWidths=[150, 220, 120])
            contact_table_full.setStyle(TableStyle([
                ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f1f5f9')),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('PADDING', (0,0), (-1,-1), 4)
            ]))
            story.append(contact_table_full)

    # ── ALERTAS CIENTÍFICAS DEL PIPELINE (scientific_warnings) ──────────
    #
    # LA SEVERIDAD LA DECLARA QUIEN EMITE EL AVISO. Aquí se deducía buscando
    # subcadenas, con una lista de positivos que incluía `"sin"`. Sobre los 184
    # avisos que emite hoy el backend, esa regla marcaba DIEZ como
    # «[POSITIVA]», en verde, dentro del documento que se firma y se comparte
    # como evidencia. Entre ellos:
    #
    #     «Vina no encontrado. Devolviendo estructura plegada sin docking.»
    #     «conformación N sin minimizar (MMFF no disponible)»
    #     «Estructura APO (sin ligando): se usó MolPocket para detectar el pocket»
    #     «N targets preparados sin PDB local (se omiten)»
    #
    # El primero es el peor que puede haber: el motor de acoplamiento no
    # estaba, el resultado no contiene acoplamiento ninguno, y el certificado
    # lo etiquetaba como hallazgo favorable.
    #
    # Ver `services/avisos.py`. Un aviso heredado —de una corrida anterior a la
    # severidad declarada— sale como «NOTA» sin color: no se sabe su severidad,
    # y adivinarla es exactamente lo que se está quitando.
    from services.avisos import Severidad, normalizar_avisos

    _ESTILO_POR_SEVERIDAD = {
        Severidad.CRITICA.value: (BAD, "CRÍTICA"),
        Severidad.PRECAUCION.value: (WARN, "PRECAUCIÓN"),
        Severidad.POSITIVA.value: (GOOD, "POSITIVA"),
        Severidad.INFO.value: (SLATE, "NOTA"),
        Severidad.HEREDADA.value: (SLATE, "NOTA"),
    }

    sci_warnings = normalizar_avisos(getattr(eval_result, "scientific_warnings", None))
    if sci_warnings:
        story.append(Spacer(1, 10))
        story.append(Paragraph("Alertas Científicas del Pipeline", section_title_style))
        for item in sci_warnings:
            color, badge = _ESTILO_POR_SEVERIDAD.get(item["severidad"], (SLATE, "NOTA"))
            story.append(Paragraph(
                f"<font color='{color.hexval() if hasattr(color, 'hexval') else '#b91c1c'}'>"
                f"<b>[{badge}]</b></font> {item['mensaje']}",
                ParagraphStyle('SciWarning', parent=normal_style, fontSize=8, leading=11, spaceAfter=3)
            ))

    # ── PANEL DE SELECTIVIDAD (ANTI-TARGETS) ────────────────────────
    anti_results = getattr(eval_result, "anti_target_results", None) or []
    selectivity_ran = getattr(eval_result, "selectivity_ran", False)
    selectivity_ratio = getattr(eval_result, "selectivity_ratio", None)
    selectivity_verdict = getattr(eval_result, "selectivity_verdict", None)

    if selectivity_ran and anti_results:
        anti_section = [
            Spacer(1, 14),
            Paragraph("Panel computacional de anti-targets", section_title_style),
        ]

        # Selectivity ratio + verdict
        if selectivity_ratio is not None:
            ratio_color = "#15803d" if (selectivity_ratio or 0) > 3 else "#b45309" if (selectivity_ratio or 0) > 1 else "#b91c1c"
            anti_section.append(Paragraph(
                f"<b>Ratio de separación reportado:</b> <font color='{ratio_color}'>{selectivity_ratio:.1f}x</font> "
                f"- etiqueta serializada: {selectivity_verdict or 'sin clasificación'}",
                normal_style
            ))

        # Anti-target results table
        anti_headers = ["Anti-target", "Afinidad (kcal/mol)", "Umbral operativo", "Lectura"]
        anti_data = [anti_headers]
        for r in anti_results:
            aff = r.get("affinity")
            status = r.get("status", "ok")
            thresh = r.get("threshold", -7.0)

            if status == "ok" and aff is not None:
                aff_str = f"{aff:.2f}"
                thresh_str = f"{thresh:.1f}"
                state = "NO CRUZA UMBRAL" if aff >= thresh else "CRUZA UMBRAL"
                state_color = "#15803d" if aff >= thresh else "#b91c1c"
            elif status == "unpreparable":
                aff_str = "N/A"
                thresh_str = f"{thresh:.1f}"
                state = "PDB INVALIDO"
                state_color = "#b45309"
            elif status == "no_pdb":
                aff_str = "N/A"
                thresh_str = f"{thresh:.1f}"
                state = "SIN ESTRUCTURA"
                state_color = "#b45309"
            elif status == "timeout":
                aff_str = "N/A"
                thresh_str = f"{thresh:.1f}"
                state = "TIMEOUT"
                state_color = "#b45309"
            else:
                aff_str = "N/A"
                thresh_str = f"{thresh:.1f}"
                state = "FALLO"
                state_color = "#b91c1c"

            anti_data.append([
                r.get("name", r.get("pdb_id", "?")),
                aff_str,
                thresh_str,
                Paragraph(f"<font color='{state_color}'><b>{state}</b></font>", normal_style),
            ])

        anti_table = Table(anti_data, colWidths=[180, 110, 100, 90])
        anti_table.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1e293b')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor('#f8fafc')),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 7),
            ('PADDING', (0,0), (-1,-1), 4),
        ]))
        anti_section.append(anti_table)
        anti_section.append(Paragraph(
            "<i>Lectura relativa a un umbral del protocolo; no demuestra seguridad ni selectividad experimental.</i>",
            ParagraphStyle('AntiTargetEvidenceNote', parent=normal_style, fontSize=7.5, leading=9.5, textColor=SLATE),
        ))

        # Source note
        user_anti = [r for r in anti_results if r.get("category") == "Custom"]
        if user_anti:
            anti_section.append(Paragraph(
                f"<font color='#94a3b8' size='6'>* {len(user_anti)} anti-target(s) subido(s) por el usuario incluido(s) en este panel.</font>",
                normal_style
            ))
        story.append(KeepTogether(anti_section))

    elif selectivity_ran:
        story.append(Spacer(1, 14))
        story.append(Paragraph("Panel de Selectividad Farmacologica", section_title_style))
        story.append(Paragraph(
            "<i>El panel de selectividad se ejecuto pero no se encontraron resultados. "
            "Verifica que los anti-targets seleccionados tengan estructuras PDB validas.</i>",
            normal_style
        ))

    # Continuar en el espacio disponible; los saltos forzados producían páginas
    # casi vacías cuando la sección anterior era corta.

    # ADME & PHYSICOCHEMICAL. El dossier no mezcla la corrida con controles
    # internos sin procedencia serializada; una comparación solo debe aparecer
    # cuando el backend reciba y registre explícitamente ese control.
    story.append(Paragraph("Perfil Fisicoquímico (ADME)", section_title_style))

    adme_headers = ["Propiedad", "Valor calculado", "Regla de referencia"]

    adme_data = [
        adme_headers,
        ["Peso Molecular (MW)", f"{eval_result.molecular_weight:.2f} Da" if eval_result.molecular_weight else "N/A", "≤ 500 Da (Lipinski)"],
        ["Coef. Partición (LogP)", f"{eval_result.log_p:.2f}" if eval_result.log_p is not None else "N/A", "≤ 5.0 (Lipinski)"],
        ["Área Sup. Polar (TPSA)", f"{eval_result.tpsa:.2f} Å²" if eval_result.tpsa else "N/A", "≤ 140 Å² (Veber)"],
        ["Donadores H-Bond (HBD)", f"{eval_result.hbd}" if eval_result.hbd is not None else "N/A", "≤ 5 (Lipinski)"],
        ["Aceptores H-Bond (HBA)", f"{eval_result.hba}" if eval_result.hba is not None else "N/A", "≤ 10 (Lipinski)"],
        ["Enlaces Rotables", f"{eval_result.rotatable_bonds}" if eval_result.rotatable_bonds is not None else "N/A", "≤ 10 (Veber)"],
        ["Conteo de Anillos", f"{eval_result.ring_count}" if eval_result.ring_count is not None else "N/A", "—"]
    ]

    adme_table = Table(adme_data, colWidths=[190, 130, 170])
    adme_table.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f1f5f9')),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BACKGROUND', (0,1), (0,-1), colors.HexColor('#f8fafc')),
        ('FONTNAME', (0,1), (0,-1), 'Helvetica-Bold'),
        ('PADDING', (0,0), (-1,-1), 3),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('ALIGN', (1,0), (-1,-1), 'CENTER')
    ]))
    story.append(adme_table)

    story.append(Spacer(1, 10))

    # ADMET-AI Pharmacokinetics Table
    admet_headers = ["Propiedad modelada (ADMET-AI)", "Salida", "Alcance de la señal"]

    # 1. Solubility qualitative tier classification
    solubility_val = "N/A"
    if eval_result.blood_solubility_logs is not None:
        logs = eval_result.blood_solubility_logs
        if logs >= -4.0:
            solubility_val = f"{logs:.2f} logS (Soluble)"
        elif logs <= -6.0:
            solubility_val = f"{logs:.2f} logS (Poco soluble)"
        else:
            solubility_val = f"{logs:.2f} logS (Mod. soluble)"

    ppb_val = str(eval_result.blood_ppb_category) if eval_result.blood_ppb_category else "N/A"

    if eval_result.blood_hia_permeable is not None:
        hia_val = "Alta (HIA+)" if eval_result.blood_hia_permeable else "Baja (HIA-)"
        # Aclaración científica: HIA es UN componente del Score ADME, no el
        # score completo. Un ADME alto con HIA baja es posible cuando las otras
        # métricas (LogP, TPSA, solubilidad, PPB, BBB, reactividad) dominan la
        # agregación ponderada.
        hia_note = "Salida individual del modelo; se interpreta por separado de otros descriptores."
    else:
        hia_val = "N/A"
        # `hia_note` SOLO se asignaba en la rama de arriba. Con una molecula sin
        # HIA serializada -que es cualquiera cuyo ADMET no se ejecuto- este
        # `else` dejaba la variable sin ligar y la tabla reventaba con
        # `UnboundLocalError`: el certificado NO SE PODIA GENERAR.
        #
        # No estaba en los 19 defectos del doc 71 porque la evaluacion de la VM
        # tenia ADMET completo y nunca entro por aqui. Lo encontro la prueba que
        # genera el PDF de verdad, no una que inspecciona el codigo.
        hia_note = ("La corrida no serializo absorcion intestinal. No se evaluo: "
                    "eso no dice nada sobre la molecula.")

    # 2. BBB: preservar la salida binaria sin convertirla en veredicto clínico.
    requires_cns = bool(mol.target.requires_cns) if (mol.target and hasattr(mol.target, "requires_cns")) else False
    if eval_result.blood_bbb_permeable is not None:
        bbb_val = "Permeable (SNC+)" if eval_result.blood_bbb_permeable else "No permeable (SNC-)"
        bbb_context = "El target requiere acceso al SNC; la salida sigue siendo una predicción binaria." if requires_cns else "Predicción binaria; no determina exposición ni seguridad central."
    else:
        bbb_val = "N/A"
        bbb_context = "Salida no serializada."

    cyp_warnings = []
    if eval_result.blood_systemic_reactivity:
        for alert in eval_result.blood_systemic_reactivity:
            if "CYP" in alert:
                cyp_warnings.append(alert.replace("Inhibidor ", "Inh ").replace("Sustrato ", "Sub "))
    cyp_val = ", ".join(cyp_warnings) if cyp_warnings else "Sin alertas CYP serializadas"

    tbl_cell_style = ParagraphStyle(
        'TblCell',
        parent=styles['Normal'],
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#1e293b')
    )
    tbl_cell_bold = ParagraphStyle(
        'TblCellBold',
        parent=tbl_cell_style,
        fontName='Helvetica-Bold'
    )
    tbl_cell_center = ParagraphStyle(
        'TblCellCenter',
        parent=tbl_cell_style,
        alignment=1 # Center
    )

    admet_data = [
        [Paragraph(f"<b>{h}</b>", tbl_cell_bold) for h in admet_headers],
        [
            Paragraph("Solubilidad Acuosa (LogS)", tbl_cell_bold),
            Paragraph(solubility_val, tbl_cell_center),
            Paragraph("Estimación del modelo; no sustituye una medición de solubilidad.", tbl_cell_style)
        ],
        [
            Paragraph("Unión a Proteínas (PPB)", tbl_cell_bold),
            Paragraph(ppb_val, tbl_cell_center),
            Paragraph("Categoría predicha de unión a proteínas plasmáticas.", tbl_cell_style)
        ],
        [
            Paragraph("Absorción Intestinal (HIA)", tbl_cell_bold),
            Paragraph(hia_val, tbl_cell_center),
            Paragraph(hia_note, tbl_cell_style)
        ],
        [
            Paragraph("Barrera Hematoencefálica (BBB)", tbl_cell_bold),
            Paragraph(bbb_val, tbl_cell_center),
            Paragraph(bbb_context, tbl_cell_style)
        ],
        [
            Paragraph("Metabolismo CYP (P450)", tbl_cell_bold),
            Paragraph(cyp_val, tbl_cell_center),
            Paragraph("Solo resume alertas CYP presentes; ausencia de alertas no demuestra ausencia de interacción.", tbl_cell_style)
        ]
    ]

    admet_table = Table(admet_data, colWidths=[160, 140, 190])
    admet_table.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f1f5f9')),
        ('BACKGROUND', (0,1), (0,-1), colors.HexColor('#f8fafc')),
        ('PADDING', (0,0), (-1,-1), 4),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE')
    ]))
    story.append(admet_table)

    story.append(Spacer(1, 10))

    # DESCRIPTORS, HEURISTIC RULES & FILTERS
    story.append(Paragraph("Descriptores, reglas y filtros heurísticos", section_title_style))

    # Analyze infractions dynamically from pre-calculated values
    infractions = []
    if eval_result.molecular_weight and eval_result.molecular_weight > 500:
        infractions.append(f"MW alto ({eval_result.molecular_weight:.1f} Da)")
    if eval_result.log_p and eval_result.log_p > 5.0:
        infractions.append(f"LogP alto ({eval_result.log_p:.2f})")
    if eval_result.hbd and eval_result.hbd > 5:
        infractions.append(f"Exceso Donadores H-Bond ({eval_result.hbd})")
    if eval_result.hba and eval_result.hba > 10:
        infractions.append(f"Exceso Aceptores H-Bond ({eval_result.hba})")
    if eval_result.tpsa and eval_result.tpsa > 140:
        infractions.append(f"TPSA alta ({eval_result.tpsa:.1f} Å²)")
    if eval_result.rotatable_bonds and eval_result.rotatable_bonds > 10:
        infractions.append(f"Flexibilidad alta ({eval_result.rotatable_bonds} rot. bonds)")

    infractions_str = ", ".join(infractions) if infractions else "No se registraron infracciones frente a estas reglas"

    dl_data = [
        ["Regla de Lipinski (Ro5)", "CUMPLE" if eval_result.lipinski_pass else "NO CUMPLE",
         "QED (heurístico)", f"{eval_result.qed:.3f}" if eval_result.qed else "N/A"],
        ["Regla de Veber", "CUMPLE" if eval_result.veber_pass else "NO CUMPLE",
         "Fsp3 (C sp3)", f"{eval_result.fsp3:.3f}" if getattr(eval_result, 'fsp3', None) is not None else "N/A"],
        ["Regla de Ghose", "CUMPLE" if getattr(eval_result, 'ghose_pass', None) else "NO CUMPLE",
         "Regla de Egan", "CUMPLE" if getattr(eval_result, 'egan_pass', None) else "NO CUMPLE"],
        ["Regla de Muegge", f"CUMPLE ({getattr(eval_result, 'muegge_score', '?')}/9)" if getattr(eval_result, 'muegge_pass', None) else "NO CUMPLE",
         "SA (heurístico)", f"{eval_result.sa_score:.2f} / 10" if eval_result.sa_score else "N/A"],
    ]

    dl_table = Table(dl_data, colWidths=[135, 95, 135, 125])
    dl_table.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('BACKGROUND', (0,0), (0,-1), colors.HexColor('#f8fafc')),
        ('BACKGROUND', (2,0), (2,-1), colors.HexColor('#f8fafc')),
        ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
        ('FONTNAME', (2,0), (2,-1), 'Helvetica-Bold'),
        ('PADDING', (0,0), (-1,-1), 4),
        ('FONTSIZE', (0,0), (-1,-1), 8)
    ]))
    story.append(dl_table)

    story.append(Spacer(1, 4))

    diagnostics_text = f"<b>Lectura de las reglas:</b> {infractions_str}. Estas reglas describen propiedades; no califican por sí solas la idoneidad farmacológica."
    if eval_result.qed and eval_result.qed < 0.5:
        diagnostics_text += " <i>QED quedó por debajo de 0.5; se conserva como descriptor heurístico, no como veredicto.</i>"
    story.append(Paragraph(diagnostics_text, normal_style))

    if eval_result.sa_reasons:
        reasons = ", ".join(eval_result.sa_reasons)
        story.append(Paragraph(f"<b>Penalizaciones Sintéticas:</b> {reasons}", normal_style))

    # Real precalculated toxicology screening
    tox_alerts = eval_result.blood_systemic_reactivity or []
    is_pains = getattr(eval_result, "is_pains", False)
    pains_matches = getattr(eval_result, "pains_matches", []) or []

    if is_pains and pains_matches:
        pains_names = ", ".join([m.get("name", "unknown") for m in pains_matches[:5]])
        story.append(Paragraph(
            f"<b><font color='#b91c1c'>ALERTA PAINS:</font></b> "
            f"Esta molecula contiene subestructuras PAINS ({len(pains_matches)} patrones: {pains_names}). "
            f"Los PAINS son falsos positivos frecuentes en ensayos biologicos. "
            f"Se recomienda validacion experimental exhaustiva.",
            normal_style
        ))
    elif tox_alerts:
        tox_str = ", ".join(tox_alerts)
        story.append(Paragraph(
            f"<b><font color='#b91c1c'>Alertas de Toxicoforos:</font></b> {tox_str}",
            normal_style
        ))
    else:
        story.append(Paragraph(
            "<b>Filtros PAINS:</b> no se detectaron subestructuras de la biblioteca usada. La ausencia de coincidencias no descarta otros mecanismos de interferencia.",
            normal_style
        ))

    story.append(Spacer(1, 10))

    # Poses & Energy Profile section
    if eval_result.docking_poses:
        # Las poses son salidas Vina crudas. affinity_kcal se conserva como una
        # señal separada del pipeline para no mezclar escalas ni procedencias.
        pose_note = (
            "Nota: las afinidades por pose corresponden a la salida cruda de AutoDock Vina. "
            "La señal affinity_kcal puede diferir porque la serializa otra etapa del pipeline. "
            "Ninguna de las dos equivale por sí sola a una energía libre experimental."
        )
        pose_note_paragraph = Paragraph(
            f"<font color='#64748b' size='7.5'><i>{pose_note}</i></font>",
            ParagraphStyle('PoseNote', parent=normal_style, spaceAfter=4)
        )
        poses_subset = eval_result.docking_poses[:5] # Top 5 poses
        pose_rows = [["Rank", "Afinidad (kcal/mol)", "RMSD lb", "RMSD ub"]]
        for p in poses_subset:
            pose_rows.append([f"Pose {p['rank']}", f"{p['affinity']:.2f}" if p.get('affinity') is not None else "N/A", f"{p['rmsd_lb']:.2f}" if p.get('rmsd_lb') is not None else "N/A", f"{p['rmsd_ub']:.2f}" if p.get('rmsd_ub') is not None else "N/A"])

        pose_table = Table(pose_rows, colWidths=[110, 140, 120, 120]) # Width exactly 490
        pose_table.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f1f5f9')),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('PADDING', (0,0), (-1,-1), 4)
        ]))
        story.append(KeepTogether([
            Paragraph("Perfiles de Energía por Pose", section_title_style),
            pose_note_paragraph,
            pose_table,
        ]))

        ep_plot = generate_energy_profile_plot(eval_result.docking_poses, 6.8*inch, 2.5*inch)
        if ep_plot:
            story.append(Spacer(1, 8))
            story.append(ep_plot)

    # ReportLab decide el salto según el contenido para mantener un dossier compacto.

    # EXPLAINABLE AI (XAI) SECTION
    has_xai = eval_result.shap_values or eval_result.gnn_attention
    if has_xai:
        story.append(Paragraph("Explicabilidad Científica e IA de Caja Transparente", section_title_style))

        # Translation dict for internal feature names to friendly Spanish scientific terms
        feature_translation = {
            "molecular_weight": "Peso Molecular (MW)",
            "log_p": "Lipofilicidad (LogP)",
            "tpsa": "Área Superficial Polar (TPSA)",
            "hbd": "Donadores de H-Bond",
            "hba": "Aceptores de H-Bond",
            "rotatable_bonds": "Enlaces Rotables",
            "heavy_atom_count": "Conteo de Átomos Pesados",
            "ring_count": "Conteo de Anillos",
            "qed": "Drug-likeness (QED)",
            "sa_score": "Accesibilidad Sintética (SA)",
            "lipinski_pass": "Regla de Lipinski"
        }

        if eval_result.shap_values:
            shap_img = generate_shap_image(eval_result.shap_values, 6.8*inch, 2.8*inch)
            if shap_img:
                story.append(Paragraph("XGBOOST NATIVE SHAP EXPLAINER", xai_header_style))
                story.append(shap_img)
                story.append(Spacer(1, 4))

                # Tabular breakdown of the top SHAP values for the scientist
                shap_rows = [["Descriptor", "Contribución (SHAP)", "Dirección en la salida"]]
                sorted_shap = sorted(eval_result.shap_values.items(), key=lambda x: abs(x[1]), reverse=True)[:5]
                for feat, val in sorted_shap:
                    friendly_name = feature_translation.get(feat, feat.replace("_", " ").title())
                    sign = "+" if val > 0 else ""
                    impact_text = "Contribución negativa a la salida" if val < 0 else "Contribución positiva a la salida"
                    shap_rows.append([friendly_name, f"{sign}{val:.4f}", impact_text])

                shap_table = Table(shap_rows, colWidths=[150, 110, 230])
                shap_table.setStyle(TableStyle([
                    ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
                    ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f1f5f9')),
                    ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0,0), (-1,-1), 8),
                    ('PADDING', (0,0), (-1,-1), 3)
                ]))
                story.append(KeepTogether([shap_table]))
                story.append(Spacer(1, 10))

        if eval_result.gnn_attention:
            gnn_img = generate_gnn_attention_image(mol.smiles, eval_result.gnn_attention, 6.8*inch, 3.8*inch)
            if gnn_img:
                story.append(Paragraph("Atención GNN (RTMScore) MAPA DE HOTSPOTS", xai_header_style))
                story.append(gnn_img)
                story.append(Spacer(1, 4))

                legend_text = (
                    "<b>Interpretación del Mapa de Hotspots:</b> Las esferas de colores en la estructura indican los átomos en los que "
                    "la red neuronal geométrica centró su atención tridimensional al evaluar el complejo ligando-receptor. Las regiones con "
                    "colores más intensos (rojo/naranja) denotan interacciones de contacto local que más definen la afinidad predicha."
                )
                story.append(Paragraph(legend_text, ParagraphStyle('LegendStyle', parent=normal_style, fontSize=8, textColor=colors.HexColor('#475569'))))
                story.append(Spacer(1, 10))

        if eval_result.gnn_pharmacophores:
            story.append(Paragraph("Desglose de señales farmacofóricas (GNN)", xai_header_style))

            pharmacophore_rows = [["Señal farmacofórica", "Valor serializado"]]
            for k, v in eval_result.gnn_pharmacophores.items():
                value = f"{v:.1f}%" if isinstance(v, (int, float)) else str(v)
                pharmacophore_rows.append([k, value])

            ph_table = Table(pharmacophore_rows, colWidths=[320, 170])
            ph_table.setStyle(TableStyle([
                ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f1f5f9')),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,-1), 8),
                ('PADDING', (0,0), (-1,-1), 3)
            ]))
            story.append(ph_table)
            story.append(Paragraph(
                "<i>Valores informativos emitidos por el modelo. No se comparan con un control ni con un benchmark por target porque esa procedencia no está serializada en la corrida.</i>",
                ParagraphStyle('GnnEvidenceNote', parent=normal_style, fontSize=7.5, leading=9.5, textColor=SLATE),
            ))

            story.append(Spacer(1, 10))

    # Appendix only: preserve legacy outputs for traceability without placing
    # them in the scientific narrative or decision surface.
    story.append(Paragraph("Apéndice técnico: salidas heredadas", section_title_style))
    story.append(Paragraph(
        "Esta tabla existe únicamente para compatibilidad y auditoría de registros anteriores. Sus escalas no son comparables entre sí y no alimentan la conclusión operativa de este dossier.",
        ParagraphStyle('LegacyAppendixIntro', parent=normal_style, fontSize=8, textColor=SLATE, spaceAfter=5),
    ))
    signal_rows = []
    signal_fields = (
        ("Índice compuesto heredado", eval_result.total_score, " (escala histórica 0-100)"),
        ("Afinidad normalizada heredada", eval_result.affinity_score, " (escala histórica 0-100)"),
        ("Índice ADME heredado", eval_result.adme_score, " (escala histórica 0-100)"),
        ("Índice de reglas heredado", eval_result.druglikeness_score, " (escala histórica 0-100)"),
        ("Índice MPO heredado", eval_result.blood_viability_score, " (escala histórica 0-100)"),
        ("Salida GNN geométrica", eval_result.gnn_score, ""),
        ("Salida CL-GNN", eval_result.clgnn_score, ""),
        ("Salida XGBoost", eval_result.xgb_score, ""),
        ("Salida cuántica", eval_result.quantum_score, ""),
        ("MM-GBSA post-hoc", eval_result.mmgbsa_score, " kcal/mol"),
    )
    for label, value, suffix in signal_fields:
        if value is not None:
            signal_rows.append([label, f"{value:.3f}{suffix}"])
    if eval_result.target_family:
        signal_rows.append(["Familia estructural", eval_result.target_family.upper()])
    if signal_rows:
        signal_table = Table([["Señal", "Valor serializado"]] + signal_rows, colWidths=[245, 245], repeatRows=1)
        signal_table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.5, LINE),
            ('BACKGROUND', (0, 0), (-1, 0), HEAD_BG),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('PADDING', (0, 0), (-1, -1), 4),
            ('ALIGN', (1, 1), (1, -1), 'CENTER'),
        ]))
        story.append(signal_table)
    story.append(Paragraph(
        "Ninguna de estas salidas es una probabilidad de unión, eficacia, seguridad o éxito experimental. Para decidir el siguiente paso debe usarse la matriz de evidencia y sus flags de abstención.",
        ParagraphStyle('ScoringTrans', parent=normal_style, fontSize=8, textColor=SLATE, spaceBefore=5),
    ))
    story.append(Spacer(1, 4))

    # Pesos y factores que el pipeline serializó en esta corrida.
    weights_parts = []
    if getattr(eval_result, "stacking_vina_weight", None) is not None:
        weights_parts.append(f"Vina {eval_result.stacking_vina_weight:.2f}")
    if getattr(eval_result, "stacking_xgb_weight", None) is not None:
        weights_parts.append(f"XGBoost {eval_result.stacking_xgb_weight:.2f}")
    # El peso de CL-GNN es `stacking_clgnn_weight`. Hasta v17 este PDF imprimia
    # aqui `stacking_gnn_weight` -la GNN legacy- bajo la etiqueta «CL-GNN»:
    # atribuia la influencia al modelo equivocado dentro del documento que un
    # tercero lee como evidencia.
    if getattr(eval_result, "stacking_clgnn_weight", None) is not None:
        weights_parts.append(f"CL-GNN {eval_result.stacking_clgnn_weight:.2f}")
    if getattr(eval_result, "stacking_gnn_weight", None):
        weights_parts.append(f"GNN legacy {eval_result.stacking_gnn_weight:.2f}")
    if weights_parts:
        story.append(Paragraph(
            f"<b>Pesos de combinación registrados (familia {eval_result.target_family.upper() if eval_result.target_family else 'N/A'}):</b> " + " / ".join(weights_parts),
            ParagraphStyle('StackWeights', parent=normal_style, fontSize=8, textColor=SLATE)
        ))

    factor_parts = []
    if getattr(eval_result, "affinity_multiplier", None) is not None:
        factor_parts.append(f"Afinidad ×{eval_result.affinity_multiplier:.2f}")
    if getattr(eval_result, "specificity_multiplier", None) is not None:
        factor_parts.append(f"Especificidad ×{eval_result.specificity_multiplier:.2f}")
    if factor_parts:
        story.append(Paragraph(
            "<b>Factores correctivos registrados:</b> " + " / ".join(factor_parts),
            ParagraphStyle('ScoreFactors', parent=normal_style, fontSize=8, textColor=SLATE)
        ))
    story.append(Spacer(1, 10))

    # BLOCKCHAIN - Conditional rendering
    if eval_result.blockchain_tx_id:
        story.append(Paragraph("Integridad y registro temporal (Solana)", section_title_style))
        tx_id = eval_result.blockchain_tx_id
        link = f"https://explorer.solana.com/tx/{tx_id}?cluster=devnet"

        bc_data = [
            [Paragraph("<b>Firma de Transacción:</b>", normal_style), Paragraph(tx_id, mono_style)],
            [Paragraph("<b>Hash del Registro:</b>", normal_style), Paragraph(getattr(eval_result, "blockchain_hash", None) or "N/A", mono_style)],
            [Paragraph("<b>Enlace de Verificación:</b>", normal_style), Paragraph(f'<a href="{link}" color="blue">{link}</a>', mono_style)]
        ]

        bc_table = Table(bc_data, colWidths=[120, 370])
        bc_table.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ]))
        story.append(bc_table)
    else:
        story.append(Paragraph("Integridad y registro temporal (Solana)", section_title_style))
        story.append(Paragraph("<i>La huella de este dossier todavía no está registrada en Solana. El registro acredita integridad y fecha, no descubrimiento ni validez científica.</i>", normal_style))

    # OBSERVED METHODOLOGY - only facts serialized by this run.
    story.append(Spacer(1, 10))
    story.append(Paragraph("Metodología observada y procedencia", section_title_style))

    methodology_style = ParagraphStyle(
        'MethodologyText',
        parent=styles['Normal'],
        fontSize=7,
        leading=9.5,
        textColor=colors.HexColor('#475569'),
        alignment=4 # Justified
    )

    cofactor_whitelist = getattr(getattr(mol, "target", None), "cofactors_whitelist", None) or []
    cofactor_note = ", ".join(str(item) for item in cofactor_whitelist) if cofactor_whitelist else "sin whitelist registrada"
    methodology_text = (
        f"<b>Sistema de entrada:</b> receptor {pdb_upper or 'N/A'}, estado de preparación "
        f"{evidence_summary['target_readiness'].replace('_', ' ')}, cofactores: {cofactor_note}. "
        "El dossier no atribuye protonación, eliminación de aguas, minimización ni estados de carga cuando esas operaciones no fueron serializadas por la corrida.<br/>"
        f"<b>Exploración de poses:</b> el resultado registra {evidence_summary['pose_count']} poses, "
        f"motor {eval_result.vina_version or 'no informado'}, semilla "
        f"{eval_result.vina_random_seed if eval_result.vina_random_seed is not None else 'no informada'} y parser "
        f"{eval_result.parsing_source or 'no informado'}. Las afinidades son señales de la función de scoring y ranking; no son medidas experimentales de energía libre.<br/>"
        f"<b>Modelos derivados:</b> motor {model_context['engine'] or 'no informado'}, modelo "
        f"{model_context['model'] or 'no informado'}, {domain_label}. "
        "Cada salida se reporta por separado; el dossier no convierte el índice compuesto heredado en una conclusión científica.<br/>"
        "<b>Validez física:</b> no evaluada en esta versión de producción. El análisis geométrico externo debe documentarse antes de cálculos posteriores o decisiones experimentales."
    )
    story.append(Paragraph(methodology_text, methodology_style))
    story.append(Spacer(1, 8))

    # TECHNICAL TRACE - no hard-coded versions.
    story.append(Paragraph("Trazas técnicas registradas", xai_header_style))

    tech_style = ParagraphStyle(
        'TechText',
        parent=styles['Normal'],
        fontSize=6.5,
        leading=8.5,
        textColor=colors.HexColor('#64748b')
    )

    tech_info = (
        f"- <b>Motor de docking:</b> {eval_result.vina_version or 'no informado'}<br/>"
        f"- <b>Semilla:</b> {eval_result.vina_random_seed if eval_result.vina_random_seed is not None else 'no informada'}<br/>"
        f"- <b>Parser de poses:</b> {eval_result.parsing_source or 'no informado'}<br/>"
        f"- <b>Motor/modelo derivado:</b> {model_label}<br/>"
        f"- <b>Dominio de aplicabilidad:</b> {domain_label}<br/>"
        f"- <b>Fallback:</b> {model_context['fallback_reason'] or 'no registrado'}"
    )
    story.append(Paragraph(tech_info, tech_style))

    # ── Scientific Caveats / Limitaciones ───────────────────────────
    caveat_title = Paragraph(
        "Limitaciones Cientificas del Analisis Computacional",
        ParagraphStyle('CaveatTitle', parent=section_title_style, fontSize=9, textColor=colors.HexColor('#64748b'))
    )

    caveats = (
        "· <b>Naturaleza computacional:</b> Todas las predicciones presentadas en este documento "
        "provienen de modelos computacionales (AutoDock Vina, XGBoost, RDKit). "
        "NO constituyen evidencia experimental y DEBEN ser validadas mediante ensayos in vitro e in vivo.<br/><br/>"

        "· <b>Alcance del docking:</b> Las afinidades son valores de una funcion de scoring y sirven para ranking dentro de un protocolo. "
        "No constituyen mediciones de energia libre. Las poses son hipotesis estructurales y no representan la flexibilidad completa del receptor ni el solvente explicito.<br/><br/>"

        "· <b>Limitaciones ADMET:</b> Las predicciones de toxicidad y farmacocinetica provienen "
        "de modelos QSAR entrenados en datos historicos. Pueden no generalizar a quimiotipos novedosos. "
        "Los falsos negativos en cardiotoxicidad (hERG) y hepatotoxicidad son posibles.<br/><br/>"

        "· <b>PAINS y falsos positivos:</b> Los filtros PAINS cubren ~480 subestructuras conocidas "
        "pero no son exhaustivos. Pueden existir otros mecanismos de interferencia en ensayos "
        "no cubiertos por estos filtros.<br/><br/>"

        "· <b>Selectividad:</b> " +
        (f"Se evaluo la selectividad frente a {len(anti_results)} anti-targets (ratio: {selectivity_ratio:.1f}x). " if selectivity_ran and anti_results else
         "Este analisis evalua la afinidad contra UN solo target biologico. ") +
        "La selectividad in vivo puede diferir debido a metabolitos activos, union a proteinas plasmaticas y efectos de dosis.<br/><br/>"

        "· <b>Sintesis:</b> El SA Score es una estimacion heuristica de la dificultad sintetica. "
        "No reemplaza el analisis de un quimico medicinal experimentado ni un estudio "
        "de retrosintesis completo.<br/><br/>"

        "· <b>Reproducibilidad:</b> Este dossier registra version del motor, semilla y parser cuando el pipeline los entrega. "
        "Los campos ausentes quedan marcados y deben completarse antes de comparar corridas.<br/><br/>"

        "· <b>Validez fisica:</b> La version actual no ejecuta un validador geometrico de poses en produccion. "
        "Ausencia de alertas no significa ausencia de choques, enlaces imposibles o artefactos de preparacion.<br/><br/>"

        "<b>Este reporte es una herramienta de apoyo a la investigacion. "
        "Las decisiones sobre desarrollo de farmacos deben basarse en evidencia experimental "
        "y criterio cientifico profesional.</b>"
    )

    caveat_style = ParagraphStyle(
        'Caveats',
        fontSize=6.5,
        textColor=colors.HexColor('#94a3b8'),
        leading=9,
        leftIndent=6,
        rightIndent=6,
    )
    footer_text = "<font color='#94a3b8' size='7'><i>Generado localmente por MolDesign. Uso no comercial bajo PolyForm Noncommercial 1.0.0; uso comercial sujeto a licencia separada.<br/>Código y plataforma: https://github.com/srcacahuate619/moldesign-app</i></font>"
    story.append(KeepTogether([
        Spacer(1, 12),
        caveat_title,
        Spacer(1, 4),
        Paragraph(caveats, caveat_style),
        Spacer(1, 10),
        Paragraph(footer_text, ParagraphStyle('Footer', alignment=1)),
    ]))

    # Set canvas properties for NumberedCanvas before build
    def on_first_page(canvas_obj, doc_obj):
        pass # placeholder if needed

    doc.target_info = f"{mol.target.pdb_id.upper() if mol.target else 'N/A'} ({target_name})"
    doc.affinity_info = f"{eval_result.affinity_kcal:.2f} kcal/mol" if eval_result.affinity_kcal is not None else "N/A"
    doc.score_info = f"Estado: {evidence_summary['label']}"

    # Feed custom canvas info during build
    def canvas_maker(*args, **kwargs):
        c = NumberedCanvas(*args, **kwargs)
        c.target_info = doc.target_info
        c.affinity_info = doc.affinity_info
        c.score_info = doc.score_info
        return c

    doc.build(story, canvasmaker=canvas_maker)
    buf.seek(0)
    return buf
