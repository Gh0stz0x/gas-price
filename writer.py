# SPDX-FileCopyrightText: 2024 Cédric Bosdonnat <cedric.bosdonnat@gmail.com>
#
# SPDX-License-Identifier: MIT

# -*- coding: utf-8 -*-

import os
from datetime import datetime


# Colormap → HEX code for OsmAnd GPX
COLOR_HEX = {
    "green":  "#00AA00",
    "yellow": "#CCAA00",
    "blue":   "#0055FF",
    "white":  "#CCCCCC",
    "cyan":   "#00CCCC",
    "orange": "#FF8800",
    "purple": "#8800CC",
    "red":    "#CC0000",
}


class KmlWriter:
    """
    Write a gas prices KML file for Organic Maps / OsmAnd.
    """

    def __init__(self, filepath, name, source, color):
        self.filepath = filepath
        self._fd = open(filepath, "w", encoding="utf-8")
        self.name = name
        self.color = color

        now = datetime.now().isoformat(' ', timespec='minutes')
        self._fd.write(f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://earth.google.com/kml/2.2">
<Document>
  <Style id="placemark-{color}">
    <IconStyle>
      <Icon>
        <href>https://omaps.app/placemarks/placemark-{color}.png</href>
      </Icon>
    </IconStyle>
  </Style>
  <n>{name}</n>
  <visibility>1</visibility>
  <ExtendedData xmlns:mwm="https://omaps.app">
    <mwm:name>
      <mwm:lang code="default">{name}</mwm:lang>
    </mwm:name>
    <mwm:annotation>
    </mwm:annotation>
    <mwm:description>
      <mwm:lang code="en">Generated from {source} data on {now}</mwm:lang>
      <mwm:lang code="fr">Généré à partir des données de {source} à {now}</mwm:lang>
      <mwm:lang code="it">Generato dai dati {source} il {now}</mwm:lang>
      <mwm:lang code="es">Generado a partir de los datos de {source} el {now}</mwm:lang>
    </mwm:description>
    <mwm:accessRules>Local</mwm:accessRules>
  </ExtendedData>
""")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def close(self):
        if not self._fd.closed:
            self._fd.write("""</Document>
</kml>""")
            self._fd.close()

    def writeStation(self, price, update_time, lon, lat, vending):
        self._fd.write(f"""  <Placemark>
    <n>{price}</n>
    <TimeStamp><when>{update_time}</when></TimeStamp>
    <styleUrl>#placemark-{self.color}</styleUrl>
    <Point><coordinates>{lon},{lat}</coordinates></Point>
    <ExtendedData xmlns:mwm="https://omaps.app">
      <mwm:name><mwm:lang code="default">{price}</mwm:lang></mwm:name>
      <mwm:description>
        <mwm:lang code="default">Automate: {vending}</mwm:lang>
        <mwm:lang code="it">Modalità: {vending}</mwm:lang>
        <mwm:lang code="es">Modo: {vending}</mwm:lang>
      </mwm:description>
      <mwm:icon>Gas</mwm:icon>
    </ExtendedData>
  </Placemark>
""")


# ---------------------------------------------------------------------------
# Defining macro-categories and subcategories for multi-file GPX
# ---------------------------------------------------------------------------

MACRO_CATEGORY = {
    "Benzina":          "Benzina",
    "Benzina Speciale": "Benzina",
    "Gasolio":          "Gasolio",
    "Gasolio Speciale": "Gasolio",
    "GPL":              "GPL",
    "Metano / GNL":     "Metano",
    "HVO":              "HVO",
    "Idrogeno":         "Idrogeno",
    "Elettrico":        "Elettrico",
    "Altro":            "Altro",
}

MACRO_COLOR = {
    "Benzina":   COLOR_HEX["green"],
    "Gasolio":   COLOR_HEX["yellow"],
    "GPL":       COLOR_HEX["blue"],
    "Metano":    COLOR_HEX["white"],
    "HVO":       COLOR_HEX["orange"],
    "Idrogeno":  COLOR_HEX["purple"],
    "Elettrico": COLOR_HEX["red"],
    "Altro":     COLOR_HEX["yellow"],
}

SUBCATEGORY_COLORS = {
    "Benzina": {
        "Benzina":          COLOR_HEX["green"],
        "Benzina Speciale": COLOR_HEX["cyan"],
    },
    "Gasolio": {
        "Gasolio":          COLOR_HEX["yellow"],
        "Gasolio Speciale": COLOR_HEX["orange"],
    },
    "GPL": {
        "GPL":              COLOR_HEX["blue"],
    },
    "Metano": {
        "Metano / GNL":     COLOR_HEX["white"],
    },
    "HVO": {
        "HVO":              COLOR_HEX["orange"],
    },
    "Idrogeno": {
        "Idrogeno":         COLOR_HEX["purple"],
    },
    "Elettrico": {
        "Elettrico":        COLOR_HEX["red"],
    },
    "Altro": {
        "Altro":            COLOR_HEX["yellow"],
    },
}

FUEL_MAP = [
    (["v-power",  "excellium 9", "supreme ben", "especial ben",
      "ultimate", "momentum", "evo ben", "racing"], "Benzina Speciale"),
    (["benzina", "super sp", "super 95", "super 98", "gasolio senza", "sp95", "sp98"], "Benzina"),
    (["v-power d", "excellium d", "supreme d", "blue diesel", "iq diesel",
      "energy diesel", "excelium d", "oro", "premium", "prestazional",
      "speciale", "artic", "alpin", "invernale", "hvo diesel"], "Gasolio Speciale"),
    (["gasolio", "diesel", "blu", "gasol"], "Gasolio"),
    (["gpl", "autogas", "lpg"], "GPL"),
    (["metano", "gnl", "gnc", "cng", "lng"], "Metano / GNL"),
    (["hvo"], "HVO"),
    (["idrogeno", "hydrogen", "h2"], "Idrogeno"),
    (["elettr", "electric", "ev ", "ricaric"], "Elettrico"),
]


def normalize_fuel(fuel_raw):
    """Normalizza il nome grezzo del carburante in una sottocategoria standard."""
    fuel_lower = fuel_raw.lower()
    for keywords, category in FUEL_MAP:
        if any(kw in fuel_lower for kw in keywords):
            return category
    return "Altro"


class GpxMultiWriter:
    """
    Gestisce la scrittura di più file GPX separati per macro-categoria.
    """

    def __init__(self, out_dir, source):
        self.out_dir = out_dir
        self.source = source
        os.makedirs(out_dir, exist_ok=True)
        self._data = {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def writeStation(self, label, dt_iso, lon, lat, vending, fuel_raw, color=None):
        """Accumula il waypoint nella macro-categoria corretta, supportando il colore dinamico."""
        subcategory = normalize_fuel(fuel_raw)
        macro = MACRO_CATEGORY.get(subcategory, "Altro")
        if macro not in self._data:
            self._data[macro] = []
        self._data[macro].append((lat, lon, label, subcategory, vending, dt_iso, color))

    def close(self):
        """Scrive un file GPX per ogni macro-categoria."""
        now = datetime.now().isoformat(' ', timespec='minutes')
        files_written = []

        for macro, waypoints in self._data.items():
            filename = f"italy_{macro.lower().replace(' / ', '_').replace(' ', '_')}.gpx"
            filepath = os.path.join(self.out_dir, filename)
            subcategory_colors = SUBCATEGORY_COLORS.get(macro, {"Altro": COLOR_HEX["yellow"]})
            used_subcategories = {wp[3] for wp in waypoints}

            with open(filepath, "w", encoding="utf-8") as fd:
                fd.write(f"""<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="pododoo"
     xmlns="http://www.topografix.com/GPX/1/1"
     xmlns:osmand="https://osmand.net"
     xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
     xsi:schemaLocation="http://www.topografix.com/GPX/1/1
       http://www.topografix.com/GPX/1/1/gpx.xsd">
  <metadata>
    <name>Italy - {macro}</name>
    <desc>Generated from {self.source} data on {now}</desc>
  </metadata>
""")
                # Color-managed waypoints
                for lat, lon, label, subcategory, vending, dt_iso, dynamic_color in waypoints:
                    # If dynamic_color is passed, use that (gradient), otherwise use the default
                    color_hex = dynamic_color if dynamic_color else subcategory_colors.get(subcategory, MACRO_COLOR.get(macro, COLOR_HEX["yellow"]))

                    time_tag = f"\n    <time>{dt_iso}</time>" if dt_iso else ""
                    fd.write(f"""  <wpt lat="{lat}" lon="{lon}">
    <name>{label}</name>{time_tag}
    <type>{subcategory}</type>
    <desc>Modalità: {vending} / Modo: {vending}</desc>
    <extensions>
      <osmand:color>{color_hex}</osmand:color>
      <osmand:icon>fuel</osmand:icon>
      <osmand:background>circle</osmand:background>
    </extensions>
  </wpt>
""")

                # OsmAnd Groups
                fd.write("  <extensions>\n    <osmand:points_groups>\n")
                for subcat, color_hex in subcategory_colors.items():
                    if subcat in used_subcategories:
                        fd.write(
                            f'      <group name="{subcat}" color="{color_hex}" '
                            f'icon="fuel" background="circle"/>\n'
                        )
                fd.write("    </osmand:points_groups>\n  </extensions>\n</gpx>")

            files_written.append((filename, len(waypoints)))

        return files_written


class GpxWriter:
    """
    Write a gas prices GPX file with OsmAnd waypoint groups.
    """

    GROUPS = {
        "Benzina":          (COLOR_HEX["green"],  "fuel"),
        "Benzina Speciale": (COLOR_HEX["cyan"],   "fuel"),
        "Gasolio":          (COLOR_HEX["yellow"], "fuel"),
        "Gasolio Speciale": (COLOR_HEX["orange"], "fuel"),
        "GPL":              (COLOR_HEX["blue"],   "fuel"),
        "Metano / GNL":     (COLOR_HEX["white"],  "fuel"),
        "HVO":              (COLOR_HEX["purple"], "fuel"),
        "Idrogeno":         (COLOR_HEX["purple"], "fuel"),
        "Elettrico":        (COLOR_HEX["red"],    "fuel"),
        "Altro":            (COLOR_HEX["yellow"], "fuel"),
    }

    def __init__(self, filepath, name, source):
        self.filepath = filepath
        self._fd = open(filepath, "w", encoding="utf-8")
        self.name = name
        self.source = source
        self._waypoints = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def writeStation(self, label, dt_iso, lon, lat, vending, fuel_raw, color=None):
        category = normalize_fuel(fuel_raw)
        self._waypoints.append((lat, lon, label, category, vending, dt_iso, color))

    def close(self):
        if self._fd.closed:
            return

        now = datetime.now().isoformat(' ', timespec='minutes')
        used_groups = {wp[3] for wp in self._waypoints}

        self._fd.write(f"""<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="pododoo"
     xmlns="http://www.topografix.com/GPX/1/1"
     xmlns:osmand="https://osmand.net">
  <metadata>
    <name>{self.name}</name>
    <desc>Generated from {self.source} data on {now}</desc>
  </metadata>
""")

        for lat, lon, label, category, vending, dt_iso, dynamic_color in self._waypoints:
            color_hex = dynamic_color if dynamic_color else self.GROUPS.get(category, (COLOR_HEX["yellow"], "fuel"))[0]
            time_tag = f"\n    <time>{dt_iso}</time>" if dt_iso else ""
            self._fd.write(f"""  <wpt lat="{lat}" lon="{lon}">
    <name>{label}</name>{time_tag}
    <type>{category}</type>
    <desc>Modalità: {vending}</desc>
    <extensions>
      <osmand:color>{color_hex}</osmand:color>
      <osmand:icon>fuel</osmand:icon>
      <osmand:background>circle</osmand:background>
    </extensions>
  </wpt>
""")

        self._fd.write("  <extensions>\n    <osmand:points_groups>\n")
        for group_name, (color_hex, icon) in self.GROUPS.items():
            if group_name in used_groups:
                self._fd.write(
                    f'      <group name="{group_name}" color="{color_hex}" '
                    f'icon="{icon}" background="circle"/>\n'
                )
        self._fd.write("    </osmand:points_groups>\n  </extensions>\n</gpx>")
        self._fd.close()
