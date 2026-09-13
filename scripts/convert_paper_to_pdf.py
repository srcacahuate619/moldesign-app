"""
scripts/convert_paper_to_pdf.py — Convert PAPER_UMS.md to a beautiful, highly-legible PDF.
"""

import os
import re
import subprocess
from pathlib import Path
import markdown

PROJECT_DIR = Path(__file__).resolve().parent.parent
DOCS_DIR = PROJECT_DIR / "docs"
MD_FILE = DOCS_DIR / "PAPER_UMS.md"
HTML_FILE = DOCS_DIR / "PAPER_UMS.html"
PDF_FILE = DOCS_DIR / "PAPER_UMS.pdf"

def clean_latex(text: str) -> str:
    """Replace inline LaTeX dollar math markers with clean Unicode equivalents.

    IMPORTANT: `$$...$$` display-math blocks are PRESERVED (they are rendered
    by the markdown->HTML pipeline via the 'math' extension), while inline
    `$...$` markers are converted to Unicode. The old blanket regex
    `\$([^$]+)\$` destroyed `$$...$$` blocks (e.g., the MolChamb equation in
    §2.1.6); we now protect display blocks first.
    """
    # Protect display-math blocks $$...$$ with a placeholder
    _DISPLAY = "__DISPLAY_MATH__"
    displays = []
    def _capture(m):
        displays.append(m.group(0))
        return f"{_DISPLAY}{len(displays)-1}{_DISPLAY}"

    text = re.sub(r"\$\$(.+?)\$\$", _capture, text, flags=re.DOTALL)

    text = text.replace(r"$\Delta = +0.122$", "Δ = +0.122")
    text = text.replace(r"$\Delta = +0.067$", "Δ = +0.067")
    text = text.replace(r"$\Delta = +0.240$", "Δ = +0.240")
    text = text.replace(r"$\Delta\text{AUC}$", "Δ AUC")
    text = text.replace(r"$p < 0.0001$", "p < 0.0001")
    text = text.replace(r"$n = 500$", "n = 500")
    text = text.replace(r"$r = 0.027, p = 0.38$", "r = 0.027, p = 0.38")
    # General regex replacement for simple $\Delta...$ — but only SINGLE dollars
    text = re.sub(r"\$\\Delta\\text\{([^}]+)\}\$", r"Δ \1", text)
    text = re.sub(r"\$\\Delta\$", "Δ", text)
    text = re.sub(r"\$([^$]+)\$", r"\1", text)

    # Restore display-math blocks
    for i, disp in enumerate(displays):
        text = text.replace(f"{_DISPLAY}{i}{_DISPLAY}", disp)
    return text

def build_html():
    with open(MD_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    content = clean_latex(content)

    # Convert markdown to html
    html_body = markdown.markdown(
        content,
        extensions=[
            "tables",
            "fenced_code",
            "toc",
            "attr_list",
            "sane_lists"
        ]
    )

    # Custom academic CSS tailored for readability and crisp rendering
    css = """
    @page {
        size: A4 portrait;
        margin: 20mm 20mm 22mm 20mm;
    }

    body {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
        font-size: 15px;
        line-height: 1.65;
        color: #1e293b;
        background-color: #ffffff;
        margin: 0;
        padding: 0;
    }

    /* Cover / Header styling */
    h1 {
        font-size: 24px;
        font-weight: 700;
        color: #0f172a;
        margin-top: 0;
        margin-bottom: 12px;
        line-height: 1.3;
        border-bottom: 2px solid #2563eb;
        padding-bottom: 10px;
    }

    h2 {
        font-size: 19px;
        font-weight: 700;
        color: #1e3a8a;
        margin-top: 28px;
        margin-bottom: 14px;
        border-bottom: 1px solid #e2e8f0;
        padding-bottom: 6px;
        page-break-after: avoid;
    }

    h3 {
        font-size: 16px;
        font-weight: 600;
        color: #1e293b;
        margin-top: 20px;
        margin-bottom: 10px;
        page-break-after: avoid;
    }

    h4 {
        font-size: 15px;
        font-weight: 600;
        color: #334155;
        margin-top: 16px;
        margin-bottom: 8px;
        page-break-after: avoid;
    }

    p {
        margin-top: 0;
        margin-bottom: 12px;
        text-align: justify;
    }

    strong {
        color: #0f172a;
    }

    hr {
        border: none;
        border-top: 1px solid #cbd5e1;
        margin: 24px 0;
    }

    /* Links */
    a {
        color: #2563eb;
        text-decoration: none;
    }

    /* Lists */
    ul, ol {
        margin-top: 0;
        margin-bottom: 14px;
        padding-left: 24px;
    }

    li {
        margin-bottom: 4px;
    }

    /* Tables */
    table {
        width: 100%;
        border-collapse: collapse;
        margin: 18px 0;
        font-size: 13.5px;
        page-break-inside: avoid;
    }

    th, td {
        border: 1px solid #cbd5e1;
        padding: 8px 12px;
        text-align: left;
    }

    th {
        background-color: #f1f5f9;
        color: #0f172a;
        font-weight: 600;
    }

    tr:nth-child(even) {
        background-color: #f8fafc;
    }

    /* Images / Figures */
    p img {
        display: block;
        max-width: 95%;
        height: auto;
        margin: 16px auto 8px auto;
        border: 1px solid #e2e8f0;
        border-radius: 6px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }

    img {
        page-break-inside: avoid;
    }

    /* Code blocks */
    pre {
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 6px;
        padding: 12px 16px;
        font-family: "Cascadia Code", "Fira Code", Consolas, Monaco, "Courier New", monospace;
        font-size: 13px;
        line-height: 1.5;
        overflow-x: auto;
        margin: 14px 0;
        page-break-inside: avoid;
        white-space: pre-wrap;
        word-wrap: break-word;
    }

    code {
        font-family: "Cascadia Code", "Fira Code", Consolas, Monaco, "Courier New", monospace;
        background-color: #f1f5f9;
        color: #0f172a;
        padding: 2px 5px;
        border-radius: 4px;
        font-size: 13.5px;
    }

    pre code {
        background-color: transparent;
        padding: 0;
        border-radius: 0;
        font-size: 13px;
    }

    /* Blockquotes */
    blockquote {
        border-left: 4px solid #3b82f6;
        background-color: #eff6ff;
        margin: 16px 0;
        padding: 10px 16px;
        color: #1e3a8a;
        border-radius: 0 6px 6px 0;
    }

    blockquote p {
        margin: 0;
        text-align: left;
    }
    """

    full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Universal Metal Score: A Docking-Orthogonal Cheminformatics Feature</title>
    <script>
        window.MathJax = {{
            tex: {{
                inlineMath: [['$', '$'], ['\\\\(', '\\\\)']],
                displayMath: [['$$', '$$'], ['\\\\[', '\\\\]']],
                processEscapes: true
            }},
            svg: {{ fontCache: 'global' }},
            startup: {{
                typeset: true
            }}
        }};
    </script>
    <script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js" async></script>
    <style>{css}</style>
</head>
<body>
{html_body}
</body>
</html>
"""

    with open(HTML_FILE, "w", encoding="utf-8") as f:
        f.write(full_html)

    print(f"[OK] Generated HTML: {HTML_FILE}")

def convert_to_pdf():
    edge_paths = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    ]

    browser_exe = None
    for path in edge_paths:
        if os.path.exists(path):
            browser_exe = path
            break

    if not browser_exe:
        raise RuntimeError("Neither Edge nor Chrome executable found for PDF printing.")

    cmd = [
        browser_exe,
        "--headless",
        "--disable-gpu",
        "--no-pdf-header-footer",
        "--virtual-time-budget=10000",
        f"--print-to-pdf={PDF_FILE}",
        str(HTML_FILE)
    ]

    print(f"Running command: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0 and os.path.exists(PDF_FILE):
        size_mb = os.path.getsize(PDF_FILE) / (1024 * 1024)
        print(f"[SUCCESS] PDF generated successfully: {PDF_FILE} ({size_mb:.2f} MB)")
    else:
        print(f"[ERROR] Failed to generate PDF: {result.stderr}")
        raise RuntimeError(result.stderr)

if __name__ == "__main__":
    build_html()
    convert_to_pdf()
