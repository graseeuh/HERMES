# Methodology for Geospatial Evaluation of Energy Reliability
## Northeast Florida Military Installation Resilience Review (NEFRC MIRR)
**Naval Air Station Jacksonville | Naval Station Mayport | MCSF Blount Island | Camp Blanding JTF**

---

## 1. Overview

This methodology provides a reproducible framework for evaluating energy reliability at and around the four NEFRC MIRR installations in Duval and Clay Counties. It is grounded in the MIRR's confirmed vulnerability assessment approach and extends it with energy-specific datasets and analysis steps. The framework follows the MIRR's two-step structure: (1) assess asset vulnerability to hazards, and (2) calculate risk to mission using vulnerability × likelihood × consequence.

---

## 2. Analytical Framework

The MIRR uses the following definitions, which this methodology adopts directly:

- **Vulnerability** = Exposure × Sensitivity (scale 1–5: Low to High)
- **Risk to Mission** = Vulnerability × Likelihood × Consequence of asset failure (Low / Moderate / High)
- **Level of Urgency**: Immediate (0–5 yr, 2026–2030), Near-Term (5–10 yr, 2030–2035), Mid-Term (10–25 yr, 2035–2050), Long-Term (25+ yr, 2050+)
- **Mission Lens**: Primary mission-critical → Secondary mission-critical → Mission-supportive → Additional vulnerabilities

Energy production and supply facilities are classified as **Primary Mission-Critical Assets** for all four installations per the MIRR vulnerability assessment.

---

## 3. Datasets

### 3.1 Hazard Datasets (Confirmed by MIRR Vulnerability Assessment)

| Hazard | Scenario | Dataset | Source |
|---|---|---|---|
| Rainfall Flooding | Present-day 100-yr, 2040, 2070 | CDBG Flood Model | NEFRC / Resilient Jax |
| Storm Surge | Category 3, Category 5 | NHC SLOSH Model | NOAA NHC + Resilient Jax |
| Sea Level Rise | 2022 NOAA SLR Projections | SLR Scenarios | NOAA / Resilient Jax |
| Compound Flooding | Future 1% AEP flood in 2070 | Compound Flood Model | Resilient Jax |
| High Wind | Qualitative (hurricane, thunderstorm, nor'easter) | NWS Jacksonville wind event database | NOAA NWS |
| Wildfire | Wildfire hazard footprint | USDA Forest Service Research Data | USDA FS |
| Extreme Heat | Heat Severity 2024 | Heat Severity Dataset | Trust for Public Land |
| Transportation Interruption | Network disruption scenarios | NERPM 2020 Loaded Networks | North Florida MPO |
| Flood Hazard Zones | 1% AEP (Zone AE/VE) | National Flood Hazard Layer (NFHL) | FEMA |
| Hydrology / Elevation | Terrain, drainage | National Map / 3DEP LiDAR | USGS |
| Erosion / Shoreline Change | Historical and projected | FDEP shoreline data, USACE, SJRWMD, NOAA | FDEP / USACE |

### 3.2 Energy Infrastructure Datasets

| Dataset | Source | Notes |
|---|---|---|
| Electric Power Transmission Lines | EIA / HIFLD Open | Voltage class, ownership; includes JEA and FPL lines |
| Electric Substations | EIA Form 860 / HIFLD | Name, voltage, county — basis for SPOF mapping |
| Power Plants (generation) | EIA Form 860 | Fuel type, capacity, age |
| Utility Service Territory Boundaries | EIA / Florida PSC | JEA, FPL, Seminole Electric, Clay Electric, TECO |
| Natural Gas Inter/Intrastate Pipelines | OpenEnergyDataPortal (ORNL) | TECO supply to NAS JAX — primary gas dependency |
| Existing Hydropower Assets | HydroSource / ORNL (EHA 2022) | Regional generation inventory |
| State Energy Infrastructure Data | EIA State Data Portal | Florida-specific generation and transmission |
| Open Energy Data Portal | OpenEnergyHub (ORNL) | Aggregated energy infrastructure layers |
| Esri Federal Energy Datasets | ArcGIS Federal Content Group | Composite federal energy infrastructure layers |
| National Laboratory of the Rockies GIS | NLR GIS Portal | Supplemental energy mapping resources |
| Distributed Solar + Storage | SEIA / NREL OpenPV | On-installation renewable assets (partial coverage) |

### 3.3 Military Installation and Community Datasets

| Dataset | Source | Notes |
|---|---|---|
| Military Installation Boundaries | HIFLD Open | All 4 confirmed installations + OLF Whitehouse |
| Critical Facilities | HIFLD / Duval and Clay County GIS | Hospitals, EOCs, fire stations |
| Road Network | FDOT / OpenStreetMap | Restoration access route analysis |
| Census TIGER Boundaries | US Census Bureau | Duval, Clay, Bradford Counties |
| SJRWMD Water Resources Data | St. Johns River WMD | Water supply / water system interdependencies |
| High Plains Regional Climate Center | NOAA / Univ. of Nebraska | Regional climate trends and projections |
| NOAA Sea Level Rise Viewer | NOAA Digital Coast | SLR inundation visualization (0.5m–2.5m) |

---

## 4. Analytical Steps

### Step 1 — Energy Infrastructure Inventory and Topology Mapping
Compile all transmission lines, substations, and utility service territories within a defined study area buffer around each installation (boundaries established through the MIRR stakeholder process). Build a network topology identifying: (a) the single substation supplying each installation, (b) the transmission segments connecting each substation to the regional grid, and (c) any existing backup or alternative supply paths (currently confirmed as none at all four installations).

### Step 2 — Hazard Exposure Analysis
Intersect each energy infrastructure element with the confirmed MIRR hazard layers:
- Storm surge (Cat 3, Cat 5 SLOSH) — primary concern for NS Mayport and MCSF Blount Island substations
- Rainfall flooding (100-yr present, 2040, 2070 CDBG scenarios) — NAS JAX and NS Mayport
- SLR scenarios (NOAA 2022 projections) — coastal substations
- Wildfire hazard (USDA FS) — Camp Blanding FPL substation and transmission corridor
- High wind (NWS qualitative) — all installations; NAS JAX recorded 106 mph gust in 1997

Output: per-element hazard exposure rating (Low through High) consistent with MIRR VA scale.

### Step 3 — Sensitivity Analysis
Score each energy asset on sensitivity factors:
- Asset age (EIA Form 860 install year as proxy)
- Redundancy (number of alternate supply paths — all four installations currently score zero)
- Asset type vulnerability (overhead vs. underground, transformer type, substation elevation)
- Proximity to known hazard exposure (surge zone, flood zone, WUI)

### Step 4 — Risk-to-Mission Calculation
Apply the MIRR's mission lens: electric production and supply facilities are Primary Mission-Critical at all four installations. Combine exposure and sensitivity to produce vulnerability score, then apply likelihood and consequence weights to calculate risk-to-mission designation (Low/Moderate/High) and urgency tier (Immediate through Long-Term). Cross-check results against the confirmed MIRR VA table:

| Installation | Substation | Risk to Mission | Urgency |
|---|---|---|---|
| NS Mayport | JEA Mayport Substation (south of base) | **High** | **Immediate** |
| MCSF Blount Island | JEA Substation | Medium | **Immediate** |
| NAS Jacksonville | JEA Substation (north of base) | Medium | **Immediate** |
| Camp Blanding | FPL Substation (north of base) | **High** | Near-Term |

### Step 5 — Adaptation Strategy Development
Using the MIRR 8-step approach: organize strategies around confirmed SPOFs → identify current efforts (JEA grid hardening, P035 generators at Blount Island, microgrid feasibility at NAS JAX) → build comprehensive projects across RRAP goals (Physical Infrastructure, Natural Resources, Public Health, Economic Policies) → layer coordination across the fenceline (IGSA expansion, FPL coordination) → score on feasibility and risk mitigation metrics → develop timeline and funding toolkit (ERCIP, ESPC, UESC, MILCON, ESTCP).

### Step 6 — Scenario Analysis
Run two minimum scenarios:
- **Baseline**: Current climate + current grid configuration (single substations, O&M-only IGSAs)
- **2070 Climate**: NOAA SLR + NEFRC compound flood 2070 scenario + projected hurricane intensification, with planned resilience investments in place

Compare risk scores to quantify the value of near-term vs. long-term adaptation investments.

---

## 5. Geospatial Data Gaps

### Critical Gaps (block or severely limit analysis if unresolved)

| Gap | Description | Status from MIRR TAC | Workaround |
|---|---|---|---|
| **JEA utility infrastructure data** | Exact substation locations, condition ratings, planned hardening investments | Follow-up meetings still being scheduled as of Sept 2025 TAC | Use EIA Form 860 and HIFLD as proxy; flag for JEA coordination under expanded IGSA |
| **NS Mayport detailed energy data** | On-installation distribution layout, backup capacity, fuel storage | Data request pending as of Sept 2025 | Coordinate through NAVFAC Southeast; use MIRR site visit notes as qualitative input |
| **Camp Blanding energy data** | On-installation distribution, FPL interface details | Data request submitted but unresolved | FPL coordination recommended in R-2; use EIA Form 860 for FPL substation proxy |
| **CCUA (Clay County Utility Authority)** | Water/utility service data relevant to Camp Blanding resilience | Follow-up discussions pending | Coordinate through Clay County Planning staff engaged in MIRR TAC |
| **On-installation asset data** | Generator inventory, fuel storage, distribution panel layout | Not public; requires NAVFAC/installation DPW coordination | P035 project data available for Blount Island; request IEPs from other installations |

### Significant Gaps (degrade analysis quality)

| Gap | Description | Workaround |
|---|---|---|
| **TECO natural gas routing** | NAS JAX depends on TECO privatized natural gas system; routing not in public datasets | TECO coordination; flag as qualitative risk only |
| **FPL substation condition** | FPL substation north of Camp Blanding — age, condition, hardening plan | FPSC Storm Hardening reporting (R-2 recommendation) — annual filings contain hardening investments |
| **Seminole Electric data** | Camp Blanding's multi-provider arrangement includes Seminole Electric; territory and infrastructure not in public layers | Seminole Electric direct outreach |
| **Underground cable locations** | JEA underground distribution routing in urban areas not in HIFLD | Utility coordination; assume overhead in absence of data |
| **Real-time outage data** | No public feed of real-time grid status during events | Post-event EIA-417 outage reports (submitted by utilities after significant events) |
| **Wind hazard quantitative layer** | NWS data was used qualitatively in MIRR VA; no quantitative wind hazard raster was applied | HAZUS-MH wind fragility curves for transmission structures; ASCE 7 wind maps |

### Methodological Gaps

- **Cascading failure modeling**: The MIRR VA identifies SPOFs but does not model cascade effects (e.g., substation loss → SCADA failure → water pumping failure → mission degradation). A system-of-systems model would be needed for full interdependency analysis.
- **Demand-side uncertainty**: Future energy demand at installations (EV fleet electrification, increased cooling load under higher temperatures, new mission sets) is not captured in current utility planning data.
- **Multi-provider coordination modeling**: Camp Blanding's four-provider arrangement creates coordination complexity that standard network topology analysis does not capture — requires stakeholder-level process mapping.

---

## 6. Recommended Next Steps to Close Critical Gaps

1. Expand JEA IGSAs to include data-sharing provisions for resilience planning (MIRR Regional Recommendation R-2)
2. Request Installation Energy Plans (IEPs) from NAVFAC Southeast for NAS JAX and NS Mayport
3. Engage FPSC annual Storm Hardening filings to obtain FPL's planned investments along Camp Blanding's supply corridor
4. Establish data-sharing MOU with CCUA and Seminole Electric through MIRR TAC coordination structure
5. Commission quantitative wind fragility analysis for transmission lines serving NS Mayport and MCSF Blount Island

---

*Sources: NEFRC MIRR Vulnerability Assessment Methodology (Jan 2026 SC; Sept 2025 TAC); MIRR Data Gaps Summary (Sept 2025 TAC); Nov 2025 TAC Hazard Data Sources Table; MIRR Adaptation Planning Framework (April 2026 SC); Prior intern geospatial dataset inventory (May 2026)*
