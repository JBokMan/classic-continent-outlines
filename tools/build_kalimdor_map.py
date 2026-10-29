#!/usr/bin/env python3
"""Builds the WoW: Forever Kalimdor outlines from Syrio's Wikimedia Commons map.

Source: https://commons.wikimedia.org/wiki/File:Kalimdor_english.svg (CC BY-SA 4.0, Syrio).
The derived geometry inherits CC BY-SA 4.0.

Usage: python3 tools/build_kalimdor_map.py path/to/Kalimdor_english.svg

Writes data/
  kalimdor_geometry.json  one polygon per zone + its label anchor
  kalimdor_land.json      the backdrop: zoneId "land" (landmass pieces) and "water" (lakes)

Method: the source reuses fill colors across zones, so a zone is the solid subpath of its fill
that contains a probe point taken from the SVG's own zone label. Parts of one zone are joined
across their seams. Holes, simplification, framing and label anchors work exactly like the
Eastern Kingdoms generator.

Forever, not retail: the source draws the Cataclysm continent, WoW: Forever (client 1.60.1) the
2004 one plus Mount Hyjal and Shen'dralas. The client's UiMap table lists exactly the 18 classic
zones and those two on this continent (Zephras Isle, the Skyborne start zone, floats in Skywall
on its own map, Darkspear Islands is a battleground); Blizzard's Forever continent and zone maps
(warcraft.wiki.gg, "Forever map comparison") show where they sit:
- The Barrens is the classic single zone: the source's Northern and Southern Barrens joined.
- Thousand Needles is not flooded: the source keeps only the mesas that stuck out of Cataclysm's
  water. They are bridged into one zone, and THOUSAND_NEEDLES (hand-placed from Forever's zone
  map) adds the canyon floor and the Shimmering Flats back, as zone and as land; the neighbours
  keep their ground.
- Mount Hyjal (60) is a zone again, smaller than Cataclysm's: Forever's zone map holds the
  Summit of Eternity down to the Tainted Foothills and Felblood Scar. HYJAL clips the source's
  Hyjal to that hand-placed outline; the rest stays land without a zone.
- Shen'dralas is new, where Cataclysm put Lake Dumont: between Desolace (Valley of Bones),
  Mulgore and Feralas. No CC map draws it, so SHENDRALAS is a coarse hand-placed outline of the
  valley Forever's zone map shows (Evenshade's Overlook, Magram Front, Outcast Hideaway, Forlorn
  Gardens, the Shen'dralas ruins); Desolace, Feralas and Mulgore give it that ground and Lake
  Dumont (a Cataclysm lake) goes.
- Mulgore gains the Skywatcher Plateau, Forever's new arrival point for Horde Skyborne on its
  north-west rim (SKYWATCHER, hand-placed from Forever's Mulgore map).
- Removed: Azuremyst and Bloodmyst Isle (Burning Crusade), zone and land, which Forever's
  continent map does not draw. Uldum and Ahn'Qiraj: The Fallen Kingdom (Cataclysm) have no
  zone; Forever paints that desert south of Silithus and Un'Goro as unexplored land, so it stays
  land without a zone (without Uldum's Cataclysm lakes).
Hand-placed outlines are coarse artboard polygons set by eye against Blizzard's Forever maps,
registered onto the artboard through the client's zone-map rectangles (UiMapAssignment) and the
coastline; no Blizzard pixels are traced.
"""
import json
import pathlib
import sys

from shapely.geometry import Polygon
from shapely.ops import unary_union

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

# zone id -> parts as (fill, probe point inside that part, in artboard units). Probe points sit
# on the SVG's own label for the zone (or inside the body where the label is rotated/offset).
ZONE_PARTS = {
    "durotar": [("#FFF200", (360, 322))],
    "mulgore": [("#F79226", (238, 420))],
    "teldrassil": [("#00AEEF", (193, 48))],
    "darkshore": [("#57BF93", (255, 133))],
    "the-barrens": [("#FDB714", (305, 335)), ("#B36928", (288, 414))],
    "stonetalon-mountains": [("#B47565", (203, 300))],
    "ashenvale": [("#87BC40", (265, 264))],
    "thousand-needles": [("#F175AD", (301, 506)), ("#F175AD", (344, 493))],
    "desolace": [("#E27423", (170, 378))],
    "dustwallow-marsh": [("#C8A760", (330, 451))],
    "feralas": [("#C161A5", (195, 462))],
    "tanaris": [("#737A9D", (327, 577))],
    "azshara": [("#62BD5E", (388, 244))],
    "felwood": [("#759341", (259, 185))],
    "un-goro-crater": [("#817FBC", (268, 545))],
    "silithus": [("#A05DA5", (198, 543))],
    "winterspring": [("#B6D98B", (353, 140))],
    "moonglade": [("#81D4F7", (307, 110))],
    "mount-hyjal": [("#00A750", (313, 190))],
}
# Azuremyst Isle with its islet, Bloodmyst Isle with its islet: not on Forever's map.
DROPPED_LAND = [("#0081B2", (87, 167)), ("#0081B2", (42, 196)), ("#81D4F7", (55, 106)), ("#81D4F7", (84, 84))]
ULDUM = "#7D5AA6"
ART_W, ART_H = 481.89, 680.315
FRAME = max(ART_W, ART_H)
OFFSET_X = (FRAME - ART_W) / 2
# Closes the hairline seams between merged parts without changing their outline; zones whose
# parts are separated by real channels get a wider bridge.
SEAM = 0.8
BRIDGE = {"thousand-needles": 6.0}

# Hand-placed polygons in artboard units (see the module docstring).
HYJAL = [
    (326, 172), (336, 173), (347, 182), (337, 193), (344, 209), (331, 216), (316, 218),
    (302, 220), (289, 214), (275, 210), (266, 193), (269, 186), (286, 185), (296, 180),
    (313, 176),
]  # fmt: skip
SHENDRALAS = [
    (196, 395.5), (210, 395.5), (216.5, 398.5), (219.5, 405), (221.5, 411), (222.5, 417),
    (222.5, 423), (219.5, 427.5), (210, 429), (200, 429.5), (191, 428), (187, 421),
    (187.5, 414), (188, 406), (191, 399),
]  # fmt: skip
SKYWATCHER = [(208, 364), (208, 346), (212, 337), (219, 333.5), (226, 336), (229, 343), (229, 352), (222, 358), (216, 366)]
# The classic canyon floor and the Shimmering Flats, which Cataclysm flooded; the source keeps only
# the mesas that stuck out of the water.
THOUSAND_NEEDLES = [
    (250, 460), (259, 459.5), (268.5, 465), (281, 469.5), (293, 479.5), (308, 485), (320, 489.5),
    (332.5, 493.5), (345, 492), (353.5, 499.5), (355, 513), (351, 524.5), (337.5, 529.5),
    (325, 525), (326.5, 508.5), (311.5, 502), (295.5, 502), (281, 495), (265, 486), (255, 485),
    (253.5, 477), (249, 464.5),
]  # fmt: skip
TN_NEIGHBOURS = ("the-barrens", "feralas", "dustwallow-marsh", "tanaris", "un-goro-crater", "mulgore")


def part_body(solids, fill, probe):
    containing = [s for s in solids.get(fill.upper(), []) if inside(s, *probe)]
    if not containing:
        raise SystemExit(f"no {fill} subpath contains {probe}")
    return min(containing, key=area)


def forever_zones(solids):
    """Zone id -> shapely shape of the zone as WoW: Forever draws it."""
    zones = {
        zone_id: joined([shape(part_body(solids, fill, probe)) for fill, probe in parts], BRIDGE.get(zone_id, SEAM))
        for zone_id, parts in ZONE_PARTS.items()
    }
    zones["mount-hyjal"] = zones["mount-hyjal"].intersection(Polygon(HYJAL))
    skywatcher, shendralas = Polygon(SKYWATCHER), Polygon(SHENDRALAS)
    for zone_id in ("desolace", "stonetalon-mountains", "the-barrens"):
        zones[zone_id] = zones[zone_id].difference(skywatcher)
    zones["mulgore"] = joined([zones["mulgore"], skywatcher], SEAM)
    for zone_id in ("desolace", "feralas", "mulgore"):
        zones[zone_id] = zones[zone_id].difference(shendralas)
    zones["shendralas"] = shendralas
    neighbours = unary_union([zones[zone_id] for zone_id in TN_NEIGHBOURS])
    zones["thousand-needles"] = joined([zones["thousand-needles"], Polygon(THOUSAND_NEEDLES)], SEAM).difference(
        neighbours
    )
    return zones


def main(svg_path):
    solids, holes = solids_and_holes(read_fills(pathlib.Path(svg_path).read_text()))
    dropped = [part_body(solids, fill, probe) for fill, probe in DROPPED_LAND]

    lakes = [
        h
        for fill, subs in holes.items()
        if fill != ULDUM
        for h in subs
        if area(h) >= 12 and not inside(SHENDRALAS, *centroid(h))
    ]
    zones = []
    shapes = forever_zones(solids)
    for zone_id, geom in shapes.items():
        body = outline(geom, zone_id)
        anchor = label_anchor(body, [lake for lake in lakes if inside(body, *centroid(lake))])
        zones.append(
            {
                "zoneId": zone_id,
                "points": normalized(simplify(body, 0.3), FRAME, OFFSET_X),
                "label": {"x": round((anchor[0] + OFFSET_X) / FRAME, 4), "y": round(anchor[1] / FRAME, 4)},
            }
        )

    land = [s for subs in solids.values() for s in subs if area(s) >= 30 and not any(s is d for d in dropped)]
    land.append(outline(shapes["thousand-needles"], "thousand-needles"))
    backdrop = [{"zoneId": "land", "points": normalized(simplify(s, 0.4), FRAME, OFFSET_X)} for s in land]
    backdrop += [{"zoneId": "water", "points": normalized(simplify(h, 0.3), FRAME, OFFSET_X)} for h in lakes]

    (OUT / "kalimdor_geometry.json").write_text(json.dumps(zones, indent=2) + "\n")
    (OUT / "kalimdor_land.json").write_text(json.dumps(backdrop, separators=(",", ":")) + "\n")
    print(f"zones={len(zones)} land={len(land)} water={len(lakes)}")


if __name__ == "__main__":
    main(sys.argv[1])
