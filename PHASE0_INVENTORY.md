# Phase 0 Inventory Summary

## DOM IDs Written By JavaScript
- gradeLetter
- gradeName
- gradeScore
- exposureText
- costVal
- costNote
- recoText
- bFlood
- tFlood
- bRain
- tRain
- bHeat
- tHeat
- bCoast
- tCoast

## Frontend JSON Contract Parsed in runAssessment/renderResult
Required keys and expected value types:
- grade: string (A|B|C|D)
- gradeLabel: string
- compositeScore: number 0-100
- flood: number 0-100
- rainfall: number 0-100
- heat: number 0-100
- coastal: number 0-100
- exposureSummary: string
- costLow: formatted currency string
- costHigh: formatted currency string
- recommendations: string

Transparency keys added in backend/template integration:
- dataSources: list of source dicts
- projectionScenario: string
- dataRetrievedAt: ISO datetime string
- dataNotes: string

## Loading Steps (s1-s6)
- s1: Acquiring geospatial coordinates
- s2: Cross-referencing flood zone data
- s3: Analysing elevation and drainage
- s4: Computing rainfall intensity index
- s5: Calculating heat and coastal exposure
- s6: Generating investment grade

## Render Logic Confirmed
- renderResult(r) populates all grade, bars, summary, cost and recommendations fields.
- setBar() applies LOW/MODERATE/HIGH labels and styles.
- animBar() animates width to percentage values.

## Disclaimer and Legal Copy
- Inline results disclaimer remains visible in result card.
- Footer disclaimer bar remains visible and unchanged.
- Added explicit acknowledgment gate before assessment call (browser confirm).
- costNote is set to "Modelled estimate" in renderResult().

## SRD Data Sources and Planned Access
- NASA SRTM: Earth Engine primary, Open-Elevation fallback
- CHIRPS v2.0 rainfall: direct CHIRPS/GEE, regionalized fallback
- JRC Global Surface Water: GEE/direct water history fallback
- ESA WorldCover: GEE/direct fallback heuristics
- OpenStreetMap Overpass: drainage/river proximity query
- OSM coastline + DEM: local GeoJSON + shapely distance
- CMIP6 projections: static state-level JSON lookup
