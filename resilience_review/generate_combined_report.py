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

def heading(text, level=1):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(14 if level == 1 else 8)
    p.paragraph_format.space_after  = Pt(4)
    run = p.add_run(text)
    if level == 1:
        font(run, size=13, bold=True, color=(31, 73, 125))
    elif level == 2:
        font(run, size=11, bold=True, color=(55, 96, 146))
    else:
        font(run, size=11, bold=True, italic=True)

def body(text, space_after=6, italic=False, color=None):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(space_after)
    run = p.add_run(text)
    font(run, italic=italic, color=color)
    return p

def note(text, kind="GIS"):
    colors = {
        "GIS":      ("FFF4E5", (102, 51, 0)),
        "verify":   ("FFF0F0", (120, 0,  0)),
        "confirmed":("EAF4EA", (0,  80, 0)),
    }
    fill, tc = colors.get(kind, colors["GIS"])
    p = doc.add_paragraph()
    p.paragraph_format.left_indent  = Inches(0.3)
    p.paragraph_format.right_indent = Inches(0.3)
    p.paragraph_format.space_after  = Pt(6)
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"),   "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"),  fill)
    p._p.get_or_add_pPr().append(shd)
    labels = {"GIS": "Needs GIS: ", "verify": "Needs verification: ",
              "confirmed": "Confirmed: "}
    r1 = p.add_run(labels.get(kind, "Note: "))
    font(r1, size=10, bold=True, color=tc)
    r2 = p.add_run(text)
    font(r2, size=10, italic=True, color=tc)

def quote(text, source):
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Inches(0.4)
    p.paragraph_format.space_after = Pt(6)
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

def mixed(label, rest, indent=0):
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.left_indent = Inches(0.25 + indent * 0.2)
    r1 = p.add_run(label)
    font(r1, bold=True)
    r2 = p.add_run(rest)
    font(r2)

def divider(label, fill="1F497D"):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(16)
    p.paragraph_format.space_after  = Pt(4)
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"),   "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"),  fill)
    p._p.get_or_add_pPr().append(shd)
    run = p.add_run(f"  {label}")
    font(run, size=12, bold=True, color=(255, 255, 255))

def shaded_box(label, text, fill="EAF0F8", tc=(31, 73, 125)):
    p = doc.add_paragraph()
    p.paragraph_format.left_indent  = Inches(0.3)
    p.paragraph_format.right_indent = Inches(0.3)
    p.paragraph_format.space_after  = Pt(10)
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"),   "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"),  fill)
    p._p.get_or_add_pPr().append(shd)
    r1 = p.add_run(label + "\n")
    font(r1, size=10, bold=True, color=tc)
    r2 = p.add_run(text)
    font(r2, size=10, italic=True, color=tc)

def centered(text, size=11, bold=False, italic=False,
             color=(0,0,0), space_before=0, space_after=4):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.space_after  = Pt(space_after)
    run = p.add_run(text)
    font(run, size=size, bold=bold, italic=italic, color=color)

def tbl_header(tbl, cols):
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

def tbl_row(tbl, vals):
    row = tbl.add_row()
    for i, text in enumerate(vals):
        cell = row.cells[i]
        cell.text = ""
        p   = cell.paragraphs[0]
        p.paragraph_format.space_after = Pt(2)
        run = p.add_run(text)
        font(run, size=9.5)

# ═════════════════════════════════════════════════════════════════════════════
# COVER
# ═════════════════════════════════════════════════════════════════════════════
centered("Northeast Florida Military Installation Resilience Review",
         size=16, bold=True, color=(31,73,125), space_before=20, space_after=4)
centered("Energy Redundancy — Combined Intern Research Contribution",
         size=13, bold=True, color=(55,96,146), space_after=4)
centered(
    "Naval Air Station Jacksonville  |  Naval Station Mayport\n"
    "MCSF Blount Island  |  Camp Blanding JTF\n"
    "Duval County and Clay County, Florida",
    size=10, color=(89,89,89), space_after=4)
centered("Prepared for Supervisor Review — May 2026",
         size=10, italic=True, color=(89,89,89), space_after=10)

shaded_box(
    "About This Document",
    "This document combines two intern research contributions focused specifically on "
    "energy redundancy. Part 1 preserves the first intern's research findings verbatim. "
    "Part 2 adds geographic and vulnerability context developed through MIRR document review. "
    "No GIS analysis has been performed yet — GIS work is in progress and will spatially "
    "confirm or refine the findings stated here. No solutions or strategies are proposed. "
    "Items requiring verification before any proposal can be made are clearly labeled."
)

# ═════════════════════════════════════════════════════════════════════════════
# PART 1
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
body("These risks are exasperated by increasing energy demand throughout the region and lack "
     "of redundancy of power supply to installations.")
body("There are reports of aging infrastructure serving the installations which only increases "
     "the likelihood of single-point failure.")
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
bullet("Flood-proofing substations and supply lines are the most pressing short term adaptation "
       "strategy. Mutual Support Agreements (MSAs) are drafted to formalize collaboration between "
       "utility companies, local government agencies, and the installations themselves.")
bullet("Flood proofing and undergrounding may provide more cost-effective resilience than large "
       "scale sea-walling measures.")
bullet("Formalizing loose MSA agreements for current and future adaptation projects may improve efficiency.")
bullet("Addressing redundancy gaps in both electrical and fuel systems by creating backup paths and stocks.")

heading("Long Term", level=2)
bullet("Expand monitoring systems and data collection of grid and other infrastructure to better "
       "predict outages and manage performance. This data can be used to assess effectiveness of "
       "adaptation projects in terms of outages avoided and guide future projects.")
bullet("Microgrids could offer both independent resilience and eventually the ability to support "
       "the larger grid with BESS infrastructure. Microgrid feasibility studies are already underway.")

heading("Areas to Explore More", level=2)
bullet("Prices of battery storage and Solar PV have both fallen dramatically in recent years. "
       "Minimal mention of either technology, but could a feasibility study be completed? "
       "The two in tandem could be beneficial.")
bullet("Miramar MC Air Station outside San Diego, CA uses a blend of energy sources and BESS "
       "to provide up to 21 days of islanded energy resilience. Methane gas from landfills is "
       "a significant energy source. Could the several landfills surrounding Jacksonville provide "
       "similar energy sources or redundancy?")
bullet("Marine Corp Story")
bullet("Full CA State Project Report")

# ═════════════════════════════════════════════════════════════════════════════
# PART 2
# ═════════════════════════════════════════════════════════════════════════════
divider("PART 2 — Second Intern's Research Contribution")
doc.add_paragraph()

shaded_box(
    "Scope Notice",
    "All vulnerability findings in Part 2 are cited from confirmed MIRR project documents. "
    "No independent GIS analysis has been performed. Color-coded notes throughout indicate "
    "whether each point is confirmed (green), needs GIS to verify spatially (orange), "
    "or needs external source verification before it can be used (red).",
    fill="FFF4E5", tc=(102, 51, 0)
)

# ── 2.1 Core problem ──────────────────────────────────────────────────────────
heading("2.1  The Core Problem: Zero Electrical Redundancy", level=1)
body(
    "The MIRR vulnerability assessment identifies a single finding that frames everything else "
    "about energy at these installations. It is not a broad energy risk — it is a specific "
    "structural gap:"
)
quote(
    "At the asset systems level there is no immediate risk to mission other than single points "
    "of failure at each installation.",
    "MIRR Vulnerability Assessment, January 2026 Steering Committee"
)
body(
    "All four installations draw power from a single external substation with no backup supply "
    "path. If that substation fails — for any reason — the installation loses commercial power "
    "entirely. There is no second line, no alternative feed, no redundant path. The utility "
    "agreements (IGSAs) at NAS JAX and NS Mayport cover operations and maintenance only — they "
    "include no resilience or redundancy obligation on JEA's part."
    "  (MIRR Mutual Support Assessment, February 2026 TAC)"
)
note("Confirmed by MIRR VA and Mutual Support Assessment. No GIS needed to state this finding.",
     kind="confirmed")

body("Confirmed substation locations and risk ratings from the MIRR VA:")
t1 = doc.add_table(rows=1, cols=4)
t1.style = "Table Grid"
tbl_header(t1, ["Installation", "Substation / Owner", "Risk to Mission", "Urgency"])
tbl_row(t1, ["NS Mayport",        "JEA — south of base",  "HIGH",   "Immediate"])
tbl_row(t1, ["MCSF Blount Island","JEA Substation",       "MEDIUM", "Immediate"])
tbl_row(t1, ["NAS Jacksonville",  "JEA — north of base",  "MEDIUM", "Immediate"])
tbl_row(t1, ["Camp Blanding",     "FPL — north of base",  "HIGH",   "Near-Term"])
doc.add_paragraph()

# ── 2.2 Why redundancy is hard here ──────────────────────────────────────────
heading("2.2  Why Redundancy Is Harder Here Than Elsewhere", level=1)
body(
    "The specific geography of Northeast Florida creates constraints that make standard "
    "redundancy solutions more complex than they would be in other regions. These are not "
    "general observations — they are specific to this area."
)

heading("Shallow Water Table — Complicates Undergrounding", level=2)
body(
    "Part 1 correctly identifies undergrounding as a potential resilience measure. In coastal "
    "Duval County the water table in many areas sits only a few feet below grade. Underground "
    "cables in a high water table environment face groundwater intrusion, saltwater corrosion "
    "from below, and significantly harder fault location and repair when failures occur. "
    "JEA has been selectively undergrounding in northeast Florida but has proceeded cautiously "
    "precisely because of these conditions. Undergrounding trades wind and debris vulnerability "
    "for below-grade flood and corrosion vulnerability — it is not a clean redundancy solution "
    "in this specific region."
)
note("The shallow water table is a confirmed regional condition. Specific depths at substation "
     "locations and along potential redundant feed corridors need GIS and geotechnical data "
     "to confirm.", kind="GIS")

heading("Limited Access Corridors — Compounds Restoration Timelines", level=2)
body(
    "The installations' geographic positions create inherent access constraints that directly "
    "affect how long an outage lasts once it occurs:"
)
mixed("NS Mayport: ", "A1A is the primary southern access corridor. The installation sits on "
      "a coastal peninsula — flooding of A1A isolates restoration crews regardless of "
      "substation condition.")
mixed("MCSF Blount Island: ", "Heckscher Drive is the primary industrial access route. "
      "The installation is on an island in the St. Johns River — road access is structurally "
      "limited by geography.")
mixed("NAS Jacksonville: ", "Roosevelt Boulevard and US-17 are the primary corridors. "
      "Both run through low-lying terrain along the St. Johns River floodplain.")
mixed("Camp Blanding: ", "SR-16 is the primary access route through Clay County. "
      "Black Creek flooding closes surrounding roads even in tropical storm conditions.")
note("Access corridor flood exposure needs GIS overlay against SLOSH and CDBG flood models "
     "to confirm at which storm frequencies each corridor becomes impassable.", kind="GIS")

heading("Grid Topology Upstream of Each Substation — Unconfirmed", level=2)
body(
    "The installations depend on whatever grid infrastructure feeds their substations from "
    "upstream. A regional storm event can cut power to a substation even if the substation "
    "itself is physically intact — if a node upstream in the grid fails, the substation goes "
    "dark. The exact routing of transmission feeding each substation, how many upstream nodes "
    "exist, and how much of that path runs through flood-exposed terrain is not documented "
    "in the MIRR materials. JEA has not shared detailed infrastructure data with the MIRR "
    "team as of the September 2025 TAC."
)
note("JEA utility infrastructure data is a confirmed MIRR data gap. Transmission routing "
     "upstream of each substation needs JEA coordination and GIS mapping before the full "
     "redundancy picture can be understood.", kind="GIS")

# ── 2.3 Regional hazards ──────────────────────────────────────────────────────
heading("2.3  Regional Hazards That Trigger the Redundancy Gap", level=1)
body(
    "The redundancy gap becomes a mission risk when a hazard event disrupts the single supply "
    "path. The following hazards are confirmed by the MIRR vulnerability assessment as relevant "
    "to this specific region — they are not generic national risks."
)

heading("Storm Surge — NS Mayport and Blount Island", level=2)
body(
    "Both installations sit adjacent to the St. Johns River mouth and the Atlantic coast. "
    "NHC SLOSH modeling confirms Cat 3–5 surge reaches the substations serving these "
    "installations. NS Mayport's JEA substation carries the highest urgency rating in the "
    "entire region — HIGH / Immediate — specifically because of surge exposure combined "
    "with zero redundancy. Storm surge does not just threaten the substation physically; "
    "it also inundates the access corridors that restoration crews depend on, extending "
    "the outage duration beyond the physical damage window."
)
note("SLOSH surge extents confirmed as MIRR data source. Spatial overlay of substation "
     "locations against Cat 3/5 surge zones needs GIS confirmation — viewable now through "
     "NOAA Digital Coast web viewer without ArcGIS.", kind="GIS")

heading("Rainfall Flooding and Compound Events — NAS Jacksonville", level=2)
body(
    "NAS Jacksonville sits along the St. Johns River floodplain. The NEFRC CDBG flood model "
    "confirms 100-year present, 2040, and 2070 rainfall flood scenarios for this area. "
    "Compound flooding — where rainfall runoff cannot drain because tidal backflow holds "
    "water levels elevated — is a confirmed and increasing risk in coastal Duval County. "
    "Roosevelt Boulevard and US-17, the primary restoration access corridors for NAS JAX, "
    "run through this terrain."
)
note("CDBG compound flood model is a confirmed MIRR data source. Road corridor intersection "
     "with flood zones needs GIS overlay.", kind="GIS")

heading("Wildfire — Camp Blanding Transmission Corridor", level=2)
body(
    "Camp Blanding's 73,000 acres sit within Florida's wildland-urban interface in Clay County. "
    "The FPL transmission corridor serving the base runs through scrub and longleaf pine "
    "terrain confirmed as wildfire-exposed by USDA Forest Service data cited in the MIRR. "
    "Unlike storm events, wildfire can cut the transmission corridor without weather warning "
    "and during periods of clear operational tempo — making it a distinct and unpredictable "
    "trigger for the redundancy gap."
)
note("USDA FS wildfire hazard is a confirmed MIRR data source. Spatial extent of wildfire "
     "hazard along the specific FPL corridor to Blanding needs GIS overlay.", kind="GIS")

# ── 2.4 Historical events ─────────────────────────────────────────────────────
heading("2.4  Historical Events — Evidence the Risk Is Real", level=1)
body(
    "The following events document that the hazards identified above have occurred in this "
    "specific region and caused the types of disruption the redundancy gap makes dangerous. "
    "Items confirmed in MIRR documents are labeled. Items from public record that need "
    "primary source citation before use in a formal deliverable are labeled separately."
)

heading("Confirmed in MIRR Documents", level=2)
mixed("NS Mayport — recurring flooding: ",
      "Multiple flooding events per year confirmed as the commanding officer's most pressing "
      "operational concern. (MIRR Stakeholder Workshop 1 Summary V2)")
mixed("NAS Jacksonville — 106 mph wind gust, 1997: ",
      "Confirmed in MIRR evaluation methodology as documented regional wind event. "
      "Establishes hurricane-force wind as a demonstrated, not theoretical, hazard.")
mixed("MCSF Blount Island — active water intrusion: ",
      "Water intrusion already threatening electrical systems confirmed in Kickoff Briefing, "
      "April 2025. This is ongoing degradation, not a past event.")
mixed("Tyndall AFB — Hurricane Michael, 2018: ",
      "Confirmed in APTIM memo Section 1.1. On-base hardening proved insufficient when "
      "surrounding utilities, roads, and civilian infrastructure failed. Established the "
      "regional dependency lesson that frames this entire assessment.")

heading("From Public Record — Needs Primary Source Before Formal Use", level=2)
body(
    "The following events are well-documented in public records and directly relevant to "
    "this project. They should be verified through the sources listed before being cited "
    "in any client-facing document."
)
mixed("Hurricane Matthew, October 2016: ",
      "Made near-landfall north of Jacksonville. Caused historic St. Johns River flooding "
      "described as the worst in decades. A1A — NS Mayport's primary access corridor — "
      "flooded significantly. JEA reported widespread Duval County outages.\n"
      "     Verify through: NOAA NHC post-storm report, Florida PSC JEA storm filing, "
      "NOAA Storm Events Database (Duval County, October 2016)")
mixed("Hurricane Irma, September 2017: ",
      "JEA reported over 200,000 customers without power at peak across Jacksonville. "
      "Demonstrates regional grid vulnerability to storms tracking up the peninsula.\n"
      "     Verify through: NOAA NHC post-storm report, Florida PSC JEA storm filing, "
      "FEMA disaster declaration FL-4337")

note("Until Matthew and Irma outage data is pulled from Florida PSC filings and NOAA NHC "
     "reports, these should not be stated as confirmed findings in client documents. "
     "They are included here as research direction.", kind="verify")

# ── 2.5 What GIS will confirm ─────────────────────────────────────────────────
heading("2.5  What GIS Will Confirm — Specific Analyses Planned", level=1)
body(
    "GIS does not create the vulnerabilities documented above — the MIRR has already confirmed "
    "those qualitatively. GIS will spatially verify, quantify, and visually communicate each "
    "finding. The following table lists the specific analyses planned and the datasets required."
)

t2 = doc.add_table(rows=1, cols=4)
t2.style = "Table Grid"
tbl_header(t2, ["Analysis", "Datasets", "Source", "What It Confirms"])
gis = [
    ("Substation locations vs. surge zones",
     "HIFLD substations, NHC SLOSH Cat 3/5",
     "HIFLD Open; NOAA Digital Coast",
     "Which substations fall within confirmed surge extents"),
    ("Access corridors vs. flood zones",
     "FDOT road network, NEFRC CDBG, FEMA NFHL",
     "FDOT GIS; FEMA MSC; Resilient Jax",
     "Which corridors flood and at what storm frequency"),
    ("Transmission routing — upstream of each substation",
     "EIA Form 860, HIFLD transmission lines",
     "EIA.gov; HIFLD Open",
     "How many upstream nodes exist and their flood exposure"),
    ("US-17 transmission corridor",
     "EIA / HIFLD transmission lines",
     "HIFLD Open",
     "Whether lines along US-17 serve these installations"),
    ("FPL corridor wildfire exposure",
     "USDA FS wildfire hazard, EIA lines",
     "USDA FS Research Data; HIFLD",
     "Wildfire hazard extent along Camp Blanding supply corridor"),
    ("Water table depth at substation locations",
     "USGS groundwater data, SJRWMD",
     "USGS National Map; SJRWMD portal",
     "Feasibility constraints for undergrounding at each site"),
]
for r in gis:
    tbl_row(t2, r)
doc.add_paragraph()

# ── 2.6 What still needs research ────────────────────────────────────────────
heading("2.6  Items Requiring Research Before Any Proposal Can Be Made", level=1)
body(
    "The following items were raised in prior research but cannot be included in any "
    "professional deliverable until the work below is completed. They are documented here "
    "so the research path is clear."
)

t3 = doc.add_table(rows=1, cols=3)
t3.style = "Table Grid"
tbl_header(t3, ["Item", "What Is Known", "What Is Needed Before Use"])
research = [
    ("Miramar landfill methane / 21-day islanding",
     "First intern identified Miramar as a potential model. APTIM memo confirms only "
     "'microgrid and energy resilience investments' at Miramar — no landfill methane "
     "or islanding duration confirmed.",
     "Primary source (DOE 2022 report cited in APTIM). GIS mapping of Jacksonville-area "
     "landfill proximity to installations. Pipeline feasibility assessment."),
    ("Tidal energy at NS Mayport / Blount Island",
     "St. Johns River mouth has high tidal flow. Tidal converters sit below surge. "
     "No feasibility study found in MIRR documents.",
     "DOE Water Power Technologies Office feasibility study search. Navigation channel "
     "and environmental permitting review. Site-specific flow rate data from USGS or NOAA."),
    ("Solar PV + BESS at Camp Blanding",
     "Costs have declined. Land available. EUL authority exists. "
     "No Blanding-specific feasibility study found in MIRR documents.",
     "ESTCP / ESPC prior study search. Camp Blanding load profile data. "
     "EUL process timeline and authority confirmation."),
    ("JEA transmission routing upstream of substations",
     "Confirmed data gap in MIRR — JEA has not shared infrastructure data "
     "as of Sept 2025 TAC.",
     "JEA coordination under expanded IGSA. EIA Form 860 as proxy. "
     "Florida PSC storm hardening filings for JEA."),
    ("Actual outage history at installations",
     "Regional outages from Matthew and Irma are publicly documented. "
     "Installation-specific outage duration is not in public record.",
     "Florida PSC JEA storm filings. EIA-417 post-event outage reports. "
     "NAVFAC coordination for installation-level data."),
]
for r in research:
    tbl_row(t3, r)
doc.add_paragraph()

# ── Sources ───────────────────────────────────────────────────────────────────
heading("2.7  Sources", level=1)
body("Confirmed MIRR project documents:")
for s in [
    "NEFRC MIRR Vulnerability Assessment — January 2026 Steering Committee",
    "MIRR Mutual Support Assessment — February 2026 TAC",
    "MCSF Blount Island Kickoff Briefing — April 2025",
    "NAS Jacksonville Site Visit Summary V3",
    "Camp Blanding Summary V2",
    "NEFRC MIRR Stakeholder Workshop 1 Summary V2",
    "APTIM Memo: NE MIRR Evaluating Potential Adaptation Solutions — May 22, 2026",
]:
    bullet(s)

body("Sources to verify for historical event evidence:", space_after=3)
for s in [
    "NOAA NHC Post-Storm Reports — Hurricane Matthew (AL142016), Hurricane Irma (AL112017)",
    "NOAA Storm Events Database — Duval and Clay Counties, 2015–present",
    "Florida PSC Storm Protection Plan Filings — JEA and FPL annual reports",
    "FEMA Disaster Declarations — DR-4283 (Matthew), DR-4337 (Irma)",
    "NWS Jacksonville Local Storm Event Archive",
]:
    bullet(s)

body("GIS datasets to be used:", space_after=3)
for s in [
    "HIFLD Open Data — military boundaries, transmission lines, substations",
    "EIA Form 860 — substation and generation facility locations",
    "NOAA Digital Coast — SLOSH surge modeling, sea level rise viewer",
    "FEMA Flood Map Service Center — National Flood Hazard Layer",
    "FDOT GIS — Florida road network",
    "USDA Forest Service Wildfire Hazard Potential — national raster dataset",
    "USGS National Map / 3DEP — elevation and groundwater data",
    "SJRWMD — St. Johns River Water Management District water resource data",
    "Resilient Jacksonville — NEFRC CDBG compound flood model outputs",
]:
    bullet(s)

# ─────────────────────────────────────────────────────────────────────────────
out = "/home/user/HERMES/resilience_review/MIRR_Energy_Combined_Contribution.docx"
doc.save(out)
print(f"Saved: {out}")
