from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

doc = Document()

for section in doc.sections:
    section.top_margin    = Inches(1)
    section.bottom_margin = Inches(1)
    section.left_margin   = Inches(1.25)
    section.right_margin  = Inches(1.25)

# ── helpers ───────────────────────────────────────────────────────────────────
def font(run, size=11, bold=False, italic=False, color=None):
    run.font.name = "Calibri"
    run.font.size = Pt(size)
    run.bold   = bold
    run.italic = italic
    if color:
        run.font.color.rgb = RGBColor(*color)

def heading(text, level=1, color=None):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(14 if level == 1 else 8)
    p.paragraph_format.space_after  = Pt(4)
    run = p.add_run(text)
    if level == 1:
        c = color or (31, 73, 125)
        font(run, size=13, bold=True, color=c)
    elif level == 2:
        c = color or (55, 96, 146)
        font(run, size=11, bold=True, color=c)
    else:
        font(run, size=11, bold=True, italic=True)

def body(text, space_after=6, italic=False, color=None):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(space_after)
    run = p.add_run(text)
    font(run, italic=italic, color=color)
    return p

def note(text):
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Inches(0.3)
    p.paragraph_format.space_after = Pt(5)
    run = p.add_run("Note: " + text)
    font(run, italic=True, color=(89, 89, 89))

def quote(text, source):
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Inches(0.4)
    p.paragraph_format.space_after = Pt(4)
    r1 = p.add_run(f'"{text}"')
    font(r1, italic=True, color=(64, 64, 64))
    r2 = p.add_run(f"\n— {source}")
    font(r2, size=9.5, italic=True, color=(127, 127, 127))

def bullet(text, indent=0):
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.left_indent = Inches(0.25 + indent * 0.2)
    p.paragraph_format.space_after = Pt(3)
    run = p.add_run(text)
    font(run)

def mixed(label, rest):
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.space_after = Pt(4)
    r1 = p.add_run(label)
    font(r1, bold=True)
    r2 = p.add_run(rest)
    font(r2)

def shaded_box(text, fill="EAF0F8", text_color=(31, 73, 125), label=None):
    p = doc.add_paragraph()
    p.paragraph_format.left_indent  = Inches(0.3)
    p.paragraph_format.right_indent = Inches(0.3)
    p.paragraph_format.space_after  = Pt(8)
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    p._p.get_or_add_pPr().append(shd)
    if label:
        r1 = p.add_run(label + "\n")
        font(r1, size=10, bold=True, color=text_color)
    r2 = p.add_run(text)
    font(r2, size=10, italic=True, color=text_color)

def divider(label, fill="1F497D"):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(16)
    p.paragraph_format.space_after  = Pt(4)
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    p._p.get_or_add_pPr().append(shd)
    run = p.add_run(f"  {label}")
    font(run, size=12, bold=True, color=(255, 255, 255))

def table_header(tbl, cols):
    row = tbl.add_row()
    for i, text in enumerate(cols):
        cell = row.cells[i]
        cell.text = ""
        p   = cell.paragraphs[0]
        p.paragraph_format.space_after = Pt(2)
        run = p.add_run(text)
        font(run, size=9.5, bold=True, color=(255, 255, 255))
        tc   = cell._tc
        tcPr = tc.get_or_add_tcPr()
        shd  = OxmlElement("w:shd")
        shd.set(qn("w:val"),   "clear")
        shd.set(qn("w:color"), "auto")
        shd.set(qn("w:fill"),  "1F497D")
        tcPr.append(shd)

def table_row(tbl, vals):
    row = tbl.add_row()
    for i, text in enumerate(vals):
        cell = row.cells[i]
        cell.text = ""
        p   = cell.paragraphs[0]
        p.paragraph_format.space_after = Pt(2)
        run = p.add_run(text)
        font(run, size=9.5)

def centered(text, size=11, bold=False, italic=False,
             color=(0,0,0), space_before=0, space_after=4):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.space_after  = Pt(space_after)
    run = p.add_run(text)
    font(run, size=size, bold=bold, italic=italic, color=color)

# ═════════════════════════════════════════════════════════════════════════════
# COVER
# ═════════════════════════════════════════════════════════════════════════════
centered("Northeast Florida Military Installation Resilience Review",
         size=16, bold=True, color=(31,73,125), space_before=20, space_after=4)
centered("Energy Infrastructure — Combined Intern Research Contribution",
         size=13, bold=True, color=(55,96,146), space_after=4)
centered(
    "Naval Air Station Jacksonville  |  Naval Station Mayport\n"
    "MCSF Blount Island  |  Camp Blanding JTF",
    size=10, color=(89,89,89), space_after=4)
centered("Prepared for Supervisor Review — May 2026",
         size=10, italic=True, color=(89,89,89), space_after=12)

shaded_box(
    "This document combines two separate research contributions. "
    "Part 1 preserves the first intern's research findings in their original form — "
    "no edits, no additions. "
    "Part 2 contains additional analysis and investigation routes developed by the second "
    "intern, building on Part 1 and on the full set of MIRR project documents. "
    "Neither part proposes final strategies. GIS analysis has not yet been performed by "
    "either intern; spatial findings in the MIRR documents are cited as-is from those sources.",
    label="About This Document"
)

# ═════════════════════════════════════════════════════════════════════════════
# PART 1 — OTHER INTERN'S RESEARCH (VERBATIM)
# ═════════════════════════════════════════════════════════════════════════════
divider("PART 1 — First Intern's Research Findings  (preserved verbatim)")

doc.add_paragraph()

heading("Energy Resilience Overview", level=1)
body(
    "Common themes across the sites include dependence on outside grid and exposure to its "
    "shortcomings, namely single-point utility failures outside of these military sites that "
    "could cause failures that cascade onto military sites and threaten mission success. These "
    "failure points are typically substations or lines along the U.S. 17 highway."
)
body(
    "These risks are exasperated by increasing energy demand throughout the region and lack "
    "of redundancy of power supply to installations."
)
body(
    "There are reports of aging infrastructure serving the installations which only increases "
    "the likelihood of single-point failure."
)
body(
    "It's worth noting that one of the bases, Camp Blanding, relies on four separate power "
    "providers and Seminole Electric for generation. The Florida Power & Light (FPL) substation "
    "north of the base is a high-risk asset vulnerable to natural hazards and a lack of redundancy."
)

heading("Adaptation Strategies", level=1)
body(
    "The general theme of strategies discussed is moving from isolated but dependent islands "
    "into more connected hubs capable of both offering and accepting support to and from the "
    "larger grid. This shift was motivated by Hurricane Michael's effect on Tyndall AF Base "
    "in 2018."
)

heading("Short Term", level=2)
bullet("Flood-proofing substations and supply lines are the most pressing short term adaptation strategy. "
       "Mutual Support Agreements (MSAs) are drafted to formalize collaboration between utility companies, "
       "local government agencies, and the installations themselves.")
bullet("Flood proofing and undergrounding may provide more cost-effective resilience than large scale "
       "sea-walling measures.")
bullet("Formalizing loose MSA agreements for current and future adaptation projects may improve efficiency.")
bullet("Addressing redundancy gaps in both electrical and fuel systems by creating backup paths and stocks.")

heading("Long Term", level=2)
bullet("Expand monitoring systems and data collection of grid and other infrastructure to better predict "
       "outages and manage performance. This data can be used to assess effectiveness of adaptation "
       "projects in terms of outages avoided and guide future projects.")
bullet("Microgrids could offer both independent resilience and eventually the ability to support the "
       "larger grid with BESS infrastructure. Microgrid feasibility studies are already underway.")

heading("Areas to Explore More", level=2)
bullet("Prices of battery storage and Solar PV have both fallen dramatically in recent years. Minimal "
       "mention of either technology, but could a feasibility study be completed? The two in tandem "
       "could be beneficial.")
bullet("Miramar MC Air Station outside San Diego, CA uses a blend of energy sources and BESS to provide "
       "up to 21 days of islanded energy resilience. Methane gas from landfills is a significant energy "
       "source. Could the several landfills surrounding Jacksonville provide similar energy sources "
       "or redundancy?")
bullet("Marine Corp Story — Full CA State Project Report")

# ═════════════════════════════════════════════════════════════════════════════
# PART 2 — SECOND INTERN'S CONTRIBUTION
# ═════════════════════════════════════════════════════════════════════════════
divider("PART 2 — Second Intern's Additional Research and Investigation Routes")

doc.add_paragraph()

shaded_box(
    "Everything in Part 2 is built on the MIRR project documents reviewed by this intern "
    "(listed in Section 7). No independent GIS analysis has been performed. "
    "Vulnerabilities cited are from confirmed MIRR findings — not new claims. "
    "Investigation routes are raised as questions, not recommendations.",
    label="Scope Notice — Part 2",
    fill="FFF4E5",
    text_color=(102, 51, 0)
)

# ── 2.1 What the MIRR Confirms ────────────────────────────────────────────────
heading("2.1  What the MIRR Has Confirmed — The Baseline", level=1)
body(
    "Part 1 identifies the right themes. The MIRR vulnerability assessment provides specific "
    "confirmed findings that give those themes exact risk ratings and urgency levels."
)
quote(
    "At the asset systems level there is no immediate risk to mission other than single points "
    "of failure at each installation.",
    "MIRR Vulnerability Assessment, January 2026 Steering Committee"
)

tbl = doc.add_table(rows=1, cols=4)
tbl.style = "Table Grid"
table_header(tbl, ["Installation", "Substation / Owner", "Risk to Mission", "Urgency"])
table_row(tbl, ["NS Mayport",       "JEA Mayport Sub (south of base)", "HIGH",   "Immediate"])
table_row(tbl, ["MCSF Blount Island", "JEA Substation",               "MEDIUM", "Immediate"])
table_row(tbl, ["NAS Jacksonville", "JEA Sub (north of base)",         "MEDIUM", "Immediate"])
table_row(tbl, ["Camp Blanding",    "FPL Sub (north of base)",          "HIGH",   "Near-Term"])
doc.add_paragraph()

body("Additional confirmed details from MIRR site documents:")
mixed("Water intrusion already active at Blount Island — ",
      "not a future scenario. Confirmed in MCSF Blount Island Kickoff Briefing, April 2025.")
mixed("JEA microgrid feasibility study already underway at NAS JAX — ",
      "confirmed in NAS JAX Summary V3. This is an existing effort.")
mixed("P035 Dual Fuel Generator Project at Blount Island — ",
      "ERCIP-funded, in Final Design Authority. Construction not yet begun.")
mixed("NAS JAX has a second SPOF beyond the substation — ",
      "the TECO privatized natural gas system, which is independent of the JEA electrical grid.")

note("GIS has not been run by this intern. The risk ratings above come from the MIRR team's "
     "own spatial and vulnerability analysis.")

# ── 2.2 Framing ───────────────────────────────────────────────────────────────
heading("2.2  Framing: Risk Management, Not Efficiency Management", level=1)
body(
    "Part 1's framing — isolated islands moving toward connected hubs — is the right frame. "
    "This intern's review of the full MIRR document set confirms a related distinction worth "
    "stating explicitly: this is an energy risk management problem, not an energy efficiency problem."
)
body(
    "Efficiency measures reduce how much power is consumed. They do not change the fact that "
    "a single substation failure — with no backup supply path — cuts power to the entire "
    "installation. The MIRR's own bottom-line finding confirms the problem is supply continuity, "
    "not consumption."
)
note("This framing is the intern team's analytical observation from document review, not a "
     "MIRR-confirmed conclusion.")

# ── 2.3 Cascade ───────────────────────────────────────────────────────────────
heading("2.3  Expanding on the Cascade: How Flooding Reaches Energy Systems", level=1)
body(
    "Part 1 identifies substations and US-17 lines as common failure points. The MIRR documents "
    "confirm a broader cascade mechanism connecting flooding, transportation, and energy:"
)

steps = [
    ("Step 1", "Hazard event — storm surge, compound rainfall flooding, or wildfire"),
    ("Step 2", "Transportation corridors flood or close:\n"
               "     A1A (NS Mayport)  |  Heckscher Drive (Blount Island)  |  "
               "Roosevelt Blvd / US-17 (NAS JAX)  |  SR-16 (Camp Blanding)\n"
               "     [All confirmed as transportation SPOFs — MIRR VA, Jan 2026 SC]"),
    ("Step 3", "Utility restoration crews cannot reach the affected substation"),
    ("Step 4", "Substation damage cannot be repaired on a mission-critical timeline"),
    ("Step 5", "Backup generator fuel is depleted — mission-critical systems lose power"),
]
for label, text in steps:
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Inches(0.3)
    p.paragraph_format.space_after = Pt(3)
    r1 = p.add_run(f"{label}:  ")
    font(r1, bold=True)
    r2 = p.add_run(text)
    font(r2)

doc.add_paragraph()
body("Additional mechanisms implied by MIRR documents but not yet GIS-verified:")
mixed("Saltwater corrosion — ",
      "surge events deposit salt residue on substation equipment even without full inundation, "
      "accelerating long-term degradation at coastal sites.")
mixed("Fuel delivery on flooded roads — ",
      "generator fuel trucks use the same corridors that block restoration crews.")
mixed("Water contamination risk — ",
      "flooding near industrial land uses around Blount Island and NAS JAX may mobilize "
      "contaminants. Proximity of contamination sites to flood zones has not been mapped.")
mixed("US-17 transmission corridor — ",
      "identified in Part 1 as a common SPOF. Spatial verification of which transmission "
      "lines actually run this corridor has not been done by either intern.")

note("The cascade chain is logical analysis connecting confirmed MIRR findings. "
     "GIS would test and quantify each link.")

# ── 2.4 Mission context ───────────────────────────────────────────────────────
heading("2.4  Why This Matters: Mission-Critical Context", level=1)
body(
    "The following is background from publicly available information about each installation's "
    "mission — included to frame the consequence of the cascade, not as operational findings."
)

installs = [
    ("NS Mayport — 4th Fleet Headquarters",
     "Commands all U.S. Navy operations across the Caribbean, Central America, and South America. "
     "Shore power to docked vessels, fueling, and command communications all depend on the JEA "
     "Mayport Substation — the highest-urgency confirmed SPOF in the region. "
     "Risk rating: HIGH / Immediate."),
    ("NAS Jacksonville — Maritime Patrol Hub",
     "Primary East Coast hub for P-8 Poseidon maritime patrol aircraft. Continuous power required "
     "for aircraft maintenance, fueling, and communications. Has a second confirmed SPOF — the "
     "TECO natural gas system — independent of the electrical grid. Risk rating: MEDIUM / Immediate."),
    ("MCSF Blount Island — Maritime Prepositioning Force",
     "Prepositioned Marine Corps equipment ready to deploy globally within 72 hours. Crane and "
     "conveyor operations, climate-controlled storage, and logistics coordination all require "
     "continuous power. Water intrusion is already active. "
     "Risk rating: MEDIUM / Immediate."),
    ("Camp Blanding — National Guard Mobilization Hub",
     "Florida's primary National Guard training and mobilization center. Four-provider coordination "
     "confirmed. Wildfire could cut the FPL transmission corridor without weather warning, during "
     "a mobilization event. Risk rating: HIGH / Near-Term."),
]
for title, desc in installs:
    heading(title, level=2)
    body(desc)

# ── 2.5 Investigation routes ──────────────────────────────────────────────────
heading("2.5  Investigation Routes — Building on Part 1's Areas to Explore", level=1)
body(
    "Part 1 raises Solar PV + BESS and the Miramar landfill methane question as areas worth "
    "exploring. The following expands on those and adds additional routes identified through "
    "document review. All are framed as questions, not recommendations."
)

heading("Tidal and River Current Energy at Mayport and Blount Island", level=2)
body(
    "The St. Johns River mouth at NS Mayport has one of the highest tidal flow rates in Florida. "
    "Tidal energy converters sit below storm surge and generate on predictable tidal cycles — "
    "not mentioned in the APTIM memo or MIRR documents. Worth asking:"
)
bullet("Has a feasibility study been commissioned for tidal generation at Mayport or Blount Island?")
bullet("Do navigation channel requirements and environmental permitting for the St. Johns River "
       "make this viable?")
note("This is an avenue identified by this intern, not a confirmed option. Location-specific "
     "feasibility review needed before drawing any conclusions.")

heading("Landfill Methane — Verification Needed Before Going Further", level=2)
body(
    "Part 1 raises the Miramar landfill methane question. Important caveat: the APTIM memo "
    "(May 2026, Section 1.2) confirms only that Miramar has 'microgrid and energy resilience "
    "investments' — it does not mention landfill methane or a 21-day islanding figure. "
    "Before this is used as a comparison point, two things are needed:"
)
bullet("Primary source verification of the specific Miramar claims (islanding duration, "
       "fuel sourcing)")
bullet("GIS mapping of Jacksonville-area landfill locations relative to NAS JAX and Blount Island")
note("This intern agrees the question is worth pursuing — the geography makes it relevant. "
     "But the source needs to be found first.")

heading("Solar PV + BESS — Building on Part 1", level=2)
body(
    "Part 1 correctly identifies the cost decline in Solar PV and BESS as a reason to revisit "
    "feasibility. For Camp Blanding specifically, 73,000 acres and rural land availability "
    "make this worth a targeted question:"
)
bullet("Has a solar feasibility study been commissioned at Blanding under ESTCP or ESPC authority?")
bullet("What portion of Blanding's load could realistically be offset by on-site generation?")
bullet("Does the four-provider structure complicate or simplify an Enhanced Use Lease solar arrangement?")

heading("Civilian Infrastructure Dependency — How Deep Is the Gap?", level=2)
body(
    "The MIRR confirms that IGSAs cover O&M only — not resilience. What is not yet known and "
    "worth finding out:"
)
bullet("What restoration timelines do JEA and FPL actually commit to for major outage events — "
       "and how do those compare to mission-critical power requirements?")
bullet("Has either utility shared any data on planned hardening investments for the specific "
       "substations serving these installations?")

# ── 2.6 What GIS would add ────────────────────────────────────────────────────
heading("2.6  What GIS Analysis Would Contribute", level=1)
body(
    "GIS does not create the vulnerabilities identified in this document — the MIRR has already "
    "confirmed those. What GIS adds is spatial confirmation, quantification, and visual "
    "communication of findings that are currently qualitative."
)

tbl2 = doc.add_table(rows=1, cols=3)
tbl2.style = "Table Grid"
table_header(tbl2, ["Analysis", "Datasets Needed", "What It Would Confirm"])
gis_rows = [
    ("Substation vs. flood zone overlay",
     "HIFLD substations, NHC SLOSH, NEFRC CDBG flood model",
     "Which substations fall within Cat 3/5 surge or 100-yr flood extents"),
    ("Transportation SPOF vs. flood zone",
     "FDOT road network, same flood layers",
     "Which access corridors close at which storm frequencies"),
    ("US-17 transmission corridor verification",
     "EIA transmission lines, HIFLD",
     "Whether lines along US-17 actually serve these installations"),
    ("FPL corridor wildfire exposure",
     "USDA FS wildfire WUI, EIA transmission lines",
     "Extent of wildfire hazard along Camp Blanding's supply corridor"),
    ("Landfill proximity mapping",
     "EPA facility data, FDEP, installation boundaries",
     "Distance and routing feasibility for methane investigation"),
    ("Contamination sites vs. flood zones",
     "EPA ECHO, FDEP, FEMA NFHL",
     "Flood-mobilized contamination risk near Blount Island and NAS JAX"),
]
for r in gis_rows:
    table_row(tbl2, r)

doc.add_paragraph()

# ── Sources ───────────────────────────────────────────────────────────────────
heading("2.7  Sources for Part 2", level=1)
body("All vulnerability findings in Part 2 are sourced to the following MIRR project materials:")
for s in [
    "NEFRC MIRR Vulnerability Assessment — January 2026 Steering Committee",
    "MIRR Mutual Support Assessment — February 2026 TAC",
    "MIRR Adaptation Planning Framework — April 2026 Steering Committee",
    "MCSF Blount Island Kickoff Briefing — April 2025",
    "NAS Jacksonville Site Visit Summary V3",
    "Camp Blanding Summary V2",
    "NEFRC MIRR Stakeholder Workshop 1 Summary V2",
    "APTIM Memo: NE MIRR Evaluating Potential Adaptation Solutions — May 22, 2026",
    "GAO Climate Resilience Report — GAO-22-105452, 2021",
    "DoD Climate Adaptation Plan — 2021",
]:
    bullet(s)

# ─────────────────────────────────────────────────────────────────────────────
out = "/home/user/HERMES/resilience_review/MIRR_Energy_Combined_Contribution.docx"
doc.save(out)
print(f"Saved: {out}")
