from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

doc = Document()

for section in doc.sections:
    section.top_margin    = Inches(1)
    section.bottom_margin = Inches(1)
    section.left_margin   = Inches(1.2)
    section.right_margin  = Inches(1.2)

# ── Palette ───────────────────────────────────────────────────────────────────
NAVY       = (31,  73,  125)
SLATE      = (55,  96,  146)
GRAY       = (89,  89,  89)
BLACK      = (0,   0,   0)
GREEN_D    = (0,   97,  0)
AMBER_D    = (102, 51,  0)
RED_D      = (120, 0,   0)
WHITE      = (255, 255, 255)

TAG_CONFIRMED = "● Confirmed"
TAG_GIS       = "◐ Pending GIS"
TAG_VERIFY    = "○ Needs verification"

# ── Helpers ───────────────────────────────────────────────────────────────────
def font(run, size=10.5, bold=False, italic=False, color=None):
    run.font.name = "Calibri"
    run.font.size = Pt(size)
    run.bold   = bold
    run.italic = italic
    if color:
        run.font.color.rgb = RGBColor(*color)

def centered(text, size=11, bold=False, italic=False,
             color=BLACK, space_before=0, space_after=4):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.space_after  = Pt(space_after)
    run = p.add_run(text)
    font(run, size=size, bold=bold, italic=italic, color=color)

def h1(text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(16)
    p.paragraph_format.space_after  = Pt(2)
    # thin top rule via bottom border on preceding empty para would be complex;
    # use bold navy with a light rule feel via spacing
    run = p.add_run(text.upper())
    font(run, size=11, bold=True, color=NAVY)
    # add bottom border to paragraph
    pPr = p._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"),   "single")
    bottom.set(qn("w:sz"),    "4")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), "1F497D")
    pBdr.append(bottom)
    pPr.append(pBdr)

def h2(text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.space_after  = Pt(2)
    run = p.add_run(text)
    font(run, size=10.5, bold=True, color=SLATE)

def body(text, space_after=5, italic=False, color=None):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(space_after)
    run = p.add_run(text)
    font(run, italic=italic, color=color or BLACK)
    return p

def status_line(tag, text):
    """Single-line status annotation — tag in color, text in gray italic."""
    tag_colors = {
        TAG_CONFIRMED: GREEN_D,
        TAG_GIS:       AMBER_D,
        TAG_VERIFY:    RED_D,
    }
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Inches(0.25)
    p.paragraph_format.space_after = Pt(5)
    r1 = p.add_run(f"{tag}  ")
    font(r1, size=9.5, bold=True, color=tag_colors.get(tag, GRAY))
    r2 = p.add_run(text)
    font(r2, size=9.5, italic=True, color=GRAY)

def quote(text, source):
    p = doc.add_paragraph()
    p.paragraph_format.left_indent  = Inches(0.35)
    p.paragraph_format.right_indent = Inches(0.2)
    p.paragraph_format.space_after  = Pt(5)
    # left border
    pPr = p._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    left = OxmlElement("w:left")
    left.set(qn("w:val"),   "single")
    left.set(qn("w:sz"),    "12")
    left.set(qn("w:space"), "4")
    left.set(qn("w:color"), "1F497D")
    pBdr.append(left)
    pPr.append(pBdr)
    r1 = p.add_run(f'"{text}"')
    font(r1, italic=True, color=(64, 64, 64))
    r2 = p.add_run(f"  — {source}")
    font(r2, size=9, italic=True, color=GRAY)

def bullet(text, indent=0):
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.left_indent = Inches(0.2 + indent * 0.2)
    p.paragraph_format.space_after = Pt(2)
    run = p.add_run(text)
    font(run)

def mixed(label, rest, indent=0):
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.space_after = Pt(3)
    p.paragraph_format.left_indent = Inches(0.2 + indent * 0.2)
    r1 = p.add_run(label)
    font(r1, bold=True)
    r2 = p.add_run(rest)
    font(r2)

def divider(label):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(18)
    p.paragraph_format.space_after  = Pt(6)
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"),   "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"),  "1F497D")
    p._p.get_or_add_pPr().append(shd)
    run = p.add_run(f"  {label}")
    font(run, size=11, bold=True, color=WHITE)

def tbl_header(tbl, cols):
    row = tbl.add_row()
    for i, text in enumerate(cols):
        cell = row.cells[i]
        cell.text = ""
        p = cell.paragraphs[0]
        p.paragraph_format.space_after = Pt(1)
        run = p.add_run(text)
        font(run, size=9.5, bold=True, color=WHITE)
        tcPr = cell._tc.get_or_add_tcPr()
        shd  = OxmlElement("w:shd")
        shd.set(qn("w:val"),   "clear")
        shd.set(qn("w:color"), "auto")
        shd.set(qn("w:fill"),  "1F497D")
        tcPr.append(shd)

def tbl_row(tbl, vals, alt=False):
    row = tbl.add_row()
    fill = "F2F5FA" if alt else "FFFFFF"
    for i, text in enumerate(vals):
        cell = row.cells[i]
        cell.text = ""
        p = cell.paragraphs[0]
        p.paragraph_format.space_after = Pt(1)
        run = p.add_run(text)
        font(run, size=9.5)
        if alt:
            tcPr = cell._tc.get_or_add_tcPr()
            shd  = OxmlElement("w:shd")
            shd.set(qn("w:val"),   "clear")
            shd.set(qn("w:color"), "auto")
            shd.set(qn("w:fill"),  fill)
            tcPr.append(shd)

# ═════════════════════════════════════════════════════════════════════════════
# COVER
# ═════════════════════════════════════════════════════════════════════════════
centered("Northeast Florida Military Installation Resilience Review",
         size=15, bold=True, color=NAVY, space_before=18, space_after=3)
centered("Energy Redundancy — Combined Intern Research Contribution",
         size=12, bold=True, color=SLATE, space_after=3)
centered(
    "NAS Jacksonville  ·  NS Mayport  ·  MCSF Blount Island  ·  Camp Blanding JTF",
    size=9.5, color=GRAY, space_after=2)
centered("Duval County and Clay County, Florida  ·  Supervisor Review Draft  ·  May 2026",
         size=9.5, italic=True, color=GRAY, space_after=12)

# annotation key
p = doc.add_paragraph()
p.paragraph_format.space_after = Pt(14)
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
for tag, col, desc in [
    (TAG_CONFIRMED, GREEN_D, "sourced to confirmed MIRR documents"),
    ("  ", GRAY, ""),
    (TAG_GIS,       AMBER_D, "needs GIS to verify spatially"),
    ("  ", GRAY, ""),
    (TAG_VERIFY,    RED_D,   "needs external source before use"),
]:
    r = p.add_run(tag)
    font(r, size=9, bold=(tag not in ("  ",)), color=col)
    if desc:
        r2 = p.add_run(f" {desc}")
        font(r2, size=9, italic=True, color=GRAY)

body(
    "Part 1 preserves the first intern's findings verbatim. Part 2 adds geographic and "
    "vulnerability context developed through MIRR document review. No GIS analysis has been "
    "performed yet — that work is in progress. No solutions are proposed.",
    italic=True, color=GRAY
)

# ═════════════════════════════════════════════════════════════════════════════
# PART 1
# ═════════════════════════════════════════════════════════════════════════════
divider("PART 1 — First Intern's Research Findings  (preserved verbatim)")
doc.add_paragraph()

h1("Energy Resilience Overview")
body(
    "Common themes across the sites include dependence on outside grid and exposure to its "
    "shortcomings, namely single-point utility failures outside of these military sites that "
    "could cause failures that cascade onto military sites and threaten mission success. These "
    "failure points are typically substations or lines along the U.S. 17 highway."
)
body(
    "These risks are exasperated by increasing energy demand throughout the region and lack "
    "of redundancy of power supply to installations. There are reports of aging infrastructure "
    "serving the installations which only increases the likelihood of single-point failure."
)
body(
    "It's worth noting that one of the bases, Camp Blanding, relies on four separate power "
    "providers and Seminole Electric for generation. The Florida Power & Light (FPL) substation "
    "north of the base is a high-risk asset vulnerable to natural hazards and a lack of redundancy."
)

h1("Adaptation Strategies")
body(
    "The general theme of strategies discussed is moving from isolated but dependent islands "
    "into more connected hubs capable of both offering and accepting support to and from the "
    "larger grid. This shift was motivated by Hurricane Michael's effect on Tyndall AF Base in 2018."
)

h2("Short Term")
bullet("Flood-proofing substations and supply lines — most pressing near-term priority. "
       "Mutual Support Agreements (MSAs) to formalize collaboration between utilities, "
       "local government, and installations.")
bullet("Flood proofing and undergrounding may be more cost-effective than large-scale sea-walling.")
bullet("Formalizing loose MSA agreements for current and future adaptation projects.")
bullet("Addressing redundancy gaps in electrical and fuel systems — backup paths and stocks.")

h2("Long Term")
bullet("Expand monitoring and data collection to predict outages and measure adaptation effectiveness.")
bullet("Microgrids with BESS infrastructure — feasibility studies already underway.")

h2("Areas to Explore More")
bullet("Solar PV and battery storage costs have fallen dramatically — feasibility study warranted.")
bullet("Miramar MC Air Station uses a blend of energy sources and BESS for up to 21 days of "
       "islanded resilience. Landfill methane is noted as a fuel source. "
       "Could Jacksonville-area landfills provide similar redundancy?")
bullet("Marine Corps Story — Full CA State Project Report")

# ═════════════════════════════════════════════════════════════════════════════
# PART 2
# ═════════════════════════════════════════════════════════════════════════════
divider("PART 2 — Second Intern's Research Contribution")
doc.add_paragraph()

# ── 2.1 ──────────────────────────────────────────────────────────────────────
h1("2.1  The Core Problem: Zero Electrical Redundancy")
body(
    "All four installations draw power from a single external substation with no backup "
    "supply path. If that substation fails, the installation loses commercial power entirely. "
    "Utility agreements (IGSAs) cover operations and maintenance only — no resilience or "
    "redundancy obligation exists."
)
quote(
    "At the asset systems level there is no immediate risk to mission other than single "
    "points of failure at each installation.",
    "MIRR Vulnerability Assessment, January 2026 Steering Committee"
)
status_line(TAG_CONFIRMED, "Risk ratings and IGSA gap confirmed by MIRR VA and Mutual Support Assessment, Feb 2026 TAC.")

t1 = doc.add_table(rows=1, cols=4)
t1.style = "Table Grid"
tbl_header(t1, ["Installation", "Substation / Owner", "Risk to Mission", "Urgency"])
rows = [
    ("NS Mayport",         "JEA — south of base",  "HIGH",   "Immediate"),
    ("MCSF Blount Island", "JEA Substation",        "MEDIUM", "Immediate"),
    ("NAS Jacksonville",   "JEA — north of base",   "MEDIUM", "Immediate"),
    ("Camp Blanding",      "FPL — north of base",   "HIGH",   "Near-Term"),
]
for i, r in enumerate(rows):
    tbl_row(t1, r, alt=(i % 2 == 1))
doc.add_paragraph()

# ── 2.2 ──────────────────────────────────────────────────────────────────────
h1("2.2  Why Redundancy Is Harder Here — Regional Geography")

h2("Shallow Water Table")
body(
    "Undergrounding is often proposed as a wind and debris solution. In coastal Duval County "
    "the water table sits only a few feet below grade in many areas. Underground cables here "
    "face groundwater intrusion, saltwater corrosion from below, and difficult fault repair "
    "when failures occur. JEA has undergrounded selectively but cautiously for this reason. "
    "Undergrounding trades one vulnerability for another — it is not a clean redundancy fix "
    "in this region."
)
status_line(TAG_GIS, "Specific water table depths at substation locations need USGS groundwater data and SJRWMD mapping.")

h2("Limited Access Corridors")
body("Each installation's geography creates hard constraints on restoration crew access:")
mixed("NS Mayport — ", "A1A only. Coastal peninsula — A1A flooding isolates the substation entirely.")
mixed("Blount Island — ", "Heckscher Drive only. River island — structural access limitation.")
mixed("NAS Jacksonville — ", "Roosevelt Blvd / US-17. Both run through St. Johns River floodplain.")
mixed("Camp Blanding — ", "SR-16. Black Creek flooding closes surrounding roads in tropical storm conditions.")
status_line(TAG_GIS, "FDOT road network overlaid against SLOSH and CDBG flood models will confirm which corridors close and at what storm frequency.")

h2("Upstream Grid Topology")
body(
    "A regional storm can cut power to a substation even if the substation is physically intact — "
    "by knocking out an upstream node in the grid. How many such nodes exist between the "
    "regional grid and each installation's substation, and how much of that path runs through "
    "flood-exposed terrain, is unknown. JEA has not shared transmission routing data with "
    "the MIRR team as of September 2025 TAC."
)
status_line(TAG_GIS, "EIA Form 860 and HIFLD transmission layers will be used as proxy. JEA data sharing needed for full picture.")

# ── 2.3 ──────────────────────────────────────────────────────────────────────
h1("2.3  Regional Hazards That Activate the Redundancy Gap")
body("These hazards are confirmed by MIRR VA as region-specific — not generic national risks.")

h2("Storm Surge — NS Mayport and Blount Island")
body(
    "Both installations sit adjacent to the St. Johns River mouth and the Atlantic coast. "
    "NHC SLOSH Cat 3–5 surge reaches the substations serving these installations. "
    "Surge simultaneously threatens the substation physically and inundates the access "
    "corridors restoration crews depend on — extending outage duration beyond the storm window."
)
status_line(TAG_CONFIRMED, "SLOSH confirmed as MIRR data source. NS Mayport substation: HIGH / Immediate.")
status_line(TAG_GIS, "Spatial overlay of substation locations against Cat 3/5 surge extents — viewable now via NOAA Digital Coast.")

h2("Compound Rainfall Flooding — NAS Jacksonville")
body(
    "NAS JAX sits on the St. Johns River floodplain. NEFRC CDBG flood modeling confirms "
    "100-year present, 2040, and 2070 rainfall flood scenarios. Compound flooding — rainfall "
    "compounded by tidal backflow — is an increasing risk in coastal Duval County. Both "
    "primary access corridors (Roosevelt Blvd and US-17) run through this terrain."
)
status_line(TAG_CONFIRMED, "CDBG compound flood model confirmed as MIRR data source.")
status_line(TAG_GIS, "Road corridor intersection with flood extents needs GIS overlay.")

h2("Wildfire — Camp Blanding Transmission Corridor")
body(
    "Camp Blanding's 73,000 acres sit in Florida's wildland-urban interface. The FPL "
    "transmission corridor runs through scrub and longleaf pine terrain confirmed as "
    "wildfire-exposed by USDA FS data cited in the MIRR. Unlike storm events, wildfire "
    "can sever the corridor with no weather warning."
)
status_line(TAG_CONFIRMED, "USDA FS wildfire hazard confirmed as MIRR data source. Camp Blanding FPL substation: HIGH / Near-Term.")
status_line(TAG_GIS, "Spatial extent of wildfire hazard along FPL corridor needs GIS overlay.")

# ── 2.4 ──────────────────────────────────────────────────────────────────────
h1("2.4  Historical Events — Evidence the Risk Is Real")

h2("Confirmed in MIRR Documents")
mixed("NS Mayport — recurring flooding: ",
      "Multiple flooding events per year. Commanding officer cited as most pressing "
      "operational concern. (Stakeholder Workshop 1 Summary V2)")
mixed("NAS Jacksonville — 106 mph wind gust, 1997: ",
      "Documented in MIRR evaluation methodology. Establishes hurricane-force wind "
      "as a demonstrated regional hazard.")
mixed("Blount Island — active water intrusion: ",
      "Water intrusion already threatening electrical systems. Current ongoing "
      "degradation, not a future scenario. (Kickoff Briefing, April 2025)")
mixed("Tyndall AFB — Hurricane Michael, 2018: ",
      "On-base hardening proved insufficient when surrounding utilities and roads "
      "failed. Established the regional dependency lesson. (APTIM memo, Section 1.1)")
status_line(TAG_CONFIRMED, "All four items sourced to confirmed MIRR project documents.")

h2("From Public Record — Needs Primary Source Before Formal Use")
mixed("Hurricane Matthew, October 2016 — ",
      "Historic St. Johns River flooding in Jacksonville. A1A flooded. "
      "JEA reported widespread Duval County outages.\n"
      "         Verify: NOAA NHC report AL142016, Florida PSC JEA storm filing, "
      "NOAA Storm Events Database (Duval, Oct 2016)")
mixed("Hurricane Irma, September 2017 — ",
      "JEA reported 200,000+ customers without power at peak across Jacksonville.\n"
      "         Verify: NOAA NHC report AL112017, Florida PSC JEA storm filing, "
      "FEMA declaration DR-4337")
status_line(TAG_VERIFY, "Do not cite Matthew or Irma in formal deliverables until PSC filings and NHC reports are pulled.")

# ── 2.5 ──────────────────────────────────────────────────────────────────────
h1("2.5  GIS Analyses Planned")
body("The following will spatially confirm and quantify the vulnerabilities documented above.")

t2 = doc.add_table(rows=1, cols=3)
t2.style = "Table Grid"
tbl_header(t2, ["Analysis", "Primary Dataset / Source", "What It Will Confirm"])
gis_rows = [
    ("Substation locations vs. surge zones\n(check FEMA effective and preliminary maps)",
     "HIFLD substations; NHC SLOSH\nFEMA MSC (both versions)",
     "Which substations fall within Cat 3/5 surge; whether preliminary maps show higher risk than effective"),
    ("Access corridors vs. flood zones",
     "FDOT road network; NEFRC CDBG\nFEMA NFHL; Resilient Jax",
     "Which corridors flood and at what storm frequency"),
    ("Transmission routing upstream of substations",
     "EIA Form 860; HIFLD transmission lines\nUS-17 corridor verification",
     "Upstream node count and flood exposure; confirms or refutes Part 1 US-17 SPOF claim"),
    ("FPL corridor wildfire exposure",
     "USDA FS Wildfire Hazard Potential\nHIFLD transmission lines",
     "Wildfire hazard extent along Camp Blanding supply corridor"),
    ("Water table at substation locations",
     "USGS National Map / 3DEP\nSJRWMD groundwater data",
     "Undergrounding feasibility constraints at each site"),
    ("Coastal damage estimates — Mayport and Blount Island",
     "USACE Jacksonville District\ncoastal damage models",
     "Infrastructure damage estimates under surge scenarios"),
]
for i, r in enumerate(gis_rows):
    tbl_row(t2, r, alt=(i % 2 == 1))
doc.add_paragraph()
status_line(TAG_GIS, "Tier 1 (public data, available now): HIFLD, EIA, NOAA, FEMA, USDA FS, FDOT, USGS. "
            "Tier 2 (needs data agreements, August–September budget approval): JEA routing, "
            "NAVFAC outage history, USACE detailed models.")

# ── 2.6 ──────────────────────────────────────────────────────────────────────
h1("2.6  Items Requiring Research Before Any Proposal Can Be Made")
body(
    "These items have been raised in prior research but are not ready for any formal "
    "deliverable. Each entry documents what is known and exactly what work is needed next."
)

t3 = doc.add_table(rows=1, cols=3)
t3.style = "Table Grid"
tbl_header(t3, ["Item", "What Is Known", "Next Steps Required"])
research_rows = [
    ("Small Modular Reactors / DoD Microreactors",
     "DoD's Project Pele pursues on-site microreactors for military installations — would "
     "eliminate civilian grid dependency entirely. Most complete redundancy solution; "
     "also most complex and regulatory-intensive.",
     "Research Project Pele status and applicable installations. Contact DOE and confirm "
     "ENRIL organization name with manager. Assess NRC regulatory pathway."),
    ("Electrical infrastructure insurance",
     "Type and scope of insurance JEA and FPL carry on these substations is unknown. "
     "Claims timeline after storm events directly affects how long outages last.",
     "Review Florida PSC utility insurance filings. Check JEA and FPL annual reports. "
     "Determine whether FEMA NFIP covers utility substations."),
    ("Miramar landfill methane / 21-day islanding",
     "APTIM memo confirms only 'microgrid and energy resilience investments' at Miramar. "
     "21-day figure and landfill methane source unconfirmed.",
     "Find DOE 2022 report cited in APTIM. Map Jacksonville-area landfill proximity "
     "to NAS JAX and Blount Island via GIS."),
    ("Solar PV + BESS at Camp Blanding",
     "Costs have declined significantly. 73,000 acres available. EUL authority exists. "
     "No Blanding-specific feasibility study found in MIRR documents.",
     "Search ESTCP and ESPC for prior studies at Blanding. Obtain load profile data. "
     "Confirm EUL process timeline."),
    ("JEA upstream transmission routing",
     "Confirmed MIRR data gap — JEA has not shared infrastructure data as of Sept 2025 TAC.",
     "JEA coordination under expanded IGSA. EIA Form 860 as interim proxy. "
     "Florida PSC storm hardening filings for JEA planned investments."),
    ("Historical outage data at installations",
     "Regional outages from Matthew and Irma are documented publicly. "
     "Installation-specific outage duration is not in public record.",
     "Florida PSC JEA storm filings. EIA-417 post-event outage reports. "
     "NAVFAC coordination for installation-level data."),
]
for i, r in enumerate(research_rows):
    tbl_row(t3, r, alt=(i % 2 == 1))
doc.add_paragraph()
status_line(TAG_VERIFY, "None of the above should appear in any client-facing document until the listed research is completed.")

# ── 2.7 Sources ───────────────────────────────────────────────────────────────
h1("2.7  Sources")

h2("Confirmed MIRR Project Documents")
for s in [
    "NEFRC MIRR Vulnerability Assessment — January 2026 Steering Committee",
    "MIRR Mutual Support Assessment — February 2026 TAC",
    "MIRR Adaptation Planning Framework — April 2026 Steering Committee",
    "MCSF Blount Island Kickoff Briefing — April 2025",
    "NAS Jacksonville Site Visit Summary V3",
    "Camp Blanding Summary V2",
    "NEFRC MIRR Stakeholder Workshop 1 Summary V2",
    "APTIM Memo: NE MIRR Evaluating Potential Adaptation Solutions — May 22, 2026",
]:
    bullet(s)

h2("To Verify — Historical Events")
for s in [
    "NOAA NHC Post-Storm Reports — Matthew (AL142016), Irma (AL112017)",
    "NOAA Storm Events Database — Duval and Clay Counties, 2015–present",
    "NWS Jacksonville Local Storm Event Archive",
    "Florida PSC Storm Protection Plan Filings — JEA and FPL",
    "FEMA Disaster Declarations — DR-4283 (Matthew), DR-4337 (Irma)",
]:
    bullet(s)

h2("GIS Datasets — Planned Use")
for s in [
    "HIFLD Open Data — military boundaries, transmission lines, substations",
    "EIA Form 860 — substation and generation facility locations",
    "NOAA Digital Coast — SLOSH surge modeling, sea level rise projections",
    "FEMA Flood Map Service Center — NFHL (effective and preliminary versions)",
    "FDOT GIS — Florida road network",
    "USDA Forest Service Wildfire Hazard Potential",
    "USGS National Map / 3DEP — elevation and groundwater",
    "SJRWMD — groundwater and water resource data",
    "Resilient Jacksonville — NEFRC CDBG compound flood model",
    "USACE Jacksonville District — coastal damage modeling",
    "Department of Energy — energy resilience research and program data",
    "Florida PSC — utility storm hardening filings and niche utility data",
]:
    bullet(s)

# ─────────────────────────────────────────────────────────────────────────────
out = "/home/user/HERMES/resilience_review/MIRR_Energy_Combined_Contribution.docx"
doc.save(out)
print(f"Saved: {out}")
