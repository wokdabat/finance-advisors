"""
Renders docs/SYSTEM_DESIGN_REPORT.md to docs/SYSTEM_DESIGN_REPORT.pdf.

The Markdown file is the single source of truth; this script parses it
(headings, fenced code blocks, a `diagram` fence for the colored
architecture box, bullets, bold lines) and lays it out with fpdf2 --
chosen over a WeasyPrint/HTML pipeline because it has no system-level
dependencies (no Cairo/Pango/GDK-pixbuf), so the report can be rebuilt
on any machine that already has the project's Python deps installed.

Run with:
    python docs/generate_report_pdf.py
"""
from __future__ import annotations

import re
from pathlib import Path

from fpdf import FPDF

DOC_DIR = Path(__file__).parent
SRC_PATH = DOC_DIR / "SYSTEM_DESIGN_REPORT.md"
OUT_PATH = DOC_DIR / "SYSTEM_DESIGN_REPORT.pdf"

RUNNING_HEADER = "FINANCE ADVISORS - SYSTEM DESIGN & ENGINEERING REPORT"

CODE_FILL = (242, 242, 242)
DIAGRAM_FILL = (230, 240, 250)
DIAGRAM_BORDER = (90, 130, 190)
RULE_COLOR = (200, 200, 200)

_PDF_CHAR_REPLACEMENTS = {
    "—": "-", "–": "-",  # em/en dash
    "‘": "'", "’": "'",  # curly single quotes
    "“": '"', "”": '"',  # curly double quotes
    "…": "...",  # ellipsis
    " ": " ",  # non-breaking space
    "•": "-",  # bullet
    "↓": "v",  # diagram flow arrow (core fonts have no arrow glyph)
    "→": "->",  # inline flow arrow (core fonts have no arrow glyph)
}


def _pdf_safe(text: str) -> str:
    """Core PDF fonts only support Latin-1; normalize common Unicode
    typography to ASCII, then fall back to replacing anything else so
    rendering can never crash on an unexpected character."""
    for src, dst in _PDF_CHAR_REPLACEMENTS.items():
        text = text.replace(src, dst)
    return text.encode("latin-1", "replace").decode("latin-1")


_INLINE_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def _strip_inline_markdown(text: str) -> str:
    text = _INLINE_LINK_RE.sub(r"\1 (\2)", text)
    text = text.replace("**", "").replace("`", "")
    return text


class ReportPDF(FPDF):
    def header(self):
        if self.page_no() == 1:
            return
        self.set_font("helvetica", size=9)
        self.set_text_color(130, 130, 130)
        self.cell(0, 8, RUNNING_HEADER, align="C")
        self.set_text_color(0, 0, 0)
        self.set_y(22)

    def footer(self):
        self.set_y(-15)
        self.set_font("helvetica", size=9)
        self.set_text_color(130, 130, 130)
        self.cell(0, 10, f"Page {self.page_no()} of {{nb}}", align="C")
        self.set_text_color(0, 0, 0)


def _wrap_monospace_line(pdf: FPDF, line: str, max_w: float, font_size: float) -> list[str]:
    """Hard-wrap a monospace line to fit max_w, preserving leading indentation
    on the first physical line. Continuation lines are indented 2 spaces."""
    pdf.set_font("courier", size=font_size)
    if pdf.get_string_width(line) <= max_w:
        return [line]
    char_w = pdf.get_string_width("M")
    max_chars = max(1, int(max_w / char_w))
    chunks = []
    remaining = line
    while len(remaining) > max_chars:
        chunks.append(remaining[:max_chars])
        remaining = "  " + remaining[max_chars:]
    chunks.append(remaining)
    return chunks


def render_code_box(pdf: FPDF, lines: list[str], *, diagram: bool = False) -> None:
    fill = DIAGRAM_FILL if diagram else CODE_FILL
    border = DIAGRAM_BORDER if diagram else None
    font_size = 8.5
    line_h = 4.6
    pad = 4
    usable_w = pdf.w - pdf.l_margin - pdf.r_margin
    text_w = usable_w - 2 * pad

    wrapped: list[str] = []
    for line in lines:
        wrapped.extend(_wrap_monospace_line(pdf, line, text_w, font_size))
    lines = wrapped

    content_h = len(lines) * line_h + 2 * pad

    if pdf.get_y() + content_h > pdf.page_break_trigger:
        pdf.add_page()

    x0, y0 = pdf.l_margin, pdf.get_y()
    pdf.set_fill_color(*fill)
    if border:
        pdf.set_draw_color(*border)
        pdf.rect(x0, y0, usable_w, content_h, style="DF")
    else:
        pdf.rect(x0, y0, usable_w, content_h, style="F")

    pdf.set_font("courier", size=font_size)
    for line in lines:
        pdf.set_xy(x0 + pad, pdf.get_y() if pdf.get_y() > y0 else y0 + pad)
        pdf.cell(usable_w - 2 * pad, line_h, line, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", size=11)
    pdf.set_y(y0 + content_h + 4)
    pdf.set_x(pdf.l_margin)


def render_bullet(pdf: FPDF, text: str) -> None:
    usable_w = pdf.w - pdf.l_margin - pdf.r_margin
    pdf.set_x(pdf.l_margin + 5)
    pdf.multi_cell(usable_w - 5, 6, f"- {text}", new_x="LMARGIN", new_y="NEXT")
    pdf.set_x(pdf.l_margin)


def render_paragraph(pdf: FPDF, text: str, *, bold: bool = False, italic: bool = False) -> None:
    style = ("B" if bold else "") + ("I" if italic else "")
    pdf.set_font("helvetica", style, 11)
    pdf.multi_cell(0, 6, text, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", size=11)


def render_h2(pdf: FPDF, text: str) -> None:
    pdf.add_page()
    pdf.start_section(text, level=0)
    pdf.set_font("helvetica", "B", 16)
    pdf.multi_cell(0, 9, text, new_x="LMARGIN", new_y="NEXT")
    y = pdf.get_y()
    pdf.set_draw_color(*RULE_COLOR)
    pdf.line(pdf.l_margin, y, pdf.w - pdf.r_margin, y)
    pdf.ln(4)
    pdf.set_font("helvetica", size=11)


def render_h3(pdf: FPDF, text: str) -> None:
    pdf.start_section(text, level=1)
    pdf.ln(2)
    pdf.set_font("helvetica", "B", 12.5)
    pdf.multi_cell(0, 7, text, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)
    pdf.set_font("helvetica", size=11)


def parse_front_matter(lines: list[str]) -> tuple[str, list[str], int]:
    """Returns (title, subtitle_lines, index_of_first_real_section)."""
    idx = 0
    while not lines[idx].startswith("# "):
        idx += 1
    title = lines[idx][2:].strip()
    idx += 1
    while idx < len(lines) and not lines[idx].strip():
        idx += 1
    subtitle_lines = []
    while idx < len(lines) and lines[idx].strip() and not lines[idx].startswith("#"):
        subtitle_lines.append(lines[idx].strip())
        idx += 1
    # Skip the manual "## Table of Contents" block entirely -- a real
    # page-numbered, clickable TOC is generated by fpdf2 instead.
    while idx < len(lines) and lines[idx].strip() != "## Table of Contents":
        idx += 1
    idx += 1
    seen_next_heading = False
    while idx < len(lines) and not seen_next_heading:
        if lines[idx].startswith("## "):
            seen_next_heading = True
        else:
            idx += 1
    return title, subtitle_lines, idx


def render_title_page(pdf: FPDF, title: str, subtitle_lines: list[str]) -> None:
    pdf.add_page()
    pdf.ln(50)
    pdf.set_font("helvetica", "B", 22)
    pdf.multi_cell(0, 11, _pdf_safe(title), align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    y = pdf.get_y()
    pdf.set_draw_color(40, 70, 140)
    pdf.set_line_width(1)
    pdf.line(pdf.w / 2 - 40, y, pdf.w / 2 + 40, y)
    pdf.set_line_width(0.2)
    pdf.ln(8)
    pdf.set_font("helvetica", "B", 12)
    for line in subtitle_lines:
        pdf.multi_cell(0, 7, _pdf_safe(line), align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("helvetica", size=11)


def render_toc(pdf: FPDF, outline) -> None:
    pdf.set_font("helvetica", "B", 18)
    pdf.cell(0, 10, "Table of Contents", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    pdf.set_font("helvetica", size=11)
    for section in outline:
        link = pdf.add_link(page=section.page_number)
        indent = "    " * section.level
        label = f"{indent}{section.name}"
        page_str = str(section.page_number)
        dots_width = pdf.w - pdf.l_margin - pdf.r_margin
        pdf.set_x(pdf.l_margin)
        pdf.cell(dots_width - 12, 7, label, new_x="END", new_y="TOP", link=link)
        pdf.cell(12, 7, page_str, align="R", new_x="LMARGIN", new_y="NEXT", link=link)


def build_pdf() -> None:
    raw_lines = SRC_PATH.read_text(encoding="utf-8").splitlines()
    title, subtitle_lines, body_start = parse_front_matter(raw_lines)
    body_lines = raw_lines[body_start:]

    pdf = ReportPDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.set_font("helvetica", size=11)

    render_title_page(pdf, title, subtitle_lines)

    pdf.add_page()
    pdf.insert_toc_placeholder(render_toc, pages=1)

    in_code = False
    fence_lang = ""
    code_buffer: list[str] = []

    for raw_line in body_lines:
        line = _pdf_safe(raw_line)
        stripped = line.strip()

        if stripped.startswith("```"):
            if not in_code:
                in_code = True
                fence_lang = stripped[3:].strip()
                code_buffer = []
            else:
                render_code_box(pdf, code_buffer, diagram=(fence_lang == "diagram"))
                in_code = False
                fence_lang = ""
            continue

        if in_code:
            code_buffer.append(line.rstrip())
            continue

        if stripped.startswith("## "):
            render_h2(pdf, stripped[3:])
        elif stripped.startswith("### "):
            render_h3(pdf, stripped[4:])
        elif not stripped:
            pdf.ln(3)
        elif stripped.startswith("- "):
            render_bullet(pdf, _strip_inline_markdown(stripped[2:]))
        elif stripped.startswith("> "):
            render_paragraph(pdf, _strip_inline_markdown(stripped[2:]), italic=True)
        elif stripped.startswith("**") and stripped.endswith("**") and len(stripped) > 4:
            render_paragraph(pdf, _strip_inline_markdown(stripped), bold=True)
        else:
            render_paragraph(pdf, _strip_inline_markdown(stripped))

    pdf.output(str(OUT_PATH))
    print(f"Wrote {OUT_PATH} ({OUT_PATH.stat().st_size:,} bytes, {pdf.page_no()} pages)")


if __name__ == "__main__":
    build_pdf()
