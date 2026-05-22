"""
Northeast Military Installation Energy Risk Map
Duval County / Clay County / Jacksonville, FL
Generates: energy_risk_map.html
"""

import folium
from folium.plugins import FeatureGroupSubGroup

# Center on Jacksonville metro
CENTER = [30.3322, -81.6557]

m = folium.Map(
    location=CENTER,
    zoom_start=11,
    tiles="CartoDB positron",
    control_scale=True,
)

# ── Layer groups ──────────────────────────────────────────────────────────────
installations_group  = folium.FeatureGroup(name="Military Installations", show=True)
substations_group    = folium.FeatureGroup(name="Critical Substations", show=True)
risk_group           = folium.FeatureGroup(name="High Risk / Flood Zones", show=True)
transmission_group   = folium.FeatureGroup(name="Transmission Corridors", show=True)
adaptation_group     = folium.FeatureGroup(name="Adaptation Priority Sites", show=True)

# ── Military Installations ────────────────────────────────────────────────────
installations = [
    {
        "name": "Naval Air Station Jacksonville",
        "coords": [30.2355, -81.6801],
        "county": "Duval County",
        "risk": "HIGH — adjacent to St. Johns River floodplain; aging primary feeders; "
                "shared civilian-military transmission",
        "color": "darkblue",
    },
    {
        "name": "Naval Station Mayport",
        "coords": [30.3957, -81.4228],
        "county": "Duval County (coastal)",
        "risk": "CRITICAL — Cat 4 surge zone; coastal substation exposure; "
                "limited road/grid egress during storm",
        "color": "darkred",
    },
    {
        "name": "Camp Blanding Joint Training Center",
        "coords": [29.9457, -82.0102],
        "county": "Clay / Bradford County",
        "risk": "MEDIUM-HIGH — rural distribution; long single-circuit feeders; "
                "wildland fire interface risk",
        "color": "darkblue",
    },
]

for inst in installations:
    folium.Marker(
        location=inst["coords"],
        popup=folium.Popup(
            f"<b>{inst['name']}</b><br>{inst['county']}<br><br>"
            f"<b>Energy Risk:</b> {inst['risk']}",
            max_width=320,
        ),
        tooltip=inst["name"],
        icon=folium.Icon(color=inst["color"], icon="shield", prefix="fa"),
    ).add_to(installations_group)

# ── Critical Substations ──────────────────────────────────────────────────────
substations = [
    {
        "name": "Southside Substation (JEA)",
        "coords": [30.2810, -81.6200],
        "voltage": "138 kV",
        "risk": "HIGH — primary feeder source for NAS Jacksonville; located in Zone AE flood plain",
        "color": "orange",
    },
    {
        "name": "Deer Park Substation (JEA)",
        "coords": [30.2500, -81.6600],
        "voltage": "138 kV",
        "risk": "HIGH — serves NAS Jacksonville southern sectors; aging transformer (1970s vintage)",
        "color": "orange",
    },
    {
        "name": "Mayport Switching Station (FPL)",
        "coords": [30.3900, -81.4400],
        "voltage": "69 kV",
        "risk": "CRITICAL — sole injection point for NS Mayport; within 0.5 mi of surge inundation zone",
        "color": "red",
    },
    {
        "name": "Orange Park Substation (JEA/FPL)",
        "coords": [30.1700, -81.7060],
        "voltage": "115 kV",
        "risk": "MEDIUM — primary source for Camp Blanding distribution corridor",
        "color": "beige",
    },
    {
        "name": "Buckman Substation (JEA)",
        "coords": [30.2150, -81.6930],
        "voltage": "138 kV",
        "risk": "HIGH — St. Johns River adjacent; flood exposure during major storm events",
        "color": "orange",
    },
]

for sub in substations:
    folium.CircleMarker(
        location=sub["coords"],
        radius=12,
        color=sub["color"],
        fill=True,
        fill_color=sub["color"],
        fill_opacity=0.7,
        popup=folium.Popup(
            f"<b>{sub['name']}</b><br>Voltage: {sub['voltage']}<br><br>"
            f"<b>Risk:</b> {sub['risk']}",
            max_width=300,
        ),
        tooltip=f"⚡ {sub['name']}",
    ).add_to(substations_group)

# ── Transmission Corridors (approximate polylines) ────────────────────────────
corridors = [
    {
        "name": "NAS Jacksonville Primary Feed Corridor",
        "points": [[30.2810, -81.6200], [30.2600, -81.6500], [30.2355, -81.6801]],
        "risk": "HIGH — crosses floodplain twice; shared civilian load; no military bypass",
        "color": "darkorange",
        "weight": 4,
    },
    {
        "name": "NS Mayport Coastal Transmission Line",
        "points": [[30.3600, -81.4700], [30.3800, -81.4500], [30.3957, -81.4228]],
        "risk": "CRITICAL — overhead lines exposed to 140+ mph wind; surge inundation path",
        "color": "darkred",
        "weight": 4,
    },
    {
        "name": "Camp Blanding Rural Distribution Corridor",
        "points": [[30.1700, -81.7060], [30.0500, -81.8200], [29.9457, -82.0102]],
        "risk": "MEDIUM-HIGH — 40+ mile single-circuit rural feeder; wildland fire exposure",
        "color": "orange",
        "weight": 3,
        "dash_array": "8",
    },
    {
        "name": "Jacksonville Urban Backbone (138 kV)",
        "points": [[30.3300, -81.6600], [30.2810, -81.6200], [30.2150, -81.6930]],
        "risk": "MEDIUM — urban hardening partially complete; shared civilian-military load center",
        "color": "gray",
        "weight": 3,
    },
]

for corridor in corridors:
    opts = dict(
        locations=corridor["points"],
        color=corridor["color"],
        weight=corridor.get("weight", 3),
        opacity=0.8,
        popup=folium.Popup(
            f"<b>{corridor['name']}</b><br><b>Risk:</b> {corridor['risk']}",
            max_width=300,
        ),
        tooltip=corridor["name"],
    )
    if "dash_array" in corridor:
        opts["dash_array"] = corridor["dash_array"]
    folium.PolyLine(**opts).add_to(transmission_group)

# ── High-Risk / Flood Zones (approximate polygons) ────────────────────────────
risk_zones = [
    {
        "name": "NS Mayport Storm Surge Zone (Cat 3–4)",
        "coords": [
            [30.4150, -81.4600], [30.4150, -81.3900],
            [30.3700, -81.3900], [30.3700, -81.4600],
        ],
        "risk_level": "CRITICAL",
        "color": "#FF0000",
        "description": "Cat 3–4 surge inundation area encompasses substation and primary access routes",
    },
    {
        "name": "St. Johns River Floodplain (FEMA Zone AE)",
        "coords": [
            [30.2600, -81.7100], [30.2600, -81.6300],
            [30.2100, -81.6300], [30.2100, -81.7100],
        ],
        "risk_level": "HIGH",
        "color": "#FF8C00",
        "description": "FEMA Zone AE — 1% annual chance flood; NAS Jacksonville and Buckman substation exposure",
    },
    {
        "name": "Intracoastal / Atlantic Beach Surge Zone",
        "coords": [
            [30.3400, -81.4300], [30.3400, -81.3800],
            [30.3100, -81.3800], [30.3100, -81.4300],
        ],
        "risk_level": "HIGH",
        "color": "#FF8C00",
        "description": "Coastal surge and sea level rise zone — transmission infrastructure at increasing risk through 2050",
    },
    {
        "name": "Camp Blanding Wildland-Urban Interface",
        "coords": [
            [30.0000, -82.0700], [30.0000, -81.9500],
            [29.8900, -81.9500], [29.8900, -82.0700],
        ],
        "risk_level": "MEDIUM",
        "color": "#DAA520",
        "description": "Longleaf pine / scrub habitat — transmission line fire risk corridor; dry season vulnerability",
    },
]

for zone in risk_zones:
    folium.Polygon(
        locations=zone["coords"],
        color=zone["color"],
        fill=True,
        fill_color=zone["color"],
        fill_opacity=0.18,
        weight=2,
        popup=folium.Popup(
            f"<b>{zone['name']}</b><br>"
            f"Risk Level: <b>{zone['risk_level']}</b><br><br>"
            f"{zone['description']}",
            max_width=320,
        ),
        tooltip=f"⚠ {zone['name']}",
    ).add_to(risk_group)

# ── Adaptation Priority Sites ─────────────────────────────────────────────────
adaptations = [
    {
        "name": "Priority 1: NS Mayport Microgrid + Substation Hardening",
        "coords": [30.3957, -81.4228],
        "action": "Islanding microgrid (solar+storage+diesel); relocate/elevate transformer; "
                  "flood barrier deployment at switching station",
        "timeline": "Near-term (0–3 years)",
        "color": "red",
    },
    {
        "name": "Priority 2: NAS Jacksonville Dedicated 138 kV Spur",
        "coords": [30.2355, -81.6801],
        "action": "New dedicated military transmission spur from diverse grid injection point; "
                  "decouple from civilian distribution backbone",
        "timeline": "Long-term (5–10 years); interim microgrid within 2 years",
        "color": "orange",
    },
    {
        "name": "Priority 3: Camp Blanding Solar EUL + Storage",
        "coords": [29.9457, -82.0102],
        "action": "Enhanced Use Lease utility-scale solar (~50 MW) + 4-hr battery storage; "
                  "underground feeder segments through highest fire-risk corridor",
        "timeline": "Near-to-mid-term (2–7 years)",
        "color": "green",
    },
    {
        "name": "Deer Park / Southside Substation Flood Hardening",
        "coords": [30.2500, -81.6400],
        "action": "Deployable flood barriers; transformer replacement with dry-type units; "
                  "coordination with JEA under CPA agreement",
        "timeline": "Near-term (1–3 years)",
        "color": "orange",
    },
]

for apt in adaptations:
    folium.Marker(
        location=apt["coords"],
        popup=folium.Popup(
            f"<b>{apt['name']}</b><br><br>"
            f"<b>Action:</b> {apt['action']}<br><br>"
            f"<b>Timeline:</b> {apt['timeline']}",
            max_width=340,
        ),
        tooltip=apt["name"],
        icon=folium.Icon(color=apt["color"], icon="wrench", prefix="fa"),
    ).add_to(adaptation_group)

# ── Add all groups to map ─────────────────────────────────────────────────────
for grp in [risk_group, transmission_group, substations_group, installations_group, adaptation_group]:
    grp.add_to(m)

folium.LayerControl(collapsed=False).add_to(m)

# ── Legend ────────────────────────────────────────────────────────────────────
legend_html = """
<div style="position: fixed; bottom: 30px; left: 30px; z-index: 1000;
     background: white; padding: 15px; border-radius: 8px;
     border: 2px solid #888; font-family: Arial, sans-serif; font-size: 13px;
     box-shadow: 3px 3px 6px rgba(0,0,0,0.3); max-width: 230px;">
  <b style="font-size:14px;">Energy Risk Legend</b><br><br>
  <span style="color:darkblue;">&#9632;</span> Military Installation<br>
  <span style="color:red;">&#9632;</span> CRITICAL Risk Zone / Substation<br>
  <span style="color:darkorange;">&#9632;</span> HIGH Risk Zone / Substation<br>
  <span style="color:goldenrod;">&#9632;</span> MEDIUM Risk Zone<br>
  <span style="color:darkorange;">&#9472;&#9472;</span> Transmission Corridor<br>
  <span style="color:darkred;">&#9472;&#9472;</span> Critical Coastal Feed<br>
  <span style="color:orange;">&#9132;</span> Adaptation Priority<br><br>
  <small><i>Northeast Military Installation Resilience Review<br>May 2026</i></small>
</div>
"""
m.get_root().html.add_child(folium.Element(legend_html))

# ── Title ─────────────────────────────────────────────────────────────────────
title_html = """
<div style="position: fixed; top: 10px; left: 50%; transform: translateX(-50%);
     z-index: 1000; background: rgba(255,255,255,0.92); padding: 10px 20px;
     border-radius: 6px; border: 1px solid #aaa;
     font-family: Arial, sans-serif; text-align: center;
     box-shadow: 2px 2px 5px rgba(0,0,0,0.2);">
  <b style="font-size:16px;">Northeast FL Military Installation — Energy Risk Map</b><br>
  <span style="font-size:12px; color:#555;">Duval &amp; Clay Counties | NAS Jacksonville | NS Mayport | Camp Blanding</span>
</div>
"""
m.get_root().html.add_child(folium.Element(title_html))

output_path = "energy_risk_map.html"
m.save(output_path)
print(f"Map saved to: {output_path}")
