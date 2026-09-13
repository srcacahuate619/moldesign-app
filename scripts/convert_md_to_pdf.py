import os
import sys
import re
import markdown
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, HRFlowable
)
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    """
    Two-pass canvas to add headers and 'Página X de Y' footers dynamically.
    """
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
            self.draw_header_footer(num_pages)
            super().showPage()
        super().save()

    def draw_header_footer(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))
        
        # Suppress header/footer on page 1 (Title/Cover page)
        if self._pageNumber > 1:
            # Header
            self.drawString(54, 750, "MolDesign AI — Documentación Técnica & Deck Ejecutivo")
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.5)
            self.line(54, 744, 558, 744)
            
            # Footer
            page_text = f"Página {self._pageNumber} de {page_count}"
            self.drawRightString(558, 36, page_text)
            self.drawString(54, 36, "Confidencial — Uso Institucional & Académico")
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.5)
            self.line(54, 48, 558, 48)
            
        self.restoreState()


def md_to_reportlab_xml(text):
    """
    Converts markdown text to clean XML supported by ReportLab Paragraph parser.
    """
    if not text:
        return ""
        
    # Use python-markdown for robust inline HTML parsing
    html = markdown.markdown(text, extensions=['tables', 'fenced_code'])
    
    # Unwrap paragraph tags if present for single lines
    if html.startswith("<p>") and html.endswith("</p>") and html.count("<p>") == 1:
        html = html[3:-4]
        
    # Convert standard HTML tags to ReportLab XML equivalents
    html = re.sub(r'<code>(.*?)</code>', r'<font face="Courier" color="#0F766E"><b>\1</b></font>', html, flags=re.DOTALL)
    html = re.sub(r'<a href="[^"]*">(.*?)</a>', r'<u><b>\1</b></u>', html, flags=re.DOTALL)
    html = html.replace("<br>", "<br/>").replace("<hr>", "<hr/>")
    
    # Sanitize unclosed or illegal tags for ReportLab
    # Ensure & is &amp; unless part of an existing entity
    html = re.sub(r'&(?!(amp|lt|gt|quot|apos);)', '&amp;', html)
    
    return html.strip()


def markdown_to_flowables(md_content, styles):
    flowables = []
    lines = md_content.splitlines()
    i = 0
    n = len(lines)
    
    in_code_block = False
    code_lines = []
    
    while i < n:
        line = lines[i]
        
        # Code Blocks ```
        if line.strip().startswith("```"):
            if in_code_block:
                # End code block
                code_text = "<br/>".join(
                    [l.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace(" ", "&nbsp;") for l in code_lines]
                )
                p = Paragraph(code_text, styles['CodeBlock'])
                
                t = Table([[p]], colWidths=[504])
                t.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#0F172A")),
                    ('TOPPADDING', (0,0), (-1,-1), 8),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 8),
                    ('LEFTPADDING', (0,0), (-1,-1), 10),
                    ('RIGHTPADDING', (0,0), (-1,-1), 10),
                ]))
                flowables.append(Spacer(1, 6))
                flowables.append(t)
                flowables.append(Spacer(1, 8))
                in_code_block = False
                code_lines = []
            else:
                in_code_block = True
                code_lines = []
            i += 1
            continue
            
        if in_code_block:
            code_lines.append(line)
            i += 1
            continue
            
        # Empty lines
        if not line.strip():
            i += 1
            continue
            
        # Markdown Tables
        if "|" in line and i + 1 < n and "|---" in lines[i+1]:
            table_data = []
            headers = [md_to_reportlab_xml(cell.strip()) for cell in line.split("|")[1:-1]]
            table_data.append([Paragraph(f"<b>{h}</b>", styles['TableHeader']) for h in headers])
            
            i += 2  # skip header and separator line
            while i < n and "|" in lines[i]:
                row_cells = [md_to_reportlab_xml(cell.strip()) for cell in lines[i].split("|")[1:-1]]
                if row_cells:
                    table_data.append([Paragraph(c, styles['TableCell']) for c in row_cells])
                i += 1
                
            num_cols = len(headers)
            col_width = 504.0 / max(num_cols, 1)
            t = Table(table_data, colWidths=[col_width]*num_cols)
            t.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0F172A")),
                ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                ('VALIGN', (0,0), (-1,-1), 'TOP'),
                ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
                ('TOPPADDING', (0,0), (-1,-1), 5),
                ('BOTTOMPADDING', (0,0), (-1,-1), 5),
                ('LEFTPADDING', (0,0), (-1,-1), 5),
                ('RIGHTPADDING', (0,0), (-1,-1), 5),
                ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#F8FAFC")]),
            ]))
            flowables.append(Spacer(1, 6))
            flowables.append(t)
            flowables.append(Spacer(1, 8))
            continue

        # Horizontal Rule ---
        if line.strip() in ["---", "***", "___"]:
            flowables.append(Spacer(1, 6))
            flowables.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#E2E8F0"), spaceAfter=8))
            i += 1
            continue

        # Blockquotes >
        if line.strip().startswith(">"):
            quote_lines = []
            while i < n and lines[i].strip().startswith(">"):
                quote_lines.append(lines[i].strip().lstrip(">").strip())
                i += 1
            quote_text = md_to_reportlab_xml(" ".join(quote_lines))
            p = Paragraph(quote_text, styles['BlockQuote'])
            t = Table([[p]], colWidths=[504])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F0F9FF")),
                ('LEFTPADDING', (0,0), (-1,-1), 12),
                ('RIGHTPADDING', (0,0), (-1,-1), 10),
                ('TOPPADDING', (0,0), (-1,-1), 8),
                ('BOTTOMPADDING', (0,0), (-1,-1), 8),
                ('LINELEFT', (0,0), (0,0), 3, colors.HexColor("#0284C7")),
            ]))
            flowables.append(Spacer(1, 6))
            flowables.append(t)
            flowables.append(Spacer(1, 8))
            continue

        # Headings #
        if line.startswith("# "):
            text = md_to_reportlab_xml(line[2:].strip())
            flowables.append(Spacer(1, 10))
            flowables.append(Paragraph(text, styles['H1']))
            flowables.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#0284C7"), spaceAfter=8))
            i += 1
            continue
        if line.startswith("## "):
            text = md_to_reportlab_xml(line[3:].strip())
            flowables.append(Spacer(1, 8))
            flowables.append(Paragraph(text, styles['H2']))
            i += 1
            continue
        if line.startswith("### "):
            text = md_to_reportlab_xml(line[4:].strip())
            flowables.append(Spacer(1, 6))
            flowables.append(Paragraph(text, styles['H3']))
            i += 1
            continue
        if line.startswith("#### "):
            text = md_to_reportlab_xml(line[5:].strip())
            flowables.append(Spacer(1, 5))
            flowables.append(Paragraph(text, styles['H4']))
            i += 1
            continue

        # Bullet Lists - or *
        if line.strip().startswith("- ") or line.strip().startswith("* "):
            bullet_text = md_to_reportlab_xml(line.strip()[2:])
            flowables.append(Paragraph(f"• {bullet_text}", styles['BulletItem']))
            i += 1
            continue

        # Numbered Lists 1. 2. etc
        m_num = re.match(r'^(\d+)\.\s+(.*)', line.strip())
        if m_num:
            num = m_num.group(1)
            item_text = md_to_reportlab_xml(m_num.group(2))
            flowables.append(Paragraph(f"<b>{num}.</b> {item_text}", styles['NumberedItem']))
            i += 1
            continue

        # Normal Paragraph
        para_text = md_to_reportlab_xml(line.strip())
        if para_text:
            flowables.append(Paragraph(para_text, styles['Body']))
            flowables.append(Spacer(1, 4))
        i += 1

    return flowables


def build_pdf_from_md(md_file_path, pdf_file_path):
    print(f"Reading: {md_file_path}")
    with open(md_file_path, 'r', encoding='utf-8') as f:
        md_content = f.read()

    styles = getSampleStyleSheet()
    
    # Custom Palette & Typography
    styles.add(ParagraphStyle('H1', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=18, leading=22, textColor=colors.HexColor('#0F172A'), spaceAfter=6))
    styles.add(ParagraphStyle('H2', parent=styles['Heading2'], fontName='Helvetica-Bold', fontSize=13, leading=17, textColor=colors.HexColor('#1E293B'), spaceBefore=8, spaceAfter=4))
    styles.add(ParagraphStyle('H3', parent=styles['Heading3'], fontName='Helvetica-Bold', fontSize=10.5, leading=14, textColor=colors.HexColor('#0284C7'), spaceBefore=6, spaceAfter=3))
    styles.add(ParagraphStyle('H4', parent=styles['Heading4'], fontName='Helvetica-Bold', fontSize=9, leading=12, textColor=colors.HexColor('#334155'), spaceBefore=4, spaceAfter=2))
    styles.add(ParagraphStyle('Body', parent=styles['Normal'], fontName='Helvetica', fontSize=8.5, leading=12, textColor=colors.HexColor('#334155'), spaceAfter=3))
    styles.add(ParagraphStyle('BulletItem', parent=styles['Normal'], fontName='Helvetica', fontSize=8.5, leading=12, textColor=colors.HexColor('#334155'), leftIndent=12, spaceAfter=2))
    styles.add(ParagraphStyle('NumberedItem', parent=styles['Normal'], fontName='Helvetica', fontSize=8.5, leading=12, textColor=colors.HexColor('#334155'), leftIndent=12, spaceAfter=2))
    styles.add(ParagraphStyle('BlockQuote', parent=styles['Normal'], fontName='Helvetica-Oblique', fontSize=8, leading=11, textColor=colors.HexColor('#1E293B')))
    styles.add(ParagraphStyle('CodeBlock', parent=styles['Normal'], fontName='Courier', fontSize=7, leading=9, textColor=colors.HexColor('#38BDF8')))
    styles.add(ParagraphStyle('TableHeader', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=7.5, leading=10, textColor=colors.white))
    styles.add(ParagraphStyle('TableCell', parent=styles['Normal'], fontName='Helvetica', fontSize=7, leading=9, textColor=colors.HexColor('#1E293B')))

    flowables = markdown_to_flowables(md_content, styles)

    doc = SimpleDocTemplate(
        pdf_file_path,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )

    doc.build(flowables, canvasmaker=NumberedCanvas)
    print(f"Successfully generated PDF: {pdf_file_path}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python convert_md_to_pdf.py <input.md> <output.pdf>")
        sys.exit(1)
        
    input_md = sys.argv[1]
    output_pdf = sys.argv[2]
    build_pdf_from_md(input_md, output_pdf)
