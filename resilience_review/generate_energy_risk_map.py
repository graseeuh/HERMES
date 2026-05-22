"""
Northeast Florida Military Installation — Energy Risk Map
NEFRC MIRR | Duval County & Clay County, FL
Generates: energy_risk_map.html

All installation locations, substation data, risk ratings, and urgency levels
are sourced directly from the NEFRC MIRR Vulnerability Assessment
(January 2026 Steering Committee) and supporting MIRR documents.
"""

import folium

CENTER = [30.20, -81.70]

m = folium.Map(
    location=CENTER,
    zoom_start=10,
    tiles="CartoDB positron",
    control_scale=True,
)

# ── Layer groups ──────────────────────────────────────────────────────────────
grp_install     = folium.FeatureGroup(name="Military Installations", show=True)
grp_substations = folium.FeatureGroup(name="Energy SPOFs (Substations)", show=True)
grp_risks       = folium.FeatureGroup(name="Hazard Exposure Zones", show=True)
grp_existing    = folium.FeatureGroup(name="Existing Resilience Projects", show=True)
grp_adapt       = folium.FeatureGroup(name="Adaptation Priorities (MIRR R-2)", show=True)

# ── Military Installations ────────────────────────────────────────────────────
# Coordinates: HIFLD / confirmed MIRR map
installations = [
    {
        "name": "Naval Air Station Jacksonville",
        "coords": [30.2355, -81.6801],
        "county": "Duval County",
        "primary_mission": "Naval aviation hub, training & readiness, logistical & maintenance support",
        "energy_risk": "MEDIUM — IMMEDIATE",
        "energy_detail": "JEA substation (north of base) — Lack of redundancy. "
                         "All primary mission loads depend on single external feed. "
                         "JEA grid hardening + microgrid feasibility study underway.",
        "spof": "JEA Substation (north of base)",
        "color": "blue",
    },
    {
        "name": "Naval Station Mayport",
        "coords": [30.3957, -81.4228],
        "county": "Duval County (coastal)",
        "primary_mission": "4th Fleet homeport, UAV operations, major ship repair, regional fuel depot",
        "energy_risk": "HIGH — IMMEDIATE",
        "energy_detail": "JEA Mayport Substation (south of base) — Storm surge + rainfall flooding. "
                         "Highest energy risk in the region. Single power source dependency "
                         "confirmed by Commanding Officer. Annual flooding events.",
        "spof": "JEA Mayport Substation (south of base)",
        "color": "red",
    },
    {
        "name": "MCSF Blount Island",
        "coords": [30.3900, -81.5100],
        "county": "Duval County (St. Johns River)",
        "primary_mission": "Marine global pre-positioning, crisis response ship loading & deployment",
        "energy_risk": "MEDIUM — IMMEDIATE",
        "energy_detail": "JEA substation — Storm surge + lack of redundancy. "
                         "Mission hinges on reliable power for crisis response operations. "
                         "P035 Dual Fuel Generator Project (ERCIP funded, FDA underway) will "
                         "install generators in all 9 critical facilities.",
        "spof": "JEA Substation",
        "color": "orange",
    },
    {
        "name": "Camp Blanding Joint Training Center",
        "coords": [29.9457, -82.0102],
        "county": "Clay County",
        "primary_mission": "Level II Garrison Training Center, FL National Guard, backup state EOC",
        "energy_risk": "HIGH — NEAR-TERM",
        "energy_detail": "FPL substation (north of base) — Lack of redundancy + wildfire exposure. "
                         "County served by four separate power providers + Seminole Electric — "
                         "coordination and redundancy challenges confirmed.",
        "spof": "FPL Substation (north of base)",
        "color": "red",
    },
]

icon_colors = {"HIGH — IMMEDIATE": "red", "MEDIUM — IMMEDIATE": "orange",
               "HIGH — NEAR-TERM": "red", "MEDIUM — NEAR-TERM": "orange"}

for inst in installations:
    folium.Marker(
        location=inst["coords"],
        popup=folium.Popup(
            f"<b>{inst['name']}</b><br>"
            f"<i>{inst['county']}</i><br><br>"
            f"<b>Primary Mission:</b><br>{inst['primary_mission']}<br><br>"
            f"<b>Energy Risk to Mission:</b> {inst['energy_risk']}<br>"
            f"{inst['energy_detail']}<br><br>"
            f"<b>Confirmed SPOF:</b> {inst['spof']}",
            max_width=360,
        ),
        tooltip=f"🏛 {inst['name']} — Energy: {inst['energy_risk']}",
        icon=folium.Icon(color=inst["color"], icon="shield", prefix="fa"),
    ).add_to(grp_install)

# ── Confirmed Energy SPOFs (substations) ─────────────────────────────────────
# Positions based on MIRR VA descriptions: "south of base", "north of base", etc.
substations = [
    {
        "name": "JEA Mayport Substation",
        "coords": [30.3870, -81.4270],
        "owner": "JEA",
        "serves": "Naval Station Mayport",
        "risk": "HIGH",
        "urgency": "Immediate",
        "hazards": "Storm surge, Rainfall flooding",
        "note": "South of NS Mayport. Within surge inundation zone. "
                "No backup supply path. O&M IGSA only — no resilience provisions.",
        "color": "red",
    },
    {
        "name": "JEA Substation — Blount Island",
        "coords": [30.3960, -81.5150],
        "owner": "JEA",
        "serves": "MCSF Blount Island",
        "risk": "Medium",
        "urgency": "Immediate",
        "hazards": "Storm surge, Lack of redundancy",
        "note": "Single feed to installation. P035 generator project will reduce "
                "dependency but does not eliminate the SPOF.",
        "color": "orange",
    },
    {
        "name": "JEA Substation — NAS Jacksonville",
        "coords": [30.2600, -81.6720],
        "owner": "JEA",
        "serves": "Naval Air Station Jacksonville",
        "risk": "Medium",
        "urgency": "Immediate",
        "hazards": "Lack of redundancy",
        "note": "North of NAS JAX. JEA conducting grid hardening + "
                "microgrid feasibility study. O&M IGSA only — no resilience provisions.",
        "color": "orange",
    },
    {
        "name": "FPL Substation — Camp Blanding",
        "coords": [29.9700, -82.0050],
        "owner": "FPL",
        "serves": "Camp Blanding JTF",
        "risk": "HIGH",
        "urgency": "Near-Term",
        "hazards": "Lack of redundancy, Wildfire",
        "note": "North of base. No formal resilience coordination with FPL. "
                "Wildfire risk along transmission corridor. County relies on "
                "4 power providers + Seminole Electric.",
        "color": "red",
    },
]

for sub in substations:
    folium.CircleMarker(
        location=sub["coords"],
        radius=13,
        color=sub["color"],
        fill=True,
        fill_color=sub["color"],
        fill_opacity=0.75,
        popup=folium.Popup(
            f"<b>⚡ {sub['name']}</b><br>"
            f"Owner: {sub['owner']}<br>"
            f"Serves: {sub['serves']}<br><br>"
            f"<b>Risk to Mission:</b> {sub['risk']}<br>"
            f"<b>Urgency:</b> {sub['urgency']}<br>"
            f"<b>Hazards:</b> {sub['hazards']}<br><br>"
            f"{sub['note']}",
            max_width=340,
        ),
        tooltip=f"⚡ {sub['name']} — {sub['risk']} / {sub['urgency']}",
    ).add_to(grp_substations)

# ── Hazard Exposure Zones ─────────────────────────────────────────────────────
# Based on MIRR VA hazard scenarios (SLOSH Cat 3/5, CDBG flood, USDA wildfire)
hazard_zones = [
    {
        "name": "NS Mayport Storm Surge Zone (Cat 3–5 SLOSH)",
        "coords": [
            [30.4200, -81.4600], [30.4200, -81.3800],
            [30.3600, -81.3800], [30.3600, -81.4600],
        ],
        "source": "NHC SLOSH Model / Resilient Jax",
        "risk": "CRITICAL — Substation and primary access routes (A1A) within inundation footprint",
        "color": "#CC0000",
    },
    {
        "name": "Blount Island Surge / Compound Flood Zone",
        "coords": [
            [30.4100, -81.5400], [30.4100, -81.4800],
            [30.3700, -81.4800], [30.3700, -81.5400],
        ],
        "source": "Resilient Jax Compound Flood Model (2070 scenario)",
        "risk": "HIGH — Shoreline loss + water intrusion threatening electrical systems; "
                "northwest armored shoreline and central canal are priority risk corridors",
        "color": "#CC0000",
    },
    {
        "name": "NAS Jacksonville Rainfall / Compound Flood Zone",
        "coords": [
            [30.2700, -81.7300], [30.2700, -81.6200],
            [30.2000, -81.6200], [30.2000, -81.7300],
        ],
        "source": "NEFRC CDBG Flood Model (100-yr present + 2070 scenario)",
        "risk": "MEDIUM — St. Johns River floodplain; Roosevelt Blvd (US-17) SPOF for "
                "restoration access; JEA substation north of base",
        "color": "#FF8C00",
    },
    {
        "name": "Camp Blanding Wildfire-Transmission Corridor (WUI)",
        "coords": [
            [30.0200, -82.0800], [30.0200, -81.9500],
            [29.8800, -81.9500], [29.8800, -82.0800],
        ],
        "source": "USDA Forest Service Research Data / Camp Blanding prescribed fire records",
        "risk": "HIGH — FPL transmission corridor traverses wildland-urban interface; "
                "100+ wildfires/yr responded to at Blanding; transmission line fire risk confirmed",
        "color": "#DAA520",
    },
    {
        "name": "A1A Coastal Surge / SLR Exposure (MIRR Priority)",
        "coords": [
            [30.4100, -81.4200], [30.4100, -81.3700],
            [30.3300, -81.3700], [30.3300, -81.4200],
        ],
        "source": "NOAA 2022 SLR Projections / FDEP shoreline data",
        "risk": "HIGH — A1A rated High / Immediate in MIRR VA; primary road access for "
                "NS Mayport and utility restoration crews",
        "color": "#FF8C00",
    },
]

for zone in hazard_zones:
    folium.Polygon(
        locations=zone["coords"],
        color=zone["color"],
        fill=True,
        fill_color=zone["color"],
        fill_opacity=0.15,
        weight=2,
        popup=folium.Popup(
            f"<b>{zone['name']}</b><br>"
            f"<b>Source:</b> {zone['source']}<br><br>"
            f"<b>Risk:</b> {zone['risk']}",
            max_width=340,
        ),
        tooltip=f"⚠ {zone['name']}",
    ).add_to(grp_risks)

# ── Existing Resilience Projects ──────────────────────────────────────────────
existing = [
    {
        "name": "P035 Dual Fuel Generator Project — Blount Island",
        "coords": [30.3900, -81.5100],
        "status": "ERCIP Funded — Final Design Authority (FDA) Underway",
        "detail": "Generators in all 9 critical facilities. Reduces JEA grid dependency. "
                  "Allows continued operations if JEA power grid is down.",
        "color": "green",
    },
    {
        "name": "JEA Grid Hardening + Microgrid Feasibility Study — NAS JAX",
        "coords": [30.2355, -81.6801],
        "status": "In Progress — JEA-initiated",
        "detail": "JEA conducting grid hardening and microgrid feasibility study for NAS JAX. "
                  "Identified as response to electricity being flagged as a significant vulnerability.",
        "color": "green",
    },
    {
        "name": "P036/037 Shoreline Restoration — Blount Island",
        "coords": [30.3850, -81.5050],
        "status": "Awarded $14.7M — Construction delayed (Army Permit issues)",
        "detail": "Area 2 & 3 Shoreline Restoration. Co-benefit: protects "
                  "electrical infrastructure from water intrusion and shoreline loss.",
        "color": "green",
    },
]

for proj in existing:
    folium.Marker(
        location=proj["coords"],
        popup=folium.Popup(
            f"<b>✅ {proj['name']}</b><br>"
            f"<b>Status:</b> {proj['status']}<br><br>"
            f"{proj['detail']}",
            max_width=340,
        ),
        tooltip=f"✅ {proj['name']}",
        icon=folium.Icon(color=proj["color"], icon="check", prefix="fa"),
    ).add_to(grp_existing)

# ── Adaptation Priorities (MIRR Regional Recommendation R-2) ─────────────────
priorities = [
    {
        "name": "R-2 Priority: Expand JEA IGSA → Include Resilience (NAS JAX)",
        "coords": [30.2455, -81.6601],
        "action": "Expand existing JEA IGSA at NAS JAX to include resilience and redundancy "
                  "provisions (currently O&M only). Accelerate JEA microgrid feasibility → "
                  "funded project via ERCIP or ESPC. Timeline: 0–3 years.",
        "color": "purple",
    },
    {
        "name": "R-2 Priority: Expand JEA IGSA → Include Resilience (NS Mayport)",
        "coords": [30.4057, -81.4328],
        "action": "Expand existing JEA IGSA at NS Mayport to include resilience and redundancy. "
                  "Harden Mayport Substation against storm surge (flood barriers, dry-type "
                  "transformer). HIGHEST URGENCY — High risk, Immediate timeline.",
        "color": "purple",
    },
    {
        "name": "R-2 Priority: Establish FPL Baseline Coordination (Camp Blanding)",
        "coords": [29.9557, -82.0202],
        "action": "Establish baseline resilience coordination between Camp Blanding and FPL. "
                  "Engage FPSC Storm Hardening reporting. Long-term: Solar EUL + storage "
                  "to reduce single-provider dependency. Timeline: 1–5 years.",
        "color": "purple",
    },
    {
        "name": "R-2 Priority: Regional Utility Coordination Framework",
        "coords": [30.2800, -81.6500],
        "action": "Convene JEA, FPL, Seminole Electric, CCUA, and TECO in a regional "
                  "resilience-focused MOU. All 4 installations, unified framework. "
                  "Elevate from project-scale to system-scale coordination (TAC Q4).",
        "color": "darkpurple",
    },
]

for p in priorities:
    folium.Marker(
        location=p["coords"],
        popup=folium.Popup(
            f"<b>🔧 {p['name']}</b><br><br>{p['action']}",
            max_width=360,
        ),
        tooltip=f"🔧 {p['name']}",
        icon=folium.Icon(color=p["color"], icon="wrench", prefix="fa"),
    ).add_to(grp_adapt)

# ── Add all groups ────────────────────────────────────────────────────────────
for grp in [grp_risks, grp_substations, grp_existing, grp_install, grp_adapt]:
    grp.add_to(m)

folium.LayerControl(collapsed=False).add_to(m)

# ── Legend ────────────────────────────────────────────────────────────────────
legend_html = """
<div style="position:fixed;bottom:30px;left:30px;z-index:1000;background:white;
     padding:14px 18px;border-radius:8px;border:2px solid #888;font-family:Arial,sans-serif;
     font-size:12px;box-shadow:3px 3px 6px rgba(0,0,0,0.3);max-width:240px;">
  <b style="font-size:13px;">MIRR Energy Risk Legend</b><br><br>
  <span style="color:darkblue;">&#9632;</span> Military Installation<br>
  <span style="color:red;">&#9679;</span> HIGH Risk Substation (SPOF)<br>
  <span style="color:orange;">&#9679;</span> MEDIUM Risk Substation (SPOF)<br>
  <span style="color:#CC0000;">&#9632;</span> Critical Surge/Flood Zone<br>
  <span style="color:#FF8C00;">&#9632;</span> High Flood Zone (CDBG/NFHL)<br>
  <span style="color:#DAA520;">&#9632;</span> Wildfire-Transmission WUI<br>
  <span style="color:green;">&#9632;</span> Existing Resilience Project<br>
  <span style="color:purple;">&#9632;</span> MIRR Adaptation Priority (R-2)<br><br>
  <small><i>NEFRC Military Installation Readiness Review<br>
  All risk ratings from MIRR VA (Jan 2026 SC)<br>May 2026</i></small>
</div>
"""
m.get_root().html.add_child(folium.Element(legend_html))

# ── Title ─────────────────────────────────────────────────────────────────────
title_html = """
<div style="position:fixed;top:10px;left:50%;transform:translateX(-50%);z-index:1000;
     background:rgba(255,255,255,0.93);padding:10px 22px;border-radius:6px;
     border:1px solid #aaa;font-family:Arial,sans-serif;text-align:center;
     box-shadow:2px 2px 5px rgba(0,0,0,0.2);">
  <b style="font-size:15px;">Northeast FL — Military Installation Energy Risk Map</b><br>
  <span style="font-size:11px;color:#555;">NEFRC MIRR | NAS Jacksonville &bull; NS Mayport &bull;
  MCSF Blount Island &bull; Camp Blanding</span>
</div>
"""
m.get_root().html.add_child(folium.Element(title_html))

output_path = "energy_risk_map.html"
m.save(output_path)
print(f"Map saved → {output_path}")
