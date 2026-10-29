# classic-continent-outlines

Vector outlines of the zones, coastlines and lakes of the two classic continents of World of
Warcraft, the Eastern Kingdoms and Kalimdor, in the shape WoW: Forever (client 1.60.1) shows
them: the 2004 continents plus the zones Forever adds.

The geometry is an adaptation of two maps by Syrio on Wikimedia Commons. It is published here
under the same license, CC BY-SA 4.0, as the license requires for adapted material.

## Contents

| Path | What |
|---|---|
| `data/eastern_kingdoms_geometry.json` | One polygon per zone (23 zones) plus a label anchor |
| `data/eastern_kingdoms_land.json` | Backdrop: landmass pieces (`zoneId: "land"`) and lakes (`zoneId: "water"`) |
| `data/kalimdor_geometry.json` | One polygon per zone (20 zones) plus a label anchor |
| `data/kalimdor_land.json` | Backdrop: landmass pieces and lakes, as above |
| `tools/build_ek_map.py` | Generates the two Eastern Kingdoms files from the source SVG |
| `tools/build_kalimdor_map.py` | Generates the two Kalimdor files from the source SVG |
| `tools/svgmap.py` | Shared SVG parsing and polygon helpers |

### Format

Every file is a JSON array of entries `{"zoneId": ..., "points": [{"x": ..., "y": ...}, ...]}`.
Zone entries also carry `"label": {"x": ..., "y": ...}`, a point well inside the zone for its
name. Coordinates lie in a square frame from 0 to 1, y pointing south; the source artboard is
centered horizontally in that frame. Rings are closed (the last point repeats the first). In the
land files, `land` pieces are drawn below the zones and `water` pieces above land and zones.

## Source

- [File:Eastern_Kingdoms.svg](https://commons.wikimedia.org/wiki/File:Eastern_Kingdoms.svg),
  by [Syrio](https://commons.wikimedia.org/wiki/User:Syrio), own work, 2020-04-13,
  [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)
- [File:Kalimdor_english.svg](https://commons.wikimedia.org/wiki/File:Kalimdor_english.svg),
  by [Syrio](https://commons.wikimedia.org/wiki/User:Syrio), own work, 2020-04-13,
  [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)

The data in this repository was generated from these revisions (SHA-1 as listed on Commons):

| File | Revision | SHA-1 |
|---|---|---|
| Eastern_Kingdoms.svg | 2020-04-13T17:55:55Z | `3e9633e7164ff02f19da85d0ad7c9baa1e5e25cd` |
| Kalimdor_english.svg | 2020-04-13T11:07:22Z | `cb08e9f96ba1426590e701ef7ea285503718dc50` |

## Changes made to the source

The source maps show the continents after Cataclysm. The generators turn them into outlines of
the continents as WoW: Forever shows them. All changes are in the scripts under `tools/`; their
module docstrings describe each one in detail.

Both continents:

- Only the filled zone shapes are used. Text, labels, icons, borders and styling are dropped.
- Each zone is extracted as one polygon from its fill color (Kalimdor: from its fill color plus a
  probe point on the zone's own label, because the source reuses colors). Inner subpaths of a fill
  become lakes.
- Parts of one zone are joined across hairline seams into a single outline.
- Bézier curves are sampled into straight segments and every outline is simplified
  (Douglas-Peucker).
- Coordinates are rescaled from the artboard into a square 0..1 frame, and a label anchor is
  computed per zone (area centroid, or the pole of inaccessibility when the centroid sits too
  close to a border or lake).
- Small land pieces and lakes below an area threshold are dropped.

Eastern Kingdoms:

- Northern Stranglethorn and the Cape of Stranglethorn are merged into Stranglethorn Vale.
- Alterac Mountains is cut out of Hillsbrad Foothills along a hand-placed border.
- The Wetlands regain Grim Batol from the Twilight Highlands.
- The Riverglades are added as a coarse hand-placed outline; the Badlands, Burning Steppes and
  Redridge Mountains give up their eastern strips to it.
- Eversong Woods, Sunstrider Isle, the Isle of Quel'Danas, Tol Barad and Kul Tiras are removed.
  The Ghostlands, Gilneas and part of the Twilight Highlands remain as land without a zone.
- The ridge between Dun Morogh and Elwynn Forest is added as land.
- Loch Modan's loch is restored to its pre-Cataclysm size; the Twilight Highlands' lakes are
  removed.

Kalimdor:

- Northern and Southern Barrens are merged into The Barrens.
- Thousand Needles is restored as an unflooded zone: the source's mesas are bridged and a
  hand-placed outline adds the canyon floor and the Shimmering Flats.
- Mount Hyjal is clipped to a smaller hand-placed outline; the rest stays land without a zone.
- Shen'dralas is added as a hand-placed outline between Desolace, Mulgore and Feralas, which give
  up that ground; Lake Dumont is removed.
- Mulgore gains the Skywatcher Plateau (hand-placed).
- Azuremyst Isle and Bloodmyst Isle are removed. Uldum and Ahn'Qiraj: The Fallen Kingdom remain as
  land without a zone, without Uldum's lakes.

Hand-placed outlines are coarse polygons set by eye in the source's artboard coordinates. No
Blizzard map imagery is traced.

## Regenerating

Requires Python 3 and [shapely](https://pypi.org/project/shapely/) 2.x.

```bash
python3 -m pip install shapely
curl -L -o Eastern_Kingdoms.svg 'https://commons.wikimedia.org/wiki/Special:FilePath/Eastern_Kingdoms.svg'
curl -L -o Kalimdor_english.svg 'https://commons.wikimedia.org/wiki/Special:FilePath/Kalimdor_english.svg'
python3 tools/build_ek_map.py Eastern_Kingdoms.svg
python3 tools/build_kalimdor_map.py Kalimdor_english.svg
```

Both scripts overwrite the files in `data/`.

## Usage

These outlines are the continent maps of the app "Forever Loremaster Quest Log".

## License

The geometry in `data/` and the scripts in `tools/` are licensed under the
[Creative Commons Attribution-ShareAlike 4.0 International License](https://creativecommons.org/licenses/by-sa/4.0/)
(full legal code in [LICENSE](LICENSE)).

Attribution: "Continent outlines adapted from Eastern_Kingdoms.svg and Kalimdor_english.svg by
Syrio, Wikimedia Commons, CC BY-SA 4.0; modified."

## Disclaimer

This is an unofficial fan project. It is not affiliated with, endorsed by or sponsored by
Blizzard Entertainment. World of Warcraft, its world, zone names and geography are trademarks or
property of Blizzard Entertainment, Inc.
