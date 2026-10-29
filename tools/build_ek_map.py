#!/usr/bin/env python3
"""Builds the WoW: Forever Eastern Kingdoms outlines from Syrio's Wikimedia Commons map.

Source: https://commons.wikimedia.org/wiki/File:Eastern_Kingdoms.svg (CC BY-SA 4.0, Syrio).
The derived geometry inherits CC BY-SA 4.0.

Usage: python3 tools/build_ek_map.py path/to/Eastern_Kingdoms.svg

Writes data/
  eastern_kingdoms_geometry.json  one polygon per zone + its label anchor
  eastern_kingdoms_land.json      the backdrop: zoneId "land" (landmass pieces, drawn under the
                                  zones) and zoneId "water" (lakes, drawn over land and zones)

Method: a zone is one fill color of the source (verified against the SVG's own labels: Karazhan
marks Deadwind, the Dark Portal Blasted Lands, Zul'Gurub Northern Stranglethorn); its body is the
largest subpath of that fill unless a probe point picks the part. Subpaths whose centroid lies
inside a larger subpath of the same fill are holes (lakes). Parts of one zone are joined across
their hairline seams (Stranglethorn's coastal strip, the Western Plaguelands' strip south of
Darrowmere Lake, Hillsbrad's Durnholde part). Cubic segments are sampled, outlines simplified
(Douglas-Peucker), the 595x1049 artboard is centered in a square 0..1 frame (y southward). Label
anchor: the area centroid when it sits well inside the zone, else the pole of inaccessibility.

Forever, not retail: the source draws the Cataclysm continent, WoW: Forever (client 1.60.1) the
2004 one plus the Riverglades. The client's UiMap table lists exactly the 22 classic zones and
the Riverglades on this continent; Blizzard's Forever continent and zone maps (warcraft.wiki.gg,
"Forever map comparison") show where they sit. The generator turns the source into that state:
- Stranglethorn Vale is one zone again: Northern Stranglethorn and the Cape joined (Jaguero Isle
  stays an island).
- Alterac Mountains is its own zone again; the source merges it into Hillsbrad Foothills.
  ALTERAC_SIDE carries the hand-placed border along the foothills' edge: Dalaran, the Ruins of
  Alterac and Strahnbrad stay north, Hillsbrad Fields, Tarren Mill and Durnholde south.
- The Wetlands reach east over Grim Batol again (Cataclysm gave it to the Twilight Highlands):
  the Twilight Highlands' land inside GRIM_BATOL joins them.
- The Riverglades are new: the east coast south of the Badlands and east of the Burning Steppes
  and Redridge. No CC map draws them, so RIVERGLADES is a coarse hand-placed outline: west edge
  between the neighbours' rims and the zone's own sites (Twilight's Shroud, Bolder'ok, Wheeler's
  Grange), coast and bay as Forever's zone map draws them. The Badlands, Burning Steppes and
  Redridge give their Cataclysm-era eastern strips to it.
- Land: Ghostlands, Eversong, Sunstrider Isle and the Isle of Quel'Danas are Burning Crusade
  zones. Forever paints only the southern edge of Quel'Thalas, as unexplored land at the top of
  its map: the Ghostlands piece stays as land without a zone, the rest is dropped. The Twilight
  Highlands (Cataclysm) keep only the land inside Forever's coast (TWILIGHT_COAST), without a
  zone. Tol Barad and Kul Tiras are not on Forever's map; Gilneas is, as land without a zone.
  The ridge between Dun Morogh and Elwynn, which the source leaves blank because it draws zones
  only, is land (DUN_MOROGH_RIDGE), as Forever paints it.
- Water: Loch Modan's loch is back at its pre-Cataclysm size (LOCH replaces the drained
  remnant); the Twilight Highlands' lakes go with that zone.
Hand-placed outlines are coarse artboard polygons set by eye against Blizzard's Forever maps,
registered onto the artboard through the client's zone-map rectangles (UiMapAssignment) and the
coastline; no Blizzard pixels are traced.
"""
import json
import pathlib
import sys

from shapely.geometry import Polygon

from svgmap import (
    area,
    centroid,
    inside,
    joined,
    label_anchor,
    normalized,
    outline,
    read_fills,
    shape,
    simplify,
    solids_and_holes,
)

REPO = pathlib.Path(__file__).resolve().parents[1]
OUT = REPO / "data"

# zone id -> fill of the source; the zone is that fill's largest subpath.
ZONE_FILL = {
    "elwynn-forest": "#CC7B16",
    "dun-morogh": "#A3CF62",
    "tirisfal-glades": "#7E499D",
    "westfall": "#FFF200",
    "loch-modan": "#50B848",
    "redridge-mountains": "#F7941E",
    "duskwood": "#A3620A",
    "wetlands": "#00A76D",
    "hinterlands": "#A587BE",
    "western-plaguelands": "#5582B0",
    "eastern-plaguelands": "#7E92B7",
    "burning-steppes": "#A84821",
    "deadwind-pass": "#BA4D16",
    "swamp-of-sorrows": "#BB8A32",
    "blasted-lands": "#F26522",
    "silverpine-forest": "#B72467",
    "arathi-highlands": "#A767AA",
    "badlands": "#408742",
    "searing-gorge": "#6FA143",
}
NORTHERN_STRANGLETHORN, CAPE_OF_STRANGLETHORN = "#FDB714", "#FFF579"
STRANGLETHORN_WEST = (265, 915)  # Northern Stranglethorn's coastal part, apart from its body
HILLSBRAD = "#F05A94"  # Hillsbrad Foothills with Alterac Mountains merged in
DURNHOLDE = (332, 466)  # Hillsbrad's Durnholde Keep part, cut off from the body by a river
WESTERN_PLAGUELANDS_SOUTH = (344, 401)  # the Plaguelands' strip south of Darrowmere Lake
TWILIGHT_HIGHLANDS = "#007F49"
# Eversong Woods with Sunstrider Isle, the Isle of Quel'Danas, Tol Barad, Kul Tiras.
DROPPED_LAND = {"#00AEEF", "#7ED3F7", "#EC008C", "#B10342"}
ART_W, ART_H = 595.276, 1048.82
FRAME = max(ART_W, ART_H)
OFFSET_X = (FRAME - ART_W) / 2
SEAM = 0.8

# Hand-placed polygons in artboard units (see the module docstring).
ALTERAC_SIDE = [
    (236, 470), (250, 461), (257, 456), (266, 450), (278, 447), (290, 446.5), (300, 446),
    (307, 441), (311, 434), (316, 433), (322, 434.5), (329, 433), (338, 424), (350, 415),
    (372, 405), (372, 370), (236, 370),
]  # fmt: skip
GRIM_BATOL = [(405, 552), (436, 551), (447, 558), (453, 574), (453, 598), (447, 614), (432, 621), (405, 621)]
# The ridge between Dun Morogh and Elwynn; the source draws zones only and leaves it blank (sea).
DUN_MOROGH_RIDGE = [(214, 716), (232, 712), (296, 712), (300, 742), (240, 746), (219, 748)]
RIVERGLADES = [
    (456, 702), (470, 702), (483, 704), (493, 709), (510, 721), (525, 735), (529, 751),
    (514, 760), (506, 774), (495, 784), (483, 800), (466, 813), (443, 819), (436, 815),
    (428, 804), (418, 795), (406, 780), (403, 768), (402, 752), (406, 742), (418, 735),
    (430, 729), (445, 727), (455, 725), (456, 712),
]  # fmt: skip
TWILIGHT_COAST = [
    (410, 512), (454, 516), (450, 537), (458, 555), (462, 574), (472, 593), (484, 611),
    (495, 630), (490, 649), (482, 668), (470, 682), (440, 690), (410, 690),
]  # fmt: skip
LOCH = [
    (412.3, 630.6), (419.9, 631.3), (424.2, 640.1), (428.6, 651.1), (427.5, 660.6),
    (422.1, 667.9), (415.6, 670.1), (411.2, 666.5), (406.9, 657.0), (405.8, 646.0),
    (406.9, 635.0),
]  # fmt: skip


def part(solids, fill, probe=None):
    """The fill's subpath containing `probe`, or its largest subpath."""
    if probe is None:
        return max(solids[fill], key=area)
    containing = [s for s in solids[fill] if inside(s, *probe)]
    if not containing:
        raise SystemExit(f"no {fill} subpath contains {probe}")
    return min(containing, key=area)


def forever_zones(solids):
    """Zone id -> shapely shape of the zone as WoW: Forever draws it."""
    zones = {zone_id: shape(part(solids, fill)) for zone_id, fill in ZONE_FILL.items()}
    zones["stranglethorn-vale"] = joined(
        [
            shape(part(solids, NORTHERN_STRANGLETHORN)),
            shape(part(solids, NORTHERN_STRANGLETHORN, STRANGLETHORN_WEST)),
            shape(part(solids, CAPE_OF_STRANGLETHORN)),
        ],
        SEAM,
    )
    zones["western-plaguelands"] = joined(
        [zones["western-plaguelands"], shape(part(solids, ZONE_FILL["western-plaguelands"], WESTERN_PLAGUELANDS_SOUTH))],
        SEAM,
    )
    hillsbrad, alterac = shape(part(solids, HILLSBRAD)), Polygon(ALTERAC_SIDE)
    zones["alterac-mountains"] = hillsbrad.intersection(alterac)
    zones["hillsbrad-foothills"] = joined(
        [hillsbrad.difference(alterac), shape(part(solids, HILLSBRAD, DURNHOLDE))], SEAM
    )
    twilight = shape(part(solids, TWILIGHT_HIGHLANDS))
    zones["wetlands"] = joined([zones["wetlands"], twilight.intersection(Polygon(GRIM_BATOL))], SEAM)
    riverglades = Polygon(RIVERGLADES)
    for zone_id in ("badlands", "burning-steppes", "redridge-mountains"):
        zones[zone_id] = zones[zone_id].difference(riverglades)
    zones["riverglades"] = riverglades
    return zones


def main(svg_path):
    solids, holes = solids_and_holes(read_fills(pathlib.Path(svg_path).read_text()))

    lakes = [LOCH] + [
        h
        for fill, subs in holes.items()
        if fill not in DROPPED_LAND | {TWILIGHT_HIGHLANDS, ZONE_FILL["loch-modan"]}
        for h in subs
        if area(h) >= 15
    ]
    zones = []
    for zone_id, geom in forever_zones(solids).items():
        body = outline(geom, zone_id)
        anchor = label_anchor(body, [lake for lake in lakes if inside(body, *centroid(lake))])
        zones.append(
            {
                "zoneId": zone_id,
                "points": normalized(simplify(body, 0.35), FRAME, OFFSET_X),
                "label": {"x": round((anchor[0] + OFFSET_X) / FRAME, 4), "y": round(anchor[1] / FRAME, 4)},
            }
        )

    land = [s for fill, subs in solids.items() if fill not in DROPPED_LAND | {TWILIGHT_HIGHLANDS} for s in subs]
    twilight = shape(part(solids, TWILIGHT_HIGHLANDS)).intersection(Polygon(TWILIGHT_COAST))
    land += [list(g.exterior.coords)[:-1] for g in getattr(twilight, "geoms", [twilight])]
    land += [RIVERGLADES, DUN_MOROGH_RIDGE]
    backdrop = [
        {"zoneId": "land", "points": normalized(simplify(s, 0.45), FRAME, OFFSET_X)} for s in land if area(s) >= 40
    ]
    backdrop += [{"zoneId": "water", "points": normalized(simplify(h, 0.35), FRAME, OFFSET_X)} for h in lakes]

    (OUT / "eastern_kingdoms_geometry.json").write_text(json.dumps(zones, indent=2) + "\n")
    (OUT / "eastern_kingdoms_land.json").write_text(json.dumps(backdrop, separators=(",", ":")) + "\n")
    print(f"zones={len(zones)} land={len(backdrop) - len(lakes)} water={len(lakes)}")


if __name__ == "__main__":
    main(sys.argv[1])
