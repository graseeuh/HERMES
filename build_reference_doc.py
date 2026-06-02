from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

doc = Document()

section = doc.sections[0]
section.left_margin   = Inches(1)
section.right_margin  = Inches(1)
section.top_margin    = Inches(1)
section.bottom_margin = Inches(1)

# ── helpers ────────────────────────────────────────────────────────────────

def set_cell_bg(cell, hex_color, theme_fill=None):
    tc   = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd  = OxmlElement('w:shd')
    shd.set(qn('w:val'),   'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'),  hex_color)
    if theme_fill:
        shd.set(qn('w:themeFill'), theme_fill)
    tcPr.append(shd)

def set_cell_borders(cell, color='404040', theme='text2'):
    tc   = cell._tc
    tcPr = tc.get_or_add_tcPr()
    borders = OxmlElement('w:tcBorders')
    for side in ('top', 'left', 'bottom', 'right'):
        el = OxmlElement(f'w:{side}')
        el.set(qn('w:val'),        'single')
        el.set(qn('w:sz'),         '4')
        el.set(qn('w:space'),      '0')
        el.set(qn('w:color'),      color)
        el.set(qn('w:themeColor'), theme)
        borders.append(el)
    tcPr.append(borders)

def run(para, text, bold=False, color=None, size=9, italic=False):
    r = para.add_run(text)
    r.bold        = bold
    r.italic      = italic
    r.font.name   = 'Arial'
    r.font.size   = Pt(size)
    if color:
        r.font.color.rgb = RGBColor(*bytes.fromhex(color))
    return r

# ── Intro paragraph ────────────────────────────────────────────────────────

p = doc.add_paragraph()
p.paragraph_format.space_after = Pt(10)
run(p, 'The adaptation projects identified in this plan are informed by the ', size=11)
run(p, '2026 Vulnerability Assessment and Stormwater Model Update Technical Report',
    bold=True, size=11)
run(p, (', and are aligned with projects, recommendations, and priorities identified '
        'in eleven existing plans and studies for Village of Estero. For ease of '
        'reference, each source has been assigned a number below and is cited by that '
        'number in the project sheets.'), size=11)

doc.add_paragraph()

# ── Source reference table ─────────────────────────────────────────────────

# Colors from ScrollTableNormal style in the source document
ORANGE    = 'FF8200'   # header fill (accent2)
GRAY_BG   = 'D0CFCD'   # band2 alternating rows
WHITE     = 'FFFFFF'
DARK_GRAY = '404040'

sources = [
    (1,  '2018 Village of Estero Comprehensive Plan'),
    (2,  '2018 Village of Estero Stormwater Master Plan'),
    (3,  '2023 Village of Estero Flood Mitigation Project Memorandum'),
    (4,  '2025 Village of Estero Hazard Mitigation Grant Program Memorandum: Pond Design'),
    (5,  '2022 Lee County Joint Local Mitigation Strategy'),
    (6,  '2024 Village of Estero Narrative Provided to FEMA'),
    (7,  '2018 Estero River, Imperial River, & Springs Creek Storm Assessment Summary Report'),
    (8,  '2021 South Lee County Watershed Initiative Hydrological Modeling Project Final Report'),
    (9,  '2025 Lee County Vulnerability Assessment Report'),
    (10, '2025 Lee County Coastal Flood Adaptation Plan'),
    (11, '2025 Village of Estero Progress Report on Local Mitigation Strategy'),
]

tbl = doc.add_table(rows=1 + len(sources), cols=2)
tbl.alignment = WD_TABLE_ALIGNMENT.LEFT

# column widths
col_widths = [Inches(0.6), Inches(5.9)]
for row in tbl.rows:
    for i, cell in enumerate(row.cells):
        cell.width = col_widths[i]

# ── Header row ──────────────────────────────────────────────────────────────
hdr_cells = tbl.rows[0].cells
hdr_data   = ['#', 'SOURCE DOCUMENT']
for i, (cell, txt) in enumerate(zip(hdr_cells, hdr_data)):
    set_cell_bg(cell, ORANGE, theme_fill='accent2')
    set_cell_borders(cell)
    cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
    p = cell.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER if i == 0 else WD_ALIGN_PARAGRAPH.LEFT
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after  = Pt(4)
    run(p, txt, bold=True, color=WHITE, size=9)

# ── Data rows ───────────────────────────────────────────────────────────────
for row_idx, (num, title) in enumerate(sources):
    bg = GRAY_BG if row_idx % 2 == 1 else WHITE
    row_cells = tbl.rows[row_idx + 1].cells

    num_cell = row_cells[0]
    set_cell_bg(num_cell, bg)
    set_cell_borders(num_cell)
    num_cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
    p0 = num_cell.paragraphs[0]
    p0.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p0.paragraph_format.space_before = Pt(3)
    p0.paragraph_format.space_after  = Pt(3)
    run(p0, str(num), bold=True, color=DARK_GRAY, size=9)

    title_cell = row_cells[1]
    set_cell_bg(title_cell, bg)
    set_cell_borders(title_cell)
    title_cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
    p1 = title_cell.paragraphs[0]
    p1.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p1.paragraph_format.space_before = Pt(3)
    p1.paragraph_format.space_after  = Pt(3)
    p1.paragraph_format.left_indent  = Inches(0.05)

    # Year in bold orange, rest of title in dark gray
    year = title[:4]
    rest = title[4:]
    run(p1, year, bold=True, color=ORANGE, size=9)
    run(p1, rest, color=DARK_GRAY, size=9)

out = '/home/user/HERMES/estero_source_references.docx'
doc.save(out)
print(f'Saved: {out}')
