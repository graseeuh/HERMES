from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
import copy

doc = Document()

# ── Page margins ──────────────────────────────────────────────────────────────
for section in doc.sections:
    section.top_margin = Inches(1)
    section.bottom_margin = Inches(1)
    section.left_margin = Inches(1.25)
    section.right_margin = Inches(1.25)

# ── Style helpers ─────────────────────────────────────────────────────────────
def set_font(run, size=11, bold=False, italic=False, color=None):
    run.font.name = "Calibri"
    run.font.size = Pt(size)
    run.bold = bold
    run.italic = italic
    if color:
        run.font.color.rgb = RGBColor(*color)

def heading(text, level=1):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(14 if level == 1 else 8)
    p.paragraph_format.space_after = Pt(4)
    run = p.add_run(text)
    if level == 1:
        set_font(run, size=14, bold=True, color=(31, 73, 125))
    elif level == 2:
        set_font(run, size=12, bold=True, color=(55, 96, 146))
    else:
        set_font(run, size=11, bold=True, italic=True)
    return p

def body(text, space_after=6, italic=False):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(space_after)
    run = p.add_run(text)
    set_font(run, italic=italic)
    return p

def quote(text):
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Inches(0.4)
    p.paragraph_format.space_after = Pt(6)
    run = p.add_run(f'"{text}"')
    set_font(run, italic=True, color=(89, 89, 89))
    return p

def bullet(text, level=0):
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.left_indent = Inches(0.25 + level * 0.2)
    p.paragraph_format.space_after = Pt(3)
    run = p.add_run(text)
    set_font(run)
    return p

def bold_inline(para, label, rest):
    r1 = para.add_run(label)
    set_font(r1, bold=True)
    r2 = para.add_run(rest)
    set_font(r2)

def add_table_row(table, cells, bold=False, header=False):
    row = table.add_row()
    for i, text in enumerate(cells):
        cell = row.cells[i]
        cell.text = ""
        p = cell.paragraphs[0]
        p.paragraph_format.space_after = Pt(2)
        run = p.add_run(text)
        run.font.name = "Calibri"
        run.font.size = Pt(9.5)
        run.bold = bold or header
        if header:
            run.font.color.rgb = RGBColor(255, 255, 255)
            tc = cell._tc
            tcPr = tc.get_or_add_tcPr()
            shd = OxmlElement("w:shd")
            shd.set(qn("w:val"), "clear")
            shd.set(qn("w:color"), "auto")
            shd.set(qn("w:fill"), "1F497D")
            tcPr.append(shd)
    return row

# ═════════════════════════════════════════════════════════════════════════════
# COVER
# ═════════════════════════════════════════════════════════════════════════════
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.paragraph_format.space_before = Pt(24)
run = p.add_run("Northeast Florida Military Installation Resilience Review")
set_font(run, size=16, bold=True, color=(31, 73, 125))

p2 = doc.add_paragraph()
p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
run2 = p2.add_run("Energy Reliability — Intern Research Contribution")
set_font(run2, size=13, bold=True, color=(55, 96, 146))

p3 = doc.add_paragraph()
p3.alignment = WD_ALIGN_PARAGRAPH.CENTER
run3 = p3.add_run(
    "Naval Air Station Jacksonville  |  Naval Station Mayport  |  "
    "MCSF Blount Island  |  Camp Blanding JTF\n"
    "Duval County and Clay County, Florida"
)
set_font(run3, size=10, color=(89, 89, 89))

p4 = doc.add_paragraph()
p4.alignment = WD_ALIGN_PARAGRAPH.CENTER
run4 = p4.add_run("Prepared for Supervisor Review — May 2026")
set_font(run4, size=10, italic=True, color=(89, 89, 89))

doc.add_paragraph()

# ═════════════════════════════════════════════════════════════════════════════
# SECTION 1 — FRAMING
# ═════════════════════════════════════════════════════════════════════════════
heading("1. Framing: Energy Risk Management, Not Efficiency Management", level=1)

body(
    "The energy vulnerability findings confirmed through the MIRR vulnerability assessment are "
    "fundamentally an energy risk management problem, not an energy efficiency problem. The "
    "installations are not wasting power — they depend on a fragile supply chain that can be severed "
    "by a single hazard event. The MIRR's own bottom-line finding confirms this:"
)
quote(
    "No immediate risk to mission other than single points of failure at each installation."
    "  — MIRR Vulnerability Assessment, January 2026 Steering Committee"
)
body(
    "Energy efficiency measures — load reduction, LED upgrades, demand management — do not address "
    "single points of failure. The correct framework is energy supply risk management: ensuring "
    "continuity of supply under hazard conditions, reducing failure points, and shortening restoration "
    "timelines when failure occurs."
)
body(
    "A useful way to frame the long-term goal, drawn from intern team analysis: these installations "
    "currently function as isolated but dependent islands — drawing from the regional grid with no "
    "backup path. The adaptation objective is to shift them toward connected hubs capable of both "
    "offering and accepting support to and from the larger grid. This shift was made urgent by "
    "Hurricane Michael's 2018 impact on Tyndall Air Force Base, where on-base hardening proved "
    "insufficient when surrounding roads, utilities, and civilian infrastructure failed "
    "(APTIM memo, May 2026, Section 1.1; GAO-22-105452, 2021)."
)

# ═════════════════════════════════════════════════════════════════════════════
# SECTION 2 — CASCADE
# ═════════════════════════════════════════════════════════════════════════════
heading("2. The Cascade Mechanism: How Flooding Becomes an Energy Crisis", level=1)

body(
    "Flooding does not threaten energy systems in isolation. It triggers a sequence of failures "
    "across interconnected infrastructure. For all four MIRR installations the cascade follows "
    "a common pattern:"
)

steps = [
    "Hazard event — storm surge, compound rainfall flooding, or wildfire",
    "Transportation corridors flood or close:\n     A1A (NS Mayport)  |  Heckscher Drive (Blount Island)  |  "
    "Roosevelt Blvd / US-17 (NAS JAX)  |  SR-16 (Camp Blanding)",
    "Utility restoration crews cannot reach substations",
    "Substation damage cannot be repaired on a mission-critical timeline",
    "Backup generator fuel supply is depleted",
    "Mission-critical systems lose power → Mission disruption",
]
for s in steps:
    bullet(s)

body("")
body("Flooding compounds energy risk through additional mechanisms:", space_after=3)

compounds = [
    ("Saltwater corrosion: ", "Storm surge deposits salt residue on substation equipment even when the "
     "facility is not fully inundated, accelerating equipment degradation and increasing future failure probability."),
    ("Fuel delivery disruption: ", "Backup generator fuel is delivered by truck on the same flooded roads "
     "that block restoration crews. Extended outages can exhaust fuel before grid power is restored."),
    ("Regional grid stress: ", "Large-scale flooding can knock out multiple JEA and FPL infrastructure "
     "nodes simultaneously, extending regional restoration timelines regardless of local conditions."),
    ("Water supply contamination: ", "Flood events in coastal and industrial areas mobilize contaminants — "
     "particularly relevant near Blount Island and NAS Jacksonville, where fuel storage and legacy industrial "
     "activity create contamination risk when floodwaters intrude. This compounds the post-event recovery burden "
     "and poses personnel health and operational risks."),
    ("US-17 transmission corridor (to investigate): ", "Early intern research identified substations and "
     "transmission lines along the US-17 highway corridor as common single points of failure across the region. "
     "GIS verification of which specific lines run along this corridor is needed before this is stated as a "
     "confirmed finding."),
]
for label, rest in compounds:
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.space_after = Pt(4)
    bold_inline(p, label, rest)

# ═════════════════════════════════════════════════════════════════════════════
# SECTION 3 — INSTALLATION RISK TABLE
# ═════════════════════════════════════════════════════════════════════════════
heading("3. Installation-Level Energy Risk Summary", level=1)

body(
    "All four installations carry confirmed energy risk ratings from the January 2026 Steering "
    "Committee Vulnerability Assessment. All rely on a single electrical substation with no backup "
    "supply path. Utility IGSAs cover operations and maintenance only — not resilience or redundancy "
    "(MIRR Mutual Support Assessment, February 2026 TAC)."
)

tbl = doc.add_table(rows=1, cols=5)
tbl.style = "Table Grid"
headers = ["Installation", "Strategic Mission", "Substation / Owner", "Risk / Urgency", "Primary Cascade Trigger"]
add_table_row(tbl, headers, header=True)

rows_data = [
    ("NS Mayport", "4th Fleet HQ; Atlantic operations", "JEA Mayport Sub (south of base)", "HIGH / Immediate", "A1A flooding blocks restoration crews"),
    ("NAS Jacksonville", "P-8 maritime patrol; logistics hub", "JEA Sub (north of base) + TECO gas", "MEDIUM / Immediate", "Roosevelt Blvd / US-17 flooding"),
    ("MCSF Blount Island", "Marine Corps 72-hr prepositioning", "JEA Sub", "MEDIUM / Immediate", "Heckscher Drive closure"),
    ("Camp Blanding", "National Guard mobilization", "FPL Sub (north of base)", "HIGH / Near-Term", "SR-16 flooding + wildfire on transmission corridor"),
]
for r in rows_data:
    add_table_row(tbl, r)

doc.add_paragraph()

# ═════════════════════════════════════════════════════════════════════════════
# SECTION 4 — ADAPTATION STRATEGIES
# ═════════════════════════════════════════════════════════════════════════════
heading("4. Adaptation Strategies", level=1)

body(
    "The APTIM evaluation framework (May 2026, Section 3.2) scores four strategy types — Protect, "
    "Accommodate, Avoidance/Relocation, and Regional Collaboration — on operational value, "
    "implementation feasibility, and long-term durability. Regional Collaboration scores highest "
    "for long-term durability across all utility and infrastructure scenarios."
)

heading("4.1  Near-Term Strategies (0–5 Years)", level=2)

near_term = [
    ("IGSA Expansion (Regional Collaboration — highest leverage): ",
     "Expand JEA IGSAs at NAS JAX and NS Mayport to include resilience and redundancy provisions, "
     "not only O&M. Administrative action requiring no capital. Directly addresses the confirmed mutual "
     "support gap. Establish baseline FPL coordination for Camp Blanding. (MIRR Regional Recommendation R-2)"),
    ("Substation Hardening at NS Mayport (Protect): ",
     "Flood barrier deployment or dry-type transformer installation at the JEA Mayport Substation — "
     "the highest-urgency energy risk in the region (HIGH / Immediate). Coordinated with JEA under "
     "the expanded IGSA. Flood-proofing substations may provide greater mission continuity per dollar "
     "than large-scale shoreline measures (APTIM, Section 3.2)."),
    ("P035 Dual Fuel Generator Project at Blount Island (Accommodate / Protect): ",
     "ERCIP-funded project in Final Design Authority. Installs generators in all nine critical "
     "facilities, reducing JEA grid dependency. Priority: reach construction without delay."),
    ("JEA Microgrid Feasibility → Funded Project at NAS JAX (Accommodate): ",
     "JEA's in-progress microgrid feasibility study should be accelerated toward a funded "
     "implementation via ERCIP or ESPC, providing islanding capability for Tier 1 loads."),
    ("Wildfire Fuel Management at Camp Blanding (Protect): ",
     "Prescribed fire programs already in place at Blanding should explicitly include the FPL "
     "transmission corridor as an objective, reducing wildfire SPOF risk."),
    ("Formalize Mutual Support Agreements (Regional Collaboration): ",
     "Existing informal coordination between installations and utilities should be formalized "
     "through MSAs that define restoration priorities, data sharing, and resilience obligations — "
     "building on the IGSA expansion and extending to emergency scenarios."),
]
for label, rest in near_term:
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.space_after = Pt(5)
    bold_inline(p, label, rest)

heading("4.2  Long-Term Strategies (5–20 Years)", level=2)

long_term = [
    ("Regional Utility Coordination Framework (Regional Collaboration): ",
     "Convene JEA, FPL, Seminole Electric, CCUA, and TECO under a formal resilience MOU enabling "
     "coordinated capital investment tied to installation vulnerability timelines. This is the "
     "structural solution to civilian infrastructure dependency across all four installations."),
    ("Dedicated Redundant Feed at NAS JAX (Avoidance/Relocation): ",
     "A redundant transmission feed from a diverse grid injection point — informed by the JEA "
     "microgrid study — would permanently decouple mission-critical loads from civilian distribution "
     "vulnerabilities."),
    ("Shoreline Resilience as Energy Co-Benefit at Mayport and Blount Island (Protect): ",
     "Seawall adaptation, living shorelines, and berms protecting substation access corridors "
     "directly reduce the storm surge inundation pathway to energy infrastructure — energy resilience "
     "embedded in coastal projects already scoped in the MIRR."),
    ("EUL Solar + BESS at Camp Blanding (Avoidance/Relocation): ",
     "73,000 acres and rural land availability position Blanding for utility-scale solar under "
     "Enhanced Use Lease authority, paired with battery storage. Substantially reduces dependence "
     "on the wildfire-exposed FPL corridor. Solar PV and battery storage costs have declined "
     "significantly in recent years, improving feasibility relative to prior assessments."),
    ("Expanded Monitoring and Data Collection (Accommodate — long-term): ",
     "Expand grid monitoring systems and data collection infrastructure to better predict outages, "
     "track restoration performance, and measure the effectiveness of adaptation investments over time. "
     "Performance data — outage duration, restoration time, backup duration — should be reviewed "
     "periodically with utilities and installation representatives as part of the MIRR implementation "
     "framework (APTIM, Section 5.1). This is also identified by the intern team's prior research "
     "as a key long-term enabler."),
]
for label, rest in long_term:
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.space_after = Pt(5)
    bold_inline(p, label, rest)

# ═════════════════════════════════════════════════════════════════════════════
# SECTION 5 — AREAS TO EXPLORE
# ═════════════════════════════════════════════════════════════════════════════
heading("5. Areas to Explore Further", level=1)
body(
    "The following are raised as opportunities warranting further study. They are clearly labeled "
    "as exploratory — not confirmed recommendations — because source verification or GIS analysis "
    "is still needed."
)

heading("5.1  Tidal and River Current Energy — NS Mayport and MCSF Blount Island", level=2)
body(
    "The St. Johns River mouth at Naval Station Mayport has one of the highest tidal flow rates in "
    "Florida (~4–5 ft tidal range). Tidal energy converters — underwater turbines that harvest kinetic "
    "energy from river current — are submerged below storm surge exposure and generate power on "
    "predictable tidal cycles, independent of wind or solar conditions. For installations facing the "
    "flood-transportation-energy cascade, generation that does not depend on road access for routine "
    "operation has structural appeal."
)
body("Constraints that must be honestly evaluated before any recommendation:")
for c in [
    "Navigation channel conflicts — Mayport Ferry and military vessel traffic use the river mouth",
    "Environmental permitting — manatee, fish passage, and St. Johns River ecology",
    "Saltwater maintenance demands and long-term equipment durability",
    "Capital cost and regulatory timeline for a technology not yet deployed at this location",
    "Whether a DOE Water Power Technologies Office feasibility study has been commissioned for this site (not documented in current MIRR materials — a data gap)",
]:
    bullet(c)

heading("5.2  Solar PV + Battery Storage — Camp Blanding", level=2)
body(
    "Camp Blanding's 73,000 acres and rural land availability support utility-scale solar under "
    "Enhanced Use Lease (EUL) authority, paired with battery energy storage systems (BESS). This "
    "would reduce dependence on the FPL distribution corridor and its wildfire exposure. Prices for "
    "both solar PV and battery storage have declined significantly in recent years — identified by "
    "the intern team's prior research as an area warranting a current feasibility study scoped to "
    "Blanding's load profile."
)

heading("5.3  Landfill Methane and Alternative Generation — Area for Investigation", level=2)
body(
    "The intern team's prior research flagged that Marine Corps Air Station Miramar (California) uses "
    "a blend of energy sources and battery storage to achieve extended islanded operation. Methane gas "
    "from landfills is noted as a significant energy source at that installation. The Jacksonville "
    "region has several landfill sites in proximity to NAS Jacksonville and Blount Island."
)
body(
    "Important caveat: the APTIM memo (May 2026, Section 1.2) confirms only that Miramar has "
    "\"microgrid and energy resilience investments\" (citing DOE 2022). The specific 21-day islanding "
    "duration and landfill methane details cited in the intern team's prior research have not been "
    "independently verified against a primary source. Before drawing a direct comparison to Northeast "
    "Florida, the following is needed:"
)
for c in [
    "Primary source verification of the Miramar islanding duration and fuel sourcing",
    "GIS mapping of Jacksonville-area landfill locations relative to NAS JAX and Blount Island",
    "Assessment of pipeline feasibility, permitting, and methane capture volumes",
]:
    bullet(c)
body(
    "This is a legitimate area to explore — the physics and the regional geography make it worth "
    "investigating — but it should not be presented as a confirmed strategy until the source is verified.",
    italic=True
)

# ═════════════════════════════════════════════════════════════════════════════
# SECTION 6 — CIVILIAN INFRASTRUCTURE DEPENDENCY
# ═════════════════════════════════════════════════════════════════════════════
heading("6. The Strategic Vulnerability: Civilian Infrastructure Dependency", level=1)

body("All four installations depend on substations that are:")
for b in [
    "Located outside the installation fence on civilian utility property",
    "Hardened to commercial utility standards, not military resilience standards",
    "Publicly mapped in open federal databases (HIFLD Open)",
    "Subject to no formal resilience obligation — current IGSAs cover O&M only",
]:
    bullet(b)

body(
    "This means operational continuity at all four installations is contingent on civilian utility "
    "performance under conditions those utilities have no contractual obligation to prioritize for "
    "military restoration timelines. The gap between utility standard restoration timelines (days "
    "for major events) and mission-critical requirements (hours) is unaddressed in the current "
    "framework."
)
body(
    "MIRR Regional Recommendation R-2 — IGSA expansion and FPL coordination — is the first step "
    "toward closing this gap. It is an administrative action requiring no capital. Until it is in "
    "place, the dependency remains structurally unmitigated across all four installations."
)

# ═════════════════════════════════════════════════════════════════════════════
# SECTION 7 — DATA AND GIS GAPS
# ═════════════════════════════════════════════════════════════════════════════
heading("7. Data and GIS Gaps — What Still Needs Verification", level=1)

body(
    "The following findings are identified concerns grounded in MIRR documents and intern research. "
    "They should be treated as confirmed vulnerabilities requiring GIS analysis before being "
    "presented as spatially verified findings."
)

tbl2 = doc.add_table(rows=1, cols=3)
tbl2.style = "Table Grid"
add_table_row(tbl2, ["Gap", "Current Status", "What GIS/Data Would Confirm"], header=True)

gaps = [
    ("US-17 transmission line routing", "Identified in intern research as common SPOF corridor; not yet spatially verified", "Which specific transmission lines run along US-17; which installations they serve"),
    ("Substation locations vs. flood zones", "MIRR VA confirms flood exposure qualitatively; no spatial overlay yet", "Intersection of HIFLD substations with SLOSH Cat 3/5 and CDBG flood layers"),
    ("FPL corridor wildfire exposure", "Identified qualitatively from USDA FS data and MIRR findings", "Spatial overlay of USDA wildfire WUI with FPL transmission corridor to Blanding"),
    ("Landfill proximity to installations", "Flagged as area to explore; no mapping done", "Distance and feasibility of methane pipeline routing to NAS JAX and Blount Island"),
    ("JEA substation exact locations", "EIA Form 860 and HIFLD used as proxies; JEA data not yet shared", "Confirmed substation coordinates, condition ratings, planned hardening investments"),
]
for g in gaps:
    add_table_row(tbl2, g)

doc.add_paragraph()

# ═════════════════════════════════════════════════════════════════════════════
# SOURCES
# ═════════════════════════════════════════════════════════════════════════════
heading("Sources", level=1)
sources = [
    "NEFRC MIRR Vulnerability Assessment — January 2026 Steering Committee",
    "MIRR Mutual Support Assessment — February 2026 TAC",
    "MIRR Adaptation Planning Framework — April 2026 Steering Committee",
    "MCSF Blount Island Kickoff Briefing — April 2025",
    "NAS Jacksonville Site Visit Summary V3",
    "Camp Blanding Summary V2",
    "APTIM Memo: NE MIRR Evaluating Potential Adaptation Solutions — May 22, 2026 (Sections 1.1, 3.2, 5–6)",
    "GAO Climate Resilience Report — GAO-22-105452, 2021",
    "DoD Climate Adaptation Plan — 2021",
    "Prior Intern Research: Energy System Points of Failure and Geospatial Dataset Inventory",
]
for s in sources:
    bullet(s)

# ─────────────────────────────────────────────────────────────────────────────
out = "/home/user/HERMES/resilience_review/MIRR_Energy_Resilience_Contribution.docx"
doc.save(out)
print(f"Saved: {out}")
